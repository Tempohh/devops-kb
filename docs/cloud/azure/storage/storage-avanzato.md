---
title: "Azure Storage Avanzato"
slug: storage-avanzato-azure
category: cloud
tags: [azure, azure-files, managed-disks, table-storage, queue-storage, nfs, smb]
search_keywords: [Azure Files SMB NFS, Azure File Sync, Premium File Shares SSD, Managed Disks Premium SSD Ultra Disk, Queue Storage message queue, Table Storage NoSQL key-value, storage firewall network rules, customer-managed keys CMK, storage access keys rotation, Azure File Sync hybrid cloud]
parent: cloud/azure/storage/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/security/key-vault, cloud/azure/compute/aks-containers]
official_docs: https://learn.microsoft.com/azure/storage/files/
status: complete
difficulty: advanced
last_updated: 2026-02-26
---

# Azure Storage Avanzato

## Panoramica

Oltre a Blob Storage, Azure offre servizi storage specializzati per scenari specifici: condivisione file (Azure Files), block storage per VM (Managed Disks), messaggi leggeri (Queue Storage) e dati strutturati chiave-valore (Table Storage). Questo documento copre anche le funzionalità avanzate di sicurezza come storage firewall e Customer-managed Keys.

## Azure Files

Azure Files offre file share gestiti nel cloud accessibili via protocollo SMB 3.0 e NFS 4.1. Può sostituire server NAS on-premises e si monta su Windows, Linux e macOS.

### Tipi di File Share

| Tipo | Protocollo | Storage | IOPS Max | Use Case |
|---|---|---|---|---|
| **Standard** (HDD) | SMB, NFS | LRS/GRS/ZRS | 10.000 | Home directory, dev/test, archivi |
| **Premium** (SSD) | SMB, NFS | ZRS/LRS | 100.000 | Database file, ERP, workload I/O intensivi |

```bash
RG="rg-storage-prod"
SA_NAME="mystorageaccount2026"

# Creare file share SMB Standard
az storage share create \
  --account-name $SA_NAME \
  --name myfileshare \
  --quota 1024 \
  --auth-mode login

# Creare file share NFS (richiede Premium tier storage account)
az storage account create \
  --resource-group $RG \
  --name mypremiumnfs2026 \
  --location westeurope \
  --sku Premium_LRS \
  --kind FileStorage \
  --https-only false  # NFS non usa HTTPS ma transport-level security

az storage share-rm create \
  --resource-group $RG \
  --storage-account mypremiumnfs2026 \
  --name nfs-share \
  --enabled-protocols NFS \
  --root-squash NoRootSquash \
  --quota 2048

# Listare file in un share
az storage file list \
  --account-name $SA_NAME \
  --share-name myfileshare \
  --output table \
  --auth-mode login
```

### Mount su Linux (SMB)

```bash
# Installare cifs-utils
sudo apt-get install cifs-utils -y

# Ottenere la storage account key
STORAGE_KEY=$(az storage account keys list \
  --resource-group $RG \
  --account-name $SA_NAME \
  --query "[0].value" -o tsv)

# Creare directory mount point
sudo mkdir -p /mnt/azurefiles

# Mount temporaneo
sudo mount -t cifs \
  //$SA_NAME.file.core.windows.net/myfileshare \
  /mnt/azurefiles \
  -o vers=3.0,username=$SA_NAME,password=$STORAGE_KEY,dir_mode=0777,file_mode=0777,serverino

# Mount persistente in /etc/fstab
echo "//$SA_NAME.file.core.windows.net/myfileshare /mnt/azurefiles cifs vers=3.0,username=$SA_NAME,password=$STORAGE_KEY,dir_mode=0777,file_mode=0777,serverino 0 0" | sudo tee -a /etc/fstab
```

### Mount su Windows (SMB)

