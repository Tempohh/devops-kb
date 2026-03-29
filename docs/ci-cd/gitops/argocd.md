---
title: "ArgoCD"
slug: argocd
category: ci-cd
tags: [argocd, gitops, kubernetes, app-of-apps, applicationset, progressive-delivery, multi-cluster]
search_keywords: [argocd, argocd application, argocd app of apps, argocd applicationset, argocd multi cluster, argocd sso, argocd rbac, argocd notifications, argocd image updater, argocd rollouts, progressive delivery argocd, argocd sync policy, argocd helm, argocd kustomize]
parent: ci-cd/gitops/_index
related: [ci-cd/gitops/_index, ci-cd/gitops/flux, containers/kubernetes/_index, containers/helm/_index, containers/kustomize/_index]
official_docs: https://argo-cd.readthedocs.io/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# ArgoCD

## Panoramica

ArgoCD è uno strumento GitOps dichiarativo per Kubernetes che si installa come controller nel cluster e sincronizza continuamente lo stato del cluster con i manifesti Git. Ogni risorsa Kubernetes desiderata è rappresentata come una `Application` CRD (Custom Resource Definition — un'estensione dell'API Kubernetes che aggiunge nuovi tipi di oggetti personalizzati) che punta a un repository Git e a un namespace di destinazione. ArgoCD supporta Helm, Kustomize, Jsonnet e YAML plain come formati di configurazione, offre una web UI visuale per monitorare lo stato dei deployment, e include funzionalità avanzate come multi-cluster management, ApplicationSet per generazione di Application in bulk, e integrazione con Argo Rollouts per progressive delivery. ArgoCD è un progetto CNCF (Cloud Native Computing Foundation) Graduated.

## Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                         ArgoCD                                   │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │  API Server  │    │ Repo Server  │    │App Controller       │ │
│  │             │    │             │    │                     │ │
│  │ REST/gRPC   │    │ Clone repos │    │ Reconciliation loop │ │
│  │ Auth (Dex)  │    │ Render tmpl │    │ Status management  │ │
│  │ RBAC        │    │ Helm/Kustom │    │ Health assessment  │ │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘ │
│         │                  │                       │            │
│  ┌──────▼──────────────────▼───────────────────────▼──────────┐ │
│  │                    Redis (cache)                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Dex (OIDC Provider)    ArgoCD UI    ApplicationSet Controller││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ watch/apply (in-cluster)
                              ▼
              ┌───────────────────────────────┐
              │        Kubernetes API          │
              │   (cluster locale o remoti)    │
              └───────────────────────────────┘
```

| Componente | Responsabilità |
|-----------|----------------|
| **API Server** | Espone API REST/gRPC per CLI e UI, gestisce autenticazione e RBAC |
| **Repo Server** | Clona repository Git, renderizza template (Helm, Kustomize, Jsonnet) |
| **Application Controller** | Loop di reconciliazione: confronta desired state (Git) con live state (K8s) |
| **Dex** | Identity provider OIDC (OpenID Connect) per SSO (Single Sign-On) con GitHub, Okta, LDAP (Lightweight Directory Access Protocol), SAML (Security Assertion Markup Language) |
| **Redis** | Cache per rendering repository e stato applicazioni |
| **ApplicationSet Controller** | Genera Application CRD da generator (Git, Cluster, List, Matrix) |

### Installazione

```bash
# Installazione con kubectl
kubectl create namespace argocd
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/v2.10.0/manifests/install.yaml

# Installazione con Helm (raccomandato per produzione)
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 6.7.0 \
  -f argocd-values.yaml

# Accedere alla UI (port-forward per setup iniziale)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login iniziale (password iniziale: nome pod argocd-server)
argocd login localhost:8080 \
  --username admin \
  --password $(kubectl -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath="{.data.password}" | base64 -d)
