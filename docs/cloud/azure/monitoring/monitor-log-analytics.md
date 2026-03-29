---
title: "Azure Monitor & Log Analytics"
slug: monitor-log-analytics
category: cloud
tags: [azure, azure-monitor, log-analytics, metrics, alerts, workbooks, diagnostic-settings, kql]
search_keywords: [Azure Monitor metrics logs traces, Log Analytics Workspace KQL Kusto, Diagnostic Settings resource logs, Azure Monitor Agent AMA OMS MMA, metric alert log alert activity log alert, Action Group email SMS webhook, Workbooks dashboard, Container Insights AKS pods, data retention archive, Azure Monitor for VMs]
parent: cloud/azure/monitoring/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/compute/aks-containers, cloud/azure/security/defender-sentinel]
official_docs: https://learn.microsoft.com/azure/azure-monitor/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
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

I Diagnostic Settings abilitano l'invio di logs e metriche delle risorse Azure a Log Analytics, Storage Account e/o Event Hubs.

```bash
# Diagnostic Settings per una VM (Azure Monitor Agent — vedi sotto per AMA)
# Per risorse come App Service, SQL, Key Vault:
az monitor diagnostic-settings create \
  --resource $(az webapp show --resource-group rg-webapp-prod --name myapp-prod --query id -o tsv) \
  --name diag-appservice-prod \
  --workspace $LAW_ID \
  --logs '[
    {"category": "AppServiceHTTPLogs", "enabled": true, "retentionPolicy": {"enabled": false}},
    {"category": "AppServiceAppLogs", "enabled": true, "retentionPolicy": {"enabled": false}},
    {"category": "AppServiceAuditLogs", "enabled": true, "retentionPolicy": {"enabled": false}},
    {"category": "AppServiceIPSecAuditLogs", "enabled": true, "retentionPolicy": {"enabled": false}},
    {"category": "AppServicePlatformLogs", "enabled": true, "retentionPolicy": {"enabled": false}}
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

AMA è l'agente unificato per raccogliere log e metriche dalle VM, sostituendo i deprecati MMA (Microsoft Monitoring Agent) e OMS Agent.

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
| summarize ErrorCount = count() by AppRoleName, ExceptionType, outerMessage
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
| summarize Count = count() by ResultCode = tostring(toint(Success) * 200 + toint(!Success) * 500)
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

# Alert su più VM (dimension)
az monitor metrics alert create \
  --resource-group $RG \
  --name alert-cpu-vmss \
  --scopes $(az vmss show --resource-group $RG --name vmss-web-frontend --query id -o tsv) \
  --condition "avg Percentage CPU > 90" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 1 \
  --target-resource-type Microsoft.Compute/virtualMachineScaleSets
```

### Log Alert (KQL-based)

```bash
# Alert quando ci sono errori 500 nella webapp
az monitor scheduled-query create \
  --resource-group rg-webapp-prod \
  --name alert-http500-myapp \
  --scopes $(az webapp show --resource-group rg-webapp-prod --name myapp-prod --query id -o tsv) \
  --condition-query "AppServiceHTTPLogs | where ScStatus >= 500 | summarize Count = count()" \
  --condition-threshold 5 \
  --condition-operator GreaterThan \
  --evaluation-frequency 5m \
  --window-duration 5m \
  --severity 2 \
  --description "Più di 5 errori HTTP 500 in 5 minuti" \
  --action $(az monitor action-group show --resource-group $RG --name ag-ops-team --query id -o tsv)
```

### Activity Log Alert

```bash
# Alert quando viene eliminato un resource group
az monitor activity-log alert create \
  --resource-group $RG \
  --name alert-rg-deletion \
  --scopes /subscriptions/SUB_ID \
  --condition category=Administrative and operationName=Microsoft.Resources/subscriptions/resourceGroups/delete and status=Succeeded \
  --action $(az monitor action-group show --resource-group $RG --name ag-ops-team --query id -o tsv)
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
  --action sms sms-oncall +39555123456 \
  --action webhook webhook-slack "https://hooks.slack.com/services/..." \
  --action logic-app logic-app-itsm /subscriptions/SUB_ID/resourceGroups/rg-security/providers/Microsoft.Logic/workflows/create-ticket true

# Aggiornare Action Group aggiungendo Azure Function
az monitor action-group update \
  --resource-group $RG \
  --name ag-ops-team \
  --add-action azureFunctionReceiver \
    function-auto-remediate \
    /subscriptions/SUB_ID/resourceGroups/rg-functions/providers/Microsoft.Web/sites/func-remediation \
    auto_scale_out \
    "https://func-remediation.azurewebsites.net/api/auto_scale_out?code=..."
```

## Workbooks

I Workbooks Azure Monitor sono dashboard interattivi parametrizzati che combinano query KQL con visualizzazioni.

