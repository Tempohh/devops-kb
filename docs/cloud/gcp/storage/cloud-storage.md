---
title: "Cloud Storage (GCS)"
slug: cloud-storage
category: cloud/gcp/storage
tags: [gcs, cloud-storage, gcp, object-storage, bucket, blob, storage-classes, lifecycle, versioning, terraform-backend]
search_keywords: [Cloud Storage, GCS, Google Cloud Storage, object storage GCP, bucket GCP, gs://, gsutil, gcloud storage, STANDARD storage class, Nearline, Coldline, Archive, storage class GCP, lifecycle policy GCS, object versioning GCS, uniform bucket-level access, bucket ACL, IAM GCS, storage.objectViewer, storage.objectCreator, storage.admin, Terraform state GCS, GCS backend Terraform, Workload Identity GCS, data lake GCP, BigQuery external table GCS, Cloud Functions trigger GCS, Cloud Logging export GCS, object lock GCS, CMEK GCS, Customer Managed Encryption Key, GCS presigned URL, signed URL GCS, blob storage, S3 equivalent GCP, S3 alternative Google, rsync GCS, parallel composite upload, retention policy GCS, soft delete GCS, multipart upload, GCS FUSE, gcsfuse, GCS JSON API, GCS XML API, GCS transfer service, Storage Transfer Service]
parent: cloud/gcp/storage/_index
related: [cloud/gcp/dati/bigquery, cloud/gcp/containers/gke, cloud/gcp/iam/iam-service-accounts, cloud/gcp/fondamentali/panoramica, iac/terraform/_index]
official_docs: https://cloud.google.com/storage/docs
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# Cloud Storage (GCS)

## Panoramica

**Cloud Storage (GCS)** è il servizio di **object storage unificato** di Google Cloud Platform. Progettato per durabilità del 99.999999999% (11 nove) e disponibilità globale, GCS è il layer di storage fondamentale su cui si appoggiano quasi tutti i workload GCP: Terraform state, log export, backup, data lake, dataset ML, artefatti CI/CD, e BigQuery load job.

Ogni risorsa GCS è un **oggetto** (file + metadati) memorizzato in un **bucket**. Gli oggetti non hanno gerarchia reale — il prefisso `logs/2026/03/` è un convenzione di naming, non una cartella. L'accesso avviene tramite URL `gs://nome-bucket/path/oggetto` (API native) o URL HTTPS (API JSON/XML e link pubblici).

**Quando usare Cloud Storage:**
- Archiviazione di file di qualsiasi dimensione senza schema (blob, log, immagini, video, archivi ZIP)
- Backend per Terraform state remoto su GCP
- Data lake: sorgente per BigQuery external tables o load job
- Distribuzione di artefatti (build output, container layer, release binaries)
- Backup e disaster recovery con lifecycle automatico verso classi più economiche
- Hosting di siti statici (HTML/CSS/JS senza server)

**Quando valutare alternative:**
- Dati strutturati con query SQL frequenti → **BigQuery** (non GCS)
- File system condiviso tra VM/pod → **Filestore** (NFS managed) o **GCS FUSE** (limitazioni di prestazioni)
- Database transazionale → Cloud SQL, Spanner, Firestore
- Cache ad alta frequenza → Memorystore (Redis/Valkey)

---

## Concetti Chiave

### Gerarchia delle Risorse

```
GCP Project
└── Bucket  (namespace globale — il nome è univoco in tutto GCP)
    ├── Object  (file + metadati + versioni)
    │   ├── Content-Type, Cache-Control, metadati custom
    │   └── Versioni precedenti (se versioning abilitato)
    └── IAM Policy  (uniform bucket-level access, raccomandato)
```

- **Bucket**: contiene gli oggetti. Il nome è globalmente univoco in GCP (come i domini DNS). Una volta creato il nome non è modificabile.
- **Oggetto**: fino a 5TB per singolo oggetto. Identificato da `bucket_name + object_name` (path completo incluso prefisso).
- **Location**: la posizione fisica del bucket — **regione singola** (`europe-west1`), **dual-region** (`EUR4` = Finlandia + Paesi Bassi), o **multi-region** (`EU`, `US`, `ASIA`). La location è **immutabile** dopo la creazione.

!!! warning "Il nome del bucket è globale e permanente"
    Un bucket denominato `my-company-backup` blocca quel nome per tutto GCP finché esiste. Scegliere nomi che includano il project ID o un prefisso aziendale per evitare collisioni e typosquatting: `my-project-id-terraform-state`, `acme-corp-logs-prod`.

### Consistenza

GCS offre **strong consistency** su tutte le operazioni (lettura dopo scrittura, lettura dopo delete, list dopo write). Non esiste la eventual consistency che caratterizzava S3 prima del 2020 — dopo un'operazione di PUT o DELETE, le letture successive e le `list` vedono immediatamente lo stato aggiornato.

### Naming Oggetti

- Lunghezza massima: 1024 byte (UTF-8)
- Non usare `..` come singolo componente del path
- I prefissi simulano le cartelle: `gs://bucket/a/b/file.txt` dove `a/b/` è un prefisso virtuale
- Gli oggetti il cui nome termina con `/` sono convenzionalmente usati come "directory marker"

---

## Storage Classes

Le storage class determinano il **costo di storage mensile** e il **costo di retrieval** (lettura dei dati). Non influenzano la durabilità (sempre 11 nove) né la latenza di accesso (sempre millisecondi).

| Classe | Costo storage | Retrieval fee | Min. retention | Use case tipico |
|--------|--------------|--------------|----------------|-----------------|
| **STANDARD** | ~$0.020/GB/mese (EU) | Nessuno | Nessuna | Dati ad accesso frequente, siti web, dataset attivi |
| **NEARLINE** | ~$0.010/GB/mese (EU) | $0.01/GB letto | 30 giorni | Backup mensili, log acceduti occasionalmente, archivi ricercabili |
| **COLDLINE** | ~$0.004/GB/mese (EU) | $0.02/GB letto | 90 giorni | Disaster recovery, dati acceduti < 1 volta ogni 3 mesi |
| **ARCHIVE** | ~$0.0012/GB/mese (EU) | $0.05/GB letto | 365 giorni | Conformità legale, archivi storici, dati MAI o quasi mai letti |

!!! tip "Autoclass: ottimizzazione automatica del costo"
    GCS offre la modalità **Autoclass** che sposta automaticamente ogni oggetto verso la storage class più economica in base alla frequenza di accesso reale. Un oggetto non letto per 30 giorni viene spostato in Nearline, poi Coldline dopo 90, poi Archive dopo 365. Ideale per bucket con pattern di accesso imprevedibili.

!!! warning "Minimum retention fee"
    Se elimini un oggetto Coldline prima dei 90 giorni, paghi comunque 90 giorni di storage. Per Archive, paghi comunque 365 giorni. Pianifica le lifecycle policy considerando queste soglie.

### Confronto con AWS S3

| Concetto GCS | Equivalente AWS S3 |
|---|---|
| Bucket GCS | Bucket S3 |
| Oggetto GCS | Oggetto S3 |
| `gs://bucket/key` | `s3://bucket/key` |
| `gcloud storage cp` | `aws s3 cp` |
| `gcloud storage rsync` | `aws s3 sync` |
| STANDARD class | S3 Standard |
| NEARLINE class | S3 Standard-IA |
| COLDLINE class | S3 Glacier Instant Retrieval |
| ARCHIVE class | S3 Glacier Deep Archive |
| Uniform bucket-level access | S3 Block Public Access + Bucket Policy |
| GCS Signed URL | S3 Presigned URL |
| Storage Transfer Service | AWS DataSync |

---

## Architettura / Come Funziona

GCS è costruito su **Colossus** (il file system distribuito interno di Google, successore di GFS) e **Spanner** per i metadati. L'architettura è completamente trasparente all'utente — non esistono concetti di "shard", "node" o "replica" da gestire.

```
Client (gsutil / SDK / HTTP)
    │
    ▼
GCS Frontend (load balancer globale — 200+ PoP Google)
    │
    ├── Metadata (Spanner — strong consistency, globale)
    │
    └── Data (Colossus — storage distribuito, regionale o multi-regionale)
              │
              └── Replica automatica (in-region: 3 copie; multi-region: 2+ regioni)
```

**Proprietà chiave dell'architettura:**
- **Upload di oggetti grandi**: GCS supporta **parallel composite upload** — un file viene diviso in chunk paralleli e ricomposto server-side. Questo riduce drasticamente il tempo di upload per file >100MB.
- **Download**: il protocollo HTTP range request permette di scaricare porzioni di un oggetto senza scaricare tutto il file.
- **Consistent hashing**: gli oggetti sono distribuiti in base al nome — evitare prefissi sequenziali (es. timestamp) per oggetti scritti ad alta frequenza perché concentrano il carico su pochi shard.

---

## Configurazione & Pratica

### Gestione Bucket con gcloud storage

```bash
# ── CREARE UN BUCKET ─────────────────────────────────────────
# Bucket standard nella regione EU con uniform bucket-level access (raccomandato)
gcloud storage buckets create gs://my-project-data \
  --location=europe-west1 \
  --default-storage-class=STANDARD \
  --uniform-bucket-level-access

# Bucket multi-region per alta disponibilità (più costoso)
gcloud storage buckets create gs://my-project-global-assets \
  --location=EU \
  --default-storage-class=STANDARD \
  --uniform-bucket-level-access

# Bucket con soft delete disabilitato (riduce costi per bucket con molti overwrite)
gcloud storage buckets create gs://my-project-tf-state \
  --location=europe-west1 \
  --uniform-bucket-level-access \
  --no-soft-delete

# ── LISTARE E ISPEZIONARE ────────────────────────────────────
# Listare tutti i bucket del progetto corrente
gcloud storage buckets list

# Mostrare dettagli di un bucket (location, storage class, IAM)
gcloud storage buckets describe gs://my-project-data

# Listare oggetti in un bucket (con dimensione e data)
gcloud storage ls -l gs://my-project-data/
gcloud storage ls -lr gs://my-project-data/logs/  # ricorsivo

# ── ELIMINARE ────────────────────────────────────────────────
# Eliminare un bucket vuoto
gcloud storage buckets delete gs://my-project-temp

# Eliminare tutti gli oggetti di un bucket (senza eliminare il bucket)
gcloud storage rm -r gs://my-project-temp/**
```

### Upload, Download e Copia

```bash
# ── UPLOAD ───────────────────────────────────────────────────
# Upload di un file singolo
gcloud storage cp ./data/report.csv gs://my-project-data/reports/2026/04/

# Upload con storage class diversa dalla default del bucket
gcloud storage cp ./archive/old-logs.tar.gz gs://my-project-data/archives/ \
  --storage-class=COLDLINE

# Upload di una directory intera (ricorsivo)
gcloud storage cp -r ./dist/ gs://my-project-assets/static/

# Upload parallelo e ottimizzato per file grandi (>100MB)
gcloud storage cp --parallel-composite-upload-threshold=100M \
  ./dataset/large-file.parquet gs://my-project-data/datasets/

# ── DOWNLOAD ─────────────────────────────────────────────────
# Download di un oggetto singolo
gcloud storage cp gs://my-project-data/reports/2026/04/report.csv ./local/

# Download ricorsivo di un prefisso
gcloud storage cp -r gs://my-project-data/logs/2026/ ./local-logs/

# ── SYNC (equivalente a rsync) ───────────────────────────────
# Sincronizza directory locale → GCS (carica solo file nuovi/modificati)
gcloud storage rsync -r ./local-dir/ gs://my-project-data/backup/

# Sync bidirezionale con delete (elimina da GCS file non presenti in locale)
gcloud storage rsync -r -d ./local-dir/ gs://my-project-data/sync/

# Sync escludendo pattern (es. file temporanei)
gcloud storage rsync -r \
  --exclude=".*\.tmp$|.*\.log$" \
  ./local-dir/ gs://my-project-data/sync/

# ── OPERAZIONI SU OGGETTI ────────────────────────────────────
# Copiare un oggetto tra bucket (server-side, non transita dal client)
gcloud storage cp gs://source-bucket/file.txt gs://dest-bucket/file.txt

# Rinominare/spostare un oggetto
gcloud storage mv gs://my-bucket/old-name.txt gs://my-bucket/new-name.txt

# Eliminare un oggetto
gcloud storage rm gs://my-bucket/path/to/file.txt

# Eliminare tutti gli oggetti con un prefisso
gcloud storage rm gs://my-bucket/temp/**
```

### Lifecycle Policies

Le lifecycle policy automatizzano la transizione tra storage class o l'eliminazione degli oggetti in base a condizioni (età, storage class corrente, numero di versioni).

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 30,
          "matchesStorageClass": ["STANDARD"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "COLDLINE"
        },
        "condition": {
          "age": 90,
          "matchesStorageClass": ["NEARLINE"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "ARCHIVE"
        },
        "condition": {
          "age": 365,
          "matchesStorageClass": ["COLDLINE"]
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 2555
        }
      }
    ]
  }
}
```

```bash
# Applicare la lifecycle policy a un bucket
gcloud storage buckets update gs://my-project-data \
  --lifecycle-file=lifecycle.json

