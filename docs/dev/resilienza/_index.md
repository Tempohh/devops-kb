---
title: "Resilienza"
slug: resilienza
category: dev
tags: [resilienza, circuit-breaker, retry, timeout, bulkhead, rate-limiting, fault-tolerance, microservizi]
search_keywords: [resilienza, resilience, fault tolerance, circuit breaker, circuit-breaker, retry, retry policy, exponential backoff, backoff esponenziale, jitter, timeout, bulkhead, rate limiting, throttling, fallback, graceful degradation, hystrix, resilience4j, polly, tenacity, pybreaker, go-resilience, failover, health check, health probe, liveness, readiness, istio retry, envoy circuit breaker, service mesh resilienza, chaos engineering, cascade failure, cascading failure, guasto a cascata, pattern di resilienza, resilience pattern, microservizi fault tolerance, rate limiter, semaphore, thread pool isolation, hedging, timeout propagation, context deadline]
parent: dev/_index
related: [dev/api/_index, dev/resilienza/health-checks, networking/service-mesh/_index, networking/service-mesh/istio, networking/service-mesh/envoy]
official_docs: https://resilience4j.readme.io/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Resilienza

## Panoramica

La resilienza è la capacità di un microservizio di **continuare a funzionare in modo degradato** quando le sue dipendenze falliscono, sono lente, o non raggiungibili. In un sistema distribuito ogni chiamata remota può fallire: rete instabile, servizio overloaded, deploy in corso, GC pause — sono tutti eventi normali, non eccezionali.

I pattern di resilienza si dividono in due livelli complementari:

- **Livello applicativo** — implementato nel codice del servizio: Resilience4j (Java), tenacity (Python), go-resilience (Go), Polly (.NET). Il controllo è granulare e visibile nel codice.
- **Livello infrastrutturale (service mesh)** — implementato nel proxy sidecar (Envoy/Linkerd): trasparente all'applicazione, configurabile via CRD Kubernetes. Limitato a retry e circuit breaker di base.

I due livelli non si escludono ma si sovrappongono: è normale usare timeout applicativi E timeout nel service mesh, con valori diversi e semantica diversa.

!!! warning "Doppio conteggio dei retry"
    Se configuri retry sia a livello applicativo che nel service mesh, ogni tentativo dell'applicazione genera N retry nel mesh. Una policy di 3 retry applicativi + 3 retry Istio può produrre fino a 9 tentativi totali verso il downstream. Pianifica consapevolmente e preferisci gestire i retry in un solo livello.

---

## Concetti Chiave

### Timeout

Il timeout è il pattern più fondamentale e spesso il più trascurato. Ogni chiamata esterna **deve** avere un timeout esplicito. Un servizio senza timeout su chiamate downstream può bloccare thread/goroutine indefinitamente, esaurendo le risorse e propagando il guasto.

```
Tipologie di timeout:
─────────────────────────────────────────────────────────
Connection timeout   → tempo massimo per aprire la connessione TCP
                       Tipicamente: 1-5 secondi

Read timeout         → tempo massimo per ricevere una risposta dopo
                       aver inviato la request
                       Tipicamente: dipende dall'SLA del servizio

Write timeout        → tempo massimo per inviare la request completa
                       Rilevante con payload grandi

Deadline / context   → timeout end-to-end propagato attraverso
                       la catena di chiamate (gRPC context, HTTP header)
```

!!! tip "Context propagation"
    In Go e gRPC usa sempre `context.WithTimeout` e propaga il context. Se il client upstream ha un deadline di 500ms, i servizi downstream devono rispettarlo — non ha senso fare retry se il budget di tempo è già esaurito.

### Retry con Backoff Esponenziale

Il retry semplice (retry immediato) sotto carico può peggiorare la situazione: tutti i client ritentano nello stesso momento, creando una tempesta di traffico che impedisce al servizio di riprendersi.

```
Backoff esponenziale + jitter:
─────────────────────────────────────────────────────────
Tentativo 1: attendi base_delay (es. 100ms)
Tentativo 2: attendi base_delay × 2 + random_jitter (es. 200ms + [0,50ms])
Tentativo 3: attendi base_delay × 4 + random_jitter (es. 400ms + [0,50ms])
Tentativo N: min(base_delay × 2^n, max_delay) + random_jitter

Il jitter (rumore casuale) desincronizza i client che stanno tutti
ritentando contemporaneamente → distribuisce il carico nel tempo.
```

