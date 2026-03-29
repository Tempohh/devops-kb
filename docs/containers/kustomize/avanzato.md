---
title: "Kustomize Avanzato"
slug: avanzato
category: containers
tags: [kustomize, json-patch, components, transformers, functions, argocd, helm-kustomize, cross-cutting]
search_keywords: [kustomize JSON 6902 patch, kustomize RFC 6902, kustomize components, kustomize replacements, kustomize transformer config, kustomize KRM functions, kustomize helm inflator, kustomize validate, kustomize build pipeline, kustomize ArgoCD, kustomize cross-cutting concerns, kustomize inline patch, kustomize fieldspecs, kustomize openapi]
parent: containers/kustomize/_index
related: [containers/kustomize/_index, containers/helm/_index, containers/openshift/gitops-pipelines, containers/kubernetes/sicurezza]
official_docs: https://kubectl.docs.kubernetes.io/references/kustomize/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Kustomize Avanzato

## JSON 6902 Patch — Chirurgia Precisa sul YAML

La **JSON Patch (RFC 6902)** permette operazioni atomiche su nodi specifici del manifest, espressi tramite **JSON Pointer**. È più precisa della Strategic Merge Patch per operazioni che il SMP non gestisce (es. rimozione elementi da array per indice, replace di valori interi).

```yaml
# overlays/production/kustomization.yaml
patches:
  # Patch inline (per patch brevi)
  - target:
      kind: Deployment
      name: myapp
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 5

  # Patch da file (per patch complesse)
  - target:
      kind: Deployment
      name: myapp
    path: patch-resources.json6902.yaml

  # Target con labelSelector (applica a più risorse)
  - target:
      kind: Deployment
      labelSelector: "app.kubernetes.io/part-of=myapp"
    patch: |-
      - op: add
        path: /spec/template/spec/securityContext
        value:
          runAsNonRoot: true
          runAsUser: 1000
          fsGroup: 1000
```

**Operazioni JSON Patch disponibili:**

```yaml
# op: add — aggiunge un campo o elemento in lista
- op: add
  path: /spec/template/spec/containers/0/env/-   # '-' = append alla lista
  value:
    name: NEW_VAR
    value: "hello"

# op: remove — rimuove un campo o elemento
- op: remove
  path: /spec/template/spec/containers/0/livenessProbe

# op: replace — sostituisce un valore esistente
- op: replace
  path: /spec/template/spec/containers/0/image
  value: "registry.company.com/myapp:1.3.0"

# op: copy — copia il valore di un path in un altro
- op: copy
  from: /spec/template/metadata/labels
  path: /spec/selector/matchLabels

# op: move — sposta (equivale a copy + remove)
- op: move
  from: /metadata/annotations/old-key
  path: /metadata/annotations/new-key

# op: test — verifica un valore (fallisce se non corrisponde)
# Utile per assert prima di applicare patch
- op: test
  path: /spec/replicas
  value: 1
```

```yaml
# Esempio completo: patch su Service per aggiungere NodePort
# patch-service-nodeport.yaml
- op: replace
  path: /spec/type
  value: NodePort

- op: add
  path: /spec/ports/0/nodePort
  value: 30080

# Target nel kustomization.yaml
patches:
  - target:
      kind: Service
      name: myapp
    path: patch-service-nodeport.yaml
```

---

## Target Multi-Risorsa con Selectors

```yaml
# Applicare una patch a TUTTE le risorse che corrispondono al target
patches:
  # Per kind + labelSelector
  - target:
      kind: Deployment
      labelSelector: "app.kubernetes.io/part-of=myapp"
    patch: |-
      - op: add
        path: /spec/template/metadata/annotations
        value:
          prometheus.io/scrape: "true"

  # Per group/version/kind + namespace
  - target:
      group: apps
      version: v1
      kind: StatefulSet
      namespace: data
    patch: |-
      - op: replace
        path: /spec/podManagementPolicy
        value: Parallel

  # Per annotationSelector
  - target:
      kind: Deployment
      annotationSelector: "inject-sidecar=true"
    patch: |-
      - op: add
        path: /spec/template/spec/containers/-
        value:
          name: envoy-sidecar
          image: envoyproxy/envoy:v1.28
          ports:
            - containerPort: 9901
```

---

## Replacements — Propagare Valori tra Risorse

