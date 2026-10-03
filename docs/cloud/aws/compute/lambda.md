---
title: "AWS Lambda — Serverless"
slug: lambda
category: cloud
tags: [aws, lambda, serverless, functions, triggers, concurrency, cold-start, layers, destinations, event-source-mapping, power-tuning]
search_keywords: [AWS Lambda, serverless, function, trigger, event source, SQS trigger, API Gateway Lambda, SNS Lambda, S3 Lambda, DynamoDB Streams, Kinesis Lambda, EventBridge, concurrency, reserved concurrency, provisioned concurrency, cold start, warm start, Lambda layers, Lambda destinations, Lambda power tuning, SnapStart, Lambda VPC, execution role, function URL, DLQ]
parent: cloud/aws/compute/_index
related: [cloud/aws/messaging/sqs-sns, cloud/aws/messaging/eventbridge-kinesis, cloud/aws/networking/cloudfront, cloud/aws/storage/s3]
official_docs: https://docs.aws.amazon.com/lambda/latest/dg/
status: needs-review
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# AWS Lambda — Serverless

**Lambda** è il servizio serverless di AWS: permette di eseguire codice senza dover provisioning, gestire o scalare alcun server. Si paga solo per il tempo di esecuzione effettivo, con granularità al millisecondo.

Il modello di esecuzione è **event-driven**: Lambda non gira continuamente in attesa di richieste, ma viene invocata solo quando accade qualcosa — una richiesta HTTP arriva all'API Gateway, un messaggio arriva su una coda SQS, un file viene caricato su S3. Questo la rende ideale per carichi di lavoro intermittenti o variabili, dove mantenere un server sempre acceso sarebbe uno spreco.

**Quando usare Lambda:**
- Funzioni di breve durata (fino a 15 minuti) con logica event-driven
- Backend API (con API Gateway o Function URL) che devono scalare a zero in assenza di traffico
- Processing asincrono: trasformazione dati S3, elaborazione messaggi SQS, reazione a eventi DynamoDB
- Automazione e orchestrazione (reazione ad eventi CloudWatch, EventBridge)
- Glue code tra servizi AWS

**Quando NON usare Lambda:**
- Processi che richiedono più di 15 minuti → valuta ECS/Fargate o EC2
- Applicazioni con stato persistente in memoria → Lambda è stateless per definizione
- Workload con traffico costante e alto volume → EC2 o container sono più economici
- Applicazioni che richiedono filesystem locale persistente o molto grande → Lambda può montare EFS, ma `/tmp` è effimero e il mount EFS in VPC aggiunge latenza; per I/O intensivo valuta ECS/EC2
- Workflow lunghi con stato → orchestra con Step Functions (o Lambda durable functions, vedi nota in Fondamentali) invece di una singola funzione

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

**Limiti (fine 2025 — verificare su [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)):**

| Parametro | Limite |
|-----------|--------|
| Timeout massimo | 15 minuti (default alla creazione: 3 s) |
| Memoria | 128 MB - 10 GB |
| vCPU | Proporzionale alla memoria (6 vCPU a 10 GB) |
| Storage temporaneo (/tmp) | 512 MB - 10 GB |
| Package size (zip) | 50 MB (zipped, upload diretto) / 250 MB (unzipped, **layer inclusi**) |
| Package size (container) | 10 GB (immagine non compressa) |
| Payload sincrono | 6 MB (request) / 6 MB (response); con response streaming fino a 200 MB (Function URL) |
| Payload asincrono | 1 MB (era 256 KB fino al 2025) |
| Concurrency default | 1000 per account per Region (account nuovi: spesso molto meno, verificare con `get-account-settings`) |
| Scaling rate | +1000 ambienti ogni 10 s per funzione, finché non si raggiunge il limite account |

!!! note "Vita dell'execution environment"
    Un ambiente può restare caldo per minuti/ore ed essere riusato da più invocazioni, ma AWS **non garantisce** nessuna durata: può essere riciclato in qualsiasi momento (anche dopo ~poche ore al massimo). Non farci affidamento per cache o stato; il cold start si ripresenta ad ogni nuovo ambiente (scale-out, deploy, riciclo).

