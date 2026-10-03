---
title: "GitHub Actions — Enterprise & Self-Hosted Runners"
slug: enterprise
category: ci-cd
tags: [github-actions, enterprise, self-hosted-runners, security, arc, github-enterprise]
search_keywords: [github actions self hosted runner, GHAS, github secret protection, github code security, repository rulesets, required workflows, ARC actions runner controller, github enterprise server, runner groups, github actions security hardening, github actions audit log, github advanced security, codeql, dependabot, secret scanning, push protection]
parent: ci-cd/github-actions/_index
related: [ci-cd/github-actions/workflow-avanzati, ci-cd/jenkins/agent-infrastructure, security/supply-chain/sbom-cosign]
official_docs: https://docs.github.com/en/actions/hosting-your-own-runners
status: reviewed
difficulty: expert
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# GitHub Actions — Enterprise & Self-Hosted Runners

## Panoramica

In contesti enterprise, i GitHub-hosted runner spesso non sono sufficienti: le organizzazioni necessitano di accesso a reti private, hardware specifico (GPU, ARM, high-memory), compliance su dove girano i workload, o controllo completo sulla catena di custody del software. Questa guida copre i self-hosted runner (incluso il runner autoscalante su Kubernetes tramite Actions Runner Controller), le funzionalità di sicurezza avanzata di GitHub (GHAS), la gestione centralizzata delle policy in GitHub Enterprise, e le best practice di hardening per pipeline CI/CD sicure.

## Self-Hosted Runners

### Quando Usarli

| Scenario | Motivazione |
|----------|-------------|
| Accesso a VPC/rete privata | Database, API interne, registri privati non accessibili da Internet |
| Hardware specifico | GPU per ML training, ARM (Apple Silicon, Graviton), high-memory |
| Compliance | Data sovereignty (dati non possono uscire dalla regione/infrastruttura) |
| Costo | Workload ad alto volume di minuti CI (self-hosted può essere più economico) |
| Cache locale | Build cache persistente tra run (evita re-download dipendenze) |
| Long-running jobs | Oltre i limiti dei GitHub-hosted runner (6h per job) |

### Registrazione Runner

```bash
# 1. Scaricare il runner (esempio Linux x64)
#    Usare l'ultima release: https://github.com/actions/runner/releases
#    (GitHub rifiuta runner troppo vecchi: tenerlo aggiornato)
RUNNER_VERSION=<VERSIONE>   # sostituire con la release corrente
mkdir actions-runner && cd actions-runner
curl -o actions-runner.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
tar xzf ./actions-runner.tar.gz

# 2. Configurare il runner (token generato in Settings > Actions > Runners)
./config.sh \
  --url https://github.com/my-org/my-repo \
  --token AABBCCDDEE... \
  --name my-runner-001 \
  --labels linux,x64,production,large \
  --work /tmp/runner-work \
  --runnergroup "Production Runners"

# 3. Runner ephemerali (best practice sicurezza): si registra e poi viene rimosso
# --ephemeral: il runner si deregistra dopo aver completato 1 job
./config.sh \
  --url https://github.com/my-org \
  --token AABBCCDDEE... \
  --ephemeral \
  --name ephemeral-runner-$RANDOM

# 4. Avviare come servizio (Linux)
sudo ./svc.sh install
sudo ./svc.sh start

# 5. Oppure avviare in foreground (per container)
./run.sh
```

