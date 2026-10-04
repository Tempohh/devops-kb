---
title: "Billing & Pricing GCP"
slug: billing-pricing
category: cloud/gcp
tags: [gcp, billing, pricing, cost-optimization, sustained-use-discounts, committed-use-discounts, spot-vm, preemptible, bigquery-pricing, budget-alerts, finops, billing-export]
search_keywords: [GCP billing, GCP pricing, Google Cloud pricing, costi GCP, gestione costi GCP, Sustained Use Discounts, SUD, Committed Use Discounts, CUD, Preemptible VM, Spot VM, BigQuery on-demand pricing, BigQuery flat-rate, BigQuery slot, Billing Account GCP, budget alert GCP, esportazione billing BigQuery, gcloud billing, Billing API GCP, pay-as-you-go GCP, Google Cloud free tier, free trial GCP, crediti GCP, FinOps GCP, cost allocation labels GCP, rightsizing GCP, Recommender API, Cloud Billing Budget, TCO GCP, confronto AWS Azure pricing, GCP pricing calculator, Active Assist, carbon footprint GCP]
parent: cloud/gcp/fondamentali/_index
related: [cloud/aws/fondamentali/billing-pricing, cloud/gcp/fondamentali/panoramica, cloud/gcp/dati/bigquery, cloud/gcp/containers/gke]
official_docs: https://cloud.google.com/billing/docs
status: needs-review
difficulty: beginner
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Billing & Pricing GCP

## Panoramica

Google Cloud Platform usa un modello **pay-as-you-go** dove si paga per ciò che si consuma, al secondo o al minuto, senza costi minimi. GCP si distingue da AWS e Azure per i **Sustained Use Discounts (SUD)**: sconti automatici che si applicano senza alcuna azione da parte dell'utente quando si usa una risorsa per oltre il 25% del mese. Per impegni più lunghi esistono i **Committed Use Discounts (CUD)**, equivalenti delle Reserved Instances AWS ma con una struttura più flessibile.

La gestione della spesa avviene attraverso i **Billing Account**, entità centrali che aggregano i costi di uno o più project e permettono export granulare su BigQuery per analisi FinOps avanzate.

---

## Principi di Pricing GCP

GCP applica prezzi su **4 driver fondamentali**:

| Driver | Esempi |
|--------|--------|
| **Compute** | VM ore/secondi, GKE nodi, Cloud Run CPU+memoria, Cloud Functions invocazioni |
| **Storage** | Cloud Storage GB/mese per classe, Persistent Disk GB provisioned, Filestore |
| **Network** | Egress verso Internet (a pagamento), egress inter-regione (a pagamento), ingress gratuito |
| **Servizi Managed** | BigQuery TB processati o slot, Cloud SQL vCPU+RAM, Spanner nodi |

!!! tip "Regola data transfer GCP"
    Come AWS, il **traffico in ingresso (ingress) è gratuito**. Il traffico in uscita verso Internet (egress) è a pagamento. Il traffico tra VM nella stessa zona tramite rete interna è gratuito; tra zone della stessa regione ha un costo ridotto; tra regioni costa di più.

---

## Modelli di Pricing — Compute Engine

### On-Demand (Pay-as-you-go)

- Fatturazione al **secondo**, con minimo di 1 minuto
- Nessun impegno — massima flessibilità
- Prezzo più alto per unità

```bash
# Specifiche di un machine type (il prezzo NON è nell'output: usare Pricing Calculator o Cloud Billing Catalog API)
gcloud compute machine-types describe e2-standard-4 \
    --zone=europe-west8-b

# Listare tutti i machine type disponibili in una zona
gcloud compute machine-types list \
    --filter="zone:europe-west8-b" \
    --format="table(name,guestCpus,memoryMb)"
```

### Sustained Use Discounts (SUD) — Automatici

I **SUD** sono sconti automatici che GCP applica **senza azioni da parte dell'utente** quando una VM viene usata per una certa percentuale del mese di fatturazione:

Esempio per la famiglia **N1** (lo sconto massimo è il più alto):

| Percentuale di utilizzo mensile | Sconto effettivo |
|---------------------------------|-----------------|
| 25% del mese | ~0% |
| 50% del mese | ~10% |
| 75% del mese | ~20% |
| 100% del mese (sempre accesa) | **~30%** |

