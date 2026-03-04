---
title: "EventBridge, Kinesis & MSK"
slug: eventbridge-kinesis
category: cloud
tags: [aws, eventbridge, kinesis, msk, kafka, streaming, event-bus, pipes, scheduler]
search_keywords: [AWS EventBridge, EventBridge event bus, EventBridge rules, EventBridge Pipes, EventBridge Scheduler, Kinesis Data Streams, Kinesis Firehose, Kinesis Data Analytics, MSK Managed Streaming Kafka, Apache Kafka AWS, shard, enhanced fan-out, KCL Kinesis Client Library, event bridge patterns, cross-account events, SaaS integration, custom event bus, global endpoint, dead letter queue EventBridge]
parent: cloud/aws/messaging/_index
related: [cloud/aws/messaging/sqs-sns, cloud/aws/compute/lambda, cloud/aws/storage/s3, cloud/aws/monitoring/cloudwatch]
official_docs: https://docs.aws.amazon.com/eventbridge/latest/userguide/
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# EventBridge, Kinesis & MSK

## Amazon EventBridge

**EventBridge** è un **serverless event bus** che connette applicazioni tramite eventi. Supporta routing, filtraggio, trasformazione e delivery a oltre 20 target AWS.

### Architettura EventBridge

```
Event Sources                    EventBridge               Targets
──────────────                   ───────────               ───────
AWS Services ──────────────────► Default Bus ──► Rules ──► Lambda
SaaS Partners (Salesforce) ────► Partner Bus  ──► Rules ──► SQS/SNS
Custom Applications ────────────► Custom Bus   ──► Rules ──► Step Functions
                                                         ──► API Gateway
                                                         ──► Kinesis Streams
                                                         ──► ECS Task
                                                         ──► EventBridge Bus
                                                         ──► SaaS Target
```

**Event Bus tipi:**
- **Default Bus:** eventi AWS (EC2 state change, S3 ObjectCreated, RDS events, ecc.)
- **Custom Bus:** eventi custom delle tue applicazioni
- **Partner Bus:** integrazione con SaaS (Salesforce, Zendesk, Auth0, Datadog, ecc.)

---

### Creare Custom Event Bus e Rules

```bash
# Creare custom event bus
aws events create-event-bus \
    --name myapp-events \
    --tags Key=Environment,Value=production

# Creare rule con event pattern (filtraggio)
aws events put-rule \
    --name process-order-created \
    --event-bus-name myapp-events \
    --event-pattern '{
        "source": ["myapp.orders"],
        "detail-type": ["order.created"],
        "detail": {
            "status": ["PENDING"],
            "amount": [{"numeric": [">", 100]}]
        }
    }' \
    --state ENABLED \
    --description "Route high-value pending orders to Lambda"

# Aggiungere target alla rule (Lambda)
aws events put-targets \
    --rule process-order-created \
    --event-bus-name myapp-events \
    --targets '[{
        "Id": "lambda-process-order",
        "Arn": "arn:aws:lambda:eu-central-1:123456789012:function:ProcessOrder",
        "RetryPolicy": {
            "MaximumRetryAttempts": 3,
            "MaximumEventAgeInSeconds": 3600
        },
        "DeadLetterConfig": {
            "Arn": "arn:aws:sqs:eu-central-1:123456789012:eventbridge-dlq"
        }
    }]'

# Aggiungere target SQS (con input transformation)
aws events put-targets \
    --rule process-order-created \
    --event-bus-name myapp-events \
    --targets '[{
        "Id": "sqs-analytics",
        "Arn": "arn:aws:sqs:eu-central-1:123456789012:analytics-queue",
        "InputTransformer": {
            "InputPathsMap": {
                "orderId": "$.detail.orderId",
                "amount": "$.detail.amount",
                "ts": "$.time"
            },
            "InputTemplate": "{\"order_id\": \"<orderId>\", \"value\": <amount>, \"timestamp\": \"<ts>\"}"
        }
    }]'

# Permettere a Lambda di essere invocata da EventBridge
aws lambda add-permission \
    --function-name ProcessOrder \
    --statement-id eventbridge-invoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:eu-central-1:123456789012:rule/myapp-events/process-order-created
```

---

### Inviare Eventi Custom

