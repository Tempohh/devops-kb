---
title: "REST API Design & OpenAPI 3.x"
slug: rest-openapi
category: dev
tags: [rest, openapi, api-design, http, json, swagger, versioning, contract]
search_keywords: [rest api, restful api, openapi, openapi 3, openapi 3.1, swagger, swagger ui, api design, api first, api contract, http methods, status codes, url design, resource design, api versioning, api versionamento, path versioning, header versioning, error response, problem details, rfc 7807, paginazione api, cursor pagination, offset pagination, rate limiting, idempotency key, caching api, etag, cors, content negotiation, api gateway, api mock, prism mock server, redoc, scalar, oasdiff, breaking changes, deprecation header, sunset header, json schema, openapi components, openapi ref, security scheme, bearer token, api key, oauth2 openapi, api specification, api documentation, api testing, contract testing, api linting, spectral, api design patterns, hateoas, hypermedia, link header, api filter, api sorting, api projection, field masking]
parent: dev/api/_index
related: [dev/api/_index, dev/resilienza/_index, dev/sicurezza/tls-da-codice, security/_index]
official_docs: https://spec.openapis.org/oas/v3.1.0
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# REST API Design & OpenAPI 3.x

## Panoramica

REST (Representational State Transfer) è un'architettura per sistemi distribuiti basata su HTTP. Non è un protocollo né uno standard formale: è un insieme di vincoli architetturali che, se rispettati, producono API uniformi, scalabili e manutenibili nel tempo.

**OpenAPI Specification (OAS)** — precedentemente nota come Swagger — è il formato standard de-facto per descrivere, documentare e validare REST API. La versione 3.1 allinea lo schema a JSON Schema 2020-12 e aggiunge il supporto a webhook e `pathItems` riusabili.

Questa guida copre il design operativo di REST API e la scrittura di spec OpenAPI 3.x production-ready: si concentra su convenzioni pratiche, errori comuni, e tooling — il complemento operativo all'overview in [API Design](_index.md).

---

## Concetti Chiave

### I Vincoli REST

I sei vincoli di Fielding definiscono cosa rende un'API "truly RESTful":

| Vincolo | Significato pratico |
|---|---|
| **Stateless** | Ogni richiesta è autocontenuta — il server non mantiene sessione client. Lo stato va nel token (JWT) o nell'URL |
| **Client-Server** | Separazione netta: il client gestisce UI/UX, il server gestisce dati e logica |
| **Cacheable** | Le risposte devono dichiarare se sono cacheable (`Cache-Control`, `ETag`) |
| **Uniform Interface** | URL come sostantivi, metodi HTTP come verbi, rappresentazioni standard (JSON) |
| **Layered System** | Il client non sa se parla direttamente al server o a un proxy/gateway |
| **Code on Demand** | Opzionale — il server può inviare codice eseguibile (es. script JavaScript) |

!!! tip "Stateless è il vincolo più critico"
    Ogni violazione del principio stateless scala male. Cookie di sessione server-side, sticky sessions, o logica che dipende da "cosa ha fatto prima il client" sono red flag. Preferire token JWT autocontenuti.

### Metodi HTTP — Semantica e Proprietà

```
Metodo   Sicuro?  Idempotente?  Corpo?   Uso
───────────────────────────────────────────────────────
GET      ✅        ✅           No       Lettura risorsa/collezione
HEAD     ✅        ✅           No       Come GET ma senza body (verifica esistenza)
OPTIONS  ✅        ✅           No       CORS preflight, capabilities
POST     ❌        ❌           Sì       Creazione risorsa, azioni non idempotenti
PUT      ❌        ✅           Sì       Sostituzione completa risorsa
PATCH    ❌        ❌*          Sì       Modifica parziale risorsa
DELETE   ❌        ✅           No       Eliminazione risorsa

* PATCH può essere reso idempotente con JSON Patch o If-Match
```

!!! warning "PUT vs PATCH"
    `PUT` sostituisce **l'intera risorsa** — i campi non inclusi nel body vengono azzerati. `PATCH` aggiorna solo i campi inclusi. Usare PUT solo per replacement completo; per update parziali usare sempre PATCH.

---

## Architettura / Come Funziona

### URL Design — Gerarchia delle Risorse

