---
title: "Observability da Codice — OpenTelemetry SDK"
slug: observability-code
category: dev
tags: [observability, opentelemetry, tracing, instrumentation, java, dotnet, go, microservizi, distributed-tracing]
search_keywords: [opentelemetry sdk, OTel SDK, strumentazione, instrumentazione, instrumentazione manuale, manual instrumentation, auto instrumentation, auto-instrumentation, javaagent, -javaagent, java agent otel, OTEL_DOTNET_AUTO_HOME, dotnet zero-code instrumentation, go otel, tracer, span, trace context, traceparent, W3C TraceContext, context propagation, propagazione contesto, baggage, otel baggage, cross-cutting context, MDC, mapped diagnostic context, log4j MDC, logback MDC, LogContext dotnet, structured logging traces, log correlation, trace_id log, span_id log, OTLP exporter, OTLP grpc, OTLP http, resource attributes, service.name, sampling head, sampling tail, parent-based sampling, ratio sampling, SDK configuration, span attributes, span events, span status, RecordError, StartSpan, ActivitySource, Activity dotnet, Activity.Start, tracer provider, TracerProvider, MeterProvider, go.opentelemetry.io, opentelemetry-java, opentelemetry-dotnet, distributed tracing microservizi, kafka trace propagation, grpc tracing, http trace propagation, B3 propagation, W3C tracestate, inject extract context]
parent: dev/resilienza/_index
related: [monitoring/fondamentali/opentelemetry, monitoring/tools/jaeger-tempo, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go, dev/resilienza/health-checks]
official_docs: https://opentelemetry.io/docs/instrumentation/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# Observability da Codice — OpenTelemetry SDK

## Panoramica

Questo documento tratta l'OpenTelemetry dalla **prospettiva del codice applicativo**: come aggiungere distributed tracing, metriche e log correlati ai propri microservizi in Java, .NET e Go. È complementare a [OpenTelemetry (concettuale)](../../monitoring/fondamentali/opentelemetry.md) che copre l'architettura del Collector, il deployment su Kubernetes e le pipeline di telemetria.

La strumentazione OTel si divide in due approcci che si usano insieme:

- **Auto-instrumentation**: un agent esterno al binario (bytecode manipulation in Java, CLR profiler in .NET, wrap delle librerie in Go) che injetta trace automaticamente su framework popolari (HTTP server/client, database, gRPC, messaging) senza modificare il codice
- **Manual instrumentation**: codice scritto esplicitamente con le API OTel per tracciare logica di business, aggiungere attributi custom, correlare log con le tracce

**Quando serve la strumentazione manuale:** l'auto-instrumentation copre le chiamate infrastrutturali (HTTP, DB, gRPC). Non vede la logica business: "quale cliente ha eseguito l'ordine?", "qual è l'ID della transazione?", "quante righe sono state processate?". Per rispondere a queste domande in un trace, serve il codice.

!!! warning "Nota su strumentazione vs infrastruttura"
    Questo documento non copre la configurazione del OTel Collector, il deployment Kubernetes, o la configurazione dei backend (Jaeger, Tempo). Quelli sono argomenti infrastrutturali → vedi [OpenTelemetry](../../monitoring/fondamentali/opentelemetry.md).

---

## Concetti Chiave

### La Triade SDK: API, SDK, Instrumentation

```
┌─────────────────────────────────────────────────────────┐
│                  OTel SDK (per linguaggio)               │
│                                                          │
│  ┌───────────────┐    ┌────────────────┐                 │
│  │   OTel API    │    │ Auto-instrum.  │                 │
│  │               │    │ libraries      │                 │
│  │ Tracer        │    │ - HTTP client  │                 │
│  │ Meter         │    │ - gRPC         │                 │
│  │ Logger        │    │ - JDBC/SQL     │                 │
│  └───────┬───────┘    │ - Kafka        │                 │
│          │            └────────┬───────┘                 │
│          ▼                     ▼                         │
│  ┌────────────────────────────────────┐                  │
│  │         SDK Implementation         │                  │
│  │  Sampling │ Processing │ Export    │                  │
│  └─────────────────────┬──────────────┘                  │
└────────────────────────┼────────────────────────────────┘
                         │ OTLP (gRPC 4317 / HTTP 4318)
                         ▼
                  OTel Collector / Backend
```

- **API**: interfacce stabili per creare span, metriche, log. Il codice business dipende SOLO dall'API, non dall'SDK — cambiare implementazione non richiede modifiche al codice.
- **SDK**: implementazione dell'API con sampling, batch processing, export. Configurato una volta al bootstrap dell'applicazione.
- **Instrumentation libraries**: wrappano le librerie di terze parti (Spring, HttpClient, JDBC) per generare span automaticamente.

