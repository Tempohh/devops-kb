---
title: "Backstage"
slug: backstage
category: ci-cd
tags: [backstage, platform-engineering, internal-developer-platform, software-catalog, idp, developer-portal, cncf, techdocs, scaffolder]
search_keywords: [backstage, backstage.io, internal developer platform, IDP, developer portal, software catalog, service catalog, TechDocs, scaffolder, golden path, template, plugin backstage, backstage kubernetes plugin, backstage github plugin, backstage argocd plugin, CNCF backstage, spotify backstage, developer experience, DevEx, DX, developer productivity, self-service infrastructure, platform engineering, paved road, golden path templates, component catalog, api catalog, resource catalog, entity descriptor, kind Component, kind API, kind System, kind Domain, kind Resource, backstage RBAC, backstage auth, backstage postgres, backstage helm chart, app-config.yaml]
parent: ci-cd/platform-engineering/_index
related: [ci-cd/gitops/argocd, ci-cd/github-actions/workflow-avanzati, containers/kubernetes/_index]
official_docs: https://backstage.io/docs
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# Backstage

## Panoramica

Backstage è una piattaforma open-source per la costruzione di **Internal Developer Portals (IDP)** — portali centralizzati che unificano strumenti, documentazione, infrastruttura e catalogo dei servizi in un'unica interfaccia per i team di sviluppo. Creato da Spotify nel 2016 e donato alla CNCF nel 2020 (progetto Incubating dal 2022, Graduated dal 2024), Backstage risolve il problema della complessità che cresce linearmente con il numero di microservizi: in un ecosistema con 100+ servizi, i developer perdono tempo a cercare chi possiede cosa, dove si trova la documentazione, come si fa il deploy, quali API esistono.

Il cuore di Backstage è il **Software Catalog** — un registro centralizzato di tutti i componenti software, API, risorse infrastrutturali e team, navigabile via UI e interrogabile via API. Attorno al catalog si integrano: **TechDocs** (documentazione-as-code pubblicata automaticamente), **Scaffolder** (template per creare nuovi servizi seguendo le best practice aziendali), e un ecosistema di **Plugin** (1000+ nella community) che portano visibilità su Kubernetes, CI/CD, Alerting, Cloud costs e molto altro — tutto in un'unica finestra.

Backstage è indicato per team con **10+ microservizi** che vogliono migliorare la developer experience, standardizzare i processi e ridurre il cognitive overhead. Non è adatto per applicazioni monolitiche semplici o team piccoli (< 5 persone) dove l'overhead di gestione supera il beneficio.

## Concetti Chiave

!!! note "Terminologia Core"
    - **IDP (Internal Developer Platform):** piattaforma interna che astrae l'infrastruttura e offre self-service ai developer.
    - **Software Catalog:** il registro centrale di tutte le entità (componenti, API, team, risorse).
    - **Entity:** qualsiasi oggetto nel catalog (Component, API, System, Domain, Resource, Group, User).
    - **Descriptor file (`catalog-info.yaml`):** file YAML nella repo che registra un'entità nel catalog.
    - **Plugin:** estensione che aggiunge funzionalità a Backstage (frontend e/o backend).
    - **Scaffolder Template:** template Golden Path per creare nuovi servizi con configurazione pre-approvata.
    - **TechDocs:** sistema di documentazione-as-code (MkDocs-based) che pubblica docs direttamente nel portale.

### Il Software Catalog

Il catalog è organizzato in una gerarchia di entità che rispecchia la struttura organizzativa e tecnica:

```
Domain (Business Area)
  └── System (insieme di componenti correlati)
        ├── Component (microservizio, libreria, website, pipeline)
        │     └── API (esposta dal component)
        └── Resource (database, storage bucket, message queue)
```

Ogni entità è descritta da un file `catalog-info.yaml` nel repository sorgente:

