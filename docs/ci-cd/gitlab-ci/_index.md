---
title: "GitLab CI/CD"
slug: gitlab-ci
category: ci-cd
tags: [gitlab, gitlab-ci, pipeline, devops-platform]
search_keywords: [gitlab ci cd, gitlab pipeline, .gitlab-ci.yml, gitlab runner, gitlab devops, gitlab merge request pipeline, gitlab pages, gitlab environments, gitlab auto devops]
parent: ci-cd/_index
related: [ci-cd/gitlab-ci/pipeline-avanzato, ci-cd/github-actions/_index, ci-cd/gitops/argocd]
official_docs: https://docs.gitlab.com/ee/ci/
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# GitLab CI/CD

## Panoramica

GitLab è una piattaforma DevOps completa che integra in un singolo prodotto tutto il ciclo di vita del software: SCM (Git), CI/CD, Container Registry, Package Registry, Security Scanning, Environments, Monitoring e molto altro. A differenza di GitHub Actions (solo CI/CD) o Jenkins (solo pipeline), GitLab offre una visibilità end-to-end dal commit al deploy senza necessità di integrare strumenti terzi. Le pipeline sono definite nel file `.gitlab-ci.yml` nella root del repository e supportano costrutti avanzati come DAG (Directed Acyclic Graph), pipeline gerarchiche parent-child, multi-project pipelines e compliance frameworks. GitLab è disponibile come SaaS (gitlab.com), come self-managed (Community Edition gratuita, Enterprise Edition a pagamento) e come GitLab Dedicated (single-tenant managed).

## GitLab come DevOps Platform

```
┌─────────────────────────────────────────────────────────────┐
│                     GitLab DevOps Platform                   │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Manage  │   Plan   │  Create  │  Verify  │    Package      │
│          │          │          │          │                 │
│  Groups  │  Issues  │   SCM    │  CI/CD   │  Container Reg  │
│  Members │  Boards  │   MR     │  Testing │  Package Reg    │
│  Audit   │ Roadmaps │  Review  │  Quality │  Helm Charts    │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│   Secure  │  Deploy  │  Monitor  │  Govern  │               │
│           │          │           │          │               │
│   SAST    │  Envs    │  Metrics  │  Compliance               │
│   DAST    │  GitOps  │  Logs     │  Policies│               │
│   Scan    │  K8s     │  Alerts   │  Audit   │               │
└───────────┴──────────┴───────────┴──────────┘───────────────┘
```

## Struttura del `.gitlab-ci.yml`

Il file di configurazione CI/CD risiede nella root del repository. GitLab lo processa all'apertura di ogni pipeline.

### Keywords Principali

```yaml
# .gitlab-ci.yml — Esempio completo con le keyword fondamentali

# Stages: definisce l'ordine di esecuzione e il raggruppamento dei job
stages:
  - build
  - test
  - security
  - package
  - deploy

# Variabili globali
variables:
  MAVEN_OPTS: "-Dmaven.repo.local=.m2/repository"
  DOCKER_DRIVER: overlay2
  IMAGE_NAME: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"

# Default: applica a tutti i job (override possibile per singolo job)
default:
  image: eclipse-temurin:21-jdk
  interruptible: true    # Il job può essere cancellato se pipeline più nuova parte
  retry:
    max: 2
    when:
      - runner_system_failure
      - stuck_or_timeout_failure

# Cache globale
cache:
  key:
    files:
      - pom.xml
  paths:
    - .m2/repository
  policy: pull-push   # pull-push | pull | push

# ─── JOB ESEMPI ─────────────────────────────────────────────

compile:
  stage: build
  script:
    - mvn --batch-mode compile -DskipTests
  artifacts:
    paths:
      - target/classes/
    expire_in: 1 hour

unit-tests:
  stage: test
  script:
    - mvn --batch-mode test
  artifacts:
    when: always   # Carica anche se il job fallisce
    reports:
      junit: target/surefire-reports/TEST-*.xml
    paths:
      - target/surefire-reports/
    expire_in: 1 week
  coverage: '/Total.*?([0-9]{1,3})%/'  # Regex per estrarre % copertura

build-docker:
  stage: package
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  before_script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
  script:
    - docker build -t "$IMAGE_NAME" .
    - docker push "$IMAGE_NAME"
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual

deploy-staging:
  stage: deploy
  environment:
    name: staging
    url: https://staging.myapp.example.com
    on_stop: stop-staging  # Job da eseguire per "stop" dell'environment
  script:
    - kubectl set image deployment/myapp app="$IMAGE_NAME"
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
  needs:
    - build-docker

stop-staging:
  stage: deploy
  environment:
    name: staging
    action: stop
  script:
    - kubectl delete deployment myapp -n staging
  when: manual
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: manual
```

### Keyword di Controllo Flusso

