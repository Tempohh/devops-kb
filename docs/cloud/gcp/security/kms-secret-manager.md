---
title: "Cloud KMS e Secret Manager"
slug: kms-secret-manager
category: cloud/gcp/security
tags: [gcp, kms, secret-manager, encryption, cmek, envelope-encryption, key-management, hsm, iam]
search_keywords: [Cloud KMS, Google Cloud KMS, GCP Key Management Service, Secret Manager GCP, CMEK, customer managed encryption key, CSEK, customer supplied encryption key, Google managed key, envelope encryption GCP, Cloud HSM, key ring, crypto key, key version, cryptoKeyEncrypterDecrypter, rotazione chiavi GCP, key rotation GCP, Workload Identity Secret Manager, CSI driver secret manager, secret versioning GCP, replica secret, automatic replication, user managed replication, HashiCorp Vault GCP, PERMISSION_DENIED cryptoKey, secret manager Cloud Run, secret manager GKE, FIPS 140-2 GCP, asymmetric key GCP, symmetric encryption GCP]
parent: cloud/gcp/security/_index
related: [security/secret-management/vault, cloud/gcp/iam/iam-service-accounts, cloud/aws/security/kms-secrets, cloud/gcp/containers/gke]
official_docs: https://cloud.google.com/kms/docs
status: reviewed
difficulty: advanced
last_updated: 2026-10-02
last_verified: 2026-10-04
---

# Cloud KMS e Secret Manager

## Panoramica

**Cloud KMS** (Key Management Service) e **Secret Manager** sono i due servizi GCP per la protezione dei dati: KMS gestisce le chiavi crittografiche usate per cifrare dati a riposo e in transito, Secret Manager archivia e versiona credenziali applicative (password, API key, certificati). Si usano spesso insieme: Secret Manager cifra ogni secret con una chiave KMS (Google-managed di default, CMEK su richiesta).

**Quando servono:**
- Requisiti di compliance che impongono il controllo del ciclo di vita delle chiavi (rotazione, revoca, residenza geografica) → CMEK con Cloud KMS
- Credenziali applicative (connection string DB, token API terze parti) che non devono finire in variabili d'ambiente o ConfigMap in chiaro → Secret Manager
- Integrazione con workload Kubernetes/Cloud Run che devono leggere secret senza gestire chiavi JSON → Secret Manager + Workload Identity

**Quando NON servono:**
- Dati generici su GCS/BigQuery/Compute: sono già cifrati at-rest con chiavi Google-managed per default — non serve CMEK a meno di un requisito esplicito di controllo chiave
- Configurazione non sensibile (feature flag, URL pubblici): usare variabili d'ambiente o ConfigMap, Secret Manager ha un costo per versione e per accesso
- Secret dinamici con TTL e revoca automatica: Secret Manager non genera credenziali on-demand — per quello serve [HashiCorp Vault](../../../security/secret-management/vault.md), che GCP supporta come secrets engine esterno

---

## Concetti Chiave

### Cloud KMS — Gerarchia delle Chiavi

```
Project
└── Key Ring (contenitore logico, legato a una location)
    └── Crypto Key (identità logica della chiave, immutabile nel tempo)
        └── Key Version 1 (materiale crittografico effettivo)
        └── Key Version 2 (generata da rotazione — la precedente resta per decrypt)
        └── Key Version N (primary — usata per i nuovi encrypt)
```

- **Key Ring**: raggruppa Crypto Key nella stessa location (region o `global`). Non eliminabile, non rinominabile.
- **Crypto Key**: l'identità stabile referenziata dalle applicazioni (`projects/P/locations/L/keyRings/R/cryptoKeys/K`). Ha un algoritmo e uno scopo fissati alla creazione (encrypt/decrypt, sign/verify, MAC).
- **Key Version**: il materiale di chiave vero e proprio. La rotazione crea una nuova version e la promuove a *primary*; le version precedenti restano attive solo per decifrare dati già cifrati con esse.

!!! warning "Key Ring e Location sono permanenti"
    Un Key Ring non può essere eliminato né spostato di location dopo la creazione (resta per sempre, anche vuoto). Pianificare la struttura (es. un Key Ring per ambiente: `prod`, `staging`) prima di creare le prime chiavi.