`replacements` (Kustomize v4.5+) permette di **leggere un valore da una risorsa e scriverlo in un'altra**, eliminando la duplicazione di dati tra manifest.

```yaml
# kustomization.yaml
replacements:
  # Propaga il numero di porta dal Service al ConfigMap
  - source:
      kind: Service
      name: myapp
      fieldPath: spec.ports.0.port          # legge da qui
    targets:
      - select:
          kind: ConfigMap
          name: app-config
        fieldPaths:
          - data.SERVICE_PORT               # scrive qui

  # Propaga nome ServiceAccount → Pod spec
  - source:
      kind: ServiceAccount
      name: myapp
      fieldPath: metadata.name
    targets:
      - select:
          kind: Deployment
          name: myapp
        fieldPaths:
          - spec.template.spec.serviceAccountName
        options:
          create: true                       # crea il campo se non esiste

  # Propaga image tag dal Deployment → initContainer (stesso tag)
  - source:
      kind: Deployment
      name: myapp
      fieldPath: spec.template.spec.containers.[name=myapp].image
    targets:
      - select:
          kind: Deployment
          name: myapp
        fieldPaths:
          - spec.template.spec.initContainers.[name=init-migration].image
```

---

## Components — Concern Trasversali Riutilizzabili

I **Components** (Kustomize v4.1+) sono pacchetti di risorse e patch riutilizzabili tra più overlays, ideali per concern trasversali (monitoring, TLS, RBAC, sidecar injection).

```
components/
├── prometheus-monitoring/
│   ├── kustomization.yaml    (kind: Component)
│   ├── servicemonitor.yaml
│   └── patch-annotations.yaml
├── pod-disruption-budget/
│   ├── kustomization.yaml
│   └── pdb.yaml
├── network-policy/
│   ├── kustomization.yaml
│   ├── default-deny.yaml
│   └── allow-ingress.yaml
└── external-secrets/
    ├── kustomization.yaml
    └── externalsecret.yaml
```

```yaml
# components/prometheus-monitoring/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component                             # ← tipo Component, non Kustomization

resources:
  - servicemonitor.yaml

patches:
  - target:
      kind: Deployment
    patch: |-
      - op: add
        path: /spec/template/metadata/annotations
        value:
          prometheus.io/scrape: "true"
          prometheus.io/port: "8080"
          prometheus.io/path: "/metrics"
```

```yaml
# components/pod-disruption-budget/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component

patches:
  # PDB generato dinamicamente per ogni Deployment
  - target:
      kind: Deployment
    patch: |-
      apiVersion: policy/v1
      kind: PodDisruptionBudget
      metadata:
        name: placeholder            # kustomize usa il nome del Deployment
      spec:
        minAvailable: 1
        selector:
          matchLabels: {}            # kustomize inietta i selector automaticamente
```

```yaml
# overlays/production/kustomization.yaml
resources:
  - ../../base

# Selezionare quali components abilitare per questo overlay
components:
  - ../../components/prometheus-monitoring
  - ../../components/pod-disruption-budget
  - ../../components/network-policy
  # non includiamo external-secrets → usa ConfigMap locali in prod
```

```yaml
# overlays/staging/kustomization.yaml
resources:
  - ../../base

components:
  - ../../components/prometheus-monitoring
  # non includiamo PDB → staging può avere downtime
  # non includiamo network-policy → meno restrittivo in staging
```

---

## Transformer Config — Personalizzare i Transformer

I transformer Kustomize (es. NamespaceTransformer, LabelTransformer) usano **FieldSpecs** per sapere dove applicare le modifiche. È possibile estendere questa configurazione per CRD custom.

```yaml
# kustomization.yaml
configurations:
  - transformer-config.yaml
```

```yaml
# transformer-config.yaml — insegna a Kustomize dove applicare namespace su CRD custom
namespace:
  # Kustomize già conosce namespace per risorse K8s built-in
  # Aggiungere qui i path per CRD personalizzate
  - path: spec/targetNamespace
    kind: MyCustomResource
    group: company.com

namePrefix:
  - path: metadata/name
    kind: MyCustomResource

commonLabels:
  - path: spec/selector/matchLabels
    kind: MyCustomResource
    create: true
  - path: spec/template/metadata/labels
    kind: MyCustomResource
    create: true
```

---

## Kustomize + Helm — Helm Inflator

