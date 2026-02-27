---
title: "KMS, Secrets Manager, Parameter Store e ACM"
slug: kms-secrets
category: cloud
tags: [aws, kms, secrets-manager, parameter-store, acm, ssm, encryption, key-management, certificate, rotation, envelope-encryption, cloudhsm]
search_keywords: [kms, key management service, cmk, customer master key, symmetric key, asymmetric key, hmac, aws managed key, customer managed key, key policy, kms grant, envelope encryption, data key, multi region key, bucket key, secrets manager, secret rotation, acm, certificate manager, private ca, ssl, tls, parameter store, secure string, ssm parameter, hierarchy, cloudhsm, fips 140-2, key rotation, cross account secrets]
parent: cloud/aws/security/_index
related: [cloud/aws/security/network-security, cloud/aws/security/compliance-audit, cloud/aws/storage/s3-avanzato, cloud/aws/database/rds-aurora]
official_docs: https://docs.aws.amazon.com/kms/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# KMS, Secrets Manager, Parameter Store e ACM

## Panoramica

Questo documento copre la gestione della crittografia e dei secrets in AWS: AWS KMS per la gestione delle chiavi crittografiche, AWS Secrets Manager per la rotazione automatica delle credenziali, AWS Systems Manager Parameter Store per la configurazione gerarchica, e AWS Certificate Manager per i certificati TLS.

---

## AWS KMS — Key Management Service

### Concetti Fondamentali

AWS KMS è il servizio centralizzato per la gestione delle chiavi crittografiche in AWS. Le chiavi KMS non lasciano mai il servizio in plaintext — tutte le operazioni crittografiche avvengono all'interno di KMS su hardware validato FIPS 140-2 Level 3.

**Tipi di chiave (KMS Key Types):**

| Tipo | Uso | Algoritmi | Note |
|------|-----|----------|------|
| **Symmetric** | Encrypt/Decrypt | AES-256-GCM | Default e più comune |
| **Asymmetric RSA** | Sign/Verify, Encrypt/Decrypt | RSA 2048/3072/4096 | Per PKI, digital signatures |
| **Asymmetric ECC** | Sign/Verify | P-256, P-384, P-521, secp256k1 | Per blockchain, JWT |
| **HMAC** | Generate/Verify MAC | HMAC-SHA256/384/512 | Per token di autenticazione |

### Tipi di KMS Keys

**AWS Owned Keys:**
- Create e gestite da AWS per servizi specifici
- Non visibili nella console KMS
- Gratuiti
- Non controllabili dal cliente

**AWS Managed Keys:**
- Create da AWS per conto del cliente quando un servizio le usa per la prima volta
- Formato nome: `aws/s3`, `aws/rds`, `aws/ebs`, etc.
- Rotazione automatica ogni anno
- Visibili ma non configurabili
- Gratuiti (tranne per le API calls)
- Non eliminabili

**Customer Managed Keys (CMK):**
- Create e gestite interamente dal cliente
- Controllo granulare tramite Key Policy
- Rotazione configurabile (automatica annuale o manuale)
- Audit completo via CloudTrail
- **$1/mese per CMK + $0.03 per 10.000 API calls**
- Eliminabili con periodo di attesa (7-30 giorni)

```bash
# Creare una CMK symmetric
aws kms create-key \
  --description "CMK per cifratura dati applicazione" \
  --key-usage ENCRYPT_DECRYPT \
  --key-spec SYMMETRIC_DEFAULT \
  --tags TagKey=Environment,TagValue=production TagKey=App,TagValue=myapp

# Creare un alias per la chiave
aws kms create-alias \
  --alias-name alias/myapp-encryption \
  --target-key-id arn:aws:kms:us-east-1:123456789012:key/mrk-1234abcd...

# Creare una CMK asimmetrica RSA per firma
aws kms create-key \
  --description "Chiave RSA per firma JWT" \
  --key-usage SIGN_VERIFY \
  --key-spec RSA_2048

# Listare le chiavi
aws kms list-keys
aws kms list-aliases

# Descrivere una chiave
aws kms describe-key --key-id alias/myapp-encryption
```

