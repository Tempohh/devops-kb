---
title: "Terraform — Workflow CI/CD e Collaborazione in Team"
slug: terraform-ci-cd
category: iac
tags: [terraform, iac, ci-cd, atlantis, github-actions, automation, gitops, drift-detection, oidc, pipeline]
search_keywords: [terraform ci/cd, terraform pipeline, atlantis terraform, github actions terraform, terraform apply automatico, PR-based workflow, terraform plan su PR, terraform collaborativo, multi-ambiente terraform, terraform workspace ci, terraform promotion, promozione ambienti, drift detection terraform, terraform scheduled plan, state divergence, terraform apply merge, terraform security ci, OIDC terraform aws, OIDC terraform gcp, service account ci terraform, terraform environment promotion, dev staging prod terraform, terraform team workflow, terraform remote apply, terraform cloud ci, terragrunt run-all, terraform plan artifact, terraform apply production, environment protection github, required reviewers terraform, terraform audit log, atlantis helm, atlantis kubernetes, atlantis autoplan, terraform concurrency, state lock ci, terraform no manual apply, infra as code pipeline, IaC pipeline, terraform CD workflow, atlantis apply requirements, sentinel terraform, tfsec ci, checkov ci terraform]
parent: iac/terraform/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management, iac/terraform/testing, iac/terraform/moduli, ci-cd/pipeline, ci-cd/github-actions/workflow-avanzati]
official_docs: https://developer.hashicorp.com/terraform/tutorials/automation/github-actions
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# Terraform — Workflow CI/CD e Collaborazione in Team

## Panoramica

In un team, eseguire `terraform apply` manualmente dalla propria macchina è una pratica rischiosa: nessun audit trail, stato che diverge tra macchine, cambiamenti distruttivi che passano inosservati, contention sullo state lock. La soluzione è il **PR-based workflow**: ogni modifica all'infrastruttura passa attraverso una Pull Request, il `plan` viene eseguito automaticamente e commentato sulla PR, e l'`apply` avviene solo dopo approvazione esplicita — su merge o via comando. I due strumenti principali sono **Atlantis** (self-hosted, Kubernetes-native) e **GitHub Actions** (CI/CD general-purpose già disponibile nei team che usano GitHub). Questo file copre entrambi i pattern, il workflow multi-ambiente con promozione dev→staging→prod, la drift detection automatica, e la sicurezza delle credenziali nel CI.

!!! warning "Apply manuale dal locale: va eliminato in produzione"
    Anche se Terraform non lo impedisce, `terraform apply` da locale in ambienti condivisi (staging, prod) crea stato divergente dal CI, bypassa le approvazioni, e non lascia audit trail. Usa policy o permessi IAM per forzare il workflow automatizzato.

## Concetti Chiave

### Il Problema del Terraform Collaborativo

| Problema | Sintomo | Soluzione |
|---|---|---|
| Apply manuale da locale | Stato divergente, nessun audit | PR-based workflow + apply solo da CI |
| Plan non revisionato | Distruzione accidentale di risorse | Plan commentato su PR, review obbligatoria |
| State lock contention | Due ingegneri applicano in contemporanea | Apply serializzato dal CI, una queue |
| Credenziali long-lived nel CI | Secret leak da log o repo | OIDC federated identity, no static keys |
| Drift silenzioso | Infrastruttura reale ≠ codice | Drift detection schedulata |

### Flusso PR-Based (principio generale)

```
Developer modifica .tf
        │
        ▼
   git push → PR aperta
        │
        ▼
 CI esegue terraform plan
        │
        ▼
 Piano commentato su PR
   (diff risorse, costo stimato)
        │
        ▼
  Code review + approvazione
        │
        ▼
  Apply (su merge o comando)
        │
        ▼
  State aggiornato nel backend remoto
```

### Atlantis vs GitHub Actions

