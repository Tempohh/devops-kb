---
title: "Azure Networking"
slug: networking-azure
category: cloud
tags: [azure, networking, vnet, nsg, load-balancer, application-gateway, azure-firewall, vpn, expressroute, dns, front-door]
search_keywords: [Azure networking, Virtual Network VNet, NSG Network Security Group, Azure Load Balancer, Application Gateway, Azure Firewall, VPN Gateway, ExpressRoute, Azure DNS, Azure Front Door, CDN, Private Endpoint, Service Endpoint, VNet peering, hub-and-spoke, Azure Bastion, DDoS Protection]
parent: cloud/azure/_index
related: [cloud/azure/compute/_index, cloud/azure/security/_index]
official_docs: https://learn.microsoft.com/azure/networking/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Networking

## Panoramica Servizi di Rete

| Categoria | Servizio | Funzione |
|-----------|---------|----------|
| **Virtual Network** | Azure VNet | Rete privata isolata in Azure |
| **Sicurezza rete** | NSG, ASG, Azure Firewall | Filtraggio traffico |
| **Load Balancing** | Load Balancer, Application Gateway, Front Door, Traffic Manager | Distribuzione traffico |
| **DNS** | Azure DNS, Private DNS | Risoluzione nomi |
| **Connettività ibrida** | VPN Gateway, ExpressRoute | On-premises → Azure |
| **Accesso privato** | Private Endpoints, Service Endpoints | Accesso ai servizi senza Internet |
| **Protezione DDoS** | DDoS Protection Standard | Protezione attacchi volumetrici |
| **CDN** | Azure CDN, Azure Front Door | Distribuzione contenuti globale |
| **Bastion** | Azure Bastion | Accesso RDP/SSH sicuro senza IP pubblico |
| **Network Watcher** | Network Watcher | Diagnostica e monitoring rete |

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-lan: **[Virtual Network (VNet)](vnet.md)**

    ---
    VNet, subnet, NSG, ASG, route tables, peering, Private Endpoints, Service Endpoints, Azure Bastion

-   :material-scale-balance: **[Load Balancing](load-balancing.md)**

    ---
    Azure Load Balancer (L4), Application Gateway (L7 + WAF), Azure Front Door (globale), Traffic Manager

-   :material-connection: **[Connettività Ibrida](connettivita.md)**

    ---
    VPN Gateway (Site-to-Site, P2S), ExpressRoute (Dedicated, FastPath), Virtual WAN

-   :material-dns: **[DNS & CDN](dns-cdn.md)**

    ---
    Azure DNS (Public/Private Zones), Azure CDN, Azure Front Door CDN, DDoS Protection Standard

</div>
