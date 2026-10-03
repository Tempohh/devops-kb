---
title: "Azure Pricing & Cost Management"
slug: pricing-azure
category: cloud
tags: [azure, pricing, cost-management, reserved-instances, savings-plans, spot-vms, azure-hybrid-benefit, tco, billing]
search_keywords: [Azure pricing, Azure cost management, Reserved Instances RI, Azure Savings Plans, Azure Spot VMs, Azure Hybrid Benefit, pay-as-you-go, TCO calculator, Azure Budgets, Cost Analysis, billing Azure, free tier Azure, Azure pricing calculator, chargeback showback, tagging costi]
parent: cloud/azure/fondamentali/_index
related: [cloud/azure/fondamentali/well-architected, cloud/azure/compute/virtual-machines]
official_docs: https://azure.microsoft.com/pricing/
status: reviewed
difficulty: beginner
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Pricing & Cost Management

## Modelli di Pricing

### Pay-As-You-Go (PAYG)

Paghi per ciò che usi, senza impegni. Prezzi più alti ma massima flessibilità.

- VM fatturate per **secondo** di utilizzo
- Storage per **GB-mese**
- Bandwidth per **GB outbound** (inbound gratuito)
- Servizi serverless per **esecuzione / request / GB processato**

### Reserved Instances (RI)

Impegno di 1 o 3 anni per VM, SQL, Cosmos DB, ecc. — sconto fino al **72%** rispetto a PAYG.

Le RI sono un **impegno di capacità/tipo** (es. famiglia VM + region): in cambio dello sconto, Azure applica automaticamente la tariffa ridotta alle risorse che corrispondono, fatturando l'impegno anche se non lo usi. Si acquistano da portal (Reservations) con scope `Single subscription`, `Resource group`, `Management group` o `Shared` (tutto il billing account).

```bash
# Elenco reservation order (richiede l'estensione: az extension add --name reservation)
az reservations reservation-order list --output table

# Raccomandazioni di acquisto RI da Advisor
az advisor recommendation list \
    --category Cost \
    --query "[?contains(shortDescription.problem, 'reserved')].{Resource:resourceId, Savings:extendedProperties.annualSavingsAmount}" \
    --output table
```

| Durata | Sconto tipico | Pagamento |
|--------|---------------|-----------|
| 1 anno | ~40% rispetto PAYG | Upfront, mensile, o misto |
| 3 anni | ~60-72% rispetto PAYG | Upfront, mensile, o misto |

### Azure Savings Plans

**Savings Plans** sono impegni di spesa oraria (in USD) flessibili tra più servizi compute:

- **Compute Savings Plan:** copre VM (quindi anche i nodi AKS), Dedicated Host, Container Instances, App Service Premium v3, Functions Premium — flessibile tra size/region/OS
- **Durata:** 1 o 3 anni; **sconto:** fino al 65% rispetto PAYG
- **Differenza vs RI:** RI = impegno su istanza specifica (sconto massimo, es. 72%); Savings Plan = impegno su spesa compute oraria, applicato ai consumi più costosi che rientrano nel perimetro (sconto minore, molta più flessibilità)
- **Attenzione:** a differenza di molte RI, un Savings Plan non è scambiabile né rimborsabile

### Azure Spot VMs

Utilizzo di capacità compute non allocata a prezzi ridotti (fino al **90%** rispetto PAYG):

```bash
# Creare Spot VM
az vm create \
    --resource-group myapp-rg \
    --name spot-worker \
    --image Ubuntu2204 \
    --size Standard_D4s_v5 \
    --priority Spot \
    --eviction-policy Deallocate \
    --max-price -1 \
    --output json
# --eviction-policy: Deallocate (default, i dischi restano e si paga lo storage) o Delete
# --max-price -1: paga il prezzo Spot corrente, nessun cap di prezzo

# Prezzo Spot corrente per una size (Azure Retail Prices API, pubblica, senza auth)
curl -s "https://prices.azure.com/api/retail/prices?\$filter=armRegionName eq 'italynorth' and armSkuName eq 'Standard_D4s_v5' and priceType eq 'Consumption' and contains(meterName,'Spot')"
```

!!! warning "Spot VM — Eviction"
    Le Spot VM possono essere **interrotte con 30 secondi di preavviso** quando Azure ha bisogno della capacità.
    Usare solo per workload interrompibili: batch, rendering, CI workers, ML training.

