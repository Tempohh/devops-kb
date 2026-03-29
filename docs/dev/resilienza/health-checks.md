---
title: "Health Checks"
slug: health-checks
category: dev
tags: [health-checks, kubernetes, probes, liveness, readiness, startup, spring-boot, dotnet, go, actuator]
search_keywords: [health check, health probe, liveness probe, readiness probe, startup probe, kubernetes probes, k8s probes, actuator health, spring boot actuator, /actuator/health, HealthIndicator, IHealthCheck, AddHealthChecks, MapHealthChecks, AddDbContextCheck, AddRedis, /healthz, /readyz, health endpoint, probe configuration, pod lifecycle, container health, livello applicativo probes, sonde kubernetes, sonde salute, health status, health group, probes group, custom health indicator, custom health check, db health check, kafka health check, redis health check, readiness gate, pod readiness, container restart, liveness restart, CrashLoopBackOff, startup probe grace period, initialDelaySeconds, periodSeconds, failureThreshold, successThreshold, timeoutSeconds, health check pattern, graceful shutdown health]
parent: dev/resilienza/_index
related: [containers/kubernetes/workloads, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go, dev/resilienza/_index]
official_docs: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Health Checks

## Panoramica

Gli health check sono endpoint HTTP (o TCP/exec) che Kubernetes interroga periodicamente per capire se un pod è vivo, pronto a ricevere traffico, o ancora in fase di avvio. Sbagliare la semantica delle probe — o implementarle in modo superficiale — è una delle cause più comuni di restart a cascata, CrashLoopBackOff, e interruzioni di servizio durante i deploy.

Kubernetes distingue tre tipi di probe con semantiche ben distinte:

| Probe | Failing action | Scopo |
|---|---|---|
| **liveness** | Restart del container | Il processo è bloccato o in uno stato irrecuperabile |
| **readiness** | Rimuove il pod dall'endpoint (no traffico) | Il pod non è pronto a servire richieste (es. dipendenza down) |
| **startup** | Restart del container (se non passa entro il timeout) | Sostituisce `initialDelaySeconds` per app a startup lento |

La regola fondamentale: **liveness controlla solo il processo stesso**, readiness controlla le dipendenze esterne. Confondere i due genera restart non necessari che amplificano i guasti invece di contenerli.

!!! warning "Anti-pattern critico"
    Una liveness probe che chiama il database provoca restart a cascata: se il DB è down, tutti i pod vengono riavviati contemporaneamente, aggravando la situazione invece di gestirla in graceful degradation. La liveness probe deve fallire solo se il processo stesso è irrecuperabile.

---

## Concetti Chiave

### Le tre probe e le loro responsabilità

```
STARTUP PROBE
  Attiva: durante l'avvio del container (finché non passa)
  Quando fallisce: restart del container
  Scopo: rimpiazza initialDelaySeconds per app con startup variabile
  Esempio: attendi che Spring Boot completi la startup (10-120s)
  Quando è completa: disabilitata; liveness e readiness prendono il controllo

LIVENESS PROBE
  Attiva: continuamente durante tutta la vita del pod
  Quando fallisce: restart del container (kubelet uccide e ricrea il container)
  Scopo: rileva deadlock, memory leak terminali, stati irrecuperabili
  Regola d'oro: verifica solo lo stato interno del processo, MAI dipendenze esterne

READINESS PROBE
  Attiva: continuamente durante tutta la vita del pod
  Quando fallisce: il pod viene rimosso dall'Endpoints del Service (niente traffico)
  Scopo: segnala che il pod non può servire traffico (dipendenza down, warmup, etc.)
  Il pod NON viene riavviato — attende che la probe torni verde
```

### Parametri di configurazione comuni

```yaml
# Parametri condivisi tra tutte le probe
livenessProbe:
  httpGet:
    path: /livez           # endpoint da interrogare
    port: 8080
  initialDelaySeconds: 10  # attendi N secondi prima della prima probe
  periodSeconds: 15        # interroga ogni N secondi
  timeoutSeconds: 5        # timeout per la risposta
  successThreshold: 1      # N successi consecutivi per passare a healthy
  failureThreshold: 3      # N fallimenti consecutivi per passare a unhealthy
                           # → restart dopo 3 × 15 = 45 secondi di errori
```

