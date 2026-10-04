# CLAUDE.md — DevOps Knowledge Base

## 🎯 Identità del Progetto
Knowledge base DevOps scalabile e modulare. Ogni argomento è un file `.md` indipendente con frontmatter YAML standardizzato. L'architettura garantisce costo O(1) per ogni operazione: aggiungere o modificare un argomento non richiede mai la lettura di altri argomenti.

Tecnologie: MkDocs + Material Theme + Draw.io (diagrammi complessi) + GitHub + GitHub Pages.
Piattaforma di sviluppo: Windows.
Lingua contenuti: Italiano con terminologia tecnica in inglese.

---

## 📋 PROCESSO OPERATIVO — LEGGERE SEMPRE PRIMA DI OGNI AZIONE

### Prima di qualsiasi operazione:
1. **Leggere la sezione [⚠️ CRITICITÀ E LEZIONI APPRESE](#-criticità-e-lezioni-apprese)** in fondo a questo file
2. Identificare il tipo di richiesta (vedi sotto)
3. Seguire il protocollo corrispondente
4. Al termine, valutare se la richiesta ha evidenziato criticità da registrare

---

## 🔄 TIPI DI RICHIESTA E PROTOCOLLI

### 1️⃣ NUOVO ARGOMENTO
**Trigger:** "Aggiungi [argomento]", "Crea documentazione su [argomento]"

**Protocollo:**
1. Identificare la categoria corretta dalla gerarchia (vedi sezione Gerarchia)
2. Verificare che l'argomento non esista già (controllare nome file nella cartella target)
3. Creare il file `.md` usando il **Template Standard** (vedi sotto)
4. Compilare TUTTI i campi del frontmatter — nessuna eccezione
5. Popolare `search_keywords` con sinonimi, acronimi, concetti correlati
6. Popolare `related` con gli slug degli argomenti collegati già noti
7. **NON modificare altri file** — il costo deve restare isolato
8. Se durante la stesura emerge che un diagramma complesso sarebbe utile → **proporre** (vedi protocollo 4)

**File coinvolti:** SOLO il nuovo file `.md` creato

---

### 2️⃣ MODIFICA / ESTENSIONE ARGOMENTO ESISTENTE
**Trigger:** "Modifica [argomento]", "Aggiungi sezione su [dettaglio] in [argomento]", "Estendi [argomento]"

**Protocollo:**
1. Leggere SOLO il file dell'argomento richiesto
2. Applicare la modifica richiesta
3. Aggiornare `last_updated` nel frontmatter
4. Se la modifica introduce nuove relazioni → aggiornare `related` nello stesso file
5. **NON leggere né modificare altri file**
6. **NON rigenerare diagrammi esistenti** — sono indipendenti
7. **Gate qualità:** se la modifica aggiunge una sezione intera o cambia più del 30% del contenuto → impostare `status: needs-review` invece di `complete`. Questo segnala che il file ha subito una modifica significativa e richiede una revisione complessiva prima di tornare a `complete`.

**File coinvolti:** SOLO il file `.md` dell'argomento target

---

### 3️⃣ SEGNALAZIONE RELAZIONI
**Trigger:** "Collega [A] a [B]", "Aggiungi relazione tra [A] e [B]"

**Protocollo:**
1. Aprire il file dell'argomento A → aggiungere B nel campo `related`
2. Aprire il file dell'argomento B → aggiungere A nel campo `related`
3. Aggiornare `last_updated` in entrambi

**Nota:** Questo è l'unico caso in cui si toccano 2 file. Il costo è O(2) e non dipende dalla dimensione del progetto.

**File coinvolti:** SOLO i 2 file delle relazioni

---

### 4️⃣ DIAGRAMMA COMPLESSO (Draw.io)
**Trigger:** Claude propone la creazione di un diagramma OPPURE l'utente lo richiede esplicitamente.

**Protocollo SUGGEST → CONFIRM → EXECUTE:**

**Fase SUGGEST (costo: 0 — è parte della risposta corrente):**
- Claude identifica che un diagramma complesso aggiungerebbe valore
- Claude descrive brevemente cosa conterrebbe il diagramma
- Claude chiede conferma all'utente

**Fase CONFIRM (costo: 0 — è il messaggio dell'utente):**
- L'utente conferma con eventuali appunti/correzioni
- L'utente può specificare: elementi da includere, focus, livello di dettaglio

**Fase EXECUTE (costo: 1 richiesta isolata):**
- Leggere il microargomento di riferimento per estrarre le informazioni necessarie
- Generare il file `.drawio.svg` in `assets/diagrams/`
- Naming: `[categoria]-[argomento]-[descrizione].drawio.svg`
  - Esempio: `networking-k8s-cluster-networking.drawio.svg`
- Il diagramma deve essere **ultra preciso e completo**
- Aggiungere la riga di embed nel file `.md` dell'argomento (unica modifica al .md)

**Regole diagrammi:**
- Il file diagramma è INDIPENDENTE dal file `.md`
- Modifiche future al `.md` non richiedono rigenerazione del diagramma
- Rigenerazione del diagramma non richiede modifica del `.md` (il path non cambia)
- Un diagramma si rigenera SOLO su richiesta esplicita

**File coinvolti:** Il file diagramma + 1 riga di embed nel `.md` (solo alla prima creazione)

---

### 5️⃣ RICHIESTA SPECIFICA / MISTA
**Trigger:** Richieste che non rientrano nei casi precedenti.

**Protocollo:**
1. Scomporre la richiesta in sotto-operazioni mappabili ai protocolli 1-4
2. Eseguire ogni sotto-operazione secondo il suo protocollo
3. Minimizzare sempre i file coinvolti

---

### 6️⃣ SEGNALAZIONE CRITICITÀ
**Trigger:** L'utente segnala un errore, un'imprecisione, un problema, o un miglioramento.

**Protocollo:**
1. Registrare nella tabella [Registro Criticità](#registro-criticità)
2. Se la criticità richiede una modifica a questo CLAUDE.md → applicarla subito
3. Se la criticità riguarda un argomento → applicare la correzione al file specifico
4. Se la criticità rivela un pattern ricorrente → aggiungerlo a [Pattern da Evitare](#pattern-da-evitare)

---

## 📝 TEMPLATE STANDARD — NUOVO ARGOMENTO

```markdown
---
title: "Nome Argomento"
slug: nome-argomento
category: categoria-principale
tags: [tag1, tag2, tag3]
search_keywords: [sinonimo1, sinonimo2, acronimo, concetto-correlato, termine-alternativo]
parent: categoria/_index
related: [categoria/slug-argomento-correlato]
official_docs: https://link-documentazione-ufficiale.com
status: draft
difficulty: intermediate
last_updated: YYYY-MM-DD
---

# Nome Argomento

## Panoramica
<!-- Cos'è, perché esiste, quando si usa, quando NON si usa -->
<!-- 3-5 frasi che danno il quadro completo -->

## Concetti Chiave
<!-- I fondamentali da conoscere -->
<!-- Usare admonitions per definizioni importanti -->

## Architettura / Come Funziona
<!-- Spiegazione del funzionamento interno -->
<!-- Qui valutare se proporre un diagramma Draw.io -->

## Configurazione & Pratica
<!-- Esempi concreti, comandi, snippet di codice -->
<!-- Code blocks con syntax highlighting appropriato -->

## Best Practices
<!-- Pattern consigliati, anti-pattern da evitare -->

## Troubleshooting
<!-- Problemi comuni e soluzioni -->

## Relazioni
<!-- Come si integra con altri argomenti della KB -->
<!-- Usare admonitions collapsibili per riferimenti espandibili -->

## Riferimenti
<!-- Link a documentazione ufficiale, articoli autorevoli, video -->
```

---

## 📦 GERARCHIA CATEGORIE

```
docs/
├── cloud/              → Provider cloud (aws, azure, gcp) + finops/
├── containers/         → docker, kubernetes, openshift, helm, kustomize, container-runtime, registry
├── networking/         → fondamentali, protocolli, load-balancing, service-mesh, api-gateway, kubernetes, sicurezza
├── messaging/          → kafka, rabbitmq
├── databases/          → fondamentali, postgresql, nosql, sql-avanzato, replicazione-ha, kubernetes-cloud
├── security/           → autenticazione, autorizzazione, pki-certificati, secret-management, supply-chain, runtime, network, compliance
├── ci-cd/              → jenkins, github-actions, gitlab-ci, gitops, strategie, testing, tools, platform-engineering
├── iac/                → terraform (+ opentofu), pulumi, ansible
├── monitoring/         → fondamentali, tools, alerting, sre
├── ai/                 → fondamentali, modelli, agents, sviluppo, tokens-context, training, mlops
└── dev/                → linguaggi, runtime, resilienza, sicurezza, api, data, integrazioni, processi, testing
```

Riferimento completo (sottocategorie + tag): `docs/_metadata/taxonomy.yml`.

**Regola:** Se un argomento non rientra in nessuna categoria → creare una nuova cartella
e aggiungerla a `taxonomy.yml`. Le categorie sono estensibili.

---

## ✏️ CONVENZIONI

### Naming
- **File:** `kebab-case.md` → `mutual-authentication.md`, `aurora-postgresql.md`
- **Cartelle:** `kebab-case/` → `ci-cd/`, `cloud/`
- **Diagrammi:** `[categoria]-[argomento]-[desc].drawio.svg`
- **Immagini:** `[categoria]-[argomento]-[desc].[ext]`

### Frontmatter
- `slug`: identico al nome file senza estensione
- `tags`: lowercase, inglese, plurale dove sensato
- `search_keywords`: includere SEMPRE acronimi, sinonimi italiani e inglesi
- `difficulty`: `beginner` | `intermediate` | `advanced` | `expert`
- `related`: percorsi relativi dalla root docs, es. `networking/tcp`
- `last_updated`: cambia **solo** su modifica sostanziale del contenuto
- `last_verified`: data dell'ultimo controllo di correttezza/attualità (segnale di freschezza)

#### Ciclo di vita `status`

| valore | significato | chi lo assegna |
|---|---|---|
| `draft` | bozza incompleta | autore iniziale |
| `complete` | supera il gate meccanico (≥150 righe utili, ≥2 code-block, sezione Troubleshooting, ≥10 `search_keywords`, ≥2 `related`) | task `new_topic` / `audit` |
| `needs-review` | modifica significativa (sezione intera o >30% del contenuto) o review non conclusa | task `expand`, o l'autore di una modifica grande |
| `reviewed` | un modello ad alto ragionamento ha giudicato il file **corretto, attuale e utile**; imposta anche `last_verified` | task `review` / `currency` |

`complete` **non** implica "revisionato": è solo la soglia meccanica. La qualità
reale la certifica `reviewed`. Non impostare `complete` a mano su un file che ha
subito una modifica grande — usa `needs-review`.

### Contenuto
- Titoli H1 solo per il titolo principale (1 per file)
- H2 per le sezioni del template
- H3+ per sotto-sezioni
- Code blocks sempre con language tag: ````yaml`, ````bash`, ````python`, etc.
- Admonitions per note importanti, warning, tips

### Admonitions Collapsibili (per riferimenti incrociati)
```markdown
??? info "Mutual TLS — Approfondimento"
    Breve riassunto contestuale (2-3 frasi massimo).
    
    **Approfondimento completo →** [Mutual TLS](../security/mutual-tls.md)
```

### Admonitions Standard
```markdown
!!! note "Nota"
    Informazione supplementare utile.

!!! warning "Attenzione"
    Aspetto critico da non sottovalutare.

!!! tip "Suggerimento"
    Best practice o consiglio pratico.

!!! example "Esempio"
    Caso d'uso concreto.
```

---

## 🤖 LAYER DI AUTOMAZIONE

La KB si mantiene anche da sola. Documento autoritativo: **`_automation/AUTOMATION.md`**.
Sintesi:

- **Esecuzione**: GitHub Actions (`.github/workflows/kb-maintenance.yml`) esegue una
  iterazione bounded via `_automation/run_once.py`. Trigger **solo `workflow_dispatch`**:
  lo scheduling puntuale **alle 00/06/12/18 ora di Roma** è delegato a uno scheduler
  **ESTERNO** (cron-job.org, timezone Europe/Rome) che chiama l'endpoint REST
  `actions/workflows/.../dispatches`. Il cron nativo di Actions è stato rimosso:
  partiva con 1–4 h di ritardo e il gate orario scartava sistematicamente ogni run.
  Setup dello scheduler esterno (PAT fine-grained + cron-job.org): `_automation/AUTOMATION.md` §2.
  In locale `KB_Aggiorna_Sicuro.bat` fa lo stesso per 1 task. Il deploy del sito
  (`deploy.yml` → `mkdocs gh-deploy`) parte su push a `master`.
- **Pausa** (interruttore, solo owner del repo): Actions variable
  `KB_MAINTENANCE_ENABLED`. `false`/`0`/`off`/`no` → lo step *Gate* esce
  `enabled=false` e dispatch esterno + *Run workflow* fanno no-op pulito; assente o
  altro valore → attiva (default). `gh variable set KB_MAINTENANCE_ENABLED --body false|true`.
  Input dispatch `force: true` = un giro ignorando la pausa. `run_once.py` onora lo
  stesso nome come env var (pausa locale). Dettagli in `_automation/AUTOMATION.md` §2.
- **Coda**: `_automation/state.yaml` (gestita SOLO da `manage-state.py` — un agente
  di contenuto non la tocca mai). Priorità P0>P1>P2>P3; `interrupted_task` per il
  recovery.
- **Tipi di task e prompt**: `new_topic`→`run-prompt.md`, `expand`→`expand-prompt.md`,
  `audit`→`audit-prompt.md`, `review`→`review-prompt.md`, `currency`→`currency-prompt.md`,
  `consolidate`→`consolidate-prompt.md`, `proposal`→`proposal-prompt.md`.
- **Policy modello** (`_automation/config.yaml`): audit→Haiku/low, new_topic·expand→
  Sonnet, review·proposal→Opus/high. `run_once.py` passa `--model` di conseguenza.
- **Cascata `next-work`** (coda vuota, entrambi i loop): proposte pendenti →
  lifecycle (`draft`/`needs-review`) → gate meccanico → review dei `complete` →
  currency dei `reviewed` scaduti → esplorazione di **una sottocategoria** alla volta.
  Fonti misurate in Python (0 token), cooldown + tetto tentativi anti-loop.
- **Criterio di completezza**: non un numero di file, ma `coverage.yaml` — una
  sottocategoria è `exhausted` quando la sua proposal limitata restituisce zero
  proposte; si riapre se cambia l'insieme dei suoi file o dopo 90 giorni. Tutte le
  fonti vuote ⇒ `idle` (nessuna chiamata al modello) fino alla prossima scadenza.
  `saturation.max_file_count` è solo un tetto di budget opzionale (default `null`).
- **Quality revisioning**: `review`/`currency` possono retrocedere lo `status` o
  aprire una proposta di follow-up; i `needs-review` risultanti rientrano dalla
  fonte lifecycle.

**Quando lavori come agente di contenuto** (protocolli 1–5): il task è in
`_automation/current-task.json`; segui il prompt indicato; **non leggere né
scrivere `_automation/state.yaml`**; fermati dopo un task.

---

## ⚠️ CRITICITÀ E LEZIONI APPRESE

> **ISTRUZIONE:** Questa sezione DEVE essere letta all'inizio di OGNI richiesta.
> Se contiene voci attive, verificare che la richiesta corrente non ricada negli stessi errori.

### Registro Criticità

| # | Data | Criticità | Correzione Applicata | File Impattati | Stato |
|---|------|-----------|---------------------|----------------|-------|
| 1 | 2025-02-23 | Progetto inizializzato | N/A | N/A | ✅ Chiuso |
| 2 | 2026-02-23 | Sequenze di escape letterali (es. `\n`) nei diagrammi/schemi renderizzate come testo invece che come caratteri di controllo | Aggiunto pattern da evitare; usare sempre newline reali o attributi XML appropriati nei file `.drawio.svg` | CLAUDE.md | ✅ Chiuso |
| 3 | 2026-09-08 | `status: complete` privo di significato (404/407 file "complete"); gate qualità solo meccanico; nessun freno alla crescita; automazione non documentata in CLAUDE.md; sezione AI indietro di una generazione (Claude 4.6 vs famiglia Claude 5); `mkdocs build --strict` rotto; automazione dipendente dal PC acceso | Ciclo di stato reale con `reviewed`/`last_verified`; task type `review`/`currency`/`consolidate`; freno di saturazione; sezione "Layer di automazione"; CI GitHub Actions (deploy + manutenzione schedulata); fix config tags; sweep attualità sezione AI | CLAUDE.md, `_automation/*`, `.github/workflows/*`, `mkdocs.yml`, `docs/ai/modelli/*`, `docs/index.md`, `docs/_metadata/taxonomy.yml` | ✅ Chiuso |
| 4 | 2026-09-09 | Il cron nativo di GitHub Actions per `kb-maintenance` partiva con 1–4 h di ritardo (o veniva droppato): lo step *Gate* con finestra oraria di 1 h scartava **ogni** run schedulato (`ora di Roma fuori da 00/06/12/18`). Da quando lo schedule fu ancorato: zero iterazioni reali dell'automazione via cron. | Rimosso `schedule:` dal workflow (trigger solo `workflow_dispatch`); scheduling puntuale 00/06/12/18 ora di Roma delegato a scheduler esterno (cron-job.org, timezone Europe/Rome, PAT fine-grained con permesso *Actions: RW*) che chiama l'endpoint `dispatches`; gate ridotto a pausa + secret; runbook in `AUTOMATION.md` §2 | `.github/workflows/kb-maintenance.yml`, `_automation/AUTOMATION.md`, CLAUDE.md | ✅ Chiuso |
| 5 | 2026-09-27 | `run_once.py::handle_empty_queue` iniettava un nuovo task `proposal` (Opus/high, scansione intera KB) a ogni tick con coda vuota, senza alcun cooldown — fino a 4 sessioni/giorno via CI, tutte concluse a "zero proposte" perché nulla era cambiato dall'ultima (5 commit auto #552-556 di fila identici). `kb-infinite.ps1` aveva lo stesso problema ma piggiore: loop ogni 30s, `EmptyBeforeProposal=1` → re-iniettava dopo una sola run vuota (~30-60s); inoltre il branch throttle faceva `continue` senza `Start-Sleep`, quindi durante l'attesa girava senza pausa (centinaia di iterazioni/sec, solo I/O locale, nessun costo Opus ma spreco CPU/disco). | `run_once.py`: rimossa l'iniezione standalone a coda vuota — la generazione proposte per CI/`.bat` resta solo dentro `init-analysis` (1/settimana, `analysis_interval_days`). `kb-infinite.ps1`: mantenuta l'iniezione rapida (uso interattivo) ma con throttle di sessione in memoria (`ProposalMinIntervalSeconds=600`, non persistito in `state.yaml`), `Start-Sleep` esplicito nel branch throttle, e output silenzioso durante l'attesa (countdown solo a 30/10/5/3/2/1s) invece di un header vuoto ogni 30s. | `_automation/run_once.py`, `_automation/manage-state.py`, `_automation/kb-infinite.ps1`, `_automation/AUTOMATION.md`, CLAUDE.md | ✅ Chiuso |
| 6 | 2026-09-27 | `kb-maintenance.yml` (CI) chiamava `mkdocs gh-deploy --force --strict` manualmente dopo ogni push, ma quello stesso push (quando toccava `docs/**`) faceva scattare *anche* `deploy.yml` in automatico (trigger su `push`+`paths`) — doppio build/deploy per ogni task CI che tocca contenuti. Inoltre `deploy-pages` aveva `cancel-in-progress: false`: push ravvicinati da `kb-infinite.ps1` (che pusha dopo ogni singolo task, non in batch) accodavano build ridondanti invece di cancellare quelle superate. | Rimossa la chiamata `mkdocs gh-deploy` da `kb-maintenance.yml` (resta solo `git push`, il deploy lo fa `deploy.yml` via trigger); `deploy-pages` → `cancel-in-progress: true`. | `.github/workflows/kb-maintenance.yml`, `.github/workflows/deploy.yml`, `_automation/AUTOMATION.md`, CLAUDE.md | ✅ Chiuso |
| 7 | 2026-10-03 | `kb-infinite.ps1` a coda vuota aveva un'unica mossa: proposal globale Opus su tutta la KB, ogni 10 min (throttle #5). Con KB ferma e tetto fisso `target_file_count: 330` (scelto a mano, 328 file) ogni sessione concludeva "zero proposte": 20+ commit `proposal` consecutivi con solo `state.yaml` (#750–#772). Nel frattempo 261 file `complete` mai revisionati (30 `reviewed`): le review arrivavano solo da `init-analysis`, 3/settimana; `inject-review-tasks` esisteva ma nessun loop lo chiamava. Gate meccanico con falsi `no_related`/`no_keywords` su liste YAML a blocchi. | Cascata deterministica `manage-state.py next-work` usata da ps1 e `run_once.py` (proposte → lifecycle → gate → review → currency → esplorazione per sottocategoria), cooldown + `max_attempts` anti-loop; `coverage.yaml` con esaurimento per sottocategoria al posto del tetto fisso (`max_file_count` opzionale, default null); `proposal-prompt.md` limitato a uno `scope`; stato `idle` senza chiamate al modello; no commit per proposal vuote; gate su frontmatter parsato; 17 test su copie temporanee. | `_automation/manage-state.py`, `_automation/kb-infinite.ps1`, `_automation/run_once.py`, `_automation/proposal-prompt.md`, `_automation/config.yaml`, `_automation/AUTOMATION.md`, CLAUDE.md | ✅ Chiuso |
| 8 | 2026-10-03 | Falso rate limit: i pattern (`rate limit`, `usage limit`…) erano cercati in TUTTO l'output dell'agente. La review di `api-gateway/rate-limiting.md` (task 848), che nel riepilogo parla di rate limiting, veniva scambiata per un rate limit: task lasciato pending, probe "OK" riuscito, task rieseguito → ~1 h bloccato e 3 review Opus dello stesso file. Stesso falso positivo su `kong.md` (846). | Pattern cercati solo se `exit != 0` o output < 500 caratteri (il messaggio reale del CLI è una riga), in `kb-infinite.ps1` e `run_once.py::is_rate_limited`; task 848 chiuso a mano (review già applicata). | `_automation/kb-infinite.ps1`, `_automation/run_once.py`, CLAUDE.md | ✅ Chiuso |
| 9 | 2026-10-04 | 25 file `needs-review` (prodotti dalle review, con marker `<!-- REVIEW: verificare X -->` su fatti esterni) parcheggiati 30 giorni: la fonte lifecycle li rimandava a `review`, bloccata dal cooldown sullo stesso (tipo, file) appena revisionato; e una nuova review avrebbe dato lo stesso esito. | Lifecycle: `needs-review` con marker → `currency` (verifica su `official_docs`, rimuove i marker risolti; `reason` elenca i marker); senza marker → `review`. `currency-prompt.md` tratta i marker come priorità. | `_automation/manage-state.py`, `_automation/currency-prompt.md`, CLAUDE.md | ✅ Chiuso |
| 10 | 2026-10-04 | I task creati da proposte approvate (`approve-proposal` / `auto-approve-proposals`) non avevano `created_at`: il cooldown della cascata non li vedeva. Caso reale: la review #1113 ha aperto `prop-143` (currency su `kafka/kubernetes-cloud/helm.md`) e lascia il file `needs-review` con marker → dopo il task della proposta, lifecycle avrebbe accodato un secondo currency identico. | `created_at` + `source: proposals` sui task da proposta; verificato sullo stato reale (helm.md non più candidato dopo l'approvazione). | `_automation/manage-state.py`, CLAUDE.md | ✅ Chiuso |

### Pattern da Evitare

- **[ESCAPE LETTERALI NEI DIAGRAMMI]**: Quando si generano file `.drawio.svg` o altri formati schema, non usare mai sequenze di escape testuali come `\n`, `\t`, `\r` all'interno dei valori delle celle/label. Questi vengono renderizzati letteralmente come stringa invece che essere interpretati come caratteri di controllo. → Usare newline XML reali (`&#xa;`) per i ritorni a capo nelle label Draw.io, oppure suddividere il testo su più elementi distinti.

### Miglioramenti al CLAUDE.md
<!-- Formato: - **[DATA]**: Descrizione miglioria → Stato (proposta/applicata) -->
- **2026-09-08**: Aggiunta sezione "Layer di automazione"; ciclo di vita `status`
  esplicito con `reviewed`/`last_verified`; gerarchia aggiornata a 11 categorie;
  registro criticità #3. → applicata
- **2026-09-08**: Schedule `kb-maintenance` ancorato a 00/06/12/18 ora di Roma
  (cron UTC estate/inverno + gate); interruttore di pausa owner-only
  `KB_MAINTENANCE_ENABLED` (Actions variable + env var per `run_once.py`);
  collaboratore `danipalu03` rimosso (owner unico controllo). → applicata
- **2026-09-09**: `kb-maintenance` migrato da cron nativo a **scheduler esterno**
  (cron-job.org → endpoint `dispatches`); il cron di Actions arrivava troppo in
  ritardo e il gate orario azzerava il throughput (criticità #4). Workflow con
  trigger solo `workflow_dispatch`, gate ridotto a pausa + secret. → applicata
- **2026-09-27**: Rimossa l'iniezione standalone di task `proposal` a coda vuota
  da `run_once.py` (CI + `.bat` locale) — restava solo dentro `init-analysis`,
  1/settimana; sessioni Opus/high ripetute a vuoto (criticità #5). Aggiunto
  throttle di sessione (10 min, in memoria) in `kb-infinite.ps1`, unico
  percorso che mantiene l'iniezione rapida per uso interattivo. → applicata
- **2026-10-03**: Throttle/backoff delle proposal sostituiti dalla cascata
  `next-work`; freno di saturazione da tetto globale a esaurimento per
  sottocategoria (`coverage.yaml`) (criticità #7). → applicata

---

## 🔧 COMANDI UTILI

```bash
# Preview locale del sito
mkdocs serve

# Build (strict = fallisce su link rotti; è quello che gira in CI)
mkdocs build --strict

# Deploy: automatico su push a master (.github/workflows/deploy.yml).
# Manuale/fallback locale:
mkdocs gh-deploy --force

# Automazione — un task dalla coda (stessa logica della CI):
python _automation/run_once.py --max-tasks 1
python _automation/manage-state.py stats
python _automation/manage-state.py stats-doc write   # rigenera la tabella in docs/index.md

# Automazione CI — pausa / ripresa (solo owner del repo):
gh variable set KB_MAINTENANCE_ENABLED --body false   # STOP  (effetto dal tick successivo)
gh variable set KB_MAINTENANCE_ENABLED --body true    # RIPRENDI
gh workflow disable "KB maintenance"   # hard-kill alternativo (ferma anche il dispatch)
```

---

## 📌 NOTE FINALI
- Il costo di ogni richiesta deve essere proporzionale SOLO alla richiesta stessa
- Mai leggere file non strettamente necessari
- Mai modificare file non esplicitamente richiesti
- In caso di dubbio sul protocollo → chiedere conferma all'utente
- La qualità non è negoziabile: ogni argomento deve essere completo, preciso e utile
