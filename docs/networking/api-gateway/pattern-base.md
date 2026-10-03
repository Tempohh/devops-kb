---
title: "API Gateway — Pattern e Concetti Base"
slug: pattern-base
category: networking
tags: [api-gateway, pattern, bff, aggregation, routing, versioning, microservizi]
search_keywords: [api gateway pattern, backend for frontend, bff, gateway aggregation, request routing, api versioning, api composition, circuit breaker, bulkhead, strangler fig, api proxy, reverse proxy, edge service, gateway offloading, cross cutting concerns, throttling, ssl termination]
parent: networking/api-gateway/_index
related: [networking/api-gateway/kong, networking/api-gateway/rate-limiting, networking/load-balancing/layer4-vs-layer7, networking/service-mesh/concetti-base]
official_docs: https://microservices.io/patterns/apigateway.html
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# API Gateway — Pattern e Concetti Base

## Panoramica

L'API Gateway è il pattern architetturale che definisce un singolo punto di ingresso per i client di un sistema a microservizi. Risponde a un problema concreto: i client (app mobile, SPA, servizi terzi) devono comunicare con decine di microservizi ognuno con il proprio contratto, versione e localizzazione di rete. Il gateway centralizza la complessità, esponendo un'interfaccia coerente e nascondendo la topologia interna.

Le responsabilità tipiche di un API gateway includono: routing verso i servizi corretti, autenticazione e autorizzazione, rate limiting, trasformazione delle richieste/risposte, aggregazione di più chiamate in una, caching, logging e tracing. Queste funzionalità sono **cross-cutting concerns** che altrimenti andrebbero reimplementati in ogni servizio.

## Concetti Chiave

### Funzionalità Principali

| Funzionalità | Descrizione | Implementazione |
|-------------|-------------|-----------------|
| **Routing** | Instrada verso servizi diversi per path/host | Regole di routing per `/api/users` → user-service |
| **Autenticazione** | Verifica identità del chiamante | JWT validation, OAuth 2.0, API Key |
| **Autorizzazione** | Verifica permessi | Scope JWT, RBAC, OPA |
| **Rate Limiting** | Limita chiamate per client | Token bucket, sliding window |
| **SSL Termination** | Decifratura TLS centralizz. | Gestione certificati al gateway |
| **Request Transform** | Modifica header/body in input | Aggiungere `X-User-Id`, convertire XML→JSON |
| **Response Transform** | Filtra/arricchisce la risposta | Rimuovere campi sensibili, aggiungere metadati |
| **Aggregation** | Combina risposte di più servizi | Una chiamata client = N chiamate backend |
| **Caching** | Cache delle risposte | Riduce carico sui backend |
| **Circuit Breaker** | Blocca chiamate a backend degradati | Evita cascade failure |
| **Logging/Tracing** | Registra ogni richiesta | Audit trail, distributed tracing |

### API Gateway vs Reverse Proxy vs Load Balancer

```
Client
  │
  ▼
API Gateway          ← Routing applicativo, auth, rate limit, aggregation
  │
  ├── /users → LB    ← Load Balancing (distribuzione su istanze)
  │              └── user-service x3
  │
  ├── /orders → LB
  │              └── order-service x2
  │
  └── /products → LB
                 └── product-service x4
```

Un **reverse proxy** (Nginx base) instrada semplicemente le richieste — nessuna logica applicativa.
Un **load balancer** distribuisce il traffico tra istanze dello stesso servizio — nessun routing per path.
Un **API gateway** combina routing applicativo con funzionalità di sicurezza e osservabilità.

## Pattern Principali

### 1. Backend for Frontend (BFF)

Invece di un gateway generico, si crea un gateway dedicato per ogni tipo di client:

```
Mobile App  → Mobile BFF  → Microservizi interni
Web SPA     → Web BFF     → Microservizi interni
Partner API → Partner BFF → Microservizi interni (subset)
```

