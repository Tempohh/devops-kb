---
title: "CircleCI"
slug: circleci
category: ci-cd
tags: [circleci, saas-ci, orbs, executors, workflows, dynamic-config, self-hosted-runner, docker-layer-caching]
search_keywords: [circleci, circle ci, circleci orbs, circleci executors, circleci workflows, circleci resource_class, circleci config.yml, circleci pipeline, circleci setup workflows, continuation orb, circleci matrix, circleci contexts, circleci oidc, circleci runner, self-hosted runner circleci, docker layer caching circleci, dlc, circleci caching, save_cache, restore_cache, circleci approval job, circleci scheduled workflow, circleci fan-out fan-in, circleci vs github actions, circleci vs gitlab ci, saas ci/cd, circleci machine executor, circleci macos executor, circleci windows executor]
parent: ci-cd/tools/_index
related: [ci-cd/github-actions/_index, ci-cd/gitlab-ci/_index, ci-cd/strategie/pipeline-security, ci-cd/pipeline]
official_docs: https://circleci.com/docs/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# CircleCI

## Panoramica

CircleCI è una piattaforma CI/CD **SaaS-first** (con opzione self-hosted via server on-prem, ormai marginale) nata per offrire setup rapido e configurazione dichiarativa via singolo file `config.yml`. A differenza di Jenkins — che richiede provisioning e manutenzione di un server — o di GitHub Actions/GitLab CI, che sono integrati nativamente nel proprio code hosting, CircleCI è un servizio esterno che si collega a GitHub, GitLab o Bitbucket tramite integrazione OAuth/webhook. Il suo punto di forza storico è la **resource_class granulare** (scelta fine di CPU/memoria per singolo job) e un ecosistema di **orbs** (pacchetti di configurazione riutilizzabile) che riduce boilerplate per integrazioni comuni (AWS, Slack, Kubernetes, SonarCloud).

CircleCI si usa quando serve velocità di setup su progetti multi-repo/multi-cloud senza legarsi a un singolo code host, quando si vuole controllo fine sulle risorse macchina per job costosi (build Android/iOS, matrix test pesanti), o quando si necessita self-hosted runner per workload non containerizzabili (test su hardware specifico, licenze software vincolate a macchina). Si sceglie **meno** quando il team è già interamente su GitHub o GitLab e vuole evitare un servizio terzo con la relativa gestione di secret e permessi separati, o quando il budget è limitato e i minuti gratuiti di GitHub Actions/GitLab CI bastano.

!!! warning "CircleCI non è gratuito su larga scala"
    Il piano free ha limiti stretti di credit mensili. Su repository con molte pipeline parallele (monorepo, PR frequenti) i costi salgono rapidamente rispetto a runner self-hosted GitHub Actions o GitLab CI con executor propri. Valutare `resource_class` più piccole dove possibile e usare workspace/cache aggressivamente per contenere i tempi di esecuzione (= credit consumati).

## Concetti Chiave

### Gerarchia della Configurazione

```
.circleci/config.yml
├── version: 2.1                    ← abilita orbs e reusable config
├── orbs                            ← pacchetti riutilizzabili (import)
├── executors                       ← definizioni riutilizzabili di ambiente
├── commands                        ← step riutilizzabili (come function)
├── jobs                            ← unità di lavoro (eseguite in un executor)
│   └── steps                       ← comandi eseguiti in sequenza nel job
└── workflows                       ← orchestrazione dei job (DAG, requires)
```

### Executors — Ambiente di Esecuzione

| Executor | Isolamento | Costo relativo | Uso tipico |
|----------|-----------|-----------------|------------|
| **docker** | Container Linux, immagine custom o pubblica | Basso | Build/test standard, la maggioranza dei job |
| **machine** | VM Linux dedicata (accesso Docker daemon nativo) | Medio-alto | Build immagini Docker, `docker-compose`, servizi che richiedono privilegi |
| **macos** | VM macOS dedicata | Alto | Build/test iOS, app macOS, Xcode |
| **windows** | VM Windows dedicata | Alto | Build .NET, test su Windows nativo |

