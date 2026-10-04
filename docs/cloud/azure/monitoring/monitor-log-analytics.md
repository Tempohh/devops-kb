---
title: "Azure Monitor & Log Analytics"
slug: monitor-log-analytics
category: cloud
tags: [azure, azure-monitor, log-analytics, metrics, alerts, workbooks, diagnostic-settings, kql]
search_keywords: [Azure Monitor metrics logs traces, Log Analytics Workspace KQL Kusto, Diagnostic Settings resource logs, Azure Monitor Agent AMA OMS MMA, metric alert log alert activity log alert, Action Group email SMS webhook, Workbooks dashboard, Container Insights AKS pods, data retention archive, Azure Monitor for VMs]
parent: cloud/azure/monitoring/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/compute/aks-containers, cloud/azure/security/defender-sentinel, cloud/azure/monitoring/application-insights]
official_docs: https://learn.microsoft.com/azure/azure-monitor/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Monitor & Log Analytics

## Panoramica

Azure Monitor è la piattaforma unificata di observability di Azure. Raccoglie tre tipi fondamentali di segnali:
- **Metrics**: serie temporali numeriche (CPU%, memoria, latency) — alta frequenza, retention 93 giorni
- **Logs**: dati testuali strutturati inviati a Log Analytics Workspace — queryabili con KQL
- **Traces**: dati di distributed tracing per Application Insights

Tutto converge in Log Analytics Workspace, che funge da repository centrale per tutti i log dell'infrastruttura Azure, VM, container, database e applicazioni.

## Log Analytics Workspace

```bash
RG="rg-monitoring-prod"
LOCATION="westeurope"
LAW_NAME="law-prod-westeurope-2026"

# Creare Log Analytics Workspace
az monitor log-analytics workspace create \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --location $LOCATION \
  --sku PerGB2018 \
  --retention-time 90

# Configurare retention differenziata per tabella (fino a 730 giorni)
az monitor log-analytics workspace table update \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --name SecurityEvent \
  --retention-time 365

# Archive tier (fino a 12 anni, costo molto basso)
az monitor log-analytics workspace table update \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --name AzureActivity \
  --total-retention-time 2557  # 7 anni

# Ottenere ID workspace (necessario per diagnostic settings)
LAW_ID=$(az monitor log-analytics workspace show \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --query id -o tsv)

# Listare tabelle nel workspace
az monitor log-analytics workspace table list \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --output table
```

## Metriche Azure Monitor

Le metriche sono disponibili automaticamente per ogni risorsa Azure senza configurazione. Si possono interrogare via CLI, portale o API.

```bash
# Listare metriche disponibili per una risorsa
az monitor metrics list-definitions \
  --resource /subscriptions/SUB_ID/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/my-vm \
  --output table

# Interrogare metrica specifica
az monitor metrics list \
  --resource /subscriptions/SUB_ID/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/my-vm \
  --metric "Percentage CPU" \
  --interval PT5M \
  --aggregation Average Maximum \
  --start-time 2026-02-26T00:00:00Z \
  --end-time 2026-02-26T23:59:59Z \
  --output json

# Metrica per App Service
az monitor metrics list \
  --resource $(az webapp show --resource-group rg-webapp-prod --name myapp-prod --query id -o tsv) \
  --metric "Http5xx" "Requests" "ResponseTime" \
  --interval PT1M \
  --aggregation Count Average \
  --start-time $(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)
```

## Diagnostic Settings

I Diagnostic Settings abilitano l'invio di logs e metriche delle risorse Azure a Log Analytics, Storage Account e/o Event Hubs. Servono perché i **resource logs** non sono raccolti di default: senza un Diagnostic Setting la risorsa li scarta (solo metriche piattaforma e Activity Log sono automatici).

!!! warning "retentionPolicy deprecato"
    Il campo `retentionPolicy` dei Diagnostic Settings è deprecato: la retention si gestisce sul workspace/tabella (o con lifecycle management sullo Storage Account), non per singolo setting. Per questo gli esempi seguenti non lo usano.

