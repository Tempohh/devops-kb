---
title: "Circuit Breaker — Implementazione Applicativa"
slug: circuit-breaker
category: dev
tags: [resilienza, circuit-breaker, resilience4j, polly, gobreaker, fault-tolerance, microservizi, metriche]
search_keywords: [circuit breaker, circuit-breaker, cb, hystrix, resilience4j, polly, gobreaker, sony/gobreaker, go-resilience, fault tolerance, fault-tolerance, tolleranza ai guasti, fail fast, stato aperto, stato chiuso, half-open, sliding window, failure rate threshold, slow call threshold, fallback, graceful degradation, bulkhead, retry, timeout, rate limiter, micrometer, prometheus metriche cb, circuit breaker state, CBStateTransition, ResiliencePipeline, AddCircuitBreaker, AddRetry, AddFallback, AddTimeout, exponential backoff, jitter, testcontainers, toxiproxy, network fault injection, chaos testing, circuit breaker test, app vs service mesh, istio circuit breaker, envoy outlier detection, resilienza applicativa, pattern di stabilità, michael nygard, release it, thread pool isolation, semaphore, max concurrent calls, wait duration open state]
parent: dev/resilienza/_index
related: [dev/resilienza/_index, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go, networking/service-mesh/istio]
official_docs: https://resilience4j.readme.io/docs/circuitbreaker
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# Circuit Breaker — Implementazione Applicativa

## Panoramica

Il Circuit Breaker è un pattern di resilienza che protegge un servizio dal continuare a chiamare una dipendenza in stato di guasto. Funziona come un fusibile elettrico: monitora le chiamate verso un servizio downstream e, al superamento di una soglia di errori (o di latenza), "apre" il circuito — le chiamate successive falliscono immediatamente senza nemmeno tentare la connessione. Dopo un periodo di attesa, passa a uno stato di test (*half-open*) per verificare se il downstream si è ripreso.

**Quando usare un circuit breaker applicativo:** quando il servizio corrente chiama dipendenze esterne (HTTP, gRPC, database, broker) che possono diventare lente o non disponibili, e vuoi controllare in modo granulare le policy per ogni dipendenza specifica, integrare fallback con logica di business, o esporre metriche dettagliate sullo stato del circuito.

**Quando usare il circuit breaker del service mesh (Istio/Envoy/Linkerd):** quando il team non vuole modificare il codice, le policy sono uniformi tra tutti i servizi, e il controllo granulare per singola dipendenza non è necessario.

