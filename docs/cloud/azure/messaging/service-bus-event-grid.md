---
title: "Azure Service Bus & Event Grid"
slug: service-bus-event-grid
category: cloud
tags: [azure, service-bus, event-grid, messaging, pub-sub, queue, topic, subscription, dlq, sessions]
search_keywords: [Azure Service Bus, Service Bus Queue, Service Bus Topic, Service Bus subscription, dead letter queue DLQ, message sessions FIFO, duplicate detection, scheduled messages, Service Bus namespace, Event Grid, System Topic Event Grid, Custom Topic Event Grid, CloudEvents, event subscription, event filter, event routing Azure, Logic Apps Event Grid, Service Bus Premium geo-DR]
parent: cloud/azure/messaging/_index
related: [cloud/azure/messaging/event-hubs, cloud/azure/compute/app-service-functions, cloud/azure/storage/blob-storage]
official_docs: https://learn.microsoft.com/azure/service-bus-messaging/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Service Bus & Event Grid

## Azure Service Bus

**Azure Service Bus** è un message broker enterprise fully managed — equivalente ad AWS SQS/SNS combinati, con features avanzate per scenari aziendali (transazioni, ordering, sessioni).

### SKU e Funzionalità

| Feature | Basic | Standard | Premium |
|---------|-------|----------|---------|
| Queue | Sì | Sì | Sì |
| Topic/Subscription | No | Sì | Sì |
| Message size | 256 KB | 256 KB | 100 MB |
| Sessions | No | Sì | Sì |
| Transactions | No | Sì | Sì |
| Geo-DR | No | No | Sì |
| VNet Integration | No | No | Sì |
| Dedicated | No | No | Sì |
| Prezzo | ~$0.05/M op | ~$0.10/M op | da $670/mese |

---

### Creare Namespace, Queue e Topic

```bash
# Creare namespace
az servicebus namespace create \
    --resource-group myapp-rg \
    --name myapp-servicebus \
    --sku Standard \
    --location italynorth

# Creare Queue
az servicebus queue create \
    --resource-group myapp-rg \
    --namespace-name myapp-servicebus \
    --name orders-queue \
    --max-size 5120 \                             # MB: 1024, 2048, 3072, 4096, 5120
    --lock-duration PT2M \                        # ISO 8601: 2 minuti (default 1 min, max 5 min)
    --default-message-time-to-live P14D \         # TTL: 14 giorni
    --dead-lettering-on-message-expiration true \
    --duplicate-detection-history-time-window PT10M \   # finestra deduplica (max 7 giorni)
    --enable-duplicate-detection true \
    --max-delivery-count 5                        # max retry prima di DLQ

# Creare Topic
az servicebus topic create \
    --resource-group myapp-rg \
    --namespace-name myapp-servicebus \
    --name order-events \
    --max-size 5120 \
    --default-message-time-to-live P14D

# Creare Subscription al Topic (senza filtro = riceve tutto)
az servicebus topic subscription create \
    --resource-group myapp-rg \
    --namespace-name myapp-servicebus \
    --topic-name order-events \
    --name inventory-subscription \
    --max-delivery-count 5 \
    --dead-letter-on-filter-evaluation-exceptions true \
    --lock-duration PT1M

# Creare Subscription con filtro SQL
az servicebus topic subscription rule create \
    --resource-group myapp-rg \
    --namespace-name myapp-servicebus \
    --topic-name order-events \
    --subscription-name inventory-subscription \
    --name high-value-orders \
    --filter-sql-expression "amount > 100 AND region = 'EU'"

# Creare Subscription con filtro correlationFilter (più efficiente per semplice matching)
az servicebus topic subscription rule create \
    --resource-group myapp-rg \
    --namespace-name myapp-servicebus \
    --topic-name order-events \
    --subscription-name notification-subscription \
    --name order-created-filter \
    --filter-type CorrelationFilter \
    --correlation-filter-properties eventType=order.created
```

