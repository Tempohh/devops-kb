---
title: "Tekton"
slug: tekton
category: ci-cd
tags: [tekton, kubernetes, cicd, pipeline, cloud-native, cncf, tasks, triggers, eventlistener, pipelinerun]
search_keywords: [tekton, tekton pipelines, tekton ci/cd, tekton kubernetes, cloud-native ci, cloud-native cd, tekton task, tekton pipeline, tekton pipelinerun, tekton taskrun, tekton triggers, tekton eventlistener, tekton hub, tekton catalog, tekton workspace, tekton results, tekton params, tekton steps, openshift pipelines, CNCF tekton, kubernetes-native pipeline, tekton vs github actions, tekton vs jenkins, tekton vs gitlab ci, CI cloud native, pipeline as kubernetes resources, tekton dashboard, tekton chains, supply chain security tekton, tekton buildah, tekton kaniko, git-clone task, tekton interceptor, triggerbinding, triggertemplate, tekton rbac, tekton service account, tekton finally, tekton when expression, tekton matrix]
parent: ci-cd/tools/_index
related: [ci-cd/gitops/argocd, ci-cd/pipeline, ci-cd/strategie/pipeline-security, containers/openshift/gitops-pipelines, containers/kubernetes/operators-crd]
official_docs: https://tekton.dev/docs/
status: complete
difficulty: advanced
last_updated: 2026-03-26
---

# Tekton

## Panoramica

Tekton è un framework open-source **Kubernetes-native** per la costruzione di pipeline CI/CD. A differenza di Jenkins, GitHub Actions o GitLab CI — sistemi esterni al cluster — Tekton si installa come estensione dell'API Kubernetes tramite CRD (Custom Resource Definition) e usa i pod Kubernetes come unità di esecuzione. Ogni step di una pipeline è un container, ogni task è un pod, ogni configurazione è un manifest YAML applicabile con `kubectl`. Questo approccio elimina la dipendenza da un server CI separato, sfrutta l'infrastruttura Kubernetes già esistente, e rende le pipeline portabili tra qualsiasi cluster.

Tekton è un progetto CNCF Graduated (dal 2022), alla base di OpenShift Pipelines (Red Hat) e usato come building block da altre soluzioni CI/CD cloud-native. Il pattern più comune è usare Tekton per la parte **CI** (build, test, push immagine) e ArgoCD per la parte **CD** (deploy GitOps-style) — complementari per natura.

!!! warning "Tekton NON è un sistema CI/CD completo out-of-the-box"
    Tekton è un framework a basso livello: non include UI avanzata, notifiche, policy di retention automatica, o dashboard ricca senza installare componenti aggiuntivi (Tekton Dashboard, Tekton Chains). Va usato quando si vuole controllo totale sulla pipeline come risorsa Kubernetes, non quando si vuole velocità di setup iniziale.

## Concetti Chiave

### Gerarchia dei Componenti

```
Pipeline
├── Task A (eseguita come Pod)
│   ├── Step 1 (container nel pod)
│   ├── Step 2 (container nel pod)
│   └── Sidecar (container ausiliario)
├── Task B
│   └── ...
└── Task C (finally — eseguita sempre, anche su fallimento)

PipelineRun       ← istanza di esecuzione di Pipeline
└── TaskRun       ← istanza di esecuzione di Task
    └── Pod       ← risorsa Kubernetes creata da Tekton
```

### Risorse Core

| Risorsa | Scopo |
|---------|-------|
| **Task** | Unità riutilizzabile di lavoro. Definisce steps, params, workspaces, results. |
| **TaskRun** | Esecuzione concreta di un Task. Passa i valori dei params e riferisce workspace PVC. |
| **Pipeline** | Sequenza (o DAG) di Task con dipendenze e passaggio di parametri tra task. |
| **PipelineRun** | Esecuzione concreta di una Pipeline. Crea automaticamente i TaskRun. |
| **Workspace** | Volume condiviso tra task (PVC, ConfigMap, Secret, emptyDir). |
| **Result** | Output di una Task passabile come input a task successive nella stessa Pipeline. |
| **Param** | Parametro tipizzato (string, array, object) con validazione opzionale e default. |

### Tekton Triggers