# Visualizzare la lifecycle attuale
gcloud storage buckets describe gs://my-project-data \
  --format="json(lifecycle)"

# Rimuovere tutte le lifecycle policy
gcloud storage buckets update gs://my-project-data \
  --clear-lifecycle
```

### Versioning

Il versioning mantiene versioni precedenti degli oggetti quando vengono sovrascritti o eliminati. Utile per protezione da cancellazioni accidentali e rollback.

```bash
# Abilitare il versioning su un bucket
gcloud storage buckets update gs://my-project-data \
  --versioning

# Verificare stato versioning
gcloud storage buckets describe gs://my-project-data \
  --format="value(versioning)"

# Listare tutte le versioni di un oggetto
gcloud storage ls -a gs://my-project-data/config.yaml

# Recuperare una versione specifica (con generation number)
gcloud storage cp \
  "gs://my-project-data/config.yaml#1711929600000000" \
  ./config-backup.yaml

# Eliminare una versione specifica (non la live)
gcloud storage rm \
  "gs://my-project-data/config.yaml#1711929600000000"

# Eliminare tutte le versioni non correnti (pulizia)
gcloud storage rm -a gs://my-project-data/old-logs/**
```

!!! warning "Versioning e costi"
    Il versioning accumula tutte le versioni precedenti degli oggetti, ognuna fatturata per la propria storage class e dimensione. In bucket con upload frequenti (log, build artifact) il costo può moltiplicarsi rapidamente. Aggiungere sempre una lifecycle rule che elimini le versioni non correnti dopo N giorni: `"condition": {"numNewerVersions": 3}` mantiene solo le ultime 3 versioni.

### IAM e Controllo Accessi

GCS supporta due modelli di controllo accessi, **mutuamente esclusivi** a livello di bucket:

```bash
# ── UNIFORM BUCKET-LEVEL ACCESS (raccomandato) ───────────────
# Tutto il controllo accessi è gestito da IAM a livello di bucket.
# Nessun ACL legacy per singolo oggetto.

