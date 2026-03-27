---
title: "Panoramica GCP"
slug: panoramica-gcp
category: cloud/gcp
tags: [gcp, google-cloud, projects, iam, billing, regions, zones, sdk, gcloud, organization]
search_keywords: [GCP panoramica, Google Cloud overview, progetto Google Cloud, GCP project, GCP organization, risorsa GCP, IAM GCP, ruoli GCP, billing account GCP, regioni GCP, zone GCP, Google Cloud SDK, gcloud CLI, Cloud Shell, resource hierarchy, cartella GCP, folder GCP, service account, principal GCP, Google Cloud Console, quota GCP, Google Cloud free tier, GCP pricing, compute engine, GKE, App Engine, Cloud Run, Cloud Functions, GCP vs AWS, GCP vs Azure]
parent: cloud/gcp/fondamentali/_index
related: [cloud/aws/fondamentali/global-infrastructure, cloud/azure/fondamentali/global-infrastructure, cloud/aws/fondamentali/billing-pricing]
official_docs: https://cloud.google.com/docs/overview
status: complete
difficulty: beginner
last_updated: 2026-03-25
---

# Panoramica GCP

## Panoramica

Google Cloud Platform (GCP) è il cloud provider di Google, lanciato nel 2008 con App Engine e oggi disponibile con oltre **300 prodotti** distribuiti su 40+ regioni globali. GCP si distingue dagli altri provider per la **qualità dell'infrastruttura di rete** (la stessa rete privata che alimenta Google Search, YouTube e Gmail), per l'eccellenza in **Big Data e Machine Learning**, e per aver creato Kubernetes internamente prima di donarlo a CNCF.

**Quando scegliere GCP:**
- Workload **Kubernetes-native** (GKE è il managed K8s di riferimento)
- Pipeline di **data analytics** e **ML** (BigQuery, Vertex AI)
- Applicazioni che beneficiano della **rete globale Google** (bassa latenza, alta disponibilità)
- Team che già usano **Google Workspace** (integrazione nativa)

**Quando valutare alternative:**
- Ecosistema enterprise già Microsoft → Azure
- Massima varietà di servizi managed → AWS
- Compliance normativa con requisiti specifici su provider → verificare caso per caso

---

## Gerarchia delle Risorse

GCP organizza le risorse in una **gerarchia a 4 livelli** obbligatoria. Comprenderla è fondamentale perché policy IAM e billing ereditano in cascata dall'alto verso il basso.

```
Organization  (es. "example.com")
│   └── corrisponde a un dominio Google Workspace o Cloud Identity
│
├── Folder  (es. "Produzione", "Sviluppo", "Team-A")
│   │   └── raggruppamento logico di progetti — opzionale ma consigliato
│   │
│   └── Folder annidata  (fino a 10 livelli)
│
└── Project  (es. "myapp-prod", "myapp-staging")
    │   └── unità fondamentale — ogni risorsa appartiene esattamente a 1 project
    │
    └── Resource  (VM, bucket, database, cluster K8s…)
```

**Organization:**
- Nodo radice — esiste se si usa Google Workspace o Cloud Identity
- Le policy applicate all'Organization si ereditano su tutto il sotto-albero
- Permette di gestire policy centrali, billing consolidato, audit

**Folder:**
- Raggruppamento opzionale di progetti (es. per business unit, ambiente, team)
- Può contenere altri folder o progetti
- Permette di applicare policy IAM a un gruppo di progetti senza toccarli uno a uno

**Project:**
- Unità base di isolamento in GCP — ogni risorsa appartiene a un unico project
- Ha un **Project ID** (globalmente univoco, immutabile), un **Project Name** (display name) e un **Project Number** (generato automaticamente)
- Contiene il proprio billing account, quota, API abilitate

```bash
# Creare un nuovo project
gcloud projects create my-project-id \
    --name="My Project" \
    --folder=FOLDER_ID

# Listare i project disponibili
gcloud projects list

# Impostare il project attivo nella sessione
gcloud config set project my-project-id

# Verificare il project corrente
gcloud config get-value project
```

!!! warning "Project ID è immutabile"
    Il **Project ID** non può essere cambiato dopo la creazione. Sceglierlo con cura: `company-environment-service` (es. `acme-prod-payments`). Il Project Name è modificabile ma non è univoco.

---

## Regioni e Zone