| | Atlantis | GitHub Actions |
|---|---|---|
| **Hosting** | Self-hosted (Kubernetes) | Cloud (GitHub-managed) |
| **Trigger apply** | `/atlantis apply` in commento PR | Merge su `main` + environment approval |
| **Multi-workspace** | Nativo con `atlantis.yaml` | Manuale (matrix strategy o workflow separati) |
| **Audit trail** | Commenti PR + log Atlantis | GitHub Actions run log |
| **Costo** | Infrastruttura propria | Incluso nei minuti GitHub Actions |
| **Ideale per** | Team IaC-first, mono-repo infra | Team già su GitHub Actions, setup più semplice |

## Architettura / Come Funziona

### Architettura Atlantis

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub / GitLab                                             │
│                                                              │
│  PR aperta → webhook → Atlantis server                      │
│  Commento "/atlantis apply" → webhook → Atlantis server     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS webhook
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Atlantis Server (Kubernetes pod)                            │
│                                                              │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐  │
│  │  Webhook    │→  │  Plan/Apply │→  │  GitHub Comment  │  │
│  │  receiver   │   │  executor   │   │  poster          │  │
│  └─────────────┘   └──────┬──────┘   └──────────────────┘  │
│                            │                                 │
│                     terraform binary                         │
└────────────────────────────┼────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Remote Backend │
                    │  (S3, GCS, TFC) │
                    └─────────────────┘
```

### Architettura GitHub Actions (Plan su PR, Apply su Main)

```
PR aperta/aggiornata
        │
        ▼
┌───────────────────────────────────────┐
│  Job: plan                             │
│  - terraform init                      │
│  - terraform plan -out=tfplan          │
│  - upload artifact tfplan              │
│  - commento PR con output piano        │
└───────────────────────────────────────┘
        │ merge su main
        ▼
┌───────────────────────────────────────┐
│  Job: apply                            │
│  environment: production              │
│  (richiede approvazione manuale)      │
│  - download artifact tfplan           │
│  - terraform apply tfplan             │
└───────────────────────────────────────┘
```

!!! note "Artifact tfplan: stessa versione garantita"
    Passare il file `tfplan` binario dal job `plan` al job `apply` garantisce che venga applicato esattamente il piano revisionato — non un nuovo piano che potrebbe differire se nel frattempo qualcosa è cambiato.

## Configurazione & Pratica

### 1. Atlantis — Installazione su Kubernetes

```bash
# Installazione via Helm
helm repo add runatlantis https://runatlantis.github.io/atlantis
helm repo update

# values.yaml per configurazione base
helm install atlantis runatlantis/atlantis \
  --values atlantis-values.yaml \
  --namespace atlantis \
  --create-namespace
```

```yaml
# atlantis-values.yaml
orgAllowlist: "github.com/myorg/*"

github:
  user: atlantis-bot
  token: "ghp_xxxxx"          # GitHub token del bot
  secret: "webhook-secret"    # Secret del webhook

repoConfig: |
  repos:
  - id: /.*/
    allowed_overrides: [workflow, apply_requirements]
    allow_custom_workflows: true

# Storage per state dei lock (Redis in prod, in-memory per test)
lockingDbType: redis
redis:
  host: redis-master
  port: 6379

# Resources
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### 2. Atlantis — Configurazione Repository (`atlantis.yaml`)