```bash
# Diagnostic Settings per una VM (Azure Monitor Agent — vedi sotto per AMA)
# Per risorse come App Service, SQL, Key Vault:
az monitor diagnostic-settings create \
  --resource $(az webapp show --resource-group rg-webapp-prod --name myapp-prod --query id -o tsv) \
  --name diag-appservice-prod \
  --workspace $LAW_ID \
  --logs '[
    {"category": "AppServiceHTTPLogs", "enabled": true},
    {"category": "AppServiceAppLogs", "enabled": true},
    {"category": "AppServiceAuditLogs", "enabled": true},
    {"category": "AppServiceIPSecAuditLogs", "enabled": true},
    {"category": "AppServicePlatformLogs", "enabled": true}
  ]' \
  --metrics '[{"category": "AllMetrics", "enabled": true}]'

# Diagnostic Settings per Azure SQL
az monitor diagnostic-settings create \
  --resource $(az sql server show --resource-group rg-database-prod --name sqlsrv-prod-2026 --query id -o tsv)/databases/myapp-production \
  --name diag-sql-prod \
  --workspace $LAW_ID \
  --logs '[
    {"category": "SQLInsights", "enabled": true},
    {"category": "AutomaticTuning", "enabled": true},
    {"category": "QueryStoreRuntimeStatistics", "enabled": true},
    {"category": "QueryStoreWaitStatistics", "enabled": true},
    {"category": "Errors", "enabled": true},
    {"category": "DatabaseWaitStatistics", "enabled": true},
    {"category": "Timeouts", "enabled": true},
    {"category": "Blocks", "enabled": true},
    {"category": "Deadlocks", "enabled": true}
  ]' \
  --metrics '[{"category": "Basic", "enabled": true}, {"category": "InstanceAndAppAdvanced", "enabled": true}]'

# Diagnostic Settings per Key Vault
az monitor diagnostic-settings create \
  --resource $(az keyvault show --resource-group rg-security-prod --name kv-prod-myapp-2026 --query id -o tsv) \
  --name diag-keyvault-prod \
  --workspace $LAW_ID \
  --logs '[
    {"category": "AuditEvent", "enabled": true},
    {"category": "AzurePolicyEvaluationDetails", "enabled": true}
  ]' \
  --metrics '[{"category": "AllMetrics", "enabled": true}]'
```

## Azure Monitor Agent (AMA)

AMA è l'agente unificato per raccogliere log e metriche dalle VM, sostituendo MMA (Microsoft Monitoring Agent, alias Log Analytics agent) e OMS Agent, **ritirati il 31 agosto 2024**: non ricevono più supporto e vanno migrati ad AMA. A differenza degli agent legacy, AMA non ha configurazione locale: *cosa* raccogliere è definito centralmente nelle Data Collection Rules (DCR), associabili a molte VM, e l'autenticazione usa la managed identity della VM.

