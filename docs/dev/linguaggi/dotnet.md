---
title: "ASP.NET Core 8+ per Microservizi"
slug: dotnet
category: dev
tags: [dotnet, aspnet, csharp, kubernetes, microservizi, minimal-api, grpc, aspire, health-checks, di]
search_keywords: [asp.net core, aspnet core 8, dotnet 8, dotnet 9, c#, csharp, minimal api, controller pattern, dependency injection, di lifetime, singleton, scoped, transient, ihostedservice, backgroundservice, worker service, dotnet aspire, aspire, orchestrazione locale, iconfiguration, appsettings, configurazione kubernetes, configmap dotnet, health checks, healthcheck api, mapHealthChecks, addCheck, grpc dotnet, protobuf, proto, dockerfile dotnet, multistage dockerfile dotnet, microservizi dotnet, microservizi c#, dotnet kubernetes, kestrel, web api, rest api dotnet, .net 8, .net 9, openapi dotnet, swagger dotnet, dotnet di container, service lifetime, addsingleton, addscoped, addtransient]
parent: dev/linguaggi/_index
related: [dev/linguaggi/java-spring-boot, dev/linguaggi/java-quarkus]
official_docs: https://learn.microsoft.com/en-us/aspnet/core/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# ASP.NET Core 8+ per Microservizi

## Panoramica

ASP.NET Core 8+ è il framework .NET per costruire microservizi, API REST e servizi gRPC pronti per Kubernetes. Con .NET 8 (LTS) e .NET 9, il framework ha consolidato due approcci per gli endpoint HTTP: **Minimal API** (introdotto in .NET 6, maturato in .NET 8) per servizi leggeri e ad alta performance, e il tradizionale **Controller pattern** (MVC) per applicazioni con logica di routing complessa. Il runtime .NET è container-aware, rispetta i limiti di CPU e memoria del cgroup, e Kestrel (il web server built-in) non ha dipendenze da IIS.

Per il contesto Kubernetes, ASP.NET Core 8+ offre: DI container built-in con gestione dei lifetime (Singleton/Scoped/Transient), HealthChecks API nativa con endpoint separati per readiness/liveness, configurazione strutturata tramite `IConfiguration` che legge automaticamente env vars e ConfigMap, `IHostedService`/`BackgroundService` per worker asincroni, e immagini Docker ottimizzate con Chiseled Ubuntu (footprint ~80MB).

Quando usare ASP.NET Core: team C# esistente, necessità di performance elevate (benchmark TechEmpower top 10), workload API REST o gRPC con ricco ecosistema .NET (Entity Framework Core, MassTransit, OpenTelemetry). Quando NON usarlo: workload ML/AI Python-first, sidecar di rete ultra-leggeri (preferire Go), team senza esperienza .NET.

---

## Concetti Chiave

### Minimal API vs Controller Pattern

| Aspetto | Minimal API | Controller Pattern (MVC) |
|---|---|---|
| Struttura | Lambda/method group inline in `Program.cs` | Classi `Controller` separate |
| Performance | Leggermente superiore (meno middleware) | Ottima, ma più overhead riflessione |
| Routing | Dichiarativo, esplicito per ogni endpoint | Convention-based (`[Route]`, `[HttpGet]`) |
| Filtri/Middleware | `IEndpointFilter` | Action filter, `IActionFilter` |
| Testabilità | Richiede `WebApplicationFactory` | Unit test diretti su controller |
| Ideal per | Microservizi semplici (<20 endpoint) | API complesse, team grandi, CRUD enterprise |

!!! tip "Regola pratica"
    Usare **Minimal API** per nuovi microservizi con pochi endpoint ben definiti. Passare al **Controller pattern** quando il numero di endpoint supera ~20, si necessita di filtri per gruppo, o il team è abituato a MVC.

### DI Lifetime — Singleton, Scoped, Transient

| Lifetime | Istanza | Uso corretto | Anti-pattern |
|---|---|---|---|
| `Singleton` | 1 per applicazione (tutta la vita del processo) | Config, cache in-memory, HttpClient factory, connessioni stateless | MAI iniettare Scoped in Singleton (captive dependency) |
| `Scoped` | 1 per richiesta HTTP (o per scope esplicito) | DbContext, Unit of Work, servizi con stato per-request | Non usare fuori da uno scope (es. in BackgroundService senza `IServiceScopeFactory`) |
| `Transient` | 1 nuova istanza ogni volta che viene richiesta | Servizi leggeri stateless, factory | Servizi pesanti o con connessioni (leak di risorse) |

!!! warning "Captive Dependency — Errore comune"
    Iniettare un servizio `Scoped` o `Transient` in un `Singleton` causa un **captive dependency**: il servizio a vita breve viene "catturato" e non rilasciato. Risultato: un `DbContext` (Scoped) diventa di fatto Singleton → race condition su richieste concorrenti.

---

## Architettura / Come Funziona

### Pipeline delle Richieste ASP.NET Core

```
Client HTTP
    │
    ▼
Kestrel (web server built-in)
    │
    ▼
Middleware Pipeline (ordinato, FIFO per request, LIFO per response)
    ├─ UseExceptionHandler
    ├─ UseHttpsRedirection
    ├─ UseAuthentication
    ├─ UseAuthorization
    ├─ UseRateLimiter            (.NET 7+)
    ├─ UseOutputCache            (.NET 7+)
    └─ MapControllers / MapGet / MapGrpcService
          │
          ▼
      DI Container → risolve servizi Scoped per la richiesta
          │
          ▼
      Business Logic → DbContext, Repository, ...
          │
          ▼
      Response serializzata (System.Text.Json, default)
```

### IConfiguration — Gerarchia delle Sorgenti

```
appsettings.json                     (priorità bassa)
    │
    ▼
appsettings.{Environment}.json       (override per ambiente)
    │
    ▼
User Secrets (solo Development)
    │
    ▼
Variabili d'ambiente                 (priorità alta — K8s env/ConfigMap)
    │
    ▼
Command-line arguments               (priorità massima)
```

Le env var con `__` (doppio underscore) vengono automaticamente mappate come sezioni gerarchiche:
`Database__ConnectionString` → `IConfiguration["Database:ConnectionString"]`

---

## Configurazione & Pratica

### Minimal API — Struttura Completa

```csharp
// Program.cs — Minimal API per microservizio ordini
var builder = WebApplication.CreateBuilder(args);

// --- Configurazione servizi ---
builder.Services.AddProblemDetails();   // RFC 9457 error responses

// DI: registra servizi
builder.Services.AddSingleton<IOrderCache, InMemoryOrderCache>();
builder.Services.AddScoped<IOrderRepository, OrderRepository>();
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddHttpClient<IPaymentClient, PaymentClient>(client =>
{
    client.BaseAddress = new Uri(builder.Configuration["Services:Payment:BaseUrl"]
        ?? throw new InvalidOperationException("Payment service URL not configured"));
    client.Timeout = TimeSpan.FromSeconds(10);
});

// Swagger/OpenAPI
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Health checks (vedi sezione dedicata)
builder.Services.AddHealthChecks()
    .AddDbContextCheck<OrderDbContext>()
    .AddCheck<PaymentServiceHealthCheck>("payment-service");

var app = builder.Build();

// --- Pipeline middleware ---
app.UseExceptionHandler();
app.UseStatusCodePages();

if (app.Environment.IsDevelopment())
    app.UseSwaggerUI();

app.MapSwagger();

// --- Endpoint ---
var ordersGroup = app.MapGroup("/orders")
    .WithTags("Orders")
    .WithOpenApi();

ordersGroup.MapGet("/", async (IOrderService svc, CancellationToken ct) =>
    Results.Ok(await svc.GetAllAsync(ct)));

ordersGroup.MapGet("/{id:guid}", async (Guid id, IOrderService svc, CancellationToken ct) =>
{
    var order = await svc.GetByIdAsync(id, ct);
    return order is null ? Results.NotFound() : Results.Ok(order);
});

ordersGroup.MapPost("/", async (CreateOrderRequest req, IOrderService svc, CancellationToken ct) =>
{
    var order = await svc.CreateAsync(req, ct);
    return Results.Created($"/orders/{order.Id}", order);
})
.WithRequestValidation<CreateOrderRequest>();  // IEndpointFilter custom

// Health check endpoints (vedi sezione HealthChecks)
app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
});
app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false   // Liveness: solo "sono vivo", nessun check esterno
});

app.Run();
```

### Controller Pattern — Struttura

```csharp
// Program.cs — Controller pattern
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddScoped<IOrderService, OrderService>();
// ...

var app = builder.Build();
app.MapControllers();
app.Run();
```

```csharp
// Controllers/OrdersController.cs
[ApiController]
[Route("orders")]
[Produces("application/json")]
public class OrdersController : ControllerBase
{
    private readonly IOrderService _service;

    public OrdersController(IOrderService service) => _service = service;

    [HttpGet]
    [ProducesResponseType<IEnumerable<OrderDto>>(StatusCodes.Status200OK)]
    public async Task<IActionResult> GetAll(CancellationToken ct) =>
        Ok(await _service.GetAllAsync(ct));

    [HttpGet("{id:guid}")]
    [ProducesResponseType<OrderDto>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetById(Guid id, CancellationToken ct)
    {
        var order = await _service.GetByIdAsync(id, ct);
        return order is null ? NotFound() : Ok(order);
    }

    [HttpPost]
    [ProducesResponseType<OrderDto>(StatusCodes.Status201Created)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> Create(CreateOrderRequest req, CancellationToken ct)
    {
        var order = await _service.CreateAsync(req, ct);
        return CreatedAtAction(nameof(GetById), new { id = order.Id }, order);
    }
}
```

### IConfiguration con appsettings e Kubernetes

```json
// appsettings.json — valori base
{
  "Database": {
    "ConnectionString": "Host=localhost;Port=5432;Database=orders;Username=orders;Password=changeme"
  },
  "Services": {
    "Payment": {
      "BaseUrl": "http://localhost:5001"
    }
  },
  "FeatureFlags": {
    "EnableNewCheckout": false
  }
}
```

```json
// appsettings.Production.json — override prod (non includere segreti qui)
{
  "Logging": {
    "LogLevel": {
      "Default": "Warning",
      "Microsoft.AspNetCore": "Warning"
    }
  }
}
```

**Accesso type-safe con `IOptions<T>`:**

```csharp
// Models/DatabaseOptions.cs
public class DatabaseOptions
{
    public const string Section = "Database";

    [Required]
    public string ConnectionString { get; init; } = string.Empty;

    public int MaxRetryCount { get; init; } = 3;
    public int CommandTimeoutSeconds { get; init; } = 30;
}
```

```csharp
// Program.cs — registrazione options con validazione
builder.Services
    .AddOptions<DatabaseOptions>()
    .BindConfiguration(DatabaseOptions.Section)
    .ValidateDataAnnotations()        // Valida [Required], [Range], ecc.
    .ValidateOnStart();               // Fallisce lo startup se config non valida

// Uso nel servizio
public class OrderRepository(IOptions<DatabaseOptions> opts) : IOrderRepository
{
    private readonly string _connectionString = opts.Value.ConnectionString;
    // ...
}
```

**ConfigMap Kubernetes mappato su env var:**

```yaml
# configmap.yaml — K8s ConfigMap per order-service
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-service-config
  namespace: production
data:
  # ASP.NET Core legge env var con __ come separatore sezione
  Database__CommandTimeoutSeconds: "45"
  Services__Payment__BaseUrl: "http://payment-service.production.svc.cluster.local:80"
  FeatureFlags__EnableNewCheckout: "true"
---
# Deployment — monta ConfigMap come env vars
spec:
  template:
    spec:
      containers:
        - name: order-service
          image: my-registry/order-service:1.0.0
          envFrom:
            - configMapRef:
                name: order-service-config    # Tutte le chiavi → env var
          env:
            # Segreti da Secret K8s (mai da ConfigMap)
            - name: Database__ConnectionString
              valueFrom:
                secretKeyRef:
                  name: order-service-secrets
                  key: db-connection-string
```

### Dependency Injection — Pattern Avanzati

```csharp
// Keyed services (.NET 8+) — più implementazioni della stessa interfaccia
builder.Services.AddKeyedScoped<INotificationSender, EmailSender>("email");
builder.Services.AddKeyedScoped<INotificationSender, SmsSender>("sms");

// Risoluzione nel controller/service
public class NotificationService(
    [FromKeyedServices("email")] INotificationSender email,
    [FromKeyedServices("sms")] INotificationSender sms)
{ /* ... */ }
```

```csharp
// IServiceScopeFactory — uso di Scoped services in un Singleton
// PATTERN CORRETTO per BackgroundService
public class OrderCleanupWorker(IServiceScopeFactory scopeFactory) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            // Crea scope esplicito — DbContext vive solo in questo scope
            await using var scope = scopeFactory.CreateAsyncScope();
            var repo = scope.ServiceProvider.GetRequiredService<IOrderRepository>();
            await repo.DeleteExpiredOrdersAsync(ct);

            await Task.Delay(TimeSpan.FromHours(1), ct);
        }
    }
}
```

### IHostedService e BackgroundService

```csharp
// Workers/KafkaConsumerWorker.cs — consumer Kafka come BackgroundService
public class KafkaConsumerWorker : BackgroundService
{
    private readonly ILogger<KafkaConsumerWorker> _logger;
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly IConsumer<string, OrderCreatedEvent> _consumer;

    public KafkaConsumerWorker(
        ILogger<KafkaConsumerWorker> logger,
        IServiceScopeFactory scopeFactory,
        IConfiguration config)
    {
        _logger = logger;
        _scopeFactory = scopeFactory;

        var consumerConfig = new ConsumerConfig
        {
            BootstrapServers = config["Kafka:BootstrapServers"],
            GroupId = "order-processor",
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = false    // Commit manuale dopo elaborazione
        };
        _consumer = new ConsumerBuilder<string, OrderCreatedEvent>(consumerConfig)
            .SetValueDeserializer(new JsonDeserializer<OrderCreatedEvent>())
            .Build();
    }

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        _consumer.Subscribe("orders.created");
        _logger.LogInformation("Kafka consumer avviato");

        while (!ct.IsCancellationRequested)
        {
            try
            {
                var result = _consumer.Consume(ct);

                await using var scope = _scopeFactory.CreateAsyncScope();
                var handler = scope.ServiceProvider
                    .GetRequiredService<IOrderCreatedHandler>();

                await handler.HandleAsync(result.Message.Value, ct);
                _consumer.Commit(result);   // Commit solo dopo elaborazione riuscita
            }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Errore elaborazione messaggio Kafka");
                await Task.Delay(TimeSpan.FromSeconds(5), ct);  // Backoff su errore
            }
        }
    }

    public override void Dispose()
    {
        _consumer.Close();
        _consumer.Dispose();
        base.Dispose();
    }
}
```

```csharp
// Program.cs — registrazione worker
builder.Services.AddHostedService<KafkaConsumerWorker>();

// Per un worker-only service (nessun endpoint HTTP), usare Worker Service template:
// dotnet new worker -n MyWorker
// Non serve AddControllers o Kestrel
```

### HealthChecks API

```csharp
// Program.cs — Health Checks configurazione completa
builder.Services.AddHealthChecks()
    // Check Entity Framework Core DbContext
    .AddDbContextCheck<OrderDbContext>(
        name: "database",
        tags: new[] { "ready", "db" })

    // Check URL esterna (dipendenza HTTP)
    .AddUrlGroup(
        uri: new Uri(builder.Configuration["Services:Payment:BaseUrl"] + "/health"),
        name: "payment-service",
        tags: new[] { "ready" })

    // Check custom (implementazione sotto)
    .AddCheck<RedisHealthCheck>(
        name: "redis",
        tags: new[] { "ready", "cache" })

    // Check built-in memory
    .AddCheck("memory", () =>
    {
        var allocated = GC.GetTotalMemory(forceFullCollection: false);
        var limit = 512 * 1024 * 1024; // 512 MB
        return allocated < limit
            ? HealthCheckResult.Healthy($"Memoria: {allocated / 1024 / 1024}MB")
            : HealthCheckResult.Degraded($"Memoria alta: {allocated / 1024 / 1024}MB");
    }, tags: new[] { "ready" });

// Endpoint
app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse,  // JSON dettagliato
    ResultStatusCodes = {
        [HealthStatus.Healthy] = 200,
        [HealthStatus.Degraded] = 200,   // Degraded → ancora ready
        [HealthStatus.Unhealthy] = 503
    }
});

app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    // Liveness: solo processo vivo, NO check dipendenze esterne
    Predicate = _ => false,
    ResponseWriter = (ctx, _) =>
    {
        ctx.Response.ContentType = "application/json";
        return ctx.Response.WriteAsync("{\"status\":\"UP\"}");
    }
});
```

```csharp
// HealthChecks/RedisHealthCheck.cs — check custom
public class RedisHealthCheck(IConnectionMultiplexer redis) : IHealthCheck
{
    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken ct = default)
    {
        try
        {
            var db = redis.GetDatabase();
            await db.PingAsync();
            return HealthCheckResult.Healthy("Redis raggiungibile");
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Unhealthy("Redis non raggiungibile", ex);
        }
    }
}
```

```yaml
# Kubernetes Deployment — probe configuration
spec:
  containers:
    - name: order-service
      ports:
        - containerPort: 8080   # HTTP/gRPC
      livenessProbe:
        httpGet:
          path: /health/live
          port: 8080
        initialDelaySeconds: 15
        periodSeconds: 10
        failureThreshold: 3
      readinessProbe:
        httpGet:
          path: /health/ready
          port: 8080
        initialDelaySeconds: 10
        periodSeconds: 5
        failureThreshold: 3
      startupProbe:
        httpGet:
          path: /health/live
          port: 8080
        failureThreshold: 30   # 30 * 10s = 5 min max startup
        periodSeconds: 10
```

### gRPC con Protobuf

```protobuf
// Protos/orders.proto
syntax = "proto3";
option csharp_namespace = "OrderService.Grpc";

package orders;

service Orders {
    rpc GetOrder (GetOrderRequest) returns (OrderResponse);
    rpc CreateOrder (CreateOrderRequest) returns (OrderResponse);
    rpc StreamOrders (StreamOrdersRequest) returns (stream OrderResponse);
}

message GetOrderRequest {
    string id = 1;
}

message CreateOrderRequest {
    string user_id = 1;
    repeated OrderItem items = 2;
}

message OrderResponse {
    string id = 1;
    string user_id = 2;
    string status = 3;
    double total = 4;
    int64 created_at_unix = 5;
}

message OrderItem {
    string product_id = 1;
    int32 quantity = 2;
    double unit_price = 3;
}

message StreamOrdersRequest {
    string status_filter = 1;
}
```

```xml
<!-- orders.csproj — aggiunge supporto gRPC -->
<ItemGroup>
    <PackageReference Include="Grpc.AspNetCore" Version="2.62.0" />
    <!-- Il .proto genera automaticamente classi C# -->
    <Protobuf Include="Protos\orders.proto" GrpcServices="Server" />
</ItemGroup>
```

```csharp
// Services/OrderGrpcService.cs — implementazione server gRPC
public class OrderGrpcService(IOrderService orderService)
    : Orders.OrdersBase
{
    public override async Task<OrderResponse> GetOrder(
        GetOrderRequest request,
        ServerCallContext context)
    {
        var order = await orderService.GetByIdAsync(
            Guid.Parse(request.Id),
            context.CancellationToken);

        if (order is null)
            throw new RpcException(new Status(StatusCode.NotFound, $"Order {request.Id} not found"));

        return MapToResponse(order);
    }

    public override async Task StreamOrders(
        StreamOrdersRequest request,
        IServerStreamWriter<OrderResponse> responseStream,
        ServerCallContext context)
    {
        await foreach (var order in orderService
            .StreamByStatusAsync(request.StatusFilter, context.CancellationToken))
        {
            await responseStream.WriteAsync(MapToResponse(order));
        }
    }

    private static OrderResponse MapToResponse(Order order) => new()
    {
        Id = order.Id.ToString(),
        UserId = order.UserId,
        Status = order.Status.ToString(),
        Total = (double)order.Total,
        CreatedAtUnix = ((DateTimeOffset)order.CreatedAt).ToUnixTimeSeconds()
    };
}
```

```csharp
// Program.cs — registrazione gRPC
builder.Services.AddGrpc(options =>
{
    options.EnableDetailedErrors = builder.Environment.IsDevelopment();
    options.MaxReceiveMessageSize = 4 * 1024 * 1024;  // 4MB
});

// Se offre sia REST che gRPC sullo stesso port
builder.Services.AddGrpcReflection();   // Per grpcurl in dev

var app = builder.Build();

app.MapGrpcService<OrderGrpcService>();
app.MapGrpcReflectionService();         // Solo in development
app.MapControllers();                   // REST endpoint coesistono
```

### .NET Aspire — Orchestrazione Locale

.NET Aspire è lo stack per sviluppo locale di applicazioni distribuite. Non va in produzione: serve per orchestrare localmente i servizi, configurare dipendenze (DB, Redis, Kafka), e iniettare connection string automaticamente.

```csharp
// AppHost/Program.cs — AppHost Aspire (progetto separato)
var builder = DistributedApplication.CreateBuilder(args);

// Infrastruttura locale
var postgres = builder.AddPostgres("postgres")
    .WithDataVolume()
    .AddDatabase("ordersdb");

var redis = builder.AddRedis("redis");

var kafka = builder.AddKafka("kafka");

// Servizi applicativi
var orderService = builder.AddProject<Projects.OrderService>("order-service")
    .WithReference(postgres)      // Inietta connection string automaticamente
    .WithReference(redis)
    .WithReference(kafka)
    .WithReplicas(1);

var paymentService = builder.AddProject<Projects.PaymentService>("payment-service")
    .WithReference(postgres);

builder.AddProject<Projects.ApiGateway>("api-gateway")
    .WithReference(orderService)
    .WithReference(paymentService);

builder.Build().Run();
```

```csharp
// OrderService/Program.cs — lato servizio, usa Aspire service discovery
builder.AddServiceDefaults();    // Registra OpenTelemetry, Health Checks, Service Discovery

// Con Aspire, la connection string viene iniettata automaticamente
// come env var da AppHost — non serve configurare manualmente
builder.AddNpgsqlDbContext<OrderDbContext>("ordersdb");
builder.AddRedisClient("redis");
```

!!! tip ".NET Aspire in produzione"
    Aspire AppHost e Dashboard sono **solo per sviluppo locale**. In produzione si usa Kubernetes con le stesse variabili d'ambiente che Aspire inietta localmente. Il `builder.AddServiceDefaults()` è invece utile in produzione: configura OpenTelemetry e health checks.

### Dockerfile Multi-Stage Ottimale

```dockerfile
# Dockerfile — multi-stage per ASP.NET Core 8
# Stage 1: restore dipendenze (layer cachato separatamente)
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS restore
WORKDIR /src
# Copia solo i file di progetto per cache efficiente
COPY ["src/OrderService/OrderService.csproj", "src/OrderService/"]
COPY ["src/OrderService.Core/OrderService.Core.csproj", "src/OrderService.Core/"]
RUN dotnet restore "src/OrderService/OrderService.csproj" \
    --runtime linux-musl-x64 \
    -p:PublishReadyToRun=false

# Stage 2: build
FROM restore AS build
COPY . .
RUN dotnet build "src/OrderService/OrderService.csproj" \
    --configuration Release \
    --no-restore \
    -p:TreatWarningsAsErrors=true

# Stage 3: publish — genera artefatto ottimizzato
FROM build AS publish
RUN dotnet publish "src/OrderService/OrderService.csproj" \
    --configuration Release \
    --no-build \
    --runtime linux-musl-x64 \
    --self-contained false \
    -p:PublishReadyToRun=true \
    -p:PublishTrimmed=false \
    -o /app/publish

# Stage 4: immagine finale — Chiseled Ubuntu (~80MB vs ~200MB standard)
FROM mcr.microsoft.com/dotnet/aspnet:8.0-jammy-chiseled AS final
# Chiseled: non-root user built-in, no shell, superficie attacco minima
WORKDIR /app
EXPOSE 8080

# Copia solo l'output del publish
COPY --from=publish /app/publish .

# Variabili d'ambiente per produzione
ENV ASPNETCORE_URLS=http://+:8080
ENV DOTNET_RUNNING_IN_CONTAINER=true
ENV DOTNET_USE_POLLING_FILE_WATCHER=false

ENTRYPOINT ["dotnet", "OrderService.dll"]
```

```yaml
# .dockerignore — esclude file non necessari
**/.git
**/.vs
**/bin
**/obj
**/node_modules
**/*.md
Dockerfile*
docker-compose*
.dockerignore
```

!!! tip "Chiseled Images"
    Le immagini `jammy-chiseled` di Microsoft usano Ubuntu Chiseled: nessuna shell, utente non-root di default, solo le librerie strettamente necessarie. Footprint ~80MB vs ~200MB dell'immagine standard. Preferire sempre in produzione.

---

## Best Practices

### Configurazione Sicura

```csharp
// Validazione obbligatoria della configurazione allo startup
// Se una proprietà Required manca → eccezione allo startup, non a runtime
builder.Services
    .AddOptions<DatabaseOptions>()
    .BindConfiguration("Database")
    .ValidateDataAnnotations()
    .ValidateOnStart();  // ← Critico: fallisce subito, non alla prima richiesta
```

!!! warning "Segreti e ConfigMap"
    Non inserire mai password, token o chiavi API nei ConfigMap Kubernetes — sono base64 ma non cifrati. Usare K8s Secrets (con encryption at rest abilitata), Vault, o Azure Key Vault / AWS Secrets Manager con CSI driver.

### Graceful Shutdown

```csharp
// Program.cs — graceful shutdown integrato
builder.Host.ConfigureHostOptions(opts =>
    opts.ShutdownTimeout = TimeSpan.FromSeconds(30));

// I BackgroundService ricevono CancellationToken che viene segnalato
// quando Kubernetes invia SIGTERM → completare il lavoro in corso, poi uscire
```

```yaml
# Deployment — preStop hook per dare tempo a kube-proxy
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 5"]
# Con immagine Chiseled (nessuna shell), usare httpGet invece:
# preStop:
#   httpGet:
#     path: /shutdown
#     port: 8080
```

### Logging Strutturato

```csharp
// Program.cs — configurazione logging strutturato
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(opts =>
{
    opts.IncludeScopes = true;
    opts.TimestampFormat = "O";
    opts.JsonWriterOptions = new JsonWriterOptions { Indented = false };
});

// Uso nel codice — MAI string interpolation nel log message
// SBAGLIATO: _logger.LogInformation($"Order {id} created");
// CORRETTO (structured logging):
_logger.LogInformation("Order {OrderId} created by {UserId}", order.Id, order.UserId);
```

### HttpClient e Resilienza

```csharp
// Uso corretto di HttpClient — sempre via IHttpClientFactory
// MAI new HttpClient() direttamente (socket exhaustion)
builder.Services.AddHttpClient<IPaymentClient, PaymentClient>()
    .AddStandardResilienceHandler();    // .NET 8: retry, circuit breaker, timeout built-in

// Oppure configurazione esplicita con Polly
builder.Services.AddHttpClient<IPaymentClient, PaymentClient>()
    .AddResilienceHandler("payment-pipeline", pipeline =>
    {
        pipeline.AddRetry(new HttpRetryStrategyOptions
        {
            MaxRetryAttempts = 3,
            BackoffType = DelayBackoffType.Exponential,
            Delay = TimeSpan.FromMilliseconds(200)
        });
        pipeline.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5,
            SamplingDuration = TimeSpan.FromSeconds(10),
            BreakDuration = TimeSpan.FromSeconds(30)
        });
        pipeline.AddTimeout(TimeSpan.FromSeconds(5));
    });
```

---

## Troubleshooting

### Il container si avvia ma il Pod non diventa Ready — readinessProbe fails

**Sintomo:** `kubectl describe pod` mostra `Readiness probe failed: HTTP probe failed with statuscode: 503`. Il servizio è in `Running` ma non riceve traffico.

**Causa:** Un health check `tagged: ready` fallisce — tipicamente il database non è raggiungibile al primo start.

**Soluzione:**
```csharp
// Aumenta la tolleranza per servizi lenti ad avviarsi
// Oppure usa startupProbe per dare tempo al warmup
```
```yaml
startupProbe:
  httpGet:
    path: /health/live    # Usa liveness (senza check DB) per startup
    port: 8080
  failureThreshold: 30
  periodSeconds: 10       # 5 minuti massimo per avviarsi
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 0  # startupProbe gestisce il delay
  periodSeconds: 5
  failureThreshold: 3
```

### DbContext risolto fuori dallo scope — InvalidOperationException

**Sintomo:** `System.InvalidOperationException: Cannot resolve scoped service 'OrderDbContext' from root provider.`

**Causa:** Tentativo di risolvere un servizio Scoped (es. DbContext) da un Singleton o dal root provider.

**Soluzione:**
```csharp
// SBAGLIATO: iniettare DbContext in Singleton
public class OrderCache(OrderDbContext ctx) { }   // ctx è Scoped, cache è Singleton → errore

// CORRETTO: usare IServiceScopeFactory
public class OrderCache(IServiceScopeFactory factory) : IOrderCache
{
    public async Task<Order?> GetAsync(Guid id, CancellationToken ct)
    {
        await using var scope = factory.CreateAsyncScope();
        var ctx = scope.ServiceProvider.GetRequiredService<OrderDbContext>();
        return await ctx.Orders.FindAsync([id], ct);
    }
}
```

### gRPC — "Response Content-Type is not application/grpc"

**Sintomo:** Client gRPC riceve errore `Status(StatusCode="Internal", Detail="Bad gRPC response.")`.

**Causa 1:** Un reverse proxy (nginx, Ingress) non supporta HTTP/2 o lo converte in HTTP/1.1.

**Soluzione:**
```yaml
# Ingress NGINX — abilita HTTP/2 per gRPC
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "GRPC"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"   # gRPC richiede TLS
spec:
  rules:
    - http:
        paths:
          - path: /orders.Orders
            pathType: Prefix
            backend:
              service:
                name: order-service
                port:
                  number: 8080
```

**Causa 2:** Kestrel non abilitato per HTTP/2.
```csharp
// Program.cs — Kestrel esplicito per gRPC
builder.WebHost.ConfigureKestrel(opts =>
{
    opts.ListenAnyIP(8080, listenOpts =>
        listenOpts.Protocols = HttpProtocols.Http1AndHttp2);
});
```

### Perdita di messaggi Kafka — BackgroundService si ferma silenziosamente

**Sintomo:** Il consumer Kafka smette di elaborare messaggi senza errori nei log.

**Causa:** Eccezione non gestita nel loop di `ExecuteAsync` che fa uscire il worker senza riavvio.

**Soluzione:**
```csharp
protected override async Task ExecuteAsync(CancellationToken ct)
{
    while (!ct.IsCancellationRequested)
    {
        try
        {
            // ... logica consumer
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            break;  // Shutdown normale
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Errore nel consumer worker — retry tra 10s");
            // MAI lasciare il catch vuoto o senza retry
            await Task.Delay(TimeSpan.FromSeconds(10), ct);
        }
    }
}
```

### OOM — Il Pod viene terminato per uso eccessivo di memoria

**Sintomo:** `kubectl describe pod` mostra `OOMKilled`. `kubectl top pod` mostra memoria vicina al limit.

**Causa:** Il runtime .NET non libera automaticamente la memoria al GC in risposta alla pressione del container (default in .NET 8 è GC Server mode con heap large).

**Soluzione:**
```dockerfile
# Imposta GC config tramite env var nel Dockerfile o Deployment
ENV DOTNET_GCConserveMemory=5          # 0-9: più alto = GC più aggressivo
ENV DOTNET_GCHeapHardLimit=419430400   # 400MB limite heap esplicito
# Oppure
ENV DOTNET_GCHeapHardLimitPercent=75   # 75% del memory limit del container
```
```yaml
# Deployment — memory request/limit sempre entrambi impostati
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"   # limit = DOTNET_GCHeapHardLimitPercent base
    cpu: "1000m"
```

---

## Relazioni

ASP.NET Core 8+ è il runtime C# di riferimento in questa KB — si integra con molti altri argomenti:

??? info "Java Spring Boot — Confronto framework JVM"
    Spring Boot è il corrispettivo JVM di ASP.NET Core. Entrambi seguono pattern simili: DI container, health endpoint, configurazione esternalizzata, Dockerfile multi-stage. Le differenze principali: Spring Boot usa profili YAML, ASP.NET Core usa IConfiguration con env var `__`-separated. Spring Boot ha un ecosistema più ricco per integrazione enterprise (Spring Data, Spring Security, Spring Cloud).

    **Approfondimento completo →** [Java Spring Boot](java-spring-boot.md)

??? info "Java Quarkus — Alternativa cloud-native JVM"
    Quarkus Native offre startup sub-100ms simile a .NET Native AOT. Confronto con .NET: Quarkus usa Panache (active record pattern), .NET usa EF Core (data mapper). Entrambi supportano gRPC nativo.

    **Approfondimento completo →** [Java Quarkus](java-quarkus.md)

---

## Riferimenti

- [ASP.NET Core Documentation](https://learn.microsoft.com/en-us/aspnet/core/)
- [Minimal APIs in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/)
- [.NET Aspire Documentation](https://learn.microsoft.com/en-us/dotnet/aspire/)
- [Health checks in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/health-checks)
- [gRPC services with ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/grpc/)
- [.NET Generic Host](https://learn.microsoft.com/en-us/dotnet/core/extensions/generic-host)
- [IHostedService and BackgroundService](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/host/hosted-services)
- [Dependency injection in .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection)
- [.NET Container Images](https://github.com/dotnet/dotnet-docker/blob/main/documentation/ubuntu-chiseled.md)
- [Microsoft.Extensions.Http.Resilience](https://learn.microsoft.com/en-us/dotnet/core/resilience/)
