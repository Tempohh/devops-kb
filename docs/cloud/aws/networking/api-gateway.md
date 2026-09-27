---
title: "API Gateway"
slug: api-gateway
category: cloud
tags: [aws, api-gateway, rest-api, http-api, websocket-api, lambda, throttling, authorizer, vpc-link, cors]
search_keywords: [AWS API Gateway, Amazon API Gateway, REST API, HTTP API, WebSocket API, Lambda proxy integration, Lambda authorizer, IAM authorizer, Cognito authorizer, JWT authorizer, usage plan, API key, throttling, rate limit, burst limit, VPC Link, private API, interface endpoint, resource policy, mapping template, VTL, custom domain name, edge-optimized, regional endpoint, canary deployment, execution log, access log, CORS preflight]
parent: cloud/aws/networking/_index
related: [cloud/aws/compute/lambda, cloud/aws/networking/route53, cloud/aws/security/network-security, cloud/aws/iam/policies-avanzate, networking/api-gateway/pattern-base]
official_docs: https://docs.aws.amazon.com/apigateway/latest/developerguide/
status: complete
difficulty: intermediate
last_updated: 2026-09-27
---

# API Gateway

**Amazon API Gateway** è il servizio managed AWS per creare, pubblicare, proteggere e monitorare API — REST, HTTP e WebSocket. Fa da front-door verso Lambda, servizi AWS (SQS, Step Functions, DynamoDB) o backend HTTP privati/pubblici, gestendo autenticazione, throttling, caching e trasformazione delle richieste senza dover gestire infrastruttura.

!!! note "Perché esiste"
    Senza API Gateway, esporre una funzione Lambda o un microservizio richiederebbe gestire a mano TLS, autenticazione, rate limiting, CORS, logging e versioning. API Gateway centralizza tutto questo come layer managed, scalando automaticamente fino a decine di migliaia di richieste/secondo.

---

## Panoramica

API Gateway supporta tre tipi di API con caratteristiche molto diverse tra loro — la scelta sbagliata del tipo è spesso la causa principale di over-engineering o di feature mancanti scoperte tardi. Si usa quando serve un endpoint pubblico o privato per invocare Lambda, servizi AWS o backend HTTP, con necessità di autenticazione centralizzata, throttling per tenant, o trasformazione del payload. **Non** conviene per comunicazione interna a bassissima latenza tra microservizi nello stesso VPC (meglio ALB/NLB o service mesh) né per streaming di grandi volumi di dati binari continuativi.

Le tre famiglie di API non sono intercambiabili: HTTP API è pensata per il caso comune (proxy verso Lambda o HTTP backend, JWT nativo, costo ridotto), REST API copre i casi enterprise (API keys, usage plans, mapping template VTL, private API via VPC endpoint, request validation), WebSocket API gestisce connessioni bidirezionali persistenti (chat, notifiche real-time, dashboard live).

---

## Concetti Chiave

!!! note "REST API vs HTTP API vs WebSocket API"
    | Feature | REST API | HTTP API | WebSocket API |
    |---|---|---|---|
    | Costo (per milione richieste) | ~$3.50 | ~$1.00 (fino a 70% in meno) | ~$1.00 + $0.25/milione minuti connessione |
    | Latenza | Baseline | ~50-60% più bassa di REST | N/A (connessione persistente) |
    | Lambda proxy integration | Sì | Sì | Sì |
    | HTTP proxy integration | Sì | Sì | No |
    | Mapping template (VTL) | Sì | No (solo trasformazioni semplici) | Sì |
    | Usage plans / API keys | Sì | No | No |
    | Private API (VPC endpoint) | Sì | No | No |
    | JWT authorizer nativo | No (serve Lambda authorizer) | Sì | No |
    | Request validation | Sì (schema JSON) | Limitata | No |
    | Caching risposta | Sì | No | No |
    | WAF integration | Sì | Sì | No |
    | Canary deployment | Sì | Sì | No |

**Regola pratica:** default su HTTP API per nuovi progetti (costo e latenza migliori); passa a REST API solo se servono API keys/usage plans, private API, caching o mapping template VTL avanzati.

**Componenti fondamentali:**

