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
last_updated: 2026-02-25
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
| **Global** | IAM, Route 53, CloudFront, WAF (global), AWS Organizations |
| **Regional** | VPC, EC2, S3, RDS, Lambda, SQS, SNS, DynamoDB, ECS, EKS |
| **AZ-scoped** | Subnet, EC2 instance, EBS volume, RDS Primary/Standby |

!!! warning "Esame CLF-C02"
    Ricordare: IAM è **globale** (non ha Region). Route 53 e CloudFront sono **globali**. S3 bucket ha nome globale univoco ma i dati risiedono in una specifica Region. EC2 è **regionale** (si sceglie AZ/Subnet al lancio).

---

## Riferimenti

- [AWS Global Infrastructure](https://aws.amazon.com/about-aws/global-infrastructure/)
- [AWS Regions and AZ](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/)
- [AWS Local Zones](https://aws.amazon.com/about-aws/global-infrastructure/localzones/)
- [AWS Outposts](https://aws.amazon.com/outposts/)
- [Servizi per Region](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/)
