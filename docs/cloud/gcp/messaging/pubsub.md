---
title: "Cloud Pub/Sub"
slug: pubsub
category: cloud/gcp/messaging
tags: [gcp, pubsub, messaging, pub-sub, event-driven, streaming, async, queue, topic, subscription]
search_keywords: [Cloud Pub/Sub, Google Pub/Sub, GCP messaging, pub sub GCP, topic subscription GCP, push subscription, pull subscription, StreamingPull, BigQuery subscription, Cloud Storage subscription, Dead Letter Topic, DLT Pub/Sub, message ordering, ordering key, Pub/Sub retention, snapshot seek replay, Pub/Sub IAM, Workload Identity Pub/Sub, fan-out GCP, Pub/Sub vs Kafka, Pub/Sub vs SQS, Pub/Sub vs SNS, exactly-once delivery GCP, at-least-once delivery GCP, Pub/Sub Cloud Run trigger, Pub/Sub Dataflow, Pub/Sub analytics, gcloud pubsub, managed messaging GCP, asincrono GCP, messaggistica GCP, broker messaggi Google Cloud, event streaming GCP]
parent: cloud/gcp/messaging/_index
related: [cloud/gcp/compute/cloud-run, cloud/gcp/dati/bigquery, cloud/gcp/iam/iam-service-accounts, cloud/gcp/containers/gke]
official_docs: https://cloud.google.com/pubsub/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-31
---

# Cloud Pub/Sub

## Panoramica

Cloud Pub/Sub è il servizio di **messaggistica asincrona fully managed** di Google Cloud. Implementa il pattern publisher/subscriber: i producer pubblicano messaggi su un **topic** e i consumer li ricevono tramite **subscription**, senza che i due lati si conoscano o siano online contemporaneamente. È il backbone della messaggistica asincrona su GCP.

A differenza di Kafka, Pub/Sub è completamente serverless: non ci sono broker, partizioni o cluster da gestire. La scalabilità è automatica e globale — Pub/Sub è **multi-region by default**, replicando i messaggi su più datacenter senza configurazione aggiuntiva.

**Quando usare Pub/Sub:**
- Disaccoppiare microservizi produttori di eventi dai consumer
- Triggerare Cloud Run o Cloud Functions su eventi asincroni (equivalente SQS→Lambda)
- Pipeline di streaming verso Dataflow, BigQuery, o Cloud Storage
- Fan-out: un evento deve essere processato da più sistemi indipendenti
- Ingestione di dati da dispositivi IoT o log ad alto volume

**Quando NON usare Pub/Sub:**
- Serve FIFO garantito globalmente tra topic diversi → considerare Kafka (Confluent su GCP)
- Replay storico illimitato come in Kafka → Pub/Sub ha retention max 31 giorni
- Job queue con visibilità e ACK espliciti → valutare Cloud Tasks (ha scheduling, retry granulare)
- Messaggi > 10 MB → usa Cloud Storage come intermediario

**Posizionamento rispetto ad altri servizi:**

| Servizio | Paradigma | Use case principale |
|---|---|---|
| **Pub/Sub** | Pub/Sub asincrono | Messaggistica event-driven, fan-out, streaming |
| **Cloud Tasks** | Queue con scheduling | Job asincroni con retry granulare, deduplication |
| **Eventarc** | Event routing | Routing eventi GCP verso Cloud Run/Functions (usa Pub/Sub internamente) |
| **Dataflow** | Stream processing | Trasformazioni su stream Pub/Sub (ETL, aggregazioni) |

---

## Concetti Chiave

**Topic:** canale logico di pubblicazione. Il producer scrive messaggi sul topic senza sapere chi li consumerà. Un topic può avere zero o più subscription.

**Subscription:** rappresenta un consumer (o gruppo di consumer) su un topic. Ogni subscription riceve una copia di ogni messaggio pubblicato dopo la sua creazione. Le subscription sono indipendenti: se ci sono 3 subscription, ogni messaggio viene consegnato 3 volte (una per subscription).

**Message:** unità di dati inviata. Composta da:
- `data` — payload in bytes (max 10 MB)
- `attributes` — mappa chiave/valore per metadata (filtri, routing)
- `messageId` — generato da Pub/Sub, univoco
- `publishTime` — timestamp di pubblicazione
- `orderingKey` — opzionale, per ordering garantito

