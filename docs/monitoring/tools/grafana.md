---
title: "Grafana"
slug: grafana
category: monitoring
tags: [grafana, dashboard, visualization, alerting, monitoring, observability]
search_keywords: [grafana, dashboard, visualizzazione, pannelli, panel, data source, loki, prometheus, alerting, grafana cloud, tempo, mimir, annotation, variabili, template, osservabilità]
parent: monitoring/tools/_index
related: [monitoring/tools/prometheus, monitoring/tools/loki, monitoring/alerting/alertmanager, monitoring/fondamentali/opentelemetry, monitoring/tools/jaeger-tempo]
official_docs: https://grafana.com/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Grafana

## Panoramica

Grafana è la piattaforma open-source di riferimento per la visualizzazione e l'analisi di dati di monitoraggio. Nata nel 2014 come fork di Kibana orientato a Graphite, è oggi il tool standard nel mondo DevOps/SRE per costruire dashboard operative, explorare metriche e log, e configurare alerting multi-canale. La sua caratteristica distintiva è la capacità di connettere **fonti dati eterogenee** (Prometheus, Loki, Elasticsearch, InfluxDB, PostgreSQL, CloudWatch, e decine di altre) in un'unica interfaccia. Non sostituisce i sistemi di storage delle metriche, ma li rende interrogabili e visualizzabili in modo uniforme.

## Concetti Chiave

### Data Sources

Un Data Source è la connessione configurata verso una sorgente dati. Grafana supporta oltre 150 data source tramite plugin.

| Data Source | Tipo | Uso tipico |
|-------------|------|------------|
| **Prometheus** | Metriche | Metriche infrastruttura e applicazioni |
| **Loki** | Log | Log aggregati (stack PLG) |
| **Tempo** | Tracce | Distributed tracing |
| **Alertmanager** | Alert | Visualizzazione stato alert |
| **Elasticsearch** | Log/Search | Stack ELK, full-text search |
| **InfluxDB** | Metriche | IoT, time series legacy |
| **PostgreSQL/MySQL** | SQL | Metriche business da DB relazionali |
| **CloudWatch** | Metriche AWS | Monitoraggio servizi AWS nativi |
| **Azure Monitor** | Metriche Azure | Monitoraggio servizi Azure |

### Dashboard e Panel

- **Dashboard**: collezione di panel organizzati in una griglia
- **Panel**: unità base di visualizzazione (grafico, stat, gauge, table, heatmap, logs, etc.)
- **Row**: gruppo collassabile di panel
- **Variables**: template variables per dashboard parametriche (es. `$namespace`, `$pod`)

### Organizations e Teams

Grafana supporta multi-tenancy tramite Organizations. All'interno di ogni Org, i Team gestiscono i permessi su folder e dashboard.

## Architettura / Come Funziona

```
┌─────────────────────────────────────────────────┐
│                  Grafana Server                  │
│                                                   │
│  ┌─────────────┐   ┌────────────────────────┐   │
│  │   Frontend  │   │   Backend              │   │
│  │   (React)   │◀─▶│   (Go)                 │   │
│  └─────────────┘   │   - API Server         │   │
│                     │   - Auth               │   │
│  ┌─────────────┐   │   - Plugin Manager     │   │
│  │  Dashboard  │   │   - Alerting Engine    │   │
│  │  Storage    │   └──────────┬─────────────┘   │
│  │  (SQLite /  │              │                  │
│  │   MySQL /   │    ┌─────────▼──────────┐      │
│  │  PostgreSQL)│    │   Data Source      │      │
│  └─────────────┘    │   Plugins          │      │
│                      └─────────┬──────────┘      │
└────────────────────────────────┼────────────────┘
                                  │
           ┌──────────────────────┼──────────────┐
           ▼                      ▼               ▼
     Prometheus                 Loki           Tempo
```

Grafana non memorizza dati di metriche: **ogni query viene eseguita in tempo reale** verso il data source configurato al momento del rendering del panel.

## Configurazione & Pratica

### Deploy con Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  grafana:
    image: grafana/grafana:10.4.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=secret
      - GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-piechart-panel
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    restart: unless-stopped

volumes:
  grafana-storage:
```

### Provisioning as Code

Grafana supporta il provisioning declarativo tramite file YAML — fondamentale per GitOps.

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      httpMethod: POST
      prometheusType: Prometheus
      prometheusVersion: 2.48.0
      timeInterval: "15s"

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
    jsonData:
      maxLines: 1000
```

```yaml
# grafana/provisioning/dashboards/default.yml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'Infrastructure'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: false
    options:
      path: /etc/grafana/provisioning/dashboards/json
```

### Deploy su Kubernetes con Helm

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install grafana grafana/grafana \
  --namespace monitoring \
  --set persistence.enabled=true \
  --set persistence.size=10Gi \
  --set adminPassword='changeme' \
  --set datasources."datasources\.yaml".apiVersion=1 \
  --values grafana-values.yml
```

### Dashboard as Code con Grafonnet / Jsonnet

Per dashboard versionabili in Git, si usa Grafonnet (libreria Jsonnet):

```bash
# Esportare una dashboard esistente come JSON
curl -s http://admin:secret@grafana:3000/api/dashboards/uid/abc123 | jq '.dashboard' > dashboard.json

