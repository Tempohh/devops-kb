---
title: "API Design"
slug: api
category: dev
tags: [api, rest, grpc, graphql, asyncapi, openapi, versionamento, contratti, microservizi]
search_keywords: [api design, rest api, restful, grpc, graphql, asyncapi, openapi, swagger, api gateway, versionamento api, api versioning, contratti api, api contract, backward compatibility, protobuf, protocol buffers, api first, design first, code first, idl, interface definition language, api schema, json schema, avro, schema registry, http api, web api, service api, endpoint, route, resource, api specification, api documentation, api testing, api mocking, consumer driven contract, pact, contract testing, api security, oauth2, jwt bearer, rate limiting, throttling, api design patterns, hateoas, hypermedia]
parent: dev/_index
related: [dev/linguaggi/_index, dev/resilienza/_index, dev/integrazioni/_index, security/_index, messaging/_index]
official_docs: https://swagger.io/specification/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# API Design

## Panoramica

L'API è il **contratto pubblico** di un microservizio: definisce cosa espone al mondo, come si usa, e cosa può cambiare senza rompere i client esistenti. Un'API ben progettata è stabile, versionabile, auto-documentata e testabile.

Esistono tre paradigmi principali per le API di microservizi:

- **REST over HTTP/JSON** — il default per API pubbliche e comunicazione inter-servizio sincrona. Semplice, universale, tooling maturo.
- **gRPC** — RPC binario su HTTP/2 con schema Protobuf. Ideale per comunicazione interna ad alta frequenza, streaming, e contesti poliglotta.
- **AsyncAPI / Event-Driven** — descrive le API asincrone (Kafka, RabbitMQ, NATS). Il complemento di OpenAPI per il mondo event-driven.

La scelta del paradigma influenza profondamente le decisioni successive: serializzazione, versionamento, testing, e tooling di generazione codice.

---

## Concetti Chiave

### API-First vs Code-First

!!! tip "Raccomandazione: API-First"
    Scrivi la spec prima del codice. Questo ti permette di validare il contratto con i team consumer prima di implementare, usare mock server per sviluppo parallelo, e garantire che la documentazione sia sempre aggiornata.

```
API-First workflow:
  1. Scrivi OpenAPI spec (o .proto per gRPC)
  2. Condividi con team consumer → feedback
  3. Genera mock server (Prism, WireMock)
  4. Sviluppo consumer e provider in parallelo
  5. Genera client/server stub dal contratto
  6. Implementa la business logic

Code-First workflow (evitare):
  1. Implementa il servizio
  2. Aggiungi annotazioni
  3. Genera spec dal codice
  ⚠ La spec riflette l'implementazione, non il contratto ideale
```

### Contratti e Backward Compatibility

Un cambiamento è **backward-compatible** (non-breaking) se i client esistenti continuano a funzionare senza modifiche:

| Tipo di cambiamento | Breaking? | Esempio |
|---|---|---|
| Aggiungere un campo opzionale | No | `"newField": "value"` |
| Rimuovere un campo obbligatorio | **Sì** | Rimuovere `"userId"` |
| Cambiare tipo di un campo | **Sì** | `string` → `int` |
| Aggiungere un nuovo endpoint | No | `GET /v1/orders/stats` |
| Cambiare semantica di un campo | **Sì** | `status: "active"` → `status: 1` |
| Aggiungere un campo obbligatorio in request | **Sì** | Nuovo required param |
| Cambiare HTTP method | **Sì** | `POST` → `PUT` |

!!! warning "Regola d'oro"
    Mai rimuovere o rinominare campi in una versione già rilasciata. Depreca prima, rimuovi nella versione major successiva con adeguato periodo di sunset.

---

## REST API Design

### Principi REST

```
Risorse e URI
─────────────────────────────────────────────
✅ Corretto (sostantivi, gerarchie logiche):
  GET    /orders              → lista ordini
  POST   /orders              → crea ordine
  GET    /orders/{id}         → recupera ordine
  PUT    /orders/{id}         → sostituisce ordine
  PATCH  /orders/{id}         → aggiorna parzialmente
  DELETE /orders/{id}         → elimina ordine
  GET    /orders/{id}/items   → sotto-risorse

❌ Sbagliato (verbi nell'URI):
  POST   /createOrder
  GET    /getOrderById?id=123
  POST   /orders/update
```