```yaml
# atlantis.yaml — configurazione per repo multi-workspace e multi-progetto
version: 3

projects:
  # Progetto networking in ambiente prod
  - name: networking-prod
    dir: infra/networking
    workspace: prod
    autoplan:
      # Esegue plan automatico se questi file cambiano
      when_modified:
        - "*.tf"
        - "*.tfvars"
        - "../modules/**/*.tf"    # Anche se cambiano i moduli condivisi
      enabled: true
    apply_requirements:
      - approved           # Almeno 1 approvazione review
      - mergeable          # PR senza conflict, checks CI passati
    workflow: prod-workflow

  # Progetto networking in ambiente staging
  - name: networking-staging
    dir: infra/networking
    workspace: staging
    autoplan:
      when_modified: ["*.tf", "*.tfvars", "../modules/**/*.tf"]
      enabled: true
    apply_requirements:
      - approved
    workflow: default

  # Progetto applicativo
  - name: app-infra-prod
    dir: infra/app
    workspace: prod
    autoplan:
      when_modified: ["*.tf", "*.tfvars"]
      enabled: true
    apply_requirements:
      - approved
      - mergeable

# Workflow personalizzato con step aggiuntivi
workflows:
  prod-workflow:
    plan:
      steps:
        - init:
            extra_args: ["-backend-config=backend-prod.hcl"]
        - run: checkov -d . --framework terraform --compact --quiet
        - plan:
            extra_args: ["-var-file=prod.tfvars", "-no-color"]
    apply:
      steps:
        - apply:
            extra_args: ["-no-color"]
```

```bash
# Comandi Atlantis nei commenti PR
atlantis plan                  # Riesegue il plan manualmente
atlantis plan -p networking-prod  # Plan per progetto specifico
atlantis apply                 # Apply di tutti i progetti pianificati
atlantis apply -p networking-prod # Apply progetto specifico
atlantis unlock                # Sblocca il lock (se bloccato da plan)
```

### 3. GitHub Actions — Workflow Completo Plan/Apply

```yaml
# .github/workflows/terraform.yml
name: Terraform CI/CD

on:
  pull_request:
    paths:
      - "infra/**"       # Trigger solo su modifiche infra
      - "modules/**"
  push:
    branches: [main]
    paths:
      - "infra/**"
      - "modules/**"

permissions:
  contents: read
  pull-requests: write   # Per commentare il piano sulla PR
  id-token: write        # Per OIDC (federazione identità)

env:
  TF_VERSION: "1.7.5"
  AWS_REGION: "eu-west-1"
  WORKING_DIR: "infra/app"

jobs:
  # ── Job 1: Plan su Pull Request ────────────────────────────
  plan:
    name: Terraform Plan
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    defaults:
      run:
        working-directory: ${{ env.WORKING_DIR }}

    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      # OIDC: autenticazione senza secret statici
      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-terraform
          aws-region: ${{ env.AWS_REGION }}

      - name: Terraform Init
        run: terraform init -backend-config=backend-prod.hcl

      - name: Terraform Format Check
        run: terraform fmt -check -recursive

      - name: Terraform Validate
        run: terraform validate -no-color

      - name: Terraform Plan
        id: plan
        run: terraform plan -out=tfplan -no-color -input=false
        continue-on-error: true    # Salva l'output anche se plan fallisce

      # Commenta il piano sulla PR
      - name: Comment Plan on PR
        uses: actions/github-script@v7
        env:
          PLAN_STDOUT: ${{ steps.plan.outputs.stdout }}
          PLAN_STDERR: ${{ steps.plan.outputs.stderr }}
        with:
          script: |
            const planOutput = process.env.PLAN_STDOUT || process.env.PLAN_STDERR;
            const status = '${{ steps.plan.outcome }}' === 'success' ? '✅' : '❌';
            const body = `#### Terraform Plan ${status}
            <details><summary>Mostra piano completo</summary>

            \`\`\`terraform
            ${planOutput}
            \`\`\`

            </details>

            *Workflow: \`${{ github.workflow }}\`, Run: \`${{ github.run_id }}\`*`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });

      # Fallisce il job se il plan è fallito (dopo aver commentato)
      - name: Check Plan Status
        if: steps.plan.outcome == 'failure'
        run: exit 1

      # Salva il piano come artifact per il job apply
      - name: Upload Plan Artifact
        uses: actions/upload-artifact@v4
        with:
          name: tfplan-${{ github.sha }}
          path: ${{ env.WORKING_DIR }}/tfplan
          retention-days: 5

  # ── Job 2: Apply su Merge in Main ──────────────────────────
  apply:
    name: Terraform Apply
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production      # Richiede approvazione manuale in GitHub
    defaults:
      run:
        working-directory: ${{ env.WORKING_DIR }}

    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-terraform
          aws-region: ${{ env.AWS_REGION }}

      - name: Terraform Init
        run: terraform init -backend-config=backend-prod.hcl

      # Scarica il piano prodotto nel job precedente
      - name: Download Plan Artifact
        uses: actions/download-artifact@v4
        with:
          name: tfplan-${{ github.sha }}
          path: ${{ env.WORKING_DIR }}

      - name: Terraform Apply
        run: terraform apply -auto-approve -no-color tfplan
