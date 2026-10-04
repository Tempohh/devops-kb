---
title: "GitOps e Pipelines"
slug: gitops-pipelines
category: containers
tags: [openshift, gitops, argocd, tekton, pipelines, cicd, image-promotion]
search_keywords: [openshift gitops ArgoCD, openshift pipelines tekton, ArgoCD ApplicationSet, tekton pipeline, openshift eventlistener, gitops app of apps, sync waves ArgoCD, openshift CI/CD, tekton task, argocd sync policy, gitops multi-cluster, openshift pipeline triggers]
parent: containers/openshift/_index
related: [containers/openshift/build-imagestream, containers/helm/deployment-produzione]
official_docs: https://docs.openshift.com/gitops/latest/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# GitOps e Pipelines

## OpenShift GitOps — ArgoCD Integrato

**OpenShift GitOps** è l'Operator ufficiale che installa e gestisce ArgoCD su OpenShift. Integra ArgoCD con il RBAC OpenShift e l'OAuth Server.

```bash
# Installazione via OLM (OpenShift GitOps Operator)
oc apply -f - <<'EOF'
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-gitops-operator
  namespace: openshift-operators
spec:
  channel: latest
  name: openshift-gitops-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic   # in produzione: Manual + canale versionato (gitops-1.x) invece di latest
EOF

# L'operator installa automaticamente ArgoCD in openshift-gitops
oc get pods -n openshift-gitops
# NAME                                          READY   STATUS
# argocd-server-...                             1/1     Running
# argocd-repo-server-...                        1/1     Running
# argocd-application-controller-...             1/1     Running
# argocd-applicationset-controller-...          1/1     Running
# argocd-dex-server-...                         1/1     Running  ← SSO con OCP OAuth

# URL console ArgoCD
oc get route -n openshift-gitops openshift-gitops-server -o jsonpath='{.spec.host}'
```

---

## ArgoCD Application — Sincronizzazione Git

```yaml
# Application — sincronizza un path Git su un cluster/namespace
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: production-api
  namespace: openshift-gitops
  finalizers:
    - resources-finalizer.argocd.argoproj.io   # elimina risorse su app delete
spec:
  project: production

  source:
    repoURL: https://github.com/company/gitops.git
    targetRevision: main
    path: apps/production/api
    # Per Helm:
    # helm:
    #   valueFiles: [values.production.yaml]
    #   parameters: [{name: image.tag, value: "1.2.0"}]

  destination:
    server: https://kubernetes.default.svc   # cluster locale
    namespace: production

  syncPolicy:
    automated:
      prune: true          # elimina risorse rimosse da Git
      selfHeal: true       # ri-sincronizza se qualcuno modifica manualmente
      allowEmpty: false    # non elimina tutto se la dir Git è vuota
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground  # foreground delete (attende i child)
      - PruneLast=true                     # elimina solo alla fine dello sync
      - RespectIgnoreDifferences=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m

  # Ignora differenze su campi gestiti da altri
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas    # ignorato: gestito da HPA
    - group: ""
      kind: Secret
      jsonPointers:
        - /data             # ignorato: gestito da ESO (External Secrets)
```

---

## App of Apps — Gestire Molte Applicazioni

```yaml
# App of Apps — un'Application che gestisce altre Applications
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cluster-apps
  namespace: openshift-gitops
spec:
  source:
    repoURL: https://github.com/company/gitops.git
    targetRevision: main
    path: clusters/production/apps     # questa directory contiene altri Application manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: openshift-gitops
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

```
App of Apps — Struttura Git

  gitops/
  ├── clusters/
  │   └── production/
  │       └── apps/                    ← App of Apps
  │           ├── api-app.yaml         ← Application CRD
  │           ├── database-app.yaml    ← Application CRD
  │           └── monitoring-app.yaml  ← Application CRD
  └── apps/
      ├── production/
      │   ├── api/
      │   │   ├── deployment.yaml
      │   │   ├── service.yaml
      │   │   └── hpa.yaml
      │   └── database/
      │       ├── statefulset.yaml
      │       └── pvc.yaml
      └── staging/
          └── api/
              └── ...
```

---

## ApplicationSet — Multi-Cluster e Matrix

```yaml
# ApplicationSet — genera Applications da template
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: cluster-apps
  namespace: openshift-gitops
