---
title: "Jaeger & Grafana Tempo"
slug: jaeger-tempo
category: monitoring
tags: [tracing, distributed-tracing, observability, jaeger, tempo, grafana, cncf, opentelemetry]
search_keywords: [Jaeger, Tempo, Grafana Tempo, distributed tracing, tracce distribuite, tracciamento, tracing backend, OTLP, OpenTelemetry backend, Zipkin, spans, trace ID, sampling, tail-based sampling, head-based sampling, TraceQL, Jaeger UI, observability, osservabilità, microservices tracing, request tracing]
parent: monitoring/tools
related: [monitoring/fondamentali/opentelemetry, monitoring/tools/prometheus, monitoring/tools/grafana, monitoring/tools/loki, networking/service-mesh/istio]
official_docs: https://www.jaegertracing.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Jaeger & Grafana Tempo

## Panoramica

**Jaeger** e **Grafana Tempo** sono i due principali backend open-source per il distributed tracing. Entrambi ricevono tracce da applicazioni instrumentate (tramite OpenTelemetry, Zipkin o SDK nativi), le conservano e le rendono interrogabili per il debugging di sistemi distribuiti.

- **Jaeger** (CNCF Graduated) è il sistema di tracing storico, nato in Uber nel 2016. Ha una UI integrata potente, supporto nativo per Zipkin e un'architettura ricca di componenti.
- **Grafana Tempo** è il backend di tracing di Grafana Labs, progettato per essere estremamente economico da scalare (storage su object storage come S3), integrato nativamente con Grafana e Loki.

Si usano quando occorre analizzare la latenza di singole richieste attraverso più microservizi, trovare colli di bottiglia, correlare errori con percorsi specifici di esecuzione. Non sostituiscono i sistemi di metriche (Prometheus) né i log aggregati (Loki): i tre segnali sono complementari.

## Concetti Chiave

!!! note "Anatomia di una Traccia"
    Una **traccia** è l'insieme di tutte le operazioni eseguite per servire una singola richiesta:

    - **Trace**: l'intera operazione end-to-end, identificata da un `trace_id` univoco
    - **Span**: singola unità di lavoro (es. chiamata HTTP, query DB), con timestamp di inizio/fine
    - **Parent Span / Child Span**: gli span formano un albero che rappresenta il flusso causale
    - **Baggage / Context Propagation**: metadati propagati lungo la catena di chiamate (W3C TraceContext)

### Sampling

Il sampling controlla quante tracce vengono effettivamente registrate — catturare il 100% su sistemi ad alto traffico è proibitivo:

| Strategia | Descrizione | Quando usare |
|---|---|---|
| **Head-based (probabilistico)** | Decisione presa all'inizio della richiesta, es. "1% delle richieste" | Produzione ad alto volume, overhead minimo |
| **Head-based (rate limiting)** | Max N tracce/secondo indipendentemente dal traffico | Carico variabile |
| **Tail-based** | Decisione presa a fine richiesta, può selezionare tracce con errori o alta latenza | Debugging mirato, richiede buffer |
| **Always-on** | 100% delle tracce | Sviluppo, staging, traffico molto basso |

---

## Jaeger

### Architettura

```
Applicazioni (SDK OTel / Zipkin)
        │
        ▼ OTLP / Jaeger Protocol
┌─────────────────┐
│  Jaeger Collector│  ← riceve, valida, processa gli span
└────────┬────────┘
         │
    ┌────┴────┐
    │ Storage  │  ← Cassandra, Elasticsearch, OpenSearch, Badger (in-memory)
    └────┬────┘
         │
┌────────┴────────┐
│   Jaeger Query  │  ← API + Jaeger UI
└─────────────────┘
```

**Componenti principali:**

