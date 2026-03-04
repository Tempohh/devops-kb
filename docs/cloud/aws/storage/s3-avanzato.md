---
title: "Amazon S3 — Sicurezza e Funzionalità Avanzate"
slug: s3-avanzato
category: cloud
tags: [aws, s3, security, encryption, sse-kms, object-lock, worm, s3-select, object-lambda, event-notifications, access-points, cors, batch-operations]
search_keywords: [s3 security, block public access, bucket policy, sse-s3, sse-kms, sse-c, dsse-kms, server side encryption, object lock, compliance mode, governance mode, worm, legal hold, s3 select, object lambda, event notifications, s3 inventory, access points, cors, s3 batch operations, bucket key, s3 performance, byte range fetch]
parent: cloud/aws/storage/_index
related: [cloud/aws/storage/s3, cloud/aws/security/kms-secrets, cloud/aws/security/compliance-audit, cloud/aws/messaging/eventbridge-kinesis]
official_docs: https://docs.aws.amazon.com/s3/latest/userguide/security.html
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# Amazon S3 — Sicurezza e Funzionalità Avanzate

## Panoramica

Questo documento approfondisce le funzionalità avanzate di S3: sicurezza granulare (Block Public Access, Bucket Policy, Encryption), immutabilità dei dati (Object Lock), query intelligenti su oggetti (S3 Select, Object Lambda), event-driven architecture (Event Notifications), inventario e operazioni di massa (Inventory, Batch Operations), performance tuning e access governance (Access Points, CORS).

Queste funzionalità sono frequentemente oggetto di domande nell'esame AWS SAA-C03 e DOP-C02.

---

## Concetti Chiave: Block Public Access

Block Public Access è la prima linea di difesa contro l'esposizione accidentale di dati pubblici. Può essere configurato a livello di **account** (sovrascrive tutto) o a livello di **singolo bucket**.

### Le 4 Impostazioni

| Impostazione | Descrizione |
|-------------|-------------|
| **BlockPublicAcls** | Blocca le nuove ACL pubbliche e blocca le richieste PUT Object che includono ACL pubbliche |
| **IgnorePublicAcls** | Ignora tutte le ACL pubbliche esistenti su bucket e oggetti |
| **BlockPublicPolicy** | Blocca le bucket policy che concedono accesso pubblico |
| **RestrictPublicBuckets** | Restringe l'accesso pubblico e cross-account ai bucket con policy pubbliche |

!!! tip "Best practice"
    Abilitare tutte e 4 le impostazioni a livello di account come baseline. Abilitare selettivamente solo dove necessario per bucket che devono essere pubblici (es. sito statico).

```bash
# Configurare Block Public Access a livello account
aws s3control put-public-access-block \
  --account-id 123456789012 \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,\
BlockPublicPolicy=true,RestrictPublicBuckets=true

# Verificare configurazione account
aws s3control get-public-access-block --account-id 123456789012

# Configurare su singolo bucket
aws s3api put-public-access-block \
  --bucket my-bucket \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,\
BlockPublicPolicy=true,RestrictPublicBuckets=true
```

---

## Bucket Policy

La Bucket Policy è una resource-based IAM policy JSON allegata al bucket. Permette di controllare l'accesso con granularità elevata, inclusi accessi cross-account.

### Struttura di una Bucket Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StatementID",
      "Effect": "Allow|Deny",
      "Principal": "*" | "arn:aws:iam::ACCOUNT-ID:root" | {"AWS": "..."},
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"],
      "Condition": {...}
    }
  ]
}
```

### Esempi Pratici

**1. Deny accesso non-HTTPS (forza TLS):**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyNonHTTPS",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:*",
    "Resource": [
      "arn:aws:s3:::my-bucket",
      "arn:aws:s3:::my-bucket/*"
    ],
    "Condition": {
      "Bool": {
        "aws:SecureTransport": "false"
      }
    }
  }]
}
```