```powershell
# Mappare come drive Z: (PowerShell)
$StorageAccountName = "mystorageaccount2026"
$ShareName = "myfileshare"
$StorageKey = "BASE64_KEY_HERE"

$connectTestResult = Test-NetConnection -ComputerName "$StorageAccountName.file.core.windows.net" -Port 445
if ($connectTestResult.TcpTestSucceeded) {
    # Salvare credenziali
    cmd.exe /C "cmdkey /add:`"$StorageAccountName.file.core.windows.net`" /user:`"localhost\$StorageAccountName`" /pass:`"$StorageKey`""
    # Mount drive
    New-PSDrive -Name Z -PSProvider FileSystem -Root "\\$StorageAccountName.file.core.windows.net\$ShareName" -Persist
}
```

### Azure File Sync

Azure File Sync sincronizza file share on-premises con Azure Files, creando un tier ibrido dove i file acceduti raramente vengono spostati sul cloud (Cloud Tiering).

```
On-Premises Windows Server
├── File Server con Azure File Sync Agent
│   ├── Hot files → mantiene copia locale (stub)
│   └── Cold files → solo stub, contenuto su Azure Files
│
Azure Files (cloud share completo)
│   └── Tutti i file (hot + cold)
```

Architettura installazione:
1. Creare Storage Sync Service su Azure
2. Installare agente File Sync su Windows Server
3. Registrare il server nel Storage Sync Service
4. Creare Sync Group (collega Azure File Share al server endpoint)
5. Configurare Cloud Tiering (es: mantieni ultimi 30 giorni localmente)

```bash
# Creare Storage Sync Service
az storagesync create \
  --resource-group $RG \
  --name myfilesyncsvc \
  --location westeurope

# Creare Sync Group
az storagesync sync-group create \
  --resource-group $RG \
  --storage-sync-service myfilesyncsvc \
  --name sync-group-prod

# Creare Cloud Endpoint (collega Azure File Share)
az storagesync sync-group cloud-endpoint create \
  --resource-group $RG \
  --storage-sync-service myfilesyncsvc \
  --sync-group-name sync-group-prod \
  --name cloud-endpoint \
  --storage-account-resource-id $(az storage account show --resource-group $RG --name $SA_NAME --query id -o tsv) \
  --azure-file-share-name myfileshare
```

## Managed Disks

I Managed Disks sono volumi di block storage per Azure VM, gestiti da Azure (no storage account da gestire manualmente).

### Tipi e Caratteristiche

| Tipo | IOPS/TB | MB/s/TB | Max IOPS | Max MB/s | Use Case |
|---|---|---|---|---|---|
| **Standard HDD** | 500 | 60 | 2000 | 500 | Dev/test, backup, archivio |
| **Standard SSD** | 750 | 100 | 6000 | 750 | Web server, light database |
| **Premium SSD v1** | 3000-7500 | 200-900 | 20000 | 900 | Database enterprise, workload I/O |
| **Premium SSD v2** | Configurabile | Configurabile | 80000 | 1200 | Database mission-critical, SAP, Redis |
| **Ultra Disk** | Configurabile | Configurabile | 160000 | 4000 | HPC, database ultra-performance |

```bash
# Creare disco Premium SSD v2 (IOPS/throughput configurabili indipendentemente dalla dimensione)
az disk create \
  --resource-group $RG \
  --name disk-db-data \
  --size-gb 1024 \
  --sku PremiumV2_LRS \
  --disk-iops-read-write 40000 \
  --disk-mbps-read-write 800 \
  --zone 1 \
  --location westeurope

# Creare Ultra Disk (richiede zona specifica)
az disk create \
  --resource-group $RG \
  --name disk-ultra-db \
  --size-gb 2048 \
  --sku UltraSSD_LRS \
  --disk-iops-read-write 80000 \
  --disk-mbps-read-write 2000 \
  --zone 1

# Allegare disco a VM esistente
az vm disk attach \
  --resource-group $RG \
  --vm-name myvm \
  --name disk-db-data \
  --caching None

# Detach disco
az vm disk detach \
  --resource-group $RG \
  --vm-name myvm \
  --name disk-db-data

# Snapshot incrementale
az snapshot create \
  --resource-group $RG \
  --name snap-disk-db-data-$(date +%Y%m%d) \
  --source $(az disk show --resource-group $RG --name disk-db-data --query id -o tsv) \
  --incremental true \
  --sku Standard_ZRS

# Creare disco da snapshot
az disk create \
  --resource-group $RG \
  --name disk-restored \
  --source $(az snapshot show --resource-group $RG --name snap-disk-db-data-20260226 --query id -o tsv)
```

