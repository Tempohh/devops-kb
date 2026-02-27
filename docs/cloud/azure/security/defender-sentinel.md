---
title: "Defender for Cloud & Microsoft Sentinel"
slug: defender-sentinel
category: cloud
tags: [azure, defender-for-cloud, microsoft-sentinel, cspm, cwpp, siem, soar, security-center]
search_keywords: [Microsoft Defender for Cloud CSPM CWPP, Secure Score postura sicurezza, Defender for Servers EDR, Just-In-Time JIT VM Access, Microsoft Sentinel SIEM cloud-native, KQL analytics rules, SOAR playbook Logic Apps, MITRE ATT&CK framework, Fusion detection ML, UEBA user behavior analytics, Azure Security Benchmark MCSB]
parent: cloud/azure/security/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/monitoring/monitor-log-analytics, cloud/azure/compute/aks-containers]
official_docs: https://learn.microsoft.com/azure/defender-for-cloud/
status: complete
difficulty: advanced
last_updated: 2026-02-26
---

# Defender for Cloud & Microsoft Sentinel

## Panoramica

**Microsoft Defender for Cloud** è la piattaforma unificata per la sicurezza cloud di Azure, coprendo due domini:
- **CSPM** (Cloud Security Posture Management): valuta la postura di sicurezza, identifica misconfiguration, fornisce raccomandazioni prioritizzate
- **CWPP** (Cloud Workload Protection Platform): protezione runtime di VM, container, database, storage e altri workload

**Microsoft Sentinel** è il SIEM (Security Information and Event Management) + SOAR (Security Orchestration and Response) cloud-native di Microsoft, basato su Azure Monitor Log Analytics. Raccoglie eventi da tutta l'infrastruttura, correla anomalie e automatizza la risposta.

## Microsoft Defender for Cloud

### Free Tier vs Paid Plans

| Tier | Funzionalità | Costo |
|---|---|---|
| **Foundational CSPM (Free)** | Secure Score, raccomandazioni base, Azure Policy | Gratuito |
| **Defender CSPM (Paid)** | Attack path analysis, cloud security explorer, agentless scanning | ~$0.01/risorsa/ora |
| **Defender for Servers P1** | Defender for Endpoint (EDR), JIT Access | ~$0.005/VM/ora |
| **Defender for Servers P2** | Tutto P1 + vulnerability assessment, file integrity monitoring | ~$0.02/VM/ora |
| **Defender for SQL** | SQL threat protection (injection, anomaly detection) | ~$0.018/vCore/ora |
| **Defender for Storage** | Malware scanning, sensitive data threat detection | ~$10/storage account/mese |
| **Defender for Containers** | AKS runtime protection, image scanning, Kubernetes hardening | ~$7/vCore/ora nodo |
| **Defender for App Service** | HTTP endpoint protection, anomaly detection | ~$0.018/istanza/ora |
| **Defender for Key Vault** | Anomaly detection accessi Key Vault | ~$0.02/10K operazioni |

### Secure Score

Il Secure Score è un punteggio (0-100%) che misura la postura di sicurezza della subscription. Ogni raccomandazione ha un peso; implementarla aumenta lo score.

```bash
# Listare lo score corrente
az security secure-score list \
  --output table

# Listare tutte le raccomandazioni di sicurezza
az security assessment list \
  --output table

# Dettaglio di una raccomandazione specifica
az security assessment show \
  --resource-group $RG \
  --resource-name myvm \
  --name "vulnerability-assessment-solution-should-be-installed-on-your-virtual-machines" \
  --output json

# Listare risorse non conformi per una policy
az security sub-assessment list \
  --resource-group $RG \
  --assessed-resource-id /subscriptions/SUB_ID \
  --output table
```

### Abilitare Defender Plans

