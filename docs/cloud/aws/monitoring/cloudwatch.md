---
title: "Amazon CloudWatch — Metrics, Logs, Alarms, Dashboards"
slug: cloudwatch
category: cloud
tags: [aws, cloudwatch, metrics, logs, alarms, dashboards, log-insights, emf, cloudwatch-agent, composite-alarms, anomaly-detection, container-insights]
search_keywords: [cloudwatch, metrics, namespace, dimensions, statistics, high resolution metrics, custom metrics, cloudwatch agent, cloudwatch logs, log groups, log streams, subscription filters, log insights, metric filters, cloudwatch alarms, composite alarms, anomaly detection, metric math, cloudwatch dashboards, emf, embedded metric format, container insights, application insights, log retention, putmetricdata]
parent: cloud/aws/monitoring/_index
related: [cloud/aws/monitoring/observability, cloud/aws/security/compliance-audit, cloud/aws/messaging/sqs-sns]
official_docs: https://docs.aws.amazon.com/cloudwatch/
status: complete
difficulty: intermediate
last_updated: 2026-03-03
---

# Amazon CloudWatch — Metrics, Logs, Alarms, Dashboards

## Panoramica

Amazon CloudWatch è il servizio di monitoring e observability nativo di AWS. Raccoglie automaticamente metriche da tutti i servizi AWS, permette di inviare log e metriche custom, di impostare allarmi e di visualizzare dati su dashboard. È il punto di partenza per qualsiasi implementazione di monitoring su AWS.

---

## Metrics

### Struttura delle Metriche

Ogni metrica CloudWatch è identificata da:
- **Namespace:** raggruppamento logico (es. `AWS/EC2`, `AWS/RDS`, `MyApp`)
- **Metric Name:** nome della metrica (es. `CPUUtilization`, `RequestCount`)
- **Dimensions:** coppie key-value che identificano la sorgente (es. `InstanceId=i-1234`, `FunctionName=my-lambda`)
- **Statistics:** aggregazioni disponibili (Average, Sum, Minimum, Maximum, SampleCount, pNN.NN)
- **Period:** intervallo di aggregazione in secondi (60, 300, 3600...)

```bash
# Pubblicare una metrica custom
aws cloudwatch put-metric-data \
  --namespace "MyApp/Performance" \
  --metric-data '[
    {
      "MetricName": "OrderProcessingTime",
      "Dimensions": [
        {"Name": "Service", "Value": "OrderService"},
        {"Name": "Environment", "Value": "production"}
      ],
      "Value": 245.5,
      "Unit": "Milliseconds",
      "Timestamp": "2024-01-15T10:00:00Z"
    }
  ]'

# Leggere metriche
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-1234567890abcdef0 \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-16T00:00:00Z \
  --period 3600 \
  --statistics Average Maximum

# Lettura avanzata con GetMetricData (supporta Metric Math)
aws cloudwatch get-metric-data \
  --metric-data-queries '[
    {
      "Id": "cpu",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/EC2",
          "MetricName": "CPUUtilization",
          "Dimensions": [{"Name": "InstanceId", "Value": "i-1234567890abcdef0"}]
        },
        "Period": 300,
        "Stat": "Average"
      },
      "ReturnData": true
    }
  ]' \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-16T00:00:00Z
```

### Retention delle Metriche

CloudWatch conserva le metriche con granularità diversa a seconda dell'età:

| Periodo Dati | Granularità Conservata |
|-------------|----------------------|
| Ultimi 3 ore | 1 secondo (high-resolution) |
| Ultimi 15 giorni | 1 minuto |
| Ultimi 63 giorni | 5 minuti |
| Ultimi 455 giorni (~15 mesi) | 1 ora |

!!! warning "Dati aggregati perduti"
    Dopo 15 mesi, i dati a 1 minuto vengono aggregati in dati orari e i dati ad 1 minuto vengono eliminati. Pianificare export verso S3 per retention storica più lunga.

### High-Resolution Metrics