```bash
# Inviare eventi al custom event bus (CLI)
aws events put-events \
    --entries '[{
        "EventBusName": "myapp-events",
        "Source": "myapp.orders",
        "DetailType": "order.created",
        "Detail": "{\"orderId\": \"ORD-001\", \"amount\": 150.00, \"status\": \"PENDING\", \"customerId\": \"CUST-42\"}"
    }]'

# Inviare batch di eventi (max 10 per chiamata)
aws events put-events \
    --entries '[
        {
            "EventBusName": "myapp-events",
            "Source": "myapp.orders",
            "DetailType": "order.created",
            "Detail": "{\"orderId\": \"ORD-001\"}"
        },
        {
            "EventBusName": "myapp-events",
            "Source": "myapp.inventory",
            "DetailType": "stock.updated",
            "Detail": "{\"sku\": \"PROD-001\", \"quantity\": 50}"
        }
    ]'
```

```python
# Python — inviare eventi da applicazione
import boto3
import json
from datetime import datetime

events_client = boto3.client('events', region_name='eu-central-1')

def publish_event(event_type: str, detail: dict, source: str = "myapp.orders"):
    response = events_client.put_events(
        Entries=[
            {
                'EventBusName': 'myapp-events',
                'Source': source,
                'DetailType': event_type,
                'Detail': json.dumps(detail),
                'Time': datetime.utcnow()
            }
        ]
    )

    failed = response.get('FailedEntryCount', 0)
    if failed > 0:
        raise Exception(f"Failed to publish {failed} events: {response['Entries']}")

    return response['Entries'][0]['EventId']

# Usare nell'applicazione
publish_event(
    event_type='order.created',
    detail={'orderId': 'ORD-001', 'amount': 150.00, 'status': 'PENDING'}
)
```

---

### Event Pattern — Filtraggio Avanzato

```json
{
  "source": ["myapp.orders"],
  "detail-type": ["order.created", "order.updated"],
  "detail": {
    "status": ["PENDING", "CONFIRMED"],
    "amount": [{"numeric": [">=", 100, "<", 10000]}],
    "customerId": [{"prefix": "CUST-"}],
    "metadata": {
      "environment": ["production"]
    },
    "tags": {
      "priority": [{"anything-but": "low"}]
    }
  },
  "region": ["eu-central-1", "eu-west-1"]
}
```

**Operatori disponibili nei pattern:**
- `["value"]` — exact match (stringa, numero, booleano)
- `[{"prefix": "str"}]` — inizia con prefisso
- `[{"suffix": "str"}]` — finisce con suffisso
- `[{"anything-but": ["a", "b"]}]` — tutto tranne questi valori
- `[{"numeric": [">=", 10, "<", 100]}]` — range numerico
- `[{"exists": false}]` — campo assente
- `[{"cidr": "10.0.0.0/8"}]` — IP in range CIDR

---

### Cross-Account Event Bus

```bash
# Account A: permettere a Account B di inviare eventi
aws events put-permission \
    --event-bus-name myapp-events \
    --action events:PutEvents \
    --principal "111122223333" \       # Account B
    --statement-id allow-account-b

# Account B: inviare eventi al bus di Account A
aws events put-events \
    --entries '[{
        "EventBusName": "arn:aws:events:eu-central-1:123456789012:event-bus/myapp-events",
        "Source": "accountb.service",
        "DetailType": "order.created",
        "Detail": "{\"orderId\": \"ORD-001\"}"
    }]'
```

---

### EventBridge Pipes

**EventBridge Pipes** connette source e target con filtraggio e trasformazione senza codice intermedio (Lambda opzionale solo per enrichment).

```bash
# Pipe: SQS → filtraggio → (Lambda enrichment opzionale) → Kinesis Firehose
aws pipes create-pipe \
    --name sqs-to-firehose \
    --role-arn arn:aws:iam::123456789012:role/PipeRole \
    --source arn:aws:sqs:eu-central-1:123456789012:orders-queue \
    --source-parameters '{
        "SqsQueueParameters": {
            "BatchSize": 10,
            "MaximumBatchingWindowInSeconds": 5
        },
        "FilterCriteria": {
            "Filters": [{
                "Pattern": "{\"body\":{\"status\":[\"COMPLETED\"]}}"
            }]
        }
    }' \
    --enrichment arn:aws:lambda:eu-central-1:123456789012:function:EnrichOrder \
    --target arn:aws:firehose:eu-central-1:123456789012:deliverystream/orders-stream \
    --target-parameters '{
        "KinesisStreamParameters": {
            "PartitionKey": "$.body.customerId"
        }
    }' \
    --log-configuration '{
        "Level": "ERROR",
        "CloudwatchLogsLogDestination": {
            "LogGroupArn": "arn:aws:logs:...:log-group:/pipes/sqs-to-firehose"
        }
    }'
```

