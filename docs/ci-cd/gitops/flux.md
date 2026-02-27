---
title: "Flux CD"
slug: flux
category: ci-cd
tags: [flux, gitops, kubernetes, helmrelease, kustomization, flagger, progressive-delivery]
search_keywords: [flux cd, flux v2, gitrepository, ocirepository, helmrelease, kustomization flux, flagger, progressive delivery flux, flux image automation, flux notification, flux multi tenancy, weave gitops, flux bootstrap]
parent: ci-cd/gitops/_index
related: [ci-cd/gitops/_index, ci-cd/gitops/argocd, containers/helm/_index, containers/kustomize/_index]
official_docs: https://fluxcd.io/flux/
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Flux CD

## Panoramica

Flux CD (v2) è un set di controller Kubernetes che implementano GitOps secondo il GitOps Toolkit. A differenza di ArgoCD (architettura monolitica), Flux è composto da controller indipendenti e specializzati: il Source Controller gestisce le sorgenti (Git, Helm, OCI), il Kustomize Controller applica i manifesti, il Helm Controller gestisce i release Helm, il Notification Controller gestisce gli alert, e l'Image Automation Controller aggiorna automaticamente i tag delle immagini nel repository Git. Ogni componente espone CRD Kubernetes e può essere usato in modo indipendente. Flux è un progetto CNCF Graduated.

## Architettura — GitOps Toolkit

```
┌─────────────────────────────────────────────────────────────────┐
│                      Flux GitOps Toolkit                         │
│                                                                  │
│  ┌──────────────────┐   ┌──────────────────┐                   │
│  │ Source Controller │   │Kustomize Controller│                  │
│  │                  │   │                  │                   │
│  │ GitRepository    │──►│ Kustomization    │                   │
│  │ OCIRepository    │   │ (applica YAML/   │                   │
│  │ HelmRepository   │   │  Kustomize al    │                   │
│  │ HelmChart        │   │  cluster)        │                   │
│  │ Bucket           │   └──────────────────┘                   │
│  └──────────────────┘                                           │
│          │                ┌──────────────────┐                  │
│          │                │  Helm Controller  │                  │
│          └───────────────►│                  │                  │
│                           │  HelmRelease     │                  │
│                           │  (gestisce Helm  │                  │
│                           │   releases)      │                  │
│                           └──────────────────┘                  │
│                                                                  │
│  ┌──────────────────┐   ┌──────────────────────────────────┐   │
│  │ Notification     │   │    Image Automation Controller    │   │
│  │ Controller       │   │                                  │   │
│  │                  │   │ ImageRepository                  │   │
│  │ Alert            │   │ ImagePolicy (semver/alpha)       │   │
│  │ Provider         │   │ ImageUpdateAutomation            │   │
│  │ (Slack, GH, PD)  │   │ (commit nel repo Git)            │   │
│  └──────────────────┘   └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Bootstrap

Il bootstrap installa Flux nel cluster e configura il repository GitOps su GitHub/GitLab/Gitea/Bitbucket. Dopo il bootstrap, il cluster è completamente gestito da Git.

```bash
# Prerequisiti: kubectl configurato, token GitHub/GitLab

# Bootstrap su GitHub (repo esistente o nuovo)
flux bootstrap github \
  --owner=my-org \
  --repository=gitops-manifests \
  --branch=main \
  --path=clusters/production \
  --personal=false \               # Usa GitHub App o PAT org
  --token-auth                     # Usa GITHUB_TOKEN per autenticazione

# Bootstrap su GitLab
flux bootstrap gitlab \
  --owner=my-group \
  --repository=gitops-manifests \
  --branch=main \
  --path=clusters/production \
  --token-auth

# Cosa fa il bootstrap:
# 1. Crea il repository se non esiste
# 2. Genera le chiavi SSH o usa il token
# 3. Installa i CRD e i controller Flux nel namespace flux-system
# 4. Crea un GitRepository source che punta al repo
# 5. Crea una Kustomization che punta a clusters/production
# 6. Fa commit dei manifest nel repository
# 7. Il cluster diventa self-managed: Flux si aggiorna da solo

# Verificare lo stato dopo il bootstrap
flux check
flux get all -n flux-system
```

## Source Controller — GitRepository

```yaml
# Source: punta al repository Git che contiene i manifesti
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: gitops-manifests
  namespace: flux-system