### CMEK vs CSEK vs Google-Managed Key

| Modello | Chi genera la chiave | Chi la gestisce | Controllo cliente |
|---|---|---|---|
| **Google-managed** | Google | Google (rotazione automatica, trasparente) | Nessuno — default su tutti i servizi |
| **CMEK** (Customer-Managed Encryption Key) | Cliente, via Cloud KMS | Cliente (rotazione, IAM binding, revoca) | Alto — il cliente può disabilitare/distruggere la chiave e rendere i dati inaccessibili |
| **CSEK** (Customer-Supplied Encryption Key) | Cliente, fuori da GCP | Cliente (Google non la archivia mai) | Massimo — la chiave va fornita a ogni richiesta, Google non la persiste |

**Regola pratica:** Google-managed per la maggioranza dei workload (nessun costo, nessuna gestione). CMEK quando serve audit trail della chiave, rotazione controllata, o revoca d'emergenza (requisiti bancari/sanitari). CSEK solo per casi estremi — legacy, usato principalmente con Compute Engine e GCS, operativamente oneroso perché la chiave va passata a ogni chiamata API.

### Envelope Encryption

Cloud KMS non cifra mai direttamente payload grandi: usa il pattern envelope encryption, identico nel principio ad AWS KMS.

```
1. L'applicazione chiama KMS GenerateRandomBytes o genera localmente una DEK (Data Encryption Key)
2. La DEK cifra i dati localmente (AES-256-GCM)
3. KMS cifra la DEK con la chiave KMS (Key Encryption Key, mai esposta in chiaro fuori da KMS)
4. Si archiviano: dati cifrati + DEK cifrata
5. Per decifrare: KMS decifra la DEK → la DEK decifra i dati
```

A differenza di AWS KMS, Cloud KMS non espone una `GenerateDataKey` nativa a 2 output (plaintext+encrypted) per uso generico applicativo — il pattern tipico usa `Encrypt`/`Decrypt` su una DEK generata lato client, oppure si delega la cifratura a un servizio GCP già integrato nativamente con CMEK (GCS, BigQuery, Compute Engine Persistent Disk), che implementa l'envelope encryption internamente.

### Cloud HSM

**Cloud HSM** fornisce le stesse API di Cloud KMS, ma il materiale di chiave vive in moduli hardware certificati **FIPS 140-2 Level 3**, dedicati al progetto del cliente (non condivisi). Si sceglie al momento della creazione della Crypto Key impostando `protectionLevel: HSM` invece di `SOFTWARE`.

!!! tip "HSM è trasparente alle applicazioni"
    Il `protectionLevel` è un attributo della Crypto Key, non cambia nessuna chiamata API lato applicazione — `encrypt`/`decrypt` restano identiche. Si passa da `SOFTWARE` a `HSM` senza modificare il codice, solo la chiave sottostante.

### Rotazione Automatica

Cloud KMS supporta rotazione automatica schedulata per chiavi symmetric. La rotazione genera una nuova Key Version e la promuove a primary; le version precedenti restano disponibili per decrypt a tempo indeterminato (finché non vengono distrutte esplicitamente).

!!! note "La rotazione non ri-cifra i dati esistenti"
    Come in AWS KMS, ruotare una chiave non tocca i dati già cifrati — serve una pipeline di re-encryption esplicita se si vuole migrare dati a una nuova Key Version (rilevante per compliance che richiede "crypto-shredding" completo).

### IAM Binding su Chiavi KMS

I permessi KMS si assegnano a livello di Key Ring o Crypto Key (non solo a livello project), seguendo il principio del minimo privilegio.

| Ruolo | Permessi | Uso tipico |
|---|---|---|
| `roles/cloudkms.admin` | Gestione completa (crea, ruota, elimina, IAM) | Team security/platform |
| `roles/cloudkms.cryptoKeyEncrypterDecrypter` | Solo `encrypt`/`decrypt` | Service account applicativi |
| `roles/cloudkms.cryptoKeyEncrypter` | Solo `encrypt` | Processi write-only (es. ingestion) |
| `roles/cloudkms.cryptoKeyDecrypter` | Solo `decrypt` | Processi read-only |
| `roles/cloudkms.viewer` | Solo metadata, nessuna operazione crittografica | Audit |