**Acknowledgment (ACK):** il consumer deve confermare la ricezione di ogni messaggio. I messaggi non ACK entro il deadline vengono riconsegnati (**at-least-once delivery** by default).

!!! warning "At-least-once delivery"
    Per default, ogni messaggio può essere consegnato **più di una volta**. I consumer devono essere **idempotenti** oppure abilitare la modalità exactly-once delivery (disponibile, ma con limitazioni di throughput).

!!! tip "Exactly-once delivery"
    Abilitabile per subscription con `--enable-exactly-once-delivery`. Pub/Sub garantisce che il messaggio venga consegnato esattamente una volta all'interno della finestra di retention, ma riduce il throughput massimo. Usarlo solo quando l'idempotenza nel consumer non è implementabile.

---

## Architettura / Come Funziona

### Flusso base

```
Publisher (es. Cloud Run, GKE, VM)
    │
    │  publish(message)
    ▼
┌─────────────────────────────────────────┐
│              TOPIC                      │
│    (globale, multi-region by default)   │
└────────────┬────────────────────────────┘
             │  copia del messaggio per ogni subscription
      ┌──────┴──────────────────────────┐
      │                                 │
      ▼                                 ▼
┌──────────────────┐         ┌──────────────────────┐
│  Subscription A  │         │   Subscription B     │
│  (Pull — worker) │         │   (Push — Cloud Run)  │
└────────┬─────────┘         └──────────┬───────────┘
         │                              │
         │  pull() → ACK()              │  HTTP POST → 200 OK
         ▼                              ▼
   Consumer Pool                   Cloud Run Service
   (GKE, Compute)                  (invocato da Pub/Sub)
```

### Retention e Delivery

I messaggi vengono conservati nel topic per la durata di retention configurata (default **7 giorni**, min 10 min, max 31 giorni). La subscription ha il suo puntatore di avanzamento: un messaggio non ACK viene riconsegnato dopo l'`ackDeadline` (default 10s, max 600s).

```
Timeline messaggio in Pub/Sub:

T+0   Publisher → publish(msg)
T+0   Msg nel topic, disponibile per tutte le subscription
T+1   Subscription A riceve msg via pull
T+1   ackDeadline inizia (default 10s)
T+11  Msg non ACK → riconsegnato (at-least-once)
      O
T+5   Consumer elabora → ACK → msg rimosso dalla subscription

T+7d  Topic retention scade → msg eliminato dal topic
```

---

## Tipi di Subscription

### Pull Subscription

Il consumer **chiede attivamente** i messaggi a Pub/Sub. Adatto per worker pool, batch processing, consumer che devono controllare la propria velocità di consumo.

```bash
# Creare una pull subscription
gcloud pubsub subscriptions create my-pull-sub \
    --topic=my-topic \
    --ack-deadline=60 \                      # secondi prima della riconsegna
    --message-retention-duration=7d \         # quanti giorni trattenere msg non ACK
    --max-delivery-attempts=5 \              # prima di mandare al Dead Letter Topic
    --dead-letter-topic=my-topic-dlq \
    --expiration-period=never                 # la subscription non scade

# Pull manuale (fino a 10 messaggi per chiamata)
gcloud pubsub subscriptions pull my-pull-sub \
    --limit=10 \
    --auto-ack       # ACK automatico (solo per test — in produzione ACK manuale)

# Pull senza auto-ack (riceve i messaggi senza confermarli)
gcloud pubsub subscriptions pull my-pull-sub --limit=5
# L'output include il receipt handle (ACK ID) da usare per confermare
```

**StreamingPull (gRPC bidirezionale)** — per throughput elevato. Il consumer apre una connessione gRPC persistente e riceve messaggi in streaming. Raccomandato per tutte le implementazioni in produzione. Supportato dalle client library ufficiali:

