---
title: "CloudFront — CDN Global"
slug: cloudfront
category: cloud
tags: [aws, cloudfront, cdn, distribution, caching, lambda-at-edge, cloudfront-functions, waf, origin, geo-restriction, signed-url, signed-cookies, origin-access-control]
search_keywords: [AWS CloudFront, CDN, Content Delivery Network, CloudFront distribution, origin, edge location, cache behavior, TTL, invalidation, Lambda@Edge, CloudFront Functions, WAF, geo restriction, signed URL, signed cookies, OAC, Origin Access Control, custom headers, real-time logs, CloudFront reports, price class, HTTPS, TLS, ACM]
parent: cloud/aws/networking/_index
related: [cloud/aws/storage/s3, cloud/aws/security/network-security, cloud/aws/networking/route53]
official_docs: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# CloudFront — CDN Global

**CloudFront** è il CDN (Content Delivery Network) globale di AWS con centinaia di **Edge Locations** (oltre 600 Point of Presence, numero in costante crescita) in decine di paesi. Riduce la latenza servendo contenuti dalla cache più vicina all'utente.

```
User (Roma)
    ↓
CloudFront Edge Location (Milano)
    ├── Cache Hit → risposta immediata (<5ms)
    └── Cache Miss → Regional Edge Cache (Francoforte)
                         ├── Cache Hit → risposta dalla Regional Cache
                         └── Cache Miss → Origin (S3/ALB/EC2 in eu-central-1)
```

---

## Distributions

Una **Distribution** è la configurazione CloudFront — definisce Origin, comportamenti di cache, e impostazioni di sicurezza.

```bash
# Creare Distribution (esempio: S3 website + ALB API)
aws cloudfront create-distribution \
    --distribution-config '{
        "CallerReference": "my-dist-2026",
        "Comment": "Production Distribution",
        "Enabled": true,
        "DefaultRootObject": "index.html",
        "Origins": {
            "Quantity": 2,
            "Items": [
                {
                    "Id": "S3-static",
                    "DomainName": "my-bucket.s3.eu-central-1.amazonaws.com",
                    "S3OriginConfig": {"OriginAccessIdentity": ""},
                    "OriginAccessControlId": "OAC_ID"
                },
                {
                    "Id": "ALB-api",
                    "DomainName": "myalb.eu-central-1.elb.amazonaws.com",
                    "CustomOriginConfig": {
                        "HTTPSPort": 443,
                        "OriginProtocolPolicy": "https-only",
                        "OriginSSLProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]}
                    }
                }
            ]
        },
        "DefaultCacheBehavior": {
            "TargetOriginId": "S3-static",
            "ViewerProtocolPolicy": "redirect-to-https",
            "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
            "Compress": true,
            "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}
        },
        "CacheBehaviors": {
            "Quantity": 1,
            "Items": [{
                "PathPattern": "/api/*",
                "TargetOriginId": "ALB-api",
                "ViewerProtocolPolicy": "https-only",
                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                "OriginRequestPolicyId": "b689b0a8-53d0-40ab-baf2-68738e2966ac",
                "AllowedMethods": {"Quantity": 7, "Items": ["GET","HEAD","OPTIONS","PUT","POST","PATCH","DELETE"]},
                "Compress": true
            }]
        },
        "PriceClass": "PriceClass_100",
        "ViewerCertificate": {
            "AcmCertificateArn": "arn:aws:acm:us-east-1:...:certificate/xxx",
            "SslSupportMethod": "sni-only",
            "MinimumProtocolVersion": "TLSv1.2_2021"
        },
        "Aliases": {"Quantity": 1, "Items": ["www.company.com"]}
    }'
```

!!! note "Perché `OriginRequestPolicyId` sul behavior `/api/*`"
    Con `CachingDisabled` la cache key è vuota e, senza una Origin Request Policy, CloudFront **non inoltra** cookie, query string né header (es. `Authorization`) all'origin. `AllViewerExceptHostHeader` inoltra tutto il resto senza sovrascrivere l'`Host` dell'origin. `S3OriginConfig` con `OriginAccessIdentity` vuoto è la forma richiesta per usare OAC su un origin S3.

!!! warning "ACM Certificate per CloudFront"
    Il certificato ACM per CloudFront **deve essere creato nella Region us-east-1** (CloudFront è un servizio globale che legge i certificati da us-east-1).

---

## Cache Behaviors

I **Cache Behaviors** definiscono come CloudFront gestisce richieste per pattern di path diversi.

