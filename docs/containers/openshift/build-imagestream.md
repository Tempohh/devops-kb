---
title: "Build e ImageStream"
slug: build-imagestream
category: containers
tags: [openshift, buildconfig, imagestream, s2i, tekton, image-promotion, binary-build]
search_keywords: [openshift BuildConfig, S2I source to image, openshift ImageStream, openshift image promotion, openshift tekton pipelines, openshift binary build, openshift docker strategy build, openshift imagestream tag, openshift image trigger, openshift build webhook]
parent: containers/openshift/_index
related: [containers/openshift/gitops-pipelines, containers/registry/_index]
official_docs: https://docs.openshift.com/container-platform/latest/cicd/builds/understanding-buildconfigs.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Build e ImageStream

## S2I — Source-to-Image

**S2I (Source-to-Image)** è il meccanismo di build nativo OpenShift che converte il codice sorgente direttamente in un'immagine OCI, senza richiedere un Dockerfile.

```
S2I Build Process

  Source Code (Git / directory locale)
       |
       v
  Builder Image (es. registry.access.redhat.com/ubi9/python-312)
  +-------------------------------------------------------+
  |  1. Clona il codice sorgente in /tmp/src              |
  |  2. Chiama scripts S2I:                               |
  |     /usr/libexec/s2i/assemble   ← installa deps,      |
  |                                    compila, configura  |
  |     /usr/libexec/s2i/run        ← entrypoint finale   |
  |  3. Committa il risultato come nuovo layer            |
  +-------------------------------------------------------+
       |
       v
  Output Image (application container)
  Contiene: runtime + codice compilato + dipendenze

  Vantaggi S2I:
  ✓ Developer non deve conoscere Docker/Dockerfile
  ✓ Builder image gestita centralmente dal platform team
  ✓ Security: lo script assemble gira come utente non-root della builder image
  ✓ Riproducibilità: stesso builder → stesso risultato
```

**Builder Images disponibili:**

```bash
# Lista builder images nel cluster
oc get is -n openshift | grep -v NAME | awk '{print $1}' | head -20
# nodejs    python    java    ruby    php    golang    dotnet    nginx ...

# Dettaglio di una builder image (tutti i tag disponibili)
oc describe is python -n openshift
# Tags:
#   3.11 → registry.redhat.io/ubi9/python-311:latest
#   3.12 → registry.redhat.io/ubi9/python-312:latest
```

---

## BuildConfig — Definizione del Build

```yaml
# BuildConfig con strategia S2I
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: myapp
  namespace: production
spec:
  # ── Source ────────────────────────────────────────────
  source:
    type: Git
    git:
      uri: https://github.com/company/myapp.git
      ref: main
    contextDir: /backend        # subdirectory del repo
    secrets:
      - secret:
          name: github-token    # credenziali per repo privato
        destinationDir: /etc/secrets

  # ── Strategia Build ───────────────────────────────────
  strategy:
    type: Source              # Source (S2I) | Docker | Custom
    sourceStrategy:
      from:
        kind: ImageStreamTag
        namespace: openshift
        name: python:3.12
      env:
        - name: PIP_INDEX_URL
          value: https://pypi.company.com/simple
      incremental: true       # riusa cache del build precedente (se supportato)
      pullSecret:
        name: registry-secret

  # ── Output ────────────────────────────────────────────
  output:
    to:
      kind: ImageStreamTag
      name: myapp:latest      # pusha nell'ImageStream locale
    pushSecret:
      name: registry-secret
    imageLabels:
      - name: team
        value: platform       # label OCI statica aggiunta all'immagine prodotta

  # ── Trigger ───────────────────────────────────────────
  triggers:
    - type: ImageChange       # rebuild quando la builder image si aggiorna
      imageChange: {}
    - type: ConfigChange      # rebuild quando questo BuildConfig cambia
    - type: GitHub
      github:
        secretReference:
          name: webhook-secret   # Secret con chiave WebHookSecretKey (il campo `secret` in chiaro è deprecato)
    - type: Generic
      generic:
        secretReference:
          name: webhook-secret
        allowEnv: true        # permette di passare env vars via webhook

  # ── Post-Build Hook ───────────────────────────────────
  postCommit:
    script: "python -m pytest tests/"   # esegue test dopo il build

  # ── Risorse del build ─────────────────────────────────
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "2"
      memory: "4Gi"

  # ── Retention ─────────────────────────────────────────
  successfulBuildsHistoryLimit: 5
  failedBuildsHistoryLimit: 5
  runPolicy: Serial           # Serial | Parallel | SerialLatestOnly
```