- **Resource** — nodo nell'albero URL dell'API (es. `/users/{id}`)
- **Method** — verbo HTTP su una resource (GET, POST, ecc.), con integration associata
- **Integration** — collegamento tra method e backend (Lambda, HTTP, AWS service, Mock)
- **Stage** — ambiente deployato (es. `dev`, `prod`), con variabili proprie e throttling indipendente
- **Deployment** — snapshot immutabile della configurazione API, associato a uno stage

!!! warning "Timeout hard limit"
    Ogni integration ha un **timeout massimo di 29 secondi**, non configurabile e non aumentabile via support ticket. Backend che superano questo limite (elaborazioni lunghe, batch job) devono passare a pattern asincroni (API Gateway → SQS → worker, con polling o WebSocket per il risultato).

---

## Architettura / Come Funziona

Il flusso di una richiesta REST API: client → **stage** → **method request** (validazione, authorizer) → **integration request** (mapping template opzionale, trasforma richiesta HTTP in formato per il backend) → **backend** (Lambda/HTTP/AWS service) → **integration response** (mapping template opzionale) → **method response** → client.

Con **Lambda proxy integration** (il pattern più comune) API Gateway passa l'intera richiesta HTTP raw a Lambda come evento JSON (`event.body`, `event.headers`, `event.queryStringParameters`) e si aspetta una risposta con `statusCode`, `headers`, `body` — nessun mapping template necessario, la logica di parsing sta nel codice Lambda.

Con **HTTP proxy integration** l'intera richiesta (path, query string, headers, body) viene inoltrata as-is verso un endpoint HTTP/HTTPS esterno o interno (es. ALB privato via VPC Link), senza trasformazioni.

Con **AWS service integration** API Gateway chiama direttamente un'API AWS (es. `SQS:SendMessage`, `StepFunctions:StartExecution`) senza passare da Lambda — utile per pattern "backend diretto" a costo zero di compute, ma richiede un mapping template VTL per tradurre il payload HTTP nel formato atteso dal servizio AWS (solo su REST API).

**Esposizione privata (Private API):** un'API REST può essere resa raggiungibile solo dall'interno di uno o più VPC tramite un **Interface VPC Endpoint** (`execute-api`), combinato con una **resource policy** che nega l'accesso da fuori quel VPC endpoint. Per il verso opposto — un'API pubblica che deve raggiungere un backend privato (ALB/NLB interno) — si usa un **VPC Link**, che apre un canale privato tra API Gateway e il load balancer interno senza esporlo su Internet.

```
Client pubblico
      │
      ▼
API Gateway (pubblica, edge-optimized)
      │  VPC Link
      ▼
NLB interno (VPC privato)
      │
      ▼
ECS/EC2 backend (nessuna IP pubblica)
```

```
Client dentro VPC
      │
      ▼
Interface VPC Endpoint (execute-api)
      │
      ▼
API Gateway (privata, resource policy limita a vpce-xxxx)
      │
      ▼
Lambda
```

---

## Configurazione & Pratica

### Autenticazione/Autorizzazione

```yaml
# Lambda Authorizer (token-based) — REST API, SAM template
UsersApiAuthorizer:
  Type: AWS::ApiGateway::Authorizer
  Properties:
    Name: TokenAuthorizer
    Type: TOKEN
    IdentitySource: method.request.header.Authorization
    AuthorizerUri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${AuthorizerLambda.Arn}/invocations
    AuthorizerResultTtlInSeconds: 300  # cache risultato per 5 min sullo stesso token
    RestApiId: !Ref UsersApi

# JWT Authorizer nativo — HTTP API (nessun Lambda richiesto)
UsersHttpApiAuthorizer:
  Type: AWS::ApiGatewayV2::Authorizer
  Properties:
    ApiId: !Ref UsersHttpApi
    AuthorizerType: JWT
    IdentitySource:
      - "$request.header.Authorization"
    JwtConfiguration:
      Audience: ["my-app-client-id"]
      Issuer: !Sub "https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPoolId}"
```

```python
# Lambda authorizer (REQUEST based) — valuta header/query/context custom
def lambda_handler(event, context):
    token = event["headers"].get("authorization", "")
    principal_id = verify_token(token)  # tua logica di validazione

    if not principal_id:
        raise Exception("Unauthorized")  # 401

    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Allow",
                "Resource": event["methodArn"]
            }]
        },
        "context": {"userId": principal_id}  # passato al backend
    }
```

**Opzioni di autorizzazione disponibili:**

