---
title: "FinOps — Fondamentali"
slug: finops-fondamentali
category: cloud
tags: [finops, cost-optimization, cloud-economics, tagging, rightsizing, chargeback, showback, unit-economics, reserved-instances, spot, savings-plans]
search_keywords: [FinOps, Financial Operations, ottimizzazione costi cloud, cloud cost management, cloud cost optimization, unit economics, rightsizing, tagging strategy, cost allocation, chargeback, showback, cost center, Reserved Instances, Savings Plans, Spot Instances, FinOps Foundation, CNCF FinOps, cloud financial management, CFM, cost governance, cloud spend, cloud billing, anomaly detection, budget alert, cloud waste, idle resources, over-provisioned, costi cloud, gestione finanziaria cloud, cost visibility, forecasting cloud, cost per feature, cost per customer]
parent: cloud/finops/_index
related: [cloud/aws/fondamentali/billing-pricing, cloud/azure/fondamentali/pricing, cloud/gcp/fondamentali/panoramica]
official_docs: https://www.finops.org/
status: needs-review
difficulty: intermediate
last_updated: 2026-03-29
---

# FinOps — Fondamentali

## Panoramica

**FinOps** (Financial Operations) è la disciplina e la cultura organizzativa che porta responsabilità finanziaria al consumo variable e scalabile del cloud. Non è un tool né una funzione aziendale isolata: è un framework collaborativo che unisce **Engineering**, **Finance** e **Business** per prendere decisioni basate su dati di costo.

Il problema che FinOps risolve: nei modelli cloud pay-per-use, i team di ingegneria hanno il potere di spendere immediatamente (ogni deploy può generare costo), mentre la visibilità finanziaria arriva in ritardo. FinOps chiude questo gap portando visibilità real-time e responsabilità distribuita.

**Quando si usa FinOps:** in qualsiasi organizzazione con cloud spend rilevante (indicativamente >$10k/mese) e più team che usano risorse cloud. Prima di quella soglia, la complessità del processo non giustifica l'investimento.

**Quando NON serve un programma FinOps formale:** startup early-stage con un solo team, ambienti puramente on-premises, progetti cloud temporanei con budget fisso e scadenza definita.

Il framework di riferimento è la **FinOps Foundation** (parte della Linux Foundation / CNCF), che definisce terminologia, best practice e certificazioni standard del settore.

---

## Concetti Chiave

### Il Triangolo FinOps

FinOps richiede la collaborazione continua di tre funzioni:

| Funzione | Ruolo | Responsabilità |
|----------|-------|----------------|
| **Engineering** | Crea e gestisce le risorse | Rightsizing, efficienza architetturale, tagging |
| **Finance** | Pianifica e controlla i budget | Forecasting, chargeback, reporting |
| **Business** | Definisce le priorità | Approvazione spese, bilanciamento velocità/costo |

!!! note "Il principio fondamentale"
    Nei modelli cloud tradizionali, chi spende (Engineering) non vede i costi, e chi vede i costi (Finance) non controlla la spesa. FinOps risolve questa asimmetria.

### Le Tre Fasi del Lifecycle FinOps

Il ciclo FinOps è iterativo e continuo — non un progetto con fine:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   INFORM    │───▶│  OPTIMIZE   │───▶│   OPERATE   │
│             │    │             │    │             │
│ Visibilità  │    │ Identificare│    │ Governance  │
│ & Allocazione│   │ opportunità │    │ & Automazione│
└─────────────┘    └─────────────┘    └─────────────┘
       ▲                                     │
       └─────────────────────────────────────┘
                     (ciclo continuo)
```

**Fase INFORM — Visibilità:**
- Raccogliere e normalizzare i dati di costo da tutti i provider
- Allocare il 100% dei costi a team/prodotto/progetto (tagging + showback)
- Calcolare le metriche di unit economics
- Identificare anomalie e trend

**Fase OPTIMIZE — Riduzione sprechi:**
- Eliminare risorse inutilizzate (idle instances, orphaned disks, snapshot vecchi)
- Rightsizing delle risorse over-provisioned
- Acquisto di commitments (Reserved Instances, Savings Plans)
- Ottimizzazione architetturale (Spot, serverless, storage tiering)

**Fase OPERATE — Governance:**
- Definire policy e processi (chi approva cosa, soglie di budget)
- Automatizzare azioni correttive (shutdown notturno, alert)
- Continuous improvement del processo
- Cultura FinOps — engineering teams che fanno trade-off consapevoli

### Maturità FinOps

La FinOps Foundation definisce tre livelli di maturità (Crawl → Walk → Run):

| Livello | Caratteristiche | Metriche tipiche |
|---------|----------------|-----------------|
| **Crawl** | Visibilità di base, tagging parziale, budget alert manuali | <50% costi allocati, revisioni mensili |
| **Walk** | Tagging >80%, showback automatico, rightsizing attivo | Rightsizing trimestrale, anomaly detection |
| **Run** | Allocazione 100%, chargeback reale, automazione, forecasting accurato | Unit economics per prodotto, ottimizzazione continua |

---

## Come Funziona — Componenti Essenziali

### 1. Tagging Strategy

Il tagging è la fondamenta di ogni programma FinOps. Senza tag coerenti non è possibile allocare i costi ai team/prodotti.

**Tag minimi obbligatori (standard de-facto):**

```yaml
# Esempio tag set obbligatorio per ogni risorsa cloud
Environment: production | staging | dev | sandbox
Team: platform | backend | frontend | data | security
Project: nome-progetto-o-prodotto
CostCenter: CC-1234
Owner: email-responsabile@company.com
```

**Enforcement dei tag — AWS:**

```bash
# AWS Config Rule: require-tags su tutte le risorse EC2
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "required-tags-ec2",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "REQUIRED_TAGS"
    },
    "Scope": {
      "ComplianceResourceTypes": ["AWS::EC2::Instance"]
    },
    "InputParameters": "{\"tag1Key\":\"Team\",\"tag2Key\":\"Project\",\"tag3Key\":\"Environment\"}"
  }'