**2. Allow accesso cross-account:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "CrossAccountAccess",
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::999888777666:root"
    },
    "Action": ["s3:GetObject", "s3:ListBucket"],
    "Resource": [
      "arn:aws:s3:::my-bucket",
      "arn:aws:s3:::my-bucket/*"
    ]
  }]
}
```

**3. Deny upload senza encryption SSE-KMS:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyUnencryptedUploads",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::my-bucket/*",
    "Condition": {
      "StringNotEquals": {
        "s3:x-amz-server-side-encryption": "aws:kms"
      }
    }
  }]
}
```

**4. Restrict accesso a VPC specifico (VPC Endpoint):**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyExternalAccess",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:*",
    "Resource": [
      "arn:aws:s3:::my-bucket",
      "arn:aws:s3:::my-bucket/*"
    ],
    "Condition": {
      "StringNotEquals": {
        "aws:SourceVpce": "vpce-1234567890abcdef0"
      }
    }
  }]
}
```

```bash
# Applicare una bucket policy
aws s3api put-bucket-policy \
  --bucket my-bucket \
  --policy file://bucket-policy.json

# Leggere la policy esistente
aws s3api get-bucket-policy --bucket my-bucket --query Policy --output text | python3 -m json.tool
```

### ACL (Access Control Lists)

Le ACL sono un meccanismo legacy, AWS raccomanda di usare le bucket policy. L'impostazione "Object Ownership" a **Bucket owner enforced** disabilita le ACL (raccomandato).

```bash
# Disabilitare ACL (Object Ownership → Bucket owner enforced)
aws s3api put-bucket-ownership-controls \
  --bucket my-bucket \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'
```

**Quando usare ancora le ACL:** solo quando si ricevono oggetti da account esterni e non si può usare una bucket policy (raro, praticamente mai nelle architetture moderne).

---

## Server-Side Encryption (SSE)

S3 supporta 4 meccanismi di cifratura server-side. Dal 2023 la cifratura SSE-S3 è **abilitata di default** su tutti i bucket.

### Tabella Comparativa SSE

| Tipo | Gestione Chiave | Algoritmo | Audit Key Usage | Costo |
|------|----------------|-----------|----------------|-------|
| **SSE-S3** | AWS (non visibile) | AES-256 | No | Incluso |
| **SSE-KMS** | AWS KMS (customer managed) | AES-256 | CloudTrail | $0.03/10K API calls |
| **SSE-C** | Cliente (passata nella richiesta) | AES-256 | No | Incluso |
| **DSSE-KMS** | AWS KMS (dual layer) | AES-256 x2 | CloudTrail | $0.03/10K API calls |

### SSE-S3 (Amazon S3 Managed Keys)

La chiave di cifratura è gestita interamente da AWS. Rotazione automatica. Non è possibile controllare chi usa la chiave tramite IAM.

```bash
# Impostare SSE-S3 come default per tutti gli upload
aws s3api put-bucket-encryption \
  --bucket my-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": false
    }]
  }'
```

### SSE-KMS (AWS KMS Managed Keys)

La chiave è gestita in AWS KMS. Permette audit via CloudTrail di ogni operazione di decrypt. Supporta sia AWS Managed Keys (`aws/s3`) che Customer Managed Keys.

```bash
# Impostare SSE-KMS come default con una Customer Managed Key
aws s3api put-bucket-encryption \
  --bucket my-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "arn:aws:kms:us-east-1:123456789012:key/mrk-1234abcd..."
      },
      "BucketKeyEnabled": true
    }]
  }'

# Caricare un oggetto con SSE-KMS
aws s3 cp file.txt s3://my-bucket/ \
  --sse aws:kms \
  --sse-kms-key-id arn:aws:kms:us-east-1:123456789012:key/mrk-1234abcd