Componente separato per avviare PipelineRun da eventi esterni (webhook GitHub/GitLab, eventi CloudEvents).

| Risorsa | Scopo |
|---------|-------|
| **EventListener** | Server HTTP in ascolto di eventi webhook. |
| **Trigger** | Regola che mappa un evento a un TriggerTemplate. |
| **TriggerBinding** | Estrae valori dall'evento (es. `body.repository.clone_url`). |
| **TriggerTemplate** | Template che genera le risorse Kubernetes da creare (es. PipelineRun). |
| **Interceptor** | Filtro/trasformazione dell'evento (validazione firma HMAC, filtro su branch, CEL). |

## Architettura / Come Funziona

```
GitHub Webhook
      │
      │ POST /
      ▼
EventListener (Pod HTTP)
      │
      ├─ Interceptor: valida firma HMAC
      ├─ Interceptor: filtro CEL (es. solo push su main)
      │
      ▼
TriggerBinding: estrae git-url, git-revision, image-name
      │
      ▼
TriggerTemplate: genera PipelineRun con i valori estratti
      │
      ▼
PipelineRun (risorsa Kubernetes creata)
      │
      ├─ TaskRun: git-clone     → Pod K8s con 1 container
      ├─ TaskRun: run-tests     → Pod K8s con 1 container
      ├─ TaskRun: build-push    → Pod K8s con 2 container (build + push)
      └─ TaskRun: update-gitops → Pod K8s con 1 container
                                    │
                                    ▼
                              ArgoCD detects Git change
                                    │
                                    ▼
                              Deploy in cluster (CD)
```

### Workspaces e Condivisione Dati

Tekton **non ha stato condiviso** tra task per default: ogni TaskRun è un pod isolato. Per passare file tra task si usano Workspace backed da PVC:

```
Task git-clone  ──writes──► PVC (workspace: source)
Task run-tests  ──reads───► PVC (workspace: source)
Task build-push ──reads───► PVC (workspace: source)
```

I Result invece passano valori scalari (stringa) senza PVC:

```
Task git-clone  ──result: commit────► Task build-push (param: image-tag=$(tasks.git-clone.results.commit))
```

## Configurazione & Pratica

### 1. Installazione

```bash
# Installa Tekton Pipelines (CRD + controller)
kubectl apply --filename https://storage.googleapis.com/tekton-releases/pipeline/latest/release.yaml

# Installa Tekton Triggers (EventListener, TriggerTemplate, ecc.)
kubectl apply --filename https://storage.googleapis.com/tekton-releases/triggers/latest/release.yaml
kubectl apply --filename https://storage.googleapis.com/tekton-releases/triggers/latest/interceptors.yaml

# Installa Tekton Dashboard (UI web opzionale)
kubectl apply --filename https://storage.googleapis.com/tekton-releases/dashboard/latest/release.yaml

# Verifica installazione
kubectl get pods -n tekton-pipelines
# NAME                                          READY   STATUS
# tekton-pipelines-controller-...              1/1     Running
# tekton-pipelines-webhook-...                 1/1     Running
# tekton-dashboard-...                          1/1     Running (se installato)

# Installa CLI tkn (macOS)
brew install tektoncd-cli

# Verifica versione
tkn version
```

```bash
# Installa Tekton via Helm (alternativa)
helm repo add tekton https://charts.openshift.io/
helm install tekton-pipeline tekton/tekton-pipeline \
  --namespace tekton-pipelines \
  --create-namespace

# Oppure via OpenShift Pipelines Operator (Red Hat)
# → installa automaticamente Pipelines + Triggers + Dashboard
```

### 2. Task — Unità di Lavoro

