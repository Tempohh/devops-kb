---
title: "Prometheus"
slug: prometheus
category: monitoring
tags: [prometheus, monitoring, metrics, alerting, tsdb, promql]
search_keywords: [prometheus, metriche, time series, tsdb, promql, alerting, scraping, exporter, grafana, monitoring, osservabilità, alertmanager, recording rules, federation, remote write]
parent: monitoring/tools/_index
related: [monitoring/tools/grafana, monitoring/alerting/alertmanager, monitoring/fondamentali/opentelemetry, monitoring/sre/slo-sla-sli, networking/kubernetes/_index]
official_docs: https://prometheus.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Prometheus

## Panoramica

Prometheus è un sistema di monitoraggio e alerting open-source, progetto CNCF graduated, diventato lo standard de-facto per il monitoring cloud-native. Nato in SoundCloud nel 2012 e donato alla CNCF nel 2016, è costruito attorno a un modello di dati time series con un potente linguaggio di query (PromQL). A differenza dei sistemi push-based, Prometheus usa un modello **pull**: scraping periodico degli endpoint HTTP `/metrics` esposti dai target. È particolarmente adatto per microservizi, Kubernetes e ambienti dinamici dove i target cambiano continuamente.

## Concetti Chiave

!!! note "Modello dati"
    Ogni time series è identificata da un **metric name** e da un set di **labels** (coppie chiave-valore).
    Esempio: `http_requests_total{method="POST", status="200", service="api"}`

### Tipi di Metriche

| Tipo | Descrizione | Uso tipico |
|------|-------------|------------|
| **Counter** | Valore monotonicamente crescente | Request count, error count, bytes inviati |
| **Gauge** | Valore che può salire e scendere | CPU usage, memoria in uso, connessioni attive |
| **Histogram** | Campioni in bucket predefiniti + somma + count | Latenza, dimensione richieste |
| **Summary** | Quantili calcolati lato client + somma + count | Latenza con percentili precisi |

!!! tip "Counter vs Gauge"
    Usa **Counter** per tutto ciò che si incrementa nel tempo (eventi, bytes). Usa **Gauge** per stati correnti (utilizzo, code, flag). Non confondere i due: un Counter che si azzera al restart è normale; un Gauge che va a zero è un segnale d'allarme.

### Labels

Le labels sono il meccanismo di dimensionalità di Prometheus. Permettono di filtrare, aggregare e raggruppare le metriche.

```promql
# Filtrare per label specifica
http_requests_total{service="api", status=~"5.."}

# Aggregare eliminando una dimensione
sum by (service) (rate(http_requests_total[5m]))
```

!!! warning "Label cardinality"
    Ogni combinazione unica di label values crea una time series distinta. Non usare mai come label valori ad alta cardinalità (user ID, IP, UUID). Questo causa un'esplosione del numero di time series e degrada le prestazioni del TSDB.

## Architettura / Come Funziona

```
┌─────────────────────────────────────────────────────┐
│                   Prometheus Server                  │
│                                                       │
│  ┌──────────────┐    ┌──────────────┐               │
│  │   Retrieval  │    │   TSDB       │               │
│  │  (Scraper)   │───▶│  (Storage)   │               │
│  └──────┬───────┘    └──────┬───────┘               │
│         │                   │                        │
│  ┌──────▼───────┐    ┌──────▼───────┐               │
│  │   Service    │    │  HTTP API /  │               │
│  │  Discovery   │    │  PromQL Eng. │               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│  ┌──────────────┐           │                        │
│  │  Rule Eval.  │◀──────────┘                        │
│  │  (Alerting / │                                    │
│  │  Recording)  │                                    │
│  └──────┬───────┘                                    │
└─────────┼───────────────────────────────────────────┘
          │
          ▼
  ┌───────────────┐      ┌──────────────────┐
  │ Alertmanager  │      │ Grafana / Client │
  └───────────────┘      └──────────────────┘
```

### Flusso di Scraping

1. **Service Discovery** — Prometheus scopre i target dinamicamente (Kubernetes, Consul, file-based, DNS, EC2, etc.)
2. **Scraping** — Ogni `scrape_interval` (default 15s), Prometheus fa HTTP GET all'endpoint `/metrics` di ogni target
3. **Parsing** — Il formato text-based (exposition format) viene parsato e le metriche salvate nel TSDB
4. **Rule Evaluation** — Ogni `evaluation_interval`, vengono valutate le recording rules e alerting rules
5. **Alerting** — Gli alert attivi vengono inviati ad Alertmanager per routing e deduplication