```python
# Python — consumer con StreamingPull (client library GCP)
# pip install google-cloud-pubsub

from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1

project_id = "my-project"
subscription_id = "my-pull-sub"

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(project_id, subscription_id)

def callback(message: pubsub_v1.types.PubsubMessage) -> None:
    """Callback invocato per ogni messaggio ricevuto."""
    import json
    try:
        data = json.loads(message.data.decode("utf-8"))
        print(f"Received: {data}, attributes: {dict(message.attributes)}")

        # Business logic
        process_event(data)

        # ACK obbligatorio — senza ACK il messaggio viene riconsegnato
        message.ack()
    except Exception as e:
        print(f"Error processing message {message.message_id}: {e}")
        # NACK — riconsegna immediata per retry
        message.nack()

# Configurazione flow control
flow_control = pubsub_v1.types.FlowControl(
    max_messages=100,          # max messaggi in volo contemporaneamente
    max_bytes=10 * 1024 * 1024  # max 10MB in memoria
)

streaming_pull_future = subscriber.subscribe(
    subscription_path,
    callback=callback,
    flow_control=flow_control
)
print(f"Listening for messages on {subscription_path}...")

# Blocca finché non viene interrotto
with subscriber:
    try:
        streaming_pull_future.result(timeout=None)
    except TimeoutError:
        streaming_pull_future.cancel()
        streaming_pull_future.result()
```

### Push Subscription

**Pub/Sub chiama un endpoint HTTP/HTTPS** per ogni messaggio. Il consumer non deve gestire connessioni — riceve chiamate POST. Ideale per Cloud Run, Cloud Functions, o qualsiasi endpoint HTTP.

```bash
# Creare una push subscription verso Cloud Run
gcloud pubsub subscriptions create my-push-sub \
    --topic=my-topic \
    --push-endpoint=https://my-service-xxxx-xx.a.run.app/pubsub \
    --push-auth-service-account=pubsub-invoker@my-project.iam.gserviceaccount.com \
    --ack-deadline=60

# Il SA pubsub-invoker deve avere roles/run.invoker sul servizio target
gcloud run services add-iam-policy-binding my-service \
    --region=europe-west8 \
    --member="serviceAccount:pubsub-invoker@my-project.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Dare al SA di Pub/Sub il permesso di creare token
# (necessario per push con autenticazione OIDC)
gcloud projects add-iam-policy-binding my-project \
    --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"
```

Il payload che arriva all'endpoint push ha questo formato:

```json
{
  "message": {
    "data": "eyJldmVudCI6ICJ1c2VyLmNyZWF0ZWQifQ==",
    "attributes": {
      "eventType": "user.created"
    },
    "messageId": "11627140583501765",
    "publishTime": "2026-03-31T10:00:00.000Z"
  },
  "subscription": "projects/my-project/subscriptions/my-push-sub"
}
```

```python
# Cloud Run handler per push subscription (Python/Flask)
import base64
import json
import flask

app = flask.Flask(__name__)

@app.route("/pubsub", methods=["POST"])
def pubsub_push():
    """Riceve messaggi Pub/Sub via push."""
    envelope = flask.request.get_json()
    if not envelope or "message" not in envelope:
        return "Bad Request: no message received", 400

    pubsub_message = envelope["message"]

    # Il payload è base64-encoded
    data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
    payload = json.loads(data)
    attributes = pubsub_message.get("attributes", {})

    try:
        process_event(payload, attributes)
        # HTTP 200/201/202/204 = ACK implicito
        return "OK", 200
    except Exception as e:
        # HTTP 4xx/5xx = NACK, Pub/Sub riprova con backoff
        return f"Error: {e}", 500
```

!!! warning "Timeout push subscription"
    Pub/Sub considera un messaggio non ACK se l'endpoint risponde con status 5xx o non risponde entro l'`ackDeadline`. Impostare `ackDeadline` coerente con il tempo di elaborazione del Cloud Run handler. Il retry usa backoff esponenziale.

### BigQuery Subscription

Scrive i messaggi direttamente su una tabella BigQuery **senza codice consumer**. Pub/Sub gestisce la conversione e l'ingestion.

```bash
# Prerequisito: la tabella BQ deve esistere con schema compatibile
# Creare la tabella BQ
bq mk --table my-project:my_dataset.pubsub_events \
    "data:BYTES,attributes:STRING,message_id:STRING,publish_time:TIMESTAMP,subscription_name:STRING"

# Creare BigQuery subscription
gcloud pubsub subscriptions create my-bq-sub \
    --topic=my-topic \
    --bigquery-table=my-project:my_dataset.pubsub_events \
    --write-metadata \       # include message_id, publish_time, subscription_name
    --drop-unknown-fields    # ignora attributi non presenti nello schema BQ

# Il SA di Pub/Sub deve avere permessi su BQ
gcloud projects add-iam-policy-binding my-project \
    --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"
```

### Cloud Storage Subscription

Scrive i messaggi su un bucket GCS come file, raggruppati per intervallo temporale o dimensione.

