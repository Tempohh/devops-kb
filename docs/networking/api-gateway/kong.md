---
title: "Kong API Gateway"
slug: kong
category: networking
tags: [kong, api-gateway, nginx, openresty, plugin, kubernetes, ingress]
search_keywords: [kong gateway, kong plugin, kong admin api, kong manager, kong deck, kong ingress controller, kic, rate limiting kong, jwt kong, oauth2 kong, kong enterprise, kong oss, kong helm, db-less mode, declarative config, service entity, route entity, upstream entity, plugin entity]
parent: networking/api-gateway/_index
related: [networking/api-gateway/pattern-base, networking/api-gateway/rate-limiting, networking/kubernetes/ingress]
official_docs: https://docs.konghq.com/
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Kong API Gateway

## Panoramica

Kong è l'API gateway open source più diffuso, costruito su **Nginx/OpenResty** (Nginx + LuaJIT). Offre un'architettura plugin-based che permette di estendere le funzionalità senza modificare il core. Kong si configura tramite una Admin API REST (o dichiarativamente con Kong Deck), persiste la configurazione in PostgreSQL o in modalità DB-less via file YAML, e si integra nativamente con Kubernetes tramite il Kong Ingress Controller (KIC).

Kong è disponibile in versione **open source** (OSS, con ~40 plugin ufficiali) e **Enterprise** (con funzionalità avanzate come Developer Portal, RBAC granulare, Analytics). Per la maggior parte dei casi d'uso, Kong OSS è sufficiente.

## Concetti Chiave

### Entità Principali

```
Service  →  Upstream service (es: http://user-service:8080)
  │
Route    →  Regola di matching (path, host, method)
  │
Plugin   →  Funzionalità applicata su Service, Route o globalmente
  │
Upstream →  Pool di backend con health check e load balancing
  │
Consumer →  Identità del client (per rate limiting, auth per-consumer)
```

### Modalità di Deployment

| Modalità | Storage | Pro | Contro |
|----------|---------|-----|--------|
| **DB Mode** (PostgreSQL) | Database | Admin API completa, UI Manager | Dipende da DB |
| **DB-less** | File YAML/JSON | Nessuna dipendenza esterna | Solo Config file push, no Admin API runtime |
| **Hybrid Mode** | Control Plane (DB) + Data Plane (DB-less) | Separazione CP/DP | Più complesso |

## Architettura / Come Funziona

### Flusso di una Richiesta

```
Client
  │
  ▼
Kong Proxy (porta 8000 HTTP / 8443 HTTPS)
  │
  ├── Matching Route (host, path, method)
  │
  ├── Plugin chain (Pre-processing):
  │   ├── JWT authentication
  │   ├── Rate Limiting
  │   ├── IP Restriction
  │   └── Request Transformer
  │
  ├── Forwarding → Upstream service
  │
  └── Plugin chain (Post-processing):
      ├── Response Transformer
      └── Logging (file, http)

Kong Admin API (porta 8001 HTTP / 8444 HTTPS)
  └── Configurazione di Service, Route, Plugin, Consumer
```

## Configurazione & Pratica

### Docker Compose — Setup Completo

```yaml
# docker-compose.yaml
version: '3.8'

services:
  kong-db:
    image: postgres:15
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpassword
    volumes:
      - kong_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kong"]
      interval: 10s

  kong-migration:
    image: kong:3.5
    command: kong migrations bootstrap
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: kong-db
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpassword
      KONG_PG_DATABASE: kong
    depends_on:
      kong-db:
        condition: service_healthy

  kong:
    image: kong:3.5
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: kong-db
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpassword
      KONG_PG_DATABASE: kong
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      KONG_ADMIN_LISTEN: 0.0.0.0:8001
      KONG_PROXY_LISTEN: 0.0.0.0:8000, 0.0.0.0:8443 ssl
    ports:
      - "8000:8000"   # HTTP proxy
      - "8443:8443"   # HTTPS proxy
      - "8001:8001"   # Admin API
    depends_on:
      - kong-migration
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s

volumes:
  kong_data:
```

### Configurazione via Admin API

```bash
# 1. Crea un Service (il backend)
curl -X POST http://localhost:8001/services \
  -d name=user-service \
  -d url=http://user-service:8080

# 2. Crea una Route associata al Service
curl -X POST http://localhost:8001/services/user-service/routes \
  -d 'paths[]=/api/v1/users' \
  -d 'methods[]=GET' \
  -d 'methods[]=POST' \
  -d 'strip_path=true'

# 3. Aggiungi plugin JWT alla route
curl -X POST http://localhost:8001/services/user-service/plugins \
  -d name=jwt

# 4. Crea un Consumer
curl -X POST http://localhost:8001/consumers \
  -d username=mobile-app

# 5. Crea credenziali JWT per il Consumer
curl -X POST http://localhost:8001/consumers/mobile-app/jwt \
  -d algorithm=HS256 \
  -d secret=my-secret-key

# 6. Aggiungi rate limiting al Service
curl -X POST http://localhost:8001/services/user-service/plugins \
  -d name=rate-limiting \
  -d 'config.minute=100' \
  -d 'config.policy=redis' \
  -d 'config.redis_host=redis' \
  -d 'config.redis_port=6379'

# 7. Aggiungi CORS
curl -X POST http://localhost:8001/services/user-service/plugins \
  -d name=cors \
  -d 'config.origins[]=https://myapp.example.com' \
  -d 'config.methods[]=GET,POST,PUT,DELETE' \
  -d 'config.headers[]=Authorization,Content-Type'
```

