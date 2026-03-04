---
title: "AWS Lambda — Serverless"
slug: lambda
category: cloud
tags: [aws, lambda, serverless, functions, triggers, concurrency, cold-start, layers, destinations, event-source-mapping, lambda-at-edge, extensions, power-tuning]
search_keywords: [AWS Lambda, serverless, function, trigger, event source, SQS trigger, API Gateway Lambda, SNS Lambda, S3 Lambda, DynamoDB Streams, Kinesis Lambda, EventBridge, concurrency, reserved concurrency, provisioned concurrency, cold start, warm start, Lambda layers, Lambda extensions, Lambda destinations, Lambda@Edge, CloudFront Functions, Lambda power tuning, SnapStart, Lambda VPC, execution role, function URL]
parent: cloud/aws/compute/_index
related: [cloud/aws/messaging/sqs-sns, cloud/aws/messaging/eventbridge-kinesis, cloud/aws/networking/cloudfront, cloud/aws/storage/s3]
official_docs: https://docs.aws.amazon.com/lambda/latest/dg/
status: complete
difficulty: intermediate
last_updated: 2026-03-03
---

# AWS Lambda — Serverless

**Lambda** è il servizio serverless di AWS — esegui codice senza gestire server, pagando solo per il tempo di esecuzione.

```
Lambda Model

  Event Source               Lambda Function             Output
  ─────────────              ────────────────            ──────
  API Gateway ──────────────→│  Handler         │──────→ HTTP Response
  SQS Queue   ──── Batch ───→│  function(event, │──────→ Processed messages
  S3 Event    ──────────────→│   context):      │──────→ (processata)
  DynamoDB    ──── Stream ──→│       ...        │──────→ Downstream service
  EventBridge ──────────────→│                  │
  Kinesis     ──── Batch ───→└──────────────────┘
```

---

## Fondamentali

**Limiti (al 2025):**

| Parametro | Limite |
|-----------|--------|
| Timeout massimo | 15 minuti |
| Memoria | 128 MB - 10 GB |
| vCPU | Proporzionale alla memoria (6 vCPU a 10 GB) |
| Storage temporaneo (/tmp) | 512 MB - 10 GB |
| Package size (zip) | 50 MB (zipped) / 250 MB (unzipped) |
| Package size (container) | 10 GB |
| Payload sincrono | 6 MB (request) / 6 MB (response) |
| Payload asincrono | 256 KB |
| Concurrency default | 1000 per account per Region |
| Durata ambiente | 15 minuti (poi cold start alla prossima invocazione) |

**Runtime supportati:** Node.js 20/22, Python 3.11/3.12/3.13, Java 17/21, .NET 8, Ruby 3.2/3.3, Go (custom runtime), Custom Runtime (Amazon Linux 2023)

---

## Creare e Configurare una Lambda

```bash
# Creare execution role
aws iam create-role \
    --role-name lambda-basic-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

# Policy base: CloudWatch Logs + VPC networking
aws iam attach-role-policy \
    --role-name lambda-basic-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Package funzione
zip function.zip handler.py

# Creare funzione
aws lambda create-function \
    --function-name MyFunction \
    --runtime python3.12 \
    --role arn:aws:iam::123456789012:role/lambda-basic-role \
    --handler handler.lambda_handler \
    --zip-file fileb://function.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment Variables='{DB_HOST=rds.company.com,ENV=prod}' \
    --ephemeral-storage Size=1024 \        # /tmp storage in MB
    --architectures arm64 \               # arm64 per Graviton (20% più economico)
    --description "API handler"

# Aggiornare codice
aws lambda update-function-code \
    --function-name MyFunction \
    --zip-file fileb://function.zip

# Invocare manualmente
aws lambda invoke \
    --function-name MyFunction \
    --payload '{"key": "value"}' \
    --cli-binary-format raw-in-base64-out \
    response.json
cat response.json

# Invocare asincrono
aws lambda invoke-async \       # DEPRECATED — usare --invocation-type Event
    --function-name MyFunction \
    --invoke-args payload.json

aws lambda invoke \
    --function-name MyFunction \
    --invocation-type Event \   # Asincrono
    --payload '{"key":"value"}' \
    --cli-binary-format raw-in-base64-out \
    /dev/null
```

---

## Handler — Struttura del Codice

```python
# Python handler
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Inizializzazione fuori dall'handler = eseguita solo al cold start
s3 = boto3.client('s3')
ssm = boto3.client('ssm')

def lambda_handler(event, context):
    """
    event: payload dell'evento (dict)
    context: oggetto con info sull'esecuzione Lambda
    """
    logger.info(f"Event: {json.dumps(event)}")
    logger.info(f"Function: {context.function_name}")
    logger.info(f"Remaining time: {context.get_remaining_time_in_millis()}ms")
    logger.info(f"Request ID: {context.aws_request_id}")

    try:
        # Elaborazione
        result = process(event)
        return {
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {'Content-Type': 'application/json'}
        }
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise   # Lambda ritentar se configurato

def process(event):
    # business logic
    return {"processed": True}
```

