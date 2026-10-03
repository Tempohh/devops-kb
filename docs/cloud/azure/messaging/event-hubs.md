---
title: "Azure Event Hubs"
slug: event-hubs
category: cloud
tags: [azure, event-hubs, kafka, streaming, partitions, consumer-group, capture, stream-analytics]
search_keywords: [Azure Event Hubs, Kafka Azure, streaming Azure, partition Event Hubs, consumer group Event Hubs, Event Hubs Capture, Avro, Azure Stream Analytics, Kinesis Azure equivalent, event streaming, telemetria IoT, clickstream, high throughput messaging, Event Hubs namespace, throughput units, processing units, Event Hubs Dedicated, Schema Registry, AMQP Kafka HTTPS]
parent: cloud/azure/messaging/_index
related: [cloud/azure/messaging/service-bus-event-grid, cloud/azure/storage/blob-storage, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/event-hubs/
status: needs-review
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Event Hubs

**Azure Event Hubs** è il servizio di **streaming ad alto volume** di Azure — gestisce milioni di eventi al secondo con latenza sub-secondo. È l'equivalente di Apache Kafka (e ha un'API Kafka nativa compatibile).

**Perché esiste:** un log distribuito append-only e partizionato disaccoppia chi produce eventi da chi li consuma: ogni consumer legge al proprio ritmo (tramite offset) e può rileggere eventi già consumati entro la retention. Questo lo distingue da una coda (Service Bus), dove il messaggio sparisce dopo il consumo.
**Quando NON usarlo:** messaggi di comando con ordering/dead-letter/transazioni → Service Bus; notifiche reattive su eventi di risorse Azure → Event Grid; volumi bassi e semplici → Storage Queue.

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
- **Partition:** unità di parallelismo e ordinamento; `partition_key → hash → partition`. L'ordine è garantito solo *dentro* una partition. Limiti per Event Hub: Basic/Standard 32 (Standard fino a 1024 su richiesta), Premium 100, Dedicated 1024. Su Basic/Standard il numero è fisso dopo la creazione; su Premium/Dedicated si può aumentare
- **Consumer Group:** vista indipendente sullo stream: ogni gruppo ha i propri offset (simile al Kafka consumer group, ma vedi limitazioni Kafka sotto)
- **Retention:** 1 giorno (Basic), fino a 7 giorni (Standard), fino a 90 giorni (Premium/Dedicated)
- **Throughput Unit (TU):** unità di capacità per Standard — 1 TU = 1 MB/s (o 1000 eventi/s) ingress, 2 MB/s (o 4096 eventi/s) egress. Premium usa **Processing Unit (PU)**, Dedicated usa **Capacity Unit (CU)**
- **Checkpoint:** offset salvato dal consumer; dopo un restart riparte da lì (a differenza di Kafka, lo store è gestito dal client, tipicamente su Blob Storage)

---

## SKU Event Hubs

| | Basic | Standard | Premium | Dedicated |
|---|-------|----------|---------|-----------|
| Consumer Groups (per Event Hub) | 1 | 20 | 100 | 1000 |
| Retention max | 1 giorno | 7 giorni | 90 giorni | 90 giorni |
| Message size | 256 KB | 1 MB | 1 MB | 1 MB |
| Throughput | TU (fisse) | TU (auto-inflate opzionale) | PU (scelte manualmente) | CU (dedicate) |
| Kafka API | No | Sì | Sì | Sì |
| Capture | No | Sì | Sì | Sì |
| Schema Registry | No | Sì | Sì | Sì |
| Private Endpoint | No | Sì | Sì | Sì |
| Prezzo (indicativo, verificare sul pricing calculator) | per milione di eventi, il più basso | per milione di eventi + TU/ora | per PU/ora, ingress/egress inclusi | per CU/ora, ordine di migliaia di $/mese per CU |

---

## Creare Namespace e Event Hub

