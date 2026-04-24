---
title: "GCP IAM e Service Account"
slug: iam-service-accounts
category: cloud/gcp/iam
tags: [gcp, iam, service-accounts, workload-identity, security, rbac, org-policy]
search_keywords: [GCP IAM, Google Cloud IAM, Identity Access Management, Service Account GCP, SA GCP, Workload Identity GKE, gcloud iam, gcloud projects add-iam-policy-binding, ruoli IAM GCP, roles IAM GCP, principio minimo privilegio GCP, least privilege GCP, IAM conditions, Deny policy GCP, Organization Policy GCP, org policy, constraints GCP, impersonation service account, gcloud impersonate, SA key JSON, keyless authentication GCP, Workload Identity Federation, WIF, KSA, GSA, binding IAM, policy IAM, member IAM, role binding, custom role GCP, predefined role GCP, primitive role GCP, Owner Editor Viewer, resource hierarchy GCP, Organization Folder Project Resource, IAM audit log, service account permissions, iam.serviceAccounts.actAs, iam.disableServiceAccountKeyCreation, compute.requireShieldedVm, asset inventory GCP, gcloud asset]
parent: cloud/gcp/iam/_index
related: [cloud/gcp/fondamentali/panoramica, cloud/gcp/containers/gke, security/network/zero-trust]
official_docs: https://cloud.google.com/iam/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-30
---

# GCP IAM e Service Account

## Panoramica

**IAM (Identity and Access Management)** è il sistema di controllo degli accessi di Google Cloud: definisce *chi* (identity) può fare *cosa* (role) su *quale risorsa* (resource). Ogni chiamata API a GCP passa attraverso IAM — non esiste accesso a una risorsa senza una policy IAM che lo autorizzi.

**Quando conoscere IAM a fondo:**
- Configurare l'accesso tra microservizi su GCP (Service Account + Workload Identity)
- Impostare ambienti multi-team con isolamento tra project/folder
- Rispondere a requisiti di compliance (audit, least privilege, no persistent credentials)
- Automatizzare con Terraform o pipeline CI/CD che devono agire su risorse GCP

**Cosa NON è IAM:**
- IAM non gestisce l'autenticazione degli utenti finali dell'applicazione (usa Firebase Auth, Identity Platform, o Auth0)
- IAM non è un firewall di rete — per il networking usa VPC Firewall Rules e Cloud Armor
- IAM non gestisce i secret applicativi — per le credenziali usa Secret Manager

---

## Concetti Chiave

### Gerarchia delle Risorse

GCP organizza le risorse in una gerarchia a 4 livelli. Le policy IAM si ereditano verso il basso: una policy assegnata a livello Organization si applica a tutti i Folder, Project, e Resource sottostanti.

```
Organization  (es. example.com)
├── Folder "Produzione"
│   ├── Project "prod-backend"    ← policy ereditate da Organization + Folder
│   │   ├── GCE Instance "api-vm"
│   │   ├── GCS Bucket "prod-data"
│   │   └── CloudSQL "prod-db"
│   └── Project "prod-frontend"
├── Folder "Sviluppo"
│   ├── Project "dev-backend"
│   └── Project "dev-frontend"
└── Project "shared-infra"        ← progetti direttamente sotto Organization
```

**Regola critica:** le policy IAM si **accumulano** — non si sovrascrivono. Se un utente ha `roles/editor` a livello Organization e nessun ruolo su `prod-backend`, eredita comunque `roles/editor` su quel project. Questo è il motivo per cui il principio del minimo privilegio si applica preferibilmente al livello più basso possibile.

### Identity (Chi)

Un **member** IAM può essere:

| Tipo | Formato | Uso |
|------|---------|-----|
| User account | `user:alice@example.com` | Persona fisica — autenticazione con Google Account |
| Group | `group:devops@example.com` | Gruppo Google Workspace — gestione centralizzata |
| Service Account | `serviceAccount:sa@project.iam.gserviceaccount.com` | Identità per applicazioni/servizi |
| Domain | `domain:example.com` | Tutti i Google Account del dominio |
| `allUsers` | `allUsers` | Chiunque, incluso non autenticato — **attenzione** |
| `allAuthenticatedUsers` | `allAuthenticatedUsers` | Qualsiasi Google Account autenticato — **attenzione** |
| Workload Identity | `principal://iam.googleapis.com/...` | Federazione da provider OIDC esterni |