```

## Application CRD

L'`Application` è la risorsa CRD principale di ArgoCD: definisce cosa sincronizzare e dove.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-staging
  namespace: argocd                                    # ArgoCD deve essere nel ns argocd
  labels:
    app.kubernetes.io/name: myapp
    environment: staging
  annotations:
    argocd.argoproj.io/sync-wave: "10"               # Ordine di sync
  finalizers:
    - resources-finalizer.argocd.argoproj.io         # Cancella le risorse K8s all'eliminazione dell'Application
spec:
  project: myteam                                     # AppProject di appartenenza

  source:
    repoURL: https://github.com/my-org/gitops-manifests
    targetRevision: HEAD                              # Branch, tag o SHA
    path: apps/myapp/overlays/staging                 # Path nel repo

    # Per Helm:
    # chart: myapp                                    # Se usi Helm chart (non path)
    # helm:
    #   releaseName: myapp
    #   valueFiles:
    #     - values-staging.yaml
    #   values: |
    #     replicaCount: 2
    #   parameters:
    #     - name: image.tag
    #       value: "1.2.3"

    # Per Kustomize (auto-rilevato se esiste kustomization.yaml):
    kustomize:
      images:
        - myapp=ghcr.io/my-org/myapp:v1.2.3          # Override image tag

  destination:
    server: https://kubernetes.default.svc            # Cluster locale
    # server: https://staging-cluster.example.com    # Cluster remoto
    namespace: myapp-staging

  syncPolicy:
    automated:
      prune: true           # Rimuove risorse K8s non più nel Git
      selfHeal: true        # Corregge il drift (modifiche manuali) automaticamente
      allowEmpty: false     # Non prune tutto se il source è vuoto
    syncOptions:
      - CreateNamespace=true             # Crea il namespace se non esiste
      - PrunePropagationPolicy=foreground # Aspetta che le risorse siano cancellate
      - ApplyOutOfSyncOnly=true          # Applica solo le risorse che differiscono
      - ServerSideApply=true             # Usa server-side apply (evita annotation troppo grandi)
      - RespectIgnoreDifferences=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m

  # Ignora differenze in campi gestiti da altri controller
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas                              # HPA gestisce le repliche, ArgoCD non deve toccarle
    - group: ""
      kind: ConfigMap
      name: kube-root-ca.crt
      jsonPointers:
        - /data

  # Override informazioni di revisione per display
  revisionHistoryLimit: 10

  info:
    - name: "Documentation"
      value: "https://confluence.mycompany.com/myapp"
```

## App of Apps Pattern

Il pattern App of Apps usa un'Application ArgoCD che gestisce altre Application. Permette di bootstrappare un intero cluster con un singolo punto di entrata.

```yaml
# Application "root" che gestisce tutte le altre
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/my-org/gitops-manifests
    targetRevision: HEAD
    path: environments/production/apps   # Contiene i manifest delle Application
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd                    # Le Application vengono create in argocd ns
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

```
environments/production/apps/
├── kustomization.yaml
├── myapp.yaml          # Application CRD per myapp
├── other-service.yaml  # Application CRD per other-service
├── cert-manager.yaml   # Application CRD per cert-manager
├── ingress-nginx.yaml  # Application CRD per ingress-nginx
└── monitoring.yaml     # Application CRD per prometheus/grafana
```

## ApplicationSet

ApplicationSet genera Application automaticamente da un insieme di parametri. È più potente del pattern App of Apps per gestire molti cluster o molte applicazioni.

### Generator List (Semplice)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: myapp-environments
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - env: dev
            cluster: https://dev-cluster.example.com
            namespace: myapp-dev
            replicas: "1"
          - env: staging
            cluster: https://staging-cluster.example.com
            namespace: myapp-staging
            replicas: "2"
          - env: production
            cluster: https://prod-cluster.example.com
            namespace: myapp-production
            replicas: "5"

  template:
    metadata:
      name: 'myapp-{{env}}'
      labels:
        environment: '{{env}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/my-org/gitops-manifests
        targetRevision: HEAD
        path: 'apps/myapp/overlays/{{env}}'
      destination:
        server: '{{cluster}}'
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

### Generator Matrix (Cross-Product)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: all-apps-all-clusters
  namespace: argocd
spec:
  generators:
    - matrix:
        generators:
          # Generator 1: tutti i cluster registrati in ArgoCD
          - clusters:
              selector:
                matchLabels:
                  environment: production  # Solo cluster di produzione
          # Generator 2: tutte le app nel repo Git
          - git:
              repoURL: https://github.com/my-org/gitops-manifests
              revision: HEAD
              directories:
                - path: apps/*
                  exclude: false
                - path: apps/experimental/*
                  exclude: true        # Escludi app sperimentali

  template:
    metadata:
      name: '{{name}}-{{path.basename}}'  # name=cluster, path.basename=nome app
    spec:
      project: default
      source:
        repoURL: https://github.com/my-org/gitops-manifests
        targetRevision: HEAD
        path: '{{path}}'
      destination:
        server: '{{server}}'
        namespace: '{{path.basename}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

### Generator Git con File

```yaml
# Ogni file JSON/YAML nel repo definisce un'Application
generators:
  - git:
      repoURL: https://github.com/my-org/gitops-manifests
      revision: HEAD
      files:
        - path: 'apps/*/config.json'   # Ogni file genera un'Application