**Runtime supportati (fine 2025):** Node.js 20/22/24, Python 3.11–3.14, Java 17/21/25, .NET 8, Ruby 3.2–3.4, Go e altri linguaggi compilati via OS-only runtime `provided.al2023`. I runtime vengono deprecati periodicamente (es. Node.js 18, Python 3.8-3.9): controlla la [lista aggiornata](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) prima di scegliere.

!!! info "Novità recenti (re:Invent 2025)"
    **Lambda durable functions** (workflow con checkpoint/replay fino a lunga durata, in codice) e **Lambda Managed Instances** (funzioni su istanze EC2 gestite, per carichi costanti) ampliano i casi d'uso oltre il modello classico. Non sono trattate qui.
    <!-- REVIEW: verificare disponibilità/regioni/pricing di durable functions e Managed Instances ed eventualmente aggiungere sezioni dedicate -->

**Architetture:** `arm64` (Graviton) costa ~20% in meno per GB-secondo e offre in genere miglior price-performance (fino a ~34% secondo AWS); `x86_64` resta necessario se le dipendenze native non hanno build ARM.

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

# Policy base: solo CloudWatch Logs
# (per Lambda in VPC serve AWSLambdaVPCAccessExecutionRole, che include anche i permessi ENI)
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
    --environment "Variables={DB_HOST=rds.company.com,ENV=prod}" \
    --ephemeral-storage Size=1024 \
    --architectures arm64 \
    --description "API handler"
# --ephemeral-storage: dimensione di /tmp in MB
# --architectures arm64: Graviton, ~20% più economico per GB-secondo

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

# Invocare in modo asincrono (--invocation-type Event: risponde 202 subito, retry gestiti da Lambda)
aws lambda invoke \
    --function-name MyFunction \
    --invocation-type Event \
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
        raise   # rilancia: Lambda ritenta se configurato (invocazioni async / event source mapping)

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

La **concurrency** di Lambda è il numero di invocazioni in esecuzione simultaneamente. Per default, un account AWS ha un limite di 1.000 esecuzioni concorrenti per Region, condiviso tra tutte le Lambda functions. Superato questo limite, le invocazioni vengono **throttlate** (rifiutate con errore `TooManyRequestsException`).

Esistono due meccanismi per gestire la concurrency:
- **Reserved Concurrency**: riserva un numero fisso di esecuzioni concorrenti per una funzione, garantendo che non venga "soffocata" dal traffico di altre funzioni — ma allo stesso tempo ponendo un tetto massimo (utile per proteggere sistemi a valle come un database).
- **Provisioned Concurrency**: pre-inizializza un numero fisso di ambienti di esecuzione, eliminando il cold start per le invocazioni che rientrano in quel numero (a costo di pagare per il provisioning anche in assenza di traffico). Oltre la soglia le invocazioni usano ambienti on-demand, quindi con cold start. Si applica a una versione o a un alias, mai a `$LATEST`.

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
    --qualifier 1 \
    --provisioned-concurrent-executions 50
# --qualifier: versione o alias

# Application Auto Scaling per Provisioned Concurrency
# (poi serve anche una scaling policy: put-scaling-policy con target tracking
#  sulla metrica LambdaProvisionedConcurrencyUtilization)
aws application-autoscaling register-scalable-target \
    --service-namespace lambda \
    --resource-id function:MyFunction:prod \
    --scalable-dimension lambda:function:ProvisionedConcurrency \
    --min-capacity 10 \
    --max-capacity 100
```

**Cold Start:** il tempo di inizializzazione dell'ambiente Lambda (download codice, inizializzazione runtime, esecuzione codice fuori dall'handler).

**Ridurre il Cold Start:**
- Usare runtime con init leggero (Node.js, Python); evitare framework pesanti (es. Spring completo) o usare SnapStart
- Minimizzare dimensione package e codice eseguito fuori dall'handler (lazy init di ciò che non serve sempre)
- Più memoria = più CPU: spesso abbassa anche l'`Init Duration` (verificare con Power Tuning)
- **SnapStart** (Java, Python, .NET): snapshot dell'ambiente dopo la fase init, ripristinato al posto di rieseguirla
- Provisioned Concurrency per funzioni latency-sensitive

---

## Triggers — Event Sources

### API Gateway / Function URL

```bash
# Function URL (endpoint HTTP pubblico diretto, senza API Gateway)
aws lambda create-function-url-config \
    --function-name MyFunction \
    --auth-type NONE \
    --cors '{"AllowOrigins": ["*"], "AllowMethods": ["GET","POST"]}'