!!! tip "Preferire `docker` quando possibile"
    L'executor `docker` è il più rapido da avviare (no boot VM) e il più economico. Usare `machine` solo quando serve accesso diretto al Docker daemon dell'host (es. `docker build` con cache layer complessa, `docker-compose up` con più servizi) — con `docker` executor il Docker-in-Docker richiede il setup `setup_remote_docker`, più lento e con limitazioni di networking tra container.

### Resource Class — Dimensionamento CPU/Memoria

| resource_class (docker, esempio) | vCPU | RAM |
|-----------------------------------|------|-----|
| `small` | 1 | 2 GB |
| `medium` | 2 | 4 GB |
| `medium+` | 3 | 6 GB |
| `large` | 4 | 8 GB |
| `xlarge` | 8 | 16 GB |
| `2xlarge` | 16 | 32 GB |

Valori equivalenti esistono per `machine`, `macos` (es. `m4pro.medium`; le vecchie classi M1 `macos.m1.*` sono dismesse) e `windows`. I valori esatti cambiano nel tempo: verificare nella reference ufficiale. Il costo in credit è proporzionale alla resource class scelta e alla durata del job — sovradimensionare spreca credit, sottodimensionare causa OOM/timeout su build pesanti.

### Workflows — Orchestrazione

| Concetto | Scopo |
|----------|-------|
| **`requires`** | Dipendenza tra job — un job parte solo dopo il completamento dei job richiesti (fan-in). |
| **Fan-out** | Un job genera più job paralleli che partono simultaneamente dopo di esso. |
| **`type: approval`** | Job manuale che blocca il workflow finché un utente non lo approva dalla UI/API. |
| **`triggers` + `schedule`** | Avvia il workflow su cron (es. nightly build), separato dai trigger su push. |
| **`matrix`** | Genera automaticamente N job dallo stesso template, parametrizzati (es. su versioni linguaggio o OS). |

## Architettura / Come Funziona

```
git push / PR
      │
      ▼
Webhook → CircleCI (SaaS, fuori dal repo)
      │
      ▼
Legge .circleci/config.yml
      │
      ├─ (opzionale) Dynamic config: genera pipeline a runtime
      │
      ▼
Pipeline instanziata (workflows)
      │
      ├─ Job A (executor: docker, resource_class: medium)
      │     └─ Steps: checkout → restore_cache → npm ci → npm test → save_cache
      │
      ├─ Job B (requires: [Job A]) ── parte solo dopo A
      │     └─ Steps: build immagine, docker layer caching
      │
      └─ Job C (type: approval, requires: [Job B]) ── attende click umano
            │
            ▼
      Job D (requires: [Job C]) ── deploy in produzione
```

Ogni job gira in un **container/VM effimero**: non c'è stato condiviso tra job per default. Per passare file tra job si usano i **workspace** (simili ai workspace Tekton, ma basati su storage temporaneo CircleCI, non PVC Kubernetes):

```
Job build   ──persist_to_workspace──► workspace (storage temporaneo)
Job test    ──attach_workspace──────► legge gli artifact di build
Job deploy  ──attach_workspace──────► legge il binario/immagine da deployare
```

## Configurazione & Pratica

### 1. Struttura Base — `config.yml` con Orbs ed Executors

```yaml
# .circleci/config.yml
version: 2.1

# Le versioni degli orb sono esempi: verificare l'ultima nel Registry e pinnare sempre una versione esatta
orbs:
  node: circleci/node@5.2.0          # Orb pubblico: setup Node.js, cache automatica
  aws-cli: circleci/aws-cli@4.1.3     # Orb pubblico: configurazione AWS CLI
  slack: circleci/slack@4.13.3        # Orb pubblico: notifiche Slack

executors:
  node-medium:
    docker:
      - image: cimg/node:20.11
    resource_class: medium

  docker-build:
    machine:
      image: ubuntu-2404:current       # Machine executor con Docker daemon nativo (preferire tag `current`/datati recenti)
      docker_layer_caching: true       # DLC su machine: si abilita qui, non con setup_remote_docker
    resource_class: medium

jobs:
  lint-and-test:
    executor: node-medium
    steps:
      - checkout
      - node/install-packages:          # Step definito dall'orb node — cache automatica npm/yarn
          pkg-manager: npm
      - run:
          name: Lint
          command: npm run lint
      - run:
          name: Unit tests con coverage
          command: npm test -- --coverage --ci
      - store_test_results:             # Mostra risultati nella UI CircleCI
          path: test-results
      - store_artifacts:
          path: coverage
          destination: coverage-report

  build-image:
    executor: docker-build
    steps:
      - checkout
      # Nessun setup_remote_docker: serve solo con executor `docker`. Su `machine` il daemon è già locale.
      - run:
          name: Build e push immagine
          command: |
            docker build -t "$AWS_ECR_REGISTRY/myapp:${CIRCLE_SHA1}" .
            docker push "$AWS_ECR_REGISTRY/myapp:${CIRCLE_SHA1}"

workflows:
  ci-pipeline:
    jobs:
      - lint-and-test
      - build-image:
          requires: [lint-and-test]     # Fan-in: build solo dopo lint+test ok
          filters:
            branches:
              only: [main, /release\/.*/]
```

