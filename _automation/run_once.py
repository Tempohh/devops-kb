#!/usr/bin/env python3
"""
run_once.py — iterazione bounded del loop di manutenzione KB (cross-platform).

Equivalente headless e portabile di KB_Aggiorna_Sicuro.bat / kb-infinite.ps1:
processa fino a --max-tasks task dalla coda di state.yaml, poi si ferma.
Pensato per essere invocato da GitHub Actions (Linux) o in locale (Windows).

Delego tutta la logica di stato a manage-state.py; qui c'e' solo l'orchestrazione:
  next-task -> pre-flight -> selezione modello -> `claude -p` -> check -> commit.

Uso:
  python _automation/run_once.py                 # 1 task, commit locale, no push
  python _automation/run_once.py --max-tasks 3
  python _automation/run_once.py --dry-run       # non chiama claude, non committa
  python _automation/run_once.py --push          # git push dopo i commit (uso locale)

Exit code:
  0  tutto ok, oppure rate limit (soft: il task resta pending, ritenta al prossimo run)
  1  errore di configurazione / ambiente
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AUTO_DIR      = Path(__file__).resolve().parent
PROJECT_ROOT  = AUTO_DIR.parent
STATE_PY      = AUTO_DIR / "manage-state.py"
CONFIG_FILE   = AUTO_DIR / "config.yaml"
TASK_FILE     = AUTO_DIR / "current-task.json"
LOG_FILE      = AUTO_DIR / "runs.log"

RATE_LIMIT_PATTERNS = [
    r"rate.limit", r"rate limit", r"overloaded", r"too many requests",
    r"usage limit", r"quota exceeded", r"hit your limit", r"resets \d",
    r"5-hour limit", r"try again later",
]

PROMPT_BY_TYPE = {
    "audit":       "audit-prompt.md",
    "expand":      "expand-prompt.md",
    "proposal":    "proposal-prompt.md",
    "review":      "review-prompt.md",
    "currency":    "currency-prompt.md",
    "consolidate": "consolidate-prompt.md",
}


# ── util ────────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [RUN_ONCE] {msg}"
    print("  " + line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config() -> dict:
    try:
        import yaml
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log(f"config.yaml non leggibile ({e}) — uso i default")
        return {}


def state(*args: str) -> str:
    """Chiama manage-state.py e ritorna stdout ripulito (ultima riga JSON/valore)."""
    res = subprocess.run(
        [sys.executable, str(STATE_PY), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=PROJECT_ROOT,
    )
    out = (res.stdout or "").strip()
    return out


def state_json(*args: str):
    raw = state(*args)
    # isola l'ultima riga che sembra JSON o 'null'
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    for cand in reversed(lines):
        if cand == "null":
            return None
        if cand.startswith("{") or cand.startswith("["):
            try:
                return json.loads(cand)
            except Exception:
                continue
    # forse e' un blob JSON multiriga
    try:
        return json.loads(raw)
    except Exception:
        return None


def find_claude() -> str | None:
    exe = shutil.which("claude")
    if exe:
        return exe
    # npm global su Linux CI
    for cand in (
        Path.home() / ".npm-global/bin/claude",
        Path("/usr/local/bin/claude"),
        Path("/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
    ):
        if cand.exists():
            return str(cand)
    # Windows: estensione VSCode
    for p in (Path.home() / ".vscode/extensions").glob(
        "anthropic.claude-code-*/resources/native-binary/claude.exe"
    ):
        return str(p)
    return None


def is_rate_limited(text: str, exit_code: int) -> bool:
    if exit_code == 529:
        return True
    low = text.lower()
    return any(re.search(p, low) for p in RATE_LIMIT_PATTERNS)


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=PROJECT_ROOT, check=check,
    )


def commit_task(task: dict, dry_run: bool) -> bool:
    """git add (escluso site/) + commit. Ritorna True se ha creato un commit."""
    if dry_run:
        log("[dry-run] salto il commit")
        return False
    git("add", "-A", "--", ":!site")
    staged = git("diff", "--cached", "--quiet")
    if staged.returncode == 0:
        log("nessuna modifica da committare")
        return False
    tid  = task.get("id", "?")
    ttype = task.get("type", "task")
    path = task.get("path", "")
    msg = f"kb: {ttype} {path} (auto #{tid})"
    r = git("commit", "-m", msg,
            "-m", "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>")
    if r.returncode == 0:
        log(f"commit: {msg}")
        return True
    log(f"commit fallito: {r.stderr.strip()[:200]}")
    return False


# ── pre-flight ─────────────────────────────────────────────────────────────

def preflight_skip(task: dict) -> str | None:
    """Ritorna un motivo di skip (0 token) o None se il task va eseguito."""
    ttype = task.get("type") or "new_topic"
    path  = task.get("path") or ""
    full  = PROJECT_ROOT / path if path else None

    if ttype in ("new_topic", "new-file") and full and full.exists():
        return "file gia' presente"
    if ttype in ("audit", "expand", "currency", "review") and full and path and not full.exists():
        return f"file assente — task {ttype} non applicabile"
    if ttype == "audit" and path:
        pf = state_json("audit-preflight", path)
        if pf and pf.get("pass"):
            return f"audit-preflight pass (lines={pf.get('lines')}, blocks={pf.get('code_blocks')})"
    return None


# ── esecuzione di un singolo task ──────────────────────────────────────────

def run_task(task: dict, cfg: dict, claude_bin: str, args) -> str:
    """
    Esegue un task. Ritorna uno di:
      'done'  completato/skippato — si puo' passare al prossimo
      'rate'  rate limit — fermarsi, task resta pending
      'error' errore di esecuzione — task force-completato, fermarsi
    """
    tid   = task.get("id", "?")
    ttype = task.get("type") or "new_topic"
    path  = task.get("path") or ""
    log(f"task [{task.get('priority','P?')}] {tid} {ttype} {path}")

    reason = preflight_skip(task)
    if reason:
        log(f"[SKIP] {reason}")
        if not args.dry_run:
            state("force-complete", str(tid))
        return "done"

    if not args.dry_run:
        # scrivi current-task.json (UTF-8 senza BOM)
        TASK_FILE.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
        state("mark-started", str(tid))

    prompt_file = AUTO_DIR / PROMPT_BY_TYPE.get(ttype, "run-prompt.md")
    if not prompt_file.exists():
        prompt_file = AUTO_DIR / "run-prompt.md"
    prompt = prompt_file.read_text(encoding="utf-8")

    models = (cfg.get("models") or {})
    mcfg   = models.get(ttype) or models.get("default") or {}
    model  = args.model_override or mcfg.get("model")

    cmd = [claude_bin, "--dangerously-skip-permissions"]
    if model:
        cmd += ["--model", model]
    if cfg.get("pass_effort_flag") and mcfg.get("effort"):
        cmd += ["--effort", mcfg["effort"]]
    cmd += ["-p", prompt]

    log(f"prompt={prompt_file.name} model={model or '(default)'}")

    if args.dry_run:
        log("[dry-run] non chiamo claude; force-complete simulato saltato")
        return "done"

    started = datetime.now()
    proc = subprocess.run(
        cmd, input="", capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=PROJECT_ROOT,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    elapsed = int((datetime.now() - started).total_seconds())

    state("update-run")

    if is_rate_limited(out, proc.returncode):
        log(f"[RATE_LIMIT] task {tid} resta pending — stop soft dopo {elapsed}s")
        return "rate"

    if proc.returncode != 0:
        log(f"[ERROR] exit={proc.returncode} dopo {elapsed}s — force-complete")
        for l in [x for x in out.splitlines() if x.strip()][-4:]:
            log(f"  | {l[:200]}")
        state("force-complete", str(tid))
        return "error"

    state("force-complete", str(tid))

    # post-check leggeri
    if path:
        state("validate-all", json.dumps([path]))
    state("prune")

    tail = [x for x in out.splitlines() if x.strip()][-6:]
    for l in tail:
        log(f"  > {l[:200]}")
    log(f"[OK] task {tid} in {elapsed}s")

    commit_task(task, args.dry_run)
    return "done"


# ── queue-empty handling ──────────────────────────────────────────────────

def handle_empty_queue(cfg: dict, args) -> bool:
    """Ritorna True se ha modificato lo stato (creato task) e conviene rifare next-task."""
    analysis = state_json("analysis-status")
    if analysis and analysis.get("needs_analysis"):
        log(f"[ANALISI] {analysis.get('reason')} — init-analysis")
        if not args.dry_run:
            r = state_json("init-analysis")
            if r:
                log(f"[ANALISI] {r.get('tasks_created')} task su {r.get('total_kb_files')} file")
        return True

    props = state_json("list-proposals")
    pending = int((props or {}).get("count", 0) or 0)
    if pending > 0:
        loop_cfg = cfg.get("loop") or {}
        if loop_cfg.get("auto_approve_proposals", True):
            log(f"[PROPOSTE] {pending} pendenti — auto-approvazione (CI: nessun umano)")
            if not args.dry_run:
                state("auto-approve-proposals")
            return True
        log(f"[PROPOSTE] {pending} pendenti — lasciate per review manuale")
        return False

    # coda vuota, nessuna proposta: inietta una sessione di proposte
    log("[PROPOSTE] coda vuota — inietto task proposal")
    if not args.dry_run:
        state("inject-proposal-task")
    return True


# ── main ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-tasks", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--model-override", default=None)
    args = ap.parse_args()

    if not STATE_PY.exists():
        log("manage-state.py non trovato"); return 1

    # Interruttore di pausa — stesso nome/valori della Actions variable usata
    # dalla CI. Utile per fermare KB_Aggiorna_Sicuro.bat in locale:
    #   setx KB_MAINTENANCE_ENABLED false   (Windows, persistente)
    if os.environ.get("KB_MAINTENANCE_ENABLED", "").strip().lower() in {"false", "0", "off", "no"} and not args.dry_run:
        log("automazione in pausa (KB_MAINTENANCE_ENABLED) — nessun task eseguito")
        print(json.dumps({"processed": 0, "stop_reason": "paused"}, ensure_ascii=False))
        return 0

    cfg = load_config()

    claude_bin = None
    if not args.dry_run:
        claude_bin = find_claude()
        if not claude_bin:
            log("eseguibile `claude` non trovato — impossibile procedere "
                "(in CI: `npm i -g @anthropic-ai/claude-code`)")
            return 1
        log(f"claude: {claude_bin}")

    processed = 0
    stop_reason = "max-tasks"
    for _ in range(max(1, args.max_tasks)):
        task = state_json("next-task")
        if task is None:
            if handle_empty_queue(cfg, args):
                task = state_json("next-task")
            if task is None:
                stop_reason = "coda vuota"
                break

        outcome = run_task(task, cfg, claude_bin, args)
        processed += 1
        if outcome == "rate":
            stop_reason = "rate limit (soft)"
            break
        if outcome == "error":
            stop_reason = "errore task"
            break

    # manutenzione di fine giro (best-effort)
    if not args.dry_run and processed > 0:
        state("check-mkdocs")
        state("maintain")
        state("stats-doc", "write")   # rigenera la tabella in docs/index.md
        # eventuali P0 da broken link + tabella stats aggiornata: committali
        git("add", "-A", "--", ":!site")
        if git("diff", "--cached", "--quiet").returncode != 0:
            git("commit", "-m", "kb: post-run maintenance (auto)",
                "-m", "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>")

    if args.push and not args.dry_run:
        r = git("push", "origin", "HEAD:master")
        log("push ok" if r.returncode == 0 else f"push fallito: {r.stderr.strip()[:200]}")

    stats = state_json("stats") or {}
    summary = {
        "processed": processed,
        "stop_reason": stop_reason,
        "pending": stats.get("total_pending"),
        "total_ops": stats.get("total_ops"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    log(f"fine: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