# Abilitare uniform access su un bucket esistente
gcloud storage buckets update gs://my-project-data \
  --uniform-bucket-level-access

# Assegnare ruolo di lettura a un service account
gcloud storage buckets add-iam-policy-binding gs://my-project-data \
  --member="serviceAccount:my-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Assegnare ruolo di scrittura (upload senza delete)
gcloud storage buckets add-iam-policy-binding gs://my-project-data \
  --member="serviceAccount:app-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"

# Assegnare accesso admin a un bucket
gcloud storage buckets add-iam-policy-binding gs://my-project-data \
  --member="group:devops-team@example.com" \
  --role="roles/storage.admin"

# Rendere un bucket pubblicamente leggibile (hosting statico)
gcloud storage buckets add-iam-policy-binding gs://my-public-site \
  --member="allUsers" \
  --role="roles/storage.objectViewer"

# Verificare la IAM policy corrente
gcloud storage buckets get-iam-policy gs://my-project-data
```

**Ruoli principali GCS:**

| Ruolo | Permessi | Use case |
|-------|----------|----------|
| `roles/storage.objectViewer` | Listare e leggere oggetti | Pipeline di lettura, ML training |
| `roles/storage.objectCreator` | Upload oggetti (no delete, no list) | Applicazione che produce file |
| `roles/storage.objectUser` | Legge, scrive, ed elimina oggetti | Applicazione che gestisce i propri file |
| `roles/storage.legacyBucketReader` | Listare oggetti del bucket | Necessario spesso insieme a objectViewer |
| `roles/storage.admin` | Accesso completo: bucket + oggetti + IAM | Amministrazione infrastruttura |

### Terraform State Backend su GCS

GCS è il backend raccomandato per lo state Terraform su GCP. Offre locking nativo via Cloud Storage object locking o metadata:

```hcl
# backend.tf
terraform {
  backend "gcs" {
    bucket = "my-project-tf-state"
    prefix = "terraform/state"
    # La location del bucket è già fissata alla creazione
    # Non serve specificarla qui
  }
}
```

```bash
# Setup iniziale: creare il bucket per lo state
gcloud storage buckets create gs://my-project-tf-state \
  --location=europe-west1 \
  --uniform-bucket-level-access \
  --versioning  # versioning obbligatorio per poter recuperare stati precedenti