```bash
# Installare AMA su VM Linux
az vm extension set \
  --resource-group $RG \
  --vm-name my-vm \
  --name AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true

# Installare AMA su VM Windows
az vm extension set \
  --resource-group $RG \
  --vm-name my-win-vm \
  --name AzureMonitorWindowsAgent \
  --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true

# Data Collection Rule (DCR): definisce quali dati raccogliere e dove inviarli
az monitor data-collection rule create \
  --resource-group $RG \
  --name dcr-vm-performance \
  --location $LOCATION \
  --data-sources '{
    "performanceCounters": [
      {
        "streams": ["Microsoft-Perf"],
        "samplingFrequencyInSeconds": 60,
        "counterSpecifiers": [
          "\\Processor(_Total)\\% Processor Time",
          "\\Memory\\% Committed Bytes In Use",
          "\\LogicalDisk(_Total)\\% Free Space",
          "\\Network Interface(*)\\Bytes Total/sec"
        ],
        "name": "perf-counters"
      }
    ],
    "syslog": [
      {
        "streams": ["Microsoft-Syslog"],
        "facilityNames": ["kern", "mail", "daemon", "auth", "syslog", "user"],
        "logLevels": ["Warning", "Error", "Critical", "Alert", "Emergency"],
        "name": "syslog-collection"
      }
    ]
  }' \
  --destinations '{
    "logAnalytics": [
      {
        "workspaceResourceId": "'"$LAW_ID"'",
        "name": "la-destination"
      }
    ]
  }' \
  --data-flows '[
    {
      "streams": ["Microsoft-Perf", "Microsoft-Syslog"],
      "destinations": ["la-destination"]
    }
  ]'

# Associare DCR alla VM
az monitor data-collection rule association create \
  --resource-group $RG \
  --name dcra-my-vm \
  --rule-id $(az monitor data-collection rule show --resource-group $RG --name dcr-vm-performance --query id -o tsv) \
  --resource $(az vm show --resource-group $RG --name my-vm --query id -o tsv)
```

## KQL (Kusto Query Language)

KQL è il linguaggio per interrogare Log Analytics, Application Insights e Azure Data Explorer.

### Sintassi Base

```kql
// Struttura base: tabella | operatori
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "Processor"
| take 100

// Operatori comuni:
// where       - filtrare righe
// project     - selezionare colonne
// extend      - aggiungere colonne calcolate
// summarize   - aggregare dati
// order by    - ordinare
// join        - unire tabelle
// union       - unire risultati di query diverse
// parse       - estrarre valori da stringhe
// mv-expand   - espandere array
```

### Query Pratiche

```kql
// 1. VM con CPU > 80% nelle ultime ore
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "Processor" and CounterName == "% Processor Time"
| where InstanceName == "_Total"
| summarize AvgCPU = avg(CounterValue) by Computer, bin(TimeGenerated, 5m)
| where AvgCPU > 80
| order by AvgCPU desc

// 2. Top 10 errori nelle ultime 24 ore per applicazione
AppExceptions
| where TimeGenerated > ago(24h)
| summarize ErrorCount = count() by AppRoleName, ExceptionType, OuterMessage
| order by ErrorCount desc
| take 10

// 3. Richieste HTTP lente (> 2 secondi)
AppRequests
| where TimeGenerated > ago(1h)
| where DurationMs > 2000
| project TimeGenerated, Name, Url, DurationMs, ResultCode, AppRoleName
| order by DurationMs desc

// 4. Log di App Service — richieste 5xx
AppServiceHTTPLogs
| where TimeGenerated > ago(24h)
| where ScStatus >= 500
| project TimeGenerated, CIp, CsMethod, CsUriStem, ScStatus, TimeTaken
| order by TimeGenerated desc

// 5. Modifiche alle risorse Azure (Activity Log)
AzureActivity
| where TimeGenerated > ago(24h)
| where ActivityStatusValue == "Succeeded"
| where OperationNameValue startswith "Microsoft.Compute"
| project TimeGenerated, Caller, OperationNameValue, ResourceGroup, _ResourceId
| order by TimeGenerated desc

// 6. Analisi performance SQL Query
AzureDiagnostics
| where ResourceType == "SERVERS/DATABASES" and Category == "QueryStoreRuntimeStatistics"
| where TimeGenerated > ago(1h)
| project TimeGenerated, query_hash_s, avg_logical_io_reads_d, avg_duration_d, count_executions_d
| order by avg_duration_d desc
| take 20

// 7. Analisi spazio disco nelle VM
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "LogicalDisk" and CounterName == "% Free Space"
| where InstanceName != "_Total" and InstanceName != "HarddiskVolume"
| summarize AvgFreeSpace = avg(CounterValue) by Computer, InstanceName
| where AvgFreeSpace < 20
| order by AvgFreeSpace asc

// 8. Conta richieste per status code nell'ultima ora (webapp)
AppRequests
| where TimeGenerated > ago(1h)
| summarize Count = count() by ResultCode
| render piechart

// 9. Memory usage trend
Perf
| where TimeGenerated > ago(6h)
| where ObjectName == "Memory" and CounterName == "% Committed Bytes In Use"
| summarize AvgMemory = avg(CounterValue) by Computer, bin(TimeGenerated, 15m)
| render timechart

// 10. Analisi network: inbound/outbound bytes
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "Network Interface" and CounterName in ("Bytes Received/sec", "Bytes Sent/sec")
| summarize AvgBytes = avg(CounterValue) by Computer, CounterName, bin(TimeGenerated, 5m)
| render timechart
```