**Pipe source supportati:** SQS, Kinesis Streams, DynamoDB Streams, MSK, MQ
**Pipe target:** Lambda, ECS, Step Functions, EventBridge Bus, Kinesis, Firehose, SQS, SNS, API Gateway, API Destination

---

### EventBridge Scheduler

**Scheduler** gestisce task programmati (cron e rate) con delivery garantita, retry e timezone.

```bash
# Task one-time (esempio: processo batch tra 1 ora)
aws scheduler create-schedule \
    --name process-monthly-report \
    --schedule-expression "at(2026-03-01T00:00:00)" \
    --schedule-expression-timezone "Europe/Rome" \
    --flexible-time-window '{"Mode": "OFF"}' \
    --target '{
        "Arn": "arn:aws:lambda:eu-central-1:123456789012:function:MonthlyReport",
        "RoleArn": "arn:aws:iam::123456789012:role/SchedulerRole",
        "Input": "{\"reportType\": \"monthly\", \"month\": \"2026-02\"}"
    }' \
    --action-after-completion DELETE    # elimina lo schedule dopo l'esecuzione

# Task ricorrente cron (ogni giorno alle 8:00 ora italiana)
aws scheduler create-schedule \
    --name daily-sync \
    --schedule-expression "cron(0 8 * * ? *)" \
    --schedule-expression-timezone "Europe/Rome" \
    --flexible-time-window '{"Mode": "FLEXIBLE", "MaximumWindowInMinutes": 15}' \
    --target '{
        "Arn": "arn:aws:sqs:eu-central-1:123456789012:sync-queue",
        "RoleArn": "arn:aws:iam::123456789012:role/SchedulerRole",
        "Input": "{\"action\": \"sync\"}"
    }' \
    --retry-policy '{"MaximumRetryAttempts": 3, "MaximumEventAgeInSeconds": 3600}' \
    --dead-letter-config '{"Arn": "arn:aws:sqs:...:scheduler-dlq"}'

# Task rate expression
aws scheduler create-schedule \
    --name heartbeat \
    --schedule-expression "rate(5 minutes)" \
    --target '{
        "Arn": "arn:aws:lambda:...:function:HealthCheck",
        "RoleArn": "arn:aws:iam::123456789012:role/SchedulerRole"
    }'
```

---

## Amazon Kinesis

### Kinesis Data Streams

**Kinesis Data Streams** è un servizio di **streaming real-time** basato su shard. Ideale per log, clickstream, IoT, eventi ad alto volume.

```
Producers                    Kinesis Data Streams               Consumers
─────────                    ──────────────────────             ─────────
App Servers  ──────────────► Shard 1 (1 MB/s in, 2 MB/s out)► Lambda
IoT Devices  ──────────────► Shard 2 (1 MB/s in, 2 MB/s out)► KCL App
Web Logs     ──────────────► Shard 3 (1 MB/s in, 2 MB/s out)► Kinesis Firehose
                             │                                  (enhanced fan-out)
                             └── Retention: 24h - 365 giorni
```

**Limiti per shard:**
- **Write:** 1 MB/s o 1000 record/s per shard
- **Read (shared):** 2 MB/s totali per shard, divisi tra tutti i consumer
- **Read (enhanced fan-out):** 2 MB/s per consumer per shard (dedicated throughput)
- **Record size:** max 1 MB