spec:
  interval: 1m                                    # Poll ogni minuto
  url: https://github.com/my-org/gitops-manifests
  ref:
    branch: main
    # oppure tag specifico:
    # tag: v1.2.3
    # oppure commit SHA:
    # commit: a3f8c2d4b5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0
  secretRef:
    name: github-credentials    # Secret con SSH key o token HTTPS

---
# Secret per autenticazione HTTPS
apiVersion: v1
kind: Secret
metadata:
  name: github-credentials
  namespace: flux-system
stringData:
  username: git
  password: "ghp_..."    # GitHub PAT o App token

---
# Oppure con SSH key
apiVersion: v1
kind: Secret
metadata:
  name: github-ssh-key
  namespace: flux-system
stringData:
  identity: |
    -----BEGIN OPENSSH PRIVATE KEY-----
    ...
    -----END OPENSSH PRIVATE KEY-----
  identity.pub: |
    ssh-ed25519 AAAA...
  known_hosts: |
    github.com ecdsa-sha2-nistp256 AAAA...
```

### OCIRepository — Artefatti OCI

```yaml
# Source OCI: consuma manifesti distribuiti come OCI artifact
# (es. pushati con flux push artifact o ko)
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: myapp-manifests
  namespace: flux-system
spec:
  interval: 5m
  url: oci://ghcr.io/my-org/myapp-manifests
  ref:
    tag: latest
    # oppure digest:
    # digest: sha256:abc123...
  secretRef:
    name: ghcr-credentials
  verify:
    provider: cosign           # Verifica firma Cosign
    secretRef:
      name: cosign-public-key
```

## Kustomize Controller — Kustomization

La `Kustomization` di Flux (diversa dalla `kustomize.config.k8s.io/v1beta1`) è il CRD che applica i manifesti al cluster.

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: myapp-staging
  namespace: flux-system
spec:
  interval: 5m                            # Reconciliation ogni 5 minuti
  retryInterval: 1m                       # Retry in caso di errore
  timeout: 2m                             # Timeout per applicazione

  # Sorgente: punta al GitRepository (o OCIRepository)
  sourceRef:
    kind: GitRepository
    name: gitops-manifests

  path: ./apps/myapp/overlays/staging    # Path nel repo

  prune: true                             # Rimuove risorse K8s cancellate dal Git
  wait: true                              # Aspetta che tutte le risorse siano ready

  # Health check: aspetta che Deployment sia Available
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: myapp
      namespace: myapp-staging

  # Dipendenze: aspetta che queste Kustomization siano ready prima
  dependsOn:
    - name: cert-manager
    - name: ingress-nginx

  # Decryption SOPS
  decryption:
    provider: sops
    secretRef:
      name: sops-age-key

  # Patch dinamiche sulle risorse (senza modificare il repo)
  patches:
    - patch: |
        - op: replace
          path: /spec/replicas
          value: 2
      target:
        kind: Deployment
        name: myapp

  # Sostituzione variabili (${ } nelle risorse)
  postBuild:
    substitute:
      ENVIRONMENT: staging
      REPLICA_COUNT: "2"
    substituteFrom:
      - kind: ConfigMap
        name: cluster-config
      - kind: Secret
        name: cluster-secrets
        optional: true
```

### Struttura Raccomandata del Repository

```
gitops-manifests/
├── clusters/
│   ├── production/
│   │   ├── flux-system/         # Bootstrap Flux (auto-generato)
│   │   │   └── gotk-sync.yaml
│   │   ├── infrastructure.yaml  # Kustomization per infra
│   │   └── apps.yaml            # Kustomization per apps
│   └── staging/
│       ├── flux-system/
│       ├── infrastructure.yaml
│       └── apps.yaml
├── infrastructure/
│   ├── base/
│   │   ├── cert-manager/        # HelmRelease cert-manager
│   │   ├── ingress-nginx/       # HelmRelease ingress-nginx
│   │   └── monitoring/          # HelmRelease prometheus-stack
│   └── overlays/
│       ├── production/          # Patch produzione (più repliche, etc.)
│       └── staging/
└── apps/
    ├── base/
    │   └── myapp/               # Manifesti base
    └── overlays/
        ├── production/
        └── staging/
```

