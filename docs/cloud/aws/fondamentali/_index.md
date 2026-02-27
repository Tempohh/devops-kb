---
title: "Fondamentali AWS"
slug: fondamentali
category: cloud
tags: [aws, cloud-concepts, well-architected, billing, shared-responsibility, global-infrastructure]
search_keywords: [AWS fondamentali, cloud concepts, vantaggi cloud, AWS Well-Architected, shared responsibility model, AWS pricing, AWS billing, AWS global infrastructure]
parent: cloud/aws/_index
related: [cloud/aws/iam/_index, cloud/aws/networking/_index]
official_docs: https://aws.amazon.com/getting-started/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# Fondamentali AWS

I fondamentali AWS coprono i concetti di base necessari per qualsiasi percorso cloud — e sono il **cuore del Cloud Practitioner (CLF-C02)**.

## Sezioni

<div class="grid cards" markdown>

- :material-earth: **[Global Infrastructure](global-infrastructure.md)**

    Regions, Availability Zones, Edge Locations, Local Zones, Outposts

- :material-shield-half-full: **[Shared Responsibility Model](shared-responsibility.md)**

    Responsabilità AWS vs Cliente — il principio fondamentale della sicurezza cloud

- :material-pillar: **[Well-Architected Framework](well-architected.md)**

    6 pilastri per architetture cloud eccellenti + WAF Tool

- :material-currency-usd: **[Billing & Pricing](billing-pricing.md)**

    Modelli di prezzo, Cost Explorer, Budgets, Savings Plans, Trusted Advisor

</div>

---

## I 6 Vantaggi del Cloud (CLF-C02)

AWS identifica **6 vantaggi** del cloud computing rispetto all'on-premises — frequentemente testati nel Cloud Practitioner:

| # | Vantaggio | Spiegazione |
|---|-----------|-------------|
| 1 | **Trade capital expense for variable expense** | Da CAPEX (datacenter) a OPEX (pay-as-you-go) |
| 2 | **Benefit from massive economies of scale** | AWS aggrega milioni di clienti → prezzi più bassi |
| 3 | **Stop guessing capacity** | Scale up/down on demand — no over-provisioning |
| 4 | **Increase speed and agility** | Deploy in minuti invece di settimane |
| 5 | **Stop spending money on maintaining data centers** | Focus sul business, non sull'infrastruttura |
| 6 | **Go global in minutes** | Deploy in qualsiasi Region AWS con pochi click |

## Tipi di Cloud Deployment

| Modello | Descrizione | Esempio |
|---------|-------------|---------|
| **Cloud** | Tutto nel cloud, niente on-premises | Startup native cloud |
| **Hybrid** | Mix cloud + on-premises | Enterprise con legacy systems |
| **On-premises** | Tutto nel datacenter aziendale (Private Cloud) | Compliance/sovranità dati |

## Modelli di Servizio (IaaS / PaaS / SaaS)

```
Responsabilità crescente verso il cliente →

IaaS              PaaS              SaaS
─────             ─────             ─────
EC2, VPC,         Elastic           Gmail,
EBS, S3           Beanstalk,        Salesforce,
                  RDS, Lambda       WorkDocs

Tu gestisci:      Tu gestisci:      Tu usi:
OS, middleware,   applicazione      applicazione
applicazione,     e dati            e dati
dati
```