### Span: Unità Fondamentale di Tracing

Ogni operazione significativa è rappresentata da uno **span**:

```
trace_id: 4bf92f3577b34da6a3ce929d0e0e4736 (identifica tutta la request chain)
span_id:  00f067aa0ba902b7 (identifica questo span)
parent:   a3ce929d0e0e4736 (span parent — null per il root span)

name:     "POST /orders"
kind:     SERVER | CLIENT | PRODUCER | CONSUMER | INTERNAL
start:    2026-03-28T10:00:00.000Z
end:      2026-03-28T10:00:00.120Z  (durata: 120ms)

attributes:
  http.method = "POST"
  http.url    = "/orders"
  http.status_code = 200
  order.id    = "ORD-12345"   ← attributo custom
  customer.tier = "premium"    ← attributo custom

events:
  10:00:00.050 "payment.validated" {payment_method: "card"}
  10:00:00.090 "inventory.reserved" {sku: "SKU-789", qty: 2}

status: OK | ERROR | UNSET
```

### Context Propagation — W3C TraceContext

Il trace context si propaga tra servizi tramite header HTTP standard **W3C TraceContext** (RFC 7230):

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             ^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^ ^^
             ver        trace_id (128 bit)         span_id (64 bit) flags

tracestate: vendor1=value1,vendor2=value2  ← metadati vendor-specific opzionali
```

Il flag `01` in `flags` attiva il **sampled** bit — indica al downstream che questa trace è campionata e deve essere mantenuta.

---

## Architettura / Come Funziona

### Bootstrap del TracerProvider

Il `TracerProvider` è il punto di ingresso globale dell'SDK. Va inizializzato **una sola volta** all'avvio dell'applicazione, prima di qualsiasi operazione tracciata:

```
Application Boot
      │
      ▼
1. Configura Resource (service.name, version, env)
2. Configura Exporter (OTLP endpoint, auth)
3. Configura Sampler (ratio, parent-based, always-on)
4. Crea TracerProvider con BatchSpanProcessor
5. Registra come GlobalTracerProvider
      │
      ▼
Application Runtime
  ctx, span := tracer.Start(ctx, "operationName")
  // ...
  span.End()
```

### Auto vs Manual — Quando si Usa Cosa

```
Framework HTTP (Spring, ASP.NET, net/http)   → auto-instrumentation
Database calls (JDBC, EF Core, database/sql) → auto-instrumentation
gRPC calls                                   → auto-instrumentation
Message broker (Kafka, RabbitMQ)             → auto-instrumentation

Logica business (regole, calcoli)            → manual instrumentation
Attributi domain-specific (order.id, user)  → manual instrumentation
Log correlation (trace_id in ogni log)       → manual instrumentation
Context cross-cutting (baggage)             → manual instrumentation
```

---

## Configurazione & Pratica

### Java — Auto-Instrumentation con -javaagent

L'agent Java OTel usa bytecode manipulation (via OpenTelemetry Java Agent) per instrumentare automaticamente oltre 80 librerie: Spring MVC/WebFlux, gRPC, JDBC, Kafka, Redis, MongoDB, e molte altre.

```bash
# Avvio con l'agent — nessuna modifica al codice o al pom.xml
java \
  -javaagent:/opt/opentelemetry-javaagent.jar \
  -Dotel.service.name=order-service \
  -Dotel.service.version=2.1.0 \
  -Dotel.resource.attributes=deployment.environment=production,team=backend \
  -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
  -Dotel.exporter.otlp.protocol=grpc \
  -Dotel.traces.sampler=parentbased_traceidratio \
  -Dotel.traces.sampler.arg=0.1 \
  -jar app.jar
```

```bash
# Equivalente con variabili d'ambiente (Docker/Kubernetes)
OTEL_SERVICE_NAME=order-service
OTEL_SERVICE_VERSION=2.1.0
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,team=backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
# Disabilita instrumentazione specifica se troppo verbosa
OTEL_INSTRUMENTATION_JDBC_ENABLED=true
OTEL_INSTRUMENTATION_LOGBACK_APPENDER_ENABLED=true  # log correlation automatica
```

### Java — Manual Instrumentation

Per tracciare logica business, aggiungere attributi domain-specific, o gestire errori:

```xml
<!-- pom.xml — solo la API OTel, non l'SDK (l'agent lo porta lui) -->
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-api</artifactId>
    <version>1.36.0</version>
</dependency>
<!-- Con Spring Boot: usa lo starter che configura SDK + exporter -->
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-spring-boot-starter</artifactId>
    <version>2.3.0-alpha</version>