!!! tip "Threshold conservative per liveness"
    Per la liveness, usa `failureThreshold` almeno 3 e `periodSeconds` 15-30. Questo dà al pod 45-90 secondi di tempo per recuperare prima di essere riavviato. Threshold troppo basse causano restart prematuri su spike temporanei di carico.

---

## Architettura / Come Funziona

### Flusso del ciclo di vita del pod

```
Container avviato
      │
      ▼
┌─────────────────────────────────────────────┐
│  STARTUP PROBE (se configurata)             │
│  Interroga ogni periodSeconds               │
│  ┌── passa → disabilita startup probe       │
│  └── fallisce per failureThreshold volte    │
│       → restart container                  │
└─────────────────┬───────────────────────────┘
                  │ (startup completata)
                  ▼
┌─────────────────────────────────────────────┐
│  LIVENESS + READINESS (parallele, continue) │
│                                             │
│  Liveness:                                  │
│  ┌── OK → container rimane in vita          │
│  └── fail N volte → restart container       │
│                                             │
│  Readiness:                                 │
│  ┌── OK → pod nel pool Endpoints del Service│
│  └── fail → rimosso da Endpoints (no traffico)
│             (pod vivo, solo non raggiungibile)
└─────────────────────────────────────────────┘
```

### Separazione degli endpoint per Kubernetes

```
/livez  →  liveness   (controlla: processo vivo, thread pool non saturato)
/readyz →  readiness  (controlla: DB, cache, broker, dipendenze critiche)
/health →  combined   (per monitoring esterno, non per K8s probes)

Spring Boot 2.3+ crea automaticamente:
  /actuator/health/liveness   → gruppo "liveness"
  /actuator/health/readiness  → gruppo "readiness"
```

---

## Configurazione & Pratica

### Spring Boot — Actuator Health con gruppi K8s

Spring Boot 2.3+ introduce il supporto nativo per liveness e readiness come gruppi separati di `HealthIndicator`.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

```yaml
# application.yml
management:
  endpoint:
    health:
      probes:
        enabled: true               # abilita /actuator/health/liveness e /readiness
      show-details: always          # mostra dettagli (utile per debug)
      show-components: always
      group:
        liveness:
          include: livenessState    # solo lo stato interno del processo
        readiness:
          include: >-
            readinessState,         # stato di readiness del framework
            db,                     # DataSource health
            redis,                  # Redis health
            kafka                   # Kafka health
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus

  # Metriche per alerting
  metrics:
    tags:
      application: ${spring.application.name}
```

Quando l'applicazione gira su Kubernetes, Spring Boot rileva automaticamente l'ambiente e imposta i gruppi. Per ambienti non-K8s, forzare con:

```yaml
# application.yml — forzare la modalità K8s
spring:
  application:
    name: my-service
management:
  health:
    livenessstate:
      enabled: true
    readinessstate:
      enabled: true
```

### Spring Boot — HealthIndicator Custom

```java
// DatabaseHealthIndicator.java
// Controlla che il pool di connessioni abbia connessioni disponibili
@Component
@ConditionalOnProperty(name = "management.health.db.enabled", matchIfMissing = true)
public class DatabaseHealthIndicator implements HealthIndicator {

    private final DataSource dataSource;

    public DatabaseHealthIndicator(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public Health health() {
        try (Connection conn = dataSource.getConnection()) {
            // Esegui una query leggera per verificare la connettività
            boolean valid = conn.isValid(2); // timeout 2 secondi
            if (!valid) {
                return Health.down()
                    .withDetail("error", "Connection not valid")
                    .build();
            }
            // Includi informazioni utili per il debugging
            DatabaseMetaData meta = conn.getMetaData();
            return Health.up()
                .withDetail("database", meta.getDatabaseProductName())
                .withDetail("version", meta.getDatabaseProductVersion())
                .build();
        } catch (Exception e) {
            return Health.down()
                .withDetail("error", e.getMessage())
                .withException(e)
                .build();
        }
    }
}
```