Le metriche standard hanno una granularità minima di 1 minuto. Le High-Resolution Metrics permettono granularità fino a **1 secondo**, ma hanno un costo più elevato e retention ridotta.

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Pubblicare metrica ad alta risoluzione (ogni secondo)
cloudwatch.put_metric_data(
    Namespace='MyApp/HighFrequency',
    MetricData=[{
        'MetricName': 'RequestLatency',
        'Dimensions': [
            {'Name': 'Endpoint', 'Value': '/api/orders'},
        ],
        'Value': 123.4,
        'Unit': 'Milliseconds',
        'StorageResolution': 1  # 1 = high-resolution (1 secondo)
                                 # 60 = standard (1 minuto)
    }]
)
```

---

## CloudWatch Agent

Il CloudWatch Agent permette di raccogliere metriche OS aggiuntive (non disponibili di default) e log da file arbitrari su istanze EC2, container, o server on-premises.

**Metriche aggiuntive con l'agent:**
- Memoria (mem_used_percent)
- Disk usage (disk_used_percent per ogni mount point)
- Swap usage
- Processi e connessioni di rete
- Windows Performance Counters

### Installazione e Configurazione

```bash
# Su Amazon Linux 2023
sudo yum install -y amazon-cloudwatch-agent

# Configurazione wizard interattivo
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard

# O configurazione manuale (file JSON)
sudo cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "metrics": {
    "namespace": "MyApp/System",
    "append_dimensions": {
      "InstanceId": "${aws:InstanceId}",
      "AutoScalingGroupName": "${aws:AutoScalingGroupName}"
    },
    "metrics_collected": {
      "mem": {
        "measurement": ["mem_used_percent", "mem_available"],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": ["disk_used_percent", "disk_free"],
        "metrics_collection_interval": 300,
        "resources": ["/", "/data"]
      },
      "netstat": {
        "measurement": ["tcp_established", "tcp_time_wait"],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/nginx/access.log",
            "log_group_name": "/myapp/nginx/access",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          },
          {
            "file_path": "/var/log/myapp/application.log",
            "log_group_name": "/myapp/application",
            "log_stream_name": "{hostname}/{instance_id}",
            "multi_line_start_pattern": "^\\d{4}-\\d{2}-\\d{2}"
          }
        ]
      }
    }
  }
}
EOF

# Avviare il CloudWatch Agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
  -s

# Deploy tramite SSM (per fleet di istanze)
aws ssm send-command \
  --document-name "AmazonCloudWatch-ManageAgent" \
  --parameters 'action=configure,mode=ec2,optionalConfigurationLocation=/myapp/cloudwatch-agent-config,optionalRestart=yes' \
  --targets '[{"Key":"tag:Environment","Values":["production"]}]'
```

---

## CloudWatch Logs

### Struttura

```
CloudWatch Logs
└── Log Group (/myapp/application)
    ├── Log Stream (i-1234567890/myapp)
    │   ├── Log Event (timestamp + message)
    │   ├── Log Event
    │   └── ...
    └── Log Stream (i-abcdef/myapp)
        └── ...
```

**Log Group:** Contenitore logico per log della stessa applicazione/componente.
**Log Stream:** Flusso di log da una specifica fonte (es. singola istanza EC2, container, Lambda invocation).
**Log Event:** Singola riga di log con timestamp e messaggio.

```bash
# Creare un log group con retention
aws logs create-log-group \
  --log-group-name "/myapp/application" \
  --tags Environment=production,App=myapp

# Impostare retention (1 giorno fino a mai)
aws logs put-retention-policy \
  --log-group-name "/myapp/application" \
  --retention-in-days 90  # 1,3,5,7,14,30,60,90,120,150,180,365,400,545,731,1096,1827,2192,2557,2922,3288,3653

# Inviare log manualmente
aws logs put-log-events \
  --log-group-name "/myapp/application" \
  --log-stream-name "manual-stream" \
  --log-events '[
    {"timestamp": 1705312800000, "message": "Application started"},
    {"timestamp": 1705312801000, "message": "Listening on port 8080"}
  ]'

# Cercare log
aws logs filter-log-events \
  --log-group-name "/myapp/application" \
  --start-time $(($(date +%s) - 3600))000 \
  --filter-pattern "[timestamp, level=ERROR, ...]" \
  --limit 100

# Tail di un log group (equivalente tail -f)
aws logs tail "/myapp/application" --follow --format short
```

### Subscription Filters

I Subscription Filters inviano eventi di log in real-time a una destinazione (Lambda, Kinesis Streams, Kinesis Firehose, OpenSearch).

```bash
# Subscription verso Lambda
aws logs put-subscription-filter \
  --log-group-name "/myapp/application" \
  --filter-name "ErrorsToLambda" \
  --filter-pattern "ERROR" \
  --destination-arn arn:aws:lambda:us-east-1:123456789012:function:process-errors