!!! warning "Runner Ephemeral — Sicurezza"
    I runner ephemerali (`--ephemeral`) sono fondamentali per ambienti multi-tenant. Un runner persistente che esegue job di repository diversi rischia contaminazione tra job (file temporanei, variabili d'ambiente, credenziali in cache). Con `--ephemeral`, il runner termina dopo 1 job e viene ricreato pulito.

!!! danger "Self-hosted runner e repository pubblici"
    Non collegare mai runner self-hosted persistenti a repository pubblici: una PR da fork può eseguire codice arbitrario sul runner (e quindi nella tua rete). Usare solo repository privati, oppure runner ephemeral isolati (VM/Pod usa-e-getta) con runner group ristretto a repo/workflow noti.

### Dockerfile per Runner Containerizzato

```dockerfile
FROM ubuntu:22.04

ARG RUNNER_VERSION=<VERSIONE>   # release corrente del runner
ARG TARGETPLATFORM

RUN apt-get update && apt-get install -y \
    curl \
    git \
    jq \
    libicu70 \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Utente non-root per il runner
# (niente sudo NOPASSWD: equivale a dare root ai workflow, concederlo solo se indispensabile)
RUN useradd -m runner

WORKDIR /home/runner

# Scarica runner in base all'architettura
RUN case ${TARGETPLATFORM} in \
    "linux/amd64") ARCH="x64" ;; \
    "linux/arm64") ARCH="arm64" ;; \
    *) ARCH="x64" ;; \
    esac && \
    curl -o actions-runner.tar.gz -L \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${ARCH}-${RUNNER_VERSION}.tar.gz" && \
    tar xzf actions-runner.tar.gz && \
    rm actions-runner.tar.gz

RUN ./bin/installdependencies.sh

USER runner

COPY entrypoint.sh /home/runner/entrypoint.sh
ENTRYPOINT ["/home/runner/entrypoint.sh"]
```

## Actions Runner Controller (ARC)

ARC è un operatore Kubernetes che gestisce runner GitHub Actions scalabili automaticamente. I runner vengono creati come Pod **ephemeral** in risposta ai job in coda: un *listener* per ogni scale set interroga GitHub (long-poll in uscita, nessun webhook in ingresso) e chiede al controller di creare/rimuovere `EphemeralRunner` in base alla coda.

!!! note "ARC ufficiale vs legacy"
    Questa sezione usa l'ARC mantenuto da GitHub (modalità *runner scale set*, chart `gha-runner-scale-set*`). Il vecchio ARC della community (`summerwind`, CRD `RunnerDeployment`/`HorizontalRunnerAutoscaler`, repo Helm `actions-runner-controller.github.io`) è un progetto distinto e non va mischiato con questo.

### Installazione con Helm

```bash
# Controller ARC (chart OCI ufficiale GitHub, nessun `helm repo add` necessario).
# Pinnare sempre --version all'ultima release: https://github.com/actions/actions-runner-controller/releases
helm install arc \
  --namespace arc-systems \
  --create-namespace \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller \
  --version <VERSIONE>
```

### RunnerScaleSet — Runner Autoscalanti

```yaml
# arc-runner-scale-set.yml
# Installa con (il nome della release = nome da usare in `runs-on`):
#   helm install arc-runner-k8s \
#     --namespace arc-runners \
#     --create-namespace \
#     oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
#     --version <VERSIONE> \
#     --values arc-runner-scale-set.yml
githubConfigUrl: "https://github.com/my-org"   # org (consigliato) o repo
githubConfigSecret: arc-github-secret          # Secret con GitHub App credentials

minRunners: 0       # Scale to zero quando non ci sono job
maxRunners: 20      # Massimo 20 runner concorrenti

# Docker-in-Docker gestito dal chart: aggiunge il sidecar dind (privileged)
# e i volumi necessari. Non serve scrivere a mano initContainer/sidecar.
containerMode:
  type: "dind"      # alternativa: "kubernetes" (no privileged, job eseguiti come Pod)

template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:<VERSIONE>   # pin, evitare :latest
        command: ["/home/runner/run.sh"]
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2"
            memory: "4Gi"
```

Nel workflow, il nome della release Helm diventa il label di `runs-on`:

```yaml
jobs:
  build:
    runs-on: arc-runner-k8s
```

!!! warning "dind = container privileged"
    Il sidecar `dind` gira `privileged`: un job compromesso può uscire verso il nodo. Per carichi non fidati preferire `containerMode: kubernetes` (senza privileged), o nodi dedicati con taint/toleration e isolamento di rete.

### Secret per Autenticazione GitHub App

```yaml
# Creare la GitHub App in Settings > Developer settings > GitHub Apps
# Scaricare la private key e annotare App ID e Installation ID

apiVersion: v1
kind: Secret
metadata:
  name: arc-github-secret
  namespace: arc-runners
stringData:
  github_app_id: "123456"
  github_app_installation_id: "78901234"
  github_app_private_key: |
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpAIBAAKCAQEA...
    -----END RSA PRIVATE KEY-----
```

## Runner Groups

I runner group consentono di organizzare i runner self-hosted e controllare quale repository/workflow può usarli.

**Configurazione via API GitHub:**

```bash
# Creare un runner group per i deployment di produzione
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/orgs/my-org/actions/runner-groups \
  -d '{
    "name": "Production Runners",
    "visibility": "selected",
    "selected_repository_ids": [123456789, 987654321],
    "allows_public_repositories": false,
    "restricted_to_workflows": true,
    "selected_workflows": [
      "deploy-production.yml"
    ]
  }'
```

**Utilizzo nel workflow:**

```yaml
jobs:
  deploy:
    runs-on:
      group: Production Runners     # Runner group
      labels: [linux, x64, prod]   # Labels aggiuntive per filtrare
```

## Security Hardening

### Permissions Minime — Principio di Least Privilege

```yaml
# A livello workflow: disabilita tutti i permessi di default
permissions:
  contents: read    # Solo lettura del codice

jobs:
  build:
    permissions:
      contents: read
      packages: write   # Solo il job che fa push ai packages

  security-scan:
    permissions:
      contents: read
      security-events: write  # Per upload dei risultati SARIF

  deploy:
    permissions:
      contents: read
      id-token: write   # Solo per OIDC
      deployments: write
```

### SHA Pinning delle Actions

```yaml
# ❌ Vulnerabile: tag mutabile, può essere spostato su un commit malevolo
#    (es. compromissione di tj-actions/changed-files, marzo 2025)
- uses: actions/checkout@v4

# ✅ Sicuro: SHA immutabile, impossibile cambiare il codice senza modificare il workflow
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
- uses: actions/setup-java@<SHA-40-hex>  # v4.x (SHA completo di 40 caratteri esadecimali, copiato dal commit del tag)
- uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502  # v4.0.2

# Tool per aggiornare automaticamente i SHA:
# - Dependabot (nativo GitHub)
# - Renovate (più configurabile)
# - pin-github-action CLI (github.com/mheap/pin-github-action)
# Enforcement: la policy org/enterprise "Require actions to be pinned to a full-length commit SHA"
# (Settings > Actions > General) rifiuta i workflow che usano tag o branch.
```

### Rischi di `pull_request_target`

```yaml
# ⚠️ ATTENZIONE: pull_request_target esegue il workflow del branch BASE
# con i secrets del repository. Se il workflow fa checkout del branch PR
# e poi esegue codice da quella PR, c'è una vulnerabilità critica.

# ❌ Pattern pericoloso
on: pull_request_target
jobs:
  dangerous:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.ref }}  # PERICOLOSO: checkout della PR
      - run: npm install && npm run build  # Esegue codice non trusted

# ✅ Pattern sicuro: separare il checkout dal codice privilegiato
on: pull_request_target
jobs:
  safe:
    runs-on: ubuntu-latest
    steps:
      # Checkout del codice TRUSTED (base branch)
      - uses: actions/checkout@v4
      # Leggere solo metadata della PR, non eseguire il suo codice
      - name: Comment PR
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: 'CI passed!'
            })
```

### Dependency Review Action

```yaml
# Blocca PR che introducono dipendenze con vulnerabilità note o licenze non ammesse.
# Su repository privati richiede GitHub Code Security (o GHAS).
# `deny-licenses` è deprecato in favore di `allow-licenses` (non usarli insieme).
name: Dependency Review

on: pull_request

permissions:
  contents: read
  pull-requests: write

jobs:
  dependency-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Dependency Review
        uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: moderate
          allow-licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC
          comment-summary-in-pr: always
```

## GitHub Advanced Security (GHAS)

Le funzionalità di sicurezza sono gratuite sui repository pubblici. Sui repository privati sono a pagamento: da aprile 2025 GHAS è offerta come due prodotti acquistabili anche separatamente, **GitHub Secret Protection** (secret scanning, push protection) e **GitHub Code Security** (code scanning/CodeQL, dependency review, Copilot Autofix), fatturati per *active committer*. Su GHES la licenza GHAS resta unica.

### Code Scanning con CodeQL

```yaml
# .github/workflows/codeql.yml
name: CodeQL Analysis

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Ogni lunedì alle 06:00 UTC

permissions:
  actions: read
  contents: read
  security-events: write  # Necessario per upload risultati

jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        language: [java-kotlin, javascript-typescript, python]
        # Linguaggi supportati: actions (analizza i workflow stessi), c-cpp, csharp,
        # go, java-kotlin, javascript-typescript, python, ruby, rust, swift
        # (elenco in evoluzione: vedi docs CodeQL)

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v4
        with:
          languages: ${{ matrix.language }}
          # Query suite aggiuntiva a quella di default
          queries: security-extended  # security-and-quality | security-extended
          # Config inline: filtri sulle query
          config: |
            query-filters:
              - exclude:
                  id: java/unsafe-deserialization

      # Per linguaggi compilati (Java, C++, C#), build manuale
      - name: Build Java
        if: matrix.language == 'java-kotlin'
        run: mvn --batch-mode clean package -DskipTests

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v4
        with:
          category: "/language:${{ matrix.language }}"
          # Per default i risultati sono caricati su Code Scanning
```

### Secret Scanning e Push Protection

Sui repository pubblici secret scanning è attivo di default e la push protection è abilitata di default per gli utenti. Sui repository privati servono GitHub Secret Protection e l'abilitazione esplicita (consigliato: a livello org/enterprise tramite *security configurations*). La push protection **blocca il push** prima che il segreto entri nella storia; lo scanning classico segnala solo a posteriori.

**Configurazione push protection personalizzata:**

```yaml
# .github/secret_scanning.yml
paths-ignore:
  - "tests/fixtures/**"
  - "**/*.example"
  - "docs/**"

# Pattern custom (GHAS Enterprise)
# Non inclusi in questo file: configurati nelle org settings
```

**Bypass della push protection:** quando un push è bloccato, il messaggio di errore contiene un URL: da lì lo sviluppatore sceglie un motivo (`used in tests`, `false positive`, `I'll fix it later`) e rifà il push. Il bypass è tracciato nell'audit log e può richiedere l'approvazione di un reviewer (*delegated bypass*, configurabile a livello org).

**Chiudere un alert già aperto** (REST API, `PATCH`):

```bash
curl -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/my-org/my-repo/secret-scanning/alerts/42 \
  -d '{"state": "resolved", "resolution": "false_positive", "resolution_comment": "Test fixture, not a real secret"}'
```

### Dependabot — Security e Version Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  # Version updates per npm (i security updates sono un meccanismo separato,
  # attivato nelle impostazioni del repo, indipendente da questo file)
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Europe/Rome"
    open-pull-requests-limit: 10
    # `reviewers` è stato rimosso da Dependabot: usare CODEOWNERS per l'assegnazione
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "chore(deps)"
    groups:
      production-dependencies:
        dependency-type: "production"
      development-dependencies:
        dependency-type: "development"
        update-types:
          - "minor"
          - "patch"
    ignore:
      - dependency-name: "lodash"
        versions: ["4.x"]  # Blocca specifiche versioni

  # Aggiornamenti per Maven
  - package-ecosystem: "maven"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  # Aggiornamenti per GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    commit-message:
      prefix: "ci(deps)"

  # Aggiornamenti per Docker
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
```

## GitHub Enterprise Server (GHES)

GHES è l'istanza self-hosted di GitHub per organizzazioni che non possono usare GitHub.com per compliance (dati on-premises, air-gapped environments, ecc.).

**Differenze principali rispetto a GitHub.com:**

| Feature | GitHub.com | GHES |
|---------|-----------|------|
| GitHub-hosted runner | Disponibili | NON disponibili — solo self-hosted |
| GitHub Marketplace | Completo | Solo via GitHub Connect o `actions-sync` (mirror manuale) |
| GitHub Advanced Security | Disponibile (a pagamento) | Disponibile (licenza separata) |
| Actions version | Sempre aggiornata | Dipende dalla versione GHES installata |
| OIDC | Disponibile | Disponibile nelle versioni recenti (verificare la propria versione) |
| Nuove feature | Rilascio continuo | Arrivano con ritardo, nelle release GHES |

**Configurazione runner self-hosted per GHES:**

```bash
# URL è il FQDN dell'istanza GHES
./config.sh \
  --url https://github.mycompany.internal/my-org/my-repo \
  --token AABBCCDDEE... \
  --name ghes-runner-001

# Per ambienti air-gapped: scaricare le action runner tools manualmente
# e puntare il runner alla tool cache locale (usata da setup-node, setup-java, ...)
export AGENT_TOOLSDIRECTORY=/opt/runner-tool-cache
```

**Proxy per GHES in rete privata:**

```bash
# Configurare proxy HTTP per il runner (accesso a download.githubusercontent.com)
export https_proxy=http://proxy.mycompany.internal:8080
export no_proxy=github.mycompany.internal,registry.mycompany.internal
./config.sh --url https://github.mycompany.internal/...
```

## Governance e Audit Enterprise

### Policy a Livello Organizzazione

Le policy di organizzazione si configurano in `Settings > Actions > General` dell'organizzazione:

```
- Allow all actions and reusable workflows
- Allow only local actions and those from verified creators
- Allow only specific actions and reusable workflows
  → es. actions/*, aws-actions/*, docker/*
```

**Required workflows → Repository rulesets.** La vecchia feature "required workflows" (beta) è stata dismessa. Oggi si usa una **repository ruleset** a livello org con la regola *Require workflows to pass before merging*: si scelgono repository e branch target e il file di workflow (da un repo centrale, a un ref fissato). Il workflow gira sulle PR e il merge è bloccato finché non passa.

```yaml
# Nel repo centrale: workflow richiesto dalla ruleset.
# Deve avere il trigger pull_request (e merge_group se si usa la merge queue)
name: Required Security Scan
on:
  pull_request:
  merge_group:

permissions:
  contents: read

jobs:
  security-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # gitleaks scansiona la storia
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}  # richiesta per le org
      - name: License compliance check
        run: ./scripts/check-licenses.sh
```

### Audit Log Streaming

GitHub Enterprise Cloud supporta lo streaming dell'audit log verso sistemi esterni (Splunk, Datadog, Azure Event Hubs, Amazon S3, Google Cloud Storage, endpoint HTTPS generico). Si configura in *Enterprise settings > Audit log > Log streaming*: registrazioni di runner e modifiche alle policy arrivano al SIEM per correlazione e alerting. Per interrogazioni puntuali esiste la REST API `GET /orgs/{org}/audit-log?phrase=...`.

**Eventi chiave da monitorare** (nomi indicativi, verificare nella [documentazione degli eventi](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/audit-log-events-for-your-organization)):

```
org.register_self_hosted_runner      # Registrazione di un nuovo runner
org.remove_self_hosted_runner        # Rimozione di un runner
org.runner_group_created             # Creazione di un runner group
org.runner_group_runners_added       # Runner aggiunti a un gruppo
org.update_actions_secret            # Modifica di un secret di org
org.disable_two_factor_requirement   # Modifica requisiti 2FA
protected_branch.policy_override     # Bypass di una branch protection
workflows.completed_workflow_run     # Workflow completato
```

## Troubleshooting

### Scenario 1 — Runner offline o stuck in "Idle"

**Sintomo:** Il runner appare come offline nella UI GitHub oppure rimane in stato "Idle" indefinitamente senza eseguire job.

**Causa:** Il processo runner non riesce a raggiungere i server GitHub (problemi di rete, proxy, firewall), oppure il token di registrazione è scaduto (validità 1 ora).

**Soluzione:** Verificare la connettività e il processo runner; se il token è scaduto, rigenerare dalle Settings.

```bash
# Verificare connettività agli endpoint GitHub richiesti
curl -v https://api.github.com
curl -v https://pipelines.actions.githubusercontent.com   # lista host: docs 'Communicating with self-hosted runners'

# Controllare il processo runner e i log
sudo ./svc.sh status
tail -f _diag/Runner_*.log

# Se il runner è registrato ma non risponde, rimuoverlo e re-registrarlo
./config.sh remove --token <NEW_TOKEN>
./config.sh --url https://github.com/my-org/my-repo --token <NEW_TOKEN> --name my-runner

# Per ambienti con proxy, assicurarsi che le variabili siano esposte al servizio
sudo systemctl edit actions.runner.<scope>.<nome-runner>.service   # es. actions.runner.my-org-my-repo.my-runner.service
# Aggiungere nel file di override:
# [Service]
# Environment="https_proxy=http://proxy.internal:8080"
# Environment="no_proxy=github.mycompany.internal"
```

---

### Scenario 2 — ARC (Actions Runner Controller) non scala i runner

**Sintomo:** Job in coda su GitHub Actions, ma i Pod runner non vengono creati su Kubernetes. `minRunners: 0` e nessun pod attivo.

**Causa:** Problemi di autenticazione della GitHub App, RBAC insufficiente per l'operatore ARC, o namespace non configurato correttamente.

**Soluzione:** Verificare i Secret Kubernetes e i log dell'operatore ARC.

```bash
# Verificare lo stato del controller ARC
kubectl -n arc-systems get pods
kubectl -n arc-systems logs deploy/arc-gha-rs-controller   # nome = <release>-gha-rs-controller

# Il listener (un Pod per scale set) mostra se parla correttamente con GitHub
kubectl -n arc-systems get pods   # cercare il pod *-listener
kubectl -n arc-systems logs <pod-listener>

# Risorse ARC (CRD): AutoscalingRunnerSet, EphemeralRunnerSet, EphemeralRunner
kubectl -n arc-runners get autoscalingrunnerset
kubectl -n arc-runners describe autoscalingrunnerset
kubectl -n arc-runners get ephemeralrunners

# Il Secret esiste e ha le chiavi attese? (senza stampare la private key)
kubectl -n arc-runners get secret arc-github-secret -o json | jq '.data | keys'

# Verificare gli eventi Kubernetes per errori
kubectl -n arc-runners get events --sort-by='.lastTimestamp' | tail -20

# Reinstallare il chart se la configurazione è corrotta
helm upgrade arc-runner-set \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
  --namespace arc-runners \
  --values arc-runner-scale-set.yml
```

---

### Scenario 3 — Secret scanning blocca un push legittimo (falso positivo)

**Sintomo:** Git push respinto con messaggio "Push blocked due to detected secrets". Il contenuto segnalato è un valore di test, un placeholder, o una stringa che assomiglia a un segreto ma non lo è.

**Causa:** Il pattern di secret scanning di GitHub ha rilevato una corrispondenza su un valore che non è un segreto reale (es. fixture di test, documentazione, chiavi di esempio).

**Soluzione:** Bypassare il blocco tramite l'URL riportato nell'errore di push (con giustificazione) e, se il file è ricorrente, aggiungere il percorso a `paths-ignore`.

```bash
# Il push è rifiutato con un URL di bypass: aprirlo, scegliere il motivo, rifare `git push`
# (il bypass è registrato nell'audit log)

# Prevenire future segnalazioni: creare .github/secret_scanning.yml
# (se esiste già, modificarlo: `paths-ignore` va definito una sola volta)
cat > .github/secret_scanning.yml << 'EOF'
paths-ignore:
  - "tests/fixtures/**"
  - "**/*.example"
  - "docs/examples/**"
EOF

git add .github/secret_scanning.yml
git commit -m "chore: exclude test fixtures from secret scanning"
git push
```

---

### Scenario 4 — Job fallisce con "No runner matching labels found"

**Sintomo:** Il job rimane in coda con messaggio "Waiting for a runner to pick up this job" o fallisce immediatamente con "No runner matching the specified labels was found".

**Causa:** Nessun runner attivo ha le label richieste dal job, oppure il runner group non include il repository che ha avviato il workflow.

**Soluzione:** Verificare le label del runner, la disponibilità del runner group, e la configurazione di visibilità del gruppo.

```bash
# Elencare i runner dell'organizzazione e le loro label
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/orgs/my-org/actions/runners | \
  jq '.runners[] | {name: .name, status: .status, labels: [.labels[].name]}'

# Verificare i runner group e i repository autorizzati
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/orgs/my-org/actions/runner-groups | \
  jq '.runner_groups[] | {name: .name, visibility: .visibility, restricted_to_workflows: .restricted_to_workflows}'

# Aggiungere un repository a un runner group
curl -X PUT \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/orgs/my-org/actions/runner-groups/1/repositories/123456789

# Aggiungere label mancante a un runner esistente
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/orgs/my-org/actions/runners/42/labels \
  -d '{"labels": ["gpu", "large"]}'
```

---

## Relazioni

??? info "GitHub Actions — Workflow Avanzati"
    Matrix, reusable workflows, OIDC, composite actions, artifacts, environments.

    **Approfondimento completo →** [Workflow Avanzati](workflow-avanzati.md)

??? info "Supply Chain Security"
    SLSA, Sigstore/Cosign, SBOM, firma delle immagini container.

    **Approfondimento completo →** [Pipeline Security](../strategie/pipeline-security.md)

??? info "Jenkins Agent Infrastructure"
    Confronto con Jenkins agent management, controller/agent, Kubernetes plugin.

    **Approfondimento completo →** [Jenkins Agent Infrastructure](../jenkins/agent-infrastructure.md)

## Riferimenti

- [Hosting self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [Actions Runner Controller (ARC)](https://github.com/actions/actions-runner-controller)
- [ARC quickstart](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller/quickstart-for-actions-runner-controller)
- [Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [GitHub Advanced Security](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security)
- [CodeQL documentation](https://codeql.github.com/docs/)
- [Dependabot configuration](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
- [GitHub Enterprise Server docs](https://docs.github.com/en/enterprise-server)
- [Repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