GCP distribuisce l'infrastruttura in **Regioni** (aree geografiche) suddivise in **Zone** (datacenter fisicamente separati).

```
Struttura geografica GCP

Geography (es. Europe)
└── Region  (es. europe-west8 = Milano)
    ├── Zone A  (europe-west8-a)
    ├── Zone B  (europe-west8-b)
    └── Zone C  (europe-west8-c)
```

**Regioni europee principali:**

| Regione | Sede | Zone |
|---------|------|------|
| `europe-west1` | Belgio | 4 |
| `europe-west2` | Londra | 3 |
| `europe-west3` | Francoforte | 3 |
| `europe-west4` | Olanda | 3 |
| `europe-west6` | Zurigo | 3 |
| `europe-west8` | Milano | 3 |
| `europe-west9` | Parigi | 3 |
| `europe-north1` | Finlandia | 3 |
| `europe-southwest1` | Madrid | 3 |

**Zone:**
- Unità di isolamento guasti all'interno di una regione
- Ogni zona ha alimentazione, raffreddamento e networking indipendenti
- Risorse **zonali**: VM (Compute Engine), Persistent Disk, GKE Node Pool
- Risorse **regionali**: Cloud SQL con HA, GKE cluster (control plane regionale)
- Risorse **globali**: Cloud Storage bucket, IAM, VPC network, immagini

```bash
# Listare le regioni disponibili
gcloud compute regions list

# Listare le zone di una regione
gcloud compute zones list --filter="region:europe-west8"

# Impostare regione e zona di default nella configurazione
gcloud config set compute/region europe-west8
gcloud config set compute/zone europe-west8-b

# Creare VM in zona specifica
gcloud compute instances create my-vm \
    --zone=europe-west8-b \
    --machine-type=e2-medium \
    --image-family=debian-12 \
    --image-project=debian-cloud
```

!!! tip "Scelta della zona"
    Per applicazioni ad alta disponibilità, distribuire le VM su **almeno 2 zone** della stessa regione. GKE con cluster regionale gestisce questo automaticamente.

---

## IAM — Identity & Access Management

IAM in GCP controlla **chi** (principal) può fare **cosa** (ruolo/permesso) su **quale risorsa**.

### Componenti IAM

```
Principal  ──ha──►  Role  ──composto da──►  Permissions
(chi)               (cosa)                   (azioni specifiche)

Esempio:
serviceAccount:deploy@myproject.iam.gserviceaccount.com
    ──ha──►  roles/storage.objectCreator
    ──composto da──►  storage.objects.create
```

**Tipi di Principal:**

| Principal | Descrizione |
|-----------|-------------|
| **Google Account** | Utente con account Google (andrea@gmail.com) |
| **Service Account** | Identità per applicazioni/VM, non per persone |
| **Google Group** | Gruppo di account Google — gestione semplificata |
| **Google Workspace Domain** | Tutti gli utenti di un dominio Workspace |
| **Cloud Identity Domain** | Come Workspace ma senza le app G Suite |
| `allUsers` | Chiunque (incluso non autenticato) — usare con estrema cautela |
| `allAuthenticatedUsers` | Qualsiasi account Google autenticato |

**Tipi di Ruolo:**

| Tipo | Descrizione | Esempi |
|------|-------------|--------|
| **Primitive** (legacy) | Owner, Editor, Viewer — troppo permissivi | Da evitare in produzione |
| **Predefined** | Ruoli granulari gestiti da Google | `roles/storage.objectViewer`, `roles/container.developer` |
| **Custom** | Ruoli creati dall'utente con permessi specifici | Solo permessi strettamente necessari |

```bash
# Listare i ruoli di un project
gcloud projects get-iam-policy my-project-id

# Assegnare un ruolo a un utente
gcloud projects add-iam-policy-binding my-project-id \
    --member="user:andrea@example.com" \
    --role="roles/compute.viewer"

# Assegnare un ruolo a un service account
gcloud projects add-iam-policy-binding my-project-id \
    --member="serviceAccount:deploy-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

# Rimuovere un binding
gcloud projects remove-iam-policy-binding my-project-id \
    --member="user:ex-employee@example.com" \
    --role="roles/editor"
```

### Service Account

I **Service Account** sono identità per applicazioni, VM e pipeline CI/CD — non per persone fisiche.