```javascript
// Node.js handler
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');

// Inizializzazione fuori dall'handler (cold start)
const s3Client = new S3Client({ region: process.env.AWS_REGION });

exports.handler = async (event, context) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    console.log('Remaining time:', context.getRemainingTimeInMillis());

    try {
        const result = await processEvent(event);
        return {
            statusCode: 200,
            body: JSON.stringify(result)
        };
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
};
```

---

## Concurrency

```
Lambda Concurrency

  Account Limit (default 1000)
  ├── Reserved Concurrency (Function A: 200)  ← garantito, ma limita max
  ├── Reserved Concurrency (Function B: 100)
  └── Unreserved Pool (700)                   ← condiviso tra le restanti funzioni

  Provisioned Concurrency (Function C: 50)   ← pre-warmed, no cold start
```

```bash
# Reserved Concurrency: garantisce e limita concurrency di una funzione
aws lambda put-function-concurrency \
    --function-name MyFunction \
    --reserved-concurrent-executions 200
# reserved=0 → throttle completo (disabilita funzione)

# Provisioned Concurrency: pre-inizializza N ambienti di esecuzione
# Elimina cold start — paghi per le ore di provisioning anche se non usi
aws lambda put-provisioned-concurrency-config \
    --function-name MyFunction \
    --qualifier 1 \                    # versione o alias
    --provisioned-concurrent-executions 50

# Application Auto Scaling per Provisioned Concurrency
aws application-autoscaling register-scalable-target \
    --service-namespace lambda \
    --resource-id function:MyFunction:prod \
    --scalable-dimension lambda:function:ProvisionedConcurrency \
    --min-capacity 10 \
    --max-capacity 100
```

**Cold Start:** il tempo di inizializzazione dell'ambiente Lambda (download codice, inizializzazione runtime, esecuzione codice fuori dall'handler).

**Ridurre il Cold Start:**
- Usare runtime veloci (Node.js, Python)
- Minimizzare dimensione package
- Usare arm64 (Graviton) — ~30% più veloce
- **SnapStart** per Java: salva snapshot RAM dell'ambiente dopo init → resume <1s
- Provisioned Concurrency per funzioni latency-sensitive

---

## Triggers — Event Sources

### API Gateway / Function URL

```bash
# Function URL (endpoint HTTP pubblico diretto, senza API Gateway)
aws lambda create-function-url-config \
    --function-name MyFunction \
    --auth-type NONE \                  # NONE o AWS_IAM
    --cors '{"AllowOrigins": ["*"], "AllowMethods": ["GET","POST"]}'
# Restituisce: https://xxxx.lambda-url.eu-central-1.on.aws/

# Con auth IAM (per chiamate inter-servizio sicure)
aws lambda create-function-url-config \
    --function-name MyFunction \
    --auth-type AWS_IAM
```

### SQS Event Source Mapping

```bash
# Lambda consuma messaggi da SQS automaticamente
aws lambda create-event-source-mapping \
    --function-name MyFunction \
    --event-source-arn arn:aws:sqs:eu-central-1:123456789012:MyQueue \
    --batch-size 10 \                   # fino a 10 messaggi per invocazione
    --maximum-batching-window-in-seconds 30 \   # attendi fino a 30s per riempire batch
    --function-response-types '["ReportBatchItemFailures"]'   # partial batch failure
```

```python
# Gestione parziale del batch (non fallire l'intero batch se alcuni messaggi falliscono)
def lambda_handler(event, context):
    batch_failures = []

    for record in event['Records']:
        try:
            process_message(record['body'])
        except Exception as e:
            logger.error(f"Failed to process {record['messageId']}: {e}")
            batch_failures.append({"itemIdentifier": record['messageId']})

    return {"batchItemFailures": batch_failures}
    # SQS ritenterà solo i messaggi falliti
```

### S3 Event Notification

```bash
# Configurare S3 per notificare Lambda su PutObject
aws s3api put-bucket-notification-configuration \
    --bucket my-bucket \
    --notification-configuration '{
        "LambdaFunctionConfigurations": [{
            "LambdaFunctionArn": "arn:aws:lambda:...:function:ProcessUpload",
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {"FilterRules": [
                    {"Name": "prefix", "Value": "uploads/"},
                    {"Name": "suffix", "Value": ".jpg"}
                ]}
            }
        }]
    }'

# Aggiungere permission Lambda per S3
aws lambda add-permission \
    --function-name ProcessUpload \
    --statement-id s3-invoke \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::my-bucket \
    --source-account 123456789012
```

### DynamoDB Streams / Kinesis