# Inizializzare Terraform con il backend GCS
terraform init

# Se si migra da un backend locale a GCS
terraform init -migrate-state
```

```hcl
# Separazione degli state per environment (best practice)
# env/prod/backend.hcl
bucket = "my-project-tf-state"
prefix = "env/prod/terraform.tfstate"

# env/staging/backend.hcl
bucket = "my-project-tf-state"
prefix = "env/staging/terraform.tfstate"
```

```bash
# Usare backend config separato per environment
terraform -chdir=infra/ init -backend-config=env/prod/backend.hcl
```

### Accesso da Kubernetes con Workload Identity

Il metodo raccomandato per accedere a GCS da un pod GKE è **Workload Identity** — elimina la necessità di distribuire service account key file come Secret Kubernetes.

```bash
# 1. Abilitare Workload Identity sul cluster GKE (se non già abilitato)
gcloud container clusters update my-cluster \
  --workload-pool=my-project.svc.id.goog \
  --region=europe-west1

# 2. Creare un GCP Service Account dedicato
gcloud iam service-accounts create gcs-reader-sa \
  --display-name="GCS Reader Service Account"

# 3. Concedere al GSA i permessi GCS necessari
gcloud storage buckets add-iam-policy-binding gs://my-project-data \
  --member="serviceAccount:gcs-reader-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# 4. Creare il Kubernetes Service Account (nel namespace dell'applicazione)