### Azure Hybrid Benefit

Usa licenze Windows Server o SQL Server esistenti (con Software Assurance o subscription equivalente) su Azure: non paghi la componente licenza inclusa nel prezzo orario (sconto fino al **40%** sulle VM Windows, di più per SQL, cumulabile con RI):

```bash
# VM Windows con Hybrid Benefit
az vm create \
    --resource-group myapp-rg \
    --name mywinvm \
    --image Win2022Datacenter \
    --license-type Windows_Server    # applica Hybrid Benefit

# SQL Server su VM: la licenza si imposta sulla risorsa SQL VM (estensione sqlvm)
az sql vm update \
    --resource-group myapp-rg \
    --name mysqlvm \
    --license-type AHUB              # Azure Hybrid Benefit
```

---

## Azure Free Tier

| Tipo | Durata | Dettaglio |
|------|--------|-----------|
| **Always Free** | Illimitato | 55+ servizi con limiti mensili gratuiti |
| **12 Months Free** | 12 mesi dal primo accesso | Servizi popolari con limiti generosi |
| **$200 Credit** | 30 giorni | Credito per esplorare qualsiasi servizio |

**Always Free (selezione):**
- Azure Functions: 1 milione di esecuzioni/mese
- Azure App Service: 10 web app F1 tier
- Azure SQL: 100.000 vCore-secondi/mese (serverless)
- Azure Cosmos DB: 1000 RU/s + 25 GB (free tier, uno per account)
- Azure DevOps: 5 utenti Basic gratuiti; i minuti di pipeline hosted gratuiti per nuove organizzazioni richiedono una richiesta di parallelismo gratuito