### Secret Manager — Versioning

Ogni secret in Secret Manager è un contenitore logico con **version** numerate progressivamente (`1`, `2`, `3`, ...). Ogni version ha uno stato:

- `ENABLED`: accessibile, può essere letta
- `DISABLED`: non accessibile ma non eliminata (rollback possibile)
- `DESTROYED`: eliminata definitivamente, materiale non recuperabile

L'alias `latest` punta sempre alla version più recente in stato `ENABLED` — usarlo in sviluppo, ma **fissare il numero di version esplicito in produzione** per evitare che una rotazione non testata rompa un servizio in produzione senza preavviso.

### Secret Manager — Replica

| Modalità | Comportamento | Quando usarla |
|---|---|---|
| **Automatic** | Google sceglie le location di replica (multi-region trasparente) | Default, nessun requisito di residenza dati |
| **User-managed** | Il cliente specifica esplicitamente le location (es. solo `europe-west1`, `europe-west3`) | Compliance GDPR, data residency, workload mono-region |

---

## Architettura / Come Funziona

### Flusso CMEK con un Servizio GCP (es. GCS)

```
┌──────────────┐        IAM binding               ┌───────────────────┐
│ GCS Bucket   │──cryptoKeyEncrypterDecrypter──────▶│  Cloud KMS         │
│ (CMEK abil.) │        (service agent GCS)        │  Crypto Key        │
└──────────────┘                                    └───────────────────┘
       │                                                     │
       │ Upload oggetto                                      │
       ▼                                                     │
  GCS genera una DEK per l'oggetto ──────────────────────────▶
  KMS cifra la DEK con la Crypto Key, restituisce la DEK cifrata
  GCS archivia: oggetto cifrato con DEK + DEK cifrata

  Download: GCS invia la DEK cifrata a KMS → KMS verifica IAM e decifra →
  GCS usa la DEK plaintext per decifrare l'oggetto (mai esposta al chiamante)
```

