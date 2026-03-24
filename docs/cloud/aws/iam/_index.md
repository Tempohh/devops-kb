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
last_updated: 2026-03-09
---

# AWS IAM — Identity & Access Management

**IAM** (Identity and Access Management) è il servizio **globale** di AWS per controllare chi può accedere alle risorse cloud e cosa può fare con esse. È unico per account AWS — non ha un concetto di Region.

IAM risponde a due domande fondamentali: **chi** (o cosa) può accedere alle risorse AWS, e **quali azioni** può compiere. Per rispondere a queste domande, IAM mette a disposizione quattro blocchi costruttivi principali: Users, Groups, Roles e Policies. Comprendere quando usare ciascuno di questi elementi è essenziale per costruire un sistema di accesso sicuro e scalabile.

!!! warning "IAM è fondamentale"
    IAM è trasversale a tutte le certificazioni AWS. Non esiste servizio AWS che non coinvolga IAM. Investire tempo su IAM ripaga in tutte le aree.

---

## Quando Usare Cosa — Guida Rapida

Prima di entrare nel dettaglio di ogni componente, è utile avere una visione d'insieme su quando usare ciascuno:

| Entità | Usa quando... | Non usare quando... |
|--------|--------------|---------------------|
| **User** | Una persona fisica deve accedere ad AWS con credenziali proprie (Console o CLI) | Un'applicazione o servizio AWS deve accedere ad AWS → usa un Role |
| **Group** | Vuoi applicare gli stessi permessi a più utenti senza ripetere la configurazione | Vuoi assegnare permessi a una singola persona → allegali direttamente all'utente |
| **Role** | Un servizio AWS (EC2, Lambda...), un'applicazione esterna o un account diverso deve accedere ad AWS | Una persona fisica con accesso stabile e a lungo termine → valuta un User |
| **Policy** | Devi definire cosa è permesso o negato — è sempre necessaria, allegata a User, Group, Role o alla risorsa stessa | — |

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

Un **IAM User** è un'identità permanente con credenziali proprie, progettata per rappresentare una **persona fisica** che deve interagire con AWS in modo continuativo. A differenza dei Roles, le credenziali degli Users sono statiche: una password per accedere alla Console e, opzionalmente, delle Access Keys per l'accesso programmatico tramite CLI o SDK.

Gli Users sono appropriati quando si deve dare accesso a un collaboratore specifico — ad esempio un DevOps Engineer o un amministratore — che lavorerà con AWS in modo ricorrente. Per applicazioni e servizi, invece, si preferisce sempre un Role (vedi sezione dedicata), perché i Roles usano credenziali temporanee che non richiedono gestione manuale.

**Tipi di accesso:**
- **Console password** — accesso alla AWS Management Console tramite browser
- **Access Keys** (Access Key ID + Secret Access Key) — accesso programmatico tramite CLI, SDK o API dirette
- **MFA** — secondo fattore di autenticazione (TOTP con app come Google Authenticator, hardware FIDO2, SMS)

**Best practices:**
- Non usare il **root account** per operazioni ordinarie: va usato solo per il setup iniziale e per emergenze che richiedono permessi assoluti
- Abilitare **MFA** sul root account e su tutti gli utenti con accesso privilegiato
- **Ruotare le access keys** regolarmente, oppure sostituirle con IAM Roles per eliminare il problema alla radice
- Applicare il **principio del minimo privilegio**: concedere solo i permessi strettamente necessari

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

Un **IAM Group** è una raccolta di utenti che condividono gli stessi permessi. Usare i gruppi è una best practice fondamentale: invece di allegare policy direttamente ai singoli utenti (approccio difficile da mantenere a lungo termine), si definiscono i permessi a livello di gruppo e si aggiungono gli utenti ai gruppi appropriati. In questo modo, modificare i permessi di un intero team — ad esempio aggiungere accesso a un nuovo servizio per tutti i developer — richiede un'unica operazione sul gruppo invece di tante modifiche sui singoli utenti.

Limiti da tenere presenti:
- Un utente può appartenere a più gruppi (massimo 10 per utente)
- I gruppi **non possono essere nestati**: non è possibile mettere un gruppo dentro un altro gruppo
- Le policy allegate al gruppo si applicano automaticamente a tutti i suoi membri

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

Un **IAM Role** è un'identità **temporanea** che può essere "assunta" da un principal (un utente, un servizio AWS, o un account esterno) per ottenere credenziali temporanee con cui operare.

