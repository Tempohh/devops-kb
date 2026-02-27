---
title: "Strategie CI/CD"
slug: strategie-cicd
category: ci-cd
tags: [cicd-strategy, deployment-strategy, pipeline-design, devsecops]
search_keywords: [cicd strategies, deployment patterns, pipeline design, shift left security, devsecops, continuous deployment, continuous delivery, feature flags, release management]
parent: ci-cd/_index
related: [ci-cd/strategie/deployment-strategies, ci-cd/strategie/pipeline-security, ci-cd/jenkins/enterprise-patterns, ci-cd/gitops/argocd]
official_docs: https://dora.dev/
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# Strategie CI/CD

## Panoramica

Le strategie CI/CD definiscono come le organizzazioni strutturano i processi di integrazione, delivery e deployment del software. La scelta della strategia impatta direttamente sulla frequenza di rilascio, sulla qualità del software e sulla capacità di rispondere ai feedback degli utenti. I DORA (DevOps Research and Assessment) metrics forniscono un framework empirico per misurare e migliorare queste performance. Una pipeline CI/CD efficace non è solo un insieme di tool, ma riflette una filosofia di design: fail fast, shift left, immutabilità degli artefatti, idempotenza dei deployment.

## DORA Metrics — Misurare la Performance DevOps

Le 4 metriche DORA, definite dal team di ricerca di Google/DORA, sono i predittori più affidabili di performance organizzativa nel software delivery.

### Le 4 Metriche Chiave

| Metrica | Descrizione | Elite | High | Medium | Low |
|---------|-------------|-------|------|--------|-----|
| **Deployment Frequency** | Quante volte si fa deploy in produzione | Su richiesta (più volte/giorno) | 1/giorno – 1/settimana | 1/settimana – 1/mese | < 1/mese |
| **Lead Time for Changes** | Dal commit al deploy in produzione | < 1 ora | 1 giorno – 1 settimana | 1 settimana – 1 mese | > 1 mese |
| **Change Failure Rate** | % deploy che causano degradazione | 0-5% | 5-10% | 10-15% | > 15% |
| **Time to Restore Service** | Tempo per ripristinare dopo un incidente | < 1 ora | < 1 giorno | < 1 giorno | > 1 settimana |

### Come Misurare le Metriche

```python
# Esempi di calcolo (pseudo-codice / query Prometheus/Datadog)

# Deployment Frequency: deploy per giorno (media 30 giorni)
# Query Prometheus (da deployment events)
deployment_frequency = (
    count(deployments WHERE environment="production" AND timestamp > 30d ago)
    / 30
)

# Lead Time: differenza tra commit time e deploy time
# Richiede correlazione tra commit SHA e deployment
lead_time_seconds = (
    deploy_timestamp - commit_timestamp
    WHERE deployment.commit_sha = commit.sha
    AND environment = "production"
)

# Change Failure Rate: deploy che hanno richiesto hotfix/rollback
change_failure_rate = (
    count(deployments WHERE type IN ("hotfix", "rollback") AND timestamp > 30d ago)
    /
    count(deployments WHERE environment="production" AND timestamp > 30d ago)
)

# Time to Restore: durata degli incidenti
time_to_restore = (
    incident.resolved_at - incident.opened_at
    WHERE severity IN ("p1", "p2")
    AND environment = "production"
)
```

**Strumenti per la raccolta:**
- **DORA Metrics Dashboard**: Integrazione nativa in GitLab, LinearB, Sleuth, Cortex
- **GitHub Actions**: metriche derivabili da workflow run data
- **Jenkins**: plugin DORA metrics o integrazione con Datadog
- **Custom**: webhook su deployment events verso InfluxDB/Prometheus

### Come Migliorare le Metriche

| Metrica bassa | Cause comuni | Interventi |
|---------------|-------------|-----------|
| Deployment Frequency bassa | Batch grandi, paura del deploy | Trunk-based development, feature flags, pipeline automatica |
| Lead Time alto | Review lente, pipeline lenta, gating manuale | Parallelizzare test, automatizzare approval, ottimizzare build |
| Change Failure Rate alta | Test insufficienti, monitoring scarso | Testing pyramid, canary deployment, rollback automatico |
| MTTR alto | Detection lenta, runbook assenti | Alert proattivi, SLO, runbook automatizzati, chaos engineering |

## CI vs CD vs Continuous Deployment