```yaml
# Task: build e push di un container image con kaniko (no Docker daemon)
apiVersion: tekton.dev/v1
kind: Task
metadata:
  name: kaniko-build-push
  namespace: ci
spec:
  description: "Build e push di un container image con kaniko"

  params:
    - name: image
      description: "Image completa da pushare (registry/org/name:tag)"
      type: string
    - name: dockerfile
      description: "Path del Dockerfile relativo al context"
      type: string
      default: Dockerfile
    - name: context
      description: "Build context path nel workspace"
      type: string
      default: .

  workspaces:
    - name: source
      description: "Workspace con il codice sorgente"
    - name: dockerconfig
      description: "Secret con credenziali registry (~/.docker/config.json)"
      optional: true

  results:
    - name: image-digest
      description: "SHA256 digest dell'immagine pushata"

  steps:
    - name: build-and-push
      image: gcr.io/kaniko-project/executor:v1.21.0
      args:
        - "--dockerfile=$(params.dockerfile)"
        - "--context=$(workspaces.source.path)/$(params.context)"
        - "--destination=$(params.image)"
        - "--digest-file=$(results.image-digest.path)"
        - "--cache=true"
        - "--cache-ttl=24h"
        - "--snapshot-mode=redo"   # più veloce di full per layer grandi
      env:
        - name: DOCKER_CONFIG
          value: /kaniko/.docker
      volumeMounts:
        - name: docker-config
          mountPath: /kaniko/.docker

  volumes:
    - name: docker-config
      secret:
        secretName: registry-credentials   # Secret con .dockerconfigjson
        optional: true
```

```yaml
# Task: run unit tests (esempio Node.js)
apiVersion: tekton.dev/v1
kind: Task
metadata:
  name: node-test
  namespace: ci
spec:
  params:
    - name: node-version
      type: string
      default: "20"
    - name: test-command
      type: string
      default: "npm test -- --coverage --ci"

  workspaces:
    - name: source

  results:
    - name: test-result
      description: "pass o fail"

  steps:
    - name: install
      image: node:$(params.node-version)-alpine
      workingDir: $(workspaces.source.path)
      script: |
        npm ci --prefer-offline
      resources:
        requests:
          memory: "256Mi"
          cpu: "200m"
        limits:
          memory: "512Mi"
          cpu: "500m"

    - name: test
      image: node:$(params.node-version)-alpine
      workingDir: $(workspaces.source.path)
      script: |
        #!/bin/sh
        set -e
        $(params.test-command)
        echo -n "pass" | tee $(results.test-result.path)
```

### 3. Pipeline — Orchestrazione di Task

```yaml
# Pipeline: CI completa — clone, test, build, update GitOps
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: ci-pipeline
  namespace: ci
spec:
  description: "Pipeline CI: clone → test → build → update gitops"

  params:
    - name: git-url
      type: string
    - name: git-revision
      type: string
      default: main
    - name: image-name
      type: string
    - name: registry
      type: string
      default: ghcr.io/myorg

  workspaces:
    - name: source          # PVC condiviso tra tutti i task
    - name: docker-config   # Secret registry
    - name: ssh-creds       # Secret SSH per repo privati (opzionale)
      optional: true

  tasks:
    # Task 1: clone dal Tekton Hub
    - name: git-clone
      taskRef:
        resolver: hub
        params:
          - {name: catalog, value: tekton-catalog-tasks}
          - {name: type, value: artifact}
          - {name: kind, value: task}
          - {name: name, value: git-clone}
          - {name: version, value: "0.9"}
      params:
        - {name: url, value: "$(params.git-url)"}
        - {name: revision, value: "$(params.git-revision)"}
        - {name: deleteExisting, value: "true"}
      workspaces:
        - {name: output, workspace: source}
        - {name: ssh-directory, workspace: ssh-creds}

    # Task 2: unit tests (dopo clone)
    - name: run-tests
      runAfter: [git-clone]
      taskRef:
        kind: Task
        name: node-test
      params:
        - {name: node-version, value: "20"}
      workspaces:
        - {name: source, workspace: source}

    # Task 3: build e push (dopo test)
    - name: build-push
      runAfter: [run-tests]
      taskRef:
        kind: Task
        name: kaniko-build-push
      params:
        - name: image
          value: "$(params.registry)/$(params.image-name):$(tasks.git-clone.results.commit)"
      workspaces:
        - {name: source, workspace: source}
        - {name: dockerconfig, workspace: docker-config}

    # Task 4: aggiorna il repo GitOps con il nuovo tag
    - name: update-gitops
      runAfter: [build-push]
      taskRef:
        resolver: hub
        params:
          - {name: name, value: git-cli}
          - {name: version, value: "0.4"}
      params:
        - name: GIT_USER_NAME
          value: "tekton-bot"
        - name: GIT_USER_EMAIL
          value: "tekton@company.com"
        - name: GIT_SCRIPT
          value: |
            git clone https://github.com/myorg/gitops-manifests /workspace/gitops
            cd /workspace/gitops
            # Aggiorna il tag dell'immagine con yq
            yq e ".image.tag = \"$(tasks.git-clone.results.commit)\"" \
              -i apps/$(params.image-name)/values.staging.yaml
            git add -A
            git commit -m "chore(ci): update $(params.image-name) to $(tasks.git-clone.results.commit)"
            git push

  # Finally: eseguito sempre (anche se la pipeline fallisce)
  finally:
    - name: cleanup
      taskRef:
        kind: Task
        name: cleanup-workspace
      workspaces:
        - {name: source, workspace: source}

  results:
    - name: image-digest
      value: "$(tasks.build-push.results.image-digest)"
    - name: git-commit
      value: "$(tasks.git-clone.results.commit)"
```