## Alerts

### Metric Alert

```bash
# Alert quando CPU media > 85% per 5 minuti
az monitor metrics alert create \
  --resource-group $RG \
  --name alert-cpu-high-my-vm \
  --scopes $(az vm show --resource-group $RG --name my-vm --query id -o tsv) \
  --condition "avg Percentage CPU > 85" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 2 \
  --description "CPU media sopra 85% per 5 minuti" \
  --action $(az monitor action-group show --resource-group $RG --name ag-ops-team --query id -o tsv)

# Alert multi-risorsa: una sola regola su più VM (stessa subscription e region).
# Con scope = resource group/subscription servono tipo e region; ogni VM è valutata separatamente.
az monitor metrics alert create \
  --resource-group $RG \
  --name alert-cpu-all-vms \
  --scopes /subscriptions/SUB_ID/resourceGroups/$RG \
  --target-resource-type Microsoft.Compute/virtualMachines \
  --target-resource-region $LOCATION \
  --condition "avg Percentage CPU > 90" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 1 \
  --action $(az monitor action-group show --resource-group $RG --name ag-ops-team --query id -o tsv)
```

### Log Alert (KQL-based)

```bash
# Alert quando ci sono errori 5xx nella webapp
# (estensione scheduled-query: az extension add --name scheduled-query)
# La condizione referenzia la query per nome (q1) e ne valuta il numero di righe.
az monitor scheduled-query create \
  --resource-group $RG \
  --name alert-http500-myapp \
  --scopes $LAW_ID \
  --condition "count 'q1' > 5" \
  --condition-query q1="AppServiceHTTPLogs | where ScStatus >= 500" \
  --evaluation-frequency 5m \
  --window-duration 5m \
  --severity 2 \
  --description "Più di 5 errori HTTP 5xx in 5 minuti" \
  --action-groups $(az monitor action-group show --resource-group $RG --name ag-ops-team --query id -o tsv)
```

### Activity Log Alert

```bash
# Alert quando viene eliminato un resource group
az monitor activity-log alert create \
  --resource-group $RG \
  --name alert-rg-deletion \
  --scopes /subscriptions/SUB_ID \
  --condition category=Administrative and operationName=Microsoft.Resources/subscriptions/resourceGroups/delete and status=Succeeded \
  --action-group $(az monitor action-group show --resource-group $RG --name ag-ops-team --query id -o tsv)
```

## Action Groups

Gli Action Groups definiscono cosa fare quando scatta un alert: notificare persone, chiamare webhook, eseguire runbook, ecc.