```
Distribution
├── Default (*) → S3 Origin (static)
├── /api/* → ALB Origin (no cache, forward headers)
├── /images/* → S3 Origin (lunga TTL cache)
└── /auth/* → ALB Origin (no cache, forward cookies/auth)
```

**Cache Policies** (managed da AWS — preferire queste):

| Policy | ID | TTL default | Uso |
|--------|----|-------------|-----|
| `CachingOptimized` | 658327ea... | 24h | Contenuti statici |
| `CachingDisabled` | 4135ea2d... | 0 | API dinamiche |
| `CachingOptimizedForUncompressed` | b2884449... | 24h | File non comprimibili |
| `Elemental-MediaPackage` | 08627262... | Variabile | Origin AWS Elemental MediaPackage (streaming) |

**Origin Request Policies** (cosa passare all'origin):

| Policy | ID | Comportamento |
|--------|------|---------------|
| `AllViewer` | 216adef6... | Passa tutto (headers, cookies, query) |
| `AllViewerExceptHostHeader` | b689b0a8... | Tutti tranne Host |
| `CORS-S3Origin` | 88a5eaf4... | CORS (Cross-Origin Resource Sharing) headers per S3 |

---

## Origin Access Control (OAC)

**OAC** permette a CloudFront di accedere a un S3 bucket privato senza URL pubblici. Sostituisce il vecchio **OAI** (Origin Access Identity, legacy): OAC firma le richieste con SigV4 (meccanismo), quindi supporta SSE-KMS, tutte le Region e i metodi `PUT`/`DELETE`, e usa il service principal `cloudfront.amazonaws.com` con condizione sull'ARN della distribution (più restrittivo di un utente OAI condiviso).

```bash
# 1. Creare OAC
OAC_ID=$(aws cloudfront create-origin-access-control \
    --origin-access-control-config '{
        "Name": "S3-OAC",
        "OriginAccessControlOriginType": "s3",
        "SigningBehavior": "always",
        "SigningProtocol": "sigv4"
    }' \
    --query 'OriginAccessControl.Id' \
    --output text)

# 2. Bucket privato (Block Public Access)
aws s3api put-public-access-block \
    --bucket my-static-bucket \
    --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,\
        BlockPublicPolicy=true,RestrictPublicBuckets=true

# 3. Bucket Policy: consente solo CloudFront Distribution
aws s3api put-bucket-policy \
    --bucket my-static-bucket \
    --policy '{
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::my-static-bucket/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE"
                }
            }
        }]
    }'
```

---

## Caching — TTL e Invalidation

```bash
# TTL configurabili nel Cache Policy:
# - Minimum TTL: 1 secondo per CachingOptimized (0 per CachingDisabled)
# - Default TTL: 86400 (24h) per CachingOptimized
# - Maximum TTL: 31536000 (1 anno)

# Origin può controllare TTL via headers:
# Cache-Control: max-age=3600
# Cache-Control: no-cache (TTL = minimum)
# Cache-Control: s-maxage=3600 (override specifico per CloudFront)

# Invalidare cache (dopo deploy nuova versione)
aws cloudfront create-invalidation \
    --distribution-id EDFDVBD6EXAMPLE \
    --paths "/*"                  # invalida tutto (conta come 1 path)

# Invalidazione selettiva (evita di svuotare cache che non è cambiata → meno cache miss/origin load)
aws cloudfront create-invalidation \
    --distribution-id EDFDVBD6EXAMPLE \
    --paths "/index.html" "/app.*.js" "/style.*.css"

# Costo: primi 1000 path/mese gratis → $0.005/path dopo
# (un wildcard come /* conta come un solo path; il costo reale di /* è il re-popolamento della cache)
```

**Best practice per evitare invalidazioni:**
Usare **content hashing nel filename** (es. `app.abc123.js`) — quando il contenuto cambia, il filename cambia → cache miss naturale. Solo `index.html` necessita invalidazione.

---

## Price Classes

| Price Class | Edge Locations | Costo |
|-------------|---------------|-------|
| `PriceClass_All` | Tutte (incluso Sud America, Australia, India) | Massimo |
| `PriceClass_200` | Nord America, Europa, Asia, Medio Oriente, Africa (esclusi Sud America, Australia/Nuova Zelanda) | Medio |
| `PriceClass_100` | Solo Nord America + Europa | Minimo |

Una price class più bassa non esclude gli utenti dei Paesi non coperti: vengono serviti dall'edge incluso più vicino, con latenza maggiore.

```bash
# Modificare price class su distribuzione esistente
aws cloudfront update-distribution \
    --id EDFDVBD6EXAMPLE \
    --distribution-config '{"PriceClass": "PriceClass_100", ...}'
```

---

## Lambda@Edge e CloudFront Functions

Permette di eseguire codice all'Edge, modificando request/response.

### CloudFront Functions (preferite per operazioni semplici)

Girano direttamente sugli edge (non sui Regional Edge Cache), da cui latenza sub-ms e costo ~6× inferiore. Per leggere dati di configurazione (es. mappe di redirect) senza ridistribuire la funzione esiste il **CloudFront KeyValueStore**. Gli esempi sotto usano template literal: richiedono il runtime `cloudfront-js-2.0`.

```javascript
// Esempio: redirect www → non-www
function handler(event) {
    const request = event.request;
    const host = request.headers.host.value;

    if (host.startsWith('www.')) {
        return {
            statusCode: 301,
            statusDescription: 'Moved Permanently',
            headers: {
                'location': { value: `https://${host.slice(4)}${request.uri}` }
            }
        };
    }
    return request;
}
```

```javascript
// Rewrite URL: /user/123 → /user?id=123
function handler(event) {
    const request = event.request;
    const uri = request.uri;

    const match = uri.match(/^\/user\/(\d+)$/);
    if (match) {
        request.uri = '/user';
        request.querystring = { id: { value: match[1] } };
    }
    return request;
}
```

**CloudFront Functions vs Lambda@Edge:**

| Caratteristica | CloudFront Functions | Lambda@Edge |
|---------------|---------------------|-------------|
| Trigger | Viewer Request/Response | Viewer + Origin Request/Response |
| Runtime | JavaScript (`cloudfront-js-2.0`; il 1.0 è solo ES5.1) | Node.js, Python |
| Timeout | < 1ms (sub-millisecondo) | 5s (viewer) / 30s (origin) |
| Memoria | 2MB | 128MB (viewer) / fino a 10GB (origin) |
| Accesso a rete | No | Sì |
| Costo | $0.0000001/invocazione | $0.0000006/invocazione |
| Use case | Header manipulation, URL rewrite, auth semplice | Auth JWT, A/B test, ISR (Incremental Static Regeneration) |

### Lambda@Edge

La funzione va creata in **us-east-1** e CloudFront la replica agli edge; i log CloudWatch finiscono nella Region più vicina all'edge che ha eseguito la funzione.

!!! tip "Security headers: preferire le Response Headers Policies"
    Per i soli header statici (HSTS, `X-Content-Type-Options`, CSP, CORS) usare una **Response Headers Policy** (managed, es. `SecurityHeadersPolicy`) associata al behavior: nessun codice, nessun costo per invocazione. L'esempio sotto serve solo se gli header devono essere calcolati dinamicamente.

```python
# Aggiungere Security Headers (Lambda@Edge - Origin Response)
def handler(event, context):
    response = event['Records'][0]['cf']['response']
    headers = response['headers']

    headers['strict-transport-security'] = [{
        'key': 'Strict-Transport-Security',
        'value': 'max-age=63072000; includeSubdomains; preload'
    }]
    headers['x-content-type-options'] = [{
        'key': 'X-Content-Type-Options',
        'value': 'nosniff'
    }]
    headers['x-frame-options'] = [{
        'key': 'X-Frame-Options',
        'value': 'DENY'
    }]
    headers['content-security-policy'] = [{
        'key': 'Content-Security-Policy',
        'value': "default-src 'self'; script-src 'self' 'unsafe-inline'"
    }]

    return response