| Keyword | Descrizione | Esempio |
|---------|-------------|---------|
| `rules` | Condizioni per includere/escludere job | `if`, `changes`, `exists`, `when` |
| `needs` | Dipendenze DAG tra job (aggira l'ordine degli stage) | `needs: [build, lint]` |
| `dependencies` | Scarica artifacts solo da job specifici | `dependencies: [build]` |
| `when` | Timing esecuzione job | `on_success`, `on_failure`, `always`, `manual`, `delayed` |
| `allow_failure` | Job può fallire senza bloccare la pipeline | `allow_failure: true` |
| `timeout` | Timeout specifico per job | `timeout: 30 minutes` |
| `parallel` | Esegue N istanze del job in parallelo | `parallel: 5` |
| `trigger` | Avvia una pipeline downstream | `trigger: my-org/other-project` |
| `include` | Include altri file di configurazione | `include: [template, file, component]` |
| `extends` | Eredita configurazione da un job base | `extends: .base-job` |
| `interruptible` | Il job può essere cancellato | `interruptible: true` |

### Variabili Predefinite Utili

```yaml
# Variabili CI/CD sempre disponibili
CI_COMMIT_SHA           # SHA completo del commit
CI_COMMIT_SHORT_SHA     # SHA breve (8 caratteri)
CI_COMMIT_BRANCH        # Branch corrente (non su MR)
CI_COMMIT_TAG           # Tag (se la pipeline è per un tag)
CI_COMMIT_REF_SLUG      # Branch/tag normalizzato per URL (es. feature-my-branch)
CI_MERGE_REQUEST_IID    # IID della Merge Request (solo su MR pipeline)
CI_PIPELINE_SOURCE      # Sorgente: push, web, schedule, trigger, merge_request_event
CI_PROJECT_NAME         # Nome del progetto
CI_PROJECT_PATH         # Namespace/project-name
CI_REGISTRY             # URL del GitLab Container Registry
CI_REGISTRY_IMAGE       # URL immagine nel registry (registry/namespace/project)
CI_ENVIRONMENT_NAME     # Nome dell'environment (nei job con environment:)
CI_JOB_TOKEN            # Token temporaneo valido per la durata del job
GITLAB_USER_EMAIL       # Email di chi ha triggerato la pipeline
```

## GitLab Runner

Il GitLab Runner è il processo che esegue i job della pipeline. Può essere shared (fornito da GitLab.com), group (condiviso tra progetti di un gruppo) o project-specific.

### Tipi di Executor

| Executor | Descrizione | Isolamento | Uso tipico |
|----------|-------------|------------|------------|
| `shell` | Esegue comandi direttamente sulla macchina host | Nessuno | Dev, task semplici |
| `docker` | Ogni job in un container Docker fresco | Container | Standard CI/CD |
| `docker+machine` | Docker Machine per scaling automatico (legacy) | Container | GitLab.com shared |
| `kubernetes` | Ogni job in un Pod Kubernetes | Container/Pod | K8s-native, scalabile |
| `virtualbox` | VM VirtualBox | VM | Test OS diversi |
| `custom` | Script di setup/cleanup personalizzati | Custom | Casi speciali |

### Registrazione Runner

```bash
# Installare GitLab Runner (Linux)
curl -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.rpm.sh | sudo bash
sudo apt-get install gitlab-runner   # Debian/Ubuntu

# Registrare il runner
sudo gitlab-runner register \
  --non-interactive \
  --url "https://gitlab.com" \
  --token "$RUNNER_REGISTRATION_TOKEN" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
  --description "my-docker-runner" \
  --tag-list "docker,linux,x64" \
  --run-untagged="false" \
  --locked="false" \
  --maintenance-note "Runner per CI standard"

# Runner config in /etc/gitlab-runner/config.toml
```

### Configurazione Runner Kubernetes

```toml
# /etc/gitlab-runner/config.toml
[[runners]]
  name = "k8s-runner"
  url = "https://gitlab.com"
  token = "RUNNER_TOKEN"
  executor = "kubernetes"

  [runners.kubernetes]
    host = ""  # Usa in-cluster config
    namespace = "gitlab-runners"
    image = "alpine:latest"
    privileged = false
    cpu_request = "500m"
    cpu_limit = "2"
    memory_request = "512Mi"
    memory_limit = "2Gi"
    service_account = "gitlab-runner"

    [[runners.kubernetes.volumes.empty_dir]]
      name = "docker-certs"
      mount_path = "/certs/client"
      medium = "Memory"
```

## Tipi di Pipeline

| Tipo | Trigger | Quando usare |
|------|---------|--------------|
| **Branch pipeline** | Push su branch | CI standard per ogni commit |
| **Merge Request pipeline** | Apertura/aggiornamento MR | Validazione pre-merge |
| **Merged results pipeline** | MR + merge con target branch (simulato) | Test del risultato del merge |
| **Merge Train** | Auto-merge sequenziale | Throughput alto, branch protetti |
| **Scheduled pipeline** | Cron schedule | Nightly builds, security scans |
| **Tag pipeline** | Push di un tag | Release, publish artifacts |
| **Parent-child pipeline** | `trigger:` con `include:` | Modularizzazione pipeline complesse |
| **Multi-project pipeline** | `trigger:` cross-project | Deploy coordinato tra microservizi |

### MR Pipeline vs Branch Pipeline

```yaml
# Evitare pipeline doppie (branch + MR) con rules intelligenti
workflow:
  rules:
    # Esegui su MR
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    # Esegui su branch main/develop senza MR aperta
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_COMMIT_BRANCH == "develop"'
    # Non eseguire su branch normali se esiste una MR aperta
    - if: '$CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS'
      when: never
    - if: '$CI_COMMIT_BRANCH'
```

## Include — Riutilizzo della Configurazione

```yaml
include:
  # Template ufficiali GitLab (gitlab.com/gitlab-org/gitlab)
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml

  # File nel repository corrente
  - local: '.gitlab/ci/build.yml'
  - local: '.gitlab/ci/deploy.yml'

  # File remoto (URL)
  - remote: 'https://gitlab.mycompany.com/devops/ci-templates/-/raw/main/java-pipeline.yml'

  # File da altro progetto GitLab
  - project: 'my-group/ci-templates'
    ref: 'v2.1.0'
    file: '/templates/java-maven.yml'

  # Componente GitLab (nuovo sistema raccomandato)
  - component: gitlab.com/my-group/ci-components/sast@1.0.0
    inputs:
      stage: security
      scan-type: semgrep
```

## Auto DevOps

GitLab Auto DevOps è una pipeline automatica che rileva il linguaggio del progetto e applica best practice senza configurazione manuale.

```yaml
# Abilitare Auto DevOps nel progetto (Settings > CI/CD > Auto DevOps)
# Oppure configurare parzialmente:
include:
  - template: Auto-DevOps.gitlab-ci.yml

variables:
  AUTO_DEVOPS_PLATFORM_TARGET: "kubernetes"
  KUBE_NAMESPACE: "myapp-production"
  # AUTO_DEVOPS_BUILD_IMAGE_CNB_ENABLED: "true"  # Cloud Native Buildpacks
```

Auto DevOps include automaticamente: build, test, code quality, SAST, dependency scanning, container scanning, review apps, deploy staging/production.

## Confronto GitHub Actions vs GitLab CI

| Feature | GitLab CI/CD | GitHub Actions |
|---------|-------------|----------------|
| **Configurazione** | `.gitlab-ci.yml` | `.github/workflows/*.yml` |
| **Runner managed** | Shared runners (GitLab.com) | GitHub-hosted runners |
| **Runner self-hosted** | GitLab Runner | Actions Runner |
| **Autoscaling K8s** | Kubernetes executor | ARC (Actions Runner Controller) |
| **DAG pipeline** | `needs:` (nativo) | Non nativo (solo sequenziale/parallelo) |
| **Parent-child pipeline** | Nativo | Non nativo |
| **Multi-project pipeline** | Nativo con `trigger:` | Via workflow_call (stesso org) |
| **Security scanning** | Nativo (template inclusi) | GHAS (a pagamento per privati) |
| **Container registry** | Nativo (GitLab Registry) | GitHub Container Registry (GHCR) |
| **Environment approvals** | Sì (Protected Environments) | Sì (Environments) |
| **Compliance pipeline** | Sì (Ultimate) | Required Workflows (Enterprise) |
| **Cache** | `cache:` keyword | `actions/cache` action |
| **Artifacts** | `artifacts:` keyword | `actions/upload-artifact` action |
| **Variabili CI** | Predefinite, ricche | `github.*`, `env.*` context |
| **OIDC cloud auth** | Nativo | Nativo |
| **Review Apps** | Nativo | Non nativo |
| **Merge Train** | Nativo | Non nativo |
| **Self-managed** | Sì (CE/EE) | GHES (a pagamento) |

## Relazioni

??? info "GitLab CI — Pipeline Avanzate"
    DAG, regole dinamiche, multi-project pipeline, child pipeline, compliance framework, security scanning avanzato.

    **Approfondimento completo →** [Pipeline Avanzate](pipeline-avanzato.md)

??? info "GitOps con ArgoCD"
    Integrare GitLab CI con ArgoCD per deployment GitOps: build immagine in GitLab, aggiornamento manifesti, sync ArgoCD.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

## Riferimenti

- [GitLab CI/CD documentation](https://docs.gitlab.com/ee/ci/)
- [.gitlab-ci.yml keyword reference](https://docs.gitlab.com/ee/ci/yaml/)
- [GitLab Runner documentation](https://docs.gitlab.com/runner/)
- [CI/CD variables reference](https://docs.gitlab.com/ee/ci/variables/predefined_variables.html)
- [Auto DevOps](https://docs.gitlab.com/ee/topics/autodevops/)
- [GitLab CI/CD examples](https://docs.gitlab.com/ee/ci/examples/)