</dependency>
```

```java
// OrderService.java — manual instrumentation con OTEL API
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;

@Service
public class OrderService {

    // Tracer: un'istanza per classe, riutilizzabile (thread-safe)
    private static final Tracer tracer =
        GlobalOpenTelemetry.getTracer("order-service", "2.1.0");

    public OrderResult processOrder(OrderRequest request) {
        // Crea uno span figlio dello span corrente (da HTTP request auto-strumentata)
        Span span = tracer.spanBuilder("processOrder")
            .setSpanKind(SpanKind.INTERNAL)
            .startSpan();

        // Il Scope associa lo span al contesto del thread corrente
        try (Scope scope = span.makeCurrent()) {

            // Attributi custom: informazioni business rilevanti
            span.setAttribute("order.id", request.getOrderId());
            span.setAttribute("order.customer_id", request.getCustomerId());
            span.setAttribute("order.item_count", request.getItems().size());
            span.setAttribute("order.total_amount", request.getTotalAmount());

            // Event: milestone significativa durante l'elaborazione
            span.addEvent("validation.started");
            validateOrder(request);
            span.addEvent("validation.completed");

            PaymentResult payment = processPayment(request);
            span.setAttribute("payment.method", payment.getMethod());
            span.addEvent("payment.processed",
                Attributes.of(
                    AttributeKey.stringKey("payment.transaction_id"),
                    payment.getTransactionId()
                ));

            span.setStatus(StatusCode.OK);
            return new OrderResult(request.getOrderId(), payment);

        } catch (PaymentException e) {
            // Registra l'errore nello span — apparirà nel trace come span in errore
            span.recordError(e);
            span.setStatus(StatusCode.ERROR, "Payment failed: " + e.getMessage());
            throw e;
        } finally {
            span.end(); // SEMPRE chiamare end() — anche in caso di eccezione
        }
    }
}
```

### Java — Log Correlation con MDC

La correlazione tra log e tracce avviene tramite MDC (Mapped Diagnostic Context). Con l'agent OTel e `opentelemetry-logback-appender`, il `trace_id` e lo `span_id` vengono iniettati automaticamente in ogni log statement.

```xml
<!-- logback-spring.xml — pattern con trace_id e span_id dal MDC -->
<configuration>
    <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>trace_id</includeMdcKeyName>
            <includeMdcKeyName>span_id</includeMdcKeyName>
            <includeMdcKeyName>trace_flags</includeMdcKeyName>
        </encoder>
    </appender>
    <root level="INFO">
        <appender-ref ref="JSON" />
    </root>
</configuration>
```

```java
// Con l'agent abilitato, ogni log include automaticamente:
// { "message": "Order validated", "trace_id": "4bf92f35...", "span_id": "00f067aa...", ... }
log.info("Order validated for customer {}", customerId);

// Senza agent (manual): aggiungi manualmente al MDC
Span currentSpan = Span.current();
MDC.put("trace_id", currentSpan.getSpanContext().getTraceId());
MDC.put("span_id", currentSpan.getSpanContext().getSpanId());
log.info("Processing order {}", orderId);
MDC.remove("trace_id");
MDC.remove("span_id");
```

---

### .NET — Zero-Code Auto-Instrumentation

```bash
# Installa OpenTelemetry .NET Automatic Instrumentation
# Il CLR profiler injetta la strumentazione senza modificare il codice

# Linux / Docker
curl -sSfL https://github.com/open-telemetry/opentelemetry-dotnet-instrumentation/releases/latest/download/otel-dotnet-auto-install.sh | sh

# Configurazione via env vars (Dockerfile/Kubernetes)
OTEL_DOTNET_AUTO_HOME=/opt/opentelemetry
CORECLR_ENABLE_PROFILING=1
CORECLR_PROFILER={918728DD-259F-4A6A-AC2B-B85E1B658318}
CORECLR_PROFILER_PATH=/opt/opentelemetry/linux-x64/OpenTelemetry.AutoInstrumentation.Native.so
DOTNET_ADDITIONAL_DEPS=/opt/opentelemetry/AdditionalDeps
DOTNET_SHARED_STORE=/opt/opentelemetry/store
DOTNET_STARTUP_HOOKS=/opt/opentelemetry/net/OpenTelemetry.AutoInstrumentation.StartupHook.dll

OTEL_SERVICE_NAME=order-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
```

```bash
# Windows
.\otel-dotnet-auto-install.ps1