```java
// KafkaHealthIndicator.java
// Controlla che il producer Kafka possa raggiungere il broker
@Component
public class KafkaHealthIndicator implements HealthIndicator {

    private final KafkaTemplate<String, String> kafkaTemplate;

    public KafkaHealthIndicator(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @Override
    public Health health() {
        try {
            // List topics è una chiamata leggera che verifica la connettività al broker
            Map<String, Object> producerMetrics = kafkaTemplate
                .metrics()
                .entrySet()
                .stream()
                .filter(e -> e.getKey().name().equals("connection-count"))
                .collect(Collectors.toMap(
                    e -> e.getKey().name(),
                    e -> e.getValue().metricValue()
                ));

            double connectionCount = (double) producerMetrics
                .getOrDefault("connection-count", 0.0);

            if (connectionCount == 0) {
                return Health.down()
                    .withDetail("reason", "No active Kafka connections")
                    .build();
            }
            return Health.up()
                .withDetail("connections", (int) connectionCount)
                .build();
        } catch (Exception e) {
            return Health.down()
                .withDetail("error", e.getMessage())
                .build();
        }
    }
}
```

```java
// RedisHealthIndicator.java
// Controlla la connettività Redis con PING
@Component
public class RedisHealthIndicator implements HealthIndicator {

    private final RedisTemplate<String, String> redisTemplate;

    public RedisHealthIndicator(RedisTemplate<String, String> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    public Health health() {
        try {
            String pong = redisTemplate.execute(RedisServerCommands::ping);
            if ("PONG".equalsIgnoreCase(pong)) {
                return Health.up()
                    .withDetail("ping", "PONG")
                    .build();
            }
            return Health.down()
                .withDetail("ping", pong)
                .build();
        } catch (Exception e) {
            return Health.down()
                .withDetail("error", e.getMessage())
                .build();
        }
    }
}
```

### Kubernetes manifest — probe su Spring Boot

```yaml
# deployment.yaml — Spring Boot con probe corrette
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
  namespace: production
spec:
  template:
    spec:
      containers:
        - name: my-service
          image: my-service:1.0.0
          ports:
            - containerPort: 8080

          # Startup probe: sostituisce initialDelaySeconds
          # Dà fino a 120 secondi per completare lo startup
          startupProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8080
            failureThreshold: 24      # 24 × 5s = 120 secondi di grazia
            periodSeconds: 5
            timeoutSeconds: 3

          # Liveness: controlla solo lo stato interno
          # SOLO /liveness, mai /readiness o /health (include dipendenze)
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8080
            initialDelaySeconds: 0    # startup probe gestisce il delay
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3       # restart dopo 60s di problemi
            successThreshold: 1

          # Readiness: controlla DB, Redis, Kafka etc.
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8080
            initialDelaySeconds: 0
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
            successThreshold: 1

          # Risorse: sempre definite per evitare OOM restart
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
```

### .NET — HealthChecks API

```csharp
// Program.cs — .NET 6+ minimal hosting model
using Microsoft.Extensions.Diagnostics.HealthChecks;

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddHealthChecks()
    // Check DbContext (Entity Framework Core)
    .AddDbContextCheck<AppDbContext>(
        name: "database",
        failureStatus: HealthStatus.Unhealthy,
        tags: new[] { "readiness" }
    )
    // Check Redis
    .AddRedis(
        builder.Configuration.GetConnectionString("Redis")!,
        name: "redis",
        failureStatus: HealthStatus.Degraded,  // Degraded: non blocca readiness
        tags: new[] { "readiness" }
    )
    // Custom health check
    .AddCheck<KafkaHealthCheck>(
        name: "kafka",
        failureStatus: HealthStatus.Unhealthy,
        tags: new[] { "readiness" }
    )
    // Check sempre disponibile per liveness
    .AddCheck("liveness", () => HealthCheckResult.Healthy(), tags: new[] { "liveness" });

var app = builder.Build();

// Endpoint separati per K8s probes
app.MapHealthChecks("/livez", new HealthCheckOptions
{
    // Solo check con tag "liveness"
    Predicate = check => check.Tags.Contains("liveness"),
    ResultStatusCodes =
    {
        [HealthStatus.Healthy] = StatusCodes.Status200OK,
        [HealthStatus.Degraded] = StatusCodes.Status200OK,   // Degraded = OK per liveness
        [HealthStatus.Unhealthy] = StatusCodes.Status503ServiceUnavailable,
    },
});

app.MapHealthChecks("/readyz", new HealthCheckOptions
{
    // Solo check con tag "readiness"
    Predicate = check => check.Tags.Contains("readiness"),
    ResultStatusCodes =
    {
        [HealthStatus.Healthy] = StatusCodes.Status200OK,
        [HealthStatus.Degraded] = StatusCodes.Status200OK,   // tollerato su readiness
        [HealthStatus.Unhealthy] = StatusCodes.Status503ServiceUnavailable,
    },
    // Restituisce JSON dettagliato (utile per debug, proteggere in prod)
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse,
});

// Endpoint aggregato per monitoring esterno
app.MapHealthChecks("/health");

app.Run();
```