# Trovare risorse EC2 senza tag obbligatori
aws ec2 describe-instances \
  --query "Reservations[*].Instances[?!not_null(Tags[?Key=='Team'])].[InstanceId, InstanceType, State.Name]" \
  --output table
```

**Enforcement dei tag — Azure Policy:**

```bash
# Azure Policy: richiedi tag CostCenter su tutti i resource group
az policy assignment create \
  --name require-costcenter-tag \
  --policy "/providers/Microsoft.Authorization/policyDefinitions/96670d01-0a4d-4649-9c89-2d3abc0a5025" \
  --scope "/subscriptions/$(az account show --query id -o tsv)" \
  --params '{"tagName": {"value": "CostCenter"}}'

# Audit compliance dei tag su tutti i resource group
az group list \
  --query "[?tags.CostCenter == null].{Name:name, Location:location}" \
  --output table
```

!!! warning "Tag retroattivi"
    I tag vanno imposti **prima** della creazione delle risorse, non a posteriori. Senza enforcement automatico (AWS Config, Azure Policy, Terraform pre-conditions), i team tendono a taggare inconsistentemente. Uno script retroattivo su 1000 risorse è più costoso da gestire che 1 policy attiva dall'inizio.

### 2. Showback vs Chargeback

Due approcci per attribuire i costi ai team:

| Modello | Descrizione | Pro | Contro |
|---------|-------------|-----|--------|
| **Showback** | Mostrare i costi per team/progetto senza addebitarli realmente | Facile da implementare, crea consapevolezza | Senza impatto economico, incentivi deboli |
| **Chargeback** | Addebitare realmente i costi al budget del team/BU | Responsabilità forte, ottimizzazione spontanea | Richiede budget separati, può creare conflitti |

La maggior parte delle organizzazioni inizia con showback e migra verso chargeback parziale per i team maturi.

```bash
# AWS Cost Explorer API — esportare costi per tag Team
aws ce get-cost-and-usage \
  --time-period '{"Start":"2026-03-01","End":"2026-03-31"}' \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by '[{"Type":"TAG","Key":"Team"}]' \
  --query "ResultsByTime[0].Groups[*].{Team:Keys[0],Cost:Metrics.UnblendedCost.Amount}" \
  --output table
```

### 3. Unit Economics

Le **unit economics** misurano il costo cloud in relazione al valore prodotto — l'unica metrica che risponde alla domanda "stiamo spendendo bene?":

| Metrica | Formula | Esempio |
|---------|---------|---------|
| **Cost per Request** | Spesa cloud / N. richieste | $0.0003 per API call |
| **Cost per Customer** | Spesa cloud / N. clienti attivi | $2.40/mese per utente |
| **Cost per Transaction** | Spesa cloud / N. transazioni | $0.05 per ordine |
| **Infrastructure Efficiency** | Revenue / Spesa cloud | $12 revenue per $1 di infra |

!!! tip "La metrica giusta"
    Una riduzione del 20% della spesa cloud con un calo del 50% delle performance non è un successo. Le unit economics mettono la spesa in contesto: $100k/mese può essere ottimo per 10M utenti, o eccessivo per 10k utenti.

```python
# Script Python per calcolare cost-per-customer (esempio)
import boto3
from datetime import datetime, timedelta

ce_client = boto3.client('ce', region_name='us-east-1')

# Costo cloud del mese corrente
response = ce_client.get_cost_and_usage(
    TimePeriod={
        'Start': '2026-03-01',
        'End': '2026-03-31'
    },
    Granularity='MONTHLY',
    Metrics=['UnblendedCost']
)

total_cost = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
active_customers = 15000  # da database/analytics

