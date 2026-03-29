---
title: "Azure Well-Architected Framework"
slug: well-architected-azure
category: cloud
tags: [azure, well-architected, waf, reliability, security, cost-optimization, performance, operational-excellence]
search_keywords: [Azure Well-Architected Framework, WAF Azure, 5 pilastri Azure, Reliability Azure, Security pillar, Cost Optimization Azure, Performance Efficiency, Operational Excellence, Azure Advisor, workload assessment, trade-offs]
parent: cloud/azure/fondamentali/_index
related: [cloud/azure/monitoring/_index, cloud/azure/security/_index]
official_docs: https://learn.microsoft.com/azure/well-architected/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Azure Well-Architected Framework

Il **Azure Well-Architected Framework (WAF)** è un insieme di principi guida per la progettazione di workload cloud affidabili, sicuri, efficienti e ottimizzati per i costi.

Composto da **5 pilastri** con trade-off espliciti tra di loro.

---

## I 5 Pilastri

```
                    ┌─────────────────────────────────┐
                    │  Workload ben progettato         │
                    └─────────────┬───────────────────┘
                                  │
        ┌─────────────────────────┼──────────────────────────┐
        │             │           │           │              │
   Reliability    Security   Cost        Operational  Performance
                             Optimization  Excellence   Efficiency
```

---

## 1. Reliability (Affidabilità)

**Obiettivo:** Il workload deve soddisfare gli SLA e riprendersi dai guasti.

**Principi di design:**
- Progettare per il guasto — assumere che i componenti falliranno
- Usare Availability Zones e Region Pairs per HA e DR
- Implementare retry con backoff esponenziale
- Circuit breaker pattern per fallimenti a cascata
- Definire RTO (Recovery Time Objective) e RPO (Recovery Point Objective)
- Testare i failover regolarmente (Chaos Engineering)

**Servizi chiave:**

| Obiettivo | Servizio |
|-----------|----------|
| HA multi-zone compute | VMSS con zone balancing, AKS multi-zone |
| HA database | Azure SQL Zone Redundant, Cosmos DB multi-region |
| Load balancing | Azure Load Balancer (zonal), Application Gateway (zone-redundant) |
| Failover DNS | Azure Traffic Manager, Azure Front Door |
| Backup | Azure Backup |
| DR | Azure Site Recovery |
| Monitoring HA | Azure Monitor, Application Insights |

**SLA compositi:**

```
SLA composito = SLA(A) × SLA(B) × SLA(C)
Esempio: VM (99.9%) × SQL (99.99%) × App Gateway (99.95%) = 99.84%

Con Availability Zones: 99.99%+ per servizi zone-redundant
```

---

## 2. Security (Sicurezza)

**Obiettivo:** Proteggere il workload da minacce, gestire accessi e proteggere i dati.

**Principi di design:**
- **Zero Trust:** "Never trust, always verify" — verificare ogni accesso
- **Privilegio minimo:** ogni identità ha solo i permessi necessari
- **Defense in depth:** più livelli di sicurezza (identità, rete, dati, applicazione)
- **Segmentazione:** isolare workload con VNet, NSG, subnet
- **Crittografia ovunque:** dati at rest e in transit
- **Shift-left security:** sicurezza nel processo di sviluppo

**Livelli di Defense in Depth:**

```
1. Sicurezza Fisica    ← Microsoft (datacenter)
2. Identità e accessi  ← Entra ID, RBAC, MFA, PIM
3. Perimetro rete      ← DDoS Protection, Azure Firewall
4. Rete interna        ← NSG, Private Endpoints, VNet peering
5. Compute             ← Defender for Servers, EDR, Just-In-Time VM access
6. Applicazione        ← WAF (Application Gateway/Front Door), secure coding
7. Dati                ← Key Vault, TDE, CMK, classificazione Purview
```

---

## 3. Cost Optimization (Ottimizzazione Costi)

**Obiettivo:** Ottimizzare i costi senza compromettere qualità e performance.

**Principi di design:**
- Scegliere il tier di servizio corretto per i requisiti (non over-provisioning)
- Usare Reserved Instances / Savings Plans per workload stabili (fino a 72% risparmio)
- Azure Spot VMs per workload interrompibili (fino a 90% risparmio)
- Scale in aggressivo — non mantenere risorse idle
- Monitorare spesa con Cost Management + Budgets + Alerts
- Tagging consistente per chargeback/showback

**Strumenti:**

