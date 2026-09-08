---
title: Home
slug: index
search_keywords: [devops, knowledge base, documentazione, wiki, cloud, kubernetes, docker, ci-cd, pipeline, networking, database, security, ai, llm, aws, azure, containers, automation, infrastruttura, infrastructure, iac, gitops, mlops, sre, platform-engineering, monitoring, observability, prometheus, grafana, opentelemetry, microservizi, java, spring-boot, quarkus, go, dotnet]
related: [cloud/_index, containers/_index, ci-cd/_index, networking/_index, databases/_index, security/_index, ai/_index, messaging/_index, monitoring/_index, dev/_index]
status: complete
last_updated: 2026-09-08
last_verified: 2026-09-08
---

# DevOps Knowledge Base

Documentazione tecnica completa, scalabile e organizzata per il mondo DevOps Engineering.

---

## 🗂️ Aree di Conoscenza

<div class="grid cards" markdown>

-   :material-cloud:{ .lg .middle } **Cloud**

    ---

    AWS, Azure, GCP — servizi, architetture, best practices

    [:octicons-arrow-right-24: Esplora](cloud/_index.md)

-   :material-lan:{ .lg .middle } **Networking**

    ---

    Protocolli, architetture di rete, DNS, load balancing

    [:octicons-arrow-right-24: Esplora](networking/_index.md)

-   :material-email-fast:{ .lg .middle } **Messaging**

    ---

    Message broker, event streaming, pattern asincroni

    [:octicons-arrow-right-24: Esplora](messaging/_index.md)

-   :material-database:{ .lg .middle } **Databases**

    ---

    SQL, NoSQL, managed databases, replication, sharding

    [:octicons-arrow-right-24: Esplora](databases/_index.md)

-   :material-shield-lock:{ .lg .middle } **Security**

    ---

    Certificati, IAM, IdP, mTLS, compliance, zero trust

    [:octicons-arrow-right-24: Esplora](security/_index.md)

-   :material-pipe:{ .lg .middle } **CI/CD**

    ---

    Pipeline, automazione, Jenkins, GitOps, Helm, Terraform, Ansible

    [:octicons-arrow-right-24: Esplora](ci-cd/_index.md)

-   :material-docker:{ .lg .middle } **Containers**

    ---

    Docker, Kubernetes, OpenShift, orchestration

    [:octicons-arrow-right-24: Esplora](containers/_index.md)

-   :material-robot:{ .lg .middle } **AI**

    ---

    LLM, Transformer, Claude, Agenti, RAG, Fine-Tuning, MLOps

    [:octicons-arrow-right-24: Esplora](ai/_index.md)

-   :material-chart-line:{ .lg .middle } **Monitoring & Observability**

    ---

    Prometheus, Grafana, Loki, Jaeger, OpenTelemetry, SLO/SLI, SRE

    [:octicons-arrow-right-24: Esplora](monitoring/_index.md)

-   :material-code-braces:{ .lg .middle } **Sviluppo Microservizi**

    ---

    Java Spring Boot, Quarkus, .NET, Go, Circuit Breaker, Health Checks, TLS da codice

    [:octicons-arrow-right-24: Esplora](dev/_index.md)

</div>

---

## 📊 Stato del Progetto

<!-- STATS:BEGIN — generato da `python _automation/manage-state.py stats-doc write` -->
| Categoria | File di contenuto | Righe |
|-----------|-------------------|-------|
| cloud | 71 | 45.111 |
| messaging | 43 | 18.230 |
| networking | 31 | 12.279 |
| containers | 30 | 17.676 |
| databases | 21 | 9.222 |
| ci-cd | 20 | 15.956 |
| ai | 19 | 12.354 |
| dev | 18 | 16.634 |
| security | 17 | 9.344 |
| monitoring | 15 | 8.026 |
| iac | 10 | 6.757 |
| **Totale** | **295** | **171.589** |

*Ultimo argomento aggiornato: 2026-09-08 · snapshot rigenerato: 2026-09-08*
<!-- STATS:END -->

### Copertura per Livello di Profondità

