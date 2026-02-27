---
title: "Rate Limiting"
slug: rate-limiting
category: networking
tags: [rate-limiting, throttling, api, protezione, redis, token-bucket, sliding-window]
search_keywords: [rate limiting, throttling, token bucket, sliding window, fixed window, leaky bucket, distributed rate limiting, redis rate limit, 429 too many requests, retry-after, burst, quota, rate limit header, nginx rate limit, kong rate limit, api abuse, ddos protection]
parent: networking/api-gateway/_index
related: [networking/api-gateway/pattern-base, networking/api-gateway/kong, networking/sicurezza/ddos-protezione]
official_docs: https://nginx.org/en/docs/http/ngx_http_limit_req_module.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Rate Limiting

## Panoramica

Il rate limiting è il meccanismo che limita il numero di richieste che un client può fare a un'API in un determinato intervallo di tempo. Serve a proteggere i backend dall'overload, prevenire abusi (scraping, attacchi brute-force), garantire equità d'accesso tra i client e rispettare contratti SLA. La risposta standard quando il limite è superato è `429 Too Many Requests` con l'header `Retry-After` che indica quando riprovare.

Il rate limiting deve essere **distribuito** in produzione: se si hanno più istanze del gateway, ognuna deve vedere il contatore globale — la soluzione tipica è Redis come store condiviso.

## Concetti Chiave

### Algoritmi di Rate Limiting

#### Fixed Window (Finestra Fissa)

Il periodo viene diviso in finestre temporali fisse (es. ogni minuto). Il contatore si azzera all'inizio di ogni finestra.

```
Finestra: [00:00 — 01:00]   Finestra: [01:00 — 02:00]
Client A:   99 richieste          1 richiesta
Limite: 100/minuto → OK      → OK

Problema: burst al confine
[00:59]: 100 richieste → OK
[01:00]: 100 richieste → OK (finestra si azzera!)
Effettivo: 200 richieste in 1 secondo
```

**Pros:** Semplicissimo da implementare, O(1) per richiesta.
**Cons:** Burst al confine della finestra.

#### Sliding Window Log (Finestra Scorrevole — Log)

Mantiene il timestamp di ogni richiesta. Per ogni nuova richiesta, scarta le entry più vecchie della finestra e conta quelle rimaste.

```
Limite: 100/minuto
Ora: 14:05:30

Log richieste: [14:04:31, 14:04:45, 14:05:00, 14:05:29]
Finestra attiva: [14:04:30 — 14:05:30]
Conteggio: 4 richieste → OK

Pros: preciso
Cons: memoria O(richieste per finestra) — costoso ad alta frequenza
```

#### Sliding Window Counter (Finestra Scorrevole — Counter)

Approssima la finestra scorrevole usando i contatori di due finestre fisse adiacenti:

```
Limite: 100/minuto
Finestra precedente (14:04): 80 richieste
Finestra corrente (14:05): 20 richieste, posizione nel minuto: 70%

Stima: 80 × (1 - 0.70) + 20 = 80 × 0.30 + 20 = 24 + 20 = 44 richieste
```

