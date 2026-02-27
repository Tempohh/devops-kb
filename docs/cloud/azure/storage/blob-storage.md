---
title: "Azure Blob Storage"
slug: blob-storage-azure
category: cloud
tags: [azure, blob-storage, data-lake, storage-account, lifecycle-management, sas, azcopy]
search_keywords: [Azure Blob Storage, object storage Azure, storage account, LRS ZRS GRS GZRS RA-GRS redundancy, Hot Cool Cold Archive tier, lifecycle management policy, SAS token Shared Access Signature, AzCopy sync, Data Lake Storage Gen2 hierarchical namespace, immutable storage WORM, object replication, static website hosting]
parent: cloud/azure/storage/_index
related: [cloud/azure/security/key-vault, cloud/azure/compute/aks-containers, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/storage/blobs/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Blob Storage

## Panoramica

Azure Blob Storage è il servizio di object storage di Azure, equivalente ad Amazon S3. Progettato per archiviare quantità massicce di dati non strutturati — file, immagini, video, log, backup, archivi — con durabilità 11 nines (99.999999999%) grazie alla replica automatica. È anche la base di Azure Data Lake Storage Gen2 per analytics.

Non usare Blob Storage per: dati che richiedono query SQL strutturate (usare Azure SQL), file condivisi tra VM con protocollo SMB/NFS (usare Azure Files), o messaggi a coda (usare Service Bus o Queue Storage).

## Storage Account: Creazione e Configurazione

```bash
RG="rg-storage-prod"
LOCATION="westeurope"
SA_NAME="mystorageaccount2026"  # Globalmente unico, 3-24 char, solo lowercase e numeri

# Creare storage account con best practices di sicurezza
az storage account create \
  --resource-group $RG \
  --name $SA_NAME \
  --location $LOCATION \
  --sku Standard_GRS \
  --kind StorageV2 \
  --access-tier Hot \
  --https-only true \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --allow-shared-key-access false \
  --enable-hierarchical-namespace false \
  --default-action Deny \
  --bypass AzureServices Logging Metrics

# Verificare configurazione di sicurezza
az storage account show \
  --resource-group $RG \
  --name $SA_NAME \
  --query "{name:name, httpsOnly:enableHttpsTrafficOnly, minTls:minimumTlsVersion, publicBlob:allowBlobPublicAccess, sharedKey:allowSharedKeyAccess}" \
  --output json
```

!!! warning "allow-shared-key-access false"
    Disabilitare l'accesso con chiavi condivise (`--allow-shared-key-access false`) forza l'autenticazione Entra ID + Managed Identity. Verifica che tutte le applicazioni supportino questa modalità prima di abilitarlo in produzione.

## Tipi di Ridondanza

| Tipo | Repliche | Regioni | Availability SLA | RTO | RPO | Use Case |
|---|---|---|---|---|---|---|
| **LRS** (Locally Redundant) | 3 sync | 1 datacenter | 99.9% | – | – | Dev/test, dati ricreable |
| **ZRS** (Zone Redundant) | 3 sync | 3 zone | 99.99% | Automatico | ~0 | Produzione, alta disponibilità locale |
| **GRS** (Geo Redundant) | 6 (3+3) | 2 regioni | 99.99% | Ore | <1h | Disaster recovery, backup cross-region |
| **GZRS** (Geo+Zone Redundant) | 6 (3z+3) | 2 regioni | 99.99% | Ore | <1h | Best protection, workload critici |
| **RA-GRS** (Read-Access Geo) | 6 (3+3) | 2 regioni | 99.99%/99.9% | Automatico lettura | <1h | Read scaling cross-region, CDN-like |
| **RA-GZRS** (Read-Access Geo+Zone) | 6 | 2 regioni | 99.99%/99.9% | Automatico lettura | <1h | Massima disponibilità + read scaling |

```bash
# Aggiornare ridondanza storage account esistente
az storage account update \
  --resource-group $RG \
  --name $SA_NAME \
  --sku Standard_GZRS

# Verificare ridondanza corrente
az storage account show \
  --resource-group $RG \
  --name $SA_NAME \
  --query "sku.name" -o tsv
```

## Tier di Accesso Blob

Azure Blob offre 4 tier di accesso con diversi trade-off tra costo di storage e costo di operazioni:

| Tier | Storage Cost | Access Cost | Min Stay | Latency | Use Case |
|---|---|---|---|---|---|
| **Hot** | Alto | Basso | – | Millisecondi | Accesso frequente, web app attive |
| **Cool** | Medio | Medio | 30 giorni | Millisecondi | Accesso infrequente, backup recenti |
| **Cold** | Basso | Alto | 90 giorni | Millisecondi | Accesso raro, archivi recenti |
| **Archive** | Molto basso | Molto alto | 180 giorni | Ore (rehydration) | Archiviazione a lungo termine, compliance |

!!! note "Archive Rehydration"
    I blob in tier Archive sono "offline" e non accessibili direttamente. Per accedervi è necessario un processo di "rehydration" (da Archive a Hot/Cool) che richiede ore. Priorità Standard: 15h; Priorità High: 1h (più costoso).

```bash
# Impostare tier a livello di blob singolo
az storage blob set-tier \
  --account-name $SA_NAME \
  --container-name mycontainer \
  --name large-backup.tar.gz \
  --tier Archive \
  --auth-mode login

# Rehydration da Archive (richiede ore)
az storage blob set-tier \
  --account-name $SA_NAME \
  --container-name mycontainer \
  --name large-backup.tar.gz \
  --tier Cool \
  --rehydrate-priority Standard \
  --auth-mode login
```

## Operazioni Base su Container e Blob

```bash
# Autenticazione con Entra ID (preferita su chiavi)
export AZURE_STORAGE_AUTH_MODE=login

# Creare container
az storage container create \
  --account-name $SA_NAME \
  --name mycontainer \
  --auth-mode login

# Upload file
az storage blob upload \
  --account-name $SA_NAME \
  --container-name mycontainer \
  --name path/to/myfile.txt \
  --file /local/path/myfile.txt \
  --auth-mode login

# Upload directory completa
az storage blob upload-batch \
  --account-name $SA_NAME \
  --destination mycontainer \
  --source /local/directory \
  --pattern "*.csv" \
  --auth-mode login

# Download file
az storage blob download \
  --account-name $SA_NAME \
  --container-name mycontainer \
  --name path/to/myfile.txt \
  --file /local/download/myfile.txt \
  --auth-mode login

# Listare blob
az storage blob list \
  --account-name $SA_NAME \
  --container-name mycontainer \
  --prefix logs/2026/ \
  --output table \
  --auth-mode login

# Copiare blob tra container/account
az storage blob copy start \
  --account-name $SA_NAME \
  --destination-container archive \
  --destination-blob myfile.txt \
  --source-account-name otherstorage \
  --source-container source \
  --source-blob myfile.txt
```

## Lifecycle Management Policy

Le policy di lifecycle management automatizzano il tiering e l'eliminazione dei blob in base all'età.

```bash
# Creare policy lifecycle (file JSON)
cat > lifecycle-policy.json << 'EOF'
{
  "rules": [
    {
      "name": "tier-to-cool",
      "enabled": true,
      "type": "Lifecycle",
      "definition": {
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["logs/", "backups/"]
        },
        "actions": {
          "baseBlob": {
            "tierToCool": {
              "daysAfterModificationGreaterThan": 30
            },
            "tierToCold": {
              "daysAfterModificationGreaterThan": 90
            },
            "tierToArchive": {
              "daysAfterModificationGreaterThan": 180
            },
            "delete": {
              "daysAfterModificationGreaterThan": 2555
            }
          },
          "snapshot": {
            "delete": {
              "daysAfterCreationGreaterThan": 90
            }
          },
          "version": {
            "tierToCool": {
              "daysAfterCreationGreaterThan": 30
            },
            "delete": {
              "daysAfterCreationGreaterThan": 365
            }
          }
        }
      }
    }
  ]
}
EOF

az storage account management-policy create \
  --account-name $SA_NAME \
  --resource-group $RG \
  --policy @lifecycle-policy.json
```

## SAS Token (Shared Access Signature)

I SAS token forniscono accesso delegato a risorse storage con permessi e scadenza specifici. Utili per condividere accesso temporaneo senza esporre le chiavi account.

### Tipi di SAS

| Tipo | Scope | Revoca | Use Case |
|---|---|---|---|
| **Account SAS** | Intero account | Solo ruotando chiave | Accesso multi-servizio temporaneo |
| **Service SAS** | Container/blob specifico | Solo ruotando chiave | Accesso a risorsa specifica |
| **User Delegation SAS** | Blob/container | Sì (revoca identity) | **Preferito**: firmato con credenziali Entra ID |

```bash
# User Delegation SAS (preferito — firmato con Entra ID)
az storage blob generate-sas \
  --account-name $SA_NAME \
  --container-name mycontainer \
  --name report-2026-02.pdf \
  --permissions r \
  --expiry 2026-02-28T23:59:59Z \
  --auth-mode login \
  --as-user \
  --https-only \
  --output tsv

# Service SAS per container (upload temporaneo da client esterno)
az storage container generate-sas \
  --account-name $SA_NAME \
  --name uploads \
  --permissions rwl \
  --start 2026-02-26T00:00:00Z \
  --expiry 2026-02-26T06:00:00Z \
  --https-only \
  --auth-mode login \
  --as-user \
  --output tsv
```

!!! warning "Best Practice SAS"
    Usa sempre SAS con User Delegation (`--as-user`). Imposta sempre `--https-only`. Usa la scadenza più breve possibile. Non hardcodare SAS nell'applicazione: generali dinamicamente e memorizzali in Key Vault.

## Accesso Sicuro con Managed Identity

```bash
# Assegnare Storage Blob Data Contributor alla Managed Identity
az role assignment create \
  --assignee $(az identity show --resource-group $RG --name mi-myapp --query principalId -o tsv) \
  --role "Storage Blob Data Contributor" \
  --scope $(az storage account show --resource-group $RG --name $SA_NAME --query id -o tsv)

# Accesso solo a container specifico
az role assignment create \
  --assignee PRINCIPAL_ID \
  --role "Storage Blob Data Reader" \
  --scope "$(az storage account show --resource-group $RG --name $SA_NAME --query id -o tsv)/blobServices/default/containers/readonly-data"
```

```python
# Accesso da Python con Managed Identity
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = BlobServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=credential
)

# Upload
container_client = client.get_container_client("mycontainer")
with open("local_file.txt", "rb") as data:
    container_client.upload_blob(name="remote_file.txt", data=data, overwrite=True)

# Download
blob_client = client.get_blob_client(container="mycontainer", blob="remote_file.txt")
with open("downloaded_file.txt", "wb") as download_file:
    download_file.write(blob_client.download_blob().readall())
```

## Static Website Hosting

```bash
# Abilitare static website (index.html + 404.html)
az storage blob service-properties update \
  --account-name $SA_NAME \
  --static-website \
  --index-document index.html \
  --404-document 404.html \
  --auth-mode login

# Upload file sito web
az storage blob upload-batch \
  --account-name $SA_NAME \
  --destination '$web' \
  --source ./dist \
  --content-type text/html \
  --auth-mode login

# Ottenere URL del sito
az storage account show \
  --resource-group $RG \
  --name $SA_NAME \
  --query "primaryEndpoints.web" -o tsv

# Abbinare Azure CDN per HTTPS custom domain e performance globale
az cdn endpoint create \
  --resource-group $RG \
  --profile-name cdn-prod \
  --name myapp-cdn \
  --origin myapp.z6.web.core.windows.net \
  --origin-host-header myapp.z6.web.core.windows.net \
  --enable-compression \
  --query-string-caching-behavior UseQueryString
```

## AzCopy

AzCopy è lo strumento CLI ottimizzato per trasferimenti bulk da/verso Azure Storage, con supporto per trasferimenti paralleli, ripresa automatica e ottimizzazione bandwidth.

```bash
# Login con Entra ID
azcopy login --tenant-id YOUR_TENANT_ID

# Copiare file locale in Blob
azcopy copy '/local/path/file.txt' \
  'https://mystorageaccount.blob.core.windows.net/mycontainer/file.txt'

# Copiare directory completa (ricorsiva)
azcopy copy '/local/data/' \
  'https://mystorageaccount.blob.core.windows.net/mycontainer/data/' \
  --recursive

# Sincronizzare directory (solo file modificati)
azcopy sync '/local/data/' \
  'https://mystorageaccount.blob.core.windows.net/mycontainer/data/' \
  --recursive \
  --delete-destination true

# Copiare tra due storage account (server-side, senza download locale)
azcopy copy \
  'https://source.blob.core.windows.net/container?SAS_TOKEN' \
  'https://destination.blob.core.windows.net/container?SAS_TOKEN' \
  --recursive

# Listare contenuto container
azcopy list 'https://mystorageaccount.blob.core.windows.net/mycontainer'

# Benchmark velocità upload
azcopy benchmark 'https://mystorageaccount.blob.core.windows.net/mycontainer'
```

## Data Lake Storage Gen2

Data Lake Storage Gen2 combina Blob Storage con un filesystem gerarchico (Hierarchical Namespace) per analytics, big data e ML. Si abilita al momento della creazione dello storage account.

```bash
# Creare storage account con HNS abilitato (Data Lake Gen2)
az storage account create \
  --resource-group $RG \
  --name mydatalake2026 \
  --location $LOCATION \
  --sku Standard_GZRS \
  --kind StorageV2 \
  --enable-hierarchical-namespace true \
  --https-only true \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

# Creare filesystem (equivalente container)
az storage fs create \
  --account-name mydatalake2026 \
  --name raw \
  --auth-mode login

# Creare directory nel filesystem
az storage fs directory create \
  --account-name mydatalake2026 \
  --file-system raw \
  --name "2026/02/26" \
  --auth-mode login

# Upload file
az storage fs file upload \
  --account-name mydatalake2026 \
  --file-system raw \
  --path "2026/02/26/events.parquet" \
  --source ./events.parquet \
  --auth-mode login

# Impostare POSIX ACL su directory
az storage fs access set \
  --account-name mydatalake2026 \
  --file-system raw \
  --path "2026/02/26" \
  --acl "user::rwx,group::r-x,other::---,mask::rwx,user:OBJECT_ID:r-x" \
  --auth-mode login
```

!!! tip "Data Lake Gen2 con Spark/Databricks"
    Data Lake Gen2 è il storage layer standard per Azure Databricks e Synapse Analytics. Il filesystem gerarchico permette operazioni atomiche su directory (rename, delete) richieste dai framework analytics.

## Immutable Storage (WORM)

Lo storage immutabile (Write Once Read Many) previene la modifica o eliminazione di blob per un periodo definito. Utile per compliance (SOX, FINRA, SEC 17a-4).

```bash
# Impostare policy immutabilità sul container
az storage container immutability-policy create \
  --resource-group $RG \
  --account-name $SA_NAME \
  --container-name compliance-docs \
  --period 2555 \
  --allow-protected-append-writes false

# Bloccare la policy (rende immutabile anche la policy stessa)
az storage container immutability-policy lock \
  --resource-group $RG \
  --account-name $SA_NAME \
  --container-name compliance-docs \
  --if-match $(az storage container immutability-policy show --resource-group $RG --account-name $SA_NAME --container-name compliance-docs --query etag -o tsv)
```

!!! warning "WORM Lock Irreversibile"
    Una volta che la policy WORM viene "locked", non può essere modificata o rimossa prima della scadenza. Testare accuratamente in ambiente di staging prima di applicare in produzione.

## Object Replication Policy

La replica degli oggetti copia in modo asincrono i blob Block tra storage account in regioni diverse (cross-region replication).

```bash
# Abilitare versioning (obbligatorio per object replication)
az storage account blob-service-properties update \
  --account-name $SA_NAME \
  --resource-group $RG \
  --enable-versioning true \
  --enable-change-feed true

# Creare policy di replica sul destination account
az storage account or-policy create \
  --account-name destination-storage \
  --resource-group $RG \
  --source-account $SA_NAME \
  --destination-account destination-storage \
  --source-container source-data \
  --destination-container replica-data \
  --min-creation-time 2026-01-01T00:00:00Z \
  --prefix-match logs/critical/
```

## Private Endpoint per Blob Storage

```bash
# Creare Private Endpoint per Blob
az network private-endpoint create \
  --resource-group $RG \
  --name pep-storage-blob \
  --vnet-name vnet-prod \
  --subnet snet-private-endpoints \
  --private-connection-resource-id $(az storage account show --resource-group $RG --name $SA_NAME --query id -o tsv) \
  --group-ids blob \
  --connection-name conn-storage-blob

# DNS: zona privata per Blob
az network private-dns zone create \
  --resource-group $RG \
  --name "privatelink.blob.core.windows.net"

az network private-dns link vnet create \
  --resource-group $RG \
  --zone-name "privatelink.blob.core.windows.net" \
  --name link-vnet-prod \
  --virtual-network vnet-prod \
  --registration-enabled false

# Registrare record A nel DNS privato
NIC_ID=$(az network private-endpoint show --resource-group $RG --name pep-storage-blob --query networkInterfaces[0].id -o tsv)
PRIVATE_IP=$(az network nic show --ids $NIC_ID --query ipConfigurations[0].privateIPAddress -o tsv)

az network private-dns record-set a create \
  --resource-group $RG \
  --zone-name "privatelink.blob.core.windows.net" \
  --name $SA_NAME

az network private-dns record-set a add-record \
  --resource-group $RG \
  --zone-name "privatelink.blob.core.windows.net" \
  --record-set-name $SA_NAME \
  --ipv4-address $PRIVATE_IP
```

## Best Practices

- Disabilita sempre l'accesso pubblico ai blob (`--allow-blob-public-access false`)
- Usa **User Delegation SAS** invece di Account SAS per access delegation temporanea
- Abilita **soft delete** per blob e container (protezione contro eliminazione accidentale)
- Configura **Lifecycle Management** per ottimizzare automaticamente i costi di storage
- Usa **GZRS** per workload critici che richiedono massima durabilità e disponibilità
- Per analytics, usa sempre **Data Lake Gen2** con HNS abilitato

```bash
# Abilitare soft delete (blob e container)
az storage account blob-service-properties update \
  --account-name $SA_NAME \
  --resource-group $RG \
  --enable-delete-retention true \
  --delete-retention-days 30 \
  --enable-container-delete-retention true \
  --container-delete-retention-days 30
```

## Riferimenti

- [Documentazione Azure Blob Storage](https://learn.microsoft.com/azure/storage/blobs/)
- [Azure Storage Redundancy](https://learn.microsoft.com/azure/storage/common/storage-redundancy)
- [Lifecycle Management](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-overview)
- [Data Lake Storage Gen2](https://learn.microsoft.com/azure/storage/blobs/data-lake-storage-introduction)
- [AzCopy Documentation](https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10)
- [Immutable Storage](https://learn.microsoft.com/azure/storage/blobs/immutable-storage-overview)