**Caratteristiche SUD:**
- Applicati automaticamente — nessuna configurazione necessaria
- Valgono solo per famiglie "legacy": N1 e M1/M2 (fino a ~30%), N2, N2D, C2, C2D (fino a ~20%); si applicano anche ai nodi GKE perché sono VM Compute Engine
- **Non si applicano** a: E2, famiglie di nuova generazione (es. C3, N4), Spot VM, Preemptible VM, App Engine flexible, Cloud SQL
<!-- REVIEW: verificare elenco famiglie con SUD e percentuali massime su cloud.google.com/compute/docs/sustained-use-discounts -->
- Il contatore SUD aggrega l'uso per **famiglia di macchine e regione** (non per singola istanza): cambiare dimensione nella stessa famiglia non azzera lo sconto
- GCP calcola l'utilizzo per **tipo di macchina** nella stessa regione — se cambi tipo ma stai nella stessa famiglia, il contatore SUD può accumularsi

!!! note "SUD vs Reserved Instances AWS"
    I SUD sono molto più semplici delle Reserved Instances AWS: non c'è nulla da acquistare o configurare. Il trade-off è che il massimo sconto (30%) è inferiore alle RI AWS (fino a 72%). Per sconti maggiori, usare i CUD.

### Committed Use Discounts (CUD)

I **CUD** richiedono un impegno contrattuale di 1 o 3 anni su una quantità di risorse, in cambio di sconti significativi:

| Risorsa | Sconto 1 anno | Sconto 3 anni |
|---------|--------------|--------------|
| vCPU generale (N1, N2, N2D) | 37% | 55% |
| RAM generale | 37% | 55% |
| vCPU compute-optimized (C2, C2D) | 37% | 55% |
| vCPU memory-optimized (M1, M2) | 41% | 63% |
| GPU (A100, V100) | 40% | 55% |

<!-- REVIEW: verificare percentuali CUD (in particolare memory-optimized 3 anni e GPU) e la migrazione ai Compute Flexible CUD multi-price (2025-2026) -->

I **Flexible CUD** (spend-based) coprono la spesa Compute Engine su più famiglie e regioni con sconti inferiori ai resource-based, ma senza vincolo di macchina.

**Tipi di CUD:**

- **Resource-based CUD** (classico): impegno su quantità di vCPU e RAM per una region specifica. Adatto quando conosci la baseline della tua infrastruttura.
- **Spend-based CUD**: impegno su spesa oraria ($/ora) per servizi specifici (Cloud Run, Cloud SQL). Più flessibile — non vincola a instance type specifici.

```bash
# Creare un CUD resource-based (1 anno, 10 vCPU N1, europe-west8)
gcloud compute commitments create my-commitment-prod \
    --plan=12-month \
    --region=europe-west8 \
    --resources=vcpu=10,memory=40GB

# Listare i CUD attivi
gcloud compute commitments list \
    --filter="region:europe-west8" \
    --format="table(name,plan,status,startTimestamp,endTimestamp)"

# L'utilizzo dei CUD si verifica in Billing Console → Committed use discounts
# o nel billing export (vedi Troubleshooting, Scenario 3)
```

!!! warning "CUD non rimborsabili"
    I CUD sono impegni vincolanti — una volta acquistati non possono essere cancellati o rimborsati. Analizzare l'utilizzo storico per almeno 30-60 giorni prima di acquistare. Usare il **Recommender API** (vedi sezione strumenti) per suggerimenti automatici.

### Spot VM e Preemptible VM

GCP offre due varianti di VM a basso costo basate sulla capacità non utilizzata:

| Caratteristica | Preemptible VM | Spot VM |
|----------------|---------------|---------|
| Disponibilità | Prodotto legacy | Prodotto corrente (sostituisce Preemptible) |
| Sconto | Fino a 91% vs On-Demand | Fino a 91% vs On-Demand |
| Durata massima | 24 ore (forza stop) | Nessun limite di durata |
| Interruzione | Sì — 30 secondi di preavviso | Sì — 30 secondi di preavviso |
| Availability | Non garantita | Non garantita |