Kustomize può **renderizzare un Helm chart** e poi applicare patch Kustomize sopra, combinando il meglio dei due strumenti.

```yaml
# kustomization.yaml (richiede kustomize v5+ o flag --enable-helm)
helmCharts:
  - name: ingress-nginx
    repo: https://kubernetes.github.io/ingress-nginx
    version: 4.9.0
    releaseName: ingress-nginx
    namespace: ingress-nginx
    valuesFile: values-ingress.yaml
    values:
      controller:
        replicaCount: 3
        service:
          type: LoadBalancer

  - name: cert-manager
    repo: https://charts.jetstack.io
    version: v1.14.0
    releaseName: cert-manager
    namespace: cert-manager
    includeCRDs: true
    values:
      installCRDs: true

# Poi si possono applicare patch Kustomize sui manifest renderizzati da Helm
patches:
  - target:
      kind: Deployment
      name: ingress-nginx-controller
    patch: |-
      - op: add
        path: /spec/template/spec/tolerations
        value:
          - key: "dedicated"
            operator: "Equal"
            value: "ingress"
            effect: "NoSchedule"
```

```bash
# Build con Helm charts abilitato
kustomize build --enable-helm overlays/production

# oppure
kubectl kustomize --enable-helm overlays/production | kubectl apply -f -
```

!!! warning "Helm Inflator — Considerazioni"
    - Il rendering Helm avviene a ogni `kustomize build` (nessuna cache locale)
    - Le modifiche al chart esterno possono essere inaspettate se non si pinnano le versioni
    - Per ArgoCD, abilitare `--enable-helm` nell'ArgoCD configmap: `kustomize.buildOptions: --enable-helm`

---

## GitOps con ArgoCD e Kustomize

```yaml
# ArgoCD Application con Kustomize
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-production
  namespace: argocd
spec:
  project: production
  source:
    repoURL: https://github.com/company/k8s-config.git
    targetRevision: main
    path: overlays/production          # Kustomize directory

    # Opzioni Kustomize in ArgoCD
    kustomize:
      # Override image tag (alternativa a modificare kustomization.yaml)
      images:
        - registry.company.com/myapp:1.3.0

      # Namespace override (se non nel kustomization.yaml)
      namespace: production

      # Flag aggiuntivi passati a kustomize build
      commonLabels:
        argocd-managed: "true"

      # Build options (es. --enable-helm, --load-restrictor=none)
      # Configurabile nel ArgoCD ConfigMap:
      # kustomize.buildOptions: "--enable-helm --load-restrictor=LoadRestrictionsNone"

  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

**Pattern GitOps image promotion con Kustomize:**

```bash
# CI Pipeline: al build dell'immagine, aggiorna il kustomization.yaml
IMAGE_TAG="sha-$(git rev-parse --short HEAD)"
IMAGE_REF="registry.company.com/myapp:${IMAGE_TAG}"

# Aggiorna staging
kustomize edit set image "registry.company.com/myapp=${IMAGE_REF}" \
    --kustomization overlays/staging/kustomization.yaml

git add overlays/staging/kustomization.yaml
git commit -m "ci: deploy myapp ${IMAGE_TAG} to staging"
git push

# ArgoCD rileva il cambio e synca automaticamente staging
# Dopo validazione QA, promuovi in produzione:
kustomize edit set image "registry.company.com/myapp=${IMAGE_REF}" \
    --kustomization overlays/production/kustomization.yaml

git add overlays/production/kustomization.yaml
git commit -m "chore: promote myapp ${IMAGE_TAG} to production"
git push
# → ArgoCD synca produzione
```

---

## Validazione e Linting

```bash
# Validazione statica del kustomization.yaml
kustomize build overlays/production --dry-run 2>&1

# Kubeval — valida i manifest generati contro gli schema K8s
kustomize build overlays/production \
    | kubeval --strict --schema-location https://kubernetesjsonschema.dev

# Kubeconform (più aggiornato di kubeval)
kustomize build overlays/production \
    | kubeconform \
        -strict \
        -kubernetes-version 1.29.0 \
        -schema-location default \
        -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'

# Conftest — policy as code con OPA Rego
kustomize build overlays/production \
    | conftest test -p policy/ -