**BuildConfig con Dockerfile strategy:**

```yaml
strategy:
  type: Docker
  dockerStrategy:
    from:
      kind: ImageStreamTag
      name: ubi9:latest
      namespace: openshift
    dockerfilePath: Dockerfile.prod    # path relativo al contextDir
    buildArgs:
      - name: APP_VERSION
        value: "1.0.0"
    noCache: false
    forcePull: true     # ri-pull l'immagine base sempre
```

**Binary Build — Deploy rapido da artefatti locali:**

```bash
# Build da directory locale (no Git)
oc start-build myapp \
    --from-dir=./src \
    --follow \
    --wait

# Build da file tar
oc start-build myapp \
    --from-archive=./myapp-1.0.0.tar.gz \
    --follow

# Build da Dockerfile locale
oc start-build myapp \
    --from-file=./Dockerfile \
    --follow

# Build con variabile d'ambiente / build-arg di override (Docker strategy)
oc start-build myapp \
    --from-dir=./src \
    --env=APP_ENV=dev \
    --build-arg=APP_VERSION=1.0.1
```

!!! note "BuildConfig vs Builds for OpenShift (Shipwright)"
    `BuildConfig` (API `build.openshift.io/v1`) resta supportato, ma l'evoluzione della piattaforma è **Builds for Red Hat OpenShift** (basato su Shipwright: `Build`/`BuildRun` con strategie `buildah`, `source-to-image`) e OpenShift Pipelines. Per nuovi progetti valuta queste alternative; `BuildConfig` è ancora comune nei cluster esistenti.

---

## ImageStream — Astrazione del Registry

Un **ImageStream** è un puntatore virtuale alle immagini, disaccoppiando i deployment dall'URL fisico del registry.

```
ImageStream — Come funziona

  Registry esterno:          ImageStream:              Deployment:
  quay.io/company/           myapp (IS in production)  image: myapp:production
  myapp:v1.0.0       →       tag: production    →       (trigger: quando IS cambia)
  myapp:v1.1.0               tag: staging
  myapp:v1.2.0               tag: latest

  Quando il Platform Team fa "promote v1.2.0 a production":
  oc tag myapp:staging myapp:production
  → Tutti i Deployment che hanno un trigger ImageChange
    vengono automaticamente re-rollati!
```

```yaml
# ImageStream definition
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: myapp
  namespace: production
spec:
  lookupPolicy:
    local: true     # permette di usare il nome dell'IS nei Pod direttamente
  tags:
    - name: latest
      from:
        kind: DockerImage
        name: quay.io/company/myapp:latest
      importPolicy:
        importMode: PreserveOriginal
        scheduled: true        # controlla periodicamente nuove versioni
      referencePolicy:
        type: Local            # usa il registry interno (proxy)
```

```bash
# Comandi ImageStream
oc get imagestream -n production
oc describe imagestream myapp -n production   # mostra tutti i tag e digest

# Promuovi un'immagine da staging a production
oc tag myapp:staging myapp:production -n production
# → trigger automatico su Deployment che watchano myapp:production

# Importa un'immagine da registry esterno
oc import-image myapp:v1.2.0 \
    --from=quay.io/company/myapp:v1.2.0 \
    --confirm \
    -n production

# Import periodico di un tag (intervallo di default del cluster: 15 min)
oc tag quay.io/company/myapp:latest myapp:latest --scheduled -n production

# Permette di usare il nome dell'IS direttamente nei Pod (lookupPolicy.local)
oc set image-lookup myapp -n production

# Lista i build che hanno generato un'immagine
oc get builds -n production | grep myapp
```

---

## Image Promotion Workflow

