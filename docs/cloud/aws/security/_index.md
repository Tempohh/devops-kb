---
title: "AWS Security"
slug: security
category: cloud
tags: [aws, security, kms, iam, waf, shield, guardduty, inspector, macie, config, cloudtrail, secrets-manager, acm]
search_keywords: [aws security, kms, secrets manager, parameter store, acm, waf, shield, network firewall, security groups, nacl, guardduty, inspector, macie, security hub, aws config, cloudtrail, compliance, encryption, iam, zero trust]
parent: cloud/aws/_index
related: [cloud/aws/security/kms-secrets, cloud/aws/security/network-security, cloud/aws/security/compliance-audit, cloud/aws/iam, cloud/aws/monitoring/cloudwatch]
official_docs: https://aws.amazon.com/security/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS Security

La sicurezza in AWS segue il modello del **Shared Responsibility Model**: AWS gestisce la sicurezza "del cloud" (infrastruttura fisica, hypervisor, rete globale), il cliente gestisce la sicurezza "nel cloud" (dati, accessi, configurazioni, applicazioni).

---

## Servizi Security AWS

<div class="grid cards" markdown>

-   **KMS, Secrets Manager, ACM**

    ---

    Gestione chiavi crittografiche (KMS), archiviazione sicura di secrets con rotazione automatica, certificati TLS (ACM), Parameter Store.

    [:octicons-arrow-right-24: KMS e Secrets Manager](kms-secrets.md)

-   **WAF, Shield, Network Firewall**

    ---

    Protezione layer 7 (WAF), DDoS protection (Shield), firewall managed a livello VPC (Network Firewall), Security Groups avanzati.

    [:octicons-arrow-right-24: Network Security](network-security.md)

-   **GuardDuty, Inspector, Macie, Config, CloudTrail**

    ---

    Threat detection ML-based (GuardDuty), vulnerability assessment (Inspector), data discovery (Macie), compliance (Config), audit log (CloudTrail).

    [:octicons-arrow-right-24: Compliance e Audit](compliance-audit.md)

</div>

---

## Shared Responsibility Model

```
┌──────────────────────────────────────────────────────────────┐
│                    RESPONSABILITÀ CLIENTE                     │
│                                                              │
│  Dati cliente          Gestione degli accessi (IAM)          │
│  Cifratura dati        Configurazione applicazioni           │
│  (client-side e        Network config (Security Groups,      │
│   server-side)         NACLs, VPC routing)                   │
│  Patching OS/DB        Compliance e auditing                 │
│  (istanze EC2,         Protezione a livello applicativo      │
│   on-premises)                                               │
├──────────────────────────────────────────────────────────────┤
│                    RESPONSABILITÀ AWS                         │
│                                                              │
│  Hardware fisico       Rete globale AWS                      │
│  Datacenter            Hypervisor                            │
│  Infrastruttura        Servizi managed (patching RDS,        │
│  globale               S3 hardware, Lambda runtime)         │
└──────────────────────────────────────────────────────────────┘
```

---

## Livelli di Sicurezza AWS

### Defense in Depth

Una buona architettura di sicurezza AWS applica controlli a ogni livello:

```
[Internet]
     │
[AWS WAF / AWS Shield]         ← Layer 7: protezione web + DDoS
     │
[CloudFront / ALB]             ← TLS termination, certificati ACM
     │
[Security Groups / NACLs]     ← Network layer: filtro traffico
     │
[EC2 / Lambda / ECS]          ← Compute: IAM roles, encryption
     │
[RDS / DynamoDB / S3]         ← Data: encryption at rest + in transit
     │
[AWS KMS]                      ← Key management per tutto lo stack
     │
[CloudTrail / GuardDuty]       ← Monitoring, audit, threat detection
     │
[AWS Config / Security Hub]   ← Compliance e aggregazione finding
```

### I Pilastri della Sicurezza AWS

| Pilastro | Servizi Chiave |
|---------|----------------|
| **Identity & Access Management** | IAM, IAM Identity Center, Cognito, Organizations |
| **Protezione Dati** | KMS, Secrets Manager, ACM, S3 encryption, Macie |
| **Protezione Infrastruttura** | Security Groups, NACLs, WAF, Shield, Network Firewall, VPC |
| **Detection & Threat Intelligence** | GuardDuty, Inspector, Macie, Security Hub |
| **Compliance e Governance** | AWS Config, CloudTrail, Audit Manager, Control Tower |
| **Incident Response** | Security Hub, EventBridge, Lambda (auto-remediation) |

---

## Quick Reference — Servizi Security

| Servizio | Categoria | Cosa Fa |
|---------|----------|---------|
| **AWS KMS** | Crittografia | Gestione chiavi, envelope encryption |
| **Secrets Manager** | Gestione secrets | Archivia e ruota automaticamente credenziali |
| **Parameter Store** | Configurazione | Store gerarchico per config e secrets leggeri |
| **ACM** | Certificati | Certificati TLS gratuiti per servizi AWS |
| **CloudHSM** | HSM | Hardware Security Module dedicato |
| **AWS WAF** | Firewall L7 | Blocca OWASP Top 10, SQL injection, XSS |
| **AWS Shield** | DDoS | Protezione DDoS automatica (Standard) e avanzata |
| **Network Firewall** | Firewall VPC | Stateful/stateless + Suricata IDS/IPS |
| **GuardDuty** | Threat Detection | ML-based detection su logs AWS |
| **Inspector** | Vulnerability | CVE scan su EC2, ECR, Lambda |
| **Macie** | Data Protection | PII detection su S3 |
| **Security Hub** | CSPM | Aggregatore centrale di finding e compliance |
| **AWS Config** | Compliance | Audit configurazioni, Config Rules |
| **CloudTrail** | Audit Log | Log di ogni API call AWS |
| **IAM Access Analyzer** | Access Analysis | Identifica accessi pubblici/cross-account |

---

## Concetti Fondamentali

### IAM Fundamentals

```
IAM Users → appartenenti a IAM Groups → con Policy attaccate
IAM Roles → assumibili da servizi AWS, utenti, account esterni
IAM Policies → documenti JSON che definiscono Allow/Deny su Action/Resource
```

**Policy Evaluation Logic:**
1. Default: tutto è DENY implicito
2. Se c'è un Deny esplicito → DENY (sovrascrive tutto)
3. Se c'è un Allow esplicito → ALLOW
4. Altrimenti → DENY implicito

**Principio del Minimo Privilegio:** concedere solo i permessi strettamente necessari.

### Cifratura in AWS

- **At rest:** dati archiviati — S3 SSE-KMS, EBS encryption, RDS encryption
- **In transit:** dati in movimento — TLS/SSL su tutte le comunicazioni
- **Client-side:** il cliente cifra prima di inviare ad AWS

### Compliance AWS

AWS ha oltre 150 certificazioni di conformità. Strumenti di supporto:
- **AWS Artifact:** scaricare report di conformità AWS (SOC, PCI DSS, ISO)
- **Audit Manager:** raccolta automatica di prove per audit
- **Control Tower:** guardrails di sicurezza multi-account
- **Security Hub:** compliance standards automatizzati (CIS, PCI DSS, NIST)

---

## Riferimenti

- [AWS Security Documentation](https://docs.aws.amazon.com/security/)
- [AWS Well-Architected Framework — Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/)
- [AWS Security Blog](https://aws.amazon.com/blogs/security/)
- [AWS Shared Responsibility Model](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [CIS AWS Benchmarks](https://www.cisecurity.org/benchmark/amazon_web_services)
