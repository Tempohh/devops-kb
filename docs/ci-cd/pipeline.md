---
title: "CI/CD Pipeline — Fondamentali e Architettura"
slug: pipeline
category: ci-cd
tags: [ci-cd, pipeline, continuous-integration, continuous-delivery, continuous-deployment, quality-gates, artifacts, environments, stages, jobs]
search_keywords: [CI/CD pipeline, continuous integration, continuous delivery, continuous deployment, pipeline stages, pipeline jobs, quality gate, artifact, build pipeline, deployment pipeline, pipeline as code, pipeline design, multi-stage pipeline, pipeline environment, pipeline trigger, webhook trigger, cron pipeline, pipeline artifact registry, pipeline cache, pipeline optimization, pipeline parallelism, pipeline matrix, shift left security, supply chain security, SBOM, SLSA, attestation, software delivery pipeline, DevOps pipeline, release pipeline, GitOps pipeline, environment promotion, deploy gate, approval gate, rollback pipeline, pipeline observability, pipeline metrics, mean time to recovery, DORA, lead time for changes, change failure rate, deployment frequency]
parent: ci-cd/_index
related: [ci-cd/jenkins/pipeline-fundamentals, ci-cd/strategie/deployment-strategies, ci-cd/strategie/pipeline-security, ci-cd/testing/contract-testing, iac/terraform/testing]
official_docs: https://docs.gitlab.com/ee/ci/pipelines/
status: complete
difficulty: intermediate
last_updated: 2026-03-26
---

# CI/CD Pipeline — Fondamentali e Architettura

## Panoramica

Una **CI/CD pipeline** è un sistema automatizzato di passaggi ordinati che trasformano un commit Git in software in esecuzione su produzione. Il suo scopo è rendere il rilascio del software un processo **ripetibile, verificabile e a basso rischio** — spostando il feedback il più vicino possibile al momento della scrittura del codice (principio *shift-left*). Una pipeline ben progettata elimina i rilasci manuali, impone quality gate non bypassabili, e produce un audit trail completo di ogni modifica. La pipeline *è* codice: vive nel repository insieme al software che gestisce, si versiona, si review, e si testa come qualsiasi altro file.

!!! warning "Pipeline non significa Deploy continuo"
    CI (Continuous Integration) e CD (Continuous Delivery) sono distinti. CI è automatica per definizione. CD può includere un *gate manuale* prima del deploy in produzione — e spesso dovrebbe. Continuous **Deployment** (senza gate manuale) è appropriato solo quando la test coverage e il monitoring sono maturi.

## Concetti Chiave

### Anatomia di una Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRIGGER                                                             │
│  • Push su branch    • Pull Request    • Tag Git    • Cron/Schedule  │
│  • Webhook esterno   • Trigger manuale • Upstream pipeline           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│  STAGE 1 — Source & Build                                            │
│  Job: checkout → compile → package → publish artifact               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ artifact verificato
┌──────────────────────────────▼──────────────────────────────────────┐
│  STAGE 2 — Verify (parallelo)                                        │
│  Job A: unit tests + coverage                                        │
│  Job B: static analysis (SAST, linting)                              │
│  Job C: dependency vulnerability scan                                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ quality gate superato
┌──────────────────────────────▼──────────────────────────────────────┐
│  STAGE 3 — Integration (ambiente effimero)                           │
│  Job: spin-up env → integration tests → E2E tests → teardown        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│  STAGE 4 — Package & Sign                                            │
│  Job: build container image → scan → sign (cosign) → push registry  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│  STAGE 5 — Deploy Staging → [gate manuale] → Deploy Production       │
│  Job: helm upgrade staging → smoke test → approval → prod deploy     │
└─────────────────────────────────────────────────────────────────────┘
```

### Terminologia Core

| Termine | Definizione |
|---------|-------------|
| **Stage** | Gruppo logico di job che condividono lo stesso obiettivo (Build, Test, Deploy) |
| **Job** | Unità atomica di esecuzione — viene eseguita su un runner/agent |
| **Runner/Agent** | Processo che esegue i job; può essere ephemeral (pod K8s) o persistente |
| **Artifact** | File prodotto da un job e condiviso con job successivi (JAR, container image, report) |
| **Quality Gate** | Condizione booleana che blocca la pipeline se non soddisfatta |
| **Environment** | Target di deployment (dev, staging, prod); può avere regole di protezione |
| **Trigger** | Evento che avvia la pipeline (push, PR, webhook, schedule) |
| **Pipeline as Code** | La definizione della pipeline è un file nel repository (`Jenkinsfile`, `.gitlab-ci.yml`, `workflow.yml`) |

### Flusso degli Artefatti

```
Source Code
    │
    ▼  (build)