cost_per_customer = total_cost / active_customers
print(f"Total cloud cost: ${total_cost:,.2f}")
print(f"Cost per customer: ${cost_per_customer:.4f}/month")
print(f"Infrastructure efficiency: ${active_customers * 50 / total_cost:.1f} revenue per $1 infra")
```

### 4. Rightsizing

Il rightsizing identifica le risorse **over-provisioned** e le ridimensiona al livello effettivamente necessario — spesso il risparmio maggiore nell'ottimizzazione FinOps.

**Processo di rightsizing:**

```
1. Raccogliere metriche utilizzo (CPU, memoria, network) per 2-4 settimane
2. Identificare risorse con utilizzo medio < 20-30% (over-provisioned)
3. Proporre raccomandazioni con risparmio stimato
4. Review con il team owner (potrebbero esserci vincoli non visibili dalle metriche)
5. Applicare in ambiente staging prima di produzione
6. Monitorare 1-2 settimane post-riduzione
```

**Rightsizing con AWS Compute Optimizer:**

```bash
# Ottenere raccomandazioni per istanze over-provisioned
aws compute-optimizer get-ec2-instance-recommendations \
  --account-ids $(aws sts get-caller-identity --query Account --output text) \
  --filters name=Finding,values=Overprovisioned \
  --query "instanceRecommendations[*].{
    Instance:instanceArn,
    Current:currentInstanceType,
    Recommended:recommendationOptions[0].instanceType,
    Savings:recommendationOptions[0].estimatedMonthlySavings.value
  }" \
  --output table

# Rightsizing Lambda (memoria)
aws compute-optimizer get-lambda-function-recommendations \
  --filters name=Finding,values=Overprovisioned \
  --query "lambdaFunctionRecommendations[*].{
    Function:functionArn,
    CurrentMem:currentMemorySize,
    RecommendedMem:memorySizeRecommendationOptions[0].memorySize,
    Savings:memorySizeRecommendationOptions[0].projectedUtilizationMetrics[0].upperBoundValue
  }" \
  --output table
```

**Rightsizing con Azure Advisor:**

```bash
# Raccomandazioni VM rightsizing da Azure Advisor
az advisor recommendation list \
  --category Cost \
  --query "[?contains(shortDescription.problem, 'right-size') || contains(shortDescription.problem, 'underutilized')].{
    Resource:resourceId,
    Problem:shortDescription.problem,
    Solution:shortDescription.solution,
    Impact:impact
  }" \
  --output table
```

**Rightsizing con GCP Recommender:**

Il servizio [Cloud Recommender](https://cloud.google.com/recommender) analizza l'utilizzo delle istanze Compute Engine e produce raccomandazioni automatiche con risparmio stimato. I due tipi rilevanti per FinOps sono:

- `compute.googleapis.com/instance/idle` — istanza non utilizzata: nessun traffico significativo nelle ultime 2 settimane
- `compute.googleapis.com/instance/overprovisioned` — istanza over-sized: CPU e/o memoria sistematicamente sotto-utilizzate

```bash
# Listare raccomandazioni idle instances per un progetto
gcloud recommender recommendations list \
  --project=my-project-id \
  --location=europe-west1 \
  --recommender=google.compute.instance.IdleResourceRecommender \
  --format="table(name.basename(), content.overview.resourceName, \
    primaryImpact.costProjection.cost.units, \
    stateInfo.state)"

# Listare raccomandazioni rightsizing (over-provisioned)
gcloud recommender recommendations list \
  --project=my-project-id \
  --location=europe-west1 \
  --recommender=google.compute.instance.MachineTypeRecommender \
  --format="table(name.basename(), \
    content.overview.resourceName, \
    content.overview.recommendedMachineType.name, \
    primaryImpact.costProjection.cost.units)"

# Applicare una raccomandazione (dopo review manuale)
gcloud recommender recommendations mark-claimed \
  --project=my-project-id \
  --location=europe-west1 \
  --recommender=google.compute.instance.MachineTypeRecommender \
  --recommendation=RECOMMENDATION_ID \
  --etag=ETAG

# Analisi aggregata multi-progetto tramite Asset Inventory
gcloud asset search-all-resources \
  --scope=organizations/ORG_ID \
  --asset-types=compute.googleapis.com/Instance \
  --query="labels.Team:*" \
  --format="table(name, location, labels)"
```

!!! tip "Recommender via BigQuery"
    Per analisi aggregate su molti progetti, esportare le raccomandazioni in BigQuery usando l'API `recommender.googleapis.com` e interrogarle con SQL. Questo è più efficiente di chiamate `gcloud` progetto per progetto.

---

## Configurazione & Pratica

### Setup Minimo FinOps — AWS

```bash
# Step 1: Abilitare Cost Allocation Tags (obbligatorio per Cost Explorer)
aws ce list-cost-allocation-tags --status Inactive \
  --query "CostAllocationTags[?TagKey=='Team' || TagKey=='Project' || TagKey=='Environment'].[TagKey]" \
  --output text | while read tag; do
    aws ce update-cost-allocation-tags-status \
      --cost-allocation-tags-status "[{\"TagKey\":\"$tag\",\"Status\":\"Active\"}]"
    echo "Activated tag: $tag"
  done

