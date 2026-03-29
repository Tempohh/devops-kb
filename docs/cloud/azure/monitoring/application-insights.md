---
title: "Application Insights"
slug: application-insights
category: cloud
tags: [azure, application-insights, apm, distributed-tracing, availability-tests, live-metrics, profiler]
search_keywords: [Application Insights APM monitoring, distributed tracing correlation, Application Map topology microservizi, Live Metrics Stream telemetry, Availability Tests ping multi-step, Smart Detection anomaly detection, Profiler CPU profiling production, Snapshot Debugger exceptions, adaptive sampling, OpenTelemetry Azure, connection string APPLICATIONINSIGHTS_CONNECTION_STRING]
parent: cloud/azure/monitoring/_index
related: [cloud/azure/compute/app-service-functions, cloud/azure/compute/aks-containers, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Application Insights

## Panoramica

Application Insights è il servizio APM (Application Performance Monitoring) di Azure, parte di Azure Monitor. Monitora le applicazioni live raccogliendo telemetria su: request (richieste HTTP), dependencies (chiamate a database, API esterne, code), exceptions (eccezioni non gestite), traces (log applicativi strutturati), custom events (eventi business), custom metrics e pageviews.

A differenza di Azure Monitor (che monitora l'infrastruttura), Application Insights monitora il comportamento interno dell'applicazione: quali path di codice sono lenti, dove si verificano le eccezioni, come si propagano le tracce attraverso i microservizi.

**Workspace-based** (preferito): usa un Log Analytics Workspace come backend storage, abilitando query KQL unificate su log applicativi e infrastrutturali.

## Creare Application Insights

```bash
RG="rg-monitoring-prod"
LOCATION="westeurope"
LAW_ID=$(az monitor log-analytics workspace show --resource-group $RG --workspace-name law-prod-westeurope-2026 --query id -o tsv)

# Creare Application Insights workspace-based
az monitor app-insights component create \
  --resource-group $RG \
  --app ai-myapp-prod \
  --location $LOCATION \
  --kind web \
  --workspace $LAW_ID \
  --application-type web

# Ottenere connection string (usare questo invece di Instrumentation Key — deprecato)
CONNECTION_STRING=$(az monitor app-insights component show \
  --resource-group $RG \
  --app ai-myapp-prod \
  --query connectionString -o tsv)

echo "Connection String: $CONNECTION_STRING"
# APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx;IngestionEndpoint=https://westeurope-5.in.applicationinsights.azure.com/;...
```

## SDK Integration

### Python

```bash
pip install opencensus-ext-azure
# Oppure con OpenTelemetry (più moderno):
pip install azure-monitor-opentelemetry
```

```python
# Metodo 1: OpenTelemetry (raccomandato, 2026+)
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
import logging
import os

# Configurare Azure Monitor con connection string
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    enable_live_metrics=True
)

# Tracing manuale
tracer = trace.get_tracer(__name__)

def process_order(order_id: str):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.type", "standard")

        # Le eccezioni vengono catturate automaticamente
        result = database.get_order(order_id)
        return result

# Logging va automaticamente a Application Insights
logger = logging.getLogger(__name__)
logger.info("Order processed", extra={"custom_dimension": {"order_id": "123"}})
logger.warning("Retry attempt", extra={"attempt": 3, "error": "timeout"})
logger.error("Payment failed", extra={"user_id": "u456", "amount": 99.99})
```

```python
# Metodo 2: OpenCensus (legacy ma ancora supportato)
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
import logging

# Setup logging con Azure Log Handler
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
))

# Custom event con proprietà
logger.warning("Custom event", extra={
    "custom_dimensions": {
        "user_id": "u123",
        "action": "purchase",
        "value": 45.99
    }
})
```

### Node.js

```bash
npm install applicationinsights
```

```javascript
// app.js — primo import nell'applicazione
const appInsights = require("applicationinsights");

appInsights.setup(process.env.APPLICATIONINSIGHTS_CONNECTION_STRING)
    .setAutoDependencyCorrelation(true)
    .setAutoCollectRequests(true)
    .setAutoCollectPerformance(true, true)
    .setAutoCollectExceptions(true)
    .setAutoCollectDependencies(true)
    .setAutoCollectConsole(true, true)
    .setUseDiskRetryCaching(true)
    .setSendLiveMetrics(true)
    .start();

const client = appInsights.defaultClient;

// Custom event
client.trackEvent({
    name: "OrderCompleted",
    properties: {
        orderId: "order-123",
        customerId: "cust-456",
        amount: 99.99
    }
});

// Custom metric
client.trackMetric({
    name: "CartSize",
    value: 5
});

// Custom exception
try {
    processPayment(order);
} catch (err) {
    client.trackException({
        exception: err,
        properties: { orderId: "order-123", paymentMethod: "credit_card" }
    });
}
```

### Auto-Instrumentation (Zero-Code)

Per App Service e AKS, non è necessario modificare il codice:

```bash
# App Service: abilitare auto-instrumentation
az webapp update \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --set "siteConfig.appSettings[0].name=APPLICATIONINSIGHTS_CONNECTION_STRING" \
  --set "siteConfig.appSettings[0].value=$CONNECTION_STRING"

# Per .NET:
az webapp config appsettings set \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING=$CONNECTION_STRING \
    ApplicationInsightsAgent_EXTENSION_VERSION=~3

# Per Java: agent si attacca automaticamente
# Per Node.js:
az webapp config appsettings set \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING=$CONNECTION_STRING \
    ApplicationInsightsAgent_EXTENSION_VERSION=~3 \
    NODE_OPTIONS=--require applicationinsights/out/applicationInsights.js
```

```bash
# AKS: auto-instrumentation via Azure Monitor Addon
az aks update \
  --resource-group rg-aks-prod \
  --name aks-prod-westeurope \
  --enable-addon monitoring \
  --workspace-resource-id $LAW_ID
```

## Distributed Tracing e Correlation

Application Insights correla automaticamente le request attraverso i microservizi usando correlation headers (W3C Trace Context).

```
Browser request → API Gateway → Service A → Service B → Database
     │                │               │          │           │
     └───────── operation_id ──────────────────────────────── (stesso ID su tutti)
```

```python
# Il SDK propaga automaticamente i correlation headers
# In una chiamata HTTP tra microservizi:
import requests
from opentelemetry.propagate import inject

headers = {}
inject(headers)  # Inietta W3C TraceContext e Baggage headers
response = requests.get("http://service-b/api/resource", headers=headers)
```

```kql
// Trovare tutte le operazioni di una specifica richiesta (cross-service)
union requests, dependencies, exceptions, traces
| where operation_Id == "OPERATION_ID_HERE"
| order by timestamp asc
| project timestamp, itemType, name, duration, success, message
```

## Application Map

L'Application Map visualizza automaticamente la topologia dei microservizi, mostrando:
- Dipendenze tra componenti (HTTP, database, storage, bus)
- Response time e failure rate per ogni link
- Alert attivi su ogni componente

```bash
# L'Application Map non richiede configurazione — si genera automaticamente
# dai dati di dependency tracking. Per visualizzarla:
# portal.azure.com → Application Insights → Application Map
```

## Live Metrics Stream

Live Metrics mostra telemetria in real-time (latency ~1 secondo) per debug di problemi live:
- Requests/sec e response time percentili
- Failure rate e exceptions/sec
- Dependency call rate e failure rate
- CPU e memoria dell'applicazione

```bash
# Live Metrics è disponibile automaticamente
# Non ha costo aggiuntivo (dati non persistono in Log Analytics)
# portal.azure.com → Application Insights → Live Metrics
```

## Availability Tests

Gli Availability Tests eseguono probe periodici sull'applicazione da più regioni geografiche.

```bash
# Creare Standard Availability Test (ping test)
az monitor app-insights web-test create \
  --resource-group $RG \
  --app-insights-name ai-myapp-prod \
  --web-test-name test-homepage-availability \
  --location westeurope \
  --frequency 300 \
  --timeout 30 \
  --enabled true \
  --retry-enabled true \
  --description "Availability test homepage" \
  --locations "us-il-ch1-azr" "emea-nl-ams-azr" "apac-sg-sin-azr" \
  --http-verbs GET \
  --request-url "https://myapp.example.com/health" \
  --expected-response-code 200 \
  --parse-dependent-requests false

# Alert automatico quando availability < 100%
az monitor metrics alert create \
  --resource-group $RG \
  --name alert-availability-low \
  --scopes $(az monitor app-insights component show --resource-group $RG --app ai-myapp-prod --query id -o tsv) \
  --condition "avg availabilityResults/availabilityPercentage < 95" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 1
```

## Smart Detection

Smart Detection usa machine learning per rilevare anomalie automaticamente, senza soglie manuali:
- **Failure Anomalies**: picchi anomali nel failure rate (ML-based, non soglia fissa)
- **Performance Degradation**: aumento anomalo di response time
- **Trace Severity Ratio Degradation**: aumento di warning/error nei log
- **Memory Leak Detection**: crescita memoria progressiva

Smart Detection è abilitato di default e invia notifiche email agli owner dell'Application Insights.

```bash
# Configurare notifiche Smart Detection
az monitor app-insights component update \
  --resource-group $RG \
  --app ai-myapp-prod \
  --kind web \
  --set "properties.ProactiveDiagnosticsEnabled=true"
```

## Profiler

Il Profiler raccoglie CPU flame graphs dell'applicazione in produzione con overhead <5%. Utile per identificare hotspot di performance senza riprodurre il problema in dev.

```bash
# Profiler è incluso per App Service (Standard tier+)
# Abilitare dal portale: Application Insights → Performance → Profiler

# Per VM o AKS, il Profiler Agent si installa separatamente
# O tramite SDK:
# applicationinsights configure --enable-agent
```

```kql
// Trovare richieste con profiler traces
requests
| where timestamp > ago(1h)
| where success == false or duration > 5000
| join kind=leftouter (
    exceptions
    | where timestamp > ago(1h)
) on operation_Id
| project timestamp, name, duration, success, type, outerMessage
| order by duration desc
```

## Snapshot Debugger

Snapshot Debugger cattura automaticamente uno snapshot dell'heap dell'applicazione quando si verifica un'eccezione, permettendo il debug post-mortem con variabili locali.

```python
# Python: snapshot si abilita tramite Application Insights SDK
# La cattura avviene automaticamente su eccezioni non gestite
# Disponibile su App Service, VM, AKS
```

```bash
# Abilitare Snapshot Debugger su App Service
az webapp config appsettings set \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --settings \
    APPLICATIONINSIGHTS_SNAPSHOT_DEBUGGER_ENABLED=true \
    APPLICATIONINSIGHTS_SNAPSHOT_DEBUGGER_MAX_SNAPSHOTS_PER_SECOND=1
```

## Sampling

Il sampling riduce la quantità di telemetria inviata (e il costo) mantenendo la rappresentatività statistica.

| Tipo | Descrizione | Quando Usare |
|---|---|---|
| **Adaptive** | Regola automaticamente il rate per mantenere sotto il target | Default, la maggior parte dei casi |
| **Fixed-rate** | Percentuale fissa (es: campiona 10% delle richieste) | Quando vuoi controllo preciso |
| **Ingestion** | Sampling lato server (scarta dati dopo ingestione) | Retroattivo su app già deployate |

```python
# Python: configurare Adaptive Sampling
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    # Adaptive sampling: mantieni 5 request/sec come target
    sampling_ratio=0.1  # 10% fixed rate
)
```

```javascript
// Node.js: configurare sampling
appInsights.setup(CONNECTION_STRING)
    .setSamplingPercentage(10)  // 10% delle richieste
    .start();
```

## Query KQL per Application Insights

```kql
// 1. Overview: request rate, failure rate, avg duration ultimi 30 min
requests
| where timestamp > ago(30m)
| summarize
    Requests = count(),
    FailedRequests = countif(success == false),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
| extend FailureRate = round(100.0 * FailedRequests / Requests, 2)

// 2. Top 10 endpoint più lenti
requests
| where timestamp > ago(1h)
| summarize
    Count = count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
  by name
| order by P95Duration desc
| take 10

// 3. Eccezioni raggruppate per tipo
exceptions
| where timestamp > ago(24h)
| summarize Count = count() by type, outerMessage
| order by Count desc
| take 20

// 4. Dependency failures (chiamate esterne fallite)
dependencies
| where timestamp > ago(1h)
| where success == false
| summarize Count = count() by name, type, resultCode
| order by Count desc

// 5. Analisi utenti per URL
pageViews
| where timestamp > ago(24h)
| summarize Users = dcount(user_Id), PageLoads = count() by url
| order by Users desc
| take 20

// 6. Latency percentili nel tempo
requests
| where timestamp > ago(3h)
| summarize
    P50 = percentile(duration, 50),
    P90 = percentile(duration, 90),
    P99 = percentile(duration, 99)
  by bin(timestamp, 5m)
| render timechart

// 7. Correlation: trovare user journey completo
let sessionId = "SESSION_ID_HERE";
union requests, pageViews, exceptions, customEvents
| where session_Id == sessionId
| order by timestamp asc
| project timestamp, itemType, name, duration, success, message, customDimensions

// 8. Rilevare pattern di errori (anomaly detection manuale)
let baseline_period = requests | where timestamp between (ago(7d) .. ago(1d)) | summarize BaselineFailures = avg(toint(success == false)) by bin(timestamp, 1h) | summarize AvgBaseline = avg(BaselineFailures);
requests
| where timestamp > ago(1h)
| summarize CurrentFailures = avg(toint(success == false))
| join kind=inner baseline_period on 1==1
| where CurrentFailures > AvgBaseline * 2
```

## Dashboard e Workbooks per Team Applicativi

```bash
# Creare workbook per team di sviluppo
az monitor workbook create \
  --resource-group $RG \
  --name workbook-app-team \
  --display-name "Application Team Dashboard" \
  --kind shared \
  --source-id $(az monitor app-insights component show --resource-group $RG --app ai-myapp-prod --query id -o tsv) \
  --serialized-data '...'
```

Dashboard consigliata per team applicativi:
- **Top**: request rate, failure rate, avg latency (last 1h)
- **Errors**: top eccezioni, failure trend, dependency failures
- **Performance**: P50/P90/P99 per endpoint, DB slow queries
- **Users**: active users, sessions, pageview funnel
- **Infrastructure**: CPU/memory App Service, autoscale events

## Best Practices

- Usa sempre **workspace-based Application Insights** (non classic) per query KQL unificate
- Configura **connection string** (non Instrumentation Key) — supporto a lungo termine
- Imposta **Adaptive Sampling** per produzione: riduce costi mantenendo rappresentatività
- Abilita **Snapshot Debugger** per debugging rapido di eccezioni production senza SSH
- Usa **custom events** per tracciare eventi business (ordini, pagamenti, conversioni) non solo HTTP
- Configura **Availability Tests** da almeno 3 regioni diverse per validare SLA
- Usa **Application Map** per identificare colli di bottiglia nei microservizi

## Troubleshooting

### Scenario 1 — Nessuna telemetria ricevuta (dati non appaiono nel portale)

**Sintomo**: L'app gira ma in Application Insights non arrivano request, eccezioni o log. Il Live Metrics è vuoto.

**Causa**: Connection string errata o non impostata, sampling al 0%, endpoint di ingestione irraggiungibile (firewall/NSG), oppure SDK non inizializzato prima del primo request handler.

**Soluzione**: Verificare la connection string, testare la connettività all'endpoint e controllare che `configure_azure_monitor()` / `appInsights.setup().start()` venga chiamato all'avvio dell'app, prima di qualsiasi middleware.

```bash
# 1. Verificare che la variabile d'ambiente sia valorizzata
echo $APPLICATIONINSIGHTS_CONNECTION_STRING

# 2. Controllare telemetria negli ultimi 5 minuti
az monitor app-insights query \
  --app ai-myapp-prod \
  --resource-group $RG \
  --analytics-query "union requests, traces, exceptions | where timestamp > ago(5m) | count"

# 3. Test diretto all'endpoint di ingestione (verificare raggiungibilità)
curl -s -o /dev/null -w "%{http_code}" \
  "https://westeurope-5.in.applicationinsights.azure.com/v2/track" \
  -X POST -H "Content-Type: application/json" -d '[]'
# Risposta attesa: 200 o 400 (endpoint raggiungibile); 0 o timeout = problema di rete

# 4. Controllare i log dell'SDK per errori di configurazione
# Python: abilitare debug logging
# import logging; logging.getLogger("azure").setLevel(logging.DEBUG)
```

---

### Scenario 2 — Dati parziali: solo alcune richieste appaiono (sampling aggressivo)

**Sintomo**: Application Insights mostra un volume di request molto inferiore al reale. Il sampling rate nel portale è < 100%.

**Causa**: Adaptive Sampling ha ridotto il rate (default: target 5 req/s). In ambienti ad alto traffico questo è normale, ma può nascondere errori rari.

**Soluzione**: Aumentare il target o passare a fixed-rate sampling per i dati critici. Usare `isSampledOut` in KQL per verificare l'esclusione.

```bash
# Verificare il sampling rate attuale in KQL
az monitor app-insights query \
  --app ai-myapp-prod \
  --resource-group $RG \
  --analytics-query "requests | where timestamp > ago(1h) | summarize avg(itemCount) by bin(timestamp, 5m) | render timechart"
# itemCount > 1 indica che ogni sample rappresenta più request reali
```

```python
# Python: aumentare target sampling (più dati, più costo)
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    sampling_ratio=1.0  # 100% — nessun sampling
)
```

---

### Scenario 3 — Distributed Tracing interrotto: operation_Id non correlato tra servizi

**Sintomo**: Nella Application Map i servizi appaiono disconnessi. Le query KQL su `operation_Id` non trovano i record del servizio downstream.

**Causa**: I correlation headers W3C TraceContext (`traceparent`, `tracestate`) non vengono propagati nelle chiamate HTTP. Può accadere se si usa un HTTP client non instrumentato, un proxy che rimuove gli header, o SDK con versioni diverse.

**Soluzione**: Assicurarsi di usare HTTP client instrumentati (es. `requests` con OpenTelemetry, `axios` con AppInsights SDK) e di iniettare i headers nelle chiamate manuali.

```python
# Propagazione manuale headers in Python (se il client HTTP non è auto-instrumentato)
from opentelemetry.propagate import inject
import requests as http_client

def call_downstream_service(url: str) -> dict:
    headers = {}
    inject(headers)  # Inietta traceparent e tracestate
    response = http_client.get(url, headers=headers)
    return response.json()
```

```kql
// Verificare correlazione: cercare operation_Id orfani (senza parent)
requests
| where timestamp > ago(1h)
| where isempty(operation_ParentId)
| summarize OrphanCount = count() by cloud_RoleName
// Un numero alto indica servizi che non ricevono gli header di correlazione
```

---

### Scenario 4 — Costi elevati: spesa Log Analytics superiore alle aspettative

**Sintomo**: La fattura Azure mostra un volume di ingestione molto alto per il workspace Log Analytics associato ad Application Insights.

**Causa**: Volume di telemetria elevato (es. ogni SQL query loggata come dependency), sampling non configurato, retention period lungo, o custom metrics con alta cardinalità.

**Soluzione**: Abilitare Adaptive Sampling, ridurre la retention a 30 giorni per i dati non critici, filtrare le dependency di bassa utilità (es. health checks), e usare `customMetrics` invece di `traces` per metriche numeriche.

```bash
# Analizzare volume per tipo di telemetria (ultimi 7 giorni)
az monitor app-insights query \
  --app ai-myapp-prod \
  --resource-group $RG \
  --analytics-query "
union requests, dependencies, exceptions, traces, customEvents, pageViews
| where timestamp > ago(7d)
| summarize TotalRows = count(), TotalSizeKB = sum(_BilledSize) / 1024 by itemType
| order by TotalSizeKB desc"

# Ridurre retention del workspace (default 90 giorni → 30 giorni)
LAW_ID=$(az monitor app-insights component show \
  --resource-group $RG --app ai-myapp-prod \
  --query workspaceResourceId -o tsv)
az monitor log-analytics workspace update \
  --ids $LAW_ID \
  --retention-time 30
```

```python
# Filtrare dependency non utili (es. health checks, blob polling)
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# Escludere endpoint specifici tramite filtro custom nel processor
# O configurare sampling solo per dipendenze critiche
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    sampling_ratio=0.1  # Ridurre a 10% per ambienti ad alto traffico
)
```

## Riferimenti

- [Documentazione Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview)
- [Python SDK (OpenTelemetry)](https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=python)
- [Node.js SDK](https://learn.microsoft.com/azure/azure-monitor/app/nodejs)
- [Distributed Tracing](https://learn.microsoft.com/azure/azure-monitor/app/distributed-tracing-telemetry-correlation)
- [Application Insights Profiler](https://learn.microsoft.com/azure/azure-monitor/app/profiler-overview)
- [Snapshot Debugger](https://learn.microsoft.com/azure/azure-monitor/app/snapshot-debugger)
- [Smart Detection](https://learn.microsoft.com/azure/azure-monitor/app/proactive-diagnostics)
- [Sampling](https://learn.microsoft.com/azure/azure-monitor/app/sampling)
