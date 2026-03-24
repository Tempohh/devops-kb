---
title: "IAM Policies Avanzate"
slug: policies-avanzate
category: cloud
tags: [aws, iam, policies, conditions, permission-boundaries, resource-based, STS, session-policy, policy-evaluation, abac, rbac]
search_keywords: [IAM policy conditions, IAM StringEquals, IAM aws:RequestedRegion, IAM permission boundaries, IAM resource-based policy, IAM cross-account policy, IAM session policy, IAM ABAC, attribute-based access control, IAM tags conditions, IAM policy evaluation logic, IAM deny, IAM PassRole, IAM explicit deny, IAM policy simulator, IAM inline vs managed]
parent: cloud/aws/iam/_index
related: [cloud/aws/iam/_index, cloud/aws/iam/organizations, cloud/aws/security/compliance-audit]
official_docs: https://docs.aws.amazon.com/iam/latest/userguide/access_policies.html
status: complete
difficulty: advanced
last_updated: 2026-03-09
---

# IAM Policies Avanzate

Questo documento approfondisce i meccanismi avanzati di IAM che permettono di costruire sistemi di accesso precisi, scalabili e sicuri. Si presuppone la conoscenza dei concetti base di IAM (Users, Groups, Roles e Policies): se sei nuovo su IAM, inizia dalla [pagina principale IAM](_index.md).

I temi trattati qui — Conditions, ABAC, Permission Boundaries, Resource-based Policies e STS — diventano rilevanti quando le policy semplici non bastano più: ad esempio quando devi scalare la gestione dei permessi su decine di team, controllare l'accesso in base al contesto della richiesta (da dove arriva, con quale MFA, in quale Region), o delegare la creazione di identità ad altri senza perdere il controllo.

---

## Prerequisiti

Questo argomento presuppone familiarità con:
- [IAM — Introduzione](../iam/_index.md) — utenti, gruppi, ruoli, policy base, evaluation logic: tutti questi concetti sono prerequisiti per le tecniche avanzate
- Almeno un caso d'uso reale con IAM — le tecniche avanzate (ABAC, Permission Boundaries, STS) hanno senso solo quando si è già lavorato con policy semplici e si è incontrato il loro limite (documentazione esperienziale, non disponibile come file KB)

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

---

## Policy Evaluation Logic — Dettaglio

```
Policy Evaluation Order (per ogni API call)

Step 1: Explicit DENY check
        ↓ (nessun deny)
Step 2: Organizations SCP
        ↓ (SCP Allow OR nessun SCP)
Step 3: Resource-based policy
        ↓ se Allow → ALLOW immediato
Step 4: Identity-based policy (User + Group + Role)
        ↓ se nessun Allow → continua
Step 5: IAM Permission Boundary
        ↓ se Allow in boundary
Step 6: Session Policy (se STS AssumeRole)
        ↓ se Allow in session policy
ALLOW

Se nessun Allow trovato → DENY implicito
```

**Regola fondamentale: Explicit DENY sempre vince** — anche se c'è un Allow altrove. Le **SCP** (Service Control Policy — policy AWS Organizations che definiscono il massimo dei permessi consentiti agli account figlio) agiscono come filtro a monte di tutte le policy identity-based.

---

## Conditions — Controllo Contestuale

Le **Condition** permettono di applicare policy solo in determinati contesti, rendendo i permessi molto più precisi rispetto a un semplice Allow/Deny statico. Senza Conditions, una policy che permette `s3:GetObject` vale per qualsiasi chiamata, da qualsiasi IP, in qualsiasi Region, con o senza MFA. Con le Conditions, puoi restringere la stessa policy a "solo da questo range IP, solo con MFA attiva, solo nella Region EU".

```json
// Struttura Condition
{
  "Condition": {
    "OperatorType": {
      "ConditionKey": "ConditionValue"
    }
  }
}
```

**Operator types:**

| Operatore | Descrizione |
|-----------|-------------|
| `StringEquals` / `StringNotEquals` | Confronto esatto stringa |
| `StringLike` / `StringNotLike` | Confronto con wildcard (`*`, `?`) |
| `NumericEquals` / `NumericLessThan` | Confronto numerico |
| `DateEquals` / `DateLessThan` | Confronto data/ora |
| `Bool` | Condizione booleana |
| `IpAddress` / `NotIpAddress` | Range IP (CIDR) |
| `ArnEquals` / `ArnLike` | Confronto ARN |
| `Null` | Verifica presenza/assenza chiave |
| `StringEqualsIfExists` | Applica solo se la chiave esiste |

