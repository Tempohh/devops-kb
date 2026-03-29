"""
review-proposals.py — Interfaccia interattiva per approvare/rifiutare proposte KB.

Uso:
    python _automation/review-proposals.py          # review interattiva (una per una)
    python _automation/review-proposals.py --list   # solo lista proposte pending
    python _automation/review-proposals.py --add    # aggiungi proposta manuale

La review avviene a ciclo: mostra proposta → chiedi [a]pprova / [r]ifiuta / [s]kip / [q]uit.
Le proposte approvate entrano direttamente nella coda dell'automazione.
Le proposte rifiutate vengono spostate in proposals/rejected/ con nota opzionale.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path
import yaml
from datetime import datetime, timezone

AUTOMATION_DIR = Path(__file__).parent
PENDING_DIR    = AUTOMATION_DIR / "proposals" / "pending"
APPROVED_DIR   = AUTOMATION_DIR / "proposals" / "approved"
REJECTED_DIR   = AUTOMATION_DIR / "proposals" / "rejected"
STATE_PY       = AUTOMATION_DIR / "manage-state.py"

APPROVED_DIR.mkdir(parents=True, exist_ok=True)
REJECTED_DIR.mkdir(parents=True, exist_ok=True)

# ── ANSI colors ────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def color(text: str, c: str) -> str:
    return f"{c}{text}{RESET}"

def hr(char="─", width=72):
    print(color(char * width, DIM))

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_proposals() -> list[tuple[Path, dict]]:
    """Carica tutte le proposte in proposals/pending/ ordinate per priorità."""
    priority_order = {"high": 0, "medium": 1, "low": 2}
    proposals = []
    for f in sorted(PENDING_DIR.glob("*.yaml")):
        with open(f, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        proposals.append((f, data))
    proposals.sort(key=lambda x: priority_order.get(x[1].get("priority", "low"), 99))
    return proposals

def print_proposal(path: Path, data: dict, index: int, total: int):
    """Stampa una proposta in modo leggibile."""
    print()
    hr("═")
    pid     = data.get("id", path.stem)
    title   = data.get("title", "(senza titolo)")
    ptype   = data.get("type", "?")
    prio    = data.get("priority", "?")
    effort  = data.get("effort", "?")
    target  = data.get("target_file", data.get("target_files", "?"))
    tags    = ", ".join(data.get("tags", []))

    prio_color = GREEN if prio == "high" else (YELLOW if prio == "medium" else DIM)

    print(f"  {color(f'[{index}/{total}]', DIM)}  {color(pid.upper(), BOLD)}  —  {color(title, BOLD)}")
    print()
    print(f"  {color('Tipo:', DIM)}     {ptype:<18}  {color('Priorità:', DIM)} {color(prio, prio_color):<10}  {color('Sforzo:', DIM)} {effort}")
    print(f"  {color('Target:', DIM)}   {str(target)}")
    if tags:
        print(f"  {color('Tag:', DIM)}      {color(tags, DIM)}")
    print()

    desc = data.get("description", "").strip()
    if desc:
        print(color("  Descrizione:", CYAN))
        for line in textwrap.wrap(desc, width=70, initial_indent="    ", subsequent_indent="    "):
            print(line)
        print()

    rationale = data.get("rationale", "").strip()
    if rationale:
        print(color("  Motivazione:", CYAN))
        for line in textwrap.wrap(rationale, width=70, initial_indent="    ", subsequent_indent="    "):
            print(line)
        print()

    action = data.get("action_required_before_execute", "").strip()
    if action:
        print(f"  {color('⚠  Azione richiesta:', YELLOW)}")
        for line in textwrap.wrap(action, width=68, initial_indent="    ", subsequent_indent="    "):
            print(line)
        print()

    hr("─")

def manage_state(cmd: str, *args) -> dict | None:
    """Chiama manage-state.py e ritorna l'output JSON (se presente)."""
    result = subprocess.run(
        [sys.executable, str(STATE_PY), cmd, *args],
        capture_output=True, text=True
    )
    out = result.stdout.strip()
    if out:
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            pass
    return None

def approve(path: Path, data: dict):
    pid = data.get("id", path.stem)
    result = manage_state("approve-proposal", pid)
    if result and result.get("status") == "ok":
        task_id = result.get("task_id", "?")
        print(color(f"  ✓ Approvata → task {task_id} aggiunto alla coda", GREEN))
    else:
        print(color(f"  ✗ Errore nell'approvazione. Esegui manualmente:", RED))
        print(f"    python _automation/manage-state.py approve-proposal {pid}")