```bash
# Creare stream (provisioned — shard fissi)
aws kinesis create-stream \
    --stream-name app-events \
    --shard-count 4            # 4 shard = 4 MB/s write, 8 MB/s read

# Creare stream ON-DEMAND (auto-scaling, pay-per-use)
aws kinesis create-stream \
    --stream-name app-events-od \
    --stream-mode-details StreamMode=ON_DEMAND

# Inviare record
aws kinesis put-record \
    --stream-name app-events \
    --partition-key "user-123" \          # determina lo shard (via hash)
    --data '{"event": "page.view", "userId": "user-123", "url": "/products"}' \
    --cli-binary-format raw-in-base64-out

# Inviare batch (max 500 record, max 5 MB totali)
aws kinesis put-records \
    --stream-name app-events \
    --records '[
        {"PartitionKey": "user-1", "Data": "eyJldmVudCI6ICJ2aWV3In0="},
        {"PartitionKey": "user-2", "Data": "eyJldmVudCI6ICJjbGljayJ9"}
    ]'

# Leggere record (shard iterator)
SHARD_ITERATOR=$(aws kinesis get-shard-iterator \
    --stream-name app-events \
    --shard-id shardId-000000000000 \
    --shard-iterator-type TRIM_HORIZON \     # TRIM_HORIZON, LATEST, AT_SEQUENCE_NUMBER, AFTER_SEQUENCE_NUMBER, AT_TIMESTAMP
    --query 'ShardIterator' \
    --output text)

aws kinesis get-records \
    --shard-iterator $SHARD_ITERATOR \
    --limit 100

# Listare shard
aws kinesis list-shards --stream-name app-events

# Scalare stream (split/merge shard)
aws kinesis split-shard \
    --stream-name app-events \
    --shard-to-split shardId-000000000000 \
    --new-starting-hash-key "170141183460469231731687303715884105728"
    # splitting un shard al centro del range di hash

aws kinesis merge-shards \
    --stream-name app-events \
    --shard-to-merge shardId-000000000001 \
    --adjacent-shard-to-merge shardId-000000000002
```

---

### Lambda come Consumer Kinesis

```bash
# Event Source Mapping Lambda → Kinesis
aws lambda create-event-source-mapping \
    --function-name ProcessKinesisEvents \
    --event-source-arn arn:aws:kinesis:eu-central-1:123456789012:stream/app-events \
    --starting-position LATEST \
    --batch-size 100 \
    --maximum-batching-window-in-seconds 5 \
    --parallelization-factor 2 \            # 2 concurrent Lambda per shard
    --bisect-batch-on-function-error true \  # divide batch su errore
    --maximum-retry-attempts 3 \
    --destination-config '{
        "OnFailure": {"Destination": "arn:aws:sqs:...:kinesis-failures-dlq"}
    }' \
    --filter-criteria '{
        "Filters": [{
            "Pattern": "{\"data\":{\"eventType\":[\"click\",\"purchase\"]}}"
        }]
    }'
```

```python
# Lambda handler per Kinesis
import base64
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    batch_item_failures = []

    for record in event['Records']:
        try:
            # Record Kinesis è base64-encoded
            payload = base64.b64decode(record['kinesis']['data']).decode('utf-8')
            data = json.loads(payload)

            logger.info(f"Processing: shard={record['kinesis']['sequenceNumber']}, "
                       f"partitionKey={record['kinesis']['partitionKey']}")

            process_event(data)

        except Exception as e:
            logger.error(f"Failed to process record: {e}")
            batch_item_failures.append({
                "itemIdentifier": record['kinesis']['sequenceNumber']
            })

    return {"batchItemFailures": batch_item_failures}
```

---

### Enhanced Fan-Out

```bash
# Registrare consumer con enhanced fan-out (2 MB/s dedicati per shard)
STREAM_ARN=$(aws kinesis describe-stream-summary \
    --stream-name app-events \
    --query 'StreamDescriptionSummary.StreamARN' \
    --output text)

aws kinesis register-stream-consumer \
    --stream-arn $STREAM_ARN \
    --consumer-name analytics-consumer

# Lista consumer registrati
aws kinesis list-stream-consumers --stream-arn $STREAM_ARN

# Enhanced fan-out usa SubscribeToShard (HTTP/2 push) invece di GetRecords (polling)
# → latenza ~65ms vs ~200ms del polling standard
```

---

### Kinesis Firehose

**Kinesis Firehose** è un servizio di delivery managed per streaming data verso S3, Redshift, OpenSearch, Splunk, HTTP endpoint.

