"""
Gestione dello state.yaml per il sistema di automazione KB.
Usato dagli script PowerShell per:
- Estrarre il prossimo task da eseguire (next-task)
- Potare la lista completed (prune)
- Validare la struttura MkDocs delle directory create (validate)
"""

import sys
import os
import json
import yaml
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).parent.parent / "docs"
STATE_FILE = Path(__file__).parent / "state.yaml"
MAX_COMPLETED = 15  # Mantieni solo gli ultimi N completed


def load_state():
    with open(STATE_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        # Mantieni i commenti di intestazione
        f.write("# Stato del sistema di automazione KB\n")
        f.write("# Aggiornato automaticamente - non modificare 'completed' manualmente\n\n")
        yaml.dump(
            state,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )


def cmd_next_task():
    """Stampa il prossimo task pending come JSON. Stampa 'null' se la coda e' vuota."""
    state = load_state()

    # Se c'e' un interrupted_task, ha priorita' assoluta
    if state.get("interrupted_task"):
        it = state["interrupted_task"]
        # Cerca l'item corrispondente nella queue
        for item in state.get("queue", []):
            if item.get("id") == it.get("id"):
                print(json.dumps(item, ensure_ascii=False))
                return
        # Se non trovato nella queue (gia' completato), pulisci
        state["interrupted_task"] = None
        save_state(state)

    # Prendi il primo pending ordinato per priorita'
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    pending = [
        item for item in state.get("queue", [])
        if item.get("status") == "pending"
    ]
    if not pending:
        print("null")
        return

    pending.sort(key=lambda x: priority_order.get(x.get("priority", "P3"), 3))
    print(json.dumps(pending[0], ensure_ascii=False))


def cmd_mark_started(task_id):
    """Imposta interrupted_task nello state (checkpoint prima di iniziare)."""
    state = load_state()
    for item in state.get("queue", []):
        if item.get("id") == task_id:
            state["interrupted_task"] = {"id": task_id, "path": item.get("path"), "step": "started"}
            save_state(state)
            print(f"Checkpoint impostato per task {task_id}")
            return
    print(f"Task {task_id} non trovato", file=sys.stderr)
    sys.exit(1)


def cmd_prune():
    """Mantieni solo gli ultimi MAX_COMPLETED nella lista completed."""
    state = load_state()
    completed = state.get("completed", [])
    if len(completed) > MAX_COMPLETED:
        removed = len(completed) - MAX_COMPLETED
        state["completed"] = completed[-MAX_COMPLETED:]
        save_state(state)
        print(f"Pruned {removed} vecchi completed. Mantenuti: {MAX_COMPLETED}")
    else:
        print(f"Nessun pruning necessario ({len(completed)}/{MAX_COMPLETED})")


def check_pages_nav_entries(directory):
    """
    Verifica che ogni entry nel .pages nav esista fisicamente.
    Restituisce lista di entry mancanti (stringa 'dir/entry').
    """
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
        entry_path = DOCS_ROOT / directory / entry
        if not entry_path.exists():
            missing.append(f"{directory}/.pages nav entry '{entry}' non esiste")
    return missing


def cmd_validate(directory):
    """
    Verifica che una directory docs/ abbia _index.md e .pages.
    Stampa JSON con {ok: bool, missing: [...]}
    """
    target = DOCS_ROOT / directory
    if not target.exists():
        print(json.dumps({"ok": False, "missing": [f"{directory} non esiste"]}))
        return

    missing = []
    index = target / "_index.md"
    pages = target / ".pages"

    if not index.exists():
        missing.append(f"{directory}/_index.md")
    if not pages.exists():
        missing.append(f"{directory}/.pages")

    # Controlla anche il parent se non e' docs/ direttamente
    parts = Path(directory).parts
    if len(parts) > 1:
        parent = Path(*parts[:-1])
        parent_index = DOCS_ROOT / parent / "_index.md"
        parent_pages = DOCS_ROOT / parent / ".pages"
        if not parent_index.exists():
            missing.append(f"{parent}/_index.md")
        if not parent_pages.exists():
            missing.append(f"{parent}/.pages")

    print(json.dumps({"ok": len(missing) == 0, "missing": missing}, ensure_ascii=False))


def cmd_validate_all_new(paths_json):
    """
    Dato un JSON array di path docs-relative, verifica struttura di tutte.
    Usato post-run per validare ogni directory toccata.
    """
    paths = json.loads(paths_json)
    all_missing = []
    for p in paths:
        # Estrai la directory dal path file
        p_path = Path(p)
        if p_path.suffix:  # e' un file
            dirs_to_check = [p_path.parent]
            # Aggiungi anche il parent se e' una sottocartella
            if len(p_path.parts) > 2:
                dirs_to_check.append(p_path.parent.parent)
        else:
            dirs_to_check = [p_path]

        for d in dirs_to_check:
            d_str = str(d).replace("\\", "/")
            if d_str in ("docs", "."):
                continue
            # Rimuovi il prefisso "docs/" se presente
            d_rel = d_str.removeprefix("docs/")
            target = DOCS_ROOT / d_rel
            if not target.exists():
                continue
            index = target / "_index.md"
            pages = target / ".pages"
            if not index.exists():
                all_missing.append(f"{d_rel}/_index.md")
            if not pages.exists():
                all_missing.append(f"{d_rel}/.pages")
            else:
                # Verifica che le nav entries nel .pages esistano fisicamente
                all_missing.extend(check_pages_nav_entries(d_rel))

    if all_missing:
        print(json.dumps({"ok": False, "missing": list(set(all_missing))}, ensure_ascii=False))
    else:
        print(json.dumps({"ok": True, "missing": []}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: manage-state.py <command> [args]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "next-task":
        cmd_next_task()
    elif cmd == "mark-started" and len(sys.argv) >= 3:
        cmd_mark_started(sys.argv[2])
    elif cmd == "prune":
        cmd_prune()
    elif cmd == "validate" and len(sys.argv) >= 3:
        cmd_validate(sys.argv[2])
    elif cmd == "validate-all" and len(sys.argv) >= 3:
        cmd_validate_all_new(sys.argv[2])
    else:
        print(f"Comando sconosciuto: {cmd}", file=sys.stderr)
        sys.exit(1)