```bash
# Abilitare Defender for Servers P2 per tutta la subscription
az security pricing create \
  --name VirtualMachines \
  --tier Standard \
  --subplan P2

# Abilitare Defender for SQL
az security pricing create \
  --name SqlServers \
  --tier Standard

az security pricing create \
  --name SqlServerVirtualMachines \
  --tier Standard

# Abilitare Defender for Containers
az security pricing create \
  --name Containers \
  --tier Standard

# Abilitare Defender for Storage con malware scanning
az security pricing create \
  --name StorageAccounts \
  --tier Standard

# Verificare piani attivi
az security pricing list \
  --output table
```

### Just-In-Time (JIT) VM Access

JIT Access elimina la necessità di tenere le porte SSH/RDP sempre aperte. Le porte vengono aperte nel NSG solo per l'IP richiedente e per la durata specificata.

```bash
# Creare policy JIT per una VM
az security jit-policy create \
  --resource-group $RG \
  --location $LOCATION \
  --name "default" \
  --virtual-machines "[
    {
      \"id\": \"/subscriptions/SUB_ID/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/my-vm\",
      \"ports\": [
        {
          \"number\": 22,
          \"protocol\": \"TCP\",
          \"allowedSourceAddressPrefix\": \"*\",
          \"maxRequestAccessDuration\": \"PT3H\"
        },
        {
          \"number\": 3389,
          \"protocol\": \"TCP\",
          \"allowedSourceAddressPrefix\": \"*\",
          \"maxRequestAccessDuration\": \"PT3H\"
        }
      ]
    }
  ]"

# Richiedere accesso JIT (apre SSH per 2 ore da IP specifico)
MY_IP=$(curl -s https://ipinfo.io/ip)
az security jit-policy initiate \
  --resource-group $RG \
  --name "default" \
  --virtual-machines "[
    {
      \"id\": \"/subscriptions/SUB_ID/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/my-vm\",
      \"ports\": [
        {
          \"number\": 22,
          \"duration\": \"PT2H\",
          \"allowedSourceAddressPrefix\": \"$MY_IP\"
        }
      ]
    }
  ]"
```

### Multi-Cloud Security

Defender for Cloud può proteggere anche workload AWS e GCP tramite connettori.

```bash
# Connettere account AWS per CSPM multi-cloud
az security aws-connector create \
  --resource-group $RG \
  --name "aws-prod-account" \
  --hierarchy-identifier "123456789012" \
  --offering cspm

# Connettere GCP per CSPM multi-cloud
az security gcp-project-connector create \
  --resource-group $RG \
  --name "gcp-prod-project" \
  --hierarchy-identifier "my-gcp-project" \
  --offering cspm
```

### Microsoft Cloud Security Benchmark (MCSB)

MCSB (ex Azure Security Benchmark) definisce best practice di sicurezza per Azure organizzate in domini: Network Security, Identity Management, Privileged Access, Data Protection, Asset Management, Logging and Threat Detection, Incident Response, Posture Management, Endpoint Security, Backup and Recovery, DevOps Security.

```bash
# Verificare compliance rispetto a MCSB
az security regulatory-compliance-standards list \
  --output table

# Dettaglio conformità MCSB
az security regulatory-compliance-assessments list \
  --standard-name "Microsoft cloud security benchmark" \
  --output table
```

## Microsoft Sentinel

### Architettura

```
Data Sources → Data Connectors → Log Analytics Workspace → Sentinel
                                                              ├── Analytics Rules (KQL)
                                                              ├── Incidents
                                                              ├── Playbooks (Logic Apps)
                                                              ├── Workbooks (dashboard)
                                                              └── Hunting Queries
```

### Abilitare Sentinel

