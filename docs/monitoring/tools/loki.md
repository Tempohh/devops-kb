---
title: "Loki — Log Aggregation"
slug: loki
category: monitoring
tags: [loki, logs, log-aggregation, grafana, logql, promtail, plg-stack]
search_keywords: [loki, log aggregation, log centralized, logql, promtail, grafana loki, plg stack, log management, logging, logs centrali, log pipeline, fluentd, fluent bit, vector, retention log, label log]
parent: monitoring/tools/_index
related: [monitoring/tools/grafana, monitoring/tools/prometheus, monitoring/fondamentali/opentelemetry, monitoring/alerting/alertmanager, networking/kubernetes/_index]
official_docs: https://grafana.com/docs/loki/latest/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Loki — Log Aggregation

## Panoramica

Loki è il sistema di log aggregation cloud-native sviluppato da Grafana Labs, progettato per essere il complemento "economico" di Prometheus nel mondo dei log. A differenza di Elasticsearch (che fa full-text indexing di ogni campo), Loki indicizza **solo le labels** dei log e comprime il contenuto del log grezzo. Questo lo rende molto più economico in termini di storage e computazione, al prezzo di query full-text meno potenti. Loki è la componente "L" dello stack **PLG** (Prometheus + Loki + Grafana) e si integra nativamente con Grafana, permettendo di passare da una metrica anomala al log corrispondente in un click.

## Concetti Chiave

### Modello Dati

Loki usa lo stesso modello a labels di Prometheus per identificare i log stream.

```
Log stream = {app="nginx", namespace="production", pod="nginx-7d4b8c-x2k9p"}
```

!!! note "Differenza chiave vs Elasticsearch"
    Elasticsearch indicizza il contenuto di ogni log line (full-text search).
    Loki indicizza **solo le labels** e il timestamp. Il contenuto viene compresso e memorizzato.
    **Vantaggio**: 10-100x meno storage e costo. **Svantaggio**: query su contenuto più lente.

### Labels

Le labels identificano un **log stream**. Ogni combinazione unica di labels = uno stream distinto.

!!! warning "Cardinality delle labels"
    Come Prometheus, alta cardinalità nelle labels (user_id, request_id) causa un'esplosione di stream e degrada le performance. Usare le labels SOLO per dimensioni di routing (app, namespace, pod, env). I valori ad alta cardinalità vanno nel contenuto del log, filtrabile con LogQL.

### LogQL

LogQL è il linguaggio di query di Loki, ispirato a PromQL.

```logql
# Selettore base (log stream selector)
{app="nginx", namespace="production"}

# Filtro sul contenuto
{app="nginx"} |= "error"          # contiene "error"
{app="nginx"} != "health-check"   # non contiene "health-check"
{app="nginx"} |~ "ERROR|CRITICAL" # regex match
{app="nginx"} !~ "GET /health"    # regex no-match

# Parsing JSON
{app="api"} | json | status >= 500

# Parsing logfmt
{app="api"} | logfmt | duration > 1s

# Parsing con pattern
{app="nginx"} | pattern `<ip> - - [<_>] "<method> <path> <_>" <status> <bytes>`
              | status >= 500

# Metric queries (aggregazioni)
# Rate di log per minuto
rate({app="nginx"}[5m])

# Contare errori per pod
sum by (pod) (count_over_time({app="nginx"} |= "error" [5m]))

# Quantità di bytes ingestiti
bytes_rate({app="nginx"}[5m])
```

## Architettura / Come Funziona

```
┌──────────────────────────────────────────────────────────────┐
│                    Loki Architecture                          │
│                                                                │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐    │
│  │  Promtail  │  │ Fluent Bit │  │  OpenTelemetry      │    │
│  │  (agent)   │  │  (agent)   │  │  Collector          │    │
│  └─────┬──────┘  └─────┬──────┘  └──────────┬──────────┘    │
│        └───────────────┴────────────────────┘│               │
│                                               ▼               │
│                              ┌────────────────────────┐      │
│                              │    Loki Distributor     │      │
│                              └───────────┬────────────┘      │
│                                          │                    │
│                    ┌─────────────────────┼──────────────┐    │
│                    ▼                     ▼               ▼    │
│             ┌──────────┐         ┌──────────┐    ┌──────────┐│
│             │ Ingester  │         │ Ingester  │    │ Ingester ││
│             └──────┬───┘         └──────┬───┘    └──────┬───┘│
│                    │                    │                │    │
│             ┌──────▼────────────────────▼────────────────▼──┐│
│             │               Object Storage                    ││
│             │            (S3, GCS, Azure Blob)               ││
│             └─────────────────────────────────────────────────┘│
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Loki Querier                            │  │
│  │  (legge da Object Storage + Ingester in-memory)         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
              ▲
              │ LogQL queries
              │
         ┌────┴────┐
         │ Grafana  │
         └──────────┘
```

