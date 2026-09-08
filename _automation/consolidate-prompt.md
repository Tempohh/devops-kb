# Istruzioni: Consolidamento / Sfoltimento

Unisci contenuto ridondante o ritira contenuto di basso valore, mantenendo la KB
navigabile e senza link rotti. Operazione a rischio: procedi con cautela.

## Task corrente

Leggi `_automation/current-task.json`. Il `reason` indica lo scenario:
- **merge**: `path` è il file di destinazione; il `reason` elenca i file sorgente da assorbire.
- **retire**: `path` è il file da ritirare; il `reason` spiega perché e dove reindirizzare.

## Processo

### Fase 1 — Mappa i riferimenti (obbligatoria)
Con Grep trova **ogni** link entrante ai file coinvolti:
```
grep -rn "nome-file-senza-estensione" docs/
```
Controlla anche i campi `related:` nei frontmatter e le voci nei file `.pages`.

### Fase 2a — Scenario MERGE
1. Leggi destinazione + sorgenti.
2. Integra nella destinazione SOLO le parti non già presenti; nessuna duplicazione.
3. Unisci `search_keywords` e `related` (dedup).
4. Per ogni file sorgente: cancellalo, poi aggiorna ogni link entrante per puntare alla destinazione (sezione con anchor se serve), rimuovi la voce dal `.pages` della cartella, togli il path dai `related:` altrui.
5. `status: needs-review`, `last_updated: <oggi>` sulla destinazione.

### Fase 2b — Scenario RETIRE
1. Verifica che il contenuto sia davvero coperto altrove (cita dove).
2. Cancella il file, la sua voce `.pages`, i riferimenti in `related:`.
3. Redirigi i link entranti al file indicato nel `reason`.
4. Se nulla lo copre: NON cancellare — riporta `BLOCKED` e spiega.

### Fase 3 — Verifica no-broken-link
Mentalmente (o con `mkdocs build --strict` se veloce): nessun link deve puntare a un file eliminato.

### Fase 4 — NON toccare `_automation/state.yaml`.

## Output finale (max 12 righe)

```
CONSOLIDATE ([merge|retire]): [path]
File assorbiti/ritirati: [lista]
Link entranti aggiornati: [N in M file]
.pages aggiornati: [lista]
related: aggiornati: [N file]
Esito: [OK | BLOCKED: motivo]
```