| Metodo | REST API | HTTP API | Uso tipico |
|---|---|---|---|
| **IAM** | Sì | Sì | Chiamate service-to-service con SigV4 |
| **Lambda authorizer (TOKEN)** | Sì | No | Token opaco/JWT custom, logica arbitraria |
| **Lambda authorizer (REQUEST)** | Sì | Sì | Valutazione su header multipli/query/context |
| **Cognito authorizer** | Sì | No (usa JWT authorizer) | User pool Cognito diretto |
| **JWT authorizer nativo** | No | Sì | Cognito o qualsiasi IdP OIDC-compliant |
| **API Key** | Sì (con usage plan) | No | Identificazione client, non autenticazione |

### Throttling e Usage Plans

```bash
# Creare un Usage Plan con throttling e quota per tier "basic"
aws apigateway create-usage-plan \
    --name "basic-tier" \
    --throttle burstLimit=50,rateLimit=20 \
    --quota limit=10000,period=MONTH \
    --api-stages apiId=abc123,stage=prod

# Creare API Key e associarla al piano
KEY_ID=$(aws apigateway create-api-key \
    --name "cliente-acme" \
    --enabled \
    --query 'id' --output text)

aws apigateway create-usage-plan-key \
    --usage-plan-id up-xxxx \
    --key-id $KEY_ID \
    --key-type API_KEY

# Throttling a livello di singolo metodo (override dello stage)
aws apigateway update-stage \
    --rest-api-id abc123 \
    --stage-name prod \
    --patch-operations op=replace,path=/~1users~1GET/throttling/rateLimit,value=10
```

Il throttling è gerarchico: **account** (default 10.000 rps/regione, aumentabile via ticket) → **stage** (default dello stage) → **method** (override per singolo endpoint) → **usage plan/API key** (limite per singolo cliente).

### Esempio SAM minimo — REST API + Lambda + Authorizer

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31

Resources:
  UsersApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Auth:
        DefaultAuthorizer: TokenAuthorizer
        Authorizers:
          TokenAuthorizer:
            FunctionArn: !GetAtt AuthorizerFunction.Arn
            Identity:
              Header: Authorization
      Cors:
        AllowMethods: "'GET,POST,OPTIONS'"
        AllowOrigin: "'https://app.company.com'"
        AllowHeaders: "'Authorization,Content-Type'"
      AccessLogSetting:
        DestinationArn: !GetAtt ApiAccessLogGroup.Arn
        Format: '{"requestId":"$context.requestId","ip":"$context.identity.sourceIp","status":"$context.status","latency":"$context.responseLatency"}'

  GetUsersFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: index.handler
      Runtime: python3.12
      Events:
        GetUsers:
          Type: Api
          Properties:
            RestApiId: !Ref UsersApi
            Path: /users
            Method: GET

  ApiAccessLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: /aws/apigateway/users-api-access
      RetentionInDays: 30
```

### Custom Domain Name e Stage

```bash
# Custom domain regionale (più economico e semplice di edge-optimized)
aws apigateway create-domain-name \
    --domain-name api.company.com \
    --regional-certificate-arn arn:aws:acm:eu-central-1:123456789012:certificate/xxxx \
    --endpoint-configuration types=REGIONAL

# Mappare il dominio custom allo stage prod
aws apigateway create-base-path-mapping \
    --domain-name api.company.com \
    --rest-api-id abc123 \
    --stage prod \
    --base-path "v1"

# Canary deployment: 10% del traffico su nuova versione
aws apigateway create-deployment \
    --rest-api-id abc123 \
    --stage-name prod \
    --canary-settings percentTraffic=10,useStageCache=false
