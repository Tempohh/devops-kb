---
title: "GCP Cloud Monitoring"
slug: cloud-monitoring
category: cloud/gcp/monitoring
tags: [gcp, monitoring, observability, stackdriver, prometheus, logging, alerting, slo, otel, gke]
search_keywords: [GCP Cloud Monitoring, Stackdriver, Stackdriver Monitoring, Cloud Logging, GCP observability, GCP metriche, Google Cloud monitoring, Monitoring Query Language, MQL, Managed Service for Prometheus, MSP, Cloud Trace, GKE monitoring, Cloud Run monitoring, Log Router, log sink BigQuery, log-based metrics, Alerting Policy GCP, Notification Channel GCP, SLO GCP, burn rate alert, uptime check GCP, Application Signals, OTEL Google Cloud, OpenTelemetry GCP, googlemanagedprometheus, metric explorer GCP, workspace GCP monitoring, custom metrics GCP, external metrics prometheus, Logging Query Language, LQL, _Required log bucket, _Default log bucket, CMEK logging GCP, monitoraggio GCP, osservabilità GCP, metriche GCP, log GCP, alert GCP, prometheus GKE, trace distribuito GCP, Cloud Trace GKE, GKE observability]
parent: cloud/gcp/monitoring/_index
related: [cloud/gcp/containers/gke, cloud/gcp/compute/cloud-run, monitoring/tools/prometheus, monitoring/fondamentali/opentelemetry, monitoring/sre/slo-sla-sli, monitoring/alerting/alertmanager, monitoring/tools/otel-collector-kubernetes]
official_docs: https://cloud.google.com/monitoring/docs
status: complete
difficulty: intermediate
last_updated: 2026-04-03
---

# GCP Cloud Monitoring

## Panoramica

**GCP Cloud Monitoring** (ex Stackdriver, rinominato nel 2020) è la piattaforma di osservabilità nativa di Google Cloud. Copre le quattro dimensioni dell'osservabilità — **metriche, log, trace, profiling** — con servizi distinti ma integrati nello stesso pannello Cloud Console: Cloud Monitoring per le metriche, Cloud Logging per i log, Cloud Trace per il tracing distribuito e Cloud Profiler per il profiling CPU/memoria.

**Quando usare Cloud Monitoring come soluzione primaria:**
- Workload su GCP (GKE, Cloud Run, Compute Engine, App Engine) che vogliono zero overhead infra
- Team che vogliono SLO nativi con burn rate alert automatici senza configurazione manuale
- Ambienti che integrano Prometheus esistente su GKE tramite Managed Service for Prometheus

**Quando affiancare strumenti esterni:**
- Dashboard avanzate con Grafana (si connette via Cloud Monitoring API o MSP)
- Multi-cloud o on-premise: OTEL Collector → Google Cloud Exporter + strumenti self-managed
- Log analytics complessa: Log Router → BigQuery + Looker Studio

**Cosa NON è Cloud Monitoring:**
- Non è un APM completo out-of-the-box (Application Insights di Azure ha più auto-instrumentazione)
- Non gestisce profiling di produzione autonomamente (Cloud Profiler è un servizio separato)
- Non sostituisce Grafana per dashboard complesse multi-sorgente

---

## Architettura / Come Funziona

### Struttura a Livelli

```
┌──────────────────────────────────────────────────────────────────┐
│                    Cloud Monitoring (metriche)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ GCP System  │  │   Custom     │  │  External (Prometheus    │ │
│  │  Metrics    │  │  Metrics     │  │  via MSP/OTEL)           │ │
│  │ (auto-race) │  │  (API/agent) │  │                          │ │
│  └─────────────┘  └──────────────┘  └──────────────────────────┘ │
│                                                                   │
│  Metric Explorer ── Dashboards ── Alerting Policy ── SLOs        │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│                    Cloud Logging                                  │
│  ┌─────────────────────┐  ┌───────────────────────────────────┐  │
│  │  Log Ingestion      │  │  Log Router (sinks)               │  │
│  │  (agents, API, GKE) │  │  → BigQuery / GCS / Pub/Sub       │  │
│  └─────────────────────┘  └───────────────────────────────────┘  │
│                                                                   │
│  Log Explorer ── Log-based Metrics ── Log Buckets                │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  Cloud Trace  │  Cloud Profiler  │  Error Reporting              │
└──────────────────────────────────────────────────────────────────┘
```