**Vantaggi:**
- Ogni BFF può ottimizzare per il suo client (mobile riceve payload ridotto)
- Team diversi gestiscono i loro BFF in autonomia
- Breaking changes isolati per tipo di client

**Quando usare:** Quando i requisiti di app mobile e web divergono significativamente, o quando si hanno partnership API con contratti diversi.

### 2. Gateway Aggregation

Un singolo endpoint esposto al client che aggrega internamente chiamate a più servizi:

```
Client: GET /api/dashboard
          │
          ▼
   API Gateway
       │    │    │
       ▼    ▼    ▼
   User  Orders  Notifications
   svc    svc      svc
       │    │    │
       └────┴────┘
          │
          ▼
   { user: {...}, recentOrders: [...], unread: 5 }
```

**Vantaggi:** Riduce i round-trip del client (1 chiamata invece di 3).
**Svantaggi:** Aumenta la latenza totale della risposta al max delle latenze dei servizi aggregati (usare chiamate parallele).

!!! note "L'aggregazione richiede codice"
    I plugin dichiarativi (es. `request-transformer`, `response-transformer` in Kong) modificano una singola richiesta/risposta: **non** fanno fan-out verso più backend. L'aggregazione richiede un handler dedicato (plugin custom, funzione serverless, o un BFF/servizio di composizione, vedi Scenario 3). Alternativa: GraphQL gateway/federation.

```yaml
# Esempio: aggregazione con AWS API Gateway + Lambda (Serverless Framework)
functions:
  aggregateHandler:
    handler: aggregator.handler
    events:
      - http: GET /api/dashboard
```

### 3. API Versioning

Strategie per mantenere backward compatibility:

```
# URL versioning (più comune)
GET /api/v1/users
GET /api/v2/users     ← nuova versione con schema diverso

# Header versioning
GET /api/users
Accept: application/vnd.myapp.v2+json

# Query parameter versioning
GET /api/users?version=2

# Subdomain versioning
GET https://v2.api.example.com/users
```

**Routing nel gateway per versione:**

```nginx
# Nginx — routing per versione API
location ~ ^/api/v1/(.*)$ {
    proxy_pass http://api_v1_backend/$1;
}

location ~ ^/api/v2/(.*)$ {
    proxy_pass http://api_v2_backend/$1;
}
```

### 4. Gateway Offloading

Spostare funzionalità comuni dal servizio al gateway:

```
SENZA gateway offloading:
ogni microservizio implementa:
  ├── JWT validation
  ├── CORS handling
  ├── Rate limiting
  ├── Request ID injection
  └── SSL handling

CON gateway offloading:
gateway implementa:
  ├── JWT validation         ← 1 volta per tutti
  ├── CORS handling          ← 1 volta per tutti
  ├── Rate limiting          ← 1 volta per tutti
  ├── Request ID injection   ← 1 volta per tutti
  └── SSL handling           ← 1 volta per tutti

microservizio implementa solo:
  └── Business logic
```

## Architettura / Come Funziona

### Flusso di una Richiesta

```
1. Client invia: GET /api/v2/users/123
                Authorization: Bearer eyJ...

2. Gateway: TLS termination

3. Gateway: JWT validation
   - Verifica firma
   - Verifica scadenza
   - Estrae claims (user_id, roles)

4. Gateway: Rate limiting check
   - user_id=user-456: 47/50 req/min → OK
   - Se 50/50: risponde 429 Too Many Requests

5. Gateway: Routing
   - path /api/v2/users/* → user-service-v2:8080

6. Gateway: Request transformation
   - Aggiunge header X-User-Id: user-456
   - Aggiunge header X-Request-Id: uuid-123
   - Rimuove Authorization (non serve al backend)

7. Backend: user-service-v2 processa la richiesta

8. Gateway: Response transformation
   - Aggiunge header X-Gateway-Latency: 23ms
   - Rimuove header interni (X-Pod-Name, ecc.)

9. Client riceve risposta arricchita
```

