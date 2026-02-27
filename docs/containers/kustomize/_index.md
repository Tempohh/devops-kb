---
title: "Kustomize"
slug: kustomize
category: containers
tags: [kustomize, kubernetes, overlays, patches, bases, configuration-management, gitops]
search_keywords: [kustomize overlays, kustomize bases, kustomize patches, kustomize strategic merge patch, kustomize JSON 6902 patch, kustomize generators, kustomize transformers, kustomize vs helm, kubectl kustomize, kustomize gitops, kustomize nameprefix, kustomize namesuffix, kustomize commonlabels, kustomize images]
parent: containers/_index
related: [containers/kustomize/avanzato, containers/helm/_index, containers/openshift/gitops-pipelines, containers/kubernetes/workloads]
official_docs: https://kustomize.io/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# Kustomize

**Kustomize** è uno strumento di configuration management per Kubernetes integrato in `kubectl` (da v1.14). A differenza di Helm, non usa template: opera per **trasformazioni dichiarative** su YAML esistenti tramite **basi** e **overlay**.

```
Kustomize Philosophy — Template-Free Patching

  ┌─────────────────────────────────────────────────────┐
  │  base/                  overlays/                   │
  │  ├── deployment.yaml    ├── staging/                │
  │  ├── service.yaml       │   └── kustomization.yaml  │
  │  └── kustomization.yaml │       ← patches staging   │
  │                         └── production/             │
  │  Risorse K8s "vanilla"      └── kustomization.yaml  │
  │  senza placeholder/vars          ← patches prod     │
  └─────────────────────────────────────────────────────┘
            ↓ kustomize build
  ┌─────────────────────────────┐
  │  Manifest finale per        │
  │  staging OPPURE production  │
  │  (YAML standard, pronto     │
  │  per kubectl apply)         │
  └─────────────────────────────┘
```

## Kustomize vs Helm

| Aspetto | Kustomize | Helm |
|---------|-----------|------|
| Approccio | Patch su YAML esistenti | Template con Go template engine |
| Curva apprendimento | Bassa | Media-alta |
| Flessibilità | Alta (patch arbitrarie) | Molto alta (logica condizionale) |
| Distribuzione | No packaging, solo Git | Chart OCI/HTTP distribuibili |
| Stato release | Nessuno (stateless) | Release secrets in cluster |
| Rollback | `git revert` | `helm rollback` |
| Validazione values | No (runtime error) | JSON Schema |
| Integrazione nativa K8s | Sì (`kubectl apply -k`) | No (CLI separato) |
| Uso ideale | GitOps multi-ambiente, patch semplici | Package distribuibili, parametrizzazione complessa |

---

## Struttura Base — Multi-Ambiente

```
myapp/
├── base/                               # risorse "vanilla" condivise
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   └── hpa.yaml
└── overlays/
    ├── staging/
    │   ├── kustomization.yaml
    │   ├── patch-replicas.yaml
    │   └── patch-resources.yaml
    └── production/
        ├── kustomization.yaml
        ├── patch-replicas.yaml
        ├── patch-resources.yaml
        └── patch-ingress.yaml
```

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
  - serviceaccount.yaml
  - hpa.yaml

# Label aggiunta a TUTTE le risorse
commonLabels:
  app.kubernetes.io/name: myapp
  app.kubernetes.io/managed-by: kustomize
```

```yaml
# base/deployment.yaml — YAML "puro", no placeholder
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      serviceAccountName: myapp
      containers:
        - name: myapp
          image: registry.company.com/myapp:latest
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base                    # include la base

# Sostituzione immagine (il modo corretto — non patch manuale)
images:
  - name: registry.company.com/myapp
    newTag: "1.2.0-staging"

# Namespace override
namespace: staging

# Prefisso a tutti i nomi risorse (es. staging-myapp)
namePrefix: staging-

# Labels aggiuntive per staging
commonLabels:
  environment: staging

# Patch: patch YAML dichiarativa (Strategic Merge Patch)
patches:
  - path: patch-replicas.yaml
  - path: patch-resources.yaml
```

```yaml
# overlays/staging/patch-replicas.yaml — Strategic Merge Patch
# Kustomize fa merge di questo YAML con il Deployment della base.
# Solo i campi specificati vengono modificati.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp                     # identifica quale risorsa patchare
spec:
  replicas: 1                     # override: staging ha 1 replica
```

```yaml
# overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base
  - ingress.yaml                  # risorsa aggiuntiva solo in produzione

images:
  - name: registry.company.com/myapp
    newTag: "1.2.0"

namespace: production

commonLabels:
  environment: production

patches:
  - path: patch-replicas.yaml
  - path: patch-resources.yaml
  - path: patch-ingress-tls.yaml
```

---

## Comandi Essenziali

```bash
# Build: genera il YAML finale (senza applicarlo)
kubectl kustomize overlays/staging
kubectl kustomize overlays/production

# Apply diretto (build + apply in uno)
kubectl apply -k overlays/staging
kubectl apply -k overlays/production

# Dry run
kubectl apply -k overlays/production --dry-run=client

# Diff: mostra differenze rispetto allo stato del cluster
kubectl diff -k overlays/production

# kustomize CLI standalone (più funzioni rispetto a kubectl)
brew install kustomize                    # macOS
# oppure: go install sigs.k8s.io/kustomize/kustomize/v5@latest

kustomize build overlays/production
kustomize build overlays/production | kubectl apply -f -
kustomize build overlays/production | kubectl diff -f -

# Build con output su file
kustomize build overlays/production -o manifests.yaml