```yaml
# catalog-info.yaml — Component (microservizio)
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payment-service
  description: "Gestisce transazioni e pagamenti"
  annotations:
    github.com/project-slug: myorg/payment-service
    backstage.io/techdocs-ref: dir:.
    argocd/app-name: payment-service-prod
    pagerduty.com/service-id: P1234XY
  tags:
    - java
    - payments
    - critical
  links:
    - url: https://grafana.internal/d/payment-dashboard
      title: Dashboard Grafana
      icon: dashboard
spec:
  type: service
  lifecycle: production
  owner: group:platform-team/payments
  system: payments-platform
  dependsOn:
    - component:postgres-payments
    - resource:payments-queue
  providesApis:
    - payment-api-v2
```

```yaml
# catalog-info.yaml — API OpenAPI
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: payment-api-v2
  description: "REST API per operazioni di pagamento"
  annotations:
    backstage.io/techdocs-ref: dir:.
spec:
  type: openapi
  lifecycle: production
  owner: group:platform-team/payments
  definition:
    $text: ./openapi.yaml   # File OpenAPI locale
```

### Tipi di Component

| `spec.type` | Descrizione | Esempio |
|-------------|-------------|---------|
| `service` | Backend API o microservizio | payment-service, auth-service |
| `website` | Frontend o SPA | customer-portal, admin-dashboard |
| `library` | Libreria condivisa | shared-utils, design-system |
| `pipeline` | Pipeline CI/CD | deploy-pipeline, data-pipeline |
| `documentation` | Documentazione standalone | architecture-docs, runbooks |

### Lifecycle

| `spec.lifecycle` | Significato |
|-----------------|-------------|
| `experimental` | In sviluppo, instabile |
| `production` | In produzione, stabile |
| `deprecated` | Da migrare, non usare per nuovi servizi |

## Architettura / Come Funziona

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKSTAGE                                    │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Software    │  │  Scaffolder  │  │       TechDocs           │  │
│  │  Catalog     │  │  (Templates) │  │  (Docs as Code)          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                       │                  │
│  ┌──────▼─────────────────▼───────────────────────▼──────────────┐  │
│  │                    Plugin Framework                             │  │
│  │  Kubernetes │ ArgoCD │ GitHub │ PagerDuty │ Datadog │ ...     │  │
│  └─────────────────────────────┬──────────────────────────────────┘  │
│                                │                                     │
│  ┌─────────────────────────────▼──────────────────────────────────┐  │
│  │                   Backstage Backend                             │  │
│  │  (Node.js / TypeScript — Express/Fastify)                       │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                               │                                      │
│  ┌────────────────────────────▼───────────────────────────────────┐  │
│  │                     PostgreSQL                                   │  │
│  │  (catalog entities, TechDocs metadata, scaffolder state)        │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
   Git Repositories     Kubernetes Clusters    Cloud Provider APIs
   (catalog-info.yaml)  (pod status, logs)     (AWS, GCP, Azure)
```

### Flusso di Ingestion del Catalog

1. **Discovery:** Backstage legge i repository (GitHub, GitLab, Bitbucket) alla ricerca di file `catalog-info.yaml`
2. **Ingestion:** Le entità trovate vengono processate e caricate nel database PostgreSQL
3. **Stitching:** Backstage risolve le relazioni tra entità (chi usa cosa, chi dipende da cosa)
4. **Rendering:** La UI mostra il catalog con relazioni, plugin data, documentazione

### Discovery automatica con GitHub Integration

```yaml
# app-config.yaml — discovery automatica di tutti i catalog-info.yaml nell'organizzazione
catalog:
  providers:
    github:
      myOrg:
        organization: 'myorg'
        catalogPath: '/catalog-info.yaml'        # path nel repo
        filters:
          branch: 'main'                          # solo branch main
          repository: '.*'                        # tutti i repo (regex)
        schedule:
          frequency: { minutes: 30 }
          timeout: { minutes: 3 }
```

## Configurazione & Pratica

### Installazione con Docker Compose (sviluppo locale)

```bash
# Crea un nuovo progetto Backstage
npx @backstage/create-app@latest --name my-backstage

# Entra nella directory
cd my-backstage

# Configura le variabili d'ambiente
cp .env.example .env
# Modifica .env con i tuoi valori