```

### 4. OIDC — Autenticazione Senza Credenziali Statiche

```yaml
# AWS: configurazione del trust policy per GitHub Actions
# Permette al workflow del repo specifico di assumere il ruolo IAM
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringLike": {
          "token.actions.githubusercontent.com:sub":
            "repo:myorg/myrepo:*"
        },
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

```yaml
# GCP: Workload Identity Federation (equivalente OIDC)
# In GitHub Actions:
- name: Authenticate to GCP
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: "projects/123/locations/global/workloadIdentityPools/github/providers/github"
    service_account: "terraform-ci@myproject.iam.gserviceaccount.com"
```

!!! tip "OIDC: nessun secret da ruotare"
    Con OIDC la CI ottiene token temporanei automaticamente firmati da GitHub. Non ci sono `AWS_ACCESS_KEY_ID` o `AWS_SECRET_ACCESS_KEY` da gestire, ruotare, o rischiare di leakare nei log.

### 5. Pattern Multi-Ambiente con Promozione

```bash
# Pattern A: workspace Terraform
# Dev → Staging → Prod tramite workspace separati
terraform workspace select dev
terraform plan -var-file=envs/dev.tfvars -out=tfplan-dev
terraform apply tfplan-dev

terraform workspace select staging
terraform plan -var-file=envs/staging.tfvars -out=tfplan-staging
terraform apply tfplan-staging

# Solo dopo test su staging:
terraform workspace select prod
terraform plan -var-file=envs/prod.tfvars -out=tfplan-prod
terraform apply tfplan-prod
```

```bash
# Pattern B: directory separate (più esplicito, meno errori)
infra/
├── dev/
│   ├── main.tf         # o symlink/file che chiama moduli
│   ├── backend.tf      # backend S3 bucket per dev
│   └── terraform.tfvars
├── staging/
│   ├── main.tf
│   ├── backend.tf
│   └── terraform.tfvars
└── prod/
    ├── main.tf
    ├── backend.tf
    └── terraform.tfvars
```

```yaml
# GitHub Actions: matrix per ambienti (Pattern B)
jobs:
  plan:
    strategy:
      matrix:
        environment: [dev, staging, prod]
    steps:
      - name: Terraform Plan - ${{ matrix.environment }}
        working-directory: infra/${{ matrix.environment }}
        run: |
          terraform init
          terraform plan -no-color -out=tfplan
```

### 6. Drift Detection Automatica

Lo **state drift** si verifica quando l'infrastruttura reale diverge dal codice Terraform (modifica manuale in console, risorsa eliminata fuori banda). Rilevarlo proattivamente previene sorprese al prossimo `apply`.

