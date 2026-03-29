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
last_updated: 2026-03-28
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

## Troubleshooting

### Scenario 1 — S3 bucket accessibile pubblicamente per errore

**Sintomo:** Dati esposti pubblicamente; alert da AWS Security Hub o Trusted Advisor: "S3 bucket is publicly accessible".

**Causa:** Il cliente ha configurato erroneamente la bucket policy o non ha attivato il "Block Public Access" — responsabilità del cliente secondo il modello condiviso.

**Soluzione:** Attivare immediatamente il blocco accesso pubblico e rivedere la policy.

```bash
# Blocca accesso pubblico su un bucket specifico
aws s3api put-public-access-block \
  --bucket my-bucket \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Verifica lo stato
aws s3api get-public-access-block --bucket my-bucket

# Audit: trova tutti i bucket pubblici nell'account
aws s3api list-buckets --query 'Buckets[].Name' --output text | \
  xargs -I {} aws s3api get-public-access-block --bucket {}
```

---

### Scenario 2 — EC2 compromessa: OS non aggiornato

**Sintomo:** Notifica da Amazon Inspector o GuardDuty di vulnerabilità critica su istanza EC2; exploit noto sull'OS.

**Causa:** Il patching del sistema operativo su EC2 è responsabilità del cliente (IaaS). Il cliente non aveva attivato patch management automatico.

**Soluzione:** Applicare patch immediatamente tramite AWS Systems Manager Patch Manager.

```bash
# Esegui patching immediato via SSM su istanza specifica
aws ssm send-command \
  --instance-ids "i-0123456789abcdef0" \
  --document-name "AWS-RunPatchBaseline" \
  --parameters '{"Operation":["Install"]}' \
  --comment "Emergency security patching"

# Verifica stato patch
aws ssm describe-instance-patch-states \
  --instance-ids "i-0123456789abcdef0"

# Configura patching automatico (baseline di default)
aws ssm create-patch-baseline \
  --name "AutoPatchBaseline" \
  --operating-system "AMAZON_LINUX_2" \
  --approval-rules '{"PatchRules":[{"PatchFilterGroup":{"PatchFilters":[{"Key":"SEVERITY","Values":["Critical","Important"]}]},"ApproveAfterDays":7}]}'
```

---

### Scenario 3 — Credenziali IAM esposte in un repository pubblico

**Sintomo:** Alert di AWS (email o GuardDuty) per utilizzo anomalo di access key; oppure chiave trovata in commit GitHub.

**Causa:** La gestione delle credenziali IAM è responsabilità esclusiva del cliente. AWS non può impedire che il cliente esponga le proprie chiavi.

**Soluzione:** Revocare immediatamente la chiave compromessa, analizzare l'accesso, e ruotare le credenziali.

```bash
# 1. Disabilita immediatamente la chiave compromessa
aws iam update-access-key \
  --access-key-id AKIAIOSFODNN7EXAMPLE \
  --status Inactive \
  --user-name my-user

# 2. Verifica le azioni eseguite con la chiave (ultimi 90 giorni)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=AccessKeyId,AttributeValue=AKIAIOSFODNN7EXAMPLE \
  --max-results 50

# 3. Elimina la chiave compromessa e creane una nuova
aws iam delete-access-key \
  --access-key-id AKIAIOSFODNN7EXAMPLE \
  --user-name my-user

aws iam create-access-key --user-name my-user
```

---

### Scenario 4 — Confusione su chi gestisce il patching di RDS

**Sintomo:** Il team di sicurezza segnala che il database engine RDS non è aggiornato all'ultima versione; si chiede chi deve agire.

**Causa:** Fraintendimento del modello condiviso: per RDS (PaaS), AWS gestisce il patching del database engine e dell'OS sottostante. Il cliente non ha accesso diretto all'OS.

**Soluzione:** Verificare la versione e la policy di manutenzione automatica; per aggiornamenti di versione major, il cliente deve pianificare la migrazione.

```bash
# Verifica versione engine e prossimo maintenance window
aws rds describe-db-instances \
  --query 'DBInstances[*].{ID:DBInstanceIdentifier,Engine:Engine,Version:EngineVersion,AutoMinorUpgrade:AutoMinorVersionUpgrade,MaintenanceWindow:PreferredMaintenanceWindow}'

# Attiva aggiornamenti automatici per minor versions (responsabilità configurazione: cliente)
aws rds modify-db-instance \
  --db-instance-identifier my-db \
  --auto-minor-version-upgrade \
  --apply-immediately

# Verifica gli aggiornamenti pending
aws rds describe-db-instances \
  --db-instance-identifier my-db \
  --query 'DBInstances[0].PendingModifiedValues'
```

---

## Riferimenti

- [AWS Shared Responsibility Model](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [AWS Artifact](https://aws.amazon.com/artifact/)
- [AWS Compliance Programs](https://aws.amazon.com/compliance/programs/)