```yaml
# Uso di contexts per secret condivisi tra progetti (definiti in Org Settings > Contexts)
workflows:
  deploy-prod:
    jobs:
      - build-image
      - hold-for-approval:
          type: approval               # Job manuale — richiede click in UI/API
          requires: [build-image]
      - deploy:
          requires: [hold-for-approval]
          context: [aws-production]    # Inietta env var/secret dal Context "aws-production"
          filters:
            branches:
              only: main
```

### 2. Workflows Avanzati — Fan-out/Fan-in, Matrix, Scheduled

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  test-matrix:
    parameters:
      node-version:
        type: string
    docker:
      - image: cimg/node:<< parameters.node-version >>
    resource_class: small
    steps:
      - checkout
      - run: npm ci
      - run: npm test

  build:
    docker:
      - image: cimg/base:2024.01
    resource_class: medium
    steps:
      - checkout
      - run: echo "Build eseguito dopo tutta la matrix"

workflows:
  matrix-and-schedule:
    jobs:
      # Fan-out: genera 3 job paralleli, uno per versione Node
      - test-matrix:
          matrix:
            parameters:
              node-version: ["18.19", "20.11", "22.1"]

      # Fan-in: build parte solo quando TUTTI i job matrix completano
      - build:
          requires: [test-matrix]

  nightly-tests:
    triggers:
      - schedule:
          cron: "0 2 * * *"            # Ogni notte alle 02:00 UTC
          filters:
            branches:
              only: main
    jobs:
      - test-matrix:
          matrix:
            parameters:
              node-version: ["20.11"]
```

!!! note "Scheduled workflow vs scheduled pipeline"
    `triggers: schedule` nel `config.yml` è l'approccio legacy: CircleCI raccomanda i **scheduled pipelines** (Project Settings > Triggers, o API), che vivono fuori dal config, supportano parametri di pipeline e non richiedono un commit per cambiare l'orario.

### 3. Dynamic Config — Setup Workflows e Continuation Orb

Utile in monorepo dove si vuole generare la pipeline a runtime in base ai file modificati, evitando di eseguire job per servizi non toccati.

```yaml
# .circleci/config.yml — config "setup" iniziale, minimale
version: 2.1

setup: true                            # Abilita dynamic config

orbs:
  continuation: circleci/continuation@1.0.0
  path-filtering: circleci/path-filtering@1.1.1

workflows:
  generate-config:
    jobs:
      - path-filtering/filter:
          base-revision: main
          config-path: .circleci/continue-config.yml
          mapping: |
            services/api/.*      run-api-pipeline    true
            services/frontend/.* run-frontend-pipeline true
```

```yaml
# .circleci/continue-config.yml — generata/selezionata a runtime
version: 2.1

parameters:
  run-api-pipeline:
    type: boolean
    default: false
  run-frontend-pipeline:
    type: boolean
    default: false

jobs:
  build-api:
    docker:
      - image: cimg/openjdk:21.0
    steps:
      - checkout
      - run: cd services/api && mvn package

workflows:
  api:
    when: << pipeline.parameters.run-api-pipeline >>
    jobs:
      - build-api
