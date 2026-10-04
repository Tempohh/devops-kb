---
title: "Azure Storage Avanzato"
slug: storage-avanzato
category: cloud
tags: [azure, azure-files, managed-disks, table-storage, queue-storage, nfs, smb]
search_keywords: [Azure Files SMB NFS, Azure File Sync, Premium File Shares SSD, Managed Disks Premium SSD Ultra Disk, Queue Storage message queue, Table Storage NoSQL key-value, storage firewall network rules, customer-managed keys CMK, storage access keys rotation, Azure File Sync hybrid cloud]
parent: cloud/azure/storage/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/security/key-vault, cloud/azure/compute/aks-containers]
official_docs: https://learn.microsoft.com/azure/storage/files/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Storage Avanzato

## Panoramica

Oltre a Blob Storage, Azure offre servizi storage specializzati per scenari specifici: condivisione file (Azure Files), block storage per VM (Managed Disks), messaggi leggeri (Queue Storage) e dati strutturati chiave-valore (Table Storage). Questo documento copre anche le funzionalità avanzate di sicurezza come storage firewall e Customer-managed Keys.

## Azure Files

Azure Files offre file share gestiti nel cloud accessibili via protocollo SMB (3.x) e NFS 4.1. Può sostituire server NAS on-premises e si monta su Windows, Linux e macOS (NFS solo Linux).

### Tipi di File Share

| Tipo | Protocollo | Redundancy | IOPS Max (per share) | Use Case |
|---|---|---|---|---|
| **Standard** (HDD) | solo SMB (e REST) | LRS/ZRS/GRS/GZRS | ~20.000 | Home directory, dev/test, archivi |
| **Premium** (SSD, `FileStorage`) | SMB, NFS | LRS/ZRS | ~100.000 | Database file, ERP, workload I/O intensivi |

!!! warning "NFS solo su Premium"
    NFS 4.1 richiede uno storage account `FileStorage` Premium. NFS non supporta cifratura in transito né autenticazione utente: l'accesso va limitato con Private Endpoint o Service Endpoint (rete come unico perimetro) e `secure transfer required` va disabilitato sull'account.

```bash
RG="rg-storage-prod"
SA_NAME="mystorageaccount2026"

# Creare file share SMB Standard
az storage share-rm create \
  --resource-group $RG \
  --storage-account $SA_NAME \
  --name myfileshare \
  --quota 1024

# Creare file share NFS (richiede Premium tier storage account)
az storage account create \
  --resource-group $RG \
  --name mypremiumnfs2026 \
  --location westeurope \
  --sku Premium_LRS \
  --kind FileStorage \
  --https-only false  # obbligatorio per NFS: niente encryption in transit, proteggere via rete

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

# Mount persistente in /etc/fstab: credenziali in file dedicato (non in chiaro in fstab)
sudo mkdir -p /etc/smbcredentials
printf "username=%s\npassword=%s\n" "$SA_NAME" "$STORAGE_KEY" | sudo tee /etc/smbcredentials/$SA_NAME.cred > /dev/null
sudo chmod 600 /etc/smbcredentials/$SA_NAME.cred
echo "//$SA_NAME.file.core.windows.net/myfileshare /mnt/azurefiles cifs nofail,vers=3.0,credentials=/etc/smbcredentials/$SA_NAME.cred,dir_mode=0770,file_mode=0660,serverino 0 0" | sudo tee -a /etc/fstab
```

!!! warning "Permessi e chiave"
    `0777` espone i file a ogni utente locale e la storage key dà accesso completo all'account: in produzione preferisci autenticazione identity-based (Microsoft Entra Kerberos / AD DS) e permessi restrittivi.

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
│   ├── Hot files → contenuto completo in locale
│   └── Cold files → solo stub (reparse point), contenuto su Azure Files
│
Azure Files (cloud share completo)
│   └── Tutti i file (hot + cold)
```

Architettura installazione:
1. Creare Storage Sync Service su Azure
2. Installare agente File Sync su Windows Server
3. Registrare il server nel Storage Sync Service
4. Creare Sync Group (collega Azure File Share al server endpoint)
5. Creare il Server Endpoint e configurare Cloud Tiering (policy *volume free space* e/o *date*, es: tieni in locale solo i file acceduti negli ultimi 30 giorni)

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
  --storage-account $(az storage account show --resource-group $RG --name $SA_NAME --query id -o tsv) \
  --storage-account-tenant-id $(az account show --query tenantId -o tsv) \
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
| **Ultra Disk** | Configurabile | Configurabile | 400000 | 10000 | HPC, database ultra-performance |

!!! note "Limiti indicativi"
    I massimi dipendono da dimensione disco e dalla size della VM (che ha propri cap di IOPS/throughput): verifica la pagina *Disk types* prima di dimensionare. Premium SSD v2 e Ultra Disk non supportano host caching.

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

# Creare Ultra Disk (richiede zona specifica; la VM deve essere creata/aggiornata con --ultra-ssd-enabled true nella stessa zona)
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
- Capacità totale limitata dal solo storage account (500 TiB), non da un tetto per queue
- TTL default 7 giorni (configurabile a qualsiasi valore positivo, oppure -1 per nessuna scadenza)
- Visibility timeout: un messaggio è invisibile dopo il get per N secondi (worker lock)
- At-least-once delivery (deduplication non garantita — idempotenza nel consumer)

```bash
# Creare una queue
az storage queue create \
  --account-name $SA_NAME \
  --name task-queue \
  --auth-mode login

