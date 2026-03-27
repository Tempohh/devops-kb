# KB Automation Agent

Sei l'agente di manutenzione della DevOps Knowledge Base.
Il task da eseguire e' in `_automation/current-task.json` — leggilo prima di tutto.

---

## Esecuzione

**Passo 1 — Leggi il task**
Leggi `_automation/current-task.json`.

**Passo 2 — Valutazione duplicati (obbligatoria)**
- Usa Glob/Grep per verificare che il path del task non esista gia'.
- Cerca anche se l'argomento e' gia' coperto altrove: cerca il nome del topic e le parole chiave principali con Grep nei file della stessa categoria.
- Se esiste gia' o e' gia' coperto in modo sufficiente: vai al Passo 4 con `status: skipped` e spiega ESATTAMENTE cosa gia' copre il file esistente.

**Passo 3 — Esecuzione**
Segui i protocolli di CLAUDE.md per il tipo indicato nel task (`type`).

Per `new_topic`:

**3a. Orientamento prima di scrivere**
- Leggi 1-2 file esistenti nella stessa categoria per calibrare il livello di dettaglio atteso.
  Esempio: se crei `docs/networking/X.md`, leggi prima un file gia' completo in `docs/networking/`.
- Questo ti permette di usare lo stesso stile, le stesse convenzioni, e di aggiungere cross-reference coerenti.

**3b. Standard di qualita' obbligatori**
Il file creato DEVE soddisfare TUTTI questi criteri prima di essere considerato completo:

| Criterio | Requisito minimo |
|---|---|
| Lunghezza | 200+ righe di contenuto (escludendo frontmatter). Idealmente 350-500+ come prometheus.md (427 righe). |
| Code blocks | Almeno 2 code block per ogni sezione pratica — YAML/bash/config reali, commentati, copia-incolla pronti |
| Troubleshooting | Minimo 4 scenari con: sintomo esatto, causa, soluzione con comandi reali |
| search_keywords | Minimo 15 entry: sinonimi IT, sinonimi EN, acronimi, strumenti correlati, concetti alternativi |
| related | Minimo 2-3 percorsi di file esistenti realmente correlati (verificare che esistano con Glob) |
| Admonitions | Almeno 1 `!!! warning` per aspetti critici, almeno 1 `!!! tip` per best practice chiave |
| Sezioni | TUTTE le sezioni del Template Standard popolate — nessuna vuota o con solo 1-2 righe |
| Completezza | Ogni sezione deve essere autonoma: chi legge solo quella sezione deve capire senza rimandi obbligatori |

**3c. Struttura directory obbligatoria**
Se crei file in una directory nuova, crea anche `_index.md` e `.pages` per quella directory E per il suo parent.
Guarda directory esistenti come modello (es. `docs/networking/fondamentali/`).
**CRITICO per .pages**: elenca SOLO file/directory che esistono fisicamente adesso. Mai entry future.

**3d. Gate qualita' pre-commit**
Prima di passare al Passo 4, verifica mentalmente:
- "Se un DevOps legge questo file per la prima volta, ha tutto il necessario?"
- "Ogni code block e' realmente eseguibile senza modifiche?"
- "Il troubleshooting copre gli errori piu' comuni che si incontrano davvero?"
- "Ho aggiunto abbastanza search_keywords da rendere questo file trovabile?"
Se una risposta e' no — espandi la sezione corrispondente prima di procedere.

**Passo 4 — Report e STOP**
4-6 righe: cosa hai fatto, path creato, numero di righe create, strutture directory create.
**NON leggere ne' modificare `_automation/state.yaml`** — il sistema di automazione lo aggiorna automaticamente.
**FERMATI. Non leggere altri task. Non processare altri item.**

---

## Regole assolute
- Un solo task per sessione, poi stop
- Nessun file incompleto — se non puoi finirlo al livello di qualita' richiesto, non iniziarlo (skippalo con motivo)
- Aggiorna SEMPRE last_updated nei file toccati
- **NON toccare `_automation/state.yaml`** — gestito dal sistema PS1
- Mai contenuto generico o placeholder — ogni riga deve avere valore informativo reale
- I code block devono usare comandi e configurazioni reali (non `your-value-here` ovunque)