### 4. PipelineRun — Esecuzione Manuale

```yaml
# PipelineRun: avvia la pipeline manualmente per test
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: ci-pipeline-run-      # nome univoco auto-generato
  namespace: ci
spec:
  pipelineRef:
    name: ci-pipeline

  params:
    - {name: git-url, value: "https://github.com/myorg/myapp"}
    - {name: git-revision, value: "main"}
    - {name: image-name, value: "myapp"}
    - {name: registry, value: "ghcr.io/myorg"}

  workspaces:
    - name: source
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          storageClassName: standard
          resources:
            requests:
              storage: 1Gi

    - name: docker-config
      secret:
        secretName: ghcr-credentials

  taskRunTemplate:
    serviceAccountName: tekton-pipeline-sa
    podTemplate:
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
      nodeSelector:
        workload-type: ci       # runner dedicati al CI
```

```bash
# Avviare una PipelineRun via CLI
tkn pipeline start ci-pipeline \
  --namespace ci \
  --param git-url=https://github.com/myorg/myapp \
  --param git-revision=main \
  --param image-name=myapp \
  --workspace name=source,volumeClaimTemplateFile=workspace-pvc.yaml \
  --workspace name=docker-config,secret=ghcr-credentials \
  --serviceaccount tekton-pipeline-sa \
  --showlog   # mostra log in tempo reale

# Visualizzare PipelineRun in corso
tkn pipelinerun list --namespace ci

# Log di un TaskRun specifico
tkn taskrun logs ci-pipeline-run-xyz-build-push-1 --namespace ci

# Cancellare tutti i PipelineRun completati (pulizia)
tkn pipelinerun delete --all --keep 5 --namespace ci
```

### 5. Tekton Triggers — Automazione da Webhook

```yaml
# ServiceAccount e RBAC per EventListener
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tekton-triggers-sa
  namespace: ci
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: tekton-triggers-binding
  namespace: ci
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: tekton-triggers-eventlistener-roles
subjects:
  - kind: ServiceAccount
    name: tekton-triggers-sa
    namespace: ci
---
# TriggerBinding: estrae dati dal payload del webhook GitHub
apiVersion: triggers.tekton.dev/v1beta1
kind: TriggerBinding
metadata:
  name: github-push-binding
  namespace: ci
spec:
  params:
    - name: git-url
      value: $(body.repository.clone_url)
    - name: git-revision
      value: $(body.after)                  # commit SHA del push
    - name: git-branch
      value: $(body.ref)                    # es. refs/heads/main
    - name: image-name
      value: $(body.repository.name)
---
# TriggerTemplate: genera il PipelineRun
apiVersion: triggers.tekton.dev/v1beta1
kind: TriggerTemplate
metadata:
  name: ci-pipeline-template
  namespace: ci
spec:
  params:
    - name: git-url
    - name: git-revision
    - name: image-name
  resourcetemplates:
    - apiVersion: tekton.dev/v1
      kind: PipelineRun
      metadata:
        generateName: ci-pipeline-run-
        namespace: ci
      spec:
        pipelineRef:
          name: ci-pipeline
        params:
          - {name: git-url, value: $(tt.params.git-url)}
          - {name: git-revision, value: $(tt.params.git-revision)}
          - {name: image-name, value: $(tt.params.image-name)}
        workspaces:
          - name: source
            volumeClaimTemplate:
              spec:
                accessModes: [ReadWriteOnce]
                resources:
                  requests:
                    storage: 1Gi
          - name: docker-config
            secret:
              secretName: ghcr-credentials
        taskRunTemplate:
          serviceAccountName: tekton-pipeline-sa
---
# EventListener: server HTTP che riceve i webhook
apiVersion: triggers.tekton.dev/v1beta1
kind: EventListener
metadata:
  name: github-push-listener
  namespace: ci
spec:
  serviceAccountName: tekton-triggers-sa
  triggers:
    - name: github-push-main
      interceptors:
        # Valida firma HMAC del webhook GitHub
        - ref:
            name: github
          params:
            - name: secretRef
              value:
                secretName: github-webhook-secret
                secretKey: secret-token
            - name: eventTypes
              value: [push]
        # Filtro CEL: solo push su main (non tag, non altre branch)
        - ref:
            name: cel
          params:
            - name: filter
              value: >
                body.ref == 'refs/heads/main' &&
                !body.deleted
      bindings:
        - ref: github-push-binding
      template:
        ref: ci-pipeline-template
```