```

```bash
# Alternativa manuale senza orb path-filtering: script + continuation API.
# L'autenticazione è la continuation-key (no Circle-Token); jq gestisce l'escaping del YAML.
# Il continuation-key è disponibile nel job setup come $CIRCLE_CONTINUATION_KEY
# (con `setup: true` l'orb continuation fa già tutto questo).
jq -n --arg key "$CIRCLE_CONTINUATION_KEY" --rawfile cfg generated-config.yml \
  '{"continuation-key": $key, "configuration": $cfg}' \
| curl -X POST https://circleci.com/api/v2/pipeline/continue \
    -H "Content-Type: application/json" \
    -d @-
```

### 4. Caching — `save_cache`/`restore_cache` con Chiavi su Checksum

```yaml
jobs:
  test-with-cache:
    docker:
      - image: cimg/node:20.11
    resource_class: medium
    steps:
      - checkout
      - restore_cache:
          keys:
            # Chiave primaria: checksum esatto di package-lock.json
            - node-deps-v1-{{ checksum "package-lock.json" }}
            # Fallback: prefix match, la cache più recente con quel prefisso (qualsiasi branch)
            - node-deps-v1-
      - run: npm ci
      - save_cache:
          key: node-deps-v1-{{ checksum "package-lock.json" }}
          paths:
            - node_modules
            - ~/.npm
```

!!! note "Differenza rispetto a GitHub Actions cache"
    GitHub Actions (`actions/cache`) gestisce automaticamente l'eviction e ha un limite di 10 GB per repo con LRU eviction cross-workflow. CircleCI invece richiede gestione manuale del versionamento chiave (es. `v1`, `v2` nel nome) per invalidare cache corrotte o obsolete — non c'è eviction automatica intelligente, e cache vecchie continuano ad accumularsi finché non scadono (15 giorni di default) o non si esaurisce lo storage del piano.

### 5. Self-Hosted Runner

```yaml
# .circleci/config.yml — job su self-hosted runner
version: 2.1

jobs:
  test-on-prem:
    machine: true                      # Richiesto per i runner self-hosted
    resource_class: my-namespace/gpu-runner-pool   # Nome del resource class registrato
    steps:
      - checkout
      - run:
          name: Test su hardware con GPU dedicata
          command: ./run-gpu-tests.sh

workflows:
  on-prem-tests:
    jobs:
      - test-on-prem
```

```bash
# 1. Crea la resource class e genera il token di autenticazione del runner (mostrato una volta sola)
circleci runner resource-class create my-namespace/gpu-runner-pool "Runner GPU on-prem" --generate-token

# 2. Installa il runner sull'host (machine runner 3: pacchetto/servizio systemd) e inserisci il token
#    nel suo file di config (runner.api.auth_token). Per Kubernetes esiste il container runner via Helm.
#    Procedura aggiornata: https://circleci.com/docs/runner-installation-cli/

# 3. Verifica registrazione
circleci runner resource-class list my-namespace
circleci runner instance list my-namespace/gpu-runner-pool
```

## Best Practices

### Contexts e Sicurezza dei Secret

!!! warning "Non metter secret direttamente in `config.yml`"
    Secret e credenziali vanno definiti come **Project Environment Variables** (scope singolo progetto) o **Contexts** (scope condiviso tra progetti, con restrizione per gruppo/team) nella UI/API CircleCI — mai hardcoded nel file versionato, nemmeno in branch privati.

```yaml
# Context con restrizione di accesso (configurato in Org Settings > Contexts)
# Solo i membri del team "platform-team" possono usare il context "aws-production"
workflows:
  deploy:
    jobs:
      - deploy-prod:
          context: [aws-production]
          filters:
            branches:
              only: main
```

### OIDC per Cloud Provider — No Static Credentials

```yaml
jobs:
  deploy-aws-oidc:
    docker:
      - image: cimg/aws:2024.01
    steps:
      - checkout
      - run:
          name: Assume ruolo AWS via OIDC (nessuna access key statica)
          command: |
            aws configure set default.region eu-west-1
            CREDS=$(aws sts assume-role-with-web-identity \
              --role-arn "$AWS_ROLE_ARN" \
              --role-session-name "circleci-${CIRCLE_WORKFLOW_ID}" \
              --web-identity-token "$CIRCLE_OIDC_TOKEN" \
              --duration-seconds 900)
            export AWS_ACCESS_KEY_ID=$(echo $CREDS | jq -r .Credentials.AccessKeyId)
            export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | jq -r .Credentials.SecretAccessKey)
            export AWS_SESSION_TOKEN=$(echo $CREDS | jq -r .Credentials.SessionToken)
            aws s3 sync ./dist s3://my-bucket/