### Tipi di Metriche

Cloud Monitoring gestisce tre famiglie di metriche con namespace distinti:

| Tipo | Prefisso | Fonte | Latenza |
|------|----------|-------|---------|
| **GCP System Metrics** | `compute.googleapis.com/`, `k8s.io/`, `run.googleapis.com/` | Auto-raccolta da infra GCP | 30-60s |
| **Custom Metrics** | `custom.googleapis.com/` | API Monitoring o agent (Ops Agent) | ~1min |
| **External Metrics** | `external.googleapis.com/prometheus/` | Prometheus via MSP o scraping | ~2min |

**Esempi di metriche GCP system più usate:**

```
# Compute Engine
compute.googleapis.com/instance/cpu/utilization
compute.googleapis.com/instance/memory/balloon/ram_used

# GKE
kubernetes.io/container/cpu/request_utilization
kubernetes.io/container/memory/used_bytes
kubernetes.io/node/cpu/allocatable_utilization
kubernetes.io/pod/network/received_bytes_count

# Cloud Run
run.googleapis.com/request_count
run.googleapis.com/request_latencies
run.googleapis.com/container/cpu/utilization
run.googleapis.com/container/memory/utilizations
```

### Workspace e Scope

Un **Workspace** (ora chiamato "Metrics Scope") permette di visualizzare metriche da più progetti GCP in un'unica vista. Il progetto che "ospita" il workspace viene chiamato **scoping project**.

```
Scoping Project: monitoring-hub
├── Monitored Project: prod-backend
├── Monitored Project: prod-frontend
├── Monitored Project: staging
└── Monitored Project: shared-infra
                ↓
Dashboard unificata con metriche cross-project
```

!!! warning "Billing del workspace"
    Le metriche dei progetti monitorati vengono fatturate nel **progetto che le genera**, non nel scoping project. Il workspace è solo una vista aggregata — non sposta il billing.

---

## Cloud Logging

### Log Router e Sinks

Il **Log Router** intercetta tutti i log in ingresso prima che raggiungano i bucket di destinazione. Tramite i **sink** puoi esportare log (filtrando con LQL) verso BigQuery, Cloud Storage o Pub/Sub per retention a lungo termine o analisi avanzata.

```bash
# Creare un sink verso BigQuery (retention 90+ giorni con query SQL)
gcloud logging sinks create prod-logs-bq \
  bigquery.googleapis.com/projects/my-project/datasets/logs_dataset \
  --log-filter='resource.type="k8s_container" AND severity>=WARNING' \
  --project=my-project

# Creare un sink verso GCS per archivio a lungo termine (compliance)
gcloud logging sinks create prod-logs-archive \
  storage.googleapis.com/my-log-archive-bucket \
  --log-filter='logName="projects/my-project/logs/cloudaudit.googleapis.com%2Factivity"' \
  --project=my-project

# Creare un sink verso Pub/Sub (per webhook custom, SIEM, real-time processing)
gcloud logging sinks create security-events-pubsub \
  pubsub.googleapis.com/projects/my-project/topics/security-logs \
  --log-filter='protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"' \
  --project=my-project

# Verificare i sink attivi
gcloud logging sinks list --project=my-project
```

```bash
# IMPORTANTE: dopo aver creato un sink, assegnare i permessi al service account
# Il comando restituisce il SA del sink — dargli accesso alla destinazione
gcloud logging sinks describe prod-logs-bq --format="value(writerIdentity)"
# Output: serviceAccount:p123456789-123456@gcp-sa-logging.iam.gserviceaccount.com

# Assegnare roles/bigquery.dataEditor al SA sul dataset BigQuery
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:p123456789-123456@gcp-sa-logging.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

### Log-based Metrics

Le **log-based metrics** trasformano pattern nei log in metriche di Cloud Monitoring — utili per alertare su errori applicativi non esposti nativamente come metriche.

```bash
# Metrica counter: conta gli errori HTTP 500 dai container GKE
gcloud logging metrics create http_500_errors \
  --description="Conteggio errori HTTP 500 dai container GKE" \
  --log-filter='resource.type="k8s_container" severity=ERROR httpRequest.status=500'

