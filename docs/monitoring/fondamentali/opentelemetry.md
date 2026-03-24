---
title: "OpenTelemetry"
slug: opentelemetry
category: monitoring
tags: [observability, telemetry, tracing, metrics, logs, otel, cncf]
search_keywords: [OTel, OpenTelemetry, OTEL, telemetria, osservabilità, distributed tracing, metriche, log, tracce, OTLP, collector, SDK, instrumentazione, CNCF, spans, traces, context propagation, vendor-neutral]
parent: monitoring/fondamentali
related: [monitoring/tools/prometheus, monitoring/tools/grafana, monitoring/tools/loki, monitoring/tools/jaeger-tempo, monitoring/sre/slo-sla-sli, networking/service-mesh/istio]
official_docs: https://opentelemetry.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# OpenTelemetry

## Panoramica

OpenTelemetry (OTel) è il framework CNCF open-source per la raccolta, elaborazione ed esportazione di dati di telemetria — metriche, log e tracce distribuite — in modo vendor-neutral. Nasce dalla fusione dei progetti OpenCensus e OpenTracing (2019) ed è oggi lo standard de-facto per l'osservabilità nei sistemi cloud-native. Si usa quando si vuole instrumentare applicazioni e infrastrutture senza lock-in verso uno specifico backend (Datadog, Jaeger, Prometheus, etc.), garantendo portabilità della telemetria tra vendor. Non si usa come backend di storage o visualizzazione: OTel raccoglie e trasporta, non conserva né visualizza.

## Concetti Chiave

!!! note "I Tre Pilastri della Telemetria"
    OpenTelemetry copre i tre segnali fondamentali dell'osservabilità:

    - **Metriche**: valori numerici aggregati nel tempo (CPU, latenza, error rate)
    - **Log**: eventi discreti con timestamp e contesto strutturato
    - **Tracce (Distributed Tracing)**: catena di operazioni attraverso microservizi

### Signal: Traces

Una **trace** rappresenta il percorso completo di una richiesta attraverso un sistema distribuito. È composta da **span** collegati gerarchicamente.

```
Trace
└── Span: frontend → /checkout (root span)
    ├── Span: payment-service → processPayment
    │   └── Span: db → INSERT orders
    └── Span: inventory-service → decreaseStock
```

Ogni span contiene:
- `trace_id`: identificativo univoco della trace
- `span_id`: identificativo dello span
- `parent_span_id`: riferimento al parent
- `start_time` / `end_time`
- **Attributes**: coppie chiave-valore (es. `http.method = "POST"`)
- **Events**: log immutabili all'interno dello span
- **Status**: `OK`, `ERROR`, `UNSET`

### Signal: Metrics

Le metriche OTel sono rappresentate come **Instruments**:

| Instrument | Tipo | Uso tipico |
|---|---|---|
| `Counter` | monotono crescente | richieste totali, bytes inviati |
| `UpDownCounter` | bidirezionale | connessioni attive, queue size |
| `Histogram` | distribuzione | latenza, dimensione payload |
| `Gauge` | valore istantaneo | temperatura, utilizzo memoria |
| `ObservableCounter` | async pull | metriche dal SO |

### Signal: Logs

OTel non reinventa il logging: si integra con framework esistenti (log4j, logrus, slog) correlando automaticamente i log agli span attivi tramite **context propagation**.

### Context Propagation

Il meccanismo che permette il tracciamento cross-service. Ogni chiamata trasporta il `trace_id` e `span_id` nell'header HTTP (W3C TraceContext standard):

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

Formato: `version-trace_id-parent_id-flags`

## Architettura / Come Funziona

L'architettura OTel è composta da tre layer principali:

```
┌─────────────────────────────────────────────────┐
│              Applicazione                        │
│  ┌──────────────────────────────────────────┐   │
│  │         OTel SDK (linguaggio)            │   │
│  │  Tracers │ Meters │ Loggers              │   │
│  └──────────────────┬───────────────────────┘   │
│                     │ OTLP (gRPC/HTTP)           │
└─────────────────────┼───────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│           OTel Collector                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Receiver │→ │Processor │→ │   Exporter   │  │
│  │ (OTLP,   │  │(batch,   │  │(Jaeger,      │  │
│  │ Jaeger,  │  │ filter,  │  │ Prometheus,  │  │
│  │ Zipkin)  │  │ tail-    │  │ Loki, OTLP)  │  │
│  └──────────┘  │ sampling)│  └──────────────┘  │
│                └──────────┘                      │
└─────────────────────────────────────────────────┘
                      ↓
         Backend (Jaeger, Grafana, Datadog...)
```