# Subscription verso Kinesis (per analytics in real-time)
aws logs put-subscription-filter \
  --log-group-name "/myapp/access" \
  --filter-name "AllToKinesis" \
  --filter-pattern "" \
  --destination-arn arn:aws:kinesis:us-east-1:123456789012:stream/log-stream \
  --role-arn arn:aws:iam::123456789012:role/CloudWatchToKinesisRole

# Cross-account subscription (verso account centralizzato)
# 1. Nel destination account: creare destination
aws logs put-destination \
  --destination-name "CrossAccountDestination" \
  --target-arn arn:aws:kinesis:us-east-1:DEST_ACCOUNT:stream/central-logs \
  --role-arn arn:aws:iam::DEST_ACCOUNT:role/CloudWatchDestinationRole

# 2. Nel source account: subscription al destination
aws logs put-subscription-filter \
  --log-group-name "/myapp/application" \
  --filter-name "ToCentralAccount" \
  --filter-pattern "" \
  --destination-arn arn:aws:logs:us-east-1:DEST_ACCOUNT:destination:CrossAccountDestination
```

### Metric Filters

I Metric Filters estraggono metriche numeriche dai log, permettendo di creare allarmi basati sul contenuto dei log.

```bash
# Contare gli errori 5xx dal log nginx
aws logs put-metric-filter \
  --log-group-name "/myapp/nginx/access" \
  --filter-name "HTTP5xx" \
  --filter-pattern '[ip, dash, user, timestamp, request, status_code=5*, bytes]' \
  --metric-transformations '[{
    "metricName": "HTTP5xxCount",
    "metricNamespace": "MyApp/Nginx",
    "metricValue": "1",
    "unit": "Count"
  }]'

# Estrarre latenza da log JSON strutturato
aws logs put-metric-filter \
  --log-group-name "/myapp/application" \
  --filter-name "RequestLatency" \
  --filter-pattern '{ $.level = "INFO" && $.duration_ms != "" }' \
  --metric-transformations '[{
    "metricName": "RequestDuration",
    "metricNamespace": "MyApp/Performance",
    "metricValue": "$.duration_ms",
    "unit": "Milliseconds"
  }]'
```

---

## CloudWatch Log Insights

Log Insights è il motore di query per analizzare log in CloudWatch. Usa un linguaggio simile a SQL con comandi specifici.

### Sintassi Base

```
fields @timestamp, @message
| filter @message like /pattern/
| stats count(*) as count by bin(1h)
| sort count desc
| limit 100
```

**Comandi principali:**
- `fields`: seleziona i campi da mostrare
- `filter`: filtra eventi (supporta regex, confronti, funzioni)
- `stats`: aggregazioni (count, sum, avg, min, max, pNN)
- `sort`: ordinamento
- `limit`: limitare il numero di risultati
- `parse`: estrae valori da testo con regex o glob
- `display`: formatta l'output finale

### Query Pratiche

```
# Top errori delle ultime 24 ore
fields @timestamp, @message, @logStream
| filter @message like /ERROR|Exception|FATAL/
| stats count(*) as error_count by @logStream
| sort error_count desc
| limit 20

# Latenza media per endpoint (log JSON strutturato)
fields @timestamp, endpoint, duration_ms, status_code
| filter ispresent(endpoint) and ispresent(duration_ms)
| stats
    avg(duration_ms) as avg_latency,
    pct(duration_ms, 95) as p95_latency,
    pct(duration_ms, 99) as p99_latency,
    count(*) as request_count
  by endpoint, bin(5m) as time_window
| sort time_window desc, avg_latency desc

# Analisi Lambda cold starts
fields @timestamp, @duration, @billedDuration, @initDuration
| filter @type = "REPORT"
| stats
    avg(@duration) as avg_duration,
    avg(@initDuration) as avg_cold_start,
    count(*) as invocations,
    sum(@billedDuration) / 1000 as total_billed_sec
  by bin(1h)

# Trovare IP con più richieste (potenziale DDoS)
fields @timestamp, clientIp, requestPath
| stats count(*) as requests by clientIp
| sort requests desc
| limit 50

