---
title: "GitLab CI — Pipeline Avanzate"
slug: pipeline-avanzato
category: ci-cd
tags: [gitlab, dag, multi-project, compliance, protected-environments, gitlab-security, gitlab-component]
search_keywords: [gitlab dag pipeline, gitlab needs keyword, gitlab multi project pipeline, gitlab downstream pipeline, gitlab compliance pipeline, gitlab protected environment, gitlab approval rules, gitlab security scanning, gitlab dast sast, gitlab container scanning, gitlab license compliance, gitlab merge train, gitlab dynamic child pipeline, gitlab rules changes]
parent: ci-cd/gitlab-ci/_index
related: [ci-cd/gitlab-ci/_index, ci-cd/gitops/argocd, security/supply-chain]
official_docs: https://docs.gitlab.com/ee/ci/directed_acyclic_graph/
status: complete
difficulty: expert
last_updated: 2026-03-28
---

# GitLab CI — Pipeline Avanzate

## Panoramica

Le funzionalità avanzate di GitLab CI/CD consentono di costruire pipeline enterprise-grade con esecuzione ottimizzata tramite DAG (Directed Acyclic Graph), dinamismo tramite child pipeline generate a runtime, coordinamento cross-team con multi-project pipeline, e compliance obbligatoria tramite framework di sicurezza. Questa guida copre i costrutti avanzati che distinguono GitLab da soluzioni CI/CD più semplici, con esempi di configurazione reali e pronti per ambienti di produzione.

## DAG con `needs`

Per default, GitLab esegue i job in ordine di stage: tutti i job dello stage N devono completare prima che lo stage N+1 inizi. La keyword `needs` rompe questo vincolo, creando un grafo di dipendenze dove i job iniziano non appena i loro prerequisiti sono completati.

```yaml
stages:
  - build
  - test
  - package
  - deploy

# ─── STAGE: build ─────────────────────────────────
compile-backend:
  stage: build
  script: mvn --batch-mode compile -DskipTests
  artifacts:
    paths: [target/classes/]
    expire_in: 1h

compile-frontend:
  stage: build
  image: node:20-alpine
  script: npm ci && npm run build
  artifacts:
    paths: [dist/]
    expire_in: 1h

# ─── STAGE: test ──────────────────────────────────
# Inizia subito dopo compile-backend, NON aspetta compile-frontend
unit-tests-backend:
  stage: test
  needs:
    - job: compile-backend
      artifacts: true  # Scarica gli artifacts di compile-backend
  script: mvn --batch-mode test
  artifacts:
    reports:
      junit: target/surefire-reports/TEST-*.xml
    when: always

# Inizia subito dopo compile-frontend, NON aspetta compile-backend
unit-tests-frontend:
  stage: test
  image: node:20-alpine
  needs:
    - job: compile-frontend
      artifacts: true
  script: npm test -- --watchAll=false
  artifacts:
    reports:
      junit: junit.xml
    when: always

# Dipende da entrambe le compilazioni
integration-tests:
  stage: test
  needs:
    - job: compile-backend
      artifacts: true
    - job: compile-frontend
      artifacts: true
  script: ./run-integration-tests.sh
  allow_failure: false

# ─── STAGE: package ───────────────────────────────
# Inizia quando unit-tests-backend completa, NON aspetta integration-tests
build-docker:
  stage: package
  needs: [unit-tests-backend]
  image: docker:24
  services: [docker:24-dind]
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
    - docker build -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"

# ─── STAGE: deploy ────────────────────────────────
deploy-staging:
  stage: deploy
  needs:
    - job: build-docker
    - job: integration-tests   # Aspetta ANCHE integration-tests
  environment:
    name: staging
    url: https://staging.example.com
  script:
    - kubectl set image deployment/myapp app="$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"
```

!!! note "Tempo risparmiato con DAG"
    Con gli stage tradizionali, la sequenza sarebbe: build (2 job paralleli, ~3 min) → test (3 job paralleli, ~10 min) → package (1 job, ~5 min). Con DAG, `build-docker` può iniziare 7 minuti prima perché non aspetta `integration-tests`.

## Rules vs Only/Except

La keyword `rules` sostituisce `only`/`except` (deprecate) con una logica condizionale più espressiva e componibile.

### Migrazione da only/except a rules