I due livelli non si escludono ma vanno coordinati — vedi sezione [App vs Service Mesh](#app-vs-service-mesh).

!!! warning "Circuit Breaker non sostituisce il timeout"
    Un circuit breaker aperto restituisce un errore *immediato*. Ma finché il circuito è CLOSED, ogni chiamata può bloccarsi fino al timeout. Il timeout rimane obbligatorio: un circuit breaker senza timeout non protegge dall'esaurimento del thread pool.

---

## Concetti Chiave

### Macchina a Stati

```
                  error_rate > threshold
       ┌─────────────────────────────────────┐
       │                                     ▼
   ┌───────┐  wait_duration expires   ┌────────────┐
   │ OPEN  │─────────────────────────▶│ HALF-OPEN  │
   └───────┘                          └────────────┘
       ▲                                    │
       │    probe calls fail                │ probe calls succeed
       │◄───────────────────────────────────┘
                                            │ probe calls succeed
                                            ▼
                                       ┌────────┐
                                       │ CLOSED │
                                       └────────┘
                                            │
                                  error_rate > threshold
                                            │
                                            ▼
                                        (→ OPEN)
```

| Stato | Comportamento | Transizione |
|---|---|---|
| **CLOSED** | Chiamate passano normalmente; errori vengono registrati nella sliding window | Se `failure_rate >= threshold` → OPEN |
| **OPEN** | Chiamate bloccate immediatamente con `CallNotPermittedException` | Dopo `wait_duration` → HALF-OPEN |
| **HALF-OPEN** | Numero limitato di chiamate di test ammesse | Se OK → CLOSED; se KO → OPEN |

### Tipi di Sliding Window

Resilience4j (e la maggior parte delle librerie moderne) supporta due modalità:

| Tipo | Quando usare | Pro | Contro |
|---|---|---|---|
| **COUNT_BASED** | Traffico costante e alto | Semplice da ragionare | Insensibile al tempo; reacts slowly su traffico basso |
| **TIME_BASED** | Traffico variabile o a burst | Reagisce in finestre temporali | Richiede calibrazione del window size in secondi |

### Slow Call Detection

Oltre agli errori HTTP, il circuit breaker moderno può aprirsi anche per *chiamate lente*: se una percentuale delle chiamate supera una certa durata (`slow_call_duration_threshold`), il circuito si apre anche in assenza di errori espliciti. Questo cattura la degradazione di performance prima che diventi un errore.

---

## Architettura / Come Funziona

### Composizione con Altri Pattern

Il circuit breaker va sempre composto con retry, timeout e bulkhead. L'ordine di wrapping è critico:

```
Request
   │
   ▼
[Bulkhead]          → controlla la concorrenza disponibile nel pool
   │
   ▼
[Circuit Breaker]   → fail fast se il circuito è aperto
   │
   ▼
[TimeLimiter]       → imposta il deadline per questo tentativo
   │
   ▼
[Retry]             → ritenta su errori transitori
   │
   ▼
Chiamata reale
```

Il bulkhead sta all'esterno: se il pool è pieno, rifiuta la request prima ancora di consultare il CB. Il CB sta fuori dal retry: se il circuito è aperto, non ha senso nemmeno tentare il retry — il CB aperto è già un segnale che tutti i tentativi falliranno.

### App vs Service Mesh

```
┌──────────────────────────────────────────────────────────────┐
│ Livello Applicativo (Resilience4j / Polly / gobreaker)       │
│                                                              │
│ + Fallback con logica di business (cache, default, coda)    │
│ + Granularità per endpoint/operazione specifica              │
│ + Metriche dettagliate (state transitions, call volume)      │
│ + Idempotency key e retry-safe nel codice                    │
│ + Test precisi con Testcontainers + Toxiproxy                │
│                                                              │
│ - Richiede modifica del codice                              │
│ - Ogni linguaggio ha la propria libreria                     │
│ - Duplica config se il mesh fa lo stesso                     │
└──────────────────────────────────────────────────────────────┘
         vs
┌──────────────────────────────────────────────────────────────┐
│ Livello Service Mesh (Istio DestinationRule / Envoy)         │
│                                                              │
│ + Trasparente all'applicazione                              │
│ + Uniforme per tutti i servizi del mesh                      │
│ + Zero modifica al codice applicativo                        │
│ + Visibilità centralizzata (Kiali, Grafana Istio dashboard)  │
│                                                              │
│ - Solo outlier detection per host (non per singolo endpoint) │
│ - Nessun fallback applicativo                                │
│ - Retry possono moltiplicarsi (vedi _index.md warning)       │
│ - Dipende dall'infrastruttura (non portabile)                │
└──────────────────────────────────────────────────────────────┘
```

**Regola pratica:**
- Servizi interni con logica di fallback critica → CB applicativo
- Servizi dove basta il fail fast e il retry mesh è sufficiente → solo service mesh
- Servizi critici (pagamenti, autenticazione) → entrambi i livelli, coordinati

---

## Configurazione & Pratica

### Java — Resilience4j con Spring Boot

#### Dipendenze Maven

```xml
<!-- pom.xml — Spring Boot 3.x -->
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-spring-boot3</artifactId>
    <version>2.2.0</version>
</dependency>
<!-- AOP obbligatorio per le annotazioni @CircuitBreaker, @Retry, etc. -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-aop</artifactId>
</dependency>
<!-- Metriche Prometheus via Micrometer -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

#### Configurazione via Properties (Consigliata)

```yaml
# application.yml
resilience4j:
  circuitbreaker:
    instances:
      paymentService:
        register-health-indicator: true          # Espone stato in /actuator/health
        sliding-window-type: COUNT_BASED
        sliding-window-size: 20                  # Ultimi 20 chiamate valutate
        minimum-number-of-calls: 5               # Min per calcolare failure rate
        failure-rate-threshold: 50               # >50% errori → OPEN
        slow-call-duration-threshold: 2s         # Chiamate >2s = "slow"
        slow-call-rate-threshold: 80             # >80% slow → OPEN
        wait-duration-in-open-state: 30s         # Attesa prima di HALF-OPEN
        permitted-number-of-calls-in-half-open-state: 3  # Probe calls
        automatic-transition-from-open-to-half-open-enabled: true
        record-exceptions:
          - java.io.IOException
          - java.net.SocketTimeoutException
          - java.util.concurrent.TimeoutException
          - feign.RetryableException
          - org.springframework.web.client.HttpServerErrorException
        ignore-exceptions:
          # Non apertura su errori 4xx che sono dell'utente, non del servizio
          - com.example.exceptions.ValidationException
          - com.example.exceptions.NotFoundException

  retry:
    instances:
      paymentService:
        max-attempts: 3
        wait-duration: 500ms
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2.0
        exponential-max-wait-duration: 10s
        retry-exceptions:
          - java.io.IOException
          - java.net.SocketTimeoutException
        ignore-exceptions:
          - com.example.exceptions.BusinessException

  bulkhead:
    instances:
      paymentService:
        max-concurrent-calls: 15
        max-wait-duration: 100ms    # Attendi max 100ms se pool pieno

  timelimiter:
    instances:
      paymentService:
        timeout-duration: 3s
        cancel-running-future: true
```

#### Configurazione via @Bean (Consigliata per Config Dinamica)

```java
// ResilienceConfig.java
@Configuration
public class ResilienceConfig {

    @Bean
    public CircuitBreakerConfig paymentCBConfig() {
        return CircuitBreakerConfig.custom()
            .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
            .slidingWindowSize(20)
            .minimumNumberOfCalls(5)
            .failureRateThreshold(50f)
            .slowCallDurationThreshold(Duration.ofSeconds(2))
            .slowCallRateThreshold(80f)
            .waitDurationInOpenState(Duration.ofSeconds(30))
            .permittedNumberOfCallsInHalfOpenState(3)
            .automaticTransitionFromOpenToHalfOpenEnabled(true)
            .recordExceptions(IOException.class, SocketTimeoutException.class)
            .ignoreExceptions(ValidationException.class)
            .build();
    }

    @Bean
    public CircuitBreakerRegistry circuitBreakerRegistry(
            CircuitBreakerConfig paymentCBConfig) {
        // Registry consente di creare CB da config named
        Map<String, CircuitBreakerConfig> configs = Map.of(
            "paymentService", paymentCBConfig
        );
        return CircuitBreakerRegistry.of(configs);
    }
}
```

#### Utilizzo con Annotazioni

```java
// PaymentClient.java
@Service
@Slf4j
public class PaymentClient {

    private final WebClient webClient;

    public PaymentClient(WebClient.Builder builder) {
        this.webClient = builder.baseUrl("http://payment-service").build();
    }

    // Ordine annotazioni = ordine wrapping (CircuitBreaker esterno, Retry interno)
    @CircuitBreaker(name = "paymentService", fallbackMethod = "paymentFallback")
    @Retry(name = "paymentService", fallbackMethod = "paymentFallback")
    @Bulkhead(name = "paymentService")
    @TimeLimiter(name = "paymentService")
    public CompletableFuture<PaymentResult> processPayment(PaymentRequest request) {
        return webClient.post()
            .uri("/api/v1/payments")
            .bodyValue(request)
            .retrieve()
            .onStatus(
                status -> status.is5xxServerError(),
                response -> response.bodyToMono(String.class)
                    .flatMap(body -> Mono.error(
                        new HttpServerErrorException(response.statusCode(), body)))
            )
            .bodyToMono(PaymentResult.class)
            .toFuture();
    }

    // Fallback per CircuitBreaker (riceve Throwable come ultimo parametro)
    public CompletableFuture<PaymentResult> paymentFallback(
            PaymentRequest request, CallNotPermittedException ex) {
        // Circuito aperto — fail fast, non aspettare
        log.warn("Circuit OPEN for paymentService, returning pending result. CB: {}",
                 ex.getCausingCircuitBreakerName());
        return CompletableFuture.completedFuture(
            PaymentResult.pending(request.getOrderId(), "Payment queued — service temporarily unavailable"));
    }

    // Fallback generico per altri errori (deve accettare Throwable)
    public CompletableFuture<PaymentResult> paymentFallback(
            PaymentRequest request, Throwable ex) {
        log.error("Payment service failed, activating fallback. Cause: {}", ex.getMessage());
        return CompletableFuture.completedFuture(
            PaymentResult.pending(request.getOrderId(), "Queued for async processing"));
    }
}
```

#### Metriche Micrometer e Prometheus

Resilience4j espone automaticamente metriche via Micrometer quando `spring-boot-starter-actuator` e il registry Prometheus sono presenti:

```bash
# Endpoint Prometheus (GET /actuator/prometheus)
# Filtra metriche CB:
curl -s http://localhost:8080/actuator/prometheus | grep resilience4j_circuitbreaker

# Output atteso:
# resilience4j_circuitbreaker_state{name="paymentService",state="closed"} 1.0
# resilience4j_circuitbreaker_state{name="paymentService",state="open"} 0.0
# resilience4j_circuitbreaker_state{name="paymentService",state="half_open"} 0.0
# resilience4j_circuitbreaker_failure_rate{name="paymentService"} 12.5
# resilience4j_circuitbreaker_slow_call_rate{name="paymentService"} 0.0
# resilience4j_circuitbreaker_calls_total{kind="successful",name="paymentService"} 42.0
# resilience4j_circuitbreaker_calls_total{kind="failed",name="paymentService"} 6.0
# resilience4j_circuitbreaker_calls_total{kind="not_permitted",name="paymentService"} 0.0
# resilience4j_circuitbreaker_calls_total{kind="slow_successful",name="paymentService"} 3.0
```

```yaml
# Alert Prometheus consigliati
groups:
  - name: circuit-breaker
    rules:
      - alert: CircuitBreakerOpen
        expr: resilience4j_circuitbreaker_state{state="open"} == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker {{ $labels.name }} è OPEN"
          description: "Il circuit breaker {{ $labels.name }} è aperto da > 1 minuto"

      - alert: CircuitBreakerHighFailureRate
        expr: resilience4j_circuitbreaker_failure_rate > 30
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High failure rate su {{ $labels.name }}: {{ $value }}%"
```

#### Ascolto di CBStateTransition Events

```java
// CircuitBreakerEventListener.java
@Component
@Slf4j
public class CircuitBreakerEventListener {

    private final CircuitBreakerRegistry registry;
    private final MeterRegistry meterRegistry;

    public CircuitBreakerEventListener(
            CircuitBreakerRegistry registry,
            MeterRegistry meterRegistry) {
        this.registry = registry;
        this.meterRegistry = meterRegistry;
    }

    @PostConstruct
    public void registerListeners() {
        // Registra listener per ogni CB nel registry
        registry.getAllCircuitBreakers().forEach(this::addEventListeners);
        // Registra anche per CB creati in futuro
        registry.getEventPublisher()
            .onEntryAdded(event -> addEventListeners(event.getAddedEntry()));
    }

    private void addEventListeners(CircuitBreaker cb) {
        cb.getEventPublisher()
            .onStateTransition(event -> {
                log.warn("CircuitBreaker '{}': {} → {}",
                    event.getCircuitBreakerName(),
                    event.getStateTransition().getFromState(),
                    event.getStateTransition().getToState());

                // Pubblica metrica custom su ogni transizione di stato
                meterRegistry.counter("cb.state.transition",
                    "name", event.getCircuitBreakerName(),
                    "from", event.getStateTransition().getFromState().name(),
                    "to", event.getStateTransition().getToState().name()
                ).increment();

                // Alert specifico quando il circuito si apre
                if (event.getStateTransition().getToState() == CircuitBreaker.State.OPEN) {
                    notifyOncall(event.getCircuitBreakerName());
                }
            })
            .onCallNotPermitted(event ->
                log.debug("CB '{}': call not permitted (circuit OPEN)",
                    event.getCircuitBreakerName()))
            .onError(event ->
                log.debug("CB '{}': recorded failure — {}",
                    event.getCircuitBreakerName(),
                    event.getThrowable().getClass().getSimpleName()));
    }

    private void notifyOncall(String cbName) {
        // Integrazione con PagerDuty/Slack/etc.
        log.error("ONCALL ALERT: CircuitBreaker '{}' has OPENED — downstream may be down", cbName);
    }
}
```

---

### .NET — Polly v8 con ResiliencePipeline

Polly v8 ha introdotto l'API `ResiliencePipeline` (fluent builder), sostituendo la vecchia API `Policy.Handle<>`. È la versione raccomandata per .NET 8+.

#### Dipendenza NuGet

```xml
<!-- .csproj -->
<PackageReference Include="Microsoft.Extensions.Http.Resilience" Version="8.10.0" />
<!-- oppure direttamente Polly -->
<PackageReference Include="Polly.Extensions" Version="8.5.0" />
```

#### Configurazione con Dependency Injection

```csharp
// Program.cs / Startup.cs
builder.Services.AddResiliencePipeline("payment-pipeline", static builder =>
{
    // Ordine: dal più esterno al più interno
    builder
        // 1. Fallback (outermost): intercetta tutti i fallimenti finali
        .AddFallback(new FallbackStrategyOptions<PaymentResult>
        {
            FallbackAction = static args =>
            {
                var logger = args.Context.ServiceProvider
                    .GetRequiredService<ILogger<PaymentClient>>();
                logger.LogWarning("Payment fallback activated. Outcome: {Outcome}",
                    args.Outcome.Exception?.Message ?? args.Outcome.Result?.ToString());

                return ValueTask.FromResult(Outcome.FromResult(
                    PaymentResult.Pending("Service temporarily unavailable")));
            },
            ShouldHandle = static args =>
                ValueTask.FromResult(args.Outcome.Exception is not null)
        })

        // 2. Circuit Breaker
        .AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            SamplingDuration = TimeSpan.FromSeconds(30),
            MinimumThroughput = 5,              // Min chiamate per valutare
            FailureRatio = 0.5,                 // 50% errori → OPEN
            BreakDuration = TimeSpan.FromSeconds(30),
            ShouldHandle = static args => ValueTask.FromResult(
                args.Outcome.Exception is HttpRequestException or
                TimeoutRejectedException or TaskCanceledException),
            OnOpened = static args =>
            {
                Console.Error.WriteLine(
                    $"[CB] Circuit OPENED. Break duration: {args.BreakDuration}");
                return ValueTask.CompletedTask;
            },
            OnClosed = static args =>
            {
                Console.Error.WriteLine("[CB] Circuit CLOSED — service recovered");
                return ValueTask.CompletedTask;
            },
            OnHalfOpened = static args =>
            {
                Console.Error.WriteLine("[CB] Circuit HALF-OPEN — probing...");
                return ValueTask.CompletedTask;
            }
        })

        // 3. Timeout per singolo tentativo
        .AddTimeout(new TimeoutStrategyOptions
        {
            Timeout = TimeSpan.FromSeconds(3),
            OnTimeout = static args =>
            {
                Console.Error.WriteLine(
                    $"[Timeout] Call timed out after {args.Timeout.TotalSeconds}s");
                return ValueTask.CompletedTask;
            }
        })

        // 4. Retry con exponential backoff + jitter (innermost)
        .AddRetry(new RetryStrategyOptions
        {
            MaxRetryAttempts = 3,
            Delay = TimeSpan.FromMilliseconds(200),
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,               // jitter automatico
            MaxDelay = TimeSpan.FromSeconds(10),
            ShouldHandle = static args => ValueTask.FromResult(
                args.Outcome.Exception is HttpRequestException { StatusCode: >= HttpStatusCode.InternalServerError }
                or TimeoutRejectedException
                or HttpRequestException { StatusCode: HttpStatusCode.ServiceUnavailable }),
            OnRetry = static args =>
            {
                Console.Error.WriteLine(
                    $"[Retry] Attempt {args.AttemptNumber + 1}. Delay: {args.RetryDelay.TotalMilliseconds}ms. " +
                    $"Reason: {args.Outcome.Exception?.Message}");
                return ValueTask.CompletedTask;
            }
        });
});
```

#### Utilizzo del Pipeline

```csharp
// PaymentClient.cs
public class PaymentClient
{
    private readonly ResiliencePipeline<PaymentResult> _pipeline;
    private readonly HttpClient _httpClient;
    private readonly ILogger<PaymentClient> _logger;

