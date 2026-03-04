---
title: "X-Ray, OpenTelemetry, Managed Grafana e Prometheus"
slug: observability
category: cloud
tags: [aws, x-ray, opentelemetry, adot, grafana, prometheus, distributed-tracing, observability, amp, amg]
search_keywords: [x-ray, distributed tracing, service map, segments, subsegments, annotations, metadata, sampling, x-ray daemon, x-ray sdk, adot, aws distro opentelemetry, otel collector, otlp, managed grafana, amazon managed grafana, amg, amazon managed prometheus, amp, promql, prometheus remote write, jaeger, zipkin, trace analytics, x-ray groups, x-ray analytics]
parent: cloud/aws/monitoring/_index
related: [cloud/aws/monitoring/cloudwatch, cloud/aws/security/compliance-audit, cloud/aws/ci-cd/code-services]
official_docs: https://docs.aws.amazon.com/xray/
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# X-Ray, OpenTelemetry, Managed Grafana e Prometheus

## Panoramica

Questo documento copre il layer di observability avanzata su AWS: distributed tracing con AWS X-Ray, vendor-neutral instrumentation con AWS Distro for OpenTelemetry (ADOT), visualizzazione con Amazon Managed Grafana, e metriche Prometheus con Amazon Managed Service for Prometheus.

---

## AWS X-Ray

### Panoramica

AWS X-Ray è il servizio di distributed tracing di AWS. Permette di tracciare le richieste attraverso microservizi, identificare colli di bottiglia, errori e dipendenze in un sistema distribuito.

**Integrazione nativa con:**
- AWS Lambda
- Amazon ECS e EKS
- Amazon EC2 (via X-Ray Daemon)
- AWS API Gateway
- AWS ALB (trace headers)
- AWS Elastic Beanstalk
- AWS App Mesh (Envoy proxy integration)
- AWS Step Functions

### Concetti Fondamentali

**Trace:** una singola richiesta end-to-end attraverso il sistema. Identificato da un Trace ID univoco.

**Segment:** unità di lavoro principale. Ogni servizio che partecipa a una richiesta crea un segment (es. Lambda function, EC2 service).

**Subsegment:** operazioni all'interno di un segment (chiamata a DynamoDB, query RDS, chiamata HTTP esterna).

**Annotations:** metadati indicizzati (string, number, boolean) su cui si può fare query/filter nella X-Ray console. Limitati a 50 per trace.

**Metadata:** metadati non indicizzati (qualsiasi oggetto JSON). Non filtrabili ma visibili nei trace details. Limite 64 KB per segment.

### Sampling

X-Ray non registra ogni singola richiesta per evitare costi eccessivi. La **sampling rule** determina quale percentuale di richieste registrare.

**Default sampling rule:** 1 richiesta per secondo + 5% delle richieste successive per host.

```bash
# Creare una sampling rule custom
aws xray create-sampling-rule \
  --sampling-rule '{
    "RuleName": "HighVolumeEndpoint",
    "RuleARN": "",
    "ResourceARN": "*",
    "Priority": 1,
    "FixedRate": 0.01,
    "ReservoirSize": 5,
    "ServiceName": "my-service",
    "ServiceType": "*",
    "Host": "*",
    "HTTPMethod": "GET",
    "URLPath": "/api/health",
    "Version": 1
  }'

# Sampling più aggressivo per path critici
aws xray create-sampling-rule \
  --sampling-rule '{
    "RuleName": "PaymentEndpoints",
    "Priority": 2,
    "FixedRate": 0.10,
    "ReservoirSize": 50,
    "ServiceName": "*",
    "HTTPMethod": "*",
    "URLPath": "/api/payments/*",
    "Host": "*",
    "ServiceType": "*",
    "ResourceARN": "*",
    "Version": 1
  }'
```

### X-Ray SDK — Instrumentazione

