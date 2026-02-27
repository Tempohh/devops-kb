---
title: "Modello di Responsabilità Condivisa Azure"
slug: shared-responsibility-azure
category: cloud
tags: [azure, shared-responsibility, security, compliance, iaas, paas, saas]
search_keywords: [Azure shared responsibility model, responsabilità condivisa Azure, sicurezza cloud Azure, IaaS responsabilità, PaaS responsabilità, SaaS responsabilità, Microsoft responsabilità, compliance Azure, GDPR Azure, customer responsibility]
parent: cloud/azure/fondamentali/_index
related: [cloud/azure/security/_index, cloud/azure/identita/_index]
official_docs: https://learn.microsoft.com/azure/security/fundamentals/shared-responsibility
status: complete
difficulty: beginner
last_updated: 2026-02-26
---

# Modello di Responsabilità Condivisa Azure

Il **Modello di Responsabilità Condivisa** definisce la ripartizione delle responsabilità di sicurezza tra Microsoft Azure e il cliente.

> **Microsoft** è responsabile della sicurezza **del** cloud.
> **Il cliente** è responsabile della sicurezza **nel** cloud.

---

## Matrice delle Responsabilità

| Responsabilità | On-Premises | IaaS | PaaS | SaaS |
|---------------|-------------|------|------|------|
| Dati e contenuti | Cliente | Cliente | Cliente | Cliente |
| Endpoint / dispositivi | Cliente | Cliente | Cliente | Condivisa |
| Account e identità | Cliente | Cliente | Condivisa | Condivisa |
| Applicazioni | Cliente | Cliente | Condivisa | Microsoft |
| Controlli di rete | Cliente | Condivisa | Microsoft | Microsoft |
| Sistema operativo | Cliente | Cliente | Microsoft | Microsoft |
| Host fisico | Cliente | Microsoft | Microsoft | Microsoft |
| Rete fisica | Cliente | Microsoft | Microsoft | Microsoft |
| Datacenter fisico | Cliente | Microsoft | Microsoft | Microsoft |

---

## Responsabilità Microsoft (sempre)

- Sicurezza fisica dei datacenter (accesso, sorveglianza, climatizzazione)
- Infrastruttura di rete fisica (fibra, switch, router backbone)
- Hypervisor e virtualizzazione dell'hardware
- Patch e aggiornamenti del firmware hardware
- Conformità del datacenter (ISO 27001, SOC 1/2/3, PCI DSS, ecc.)

---

## Responsabilità del Cliente (sempre)

- **Dati**: classificazione, crittografia, backup
- **Identità e accessi**: account, password, MFA, privilegi minimi
- **Endpoint**: dispositivi che accedono ai servizi Azure
- **Configurazione corretta dei servizi**: NSG, firewall, policy

---

## Dettaglio per Tipo di Servizio

=== "IaaS (es. Virtual Machines)"
    Il cliente gestisce TUTTO sopra l'hypervisor:

    | Area | Responsabilità |
    |------|---------------|
    | OS (patching, hardening) | **Cliente** |
    | Runtime (Java, .NET, Python) | **Cliente** |
    | Middleware (web server, app server) | **Cliente** |
    | Applicazione | **Cliente** |
    | Dati applicativi | **Cliente** |
    | Network security (NSG, firewall) | **Cliente** |
    | Backup e DR | **Cliente** |
    | Identità (OS-level) | **Cliente** |

=== "PaaS (es. App Service, Azure SQL)"
    Microsoft gestisce infrastruttura + OS + runtime:

    | Area | Responsabilità |
    |------|---------------|
    | OS patching | **Microsoft** |
    | Runtime patching | **Microsoft** |
    | Scaling infrastructure | **Microsoft** |
    | Applicazione e codice | **Cliente** |
    | Configurazione servizio | **Cliente** |
    | Dati applicativi | **Cliente** |
    | Identità applicativa (Managed Identity) | **Condivisa** |

=== "SaaS (es. Microsoft 365)"
    Microsoft gestisce quasi tutto:

    | Area | Responsabilità |
    |------|---------------|
    | Infrastruttura completa | **Microsoft** |
    | Applicazione SaaS | **Microsoft** |
    | Dati degli utenti | **Cliente** |
    | Configurazione (policy, permessi) | **Cliente** |
    | Accessi e identità (account) | **Cliente** |

---

## Compliance e Certificazioni Azure

Microsoft Azure è certificato per i principali standard di compliance:

| Standard | Descrizione | Scope |
|----------|-------------|-------|
| **ISO 27001** | Sicurezza informazioni | Globale |
| **ISO 27017** | Sicurezza cloud | Globale |
| **ISO 27018** | Privacy dati cloud (PII) | Globale |
| **SOC 1, 2, 3** | Controlli servizi | Globale |
| **PCI DSS Level 1** | Carte di pagamento | Globale |
| **GDPR** | Protezione dati EU | Europa |
| **HIPAA/HITECH** | Dati sanitari USA | USA |
| **FedRAMP High** | Governo federale USA | Azure Government |
| **C5** | Sicurezza cloud (BSI Germania) | Europa |
| **ENS High** | Sicurezza nazionale spagnola | Spagna |

```bash
# Azure Compliance Manager — verificare postura compliance
# Disponibile in Microsoft Defender for Cloud o Microsoft Purview Compliance Manager

# Verificare policy compliance (Azure Policy)
az policy state list \
    --resource-group myapp-rg \
    --query "[?complianceState=='NonCompliant'].{Policy:policyDefinitionName, Resource:resourceId}" \
    --output table
```

---

## Strumenti per la Conformità

| Strumento | Funzione |
|-----------|----------|
| **Microsoft Defender for Cloud** | Postura sicurezza, raccomandazioni, compliance dashboard |
| **Azure Policy** | Policy enforcement automatico su risorse |
| **Microsoft Purview** | Governance dati, classificazione, compliance |
| **Azure Blueprints** (legacy) | Template ambiente conforme (sostituito da Template Specs + Policy) |
| **Microsoft Compliance Manager** | Assessment compliance, action items, punteggio |

---

## Riferimenti

- [Shared Responsibility in the Cloud](https://learn.microsoft.com/azure/security/fundamentals/shared-responsibility)
- [Azure Compliance Documentation](https://learn.microsoft.com/azure/compliance/)
- [Azure Trust Center](https://www.microsoft.com/trust-center)
- [Azure Security Benchmark](https://learn.microsoft.com/security/benchmark/azure/)
