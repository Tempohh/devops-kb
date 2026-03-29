---
title: "Azure Event Hubs"
slug: event-hubs
category: cloud
tags: [azure, event-hubs, kafka, streaming, partitions, consumer-group, capture, stream-analytics]
search_keywords: [Azure Event Hubs, Kafka Azure, streaming Azure, partition Event Hubs, consumer group Event Hubs, Event Hubs Capture, Avro, Azure Stream Analytics, Kinesis Azure equivalent, event streaming, telemetria IoT, clickstream, high throughput messaging, Event Hubs namespace, throughput units, processing units, Event Hubs Dedicated, Schema Registry, AMQP Kafka HTTPS]
parent: cloud/azure/messaging/_index
related: [cloud/azure/messaging/service-bus-event-grid, cloud/azure/storage/blob-storage, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/event-hubs/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Azure Event Hubs

**Azure Event Hubs** è il servizio di **streaming ad alto volume** di Azure — gestisce milioni di eventi al secondo con latenza sub-secondo. È l'equivalente di Apache Kafka (e ha un'API Kafka nativa compatibile).

## Architettura Event Hubs

```
Producers                     Event Hubs Namespace            Consumers
─────────                     ─────────────────────           ─────────
App Servers ─────────────────► Event Hub                     Consumer Group 1 (analytics)
IoT Devices ─────────────────►   Partition 0 ────────────────► Consumer Group 2 (archivio)
Web Logs ────────────────────►   Partition 1 ────────────────► Consumer Group 3 (alerts)
Kafka clients ───────────────►   Partition 2
                              │   Partition N
                              │
                              └── Event Hubs Capture → Blob Storage (Avro)
```

**Concetti chiave:**
- **Namespace:** contenitore di Event Hub, URL di connessione
- **Event Hub:** equivalente a un topic Kafka
- **Partition:** unità di parallelismo e ordinamento (1-2048); `partition_key → hash → partition`
- **Consumer Group:** reader indipendenti sullo stesso stream (equivalente a Kafka consumer group)
- **Retention:** 1 giorno (Basic), fino a 90 giorni (Standard/Premium), 7 giorni default
- **Throughput Unit (TU):** unità capacità per Standard — 1 TU = 1 MB/s ingress, 2 MB/s egress

---

## SKU Event Hubs

| | Basic | Standard | Premium | Dedicated |
|---|-------|----------|---------|-----------|
| Consumer Groups | 1 | 20 | 100 | illimitati |
| Retention max | 1 giorno | 7 giorni | 90 giorni | 90 giorni |
| Message size | 256 KB | 1 MB | 1 MB | 1 MB |
| Throughput | TU (manual) | TU (manual) | PU (auto) | CU (dedicated) |
| Kafka API | No | Sì | Sì | Sì |
| Capture | No | Sì | Sì | Sì |
| Schema Registry | No | No | Sì | Sì |
| Private Endpoint | No | Sì | Sì | Sì |
| Prezzo | ~$0.015/M events | ~$0.10/M events + TU | ~$750/mese | ~$65000/mese (10 CU) |

---

## Creare Namespace e Event Hub

```bash
# Creare Namespace Standard
az eventhubs namespace create \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --sku Standard \
    --location italynorth \
    --capacity 2 \                          # Throughput Units: 1-20 (auto-inflate opzionale)
    --enable-auto-inflate true \
    --maximum-throughput-units 10 \         # auto-scale fino a 10 TU
    --minimum-tls-version 1.2

# Creare Event Hub
az eventhubs eventhub create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name app-events \
    --partition-count 8 \                   # fisso — scegliere con cura (max throughput = partitions × 1MB/s)
    --message-retention 7 \                 # giorni
    --cleanup-policy Delete                 # Delete (standard) o Compact (solo ultima versione per key)

# Creare Consumer Group
az eventhubs eventhub consumer-group create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --eventhub-name app-events \
    --name analytics-consumer

az eventhubs eventhub consumer-group create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --eventhub-name app-events \
    --name archival-consumer

# RBAC: concedere accesso a Managed Identity
az role assignment create \
    --assignee-object-id $MANAGED_IDENTITY_PRINCIPAL_ID \
    --assignee-principal-type ServicePrincipal \
    --role "Azure Event Hubs Data Sender" \           # Data Sender o Data Receiver o Data Owner
    --scope /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.EventHub/namespaces/myapp-eventhubs/eventhubs/app-events
```

---

## Produrre e Consumare Eventi — Python SDK

### Producer

