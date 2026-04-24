---
title: "Kustomize — Fondamentali"
slug: fondamentali
category: containers
tags: [kustomize, kubernetes, overlays, patches, bases, configuration-management, gitops, generators]
search_keywords: [kustomize fondamentali, kustomize basi, kustomize overlays, kustomize bases, kustomize patches, kustomize strategic merge patch, kustomize SMP, kustomize generators, kustomize configMapGenerator, kustomize secretGenerator, kustomize namePrefix, kustomize nameSuffix, kustomize commonLabels, kustomize commonAnnotations, kustomize images, kustomize vs helm, kubectl apply -k, kubectl kustomize, kustomize tutorial, kustomize beginner, kustomize hash suffix, kustomize rolling update, kustomize trasformazioni, kustomize build pipeline, kustomize CI/CD]
parent: containers/kustomize/_index
related: [containers/kustomize/avanzato, containers/helm/_index, containers/kubernetes/workloads, containers/openshift/gitops-pipelines]
official_docs: https://kubectl.docs.kubernetes.io/guides/introduction/kustomize/
status: complete
difficulty: beginner
last_updated: 2026-04-04
---

# Kustomize — Fondamentali

## Panoramica

**Kustomize** è uno strumento di configuration management per Kubernetes integrato nativamente in `kubectl` (da v1.14). La sua filosofia è radicalmente diversa da Helm: **non usa template, non aggiunge placeholder nei manifest, non inventa un linguaggio di templating**. Opera invece per *trasformazioni dichiarative* su YAML Kubernetes standard — le stesse risorse che potresti applicare direttamente con `kubectl apply -f`.

Il concetto centrale è la **separazione tra base e overlay**: la base contiene le risorse Kubernetes "vanilla" valide per ogni ambiente, gli overlay applicano solo le differenze (replicas, risorse CPU/RAM, tag immagine, namespace). Il risultato è YAML Kubernetes standard, non un formato proprietario.

**Quando usare Kustomize:**
- GitOps multi-ambiente (dev/staging/production) con differenze minime tra ambienti
- Team che vuole mantenere YAML leggibili senza un engine di templating
- Integrazione nativa con `kubectl` senza dipendenze esterne aggiuntive
- Patch puntuali su chart Helm di terze parti (Kustomize può wrappare Helm — vedi `avanzato.md`)

**Quando preferire Helm:**
- Distribuzione di software a utenti esterni (Helm chart come pacchetto)
- Logica condizionale complessa tra molti parametri
- Ecosistema di chart pubblici (ArtifactHub)

---

## Concetti Chiave

### Base

La **base** è un insieme di manifest Kubernetes standard, con un file `kustomization.yaml` che li elenca. La base deve essere applicabile da sola (`kubectl apply -f base/` funziona). Non contiene valori ambiente-specifici.

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

# Elenca le risorse K8s in questa directory
resources:
  - deployment.yaml
  - service.yaml
  - serviceaccount.yaml

# Label aggiunta a TUTTE le risorse (opzionale nella base)
commonLabels:
  app.kubernetes.io/name: myapp
  app.kubernetes.io/managed-by: kustomize
```

```yaml
# base/deployment.yaml — YAML puro, nessun placeholder
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
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
```

### Overlay

Un **overlay** è un `kustomization.yaml` che punta alla base e specifica solo le differenze per quell'ambiente. Non copia i manifest — li referenzia.

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base          # path relativo alla base

namespace: staging
namePrefix: staging-    # tutte le risorse avranno prefix "staging-"

images:
  - name: registry.company.com/myapp
    newTag: "1.2.0-rc1"   # override del tag immagine

commonLabels:
  environment: staging

patches:
  - path: patch-replicas.yaml
  - path: patch-resources.yaml
```

!!! note "Path relativi"
    I path in `resources:` e `patches:` sono **sempre relativi** alla posizione del `kustomization.yaml` corrente. Non usare path assoluti.

### kustomization.yaml

Il file `kustomization.yaml` è il punto di ingresso di ogni directory Kustomize. Dichiara:
- `resources`: file o directory da includere
- `patches`: trasformazioni da applicare
- `images`: override dei tag immagine
- `generators`: ConfigMap/Secret da generare
- Trasformatori globali: `namespace`, `namePrefix`, `nameSuffix`, `commonLabels`, `commonAnnotations`