```bash
# Creare una Spot VM
gcloud compute instances create my-spot-vm \
    --zone=europe-west8-b \
    --machine-type=n2-standard-4 \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --provisioning-model=SPOT \
    --instance-termination-action=STOP

# Instance template Spot (base per un MIG; il fallback On-Demand si ottiene
# con un secondo MIG/node pool on-demand, non con questo template)
gcloud compute instance-templates create spot-template \
    --machine-type=n2-standard-4 \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --provisioning-model=SPOT \
    --instance-termination-action=STOP

# Verificare le interruzioni recenti
gcloud logging read \
    'resource.type="gce_instance" AND protoPayload.methodName="compute.instances.preempted"' \
    --limit=10
```

**Use case ideali Spot VM:**
- Batch processing, data pipelines, ETL
- ML training (con checkpoint frequenti)
- CI/CD runner, test automatizzati
- Rendering, simulazioni

!!! tip "Gestire le interruzioni Spot"
    Configurare sempre un **termination handler** nel OS per fare cleanup (salvare stato, drainare connessioni). In GKE, usare `cluster-autoscaler` con node pool spot + node pool on-demand come fallback per workload critici.

### E2 Series — Shared-core e Cost-optimized

Le VM **E2** sono la famiglia più economica per workload general-purpose con utilizzo CPU variabile:

- Fino a **31% più economiche** delle N1 equivalenti
- Usano **dynamic resource sharing** — non hanno SUD ma hanno un prezzo base già basso
- Disponibili anche in **e2-micro** e **e2-small** (shared-core, per workload leggeri)

```bash
# VM e2-micro (inclusa nel Free Tier GCP)
gcloud compute instances create my-free-tier-vm \
    --zone=us-east1-b \
    --machine-type=e2-micro \
    --image-family=debian-12 \
    --image-project=debian-cloud
```

---

## Pricing BigQuery

BigQuery ha un modello di pricing **duale** — si può scegliere tra:

### On-Demand (per query)

- Si paga per i **byte processati** dalla query: **$6.25 per TB** (primi 1TB/mese gratuiti)
- Semplice, senza impegni — adatto per workload variabili o esplorativi
- **Storage separato**: $0.02/GB/mese (active storage) + $0.01/GB/mese (long-term storage, dati non modificati per 90+ giorni)

```sql
-- Stimare i byte processati prima di eseguire (dry run)
-- In Console: attivare "Job information" prima di eseguire

-- Via CLI con dry-run
bq query --dry_run --use_legacy_sql=false \
    'SELECT * FROM `bigquery-public-data.usa_names.usa_1910_2013` LIMIT 1000'
```

```bash
# Impostare un limite di byte per query (protezione da query costose)
bq query \
    --maximum_bytes_billed=1073741824 \
    --use_legacy_sql=false \
    'SELECT state, SUM(number) FROM `bigquery-public-data.usa_names.usa_1910_2013` GROUP BY state'
```

### Capacity-based (slot)

- Si acquistano **slot** (unità di compute BigQuery) — ogni slot è un'unità di elaborazione parallela
- **BigQuery Edition** (modello corrente, sostituisce flat-rate): slot su base oraria con auto-scaling

| Edition | Fatturazione | Use case |
|---------|-------------|---------|
| **Standard** | Slot-ora, solo autoscaling (nessun commitment) | Workload standard, dev/test |
| **Enterprise** | Slot-ora (autoscaling) + commitment 1/3 anni opzionali | Feature enterprise, governance, BI Engine |
| **Enterprise Plus** | Come Enterprise | Workload mission-critical, requisiti di compliance/DR avanzati |

Gli slot autoscalati sono fatturati per slot-ora con incrementi di 50 slot; una **baseline** opzionale riserva slot sempre attivi.
<!-- REVIEW: verificare incrementi autoscaling, minimi e feature per edition su cloud.google.com/bigquery/docs/editions-intro -->

Perché scegliere capacity: il costo diventa prevedibile e limitato dagli slot, invece di crescere con i byte scansionati.

!!! note "On-demand vs Slot: quando scegliere"
    **On-demand**: team di analisi con query ad-hoc, poche query al giorno, difficile prevedere il volume.
    **Slot (Capacity-based)**: pipeline di produzione con query frequenti e prevedibili, costo mensile BigQuery > ~$2000-3000 on-demand.