```

**Edge-optimized vs Regional:** edge-optimized instrada il traffico attraverso il CloudFront network AWS (bassa latenza globale, ma serve certificato ACM in `us-east-1`); regional è più economico, più semplice da combinare con CloudFront custom o WAF, e preferibile quando i client sono concentrati in un'unica area geografica.

---

## Best Practices

!!! tip "Cache a livello di stage per backend costosi"
    Su REST API, abilitare il response caching (`CacheClusterEnabled`) su endpoint GET idempotenti con TTL breve (30-300s) riduce drasticamente il carico su Lambda/DB per traffico ripetitivo, senza serverless cache layer esterno.

- Usare **HTTP API** come default, non REST API, salvo necessità specifiche (API keys, VPC endpoint privato, VTL)
- Impostare **throttling a livello di usage plan per tenant**, non solo a livello account, per evitare che un client "rumoroso" saturi la quota di tutti
- Abilitare **execution log** solo in `INFO` o `ERROR` (mai `DEBUG` in produzione: costo CloudWatch e rischio di loggare dati sensibili nel body)
- Validare il payload con **request validation** (JSON Schema) lato API Gateway per respingere richieste malformate prima che raggiungano Lambda (risparmio di invocazioni)
- Per API private, combinare **VPC endpoint + resource policy** — il solo VPC endpoint non basta, senza resource policy l'API resta raggiungibile pubblicamente
- Versionare l'API nel path (`/v1/users`) o via custom domain + base path mapping, mai solo nello stage name (lo stage è per l'ambiente, non per la versione semantica)

!!! warning "CORS non è un'opzione lato client"
    Le richieste OPTIONS preflight devono essere gestite esplicitamente da API Gateway (mock integration o `Cors` block in SAM/CDK) — un errore CORS in produzione quasi sempre significa che il metodo OPTIONS non è configurato o che gli header `Access-Control-Allow-*` mancano nella risposta reale (non solo nel preflight).

---

## Troubleshooting

### Scenario 1 — Errore 403 "Missing Authentication Token"

**Sintomo:** Richiesta a un path esistente restituisce `{"message":"Missing Authentication Token"}` con HTTP 403.

**Causa:** Quasi mai un problema di autenticazione reale — nella maggior parte dei casi il path/method richiesto non esiste nella configurazione dell'API (typo nel path, verbo HTTP sbagliato, deployment non aggiornato allo stage).

**Soluzione:**
```bash
# Verificare le resource/method effettivamente deployate sullo stage
aws apigateway get-resources --rest-api-id abc123
aws apigateway get-deployment --rest-api-id abc123 --deployment-id $(aws apigateway get-stage --rest-api-id abc123 --stage-name prod --query deploymentId --output text)

# Verificare che l'ultimo deployment sia effettivamente associato allo stage prod
aws apigateway get-stage --rest-api-id abc123 --stage-name prod --query 'deploymentId'
```

### Scenario 2 — Errore 403 da resource policy vs IAM vs authorizer (distinguere la causa)

**Sintomo:** HTTP 403 ma il path/method esistono e sono corretti.

**Causa:** Tre sorgenti possibili di 403, con messaggi diversi:
- `{"Message":"User: arn:... is not authorized to perform: execute-api:Invoke"}` → policy IAM del chiamante non concede `execute-api:Invoke`
- `{"message":"Forbidden"}` senza altro dettaglio → **resource policy** dell'API nega l'accesso (es. private API chiamata da fuori il VPC endpoint consentito)
- `{"message":"User is not authorized"}` dal Lambda authorizer → la `policyDocument` restituita ha `Effect: Deny`

**Soluzione:**
```bash
# Ispezionare la resource policy dell'API
aws apigateway get-rest-api --rest-api-id abc123 --query 'policy' --output text | jq .

# Controllare i log del Lambda authorizer (CloudWatch)
aws logs tail /aws/lambda/token-authorizer --since 15m --follow

# Verificare la IAM policy del chiamante (per auth IAM)
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:role/caller-role \
    --action-names execute-api:Invoke \
    --resource-arns "arn:aws:execute-api:eu-central-1:123456789012:abc123/prod/GET/users"
```

### Scenario 3 — CORS preflight fallisce nonostante la configurazione sembri corretta

**Sintomo:** Il browser blocca la richiesta con `No 'Access-Control-Allow-Origin' header is present`, ma la stessa chiamata funziona da `curl`.

**Causa:** La risposta OPTIONS (preflight) è configurata correttamente, ma la **risposta reale** del metodo (GET/POST) — specialmente su Lambda proxy integration — non include gli header CORS: con proxy integration è il codice Lambda a dover restituire esplicitamente `Access-Control-Allow-Origin` in ogni risposta, incluse quelle di errore.

**Soluzione:**
```bash
# Verificare risposta OPTIONS
curl -i -X OPTIONS https://api.company.com/v1/users \
    -H "Origin: https://app.company.com" \
    -H "Access-Control-Request-Method: GET"