    public PaymentClient(
        ResiliencePipelineProvider<string> pipelineProvider,
        HttpClient httpClient,
        ILogger<PaymentClient> logger)
    {
        _pipeline = pipelineProvider.GetPipeline<PaymentResult>("payment-pipeline");
        _httpClient = httpClient;
        _logger = logger;
    }

    public async Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request,
        CancellationToken cancellationToken = default)
    {
        var context = ResilienceContextPool.Shared.Get(cancellationToken);
        context.Properties.Set(new ResiliencePropertyKey<string>("orderId"), request.OrderId);

        try
        {
            return await _pipeline.ExecuteAsync(
                async ctx =>
                {
                    var response = await _httpClient.PostAsJsonAsync(
                        "/api/v1/payments", request, ctx.CancellationToken);
                    response.EnsureSuccessStatusCode();
                    return await response.Content.ReadFromJsonAsync<PaymentResult>(
                        cancellationToken: ctx.CancellationToken)
                        ?? throw new InvalidOperationException("Null response from payment service");
                },
                context);
        }
        finally
        {
            ResilienceContextPool.Shared.Return(context);
        }
    }
}
```

#### Configurazione per HttpClient Factory (Approccio Consigliato)

```csharp
// Program.cs — integrazione con IHttpClientFactory
builder.Services.AddHttpClient("PaymentService", client =>
{
    client.BaseAddress = new Uri("http://payment-service");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
})
.AddResilienceHandler("payment-resilience", static builder =>
{
    // Pipeline inline per HttpClient
    builder.AddStandardResilienceHandler(options =>
    {
        options.Retry.MaxRetryAttempts = 3;
        options.Retry.UseJitter = true;
        options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(30);
        options.CircuitBreaker.FailureRatio = 0.5;
        options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(15);
        options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(4);
    });
});
```

---

### Go — sony/gobreaker

`sony/gobreaker` è la libreria circuit breaker più diffusa in Go: minimalista, idiomatica, senza dipendenze esterne.

#### Installazione

```bash
go get github.com/sony/gobreaker/v2@latest
```

#### Configurazione e Utilizzo Base

```go
// resilience/circuit_breaker.go
package resilience