```bash
# Creare delivery stream → S3 con compressione e conversione formato
aws firehose create-delivery-stream \
    --delivery-stream-name app-logs-to-s3 \
    --delivery-stream-type DirectPut \        # DirectPut (produttori diretti) o KinesisStreamAsSource
    --s3-destination-configuration '{
        "RoleARN": "arn:aws:iam::123456789012:role/FirehoseRole",
        "BucketARN": "arn:aws:s3:::my-data-lake",
        "Prefix": "raw/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/",
        "ErrorOutputPrefix": "errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/",
        "BufferingHints": {
            "SizeInMBs": 128,              # flush ogni 128 MB (max)
            "IntervalInSeconds": 300        # flush ogni 5 minuti (max)
        },
        "CompressionFormat": "GZIP",       # UNCOMPRESSED, GZIP, ZIP, Snappy, HADOOP_SNAPPY
        "CloudWatchLoggingOptions": {
            "Enabled": true,
            "LogGroupName": "/firehose/app-logs-to-s3",
            "LogStreamName": "S3Delivery"
        }
    }'

# Delivery stream con trasformazione Lambda (data processing)
aws firehose create-delivery-stream \
    --delivery-stream-name events-transformed \
    --delivery-stream-type DirectPut \
    --extended-s3-destination-configuration '{
        "RoleARN": "arn:aws:iam::123456789012:role/FirehoseRole",
        "BucketARN": "arn:aws:s3:::my-data-lake",
        "Prefix": "processed/",
        "ProcessingConfiguration": {
            "Enabled": true,
            "Processors": [{
                "Type": "Lambda",
                "Parameters": [{
                    "ParameterName": "LambdaArn",
                    "ParameterValue": "arn:aws:lambda:...:function:TransformEvents"
                }, {
                    "ParameterName": "BufferSizeInMBs",
                    "ParameterValue": "3"
                }, {
                    "ParameterName": "BufferIntervalInSeconds",
                    "ParameterValue": "60"
                }]
            }]
        },
        "DataFormatConversionConfiguration": {
            "Enabled": true,
            "InputFormatConfiguration": {
                "Deserializer": {"OpenXJsonSerDe": {}}
            },
            "OutputFormatConfiguration": {
                "Serializer": {"ParquetSerDe": {}}   # JSON → Parquet per Athena/Glue
            },
            "SchemaConfiguration": {
                "RoleARN": "arn:aws:iam::...:role/FirehoseRole",
                "DatabaseName": "mydb",
                "TableName": "events",
                "Region": "eu-central-1",
                "VersionId": "LATEST"
            }
        }
    }'

# Delivery stream con Kinesis Streams come sorgente
aws firehose create-delivery-stream \
    --delivery-stream-name kinesis-to-s3 \
    --delivery-stream-type KinesisStreamAsSource \
    --kinesis-stream-source-configuration '{
        "KinesisStreamARN": "arn:aws:kinesis:eu-central-1:123456789012:stream/app-events",
        "RoleARN": "arn:aws:iam::123456789012:role/FirehoseRole"
    }' \
    --extended-s3-destination-configuration '{
        "RoleARN": "arn:aws:iam::123456789012:role/FirehoseRole",
        "BucketARN": "arn:aws:s3:::my-data-lake",
        "Prefix": "events/",
        "CompressionFormat": "GZIP"
    }'

# Inviare record a Firehose (DirectPut)
aws firehose put-record \
    --delivery-stream-name app-logs-to-s3 \
    --record '{"Data": "eyJldmVudCI6ICJsb2dMaW5lIn0="}'   # base64

aws firehose put-record-batch \
    --delivery-stream-name app-logs-to-s3 \
    --records '[
        {"Data": "eyJldmVudCI6ICJsb2cxIn0="},
        {"Data": "eyJldmVudCI6ICJsb2cyIn0="}
    ]'
```

```python
# Lambda handler per trasformazione Firehose
import base64
import json

def lambda_handler(event, context):
    output = []

    for record in event['records']:
        # Decodificare payload
        payload = base64.b64decode(record['data']).decode('utf-8')
        data = json.loads(payload)

        # Trasformazione (esempio: aggiungere timestamp, normalizzare)
        transformed = {
            'timestamp': data.get('ts', ''),
            'event_type': data.get('type', 'unknown'),
            'user_id': data.get('userId'),
            'metadata': data.get('meta', {})
        }

        # DEVE includere newline per separare record JSON lines in S3
        transformed_str = json.dumps(transformed) + '\n'

        output.append({
            'recordId': record['recordId'],
            'result': 'Ok',             # Ok, Dropped, ProcessingFailed
            'data': base64.b64encode(transformed_str.encode('utf-8')).decode('utf-8')
        })

    return {'records': output}
```

---

## Amazon MSK — Managed Streaming for Apache Kafka

**MSK** è Apache Kafka completamente gestito su AWS. Ideale per chi ha già workload Kafka e vuole delegare la gestione del cluster.