```yaml
# .github/workflows/drift-detection.yml
name: Terraform Drift Detection

on:
  schedule:
    - cron: '0 8 * * 1-5'    # Ogni giorno lavorativo alle 08:00 UTC

permissions:
  contents: read
  id-token: write

jobs:
  detect-drift:
    name: Detect Drift in Production
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-terraform
          aws-region: eu-west-1

      - name: Terraform Init
        working-directory: infra/prod
        run: terraform init -backend-config=backend-prod.hcl

      - name: Check for Drift
        id: drift
        working-directory: infra/prod
        run: |
          # Exit code: 0 = no changes, 1 = error, 2 = drift rilevato
          terraform plan -detailed-exitcode -no-color \
            -var-file=prod.tfvars 2>&1 | tee drift-output.txt
          echo "exitcode=$?" >> $GITHUB_OUTPUT
        continue-on-error: true

      # Alert su Slack se drift rilevato (exit code 2)
      - name: Alert on Drift
        if: steps.drift.outputs.exitcode == '2'
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK_INFRA }}
        run: |
          SUMMARY=$(grep -E "^  [+~-]" drift-output.txt | head -20)
          curl -X POST "$SLACK_WEBHOOK" \
            -H 'Content-type: application/json' \
            -d "{
              \"text\": \"⚠️ *Terraform Drift Detected in PROD*\",
              \"attachments\": [{
                \"color\": \"danger\",
                \"text\": \"\`\`\`${SUMMARY}\`\`\`\",
                \"footer\": \"Run: ${{ github.run_id }}\"
              }]
            }"

      # Fail il workflow così è visibile nella dashboard
      - name: Fail on Drift
        if: steps.drift.outputs.exitcode == '2'
        run: |
          echo "::error::Drift rilevato in produzione. Revisionare il piano e applicare le correzioni."
          exit 1
```

### 7. Terragrunt — Orchestrazione Multi-Modulo

Per repo con molti moduli inter-dipendenti, **Terragrunt** aggiunge `run-all` per orchestrare plan/apply rispettando le dipendenze.

```hcl
# terragrunt.hcl (root) — configurazione comune
remote_state {
  backend = "s3"
  config = {
    bucket         = "myorg-terraform-state-${local.account_id}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

locals {
  account_id  = get_aws_account_id()
  environment = get_env("TF_VAR_environment", "dev")
}
```

```hcl
# infra/networking/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../modules/networking"
}

inputs = {
  environment = "prod"
  vpc_cidr    = "10.0.0.0/16"
}
```

```bash
# Comandi Terragrunt multi-modulo
# Plan su tutti i moduli nella directory (rispetta dipendenze)
terragrunt run-all plan --terragrunt-working-dir infra/prod

# Apply su tutti i moduli in sequenza (dep-aware)
terragrunt run-all apply --terragrunt-working-dir infra/prod

# Solo moduli con modifiche
terragrunt run-all plan --terragrunt-modules-that-include networking
```

## Best Practices

!!! tip "Regola d'oro: mai apply manuale in ambienti condivisi"
    Ogni modifica a staging e prod deve passare dal CI. Se hai bisogno di un hotfix urgente, il CI con `environment: production` richiede pochi minuti e lascia un audit trail completo. L'urgenza non giustifica bypassare il processo.

### Struttura Consigliata del Repository

```
infra-repo/
├── modules/                    # Moduli riusabili (versionati)
│   ├── networking/
│   ├── compute/
│   └── database/
├── environments/               # Configurazioni per ambiente
│   ├── dev/
│   │   ├── main.tf             # Chiama i moduli
│   │   ├── backend.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
├── .github/
│   └── workflows/
│       ├── terraform.yml       # Plan su PR, apply su merge
│       └── drift-detection.yml
├── atlantis.yaml               # Se si usa Atlantis
├── .tflint.hcl
└── .checkov.yaml
```

### Protezioni Raccomandate

```yaml
# GitHub: configurazione Environment "production"
# In: Repository Settings → Environments → production
protection_rules:
  required_reviewers:
    - team: "platform-team"    # Almeno 1 reviewer dal team
  wait_timer: 10               # 10 minuti di attesa prima dell'apply
  deployment_branch_policy:
    protected_branches: true   # Solo da branch protetti (main)
```

