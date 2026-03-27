---
title: "I Tre Pilastri dell'Osservabilità"
slug: tre-pilastri-osservabilita
category: monitoring
tags: [observability, metrics, logs, traces, monitoring, telemetry, sre, cloud-native]
search_keywords: [osservabilità, tre pilastri, metriche, log, tracce, metrics, logs, traces, telemetria, observability, distributed tracing, logging, monitoring, MELT, golden signals, segnali telemetrici, quando usare metriche, quando usare log, quando usare tracce, correlazione segnali, cardinality, high cardinality, structured logging, span, trace context, RED method, USE method, four golden signals, osservabilità vs monitoring, whitebox monitoring, blackbox monitoring]
parent: monitoring/fondamentali
related: [monitoring/fondamentali/opentelemetry, monitoring/tools/prometheus, monitoring/tools/loki, monitoring/tools/jaeger-tempo, monitoring/sre/slo-sla-sli]
official_docs: https://opentelemetry.io/docs/concepts/observability-primer/
status: complete
difficulty: beginner
last_updated: 2026-03-25
---

# I Tre Pilastri dell'Osservabilità

## Panoramica

L'osservabilità è la capacità di comprendere lo stato interno di un sistema a partire dai suoi output esterni. In un sistema distribuito moderno, i "segnali" che emette un sistema si dividono in tre categorie fondamentali — metriche, log e tracce — ognuna con caratteristiche, costi e usi distinti. Insieme formano i **tre pilastri dell'osservabilità** (anche detti MELT: Metrics, Events/Logs, Logs, Traces) o la "triade della telemetria".

La differenza rispetto al monitoring tradizionale è sostanziale: il **monitoring** risponde a "il sistema funziona?" (domande note con risposte note), mentre l'**osservabilità** risponde a "perché il sistema si comporta così?" (domande non anticipate). Un sistema osservabile permette di diagnosticare problemi mai visti prima senza dover deployare nuova strumentazione.

I tre pilastri non sono intercambiabili: ogni segnale ha un costo, una granularità e un caso d'uso ottimale. Usarli tutti e tre in modo coerente — e saperli correlare — è la base dell'SRE moderna.

---

## Concetti Chiave

### Metriche

Le **metriche** sono misurazioni numeriche aggregate nel tempo. Rappresentano lo stato del sistema in forma quantitativa: quante richieste al secondo, quanto CPU, quale percentuale di errori.

!!! note "Caratteristiche delle metriche"
    - **Cardinalità bassa**: identificate da nome + label set; ogni combinazione è una time series
    - **Aggregazione**: perdono la granularità individuale in favore di tendenze aggregate
    - **Efficienti**: storage e query costano poco rispetto a log e tracce
    - **Ideali per alerting**: una soglia su una metrica è la forma più comune di alert

**Tipi standard** (seguono la tassonomia Prometheus/OTel):

| Tipo | Descrizione | Esempio |
|------|-------------|---------|
| **Counter** | Valore monotono crescente | `http_requests_total` |
| **Gauge** | Valore istantaneo, sale e scende | `memory_used_bytes` |
| **Histogram** | Distribuzione in bucket | `request_duration_seconds` |
| **Summary** | Quantili calcolati lato client | `rpc_duration_seconds` |

**Quando usare le metriche:**
- Alerting su soglie (`error_rate > 5%`)
- Dashboard di overview (quante RPS, latenza media, uptime)
- SLI/SLO: misurare affidabilità nel tempo
- Capacity planning: trend di crescita
- Confronto aggregato: "il deployment di ieri vs oggi"

**Quando NON usare le metriche:**
- Capire *perché* una singola richiesta ha fallito → usa i log
- Tracciare il percorso di una specifica transazione → usa le tracce
- Debugging con contesto ricco (user ID, payload, stack trace) → usa i log

---

### Log

I **log** sono eventi discreti, testuali o strutturati, con timestamp. Ogni riga di log descrive qualcosa che è accaduto in un momento preciso, con tutto il contesto disponibile a quel punto.

!!! note "Caratteristiche dei log"
    - **Alta cardinalità**: ogni evento è unico, con dati arbitrari
    - **Contesto ricco**: possono includere stack trace, payload, user ID, correlationID
    - **Costosi a scala**: volume alto → storage e indicizzazione costosi
    - **Non aggregabili per default**: richiedono query full-text o strutturate