# Visualizzazione time-series degli errori
fields @timestamp, @message
| filter @message like /ERROR/
| stats count(*) as error_count by bin(15m) as time_window
| sort time_window asc

# Parse di log non strutturati con regex
parse @message /(?P<level>INFO|ERROR|WARN|DEBUG)\s+(?P<component>\S+)\s+(?P<message>.+)/
| filter level = "ERROR"
| stats count(*) as count by component
| sort count desc
```

```bash
# Eseguire una query via CLI
aws logs start-query \
  --log-group-names "/myapp/application" \
  --start-time $(($(date +%s) - 3600)) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | limit 20'

# Ottenere i risultati
QUERY_ID="query-id-from-above"
aws logs get-query-results --query-id $QUERY_ID
```

---

## CloudWatch Alarms

### Tipi di Allarme

**Standard Alarm:** su una singola metrica per un periodo di tempo.

**Composite Alarm:** AND/OR di più allarmi. Riduce il rumore di allarmi correlati.

**Anomaly Detection Alarm:** usa ML per definire una banda di normalità dinamica basata sul comportamento storico della metrica.

### Stati degli Allarmi

- **OK:** la metrica è nei limiti definiti
- **ALARM:** la metrica ha superato la soglia
- **INSUFFICIENT_DATA:** dati insufficienti per valutare la condizione

### Configurare Allarmi

```bash
# Allarme CPU alta su EC2
aws cloudwatch put-metric-alarm \
  --alarm-name "HighCPU-prod-web-1" \
  --alarm-description "CPU > 80% per 5 minuti" \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-1234567890abcdef0 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 2 \
  --datapoints-to-alarm 2 \
  --treat-missing-data notBreaching \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:ops-alerts \
  --ok-actions arn:aws:sns:us-east-1:123456789012:ops-alerts \
  --insufficient-data-actions arn:aws:sns:us-east-1:123456789012:ops-alerts

# Allarme per errori 5xx (da Metric Filter o ALB)
aws cloudwatch put-metric-alarm \
  --alarm-name "HighErrorRate" \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value=app/my-alb/abc123 \
  --statistic Sum \
  --period 60 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:pagerduty

# Allarme per Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name "LambdaErrors-my-function" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=my-function \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:dev-alerts
```

### Composite Alarms

```bash
# Allarme composito: ALARM solo se ENTRAMBI CPU e Memory sono alti
aws cloudwatch put-composite-alarm \
  --alarm-name "HighLoadComposite" \
  --alarm-description "Allarme solo se CPU AND Memory sono alti simultaneamente" \
  --alarm-rule "ALARM(HighCPU-prod-web-1) AND ALARM(HighMemory-prod-web-1)" \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:critical-alerts

# Allarme che si attiva se QUALSIASI servizio del cluster è in ALARM
aws cloudwatch put-composite-alarm \
  --alarm-name "AnyClusterServiceDown" \
  --alarm-rule "ALARM(ServiceA-Health) OR ALARM(ServiceB-Health) OR ALARM(ServiceC-Health)" \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:ops-critical
```

### Anomaly Detection

```bash
# Creare un modello di anomaly detection
aws cloudwatch put-anomaly-detector \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions '[{"Name": "InstanceId", "Value": "i-1234567890abcdef0"}]' \
  --stat Average \
  --configuration '{
    "ExcludedTimeRanges": [
      {
        "StartTime": "2024-01-20T08:00:00Z",
        "EndTime": "2024-01-20T20:00:00Z"
      }
    ]
  }'

# Allarme basato su anomaly detection
aws cloudwatch put-metric-alarm \
  --alarm-name "AnomalousCPU" \
  --metrics '[
    {
      "Id": "m1",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/EC2",
          "MetricName": "CPUUtilization",
          "Dimensions": [{"Name": "InstanceId", "Value": "i-1234567890abcdef0"}]
        },
        "Period": 300,
        "Stat": "Average"
      }
    },
    {
      "Id": "ad1",
      "Expression": "ANOMALY_DETECTION_BAND(m1, 2)",
      "Label": "CPUUtilization (expected)"
    }
  ]' \
  --comparison-operator GreaterThanUpperThreshold \
  --threshold-metric-id ad1 \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:ops-alerts