### Key Policy

La Key Policy è il documento IAM-like che definisce chi può usare e amministrare la chiave. A differenza delle IAM policy, la Key Policy è obbligatoria e deve esplicitamente consentire l'accesso all'account root o ad altri IAM principals.

!!! warning "Key Policy vs IAM Policy"
    Per usare una CMK, un principal deve avere permessi sia nella Key Policy che nella IAM Policy. Le IAM policies da sole non bastano (a meno che la Key Policy non deleghi esplicitamente ad IAM).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Enable IAM User Permissions",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow Key Administrators",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::123456789012:role/KMSAdminRole",
          "arn:aws:iam::123456789012:user/alice"
        ]
      },
      "Action": [
        "kms:Create*", "kms:Describe*", "kms:Enable*", "kms:List*",
        "kms:Put*", "kms:Update*", "kms:Revoke*", "kms:Disable*",
        "kms:Get*", "kms:Delete*", "kms:TagResource", "kms:UntagResource",
        "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Allow Key Usage — Application",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::123456789012:role/AppRole",
          "arn:aws:iam::123456789012:role/LambdaExecutionRole"
        ]
      },
      "Action": [
        "kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*",
        "kms:GenerateDataKey*", "kms:DescribeKey"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Allow Cross-Account Access",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::999888777666:root"
      },
      "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:CallerAccount": "999888777666",
          "kms:ViaService": "s3.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
```

```bash
# Applicare una Key Policy
aws kms put-key-policy \
  --key-id alias/myapp-encryption \
  --policy-name default \
  --policy file://key-policy.json

# Verificare la Key Policy
aws kms get-key-policy \
  --key-id alias/myapp-encryption \
  --policy-name default \
  --query Policy \
  --output text | python3 -m json.tool
```

### KMS Grants

I KMS Grants delegano permessi temporanei su una chiave a un principal, senza modificare la Key Policy. Usato da servizi AWS internamente (es. EBS usa grants per cifrare i volumi).

```bash
# Creare un grant
GRANT_TOKEN=$(aws kms create-grant \
  --key-id alias/myapp-encryption \
  --grantee-principal arn:aws:iam::123456789012:role/TempRole \
  --operations Decrypt GenerateDataKey \
  --query 'GrantToken' \
  --output text)

# Revocare un grant
aws kms revoke-grant \
  --key-id alias/myapp-encryption \
  --grant-id grant-1234567890abcdef

# Listare i grants su una chiave
aws kms list-grants --key-id alias/myapp-encryption
```

### Envelope Encryption

L'Envelope Encryption è il pattern fondamentale di KMS per cifrare dati di grandi dimensioni:

1. KMS genera una **Data Encryption Key (DEK)** in forma plaintext + cifrata
2. Il plaintext DEK viene usato per cifrare i dati
3. Il plaintext DEK viene immediatamente distrutto
4. La DEK cifrata viene archiviata insieme ai dati cifrati
5. Per decifrare: inviare la DEK cifrata a KMS → KMS restituisce il plaintext DEK → si decifrano i dati

```
[KMS]                       [Application]
  │                              │
  │ GenerateDataKey request       │
  │◄─────────────────────────────┤
  │                              │
  │ Returns:                     │
  │ - Plaintext DEK (32 bytes)   │
  │ - Encrypted DEK              │
  ├─────────────────────────────►│
  │                              │
  │                    Use Plaintext DEK to encrypt data
  │                    Discard Plaintext DEK immediately
  │                    Store Encrypted DEK alongside ciphertext
```

```python
import boto3
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

kms = boto3.client('kms')

