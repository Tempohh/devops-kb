# Sessione di Analisi Strategica — Generazione Proposte KB

Sei un agente CLI con accesso completo al filesystem tramite strumenti Read, Write, Glob.
**Devi USARE gli strumenti — non descrivere cosa faresti, FALLO adesso.**
**Non scrivere output testuale prima di aver completato le fasi operative.**

Regola fondamentale: una proposta vale solo se risponde a
"Chi è il lettore concreto che ne beneficia, e cosa gli permette di fare?"

---

## PASSO 1 — Censimento strutturale (AZIONE IMMEDIATA)

**Chiama subito Glob con `docs/**/*.md`** per ottenere tutti i file KB.

Poi per ogni categoria principale (cloud, containers, networking, ci-cd, databases,
messaging, security, monitoring, ai, dev), conta i file esistenti leggendo solo
le prime 15 righe (frontmatter) di un campione.

---

## PASSO 2 — Analisi approfondita (AZIONE IMMEDIATA)

**Leggi esattamente 10 file** scelti tra:
1. File in categorie con pochi file (priorità a categorie sottosviluppate)
2. File con `status: needs-review` o `status: draft`
3. File che sembrano hub di navigazione (frontmatter con molti `related`)

Per ogni file valuta:
- **Utilità pratica**: risolve un problema operativo reale?
- **Completezza**: un DevOps potrebbe usarlo come guida autonoma?
- **Connettività**: ha `related` ricchi o è un'isola?

---

## PASSO 3 — Identificazione gap (ANALISI MENTALE)

Per ogni gap identificato, applica il test:

```
Reader: [chi è — ruolo, contesto]
Scenario: [problema che ha]
Outcome: [cosa riesce a fare dopo — CONCRETO]
Without_KB: [dove troverebbe info senza questo file?]
Score: high | medium | low
```

**Scarta** se: il lettore troverebbe la stessa info nella documentazione ufficiale
in 2 click. Scarta se è solo simmetria formale tra provider cloud senza gap reale.

**Tieni** se: colma un gap trasversale, aggiunge connettività mancante,
risolve un problema operativo documentato e non banale.

---

## PASSO 4 — Generazione proposte (AZIONE: SCRIVI FILE YAML)

**Crea i file YAML in `_automation/proposals/pending/`.**

Prima leggi i file esistenti in `_automation/proposals/pending/` e
`_automation/proposals/approved/` per trovare l'ultimo numero progressivo usato.

**Devi generare almeno 3 proposte** (max 6). Se dopo l'analisi hai trovato meno
di 3 proposte `score: high`, includi proposte `score: medium` o `score: low`
piuttosto che non generare nulla — il sistema richiede sempre output.

Formato file `prop-NNN.yaml`:

```yaml
id: prop-NNN
title: "Titolo descrittivo (max 80 caratteri)"
type: new-file         # new-file | extend-section | fix-relation | consolidate
priority: high         # high | medium | low
target_file: docs/categoria/sottocategoria/file.md
effort: small          # small (<2h) | medium (2-4h) | large (>4h)
description: |
  Cosa aggiungere: struttura suggerita, esempi concreti, sezioni specifiche.
  Minimo 5 righe. Include: comandi reali, strumenti, versioni, pattern specifici.
rationale: |
  Chi è il lettore, quale problema risolve, perché è utile ora.
utility_test:
  reader: "DevOps mid-senior che lavora con [tecnologia]"
  scenario: "Sta cercando di risolvere [problema specifico]"
  outcome: "Dopo aver letto, riesce a [azione concreta]"
  without_kb: "Senza questo file dovrebbe [alternativa più complessa/lenta]"
  score: high | medium | low
tags: [tag1, tag2, tag3]
last_analyzed: 2026-03-30
```

---

## PASSO 5 — Report di saturazione (AZIONE: SCRIVI FILE)

**Scrivi `_automation/proposals/kb-saturation-report.md`** con questo contenuto:

```markdown
# KB Saturation Report — 2026-03-30

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| ...       | ...   | ...        | ...   | ...  |

## Categorie vicine alla saturazione
[elenco con motivazione]

## Categorie con gap reali
[elenco con motivazione]

## Prossima sessione consigliata
[data + focus tematico]
```

---

## Output finale (breve)

Dopo aver scritto tutti i file, produci questo summary:

```
PROPOSAL SESSION
File analizzati: [N]
Proposte generate: [N] in _automation/proposals/pending/

  - [prop-NNN] [priority] [type] — [titolo]

Saturazione KB: [breve valutazione]
Report: _automation/proposals/kb-saturation-report.md
```
