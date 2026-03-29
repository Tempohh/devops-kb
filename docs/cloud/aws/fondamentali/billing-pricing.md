---
title: "Billing & Pricing AWS"
slug: billing-pricing
category: cloud
tags: [aws, billing, pricing, cost-explorer, budgets, savings-plans, reserved-instances, spot, trusted-advisor, cost-optimization, free-tier]
search_keywords: [AWS billing, AWS pricing, AWS Cost Explorer, AWS Budgets, Reserved Instances, Savings Plans, Spot Instances, AWS Free Tier, pay-as-you-go, cost allocation tags, Trusted Advisor, Compute Optimizer, Total Cost of Ownership, TCO Calculator, AWS Pricing Calculator, cost management, FinOps, AWS Organizations billing]
parent: cloud/aws/fondamentali/_index
related: [cloud/aws/fondamentali/well-architected, cloud/aws/iam/organizations]
official_docs: https://aws.amazon.com/pricing/
status: complete
difficulty: beginner
last_updated: 2026-03-28
---

# Billing & Pricing AWS

## Principi di Pricing AWS

AWS usa **3 driver fondamentali** di costo:

| Driver | Esempi |
|--------|--------|
| **Compute** | EC2 ore/secondi, Lambda invocazioni+durata, ECS/Fargate vCPU+memoria |
| **Storage** | S3 GB/mese, EBS GB provisioned, EFS GB usato |
| **Data Transfer** | **Ingress: gratuito**. Egress verso Internet: a pagamento. Inter-Region: a pagamento. Intra-Region tra AZ: a pagamento (ridotto). Stessa AZ: gratuito. |

!!! tip "Regola data transfer"
    Dati che **entrano** in AWS (ingress) sono sempre gratuiti. Dati che **escono** (egress) costano. Questo incentiva ad architetture che processano i dati vicino alla source.

---

## Modelli di Pricing — EC2

### On-Demand

- Paga per **secondo** (Linux) o per **ora** (Windows)
- Zero impegno, massima flessibilità
- Prezzo più alto per unità — adatto per carichi variabili o testing

### Reserved Instances (RI)

- Impegno **1 anno** o **3 anni** → sconto fino a **72%** vs On-Demand
- Tipi di pagamento: All Upfront (max sconto), Partial Upfront, No Upfront
- **Standard RI**: fixed instance type/family/OS/Region
- **Convertible RI**: può cambiare instance family/OS — sconto minore (~54%)
- **Scheduled RI**: finestre orarie specifiche (deprecato, sostituito da Savings Plans)
- RI non usate possono essere **vendute nel Reserved Instance Marketplace**

### Savings Plans

Più flessibili delle RI — impegno su **spesa $/ora** per 1 o 3 anni:

| Tipo | Flessibilità | Sconto |
|------|-------------|--------|
| **Compute Savings Plans** | EC2 + Lambda + Fargate, qualsiasi Region/family/OS | ~66% |
| **EC2 Instance Savings Plans** | EC2 specifica family + Region | ~72% |
| **SageMaker Savings Plans** | SageMaker instance types | ~64% |

!!! note "Savings Plans vs Reserved Instances"
    Per nuovi deployment: preferire **Savings Plans** (più flessibili). RI rimane conveniente per workload stabili con instance type fisso (es. RDS).

### Spot Instances

- Capacità EC2 **non utilizzata** da AWS venduta a -60/-90% vs On-Demand
- **Interruption notice**: 2 minuti prima dello stop
- Adatte per: batch, rendering, ML training, big data, CI/CD
- **Spot Fleet**: combinazione di instance type + On-Demand per target capacity
- **Spot Interruption**: l'istanza viene terminata se AWS riprende la capacità

### Dedicated Hosts

- Server fisico **dedicato** al tuo account
- Necessario per: BYOL (Bring Your Own License — SQL Server, Oracle), compliance (multi-tenant non consentito)
- Prezzo più alto — si paga per host, non per istanza

### Dedicated Instances

- Istanze girano su hardware fisico **non condiviso** con altri account
- Più economiche dei Dedicated Hosts ma meno controllo

---

## Confronto Modelli Pricing EC2