# Step 2: Creare Cost and Usage Report (CUR) per analisi avanzata
aws cur put-report-definition \
  --report-definition '{
    "ReportName": "finops-cur",
    "TimeUnit": "HOURLY",
    "Format": "Parquet",
    "Compression": "Parquet",
    "AdditionalSchemaElements": ["RESOURCES"],
    "S3Bucket": "my-finops-cur-bucket",
    "S3Prefix": "cur/",
    "S3Region": "eu-west-1",
    "RefreshClosedReports": true,
    "ReportVersioning": "OVERWRITE_REPORT"
  }'

# Step 3: Budget mensile con alert a 80% e 100%
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget '{
    "BudgetName": "monthly-total",
    "BudgetLimit": {"Amount": "5000", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[
    {
      "Notification": {
        "NotificationType": "ACTUAL",
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": 80,
        "ThresholdType": "PERCENTAGE"
      },
      "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "finops@company.com"}]
    },
    {
      "Notification": {
        "NotificationType": "FORECASTED",
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": 100,
        "ThresholdType": "PERCENTAGE"
      },
      "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "finops@company.com"}]
    }
  ]'
```

### Setup Minimo FinOps — Azure

```bash
# Step 1: Budget mensile con alert a 80%, 100% e forecast 110%
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az consumption budget create \
  --budget-name monthly-total \
  --amount 5000 \
  --time-grain Monthly \
  --start-date 2026-01-01 \
  --end-date 2026-12-31 \
  --category Cost \
  --scope "/subscriptions/$SUBSCRIPTION_ID" \
  --notifications '[
    {"enabled": true, "operator": "GreaterThan", "threshold": 80,
     "contactEmails": ["finops@company.com"], "thresholdType": "Actual"},
    {"enabled": true, "operator": "GreaterThan", "threshold": 100,
     "contactEmails": ["finops@company.com", "cto@company.com"], "thresholdType": "Actual"},
    {"enabled": true, "operator": "GreaterThan", "threshold": 110,
     "contactEmails": ["cto@company.com"], "thresholdType": "Forecasted"}
  ]'

# Step 2: Azure Policy — enforce tag su resource group
for tag in "Team" "Project" "Environment" "CostCenter"; do
  az policy assignment create \
    --name "require-${tag,,}-tag" \
    --policy "/providers/Microsoft.Authorization/policyDefinitions/96670d01-0a4d-4649-9c89-2d3abc0a5025" \
    --scope "/subscriptions/$SUBSCRIPTION_ID" \
    --params "{\"tagName\": {\"value\": \"$tag\"}}"
done

# Step 3: Esportazione costi verso Storage Account (equivalente CUR)
az costmanagement export create \
  --name finops-daily-export \
  --type ActualCost \
  --scope "/subscriptions/$SUBSCRIPTION_ID" \
  --storage-account-id "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/finops-rg/providers/Microsoft.Storage/storageAccounts/finopsexports" \
  --storage-container "exports" \
  --timeframe MonthToDate \
  --recurrence Daily \
  --recurrence-period from=2026-03-01 to=2026-12-31
```

### Setup Minimo FinOps — GCP

```bash
# ---------------------------------------------------------------
# Prerequisito: abilitare la Billing API e il progetto di billing
# ---------------------------------------------------------------
gcloud services enable billingbudgets.googleapis.com
gcloud services enable bigquery.googleapis.com

# Recuperare il Billing Account ID
gcloud billing accounts list --format="table(name, displayName, open)"
# Output: BILLING_ACCOUNT_ID = billingAccounts/012345-ABCDEF-GHIJKL

BILLING_ACCOUNT="billingAccounts/012345-ABCDEF-GHIJKL"

# Step 1: Budget mensile con alert a 50%, 80%, 100% (actual) e 110% (forecast)
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name="monthly-total" \
  --budget-amount=5000USD \
  --threshold-rule=percent=0.5,basis=CURRENT_SPEND \
  --threshold-rule=percent=0.8,basis=CURRENT_SPEND \
  --threshold-rule=percent=1.0,basis=CURRENT_SPEND \
  --threshold-rule=percent=1.1,basis=FORECASTED_SPEND \
  --notifications-rule-pubsub-topic=projects/my-project-id/topics/billing-alerts \
  --calendar-period=MONTH

# Creare il topic Pub/Sub per ricevere le notifiche budget
gcloud pubsub topics create billing-alerts --project=my-project-id

# Step 2: Label enforcement tramite Organization Policy
# Richiedere il label "team" su tutte le risorse Compute Engine
gcloud org-policies set-policy - <<'EOF'
name: organizations/ORG_ID/policies/compute.disableSerialPortAccess
spec:
  rules:
  - enforce: true
