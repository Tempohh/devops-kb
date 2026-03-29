---
title: "AWS Well-Architected Framework"
slug: well-architected
category: cloud
tags: [aws, well-architected, pillars, reliability, security, performance, cost, sustainability, operational-excellence]
search_keywords: [AWS Well-Architected Framework, WAF, 6 pillars, Operational Excellence, Security pillar, Reliability pillar, Performance Efficiency, Cost Optimization, Sustainability, Well-Architected Tool, WAF review, design principles, tradeoffs]
parent: cloud/aws/fondamentali/_index
related: [cloud/aws/fondamentali/shared-responsibility, cloud/aws/monitoring/cloudwatch, cloud/aws/security/_index]
official_docs: https://aws.amazon.com/architecture/well-architected/
status: complete
difficulty: beginner
last_updated: 2026-03-28
---

# AWS Well-Architected Framework

Il **Well-Architected Framework (WAF)** è la guida di AWS per costruire architetture cloud **sicure, resilienti, efficienti e sostenibili**. Si articola in **6 pilastri** e decine di best practices.

!!! note "CLF-C02"
    Il WAF con i suoi 6 pilastri è sempre presente nell'esame Cloud Practitioner. Saper identificare a quale pilastro appartiene una pratica o un servizio è fondamentale.

---

## I 6 Pilastri

```
Well-Architected Framework — 6 Pillars

  1. Operational      2. Security      3. Reliability
     Excellence
  ┌────────────┐   ┌────────────┐   ┌────────────┐
  │ Operazioni │   │ Sicurezza  │   │  Affidabi- │
  │ automatiz. │   │ a tutti i  │   │  lità e    │
  │ e migliora │   │ livelli    │   │  recovery  │
  │ continue   │   │            │   │            │
  └────────────┘   └────────────┘   └────────────┘

  4. Performance    5. Cost           6. Sustainability
     Efficiency       Optimization
  ┌────────────┐   ┌────────────┐   ┌────────────┐
  │ Risorse    │   │ Eliminare  │   │ Impatto    │
  │ giuste per │   │ sprechi,   │   │ ambientale │
  │ il workload│   │ right-size │   │ minimo     │
  └────────────┘   └────────────┘   └────────────┘
```

---

## 1. Operational Excellence

> *"Run and monitor systems to deliver business value and continually improve supporting processes and procedures."*

**Principi di design:**
- **Operations as code** — infrastruttura e procedure come codice (IaC — Infrastructure as Code)
- **Small, frequent, reversible changes** — deploy incrementali, rollback facile
- **Refine operations procedures frequently** — runbook aggiornati e testati
- **Anticipate failure** — chaos engineering, test di failure
- **Learn from all operational failures** — post-mortem blameless

**Best practices chiave:**
- Usa **CloudFormation/CDK** per infrastruttura come codice
- Usa **AWS Systems Manager** per gestione operativa (patch, runbook, automazione)
- Implementa **CloudWatch Dashboards** e allarmi prima del go-live
- Definisci **KPI** (Key Performance Indicators) operativi misurabili (MTTR, MTTD — Mean Time To Detect, change failure rate)
- Conduci **Game Days** (simulazioni di failure controllate)

**Servizi AWS rilevanti:** CloudFormation, CDK, Systems Manager, CloudWatch, X-Ray, CodePipeline, Config

---

## 2. Security

> *"Protect information, systems, and assets while delivering business value through risk assessments and mitigation strategies."*

**Principi di design:**
- **Implement a strong identity foundation** — IAM, MFA, privilegio minimo
- **Enable traceability** — CloudTrail, CloudWatch Logs, VPC Flow Logs
- **Apply security at all layers** — edge, VPC, subnet, endpoint, OS, applicazione, dati
- **Automate security best practices** — policy as code, Security Hub, Config rules
- **Protect data in transit and at rest** — TLS ovunque, KMS per cifratura
- **Keep people away from data** — accesso diretto ai dati di produzione tramite strumenti, non manuale
- **Prepare for security events** — incident response plan, esercitazioni