# Inviare messaggio (il contenuto è testo; se il consumer si aspetta base64, codificalo prima)
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

# Aggiungere subnet VNet specifica (richiede Service Endpoint Microsoft.Storage sulla subnet)
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
  --enable-purge-protection true  # soft-delete è sempre attivo sui nuovi vault

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
  --assignee-object-id $STORAGE_MI \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Crypto Service Encryption User" \
  --scope $(az keyvault show --name mykeyvault-cmk --query id -o tsv)

# Abilitare CMK sullo storage account (identità system-assigned: nessun identity id da passare)
# Senza --encryption-key-version Storage usa sempre l'ultima versione (auto-rotation della chiave)
az storage account update \
  --resource-group $RG \
  --name $SA_NAME \
  --encryption-key-source Microsoft.Keyvault \
  --encryption-key-vault https://mykeyvault-cmk.vault.azure.net/ \
  --encryption-key-name storage-encryption-key
```

!!! note "User-assigned identity"
    Con una user-assigned managed identity aggiungi `--key-vault-user-identity-id <resourceId dell'identità>`. È utile per assegnare il ruolo sul Key Vault *prima* di creare l'account.

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
    Memorizza la connection string dello storage in Key Vault e usa Key Vault References (senza versione) nelle App Service/Functions. Quando aggiorni il segreto dopo la rotation, le app lo rileggono entro circa 24 ore senza redeploy (per applicarlo subito, riavvia l'app o aggiorna il riferimento).

!!! tip "Meglio: niente chiavi"
    Il rimedio più forte alla rotation è eliminare le chiavi: usa Microsoft Entra ID con RBAC (`Storage Blob Data Contributor`, `Storage Queue Data Contributor`, ecc.) e imposta `--allow-shared-key-access false` sull'account. Imposta anche una *key expiration policy* per avere alert di rotation.

## Diagnostics e Monitoring

```bash
# I log (StorageRead/Write/Delete) si configurano per servizio (blob, file, queue, table),
# non sulla risorsa account: qui il servizio blob. Metriche: stesso resource ID del servizio.
SA_ID=$(az storage account show --resource-group $RG --name $SA_NAME --query id -o tsv)

az monitor diagnostic-settings create \
  --resource "$SA_ID/blobServices/default" \
  --name diag-storage-prod \
  --workspace $(az monitor log-analytics workspace show --resource-group rg-monitoring --workspace-name law-prod --query id -o tsv) \
  --logs '[
    {"category": "StorageRead", "enabled": true},
    {"category": "StorageWrite", "enabled": true},
    {"category": "StorageDelete", "enabled": true}
  ]' \
  --metrics '[{"category": "Transaction", "enabled": true}]'
```

Ripeti con `fileServices/default`, `queueServices/default`, `tableServices/default` per gli altri servizi (in quel caso le tabelle KQL sono `StorageFileLogs`, `StorageQueueLogs`, `StorageTableLogs`).

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

## Troubleshooting

### Scenario 1 — Mount SMB fallisce con errore 13 (Permission Denied) o 115

**Sintomo:** `mount -t cifs` ritorna `mount error(13): Permission denied` oppure `mount error(115): Operation now in progress`.

**Causa:** La porta 445 (SMB) è bloccata dall'ISP o dal firewall. Oppure le credenziali (storage key) non sono corrette.

**Soluzione:** Verificare connettività porta 445 e le credenziali.

```bash
# Verificare se la porta 445 è raggiungibile
nc -zv mystorageaccount2026.file.core.windows.net 445

# Verificare che la storage key sia corretta
az storage account keys list \
  --resource-group $RG \
  --account-name $SA_NAME \
  --query "[0].value" -o tsv

# Se la porta è bloccata, usare VPN (P2S/S2S) / ExpressRoute con Private Endpoint, o Azure File Sync come alternativa
# Verificare che il servizio sia abilitato per il protocollo SMB
az storage account show \
  --resource-group $RG \
  --name $SA_NAME \
  --query "primaryEndpoints.file"
```

### Scenario 2 — Storage Firewall blocca accessi imprevisti dopo abilitazione

**Sintomo:** Dopo aver impostato `--default-action Deny`, Azure Monitor smette di ricevere log, i backup automatici falliscono, o le Azure Functions non riescono ad accedere allo storage.

**Causa:** Il flag `--bypass AzureServices` non è stato incluso, oppure la subnet della risorsa non è stata aggiunta alle network rules.

**Soluzione:** Aggiungere il bypass per i servizi Azure trusted e/o la subnet mancante.

```bash
# Aggiornare il firewall per includere il bypass AzureServices
az storage account update \
  --resource-group $RG \
  --name $SA_NAME \
  --default-action Deny \
  --bypass AzureServices Logging Metrics

# Verificare le regole attuali
az storage account network-rule list \
  --resource-group $RG \
  --account-name $SA_NAME \
  --output json

# Aggiungere la subnet mancante (es: subnet dove gira App Service/Functions)
az storage account network-rule add \
  --resource-group $RG \
  --account-name $SA_NAME \
  --vnet-name vnet-prod \
  --subnet snet-functions
```

### Scenario 3 — CMK: crittografia non si abilita, errore "Key Vault key not found" o accesso negato

**Sintomo:** Il comando `az storage account update --encryption-key-source Microsoft.Keyvault` fallisce con `KeyVaultKeyNotFound` o `AuthorizationFailed`.

**Causa:** La Managed Identity dello storage account non ha il ruolo corretto sul Key Vault, oppure soft-delete/purge-protection non sono abilitati sul Key Vault.

**Soluzione:** Verificare i permessi della Managed Identity e i prerequisiti del Key Vault.

```bash
# Verificare che soft-delete e purge-protection siano abilitati
az keyvault show \
  --name mykeyvault-cmk \
  --query "{softDelete:properties.enableSoftDelete, purgeProtection:properties.enablePurgeProtection}"

# Verificare che la Managed Identity esista sullo storage account
az storage account show \
  --resource-group $RG \
  --name $SA_NAME \
  --query "identity"

# Riassegnare il ruolo se mancante
STORAGE_MI=$(az storage account show --resource-group $RG --name $SA_NAME --query identity.principalId -o tsv)
az role assignment create \
  --assignee-object-id $STORAGE_MI \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Crypto Service Encryption User" \
  --scope $(az keyvault show --name mykeyvault-cmk --query id -o tsv)

# Verificare che la chiave sia nello stato "Enabled"
az keyvault key show \
  --vault-name mykeyvault-cmk \
  --name storage-encryption-key \
  --query "attributes.enabled"
```

### Scenario 4 — Queue Storage: messaggi rimangono in coda indefinitamente (poison messages)

**Sintomo:** Alcuni messaggi nella queue non vengono mai elaborati e continuano a riapparire dopo il visibility timeout, causando retry loop infiniti.

**Causa:** Il consumer lancia un'eccezione durante l'elaborazione, non elimina il messaggio, e non gestisce i messaggi "velenosi" (poison messages) che superano un certo numero di tentativi.

**Soluzione:** Implementare un contatore di tentativi e spostare i messaggi problematici in una dead-letter queue separata.

```python
from azure.storage.queue import QueueClient
from azure.identity import DefaultAzureCredential
import json, base64, logging

credential = DefaultAzureCredential()
queue_client = QueueClient(
    account_url=f"https://{STORAGE_ACCOUNT_NAME}.queue.core.windows.net",
    queue_name="task-queue",
    credential=credential
)
dlq_client = QueueClient(
    account_url=f"https://{STORAGE_ACCOUNT_NAME}.queue.core.windows.net",
    queue_name="task-queue-dlq",
    credential=credential
)

MAX_RETRIES = 5

messages = queue_client.receive_messages(visibility_timeout=60)
for msg in messages:
    # dequeue_count > MAX_RETRIES → spostare in DLQ
    if msg.dequeue_count > MAX_RETRIES:
        dlq_client.send_message(msg.content)
        queue_client.delete_message(msg)
        logging.warning(f"Poison message moved to DLQ: {msg.id}")
        continue
    try:
        data = json.loads(base64.b64decode(msg.content).decode())
        process_task(data)
        queue_client.delete_message(msg)
    except Exception as e:
        logging.error(f"Attempt {msg.dequeue_count}/{MAX_RETRIES} failed: {e}")
        # Non eliminare → riapparirà dopo visibility timeout
```

```bash
# Verificare messaggi in coda e stimare messaggi bloccati
az storage queue show \
  --account-name $SA_NAME \
  --name task-queue \
  --auth-mode login

# Controllare se la DLQ esiste, crearla se necessario
az storage queue create \
  --account-name $SA_NAME \
  --name task-queue-dlq \
  --auth-mode login
```

!!! note "Poison queue con Azure Functions"
    Queue Storage non ha una DLQ nativa (a differenza di Service Bus). Il trigger queue di Azure Functions però sposta da solo i messaggi dopo 5 tentativi (`maxDequeueCount`) in una queue `<nome>-poison`: il codice sopra serve per consumer custom.

## Best Practices

- Usa sempre **Private Endpoint** invece di Service Endpoint per isolamento rete completo
- Abilita **Soft Delete** per file share e blob (protezione contro eliminazione accidentale)
- Per Managed Disks in produzione, usa sempre **Premium SSD v1** minimo, **Premium SSD v2** per database
- Host caching (solo Premium SSD v1/Standard): `ReadWrite` di default per OS disk; `ReadOnly` per data disk con carichi read-heavy (es. data file SQL Server); `None` per log file e dischi write-heavy
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