```csharp
// KafkaHealthCheck.cs — IHealthCheck custom
public class KafkaHealthCheck : IHealthCheck
{
    private readonly IProducer<string, string> _producer;
    private readonly ILogger<KafkaHealthCheck> _logger;

    public KafkaHealthCheck(
        IProducer<string, string> producer,
        ILogger<KafkaHealthCheck> logger)
    {
        _producer = producer;
        _logger = logger;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            // Verifica metadati del cluster (leggero, non produce messaggi)
            var metadata = _producer.GetMetadata(
                allTopics: false,
                timeout: TimeSpan.FromSeconds(2)
            );

            if (metadata.Brokers.Count == 0)
            {
                return HealthCheckResult.Unhealthy("No Kafka brokers available");
            }

            return HealthCheckResult.Healthy(
                $"Connected to {metadata.Brokers.Count} broker(s)"
            );
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Kafka health check failed");
            return HealthCheckResult.Unhealthy("Kafka unreachable", ex);
        }
    }
}
```

### Go — handler idiomatico con goroutine

In Go il pattern standard prevede due endpoint separati con logica diversa. Il check di readiness è eseguito con timeout esplicito via `context`.

```go
// health/handler.go
package health

import (
    "context"
    "encoding/json"
    "net/http"
    "sync"
    "time"
)

// Checker è l'interfaccia per ogni dependency check
type Checker interface {
    Name() string
    Check(ctx context.Context) error
}

// Handler gestisce /livez e /readyz
type Handler struct {
    readinessCheckers []Checker
}

func NewHandler(checkers ...Checker) *Handler {
    return &Handler{readinessCheckers: checkers}
}

// LivezHandler risponde 200 se il processo è vivo.
// Non controlla dipendenze esterne — solo che il server risponde.
func (h *Handler) LivezHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// ReadyzHandler esegue tutti i check in parallelo con timeout globale.
func (h *Handler) ReadyzHandler(w http.ResponseWriter, r *http.Request) {
    // Timeout totale per tutti i check di readiness
    ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
    defer cancel()

    type checkResult struct {
        name string
        err  error
    }

    results := make(chan checkResult, len(h.readinessCheckers))
    var wg sync.WaitGroup

    for _, checker := range h.readinessCheckers {
        wg.Add(1)
        go func(c Checker) {
            defer wg.Done()
            results <- checkResult{name: c.Name(), err: c.Check(ctx)}
        }(checker)
    }

    // Chiudi il canale quando tutti i goroutine sono terminati
    go func() {
        wg.Wait()
        close(results)
    }()

    status := http.StatusOK
    checks := make(map[string]string)

    for result := range results {
        if result.err != nil {
            checks[result.name] = result.err.Error()
            status = http.StatusServiceUnavailable // 503
        } else {
            checks[result.name] = "ok"
        }
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(map[string]interface{}{
        "status": map[int]string{200: "ok", 503: "not ready"}[status],
        "checks": checks,
    })
}
```

```go
// health/checkers.go — implementazioni per DB, Redis, Kafka
package health

import (
    "context"
    "database/sql"
    "fmt"

    "github.com/go-redis/redis/v8"
)

// DBChecker verifica la connettività al database
type DBChecker struct {
    db *sql.DB
}

func NewDBChecker(db *sql.DB) *DBChecker {
    return &DBChecker{db: db}
}

func (c *DBChecker) Name() string { return "database" }

func (c *DBChecker) Check(ctx context.Context) error {
    return c.db.PingContext(ctx)
}

// RedisChecker verifica la connettività Redis con PING
type RedisChecker struct {
    client *redis.Client
}

func NewRedisChecker(client *redis.Client) *RedisChecker {
    return &RedisChecker{client: client}
}

func (c *RedisChecker) Name() string { return "redis" }

func (c *RedisChecker) Check(ctx context.Context) error {
    result := c.client.Ping(ctx)
    if err := result.Err(); err != nil {
        return fmt.Errorf("redis PING failed: %w", err)
    }
    return nil
}
```