```bash
# Creare Cloud Storage subscription
gcloud pubsub subscriptions create my-gcs-sub \
    --topic=my-topic \
    --cloud-storage-bucket=my-archive-bucket \
    --cloud-storage-file-prefix=events/ \
    --cloud-storage-file-suffix=.json \
    --cloud-storage-max-bytes=100000000 \   # 100 MB per file
    --cloud-storage-max-duration=600s        # o ogni 10 minuti, il primo che scatta
```

---

## Configurazione & Pratica

### Gestione Topic e Subscription

```bash
# Creare topic
gcloud pubsub topics create my-topic \
    --message-retention-duration=7d    # retention del topic (default 7d, max 31d)

# Creare topic con schema (validazione messaggi)
gcloud pubsub schemas create user-event-schema \
    --type=AVRO \
    --definition-file=schema.avsc

gcloud pubsub topics create my-typed-topic \
    --schema=user-event-schema \
    --message-encoding=JSON

# Pubblicare messaggi
gcloud pubsub topics publish my-topic \
    --message='{"event":"user.created","userId":"123"}' \
    --attribute="eventType=user.created,region=eu"

# Pubblicare batch di messaggi (via SDK — gcloud non supporta batch nativo)
# Usare client library con batch settings per produzione

# Listare topic e subscription
gcloud pubsub topics list
gcloud pubsub subscriptions list
gcloud pubsub subscriptions describe my-pull-sub

# Eliminare subscription/topic
gcloud pubsub subscriptions delete my-pull-sub
gcloud pubsub topics delete my-topic   # elimina anche tutte le subscription
```

### Dead Letter Topic

```bash
# Creare il Dead Letter Topic
gcloud pubsub topics create my-topic-dlq

# Creare subscription per leggere i messaggi falliti dalla DLQ
gcloud pubsub subscriptions create my-topic-dlq-sub \
    --topic=my-topic-dlq

# Configurare DLT sulla subscription principale
gcloud pubsub subscriptions modify-config my-pull-sub \
    --dead-letter-topic=my-topic-dlq \
    --max-delivery-attempts=5    # dopo 5 tentativi → DLQ

# Il SA di Pub/Sub deve avere permessi su topic e subscription DLQ
PROJECT_NUMBER=$(gcloud projects describe my-project --format="value(projectNumber)")
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud pubsub topics add-iam-policy-binding my-topic-dlq \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="roles/pubsub.publisher"

gcloud pubsub subscriptions add-iam-policy-binding my-pull-sub \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="roles/pubsub.subscriber"
```

### Message Ordering

Per default, Pub/Sub non garantisce l'ordine di consegna. Abilitando l'ordering, messaggi con lo stesso `orderingKey` vengono consegnati in ordine:

```bash
# Creare subscription con ordering abilitato
gcloud pubsub subscriptions create my-ordered-sub \
    --topic=my-topic \
    --enable-message-ordering

# Publicare con ordering key (tutti i msg con stesso key → in ordine)
gcloud pubsub topics publish my-topic \
    --message='{"orderId":"ORD-001","step":1}' \
    --ordering-key="customer-456"

gcloud pubsub topics publish my-topic \
    --message='{"orderId":"ORD-001","step":2}' \
    --ordering-key="customer-456"
```

!!! warning "Ordering e parallelismo"
    Con ordering abilitato, messaggi con lo stesso `orderingKey` non possono essere processati in parallelo — sono sequenziali per design. Usare ordering key granulare (es. `userId` o `orderId`) per mantenere parallelismo tra chiavi diverse. Se un messaggio fallisce e va in retry, Pub/Sub sospende la consegna per quella ordering key finché il messaggio non viene ACK.

### Snapshot e Seek — Replay

Pub/Sub permette di **tornare indietro** nella timeline dei messaggi tramite seek:

```bash
# Creare uno snapshot del checkpoint attuale
gcloud pubsub snapshots create my-snapshot \
    --subscription=my-pull-sub

# Tornare al checkpoint dello snapshot (replay tutti i messaggi da quel punto)
gcloud pubsub subscriptions seek my-pull-sub \
    --snapshot=my-snapshot

# Seek a un timestamp specifico (es. 30 minuti fa)
gcloud pubsub subscriptions seek my-pull-sub \
    --time="2026-03-31T10:00:00Z"

# Seek al futuro (scartare tutti i messaggi non ancora ACK)
gcloud pubsub subscriptions seek my-pull-sub \
    --time="2099-01-01T00:00:00Z"

# Listare snapshot disponibili
gcloud pubsub snapshots list
```