# apps/myapp/config.json:
# {
#   "app": { "name": "myapp", "namespace": "myapp-prod" },
#   "destination": { "cluster": "production" }
# }
```

## Multi-Cluster Management

ArgoCD può gestire deployment su cluster Kubernetes multipli dal cluster hub.

```bash
# Aggiungere un cluster remoto (il contesto deve essere in ~/.kube/config)
argocd cluster add my-staging-cluster \
  --name staging \
  --label environment=staging \
  --label region=eu-west-1

argocd cluster add my-production-cluster \
  --name production \
  --label environment=production

# Listare i cluster registrati
argocd cluster list
```

```yaml
# Nelle Application, referenziare il cluster per nome o URL
destination:
  server: https://staging-k8s-api.example.com   # URL API server
  # oppure
  name: staging                                  # Nome del cluster registrato
  namespace: myapp
```

## Projects (AppProject)

Gli AppProject definiscono limiti di sicurezza e governance per gruppi di Application.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-payments
  namespace: argocd
spec:
  description: "Project per il team Payments"

  # Repository Git consentiti
  sourceRepos:
    - 'https://github.com/my-org/payments-*'
    - 'https://charts.helm.sh/stable'

  # Cluster e namespace di destinazione consentiti
  destinations:
    - server: https://kubernetes.default.svc
      namespace: payments-*                    # Wildcard per namespace
    - server: https://prod-cluster.example.com
      namespace: payments-production

  # Risorse Kubernetes che questo project può creare/modificare
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace                          # Può creare Namespace
  namespaceResourceBlacklist:
    - group: ''
      kind: ResourceQuota                      # Non può modificare ResourceQuota

  # Roles per RBAC
  roles:
    - name: developer
      description: "Developer del team Payments"
      policies:
        - p, proj:team-payments:developer, applications, get, team-payments/*, allow
        - p, proj:team-payments:developer, applications, sync, team-payments/*, allow
      groups:
        - my-org:payments-developers            # GitHub team

    - name: deployer
      description: "CI/CD deployer"
      policies:
        - p, proj:team-payments:deployer, applications, *, team-payments/*, allow
      jwtTokens:
        - iat: 1706745600                       # Token generato per la CI

  # Finestre di sync (manutenzione programmatica)
  syncWindows:
    - kind: allow
      schedule: '* 9-17 * * 1-5'              # Solo deploy in orario lavorativo
      duration: 8h
      applications:
        - '*'
      manualSync: true                          # Permetti sync manuale anche fuori finestra
    - kind: deny
      schedule: '0 0 * * 5'                   # No deploy venerdì sera
      duration: 72h
      applications:
        - '*payments*'
```

## SSO e RBAC

```yaml
# ConfigMap argocd-cm — Configurazione SSO con GitHub OAuth
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  # URL pubblico di ArgoCD (IMPORTANTE: deve corrispondere al callback OAuth)
  url: https://argocd.mycompany.com

  # Dex connector per GitHub
  dex.config: |
    connectors:
    - type: github
      id: github
      name: GitHub
      config:
        clientID: $dex.github.clientID        # Da secret argocd-secret
        clientSecret: $dex.github.clientSecret
        redirectURI: https://argocd.mycompany.com/api/dex/callback
        orgs:
        - name: my-org
          teams:
          - platform-team
          - developers

  # Oppure OIDC generico (Okta, Azure AD, Keycloak)
  # dex.config: |
  #   connectors:
  #   - type: oidc
  #     id: okta
  #     name: Okta
  #     config:
  #       issuer: https://mycompany.okta.com
  #       clientID: $dex.okta.clientID
  #       clientSecret: $dex.okta.clientSecret
  #       redirectURI: https://argocd.mycompany.com/api/dex/callback
  #       getUserInfo: true
  #       insecureEnableGroups: true

  # Admin account (disabilitare in produzione dopo setup SSO)
  admin.enabled: "false"
```