```go
// main.go — registrazione degli handler
func main() {
    db, _ := sql.Open("postgres", os.Getenv("DATABASE_URL"))
    redisClient := redis.NewClient(&redis.Options{Addr: os.Getenv("REDIS_ADDR")})

    healthHandler := health.NewHandler(
        health.NewDBChecker(db),
        health.NewRedisChecker(redisClient),
    )

    mux := http.NewServeMux()
    mux.HandleFunc("/livez", healthHandler.LivezHandler)
    mux.HandleFunc("/readyz", healthHandler.ReadyzHandler)
    mux.HandleFunc("/api/v1/", appHandler)

    http.ListenAndServe(":8080", mux)
}
```

---

## Best Practices

### Separazione delle responsabilità

!!! tip "Regola d'oro: liveness ≠ readiness"
    Ogni check deve rispondere alla domanda giusta:
    - **Liveness:** "Il processo è in uno stato irrecuperabile?" → se NO, ritorna 200
    - **Readiness:** "Il pod può servire traffico adesso?" → controlla dipendenze esterne

```
Cosa includere in LIVENESS:
  ✅ Thread pool / goroutine pool saturo
  ✅ Deadlock rilevato
  ✅ Heap quasi pieno (>95%) senza possibilità di GC
  ✅ Stato interno corrotto irrecuperabile

  ❌ Database unreachable
  ❌ Redis down
  ❌ Kafka broker non raggiungibile
  ❌ Qualsiasi dipendenza esterna

Cosa includere in READINESS:
  ✅ Database reachable con pool di connessioni disponibile
  ✅ Cache Redis raggiungibile (se critica per il business)
  ✅ Message broker raggiungibile (se il servizio ne ha bisogno per operare)
  ✅ Warmup completato (es. cache pre-caricata, modello ML caricato)

  ✅ Va bene includere dipendenze esterne — questo è lo scopo
```

### Sizing dei parametri

```yaml
# Parametri consigliati per servizi Java/Spring Boot
# Startup lento (30-120s di avvio tipico per app enterprise)
startupProbe:
  failureThreshold: 24    # 24 × 5s = 120s di grazia
  periodSeconds: 5

livenessProbe:
  periodSeconds: 20       # non interrogare troppo frequentemente
  timeoutSeconds: 5
  failureThreshold: 3     # restart solo dopo 60s di problemi continui

readinessProbe:
  periodSeconds: 10       # più frequente: vogliamo rilevare recovery velocemente
  timeoutSeconds: 5
  failureThreshold: 3     # rimuovi dal pool dopo 30s

---
# Parametri consigliati per servizi Go/Node (startup veloce)
startupProbe:
  failureThreshold: 6     # 6 × 5s = 30s di grazia
  periodSeconds: 5

livenessProbe:
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3

readinessProbe:
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

!!! warning "Threshold troppo basse = restart a cascata"
    Con `failureThreshold: 1` e `periodSeconds: 5`, un singolo timeout di 5 secondi del database (GC pause, network jitter) porta al restart del pod. Durante un deploy rolling, se i pod restartano durante il check, lo stesso deployment può bloccarsi in un loop.

### Graceful shutdown e readiness

```java
// Spring Boot: segnala not-ready prima di shutdown
// Kubernetes invia SIGTERM → Spring Boot imposta readiness DOWN
// Il pod smette di ricevere nuove richieste
// Le richieste in corso vengono completate (grace period)

// application.yml
server:
  shutdown: graceful           # abilita graceful shutdown
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # attendi max 30s per le richieste in corso
```

```go
// Go: graceful shutdown con segnale OS
func main() {
    srv := &http.Server{Addr: ":8080", Handler: mux}

    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)

    go func() { srv.ListenAndServe() }()

    <-quit // attendi SIGTERM da Kubernetes

    // Prima: imposta readiness probe a DOWN (via flag atomico)
    atomic.StoreInt32(&ready, 0)

    // Poi: attendi il grace period di K8s (terminationGracePeriodSeconds)
    // e completa le richieste in corso
    ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
    defer cancel()
    srv.Shutdown(ctx)
}
```

---

## Troubleshooting

### Problema: Pod in CrashLoopBackOff per liveness probe che chiama il DB

**Sintomo:** Il pod si riavvia ciclicamente. Nei log si vede che l'applicazione stava funzionando correttamente ma è stata uccisa dal kubelet. Il database era temporaneamente irraggiungibile (es. failover RDS, manutenzione).

**Causa:** La liveness probe include un check al database. Quando il DB è down, liveness ritorna 503, il kubelet riavvia il pod, ma alla ripartenza il DB è ancora down, e il ciclo continua.

**Diagnosi:**
```bash
# Controlla gli eventi del pod
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Liveness probe failed"