---

## IAM su Pub/Sub

### Ruoli Principali

| Ruolo | Permessi | Use case |
|---|---|---|
| `roles/pubsub.publisher` | `topics.publish` | Producer — può solo pubblicare |
| `roles/pubsub.subscriber` | `subscriptions.consume` | Consumer — può solo leggere/ACK |
| `roles/pubsub.viewer` | Lista topic e subscription | Monitoring, audit |
| `roles/pubsub.editor` | Crea/modifica topic e subscription | CI/CD, Terraform |
| `roles/pubsub.admin` | Tutto incluso IAM | Amministrazione |

```bash
# Publisher: solo permesso di pubblicare su un topic specifico
gcloud pubsub topics add-iam-policy-binding my-topic \
    --member="serviceAccount:producer-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher"

# Subscriber: solo permesso di leggere da una subscription specifica
gcloud pubsub subscriptions add-iam-policy-binding my-pull-sub \
    --member="serviceAccount:consumer-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/pubsub.subscriber"

# Verificare policy IAM attive su un topic
gcloud pubsub topics get-iam-policy my-topic

# Verificare policy IAM attive su una subscription
gcloud pubsub subscriptions get-iam-policy my-pull-sub
```

### Workload Identity per GKE

Per consumer su GKE, usare Workload Identity anziché export di chiavi JSON:

```bash
# Prerequisito: GKE con Workload Identity abilitato
# Creare Service Account GCP
gcloud iam service-accounts create pubsub-consumer-sa \
    --display-name="Pub/Sub Consumer SA"

# Dare al SA GCP il permesso di subscriber
gcloud pubsub subscriptions add-iam-policy-binding my-pull-sub \
    --member="serviceAccount:pubsub-consumer-sa@my-project.iam.gserviceaccount.com" \
    --role="roles/pubsub.subscriber"

# Collegare SA GCP al Kubernetes Service Account
gcloud iam service-accounts add-iam-policy-binding \
    pubsub-consumer-sa@my-project.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:my-project.svc.id.goog[my-namespace/my-ksa]"

# Annotare il Kubernetes Service Account
kubectl annotate serviceaccount my-ksa \
    --namespace my-namespace \
    iam.gke.io/gcp-service-account=pubsub-consumer-sa@my-project.iam.gserviceaccount.com
```

!!! tip "Principio del minimo privilegio"
    Un publisher non deve avere `roles/pubsub.subscriber` e viceversa. Creare SA separati per producer e consumer, ciascuno con binding sul topic o sulla subscription specifica — non sul progetto intero. Questo limita l'impatto in caso di compromissione.

---

## Pattern di Integrazione

### Pub/Sub → Cloud Run (Trigger Serverless)

Pattern equivalente a SQS→Lambda su AWS: un messaggio in Pub/Sub triggera un'istanza Cloud Run.

```bash
# Opzione 1: Push subscription verso Cloud Run
# (vedere sezione Push Subscription sopra)

# Opzione 2: Eventarc (trigger Cloud Run da eventi Pub/Sub)
gcloud eventarc triggers create my-trigger \
    --location=europe-west8 \
    --service-account=eventarc-sa@my-project.iam.gserviceaccount.com \
    --destination-run-service=my-cloud-run-service \
    --destination-run-region=europe-west8 \
    --event-filters="type=google.cloud.pubsub.topic.v1.messagePublished" \
    --transport-topic=my-topic
```

### Fan-Out: Un Topic, Più Consumer

```bash
# 1 topic → 3 subscription indipendenti → 3 consumer diversi
gcloud pubsub topics create order-events

# Consumer 1: servizio inventory (pull)
gcloud pubsub subscriptions create inventory-sub \
    --topic=order-events \
    --ack-deadline=30

# Consumer 2: servizio notifiche (push → Cloud Run)
gcloud pubsub subscriptions create notifications-sub \
    --topic=order-events \
    --push-endpoint=https://notifications-xxxx.a.run.app/events \
    --push-auth-service-account=pubsub-push-sa@my-project.iam.gserviceaccount.com

# Consumer 3: analytics diretta su BigQuery
gcloud pubsub subscriptions create analytics-bq-sub \
    --topic=order-events \
    --bigquery-table=my-project:analytics.order_events \
    --write-metadata

# Pubblicare un ordine → arriva a tutti e 3 i consumer automaticamente
gcloud pubsub topics publish order-events \
    --message='{"orderId":"ORD-999","amount":299.99,"customerId":"CUST-123"}'
```

