"""
Gestione dello state.yaml per il sistema di automazione KB.
Comandi:
  next-task              Stampa il prossimo task pending come JSON (o 'null')
  mark-started <id>      Imposta checkpoint interrupted_task
  force-complete <id>    Forza task come completed/skipped (fallback se agente non aggiorna)
  check-mkdocs           Esegue mkdocs build, trova broken links, aggiunge P0 alla queue
  estimate-tokens <path> <prompt_chars> <output_chars>  Stima token usati
  prune                  Mantieni solo ultimi MAX_COMPLETED nella lista completed
  validate-all <json>    Verifica struttura MkDocs di un array di path
  stats                  Stampa riepilogo JSON della coda e contatori
  update-run             Incrementa total_runs e aggiorna last_run
  analysis-status        Verifica se e' necessaria una nuova analisi KB
  init-analysis          Crea task audit/proposal per ogni file KB (checkpoint nativo via queue)
  list-proposals         Elenca proposte in attesa di approvazione
  approve-proposal <id>  Approva proposta: la aggiunge alla queue come task
  reject-proposal <id>   Rifiuta proposta (sposta in rejected/)
"""

import sys
import os
import json
import re
import yaml
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT      = Path(__file__).parent.parent / "docs"
STATE_FILE     = Path(__file__).parent / "state.yaml"
PROPOSALS_DIR  = Path(__file__).parent / "proposals"
MAX_COMPLETED  = 15


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_state():
    with open(STATE_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write("# Stato del sistema di automazione KB\n")
        f.write("# Aggiornato automaticamente - non modificare 'completed' manualmente\n\n")
        yaml.dump(state, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=120)


def check_pages_nav_entries(directory):
    """Verifica che ogni entry in .pages nav esista fisicamente."""
    pages_file = DOCS_ROOT / directory / ".pages"
    if not pages_file.exists():
        return []
    with open(pages_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "nav" not in data:
        return []
    missing = []
    for entry in data["nav"]:
        if entry is None:
            continue
        if not (DOCS_ROOT / directory / entry).exists():
            missing.append(f"{directory}/.pages nav entry '{entry}' non esiste")
    return missing


# ── Comandi ──────────────────────────────────────────────────────────────────

def cmd_next_task():
    """Stampa il prossimo task pending come JSON. 'null' se coda vuota."""
    state = load_state()

    # Se c'e' un interrupted_task, ha priorita' assoluta — ma solo se e' ancora pending
    it = state.get("interrupted_task")
    if it:
        for item in state.get("queue", []):
            if item.get("id") == it.get("id") and item.get("status") == "pending":
                print(json.dumps(item, ensure_ascii=False))
                return
        # interrupted_task e' stale (item gia' completato o non trovato) — pulisci
        state["interrupted_task"] = None
        save_state(state)

    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    pending = [i for i in state.get("queue", []) if i.get("status") == "pending"]
    if not pending:
        print("null")
        return
    pending.sort(key=lambda x: priority_order.get(x.get("priority", "P3"), 3))
    print(json.dumps(pending[0], ensure_ascii=False))


def cmd_mark_started(task_id):
    """Imposta interrupted_task (checkpoint di sicurezza prima di chiamare claude)."""
    state = load_state()
    for item in state.get("queue", []):
        if item.get("id") == task_id:
            state["interrupted_task"] = {
                "id": task_id,
                "path": item.get("path"),
                "step": "started"
            }
            save_state(state)
            return
    print(f"Task {task_id} non trovato", file=sys.stderr)
    sys.exit(1)


def _write_log(message: str):
    """Scrive una riga nel runs.log (best-effort, non blocca se fallisce)."""
    log_file = Path(__file__).parent / "runs.log"
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{ts} {message}\n")
    except Exception:
        pass


def cmd_force_complete(task_id):
    """
    Fallback PS1: forza un task come completed o skipped se l'agente
    ha terminato senza aggiornare state.yaml.
    Solo attivo se il task e' ancora pending/in_progress — se gia' aggiornato dall'agente, no-op.
    """
    state = load_state()
    for item in state.get("queue", []):
        if item.get("id") == task_id and item.get("status") in ("pending", "in_progress"):
            file_path = item.get("path", "")
            file_exists = bool(file_path) and (Path(__file__).parent.parent / file_path).exists()

            if file_exists:
                item["status"] = "completed"
                note = "File presente su disco - completato ma state non aggiornato dall'agente"
                log_tag = "FORCE_COMPLETE"
            else:
                item["status"] = "skipped"
                note = "File non creato - task saltato o fallito, forzato come skipped"
                log_tag = "FORCE_SKIP"

            # Pulisci interrupted_task
            it = state.get("interrupted_task") or {}
            if it.get("id") == task_id:
                state["interrupted_task"] = None

            # Aggiorna contatori (solo total_ops — total_runs e' aggiornato dall'agente o non conta)
            state["total_ops"] = state.get("total_ops", 0) + 1

            # Aggiungi a completed
            state.setdefault("completed", []).append({
                "id": task_id,
                "path": file_path,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": note
            })

            save_state(state)
            _write_log(f"[FALLBACK] {log_tag} task={task_id} path={file_path}")
            print(f"force-complete: {task_id} -> {item['status']} | {note}")
            return

    # Task gia' completato dall'agente (stato aggiornato correttamente) — no-op
    it = state.get("interrupted_task") or {}
    if it.get("id") == task_id:
        state["interrupted_task"] = None
        save_state(state)
    print(f"force-complete: {task_id} gia' gestito — nessuna azione (agente ha aggiornato state correttamente)")


def cmd_check_mkdocs():
    """
    Esegue mkdocs build, trova broken links nei WARNING, aggiunge come P0 alla queue.
    """
    project_root = Path(__file__).parent.parent
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=project_root, env=env
    )
    output = result.stdout + result.stderr

    # Pattern MkDocs: WARNING - Doc file 'X' contains a link 'Y', but the target 'Z' is not found
    pattern = re.compile(
        r"WARNING.*?Doc file '([^']+)' contains a link '[^']+', but the target '([^']+)' is not found"
    )

    state = load_state()
    existing_paths = {item.get("path", "") for item in state.get("queue", [])}
    existing_paths.update(c.get("path", "") for c in state.get("completed", []))

    new_items = []
    seen_targets = set()

    for match in pattern.finditer(output):
        source_file = match.group(1).replace("\\", "/")
        target      = match.group(2).replace("\\", "/")

        # Normalizza il target a path docs-relativo
        if not target.startswith("docs/"):
            target_path = f"docs/{target}"
        else:
            target_path = target

        if target_path in existing_paths or target_path in seen_targets:
            continue
        seen_targets.add(target_path)

        category = target.split("/")[0] if "/" in target else "unknown"
        item_id  = f"W-{len(new_items)+1:03d}"

        new_items.append({
            "id": item_id,
            "type": "new_topic",
            "path": target_path,
            "category": category,
            "priority": "P0",
            "reason": f"Broken link: '{source_file}' referenzia questo file che non esiste ancora.",
            "worth_if": "Broken link attivo - necessario per evitare warning MkDocs",
            "skip_if": "Solo se il link nel file sorgente viene rimosso/corretto",
            "status": "pending"
        })

    if new_items:
        state["queue"] = new_items + state["queue"]
        save_state(state)
        print(f"check-mkdocs: {len(new_items)} broken link aggiunti come P0")
        for item in new_items:
            print(f"  {item['id']}: {item['path']}")
    else:
        print("check-mkdocs: nessun broken link trovato")


def cmd_estimate_tokens(file_path, prompt_chars, output_chars):
    """
    Stima i token usati in una run (approssimazione: chars/4).
    Input: prompt + file letti stimati
    Output: risposta claude + file creato
    """
    prompt_chars  = int(prompt_chars)
    output_chars  = int(output_chars)

    # Overhead realistico per file letti da claude in ogni run:
    #   run-prompt.md     ~1800 chars
    #   current-task.json ~500  chars
    #   CLAUDE.md (sezioni rilevanti) ~8000 chars
    #   state.yaml        ~7000 chars
    #   Glob/Grep checks  ~2000 chars stimati
    #   Total input overhead: ~19300 chars
    read_overhead = 19300

    project_root = Path(__file__).parent.parent

    # Leggi dimensione reale di CLAUDE.md e state.yaml se disponibili
    try:
        claude_md_size = (project_root / "CLAUDE.md").stat().st_size
        task_json_size = (project_root / "_automation" / "current-task.json").stat().st_size
        # state.yaml NON viene piu' letto da claude (aggiornato solo dal PS1)
        # prompt_chars e' gia' la dimensione del prompt attivo — non aggiungerla di nuovo
        read_overhead  = claude_md_size + task_json_size + 2000
    except Exception:
        pass

    input_tokens  = (int(prompt_chars) + read_overhead) // 4
    output_tokens = int(output_chars) // 4

    # Dimensione del file creato (output di claude)
    full_path   = project_root / file_path
    file_tokens = 0
    if full_path.exists():
        try:
            file_tokens = full_path.stat().st_size // 4
        except Exception:
            pass
    output_tokens += file_tokens

    total = input_tokens + output_tokens
    print(json.dumps({
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "total_tokens":  total,
        "input_overhead_chars": read_overhead,
        "note": "stima realistica (chars/4) — errore tipico ±25%"
    }, ensure_ascii=False))


def cmd_update_run():
    """
    Aggiorna total_runs e last_run in state.yaml.
    Chiamato dal PS1 dopo ogni run (indipendentemente dall'agente).
    """
    state = load_state()
    state["total_runs"] = state.get("total_runs", 0) + 1
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print(f"update-run: total_runs={state['total_runs']} last_run={state['last_run']}")


def cmd_stats():
    """Stampa riepilogo JSON della coda: contatori, stato per priorita', ultimo run."""
    state = load_state()
    queue = state.get("queue", [])

    by_status           = {}
    pending_by_priority = {}
    pending_by_type     = {}
    for item in queue:
        s = item.get("status", "unknown")
        p = item.get("priority", "P3")
        t = item.get("type", "new_topic")
        by_status[s] = by_status.get(s, 0) + 1
        if s == "pending":
            pending_by_priority[p] = pending_by_priority.get(p, 0) + 1
            pending_by_type[t]     = pending_by_type.get(t, 0) + 1

    total_pending = by_status.get("pending", 0)

    # Stima token rimanenti (approssimazione 13k token/run per nuovi file, 3k per skip)
    estimated_tokens_left = total_pending * 13000  # rough estimate

    print(json.dumps({
        "total_ops":   state.get("total_ops", 0),
        "total_runs":  state.get("total_runs", 0),
        "by_status":   by_status,
        "pending_by_priority": pending_by_priority,
        "pending_by_type":     pending_by_type,
        "total_pending": total_pending,
        "completed_in_memory": len(state.get("completed", [])),
        "last_run":    state.get("last_run"),
        "interrupted_task": state.get("interrupted_task"),
        "estimated_tokens_remaining": estimated_tokens_left,
        "analysis":    state.get("analysis", {}),
    }, ensure_ascii=False, indent=2))


def cmd_prune():
    """Mantieni solo gli ultimi MAX_COMPLETED nella lista completed."""
    state = load_state()
    completed = state.get("completed", [])
    if len(completed) > MAX_COMPLETED:
        removed = len(completed) - MAX_COMPLETED
        state["completed"] = completed[-MAX_COMPLETED:]
        save_state(state)
        print(f"Pruned {removed} completed. Mantenuti: {MAX_COMPLETED}")
    else:
        print(f"Nessun pruning ({len(completed)}/{MAX_COMPLETED})")


def cmd_validate_all(paths_json):
    """
    Dato JSON array di path, verifica struttura MkDocs (_index.md, .pages, nav entries).
    """
    paths = json.loads(paths_json)
    all_missing = []

    for p in paths:
        p_path = Path(p)
        dirs_to_check = []

        if p_path.suffix:
            dirs_to_check.append(p_path.parent)
            if len(p_path.parts) > 2:
                dirs_to_check.append(p_path.parent.parent)
        else:
            dirs_to_check.append(p_path)

        for d in dirs_to_check:
            d_str = str(d).replace("\\", "/").removeprefix("docs/")
            if d_str in ("docs", ".", ""):
                continue
            target = DOCS_ROOT / d_str
            if not target.exists():
                continue
            if not (target / "_index.md").exists():
                all_missing.append(f"{d_str}/_index.md")
            if not (target / ".pages").exists():
                all_missing.append(f"{d_str}/.pages")
            else:
                all_missing.extend(check_pages_nav_entries(d_str))

    result = {"ok": len(all_missing) == 0, "missing": list(set(all_missing))}
    print(json.dumps(result, ensure_ascii=False))


# ── Analisi KB ────────────────────────────────────────────────────────────────

def find_kb_content_files():
    """
    Tutti i .md di contenuto in docs/.
    Esclude:
    - file il cui nome inizia con _ (es. _index.md)
    - file in directory il cui nome inizia con _ (es. _templates/)
    """
    files = []
    for path in DOCS_ROOT.rglob("*.md"):
        if path.name.startswith("_"):
            continue
        # Escludi se qualsiasi directory antenata (dentro docs/) inizia con _
        rel_parts = path.relative_to(DOCS_ROOT).parts[:-1]  # directory sotto docs/
        if any(part.startswith("_") for part in rel_parts):
            continue
        files.append(path.relative_to(DOCS_ROOT.parent).as_posix())
    return sorted(files)


def cmd_analysis_status():
    """
    Ritorna JSON con needs_analysis=True/False.
    Auto-completa l'analisi se era in corso e non ci sono piu' task di analisi pendenti.
    """
    state = load_state()
    queue = state.get("queue", [])
    analysis_types = ("audit", "expand", "proposal")
    pending_analysis = [i for i in queue if i.get("status") == "pending" and i.get("type") in analysis_types]

    analysis = state.get("analysis", {})
    last_started   = analysis.get("last_started")
    last_completed = analysis.get("last_completed")

    # Auto-complete: l'analisi era avviata, non ci sono piu' task pendenti -> segna completa
    if last_started and not pending_analysis:
        try:
            ls = datetime.fromisoformat(last_started)
            lc = datetime.fromisoformat(last_completed) if last_completed else None
            if lc is None or (ls.replace(tzinfo=None) > lc.replace(tzinfo=None)):
                state["analysis"]["last_completed"] = datetime.now(timezone.utc).isoformat()
                save_state(state)
                last_completed = state["analysis"]["last_completed"]
                _write_log("[ANALYSIS] auto-complete: tutti i task di analisi elaborati")
        except Exception:
            pass

    if pending_analysis:
        print(json.dumps({
            "needs_analysis": False,
            "reason": f"{len(pending_analysis)} task di analisi ancora in coda",
            "pending_count": len(pending_analysis),
            "in_progress": True
        }, ensure_ascii=False))
        return

    if not last_completed:
        print(json.dumps({
            "needs_analysis": True,
            "reason": "Prima analisi mai eseguita"
        }, ensure_ascii=False))
        return

    try:
        last_dt = datetime.fromisoformat(last_completed)
        now = datetime.now(timezone.utc) if last_dt.tzinfo else datetime.now()
        days_since = (now - last_dt).days
    except Exception:
        days_since = 999

    print(json.dumps({
        "needs_analysis": days_since >= 7,
        "reason": f"Ultima analisi completata {days_since} giorni fa",
        "days_since": days_since,
        "last_completed": last_completed
    }, ensure_ascii=False))


def cmd_init_analysis():
    """
    Scansiona docs/, crea task audit (P3) per ogni file di contenuto non gia' in coda
    e 1 task proposal (P3) per la generazione di proposte trasversali.
    I task salvati nella queue sono il checkpoint nativo: sopravvivono a qualsiasi interruzione.
    """
    state = load_state()
    kb_files = find_kb_content_files()

    queued_paths = {item.get("path") for item in state.get("queue", [])}

    # Calcola ID massimo corrente
    max_id = 0
    for item in state.get("queue", []):
        raw = str(item.get("id", "0"))
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            max_id = max(max_id, int(digits))

    new_tasks = []
    auto_completed = 0
    for path in kb_files:
        if path in queued_paths:
            continue

        # Esegui pre-flight locale (0 token) per conoscere gli issue prima di creare il task
        pf = {"pass": False, "issues": [], "lines": 0, "code_blocks": 0}
        try:
            full_path = Path(__file__).parent.parent / path
            if full_path.exists():
                # Riusa la logica di audit_preflight inline (evita subprocess)
                pf_content = full_path.read_text(encoding="utf-8", errors="replace")
                pf_lines = sum(1 for l in pf_content.splitlines() if l.strip())
                pf_codeblocks = pf_content.count("```") // 2
                pf_lower = pf_content.lower()
                ts_kws = ["## troubleshooting","## risoluzione","## problemi comuni","## debug"]
                has_ts = any(kw in pf_lower for kw in ts_kws)
                pf["lines"] = pf_lines
                pf["code_blocks"] = pf_codeblocks
                if pf_lines >= 150 and pf_codeblocks >= 2 and has_ts:
                    pf["pass"] = True
                else:
                    if not has_ts: pf["issues"].append("no_troubleshooting_section")
                    if pf_codeblocks < 2: pf["issues"].append(f"pochi_codeblock:{pf_codeblocks}")
                    if pf_lines < 150: pf["issues"].append(f"corto:{pf_lines}righe")
        except Exception:
            pass

        if pf["pass"]:
            # File gia' buono: segnalo come auto-completato (nessun task creato)
            auto_completed += 1
            # Aggiungiamo direttamente ai completed per non riprocessarlo nelle prossime analisi
            state.setdefault("completed", []).append({
                "id": f"auto-{path.replace('/','_')}",
                "path": path,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": f"audit-preflight: pass (lines={pf['lines']}, blocks={pf['code_blocks']})"
            })
            queued_paths.add(path)
            continue

        # File con issue: crea task con reason che descrive gia' l'issue specifico
        issue_str = ", ".join(pf["issues"]) if pf["issues"] else "qualita' da verificare"
        task_id = str(max_id + len(new_tasks) + 1)
        new_tasks.append({
            "id": task_id,
            "type": "audit",
            "path": path,
            "category": path.split("/")[1] if len(path.split("/")) > 1 else "unknown",
            "priority": "P3",
            "status": "pending",
            "reason": f"Issue identificati: {issue_str}"
        })

    # 1 task proposal per analisi trasversale (se non gia' presente)
    prop_sentinel = "_automation/proposals"
    if prop_sentinel not in queued_paths:
        task_id = str(max_id + len(new_tasks) + 1)
        new_tasks.append({
            "id": task_id,
            "type": "proposal",
            "path": prop_sentinel,
            "category": "meta",
            "priority": "P3",
            "status": "pending",
            "reason": "Analisi trasversale KB: genera proposte di miglioramento per approvazione utente"
        })

    state["queue"].extend(new_tasks)
    state["total_ops"] = state.get("total_ops", 0) + len(new_tasks)

    if "analysis" not in state:
        state["analysis"] = {}
    state["analysis"]["last_started"] = datetime.now(timezone.utc).isoformat()
    state["analysis"]["total_files"]   = len(kb_files)
    state["analysis"]["tasks_created"] = len(new_tasks)

    save_state(state)
    audit_n = len([t for t in new_tasks if t["type"] == "audit"])
    _write_log(f"[ANALYSIS] init: {len(new_tasks)} task ({audit_n} audit + 1 proposal), {auto_completed} auto-ok su {len(kb_files)} file KB")

    print(json.dumps({
        "status": "ok",
        "tasks_created": len(new_tasks),
        "audit_tasks":    audit_n,
        "proposal_tasks": 1,
        "auto_completed": auto_completed,
        "total_kb_files": len(kb_files)
    }, ensure_ascii=False))


def cmd_audit_preflight(file_path):
    """
    Valutazione qualità locale di un file KB: 0 token, solo lettura.
    Ritorna pass=True se il file soddisfa già i criteri minimi.
    Se pass=True il PS1 può completare il task senza chiamare claude.
    """
    full_path = Path(__file__).parent.parent / file_path
    if not full_path.exists():
        print(json.dumps({"pass": False, "issues": ["file non trovato"]}))
        return

    try:
        content = full_path.read_text(encoding="utf-8")
    except Exception as e:
        print(json.dumps({"pass": False, "issues": [str(e)]}))
        return

    issues = []

    # Conta righe di contenuto (non frontmatter)
    in_frontmatter = False
    fm_closed = False
    content_lines = 0
    for i, line in enumerate(content.splitlines()):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            in_frontmatter = False
            fm_closed = True
            continue
        if not in_frontmatter:
            content_lines += 1

    if content_lines < 150:
        issues.append(f"corto:{content_lines}righe")

    # Code blocks
    code_block_count = content.count("```") // 2
    if code_block_count < 2:
        issues.append(f"pochi_codeblock:{code_block_count}")

    # Sezione Troubleshooting (accetta varianti IT/EN)
    lower = content.lower()
    ts_keywords = ["## troubleshooting", "## risoluzione", "## problemi comuni", "## debug"]
    ts_idx = -1
    for kw in ts_keywords:
        if kw in lower:
            ts_idx = lower.index(kw)
            break
    if ts_idx == -1:
        issues.append("no_troubleshooting_section")
    else:
        ts_end = lower.find("\n## ", ts_idx + 5)
        ts_body = content[ts_idx: ts_end if ts_end > 0 else len(content)]
        ts_items = ts_body.count("###") + ts_body.lower().count("**sintomo") + ts_body.lower().count("**problema") + ts_body.lower().count("**errore")
        if ts_items < 3:
            issues.append(f"pochi_ts:{ts_items}")

    # Frontmatter: search_keywords e related
    fm_text = ""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end > 0:
            fm_text = content[4:end]

    if fm_text:
        kw_match = re.search(r"search_keywords:\s*\[([^\]]*)\]", fm_text)
        if kw_match:
            kw_count = len([k for k in kw_match.group(1).split(",") if k.strip()])
            if kw_count < 10:
                issues.append(f"pochi_keywords:{kw_count}")
        else:
            issues.append("no_keywords")

        rel_match = re.search(r"related:\s*\[([^\]]*)\]", fm_text)
        if rel_match:
            rel_items = [r.strip() for r in rel_match.group(1).split(",") if r.strip()]
            if len(rel_items) < 2:
                issues.append(f"pochi_related:{len(rel_items)}")
        else:
            issues.append("no_related")

        status_match = re.search(r"status:\s*['\"]?(\S+?)['\"]?\s*$", fm_text, re.MULTILINE)
        if status_match and status_match.group(1) in ("draft", "needs-review"):
            issues.append(f"status:{status_match.group(1)}")

    passed = len(issues) == 0
    print(json.dumps({
        "pass": passed,
        "lines": content_lines,
        "code_blocks": code_block_count,
        "issues": issues
    }, ensure_ascii=False))


# ── Proposte ──────────────────────────────────────────────────────────────────

def cmd_list_proposals():
    """Elenca le proposte in pending/ come JSON."""
    pending_dir = PROPOSALS_DIR / "pending"
    if not pending_dir.exists():
        print(json.dumps({"count": 0, "proposals": []}, ensure_ascii=False))
        return

    proposals = []
    for f in sorted(pending_dir.glob("*.yaml")):
        try:
            with open(f, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            data["_file"] = f.stem
            proposals.append(data)
        except Exception:
            pass

    print(json.dumps({"count": len(proposals), "proposals": proposals},
                     ensure_ascii=False, indent=2))


def cmd_approve_proposal(prop_id):
    """
    Approva una proposta (cerca per nome file o id interno):
    - sposta da pending/ ad approved/
    - crea il task corrispondente nella queue
    """
    import shutil
    pending_dir  = PROPOSALS_DIR / "pending"
    approved_dir = PROPOSALS_DIR / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    if not pending_dir.exists():
        print(json.dumps({"status": "error", "message": "Nessuna proposta pendente"}, ensure_ascii=False))
        return

    target_file = None
    target_data = None
    for f in pending_dir.glob("*.yaml"):
        if f.stem == prop_id or f.stem.startswith(prop_id):
            target_file = f
        else:
            try:
                with open(f, encoding="utf-8") as fp:
                    d = yaml.safe_load(fp) or {}
                if str(d.get("id", "")) == str(prop_id):
                    target_file = f
            except Exception:
                pass
        if target_file:
            with open(target_file, encoding="utf-8") as fp:
                target_data = yaml.safe_load(fp) or {}
            break

    if not target_file or not target_data:
        print(json.dumps({"status": "error", "message": f"Proposta '{prop_id}' non trovata"}, ensure_ascii=False))
        return

    state = load_state()
    max_id = max(
        (int(str(i.get("id", 0))) for i in state.get("queue", []) if str(i.get("id", "")).isdigit()),
        default=0
    )

    # target_file / target_files → path (le proposte usano target_file, non path)
    raw_target = target_data.get("target_file", target_data.get("target_files", ""))
    if isinstance(raw_target, list):
        raw_target = raw_target[0] if raw_target else ""
    path = raw_target.lstrip("/") if raw_target else ""

    # Mappa tipo proposta → tipo task standard
    type_map = {
        "new-file":       "new_topic",
        "new_topic":      "new_topic",
        "extend-section": "expand",
        "extend":         "expand",
        "expand":         "expand",
        "fix-relation":   "audit",
        "fix-link":       "audit",
        "audit":          "audit",
        "consolidate":    "audit",
    }
    raw_type = target_data.get("type", "expand")
    task_type = type_map.get(raw_type, "expand")

    # Mappa priorità testuale → P-code
    priority_map = {"high": "P1", "medium": "P2", "low": "P3"}
    raw_prio = str(target_data.get("priority", "medium")).lower()
    task_priority = priority_map.get(raw_prio, raw_prio.upper() if raw_prio.startswith("p") else "P2")

    task = {
        "id": str(max_id + 1),
        "type": task_type,
        "path": path,
        "category": path.split("/")[1] if path and "/" in path else "meta",
        "priority": task_priority,
        "status": "pending",
        "reason": target_data.get("description", target_data.get("title", "")),
        "proposal_id": target_file.stem
    }
    state["queue"].append(task)
    state["total_ops"] = state.get("total_ops", 0) + 1
    save_state(state)

    target_data["status"] = "approved"
    target_data["approved_at"] = datetime.now().date().isoformat()
    with open(approved_dir / target_file.name, "w", encoding="utf-8") as fp:
        yaml.dump(target_data, fp, allow_unicode=True)
    target_file.unlink()

    _write_log(f"[PROPOSAL] approved: {target_file.stem} -> task {task['id']}")
    print(json.dumps({"status": "ok", "task_id": task["id"], "proposal": target_file.stem}, ensure_ascii=False))


def cmd_reject_proposal(prop_id):
    """Rifiuta una proposta (sposta in rejected/)."""
    import shutil
    pending_dir  = PROPOSALS_DIR / "pending"
    rejected_dir = PROPOSALS_DIR / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)

    if not pending_dir.exists():
        print(json.dumps({"status": "error", "message": "Nessuna proposta pendente"}, ensure_ascii=False))
        return

    for f in pending_dir.glob("*.yaml"):
        if f.stem == prop_id or f.stem.startswith(prop_id):
            shutil.move(str(f), str(rejected_dir / f.name))
            _write_log(f"[PROPOSAL] rejected: {f.stem}")
            print(json.dumps({"status": "ok", "proposal": f.stem}, ensure_ascii=False))
            return

    print(json.dumps({"status": "error", "message": f"Proposta '{prop_id}' non trovata"}, ensure_ascii=False))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "next-task":
        cmd_next_task()
    elif cmd == "mark-started" and len(sys.argv) >= 3:
        cmd_mark_started(sys.argv[2])
    elif cmd == "force-complete" and len(sys.argv) >= 3:
        cmd_force_complete(sys.argv[2])
    elif cmd == "check-mkdocs":
        cmd_check_mkdocs()
    elif cmd == "estimate-tokens" and len(sys.argv) >= 5:
        cmd_estimate_tokens(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "prune":
        cmd_prune()
    elif cmd == "validate-all" and len(sys.argv) >= 3:
        cmd_validate_all(sys.argv[2])
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "update-run":
        cmd_update_run()
    elif cmd == "audit-preflight" and len(sys.argv) >= 3:
        cmd_audit_preflight(sys.argv[2])
    elif cmd == "analysis-status":
        cmd_analysis_status()
    elif cmd == "init-analysis":
        cmd_init_analysis()
    elif cmd == "list-proposals":
        cmd_list_proposals()
    elif cmd == "approve-proposal" and len(sys.argv) >= 3:
        cmd_approve_proposal(sys.argv[2])
    elif cmd == "reject-proposal" and len(sys.argv) >= 3:
        cmd_reject_proposal(sys.argv[2])
    else:
        print(f"Comando sconosciuto: {cmd}", file=sys.stderr)
        sys.exit(1)