## Helm Controller — HelmRelease

```yaml
# HelmRepository: sorgente del chart
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: ingress-nginx
  namespace: flux-system
spec:
  interval: 1h
  url: https://kubernetes.github.io/ingress-nginx
  # Per OCI registry:
  # type: oci
  # url: oci://ghcr.io/my-org/helm-charts

---
# HelmRelease: gestisce un Helm release
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: ingress-nginx
  namespace: flux-system
spec:
  interval: 10m
  chart:
    spec:
      chart: ingress-nginx
      version: ">=4.9.0 <5.0.0"     # Constraint semver (auto-upgrade nei range)
      sourceRef:
        kind: HelmRepository
        name: ingress-nginx
      interval: 1h

  # Values inline
  values:
    controller:
      replicaCount: 2
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 500m
          memory: 512Mi
      metrics:
        enabled: true
        serviceMonitor:
          enabled: true
      config:
        use-gzip: "true"
        enable-brotli: "true"

  # Values da ConfigMap o Secret
  valuesFrom:
    - kind: ConfigMap
      name: ingress-nginx-values
      valuesKey: values.yaml        # Key nel ConfigMap
    - kind: Secret
      name: ingress-nginx-secrets
      optional: true

  # Upgrade configuration
  upgrade:
    remediation:
      remediateLastFailure: true
      retries: 3
      strategy: rollback             # rollback | uninstall
    cleanupOnFail: true
    force: false                     # Force recreate se CRD cambia

  # Install configuration
  install:
    createNamespace: true
    remediation:
      retries: 3

  # Post-renderer con Kustomize (patch dopo il render del chart)
  postRenderers:
    - kustomize:
        patches:
          - patch: |
              - op: add
                path: /metadata/annotations/custom.annotation
                value: "managed-by-flux"
            target:
              kind: Deployment
              labelSelector: "app.kubernetes.io/name=ingress-nginx"

  # Rollback automatico
  rollback:
    timeout: 5m
    disableWait: false
    disableHooks: false
    recreate: false
    force: false
    cleanupOnFail: false

  # Dependency
  dependsOn:
    - name: cert-manager
      namespace: flux-system
```

## SOPS — Secrets Cifrati nel Repository

SOPS permette di cifrare i secrets Kubernetes e committarli in chiaro nel repository Git.

```bash
# Installare SOPS
brew install sops                    # macOS
# o scaricare il binario: github.com/getsops/sops/releases

# Generare una chiave age (raccomandato per semplicità)
age-keygen -o age.agekey
cat age.agekey
# public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Cifrare un secret con age
sops --encrypt \
  --age age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  --encrypted-regex '^(data|stringData)$' \
  secret.yaml > secret.enc.yaml

# Decifrare per modifica
sops --decrypt secret.enc.yaml > secret.yaml
sops secret.enc.yaml    # Apre l'editor con decifrazione automatica

# .sops.yaml — configurazione nel repository
creation_rules:
  - path_regex: .*/production/.*
    age: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,age1yyyyyy...
  - path_regex: .*/staging/.*
    age: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```yaml
# Configurare Flux per decifrare con SOPS
# Step 1: creare il secret con la chiave privata age nel cluster
kubectl create secret generic sops-age-key \
  --namespace=flux-system \
  --from-file=age.agekey=/path/to/age.agekey

# Step 2: nella Kustomization, aggiungere la decryption config
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: myapp
  namespace: flux-system
spec:
  # ...
  decryption:
    provider: sops
    secretRef:
      name: sops-age-key   # Secret con la chiave privata
```

## Image Automation Controller

L'Image Automation Controller monitora i registri container e aggiorna automaticamente il tag dell'immagine nel repository Git.

```yaml
# Step 1: ImageRepository — monitora un registry
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImageRepository
metadata:
  name: myapp
  namespace: flux-system
spec:
  image: ghcr.io/my-org/myapp
  interval: 1m
  secretRef:
    name: ghcr-credentials      # Secret per registry privato
  # Filtra i tag da considerare
  exclusionList:
    - "^.*-dev$"
    - "^latest$"
    - "^sha-[a-z0-9]{7}$"