```yaml
# ❌ Vecchio stile: only/except
deploy-old:
  script: ./deploy.sh
  only:
    - main
  except:
    - schedules

# ✅ Nuovo stile: rules
deploy-new:
  script: ./deploy.sh
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
      when: never   # Escludi pipeline schedulate
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: on_success
```

### Rules Avanzate con Condizioni Multiple

```yaml
.production-deploy-rules: &production-deploy-rules
  rules:
    # Su merge request: job manuale (per review)
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual
      allow_failure: true
    # Su main dopo push: automatico
    - if: '$CI_COMMIT_BRANCH == "main" && $CI_PIPELINE_SOURCE == "push"'
      when: on_success
    # Su tag di release: automatico
    - if: '$CI_COMMIT_TAG =~ /^v[0-9]+\.[0-9]+\.[0-9]+$/'
      when: on_success
    # Altrimenti: non eseguire
    - when: never

deploy-production:
  <<: *production-deploy-rules
  stage: deploy
  script: ./deploy-prod.sh
  environment:
    name: production
    url: https://app.example.com

# ─── Condizioni su file modificati ────────────────
build-backend:
  stage: build
  script: mvn package
  rules:
    # Esegui solo se file backend sono cambiati
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      changes:
        - backend/**/*
        - pom.xml
        - Dockerfile
      when: on_success
    # Su main, esegui sempre
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: on_success
    - when: never

# ─── Condizioni su esistenza di file ──────────────
run-terraform:
  stage: deploy
  script: terraform apply
  rules:
    - exists:
        - "terraform/**/*.tf"
      when: on_success
    - when: never

# ─── Variabili dinamiche nelle rules ──────────────
build-experimental:
  stage: build
  script: ./build.sh
  rules:
    - if: '$ENABLE_EXPERIMENTAL == "true"'
      variables:
        BUILD_FLAGS: "--experimental --verbose"
      when: on_success
    - when: never
  script:
    - ./build.sh $BUILD_FLAGS
```

## Multi-Project Pipelines

Le multi-project pipeline permettono di triggerare pipeline in altri progetti GitLab, coordinando deployment di microservizi o infrastrutture correlate.

```yaml
# Progetto A: my-org/api-service
# Triggera il deploy dell'API quando il progetto frontend si aggiorna

stages: [build, test, trigger-downstream]

build-frontend:
  stage: build
  script: npm run build
  artifacts:
    paths: [dist/]

test-frontend:
  stage: test
  needs: [build-frontend]
  script: npm test

# Triggera pipeline nel progetto api-service con strategy: depend
# (aspetta che la pipeline downstream completi)
trigger-api-deploy:
  stage: trigger-downstream
  needs: [test-frontend]
  trigger:
    project: my-org/api-service
    branch: main
    strategy: depend   # Aspetta il completamento della pipeline downstream
  variables:
    FRONTEND_BUILD_SHA: "$CI_COMMIT_SHORT_SHA"
    DEPLOY_TRIGGERED_BY: "$GITLAB_USER_EMAIL"
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

# ─── Cross-project artifacts ──────────────────────
# Nel progetto downstream (api-service), accedere agli artifacts del progetto upstream:
download-frontend-artifacts:
  stage: build
  script:
    - |
      curl --header "JOB-TOKEN: $CI_JOB_TOKEN" \
        "https://gitlab.com/api/v4/projects/${UPSTREAM_PROJECT_ID}/jobs/artifacts/main/download?job=build-frontend" \
        --output frontend-dist.zip
    - unzip frontend-dist.zip -d ./public
```

## Dynamic Child Pipelines

Le child pipeline vengono generate dinamicamente a runtime, permettendo pipeline adattive al contesto (es. monorepo dove ogni servizio ha la propria pipeline).

```yaml
# Progetto monorepo con struttura:
# services/
#   auth-service/
#   payment-service/
#   notification-service/

stages: [generate, trigger]

# Step 1: Genera il file di configurazione pipeline a runtime
generate-child-pipelines:
  stage: generate
  image: python:3.12-alpine
  script:
    - pip install pyyaml
    - python scripts/generate_pipeline.py > generated-pipeline.yml
    - cat generated-pipeline.yml  # Debug: mostra il file generato
  artifacts:
    paths: [generated-pipeline.yml]
    expire_in: 1h

# Step 2: Esegui la pipeline generata come child pipeline
trigger-generated:
  stage: trigger
  needs:
    - job: generate-child-pipelines
      artifacts: true
  trigger:
    include:
      - artifact: generated-pipeline.yml
        job: generate-child-pipelines
    strategy: depend
```

