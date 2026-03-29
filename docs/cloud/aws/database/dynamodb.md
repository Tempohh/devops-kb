---
title: "Amazon DynamoDB — NoSQL Serverless"
slug: dynamodb
category: cloud
tags: [aws, dynamodb, nosql, serverless, dynamodb-streams, dax, global-tables, transactions, gsi, lsi, partiql, ttl, kinesis]
search_keywords: [dynamodb, nosql, key-value, document store, partition key, sort key, hash key, rcu, wcu, read capacity unit, write capacity unit, provisioned capacity, on-demand, eventually consistent, strongly consistent, lsi, local secondary index, gsi, global secondary index, dax, dynamodb accelerator, global tables, streams, ttl, time to live, transactions, acid, partiql, conditional writes, batch operations, parallel scan, dynamodb export s3, table classes, standard ia]
parent: cloud/aws/database/_index
related: [cloud/aws/database/rds-aurora, cloud/aws/database/altri-db, cloud/aws/security/kms-secrets, cloud/aws/messaging/eventbridge-kinesis]
official_docs: https://docs.aws.amazon.com/dynamodb/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# Amazon DynamoDB — NoSQL Serverless

## Panoramica

Amazon DynamoDB è un database NoSQL fully serverless, chiave-valore e documento, progettato per performance a singola cifra di millisecondi a qualsiasi scala. Non richiede provisioning di server, gestione di cluster, o ottimizzazione di indici B-tree.

**Caratteristiche fondamentali:**
- **Serverless:** nessun server da gestire, nessun patching, scaling automatico
- **Performance:** latenza di lettura/scrittura in singola cifra di ms, sempre (anche a milioni di req/s)
- **Scalabilità:** da zero a trilioni di item, fino a decine di milioni di richieste al secondo
- **Disponibilità:** 99.999% SLA (Service Level Agreement — accordo sulla disponibilità garantita del servizio), dati replicati su 3 AZ automaticamente
- **Nessuna join:** il modello di dati è denormalized-by-design
- **Schema flessibile:** ogni item può avere attributi diversi (fatta eccezione per la primary key)

**Quando NON usare DynamoDB:**
- Query SQL complesse con JOIN tra entità diverse → RDS/Aurora
- Transazioni ACID (Atomicity, Consistency, Isolation, Durability — le 4 proprietà fondamentali di una transazione database affidabile) complesse tra molte tabelle → RDS/Aurora
- Analytics su grandi dataset → Redshift, Athena
- Ricerca full-text → OpenSearch

---

## Concetti Chiave

### Modello Dati

**Tabella:** contenitore di items (equivalente a una tabella SQL, ma senza schema fisso).

**Item:** una singola "riga" (massimo 400 KB per item).

**Attribute:** un campo di un item. Tipi supportati:
- Scalar: `String` (S), `Number` (N), `Binary` (B), `Boolean` (BOOL), `Null` (NULL)
- Document: `Map` (M, equivalente a oggetto JSON), `List` (L, equivalente a array JSON)
- Set: `String Set` (SS), `Number Set` (NS), `Binary Set` (BS) — set di valori unici dello stesso tipo

### Primary Key

Ogni tabella deve avere una primary key, definita alla creazione e immutabile.

**Partition Key (HASH Key) — Simple Primary Key:**
- Un singolo attributo che identifica univocamente l'item
- DynamoDB usa questo valore per distribuire i dati su partizioni fisiche tramite hashing
- Esempio: `userId` per una tabella di utenti

**Partition Key + Sort Key (HASH + RANGE Key) — Composite Primary Key:**
- Due attributi: la partition key per la distribuzione, la sort key per l'ordinamento all'interno della partizione
- Gli item con la stessa partition key vengono archiviati insieme, ordinati per sort key
- Esempio: `userId` (partition) + `timestamp` (sort) per una tabella di sessioni

!!! note "Scelta della partition key"
    La partition key deve avere alta cardinalità per distribuire i dati uniformemente su molte partizioni. Partition key con pochi valori distinti creano "hot partitions" che limitano le performance. Regola: più valori distinti, meglio è.