### Status Code Semantici

```
2xx — Successo
  200 OK             → GET, PUT, PATCH riuscito
  201 Created        → POST riuscito, body con risorsa creata
  202 Accepted       → Operazione asincrona avviata
  204 No Content     → DELETE riuscito, nessun body

4xx — Errore Client
  400 Bad Request    → Input malformato o invalido
  401 Unauthorized   → Autenticazione mancante/invalida
  403 Forbidden      → Autenticato ma non autorizzato
  404 Not Found      → Risorsa non trovata
  409 Conflict       → Conflitto di stato (es. duplicate)
  422 Unprocessable  → Sintassi ok ma semantica invalida
  429 Too Many Req   → Rate limit superato

5xx — Errore Server
  500 Internal Error → Errore non gestito
  502 Bad Gateway    → Errore upstream
  503 Unavailable    → Servizio temporaneamente non disponibile
  504 Gateway Timeout→ Timeout upstream
```

### Formato degli Errori

Usare un formato consistente per tutti gli errori:

```json
{
  "error": {
    "code": "ORDER_NOT_FOUND",
    "message": "Order with id '123' not found",
    "details": [
      {
        "field": "orderId",
        "reason": "No order exists with the provided identifier"
      }
    ],
    "traceId": "abc123def456",
    "timestamp": "2026-03-28T10:30:00Z"
  }
}
```

!!! tip "Codici di errore applicativi"
    Affianca sempre un `code` stringa leggibile allo status HTTP numerico. Il codice `ORDER_NOT_FOUND` è più utile di `404` per il debugging e per i client che devono gestire casi specifici.

### Paginazione

```json
// Cursor-based (consigliata per dataset grandi e live)
GET /orders?cursor=eyJpZCI6MTIzfQ&limit=20

{
  "data": [...],
  "pagination": {
    "cursor": "eyJpZCI6MTQzfQ",
    "hasMore": true,
    "limit": 20
  }
}

// Offset-based (semplice, ma problemi con dataset live)
GET /orders?page=2&size=20

{
  "data": [...],
  "pagination": {
    "page": 2,
    "size": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

---

## OpenAPI Specification

### Struttura Base

```yaml
# openapi.yaml
openapi: "3.1.0"
info:
  title: Order Service API
  version: "1.0.0"
  description: |
    Gestione ordini per l'e-commerce platform.

    ## Autenticazione
    Tutti gli endpoint richiedono un Bearer token JWT.
  contact:
    email: platform-team@example.com

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: https://staging-api.example.com/v1
    description: Staging

security:
  - BearerAuth: []

paths:
  /orders:
    get:
      summary: Lista ordini
      operationId: listOrders
      tags: [orders]
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [pending, confirmed, shipped, delivered, cancelled]
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
      responses:
        "200":
          description: Lista ordini
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/OrderList"
        "401":
          $ref: "#/components/responses/Unauthorized"

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Order:
      type: object
      required: [id, status, createdAt]
      properties:
        id:
          type: string
          format: uuid
        status:
          type: string
          enum: [pending, confirmed, shipped, delivered, cancelled]
        createdAt:
          type: string
          format: date-time
        items:
          type: array
          items:
            $ref: "#/components/schemas/OrderItem"
```

---

## gRPC API Design

### Struttura Protobuf

```protobuf
// order_service.proto
syntax = "proto3";

package order.v1;
option go_package = "github.com/example/order/v1;orderv1";

import "google/protobuf/timestamp.proto";

// OrderService gestisce il ciclo di vita degli ordini
service OrderService {
  // Unary RPC — tipico CRUD
  rpc GetOrder(GetOrderRequest) returns (GetOrderResponse);
  rpc CreateOrder(CreateOrderRequest) returns (CreateOrderResponse);

  // Server streaming — eventi in tempo reale
  rpc WatchOrderStatus(WatchOrderStatusRequest)
      returns (stream OrderStatusEvent);

  // Client streaming — bulk upload
  rpc BulkImportOrders(stream ImportOrderRequest)
      returns (BulkImportResponse);
}

message GetOrderRequest {
  string order_id = 1;  // field number è permanente — non cambiare mai
}

message GetOrderResponse {
  Order order = 1;
}