```
# Regola: URL = sostantivo plurale + gerarchia logica

✅ Corretto                        ❌ Sbagliato
────────────────────────────────────────────────────────────
GET /v1/orders                     GET /v1/getOrders
POST /v1/orders                    POST /v1/createOrder
GET /v1/orders/{id}                GET /v1/order/{id}
PUT /v1/orders/{id}                POST /v1/orders/update/{id}
DELETE /v1/orders/{id}             DELETE /v1/deleteOrder?id=123
GET /v1/orders/{id}/items          GET /v1/getOrderItems/{id}
POST /v1/orders/{id}/items         POST /v1/addItemToOrder

# Convenzioni di naming
# - kebab-case per URI multi-parola
GET /v1/order-items                # ✅
GET /v1/orderItems                 # ❌ camelCase nell'URL
GET /v1/order_items                # ❌ snake_case nell'URL

# - Non annidare troppo (max 2 livelli di sub-risorsa)
GET /v1/orders/{id}/items          # ✅ — 2 livelli, leggibile
GET /v1/users/{id}/orders/{oid}/items/{iid}/reviews  # ❌ troppo profondo
```

### Filtri, Paginazione e Ordinamento

```bash
# Filtro su singolo campo
GET /v1/orders?status=pending

# Filtro su più valori (multi-value)
GET /v1/orders?status=pending&status=confirmed

# Filtro su range di date
GET /v1/orders?createdAfter=2026-01-01T00:00:00Z&createdBefore=2026-03-31T23:59:59Z

# Paginazione offset-based
GET /v1/orders?page=2&limit=20

# Paginazione cursor-based (raccomandata)
GET /v1/orders?cursor=eyJpZCI6MTIzfQ&limit=20

# Ordinamento — campo:direzione, separato da virgola
GET /v1/orders?sort=createdAt:desc,totalPrice:asc

# Field projection — restituire solo i campi necessari
GET /v1/orders?fields=id,status,createdAt,total

# Ricerca full-text
GET /v1/products?q=laptop&category=electronics
```

### HTTP Status Codes — Riferimento Completo

```
2xx — Successo
  200 OK              GET/PUT/PATCH riuscito, body con la risorsa
  201 Created         POST riuscito; includere Location: /v1/orders/456
  202 Accepted        Operazione asincrona avviata; restituire job ID
  204 No Content      DELETE riuscito, nessun body

3xx — Redirect
  301 Moved Permanently   Risorsa spostata (cambiare URL permanentemente)
  304 Not Modified        Cache hit — ETag/Last-Modified coincidono
  307 Temporary Redirect  Redirect temporaneo, stesso metodo HTTP
  308 Permanent Redirect  Redirect permanente, stesso metodo HTTP

4xx — Errore Client
  400 Bad Request         Payload malformato, parametri mancanti
  401 Unauthorized        Autenticazione mancante o token invalido
  403 Forbidden           Autenticato ma senza permesso per questa risorsa
  404 Not Found           Risorsa non esiste (non usare per "lista vuota")
  405 Method Not Allowed  Metodo HTTP non supportato su questo endpoint
  409 Conflict            Stato inconsistente (ordine già processato, email duplicata)
  410 Gone                Risorsa eliminata definitivamente (es. dopo sunset)
  412 Precondition Failed If-Match ETag non corrisponde (conflict su update)
  415 Unsupported Media   Content-Type non accettato dal server
  422 Unprocessable       Sintassi ok ma validazione semantica fallita
  429 Too Many Requests   Rate limit superato; includere Retry-After header

5xx — Errore Server
  500 Internal Error      Bug non gestito — loggare, non esporre dettagli
  502 Bad Gateway         Errore da upstream (database, microservizio)
  503 Service Unavailable Maintenance mode o overload temporaneo
  504 Gateway Timeout     Timeout atteso da upstream
```

---

## Configurazione & Pratica

### Error Response — RFC 7807 Problem Details

Lo standard RFC 7807 (Problem Details for HTTP APIs) definisce un formato JSON uniforme per gli errori:

```json
{
  "type": "https://api.example.com/errors/validation-failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "Uno o più campi non hanno superato la validazione",
  "instance": "/v1/users/register",
  "errors": [
    {
      "field": "email",
      "code": "INVALID_FORMAT",
      "message": "L'indirizzo email non è in un formato valido"
    },
    {
      "field": "password",
      "code": "TOO_SHORT",
      "message": "La password deve contenere almeno 8 caratteri"
    }
  ],
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

```json
// Esempio errore 404
{
  "type": "https://api.example.com/errors/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Nessun ordine trovato con id '550e8400-e29b-41d4-a716-446655440000'",
  "instance": "/v1/orders/550e8400-e29b-41d4-a716-446655440000",
  "traceId": "7b52009b64fd0a2a49e6d8a939753077"
}
```

!!! warning "Non esporre mai stack trace in produzione"
    I dettagli dell'errore server (stack trace, query SQL, path interni) non devono mai raggiungere il client. Loggarli lato server con il `traceId`, restituire solo il trace ID al client per la correlazione.

### OpenAPI 3.1 — Spec Completa con Componenti

```yaml
# openapi.yaml — struttura production-ready
openapi: "3.1.0"

info:
  title: Order Service API
  version: "1.2.0"
  description: |
    Gestione completa del ciclo di vita degli ordini.
    
    ## Autenticazione
    Tutti gli endpoint richiedono un Bearer JWT tranne `/health`.
    
    ## Rate Limiting
    100 req/min per token autenticato. Header di risposta: `X-RateLimit-*`.
  contact:
    name: Platform Team
    email: platform@example.com
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: https://staging-api.example.com/v1
    description: Staging

# Security globale — override per endpoint specifici
security:
  - BearerAuth: []

tags:
  - name: orders
    description: Operazioni sugli ordini
  - name: health
    description: Health check (no auth)

paths:
  /orders:
    get:
      summary: Lista ordini paginata
      description: Restituisce gli ordini dell'utente autenticato con supporto a filtri e paginazione.
      operationId: listOrders
      tags: [orders]
      parameters:
        - $ref: "#/components/parameters/LimitParam"
        - $ref: "#/components/parameters/CursorParam"
        - name: status
          in: query
          description: Filtra per stato ordine
          schema:
            type: string
            enum: [pending, confirmed, shipped, delivered, cancelled]
        - name: sort
          in: query
          description: "Ordinamento: campo:direzione"
          example: "createdAt:desc"
          schema:
            type: string
      responses:
        "200":
          description: Lista ordini
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/OrderList"
              example:
                data:
                  - id: "550e8400-e29b-41d4-a716-446655440000"
                    status: "pending"
                    total: 99.99
                pagination:
                  cursor: "eyJpZCI6IjU1MGU4NDAwIn0"
                  hasMore: true
        "401":
          $ref: "#/components/responses/Unauthorized"
        "429":
          $ref: "#/components/responses/TooManyRequests"

    post:
      summary: Crea nuovo ordine
      operationId: createOrder
      tags: [orders]
      parameters:
        - name: Idempotency-Key
          in: header
          required: false
          description: UUID per prevenire creazioni duplicate su retry
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateOrderRequest"
      responses:
        "201":
          description: Ordine creato
          headers:
            Location:
              description: URL del nuovo ordine
              schema:
                type: string
                example: "/v1/orders/550e8400-e29b-41d4-a716-446655440000"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Order"
        "400":
          $ref: "#/components/responses/BadRequest"
        "422":
          $ref: "#/components/responses/UnprocessableEntity"

  /orders/{orderId}:
    get:
      summary: Recupera ordine per ID
      operationId: getOrder
      tags: [orders]
      parameters:
        - $ref: "#/components/parameters/OrderIdParam"
      responses:
        "200":
          description: Dettaglio ordine
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Order"
        "404":
          $ref: "#/components/responses/NotFound"

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    ApiKey:
      type: apiKey
      in: header
      name: X-Api-Key

  parameters:
    OrderIdParam:
      name: orderId
      in: path
      required: true
      schema:
        type: string
        format: uuid
    LimitParam:
      name: limit
      in: query
      schema:
        type: integer
        minimum: 1
        maximum: 100
        default: 20
    CursorParam:
      name: cursor
      in: query
      schema:
        type: string

  schemas:
    Order:
      type: object
      required: [id, status, createdAt, total]
      properties:
        id:
          type: string
          format: uuid
          readOnly: true
        status:
          type: string
          enum: [pending, confirmed, shipped, delivered, cancelled]
        total:
          type: number
          format: decimal
          minimum: 0
        createdAt:
          type: string
          format: date-time
          readOnly: true
        items:
          type: array
          items:
            $ref: "#/components/schemas/OrderItem"

    OrderItem:
      type: object
      required: [productId, quantity, price]
      properties:
        productId:
          type: string
          format: uuid
        quantity:
          type: integer
          minimum: 1
        price:
          type: number
          format: decimal

    OrderList:
      type: object
      required: [data, pagination]
      properties:
        data:
          type: array
          items:
            $ref: "#/components/schemas/Order"
        pagination:
          $ref: "#/components/schemas/CursorPagination"

    CursorPagination:
      type: object
      properties:
        cursor:
          type: string
          nullable: true
        hasMore:
          type: boolean
        limit:
          type: integer

    CreateOrderRequest:
      type: object
      required: [items, shippingAddressId]
      properties:
        items:
          type: array
          minItems: 1
          items:
            $ref: "#/components/schemas/OrderItem"
        shippingAddressId:
          type: string
          format: uuid
        notes:
          type: string
          maxLength: 500

    ProblemDetail:
      type: object
      required: [type, title, status]
      properties:
        type:
          type: string
          format: uri
        title:
          type: string
        status:
          type: integer
        detail:
          type: string
        instance:
          type: string
        traceId:
          type: string

  responses:
    BadRequest:
      description: Request malformata o parametri invalidi
      content:
        application/problem+json:
          schema:
            $ref: "#/components/schemas/ProblemDetail"
    Unauthorized:
      description: Token mancante o non valido
      headers:
        WWW-Authenticate:
          schema:
            type: string
            example: 'Bearer realm="api.example.com"'
      content:
        application/problem+json:
          schema:
            $ref: "#/components/schemas/ProblemDetail"
    NotFound:
      description: Risorsa non trovata
      content:
        application/problem+json:
          schema:
            $ref: "#/components/schemas/ProblemDetail"
    UnprocessableEntity:
      description: Validazione semantica fallita
      content:
        application/problem+json:
          schema:
            $ref: "#/components/schemas/ProblemDetail"
    TooManyRequests:
      description: Rate limit superato
      headers:
        Retry-After:
          schema:
            type: integer
          description: Secondi da attendere prima del prossimo tentativo
        X-RateLimit-Limit:
          schema:
            type: integer
        X-RateLimit-Remaining:
          schema:
            type: integer
        X-RateLimit-Reset:
          schema:
            type: integer
          description: Unix timestamp del reset del limite
      content:
        application/problem+json:
          schema:
            $ref: "#/components/schemas/ProblemDetail"