```python
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Creare una tabella
table = dynamodb.create_table(
    TableName='UserSessions',
    KeySchema=[
        {'AttributeName': 'userId', 'KeyType': 'HASH'},
        {'AttributeName': 'sessionId', 'KeyType': 'RANGE'}
    ],
    AttributeDefinitions=[
        {'AttributeName': 'userId', 'AttributeType': 'S'},
        {'AttributeName': 'sessionId', 'AttributeType': 'S'}
    ],
    BillingMode='PAY_PER_REQUEST'
)
```

```bash
# Creare tabella via CLI
aws dynamodb create-table \
  --table-name UserSessions \
  --attribute-definitions \
    AttributeName=userId,AttributeType=S \
    AttributeName=sessionId,AttributeType=S \
  --key-schema \
    AttributeName=userId,KeyType=HASH \
    AttributeName=sessionId,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --sse-specification Enabled=true,SSEType=KMS,KMSMasterKeyId=alias/my-dynamodb-key \
  --tags Key=Environment,Value=production
```

---

## Capacity Modes

### Provisioned (Manuale + Autoscaling)

Si definisce esplicitamente il throughput in Read Capacity Units (RCU) e Write Capacity Units (WCU). È possibile configurare Application Auto Scaling per adattare automaticamente il throughput in base al traffico.

**RCU — Read Capacity Unit:**
- 1 RCU = 1 strongly consistent read/s per item fino a 4 KB
- 1 RCU = 2 eventually consistent reads/s per item fino a 4 KB
- Per item più grandi: arrotondare per eccesso a multipli di 4 KB

**WCU — Write Capacity Unit:**
- 1 WCU = 1 write/s per item fino a 1 KB
- Per item più grandi: arrotondare per eccesso a multipli di 1 KB
- Transactional write: 2 WCU per 1 KB

**Esempio calcolo:**
- Leggo 10 item/s di 6 KB ciascuno (strongly consistent): 10 × ceil(6/4) = 10 × 2 = 20 RCU
- Scrivo 5 item/s di 3 KB ciascuno: 5 × ceil(3/1) = 5 × 3 = 15 WCU

```bash
# Creare tabella con throughput provisioned
aws dynamodb create-table \
  --table-name Products \
  --attribute-definitions AttributeName=productId,AttributeType=S \
  --key-schema AttributeName=productId,KeyType=HASH \
  --billing-mode PROVISIONED \
  --provisioned-throughput ReadCapacityUnits=100,WriteCapacityUnits=50

# Configurare Application Auto Scaling per RCU
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id "table/Products" \
  --scalable-dimension "dynamodb:table:ReadCapacityUnits" \
  --min-capacity 10 \
  --max-capacity 1000

aws application-autoscaling put-scaling-policy \
  --service-namespace dynamodb \
  --resource-id "table/Products" \
  --scalable-dimension "dynamodb:table:ReadCapacityUnits" \
  --policy-name "DynamoDB-Autoscaling-Reads" \
  --policy-type "TargetTrackingScaling" \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "DynamoDBReadCapacityUtilization"
    },
    "ScaleInCooldown": 60,
    "ScaleOutCooldown": 60
  }'
```

### On-Demand

DynamoDB gestisce automaticamente la capacità in base al traffico. Si paga per le richieste effettive (RRU/WRU).

- **RRU — Request Read Unit:** $0.25 per milione di RRU (strongly consistent), $0.125 per milione (eventually consistent)
- **WRU — Write Request Unit:** $1.25 per milione di WRU

!!! tip "Provisioned vs On-Demand"
    - **On-Demand:** per traffic variabile, unpredictable, o applicazioni nuove. Non richiede capacity planning.
    - **Provisioned con Autoscaling:** per traffic prevedibile. Più economico di On-Demand per carichi costanti.
    - Regola pratica: se paghi > $1.25/milione WRU on-demand per un carico stabile → valuta provisioned.

```bash
# Cambiare una tabella da provisioned a on-demand
aws dynamodb update-table \
  --table-name Products \
  --billing-mode PAY_PER_REQUEST
```

---

## Consistenza delle Letture