| Livello | Argomenti |
|---------|-----------|
| `beginner` | Cloud fondamentali, ML base, Networking OSI/TCP/IP, Container intro |
| `intermediate` | Kubernetes workloads, CI/CD pipeline, Prompt Engineering, API LLM, RAG |
| `advanced` | Kafka internals, PostgreSQL MVCC, Jenkins enterprise, Transformer architecture |
| `expert` | Kafka Streams/KSQLdb, QLoRA fine-tuning, Jenkins security governance, vLLM serving |

---

## ⚡ Quick Start

Per avviare il sito in locale o eseguire il build:

```bash
# Installare le dipendenze (una tantum)
pip install -r requirements.txt

# Avviare il server di sviluppo locale (hot-reload)
mkdocs serve
# → http://127.0.0.1:8000

# Build del sito statico in ./site/ (strict = fallisce sui link rotti)
mkdocs build --strict
```

Il **deploy su GitHub Pages è automatico**: ogni push su `master` che tocca
`docs/`, `mkdocs.yml` o `requirements.txt` fa girare il workflow
`.github/workflows/deploy.yml` che ricostruisce e pubblica il sito. Deploy
manuale: *Actions → Deploy site → Run workflow*. Dettagli in
[`_automation/AUTOMATION.md`](https://github.com/Tempohh/devops-kb/blob/master/_automation/AUTOMATION.md).

Per aggiungere un nuovo argomento alla KB:

```bash
# Creare il file nella categoria corretta
touch docs/<categoria>/<sotto-categoria>/<nuovo-argomento>.md

# Verificare il rendering immediato
mkdocs serve
```

---

## 🔧 Troubleshooting

### Scenario 1 — Articolo non trovato tramite ricerca

**Sintomo:** La ricerca integrata non restituisce risultati per un argomento presente nella KB.

**Causa:** Il file `.md` ha `search_keywords` vuoto o assente, oppure il build non è stato rigenerato dopo l'aggiunta.

**Soluzione:** Verificare il frontmatter del file target e ricostruire il sito.

```bash
# Verificare il frontmatter del file
head -20 docs/<categoria>/<argomento>.md

# Forzare rebuild completo (pulisce cache)
mkdocs build --clean

# Riavviare il server di sviluppo
mkdocs serve
```

---

### Scenario 2 — `mkdocs serve` fallisce all'avvio

**Sintomo:** Errore `Config file 'mkdocs.yml' does not exist` o `ModuleNotFoundError: No module named 'material'`.

**Causa:** Dipendenze non installate o comando eseguito dalla directory sbagliata.

**Soluzione:**

```bash
# Verificare di essere nella root del progetto
pwd  # deve terminare con /devops-kb

# Reinstallare le dipendenze
pip install mkdocs-material mkdocs-minify-plugin

# Verificare la versione
mkdocs --version

# Se si usa un virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
pip install mkdocs-material
```

---

### Scenario 3 — Link interni rotti (404 in navigazione)

**Sintomo:** Cliccando su un link interno il browser mostra 404 o la pagina non viene trovata.

**Causa:** Il file referenziato è stato rinominato, spostato, o il path nel link è errato (relativo vs assoluto).

**Soluzione:**

```bash
# Identificare tutti i link rotti con build strict
mkdocs build --strict 2>&1 | grep "WARNING"

# Esempio output: WARNING - Doc file 'containers/docker/foo.md' not found
# Correggere il path nel file sorgente oppure creare il file mancante
```

---

### Scenario 4 — Deploy su GitHub Pages fallisce

**Sintomo:** `mkdocs gh-deploy` restituisce errori di autenticazione o push rifiutato.

**Causa:** Token GitHub scaduto, branch `gh-pages` protetto, o remote non configurato correttamente.

**Soluzione:**

```bash
# Verificare il remote configurato
git remote -v

# Verificare l'autenticazione
gh auth status

# Deploy esplicito con branch target
mkdocs gh-deploy --remote-branch gh-pages --force

# Se il branch gh-pages non esiste, crearlo
git checkout --orphan gh-pages
git reset --hard
git commit --allow-empty -m "init gh-pages"
git push origin gh-pages
git checkout master
```

---

> *La conoscenza non deve mai essere un limite.*