### OTel SDK

L'SDK è disponibile per ogni linguaggio principale (Go, Java, Python, Node.js, .NET, etc.) e fornisce:
- **API**: interfacce stabili per creare span, metriche, log
- **SDK**: implementazione con processing, sampling, export
- **Auto-instrumentation**: agent bytecode che instrumenta automaticamente framework popolari (Spring, Django, Express, etc.) senza modificare il codice

### OTel Collector

Componente opzionale ma raccomandato in produzione. Agisce da proxy/agent tra le applicazioni e i backend:

**Perché usarlo invece di esportare direttamente:**
- Decoupla l'applicazione dal backend specifico
- Aggrega e processa prima di inviare (riduce traffico)
- Tail-based sampling: decide quali trace conservare DOPO averle ricevute completamente
- Retry e buffering in caso di downtime del backend
- Filtraggio PII prima che i dati lascino il cluster

**Deployment modes:**
- **Agent**: sidecar o daemonset per-node, minima latenza
- **Gateway**: deployment centralizzato, pool scalabile

### OTLP — OpenTelemetry Protocol

Il protocollo di trasporto nativo OTel. Supporta gRPC (più efficiente) e HTTP/JSON (più compatibile). Tutti i vendor moderni accettano OTLP nativamente.

## Configurazione & Pratica

### Instrumentazione automatica (Go + gRPC)

```go
// main.go — setup OTel con OTLP exporter
package main

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func initTracer(ctx context.Context) (*trace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("my-service"),
            semconv.ServiceVersion("1.0.0"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}

// Uso in codice applicativo
func handleRequest(ctx context.Context) {
    tracer := otel.Tracer("my-service")
    ctx, span := tracer.Start(ctx, "handleRequest")
    defer span.End()

    span.SetAttributes(attribute.String("user.id", "123"))

    // ... logica business ...

    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
    }
}
```

### OTel Collector — configurazione base

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_mib: 512

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [loki]
```

### Deploy su Kubernetes (Helm)

```bash
# Aggiungi il repo Helm ufficiale
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts

# Installa il collector come DaemonSet (agent mode)
helm install otel-collector open-telemetry/opentelemetry-collector \
  --set mode=daemonset \
  --values otel-collector-config.yaml

# Installa l'Operator per auto-instrumentazione
helm install opentelemetry-operator open-telemetry/opentelemetry-operator
```

### Auto-instrumentazione con Operator (Kubernetes)

```yaml
# Inietta automaticamente l'agente OTel nei pod Java
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: java-instrumentation
spec:
  exporter:
    endpoint: http://otel-collector:4317
  propagators:
    - tracecontext
    - baggage
  sampler:
    type: parentbased_traceidratio
    argument: "0.1"  # 10% sampling rate
  java:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:latest
---
# Il pod riceve un'annotation per attivare l'injection
apiVersion: v1
kind: Pod
metadata:
  annotations:
    instrumentation.opentelemetry.io/inject-java: "true"
```

### Sampling

```yaml
# Tail-based sampling nel Collector — conserva solo trace con errori o lente
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    expected_new_traces_per_sec: 10
    policies:
      - name: errors-policy
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow-traces-policy
        type: latency
        latency: {threshold_ms: 1000}
      - name: probabilistic-policy
        type: probabilistic
        probabilistic: {sampling_percentage: 5}