```bash
# Azure Cost Management — analisi spesa
az consumption usage list \
    --billing-period-name 202601 \
    --query "[].{Service:instanceName, Cost:pretaxCost, Currency:currency}" \
    --output table

# Creare Budget alert
az consumption budget create \
    --resource-group myapp-rg \
    --budget-name monthly-budget \
    --amount 1000 \
    --time-grain Monthly \
    --start-date 2026-02-01 \
    --end-date 2026-12-31 \
    --category Cost \
    --notifications '[{
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 80,
        "contactEmails": ["team@company.com"],
        "thresholdType": "Actual"
    }]'

# Azure Advisor — raccomandazioni costo
az advisor recommendation list \
    --category Cost \
    --query "[].{Title:shortDescription.problem, Impact:impact, Savings:extendedProperties.annualSavingsAmount}" \
    --output table
```

---

## 4. Operational Excellence (Eccellenza Operativa)

**Obiettivo:** Operare il workload in modo efficiente con processi maturi.

**Principi di design:**
- Infrastructure as Code (Bicep, ARM, Terraform) — tutto versionato
- CI/CD automatizzato (Azure DevOps Pipelines, GitHub Actions)
- GitOps per Kubernetes (Flux, ArgoCD)
- Observability completa: metrics, logs, traces (Azure Monitor stack)
- Deployment sicuri: blue/green, canary, rolling
- Runbook automatizzati per operazioni comuni
- Tagging per gestione ciclo vita risorse

**Maturità operativa:**

| Livello | Caratteristiche |
|---------|----------------|
| 1 — Reactive | Interventi manuali, no monitoring |
| 2 — Repeatable | IaC, CI/CD base, alerting |
| 3 — Defined | SLO/SLA definiti, runbook, on-call |
| 4 — Managed | Chaos engineering, auto-remediation |
| 5 — Optimizing | ML-driven ops, continuous improvement |

---

## 5. Performance Efficiency (Efficienza delle Performance)

**Obiettivo:** Scalare per soddisfare la domanda in modo efficiente.

**Principi di design:**
- Scegliere il servizio giusto per il pattern di carico (VM vs serverless vs container)
- Scalabilità orizzontale preferita a verticale
- Caching a più livelli (CDN, Redis, in-memory)
- Database sharding e partitioning per scalabilità
- Async patterns: code, event streaming per decoupling
- Performance testing prima del go-live
- Profiling e load testing continuo

**Pattern di scaling:**

```bash
# VMSS autoscaling — regola per CPU
az monitor autoscale create \
    --resource-group myapp-rg \
    --resource myapp-vmss \
    --resource-type Microsoft.Compute/virtualMachineScaleSets \
    --name cpu-autoscale \
    --min-count 2 --max-count 10 --count 3

az monitor autoscale rule create \
    --resource-group myapp-rg \
    --autoscale-name cpu-autoscale \
    --condition "Percentage CPU > 70 avg 5m" \
    --scale out 2

az monitor autoscale rule create \
    --resource-group myapp-rg \
    --autoscale-name cpu-autoscale \
    --condition "Percentage CPU < 30 avg 10m" \
    --scale in 1
```

---

## Azure Well-Architected Review

Microsoft fornisce uno strumento di **assessment interattivo** per valutare un workload rispetto ai 5 pilastri:

- **URL:** [https://learn.microsoft.com/assessments/](https://learn.microsoft.com/assessments/)
- **Output:** punteggio per pilastro + raccomandazioni prioritizzate
- **Integrazione:** Azure Advisor legge risorse reali e fornisce raccomandazioni specifiche

```bash
# Azure Advisor — tutte le raccomandazioni
az advisor recommendation list --output table

# Advisor per categoria specifica
az advisor recommendation list \
    --category HighAvailability \
    --output table
```

---

## Trade-Off tra Pilastri

| Trade-Off | Esempio |
|-----------|---------|
| Reliability vs Cost | Zone-redundant = più costoso ma più affidabile |
| Performance vs Cost | Provisioned throughput vs serverless auto-scale |
| Security vs Performance | TLS inspection = overhead ma sicurezza |
| Reliability vs Performance | Multi-region = latenza write aggiuntiva |

---

## Troubleshooting

### Scenario 1 — SLA composito inferiore alle aspettative

**Sintomo:** Il calcolo dell'SLA composito del workload è significativamente più basso del target (es. 99.9% desiderato ma reale è 99.7%).

**Causa:** Il prodotto degli SLA dei singoli componenti abbassa l'SLA complessivo; un componente non zone-redundant rompe la catena.

**Soluzione:** Identificare i componenti con SLA basso o non zone-redundant e aggiornarli. Usare Azure Advisor per evidenziare i single point of failure.

```bash
# Verificare le raccomandazioni di alta disponibilità
az advisor recommendation list \
    --category HighAvailability \
    --query "[].{Titolo:shortDescription.problem, Impatto:impact, Risorsa:resourceMetadata.resourceId}" \
    --output table

# Verificare le zone di una VMSS
az vmss show \
    --resource-group myapp-rg \
    --name myapp-vmss \
    --query "zones"
```

---

### Scenario 2 — Costi anomali non attesi

**Sintomo:** La fattura mensile supera il budget previsto senza una causa apparente; gli alert di budget non sono scattati.

**Causa:** Risorse lasciate in esecuzione (VM stopped ma non deallocate, dischi orfani), mancanza di tag per il chargeback, budget alert configurati male.

**Soluzione:** Usare Cost Management per analizzare la spesa per risorsa; deallocare VM ferme; cercare dischi non collegati.

```bash
# Trovare VM ferme ma non deallocate (continuano a costare)
az vm list \
    --query "[?powerState=='VM stopped'].{Nome:name, RG:resourceGroup}" \
    --show-details \
    --output table

# Trovare dischi non collegati a nessuna VM
az disk list \
    --query "[?diskState=='Unattached'].{Nome:name, RG:resourceGroup, SizeGB:diskSizeGb}" \
    --output table

# Analisi spesa ultimi 7 giorni
az consumption usage list \
    --start-date $(date -d "-7 days" +%Y-%m-%d) \
    --end-date $(date +%Y-%m-%d) \
    --query "sort_by([].{Risorsa:instanceName, Costo:pretaxCost}, &Costo) | reverse(@)" \
    --output table
```

---

### Scenario 3 — Deployment fallisce dopo introduzione di policy di sicurezza

**Sintomo:** Le pipeline CI/CD iniziano a fallire con errori `RequestDisallowedByPolicy` dopo l'applicazione di nuove Azure Policy.

**Causa:** Le Azure Policy nel pilastro Security bloccano la creazione di risorse non conformi (es. VM senza crittografia, storage senza HTTPS, risorse in region non autorizzate).

**Soluzione:** Identificare la policy violata, correggere la definizione IaC, oppure richiedere un'esenzione temporanea se la policy è troppo restrittiva.

```bash
# Vedere le policy non conformi nella subscription
az policy state list \
    --filter "complianceState eq 'NonCompliant'" \
    --query "[].{Policy:policyDefinitionName, Risorsa:resourceId, Causa:complianceReasonCode}" \
    --output table

# Dettagli su un'assegnazione di policy specifica
az policy assignment show \
    --name <assignment-name> \
    --query "{Nome:displayName, Scope:scope, Parametri:parameters}"

# Verificare se un'operazione verrebbe bloccata (what-if policy)
az policy state summarize \
    --resource-group myapp-rg \
    --output table
```

---

### Scenario 4 — Autoscaling non interviene sotto carico

**Sintomo:** Il VMSS o AKS non scala durante i picchi di traffico; la CPU rimane alta per minuti senza aumentare le istanze.

**Causa:** Regole di autoscaling troppo conservative (cooldown troppo lungo, soglie troppo alte), metriche non configurate correttamente, limite `max-count` raggiunto.

**Soluzione:** Rivedere le regole di autoscale, verificare i log di scaling, abbassare il cooldown period, aumentare il limite massimo.

```bash
# Vedere la configurazione autoscale attuale
az monitor autoscale show \
    --resource-group myapp-rg \
    --name cpu-autoscale \
    --query "{Min:profiles[0].capacity.minimum, Max:profiles[0].capacity.maximum, Regole:profiles[0].rules}" \
    --output json

# Log degli eventi di scaling
az monitor activity-log list \
    --resource-group myapp-rg \
    --start-time $(date -d "-1 hour" --iso-8601) \
    --query "[?contains(operationName.value,'autoscale')].{Ora:eventTimestamp, Operazione:operationName.value, Status:status.value}" \
    --output table

# Aggiornare cooldown a 2 minuti (default è 5)
az monitor autoscale rule update \
    --resource-group myapp-rg \
    --autoscale-name cpu-autoscale \
    --scale-cool-down 2
```

---

## Riferimenti

- [Azure Well-Architected Framework](https://learn.microsoft.com/azure/well-architected/)
- [WAF Assessment](https://learn.microsoft.com/assessments/)
- [Azure Advisor](https://learn.microsoft.com/azure/advisor/)
- [Azure Architecture Center](https://learn.microsoft.com/azure/architecture/)
- [Cloud Adoption Framework (CAF)](https://learn.microsoft.com/azure/cloud-adoption-framework/)