# --auth-type: NONE (pubblico) oppure AWS_IAM
# Restituisce: https://xxxx.lambda-url.eu-central-1.on.aws/

# Con auth NONE servono le resource-based policy che rendono la URL pubblica
# (dal 2025 per le nuove URL servono entrambe le azioni, non solo InvokeFunctionUrl)
aws lambda add-permission \
    --function-name MyFunction \
    --statement-id url-public-url \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE
aws lambda add-permission \
    --function-name MyFunction \
    --statement-id url-public-invoke \
    --action lambda:InvokeFunction \
    --principal "*" \
    --invoked-via-function-url

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
    --batch-size 10 \
    --maximum-batching-window-in-seconds 30 \
    --function-response-types '["ReportBatchItemFailures"]'
# --batch-size: fino a 10 messaggi per invocazione (FIFO: max 10; standard: fino a 10.000 con batching window)
# --maximum-batching-window-in-seconds: attendi fino a 30 s per riempire il batch (max 300)
# ReportBatchItemFailures: abilita il partial batch failure (vedi handler sotto)
```

!!! warning "SQS: visibility timeout e DLQ"
    Imposta il **visibility timeout** della coda ad almeno 6× il timeout della funzione, altrimenti i messaggi riappaiono mentre sono ancora in elaborazione. La **DLQ va configurata sulla coda sorgente** (redrive policy con `maxReceiveCount`), non sulla Lambda: per le sorgenti SQS la DLQ/Destination della funzione non si applica.

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
# 1) PRIMA la permission: S3 verifica di poter invocare la funzione quando salvi la notifica,
#    altrimenti put-bucket-notification-configuration fallisce
aws lambda add-permission \
    --function-name ProcessUpload \
    --statement-id s3-invoke \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::my-bucket \
    --source-account 123456789012

# 2) Configurare S3 per notificare Lambda su PutObject
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
```

!!! warning "Loop ricorsivo"
    Se la funzione scrive nello stesso bucket/prefisso che la innesca, crea un loop infinito (e costi). Usa prefissi distinti o un bucket di output separato.

### DynamoDB Streams / Kinesis

```bash
# Lambda triggered da DynamoDB Streams
aws lambda create-event-source-mapping \
    --function-name ProcessDDBStream \
    --event-source-arn arn:aws:dynamodb:...:table/MyTable/stream/2026-01-01T00:00:00.000 \
    --batch-size 100 \
    --starting-position LATEST \
    --bisect-batch-on-function-error \
    --maximum-retry-attempts 3 \
    --destination-config '{"OnFailure": {"Destination": "arn:aws:sqs:...:DLQ"}}'
# --starting-position: LATEST, TRIM_HORIZON, AT_TIMESTAMP
# --bisect-batch-on-function-error: su errore divide il batch a metà per isolare il record "poison"
# OnFailure: coda SQS/topic SNS che riceve i metadati dei batch scartati dopo i retry (non i record)
```

Senza `--maximum-retry-attempts` (default: infiniti, fino alla scadenza del record) un record malformato **blocca lo shard**: imposta sempre retry/età massima e una destination di failure.

---

## Lambda Layers

I **Lambda Layers** sono archivi ZIP contenenti librerie, dipendenze o codice condiviso che possono essere riutilizzati da più funzioni Lambda. Senza i Layers, ogni funzione dovrebbe includere le proprie dipendenze nel package — con il rischio di duplicare decine di MB di librerie comuni tra funzioni diverse.

I Layers risolvono due problemi: riducono la dimensione del deployment package della singola funzione (deploy più rapidi) e centralizzano le dipendenze comuni. Non riducono però il cold start: il contenuto dei layer viene comunque scaricato ed estratto e il totale (funzione + layer) resta entro il limite di 250 MB unzipped. Un layer è una versione **immutabile**: per aggiornare una libreria pubblichi una nuova versione e devi riconfigurare ogni funzione (non si propaga da sola).

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

Di default, Lambda gira in una rete gestita da AWS e può accedere a Internet e ai servizi AWS pubblici, ma non alle risorse private del tuo VPC (RDS, ElastiCache, EC2 in subnet private). Configurando Lambda in VPC, la funzione viene connessa alle tue subnet private e può raggiungere queste risorse.

