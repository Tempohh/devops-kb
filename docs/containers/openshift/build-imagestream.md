---
title: "Build e ImageStream"
slug: build-imagestream
category: containers
tags: [openshift, buildconfig, imagestream, s2i, tekton, image-promotion, binary-build]
search_keywords: [openshift BuildConfig, S2I source to image, openshift ImageStream, openshift image promotion, openshift tekton pipelines, openshift binary build, openshift docker strategy build, openshift imagestream tag, openshift image trigger, openshift build webhook]
parent: containers/openshift/_index
related: [containers/openshift/gitops-pipelines, containers/registry/_index]
official_docs: https://docs.openshift.com/container-platform/latest/cicd/builds/understanding-buildconfigs.html
status: complete
difficulty: advanced
last_updated: 2026-02-25
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
  ✓ Security: build non esegue come root
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
      - name: build-date
        value: ""             # popolato dinamicamente dal builder

  # ── Trigger ───────────────────────────────────────────
  triggers:
    - type: ImageChange       # rebuild quando la builder image si aggiorna
      imageChange: {}
    - type: ConfigChange      # rebuild quando questo BuildConfig cambia
    - type: GitHub
      github:
        secret: webhook-secret
    - type: Generic
      generic:
        secret: webhook-secret
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

# Build con override dell'immagine di destinazione
oc start-build myapp \
    --from-dir=./src \
    --to=myregistry.company.com/myapp:dev
```

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

# Policy di importazione periodica (ogni 15m)
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

  Promozione via tag (immutabile tramite digest):
  SOURCE_DIGEST=$(oc get istag myapp:staging -o jsonpath='{.image.dockerImageReference}')
  oc tag --source=docker $SOURCE_DIGEST myapp:production
  # → production punta esattamente allo stesso digest di staging
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
        kind: ClusterTask
        name: openshift-client
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

## Riferimenti

- [BuildConfig](https://docs.openshift.com/container-platform/latest/cicd/builds/understanding-buildconfigs.html)
- [S2I](https://docs.openshift.com/container-platform/latest/cicd/builds/build-strategies.html#builds-strategy-s2i-build_build-strategies)
- [ImageStream](https://docs.openshift.com/container-platform/latest/openshift_images/image-streams-manage.html)
- [OpenShift Pipelines (Tekton)](https://docs.openshift.com/pipelines/latest/create/creating-applications-with-cicd-pipelines.html)