### TSDB (Time Series Database)

Prometheus usa un TSDB embedded ottimizzato per:
- **Write**: blocchi di dati in memoria (WAL), compattati periodicamente su disco
- **Read**: query su range temporali con indice invertito su labels
- **Retention**: default 15 giorni, configurabile con `--storage.tsdb.retention.time`

Per retention a lungo termine, si usa **Remote Write** verso sistemi esterni (Thanos, Cortex, VictoriaMetrics, Mimir).

## Configurazione & Pratica

### Configurazione Base

```yaml
# prometheus.yml
global:
  scrape_interval: 15s        # frequenza scraping (default 1m)
  evaluation_interval: 15s    # frequenza valutazione rules
  scrape_timeout: 10s

  # Labels aggiunti a tutte le time series di questo server
  external_labels:
    cluster: 'prod-eu-west-1'
    env: 'production'

# File con le alerting/recording rules
rule_files:
  - "rules/*.yml"

# Configurazione Alertmanager
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

# Configurazione degli scrape job
scrape_configs:
  # Prometheus scrapa se stesso
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Scraping via Service Discovery Kubernetes
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # Scrapa solo i pod con l'annotation prometheus.io/scrape: "true"
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod

  # Scraping nodi Kubernetes via node_exporter
  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - action: labelmap
        regex: __meta_kubernetes_node_label_(.+)
```

### Deployment su Kubernetes con Helm

```bash
# Aggiungere il repo kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Installare lo stack completo (Prometheus + Grafana + Alertmanager + exporters)
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi
```

### PromQL — Linguaggio di Query

PromQL permette di interrogare e manipolare le time series.

```promql
# --- Instant vector (valore corrente) ---
# Tutte le time series di una metrica
http_requests_total

# Filtrare per label
http_requests_total{job="api", status!="200"}

# Filtrare con regex
http_requests_total{status=~"5.."}

# --- Range vector (valore negli ultimi N minuti) ---
# Usato come input per funzioni
http_requests_total[5m]

# --- Funzioni aggregate ---
# Rate di incremento per secondo (per counter)
rate(http_requests_total[5m])

# Rate con aggregazione per servizio
sum by (service) (rate(http_requests_total[5m]))

# Percentuale di errori
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100

# Percentili da histogram
histogram_quantile(0.99,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)

# --- Funzioni utili ---
increase(http_requests_total[1h])     # incremento in 1h
irate(http_requests_total[5m])        # rate istantaneo (ultimi 2 campioni)
delta(temperature[1h])                # differenza (per gauge)
predict_linear(disk_free[1h], 4*3600) # previsione lineare a 4h
absent(up{job="api"})                 # alert se metrica assente
```

### Recording Rules

Le recording rules pre-calcolano query costose e le salvano come nuove time series.

```yaml
# rules/recording.yml
groups:
  - name: http_recording
    interval: 1m  # override dell'evaluation_interval globale
    rules:
      # Pre-calcola il rate di richieste per servizio
      - record: job:http_requests_total:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))

      # Pre-calcola la latenza al 99° percentile
      - record: job:http_request_duration_seconds:p99
        expr: >
          histogram_quantile(0.99,
            sum by (job, le) (
              rate(http_request_duration_seconds_bucket[5m])
            )
          )
```

### Alerting Rules

```yaml
# rules/alerts.yml
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: >
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)
          > 0.05
        for: 5m  # l'alert deve essere vero per 5 minuti consecutivi
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "Alto tasso di errori su {{ $labels.service }}"
          description: >
            Il servizio {{ $labels.service }} ha un error rate del
            {{ printf "%.2f" $value }}% (soglia: 5%).
          runbook_url: "https://wiki.example.com/runbooks/high-error-rate"

      - alert: PrometheusTargetDown
        expr: up == 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Target {{ $labels.instance }} non raggiungibile"
```

### Exporters Principali

| Exporter | Target | Porta |
|----------|--------|-------|
| **node_exporter** | Metriche OS Linux (CPU, mem, disk, network) | 9100 |
| **kube-state-metrics** | Stato oggetti Kubernetes (pod, deployment, etc.) | 8080 |
| **blackbox_exporter** | Probing HTTP/HTTPS, TCP, ICMP, DNS | 9115 |
| **mysqld_exporter** | MySQL/MariaDB | 9104 |
| **postgres_exporter** | PostgreSQL | 9187 |
| **redis_exporter** | Redis | 9121 |
| **cadvisor** | Metriche container Docker/containerd | 8080 |
| **nginx-prometheus-exporter** | NGINX | 9113 |

