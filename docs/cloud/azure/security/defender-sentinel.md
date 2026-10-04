---
title: "Defender for Cloud & Microsoft Sentinel"
slug: defender-sentinel
category: cloud
tags: [azure, defender-for-cloud, microsoft-sentinel, cspm, cwpp, siem, soar, security-center]
search_keywords: [Microsoft Defender for Cloud CSPM CWPP, Secure Score postura sicurezza, Defender for Servers EDR, Just-In-Time JIT VM Access, Microsoft Sentinel SIEM cloud-native, KQL analytics rules, SOAR playbook Logic Apps, MITRE ATT&CK framework, Fusion detection ML, UEBA user behavior analytics, Azure Security Benchmark MCSB]
parent: cloud/azure/security/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/monitoring/monitor-log-analytics, cloud/azure/compute/aks-containers]
official_docs: https://learn.microsoft.com/azure/defender-for-cloud/
status: needs-review
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
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
| **Defender for Servers P1** | Defender for Endpoint (EDR) integrato, vulnerability assessment di base (MDVM), Azure Arc | ~$5/server/mese |
| **Defender for Servers P2** | Tutto P1 + JIT VM Access, file integrity monitoring, agentless scanning, log retention 500 MB/giorno | ~$15/server/mese |
| **Defender for SQL** | SQL threat protection (injection, anomaly detection) | ~$15/server/mese |
| **Defender for Storage** | Malware scanning (a consumo per GB), sensitive data threat detection | ~$10/storage account/mese |
| **Defender for Containers** | AKS runtime protection, image scanning, Kubernetes hardening | ~$7/vCore/mese |
| **Defender for App Service** | HTTP endpoint protection, anomaly detection | ~$15/istanza/mese |
| **Defender for Key Vault** | Anomaly detection accessi Key Vault | ~$0.02/10K operazioni |