### Role (Cosa)

I ruoli IAM sono collezioni di **permissions** (es. `storage.objects.get`, `compute.instances.start`).

**Tre famiglie di ruoli:**

```
Primitive roles (legacy — evitare in produzione)
├── roles/owner    → tutto + gestione IAM e billing
├── roles/editor   → lettura + scrittura su quasi tutto
└── roles/viewer   → lettura su quasi tutto

Predefined roles (consigliati)
├── roles/storage.objectViewer    → solo lettura GCS objects
├── roles/storage.objectCreator   → solo upload GCS objects
├── roles/cloudsql.client         → connessione a CloudSQL, senza admin
├── roles/container.developer     → deploy su GKE, no gestione cluster
└── ... (centinaia di ruoli granulari per ogni servizio)

Custom roles (quando i predefined non bastano)
└── Aggregazione manuale di permissions specifiche
    → usare solo se nessun predefined role soddisfa il principio di minimo privilegio
```

!!! warning "Evitare i Primitive Role in Produzione"
    `roles/editor` dà accesso in scrittura a quasi tutto il project — CloudSQL, GCS, Compute, Secrets. Se un'applicazione con `roles/editor` viene compromessa, l'intera infrastruttura del project è a rischio. Usare sempre ruoli predefiniti o custom al posto di `roles/editor` e `roles/owner`.

### Service Account vs User Account

| Caratteristica | User Account | Service Account |
|---|---|---|
| Rappresenta | Una persona fisica | Un'applicazione/servizio |
| Autenticazione | Google Account (password + 2FA) | Chiave privata RSA o token OIDC |
| Gestito da | Google Workspace / Google Account | Google Cloud IAM |
| Uso in pipeline CI/CD | Sconsigliato (credenziali personali) | Corretto — nessuna persona coinvolta |
| Impersonation | Non supportata | Supportata (`iam.serviceAccounts.actAs`) |
| Limite per project | N/A | 100 SA per project |

### Tipi di Service Account

```
Service Account GCP
├── User-managed SA
│   ├── Creati esplicitamente dall'utente: gcloud iam service-accounts create
│   ├── Email: sa-name@PROJECT_ID.iam.gserviceaccount.com
│   └── Uso: applicazioni custom, pipeline CI/CD, workload GKE
│
├── Google-managed SA
│   ├── Creati automaticamente quando si abilita un servizio GCP
│   ├── Email: PROJECT_NUMBER@cloudservices.gserviceaccount.com (Cloud APIs)
│   │         PROJECT_NUMBER-compute@developer.gserviceaccount.com (default Compute)
│   └── NON modificare i ruoli dei Google-managed SA — rischi di rompere il servizio
│
└── Default SA (caso speciale del Google-managed)
    ├── "Default Compute Engine SA" — creato automaticamente con roles/editor (!)
    ├── Tutte le VM e i Pod GKE lo usano se non si specifica diversamente
    └── ANTI-PATTERN: mai usarlo per applicazioni → usa SA dedicati
```