$env:OTEL_DOTNET_AUTO_HOME="C:\otel"
$env:CORECLR_ENABLE_PROFILING="1"
$env:CORECLR_PROFILER="{918728DD-259F-4A6A-AC2B-B85E1B658318}"
$env:CORECLR_PROFILER_PATH="C:\otel\win-x64\OpenTelemetry.AutoInstrumentation.Native.dll"
$env:OTEL_SERVICE_NAME="order-service"
```

### .NET — Manual Instrumentation con ActivitySource

In .NET, la strumentazione manuale usa le `System.Diagnostics.Activity` (API nativa) wrappate da OTel. Non richiedono l'auto-instrumentation agent per funzionare.

```xml
<!-- .csproj -->
<PackageReference Include="OpenTelemetry" Version="1.8.0" />
<PackageReference Include="OpenTelemetry.Exporter.OpenTelemetryProtocol" Version="1.8.0" />
<PackageReference Include="OpenTelemetry.Extensions.Hosting" Version="1.8.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.AspNetCore" Version="1.8.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.Http" Version="1.8.0" />
```

```csharp
// Program.cs — bootstrap SDK
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource =>
        resource.AddService(
            serviceName: "order-service",
            serviceVersion: "2.1.0"))
    .WithTracing(tracing =>
        tracing
            .AddAspNetCoreInstrumentation()   // auto-instrumenta controller
            .AddHttpClientInstrumentation()   // auto-instrumenta HttpClient
            .AddSqlClientInstrumentation()    // auto-instrumenta ADO.NET
            .AddSource("OrderService")        // registra il nostro ActivitySource
            .AddOtlpExporter(otlp =>
            {
                otlp.Endpoint = new Uri("http://otel-collector:4317");
                otlp.Protocol = OtlpExportProtocol.Grpc;
            }))
    .WithMetrics(metrics =>
        metrics
            .AddAspNetCoreInstrumentation()
            .AddRuntimeInstrumentation()
            .AddOtlpExporter());
```

```csharp
// OrderService.cs — manual instrumentation
public class OrderService
{
    // ActivitySource: equivalente al Tracer in Java/Go
    private static readonly ActivitySource ActivitySource =
        new("OrderService", "2.1.0");

    private readonly ILogger<OrderService> _logger;

    public async Task<OrderResult> ProcessOrderAsync(OrderRequest request)
    {
        // Crea uno span figlio dell'Activity corrente (da ASP.NET Core)
        using var activity = ActivitySource.StartActivity("ProcessOrder");

        // Tag: equivalenti agli span attributes
        activity?.SetTag("order.id", request.OrderId);
        activity?.SetTag("order.customer_id", request.CustomerId);
        activity?.SetTag("order.item_count", request.Items.Count);

        // Event: milestone significativa
        activity?.AddEvent(new ActivityEvent("validation.started"));

        try
        {
            await ValidateOrderAsync(request);
            activity?.AddEvent(new ActivityEvent("validation.completed"));

            var payment = await ProcessPaymentAsync(request);
            activity?.SetTag("payment.method", payment.Method);
            activity?.SetTag("payment.transaction_id", payment.TransactionId);

            // Status OK implicito se non si imposta errore
            return new OrderResult(request.OrderId, payment);
        }
        catch (PaymentException ex)
        {
            // Marca lo span come errore
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            activity?.RecordException(ex);
            throw;
        }
    }
}
```

### .NET — Log Correlation con ILogger

```csharp
// Con OpenTelemetry.Extensions.Logging, trace_id e span_id
// vengono aggiunti automaticamente ai log via LogContext.
// Output JSON include trace_id, span_id, trace_flags.

// appsettings.json
{
  "Logging": {
    "Console": {
      "FormatterName": "json"  // richiede formatter JSON per log strutturati
    }
  }
}
```

```csharp
// I log emessi dentro uno span attivo includono automaticamente:
// { "message": "Order validated", "TraceId": "4bf92f35...", "SpanId": "00f067aa...", ... }
_logger.LogInformation("Processing order {OrderId} for customer {CustomerId}",
    request.OrderId, request.CustomerId);

// Per accedere manualmente al trace context nei log:
var activity = Activity.Current;
using (_logger.BeginScope(new Dictionary<string, object>
{
    ["TraceId"] = activity?.TraceId.ToString() ?? "00000000...",
    ["SpanId"]  = activity?.SpanId.ToString() ?? "00000000"
}))
{
    _logger.LogInformation("Order {OrderId} validated", orderId);
}
```

---

### Go — Auto-Instrumentation

Go non supporta auto-instrumentation via bytecode (è compilato). L'auto-instrumentation si ottiene usando le **instrumentation libraries** OTel che wrappano le librerie standard:

```go
// go.mod dependencies per auto-instrumentation delle librerie
require (
    go.opentelemetry.io/otel v1.26.0
    go.opentelemetry.io/otel/sdk v1.26.0
    go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.26.0

    // Instrumentation libraries (wrappano automaticamente)
    go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.51.0
    go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.51.0
    go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin v0.51.0
)
```

```go
// main.go — bootstrap SDK completo
package main