**Suffissi modificatori:**
- `...IfExists` — applica condizione solo se la chiave è presente nella request
- `ForAllValues:...` — tutte le values devono soddisfare
- `ForAnyValue:...` — almeno una value deve soddisfare

---

### Condition Keys Globali (aws:...)

```json
// Restricting to specific Region
{
  "Effect": "Deny",
  "Action": "*",
  "Resource": "*",
  "Condition": {
    "StringNotEquals": {
      "aws:RequestedRegion": ["eu-central-1", "eu-west-1"]
    }
  }
}

// Require MFA for sensitive operations
{
  "Effect": "Deny",
  "Action": ["iam:*", "ec2:TerminateInstances"],
  "Resource": "*",
  "Condition": {
    "BoolIfExists": {
      "aws:MultiFactorAuthPresent": "false"
    }
  }
}

// Restrict to specific source IP
{
  "Effect": "Allow",
  "Action": "s3:*",
  "Resource": "*",
  "Condition": {
    "IpAddress": {
      "aws:SourceIp": ["203.0.113.0/24", "198.51.100.0/24"]
    }
  }
}

// Require SSL/TLS
{
  "Effect": "Deny",
  "Action": "s3:*",
  "Resource": "*",
  "Condition": {
    "Bool": {
      "aws:SecureTransport": "false"
    }
  }
}

// Tag-based conditions (ABAC)
{
  "Effect": "Allow",
  "Action": "ec2:*",
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "aws:ResourceTag/Environment": "${aws:PrincipalTag/Environment}"
    }
  }
}

// Restrict principal (chi fa la chiamata)
{
  "Effect": "Deny",
  "Action": "*",
  "Resource": "*",
  "Condition": {
    "ArnNotLike": {
      "aws:PrincipalArn": [
        "arn:aws:iam::123456789012:role/AdminRole",
        "arn:aws:iam::123456789012:role/DevOpsRole"
      ]
    }
  }
}

// Time-based access
{
  "Effect": "Allow",
  "Action": "ec2:StartInstances",
  "Resource": "*",
  "Condition": {
    "DateGreaterThan": {"aws:CurrentTime": "2026-01-01T00:00:00Z"},
    "DateLessThan": {"aws:CurrentTime": "2026-12-31T23:59:59Z"}
  }
}
```

---

## ABAC — Attribute-Based Access Control

**ABAC** (Attribute-Based Access Control, anche detto tag-based access control) è un approccio alla gestione dei permessi che usa i **tag** come attributi per determinare l'accesso, invece di definire policy separate per ogni team o progetto.

Il problema che risolve: con un approccio tradizionale (RBAC — Role-Based Access Control), ogni volta che nasce un nuovo team o progetto devi creare nuove policy e nuovi role specifici. Con ABAC, scrivi la policy una volta in modo generico (es. "puoi gestire le risorse che hanno lo stesso tag Team del tuo utente") e il controllo degli accessi si aggiorna automaticamente man mano che tagghi correttamente utenti e risorse — senza toccare le policy IAM.

```json
// Scenario: developer può gestire solo risorse con il suo team tag

// Policy IAM del developer
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:DescribeInstances"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          // La risorsa deve avere lo stesso tag Team del principal
          "ec2:ResourceTag/Team": "${aws:PrincipalTag/Team}"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "ec2:CreateTags",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          // Può solo taggare con il proprio team
          "aws:RequestTag/Team": "${aws:PrincipalTag/Team}"
        }
      }
    }
  ]
}
```

**Vantaggio ABAC vs RBAC:**
- RBAC (Role-Based Access Control): devi creare/aggiornare policy per ogni nuovo progetto/team
- ABAC: le policy rimangono stabili — basta aggiungere i tag corretti all'utente e alle risorse

---

## Permission Boundaries

Un **Permission Boundary** definisce il **tetto massimo dei permessi** che un'identità IAM può avere — anche se le sue policy allegano più permessi, i permessi effettivi non potranno mai superare il boundary.