```bash
# Creare Action Group con email, SMS e webhook
az monitor action-group create \
  --resource-group $RG \
  --name ag-ops-team \
  --short-name OpsTeam \
  --action email ops-lead john.doe@example.com \
  --action sms sms-oncall 39 555123456 \
  --action webhook webhook-slack "https://hooks.slack.com/services/..." \
  --action logic-app logic-app-itsm /subscriptions/SUB_ID/resourceGroups/rg-security/providers/Microsoft.Logic/workflows/create-ticket "https://<logic-app-callback-url>"
# sms: NOME PREFISSO_PAESE NUMERO (senza + e spazi); logic-app: NOME RESOURCE_ID CALLBACK_URL

# Aggiornare Action Group aggiungendo Azure Function
az monitor action-group update \
  --resource-group $RG \
  --name ag-ops-team \
  --add-action azure-function \
    function-auto-remediate \
    /subscriptions/SUB_ID/resourceGroups/rg-functions/providers/Microsoft.Web/sites/func-remediation \
    auto_scale_out \
    "https://func-remediation.azurewebsites.net/api/auto_scale_out?code=..."
```

## Workbooks

I Workbooks Azure Monitor sono dashboard interattivi parametrizzati che combinano query KQL con visualizzazioni.

```bash
# Creare workbook personalizzato (richiede JSON di definizione; estensione application-insights,
# installata al primo uso). --name deve essere un UUID; --kind accetta solo "shared".
az monitor app-insights workbook create \
  --resource-group $RG \
  --name "$(uuidgen)" \
  --display-name "Web App Performance Dashboard" \
  --kind shared \
  --category workbook \
  --serialized-data @workbook-definition.json \
  --location $LOCATION
```

In pratica i workbook si costruiscono dal portale (galleria template) e si versionano esportando il JSON per ripubblicarlo via IaC (ARM/Bicep/Terraform `azurerm_application_insights_workbook`).

Workbook predefiniti utili:
- **Performance** (VM): CPU, memoria, disco, rete per flotta VM
- **Failures** (Application Insights): eccezioni, request failure, dependency failure
- **Traffic** (App Service): throughput, latency, errori per endpoint
- **Microsoft Entra ID Sign-ins** (ex Azure AD): analisi pattern di accesso
- **AKS**: node health, pod metrics, cluster overview

## Azure Monitor for VMs (VM Insights)

VM Insights abilita monitoring avanzato per VM: performance chart e (legacy) dependency map. Oggi si basa su AMA + una DCR dedicata (creata dal portale con "Enable" in VM Insights); il monitoring delle performance non dipende dal Dependency Agent.

!!! warning "Dependency Agent e VM Insights Map: deprecati, ritiro 30 giugno 2028"
    Il **Dependency Agent** e la funzione *Map* (tab Map, workbook *Connections Overview*, Service Map API) sono deprecati e **ritirati il 30 giugno 2028**. Dal 30 settembre 2025 non si possono onboardare nuove VM dal portale e Microsoft raccomanda di **non installarlo su nuovi sistemi**. I dati già ingeriti (`VMComputer`, `VMProcess`, `VMConnection`, `VMBoundPort`) restano nel workspace secondo la retention. Alternative indicate da Microsoft: soluzioni di terze parti dal Marketplace (categoria monitoring & diagnostics); per l'inventario, AMA + *Change Tracking and Inventory*. Su Azure Advisor la raccomandazione *Migrate from Dependency Agent and VM Insights Map* elenca le VM interessate.

```bash
# SOLO per offboarding/riferimento: Dependency Agent già presente (richiede AMA).
# Non usare per nuove installazioni. Rimozione:
az vm extension delete \
  --resource-group $RG \
  --vm-name my-vm \
  --name DependencyAgentLinux

# Installazione (sconsigliata, legacy)
az vm extension set \
  --resource-group $RG \
  --vm-name my-vm \
  --name DependencyAgentLinux \
  --publisher Microsoft.Azure.Monitoring.DependencyAgent \
  --enable-auto-upgrade true

# Dati storici della Map (VM Insights): la tabella VMConnection mostra connessioni TCP tra processi
```

```kql
// VM Connections (dati storici del Dependency Agent): processi che accettano connessioni
VMConnection
| where TimeGenerated > ago(1h)
| where Direction == "inbound"
| summarize ConnectionCount = count() by Computer, ProcessName, DestinationPort
| order by ConnectionCount desc
```