# Output tipico:
# Warning  Unhealthy  5m  kubelet  Liveness probe failed:
#   HTTP probe failed with statuscode: 503

# Controlla i restart count
kubectl get pods -n <namespace> | grep -E "RESTARTS|my-service"
# my-service-abc123   0/1   CrashLoopBackOff   12   45m
```

**Soluzione:**
```yaml
# application.yml — Spring Boot: rimuovi DB dal gruppo liveness
management:
  health:
    group:
      liveness:
        include: livenessState   # SOLO lo stato del framework, mai DB
      readiness:
        include: readinessState,db,redis,kafka  # dipendenze solo qui
```

```go
// Go: handler liveness senza dipendenze esterne
func (h *Handler) LivezHandler(w http.ResponseWriter, r *http.Request) {
    // Nessuna chiamata a DB, Redis, Kafka, o qualsiasi I/O esterno
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(`{"status":"ok"}`))
}
```

---

### Problema: Pod non riceve traffico dopo il deploy (readiness sempre failing)

**Sintomo:** Il deploy completa, i pod sono Running, ma il Service non instrada traffico. `kubectl get endpoints` mostra l'IP del pod mancante. La readiness probe restituisce 503.

**Causa comune 1:** Il database non è raggiungibile dalla subnet del pod (firewall, Security Group AWS, NetworkPolicy K8s).

**Causa comune 2:** Il `ConnectionString` punta all'ambiente sbagliato (staging vs production).

**Causa comune 3:** Il pod non ha il tempo sufficiente per completare lo startup (manca la startupProbe).

**Diagnosi:**
```bash
# Controlla gli endpoint del service
kubectl get endpoints my-service -n production
# NAME         ENDPOINTS   AGE
# my-service   <none>      5m   ← Pod non pronto

# Verifica manualmente la probe dall'interno del pod
kubectl exec -it <pod-name> -n production -- curl -v http://localhost:8080/readyz

# Controlla i log del pod per capire cosa sta fallendo
kubectl logs <pod-name> -n production --tail=50

# Controlla gli eventi della readiness probe
kubectl describe pod <pod-name> -n production | grep -A 10 "Readiness"
```

**Soluzione:**
```yaml
# Aggiungi startupProbe se manca
startupProbe:
  httpGet:
    path: /readyz
    port: 8080
  failureThreshold: 30      # 30 × 10s = 5 minuti per app molto lente
  periodSeconds: 10

# Riduci il timeout del check se la probe scade prima che il DB risponda
readinessProbe:
  timeoutSeconds: 10        # aumenta se il DB è lento a rispondere durante startup
```

---

### Problema: Readiness probe causa flapping (verde/rosso alternato)

**Sintomo:** Il pod entra ed esce dal pool degli endpoint ripetutamente. Il monitoring mostra spike di 503 durante picchi di traffico.

**Causa:** Il check di readiness chiama il DB con un timeout troppo basso. Durante picchi di carico, il DB risponde più lentamente e la probe scade, rimuovendo il pod dal pool proprio quando c'è più bisogno.

**Diagnosi:**
```bash
# Conta i flap con kubectl events
kubectl get events -n production --field-selector reason=Unhealthy \
  --sort-by='.lastTimestamp' | grep readiness

# Verifica latenza del DB durante picco
# (Prometheus query)
histogram_quantile(0.99,
  rate(db_query_duration_seconds_bucket[5m])
)
```

**Soluzione:**
```yaml
readinessProbe:
  timeoutSeconds: 10        # allineato al P99+buffer della latenza DB
  periodSeconds: 15         # meno frequente per non stressare il DB
  failureThreshold: 2       # tollera 1 fallimento prima di rimuovere