```bash
# Creare un service account
gcloud iam service-accounts create deploy-sa \
    --display-name="Deploy Service Account" \
    --description="Used by CI/CD pipeline for deployments"

# Creare una chiave JSON (usare solo quando necessario)
gcloud iam service-accounts keys create key.json \
    --iam-account=deploy-sa@my-project-id.iam.gserviceaccount.com

# Listare i service account del project
gcloud iam service-accounts list

# Assegnare un ruolo al service account a livello di risorsa specifica
gcloud storage buckets add-iam-policy-binding gs://my-bucket \
    --member="serviceAccount:deploy-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

!!! warning "Chiavi JSON dei Service Account"
    Le chiavi JSON sono credenziali a lungo termine — se compromesse danno accesso completo. Preferire **Workload Identity Federation** (per CI/CD esterni) o **service account impersonation** (per accesso temporaneo). Le VM su GCP non hanno bisogno di chiavi JSON: usare il metadata server con service account assegnato all'istanza.

!!! tip "Principio del Minimo Privilegio"
    Assegnare sempre i ruoli **predefined** più granulari, non ruoli primitivi (Editor/Owner). Assegnare i ruoli al livello più basso della gerarchia (risorsa > project > folder > organization).

### Ereditarietà Policy IAM

Le policy IAM si **accumulano** scendendo nella gerarchia — non si sovrascrivono:

```
Organization  →  policy: bob=Billing Admin
  └── Folder  →  policy: alice=Folder Admin
      └── Project  →  policy: charlie=Compute Admin
          └── Resource  →  policy: dave=Storage Object Viewer

Risultato per charlie sul project:
  charlie ha Compute Admin (dal project) + eventuali ruoli ereditati da folder e org
```

!!! warning "Non si può negare con IAM standard"
    IAM in GCP è additivo: si possono solo *aggiungere* permessi, non *negare* permessi già concessi a un livello superiore. Per restrizioni esplicite usare **Organization Policy** (es. bloccare creazione di risorse in certe regioni).

---

## Billing

### Struttura del Billing

```
Billing Account  (es. "Fatturazione Principale")
│   └── legato a un metodo di pagamento
│   └── può coprire più project
│
└── Project A  ──  tutte le spese del project → addebitate al billing account
└── Project B  ──  idem
└── Project C  ──  idem
```

**Billing Account:**
- Entità che raccoglie e paga le fatture
- Un billing account può coprire N progetti
- Un project ha esattamente 1 billing account attivo (o nessuno → servizi bloccati)
- In un'Organization: il **Billing Admin** a livello org gestisce i billing account

```bash
# Listare i billing account accessibili
gcloud billing accounts list

# Collegare un project a un billing account
gcloud billing projects link my-project-id \
    --billing-account=BILLING_ACCOUNT_ID

# Verificare il billing account di un project
gcloud billing projects describe my-project-id
```

### Modello di Pricing GCP

GCP applica un modello **pay-as-you-go** con diversi meccanismi di sconto:

| Meccanismo | Descrizione | Sconto |
|-----------|-------------|--------|
| **Sustained Use Discounts (SUD)** | Sconto automatico per VM usate >25% del mese | Fino a 30% |
| **Committed Use Discounts (CUD)** | Impegno 1 o 3 anni | Fino a 57% (1yr) / 70% (3yr) |
| **Preemptible / Spot VM** | VM interrompibili con breve preavviso | Fino a 91% |
| **Free Tier** | Risorse sempre gratuite entro limiti | f1-micro, 5GB Cloud Storage, ecc. |
| **Free Trial** | $300 crediti per 90 giorni ai nuovi account | — |

```bash
# Stimare i costi con il pricing calculator (via browser)
# https://cloud.google.com/products/calculator

# Esportare i dati di billing su BigQuery per analisi
# (configurare nella console Billing > Billing export)

# Vedere il riepilogo costi del project corrente via API
gcloud billing accounts get-spot-price-info --help
```

### Budget e Alert

```bash
# Creare un budget via CLI (richiede billing account ID)
gcloud billing budgets create \
    --billing-account=BILLING_ACCOUNT_ID \
    --display-name="Monthly Budget" \
    --budget-amount=100USD \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0