def encrypt_data(plaintext: bytes, key_id: str) -> dict:
    """Cifra dati usando envelope encryption."""
    # 1. Generare una data key
    response = kms.generate_data_key(
        KeyId=key_id,
        KeySpec='AES_256'
    )
    plaintext_key = response['Plaintext']     # usare e poi distruggere
    encrypted_key = response['CiphertextBlob']  # archiviare

    # 2. Cifrare i dati con la data key (AES-256-GCM)
    aesgcm = AESGCM(plaintext_key)
    nonce = os.urandom(12)  # 96 bits per GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # 3. Pulire la plaintext key dalla memoria
    plaintext_key = b'\x00' * len(plaintext_key)
    del plaintext_key

    return {
        'encrypted_data': base64.b64encode(nonce + ciphertext).decode(),
        'encrypted_key': base64.b64encode(encrypted_key).decode()
    }

def decrypt_data(encrypted_data: str, encrypted_key: str) -> bytes:
    """Decifra dati usando envelope encryption."""
    # 1. Decifrare la data key tramite KMS
    response = kms.decrypt(
        CiphertextBlob=base64.b64decode(encrypted_key)
    )
    plaintext_key = response['Plaintext']

    # 2. Decifrare i dati
    aesgcm = AESGCM(plaintext_key)
    data = base64.b64decode(encrypted_data)
    nonce = data[:12]
    ciphertext = data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    # 3. Pulire la plaintext key
    plaintext_key = b'\x00' * len(plaintext_key)
    del plaintext_key

    return plaintext

# Uso diretto KMS per dati piccoli (max 4 KB)
def encrypt_small(plaintext: str, key_id: str) -> str:
    response = kms.encrypt(
        KeyId=key_id,
        Plaintext=plaintext.encode()
    )
    return base64.b64encode(response['CiphertextBlob']).decode()

def decrypt_small(ciphertext_b64: str) -> str:
    response = kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext_b64)
    )
    return response['Plaintext'].decode()
```

### Multi-Region Keys

Le Multi-Region Keys sono chiavi KMS che possono essere replicate in più Region. Hanno lo stesso materiale di chiave e Key ID, ma sono gestite indipendentemente in ogni Region.

**Use case:** cifrare un segreto in us-east-1, decifrarlo in eu-west-1 (senza re-encrypt cross-Region).

```bash
# Creare una Multi-Region Key primaria
aws kms create-key \
  --multi-region \
  --description "Multi-Region key primaria"

# Replicare in un'altra Region
aws kms replicate-key \
  --key-id arn:aws:kms:us-east-1:123456789012:key/mrk-1234abcd... \
  --replica-region eu-west-1 \
  --region us-east-1
```

### Rotazione Automatica

```bash
# Abilitare rotazione automatica annuale (solo symmetric CMK)
aws kms enable-key-rotation \
  --key-id alias/myapp-encryption

# Verificare stato rotazione
aws kms get-key-rotation-status \
  --key-id alias/myapp-encryption

# Rotazione manuale on-demand (genera nuovo materiale, mantiene vecchio per decrypt)
aws kms rotate-key-on-demand \
  --key-id alias/myapp-encryption
```

!!! note "Rotazione e dati esistenti"
    La rotazione KMS non re-cifra i dati esistenti. Il vecchio materiale di chiave viene mantenuto per decriptare i dati cifrati con quella versione. I nuovi encrypt usano il materiale più recente.

### Pricing KMS

- **Customer Managed Key:** $1.00/mese per chiave
- **AWS Managed Key:** gratuito
- **API Calls:** $0.03 per 10.000 richieste (dopo 20.000 gratuite/mese)
- **Bucket Key:** riduce le API calls KMS fino al 99% per S3

### CloudHSM

CloudHSM è un Hardware Security Module dedicato (non condiviso) in conformità FIPS 140-2 Level 3. A differenza di KMS, l'HSM è esclusivamente del cliente — AWS non ha accesso alle chiavi.

**Quando usare CloudHSM invece di KMS:**
- Requisiti normativi che richiedono FIPS 140-2 Level 3 con hardware dedicato
- Necessità di controllo assoluto (AWS non può mai vedere le chiavi)
- Performance molto elevata di crittografia RSA/ECC

**Costo:** ~$1.45/ora per modulo HSM (significativamente più costoso di KMS).

```bash
# Creare un cluster CloudHSM
aws cloudhsmv2 create-cluster \
  --hsm-type hsm2m.medium \
  --subnet-ids subnet-1234567890