**Eventually Consistent (default):**
- Le letture potrebbero non riflettere l'ultimo write (possibile ritardo < 1s)
- Consuma 0.5 RCU per 4 KB
- Sufficiente per la maggior parte dei casi d'uso

**Strongly Consistent:**
- Garantisce che la lettura rifletta il write più recente confermato
- Consuma 1 RCU per 4 KB (il doppio)
- Richiede specificazione esplicita: `ConsistentRead: true`
- Non disponibile per GSI — Global Secondary Index (solo LSI — Local Secondary Index)

```python
# GetItem con strong consistency
response = table.get_item(
    Key={'userId': 'user123', 'sessionId': 'sess456'},
    ConsistentRead=True
)

# Query con eventually consistent (default)
response = table.query(
    KeyConditionExpression='userId = :uid',
    ExpressionAttributeValues={':uid': 'user123'}
)
```

---

## Indici

### LSI — Local Secondary Index

- Stesso partition key della tabella, sort key diversa
- Massimo **5 LSI per tabella**
- Devono essere creati alla creazione della tabella (immutabili)
- Condividono il throughput della tabella
- Supportano strongly consistent reads

**Use case:** stessa entità, diversi ordinamenti. Esempio: tabella ordini con partition key `customerId`, sort key `orderId`; LSI con sort key `orderDate` per query per data.

### GSI — Global Secondary Index

- Partition key e/o sort key **completamente diversi** dalla tabella
- Massimo **20 GSI per tabella** (di default; aumentabile)
- Possono essere creati o eliminati dopo la creazione della tabella
- Hanno throughput separato (RCU/WCU propri, o seguono la tabella se on-demand)
- Solo eventually consistent reads
- Lo storage del GSI è aggiuntivo (si paga separatamente)

**Use case:** query su attributi non-key. Esempio: tabella utenti con partition key `userId`; GSI con partition key `email` per cercare per email.

```bash
# Aggiungere un GSI a una tabella esistente
aws dynamodb update-table \
  --table-name Users \
  --attribute-definitions \
    AttributeName=email,AttributeType=S \
  --global-secondary-index-updates '[{
    "Create": {
      "IndexName": "email-index",
      "KeySchema": [
        {"AttributeName": "email", "KeyType": "HASH"}
      ],
      "Projection": {
        "ProjectionType": "INCLUDE",
        "NonKeyAttributes": ["name", "createdAt", "status"]
      },
      "ProvisionedThroughput": {
        "ReadCapacityUnits": 50,
        "WriteCapacityUnits": 25
      }
    }
  }]'
```

**Projection Types:**
- `ALL`: tutti gli attributi proiettati nell'indice (più storage, query complete)
- `KEYS_ONLY`: solo le chiavi (meno storage, richiede GetItem per attributi aggiuntivi)
- `INCLUDE`: chiavi + attributi specificati (bilanciamento)

```python
# Query su GSI
response = table.query(
    IndexName='email-index',
    KeyConditionExpression=Key('email').eq('user@example.com')
)

# Query con FilterExpression (filtro post-retrieval, non riduce costi)
response = table.query(
    IndexName='email-index',
    KeyConditionExpression=Key('email').eq('user@example.com'),
    FilterExpression=Attr('status').eq('active')
)
```

---

## DynamoDB Streams

DynamoDB Streams cattura ogni modifica alla tabella (INSERT, MODIFY, REMOVE) in un log ordinato per item. I record sono disponibili per 24 ore.

**Stream Record View Types:**
- `KEYS_ONLY`: solo le chiavi dell'item modificato
- `NEW_IMAGE`: l'item dopo la modifica
- `OLD_IMAGE`: l'item prima della modifica
- `NEW_AND_OLD_IMAGES`: prima e dopo (più comune)

**Use case:** event-driven architecture, replica cross-region custom, notifiche, audit trail, mantenere un secondo database in sync.

```bash
# Abilitare Streams
aws dynamodb update-table \
  --table-name Orders \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES

# Ottenere l'ARN dello stream
aws dynamodb describe-table \
  --table-name Orders \
  --query 'Table.LatestStreamArn'
```