```python
# Python — Flask + DynamoDB
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
import boto3
import flask

# Patch automatico di boto3, requests, httpx, psycopg2, etc.
patch_all()

app = flask.Flask(__name__)
XRayMiddleware(app, xray_recorder)  # middleware Flask

xray_recorder.configure(service='order-service')

@app.route('/api/orders/<order_id>')
def get_order(order_id):
    # X-Ray crea automaticamente un segment per questa richiesta

    # Subsegment manuale per logica applicativa custom
    with xray_recorder.in_subsegment('validate-order-id') as subsegment:
        subsegment.put_annotation('orderId', order_id)
        subsegment.put_metadata('requestContext', {
            'userId': flask.request.headers.get('X-User-Id'),
            'timestamp': time.time()
        })
        if not is_valid_order_id(order_id):
            subsegment.add_exception(ValueError("Invalid order ID"))
            return {'error': 'Invalid order ID'}, 400

    # boto3 è già patched — X-Ray traccia automaticamente la chiamata DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Orders')
    response = table.get_item(Key={'orderId': order_id})

    return response.get('Item', {}), 200
```

```python
# Lambda con X-Ray (Active tracing abilitato nella configurazione)
import boto3
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

def handler(event, context):
    # Lambda crea automaticamente un segment
    # Il segment padre è la chiamata API/EventBridge che ha triggerato la Lambda

    with xray_recorder.in_subsegment('process-event') as sub:
        sub.put_annotation('eventType', event.get('source', 'unknown'))

        # Chiamate a servizi AWS vengono tracciate automaticamente
        s3 = boto3.client('s3')
        s3.get_object(Bucket='my-bucket', Key='config.json')

        # HTTP call esterna (richiede requests patched)
        import requests
        response = requests.get('https://api.external.com/data')

    return {'statusCode': 200}
```

### X-Ray Daemon

Il X-Ray Daemon è un processo leggero che raccoglie i dati di trace dall'applicazione (via UDP porta 2000) e li invia al servizio X-Ray in batch. Richiesto per EC2/on-premises, già incluso in Lambda e ECS Fargate.

```bash
# Installare il daemon su EC2 Amazon Linux
sudo yum install -y xray

# Configurare il daemon
cat > /etc/amazon/xray/cfg.yaml << 'EOF'
TotalBufferSizeMB: 50
Concurrency: 8
Region: "us-east-1"
Socket:
  UDPAddress: "127.0.0.1:2000"
  TCPAddress: "127.0.0.1:2000"
LocalMode: false
ResourceARN: ""
RoleARN: ""
Logging:
  LogRotation: true
  LogLevel: "prod"
  LogPath: "/var/log/xray/xray.log"
EOF

sudo systemctl start xray
sudo systemctl enable xray

# Su ECS: aggiungere il daemon come sidecar container
# Nel task definition:
# {
#   "name": "xray-daemon",
#   "image": "amazon/aws-xray-daemon",
#   "cpu": 32,
#   "memoryReservation": 256,
#   "portMappings": [{"hostPort": 2000, "containerPort": 2000, "protocol": "udp"}]
# }
```

### X-Ray Groups e Analytics

```bash
# Creare un gruppo per filtrare trace per errori
aws xray create-group \
  --group-name "HighLatencyTraces" \
  --filter-expression "responsetime > 2 AND service(\"order-service\")"

aws xray create-group \
  --group-name "ErrorTraces" \
  --filter-expression "error = true OR fault = true"

# Query per trace specifici via CLI
aws xray get-trace-summaries \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-16T00:00:00Z \
  --filter-expression "error = true AND annotation.orderId = \"ORDER-12345\""

# Ottenere trace completi
aws xray batch-get-traces \
  --trace-ids "1-5e4b5f28-a1b2c3d4e5f67890abcdef12"
```

### Service Map

La Service Map visualizza graficamente le dipendenze tra servizi. Per ogni nodo mostra: error rate, fault rate, latenza media, numero di chiamate.

!!! tip "Service Map e latency detection"
    La Service Map è il posto migliore per trovare colli di bottiglia. Un nodo con latenza alta e tante frecce in entrata è probabilmente il problema. Un nodo con fault rate elevato indica un servizio degradato.

---

## AWS Distro for OpenTelemetry (ADOT)

### Panoramica

ADOT è la distribuzione OpenTelemetry certificata da AWS. OpenTelemetry è lo standard vendor-neutral per instrumentazione e raccolta di telemetry data (traces, metrics, logs).

**Vantaggi di ADOT vs strumenti nativi AWS:**
- Vendor-neutral: cambiare backend (X-Ray, Jaeger, Zipkin, Datadog) senza modificare il codice
- Unico SDK per trace + metrics + logs
- Ecosistema più ampio: integrazioni con molti framework e librerie
- Standard di settore (CNCF Graduated project)