```

---

## AWS Secrets Manager

### Panoramica

Secrets Manager archivia, ruota e gestisce credenziali sensibili (password database, API key, certificati) con rotazione automatica integrata per i principali servizi AWS.

**Differenza da Parameter Store:** Secrets Manager è specificamente progettato per secrets con rotazione automatica. Parameter Store è per configurazione generale + secrets semplici.

### Rotazione Automatica

Secrets Manager include Lambda functions di rotazione predefinite per:
- RDS (MySQL, PostgreSQL, Oracle, SQL Server, MariaDB)
- Amazon Redshift
- Amazon DocumentDB
- Amazon ElastiCache

Per altri secrets, si può configurare una Lambda function custom.

```bash
# Creare un secret per un database RDS
aws secretsmanager create-secret \
  --name "prod/myapp/database" \
  --description "Credenziali database produzione" \
  --secret-string '{
    "username": "admin",
    "password": "MySecurePassword123!",
    "engine": "mysql",
    "host": "my-db.xxxxxxxx.us-east-1.rds.amazonaws.com",
    "port": 3306,
    "dbname": "myapp"
  }' \
  --kms-key-id alias/myapp-encryption \
  --tags Key=Environment,Value=production Key=App,Value=myapp

# Abilitare rotazione automatica (ogni 30 giorni) per RDS
aws secretsmanager rotate-secret \
  --secret-id "prod/myapp/database" \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789012:function:SecretsManagerRDSMySQLRotationSingleUser \
  --rotation-rules AutomaticallyAfterDays=30

# Leggere il valore corrente del secret
aws secretsmanager get-secret-value \
  --secret-id "prod/myapp/database" \
  --query SecretString \
  --output text

# Forzare una rotazione manuale
aws secretsmanager rotate-secret \
  --secret-id "prod/myapp/database"
```

### Versioning dei Secrets

Secrets Manager mantiene multiple versioni di un secret identificate da staging labels:

- `AWSCURRENT`: versione attiva corrente
- `AWSPREVIOUS`: versione precedente (mantenuta per rollback)
- `AWSPENDING`: versione in fase di rotazione (temporanea)

```bash
# Listare le versioni
aws secretsmanager list-secret-version-ids \
  --secret-id "prod/myapp/database"

# Leggere una versione specifica
aws secretsmanager get-secret-value \
  --secret-id "prod/myapp/database" \
  --version-stage AWSPREVIOUS
```

### Accesso Programmatico

```python
import boto3
import json

def get_db_credentials(secret_name: str) -> dict:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Uso (la password viene recuperata ogni volta — Secrets Manager gestisce la cache)
creds = get_db_credentials('prod/myapp/database')
conn = mysql.connect(
    host=creds['host'],
    user=creds['username'],
    password=creds['password'],
    database=creds['dbname']
)
```

**Lambda + Secrets Manager — best practice con caching:**
```python
import boto3
import json
import os

# Cache locale per evitare chiamate API ad ogni invocazione Lambda
_secrets_cache = {}

def get_secret(secret_name: str, force_refresh: bool = False) -> dict:
    if secret_name not in _secrets_cache or force_refresh:
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_name)
        _secrets_cache[secret_name] = json.loads(response['SecretString'])
    return _secrets_cache[secret_name]

# Nota: in produzione usare AWS Secrets Manager Agent o SDK caching
# https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets_cache-java.html
```

### Cross-Account Access

```json
// Resource Policy del secret per permettere accesso cross-account
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::999888777666:role/AppRole"
      },
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "*"
    }
  ]
}
```

```bash
aws secretsmanager put-resource-policy \
  --secret-id "prod/myapp/database" \
  --resource-policy file://secret-policy.json
