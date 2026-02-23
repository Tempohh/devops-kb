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
├── cloud/              → Provider e servizi cloud
│   ├── aws/            → Amazon Web Services
│   ├── azure/          → Microsoft Azure
│   └── gcp/            → Google Cloud Platform (futuro)
├── networking/         → Reti, protocolli, architetture di rete
├── messaging/          → Message broker, streaming, event-driven
├── databases/          → SQL, NoSQL, managed databases
├── security/           → Autenticazione, certificati, compliance, IAM
├── ci-cd/              → Pipeline, automazione, tools CI/CD
├── containers/         → Container runtime, orchestration, registry
└── ai/                 → AI/ML services, MLOps
```

**Regola:** Se un argomento non rientra in nessuna categoria → creare una nuova cartella. Le categorie sono estensibili.

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
- `status`: `draft` → `in-progress` → `complete` → `needs-review`
- `difficulty`: `beginner` | `intermediate` | `advanced` | `expert`
- `related`: percorsi relativi dalla root docs, es. `networking/tcp`

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

## ⚠️ CRITICITÀ E LEZIONI APPRESE

> **ISTRUZIONE:** Questa sezione DEVE essere letta all'inizio di OGNI richiesta.
> Se contiene voci attive, verificare che la richiesta corrente non ricada negli stessi errori.

### Registro Criticità

| # | Data | Criticità | Correzione Applicata | File Impattati | Stato |
|---|------|-----------|---------------------|----------------|-------|
| 1 | 2025-02-23 | Progetto inizializzato | N/A | N/A | ✅ Chiuso |

### Pattern da Evitare
<!-- Aggiungere qui pattern ricorrenti di errore -->
<!-- Formato: - **[PATTERN]**: Descrizione → Comportamento corretto -->

### Miglioramenti al CLAUDE.md
<!-- Aggiungere qui migliorie proposte o applicate a questo file -->
<!-- Formato: - **[DATA]**: Descrizione miglioria → Stato (proposta/applicata) -->

---

## 🔧 COMANDI UTILI

```bash
# Preview locale del sito
mkdocs serve

# Build del sito statico
mkdocs build

# Deploy su GitHub Pages
mkdocs gh-deploy
```

---

## 📌 NOTE FINALI
- Il costo di ogni richiesta deve essere proporzionale SOLO alla richiesta stessa
- Mai leggere file non strettamente necessari
- Mai modificare file non esplicitamente richiesti
- In caso di dubbio sul protocollo → chiedere conferma all'utente
- La qualità non è negoziabile: ogni argomento deve essere completo, preciso e utile