### Architettura ADOT

```
[Applicazione + OTel SDK]
         │ OTLP (gRPC/HTTP)
         ▼
[ADOT Collector]
  ├── Receivers: OTLP, Jaeger, Zipkin, Prometheus scrape
  ├── Processors: batch, memory_limiter, resource, filter
  └── Exporters:
      ├── AWS X-Ray (traces)
      ├── AWS CloudWatch EMF (metrics)
      ├── Prometheus Remote Write (AMP)
      └── OTLP (qualsiasi backend OTel-compatible)
```

### ADOT Collector Configuration

```yaml
# otelcol-config.yaml
extensions:
  health_check:
  pprof:
    endpoint: 0.0.0.0:1777
  zpages:
    endpoint: 0.0.0.0:55679

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
        - job_name: 'kubernetes-pods'
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: true

processors:
  batch:
    timeout: 10s
    send_batch_size: 100
  memory_limiter:
    check_interval: 5s
    limit_mib: 400
    spike_limit_mib: 100
  resource:
    attributes:
      - key: service.environment
        value: production
        action: insert

exporters:
  awsxray:
    region: us-east-1
    local_mode: false
    telemetry:
      enabled: true

  awsemf:
    region: us-east-1
    namespace: MyApp
    log_group_name: '/aws/otel/metrics'
    log_stream_name: '{TaskId}'
    dimension_rollup_option: "ZeroAndSingleDimensionRollup"

  prometheusremotewrite:
    endpoint: "https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-XXXX/api/v1/remote_write"
    auth:
      authenticator: sigv4auth

  awscloudwatchlogs:
    region: us-east-1
    log_group_name: '/aws/otel/logs'

service:
  extensions: [health_check, pprof, zpages]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [awsxray]

    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, resource, batch]
      exporters: [awsemf, prometheusremotewrite]

    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [awscloudwatchlogs]
```

### Instrumentazione con OTel SDK (Python)

```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.boto3 import Boto3Instrumentor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import flask

# Setup Tracing
trace_provider = TracerProvider(
    resource=Resource(attributes={
        SERVICE_NAME: "order-service",
        SERVICE_VERSION: "1.2.3",
        "deployment.environment": "production"
    })
)
trace_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317"))
)
trace.set_tracer_provider(trace_provider)

# Auto-instrumentazione
FlaskInstrumentor().instrument()
Boto3Instrumentor().instrument()
RequestsInstrumentor().instrument()

# Setup Metrics
meter_provider = MeterProvider(
    resource=Resource(attributes={SERVICE_NAME: "order-service"}),
    metric_readers=[PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint="http://otel-collector:4317"),
        export_interval_millis=60000
    )]
)
metrics.set_meter_provider(meter_provider)

# Uso manuale del tracer
tracer = trace.get_tracer("order-service")
meter = metrics.get_meter("order-service")

order_counter = meter.create_counter(
    "orders.created",
    unit="1",
    description="Numero di ordini creati"
)

app = flask.Flask(__name__)

@app.route('/api/orders', methods=['POST'])
def create_order():
    with tracer.start_as_current_span("create-order") as span:
        span.set_attribute("order.type", flask.request.json.get("type"))
        span.set_attribute("customer.id", flask.request.json.get("customerId"))

        order = process_order(flask.request.json)

        order_counter.add(1, {"order.type": order["type"], "status": "created"})
        span.set_attribute("order.id", order["id"])

        return order, 201
```

### ADOT su EKS (Add-on)

```bash
# Installare ADOT operator via EKS add-on
aws eks create-addon \
  --cluster-name my-eks-cluster \
  --addon-name adot \
  --addon-version v0.88.0-eksbuild.1

# Creare un OpenTelemetryCollector CRD
kubectl apply -f - << 'EOF'
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel-collector
  namespace: observability
spec:
  mode: DaemonSet
  serviceAccount: otel-collector-sa
  config: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
      kubeletstats:
        collection_interval: 30s
        auth_type: "serviceAccount"
        endpoint: "https://${K8S_NODE_NAME}:10250"
        insecure_skip_verify: true
    processors:
      batch: {}
      k8sattributes:
        extract:
          metadata: [k8s.namespace.name, k8s.deployment.name, k8s.pod.name]
    exporters:
      awsxray:
        region: us-east-1
      prometheusremotewrite:
        endpoint: "https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-XXXX/api/v1/remote_write"
        auth:
          authenticator: sigv4auth
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [k8sattributes, batch]
          exporters: [awsxray]
        metrics:
          receivers: [otlp, kubeletstats]
          processors: [k8sattributes, batch]
          exporters: [prometheusremotewrite]
EOF
```