# Metrica distribution: distribuzione della latenza da log applicativi
# (quando l'app loga la latenza in ms nel campo jsonPayload.latency_ms)
gcloud logging metrics create app_request_latency \
  --description="Distribuzione latenza richieste applicative" \
  --log-filter='resource.type="k8s_container" jsonPayload.latency_ms!=""' \
  --value-extractor='EXTRACT(jsonPayload.latency_ms)'

# Listare le metriche log-based esistenti
gcloud logging metrics list --project=my-project
```

Una volta create, le log-based metrics appaiono come `logging.googleapis.com/user/NOME_METRICA` in Metric Explorer e possono essere usate in alerting policy e dashboard come qualsiasi altra metrica.

### Log Buckets e Retention

GCP crea automaticamente due bucket di log speciali per ogni progetto:

| Bucket | Retention default | Modificabile | Note |
|--------|------------------|--------------|------|
| `_Required` | 400 giorni | **No** | Audit log, Admin Activity — obbligatori per compliance |
| `_Default` | 30 giorni | Sì (1-3650 giorni) | Tutti gli altri log |

```bash
# Aumentare la retention del bucket _Default a 90 giorni
gcloud logging buckets update _Default \
  --location=global \
  --retention-days=90 \
  --project=my-project

# Creare un bucket custom con CMEK (Customer-Managed Encryption Keys)
gcloud logging buckets create secure-logs \
  --location=europe-west8 \
  --retention-days=365 \
  --cmek-kms-key-name=projects/my-project/locations/europe-west8/keyRings/log-keyring/cryptoKeys/log-key \
  --project=my-project
```

!!! warning "Costo retention estesa"
    Il bucket `_Default` con retention oltre 30 giorni viene fatturato per i giorni aggiuntivi. Per log ad alto volume (GKE, Cloud Run) valutare un sink BigQuery invece di estendere la retention: è più economico e permette query SQL analitiche.

### Logging Query Language (LQL)

```
# Filtrare per severity e risorsa
resource.type="k8s_container"
resource.labels.namespace_name="production"
severity>=ERROR

# Filtrare per campo nel payload JSON
resource.type="cloud_run_revision"
jsonPayload.level="error"
jsonPayload.user_id!=""

# Ricerca full-text in textPayload
resource.type="k8s_container"
textPayload=~"OOMKilled|Out of memory"

# Combinare condizioni con AND/OR
(resource.type="k8s_container" OR resource.type="cloud_run_revision")
AND severity>=WARNING
AND timestamp>="2026-04-01T00:00:00Z"
```

---

## Configurazione & Pratica

### Metric Explorer e MQL

Il **Metric Explorer** ha due modalità di query:
- **Builder UI** (default): seleziona risorsa, metrica, aggregazione tramite dropdown
- **MQL (Monitoring Query Language)**: linguaggio di query dichiarativo per analisi avanzate

```
# MQL: utilizzo CPU medio per namespace GKE negli ultimi 30 minuti
fetch k8s_container
| metric 'kubernetes.io/container/cpu/request_utilization'
| filter resource.labels.namespace_name = 'production'
| group_by [resource.labels.namespace_name, resource.labels.pod_name], mean(val())
| within 30m

# MQL: rate degli errori 5xx su Cloud Run per revision
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter metric.labels.response_code_class = '5xx'
| group_by [resource.labels.service_name, resource.labels.revision_name],
           sliding(5m), rate(val())

# MQL: confronto percentili di latenza (p50, p95, p99)
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| group_by [resource.labels.service_name],
           [p50: percentile(val(), 50),
            p95: percentile(val(), 95),
            p99: percentile(val(), 99)]
| within 1h
```

### Alerting Policy

Un'**Alerting Policy** in Cloud Monitoring ha tre componenti:

```
Alerting Policy
├── Condition (quando triggerare)
│   ├── Metric threshold — soglia su metrica aggregata
│   ├── Metric absence — metrica assente per N minuti (servizio down)
│   ├── Log-based metric — threshold su metrica da log
│   ├── Uptime check — endpoint HTTP/TCP risponde?
│   └── SLO — burn rate troppo elevato
├── Notification Channels (dove notificare)
│   ├── Email, SMS
│   ├── PagerDuty, Slack, Opsgenie
│   └── Pub/Sub (per webhook custom)
└── Documentation (cosa incluire nella notifica)
    ├── Runbook URL
    └── Testo contestuale con variabili dinamiche