**Condizioni per il retry:** ritenta SOLO su errori idempotenti e transitori:

| Errore | Retry? | Motivo |
|---|---|---|
| 500 Internal Server Error | Dipende | Solo se l'operazione è idempotente |
| 502 Bad Gateway | Sì | Errore transitorio di rete/proxy |
| 503 Service Unavailable | Sì | Servizio temporaneamente down |
| 504 Gateway Timeout | Sì | Timeout upstream |
| 429 Too Many Requests | Sì (dopo Retry-After) | Rate limit — rispettare il backoff indicato |
| 400 Bad Request | No | Errore client — il retry non cambierà nulla |
| 401 Unauthorized | No | Credenziali invalide |
| 404 Not Found | No | La risorsa non esiste |
| 409 Conflict | No | Conflitto di stato |

### Circuit Breaker

Il circuit breaker monitora le chiamate verso una dipendenza e, se il tasso di errori supera una soglia, "apre" il circuito interrompendo temporaneamente le chiamate. Questo protegge sia il servizio upstream (che è già in difficoltà) sia il servizio corrente (che non esaurisce thread/goroutine aspettando timeout).

```
Stati del Circuit Breaker:
─────────────────────────────────────────────────────────
CLOSED (normale)
  → Le chiamate passano normalmente
  → Errori vengono contati in una sliding window
  → Se error_rate > threshold → transizione a OPEN

OPEN (circuito aperto)
  → Le chiamate vengono bloccate immediatamente (fail fast)
  → Viene restituito un fallback o un errore esplicito
  → Dopo wait_duration → transizione a HALF-OPEN

HALF-OPEN (test)
  → Alcune chiamate di prova vengono lasciate passare
  → Se hanno successo → ritorno a CLOSED
  → Se falliscono → ritorno a OPEN
```

### Bulkhead

Il bulkhead (paratia stagna, termine navale) isola le risorse per evitare che un guasto in un'area si propaghi ad altre. In pratica: thread pool separati o semafori per call group diversi.

```
Senza bulkhead:
  OrderService → [thread pool condiviso 20 thread]
                     ├── chiama PaymentService (lento → occupa 20 thread)
                     └── chiama InventoryService (non può più rispondere!)

Con bulkhead:
  OrderService → [thread pool payment: 10 thread]  → PaymentService
               → [thread pool inventory: 10 thread] → InventoryService

  PaymentService lento → esaurisce i 10 thread del payment pool
  InventoryService rimane funzionante nel suo pool isolato
```

### Rate Limiting

Controlla la frequenza di chiamate in uscita o in entrata per proteggere servizi downstream o per rispettare i limiti di API esterne (es. provider cloud, servizi SaaS).

---

## Architettura / Come Funziona

### Stack di Resilienza Completo

```
Request da client upstream
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Service Mesh (Envoy sidecar)                          │
│  - Timeout: 30s (ceiling globale)                      │
│  - Retry: 2 tentativi su 502/503/504                   │
│  - Circuit Breaker: outlier detection                  │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│  Applicazione                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Rate Limiter (in entrata)                       │  │
│  │  → protegge il servizio da traffico eccessivo    │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Business Logic                                  │  │
│  │    │                                             │  │
│  │    ▼                                             │  │
│  │  [Bulkhead] Thread Pool Isolato per dipendenza   │  │
│  │    │                                             │  │
│  │    ▼                                             │  │
│  │  [Circuit Breaker] monitora error rate           │  │
│  │    │                                             │  │
│  │    ▼                                             │  │
│  │  [Retry + Backoff] su errori transitori          │  │
│  │    │                                             │  │
│  │    ▼                                             │  │
│  │  [Timeout] context deadline applicativo          │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
           Servizio downstream
```

### Ordine di Composizione dei Pattern

Quando si compongono più pattern, l'ordine conta:

```
Composizione corretta (dall'esterno verso l'interno):
  Bulkhead → Circuit Breaker → Timeout → Retry → chiamata

Logica:
1. Bulkhead: controlla prima se c'è capacità disponibile nel pool
2. Circuit Breaker: se il circuito è aperto, fail fast senza aspettare
3. Timeout: imposta il deadline per ogni tentativo
4. Retry: esegui la chiamata, ritenta se timeout o errore transitorio
```