```yaml
# ConfigMap argocd-rbac-cm — Policy RBAC
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  # Policy format: p, <subject>, <resource>, <action>, <object>, <effect>
  # Subjects: user:<email>, group:<group>
  # Resources: applications, applicationsets, clusters, repositories, ...
  # Actions: get, create, update, delete, sync, override, action
  policy.csv: |
    # Admins: accesso completo
    g, my-org:platform-team, role:admin

    # Developers: lettura e sync su tutti i progetti
    p, role:developer, applications, get, */*, allow
    p, role:developer, applications, sync, */*, allow
    p, role:developer, logs, get, */*, allow
    g, my-org:developers, role:developer

    # CI/CD service account: gestione applicazioni
    p, role:ci-deployer, applications, get, */*, allow
    p, role:ci-deployer, applications, sync, */*, allow
    p, role:ci-deployer, applications, update, */*, allow
    g, serviceaccount:argocd:ci-deployer, role:ci-deployer

    # Read-only per tutti gli autenticati
    p, role:readonly, applications, get, */*, allow
    p, role:readonly, clusters, get, *, allow
    g, *, role:readonly

  policy.default: role:readonly
  scopes: '[groups, email]'
```

## Sync Hooks e Waves

Gli hook permettono di eseguire azioni prima/durante/dopo la sincronizzazione. Le waves controllano l'ordine di applicazione.

```yaml
# Pre-sync hook: database migration prima del deploy
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  annotations:
    argocd.argoproj.io/hook: PreSync                      # Eseguito prima della sync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded  # Cancella il Job dopo successo
    argocd.argoproj.io/sync-wave: "-5"                   # Wave negativa: eseguito prima
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migration
          image: ghcr.io/my-org/myapp:latest
          command: ["./scripts/migrate.sh"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: url

---
# Sync wave per namespace prima del deployment
apiVersion: v1
kind: Namespace
metadata:
  name: myapp-production
  annotations:
    argocd.argoproj.io/sync-wave: "-10"    # Crea namespace per primo

---
# Post-sync hook: smoke test dopo il deploy
apiVersion: batch/v1
kind: Job
metadata:
  name: smoke-test
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: smoke-test
          image: curlimages/curl:latest
          command:
            - sh
            - -c
            - |
              curl --fail --retry 5 --retry-delay 10 \
                https://myapp-production.example.com/health || exit 1
```

## ArgoCD Image Updater

ArgoCD Image Updater monitora i registry Docker e aggiorna automaticamente il tag dell'immagine nel repository Git.

```yaml
# Installazione
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj-labs/argocd-image-updater/v0.12.2/manifests/install.yaml

# Annotazioni sull'Application per configurare l'aggiornamento
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
  annotations:
    # Lista immagini da monitorare
    argocd-image-updater.argoproj.io/image-list: |
      myapp=ghcr.io/my-org/myapp

    # Strategia di aggiornamento: semver, latest, digest, name
    argocd-image-updater.argoproj.io/myapp.update-strategy: semver

    # Constraint semver
    argocd-image-updater.argoproj.io/myapp.allow-tags: regexp:^v[0-9]+\.[0-9]+\.[0-9]+$

    # Come aggiornare: git (commit nel repo) o argocd (aggiornamento diretto)
    argocd-image-updater.argoproj.io/write-back-method: git

    # Branch su cui fare il commit
    argocd-image-updater.argoproj.io/git-branch: main

    # File da aggiornare (per Kustomize)
    argocd-image-updater.argoproj.io/myapp.kustomize.image-name: ghcr.io/my-org/myapp
```

## Argo Rollouts — Progressive Delivery

Argo Rollouts estende Kubernetes con strategie di deployment avanzate (Canary, Blue-Green) con analisi automatiche.