```

```bash
# Creare un notification channel Slack (via API — la UI è più comoda per OAuth)
gcloud alpha monitoring channels create \
  --display-name="Slack #alerts-prod" \
  --type=slack \
  --channel-labels=channel_name="#alerts-prod" \
  --project=my-project

# Creare un'alerting policy da file JSON (approccio IaC)
gcloud alpha monitoring policies create \
  --policy-from-file=alert-cpu-high.json \
  --project=my-project
```

```json
// alert-cpu-high.json — CPU GKE node > 80% per 5 minuti
{
  "displayName": "GKE Node CPU > 80%",
  "conditions": [{
    "displayName": "CPU utilization alta",
    "conditionThreshold": {
      "filter": "resource.type=\"k8s_node\" AND metric.type=\"kubernetes.io/node/cpu/allocatable_utilization\"",
      "aggregations": [{
        "alignmentPeriod": "60s",
        "perSeriesAligner": "ALIGN_MEAN",
        "crossSeriesReducer": "REDUCE_MAX",
        "groupByFields": ["resource.labels.node_name"]
      }],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0.80,
      "duration": "300s"
    }
  }],
  "alertStrategy": {
    "autoClose": "1800s"
  },
  "notificationChannels": ["projects/my-project/notificationChannels/CHANNEL_ID"],
  "documentation": {
    "content": "## CPU Node Pressure\nRunbook: https://wiki.example.com/gke-cpu-pressure\nComando diagnostico: `kubectl top nodes`",
    "mimeType": "text/markdown"
  }
}
```

**Parametri critici per evitare alert fatigue:**

| Parametro | Descrizione | Consiglio |
|-----------|-------------|-----------|
| `alignmentPeriod` | Finestra di aggregazione della serie temporale | 60s per metriche normali, 300s per batch/lente |
| `duration` | Per quanti secondi la condizione deve essere vera prima di triggerare | ≥300s per CPU/memory, 0s per errori critici |
| `autoClose` | Chiusura automatica alert dopo N secondi | 1800s-3600s per evitare alert fantasma |

!!! warning "Alert fatigue con duration = 0"
    Impostare `duration: 0s` significa triggerare all'istante in cui la soglia viene superata. Per metriche volatili (CPU spike momentanei, traffico burst) produce decine di alert per evento. Usare `duration: 0s` solo per condizioni strettamente binarie (servizio down, certificato scaduto).

### Terraform — Alert Policy e SLO

```hcl
# Alerting policy via Terraform
resource "google_monitoring_alert_policy" "cpu_high" {
  display_name = "GKE Node CPU > 80%"
  combiner     = "OR"

  conditions {
    display_name = "CPU utilization alta"
    condition_threshold {
      filter          = "resource.type=\"k8s_node\" AND metric.type=\"kubernetes.io/node/cpu/allocatable_utilization\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.80

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.slack.name]

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "## CPU Node Pressure\nRunbook: https://wiki.example.com/gke-cpu-pressure"
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_notification_channel" "slack" {
  display_name = "Slack #alerts-prod"
  type         = "slack"
  labels = {
    channel_name = "#alerts-prod"
  }
  sensitive_labels {
    auth_token = var.slack_auth_token
  }
}
```

---

## SLOs Nativi GCP

Cloud Monitoring supporta la definizione di **SLO nativi** direttamente sulla piattaforma, con burn rate alert generati automaticamente — senza dover calcolare manualmente le finestre di lookback.

### Tipi di SLO

| Tipo | Quando usare | Servizi supportati |
|------|-------------|-------------------|
| **Request-based** (good/total ratio) | API con metriche request_count | Cloud Run, GKE con metriche custom |
| **Window-based** (availability) | Uptime check o metriche booleane | Qualsiasi servizio con uptime check |

```bash
# Creare un SLO request-based per Cloud Run (99.5% richieste buone su 30 giorni)
# Con "buona" = latenza < 500ms AND status 2xx
gcloud alpha monitoring services create \
  --service-id=my-api-service \
  --display-name="My API Service" \
  --project=my-project

# Il SLO si crea più facilmente via Terraform o Console UI
# per la complessità della struttura JSON richiesta da gcloud
```

```hcl
# SLO Terraform: 99.5% availability su 30 giorni rolling
resource "google_monitoring_slo" "api_availability" {
  service      = google_monitoring_custom_service.api.service_id
  display_name = "API Availability 99.5% - 30d"

  goal                = 0.995
  rolling_period_days = 30

  request_based_sli {
    good_total_ratio {
      good_service_filter  = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" metric.labels.response_code_class=\"2xx\""
      total_service_filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\""
    }
  }
}

# Burn rate alert: automatico dal SLO (5x burn rate su 1h O 2x su 6h)
resource "google_monitoring_alert_policy" "slo_burn_rate" {
  display_name = "API SLO Burn Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "Burn rate 5x su 1h"
    condition_threshold {
      filter     = "select_slo_burn_rate(\"${google_monitoring_slo.api_availability.name}\", 3600s)"
      comparison = "COMPARISON_GT"
      threshold_value = 5.0
      duration   = "0s"
    }
  }

  conditions {
    display_name = "Burn rate 2x su 6h"
    condition_threshold {
      filter     = "select_slo_burn_rate(\"${google_monitoring_slo.api_availability.name}\", 21600s)"
      comparison = "COMPARISON_GT"
      threshold_value = 2.0
      duration   = "0s"
    }
  }

  notification_channels = [google_monitoring_notification_channel.slack.name]
}
```

!!! tip "Burn rate alert multi-finestra"
    GCP genera automaticamente burn rate alert su 2 finestre (1h fast-burn + 6h slow-burn) se usi la UI Console → SLO → "Add alert". Questo copre sia degradi rapidi (che esauriscono il budget in ore) sia degradi lenti (che passerebbero inosservati su finestre brevi). Replicare questo pattern in Terraform come nell'esempio sopra.

---

## GKE Observability

### Managed Service for Prometheus (MSP)

**Managed Service for Prometheus** permette di raccogliere metriche Prometheus-native da GKE senza gestire un'infrastruttura Prometheus (storage, HA, sharding). Le metriche finiscono in Cloud Monitoring come `external.googleapis.com/prometheus/` e sono accessibili tramite PromQL nativo via API compatibile Prometheus.

```bash
# Abilitare MSP su cluster GKE esistente
gcloud container clusters update my-cluster \
  --enable-managed-prometheus \
  --region=europe-west8