### Tipi di Cluster MSK

| | MSK Provisioned | MSK Serverless |
|---|----------------|----------------|
| Gestione | Scegli broker type/count | Zero gestione infrastruttura |
| Scaling | Manuale o auto-expand storage | Automatico |
| Throughput | Fino a 30 GB/s | Fino a 200 MB/s in, 400 MB/s out |
| Availability | Multi-AZ | Multi-AZ automatico |
| Retention | Configurabile | Configurabile |
| Pricing | Ora broker + storage | Per GB throughput + storage |
| Use case | Workload prevedibili, alta performance | Variable/unknown load |

### Creare Cluster MSK

```bash
# Creare cluster MSK Provisioned
aws kafka create-cluster \
    --cluster-name production-kafka \
    --kafka-version "3.7.x" \
    --number-of-broker-nodes 3 \
    --broker-node-group-info '{
        "InstanceType": "kafka.m5.large",
        "ClientSubnets": ["subnet-a", "subnet-b", "subnet-c"],
        "SecurityGroups": ["sg-kafka"],
        "StorageInfo": {
            "EbsStorageInfo": {
                "VolumeSize": 1000,
                "ProvisionedThroughput": {
                    "Enabled": true,
                    "VolumeThroughput": 250
                }
            }
        }
    }' \
    --encryption-info '{
        "EncryptionAtRest": {"DataVolumeKMSKeyId": "arn:aws:kms:...:key/..."},
        "EncryptionInTransit": {"ClientBroker": "TLS", "InCluster": true}
    }' \
    --client-authentication '{
        "Sasl": {
            "Iam": {"Enabled": true}        # IAM auth + ACL
        }
    }' \
    --logging-info '{
        "BrokerLogs": {
            "CloudWatchLogs": {"Enabled": true, "LogGroup": "/msk/production-kafka"},
            "S3": {"Enabled": true, "Bucket": "my-msk-logs", "Prefix": "kafka/"}
        }
    }'

# Creare cluster MSK Serverless
aws kafka create-cluster-v2 \
    --cluster-name serverless-kafka \
    --serverless '{
        "VpcConfigs": [{
            "SubnetIds": ["subnet-a", "subnet-b", "subnet-c"],
            "SecurityGroupIds": ["sg-kafka"]
        }],
        "ClientAuthentication": {
            "Sasl": {"Iam": {"Enabled": true}}
        }
    }'

# Ottenere bootstrap brokers
aws kafka get-bootstrap-brokers --cluster-arn arn:aws:kafka:...:cluster/production-kafka/...
# Output: BootstrapBrokerStringTls, BootstrapBrokerStringSaslIam
```

### Operare con MSK (Kafka CLI)

```bash
# Installare Kafka CLI tools
# Download: https://kafka.apache.org/downloads

# Creare topic
kafka-topics.sh \
    --bootstrap-server broker1:9098 \
    --create \
    --topic order-events \
    --partitions 12 \
    --replication-factor 3 \
    --config retention.ms=604800000 \       # 7 giorni
    --config min.insync.replicas=2

# Listare topic
kafka-topics.sh --bootstrap-server broker1:9098 --list

# Descrivere topic
kafka-topics.sh --bootstrap-server broker1:9098 --describe --topic order-events

# Producer test
kafka-console-producer.sh \
    --bootstrap-server broker1:9098 \
    --topic order-events

# Consumer test (da inizio)
kafka-console-consumer.sh \
    --bootstrap-server broker1:9098 \
    --topic order-events \
    --from-beginning \
    --group test-consumer-group
```

### MSK con IAM Authentication

```python
# Python consumer con MSK IAM Auth
# pip install kafka-python aws-msk-iam-sasl-signer-python

from kafka import KafkaConsumer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
import json

def get_token(config):
    token, expiry_ms = MSKAuthTokenProvider.generate_auth_token('eu-central-1')
    return token, expiry_ms

consumer = KafkaConsumer(
    'order-events',
    bootstrap_servers=['broker1:9098', 'broker2:9098', 'broker3:9098'],
    security_protocol='SASL_SSL',
    sasl_mechanism='OAUTHBEARER',
    sasl_oauth_token_provider=get_token,
    group_id='order-processor',
    auto_offset_reset='latest',
    enable_auto_commit=False,        # commit manuale per exactly-once processing
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    try:
        process_order(message.value)
        consumer.commit()            # commit dopo elaborazione
    except Exception as e:
        logger.error(f"Failed to process message: {e}")
        # Non commita → messaggio riprocessato alla prossima iterazione
```