---

### Inviare e Ricevere Messaggi — Python SDK

```python
# pip install azure-servicebus azure-identity

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity import DefaultAzureCredential
import json
from datetime import datetime, timedelta, timezone

NAMESPACE = "myapp-servicebus.servicebus.windows.net"
QUEUE_NAME = "orders-queue"
TOPIC_NAME = "order-events"

credential = DefaultAzureCredential()   # Managed Identity / az login

# ── Inviare a Queue ────────────────────────────────────────────────────────
def send_order(order: dict):
    with ServiceBusClient(NAMESPACE, credential) as client:
        with client.get_queue_sender(QUEUE_NAME) as sender:
            message = ServiceBusMessage(
                body=json.dumps(order).encode('utf-8'),
                message_id=f"order-{order['id']}",          # deduplication ID
                correlation_id=order.get('customerId'),
                subject="order.created",
                content_type="application/json",
                time_to_live=timedelta(hours=24),
                # Messaggio schedulato: visibile tra 5 minuti
                scheduled_enqueue_time_utc=datetime.now(timezone.utc) + timedelta(minutes=5)
            )
            sender.send_messages(message)

# ── Inviare a Topic ────────────────────────────────────────────────────────
def publish_event(event_type: str, payload: dict):
    with ServiceBusClient(NAMESPACE, credential) as client:
        with client.get_topic_sender(TOPIC_NAME) as sender:
            message = ServiceBusMessage(
                body=json.dumps(payload).encode('utf-8'),
                application_properties={
                    "eventType": event_type,
                    "region": payload.get("region", "EU"),
                    "amount": payload.get("amount", 0)
                }
            )
            sender.send_messages(message)

# ── Ricevere da Queue ──────────────────────────────────────────────────────
def process_orders():
    with ServiceBusClient(NAMESPACE, credential) as client:
        with client.get_queue_receiver(
            QUEUE_NAME,
            max_wait_time=30                # long polling 30 secondi
        ) as receiver:
            for msg in receiver:
                try:
                    order = json.loads(msg.body)
                    process_order(order)
                    receiver.complete_message(msg)         # rimuove dalla queue
                except Exception as e:
                    print(f"Error processing {msg.message_id}: {e}")
                    if msg.delivery_count >= 4:
                        receiver.dead_letter_message(        # DLQ manuale
                            msg,
                            reason="MaxRetriesExceeded",
                            error_description=str(e)
                        )
                    else:
                        receiver.abandon_message(msg)       # torna disponibile

# ── Sessioni (FIFO per entità) ─────────────────────────────────────────────
# Queue deve avere --enable-session true
def send_with_session(order: dict):
    with ServiceBusClient(NAMESPACE, credential) as client:
        with client.get_queue_sender("orders-session-queue") as sender:
            message = ServiceBusMessage(
                body=json.dumps(order).encode('utf-8'),
                session_id=f"customer-{order['customerId']}"   # tutti gli ordini dello stesso customer in ordine
            )
            sender.send_messages(message)

def receive_session(session_id: str):
    with ServiceBusClient(NAMESPACE, credential) as client:
        # Blocca una sessione specifica
        with client.get_queue_receiver(
            "orders-session-queue",
            session_id=session_id
        ) as receiver:
            for msg in receiver:
                process_order(json.loads(msg.body))
                receiver.complete_message(msg)
```

---

### Dead Letter Queue (DLQ)

```bash
# Listare messaggi in DLQ (via CLI)
# La DLQ si accede con path: queuename/$DeadLetterQueue

# Via SDK Python
from azure.servicebus import ServiceBusSubQueue

def inspect_dlq():
    with ServiceBusClient(NAMESPACE, credential) as client:
        with client.get_queue_receiver(
            QUEUE_NAME,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER
        ) as receiver:
            msgs = receiver.receive_messages(max_message_count=10, max_wait_time=5)
            for msg in msgs:
                print(f"DLQ msg: {msg.message_id}, reason: {msg.dead_letter_reason}")
                # Analizza, correggi, rispedisci alla queue principale se possibile
```

