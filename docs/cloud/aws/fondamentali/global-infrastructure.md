---
title: "AWS Global Infrastructure"
slug: global-infrastructure
category: cloud
tags: [aws, regions, availability-zones, edge-locations, local-zones, wavelength, outposts, global-infrastructure]
search_keywords: [AWS regions, AWS availability zones, AZ, edge locations, local zones, AWS wavelength, AWS outposts, AWS global infrastructure, latency, data residency, us-east-1, eu-west-1, eu-central-1, AWS backbone]
parent: cloud/aws/fondamentali/_index
related: [cloud/aws/networking/vpc, cloud/aws/networking/route53, cloud/aws/networking/cloudfront]
official_docs: https://aws.amazon.com/about-aws/global-infrastructure/
status: complete
difficulty: beginner
last_updated: 2026-03-28
---

# AWS Global Infrastructure

## Gerarchia dell'Infrastruttura

```
AWS Global Network (backbone privato fibra ottica mondiale)
│
├── Region (34+ geografiche)
│   ├── Availability Zone A  (datacenter cluster fisicamente separato)
│   ├── Availability Zone B  (min 3 AZ per Region)
│   └── Availability Zone C
│
├── Local Zone (estensione Region in città — latenza <10ms)
│
├── Wavelength Zone (embedding in reti 5G)
│
├── AWS Outposts (hardware AWS nel tuo datacenter)
│
└── Edge Locations / Points of Presence (600+)
    ├── CloudFront CDN
    └── Route 53 DNS
```

---

## Regions

Una **Region** è un'area geografica con infrastruttura AWS indipendente.

**Caratteristiche:**
- Ogni Region ha un **nome** (es. `eu-central-1`) e un **nome geografico** (Francoforte)
- Le Region sono **completamente isolate** tra loro — fault isolation geografica
- I dati **non abbandonano mai** una Region senza configurazione esplicita (data residency/sovranità)
- Ogni Region ha ≥3 AZ (la maggior parte ne ha 3-6)
- Non tutte le Region hanno tutti i servizi — verificare sempre la disponibilità

**Regions principali (Italia/Europa):**

| Region | Sede | Codice | AZ |
|--------|------|--------|-----|
| Europe (Ireland) | Irlanda | `eu-west-1` | 3 |
| Europe (Frankfurt) | Francoforte | `eu-central-1` | 3 |
| Europe (Milan) | Milano | `eu-south-1` | 3 |
| Europe (Paris) | Parigi | `eu-west-3` | 3 |
| Europe (London) | Londra | `eu-west-2` | 3 |
| Europe (Spain) | Spagna | `eu-south-2` | 3 |
| Europe (Stockholm) | Stoccolma | `eu-north-1` | 3 |
| US East (N. Virginia) | Virginia | `us-east-1` | 6 |

!!! note "Scegliere una Region"
    Criteri in ordine: **1) Compliance/Data Sovereignty** → **2) Latency** → **3) Servizi disponibili** → **4) Pricing** (varia fino al 20% tra Region)

---

## Availability Zones (AZ)

Un'**Availability Zone** è uno o più datacenter fisicamente separati all'interno di una Region.

**Caratteristiche:**
- Separazione fisica: power, cooling, networking **indipendenti**
- Connesse tra loro con fibra ridondante a **<10ms** di latenza
- Il nome AZ (es. `eu-central-1a`) non corrisponde necessariamente allo stesso datacenter fisico tra account diversi (AWS randomizza il mapping per distribuire il carico)
- I servizi **Multi-AZ** replicano su ≥2 AZ per alta disponibilità

```bash
# Listare le AZ disponibili in una Region
aws ec2 describe-availability-zones \
    --region eu-central-1 \
    --query 'AvailabilityZones[*].{Name:ZoneName,State:State}' \
    --output table
```

**Servizi con supporto Multi-AZ nativo:**
- **RDS Multi-AZ** — standby sincrono in AZ diversa
- **ElastiCache Multi-AZ** — replica automatica
- **EFS** — file system distribuito su tutte le AZ
- **ALB** — distribuisce traffico su più AZ
- **Auto Scaling Group** — lancia istanze in più AZ

---