**Integrazione con Lambda:**
```python
# Lambda function triggered da DynamoDB Streams
def handler(event, context):
    for record in event['Records']:
        event_name = record['eventName']  # INSERT, MODIFY, REMOVE

        if event_name == 'INSERT':
            new_item = record['dynamodb']['NewImage']
            order_id = new_item['orderId']['S']
            print(f"Nuovo ordine: {order_id}")
            # Inviare notifica, aggiornare cache, ecc.

        elif event_name == 'MODIFY':
            old_item = record['dynamodb']['OldImage']
            new_item = record['dynamodb']['NewImage']
            # Confrontare vecchio e nuovo stato

        elif event_name == 'REMOVE':
            old_item = record['dynamodb']['OldImage']
            # Gestire eliminazione
```

```bash
# Configurare Lambda come consumer degli Streams
aws lambda create-event-source-mapping \
  --function-name process-order-events \
  --event-source-arn arn:aws:dynamodb:us-east-1:123456789012:table/Orders/stream/2024-01-15 \
  --batch-size 100 \
  --starting-position LATEST \
  --bisect-batch-on-function-error \
  --destination-config '{"OnFailure":{"Destination":"arn:aws:sqs:us-east-1:123456789012:dlq"}}'
```

---

## TTL — Time To Live

TTL permette di configurare la scadenza automatica degli item, evitando di dover eliminare manualmente i dati obsoleti. DynamoDB elimina gli item scaduti entro 48 ore dalla scadenza (best effort, non istantaneo).

**Use case:** sessioni utente, token di autenticazione, dati temporanei, cache entries.

```bash
# Abilitare TTL su un attributo della tabella
aws dynamodb update-time-to-live \
  --table-name Sessions \
  --time-to-live-specification Enabled=true,AttributeName=expiresAt
```

```python
import time

# Inserire un item con TTL (expiresAt = timestamp Unix in secondi)
table.put_item(
    Item={
        'sessionId': 'abc123',
        'userId': 'user456',
        'data': {'token': 'xyz789', 'permissions': ['read', 'write']},
        'expiresAt': int(time.time()) + 3600  # scade tra 1 ora
    }
)
```

!!! note "TTL e DynamoDB Streams"
    Gli item eliminati da TTL appaiono negli Streams come eventi REMOVE. Utile per triggere azioni alla scadenza (es. inviare email di sessione scaduta).

---

## DAX — DynamoDB Accelerator

DAX è una cache in-memory fully managed per DynamoDB, compatibile con l'API DynamoDB (non richiede modifiche al codice, solo cambiare l'endpoint). Riduce la latenza da millisecondi a **microsecondi** per le letture.

**Caratteristiche:**
- Write-through cache: ogni write va sia su DAX che su DynamoDB
- Item cache + Query cache separati
- Cluster multi-nodo (1 primary + N read node), Multi-AZ
- VPC-only (non accessibile da Internet)
- Supporta solo l'API DynamoDB (non fa da proxy per altre operazioni)

**Use case:** applicazioni read-heavy con gli stessi item acceduti molto frequentemente (hot items), leaderboard, catalogo prodotti ad alto traffico.

```python
import amazon_dax_client

# Sostituire boto3 con DAX client (stessa API)
dax = amazon_dax_client.AmazonDaxClient(
    endpoints=['my-dax-cluster.xxxxx.dax-clusters.us-east-1.amazonaws.com:8111'],
    region_name='us-east-1'
)

# Usare esattamente come boto3 DynamoDB resource
table = dax.Table('Products')
response = table.get_item(Key={'productId': 'prod123'})
```

```bash
# Creare cluster DAX
aws dax create-cluster \
  --cluster-name my-dax-cluster \
  --node-type dax.r6g.large \
  --replication-factor 3 \
  --iam-role-arn arn:aws:iam::123456789012:role/DAXRole \
  --subnet-group-name my-dax-subnet-group \
  --security-group-ids sg-1234567890 \
  --sse-specification Enabled=true
```

---

## Global Tables

Le Global Tables replicano automaticamente una tabella DynamoDB in **più Region**, con un modello **active-active** (si può scrivere da qualsiasi Region). Ideale per applicazioni globali che richiedono bassa latenza locale.