---

## Struttura Billing Account

```
Organization GCP
│
├── Billing Account "Produzione"  (es. 01A2B3-C4D5E6-F7G8H9)
│   ├── project-prod-api        → €X / mese
│   ├── project-prod-data       → €Y / mese
│   └── project-prod-infra      → €Z / mese
│
└── Billing Account "Sviluppo"
    ├── project-dev-api         → €A / mese
    └── project-staging-api     → €B / mese
```

**Billing Account:**
- Entità che raccoglie e paga le fatture GCP
- Collegato a un metodo di pagamento (carta, bonifico, invoice)
- Può coprire N project — un project ha esattamente 1 billing account
- In un'Organization: i ruoli `billing.admin` e `billing.viewer` controllano l'accesso

```bash
# Listare i billing account accessibili
gcloud billing accounts list \
    --format="table(name,displayName,open,masterBillingAccount)"

# Verificare il billing account di un project
gcloud billing projects describe PROJECT_ID \
    --format="table(projectId,billingAccountName,billingEnabled)"

# Collegare un project a un billing account
gcloud billing projects link PROJECT_ID \
    --billing-account=BILLING_ACCOUNT_ID

# Scollegare un project dal billing (disabilita tutti i servizi a pagamento)
gcloud billing projects unlink PROJECT_ID
```

!!! warning "Project senza Billing Account"
    Un project non collegato a un billing account non può usare servizi a pagamento. Le risorse esistenti vengono sospese dopo un periodo di grazia. Questo può causare interruzioni del servizio se il billing account scade o viene scollegato accidentalmente.

---

## Budget e Alert

I **Budget** GCP permettono di impostare soglie di spesa e ricevere notifiche via email o Pub/Sub quando vengono superate.

### Creare un Budget

```bash
# Creare un budget mensile di 500€ con alert a 50%, 80%, 100%
#   (percent è una frazione: 0.5 = 50%, 1.0 = 100%)
gcloud billing budgets create \
    --billing-account=BILLING_ACCOUNT_ID \
    --display-name="Budget Produzione Mensile" \
    --budget-amount=500EUR \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.8 \
    --threshold-rule=percent=1.0 \
    --threshold-rule=percent=1.0,basis=forecasted-spend

# Creare un budget filtrato su un singolo project
gcloud billing budgets create \
    --billing-account=BILLING_ACCOUNT_ID \
    --display-name="Budget project-prod-api" \
    --filter-projects=projects/PROJECT_NUMBER \
    --budget-amount=200EUR \
    --threshold-rule=percent=0.9

# Listare i budget configurati
gcloud billing budgets list \
    --billing-account=BILLING_ACCOUNT_ID \
    --format="table(name,displayName,amount.specifiedAmount.units,amount.specifiedAmount.currencyCode)"
```

### Budget con Notifica Pub/Sub

Per integrazioni avanzate (es. disabilitare automaticamente le risorse al superamento del budget):

```bash
# Creare un topic Pub/Sub per le notifiche budget
gcloud pubsub topics create billing-alerts

# Aggiornare il budget per notificare su Pub/Sub
gcloud billing budgets update BUDGET_ID \
    --billing-account=BILLING_ACCOUNT_ID \
    --notifications-rule-pubsub-topic=projects/PROJECT_ID/topics/billing-alerts
```

```python
# Cloud Function per disabilitare la billing al superamento budget
# (pattern comune per ambienti di sviluppo)
import base64
import json
from googleapiclient import discovery

# Il messaggio del budget NON contiene il project id: il budget deve essere
# filtrato su un solo project, che la function conosce per configurazione.
PROJECT_ID = "my-dev-project"

def disable_billing_on_budget_exceed(data, context):
    """Disabilita billing su un project quando il budget è superato."""
    pubsub_data = json.loads(base64.b64decode(data['data']).decode('utf-8'))

    cost_amount = float(pubsub_data.get('costAmount', 0))
    budget_amount = float(pubsub_data.get('budgetAmount', 0))

    if cost_amount >= budget_amount:
        project_id = PROJECT_ID
        billing = discovery.build('cloudbilling', 'v1')
        billing.projects().updateBillingInfo(
            name=f'projects/{project_id}',
            body={'billingAccountName': ''}  # scollegare billing
        ).execute()
```