---

## Amazon Managed Service for Prometheus (AMP)

AMP è un servizio Prometheus fully managed, compatibile con il protocollo Prometheus (PromQL — Prometheus Query Language, remote write, alerting rules).

```bash
# Creare un workspace AMP
aws amp create-workspace \
  --alias "production-metrics" \
  --tags Environment=production

# Ottenere l'endpoint del workspace
WORKSPACE_ID=$(aws amp list-workspaces --query 'workspaces[0].workspaceId' --output text)
WORKSPACE_ENDPOINT=$(aws amp describe-workspace \
  --workspace-id $WORKSPACE_ID \
  --query 'workspace.prometheusEndpoint' \
  --output text)

# Configurare Prometheus (su EC2 o EKS) per remote write ad AMP
# prometheus.yaml
cat > prometheus.yaml << 'EOF'
global:
  scrape_interval: 30s

remote_write:
  - url: "https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-XXXXX/api/v1/remote_write"
    sigv4:
      region: us-east-1
    queue_config:
      max_samples_per_send: 1000
      max_shards: 200
      capacity: 2500

scrape_configs:
  - job_name: 'my-app'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: /metrics
EOF

# Query PromQL tramite AWS CLI
aws amp query-metrics \
  --workspace-id $WORKSPACE_ID \
  --query 'rate(http_requests_total{job="order-service", status_code=~"5.."}[5m])' \
  --time $(date +%s)

# Creare Alerting Rules
aws amp create-rule-groups-namespace \
  --workspace-id $WORKSPACE_ID \
  --name "production-alerts" \
  --data "$(cat << 'EOF' | base64
groups:
  - name: api-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status_code=~"5.."}[5m])) /
          sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "P95 latency above 2 seconds"
EOF
)"
```

---

## Amazon Managed Grafana (AMG)

Amazon Managed Grafana è un servizio Grafana hosted, con autenticazione tramite IAM Identity Center (SSO — Single Sign-On), e integrazione nativa con i data source AWS.

```bash
# Creare un workspace Grafana
aws grafana create-workspace \
  --workspace-name "production-monitoring" \
  --account-access-type CURRENT_ACCOUNT \
  --authentication-providers AWS_SSO \
  --permission-type SERVICE_MANAGED \
  --workspace-data-sources CLOUDWATCH PROMETHEUS XRAY ATHENA \
  --workspace-notification-destinations SNS

# Creare un API key per automazione
aws grafana create-workspace-api-key \
  --workspace-id ws-1234567890 \
  --key-name "terraform-automation" \
  --key-role ADMIN \
  --seconds-to-live 86400
```

### Configurare Data Sources via API

```bash
GRAFANA_URL="https://g-1234567890.grafana-workspace.us-east-1.amazonaws.com"
API_KEY="your-api-key"

# Aggiungere CloudWatch come data source
curl -X POST "$GRAFANA_URL/api/datasources" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CloudWatch",
    "type": "cloudwatch",
    "access": "proxy",
    "jsonData": {
      "authType": "default",
      "defaultRegion": "us-east-1"
    }
  }'

# Aggiungere AMP come data source
curl -X POST "$GRAFANA_URL/api/datasources" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AMP",
    "type": "prometheus",
    "access": "proxy",
    "url": "https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-XXXXX",
    "jsonData": {
      "httpMethod": "GET",
      "sigV4Auth": true,
      "sigV4Region": "us-east-1",
      "sigV4AuthType": "default"
    }
  }'

# Aggiungere X-Ray come data source
curl -X POST "$GRAFANA_URL/api/datasources" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "X-Ray",
    "type": "grafana-x-ray-datasource",
    "access": "proxy",
    "jsonData": {
      "authType": "default",
      "defaultRegion": "us-east-1"
    }
  }'
```

---

## Architettura di Observability Completa

### Per Microservizi su EKS