```bash
# Creare Namespace Standard
az eventhubs namespace create \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --sku Standard \
    --location italynorth \
#   --capacity 2: Throughput Units iniziali
#   auto-inflate: scala SOLO verso l'alto fino a 10 TU, mai verso il basso (scendere è manuale)
az eventhubs namespace create \
    --resource-group myapp-rg \
    --name myapp-eventhubs \
    --sku Standard \
    --location italynorth \
    --capacity 2 \
    --enable-auto-inflate true \
    --maximum-throughput-units 10 \
    --minimum-tls-version 1.2

# Creare Event Hub
#   --partition-count: fisso su Standard — scegliere con cura (parallelismo massimo dei consumer = n. partition)
#   --retention-time-in-hours: 168 = 7 giorni (max Standard)
#   --cleanup-policy: Delete (default) o Compact (solo ultima versione per key; solo Premium/Dedicated)
az eventhubs eventhub create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name app-events \
    --partition-count 8 \
    --retention-time-in-hours 168 \
    --cleanup-policy Delete

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

# RBAC: concedere accesso a Managed Identity (ruoli: Data Sender, Data Receiver, Data Owner)
# Preferire RBAC alle chiavi SAS: nessun segreto da ruotare, audit per identità
az role assignment create \
    --assignee-object-id $MANAGED_IDENTITY_PRINCIPAL_ID \
    --assignee-principal-type ServicePrincipal \
    --role "Azure Event Hubs Data Sender" \
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
        # Batch per efficienza: create_batch() è una coroutine (await), non un context manager.
        # Se partition_key e partition_id sono omessi, il servizio distribuisce tra le partition.
        batch = await producer.create_batch()
        for event in events:
            event_data = EventData(json.dumps(event).encode('utf-8'))
            try:
                batch.add(event_data)
            except ValueError:
                # Batch pieno (limite di dimensione): invia e ricrea
                await producer.send_batch(batch)
                batch = await producer.create_batch()
                batch.add(event_data)
        if len(batch) > 0:
            await producer.send_batch(batch)

# Usare con partition key
async def send_with_partition_key(user_id: str, user_events: list[dict]):
    credential = DefaultAzureCredential()
    async with EventHubProducerClient(NAMESPACE, EVENTHUB, credential) as producer:
        # La partition_key è del batch: tutti gli eventi dello stesso utente
        # finiscono nella stessa partition, quindi mantengono l'ordine
        batch = await producer.create_batch(partition_key=f"user-{user_id}")
        for event in user_events:
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

NAMESPACE = "myapp-eventhubs.servicebus.windows.net"
EVENTHUB = "app-events"
CONSUMER_GROUP = "analytics-consumer"
STORAGE_ACCOUNT = "https://mystorageaccount.blob.core.windows.net"
CONTAINER = "event-checkpoints"

async def handle_event(data: dict):
    ...  # logica applicativa (idempotente: la consegna è at-least-once)

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
        # Non aggiornare il checkpoint qui. Attenzione: il prossimo evento che ha successo
        # checkpointerà un offset successivo e questo evento andrebbe perso →
        # in produzione usare retry o una dead-letter (es. un secondo Event Hub / Blob)

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
    ) as consumer:
        print(f"Listening on {EVENTHUB}...")
        # starting_position vale solo per le partition SENZA checkpoint;
        # con un checkpoint esistente si riparte da lì. "@latest" (default) o "-1" (dall'inizio)
        await consumer.receive(
            on_event=process_event,
            starting_position="-1"
        )

asyncio.run(main())
```

---

## Event Hubs Capture

**Capture** archivia automaticamente gli eventi su **Blob Storage** o **Data Lake Gen2** in formato **Avro** (formato binario compatto con schema incorporato) — utile per data lake, auditing, replay. Scatta al primo tra intervallo di tempo e soglia di dimensione, per ogni partition.

```bash
# Abilitare Capture su Event Hub esistente
#   --capture-interval: secondi (60-900), flush ogni 5 minuti
#   --capture-size-limit: bytes (10 MB-500 MB), flush al raggiungimento di ~300 MB
#   --archive-name-format: deve contenere tutti i token {Namespace} {EventHub} {PartitionId} {Year} {Month} {Day} {Hour} {Minute} {Second}
#   esempio di path risultante: myapp-eventhubs/app-events/0/2026/02/26/14/30/00.avro
az eventhubs eventhub update \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name app-events \
    --enable-capture true \
    --capture-interval 300 \
    --capture-size-limit 314572800 \
    --destination-name EventHubArchive \
    --storage-account /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount \
    --blob-container eventhubs-capture \
    --archive-name-format "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}"
```