---

## Configurazione & Pratica

### Java — Resilience4j

Resilience4j è la libreria di riferimento per la resilienza in Java post-Hystrix. È modulare e si integra nativamente con Spring Boot Actuator per le metriche.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-spring-boot3</artifactId>
    <version>2.2.0</version>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-aop</artifactId>
</dependency>
```

```yaml
# application.yml
resilience4j:
  circuitbreaker:
    instances:
      paymentService:
        register-health-indicator: true
        sliding-window-size: 10           # ultimi 10 chiamate
        minimum-number-of-calls: 5        # minimo per valutare
        failure-rate-threshold: 50        # >50% errori → OPEN
        wait-duration-in-open-state: 30s  # attendi 30s prima di HALF-OPEN
        permitted-number-of-calls-in-half-open-state: 3
        slow-call-duration-threshold: 2s  # chiamate >2s sono "slow"
        slow-call-rate-threshold: 80      # >80% slow → OPEN

  retry:
    instances:
      paymentService:
        max-attempts: 3
        wait-duration: 500ms
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2
        exponential-max-wait-duration: 10s
        retry-exceptions:
          - java.io.IOException
          - java.net.SocketTimeoutException
          - feign.RetryableException
        ignore-exceptions:
          - com.example.exceptions.BusinessException

  bulkhead:
    instances:
      paymentService:
        max-concurrent-calls: 10      # max thread paralleli
        max-wait-duration: 100ms      # attendi max 100ms se pool pieno

  timelimiter:
    instances:
      paymentService:
        timeout-duration: 3s
        cancel-running-future: true
```

```java
// PaymentClient.java
@Service
public class PaymentClient {

    private final WebClient webClient;

    // L'ordine delle annotazioni rispecchia la composizione dei pattern
    @CircuitBreaker(name = "paymentService", fallbackMethod = "paymentFallback")
    @Retry(name = "paymentService")
    @Bulkhead(name = "paymentService")
    @TimeLimiter(name = "paymentService")
    public CompletableFuture<PaymentResult> processPayment(PaymentRequest request) {
        return webClient.post()
            .uri("/payments")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(PaymentResult.class)
            .toFuture();
    }

    // Fallback chiamato quando il circuit breaker è OPEN
    public CompletableFuture<PaymentResult> paymentFallback(
            PaymentRequest request, Throwable ex) {
        log.warn("Payment service unavailable, returning cached/default response. Cause: {}",
                 ex.getMessage());
        // Graceful degradation: accetta l'ordine e processa il pagamento in async
        return CompletableFuture.completedFuture(
            PaymentResult.pending("Payment queued for retry"));
    }
}
```

### Python — tenacity

```python
# dependencies: pip install tenacity
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
import httpx

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.5, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,  # rilancia l'eccezione originale dopo tutti i tentativi
)
async def call_payment_service(client: httpx.AsyncClient, payload: dict) -> dict:
    response = await client.post(
        "/payments",
        json=payload,
        timeout=httpx.Timeout(connect=2.0, read=5.0, write=2.0, pool=1.0),
    )
    response.raise_for_status()
    return response.json()
```

```python
# Circuit Breaker con pybreaker
# pip install pybreaker
import pybreaker

payment_breaker = pybreaker.CircuitBreaker(
    fail_max=5,         # apri dopo 5 errori consecutivi
    reset_timeout=30,   # riprova dopo 30 secondi
    listeners=[pybreaker.CircuitBreakerListener()],
)