```

### Versioning — Strategie con Deprecation

```bash
# 1. URL Versioning (default raccomandato per API pubbliche)
#    Visibile, cacheable, routing semplice, supportato da tutti i gateway
GET /v1/orders
GET /v2/orders   # nuova versione con breaking changes

# 2. Header Versioning (URL puliti, meno visibile)
GET /orders
Accept: application/vnd.example.v2+json

# 3. Query parameter (deprecazione graduale, non standard)
GET /orders?api-version=2026-01-01
```

```http
# Header di deprecation — da includere nelle risposte v1 dopo il rilascio di v2
HTTP/1.1 200 OK
Content-Type: application/json
Deprecation: true
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
Link: <https://api.example.com/v2/orders>; rel="successor-version"
Link: <https://docs.example.com/migration/v1-to-v2>; rel="deprecation"
```

### Caching con ETag

```http
# Prima richiesta — il server restituisce ETag
GET /v1/orders/123
HTTP/1.1 200 OK
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"
Cache-Control: private, max-age=60

# Richiesta successiva con validazione condizionale
GET /v1/orders/123
If-None-Match: "33a64df551425fcc55e4d42a148795d9f25f89d4"

# Risposta se non modificato (no body, risparmio banda)
HTTP/1.1 304 Not Modified

# Update condizionale con PATCH — prevenire lost update
PATCH /v1/orders/123
If-Match: "33a64df551425fcc55e4d42a148795d9f25f89d4"
Content-Type: application/merge-patch+json

{"status": "confirmed"}

# Se nel frattempo qualcun altro ha modificato la risorsa
HTTP/1.1 412 Precondition Failed
```

---

## Best Practices

### Idempotency Key per POST

```http
# Il client genera un UUID prima della richiesta
POST /v1/orders
Idempotency-Key: 7f3e2a1b-9d4c-4e8f-b6a0-1c2d3e4f5g6h
Content-Type: application/json