kubectl create serviceaccount gcs-reader-ksa \
  --namespace=my-app-namespace

# 5. Binding tra KSA e GSA (la chiave di Workload Identity)
gcloud iam service-accounts add-iam-policy-binding \
  gcs-reader-sa@my-project.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:my-project.svc.id.goog[my-app-namespace/gcs-reader-ksa]"

# 6. Annotare il KSA con il GSA
kubectl annotate serviceaccount gcs-reader-ksa \
  --namespace=my-app-namespace \
  iam.gke.io/gcp-service-account=gcs-reader-sa@my-project.iam.gserviceaccount.com
```

```yaml
# deployment.yaml — usare il KSA annotato nel pod
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-app-namespace
spec:
  template:
    spec:
      serviceAccountName: gcs-reader-ksa  # KSA annotato
      containers:
        - name: app
          image: my-app:latest
          # L'applicazione usa Application Default Credentials automaticamente.
          # Nessuna variabile d'ambiente GOOGLE_APPLICATION_CREDENTIALS necessaria.
          env:
            - name: GCS_BUCKET
              value: "my-project-data"
```

---

## Best Practices

!!! tip "Usare sempre uniform bucket-level access"
    Il controllo accessi legacy per singolo oggetto (ACL) è difficile da auditare e gestire. Abilitare `uniform-bucket-level-access` su tutti i bucket nuovi e disabilitarlo è possibile solo entro 90 giorni dalla creazione. Con uniform access, IAM è l'unico sistema di controllo — più semplice, auditabile e sicuro.

!!! tip "Struttura dei prefissi per performance"
    GCS distribuisce gli oggetti per hash del nome. Prefissi altamente sequenziali (es. `logs/2026-04-04T10:00:00Z-`, `logs/2026-04-04T10:00:01Z-`) concentrano il traffico su pochi shard. Per upload ad alta frequenza (>1000/sec), aggiungere un hash random come prefisso: `logs/a3f2/2026-04-04T10:00:00Z-event.json` distribuisce il carico.

!!! warning "Non usare GCS come database"
    GCS non supporta aggiornamenti parziali agli oggetti — ogni modifica richiede il re-upload completo dell'oggetto. Non usare GCS per file che vengono aggiornati frequentemente a livello di riga o record. Per questo caso usare Firestore, Cloud SQL, o Bigtable.

### Sicurezza

```bash
# Prevenire accesso pubblico accidentale a livello di organizzazione
# (impostare come org policy per tutti i bucket)
gcloud resource-manager org-policies set-policy \
  --organization=ORGANIZATION_ID \
  storage-iam-constraint.yaml