**Caratteristiche:**
- Replication quasi in real-time (< 1s tipicamente)
- Conflitti di write: "last writer wins" basato su timestamp
- Global Tables v2 (2019): versioning abilitato automaticamente

```bash
# Creare tabella con Global Tables (aggiungere Region)
aws dynamodb create-table \
  --table-name GlobalUsers \
  --attribute-definitions AttributeName=userId,AttributeType=S \
  --key-schema AttributeName=userId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Aggiungere replicas nelle Region target
aws dynamodb update-table \
  --table-name GlobalUsers \
  --replica-updates '[
    {"Create": {"RegionName": "eu-west-1"}},
    {"Create": {"RegionName": "ap-northeast-1"}}
  ]'
```

---

## Transactions

DynamoDB supporta transazioni ACID su item singoli o multipli nella stessa Region. Le transazioni consumano 2x RCU/WCU (il costo raddoppia per la coordinazione).

**TransactGetItems:** lettura atomica di fino a 100 item in modo transazionale.
**TransactWriteItems:** write atomica di fino a 100 item (Put, Update, Delete, ConditionCheck).

```python
# Transazione: trasferisci crediti da utente A a utente B
dynamodb_client = boto3.client('dynamodb')

response = dynamodb_client.transact_write_items(
    TransactItems=[
        {
            'Update': {
                'TableName': 'UserBalances',
                'Key': {'userId': {'S': 'userA'}},
                'UpdateExpression': 'SET balance = balance - :amount',
                'ConditionExpression': 'balance >= :amount',  # fallisce se saldo insufficiente
                'ExpressionAttributeValues': {':amount': {'N': '100'}}
            }
        },
        {
            'Update': {
                'TableName': 'UserBalances',
                'Key': {'userId': {'S': 'userB'}},
                'UpdateExpression': 'SET balance = balance + :amount',
                'ExpressionAttributeValues': {':amount': {'N': '100'}}
            }
        }
    ],
    ClientRequestToken='unique-idempotency-key-12345'  # per idempotenza
)
```

!!! warning "Transazioni cross-table"
    DynamoDB transactions supportano item in tabelle diverse nella stessa Region (e stesso account). Non supportano cross-Region.

---

## Conditional Writes

I Conditional Writes permettono di scrivere un item solo se una condizione è verificata, garantendo atomic check-and-write senza transazioni.

```python
from boto3.dynamodb.conditions import Attr

# Crea item solo se non esiste (PUT con condition)
try:
    table.put_item(
        Item={'userId': 'user123', 'email': 'user@example.com', 'status': 'active'},
        ConditionExpression='attribute_not_exists(userId)'
    )
except table.meta.client.exceptions.ConditionalCheckFailedException:
    print("Utente già esistente")

# Aggiorna solo se il valore corrente è quello atteso (optimistic locking)
try:
    table.update_item(
        Key={'userId': 'user123'},
        UpdateExpression='SET version = :newV, status = :status',
        ConditionExpression='version = :currentV',
        ExpressionAttributeValues={
            ':newV': 2,
            ':currentV': 1,
            ':status': 'premium'
        }
    )
except table.meta.client.exceptions.ConditionalCheckFailedException:
    print("Versione modificata da un altro processo — riprova")
```

---

## PartiQL

PartiQL è un linguaggio di query SQL-compatible per DynamoDB. Permette di usare sintassi SQL familiar per operazioni CRUD.

```bash
# Query con PartiQL via CLI
aws dynamodb execute-statement \
  --statement "SELECT userId, email, status FROM Users WHERE userId = 'user123'"

# Insert
aws dynamodb execute-statement \
  --statement "INSERT INTO Users VALUE {'userId': 'user789', 'email': 'new@example.com', 'status': 'active'}"

# Update
aws dynamodb execute-statement \
  --statement "UPDATE Users SET status = 'inactive' WHERE userId = 'user789'"

# Delete
aws dynamodb execute-statement \
  --statement "DELETE FROM Users WHERE userId = 'user789'"
```