# Verificare che i componenti MSP siano running
kubectl get pods -n gmp-system
# Deve mostrare: gmp-operator, rule-evaluator, alertmanager (se configurato)
```

```yaml
# PodMonitoring: equivalente MSP di un ServiceMonitor Prometheus
# Scrape ogni Pod con label app=my-app ogni 30 secondi
apiVersion: monitoring.googleapis.com/v1
kind: PodMonitoring
metadata:
  name: my-app-monitoring
  namespace: production
spec:
  selector:
    matchLabels:
      app: my-app
  endpoints:
  - port: metrics        # porta named nel container
    interval: 30s
    path: /metrics
  targetLabels:
    metadata:
    - pod
    - namespace
    - node
```

```yaml
# ClusterPodMonitoring: scrape cluster-wide (cross-namespace)
apiVersion: monitoring.googleapis.com/v1
kind: ClusterPodMonitoring
metadata:
  name: all-apps-monitoring
spec:
  selector:
    matchLabels:
      prometheus.io/scrape: "true"
  endpoints:
  - port: metrics
    interval: 60s
```

```bash
# Query PromQL tramite l'endpoint Prometheus compatibile di MSP
# Richiede autenticazione con token GCP
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v1/projects/my-project/location/global/prometheus/api/v1/query" \
  --data-urlencode 'query=rate(http_requests_total{namespace="production"}[5m])'