```python
# pip install azure-eventhub azure-identity

import asyncio
import json
from azure.eventhub.aio import EventHubProducerClient
from azure.eventhub import EventData
from azure.identity.aio import DefaultAzureCredential

NAMESPACE = "myapp-eventhubs.servicebus.windows.net"
EVENTHUB = "app-events"

async def send_events(events: list[dict]):
    credential = DefaultAzureCredential()
    async with EventHubProducerClient(NAMESPACE, EVENTHUB, credential) as producer:
        # Batch per efficienza (auto-size rispetta il limite 1MB)
        async with producer.create_batch() as batch:
            for event in events:
                event_data = EventData(
                    body=json.dumps(event).encode('utf-8')
                )
                # partition_key: eventi con stesso key vanno nella stessa partition (ordinamento)
                # Se omesso: distribuzione round-robin tra partitions
                try:
                    batch.add(event_data)
                except ValueError:
                    # Batch pieno: invia e ricrea
                    await producer.send_batch(batch)
                    async with producer.create_batch() as batch:
                        batch.add(event_data)

            await producer.send_batch(batch)

# Usare con partition key
async def send_with_partition_key(user_events: list[dict]):
    credential = DefaultAzureCredential()
    async with EventHubProducerClient(NAMESPACE, EVENTHUB, credential) as producer:
        # Tutti gli eventi dello stesso user_id vanno nella stessa partition
        for event in user_events:
            partition_key = f"user-{event['userId']}"
            async with producer.create_batch(partition_key=partition_key) as batch:
                batch.add(EventData(json.dumps(event).encode('utf-8')))
            await producer.send_batch(batch)

asyncio.run(send_events([
    {"type": "page.view", "userId": "u1", "url": "/products"},
    {"type": "click", "userId": "u2", "element": "buy-button"},
]))
```

### Consumer con Checkpoint Store

```python
# Checkpoint store su Blob Storage — mantiene offset per ogni partition
# pip install azure-eventhub-checkpointstoreblob-aio

import asyncio
import json
from azure.eventhub.aio import EventHubConsumerClient
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import ContainerClient

NAMESPACE = "myapp-eventhubs.servicebus.windows.net"
EVENTHUB = "app-events"
CONSUMER_GROUP = "analytics-consumer"
STORAGE_ACCOUNT = "https://mystorageaccount.blob.core.windows.net"
CONTAINER = "event-checkpoints"

async def process_event(partition_context, event):
    """Callback per ogni evento ricevuto."""
    try:
        data = json.loads(event.body_as_str())
        print(f"Partition: {partition_context.partition_id}, "
              f"Offset: {event.offset}, "
              f"Event: {data}")

        # Processa evento
        await handle_event(data)

        # Checkpoint: salva l'offset corrente (fault tolerance)
        # Il consumer ripartirà da qui in caso di restart
        await partition_context.update_checkpoint(event)

    except Exception as e:
        print(f"Error processing event: {e}")
        # Non aggiornare checkpoint → l'evento sarà riprocessato

async def main():
    credential = DefaultAzureCredential()

    # Checkpoint store su Blob Storage
    checkpoint_store = BlobCheckpointStore(
        blob_account_url=STORAGE_ACCOUNT,
        container_name=CONTAINER,
        credential=credential
    )

    async with EventHubConsumerClient(
        NAMESPACE, EVENTHUB, CONSUMER_GROUP,
        credential=credential,
        checkpoint_store=checkpoint_store,
        # Iniziare dall'inizio o dall'ultimo checkpoint
        # initial_event_position: "@latest" (default) o "@earliest" o specifico offset
    ) as consumer:
        print(f"Listening on {EVENTHUB}...")
        await consumer.receive(
            on_event=process_event,
            max_wait_time=5,        # secondi prima di callback con event=None
            starting_position="@latest"   # solo nuovi eventi
        )

asyncio.run(main())
```

---

## Event Hubs Capture

**Capture** archivia automaticamente gli eventi su **Blob Storage** o **Data Lake Gen2** in formato **Avro** — utile per data lake, auditing, replay:

```bash
# Abilitare Capture su Event Hub esistente
az eventhubs eventhub update \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name app-events \
    --enable-capture true \
    --capture-interval 300 \                    # secondi (60-900): flush ogni 5 minuti
    --capture-size-limit 314572800 \            # bytes (10MB-524MB): flush quando raggiunge 300MB
    --destination-name EventHubArchive \
    --storage-account /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount \
    --blob-container eventhubs-capture \
    --archive-name-format "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}"
    # Formato path: myapp-eventhubs/app-events/0/2026/02/26/14/30/00.avro

# Leggere file Avro catturati
# pip install fastavro
import fastavro
import json

def read_capture_file(avro_file_path: str):
    with open(avro_file_path, 'rb') as f:
        reader = fastavro.reader(f)
        for record in reader:
            # Il payload è nel campo 'Body' come bytes
            body = json.loads(record['Body'].decode('utf-8'))
            print(f"Offset: {record['Offset']}, "
                  f"SequenceNumber: {record['SequenceNumber']}, "
                  f"EnqueuedTimeUtc: {record['EnqueuedTimeUtc']}, "
                  f"Body: {body}")
```

**Path pattern utili:**
- `{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}` — partizionamento temporale
- `{Namespace}/{EventHub}/{Year}/{Month}/{Day}` — raggruppamento giornaliero (tutti i partition nella stessa cartella)

---

## API Kafka — Compatibilità Nativa

Event Hubs Standard/Premium espone un'endpoint **Kafka-compatible** — il codice Kafka esistente funziona senza modifiche applicative:

```python
# Producer Kafka che scrive su Event Hubs
from kafka import KafkaProducer
import json
import ssl

# Event Hubs Kafka endpoint: namespace.servicebus.windows.net:9093
producer = KafkaProducer(
    bootstrap_servers='myapp-eventhubs.servicebus.windows.net:9093',
    security_protocol='SASL_SSL',
    sasl_mechanism='PLAIN',
    sasl_plain_username='$ConnectionString',
    sasl_plain_password='Endpoint=sb://myapp-eventhubs.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=...',
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    ssl_context=ssl.create_default_context()
)

# Topic Kafka = Event Hub name
producer.send('app-events', value={'type': 'page.view', 'userId': 'u1'})
producer.flush()
```

```properties
# Consumer Kafka (properties file — es. Kafka Streams, Connect)
bootstrap.servers=myapp-eventhubs.servicebus.windows.net:9093
security.protocol=SASL_SSL
sasl.mechanism=PLAIN
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required \
    username="$ConnectionString" \
    password="Endpoint=sb://myapp-eventhubs...";
group.id=my-consumer-group
auto.offset.reset=latest
```

**Limitazioni API Kafka su Event Hubs:**
- No Kafka Transactions
- No Kafka Streams (usa Azure Stream Analytics)
- No topic auto-creation (crea Event Hub prima)
- Consumer group = Event Hubs Consumer Group (limite per SKU)

---

## Azure Stream Analytics

**Azure Stream Analytics** è il servizio di stream processing managed per event in tempo reale — usa SQL-like query su dati in streaming:

```bash
# Creare Stream Analytics Job
az stream-analytics job create \
    --resource-group myapp-rg \
    --job-name clickstream-processor \
    --location italynorth \
    --output-error-policy Drop \
    --sku Standard

# Aggiungere input (Event Hubs)
az stream-analytics input create \
    --resource-group myapp-rg \
    --job-name clickstream-processor \
    --input-name eventhubs-input \
    --type Stream \
    --datasource '{
        "type": "Microsoft.ServiceBus/EventHub",
        "properties": {
            "eventHubName": "app-events",
            "serviceBusNamespace": "myapp-eventhubs",
            "authenticationMode": "Msi"
        }
    }' \
    --serialization '{"type": "Json", "properties": {"encoding": "UTF8"}}'

# Aggiungere output (Blob Storage per data lake)
az stream-analytics output create \
    --resource-group myapp-rg \
    --job-name clickstream-processor \
    --output-name blob-output \
    --datasource '{
        "type": "Microsoft.Storage/Blob",
        "properties": {
            "storageAccounts": [{"accountName": "mystorageaccount"}],
            "container": "stream-output",
            "pathPattern": "clickstream/{date}/{time}",
            "dateFormat": "yyyy/MM/dd",
            "timeFormat": "HH",
            "authenticationMode": "Msi"
        }
    }' \
    --serialization '{"type": "Json"}'

# Definire la trasformazione (query SQL)
az stream-analytics transformation create \
    --resource-group myapp-rg \
    --job-name clickstream-processor \
    --transformation-name main-query \
    --streaming-units 3 \
    --saql "
        SELECT
            userId,
            url,
            COUNT(*) AS pageviews,
            AVG(duration) AS avgDuration,
            System.Timestamp() AS windowEnd
        INTO [blob-output]
        FROM [eventhubs-input] TIMESTAMP BY eventTime
        GROUP BY
            userId,
            url,
            TumblingWindow(minute, 5)       -- finestra aggregazione 5 minuti
        HAVING COUNT(*) > 1

        -- Seconda query: alert su errori
        SELECT *
        INTO [alerting-output]
        FROM [eventhubs-input]
        WHERE eventType = 'error'
            AND severity = 'CRITICAL'
    "

# Avviare job
az stream-analytics job start \
    --resource-group myapp-rg \
    --job-name clickstream-processor \
    --output-start-mode JobStartTime
```