### Pub/Sub → Dataflow (Stream Processing)

```bash
# Template Dataflow per Pub/Sub → BigQuery con trasformazioni
gcloud dataflow jobs run pubsub-to-bq \
    --gcs-location=gs://dataflow-templates/latest/PubSub_to_BigQuery \
    --region=europe-west8 \
    --parameters \
inputTopic=projects/my-project/topics/my-topic,\
outputTableSpec=my-project:my_dataset.output_table,\
outputDeadletterTable=my-project:my_dataset.errors
```

---

## Monitoring e Observability

### Metriche Chiave

```bash
# Visualizzare le metriche principali di una subscription
gcloud monitoring metrics list \
    --filter="metric.type:pubsub.googleapis.com/subscription"

# Le metriche più importanti (via Cloud Monitoring / Metrics Explorer):
# subscription/num_undelivered_messages     — messaggi in attesa di ACK (backlog)
# subscription/oldest_unacked_message_age   — età del messaggio più vecchio non ACK (CRITICA)
# subscription/num_outstanding_messages     — messaggi inviati al consumer ma non ancora ACK
# topic/send_message_operation_count        — rate di pubblicazione
# subscription/pull_message_operation_count — rate di consumo
```

```bash
# Creare alert su backlog crescente (subscription/oldest_unacked_message_age > 300s)
gcloud alpha monitoring policies create \
    --notification-channels=CHANNEL_ID \
    --display-name="Pub/Sub Consumer Lag Alert" \
    --condition-display-name="Oldest unacked message age > 5 min" \
    --condition-filter='resource.type="pubsub_subscription" AND metric.type="pubsub.googleapis.com/subscription/oldest_unacked_message_age"' \
    --condition-threshold-value=300 \
    --condition-threshold-comparison=COMPARISON_GT \
    --condition-duration=120s
```

!!! tip "Metrica più importante: oldest_unacked_message_age"
    `subscription/oldest_unacked_message_age` è l'indicatore principale di salute di un consumer Pub/Sub. Se questa metrica cresce, il consumer è in ritardo rispetto alla produzione. Un alert su questa metrica con soglia 5-10 minuti permette di rilevare problemi prima che il backlog diventi critico.

---

## Confronto con AWS e Kafka

| Feature | Cloud Pub/Sub | AWS SQS/SNS | Apache Kafka |
|---|---|---|---|
| **Modello** | Pub/Sub managed | Queue (SQS) + Pub/Sub (SNS) | Log distribuito con partizioni |
| **Retention** | Max 31 giorni | Max 14 giorni (SQS) | Illimitata (configurabile) |
| **Replay** | Snapshot + seek | No (SQS) | Offset su partition |
| **Partizioni** | Automatiche (invisibili) | N/A | Manuali, configurabili |
| **Multi-region** | Default (nessuna config) | Cross-region manuale | Mirror Maker o Confluent |
| **Ordering** | Per ordering key | FIFO queue separata | Per partition |
| **Exactly-once** | Abilitabile | SQS FIFO | Kafka Streams + idempotent producer |
| **Max msg size** | 10 MB | 256 KB (2 GB con S3) | 1 MB (default, configurabile) |
| **Scalabilità** | Automatica, serverless | Automatica | Manuale (aumento partizioni) |
| **Gestione** | Zero ops | Zero ops | Alto overhead ops (a meno di Confluent) |
| **Cost model** | Per messaggio + storage | Per richiesta + GB | VM/cluster + storage |

---

## Best Practices

!!! tip "Impostare sempre il Dead Letter Topic"
    Ogni subscription in produzione deve avere un Dead Letter Topic con `--max-delivery-attempts` configurato (tipicamente 5-10). Senza DLT, i messaggi che il consumer non riesce ad elaborare rimangono nel backlog indefinitamente, bloccando l'avanzamento in caso di ordering o consumando risorse.

!!! warning "Non ACK prima di elaborare"
    Il pattern `message.ack()` deve essere chiamato SOLO dopo che l'elaborazione è andata a buon fine. ACK immediato all'arrivo del messaggio e poi errore = messaggio perso. Usare `message.nack()` in caso di errore per forzare la riconsegna immediata.