import (
    "context"
    "log"
    "os"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

func initTracerProvider(ctx context.Context) (func(context.Context) error, error) {
    // Exporter OTLP via gRPC (preferito in produzione per efficienza)
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint(getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "otel-collector:4317")),
        otlptracegrpc.WithInsecure(), // rimuovere in produzione — usare TLS
    )
    if err != nil {
        return nil, err
    }

    // Resource: metadati del servizio che appaiono su ogni span
    res, err := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName(getEnv("OTEL_SERVICE_NAME", "order-service")),
            semconv.ServiceVersion(getEnv("OTEL_SERVICE_VERSION", "1.0.0")),
            semconv.DeploymentEnvironment(getEnv("OTEL_DEPLOYMENT_ENV", "development")),
        ),
        resource.WithHost(),      // hostname automatico
        resource.WithProcess(),   // PID, runtime Go automatico
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        // BatchSpanProcessor: invia in batch per efficienza
        trace.WithBatcher(exporter,
            trace.WithMaxExportBatchSize(512),
            trace.WithBatchTimeout(5*time.Second),
        ),
        trace.WithResource(res),
        // Sampler: head-based, 10% con rispetto del parent
        trace.WithSampler(trace.ParentBased(
            trace.TraceIDRatioBased(0.1),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp.Shutdown, nil
}

func main() {
    ctx := context.Background()
    shutdown, err := initTracerProvider(ctx)
    if err != nil {
        log.Fatal(err)
    }
    defer func() {
        if err := shutdown(ctx); err != nil {
            log.Printf("error shutting down tracer: %v", err)
        }
    }()

    // Auto-instrumentation HTTP server via otelhttp
    mux := http.NewServeMux()
    mux.HandleFunc("/orders", handleOrders)

    handler := otelhttp.NewHandler(mux, "order-service-http")
    log.Fatal(http.ListenAndServe(":8080", handler))
}
```

```go
// orderservice/service.go — manual instrumentation
package orderservice

import (
    "context"
    "fmt"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/trace"
)

var tracer = otel.Tracer("orderservice", trace.WithInstrumentationVersion("1.0.0"))

func (s *Service) ProcessOrder(ctx context.Context, req OrderRequest) (*OrderResult, error) {
    // Crea span figlio — il context porta il parent span automaticamente
    ctx, span := tracer.Start(ctx, "ProcessOrder",
        trace.WithSpanKind(trace.SpanKindInternal),
        // Attributi noti già al momento della creazione
        trace.WithAttributes(
            attribute.String("order.id", req.OrderID),
            attribute.String("order.customer_id", req.CustomerID),
        ),
    )
    defer span.End()

    // Attributi aggiuntivi scoperti durante l'elaborazione
    span.SetAttributes(attribute.Int("order.item_count", len(req.Items)))

    // Event: milestone business
    span.AddEvent("validation.started")
    if err := s.validateOrder(ctx, req); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, fmt.Sprintf("validation failed: %v", err))
        return nil, err
    }
    span.AddEvent("validation.completed")

    payment, err := s.processPayment(ctx, req)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "payment processing failed")
        return nil, err
    }

    span.SetAttributes(
        attribute.String("payment.method", payment.Method),
        attribute.String("payment.transaction_id", payment.TransactionID),
    )
    span.SetStatus(codes.Ok, "")

    return &OrderResult{OrderID: req.OrderID, Payment: payment}, nil
}
```

### Context Propagation — HTTP, gRPC, Kafka

```go
// HTTP: inject del trace context negli header outbound
// Con otelhttp.NewTransport() viene fatto automaticamente
client := &http.Client{
    Transport: otelhttp.NewTransport(http.DefaultTransport),
}

// Manuale (se non si usa otelhttp):
req, _ := http.NewRequestWithContext(ctx, "POST", url, body)
otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
// → aggiunge automaticamente: traceparent, tracestate

// HTTP: extract del trace context dagli header inbound
// Con otelhttp.NewHandler() viene fatto automaticamente
// Manuale:
ctx = otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))
```

```java
// Kafka: propagazione del trace context nei message headers
// Con opentelemetry-kafka-clients-2.6, fatto automaticamente da Producer/Consumer wrapper

// Manuale (Kafka Producer):
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.context.propagation.TextMapSetter;

TextMapSetter<ProducerRecord<?, ?>> kafkaSetter = (carrier, key, value) ->
    carrier.headers().add(key, value.getBytes(StandardCharsets.UTF_8));