| Modello | Sconto vs On-Demand | Impegno | Interruzioni | Use Case |
|---------|---------------------|---------|--------------|---------|
| On-Demand | 0% | Nessuno | No | Dev, test, carichi spike |
| Reserved (1yr) | ~40% | 1 anno | No | Produzione stabile |
| Reserved (3yr) | ~60-72% | 3 anni | No | DB, infrastruttura stabile |
| Savings Plans | ~66% | 1-3 anni | No | Flessibilità multi-servizio |
| Spot | ~60-90% | Nessuno | Sì (2 min notice) | Batch, ML, resilient apps |
| Dedicated Host | — (premium) | On-demand/1-3yr | No | BYOL, compliance |

---

## AWS Free Tier

AWS offre un **Free Tier** per esplorare i servizi — 3 tipologie:

| Tipo | Durata | Esempio |
|------|--------|---------|
| **Always Free** | Per sempre | Lambda 1M invocazioni/mese, DynamoDB 25GB, CloudWatch basic |
| **12 Months Free** | 12 mesi dal signup | EC2 t2.micro 750h/mese, S3 5GB, RDS 750h/mese db.t2/t3.micro |
| **Trial** | Periodo limitato | SageMaker 2 mesi, Amazon Comprehend 3 mesi |

**Servizi sempre gratuiti (selezione):**
- Lambda: 1 milione richieste/mese + 400.000 GB-secondi
- DynamoDB: 25 GB storage + 25 WCU + 25 RCU
- CloudWatch: 10 custom metrics, 5GB log ingestion, 3 dashboards
- AWS CloudFormation: no charge (si paga solo le risorse create)
- IAM: completamente gratuito
- VPC: gratuito (si paga NAT Gateway, VPN, ecc.)

---

## Strumenti di Gestione Costi

### AWS Pricing Calculator