EOF

# Policy custom per label obbligatori (richiede Custom Org Policy — disponibile da GA 2024)
gcloud org-policies set-policy label-policy.yaml --organization=ORG_ID

# label-policy.yaml (esempio):
# name: organizations/ORG_ID/policies/custom.requireLabels
# spec:
#   rules:
#   - condition:
#       expression: >
#         resource.type == "compute.googleapis.com/Instance" &&
#         !has(resource.labels.team)
#     enforce: true

# Step 3: BigQuery Billing Export — esportare i dati di costo per analisi avanzata
# Da Console: Billing → Billing Export → BigQuery Export → Enable
# Via gcloud (richiede un dataset BigQuery già esistente):
bq mk --dataset \
  --location=EU \
  --description "GCP Billing Export" \
  my-project-id:billing_export

# Abilitare Standard Usage Cost Export (da Console o API Billing)
gcloud billing accounts get-iam-policy "$BILLING_ACCOUNT"

# Step 4: Analisi costi con gcloud CLI
# Costo per servizio dell'ultimo mese (via BigQuery — dopo export attivo)
bq query --use_legacy_sql=false '
SELECT
  service.description AS service,
  ROUND(SUM(cost), 2) AS monthly_cost_usd,
  ROUND(SUM(cost) / SUM(SUM(cost)) OVER () * 100, 1) AS pct_total
FROM `my-project-id.billing_export.gcp_billing_export_v1_*`
WHERE DATE(_PARTITIONTIME) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND CURRENT_DATE()
GROUP BY service.description
ORDER BY monthly_cost_usd DESC
LIMIT 10'

# Costo per label "team" (cost allocation)
bq query --use_legacy_sql=false '
SELECT
  (SELECT value FROM UNNEST(labels) WHERE key = "team") AS team,
  ROUND(SUM(cost), 2) AS monthly_cost_usd
FROM `my-project-id.billing_export.gcp_billing_export_v1_*`
WHERE DATE(_PARTITIONTIME) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND CURRENT_DATE()
GROUP BY team
ORDER BY monthly_cost_usd DESC'
```

!!! note "BigQuery Export vs Standard Reports"
    GCP offre due tipi di export BigQuery: **Standard Usage Cost** (aggregato giornaliero, gratuito) e **Detailed Usage Cost** (granularità per risorsa, include crediti e sconti, necessario per analisi avanzate). Per un programma FinOps, abilitare entrambi fin dall'inizio — retroattivi non sono disponibili.

!!! tip "Committed Use Discounts (CUD)"
    L'equivalente GCP dei Reserved Instances è il **Committed Use Discount**: 1 o 3 anni su vCPU e memoria, con sconto fino al 57% (3 anni) rispetto al prezzo on-demand. A differenza di AWS, i CUD GCP si applicano automaticamente a tutte le VM idonee nel progetto, senza scegliere un'istanza specifica.

### Strumenti FinOps Multi-Cloud

| Strumento | Tipo | Forza principale |
|-----------|------|-----------------|
| **AWS Cost Explorer** | Native AWS | RI/SP recommendations, forecasting |
| **Azure Cost Management** | Native Azure | Budget alerts, cost analysis per tag |
| **GCP Billing Console** | Native GCP | Dashboard costi, budget alerts, CUD tracking |
| **GCP Cloud Billing API** | Native GCP | Automazione report costi, export programmatico |
| **GCP Cost Table Reports** | Native GCP | Vista tabulare per progetto/servizio/SKU |
| **GCP Cost Breakdown Reports** | Native GCP | Analisi sconti (CUD, SUD), crediti separati dai costi lordi |
| **BigQuery Billing Export** | Native GCP | Analisi avanzata con SQL, retention illimitata, join con dati business |
| **GCP Recommender** | Native GCP | Rightsizing automatico VM, idle resource detection |
| **CloudHealth (VMware)** | Commerciale multi-cloud | Policy automation, chargeback avanzato |
| **Apptio Cloudability** | Commerciale multi-cloud | Unit economics, forecasting, FinOps workflow |
| **OpenCost** | Open source (CNCF) | Cost allocation Kubernetes, self-hosted |
| **Infracost** | Open source | Stima costi IaC pre-deploy (Terraform) |
| **Kubecost** | Open source/commerciale | Kubernetes cost visibility per namespace/pod |

```bash
# Infracost — stimare costo Terraform prima di applicare
# Installazione
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Setup API key (gratuita)
infracost auth login

# Stima costi di un piano Terraform
cd my-terraform-module/
terraform plan -out tfplan.json
terraform show -json tfplan.json > plan.json
infracost breakdown --path plan.json