Il caso d'uso tipico è la **delega controllata**: vuoi permettere ai tuoi developer di creare autonomamente IAM Role per le loro applicazioni, ma senza rischiare che creino role con permessi amministrativi illimitati. Con i Permission Boundaries, puoi dire "i developer possono creare role, ma solo se questi role hanno il nostro boundary standard applicato" — garantendo così che i role creati dai developer non possano mai superare un determinato livello di accesso, indipendentemente da quali policy vi allegano.

```
Permessi effettivi = Identity Policy ∩ Permission Boundary
```

```json
// Permission Boundary: consente SOLO S3 e DynamoDB (massimo)
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:*", "dynamodb:*", "cloudwatch:*"],
    "Resource": "*"
  }]
}
```

```bash
# Impostare Permission Boundary su un user
aws iam put-user-permissions-boundary \
    --user-name alice \
    --permissions-boundary arn:aws:iam::123456789012:policy/DeveloperBoundary

# Impostare Permission Boundary su un role
aws iam put-role-permissions-boundary \
    --role-name DeveloperRole \
    --permissions-boundary arn:aws:iam::123456789012:policy/DeveloperBoundary
```

**Use case tipico: delegare la creazione di role agli sviluppatori**

```json
// Policy per "Developer Lead" che può creare IAM Roles
// ma solo con il Permission Boundary obbligatorio
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["iam:CreateRole", "iam:AttachRolePolicy"],
      "Resource": "arn:aws:iam::123456789012:role/*",
      "Condition": {
        "StringEquals": {
          // Obbligatorio: il role creato deve avere questo boundary
          "iam:PermissionsBoundary": "arn:aws:iam::123456789012:policy/DeveloperBoundary"
        }
      }
    }
  ]
}
```

---

## Resource-Based Policies

Le **Resource-based policies** sono policy allegate direttamente alla risorsa (es. un bucket S3, una coda SQS), invece che all'identità che vi accede. Sono supportate da: S3, SQS, SNS, KMS, Lambda, API Gateway, Secrets Manager, ECR, CloudWatch Logs.

Il vantaggio principale rispetto alle policy identity-based è l'accesso **cross-account senza AssumeRole**: un'entità di un altro account AWS può accedere direttamente alla risorsa se la resource policy lo permette, senza dover prima assumere un role nell'account di destinazione. Questo semplifica architetture in cui più account devono condividere una risorsa comune.

```json
// S3 Bucket Policy — accesso cross-account
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountRead",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_B:role/ReadRole"
      },
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-shared-bucket",
        "arn:aws:s3:::my-shared-bucket/*"
      ]
    },
    {
      "Sid": "DenyPublicAccess",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-shared-bucket/*",
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"   // Deny se non HTTPS
        }
      }
    }
  ]
}
```

```json
// SQS Queue Policy — consenti a SNS di inviare messaggi
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "sns.amazonaws.com"},
    "Action": "sqs:SendMessage",
    "Resource": "arn:aws:sqs:eu-central-1:123456789012:my-queue",
    "Condition": {
      "ArnEquals": {
        "aws:SourceArn": "arn:aws:sns:eu-central-1:123456789012:my-topic"
      }
    }
  }]
}
```

---

## iam:PassRole

`iam:PassRole` è un permesso speciale che controlla quali role un utente può "passare" a un servizio AWS. Senza questo permesso, un utente non può associare un IAM Role a una risorsa (es. configurare il role di esecuzione di una Lambda function), anche se ha i permessi per creare la risorsa stessa.

Questo meccanismo previene una forma di **privilege escalation**: senza `iam:PassRole`, un developer con accesso limitato potrebbe creare una Lambda function e assegnarle un role con permessi amministrativi, eseguendo poi codice con privilegi superiori ai propri.

```json
// Permette di passare SOLO MyLambdaRole a Lambda
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::123456789012:role/MyLambdaRole",
  "Condition": {
    "StringEquals": {
      "iam:PassedToService": "lambda.amazonaws.com"
    }
  }
}
```

**Perché è importante:** senza `iam:PassRole`, un developer potrebbe creare una Lambda con un role più potente del proprio — privilege escalation.

---

## STS — Security Token Service

**STS** (Security Token Service) è il servizio che emette le **credenziali temporanee** usate da IAM Roles. Ogni volta che un'entità "assume" un Role, è STS che genera e restituisce le credenziali temporanee (AccessKeyId, SecretAccessKey, SessionToken) con una scadenza configurata.

