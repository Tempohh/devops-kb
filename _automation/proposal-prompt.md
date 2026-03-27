# Istruzioni: Sessione di Analisi e Generazione Proposte

Stai eseguendo un'**analisi trasversale** della Knowledge Base per identificare opportunità di miglioramento significative. Le proposte che generi verranno presentate all'utente per approvazione — nessun file di contenuto viene modificato in questa sessione.

## Processo

### Fase 1 — Campionamento KB

Leggi **10-15 file** dalla KB, scegliendo in modo bilanciato tra le categorie disponibili. Priorità:
1. File con `status: draft` o `status: needs-review` nel frontmatter
2. File con `related` vuoto o `search_keywords` con meno di 8 entry
3. File più vecchi (data `last_updated` più lontana)

Usa Glob per scoprire i file disponibili:
- `docs/cloud/**/*.md`
- `docs/containers/**/*.md`
- `docs/networking/**/*.md`
- `docs/monitoring/**/*.md`
- `docs/security/**/*.md`
- `docs/ci-cd/**/*.md`

### Fase 2 — Analisi qualità per ogni file letto

Valuta:
1. **Completezza**: tutte le sezioni H2 del template sono popolate con contenuto reale?
2. **Profondità tecnica**: code block con esempi reali, troubleshooting sufficienti?
3. **Relazioni**: il campo `related` è ricco? ci sono argomenti collegati non referenziati?
4. **Lacune trasversali**: argomenti menzionati ma non coperti nella KB?

### Fase 3 — Generazione proposte

Per ogni opportunità di impatto **significativo** identificata (non cosmetic), crea un file YAML in `_automation/proposals/pending/`.

**Formato obbligatorio:**

```yaml
id: prop-NNN
title: "Titolo breve e descrittivo (max 80 caratteri)"
path: docs/categoria/file.md
type: expand      # expand | audit | new_topic
priority: P2      # P1=critico | P2=utile | P3=nice-to-have
description: |
  Descrizione dettagliata dell'intervento proposto.
  Cosa aggiungere, perché è utile, chi ne beneficia.
  Includere: sezioni da espandere, numero di scenari troubleshooting mancanti,
  esempi pratici che mancano.
status: pending_approval
created: YYYY-MM-DD
```

**Naming file:** `prop-NNN-slug-descrittivo.yaml`
Esempio: `prop-001-expand-docker-troubleshooting.yaml`

**Limiti e regole:**
- Massimo **8 proposte** per sessione
- Solo proposte con impatto concreto (almeno +50 righe o +3 scenari troubleshooting o nuovo argomento rilevante)
- `P1` solo per file criticamente incompleti (< 80 righe, sezioni vuote)
- `new_topic` solo per argomenti chiaramente assenti dalla KB e di alto valore

**Prima di creare la directory**, verifica che esista con Glob su `_automation/proposals/`. Se non esiste, creala implicitamente scrivendo il primo file (il Write tool la crea automaticamente).

### Fase 4 — NON aggiornare state.yaml

**Non leggere né modificare `_automation/state.yaml`.**
Il sistema PS1 aggiorna lo stato automaticamente dopo la tua risposta.

## Output finale (obbligatorio)

```
PROPOSAL SESSION
File analizzati: [numero]
Proposte generate: [numero]
Elenco:
  - [prop-NNN] [path] — [titolo]
  - ...
Pattern di qualità identificati: [osservazioni trasversali sulla KB]
```