spec:
  generators:
    # Matrix generator: genera il prodotto cartesiano di clusters × apps
    - matrix:
        generators:
          # Generator 1: lista cluster
          - list:
              elements:
                - cluster: production
                  url: https://prod-api.company.com:6443
                - cluster: staging
                  url: https://staging-api.company.com:6443

          # Generator 2: scopre directory Git automaticamente
          - git:
              repoURL: https://github.com/company/gitops.git
              revision: main
              directories:
                - path: apps/*

  template:
    metadata:
      name: "{{cluster}}-{{path.basename}}"
      labels:
        cluster: "{{cluster}}"
    spec:
      project: "{{cluster}}"
      source:
        repoURL: https://github.com/company/gitops.git
        targetRevision: main
        path: "apps/{{path.basename}}"
        helm:
          valueFiles:
            - values.yaml
            - "values.{{cluster}}.yaml"    # override per cluster
      destination:
        server: "{{url}}"   # il cluster deve essere già registrato in ArgoCD (argocd cluster add / Secret cluster)
        namespace: "{{path.basename}}"
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

---

## Sync Waves — Ordine di Deploy

```yaml
# Sync Waves: le risorse con wave minore vengono applicate per prime
# Tutte le risorse dello stesso wave vengono applicate insieme
# Il sistema aspetta che la wave precedente sia healthy prima di procedere

# Wave 0 (default): deploy l'infrastruttura
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  annotations:
    argocd.argoproj.io/sync-wave: "0"

---
# Wave 1: database (la wave 2 parte solo quando lo StatefulSet è Healthy)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  annotations:
    argocd.argoproj.io/sync-wave: "1"

---
# Wave 2: applicazione (aspetta che DB sia ready)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  annotations:
    argocd.argoproj.io/sync-wave: "2"

---
# Wave 3: ingress (espone solo quando l'app è ready)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    argocd.argoproj.io/sync-wave: "3"
```

---

## OpenShift Pipelines (Tekton)

```yaml
# Task — unità atomica di lavoro
apiVersion: tekton.dev/v1
kind: Task
metadata:
  name: build-and-push
spec:
  params:
    - name: image
      type: string
    - name: dockerfile
      type: string
      default: Dockerfile

  workspaces:
    - name: source
      description: Source code workspace

  results:
    - name: digest
      description: Digest dell'immagine pushata

  steps:
    # Build + push nello STESSO step: ogni step è un container separato e lo
    # storage locale di Buildah (/var/lib/containers) non è condiviso tra step.
    # Il digest va scritto in $(results.*) o nel workspace, NON in /tmp (non condiviso).
    - name: build-push
      image: registry.redhat.io/ubi9/buildah:latest   # pinnare a un tag/digest in produzione
      securityContext:
        runAsUser: 0   # Buildah richiede UID 0 nel container: serve la SCC pipelines-scc (vedi Troubleshooting)
      script: |
        buildah build \
          --format=oci \
          -f $(params.dockerfile) \
          -t $(params.image) \
          $(workspaces.source.path)
        buildah push \
          --digestfile $(results.digest.path) \
          $(params.image)
        echo "Pushed: $(cat $(results.digest.path))"

!!! note "Firma delle immagini: usa Tekton Chains"
    Firmare con uno step `cosign` dentro il Task è fragile (le immagini cosign sono distroless, senza shell; il keyless richiede un'identità OIDC). Su OpenShift Pipelines la via supportata è **Tekton Chains**: osserva i TaskRun completati, firma immagini e attestation (provenance SLSA) senza modificare i Task.

---
# Pipeline — sequenza di Task (run-tests e git-update-deployment sono Task custom da definire)
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: build-sign-deploy
spec:
  params:
    - name: git-url
    - name: git-revision
      default: main
    - name: image-name

  workspaces:
    - name: source

  tasks:
    - name: git-clone
      taskRef:
        resolver: cluster
        params:
          - {name: kind, value: task}
          - {name: name, value: git-clone}
          - {name: namespace, value: openshift-pipelines}   # i ClusterTask sono rimossi: i Task di catalogo vivono qui
      params:
        - {name: url, value: "$(params.git-url)"}
        - {name: revision, value: "$(params.git-revision)"}
      workspaces:
        - {name: output, workspace: source}

    - name: unit-tests
      runAfter: [git-clone]
      taskRef:
        kind: Task
        name: run-tests
      workspaces:
        - {name: source, workspace: source}

    - name: build-push
      runAfter: [unit-tests]
      taskRef:
        kind: Task
        name: build-and-push
      params:
        - {name: image, value: "$(params.image-name):$(tasks.git-clone.results.commit)"}
      workspaces:
        - {name: source, workspace: source}

    - name: update-gitops
      runAfter: [build-push]
      taskRef:
        kind: Task
        name: git-update-deployment
      params:
        - {name: image, value: "$(params.image-name):$(tasks.git-clone.results.commit)"}
      # Aggiorna il tag dell'immagine nel repo GitOps
      # → ArgoCD rileva il cambio e fa il deploy automaticamente

  results:
    - name: image-digest
      value: "$(tasks.build-push.results.digest)"
```

!!! tip "Pipelines as Code"
    Per repository Git-centrici OpenShift Pipelines include **Pipelines as Code** (PaC): la pipeline vive in `.tekton/` nel repo e il webhook/GitHub App è gestito dall'operator, senza scrivere EventListener/TriggerTemplate a mano. È l'approccio preferito per i nuovi progetti; gli EventListener restano per integrazioni custom.

**EventListener — Trigger da webhook Git:**

```yaml
apiVersion: triggers.tekton.dev/v1beta1
kind: EventListener
metadata:
  name: github-push
  namespace: pipelines
spec:
  serviceAccountName: pipeline-trigger-sa
  triggers:
    - name: push-trigger
      interceptors:
        # Valida la firma HMAC del webhook (secret condiviso con GitHub)
        - ref:
            name: github
          params:
            - {name: secretRef, value: {secretName: github-secret, secretKey: secretToken}}
            - {name: eventTypes, value: [push]}
        # L'interceptor github NON ha un filtro "branches": si filtra con CEL
        - ref:
            name: cel
          params:
            - {name: filter, value: "body.ref == 'refs/heads/main'"}
      bindings:
        - ref: push-binding
      template:
        ref: build-pipeline-template
```

---

## Image Promotion GitOps-Style

```
GitOps Image Promotion Flow

  Feature Branch:
  1. Developer fa push → GitHub webhook → EventListener
  2. Pipeline: clone → test → build → push myapp:feature-abc123
  3. Open PR

  Merge su main:
  4. Pipeline: build → push myapp:main-<sha>
  5. Pipeline task "update-staging": PR automatica sul repo GitOps che
     aggiorna il tag nel path staging/ (es. `kustomize edit set image
     myapp=myapp:main-<sha>`, o modifica di values.yaml per Helm)
  6. ArgoCD rileva il cambio Git → sync automatico in staging

  Promotion a produzione:
  7. QA approva → merge PR GitOps da staging a production path
  8. ArgoCD sync automatico → deploy in produzione

  Audit trail completo: ogni deployment è tracciato in Git
```

---

## Troubleshooting

### Scenario 1 — ArgoCD Application bloccata in `OutOfSync` dopo sync

**Sintomo:** L'Application rimane `OutOfSync` anche dopo un sync manuale; il diff mostra differenze su campi non modificati (es. `spec.replicas`, `creationTimestamp`).

**Causa:** ArgoCD confronta il manifest Git con la risorsa live inclusi campi iniettati dal cluster (HPA, defaulting del webhook, controller). Questi campi non presenti in Git appaiono come drift.

**Soluzione:** Aggiungere `ignoreDifferences` nel manifest Application per i campi gestiti da altri controller.

```yaml
# Application — ignoreDifferences per campi gestiti da HPA e controller
ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers:
      - /spec/replicas        # gestito da HPA
      - /metadata/annotations # iniettato da admission webhook
  - group: ""
    kind: ServiceAccount
    jsonPointers:
      - /secrets              # iniettato dal token controller
```

```bash
# Forzare un hard-refresh (svuota la cache del repo server)
argocd app get production-api --hard-refresh

# Verificare il diff attuale
argocd app diff production-api

# Sync manuale con log verboso del client
argocd --loglevel debug app sync production-api
```

---

### Scenario 2 — PipelineRun fallisce su step `build` con errore di permessi Buildah

**Sintomo:** Il TaskRun termina con `Error: error creating build container: Error committing the finished image: ... permission denied`.

**Causa:** Una **SCC** (SecurityContextConstraints, il meccanismo OpenShift che limita UID, capability e volumi dei pod) troppo restrittiva: con `restricted-v2` il pod gira con un UID casuale e Buildah non riesce a scrivere/montare lo storage dei container.

**Soluzione:** Usare il ServiceAccount `pipeline` (creato dall'operator in ogni namespace) che ha già la SCC dedicata `pipelines-scc`. Evitare `privileged`: dà accesso al nodo e viola il principio del minimo privilegio.

```bash
# Verificare quale SCC viene applicata al pod della pipeline
oc get pod <pipelinerun-pod> -o jsonpath='{.metadata.annotations.openshift\.io/scc}'

# Il SA "pipeline" ha già pipelines-scc; per un SA custom:
oc adm policy add-scc-to-user pipelines-scc -z <sa-custom> -n <namespace>
oc get sa pipeline -n <namespace>

# Controllare i log del task fallito
tkn taskrun logs <taskrun-name> -n <namespace>
```

---

### Scenario 3 — EventListener non riceve i webhook GitHub

**Sintomo:** I push su GitHub non scatenano alcuna PipelineRun; su GitHub (Recent Deliveries) il webhook risulta in errore o 202 senza run create.

**Causa 1:** Il secret HMAC configurato nell'interceptor `github` non coincide con quello registrato su GitHub.
**Causa 2:** La Route dell'EventListener non esiste (l'operator crea solo il Service `el-<nome>`; la Route va creata) o ha TLS non valido.
**Causa 3:** Il filtro CEL nell'interceptor non corrisponde alla branch del push (es. `refs/heads/main` vs `refs/heads/master`).

**Soluzione:**

```bash
# Esporre il Service dell'EventListener, se manca la Route
oc expose svc/el-github-push -n pipelines
oc get route -n pipelines el-github-push
curl -s -o /dev/null -w "%{http_code}" https://<route-host>

# Controllare i log dell'EventListener per vedere i payload ricevuti
oc logs -n pipelines -l eventlistener=github-push --tail=50

# Verificare il secret HMAC
oc get secret github-secret -n pipelines -o jsonpath='{.data.secretToken}' | base64 -d

# Testare manualmente un webhook (sostituire TOKEN e URL)
curl -X POST https://<route-host> \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=<hmac>" \
  -d '{"ref":"refs/heads/main","repository":{"clone_url":"https://github.com/org/repo"}}'
```

---

### Scenario 4 — Sync Waves bloccato: ArgoCD aspetta indefinitamente la wave precedente

**Sintomo:** Il sync si blocca su una wave intermedia; i log ArgoCD mostrano `Waiting for resource to become healthy: apps/Deployment/<name>`.

**Causa:** Una risorsa nella wave N non raggiunge lo stato `Healthy` (es. un Deployment che non parte per mancanza di immagine, ConfigMap errata, o readiness probe fallita). ArgoCD non avanza alla wave N+1 finché tutte le risorse della wave corrente non sono healthy.

**Soluzione:**

```bash
# Identificare quale risorsa blocca la wave
argocd app get production-api -o wide | grep -v Synced

# Controllare lo stato dei pod del Deployment bloccato
oc get pods -n production -l app=<deployment-name>
oc describe pod <pod-name> -n production

# Job one-shot: gestirli come hook (annotation argocd.argoproj.io/hook: PostSync
# + hook-delete-policy) invece che come risorse normali: l'health di un Job
# completato/fallito altrimenti blocca la wave

# Sincronizzare solo una risorsa specifica (solo emergenze, bypassa l'ordine delle wave)
argocd app sync production-api --resource apps:Deployment:<name>

# Messaggio dell'operazione di sync in corso
oc get application production-api -n openshift-gitops \
  -o jsonpath='{.status.operationState.message}'
```

---

## Riferimenti

- [OpenShift GitOps](https://docs.openshift.com/gitops/latest/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/en/stable/)
- [OpenShift Pipelines (Tekton)](https://docs.openshift.com/pipelines/latest/)
- [Tekton Catalog](https://hub.tekton.dev/)
- [ApplicationSet](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