!!! warning "PartiQL NON supporta JOIN"
    PartiQL su DynamoDB non supporta JOIN tra tabelle. DynamoDB rimane un database NoSQL; PartiQL è solo syntactic sugar SQL, non trasforma DynamoDB in un database relazionale.

---

## Backup

**Point-In-Time Recovery (PITR):**
- Abilita ripristino continuo agli ultimi 35 giorni
- Granularità al secondo
- Ripristino crea una nuova tabella (non sovrascrive)

```bash
# Abilitare PITR
aws dynamodb update-continuous-backups \
  --table-name Orders \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Ripristinare a un punto specifico
aws dynamodb restore-table-to-point-in-time \
  --source-table-name Orders \
  --target-table-name Orders-restored-20240115 \
  --restore-date-time "2024-01-15T14:30:00Z" \
  --billing-mode-override PAY_PER_REQUEST
```

**On-Demand Backup:**
- Snapshot completo della tabella
- Non scade automaticamente
- Costo: $0.10 per GB/mese

```bash
# Creare backup on-demand
aws dynamodb create-backup \
  --table-name Orders \
  --backup-name orders-backup-20240115

# Ripristinare da backup
aws dynamodb restore-table-from-backup \
  --target-table-name Orders-from-backup \
  --backup-arn arn:aws:dynamodb:us-east-1:123456789012:table/Orders/backup/01234567
```

---

## Export to S3

DynamoDB può esportare l'intera tabella su S3 in formato JSON o Parquet, senza impatto sulle performance della tabella. Utile per analytics con Athena, data lake, migrazione.

```bash
# Esportare tabella su S3 (Parquet)
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:us-east-1:123456789012:table/Orders \
  --s3-bucket my-data-lake \
  --s3-prefix dynamodb-exports/orders/ \
  --export-format DYNAMODB_JSON \
  --export-time "2024-01-15T00:00:00Z"

# Con Parquet per Athena
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:us-east-1:123456789012:table/Orders \
  --s3-bucket my-data-lake \
  --s3-prefix dynamodb-exports/orders-parquet/ \
  --export-format PARQUET
```

---

## Kinesis Data Streams Integration

DynamoDB può inviare le modifiche degli item direttamente a Kinesis Data Streams (alternativa a DynamoDB Streams con retention più lunga e integrazione con Kinesis ecosystem).

```bash
# Abilitare Kinesis integration
aws dynamodb enable-kinesis-streaming-destination \
  --table-name Orders \
  --stream-arn arn:aws:kinesis:us-east-1:123456789012:stream/orders-stream
```

---

## Table Classes

| Classe | Costo Storage | Costo Throughput | Use Case |
|--------|--------------|-----------------|---------|
| **Standard** | $0.25/GB/mese | Normale | Dati acceduti frequentemente |
| **Standard-IA** | $0.10/GB/mese (+75% throughput cost) | +25% più costoso | Dati acceduti raramente |

Standard-IA conviene per tabelle grandi dove l'accesso è infrequente (tabelle di log, archivio storico, audit trail).

```bash
# Cambiare la table class
aws dynamodb update-table \
  --table-name ArchivedOrders \
  --table-class STANDARD_INFREQUENT_ACCESS
```

---

## Operazioni CRUD Complete

