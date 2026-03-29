---
title: "GitHub Actions — Enterprise & Self-Hosted Runners"
slug: enterprise
category: ci-cd
tags: [github-actions, enterprise, self-hosted-runners, security, arc, github-enterprise]
search_keywords: [github actions self hosted runner, ARC actions runner controller, github enterprise server, runner groups, github actions security hardening, github actions audit log, github advanced security, codeql, dependabot, secret scanning, push protection]
parent: ci-cd/github-actions/_index
related: [ci-cd/github-actions/workflow-avanzati, ci-cd/jenkins/agent-infrastructure, security/supply-chain]
official_docs: https://docs.github.com/en/actions/hosting-your-own-runners
status: complete
difficulty: expert
last_updated: 2026-03-28
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
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# 2. Configurare il runner (token generato in Settings > Actions > Runners)
./config.sh \
  --url https://github.com/my-org/my-repo \
  --token AABBCCDDEE... \
  --name my-runner-001 \
  --labels linux,x64,production,large \
  --work /tmp/runner-work \
  --runnergroup "Production Runners"

# 3. Runner ephemerali (best practice sicurezza): si registra e poi viene rimosso
./config.sh \
  --url https://github.com/my-org \
  --token AABBCCDDEE... \
  --ephemeral \   # Il runner si deregistra dopo aver completato 1 job
  --name ephemeral-runner-$RANDOM

# 4. Avviare come servizio (Linux)
sudo ./svc.sh install
sudo ./svc.sh start

# 5. Oppure avviare in foreground (per container)
./run.sh
```

!!! warning "Runner Ephemeral — Sicurezza"
    I runner ephemerali (`--ephemeral`) sono fondamentali per ambienti multi-tenant. Un runner persistente che esegue job di repository diversi rischia contaminazione tra job (file temporanei, variabili d'ambiente, credenziali in cache). Con `--ephemeral`, il runner termina dopo 1 job e viene ricreato pulito.

### Dockerfile per Runner Containerizzato

```dockerfile
FROM ubuntu:22.04

ARG RUNNER_VERSION=2.311.0
ARG TARGETPLATFORM

RUN apt-get update && apt-get install -y \
    curl \
    git \
    jq \
    libicu70 \
    openssl \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Utente non-root per il runner
RUN useradd -m runner && echo "runner ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

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

ARC è un operatore Kubernetes che gestisce runner GitHub Actions scalabili automaticamente. I runner vengono creati come Pod Kubernetes in risposta ai job in coda.

### Installazione con Helm

```bash
# Aggiungere il Helm repository di ARC
helm repo add actions-runner-controller \
  https://actions-runner-controller.github.io/actions-runner-controller
helm repo update

# Installare ARC con GitHub App authentication (raccomandato)
helm install arc \
  --namespace arc-systems \
  --create-namespace \
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller \
  --version 0.9.3
```

### RunnerScaleSet — Runner Autoscalanti

```yaml
# arc-runner-scale-set.yml
# Installa con: helm install arc-runner-set \
#   --namespace arc-runners \
#   --create-namespace \
#   oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set \
#   --values arc-runner-scale-set.yml
githubConfigUrl: "https://github.com/my-org/my-repo"
githubConfigSecret: "arc-github-secret"  # Secret con GitHub App credentials

minRunners: 0       # Scale to zero quando non ci sono job
maxRunners: 20      # Massimo 20 runner concorrenti

runnerScaleSetName: "arc-runner-k8s"

# Configurazione del Pod runner
template:
  spec:
    serviceAccountName: arc-runner
    initContainers:
      - name: init-dind-externals
        image: ghcr.io/actions/actions-runner:latest
        command: ["cp", "-r", "-v", "/home/runner/externals/.", "/home/runner/tmpDir/"]
        volumeMounts:
          - name: dind-externals
            mountPath: /home/runner/tmpDir
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        command: ["/home/runner/run.sh"]
        env:
          - name: DOCKER_HOST
            value: unix:///var/run/docker.sock
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2"
            memory: "4Gi"
        volumeMounts:
          - name: work
            mountPath: /home/runner/_work
          - name: dind-sock
            mountPath: /var/run
      - name: dind
        image: docker:24-dind
        args:
          - dockerd
          - --host=unix:///var/run/docker.sock
          - --group=$(DOCKER_GROUP_GID)
        env:
          - name: DOCKER_GROUP_GID
            value: "123"
        securityContext:
          privileged: true
        volumeMounts:
          - name: work
            mountPath: /home/runner/_work
          - name: dind-sock
            mountPath: /var/run
          - name: dind-externals
            mountPath: /home/runner/externals
    volumes:
      - name: work
        emptyDir: {}
      - name: dind-sock
        emptyDir: {}
      - name: dind-externals
        emptyDir: {}

# Configurazione autoscaling
containerMode:
  type: dind
```

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
# ❌ Vulnerabile: tag può essere modificato (tag hijacking)
- uses: actions/checkout@v4