### Pattern di Windowing ASA

```sql
-- Tumbling Window: finestre non sovrapposte (5 min ogni 5 min)
GROUP BY TumblingWindow(minute, 5)

-- Hopping Window: finestre sovrapposte (5 min ogni 1 min)
GROUP BY HoppingWindow(minute, 5, 1)

-- Sliding Window: si attiva ad ogni evento (continuous)
GROUP BY SlidingWindow(minute, 5)

-- Session Window: raggruppa eventi vicini temporalmente
GROUP BY SessionWindow(minute, 1, 10)   -- gap 1min, max 10min

-- DATEDIFF: join temporale tra stream
SELECT a.*, b.productName
FROM clickstream a TIMESTAMP BY eventTime
JOIN productcatalog b TIMESTAMP BY updateTime
    ON a.productId = b.id
    AND DATEDIFF(minute, a, b) BETWEEN 0 AND 10
```

---

## Event Hubs Schema Registry

Lo **Schema Registry** (Premium/Dedicated) valida e versiona schema Avro o JSON Schema:

```bash
# Creare Schema Group
az eventhubs namespace schema-registry create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name orders-schemas \
    --schema-compatibility Forward \    # None, Backward, Forward
    --schema-type Avro

# Registrare schema
az eventhubs namespace schema-registry schema create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --schema-registry-name orders-schemas \
    --schema-name order-event \
    --schema-definition '{
        "type": "record",
        "name": "OrderEvent",
        "fields": [
            {"name": "orderId", "type": "string"},
            {"name": "amount", "type": "double"},
            {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"}
        ]
    }'
```

---

## Confronto Finale

```
Hai bisogno di...

Alta performance streaming (milioni eventi/sec)?
  └── Event Hubs

Kafka workload esistente su Azure?
  └── Event Hubs (Kafka API)

Archivio automatico su Data Lake?
  └── Event Hubs + Capture

Stream processing real-time?
  └── Event Hubs → Azure Stream Analytics

Enterprise messaging con ordering/transazioni?
  └── Service Bus

Event routing da servizi Azure (Blob, VM, AKS)?
  └── Event Grid System Topic

Event routing custom con filtri avanzati?
  └── Event Grid Custom Topic

Simple background queue low-cost?
  └── Storage Queue
```

---

## Troubleshooting

### Scenario 1 — Throughput Units esauriti (ingress throttling)

**Sintomo:** Il producer riceve errori `ServerBusy` o `QuotaExceededException`; i messaggi vengono rifiutati o ritardati.

**Causa:** Il namespace Standard ha raggiunto il limite di TU configurati (1 TU = 1 MB/s ingress). Se auto-inflate non è abilitato, il traffico in eccesso viene throttled.

**Soluzione:** Abilitare auto-inflate o aumentare manualmente i TU; monitorare la metrica `ThrottledRequests`.

```bash
# Verificare TU attuali e abilitare auto-inflate
az eventhubs namespace show \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --query "{sku:sku.capacity, autoInflate:isAutoInflateEnabled, maxTU:maximumThroughputUnits}"

# Aumentare TU manualmente
az eventhubs namespace update \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --capacity 10

# Abilitare auto-inflate
az eventhubs namespace update \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --enable-auto-inflate true \
    --maximum-throughput-units 20

# Monitorare throttling (ultimi 30 minuti)
az monitor metrics list \
    --resource /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.EventHub/namespaces/myapp-eventhubs \
    --metric ThrottledRequests \
    --interval PT1M \
    --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%MZ)
```

---

### Scenario 2 — Consumer non avanza (offset bloccato)

**Sintomo:** Il consumer group non processa nuovi eventi; la metrica `IncomingMessages` cresce ma `OutgoingMessages` è piatta. Il lag aumenta continuamente.

**Causa:** Il checkpoint store (Blob Storage) non viene aggiornato (eccezione silenziata nel callback `on_event`), oppure un singolo consumer detiene una partition ma non la processa (crash senza rilascio).