**Best practices chiave:**
- MFA obbligatoria per root e utenti privilegiati
- Nessuna credenziale hardcoded — usare IAM Roles + Secrets Manager
- Principio del minimo privilegio in tutte le IAM policies
- Cifratura a riposo (S3 SSE, EBS, RDS) e in transito (TLS, ACM)
- Rotazione automatica dei secrets (Secrets Manager)

**Servizi AWS rilevanti:** IAM, KMS, Secrets Manager, GuardDuty, Security Hub, WAF, Shield, Inspector, Macie, CloudTrail

---

## 3. Reliability

> *"Ensure a workload performs its intended function correctly and consistently when expected to."*

**Principi di design:**
- **Automatically recover from failure** — health checks, auto healing
- **Test recovery procedures** — chaos engineering, simulated failures
- **Scale horizontally to increase aggregate system availability** — molti piccoli componenti invece di uno grande
- **Stop guessing capacity** — auto scaling
- **Manage change in automation** — infrastruttura versionata, deploy automatizzati

**Concetti chiave:**
- **RTO** (Recovery Time Objective) — massimo tempo di downtime tollerabile
- **RPO** (Recovery Point Objective) — massima perdita di dati tollerabile
- **MTTR** (Mean Time To Recovery)
- **MTBF** (Mean Time Between Failures)

**Strategie di DR:**

| Strategia | RTO/RPO | Costo | Descrizione |
|-----------|---------|-------|-------------|
| **Backup & Restore** | Ore | $ | Backup in S3, restore su evento |
| **Pilot Light** | Minuti-Ore | $$ | Core system sempre attivo, scale on failure |
| **Warm Standby** | Minuti | $$$ | Sistema scalato ridotto sempre attivo |
| **Multi-Site Active/Active** | Secondi | $$$$ | Full capacity in più Region |

**Servizi AWS rilevanti:** Auto Scaling, ELB, Route 53 (health checks + failover), RDS Multi-AZ, S3 (11 9s durabilità), CloudWatch, AWS Backup

---

## 4. Performance Efficiency

> *"Use computing resources efficiently to meet system requirements, and maintain that efficiency as demand changes and technologies evolve."*

**Principi di design:**
- **Democratize advanced technologies** — usa servizi managed invece di gestirli tu
- **Go global in minutes** — deploy multi-region per latenza bassa
- **Use serverless architectures** — elimina overhead gestione server
- **Experiment more often** — A/B test di architetture
- **Consider mechanical sympathy** — allinea architettura ai pattern di accesso ai dati

**Best practices chiave:**
- Scegli il tipo di istanza EC2 corretto per il workload (compute/memory/storage optimized)
- Usa **Graviton** (ARM) per rapporto prezzo/performance migliore
- **ElastiCache** per caching — riduce carico su DB
- **CDN (CloudFront)** per contenuti statici — riduce latenza globale
- **DynamoDB** per NoSQL ad alta velocità invece di RDBMS

**Servizi AWS rilevanti:** EC2 (instance types), Lambda, ElastiCache, CloudFront, RDS Read Replicas, DynamoDB, Kinesis, EMR

---

## 5. Cost Optimization

> *"Run systems to deliver business value at the lowest price point."*

**Principi di design:**
- **Implement cloud financial management** — Cost allocation tags, budget alerts
- **Adopt a consumption model** — paga solo ciò che usi
- **Measure overall efficiency** — business value per $ speso
- **Stop spending money on undifferentiated heavy lifting** — managed services
- **Analyze and attribute expenditure** — cost center, team, progetto

**Strumenti di ottimizzazione:**

| Strumento | Scopo |
|-----------|-------|
| **AWS Cost Explorer** | Visualizzare e analizzare spesa storica |
| **AWS Budgets** | Allarmi su soglie di spesa |
| **Cost Allocation Tags** | Attribuire costi a team/progetto |
| **Savings Plans** | Sconti 1-3 anni su Compute (EC2, Lambda, Fargate) |
| **Reserved Instances** | Sconti 1-3 anni su EC2, RDS, ElastiCache |
| **Spot Instances** | EC2 a -90% per workload fault-tolerant |
| **Trusted Advisor** | Raccomandazioni costo, sicurezza, performance |
| **Compute Optimizer** | Rightsizing EC2 basato su metriche reali |