```

### Bucket Key per Ridurre Costi KMS

Senza Bucket Key, ogni operazione S3 (`GetObject`, `PutObject`) genera una chiamata KMS separata (`GenerateDataKey`). Con Bucket Key abilitato, S3 genera una data key di sessione a livello bucket, riducendo le chiamate KMS fino al 99% e i costi KMS proporzionalmente.

!!! note "Abilitare sempre Bucket Key con SSE-KMS"
    Il Bucket Key non riduce la sicurezza ma può ridurre drasticamente i costi KMS quando si hanno molti oggetti. Abilitarlo è quasi sempre la scelta corretta.

### SSE-C (Customer-Provided Keys)

Il cliente gestisce e trasmette la chiave in ogni richiesta. AWS non memorizza mai la chiave. Se si perde la chiave, i dati sono irrecuperabili.

```bash
# Caricare con SSE-C (la chiave deve essere passata come header)
# Generare una chiave AES-256 (32 bytes)
KEY=$(openssl rand -base64 32)
KEY_MD5=$(echo -n "$KEY" | base64 -d | openssl md5 -binary | base64)

aws s3api put-object \
  --bucket my-bucket \
  --key file.txt \
  --body file.txt \
  --sse-customer-algorithm AES256 \
  --sse-customer-key "$KEY" \
  --sse-customer-key-md5 "$KEY_MD5"
```

!!! warning "SSE-C e HTTPS"
    SSE-C richiede HTTPS obbligatoriamente. Il trasferimento della chiave via HTTP non è permesso.

### DSSE-KMS (Dual-Layer Server-Side Encryption)

Doppio layer di cifratura KMS (due data key separate). Richiesto da alcuni framework di compliance governativi. Non è necessario per la maggior parte dei workload.

---

## S3 Object Lock (WORM Storage)

Object Lock implementa il modello WORM (Write Once Read Many): impedisce che un oggetto venga eliminato o sovrascritto per un periodo configurabile o indefinitamente. Richiede versioning abilitato.

**Use case:** conformità normativa (SEC Rule 17a-4, FINRA, FDA 21 CFR Part 11), protezione da ransomware, audit trails immutabili.

### Retention Modes

**COMPLIANCE Mode:**
- L'oggetto NON può essere eliminato né sovrascritto da nessun utente, incluso root
- Il retention period NON può essere ridotto (solo esteso)
- Il mode NON può essere cambiato in GOVERNANCE
- Scelta per conformità normativa stringente

**GOVERNANCE Mode:**
- Gli utenti con permesso speciale `s3:BypassGovernanceRetention` possono sovrascrivere o eliminare
- Permette test e operazioni amministrative mantenendo protezione di default
- Più flessibile di COMPLIANCE, meno assoluto

### Legal Hold

Un Legal Hold blocca l'eliminazione/sovrascrittura indipendentemente dal retention period. Può essere applicato/rimosso da utenti con permesso `s3:PutObjectLegalHold` in qualsiasi momento.

**Use case:** preservare oggetti durante una causa legale o un'indagine, indipendentemente dalla policy di retention configurata.

```bash
# Abilitare Object Lock durante la creazione del bucket
aws s3api create-bucket \
  --bucket my-compliant-bucket \
  --object-lock-enabled-for-bucket

# Configurare retention di default del bucket (tutti gli oggetti)
aws s3api put-object-lock-configuration \
  --bucket my-compliant-bucket \
  --object-lock-configuration '{
    "ObjectLockEnabled": "Enabled",
    "Rule": {
      "DefaultRetention": {
        "Mode": "COMPLIANCE",
        "Days": 2555
      }
    }
  }'

# Mettere un oggetto con retention specifica
aws s3api put-object \
  --bucket my-compliant-bucket \
  --key important-record.pdf \
  --body important-record.pdf \
  --object-lock-mode COMPLIANCE \
  --object-lock-retain-until-date "2034-01-01T00:00:00Z"

# Applicare Legal Hold
aws s3api put-object-legal-hold \
  --bucket my-compliant-bucket \
  --key important-record.pdf \
  --legal-hold Status=ON

# Rimuovere Legal Hold
aws s3api put-object-legal-hold \
  --bucket my-compliant-bucket \
  --key important-record.pdf \
  --legal-hold Status=OFF