# Versione di kustomize integrata in kubectl
kubectl version --client -o json | jq '.kustomizeVersion'
```

---

## Images — Sostituzione Immagine

Il campo `images` è il modo corretto per aggiornare i tag delle immagini in Kustomize, senza dover scrivere patch manuali.

```yaml
# kustomization.yaml
images:
  # Cambia solo il tag
  - name: registry.company.com/myapp
    newTag: "1.3.0"

  # Cambia repository e tag
  - name: nginx
    newName: registry.company.com/proxy/nginx
    newTag: "1.25-alpine"

  # Usa digest invece del tag (immutabile — raccomandato per produzione)
  - name: registry.company.com/myapp
    digest: "sha256:abc123def456..."

  # Regex per namespace/name nel registry
  - name: "*/myapp"               # corrisponde a qualsiasi registry/myapp
    newTag: "1.3.0"
```

```bash
# Aggiornare il tag da CI/CD (modifica kustomization.yaml in place)
kustomize edit set image registry.company.com/myapp:1.3.0 \
    --kustomization overlays/production/kustomization.yaml

# Equivalente con yq
yq -i '(.images[] | select(.name == "registry.company.com/myapp")).newTag = "1.3.0"' \
    overlays/production/kustomization.yaml

# Commit e push → ArgoCD rileva il cambio → sync automatico
git add overlays/production/kustomization.yaml
git commit -m "chore: bump myapp to 1.3.0"
git push
```

---

## Patches — Strategic Merge Patch

La **Strategic Merge Patch** (SMP) è il tipo di patch default. Kustomize fa un merge intelligente dei campi, gestendo correttamente liste come `containers[]`.

```yaml
# Aggiungere una variabile d'ambiente (merge lista containers)
# overlays/production/patch-env.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: myapp                       # identifica il container per nome
          env:
            - name: LOG_LEVEL
              value: "warn"
            - name: DATABASE_POOL_SIZE
              value: "50"
```

```yaml
# Modificare risorse (override completo del blocco resources)
# overlays/production/patch-resources.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: myapp
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 2Gi
```

```yaml
# Aggiungere annotations (merge del dict)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
spec: {}
```

```yaml
# Eliminare un campo con patch $patch: delete
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: myapp
          livenessProbe:
            $patch: delete        # rimuove completamente livenessProbe
```

---

## ConfigMap e Secret Generators

Kustomize può generare ConfigMap e Secret da file, e aggiunge automaticamente un **hash suffix** al nome per forzare il rolling update dei Pod quando i dati cambiano.

```yaml
# kustomization.yaml
configMapGenerator:
  # Da coppie key=value
  - name: app-config
    literals:
      - LOG_LEVEL=info
      - MAX_CONNECTIONS=25
      - FEATURE_FLAG_X=true

  # Da file
  - name: nginx-config
    files:
      - nginx.conf                          # key = nome file
      - config=custom-nginx.conf            # key = "config"

  # Da file .env
  - name: app-env
    envs:
      - .env.staging

  # Opzioni
  options:
    disableNameSuffixHash: false            # default: true (aggiunge hash)
    labels:
      component: config
    annotations:
      managed-by: kustomize

secretGenerator:
  # Da literals (in produzione preferire ExternalSecrets)
  - name: db-credentials
    literals:
      - username=myapp
      - password=changeme
    type: Opaque

  # Da file (es. TLS cert)
  - name: tls-cert
    files:
      - tls.crt
      - tls.key
    type: kubernetes.io/tls

  # Senza hash suffix (es. per Secret referenziato staticamente)
  - name: api-key
    literals:
      - key=abc123
    options:
      disableNameSuffixHash: true
```

```bash
# Verificare i ConfigMap generati con hash
kustomize build overlays/staging | grep "name: app-config"
# name: app-config-k8t5d97hm6    ← hash calcolato dal contenuto

# Quando i valori cambiano, l'hash cambia → K8s crea nuovo ConfigMap
# → Deployment rileva il cambio reference → rolling update automatico
```

---

## Transformers — Modifiche Globali

```yaml
# kustomization.yaml — trasformazioni applicabili globalmente

# Aggiunge namespace a tutte le risorse
namespace: production

# Aggiunge prefisso/suffisso a TUTTI i nomi
namePrefix: prod-
# nameSuffix: -v2

# Labels aggiunte a metadata.labels E a spec.selector (con gestione intelligente)
commonLabels:
  environment: production
  team: platform

# Annotations aggiunte a metadata.annotations di tutte le risorse
commonAnnotations:
  deploy-date: "2026-02-25"
  managed-by: argocd

# Replica count (scorciatoia rispetto a patch manuale)
replicas:
  - name: myapp
    count: 3
  - name: myapp-worker
    count: 5
```

---

## Riferimenti Remoti — Remote Bases

```yaml
# kustomization.yaml — include risorse da Git remoto
resources:
  # Base da repo Git remoto (SHA pinnata per stabilità)
  - https://github.com/kubernetes/cert-manager/releases/download/v1.14.0/cert-manager.yaml

  # Subdirectory di un repo Git
  - github.com/company/k8s-base//apps/myapp/base?ref=v1.2.0

  # Con protocollo SSH
  - ssh://git@github.com/company/k8s-base.git//base?ref=main

  # OCI resource (Kustomize v5+)
  - oci://registry.company.com/kustomize/base:1.0.0
```

!!! warning "Remote bases in produzione"
    Le remote bases con branch floating (es. `?ref=main`) possono introdurre instabilità. In produzione, **pinnare sempre a un tag o SHA** per build riproducibili.

---

## Riferimenti

- [Kustomize Official Docs](https://kustomize.io/)
- [kustomization.yaml Reference](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/)
- [Strategic Merge Patch](https://kubectl.docs.kubernetes.io/references/kustomize/glossary/#strategic-merge-patch)
- [Kustomize Examples](https://github.com/kubernetes-sigs/kustomize/tree/master/examples)