Script Python per generare la pipeline dinamicamente:

```python
# scripts/generate_pipeline.py
import yaml
import os
import subprocess

# Trova i servizi con modifiche (git diff)
result = subprocess.run(
    ['git', 'diff', '--name-only', 'HEAD~1'],
    capture_output=True, text=True
)
changed_files = result.stdout.strip().split('\n')

services_dir = 'services'
changed_services = set()

for f in changed_files:
    parts = f.split('/')
    if len(parts) > 1 and parts[0] == services_dir:
        changed_services.add(parts[1])

# Genera job solo per i servizi modificati
pipeline = {
    'stages': ['build', 'test', 'push'],
    'variables': {'CI_REGISTRY_IMAGE': os.environ.get('CI_REGISTRY_IMAGE', '')}
}

for service in changed_services:
    service_path = os.path.join(services_dir, service)
    if not os.path.isdir(service_path):
        continue

    pipeline[f'build-{service}'] = {
        'stage': 'build',
        'image': 'maven:3.9-eclipse-temurin-21',
        'script': [
            f'cd {service_path}',
            'mvn --batch-mode package -DskipTests'
        ],
        'artifacts': {
            'paths': [f'{service_path}/target/*.jar'],
            'expire_in': '1h'
        }
    }

    pipeline[f'test-{service}'] = {
        'stage': 'test',
        'image': 'maven:3.9-eclipse-temurin-21',
        'needs': [f'build-{service}'],
        'script': [
            f'cd {service_path}',
            'mvn --batch-mode test'
        ]
    }

print(yaml.dump(pipeline, default_flow_style=False))
```

## Compliance Pipelines (GitLab Ultimate)

I compliance framework permettono di forzare l'inclusione di job di sicurezza su tutti i progetti di un gruppo, indipendentemente dalla configurazione del singolo progetto.

```yaml
# File nel repository di compliance: compliance-pipeline.yml
# Configurato in: Group Settings > Compliance frameworks

# Questo file viene INCLUSO automaticamente in ogni pipeline del gruppo
# I developer del progetto NON possono sovrascrivere questi job

stages:
  - .pre    # Si esegue prima di tutti gli stage del progetto
  - .post   # Si esegue dopo tutti gli stage del progetto

# Job obbligatorio: secret detection
mandatory-secret-detection:
  stage: .pre
  image: registry.gitlab.com/security-products/secrets-detection:latest
  variables:
    SECRET_DETECTION_HISTORIC_SCAN: "false"
  script:
    - /analyzer run
  artifacts:
    reports:
      secret_detection: gl-secret-detection-report.json
    when: always
  allow_failure: false  # Blocca la pipeline se troviamo secrets

# Job obbligatorio: license compliance
mandatory-license-check:
  stage: .post
  image: registry.gitlab.com/security-products/license-finder:latest
  script:
    - /run.sh analyze .
  artifacts:
    reports:
      license_scanning: gl-license-scanning-report.json
  allow_failure: true  # Warning ma non blocca

# Job obbligatorio: validazione SBOM
mandatory-sbom-generation:
  stage: .post
  image: anchore/syft:latest
  script:
    - syft . -o cyclonedx-json > sbom.json
    - grype sbom:./sbom.json --fail-on high
  artifacts:
    paths: [sbom.json]
    expire_in: 90 days
```

## Protected Environments

I protected environment aggiungono controlli di accesso ai deployment, richiedendo approvazione esplicita prima che un job di deploy venga eseguito.

```yaml
# Configurazione in GitLab UI: Settings > CI/CD > Environments
# O via API:
curl -X POST \
  --header "PRIVATE-TOKEN: $ADMIN_TOKEN" \
  "https://gitlab.com/api/v4/projects/$PROJECT_ID/protected_environments" \
  --form "name=production" \
  --form "deploy_access_levels[][group_id]=42" \    # Solo questo gruppo può fare deploy
  --form "approval_rules[][group_id]=100" \         # Questo gruppo deve approvare
  --form "approval_rules[][required_approvals]=2"   # Minimo 2 approvazioni

# Nel .gitlab-ci.yml, il job aspetterà l'approvazione automaticamente
deploy-production:
  stage: deploy
  environment:
    name: production
    url: https://app.example.com
    deployment_tier: production  # production | staging | testing | development | other
  script:
    - kubectl apply -f k8s/production/
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v[0-9]+\.[0-9]+\.[0-9]+$/'
      when: on_success
```