```python
import boto3
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('Products')

# PUT ITEM — crea o sostituisce completamente
table.put_item(
    Item={
        'productId': 'prod-001',
        'name': 'Widget Pro',
        'category': 'electronics',
        'price': 29.99,
        'stock': 100,
        'tags': ['sale', 'featured'],
        'metadata': {'color': 'blue', 'weight': 0.5}
    }
)

# GET ITEM — lettura per primary key
response = table.get_item(
    Key={'productId': 'prod-001'},
    ProjectionExpression='productId, #n, price',  # '#n' aliasa 'name' (reserved word)
    ExpressionAttributeNames={'#n': 'name'}
)
item = response.get('Item')

# UPDATE ITEM — aggiorna attributi specifici
table.update_item(
    Key={'productId': 'prod-001'},
    UpdateExpression='SET price = :p, stock = stock - :qty, #ts = :ts ADD viewCount :one',
    ExpressionAttributeNames={'#ts': 'lastUpdated'},
    ExpressionAttributeValues={
        ':p': 24.99,
        ':qty': 5,
        ':ts': '2024-01-15T10:00:00Z',
        ':one': 1
    },
    ReturnValues='UPDATED_NEW'  # restituisce i valori aggiornati
)

# DELETE ITEM
table.delete_item(
    Key={'productId': 'prod-001'},
    ConditionExpression=Attr('stock').eq(0)  # elimina solo se esaurito
)

# QUERY — cerca per partition key (+ sort key opzionale)
response = table.query(
    KeyConditionExpression=Key('category').eq('electronics') & Key('price').lt(50),
    IndexName='category-price-index',  # GSI
    FilterExpression=Attr('stock').gt(0),
    Limit=20,
    ScanIndexForward=False  # ordine decrescente della sort key
)
items = response['Items']

# Paginazione (DynamoDB restituisce max 1 MB per chiamata)
while 'LastEvaluatedKey' in response:
    response = table.query(
        KeyConditionExpression=Key('category').eq('electronics'),
        ExclusiveStartKey=response['LastEvaluatedKey'],
        Limit=20
    )
    items.extend(response['Items'])

# SCAN — scansione intera tabella (costoso, evitare in prod)
response = table.scan(
    FilterExpression=Attr('category').eq('electronics') & Attr('price').lt(30),
    Limit=100
)

# PARALLEL SCAN — divide la tabella in N segmenti paralleli
import concurrent.futures

def scan_segment(segment_id, total_segments):
    resp = table.scan(
        Segment=segment_id,
        TotalSegments=total_segments
    )
    return resp['Items']

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(scan_segment, i, 4) for i in range(4)]
    all_items = [item for f in futures for item in f.result()]

# BATCH OPERATIONS
# BatchWriteItem — fino a 25 item per chiamata
with table.batch_writer() as batch:
    for i in range(100):
        batch.put_item(Item={
            'productId': f'prod-{i:03d}',
            'name': f'Product {i}',
            'price': i * 1.99
        })

# BatchGetItem — fino a 100 item per chiamata
response = dynamodb.batch_get_item(
    RequestItems={
        'Products': {
            'Keys': [
                {'productId': 'prod-001'},
                {'productId': 'prod-002'},
                {'productId': 'prod-003'}
            ],
            'ConsistentRead': False
        }
    }
)
```

---

## Best Practices

### Modello Dati

