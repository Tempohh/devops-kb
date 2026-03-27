---
title: "Terraform — Testing e Quality Gate"
slug: terraform-testing
category: iac
tags: [terraform, iac, testing, quality, security, linting, policy, ci-cd, compliance]
search_keywords: [terraform testing, terratest, tflint, checkov, conftest, OPA, open policy agent, terraform validate, terraform plan, pre-commit hooks, iac testing, infrastructure testing, security scanning, policy as code, compliance as code, static analysis, terraform lint, infracost, snyk iac, terraform compliance, kitchen terraform, inspec, regula, sentinel, quality gate, ci cd terraform, terraform pipeline, unit test infrastruttura, integration test infrastruttura, test iac, terraform check, terraform fmt, security iac, vulnerabilità iac, misconfiguration, CIS benchmark, cloud security posture]
parent: iac/terraform/_index
related: [iac/terraform/fondamentali, iac/terraform/moduli, iac/terraform/state-management, ci-cd/pipeline]
official_docs: https://developer.hashicorp.com/terraform/language/checks
status: complete
difficulty: intermediate
last_updated: 2026-03-26
---

# Terraform — Testing e Quality Gate

## Panoramica

Testare il codice Terraform è essenziale quanto testare il codice applicativo: un modulo IaC difettoso può creare risorse esposte pubblicamente, configurazioni non conformi, o infrastruttura instabile. La **piramide di testing IaC** prevede tre livelli: *static analysis* (linting, formatting, validazione sintattica), *policy/compliance* (regole di sicurezza e governance applicate prima dell'apply), e *integration testing* (provisioning reale in ambiente sandbox e verifica del comportamento). Strumenti come **tflint**, **checkov**, **conftest/OPA** e **Terratest** coprono rispettivamente questi livelli. I pre-commit hooks e la CI/CD integration rendono i quality gate automatici e non bypassabili. Questa combinazione trasforma Terraform da "wild west" a disciplina ingegneristica verificabile.

!!! warning "Testing IaC non sostituisce la revisione umana"
    I tool automatici trovano pattern noti e policy violate. Non trovano errori di business logic (es. "questa subnet dovrebbe essere privata, non pubblica"). La code review rimane indispensabile per le modifiche strutturali.

## Concetti Chiave

### Piramide di Testing IaC

```
                    ┌──────────────┐
                    │  Integration │  Terratest, kitchen-terraform
                    │   Testing    │  Costo alto, feedback lento
                    └──────┬───────┘
               ┌───────────┴───────────┐
               │  Policy / Compliance  │  conftest/OPA, checkov, Sentinel
               │  (pre-apply checks)   │  Costo medio, feedback medio
               └───────────┬───────────┘
          ┌────────────────┴────────────────┐
          │      Static Analysis / Linting  │  tflint, terraform validate/fmt
          │      (no cloud resources)       │  Costo zero, feedback immediato
          └─────────────────────────────────┘
```

### Tool Overview

| Tool | Livello | Cosa Fa |
|------|---------|---------|
| `terraform fmt` | Static | Formattazione canonica HCL |
| `terraform validate` | Static | Validazione sintattica e riferimenti |
| **tflint** | Static | Linting avanzato, best practice, errori provider-specifici |
| **checkov** | Policy | Security scanning, CIS benchmark, 1000+ check built-in |
| **conftest/OPA** | Policy | Policy-as-code personalizzate in Rego |
| **Terratest** | Integration | Test Go che provisionano infrastruttura reale |
| **pre-commit** | Orchestrazione | Esegue tutti i check prima di ogni commit |

!!! note "Terraform built-in checks (≥ v1.5)"
    Da Terraform 1.5, il blocco `check {}` permette asserzioni personalizzate nel piano stesso. Non richiede tool esterni ma è limitato a condizioni valutabili durante il plan.

## Architettura / Come Funziona

### Flusso Quality Gate in CI/CD

```
Developer push
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  Pre-commit hooks (locale, prima del commit)                 │
│  terraform fmt --check  →  terraform validate  →  tflint    │
└──────────────────────┬──────────────────────────────────────┘
                       │ commit OK
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  CI Pipeline — Static & Policy (PR check, minuti)           │
│  checkov  →  conftest/OPA  →  terraform plan  →  plan review│
└──────────────────────┬──────────────────────────────────────┘
                       │ PR approvata
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Integration Tests (schedule/nightly, ore)                   │
│  Terratest → provisioning sandbox → assert → destroy        │
└─────────────────────────────────────────────────────────────┘
```

### Separazione dei Costi

- **Static analysis**: gratuita, eseguita in millisecondi, zero risorse cloud.
- **Policy check**: gratuita, eseguita su file `.tf` o sul piano JSON, zero risorse cloud.
- **Integration test**: costa risorse cloud reali (usa account sandbox/test) e tempo (minuti→ore).

## Configurazione & Pratica

### 1. terraform fmt e validate

```bash
# Verifica formattazione (exit code 1 se file non formattati)
terraform fmt -check -recursive

# Applica formattazione automaticamente
terraform fmt -recursive

# Validazione sintattica + riferimenti (non contatta il provider)
terraform init -backend=false
terraform validate
```

```yaml
# .github/workflows/terraform-ci.yml — snippet validate
- name: Terraform Format Check
  run: terraform fmt -check -recursive

- name: Terraform Validate
  run: |
    terraform init -backend=false
    terraform validate
```

### 2. tflint — Linting Avanzato

tflint trova errori che `validate` non rileva: tipo VM non esistente, deprecazioni provider, convenzioni di naming.

```bash
# Installazione (Linux/macOS)
curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash

# Inizializzazione con plugin provider (es. AWS)
tflint --init

# Esecuzione (dalla root del modulo)
tflint --recursive
```

```hcl
# .tflint.hcl — configurazione tflint
plugin "aws" {
  enabled = true
  version = "0.31.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

rule "terraform_naming_convention" {
  enabled = true
  # Risorse devono seguire snake_case
  resource {
    format = "snake_case"
  }
}

rule "terraform_required_version" {
  enabled = true
}

rule "terraform_required_providers" {
  enabled = true
}
```

```bash
# Output tipico di tflint
$ tflint --recursive
3 issue(s) found:

Warning: aws_instance.web: "t2.micro" is previous generation (aws_instance_invalid_type)
  on main.tf line 4:
   4:   instance_type = "t2.micro"

Error: Required version constraint not found (terraform_required_version)
  on main.tf line 1:
```

### 3. checkov — Security Scanning

checkov analizza file `.tf` e piano JSON contro 1000+ policy CIS, NIST, SOC2.

```bash
# Installazione
pip install checkov

# Scan directory Terraform
checkov -d . --framework terraform

# Scan del piano JSON (più preciso — valuta valori interpolati)
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
checkov -f tfplan.json --framework terraform_plan

# Output solo failed (CI-friendly)
checkov -d . --framework terraform --compact --quiet
```

```bash
# Output tipico checkov
Check: CKV_AWS_8: "Ensure all data stored in the Launch configuration EBS is securely encrypted"
	FAILED for resource: aws_instance.web
	File: /main.tf:1-15

Check: CKV_AWS_135: "Ensure that EC2 instance should disable IMDSv1"
	FAILED for resource: aws_instance.web
	File: /main.tf:1-15

Passed checks: 18, Failed checks: 2, Skipped checks: 0
```

```hcl
# Sopprimere un check specifico (con giustificazione obbligatoria)
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"

  # checkov:skip=CKV_AWS_135:IMDSv1 necessario per agent legacy, ticket #1234
  metadata_options {
    http_tokens = "optional"
  }
}
```

```yaml
# .checkov.yaml — configurazione checkov
skip-check:
  - CKV2_AWS_5  # Security group non sempre associato a risorsa nello stesso modulo
compact: true
output: cli
framework:
  - terraform
```

### 4. conftest / OPA — Policy-as-Code Custom

Quando le policy built-in di checkov non bastano, conftest permette di scrivere regole personalizzate in **Rego** e applicarle al piano Terraform.

```bash
# Installazione conftest
brew install conftest
# oppure: https://www.conftest.dev/install/

# Struttura cartelle
project/
├── policy/
│   ├── terraform.rego    # Regole custom
│   └── required_tags.rego
└── main.tf

# Generare il piano JSON
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# Eseguire le policy
conftest test tfplan.json --policy policy/
```

```rego
# policy/required_tags.rego — Ogni risorsa AWS deve avere tag Environment e Owner
package main

import future.keywords.in

required_tags := ["Environment", "Owner", "CostCenter"]

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"

  after_tags := resource.change.after.tags
  missing_tag := required_tags[_]
  not after_tags[missing_tag]

  msg := sprintf(
    "aws_instance '%s' manca del tag obbligatorio '%s'",
    [resource.address, missing_tag]
  )
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  resource.change.after.instance_type == "t2.micro"

  msg := sprintf(
    "aws_instance '%s' usa t2.micro (generazione precedente). Usare t3.micro o superiore.",
    [resource.address]
  )
}
```

```bash
# Output conftest
$ conftest test tfplan.json --policy policy/
FAIL - tfplan.json - main - aws_instance 'aws_instance.web' manca del tag obbligatorio 'CostCenter'
FAIL - tfplan.json - main - aws_instance 'aws_instance.web' manca del tag obbligatorio 'Owner'

2 tests, 0 passed, 0 warnings, 2 failures, 0 exceptions
```

### 5. Terratest — Integration Testing

Terratest è una libreria Go per scrivere test che provisionano infrastruttura reale, la verificano, e la distruggono.

```
terraform/
├── modules/
│   └── web-server/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── test/
    └── web_server_test.go
```

```go
// test/web_server_test.go
package test

import (
    "fmt"
    "testing"
    "time"

    http_helper "github.com/gruntwork-io/terratest/modules/http-helper"
    "github.com/gruntwork-io/terratest/modules/terraform"
    "github.com/stretchr/testify/assert"
)

func TestWebServer(t *testing.T) {
    t.Parallel()

    terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
        // Path al modulo da testare
        TerraformDir: "../modules/web-server",

        // Variabili di input
        Vars: map[string]interface{}{
            "instance_type": "t3.micro",
            "environment":   "test",
        },

        // Evita prompt interattivi
        NoColor: true,
    })

    // Esegui terraform destroy al termine del test (anche in caso di fallimento)
    defer terraform.Destroy(t, terraformOptions)

    // Provisioning: terraform init + apply
    terraform.InitAndApply(t, terraformOptions)

    // Leggi gli output del modulo
    publicIP := terraform.Output(t, terraformOptions, "public_ip")
    assert.NotEmpty(t, publicIP, "public_ip non deve essere vuoto")

    // Verifica che l'endpoint HTTP risponda correttamente
    url := fmt.Sprintf("http://%s:80", publicIP)
    http_helper.HttpGetWithRetry(
        t,
        url,
        nil,                // no TLS
        200,                // HTTP status atteso
        "Hello, World!",    // body atteso (substring)
        30,                 // max retry
        10*time.Second,     // intervallo tra retry
    )
}
```

```bash
# Esecuzione test
cd test/
go test -v -run TestWebServer -timeout 30m

# Esecuzione con output dettagliato (include terraform output)
go test -v -run TestWebServer -timeout 30m 2>&1 | tee test-results.log
```

!!! tip "Usa account AWS separato per i test"
    Terratest crea risorse reali. Usa un account AWS dedicato ai test (con budget alert) separato da prod e staging. Configura il cleanup automatico con aws-nuke o simili per evitare risorse orfane se il test si interrompe.

### 6. Terraform built-in checks (v1.5+)

```hcl
# Asserzioni inline nella configurazione Terraform
resource "aws_s3_bucket" "app_data" {
  bucket = "myapp-data-${var.environment}"
}

# Check: il bucket non deve avere ACL public-read
check "bucket_not_public" {
  assert {
    condition     = !contains(["public-read", "public-read-write"], aws_s3_bucket_acl.this.acl)
    error_message = "Il bucket ${aws_s3_bucket.app_data.id} non deve avere ACL pubblica."
  }
}

# Check con data source: verifica stato risorsa esterna
data "aws_s3_bucket" "external" {
  bucket = "existing-bucket"
}

check "external_bucket_exists" {
  assert {
    condition     = data.aws_s3_bucket.external.id != null
    error_message = "Il bucket esterno non esiste o non è accessibile."
  }
}
```

### 7. pre-commit hooks — Automazione Locale

```bash
# Installazione pre-commit
pip install pre-commit

# Installazione hooks nel repo
pre-commit install
```

```yaml
# .pre-commit-config.yaml
repos:
  # Hooks ufficiali Terraform
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.86.0
    hooks:
      # Formattazione automatica
      - id: terraform_fmt

      # Validazione sintattica
      - id: terraform_validate
        args:
          - --args=-no-color

      # tflint con plugin AWS
      - id: terraform_tflint
        args:
          - --args=--config=__GIT_WORKING_DIR__/.tflint.hcl

      # checkov security scan
      - id: terraform_checkov
        args:
          - --args=--config-file=__GIT_WORKING_DIR__/.checkov.yaml

      # Aggiornamento automatico docs (terraform-docs)
      - id: terraform_docs
        args:
          - --args=--config=.terraform-docs.yml

  # Hook generici
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict
```

```bash
# Esecuzione manuale su tutti i file
pre-commit run --all-files

# Esecuzione su file staged (come farebbe il hook automatico)
pre-commit run

# Output esempio
terraform_fmt........................................................Passed
terraform_validate...................................................Passed
terraform_tflint.....................................................Failed
- hook id: terraform_tflint
- exit code: 1
2 issue(s) found:
Warning: Missing version constraint for provider "aws"
```

## Best Practices

!!! tip "Strategia di rollout graduale"
    Non abilitare tutti i check in una volta su un repo esistente. Inizia con `fmt` + `validate`, poi aggiungi `tflint`, poi `checkov`. Risolvi i warning esistenti prima di forzare il blocco della CI.

### Gerarchia dei Check

1. **terraform fmt** — sempre, nessuna eccezione, non negoziabile
2. **terraform validate** — sempre, è gratuito e trova errori reali
3. **tflint** — per ogni modulo, con ruleset provider-specifici
4. **checkov** — per ogni PR, con policy baseline concordate dal team
5. **conftest/OPA** — per policy aziendali che checkov non copre
6. **Terratest** — per moduli condivisi/critici, in nightly pipeline (non su ogni PR)

### Gestione dei Falsi Positivi

```bash
# checkov: skip con commento giustificativo nel .tf
# checkov:skip=CKV_AWS_123:Giustificazione + ticket reference

# tflint: ignore specifico
# tflint-ignore: aws_instance_invalid_type

# conftest: esclusione per risorsa (gestita in Rego con eccezioni esplicite)
```

!!! warning "Non disabilitare check globalmente senza approvazione"
    Ogni `skip` o `ignore` deve avere una giustificazione e (idealmente) un ticket. Disabilitare un check globalmente in `.checkov.yaml` nasconde problemi reali. Preferisci eccezioni granulari con commento.

### Testing dei Moduli

```
modules/
└── vpc/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    └── test/
        └── vpc_test.go    # Terratest per questo modulo
```

- Ogni modulo condiviso deve avere almeno un test Terratest che verifica gli output principali
- I test di moduli devono essere eseguibili in isolamento (no dipendenze cross-modulo)
- Usa `t.Parallel()` per ridurre i tempi quando si testano più moduli

### CI/CD Pipeline Pattern

```yaml
# GitHub Actions — pipeline completa
name: Terraform CI

on: [pull_request]

jobs:
  static:
    name: Static Analysis
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.7.x"

      - name: Format Check
        run: terraform fmt -check -recursive

      - name: Validate
        run: |
          terraform init -backend=false
          terraform validate

      - name: tflint
        uses: terraform-linters/setup-tflint@v4
        run: |
          tflint --init
          tflint --recursive

      - name: checkov
        uses: bridgecrewio/checkov-action@v12
        with:
          directory: .
          framework: terraform
          config_file: .checkov.yaml

      - name: Plan
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          terraform init
          terraform plan -out=tfplan -no-color 2>&1 | tee plan.txt

      - name: conftest policy check
        run: |
          terraform show -json tfplan > tfplan.json
          conftest test tfplan.json --policy policy/
```

## Troubleshooting

### Problema: `terraform validate` passa ma `tflint` fallisce

**Sintomo:** `terraform validate` non riporta errori, tflint riporta `aws_instance_invalid_type`.

**Causa:** `terraform validate` controlla solo la sintassi HCL e i riferimenti interni. Non interroga il provider — non sa quali AMI o instance type esistono. tflint usa regole provider-specifiche che conoscono i valori validi.

**Soluzione:**
```bash
# Verifica che il plugin provider sia installato
tflint --init

# Controlla la versione del ruleset
cat .tflint.hcl | grep version

# Aggiorna il ruleset se obsoleto
tflint --init --upgrade
```

---

### Problema: checkov produce troppi falsi positivi su risorse legacy

**Sintomo:** Decine di `FAILED` check su risorse esistenti che funzionano correttamente, bloccando la CI.

**Causa:** Checkov usa standard CIS aggiornati che possono essere più restrittivi di configurazioni storiche.

**Soluzione:**
```bash
# Genera un baseline da ignorare (solo per risorse esistenti)
checkov -d . --framework terraform --create-baseline

# Il baseline viene salvato in .checkov.baseline
# Da committare nel repo per ignorare i false positive noti
checkov -d . --framework terraform --baseline .checkov.baseline
```

---

### Problema: Terratest rimane appeso e le risorse non vengono distrutte

**Sintomo:** Il test si blocca (timeout), le risorse rimangono su AWS.

**Causa:** Il `defer terraform.Destroy()` non viene eseguito se il processo viene ucciso con SIGKILL.

**Soluzione:**
```go
// Usa TestCleanupOptions per registrare il cleanup anche su SIGTERM
defer terraform.Destroy(t, terraformOptions)

// In alternativa, configura un cleanup job separato
// che usa aws-nuke o tag-based cleanup
```

```bash
# Cleanup manuale delle risorse orfane con tag
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Environment,Values=test \
  --query 'ResourceTagMappingList[*].ResourceARN'
```

---

### Problema: conftest test fallisce con "no policies found"

**Sintomo:** `conftest test tfplan.json --policy policy/` → `0 tests, 0 passed`.

**Causa:** I file Rego non sono nella directory corretta, o la `package` declaration è sbagliata.

**Soluzione:**
```bash
# Verifica struttura
ls -la policy/
# Deve contenere file .rego

# Verifica package declaration nel file Rego
head -1 policy/terraform.rego
# Deve essere: package main

# Test con output verboso
conftest test tfplan.json --policy policy/ --trace 2>&1 | head -50
```

---

### Problema: pre-commit hook lento in repository grandi

**Sintomo:** Pre-commit impiega 2+ minuti, gli sviluppatori lo bypassano con `git commit --no-verify`.

**Causa:** I hook vengono eseguiti su tutti i file invece che solo sui file modificati.

**Soluzione:**
```yaml
# .pre-commit-config.yaml — limita l'ambito
- id: terraform_validate
  # Esegue solo nelle directory con file .tf modificati
  pass_filenames: false

# Oppure: sposta i check pesanti (checkov) solo nella CI
# e mantieni nel pre-commit solo fmt + validate (< 5 secondi)
```

## Relazioni

??? info "Terraform Fondamentali — Pre-requisiti"
    La comprensione del ciclo `plan/apply` e della struttura HCL è necessaria prima di implementare un testing pipeline. In particolare: come generare il piano JSON (`terraform plan -out + terraform show -json`).

    **Approfondimento completo →** [Terraform Fondamentali](fondamentali.md)

??? info "Terraform Moduli — Test dei Moduli Condivisi"
    I moduli condivisi sono i candidati primari per Terratest: un modulo usato in 10 progetti non può essere modificato senza test automatici.

    **Approfondimento completo →** [Terraform Moduli](moduli.md)

??? info "CI/CD Pipeline — Integrazione dei Quality Gate"
    I check Terraform vanno integrati nella pipeline CI come step bloccanti. Il pattern standard è: static check nel PR check, integration test nel nightly.

    **Approfondimento completo →** [CI/CD Pipeline](../../ci-cd/pipeline.md)

## Riferimenti

- [Terratest — documentazione ufficiale](https://terratest.gruntwork.io/)
- [tflint — Terraform Linter](https://github.com/terraform-linters/tflint)
- [checkov — Bridgecrew/Prisma Cloud](https://www.checkov.io/)
- [conftest — Policy testing con OPA](https://www.conftest.dev/)
- [pre-commit-terraform hooks](https://github.com/antonbabenko/pre-commit-terraform)
- [Open Policy Agent — Rego Language](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [Terraform Checks (v1.5+)](https://developer.hashicorp.com/terraform/language/checks)
- [HashiCorp — Testing di Moduli](https://developer.hashicorp.com/terraform/tutorials/modules/module-test)