## Edge Locations — CloudFront e Route 53

Le **Edge Locations** (Punti di Presenza) sono la rete di caching e routing distribuita globalmente.

| Componente | Numero | Utilizzo |
|-----------|--------|---------|
| Edge Locations | 600+ | CloudFront CDN, Lambda@Edge, Route 53 |
| Regional Edge Caches | 13 | Cache intermedia tra origin e edge |

**Come funziona CloudFront con Edge Locations:**
```
Utente (Milano)
      ↓
Edge Location Milano (cache hit → risposta immediata)
      ↓ (cache miss)
Regional Edge Cache Francoforte
      ↓ (cache miss)
Origin (S3/EC2/ALB nella Region)
```

---

## Local Zones

Le **Local Zones** portano compute, storage e database AWS **vicino agli utenti finali** in aree metropolitane specifiche, riducendo la latenza a **<10ms**.

**Caratteristiche:**
- Estensione di una Region (es. Los Angeles è estensione di `us-west-2`)
- Supportano: EC2, EBS, ECS, EKS, RDS, ElastiCache
- Ideali per: gaming, media & entertainment, video rendering, ML inference
- Si abilitano manualmente per account/Region

```bash
# Verificare Local Zones disponibili
aws ec2 describe-availability-zones \
    --all-availability-zones \
    --query 'AvailabilityZones[?ZoneType==`local-zone`].{Name:ZoneName,Region:RegionName}' \
    --output table
```

---

## Wavelength Zones

Le **Wavelength Zones** integrano l'infrastruttura AWS direttamente nelle reti **5G** degli operatori di telecomunicazione.

- Latenza ultra-bassa (<10ms) per applicazioni mobili 5G
- I device mobili si connettono direttamente al compute AWS senza passare per Internet
- Use case: video streaming live, AR/VR, veicoli autonomi, IoT industriale

---

## AWS Outposts

**AWS Outposts** porta l'hardware e il software AWS **nel tuo datacenter on-premises**.

| Opzione | Descrizione |
|---------|-------------|
| **Outposts Rack** | Full 42U rack AWS (da 1 a 96 rack) |
| **Outposts Servers** | Server 1U/2U per spazi ristretti |

**Caratteristiche:**
- Stesso hardware, APIs e tools del cloud AWS
- Latenza molto bassa per workload on-premises
- Connessione obbligatoria alla Region "parent" (Outpost Region)
- Gestione tramite AWS Console/CLI come servizi cloud normali

**Use case:** Compliance con data residency, latenza ultra-bassa per sistemi industriali, modernizzazione graduale legacy

---

## AWS Global Backbone

AWS possiede una rete privata globale in fibra ottica che interconnette tutte le Region e i datacenter.

```
Internet           AWS Backbone (privato)
─────────          ───────────────────────
Utente             Edge     Region A    Region B
  ↓                Location   ↓          ↓
Request ──────────→ POP ────→ Fiber ────→ Fiber
(public internet)       (privato, no internet)
```

**Vantaggi del backbone privato:**
- Throughput e latenza prevedibili (non soggetti a congestione Internet)
- Sicurezza (traffico non esposto a Internet)
- Riduzione dei costi di trasferimento dati inter-Region rispetto a Internet

---

## Confronto: Global vs Regional vs AZ-scoped

| Scope | Servizi |
|-------|---------|
| **Global** | IAM, Route 53, CloudFront, WAF (Web Application Firewall — global), AWS Organizations |
| **Regional** | VPC, EC2, S3, RDS, Lambda, SQS, SNS, DynamoDB, ECS, EKS |
| **AZ-scoped** | Subnet, EC2 instance, EBS volume, RDS Primary/Standby |

!!! warning "Esame CLF-C02"
    Ricordare: IAM è **globale** (non ha Region). Route 53 e CloudFront sono **globali**. S3 bucket ha nome globale univoco ma i dati risiedono in una specifica Region. EC2 è **regionale** (si sceglie AZ/Subnet al lancio).

---

## Troubleshooting

### Scenario 1 — Servizio non disponibile nella Region scelta

**Sintomo:** `InvalidClientTokenId` o errore "service not available in this region" quando si tenta di creare una risorsa.