**Structured vs Unstructured logging:**

```json
// Structured log (JSON) — raccomandato in produzione
{
  "timestamp": "2026-03-25T14:32:01.123Z",
  "level": "ERROR",
  "service": "payment-service",
  "message": "Payment processing failed",
  "user_id": "usr-4821",
  "order_id": "ord-99201",
  "error": "card declined: insufficient funds",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "duration_ms": 342
}
```

```
# Unstructured log — difficile da parsare e interrogare
2026-03-25 14:32:01 ERROR payment-service: Payment for user 4821 failed - card declined
```

**Quando usare i log:**
- Debug di un errore specifico ("cosa è successo esattamente a quell'utente?")
- Audit trail: chi ha fatto cosa e quando
- Analisi di eventi rari (eccezioni, fallimenti sporadici)
- Contesto operativo: messaggi human-readable per operators
- Investigazione post-mortem: ricostruire la sequenza degli eventi

**Quando NON usare i log:**
- Misurare trend aggregati → usa le metriche (parsare i log per costruire metriche è antipattern)
- Tracciare il flusso cross-service → usa le tracce
- Alerting in real-time → troppo rumore e latenza

---

### Tracce

Le **tracce** (distributed traces) rappresentano il percorso completo di una richiesta attraverso un sistema distribuito. Ogni traccia è composta da **span** gerarchici, ognuno dei quali rappresenta un'operazione atomica (chiamata HTTP, query DB, operazione interna).

!!! note "Caratteristiche delle tracce"
    - **Contestuali per definizione**: collegano operazioni in servizi diversi
    - **Strutturate**: albero di span con relazioni parent-child
    - **Sampling-dipendenti**: in produzione non si conservano tutte le tracce (troppo costoso)
    - **Essenziali per i microservizi**: senza tracce, è impossibile capire dove si perde tempo

**Anatomia di una traccia:**

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736

└── [0ms - 450ms]  Span: api-gateway → POST /checkout
    ├── [10ms - 50ms]   Span: auth-service → validateToken
    ├── [55ms - 200ms]  Span: cart-service → getCart
    │   └── [60ms - 190ms]  Span: redis → GET cart:usr-4821
    └── [205ms - 440ms] Span: payment-service → processPayment
        ├── [210ms - 380ms] Span: payment-provider → chargeCard  ← COLLO DI BOTTIGLIA
        └── [385ms - 435ms] Span: db → INSERT orders
```

**Quando usare le tracce:**
- Identificare il collo di bottiglia in una request lenta ("quale servizio aggiunge latenza?")
- Capire le dipendenze tra microservizi
- Analisi di latenza end-to-end
- Debug di errori che coinvolgono più servizi
- Ottimizzazione delle chiamate seriali vs parallele

**Quando NON usare le tracce:**
- Alerting su metriche aggregate → usa Prometheus
- Analisi di log di sistema (OS, infrastruttura) → usa i log
- Misurare utilizzo risorse → usa le metriche

---

## Architettura / Come Funziona

### Il Ciclo Completo di Osservabilità

In un sistema cloud-native, i tre segnali vengono generati, raccolti, archiviati e visualizzati in pipeline separate ma correlate:

```
Applicazioni / Infrastruttura
       │
       ├── Metriche ──────────────────▶ Prometheus / VictoriaMetrics
       │   (es. /metrics endpoint,      (TSDB, scraping)
       │    OTel SDK Meters)                    │
       │                                        ▼
       ├── Log ───────────────────────▶ Loki / Elasticsearch
       │   (stdout, structured JSON,    (indicizzazione, full-text search)
       │    OTel SDK Loggers)                   │
       │                                        ▼
       └── Tracce ────────────────────▶ Jaeger / Grafana Tempo
           (OTel SDK Tracers,           (storage tracce, visualizzazione)
            context propagation)                │
                                                ▼
                                         Grafana (dashboard unificata)
```

### Correlazione tra i Tre Segnali

Il valore massimo si ottiene **correlando** i segnali tra loro. La chiave è il **trace ID**: includendolo nei log e nelle metriche, si passa fluidamente da un segnale all'altro.

**Esempio di flusso di investigazione:**

```
1. Alert su metrica:
   payment_errors_total > 10/min  ← Prometheus mi avvisa

2. Vado sul dashboard Grafana:
   error_rate del payment-service è salito alle 14:30