**Tier degli ambienti e visualizzazione:**

```yaml
# GitLab usa il deployment_tier per visualizzare gli ambienti
# nel dashboard di monitoraggio
environments:
  - name: production
    tier: production
  - name: staging
    tier: staging
  - name: review/feature-xyz
    tier: development
```

## GitLab Security Scanning

GitLab include template di security scanning che si integrano con la Security Dashboard e il Merge Request security widget.

```yaml
include:
  # SAST (Static Application Security Testing)
  - template: Security/SAST.gitlab-ci.yml

  # DAST (Dynamic Application Security Testing)
  - template: Security/DAST.gitlab-ci.yml

  # Dependency Scanning
  - template: Security/Dependency-Scanning.gitlab-ci.yml

  # Container Scanning
  - template: Security/Container-Scanning.gitlab-ci.yml

  # Secret Detection
  - template: Security/Secret-Detection.gitlab-ci.yml

  # IaC Scanning (Terraform, Kubernetes, CloudFormation)
  - template: Security/KICS.gitlab-ci.yml

variables:
  # SAST: configurazione
  SAST_EXCLUDED_PATHS: "spec,test,tests,tmp,.git"
  SAST_ANALYZER_IMAGE_TAG: "4"

  # DAST: target da scansionare (deploy staging prima)
  DAST_WEBSITE: "https://staging.myapp.example.com"
  DAST_FULL_SCAN_ENABLED: "false"  # Quick scan in CI, full scan schedulato

  # Container Scanning
  CS_IMAGE: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"
  CS_SEVERITY_THRESHOLD: "high"

  # Dependency Scanning
  DS_MAX_DEPTH: 5

stages:
  - build
  - test
  - security    # Security jobs girano in parallelo
  - deploy-staging
  - dast        # DAST richiede un ambiente running
  - deploy-production
```

**Pipeline completa con security gate:**

```yaml
# Override del job DAST per personalizzazione
dast:
  stage: dast
  needs:
    - job: deploy-staging
  variables:
    DAST_WEBSITE: "https://staging.myapp.example.com"
    DAST_ZAP_CLI_OPTIONS: "-config scanner.strength=MEDIUM"
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual

# Job custom: analisi qualità con SonarQube
sonarqube-check:
  stage: security
  image:
    name: sonarsource/sonar-scanner-cli:latest
    entrypoint: [""]
  variables:
    SONAR_USER_HOME: "${CI_PROJECT_DIR}/.sonar"
    GIT_DEPTH: 0
  cache:
    key: "${CI_JOB_NAME}"
    paths:
      - .sonar/cache
  script:
    - sonar-scanner
      -Dsonar.projectKey=$SONAR_PROJECT_KEY
      -Dsonar.sources=src/main
      -Dsonar.tests=src/test
      -Dsonar.java.binaries=target/classes
      -Dsonar.qualitygate.wait=true
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == "main"'
```

## Merge Trains

I Merge Trains automatizzano il processo di merge sequenziale, testando ogni MR in combinazione con quelle già in coda, garantendo che il branch target rimanga sempre verde.

**Come funzionano:**

```
main: ─────────────────────────────────────────────────────►
         A    B    C
         │    │    │
Train:  [A] → [A+B] → [A+B+C]
         │         │         │
        Pass      Pass      Pass
         │         │         │
         └─────────┴─────────┴──► merge sequenziale garantito
```

**Configurazione:**

```yaml
# Abilitare in: Project Settings > Merge Requests > Merge Trains

# Nel .gitlab-ci.yml, i job che supportano merge train devono essere idempotenti
# e usare la variabile CI_MERGE_TRAIN_BRANCH se disponibile

test-for-merge-train:
  stage: test
  script:
    - echo "Testing on branch: ${CI_MERGE_TRAIN_BRANCH:-$CI_COMMIT_BRANCH}"
    - mvn test
  interruptible: true  # FONDAMENTALE: permite cancellazione se train viene riorganizzato
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_train"'
      when: on_success
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: on_success
```

!!! warning "Costo dei Merge Trains"
    I merge train aumentano significativamente il numero di pipeline eseguite (O(n²) nel caso peggiore con N MR in coda). Sono appropriati per team con alta frequenza di merge e branch protetti strict. Per team piccoli, le merged result pipeline (senza train) offrono un buon compromesso.