```bash
# Prerequisito: Log Analytics Workspace
az monitor log-analytics workspace create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --location westeurope \
  --retention-time 90

# Abilitare Sentinel sul workspace (tramite estensione)
az sentinel workspace enable \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod

# Oppure via REST API / portal (approccio più comune per onboarding iniziale)
az rest \
  --method PUT \
  --url "https://management.azure.com/subscriptions/SUB_ID/resourceGroups/rg-security-prod/providers/Microsoft.OperationsManagement/solutions/SecurityInsights(law-sentinel-prod)?api-version=2015-11-01-preview" \
  --body '{"location":"westeurope","properties":{"workspaceResourceId":"/subscriptions/SUB_ID/resourceGroups/rg-security-prod/providers/Microsoft.OperationalInsights/workspaces/law-sentinel-prod"},"plan":{"name":"SecurityInsights(law-sentinel-prod)","product":"OMSGallery/SecurityInsights","publisher":"Microsoft","promotionCode":""}}'
```

### Data Connectors

I data connector collegano Sentinel alle sorgenti dati.

```bash
# Connettere Azure Activity Logs
az sentinel data-connector create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --data-connector-id "AzureActivity" \
  --kind AzureActivity

# Connettore per Microsoft Entra ID (sign-in logs, audit logs)
az sentinel data-connector create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --data-connector-id "AzureActiveDirectory" \
  --kind AzureActiveDirectory

# Connettore per Microsoft 365 Defender
az sentinel data-connector create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --data-connector-id "MicrosoftThreatProtection" \
  --kind MicrosoftThreatProtection
```

Connettori comuni disponibili:
- Microsoft Entra ID (sign-in logs, audit logs, risky users)
- Microsoft 365 (Exchange, SharePoint, Teams)
- Microsoft 365 Defender (XDR unificato)
- Azure Activity (operazioni ARM)
- Azure Defender alerts
- AWS CloudTrail
- Google Cloud Platform
- Firewall di terze parti (Palo Alto, Fortinet, Check Point) via Syslog/CEF
- Security Events (Windows Event Log da VM con AMA)

### Analytics Rules — KQL Queries

Le Analytics Rules definiscono quando creare un Alert/Incident basandosi su query KQL schedulata.

```bash
# Creare Scheduled Analytics Rule
az sentinel alert-rule create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --alert-rule-id "brute-force-ssh-login" \
  --kind Scheduled \
  --display-name "Multiple Failed SSH Logins" \
  --description "Rileva 10+ tentativi di login SSH falliti dallo stesso IP in 5 minuti" \
  --severity Medium \
  --enabled true \
  --query-frequency PT5M \
  --query-period PT5M \
  --trigger-operator GreaterThan \
  --trigger-threshold 0 \
  --suppression-duration PT1H \
  --suppression-enabled false \
  --query "Syslog
| where TimeGenerated > ago(5m)
| where Facility == 'auth' and SeverityLevel == 'err'
| where SyslogMessage contains 'Failed password'
| extend IPAddress = extract(@'from\s+(\d+\.\d+\.\d+\.\d+)', 1, SyslogMessage)
| where isnotempty(IPAddress)
| summarize FailedAttempts = count() by IPAddress, bin(TimeGenerated, 5m)
| where FailedAttempts >= 10"
```

#### KQL Examples: Rilevamento Minacce

