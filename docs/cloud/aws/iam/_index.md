---
title: "AWS IAM — Identity & Access Management"
slug: iam
category: cloud
tags: [aws, iam, identity, access-management, users, groups, roles, policies, mfa, sts, federation]
search_keywords: [AWS IAM, Identity Access Management, IAM user, IAM group, IAM role, IAM policy, MFA, multi-factor authentication, least privilege, IAM best practices, STS, assume role, IAM Identity Center, SSO, SAML, OIDC, Cognito, cross-account, permission boundaries, service control policy, SCP]
parent: cloud/aws/_index
related: [cloud/aws/fondamentali/shared-responsibility, cloud/aws/iam/policies-avanzate, cloud/aws/iam/organizations, cloud/aws/security/_index]
official_docs: https://docs.aws.amazon.com/iam/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS IAM — Identity & Access Management

**IAM** è il servizio **globale** di AWS per gestire l'accesso alle risorse. Non ha Region — è unico per account.

!!! warning "IAM è fondamentale"
    IAM è trasversale a tutte le certificazioni AWS. Non esiste servizio AWS che non coinvolga IAM. Investire tempo su IAM ripaga in tutte le aree.

---

## Componenti Fondamentali

```
IAM Components

  ┌─────────┐    appartiene a     ┌─────────┐
  │  User   │ ─────────────────→  │  Group  │
  └────┬────┘                     └────┬────┘
       │ ha allegato                    │ ha allegato
       ↓                                ↓
  ┌──────────────────────────────────────────┐
  │                  Policy                  │
  │  {Effect, Action, Resource, Condition}   │
  └──────────────────────────────────────────┘
       ↑ ha allegato
  ┌─────────┐    assumed by      ┌─────────────┐
  │  Role   │ ←────────────────  │  Principal  │
  └─────────┘                   │ (user/svc/  │
                                │  account)   │
                                └─────────────┘
```

---

## IAM Users

Un **IAM User** è un'identità permanente con credenziali proprie.

**Tipi di accesso:**
- **Console password** — accesso AWS Management Console
- **Access Keys** (Access Key ID + Secret Access Key) — accesso programmatico (CLI, SDK, API)
- **MFA** — secondo fattore (TOTP, hardware FIDO2, SMS)

**Best practices:**
- Non usare **root account** per operazioni ordinarie (solo setup iniziale + emergenze)
- Abilitare **MFA** su root e su tutti gli utenti privilegiati
- **Ruotare le access keys** regolarmente (o usare IAM Roles per evitare keys)
- Applicare il **principio del minimo privilegio**

```bash
# Creare un IAM user
aws iam create-user --user-name alice

# Creare access key
aws iam create-access-key --user-name alice

# Abilitare MFA (virtual MFA device)
aws iam enable-mfa-device \
    --user-name alice \
    --serial-number arn:aws:iam::123456789012:mfa/alice \
    --authentication-code1 123456 \
    --authentication-code2 789012

# Listare utenti
aws iam list-users \
    --query 'Users[*].{User:UserName,Created:CreateDate}' \
    --output table

# IAM Credential Report — stato di tutti gli utenti/credenziali
aws iam generate-credential-report
aws iam get-credential-report --query 'Content' --output text | base64 -d
```

---

## IAM Groups

Un **IAM Group** è una raccolta di utenti con policy comuni.

- Un utente può appartenere a più gruppi (max 10 per utente)
- I gruppi **non possono essere nestati** (gruppi dentro gruppi non supportati)
- Le policy del gruppo si applicano a tutti i membri

```bash
# Creare gruppo e aggiungere policy
aws iam create-group --group-name Developers

aws iam attach-group-policy \
    --group-name Developers \
    --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Aggiungere utente al gruppo
aws iam add-user-to-group --group-name Developers --user-name alice
```

**Struttura tipica dei gruppi:**
- `Admins` → AdministratorAccess
- `Developers` → PowerUserAccess (no IAM)
- `ReadOnly` → ReadOnlyAccess
- `Billing` → Billing + CostExplorer

---

## IAM Roles

Un **IAM Role** è un'identità **temporanea** assunta da un principal (utente, servizio, account).

**Quando si usa un Role:**
- EC2 instance che deve accedere a S3 → **EC2 Instance Profile** (role)
- Lambda che scrive su DynamoDB → **Lambda Execution Role**
- Cross-account: Account A accede a risorse Account B → **Cross-Account Role**
- Utenti federati (SAML/OIDC) → **Federated Identity Role**
- AWS services che agiscono per conto tuo (es. CloudFormation crea risorse)

**Componenti di un Role:**
- **Trust Policy** — chi può assumere il role (`sts:AssumeRole`)
- **Permission Policy** — cosa può fare chi assume il role

```json
// Trust Policy — chi può assumere questo role
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "ec2.amazonaws.com"     // EC2 può assumere questo role
    },
    "Action": "sts:AssumeRole"
  }]
}
```

```bash
# Creare role per EC2
aws iam create-role \
    --role-name MyEC2Role \
    --assume-role-policy-document file://trust-policy.json

# Allegare policy al role
aws iam attach-role-policy \
    --role-name MyEC2Role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Creare instance profile (necessario per EC2)
aws iam create-instance-profile --instance-profile-name MyEC2Profile
aws iam add-role-to-instance-profile \
    --instance-profile-name MyEC2Profile \
    --role-name MyEC2Role

# Assumere un role (cross-account o testing)
aws sts assume-role \
    --role-arn arn:aws:iam::ACCOUNT_B:role/CrossAccountRole \
    --role-session-name MySession \
    --duration-seconds 3600
# Restituisce: AccessKeyId, SecretAccessKey, SessionToken (temporanei)

# Usare le credenziali temporanee
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```