# Verificare lo stato di lock
aws s3api get-object-retention \
  --bucket my-compliant-bucket \
  --key important-record.pdf

aws s3api get-object-legal-hold \
  --bucket my-compliant-bucket \
  --key important-record.pdf
```

---

## S3 Select

S3 Select permette di eseguire query SQL direttamente su oggetti S3 (CSV, JSON, Parquet, Parquet compresso con GZIP/BZIP2) **senza scaricare l'intero oggetto**. S3 filtra i dati lato server e restituisce solo il subset richiesto.

**Vantaggi:**
- Riduzione trasferimento dati fino all'80%
- Riduzione costi di trasferimento dati e latenza
- Filtraggio lato S3 prima di inviare al client

**Limitazioni:**
- Query su un singolo oggetto per volta (non su interi bucket)
- SQL subset limitato: `SELECT`, `WHERE`, `LIMIT`, aggregazioni di base
- Non supporta JOIN, subquery, funzioni definite dall'utente

```bash
# Query su file CSV (prima riga è header)
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/sales-2024.csv \
  --expression "SELECT * FROM S3Object WHERE region = 'EU' AND revenue > 10000" \
  --expression-type SQL \
  --input-serialization '{
    "CSV": {
      "FileHeaderInfo": "USE",
      "RecordDelimiter": "\n",
      "FieldDelimiter": ","
    },
    "CompressionType": "GZIP"
  }' \
  --output-serialization '{"CSV": {}}' \
  /dev/stdout

# Query su file JSON
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/events.json \
  --expression "SELECT s.eventType, s.userId, s.timestamp FROM S3Object s WHERE s.eventType = 'purchase'" \
  --expression-type SQL \
  --input-serialization '{"JSON": {"Type": "LINES"}}' \
  --output-serialization '{"JSON": {"RecordDelimiter": "\n"}}' \
  /dev/stdout

# Query su Parquet (senza specificare tipo file, S3 lo rileva)
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/users.parquet \
  --expression "SELECT name, email FROM S3Object WHERE age > 30" \
  --expression-type SQL \
  --input-serialization '{"Parquet": {}}' \
  --output-serialization '{"JSON": {"RecordDelimiter": "\n"}}' \
  output.json
```

!!! note "S3 Select vs Amazon Athena"
    S3 Select è per query su un singolo oggetto. Athena è per query su un intero dataset distribuito su molti file S3. Athena è più potente e flessibile, ma S3 Select è più economico per filtrare un singolo file.

---

## S3 Object Lambda

S3 Object Lambda permette di trasformare l'output di `GetObject` con una funzione Lambda prima che venga restituito al richiedente. Non modifica l'oggetto originale.

**Use case:**
- Rimuovere PII (Personally Identifiable Information) prima di consegnare dati a team analytics
- Aggiungere watermark a immagini/PDF
- Convertire formato dati (XML → JSON) on-the-fly
- Comprimere/decomprimere dati in base al client
- Filtrare righe in base alle autorizzazioni dell'utente

### Architettura

```
Client → S3 Object Lambda Access Point → Lambda Function
                                              ↓
                                    S3 Supporting Access Point → S3 Bucket
                                    (scarica oggetto originale)
```

```bash
# Creare un Access Point standard (necessario per Object Lambda)
aws s3control create-access-point \
  --account-id 123456789012 \
  --name my-supporting-ap \
  --bucket my-bucket

# Creare l'Object Lambda Access Point
aws s3control create-access-point-for-object-lambda \
  --account-id 123456789012 \
  --name my-object-lambda-ap \
  --configuration '{
    "SupportingAccessPoint": "arn:aws:s3:us-east-1:123456789012:accesspoint/my-supporting-ap",
    "TransformationConfigurations": [{
      "Actions": ["GetObject"],
      "ContentTransformation": {
        "AwsLambda": {
          "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-transform-fn"
        }
      }
    }]
  }'
```

**Esempio Lambda function (rimuove PII da CSV):**
```python
import boto3
import urllib.request
import csv
import io