```bash
# Lambda triggered da DynamoDB Streams
aws lambda create-event-source-mapping \
    --function-name ProcessDDBStream \
    --event-source-arn arn:aws:dynamodb:...:table/MyTable/stream/2026-01-01T00:00:00.000 \
    --batch-size 100 \
    --starting-position LATEST \        # LATEST, TRIM_HORIZON, AT_TIMESTAMP
    --bisect-batch-on-function-error true \   # divide batch su errore
    --maximum-retry-attempts 3 \
    --destination-config '{
        "OnFailure": {
            "Destination": "arn:aws:sqs:...:DLQ"    # Dead Letter Queue
        }
    }'
```

---

## Lambda Layers

I **Lambda Layers** sono archivi ZIP con librerie/dipendenze condivise tra più funzioni.

```bash
# Creare layer con dipendenze Python
pip install -r requirements.txt -t python/
zip -r layer.zip python/

aws lambda publish-layer-version \
    --layer-name my-dependencies \
    --description "Common Python deps" \
    --zip-file fileb://layer.zip \
    --compatible-runtimes python3.11 python3.12 \
    --compatible-architectures arm64 x86_64

# Allegare layer alla funzione (max 5 layer per funzione)
aws lambda update-function-configuration \
    --function-name MyFunction \
    --layers \
        arn:aws:lambda:eu-central-1:123456789012:layer:my-dependencies:3 \
        arn:aws:lambda:eu-central-1:580247275435:layer:LambdaInsightsExtension:21
        # AWS managed layer per CloudWatch Lambda Insights
```

---

## Lambda in VPC

Lambda in VPC permette di accedere a risorse private (RDS, ElastiCache, EC2).

```bash
aws lambda update-function-configuration \
    --function-name MyFunction \
    --vpc-config SubnetIds=subnet-private-a,subnet-private-b,\
        SecurityGroupIds=sg-lambda

# IMPORTANTE: Lambda in VPC usa ENI (Elastic Network Interface)
# - Aggiunge 100-200ms di cold start iniziale (creazione ENI, ora migliorata)
# - Richiede NAT Gateway per accesso Internet
# - Richiede VPC Endpoints per accesso a servizi AWS senza Internet
# - IAM Policy DEVE includere: ec2:CreateNetworkInterface, ec2:DescribeNetworkInterfaces, ec2:DeleteNetworkInterface
```

---

## Destinations e DLQ (Dead Letter Queue — coda che riceve gli eventi non elaborati dopo tutti i retry)

```bash
# Lambda Destinations: dove inviare il risultato (successo o fallimento)
# Solo per invocazioni ASINCRONE
aws lambda put-function-event-invoke-config \
    --function-name MyFunction \
    --maximum-retry-attempts 2 \
    --maximum-event-age-in-seconds 3600 \
    --destination-config '{
        "OnSuccess": {"Destination": "arn:aws:sqs:...:SuccessQueue"},
        "OnFailure": {"Destination": "arn:aws:sqs:...:DLQ"}
    }'

# DLQ: solo per fallimenti (alternativa a Destinations, meno informazioni)
aws lambda update-function-configuration \
    --function-name MyFunction \
    --dead-letter-config TargetArn=arn:aws:sqs:...:MyDLQ
```

---

## Lambda Power Tuning

**AWS Lambda Power Tuning** è uno State Machine Step Functions che identifica la configurazione ottimale memoria/costo.

```bash
# Installa tramite SAR (Serverless Application Repository)
# https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-1:451282441545:applications~aws-lambda-power-tuning

# Esegui con payload di test per trovare il sweet spot memoria/costo
# Tool testa automaticamente: 128, 256, 512, 1024, 2048, 3008 MB
# e restituisce grafici costo vs performance
```

---

## SnapStart per Java

**SnapStart** (Java 11+) elimina il cold start Java salvando snapshot dell'ambiente inizializzato.

```bash
aws lambda update-function-configuration \
    --function-name MyJavaFunction \
    --snap-start ApplyOn=PublishedVersions

# Pubblicare versione (SnapStart si attiva solo su versioni pubblicate)
aws lambda publish-version --function-name MyJavaFunction

# Creare alias che punta alla versione con SnapStart
aws lambda create-alias \
    --function-name MyJavaFunction \
    --name prod \
    --function-version 1
```

**Risultato:** riduzione cold start Java da 10-15s a <1s.

---

## Pricing Lambda

- **$0.20 per 1 milione di invocazioni** (+ 1M gratuite/mese)
- **$0.0000166667 per GB-secondo** (+ 400.000 GB-secondi/mese gratuiti)
- arm64 (Graviton): ~20% meno costoso di x86_64
- Provisioned Concurrency: $0.0000041 per GB-secondo provisionato

**Esempio:** funzione 512 MB, 100ms durata, 10M invocazioni/mese:
- `10M × $0.20/1M = $2 (invocazioni)`
- `10M × 0.1s × 0.5GB × $0.0000166667 = $8.33 (duration)`
- Totale: ~$10.33/mese

---

## Riferimenti

- [Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)
- [Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)
- [SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