### Componenti Principali

| Componente | Ruolo |
|------------|-------|
| **Distributor** | Riceve log dagli agent, valida labels, distribuisce agli ingester |
| **Ingester** | Buffer in-memory dei log recenti, scrittura su Object Storage |
| **Querier** | Esegue le query LogQL su Object Storage + Ingester |
| **Query Frontend** | Sharding e caching delle query, riduce carico sui Querier |
| **Compactor** | Compatta i chunk su Object Storage per ottimizzare storage e query |

### Chunk e Index

Loki suddivide i log in **chunk** compressi (GZIP/Snappy) per log stream. L'indice mappa le labels ai chunk, ma il contenuto non è indicizzato.

## Configurazione & Pratica

### Deploy con Docker Compose (Stack PLG)

```yaml
# docker-compose.yml
version: '3.8'
services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml
      - loki-data:/loki

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - /var/log:/var/log:ro
      - ./promtail-config.yaml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml

  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin

volumes:
  loki-data:
```

### Configurazione Loki

```yaml
# loki-config.yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  ingestion_rate_mb: 16
  ingestion_burst_size_mb: 32
  max_entries_limit_per_query: 5000
  retention_period: 720h  # 30 giorni

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
```

### Configurazione Loki su S3 (produzione)

```yaml
# loki-config-prod.yaml
auth_enabled: true

storage_config:
  aws:
    s3: s3://eu-west-1/loki-chunks
    s3forcepathstyle: false
  tsdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
    cache_ttl: 168h
    shared_store: s3

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: loki_index_
        period: 24h

limits_config:
  retention_period: 2160h  # 90 giorni
  ingestion_rate_mb: 64
  ingestion_burst_size_mb: 128
```

### Configurazione Promtail

Promtail è l'agent che raccoglie i log dai file e li invia a Loki.

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push
    tenant_id: "tenant1"  # solo se auth_enabled

scrape_configs:
  # Log di sistema
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/**/*.log

  # Log Docker container
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'logstream'
      # Aggiungere le labels Docker come label Loki
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: 'service'
    pipeline_stages:
      # Parsing JSON logs
      - json:
          expressions:
            level: level
            msg: message
            timestamp: time
      - labels:
          level:
      - timestamp:
          source: timestamp
          format: RFC3339Nano
```

### Deploy su Kubernetes con Helm

```bash
# Stack completo: Loki + Promtail + Grafana
helm repo add grafana https://grafana.github.io/helm-charts

# Installare Loki (modalità single-binary per ambienti piccoli)
helm install loki grafana/loki \
  --namespace monitoring \
  --create-namespace \
  --set loki.auth_enabled=false \
  --set loki.commonConfig.replication_factor=1 \
  --set loki.storage.type=filesystem \
  --values loki-values.yaml

# Installare Promtail come DaemonSet
helm install promtail grafana/promtail \
  --namespace monitoring \
  --set config.clients[0].url=http://loki:3100/loki/api/v1/push
```

### Promtail come DaemonSet (Kubernetes)

```yaml
# promtail-daemonset-config.yaml
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    pipeline_stages:
      # Riconoscere e parsare log JSON
      - match:
          selector: '{app="api-service"}'
          stages:
            - json:
                expressions:
                  level: level
                  trace_id: traceId
                  duration_ms: durationMs
            - labels:
                level:
                trace_id:
            - metrics:
                http_response_time_ms:
                  type: Histogram
                  source: duration_ms
                  config:
                    buckets: [50, 100, 200, 500, 1000]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: drop
        regex: false
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_pod_container_name]
        target_label: container
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
```

### Fluent Bit come alternativa a Promtail

```ini
# fluent-bit.conf
[SERVICE]
    Flush 5
    Daemon Off
    Log_Level info