s3_client = boto3.client('s3')

def handler(event, context):
    # URL pre-firmato dell'oggetto originale
    object_context = event["getObjectContext"]
    request_route = object_context["outputRoute"]
    request_token = object_context["outputToken"]
    s3_url = object_context["inputS3Url"]

    # Scaricare l'oggetto originale
    response = urllib.request.urlopen(s3_url)
    original_content = response.read().decode('utf-8')

    # Trasformare: rimuovere colonne PII (es. colonna "ssn")
    reader = csv.DictReader(io.StringIO(original_content))
    output = io.StringIO()
    # Escludere colonne sensibili
    fieldnames = [f for f in reader.fieldnames if f not in ['ssn', 'credit_card']]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in reader:
        filtered_row = {k: v for k, v in row.items() if k in fieldnames}
        writer.writerow(filtered_row)

    transformed_content = output.getvalue()

    # Restituire il contenuto trasformato
    s3_client.write_get_object_response(
        Body=transformed_content,
        RequestRoute=request_route,
        RequestToken=request_token,
        ContentType="text/csv"
    )

    return {'status_code': 200}
```

---

## Event Notifications

S3 Event Notifications inviano notifiche automatiche quando avvengono eventi nel bucket (creazione, eliminazione, restore, replica).

### Tipi di Evento

- `s3:ObjectCreated:*` — qualsiasi PUT/POST/COPY
- `s3:ObjectRemoved:*` — DELETE (incluso delete marker)
- `s3:ObjectRestore:*` — restore da Glacier
- `s3:Replication:*` — eventi di replication (missed, failed, completed)
- `s3:LifecycleExpiration:*` — expiration lifecycle
- `s3:IntelligentTiering` — transizioni Intelligent-Tiering
- `s3:ObjectTagging:*` — modifica tag

### Destinazioni

| Destinazione | Use Case |
|-------------|---------|
| **Amazon SNS** | Fan-out notifiche a più subscriber |
| **Amazon SQS** | Code per elaborazione asincrona (file processing) |
| **AWS Lambda** | Elaborazione immediata (thumbnail, parsing, validation) |
| **Amazon EventBridge** | Routing avanzato, filtraggio, multi-destination |

!!! tip "EventBridge vs notifiche dirette"
    Usare EventBridge quando si ha bisogno di filtraggio avanzato sulle proprietà degli oggetti, routing verso destinazioni multiple, o replay degli eventi. Le notifiche dirette (SNS/SQS/Lambda) sono più semplici per use case straightforward.

```bash
# Configurare notifiche S3 verso Lambda
cat > notification-config.json << 'EOF'
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "ProcessNewImages",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:process-image",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "uploads/"},
            {"Name": "suffix", "Value": ".jpg"}
          ]
        }
      }
    }
  ],
  "QueueConfigurations": [
    {
      "Id": "AuditQueue",
      "QueueArn": "arn:aws:sqs:us-east-1:123456789012:audit-queue",
      "Events": ["s3:ObjectRemoved:*"]
    }
  ]
}
EOF

aws s3api put-bucket-notification-configuration \
  --bucket my-bucket \
  --notification-configuration file://notification-config.json

# Notifiche verso EventBridge (abilitare la funzione)
aws s3api put-bucket-notification-configuration \
  --bucket my-bucket \
  --notification-configuration '{"EventBridgeConfiguration": {}}'