def reject(path: Path, data: dict, note: str = ""):
    pid = data.get("id", path.stem)
    result = manage_state("reject-proposal", pid)
    if result and result.get("status") == "ok":
        print(color(f"  ✗ Rifiutata → spostata in proposals/rejected/", RED))
        if note:
            # Aggiungi nota al file rifiutato
            rejected_path = REJECTED_DIR / path.name
            if rejected_path.exists():
                with open(rejected_path, encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                content["rejection_note"] = note
                content["rejected_at"] = datetime.now(timezone.utc).isoformat()
                with open(rejected_path, "w", encoding="utf-8") as f:
                    yaml.dump(content, f, allow_unicode=True, default_flow_style=False)
    else:
        print(color(f"  ✗ Errore. Esegui manualmente:", RED))
        print(f"    python _automation/manage-state.py reject-proposal {pid}")

# ── Modalità --list ────────────────────────────────────────────────────────────

def cmd_list():
    proposals = load_proposals()
    if not proposals:
        print(color("\n  Nessuna proposta in attesa.\n", GREEN))
        return

    print(f"\n  {color(f'{len(proposals)} proposte in attesa di revisione:', BOLD)}\n")
    prio_color = {"high": GREEN, "medium": YELLOW, "low": DIM}
    for path, data in proposals:
        pid    = data.get("id", path.stem)
        title  = data.get("title", "")
        ptype  = data.get("type", "")
        prio   = data.get("priority", "")
        effort = data.get("effort", "")
        pc     = prio_color.get(prio, RESET)
        print(f"  {color(pid, BOLD):<14} {color(prio, pc):<8} {ptype:<18} {effort:<8}  {title}")
    print()

# ── Modalità --add ─────────────────────────────────────────────────────────────

def cmd_add():
    """Crea una nuova proposta manuale."""
    print(color("\n  Nuova proposta manuale\n", BOLD))
    pid     = input("  ID (es. prop-010): ").strip() or f"prop-manual-{datetime.now().strftime('%Y%m%d%H%M')}"
    title   = input("  Titolo: ").strip()
    ptype   = input("  Tipo [new-file / extend-section / fix-relation / consolidate]: ").strip() or "new-file"
    target  = input("  File target (path relativo da docs/): ").strip()
    prio    = input("  Priorità [high / medium / low] (default: medium): ").strip() or "medium"
    effort  = input("  Sforzo [small / medium / large] (default: medium): ").strip() or "medium"
    desc    = input("  Descrizione (una riga): ").strip()
    rat     = input("  Motivazione (una riga): ").strip()
    tags    = [t.strip() for t in input("  Tag (separati da virgola): ").split(",") if t.strip()]

    proposal = {
        "id": pid,
        "title": title,
        "type": ptype,
        "priority": prio,
        "target_file": f"docs/{target}",
        "description": desc,
        "rationale": rat,
        "effort": effort,
        "tags": tags,
        "last_analyzed": datetime.now(timezone.utc).date().isoformat(),
    }

    out_path = PENDING_DIR / f"{pid}.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(proposal, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(color(f"\n  ✓ Proposta salvata in {out_path}\n", GREEN))

# ── Modalità interattiva (default) ────────────────────────────────────────────

def cmd_review():
    proposals = load_proposals()
    if not proposals:
        print(color("\n  Nessuna proposta in attesa. KB è aggiornata!\n", GREEN))
        return

    print(f"\n  {color(f'{len(proposals)} proposte in attesa.', BOLD)}")
    print(f"  {color('Comandi:', DIM)} [a]pprova  [r]ifiuta  [s]kip  [q]uit\n")

    approved_count = 0
    rejected_count = 0
    skipped_count  = 0

    for i, (path, data) in enumerate(proposals, 1):
        print_proposal(path, data, i, len(proposals))

        while True:
            try:
                choice = input(f"  Decisione [{color('a', GREEN)}/{color('r', RED)}/{color('s', YELLOW)}/{color('q', DIM)}]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Interrotto.")
                break

            if choice in ("a", "approva", "approve", "y", "si", "sì"):
                approve(path, data)
                approved_count += 1
                break
            elif choice in ("r", "rifiuta", "reject", "n", "no"):
                note = input("  Nota rifiuto (opzionale, INVIO per saltare): ").strip()
                reject(path, data, note)
                rejected_count += 1
                break
            elif choice in ("s", "skip", ""):
                print(color("  → Saltata (rimane in pending)", YELLOW))
                skipped_count += 1
                break
            elif choice in ("q", "quit", "exit"):
                print("\n  Review interrotta.")
                print(f"  Approvate: {approved_count}  Rifiutate: {rejected_count}  Saltate: {skipped_count}")
                return
            else:
                print("  Digita a, r, s o q.")

    print()
    hr("═")
    print(f"\n  Review completata.")
    print(f"  {color(f'✓ Approvate: {approved_count}', GREEN)}   {color(f'✗ Rifiutate: {rejected_count}', RED)}   {color(f'→ Saltate: {skipped_count}', YELLOW)}")

    # Mostra il report di saturazione se esiste
    sat_report = AUTOMATION_DIR / "proposals" / "kb-saturation-report.md"
    if sat_report.exists():
        print()
        print(color("  ── Report di saturazione KB ─────────────────────────────────────────", DIM))
        with open(sat_report, encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[:30]:
            print("  " + line.rstrip())
        if len(lines) > 30:
            print(color(f"  ... [{len(lines)-30} righe aggiuntive in {sat_report}]", DIM))
        hr("─")

    # Dialogo con l'utente: sue proposte
    _user_proposals_dialog()

    if approved_count > 0:
        print(f"\n  I task approvati sono ora in coda — avvia kb-infinite.ps1 per elaborarli.")
    print()


def _user_proposals_dialog():
    """Chiede all'utente se ha proposte proprie. Loop infinito fino a 'fine'."""
    print()
    print(color("  ── Le tue proposte ──────────────────────────────────────────────────", CYAN))
    print(f"  Hai idee per la KB che vuoi aggiungere?")
    print(f"  {color('Descrivi liberamente', BOLD)} cosa vorresti (una o più righe).")
    print(f"  Scrivi {color('fine', BOLD)} su una riga per terminare, {color('salta', DIM)} per saltare.\n")

    user_props = []
    while True:
        try:
            line1 = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if line1.lower() in ("fine", "done", "exit", "q", "quit", ""):
            break
        if line1.lower() in ("salta", "skip", "no", "n"):
            break

        # Raccoglie più righe fino a riga vuota
        lines = [line1]
        print(f"  {color('(continua o INVIO per terminare questa proposta)', DIM)}")
        while True:
            try:
                more = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if more == "":
                break
            if more.lower() in ("fine", "done"):
                lines.append("")  # segnaposto per uscire dal loop esterno
                break
            lines.append(more)

        idea_text = " ".join(l for l in lines if l)
        if not idea_text:
            continue

        # Crea proposta manuale con i dati minimi
        next_id = _next_proposal_id()
        priority = _ask_priority()
        effort   = _ask_effort()

        proposal = {
            "id": next_id,
            "title": idea_text[:80],
            "type": "new-file",
            "priority": priority,
            "target_file": "",   # da completare in fase di esecuzione
            "effort": effort,
            "description": idea_text,
            "rationale": "Proposta dell'utente.",
            "utility_test": {"reader": "specificato dall'utente", "scenario": idea_text, "outcome": "", "score": "high"},
            "tags": ["user-proposal"],
            "last_analyzed": datetime.now(timezone.utc).date().isoformat(),
            "source": "user",
        }

        out_path = PENDING_DIR / f"{next_id}.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(proposal, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        user_props.append(next_id)
        print(color(f"\n  ✓ Proposta '{next_id}' salvata.", GREEN))

        # Chiedi se approvare subito o lasciare in pending
        try:
            approve_now = input("  Approvare subito (entra in coda) o lasciare in pending? [a/p]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            approve_now = "p"

        if approve_now in ("a", "approva", "approve", "y", "si", "sì"):
            approve(out_path, proposal)
        else:
            print(color("  → Lasciata in pending (usa review-proposals.py per approvarla)", YELLOW))

        print()
        try:
            another = input("  Altra proposta? [s/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if another not in ("s", "si", "sì", "y", "yes"):
            break

    if user_props:
        print(color(f"\n  {len(user_props)} tue proposte registrate: {', '.join(user_props)}", GREEN))
    else:
        print(color("\n  Nessuna proposta aggiuntiva. Continua!", DIM))


def _next_proposal_id() -> str:
    existing = sorted(PENDING_DIR.glob("prop-*.yaml")) + \
               sorted((AUTOMATION_DIR / "proposals" / "approved").glob("prop-*.yaml")) + \
               sorted((AUTOMATION_DIR / "proposals" / "rejected").glob("prop-*.yaml"))
    used = set()
    for f in existing:
        m = __import__("re").match(r"prop-(\d+)", f.stem)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return f"prop-{n:03d}"


def _ask_priority() -> str:
    while True:
        try:
            p = input("  Priorità [h=high / m=medium / l=low] (default: medium): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "medium"
        if p in ("h", "high"):
            return "high"
        if p in ("l", "low"):
            return "low"
        return "medium"


def _ask_effort() -> str:
    while True:
        try:
            e = input("  Sforzo [s=small / m=medium / l=large] (default: medium): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "medium"
        if e in ("s", "small"):
            return "small"
        if e in ("l", "large"):
            return "large"
        return "medium"

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    os.system("color")  # abilita ANSI su Windows

    args = sys.argv[1:]
    if "--list" in args or "-l" in args:
        cmd_list()
    elif "--add" in args or "-a" in args:
        cmd_add()
    else:
        cmd_review()