### Disk Access (Private Endpoint per Export Disco)

Disk Access permette di esportare/importare dischi managed tramite Private Endpoint senza esporre i VHD a Internet.

```bash
# Creare Disk Access resource
az disk-access create \
  --resource-group $RG \
  --name diskaccess-prod \
  --location westeurope

# Associare il disco al Disk Access
az disk update \
  --resource-group $RG \
  --name disk-db-data \
  --disk-access $(az disk-access show --resource-group $RG --name diskaccess-prod --query id -o tsv) \
  --network-access-policy AllowPrivate

# Generare SAS per download sicuro (solo da VNet)
az disk grant-access \
  --resource-group $RG \
  --name disk-db-data \
  --duration-in-seconds 86400 \
  --access-level Read \
  --output tsv
```

## Queue Storage

Azure Queue Storage è un servizio di accodamento messaggi semplice per il disaccoppiamento di componenti applicativi. Simile ad Amazon SQS nella concettualità, ma più semplice.

Caratteristiche:
- Massimo 64 KB per messaggio
- Massimo 500 TB per queue (storage account standard)
- TTL default 7 giorni (configurabile fino a 7 giorni o -1 per infinito)
- Visibility timeout: un messaggio è invisibile dopo il get per N secondi (worker lock)
- At-least-once delivery (deduplication non garantita — idempotenza nel consumer)

```bash
# Creare una queue
az storage queue create \
  --account-name $SA_NAME \
  --name task-queue \
  --auth-mode login

# Inviare messaggio (base64 automatico con --encode true)
az storage message put \
  --account-name $SA_NAME \
  --queue-name task-queue \
  --content '{"task_id": "abc123", "action": "process_image", "file": "image.jpg"}' \
  --time-to-live 3600 \
  --auth-mode login

# Ricevere messaggio (rende invisibile per 300 secondi)
az storage message get \
  --account-name $SA_NAME \
  --queue-name task-queue \
  --visibility-timeout 300 \
  --num-messages 5 \
  --auth-mode login

# Eliminare messaggio dopo elaborazione (richiede pop-receipt dal get)
az storage message delete \
  --account-name $SA_NAME \
  --queue-name task-queue \
  --id MESSAGE_ID \
  --pop-receipt POP_RECEIPT \
  --auth-mode login

# Visualizzare dimensione queue
az storage queue show \
  --account-name $SA_NAME \
  --name task-queue \
  --output table \
  --auth-mode login
```

```python
# Uso da Python
from azure.storage.queue import QueueClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
queue_client = QueueClient(
    account_url=f"https://{STORAGE_ACCOUNT_NAME}.queue.core.windows.net",
    queue_name="task-queue",
    credential=credential
)

# Inviare messaggio
import json, base64
message = {"task_id": "abc123", "action": "process_image"}
queue_client.send_message(base64.b64encode(json.dumps(message).encode()).decode())

# Ricevere ed elaborare messaggi
messages = queue_client.receive_messages(messages_per_page=5, visibility_timeout=300)
for msg in messages:
    try:
        data = json.loads(base64.b64decode(msg.content).decode())
        process_task(data)
        queue_client.delete_message(msg)
    except Exception as e:
        # Non eliminare → riappare dopo visibility timeout
        logging.error(f"Failed to process message: {e}")
```

!!! tip "Queue Storage vs Service Bus"
    Queue Storage è sufficiente per scenari semplici di task queue. Usa Service Bus quando hai bisogno di: ordering garantito, dead-letter queue, sessioni, transazioni, messaggi >64KB, subscription pub/sub.

## Table Storage

Azure Table Storage è un NoSQL key-value store parte degli storage account. Ogni entità è identificata da PartitionKey + RowKey.

