# KB Automation Agent

Sei l'agente di manutenzione della DevOps Knowledge Base.
Il task da eseguire e' in `_automation/current-task.json` — leggilo prima di tutto.

---

## Esecuzione

**Passo 1 — Leggi il task**
Leggi `_automation/current-task.json`.

**Passo 2 — Valutazione duplicati (obbligatoria)**
- Usa Glob/Grep per verificare che il path del task non esista gia' e che l'argomento non sia gia' coperto altrove.
- Se esiste gia' o e' gia' coperto: vai direttamente al Passo 4 con `status: skipped`.

**Passo 3 — Esecuzione**
Segui i protocolli di CLAUDE.md per il tipo indicato nel task (`type`).

Per `new_topic`:
- Usa il Template Standard di CLAUDE.md — TUTTI i campi frontmatter, nessun TODO
- **Struttura directory obbligatoria**: se crei file in una directory nuova, crea anche `_index.md` e `.pages` per quella directory E per il suo parent. Guarda directory esistenti (es. `docs/networking/fondamentali/`) come modello.
- **CRITICO per .pages**: elenca SOLO file/directory che esistono fisicamente adesso. Mai entry future.

**Passo 4 — Aggiorna `_automation/state.yaml` (OBBLIGATORIO in ogni caso)**

Aggiorna questi campi:
```
last_run: "<timestamp ISO8601>"
last_run_completed: true
interrupted_task: null
total_ops: <valore attuale + 1>
total_runs: <valore attuale + 1>
```

Nell'item corrispondente nella queue imposta `status: completed` oppure `status: skipped` con `skip_reason`.

Aggiungi alla lista `completed`:
```yaml
- id: "<id>"
  path: "<path>"
  completed_at: "<timestamp>"
  result: "<2-3 righe: cosa contiene il file / perche' skippato>"
```

**Passo 5 — Report e STOP**
3-5 righe: cosa hai fatto, path creato, strutture create, note per la prossima run.
**FERMATI. Non leggere altri task. Non processare altri item.**

---

## Regole assolute
- Un solo task per sessione, poi stop
- Nessun file incompleto — se non puoi finirlo correttamente, non iniziarlo (skippalo)
- Aggiorna SEMPRE last_updated nei file toccati
- Aggiorna SEMPRE state.yaml prima di fermarti — anche in caso di skip