```

---

## Geo Restriction

```bash
# Bloccare paesi specifici (whitelist o blacklist)
aws cloudfront update-distribution \
    --id EDFDVBD6EXAMPLE \
    --distribution-config '{
        "Restrictions": {
            "GeoRestriction": {
                "RestrictionType": "blacklist",
                "Quantity": 2,
                "Items": ["CN", "RU"]
            }
        },
        ...
    }'
# oppure "whitelist" con paesi consentiti
```

---

## Signed URLs e Signed Cookies

Per proteggere contenuti premium o privati. Il behavior deve avere **Restrict viewer access** attivo con un **Key Group** (trusted key group) che contiene la chiave pubblica; il `key_id` è l'ID della *public key* registrata in CloudFront (non una key pair dell'account root, metodo legacy). Per proteggere molti file usare **Signed Cookies** invece di un URL per file.

```python
# Generare Signed URL (Python)
import boto3
from botocore.signers import CloudFrontSigner
from datetime import datetime, timezone, timedelta
import rsa

def create_signed_url(url, key_id, private_key_pem, expiry_minutes=60):
    expire_date = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

    def rsa_signer(message):
        private_key = rsa.PrivateKey.load_pkcs1(private_key_pem)
        return rsa.sign(message, private_key, 'SHA-1')

    signer = CloudFrontSigner(key_id, rsa_signer)
    signed_url = signer.generate_presigned_url(
        url,
        date_less_than=expire_date
    )
    return signed_url