## GitLab Components

I GitLab CI/CD Components (disponibili da GitLab 16.0+) sono la nuova unità di riutilizzo raccomandata, più granulare degli include e più flessibile dei template.

```yaml
# Repository: my-org/ci-components
# Path: templates/sast/template.yml

spec:
  inputs:
    stage:
      default: test
    scan-type:
      description: 'Tipo di scan SAST'
      options: [semgrep, bandit, gosec]
      default: semgrep
    fail-on-severity:
      default: 'high'

---
"$[[ inputs.scan-type ]]-scan":
  stage: "$[[ inputs.stage ]]"
  image: "registry.gitlab.com/security-products/$[[ inputs.scan-type ]]:latest"
  script:
    - /analyzer run
  variables:
    SAST_FAIL_ON_SEVERITY: "$[[ inputs.fail-on-severity ]]"
  artifacts:
    reports:
      sast: gl-sast-report.json
    when: always
```

**Utilizzo del component:**

```yaml
# Nel progetto consumer
include:
  - component: gitlab.com/my-org/ci-components/sast@1.2.0
    inputs:
      stage: security
      scan-type: semgrep
      fail-on-severity: critical

  - component: gitlab.com/my-org/ci-components/deploy-kubernetes@2.0.0
    inputs:
      environment: staging
      namespace: myapp-staging
      image-tag: $CI_COMMIT_SHORT_SHA
```

## Troubleshooting

### Scenario 1 — Job con `needs` non trova gli artifacts

**Sintomo:** Il job fallisce con `ERROR: Job '...' is not in any dependency chain` oppure gli artifacts del job upstream non sono disponibili nonostante `artifacts: true` in `needs`.

**Causa:** Il job upstream è configurato con `artifacts: expire_in` molto breve, oppure manca `artifacts.paths` (solo `reports` non vengono scaricati automaticamente via `needs`), oppure il job upstream non è nello stesso pipeline DAG.

**Soluzione:** Verificare che il job upstream abbia `artifacts.paths` espliciti e che `expire_in` sia sufficiente per tutta la durata della pipeline. Per i report JUnit/coverage usare `artifacts.reports` in aggiunta a `artifacts.paths`.

```yaml
# ✅ Corretto: paths espliciti per il download via needs
compile-backend:
  stage: build
  script: mvn package
  artifacts:
    paths:
      - target/*.jar          # Scaricabile via needs
    reports:
      junit: target/surefire-reports/TEST-*.xml  # Solo per il widget MR
    expire_in: 2h

# Verifica che gli artifacts siano presenti nel job upstream:
# GitLab UI → Pipeline → Job → Browse artifacts
```

---

### Scenario 2 — Pipeline downstream con `strategy: depend` rimane bloccata

**Sintomo:** Il job `trigger` rimane nello stato "running" per ore e non completa. La pipeline downstream è visibile ma non viene attenduta correttamente.

**Causa:** La pipeline downstream contiene job con `when: manual` non eseguiti oppure protected environments con approvazioni pendenti. Con `strategy: depend`, GitLab aspetta il completamento totale inclusi job manuali.

**Soluzione:** Nella pipeline downstream, assicurarsi che i job manuali bloccanti abbiano `allow_failure: true` se non devono bloccare il flusso, oppure usare `strategy: depend` solo sulle pipeline che si completano automaticamente.

```yaml
# Nel progetto upstream: imposta timeout esplicito
trigger-api-deploy:
  trigger:
    project: my-org/api-service
    branch: main
    strategy: depend
  timeout: 30m   # Evita attese infinite

# Nel progetto downstream: job manuali non bloccanti
deploy-canary:
  when: manual
  allow_failure: true   # Non blocca la pipeline padre
  environment:
    name: production
```

---

### Scenario 3 — Compliance pipeline non viene applicata ai nuovi progetti

**Sintomo:** Nuovi progetti creati nel gruppo non eseguono i job di compliance (`mandatory-secret-detection`, ecc.) nonostante il compliance framework sia configurato sul gruppo.

**Causa:** Il compliance framework deve essere assegnato esplicitamente ad ogni progetto (o ai subgroup) — non viene ereditato automaticamente dai nuovi progetti creati dopo la configurazione.

**Soluzione:** Usare l'API GitLab per assegnare il compliance framework a tutti i progetti del gruppo, inclusi quelli futuri tramite webhook o automazione.