```

!!! tip "MSP vs Self-managed Prometheus su GKE"
    Con MSP elimini: storage Prometheus (PVC), HA setup (2+ repliche), compaction, TSDB management. Il costo è simile a un'istanza Prometheus medio-grande. Per cluster con <1000 serie temporali, MSP può costare leggermente di più rispetto a Prometheus self-hosted su e2-small; per cluster enterprise con milioni di serie, MSP è quasi sempre più economico dell'overhead operativo.

### Metriche GKE System Auto-raccolte

GKE raccoglie automaticamente metriche di sistema senza configurazione aggiuntiva:

```
# Metriche Nodo
kubernetes.io/node/cpu/allocatable_utilization   → % CPU usata vs allocable
kubernetes.io/node/memory/allocatable_utilization → % memoria usata vs allocable
kubernetes.io/node/network/received_bytes_count   → traffico in ingresso per nodo
kubernetes.io/node/status/ready                   → nodo Ready?

# Metriche Container
kubernetes.io/container/cpu/request_utilization   → CPU usata / CPU requested
kubernetes.io/container/memory/used_bytes         → memoria RSS container
kubernetes.io/container/restart_count             → restart per container

# Metriche Pod
kubernetes.io/pod/network/received_bytes_count    → traffico Pod in ingresso
kubernetes.io/pod/volume/total_bytes              → dimensione PVC
```

### Cloud Trace su GKE

**Cloud Trace** raccoglie trace distribuiti senza infra dedicata. Su GKE si integra tramite librerie client o OTEL.

```python
# Python — traccia automatica con libreria cloud-trace
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup OTEL → Cloud Trace
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(CloudTraceSpanExporter(project_id="my-project"))
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

def handle_request(request_id):
    with tracer.start_as_current_span("handle-request") as span:
        span.set_attribute("request.id", request_id)
        # Il trace viene inviato a Cloud Trace automaticamente
        result = process(request_id)
        return result
```

---

## Integrazione con OpenTelemetry

### OTEL Collector → Google Cloud Exporter

```yaml
# otel-collector-config.yaml — pipeline completa verso GCP
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      scrape_configs:
      - job_name: 'my-app'
        static_configs:
        - targets: ['localhost:8080']

processors:
  batch:
    timeout: 10s
    send_batch_size: 1000
  resourcedetection:
    detectors: [gcp]   # auto-aggiunge labels GCP (project_id, zone, etc.)

exporters:
  googlecloud:
    project: my-project
    log:
      default_log_name: "opentelemetry.io/collector-exported-log"
    metric:
      prefix: "custom.googleapis.com/opentelemetry"
    trace: {}  # Cloud Trace

  googlemanagedprometheus:
    project: my-project  # per Managed Service for Prometheus

service:
  pipelines:
    metrics:
      receivers: [prometheus, otlp]
      processors: [resourcedetection, batch]
      exporters: [googlemanagedprometheus]
    traces:
      receivers: [otlp]
      processors: [resourcedetection, batch]
      exporters: [googlecloud]
    logs:
      receivers: [otlp]
      processors: [resourcedetection, batch]
      exporters: [googlecloud]
```

```yaml
# Deployment OTEL Collector su GKE come sidecar (per tracing)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      serviceAccountName: my-app-ksa  # con Workload Identity per GCP API
      containers:
      - name: app
        image: my-app:latest
        env:
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://localhost:4317"
      - name: otel-collector
        image: otel/opentelemetry-collector-contrib:latest
        args: ["--config=/etc/otel/config.yaml"]
        volumeMounts:
        - name: otel-config
          mountPath: /etc/otel
      volumes:
      - name: otel-config
        configMap:
          name: otel-collector-config
```

!!! tip "Workload Identity per OTEL Collector"
    Il container OTEL Collector ha bisogno di permessi IAM per scrivere su Cloud Monitoring, Cloud Trace e Cloud Logging. Usare **Workload Identity** con un GSA che ha i ruoli `roles/monitoring.metricWriter`, `roles/cloudtrace.agent`, `roles/logging.logWriter`. Mai montare chiavi JSON nel container.

---

## Best Practices

!!! warning "Non disabilitare Cloud Logging sui nodi GKE"
    GKE Autopilot non lo permette. Su Standard, disabilitare il system logging (`--logging=NONE`) rompe Cloud Monitoring dashboard GKE, gli alert su metriche di sistema e i log audit. Se il costo dei log è alto, usare un sink con filtro per ridurre il volume, non disabilitare il logging.

!!! warning "Log-based metrics: attenzione ai costi"
    Le metriche distribution (con value extractor) vengono campionate da ogni log entry corrispondente. Su servizi ad alto volume (migliaia di req/s) possono diventare costose. Aggiungere sempre un filtro specifico nel `--log-filter` per limitare il volume. Le metriche counter sono molto meno costose.

```bash
# Verificare il volume di log per servizio (utile per ottimizzare costi)
gcloud logging metrics list --project=my-project
gcloud logging read "resource.type=k8s_container" \
  --freshness=1h \
  --project=my-project \
  | wc -l  # stima delle entry nell'ultima ora
