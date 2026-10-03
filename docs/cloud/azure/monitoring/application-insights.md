---
title: "Application Insights"
slug: application-insights
category: cloud
tags: [azure, application-insights, apm, distributed-tracing, availability-tests, live-metrics, profiler]
search_keywords: [Application Insights APM monitoring, distributed tracing correlation, Application Map topology microservizi, Live Metrics Stream telemetry, Availability Tests ping multi-step, Smart Detection anomaly detection, Profiler CPU profiling production, Snapshot Debugger exceptions, adaptive sampling, OpenTelemetry Azure, connection string APPLICATIONINSIGHTS_CONNECTION_STRING]
parent: cloud/azure/monitoring/_index
related: [cloud/azure/compute/app-service-functions, cloud/azure/compute/aks-containers, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview
status: needs-review
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Application Insights

## Panoramica

Application Insights è il servizio APM (Application Performance Monitoring) di Azure, parte di Azure Monitor. Monitora le applicazioni live raccogliendo telemetria su: request (richieste HTTP), dependencies (chiamate a database, API esterne, code), exceptions (eccezioni non gestite), traces (log applicativi strutturati), custom events (eventi business), custom metrics e pageviews.

A differenza di Azure Monitor (che monitora l'infrastruttura), Application Insights monitora il comportamento interno dell'applicazione: quali path di codice sono lenti, dove si verificano le eccezioni, come si propagano le tracce attraverso i microservizi.

**Workspace-based** (unica modalità): usa un Log Analytics Workspace come backend storage, abilitando query KQL unificate su log applicativi e infrastrutturali. Le risorse *classic* sono state ritirate (29 febbraio 2024) e non si possono più creare.

!!! note "Nomi delle tabelle KQL"
    Nel blade *Logs* della risorsa Application Insights (e con `az monitor app-insights query`) valgono i nomi classici: `requests`, `dependencies`, `exceptions`, `traces`, `customEvents`, `pageViews`, `customMetrics`. Interrogando direttamente il Log Analytics Workspace i nomi diventano `AppRequests`, `AppDependencies`, `AppExceptions`, `AppTraces`, `AppEvents`, `AppPageViews`, `AppMetrics` (colonne in PascalCase: `TimeGenerated`, `OperationId`, `Success`). Le query di questa pagina usano i nomi classici.

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

# Ottenere connection string (obbligatoria: l'ingestion con sola Instrumentation Key non è più supportata dal 31 marzo 2025)
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
pip install azure-monitor-opentelemetry
```

!!! warning "OpenCensus è ritirato"
    Gli SDK OpenCensus per Azure Monitor (`opencensus-ext-azure`) non sono più supportati da Microsoft (fine supporto settembre 2024). Per Python usare solo la distro OpenTelemetry (`azure-monitor-opentelemetry`); per migrare sostituire exporter/handler OpenCensus con `configure_azure_monitor()`.

```python
# OpenTelemetry — approccio supportato
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
import logging
import os

# Configurare Azure Monitor con connection string.
# Chiamare PRIMA di importare/creare l'app (Flask, Django, FastAPI...) per l'auto-instrumentation.
# Imposta OTEL_SERVICE_NAME=<nome-servizio>: diventa cloud_RoleName, cioè il nodo nell'Application Map.
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

# I log stdlib `logging` vanno in `traces`; le chiavi di `extra` diventano customDimensions
logger = logging.getLogger(__name__)
logger.info("Order processed", extra={"order_id": "123"})
logger.warning("Retry attempt", extra={"attempt": 3, "error": "timeout"})
logger.error("Payment failed", extra={"user_id": "u456", "amount": 99.99})
```

### Node.js

```bash
npm install applicationinsights
```

Dalla v3 il pacchetto `applicationinsights` è costruito su OpenTelemetry: l'API fluente `setup().setAutoCollect*()` è stata rimossa e si usa `useAzureMonitor()`. Per nuovi progetti preferire il pacchetto `@azure/monitor-opentelemetry` (stessa distro, API ufficiale OTel per span custom).

```javascript
// app.js — v3: da chiamare prima di ogni altro import (require/--require)
const { useAzureMonitor } = require("applicationinsights");

useAzureMonitor({
    azureMonitorExporterOptions: {
        connectionString: process.env.APPLICATIONINSIGHTS_CONNECTION_STRING
    },
    samplingRatio: 1.0   // 1.0 = 100%; vedi sezione Sampling
});
// OTEL_SERVICE_NAME=<nome-servizio> → cloud_RoleName
```

```javascript
// LEGACY (SDK v2) — solo per applicazioni non ancora migrate
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

// Custom event (API v2; in v3 la disponibilità di trackEvent/trackMetric/trackException
// va verificata, oppure usare span/metriche OpenTelemetry) <!-- REVIEW: verificare API custom telemetry in applicationinsights v3 -->
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

Un agent attaccato dall'esterno raccoglie telemetria senza modificare il codice. Su App Service si abilita dal portale (*Application Insights → Enable*) o con app setting; il supporto per linguaggio dipende dal sistema operativo del Web App (.NET, .NET Core, Java e Node.js: sì; Python: no, serve l'SDK).

```bash
# App Service (Linux): agent codeless via app settings
az webapp config appsettings set \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING="$CONNECTION_STRING" \
    ApplicationInsightsAgent_EXTENSION_VERSION=~3
# Windows: la versione dell'estensione dipende dal runtime (~2 per .NET Framework/.NET Core). <!-- REVIEW: verificare valori EXTENSION_VERSION per runtime/OS -->
```

!!! warning "Container Insights ≠ Application Insights"
    `az aks update --enable-addon monitoring` abilita **Container Insights** (metriche e log di nodi/pod su Log Analytics), non l'instrumentation applicativa. Per l'APM su AKS si usa l'auto-instrumentation di Application Insights (preview, per workload Java e Node.js, via `az aks update --enable-azure-monitor-app-monitoring` con estensione `aks-preview` e risorsa `Instrumentation`) oppure la distro OpenTelemetry nel codice. <!-- REVIEW: verificare stato GA e flag CLI dell'auto-instrumentation AKS -->

!!! tip "Autenticazione Entra ID"
    In produzione disabilitare l'ingestion con sola connection string (`DisableLocalAuth=true` sulla risorsa) e autenticare l'SDK con Microsoft Entra ID (ruolo *Monitoring Metrics Publisher* sulla risorsa, usando una managed identity): impedisce a chiunque conosca la connection string di inviare telemetria falsa.

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

Gli Availability Tests eseguono probe periodici sull'applicazione da più regioni geografiche. Tipi attuali:

- **Standard test**: singola richiesta HTTP (verbo, header, body, validazione status/contenuto, scadenza certificato TLS). È il tipo da usare.
- **Custom TrackAvailability**: codice proprio (Azure Functions, ecc.) che chiama `TrackAvailability()`; sostituisce i vecchi test multi-step.
- **URL ping test (classic)**: ritirati il 30 settembre 2026 → migrare a Standard test. I multi-step web test (Visual Studio `.webtest`) sono già stati ritirati.

```bash
# Creare Standard test (--kind standard). Il tag hidden-link lega il test alla risorsa Application Insights.
AI_ID=$(az monitor app-insights component show --resource-group $RG --app ai-myapp-prod --query id -o tsv)

az monitor app-insights web-test create \
  --resource-group $RG \
  --name test-homepage-availability \
  --location westeurope \
  --defined-web-test-name test-homepage-availability \
  --kind standard \
  --enabled true \
  --frequency 300 \
  --timeout 30 \
  --retry-enabled true \
  --synthetic-monitor-id test-homepage-availability \
  --locations Id="us-il-ch1-azr" Id="emea-nl-ams-azr" Id="apac-sg-sin-azr" \
  --request-url "https://myapp.example.com/health" \
  --http-verb GET \
  --expected-status-code 200 \
  --tags "hidden-link:$AI_ID=Resource"
# <!-- REVIEW: verificare nomi/flag esatti di `az monitor app-insights web-test create` (estensione application-insights) -->

# Alert quando availability scende sotto il 95% (finestra 5 min)
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

Smart Detection usa machine learning per rilevare anomalie rispetto al comportamento storico, senza soglie manuali:
- **Failure Anomalies**: picchi anomali nel failure rate. Oggi è una *smart detection alert rule* in Azure Monitor (`microsoft.alertsmanagement/smartdetectoralertrules`), quindi le notifiche passano da **Action Group** come ogni altro alert.
- **Performance Degradation**: aumento anomalo di response time o di dependency duration
- **Trace Severity Ratio Degradation**: aumento di warning/error nei log
- **Memory Leak Detection**: crescita progressiva della memoria

Le regole sono create di default con la risorsa. Per le notifiche configurare l'Action Group della regola (portale: *Application Insights → Alerts → Alert rules / Smart Detection settings*); non c'è un flag dedicato su `az monitor app-insights component update`.

## Profiler

Il Profiler campiona gli stack trace dell'applicazione in produzione (a intervalli e per brevi finestre, con overhead contenuto) e li mostra come flame graph per singola richiesta lenta. Utile per trovare hotspot senza riprodurre il problema in dev. Supporto principale: applicazioni .NET (App Service, VM, AKS/container tramite pacchetto NuGet `Microsoft.ApplicationInsights.Profiler.AspNetCore`); per Java esiste un profiler dedicato basato su JFR.

```bash
# App Service: abilitare dal portale (Application Insights → Performance → Profiler).
# Richiede un piano App Service Basic o superiore. <!-- REVIEW: verificare tier minimo corrente e opzioni CLI -->
# Per VM / container: aggiungere il pacchetto NuGet al progetto .NET e chiamare AddServiceProfiler().
```

```kql
// Candidati per il Profiler: richieste lente o fallite con eventuale eccezione associata
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

Snapshot Debugger cattura uno snapshot (minidump con stack e variabili locali) quando si verifica un'eccezione "first chance" su un'applicazione **.NET / .NET Core**, permettendo il debug post-mortem da Visual Studio senza fermare l'app. Non è disponibile per Python o Node.js: lì servono log/eccezioni strutturati e span OpenTelemetry.

Abilitazione su App Service: dal portale (*Application Insights → Snapshot Debugger*) oppure con l'estensione del sito; per VM/container si usa il pacchetto NuGet `Microsoft.ApplicationInsights.SnapshotCollector`. <!-- REVIEW: verificare app setting esatti (SnapshotDebugger_EXTENSION_VERSION) e stato di supporto corrente di Snapshot Debugger -->

```csharp
// .NET: registrazione del collector (pacchetto Microsoft.ApplicationInsights.SnapshotCollector)
builder.Services.AddSnapshotCollector(config => builder.Configuration.Bind(nameof(SnapshotCollectorConfiguration), config));
```

## Sampling

Il sampling riduce la quantità di telemetria inviata (e il costo) mantenendo la rappresentatività statistica.

| Tipo | Descrizione | Quando Usare |
|---|---|---|
| **Adaptive** | Regola automaticamente il rate per restare sotto un target (default 5 item/s) | SDK classici .NET; non esiste negli SDK OpenTelemetry |
| **Fixed-rate** | Percentuale fissa (es: campiona 10% delle richieste) | Default pratico con OpenTelemetry; controllo preciso del costo |
| **Rate-limited** | Limita le trace al secondo (`traces_per_second`) | Distro OpenTelemetry Python/JS/Java più recenti |
| **Ingestion** | Il servizio scarta una % di telemetria all'arrivo, prima dello storage | Quando non si può ridisegnare l'SDK; non agisce sui dati già salvati e non si applica se l'SDK sta già campionando |

Il sampling coerente per `operation_Id` mantiene o scarta **l'intera trace**, quindi le correlazioni cross-service restano intatte se tutti i servizi usano lo stesso rapporto.

```python
# Python (distro OpenTelemetry): fixed-rate
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    sampling_ratio=0.1  # 10% delle trace
)
# Versioni recenti espongono anche traces_per_second (rate-limited). <!-- REVIEW: verificare parametri sampling correnti di configure_azure_monitor -->
```

```javascript
// Node.js v3: samplingRatio in useAzureMonitor
useAzureMonitor({ samplingRatio: 0.1 });   // 10%
// Node.js v2 (legacy): appInsights.setup(CS).setSamplingPercentage(10).start();
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

// 8. Rilevare pattern di errori (confronto con baseline degli ultimi 7 giorni)
let baseline = toscalar(
    requests
    | where timestamp between (ago(7d) .. ago(1d))
    | summarize avg(toint(success == false)));
requests
| where timestamp > ago(1h)
| summarize CurrentFailures = avg(toint(success == false))
| extend Baseline = baseline
| where CurrentFailures > Baseline * 2
```

## Dashboard e Workbooks per Team Applicativi

```bash
# Creare workbook per team di sviluppo (il nome della risorsa deve essere un GUID)
az monitor app-insights workbook create \
  --resource-group $RG \
  --name "$(uuidgen)" \
  --display-name "Application Team Dashboard" \
  --category workbook \
  --location westeurope \
  --source-id $(az monitor app-insights component show --resource-group $RG --app ai-myapp-prod --query id -o tsv) \
  --serialized-data @workbook.json
# <!-- REVIEW: verificare flag di `az monitor app-insights workbook create` -->
# In pratica: costruire il workbook dal portale ed esportarne il JSON (Advanced editor) per versionarlo in IaC.
```

Dashboard consigliata per team applicativi:
- **Top**: request rate, failure rate, avg latency (last 1h)
- **Errors**: top eccezioni, failure trend, dependency failures
- **Performance**: P50/P90/P99 per endpoint, DB slow queries
- **Users**: active users, sessions, pageview funnel
- **Infrastructure**: CPU/memory App Service, autoscale events

## Best Practices

- Usa un'unica **workspace-based Application Insights** per ambiente, collegata al Log Analytics Workspace del team: query KQL unificate con i log infrastrutturali
- Configura **connection string** (la sola Instrumentation Key non è più accettata) e valuta **Entra ID auth** con `DisableLocalAuth`
- Imposta un **sampling** esplicito in produzione (adaptive sugli SDK classici .NET, fixed/rate-limited con OpenTelemetry): riduce costi mantenendo rappresentatività
- Imposta `OTEL_SERVICE_NAME` / `cloud_RoleName` per ogni servizio, altrimenti l'Application Map unisce o confonde i nodi
- Su .NET abilita **Snapshot Debugger** per debugging rapido di eccezioni production senza SSH
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

**Causa**: Il sampling (adaptive sugli SDK classici, target default 5 item/s; ratio o rate-limited con OpenTelemetry; oppure ingestion sampling lato servizio) scarta parte della telemetria. In ambienti ad alto traffico è normale, ma può nascondere errori rari.

**Soluzione**: Aumentare il target/ratio o disabilitare il sampling per i dati critici. Verificare la percentuale effettiva con `itemCount` (ogni record campionato rappresenta `itemCount` eventi reali; i conteggi corretti si ottengono con `sum(itemCount)`, non con `count()`).

```bash
# Verificare il sampling rate attuale in KQL
az monitor app-insights query \
  --app ai-myapp-prod \
  --resource-group $RG \
  --analytics-query "requests | where timestamp > ago(1h) | summarize avg(itemCount) by bin(timestamp, 5m) | render timechart"
# itemCount > 1 indica che ogni sample rappresenta più request reali
```

```python
# Python: disabilitare il sampling (più dati, più costo)
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

**Soluzione**: Abilitare il sampling, impostare un **daily cap** sul workspace come rete di sicurezza, ridurre la retention per i dati non critici (la retention inclusa gratuitamente per le tabelle Application Insights è 90 giorni: ridurla sotto non riduce l'ingestion, che è la voce di costo principale), escludere le richieste di bassa utilità (es. health check) e usare `customMetrics` invece di `traces` per metriche numeriche.

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

```bash
# Escludere dalla telemetria gli endpoint rumorosi (health check) senza modificare il codice.
# Variabile OpenTelemetry standard: lista di regex separate da virgola, per libreria instrumentata.
export OTEL_PYTHON_EXCLUDED_URLS="/health,/ready"          # tutte le librerie HTTP Python
export OTEL_PYTHON_FLASK_EXCLUDED_URLS="/health,/ready"    # solo Flask
```

```python
# Ridurre il volume di trace in ambienti ad alto traffico
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    sampling_ratio=0.1  # 10%
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