### Circuit Breaker nel Gateway

```
Stato CLOSED (normale):
Richiesta → Gateway → Backend → Risposta

Stato OPEN (backend degradato, troppi errori):
Richiesta → Gateway → Fallback immediato (503 o cache)
                    (nessuna chiamata al backend)

Stato HALF-OPEN (test recovery):
Alcune richieste → Gateway → Backend → se OK: CLOSED
                                      → se KO: OPEN ancora
```

## Configurazione & Pratica

### Nginx come API Gateway Base

```nginx
# /etc/nginx/nginx.conf

# Variabili per routing dinamico
map $uri $backend {
    ~^/api/v1/users    "http://user-service-v1";
    ~^/api/v2/users    "http://user-service-v2";
    ~^/api/orders      "http://order-service";
    ~^/api/products    "http://product-service";
    default            "http://fallback-service";
}

server {
    listen 443 ssl;
    http2 on;                       # nginx >= 1.25.1 (il parametro "listen ... http2" è deprecato)
    server_name api.example.com;

    # Con proxy_pass su variabile ($backend) nginx risolve i nomi a runtime:
    # serve un resolver (es. kube-dns), altrimenti 502 "no resolver defined"
    resolver 10.96.0.10 valid=30s;

    # Rate limiting (definito in http block)
    # limit_req_zone $http_authorization zone=by_token:10m rate=100r/m;

    location /api/ {
        # Rate limiting: 100 req/min per token JWT
        limit_req zone=by_token burst=20 nodelay;
        limit_req_status 429;

        # Auth tramite subrequest
        auth_request /auth/validate;
        auth_request_set $user_id $upstream_http_x_user_id;

        # Propagazione identità al backend
        proxy_set_header X-User-Id     $user_id;
        proxy_set_header X-Request-Id  $request_id;
        proxy_set_header X-Forwarded-For $remote_addr;

        proxy_pass $backend;
        proxy_connect_timeout 5s;
        proxy_read_timeout    30s;
    }

    # Endpoint interno per validazione JWT
    location = /auth/validate {
        internal;
        proxy_pass http://auth-service/validate;
        proxy_set_header Authorization $http_authorization;
    }
}
```

### Traefik come API Gateway in Kubernetes

```yaml
# Middleware: autenticazione JWT
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: jwt-auth
spec:
  forwardAuth:
    address: http://auth-service/validate
    authResponseHeaders:
      - X-User-Id
      - X-User-Roles

---
# Middleware: rate limiting
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: rate-limit
spec:
  rateLimit:
    average: 100
    burst: 50
    period: 1m

---
# IngressRoute con middleware
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: api-route
spec:
  entryPoints:
    - websecure
  routes:
  - match: Host(`api.example.com`) && PathPrefix(`/api/v2/users`)
    kind: Rule
    middlewares:
      - name: jwt-auth
      - name: rate-limit
    services:
      - name: user-service-v2
        port: 8080
  tls:
    certResolver: le-resolver
```

## Best Practices

- **Autenticazione al gateway, autorizzazione al servizio**: il gateway verifica "chi sei" (JWT valid), il servizio verifica "cosa puoi fare" (hai i permessi per questa risorsa)
- **Non mettere business logic nel gateway**: il gateway è infrastruttura, non applicazione
- **Circuit breaker con fallback**: risposta di cache o messaggio di errore chiaro invece di timeout
- **Versioning esplicito**: sempre versionare le API dall'inizio — cambiare schema senza versioning rompe i client
- **Propagare il Request ID**: ogni richiesta deve avere un ID univoco propagato a tutti i servizi — indispensabile per il tracing distribuito
- **Health check dell'API gateway stesso**: il gateway deve essere monitorato come qualsiasi altro componente critico

## Troubleshooting

