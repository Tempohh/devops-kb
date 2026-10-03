# Sessione di Esplorazione — Proposte per una Sottocategoria KB

Sei un agente CLI con accesso completo al filesystem tramite strumenti Read, Write, Glob, Grep.
**Devi USARE gli strumenti — non descrivere cosa faresti, FALLO adesso.**
**Non scrivere output testuale prima di aver completato le fasi operative.**

Regola fondamentale: una proposta vale solo se risponde a
"Chi è il lettore concreto che ne beneficia, e cosa gli permette di fare?"

---

## PASSO 0 — Scope (AZIONE IMMEDIATA)

Leggi `_automation/current-task.json`. Il campo `scope` (es. `networking/protocolli`)
è la **sottocategoria da esplorare**: lavori SOLO su `docs/<scope>/`.
Se `scope` manca (task legacy/manuale), scegli tu la sottocategoria con meno file
e dichiaralo nel summary.

Questa sessione decide se la sottocategoria è **esaurita**. Il sistema lo registra
in modo deterministico dal numero di proposte che scrivi:
- **≥1 proposta** → la sottocategoria resta aperta e verrà riesplorata dopo
  che le proposte saranno implementate.
- **0 proposte** → la sottocategoria viene marcata *exhausted* e non verrà più
  esplorata finché non cambia l'insieme dei suoi file (o per 90 giorni).

Quindi: zero è una risposta legittima e utile **solo se è vera**. Non inventare
proposte per riempire, ma non dichiarare esaurita una sottocategoria con gap reali.

---

## PASSO 1 — Censimento della sottocategoria

1. **Glob `docs/<scope>/**/*.md`**: elenco degli argomenti esistenti.
2. Per ogni file leggi frontmatter e **titoli H2/H3** (Grep `^#{2,3} ` sul file):
   ti serve sapere cosa è coperto e a che profondità, non leggere tutto.
3. Leggi per intero **al massimo 3 file**: quelli centrali (hub) o i più corti.
4. Leggi la voce della categoria in `docs/_metadata/taxonomy.yml` (descrizione).

---

## PASSO 2 — Gap analysis

Ragiona come un DevOps mid-senior che usa questa sottocategoria come riferimento
operativo. Elenca mentalmente cosa *dovrebbe* coprire una sezione completa su
`<scope>` (strumenti principali, concetti fondamentali, operazioni day-2,
troubleshooting, sicurezza, integrazione con il resto dello stack) e confrontalo
con quanto già esiste.

Prima di proporre un argomento verifica che non esista già altrove nella KB:
**Grep del termine chiave su `docs/`**. Se è già coperto in un'altra
sottocategoria, NON proporre un file nuovo (al massimo `fix-relation`).

Controlla anche `_automation/proposals/approved/` e `_automation/proposals/rejected/`
(Grep sul `target_file`/titolo): non riproporre ciò che è già stato approvato o
rifiutato.

Per ogni gap candidato applica il test:

```
Reader: [chi è — ruolo, contesto]
Scenario: [problema che ha]
Outcome: [cosa riesce a fare dopo — CONCRETO]
Without_KB: [dove troverebbe info senza questo file?]
Score: high | medium | low
```

**Scarta** se: il lettore troverebbe la stessa info nella documentazione ufficiale
in 2 click; è solo simmetria formale (es. "manca l'equivalente Azure"); è un
dettaglio che sta meglio come sezione di un file esistente (allora proponi
`extend-section`, non `new-file`).

**Tieni** se: colma un gap operativo reale, non banale, che un professionista
incontra davvero.

---

## PASSO 3 — Scrivi le proposte

**Crea i file YAML in `_automation/proposals/pending/`.** Prima trova l'ultimo
numero progressivo usato in `pending/`, `approved/`, `rejected/`.

**Da 0 a 4 proposte**, tutte con `target_file` dentro `docs/<scope>/`.

Formato file `prop-NNN.yaml`:

```yaml
id: prop-NNN
title: "Titolo descrittivo (max 80 caratteri)"
type: new-file         # new-file | extend-section | fix-relation | consolidate | currency | review
priority: high         # high | medium | low
target_file: docs/categoria/sottocategoria/file.md
effort: small          # small (<2h) | medium (2-4h) | large (>4h)
scope: categoria/sottocategoria
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
last_analyzed: AAAA-MM-GG
```

**Non scrivere** `kb-saturation-report.md` e **non toccare** `state.yaml` né
`coverage.yaml`: l'esito viene registrato automaticamente.

---

## Output finale (breve)

```
EXPLORATION SESSION — <scope>
File esistenti: [N]
Proposte generate: [N]
  - [prop-NNN] [priority] [type] — [titolo]
Esito: [aperta | esaurita] — [1-2 frasi: perché]
```