```hcl
# Politica IAM minima per il ruolo CI/CD
# Il ruolo CI deve avere SOLO i permessi necessari per il proprio ambiente
# Esempio: ruolo per gestire solo EC2 in un account dedicato
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:Create*",
        "ec2:Delete*",
        "ec2:Modify*"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-1"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::myorg-terraform-state/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:eu-west-1:*:table/terraform-locks"
    }
  ]
}
```

!!! warning "Least privilege per il ruolo CI"
    Il service account o ruolo IAM del CI non deve avere `AdministratorAccess`. Definisci permessi minimi per le risorse gestite da quel modulo. Se un secret viene leakato, il blast radius è limitato all'insieme di risorse che il ruolo può modificare.

### Gestione dei Secrets nel CI

```yaml
# ❌ NON fare: credenziali statiche in GitHub Secrets
AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

# ✅ FARE: OIDC con token temporanei (durata ~1 ora, auto-revocati)
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789:role/github-actions-terraform
    aws-region: eu-west-1
    # Nessun secret richiesto: GitHub firma il token JWT
```

```bash
# Variabili sensibili (DB password, API key) passate come env var nel CI
# MAI hardcodate nel .tfvars committato
- name: Terraform Apply
  env:
    TF_VAR_db_password: ${{ secrets.DB_PASSWORD_PROD }}
    TF_VAR_api_key: ${{ secrets.THIRD_PARTY_API_KEY }}
  run: terraform apply -auto-approve tfplan
```

## Troubleshooting

### Problema: Il plan artifact non è compatibile con l'apply (versione diversa)

**Sintomo:** `terraform apply tfplan` fallisce con `Error: The current configuration does not match the plan that was saved`.

**Causa:** Il piano binario `tfplan` contiene snapshot del provider e dei moduli. Se il job `apply` usa una versione Terraform o provider diversa dal job `plan`, il piano è invalidato.

**Soluzione:**
```yaml
# Fissare la versione Terraform identica in entrambi i job
- uses: hashicorp/setup-terraform@v3
  with:
    terraform_version: "1.7.5"   # Versione esatta, non "~> 1.7"

# Fissare le versioni provider in versions.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.40.0"    # Pin esatto, non ">= 5.0"
    }
  }
  required_version = "= 1.7.5"
}
```

---

### Problema: Atlantis non esegue autoplan su PR

**Sintomo:** PR aperta con modifiche a file `.tf`, ma Atlantis non commenta il piano.

**Causa:** I webhook non sono configurati correttamente, oppure il pattern `when_modified` in `atlantis.yaml` non matcha i file modificati.

**Soluzione:**
```bash
# 1. Verifica che il webhook sia registrato su GitHub
# Repository Settings → Webhooks → verifica URL Atlantis e secret

# 2. Verifica il log di Atlantis
kubectl logs -n atlantis deploy/atlantis --tail=100 | grep -i "webhook\|plan\|error"

# 3. Testa il matching manualmente nel commento PR
atlantis plan -d infra/networking -w prod

# 4. Verifica atlantis.yaml syntax
# Il campo when_modified usa glob patterns relativi alla dir del progetto
# "*.tf" matcha solo nella directory specificata in 'dir'
# "../modules/**/*.tf" per file nelle directory parent
```

---

### Problema: State lock non viene rilasciato dopo apply fallito

**Sintomo:** `Error: Error locking state: Error acquiring the state lock` per tutti i plan successivi.

**Causa:** Il processo Terraform è stato interrotto durante un'operazione (SIGKILL, OOM, timeout CI) senza rilasciare il lock.