### Configurazione Dichiarativa (DB-less) con Kong Deck

```yaml
# kong.yaml — Configurazione dichiarativa (per deck sync)
_format_version: "3.0"
_transform: true

services:
  - name: user-service
    url: http://user-service:8080
    connect_timeout: 5000
    read_timeout: 30000
    retries: 3

    routes:
      - name: user-routes
        paths:
          - /api/v1/users
        methods:
          - GET
          - POST
          - PUT
          - DELETE
        strip_path: true
        preserve_host: false

    plugins:
      - name: jwt
        config:
          key_claim_name: kid
          claims_to_verify:
            - exp
          maximum_expiration: 3600

      - name: rate-limiting
        config:
          minute: 100
          hour: 5000
          policy: redis
          redis_host: redis
          redis_port: 6379

      - name: request-transformer
        config:
          add:
            headers:
              - X-Gateway-Version:1.0

      - name: response-transformer
        config:
          remove:
            headers:
              - X-Internal-Server

consumers:
  - username: mobile-app
    jwt_secrets:
      - algorithm: HS256
        secret: "$(SECRET_JWT_KEY)"

  - username: web-app
    jwt_secrets:
      - algorithm: RS256
        rsa_public_key: |
          -----BEGIN PUBLIC KEY-----
          ...
          -----END PUBLIC KEY-----

upstreams:
  - name: order-service
    algorithm: least-connections
    healthchecks:
      active:
        healthy:
          interval: 5
          successes: 2
        unhealthy:
          interval: 5
          http_failures: 3
        http_path: /health

    targets:
      - target: order-svc-1:8080
        weight: 100
      - target: order-svc-2:8080
        weight: 100
```

```bash
# Applica la configurazione con deck
deck sync --kong-addr http://localhost:8001 --state kong.yaml

# Verifica differenze prima di applicare
deck diff --kong-addr http://localhost:8001 --state kong.yaml

# Esporta configurazione attuale
deck dump --kong-addr http://localhost:8001 --output-file kong-current.yaml
```

### Kong Ingress Controller (Kubernetes)

```yaml
# Installa KIC con Helm
# helm install kong kong/ingress -n kong --create-namespace

# Configurazione Ingress con Kong
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    konghq.com/strip-path: "true"
    konghq.com/plugins: rate-limit,jwt-auth
spec:
  ingressClassName: kong
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api/v1/users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 8080

---
# Plugin rate-limiting come CRD Kubernetes
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: rate-limit
plugin: rate-limiting
config:
  minute: 100
  policy: redis
  redis_host: redis
  redis_port: 6379

---
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: jwt-auth
plugin: jwt
config:
  claims_to_verify:
    - exp
```

## Best Practices

- **DB-less in produzione per Kubernetes**: più semplice, nessuna dipendenza da PostgreSQL — configurazione come ConfigMap
- **Separare plugin globali da specifici**: applicare autenticazione e logging globalmente, rate limiting e trasformazioni per Service
- **Consumer per applicazione, non per utente**: i Consumer Kong rappresentano applicazioni client, non utenti finali (gli utenti sono nel JWT)
- **Health check sugli Upstream**: configurare sempre health check attivi per rilevare backend degradati
- **Usare deck**: gestire la configurazione come codice con versioning Git
- **Plugin ordering**: l'ordine di esecuzione dei plugin è predefinito (authentication → rate limiting → transform) — verificare la priorità se si aggiungono plugin custom

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| `401 Unauthorized` | JWT mancante o invalido | Verificare plugin JWT e header `Authorization: Bearer ...` |
| `429 Too Many Requests` | Rate limit superato | Verificare quota in Admin API: `GET /consumers/{id}/plugins` |
| Route non trovata (`404`) | Path non corrisponde | `deck diff` per verificare config; verificare `strip_path` |
| Backend non raggiungibile | Health check fallisce | `GET /upstreams/{name}/health` via Admin API |
| Plugin non si applica | Plugin associato al Consumer invece che alla Route | Verificare scope del plugin |

```bash
# Debug: verifica quale route viene matchata
curl -I http://localhost:8000/api/v1/users \
  -H "Kong-Debug: 1"  # Header debug (solo in dev)

# Stato health dei backend
curl http://localhost:8001/upstreams/order-service/health | jq .

# Lista plugin attivi su un service
curl http://localhost:8001/services/user-service/plugins | jq '.data[].name'
```

## Relazioni

??? info "Pattern Base API Gateway"
    Concetti fondamentali prima di approfondire Kong.

    **Approfondimento →** [Pattern e Concetti Base](pattern-base.md)

??? info "Rate Limiting — Algoritmi e implementazione"
    Come funziona il rate limiting e le alternative a Kong.

    **Approfondimento →** [Rate Limiting](rate-limiting.md)

## Riferimenti

- [Kong Documentation](https://docs.konghq.com/)
- [Kong Deck — Declarative Configuration](https://docs.konghq.com/deck/latest/)
- [Kong Ingress Controller](https://docs.konghq.com/kubernetes-ingress-controller/latest/)