---
# Step 2: ImagePolicy — definisce quale tag selezionare
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImagePolicy
metadata:
  name: myapp
  namespace: flux-system
spec:
  imageRepositoryRef:
    name: myapp
  policy:
    # Semver: seleziona il tag più recente nel range
    semver:
      range: ">=1.0.0 <2.0.0"
    # Oppure alphabetical (latest lexicographic)
    # alphabetical:
    #   order: asc   # asc | desc
    # Oppure numerical (numero più alto)
    # numerical:
    #   order: asc

---
# Step 3: Annotare il file che contiene il tag dell'immagine
# In apps/myapp/overlays/production/deployment.yaml:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:1.0.5  # {"$imagepolicy": "flux-system:myapp"}

---
# Step 4: ImageUpdateAutomation — commit nel repo Git
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImageUpdateAutomation
metadata:
  name: myapp-image-updater
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: gitops-manifests

  git:
    commit:
      author:
        email: fluxbot@mycompany.com
        name: Flux Image Updater
      messageTemplate: |
        chore(image): update {{range .Updated.Images}}{{.Name}} to {{.NewTag}}{{end}}
    push:
      branch: main
      # Oppure push su un branch separato per PR review:
      # branch: flux/image-updates

  update:
    path: ./apps
    strategy: Setters           # Aggiorna le annotazioni {"$imagepolicy": "..."}
```

## Notification Controller

```yaml
# Provider: destinazione delle notifiche
apiVersion: notification.toolkit.fluxcd.io/v1beta3
kind: Provider
metadata:
  name: slack-notifications
  namespace: flux-system
spec:
  type: slack
  channel: "#gitops-alerts"
  secretRef:
    name: slack-webhook-url    # Secret con data.address = webhook URL

---
# Provider per GitHub commit status
apiVersion: notification.toolkit.fluxcd.io/v1beta3
kind: Provider
metadata:
  name: github-status
  namespace: flux-system
spec:
  type: github
  address: https://github.com/my-org/gitops-manifests
  secretRef:
    name: github-token

---
# Alert: regola quali eventi notificare
apiVersion: notification.toolkit.fluxcd.io/v1beta3
kind: Alert
metadata:
  name: production-alerts
  namespace: flux-system
spec:
  providerRef:
    name: slack-notifications
  eventSeverity: error          # info | error
  eventSources:
    - kind: Kustomization
      name: '*'                  # Tutti le Kustomization
      namespace: flux-system
    - kind: HelmRelease
      name: '*'
      namespace: flux-system
  exclusionList:
    - ".*waiting.*"             # Escludi messaggi di attesa
  summary: "Produzione GitOps Alert"
```

## Multi-Tenancy

Flux supporta multi-tenancy tramite namespace isolation e ServiceAccount impersonation.

```yaml
# Tenant A: namespace isolato con permessi limitati
apiVersion: v1
kind: Namespace
metadata:
  name: team-a
  labels:
    toolkit.fluxcd.io/tenant: "team-a"

---
# ServiceAccount per il tenant (ha solo accesso al suo namespace)
apiVersion: v1
kind: ServiceAccount
metadata:
  name: flux-reconciler
  namespace: team-a

---
# RoleBinding: permessi limitati al namespace team-a
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: flux-reconciler
  namespace: team-a
subjects:
  - kind: ServiceAccount
    name: flux-reconciler
    namespace: team-a
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin              # Limita questo a un Role con meno permessi in prod

---
# Kustomization del tenant con impersonation
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: team-a-apps
  namespace: team-a                  # Kustomization nel namespace del tenant
spec:
  interval: 5m
  path: ./teams/team-a
  sourceRef:
    kind: GitRepository
    name: team-a-repo
    namespace: team-a
  serviceAccountName: flux-reconciler  # Usa il SA del tenant (non admin)
  prune: true
  targetNamespace: team-a            # Forza tutto nel namespace del tenant
```

## Flagger — Progressive Delivery

Flagger è un operatore Kubernetes che automatizza il deployment progressivo (Canary, Blue-Green, A/B Testing) usando metriche da Prometheus, Datadog, ecc.

```bash
# Installazione Flagger con Helm
helm repo add flagger https://flagger.app
helm repo update