```bash
# Esporre EventListener con un Service e Ingress
kubectl get svc -n ci el-github-push-listener
# NAME                       TYPE        CLUSTER-IP     PORT(S)
# el-github-push-listener    ClusterIP   10.96.x.x      8080/TCP

# Ingress (o LoadBalancer) per rendere l'EventListener raggiungibile da GitHub
kubectl expose service el-github-push-listener \
  --name=el-github-listener-external \
  --type=LoadBalancer \
  --port=80 \
  --target-port=8080 \
  --namespace ci

# URL da registrare come webhook GitHub:
# http://<EXTERNAL-IP>/   (campo "Payload URL" nelle GitHub Repo Settings)
# Content type: application/json
# Secret: valore del Secret github-webhook-secret
```

### 6. RBAC e Service Account

```yaml
# ServiceAccount per l'esecuzione della pipeline
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tekton-pipeline-sa
  namespace: ci
---
# Permessi minimi: creare TaskRun, leggere Secret dei workspace
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: tekton-pipeline-role
  namespace: ci
rules:
  - apiGroups: ["tekton.dev"]
    resources: ["taskruns", "pipelineruns"]
    verbs: ["get", "list", "create", "update", "patch", "delete"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["secrets", "configmaps"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: tekton-pipeline-binding
  namespace: ci
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: tekton-pipeline-role
subjects:
  - kind: ServiceAccount
    name: tekton-pipeline-sa
    namespace: ci
```

## Best Practices