1. **Single-Table Design:** consolidare entità correlate in un'unica tabella con overloaded keys. Riduce le chiamate API e i costi.
2. **Partition key ad alta cardinalità:** UUID, userId, productId — non status, country, category
3. **Evitare hot partitions:** distribuire il carico su molte partition key
4. **Sparse indexes:** usare GSI con attributi presenti solo su alcuni item (GSI non indicizza item senza quell'attributo)

### Performance

1. **Eventually consistent reads** quando possibile (costo dimezzato)
2. **Query invece di Scan** — Query usa l'indice; Scan legge tutta la tabella
3. **ProjectionExpression** per recuperare solo gli attributi necessari
4. **DAX** per applicazioni read-heavy con hot items

### Costi

1. **On-Demand per carichi variabili**, Provisioned + Autoscaling per carichi stabili
2. **Standard-IA** per tabelle con > 1 GB e accesso infrequente
3. **TTL** per eliminare automaticamente i dati scaduti
4. **Export to S3** per analytics invece di query Scan frequenti

---

## Troubleshooting

### "ProvisionedThroughputExceededException"

```bash
# Verificare throttling in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ThrottledRequests \
  --dimensions Name=TableName,Value=Products Name=Operation,Value=PutItem \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T01:00:00Z \
  --period 300 \
  --statistics Sum
```

Soluzioni:
1. Aumentare il throughput provisioned o usare On-Demand
2. Verificare hot partitions (CloudWatch → ConsumedWriteCapacityUnits per partition)
3. Implementare exponential backoff nelle retry
4. Distribuire meglio le writes su più partition keys

### Latenza Alta

1. Verificare item size — item grandi richiedono più RCU e hanno latenza più alta
2. Usare ProjectionExpression per recuperare solo i campi necessari
3. Considerare DAX per hot reads
4. Verificare la Region — connettiti sempre alla Region più vicina

### Scenario 3 — ConditionalCheckFailedException inatteso

**Sintomo:** `ConditionalCheckFailedException` viene sollevata anche quando si presume che la condizione sia verificata, causando fallimenti intermittenti in operazioni concurrent.

**Causa:** Race condition tra più processi che leggono lo stesso item e tentano di aggiornarlo basandosi su un attributo di versione o su `attribute_not_exists`. Il valore letto è già stato modificato al momento della scrittura.

**Soluzione:** Implementare optimistic locking con retry limitato e backoff esponenziale. Loggare i conflitti per rilevare pattern anomali.

```python
import time
import random

def update_with_retry(table, key, version, max_retries=3):
    for attempt in range(max_retries):
        try:
            table.update_item(
                Key=key,
                UpdateExpression='SET version = :newV, #data = :data',
                ConditionExpression='version = :currentV',
                ExpressionAttributeNames={'#data': 'data'},
                ExpressionAttributeValues={
                    ':newV': version + 1,
                    ':currentV': version,
                    ':data': 'updated'
                }
            )
            return True
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            if attempt == max_retries - 1:
                raise
            # Exponential backoff con jitter
            wait = (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(wait)
            # Ri-leggere il valore corrente
            response = table.get_item(Key=key, ConsistentRead=True)
            version = response['Item']['version']
    return False
```

### Scenario 4 — Item size supera il limite di 400 KB

**Sintomo:** `ValidationException: Item size has exceeded the maximum allowed size` durante PutItem o UpdateItem.

**Causa:** Un singolo item DynamoDB non può superare 400 KB. Attributi con contenuto binario, JSON annidato profondo, o liste di grandi dimensioni provocano il superamento del limite.

**Soluzione:** Decomposizione dell'item: spostare i payload grandi su S3 e conservare in DynamoDB solo il riferimento (S3 key). Oppure suddividere l'item in chunk con sort key progressiva.

```bash
# Verificare la dimensione dell'item corrente
aws dynamodb get-item \
  --table-name Documents \
  --key '{"docId": {"S": "doc-001"}}' \
  --query 'Item' | python3 -c "
import sys, json
item = json.load(sys.stdin)
size = len(json.dumps(item).encode('utf-8'))
print(f'Item size approssimativa: {size} bytes ({size/1024:.1f} KB)')
"

# Pattern: memorizzare payload su S3, riferimento in DynamoDB
aws s3 cp large-payload.json s3://my-bucket/documents/doc-001/payload.json

aws dynamodb update-item \
  --table-name Documents \
  --key '{"docId": {"S": "doc-001"}}' \
  --update-expression 'SET payloadRef = :ref, payloadBucket = :bucket REMOVE largeAttribute' \
  --expression-attribute-values '{
    ":ref": {"S": "documents/doc-001/payload.json"},
    ":bucket": {"S": "my-bucket"}
  }'
```

---

## Relazioni

??? info "Aurora Serverless v2 — Alternativa OLTP"
    Per workload relazionali con scaling variabile, Aurora Serverless v2 è l'alternativa managed SQL.

    **Approfondimento completo →** [RDS e Aurora](rds-aurora.md)

??? info "DAX — Caching"
    DAX è la cache nativa di DynamoDB. Per caching applicativo più generico considerare ElastiCache Redis.

    **Approfondimento completo →** [Altri Database AWS](altri-db.md)

??? info "Kinesis / EventBridge — Event Streaming"
    DynamoDB Streams si integra con Lambda, Kinesis, e EventBridge per architetture event-driven.

    **Approfondimento completo →** [EventBridge e Kinesis](../messaging/eventbridge-kinesis.md)

---

## Riferimenti

- [DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/latest/developerguide/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [DynamoDB Single-Table Design](https://www.alexdebrie.com/posts/dynamodb-single-table/)
- [DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
- [DynamoDB Global Tables](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html)
- [PartiQL for DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ql-reference.html)
- [DynamoDB Transactions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transactions.html)
- [The DynamoDB Book — Alex DeBrie](https://www.dynamodbbook.com/)