### Scenario 1 — 401 Unauthorized anche con token valido

**Sintomo:** Il client riceve `401 Unauthorized` nonostante invii un JWT valido verificabile esternamente.

**Causa:** Il gateway non riesce a validare il JWT per uno di questi motivi: clock skew tra gateway e auth service (il token risulta expired), chiave pubblica non aggiornata (key rotation non propagata), oppure il token viene inviato senza prefisso `Bearer `.

**Soluzione:** Verificare l'orario del gateway e dell'auth service, forzare il refresh delle chiavi pubbliche, controllare il formato dell'header.

```bash
# Verificare sincronizzazione orario sul gateway
date && timedatectl status

# Decodificare il JWT e controllare exp/iat
#   (JWT usa base64url senza padding: tr + padding evitano errori di base64 -d)
p=$(echo "eyJ..." | cut -d. -f2 | tr '_-' '/+'); while [ $(( ${#p} % 4 )) -ne 0 ]; do p="$p="; done
echo "$p" | base64 -d | python3 -m json.tool | grep -E 'exp|iat|nbf'

# Controllare i log del gateway per il motivo esatto del rifiuto
# (esempio con ingress-nginx; il progetto è stato ritirato a marzo 2026, vedi nota in Relazioni)
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller | grep -i "401\|unauthorized\|jwt"

# Traefik: verificare configurazione forwardAuth
kubectl describe middleware jwt-auth -n default
```

---

### Scenario 2 — 429 Too Many Requests inatteso

**Sintomo:** Il client riceve `429` molto prima di aver raggiunto il rate limit dichiarato. Il problema si manifesta in modo intermittente o solo in certi orari.

**Causa:** Il rate limit è configurato per IP ma il gateway è dietro un proxy/load balancer che non propaga `X-Forwarded-For`. Tutti i client risultano con lo stesso IP (quello del proxy) e condividono il bucket.

**Soluzione:** Configurare il gateway per leggere l'IP reale dall'header `X-Forwarded-For` o `X-Real-IP`, oppure basare il rate limit sul JWT claim `sub` invece che sull'IP.

```nginx
# Nginx: usare l'IP reale dal header X-Forwarded-For
# In http block:
set_real_ip_from 10.0.0.0/8;       # range del load balancer
real_ip_header   X-Forwarded-For;
real_ip_recursive on;

# Verificare quale IP viene visto dal gateway
# nei log: $remote_addr vs $http_x_forwarded_for
log_format debug_ip '$remote_addr | $http_x_forwarded_for | $http_x_real_ip';
```

```bash
# Kong: ispezionare il plugin rate-limiting e il consumer identificato
curl -s http://localhost:8001/plugins | jq '.data[] | select(.name=="rate-limiting") | .config'

# Verificare quale key viene usata per il rate limit
curl -I https://api.example.com/api/users \
  -H "Authorization: Bearer <token>" \
  | grep -i 'x-ratelimit'
```

---

### Scenario 3 — Latenza elevata sulle chiamate aggregate (Gateway Aggregation)

**Sintomo:** Un endpoint di aggregazione risponde in 3-5 secondi, ma i singoli servizi backend rispondono in ~200ms ciascuno.

**Causa:** Le chiamate ai microservizi vengono eseguite in sequenza invece che in parallelo. La latenza totale è la somma delle latenze invece del massimo.

**Soluzione:** Riscrivere il handler di aggregazione per eseguire le chiamate in parallelo (`Promise.all` in Node.js, `asyncio.gather` in Python, goroutine in Go).