# policy/no-root.rego
# package main
# deny[msg] {
#   input.kind == "Deployment"
#   not input.spec.template.spec.securityContext.runAsNonRoot
#   msg := sprintf("Deployment %s deve avere runAsNonRoot=true", [input.metadata.name])
# }

# Kustomize build nella CI (GitHub Actions)
# - name: Validate kustomize
#   run: |
#     kustomize build overlays/production \
#       | kubeconform -strict -kubernetes-version 1.29.0
```

---

## Struttura Monorepo Multi-Cluster

```
gitops/
├── clusters/
│   ├── prod-eu-west-1/
│   │   └── kustomization.yaml      # cluster-specific patches
│   ├── prod-us-east-1/
│   │   └── kustomization.yaml
│   └── staging/
│       └── kustomization.yaml
├── apps/
│   ├── myapp/
│   │   ├── base/
│   │   └── overlays/
│   │       ├── staging/
│   │       └── production/
│   └── database/
│       ├── base/
│       └── overlays/
└── infrastructure/
    ├── cert-manager/
    ├── ingress-nginx/
    └── monitoring/
```

```yaml
# clusters/prod-eu-west-1/kustomization.yaml
# Composizione: include tutti i componenti per questo cluster
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  # Infrastruttura
  - ../../infrastructure/cert-manager
  - ../../infrastructure/ingress-nginx
  - ../../infrastructure/monitoring

  # Applicazioni (overlay production)
  - ../../apps/myapp/overlays/production
  - ../../apps/database/overlays/production

# Patch cluster-specific (es. replica count per questo cluster)
patches:
  - target:
      kind: Deployment
      name: myapp
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 10        # EU ha più traffico → più repliche

# Labels per identificare il cluster nei metrics
commonLabels:
  cluster: prod-eu-west-1
  region: eu-west-1
```

---

## Best Practices

```
Kustomize Best Practices

  Struttura:
  ✓ Base = risorse K8s "vanilla", valide da sole (kubectl apply -f base/ funziona)
  ✓ Overlay = solo le differenze, non ricopiare interi manifest
  ✓ Nomi file espliciti: patch-hpa-limits.yaml (non patch1.yaml)
  ✓ Un overlay per ambiente (staging/production), non per team
  ✓ Components per concern trasversali (monitoring, security, etc.)

  Patches:
  ✓ Strategic Merge Patch per la maggior parte dei casi (più leggibile)
  ✓ JSON 6902 per operazioni precise (remove, operazioni su array per indice)
  ✓ replacements per evitare duplicazione di valori tra risorse
  ✓ Inline patch per patch brevi (<10 righe), file separato altrimenti

  Image management:
  ✓ Sempre usare il campo images: (non patch manuale del tag)
  ✓ In produzione: digest sha256 invece di tag (immutabile)
  ✓ CI/CD: kustomize edit set image per aggiornamento automatizzato

  Remote bases:
  ✓ Pinnare SEMPRE a tag/SHA specifico (?ref=v1.2.0)
  ✓ Mai ?ref=main in produzione → build non riproducibili

  Validazione:
  ✓ kustomize build in CI prima del deploy
  ✓ kubectl diff -k per review pre-apply
  ✓ kubeconform per schema validation
  ✓ conftest/OPA per policy enforcement
```

---

## Troubleshooting

### Scenario 1 — `kustomize build` fallisce con "no such file or directory"

**Sintomo:** `Error: accumulating resources: accumulation err='accumulating resources from '../../base': ...no such file or directory`

**Causa:** Il path relativo in `resources:` o `components:` è errato rispetto alla posizione del `kustomization.yaml`. I path sono sempre relativi al file che li dichiara.

**Soluzione:** Verificare la struttura delle directory e i path relativi.

```bash
# Verificare la struttura
find . -name "kustomization.yaml" | head -20

# Testare il build dalla directory corretta
cd overlays/production && kustomize build .

# Oppure con path assoluto
kustomize build overlays/production
```

---

### Scenario 2 — JSON Patch fallisce con "add operation does not apply: doc is missing path"

**Sintomo:** `Error: json patch error: add operation does not apply: doc is missing path "/spec/template/metadata/annotations"`

**Causa:** `op: add` su un path intermedio inesistente (il parent non esiste). JSON Patch non crea path intermedi automaticamente.

**Soluzione:** Usare `op: add` sul path parent prima, oppure usare Strategic Merge Patch che gestisce la creazione di oggetti annidati.

