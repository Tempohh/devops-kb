# Sessione di Analisi Strategica — Generazione Proposte KB

Stai eseguendo un'analisi strategica della Knowledge Base DevOps. Questa sessione è
diversa dall'audit di qualità: non guarda i singoli file ma l'utilità complessiva della
KB come strumento. Le proposte che generi vengono presentate al proprietario per
approvazione — nessun file di contenuto viene modificato.

**Regola fondamentale:** Una proposta vale solo se risponde alla domanda
"Chi è il lettore concreto che ne beneficia, e cosa gli permette di fare che prima
non riusciva a fare?" Se non riesci a rispondere, la proposta non va creata.

---

## Fase 1 — Censimento strutturale della KB

Prima di tutto, mappa la struttura reale con Glob:

```
docs/**/_index.md    → categorie e sottocategorie esistenti
docs/**/*.md         → tutti i file (escludi _index.md e tags.md)
```

Per ogni categoria principale (cloud, containers, networking, ci-cd, databases,
messaging, security, monitoring, ai, dev), conta:
- Quanti file esistenti
- Quali sottocategorie hanno _index.md
- Eventuali file `status: draft` o `status: needs-review` (leggi solo frontmatter)

**Non leggere il contenuto completo** in questa fase — solo frontmatter (prime 20 righe).

---

## Fase 2 — Analisi strategica del valore (NON audit tecnico)

Leggi **8-12 file** scelti tra:
1. File che sembrano essere hub di navigazione (molti `related`)
2. File in categorie recenti o poco sviluppate
3. File che il frontmatter segnala come `needs-review`

Per ogni file letto, valuta:
- **Utilità**: il contenuto risolve un problema reale? O è documentazione per documentazione?
- **Completezza pratica**: un DevOps potrebbe usare questo file come guida autonoma?
- **Connettività**: è ben collegato al resto della KB o è un'isola?

---

## Fase 3 — Identificazione opportunità con test di utilità

Per ogni potenziale proposta che stai considerando, applica questo test prima di scriverla:

### Test di utilità (obbligatorio per ogni proposta)

```
Scenario: [Descrivi il lettore — ruolo, contesto, problema che ha]
Azione: [Cosa fa con questo contenuto — lo legge, lo usa come riferimento, lo segue]
Risultato: [Cosa riesce a fare dopo che prima non riusciva]
Alternativa: [Dove troverebbe questa info senza la KB? Quanto è difficile?]
Incremento: [Quanto valore aggiunge rispetto all'alternativa?]
```

**Scarta la proposta se:**
- "Alternativa" è la documentazione ufficiale che il lettore leggerebbe comunque
- "Risultato" è "sa cosa è X" senza un'applicazione pratica
- Stai solo completando una simmetria formale (es. "GCP ha questo, AWS pure, aggiungiamo")
  senza una reale lacuna di copertura tematica

**Tieni la proposta se:**
- Colma un gap trasversale (un tema che taglia più sezioni e non è coperto da nessuna)
- Aggiunge connettività mancante (pattern relazione A↔B non documentata)
- Risolve un problema operativo reale (troubleshooting, decision-making, configuration)

---

## Fase 4 — Valutazione saturazione della KB

Prima di generare proposte, rispondi a queste domande nella tua analisi interna:

1. **Coverage**: La KB copre in modo adeguato i problemi quotidiani di un DevOps mid-senior?
   Stima la percentuale di copertura per categoria (es. "Kubernetes: 85%, GCP: 40%").

2. **Depth**: I file esistenti hanno profondità pratica o sono solo panoramiche?
   Identifica le categorie dove la profondità è insufficiente.

3. **Segnale di saturazione**: Stai trovando proposte solo perché "mancano" file,
   o perché c'è una reale esigenza non coperta? Se le ultime 3 proposte che hai
   pensato non passano il test di utilità, probabilmente la KB è vicina alla
   saturazione in quella categoria — segnalalo.

4. **Priorità strategica**: Quali sono i 3 temi dove un'ora di lavoro porta il
   massimo beneficio al lettore? Solo quelli meritano proposta P1.

---

## Fase 5 — Generazione proposte (formato obbligatorio)

Crea file YAML in `_automation/proposals/pending/`. Usa questo formato:

```yaml
id: prop-NNN
title: "Titolo descrittivo (max 80 caratteri)"
type: new-file         # new-file | extend-section | fix-relation | consolidate
priority: high         # high | medium | low
target_file: docs/categoria/sottocategoria/file.md
effort: small          # small (<2h) | medium (2-4h) | large (>4h)
description: |
  Descrizione dettagliata: cosa aggiungere, struttura suggerita, esempi concreti.
  Minimo 5 righe. Include: sezioni specifiche, esempi di codice/comandi da aggiungere,
  riferimenti tecnici (strumenti, versioni, pattern specifici).
rationale: |
  Motivazione strategica: chi è il lettore, quale problema risolve, perché ora.
  Include il risultato del test di utilità (scenario + risultato concreto).
utility_test:
  reader: "DevOps mid-senior che lavora con [tecnologia]"
  scenario: "Sta cercando di risolvere [problema specifico]"
  outcome: "Dopo aver letto, riesce a [azione concreta]"
  without_kb: "Senza questo file dovrebbe [alternativa complessa]"
  score: high | medium | low   # valutazione soggettiva del tuo test
tags: [tag1, tag2, tag3]
last_analyzed: YYYY-MM-DD
```

**Naming file:** `prop-NNN.yaml` (usa il numero progressivo dopo l'ultimo esistente)

**Limiti:**
- Massimo **6 proposte** per sessione (meno è meglio se le idee sono davvero forti)
- `priority: high` solo se `utility_test.score: high` E il tema è assente dalla KB
- Non creare proposte solo per completare simmetrie formali tra provider cloud
- Se la KB è satura in una categoria, non forzare proposte — segnala la saturazione

---

## Fase 6 — Analisi di saturazione e riflessione

Dopo aver generato le proposte, scrivi un breve report di saturazione in
`_automation/proposals/kb-saturation-report.md`:

```markdown
# KB Saturation Report — YYYY-MM-DD

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| ...       | ...   | ...        | ...   | ...  |

## Categorie vicine alla saturazione
[Elenco con motivazione]

## Categorie con gap reali
[Elenco con motivazione]

## Prossima sessione di proposte consigliata
[Data suggerita + focus tematico raccomandato]

## Segnale di stop
[Se la KB è complessivamente completa per il suo scopo, dichiaralo esplicitamente]
```

---

## Output finale (obbligatorio)

```
PROPOSAL SESSION STRATEGICA
File analizzati: [numero]
Proposte generate: [numero]

Proposte:
  - [prop-NNN] [priority] [type] [effort] — [titolo]
  - ...

Saturazione stimata KB: [breve valutazione, es. "70% coverage, depth adeguata in 6/10 categorie"]
Categorie prioritarie per future proposte: [lista]
Categorie sature (no nuove proposte utili): [lista]

Report salvato in: _automation/proposals/kb-saturation-report.md
```