---

## Architettura / Come Funziona

### Struttura Directory Standard

```
myapp/
├── base/
│   ├── kustomization.yaml        # elenca deployment.yaml, service.yaml, ecc.
│   ├── deployment.yaml
│   ├── service.yaml
│   └── serviceaccount.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml    # differenze per dev
    │   └── patch-replicas.yaml
    ├── staging/
    │   ├── kustomization.yaml    # differenze per staging
    │   ├── patch-replicas.yaml
    │   └── patch-resources.yaml
    └── production/
        ├── kustomization.yaml    # differenze per produzione
        ├── patch-replicas.yaml
        ├── patch-resources.yaml
        └── patch-ingress-tls.yaml
```

### Pipeline di Build

```
base/deployment.yaml  ─┐
base/service.yaml     ─┤──► kustomize build ──► YAML finale per ambiente
base/kustomization    ─┘         ▲
                                 │
overlays/production/  ───────────┘
  kustomization.yaml (namespace, images, patches)
  patch-replicas.yaml
  patch-resources.yaml
```

Kustomize legge la base, applica i transformer (namespace, namePrefix, labels), poi applica le patches nell'ordine dichiarato. Il risultato è un unico stream YAML pronto per `kubectl apply`.

### Kustomize vs Helm — Differenza Filosofica

| Aspetto | Kustomize | Helm |
|---------|-----------|------|
| Approccio | Patch su YAML esistenti | Template Go con variabili |
| Manifest base | YAML K8s validi di per sé | Template non direttamente applicabili |
| Curva apprendimento | Bassa | Media-alta |
| Distribuzione package | Non prevista | Chart OCI/HTTP distribuibili |
| Stato release | Stateless | Release secrets nel cluster |
| Rollback | `git revert` | `helm rollback` |
| Integrazione kubectl | Nativa (`-k` flag) | CLI separata |
| Uso ideale | GitOps multi-ambiente | Software distribuibile a terzi |

!!! tip "Regola pratica"
    Se stai gestendo **il tuo** software su più ambienti → Kustomize. Se stai **distribuendo** software ad altri (open source, clienti) → Helm. Non sono mutuamente esclusivi: Kustomize può wrappare chart Helm per applicare patch post-rendering.

---

## Configurazione & Pratica

### Esempio Completo — App con 3 Overlays

**Struttura:**
```
webapp/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── hpa.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   └── patch-dev.yaml
    ├── staging/
    │   ├── kustomization.yaml
    │   └── patch-staging.yaml
    └── production/
        ├── kustomization.yaml
        ├── patch-production.yaml
        └── ingress.yaml
```

```yaml
# base/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 1
  maxReplicas: 3
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

```yaml
# overlays/dev/kustomization.yaml — ambiente dev: leggero e veloce
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: dev
namePrefix: dev-

images:
  - name: registry.company.com/myapp
    newTag: "latest"          # dev usa always-latest

commonLabels:
  environment: dev

patches:
  - path: patch-dev.yaml

# In dev non vogliamo HPA — rimuoverlo dalla lista risorse non funziona,
# ma possiamo sovrascrivere le repliche fissse con replicas:
replicas:
  - name: myapp
    count: 1
```

```yaml
# overlays/dev/patch-dev.yaml — resource limits ridotti per dev
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
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 256Mi
          env:
            - name: LOG_LEVEL
              value: "debug"
            - name: ENVIRONMENT
              value: "dev"
```

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: staging
namePrefix: staging-

images:
  - name: registry.company.com/myapp
    newTag: "1.3.0-rc2"

commonLabels:
  environment: staging

patches:
  - path: patch-staging.yaml
```

```yaml
# overlays/staging/patch-staging.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: myapp
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          env:
            - name: LOG_LEVEL
              value: "info"
            - name: ENVIRONMENT
              value: "staging"
```