# Output tipico:
# Project: my-terraform-module
# ┌─────────────────────────────┬────────────────────┬────────────┐
# │ Name                        │ Monthly Qty        │   Monthly  │
# ├─────────────────────────────┼────────────────────┼────────────┤
# │ aws_instance.web[0]         │ 730 hours          │     $29.22 │
# │ aws_db_instance.main        │ 730 hours + 100 GB │    $178.50 │
# └─────────────────────────────┴────────────────────┴────────────┘
# Total monthly cost: $207.72
```

---

## Best Practices

### Commitment Purchasing — Quando e Quanto

!!! warning "Errore comune: over-commitment"
    Acquistare Reserved Instances o Savings Plans per il 100% del workload attuale è un errore. Se il workload si riduce, si paga per capacità inutilizzata senza possibilità di rimborso (o con penali per la vendita sul marketplace).

**Formula consigliata:**

```
Coverage ottimale = (Spesa base stabile × 70-80%) → Commitments
                  + (Spesa variabile)              → On-Demand/Spot
```

- Analizzare almeno **3-6 mesi** di storico prima di acquistare commitments
- Preferire **Compute Savings Plans** (AWS) / **Compute Savings Plans** (Azure) per flessibilità
- Revisionare l'utilizzo ogni trimestre: commitment utilizzati < 80% = over-commitment

```bash
# Verificare utilizzo Savings Plans AWS (deve essere vicino al 100%)
aws ce get-savings-plans-utilization \
  --time-period '{"Start":"2026-03-01","End":"2026-03-31"}' \
  --query "Total.{Utilization:Utilization.UtilizationPercentage, OnDemandSpend:Savings.OnDemandCostEquivalent, SavingsAmount:Savings.NetSavings}" \
  --output table
```

### Waste Elimination — Quick Wins

Le risorse inutilizzate più comuni (in ordine di frequenza):

1. **Istanze EC2/VM ferme** — stopped ma con storage ancora fatturato
2. **Load Balancer senza target** — ALB/NLB con 0 target registrati
3. **Elastic IP non associati** — $0.005/ora ciascuno, si accumulano
4. **Snapshot EBS/disk obsoleti** — backup automatici mai eliminati
5. **NAT Gateway in VPC inutilizzati** — $0.045/ora + data processing
6. **CloudWatch Log Groups senza retention** — log crescono senza limite

```bash
# AWS: trovare Elastic IP non associati
aws ec2 describe-addresses \
  --query "Addresses[?AssociationId==null].{IP:PublicIp, AllocationId:AllocationId}" \
  --output table

# AWS: EC2 ferme (stopped) da più di 30 giorni (approssimazione via tag)
aws ec2 describe-instances \
  --filters Name=instance-state-name,Values=stopped \
  --query "Reservations[*].Instances[*].{ID:InstanceId, Type:InstanceType, Stopped:StateTransitionReason}" \
  --output table

# AWS: Load Balancer senza target attivi
aws elbv2 describe-load-balancers --query "LoadBalancers[*].LoadBalancerArn" --output text | \
  tr '\t' '\n' | while read arn; do
    count=$(aws elbv2 describe-target-groups --load-balancer-arn "$arn" --query "length(TargetGroups)" --output text)
    if [ "$count" -eq 0 ]; then echo "No target groups: $arn"; fi
  done

# AWS: snapshot EBS più vecchi di 90 giorni
aws ec2 describe-snapshots \
  --owner-ids self \
  --query "Snapshots[?StartTime<='2025-12-25'].{ID:SnapshotId, Size:VolumeSize, Date:StartTime, Desc:Description}" \
  --output table
```

```bash
# GCP: trovare VM in stato TERMINATED (ferme ma con disco ancora fatturato)
gcloud compute instances list \
  --filter="status=TERMINATED" \
  --format="table(name, zone, machineType, status, labels.team)"

# GCP: trovare dischi persistenti non collegati a nessuna VM
gcloud compute disks list \
  --filter="NOT users:*" \
  --format="table(name, zone, sizeGb, type, labels.team)" \
  --sort-by=~sizeGb

# GCP: trovare static IP (indirizzi esterni) non utilizzati
# Gli static IP non associati costano ~$0.010/ora ciascuno
gcloud compute addresses list \
  --filter="status=RESERVED AND addressType=EXTERNAL" \
  --format="table(name, region, address, status)"

# GCP: trovare snapshot più vecchi di 90 giorni
gcloud compute snapshots list \
  --filter="creationTimestamp < $(date -d '90 days ago' +%Y-%m-%d)" \
  --format="table(name, diskSizeGb, creationTimestamp, storageBytes)"

# GCP: trovare Load Balancer (forwarding rules) senza backend configurati
gcloud compute forwarding-rules list \
  --format="table(name, region, IPAddress, target, loadBalancingScheme)"

# GCP: Cloud NAT — verificare il traffico (equivalente NAT Gateway AWS)
# I Cloud NAT addebitano per porta-minuto allocata e per GB processato
gcloud compute routers list \
  --format="table(name, region, network)"