import (
    "context"
    "errors"
    "time"

    "github.com/sony/gobreaker/v2"
)

var ErrCircuitOpen = errors.New("circuit breaker is open")

// NewPaymentCB crea un circuit breaker configurato per il payment service.
func NewPaymentCB() *gobreaker.CircuitBreaker[[]byte] {
    settings := gobreaker.Settings{
        Name: "payment-service",

        // Finestra di valutazione: ultimi 30 secondi
        Interval: 30 * time.Second,

        // Timeout in stato OPEN prima di passare a HALF-OPEN
        Timeout: 30 * time.Second,

        // Condizione di apertura del circuito
        ReadyToTrip: func(counts gobreaker.Counts) bool {
            // Apri se: almeno 5 richieste E failure rate >= 50%
            if counts.Requests < 5 {
                return false
            }
            failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
            return failureRatio >= 0.5
        },

        // Cosa considerare un errore (default: qualsiasi error non-nil)
        IsSuccessful: func(err error) bool {
            // Non contare come failure gli errori di validazione client
            var validationErr *ValidationError
            if errors.As(err, &validationErr) {
                return true // non è un failure del server
            }
            return err == nil
        },

        // Callback di transizione stati
        OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
            log.Printf("[CB] %s: %s → %s", name, from, to)

            // Integra con il tuo metrics system
            cbStateGauge.WithLabelValues(name, to.String()).Set(1)
            cbStateGauge.WithLabelValues(name, from.String()).Set(0)
        },

        // Max richieste in HALF-OPEN (default: 1)
        MaxRequests: 3,
    }

    return gobreaker.NewCircuitBreaker[[]byte](settings)
}
```

#### Client HTTP con Circuit Breaker

```go
// payment/client.go
package payment

