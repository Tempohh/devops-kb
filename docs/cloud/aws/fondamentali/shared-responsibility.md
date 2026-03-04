---
title: "Shared Responsibility Model"
slug: shared-responsibility
category: cloud
tags: [aws, security, shared-responsibility, compliance, iam, encryption]
search_keywords: [AWS shared responsibility model, security of the cloud, security in the cloud, AWS customer responsibility, AWS managed services security, compliance, GDPR, PCI DSS, HIPAA, AWS compliance, patching, encryption, network controls]
parent: cloud/aws/fondamentali/_index
related: [cloud/aws/iam/_index, cloud/aws/security/_index, cloud/aws/fondamentali/well-architected]
official_docs: https://aws.amazon.com/compliance/shared-responsibility-model/
status: complete
difficulty: beginner
last_updated: 2026-03-03
---

# Shared Responsibility Model

Il **Modello di Responsabilità Condivisa** è il principio fondamentale della sicurezza AWS. Definisce cosa è responsabilità di AWS e cosa è responsabilità del cliente.

```
SHARED RESPONSIBILITY MODEL

┌─────────────────────────────────────────────────────────────┐
│                     CLIENTE                                  │
│  "Security IN the Cloud"                                     │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │   Data   │ │ Platform │ │   IAM    │ │   OS, Net,   │  │
│  │ cliente  │ │   App    │ │ (roles,  │ │   FW config  │  │
│  │ + cifrat.│ │          │ │ policies)│  │  (se EC2)   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                       AWS                                    │
│  "Security OF the Cloud"                                     │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  Compute │ │ Storage  │ │ Database │ │  Networking  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Physical Infrastructure                     │  │
│  │  (hardware, datacenter, network, AZ, Region)         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## AWS è Responsabile di: "Security OF the Cloud"

AWS garantisce la sicurezza dell'infrastruttura fisica e dei servizi gestiti:

**Infrastruttura fisica:**
- Sicurezza fisica dei datacenter (accessi biometrici, sorveglianza)
- Hardware dei server (host, network, storage)
- Networking globale (fibra, router, switch)
- AZ e Region (isolamento fisico)

**Hypervisor e virtualizzazione:**
- Hypervisor che isola le EC2 tra clienti diversi
- Patching del firmware e dell'hardware

**Servizi gestiti (Managed Services):**
- Per servizi come **RDS, Lambda, S3, DynamoDB** → AWS gestisce OS, patch, aggiornamenti
- AWS garantisce la disponibilità del servizio (SLA)

---

## Il Cliente è Responsabile di: "Security IN the Cloud"

Il cliente è responsabile di tutto ciò che mette nel cloud:

| Area | Responsabilità Cliente |
|------|------------------------|
| **Dati** | Classificazione, cifratura (at rest + in transit), backup |
| **IAM** | Gestione utenti, ruoli, policy, principio del minimo privilegio |
| **OS/Platform** | Patching OS (se EC2), aggiornamento librerie applicative |
| **Networking** | Security Groups, NACLs (Network Access Control Lists), VPC routing |
| **Firewall** | Configurazione delle regole di accesso |
| **Applicazione** | Sicurezza del codice, dipendenze vulnerabili |
| **Cifratura** | Abilitare/configurare KMS, TLS, cifratura S3 |

---

## Variazione per Tipo di Servizio

La responsabilità del cliente **cambia in base al tipo di servizio**:

=== "IaaS — EC2"

    | Responsabilità | AWS | Cliente |
    |----------------|-----|---------|
    | Hardware fisico | ✓ | |
    | Hypervisor | ✓ | |
    | OS (Windows/Linux) | | ✓ (patching incluso) |
    | Middleware (Apache, Nginx) | | ✓ |
    | Applicazione | | ✓ |
    | Security Groups | | ✓ (configurazione) |
    | Dati | | ✓ |
    | Cifratura EBS | | ✓ |

    **Massima responsabilità cliente — massima flessibilità**

=== "PaaS — RDS / Lambda"

    | Responsabilità | AWS | Cliente |
    |----------------|-----|---------|
    | Hardware fisico | ✓ | |
    | Hypervisor | ✓ | |
    | OS e patching OS | ✓ | |
    | Database engine patch (RDS) | ✓ | |
    | Configurazione DB (parametri) | | ✓ |
    | IAM per accesso al servizio | | ✓ |
    | Cifratura at rest / in transit | | ✓ (attivare) |
    | Dati inseriti | | ✓ |

    **AWS gestisce OS e middleware — cliente gestisce configurazione e dati**

=== "SaaS — S3 / DynamoDB"

    | Responsabilità | AWS | Cliente |
    |----------------|-----|---------|
    | Infrastruttura completa | ✓ | |
    | Durabilità (11 9s S3) | ✓ | |
    | Disponibilità (SLA 99.99%) | ✓ | |
    | Bucket Policy / ACL | | ✓ |
    | Cifratura oggetti | | ✓ (attivare SSE) |
    | Versioning e lifecycle | | ✓ (configurare) |
    | Blocco accesso pubblico | | ✓ (attivare) |
    | Dati e classificazione | | ✓ |

---

## Compliance Condivisa

Anche la **compliance** segue il modello condiviso:

- **AWS** fornisce: certificazioni (ISO 27001, SOC 1/2/3, PCI DSS, HIPAA BAA, FedRAMP), report di audit (AWS Artifact)
- **Cliente** deve: implementare controlli propri per mantenere compliance nell'uso dei servizi

**AWS Artifact** — repository di report di compliance scaricabili:
```bash
# AWS Artifact: disponibile via Console
# AWS → Artifact → Report
# Documenti disponibili: SOC 1/2/3, PCI DSS, ISO 27001, FedRAMP, GDPR...
```

**Framework di compliance supportati da AWS:**

| Framework | Descrizione |
|-----------|-------------|
| **GDPR** | Protezione dati EU — AWS è Data Processor, cliente è Data Controller |
| **PCI DSS** | Standard pagamenti — AWS ha QSA certificato |
| **HIPAA** | Sanità USA — BAA disponibile con AWS |
| **SOC 1/2/3** | Report controlli interni — scaricabili da Artifact |
| **ISO 27001** | Security management — AWS certificato |
| **FedRAMP** | US Government — AWS GovCloud |

---

## Regola Mnemonica per l'Esame

!!! tip "CLF-C02 — Regola d'oro"
    **AWS è responsabile** dell'hardware fisico, dell'hypervisor, della rete globale, e del runtime dei servizi gestiti.

    **Il cliente è responsabile** di tutto ciò che configura: IAM, cifratura, Security Groups, dati, OS (se EC2), applicazione.

    **Domanda tipo esame:** "Chi è responsabile del patching del database engine in RDS?"
    **Risposta:** AWS (perché RDS è un servizio gestito — il cliente non ha accesso all'OS)

    **Domanda tipo:** "Chi è responsabile del patching del sistema operativo su EC2?"
    **Risposta:** Il cliente (EC2 è IaaS — il cliente ha accesso root all'OS)

---

## Riferimenti

- [AWS Shared Responsibility Model](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [AWS Artifact](https://aws.amazon.com/artifact/)
- [AWS Compliance Programs](https://aws.amazon.com/compliance/programs/)