# ✅ Sicuro: SHA immutabile, impossibile cambiare il codice senza modificare il workflow
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
- uses: actions/setup-java@99b8673ff64fbf99d8d7b505bd5d0459996d8ad  # v4.2.1
- uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502  # v4.0.2

# Tool per aggiornare automaticamente i SHA:
# - Dependabot (nativo GitHub)
# - Renovate (più configurabile)
# - pin-github-action CLI (github.com/mheap/pin-github-action)
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
# Blocca PR che introducono dipendenze con vulnerabilità note
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
          deny-licenses: LGPL-2.0, BSD-2-Clause
          comment-summary-in-pr: always
```

## GitHub Advanced Security (GHAS)

GHAS è disponibile per repository pubblici (gratis) e per organizzazioni GitHub Enterprise/Team (a pagamento). Include Code scanning, Secret scanning e Dependency review.

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
        # Linguaggi supportati: c-cpp, csharp, go, java-kotlin,
        # javascript-typescript, python, ruby, swift

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
          # Configurazione query suite
          queries: security-extended  # security-and-quality | security-extended | default
          # Query custom aggiuntive
          config: |
            query-filters:
              - exclude:
                  id: java/unsafe-deserialization

      # Per linguaggi compilati (Java, C++, C#), build manuale
      - name: Build Java
        if: matrix.language == 'java-kotlin'
        run: mvn --batch-mode clean package -DskipTests

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
          upload: true   # Upload a GitHub Code Scanning
          output: sarif-results
```

### Secret Scanning e Push Protection

Secret scanning è attivo automaticamente su tutti i repository GitHub (push protection deve essere abilitato separatamente).

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

**Bypassare un falso positivo (con audit log):**

```bash
# Quando push protection blocca un push che è un falso positivo,
# il developer può bypassare con giustificazione tramite UI GitHub
# oppure usando l'API:
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/my-org/my-repo/secret-scanning/alerts/42/resolution \
  -d '{"resolution": "false_positive", "resolution_comment": "Test fixture, not a real secret"}'
```

### Dependabot — Security e Version Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  # Aggiornamenti di sicurezza per npm
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Europe/Rome"
    open-pull-requests-limit: 10
    reviewers:
      - "my-org/security-team"
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
| GitHub Marketplace | Completo | Limitato (solo actions con sync) |
| GitHub Advanced Security | Disponibile (a pagamento) | Disponibile (licenza separata) |
| Actions version | Sempre aggiornata | Dipende dalla versione GHES installata |
| OIDC | Disponibile | Disponibile dalla v3.8+ |
| Copilot | Disponibile | Non disponibile (cloud only) |

**Configurazione runner self-hosted per GHES:**

```bash
# URL è il FQDN dell'istanza GHES
./config.sh \
  --url https://github.mycompany.internal/my-org/my-repo \
  --token AABBCCDDEE... \
  --name ghes-runner-001

# Per ambienti air-gapped: scaricare le action runner tools manualmente
# e configurare ACTIONS_RUNNER_TOOL_CACHE
export ACTIONS_RUNNER_TOOL_CACHE=/opt/runner-tool-cache
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

**Required Workflows (GitHub Enterprise):**

```yaml
# I required workflows si configurano a livello organizzazione via API
# e vengono eseguiti SEMPRE su tutti i repository dell'org