# Per il traffico dettagliato, usare Cloud Logging o BigQuery billing export:
# SELECT service.description, SUM(cost) FROM billing_export
# WHERE service.description LIKE '%Cloud NAT%'
```

### Spot & Preemptible — Pattern di Utilizzo

!!! tip "Spot per CI/CD"
    I job CI/CD sono il caso d'uso ideale per Spot: sono brevi (< 1 ora), riavviabili, e di solito non in orario di punta AWS. Risparmio tipico: 70-85% vs On-Demand.

```yaml
# GitHub Actions — runner self-hosted su Spot EC2 (via actions-runner-controller)
# Configurazione HRA (HorizontalRunnerAutoscaler) con Spot
apiVersion: actions.summerwind.dev/v1alpha1
kind: HorizontalRunnerAutoscaler
metadata:
  name: ci-runner-hpa
spec:
  scaleTargetRef:
    name: ci-runner-deployment
  minReplicas: 0
  maxReplicas: 10
  metrics:
  - type: TotalNumberOfQueuedAndInProgressWorkflowRuns
    repositoryNames:
    - my-org/my-repo
---
# Configurazione RunnerDeployment con Spot
apiVersion: actions.summerwind.dev/v1alpha1
kind: RunnerDeployment
metadata:
  name: ci-runner-deployment
spec:
  template:
    spec:
      nodeSelector:
        eks.amazonaws.com/capacityType: SPOT
      tolerations:
      - key: "eks.amazonaws.com/capacityType"
        operator: "Equal"
        value: "SPOT"
        effect: "NoSchedule"
```

### Governance e Policy

```bash
# AWS Service Control Policy — bloccare regioni non autorizzate (riduce spread costi)
# Da applicare a livello AWS Organizations
cat > scp-deny-regions.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "NotAction": [
        "iam:*", "organizations:*", "sts:*",
        "cloudfront:*", "route53:*", "waf:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["eu-west-1", "eu-central-1", "us-east-1"]
        }
      }
    }
  ]
}
EOF

aws organizations create-policy \
  --name DenyUnauthorizedRegions \
  --type SERVICE_CONTROL_POLICY \
  --content file://scp-deny-regions.json
```

---

## Troubleshooting

### Problema: Spesa cloud aumenta ma nessun team sa perché

**Sintomo:** La fattura mensile cresce del 30%, nessun team ha ricevuto alert, nessuno sa quale risorsa o servizio è responsabile.

**Causa:** Mancanza di anomaly detection e di granularità nei tag → impossibile isolare la causa.

**Soluzione:**
```bash
# Abilitare AWS Cost Anomaly Detection
aws ce create-anomaly-monitor \
  --anomaly-monitor '{
    "MonitorName": "all-services-monitor",
    "MonitorType": "DIMENSIONAL",
    "MonitorDimension": "SERVICE"
  }'

# Creare subscription per alert via email
aws ce create-anomaly-subscription \
  --anomaly-subscription '{
    "SubscriptionName": "anomaly-alert",
    "Threshold": 100,
    "Frequency": "DAILY",
    "MonitorArnList": ["<monitor-arn-from-above>"],
    "Subscribers": [{"Address": "finops@company.com", "Type": "EMAIL"}]
  }'

# Investigare con Cost Explorer API: top 10 servizi per spesa nel mese
aws ce get-cost-and-usage \
  --time-period '{"Start":"2026-03-01","End":"2026-03-31"}' \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by '[{"Type":"DIMENSION","Key":"SERVICE"}]' \
  --query "ResultsByTime[0].Groups | sort_by(@, &to_number(Metrics.UnblendedCost.Amount)) | reverse(@) | [0:10].{Service:Keys[0],Cost:Metrics.UnblendedCost.Amount}" \
  --output table
```

---

### Problema: Tagging incompleto — 40% dei costi non allocato

**Sintomo:** In Cost Explorer, la voce "Untagged" o "No Tag" rappresenta una percentuale elevata della spesa.

**Causa:** Risorse create manualmente senza tag, o team che non seguono le convenzioni.

**Soluzione:**
```bash
# AWS: trovare tutte le risorse EC2 senza il tag obbligatorio "Team"
aws resourcegroupstaggingapi get-resources \
  --resource-type-filters ec2:instance \
  --tag-filters '[{"Key":"Team","Values":[""]}]' \
  --query "ResourceTagMappingList[*].ResourceARN" \
  --output text

# Applicare tag di default temporaneo per identificare l'owner via altri metadati
aws ec2 describe-instances \
  --query "Reservations[*].Instances[?!not_null(Tags[?Key=='Team'])][InstanceId, LaunchTime, KeyName]" \
  --output table

# Azure: lista risorse senza tag CostCenter per resource group
az resource list \
  --query "[?tags.CostCenter == null].{Type:type, Name:name, RG:resourceGroup}" \
  --output table | head -50