# Importare una dashboard da JSON
curl -X POST http://admin:secret@grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @dashboard.json
```

### Configurazione Alerting

Grafana ha un proprio Unified Alerting engine (dalla v9+), indipendente da Prometheus.

```yaml
# grafana/provisioning/alerting/contact-points.yml
apiVersion: 1
contactPoints:
  - orgId: 1
    name: Slack Ops
    receivers:
      - uid: slack-ops-01
        type: slack
        settings:
          url: "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX"
          channel: "#alerts-critical"
          username: "Grafana"
          iconEmoji: ":grafana:"

# grafana/provisioning/alerting/policies.yml
apiVersion: 1
policies:
  - orgId: 1
    receiver: Slack Ops
    group_by: ['alertname', 'namespace']
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 4h
```

### Template Variables

Le variables rendono le dashboard riutilizzabili su namespace/cluster diversi.

```json
{
  "templating": {
    "list": [
      {
        "name": "namespace",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(kube_pod_info, namespace)",
        "multi": false,
        "includeAll": false,
        "refresh": 2
      },
      {
        "name": "pod",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(kube_pod_info{namespace=\"$namespace\"}, pod)",
        "multi": true,
        "includeAll": true
      }
    ]
  }
}
```

### Panels Comuni

```promql
# --- Stat Panel: Request rate corrente ---
sum(rate(http_requests_total{namespace="$namespace"}[5m]))

# --- Time Series: CPU usage per pod ---
sum by (pod) (
  rate(container_cpu_usage_seconds_total{
    namespace="$namespace",
    pod=~"$pod"
  }[5m])
)

# --- Gauge: Memory usage % ---
(
  container_memory_working_set_bytes{namespace="$namespace", pod=~"$pod"}
  /
  container_spec_memory_limit_bytes{namespace="$namespace", pod=~"$pod"}
) * 100

# --- Heatmap: Distribuzione latenza ---
sum by (le) (
  rate(http_request_duration_seconds_bucket{namespace="$namespace"}[5m])
)
```

## Best Practices

### Dashboard Design

- **Una dashboard = un servizio/componente** — evitare dashboard mega-onnicomprensive
- Usare **variables** per rendere le dashboard riutilizzabili ($env, $namespace, $service)
- Fissare il **time range di default** appropriato (es. last 1h per ops, last 7d per trend)
- Usare **annotations** per visualizzare deploy e eventi significativi sulla timeline
- Ordinare i panel per importanza: metriche golden signals (latency, error rate, saturation) in alto

### Golden Signals (Google SRE)

```promql
# 1. Latency (p50, p95, p99)
histogram_quantile(0.99, sum by(le) (rate(http_request_duration_seconds_bucket[5m])))

# 2. Traffic (req/s)
sum(rate(http_requests_total[5m]))

# 3. Errors (error rate %)
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# 4. Saturation (CPU utilization)
sum(rate(container_cpu_usage_seconds_total[5m])) / sum(kube_node_status_allocatable{resource="cpu"}) * 100
```

### Sicurezza

```ini
# grafana.ini — configurazione sicurezza
[auth]
disable_login_form = false

[auth.generic_oauth]
enabled = true
name = "Company SSO"
# Integrare con OIDC provider aziendale

[security]
admin_user = admin
secret_key = SW2YcwTIb9zpOOhoPsMm    # rotare periodicamente
cookie_secure = true
cookie_samesite = strict
strict_transport_security = true
```

## Troubleshooting

### Dashboard lente

```bash
# Abilitare query profiling
# In Grafana UI: Explore → query → Query Inspector

# Verificare il tempo di risposta del data source
curl -w "@curl-format.txt" -s http://prometheus:9090/api/v1/query \
  -d 'query=sum(rate(http_requests_total[5m]))'
```

### Nessun dato nei panel

1. Verificare che il data source sia raggiungibile: **Configuration → Data Sources → Test**
2. Controllare il time range selezionato nella dashboard
3. Usare **Explore** per testare la query direttamente
4. Verificare che le label della query corrispondano ai dati effettivi

### Reset password admin

```bash
# Se self-hosted
grafana-cli admin reset-admin-password newpassword

# In Kubernetes
kubectl exec -it grafana-pod -n monitoring -- grafana-cli admin reset-admin-password newpassword
```

## Relazioni

??? info "Prometheus — Data Source principale"
    Prometheus è il data source primario per metriche infrastructure e applicazioni. Grafana supporta PromQL nativamente con autocompletion.

    **Approfondimento completo →** [Prometheus](./prometheus.md)

??? info "Loki — Log Aggregation"
    Loki è il data source per i log nello stack PLG (Prometheus + Loki + Grafana). Permette di correlare metriche e log nella stessa interfaccia.

    **Approfondimento completo →** [Loki](./loki.md)

??? info "Alertmanager — Routing Alert"
    Grafana può visualizzare gli alert di Alertmanager come data source, oppure usare il proprio Unified Alerting engine.

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

## Riferimenti

- [Documentazione ufficiale Grafana](https://grafana.com/docs/)
- [Grafana Dashboards community](https://grafana.com/grafana/dashboards/)
- [Grafana Helm chart](https://github.com/grafana/helm-charts)
- [Grafonnet — Dashboard as Code](https://grafana.github.io/grafonnet/)
- [USE Method dashboard](https://www.brendangregg.com/USEmethod/use-linux.html)
- [RED Method per microservizi](https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/)