### Federation

La federation permette a un Prometheus gerarchico di scrappare metriche pre-aggregate da altri Prometheus.

```yaml
# Prometheus di alto livello che aggrega da N cluster
scrape_configs:
  - job_name: 'federate'
    honor_labels: true
    metrics_path: '/federate'
    params:
      match[]:
        - '{job="kubernetes-pods"}'
        - 'job:http_requests_total:rate5m'  # solo recording rules
    static_configs:
      - targets:
        - 'prometheus-cluster-1:9090'
        - 'prometheus-cluster-2:9090'
```

## Best Practices

### Naming delle Metriche

```
# Pattern consigliato
<namespace>_<subsystem>_<name>_<unit>_total

# Esempi corretti
http_server_requests_total          # counter
http_server_request_duration_seconds # histogram
process_resident_memory_bytes       # gauge
```

- Usare sempre le unità base SI (seconds, bytes, not ms o MB)
- I Counter devono finire in `_total`
- I nomi devono essere snake_case
- Non includere il tipo nella metrica (no `http_requests_counter`)

### Retention e Storage

```yaml
# prometheus.yml per produzione
global:
  external_labels:
    replica: '{{ .Env.POD_NAME }}'  # per deduplication in Thanos

# Configurazione storage
# --storage.tsdb.retention.time=90d
# --storage.tsdb.retention.size=100GB
# --storage.tsdb.min-block-duration=2h
# --storage.tsdb.max-block-duration=24h
```

### Alta Disponibilità

Prometheus di default è stateful e non clusterizzabile. Le strategie HA sono:

1. **Run 2 repliche identiche** + Alertmanager clustering per deduplication degli alert
2. **Thanos / Cortex / Mimir** per storage distribuito e query federata
3. **Remote Write** verso VictoriaMetrics per retention centralizzata

```yaml
# Remote write verso Thanos/VictoriaMetrics
remote_write:
  - url: "http://thanos-receive:19291/api/v1/receive"
    queue_config:
      max_samples_per_send: 10000
      max_shards: 30
      capacity: 100000
```

## Troubleshooting

### Target Down

```bash
# Verificare lo stato dei target
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Controllare i log di scraping
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | {instance: .labels.instance, lastError: .lastError}'
```

### Query Lente / TSDB Saturo

```bash
# Verificare il numero di time series attive
prometheus_tsdb_head_series

# Identificare i job con più serie
sort_desc(count by (job) ({__name__=~".+"}))

# Verificare chunk e block
prometheus_tsdb_head_chunks
prometheus_tsdb_blocks_loaded
```

### Metriche Mancanti

```promql
# Verificare se un target è up
up{job="my-service"}

# Verificare l'ultimo scrape
scrape_duration_seconds{job="my-service"}
scrape_samples_scraped{job="my-service"}
```

## Relazioni

??? info "Grafana — Visualizzazione"
    Grafana è il layer di visualizzazione standard per Prometheus. Supporta PromQL nativamente come data source e fornisce dashboard, alerting, e annotation.

    **Approfondimento completo →** [Grafana](./grafana.md)

??? info "Alertmanager — Routing Alert"
    Alertmanager riceve gli alert da Prometheus e gestisce routing, grouping, silencing e notifiche (Slack, PagerDuty, email).

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

??? info "OpenTelemetry — Standard di Telemetria"
    OTEL può esportare metriche in formato Prometheus-compatible. Il Collector può ricevere OTLP e esporre `/metrics` per Prometheus.

    **Approfondimento completo →** [OpenTelemetry](../fondamentali/opentelemetry.md)

??? info "SLO/SLA/SLI — Reliability Targets"
    Prometheus è lo strumento operativo per misurare gli SLI e calcolare l'error budget.

    **Approfondimento completo →** [SLO/SLA/SLI](../sre/slo-sla-sli.md)

## Riferimenti

- [Documentazione ufficiale Prometheus](https://prometheus.io/docs/)
- [PromQL cheat sheet](https://promlabs.com/promql-cheat-sheet/)
- [Helm chart kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)
- [Thanos — HA + Long-term storage](https://thanos.io/tip/thanos/getting-started.md/)
- [Alerting Best Practices — Robust Perception](https://www.robustperception.io/alerting-on-latency/)
