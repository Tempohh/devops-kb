---
title: "Azure Security"
slug: security-azure
category: cloud
tags: [azure, security, key-vault, defender, sentinel, ddos, firewall, waf]
search_keywords: [Azure Key Vault secrets keys certificates, Microsoft Defender for Cloud CSPM CWPP, Microsoft Sentinel SIEM SOAR, Azure DDoS Protection, Azure Firewall premium, WAF Web Application Firewall, Entra ID Protection, Just-In-Time VM Access, Azure Policy compliance]
parent: cloud/azure/_index
related: [cloud/azure/networking/vnet, cloud/azure/identita/rbac-managed-identity, cloud/azure/compute/virtual-machines]
official_docs: https://learn.microsoft.com/azure/security/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Security

Azure offre una suite completa di servizi di sicurezza che coprono protezione dei segreti, postura di sicurezza, threat detection, SIEM e protezione delle applicazioni web. La sicurezza su Azure segue il modello di responsabilità condivisa: Microsoft gestisce la sicurezza dell'infrastruttura fisica, il cliente è responsabile della configurazione e dei dati.

## Panoramica dei Servizi di Sicurezza

| Servizio | Categoria | Funzione | Tier |
|---|---|---|---|
| **Key Vault** | Gestione segreti | Archiviazione sicura di secrets, keys, certificates | Standard / Premium / Managed HSM |
| **Defender for Cloud** | CSPM + CWPP | Postura sicurezza cloud + protezione workload | Free (Foundational) / Paid (per resource) |
| **Microsoft Sentinel** | SIEM + SOAR | Rilevamento minacce, correlazione, risposta automatica | Pay-per-GB ingested |
| **DDoS Protection** | Network | Protezione DDoS L3/L4/L7 | Basic (free) / Standard (a pagamento) |
| **Azure Firewall** | Network | Firewall L4/L7 stateful, IDPS, URL filtering | Standard / Premium |
| **WAF** | Application | Web Application Firewall per App Gateway e Front Door | Incluso con App Gateway/Front Door |
| **Entra ID Protection** | Identity | Rilevamento rischio identity, Conditional Access | Incluso in Entra ID P2 |

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   **Azure Key Vault**

    ---

    Gestione centralizzata di secrets, keys e certificates. RBAC vs access policies, Private Endpoint, soft delete, purge protection, Key Vault References, auto-rotation.

    [:octicons-arrow-right-24: Vai a Key Vault](key-vault.md)

-   **Defender for Cloud & Microsoft Sentinel**

    ---

    CSPM con Secure Score, Defender plans per workload protection, SIEM Sentinel con KQL analytics, Playbooks automatici, MITRE ATT&CK integration.

    [:octicons-arrow-right-24: Vai a Defender & Sentinel](defender-sentinel.md)

</div>

## Defense-in-Depth su Azure

```
Layer 1: Fisica     → Microsoft gestisce (datacenter, hardware)
Layer 2: Identità   → Entra ID, MFA, Conditional Access, PIM
Layer 3: Perimetro  → Azure DDoS, Azure Firewall, Front Door WAF
Layer 4: Rete       → VNet NSG, UDR, Private Endpoint, VPN/ExpressRoute
Layer 5: Compute    → Defender for Servers, Bastion, JIT, TrustedLaunch
Layer 6: App        → App Gateway WAF, API Management, Managed Identity
Layer 7: Dati       → Key Vault, TDE, CMK, Purview, Storage encryption
```

## Riferimenti

- [Azure Security Documentation](https://learn.microsoft.com/azure/security/)
- [Microsoft Cloud Security Benchmark (MCSB)](https://learn.microsoft.com/security/benchmark/azure/introduction)
- [Azure Security Center (ora Defender for Cloud)](https://learn.microsoft.com/azure/defender-for-cloud/)
