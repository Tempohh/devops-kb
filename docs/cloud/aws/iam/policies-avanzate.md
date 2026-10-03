---
title: "IAM Policies Avanzate"
slug: policies-avanzate
category: cloud
tags: [aws, iam, policies, conditions, permission-boundaries, resource-based, STS, session-policy, policy-evaluation, abac, rbac]
search_keywords: [IAM policy conditions, IAM StringEquals, IAM aws:RequestedRegion, IAM permission boundaries, IAM resource-based policy, IAM cross-account policy, IAM session policy, IAM ABAC, attribute-based access control, IAM tags conditions, IAM policy evaluation logic, IAM deny, IAM PassRole, IAM explicit deny, IAM policy simulator, IAM inline vs managed]
parent: cloud/aws/iam/_index
related: [cloud/aws/iam/_index, cloud/aws/iam/organizations, cloud/aws/security/compliance-audit]
official_docs: https://docs.aws.amazon.com/iam/latest/userguide/access_policies.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-03
last_verified: 2026-10-03
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
Policy Evaluation Order (per ogni API call, stesso account)

Step 1: Explicit DENY check (in QUALSIASI policy applicabile)
        ↓ (nessun deny)
Step 2: Organizations SCP (e RCP)
        ↓ devono consentire l'azione (SCP default: FullAWSAccess)
Step 3: Resource-based policy
        ↓ se concede l'Allow al principal (vedi nota) → ALLOW
Step 4: Identity-based policy (User + Group + Role)
        ↓ serve almeno un Allow
Step 5: IAM Permission Boundary
        ↓ serve un Allow nel boundary
Step 6: Session Policy (se sessione STS con policy inline/managed passata)
        ↓ serve un Allow nella session policy
ALLOW

Se nessun Allow trovato → DENY implicito
```

**Regola fondamentale: Explicit DENY sempre vince** — anche se c'è un Allow altrove. Le **SCP** (Service Control Policy — policy AWS Organizations che definiscono il massimo dei permessi consentiti agli account figlio) e le **RCP** (Resource Control Policy — analoghe, ma limitano i permessi sulle *risorse* dell'organizzazione) agiscono come filtro a monte: non concedono nulla, restringono soltanto.

!!! note "Resource-based policy: same-account vs cross-account"
    - **Stesso account:** una resource policy che nomina direttamente un *IAM user* o l'ARN di una *sessione* di role concede l'accesso anche senza Allow identity-based, e **non** è limitata da Permission Boundary né session policy. Se nomina invece il *role* (non la sessione) o l'account root, serve comunque anche l'Allow identity-based.
    - **Cross-account:** servono **entrambi** gli Allow — resource policy nell'account di destinazione *e* identity policy nell'account del chiamante.

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
// Nota: aws:SourceIp non vale per richieste via VPC endpoint (usa aws:SourceVpc/aws:SourceVpce)
// né per chiamate fatte da servizi AWS per tuo conto (usa aws:ViaAWSService nei Deny)
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
        "ec2:StopInstances"
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
      // Le azioni Describe* non supportano resource-level permissions:
      // con la Condition sul tag sarebbero sempre negate
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
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

!!! warning "Attenzione"
    Con ABAC chi può modificare i tag controlla gli accessi. Limita `ec2:CreateTags`/`ec2:DeleteTags` (e `iam:TagUser`/`iam:TagRole` per i tag dei principal) con Condition su `aws:TagKeys` e `aws:ResourceTag`, altrimenti un utente può riassegnarsi il tag `Team` di un altro team. Verifica inoltre che il servizio supporti le tag condition keys (tabella *Actions, resources, and condition keys* della Service Authorization Reference).

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
      "Action": ["iam:CreateRole", "iam:PutRolePermissionsBoundary"],
      "Resource": "arn:aws:iam::123456789012:role/*",
      "Condition": {
        "StringEquals": {
          // Obbligatorio: il role creato deve avere questo boundary
          "iam:PermissionsBoundary": "arn:aws:iam::123456789012:policy/DeveloperBoundary"
        }
      }
    },
    {
      // AttachRolePolicy non supporta la key iam:PermissionsBoundary:
      // va concesso in uno statement separato (senza quella Condition)
      "Effect": "Allow",
      "Action": ["iam:AttachRolePolicy", "iam:PutRolePolicy"],
      "Resource": "arn:aws:iam::123456789012:role/*"
    },
    {
      // Impedisce di rimuovere il boundary o di modificare la policy del boundary stesso
      "Effect": "Deny",
      "Action": [
        "iam:DeleteRolePermissionsBoundary",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicy",
        "iam:DeletePolicyVersion",
        "iam:SetDefaultPolicyVersion"
      ],
      "Resource": [
        "arn:aws:iam::123456789012:role/*",
        "arn:aws:iam::123456789012:policy/DeveloperBoundary"
      ]
    }
  ]
}
```