!!! warning "Budget Alert ≠ Blocco automatico"
    Per default, i budget GCP inviano solo **notifiche** — non bloccano automaticamente la spesa. Per bloccare automaticamente usare il pattern Pub/Sub + Cloud Function mostrato sopra. Usare con cautela in produzione. Le notifiche budget hanno latenza (i dati di costo arrivano con ritardo): la spesa può superare la soglia prima dello stop. Scollegare il billing non è un limite di spesa garantito.

---

## Esportazione Billing su BigQuery

L'**esportazione billing** è lo strumento principale per analisi FinOps avanzate. GCP esporta automaticamente tutti i dati di costo su una tabella BigQuery in modo continuo.

### Configurazione Export

1. Andare in **Billing Console** → Billing Export → BigQuery Export
2. Creare un dataset BigQuery dedicato (es. `billing_export`)
3. Abilitare:
   - **Standard usage cost** — costi per risorsa, label, project (granularità: giornaliera)
   - **Detailed usage cost** — aggiunge resource-level details (VM specifica, disco specifico)
   - **Pricing data** — tabella separata con listino prezzi GCP

```bash
# Creare il dataset per l'export billing
bq mk \
    --dataset \
    --location=EU \
    --description="Dataset per export billing GCP" \
    PROJECT_ID:billing_export
```

### Query Analisi Costi

```sql
-- Top 10 project per costo nel mese corrente
SELECT
    project.id AS project_id,
    project.name AS project_name,
    ROUND(SUM(cost), 2) AS total_cost,
    currency
FROM `PROJECT_ID.billing_export.gcp_billing_export_v1_*`
WHERE
    DATE(_PARTITIONTIME) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
GROUP BY 1, 2, 4
ORDER BY total_cost DESC
LIMIT 10;

-- Costi per servizio e SKU nel mese corrente
SELECT
    service.description AS service,
    sku.description AS sku,
    ROUND(SUM(cost), 4) AS cost,
    currency,
    SUM(usage.amount) AS usage_amount,
    usage.unit
FROM `PROJECT_ID.billing_export.gcp_billing_export_v1_*`
WHERE
    DATE(_PARTITIONTIME) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
    AND cost > 0
GROUP BY 1, 2, 4, 6
ORDER BY cost DESC
LIMIT 20;

-- Costi per label (es. environment=prod)
SELECT
    label.value AS environment,
    service.description AS service,
    ROUND(SUM(cost), 2) AS total_cost
FROM `PROJECT_ID.billing_export.gcp_billing_export_v1_*`,
UNNEST(labels) AS label
WHERE
    label.key = 'environment'
    AND DATE(_PARTITIONTIME) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
GROUP BY 1, 2
ORDER BY total_cost DESC;
```

---

## Strumenti di Gestione Costi

### Google Cloud Pricing Calculator

- Stima costi **prima** di creare risorse
- Supporta tutti i servizi GCP con configurazioni dettagliate
- Genera stime esportabili e condivisibili

### Cost Table e Cost Breakdown (Console Billing)

```
Billing Console → Reports
```
- Visualizzazione interattiva della spesa per: project, servizio, SKU, regione, label
- Filtri temporali (giornaliero, settimanale, mensile)
- Confronto con periodi precedenti
- **Forecasting** — proiezione spesa mensile basata sul trend

### Recommender API — CUD e Rightsizing

GCP ha un sistema di raccomandazioni proattive via **Recommender API**:

```bash
# Vedere le raccomandazioni CUD (Committed Use Discounts)
gcloud recommender recommendations list \
    --project=PROJECT_ID \
    --location=europe-west8 \
    --recommender=google.compute.commitment.UsageCommitmentRecommender \
    --format="table(name,stateInfo.state,primaryImpact.costProjection.cost.units)"

# Vedere le raccomandazioni di rightsizing VM
gcloud recommender recommendations list \
    --project=PROJECT_ID \
    --location=europe-west8-b \
    --recommender=google.compute.instance.MachineTypeRecommender \
    --format="table(name,description,stateInfo.state)"

# Marcare una raccomandazione come "claimed" (in lavorazione): NON la applica,
# l'intervento resta manuale. Dopo: mark-succeeded / mark-failed
gcloud recommender recommendations mark-claimed \
    projects/PROJECT_ID/locations/europe-west8-b/recommenders/google.compute.instance.MachineTypeRecommender/recommendations/RECOMMENDATION_ID \
    --etag=ETAG
```