### MSK Connect

**MSK Connect** esegue **Kafka Connect** managed — integra Kafka con sistemi esterni (S3, RDS, OpenSearch, ecc.):

```bash
# Caricare plugin Kafka Connect su S3
aws s3 cp confluentinc-kafka-connect-s3-10.5.0.zip \
    s3://my-msk-plugins/confluentinc-kafka-connect-s3-10.5.0.zip

# Creare custom plugin
aws kafkaconnect create-custom-plugin \
    --name s3-sink-plugin \
    --content-type ZIP \
    --location '{
        "S3Location": {
            "BucketArn": "arn:aws:s3:::my-msk-plugins",
            "FileKey": "confluentinc-kafka-connect-s3-10.5.0.zip"
        }
    }'

# Creare connector (S3 Sink — Kafka → S3)
aws kafkaconnect create-connector \
    --connector-name order-events-to-s3 \
    --connector-configuration '{
        "connector.class": "io.confluent.connect.s3.S3SinkConnector",
        "tasks.max": "4",
        "topics": "order-events",
        "s3.region": "eu-central-1",
        "s3.bucket.name": "my-data-lake",
        "s3.part.size": "67108864",
        "flush.size": "10000",
        "storage.class": "io.confluent.connect.s3.storage.S3Storage",
        "format.class": "io.confluent.connect.s3.format.json.JsonFormat",
        "locale": "it_IT",
        "timezone": "Europe/Rome",
        "timestamp.extractor": "RecordField",
        "timestamp.field": "timestamp"
    }' \
    --kafka-cluster '{
        "apacheKafkaCluster": {
            "bootstrapServers": "broker1:9098",
            "vpc": {
                "subnets": ["subnet-a", "subnet-b", "subnet-c"],
                "securityGroups": ["sg-kafka"]
            }
        }
    }' \
    --kafka-cluster-client-authentication '{"authenticationType": "IAM"}' \
    --kafka-cluster-encryption-in-transit '{"encryptionType": "TLS"}' \
    --capacity '{
        "autoScaling": {
            "minWorkerCount": 1,
            "maxWorkerCount": 4,
            "scaleInPolicy": {"cpuUtilizationPercentage": 20},
            "scaleOutPolicy": {"cpuUtilizationPercentage": 80}
        }
    }' \
    --plugins '[{"customPlugin": {"customPluginArn": "arn:aws:kafkaconnect:...:custom-plugin/s3-sink-plugin/..."}}]' \
    --service-execution-role-arn arn:aws:iam::123456789012:role/MSKConnectRole
```

---

## Confronto Finale: Quale Usare?

```
Hai bisogno di...

Semplice decoupling job/worker?
  └── SQS Standard

Ordine garantito / exactly-once?
  └── SQS FIFO

Notifiche push / fan-out / mobile?
  └── SNS

Event routing con logica / cross-account?
  └── EventBridge Custom Bus

Integrazione SaaS senza codice?
  └── EventBridge Partner Bus + Pipes

Task schedulati (cron)?
  └── EventBridge Scheduler

Real-time processing / log streaming ad alto volume?
  └── Kinesis Data Streams

ETL streaming → S3 / Redshift / OpenSearch?
  └── Kinesis Firehose

Hai già Kafka o team Kafka?
  └── MSK Provisioned

Kafka senza gestione infrastruttura?
  └── MSK Serverless
```

---

## Riferimenti

- [EventBridge User Guide](https://docs.aws.amazon.com/eventbridge/latest/userguide/)
- [EventBridge Pipes](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-pipes.html)
- [EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/)
- [Kinesis Data Streams Developer Guide](https://docs.aws.amazon.com/streams/latest/dev/)
- [Kinesis Firehose Developer Guide](https://docs.aws.amazon.com/firehose/latest/dev/)
- [MSK Developer Guide](https://docs.aws.amazon.com/msk/latest/developerguide/)
- [MSK Connect](https://docs.aws.amazon.com/msk/latest/developerguide/msk-connect.html)
- [Kinesis vs SQS vs SNS vs EventBridge](https://aws.amazon.com/blogs/compute/choosing-the-right-event-routing-service-for-serverless/)