# Avvia in sviluppo locale
yarn dev
# → Frontend su http://localhost:3000
# → Backend su http://localhost:7007
```

### Installazione in Kubernetes con Helm

```bash
# Aggiunge il repo Helm ufficiale
helm repo add backstage https://backstage.github.io/charts
helm repo update

# Installa in namespace dedicato
helm install backstage backstage/backstage \
  --namespace backstage \
  --create-namespace \
  --version 1.9.0 \
  -f backstage-values.yaml
```

```yaml
# backstage-values.yaml — configurazione Helm produzione
backstage:
  image:
    repository: my-registry.io/my-backstage
    tag: "1.2.3"
    pullPolicy: IfNotPresent

  extraEnvVarsSecrets:
    - backstage-secrets    # Secret K8s con GITHUB_TOKEN, PG_PASSWORD, etc.

  appConfig:
    app:
      title: "MyCompany Developer Portal"
      baseUrl: https://backstage.mycompany.com

    backend:
      baseUrl: https://backstage.mycompany.com
      database:
        client: pg
        connection:
          host: ${POSTGRES_HOST}
          port: 5432
          user: ${POSTGRES_USER}
          password: ${POSTGRES_PASSWORD}
          database: backstage_plugin_catalog

    auth:
      environment: production
      providers:
        github:
          production:
            clientId: ${GITHUB_CLIENT_ID}
            clientSecret: ${GITHUB_CLIENT_SECRET}

postgresql:
  enabled: true
  auth:
    existingSecret: backstage-postgres-secret
    secretKeys:
      adminPasswordKey: postgres-password
      userPasswordKey: password

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: backstage.mycompany.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: backstage-tls
      hosts:
        - backstage.mycompany.com
```

### Configurazione GitHub Integration (app-config.yaml)

```yaml
# app-config.yaml — configurazione completa GitHub
integrations:
  github:
    - host: github.com
      token: ${GITHUB_TOKEN}     # Personal Access Token o GitHub App token

catalog:
  rules:
    - allow: [Component, API, Resource, Location, System, Domain, Group, User]

  providers:
    github:
      myOrg:
        organization: 'myorg'
        catalogPath: '/catalog-info.yaml'
        filters:
          branch: 'main'
        schedule:
          frequency: { minutes: 30 }
          timeout: { minutes: 3 }

  locations:
    # Aggiunge entità statiche (utile per team/utenti non auto-scopeabili)
    - type: file
      target: ../../examples/org.yaml
    - type: url
      target: https://github.com/myorg/platform-catalog/blob/main/all-components.yaml
```

### Scaffolder Template — Golden Path

I template Scaffolder guidano i developer nella creazione di nuovi servizi seguendo le best practice aziendali (struttura repo, Dockerfile standard, pipeline CI, registrazione nel catalog automatica):

```yaml
# template.yaml — Template Golden Path per microservizio Java
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: java-microservice
  title: "Java Microservice (Spring Boot)"
  description: "Template standard per nuovi microservizi Java con pipeline CI/CD e catalog registration"
  tags:
    - java
    - spring-boot
    - recommended
spec:
  owner: group:platform-team
  type: service

  parameters:
    - title: "Informazioni Servizio"
      required: [name, description, owner]
      properties:
        name:
          title: Nome Servizio
          type: string
          pattern: '^[a-z][a-z0-9-]*$'
          description: "Nome in kebab-case (es. payment-service)"
        description:
          title: Descrizione
          type: string
        owner:
          title: Owner
          type: string
          ui:field: OwnerPicker
          ui:options:
            catalogFilter:
              kind: Group

    - title: "Configurazione Repository"
      required: [repoUrl]
      properties:
        repoUrl:
          title: Repository GitHub
          type: string
          ui:field: RepoUrlPicker
          ui:options:
            allowedHosts:
              - github.com

  steps:
    - id: fetch-template
      name: Genera struttura progetto
      action: fetch:template
      input:
        url: ./skeleton     # Directory con i file template
        values:
          name: ${{ parameters.name }}
          description: ${{ parameters.description }}
          owner: ${{ parameters.owner }}

    - id: publish
      name: Pubblica su GitHub
      action: publish:github
      input:
        allowedHosts: ['github.com']
        description: ${{ parameters.description }}
        repoUrl: ${{ parameters.repoUrl }}
        defaultBranch: main
        repoVisibility: private

    - id: register
      name: Registra nel Catalog
      action: catalog:register
      input:
        repoContentsUrl: ${{ steps['publish'].output.repoContentsUrl }}
        catalogInfoPath: '/catalog-info.yaml'

  output:
    links:
      - title: Repository GitHub
        url: ${{ steps['publish'].output.remoteUrl }}
      - title: Apri nel Catalog
        entityRef: ${{ steps['register'].output.entityRef }}