---

### Features Avanzate

| Feature | Descrizione | Configurazione |
|---------|-------------|---------------|
| **Sessions** | FIFO garantito per entity (customer, order) | `--enable-session true` su queue |
| **Duplicate Detection** | Ignora messaggi con stesso MessageId in finestra temporale | `--enable-duplicate-detection true` |
| **Scheduled Messages** | Messaggio visibile a orario futuro | `scheduled_enqueue_time_utc` nel SDK |
| **Deferred Messages** | Consumer posticipa elaborazione per dopo | `receiver.defer_message(msg)` |
| **Transactions** | Operazioni atomiche su più entità | `ServiceBusClient.get_queue_sender` dentro `transaction()` |
| **Message Lock Renewal** | Estende lock durante elaborazione lunga | `receiver.renew_message_lock(msg)` |

---

## Azure Event Grid

**Event Grid** è il servizio di routing eventi completamente serverless — instrada eventi da sorgenti Azure a handler, con filtri e retry automatici.

```
Event Sources                    Event Grid                  Event Handlers
─────────────                    ──────────                  ──────────────
Azure Storage ─────────────────► System Topic ──► Rules ──► Azure Function
Azure Event Hubs ───────────────►              ──► Rules ──► Logic App
Azure Container Registry ───────►              ──► Rules ──► Service Bus Queue
Custom App ────────────────────► Custom Topic ──► Rules ──► Webhook / HTTP
SaaS Partner ──────────────────► Partner Topic ──► Rules ──► Event Hubs
```

### System Topic — Eventi da Azure Services

```bash
# Creare System Topic per Storage Account
az eventgrid system-topic create \
    --resource-group myapp-rg \
    --name storage-events-topic \
    --source /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount \
    --topic-type Microsoft.Storage.StorageAccounts \
    --location italynorth

# Creare sottoscrizione: eventi blob → Function
az eventgrid system-topic event-subscription create \
    --resource-group myapp-rg \
    --system-topic-name storage-events-topic \
    --name blob-to-function \
    --endpoint-type azurefunction \
    --endpoint /subscriptions/$SUB_ID/.../functions/ProcessBlob \
    --included-event-types Microsoft.Storage.BlobCreated \
    --subject-begins-with /blobServices/default/containers/uploads/ \
    --deadletter-endpoint /subscriptions/$SUB_ID/.../blobServices/default/containers/dlq/blobs \
    --max-delivery-attempts 10 \
    --event-ttl 1440 \                     # minuti: 24 ore
    --retry-policy max-number-of-attempts=10

# Listare tipi di eventi per ogni risorsa
az eventgrid event-subscription list-global-by-subscription-for-topic-type \
    --topic-type Microsoft.Storage.StorageAccounts
```

### Custom Topic

```bash
# Creare Custom Topic (eventi da applicazioni proprie)
TOPIC_ENDPOINT=$(az eventgrid topic create \
    --resource-group myapp-rg \
    --name myapp-events \
    --location italynorth \
    --input-schema cloudeventschemav1_0 \    # CloudEvents 1.0 (standard) o EventGridSchema
    --query endpoint -o tsv)

# Ottenere access key (per invio — usare Managed Identity in produzione)
TOPIC_KEY=$(az eventgrid topic key list \
    --resource-group myapp-rg \
    --name myapp-events \
    --query key1 -o tsv)

# Creare sottoscrizione: Custom Topic → Service Bus Queue
az eventgrid event-subscription create \
    --source-resource-id /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.EventGrid/topics/myapp-events \
    --name orders-to-servicebus \
    --endpoint-type servicebusqueue \
    --endpoint /subscriptions/$SUB_ID/.../queues/orders-queue \
    --event-delivery-schema cloudeventschemav1_0 \
    --advanced-filter data.amount NumberGreaterThan 100 \     # filtro sul payload
    --included-event-types order.created order.updated
```