```

!!! tip "Free Tier GCP"
    GCP offre un **Always Free** tier con limiti mensili: 1 f1-micro VM (us-east1/us-west1/us-central1), 30GB HDD, 5GB Cloud Storage (us region), 1GB Cloud Functions invocations. Ideale per lab e sviluppo leggero.

---

## Google Cloud SDK

### Installazione

```bash
# macOS/Linux — via script ufficiale
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Windows — scaricare installer .exe da cloud.google.com/sdk
# oppure via Chocolatey:
choco install gcloudsdk

# Verificare l'installazione
gcloud version

# Aggiornare tutti i componenti
gcloud components update
```

### Autenticazione

```bash
# Login interattivo (apre browser)
gcloud auth login

# Login per Application Default Credentials (per SDK/librerie)
gcloud auth application-default login

# Login con service account da file chiave JSON
gcloud auth activate-service-account \
    --key-file=path/to/key.json

# Verificare l'account attivo
gcloud auth list

# Revocare le credenziali dell'account corrente
gcloud auth revoke
```

### Configurazioni (Profili)

Le **configurazioni** gcloud permettono di gestire più ambienti (dev/staging/prod, più account) senza ridefinire ogni volta project/region/zona.

```bash
# Creare una nuova configurazione
gcloud config configurations create prod-config

# Attivare una configurazione
gcloud config configurations activate prod-config

# Listare tutte le configurazioni
gcloud config configurations list

# Impostare parametri nella configurazione attiva
gcloud config set project my-prod-project
gcloud config set compute/region europe-west8
gcloud config set compute/zone europe-west8-b
gcloud config set account ops@example.com

# Vedere la configurazione attiva
gcloud config list
```

!!! tip "Configurazioni per ambienti multipli"
    Creare una configurazione per ogni ambiente: `gcloud config configurations create dev`, `gcloud config configurations create prod`. Switching: `gcloud config configurations activate dev`. Molto più sicuro che cambiare il project di default e rischiare di operare sull'ambiente sbagliato.

### Comandi Essenziali

```bash
# ── COMPUTE ENGINE ──────────────────────────────────────
# Listare le VM
gcloud compute instances list

# Avviare/fermare una VM
gcloud compute instances start my-vm --zone=europe-west8-b
gcloud compute instances stop my-vm --zone=europe-west8-b

# SSH in una VM (senza chiavi SSH manuali)
gcloud compute ssh my-vm --zone=europe-west8-b

# ── CONTAINER ENGINE (GKE) ──────────────────────────────
# Recuperare le credenziali per kubectl
gcloud container clusters get-credentials my-cluster \
    --region=europe-west8

# Listare i cluster
gcloud container clusters list

# ── CLOUD STORAGE ───────────────────────────────────────
# Copiare file su/da GCS
gcloud storage cp local-file.txt gs://my-bucket/
gcloud storage cp gs://my-bucket/remote-file.txt .

# Sincronizzare cartella locale con bucket
gcloud storage rsync ./local-dir gs://my-bucket/dir --recursive

# ── IAM ──────────────────────────────────────────────────
# Verificare i permessi del proprio account
gcloud projects get-iam-policy my-project-id \
    --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:user:me@example.com"
```

### Cloud Shell

**Cloud Shell** è un ambiente browser-based con `gcloud`, `kubectl`, `terraform`, `git` e altri tool preinstallati — disponibile gratuitamente dalla console GCP.

```bash
# Aprire Cloud Shell dalla console: click sull'icona terminale in alto a destra
# Oppure da CLI:
gcloud cloud-shell ssh

# Cloud Shell fornisce:
# - 5GB di storage persistente su /home
# - VM e2-micro effimera (ricreata a ogni sessione se non usata)
# - gcloud autenticato con l'account della console
# - 50h/settimana gratuite (poi tariffazione standard VM)
```

---

## Best Practices

!!! tip "Struttura dei Project"
    Usare project separati per ambienti (dev/staging/prod). I project forniscono isolamento di billing, network e IAM — molto più efficace dei namespace o dei tag.

!!! tip "Naming Convention"
    ```
    Project ID:  {company}-{env}-{service}    → acme-prod-api
    Service Account:  {service}-sa            → deploy-sa, backend-sa
    Bucket:  {company}-{env}-{purpose}        → acme-prod-backups
    ```

!!! warning "Evitare ruoli primitivi in produzione"
    `roles/editor` e `roles/owner` danno accesso a **tutti** i servizi del project. In produzione, usare sempre ruoli predefined granulari o custom role con solo i permessi necessari.

!!! warning "Non usare l'account personale per applicazioni"
    Le VM, le pipeline CI/CD e i container devono usare **Service Account** dedicati, non account Google personali. Un service account compromesso può essere revocato senza impattare l'accesso umano.

- **Abilitare le API esplicitamente**: ogni servizio GCP richiede che la sua API sia abilitata nel project (es. `container.googleapis.com` per GKE, `sqladmin.googleapis.com` per Cloud SQL)
- **Usare Workload Identity Federation** per CI/CD esterni (GitHub Actions, GitLab CI) — elimina la necessità di chiavi JSON dei service account
- **Labels sui project e risorse** per cost allocation: `environment=prod`, `team=backend`, `cost-center=123`

---

## Troubleshooting

**Problema: `gcloud` risponde "project not set"**
```bash
# Causa: configurazione gcloud senza project impostato
# Soluzione: impostare il project
gcloud config set project my-project-id