```bash
# Lista tutti i progetti del gruppo senza compliance framework
curl --header "PRIVATE-TOKEN: $ADMIN_TOKEN" \
  "https://gitlab.com/api/v4/groups/$GROUP_ID/projects?per_page=100" \
  | jq '.[] | select(.compliance_frameworks == []) | .id, .name'

# Assegna il compliance framework a un progetto specifico
curl -X PUT \
  --header "PRIVATE-TOKEN: $ADMIN_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"compliance_framework_id": 1}' \
  "https://gitlab.com/api/v4/projects/$PROJECT_ID"

# Verifica la configurazione del compliance framework
curl --header "PRIVATE-TOKEN: $ADMIN_TOKEN" \
  "https://gitlab.com/api/v4/groups/$GROUP_ID/compliance_frameworks"
```

---

### Scenario 4 — Dynamic child pipeline genera YAML invalido

**Sintomo:** Lo stage `trigger` fallisce con `Error: could not parse YAML file generated-pipeline.yml` oppure `jobs config should contain at least one visible job`.

**Causa:** Lo script di generazione produce YAML malformato (indentazione errata, caratteri speciali non escaped), oppure nessun servizio ha subito modifiche e il file generato contiene solo `stages` senza job.

**Soluzione:** Aggiungere validazione del YAML generato prima del trigger e gestire il caso base (nessuna modifica = nessun job da eseguire) con un job placeholder.

```python
# scripts/generate_pipeline.py — versione robusta
import yaml, os, subprocess, sys

changed_files = subprocess.run(
    ['git', 'diff', '--name-only', 'HEAD~1'],
    capture_output=True, text=True
).stdout.strip().split('\n')

changed_services = {
    f.split('/')[1] for f in changed_files
    if f.startswith('services/') and len(f.split('/')) > 2
}

pipeline = {'stages': ['build', 'test']}

if not changed_services:
    # Job placeholder: evita pipeline vuota (YAML invalido per GitLab)
    pipeline['no-changes'] = {
        'stage': 'build',
        'script': ['echo "No services changed, skipping"']
    }
else:
    for service in changed_services:
        pipeline[f'build-{service}'] = {
            'stage': 'build',
            'script': [f'cd services/{service} && mvn package']
        }

output = yaml.dump(pipeline, default_flow_style=False)

# Validazione base prima di emettere il YAML
try:
    yaml.safe_load(output)
except yaml.YAMLError as e:
    print(f"YAML generation failed: {e}", file=sys.stderr)
    sys.exit(1)

print(output)
```

```bash
# Debug: valida il YAML generato localmente prima di committare
python scripts/generate_pipeline.py > /tmp/test-pipeline.yml
python -c "import yaml; yaml.safe_load(open('/tmp/test-pipeline.yml'))" && echo "YAML valido"

# Oppure usa il GitLab CI Lint API
curl -X POST \
  --header "PRIVATE-TOKEN: $CI_JOB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "{\"content\": \"$(cat /tmp/test-pipeline.yml | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')\"}" \
  "https://gitlab.com/api/v4/ci/lint"
```

## Relazioni

??? info "GitLab CI — Panoramica"
    Concetti base, struttura `.gitlab-ci.yml`, runner, tipi di pipeline, include.

    **Approfondimento completo →** [GitLab CI/CD](_index.md)

??? info "GitOps con ArgoCD"
    Pattern GitOps con GitLab CI per build immagini e ArgoCD per deployment su Kubernetes.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

## Riferimenti

- [Directed Acyclic Graph](https://docs.gitlab.com/ee/ci/directed_acyclic_graph/)
- [needs keyword reference](https://docs.gitlab.com/ee/ci/yaml/#needs)
- [rules keyword reference](https://docs.gitlab.com/ee/ci/yaml/#rules)
- [Multi-project pipelines](https://docs.gitlab.com/ee/ci/pipelines/multi_project_pipelines.html)
- [Child/parent pipelines](https://docs.gitlab.com/ee/ci/pipelines/parent_child_pipelines.html)
- [Compliance pipelines](https://docs.gitlab.com/ee/user/group/compliance_frameworks.html)
- [Protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)
- [GitLab Security Scanning](https://docs.gitlab.com/ee/user/application_security/)
- [Merge Trains](https://docs.gitlab.com/ee/ci/pipelines/merge_trains.html)
- [CI/CD Components](https://docs.gitlab.com/ee/ci/components/)