!!! tip "Usa il Tekton Hub per task standard"
    Non scrivere task per operazioni comuni. Il [Tekton Hub](https://hub.tekton.dev/) offre task certificate per git-clone, buildah, kaniko, helm-upgrade-from-repo, sonarqube-scanner, trivy, cosign. Usare task dal Hub riduce il codice da mantenere e garantisce versioning esplicito.

### Task Design

**1. Task piccole e riutilizzabili.** Una Task fa una cosa sola (clone, build, test, sign). Non creare Task monolitiche — le Pipeline compongono Task semplici.

**2. Parametri con default sensati.** Ogni param dovrebbe avere un default che funziona per il caso d'uso più comune, così le Pipeline sono più concise.

**3. Security contexts espliciti.** Specificare sempre `runAsNonRoot: true` e `readOnlyRootFilesystem: true` dove possibile negli step. Kaniko e Buildah funzionano rootless.

```yaml
# Step con security context restrittivo
steps:
  - name: lint
    image: golangci/golangci-lint:v1.56
    securityContext:
      runAsNonRoot: true
      runAsUser: 65532
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: [ALL]
    workingDir: $(workspaces.source.path)
    script: |
      golangci-lint run ./...
```

**4. Resource limits su ogni step.** Senza limits, un task runaway può consumare tutte le risorse del nodo.

```yaml
steps:
  - name: build
    image: golang:1.22
    resources:
      requests:
        memory: "512Mi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "2"
```

### Workspace Management

!!! warning "Non usare PVC Read-Write-Many per pipeline ad alta frequenza"
    I PVC ReadWriteOnce (RWO) sono sufficienti per pipeline single-node. I PVC RWX sono più costosi e non sempre supportati dallo storage class. Usare `volumeClaimTemplate` nel PipelineRun crea un PVC effimero che viene eliminato con il PipelineRun.

```yaml
# Preferire volumeClaimTemplate (PVC effimero, eliminato con il PipelineRun)
workspaces:
  - name: source
    volumeClaimTemplate:
      spec:
        accessModes: [ReadWriteOnce]
        resources:
          requests:
            storage: 2Gi    # dimensionare generosamente per il clone + build

# Evitare PVC statici per pipeline (rimangono dopo la fine e consumano storage)
# workspaces:
#   - name: source
#     persistentVolumeClaim:
#       claimName: ci-workspace-pvc   # ← rimane dopo il PipelineRun
```

### Tekton Chains — Supply Chain Security

Tekton Chains è un controller che firma automaticamente i TaskRun/PipelineRun completati usando Sigstore/cosign:

```bash
# Installazione Tekton Chains
kubectl apply --filename https://storage.googleapis.com/tekton-releases/chains/latest/release.yaml

# Configurazione: firma con cosign keyless (OIDC)
kubectl patch configmap chains-config -n tekton-chains \
  --type=merge \
  -p='{"data":{"artifacts.oci.format":"sigstore","artifacts.oci.signer":"x509","transparency.enabled":"true"}}'
```

## Troubleshooting

### Problema: TaskRun bloccato in "Pending" per minuti

**Sintomo:** Il pod del TaskRun non parte, rimane in stato `Pending`.

**Causa 1:** Il PVC non è disponibile (storage class sbagliata, nessun PV disponibile).

```bash
# Verificare lo stato del PVC
kubectl get pvc -n ci
kubectl describe pvc <pvc-name> -n ci
# Cercare eventi come "no persistent volumes available for this claim"

# Soluzione: verificare la storage class disponibile
kubectl get storageclass
# Impostare nel volumeClaimTemplate la storage class corretta
```

**Causa 2:** Risorse insufficienti nel cluster (CPU/memory request non soddisfatte).

```bash
# Verificare eventi del pod
kubectl describe pod <task-pod> -n ci
# Cercare: "Insufficient cpu" o "Insufficient memory"

# Soluzione: ridurre i resource requests, aggiungere nodi, o usare node con più risorse
kubectl get nodes -o custom-columns="NAME:.metadata.name,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory"
```

**Causa 3:** ServiceAccount mancante o senza permessi pull dell'immagine.

```bash
# Verificare che il ServiceAccount abbia il secret registry
kubectl get serviceaccount tekton-pipeline-sa -n ci -o yaml
# Deve avere: imagePullSecrets: [{name: registry-credentials}]

# Aggiungere secret al serviceaccount se manca
kubectl patch serviceaccount tekton-pipeline-sa -n ci \
  -p '{"imagePullSecrets": [{"name": "registry-credentials"}]}'
```

---

### Problema: Task fallisce con "permission denied" sul workspace

**Sintomo:** `Error: open /workspace/source/...: permission denied`

**Causa:** Il container gira come utente non-root ma il PVC è stato scritto da un container root (o viceversa).

```bash
# Verificare UID degli step
kubectl logs <task-pod> -c step-build -n ci

# Soluzione: aggiungere securityContext al pod per uniformare il fsGroup
```

```yaml
# Nel PipelineRun: imposta fsGroup per condivisione PVC tra utenti diversi
taskRunTemplate:
  podTemplate:
    securityContext:
      fsGroup: 65532       # tutti i file del volume appartengono a questo GID
      runAsUser: 65532
      runAsNonRoot: true
```

---

### Problema: EventListener non riceve webhook (timeout)

**Sintomo:** GitHub riporta "We couldn't deliver this payload: Connection refused".

**Causa:** L'EventListener non è raggiungibile dall'esterno, oppure il Service non è esposto correttamente.

```bash
# Verificare che il pod EventListener sia running
kubectl get pods -n ci -l eventlistener=github-push-listener

# Verificare il Service
kubectl get svc -n ci el-github-push-listener
# Deve avere un EXTERNAL-IP o essere raggiungibile via Ingress

# Test locale con port-forward
kubectl port-forward svc/el-github-push-listener 8080:8080 -n ci
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
# Risposta attesa: {"eventListener":"github-push-listener","namespace":"ci","eventListenerUID":"..."}

# Verificare i log dell'EventListener per errori di validazione firma
kubectl logs -l eventlistener=github-push-listener -n ci --tail=50
```

---

### Problema: Result non propagato tra Task (valore vuoto)

**Sintomo:** `$(tasks.git-clone.results.commit)` è stringa vuota nel task successivo.

**Causa 1:** Il task upstream non ha scritto il result nel path corretto.

```bash
# I result DEVONO essere scritti in $(results.<name>.path)
# NON in un path hardcoded

# ✅ Corretto
echo -n "$(git rev-parse HEAD)" > $(results.commit.path)

# ❌ Sbagliato (il file non viene letto da Tekton)
echo -n "$(git rev-parse HEAD)" > /tmp/commit.txt
```

**Causa 2:** Il result contiene newline — Tekton non supporta result multi-riga (troncati a 4096 byte).

```bash
# Usare sempre echo -n (senza newline finale)
echo -n "abc123" > $(results.commit.path)
# NON: echo "abc123" > ... (aggiunge \n che può causare problemi)
```

---

### Problema: Pipeline lenta per download dipendenze ad ogni run

**Sintomo:** Ogni PipelineRun scarica 500MB di node_modules da zero.

**Causa:** Nessuna cache configurata — ogni `volumeClaimTemplate` è un PVC vuoto e fresco.

```yaml
# Soluzione: usare un PVC persistente per la cache (separato dal workspace source)
workspaces:
  - name: source
    volumeClaimTemplate:          # effimero — codice fresco ogni run
      spec:
        accessModes: [ReadWriteOnce]
        resources:
          requests:
            storage: 1Gi
  - name: npm-cache
    persistentVolumeClaim:        # persistente — cache condivisa tra run
      claimName: npm-cache-pvc    # creato separatamente, ReadWriteMany o ReadWriteOnce
```

```bash
# Creare il PVC per la cache (una volta sola)
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: npm-cache-pvc
  namespace: ci
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard
  resources:
    requests:
      storage: 5Gi
EOF
```

## Relazioni

??? info "ArgoCD — CD nativo Kubernetes (complementare a Tekton)"
    Il pattern più diffuso è Tekton per CI (build, test, push immagine) e ArgoCD per CD (deploy GitOps). Il task finale della Pipeline Tekton aggiorna il repo GitOps, ArgoCD rileva il cambio e fa il deploy. I due tool non si sovrappongono.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

??? info "Pipeline CI/CD — Concetti fondamentali"
    Principi generali di pipeline design: stage, quality gate, artifact promotion, parallelismo, caching. Tekton implementa questi concetti usando risorse Kubernetes native.

    **Approfondimento completo →** [CI/CD Pipeline](../pipeline.md)

??? info "Pipeline Security — Supply Chain con Tekton Chains"
    Tekton Chains automatizza la firma degli artefatti e la generazione di attestazioni SLSA direttamente dai PipelineRun. È la soluzione raccomandata per supply chain security in ambienti Kubernetes-native.

    **Approfondimento completo →** [Pipeline Security](../strategie/pipeline-security.md)

??? info "OpenShift Pipelines — Tekton su OpenShift"
    OpenShift Pipelines è la distribuzione Red Hat di Tekton, installata tramite Operator. Aggiunge integrazione con la console OpenShift, template pre-built (ClusterTask deprecate → Resolver), e BuildConfig/Buildah nativo.

    **Approfondimento completo →** [GitOps e Pipelines su OpenShift](../../containers/openshift/gitops-pipelines.md)

## Riferimenti

- [Tekton — Documentazione ufficiale](https://tekton.dev/docs/)
- [Tekton Hub — Catalog di Task riutilizzabili](https://hub.tekton.dev/)
- [Tekton Chains — Supply Chain Security](https://tekton.dev/docs/chains/)
- [Tekton Pipelines — GitHub](https://github.com/tektoncd/pipeline)
- [Tekton CLI (tkn)](https://tekton.dev/docs/cli/)
- [OpenShift Pipelines — Red Hat](https://docs.openshift.com/pipelines/latest/)
- [CNCF Tekton — Project page](https://www.cncf.io/projects/tekton/)