### Labels per Cost Allocation

I **Labels** in GCP sono il meccanismo principale per attribuire i costi a team, progetti o ambienti:

```bash
# Aggiungere labels a una VM
gcloud compute instances add-labels my-vm \
    --zone=europe-west8-b \
    --labels=environment=prod,team=backend,cost-center=123

# Aggiungere labels a un bucket Cloud Storage
gcloud storage buckets update gs://my-bucket \
    --update-labels=environment=prod,team=data

# Aggiungere labels a un cluster GKE
gcloud container clusters update my-cluster \
    --region=europe-west8 \
    --update-labels=environment=prod,team=platform
```

!!! tip "Labels obbligatori: enforcement"
    Non esiste un constraint built-in di Organization Policy che imponga label obbligatorie (`constraints/gcp.resourceLocations` limita solo le **regioni**). Opzioni: **custom organization constraint** (CEL) sui tipi di risorsa supportati, oppure policy-as-code in CI sul Terraform (es. OPA/Conftest, `google_*` con `default_labels` nel provider). Così ogni risorsa è attribuita nel billing export.

---

## Free Tier e Free Trial

### Free Trial (nuovi account)

- **$300 di crediti gratuiti** validi per **90 giorni** al signup
- Utilizzabili su quasi tutti i servizi GCP
- Le risorse vengono sospese alla scadenza (non eliminate automaticamente)

### Always Free (permanente)

Risorse sempre gratuite entro i limiti mensili:

| Servizio | Limite Free |
|---------|------------|
| **Compute Engine** | 1 × e2-micro VM (us-east1, us-west1, us-central1) |
| **Cloud Storage** | 5 GB nella regione us |
| **Cloud Functions** | 2M invocazioni/mese + 400K GB-sec |
| **Cloud Run** | 2M request/mese + 180K vCPU-sec + 360K GiB-sec |
| **BigQuery** | 10 GB storage + 1 TB query/mese |
| **Cloud Build** | Minuti build mensili gratuiti (e2-standard-2) <!-- REVIEW: verificare quota corrente (storicamente 120 min/giorno, poi 2.500 min/mese) --> |
| **Pub/Sub** | 10 GB messaggi/mese |
| **Cloud Logging** | 50 GB log/mese |
| **Secret Manager** | 6 versioni attive + 10K accessi/mese |

!!! note "Free tier regionale"
    La VM e2-micro è free solo nelle regioni us-east1, us-west1 e us-central1. Se la crei in europe-west8, verrà addebitata normalmente.

---

## Confronto con AWS e Azure

| Concetto | GCP | AWS | Azure |
|----------|-----|-----|-------|
| Sconto automatico utilizzo | **SUD** (automatico, fino a 30%) | Nessuno | Nessuno |
| Sconto con impegno | **CUD** 1/3yr (37-63%) | Reserved Instances / Savings Plans (fino a 72%) | Reserved VM (fino a 72%) |
| VM interrompibili | **Spot VM** (fino a 91%) | Spot Instances (fino a 90%) | Spot VMs (fino a 90%) |
| Free tier permanente | Sì (e2-micro, BigQuery 1TB, ecc.) | Sì (t2.micro, Lambda 1M req, ecc.) | Sì (B1S VM 12 mesi, Functions 1M, ecc.) |
| Free trial | $300 per 90 giorni | Free Plan per nuovi account (crediti fino a ~$200, 6 mesi) + Always Free <!-- REVIEW: verificare condizioni attuali AWS Free Plan --> | $200 per 30 giorni |
| Billing export nativo | BigQuery (granulare) | S3 + CUR (granulare) | Storage Account (granulare) |
| Cost management tool | Billing Console + Recommender | Cost Explorer + Trusted Advisor | Azure Cost Management |
| Impegno minimo CUD | vCPU/RAM (resource-based) | Istanza specifica o spesa $/hr | vCPU/RAM (più flessibile) |