GlobalOpenTelemetry.getPropagators()
    .getTextMapPropagator()
    .inject(Context.current(), record, kafkaSetter);
producer.send(record);

// Kafka Consumer — extract context dal messaggio ricevuto
TextMapGetter<ConsumerRecord<?, ?>> kafkaGetter = ...;
Context extractedCtx = GlobalOpenTelemetry.getPropagators()
    .getTextMapPropagator()
    .extract(Context.current(), record, kafkaGetter);

try (Scope scope = extractedCtx.makeCurrent()) {
    // Lo span creato qui è figlio dello span del producer
    processMessage(record);
}
```

```go
// gRPC: automatico con otelgrpc interceptors
// Server:
grpcServer := grpc.NewServer(
    grpc.UnaryInterceptor(otelgrpc.UnaryServerInterceptor()),
    grpc.StreamInterceptor(otelgrpc.StreamServerInterceptor()),
)
// Client:
conn, err := grpc.Dial(addr,
    grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
    grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
)
```

### Baggage — Context Cross-Cutting

Il **Baggage** è un meccanismo per propagare coppie chiave-valore attraverso l'intera catena di chiamate. A differenza degli span attributes (visibili solo nello span corrente), il baggage viaggia con il trace context e può essere letto da qualsiasi servizio nel call chain.

```go
// Aggiunta di baggage al context (es. nel gateway API)
import "go.opentelemetry.io/otel/baggage"

tenantMember, _ := baggage.NewMember("tenant.id", "acme-corp")
userMember, _   := baggage.NewMember("user.tier", "premium")
bag, _          := baggage.New(tenantMember, userMember)
ctx = baggage.ContextWithBaggage(ctx, bag)

// Lettura del baggage in un servizio downstream
bag := baggage.FromContext(ctx)
tenantID := bag.Member("tenant.id").Value()  // "acme-corp"
userTier := bag.Member("user.tier").Value()  // "premium"

// Uso tipico: aggiungere il tenant_id come attributo allo span corrente
span := trace.SpanFromContext(ctx)
span.SetAttributes(attribute.String("tenant.id", tenantID))
```

!!! warning "Baggage e Performance"
    Il baggage viaggia in ogni header HTTP/gRPC del sistema. Evita di inserire valori grandi (> 100 byte) o un numero elevato di chiavi. Per informazioni voluminose, usa database/cache e propaga solo la chiave di lookup nel baggage.

### SDK Configuration — OTLP, Sampling, Resource

```bash
# Configurazione completa via env vars (valida per tutti i linguaggi)

# --- Exporter OTLP ---
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317  # gRPC (default)
# oppure per HTTP/protobuf:
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf  # grpc | http/protobuf | http/json
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer token123  # per autenticazione

# --- Sampler ---
OTEL_TRACES_SAMPLER=parentbased_traceidratio  # raccomandato in produzione
OTEL_TRACES_SAMPLER_ARG=0.1                  # 10% del traffico totale

# Opzioni sampler:
# always_on          → campiona tutto (development)
# always_off         → non campiona nulla (disable tracing)
# traceidratio       → % basata su trace_id (ignora il parent)
# parentbased_always_on     → segue il parent; sempre ON se root
# parentbased_traceidratio  → segue il parent; ratio se root (PRODUZIONE)

# --- Resource Attributes ---
OTEL_SERVICE_NAME=order-service
OTEL_SERVICE_VERSION=2.1.0
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,k8s.namespace=orders,k8s.pod.name=${POD_NAME}

# --- Propagatori ---
OTEL_PROPAGATORS=tracecontext,baggage  # W3C standard (default)
# oppure aggiunge B3 per compatibilità con Zipkin/vecchi sistemi:
# OTEL_PROPAGATORS=tracecontext,baggage,b3