```

---

## S3 Inventory

S3 Inventory fornisce rapporti giornalieri o settimanali di tutti gli oggetti in un bucket (o con un prefisso specifico), con metadati aggiuntivi. È un'alternativa alle List API per analisi su larga scala.

**Formati output:** CSV, ORC, Parquet
**Destinazione:** un altro bucket S3

```bash
# Configurare S3 Inventory
aws s3api put-bucket-inventory-configuration \
  --bucket my-bucket \
  --id "DailyInventory" \
  --inventory-configuration '{
    "Id": "DailyInventory",
    "IsEnabled": true,
    "Destination": {
      "S3BucketDestination": {
        "Bucket": "arn:aws:s3:::my-inventory-bucket",
        "Format": "Parquet",
        "Prefix": "inventory/",
        "Encryption": {
          "SSEKMS": {
            "KeyId": "arn:aws:kms:us-east-1:123456789012:key/mrk-1234"
          }
        }
      }
    },
    "Schedule": {"Frequency": "Daily"},
    "IncludedObjectVersions": "All",
    "OptionalFields": [
      "Size", "LastModifiedDate", "StorageClass",
      "ETag", "ReplicationStatus", "EncryptionStatus",
      "ObjectLockMode", "ObjectLockRetainUntilDate",
      "IntelligentTieringAccessTier"
    ],
    "Filter": {"Prefix": "data/"}
  }'
```

**Use case di S3 Inventory:**
- Identificare oggetti non cifrati per remediation
- Analizzare distribuzione storage class per ottimizzare costi
- Generare report di compliance (quali oggetti hanno Object Lock)
- Input per S3 Batch Operations

---

## S3 Batch Operations

S3 Batch Operations permette di eseguire operazioni su **miliardi di oggetti** con una singola richiesta. Usa S3 Inventory o un file manifest CSV come input.

**Operazioni supportate:**
- Copy (anche con cambio storage class, encryption, metadata)
- Invoke Lambda (custom processing per ogni oggetto)
- Restore from Glacier
- Replicate (replication retroattiva)
- Replace ACL / Tags
- Put Object Lock retention
- Put Object Legal Hold

```bash
# Creare un job di Batch Operations (esempio: ripristinare oggetti Glacier)
aws s3control create-job \
  --account-id 123456789012 \
  --operation '{
    "S3RestoreObject": {
      "ExpirationInDays": 7,
      "GlacierJobParameters": {
        "Tier": "Bulk"
      }
    }
  }' \
  --manifest '{
    "Spec": {
      "Format": "S3BatchOperations_CSV_20180820",
      "Fields": ["Bucket","Key"]
    },
    "Location": {
      "ObjectArn": "arn:aws:s3:::my-manifest-bucket/manifest.csv",
      "ETag": "etag-value"
    }
  }' \
  --report '{
    "Bucket": "arn:aws:s3:::my-report-bucket",
    "Format": "Report_CSV_20180820",
    "Enabled": true,
    "Prefix": "batch-reports/",
    "ReportScope": "AllTasks"
  }' \
  --priority 10 \
  --role-arn arn:aws:iam::123456789012:role/S3BatchRole \
  --description "Restore Glacier objects for audit"

# Monitorare il job
aws s3control describe-job \
  --account-id 123456789012 \
  --job-id "job-12345678-1234-1234-1234-123456789012"
```

---

## S3 Access Points

Gli Access Points sono endpoint con policy separate che semplificano la gestione degli accessi per diversi team o applicazioni che condividono lo stesso bucket.

**Problema che risolvono:** una bucket policy può diventare enorme e difficile da gestire quando molti team accedono allo stesso bucket con permessi diversi.

**Soluzione:** ogni team ha il suo Access Point con una policy dedicata che definisce esattamente quali operazioni può compiere e su quali prefissi.

```bash
# Creare un Access Point per il team analytics
aws s3control create-access-point \
  --account-id 123456789012 \
  --name analytics-access-point \
  --bucket my-shared-bucket \
  --vpc-configuration VpcId=vpc-1234567890abcdef0  # opzionale: limita ad un VPC

# Allegare una policy all'Access Point
cat > ap-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::123456789012:role/AnalyticsRole"
    },
    "Action": ["s3:GetObject", "s3:ListBucket"],
    "Resource": [
      "arn:aws:s3:us-east-1:123456789012:accesspoint/analytics-access-point",
      "arn:aws:s3:us-east-1:123456789012:accesspoint/analytics-access-point/object/analytics/*"
    ]
  }]
}
EOF