```yaml
# Installazione
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f \
  https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Rollout Canary con analisi Prometheus
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
  namespace: myapp-production
spec:
  replicas: 10
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:v1.2.3
          ports:
            - containerPort: 8080

  strategy:
    canary:
      stableService: myapp-stable       # Service che punta alla versione stabile
      canaryService: myapp-canary       # Service che punta alla versione canary
      trafficRouting:
        nginx:                           # Integrazione con NGINX Ingress
          stableIngress: myapp-ingress
      steps:
        - setWeight: 5                   # 5% traffico alla canary
        - pause: {duration: 2m}
        - analysis:
            templates:
              - templateName: error-rate-check
            args:
              - name: service-name
                value: myapp-canary
        - setWeight: 25
        - pause: {duration: 5m}
        - analysis:
            templates:
              - templateName: error-rate-check
              - templateName: latency-check
            args:
              - name: service-name
                value: myapp-canary
        - setWeight: 50
        - pause: {duration: 10m}
        - setWeight: 100                 # Promozione completa

---
# AnalysisTemplate: definisce le metriche di successo
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: error-rate-check
  namespace: myapp-production
spec:
  args:
    - name: service-name
  metrics:
    - name: error-rate
      interval: 1m
      successCondition: result[0] <= 0.01    # Max 1% errori
      failureLimit: 3
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(http_requests_total{service="{{args.service-name}}",status=~"5.."}[2m]))
            /
            sum(rate(http_requests_total{service="{{args.service-name}}"}[2m]))

    - name: latency-p99
      interval: 1m
      successCondition: result[0] <= 0.5    # Max 500ms al p99
      failureLimit: 3
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            histogram_quantile(0.99,
              sum(rate(http_request_duration_seconds_bucket{service="{{args.service-name}}"}[2m]))
              by (le)
            )

---
# Rollout Blue-Green
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp-bluegreen
spec:
  replicas: 5
  strategy:
    blueGreen:
      activeService: myapp-active       # Service che riceve il traffico live
      previewService: myapp-preview     # Service per il preview/test
      autoPromotionEnabled: false       # Richiede approvazione manuale
      scaleDownDelaySeconds: 300        # Aspetta 5 min prima di scalare down i vecchi pod
      prePromotionAnalysis:
        templates:
          - templateName: error-rate-check
        args:
          - name: service-name
            value: myapp-preview
```

## Troubleshooting

### Scenario 1 — Application bloccata in stato `OutOfSync` dopo commit

**Sintomo:** L'Application rimane `OutOfSync` anche dopo un commit corretto; il sync manuale non produce effetti visibili o genera errori generici.

**Causa:** ArgoCD non riesce a renderizzare i template (Helm/Kustomize) per errori nel source, oppure ci sono differenze nei campi ignorati male configurati.

**Soluzione:** Ispezionare i log del repo-server e forzare un refresh del cache Git.

```bash
# Forza il refresh del cache Git per l'Application
argocd app get myapp-staging --refresh

# Visualizza i diff dettagliati tra desired state e live state
argocd app diff myapp-staging --local

# Ispeziona errori di rendering nel repo-server
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server --tail=100

# Forza sync con prune esplicito (attenzione: rimuove risorse non nel Git)
argocd app sync myapp-staging --prune --force
```

---

### Scenario 2 — Sync fallisce con `ComparisonError` o `PermissionDenied`

**Sintomo:** La sync mostra errore `ComparisonError: failed to get cluster info` oppure `PermissionDenied` su alcune risorse Kubernetes.

**Causa 1 (ComparisonError):** Il cluster remoto non è più raggiungibile o le credenziali sono scadute.
**Causa 2 (PermissionDenied):** Il ServiceAccount di ArgoCD non ha i permessi RBAC Kubernetes necessari per le risorse target.

**Soluzione:**

```bash
# Verifica lo stato dei cluster registrati
argocd cluster list

# Controlla gli errori di connessione al cluster
argocd cluster get https://staging-k8s-api.example.com

# Rinnova le credenziali del cluster (ricollega)
argocd cluster add my-staging-cluster --name staging --upsert

# Ispeziona i permessi del ServiceAccount argocd-application-controller
kubectl auth can-i create deployments \
  --as=system:serviceaccount:argocd:argocd-application-controller \
  -n myapp-staging

# Visualizza log dell'application controller per errori RBAC
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller --tail=200 | grep -i "permission\|forbidden\|error"
```

