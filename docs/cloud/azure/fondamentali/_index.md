---
title: "Azure Fondamentali"
slug: fondamentali-azure
category: cloud
tags: [azure, fondamentali, cloud-computing, az-900]
search_keywords: [Azure fondamentali, cloud computing Azure, AZ-900, IaaS PaaS SaaS, vantaggi cloud, modello consumo, alta disponibilità scalabilità elasticità]
parent: cloud/azure/_index
related: [cloud/azure/fondamentali/global-infrastructure, cloud/azure/fondamentali/shared-responsibility, cloud/azure/fondamentali/well-architected, cloud/azure/fondamentali/pricing]
official_docs: https://learn.microsoft.com/azure/fundamentals/
status: complete
difficulty: beginner
last_updated: 2026-02-26
---

# Azure Fondamentali

## Modelli di Servizio Cloud

| Modello | Gestisce Azure | Gestisce Cliente | Esempi Azure |
|---------|---------------|-----------------|--------------|
| **IaaS** | Infrastruttura fisica, rete, virtualizzazione | OS, runtime, dati, applicazioni | Virtual Machines, Managed Disks, VNet |
| **PaaS** | Infrastruttura + OS + runtime | Applicazioni, dati | App Service, Azure SQL, AKS |
| **SaaS** | Tutto | Solo configurazione e utilizzo | Microsoft 365, Dynamics 365 |

## Vantaggi del Cloud Computing

1. **Alta disponibilità** — SLA garantiti da Microsoft (99.9% - 99.999%)
2. **Scalabilità** — verticale (resize VM) e orizzontale (scale out)
3. **Elasticità** — risorse scalano automaticamente con il carico
4. **Agilità** — provisioning in minuti invece di settimane
5. **Distribuzione geografica** — 60+ region, vicine agli utenti
6. **Disaster Recovery** — backup e failover su region pair
7. **Modello CapEx → OpEx** — da costi fissi a costi variabili (pay-as-you-go)
8. **Economia di scala** — prezzi ridotti grazie al volume Microsoft

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-earth: **[Infrastruttura Globale](global-infrastructure.md)**

    ---
    Regions, Availability Zones, Region Pairs, Edge Locations, Sovereign Clouds

-   :material-shield-half-full: **[Modello Responsabilità Condivisa](shared-responsibility.md)**

    ---
    Responsabilità Microsoft vs cliente per IaaS, PaaS e SaaS

-   :material-pillar: **[Well-Architected Framework](well-architected.md)**

    ---
    I 5 pilastri WAF Azure: Reliability, Security, Cost Optimization, Operational Excellence, Performance Efficiency

-   :material-currency-usd: **[Pricing & Cost Management](pricing.md)**

    ---
    Modelli di prezzo, Reserved Instances, Azure Cost Management, Billing, TCO Calculator

</div>