```

### Pricing Secrets Manager

- **$0.40 per secret per mese** (pro-rated giornalmente)
- **$0.05 per 10.000 API call**
- Replica cross-Region: $0.40/replica/mese aggiuntivi

---

## AWS Systems Manager Parameter Store

### Panoramica

Parameter Store è un'alternativa più economica per archiviare configurazioni e secrets che non richiedono rotazione automatica.

### Tipi di Parametro

| Tipo | Cifratura | Use Case |
|------|----------|---------|
| **String** | No | URL, nomi di risorse, configurazioni non sensitive |
| **StringList** | No | Liste CSV di valori |
| **SecureString** | Sì (KMS) | Password, API keys, certificati |

### Gerarchie di Parametri

I parametri possono essere organizzati in gerarchie path-like:

```
/myapp/
  /prod/
    /db-host
    /db-password
    /api-key
  /staging/
    /db-host
    /db-password
    /api-key
/shared/
  /certificates/
    /ca-cert
```

```bash
# Creare parametri
aws ssm put-parameter \
  --name "/myapp/prod/db-host" \
  --value "my-db.xxxxxxxx.us-east-1.rds.amazonaws.com" \
  --type String \
  --tags Key=Environment,Value=production

aws ssm put-parameter \
  --name "/myapp/prod/db-password" \
  --value "MySecurePassword123!" \
  --type SecureString \
  --key-id alias/myapp-encryption \
  --overwrite  # aggiornare un parametro esistente

# Leggere un parametro
aws ssm get-parameter \
  --name "/myapp/prod/db-password" \
  --with-decryption  # necessario per SecureString

# Leggere una gerarchia di parametri
aws ssm get-parameters-by-path \
  --path "/myapp/prod" \
  --recursive \
  --with-decryption \
  --query 'Parameters[*].{Name:Name,Value:Value}'

# History dei parametri
aws ssm get-parameter-history \
  --name "/myapp/prod/db-password" \
  --with-decryption
```

### Standard vs Advanced Parameters

| | Standard | Advanced |
|--|---------|---------|
| Numero parametri | 10.000 | 100.000 |
| Dimensione max | 4 KB | 8 KB |
| Costo storage | Gratuito | $0.05/10.000 API |
| Parameter policies | No | Sì (scadenza, notifiche) |

```bash
# Creare un parametro Advanced con policy di scadenza
aws ssm put-parameter \
  --name "/myapp/prod/temp-token" \
  --value "TemporaryToken123" \
  --type SecureString \
  --tier Advanced \
  --policies '[
    {
      "Type": "Expiration",
      "Version": "1.0",
      "Attributes": {
        "Timestamp": "2024-06-01T00:00:00.000Z"
      }
    },
    {
      "Type": "ExpirationNotification",
      "Version": "1.0",
      "Attributes": {
        "Before": "30",
        "Unit": "Days"
      }
    }
  ]'
```

```python
import boto3

ssm = boto3.client('ssm', region_name='us-east-1')

# Leggere un singolo parametro
def get_parameter(name: str) -> str:
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

# Leggere tutti i parametri di un'applicazione
def get_app_config(app: str, env: str) -> dict:
    response = ssm.get_parameters_by_path(
        Path=f'/{app}/{env}',
        Recursive=True,
        WithDecryption=True
    )
    return {
        param['Name'].split('/')[-1]: param['Value']
        for param in response['Parameters']
    }