```

---

### Problema: Reserved Instances/Savings Plans con utilizzo < 60%

**Sintomo:** Hai acquistato commitments ma il rapporto di utilizzo nel billing dashboard mostra percentuali basse. Stai pagando per capacità non usata.

**Causa:** Over-commitment, workload ridimensionato, o migrazione a servizi diversi (es. da EC2 a Lambda) dopo l'acquisto.

**Soluzione:**
```bash
# Verificare utilizzo RI AWS
aws ce get-reservation-utilization \
  --time-period '{"Start":"2026-03-01","End":"2026-03-31"}' \
  --granularity MONTHLY \
  --query "Total.{
    UtilizationPercent:UtilizationPercentage,
    UnusedHours:UnusedHours,
    UnusedValue:UnusedRecurringFee
  }" \
  --output table

# Se utilizzo < 80%: vendere RI inutilizzate nel Reserved Instance Marketplace
# (solo Standard RI, non Convertible)
# Accedere via Console: EC2 → Reserved Instances → Actions → Sell Reserved Instances

# Convertire RI inutilizzate in Convertible RI (più flessibili)
aws ec2 describe-reserved-instances \
  --filters Name=state,Values=active \
  --query "ReservedInstances[?OfferingClass=='standard'].{ID:ReservedInstancesId, Type:InstanceType, Count:InstanceCount, End:End}" \
  --output table
```

---

### Problema: Costi NAT Gateway eccessivi

**Sintomo:** AWS bill mostra NAT Gateway come uno dei top 5 servizi per costo, spesso inaspettato.

**Causa:** Ogni byte che transita attraverso NAT Gateway viene addebitato ($0.045/GB + $0.045/ora). Lambda, ECS tasks, e batch jobs che scaricano dati dall'esterno possono generare costi elevati.

**Soluzione:**
```bash
# Trovare i NAT Gateway attivi e verificare il traffico
aws ec2 describe-nat-gateways \
  --filter Name=state,Values=available \
  --query "NatGateways[*].{ID:NatGatewayId, VPC:VpcId, Subnet:SubnetId, Created:CreateTime}" \
  --output table

# CloudWatch metric per data processing via NAT Gateway
aws cloudwatch get-metric-statistics \
  --namespace AWS/NATGateway \
  --metric-name BytesOutToDestination \
  --dimensions Name=NatGatewayId,Value=nat-xxxxxxxxx \
  --start-time 2026-03-01T00:00:00Z \
  --end-time 2026-03-31T23:59:59Z \
  --period 2592000 \
  --statistics Sum \
  --query "Datapoints[0].Sum" \
  --output text

# Soluzione: VPC Endpoints per servizi AWS (S3, DynamoDB) — gratuiti/economici
# Elimina traffico S3/DynamoDB dal NAT Gateway
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxxxxxxxx \
  --service-name com.amazonaws.eu-west-1.s3 \
  --route-table-ids rtb-xxxxxxxxx
```

---

## Relazioni

??? info "AWS Billing & Pricing — Approfondimento strumenti AWS"
    Strumenti nativi AWS per cost management: Cost Explorer, Budgets, Trusted Advisor, Compute Optimizer, Savings Plans, Reserved Instances Marketplace.

    **Approfondimento completo →** [AWS Billing & Pricing](../aws/fondamentali/billing-pricing.md)

??? info "Azure Cost Management — Approfondimento strumenti Azure"
    Strumenti nativi Azure: Cost Analysis, Budgets, Advisor recommendations, Reserved Instances, Azure Hybrid Benefit.

    **Approfondimento completo →** [Azure Pricing & Cost Management](../azure/fondamentali/pricing.md)

??? info "GCP Billing & Pricing — Approfondimento strumenti GCP"
    Strumenti nativi GCP per cost management: Cloud Billing Console, BigQuery Billing Export, Cloud Billing API, GCP Recommender, Committed Use Discounts (CUD), Sustained Use Discounts (SUD), Budget Alerts via Pub/Sub.

    **Approfondimento completo →** [GCP Billing & Pricing](../gcp/fondamentali/billing-pricing.md)

---

## Riferimenti

- [FinOps Foundation](https://www.finops.org/) — framework di riferimento, certificazioni (FinOps Certified Practitioner)
- [FinOps Open Cost & Usage Specification (FOCUS)](https://focus.finops.org/) — standard per normalizzare i dati di costo multi-cloud
- [OpenCost (CNCF)](https://www.opencost.io/) — cost monitoring Kubernetes open source
- [Infracost](https://www.infracost.io/) — stima costi IaC pre-deploy
- [AWS Cost Anomaly Detection](https://aws.amazon.com/aws-cost-management/aws-cost-anomaly-detection/)
- [Azure Cost Management Best Practices](https://learn.microsoft.com/azure/cost-management-billing/costs/cost-mgt-best-practices)
- [GCP FinOps Hub](https://cloud.google.com/finops)
- [FinOps Foundation — State of FinOps Report](https://data.finops.org/) — benchmark annuale sull'adozione FinOps