# Dove storage-iam-constraint.yaml contiene:
# constraint: constraints/iam.allowedPolicyMemberDomains
# listPolicy:
#   allowedValues: [is:example.com]

# Abilitare audit logging per le operazioni GCS
gcloud projects get-iam-policy my-project --format=json | \
  python3 -c "import json,sys; p=json.load(sys.stdin); ..." # → poi aggiungere auditConfigs

# Verificare che nessun bucket sia pubblico nel progetto
gcloud storage buckets list --format="csv(name,iamConfiguration.publicAccessPrevention)"
```

```bash
# Generare una Signed URL per accesso temporaneo a un oggetto privato
# (senza dover rendere il bucket pubblico)
gcloud storage sign-url gs://my-project-data/private-report.pdf \
  --duration=1h \
  --private-key-file=signing-key.json
# Output: URL HTTPS con firma valida per 1 ora, accessibile senza autenticazione GCP
```

### Ottimizzazione Costi

```bash
# Abilitare Autoclass su un bucket (ottimizzazione automatica storage class)
gcloud storage buckets update gs://my-project-logs \
  --enable-autoclass

# Simulare il risparmio con lifecycle policy (stima manuale)
# Calcola: dimensione_dati_GB × (costo_STANDARD - costo_NEARLINE) × mesi
# €0.020/GB - €0.010/GB = €0.010/GB/mese di risparmio dopo 30 giorni

# Monitorare la distribuzione per storage class
gcloud storage buckets describe gs://my-project-data \
  --format="json(storageLayout)"