import (
    "context"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "time"

    "github.com/sony/gobreaker/v2"
)

type Client struct {
    cb         *gobreaker.CircuitBreaker[[]byte]
    httpClient *http.Client
    baseURL    string
}

func NewClient(baseURL string) *Client {
    return &Client{
        cb:      resilience.NewPaymentCB(),
        baseURL: baseURL,
        httpClient: &http.Client{
            Timeout: 5 * time.Second, // timeout complessivo per il client
        },
    }
}

func (c *Client) ProcessPayment(ctx context.Context, req PaymentRequest) (*PaymentResult, error) {
    // Il CB wrappa la chiamata HTTP
    body, err := c.cb.Execute(func() ([]byte, error) {
        return c.doHTTPCall(ctx, req)
    })

    if err != nil {
        // Distingui tra circuito aperto e errore reale
        if errors.Is(err, gobreaker.ErrOpenState) {
            return nil, fmt.Errorf("%w: payment service circuit is open", ErrCircuitOpen)
        }
        if errors.Is(err, gobreaker.ErrTooManyRequests) {
            return nil, fmt.Errorf("circuit half-open: too many concurrent probes")
        }
        return nil, fmt.Errorf("payment call failed: %w", err)
    }

    var result PaymentResult
    if err := json.Unmarshal(body, &result); err != nil {
        return nil, fmt.Errorf("failed to decode payment response: %w", err)
    }
    return &result, nil
}

func (c *Client) doHTTPCall(ctx context.Context, req PaymentRequest) ([]byte, error) {
    // Aggiungi deadline dal context (propagazione upstream)
    httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
        c.baseURL+"/api/v1/payments", encodeJSON(req))
    if err != nil {
        return nil, err
    }
    httpReq.Header.Set("Content-Type", "application/json")

    resp, err := c.httpClient.Do(httpReq)
    if err != nil {
        return nil, err // errore di rete → il CB lo conta come failure
    }
    defer resp.Body.Close()

    // Errori 5xx → failure per il CB
    if resp.StatusCode >= 500 {
        return nil, fmt.Errorf("server error: HTTP %d", resp.StatusCode)
    }
    // Errori 4xx → non sono failure del server (non aprono il CB)
    if resp.StatusCode >= 400 {
        body, _ := io.ReadAll(resp.Body)
        return nil, &ValidationError{Code: resp.StatusCode, Body: string(body)}
    }

    return io.ReadAll(resp.Body)
}
```

#### Test del Circuit Breaker con Clock Stub

`gobreaker/v2` supporta l'iniezione di un clock personalizzato per testare le transizioni di stato senza aspettare:

```go
// payment/client_test.go
package payment_test

import (
    "context"
    "net/http"
    "net/http/httptest"
    "testing"
    "time"

    "github.com/sony/gobreaker/v2"
)

// fakeClock permette di avanzare il tempo manualmente nei test
type fakeClock struct {
    current time.Time
}

func (f *fakeClock) Now() time.Time        { return f.current }
func (f *fakeClock) Since(t time.Time) time.Duration { return f.current.Sub(t) }
func (f *fakeClock) advance(d time.Duration) { f.current = f.current.Add(d) }