# --- Logging SDK ---
OTEL_LOGS_EXPORTER=otlp  # attiva export dei log via OTLP (richiede SDK + appender)
```

---

## Best Practices

!!! tip "Un TracerProvider globale per processo"
    Inizializza il `TracerProvider` una sola volta al boot e registralo come globale (`otel.SetTracerProvider(tp)`). Non creare TracerProvider multipli — ogni provider ha il suo batch buffer e porta overhead. I singoli `Tracer` si ottengono dal provider globale e sono thread-safe.

!!! tip "Usa sempre `parentbased_traceidratio` in produzione"
    Il sampler `parentbased_*` garantisce che se il parent decide di campionare, tutti i figli seguano (coerenza della trace). Con `traceidratio` puro, il downstream potrebbe campionare ma l'upstream no, generando trace incomplete. In sviluppo usa `always_on`.

!!! warning "Non loggare PII negli span attributes"
    Gli span attributes vengono inviati al backend di tracing (Jaeger, Tempo, Datadog). Non inserire: password, token, numeri di carta, dati personali identificativi. Per i dati necessari al debug, usa hash o truncation. Il Collector OTel può applicare attribute filtering prima dell'export.

!!! warning "Span.End() è obbligatorio"
    Uno span non terminato non viene mai esportato e rimane in memoria nel buffer dello SDK. In Java/Go usare `defer span.End()` come prima istruzione dopo `Start`. In .NET usare `using var activity = ...` che chiama `Dispose()` (= `End()`) automaticamente.

**Pattern consigliati:**
- Span name: usa `"VerbNoun"` o `"Service/Operation"` — evita path dinamici (`"/orders/12345"` → usa attributo `http.route = "/orders/{id}"`)
- Aggiorna il `trace.status` esplicitamente solo per gli errori — `UNSET` equivale a OK in tutti i backend
- Nei microservizi: propaga sempre il `context.Context` (Go) o il `Context` request-scoped (Java Spring/ASP.NET) — è il vettore invisibile di tutta la trace
- Aggiungi sempre `service.name`, `service.version`, `deployment.environment` nelle resource attributes — abilitano il filtraggio nei dashboard

---

## Troubleshooting

### Problema: Span non appaiono nel backend

**Sintomo:** Il servizio sembra avviato con l'agent/SDK, ma Jaeger/Tempo non mostrano alcuna trace.

**Causa più comune:** L'exporter non riesce a raggiungere il Collector (errore silenzioso con SDK default).

**Diagnosi:**
```bash
# Java: abilita debug logging dell'agent
-Dotel.javaagent.debug=true

# Tutti i linguaggi: imposta l'exporter console per verifica locale
OTEL_TRACES_EXPORTER=console  # stampa span su stdout, conferma che l'SDK funziona

# Verifica connettività al collector
curl -v http://otel-collector:4318/v1/traces  # per OTLP HTTP
# atteso: 405 Method Not Allowed (il path esiste ma richiede POST)

# Controlla i log del collector
kubectl logs deploy/otel-collector -n monitoring | grep -E "error|refused|connection"
```

**Soluzione:**
```bash
# Verifica che endpoint e porta siano corretti
# gRPC: porta 4317  — non http:// nel endpoint per gRPC
OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317  # NO http:// per gRPC
# HTTP: porta 4318  — con http:// nel endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

---

### Problema: Trace spezzate — le chiamate tra servizi non appaiono nella stessa trace

**Sintomo:** Ogni servizio mostra le proprie trace indipendenti invece di una trace unificata attraverso il call chain.

**Causa:** Il trace context non viene propagato nelle chiamate HTTP/gRPC/Kafka — gli header `traceparent`/`tracestate` vengono persi.

**Diagnosi:**
```bash
# Verifica che gli header vengano inviati (lato client)
# Abilita logging HTTP per vedere gli header outbound
OTEL_LOG_LEVEL=debug  # OTel SDK debug — mostra inject/extract

# Cattura il traffico HTTP con kubectl debug o tcpdump
kubectl debug -it pod/order-service -- curl -v http://payment-service/pay \
  -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
# Se il downstream crea una nuova trace invece di continuarla → extract non funziona
```

**Soluzione:**
```go
// Go: assicurati che il client HTTP usi l'otelhttp transport
// SBAGLIATO:
resp, err := http.DefaultClient.Post(url, ...)  // non propaga il context

// CORRETTO:
client := &http.Client{Transport: otelhttp.NewTransport(http.DefaultTransport)}
resp, err := client.Post(url, ...)  // propaga automaticamente traceparent

// Java Spring Boot: WebClient con context propagation automatica
// (WebClient + opentelemetry-spring-boot-starter = auto-propagation)
// Verifica che OTEL_PROPAGATORS=tracecontext sia impostato su tutti i servizi
```

---

### Problema: Alto overhead di CPU/memoria con tracing abilitato

**Sintomo:** Il servizio mostra un aumento di 5-15% di CPU e 50-200MB di heap aggiuntivi con OTel abilitato.

**Causa:** Sampling al 100% (`always_on`) o span troppo granulari su operazioni ad alta frequenza.

**Diagnosi:**
```bash
# Java: profila l'overhead dell'agent
-Dotel.javaagent.debug=true
# Cerca: "Dropped spans due to full queue" — indica che il batch processor è saturo

# Controlla il numero di span al secondo
curl http://otel-collector:8888/metrics | grep otelcol_processor_batch_batch_send_size
```