```python
# Python: aggregazione parallela con asyncio
import asyncio
import httpx

async def aggregate_dashboard(user_id: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Esecuzione parallela — latenza = max(latenze) invece di sum(latenze)
        user_task    = client.get(f"http://user-service/users/{user_id}")
        orders_task  = client.get(f"http://order-service/orders?user={user_id}")
        notif_task   = client.get(f"http://notif-service/unread?user={user_id}")

        user_resp, orders_resp, notif_resp = await asyncio.gather(
            user_task, orders_task, notif_task,
            return_exceptions=True  # non fallire se uno fallisce
        )

    return {
        "user":   user_resp.json() if not isinstance(user_resp, Exception) else None,
        "orders": orders_resp.json() if not isinstance(orders_resp, Exception) else None,
        "unread": notif_resp.json().get("count", 0) if not isinstance(notif_resp, Exception) else 0,
    }
```

```bash
# Diagnosticare: misurare latenza di ogni backend separatamente
curl -w "\nTime: %{time_total}s\n" -s http://user-service/users/123 -o /dev/null
curl -w "\nTime: %{time_total}s\n" -s http://order-service/orders?user=123 -o /dev/null

# Se la somma ≈ latenza endpoint aggregato → le chiamate sono sequenziali
```

---

### Scenario 4 — Circuit Breaker aperto in modo persistente (stato OPEN bloccato)

**Sintomo:** Il backend è tornato healthy, ma il gateway continua a rispondere `503 Service Unavailable` e non invia traffico al servizio.

**Causa:** Il target è marcato unhealthy (Kong: health check passivi/attivi sull'upstream; nginx: `max_fails`/`fail_timeout`; Traefik: middleware `circuitBreaker`) e il tempo di recupero non è scaduto (`fallbackDuration`/`recoveryDuration` in Traefik, `fail_timeout` in nginx, `healthy.interval` degli active check in Kong), oppure le richieste di prova continuano a fallire per un motivo diverso dal problema originale (es. timeout troppo basso, health check su path sbagliato).

**Soluzione:** Verificare lo stato del target, correggere il path/timeout dell'health check, o forzare il reset manuale in emergenza.

```bash
# Kong: verificare stato dei target via Admin API
curl -s http://localhost:8001/upstreams/<upstream-name>/health \
  | jq '.data[] | {target, health}'

# Forzare un target a "healthy" manualmente (POST, non PUT)
curl -X POST http://localhost:8001/upstreams/<upstream-name>/targets/<target>/healthy

# Nginx OSS: nessun circuit breaker vero, solo health check passivi
# Controllare i parametri di failure accumulati
nginx -T | grep -E 'max_fails|fail_timeout'

# Traefik: verificare se il middleware CircuitBreaker è configurato
curl -s http://localhost:8080/api/http/middlewares | jq '.[] | select(.type=="circuitbreaker")'
```

## Relazioni

??? info "Kong — API Gateway open source"
    Implementazione pratica con plugin ecosystem.

    **Approfondimento →** [Kong](kong.md)

??? info "Rate Limiting — Throttling delle API"
    Algoritmi e implementazioni di rate limiting.

    **Approfondimento →** [Rate Limiting](rate-limiting.md)

??? info "Service Mesh — Traffic management east-west"
    Il service mesh e l'API gateway si complementano.

    **Approfondimento →** [Concetti Base Service Mesh](../service-mesh/concetti-base.md)

??? info "Kubernetes Gateway API — successore di Ingress"
    Su Kubernetes l'API gateway si esprime oggi con la **Gateway API** (`Gateway`, `HTTPRoute`, GA dalla v1.0), implementata da Envoy Gateway, Kong, Traefik, Istio, NGINX Gateway Fabric. Separa i ruoli (infra: `Gateway`; team applicativi: `HTTPRoute`) e standardizza routing per header/path, traffic split e filtri. Il controller `ingress-nginx` è stato ritirato (marzo 2026): per nuove installazioni preferire Gateway API.

## Riferimenti

- [Microservices.io — API Gateway Pattern](https://microservices.io/patterns/apigateway.html)
- [Microsoft — API Gateway Pattern](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/gateway)
- [NGINX as an API Gateway](https://www.nginx.com/blog/nginx-api-gateway/)