```

!!! tip "Preferire sempre OIDC a static credentials"
    Con OIDC il token `CIRCLE_OIDC_TOKEN` è generato automaticamente per job, ha scadenza breve (minuti) ed è verificabile dal cloud provider tramite trust policy — elimina il rischio di access key AWS statiche esposte in log o compromesse a lungo termine. Configurare l'OIDC identity provider lato AWS/GCP una sola volta (trust relationship con `https://oidc.circleci.com/org/<org-id>`).

### Resource Class — Dimensionamento Corretto

**1. Non usare `xlarge`/`2xlarge` per job I/O-bound.** Un job che aspetta principalmente rete (npm install, docker pull) non beneficia di più CPU — sprecare credit senza guadagno di velocità.

**2. Usare `docker_layer_caching: true` solo su job che buildano immagini frequentemente.** DLC ha un costo aggiuntivo in credit; su progetti con build immagine rara il risparmio di tempo non compensa il costo.

**3. Job paralleli con `parallelism` per test suite grandi.**

```yaml
jobs:
  test-parallel:
    docker:
      - image: cimg/node:20.11
    resource_class: medium
    parallelism: 4                     # Split automatico dei test su 4 container
    steps:
      - checkout
      - run: npm ci
      - run:
          command: |
            # split-by=timings usa lo storico di store_test_results (JUnit): senza, ricade su split per nome
            TESTFILES=$(circleci tests glob "test/**/*.test.js" | circleci tests split --split-by=timings)
            npx jest $TESTFILES
```

## Troubleshooting

### Problema: Job bloccato su "Queued" senza avviarsi

**Sintomo:** Il job resta in stato `Queued` per minuti, nessun executor viene assegnato.

**Causa 1:** Limite di concorrenza del piano raggiunto (numero massimo di job paralleli esauriti).

```bash
# Pipeline recenti del progetto via API (stato dei workflow: running/on_hold...)
curl -H "Circle-Token: $CIRCLE_TOKEN" \
  "https://circleci.com/api/v2/project/gh/my-org/my-repo/pipeline?branch=main"
# La saturazione della concorrenza si vede in UI: Plan > Usage

# Soluzione: aumentare il piano, oppure ridurre parallelism/matrix concorrenti,
# oppure serializzare workflow non urgenti con "requires" artificiali
```

**Causa 2:** Self-hosted runner offline o resource_class non registrata correttamente.

```bash
circleci runner resource-class list my-namespace
# Se il runner non appare: verificare token e connettività del processo runner
docker logs circleci-runner
```

---

### Problema: `setup_remote_docker` — build lenta o fallisce con timeout di rete

**Sintomo:** `docker build`/`docker push` con executor `docker` + `setup_remote_docker` sono molto più lenti che in locale, o falliscono con `dial tcp: lookup ... timeout`.

**Causa:** Il Docker remoto (setup_remote_docker) gira su un host separato dal job container — il networking tra i due introduce latenza, e senza Docker Layer Caching ogni layer viene rebuildato da zero.

```yaml
# Soluzione: abilitare DLC e minimizzare il context di build
# (alternativa: passare a executor `machine`, daemon locale, senza hop di rete)
steps:
  - setup_remote_docker:
      docker_layer_caching: true
      version: 24.0.7
  - run:
      command: |
        # Usare .dockerignore per ridurre il context trasferito al daemon remoto
        docker build --progress=plain -t myapp:${CIRCLE_SHA1} .
```

---

### Problema: Cache non invalidata dopo update di `package-lock.json`

**Sintomo:** `npm ci` installa dipendenze vecchie nonostante il lockfile sia stato aggiornato nel commit.

**Causa:** La chiave di cache non include il checksum corretto, oppure la fallback key (prefix match) recupera una cache più vecchia prima che venga generata quella nuova.