message Order {
  string id = 1;
  OrderStatus status = 2;
  google.protobuf.Timestamp created_at = 3;
  repeated OrderItem items = 4;
  // Aggiungere nuovi campi con numeri progressivi — non riutilizzare numeri
}

enum OrderStatus {
  ORDER_STATUS_UNSPECIFIED = 0;  // sempre 0 per il default enum
  ORDER_STATUS_PENDING = 1;
  ORDER_STATUS_CONFIRMED = 2;
  ORDER_STATUS_SHIPPED = 3;
  ORDER_STATUS_DELIVERED = 4;
  ORDER_STATUS_CANCELLED = 5;
}
```

### Confronto REST vs gRPC

| Aspetto | REST/JSON | gRPC/Protobuf |
|---|---|---|
| Serializzazione | JSON (testo) | Protobuf (binario) — ~3-10x più compatto |
| Performance | Buona | Eccellente (HTTP/2 multiplexing) |
| Streaming | Limitato (SSE, WebSocket separato) | Nativo (4 pattern) |
| Tooling browser | Eccellente | Limitato (grpc-web) |
| Contratto | OpenAPI (opt-in) | Protobuf (obbligatorio) |
| Code generation | Parziale | Completo (client + server stub) |
| Debugging | Facile (curl, browser) | Richiede tool (grpcurl, Postman) |
| Ideal per | API pubbliche, B2B | Interno inter-servizio |

---

## Versionamento API

### Strategie di Versionamento

```
1. URL Versioning (raccomandato per REST pubbliche)
   GET /v1/orders
   GET /v2/orders

   Vantaggi: visibile, cacheable, facile routing
   Svantaggi: proliferazione di URI

2. Header Versioning
   GET /orders
   Accept: application/vnd.example.v2+json

   Vantaggi: URI puliti
   Svantaggi: meno visibile, non cacheable via CDN

3. Query Parameter
   GET /orders?version=2

   Svantaggi: non standard, caching problematico

Per gRPC: versioning nel package name
   package order.v1;
   package order.v2;
```

### Sunset e Deprecation

```yaml
# Header di deprecation nelle risposte
Deprecation: true
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
Link: <https://api.example.com/v2/orders>; rel="successor-version"
```

!!! warning "Periodo di sunset minimo"
    Per API interne: minimo 3 mesi. Per API esterne/B2B: minimo 6-12 mesi. Comunicare proattivamente via email/changelog ai consumer registrati.

---

## AsyncAPI per API Asincrone

```yaml
# asyncapi.yaml
asyncapi: "2.6.0"
info:
  title: Order Events API
  version: "1.0.0"

channels:
  order.created:
    description: Emesso quando un nuovo ordine viene creato
    subscribe:
      message:
        $ref: "#/components/messages/OrderCreated"

  order.status.changed:
    description: Emesso quando lo stato di un ordine cambia
    subscribe:
      message:
        $ref: "#/components/messages/OrderStatusChanged"

components:
  messages:
    OrderCreated:
      name: OrderCreated
      payload:
        type: object
        required: [orderId, userId, createdAt]
        properties:
          orderId:
            type: string
            format: uuid
          userId:
            type: string
          createdAt:
            type: string
            format: date-time
```

---

## Best Practices

### Naming e Convenzioni

```
✅ URI plurali per collezioni:  /orders, /users, /products
✅ kebab-case per URI:          /order-items, /shipping-addresses
✅ camelCase per JSON fields:   { "orderId", "createdAt", "totalPrice" }
✅ snake_case per Protobuf:     order_id, created_at, total_price
✅ SCREAMING_SNAKE per enum:    ORDER_STATUS_PENDING
✅ Timestamp in ISO 8601:       "2026-03-28T10:30:00Z"
✅ UUID per ID pubblici:        "550e8400-e29b-41d4-a716-446655440000"
✅ Evitare abbreviazioni:       "description" non "desc", "quantity" non "qty"
```

### Idempotenza

!!! tip "Implementare Idempotency Keys"
    Per operazioni `POST` (creazione) che potrebbero essere ritentate su timeout, accettare un header `Idempotency-Key`. Se la request viene ricevuta una seconda volta con la stessa chiave, restituire la risposta originale cached.

```http
POST /orders
Idempotency-Key: 7f3e2a1b-9d4c-4e8f-b6a0-1c2d3e4f5g6h
Content-Type: application/json