Capire STS è importante perché le sue API sono usate in molti scenari: accesso cross-account, federazione con Identity Provider aziendali, e integrazione con CI/CD come GitHub Actions. Le operazioni principali sono:

```bash
# AssumeRole — assume un role (cross-account, federation)
aws sts assume-role \
    --role-arn arn:aws:iam::TARGET_ACCOUNT:role/AdminRole \
    --role-session-name "MySession" \
    --duration-seconds 3600 \
    --external-id "unique-external-id"     # per cross-account sicuro

# AssumeRoleWithWebIdentity — OIDC federation (K8s, GitHub Actions)
aws sts assume-role-with-web-identity \
    --role-arn arn:aws:iam::123456789012:role/GitHubActionsRole \
    --role-session-name "gh-actions" \
    --web-identity-token "$(cat /tmp/oidc-token)"

# AssumeRoleWithSAML — SAML federation (corporate IdP)
aws sts assume-role-with-saml \
    --role-arn arn:aws:iam::123456789012:role/SAMLRole \
    --principal-arn arn:aws:iam::123456789012:saml-provider/MyIdP \
    --saml-assertion "$(base64 saml-response.xml)"

# GetCallerIdentity — chi sono io?
aws sts get-caller-identity
# {"UserId":"...", "Account":"123456789012", "Arn":"arn:aws:iam::..."}

# GetSessionToken — aggiungere MFA alle credenziali esistenti
aws sts get-session-token \
    --serial-number arn:aws:iam::123456789012:mfa/alice \
    --token-code 123456 \
    --duration-seconds 43200   # 12 ore
```

**Token STS temporanei — caratteristiche:**
- Scadono dopo 15 minuti fino a 12 ore (AssumeRole) o 36 ore (GetSessionToken)
- Non possono essere revocati prima della scadenza (solo IAM policy può rifiutarli)
- Sono composti da: `AccessKeyId`, `SecretAccessKey`, `SessionToken`
- Devono essere passati tutti e tre nelle AWS API calls

---

## GitHub Actions — OIDC Federation (Zero Secrets)

Il pattern moderno per CI/CD è eliminare completamente le access keys statiche usando **OIDC** (OpenID Connect). Il problema tradizionale è che per permettere a GitHub Actions di deployare su AWS si dovevano configurare delle access keys come secrets nel repository — con tutti i rischi che comportano (chiavi che scadono, che vengono accidentalmente esposte, da ruotare manualmente).

Con OIDC, GitHub emette un token firmato che certifica l'identità del workflow (quale repository, quale branch, quale workflow file lo ha generato). AWS IAM verifica questo token e, se è valido, emette credenziali temporanee tramite STS — senza che nessuna chiave statica sia mai esistita.

```bash
# 1. Creare OIDC Identity Provider in IAM
aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

```json
// 2. Trust Policy del role (accetta solo il repo specifico)
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub":
          "repo:company/myapp:*"        // solo questo repo
      }
    }
  }]
}
```

```yaml
# 3. GitHub Actions workflow
jobs:
  deploy:
    permissions:
      id-token: write    # OIDC token
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
          aws-region: eu-central-1
          # Nessuna access key! Zero secrets statici.
```

---

## IAM Policy Simulator

```bash
# Simulare policy via CLI
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:user/alice \
    --action-names s3:GetObject ec2:RunInstances \
    --resource-arns arn:aws:s3:::my-bucket/file.txt \
    --context-entries '[{
        "ContextKeyName": "aws:MultiFactorAuthPresent",
        "ContextKeyValues": ["true"],
        "ContextKeyType": "boolean"
    }]'
```

Il **IAM Policy Simulator** nella Console permette di testare policy prima di applicarle — indispensabile per debug di access denied.

---

## Riferimenti

- [IAM Policy Conditions](https://docs.aws.amazon.com/iam/latest/userguide/reference_policies_condition-keys.html)
- [Permission Boundaries](https://docs.aws.amazon.com/iam/latest/userguide/access_policies_boundaries.html)
- [STS Documentation](https://docs.aws.amazon.com/STS/latest/APIReference/)
- [ABAC Guide](https://docs.aws.amazon.com/iam/latest/userguide/introduction_attribute-based-access-control.html)
- [GitHub OIDC](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