**Causa:** Non tutti i servizi AWS sono disponibili in tutte le Region. Le Region più recenti (es. `eu-south-1` Milano) hanno copertura parziale.

**Soluzione:** Verificare la disponibilità del servizio nella Region target prima del deploy.

```bash
# Verificare i servizi disponibili in una Region specifica
aws ssm get-parameters-by-path \
    --path /aws/service/global-infrastructure/regions/eu-south-1/services \
    --query 'Parameters[*].Name' --output text

# In alternativa, controllare via CLI quale Region supporta un servizio
aws ec2 describe-regions \
    --filters "Name=opt-in-status,Values=opted-in,opt-in-not-required" \
    --query 'Regions[*].RegionName' --output table
```

---

### Scenario 2 — Latenza elevata tra servizi in AZ diverse

**Sintomo:** Latenza inattesa tra istanze EC2 o tra un'EC2 e un RDS, nonostante entrambi siano nella stessa Region.

**Causa:** I servizi sono in AZ diverse. La latenza inter-AZ è <10ms ma non è zero — per workload I/O intensivi può diventare rilevante. Oppure il mapping AZ (es. `eu-central-1a`) differisce tra account diversi.

**Soluzione:** Verificare il placement effettivo delle risorse e consolidarle nella stessa AZ se necessario (attenzione: riduce la fault tolerance).

```bash
# Verificare in quale AZ si trovano le istanze EC2
aws ec2 describe-instances \
    --query 'Reservations[*].Instances[*].{ID:InstanceId,AZ:Placement.AvailabilityZone}' \
    --output table

# Verificare l'AZ di un'istanza RDS
aws rds describe-db-instances \
    --query 'DBInstances[*].{ID:DBInstanceIdentifier,AZ:AvailabilityZone,MultiAZ:MultiAZ}' \
    --output table
```

---

### Scenario 3 — Data residency violata: dati replicati fuori dalla Region

**Sintomo:** Audit di compliance segnala dati in Region non autorizzate. Tipicamente S3 Cross-Region Replication o backup automatici configurati verso Region diverse.

**Causa:** Feature di replication o backup cross-Region abilitate esplicitamente o per default in alcuni servizi (es. AWS Backup con vault policy, S3 CRR, RDS automated backups cross-region).

**Soluzione:** Applicare SCP (Service Control Policy) a livello di AWS Organizations per bloccare azioni cross-Region non autorizzate.

```bash
# Verificare le regole di replication su un bucket S3
aws s3api get-bucket-replication --bucket nome-bucket

# Verificare le policy SCP applicate all'account
aws organizations list-policies-for-target \
    --target-id <account-id> \
    --filter SERVICE_CONTROL_POLICY \
    --query 'Policies[*].{Name:Name,Id:Id}' \
    --output table
```

---

### Scenario 4 — Outpost non raggiungibile: perdita di connettività con la Region parent

**Sintomo:** Le risorse sull'Outpost diventano irraggiungibili o le API calls falliscono con timeout. Il management plane smette di rispondere.

**Causa:** L'Outpost richiede connettività continua verso la Region parent tramite Service Link. Se la WAN o il Direct Connect si interrompe, il control plane perde contatto.

**Soluzione:** Verificare lo stato del Service Link e della connettività di rete verso la Region parent. Le risorse già in esecuzione continuano a funzionare localmente, ma non è possibile gestirle tramite console/API.

```bash
# Verificare lo stato degli Outpost e del loro Service Link
aws outposts list-outposts \
    --query 'Outposts[*].{Name:Name,Id:OutpostId,SiteId:SiteId,LifeCycleStatus:LifeCycleStatus}' \
    --output table

# Verificare la connettività verso la Region parent (eseguire dall'Outpost)
curl -I https://ec2.eu-central-1.amazonaws.com
```

---

## Riferimenti

- [AWS Global Infrastructure](https://aws.amazon.com/about-aws/global-infrastructure/)
- [AWS Regions and AZ](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/)
- [AWS Local Zones](https://aws.amazon.com/about-aws/global-infrastructure/localzones/)
- [AWS Outposts](https://aws.amazon.com/outposts/)
- [Servizi per Region](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/)