func TestCircuitBreakerOpensAfterFailures(t *testing.T) {
    clock := &fakeClock{current: time.Now()}

    // Server che restituisce sempre 500
    failingServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusInternalServerError)
    }))
    defer failingServer.Close()

    settings := gobreaker.Settings{
        Name:    "test-cb",
        Timeout: 30 * time.Second,
        ReadyToTrip: func(counts gobreaker.Counts) bool {
            return counts.Requests >= 5 &&
                float64(counts.TotalFailures)/float64(counts.Requests) >= 0.5
        },
        Clock: clock, // inietta il clock finto
    }
    cb := gobreaker.NewCircuitBreaker[[]byte](settings)

    client := NewClientWithCB(failingServer.URL, cb)

    // Esegui 5 chiamate che falliranno → circuito deve aprirsi
    for i := 0; i < 5; i++ {
        _, _ = client.ProcessPayment(context.Background(), PaymentRequest{Amount: 100})
    }

    if cb.State() != gobreaker.StateOpen {
        t.Fatalf("expected circuit to be OPEN, got %s", cb.State())
    }

    // Avanza il clock oltre il timeout → deve passare a HALF-OPEN
    clock.advance(31 * time.Second)

    // La prossima chiamata entra in HALF-OPEN e triggera il probe
    recoveredServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
        w.Write([]byte(`{"status":"ok","id":"123"}`))
    }))
    defer recoveredServer.Close()

    client.SetBaseURL(recoveredServer.URL)
    _, err := client.ProcessPayment(context.Background(), PaymentRequest{Amount: 100})
    if err != nil {
        t.Fatalf("expected success in HALF-OPEN state, got: %v", err)
    }

    if cb.State() != gobreaker.StateClosed {
        t.Fatalf("expected circuit to be CLOSED after successful probe, got %s", cb.State())
    }
}
```

---

### Testing con Testcontainers + Toxiproxy

Toxiproxy è un proxy TCP che simula condizioni di rete degradate: latenza, packet loss, connessioni lente, disconnessioni. Con Testcontainers puoi eseguire questi test direttamente negli integration test senza infrastruttura esterna.

```xml
<!-- pom.xml — Java -->
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>toxiproxy</artifactId>
    <version>1.20.4</version>
    <scope>test</scope>
</dependency>
```

```java
// PaymentClientResilienceTest.java
@SpringBootTest
@Testcontainers
class PaymentClientResilienceTest {

    @Container
    static ToxiproxyContainer toxiproxy = new ToxiproxyContainer(
        DockerImageName.parse("ghcr.io/shopify/toxiproxy:2.11.0"))
        .withNetwork(Network.newNetwork());

    @Container
    static GenericContainer<?> paymentServiceMock = new GenericContainer<>(
        DockerImageName.parse("mockserver/mockserver:5.15.0"))
        .withNetwork(toxiproxy.getNetwork())
        .withNetworkAliases("payment-service")
        .withExposedPorts(1080);

    static ToxiproxyClient toxiproxyClient;
    static Proxy paymentProxy;

    @BeforeAll
    static void setupProxy() throws Exception {
        toxiproxyClient = new ToxiproxyClient(
            toxiproxy.getHost(), toxiproxy.getControlPort());

        // Crea un proxy che passa il traffico verso il mock server
        paymentProxy = toxiproxyClient.createProxy(
            "payment",
            "0.0.0.0:8666",
            "payment-service:1080");
    }

    @Test
    void circuitBreaker_shouldOpenAfterSlowResponses() throws Exception {
        // Aggiungi latency toxic: ogni risposta ritarda di 3 secondi
        // (sopra il slow_call_duration_threshold di 2s)
        Toxic latency = paymentProxy.toxics()
            .latency("payment-latency", ToxicDirection.DOWNSTREAM, 3000);

        try {
            // Esegui abbastanza chiamate da trigger il slow call threshold
            for (int i = 0; i < 20; i++) {
                paymentClient.processPayment(buildRequest(i));
            }

            // Verifica che il circuito sia aperto
            CircuitBreaker cb = circuitBreakerRegistry.circuitBreaker("paymentService");
            assertThat(cb.getState()).isEqualTo(CircuitBreaker.State.OPEN);

            // Verifica che le successive chiamate falliscano immediatamente (< 100ms)
            long start = System.currentTimeMillis();
            assertThatThrownBy(() -> paymentClient.processPayment(buildRequest(99)))
                .isInstanceOf(CallNotPermittedException.class);
            long elapsed = System.currentTimeMillis() - start;
            assertThat(elapsed).isLessThan(100); // fail fast

        } finally {
            latency.remove(); // ripristina il proxy per altri test
        }
    }