**Soluzione:**
```bash
# 1. Riduci il sampling rate in produzione
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.05  # 5% invece di 100%

# 2. Disabilita instrumentation verbose non necessaria (Java agent)
OTEL_INSTRUMENTATION_METHODS_INCLUDE=""  # rimuove metodi custom
OTEL_INSTRUMENTATION_JDBC_STATEMENT_SANITIZER_ENABLED=true  # riduce attributo SQL

# 3. Aumenta il batch size per ridurre frequenza di export
OTEL_BSP_MAX_EXPORT_BATCH_SIZE=512
OTEL_BSP_SCHEDULE_DELAY=5000  # 5 secondi tra batch (default: 5000ms)
```

---

### Problema: Log non correlati con le trace (trace_id mancante nei log)

**Sintomo:** I log del servizio non contengono `trace_id`/`span_id`. Impossibile navigare da un log a una trace in Grafana/Datadog.

**Causa:** Il log appender OTel non è configurato o il log avviene fuori da uno span attivo.

**Soluzione Java (Logback):**
```xml
<!-- pom.xml: aggiungi l'appender OTel per Logback -->
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-logback-appender-1.0</artifactId>
    <version>2.3.0-alpha</version>
</dependency>
```
```xml
<!-- logback-spring.xml -->
<appender name="OpenTelemetry" class="io.opentelemetry.instrumentation.logback.appender.v1_0.OpenTelemetryAppender">
    <captureExperimentalAttributes>true</captureExperimentalAttributes>
    <captureLoggerContext>true</captureLoggerContext>
</appender>
<root level="INFO">
    <appender-ref ref="OpenTelemetry"/>
    <appender-ref ref="CONSOLE"/>
</root>
```

**Soluzione Go (slog):**
```go
// Usa il bridge slog → OTel per correlazione automatica
import "go.opentelemetry.io/contrib/bridges/otelslog"

logger := otelslog.NewLogger("order-service")
// I log emessi con questo logger includono trace_id/span_id dal contesto
logger.InfoContext(ctx, "order processed",
    slog.String("order_id", orderID),
    slog.String("customer_id", customerID),
)
```

---

## Relazioni

??? info "OpenTelemetry — Architettura e Collector"
    Questo file copre l'SDK (lato codice). Per l'architettura del Collector, le pipeline di telemetria, il deployment Kubernetes e la configurazione dei backend → [OpenTelemetry](../../monitoring/fondamentali/opentelemetry.md)

??? info "Jaeger / Grafana Tempo — Visualizzazione Trace"
    I trace prodotti dall'SDK si visualizzano in Jaeger o Grafana Tempo. Per setup, query, e analisi delle trace → [Jaeger e Tempo](../../monitoring/tools/jaeger-tempo.md)

??? info "Java Spring Boot — Integrazione OTel"
    Spring Boot Actuator si integra nativamente con OTel SDK. Il micrometro-otel bridge permette di esportare anche le metriche Actuator via OTLP → [Java Spring Boot](../linguaggi/java-spring-boot.md)

??? info ".NET — Runtime e SDK OTel"
    L'auto-instrumentation .NET usa il CLR profiler. Per configurazione avanzata del runtime e ottimizzazione delle performance con OTel abilitato → [.NET](../linguaggi/dotnet.md)

??? info "Go — Context e Goroutine con OTel"
    In Go, la propagazione del context è fondamentale per OTel. Pattern per passare context attraverso goroutine, channel, e worker pool → [Go](../linguaggi/go.md)

---

## Riferimenti

- [OpenTelemetry — Instrumentazione per Linguaggio](https://opentelemetry.io/docs/instrumentation/) — Guide ufficiali per Java, .NET, Go, Python, Node.js
- [OTel Java Agent — Configurazione](https://opentelemetry.io/docs/zero-code/java/agent/) — javaagent, env vars, strumentazione supportata
- [OTel .NET Auto-Instrumentation](https://opentelemetry.io/docs/zero-code/net/) — CLR profiler, OTEL_DOTNET_AUTO_HOME
- [OTel Go — Getting Started](https://opentelemetry.io/docs/languages/go/getting-started/) — Setup SDK, manual instrumentation
- [Semantic Conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/) — Standard per gli span attribute names (http.*, db.*, messaging.*)
- [W3C TraceContext Specification](https://www.w3.org/TR/trace-context/) — Standard per la propagazione trace via HTTP headers
- [OTel Baggage API](https://opentelemetry.io/docs/concepts/signals/baggage/) — Context propagation cross-cutting
- [Grafana OTel Loki Integration](https://grafana.com/docs/grafana/latest/datasources/loki/configure-loki-data-source/) — Correlazione log-trace in Grafana