**Soluzione:**
```bash
# Visualizza le informazioni del lock attuale
terraform force-unlock --help

# Ottieni il Lock ID dall'errore o dal backend
# Per S3 + DynamoDB:
aws dynamodb scan \
  --table-name terraform-locks \
  --filter-expression "LockID = :id" \
  --expression-attribute-values '{":id": {"S": "myorg-terraform-state/prod/terraform.tfstate"}}'

# Sblocca forzatamente (solo se sei sicuro che nessun apply sia in corso)
terraform force-unlock <LOCK_ID>

# Prevenzione: configura timeout nel CI
- name: Terraform Apply
  timeout-minutes: 30        # GitHub Actions termina il job dopo 30 min
  run: terraform apply -auto-approve tfplan
```

---

### Problema: Drift detection segnala cambiamenti che non sono drift reale

**Sintomo:** Il job di drift detection fallisce ogni notte con cambiamenti che sembrano non-deterministici (timestamp, ID casuali).

**Causa:** Il provider Terraform ricalcola alcune risorse con valori che cambiano ad ogni plan (es. ARN con timestamp, certificati auto-generati, random_id).

**Soluzione:**
```hcl
# Ignora gli attributi non deterministici con lifecycle
resource "aws_acm_certificate" "this" {
  domain_name       = var.domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
    ignore_changes = [
      # Il campo 'tags' è gestito esternamente da un altro tool
      tags["LastModified"],
    ]
  }
}
```

```bash
# Alternativa: filtra l'output del plan per escludere cambiamenti noti
terraform plan -detailed-exitcode 2>&1 | grep -v "known after apply" | \
  grep -E "^  [+~-]" | wc -l
# Se 0 righe → nessun drift reale
```

---

### Problema: GitHub Actions `environment: production` non richiede approvazione

**Sintomo:** Il job `apply` parte immediatamente senza attendere l'approvazione manuale.

**Causa:** L'Environment `production` non ha configurato `required reviewers` in GitHub.

**Soluzione:**
```
# In GitHub:
Repository → Settings → Environments → production
→ Environment protection rules
→ ✅ Required reviewers
→ Aggiungi: team/platform-team o utenti specifici
→ Save protection rules
```

## Relazioni

??? info "Terraform State Management — Backend e Locking"
    Il workflow CI/CD si appoggia al remote backend per lo state e al DynamoDB locking per la serializzazione degli apply. La configurazione del backend è il prerequisito per qualsiasi automazione.

    **Approfondimento completo →** [Terraform State Management](state-management.md)

??? info "Terraform Testing — Quality Gate nella Pipeline"
    Il job `plan` in CI include spesso checkov, tflint e conftest come step di quality gate. Il file Testing copre questi tool in dettaglio e include snippet per integrarli nella pipeline.

    **Approfondimento completo →** [Terraform Testing e Quality Gate](testing.md)

??? info "GitHub Actions Workflow Avanzati — Orchestrazione CI"
    Per approfondire i pattern GitHub Actions (matrix strategy, concurrency groups, reusable workflows, artifact management) utilizzati in questo file.

    **Approfondimento completo →** [GitHub Actions Workflow Avanzati](../../ci-cd/github-actions/workflow-avanzati.md)

??? info "CI/CD Pipeline — Principi Generali"
    I principi di pipeline-as-code, gate di qualità, e promozione tra ambienti sono descritti nella guida generale alle pipeline CI/CD.

    **Approfondimento completo →** [CI/CD Pipeline](../../ci-cd/pipeline.md)

## Riferimenti

- [Atlantis — documentazione ufficiale](https://www.runatlantis.io/docs/)
- [Atlantis — Helm Chart](https://github.com/runatlantis/helm-charts)
- [HashiCorp — Automating Terraform with GitHub Actions](https://developer.hashicorp.com/terraform/tutorials/automation/github-actions)
- [GitHub — Using environments for deployment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [GitHub — OIDC con AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Terragrunt — run-all](https://terragrunt.gruntwork.io/docs/reference/cli-options/#run-all)
- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
- [Terraform — detailed-exitcode (drift detection)](https://developer.hashicorp.com/terraform/cli/commands/plan#detailed-exitcode)