```bash
# Listare workbook templates predefiniti (gallery)
az monitor workbook template list \
  --resource-group $RG \
  --output table

# Creare workbook personalizzato (richiede JSON di definizione)
az monitor workbook create \
  --resource-group $RG \
  --name "workbook-webapp-dashboard" \
  --display-name "Web App Performance Dashboard" \
  --kind shared \
  --serialized-data @workbook-definition.json \
  --source-id $LAW_ID
```

Workbook predefiniti utili:
- **Performance** (VM): CPU, memoria, disco, rete per flotta VM
- **Failures** (Application Insights): eccezioni, request failure, dependency failure
- **Traffic** (App Service): throughput, latency, errori per endpoint
- **Azure AD Sign-ins**: analisi pattern di accesso
- **AKS**: node health, pod metrics, cluster overview

## Azure Monitor for VMs (VM Insights)

VM Insights abilita monitoring avanzato per VM: performance chart, dependency map, health model.

```bash
# Abilitare VM Insights (richiede AMA + Dependency Agent)
az vm extension set \
  --resource-group $RG \
  --vm-name my-vm \
  --name DependencyAgentLinux \
  --publisher Microsoft.Azure.Monitoring.DependencyAgent \
  --enable-auto-upgrade true

# Query per dependency map (VM Insights)
# VMConnection table mostra connessioni TCP tra processi
```

```kql
// VM Connections: processi che accettano connessioni
VMConnection
| where TimeGenerated > ago(1h)
| where Direction == "inbound"
| summarize ConnectionCount = count() by Computer, ProcessName, DestinationPort
| order by ConnectionCount desc
```

## Container Insights (AKS Monitoring)

```bash
# Abilitare Container Insights su AKS
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
// Pod CPU usage per namespace
KubePodInventory
| where TimeGenerated > ago(1h)
| join kind=leftouter (
    Perf
    | where ObjectName == "K8SContainer" and CounterName == "cpuUsageNanoCores"
    | summarize AvgCPU = avg(CounterValue) by InstanceName
) on $left.ContainerID == $right.InstanceName
| summarize AvgCPU = avg(AvgCPU) by Namespace, PodName
| order by AvgCPU desc

// Pod in CrashLoopBackOff
KubePodInventory
| where TimeGenerated > ago(1h)
| where ContainerStatus == "Waiting" and ContainerStatusReason == "CrashLoopBackOff"
| project TimeGenerated, Namespace, PodName, ContainerName, ContainerStatusReason

// Log di container specifico
ContainerLog
| where TimeGenerated > ago(1h)
| where Namespace == "production"
| where PodName contains "myapp"
| project TimeGenerated, PodName, ContainerName, LogMessage
| order by TimeGenerated desc
```

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

# Stimare costo ingestione dati
# Log Analytics: ~$2.30/GB ingested (PerGB2018 tier, West Europe)
# Retention: prime 31 giorni gratuiti, poi ~$0.10/GB/mese
# Archive: ~$0.02/GB/mese

# Configurare data cap (protezione da spike ingestione dati)
az monitor log-analytics workspace update \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --daily-quota-gb 10
```

## Best Practices

- Usa **Data Collection Rules (DCR)** invece degli agent legacy (MMA/OMS) — più flessibili e meno overhead
- Configura **Diagnostic Settings** su tutte le risorse Azure critiche (SQL, Key Vault, App Service)
- Separa workspace per ambienti di produzione e non-produzione per isolamento RBAC e costi
- Imposta **daily quota** sul workspace per protezione da spike di ingestione
- Usa **Archive tier** per log di compliance long-term invece di mantenere tutto nello interactive tier
- Per alert, privilegia **Metric Alert** (valutazione ogni minuto) su **Log Alert** (minimum 5 minuti) quando possibile

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
az monitor action-group test \
  --resource-group $RG \
  --name ag-ops-team \
  --alert-type "Metric"

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
az monitor log-analytics workspace table restore \
  --resource-group $RG \
  --workspace-name $LAW_NAME \
  --name AuditLogs_RST \
  --restore-source-table AuditLogs \
  --start-restore-time "2025-01-01T00:00:00Z" \
  --end-restore-time "2025-01-31T23:59:59Z"
```

## Riferimenti

- [Documentazione Azure Monitor](https://learn.microsoft.com/azure/azure-monitor/)
- [KQL Quick Reference](https://learn.microsoft.com/azure/data-explorer/kql-quick-reference)
- [Log Analytics Workspace](https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-workspace-overview)
- [Azure Monitor Agent (AMA)](https://learn.microsoft.com/azure/azure-monitor/agents/azure-monitor-agent-overview)
- [Data Collection Rules](https://learn.microsoft.com/azure/azure-monitor/essentials/data-collection-rule-overview)
- [Container Insights](https://learn.microsoft.com/azure/azure-monitor/containers/container-insights-overview)
- [Prezzi Azure Monitor](https://azure.microsoft.com/pricing/details/monitor/)