Lettura dei file Avro catturati (Python):

```python
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

**Path pattern:** i token sono obbligatori, ma l'ordine è libero. Mettere `{Year}/{Month}/{Day}/{Hour}` prima di `{PartitionId}` raggruppa i file per data (utile per query con partition pruning in Spark/Synapse/Fabric); l'ordine predefinito raggruppa per partition.

!!! note "Autenticazione di Capture"
    Per scrivere sullo storage, il namespace deve avere una Managed Identity (system o user-assigned) con ruolo `Storage Blob Data Contributor` sulla destinazione; senza, Capture fallisce silenziosamente (vedi Troubleshooting).

---

## API Kafka — Compatibilità Nativa

Event Hubs Standard/Premium/Dedicated espone un endpoint **Kafka-compatible** (protocollo Kafka 1.0+, porta 9093) — il codice Kafka esistente funziona cambiando solo la configurazione di connessione. Mapping: cluster Kafka = namespace, topic = Event Hub, partition = partition.

!!! warning "Autenticazione"
    L'esempio usa la connection string SAS per brevità. La `RootManageSharedAccessKey` ha permessi totali sul namespace: in produzione usare una SAS policy dedicata con solo `Send`/`Listen`, oppure **Entra ID via OAUTHBEARER** (`sasl.mechanism=OAUTHBEARER` con il callback handler della propria libreria) e i ruoli RBAC Data Sender/Receiver.

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
- Kafka Transactions e Kafka Streams: supporto limitato agli SKU Premium/Dedicated <!-- REVIEW: verificare stato GA di Kafka Transactions e Kafka Streams per SKU su learn.microsoft.com/azure/event-hubs/apache-kafka-frequently-asked-questions -->
- Nessuna auto-creazione dei topic con le impostazioni di default: creare prima l'Event Hub (o via Kafka AdminClient dove supportato)
- I *Kafka consumer group* (offset gestiti dal broker) sono distinti dai Consumer Group nativi di Event Hubs usati dagli SDK AMQP; i limiti per SKU della tabella riguardano questi ultimi
- Retention e partition si configurano sull'Event Hub, non con le proprietà Kafka del topic

---

## Azure Stream Analytics

**Azure Stream Analytics** (ASA) è il servizio di stream processing managed per eventi in tempo reale — usa query SQL-like (SAQL) su dati in streaming. Alternative: Eventstream/Real-Time Intelligence in Microsoft Fabric, Spark Structured Streaming (Databricks/Synapse), Azure Functions per logica per-evento.

```bash
# Richiede l'estensione CLI: az extension add --name stream-analytics
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
        -- ([alerting-output] va definito con un secondo `az stream-analytics output create`)
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

Lo **Schema Registry** (Standard/Premium/Dedicated, non Basic) è un repository centralizzato di schema versionati: producer e consumer si accordano sul formato (es. Avro) senza includere lo schema in ogni messaggio, e le regole di compatibilità impediscono modifiche che romperebbero i consumer esistenti.

```bash
# Creare Schema Group
# (--schema-compatibility: None, Backward, Forward)
az eventhubs namespace schema-registry create \
    --resource-group myapp-rg \
    --namespace-name myapp-eventhubs \
    --name orders-schemas \
    --schema-compatibility Forward \
    --schema-type Avro
```

I singoli schema si registrano dal data plane tramite SDK (`azure-schemaregistry` + `azure-schemaregistry-avroencoder` per Python), non da `az`:

```python
# pip install azure-schemaregistry azure-schemaregistry-avroencoder azure-identity
from azure.identity import DefaultAzureCredential
from azure.schemaregistry import SchemaRegistryClient

client = SchemaRegistryClient("myapp-eventhubs.servicebus.windows.net", DefaultAzureCredential())
schema = """{"type":"record","name":"OrderEvent","namespace":"com.myapp","fields":[
  {"name":"orderId","type":"string"},
  {"name":"amount","type":"double"},
  {"name":"timestamp","type":"long","logicalType":"timestamp-millis"}]}"""
props = client.register_schema("orders-schemas", "order-event", schema, "Avro")
print(props.id)
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

**Soluzione:** Abilitare auto-inflate o aumentare manualmente i TU; monitorare la metrica `ThrottledRequests`. Nota: auto-inflate non scala mai verso il basso, quindi dopo un picco si continua a pagare il massimo raggiunto finché non si riducono i TU a mano. Se il collo di bottiglia è una singola partition (hot key), aumentare i TU non aiuta: rivedere la partition key.

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

**Sintomo:** Il consumer group non processa nuovi eventi; la metrica `IncomingMessages` cresce ma `OutgoingMessages` è piatta. Il lag (eventi in coda non ancora letti) aumenta continuamente.

**Causa:** Il checkpoint store (Blob Storage) non viene aggiornato (eccezione silenziata nel callback `on_event`), oppure un singolo consumer detiene una partition ma non la processa (crash senza rilascio).

**Soluzione:** Verificare i checkpoint nel Blob container, forzare il rilascio delle partition resettando il consumer group, o eliminare e ricreare il checkpoint.

```bash
# Vedere checkpoint e ownership nel Blob container (un blob per partition).
# Layout dello store: <fqdn>/<eventhub>/<consumer-group>/{checkpoint,ownership}/<partition-id>
az storage blob list \
    --account-name mystorageaccount \
    --container-name event-checkpoints \
    --prefix "myapp-eventhubs.servicebus.windows.net/app-events/analytics-consumer/" \
    --auth-mode login \
    --output table

# Eliminare checkpoint per ripartire da starting_position (ATTENZIONE: replay di tutti gli eventi in retention)
az storage blob delete-batch \
    --account-name mystorageaccount \
    --source event-checkpoints \
    --pattern "myapp-eventhubs.servicebus.windows.net/app-events/analytics-consumer/checkpoint/*" \
    --auth-mode login

# Verificare lag per consumer group tramite metrica IncomingMessages vs OutgoingMessages
az monitor metrics list \
    --resource /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.EventHub/namespaces/myapp-eventhubs/eventhubs/app-events \
    --metric IncomingMessages,OutgoingMessages \
    --interval PT5M
```

---

### Scenario 3 — Kafka client non riesce a connettersi

**Sintomo:** Il Kafka producer/consumer riceve `SASL authentication failed` o `Connection refused` quando usa l'endpoint Kafka di Event Hubs.

**Causa:** Le cause più comuni sono: (1) SKU Basic (non supporta Kafka), (2) connection string errata o scaduta nella password SASL, (3) porta 9093 bloccata dal firewall o IP/VNet non autorizzato nelle regole di rete del namespace, (4) username diverso da `$ConnectionString` letterale.

**Soluzione:** Verificare lo SKU, rigenerare le chiavi SAS se necessario, controllare le regole di rete del namespace e che l'Event Hub (= topic) esista.

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

## Relazioni

??? info "Service Bus ed Event Grid — Approfondimento"
    Event Hubs è per stream ad alto volume riletti dai consumer; Service Bus per messaggi di comando con code, sessioni e dead-letter; Event Grid per routing reattivo di eventi discreti.

    **Approfondimento completo →** [Service Bus ed Event Grid](service-bus-event-grid.md)

??? info "Blob Storage — Approfondimento"
    Destinazione di Capture e sede del checkpoint store dei consumer.

    **Approfondimento completo →** [Blob Storage](../storage/blob-storage.md)

??? info "Monitor e Log Analytics — Approfondimento"
    Metriche (`ThrottledRequests`, `IncomingMessages`) e diagnostic settings (`ArchiveLogs`) usati nel Troubleshooting.

    **Approfondimento completo →** [Monitor e Log Analytics](../monitoring/monitor-log-analytics.md)

---

## Riferimenti

- [Event Hubs Documentation](https://learn.microsoft.com/azure/event-hubs/)
- [Event Hubs Python SDK](https://learn.microsoft.com/python/api/overview/azure/eventhub-readme)
- [Event Hubs Kafka](https://learn.microsoft.com/azure/event-hubs/event-hubs-for-kafka-ecosystem-overview)
- [Event Hubs Capture](https://learn.microsoft.com/azure/event-hubs/event-hubs-capture-overview)
- [Azure Stream Analytics](https://learn.microsoft.com/azure/stream-analytics/)
- [Schema Registry](https://learn.microsoft.com/azure/event-hubs/schema-registry-overview)