config = get_app_config('myapp', 'prod')
# {'db-host': 'my-db.rds...', 'db-password': '...', 'api-key': '...'}
```

---

## Quando Usare Secrets Manager vs Parameter Store

| Criterio | Secrets Manager | Parameter Store |
|---------|----------------|-----------------|
| **Rotazione automatica** | Sì (built-in per RDS, Redshift, DocumentDB) | No (serve Lambda custom) |
| **Costo** | $0.40/secret/mese | Gratuito (Standard tier) |
| **Tipi di dato** | Solo secrets JSON | String, StringList, SecureString |
| **Gerarchie path** | No (solo naming convention) | Sì (path nativo `/app/env/param`) |
| **Versioning** | Sì (staging labels) | Sì (versioni numeriche) |
| **Cross-account** | Sì (resource policy) | Limitato (richiede condivisione esplicita) |
| **Dimensione max** | 64 KB | 4 KB (Standard) / 8 KB (Advanced) |
| **Integrazione Lambda** | Extension nativa | Extension o SDK |
| **Use case** | Credenziali DB, API keys critiche con rotazione | Config applicativa, parametri non critici |

**Regola pratica:**
- Credenziali database → Secrets Manager (rotazione automatica)
- API keys di terze parti → Secrets Manager (quando la rotazione è importante)
- URL, nomi bucket, configurazioni → Parameter Store (gratuito)
- Feature flags, valori di configurazione → Parameter Store

---

## AWS Certificate Manager (ACM)

### Panoramica

ACM gestisce certificati TLS/SSL per servizi AWS. I certificati pubblici sono **gratuiti** e si rinnovano automaticamente. Eliminano il costo e la complessità di acquistare, rinnovare e implementare certificati SSL manualmente.

**Servizi supportati (dove ACM funziona nativamente):**
- Elastic Load Balancer (ALB, NLB, CLB)
- Amazon CloudFront
- AWS API Gateway
- Amazon Cognito
- AWS App Runner
- Amazon OpenSearch Service

!!! warning "ACM non è installabile su EC2"
    I certificati ACM non possono essere esportati o installati direttamente su EC2 o altri server. Per EC2, usare ACM Private CA + Let's Encrypt, o importare un certificato da CA esterna.

### Validazione

**Validazione DNS (raccomandata):**
- ACM fornisce un record CNAME da aggiungere alla hosted zone DNS
- Rinnovo automatico (il record DNS rimane valido)
- Con Route 53: ACM può aggiungere automaticamente il record

**Validazione Email:**
- Email inviata ai contatti registrati per il dominio
- Meno automatizzabile; non ideale per automazione

```bash
# Richiedere un certificato con validazione DNS
aws acm request-certificate \
  --domain-name "*.myapp.com" \
  --subject-alternative-names "myapp.com" \
  --validation-method DNS \
  --options CertificateTransparencyLoggingPreference=ENABLED \
  --tags Key=Environment,Value=production

# Verificare lo stato
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/abc12345

# Listare certificati
aws acm list-certificates \
  --certificate-statuses ISSUED PENDING_VALIDATION

# Importare un certificato da CA esterna
aws acm import-certificate \
  --certificate fileb://certificate.pem \
  --private-key fileb://private-key.pem \
  --certificate-chain fileb://chain.pem \
  --tags Key=Source,Value=external-ca
```

### ACM Private CA

ACM Private CA permette di creare una PKI interna per emettere certificati privati per risorse interne (microservizi, VPN, intranet).

```bash
# Creare una Private CA
aws acm-pca create-certificate-authority \
  --certificate-authority-configuration '{
    "KeyAlgorithm": "RSA_2048",
    "SigningAlgorithm": "SHA256WITHRSA",
    "Subject": {
      "Country": "IT",
      "Organization": "MyCompany",
      "OrganizationalUnit": "Engineering",
      "State": "Milan",
      "CommonName": "MyCompany Internal CA"
    }
  }' \
  --certificate-authority-type ROOT \
  --tags Key=Name,Value=internal-root-ca

# Emettere un certificato dalla Private CA
aws acm request-certificate \
  --domain-name "internal-service.myapp.internal" \
  --certificate-authority-arn arn:aws:acm-pca:us-east-1:123456789012:certificate-authority/abc123
```

### Rinnovo Automatico

ACM tenta il rinnovo automatico 60 giorni prima della scadenza. Per la validazione DNS (con Route 53), il rinnovo avviene senza intervento umano. Per la validazione DNS su altri provider, il record CNAME deve essere mantenuto.

```bash
# Monitorare stato di rinnovo
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/abc12345 \
  --query 'Certificate.{Status:Status,RenewalStatus:RenewalSummary.RenewalStatus,NotAfter:NotAfter}'