{ "items": [...], "shippingAddressId": "abc-123" }

# Prima chiamata: ordine creato
HTTP/1.1 201 Created
Idempotency-Key: 7f3e2a1b-9d4c-4e8f-b6a0-1c2d3e4f5g6h

# Seconda chiamata con stesso Idempotency-Key (dopo timeout/retry)
HTTP/1.1 200 OK   ← stessa risposta della prima, nessun secondo ordine creato
```

!!! tip "Implementazione server-side"
    Storare la coppia `(idempotency_key, user_id) → response` in Redis con TTL 24h. Prima di processare: controllare se esiste. Questo previene double-charge in e-commerce e double-insert in generale.

### CORS per API Pubbliche

```yaml
# Configurazione CORS su API Gateway (AWS, Nginx, ecc.)
# Header necessari nelle risposte

Access-Control-Allow-Origin: https://app.example.com  # non usare * con credenziali
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, Idempotency-Key
Access-Control-Max-Age: 86400      # cache preflight per 24h
Access-Control-Expose-Headers: Location, X-RateLimit-Remaining
```

### Tooling Ecosystem

```bash
# Validazione e linting della spec OpenAPI
npx @stoplight/spectral-cli lint openapi.yaml --ruleset .spectral.yaml

# Mock server da spec (sviluppo parallelo consumer/provider)
npx @stoplight/prism-cli mock openapi.yaml --port 4010
# curl http://localhost:4010/v1/orders → risposta da example o schema faker

# Rilevamento breaking changes tra versioni (usare in CI)
oasdiff breaking openapi-v1.yaml openapi-v2.yaml --fail-on ERR

# Generazione client SDK (40+ linguaggi)
docker run --rm -v $(pwd):/out openapitools/openapi-generator-cli generate \
  -i /out/openapi.yaml \
  -g typescript-fetch \
  -o /out/generated/client

# Generazione server stub (Go, Java Spring, FastAPI...)
docker run --rm -v $(pwd):/out openapitools/openapi-generator-cli generate \
  -i /out/openapi.yaml \
  -g go-server \
  -o /out/generated/server

# Documentazione interattiva locale (Redoc)
npx @redocly/cli preview-docs openapi.yaml
```

### Spectral Ruleset — Linting Personalizzato

```yaml
# .spectral.yaml — regole custom per il team
extends: ["spectral:oas"]

rules:
  # Tutti gli endpoint devono avere operationId
  operation-operationId: error
  
  # Tutti gli endpoint devono avere summary
  operation-summary: error
  
  # Tag obbligatori per raggruppamento
  operation-tags: warn
  
  # Tutti gli errori devono usare ProblemDetail schema
  use-problem-detail-for-errors:
    description: "Errori 4xx/5xx devono usare application/problem+json"
    message: "{{error}}"
    severity: error
    given: "$.paths[*][*].responses[?(@property >= '400')]"
    then:
      field: "content.application/problem+json"
      function: truthy
```

---

## Troubleshooting

### Problema: 401 su endpoint con token valido

**Sintomo:** Il client invia un Bearer JWT corretto ma riceve `401 Unauthorized`.

**Causa:** Il token è valido ma scaduto, o il server valida su un JWKS endpoint diverso da quello che ha firmato il token.

**Soluzione:**
```bash
# Decodificare il JWT (senza verificare firma) per ispezionare claim
echo "eyJhbGc..." | cut -d. -f2 | base64 -d | jq .
# Verificare: exp (scadenza), iss (issuer), aud (audience)

# Testare la validazione del token direttamente
curl -v -H "Authorization: Bearer $TOKEN" https://api.example.com/v1/orders
# Leggere il body del 401 — deve includere WWW-Authenticate con realm
```

---

### Problema: CORS error su preflight OPTIONS

**Sintomo:** Browser riceve errore CORS su richieste `PUT`/`PATCH`/`DELETE` o con header custom.

**Causa:** Il server non gestisce correttamente le richieste preflight `OPTIONS`, oppure mancano header `Access-Control-Allow-Headers` per header custom (es. `Idempotency-Key`).

**Soluzione:**
```bash
# Testare il preflight manualmente
curl -v -X OPTIONS https://api.example.com/v1/orders \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization, Idempotency-Key"