Attenzione: mettere Lambda in VPC ha implicazioni importanti. La funzione perde l'accesso diretto a Internet (richiede un NAT Gateway per le chiamate verso l'esterno). Dal 2019 le ENI (Elastic Network Interface — interfaccia di rete virtuale) sono condivise e create alla configurazione della funzione (Hyperplane), quindi la penalità sul cold start è trascurabile; resta però da dimensionare le subnet (IP disponibili) e da curare le security group.

```bash
aws lambda update-function-configuration \
    --function-name MyFunction \
    --vpc-config "SubnetIds=subnet-private-a,subnet-private-b,SecurityGroupIds=sg-lambda"

# - Richiede NAT Gateway per accesso Internet (Lambda in subnet pubblica NON ottiene IP pubblico)
# - Richiede VPC Endpoints (gateway per S3/DynamoDB, interface per gli altri) per servizi AWS senza Internet
# - L'execution role DEVE includere ec2:CreateNetworkInterface, ec2:DescribeNetworkInterfaces,
#   ec2:DeleteNetworkInterface: più semplice allegare AWSLambdaVPCAccessExecutionRole
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
# Input: lambdaARN, powerValues (default: 128, 256, 512, 1024, 1536, 3008 MB; accetta fino a 10240), num, payload
# Output: grafico costo vs durata e la configurazione consigliata (strategy: cost, speed o balanced)
# Perché serve: CPU e prezzo crescono con la memoria, ma la durata cala → più memoria può costare meno
```
```

---

## SnapStart per Java

**SnapStart** riduce drasticamente il cold start (Java 11+ e, più di recente, Python 3.12+ e .NET 8+) eseguendo la fase init una sola volta alla pubblicazione di una versione: Lambda salva uno snapshot (memoria + disco) dell'ambiente inizializzato e lo ripristina per i nuovi ambienti invece di rieseguire l'init. Attenzione a ciò che l'init cattura: connessioni di rete, seed random e dati temporanei vanno rigenerati con i *runtime hooks*. Non è compatibile con Provisioned Concurrency, EFS e `/tmp` > 512 MB.

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

**Risultato:** AWS indica miglioramenti fino a ~10× sui cold start (tipicamente da multi-secondo a sub-secondo restore per Java); il guadagno dipende dal tempo di init. SnapStart non è gratuito: si pagano cache dello snapshot e restore.
<!-- REVIEW: verificare prezzi SnapStart correnti per runtime -->

Dalla fine del 2025 anche la fase **init** è fatturata per tutti i runtime gestiti: un init pesante costa, non solo rallenta.

---

## Pricing Lambda

Prezzi indicativi us-east-1 (variano per Region; verificare su [Lambda Pricing](https://aws.amazon.com/lambda/pricing/)):

- **$0.20 per 1 milione di invocazioni** (+ 1M gratuite/mese)
- **$0.0000166667 per GB-secondo** x86_64 (+ 400.000 GB-secondi/mese gratuiti); arm64 $0.0000133334 (~20% in meno)
- Provisioned Concurrency: ~$0.0000041667 per GB-secondo provisionato (più la durata d'uso a tariffa ridotta)

**Esempio:** funzione 512 MB, 100ms durata, 10M invocazioni/mese:
- `10M × $0.20/1M = $2 (invocazioni)`
- `10M × 0.1s × 0.5GB × $0.0000166667 = $8.33 (duration)`
- Totale: ~$10.33/mese (x86_64, free tier escluso)

---

## Troubleshooting

### Scenario 1 — Throttling (`TooManyRequestsException`)

**Sintomo**: invocazioni sincrone falliscono con HTTP 429; metrica CloudWatch `Throttles` > 0; messaggi SQS tornano in coda.

**Causa**: concurrency account (default 1000/Region) esaurita da altre funzioni, oppure reserved concurrency della funzione troppo bassa (o impostata a 0, che blocca ogni invocazione).

**Soluzione**: controllare la reserved concurrency, ridurre quella di funzioni meno critiche o chiedere un aumento quota via Service Quotas. Per le sorgenti SQS, limitare `MaximumConcurrency` sull'event source mapping così i throttle non consumano i retry del messaggio.

```bash
aws lambda get-function-concurrency --function-name MyFunction
aws lambda get-account-settings --query 'AccountLimit.ConcurrentExecutions'
aws lambda put-function-concurrency --function-name MyFunction --reserved-concurrent-executions 100
aws lambda update-event-source-mapping --uuid <uuid> --scaling-config MaximumConcurrency=20
```

### Scenario 2 — Timeout (`Task timed out after N seconds`)

**Sintomo**: log con `Task timed out after 3.00 seconds`; invocazioni che terminano sempre al valore di timeout.

**Causa**: timeout default (3 s) troppo basso, memoria insufficiente (CPU proporzionale alla memoria), oppure chiamate di rete bloccate — tipico di Lambda in VPC senza NAT Gateway o VPC Endpoint.

**Soluzione**: alzare timeout e memoria (verificare con Power Tuning), e per funzioni in VPC aggiungere NAT/VPC Endpoint. Il timeout di una funzione dietro API Gateway non deve superare il limite dell'integrazione (29 s di default; per le REST API regionali/private il limite è aumentabile, per le HTTP API resta 30 s).

```bash
aws lambda update-function-configuration --function-name MyFunction --timeout 60 --memory-size 1024
aws logs filter-log-events --log-group-name /aws/lambda/MyFunction --filter-pattern "Task timed out"
```

### Scenario 3 — `AccessDeniedException` / permessi mancanti

**Sintomo**: `User: arn:aws:sts::...:assumed-role/... is not authorized to perform ...` nei log, oppure la sorgente (S3, SNS) non riesce a invocare la funzione.

**Causa**: due policy distinte — l'**execution role** governa cosa la funzione può chiamare; la **resource-based policy** governa chi può invocare la funzione. Confonderle è l'errore più comune.

**Soluzione**: aggiungere l'azione mancante all'execution role (least privilege) oppure `add-permission` per il principal invocante.

```bash
aws lambda get-function --function-name MyFunction --query 'Configuration.Role'
aws lambda get-policy --function-name MyFunction          # chi può invocare
aws iam list-attached-role-policies --role-name lambda-basic-role
aws lambda add-permission --function-name MyFunction --statement-id sns-invoke \
    --action lambda:InvokeFunction --principal sns.amazonaws.com --source-arn <topic-arn>
