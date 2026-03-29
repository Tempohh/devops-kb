---
title: "AWS Organizations & Multi-Account"
slug: organizations
category: cloud
tags: [aws, organizations, scp, control-tower, iam-identity-center, sso, multi-account, landing-zone, ou, management-account]
search_keywords: [AWS Organizations, Service Control Policy, SCP, AWS Control Tower, IAM Identity Center, AWS SSO, Single Sign-On, Landing Zone, multi-account strategy, management account, member account, organizational unit, OU, consolidated billing, account vending machine, guardrails, permission sets, SAML 2.0]
parent: cloud/aws/iam/_index
related: [cloud/aws/iam/_index, cloud/aws/iam/policies-avanzate, cloud/aws/fondamentali/billing-pricing]
official_docs: https://docs.aws.amazon.com/organizations/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# AWS Organizations & Multi-Account

## Perché Multi-Account?

La strategia **multi-account** è il pattern di riferimento per organizzazioni AWS mature:

| Motivazione | Dettaglio |
|-------------|-----------|
| **Security Isolation** | Account separati = blast radius limitato in caso di breach |
| **Billing separation** | Costi per team/BU/environment chiari e separati |
| **Service Limits** | Ogni account ha limiti indipendenti (no contesa tra team) |
| **Compliance** | Ambienti regolamentati (PCI — Payment Card Industry, HIPAA — Health Insurance Portability and Accountability Act) in account dedicati |
| **Governance** | Policy centrali applicate a tutti gli account |

---

## AWS Organizations

**AWS Organizations** gestisce più account AWS in una gerarchia.

```
Organizations Structure

  Management Account (root)
  └── Root
      ├── OU: Security
      │   ├── Account: Log Archive
      │   └── Account: Security Tooling
      ├── OU: Infrastructure
      │   ├── Account: Network (Transit Gateway)
      │   └── Account: Shared Services
      ├── OU: Workloads
      │   ├── OU: Production
      │   │   ├── Account: App-Team-A-Prod
      │   │   └── Account: App-Team-B-Prod
      │   └── OU: Development
      │       ├── Account: App-Team-A-Dev
      │       └── Account: App-Team-B-Dev
      └── OU: Sandbox
          └── Account: Developer-Sandbox
```

**Componenti:**
- **Management Account** (ex "Master") — account che crea l'Organization, ha pieno controllo
- **Member Accounts** — account figli, gestiti dall'Organization
- **Organizational Units (OU)** — gruppi logici di account (fino a 5 livelli di nesting)
- **Root** — nodo padre di tutta la gerarchia

```bash
# Creare Organization
aws organizations create-organization --feature-set ALL

# Creare OU
aws organizations create-organizational-unit \
    --parent-id r-xxxx \            # Root ID
    --name "Production"

# Creare account membro
aws organizations create-account \
    --email new-account@company.com \
    --account-name "App-Team-A-Prod" \
    --iam-user-access-to-billing ALLOW \
    --role-name OrganizationAccountAccessRole

# Listare tutti gli account
aws organizations list-accounts \
    --query 'Accounts[*].{Name:Name,Id:Id,Status:Status}' \
    --output table

# Muovere un account in un'OU
aws organizations move-account \
    --account-id 123456789012 \
    --source-parent-id r-xxxx \
    --destination-parent-id ou-xxxx-yyyyyyy
```

---

## Service Control Policies (SCP)

Le **SCP** sono policy applicate a OU o account — definiscono il **massimo** dei permessi consentiti per tutti i principal (utenti e ruoli) in quell'account.

!!! warning "SCP non si applicano al Management Account"
    Il Management Account non è soggetto alle SCP — usare con cautela questo account.

**Caratteristiche:**
- Le SCP NON concedono permessi — definiscono solo i limiti
- Un Allow in SCP NON basta: serve anche Allow nelle policy IAM dell'identity
- Un Deny in SCP blocca tutto, anche gli admin dell'account
- Ereditarietà: OU figlio eredita SCP del padre (intersezione)

```json
// SCP: Nega operazioni fuori dalla Region EU
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyNonEURegions",
    "Effect": "Deny",
    "Action": "*",
    "Resource": "*",
    "Condition": {
      "StringNotEquals": {
        "aws:RequestedRegion": [
          "eu-central-1",
          "eu-west-1",
          "eu-west-2",
          "eu-west-3",
          "eu-south-1",
          "eu-north-1"
        ]
      },
      "ArnNotLike": {
        // Escludi servizi globali che non hanno Region
        "aws:PrincipalArn": [
          "arn:aws:iam::*:role/OrganizationAccountAccessRole"
        ]
      }
    }
  }]
}
```