```

### TechDocs — Documentazione as Code

TechDocs converte file Markdown (MkDocs) nel repo in documentazione pubblicata nel portale:

```yaml
# mkdocs.yml — nella root del repository del servizio
site_name: "Payment Service"
docs_dir: docs/
nav:
  - Home: index.md
  - Architecture: architecture.md
  - API Reference: api.md
  - Runbook: runbook.md
  - Changelog: changelog.md

plugins:
  - techdocs-core    # Plugin obbligatorio per TechDocs
```

```yaml
# catalog-info.yaml — abilita TechDocs per il component
metadata:
  annotations:
    backstage.io/techdocs-ref: dir:.    # cerca mkdocs.yml nella root del repo
```

```yaml
# app-config.yaml — configurazione TechDocs in produzione
techdocs:
  builder: 'external'   # La build avviene in CI, non in Backstage
  generator:
    runIn: 'local'
  publisher:
    type: 'awsS3'        # oppure 'googleGcs', 'azureBlobStorage'
    awsS3:
      bucketName: ${TECHDOCS_S3_BUCKET}
      region: eu-west-1
      credentials:
        roleArn: arn:aws:iam::123456789:role/BackstageTechDocs
```

```yaml
# .github/workflows/techdocs.yml — build e publish TechDocs in CI
name: Publish TechDocs
on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']

jobs:
  publish-techdocs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install TechDocs CLI
        run: pip install mkdocs-techdocs-core

      - name: Generate TechDocs
        run: techdocs-cli generate --no-docker

      - name: Publish TechDocs
        run: |
          techdocs-cli publish \
            --publisher-type awsS3 \
            --storage-name ${{ secrets.TECHDOCS_S3_BUCKET }} \
            --entity default/component/payment-service
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### Plugin Kubernetes — Visibilità Deployment

```yaml
# app-config.yaml — plugin Kubernetes
kubernetes:
  serviceLocatorMethod:
    type: 'multiTenant'
  clusterLocatorMethods:
    - type: 'config'
      clusters:
        - name: production
          url: https://k8s-api.mycompany.com
          authProvider: 'serviceAccount'
          serviceAccountToken: ${K8S_PROD_TOKEN}
          caData: ${K8S_PROD_CA}
          customResources:
            - group: 'argoproj.io'
              apiVersion: 'v1alpha1'
              plural: 'rollouts'
```

```yaml
# catalog-info.yaml — collega component ai deployment K8s
metadata:
  annotations:
    backstage.io/kubernetes-id: payment-service           # label sul Deployment K8s
    backstage.io/kubernetes-namespace: payments           # namespace K8s
    backstage.io/kubernetes-label-selector: 'app=payment-service'
```

## Best Practices

!!! tip "Golden Path — Standardizzazione via Template"
    Il valore principale di Backstage non è il catalog in sé, ma i **Golden Path Templates**: percorsi pre-approvati che creano automaticamente repo strutturate, pipeline CI/CD, Dockerfile standard, test boilerplate, e registrazione nel catalog. Investire in template di qualità riduce il tempo di onboarding di nuovi servizi da giorni a minuti.