**Modelli di pricing:**
- **On-Demand** — paga per secondo/ora, zero impegno
- **Savings Plans** — -66% su EC2 con impegno spend $/ora per 1-3 anni
- **Reserved Instances** — -72% con impegno 1-3 anni (specifico instance type)
- **Spot Instances** — -90% per EC2 non critiche (possono essere interrotte)
- **Dedicated Hosts** — server fisico dedicato (compliance, licensing)

**Servizi AWS rilevanti:** Cost Explorer, Budgets, Trusted Advisor, Compute Optimizer, Savings Plans, Spot Instances, Auto Scaling

---

## 6. Sustainability

> *"Minimize the environmental impacts of running cloud workloads."*

(Sesto pilastro aggiunto nel 2021)

**Principi di design:**
- **Understand your impact** — misura il consumo energetico del workload
- **Establish sustainability goals** — riduzione progressiva
- **Maximize utilization** — usa serverless, container (high density)
- **Anticipate and adopt new efficient hardware** — Graviton, nuove generazioni istanze
- **Use managed services** — economie di scala energetica AWS
- **Reduce the downstream impact** — ottimizza client-side

**Obiettivo AWS:** raggiungere **100% energia rinnovabile** e **net-zero carbon** entro 2040.

**Pratiche concrete:**
- Usa istanze **Graviton3** (60% meno energia di x86 equivalente)
- Usa **Lambda/Fargate** invece di EC2 sempre accese
- Implementa **auto scaling** per evitare over-provisioning
- Spegni risorse non in uso (dev/test environments off-hours)
- Usa **S3 Intelligent-Tiering** per ridurre storage non necessario

**Servizi AWS rilevanti:** Customer Carbon Footprint Tool, Graviton, Lambda, Fargate, Compute Optimizer, S3 Intelligent-Tiering

---

## AWS Well-Architected Tool

Il **Well-Architected Tool** è un servizio gratuito in AWS Console per condurre review architetturali formali.

**Come funziona:**
1. Crea un **Workload** (nome, tipo, Region)
2. Seleziona **Lens** (WAF standard, Serverless, SaaS, Machine Learning, FTR...)
3. Rispondi a domande per pilastro
4. Il tool identifica **High Risk Items (HRI)** e **Medium Risk Items (MRI)**
5. Genera **report** con improvement plan prioritizzato
6. Tiene traccia del progresso nel tempo

```bash
# Well-Architected Tool disponibile nella Console AWS
# AWS Console → Architecture → Well-Architected Tool
# Non ha CLI commands significativi — si usa dalla Console
```

**AWS Well-Architected Lenses** (framework specializzati per domini specifici):
- **Foundational** (standard WAF)
- **Serverless**
- **SaaS**
- **Machine Learning**
- **Data Analytics**
- **Financial Services**
- **Healthcare**
- **Government**
- **IoT**
- **SAP**

---

## Design Principles Comuni a Tutti i Pilastri

| Principio | Descrizione |
|-----------|-------------|
| **Stop guessing needs** | Usa metriche reali per decisioni |
| **Test systems at production scale** | Load testing, chaos engineering |
| **Automate to make architectural experimentation easier** | IaC, CI/CD |
| **Allow for evolutionary architectures** | Design for change, non per stabilità eterna |
| **Drive architectures using data** | Metriche → decisioni |
| **Improve through game days** | Simulazioni di failure regolari |

---

## Troubleshooting

### Scenario 1 — Well-Architected Review rivela troppi High Risk Items (HRI)

**Sintomo:** Dopo una review con il Well-Architected Tool, il report mostra 10+ HRI e il team non sa da dove iniziare.

**Causa:** La review copre tutti i pilastri contemporaneamente su un workload maturo mai revisionato prima.