```

**Checklist osservabilità GCP:**

- [ ] **Managed Prometheus abilitato** su tutti i cluster GKE con PodMonitoring per app custom
- [ ] **Log Router sink** verso BigQuery per log con retention >30 giorni
- [ ] **Alerting policy** su metriche critiche: CPU nodo >80%, memory >85%, pod restart_count >5
- [ ] **Uptime check** su endpoint pubblici critici (latency + availability)
- [ ] **SLO nativo** con burn rate alert multi-finestra per servizi in produzione
- [ ] **Notification channels** testati (PagerDuty per critici, Slack per warning)
- [ ] **Workload Identity** per tutti i componenti di osservabilità (no JSON keys)
- [ ] **Alert documentation** con runbook URL in ogni policy
- [ ] **Dashboard** per ogni team: nodi GKE + namespace + servizio applicativo
- [ ] **Retention log review** trimestrale: verificare che i bucket non creino costi nascosti

---

## Troubleshooting

**Problema: metriche GKE non compaiono in Cloud Monitoring**

```bash
# Sintomo: dashboard GKE vuota, nessuna metrica kubernetes.io/*
# Causa 1: monitoring disabilitato alla creazione del cluster
gcloud container clusters describe my-cluster \
  --region=europe-west8 \
  --format="value(monitoringService)"
# Deve essere: monitoring.googleapis.com
# Se è "none", abilitare:
gcloud container clusters update my-cluster \
  --monitoring=SYSTEM \
  --region=europe-west8

# Causa 2: API Cloud Monitoring non abilitata nel progetto
gcloud services enable monitoring.googleapis.com --project=my-project

# Causa 3: SA del node pool senza ruoli monitoring
gcloud container clusters describe my-cluster \
  --region=europe-west8 \
  --format="value(nodeConfig.serviceAccount)"
# Il SA deve avere roles/monitoring.metricWriter
```

**Problema: PodMonitoring MSP non raccoglie metriche**

```bash
# Sintomo: metriche external.googleapis.com/prometheus/* assenti
# Diagnosi: verificare lo stato del PodMonitoring
kubectl describe podmonitoring my-app-monitoring -n production
# Cercare "Target status" nella sezione Status

# Causa 1: porta sbagliata nel PodMonitoring
kubectl get pods -n production -l app=my-app -o yaml \
  | grep -A5 ports
# Verificare che la porta "metrics" esista nel container

# Causa 2: Pod senza label corrispondenti al selector
kubectl get pods -n production --show-labels | grep my-app

# Log del scraper MSP
kubectl logs -n gmp-system -l app=collector | grep ERROR
```

**Problema: alert non scatta nonostante la metrica supera la soglia**

```bash
# Sintomo: metrica visibile in dashboard sopra soglia ma alert non triggera
# Causa 1: duration troppo alta — la condizione non dura abbastanza
# Verificare in Console: Monitoring → Alerting → [policy] → Edit → condition duration

# Causa 2: aggregazione nasconde il picco
# Se crossSeriesReducer = REDUCE_MEAN, un singolo nodo a 95% con altri a 20%
# darà media < soglia → l'alert non triggera
# Usare REDUCE_MAX per catturare il caso peggiore

# Causa 3: notification channel non verificato
gcloud alpha monitoring channels list --project=my-project
# Verificare che "verificationStatus" sia "VERIFIED"

# Test diretto: forzare manualmente un alert per testare il canale
gcloud alpha monitoring policies create \
  --policy-from-file=test-alert.json  # con soglia sempre vera