```

---

## Troubleshooting

**Problema: `403 Forbidden` — accesso negato a un oggetto o bucket**
```bash
# Causa 1: il service account non ha i permessi corretti
# Diagnostica: verificare l'identità usata e i permessi del bucket
gcloud auth list                      # identità attiva in locale
gcloud storage buckets get-iam-policy gs://my-bucket  # policy IAM

# Causa 2: uniform bucket-level access abilitato ma l'app usa ACL per oggetto
# Diagnostica: tentare l'accesso con le API IAM invece degli ACL
# Soluzione: assegnare il ruolo IAM corretto al service account:
gcloud storage buckets add-iam-policy-binding gs://my-bucket \
  --member="serviceAccount:my-sa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Causa 3: il bucket appartiene a un progetto diverso da quello configurato
gcloud config get project  # verificare il progetto attivo
gcloud storage buckets describe gs://my-bucket --format="value(projectNumber)"
```

**Problema: upload lento per file grandi (>500MB)**
```bash
# Causa: upload seriale senza parallel composite upload
# Soluzione: abilitare il parallel composite upload con threshold
gcloud storage cp \
  --parallel-composite-upload-threshold=150M \
  ./large-dataset.parquet gs://my-bucket/datasets/

# Per dataset molto grandi (decine di GB), usare Storage Transfer Service
# che ottimizza il trasferimento server-side senza passare per il client

# Verificare la larghezza di banda disponibile
gcloud storage cp --help | grep parallel  # verificare flag disponibili
```

**Problema: costi GCS più alti del previsto**
```bash
# Causa 1: versioning abilitato senza lifecycle per le versioni non correnti
# Verificare se il versioning è attivo
gcloud storage buckets describe gs://my-bucket --format="value(versioning)"

# Soluzione: aggiungere lifecycle rule per eliminare versioni non correnti
cat > lifecycle-cleanup.json << 'EOF'
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {
        "numNewerVersions": 3,
        "isLive": false
      }
    }]
  }
}
EOF
gcloud storage buckets update gs://my-bucket --lifecycle-file=lifecycle-cleanup.json

# Causa 2: dati in STANDARD che potrebbero essere in NEARLINE o COLDLINE
# Soluzione: abilitare Autoclass o aggiungere lifecycle di transizione

# Causa 3: egress traffic verso Internet o verso altre regioni
# I dati letti da GCS verso Internet sono a pagamento (€0.08-0.12/GB)
# I trasferimenti tra regioni GCP sono anche a pagamento
# Soluzione: usare sempre VM/GKE nella stessa regione del bucket
```

**Problema: Terraform state locking fallisce su GCS backend**
```bash
# Causa: il bucket non ha il versioning abilitato (richiesto dal backend GCS Terraform)
gcloud storage buckets update gs://my-tf-state-bucket --versioning

# Causa: stato corrotto o lock non rilasciato dopo un crash
# Verificare se esiste un oggetto di lock nel bucket
gcloud storage ls gs://my-tf-state-bucket/terraform/state.tflock

# Forzare il rilascio del lock (solo se sicuro che nessun altro terraform è in esecuzione)
terraform force-unlock LOCK_ID

# Causa: service account Terraform non ha i permessi corretti
# Permessi minimi necessari per il backend GCS:
# - roles/storage.objectAdmin sul bucket tf-state
# oppure i ruoli singoli:
# - storage.objects.create, storage.objects.get, storage.objects.delete
```

**Problema: oggetti caricati su GCS non visibili in BigQuery external table**
```bash
# Causa 1: il pattern URI nella external table non corrisponde al path degli oggetti
# Verificare il pattern usato nella definizione della tabella
bq show --format=json my-project:dataset.external_table | grep uris

# Causa 2: il bucket è in una regione diversa dal dataset BigQuery
# GCS e BigQuery devono essere nella stessa regione (o entrambi multi-region EU/US)
gcloud storage buckets describe gs://my-bucket --format="value(location)"
bq show --format=json my-project:dataset | grep location