```json
// SCP: Proteggi CloudTrail e Config dalla disabilitazione
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyDisableCloudTrail",
      "Effect": "Deny",
      "Action": [
        "cloudtrail:StopLogging",
        "cloudtrail:DeleteTrail",
        "cloudtrail:UpdateTrail"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyDisableConfig",
      "Effect": "Deny",
      "Action": [
        "config:StopConfigurationRecorder",
        "config:DeleteConfigurationRecorder",
        "config:DeleteDeliveryChannel"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyLeaveOrganization",
      "Effect": "Deny",
      "Action": "organizations:LeaveOrganization",
      "Resource": "*"
    }
  ]
}
```

```json
// SCP: Require tag su risorse create
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "RequireTagsOnEC2",
    "Effect": "Deny",
    "Action": "ec2:RunInstances",
    "Resource": "arn:aws:ec2:*:*:instance/*",
    "Condition": {
      "Null": {
        "aws:RequestTag/Environment": "true"
      }
    }
  }]
}
```

```bash
# Creare SCP
aws organizations create-policy \
    --name "DenyNonEURegions" \
    --type SERVICE_CONTROL_POLICY \
    --description "Deny all operations outside EU regions" \
    --content file://scp-deny-non-eu.json

# Allegare SCP a OU
aws organizations attach-policy \
    --policy-id p-xxxxxxxxxxxx \
    --target-id ou-xxxx-yyyyyyy

# Allegare SCP a account specifico
aws organizations attach-policy \
    --policy-id p-xxxxxxxxxxxx \
    --target-id 123456789012

# Listare policy effettive su un account
aws organizations list-policies-for-target \
    --target-id 123456789012 \
    --filter SERVICE_CONTROL_POLICY
```

---

## Delegated Administrator

Organizations permette di delegare la gestione di specifici servizi a account non-Management:

```bash
# Delegare SecurityHub all'account Security Tooling
aws organizations register-delegated-administrator \
    --account-id SECURITY_TOOLING_ACCOUNT \
    --service-principal securityhub.amazonaws.com

# Servizi che supportano Delegated Admin (selezione):
# - SecurityHub
# - GuardDuty
# - AWS Config
# - Macie
# - Inspector
# - IAM Access Analyzer
# - Firewall Manager
```

---

## AWS Control Tower

**Control Tower** automatizza il setup di un multi-account AWS secondo le best practices — è l'**Account Factory** enterprise.

```
Control Tower Components

  ┌──────────────────────────────────────────────┐
  │             Control Tower                    │
  │                                              │
  │  ┌──────────────┐  ┌──────────────────────┐  │
  │  │   Landing    │  │     Guardrails        │  │
  │  │    Zone      │  │  (SCP + Config rules) │  │
  │  │  (baseline   │  │  Preventive: SCP      │  │
  │  │   accounts)  │  │  Detective: Config    │  │
  │  └──────────────┘  └──────────────────────┘  │
  │                                              │
  │  ┌──────────────────────────────────────────┐ │
  │  │       Account Factory                    │ │
  │  │  (provisioning automatico nuovi account) │ │
  │  └──────────────────────────────────────────┘ │
  └──────────────────────────────────────────────┘
```

**Landing Zone baseline accounts:**
- **Management Account** — Organizations, Control Tower
- **Log Archive Account** — CloudTrail logs, Config history (read-only)
- **Audit Account** — Security tooling, cross-account read access

**Guardrails (ora chiamati Controls):**

| Tipo | Meccanismo | Esempio |
|------|-----------|---------|
| **Preventive** | SCP | "Deny root user access" |
| **Detective** | AWS Config Rule | "Detect EC2 without encryption" |
| **Proactive** | CloudFormation Hooks | "Check before resource creation" |

**Stato guardrail:**
- `MANDATORY` — sempre attivi, non disabilitabili
- `STRONGLY RECOMMENDED` — best practice, disabilitabili
- `ELECTIVE` — opzionali per esigenze specifiche

**Account Factory:**
```bash
# Account Factory via Service Catalog (o Account Factory for Terraform)
# Provisiona automaticamente nuovo account con:
# - Baseline OU
# - IAM Identity Center access configurato
# - Guardrails applicati
# - VPC baseline (opzionale)
# - Tag obbligatori
```

---

## IAM Identity Center (ex AWS SSO)

**IAM Identity Center** è il punto di accesso SSO (Single Sign-On) centralizzato per tutti gli account AWS dell'Organization.

```
IAM Identity Center Flow

  Corporate IdP (Okta/Azure AD/AD)
         ↓ SAML 2.0 / OIDC
  IAM Identity Center
         ↓
  Permission Sets (= role templates)
         ↓
  Account Assignment
         ↓
  Role in member account
```