Compiled Binary / Package       ← artefatto immutabile
    │
    ▼  (containerize)
Container Image :sha256-abc123  ← tagged con commit SHA
    │
    ├─► Registry (dev)          ← promoted dopo integration test
    ├─► Registry (staging)      ← promoted dopo approval
    └─► Registry (prod)         ← promoted, firmato e attestato
```

**Regola fondamentale:** l'artefatto che va in produzione è **identico** a quello testato in staging. Non si ricompila tra ambienti — si *promuove* la stessa immagine.

## Architettura / Come Funziona

### Tipi di Trigger

```yaml
# Esempio GitHub Actions — trigger multipli
on:
  # PR: pipeline di validazione (build + test, NO deploy)
  pull_request:
    branches: [main, 'release/**']
    paths-ignore: ['docs/**', '*.md']

  # Push su main: pipeline completa con deploy staging
  push:
    branches: [main]

  # Tag semantico: pipeline di release con deploy production
  push:
    tags: ['v[0-9]+.[0-9]+.[0-9]+']

  # Nightly: pipeline pesante con integration test e security scan
  schedule:
    - cron: '0 2 * * 1-5'   # lun-ven alle 02:00

  # Manuale con parametri
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, production]
      dry_run:
        type: boolean
        default: false
```

### Pipeline Parallelism e DAG

Le pipeline moderne supportano **grafi aciclici diretti (DAG)** invece di semplici sequenze lineari. I job senza dipendenze vengono eseguiti in parallelo, riducendo il tempo totale.

```
           ┌──── job: unit-tests ────┐
           │                         │
trigger ───┤──── job: lint ──────────┼──── job: build-image ──── job: deploy
           │                         │
           └──── job: sast ──────────┘

Senza DAG (lineare): 10 + 8 + 6 + 5 + 3 = 32 min
Con DAG (parallelo): max(10,8,6) + 5 + 3 = 18 min  ← 44% più veloce
```

```yaml
# GitLab CI — needs: definisce il DAG
unit-tests:
  stage: test

lint:
  stage: test

sast:
  stage: test

build-image:
  stage: package
  needs: [unit-tests, lint, sast]   # parte solo quando questi 3 finiscono

deploy-staging:
  stage: deploy
  needs: [build-image]              # non aspetta altri job di test già completati
```

### Environment Promotion Pattern

```
dev branch ──► pipeline PR ──► artifact :pr-123
                                    │
main branch ──► pipeline CI ──► artifact :sha-abc123
                                    │
                              [quality gate]
                                    │
                              staging deploy
                                    │
                              [smoke tests]
                                    │
                              [manual approval]
                                    │
                              prod deploy ──► artifact :v1.2.3 (same SHA)
```

## Configurazione & Pratica

### 1. Struttura Pipeline Multi-Ambiente (GitHub Actions)

```yaml
# .github/workflows/pipeline.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ── Stage 1: Build ────────────────────────────────────────────────
  build:
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
      image-digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=,suffix=,format=short
            type=ref,event=branch
            type=semver,pattern={{version}}

      - name: Build and push
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ── Stage 2: Test (parallelo) ─────────────────────────────────────
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm test -- --coverage
      - uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage/

  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Semgrep
        uses: semgrep/semgrep-action@v1
        with:
          config: >-
            p/default
            p/owasp-top-ten
            p/secrets

  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy filesystem scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'HIGH,CRITICAL'
          exit-code: '1'

  # ── Stage 3: Quality Gate ─────────────────────────────────────────
  quality-gate:
    needs: [build, unit-tests, sast, dependency-scan]
    runs-on: ubuntu-latest
    steps:
      - name: All checks passed
        run: echo "Quality gate passed — proceeding to deploy"

  # ── Stage 4: Deploy Staging ───────────────────────────────────────
  deploy-staging:
    needs: [quality-gate]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.myapp.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: |
          helm upgrade --install myapp ./helm/myapp \
            --namespace staging \
            --set image.tag=${{ needs.build.outputs.image-tag }} \
            --atomic --timeout 5m

  # ── Stage 5: Deploy Production (gate manuale) ─────────────────────
  deploy-production:
    needs: [deploy-staging]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: production      # Environment con required_reviewers configurato in GitHub
      url: https://myapp.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to production
        run: |
          helm upgrade --install myapp ./helm/myapp \
            --namespace production \
            --set image.tag=${{ needs.build.outputs.image-tag }} \
            --atomic --timeout 10m --wait