```
Image Promotion Pipeline

  dev → staging → production

  1. Developer fa push su feature branch
  2. OpenShift Pipelines (Tekton) triggerano un build
  3. Immagine pushata in: myapp:dev-<commit-sha>
  4. Test automatici girano
  5. Merge su main → immagine in: myapp:staging
  6. QA sign-off → promote a production:
     oc tag myapp:staging myapp:production
  7. Deployment in production con rollout automatico

  Promozione immutabile (per digest):
  DIGEST=$(oc get istag myapp:staging -o jsonpath='{.image.metadata.name}')
  oc tag myapp@$DIGEST myapp:production
  # → production punta esattamente allo stesso digest di staging.
  # Anche "oc tag myapp:staging myapp:production" copia il digest corrente,
  # ma NON segue staging in futuro (a meno di --alias): è una promozione puntuale.
```

---

## Tekton Pipelines Integration

OpenShift Pipelines (basato su Tekton) è il modo moderno per build e deploy su OpenShift.

```yaml
# Pipeline per build e deploy
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: build-and-deploy
  namespace: production
spec:
  params:
    - name: git-url
      type: string
    - name: image-name
      type: string

  tasks:
    # 1. Clone sorgente
    - name: fetch-source
      taskRef:
        resolver: cluster
        params:
          - {name: kind, value: task}
          - {name: name, value: git-clone}
          - {name: namespace, value: openshift-pipelines}
      params:
        - {name: url, value: "$(params.git-url)"}
      workspaces:
        - {name: output, workspace: shared-workspace}

    # 2. Build immagine con Buildah (no Docker daemon necessario)
    - name: build-image
      runAfter: [fetch-source]
      taskRef:
        resolver: cluster
        params:
          - {name: kind, value: task}
          - {name: name, value: buildah}
          - {name: namespace, value: openshift-pipelines}
      params:
        - {name: IMAGE, value: "$(params.image-name)"}
        - {name: DOCKERFILE, value: ./Dockerfile}
      workspaces:
        - {name: source, workspace: shared-workspace}

    # 3. Deploy (aggiorna ImageStream tag)
    - name: promote-image
      runAfter: [build-image]
      taskRef:
        resolver: cluster       # ClusterTask è deprecato/rimosso nelle versioni recenti di OpenShift Pipelines
        params:
          - {name: kind, value: task}
          - {name: name, value: openshift-client}
          - {name: namespace, value: openshift-pipelines}
      params:
        - name: SCRIPT
          value: |
            oc tag $(params.image-name):latest $(params.image-name):production

  workspaces:
    - name: shared-workspace

---
# PipelineRun trigger tramite webhook (EventListener)
apiVersion: triggers.tekton.dev/v1beta1
kind: EventListener
metadata:
  name: github-webhook
spec:
  triggers:
    - name: push-trigger
      interceptors:
        - ref:
            name: github
          params:
            - {name: secretRef, value: {secretName: github-webhook-secret, secretKey: secret}}
            - {name: eventTypes, value: [push]}
      bindings:
        - ref: github-push-binding
      template:
        ref: build-deploy-template
```

---

## Troubleshooting

### Scenario 1 — Build bloccato in stato `New` o `Pending`

**Sintomo:** `oc get builds` mostra il build fermo in `New` o `Pending` per diversi minuti senza avanzare.

**Causa:** Nessun nodo disponibile con risorse sufficienti per il build pod, oppure il pull della builder image sta fallendo per problemi di autenticazione al registry.

**Soluzione:**

```bash
# Controlla lo stato del build e descrivi il pod
oc describe build myapp-1 -n production

# Trova il build pod e controlla gli eventi
BUILD_POD=$(oc get pods -n production | grep "myapp-1-build" | awk '{print $1}')
oc describe pod $BUILD_POD -n production | grep -A 10 Events

# Verifica che il pull secret sia correttamente configurato
oc get buildconfig myapp -o jsonpath='{.spec.strategy.sourceStrategy.pullSecret}' -n production

# Forza il re-import della builder image
oc import-image python:3.12 -n openshift --confirm
```

---

### Scenario 2 — Build fallisce con errore `assemble` script (S2I)

**Sintomo:** Il log del build mostra errori durante la fase `assemble`, ad esempio dipendenze non trovate o errori di compilazione.

**Causa:** Dipendenze mancanti nel sorgente, versione incompatibile della builder image, o variabili d'ambiente S2I non configurate (es. `PIP_INDEX_URL` sbagliato).