```

## Best Practices

!!! tip "Usa il Collector in produzione"
    Non esportare mai direttamente dall'SDK al backend in produzione. Il Collector garantisce retry, buffering, e decoupling. Se il backend è down, il Collector bufferizza e riprova; l'SDK invece droppa i dati.

!!! tip "Scegli il sampling giusto"
    - **Head sampling**: decide all'inizio della trace → efficiente, ma perdi trace di errori rari
    - **Tail sampling** (nel Collector): decide a fine trace → conserva sempre gli errori, ma richiede più memoria
    - In produzione: `1-10%` per il traffico normale + `100%` per gli errori

!!! warning "Semantic Conventions"
    Usa sempre le [Semantic Conventions OTel](https://opentelemetry.io/docs/concepts/semantic-conventions/) per gli attribute degli span (es. `http.method`, `db.system`, `net.peer.ip`). Questo garantisce compatibilità con i dashboard pre-built di Grafana e altri tool.

!!! warning "Costo della instrumentazione manuale"
    L'auto-instrumentazione copre il 90% dei casi. L'instrumentazione manuale aggiunge overhead di sviluppo — usala solo per logica business critica che i framework automatici non tracciano.

**Pattern consigliati:**
- Un `TracerProvider` globale per applicazione, inizializzato al boot
- `span.RecordError(err)` + `span.SetStatus(codes.Error, ...)` per ogni errore gestito
- Propaga sempre il `context.Context` in Go, `Context` in Java/Python — è il vettore del trace context
- Aggiungi `service.name`, `service.version`, `deployment.environment` nelle Resource attributes

**Anti-pattern da evitare:**
- Non creare span per operazioni sotto i 5ms — troppo rumore, costi di storage elevati
- Non loggare dati sensibili (PII, token) negli span attributes
- Non usare span nidificati per operazioni sincrone banali (es. getter/setter)

## Troubleshooting

**Span non appaiono nel backend**
```bash
# Verifica che il collector riceva dati
kubectl logs deploy/otel-collector | grep "Received"

# Controlla la pipeline del collector
curl http://otel-collector:8888/metrics | grep otelcol_receiver_accepted_spans
```

**Context propagation interrotta**
- Verificare che tutti i servizi nel call chain usino lo stesso propagator (W3C TraceContext)
- Controllare che i framework HTTP non strippino gli header `traceparent`/`tracestate`
- In Kubernetes: verificare che gli sidecar Istio/Envoy siano configurati per passare gli header OTel

**Metriche duplicate in Prometheus**
- Succede quando si usa sia il Prometheus SDK che OTel nello stesso processo
- Soluzione: migrare completamente a OTel oppure usare `prometheus.NewRegistry()` separati

**Alto utilizzo memoria del Collector con tail sampling**
- Il tail sampling bufferizza trace complete in memoria
- Ridurre `num_traces` o aumentare le repliche del Collector
- Considerare batch processing per abbassare il footprint

## Relazioni

OpenTelemetry è il livello di raccolta dati; i backend e gli strumenti di visualizzazione sono argomenti correlati:

??? info "Prometheus — Metriche"
    Prometheus è il backend più comune per le metriche OTel. Il Collector esporta in formato Prometheus. Scraping, PromQL, alerting.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Grafana — Visualizzazione"
    Grafana visualizza tutti e tre i segnali OTel: metriche (Prometheus), log (Loki), tracce (Tempo). Dashboard unificata per l'osservabilità.

    **Approfondimento completo →** [Grafana](../tools/grafana.md)

??? info "Jaeger / Grafana Tempo — Distributed Tracing"
    Backend per le tracce OTel. Jaeger è il più maturo; Tempo è integrato nativamente in Grafana.

    **Approfondimento completo →** [Jaeger e Tempo](../tools/jaeger-tempo.md)

??? info "Loki — Log Aggregation"
    Backend per i log OTel. Integrato in Grafana, usa la stessa label syntax di Prometheus.

    **Approfondimento completo →** [Loki](../tools/loki.md)

??? info "Istio — Service Mesh"
    Istio può injectare automaticamente il trace context nei pod Kubernetes, complementando OTel.

    **Approfondimento completo →** [Istio](../../networking/service-mesh/istio.md)

## Riferimenti

- [OpenTelemetry — Documentazione Ufficiale](https://opentelemetry.io/docs/)
- [OpenTelemetry Collector — Configurazione](https://opentelemetry.io/docs/collector/configuration/)
- [Semantic Conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/)
- [OpenTelemetry Helm Charts](https://github.com/open-telemetry/opentelemetry-helm-charts)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
- [W3C TraceContext Standard](https://www.w3.org/TR/trace-context/)