    @Test
    void circuitBreaker_shouldRecoverAfterDownstreamRecovery() throws Exception {
        // Simula servizio down: connessione TCP tagliata
        Toxic connectionDown = paymentProxy.toxics()
            .limitData("payment-down", ToxicDirection.DOWNSTREAM, 0);

        try {
            // Trigger apertura circuito
            for (int i = 0; i < 10; i++) {
                try { paymentClient.processPayment(buildRequest(i)); } catch (Exception ignored) {}
            }
            assertThat(circuitBreakerRegistry.circuitBreaker("paymentService").getState())
                .isEqualTo(CircuitBreaker.State.OPEN);

        } finally {
            connectionDown.remove(); // "ripristina" il servizio downstream
        }

        // Aspetta che il CB passi in HALF-OPEN (wait-duration-in-open-state)
        await().atMost(35, SECONDS).until(() ->
            circuitBreakerRegistry.circuitBreaker("paymentService").getState()
                == CircuitBreaker.State.HALF_OPEN);

        // La prossima chiamata di probe deve avere successo e chiudere il circuito
        PaymentResult result = paymentClient.processPayment(buildRequest(200));
        assertThat(result.getStatus()).isEqualTo("ok");
        assertThat(circuitBreakerRegistry.circuitBreaker("paymentService").getState())
            .isEqualTo(CircuitBreaker.State.CLOSED);
    }
}
```

```go
// Go — Toxiproxy con Testcontainers
// payment/integration_test.go
func TestCircuitBreakerWithToxiproxy(t *testing.T) {
    ctx := context.Background()

    network, _ := testcontainers.GenericNetwork(ctx, testcontainers.GenericNetworkRequest{
        NetworkRequest: testcontainers.NetworkRequest{Name: "test-net"},
    })
    defer network.Remove(ctx)

    // Avvia mock server (es. mockserver o nginx con fixture)
    mockServer, _ := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
        ContainerRequest: testcontainers.ContainerRequest{
            Image:        "mockserver/mockserver:5.15.0",
            ExposedPorts: []string{"1080/tcp"},
            Networks:     []string{"test-net"},
            NetworkAliases: map[string][]string{"test-net": {"payment-mock"}},
            WaitingFor:   wait.ForHTTP("/mockserver/status").WithPort("1080"),
        },
        Started: true,
    })
    defer mockServer.Terminate(ctx)

    // Avvia Toxiproxy
    toxiContainer, _ := toxiproxy.Run(ctx, "ghcr.io/shopify/toxiproxy:2.11.0",
        testcontainers.WithNetworks([]string{"test-net"},
            map[string][]string{"test-net": {"toxiproxy"}}))
    defer toxiContainer.Terminate(ctx)

    proxyURL, _ := toxiContainer.URI(ctx, "payment", "payment-mock:1080")
    toxiClient := toxiproxy.NewClient(toxiContainer.ControlURI(ctx))
    proxy, _ := toxiClient.CreateProxy("payment", "0.0.0.0:8666", "payment-mock:1080")

    // Test: connessione reset → il CB deve aprirsi
    proxy.AddToxic("reset-conn", "reset_peer", "downstream", 1.0,
        toxiproxy.Attributes{"timeout": 0})

    client := NewClient(proxyURL)
    for i := 0; i < 5; i++ {
        _, _ = client.ProcessPayment(ctx, PaymentRequest{Amount: 100})
    }
    if client.CBState() != "open" {
        t.Fatal("expected circuit to be open after reset_peer toxic")
    }
}
```

---

## Best Practices

!!! tip "Calibra le soglie sul traffico reale"
    Un `minimum-number-of-calls: 20` su un endpoint che riceve 2 chiamate al minuto significa che il CB non scatterà mai. Calibra la sliding window e il minimum in base al traffico osservato, non ai valori di default.

```
Linee guida per la calibrazione:
─────────────────────────────────────────────────────────
sliding_window_size:  ~ 10-20% del traffico in 1 minuto
                      (es. 120 req/min → window = 15-20)

minimum_number_of_calls: 5-10 se traffico alto
                          2-3  se traffico basso

failure_rate_threshold: 50% per servizi non critici
                        30% per servizi critici (pagamenti, auth)

wait_duration_open: P99 tempo di recovery del downstream
                    (solitamente 15-60 secondi)
```

!!! tip "Fallback con graceful degradation, non solo eccezioni"
    Un fallback che lancia un'eccezione è solo un fail fast con più codice. Il valore del fallback è nella degradazione controllata: restituire dati dalla cache, accettare l'operazione e processarla in modo asincrono, o restituire un risultato parziale significativo.

!!! warning "Non usare circuit breaker per errori 4xx"
    Gli errori 4xx (400, 401, 403, 404, 409, 422) sono errori del client, non del server. Se il circuito si apre per questi errori, maschera un bug nell'applicazione chiamante. Configura sempre `ignore-exceptions` o `IsSuccessful` per escluderli.

```java
// SBAGLIATO: apre il circuito su 404 — il 404 è un problema del chiamante
record-exceptions:
  - java.lang.Exception  # troppo generico

// CORRETTO: registra solo errori di infrastruttura
record-exceptions:
  - java.io.IOException
  - java.net.SocketTimeoutException
ignore-exceptions:
  - org.springframework.web.client.HttpClientErrorException  # tutti i 4xx
```

!!! warning "Thread safety in Go con gobreaker"
    `gobreaker.CircuitBreaker` è thread-safe. Non creare un CB per ogni goroutine — crea un'istanza condivisa (a livello di client) e condividila tra le goroutine.

### Checklist Pre-Deploy

```
Circuit Breaker — Checklist
  □ failure-rate-threshold calibrato sul traffico atteso
  □ ignore-exceptions configurato per escludere errori 4xx
  □ Fallback implementato con logica di business reale
  □ Metriche Prometheus/Micrometer esposte e verificate
  □ Alert su circuit-breaker-open con runbook linkato
  □ Test di integrazione con Toxiproxy per verificare apertura/chiusura
  □ Coordinamento con service mesh: nessuna duplicazione non intenzionale di retry
```

---

## Troubleshooting

### Problema: Il circuit breaker non scatta mai nonostante molti errori

**Sintomo:** Il downstream è chiaramente in errore, ma `resilience4j_circuitbreaker_state` rimane `closed` e `failure_rate` è basso o 0.

**Causa 1 — Le eccezioni non sono registrate:**
```bash
# Verifica quali eccezioni vengono registrate
curl -s http://localhost:8080/actuator/prometheus | grep resilience4j_circuitbreaker_calls
# kind="failed" deve incrementare; se rimane 0 le eccezioni vengono ignorate
```
```yaml
# Fix: aggiungi le eccezioni concrete al record-exceptions
resilience4j.circuitbreaker.instances.myService:
  record-exceptions:
    - java.lang.Exception  # cattura tutto come punto di partenza, poi affina
```

**Causa 2 — minimum-number-of-calls troppo alto per il traffico:**
```bash
# Controlla il numero di chiamate nella window
curl -s http://localhost:8080/actuator/prometheus | grep buffered_calls
# Se buffered_calls < minimum-number-of-calls, il CB non valuta ancora
```
```yaml
# Fix: riduci il minimum
resilience4j.circuitbreaker.instances.myService:
  minimum-number-of-calls: 3  # da 20 a 3 su traffico basso
  sliding-window-size: 5