**Pros:** Memoria O(1), preciso (~0.1% errore), adatto per Redis.
**Cons:** Approssimato (ma la precisione è accettabile per quasi tutti i casi d'uso).

#### Token Bucket

Un "secchio" viene riempito con token a velocità fissa (rate). Ogni richiesta consuma un token. Se il secchio è vuoto, la richiesta viene rifiutata. Il secchio ha una capienza massima (burst).

```
Secchio: capienza 10 token
Rate: 5 token/secondo
Stato attuale: 8 token

Richiesta 1: consume 1 token → 7 token rimasti → OK
Richiesta 2: consume 1 token → 6 token rimasti → OK
...
Richiesta 8: consume 1 token → 0 token rimasti → OK
Richiesta 9: 0 token → 429

Dopo 1 secondo: +5 token → 5 token
```

**Pros:** Permette burst controllati (capienza del secchio), naturalissimo per limitare velocità media.
**Cons:** Più complesso da implementare in Redis.

#### Leaky Bucket

Simile a Token Bucket ma invertito: le richieste entrano nel bucket e vengono processate a velocità costante (leak rate). Eccedenze vengono scartate.

**Differenza chiave con Token Bucket:** Token Bucket permette burst (fino alla capienza); Leaky Bucket emette a velocità costante indipendentemente dai burst in entrata. Ottimo per smoothing del traffico verso backend delicati.

### Dimensioni del Rate Limiting

| Dimensione | Descrizione | Esempio |
|-----------|-------------|---------|
| Per IP | Contatore per indirizzo IP | 100 req/min per IP |
| Per API Key/Token | Contatore per client | 1000 req/min per API key |
| Per Utente | Contatore per user ID (JWT) | 500 req/min per user |
| Per Endpoint | Limiti diversi per route | 10 req/s su POST /login, 100 req/s su GET |
| Globale | Limite totale del sistema | Max 10k req/s totali |

## Architettura / Come Funziona

### Rate Limiting Distribuito con Redis

```
Client Request
      │
      ▼
API Gateway (istanza 1)     API Gateway (istanza 2)
      │                            │
      └────────────────────────────┘
                   │
                   ▼
              Redis (store condiviso)
         ┌──────────────────────┐
         │ rate:user:u123:14:05 │ → 47 (richieste in questa finestra)
         │ TTL: 60s             │
         └──────────────────────┘
```

**Script Lua per Sliding Window Counter in Redis:**

```lua
-- rate_limit.lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])  -- in secondi
local now = tonumber(ARGV[3])     -- timestamp corrente (ms)

-- Rimuovi entry vecchie (sliding window)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)

-- Conta richieste nella finestra
local count = redis.call('ZCARD', key)

if count >= limit then
    return 0  -- Rate limit exceeded
end

-- Aggiungi la richiesta corrente
redis.call('ZADD', key, now, now)
redis.call('EXPIRE', key, window)
return 1  -- OK
```

## Configurazione & Pratica

### Nginx — Rate Limiting

```nginx
http {
    # Definisci zone di rate limiting (in http block)

    # Limite per IP: 10 req/secondo
    limit_req_zone $binary_remote_addr zone=per_ip:10m rate=10r/s;

    # Limite per API token (header Authorization)
    limit_req_zone $http_authorization zone=per_token:10m rate=100r/m;

    # Limite per combinazione IP+path
    limit_req_zone $binary_remote_addr$request_uri zone=per_ip_path:20m rate=5r/s;

    server {
        listen 443 ssl http2;

        # Endpoint login: limite stretto anti-brute force
        location /auth/login {
            limit_req zone=per_ip burst=5 nodelay;
            limit_req_status 429;

            # Header informativi al client
            add_header Retry-After 60 always;
            add_header X-RateLimit-Limit 5 always;
            proxy_pass http://auth-service;
        }

        # API generica: limite per token JWT
        location /api/ {
            limit_req zone=per_token burst=20 nodelay;
            limit_req_status 429;
            proxy_pass http://api-backend;
        }
    }
}
```

### Implementazione Custom in Go con Redis

```go
package ratelimit

import (
    "context"
    "fmt"
    "net/http"
    "strconv"
    "time"

    "github.com/redis/go-redis/v9"
)

type RateLimiter struct {
    rdb    *redis.Client
    limit  int           // Richieste massime per finestra
    window time.Duration // Dimensione della finestra
}

func NewRateLimiter(rdb *redis.Client, limit int, window time.Duration) *RateLimiter {
    return &RateLimiter{rdb: rdb, limit: limit, window: window}
}

// Allow verifica se la richiesta è consentita (sliding window counter)
func (rl *RateLimiter) Allow(ctx context.Context, key string) (bool, *RateInfo, error) {
    now := time.Now()
    windowStart := now.Add(-rl.window)
    redisKey := fmt.Sprintf("rate:%s:%d", key, now.Unix()/int64(rl.window.Seconds()))

    pipe := rl.rdb.Pipeline()
    pipe.ZRemRangeByScore(ctx, redisKey, "0", strconv.FormatInt(windowStart.UnixMilli(), 10))
    countCmd := pipe.ZCard(ctx, redisKey)
    pipe.ZAdd(ctx, redisKey, redis.Z{Score: float64(now.UnixMilli()), Member: now.UnixNano()})
    pipe.Expire(ctx, redisKey, rl.window)

    _, err := pipe.Exec(ctx)
    if err != nil {
        return false, nil, err
    }

    count := int(countCmd.Val())
    remaining := rl.limit - count - 1

    info := &RateInfo{
        Limit:     rl.limit,
        Remaining: max(0, remaining),
        Reset:     now.Add(rl.window).Unix(),
    }

    return count < rl.limit, info, nil
}

type RateInfo struct {
    Limit     int
    Remaining int
    Reset     int64 // Unix timestamp
}

// Middleware HTTP
func (rl *RateLimiter) Middleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Usa il token JWT o l'IP come chiave
        key := r.Header.Get("X-User-Id")
        if key == "" {
            key = "ip:" + r.RemoteAddr
        }

        allowed, info, err := rl.Allow(r.Context(), key)
        if err != nil {
            http.Error(w, "Internal Server Error", http.StatusInternalServerError)
            return
        }

        // Aggiungi header informativi
        w.Header().Set("X-RateLimit-Limit", strconv.Itoa(info.Limit))
        w.Header().Set("X-RateLimit-Remaining", strconv.Itoa(info.Remaining))
        w.Header().Set("X-RateLimit-Reset", strconv.FormatInt(info.Reset, 10))

        if !allowed {
            w.Header().Set("Retry-After", "60")
            http.Error(w, `{"error":"rate_limit_exceeded","message":"Too many requests"}`,
                http.StatusTooManyRequests)
            return
        }

        next.ServeHTTP(w, r)
    })
}

func max(a, b int) int {
    if a > b {
        return a
    }
    return b
}
```

### Header di Risposta Standard

```http
# Risposta normale
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 73
X-RateLimit-Reset: 1708780800   ← Unix timestamp della prossima reset

# Rate limit superato
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1708780800
Retry-After: 47                  ← Secondi prima di poter riprovare
Content-Type: application/json

{
  "error": "rate_limit_exceeded",
  "message": "Hai superato il limite di 100 richieste al minuto",
  "retry_after": 47
}
```

## Best Practices

- **Rate limiting a più livelli**: globale (protezione sistema) + per client (equità) + per endpoint (protezione endpoint sensibili)
- **Redis per distribuzione**: sempre usare Redis in produzione multi-istanza — il contatore locale non funziona con più pod
- **Burst ragionevole**: permettere burst brevi (2-5x il rate) per richieste legittime (caricamento pagina con molte risorse)
- **Header informativi**: sempre restituire `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` e `Retry-After` — i client ben scritti li usano per adattarsi
- **429, non 503**: usare il corretto status code — 503 indica un problema del server, 429 indica un limite del client
- **Whitelist per servizi interni**: escludere dal rate limiting il traffico tra microservizi interni o da IP di monitoring
- **Logging**: loggare ogni 429 con client ID, endpoint e timestamp — utile per investigare abusi e calibrare i limiti

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Rate limit diversi su istanze diverse | Ogni istanza ha contatore locale | Usare Redis come store condiviso |
| Burst legittimi bloccati | Burst troppo basso | Aumentare il burst, usare Token Bucket |
| Rate limiting non applicato | Redis non raggiungibile, fallback permissivo | Configurare circuit breaker su Redis |
| Client non rispetta Retry-After | Client non legge l'header | Documentare e verificare implementazione client |
| Limite troppo stringente | Calibrazione errata | Analizzare access log per distribuzione delle richieste |

## Relazioni

??? info "Kong Rate Limiting Plugin"
    Configurazione del rate limiting in Kong con Redis.

    **Approfondimento →** [Kong](kong.md)

??? info "Protezione DDoS — Attacchi volumetrici"
    Il rate limiting è una delle tecniche di mitigazione DDoS a livello applicativo.

    **Approfondimento →** [Protezione DDoS](../sicurezza/ddos-protezione.md)

## Riferimenti

- [Nginx Rate Limiting Module](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Kong Rate Limiting Plugin](https://docs.konghq.com/hub/kong-inc/rate-limiting/)
- [Redis Lua Scripting](https://redis.io/docs/manual/programmability/eval-intro/)
- [RFC 6585 — 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585)