Il punto critico: il **service agent** del servizio GCP (non l'utente finale) deve avere il binding IAM `cryptoKeyEncrypterDecrypter` sulla Crypto Key. Se manca, ogni operazione su quel bucket/dataset/disco fallisce con `PERMISSION_DENIED`, anche se l'utente ha pieno accesso al bucket stesso.

### Secret Manager + Workload Identity su GKE

```
Pod GKE (KSA annotato con Workload Identity)
      │
      │ 1. Richiede token OIDC al metadata server
      ▼
GSA (Google Service Account) con ruolo roles/secretmanager.secretAccessor
      │
      │ 2. API call accessSecretVersion con token IAM
      ▼
Secret Manager verifica IAM binding sul secret specifico
      │
      │ 3. Restituisce il valore del secret (version fissata, non "latest")
      ▼
Pod riceve il secret in memoria — nessuna chiave JSON, nessun secret su disco
```

Due pattern di integrazione su GKE:

1. **Secret Manager CSI Driver** (consigliato): monta il secret come file nel filesystem del Pod, sincronizzato automaticamente, nessuna modifica al codice applicativo
2. **SDK diretto**: l'applicazione chiama l'API Secret Manager a runtime — più controllo (cache, retry), ma richiede codice specifico

---

## Configurazione & Pratica

### Cloud KMS — Setup Base

```bash
# ── CREARE KEY RING E CRYPTO KEY ─────────────────────────────────────
# Il Key Ring è permanente — scegliere la location con attenzione
gcloud kms keyrings create prod-keyring \
    --location=europe-west8

# Crypto Key symmetric, rotazione automatica ogni 90 giorni
gcloud kms keys create app-encryption-key \
    --location=europe-west8 \
    --keyring=prod-keyring \
    --purpose=encryption \
    --rotation-period=90d \
    --next-rotation-time="$(date -u -d '+90 days' +%Y-%m-%dT%H:%M:%SZ)"

# Crypto Key HSM-backed (FIPS 140-2 Level 3)
gcloud kms keys create app-encryption-key-hsm \
    --location=europe-west8 \
    --keyring=prod-keyring \
    --purpose=encryption \
    --protection-level=hsm

# Listare key ring e chiavi
gcloud kms keyrings list --location=europe-west8
gcloud kms keys list --location=europe-west8 --keyring=prod-keyring
gcloud kms keys versions list --location=europe-west8 \
    --keyring=prod-keyring --key=app-encryption-key
```

```bash
# ── IAM BINDING MINIMO — SOLO DECRYPT ────────────────────────────────
# Service account che deve solo decrittare (es. applicazione che legge dati cifrati)
gcloud kms keys add-iam-policy-binding app-encryption-key \
    --location=europe-west8 \
    --keyring=prod-keyring \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/cloudkms.cryptoKeyDecrypter"

# Service account che deve solo cifrare (es. pipeline di ingestion)
gcloud kms keys add-iam-policy-binding app-encryption-key \
    --location=europe-west8 \
    --keyring=prod-keyring \
    --member="serviceAccount:ingest-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/cloudkms.cryptoKeyEncrypter"

# Verificare i binding attivi su una chiave
gcloud kms keys get-iam-policy app-encryption-key \
    --location=europe-west8 --keyring=prod-keyring
```

```python
# ── ENVELOPE ENCRYPTION — PYTHON ─────────────────────────────────────
from google.cloud import kms
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

client = kms.KeyManagementServiceClient()
key_name = client.crypto_key_path(
    "my-project-id", "europe-west8", "prod-keyring", "app-encryption-key"
)

def encrypt_data(plaintext: bytes) -> dict:
    # 1. Generare una DEK localmente (KMS cifra solo la DEK, mai il payload grande)
    dek = os.urandom(32)  # AES-256

    # 2. Cifrare i dati con la DEK
    aesgcm = AESGCM(dek)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # 3. Cifrare la DEK con Cloud KMS
    encrypt_response = client.encrypt(
        request={"name": key_name, "plaintext": dek}
    )

    # 4. Rilasciare il riferimento alla DEK (best effort: i bytes Python sono
    #    immutabili, non si può azzerare davvero la memoria)
    del dek

    return {
        "encrypted_data": nonce + ciphertext,
        "encrypted_dek": encrypt_response.ciphertext,
    }

def decrypt_data(encrypted_data: bytes, encrypted_dek: bytes) -> bytes:
    # 1. Decifrare la DEK tramite KMS
    decrypt_response = client.decrypt(
        request={"name": key_name, "ciphertext": encrypted_dek}
    )
    dek = decrypt_response.plaintext

    # 2. Decifrare i dati
    aesgcm = AESGCM(dek)
    nonce, ciphertext = encrypted_data[:12], encrypted_data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    del dek
    return plaintext
```

### Abilitare CMEK su un Servizio GCP (esempio GCS)

```bash
# 1. Concedere al service agent GCS il permesso sulla chiave
#    (il service agent è creato automaticamente, formato: service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com)
gcloud kms keys add-iam-policy-binding app-encryption-key \
    --location=europe-west8 \
    --keyring=prod-keyring \
    --member="serviceAccount:service-123456789@gs-project-accounts.iam.gserviceaccount.com" \
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"

# 2. Creare il bucket con CMEK
gcloud storage buckets create gs://my-prod-bucket \
    --location=europe-west8 \
    --default-encryption-key="projects/my-project-id/locations/europe-west8/keyRings/prod-keyring/cryptoKeys/app-encryption-key"

# Verificare la chiave di default di un bucket esistente
gcloud storage buckets describe gs://my-prod-bucket \
    --format="value(encryption.defaultKmsKeyName)"
```

### Secret Manager — Setup e Rotazione

```bash
# ── CREARE E POPOLARE UN SECRET ──────────────────────────────────────
# Replica automatic (default — Google sceglie le location)
echo -n "MySecurePassword123!" | gcloud secrets create prod-db-password \
    --data-file=- \
    --replication-policy="automatic" \
    --labels=environment=production,app=myapp

# Replica user-managed (data residency — solo EU)
echo -n "MySecurePassword123!" | gcloud secrets create prod-db-password-eu \
    --data-file=- \
    --replication-policy="user-managed" \
    --locations="europe-west1,europe-west3"

# Secret cifrato con CMEK invece della chiave Google-managed di default.
# Con replica automatic la chiave KMS deve stare in location `global`;
# --kms-key-name NON è valido con replica user-managed.
# Prerequisito: service agent Secret Manager
# (service-PROJECT_NUMBER@gcp-sa-secretmanager.iam.gserviceaccount.com)
# con roles/cloudkms.cryptoKeyEncrypterDecrypter sulla chiave.
echo -n "MySecurePassword123!" | gcloud secrets create prod-db-password-cmek \
    --data-file=- \
    --replication-policy="automatic" \
    --kms-key-name="projects/my-project-id/locations/global/keyRings/prod-keyring-global/cryptoKeys/secrets-key"

# CMEK + user-managed: una chiave per ogni location, via file di policy
# (replication.json: {"userManaged":{"replicas":[{"location":"europe-west8",
#   "customerManagedEncryption":{"kmsKeyName":"projects/.../locations/europe-west8/keyRings/.../cryptoKeys/..."}}]}})
# gcloud secrets create prod-db-password-eu-cmek --data-file=- --replication-policy-file=replication.json

# ── AGGIUNGERE UNA NUOVA VERSION (rotazione manuale) ─────────────────
echo -n "NewSecurePassword456!" | gcloud secrets versions add prod-db-password \
    --data-file=-

# Listare le version
gcloud secrets versions list prod-db-password

# Leggere la version specifica (preferito in produzione)
gcloud secrets versions access 3 --secret=prod-db-password

# Leggere l'ultima version attiva (solo per sviluppo/test)
gcloud secrets versions access latest --secret=prod-db-password

# Disabilitare una version compromessa (reversibile)
gcloud secrets versions disable 2 --secret=prod-db-password

# Distruggere definitivamente una version (irreversibile)
gcloud secrets versions destroy 1 --secret=prod-db-password
```

```bash
# ── IAM BINDING MINIMO SU UN SECRET ──────────────────────────────────
gcloud secrets add-iam-policy-binding prod-db-password \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Verificare chi può accedere a un secret
gcloud secrets get-iam-policy prod-db-password
```

### Secret Manager CSI Driver su GKE

```yaml
# 1. SecretProviderClass — definisce quali secret montare
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: prod-db-secrets
  namespace: production
spec:
  provider: gcp
  parameters:
    secrets: |
      - resourceName: "projects/my-project-id/secrets/prod-db-password/versions/2"   # version fissata (non latest) in produzione
        path: "db-password"
      - resourceName: "projects/my-project-id/secrets/prod-api-key/versions/3"
        path: "api-key"
---
# 2. Deployment che monta il secret come file
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  template:
    spec:
      serviceAccountName: my-app-ksa   # KSA annotato con Workload Identity (vedi iam-service-accounts.md)
      containers:
      - name: app
        image: europe-west8-docker.pkg.dev/my-project-id/my-repo/my-app:latest
        volumeMounts:
        - name: secrets
          mountPath: "/mnt/secrets"
          readOnly: true
      volumes:
      - name: secrets
        csi:
          driver: secrets-store.csi.k8s.io
          readOnly: true
          volumeAttributes:
            secretProviderClass: "prod-db-secrets"
```

```python
# Accesso programmatico diretto (alternativa al CSI driver — più controllo su cache/retry)
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()

def get_secret(project_id: str, secret_id: str, version: str = "latest") -> str:
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# In produzione: fissare la version esplicita, non "latest"
db_password = get_secret("my-project-id", "prod-db-password", version="3")
```

### Cifratura At-Rest di Default vs CMEK

```bash
# Verificare se un servizio sta usando CMEK o chiave Google-managed
gcloud storage buckets describe gs://my-bucket \
    --format="value(encryption.defaultKmsKeyName)"
# Output vuoto = Google-managed key (default)
# Output valorizzato = CMEK attivo

# Stessa verifica per un disco Persistent Disk (Compute Engine)
gcloud compute disks describe my-disk --zone=europe-west8-a \
    --format="value(diskEncryptionKey.kmsKeyName)"

# BigQuery dataset — verificare default CMEK
bq show --format=prettyjson my-project-id:my_dataset | grep -A2 defaultEncryptionConfiguration
```

---

## Best Practices

!!! warning "Service Agent, non Service Account utente"
    Il binding IAM per CMEK su un servizio GCP (GCS, BigQuery, Compute) va fatto sul **service agent** del servizio (es. `service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com`), non sul service account dell'applicazione. Confondere i due è la causa più comune di `PERMISSION_DENIED` su CMEK.

!!! tip "Fissare la version in produzione, mai 'latest'"
    Usare `latest` in Secret Manager per servizi di produzione introduce un rischio: una rotazione del secret (es. password DB cambiata) si propaga istantaneamente a tutti i Pod, senza finestra di test. Fissare un numero di version esplicito e aggiornarlo con un deployment controllato.

1. Separare Key Ring per ambiente (`prod-keyring`, `staging-keyring`) — mai condividere chiavi tra ambienti
2. Usare CMEK solo dove richiesto da compliance — introduce un single point of failure aggiuntivo (se la chiave viene distrutta, i dati sono irrecuperabili)
3. Applicare IAM binding granulari (`cryptoKeyEncrypter` o `cryptoKeyDecrypter` separati) invece del generico `cryptoKeyEncrypterDecrypter` quando il workload ha un solo verso di flusso
4. Abilitare rotazione automatica per tutte le Crypto Key symmetric in produzione
5. Per Secret Manager, usare replica `user-managed` quando la data residency è un requisito esplicito (GDPR)
6. Preferire il CSI driver rispetto all'SDK diretto quando possibile — riduce la superficie di codice che gestisce secret
7. Audit periodico degli accessi con Cloud Audit Logs (Data Access Logs devono essere abilitati esplicitamente per KMS e Secret Manager — non sono on di default)
8. Per rotazione dinamica delle credenziali (non solo versioning statico), valutare [HashiCorp Vault](../../../security/secret-management/vault.md) come layer sopra GCP

---

## Troubleshooting

### Scenario 1 — PERMISSION_DENIED su operazione CMEK

**Sintomo:** `Permission 'cloudkms.cryptoKeyVersions.useToEncrypt' denied on resource` durante upload su bucket CMEK o creazione disco cifrato.

**Causa:** Il service agent del servizio GCP (non l'utente/applicazione) non ha il binding `cryptoKeyEncrypterDecrypter` sulla Crypto Key.

**Soluzione:**
```bash
# Identificare il service agent corretto per il servizio
gcloud storage service-agent --project=my-project-id

# Concedere il binding mancante
gcloud kms keys add-iam-policy-binding app-encryption-key \
    --location=europe-west8 \
    --keyring=prod-keyring \
    --member="serviceAccount:service-123456789@gs-project-accounts.iam.gserviceaccount.com" \
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
```

### Scenario 2 — Secret non accessibile da Cloud Run

**Sintomo:** Il servizio Cloud Run fallisce al deploy o a runtime con `PERMISSION_DENIED: Permission 'secretmanager.versions.access' denied`.

**Causa:** Il service account usato da Cloud Run (default o custom) non ha `roles/secretmanager.secretAccessor` sul secret referenziato.

**Soluzione:**
```bash
# Verificare quale SA usa il servizio Cloud Run
gcloud run services describe my-service --region=europe-west8 \
    --format="value(spec.template.spec.serviceAccountName)"

# Concedere l'accesso al secret
gcloud secrets add-iam-policy-binding prod-db-password \
    --member="serviceAccount:my-service-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Verificare il mount del secret come variabile d'ambiente
gcloud run services update my-service \
    --region=europe-west8 \
    --update-secrets=DB_PASSWORD=prod-db-password:latest
```

### Scenario 3 — Chiave KMS in stato DISABLED impedisce il decrypt

**Sintomo:** `KeyVersion is not enabled, current state is: DISABLED` durante una chiamata `decrypt`.

**Causa:** La Key Version usata per cifrare i dati è stata disabilitata (manualmente o per policy), ma esistono ancora dati cifrati con quella version.

**Soluzione:**
```bash
# Verificare lo stato delle version
gcloud kms keys versions list \
    --location=europe-west8 --keyring=prod-keyring --key=app-encryption-key

# Riabilitare la version necessaria per il decrypt (se non è stata DESTROYED)
gcloud kms keys versions enable VERSION_ID \
    --location=europe-west8 --keyring=prod-keyring --key=app-encryption-key
```

!!! warning "DESTROYED è irreversibile"
    A differenza di `DISABLED`, una Key Version in stato `DESTROYED` elimina il materiale crittografico in modo permanente. La distruzione passa prima per `DESTROY_SCHEDULED` (ripristinabile con `gcloud kms keys versions restore`) per un periodo di grazia fissato alla creazione della Crypto Key (`--destroy-scheduled-duration`, default 30 giorni, minimo 24h, non modificabile dopo). Scaduto il periodo, qualsiasi dato cifrato solo con quella version diventa definitivamente irrecuperabile ("crypto-shredding").

### Scenario 4 — CSI Driver non monta il secret nel Pod

**Sintomo:** Il Pod resta in `ContainerCreating` con evento `FailedMount: MountVolume.SetUp failed ... rpc error: PermissionDenied`.

**Causa:** Il KSA del Pod non è collegato correttamente al GSA via Workload Identity, oppure il GSA manca del ruolo `secretAccessor`.

**Soluzione:**
```bash
# Verificare l'annotazione Workload Identity sul KSA
kubectl describe serviceaccount my-app-ksa -n production

# Verificare il binding IAM sul GSA target
gcloud iam service-accounts get-iam-policy \
    my-app-gsa@my-project-id.iam.gserviceaccount.com
# Deve comparire: roles/iam.workloadIdentityUser per il KSA

# Verificare che il GSA abbia accesso al secret
gcloud secrets get-iam-policy prod-db-password \
    --flatten="bindings[].members" \
    --filter="bindings.members:my-app-gsa"

# Log del CSI driver per diagnosi dettagliata
kubectl logs -n kube-system -l app=csi-secrets-store --tail=100
```

### PERMISSION_DENIED generico — checklist rapida

1. Verificare che il principal corretto (service agent o service account applicativo) abbia il ruolo giusto
2. Verificare che il ruolo sia assegnato sulla risorsa corretta (Key Ring/Crypto Key o secret specifico, non solo a livello project)
3. Verificare eventuali Organization Policy che bloccano l'uso di CMEK (`constraints/gcp.restrictNonCmekServices`)
4. Verificare che la version del secret referenziata esista e sia `ENABLED`

---

## Relazioni

??? info "HashiCorp Vault — Secret Dinamici"
    Secret Manager gestisce secret statici versionati. Per credenziali generate dinamicamente con TTL e revoca automatica (dynamic secrets), serve un layer come Vault, che supporta anche GCP come secrets engine.

    **Approfondimento completo →** [HashiCorp Vault](../../../security/secret-management/vault.md)

??? info "IAM e Service Account GCP"
    I binding IAM su chiavi KMS e secret seguono lo stesso modello IAM generale di GCP (member, role, binding, condition) — incluso l'uso di Service Account e Workload Identity per workload GKE/Cloud Run.

    **Approfondimento completo →** [GCP IAM e Service Account](../iam/iam-service-accounts.md)

??? info "AWS KMS e Secrets Manager — Confronto"
    AWS espone concetti equivalenti (CMK, envelope encryption, rotazione, Secrets Manager con rotazione automatica via Lambda). La differenza principale: AWS Secrets Manager supporta rotazione automatica nativa per RDS/Redshift/DocumentDB. GCP Secret Manager non ruota i valori da solo: offre solo uno schedule di rotazione (`--rotation-period`, `--next-rotation-time`) che pubblica una notifica su un topic Pub/Sub; la logica che genera la nuova version (`gcloud secrets versions add`) va scritta da te, es. con Cloud Run functions in ascolto sul topic, o delegata a Vault.

    **Approfondimento completo →** [AWS KMS, Secrets Manager, ACM](../../aws/security/kms-secrets.md)

---

## Riferimenti

- [Cloud KMS Documentation](https://cloud.google.com/kms/docs)
- [Cloud KMS — Key Rotation](https://cloud.google.com/kms/docs/key-rotation)
- [CMEK Overview](https://cloud.google.com/kms/docs/cmek)
- [Cloud HSM](https://cloud.google.com/kms/docs/hsm)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Secret Manager — Access Control](https://cloud.google.com/secret-manager/docs/access-control)
- [Secrets Store CSI Driver for GCP](https://cloud.google.com/secret-manager/docs/secret-manager-managed-csi-component)
- [Cloud KMS Pricing](https://cloud.google.com/kms/pricing)
- [Secret Manager Pricing](https://cloud.google.com/secret-manager/pricing)