## Container Insights (AKS Monitoring)

```bash
# Abilitare Container Insights su AKS (usa AMA con managed identity sul cluster)
az aks enable-addons \
  --resource-group rg-aks-prod \
  --name aks-prod-westeurope \
  --addons monitoring \
  --workspace-resource-id $LAW_ID

# Metriche AKS su Azure Monitor
az monitor metrics list \
  --resource $(az aks show --resource-group rg-aks-prod --name aks-prod-westeurope --query id -o tsv) \
  --metric "node_cpu_usage_percentage" "node_memory_working_set_percentage" \
  --interval PT5M \
  --aggregation Average
```

```kql
// CPU per container (InstanceName è il path del container nel cluster; l'ultimo segmento è il nome)
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "K8SContainer" and CounterName == "cpuUsageNanoCores"
| summarize AvgCPUnc = avg(CounterValue) by InstanceName
| order by AvgCPUnc desc
| take 20

// Pod in CrashLoopBackOff
KubePodInventory
| where TimeGenerated > ago(1h)
| where ContainerStatus == "Waiting" and ContainerStatusReason == "CrashLoopBackOff"
| project TimeGenerated, Namespace, PodName, ContainerName, ContainerStatusReason

// Log di container specifico (ContainerLogV2: schema attuale, default per i nuovi cluster;
// la tabella legacy ContainerLog è deprecata)
ContainerLogV2
| where TimeGenerated > ago(1h)
| where PodNamespace == "production"
| where PodName contains "myapp"
| project TimeGenerated, PodName, ContainerName, LogMessage
| order by TimeGenerated desc
```

!!! tip "Metriche con Managed Prometheus"
    Per le metriche di cluster/pod la scelta attuale è **Azure Monitor managed service for Prometheus** + Azure Managed Grafana (query PromQL, costo per sample ingerito), lasciando a Container Insights i log (`ContainerLogV2`) e l'inventario. Evita di ingerire in `Perf`/`InsightsMetrics` metriche che Prometheus già copre.

## Data Retention e Costi

```bash
# Configurare retention workspace (default 30 giorni)
az monitor log-analytics workspace update \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --retention-time 90

# Archive tier per tabelle specifiche (costa meno ma richiede restore per query)
az monitor log-analytics workspace table update \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --name AuditLogs \
  --total-retention-time 2557  # 7 anni total: 90 gg interactive + resto archive

# Stimare costo ingestione dati (ordini di grandezza, i prezzi variano per region/valuta:
# verificare sulla pricing page)
# Log Analytics: ~$2.3-2.8/GB ingerito (Pay-as-you-go, piano tabella Analytics)
# Retention: prime 31 giorni inclusi, poi ~$0.10/GB/mese
# Archive: ~$0.02/GB/mese

# Configurare data cap (protezione da spike ingestione dati)
az monitor log-analytics workspace update \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --quota 10
```

Il costo dipende soprattutto dall'ingestione, quindi le leve sono: **piano tabella** (*Analytics* per query e alert completi; *Basic*/*Auxiliary* per log ad alto volume e basso valore, ingestione molto più economica ma query limitate e senza alert classici), **commitment tier** (sconto da ~100 GB/giorno) e **DCR transformation** per filtrare/ridurre le colonne prima dell'ingestione.

!!! warning "Daily cap"
    Raggiunto il cap, il workspace **smette di ingerire** i dati fatturabili fino al reset giornaliero: si perdono log (e alert basati su di essi). Usalo come protezione di costo su ambienti non-prod; in produzione preferisci alert sull'ingestione.

## Best Practices