{ "items": [...] }
```

### Filtraggio e Ordinamento

```
GET /orders?status=pending&status=confirmed   # multi-value filter
GET /orders?createdAfter=2026-01-01T00:00:00Z
GET /orders?sort=createdAt:desc,totalPrice:asc
GET /orders?fields=id,status,createdAt        # field projection (GraphQL-like)
```

---

## Troubleshooting

### Problema: Client riceve 422 ma il JSON sembra valido

**Sintomo:** Il client invia una request JSON sintatticamente corretta ma riceve `422 Unprocessable Entity`.

**Causa:** Il server ha validazione semantica (es. data nel passato, quantità negativa, riferimento a risorsa non esistente).

**Soluzione:** Assicurarsi che il body di risposta 422 includa dettagli campo per campo:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "details": [
      { "field": "quantity", "reason": "Must be greater than 0, got: -1" },
      { "field": "shipByDate", "reason": "Cannot be in the past" }
    ]
  }
}
```

---

### Problema: Versione deprecata ancora usata dopo il sunset

**Sintomo:** Il servizio vecchio riceve ancora traffico dopo la data di sunset.

**Causa:** Consumer non monitorano gli header `Deprecation` / `Sunset`.

**Soluzione:**
1. Aggiungere un log di warning lato server per ogni chiamata alla versione deprecata
2. Metriche per versione: `http_requests_total{version="v1"}` — creare alert se > threshold dopo sunset
3. Comunicare con un errore `410 Gone` dopo la data di sunset

---

### Problema: gRPC streaming si blocca silenziosamente

**Sintomo:** Un server stream smette di ricevere messaggi senza errori.

**Causa:** Timeout HTTP/2 keepalive o flow control backpressure.

**Soluzione:**
```go
// Configurare keepalive sul client gRPC
conn, err := grpc.Dial(addr,
    grpc.WithKeepaliveParams(keepalive.ClientParameters{
        Time:                10 * time.Second, // ping ogni 10s
        Timeout:             5 * time.Second,  // attendi 5s per pong
        PermitWithoutStream: true,
    }),
)
```

---

### Problema: Breaking change non rilevato in CI

**Sintomo:** Una modifica all'API passa i test ma rompe client in produzione.

**Causa:** Assenza di contract testing o schema validation in pipeline.

**Soluzione:** Integrare `oasdiff` (REST) o `buf breaking` (gRPC) in CI:
```bash
# Rilevamento breaking changes OpenAPI
oasdiff breaking openapi-v1.yaml openapi-v2.yaml --fail-on ERR

# Rilevamento breaking changes Protobuf
buf breaking --against .git#branch=main
```

---

## Relazioni

??? info "Dev / Resilienza — Retry e timeout sulle chiamate API"
    Ogni chiamata API può fallire. Circuit breaker, retry con backoff esponenziale e timeout devono essere configurati lato client per ogni API call critica. → [Resilienza](../resilienza/_index.md)

??? info "Dev / Integrazioni — API asincrone con Kafka/RabbitMQ"
    Per API event-driven documentate con AsyncAPI, l'implementazione concreta usa Kafka o RabbitMQ. → [Integrazioni](../integrazioni/_index.md)

??? info "Security — Autenticazione API (OAuth2, JWT)"
    Autenticazione con Bearer token JWT, OAuth2 flows, API key management, rate limiting by identity → [Security](../../security/_index.md)

??? info "Messaging — Schema registry e compatibilità eventi"
    Gli eventi AsyncAPI hanno un formato gestito via Confluent Schema Registry o AWS Glue per garantire backward compatibility. → [Messaging](../../messaging/_index.md)

---

## Riferimenti

- [OpenAPI Specification 3.1](https://spec.openapis.org/oas/v3.1.0) — Specifica ufficiale
- [Google API Design Guide](https://cloud.google.com/apis/design) — Best practice da Google
- [Protobuf Style Guide](https://protobuf.dev/programming-guides/style/) — Naming e struttura Protobuf
- [AsyncAPI Specification](https://www.asyncapi.com/docs/reference/specification/v2.6.0) — Standard per API asincrone
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines) — Linee guida REST complete
- [buf.build](https://buf.build/) — Toolchain moderna per Protobuf (linting, breaking detection, BSR)
- [oasdiff](https://github.com/Tufin/oasdiff) — Rilevamento breaking changes OpenAPI