```bash
# Checklist best practices Pub/Sub:
# [ ] Dead Letter Topic configurato su ogni subscription di produzione
# [ ] ackDeadline > max elaboration time (con margine 2x)
# [ ] Consumer idempotenti (at-least-once delivery di default)
# [ ] SA separati per publisher e subscriber (minimo privilegio)
# [ ] Workload Identity per consumer su GKE (no service account key files)
# [ ] Alert su oldest_unacked_message_age > 5 min
# [ ] Alert su num_undelivered_messages DLT > 0
# [ ] Retention topic adeguata al caso d'uso (default 7d ok per la maggior parte)
# [ ] StreamingPull via client library ufficiale (non pull manuale in loop)
# [ ] message.nack() invece di ignorare eccezioni nel callback
```

---

## Troubleshooting

**Problema: Backlog cresce — `num_undelivered_messages` sale continuamente**

```bash
# Sintomo: la metrica subscription/num_undelivered_messages aumenta nel tempo
# o subscription/oldest_unacked_message_age supera minuti/ore
# Causa: il consumer è lento o bloccato, oppure non sta scalando abbastanza

# Diagnosi 1: verificare se il consumer sta girando
gcloud pubsub subscriptions describe my-pull-sub \
    --format="table(name,pushConfig,ackDeadlineSeconds)"

# Diagnosi 2: controllare il rate di consumo vs produzione nelle ultime 1h
# Via Metrics Explorer su Cloud Monitoring:
# - topic/send_message_operation_count (produzione)
# - subscription/pull_message_operation_count (consumo)
# Se produzione >> consumo → consumer troppo lento

# Soluzione 1: aumentare parallelismo nel consumer
# Per GKE: aumentare replicas del deployment consumer
kubectl scale deployment pubsub-consumer --replicas=10

# Soluzione 2: aumentare flow control nella client library
# flow_control = FlowControl(max_messages=500)  # più messaggi in parallelo

# Soluzione 3: seek al futuro per scartare il backlog accumulato (DISTRUTTIVO)
# Usare SOLO se i messaggi nel backlog non hanno più valore
gcloud pubsub subscriptions seek my-pull-sub \
    --time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

---

**Problema: Push subscription — Cloud Run riceve 403 Forbidden su ogni messaggio**

```bash
# Sintomo: il push endpoint risponde 403, Pub/Sub non consegna i messaggi
# Causa: il SA usato per la push subscription non ha roles/run.invoker
# oppure il SA del sistema Pub/Sub non ha il permesso di creare token OIDC

# Diagnosi: verificare il SA configurato sulla subscription
gcloud pubsub subscriptions describe my-push-sub \
    --format="value(pushConfig.oidcToken.serviceAccountEmail)"

# Soluzione 1: dare roles/run.invoker al SA della push subscription
gcloud run services add-iam-policy-binding my-service \
    --region=europe-west8 \
    --member="serviceAccount:pubsub-invoker@my-project.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Soluzione 2: autorizzare il SA Pub/Sub a creare token OIDC
PROJECT_NUMBER=$(gcloud projects describe my-project --format="value(projectNumber)")
gcloud projects add-iam-policy-binding my-project \
    --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"
```

---

**Problema: Messaggi con ordering key bloccati — nuovi messaggi non arrivano**

```bash
# Sintomo: con message ordering abilitato, i messaggi con una certa ordering key
# smettono di essere consegnati anche se ci sono nuovi messaggi pubblicati
# Causa: un messaggio precedente con quella ordering key è in stato di retry
# Pub/Sub non consegna messaggi successivi finché il precedente non è ACK

# Diagnosi: verificare se ci sono messaggi non ACK per quella ordering key
gcloud pubsub subscriptions describe my-ordered-sub

# Soluzione: identificare il messaggio bloccato (nel log del consumer)
# e decidere: fixare il consumer oppure fare seek per saltare il messaggio problematico

# Seek al timestamp del primo messaggio problematico (salta i messaggi bloccati)
gcloud pubsub subscriptions seek my-ordered-sub \
    --time="2026-03-31T10:30:00Z"

# Oppure: seek allo snapshot precedente al problema
gcloud pubsub subscriptions seek my-ordered-sub \
    --snapshot=pre-incident-snapshot