```

---

### Problema: Circuit breaker si apre e non si richiude mai

**Sintomo:** Il CB passa in HALF-OPEN, le chiamate di probe vengono eseguite ma il CB torna subito OPEN.

**Causa 1 — Le probe calls falliscono per errori diversi dal motivo originale (es. auth scaduta durante il downtime):**
```java
// Controlla gli eventi del CB per vedere il tipo di errore nelle probe calls
cb.getEventPublisher().onError(event ->
    log.error("Probe call failed: {}", event.getThrowable().getClass().getName()));
// Se vedi eccezioni di autenticazione: il token è scaduto — rinnovalo prima di riaprire
```

**Causa 2 — permitted-number-of-calls-in-half-open troppo basso:**
```yaml
# 1 singola probe call non è abbastanza per stabilire il recovery
resilience4j.circuitbreaker.instances.myService:
  permitted-number-of-calls-in-half-open-state: 5  # da 1 a 5
  failure-rate-threshold: 50  # accetta fino al 50% di failure nelle probe
```

---

### Problema: gobreaker non transita mai in HALF-OPEN

**Sintomo:** Il CB è OPEN ma anche avanzando il tempo il CB rimane OPEN.

**Causa:** `gobreaker.Execute()` non viene chiamato dopo il `Timeout`. La transizione a HALF-OPEN in gobreaker non è automatica: avviene solo quando viene eseguita una nuova chiamata *dopo* che il timeout è trascorso.

```go
// SBAGLIATO: aspettarsi la transizione automatica
cb.State() // → StateOpen (corretto)
time.Sleep(31 * time.Second) // aspetta il timeout
cb.State() // → StateOpen ancora! NON transita senza una chiamata

// CORRETTO: la transizione avviene sulla prossima chiamata
time.Sleep(31 * time.Second)
cb.Execute(func() ([]byte, error) { ... }) // ora transita in HALF-OPEN
cb.State() // → StateHalfOpen
```

---

### Problema: Doppio conteggio errori (app + mesh)

**Sintomo:** Il CB applicativo si apre molto più velocemente del previsto. Le metriche mostrano failure rate elevato anche quando poche chiamate reali falliscono.

**Causa:** Il service mesh esegue retry (es. Istio: `attempts: 3`). Ogni tentativo che fallisce viene registrato come failure nel CB applicativo. 3 retry mesh × 3 retry app = fino a 9 tentativi registrati per una singola operazione.

**Soluzione:**
```yaml
# Opzione A: Disabilita i retry nel service mesh per questo servizio
# VirtualService Istio:
http:
  - retries:
      attempts: 0  # nessun retry dal mesh su questo VirtualService

# Opzione B: Disabilita il retry applicativo e affidati solo al mesh
resilience4j.retry.instances.myService:
  max-attempts: 1  # nessun retry applicativo
```

---

## Relazioni

??? info "Dev / Resilienza — Panoramica pattern (timeout, retry, bulkhead)"
    Questo file si concentra sull'implementazione specifica del circuit breaker. Per la visione d'insieme di tutti i pattern di resilienza (timeout, retry con backoff, bulkhead, rate limiter) e la loro composizione corretta, vedi il documento di overview. → [Resilienza](../_index.md)

??? info "Networking / Service Mesh / Istio — Circuit breaker infrastrutturale"
    Istio implementa il circuit breaker tramite `DestinationRule.outlierDetection`. A differenza di quello applicativo, opera a livello di host e non di singola operazione. I due livelli sono complementari ma vanno coordinati per evitare amplificazione dei retry. → [Istio](../../../networking/service-mesh/istio.md)

??? info "Dev / Linguaggi / Java Spring Boot — Integrazione con Spring ecosystem"
    Configurazione di Resilience4j in contesti Spring Boot 3.x: Actuator health indicators, Micrometer auto-configuration, testing con `@SpringBootTest` e Testcontainers. → [Java Spring Boot](../linguaggi/java-spring-boot.md)

??? info "Dev / Linguaggi / .NET — Polly e HttpClientFactory"
    L'integrazione di Polly v8 con `IHttpClientFactory` è il pattern consigliato in .NET 8+ per applicare le policy di resilienza a tutti gli `HttpClient` del servizio senza duplicare configurazione. → [.NET](../linguaggi/dotnet.md)

??? info "Dev / Linguaggi / Go — Context e cancellation"
    In Go la corretta propagazione del `context` è critica per il funzionamento dei timeout e della cancellation in combinazione con il circuit breaker. → [Go](../linguaggi/go.md)

---

## Riferimenti

- [Resilience4j — CircuitBreaker Documentation](https://resilience4j.readme.io/docs/circuitbreaker) — Configurazione completa e metriche
- [Polly v8 — Circuit Breaker Strategy](https://www.pollydocs.org/strategies/circuit-breaker.html) — Documentazione ufficiale Polly .NET
- [sony/gobreaker](https://github.com/sony/gobreaker) — Repository GitHub, README dettagliato
- [Testcontainers — Toxiproxy Module](https://java.testcontainers.org/modules/toxiproxy/) — Guida all'uso nei test JVM
- [Toxiproxy](https://github.com/Shopify/toxiproxy) — Proxying TCP per chaos testing
- [Release It! — Michael Nygard](https://pragprog.com/titles/mnee2/release-it-second-edition/) — Capitolo sul Circuit Breaker pattern (testo fondamentale)
- [Microsoft — Polly e HttpClientFactory](https://learn.microsoft.com/en-us/dotnet/core/resilience/) — Guida Microsoft alla resilienza .NET
- [Micrometer — Resilience4j Integration](https://micrometer.io/docs/ref/resilience4j) — Metriche e osservabilità