3. Cerco i log di quel servizio in Loki:
   {service="payment-service"} |= "ERROR" | start="14:29" | end="14:35"
   → Trovo: "Payment processing failed" con trace_id=abc123

4. Apro la traccia in Tempo:
   trace_id=abc123
   → La chiamata a payment-provider.chargeCard dura 8s invece di 300ms

5. Conclusione: il provider esterno ha avuto un degradation
   Tutto in 5 minuti, senza dover deployare nulla.
```

### Overhead e Sampling

Ogni segnale ha un costo diverso:

| Segnale | Volume tipico | Costo storage | Costo computazionale |
|---------|--------------|---------------|----------------------|
| Metriche | Basso (aggregato) | Basso | Basso |
| Log | Alto | Medio-Alto | Medio |
| Tracce | Molto alto (raw) | Alto | Alto |

Per le tracce in produzione si usa il **sampling**:
- **Head-based**: decisione al primo span della trace (efficiente, perde errori rari)
- **Tail-based**: decisione dopo aver ricevuto la trace completa (conserva gli errori, più costoso)

---

## Configurazione & Pratica

### Framework di Decisione: quale segnale usare?

```
Domanda                                          → Segnale
──────────────────────────────────────────────────────────────
"Il sistema funziona?" (yes/no, trending)        → Metriche
"Quanti errori/secondo nell'ultima ora?"         → Metriche
"Quale percentile di latenza stiamo rispettando?"→ Metriche
"Dove si è rotto esattamente questo fallimento?" → Log
"Quale stack trace ha generato quell'errore?"   → Log
"Chi ha chiamato quella API alle 14:32?"         → Log
"Quale microservizio rallenta questa request?"   → Tracce
"Perché questa transazione impiega 3 secondi?"   → Tracce
"Quante chiamate seriali vs parallele ci sono?"  → Tracce
```

### Struttura Minima Raccomandata per un Servizio

```yaml
# Ogni microservizio in produzione dovrebbe emettere:

# 1. METRICHE (via Prometheus/OTel)
# - http_requests_total{method, path, status}
# - http_request_duration_seconds (histogram)
# - business_metric (es. orders_processed_total)

# 2. LOG STRUTTURATI (JSON su stdout)
# - level: DEBUG/INFO/WARNING/ERROR
# - message: human-readable
# - trace_id: correlazione con le tracce (fondamentale!)
# - service, version, environment
# - context specifico dell'operazione

# 3. TRACCE (via OTel SDK)
# - Span per ogni operazione significativa (>5ms)
# - Attributi: http.method, db.statement, user.id
# - Status: OK / ERROR con messaggio
# - Link al log correlato tramite trace_id
```

### Structured Logging con Correlazione Tracce

```go
// Go — log strutturato con trace_id automatico da OTel
import (
    "go.opentelemetry.io/otel/trace"
    "log/slog"
)

func processPayment(ctx context.Context, orderID string) error {
    // Estrae trace_id e span_id dal context OTel
    span := trace.SpanFromContext(ctx)
    spanCtx := span.SpanContext()

    logger := slog.With(
        "trace_id", spanCtx.TraceID().String(),
        "span_id",  spanCtx.SpanID().String(),
        "service",  "payment-service",
        "order_id", orderID,
    )

    logger.InfoContext(ctx, "Processing payment started")

    result, err := chargeCard(ctx, orderID)
    if err != nil {
        logger.ErrorContext(ctx, "Payment failed",
            "error", err.Error(),
            "provider", "stripe",
        )
        return err
    }

    logger.InfoContext(ctx, "Payment successful",
        "transaction_id", result.TransactionID,
        "amount_cents",   result.AmountCents,
    )
    return nil
}
```

### Emissione Metriche RED (Rate, Errors, Duration)

```python
# Python — metriche RED con OpenTelemetry SDK
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
import time

meter = metrics.get_meter("payment-service")

# Rate: richieste totali
requests_counter = meter.create_counter(
    "payment_requests_total",
    description="Total payment requests",
    unit="1",
)

# Errors: fallimenti
errors_counter = meter.create_counter(
    "payment_errors_total",
    description="Total payment errors",
    unit="1",
)

# Duration: latenza in histogram
duration_histogram = meter.create_histogram(
    "payment_duration_seconds",
    description="Payment processing duration",
    unit="s",
)