```

---

**Problema: Dead Letter Topic non riceve messaggi anche dopo molti retry**

```bash
# Sintomo: i messaggi continuano a essere riconsegnati ma non vanno in DLQ
# anche dopo aver superato max-delivery-attempts
# Causa: il SA di Pub/Sub non ha i permessi corretti su DLT o subscription

# Diagnosi: verificare la configurazione DLT
gcloud pubsub subscriptions describe my-pull-sub \
    --format="value(deadLetterPolicy)"

# Ottenere il SA del sistema Pub/Sub
PROJECT_NUMBER=$(gcloud projects describe my-project --format="value(projectNumber)")
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

# Verificare i permessi del SA Pub/Sub
gcloud pubsub topics get-iam-policy my-topic-dlq | grep "$PUBSUB_SA"
gcloud pubsub subscriptions get-iam-policy my-pull-sub | grep "$PUBSUB_SA"

# Soluzione: aggiungere i permessi mancanti
gcloud pubsub topics add-iam-policy-binding my-topic-dlq \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="roles/pubsub.publisher"

gcloud pubsub subscriptions add-iam-policy-binding my-pull-sub \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="roles/pubsub.subscriber"
```

---

**Problema: BigQuery subscription — messaggi non arrivano nella tabella BQ**

```bash
# Sintomo: la subscription è creata ma la tabella BQ rimane vuota
# Causa più comune: schema incompatibile o permessi mancanti del SA Pub/Sub su BQ

# Diagnosi 1: verificare i permessi del SA su BigQuery
PROJECT_NUMBER=$(gcloud projects describe my-project --format="value(projectNumber)")
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
bq show --format=prettyjson my-project:my_dataset | grep "$PUBSUB_SA"

# Soluzione 1: aggiungere dataEditor al SA Pub/Sub
gcloud projects add-iam-policy-binding my-project \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="roles/bigquery.dataEditor"

# Diagnosi 2: verificare che la tabella abbia le colonne richieste
bq show my-project:my_dataset.pubsub_events

# Colonne richieste per BigQuery subscription con --write-metadata:
# data BYTES, attributes STRING, message_id STRING,
# publish_time TIMESTAMP, subscription_name STRING
```

---

## Relazioni

??? info "Cloud Run — Consumer Push Serverless"
    Cloud Run è il target naturale delle push subscription: Pub/Sub chiama direttamente l'endpoint HTTP del servizio Cloud Run, senza polling. Il pattern è equivalente a SQS→Lambda su AWS. Per l'autenticazione, Cloud Run verifica il token OIDC nel header Authorization iniettato da Pub/Sub.

    **Approfondimento →** [Cloud Run](../compute/cloud-run.md)

??? info "BigQuery — Ingestion Near-Realtime"
    La BigQuery subscription elimina il codice consumer per use case analitici: Pub/Sub scrive direttamente i messaggi nella tabella BQ, abilitando query in near-realtime senza pipeline Dataflow. Per trasformazioni sui dati prima dell'ingestion, usare invece Dataflow con sorgente Pub/Sub.

    **Approfondimento →** [BigQuery](../dati/bigquery.md)

??? info "IAM Service Accounts — Identità Publisher e Subscriber"
    Publisher e subscriber devono usare Service Account separati con binding IAM granulari (sul topic o sulla subscription specifica, non sul progetto). Su GKE, usare Workload Identity per eliminare la gestione di chiavi JSON.

    **Approfondimento →** [IAM & Service Accounts](../iam/iam-service-accounts.md)

---

## Riferimenti

- [Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Pub/Sub Subscriber Overview](https://cloud.google.com/pubsub/docs/subscriber)
- [Push Subscription Authentication](https://cloud.google.com/pubsub/docs/push#authentication)
- [Dead Letter Topics](https://cloud.google.com/pubsub/docs/dead-letter-topics)
- [Ordering Messages](https://cloud.google.com/pubsub/docs/ordering)
- [Exactly-Once Delivery](https://cloud.google.com/pubsub/docs/exactly-once-delivery)
- [Pub/Sub Pricing](https://cloud.google.com/pubsub/pricing)
- [Pub/Sub Quotas and Limits](https://cloud.google.com/pubsub/quotas)
- [Pub/Sub Python Client Library](https://cloud.google.com/python/docs/reference/pubsub/latest)
- [Pub/Sub Monitoring](https://cloud.google.com/pubsub/docs/monitoring)