| Pratica | Definizione | Pre-requisiti | Adatto a |
|---------|-------------|--------------|----------|
| **Continuous Integration** | Ogni commit integrato nel branch principale + build + test automatici | Test automatici, fast feedback | Tutti |
| **Continuous Delivery** | Software sempre in uno stato deployabile in produzione; deploy è manuale/con approvazione | CI + environment paritari + test E2E | Team che necessitano approvazione umana |
| **Continuous Deployment** | Ogni commit che passa tutti i test viene deployato automaticamente in produzione | CD + test di alta fiducia + monitoring robusto + rollback automatico | Team maturi, prodotti SaaS |

```
Continuous Integration:
  commit → build → test → [✓ integrato]

Continuous Delivery:
  commit → build → test → staging-deploy → [approvazione] → prod-deploy

Continuous Deployment:
  commit → build → test → staging-deploy → [test automatici] → prod-deploy (automatico)
```

!!! note "Continuous Delivery vs Deployment"
    La distinzione è sottile ma importante: in **Continuous Delivery**, un umano preme il bottone per il deploy in produzione (after verification). In **Continuous Deployment**, non esiste quel bottone — il sistema si auto-promuove. La scelta dipende da compliance, risk appetite e maturità dei test.

## Principi di Design della Pipeline

### 1. Fail Fast

Posizionare i check più veloci e più predittivi all'inizio della pipeline. Un build che fallisce dopo 45 minuti è significativamente peggio di uno che fallisce dopo 2 minuti.

```yaml
# Pipeline strutturata per fail fast
stages:
  1-lint:          # < 1 min: errori sintattici, stile
  2-unit-test:     # 2-5 min: test veloci, alta copertura logica
  3-build:         # 3-10 min: compilazione
  4-integration:   # 10-20 min: test con database, servizi reali
  5-e2e:           # 20-40 min: test scenari utente completi
  6-security:      # 5-15 min: SAST, SCA (in parallelo con integration)
  7-deploy-staging:
  8-smoke-test:    # < 5 min: verifica base post-deploy
  9-deploy-prod:   # Solo se branch main, con approvazione
```

### 2. Shift Left Security

Spostare i controlli di sicurezza il prima possibile nel ciclo di sviluppo. Un vuln trovato nel commit costa 10x meno di uno trovato in staging, e 100x meno di uno trovato in produzione.

```
Pre-commit hook:    secret scanning (gitleaks)
CI - Lint stage:    IaC scanning, Dockerfile linting
CI - Build stage:   SAST (semgrep, codeql)
CI - Test stage:    SCA (dependency scanning)
CI - Package stage: Container scanning (trivy)
CD - Staging:       DAST (ZAP baseline scan)
CD - Pre-prod:      Penetration testing (manual/automated)
```

### 3. Immutable Artifacts

Un artefatto (JAR, Docker image, Helm chart) viene prodotto UNA SOLA VOLTA e promosso attraverso gli ambienti. Non si ricompila per ogni ambiente.

```yaml
# ✅ Corretto: build una volta, promuovi l'artefatto
build:
  script:
    - docker build -t myapp:$CI_COMMIT_SHA .
    - docker push registry/myapp:$CI_COMMIT_SHA

deploy-staging:
  script:
    - kubectl set image deployment/myapp app=registry/myapp:$CI_COMMIT_SHA

deploy-production:
  script:
    # Stesso SHA, stesso artefatto testato in staging
    - kubectl set image deployment/myapp app=registry/myapp:$CI_COMMIT_SHA

# ❌ Errato: ricompila per ogni ambiente (potenziali differenze)
deploy-staging:
  script:
    - ./build.sh --env staging
    - ./deploy.sh staging

deploy-production:
  script:
    - ./build.sh --env production  # Build diverso!
    - ./deploy.sh production
```

### 4. Idempotent Deployments

Un deployment deve poter essere eseguito N volte con lo stesso risultato. Non deve dipendere dallo stato precedente del cluster.

```yaml
# ✅ Idempotente: kubectl apply e helm upgrade sono idempotenti
- kubectl apply -f k8s/
- helm upgrade --install myapp ./chart

# ❌ Non idempotente: crea risorse ogni volta
- kubectl create deployment myapp --image=...
- kubectl expose deployment myapp --port=80
```

### 5. Parallelismo

Eseguire in parallelo tutto ciò che non ha dipendenze sequenziali. Riduce il lead time senza aumentare il costo.