**Componenti:**
- **Identity Source** — dove risiedono le identità: Identity Center directory, Active Directory (AWS Managed AD / AD Connector), External IdP (Identity Provider — SAML 2.0 — Security Assertion Markup Language)
- **Permission Sets** — template di policy che diventano IAM Roles negli account
- **Account Assignment** — mappatura User/Group → PermissionSet → Account

```bash
# Identity Center: configurazione via Console (raccomandato)
# CLI disponibile ma complessa

# Listare permission sets
aws sso-admin list-permission-sets \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx

# Creare permission set
aws sso-admin create-permission-set \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx \
    --name "DevOpsEngineer" \
    --description "DevOps Engineer access" \
    --session-duration PT8H

# Allegare policy managed al permission set
aws sso-admin attach-managed-policy-to-permission-set \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx \
    --permission-set-arn arn:aws:sso:::permissionSet/ssoins-xxxx/ps-xxxx \
    --managed-policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Assegnare permission set a un gruppo su un account
aws sso-admin create-account-assignment \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx \
    --target-id 123456789012 \
    --target-type AWS_ACCOUNT \
    --permission-set-arn arn:aws:sso:::permissionSet/ssoins-xxxx/ps-xxxx \
    --principal-type GROUP \
    --principal-id "GROUP_ID_FROM_IDENTITY_STORE"
```

**Accesso programmatico con Identity Center:**
```bash
# CLI v2: login SSO automatico
aws configure sso
# → URL: https://company.awsapps.com/start
# → Region SSO: eu-central-1
# → Account: 123456789012
# → Role: DevOpsEngineer

# Login
aws sso login --profile my-sso-profile

# Usare il profilo
aws s3 ls --profile my-sso-profile

# Refresh automatico token
# ~/.aws/config
# [profile devops-prod]
# sso_session = company-sso
# sso_account_id = 123456789012
# sso_role_name = DevOpsEngineer
# region = eu-central-1
```

---

## Pattern Cross-Account Role

Pattern per accedere a risorse in account diversi senza IAM Identity Center:

```
Account A (developer)                  Account B (produzione)
─────────────────────                  ───────────────────────
IAM User Alice                         Cross-Account Role
  └── Policy:                          Trust Policy:
      Allow sts:AssumeRole               Principal:
      Resource: AccountB/Role             AWS: Account-A

           ──── sts:AssumeRole ────────────→
           ←──── Temporary Credentials ────
```

```bash
# In Account B: creare il role con trust policy per Account A
# trust-policy.json:
# {
#   "Principal": {"AWS": "arn:aws:iam::ACCOUNT_A:root"},
#   "Condition": {"StringEquals": {"sts:ExternalId": "unique-secret"}}
# }

# In Account A: assumere il role
aws sts assume-role \
    --role-arn arn:aws:iam::ACCOUNT_B:role/AdminRole \
    --role-session-name cross-account-session \
    --external-id "unique-secret"

# Profile AWS CLI per cross-account automatico
# ~/.aws/config:
# [profile account-b-admin]
# role_arn = arn:aws:iam::ACCOUNT_B:role/AdminRole
# source_profile = default  # credenziali Account A
# external_id = unique-secret
```

---

## Tag Policy

Le **Tag Policy** controllano l'utilizzo dei tag in modo centralizzato nell'Organization.

```json
// Tag Policy: obbliga tag "Environment" con valori specifici
{
  "tags": {
    "Environment": {
      "tag_key": {
        "@@assign": "Environment"
      },
      "tag_value": {
        "@@assign": ["Production", "Staging", "Development", "Sandbox"]
      },
      "enforced_for": {
        "@@assign": ["ec2:instance", "rds:db", "s3:bucket"]
      }
    },
    "Owner": {
      "tag_key": {
        "@@assign": "Owner"
      }
    }
  }
}
```

---

## Troubleshooting

### Scenario 1 — SCP blocca azioni anche agli amministratori dell'account

**Sintomo:** Un utente con `AdministratorAccess` riceve `AccessDenied` su operazioni che dovrebbe poter fare (es. `ec2:RunInstances`, `s3:PutObject`).

**Causa:** Una SCP applicata all'OU o all'account nega esplicitamente l'azione. Le SCP hanno precedenza su qualsiasi policy IAM, incluse le policy managed AWS. Un Deny in SCP non è superabile nemmeno da admin dell'account.