```yaml
# overlays/production/kustomization.yaml — produzione: alta disponibilità
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base
  - ingress.yaml           # risorsa aggiuntiva solo in produzione

namespace: production

images:
  - name: registry.company.com/myapp
    newTag: "1.3.0"        # tag stabile, mai digest per semplicità qui

commonLabels:
  environment: production

commonAnnotations:
  deploy-date: "2026-04-04"
  managed-by: argocd

patches:
  - path: patch-production.yaml
```

```yaml
# overlays/production/patch-production.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 5
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
          env:
            - name: LOG_LEVEL
              value: "warn"
            - name: ENVIRONMENT
              value: "production"
            - name: DATABASE_POOL_SIZE
              value: "50"
```

### Comandi Essenziali

```bash
# Build: genera il manifest finale SENZA applicarlo
kubectl kustomize overlays/staging
kustomize build overlays/staging         # kustomize CLI standalone

# Apply: build + kubectl apply in un solo comando
kubectl apply -k overlays/staging
kubectl apply -k overlays/production

# Dry run: simula senza modificare il cluster
kubectl apply -k overlays/production --dry-run=client
kubectl apply -k overlays/production --dry-run=server   # validazione server-side

# Diff: mostra differenze rispetto allo stato attuale del cluster
kubectl diff -k overlays/production

# Build su file (utile per debug o archiviazione)
kustomize build overlays/production -o manifests-$(date +%Y%m%d).yaml

# Build e pipe diretto a kubectl
kustomize build overlays/production | kubectl apply -f -
kustomize build overlays/production | kubectl diff -f -
```

```bash
# Installazione kustomize standalone (più features di kubectl integrato)
# Linux/macOS
curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
sudo mv kustomize /usr/local/bin/

# macOS via Homebrew
brew install kustomize

# Versione
kustomize version

# Versione di kustomize integrata in kubectl
kubectl version --client -o json | jq '.kustomizeVersion'
```

### Images — Sostituzione Tag Immagine

Il campo `images` è il modo corretto per aggiornare i tag — non usare patch manuali.

```yaml
# kustomization.yaml — esempi images
images:
  # Solo cambio tag
  - name: registry.company.com/myapp
    newTag: "1.3.0"

  # Cambio repository E tag (es. mirror interno)
  - name: nginx
    newName: registry.company.com/mirror/nginx
    newTag: "1.25-alpine"

  # Digest SHA256 — immutabile, raccomandato per produzione critica
  - name: registry.company.com/myapp
    digest: "sha256:a1b2c3d4e5f6..."

  # Pattern wildcard per qualsiasi registry con stesso nome
  - name: "*/myapp"
    newTag: "1.3.0"
```

```bash
# CI/CD: aggiornare il tag automaticamente con kustomize CLI
IMAGE_TAG="1.3.0-sha-$(git rev-parse --short HEAD)"

kustomize edit set image "registry.company.com/myapp:${IMAGE_TAG}" \
    --kustomization overlays/production/kustomization.yaml

# Oppure con yq (alternativa senza kustomize CLI)
yq -i '(.images[] | select(.name == "registry.company.com/myapp")).newTag = env(IMAGE_TAG)' \
    overlays/production/kustomization.yaml

# Commit per trigger GitOps (ArgoCD/Flux rileva il cambio)
git add overlays/production/kustomization.yaml
git commit -m "ci: deploy myapp ${IMAGE_TAG} to production"
git push
```

### ConfigMap e Secret Generators

Kustomize genera ConfigMap e Secret da file e literals, aggiungendo automaticamente un **hash suffix** al nome per forzare il rolling update dei Pod quando i dati cambiano.

```yaml
# kustomization.yaml — generators
configMapGenerator:
  # Da coppie key=value literal
  - name: app-config
    literals:
      - LOG_LEVEL=info
      - MAX_CONNECTIONS=25
      - FEATURE_FLAG_DARK_MODE=false

  # Da file di configurazione
  - name: nginx-config
    files:
      - nginx.conf                      # key = "nginx.conf"
      - config=custom-nginx.conf        # key = "config", value = contenuto file

  # Da file .env
  - name: app-env
    envs:
      - config/.env.staging             # ogni riga KEY=VALUE diventa una entry

  # Senza hash suffix (per risorse che referenziano il nome staticamente)
  - name: static-config
    literals:
      - TIMEOUT=30
    options:
      disableNameSuffixHash: true

secretGenerator:
  # Secrets da literals (OK per dev, in produzione usare ExternalSecrets)
  - name: db-credentials
    literals:
      - username=myapp
      - password=s3cr3t
    type: Opaque

  # TLS certificate da file
  - name: tls-cert
    files:
      - tls.crt
      - tls.key
    type: kubernetes.io/tls
```