```kql
// 1. Login falliti multipli (brute force)
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType != "0"  // 0 = successo
| summarize FailedCount = count() by UserPrincipalName, IPAddress, bin(TimeGenerated, 5m)
| where FailedCount > 10
| order by FailedCount desc

// 2. Login riuscito dopo serie di fallimenti (credential stuffing riuscito)
let failed_logins = SigninLogs
    | where TimeGenerated > ago(1h)
    | where ResultType != "0"
    | summarize FailedBefore = count() by UserPrincipalName, IPAddress;
SigninLogs
| where TimeGenerated > ago(30m)
| where ResultType == "0"  // login riuscito
| join kind=inner failed_logins on UserPrincipalName, IPAddress
| where FailedBefore > 5
| project TimeGenerated, UserPrincipalName, IPAddress, FailedBefore

// 3. Eliminazione resource group anomala
AzureActivity
| where TimeGenerated > ago(24h)
| where OperationNameValue == "Microsoft.Resources/subscriptions/resourcegroups/delete"
| where ActivityStatusValue == "Succeeded"
| project TimeGenerated, Caller, ResourceGroup, SubscriptionId

// 4. Accesso a Key Vault da IP insolito
AzureDiagnostics
| where ResourceType == "VAULTS"
| where OperationName == "SecretGet"
| where ResultType == "Success"
| summarize AccessCount = count() by CallerIPAddress, ResourceId, bin(TimeGenerated, 1h)
| where AccessCount > 50
| join kind=leftouter (
    AzureDiagnostics
    | where ResourceType == "VAULTS"
    | where TimeGenerated > ago(30d)
    | summarize HistoricalCount = count() by CallerIPAddress
) on CallerIPAddress
| where HistoricalCount < 10  // IP raramente visto
| order by AccessCount desc

// 5. Privilege escalation: nuovo Global Admin
AuditLogs
| where TimeGenerated > ago(1h)
| where OperationName == "Add member to role"
| extend RoleName = tostring(TargetResources[0].displayName)
| where RoleName in ("Global Administrator", "Privileged Role Administrator", "Privileged Authentication Administrator")
| project TimeGenerated, InitiatedByUser = tostring(InitiatedBy.user.userPrincipalName), NewAdmin = tostring(TargetResources[1].displayName), RoleName
```

### Playbooks (SOAR — risposta automatica)

I Playbooks sono Logic Apps che si attivano su Incident o Alert per automatizzare la risposta.

```bash
# Creare Automation Rule che lancia un Playbook su Incident
az sentinel automation-rule create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --automation-rule-id "auto-block-and-notify" \
  --display-name "Auto Block User and Notify Teams" \
  --order 1 \
  --enabled true \
  --trigger-operator Equals \
  --trigger-threshold 0 \
  --conditions '[
    {
      "conditionType": "Property",
      "conditionProperties": {
        "propertyName": "IncidentSeverity",
        "operator": "Equals",
        "propertyValues": ["High", "Critical"]
      }
    }
  ]' \
  --actions '[
    {
      "order": 1,
      "actionType": "RunPlaybook",
      "actionConfiguration": {
        "tenantId": "TENANT_ID",
        "logicAppResourceId": "/subscriptions/SUB_ID/resourceGroups/rg-security-prod/providers/Microsoft.Logic/workflows/playbook-block-user"
      }
    }
  ]'
```

Playbook comuni:
- **Block Compromised User**: disabilita account Entra ID + revoca sessioni
- **Isolate VM**: disconnette NIC dalla VNet (applica NSG deny-all)
- **ITSM Ticket**: crea ticket ServiceNow/Jira automaticamente
- **Teams Notification**: invia alert al canale Teams SOC
- **IP Enrichment**: arricchisce l'Incident con info geolocation e reputazione IP
- **Auto-Close False Positives**: chiude Incident di bassa severity dopo verifica automatica

### Incidents e Investigation

Gli Incident in Sentinel aggregano più Alert correlati in un unico caso investigativo.

```bash
# Listare Incident aperti
az sentinel incident list \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --filter "properties/status eq 'New'" \
  --output table

# Dettaglio di un Incident
az sentinel incident show \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --incident-id "INCIDENT_ID"

# Aggiornare status Incident
az sentinel incident update \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --incident-id "INCIDENT_ID" \
  --status Active \
  --owner-email analyst@example.com
```

### UEBA (User and Entity Behavior Analytics)

UEBA analizza il comportamento normale di utenti ed entità per rilevare anomalie.

```bash
# Abilitare UEBA
az sentinel ueba create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --data-sources "AuditLogs" "AzureActivity" "SecurityEvent" "SigninLogs"
```

### KQL: Hunting Queries