<!-- REVIEW: verificare prezzi (pricing page Defender for Cloud) e se Defender for App Service/Key Vault/Resource Manager sono ancora piani separati -->
!!! note "Prezzi indicativi"
    I prezzi sono orientativi (USD, list price) e cambiano: usare la [pricing page ufficiale](https://azure.microsoft.com/pricing/details/defender-for-cloud/). Defender CSPM è fatturato per risorsa fatturabile/ora (~$0.01 ≈ $7/mese).

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
#   --name = assessment key (GUID, visibile in `assessment list`)
az security assessment show \
  --name "<ASSESSMENT_KEY_GUID>" \
  --output json

# Listare sub-assessment (es. singole vulnerabilità) di una risorsa
az security sub-assessment list \
  --assessed-resource-id /subscriptions/SUB_ID/resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/my-vm \
  --assessment-name "<ASSESSMENT_KEY_GUID>" \
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

# Abilitare Defender for Storage (malware scanning e sensitive data discovery
# sono estensioni del piano, da configurare a parte via portal/ARM)
az security pricing create \
  --name StorageAccounts \
  --tier Standard \
  --subplan DefenderForStorageV2

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

Non esiste un comando `az security` dedicato per i connettori AWS/GCP: si creano da portal (*Environment settings → Add environment*), con Terraform/ARM o via REST sulla risorsa `Microsoft.Security/securityConnectors`. Il connettore usa un ruolo cross-account (AWS, via OIDC/CloudFormation) o un service account (GCP), senza agent.

```bash
# Listare i connettori multi-cloud esistenti
az rest --method GET \
  --url "https://management.azure.com/subscriptions/SUB_ID/providers/Microsoft.Security/securityConnectors?api-version=2023-10-01-preview"
```

### Microsoft Cloud Security Benchmark (MCSB)

MCSB (ex Azure Security Benchmark) definisce best practice di sicurezza per Azure organizzate in domini: Network Security, Identity Management, Privileged Access, Data Protection, Asset Management, Logging and Threat Detection, Incident Response, Posture and Vulnerability Management, Endpoint Security, Backup and Recovery, DevOps Security, Governance and Strategy.

<!-- REVIEW: verificare se MCSB v2 (con dominio AI Security) è GA e se va citato -->

```bash
# Verificare compliance rispetto a MCSB
az security regulatory-compliance-standards list \
  --output table

# Controlli dello standard MCSB
az security regulatory-compliance-controls list \
  --standard-name "Microsoft-cloud-security-benchmark" \
  --output table

# Assessment di un controllo (es. NS-1 Network Security)
az security regulatory-compliance-assessments list \
  --standard-name "Microsoft-cloud-security-benchmark" \
  --control-name "NS-1" \
  --output table
```

## Microsoft Sentinel

!!! warning "Sentinel si sposta nel portale Microsoft Defender"
    Microsoft sta unificando Sentinel con Defender XDR nel **portale Defender** (security.microsoft.com): l'esperienza SIEM nel portale Azure è in dismissione. <!-- REVIEW: verificare data di ritiro del portale Azure per Sentinel (annunciata marzo 2027, prima luglio 2026) --> Nel portale Defender incidenti e alert SIEM+XDR sono correlati in un'unica coda; i nuovi workspace vanno onboardati lì. Esiste inoltre il **Sentinel data lake** per retention a lungo termine a basso costo. <!-- REVIEW: verificare stato GA del data lake -->

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

# Estensione CLI (preview) per i comandi `az sentinel`
az extension add --name sentinel

# Abilitare Sentinel sul workspace = creare l'onboarding state "default"
az sentinel onboarding-state create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --name default
```

Alternative: portal, Bicep/Terraform (`azurerm_sentinel_log_analytics_workspace_onboarding`).

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

<!-- REVIEW: verificare sintassi esatta di `az sentinel alert-rule create` (estensione preview: usa parametri `--scheduled`, non `--kind`); in produzione preferire Bicep/ARM/Terraform o Sentinel Repositories (CI/CD) -->
!!! note "Sintassi CLI indicativa"
    L'estensione `az sentinel` è in preview e la sintassi dei comandi `alert-rule`/`automation-rule` cambia tra versioni: gli esempi seguenti mostrano i parametri logici (frequenza, finestra, soglia, tattiche). Per detection-as-code usare ARM/Bicep/Terraform o **Sentinel Repositories** (sync da GitHub/Azure DevOps).

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

UEBA si abilita da portal (*Settings → Entity behavior configuration*: collegare Entra ID come sorgente e scegliere le tabelle di log) oppure via ARM/REST sulla risorsa `Microsoft.SecurityInsights/settings` (kind `Ueba`). Non esiste un comando `az sentinel ueba`. Popola tabelle come `BehaviorAnalytics` e `UserPeerAnalytics`:

```kql
// Anomalie comportamentali ad alta priorità (ultimi 7 giorni)
BehaviorAnalytics
| where TimeGenerated > ago(7d)
| where InvestigationPriority > 5
| project TimeGenerated, UserPrincipalName, ActivityType, ActionType, InvestigationPriority
| order by InvestigationPriority desc
```

### KQL: Hunting Queries

```kql
// Hunting: identificare esfiltrazioni dati potenziali
// Utenti che hanno scaricato volumi insoliti da SharePoint
OfficeActivity
| where TimeGenerated > ago(7d)
| where RecordType == "SharePointFileOperation"
| where Operation == "FileDownloaded"
| summarize DownloadCount = count(), DistinctFiles = dcount(SourceFileName) by UserId, ClientIP, bin(TimeGenerated, 1d)
| where DownloadCount > 100
| order by DownloadCount desc

// Hunting: persistence via Scheduled Task
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID == 4698  // A scheduled task was created
| parse EventData with * "<TaskName>" TaskName "</TaskName>" *
| project TimeGenerated, Computer, AccountName, TaskName
| order by TimeGenerated desc

// Hunting: possibile lateral movement (stesso account, network logon su molti host)
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID == 4624  // Logon riuscito
| where LogonType == 3  // Network logon
| where AccountName != "SYSTEM" and AccountName != "ANONYMOUS LOGON"
| summarize Targets = make_set(Computer), TargetCount = dcount(Computer) by AccountName
| where TargetCount > 5  // stesso account su molte macchine
| order by TargetCount desc
```

### Workbooks

I Workbooks Sentinel forniscono dashboard interattivi per visualizzare dati di sicurezza.

I template si installano dal **Content hub** (*Sentinel → Content management*) e poi si salvano come workbook. Template built-in comuni: Azure Activity, Microsoft Entra ID Sign-in logs, Identity & Access, Zero Trust (TIC 3.0), copertura MITRE ATT&CK.

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

- Abilita **Defender for Servers P2** sulle VM di produzione (EDR è già in P1; P2 aggiunge JIT, FIM, agentless scanning)
- Attiva **JIT Access** (richiede P2) su tutte le VM con porte di amministrazione (22, 3389, 5985/5986) e preferisci `allowedSourceAddressPrefix` specifico invece di `*`
- Concedi al service principal Sentinel il ruolo *Microsoft Sentinel Automation Contributor* sul resource group dei Playbook, altrimenti le Automation Rules non possono lanciarli
- Per Sentinel, inizia con connettori Microsoft nativi (Entra ID, M365, Azure Activity) prima di aggiungere terze parti
- Usa **Fusion Detection** (ML-based correlation) — abilitato di default, non disabilitare
- Configura **Automation Rules** per triage automatico degli Incident di bassa severity
- Monitora il **Secure Score** settimanalmente: ogni punto percentuale rappresenta riduzione di rischio misurabile
- Usa **Workbooks** per reportistica mensile agli stakeholder executive

## Troubleshooting

### Scenario 1 — Defender for Cloud non mostra raccomandazioni dopo abilitazione

**Sintomo:** Dopo aver abilitato un Defender Plan, il Secure Score non cambia e le raccomandazioni non compaiono per ore o giorni.

**Causa:** Il piano non è realmente attivo sulla subscription (`az security pricing list`), le policy dell'iniziativa MCSB non sono ancora propagate, oppure sulle VM manca l'estensione/agent richiesto dalla feature (Defender for Endpoint, o Azure Monitor Agent per i log). Il Log Analytics agent (MMA) è ritirato da agosto 2024: non va più usato. Con Defender CSPM/Servers P2 lo **agentless scanning** copre le VM senza agent, ma con latenza di ore.

**Soluzione:** Verificare piani e agent, poi forzare la valutazione delle policy.

```bash
# Verificare che il piano sia attivo
az security pricing list --output table

# Verificare che AMA sia installato sulle VM
az vm extension list \
  --resource-group $RG \
  --vm-name $VM \
  --output table

# Installare Azure Monitor Agent se assente
az vm extension set \
  --resource-group $RG \
  --vm-name $VM \
  --name AzureMonitorWindowsAgent \
  --publisher Microsoft.Azure.Monitor \
  --version 1.0

# Forzare ri-valutazione delle raccomandazioni
az policy state trigger-scan \
  --resource-group $RG

# Controllare lo stato di conformità dopo ~15 minuti
az security assessment list \
  --output table
```

---

### Scenario 2 — Sentinel riceve dati ma non genera Incident

**Sintomo:** I log arrivano correttamente nel Log Analytics Workspace (verificabile con query KQL), ma nessuna Analytics Rule produce Incident.

**Causa:** Le Analytics Rules sono disabilitate, il threshold è troppo alto, la finestra (`query-period`) non copre la latenza di ingestion (eventi arrivano dopo l'esecuzione della regola), oppure la query KQL non restituisce risultati (filtri su colonne/valori sbagliati). Controllare anche *Suppression* e il tab *Health* della regola.

**Soluzione:** Validare la query e abilitare le regole.

```kql
// Verificare che i dati arrivino nel workspace
SigninLogs
| where TimeGenerated > ago(1h)
| summarize Count = count() by bin(TimeGenerated, 5m)
| order by TimeGenerated desc

// Testare manualmente la query di una Analytics Rule
// (eseguire nel Log Analytics workspace di Sentinel)
Syslog
| where TimeGenerated > ago(5m)
| where Facility == "auth" and SeverityLevel == "err"
| where SyslogMessage contains "Failed password"
| summarize FailedAttempts = count() by extract(@"from\s+(\d+\.\d+\.\d+\.\d+)", 1, SyslogMessage)
| where FailedAttempts >= 10
```

```bash
# Listare Analytics Rules e verificare quelle disabilitate
az sentinel alert-rule list \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --output table \
  --query "[?properties.enabled==\`false\`].{Name:name, Severity:properties.severity}"

# Abilitare una regola specifica
az sentinel alert-rule update \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --alert-rule-id "brute-force-ssh-login" \
  --enabled true
```

---

### Scenario 3 — JIT Access non funziona: la richiesta viene rifiutata

**Sintomo:** Quando si tenta di richiedere accesso JIT a una VM, l'operazione fallisce con errore `The resource is not configured for JIT access` o `Access denied`.

**Causa 1:** La VM non ha una JIT policy associata. **Causa 2:** Il ruolo dell'utente richiedente non include `Microsoft.Security/locations/jitNetworkAccessPolicies/initiate/action`. **Causa 3:** L'NSG della VM ha regole permanenti che entrano in conflitto.

**Soluzione:**

```bash
# Verificare se la VM ha una policy JIT associata
az security jit-policy list \
  --resource-group $RG \
  --output table

# Verificare che l'utente abbia i permessi necessari
az role assignment list \
  --assignee user@example.com \
  --scope /subscriptions/$SUBSCRIPTION_ID \
  --output table

# Assegnare il ruolo Security Reader + permesso JIT (custom role o Security Admin)
az role assignment create \
  --assignee user@example.com \
  --role "Security Admin" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG

# Verificare le regole NSG in conflitto
az network nsg rule list \
  --resource-group $RG \
  --nsg-name $NSG_NAME \
  --output table
```

---

### Scenario 4 — Falsi positivi eccessivi in Sentinel causano alert fatigue

**Sintomo:** Il SOC riceve centinaia di Incident al giorno, la maggior parte falsi positivi. Gli analisti ignorano gli alert.

**Causa:** Analytics Rules con threshold troppo bassi, mancanza di whitelist per IP/utenti interni, Automation Rules non configurate per il triage automatico.

**Soluzione:** Aggiungere whitelist nelle query KQL e configurare Automation Rules per la chiusura automatica dei falsi positivi noti.

```kql
// Modificare la query per escludere IP interni e service account
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType != "0"
// Escludere service account e IP trusted
| where UserPrincipalName !endswith "@serviceaccount.internal"
| where IPAddress !in ("10.0.0.1", "192.168.1.100", "10.1.0.50")
| summarize FailedCount = count() by UserPrincipalName, IPAddress, bin(TimeGenerated, 5m)
| where FailedCount > 15  // alzare il threshold
| order by FailedCount desc
```

```bash
# Creare Automation Rule per chiudere automaticamente Incident di bassa severity
# con determinate entità già note come false positive
az sentinel automation-rule create \
  --resource-group rg-security-prod \
  --workspace-name law-sentinel-prod \
  --automation-rule-id "close-known-fp" \
  --display-name "Auto-Close Known False Positives" \
  --order 100 \
  --enabled true \
  --conditions '[
    {
      "conditionType": "Property",
      "conditionProperties": {
        "propertyName": "IncidentSeverity",
        "operator": "Equals",
        "propertyValues": ["Informational", "Low"]
      }
    }
  ]' \
  --actions '[
    {
      "order": 1,
      "actionType": "ModifyProperties",
      "actionConfiguration": {
        "status": "Closed",
        "classification": "BenignPositive",
        "classificationComment": "Auto-closed: known benign activity"
      }
    }
  ]'
```

## Riferimenti

- [Documentazione Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/)
- [Microsoft Sentinel Documentation](https://learn.microsoft.com/azure/sentinel/)
- [MCSB (Microsoft Cloud Security Benchmark)](https://learn.microsoft.com/security/benchmark/azure/)
- [KQL per Sentinel](https://learn.microsoft.com/azure/sentinel/kusto-overview)
- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [Sentinel Playbooks Repository (GitHub)](https://github.com/Azure/Azure-Sentinel/tree/master/Playbooks)
- [Sentinel Analytics Rules Repository](https://github.com/Azure/Azure-Sentinel/tree/master/Detections)