!!! tip "Ownership Chiara"
    Ogni Component, API e Resource deve avere un `spec.owner` valorizzato con un Group o User. Componenti senza owner sono un segnale di debito tecnico. Usa lifecycle `deprecated` per servizi in dismissione invece di rimuoverli immediatamente — permette di tracciare le dipendenze.

!!! warning "Non registrare entità manualmente"
    Evita di aggiungere entità al catalog tramite file statici gestiti a mano. La scalabilità viene dalla **autodiscovery automatica** dei `catalog-info.yaml` nei repository. Se aggiungi un servizio manualmente, crea un `catalog-info.yaml` nel suo repository e lascia che Backstage lo scopra.

!!! warning "Database PostgreSQL obbligatorio in produzione"
    Il database SQLite in-memory (default per sviluppo) perde tutto il catalog al restart. In produzione usare sempre **PostgreSQL**. Il catalog viene rigenerato dall'autodiscovery, ma la TechDocs metadata, lo stato dello Scaffolder e i settings utente sono persistiti solo in PostgreSQL.

### Struttura catalog-info.yaml consigliata per ogni repo

```yaml
# catalog-info.yaml — best practice
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-service                    # Uguale al nome del repository
  description: "Descrizione precisa e aggiornata"
  annotations:
    # Tool di sviluppo
    github.com/project-slug: myorg/my-service
    # Documentazione
    backstage.io/techdocs-ref: dir:.
    # Osservabilità
    grafana/dashboard-selector: "title=My Service"
    pagerduty.com/service-id: P1234XY
    # Deployment
    argocd/app-name: my-service-prod
    # Kubernetes
    backstage.io/kubernetes-id: my-service
  tags:
    - python           # linguaggio
    - rest-api         # tipo
    - critical         # criticità (optional, per alerting)
spec:
  type: service
  lifecycle: production              # mai lasciare vuoto
  owner: group:my-team               # OBBLIGATORIO
  system: my-platform                # raggruppa servizi correlati
  dependsOn:                         # documenta le dipendenze esplicite
    - resource:my-postgres
    - component:other-service
```

### Plugin Essenziali per Partire

| Plugin | Package | Funzione |
|--------|---------|---------|
| `@backstage/plugin-kubernetes` | `@backstage/plugin-kubernetes` | Pod status, logs, rollouts per Component |
| `@roadiehq/backstage-plugin-argo-cd` | `@roadiehq/backstage-plugin-argo-cd` | Stato ArgoCD Application nel catalog |
| `@backstage/plugin-github-actions` | `@backstage/plugin-github-actions` | Stato workflow GitHub Actions |
| `@backstage/plugin-pagerduty` | `@pagerduty/backstage-plugin` | On-call, incidents attivi per Component |
| `@backstage/plugin-cost-insights` | `@backstage/plugin-cost-insights` | Cloud cost per team/servizio |
| `@roadiehq/backstage-plugin-datadog` | `@roadiehq/backstage-plugin-datadog` | Grafici Datadog embedded |
| `@backstage/plugin-sonarqube` | `@backstage/plugin-sonarqube` | Code quality metrics |

## Troubleshooting

### Entità non compaiono nel Catalog

**Sintomo:** Un servizio ha `catalog-info.yaml` nel repository ma non appare nel catalog.

**Cause possibili:**
1. Il file `catalog-info.yaml` ha errori di sintassi YAML
2. Il GitHub Token non ha i permessi per leggere il repository
3. Il discovery schedule non ha ancora processato il repo (attesa fino a 30 min)
4. Il repository è privato e il token non ha scope `repo`

```bash
# Diagnosi: controlla i log del backend Backstage
kubectl logs -n backstage deploy/backstage-backend -f | grep -E "(ERROR|WARN|catalog)"

# Forza il refresh immediato di un'entità specifica via API
curl -X POST \
  "https://backstage.mycompany.com/api/catalog/refresh" \
  -H "Authorization: Bearer $BACKSTAGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entityRef": "component:default/payment-service"}'

# Valida il catalog-info.yaml localmente
npx @backstage/cli catalog:validate catalog-info.yaml
```

### TechDocs non si aggiorna

