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
"""

import sys
import os
import json
import re
import yaml
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT  = Path(__file__).parent.parent / "docs"
STATE_FILE = Path(__file__).parent / "state.yaml"
MAX_COMPLETED = 15


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


def cmd_force_complete(task_id):
    """
    Fallback PS1: forza un task come completed o skipped se l'agente
    ha terminato senza aggiornare state.yaml.
    """
    state = load_state()
    for item in state.get("queue", []):
        if item.get("id") == task_id and item.get("status") in ("pending", "in_progress"):
            file_path = item.get("path", "")
            file_exists = bool(file_path) and (Path(__file__).parent.parent / file_path).exists()

            if file_exists:
                item["status"] = "completed"
                note = "File presente su disco - completato ma state non aggiornato dall'agente"
            else:
                item["status"] = "skipped"
                note = "File non creato - task saltato o fallito, forzato come skipped"

            # Pulisci interrupted_task
            it = state.get("interrupted_task") or {}
            if it.get("id") == task_id:
                state["interrupted_task"] = None

            # Aggiorna contatori
            state["total_ops"] = state.get("total_ops", 0) + 1

            # Aggiungi a completed
            state.setdefault("completed", []).append({
                "id": task_id,
                "path": file_path,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": note
            })

            save_state(state)
            print(f"force-complete: {task_id} -> {item['status']} | {note}")
            return

    # Task gia' completato o non trovato — assicurati che interrupted_task sia pulito
    it = state.get("interrupted_task") or {}
    if it.get("id") == task_id:
        state["interrupted_task"] = None
        save_state(state)
    print(f"force-complete: {task_id} gia' gestito o non trovato — nessuna azione")


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
        claude_md_size  = (project_root / "CLAUDE.md").stat().st_size
        state_yaml_size = (project_root / "_automation" / "state.yaml").stat().st_size
        task_json_size  = (project_root / "_automation" / "current-task.json").stat().st_size
        prompt_md_size  = (project_root / "_automation" / "run-prompt.md").stat().st_size
        read_overhead   = claude_md_size + state_yaml_size + task_json_size + prompt_md_size + 2000
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
    else:
        print(f"Comando sconosciuto: {cmd}", file=sys.stderr)
        sys.exit(1)