```

### Scenario 4 — Cold start lenti o `Runtime.OutOfMemory` / `Runtime.ImportModuleError`

**Sintomo**: `Init Duration` elevata in `REPORT`; oppure `Runtime.OutOfMemory` / `Runtime.ImportModuleError: Unable to import module`.

**Causa**: package grande o init pesante fuori dall'handler; memoria troppo bassa; dipendenze compilate per architettura diversa (es. layer x86_64 su funzione arm64) o handler path errato.

**Soluzione**: confrontare `Max Memory Used` con la memoria configurata, ricostruire le dipendenze per l'architettura corretta, verificare `--handler`, usare SnapStart/Provisioned Concurrency per latenza critica.

```bash
aws logs start-query --log-group-name /aws/lambda/MyFunction \
    --start-time $(date -d '-1 hour' +%s) --end-time $(date +%s) \
    --query-string 'filter @type="REPORT" | stats max(@initDuration), max(@maxMemoryUsed/1024/1024) by bin(5m)'
aws lambda get-function-configuration --function-name MyFunction --query '[Handler,Architectures,Layers]'
```

---

## Relazioni

??? info "SQS e SNS — Approfondimento"
    SQS è la sorgente più comune per carichi asincroni con retry e DLQ; SNS fa fan-out verso più Lambda.

    **Approfondimento completo →** [SQS e SNS](../messaging/sqs-sns.md)

??? info "EventBridge e Kinesis — Approfondimento"
    EventBridge instrada eventi (anche schedulati) verso Lambda; Kinesis alimenta funzioni su stream ordinati per shard.

    **Approfondimento completo →** [EventBridge e Kinesis](../messaging/eventbridge-kinesis.md)

??? info "S3 — Approfondimento"
    Le S3 Event Notification invocano Lambda alla creazione/rimozione di oggetti.

    **Approfondimento completo →** [S3](../storage/s3.md)

??? info "CloudFront — Approfondimento"
    CloudFront può eseguire logica edge (Lambda@Edge, CloudFront Functions), non trattata in questa pagina.

    **Approfondimento completo →** [CloudFront](../networking/cloudfront.md)

---

## Riferimenti

- [Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)
- [Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)
- [SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