!!! note "Evoluzione verso Cosmos DB"
    Azure Table Storage è disponibile anche come "Azure Cosmos DB for Table" API, con performance migliori e distribuzione globale. Per nuovi progetti, valuta Cosmos DB for Table invece del Table Storage classico.

```bash
# Creare tabella
az storage table create \
  --account-name $SA_NAME \
  --name DeviceMetrics \
  --auth-mode login

# Inserire entità (PartitionKey = device_id, RowKey = timestamp)
az storage entity insert \
  --account-name $SA_NAME \
  --table-name DeviceMetrics \
  --entity \
    PartitionKey=device-001 \
    RowKey=2026-02-26T10:00:00 \
    Temperature=23.5 \
    Humidity=65 \
    Status=OK \
  --auth-mode login

# Query per PartitionKey
az storage entity query \
  --account-name $SA_NAME \
  --table-name DeviceMetrics \
  --filter "PartitionKey eq 'device-001'" \
  --output table \
  --auth-mode login
```

## Storage Firewall e Network Rules

Il Storage Firewall permette di limitare l'accesso allo storage account solo da reti specifiche.

```bash
# Impostare default action a Deny (nega tutto il traffico non esplicitamente permesso)
az storage account update \
  --resource-group $RG \
  --name $SA_NAME \
  --default-action Deny \
  --bypass AzureServices Logging Metrics

# Aggiungere subnet VNet specifica
az storage account network-rule add \
  --resource-group $RG \
  --account-name $SA_NAME \
  --vnet-name vnet-prod \
  --subnet snet-app

# Aggiungere IP pubblico specifico (es: office)
az storage account network-rule add \
  --resource-group $RG \
  --account-name $SA_NAME \
  --ip-address 203.0.113.0/24

# Listare regole correnti
az storage account network-rule list \
  --resource-group $RG \
  --account-name $SA_NAME \
  --output json

# Rimuovere regola
az storage account network-rule remove \
  --resource-group $RG \
  --account-name $SA_NAME \
  --ip-address 203.0.113.0/24
```

!!! warning "AzureServices Bypass"
    Il flag `--bypass AzureServices` è importante: permette a servizi Azure trusted (Azure Monitor, Azure Backup, ecc.) di accedere allo storage anche con firewall attivo. Senza questo, i backup automatici e i diagnostic logs smettono di funzionare.

## Customer-managed Keys (CMK)

Per default, Azure cripta i dati at-rest con chiavi gestite da Microsoft (SSE - Server-Side Encryption). Con CMK, le chiavi di crittografia sono nel tuo Key Vault e tu ne controlli il ciclo di vita.

```bash
# Pre-requisiti: Key Vault con soft-delete e purge-protection abilitati
az keyvault create \
  --resource-group $RG \
  --name mykeyvault-cmk \
  --enable-soft-delete true \
  --enable-purge-protection true

# Creare chiave RSA in Key Vault
az keyvault key create \
  --vault-name mykeyvault-cmk \
  --name storage-encryption-key \
  --kty RSA \
  --size 4096 \
  --ops encrypt decrypt wrapKey unwrapKey

# Assegnare Managed Identity allo storage account
az storage account update \
  --resource-group $RG \
  --name $SA_NAME \
  --assign-identity

# Ottenere principalId della Managed Identity dello storage account
STORAGE_MI=$(az storage account show \
  --resource-group $RG \
  --name $SA_NAME \
  --query identity.principalId -o tsv)

# Assegnare ruolo Key Vault Crypto Service Encryption User
az role assignment create \
  --assignee $STORAGE_MI \
  --role "Key Vault Crypto Service Encryption User" \
  --scope $(az keyvault show --name mykeyvault-cmk --query id -o tsv)

# Abilitare CMK sullo storage account
KEY_URI=$(az keyvault key show \
  --vault-name mykeyvault-cmk \
  --name storage-encryption-key \
  --query key.kid -o tsv)

az storage account update \
  --resource-group $RG \
  --name $SA_NAME \
  --encryption-key-source Microsoft.Keyvault \
  --encryption-key-uri $KEY_URI \
  --encryption-key-vault https://mykeyvault-cmk.vault.azure.net/ \
  --key-vault-user-identity $(az storage account show --resource-group $RG --name $SA_NAME --query identity.principalId -o tsv)
```