- Usa **Data Collection Rules (DCR)** invece degli agent legacy (MMA/OMS) — più flessibili e meno overhead
- Configura **Diagnostic Settings** su tutte le risorse Azure critiche (SQL, Key Vault, App Service)
- Separa workspace per ambienti di produzione e non-produzione per isolamento RBAC e costi
- Imposta **daily quota** sul workspace per protezione da spike di ingestione
- Usa **Archive tier** per log di compliance long-term invece di mantenere tutto nello interactive tier
- Per alert, privilegia **Metric Alert** (valutazione ogni minuto, bassa latenza, costo minore) su **Log Alert** (query KQL, più flessibile ma con latenza di ingestione e costo per regola) quando la metrica esiste già
- Gestisci Workspace, DCR, Diagnostic Settings e alert come codice (Bicep/Terraform) e assegna i Diagnostic Settings con **Azure Policy** (`DeployIfNotExists`) così le nuove risorse nascono già monitorate

## Troubleshooting

### Scenario 1 — I log non arrivano nel Log Analytics Workspace

**Sintomo:** Le tabelle nel workspace sono vuote o mancano log attesi da una risorsa Azure (App Service, Key Vault, SQL, ecc.).

**Causa:** Diagnostic Settings non configurati o configurati con categorie errate; latenza di ingestione fino a 15 minuti per log nuovi.

**Soluzione:** Verificare che i Diagnostic Settings esistano e puntino al workspace corretto.

```bash
# Listare diagnostic settings su una risorsa
az monitor diagnostic-settings list \
  --resource $(az webapp show --resource-group rg-webapp-prod --name myapp-prod --query id -o tsv) \
  --output table

# Verificare che il workspace target sia corretto
az monitor diagnostic-settings show \
  --resource $(az webapp show --resource-group rg-webapp-prod --name myapp-prod --query id -o tsv) \
  --name diag-appservice-prod \
  --query "workspaceId" -o tsv

# Query per controllare quando è arrivato l'ultimo log
# (nel portale o via REST)
# AppServiceHTTPLogs | summarize max(TimeGenerated) by _ResourceId
```

---

### Scenario 2 — Azure Monitor Agent (AMA) non invia dati dalla VM

**Sintomo:** La tabella `Perf` o `Syslog` non contiene dati per una VM specifica; `Heartbeat` non mostra la VM.

**Causa:** Estensione AMA non installata o in errore; Data Collection Rule non associata alla VM; identità managed non configurata.

**Soluzione:** Verificare lo stato dell'estensione e l'associazione DCR.

```bash
# Controllare stato estensione AMA
az vm extension show \
  --resource-group $RG \
  --vm-name my-vm \
  --name AzureMonitorLinuxAgent \
  --query "{state: provisioningState, status: instanceView.statuses[0].displayStatus}"

# Listare associazioni DCR per la VM
az monitor data-collection rule association list \
  --resource $(az vm show --resource-group $RG --name my-vm --query id -o tsv) \
  --output table

# Query KQL: heartbeat VM nell'ultima ora
# Heartbeat | where Computer == "my-vm" | summarize max(TimeGenerated)

# Re-installare AMA se in errore
az vm extension delete --resource-group $RG --vm-name my-vm --name AzureMonitorLinuxAgent
az vm extension set \
  --resource-group $RG --vm-name my-vm \
  --name AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true
```

---

### Scenario 3 — Un alert non scatta nonostante la condizione sia soddisfatta

**Sintomo:** CPU alta o errori HTTP 500 visibili sui grafici, ma nessuna notifica dall'alert.

**Causa:** Alert in stato `Disabled`; Action Group con email/webhook non validi; finestra di valutazione troppo larga; alert di tipo Log con query che non restituisce dati nel window.

**Soluzione:** Verificare stato alert e testare l'Action Group.

```bash
# Listare metric alerts e il loro stato
az monitor metrics alert list \
  --resource-group $RG \
  --output table

# Verificare se l'alert è abilitato
az monitor metrics alert show \
  --resource-group $RG \
  --name alert-cpu-high-my-vm \
  --query "{enabled: enabled, severity: severity, fired: criteria}"

# Testare l'Action Group inviando una notifica di test
az monitor action-group test-notifications create \
  --resource-group $RG \
  --action-group ag-ops-team \
  --alert-type metricstaticthreshold \
  --add-action email ops-lead john.doe@example.com

# Per log alert: verificare che la query restituisca dati
# Eseguire manualmente la query KQL nel workspace nel periodo di valutazione
```

