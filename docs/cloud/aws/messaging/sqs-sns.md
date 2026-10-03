---
title: "SQS & SNS"
slug: sqs-sns
category: cloud
tags: [aws, sqs, sns, messaging, queue, pub-sub, dlq, fifo, fan-out, ses]
search_keywords: [AWS SQS, Simple Queue Service, FIFO queue, Standard queue, SNS Simple Notification Service, Dead Letter Queue DLQ, visibility timeout, long polling, message filtering, fan-out pattern, SNS mobile push, SES Simple Email Service, message deduplication, message group ID, extended client library, delay queue]
parent: cloud/aws/messaging/_index
related: [cloud/aws/messaging/eventbridge-kinesis, cloud/aws/compute/lambda, cloud/aws/security/kms-secrets]
official_docs: https://docs.aws.amazon.com/sqs/
status: needs-review
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# SQS & SNS

## Amazon SQS — Simple Queue Service

**SQS** è un servizio di code distribuito completamente gestito. Permette di **disaccoppiare** componenti di un'applicazione con garanzie di consegna configurabili.

### SQS Standard vs FIFO

| Caratteristica | Standard | FIFO |
|---------------|----------|------|
| Throughput | Praticamente illimitato | Default 300 API call/s per azione (3000 msg/s con batching); la **high throughput mode** arriva a decine di migliaia di msg/s (limiti per region, vedi doc) |
| Ordering | Best-effort | Garantito (per MessageGroupId) |
| Delivery | At-least-once (possibili duplicati) | Exactly-once processing (dedup lato SQS) |
| Deduplicazione | No | Sì (5 minuti dedup window) |
| Naming | `nome` | `nome.fifo` |
| Dead Letter Queue | Sì | Sì (la DLQ deve essere anch'essa FIFO) |
| Lambda trigger | Sì | Sì |
| Prezzo | Più basso | Leggermente più alto (~25% per richiesta, verificare pricing della region) |
| Use case | Worker pool, task idempotenti | Ordini, transazioni, sequenze |

!!! note "Perché at-least-once"
    Standard replica i messaggi su più server: una `DeleteMessage` può non raggiungere tutte le repliche e il messaggio può essere riconsegnato. I consumer Standard vanno quindi scritti **idempotenti**.

### Parametri Chiave

| Parametro | Default | Range | Descrizione |
|-----------|---------|-------|-------------|
| Message Retention | 4 giorni | 1 min - 14 giorni | Quanto a lungo SQS conserva i messaggi |
| Visibility Timeout | 30s | 0s - 12h | Tempo per processare il messaggio prima che riappaia |
| Message Size | 1 MiB | 1 B - 1 MiB | Payload massimo (portato da 256 KB a 1 MiB nel 2025; oltre → S3 + Extended Client) |
| Long Polling Wait | 0s | 0-20s | `ReceiveMessageWaitTimeSeconds` — riduce costi |
| Delivery Delay | 0s | 0s - 15 min | Ritardo prima che il messaggio sia visibile |
| Batch Size | 1 | 1-10 (Standard), 1-10 (FIFO) | Messaggi per operazione Send/Receive/Delete |

---

### Creare e Usare Code SQS

```bash
# Creare coda Standard
aws sqs create-queue \
    --queue-name myapp-queue \
    --attributes '{
        "MessageRetentionPeriod": "86400",
        "VisibilityTimeout": "60",
        "ReceiveMessageWaitTimeSeconds": "20",
        "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:eu-central-1:123456789012:myapp-dlq\",\"maxReceiveCount\":\"3\"}"
    }'

# Creare coda FIFO
aws sqs create-queue \
    --queue-name orders.fifo \
    --attributes '{
        "FifoQueue": "true",
        "ContentBasedDeduplication": "true",
        "VisibilityTimeout": "30",
        "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:eu-central-1:123456789012:orders-dlq.fifo\",\"maxReceiveCount\":\"5\"}"
    }'

# Creare DLQ prima (la coda principale la referenzia)
aws sqs create-queue \
    --queue-name myapp-dlq \
    --attributes '{"MessageRetentionPeriod": "1209600"}' # 14 giorni

# Inviare messaggio
aws sqs send-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --message-body '{"event": "user.created", "userId": "123"}'

# Inviare con delay (messaggio visibile tra 30 secondi)
aws sqs send-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --message-body '{"event": "reminder"}' \
    --delay-seconds 30

# Inviare batch (fino a 10 messaggi, max 1 MiB totale)
aws sqs send-message-batch \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --entries '[
        {"Id": "1", "MessageBody": "{\"id\":1}"},
        {"Id": "2", "MessageBody": "{\"id\":2}"},
        {"Id": "3", "MessageBody": "{\"id\":3}"}
    ]'

# Ricevere messaggi (long polling con wait 20s)
aws sqs receive-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --max-number-of-messages 10 \
    --wait-time-seconds 20 \
    --attribute-names All \
    --message-attribute-names All

# Cancellare messaggio dopo elaborazione (OBBLIGATORIO)
aws sqs delete-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --receipt-handle "AQEB..."

# Estendere visibility timeout (se l'elaborazione richiede più tempo)
aws sqs change-message-visibility \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --receipt-handle "AQEB..." \
    --visibility-timeout 120
```

---

### Visibility Timeout — Meccanismo Fondamentale

```
SQS Lifecycle

  Producer → [Send] → Coda: [ Msg A | Msg B | Msg C ]
                                    │
                            Consumer 1 → [Receive Msg A]
                                    │
                            Msg A invisibile per VisibilityTimeout (60s)
                                    │
                     ┌──────────────┴───────────────────┐
                     │                                   │
              [Delete Msg A]               Timeout scade → Msg A
              (elaborazione OK)            riappare in coda (retry)
```

**Best practice:**
- Imposta `VisibilityTimeout > tempo_max_elaborazione` (con margine 2-3x)
- Se un job supera il tempo previsto → chiama `ChangeMessageVisibility` per estenderlo
- `maxReceiveCount` in RedrivePolicy = massimo retry prima di andare in DLQ
- Con Lambda come consumer: `VisibilityTimeout` ≥ 6× il timeout della funzione (raccomandazione AWS), altrimenti i messaggi riappaiono mentre la funzione li sta ancora elaborando
- La retention della DLQ decorre dal momento di **enqueue originale** (non dall'arrivo in DLQ): impostala più lunga della coda sorgente (es. 14 giorni vs 4)
- Cifratura: SSE-SQS (chiavi gestite da SQS) è attiva di default sulle nuove code; usa SSE-KMS solo se serve controllo sulla chiave (vedi `kms-secrets`)

---

### FIFO Queue — Ordinamento e Deduplicazione

```bash
# FIFO richiede MessageGroupId (ordinamento) e MessageDeduplicationId
aws sqs send-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/orders.fifo \
    --message-body '{"orderId": "ORD-001", "amount": 99.99}' \
    --message-group-id "customer-456" \
    --message-deduplication-id "ORD-001-v1"

# --message-group-id: tutti i msg del customer-456 in ordine
# --message-deduplication-id: stesso ID = stesso messaggio (scartato entro 5 min)

# MessageGroupId: definisce il "gruppo di ordinamento"
# - Messaggi con stesso GroupId sono consegnati in ordine FIFO
# - Messaggi con GroupId diversi sono indipendenti (parallelismo)

# ContentBasedDeduplication=true → SHA-256 del body come deduplication ID automatico
```

---

### Dead Letter Queue (DLQ)

```bash
# Visualizzare messaggi in DLQ
aws sqs receive-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-dlq \
    --max-number-of-messages 10

# DLQ Redrive — rispedire messaggi dalla DLQ alla coda sorgente
# (console dal 2021; API start-message-move-task dal 2023; funziona anche con DLQ FIFO)
aws sqs start-message-move-task \
    --source-arn arn:aws:sqs:eu-central-1:123456789012:myapp-dlq \
    --destination-arn arn:aws:sqs:eu-central-1:123456789012:myapp-queue \
    --max-number-of-messages-per-second 5

# Monitorare DLQ con CloudWatch Alarm
aws cloudwatch put-metric-alarm \
    --alarm-name sqs-dlq-messages \
    --alarm-description "Messages in DLQ" \
    --namespace AWS/SQS \
    --metric-name ApproximateNumberOfMessagesVisible \
    --dimensions Name=QueueName,Value=myapp-dlq \
    --statistic Sum \
    --period 60 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --evaluation-periods 1 \
    --alarm-actions arn:aws:sns:...:ops-alerts
```

---

### Lambda come Consumer SQS

```bash
# Configurare Event Source Mapping Lambda → SQS
aws lambda create-event-source-mapping \
    --function-name ProcessOrders \
    --event-source-arn arn:aws:sqs:eu-central-1:123456789012:orders.fifo \
    --batch-size 10 \
    --maximum-batching-window-in-seconds 5 \
    --function-response-types '["ReportBatchItemFailures"]'

# ReportBatchItemFailures = partial batch failure support.
# Per code Standard limitare la concorrenza ed evitare di saturare i downstream:
#   --scaling-config MaximumConcurrency=10
```

Senza `ReportBatchItemFailures` un errore su **un** record rimette in coda l'intero batch, con rielaborazione dei messaggi già riusciti. In una coda FIFO, al primo errore smetti di elaborare il resto del gruppo e restituisci come failure anche i record successivi dello stesso `MessageGroupId`, per preservare l'ordine.

```python
# Lambda handler con partial batch failure
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    batch_item_failures = []

    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            process_order(body)
        except Exception as e:
            logger.error(f"Failed to process {record['messageId']}: {e}")
            # Solo questo messaggio tornerà in coda, non l'intero batch
            batch_item_failures.append({"itemIdentifier": record['messageId']})

    return {"batchItemFailures": batch_item_failures}

def process_order(order):
    # business logic
    logger.info(f"Processing order: {order}")
```

---

### SQS Extended Client Library

Per messaggi **oltre 1 MiB** (fino a 2 GB), il payload viene salvato su S3 e nella coda viaggia solo un puntatore. Soglia configurabile: con `always_through_s3=False` si usa S3 solo oltre la soglia.

<!-- REVIEW: verificare nome pacchetto/API della libreria Python (sqs-extended-client) sulla versione corrente -->
```python
# Python — boto3 + sqs-extended-client
# pip install sqs-extended-client

import boto3
import json
import sqs_extended_client  # noqa: F401 — estende il client boto3 con gli attributi sotto

sqs = boto3.client('sqs', region_name='eu-central-1')
sqs.large_payload_support = 'my-large-messages-bucket'  # bucket S3
sqs.always_through_s3 = False  # True = sempre via S3, False = solo oltre la soglia
sqs.message_size_threshold = 1024 * 1024

# Inviare messaggio grande (automaticamente su S3)
sqs.send_message(
    QueueUrl='https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue',
    MessageBody=json.dumps(large_data_object)
)

# Il consumer riceve il riferimento S3 → lo risolve automaticamente
message = sqs.receive_message(
    QueueUrl='https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue'
)
body = json.loads(message['Messages'][0]['Body'])  # già risolto da S3
```

---

### Queue Policy (Resource-Based Policy)

```bash
# Permettere a SNS di inviare messaggi alla queue (obbligatorio per SNS→SQS)
aws sqs set-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --attributes '{
        "Policy": "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"sns.amazonaws.com\"},\"Action\":\"sqs:SendMessage\",\"Resource\":\"arn:aws:sqs:eu-central-1:123456789012:myapp-queue\",\"Condition\":{\"ArnLike\":{\"aws:SourceArn\":\"arn:aws:sns:eu-central-1:123456789012:myapp-topic\"}}}]}"
    }'
```

La condition `aws:SourceArn` è essenziale: senza di essa **qualsiasi** topic SNS (anche di altri account) potrebbe scrivere nella coda (confused deputy).

---

## Amazon SNS — Simple Notification Service

**SNS** è un servizio di **pub/sub** completamente gestito. I producer inviano messaggi a un **topic** e SNS li distribuisce a tutti i subscriber.

### Tipi di Subscriber

| Subscriber | Protocollo | Note |
|-----------|------------|------|
| SQS | `sqs` | Fan-out più comune |
| Lambda | `lambda` | Direct invocation |
| HTTP/HTTPS | `http`, `https` | Webhook |
| Email | `email`, `email-json` | Notifiche ops |
| SMS | `sms` | Mobile notification |
| Mobile Push | `application` | APNS (Apple Push Notification Service — iOS), FCM (Firebase Cloud Messaging — Android), ADM (Amazon Device Messaging) |
| Kinesis Firehose | `firehose` | Streaming analytics |
| SES (via Lambda) | - | Email transazionali avanzate |

### Creare Topic e Sottoscrizioni

```bash
# Creare topic Standard
SNS_ARN=$(aws sns create-topic \
    --name myapp-topic \
    --query 'TopicArn' \
    --output text)

# Creare topic FIFO (subscriber ammessi: code SQS FIFO e, dal 2023, anche Standard)
aws sns create-topic \
    --name orders.fifo \
    --attributes '{
        "FifoTopic": "true",
        "ContentBasedDeduplication": "true"
    }'

# Sottoscrivere SQS al topic
aws sns subscribe \
    --topic-arn $SNS_ARN \
    --protocol sqs \
    --notification-endpoint arn:aws:sqs:eu-central-1:123456789012:myapp-queue

# Sottoscrivere Lambda
aws sns subscribe \
    --topic-arn $SNS_ARN \
    --protocol lambda \
    --notification-endpoint arn:aws:lambda:eu-central-1:123456789012:function:ProcessEvent

# Sottoscrivere email (richiede conferma)
aws sns subscribe \
    --topic-arn $SNS_ARN \
    --protocol email \
    --notification-endpoint ops-team@company.com

# Sottoscrivere HTTPS endpoint
aws sns subscribe \
    --topic-arn $SNS_ARN \
    --protocol https \
    --notification-endpoint https://webhook.company.com/events

# Pubblicare messaggio
aws sns publish \
    --topic-arn $SNS_ARN \
    --message '{"event": "user.created", "userId": "123"}' \
    --subject "New User Registration" \
    --message-attributes '{
        "eventType": {"DataType": "String", "StringValue": "user.created"},
        "region": {"DataType": "String", "StringValue": "eu-central-1"}
    }'

# Pubblicare con payload diverso per ogni protocollo (MessageStructure=json)
aws sns publish \
    --topic-arn $SNS_ARN \
    --message-structure json \
    --message '{
        "default": "New user registered",
        "sqs": "{\"event\": \"user.created\", \"userId\": \"123\", \"detailed\": true}",
        "email": "A new user has registered on your platform.",
        "http": "{\"event\": \"user.created\", \"userId\": \"123\"}"
    }'
```

---

### Subscription Filter Policy

I **filtri** permettono a ogni subscriber di ricevere SOLO i messaggi che lo interessano:

```bash
# Aggiungere filter policy a una sottoscrizione
SUBSCRIPTION_ARN="arn:aws:sns:eu-central-1:123456789012:myapp-topic:xxxx-xxxx"

# Subscriber 1: riceve solo eventi "order.*" dalla regione EU
aws sns set-subscription-attributes \
    --subscription-arn $SUBSCRIPTION_ARN \
    --attribute-name FilterPolicy \
    --attribute-value '{
        "eventType": ["order.created", "order.completed", "order.cancelled"],
        "region": ["eu-central-1", "eu-west-1"]
    }'

# Subscriber 2: riceve tutto tranne "user.deleted"
aws sns set-subscription-attributes \
    --subscription-arn $SUBSCRIPTION_ARN_2 \
    --attribute-name FilterPolicy \
    --attribute-value '{
        "eventType": [{"anything-but": "user.deleted"}]
    }'

# Subscriber 3: riceve ordini con amount > 100 (numeric filter)
aws sns set-subscription-attributes \
    --subscription-arn $SUBSCRIPTION_ARN_3 \
    --attribute-name FilterPolicy \
    --attribute-value '{
        "amount": [{"numeric": [">", 100]}]
    }'
```

**Filter policy operators:**
- `"value"` — esatta corrispondenza (stringa o numero)
- `{"anything-but": "value"}` — tutto tranne questo valore
- `{"prefix": "order"}` — inizia con prefisso
- `{"suffix": ".error"}` — finisce con suffisso
- `{"numeric": [">", 100]}` — confronto numerico (`>`, `>=`, `<`, `<=`, `=`)
- `{"exists": true}` — attributo presente/assente
- `{"equals-ignore-case": "Order"}` — confronto case-insensitive

Più chiavi nella stessa policy sono in **AND**; più valori nello stesso array in **OR**. Di default il filtro si applica ai `MessageAttributes`; con `FilterPolicyScope=MessageBody` si filtra sul JSON del body (utile quando il publisher non può impostare attributi, es. eventi S3 o CloudWatch). I messaggi scartati dal filtro non costano consegna e non arrivano al subscriber.

---

### Fan-Out Pattern — SNS → Multiple SQS

```bash
# Pattern classico: 1 producer → 1 SNS topic → N SQS queues

# Creare topic
aws sns create-topic --name order-events

# Creare code SQS per i diversi consumer
aws sqs create-queue --queue-name inventory-service-queue
aws sqs create-queue --queue-name notification-service-queue
aws sqs create-queue --queue-name analytics-service-queue

# Impostare queue policies (permettere a SNS di inviare messaggi)
for QUEUE in inventory-service-queue notification-service-queue analytics-service-queue; do
    QUEUE_URL=$(aws sqs get-queue-url --queue-name $QUEUE --query 'QueueUrl' --output text)
    QUEUE_ARN=$(aws sqs get-queue-attributes \
        --queue-url $QUEUE_URL \
        --attribute-names QueueArn \
        --query 'Attributes.QueueArn' --output text)

    aws sqs set-queue-attributes \
        --queue-url $QUEUE_URL \
        --attributes "{\"Policy\": \"{\\\"Version\\\":\\\"2012-10-17\\\",\\\"Statement\\\":[{\\\"Effect\\\":\\\"Allow\\\",\\\"Principal\\\":{\\\"Service\\\":\\\"sns.amazonaws.com\\\"},\\\"Action\\\":\\\"sqs:SendMessage\\\",\\\"Resource\\\":\\\"$QUEUE_ARN\\\",\\\"Condition\\\":{\\\"ArnEquals\\\":{\\\"aws:SourceArn\\\":\\\"arn:aws:sns:eu-central-1:123456789012:order-events\\\"}}}]}\"}"

    # Sottoscrivere la coda al topic SNS
    aws sns subscribe \
        --topic-arn arn:aws:sns:eu-central-1:123456789012:order-events \
        --protocol sqs \
        --notification-endpoint $QUEUE_ARN
done
```

**Vantaggi del fan-out SNS→SQS:**
- Ogni consumer ha la sua coda → fallimento di uno non impatta gli altri
- Consumer possono processare a velocità diverse
- DLQ separata per ogni consumer
- Filtri per consumer selettivi

---

### SNS Mobile Push

```bash
# Creare Platform Application (AWS gestisce token device)
# --platform: APNS (iOS), GCM (Android: nome API storico, oggi usa FCM), ADM (Amazon)
aws sns create-platform-application \
    --name myapp-ios \
    --platform APNS \
    --attributes '{
        "PlatformCredential": "private-key-content",
        "PlatformPrincipal": "certificate-content"
    }'

# Registrare device token (normalmente fatto dall'app lato client tramite SDK)
aws sns create-platform-endpoint \
    --platform-application-arn arn:aws:sns:...:app/APNS/myapp-ios \
    --token "device-token-from-apns" \
    --custom-user-data "userId=123"

# Inviare push notification diretta (target: endpoint specifico)
aws sns publish \
    --target-arn arn:aws:sns:...:endpoint/APNS/myapp-ios/xxxx \
    --message-structure json \
    --message '{
        "APNS": "{\"aps\":{\"alert\":\"Nuovo messaggio!\",\"badge\":1}}",
        "APNS_SANDBOX": "{\"aps\":{\"alert\":\"Nuovo messaggio!\",\"badge\":1}}"
    }'

# Inviare a tutti i device iscritti al topic
aws sns publish \
    --topic-arn arn:aws:sns:...:myapp-notifications \
    --message-structure json \
    --message '{
        "default": "Nuovo messaggio!",
        "APNS": "{\"aps\":{\"alert\":\"Nuovo messaggio!\"}}",
        "GCM": "{\"notification\":{\"title\":\"Nuovo messaggio!\"}}"
    }'
```

---

## Amazon SES — Simple Email Service

**SES** è il servizio per l'invio di email transazionali e marketing ad alto volume.

!!! note "API v1 vs v2"
    I comandi `aws ses ...` sono l'API v1 (legacy, ancora supportata). Per nuovi progetti usa `aws sesv2`, che unifica identity, configuration set, suppression list e account-level settings.

```bash
# Verificare dominio (aggiungere record DNS TXT/CNAME/MX per DKIM + MAIL FROM)
aws ses verify-domain-identity --domain company.com
aws ses verify-domain-dkim --domain company.com

# Inviare email semplice
aws ses send-email \
    --from noreply@company.com \
    --to user@example.com \
    --subject "Conferma registrazione" \
    --text "Grazie per esserti registrato!" \
    --html "<h1>Grazie per esserti registrato!</h1>"

# Inviare email con attachment (via send-raw-email o SDK)
# In produzione: usare SDK (boto3, SES v2 API)

# Configurare Configuration Set (tracking aperture, click, bounce)
aws ses create-configuration-set \
    --configuration-set '{"Name": "transactional"}'

aws ses create-configuration-set-event-destination \
    --configuration-set-name transactional \
    --event-destination '{
        "Name": "sns-notifications",
        "Enabled": true,
        "MatchingEventTypes": ["bounce", "complaint", "delivery"],
        "SNSDestination": {
            "TopicARN": "arn:aws:sns:...:ses-events"
        }
    }'

# SES v2 API (nuova, più funzionalità)
aws sesv2 send-email \
    --from-email-address noreply@company.com \
    --destination '{"ToAddresses": ["user@example.com"]}' \
    --content '{
        "Simple": {
            "Subject": {"Data": "Conferma account"},
            "Body": {
                "Html": {"Data": "<h1>Benvenuto!</h1>"}
            }
        }
    }' \
    --configuration-set-name transactional
```

**SES — Limiti e produzione:**
- Sandbox iniziale: solo indirizzi verificati, 200 email/giorno
- Richiesta aumento limite per produzione (via console → "Request Production Access")
- Gestire bounce e complaint: tieni bounce <2% e complaint <0.1%; AWS mette l'account in review/probation oltre ~5% bounce e 0.1% complaint e può sospendere l'invio a ~10% / 0.5%
- Autenticare il dominio con DKIM (e SPF/DMARC) per la deliverability; usa la suppression list per non reinviare a indirizzi in bounce

---

## Troubleshooting

### Scenario 1 — Messaggi non vengono consumati (stuck in queue)

**Sintomo:** `ApproximateNumberOfMessagesVisible` cresce ma i consumer non elaborano i messaggi.

**Causa:** Il `VisibilityTimeout` è troppo basso rispetto al tempo di elaborazione: il messaggio riappare in coda prima che il consumer finisca, causando un loop. In alternativa, il consumer non chiama `DeleteMessage` dopo l'elaborazione.

**Soluzione:** Aumentare il `VisibilityTimeout` o chiamare `ChangeMessageVisibility` durante l'elaborazione. Verificare che `DeleteMessage` venga sempre chiamato a elaborazione completata.

```bash
# Verificare lo stato della coda
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --attribute-names ApproximateNumberOfMessagesVisible ApproximateNumberOfMessagesNotVisible VisibilityTimeout

# Estendere visibility timeout a runtime
aws sqs change-message-visibility \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --receipt-handle "AQEB..." \
    --visibility-timeout 300

# Verificare se i messaggi si accumulano in DLQ
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-dlq \
    --attribute-names ApproximateNumberOfMessagesVisible
```

---

### Scenario 2 — Messaggi finiti in DLQ inaspettatamente

**Sintomo:** La DLQ accumula messaggi; `maxReceiveCount` viene raggiunto rapidamente.

**Causa:** Il consumer riceve il messaggio, va in errore (eccezione, timeout, crash) e non chiama `DeleteMessage`. SQS lo rimette in coda; dopo `maxReceiveCount` tentativi lo sposta in DLQ.

**Soluzione:** Analizzare i messaggi in DLQ per capire la causa del fallimento. Correggere il consumer. Usare `start-message-move-task` per re-processare i messaggi.

```bash
# Leggere messaggi DLQ per analisi (senza cancellarli)
aws sqs receive-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-dlq \
    --max-number-of-messages 10 \
    --visibility-timeout 0 \
    --attribute-names All

# Re-inviare messaggi dalla DLQ alla coda sorgente dopo il fix
aws sqs start-message-move-task \
    --source-arn arn:aws:sqs:eu-central-1:123456789012:myapp-dlq \
    --destination-arn arn:aws:sqs:eu-central-1:123456789012:myapp-queue \
    --max-number-of-messages-per-second 5

# Monitorare avanzamento del task
aws sqs list-message-move-tasks \
    --source-arn arn:aws:sqs:eu-central-1:123456789012:myapp-dlq
```

---

### Scenario 3 — SNS non consegna messaggi a SQS (AccessDenied)

**Sintomo:** Il topic SNS pubblica messaggi ma la coda SQS non li riceve. CloudWatch mostra `NumberOfNotificationsFailed`.

**Causa:** La Queue Policy della coda SQS non autorizza SNS a invocare `sqs:SendMessage`. Questo è un requisito esplicito per il pattern SNS→SQS.

**Soluzione:** Aggiungere una Resource-Based Policy alla coda che permetta all'ARN del topic SNS di inviare messaggi.

```bash
# Verificare la policy attuale della coda
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --attribute-names Policy

# Aggiungere policy corretta (sostituire gli ARN)
aws sqs set-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/myapp-queue \
    --attributes '{
        "Policy": "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"sns.amazonaws.com\"},\"Action\":\"sqs:SendMessage\",\"Resource\":\"arn:aws:sqs:eu-central-1:123456789012:myapp-queue\",\"Condition\":{\"ArnLike\":{\"aws:SourceArn\":\"arn:aws:sns:eu-central-1:123456789012:myapp-topic\"}}}]}"
    }'

# Verificare fallimenti SNS → SQS via CloudWatch
aws cloudwatch get-metric-statistics \
    --namespace AWS/SNS \
    --metric-name NumberOfNotificationsFailed \
    --dimensions Name=TopicName,Value=myapp-topic \
    --start-time 2026-03-28T00:00:00Z \
    --end-time 2026-03-28T23:59:59Z \
    --period 3600 \
    --statistics Sum
```

---

### Scenario 4 — FIFO Queue: messaggi duplicati o fuori ordine

**Sintomo:** Con una coda FIFO si ricevono messaggi duplicati, oppure messaggi con stesso `MessageGroupId` arrivano in ordine errato.

**Causa:** Duplicati: il producer ritenta dopo oltre 5 minuti (finestra di dedup scaduta), oppure usa un `MessageDeduplicationId` diverso a ogni retry (es. timestamp), che annulla la deduplicazione. Duplicati lato consumer: visibility timeout scaduto prima della `DeleteMessage`. Ordine errato: producer multipli/concorrenti sullo stesso `MessageGroupId` (l'ordine è quello di arrivo a SQS), oppure `MessageGroupId` diverso per messaggi che dovrebbero essere ordinati.

**Soluzione:** Usare un `MessageDeduplicationId` **deterministico** (es. ID di business dell'ordine) riusato a ogni retry dello stesso messaggio, oppure `ContentBasedDeduplication`. SQS consegna i messaggi di un `MessageGroupId` a un consumer alla volta; per scalare usa molti group ID distinti. Rendi comunque il consumer idempotente.

```bash
# Verificare attributi della coda FIFO
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/orders.fifo \
    --attribute-names FifoQueue ContentBasedDeduplication DeduplicationScope

# Inviare con MessageDeduplicationId deterministico (stesso ID a ogni retry)
aws sqs send-message \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/orders.fifo \
    --message-body '{"orderId": "ORD-001"}' \
    --message-group-id "customer-456" \
    --message-deduplication-id "ORD-001-created"

# Abilitare ContentBasedDeduplication (evita gestione manuale degli ID)
aws sqs set-queue-attributes \
    --queue-url https://sqs.eu-central-1.amazonaws.com/123456789012/orders.fifo \
    --attributes '{"ContentBasedDeduplication": "true"}'
```

---

## Riferimenti

- [SQS Developer Guide](https://docs.aws.amazon.com/sqs/latest/dg/)
- [SNS Developer Guide](https://docs.aws.amazon.com/sns/latest/dg/)
- [SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/)
- [SQS FIFO Queue](https://docs.aws.amazon.com/sqs/latest/dg/sqs-fifo-queues.html)
- [SNS Message Filtering](https://docs.aws.amazon.com/sns/latest/dg/sns-subscription-filter-policies.html)
- [SQS Extended Client](https://github.com/awslabs/amazon-sqs-java-extended-client-lib)