- Stima costi **prima** di creare risorse
- URL: [calculator.aws](https://calculator.aws/)
- Configura servizi, carichi attesi → genera estimate
- Utile per proposte, confronto cloud vs on-premises

### AWS Cost Explorer

```
Console → Billing → Cost Explorer
```
- Visualizza spesa **storica** e previsioni (forecasting a 12 mesi)
- Filtri per: servizio, account, Region, tag, istanza type
- **Savings Plans recommendations** — suggerisce quanto acquistare
- **RI recommendations** — rightsizing RI
- **Granularità**: giornaliera, mensile, oraria (solo ultimi 14 giorni)
- Report personalizzati salvabili

### AWS Budgets

- Definisci **soglie di budget** e ricevi alert
- Tipi di budget:
  - **Cost Budget** — alert quando spesa supera X $
  - **Usage Budget** — alert su utilizzo (es. EC2 ore)
  - **Savings Plans Budget** — coverage/utilization
  - **RI Budget** — coverage/utilization
- Alert via **Email** o **SNS**
- **Budget Actions** — aziona automaticamente (es. Stop EC2, apply IAM policy) al superamento soglia

```bash
# Creare budget via CLI
aws budgets create-budget \
    --account-id 123456789012 \
    --budget '{
        "BudgetName": "Monthly-100",
        "BudgetLimit": {"Amount": "100", "Unit": "USD"},
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST"
    }' \
    --notifications-with-subscribers '[{
        "Notification": {
            "NotificationType": "ACTUAL",
            "ComparisonOperator": "GREATER_THAN",
            "Threshold": 80
        },
        "Subscribers": [{
            "SubscriptionType": "EMAIL",
            "Address": "devops@company.com"
        }]
    }]'
```

### AWS Cost Allocation Tags

- Aggiungere **tag** alle risorse → visualizzare costi per tag in Cost Explorer
- Tipi: **AWS-generated tags** (es. `aws:createdBy`) e **user-defined tags**
- Tag devono essere **attivati** in Billing per apparire nei report (latenza ~24h)
- Best practice: tag obbligatori con Config Rules (es. `Project`, `Team`, `Environment`)

```bash
# Taggare una EC2 instance
aws ec2 create-tags \
    --resources i-1234567890abcdef0 \
    --tags Key=Project,Value=myapp Key=Team,Value=platform Key=Environment,Value=prod
```

### AWS Cost and Usage Report (CUR)

- Report **granulare** (per risorsa, per ora) esportato in S3
- Formato CSV/Parquet — analizzabile con Athena, QuickSight, Redshift
- Standard de-facto per FinOps (Financial Operations — gestione finanziaria del cloud) avanzato e multi-account billing

---

## AWS Trusted Advisor

**Trusted Advisor** analizza il tuo account e fornisce raccomandazioni in 5 categorie:

| Categoria | Check Esempio |
|-----------|---------------|
| **Cost Optimization** | Istanze sottoutilizzate, RI inutilizzate, S3 Glacier retrieval |
| **Security** | Security Groups troppo aperti, MFA su root, bucket S3 pubblici |
| **Fault Tolerance** | AZ single point, backup EC2/RDS, Route 53 health checks |
| **Performance** | EC2 con alta CPU, CloudFront ottimizzazioni |
| **Service Limits** | Avvisi quando ci si avvicina ai limiti AWS |
| **Service Quotas** (aggiunto 2023) | Monitoraggio quote servizi |

**Livelli di accesso:**

| Piano Support | Check Disponibili |
|---------------|-------------------|
| Basic/Developer | 7 security check fondamentali |
| Business/Enterprise | Tutti i check (oltre 500) |

```bash
# Trusted Advisor disponibile via Console e CLI
aws support describe-trusted-advisor-checks --language en

# Refresh di uno specifico check
aws support refresh-trusted-advisor-check --check-id <checkId>
```

---

## AWS Compute Optimizer

- Analizza **metriche CloudWatch** reali delle risorse
- Raccomanda **rightsizing** basato su utilizzo effettivo
- Supporta: EC2, Auto Scaling Groups, EBS, Lambda, ECS (Fargate), RDS
- Stima risparmio potenziale per ogni raccomandazione
- Classificazione: Over-provisioned / Under-provisioned / Optimized

```bash
# Ottenere raccomandazioni EC2
aws compute-optimizer get-ec2-instance-recommendations \
    --account-ids 123456789012 \
    --filters name=Finding,values=Overprovisioned
```

---

## Support Plans

| Piano | Prezzo | Technical Support | Response Time (Critical) |
|-------|--------|-------------------|-----------------------------|
| **Basic** | Gratuito | Nessuno | N/A |
| **Developer** | $29/mese o 3% | Business hours email | 12h |
| **Business** | $100/mese o 10/7/3% | 24/7 phone/email/chat | 1h |
| **Enterprise On-Ramp** | $5.500/mese o 10/7/3% | 24/7 + pool di TAM (Technical Account Manager) | 30 min |
| **Enterprise** | $15.000/mese o 10/7/3/1% | 24/7 + TAM dedicato | 15 min |

**Nota:** la percentuale è applicata sulla spesa mensile AWS (es. Business = max(100$, 10% di spesa fino a 10K, 7% da 10K a 80K, 3% oltre).

**Incluso in tutti i piani:** AWS documentation, whitepapers, forum, Trusted Advisor (basic checks), AWS Personal Health Dashboard.

---

## Total Cost of Ownership (TCO)

**AWS TCO Calculator** (ora integrato nel Pricing Calculator) confronta il costo di:
- **On-premises** (hardware, datacenter, personale, licenze)
- **AWS** (servizi cloud equivalenti)

Fattori considerati nel TCO:
- Hardware + manutenzione (3-5yr refresh cycle)
- Spazio datacenter + energy + cooling
- Networking + bandwidth
- Software licenze (OS, hypervisor, monitoring)
- Personale IT (installazione, gestione, patching)
- Costo opportunità (tempo IT vs innovazione)

---

## Billing Consolidata con AWS Organizations

Con **AWS Organizations** si possono consolidare i costi di più account:

- **Consolidated Billing** — un'unica fattura per tutti gli account
- **Volume discounts** — aggregazione utilizzo → pricing tier più vantaggioso (es. S3)
- **Savings Plans e RI sharing** — un account acquista, tutti ne beneficiano (configurabile)
- **Cost center tagging** — tag obbligatori per ogni account tramite Service Control Policy

---

## Troubleshooting

### Scenario 1 — Spike di costi imprevisto sull'account

**Sintomo:** La spesa mensile aumenta bruscamente; AWS Budgets invia un alert.

**Causa:** Risorsa creata per errore (es. NAT Gateway non rimosso dopo test), egress data transfer inatteso, o istanza lasciata in esecuzione.

**Soluzione:**
1. Aprire Cost Explorer → filtro per servizio → ordinare per costo decrescente
2. Identificare il servizio e la Region responsabile
3. Drilldown sul giorno dello spike → verificare quali risorse sono attive

```bash
# Listar tutte le risorse costose con tag mancanti (possibile risorsa dimenticata)
aws ce get-cost-and-usage \
    --time-period Start=2026-03-01,End=2026-03-28 \
    --granularity MONTHLY \
    --metrics "UnblendedCost" \
    --group-by Type=DIMENSION,Key=SERVICE \
    --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.UnblendedCost.Amount]' \
    --output table

# Verificare NAT Gateway attivi in tutte le Region
aws ec2 describe-nat-gateways --filter Name=state,Values=available \
    --query 'NatGateways[*].[NatGatewayId,VpcId,State]' --output table
```

---

### Scenario 2 — I Cost Allocation Tags non appaiono in Cost Explorer

**Sintomo:** Tag applicati alle risorse non compaiono nei filtri di Cost Explorer o nei report CUR.

**Causa:** I tag non sono stati **attivati** in Billing Management Console; oppure la latenza di propagazione (fino a 24h) non è ancora trascorsa.

**Soluzione:**
1. Andare in Billing Console → Cost Allocation Tags
2. Verificare che il tag sia in stato "Active" (non "Inactive")
3. Attivare il tag se necessario → attendere ~24h per la propagazione

```bash
# Verificare quali tag sono attivi/inattivi
aws ce list-cost-allocation-tags \
    --status Active \
    --query 'CostAllocationTags[*].[TagKey,Status]' --output table

# Non esiste CLI diretta per attivare i tag: operazione da console
# Billing Console → Cost Allocation Tags → seleziona tag → "Activate"
```

---

### Scenario 3 — Saving Plans o RI non applicati alle istanze

**Sintomo:** Le istanze continuano a essere fatturate a tariffa On-Demand nonostante l'acquisto di Reserved Instances o Savings Plans.

**Causa:** Mismatch su Region, instance family, OS, o tenancy. Per le RI Standard il match deve essere esatto; per i Savings Plans il commitment potrebbe essere esaurito da altri servizi.

**Soluzione:**
1. Verificare la **RI/SP Utilization** in Cost Explorer → Savings Plans → Utilization Report
2. Confrontare l'instance type, Region e OS delle istanze con quanto acquistato
3. Considerare la conversione a Convertible RI o l'acquisto di Compute Savings Plans

```bash
# Verificare RI acquistate e loro attributi
aws ec2 describe-reserved-instances \
    --filters Name=state,Values=active \
    --query 'ReservedInstances[*].[ReservedInstancesId,InstanceType,ProductDescription,Scope,State]' \
    --output table

# Verificare utilizzo Savings Plans
aws savingsplans describe-savings-plans \
    --states active \
    --query 'savingsPlans[*].[savingsPlanId,savingsPlanType,commitment,currency,status]' \
    --output table
```

---

### Scenario 4 — AWS Budgets non invia alert nonostante il superamento

**Sintomo:** La spesa supera la soglia configurata ma non arrivano notifiche email o SNS.

**Causa:** L'indirizzo email non è verificato (problema SNS), la soglia è impostata su "Forecasted" invece che "Actual", oppure il budget è stato creato su un account child in Organizations senza permessi.

**Soluzione:**
1. Verificare che l'alert sia di tipo "ACTUAL" (non solo "FORECASTED")
2. Controllare la subscription SNS → la prima email di conferma deve essere accettata
3. In ambienti Organizations: verificare che il management account abbia abilitato il billing access per gli account member

```bash
# Verificare i budget configurati e le soglie
aws budgets describe-budgets \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --query 'Budgets[*].[BudgetName,BudgetLimit.Amount,BudgetType,TimeUnit]' \
    --output table

# Verificare le notifiche associate a un budget
aws budgets describe-notifications-for-budget \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --budget-name "Monthly-100"
```

---

## Riferimenti

- [AWS Pricing](https://aws.amazon.com/pricing/)
- [AWS Pricing Calculator](https://calculator.aws/)
- [AWS Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/)
- [AWS Budgets](https://aws.amazon.com/aws-cost-management/aws-budgets/)
- [Savings Plans](https://aws.amazon.com/savingsplans/)
- [Trusted Advisor](https://aws.amazon.com/premiumsupport/technology/trusted-advisor/)
- [Compute Optimizer](https://aws.amazon.com/compute-optimizer/)