aws s3control put-access-point-policy \
  --account-id 123456789012 \
  --name analytics-access-point \
  --policy file://ap-policy.json

# Accedere tramite l'Access Point ARN
aws s3 ls s3://arn:aws:s3:us-east-1:123456789012:accesspoint/analytics-access-point/
```

!!! note "Bucket Policy e Access Points"
    Quando si usano Access Points, la bucket policy del bucket deve delegare il controllo degli accessi agli Access Points. Aggiungere questa statement alla bucket policy:

    ```json
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "*",
      "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"],
      "Condition": {
        "StringEquals": {"s3:DataAccessPointAccount": "123456789012"}
      }
    }
    ```

---

## Performance

S3 scala automaticamente per gestire alti volumi di richieste, ma ci sono pattern da conoscere per ottimizzare le performance in scenari ad alto throughput.

### Limiti di Performance per Prefisso

- **3.500 PUT/COPY/POST/DELETE per secondo per prefisso**
- **5.500 GET/HEAD per secondo per prefisso**

Non c'è limite al numero di prefissi in un bucket. Distribuire gli oggetti su più prefissi aumenta il throughput aggregato linearmente.

```
# Esempio: 20.000 GET/s → usare almeno 4 prefissi
s3://my-bucket/prefix-a/data.json
s3://my-bucket/prefix-b/data.json
s3://my-bucket/prefix-c/data.json
s3://my-bucket/prefix-d/data.json
```

!!! note "Random prefix non più necessario"
    Prima del 2018 era necessario aggiungere hash casuali come prefisso per evitare hot partition. Questo non è più necessario: S3 scala automaticamente per prefisso. I prefissi logici (es. per data, per tipo) sono sufficienti.

### Byte-Range Fetches

Scaricare un oggetto in parti parallele (Parallel GET) aumenta la velocità di download. Ogni parte specifica un intervallo di byte.

```bash
# Scaricare i primi 1024 byte di un oggetto
aws s3api get-object \
  --bucket my-bucket \
  --key large-file.bin \
  --range "bytes=0-1023" \
  part1.bin

# Implementazione Python: download parallelo
import boto3
import concurrent.futures
import os

def download_part(s3_client, bucket, key, start, end, part_num, output_path):
    response = s3_client.get_object(
        Bucket=bucket,
        Key=key,
        Range=f"bytes={start}-{end}"
    )
    with open(f"{output_path}.part{part_num}", 'wb') as f:
        f.write(response['Body'].read())
    return part_num

def parallel_download(bucket, key, output_path, num_threads=10):
    s3 = boto3.client('s3')
    head = s3.head_object(Bucket=bucket, Key=key)
    file_size = head['ContentLength']

    part_size = file_size // num_threads
    futures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i in range(num_threads):
            start = i * part_size
            end = start + part_size - 1 if i < num_threads - 1 else file_size - 1
            futures.append(executor.submit(
                download_part, s3, bucket, key, start, end, i, output_path
            ))

    # Assemblare le parti
    with open(output_path, 'wb') as output_file:
        for i in range(num_threads):
            with open(f"{output_path}.part{i}", 'rb') as part:
                output_file.write(part.read())
            os.remove(f"{output_path}.part{i}")
```

---

## CORS Configuration

Il Cross-Origin Resource Sharing (CORS) è necessario quando il browser di un utente carica risorse S3 da un dominio diverso da quello dell'applicazione web.

**Use case:** un'app web su `https://myapp.com` che carica immagini direttamente da `https://my-bucket.s3.amazonaws.com`.

```bash
# Configurare CORS su un bucket S3
aws s3api put-bucket-cors \
  --bucket my-bucket \
  --cors-configuration '{
    "CORSRules": [
      {
        "AllowedHeaders": ["Authorization", "Content-Type"],
        "AllowedMethods": ["GET", "PUT", "POST"],
        "AllowedOrigins": ["https://myapp.com", "https://www.myapp.com"],
        "ExposeHeaders": ["ETag", "x-amz-server-side-encryption"],
        "MaxAgeSeconds": 3000
      }
    ]
  }'

# Verificare la configurazione CORS
aws s3api get-bucket-cors --bucket my-bucket
```