!!! note "Vantaggio GCP: SUD automatici"
    Il principale vantaggio del pricing GCP vs AWS è che i SUD **non richiedono alcuna pianificazione** — si applicano automaticamente. In AWS, lo stesso livello di sconto richiede l'acquisto anticipato di Reserved Instances o Savings Plans.

---

## Best Practices

!!! tip "Usare e2 per workload burstable"
    Le VM **e2-medium** e **e2-standard** sono spesso la scelta più cost-effective per workload con utilizzo CPU variabile. Non hanno SUD ma il prezzo base è già ottimizzato per il dynamic sharing.

!!! tip "CUD su baseline, Spot per burst"
    Pattern comune: acquistare CUD per la capacità compute baseline stabile (es. 80% del cluster), usare Spot VM per gestire i picchi. Questo massimizza gli sconti senza rischiare interruzioni per i workload core.

!!! warning "Monitorare egress network"
    Il costo di rete è spesso sottovalutato. Il traffico da GCP verso Internet e tra regioni può diventare significativo. Analizzare regolarmente il billing export filtrando `service.description = "Networking"`.

!!! tip "Labels fin dal primo giorno"
    Applicare labels `environment`, `team`, `cost-center` a **tutte** le risorse fin dalla creazione. Retroattivamente è difficile: le risorse già create possono essere etichettate, ma i dati storici nel billing export non vengono aggiornati retroattivamente.

- **Abilitare BigQuery billing export subito** dopo la creazione del billing account — i dati storici non vengono caricati retroattivamente
- **Usare il Recommender API** per ricevere suggerimenti CUD e rightsizing prima di fare acquisti manuali
- **Impostare budget alert a 80% e 100%** su ogni billing account come safety net
- **Separare ambienti su billing account distinti** per una visibilità dei costi chiara e per impedire che costi di sviluppo impattino budget di produzione
- **Usare committed use discounts per Cloud SQL e GKE** oltre che per Compute Engine — spesso dimenticati

---

## Troubleshooting

### Scenario 1 — Spike di costi imprevisto

**Sintomo:** La spesa mensile aumenta bruscamente; ricevi un alert di budget.

**Causa:** Risorsa creata per errore (NAT Gateway, Load Balancer, VM non spenta), egress data transfer inatteso, o BigQuery query senza limite di byte.

**Soluzione:**
```bash
# 1. Identificare il servizio responsabile via billing export
bq query --use_legacy_sql=false '
SELECT
    service.description,
    ROUND(SUM(cost), 2) AS cost,
    currency
FROM `PROJECT_ID.billing_export.gcp_billing_export_v1_*`
WHERE DATE(_PARTITIONTIME) = CURRENT_DATE() - 1
GROUP BY 1, 3
ORDER BY cost DESC
LIMIT 10'

# 2. Verificare NAT Gateway attivi (spesso dimenticati dopo test)
gcloud compute routers list --format="table(name,region,network)"
gcloud compute routers get-nat-mapping-info ROUTER_NAME \
    --region=REGION

# 3. Verificare Load Balancer non necessari
gcloud compute forwarding-rules list \
    --format="table(name,region,IPAddress,target)"

# 4. Verificare VM accese in tutte le regioni
gcloud compute instances list \
    --format="table(name,zone,status,machineType)" \
    --filter="status=RUNNING"
```

---

### Scenario 2 — Labels non appaiono nel billing export

**Sintomo:** Le query sul billing export filtrate per label non restituiscono risultati anche se le risorse hanno le label corrette.

**Causa:** Le label vengono propagate al billing export con un ritardo di **24-48 ore**. Oppure la label è stata aggiunta dopo la creazione della risorsa e i dati storici non vengono aggiornati.

**Soluzione:**
```bash
# Verificare che la label sia presente sulla risorsa
gcloud compute instances describe my-vm \
    --zone=europe-west8-b \
    --format="yaml(labels)"

# Aggiungere label mancante
gcloud compute instances add-labels my-vm \
    --zone=europe-west8-b \
    --labels=environment=prod

# Attendere 24-48h per la propagazione nel billing export
# I dati storici PRE-label non verranno aggiornati retroattivamente
```