```yaml
# Parallelismo in GitHub Actions
jobs:
  unit-test:
    runs-on: ubuntu-latest
    # ← nessun needs: parte in parallelo con lint e security

  lint:
    runs-on: ubuntu-latest
    # ← parte in parallelo

  security-scan:
    runs-on: ubuntu-latest
    # ← parte in parallelo

  build:
    needs: [unit-test, lint]   # Aspetta i check veloci
    runs-on: ubuntu-latest

  integration-test:
    needs: [build]
    runs-on: ubuntu-latest

  deploy-staging:
    needs: [integration-test, security-scan]  # Aspetta security scan anche
```

## Testing Pyramid nella Pipeline

```
                    /\
                   /  \
                  / E2E \           Lenti, costosi, fragili (pochi)
                 /  ~20%  \         Eseguiti: post-deploy staging
                /──────────\
               / Integration \       Medi (alcuni decine)
              /    ~30%       \      Eseguiti: CI con docker-compose
             /─────────────────\
            /     Unit Tests    \    Veloci, economici, stabili (molti)
           /        ~50%         \   Eseguiti: ogni commit
          /─────────────────────  \
```

### Testing in Pipeline

```yaml
# Struttura raccomandata per i test

# 1. Unit test (fast, no external deps)
unit-test:
  runs-on: ubuntu-latest
  steps:
    - run: mvn test -Dtest="Unit*,*Service*" -DfailIfNoTests=false
  # Target: < 5 minuti

# 2. Integration test (con servizi reali via docker-compose o testcontainers)
integration-test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_DB: testdb
        POSTGRES_USER: test
        POSTGRES_PASSWORD: test
  steps:
    - run: mvn test -Dtest="Integration*" -P integration-test
  # Target: < 15 minuti

# 3. E2E / Acceptance test (contro staging deployato)
e2e-test:
  needs: [deploy-staging]
  runs-on: ubuntu-latest
  steps:
    - run: npx playwright test --project=chromium
      env:
        BASE_URL: https://staging.myapp.example.com
  # Target: < 30 minuti

# 4. Smoke test (post-deploy, verifica base)
smoke-test:
  needs: [deploy-production]
  runs-on: ubuntu-latest
  steps:
    - run: |
        curl --fail --retry 10 --retry-delay 5 \
          https://myapp.example.com/health
        curl --fail https://myapp.example.com/api/v1/status
  # Target: < 2 minuti
```

## Environment Promotion Strategy

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   Dev    │ →  │  Staging │ → │  Pre-Prod│ →  │  Prod    │
│          │    │          │    │(UAT/Canary)│    │          │
│ Auto-    │    │ Auto-    │    │ Manual   │    │ Manual/  │
│ deploy   │    │ deploy   │    │ approv.  │    │ GitOps   │
│          │    │          │    │          │    │          │
│ Unit +   │    │ Integr.  │    │ UAT      │    │ Smoke +  │
│ Lint     │    │ E2E      │    │ Perf     │    │ Monitor  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │ stesso SHA ───┴───────────────┴───────────────┘
     │ stesso artefatto (immutable artifact)
```

**Regole di promozione:**
- **Dev → Staging**: automatico al merge su main, dopo unit test
- **Staging → Pre-Prod**: automatico dopo test E2E in staging, oppure con approvazione team QA
- **Pre-Prod → Prod**: approvazione manuale (business), deployment in finestra, canary rollout

## Relazioni

??? info "Strategie di Deployment"
    Blue-Green, Canary, Rolling Update, Feature Flags, Shadow Deployment — implementazioni dettagliate con codice.

    **Approfondimento completo →** [Strategie di Deployment](deployment-strategies.md)

??? info "Pipeline Security (DevSecOps)"
    Shift left security, SAST, DAST, SCA, SBOM, Sigstore/Cosign, SLSA framework.

    **Approfondimento completo →** [Pipeline Security](pipeline-security.md)

??? info "Jenkins Enterprise Patterns"
    Pipeline design patterns in Jenkins, gestione ambienti, approvazioni, multi-branch.

    **Approfondimento completo →** [Jenkins Enterprise Patterns](../jenkins/enterprise-patterns.md)

## Riferimenti

- [DORA State of DevOps Report 2023](https://dora.dev/research/2023/dora-report/)
- [DORA Metrics reference](https://dora.dev/guides/dora-metrics-four-keys/)
- [Accelerate book (Forsgren, Humble, Kim)](https://itrevolution.com/product/accelerate/)
- [Google SRE Book — Release Engineering](https://sre.google/sre-book/release-engineering/)
- [Continuous Delivery (Humble, Farley)](https://continuousdelivery.com/)
- [The Twelve-Factor App](https://12factor.net/)
- [CNCF CI/CD Landscape](https://landscape.cncf.io/card-mode?category=continuous-integration-delivery)
