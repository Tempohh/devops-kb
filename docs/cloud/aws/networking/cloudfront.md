---
title: "CloudFront — CDN Global"
slug: cloudfront
category: cloud
tags: [aws, cloudfront, cdn, distribution, caching, lambda-at-edge, cloudfront-functions, waf, origin, geo-restriction, signed-url, signed-cookies, origin-access-control]
search_keywords: [AWS CloudFront, CDN, Content Delivery Network, CloudFront distribution, origin, edge location, cache behavior, TTL, invalidation, Lambda@Edge, CloudFront Functions, WAF, geo restriction, signed URL, signed cookies, OAC, Origin Access Control, custom headers, real-time logs, CloudFront reports, price class, HTTPS, TLS, ACM]
parent: cloud/aws/networking/_index
related: [cloud/aws/storage/s3, cloud/aws/security/network-security, cloud/aws/networking/route53]
official_docs: https://docs.aws.amazon.com/cloudfront/latest/APIReference/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# CloudFront — CDN Global

**CloudFront** è il CDN (Content Delivery Network) globale di AWS con oltre **600 Edge Locations** in 100+ paesi. Riduce la latenza servendo contenuti dalla cache più vicina all'utente.

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
|--------|----|-----------|----|
| `CachingOptimized` | 658327ea... | 24h | Contenuti statici |
| `CachingDisabled` | 4135ea2d... | 0 | API dinamiche |
| `CachingOptimizedForUncompressed` | b2884449... | 24h | File non comprimibili |
| `Elemental-MediaPackage` | 08627262... | Media streaming |

**Origin Request Policies** (cosa passare all'origin):

| Policy | ID | Comportamento |
|--------|------|---------------|
| `AllViewer` | 216adef6... | Passa tutto (headers, cookies, query) |
| `AllViewerExceptHostHeader` | b689b0a8... | Tutti tranne Host |
| `CORS-S3Origin` | 88a5eaf4... | CORS headers per S3 |

---

## Origin Access Control (OAC)

**OAC** permette a CloudFront di accedere a un S3 bucket privato senza URL pubblici.

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
# - Minimum TTL: 0 secondi
# - Default TTL: 86400 (24h) per CachingOptimized
# - Maximum TTL: 31536000 (1 anno)

# Origin può controllare TTL via headers:
# Cache-Control: max-age=3600
# Cache-Control: no-cache (TTL = minimum)
# Cache-Control: s-maxage=3600 (override specifico per CloudFront)

# Invalidare cache (dopo deploy nuova versione)
aws cloudfront create-invalidation \
    --distribution-id EDFDVBD6EXAMPLE \
    --paths "/*"                  # invalida tutto

# Invalidazione selettiva (molto più economica)
aws cloudfront create-invalidation \
    --distribution-id EDFDVBD6EXAMPLE \
    --paths "/index.html" "/app.*.js" "/style.*.css"

# Costo: prime 1000 invalidazioni/mese gratis → $0.005/path dopo
```

**Best practice per evitare invalidazioni:**
Usare **content hashing nel filename** (es. `app.abc123.js`) — quando il contenuto cambia, il filename cambia → cache miss naturale. Solo `index.html` necessita invalidazione.

---

## Price Classes

| Price Class | Edge Locations | Costo |
|-------------|---------------|-------|
| `PriceClass_All` | Tutte (incluso Sud America, Australia, India) | Massimo |
| `PriceClass_200` | Europa, USA, Canada, Asia (senza India/Sud America) | Medio |
| `PriceClass_100` | Solo USA + Europa | Minimo |

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
| Runtime | JavaScript (ES5.1) | Node.js, Python |
| Timeout | 1ms | 5s (viewer) / 30s (origin) |
| Memoria | 2MB | 128MB - 10GB |
| Accesso a rete | No | Sì |
| Costo | $0.0000001/invocazione | $0.0000006/invocazione |
| Use case | Header manipulation, URL rewrite, auth semplice | Auth JWT, A/B test, ISR |

### Lambda@Edge

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

Per proteggere contenuti premium o privati:

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
    key_id='APKA...',        # CloudFront Key Pair ID
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

# Metriche CloudWatch disponibili:
# Requests, BytesDownloaded, BytesUploaded
# 4xxErrorRate, 5xxErrorRate, TotalErrorRate
# CacheHitRate → obiettivo: >80%
```

---

## Riferimenti

- [CloudFront Developer Guide](https://docs.aws.amazon.com/cloudfront/latest/APIReference/)
- [Cache Policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html)
- [CloudFront Functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html)
- [Lambda@Edge](https://docs.aws.amazon.com/lambda/latest/dg/lambda-edge.html)
- [OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