!!! warning "Default Compute SA con roles/editor"
    Il Default Compute Service Account (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`) viene creato automaticamente con `roles/editor` sul project. Qualsiasi VM o Pod GKE che lo usa può leggere/scrivere quasi tutte le risorse del project. Creare sempre SA dedicati con soli i permessi necessari.

---

## Architettura / Come Funziona

### Policy IAM — Struttura

Una policy IAM è una lista di **binding**: ogni binding associa un ruolo a una lista di member.

```json
{
  "bindings": [
    {
      "role": "roles/storage.objectViewer",
      "members": [
        "serviceAccount:my-app@my-project.iam.gserviceaccount.com",
        "group:data-team@example.com"
      ]
    },
    {
      "role": "roles/storage.objectCreator",
      "members": [
        "serviceAccount:uploader@my-project.iam.gserviceaccount.com"
      ],
      "condition": {
        "title": "Solo bucket prefix uploads/",
        "expression": "resource.name.startsWith('projects/_/buckets/my-bucket/objects/uploads/')"
      }
    }
  ],
  "etag": "BwX..."
}
```

### Flusso di Autorizzazione

```
Richiesta API → Cloud Endpoint
      │
      ▼
  Chi è il chiamante?  ──────────────────────────────────────────────
  (autenticazione)                                                    │
      │                                                               │
      ▼                                                               │
  Ha un token OAuth2/OIDC valido per questo scope?                   │
      │ sì                                                            │ no → 401 Unauthorized
      ▼                                                               │
  Esiste una IAM policy che concede la permission                     │
  richiesta a questa identity su questa risorsa                       │
  (incluse risorse parent nella gerarchia)?                           │
      │ sì                                                            │ no → 403 Permission Denied
      ▼                                                               │
  Esiste una Deny policy che nega questa permission?  ───────────────┘
      │ no                                                            │ sì → 403 (Deny)
      ▼
  Richiesta Autorizzata ✓
```

### Workload Identity — Architettura

**Workload Identity** è il meccanismo per permettere ai workload (Pod GKE, Cloud Run, Cloud Build, GitHub Actions) di ottenere credenziali GCP senza chiavi JSON.

```
Pod GKE
└── usa Kubernetes Service Account (KSA) "my-app-ksa"
    └── annotato → "iam.gke.io/gcp-service-account: my-app-sa@project.iam.gserviceaccount.com"

Flusso token:
1. Pod richiede token al metadata server GKE (http://metadata.google.internal/...)
2. GKE genera un token OIDC firmato per il KSA
3. Le librerie client GCP (ADC) scambiano il token OIDC con un access token IAM
4. Il token IAM è valido 1 ora, rotazione automatica
5. Con il token IAM il Pod chiama l'API GCP (GCS, CloudSQL, Pub/Sub...)

Non serve nessuna chiave JSON — zero secret da gestire
```

---

## Configurazione & Pratica

### Gestione Service Account

```bash
# ── CREARE UN SERVICE ACCOUNT ────────────────────────────────────────
gcloud iam service-accounts create my-app-sa \
    --display-name="My Application Service Account" \
    --description="SA per il backend dell'applicazione my-app" \
    --project=my-project-id

# Verificare la creazione
gcloud iam service-accounts list --project=my-project-id

# ── ASSEGNARE RUOLI A UN SA ───────────────────────────────────────────
# Ruolo su un project intero
gcloud projects add-iam-policy-binding my-project-id \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Ruolo su una risorsa specifica (GCS bucket)
gcloud storage buckets add-iam-policy-binding gs://my-bucket \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# Ruolo su un folder (gerarchia)
gcloud resource-manager folders add-iam-policy-binding FOLDER_ID \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/logging.viewer"

# ── RIMUOVERE UN RUOLO ────────────────────────────────────────────────
gcloud projects remove-iam-policy-binding my-project-id \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# ── VERIFICARE I PERMESSI DI UN SA ───────────────────────────────────
# Chi ha accesso al project (tutte le binding)
gcloud projects get-iam-policy my-project-id --format=json

# Filtrare solo le policy che riguardano il SA
gcloud projects get-iam-policy my-project-id \
    --flatten="bindings[].members" \
    --format="table(bindings.role, bindings.members)" \
    --filter="bindings.members:my-app-sa"

# Test esplicito: questo SA può fare questa azione?
gcloud iam list-testable-permissions \
    //cloudresourcemanager.googleapis.com/projects/my-project-id \
    --filter="name:storage"
```

### SA Keys vs Keyless Authentication

```bash
# ── SA KEYS (sconsigliato — solo quando keyless non è disponibile) ────
# Creare una chiave JSON per un SA
gcloud iam service-accounts keys create ./sa-key.json \
    --iam-account=my-app-sa@my-project-id.iam.gserviceaccount.com

# Usare la chiave (Application Default Credentials)
export GOOGLE_APPLICATION_CREDENTIALS="./sa-key.json"

# Listare le chiavi attive di un SA (per audit)
gcloud iam service-accounts keys list \
    --iam-account=my-app-sa@my-project-id.iam.gserviceaccount.com

# Revocare (eliminare) una chiave
gcloud iam service-accounts keys delete KEY_ID \
    --iam-account=my-app-sa@my-project-id.iam.gserviceaccount.com

# ── KEYLESS (preferito) ──────────────────────────────────────────────
# Per ambienti GCP (GKE, Cloud Run, Compute Engine, Cloud Build):
# Usare Workload Identity o il metadata server — nessun comando extra.
# Le librerie client GCP rilevano ADC automaticamente tramite il metadata server.

# Per CI/CD esterni (GitHub Actions, GitLab, Jenkins) — Workload Identity Federation:
# 1. Creare un WIF pool
gcloud iam workload-identity-pools create "github-pool" \
    --location="global" \
    --display-name="GitHub Actions Pool"

# 2. Creare un provider OIDC per GitHub
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --display-name="GitHub Actions Provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='my-org/my-repo'"

# 3. Permettere al workflow GitHub di impersonare il SA
gcloud iam service-accounts add-iam-policy-binding \
    deploy-sa@my-project-id.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/my-org/my-repo"
```

### Service Account Impersonation

L'**impersonation** permette di agire temporaneamente come un SA senza avere le sue chiavi. Richiede il permesso `roles/iam.serviceAccountTokenCreator` sul SA target.

```bash
# Impersonare un SA per un singolo comando
gcloud storage ls gs://my-bucket \
    --impersonate-service-account=my-app-sa@my-project-id.iam.gserviceaccount.com

# Impostare l'impersonation come default nella sessione gcloud
gcloud config set auth/impersonate_service_account \
    my-app-sa@my-project-id.iam.gserviceaccount.com

# Rimuovere l'impersonation dalla sessione
gcloud config unset auth/impersonate_service_account

# Generare manualmente un access token impersonato (per script custom)
gcloud auth print-access-token \
    --impersonate-service-account=my-app-sa@my-project-id.iam.gserviceaccount.com

# Concedere permesso di impersonation
gcloud iam service-accounts add-iam-policy-binding \
    target-sa@my-project-id.iam.gserviceaccount.com \
    --member="user:developer@example.com" \
    --role="roles/iam.serviceAccountTokenCreator"
```

!!! tip "Impersonation per Test in Locale"
    Usa l'impersonation per testare localmente il comportamento di un'applicazione con i permessi del SA di produzione, senza generare chiavi JSON. Il developer usa le proprie credenziali gcloud (`gcloud auth login`) e le swap temporaneamente con il SA dell'applicazione.

### Workload Identity su GKE — Setup Completo

```bash
# ── PREREQUISITI ─────────────────────────────────────────────────────
# 1. Abilitare Workload Identity sul cluster (flag --workload-pool alla creazione)
gcloud container clusters create my-cluster \
    --region=europe-west8 \
    --workload-pool=my-project-id.svc.id.goog \
    # ... altri parametri

# Su cluster esistente (richiede aggiornamento anche dei node pool)
gcloud container clusters update my-cluster \
    --workload-pool=my-project-id.svc.id.goog \
    --region=europe-west8

gcloud container node-pools update default-pool \
    --cluster=my-cluster \
    --workload-metadata=GKE_METADATA \
    --region=europe-west8

# ── SETUP SA E BINDING ────────────────────────────────────────────────
# 2. Creare il Google Service Account (GSA)
gcloud iam service-accounts create my-app-gsa \
    --display-name="my-app GSA for Workload Identity"

# 3. Assegnare i ruoli al GSA (solo quelli necessari all'applicazione)
gcloud projects add-iam-policy-binding my-project-id \
    --member="serviceAccount:my-app-gsa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding my-project-id \
    --member="serviceAccount:my-app-gsa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# 4. Creare il binding IAM che permette al KSA di impersonare il GSA
# Formato member: serviceAccount:PROJECT_ID.svc.id.goog[NAMESPACE/KSA_NAME]
gcloud iam service-accounts add-iam-policy-binding \
    my-app-gsa@my-project-id.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:my-project-id.svc.id.goog[production/my-app-ksa]"
```

```yaml
# 5. Creare il Kubernetes Service Account con l'annotazione WI
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-ksa
  namespace: production
  annotations:
    # Questa annotazione è il collegamento tra KSA e GSA
    iam.gke.io/gcp-service-account: my-app-gsa@my-project-id.iam.gserviceaccount.com

---
# 6. Deployment che usa il KSA annotato
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      # CRITICO: specificare il KSA con l'annotazione WI
      serviceAccountName: my-app-ksa
      containers:
      - name: app
        image: europe-west8-docker.pkg.dev/my-project-id/my-repo/my-app:latest
        # Le librerie client GCP (Python, Go, Java, Node...) rilevano automaticamente
        # le credenziali tramite Application Default Credentials (ADC)
        # Nessuna variabile d'ambiente aggiuntiva necessaria su GKE con WI
        env:
        - name: GOOGLE_CLOUD_PROJECT
          value: "my-project-id"
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"
```

```bash
# 7. Verificare che Workload Identity funzioni
# L'email deve essere quella del GSA, non il default SA
kubectl exec -it deploy/my-app -n production -- \
    curl -s -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
# Output atteso: my-app-gsa@my-project-id.iam.gserviceaccount.com
```

---

## Organization Policies

Le **Organization Policies** sono vincoli preventivi che si applicano all'intera gerarchia (Organization, Folder, Project) e impediscono configurazioni non conformi — indipendentemente dai permessi IAM. Mentre IAM controlla chi può fare cosa, le Org Policy controllano cosa si può configurare.

```bash
# ── VISUALIZZARE LE ORG POLICY ────────────────────────────────────────
# Listare tutti i vincoli disponibili
gcloud org-policies list-available-constraints \
    --organization=ORGANIZATION_ID | head -40

# Vedere le policy effettive su un project (incluse quelle ereditate)
gcloud org-policies describe constraints/iam.disableServiceAccountKeyCreation \
    --project=my-project-id

# ── APPLICARE UN VINCOLO (richiede roles/orgpolicy.policyAdmin) ───────
# Disabilitare la creazione di chiavi SA (forza keyless auth)
cat > /tmp/no-sa-keys-policy.yaml << 'EOF'
name: projects/my-project-id/policies/iam.disableServiceAccountKeyCreation
spec:
  rules:
  - enforce: true
EOF
gcloud org-policies set-policy /tmp/no-sa-keys-policy.yaml

# Richiedere Shielded VM per tutte le nuove istanze Compute Engine
gcloud org-policies set-policy - << 'EOF'
name: organizations/ORGANIZATION_ID/policies/compute.requireShieldedVm
spec:
  rules:
  - enforce: true
EOF

# Vietare risorse pubbliche (allUsers/allAuthenticatedUsers) su GCS
gcloud org-policies set-policy - << 'EOF'
name: organizations/ORGANIZATION_ID/policies/iam.allowedPolicyMemberDomains
spec:
  rules:
  - values:
      allowedValues:
      - "C0xxxxxxx"   # Customer ID del dominio Google Workspace
EOF
```

**Vincoli più usati in DevOps:**

| Constraint | Cosa impone | Quando usarlo |
|---|---|---|
| `iam.disableServiceAccountKeyCreation` | Vieta creazione chiavi JSON per SA | Ambienti con Workload Identity disponibile |
| `iam.disableServiceAccountCreation` | Vieta creazione di nuovi SA | Solo per project molto ristretti |
| `compute.requireShieldedVm` | Tutte le VM devono usare Shielded VM | Compliance, workload sensibili |
| `compute.vmExternalIpAccess` | Nessun IP pubblico sulle VM | VPC privato, accesso solo tramite VPN/IAP |
| `storage.publicAccessPrevention` | Nessun bucket GCS pubblicamente accessibile | Tutti gli ambienti di produzione |
| `gcp.resourceLocations` | Limita le regioni GCP utilizzabili | Compliance data residency (GDPR) |
| `iam.allowedPolicyMemberDomains` | Solo identity del dominio aziendale nelle policy | Vieta `allUsers`/`allAuthenticatedUsers` |

!!! tip "Custom Org Policy (GA dal 2024)"
    Da metà 2024 le **Custom Organization Policies** permettono di scrivere vincoli CEL personalizzati sulle proprietà delle risorse GCP (non solo vincoli booleani predefiniti). Esempio: imporre che tutti i bucket GCS abbiano retention lock abilitato, o che le VM abbiano un tag specifico.

```bash
# Esempio Custom Org Policy: tutti i bucket devono avere uniform bucket-level access
cat > /tmp/custom-policy.yaml << 'EOF'
name: organizations/ORGANIZATION_ID/customConstraints/custom.requireUniformBucketAccess
resourceTypes:
  - storage.googleapis.com/Bucket
methodTypes:
  - CREATE
  - UPDATE
condition: "resource.iamConfiguration.uniformBucketLevelAccess.enabled == true"
actionType: ALLOW
displayName: "Richiedi uniform bucket-level access"
description: "Tutti i bucket GCS devono avere uniform bucket-level access abilitato"
EOF
gcloud org-policies set-custom-constraint /tmp/custom-policy.yaml
```

---

## IAM Conditions

Le **IAM Conditions** aggiungono un livello di granularità alle policy IAM: un binding è valido solo se la condizione (espressa in CEL — Common Expression Language) è soddisfatta.

```bash
# ── ACCESSO TEMPORANEO CON DATE CONDITION ────────────────────────────
# Permetti al consulente di accedere solo fino al 30 aprile 2026
gcloud projects add-iam-policy-binding my-project-id \
    --member="user:consultant@external.com" \
    --role="roles/viewer" \
    --condition='expression=request.time < timestamp("2026-04-30T23:59:59Z"),title=Accesso temporaneo consulente,description=Scade il 30 aprile 2026'

# ── CONDITION SU RESOURCE ATTRIBUTE ──────────────────────────────────
# SA può scrivere solo nel prefisso "uploads/" del bucket
gcloud storage buckets add-iam-policy-binding gs://my-bucket \
    --member="serviceAccount:uploader@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator" \
    --condition='expression=resource.name.startsWith("projects/_/buckets/my-bucket/objects/uploads/"),title=Solo prefisso uploads'

# ── CONDITION SU RESOURCE TYPE ────────────────────────────────────────
# Ruolo solo su istanze con label environment=dev (non prod)
gcloud projects add-iam-policy-binding my-project-id \
    --member="user:developer@example.com" \
    --role="roles/compute.instanceAdmin.v1" \
    --condition='expression=resource.labels["environment"] == "dev",title=Solo istanze dev'
```

```yaml
# Esempio di policy IAM con condizione — formato JSON equivalente
# (utile in Terraform o quando si modifica la policy completa)
{
  "bindings": [
    {
      "role": "roles/storage.objectAdmin",
      "members": ["serviceAccount:batch-sa@my-project.iam.gserviceaccount.com"],
      "condition": {
        "title": "Solo durante finestra di manutenzione",
        "description": "Accesso batch solo sabato e domenica UTC",
        "expression": "request.time.getDayOfWeek('UTC') == 6 || request.time.getDayOfWeek('UTC') == 0"
      }
    }
  ]
}
```

**Attributi CEL più usati nelle condizioni IAM:**

| Attributo | Tipo | Esempio |
|---|---|---|
| `request.time` | timestamp | `request.time < timestamp("2026-06-01T00:00:00Z")` |
| `resource.name` | string | `resource.name.startsWith("projects/_/buckets/my-bucket/objects/restricted/")` |
| `resource.type` | string | `resource.type == "storage.googleapis.com/Bucket"` |
| `resource.labels` | map | `resource.labels["env"] == "prod"` |
| `request.auth.access_levels` | list | Per Access Context Manager (BeyondCorp) |

---

## Best Practices

!!! warning "Mai usare il Default Compute SA"
    Non assegnare mai il Default Compute SA (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`) alle applicazioni. Ha `roles/editor` per design storico. Creare sempre SA dedicati con il minimo dei permessi necessari.

!!! warning "Mai usare SA Keys se c'è Workload Identity"
    Le chiavi SA JSON sono credenziali long-lived: se trapelano (log, container image, repository), danno accesso illimitato fino a revoca manuale. Workload Identity usa token OIDC a breve scadenza (1h) con rotazione automatica — zero credenziali da gestire.

!!! tip "Applicare il Minimo Privilegio per Risorsa, non per Project"
    Quando possibile, assegna i ruoli al livello della risorsa specifica (es. `gs://bucket-name`) piuttosto che sull'intero project. Un SA che deve solo leggere un bucket non deve avere `roles/storage.objectViewer` su tutti i bucket del project.

**Checklist IAM per ambienti di produzione:**

- [ ] **Nessun SA con ruoli primitivi** (`roles/owner`, `roles/editor`) — usare solo predefined/custom
- [ ] **Workload Identity abilitato** su GKE — nessuna chiave JSON nel cluster
- [ ] **Org Policy** `iam.disableServiceAccountKeyCreation` attiva a livello Organization
- [ ] **Org Policy** `storage.publicAccessPrevention` attiva — nessun bucket pubblico
- [ ] **Ogni SA ha un solo scopo** — un SA per microservizio, non un SA condiviso
- [ ] **SA inutilizzati eliminati** — audit regolare con `gcloud asset search-all-iam-policies`
- [ ] **Audit log abilitati** (Data Access Logs per IAM) — traccia ogni accesso alle risorse
- [ ] **Group-based access** — assegnare ruoli a Google Groups, non a singoli utenti
- [ ] **Impersonation** per accessi privilegiati occasionali — nessun utente con ruoli permanenti alti
- [ ] **IAM Conditions** per accessi temporanei (consulenti, accessi di emergenza)

### Auditare SA Inutilizzati e Permessi in Eccesso

```bash
# Trovare tutti i SA nel project
gcloud iam service-accounts list --project=my-project-id

# Trovare SA con chiavi attive (da revocare se non necessarie)
for sa in $(gcloud iam service-accounts list --project=my-project-id --format="value(email)"); do
    echo "=== $sa ==="
    gcloud iam service-accounts keys list --iam-account="$sa" \
        --filter="keyType=USER_MANAGED" --format="table(name,validAfterTime,validBeforeTime)"
done

# Trovare tutte le policy IAM che referenziano un SA specifico (a livello Organization)
gcloud asset search-all-iam-policies \
    --scope="organizations/ORGANIZATION_ID" \
    --query="policy:my-app-sa@my-project-id.iam.gserviceaccount.com"

# Trovare risorse accessibili da un SA specifico
gcloud asset search-all-iam-policies \
    --scope="projects/my-project-id" \
    --query="policy.role.permissions:storage.objects.get"

# Verificare chi ha il permesso di impersonare un SA
gcloud iam service-accounts get-iam-policy \
    my-app-sa@my-project-id.iam.gserviceaccount.com
```

### Custom Roles — Quando e Come

```bash
# Creare un custom role da permissions specifiche
gcloud iam roles create MyAppRole \
    --project=my-project-id \
    --title="My App Custom Role" \
    --description="Permessi minimi per my-app: lettura GCS e connessione CloudSQL" \
    --permissions="storage.objects.get,storage.objects.list,cloudsql.instances.connect" \
    --stage=GA

# Aggiornare un custom role (aggiungere permission)
gcloud iam roles update MyAppRole \
    --project=my-project-id \
    --add-permissions="pubsub.subscriptions.consume"

# Listare i custom role del project
gcloud iam roles list --project=my-project-id --filter="name:projects/"

# Copiare un predefined role come base per un custom role
gcloud iam roles copy \
    --source="roles/storage.objectAdmin" \
    --destination="MyStorageRole" \
    --dest-project=my-project-id
```

---

## Troubleshooting

**Problema: `403 Permission Denied` — l'applicazione non riesce ad accedere a un servizio GCP**
```bash
# Causa 1: il SA non ha il ruolo corretto
# Diagnosi: verificare quale permission manca dall'errore
# Formato errore: "Permission 'storage.objects.get' denied on resource 'projects/_/buckets/my-bucket'"
# Soluzione:
gcloud projects add-iam-policy-binding my-project-id \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Causa 2: il SA usato non è quello atteso (sta usando il default SA)
# Diagnosi su GKE: verificare il SA del Pod
kubectl exec -it my-pod -- \
    curl -s -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"

# Causa 3: Org Policy che blocca (ha precedenza su IAM)
gcloud org-policies describe constraints/iam.disableServiceAccountKeyCreation \
    --project=my-project-id

# Causa 4: Deny policy che esplicita nega (nuova feature IAM)
gcloud iam policies list --attachment-point=cloudresourcemanager.googleapis.com/projects/my-project-id
```

**Problema: Workload Identity non funziona — Pod usa il default SA invece del GSA**
```bash
# Diagnosi 1: verificare l'annotazione sul KSA
kubectl describe serviceaccount my-app-ksa -n production
# Cercare la riga: iam.gke.io/gcp-service-account

# Diagnosi 2: il Deployment usa il KSA corretto?
kubectl get deploy my-app -n production -o jsonpath='{.spec.template.spec.serviceAccountName}'

# Diagnosi 3: verificare che il node pool abbia GKE_METADATA
gcloud container node-pools describe default-pool \
    --cluster=my-cluster --region=europe-west8 \
    --format="value(config.workloadMetadataConfig.mode)"
# Deve essere: GKE_METADATA (non EXPOSE_METADATA o GCE_METADATA)

# Diagnosi 4: verificare il binding IAM workloadIdentityUser sul GSA
gcloud iam service-accounts get-iam-policy \
    my-app-gsa@my-project-id.iam.gserviceaccount.com
# Cercare: serviceAccount:my-project-id.svc.id.goog[production/my-app-ksa]

# Diagnosi 5: il workload-pool è corretto?
gcloud container clusters describe my-cluster --region=europe-west8 \
    --format="value(workloadIdentityConfig.workloadPool)"
# Deve essere: my-project-id.svc.id.goog
```

**Problema: `iam.serviceAccounts.actAs` permission denied durante deploy**
```bash
# Causa: il SA del deployer (es. Cloud Build SA) non ha il permesso
# di "usare" il SA target del deployment
# Questo permesso è necessario quando un SA deve agire come un altro SA

# Esempio: Cloud Build SA non può deployare un Cloud Run service con my-app-sa
# Soluzione: concedere iam.serviceAccountUser al deployer SA
gcloud iam service-accounts add-iam-policy-binding \
    my-app-sa@my-project-id.iam.gserviceaccount.com \
    --member="serviceAccount:PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"
```

**Problema: Org Policy blocca la creazione di risorse in CI/CD**
```bash
# Diagnosticare quale Org Policy blocca
# L'errore include tipicamente il constraint name, es:
# "Constraint constraints/compute.requireShieldedVm violated"

# Visualizzare la policy effettiva sul project
gcloud org-policies describe constraints/compute.requireShieldedVm \
    --project=my-project-id

# Opzione 1: allineare la risorsa al vincolo (preferita)
# → aggiungere --shielded-secure-boot --shielded-vtpm alla creazione VM

# Opzione 2: override a livello project (richiede roles/orgpolicy.policyAdmin)
gcloud org-policies set-policy - << 'EOF'
name: projects/my-project-id/policies/compute.requireShieldedVm
spec:
  rules:
  - enforce: false
EOF
```

**Problema: SA creati ma inutilizzati accumulano chiavi — audit fallisce**
```bash
# Trovare SA con chiavi non usate da più di 90 giorni
# Usare Cloud Asset Inventory per export di massa
gcloud asset export \
    --project=my-project-id \
    --asset-types="iam.googleapis.com/ServiceAccountKey" \
    --output-path="gs://my-audit-bucket/iam-keys-$(date +%Y%m%d).json"

# Disabilitare un SA senza eliminarlo (reversibile)
gcloud iam service-accounts disable \
    unused-sa@my-project-id.iam.gserviceaccount.com

# Eliminare definitivamente un SA (irreversibile — attendere 30 giorni per undelete)
gcloud iam service-accounts delete \
    unused-sa@my-project-id.iam.gserviceaccount.com
```

---

## Relazioni

??? info "GKE — Workload Identity in Contesto"
    Il setup completo di Workload Identity su GKE (abilitazione cluster, metadata mode node pool, annotazione KSA) è descritto in dettaglio nella documentazione GKE. Questo file copre la parte IAM (GSA, binding, ruoli).

    **Approfondimento →** [Google Kubernetes Engine (GKE)](../containers/gke.md)

??? info "Zero Trust e Principio del Minimo Privilegio"
    IAM GCP è un'implementazione concreta dei principi Zero Trust: ogni richiesta è autenticata, autorizzata, e verificata indipendentemente dalla rete di origine. Le IAM Conditions e Deny Policies estendono ulteriormente il modello.

    **Approfondimento →** [Zero Trust](../../../security/network/zero-trust.md)

??? info "GCP — Panoramica e Fondamentali"
    La gerarchia Organization > Folder > Project, la console IAM, e i concetti di base (regioni, project ID, billing account) sono coperti nella panoramica GCP.

    **Approfondimento →** [Panoramica GCP](../fondamentali/panoramica.md)

---

## Riferimenti

- [IAM Documentation](https://cloud.google.com/iam/docs)
- [Service Accounts Overview](https://cloud.google.com/iam/docs/service-account-overview)
- [Workload Identity for GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [Workload Identity Federation (external IdP)](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Organization Policy Service](https://cloud.google.com/resource-manager/docs/organization-policy/overview)
- [Custom Organization Policies](https://cloud.google.com/resource-manager/docs/organization-policy/creating-managing-custom-constraints)
- [IAM Conditions](https://cloud.google.com/iam/docs/conditions-overview)
- [IAM Deny Policies](https://cloud.google.com/iam/docs/deny-overview)
- [Predefined Roles Reference](https://cloud.google.com/iam/docs/understanding-roles)
- [IAM Best Practices](https://cloud.google.com/iam/docs/using-iam-securely)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
- [Cloud Asset Inventory](https://cloud.google.com/asset-inventory/docs/overview)
