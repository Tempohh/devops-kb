---
title: "AWS Global Infrastructure"
slug: global-infrastructure
category: cloud
tags: [aws, regions, availability-zones, edge-locations, local-zones, wavelength, outposts, global-infrastructure]
search_keywords: [AWS regions, AWS availability zones, AZ, edge locations, local zones, AWS wavelength, AWS outposts, AWS global infrastructure, latency, data residency, us-east-1, eu-west-1, eu-central-1, AWS backbone]
parent: cloud/aws/fondamentali/_index
related: [cloud/aws/networking/vpc, cloud/aws/networking/route53, cloud/aws/networking/cloudfront]
official_docs: https://aws.amazon.com/about-aws/global-infrastructure/
status: reviewed
difficulty: beginner
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# AWS Global Infrastructure

## Gerarchia dell'Infrastruttura

```
AWS Global Network (backbone privato fibra ottica mondiale)
│
├── Region (35+ geografiche — il numero cresce, verificare sul sito ufficiale)
│   ├── Availability Zone A  (datacenter cluster fisicamente separato)
│   ├── Availability Zone B  (tipicamente ≥3 AZ per Region)
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
- Quasi tutte le Region hanno ≥3 AZ (3-6); qualche Region storica ne espone solo 2 ai nuovi account (es. `us-west-1`)
- Le Region più recenti (es. Milano `eu-south-1`, Spagna `eu-south-2`) sono **opt-in**: vanno abilitate per account (Console → Account → AWS Regions, o `aws account enable-region`) prima dell'uso; le Region storiche sono sempre attive
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
    Criteri in ordine: **1) Compliance/Data Sovereignty** → **2) Latency** → **3) Servizi disponibili** → **4) Pricing** (varia sensibilmente tra Region: `us-east-1` è tipicamente tra le più economiche)

---

## Availability Zones (AZ)

Un'**Availability Zone** è uno o più datacenter fisicamente separati all'interno di una Region.

**Caratteristiche:**
- Separazione fisica: power, cooling, networking **indipendenti**
- Connesse tra loro con fibra ridondante a **<10ms** di latenza
- Il nome AZ (es. `eu-central-1a`) non corrisponde necessariamente allo stesso datacenter fisico tra account diversi: AWS randomizza il mapping per evitare che tutti gli account si concentrino sulla `a`. L'identificatore stabile è l'**AZ ID** (es. `euc1-az1`), uguale per tutti gli account: usarlo quando si coordina il placement tra account (es. VPC sharing, PrivateLink)
- I servizi **Multi-AZ** replicano su ≥2 AZ per alta disponibilità

```bash
# Listare le AZ disponibili in una Region
aws ec2 describe-availability-zones \
    --region eu-central-1 \
    --query 'AvailabilityZones[*].{Name:ZoneName,Id:ZoneId,State:State}' \
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
| Edge Locations | 600+ (PoP) | CloudFront CDN, CloudFront Functions, Route 53 DNS |
| Regional Edge Caches | 13 | Cache intermedia tra origin e edge; qui girano le Lambda@Edge |

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

- Latenza ultra-bassa (target a singola cifra di ms) per applicazioni mobili 5G, perché il traffico resta nella rete dell'operatore
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
- Connessione obbligatoria alla Region "parent" tramite **Service Link** (VPN gestita su Direct Connect o Internet): serve per control plane, monitoring e aggiornamenti
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
- Il traffico inter-Region resta comunque **a pagamento** (data transfer out inter-Region): il backbone migliora qualità e sicurezza, non azzera i costi

---

## Confronto: Global vs Regional vs AZ-scoped

| Scope | Servizi |
|-------|---------|
| **Global** | IAM, Route 53, CloudFront, AWS Organizations (control plane in `us-east-1`) |
| **Regional** | VPC, EC2, S3, RDS, Lambda, SQS, SNS, DynamoDB, ECS, EKS, ACM, AWS WAF |
| **AZ-scoped** | Subnet, EC2 instance, EBS volume, RDS Primary/Standby |

!!! warning "Esame CLF-C02"
    Ricordare: IAM è **globale** (non ha Region). Route 53 e CloudFront sono **globali**. AWS WAF è regionale (per CloudFront si crea con scope `CLOUDFRONT` in `us-east-1`; i certificati ACM per CloudFront vanno anch'essi in `us-east-1`). S3 bucket ha nome globale univoco ma i dati risiedono in una specifica Region. EC2 è **regionale** (si sceglie AZ/Subnet al lancio).

---

## Troubleshooting

### Scenario 1 — Servizio non disponibile nella Region scelta

**Sintomo:** `Could not connect to the endpoint URL`, errore "not available in this region", oppure `InvalidClientTokenId` se la Region è opt-in e non ancora abilitata.

**Causa:** Non tutti i servizi AWS sono disponibili in tutte le Region. Le Region più recenti (es. `eu-south-1` Milano) hanno copertura parziale e sono opt-in.

**Soluzione:** Verificare la disponibilità del servizio nella Region target prima del deploy.

```bash
# Verificare i servizi disponibili in una Region specifica
aws ssm get-parameters-by-path \
    --path /aws/service/global-infrastructure/regions/eu-south-1/services \
    --query 'Parameters[*].Name' --output text

# Al contrario: in quali Region è disponibile un servizio (es. Lambda)
aws ssm get-parameters-by-path \
    --path /aws/service/global-infrastructure/services/lambda/regions \
    --query 'Parameters[*].Value' --output text

# Region dell'account e stato opt-in
aws account list-regions --query 'Regions[*].[RegionName,RegionOptStatus]' --output table
```

---

### Scenario 2 — Latenza elevata tra servizi in AZ diverse

**Sintomo:** Latenza inattesa tra istanze EC2 o tra un'EC2 e un RDS, nonostante entrambi siano nella stessa Region.

**Causa:** I servizi sono in AZ diverse. La latenza inter-AZ è a singola cifra di ms ma non è zero — per workload I/O intensivi può diventare rilevante. Il traffico inter-AZ è inoltre **a pagamento** (circa 0,01 $/GB per direzione): servizi molto "chiacchieroni" in AZ diverse costano. Oppure il mapping AZ (es. `eu-central-1a`) differisce tra account: confrontare gli AZ ID, non i nomi.

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

**Causa:** Feature di replication o backup cross-Region configurate esplicitamente da qualcuno nell'account (S3 CRR, AWS Backup con copy rule, RDS cross-region automated backups, copia di snapshot/AMI). Nessuna è attiva di default: va cercato chi l'ha creata.

**Soluzione:** Applicare SCP (Service Control Policy) a livello di AWS Organizations che neghi ogni azione fuori dalle Region approvate tramite la condition `aws:RequestedRegion`. I servizi globali (IAM, Organizations, Route 53, CloudFront, Support…) vanno esclusi con `NotAction`, altrimenti si bloccano.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyOutsideEU",
    "Effect": "Deny",
    "NotAction": ["iam:*", "organizations:*", "route53:*", "cloudfront:*", "support:*", "sts:*"],
    "Resource": "*",
    "Condition": {"StringNotEquals": {"aws:RequestedRegion": ["eu-central-1", "eu-south-1"]}}
  }]
}
```

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