**Soluzione:**

```bash
# Visualizza il log completo del build
oc logs build/myapp-1 -n production --follow

# Verifica le env vars configurate nel BuildConfig
oc get bc myapp -o jsonpath='{.spec.strategy.sourceStrategy.env}' -n production

# Avvia un build con override di una variabile d'ambiente per test
oc start-build myapp \
    --env=PIP_INDEX_URL=https://pypi.org/simple \
    --follow -n production

# Debug interattivo: esegui un pod con la builder image per testare assemble
oc run debug-s2i --image=registry.access.redhat.com/ubi9/python-312 \
    --rm -it --restart=Never -- bash
```

---

### Scenario 3 — ImageStream non propaga il trigger al Deployment

**Sintomo:** Dopo `oc tag myapp:staging myapp:production`, il Deployment non fa rollout automatico. I pod continuano a girare con la vecchia immagine.

**Causa:** Il Deployment non ha un trigger ImageStream configurato, oppure il trigger punta a un nome ImageStreamTag errato. Con `Deployment` il trigger è l'annotation `image.openshift.io/triggers` e va configurato esplicitamente. `DeploymentConfig` è deprecato (dalla 4.14): per i nuovi workload usa `Deployment`.

**Soluzione:**

```bash
# Verifica l'annotation di trigger sul Deployment
oc get deploy myapp -o jsonpath='{.metadata.annotations.image\.openshift\.io/triggers}' -n production

# (solo legacy) trigger su un DeploymentConfig
oc get dc myapp -o jsonpath='{.spec.triggers}' -n production

# Per Deployment standard: imposta il trigger ImageStream (scrive l'annotation)
oc set triggers deploy/myapp \
    --from-image=myapp:production \
    --containers=myapp \
    -n production

# Controlla che l'ImageStreamTag sia stato aggiornato correttamente
oc get istag myapp:production -n production \
    -o jsonpath='{.image.metadata.name}'

# Forza rollout manuale se necessario
oc rollout restart deploy/myapp -n production
# (legacy DeploymentConfig: oc rollout latest dc/myapp)
```

---

### Scenario 4 — Pipeline Tekton fallisce con errore `permission denied` su Buildah

**Sintomo:** Il task `buildah` nella Tekton Pipeline fallisce con errori tipo `error creating build container: ... permission denied` o `error mounting /proc` (Buildah non usa un daemon: l'errore viene dal runtime nel pod).

**Causa:** Il ServiceAccount della PipelineRun non ha una SCC che consenta al task di girare con le capability richieste (es. `SETFCAP`). Il SA `pipeline`, creato dall'operator in ogni namespace, di norma ha già la SCC dedicata `pipelines-scc`; il problema compare con un SA custom o con SCC modificate.

**Soluzione:**

```bash
# Verifica il ServiceAccount usato dalla Pipeline
oc get pipelinerun myapp-run-1 -o jsonpath='{.spec.taskRunTemplate.serviceAccountName}' -n production

# Preferibile: concedi la SCC dedicata di OpenShift Pipelines al SA custom
oc adm policy add-scc-to-user pipelines-scc -z my-pipeline-sa -n production

# Ultima risorsa (ampia superficie d'attacco, evitare in produzione):
# oc adm policy add-scc-to-user privileged -z my-pipeline-sa -n production

# Se l'overlay storage non funziona, nel task Buildah:
# params:
#   - name: STORAGE_DRIVER
#     value: vfs   # più lento, ma non richiede supporto kernel overlay

# Verifica che OpenShift Pipelines operator sia aggiornato
oc get csv -n openshift-pipelines | grep pipelines
```

---

## Riferimenti

- [BuildConfig](https://docs.openshift.com/container-platform/latest/cicd/builds/understanding-buildconfigs.html)
- [S2I](https://docs.openshift.com/container-platform/latest/cicd/builds/build-strategies.html#builds-strategy-s2i-build_build-strategies)
- [ImageStream](https://docs.openshift.com/container-platform/latest/openshift_images/image-streams-manage.html)
- [OpenShift Pipelines (Tekton)](https://docs.openshift.com/pipelines/latest/create/creating-applications-with-cicd-pipelines.html)