---

## IAM Policies

Una **Policy** è un documento JSON che definisce i permessi.

**Struttura:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3Read",              // opzionale: Statement ID
      "Effect": "Allow",                 // Allow | Deny
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket",
        "arn:aws:s3:::my-bucket/*"
      ],
      "Condition": {                     // opzionale
        "StringEquals": {
          "aws:RequestedRegion": "eu-central-1"
        }
      }
    }
  ]
}
```

**Tipi di policy:**

| Tipo | Attaccata a | Gestione |
|------|------------|---------|
| **AWS Managed** | User/Group/Role | AWS (aggiornata automaticamente) |
| **Customer Managed** | User/Group/Role | Tu (controllo completo) |
| **Inline** | Solo 1 entity | Embedded, 1:1 relationship |
| **Resource-based** | Risorsa (S3, SQS...) | Sulla risorsa stessa |
| **Permission Boundaries** | User/Role | Limita massima autorizzazione |
| **Service Control Policy (SCP)** | OU/Account | Solo con Organizations |
| **Session Policy** | STS session | Temporanea, al momento di AssumeRole |

**Logica di valutazione (Evaluation Logic):**
```
1. Explicit DENY? → DENY (sempre vince)
2. SCP (Organizations) ALLOW? → continua
3. Resource-based policy ALLOW? → ALLOW
4. Identity-based policy ALLOW? → ALLOW
5. Permission Boundary ALLOW? → continua
6. Default: DENY
```

```bash
# Policy comuni AWS Managed
arn:aws:iam::aws:policy/AdministratorAccess      # full admin
arn:aws:iam::aws:policy/PowerUserAccess          # tutto tranne IAM
arn:aws:iam::aws:policy/ReadOnlyAccess           # sola lettura tutto
arn:aws:iam::aws:policy/AmazonS3FullAccess       # S3 completo
arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess  # EC2 read only

# Creare customer managed policy
aws iam create-policy \
    --policy-name MyS3Policy \
    --policy-document file://s3-policy.json

# Simulare l'effetto di una policy (IAM Policy Simulator)
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:user/alice \
    --action-names s3:GetObject \
    --resource-arns arn:aws:s3:::my-bucket/file.txt
```

---

## ARN — Amazon Resource Names

Gli ARN identificano univocamente ogni risorsa AWS:

```
arn:partition:service:region:account-id:resource-type/resource-id

Esempi:
arn:aws:iam::123456789012:user/alice          # IAM User (no region)
arn:aws:iam::123456789012:role/MyRole         # IAM Role
arn:aws:s3:::my-bucket                        # S3 Bucket (no region, no account)
arn:aws:s3:::my-bucket/*                      # Tutti gli oggetti in my-bucket
arn:aws:ec2:eu-central-1:123456789012:instance/i-abc123
arn:aws:lambda:eu-west-1:123456789012:function:my-function
```

Wildcard nei Resource ARN:
- `*` → qualsiasi sequenza di caratteri
- `?` → un singolo carattere
- `arn:aws:s3:::*` → tutti i bucket S3

---

## IAM Best Practices (AWS Raccomanda)

1. **Lock away root account credentials** — MFA su root, non usare per operazioni
2. **Create individual IAM users** — no sharing di credenziali
3. **Use groups to assign permissions** — policy su gruppi, non su singoli utenti
4. **Grant least privilege** — inizia con 0 permessi, aggiungi solo il necessario
5. **Enable MFA for privileged users** — in particolare admin
6. **Use IAM Roles for applications on EC2** — mai access keys hardcoded
7. **Use roles to delegate access** — cross-account via role, non via user
8. **Rotate credentials regularly** — access keys + passwords
9. **Use IAM Access Analyzer** — identifica accessi pubblici e cross-account inattesi
10. **Monitor activity with CloudTrail** — ogni chiamata API è loggata

---

## IAM Access Analyzer

**IAM Access Analyzer** identifica risorse con accesso **pubblico o cross-account non intenzionale**.

```bash
# Creare analyzer (analizza la Region)
aws accessanalyzer create-analyzer \
    --analyzer-name MyAnalyzer \
    --type ACCOUNT          # ACCOUNT o ORGANIZATION

# Listare i findings
aws accessanalyzer list-findings \
    --analyzer-arn arn:aws:access-analyzer:eu-central-1:123456789012:analyzer/MyAnalyzer \
    --filter '{"status": {"eq": ["ACTIVE"]}}'
```

Analizza: S3 bucket policies, IAM roles, KMS keys, Lambda, SQS queues, Secrets Manager secrets

---

## Sezioni Avanzate

<div class="grid cards" markdown>

- :material-file-document-multiple: **[Policies Avanzate](policies-avanzate.md)**

    Conditions, Permission Boundaries, Resource-based policies, Policy evaluation deep dive

- :material-domain: **[Organizations & Multi-Account](organizations.md)**

    AWS Organizations, SCPs, Control Tower, IAM Identity Center, Landing Zone

</div>

---

## Riferimenti

- [IAM Documentation](https://docs.aws.amazon.com/iam/latest/userguide/)
- [IAM Best Practices](https://docs.aws.amazon.com/iam/latest/userguide/best-practices.html)
- [IAM Policy Reference](https://docs.aws.amazon.com/iam/latest/userguide/reference_policies.html)
- [IAM Access Analyzer](https://docs.aws.amazon.com/access-analyzer/latest/APIReference/)