**Soluzione:** Identificare la SCP che causa il blocco e verificarne il contenuto.
```bash
# Identificare le SCP applicate all'account
aws organizations list-policies-for-target \
    --target-id 123456789012 \
    --filter SERVICE_CONTROL_POLICY \
    --output table

# Ottenere il contenuto di una SCP specifica
aws organizations describe-policy \
    --policy-id p-xxxxxxxxxxxx \
    --query 'Policy.Content' \
    --output text | python -m json.tool

# Verificare l'intera catena di OU (padre eredita SCP figlio)
aws organizations list-parents --child-id 123456789012
aws organizations list-parents --child-id ou-xxxx-yyyyyyy  # OU padre
```

---

### Scenario 2 — IAM Identity Center: utente non riesce ad accedere a un account

**Sintomo:** L'utente vede il portale SSO ma l'account target non compare nella lista, oppure compare ma il login fallisce con "You do not have access to this application".

**Causa:** Manca l'Account Assignment: il gruppo/utente non è stato assegnato al PermissionSet su quell'account. Oppure il PermissionSet non è stato eseguito il provisioning nell'account (provisioning pending).

**Soluzione:**
```bash
# Verificare le assegnazioni per un account specifico
aws sso-admin list-account-assignments \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx \
    --account-id 123456789012 \
    --permission-set-arn arn:aws:sso:::permissionSet/ssoins-xxxx/ps-xxxx

# Verificare lo stato del provisioning del permission set
aws sso-admin list-permission-sets-provisioned-to-account \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx \
    --account-id 123456789012

# Forzare re-provisioning del permission set su tutti gli account
aws sso-admin provision-permission-set \
    --instance-arn arn:aws:sso:::instance/ssoins-xxxx \
    --permission-set-arn arn:aws:sso:::permissionSet/ssoins-xxxx/ps-xxxx \
    --target-type ALL_PROVISIONED_ACCOUNTS
```

---

### Scenario 3 — Creazione account membro fallisce o rimane in stato PENDING

**Sintomo:** `aws organizations create-account` completa senza errori ma l'account rimane in stato `IN_PROGRESS` o `FAILED` per lungo tempo.

**Causa:** AWS richiede un indirizzo email unico per ogni account. Cause comuni: email già usata da un altro account AWS (anche fuori dall'Organization), limiti di creazione account raggiunti (default: 10 account), o problemi di verifica email.

**Soluzione:**
```bash
# Controllare lo stato della richiesta di creazione account
aws organizations describe-create-account-status \
    --create-account-request-id car-xxxxxxxxxxxx

# Listare tutti gli account con stato
aws organizations list-accounts \
    --query 'Accounts[*].{Name:Name,Status:Status,Email:Email}' \
    --output table

# In caso di FAILED: verificare il motivo
aws organizations describe-create-account-status \
    --create-account-request-id car-xxxxxxxxxxxx \
    --query 'CreateAccountStatus.FailureReason'

# Per superare il limite di account: richiedere aumento quota via Support
aws service-quotas request-service-quota-increase \
    --service-code organizations \
    --quota-code L-29A0C5DF \
    --desired-value 50
```

---

### Scenario 4 — Cross-Account AssumeRole fallisce con "Not authorized to assume role"

**Sintomo:** `aws sts assume-role` restituisce `AccessDenied: User is not authorized to assume role`.

**Causa 1:** La Trust Policy del role nell'account target non include il principal corretto (account source o specifica ARN). **Causa 2:** La policy IAM dell'utente nell'account source non include `sts:AssumeRole` sulla risorsa ARN del role. **Causa 3:** `ExternalId` mancante o errato nella Trust Policy.

**Soluzione:**
```bash
# Verificare la Trust Policy del role nell'account target
# (eseguire dall'account target o con accesso cross-account esistente)
aws iam get-role \
    --role-name AdminRole \
    --query 'Role.AssumeRolePolicyDocument' \
    --output json

# Verificare che l'utente source abbia sts:AssumeRole
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::ACCOUNT_A:user/alice \
    --action-names sts:AssumeRole \
    --resource-arns arn:aws:iam::ACCOUNT_B:role/AdminRole

# Testare assume-role con debug verboso
aws sts assume-role \
    --role-arn arn:aws:iam::ACCOUNT_B:role/AdminRole \
    --role-session-name test-session \
    --external-id "unique-secret" \
    --debug 2>&1 | grep -E "(AccessDenied|AssumeRole|error)"

# Verificare l'identità corrente e account ID
aws sts get-caller-identity
```

---

## Riferimenti

- [AWS Organizations](https://docs.aws.amazon.com/organizations/latest/userguide/)
- [Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [AWS Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/)
- [IAM Identity Center](https://docs.aws.amazon.com/singlesignon/latest/userguide/)
- [Multi-Account Best Practices](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/)
