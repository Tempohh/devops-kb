---
title: "GitOps e Pipelines"
slug: gitops-pipelines
category: containers
tags: [openshift, gitops, argocd, tekton, pipelines, cicd, image-promotion]
search_keywords: [openshift gitops ArgoCD, openshift pipelines tekton, ArgoCD ApplicationSet, tekton pipeline, openshift eventlistener, gitops app of apps, sync waves ArgoCD, openshift CI/CD, tekton task, argocd sync policy, gitops multi-cluster, openshift pipeline triggers]
parent: containers/openshift/_index
related: [containers/openshift/build-imagestream, containers/helm/deployment-produzione]
official_docs: https://docs.openshift.com/gitops/latest/
status: complete
difficulty: advanced
last_updated: 2026-02-25
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
  installPlanApproval: Automatic
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
        server: "{{url}}"
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
# Wave 1: database (aspetta che il PVC sia bound)
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

  steps:
    # Step 1: Build con Buildah (rootless, no Docker daemon)
    - name: build
      image: registry.redhat.io/rhel8/buildah:latest
      script: |
        buildah bud \
          --format=oci \
          --tls-verify=true \
          --no-cache \
          -f $(params.dockerfile) \
          -t $(params.image) \
          $(workspaces.source.path)

    # Step 2: Push al registry
    - name: push
      image: registry.redhat.io/rhel8/buildah:latest
      script: |
        buildah push \
          --tls-verify=true \
          --digestfile /tmp/image-digest \
          $(params.image)
        echo "Pushed: $(cat /tmp/image-digest)"

    # Step 3: Sign con cosign (keyless)
    - name: sign
      image: cgr.dev/chainguard/cosign:latest
      script: |
        cosign sign \
          --yes \
          --rekor-url=https://rekor.sigstore.dev \
          $(params.image)@$(cat /tmp/image-digest)

---
# Pipeline — sequenza di Task
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
    - name: dockerconfig
      optional: true

  tasks:
    - name: git-clone
      taskRef:
        resolver: cluster
        params: [{name: kind, value: task}, {name: name, value: git-clone}]
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

    - name: build-push-sign
      runAfter: [unit-tests]
      taskRef:
        kind: Task
        name: build-and-push
      params:
        - {name: image, value: "$(params.image-name):$(tasks.git-clone.results.commit)"}
      workspaces:
        - {name: source, workspace: source}

    - name: update-gitops
      runAfter: [build-push-sign]
      taskRef:
        kind: Task
        name: git-update-deployment
      params:
        - {name: image, value: "$(params.image-name):$(tasks.git-clone.results.commit)"}
      # Aggiorna il tag dell'immagine nel repo GitOps
      # → ArgoCD rileva il cambio e fa il deploy automaticamente

  results:
    - name: image-digest
      value: "$(tasks.build-push-sign.results.digest)"
```

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
        - ref:
            name: github
          params:
            - {name: secretRef, value: {secretName: github-secret, secretKey: secretToken}}
            - {name: eventTypes, value: [push]}
            - {name: branches, value: [main]}  # solo push su main
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
  5. Pipeline task "update-staging": PR automatica sul repo GitOps
     oc set image deployment/api api=myapp:main-<sha> nel path staging/
  6. ArgoCD rileva il cambio Git → sync automatico in staging

  Promotion a produzione:
  7. QA approva → merge PR GitOps da staging a production path
  8. ArgoCD sync automatico → deploy in produzione

  Audit trail completo: ogni deployment è tracciato in Git
```

---

## Riferimenti

- [OpenShift GitOps](https://docs.openshift.com/gitops/latest/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/en/stable/)
- [OpenShift Pipelines (Tekton)](https://docs.openshift.com/pipelines/latest/)
- [Tekton Catalog](https://hub.tekton.dev/)
- [ApplicationSet](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