```

### 2. Quality Gate con SonarQube

```yaml
# Snippet: Quality Gate SonarQube in GitHub Actions
- name: SonarQube Scan
  uses: SonarSource/sonarqube-scan-action@master
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}

- name: SonarQube Quality Gate check
  id: sonarqube-quality-gate-check
  uses: SonarSource/sonarqube-quality-gate-action@master
  timeout-minutes: 5
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}

# Il job fallisce se Quality Gate non è superato
- name: "Show Quality Gate Status"
  run: echo "The Quality Gate status is ${{ steps.sonarqube-quality-gate-check.outputs.quality-gate-status }}"
```

```properties
# sonar-project.properties — configurazione Quality Gate
sonar.projectKey=myapp
sonar.sources=src
sonar.tests=src
sonar.test.inclusions=**/*.test.ts,**/*.spec.ts
sonar.coverage.exclusions=**/*.test.ts,**/mocks/**

# Soglie Quality Gate (configurate in SonarQube UI o via API)
# Coverage nuove linee: >= 80%
# Duplicazioni nuove linee: <= 3%
# Maintainability Rating: A
# Reliability Rating: A
# Security Rating: A
```

### 3. Pipeline Cache Strategy

La cache riduce drasticamente i tempi eliminando il re-download di dipendenze.

```yaml
# GitHub Actions — cache multi-livello
- name: Cache node_modules
  uses: actions/cache@v4
  with:
    path: |
      ~/.npm
      node_modules
    # Cache key: OS + lockfile hash → invalida quando cambiano le dipendenze
    key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-node-      # fallback: ultima cache valida per questo OS

# Docker layer cache (BuildKit)
- name: Build con cache Docker
  uses: docker/build-push-action@v5
  with:
    cache-from: type=gha          # legge da GitHub Actions Cache
    cache-to: type=gha,mode=max   # scrive tutti i layer (max = più storage, più hit)
```

```yaml
# GitLab CI — cache per job
cache:
  key:
    files:
      - package-lock.json       # invalida se lockfile cambia
  paths:
    - node_modules/
    - .npm/
  policy: pull-push             # pull all'inizio, push alla fine del job

# Cache solo in lettura (CI jobs downstream)
test:
  cache:
    policy: pull                # non aggiorna la cache, solo legge
```

### 4. Matrix Build — Test Cross-Versione

```yaml
# GitHub Actions — matrix su versioni Node e OS
jobs:
  test-matrix:
    strategy:
      fail-fast: false           # continua anche se una cella fallisce
      matrix:
        node: ['18', '20', '22']
        os: [ubuntu-latest, windows-latest, macos-latest]
        exclude:
          # Node 18 non testato su macOS per limiti di licenza
          - os: macos-latest
            node: '18'
        include:
          # Aggiungi variabile extra solo per Node 22
          - node: '22'
            experimental: true

    runs-on: ${{ matrix.os }}
    continue-on-error: ${{ matrix.experimental || false }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
      - run: npm ci
      - run: npm test
```

### 5. Artifact Signing e SBOM (Supply Chain Security)

```bash
# Firma container image con cosign (keyless via OIDC)
# In GitHub Actions, usa il token OIDC di GitHub come identità

# Installazione cosign
curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64"
chmod +x cosign-linux-amd64
mv cosign-linux-amd64 /usr/local/bin/cosign

# Firma dell'immagine (keyless — identità dal token OIDC CI)
cosign sign --yes $REGISTRY/$IMAGE@$DIGEST

# Verifica firma
cosign verify \
  --certificate-identity-regexp="https://github.com/myorg/myapp" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  $REGISTRY/$IMAGE:latest
```

```yaml
# Generazione SBOM con syft
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}
    format: spdx-json
    output-file: sbom.spdx.json

- name: Attach SBOM to image
  run: |
    cosign attest --yes \
      --predicate sbom.spdx.json \
      --type spdxjson \
      ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build.outputs.digest }}
```

## Best Practices

!!! tip "Pipeline veloce = pipeline usata"
    Una pipeline che supera i 15 minuti viene aggirata. Obiettivo: feedback CI entro 5-10 minuti su PR. Usa parallelismo, cache aggressiva, e sposta i test lenti in pipeline notturne.

### Design Principi

**1. Fail fast**: metti i check più veloci prima. Lint (30 sec) deve fallire prima dei test di integrazione (5 min).

**2. Artefatto immutabile**: mai ricompilare tra ambienti. Build una volta, promuovi ovunque. Questo garantisce che staging e prod eseguano esattamente lo stesso binario.

**3. Pipeline as Code**: la pipeline vive nel repo, si versiona, si review come il codice applicativo. Cambiare la pipeline senza review è pericoloso quanto cambiare codice critico senza review.

**4. Secrets management**: nessun secret in chiaro nel codice pipeline. Usare il secret store del provider CI/CD (GitHub Encrypted Secrets, GitLab CI Variables Protected) o un vault esterno (HashiCorp Vault, AWS Secrets Manager).

**5. Idempotenza**: ogni step della pipeline deve produrre lo stesso risultato se eseguito più volte. Evitare side-effect accumulativi.

```yaml
# Anti-pattern: secret nel codice pipeline
env:
  API_KEY: "sk-abc123xyz"        # ❌ MAI

# Pattern corretto: secret dal store CI
env:
  API_KEY: ${{ secrets.API_KEY }}  # ✅
```

### Pipeline Branching Strategy

```
feature/* ──► pipeline: build + unit tests (veloce, 3-5 min)
                         NO deploy

develop   ──► pipeline: build + unit + integration + deploy dev (10-15 min)

main      ──► pipeline: completa + deploy staging + approval + deploy prod (20-30 min)

v*.*.*    ──► pipeline: release completa + sign + SBOM + changelog + GitHub Release
```

!!! warning "Branch protection rules"
    Proteggere `main` con: pipeline CI verde obbligatoria + almeno 1 reviewer + no force push. Senza queste regole, la pipeline è opzionale nella pratica.

### Monitoring della Pipeline

| Metrica | Target Elite | Come Misurare |
|---------|-------------|---------------|
| **Pipeline duration (CI)** | < 10 min | Durata media ultima settimana |
| **Pipeline success rate** | > 95% | (build verdi / build totali) × 100 |
| **Lead Time for Changes** | < 1 ora | Commit merge → deploy prod |
| **Change Failure Rate** | < 5% | Deploy che causano rollback / deploy totali |
| **Flaky test rate** | < 2% | Test che cambiano risultato senza modifiche codice |

```bash
# GitHub CLI — statistiche pipeline (ultimi 30 giorni)
gh run list \
  --workflow=pipeline.yml \
  --limit=100 \
  --json status,conclusion,createdAt,updatedAt \
  --jq 'group_by(.conclusion) | map({(.[0].conclusion): length}) | add'
```

## Troubleshooting

### Problema: Pipeline lenta — supera 20 minuti

**Sintomo:** La pipeline impiega oltre 20 minuti, gli sviluppatori smettono di aspettare il feedback.

**Causa comune:** Step sequenziali che potrebbero essere paralleli, cache non configurata, runner lenti, test di integrazione in CI normale.

**Soluzione:**
```yaml
# 1. Identificare i job più lenti
# GitHub Actions: tab "Actions" → seleziona run → click su ogni job

# 2. Abilitare cache npm/Maven/pip
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}

# 3. Spostare integration test su schedule notturno
on:
  schedule:
    - cron: '0 2 * * *'    # solo di notte
  push:
    branches: [main]        # build normale (senza integration test)

# 4. Parallelizzare test con matrix o split
jobs:
  test:
    strategy:
      matrix:
        shard: [1, 2, 3, 4]   # 4 shard paralleli
    steps:
      - run: npx jest --shard=${{ matrix.shard }}/4
```

---

### Problema: Pipeline "flaky" — fallisce in modo intermittente

**Sintomo:** La pipeline fallisce su step come `docker pull`, `npm ci`, o test di integrazione senza modifiche al codice.

**Causa:** Race condition nei test, dipendenze di rete instabili, risorse runner esaurite.

**Soluzione:**
```yaml
# Retry automatico su step di rete
- name: Pull base image (con retry)
  uses: nick-fields/retry@v3
  with:
    timeout_minutes: 10
    max_attempts: 3
    command: docker pull node:20-alpine

# Timeout esplicito per evitare hang infiniti
- name: Integration tests
  timeout-minutes: 15
  run: npm run test:integration
```

```bash
# Identificare test flaky con reruns
# Jest — riprova test falliti
npx jest --testPathPattern="integration" --retries=2

# Pytest — riprova test falliti
pytest --reruns=2 --reruns-delay=5
```

---

### Problema: Artefatto non trovato nello stage successivo

**Sintomo:** `Error: artifact 'build-output' not found` in un job downstream.

**Causa:** L'artefatto viene caricato con un nome diverso, o il job upstream è fallito silenziosamente, o l'artefatto è scaduto.

**Soluzione:**
```yaml
# Upload con nome esplicito
- uses: actions/upload-artifact@v4
  with:
    name: build-output          # nome univoco e stabile
    path: dist/
    retention-days: 7
    if-no-files-found: error    # ← fallisce subito se dist/ è vuota

# Download con dipendenza esplicita dal job upstream
deploy:
  needs: [build]                # garantisce che build sia completato
  steps:
    - uses: actions/download-artifact@v4
      with:
        name: build-output
        path: dist/
```

---

### Problema: Deploy fallisce ma l'immagine è stata pubblicata

**Sintomo:** Il container registry contiene l'immagine, ma `helm upgrade` fallisce → rimane in stato inconsistente.

**Causa:** Il deploy è avvenuto dopo il push dell'immagine senza atomicità.

**Soluzione:**
```bash
# Usare --atomic in helm: rollback automatico se il deploy fallisce
helm upgrade --install myapp ./helm/myapp \
  --namespace production \
  --set image.tag=$IMAGE_TAG \
  --atomic \          # ← rollback automatico se i pod non partono
  --timeout 10m \
  --wait

# Verificare rollout con kubectl
kubectl rollout status deployment/myapp -n production --timeout=5m
# In caso di fallimento:
kubectl rollout undo deployment/myapp -n production
```

---

### Problema: Secret esposto nei log della pipeline

**Sintomo:** Il log della pipeline mostra il valore di un token o password.

**Causa:** Il secret viene stampato da un comando (es. `echo $SECRET` o errore verbose).

**Soluzione:**
```yaml
# GitHub Actions — mascherare secret dinamici
- name: Mask dynamic secret
  run: echo "::add-mask::${{ steps.get-token.outputs.token }}"

# Non usare mai `set -x` in script che usano secret:
# set -x stampa ogni comando con i valori espansi
run: |
  # set -x  ← COMMENTATO se ci sono secret
  helm upgrade --install myapp ./helm \
    --set credentials.token=${{ secrets.API_TOKEN }}
```

## Relazioni

??? info "Jenkins Pipeline — Implementazione Specifica"
    Jenkins implementa CI/CD pipeline con syntax Declarative o Scripted Groovy. Offre il maggiore controllo ma richiede infrastruttura self-managed. I concetti di stage, quality gate e artifact si mappano direttamente sui concetti generali di questa pagina.

    **Approfondimento completo →** [Jenkins Pipeline Fondamentali](jenkins/pipeline-fundamentals.md)

??? info "Deployment Strategies — Blue/Green, Canary, Rolling"
    La pipeline si occupa di *costruire* e *validare* il software; le strategie di deployment definiscono *come* viene messo in produzione. Progressive delivery (canary, blue/green) va integrato come ultimo stage della pipeline.

    **Approfondimento completo →** [Deployment Strategies](strategie/deployment-strategies.md)

??? info "Pipeline Security — SBOM, SLSA, Sigstore"
    Supply chain security, firma degli artefatti, attestazioni SLSA, e policy enforcement (OPA Gatekeeper) sono estensioni della pipeline standard per ambienti con requisiti di compliance elevati.

    **Approfondimento completo →** [Pipeline Security](strategie/pipeline-security.md)

??? info "Terraform Testing — Quality Gate IaC nella Pipeline"
    Il testing dell'infrastruttura Terraform segue la stessa piramide di qualità del software applicativo: static analysis, policy check, integration test. I check tflint/checkov vanno integrati come stage bloccanti nella pipeline CI.

    **Approfondimento completo →** [Terraform Testing](../iac/terraform/testing.md)

## Riferimenti

- [GitHub Actions — Documentazione ufficiale](https://docs.github.com/en/actions)
- [GitLab CI/CD — Pipeline reference](https://docs.gitlab.com/ee/ci/pipelines/)
- [DORA Metrics — Come misurarli](https://dora.dev/guides/dora-metrics-four-keys/)
- [SLSA Framework — Supply-chain Levels for Software Artifacts](https://slsa.dev/)
- [Sigstore / cosign — Artifact signing](https://docs.sigstore.dev/cosign/overview/)
- [OpenSSF Scorecard — Valutazione sicurezza pipeline](https://github.com/ossf/scorecard)
- [Argo Workflows — Pipeline DAG Kubernetes-native](https://argo-workflows.readthedocs.io/)
- [Tekton — Pipeline framework Kubernetes-native](https://tekton.dev/docs/)