# Esempio: workflow di compliance che deve passare su ogni PR
# Configurato in: .github/workflows/required-security-scan.yml
# Nel repository .github dell'organizzazione
name: Required Security Scan (Org-wide)

on:
  pull_request:
    branches: ['**']

jobs:
  security-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check secrets baseline
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: License compliance check
        run: ./scripts/check-licenses.sh
```

### Audit Log Streaming

GitHub Enterprise supporta lo streaming del audit log verso sistemi SIEM esterni:

```bash
# Configurare audit log streaming via API (GitHub Enterprise)
curl -X PUT \
  -H "Authorization: Bearer $ENTERPRISE_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/enterprises/my-enterprise/audit-log/streaming \
  -d '{
    "enabled": true,
    "vendor_name": "splunk",
    "url": "https://splunk.mycompany.internal:8088/services/collector",
    "token": "SPLUNK_HEC_TOKEN",
    "content_type": "application/x-ndjson"
  }'
```

**Eventi chiave da monitorare nel audit log:**

```
org.actions_runner_registration      # Registrazione di un nuovo runner
org.actions_runner_group_created     # Creazione di un runner group
org.disable_two_factor_requirement   # Modifica requisiti 2FA
repo.actions_allow_force_pushes      # Cambio policy di force push
workflow_job.in_progress             # Job avviato (con runner info)
workflow_run.completed               # Workflow completato (con status)
secret.access                        # Secret acceduto (GHES Enterprise)
```

## Troubleshooting

### Scenario 1 — Runner offline o stuck in "Idle"

**Sintomo:** Il runner appare come offline nella UI GitHub oppure rimane in stato "Idle" indefinitamente senza eseguire job.

**Causa:** Il processo runner non riesce a raggiungere i server GitHub (problemi di rete, proxy, firewall), oppure il token di registrazione è scaduto (validità 1 ora).

**Soluzione:** Verificare la connettività e il processo runner; se il token è scaduto, rigenerare dalle Settings.

```bash
# Verificare connettività agli endpoint GitHub richiesti
curl -v https://api.github.com
curl -v https://pipelines.actions.githubusercontent.com

# Controllare il processo runner e i log
sudo ./svc.sh status
tail -f _diag/Runner_*.log

# Se il runner è registrato ma non risponde, rimuoverlo e re-registrarlo
./config.sh remove --token <NEW_TOKEN>
./config.sh --url https://github.com/my-org/my-repo --token <NEW_TOKEN> --name my-runner

# Per ambienti con proxy, assicurarsi che le variabili siano esposte al servizio
sudo systemctl edit actions.runner.my-org.my-runner.service
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
kubectl -n arc-systems logs deploy/arc-gha-runner-scale-set-controller

# Verificare la RunnerScaleSet
kubectl -n arc-runners get runnerscaleset
kubectl -n arc-runners describe runnerscaleset arc-runner-k8s

# Controllare che il Secret con le credenziali GitHub App sia corretto
kubectl -n arc-runners get secret arc-github-secret -o jsonpath='{.data}' | base64 -d

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

**Soluzione:** Bypassare il blocco tramite UI GitHub con giustificazione, oppure via API, e aggiungere il percorso ai path-ignore.

```bash
# Bypass via API con giustificazione (registrato nell'audit log)
curl -X PATCH \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/my-org/my-repo/secret-scanning/alerts/42 \
  -d '{"state": "dismissed", "resolution": "false_positive", "resolution_comment": "Test fixture - not a real credential"}'

# Prevenire future segnalazioni: aggiungere il path a .github/secret_scanning.yml
cat >> .github/secret_scanning.yml << 'EOF'
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
- [Required workflows (Enterprise)](https://docs.github.com/en/actions/using-workflows/required-workflows)