```kql
// Hunting: identificare esfiltrazioni dati potenziali
// Utenti che hanno scaricato volumi insoliti da SharePoint
OfficeActivity
| where TimeGenerated > ago(7d)
| where RecordType == "SharePointFileOperation"
| where Operation == "FileDownloaded"
| summarize DownloadCount = count(), TotalBytes = sum(toint(SourceFileExtension)) by UserId, ClientIP, bin(TimeGenerated, 1d)
| where DownloadCount > 100
| order by DownloadCount desc

// Hunting: persistence via Scheduled Task
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID == 4698  // A scheduled task was created
| parse EventData with * "<TaskName>" TaskName "</TaskName>" *
| project TimeGenerated, Computer, AccountName, TaskName
| order by TimeGenerated desc

// Hunting: lateral movement via WMI
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID in (4648, 4624)  // Explicit credential use / logon
| where LogonType == 3  // Network logon
| where AccountName != "SYSTEM" and AccountName != "ANONYMOUS LOGON"
| summarize Targets = make_set(Computer), TargetCount = dcount(Computer) by AccountName
| where TargetCount > 5  // stesso account su molte macchine
| order by TargetCount desc
```

### Workbooks

I Workbooks Sentinel forniscono dashboard interattivi per visualizzare dati di sicurezza.

```bash
# Listare workbook templates disponibili
az sentinel source-control list \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod

# I workbook built-in includono:
# - Azure Activity
# - Azure AD Sign-in logs
# - Microsoft Defender for Cloud coverage
# - Identity & Access
# - Zero Trust (TIC 3.0)
# - MITRE ATT&CK coverage
```

### MITRE ATT&CK Integration

Sentinel mappa automaticamente le Analytics Rules alle tecniche MITRE ATT&CK, visualizzando la copertura della detection.

```bash
# Creare Analytics Rule con mapping MITRE ATT&CK
az sentinel alert-rule create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --alert-rule-id "credential-dumping-detection" \
  --kind Scheduled \
  --display-name "Credential Dumping via LSASS" \
  --severity High \
  --enabled true \
  --query-frequency PT1H \
  --query-period PT1H \
  --trigger-operator GreaterThan \
  --trigger-threshold 0 \
  --tactics "CredentialAccess" \
  --techniques "T1003" "T1003.001" \
  --query "SecurityEvent
| where EventID == 4663
| where ObjectName has 'lsass.exe'
| where AccessMask == '0x40' or AccessMask == '0x1410'
| project TimeGenerated, Computer, SubjectUserName, ProcessName, ObjectName"
```

## Best Practices

- Abilita **Defender for Servers P2** su tutte le VM di produzione per EDR e vulnerability assessment
- Attiva **JIT Access** su tutte le VM con porte di amministrazione (22, 3389, 5985/5986)
- Per Sentinel, inizia con connettori Microsoft nativi (Entra ID, M365, Azure Activity) prima di aggiungere terze parti
- Usa **Fusion Detection** (ML-based correlation) — abilitato di default, non disabilitare
- Configura **Automation Rules** per triage automatico degli Incident di bassa severity
- Monitora il **Secure Score** settimanalmente: ogni punto percentuale rappresenta riduzione di rischio misurabile
- Usa **Workbooks** per reportistica mensile agli stakeholder executive

## Riferimenti

- [Documentazione Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/)
- [Microsoft Sentinel Documentation](https://learn.microsoft.com/azure/sentinel/)
- [MCSB (Microsoft Cloud Security Benchmark)](https://learn.microsoft.com/security/benchmark/azure/)
- [KQL per Sentinel](https://learn.microsoft.com/azure/sentinel/kusto-overview)
- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [Sentinel Playbooks Repository (GitHub)](https://github.com/Azure/Azure-Sentinel/tree/master/Playbooks)
- [Sentinel Analytics Rules Repository](https://github.com/Azure/Azure-Sentinel/tree/master/Detections)