def process_payment(order_id: str, provider: str):
    start = time.time()
    labels = {"provider": provider, "service": "payment"}

    requests_counter.add(1, labels)
    try:
        result = _charge_card(order_id)
        return result
    except Exception as e:
        errors_counter.add(1, {**labels, "error_type": type(e).__name__})
        raise
    finally:
        duration = time.time() - start
        duration_histogram.record(duration, labels)
```

### I Four Golden Signals (Google SRE)

Google SRE ha identificato quattro metriche fondamentali applicabili a qualsiasi servizio:

```
LATENCY   — Tempo di risposta delle richieste (separare successi ed errori)
TRAFFIC   — Domanda sul sistema (RPS, query/s, transazioni/s)
ERRORS    — Tasso di richieste fallite (esplicite 5xx, implicite, per policy)
SATURATION — Quanto il servizio è "pieno" (CPU, RAM, queue depth, connessioni)
```

```promql
# PromQL per i Four Golden Signals

# LATENCY — p99 in finestra 5 minuti
histogram_quantile(0.99,
  sum by (le, service) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)

# TRAFFIC — richieste per secondo
sum by (service) (rate(http_requests_total[1m]))

# ERRORS — error rate percentuale
sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
/
sum by (service) (rate(http_requests_total[5m])) * 100

# SATURATION — CPU in uso
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

---

## Best Practices

!!! tip "Includi sempre il trace_id nei log"
    Il trace_id è il ponte tra log e tracce. Senza di esso, quando un alert Prometheus ti porta a cercare i log, non puoi passare dalla riga di log alla traccia corrispondente. La correlazione è il moltiplicatore di valore dell'osservabilità.

!!! tip "Usa il metodo RED per i microservizi, USE per l'infrastruttura"
    - **RED** (Rate, Errors, Duration): per servizi e API — "quante richieste, quanti errori, quanto tempo"
    - **USE** (Utilization, Saturation, Errors): per risorse hardware — "quanto è utilizzato, quanto è saturo, quanti errori hardware"

!!! warning "Non loggare ogni metrica come log"
    Un antipattern comune è emettere log del tipo `"request completed in 342ms"` per poi parsarli in Grafana/Loki per costruire grafici di latenza. È costoso e impreciso. Usa le metriche (histogram) per la latenza, e i log per gli eventi significativi con contesto.

!!! warning "Attenzione alla label cardinality nelle metriche"
    Le label ad alta cardinalità (user_id, order_id, IP) trasformano una time series in milioni di time series. In Prometheus questo causa TSDB saturo e query lente. Valori ad alta cardinalità appartengono ai log (dove ogni evento è indipendente), non alle metriche.

**Pattern consigliati:**
- Structured logging in JSON ovunque — mai log non strutturati in produzione
- Sampling delle tracce: 10-20% in produzione per traffico normale, 100% per errori (tail-based)
- Un `trace_id` per ogni request boundary (HTTP, gRPC, message queue consumer)
- Retention differenziata: metriche 90+ giorni, log 30 giorni, tracce 7-14 giorni
- Dashboard "1 pane of glass" in Grafana che combina tutti e tre i segnali

**Anti-pattern da evitare:**
- Strumenti diversi e non integrati (metriche in Datadog, log in Splunk, tracce in Zipkin senza correlazione)
- Log non strutturati che richiedono regex per essere interrogati
- Nessun sampling sulle tracce in produzione → OOME del backend
- Alert solo su log (alta latenza, rumore) invece di metriche

---

## Troubleshooting

**Scenario 1: Alert "Error rate alto" ma non capisco quale componente**

```
Sintomo: alert Prometheus "error_rate > 5%" su payment-service
Causa:   il servizio coinvolge 4 microservizi — non so quale fallisce

Soluzione:
1. Apri Grafana → dashboard payment-service → guarda breakdown errori per span
2. Cerca in Loki: {service="payment-service"} |= "ERROR" | json | line_format "{{.error}}"
3. Prendi il trace_id dall'output del log
4. Apri Grafana Tempo con quel trace_id
5. Identifica quale span ha status=ERROR → è il componente che fallisce

Comandi:
# Loki query per errori recenti con trace_id
{service="payment-service"} |= "ERROR" | json | line_format "{{.timestamp}} {{.trace_id}} {{.error}}"
```