## Storage Access Keys: Rotation Best Practice

Lo storage account ha sempre 2 chiavi di accesso (key1 e key2) per permettere rotation senza downtime.

```bash
# Listare le chiavi
az storage account keys list \
  --resource-group $RG \
  --account-name $SA_NAME \
  --output table

# Procedura di rotation zero-downtime:
# 1. Aggiornare le applicazioni a usare key2
# 2. Ruotare key1 (invalida la vecchia key1, genera nuova)
az storage account keys renew \
  --resource-group $RG \
  --account-name $SA_NAME \
  --key key1

# 3. Aggiornare le applicazioni a usare la nuova key1
# 4. Ruotare key2
az storage account keys renew \
  --resource-group $RG \
  --account-name $SA_NAME \
  --key key2
```

!!! tip "Key Vault Reference per Connection String"
    Memorizza la connection string dello storage in Key Vault e usa Key Vault References nelle App Service/Functions. Quando ruoti la chiave e aggiorni il segreto in Key Vault, le applicazioni ricevono automaticamente la nuova connection string senza redeploy.

## Diagnostics e Monitoring

```bash
# Abilitare diagnostics log e metriche per lo storage account
az monitor diagnostic-settings create \
  --resource-group $RG \
  --resource $SA_NAME \
  --resource-type Microsoft.Storage/storageAccounts \
  --name diag-storage-prod \
  --workspace $(az monitor log-analytics workspace show --resource-group rg-monitoring --workspace-name law-prod --query id -o tsv) \
  --logs '[
    {"category": "StorageRead", "enabled": true},
    {"category": "StorageWrite", "enabled": true},
    {"category": "StorageDelete", "enabled": true}
  ]' \
  --metrics '[{"category": "Transaction", "enabled": true}, {"category": "Capacity", "enabled": true}]'
```

Query KQL utili per analisi storage:

```kql
// Top 10 operazioni per volume di transazioni
StorageBlobLogs
| where TimeGenerated > ago(1h)
| summarize Count=count() by OperationName
| order by Count desc
| take 10

// Errori di autenticazione
StorageBlobLogs
| where TimeGenerated > ago(24h)
| where StatusCode >= 400 and StatusCode < 500
| project TimeGenerated, CallerIpAddress, AuthenticationType, StatusText, Uri
| order by TimeGenerated desc
```

## Best Practices

- Usa sempre **Private Endpoint** invece di Service Endpoint per isolamento rete completo
- Abilita **Soft Delete** per file share e blob (protezione contro eliminazione accidentale)
- Per Managed Disks in produzione, usa sempre **Premium SSD v1** minimo, **Premium SSD v2** per database
- Imposta `--caching None` per dischi database (data files) e `ReadOnly` per OS disk
- Usa **Disk Access** con Private Endpoint per esportare dischi sicuramente senza esposizione Internet
- Per Queue Storage, implementa sempre logica di idempotenza nel consumer (at-least-once delivery)

## Riferimenti

- [Documentazione Azure Files](https://learn.microsoft.com/azure/storage/files/)
- [Azure File Sync](https://learn.microsoft.com/azure/storage/file-sync/file-sync-introduction)
- [Managed Disks Overview](https://learn.microsoft.com/azure/virtual-machines/managed-disks-overview)
- [Premium SSD v2](https://learn.microsoft.com/azure/virtual-machines/disks-types#premium-ssd-v2)
- [Queue Storage Documentation](https://learn.microsoft.com/azure/storage/queues/)
- [Storage Security Guide](https://learn.microsoft.com/azure/storage/common/storage-security-guide)
- [Customer-managed Keys](https://learn.microsoft.com/azure/storage/common/customer-managed-keys-overview)
