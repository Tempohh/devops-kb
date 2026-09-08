# Istruzioni: Ricontrollo di Attualità (Currency Check)

Verifichi che un file resti allineato allo stato reale delle tecnologie che descrive.
Focus stretto: **fatti che invecchiano** — versioni, pricing, model ID, nomi di
prodotto, flag CLI, stato GA/beta, tool deprecati.

## Task corrente

Leggi `_automation/current-task.json` per `path`. Il file ha (o dovrebbe avere)
`official_docs` nel frontmatter: è la fonte di verità.

## Processo

### Fase 1 — Estrai le affermazioni datate
Rileggi il file e segna ogni punto che dipende dal tempo:
- numeri di versione presentati come "corrente/ultimo"
- prezzi, limiti, quote
- identificatori di modello / SKU / nomi commerciali
- "in beta" / "in preview" / "deprecato" / "GA da"
- comandi e flag che potrebbero essere cambiati

### Fase 2 — Verifica
Per ciascun punto, confronta con `official_docs` (usa WebFetch se disponibile) o
con la documentazione ufficiale del progetto. NON indovinare: se non puoi
verificare, marca `<!-- CURRENCY: non verificato (2026-xx) -->` e prosegui.

### Fase 3 — Correzione mirata
- Aggiorna SOLO i fatti datati. Non riscrivere prosa corretta.
- Se una sezione è concettualmente ancora valida ma cita esempi vecchi, aggiorna gli esempi.
- Se emerge una novità stabile e rilevante che manca del tutto, aggiungi un paragrafo breve — non un capitolo.

### Fase 4 — Frontmatter
- `last_verified: <oggi>` sempre.
- `last_updated: <oggi>` solo se hai cambiato contenuto sostanziale.
- `status: reviewed` se ora è pulito; `needs-review` se restano `<!-- CURRENCY: -->` aperti.

### Fase 5 — NON toccare `_automation/state.yaml`.

## Output finale (max 8 righe)

```
CURRENCY: [path]
Datati trovati: [N]
Aggiornati: [lista breve]
Non verificati: [lista o "nessuno"]
status -> [reviewed | needs-review]
```