---

### Scenario 3 — Drift continuo: ArgoCD corregge sempre le stesse risorse

**Sintomo:** L'Application con `selfHeal: true` esegue sync continuamente (loop), ripristinando sempre le stesse risorse (es. `Deployment`, `HPA`).

**Causa:** Un controller esterno (HPA, Cluster Autoscaler, Operator) modifica campi che ArgoCD considera parte del desired state, generando drift continuo. Campo tipico: `spec.replicas` gestito da HPA.

**Soluzione:** Configurare `ignoreDifferences` per i campi gestiti da altri controller.

```yaml
# Nel manifest Application — ignorare spec.replicas se HPA è attivo
spec:
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
    - group: autoscaling
      kind: HorizontalPodAutoscaler
      jqPathExpressions:
        - .spec.metrics[].resource.target.averageUtilization

# Verifica quante sync sono state eseguite nelle ultime ore
argocd app history myapp-staging

# Controlla il numero di sync recenti (loop indicator)
kubectl get applications -n argocd myapp-staging -o jsonpath='{.status.history}' | jq 'length'
```

---

### Scenario 4 — `argocd login` fallisce o SSO non funziona

**Sintomo:** Il comando `argocd login` restituisce `FATA[...] dial tcp: connection refused` o il redirect SSO via Dex non completa il login (errore `invalid_client` o pagina bianca).

**Causa 1:** L'URL configurato in `argocd-cm` (`url:`) non corrisponde all'URL effettivo usato nel browser (mismatch del redirect URI OAuth).
**Causa 2:** Il secret `argocd-secret` non contiene le credenziali OAuth corrette per Dex.

**Soluzione:**

```bash
# Verifica la configurazione attuale di argocd-cm
kubectl get configmap argocd-cm -n argocd -o yaml | grep -A5 "url\|dex.config"

# Controlla i log di Dex per errori OAuth
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-dex-server --tail=100 | grep -i "error\|invalid\|failed"

# Verifica i secret Dex
kubectl get secret argocd-secret -n argocd -o jsonpath='{.data}' | jq 'keys'

# Reset password admin (utile se SSO non funziona in emergenza)
# 1. Genera hash bcrypt della nuova password
htpasswd -nbBC 10 "" 'MyNewPassword!' | tr -d ':\n' | sed 's/$2y/$2a/'
# 2. Aggiorna il secret
kubectl patch secret argocd-secret -n argocd \
  --type merge \
  -p '{"stringData":{"admin.password":"<hash-bcrypt>","admin.passwordMtime":"'$(date +%FT%T%Z)'"}}'

# Riabilita account admin temporaneamente
kubectl patch configmap argocd-cm -n argocd \
  --type merge -p '{"data":{"admin.enabled":"true"}}'
kubectl rollout restart deployment argocd-server -n argocd
```

---

## Relazioni

??? info "GitOps — Principi e Confronto ArgoCD vs Flux"
    I 4 principi GitOps, push vs pull deployment, mono-repo vs poly-repo strategy.

    **Approfondimento completo →** [GitOps](_index.md)

??? info "Flux CD"
    Alternativa GitOps basata su GitOps Toolkit: controller separati, SOPS integrato, image automation nativa.

    **Approfondimento completo →** [Flux CD](flux.md)

??? info "Kustomize"
    ArgoCD supporta Kustomize nativamente. Kustomize permette overlay per ambienti (dev/staging/prod) partendo da una base comune.

    **Approfondimento completo →** [Kustomize](../../containers/kustomize/_index.md)

## Riferimenti

- [ArgoCD Getting Started](https://argo-cd.readthedocs.io/en/stable/getting_started/)
- [Application CRD reference](https://argo-cd.readthedocs.io/en/stable/operator-manual/application-specification/)
- [ApplicationSet documentation](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
- [ArgoCD RBAC configuration](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
- [ArgoCD Sync Hooks](https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/)
- [ArgoCD Image Updater](https://argocd-image-updater.readthedocs.io/)
- [Argo Rollouts documentation](https://argo-rollouts.readthedocs.io/)
- [ArgoCD Helm chart values](https://github.com/argoproj/argo-helm/blob/main/charts/argo-cd/values.yaml)