**Soluzione:** Verificare i checkpoint nel Blob container, forzare il rilascio delle partition resettando il consumer group, o eliminare e ricreare il checkpoint.

```bash
# Vedere checkpoint nel Blob container (ogni partition ha un file)
az storage blob list \
    --account-name mystorageaccount \
    --container-name event-checkpoints \
    --prefix "myapp-eventhubs/app-events/analytics-consumer/" \
    --output table

# Eliminare checkpoint per ripartire dall'inizio (ATTENZIONE: replay tutti gli eventi in retention)
az storage blob delete-batch \
    --account-name mystorageaccount \
    --source event-checkpoints \
    --pattern "myapp-eventhubs/app-events/analytics-consumer/*"

# Verificare lag per consumer group tramite metrica IncomingMessages vs OutgoingMessages
az monitor metrics list \
    --resource /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.EventHub/namespaces/myapp-eventhubs/eventhubs/app-events \
    --metric IncomingMessages,OutgoingMessages \
    --interval PT5M
```

---

### Scenario 3 — Kafka client non riesce a connettersi

**Sintomo:** Il Kafka producer/consumer riceve `SASL authentication failed` o `Connection refused` quando usa l'endpoint Kafka di Event Hubs.

**Causa:** Le cause più comuni sono: (1) SKU Basic (non supporta Kafka), (2) connection string errata o scaduta nella password SASL, (3) porta 9093 bloccata dal firewall, (4) `group.id` non corrisponde a un Consumer Group esistente.

**Soluzione:** Verificare lo SKU, rigenerare le chiavi SAS se necessario, e creare esplicitamente il Consumer Group prima di avviare il consumer.

```bash
# Verificare SKU (deve essere Standard, Premium o Dedicated per Kafka)
az eventhubs namespace show \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --query "sku.name"

# Rigenerare chiave SAS primaria
az eventhubs namespace authorization-rule keys renew \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name RootManageSharedAccessKey \
    --key PrimaryKey \
    --query primaryConnectionString

# Verificare connettività porta 9093 (da Linux/WSL)
nc -zv myapp-eventhubs.servicebus.windows.net 9093

# Listare Consumer Group esistenti
az eventhubs eventhub consumer-group list \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --eventhub-name app-events \
    --output table
```

---

### Scenario 4 — Capture non crea file su Blob Storage

**Sintomo:** Event Hubs Capture è abilitato ma nessun file `.avro` compare nel container di destinazione dopo il tempo configurato (`--capture-interval`).

**Causa:** Il Managed Identity (o la Service Principal) usata da Event Hubs non ha il ruolo `Storage Blob Data Contributor` sul container di destinazione. In alternativa, il container non esiste o il namespace non ha il firewall Blob Storage configurato correttamente.

**Soluzione:** Assegnare il ruolo corretto e verificare che il container esista; usare i log diagnostici per identificare l'errore specifico.

```bash
# Verificare ruolo assegnato all'identità di Event Hubs namespace
EH_PRINCIPAL=$(az eventhubs namespace show \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --query "identity.principalId" -o tsv)

az role assignment list \
    --assignee $EH_PRINCIPAL \
    --scope /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount \
    --output table

# Assegnare ruolo se mancante
az role assignment create \
    --assignee $EH_PRINCIPAL \
    --role "Storage Blob Data Contributor" \
    --scope /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount/blobServices/default/containers/eventhubs-capture

# Verificare impostazioni Capture
az eventhubs eventhub show \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name app-events \
    --query "captureDescription"

# Abilitare log diagnostici per ArchiveLogs
az monitor diagnostic-settings create \
    --resource /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.EventHub/namespaces/myapp-eventhubs \
    --name eh-diag \
    --logs '[{"category":"ArchiveLogs","enabled":true}]' \
    --workspace $LOG_ANALYTICS_WORKSPACE_ID
```

---

## Riferimenti

- [Event Hubs Documentation](https://learn.microsoft.com/azure/event-hubs/)
- [Event Hubs Python SDK](https://learn.microsoft.com/python/api/overview/azure/eventhub-readme)
- [Event Hubs Kafka](https://learn.microsoft.com/azure/event-hubs/event-hubs-for-kafka-ecosystem-overview)
- [Event Hubs Capture](https://learn.microsoft.com/azure/event-hubs/event-hubs-capture-overview)
- [Azure Stream Analytics](https://learn.microsoft.com/azure/stream-analytics/)
- [Schema Registry](https://learn.microsoft.com/azure/event-hubs/schema-registry-overview)