# Oppure: usa un endpoint /readyz separato più leggero
# che non esegue query ma controlla solo se il pool ha connessioni disponibili
```

```java
// Spring Boot: health indicator con timeout esplicito
@Component
public class DatabaseHealthIndicator implements HealthIndicator {

    @Override
    public Health health() {
        try (Connection conn = dataSource.getConnection()) {
            boolean valid = conn.isValid(3); // timeout 3 secondi
            // ...
        } catch (SQLTimeoutException e) {
            // Timeout dal pool: non è un errore fatale, è carico elevato
            return Health.down()
                .withDetail("reason", "Connection pool timeout - high load")
                .build();
        }
    }
}
```

---

### Problema: Startup probe blocca il rolling update

**Sintomo:** Il rolling update si blocca: il nuovo pod rimane in `Pending` o `Init:0/1` per molto tempo. Kubernetes non procede con il drain del pod vecchio.

**Causa:** La startupProbe ha un `failureThreshold × periodSeconds` totale troppo basso rispetto al tempo reale di startup in produzione (es. startup lenta per cold start su DB con molti schemi da caricare).

**Diagnosi:**
```bash
# Misura il tempo di startup reale
kubectl logs <pod-name> -n production | grep -E "Started|started in|Startup"
# Tomcat started in 47.382 seconds

# Il tempo totale della startupProbe deve essere > tempo di startup reale
# Se failureThreshold=12 × periodSeconds=5 = 60s, e lo startup è 47s, c'è poco margine
```

**Soluzione:**
```yaml
# Dai almeno 2× il tempo di startup come budget per la startupProbe
# Se startup tipico = 45s, budget = 90-120s
startupProbe:
  failureThreshold: 24      # 24 × 5s = 120s
  periodSeconds: 5
  timeoutSeconds: 5
  successThreshold: 1       # 1 successo è sufficiente
```

---

## Relazioni

??? info "Dev / Resilienza — Circuit Breaker e tolleranza ai guasti"
    Gli health check si integrano con il circuit breaker: quando la readiness probe rileva che il DB è down, il pod viene rimosso dal pool, ma il circuit breaker applicativo gestisce il fallback per le richieste già in volo verso quel DB. I due meccanismi sono complementari. → [Circuit Breaker e Resilienza](../resilienza/_index.md)

??? info "Containers / Kubernetes / Workloads — Pod lifecycle e deployment strategy"
    La configurazione delle probe influenza direttamente la strategia di rolling update: `maxUnavailable`, `maxSurge`, e `minReadySeconds` lavorano insieme alle readiness probe per garantire che i pod vecchi vengano drenati solo quando i nuovi sono pronti. → [Kubernetes Workloads](../../containers/kubernetes/workloads.md)

??? info "Dev / Linguaggi / Java Spring Boot — Actuator e health endpoints"
    Spring Boot Actuator espone molto più degli health check: metriche Micrometer, info endpoint, env, loggers. La configurazione di `management.endpoint.health` si integra con tutta la suite Actuator. → [Java Spring Boot](../linguaggi/java-spring-boot.md)

??? info "Dev / Linguaggi / .NET — HealthChecks UI e monitoring"
    Il pacchetto `AspNetCore.HealthChecks.UI` aggiunge una dashboard visuale agli health check .NET, utile in ambienti di staging per monitorare lo stato di tutte le dipendenze. → [.NET](../linguaggi/dotnet.md)

??? info "Dev / Linguaggi / Go — HTTP server idiomatico e graceful shutdown"
    Gli handler `/livez` e `/readyz` seguono le stesse convenzioni degli altri handler Go. La gestione dei segnali OS per il graceful shutdown è parte dello stesso pattern. → [Go](../linguaggi/go.md)

---

## Riferimenti

- [Kubernetes Docs: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) — Documentazione ufficiale Kubernetes
- [Spring Boot Docs: Kubernetes Probes](https://docs.spring.io/spring-boot/docs/current/reference/html/actuator.html#actuator.endpoints.kubernetes-probes) — Guida Actuator con K8s
- [Microsoft Docs: Health checks in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/health-checks) — Documentazione .NET ufficiale
- [Learnk8s: Liveness vs Readiness](https://learnk8s.io/production-best-practices#application-development) — Best practice K8s per le probe
- [Google SRE: Health Checking](https://sre.google/sre-book/monitoring-distributed-systems/) — Approccio SRE al monitoring