```

### Metric Math

```bash
# Allarme su ratio di errori (errors/requests)
aws cloudwatch put-metric-alarm \
  --alarm-name "HighErrorRatio" \
  --metrics '[
    {
      "Id": "errors",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/ApplicationELB",
          "MetricName": "HTTPCode_Target_5XX_Count",
          "Dimensions": [{"Name": "LoadBalancer", "Value": "app/my-alb/abc123"}]
        },
        "Period": 60,
        "Stat": "Sum"
      },
      "ReturnData": false
    },
    {
      "Id": "requests",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/ApplicationELB",
          "MetricName": "RequestCount",
          "Dimensions": [{"Name": "LoadBalancer", "Value": "app/my-alb/abc123"}]
        },
        "Period": 60,
        "Stat": "Sum"
      },
      "ReturnData": false
    },
    {
      "Id": "error_ratio",
      "Expression": "IF(requests > 100, errors/requests*100, 0)",
      "Label": "Error Rate %",
      "ReturnData": true
    }
  ]' \
  --comparison-operator GreaterThanThreshold \
  --threshold 5 \
  --evaluation-periods 2
```

---

## EMF — Embedded Metric Format

EMF permette di creare metriche CloudWatch direttamente nei log strutturati, senza chiamare l'API `PutMetricData` separatamente. Questo riduce i costi e la complessità.

**Come funziona:** si scrive un log JSON con un campo `_aws` speciale che CloudWatch interpreta per estrarre metriche. Il costo è quello dei log (più economico delle API call PutMetricData).

```python
import json
import time

def emit_emf(metric_name: str, value: float, unit: str,
             namespace: str, dimensions: dict):
    """Emette una metrica tramite EMF nel log."""
    emf_log = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": namespace,
                "Dimensions": [list(dimensions.keys())],
                "Metrics": [{"Name": metric_name, "Unit": unit}]
            }]
        },
        metric_name: value,
        **dimensions
    }
    print(json.dumps(emf_log))  # Lambda invia stdout a CloudWatch Logs

# Uso in una Lambda function
def handler(event, context):
    start = time.time()
    result = process_order(event)
    duration = (time.time() - start) * 1000

    # Emette metrica senza API call separata
    emit_emf(
        metric_name="OrderProcessingTime",
        value=duration,
        unit="Milliseconds",
        namespace="MyApp/Orders",
        dimensions={
            "Service": "OrderProcessor",
            "Environment": os.environ.get("ENVIRONMENT", "unknown"),
            "OrderType": event.get("orderType", "standard")
        }
    )

    return result
```

**EMF con Lambda Powertools (raccomandato):**
```python
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

metrics = Metrics(namespace="MyApp/Orders", service="OrderProcessor")

@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    metrics.add_metric(name="OrdersProcessed", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name="OrderAmount", unit=MetricUnit.None, value=event['amount'])
    metrics.add_dimension(name="OrderType", value=event.get('type', 'standard'))
    return process(event)
```

---

## CloudWatch Dashboards

```bash
# Creare un dashboard via CLI
aws cloudwatch put-dashboard \
  --dashboard-name "ProductionOverview" \
  --dashboard-body file://dashboard.json

# Listare dashboard
aws cloudwatch list-dashboards

# Ottenere il JSON di un dashboard esistente
aws cloudwatch get-dashboard --dashboard-name "ProductionOverview"
```

**Esempio dashboard JSON:**
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "title": "API Gateway — Request Rate e Error Rate",
        "view": "timeSeries",
        "stacked": false,
        "metrics": [
          ["AWS/ApiGateway", "Count", "ApiName", "MyAPI", {"stat": "Sum", "period": 60}],
          ["AWS/ApiGateway", "5XXError", "ApiName", "MyAPI", {"stat": "Sum", "period": 60, "color": "#d62728"}]
        ],
        "period": 300,
        "region": "us-east-1"
      }
    },
    {
      "type": "alarm",
      "properties": {
        "title": "Allarmi Critici",
        "alarms": [
          "arn:aws:cloudwatch:us-east-1:123456789012:alarm:HighCPU",
          "arn:aws:cloudwatch:us-east-1:123456789012:alarm:HighErrorRate"
        ]
      }
    },
    {
      "type": "log",
      "properties": {
        "title": "Ultimi Errori",
        "query": "SOURCE '/myapp/application' | fields @timestamp, @message | filter @message like /ERROR/ | limit 20",
        "region": "us-east-1",
        "view": "table"
      }
    }
  ]
}
```