```

**Problema: log-based metric non viene creata**

```bash
# Sintomo: metrica assente in Metric Explorer dopo creazione
# Causa: il log-filter non corrisponde a nessun log
# Testare il filter in Log Explorer prima:
gcloud logging read \
  'resource.type="k8s_container" severity=ERROR httpRequest.status=500' \
  --freshness=1h \
  --project=my-project \
  --limit=5
# Se ritorna 0 risultati, il filter è sbagliato — le entry non matchano

# Causa alternativa: API Cloud Logging non abilitata
gcloud services enable logging.googleapis.com --project=my-project
```

**Problema: burn rate alert troppo rumoroso**

```bash
# Sintomo: burn rate alert triggera continuamente per traffico basso
# Causa: con pochissime richieste totali, anche 1-2 errori = burn rate alto
# Soluzione: aggiungere una condizione di volume minimo
# In MQL: filtrare solo quando total requests > N

# Alternativa: passare a SLO window-based (uptime check)
# per servizi con traffico insufficiente per SLO request-based statisticamente significativo
```

---

## Relazioni

??? info "GKE — Cluster Kubernetes su GCP"
    Cloud Monitoring raccoglie automaticamente metriche di sistema GKE. Managed Service for Prometheus si abilita direttamente sul cluster. Workload Identity è il meccanismo di autenticazione consigliato per componenti OTEL su GKE.

    **Approfondimento →** [Google Kubernetes Engine](../containers/gke.md)

??? info "Cloud Run — Serverless Containers"
    Cloud Run espone metriche native (`run.googleapis.com/request_count`, `request_latencies`, `container/cpu/utilization`) direttamente in Cloud Monitoring senza configurazione. I SLO request-based si costruiscono su queste metriche.

    **Approfondimento →** [Cloud Run](../compute/cloud-run.md)

??? info "Prometheus — Monitoring Open Source"
    Managed Service for Prometheus è compatibile con l'ecosistema Prometheus (PromQL, Operator, regole). Chi conosce Prometheus può usare MSP senza cambiare query o alerting rules — la differenza è solo il backend storage e la gestione infra.

    **Approfondimento →** [Prometheus](../../../monitoring/tools/prometheus.md)

??? info "OpenTelemetry — Standard di Osservabilità"
    OTEL Collector con Google Cloud Exporter è il bridge standard tra applicazioni instrumentate con OTEL e il backend GCP (Cloud Monitoring + Cloud Trace + Cloud Logging). Il `resourcedetection` processor aggiunge automaticamente i metadata GCP.

    **Approfondimento →** [OpenTelemetry](../../../monitoring/fondamentali/opentelemetry.md)

??? info "SLO/SLA/SLI — Service Level Objectives"
    I SLO nativi di Cloud Monitoring implementano direttamente i concetti SRE di SLI, SLO e error budget. Il burn rate alert è l'implementazione pratica del concetto di error budget consumption rate.

    **Approfondimento →** [SLO/SLA/SLI](../../../monitoring/sre/slo-sla-sli.md)

??? info "Alertmanager — Gestione Alert"
    Su GKE con MSP, Alertmanager può essere gestito da MSP stesso (ManagedAlertmanager) invece di essere deployato manualmente. Per routing avanzato (multi-tenant, silencing complesso) valutare Alertmanager self-managed affiancato a MSP.

    **Approfondimento →** [Alertmanager](../../../monitoring/alerting/alertmanager.md)

---

## Riferimenti

- [Cloud Monitoring Documentation](https://cloud.google.com/monitoring/docs)
- [Managed Service for Prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus)
- [Cloud Logging Documentation](https://cloud.google.com/logging/docs)
- [Monitoring Query Language (MQL)](https://cloud.google.com/monitoring/mql/reference)
- [Logging Query Language (LQL)](https://cloud.google.com/logging/docs/view/logging-query-language)
- [SLOs in Cloud Monitoring](https://cloud.google.com/monitoring/slo-monitoring)
- [Cloud Trace](https://cloud.google.com/trace/docs)
- [OTEL Google Cloud Exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/googlecloudexporter)
- [Terraform google_monitoring_alert_policy](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy)
- [GKE Observability Best Practices](https://cloud.google.com/stackdriver/docs/solutions/gke/observing)
- [Log Router and Sinks](https://cloud.google.com/logging/docs/export/configure_export_v2)