# Soluzione: copiare il bucket nella regione corretta con Storage Transfer Service
# oppure ricreare il dataset BigQuery nella stessa regione del bucket
```

---

## Integrazione con altri Servizi GCP

```
Cloud Storage (GCS)
│
├── Sorgente dati
│   ├── BigQuery  ──────► Load Job (batch gratuito) / External Table
│   ├── Dataflow  ──────► Input pipeline ETL
│   └── Vertex AI ──────► Dataset ML, model artifacts, training data
│
├── Destinazione dati
│   ├── Cloud Logging ──► Export sink: log a lungo termine a basso costo
│   ├── Cloud Monitoring ► Export metriche storiche
│   └── BigQuery  ──────► Export tabelle in Parquet/CSV
│
├── Trigger e automazione
│   ├── Cloud Functions ► Trigger su finalize (nuovo oggetto), delete, metadata
│   ├── Eventarc  ──────► Routing eventi GCS verso Cloud Run, Workflows
│   └── Pub/Sub   ──────► Notifiche GCS → topic Pub/Sub → subscriber
│
└── Infrastruttura
    ├── GKE  ────────────► Workload Identity per accesso sicuro senza key file
    ├── Terraform ───────► State backend remoto
    └── Cloud Build ─────► Artefatti build, cache layer Docker
```

### Cloud Functions trigger su nuovo oggetto

```python
# Cloud Function in Python triggerate da un nuovo file su GCS
# Deployment: gcloud functions deploy process-upload --trigger-bucket=my-bucket ...

import functions_framework
from google.cloud import storage

@functions_framework.cloud_event
def process_gcs_upload(cloud_event):
    data = cloud_event.data
    bucket_name = data["bucket"]
    object_name = data["name"]
    
    print(f"Nuovo oggetto: gs://{bucket_name}/{object_name}")
    
    # Elaborazione...
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    content = blob.download_as_bytes()
    # ...
```

---

## Relazioni

GCS è il layer di storage centrale dell'ecosistema GCP — quasi ogni servizio lo usa come sorgente, destinazione, o storage di stato.

??? info "BigQuery — Data warehouse su GCS"
    BigQuery può leggere dati direttamente da GCS senza import (external tables) o caricarli nativamente (load job gratuito). GCS funge da staging per pipeline dati batch e data lake.
    
    **Approfondimento →** [BigQuery](../dati/bigquery.md)

??? info "GKE — Accesso sicuro con Workload Identity"
    Workload Identity è il meccanismo raccomandato per far accedere i pod GKE a GCS senza service account key file. Collega un Kubernetes Service Account a un Google Service Account tramite annotazione.
    
    **Approfondimento →** [GKE](../containers/gke.md)

??? info "IAM e Service Account GCP"
    I permessi su GCS sono gestiti tramite IAM. Capire i ruoli predefiniti (`roles/storage.*`) e il principio del least privilege è fondamentale per una configurazione sicura.
    
    **Approfondimento →** [IAM e Service Account](../iam/iam-service-accounts.md)

??? info "Terraform — State Backend"
    GCS è il backend raccomandato per lo stato Terraform su GCP. Richiede un bucket con versioning abilitato e un service account con `roles/storage.objectAdmin` sul bucket.
    
    **Approfondimento →** [Terraform](../../../iac/terraform/_index.md)

---

## Riferimenti

- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Storage Classes](https://cloud.google.com/storage/docs/storage-classes)
- [IAM Roles for Cloud Storage](https://cloud.google.com/storage/docs/access-control/iam-roles)
- [Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)
- [Object Versioning](https://cloud.google.com/storage/docs/object-versioning)
- [Terraform GCS Backend](https://developer.hashicorp.com/terraform/language/backend/gcs)
- [Workload Identity Federation](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [gcloud storage Command Reference](https://cloud.google.com/sdk/gcloud/reference/storage)
- [Autoclass](https://cloud.google.com/storage/docs/autoclass)
- [Cloud Storage Pricing](https://cloud.google.com/storage/pricing)