```yaml
# ❌ Sbagliato: chiave statica, non invalida mai
- restore_cache:
    keys: [node-deps]

# ✅ Corretto: checksum del lockfile nella chiave primaria
- restore_cache:
    keys:
      - node-deps-v2-{{ checksum "package-lock.json" }}
      - node-deps-v2-          # fallback solo se manca match esatto
- run: npm ci
- save_cache:
    key: node-deps-v2-{{ checksum "package-lock.json" }}
    paths: [node_modules]
```

---

### Problema: Context non disponibile — job fallisce con variabili vuote

**Sintomo:** `deploy` fallisce con `AWS_ACCESS_KEY_ID: unbound variable` o simile, nonostante il Context sia configurato.

**Causa:** Il Context non è stato associato al workflow/job (`context:` mancante nello YAML), oppure l'utente/team che ha triggerato la pipeline non ha i permessi di accesso al Context (restrizione per security group).

```bash
# Verificare i Context disponibili per l'org
curl -H "Circle-Token: $CIRCLE_TOKEN" \
  "https://circleci.com/api/v2/context?owner-id=$ORG_ID"

# Verificare i restriction group associati al context
curl -H "Circle-Token: $CIRCLE_TOKEN" \
  "https://circleci.com/api/v2/context/$CONTEXT_ID/restrictions"
```

```yaml
# Assicurarsi che il job dichiari il context esplicitamente nel workflow
workflows:
  deploy:
    jobs:
      - deploy-prod:
          context: [aws-production]   # deve combaciare col nome esatto configurato in UI
```

---

### Problema: Dynamic config — pipeline continuation fallisce silenziosamente

**Sintomo:** Il job `setup` completa senza errori ma nessun job successivo viene eseguito; la pipeline appare "vuota" nella UI.

**Causa:** Il file di config generato è vuoto (nessun servizio modificato secondo `path-filtering`) e non è stato gestito il caso base, oppure la continuation API ha ricevuto YAML malformato.

```yaml
# continue-config.yml deve avere sempre almeno un job/workflow valido
# Aggiungere un placeholder per il caso "nessuna modifica rilevata"
workflows:
  no-op:
    when:
      not:
        or:
          - << pipeline.parameters.run-api-pipeline >>
          - << pipeline.parameters.run-frontend-pipeline >>
    jobs:
      - noop-placeholder

jobs:
  noop-placeholder:
    docker:
      - image: cimg/base:2024.01
    steps:
      - run: echo "Nessun servizio modificato, pipeline no-op"
```

## Relazioni

??? info "GitHub Actions — Alternativa integrata nel code hosting"
    GitHub Actions offre integrazione nativa con GitHub (nessun servizio terzo, secret condivisi con i repo settings) e un marketplace di action più ampio dell'ecosistema orbs. CircleCI mantiene il vantaggio su resource_class granulare e self-hosted runner più maturi per workload non-container. Scegliere in base a dove vive già il codice e alla necessità di controllo fine sulle risorse macchina.

    **Approfondimento completo →** [GitHub Actions](../github-actions/_index.md)

??? info "GitLab CI — Alternativa integrata, DAG e compliance framework"
    GitLab CI offre DAG nativo (`needs`), compliance framework enterprise e merge trains — funzionalità che CircleCI non replica nativamente. CircleCI resta preferibile per progetti multi-code-host o quando serve setup più rapido senza self-hosting di GitLab.

    **Approfondimento completo →** [GitLab CI](../gitlab-ci/_index.md)

??? info "Pipeline Security — Secret scoping e OIDC"
    I principi di secret management (least privilege, rotazione, no static credential) si applicano identicamente su CircleCI Contexts/OIDC, GitHub Actions Environments/OIDC e GitLab CI Protected Variables.

    **Approfondimento completo →** [Pipeline Security](../strategie/pipeline-security.md)

## Riferimenti

- [CircleCI — Documentazione ufficiale](https://circleci.com/docs/)
- [CircleCI Orb Registry](https://circleci.com/developer/orbs)
- [Resource classes reference](https://circleci.com/docs/configuration-reference/#resource_class)
- [Dynamic config](https://circleci.com/docs/dynamic-config/)
- [Self-hosted runner](https://circleci.com/docs/runner-overview/)
- [OIDC token authentication](https://circleci.com/docs/openid-connect-tokens/)
- [Contexts](https://circleci.com/docs/contexts/)
- [Caching strategy](https://circleci.com/docs/caching/)