# La risposta deve contenere:
# Access-Control-Allow-Origin: https://app.example.com
# Access-Control-Allow-Methods: ...POST...
# Access-Control-Allow-Headers: ...Authorization, Idempotency-Key...
```

---

### Problema: OpenAPI spec valida ma il mock non genera risposte corrette

**Sintomo:** Prism mock server restituisce `500` o risposte vuote per endpoint definiti nella spec.

**Causa:** Schema mancante o malformato nelle `responses`, oppure mancanza di `example` nei componenti.

**Soluzione:**
```bash
# Validare la spec prima di avviare il mock
npx @stoplight/spectral-cli lint openapi.yaml

# Avviare Prism in modalità verbose per vedere gli errori
npx @stoplight/prism-cli mock openapi.yaml --port 4010 --errors

# Forzare Prism a usare esempi invece di generare dal schema
npx @stoplight/prism-cli mock openapi.yaml --port 4010 -d
```

---

### Problema: Breaking change non rilevata — client si rompe in produzione

**Sintomo:** Una modifica alla spec passa i test ma rompe client esistenti dopo il deploy.

**Causa:** Assenza di `oasdiff` in CI, o spec non committata insieme al codice.

**Soluzione:**
```yaml
# .github/workflows/api-breaking-check.yaml
name: API Breaking Change Check
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Check breaking changes
        run: |
          # Confronta spec corrente con quella su main
          git show origin/main:openapi.yaml > openapi-main.yaml
          npx oasdiff breaking openapi-main.yaml openapi.yaml --fail-on ERR
```

---

### Problema: Rate limiting asimmetrico — alcuni client bloccati, altri no

**Sintomo:** Un client riceve `429` ma altri con traffico simile no.

**Causa:** Il rate limiting è per IP ma il client è dietro NAT (molti utenti condividono un IP), oppure la chiave di throttling non è per token.

**Soluzione:**
```bash
# Verificare gli header di rate limit nella risposta
curl -v https://api.example.com/v1/orders \
  -H "Authorization: Bearer $TOKEN" 2>&1 | grep -i "x-ratelimit"

# Header attesi:
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 0
# X-RateLimit-Reset: 1743799200   ← Unix timestamp
# Retry-After: 42                 ← secondi da attendere
```

---

## Relazioni

??? info "API Design — Overview multi-paradigma (REST, gRPC, AsyncAPI)"
    Questo file è il deep-dive su REST + OpenAPI. Per il confronto con gRPC e AsyncAPI, e per le decisioni architetturali sul paradigma da scegliere → [API Design](_index.md)

??? info "Dev / Resilienza — Retry, circuit breaker e timeout lato client API"
    Ogni chiamata REST può fallire. Circuit breaker, retry con backoff esponenziale e bulkhead devono essere implementati lato client per ogni API call critica. → [Resilienza](../resilienza/_index.md)

??? info "Security — Autenticazione OAuth2, JWT, API Key management"
    Autenticazione Bearer JWT, OAuth2 flows (Authorization Code, Client Credentials), API key rotation, scopes → [Security](../../security/_index.md)

??? info "Dev / Sicurezza — TLS da codice e gestione certificati client"
    Per API con mutual TLS (mTLS) — configurazione certificati client nel codice applicativo → [TLS da codice](../sicurezza/tls-da-codice.md)

---

## Riferimenti

- [OpenAPI Specification 3.1](https://spec.openapis.org/oas/v3.1.0) — Specifica ufficiale OAS 3.1
- [RFC 7807 — Problem Details](https://www.rfc-editor.org/rfc/rfc7807) — Standard error response HTTP
- [RFC 8288 — Web Linking](https://www.rfc-editor.org/rfc/rfc8288) — Standard `Link` header per paginazione e HATEOAS
- [Google API Design Guide](https://cloud.google.com/apis/design) — Best practice da Google per REST API
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines) — Linee guida REST complete con versioning e error handling
- [Stoplight Spectral](https://stoplight.io/open-source/spectral) — OpenAPI linter con regole customizzabili
- [Prism Mock Server](https://stoplight.io/open-source/prism) — Mock server da spec OpenAPI
- [oasdiff](https://github.com/Tufin/oasdiff) — Rilevamento breaking changes OpenAPI da CLI e CI
- [openapi-generator](https://openapi-generator.tech/) — Generazione client/server stub da OpenAPI spec
- [Redocly CLI](https://redocly.com/docs/cli/) — Preview docs, linting, bundling OpenAPI