[INPUT]
    Name tail
    Tag kube.*
    Path /var/log/containers/*.log
    Parser docker
    DB /var/log/flb_kube.db
    Mem_Buf_Limit 50MB

[FILTER]
    Name kubernetes
    Match kube.*
    Kube_URL https://kubernetes.default.svc:443
    Merge_Log On
    K8S-Logging.Parser On

[OUTPUT]
    Name grafana-loki
    Match kube.*
    Host loki
    Port 3100
    Labels {job="fluentbit", cluster="prod"}
    Auto_Kubernetes_Labels On
```

## Best Practices

### Labels Efficaci

```yaml
# ✓ BUONE labels (bassa cardinalità, utili per routing)
labels:
  app: nginx
  namespace: production
  env: prod
  cluster: eu-west-1

# ✗ CATTIVE labels (alta cardinalità — non usare)
labels:
  request_id: "abc-123-def"   # UUID diverso per ogni log
  user_id: "12345"             # ogni utente = stream separato
  ip_address: "10.0.0.1"      # ogni IP = stream separato
```

### Pipeline Stages per Parsing

Strutturare i log come JSON dal lato applicativo rende il parsing triviale:

```json
{
  "level": "error",
  "timestamp": "2026-03-24T10:30:00Z",
  "message": "Connection refused",
  "service": "api",
  "trace_id": "abc123",
  "duration_ms": 1200
}
```

### Retention per Namespace

```yaml
# Retention diversa per namespace (Loki v2.7+)
limits_config:
  per_stream_rate_limit: 5MB
  per_stream_rate_limit_burst: 15MB

# Per retention per-tenant, usare auth_enabled + tenant-specific limits
```

## Troubleshooting

### Log Non Arrivano a Loki

```bash
# Verificare lo stato di Promtail
kubectl logs -n monitoring promtail-pod

# Verificare il positions file (offset di lettura)
cat /tmp/positions.yaml

# Test push manuale
curl -X POST http://loki:3100/loki/api/v1/push \
  -H "Content-Type: application/json" \
  -d '{"streams":[{"stream":{"app":"test"},"values":[["'$(date +%s%N)'","test log message"]]}]}'
```

### Query Lente

```logql
# ✓ Usare sempre il log stream selector per ridurre la scansione
{app="api", namespace="production"} |= "error"

# ✗ Non fare full scan su tutti gli stream
{} |= "error"  # scansiona TUTTI i log
```

### Out of Order Logs

Loki accetta log in ordine crescente di timestamp per stream. Se l'agent invia log fuori ordine:

```yaml
# promtail-config.yaml
clients:
  - url: http://loki:3100/loki/api/v1/push
    backoff_config:
      max_period: 5m
    timeout: 10s

# Abilitare il re-ordering nel server Loki
limits_config:
  unordered_writes: true  # solo Loki >= 2.4
```

## Relazioni

??? info "Grafana — Visualizzazione"
    Grafana è il frontend primario per Loki. Permette di correlare metriche Prometheus e log Loki nella stessa dashboard tramite il panel Logs.

    **Approfondimento completo →** [Grafana](./grafana.md)

??? info "Prometheus — Correlazione Metriche-Log"
    Nel modello Grafana, i trace ID nei log possono essere linkati alle metriche Prometheus per la correlazione (Exemplars).

    **Approfondimento completo →** [Prometheus](./prometheus.md)

??? info "OpenTelemetry — Pipeline Unificata"
    Il OTEL Collector può ricevere log in formato OTLP e inoltrarli a Loki tramite il Loki exporter.

    **Approfondimento completo →** [OpenTelemetry](../fondamentali/opentelemetry.md)

## Riferimenti

- [Documentazione ufficiale Grafana Loki](https://grafana.com/docs/loki/latest/)
- [LogQL reference](https://grafana.com/docs/loki/latest/query/)
- [Best practices labels](https://grafana.com/docs/loki/latest/best-practices/)
- [Loki Helm chart](https://github.com/grafana/helm-charts/tree/main/charts/loki)
- [Promtail configurazione](https://grafana.com/docs/loki/latest/send-data/promtail/)
- [Fluent Bit → Loki](https://docs.fluentbit.io/manual/pipeline/outputs/loki)