# Uso
url = create_signed_url(
    'https://cdn.company.com/premium/video.mp4',
    key_id='K2JCJMDEHXQW5F', # ID della public key nel Key Group
    private_key_pem=open('private_key.pem', 'rb').read()
)
```

---

## Monitoring

```bash
# CloudFront Logs in S3
# Abilitare nella Distribution → General → Standard logging → S3 bucket

# Real-time Logs (Kinesis Data Streams)
aws cloudfront create-realtime-log-config \
    --end-points '[{
        "StreamType": "Kinesis",
        "KinesisStreamConfig": {
            "RoleARN": "arn:aws:iam::...:role/CloudFrontRealtimeLogs",
            "StreamARN": "arn:aws:kinesis:eu-central-1:...:stream/cf-logs"
        }
    }]' \
    --fields '["timestamp","c-ip","sc-status","cs-uri-stem","time-taken"]' \
    --name "my-realtime-config" \
    --sampling-rate 100

# Metriche CloudWatch (namespace AWS/CloudFront, SEMPRE in us-east-1):
# Requests, BytesDownloaded, BytesUploaded
# 4xxErrorRate, 5xxErrorRate, TotalErrorRate
# CacheHitRate, OriginLatency → richiedono "additional metrics" (a pagamento) sulla distribution
# CacheHitRate → obiettivo: >80% per contenuti statici
```

---

## Troubleshooting

### Scenario 1 — Cache Miss Rate troppo alta (CacheHitRate < 50%)

**Sintomo:** CloudWatch mostra `CacheHitRate` sotto il 50%, latenza elevata, costi origin alti.

**Causa:** Query string, cookies o headers non necessari vengono inoltrati all'origin e differenziano la cache key, frammentando le cache entries.

**Soluzione:** Verificare la Cache Policy associata al Cache Behavior e rimuovere dalla cache key i parametri non necessari.

```bash
# Ispezionare cache behavior e policy associata
aws cloudfront get-distribution --id EDFDVBD6EXAMPLE \
    --query 'Distribution.DistributionConfig.DefaultCacheBehavior'

# Controllare quali parametri sono inclusi nella cache key
aws cloudfront get-cache-policy --id 658327ea-f89d-4fab-a63d-7e88639e58f6

# Verificare CacheHitRate con CloudWatch
aws cloudwatch get-metric-statistics \
    --region us-east-1 \
    --namespace AWS/CloudFront \
    --metric-name CacheHitRate \
    --dimensions Name=DistributionId,Value=EDFDVBD6EXAMPLE Name=Region,Value=Global \
    --start-time 2026-03-27T00:00:00Z \
    --end-time 2026-03-28T00:00:00Z \
    --period 3600 \
    --statistics Average
```

Se `CacheHitRate` non restituisce datapoint, le *additional metrics* non sono attivate sulla distribution.

---

### Scenario 2 — 403 Forbidden su oggetti S3

**Sintomo:** CloudFront restituisce `403 Forbidden` per risorse statiche servite da S3; l'oggetto esiste nel bucket.

**Causa:** La Bucket Policy non include la Distribution corretta come `SourceArn`, oppure l'OAC non è configurato nella distribution, oppure il bucket ha ancora un OAI (Origin Access Identity) deprecato. Attenzione: se la policy non concede anche `s3:ListBucket`, S3 risponde `403` (non `404`) per una chiave **inesistente** — verificare quindi anche il path/key richiesto e il `DefaultRootObject`. Con bucket cifrato SSE-KMS la key policy KMS deve consentire al principal `cloudfront.amazonaws.com`.

**Soluzione:** Verificare che OAC sia configurato correttamente e che la Bucket Policy faccia riferimento all'ARN della distribution.

```bash
# Verificare OAC associato all'origin
aws cloudfront get-distribution --id EDFDVBD6EXAMPLE \
    --query 'Distribution.DistributionConfig.Origins.Items[*].{Id:Id,OAC:OriginAccessControlId}'

