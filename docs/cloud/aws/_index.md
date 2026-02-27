---
title: "Amazon Web Services"
slug: aws
category: cloud
tags: [aws, cloud, certification, devops, infrastructure]
search_keywords: [AWS, Amazon Web Services, cloud provider, AWS certification, CLF-C02, SAA-C03, DOP-C02, AWS devops, cloud practitioner, solutions architect, devops engineer professional]
parent: cloud/_index
related: []
official_docs: https://docs.aws.amazon.com/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# Amazon Web Services

AWS è il cloud provider più diffuso al mondo, con oltre **240 servizi** distribuiti globalmente. Questa sezione copre AWS dalla prospettiva di un **Cloud/DevOps Engineer**, integrando i contenuti necessari per le certificazioni AWS.

## Percorso Certificazioni

```
Foundational                Associate                Professional / Specialty
────────────                ─────────                ─────────────────────────
┌─────────────┐             ┌──────────────────┐     ┌─────────────────────────┐
│    Cloud    │ ──────────→ │ Solutions        │ ──→ │ Solutions Architect Pro  │
│ Practitioner│             │ Architect Assoc. │     │                         │
│  (CLF-C02)  │             │  (SAA-C03)       │     └─────────────────────────┘
└─────────────┘             └──────────────────┘          ↑
                            ┌──────────────────┐     ┌─────────────────────────┐
                            │  Developer       │ ──→ │ DevOps Engineer Pro     │
                            │  Associate       │     │     (DOP-C02)  ←target  │
                            │  (DVA-C02)       │     └─────────────────────────┘
                            └──────────────────┘     ┌─────────────────────────┐
                            ┌──────────────────┐     │ Specialty:              │
                            │  SysOps Admin    │ ──→ │ Security / Networking / │
                            │  Associate       │     │ Database / ML           │
                            │  (SOA-C02)       │     └─────────────────────────┘
                            └──────────────────┘
```

**Percorso consigliato per Cloud/DevOps Engineer:**
`CLF-C02` → `SAA-C03` → `DOP-C02`

| Certificazione | Dominio | Difficoltà | Note |
|---|---|---|---|
| **CLF-C02** Cloud Practitioner | Foundational | ⭐⭐ | Fondamenta di ogni percorso AWS |
| **SAA-C03** Solutions Architect Associate | Associate | ⭐⭐⭐ | Comprensione architetturale completa |
| **DOP-C02** DevOps Engineer Professional | Professional | ⭐⭐⭐⭐⭐ | Target per DevOps Engineer |
| **DVA-C02** Developer Associate | Associate | ⭐⭐⭐ | Alternativa/complemento SAA |
| **SCS-C02** Security Specialty | Specialty | ⭐⭐⭐⭐ | Approfondimento security |

---

## Global Infrastructure — Quick Reference

```
AWS Global Infrastructure (2025)

  Regions: 34 geografiche (es. eu-west-1=Irlanda, eu-central-1=Francoforte)
  Availability Zones: 108 AZ (min 3 per Region, isolate fisicamente)
  Edge Locations: 600+ (CloudFront CDN, Route 53)
  Local Zones: estensione Region per latenza ultra-bassa in città specifiche
  Wavelength Zones: integrazione con reti 5G degli operatori
  AWS Outposts: rack AWS nel tuo datacenter (cloud ibrido)
```

**Regole importanti:**
- Una **Region** contiene ≥3 **AZ** separate (~100km tra loro, connesse a bassa latenza)
- Le **AZ** sono isolate da guasti fisici (power, cooling, networking)
- La maggior parte dei servizi è **region-scoped** (es. EC2, RDS, VPC)
- Alcuni servizi sono **global** (IAM, Route 53, CloudFront, WAF)
- Dati **non si muovono mai tra Regioni** senza configurazione esplicita

---

## Mappa dei Servizi

<div class="grid cards" markdown>

- :material-shield-account: **[IAM](iam/_index.md)**

    Identity & Access Management — utenti, ruoli, policy, organizzazioni multi-account

- :material-earth: **[Networking](networking/_index.md)**

    VPC, Route 53, CloudFront, Direct Connect, Transit Gateway

- :material-server: **[Compute](compute/_index.md)**

    EC2, Auto Scaling, Lambda, ECS, EKS, Fargate

- :material-database: **[Storage](storage/_index.md)**

    S3, EBS, EFS, FSx, Storage Gateway, Snow Family

- :material-table: **[Database](database/_index.md)**

    RDS, Aurora, DynamoDB, ElastiCache, Redshift

- :material-lock: **[Security](security/_index.md)**

    KMS, Secrets Manager, GuardDuty, WAF, Shield, CloudTrail

- :material-chart-line: **[Monitoring](monitoring/_index.md)**

    CloudWatch, X-Ray, CloudTrail, AWS Config

- :material-pipe: **[CI/CD](ci-cd/_index.md)**

    CodePipeline, CodeBuild, CodeDeploy, CloudFormation, CDK

- :material-email: **[Messaging](messaging/_index.md)**

    SQS, SNS, EventBridge, Kinesis, MSK

- :material-book-open: **[Fondamentali](fondamentali/_index.md)**

    Cloud concepts, Well-Architected, pricing, shared responsibility

</div>

---

## Come Usare Questa Sezione

!!! tip "Percorso Cloud Practitioner (CLF-C02)"
    Leggi in ordine: **Fondamentali → IAM → Networking (VPC) → Compute (EC2) → Storage (S3) → Database → Security → Monitoring → Billing**

!!! info "Percorso DevOps Engineer (DOP-C02)"
    Dopo CLF-C02 e SAA-C03: **IAM Avanzato → Networking Avanzato → Lambda → ECS/EKS → CI/CD → CloudFormation/CDK → Monitoring Avanzato → Security Avanzato**

I contenuti di questa sezione integrano la prospettiva d'esame (domini, peso percentuale, servizi testati) con la pratica operativa quotidiana. Le admonition `!!! exam` segnalano i concetti più frequentemente testati negli esami.