- **Jaeger Collector**: riceve span via gRPC (OTLP), Thrift/HTTP, Zipkin. Valida e scrive sullo storage.
- **Jaeger Query**: espone le REST/gRPC API e la UI web per la ricerca tracce.
- **Jaeger Agent** *(deprecato in favore dell'OTel Collector)*: demone locale che riceveva span e li inoltrava al collector.
- **Jaeger All-in-One**: immagine Docker che raggruppa tutti i componenti con storage in-memory (solo per sviluppo).

### Storage Backend

```yaml
# Configurazione Elasticsearch (produzione)
SPAN_STORAGE_TYPE: elasticsearch
ES_SERVER_URLS: http://elasticsearch:9200
ES_NUM_SHARDS: 5
ES_NUM_REPLICAS: 1
```

| Storage | Caso d'uso |
|---|---|
| **Badger** (in-memory/local) | Sviluppo, test |
| **Elasticsearch / OpenSearch** | Produzione, ricerca full-text sulle tracce |
| **Cassandra** | Produzione, alta scalabilità write |

### Deploy con Docker Compose

```yaml
version: "3.8"
services:
  jaeger:
    image: jaegertracing/all-in-one:1.57
    ports:
      - "16686:16686"   # Jaeger UI
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
      - "14268:14268"   # Jaeger HTTP (Thrift)
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
```

### Configurazione OpenTelemetry → Jaeger

```yaml
# otel-collector-config.yaml
exporters:
  otlp/jaeger:
    endpoint: "jaeger:4317"
    tls:
      insecure: true

service:
  pipelines:
    traces:
      exporters: [otlp/jaeger]
```

### Jaeger UI — Funzionalità Principali

- **Search**: ricerca per servizio, operazione, tag, durata, trace ID
- **Trace Timeline**: visualizzazione a cascata degli span (Gantt-like)
- **Trace Graph**: visualizzazione DAG del flusso tra servizi
- **Compare**: confronto side-by-side di due tracce
- **System Architecture**: mappa dei servizi e dipendenze (deriva dalle tracce)

---

## Grafana Tempo

### Filosofia e Differenze da Jaeger

Tempo è progettato attorno a un principio: **lo storage delle tracce deve essere economico quanto lo storage di log**.

| Caratteristica | Jaeger | Grafana Tempo |
|---|---|---|
| Storage | Elasticsearch / Cassandra (costoso) | Object storage: S3, GCS, Azure Blob (economico) |
| Ricerca | Full-text sui tag | Per trace ID (nativa) + ricerca tag opzionale via indice |
| UI | Jaeger UI dedicata | Grafana Explore |
| Query Language | Nessuno (filtri UI) | **TraceQL** |
| Integrazione Loki | Manuale | Nativa (trace ID nei log → traccia in un click) |
| Integrazione Prometheus | Manuale | **Span Metrics** automatici |

### Architettura

```
Applicazioni (OTel Collector)
        │
        ▼ OTLP gRPC/HTTP
┌──────────────────┐
│  Tempo Distributor│  ← riceve e partiziona gli span
└────────┬─────────┘
         │
┌────────┴─────────┐
│  Tempo Ingester  │  ← bufferizza in memoria, scrive su object storage
└────────┬─────────┘
         │
  ┌──────┴──────┐
  │  S3 / GCS   │  ← parquet files (trace data)
  └──────┬──────┘
         │
┌────────┴─────────┐
│  Tempo Querier   │  ← esegue query TraceQL, legge da S3
└────────┬─────────┘
         │
  ┌──────┴──────┐
  │   Grafana   │  ← visualizzazione in Explore
  └─────────────┘
```

**Nota:** per deployment semplice esiste `tempo` monolitico (single binary), per produzione scalabile si usa la modalità distribuita.

### Deploy Monolitico con Docker Compose

```yaml
version: "3.8"
services:
  tempo:
    image: grafana/tempo:2.4.0
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
      - tempo-data:/var/tempo
    ports:
      - "3200:3200"   # Tempo HTTP API
      - "4317:4317"   # OTLP gRPC

volumes:
  tempo-data:
```

```yaml
# tempo.yaml — configurazione minimale
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
        http:

ingester:
  max_block_duration: 5m

compactor:
  compaction:
    block_retention: 1h   # retention delle tracce

storage:
  trace:
    backend: local         # usare s3/gcs in produzione
    local:
      path: /var/tempo/blocks
    wal:
      path: /var/tempo/wal
```

### TraceQL

TraceQL è il linguaggio di query nativo di Tempo, ispirato a LogQL e PromQL:

```
# Tutti gli span con errore del servizio "frontend"
{ resource.service.name = "frontend" && status = error }

# Span con durata > 500ms
{ duration > 500ms }

# Tracce che attraversano il servizio "payment" con errori
{ resource.service.name = "payment" && status = error } | count() > 0

# Span HTTP con status 500 e path specifico
{ span.http.status_code = 500 && span.http.url =~ "/api/checkout.*" }

# Selezionare span figli di operazioni lente
{ .db.system = "postgresql" && duration > 200ms }
```

### Integrazione con Loki (Trace-to-Log)

```yaml
# Configurazione datasource Tempo in Grafana
datasources:
  - name: Tempo
    type: tempo
    url: http://tempo:3200
    jsonData:
      tracesToLogsV2:
        datasourceUid: loki    # UID del datasource Loki
        spanStartTimeShift: "-5m"
        spanEndTimeShift: "5m"
        tags:
          - key: service.name
            value: service
      serviceMap:
        datasourceUid: prometheus
      nodeGraph:
        enabled: true
```

Con questa configurazione, da una traccia in Grafana Explore è possibile navigare direttamente ai log correlati in Loki tramite il `trace_id`.

### Span Metrics (RED Metrics automatici)

Tempo può generare automaticamente metriche RED (Rate, Error, Duration) da ogni span ricevuto:

```yaml
# In metrics-generator di Tempo
metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
  processors:
    - service-graphs    # grafo delle dipendenze tra servizi
    - span-metrics      # metriche RED per ogni operazione
```

Questo elimina la necessità di instrumentare manualmente le metriche per ogni servizio.

---

## Best Practices

!!! tip "Scegliere tra Jaeger e Tempo"
    - **Jaeger** se: hai già Elasticsearch/Cassandra, vuoi una UI dedicata al tracing, hai bisogno di ricerche full-text complesse sui tag.
    - **Tempo** se: vuoi minimizzare i costi di storage (usa S3), sei già nell'ecosistema Grafana (Loki, Prometheus), vuoi TraceQL e la correlazione automatica log-trace-metriche.

!!! warning "Sampling in Produzione"
    Non deployare mai con `AlwaysOn` sampling in produzione ad alto traffico. Il volume di tracce può saturare lo storage e la rete. Configurare **head-based probabilistic sampling** (es. 1-10%) nell'OTel Collector, riservando **tail-based sampling** solo per tracce con errori o alta latenza.

!!! tip "OTel Collector come Gateway"
    Non inviare mai le tracce direttamente dall'applicazione a Jaeger/Tempo in produzione. Usare sempre un **OTel Collector** come intermediario: gestisce buffering, retry, sampling, e permette di cambiare backend senza modificare le applicazioni.

```yaml
# Anti-pattern: applicazione → Jaeger direttamente
# Pattern corretto: applicazione → OTel Collector → Jaeger/Tempo
exporters:
  otlp:
    endpoint: "otel-collector:4317"   # OTel Collector, non Jaeger/Tempo
```

!!! tip "Retention e Costi"
    Le tracce hanno valore decrescente nel tempo. Configurare retention breve (1-7 giorni) per ridurre i costi di storage. Per analisi storiche usare le **Span Metrics** di Tempo (metriche aggregate in Prometheus che durano più a lungo).

## Troubleshooting

| Problema | Causa Probabile | Soluzione |
|---|---|---|
| Tracce non visibili in UI | Sampling troppo basso, errore export | Verificare log OTel Collector, testare con `AlwaysOn` temporaneamente |
| Trace ID non correla log e tracce | `trace_id` non propagato nei log | Configurare OTel SDK per iniettare `trace_id` nei log strutturati |
| Alta latenza query Jaeger | Elasticsearch non ottimizzato | Aumentare shards, usare indici ILM, ottimizzare query per range temporale |
| Tempo: "trace not found" | Block non ancora compattato | Attendere ciclo di compaction (default 5m), verificare configurazione WAL |
| Span orfani (senza trace parent) | Context propagation mancante | Verificare header W3C TraceContext nelle chiamate HTTP/gRPC |
| Memory spike nel Collector | Buffer tail-based sampling pieno | Aumentare `num_traces` o ridurre `decision_wait` nella config tail sampling |

## Relazioni

??? info "OpenTelemetry — Standard di Instrumentazione"
    Jaeger e Tempo sono backend passivi: ricevono tracce da sistemi già instrumentati con OpenTelemetry. OTel definisce il formato (OTLP), gli SDK per ogni linguaggio, e il Collector per routing e processing.

    **Approfondimento completo →** [OpenTelemetry](../fondamentali/opentelemetry.md)

??? info "Grafana — Visualizzazione"
    Tempo è progettato per essere la sorgente dati di tracing in Grafana. La navigazione trace-to-log (Loki) e trace-to-metrics (Prometheus) si configura nei datasource di Grafana.

    **Approfondimento completo →** [Grafana](./grafana.md)

??? info "Loki — Correlazione Log-Trace"
    Con Tempo e Loki configurati insieme in Grafana, è possibile navigare da un log con `trace_id` direttamente alla traccia corrispondente e viceversa.

    **Approfondimento completo →** [Loki](./loki.md)

??? info "Istio — Tracing nei Service Mesh"
    Istio può generare automaticamente span per ogni chiamata tra microservizi, senza modificare il codice applicativo. Il backend di tracing configurabile è Jaeger o qualsiasi endpoint OTLP (quindi anche Tempo).

    **Approfondimento completo →** [Istio](../../networking/service-mesh/istio.md)

## Riferimenti

- [Documentazione ufficiale Jaeger](https://www.jaegertracing.io/docs/)
- [Documentazione ufficiale Grafana Tempo](https://grafana.com/docs/tempo/latest/)
- [TraceQL Reference](https://grafana.com/docs/tempo/latest/traceql/)
- [OpenTelemetry Collector — Jaeger Exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/jaegerexporter)
- [Jaeger vs Tempo — Confronto architetturale](https://grafana.com/blog/2021/04/13/how-we-designed-grafana-tempos-architecture-to-cut-tracing-costs-by-10x/)
- [Distributed Tracing — Google Dapper Paper](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/)