# CloudWatch alarm per certificati in scadenza
aws cloudwatch put-metric-alarm \
  --alarm-name "acm-cert-expiry-30days" \
  --alarm-description "Certificato ACM in scadenza entro 30 giorni" \
  --metric-name DaysToExpiry \
  --namespace AWS/CertificateManager \
  --dimensions Name=CertificateArn,Value=arn:aws:acm:... \
  --statistic Minimum \
  --period 86400 \
  --threshold 30 \
  --comparison-operator LessThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:security-alerts
```

---

## Best Practices

### KMS

1. Usare **Customer Managed Keys** per dati sensibili (audit + controllo granulare)
2. **Abilitare rotazione automatica** (annuale) per tutte le CMK symmetric
3. Seguire il **principio del minimo privilegio** nelle Key Policy
4. Usare **Bucket Key** con S3 SSE-KMS per ridurre costi API calls
5. **CloudTrail** deve loggare le API KMS per audit (abilitare Data Events)
6. Non condividere CMK tra ambienti diversi (prod/staging/dev hanno chiavi separate)

### Secrets Manager

1. **Mai hard-codare** credenziali nel codice o nelle variabili di ambiente Lambda
2. Usare **rotazione automatica** per tutte le credenziali database
3. Configurare **notifiche CloudWatch** per rotazioni fallite
4. Usare **naming convention** consistente: `env/app/secret-name`
5. Abilitare la **replica cross-Region** per secret critici usati in più Region

### Parameter Store

1. Usare **SecureString per tutti i valori sensibili** (anche se considerati "meno critici")
2. Struttura gerarchica: `/environment/application/parameter`
3. Usare **Parameter Store** per configurazioni, **Secrets Manager** per credenziali con rotazione
4. **Taggare** tutti i parametri per facilità di ricerca e billing

---

## Troubleshooting

### "AccessDeniedException" su KMS

1. Verificare la Key Policy — il principal deve essere esplicitamente autorizzato
2. Verificare la IAM Policy del principal
3. Verificare che non ci sia una SCP Organizations che nega l'accesso
4. Per encrypt/decrypt S3: verificare che il bucket sia nella stessa Region della chiave

```bash
# Simulare una policy per debug
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/AppRole \
  --action-names kms:Decrypt \
  --resource-arns arn:aws:kms:us-east-1:123456789012:key/mrk-1234
```

### Rotazione Secrets Manager Fallita

1. Verificare i log della Lambda function di rotazione (CloudWatch Logs)
2. Verificare che il Security Group della Lambda permetta la connessione al database
3. Verificare che la Lambda abbia accesso al secret tramite IAM policy

```bash
# Monitorare eventi di rotazione
aws cloudwatch filter-log-events \
  --log-group-name "/aws/lambda/SecretsManagerRDSMySQLRotation" \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s000)
```

---

## Relazioni

??? info "S3 — SSE-KMS"
    S3 usa KMS per la cifratura server-side degli oggetti. Il Bucket Key riduce i costi KMS.

    **Approfondimento completo →** [S3 Avanzato](../storage/s3-avanzato.md)

??? info "RDS — Encryption e IAM Auth"
    RDS usa KMS per la cifratura at rest. Secrets Manager gestisce automaticamente le password RDS.

    **Approfondimento completo →** [RDS e Aurora](../database/rds-aurora.md)

??? info "Network Security — TLS/ACM"
    I certificati ACM si usano con ALB, CloudFront, API Gateway per TLS in transit.

    **Approfondimento completo →** [Network Security](network-security.md)

---

## Riferimenti

- [AWS KMS Documentation](https://docs.aws.amazon.com/kms/)
- [KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [Parameter Store Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [ACM User Guide](https://docs.aws.amazon.com/acm/latest/userguide/)
- [ACM Private CA](https://docs.aws.amazon.com/privateca/latest/userguide/)
- [CloudHSM User Guide](https://docs.aws.amazon.com/cloudhsm/)
- [KMS Pricing](https://aws.amazon.com/kms/pricing/)
- [Secrets Manager Pricing](https://aws.amazon.com/secrets-manager/pricing/)