# Oppure passarlo esplicitamente in ogni comando
gcloud compute instances list --project=my-project-id
```

**Problema: "API not enabled" su un servizio**
```bash
# Causa: l'API del servizio non è abilitata nel project
# Soluzione: abilitarla
gcloud services enable container.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Listare le API abilitate
gcloud services list --enabled
```

**Problema: "Permission denied" su una risorsa**
```bash
# Causa: il principal non ha il ruolo necessario
# Diagnostica: verificare i permessi del proprio account
gcloud projects get-iam-policy my-project-id \
    --flatten="bindings[].members" \
    --filter="bindings.members:user:me@example.com" \
    --format="table(bindings.role)"

# Verificare quale permesso specifico manca
gcloud iam list-testable-permissions //cloudresourcemanager.googleapis.com/projects/my-project-id
```

**Problema: "Billing account not set" — project bloccato**
```bash
# Causa: project senza billing account attivo
# Verifica
gcloud billing projects describe my-project-id

# Soluzione: collegare un billing account
gcloud billing projects link my-project-id \
    --billing-account=BILLING_ACCOUNT_ID
```

**Problema: quota esaurita (RESOURCE_EXHAUSTED)**
```bash
# Causa: raggiunto il limite di quota per un servizio nella regione
# Verifica le quote
gcloud compute project-info describe --project=my-project-id

# Richiedere aumento quota: Console > IAM & Admin > Quotas
# oppure via API Support
```

---

## Relazioni

??? info "AWS — Confronto concetti equivalenti"
    I concetti GCP hanno equivalenti diretti in AWS.

    | GCP | AWS | Note |
    |-----|-----|------|
    | Project | Account AWS | Unità di isolamento principale |
    | Organization | AWS Organizations | Gerarchia multi-account |
    | Folder | Organizational Unit (OU) | Raggruppamento logico |
    | IAM Service Account | IAM Role (per EC2/Lambda) | Identità per applicazioni |
    | Compute Engine | EC2 | VM managed |
    | GKE | EKS | Kubernetes managed |
    | Cloud Storage | S3 | Object storage |
    | BigQuery | Redshift + Athena | Data warehouse |
    | Cloud Run | AWS Fargate | Container serverless |

    **Approfondimento →** [AWS Fondamentali](../../aws/fondamentali/_index.md)

??? info "Azure — Confronto concetti equivalenti"
    | GCP | Azure | Note |
    |-----|-------|------|
    | Project | Resource Group / Subscription | Azure ha 2 livelli distinti |
    | Organization | Management Group | Gerarchia top-level |
    | IAM Service Account | Managed Identity | Identità per workload |
    | GKE | AKS | Kubernetes managed |
    | Cloud Storage | Azure Blob Storage | Object storage |
    | BigQuery | Azure Synapse Analytics | Data warehouse |

    **Approfondimento →** [Azure Fondamentali](../../azure/fondamentali/_index.md)

---

## Riferimenti

- [Google Cloud Overview](https://cloud.google.com/docs/overview)
- [Resource Hierarchy](https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy)
- [IAM Overview](https://cloud.google.com/iam/docs/overview)
- [IAM Predefined Roles](https://cloud.google.com/iam/docs/understanding-roles)
- [Billing Overview](https://cloud.google.com/billing/docs/concepts)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)
- [GCP Regions and Zones](https://cloud.google.com/compute/docs/regions-zones)
- [GCP Pricing Calculator](https://cloud.google.com/products/calculator)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