```bash
# Verifica hash generati
kustomize build overlays/staging | grep "name: app-config"
# Output: name: app-config-k8t5d97hm6   ← hash calcolato dal contenuto

# Quando LOG_LEVEL cambia da "info" a "debug":
# → hash cambia → K8s crea nuovo ConfigMap
# → Deployment rileva il cambio nella reference → rolling update automatico

# Questo meccanismo evita il classico problema:
# "ho aggiornato il ConfigMap ma i Pod usano ancora il vecchio valore"
```

!!! warning "Secrets in produzione"
    Non mettere mai segreti reali in `kustomization.yaml` committato in Git. Usare `secretGenerator` solo per dev/test locali. In produzione, integrare con [External Secrets Operator](https://external-secrets.io/) o Vault per gestire i segreti in modo sicuro.

### Trasformazioni Globali

```yaml
# kustomization.yaml — trasformatori disponibili
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

# Namespace applicato a TUTTE le risorse namespace-scoped
namespace: production

# Prefisso/suffisso aggiunti al metadata.name di TUTTE le risorse
namePrefix: prod-
# nameSuffix: -v2     # alternativa al prefix

# Labels aggiunte a metadata.labels di TUTTE le risorse
# Per Deployment/StatefulSet, aggiornate anche spec.selector e pod template labels
commonLabels:
  environment: production
  team: platform
  cost-center: "12345"

# Annotations aggiunte a metadata.annotations di TUTTE le risorse
commonAnnotations:
  deploy-date: "2026-04-04"
  managed-by: argocd
  contact: platform-team@company.com

# Shortcut per impostare replicas senza patch
replicas:
  - name: myapp
    count: 5
  - name: myapp-worker
    count: 3
```

!!! warning "commonLabels modifica anche i selectors"
    `commonLabels` aggiunge label a `spec.selector.matchLabels` e `spec.template.metadata.labels` nei Deployment. Se un Deployment è già in esecuzione nel cluster, cambiare i selectors causa un **errore immutabile** — Kubernetes non permette di modificare selectors di Deployment esistenti. In quel caso devi eliminare e ricreare il Deployment.

### Workflow CI/CD

```bash
#!/bin/bash
# .github/workflows/deploy.sh — esempio script pipeline

set -euo pipefail

ENVIRONMENT="${1:-staging}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE_REF="registry.company.com/myapp:${IMAGE_TAG}"
OVERLAY_PATH="overlays/${ENVIRONMENT}"

echo "=== Deploy ${IMAGE_REF} to ${ENVIRONMENT} ==="

# 1. Build e valida il manifest
echo "--- Building kustomize manifest ---"
kustomize build "${OVERLAY_PATH}" > /tmp/manifest.yaml

# 2. Validazione schema K8s (kubeconform)
echo "--- Validating schema ---"
kubeconform -strict -kubernetes-version 1.29.0 /tmp/manifest.yaml

# 3. Diff rispetto allo stato attuale del cluster
echo "--- Diff vs cluster ---"
kubectl diff -f /tmp/manifest.yaml || true   # exit 1 se ci sono diff (ok in pipe)

# 4. Apply
echo "--- Applying to cluster ---"
kubectl apply -f /tmp/manifest.yaml

# 5. Verifica rollout
echo "--- Waiting for rollout ---"
kubectl rollout status deployment/myapp -n "${ENVIRONMENT}" --timeout=300s

echo "=== Deploy completed ==="
```

```yaml
# .github/workflows/deploy.yaml — GitHub Actions
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build & validate
        run: |
          # Installa kustomize
          curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
          sudo mv kustomize /usr/local/bin/

          # Aggiorna image tag
          IMAGE_TAG="${{ github.sha }}"
          kustomize edit set image "registry.company.com/myapp=${IMAGE_TAG}" \
              --kustomization overlays/staging/kustomization.yaml

          # Build e valida
          kustomize build overlays/staging | kubeconform -strict

      - name: Deploy to staging
        run: kubectl apply -k overlays/staging

      - name: Wait for rollout
        run: |
          kubectl rollout status deployment/staging-myapp \
              -n staging --timeout=300s
```

---

## Best Practices

**Struttura:**
- La base deve contenere manifest K8s validi applicabili da soli — nessun valore ambiente-specifico
- Gli overlay devono contenere SOLO le differenze rispetto alla base — non copiare interi manifest
- Nomi file patch espliciti: `patch-hpa-limits.yaml` non `patch1.yaml`
- Un overlay per ambiente (dev/staging/production), non per team o feature

**Image management:**
- Usare sempre `images:` per cambiare i tag — mai patch manuale sul campo `image:`
- In produzione considerare digest `sha256:...` invece di tag (immutabile)
- CI/CD: `kustomize edit set image` per aggiornamento automatizzato del tag

**Generators:**
- Usare `configMapGenerator` con hash suffix (default) per triggering automatico del rolling update
- `disableNameSuffixHash: true` solo quando il nome è referenziato staticamente da risorse esterne
- Non mettere segreti reali in Git — integrare con External Secrets in produzione

**Validazione:**
- Sempre `kustomize build | kubeconform` in CI prima del deploy
- `kubectl diff -k` per review pre-apply in produzione
- Pinnare le remote bases a tag/SHA specifico (`?ref=v1.2.0`), mai `?ref=main`

!!! tip "kubectl diff prima di apply"
    Prima di ogni deploy in produzione, esegui `kubectl diff -k overlays/production` per vedere esattamente cosa cambierà nel cluster. È il modo più sicuro per evitare sorprese, specialmente quando si modificano `commonLabels` o `namespace`.

---

## Troubleshooting

### Scenario 1 — `no such file or directory` durante kustomize build

**Sintomo:**
```
Error: accumulating resources: accumulation err='accumulating resources from '../../base':
  '/path/to/base': no such file or directory
```

**Causa:** Il path relativo in `resources:` o `patches:` è errato rispetto alla posizione del `kustomization.yaml`.

**Soluzione:**
```bash
# Verificare la struttura delle directory
find . -name "kustomization.yaml" -exec echo "=== {} ===" \; -exec cat {} \;

# Testare il build dalla directory corretta
cd overlays/production
kustomize build .

# Oppure con path assoluto dalla root del progetto
kustomize build overlays/production

# Verificare i path relativi: da overlays/production/ ../../base
# significa: salire due livelli (→ myapp/) poi entrare in base/
ls ../../base/   # eseguire da overlays/production/
```

---

### Scenario 2 — Le modifiche al ConfigMap non triggano rolling update dei Pod

**Sintomo:** Dopo `kubectl apply -k`, i Pod continuano a usare i valori vecchi del ConfigMap.

**Causa:** Il ConfigMap è stato creato con `disableNameSuffixHash: true` o modificato direttamente senza passare da Kustomize, quindi il nome non è cambiato e i Pod non riavviano.

**Soluzione:**
```bash
# Verificare se il ConfigMap ha hash suffix
kubectl get configmap -n staging | grep app-config
# Con hash:    app-config-k8t5d97hm6   ← rolling update automatico
# Senza hash:  app-config              ← aggiornamento manuale necessario

# Se senza hash, riavvio manuale del Deployment
kubectl rollout restart deployment/staging-myapp -n staging

# Per abilitare hash suffix, rimuovere (o impostare a false) disableNameSuffixHash
# nel configMapGenerator nel kustomization.yaml
```

```yaml
# PRIMA (nessun rolling update automatico)
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
    options:
      disableNameSuffixHash: true   # ← rimuovere questa opzione

# DOPO (hash suffix abilitato — default)
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
# nessuna opzione → disableNameSuffixHash: false (default)
```

---

### Scenario 3 — `commonLabels` causa errore immutabile sui Deployment

**Sintomo:**
```
The Deployment "myapp" is invalid: spec.selector: Invalid value: ...
field is immutable
```

**Causa:** `commonLabels` aggiunge label ai selectors del Deployment. I selectors sono immutabili in Kubernetes una volta che il Deployment è stato creato. Aggiungere o modificare `commonLabels` su Deployment già in esecuzione causa questo errore.

**Soluzione:**
```bash
# Opzione 1: eliminare il Deployment e ricrearlo (downtime breve)
kubectl delete deployment myapp -n production
kubectl apply -k overlays/production

# Opzione 2: usare commonAnnotations invece di commonLabels
# (le annotations non modificano i selectors)
# Nel kustomization.yaml, spostare le label problematiche in commonAnnotations

# Opzione 3: usare patch per aggiungere label solo a metadata (non a selector)
# patch-labels.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  labels:
    team: platform       # solo metadata.labels, NON spec.selector
```

---

### Scenario 4 — `resource not found in base` con overlay annidati

**Sintomo:**
```
Error: unable to find patch target...
no matching resources for patch
```

**Causa:** Il patch target (kind + name) nel file di patch non corrisponde esattamente alle risorse nella base. Kustomize è case-sensitive e richiede corrispondenza esatta.

**Soluzione:**
```bash
# Verificare i nomi delle risorse nella base
kustomize build base/ | grep "kind:\|name:"

# Controllare il file di patch: name deve corrispondere esattamente
# Se la base ha `name: myapp` e il patch ha `name: MyApp` → no match
```

```yaml
# SBAGLIATO: name non corrisponde
# base/deployment.yaml ha metadata.name: myapp
apiVersion: apps/v1
kind: Deployment
metadata:
  name: MyApp          # ← case diverso → no match!
spec:
  replicas: 5

# CORRETTO
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp          # ← identico alla base
spec:
  replicas: 5
```

---

### Scenario 5 — namePrefix applicato a risorse che non dovrebbe

**Sintomo:** Dopo il build, un `ClusterRole` o `PersistentVolume` ha ricevuto il namePrefix e ora i binding non funzionano.

**Causa:** `namePrefix` e `nameSuffix` vengono applicati a tutte le risorse, incluse quelle cluster-scoped come `ClusterRole`, `ClusterRoleBinding`, `Namespace`.

**Soluzione:**
```yaml
# Usare patches per applicare prefix solo alle risorse che vogliamo
# Oppure rimuovere namePrefix e applicare il prefix manualmente nei file

# Alternativa: usare namespace invece di namePrefix per l'isolamento
namespace: production   # isola le risorse namespace-scoped senza toccare cluster-scoped
```

```bash
# Verificare tutte le risorse che ricevono il prefix
kustomize build overlays/production | grep "^  name:" | sort

# Se ClusterRole ha prefix indesiderato, escluderlo con transformerconfig custom
# (vedi containers/kustomize/avanzato.md — Transformer Config)
```

---

## Relazioni

??? info "Kustomize Avanzato — JSON Patch, Components, Replacements"
    Per operazioni precise su array, concern trasversali riutilizzabili (Components),
    propagazione di valori tra risorse (Replacements) e integrazione con Helm.

    **Approfondimento completo →** [Kustomize Avanzato](./avanzato.md)

??? info "Helm — Packaging e Distribuzione"
    Quando Kustomize non è sufficiente: logica condizionale complessa, distribuzione
    di chart a utenti esterni, ecosistema di chart pubblici.

    **Approfondimento completo →** [Helm](./../helm/_index.md)

??? info "OpenShift GitOps e Pipelines"
    Utilizzo di Kustomize con ArgoCD su OpenShift per GitOps completo.

    **Approfondimento completo →** [OpenShift GitOps](./../openshift/gitops-pipelines.md)

---

## Riferimenti

- [Kustomize Official Docs](https://kustomize.io/)
- [kustomization.yaml Reference](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/)
- [Kustomize Guides](https://kubectl.docs.kubernetes.io/guides/introduction/kustomize/)
- [Strategic Merge Patch](https://kubectl.docs.kubernetes.io/references/kustomize/glossary/#strategic-merge-patch)
- [Kustomize Examples — GitHub](https://github.com/kubernetes-sigs/kustomize/tree/master/examples)
- [kubeconform — Schema Validation](https://github.com/yannh/kubeconform)
