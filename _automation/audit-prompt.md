# Istruzioni: Sessione di Audit Qualità

Stai eseguendo un **audit mirato** su un file esistente della Knowledge Base.

> **Budget token**: questa sessione deve essere efficiente. Leggi il file, identifica le lacune, aggiungi SOLO quello che manca. Non riscrivere, non espandere oltre il necessario.

## Task corrente

Leggi `_automation/current-task.json` per `path` e `reason`.
Il campo `reason` può indicare issue già identificati (es. `no_troubleshooting_section`).

## Processo

### Fase 1 — Lettura rapida
Leggi il file indicato in `path`. Nota mentalmente:
- Quante righe ha (approssimativamente)
- Quali sezioni H2 sono popolate vs vuote/incomplete
- Se c'è `## Troubleshooting` e quanti scenari ha

### Fase 2 — Intervento mirato

Controlla questi criteri nell'ordine indicato. **Appena trovi un'issue, correggila e vai avanti.**

| Priorità | Criterio | Soglia | Azione |
|---|---|---|---|
| 1 | `## Troubleshooting` | Esiste? | Se mancante: aggiungi sezione con 4 scenari |
| 2 | Scenari troubleshooting | >= 3 con sintomo/causa/soluzione/comandi | Se pochi: aggiungi scenari mancanti |
| 3 | Code blocks | >= 2 nelle sezioni pratiche | Se pochi: aggiungi esempi concreti |
| 4 | `search_keywords` | >= 10 entry | Se pochi: aggiungi sinonimi IT/EN, acronimi |
| 5 | `related` | >= 2 percorsi reali | Se pochi: aggiungi path verificati |
| 6 | Sezioni H2 vuote | Tutte popolate | Se vuote: aggiungi contenuto minimo |

**Regole:**
- Aggiorna `last_updated` a oggi e `status: complete` nel frontmatter
- NON riscrivere parti già buone
- NON aggiungere contenuto decorativo o ridondante
- Per la sezione Troubleshooting: usa il formato `### Scenario N — [titolo]` con sottosezioni `**Sintomo**`, `**Causa**`, `**Soluzione**` e un code block con comandi reali

### Fase 3 — NON aggiornare state.yaml

**Non leggere né modificare `_automation/state.yaml`.**
Il sistema di automazione (PS1) aggiorna lo stato automaticamente dopo la tua risposta.
Concentrati solo sul file di contenuto indicato in `path`.

## Output finale (breve — max 10 righe)

```
AUDIT: [path]
Issue trovati: [lista o "nessuno"]
Modifiche: [cosa hai aggiunto/corretto]
Righe aggiunte: ~[N]
```