@payment_breaker
async def call_payment_with_breaker(payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        return await call_payment_service(client, payload)

# Gestione dello stato aperto
try:
    result = await call_payment_with_breaker(payload)
except pybreaker.CircuitBreakerError:
    # Circuit aperto — restituisci fallback
    return {"status": "pending", "message": "Payment service temporarily unavailable"}
```

### Go — pattern standard con context

```go
// resilience/retry.go
package resilience

import (
    "context"
    "math"
    "math/rand"
    "time"
)

type RetryConfig struct {
    MaxAttempts int
    BaseDelay   time.Duration
    MaxDelay    time.Duration
    Multiplier  float64
}

// WithRetry esegue fn con backoff esponenziale e jitter.
func WithRetry(ctx context.Context, cfg RetryConfig, fn func(ctx context.Context) error) error {
    var lastErr error
    for attempt := 0; attempt < cfg.MaxAttempts; attempt++ {
        if err := ctx.Err(); err != nil {
            return err // context cancellato o deadline superato
        }

        lastErr = fn(ctx)
        if lastErr == nil {
            return nil
        }

        if !isRetryable(lastErr) {
            return lastErr
        }

        if attempt < cfg.MaxAttempts-1 {
            delay := calculateDelay(cfg, attempt)
            select {
            case <-ctx.Done():
                return ctx.Err()
            case <-time.After(delay):
            }
        }
    }
    return lastErr
}

func calculateDelay(cfg RetryConfig, attempt int) time.Duration {
    exp := math.Pow(cfg.Multiplier, float64(attempt))
    delay := time.Duration(float64(cfg.BaseDelay) * exp)
    if delay > cfg.MaxDelay {
        delay = cfg.MaxDelay
    }
    // Jitter: ±20% del delay calcolato
    jitter := time.Duration(rand.Int63n(int64(delay / 5)))
    return delay + jitter
}
```

```go
// Utilizzo con timeout via context
func (c *PaymentClient) ProcessPayment(ctx context.Context, req PaymentRequest) (*PaymentResult, error) {
    // Timeout applicativo: 5 secondi per tutta la catena retry
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    var result *PaymentResult

    err := resilience.WithRetry(ctx, resilience.RetryConfig{
        MaxAttempts: 3,
        BaseDelay:   200 * time.Millisecond,
        MaxDelay:    3 * time.Second,
        Multiplier:  2.0,
    }, func(ctx context.Context) error {
        resp, err := c.httpClient.Do(buildRequest(ctx, req))
        if err != nil {
            return err
        }
        defer resp.Body.Close()

        if resp.StatusCode == 503 || resp.StatusCode == 502 {
            return &RetryableError{StatusCode: resp.StatusCode}
        }
        if resp.StatusCode != 200 {
            return &NonRetryableError{StatusCode: resp.StatusCode}
        }
        return json.NewDecoder(resp.Body).Decode(&result)
    })

    return result, err
}
```

### Istio — Circuit Breaker e Retry via CRD

```yaml
# DestinationRule per circuit breaker (outlier detection)
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: payment-service-dr
  namespace: production
spec:
  host: payment-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100         # max connessioni TCP verso il servizio
      http:
        http1MaxPendingRequests: 50 # max request in attesa
        maxRequestsPerConnection: 10
    outlierDetection:
      # Circuit breaker basato su errori HTTP consecutivi
      consecutiveGatewayErrors: 5  # 5 errori 502/503/504 → eject
      consecutive5xxErrors: 5
      interval: 30s                # intervallo di scan
      baseEjectionTime: 30s        # durata ejection minima
      maxEjectionPercent: 50       # max 50% degli endpoint espulsi
      minHealthPercent: 50         # mantieni almeno 50% degli endpoint
```

```yaml
# VirtualService per retry policy
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: payment-service-vs
  namespace: production
spec:
  hosts:
    - payment-service
  http:
    - timeout: 10s           # timeout globale per la route
      retries:
        attempts: 2          # max 2 retry (3 tentativi totali)
        perTryTimeout: 3s    # timeout per ogni singolo tentativo
        retryOn: >-
          gateway-error,connect-failure,retriable-4xx,
          reset,retriable-status-codes
        retryRemoteStatuses: "503,504"
      route:
        - destination:
            host: payment-service
            port:
              number: 8080
```

---

## Best Practices

### Regole Fondamentali

!!! tip "Timeout sempre esplicito"
    Non esiste una "buona" value di default per i timeout — dipende dall'SLA del servizio chiamato. Definisci sempre timeout esplicitamente nel codice e documentali. Un timeout implicito (infinito) è un bug latente.

```
Checklist resilienza per ogni chiamata esterna:
  □ Connection timeout definito
  □ Read timeout definito
  □ Retry solo su errori idempotenti e transitori
  □ Max tentativi limitati (solitamente 2-3)
  □ Backoff esponenziale con jitter
  □ Circuit breaker configurato per servizi critici
  □ Fallback definito (anche se è solo un errore esplicito)
  □ Metriche esposte (success_rate, latency_p99, circuit_state)
```

### Fallback Patterns

```
Strategie di fallback (dalla più robusta alla meno):
────────────────────────────────────────────────────
1. Cache — restituisci l'ultima risposta valida cached
   Ideale per: dati che cambiano raramente (catalogo prodotti, config)
   Rischio: dati stale

2. Default statico — risposta predefinita sicura
   Ideale per: feature non critiche (raccomandazioni, personalizzazione)
   Rischio: esperienza degradata

3. Coda asincrona — accetta la request e processala in retry
   Ideale per: operazioni write (pagamenti, ordini)
   Rischio: complessità di stato, idempotency obbligatoria

4. Errore esplicito — fail fast con messaggio chiaro
   Ideale per: operazioni critiche dove il dato stale è pericoloso
   Rischio: nessuno — il cliente sa che c'è un problema
```

### Idempotency nei Retry

!!! warning "Operazioni non idempotenti e retry"
    Non ritentare mai operazioni non idempotenti (es. addebito pagamento, invio email) senza una strategia di idempotency. Usa `Idempotency-Key` nelle API o chiavi di deduplication nel message broker.

```java
// Esempio: idempotency key con Redis per prevenire doppio addebito
@Retry(name = "paymentService")
public PaymentResult processPaymentIdempotent(String idempotencyKey, PaymentRequest req) {
    // Prima controlla se questa operazione è già stata completata
    Optional<PaymentResult> cached = redisCache.get("payment:" + idempotencyKey);
    if (cached.isPresent()) {
        return cached.get(); // restituisci il risultato precedente
    }

    PaymentResult result = paymentClient.charge(req);

    // Cache per 24h per assorbire retry tardivi
    redisCache.set("payment:" + idempotencyKey, result, Duration.ofHours(24));
    return result;
}
```

---

## Troubleshooting

### Problema: Cascade Failure — un servizio lento abbatte tutto il sistema

**Sintomo:** Un servizio downstream rallenta. Tutti i thread del servizio upstream vengono bloccati ad aspettare. Il servizio upstream smette di rispondere ai propri client. Il guasto si propaga a cascata verso l'alto.

**Causa:** Assenza di timeout e/o circuit breaker. I thread del thread pool vengono occupati da chiamate bloccate, nessun thread rimane disponibile per nuove request.

**Soluzione:**
```yaml
# 1. Configura timeout reali su ogni client HTTP
resilience4j:
  timelimiter:
    instances:
      downstreamService:
        timeout-duration: 2s  # MAI lasciare illimitato

# 2. Aggiungi circuit breaker con threshold aggressivi per servizi critici
  circuitbreaker:
    instances:
      downstreamService:
        failure-rate-threshold: 30  # apri dopo 30% di errori
        wait-duration-in-open-state: 15s

# 3. Bulkhead per isolare il pool di thread
  bulkhead:
    instances:
      downstreamService:
        max-concurrent-calls: 5  # mai più di 5 chiamate parallele
```

---

### Problema: Retry storm — i retry peggiorano il servizio in recovery

**Sintomo:** Un servizio torna online dopo un'interruzione. Tutti i client iniziano a ritentare contemporaneamente. Il servizio viene immediatamente travolto dal traffico e torna down.

**Causa:** Retry senza jitter. Tutti i client aspettano lo stesso intervallo e inviano le richieste nello stesso momento (thundering herd problem).

**Soluzione:**
```java
// Sbagliato: tutti i client aspettano esattamente 1 secondo
@Retry(name = "badRetry")  // wait-duration: 1s senza jitter

// Corretto: jitter desincronizza i client
resilience4j:
  retry:
    instances:
      goodRetry:
        wait-duration: 500ms
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2
        exponential-max-wait-duration: 30s
        # Il jitter è abilitato automaticamente con exponential backoff in R4j
```

```python
# Python — jitter esplicito con tenacity
from tenacity import wait_random_exponential

@retry(
    wait=wait_random_exponential(multiplier=1, min=0.5, max=30),
    # wait_random_exponential aggiunge automaticamente il jitter
)
async def call_with_jitter(): ...
```

---

### Problema: Circuit breaker non scatta mai nonostante molti errori

**Sintomo:** Il servizio downstream è chiaramente in errore ma il circuit breaker rimane CLOSED. Il servizio continua a sprecare risorse su chiamate destinate a fallire.

**Causa comune 1:** `minimum-number-of-calls` troppo alto o sliding window troppo lunga rispetto al traffico reale.

**Causa comune 2:** Le eccezioni generate non vengono conteggiate come failure perché il CB è configurato per ignorarle.

**Diagnosi:**
```bash
# Controlla lo stato del circuit breaker via Actuator (Spring Boot)
curl http://localhost:8080/actuator/health | jq '.components.circuitBreakers'

# Output atteso:
# { "paymentService": { "status": "UP", "details": { "state": "CLOSED",
#   "failureRate": "45.0%", "bufferedCalls": 10 } } }

# Controlla le metriche Prometheus
curl http://localhost:8080/actuator/prometheus | grep resilience4j_circuitbreaker
```

**Soluzione:**
```yaml
resilience4j:
  circuitbreaker:
    instances:
      paymentService:
        minimum-number-of-calls: 3      # riduci se il traffico è basso
        sliding-window-size: 5          # window più piccola per reagire prima
        record-exceptions:
          - java.lang.Exception         # registra TUTTE le eccezioni come failure
        ignore-exceptions:
          - com.example.NotFoundException  # escludi esplicitamente le non-failure
```

---

### Problema: Timeout scatta troppo presto in ambienti con alta latenza variabile

**Sintomo:** In produzione scattano timeout su chiamate che in staging funzionano. Il P99 di latenza del downstream è molto più alto del P50.

**Causa:** Il timeout è calibrato sul P50 (mediana) invece che sul P99. In produzione con carico reale, il P99 è significativamente più alto.

**Diagnosi:**
```bash
# Misura i percentili reali con metriche Prometheus
# http_client_request_duration_seconds{service="payment"} bucket histogram

# Calcola P99 con PromQL
histogram_quantile(0.99,
  sum(rate(http_client_request_duration_seconds_bucket{
    service="payment-service"
  }[5m])) by (le)
)
```

**Soluzione:**
```
Regola di sizing del timeout:
  Timeout = P99_latency_downstream × 1.5 + connection_overhead

  Esempio:
  P99 del payment service = 800ms
  Connection overhead     = 50ms
  Timeout consigliato     = (800 + 50) × 1.5 ≈ 1.3s

  Aggiungi sempre un margine del 50% sul P99 per assorbire spike.
  Non usare mai il P50 o il P95 come base per il timeout.
```

---

## Relazioni

??? info "Dev / API Design — Idempotency keys e retry-safe API"
    Le API che supportano i retry devono essere idempotenti. Questo richiede progettazione specifica a livello di API contract: `Idempotency-Key` header, status code semantici per operazioni già completate. → [API Design](../api/_index.md)

??? info "Networking / Service Mesh — Resilienza a livello infrastrutturale"
    Circuit breaker e retry si possono implementare anche a livello di service mesh (Istio, Linkerd, Envoy) senza modificare il codice applicativo. I due livelli sono complementari ma vanno coordinati per evitare moltiplicazione dei retry. → [Service Mesh](../../networking/service-mesh/_index.md)

??? info "Networking / Service Mesh / Istio — DestinationRule e VirtualService"
    I CRD Istio `DestinationRule` (outlier detection) e `VirtualService` (retry policy, timeout) sono il principale meccanismo di resilienza infrastrutturale in ambienti Kubernetes con Istio. → [Istio](../../networking/service-mesh/istio.md)

??? info "Monitoring — Metriche di salute del circuit breaker"
    Resilience4j espone metriche Prometheus per circuit breaker state, call volume, failure rate, e latency. Configurare alert su `resilience4j_circuitbreaker_state` e `resilience4j_circuitbreaker_failure_rate` è essenziale per osservare la resilienza in produzione. → [Prometheus](../../monitoring/tools/prometheus.md)

---

## Riferimenti

- [Resilience4j Documentation](https://resilience4j.readme.io/) — Libreria Java di riferimento
- [tenacity](https://tenacity.readthedocs.io/) — Libreria retry per Python
- [Release It! (book)](https://pragprog.com/titles/mnee2/release-it-second-edition/) — Michael Nygard, il testo fondamentale sui pattern di stabilità
- [AWS Builder's Library: Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) — Guida pratica AWS
- [Google SRE Book: Handling Overload](https://sre.google/sre-book/handling-overload/) — Approccio Google
- [Istio Traffic Management](https://istio.io/latest/docs/concepts/traffic-management/) — Circuit breaker e retry via service mesh
- [Microsoft Azure Architecture: Retry pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry) — Pattern catalog