### Inviare CloudEvents (Standard Raccomandato)

```python
# pip install azure-eventgrid azure-identity

from azure.eventgrid import EventGridPublisherClient
from azure.core.messaging import CloudEvent
from azure.identity import DefaultAzureCredential
import uuid
from datetime import datetime, timezone

# Autenticazione con Managed Identity (produzione)
credential = DefaultAzureCredential()
client = EventGridPublisherClient(TOPIC_ENDPOINT, credential)

# Evento CloudEvents 1.0
event = CloudEvent(
    type="com.myapp.order.created",
    source="/myapp/orders",
    data={
        "orderId": "ORD-001",
        "customerId": "CUST-42",
        "amount": 150.00,
        "region": "EU",
        "items": [
            {"sku": "PROD-001", "qty": 2, "price": 75.00}
        ]
    },
    id=str(uuid.uuid4()),
    time=datetime.now(timezone.utc),
    datacontenttype="application/json",
    subject="orders/ORD-001"
)

# Invio batch
client.send([event])

# Azure Function handler per CloudEvents
import azure.functions as func
import json

app = func.FunctionApp()

@app.function_name("ProcessOrderEvent")
@app.event_grid_trigger(arg_name="event")
def process_order_event(event: func.EventGridEvent) -> None:
    data = event.get_json()
    print(f"Received event: {event.event_type}")
    print(f"Order ID: {data.get('orderId')}")
    # process order...
```

### Filtri Avanzati

```json
{
  "filter": {
    "subjectBeginsWith": "/orders/",
    "subjectEndsWith": ".json",
    "includedEventTypes": ["com.myapp.order.created", "com.myapp.order.updated"],
    "advancedFilters": [
      {
        "operatorType": "NumberGreaterThan",
        "key": "data.amount",
        "value": 100
      },
      {
        "operatorType": "StringIn",
        "key": "data.region",
        "values": ["EU", "EMEA"]
      },
      {
        "operatorType": "BoolEquals",
        "key": "data.urgent",
        "value": true
      }
    ]
  }
}
```

### Event Grid Namespace (Nuovo — 2024)

**Event Grid Namespace** introduce il modello **pull-based** e supporto **MQTT** — ideale per IoT e scenari dove il subscriber non è sempre online:

```bash
# Creare Namespace
az eventgrid namespace create \
    --resource-group myapp-rg \
    --name myapp-eg-namespace \
    --location italynorth \
    --sku Standard

# Creare Topic nel Namespace
az eventgrid namespace topic create \
    --resource-group myapp-rg \
    --namespace-name myapp-eg-namespace \
    --topic-name orders \
    --publisher-type Custom \
    --input-schema CloudEventSchemaV1_0 \
    --event-retention-in-days 1

# Creare Subscription con pull delivery
az eventgrid namespace topic event-subscription create \
    --resource-group myapp-rg \
    --namespace-name myapp-eg-namespace \
    --topic-name orders \
    --event-subscription-name orders-processor \
    --delivery-configuration '{"deliveryMode": "Queue", "queue": {"receiveLockDurationInSeconds": 60, "maxDeliveryCount": 5}}'
```

---

## Riferimenti

- [Azure Service Bus Documentation](https://learn.microsoft.com/azure/service-bus-messaging/)
- [Service Bus Python SDK](https://learn.microsoft.com/python/api/overview/azure/servicebus-readme)
- [Azure Event Grid Documentation](https://learn.microsoft.com/azure/event-grid/)
- [CloudEvents Specification](https://cloudevents.io/)
- [Event Grid Namespace](https://learn.microsoft.com/azure/event-grid/event-grid-namespace-overview)
- [Service Bus vs Event Grid vs Event Hubs](https://learn.microsoft.com/azure/event-grid/compare-messaging-services)