---

### Scenario 4 — Query KQL lente o senza risultati attesi

**Sintomo:** Una query KQL impiega molto tempo o restituisce 0 righe nonostante i log esistano.

**Causa:** Filtro `TimeGenerated` mancante o troppo ampio; tabella sbagliata (es. `AzureDiagnostics` vs tabella specifica); dati in archive tier non disponibili per query diretta.

**Soluzione:** Ottimizzare la query con filtri temporali e verificare la tabella corretta.

```kql
// Verificare quali tabelle hanno dati recenti
search * | summarize count() by $table | order by count_ desc | take 20

// Controllare ultima riga inserita in una tabella
AppServiceHTTPLogs | summarize max(TimeGenerated)

// Query ottimizzata: metti sempre TimeGenerated PRIMA degli altri filtri
AppServiceHTTPLogs
| where TimeGenerated > ago(1h)   // filtro temporale PRIMA
| where ScStatus >= 500           // poi altri filtri
| take 50

// Controllare se una tabella è in archive (non queryabile direttamente)
// Nel portale: Log Analytics Workspace > Tables > verifica "Plan" (Analytics vs Basic vs Archive)
```

```bash
# Listare tabelle con il loro piano (Analytics/Basic/Archive)
az monitor log-analytics workspace table list \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --query "[].{name: name, plan: plan, retentionDays: retentionInDays}" \
  --output table

# Ripristinare dati da archive per query (restore job, costo aggiuntivo)
az monitor log-analytics workspace table restore create \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --name AuditLogs_RST \
  --restore-source-table AuditLogs \
  --start-restore-time "2025-01-01T00:00:00Z" \
  --end-restore-time "2025-01-31T23:59:59Z"
```

Alternativa al restore: una **search job** esegue una ricerca asincrona sui dati archiviati e ne scrive i risultati in una tabella `_SRCH` interrogabile.

## Relazioni

??? info "Defender for Cloud & Sentinel"
    Sentinel è un SIEM costruito *sopra* un Log Analytics Workspace: usa le stesse tabelle e KQL, e il costo di ingestione si somma. Per questo la scelta di workspace (uno centrale vs uno per ambiente) è anche una decisione di sicurezza.

    **Approfondimento completo →** [Defender & Sentinel](../security/defender-sentinel.md)

??? info "AKS e Container Insights"
    Container Insights è l'integrazione di questo workspace con AKS (log container, inventario pod); le metriche applicative si affiancano con Managed Prometheus.

    **Approfondimento completo →** [AKS & Containers](../compute/aks-containers.md)

??? info "Application Insights"
    Application Insights (APM, tracing distribuito) in modalità workspace-based scrive nelle stesse tabelle (`AppRequests`, `AppExceptions`, …) usate nelle query sopra.

    **Approfondimento completo →** [Application Insights](application-insights.md)

## Riferimenti

- [Documentazione Azure Monitor](https://learn.microsoft.com/azure/azure-monitor/)
- [KQL Quick Reference](https://learn.microsoft.com/azure/data-explorer/kql-quick-reference)
- [Log Analytics Workspace](https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-workspace-overview)
- [Azure Monitor Agent (AMA)](https://learn.microsoft.com/azure/azure-monitor/agents/azure-monitor-agent-overview)
- [Data Collection Rules](https://learn.microsoft.com/azure/azure-monitor/essentials/data-collection-rule-overview)
- [Container Insights](https://learn.microsoft.com/azure/azure-monitor/containers/container-insights-overview)
- [Prezzi Azure Monitor](https://azure.microsoft.com/pricing/details/monitor/)