# Installare con integrazione NGINX Ingress
helm install flagger flagger/flagger \
  --namespace flagger-system \
  --create-namespace \
  --set meshProvider=nginx \
  --set metricsServer=http://prometheus.monitoring.svc.cluster.local:9090
```

```yaml
# Canary CRD — Definisce la strategia di release progressiva
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: myapp
  namespace: myapp-production
spec:
  # Target: Deployment da gestire
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp

  # IngressRef: per traffic splitting con NGINX
  ingressRef:
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    name: myapp-ingress

  progressDeadlineSeconds: 600       # Max 10 minuti per completare la canary

  service:
    port: 80
    targetPort: 8080

  analysis:
    interval: 1m                     # Intervallo di analisi
    threshold: 5                     # Max 5 failures consecutive
    maxWeight: 50                    # Max 50% traffico alla canary
    stepWeight: 10                   # Incrementa 10% per step

    # Metriche di successo
    metrics:
      - name: request-success-rate
        thresholdRange:
          min: 99                    # Min 99% richieste success
        interval: 1m

      - name: request-duration
        thresholdRange:
          max: 500                   # Max 500ms latenza media
        interval: 1m

      # MetricTemplate custom con query Prometheus
      - name: custom-error-rate
        templateRef:
          name: error-rate
          namespace: flagger-system
        thresholdRange:
          max: 1                     # Max 1% errori
        interval: 1m

    # Webhook pre/post analisi
    webhooks:
      - name: acceptance-test
        type: pre-rollout
        url: http://flagger-loadtester.myapp-production/
        timeout: 30s
        metadata:
          type: bash
          cmd: "curl -s http://myapp-canary.myapp-production/health | grep 'ok'"

      - name: load-test
        url: http://flagger-loadtester.myapp-production/
        timeout: 5s
        metadata:
          type: cmd
          cmd: "hey -z 1m -q 10 -c 2 http://myapp-canary.myapp-production/"

    # Alert Slack se rollback
    alerts:
      - name: "Flagger Alert"
        severity: error
        providerRef:
          name: slack-notifications
          namespace: flux-system

---
# MetricTemplate custom
apiVersion: flagger.app/v1beta1
kind: MetricTemplate
metadata:
  name: error-rate
  namespace: flagger-system
spec:
  provider:
    type: prometheus
    address: http://prometheus.monitoring.svc.cluster.local:9090
  query: |
    sum(
      rate(
        http_requests_total{
          namespace="{{ namespace }}",
          service="{{ target }}",
          status_code=~"5.."
        }[{{ interval }}]
      )
    )
    /
    sum(
      rate(
        http_requests_total{
          namespace="{{ namespace }}",
          service="{{ target }}"
        }[{{ interval }}]
      )
    ) * 100
```

## Relazioni

??? info "GitOps — Principi e Confronto ArgoCD vs Flux"
    I 4 principi GitOps, push vs pull deployment, quando scegliere Flux vs ArgoCD.

    **Approfondimento completo →** [GitOps](_index.md)

??? info "ArgoCD"
    Alternativa GitOps con UI visuale, multi-cluster hub-and-spoke, ApplicationSet.

    **Approfondimento completo →** [ArgoCD](argocd.md)

??? info "Kustomize"
    Flux usa Kustomize nativamente per overlay e patch. Capire Kustomize è fondamentale per usare Flux.

    **Approfondimento completo →** [Kustomize](../../containers/kustomize/_index.md)

## Riferimenti

- [Flux documentation](https://fluxcd.io/flux/)
- [Flux bootstrap GitHub](https://fluxcd.io/flux/installation/bootstrap/github/)
- [GitRepository API reference](https://fluxcd.io/flux/components/source/gitrepositories/)
- [Kustomization API reference](https://fluxcd.io/flux/components/kustomize/kustomizations/)
- [HelmRelease API reference](https://fluxcd.io/flux/components/helm/helmreleases/)
- [Image Automation Controller](https://fluxcd.io/flux/components/image/)
- [SOPS integration](https://fluxcd.io/flux/guides/mozilla-sops/)
- [Multi-tenancy](https://fluxcd.io/flux/installation/configuration/multitenancy/)
- [Flagger documentation](https://docs.flagger.app/)
- [Weave GitOps (UI per Flux)](https://docs.gitops.weave.works/)