Il principio fondamentale è questo: **i Roles usano credenziali temporanee**, a differenza degli Users che hanno credenziali statiche. Quando un servizio o un'applicazione "assume" un Role tramite AWS STS (Security Token Service), riceve un set di credenziali (AccessKeyId, SecretAccessKey, SessionToken) che scadono automaticamente dopo un tempo configurabile, da 15 minuti fino a 12 ore. Questo elimina il rischio tipico delle Access Keys statiche: nessuna chiave da ruotare manualmente, nessun secret che rischia di finire nel codice o in un repository.

**Quando si usa un Role:**
- **EC2 che accede a S3** → si assegna un EC2 Instance Profile (wrapper del Role per EC2). L'istanza ottiene credenziali temporanee automaticamente, senza configurare access keys sull'OS.
- **Lambda che scrive su DynamoDB** → si assegna un Lambda Execution Role. Lambda lo assume automaticamente all'avvio.
- **Accesso cross-account** → Account A deve accedere a risorse nell'Account B: si crea un Role nell'Account B con trust verso Account A, e l'utente di A lo assume.
- **Utenti federati** (SAML/OIDC) → gli utenti si autenticano con il proprio Identity Provider aziendale (Okta, Azure AD) e assumono un Role AWS.
- **Servizi AWS che agiscono per conto tuo** → es. CloudFormation crea risorse nel tuo account usando un Role.

**Componenti di un Role:**
- **Trust Policy** — definisce chi può assumere il role (chi può fare `sts:AssumeRole`): può essere un servizio AWS, un account specifico, o un utente federato
- **Permission Policy** — definisce cosa può fare chi assume il role (stessa struttura delle policy IAM standard)

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

| Tipo | Attaccata a | Gestione | Quando usarla |
|------|------------|---------|--------------|
| **AWS Managed** | User/Group/Role | AWS (aggiornata automaticamente) | Punto di partenza e per permessi comuni standard |
| **Customer Managed** | User/Group/Role | Tu (controllo completo) | Permessi specifici per la tua applicazione — preferibile all'Inline |
| **Inline** | Solo 1 entità | Embedded, relazione 1:1 | Solo quando vuoi garantire che la policy non venga riutilizzata altrove |
| **Resource-based** | Risorsa (S3, SQS...) | Sulla risorsa stessa | Accesso cross-account senza assume role, o per definire chi può accedere a una risorsa specifica |
| **Permission Boundaries** | User/Role | Limita la massima autorizzazione | Delegare la creazione di identità ad altri team, garantendo un limite massimo ai permessi che possono assegnare |
| **Service Control Policy (SCP)** | OU/Account | Solo con AWS Organizations | Imporre limiti a livello organizzativo che si applicano anche agli amministratori degli account figlio |
| **Session Policy** | STS session | Temporanea, al momento di AssumeRole | Restringere ulteriormente i permessi di una sessione temporanea |

La scelta del tipo di policy dipende dal caso d'uso. Per la maggior parte delle situazioni, si parte dalle **AWS Managed Policies** per i permessi comuni e si definiscono **Customer Managed Policies** per i requisiti specifici dell'applicazione. Le **Inline Policies** sono generalmente sconsigliate perché difficili da riutilizzare e da tenere sotto controllo. Le **Resource-based Policies** diventano essenziali per la condivisione cross-account. I **Permission Boundaries** e le **SCP** sono strumenti avanzati per la governance multi-team e multi-account.

**Logica di valutazione (Evaluation Logic):**

Quando AWS riceve una chiamata API, valuta le policy in questo ordine per decidere se permetterla o negarla:

```
1. Explicit DENY? → DENY (sempre vince, indipendentemente da qualsiasi Allow)
2. SCP (Organizations) ALLOW? → continua (se non c'è SCP Allow, DENY)
3. Resource-based policy ALLOW? → ALLOW immediato
4. Identity-based policy ALLOW? → continua
5. Permission Boundary ALLOW? → continua
6. Session Policy ALLOW? → ALLOW
7. Default: DENY implicito (se nessun Allow trovato)
```

Il punto più importante da ricordare: un **Deny esplicito vince sempre**, anche se c'è un Allow in un'altra policy. Questo rende i Deny un meccanismo potente ma da usare con attenzione, perché non può essere sovrascritto.

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

Gli **ARN** (Amazon Resource Names) identificano univocamente ogni risorsa AWS in modo non ambiguo, indipendentemente dal contesto. Sono usati ovunque nelle policy IAM nel campo `Resource` per indicare su quali risorse si applicano i permessi.

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

**IAM Access Analyzer** è uno strumento di analisi automatica che identifica risorse con accesso **pubblico o cross-account non intenzionale**. È particolarmente utile per scoprire configurazioni errate che potrebbero esporre dati sensibili: ad esempio un bucket S3 reso pubblico per errore, o un role IAM che può essere assunto da un account esterno non autorizzato.

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