I limiti cambiano: verificare sempre la [pagina Free](https://azure.microsoft.com/free/) (es. Blob Storage 5 GB è nei *12 Months Free*, non Always Free).

---

## Azure Cost Management

### Analisi Costi

```bash
# Analisi spesa per resource group (CLI)
az consumption usage list \
    --start-date 2026-02-01 \
    --end-date 2026-02-28 \
    --query "[].{Service:consumedService, Cost:pretaxCost, RG:instanceId}" \
    --output table

# Per account MCA (Microsoft Customer Agreement) i comandi `az consumption usage`
# non sono supportati: usare Cost Analysis (portal) o la Query API
az costmanagement query \
    --type ActualCost \
    --scope "subscriptions/<subscription-id>" \
    --timeframe MonthToDate \
    --dataset-aggregation '{"totalCost":{"name":"Cost","function":"Sum"}}' \
    --dataset-grouping name=ResourceGroupName type=Dimension
# (richiede l'estensione: az extension add --name costmanagement)
```

### Budget e Alert

Un budget **notifica soltanto** (email o Action Group): non ferma né limita le risorse. Per un'azione automatica (es. spegnere VM) collegare un Action Group a Automation/Logic Apps.

Il modo più affidabile da CLI è la Budgets API via `az rest` (le `notifications` sono un dizionario con chiave arbitraria, non una lista):

```bash
SUB=$(az account show --query id -o tsv)

az rest --method put \
    --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Consumption/budgets/prod-monthly?api-version=2023-05-01" \
    --body '{
      "properties": {
        "category": "Cost",
        "amount": 5000,
        "timeGrain": "Monthly",
        "timePeriod": { "startDate": "2026-01-01T00:00:00Z", "endDate": "2026-12-31T00:00:00Z" },
        "notifications": {
          "actual80":   { "enabled": true, "operator": "GreaterThan", "threshold": 80,  "thresholdType": "Actual",     "contactEmails": ["finops@company.com"] },
          "actual100":  { "enabled": true, "operator": "GreaterThan", "threshold": 100, "thresholdType": "Actual",     "contactEmails": ["cto@company.com"] },
          "forecast110": { "enabled": true, "operator": "GreaterThan", "threshold": 110, "thresholdType": "Forecasted", "contactEmails": ["cto@company.com"] }
        }
      }
    }'
```

`startDate` deve essere il primo giorno di un mese. Gli alert `Forecasted` anticipano lo sforamento prima che avvenga.

### Tag per Cost Allocation

I **tag** Azure sono coppie chiave-valore che permettono di raggruppare e allocare i costi:

```bash
# Applicare tag a resource group
az group update \
    --name myapp-rg \
    --tags \
        Environment=production \
        Team=platform \
        CostCenter=CC-1234 \
        Application=ecommerce

# Azure Policy — require tag su resource group
az policy assignment create \
    --name require-costcenter-tag \
    --policy "/providers/Microsoft.Authorization/policyDefinitions/96670d01-0a4d-4649-9c89-2d3abc0a5025" \
    --params '{"tagName": {"value": "CostCenter"}}'
    # Built-in policy: "Require a tag on resource groups"
```

!!! warning "Tag Propagation"
    I tag applicati a un Resource Group **non si propagano automaticamente** alle risorse contenute. Usare Azure Policy (*Inherit a tag from the resource group if missing*, effect `modify`) oppure la funzione **Tag inheritance** di Cost Management (Settings → Configuration), che copia i tag di subscription/RG sui record di costo senza toccare le risorse.

---

## TCO Calculator e Pricing Calculator

| Strumento | Scopo | URL |
|-----------|-------|-----|
| **Pricing Calculator** | Stimare costo di una soluzione Azure specifica | [azure.microsoft.com/pricing/calculator](https://azure.microsoft.com/pricing/calculator/) |
| **TCO Calculator** | Confrontare costo on-premises vs Azure | [azure.microsoft.com/pricing/tco](https://azure.microsoft.com/pricing/tco/calculator/) |
| **Cost Management** | Monitorare e ottimizzare spesa corrente | Portal → Cost Management + Billing |

---

## Tipi di Subscription e Billing

| Tipo | Descrizione |
|------|-------------|
| **Pay-As-You-Go** | Fatturazione mensile carta di credito — per individui e PMI |
| **Enterprise Agreement (EA)** | Accordo aziendale 3 anni — sconti volume per grandi organizzazioni; legacy, i nuovi clienti vengono indirizzati verso MCA |
| **Microsoft Customer Agreement (MCA)** | Modello di contratto corrente (online o enterprise, *MCA-E*) — sostituisce EA/PAYG legacy |
| **Cloud Solution Provider (CSP)** | Acquisto tramite partner Microsoft — prezzi negoziati |
| **Dev/Test** | Prezzi scontati per ambienti non produzione |

**Struttura billing MCA:**

```
Billing Account (Azienda)
└── Billing Profile (Fattura / metodo di pagamento)
    └── Invoice Section (Progetto / Team)
        └── Subscription
```

Nell'EA legacy la gerarchia è diversa: `Enrollment → Department → Account → Subscription`.

---

## Troubleshooting

### Scenario 1 — Budget Alert non arriva

**Sintomo:** Il budget ha superato la soglia configurata ma non arrivano email di notifica.

**Causa:** Latenza del Cost Management (dati aggiornati ogni 8-24h) oppure email finita in spam; in alcuni casi il budget è stato creato su subscription sbagliata o con `--end-date` già scaduta.

**Soluzione:** Verificare configurazione budget e testare manualmente l'alert.

```bash
# Verificare budget esistenti e relative notifiche
SUB=$(az account show --query id -o tsv)
az rest --method get \
    --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Consumption/budgets?api-version=2023-05-01" \
    --query "value[].{Name:name, Amount:properties.amount, CurrentSpend:properties.currentSpend.amount, Notifications:properties.notifications}"

# Controllare che la subscription sia corretta
az account show --query "{Name:name, ID:id}" --output table

# Ricreare il budget se la configurazione è errata (stesso PUT, sovrascrive)
```

---

### Scenario 2 — Costi imprevisti su Spot VM non interrotte

**Sintomo:** Le Spot VM non vengono evicted anche quando il prezzo Spot supera il `--max-price` impostato.

**Causa:** Con `--max-price -1` non c'è cap di prezzo — Azure non evitta mai per prezzo, solo per recupero capacità. L'eviction per prezzo si attiva SOLO se si specifica un `max-price` positivo.

**Soluzione:** Impostare un max-price esplicito oppure accettare il comportamento predefinito.

```bash
# Verificare max-price corrente di una Spot VM
az vm show \
    --resource-group myapp-rg \
    --name spot-worker \
    --query "billingProfile.maxPrice" \
    --output tsv

# Aggiornare max-price (richiede deallocate prima)
az vm deallocate --resource-group myapp-rg --name spot-worker
az vm update \
    --resource-group myapp-rg \
    --name spot-worker \
    --max-price 0.05    # 0.05 USD/ora — se spot supera, VM viene evicted
az vm start --resource-group myapp-rg --name spot-worker
```

---

### Scenario 3 — Reserved Instance non applicata alle VM

**Sintomo:** Le VM continuano a essere fatturate a tariffa PAYG nonostante una RI acquistata.

**Causa:** La RI è stata acquistata con scope `Single subscription` e la VM gira su subscription diversa; oppure la `region` o la famiglia VM non corrispondono alla RI (con *instance size flexibility*, attiva di default, la RI copre size diverse della stessa famiglia, non famiglie diverse); oppure la RI è scaduta.

**Soluzione:** Verificare scope, famiglia e regione della RI.

```bash
# Elenco reservation order con stato e scadenza
az reservations reservation-order list --output table

# Cambiare scope da single a shared (copre tutte le subscription del billing account)
# Eseguibile dal portal: Reservations → seleziona RI → Change scope → Shared
```

---

### Scenario 4 — Tag non propagati alle risorse figlie

**Sintomo:** Il Cost Analysis mostra risorse senza tag `CostCenter` o `Team` nonostante il Resource Group sia correttamente taggato.

**Causa:** Azure non propaga i tag da Resource Group alle risorse automaticamente; le risorse create prima della policy non vengono remediate in automatico.

**Soluzione:** Usare Azure Policy con `deployIfNotExists` o `modify` effect per ereditare tag, poi eseguire remediation task.

```bash
# Verificare policy assignments attive sul resource group
az policy assignment list \
    --resource-group myapp-rg \
    --query "[].{Name:name, Policy:policyDefinitionId, Effect:parameters.effect.value}" \
    --output table

# Avviare remediation task per applicare la policy retroattivamente
az policy remediation create \
    --name remediate-costcenter \
    --policy-assignment require-costcenter-tag \
    --resource-group myapp-rg

# Monitorare stato remediation
az policy remediation show \
    --name remediate-costcenter \
    --resource-group myapp-rg \
    --query "provisioningState" \
    --output tsv
```

---

## Best Practices

- **Tag strategy prima del giorno 1:** definire uno schema di tag obbligatori (`Environment`, `Team`, `CostCenter`, `Application`) e applicarlo via Azure Policy prima di creare le prime risorse.
- **RI su baseline, Savings Plan su variabilità:** acquistare RI per workload stabili e prevedibili (DB, VM production); usare Compute Savings Plan per copertura flessibile su picchi imprevedibili.
- **Budget su ogni subscription non solo sul billing account:** un budget a livello subscription intercetta lo sforamento prima della fattura (non blocca la spesa, avvisa); un budget a livello billing account offre visibilità aggregata ma non granularità.
- **Advisor Cost settimanale:** eseguire regolarmente `az advisor recommendation list --category Cost` per intercettare RI inutilizzate, VM undersized e risorse orfane (disk, IP pubblici, ecc.).
- **Dev/Test subscription separata:** usare subscription Dev/Test per ambienti non-prod — prezzi scontati fino al 55% su Windows VM e servizi PaaS.

---

## Relazioni

??? info "Azure Well-Architected Framework — Cost Optimization Pillar"
    Il pilastro Cost Optimization del WAF definisce i principi di governance della spesa cloud (tagging, rightsizing, RI/Savings Plan). I modelli di pricing descritti qui sono gli strumenti operativi per applicare quell'ottimizzazione.

    **Approfondimento completo →** [Azure Well-Architected Framework](../fondamentali/well-architected.md)

??? info "Virtual Machines — Sizing e costi compute"
    La scelta della VM size è il principale driver di costo per i workload IaaS. Conoscere la differenza tra PAYG, RI e Spot è fondamentale per scegliere la modalità di acquisto corretta per ogni workload.

    **Approfondimento completo →** [Azure Virtual Machines](../compute/virtual-machines.md)

---

## Riferimenti

- [Azure Pricing](https://azure.microsoft.com/pricing/)
- [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
- [Azure Cost Management](https://learn.microsoft.com/azure/cost-management-billing/)
- [Azure Hybrid Benefit](https://azure.microsoft.com/pricing/hybrid-benefit/)
- [Reserved Instances](https://learn.microsoft.com/azure/cost-management-billing/reservations/save-compute-costs-reservations)
- [Azure Savings Plans](https://learn.microsoft.com/azure/cost-management-billing/savings-plan/)
- [Azure Spot VMs](https://learn.microsoft.com/azure/virtual-machines/spot-vms)