```
[Microservizi]
  │ OTel SDK (auto-instrumentazione)
  │ OTLP (gRPC)
  ▼
[ADOT Collector (DaemonSet)]
  ├── Traces → AWS X-Ray
  ├── Metrics → AMP (Prometheus Remote Write)
  └── Logs → CloudWatch Logs (via Fluent Bit)

[AWS X-Ray] ← Service Map, Trace Analytics
[AMP] ← PromQL, Alert Rules
[CloudWatch Logs] ← Log Insights, Metric Filters, Alarms

[Amazon Managed Grafana]
  ├── Data Source: X-Ray (trace visualization)
  ├── Data Source: AMP (PromQL dashboards)
  ├── Data Source: CloudWatch (metriche AWS native)
  └── Alerting → SNS → PagerDuty
```

---

## Best Practices

### X-Ray

1. **Sampling rules** appropriate — non servono al 100% per ambienti ad alto volume
2. **Annotazioni** per chiavi di business (orderId, userId, requestType) — permettono query nei trace
3. **Subsegment** per operazioni critiche (query DB, chiamate esterne)
4. **Active tracing** su Lambda — abilitarlo nella configurazione, non nel codice
5. **Groups** per filtrare trace problematici automaticamente

### ADOT vs X-Ray SDK nativo

- **X-Ray SDK nativo:** più semplice, zero config, ideale per applicazioni pure AWS
- **ADOT:** per architetture multi-cloud, team con esperienza OTel, o quando si vuole portabilità del codice verso altri provider

### Prometheus/Grafana

1. **Recording rules** per pre-calcolare aggregazioni costose
2. **Alert fatigue** — configurare allarmi con significato operativo, non ogni metrica
3. **Dashboard-as-code** — versionare i dashboard Grafana in Git (Terraform/Jsonnet)
4. **Retention** — AMP ha retention configurabile; spostare metriche storiche su S3 via regole di recording

---

## Troubleshooting

### X-Ray: Trace Non Appaiono

1. Verificare che X-Ray Active Tracing sia abilitato sul servizio (Lambda, API GW, ECS)
2. Verificare che il ruolo IAM abbia `xray:PutTraceSegments` e `xray:PutTelemetryRecords`
3. Verificare che il X-Ray Daemon sia in esecuzione e raggiungibile (porta 2000 UDP)
4. Verificare le sampling rules — potrebbe star campionando 0% del traffico

```bash
# Verificare permessi IAM
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/LambdaRole \
  --action-names xray:PutTraceSegments xray:PutTelemetryRecords \
  --resource-arns "*"
```

### ADOT: Metriche Non Arrivano ad AMP

1. Verificare la configurazione SigV4Auth nel remote write (credenziali IAM)
2. Verificare i log del collector: `kubectl logs -n observability daemonset/otel-collector`
3. Verificare che il workspace AMP esista e sia ACTIVE

```bash
aws amp list-workspaces --query 'workspaces[*].{id:workspaceId,status:status.statusCode}'
```

---

## Relazioni

??? info "CloudWatch — Metrics e Logs"
    ADOT può inviare metriche a CloudWatch tramite EMF. X-Ray si integra con CloudWatch per service health monitoring.

    **Approfondimento completo →** [CloudWatch](cloudwatch.md)

??? info "EKS e Container"
    ADOT è il metodo raccomandato per observability su EKS. Container Insights di CloudWatch è l'alternativa più semplice.

??? info "CodePipeline/CodeBuild — CI/CD"
    X-Ray e ADOT possono essere configurati automaticamente via CodeBuild e deployment pipeline.

    **Approfondimento completo →** [Code Services](../ci-cd/code-services.md)

---

## Riferimenti

- [AWS X-Ray Documentation](https://docs.aws.amazon.com/xray/)
- [X-Ray SDK for Python](https://github.com/aws/aws-xray-sdk-python)
- [AWS Distro for OpenTelemetry](https://aws-otel.github.io/)
- [ADOT GitHub Repository](https://github.com/aws-observability/aws-otel-collector)
- [Amazon Managed Prometheus](https://docs.aws.amazon.com/prometheus/)
- [Amazon Managed Grafana](https://docs.aws.amazon.com/grafana/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [AWS Observability Best Practices](https://aws-observability.github.io/observability-best-practices/)
- [X-Ray Pricing](https://aws.amazon.com/xray/pricing/)
- [AMP Pricing](https://aws.amazon.com/prometheus/pricing/)