!!! warning "CORS non è sicurezza"
    CORS è una policy del browser, non una misura di sicurezza server. Un `curl` o qualsiasi client non-browser ignora il CORS. La vera sicurezza è sempre la Bucket Policy e IAM.

---

## Best Practices — Sicurezza

1. **Block Public Access** abilitato su tutti i bucket non pubblici (sia a livello account che bucket)
2. **SSE-KMS con Bucket Key** per tutti i bucket contenenti dati sensibili
3. **Bucket Policy** che forza HTTPS (`aws:SecureTransport: true`)
4. **Object Lock** (COMPLIANCE mode) per dati di audit/compliance
5. **Versioning + MFA Delete** per bucket critici
6. **Access Points** invece di gestire permessi complessi nella bucket policy
7. **S3 Access Analyzer** per identificare bucket con accesso pubblico o cross-account
8. **CloudTrail Data Events** abilitati per audit di accesso agli oggetti

```bash
# Abilitare S3 Access Analyzer
aws accessanalyzer create-analyzer \
  --analyzer-name my-s3-analyzer \
  --type ACCOUNT

# Listare i finding (bucket esposti)
aws accessanalyzer list-findings \
  --analyzer-arn arn:aws:access-analyzer:us-east-1:123456789012:analyzer/my-s3-analyzer
```

---

## Troubleshooting

### "Access Denied" nonostante Policy Corretta

1. Verificare Block Public Access a livello account (può sovrascrivere la bucket policy)
2. Verificare che non ci sia una SCP (Service Control Policy) Organizations che blocca
3. Verificare condizioni nella policy (es. `aws:SourceVpc`)
4. Usare IAM Policy Simulator

### Upload Fallisce con "SignatureDoesNotMatch"

Con SSE-C: verificare che la chiave passata corrisponda a quella usata per il primo upload.

### Event Notifications Non Arrivano

1. Verificare la resource policy della coda SQS/topic SNS/Lambda che permette a S3 di invocarli
2. Verificare i filtri di prefisso/suffix nella configurazione
3. Usare EventBridge invece di notifiche dirette per migliore debugging

---

## Relazioni

??? info "S3 Fondamentali"
    Storage classes, versioning, replication, lifecycle e operazioni base.

    **Approfondimento completo →** [S3 Fondamentali](s3.md)

??? info "KMS — SSE-KMS"
    Dettagli su AWS Key Management Service, Customer Managed Keys, rotazione automatica.

    **Approfondimento completo →** [KMS e Secrets Manager](../security/kms-secrets.md)

??? info "EventBridge — S3 Events"
    Routing avanzato degli eventi S3, filtraggio, replay.

    **Approfondimento completo →** [EventBridge e Kinesis](../messaging/eventbridge-kinesis.md)

---

## Riferimenti

- [S3 Security Best Practices](https://docs.aws.amazon.com/s3/latest/userguide/security-best-practices.html)
- [S3 Object Lock](https://docs.aws.amazon.com/s3/latest/userguide/object-lock.html)
- [S3 Select](https://docs.aws.amazon.com/s3/latest/userguide/selecting-content-from-objects.html)
- [S3 Object Lambda](https://docs.aws.amazon.com/s3/latest/userguide/transforming-objects.html)
- [S3 Event Notifications](https://docs.aws.amazon.com/s3/latest/userguide/EventNotifications.html)
- [S3 Access Points](https://docs.aws.amazon.com/s3/latest/userguide/access-points.html)
- [S3 Batch Operations](https://docs.aws.amazon.com/s3/latest/userguide/batch-ops.html)
- [S3 Server-Side Encryption](https://docs.aws.amazon.com/s3/latest/userguide/serv-side-encryption.html)
- [S3 Performance Guidelines](https://docs.aws.amazon.com/s3/latest/userguide/optimizing-performance.html)