```yaml
# SBAGLIATO: il parent /spec/template/metadata/annotations potrebbe non esistere
- op: add
  path: /spec/template/metadata/annotations/prometheus.io~1scrape
  value: "true"

# CORRETTO: crea prima il parent se non esiste
- op: add
  path: /spec/template/metadata/annotations
  value:
    prometheus.io/scrape: "true"

# ALTERNATIVA: Strategic Merge Patch (crea automaticamente i parent)
# patch-annotations.yaml
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
```

---

### Scenario 3 — `replacements` non propaga il valore, il campo rimane vuoto

**Sintomo:** Dopo `kustomize build`, il campo target non viene aggiornato con il valore sorgente.

**Causa:** Il `fieldPath` della sorgente o del target è errato, oppure il nome/kind della risorsa non corrisponde esattamente (case-sensitive).

**Soluzione:** Verificare i path con `kustomize build` e ispezionare il manifest generato.

```bash
# Generare il manifest e cercare il campo target
kustomize build overlays/production | grep -A5 "SERVICE_PORT"

# Verificare che la risorsa sorgente esista nel build
kustomize build overlays/production | grep -B2 "kind: Service"

# Debug: stampare tutto il manifest generato su file
kustomize build overlays/production > /tmp/manifest-debug.yaml
cat /tmp/manifest-debug.yaml | grep -A3 "fieldPath target"
```

```yaml
# Errore comune: fieldPath con notazione errata
replacements:
  - source:
      kind: Service
      name: myapp
      fieldPath: spec.ports[0].port    # SBAGLIATO: usare notazione con punto
      # fieldPath: spec.ports.0.port  # CORRETTO
```

---

### Scenario 4 — `--enable-helm` richiesto ma non abilitato in ArgoCD

**Sintomo:** ArgoCD mostra errore `helm not enabled` oppure i manifest Helm non vengono renderizzati.

**Causa:** L'integrazione Kustomize+Helm richiede il flag `--enable-helm` che non è attivo di default in ArgoCD per motivi di sicurezza.

**Soluzione:** Abilitare il flag nel ConfigMap di ArgoCD e verificare la versione di Kustomize supportata.

```bash
# Verificare la versione di kustomize usata da ArgoCD
kubectl -n argocd exec deploy/argocd-repo-server -- kustomize version

# Abilitare --enable-helm nel ConfigMap di ArgoCD
kubectl -n argocd edit configmap argocd-cm
```

```yaml
# argocd-cm — aggiungere buildOptions
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  kustomize.buildOptions: "--enable-helm"
  # Per versioni specifiche di kustomize
  kustomize.version.v5.3.0: "--enable-helm"
```

```bash
# Dopo la modifica, riavviare il repo-server
kubectl -n argocd rollout restart deployment/argocd-repo-server

# Verificare che l'Application synci correttamente
argocd app sync myapp-production --dry-run
```

---

### Scenario 5 — Component non applicato all'overlay

**Sintomo:** Le risorse o patch del Component non appaiono nel manifest generato dall'overlay.

**Causa:** Il `kind: Component` non può essere referenziato in `resources:` — deve essere referenziato in `components:`. Oppure il path del component è errato.

**Soluzione:** Verificare che il component usi `kind: Component` e sia referenziato correttamente.

```bash
# Verificare il kind del component
head -5 components/prometheus-monitoring/kustomization.yaml
# Deve mostrare: kind: Component

# Verificare che l'overlay lo referenzi in components: (non resources:)
grep -A10 "components:" overlays/production/kustomization.yaml

# Build di debug per vedere cosa viene incluso
kustomize build overlays/production | grep -c "prometheus.io/scrape"
```

```yaml
# SBAGLIATO: un Component non può stare in resources:
resources:
  - ../../base
  - ../../components/prometheus-monitoring   # ERRORE

# CORRETTO
resources:
  - ../../base
components:
  - ../../components/prometheus-monitoring   # CORRETTO
```

---

## Riferimenti

- [Kustomize Reference](https://kubectl.docs.kubernetes.io/references/kustomize/)
- [JSON Patch RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)
- [Kustomize Components](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/components/)
- [Replacements](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/replacements/)
- [Kustomize + ArgoCD](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/)
- [Helm Charts in Kustomize](https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/helmcharts/)
