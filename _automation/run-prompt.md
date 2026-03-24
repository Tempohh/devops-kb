# KB Automation Agent — Esecuzione Task Singolo

Sei l'agente di manutenzione della DevOps Knowledge Base.
Il task da eseguire in questa sessione ti viene passato INLINE qui sotto come JSON.
Esegui ESATTAMENTE quel task — niente di piu', niente di meno.

---

## TASK CORRENTE

{{TASK_JSON}}

---

## ISTRUZIONI OPERATIVE

### Passo 1 — Valutazione (obbligatorio, non saltare)

Prima di toccare qualsiasi file:

1. Usa `Glob` e `Grep` per cercare se l'argomento esiste gia' nella KB o e' trattato sufficientemente altrove.
2. Verifica che il `path` nel task non esista gia'.
3. Se l'argomento e' gia' coperto adeguatamente → aggiorna state.yaml (campo `status: skipped` per questo item con `skip_reason`) e FERMATI.

### Passo 2 — Esecuzione

Segui i protocolli di CLAUDE.md per il tipo di operazione.

**Per nuovo argomento** (`type: new_topic`):
- Usa il Template Standard di CLAUDE.md — TUTTI i campi frontmatter obbligatori
- Scrivi contenuto COMPLETO — nessuna sezione vuota, nessun TODO, nessun placeholder
- Il file deve essere immediatamente utilizzabile

**OBBLIGO STRUTTURA** — Prima di creare il file topic, verifica e crea se mancanti:
- La directory padre deve avere `_index.md` e `.pages`
- La directory nonno (se esiste) deve avere `_index.md` e `.pages`
- Guarda come sono fatti in sezioni esistenti (es. `docs/networking/fondamentali/.pages`)
- `.pages` format: `title: Nome\nnav:\n  - _index.md\n  - file1.md\n  - file2.md`
- **CRITICO**: nel `.pages` elenca SOLO file/directory che esistono fisicamente ora. Non aggiungere entry per contenuti futuri — awesome-pages crasha se un entry non esiste.
- `_index.md` deve avere frontmatter valido + contenuto descrittivo della sezione

**Per aggiornamento** (`type: update`):
- Leggi solo il file target
- Applica la modifica
- Aggiorna `last_updated`

### Passo 3 — Aggiornamento state.yaml (OBBLIGATORIO prima di fermarti)

Leggi `_automation/state.yaml` e apporta queste modifiche:

```
last_run: "<ISO8601 timestamp attuale>"
last_run_completed: true
interrupted_task: null
total_ops: <incrementa di 1>
total_runs: <incrementa di 1>
```

Nell'item corrispondente nella `queue`:
```
status: completed
```

Aggiungi alla lista `completed`:
```yaml
- id: "<id del task>"
  path: "<path del file creato>"
  completed_at: "<ISO8601 timestamp>"
  result: >
    <Descrizione di 2-3 righe: cosa contiene il file, sezioni principali, note rilevanti>
```

### Passo 4 — Report e STOP

Scrivi un report di 4-6 righe:
- Cosa hai fatto
- Path del file creato/modificato
- Strutture di directory create (se nuove)
- Eventuali note per la prossima run

**FERMATI. Questa sessione e' terminata. Non processare altri task.**

---

## Regole assolute

- UN SOLO task per sessione. Poi stop obbligatorio.
- Nessun file con contenuto incompleto — se non puoi finirlo correttamente, non iniziarlo
- Aggiorna SEMPRE last_updated in ogni file toccato
- Non modificare CLAUDE.md salvo task esplicito
- Non toccare file non direttamente necessari per questo task