---

### Scenario 3 — CUD non applicati alle VM

**Sintomo:** Le VM continuano a essere fatturate a tariffa On-Demand nonostante l'acquisto di Committed Use Discounts.

**Causa:** Mismatch su regione, machine type family, o il CUD è già esaurito da altre VM. I CUD resource-based si applicano a livello di **regione** — un CUD in europe-west1 non copre VM in europe-west8.

**Soluzione:**
```bash
# Verificare i CUD acquistati e la loro region
gcloud compute commitments list \
    --format="table(name,region,plan,status,endTimestamp,resources[])"

# Verificare l'utilizzo dei CUD (nel billing export)
bq query --use_legacy_sql=false '
SELECT
    usage_start_time,
    sku.description,
    credit.name AS credit_type,
    ROUND(SUM(credit.amount), 4) AS credit_amount
FROM `PROJECT_ID.billing_export.gcp_billing_export_v1_*`,
UNNEST(credits) AS credit
WHERE
    credit.name LIKE "%Committed%"
    AND DATE(_PARTITIONTIME) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
GROUP BY 1, 2, 3
ORDER BY 1 DESC'
```

---

### Scenario 4 — Billing account disabilitato o scollegato

**Sintomo:** I servizi GCP di un project smettono di funzionare; errore "Billing account disabled" o "project not linked to billing account".

**Causa:** Carta di credito scaduta, superamento del limite di credito, o accidentale scollegamento del billing account.

**Soluzione:**
```bash
# Verificare lo stato del billing account
gcloud billing accounts list \
    --format="table(name,displayName,open)"

# Verificare il billing del project
gcloud billing projects describe PROJECT_ID

# Ricollegare il billing account
gcloud billing projects link PROJECT_ID \
    --billing-account=BILLING_ACCOUNT_ID

# Se il billing account è chiuso (open=false), aprire la console Billing
# per risolvere il problema di pagamento
```

!!! warning "Dati non persi ma servizi sospesi"
    Quando un project perde il billing, le risorse vengono **sospese** (non eliminate). I dati rimangono per un periodo limitato, ma risorse e project senza billing possono essere eliminati in via definitiva. Ripristinare il billing il prima possibile.
    <!-- REVIEW: verificare tempistiche esatte di cancellazione delle risorse dopo disabilitazione billing -->
---

## Relazioni

??? info "GCP Panoramica — Contesto billing nella gerarchia risorse"
    Il billing si integra con la gerarchia Organization → Folder → Project. Un billing account copre più project; le Organization Policy possono forzare l'uso di billing account approvati.

    **Approfondimento →** [Panoramica GCP](panoramica.md)

??? info "BigQuery — Pricing on-demand vs slot"
    BigQuery ha un modello di pricing specifico (query-based vs capacity-based) che richiede un'analisi separata rispetto al pricing compute.

    **Approfondimento →** [BigQuery](../dati/bigquery.md)

??? info "AWS Billing — Confronto modelli pricing"
    AWS usa Reserved Instances e Savings Plans al posto di SUD/CUD. I meccanismi sono simili ma richiedono più pianificazione manuale rispetto ai SUD automatici GCP.

    **Approfondimento →** [Billing & Pricing AWS](../../aws/fondamentali/billing-pricing.md)

---

## Riferimenti

- [Google Cloud Billing Documentation](https://cloud.google.com/billing/docs)
- [GCP Pricing Calculator](https://cloud.google.com/products/calculator)
- [Sustained Use Discounts](https://cloud.google.com/compute/docs/sustained-use-discounts)
- [Committed Use Discounts](https://cloud.google.com/compute/docs/instances/signing-up-committed-use-discounts)
- [Spot VMs](https://cloud.google.com/compute/docs/instances/spot)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [Cloud Billing Budget API](https://cloud.google.com/billing/docs/how-to/budgets)
- [Billing Export to BigQuery](https://cloud.google.com/billing/docs/how-to/export-data-bigquery)
- [Recommender API](https://cloud.google.com/recommender/docs)
- [GCP Always Free](https://cloud.google.com/free/docs/free-cloud-features)