**Scenario 2: Latenza alta ma metriche aggregate sembrano normali**

```
Sintomo: utenti si lamentano di lentezza, ma p99 su Prometheus è OK
Causa:   il problema riguarda un sottoinsieme di utenti (alta cardinalità)

Soluzione:
- Le metriche aggregate nascondono sottoset di traffico — è un limite del modello
- Cerca in Loki i log con duration_ms > 2000 per identificare i pattern
- Cerca in Tempo le tracce con latenza > 2s (Tempo supporta search per durata)

Query Loki:
{service="api"} | json | duration_ms > 2000 | line_format "{{.user_id}} {{.path}} {{.duration_ms}}ms"

Query Tempo:
minDuration=2s, service=api
```

**Scenario 3: Log troppo voluminosi, storage in crescita esponenziale**

```
Sintomo: Loki storage cresce di 50GB/giorno, costi fuori controllo
Causa:   log a livello DEBUG in produzione, o log di metriche che non appartengono ai log

Soluzione:
1. Identifica i servizi più prolissi:
   # In Loki/Grafana: topk(10, sum by (service) (rate({} [5m])))

2. Per ogni servizio problematico:
   - Alzare il log level a INFO o WARNING in produzione
   - Convertire i log periodici in metriche (es. "request completed in Xms" → histogram)
   - Usare sampling sul log level DEBUG (es. 1% in produzione)

3. Configura retention per log level:
   - ERROR/WARNING: 90 giorni
   - INFO: 30 giorni
   - DEBUG: 7 giorni (se proprio necessario in prod)
```

**Scenario 4: Tracce incomplete — alcuni span mancano**

```
Sintomo: le tracce mostrano gap (es. il span del DB non appare)
Causa:   il context OTel non viene propagato correttamente attraverso i layer

Soluzioni possibili:
a) Libreria non instrumentata: verifica che l'SDK OTel supporti il driver DB in uso
   (es. psycopg2 per Postgres richiede opentelemetry-instrumentation-psycopg2)

b) Context non propagato: il thread/goroutine che fa la query non riceve il context OTel
   → In Go: assicurarsi di passare ctx a tutte le funzioni downstream
   → In Java: usare MDC + OTel context propagation

c) Sampling aggressivo: la traccia è stata droppa dal sampler
   → Abbassa il sampling rate o usa tail-based sampling nel Collector

Verifica:
kubectl logs deploy/otel-collector | grep "dropped"
curl http://otel-collector:8888/metrics | grep otelcol_processor_dropped
```

---

## Relazioni

I tre pilastri sono concetti fondamentali; gli strumenti che li implementano sono argomenti correlati:

??? info "OpenTelemetry — Standard di Strumentazione"
    OTel è il framework unificato per emettere tutti e tre i segnali in modo vendor-neutral. SDK, Collector, OTLP.

    **Approfondimento completo →** [OpenTelemetry](./opentelemetry.md)

??? info "Prometheus — Backend per le Metriche"
    Prometheus è il sistema di raccolta e query per le metriche. PromQL, alerting rules, scraping.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Loki — Backend per i Log"
    Loki aggrega e indicizza i log con un modello simile a Prometheus (label-based, non full-text).

    **Approfondimento completo →** [Loki](../tools/loki.md)

??? info "Jaeger / Grafana Tempo — Backend per le Tracce"
    Backend per lo storage e la visualizzazione delle tracce distribuite. Jaeger è il più maturo, Tempo è integrato in Grafana.

    **Approfondimento completo →** [Jaeger e Tempo](../tools/jaeger-tempo.md)

??? info "SLO/SLA/SLI — Reliability Engineering"
    Gli SLI sono metriche specifiche scelte dai tre pilastri per rappresentare l'affidabilità dal punto di vista utente.

    **Approfondimento completo →** [SLO/SLA/SLI](../sre/slo-sla-sli.md)

---

## Riferimenti

- [OpenTelemetry — Observability Primer](https://opentelemetry.io/docs/concepts/observability-primer/)
- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Grafana — The Three Pillars of Observability](https://grafana.com/blog/2019/10/21/whats-next-for-observability/)
- [Cindy Sridharan — Distributed Systems Observability (O'Reilly)](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/)
- [Brendan Gregg — USE Method](https://www.brendangregg.com/usemethod.html)
- [Tom Wilkie — RED Method](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/)