# Verificare Bucket Policy su S3
aws s3api get-bucket-policy --bucket my-static-bucket | python -m json.tool

# La condizione deve essere:
# "AWS:SourceArn": "arn:aws:cloudfront::ACCOUNT_ID:distribution/EDFDVBD6EXAMPLE"

# Invalidare cache dopo correzione della policy
aws cloudfront create-invalidation \
    --distribution-id EDFDVBD6EXAMPLE \
    --paths "/*"
```

---

### Scenario 3 — Certificato SSL non trovato / ERR_SSL_PROTOCOL_ERROR

**Sintomo:** Browser restituisce errore SSL quando si accede al dominio custom (`www.company.com`). La distribution ha un Alternate Domain Name configurato.

**Causa:** Il certificato ACM non è stato creato in `us-east-1` (CloudFront richiede certificati solo da quella region), oppure il dominio nel certificato non corrisponde all'alias configurato.

**Soluzione:** Creare o importare il certificato ACM in `us-east-1` e associarlo alla distribution.

```bash
# Verificare che il certificato sia in us-east-1
aws acm list-certificates --region us-east-1 \
    --query 'CertificateSummaryList[*].{Domain:DomainName,Arn:CertificateArn}'

# Controllare lo stato del certificato
aws acm describe-certificate \
    --region us-east-1 \
    --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/xxx \
    --query 'Certificate.Status'
# Deve essere "ISSUED", non "PENDING_VALIDATION"

# Verificare alias e certificato sulla distribution
aws cloudfront get-distribution --id EDFDVBD6EXAMPLE \
    --query 'Distribution.DistributionConfig.{Aliases:Aliases.Items,Cert:ViewerCertificate.AcmCertificateArn}'
```

---

### Scenario 4 — Invalidazione non propagata / contenuto vecchio ancora servito

**Sintomo:** Dopo `create-invalidation`, gli utenti ricevono ancora la versione precedente del file. Il sito mostra contenuto stale anche a distanza di minuti.

**Causa:** L'invalidazione richiede tipicamente da pochi secondi a qualche minuto per propagarsi a tutti gli Edge (stato `InProgress` → `Completed`). Oppure il browser sta cachando localmente il file (Cache-Control lato client), o l'invalidazione ha usato un path errato (case sensitive, mancanza di `/`).

**Soluzione:** Verificare lo stato dell'invalidazione, testare bypassando la cache del browser, e controllare gli header di risposta.

```bash
# Verificare stato invalidazione
aws cloudfront list-invalidations --distribution-id EDFDVBD6EXAMPLE \
    --query 'InvalidationList.Items[0].{Id:Id,Status:Status,CreateTime:CreateTime}'

# Attendere completamento (polling)
aws cloudfront wait invalidation-completed \
    --distribution-id EDFDVBD6EXAMPLE \
    --id INVALIDATION_ID

# Testare response headers con curl (nessuna cache del browser; CloudFront ignora
# il Cache-Control della request, quindi non serve a forzare un miss)
curl -I https://www.company.com/index.html
# Cercare: X-Cache: Miss from cloudfront (appena recuperato dall'origin)
# X-Cache: Hit from cloudfront (servito dalla cache; vedere anche l'header Age)
# X-Cache: RefreshHit from cloudfront (revalidato con l'origin)

# Forzare cache miss aggiungendo query string temporanea
curl -I "https://www.company.com/index.html?v=$(date +%s)"
```

---

## Integrazioni e novità

- **AWS WAF**: si associa una Web ACL alla distribution (scope `CLOUDFRONT`, creata in us-east-1) per filtrare SQLi/XSS, rate limiting e bot control già all'edge, prima che il traffico raggiunga l'origin.
- **VPC Origins**: permettono a CloudFront di raggiungere ALB/NLB/EC2 in subnet **private**, senza esporli su Internet (alternativa al pattern "ALB pubblico + header segreto custom").
- **Origin Shield**: layer di cache centralizzato aggiuntivo davanti all'origin; riduce le richieste duplicate da edge diversi (utile con origin lenti o costosi).
- **Origin Failover (origin group)**: failover automatico su un secondo origin per status code 5xx/4xx configurati.

---

## Riferimenti

- [CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/)
- [CloudFront API Reference](https://docs.aws.amazon.com/cloudfront/latest/APIReference/)
- [Cache Policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html)
- [CloudFront Functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html)
- [Lambda@Edge](https://docs.aws.amazon.com/lambda/latest/dg/lambda-edge.html)
- [OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