**Sintomo:** La documentazione nel portale è obsoleta rispetto al repository.

**Causa:** La pipeline CI non ha pubblicato la nuova versione su S3/GCS, oppure Backstage non ha invalidato la cache.

```bash
# Verifica che l'ultima run della pipeline TechDocs sia passata
gh run list --workflow=techdocs.yml --repo myorg/payment-service

# Forza rigenerazione TechDocs per una specifica entità
techdocs-cli generate --no-docker
techdocs-cli publish \
  --publisher-type awsS3 \
  --storage-name my-techdocs-bucket \
  --entity default/component/payment-service

# Verifica che l'artefatto esista su S3
aws s3 ls s3://my-techdocs-bucket/default/component/payment-service/
```

### Scaffolder Template fallisce durante publish

**Sintomo:** Il template si blocca allo step `publish:github` con errore `Resource not accessible by integration`.

**Causa:** Il GitHub App o il Personal Access Token usato da Backstage non ha i permessi per creare repository nell'organizzazione.

```bash
# Verifica i permessi del token
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/orgs/myorg/repos \
  | jq '.[0].name'

# Se usa GitHub App, verifica che abbia:
# - Contents: Read & Write
# - Administration: Read & Write (per creare repo)
# - Metadata: Read
```

### Backstage è lento / PostgreSQL connection pool esaurita

**Sintomo:** La UI impiega 10+ secondi a caricare, i log mostrano `connection pool exhausted`.

**Causa:** Troppi plugin che aprono connessioni al DB, oppure PostgreSQL sottodimensionato.

```yaml
# app-config.yaml — aumenta il pool di connessioni
backend:
  database:
    client: pg
    connection:
      host: ${POSTGRES_HOST}
      port: 5432
      user: ${POSTGRES_USER}
      password: ${POSTGRES_PASSWORD}
    # Pool configuration
    pool:
      min: 2
      max: 20              # default è 10, aumenta se hai molti plugin
      acquireTimeoutMillis: 30000
      idleTimeoutMillis: 30000
```

```yaml
# Horizontal Pod Autoscaler per Backstage backend
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backstage-backend-hpa
  namespace: backstage
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backstage-backend
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Relazioni

??? info "ArgoCD — Integrazione Deployment"
    Il plugin `backstage-plugin-argo-cd` mostra lo stato di sync, health e history delle ArgoCD Application direttamente nella scheda del Component nel catalog. Richiede annotazione `argocd/app-name` nel `catalog-info.yaml`.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

??? info "GitHub Actions — Pipeline CI"
    Il plugin GitHub Actions mostra le run delle workflow CI/CD per ogni Component. Richiede annotazione `github.com/project-slug` nel `catalog-info.yaml` e un token GitHub con scope `workflow`.

    **Approfondimento completo →** [GitHub Actions Workflow Avanzati](../github-actions/workflow-avanzati.md)

??? info "Kubernetes — Visibilità Cluster"
    Il plugin Kubernetes di Backstage mostra pod, deployment, services e rollout direttamente nel portale. È uno dei plugin più usati: permette ai developer di vedere lo stato del loro servizio in produzione senza accesso diretto al cluster.

    **Approfondimento completo →** [Kubernetes](../../containers/kubernetes/_index.md)

## Riferimenti

- [Backstage.io — Documentazione Ufficiale](https://backstage.io/docs)
- [Backstage — Software Catalog Model](https://backstage.io/docs/features/software-catalog/descriptor-format)
- [Backstage — TechDocs](https://backstage.io/docs/features/techdocs/)
- [Backstage — Scaffolder](https://backstage.io/docs/features/software-templates/)
- [CNCF Backstage Project](https://www.cncf.io/projects/backstage/)
- [Backstage Plugin Marketplace](https://backstage.io/plugins)
- [Platform Engineering Maturity Model (CNCF)](https://tag-app-delivery.cncf.io/whitepapers/platform-eng-maturity-model/)
- [Spotify Engineering Blog — How Backstage Came to Be](https://engineering.atspotify.com/2020/04/how-we-use-backstage-at-spotify/)