# Verificare che la risposta REALE (non solo OPTIONS) includa gli header CORS
curl -i https://api.company.com/v1/users -H "Origin: https://app.company.com"
```
```python
# Nel codice Lambda, includere sempre gli header CORS — anche negli errori
return {
    "statusCode": 200,
    "headers": {
        "Access-Control-Allow-Origin": "https://app.company.com",
        "Access-Control-Allow-Headers": "Authorization,Content-Type"
    },
    "body": json.dumps(result)
}
```

### Scenario 4 — Timeout HTTP 504 a 29 secondi esatti

**Sintomo:** Richieste verso un'elaborazione lunga (report, export, batch) falliscono sistematicamente a ~29s con `{"message":"Endpoint request timed out"}`.

**Causa:** Il timeout massimo di integrazione API Gateway (29s) è raggiunto — non è configurabile, indipendentemente dal timeout impostato su Lambda (che può arrivare a 15 minuti) o sul backend HTTP.

**Soluzione:** Passare a pattern asincrono — API Gateway avvia il lavoro e ritorna subito un job ID, il client fa polling o riceve il risultato via WebSocket/webhook.
```bash
# Pattern: API Gateway -> Lambda (avvia async) -> Step Functions/SQS -> worker
# La Lambda sincrona ritorna immediatamente 202 Accepted con un job id
aws stepfunctions start-execution \
    --state-machine-arn arn:aws:states:eu-central-1:123456789012:stateMachine:LongReport \
    --input '{"reportId": "abc-123"}'
# Il client fa polling su GET /reports/abc-123/status oppure riceve
# il risultato via connessione WebSocket API separata
```

### Scenario 5 — Throttling 429 inatteso con traffico apparentemente basso

**Sintomo:** Errori `429 Too Many Requests` anche se il volume di richieste sembra ben sotto i limiti dello stage.

**Causa:** Il limite più stringente tra account/stage/method/usage-plan è quello che si applica — un override a livello di singolo metodo (spesso dimenticato da una configurazione precedente) può essere molto più basso del limite dello stage.

**Soluzione:**
```bash
# Controllare throttling a livello di stage
aws apigateway get-stage --rest-api-id abc123 --stage-name prod \
    --query '{StageThrottle: methodSettings."*/*"}'

# Controllare override specifici per singolo metodo
aws apigateway get-stage --rest-api-id abc123 --stage-name prod \
    --query 'methodSettings'

# Metriche CloudWatch per identificare quale dimensione throttla
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApiGateway \
    --metric-name ThrottleCount \
    --dimensions Name=ApiName,Value=UsersApi \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 --statistics Sum
```

---

## Relazioni

API Gateway si integra strettamente con altri servizi della KB:

??? info "Lambda — Approfondimento"
    Il backend più comune per API Gateway, tramite Lambda proxy integration. Timeout, cold start e memory sizing di Lambda influenzano direttamente la latenza percepita sull'API.

    **Approfondimento completo →** [Lambda](../compute/lambda.md)

??? info "Route 53 — Approfondimento"
    Custom domain name di API Gateway si abbina a un Alias Record Route 53 per esporre l'API su un dominio proprio invece dell'endpoint `execute-api.amazonaws.com` generato.

    **Approfondimento completo →** [Route 53](route53.md)

??? info "IAM Policies Avanzate — Approfondimento"
    L'autorizzazione IAM su API Gateway (`execute-api:Invoke`) e le resource policy per private API seguono gli stessi principi di least-privilege e condition keys trattati nell'IAM avanzato.

    **Approfondimento completo →** [IAM Policies Avanzate](../iam/policies-avanzate.md)

??? info "Network Security — Approfondimento"
    Private API via VPC Interface Endpoint fa parte della strategia più ampia di esposizione controllata dei servizi AWS descritta nella sicurezza di rete.

    **Approfondimento completo →** [Network Security](../security/network-security.md)

Concettualmente affine (ma non AWS-specifico) al pattern generico di API Gateway trattato in [networking/api-gateway](../../../networking/api-gateway/pattern-base.md), che copre principi validi anche per Kong, Envoy o soluzioni self-hosted.

---

## Riferimenti

- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [REST API vs HTTP API vs WebSocket API](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-protocol-reference.html)
- [Lambda proxy integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html)
- [Controlling access with usage plans and API keys](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)
- [Private APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-private-apis.html)