Senza lo statement di Deny il pattern è aggirabile: chi può rimuovere il boundary o riscrivere `DeveloperBoundary` annulla la delega controllata. In produzione restringi anche `Resource` a un prefisso di role (es. `role/app-*`) e a un `Path`, così gli sviluppatori non toccano role di altri team o di piattaforma.

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
      "Sid": "DenyInsecureTransport",
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
- Durata: da 15 minuti al *max session duration* del role (1–12 ore, default 1 ora) per AssumeRole; role chaining (role che assume un altro role) limitato a 1 ora; fino a 36 ore per GetSessionToken (IAM user; 1 ora per root)
- Non esiste "delete" della singola credenziale: dalla console *Revoke active sessions* aggiunge al role una policy `Deny` con `aws:TokenIssueTime` precedente a ora, invalidando le sessioni già emesse; le nuove sessioni restano valide
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
    --client-id-list sts.amazonaws.com
# Il thumbprint non è più richiesto: per GitHub AWS valida la catena TLS
# con la propria libreria di CA radice attendibili (--thumbprint-list opzionale)
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

!!! warning "Attenzione"
    `repo:company/myapp:*` accetta qualsiasi branch, tag, pull request ed environment del repo. Per role con permessi di deploy restringi il `sub` a un ref o environment preciso (es. `repo:company/myapp:ref:refs/heads/main` oppure `repo:company/myapp:environment:production`), altrimenti qualunque PR/branch può assumere il role. Senza Condition su `sub` il role è assumibile da *qualsiasi* repo GitHub.

```yaml
# 3. GitHub Actions workflow
jobs:
  deploy:
    permissions:
      id-token: write    # OIDC token
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v5
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

## Best Practices

- **Usa Explicit Deny per guardrail critici** — per restrizioni di sicurezza (es. blocco Region, require MFA) usa sempre Deny esplicito, mai affidarti all'assenza di Allow.
- **Preferisci ABAC quando i team scalano** — se hai più di 5-10 team/progetti, ABAC con tag riduce drasticamente il numero di policy da mantenere.
- **Applica Permission Boundaries in organizzazioni multi-team** — impedisce privilege escalation quando deleghi la creazione di role.
- **Usa credenziali STS temporanee per CI/CD** — mai access key statiche nei workflow; OIDC è il pattern consigliato.
- **Testa sempre con IAM Policy Simulator prima di applicare** — specialmente policy con Conditions complesse o cross-account.
- **Limita `iam:PassRole` per servizio** — aggiungi sempre la Condition `iam:PassedToService` per evitare che il permesso sia più ampio del necessario.
- **Usa `aws:SecureTransport` su tutte le resource policy S3** — forza HTTPS anche se il bucket non è pubblico.

---

## Troubleshooting

### Scenario 1 — AccessDenied nonostante la policy sembri corretta

**Sintomo:** L'utente riceve `AccessDenied` ma la policy identity-based contiene un Allow per l'azione richiesta.

**Causa:** Un `Deny` esplicito in una qualsiasi policy (anche resource-based), oppure uno degli strati nella evaluation logic non ha un Allow corrispondente: SCP/RCP, Permission Boundary o Session Policy. Basta uno strato senza Allow perché il risultato finale sia Deny. In cross-account manca spesso l'Allow su uno dei due lati.

**Soluzione:** Cercare prima Deny espliciti, poi verificare ogni strato nell'ordine di evaluation: SCP/RCP tramite AWS Organizations, Permission Boundary, Session Policy. Il messaggio di errore indica spesso il tipo di policy che nega ("...with an explicit deny in a service control policy").

```bash
# Simulare la policy dell'utente con contesto completo
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:user/alice \
    --action-names s3:GetObject \
    --resource-arns arn:aws:s3:::my-bucket/file.txt

# Controllare i Permission Boundaries applicati
aws iam get-user --user-name alice --query 'User.PermissionsBoundary'

# Verificare gli SCP sull'account
aws organizations list-policies-for-target \
    --target-id <account-id> \
    --filter SERVICE_CONTROL_POLICY