**Soluzione:** Prioritizzare HRI per impatto di business, non per pilastro. Attaccare prima Reliability e Security (impatto operativo diretto), poi Cost e Performance. Creare milestone nel Improvement Plan del tool.

```bash
# Visualizzare HRI per workload via CLI
aws wellarchitected list-answers \
  --workload-id <workload-id> \
  --lens-alias arn:aws:wellarchitected::aws:lens/wellarchitected \
  --pillar-id reliability \
  --query "AnswerSummaries[?Risk=='HIGH']"

# Ottenere lista workload
aws wellarchitected list-workloads --query "WorkloadSummaries[*].[WorkloadId,WorkloadName,RiskCounts]"
```

---

### Scenario 2 — Costi AWS superiori al budget senza causa apparente

**Sintomo:** Il costo mensile supera il budget del 30-50%, ma non ci sono nuove risorse visibili nel dashboard principale.

**Causa:** Risorse orfane (snapshot EBS, Load Balancer inutilizzati, NAT Gateway), traffico data transfer inter-region, o istanze over-provisioned.

**Soluzione:** Usare Cost Explorer con granularità servizio, verificare i suggerimenti di Trusted Advisor e Compute Optimizer.

```bash
# Identificare risorse costose per servizio nell'ultimo mese
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-03-01 \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query "ResultsByTime[0].Groups[?Metrics.UnblendedCost.Amount > '10']" \
  --output table

# Verificare snapshot EBS non associati a volumi attivi
aws ec2 describe-snapshots --owner-ids self \
  --query "Snapshots[?State=='completed'].[SnapshotId,VolumeSize,StartTime]" \
  --output table
```

---

### Scenario 3 — Applicazione non resiliente a failure di singola AZ

**Sintomo:** Durante una manutenzione AWS su un'AZ, l'applicazione va offline invece di fare failover automatico.

**Causa:** Risorse deployate in una sola AZ (EC2 singola, RDS senza Multi-AZ, ELB senza subnets in più AZ).

**Soluzione:** Distribuire risorse su almeno 2 AZ, abilitare RDS Multi-AZ, configurare Auto Scaling Group con AZ multipli.

```bash
# Verificare distribuzione EC2 per AZ
aws ec2 describe-instances \
  --query "Reservations[*].Instances[*].[InstanceId,Placement.AvailabilityZone,State.Name]" \
  --output table

# Verificare se RDS ha Multi-AZ abilitato
aws rds describe-db-instances \
  --query "DBInstances[*].[DBInstanceIdentifier,MultiAZ,AvailabilityZone]" \
  --output table

# Abilitare Multi-AZ su RDS esistente (causa breve downtime)
aws rds modify-db-instance \
  --db-instance-identifier <db-id> \
  --multi-az \
  --apply-immediately
```

---

### Scenario 4 — Security Hub segnala findings critici ignorati

**Sintomo:** Security Hub accumula centinaia di findings, il team li considera rumore di fondo e smette di monitorarli.

**Causa:** Nessun processo di triage, findings non assegnati a owner, mancanza di integrazione con ticket system.

**Soluzione:** Filtrare per severity CRITICAL/HIGH, sopprimere finding non applicabili con giustificazione, integrare con EventBridge → Lambda → Jira/ServiceNow per auto-ticketing.

```bash
# Elencare finding critici attivi in Security Hub
aws securityhub get-findings \
  --filters '{"SeverityLabel":[{"Value":"CRITICAL","Comparison":"EQUALS"}],"RecordState":[{"Value":"ACTIVE","Comparison":"EQUALS"}]}' \
  --query "Findings[*].[Title,AwsAccountId,UpdatedAt]" \
  --output table

# Sopprimere finding non applicabile (con nota)
aws securityhub batch-update-findings \
  --finding-identifiers Id=<finding-arn>,ProductArn=<product-arn> \
  --workflow Status=SUPPRESSED \
  --note Text="Non applicabile: ambiente sandbox senza dati sensibili",UpdatedBy=security-team
```

---

## Riferimenti

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [WAF Whitepaper](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- [Well-Architected Tool](https://aws.amazon.com/well-architected-tool/)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)