---

## Container Insights

Container Insights raccoglie metriche e log da cluster ECS e EKS, con visualizzazioni pre-built per CPU, memoria, network, disk e metriche a livello di pod/task.

```bash
# Abilitare Container Insights per ECS
aws ecs update-cluster-settings \
  --cluster my-ecs-cluster \
  --settings name=containerInsights,value=enabled

# Abilitare Container Insights per EKS
# Prima installare l'add-on ADOT o CloudWatch agent su EKS
aws eks create-addon \
  --cluster-name my-eks-cluster \
  --addon-name amazon-cloudwatch-observability

# Verificare il namespace di Container Insights
aws cloudwatch list-metrics \
  --namespace "ContainerInsights" \
  --query 'Metrics[*].MetricName' \
  --output text | tr '\t' '\n' | sort -u
```

---

## Best Practices

### Metriche

1. Usare **dimensioni significative** — non aggiungere troppi valori unici per dimensione (limiti di cardinalità)
2. **EMF** per Lambda e container — riduce costi API e latenza
3. **High-Resolution** solo quando necessario — costo più elevato
4. **GetMetricData** invece di GetMetricStatistics per query multiple

### Log

1. **Retention policy** su ogni log group — evitare accumulo infinito
2. **Structured logging** (JSON) — facilita le query con Log Insights e Metric Filters
3. **Log group naming convention:** `/aws/service/name` o `/myapp/component/environment`
4. **Subscription filter** verso S3 per archivio a lungo termine

### Allarmi

1. **Trattare missing data** appropriatamente — `notBreaching` per Lambda/intermittente, `breaching` per metriche continue
2. **Composite Alarms** per ridurre rumore — evitare alert storm
3. **Anomaly Detection** per metriche con pattern stagionali
4. **Evaluation Periods > 1** per evitare false positive su spike momentanei

---

## Troubleshooting

### Dati Mancanti in CloudWatch

1. Verificare che il CloudWatch Agent sia in esecuzione: `sudo systemctl status amazon-cloudwatch-agent`
2. Verificare i permessi IAM del ruolo dell'istanza (serve `cloudwatch:PutMetricData`, `logs:PutLogEvents`)
3. Verificare la connettività all'endpoint CloudWatch (usa VPC Endpoint se in VPC privata)

### Allarme Bloccato in INSUFFICIENT_DATA

1. Verificare che le dimensioni dell'allarme corrispondano esattamente a quelle della metrica
2. Verificare che la metrica esista (potrebbe essere stata eliminata o rinominata)
3. Aumentare il `evaluation-periods` per dare più tempo alla metrica di arrivare

### Log Insights: Risultati Vuoti

1. Verificare l'intervallo temporale — deve coprire il periodo dei log cercati
2. Verificare che il log group sia corretto (case-sensitive)
3. Il pattern regex non deve avere slash aggiuntivi: `like /ERROR/` non `like //ERROR//`

---

## Relazioni

??? info "X-Ray e OpenTelemetry"
    CloudWatch si integra con X-Ray per il distributed tracing. ADOT (AWS Distro for OpenTelemetry — distribuzione AWS di OpenTelemetry per raccogliere metriche, log e trace) collector invia metriche sia a CloudWatch che a Prometheus.

    **Approfondimento completo →** [Observability](observability.md)

??? info "EventBridge"
    CloudWatch Alarms possono triggerare EventBridge rules per orchestrazione complessa degli allarmi.

    **Approfondimento completo →** [EventBridge e Kinesis](../messaging/eventbridge-kinesis.md)

??? info "Security — GuardDuty e Config"
    GuardDuty e Config pubblicano metriche e finding su CloudWatch. CloudTrail invia log a CloudWatch Logs.

    **Approfondimento completo →** [Compliance e Audit](../security/compliance-audit.md)

---

## Riferimenti

- [CloudWatch User Guide](https://docs.aws.amazon.com/cloudwatch/latest/monitoring/)
- [CloudWatch Logs User Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
- [CloudWatch Agent Configuration](https://docs.aws.amazon.com/cloudwatch-agent/)
- [Embedded Metric Format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html)
- [Lambda Powertools Metrics](https://docs.powertools.aws.dev/lambda/python/latest/core/metrics/)
- [CloudWatch Pricing](https://aws.amazon.com/cloudwatch/pricing/)