```

---

### Scenario 2 — Condition non valutata come attesa (StringLike con wildcard)

**Sintomo:** La policy usa `StringLike` con wildcard ma la Condition non si comporta come previsto — permettendo accessi non voluti o bloccando accessi legittimi.

**Causa:** Errori comuni: uso di `StringEquals` invece di `StringLike` quando si intende usare wildcard (`*`, `?`); wildcard posizionata nel posto sbagliato nel pattern; case sensitivity (le Condition key di servizio come `s3:prefix` sono case-sensitive).

**Soluzione:** Verificare l'operatore usato e testare con IAM Policy Simulator fornendo valori espliciti.

```bash
# Test con contesto: verifica che la Condition s3:prefix funzioni
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:role/DevRole \
    --action-names s3:ListBucket \
    --resource-arns "arn:aws:s3:::my-bucket" \
    --context-entries '[{
        "ContextKeyName": "s3:prefix",
        "ContextKeyValues": ["dev/"],
        "ContextKeyType": "string"
    }]'
```

---

### Scenario 3 — STS AssumeRole fallisce con `AccessDenied`

**Sintomo:** `aws sts assume-role` restituisce `AccessDenied` o `An error occurred (AccessDenied) when calling the AssumeRole operation`.

**Causa possibile A:** La Trust Policy del role non include il principal che tenta l'assume.
**Causa possibile B:** Manca `sts:AssumeRole` nell'identity policy del principal.
**Causa possibile C:** L'`external-id` richiesto dalla Trust Policy non viene passato (comune in setup cross-account con third party).

**Soluzione:** Verificare la Trust Policy del role target e la policy del principal chiamante.

```bash
# Verificare la Trust Policy del role
aws iam get-role --role-name TargetRole \
    --query 'Role.AssumeRolePolicyDocument'

# Verificare chi sta chiamando (utile per debug di identità)
aws sts get-caller-identity

# Richiesta con external-id (se richiesto dalla Trust Policy)
aws sts assume-role \
    --role-arn arn:aws:iam::TARGET:role/TargetRole \
    --role-session-name debug-session \
    --external-id "expected-external-id"
```

---

### Scenario 4 — GitHub Actions OIDC: `Could not assume role with OIDC`

**Sintomo:** Il workflow GitHub Actions fallisce con errore OIDC durante `aws-actions/configure-aws-credentials`.

**Causa possibile A:** La Trust Policy non ha la Condition corretta su `sub` (es. branch sbagliato, repo sbagliato, o pattern `StringLike` troppo restrittivo).
**Causa possibile B:** Il workflow manca del permesso `id-token: write`.
**Causa possibile C:** L'OIDC provider non esiste nell'account, o la `aud` nella Trust Policy non coincide con quella del token (default `sts.amazonaws.com`). (Il thumbprint non è più causa tipica: per GitHub AWS non lo verifica più.)

**Soluzione:** Verificare la Trust Policy e i log del workflow. Il claim `sub` ha il formato `repo:<owner>/<repo>:ref:refs/heads/<branch>` (oppure `:environment:<name>`, `:pull_request`).

```bash
# Verificare la Trust Policy del role GitHub Actions
aws iam get-role --role-name GitHubActionsRole \
    --query 'Role.AssumeRolePolicyDocument'

# Verificare che l'OIDC provider esista
aws iam list-open-id-connect-providers

# Verificare audience/thumbprint registrati sul provider
aws iam get-open-id-connect-provider \
    --open-id-connect-provider-arn arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com
```

---

## Relazioni

??? info "IAM — Fondamentali"
    Users, Groups, Roles e policy base. Prerequisito per questo documento.

    **Approfondimento completo →** [IAM Index](../iam/_index.md)

??? info "AWS Organizations & SCP"
    Le Service Control Policy (SCP) si posizionano sopra le identity-based policy nell'evaluation logic e possono bloccare anche gli admin dell'account.

    **Approfondimento completo →** [Organizations](../iam/organizations.md)

??? info "Compliance & Audit"
    AWS Config e CloudTrail per verificare che le policy IAM rispettino i requisiti di compliance e per auditare le chiamate STS.

    **Approfondimento completo →** [Compliance & Audit](../security/compliance-audit.md)

---

## Riferimenti

- [IAM Policy Conditions](https://docs.aws.amazon.com/iam/latest/userguide/reference_policies_condition-keys.html)
- [Permission Boundaries](https://docs.aws.amazon.com/iam/latest/userguide/access_policies_boundaries.html)
- [STS Documentation](https://docs.aws.amazon.com/STS/latest/APIReference/)
- [ABAC Guide](https://docs.aws.amazon.com/iam/latest/userguide/introduction_attribute-based-access-control.html)
- [GitHub OIDC](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
