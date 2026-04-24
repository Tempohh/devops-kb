---
title: "OpenTofu"
slug: opentofu
category: iac
tags: [opentofu, terraform, iac, infrastructure-as-code, open-source, linux-foundation, cncf, hcl, fork]
search_keywords: [opentofu, open tofu, tofu, terraform fork, bsl, business source license, mpl, mozilla public license, hashicorp license, terraform open source, iac open source, cncf terraform, linux foundation terraform, terraform alternative, state encryption, tofu init, tofu plan, tofu apply, registry.opentofu.org, opentofu registry, terraform compatible, drop-in replacement, terragrunt opentofu, atlantis opentofu, infracost opentofu, setup-opentofu, opentofu github actions, opentofu state encryption, aes-gcm, pbkdf2, early evaluation, provider_meta]
parent: iac/terraform/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management, iac/terraform/ci-cd, iac/terraform/moduli]
official_docs: https://opentofu.org/docs/
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# OpenTofu

## Panoramica

OpenTofu è il fork open-source di Terraform, mantenuto dalla **Linux Foundation** (sotto l'ombrello della CNCF) a partire da settembre 2023. Nasce in risposta al cambio di licenza di HashiCorp: nell'agosto 2023 Terraform è passato dalla **MPL 2.0** (Mozilla Public License, licenza open source permissiva) alla **BSL 1.1** (Business Source License), che limita l'uso commerciale da parte di terze parti concorrenti di HashiCorp. Il progetto ha raggiunto la **General Availability con la v1.6 in gennaio 2024** ed è ora una scelta consolidata per chi necessita di IaC completamente open source senza vincoli di licensing.

OpenTofu è un **drop-in replacement** di Terraform fino alla v1.5.x: gli stessi file `.tf`, gli stessi provider, gli stessi state file — nessuna modifica al codice esistente per la migrazione base. Le versioni successive di OpenTofu aggiungono feature non presenti in Terraform (in particolare la **state encryption nativa**) e divergono progressivamente.

!!! note "Versioni di riferimento"
    Questa documentazione fa riferimento a OpenTofu **v1.8.x** (LTS). Verificare sempre le release notes per le versioni più recenti.

## Concetti Chiave

### Contesto Storico: Perché Esiste OpenTofu

| Data | Evento |
|------|--------|
| Agosto 2023 | HashiCorp annuncia il cambio di licenza Terraform: da MPL 2.0 a BSL 1.1 |
| Settembre 2023 | La community lancia il fork sotto la CNCF/Linux Foundation come "OpenTofu" |
| Dicembre 2023 | OpenTofu v1.6.0-rc1 — prima release candidate |
| Gennaio 2024 | **OpenTofu v1.6.0 GA** — il fork è stabile e production-ready |
| 2024–2025 | Feature divergenti rispetto a Terraform: state encryption, early evaluation, improved testing |

La BSL 1.1 impedisce l'utilizzo di Terraform per costruire prodotti o servizi che competono con HashiCorp (es. una piattaforma IaC-as-a-service). Per chi usa Terraform internamente senza rivendita, il cambio di licenza ha impatto limitato. Per i vendor e le organizzazioni con compliance open-source obbligatoria, OpenTofu è la risposta diretta.

!!! warning "BSL 1.1 non è open source"
    La BSL 1.1 non soddisfa la definizione OSI di open source. Terraform a partire dalla v1.6 non è più open source in senso stretto. OpenTofu mantiene la licenza MPL 2.0 originale.

### Compatibilità con Terraform

OpenTofu è compatibile con Terraform fino alla **v1.5.x**:

- Tutti i file `.tf` e `.tfvars` esistenti funzionano senza modifiche
- Il formato del **state file** è identico
- Tutti i provider del Terraform Registry (`registry.terraform.io`) funzionano con OpenTofu
- OpenTofu ha il proprio registry (`registry.opentofu.org`) con gli stessi provider
- I moduli da Terraform Registry sono compatibili

!!! warning "Divergenza per versioni >= 1.6"
    Feature introdotte in Terraform v1.6+ (es. test framework evoluto, alcune sintassi HCL) potrebbero non essere presenti in OpenTofu con la stessa sintassi o potrebbero essere implementate diversamente. Verificare la compatibility matrix nelle release notes.

### Differenze Chiave rispetto a Terraform

| Feature | Terraform | OpenTofu |
|---------|-----------|----------|
| **Licenza** | BSL 1.1 (non OSI) | MPL 2.0 (open source) |
| **Registry principale** | `registry.terraform.io` | `registry.opentofu.org` |
| **State Encryption** | Non disponibile | Nativa (AES-GCM, PBKDF2) |
| **Terraform Cloud** | Supportato | Non supportato (solo backend open) |
| **Early Evaluation** | Limitata | Estesa (loops più potenti) |
| **Governance** | HashiCorp/IBM | Linux Foundation / CNCF |
| **Binary** | `terraform` | `tofu` |

## Architettura / Come Funziona

OpenTofu mantiene la stessa architettura di Terraform:

```
Files .tf  ──▶  OpenTofu Core  ──▶  Provider Plugin  ──▶  Cloud API
                      │
                      ▼
                State Backend          ◀── State Encryption (feature esclusiva)
              (locale / S3 / GCS       AES-GCM o PBKDF2
               Azure Blob / Consul)
```

Il motore OpenTofu:
1. **Parsa i file HCL** nella directory corrente
2. **Risolve le dipendenze** costruendo un DAG (Directed Acyclic Graph)
3. **Legge lo state** (decriptandolo se l'encryption è attiva)
4. **Calcola il plan** confrontando stato desiderato con stato corrente
5. **Applica le modifiche** tramite i provider
6. **Aggiorna lo state** (criptandolo se l'encryption è attiva)

### State Encryption — Architettura

```
┌─────────────────────────────────────────────────────┐
│              OpenTofu State Encryption               │
│                                                      │
│  State plaintext  ──▶  Key Provider  ──▶  Method    │
│                        (PBKDF2 /         (AES-GCM)  │
│                         AWS KMS /                    │
│                         GCP KMS)                     │
│                                  │                   │
│                                  ▼                   │
│                         Encrypted state file         │
│                         (backend storage)            │
└─────────────────────────────────────────────────────┘
```

Componenti della state encryption:
- **Key Provider**: genera o recupera la chiave crittografica (PBKDF2 da passphrase, AWS KMS, GCP KMS, OpenBao/Vault)
- **Method**: algoritmo di cifratura applicato (attualmente AES-GCM)
- **State / Plan**: target dell'encryption (state file, plan file, o entrambi)

## Configurazione & Pratica

### Installazione

```bash
# macOS (Homebrew)
brew install opentofu

# Linux — binario diretto
wget https://github.com/opentofu/opentofu/releases/download/v1.8.0/tofu_1.8.0_linux_amd64.zip
unzip tofu_1.8.0_linux_amd64.zip
sudo mv tofu /usr/local/bin/tofu
tofu version

# Linux — package repository (Debian/Ubuntu)
curl --proto '=https' --tlsv1.2 -fsSL https://get.opentofu.org/install-opentofu.sh | sh -s -- --install-method deb

# Windows (Chocolatey)
choco install opentofu

# Windows (Winget)
winget install OpenTofu.OpenTofu

# Verifica
tofu version
# OpenTofu v1.8.0
# on linux_amd64
```

### Migrazione da Terraform

La migrazione da Terraform a OpenTofu è progettata per essere senza frizioni per state locali e backend remoti standard.

```bash
# 1. Installa OpenTofu (vedi sopra)

# 2. Verifica la versione Terraform del progetto
terraform version
# Se <= 1.5.x: migrazione diretta
# Se >= 1.6.x: verificare le release notes per incompatibilità

# 3. Opzione A — Alias (cambio rapido, nessuna modifica al PATH)
alias terraform=tofu
# Oppure aggiungere al ~/.bashrc / ~/.zshrc:
echo 'alias terraform=tofu' >> ~/.bashrc

# 4. Opzione B — Sostituzione del binario
which terraform  # es. /usr/local/bin/terraform
sudo mv /usr/local/bin/terraform /usr/local/bin/terraform.bak
sudo ln -s $(which tofu) /usr/local/bin/terraform

# 5. Inizializzare il progetto con OpenTofu
# I file .terraform vengono ricreati, il .terraform.lock.hcl è compatibile
tofu init

# 6. Verificare che il plan non mostri cambiamenti inattesi
tofu plan

# 7. Per backend remoti (S3, GCS, Azure Blob): nessuna migrazione necessaria
# Il format del state file è identico — OpenTofu legge e scrive lo stesso formato
```

!!! warning "Terraform Cloud non è supportato"
    OpenTofu non supporta Terraform Cloud / HCP Terraform come backend. Se il tuo progetto usa Terraform Cloud, devi migrare a un backend alternativo (S3, GCS, Azure Blob, ecc.) prima di passare a OpenTofu.

```bash
# Migrazione da Terraform Cloud — esempio su S3
# 1. Configura il nuovo backend nel codice
# 2. tofu init -migrate-state
# 3. Verifica con tofu state list

# Esempio backend S3 (versions.tf)
terraform {
  backend "s3" {
    bucket         = "my-opentofu-state"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "opentofu-state-lock"
  }
}
```

### Configurazione versions.tf per OpenTofu

```hcl
# versions.tf — progetto OpenTofu
terraform {
  required_version = ">= 1.6.0"  # OpenTofu versioning segue lo stesso schema

  required_providers {
    aws = {
      # OpenTofu registry — stesso path del Terraform Registry
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.23"
    }
  }

  backend "s3" {
    bucket         = "my-opentofu-state"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "opentofu-state-lock"
  }
}
```

!!! tip "registry.opentofu.org vs registry.terraform.io"
    OpenTofu risolve automaticamente i provider da entrambi i registry. Non è necessario cambiare i `source` dei provider per la migrazione. `registry.opentofu.org` è il registry ufficiale di OpenTofu ed è un mirror aggiornato dei provider principali.

### State Encryption (Feature Esclusiva OpenTofu)

La state encryption protegge il contenuto del state file a riposo. Con Terraform, il state viene salvato in chiaro (o con encryption del backend come S3 SSE, che è encryption del trasporto/storage ma non del contenuto). OpenTofu aggiunge encryption a livello applicativo.

```hcl
# versions.tf — State encryption con PBKDF2 (passphrase)
terraform {
  encryption {
    # Key provider: genera la chiave da una passphrase
    key_provider "pbkdf2" "my_passphrase" {
      passphrase = var.state_passphrase  # mai hardcodare!
    }

    # Metodo di cifratura
    method "aes_gcm" "my_method" {
      keys = key_provider.pbkdf2.my_passphrase
    }

    # Applica al state file
    state {
      method   = method.aes_gcm.my_method
      enforced = true  # fallisce se lo state non è criptato
    }

    # Applica anche ai plan file (opzionale ma consigliato)
    plan {
      method = method.aes_gcm.my_method
    }
  }
}
```

```hcl
# versions.tf — State encryption con AWS KMS (produzione)
terraform {
  encryption {
    key_provider "aws_kms" "main" {
      kms_key_id = "arn:aws:kms:eu-west-1:123456789:key/my-key-id"
      region     = "eu-west-1"

      # Credenziali via environment variables (AWS_ACCESS_KEY_ID, etc.)
      # oppure IAM role se su EC2/ECS/Lambda
    }

    method "aes_gcm" "kms_method" {
      keys = key_provider.aws_kms.main
    }

    state {
      method   = method.aes_gcm.kms_method
      enforced = true
    }
  }
}
```

```bash
# Variabile passphrase — passare via environment variable
export TF_VAR_state_passphrase="$(cat /run/secrets/tofu-passphrase)"
tofu plan

# Oppure via -var
tofu apply -var="state_passphrase=$(vault kv get -field=passphrase secret/tofu)"
```

!!! warning "Backup obbligatorio prima di abilitare l'encryption"
    Una volta abilitata con `enforced = true`, OpenTofu rifiuta di leggere state in chiaro. Fare sempre un backup del state file prima di migrare all'encryption. Per migrare uno state esistente: abilitare prima senza `enforced`, eseguire `tofu apply`, poi aggiungere `enforced`.

### Comandi OpenTofu

I comandi sono identici a Terraform con il binario `tofu`:

```bash
# Inizializzazione (scarica provider, configura backend)
tofu init

# Aggiornare i provider
tofu init -upgrade

# Validazione HCL
tofu validate

# Formattazione codice
tofu fmt -recursive

# Plan
tofu plan
tofu plan -var-file=prod.tfvars -out=tfplan

# Apply
tofu apply
tofu apply tfplan
tofu apply -auto-approve

# Destroy
tofu destroy
tofu destroy -target=aws_instance.web[0]

# State
tofu show
tofu state list
tofu state rm aws_instance.old

# Import
tofu import aws_s3_bucket.my_bucket my-bucket-name

# Output
tofu output web_public_ips

# Test (framework di testing integrato)
tofu test
```

### CI/CD con OpenTofu

#### GitHub Actions

```yaml
# .github/workflows/opentofu.yml
name: OpenTofu CI/CD

on:
  push:
    branches: [main]
    paths: ['infra/**']
  pull_request:
    paths: ['infra/**']

jobs:
  plan:
    name: Tofu Plan
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: infra/

    steps:
      - uses: actions/checkout@v4

      - name: Setup OpenTofu
        uses: opentofu/setup-opentofu@v1
        with:
          tofu_version: "1.8.0"

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/GithubActionsOpenTofu
          aws-region: eu-west-1

      - name: Tofu Init
        run: tofu init

      - name: Tofu Validate
        run: tofu validate

      - name: Tofu Plan
        id: plan
        run: tofu plan -var-file=prod.tfvars -out=tfplan -no-color
        env:
          TF_VAR_state_passphrase: ${{ secrets.TOFU_STATE_PASSPHRASE }}

      - name: Comment Plan on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const output = `#### Tofu Plan 📝\`${{ steps.plan.outcome }}\`
            <details><summary>Show Plan</summary>
            \`\`\`\n${{ steps.plan.outputs.stdout }}\n\`\`\`
            </details>`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })

  apply:
    name: Tofu Apply
    runs-on: ubuntu-latest
    needs: plan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production  # richiede approvazione manuale
    defaults:
      run:
        working-directory: infra/

    steps:
      - uses: actions/checkout@v4

      - name: Setup OpenTofu
        uses: opentofu/setup-opentofu@v1
        with:
          tofu_version: "1.8.0"

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/GithubActionsOpenTofu
          aws-region: eu-west-1

      - name: Tofu Init
        run: tofu init

      - name: Tofu Apply
        run: tofu apply -auto-approve -var-file=prod.tfvars
        env:
          TF_VAR_state_passphrase: ${{ secrets.TOFU_STATE_PASSPHRASE }}
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
variables:
  TOFU_VERSION: "1.8.0"
  TF_ROOT: ${CI_PROJECT_DIR}/infra

image:
  name: ghcr.io/opentofu/opentofu:${TOFU_VERSION}
  entrypoint: [""]

cache:
  key: "${CI_COMMIT_REF_SLUG}"
  paths:
    - ${TF_ROOT}/.terraform/

stages:
  - validate
  - plan
  - apply

before_script:
  - cd ${TF_ROOT}
  - tofu init -reconfigure

validate:
  stage: validate
  script:
    - tofu validate
    - tofu fmt -check -recursive

plan:
  stage: plan
  script:
    - tofu plan -var-file=prod.tfvars -out=tfplan
  artifacts:
    name: plan
    paths:
      - ${TF_ROOT}/tfplan
    expire_in: 1 week

apply:
  stage: apply
  script:
    - tofu apply tfplan
  dependencies:
    - plan
  when: manual
  only:
    - main
```

### Tooling Compatibile

Tutti i principali tool dell'ecosistema Terraform supportano OpenTofu:

| Tool | Supporto OpenTofu | Note |
|------|-------------------|------|
| **Terragrunt** | ✅ Completo | `terraform_binary = "tofu"` in `terragrunt.hcl` |
| **Atlantis** | ✅ Completo | `--tofu-bin` flag o config YAML |
| **Infracost** | ✅ Completo | `--terraform-binary tofu` |
| **tflint** | ✅ Completo | Nessuna modifica richiesta |
| **checkov** | ✅ Completo | Nessuna modifica richiesta |
| **terraform-docs** | ✅ Completo | Nessuna modifica richiesta |
| **pre-commit hooks** | ✅ Completo | Sostituire `terraform_` con `tofu_` negli hook |

```hcl
# terragrunt.hcl — configurare OpenTofu come binary
terraform_binary = "tofu"

remote_state {
  backend = "s3"
  config = {
    bucket         = "my-opentofu-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "opentofu-locks"
  }
}
```

```yaml
# atlantis.yaml — configurare OpenTofu
version: 3
projects:
  - name: my-project
    dir: infra/
    terraform_version: v1.8.0
    workflow: opentofu

workflows:
  opentofu:
    plan:
      steps:
        - run: tofu init -input=false
        - run: tofu plan -input=false -out=$PLANFILE
    apply:
      steps:
        - run: tofu apply $PLANFILE
```

## Quando Scegliere OpenTofu vs Terraform

### Tabella Decisionale

| Scenario | Raccomandazione | Motivazione |
|----------|-----------------|-------------|
| Progetto nuovo, nessun vincolo | OpenTofu | Licenza OSI, state encryption, stessa UX |
| Progetto esistente su Terraform <= 1.5 | Migrazione a OpenTofu | Drop-in, nessun rischio |
| Usa Terraform Cloud come backend | Terraform (o migrazione backend) | OpenTofu non supporta Terraform Cloud |
| Compliance open-source obbligatoria | OpenTofu | Unica opzione con MPL 2.0 |
| Vendor/SaaS che riutilizza IaC | OpenTofu | BSL 1.1 limita rivendita commerciale |
| Team già su Terraform >= 1.6 | Valutare caso per caso | Verificare feature divergenti |
| State encryption nativa richiesta | OpenTofu | Feature non presente in Terraform |
| HashiCorp enterprise contracts | Terraform | Supporto commerciale garantito |

!!! tip "Default consigliato: OpenTofu per nuovi progetti"
    Per nuovi progetti senza vincoli specifici, OpenTofu è la scelta consigliata: stessa esperienza, licenza OSI, governance neutrale, state encryption inclusa e roadmap più aperta alla community.

## Best Practices

### Abilitare State Encryption Gradualmente

```hcl
# Step 1: abilitare senza enforced (primo apply migra lo state)
state {
  method   = method.aes_gcm.my_method
  # enforced = true  # non ancora!
}

# Step 2: dopo il primo apply, abilitare enforced
state {
  method   = method.aes_gcm.my_method
  enforced = true
}
```

### Gestione della Passphrase con Variabili d'Ambiente

```bash
# Non passare la passphrase sulla command line (visibile in ps aux)
# ✗ SBAGLIATO
tofu apply -var="state_passphrase=mysecret"

# ✓ CORRETTO: environment variable
export TF_VAR_state_passphrase="$(vault kv get -field=value secret/tofu/passphrase)"
tofu apply

# ✓ CORRETTO in CI/CD: GitHub Actions secret → env var
env:
  TF_VAR_state_passphrase: ${{ secrets.TOFU_STATE_PASSPHRASE }}
```

### Pinning della Versione OpenTofu

```hcl
# versions.tf — pin esplicito per riproducibilità
terraform {
  required_version = "~> 1.8.0"  # accetta 1.8.x, non 1.9.x

  # Usare tofuenv per gestire più versioni localmente
  # https://github.com/tofuutils/tofuenv
}
```

```bash
# tofuenv — gestore versioni OpenTofu (simile a tfenv)
brew install tofuenv
tofuenv install 1.8.0
tofuenv use 1.8.0
tofuenv list
```

!!! tip "Usa il file .opentofu-version"
    Crea un file `.opentofu-version` nella root del progetto con la versione (es. `1.8.0`). `tofuenv` lo legge automaticamente, garantendo che tutti i membri del team usino la stessa versione.

## Troubleshooting

### State Encryption — Errore "state is not encrypted"

```bash
# Sintomo
# Error: Unable to decrypt state: state is not encrypted

# Causa
# enforced = true ma lo state è ancora in chiaro (non è stato migrato)

# Soluzione
# 1. Rimuovere temporaneamente enforced = true
# 2. Eseguire tofu apply (migra lo state → lo cifra)
# 3. Riaggiungere enforced = true
tofu apply  # migra lo state
# Poi aggiungere enforced = true e fare un altro apply
```

### State Encryption — Passphrase Persa

```bash
# Sintomo
# Error: Unable to decrypt state: cipher: message authentication failed

# Causa
# Passphrase sbagliata o modificata rispetto a quella usata per cifrare

# Soluzione
# Non esiste modo di recuperare lo state senza la passphrase originale.
# Prevenzione: salvare la passphrase su un secret manager (Vault, AWS Secrets Manager)
# e fare backup regolari del state plaintext in un vault separato.
```

### Provider Registry — 403 o timeout

```bash
# Sintomo
# Error: Failed to query available provider packages
# registry.opentofu.org: 403 Forbidden (o timeout)

# Causa
# Firewall corporativo che blocca registry.opentofu.org

# Soluzione A: usare Terraform Registry come fallback
# In versions.tf, specificare registry.terraform.io esplicitamente
required_providers {
  aws = {
    source  = "registry.terraform.io/hashicorp/aws"
    version = "~> 5.0"
  }
}

# Soluzione B: mirror locale dei provider
# Configurare un mirror interno in ~/.terraformrc (compatibile con OpenTofu)
provider_installation {
  network_mirror {
    url     = "https://my-mirror.internal/providers/"
    include = ["registry.opentofu.org/*/*"]
  }
  direct {
    exclude = ["registry.opentofu.org/*/*"]
  }
}
```

### Incompatibilità con Terraform >= 1.6

```bash
# Sintomo
# Error: Unsupported argument / unexpected block

# Causa
# Il progetto usa sintassi introdotta in Terraform >= 1.6 non ancora
# implementata in OpenTofu (o implementata con sintassi diversa)

# Soluzione
# 1. Verificare la compatibility matrix su opentofu.org/docs/intro/migration/terraform/
# 2. Se la feature è esclusiva di Terraform (es. Terraform test v2), valutare
#    l'alternativa OpenTofu (opentofu test ha la propria implementazione)

# Confronto versioni
tofu version
terraform version
```

### Lock File Incompatibile

```bash
# Sintomo
# Error: The following providers are required but not installed
# (o hash mismatch nel .terraform.lock.hcl)

# Causa
# Il lock file è stato generato con Terraform e i hash includono
# solo le piattaforme scaricate con terraform init

# Soluzione
# Rigenerare il lock file con OpenTofu
rm .terraform.lock.hcl
tofu init
# Aggiungere piattaforme aggiuntive se necessario
tofu providers lock -platform=linux_amd64 -platform=darwin_arm64
```

## Relazioni

??? info "Terraform Fondamentali — Base comune"
    OpenTofu condivide la stessa sintassi HCL, gli stessi blocchi (`resource`, `variable`, `output`, `module`) e lo stesso ciclo `init → plan → apply`. La documentazione fondamentale di Terraform si applica integralmente a OpenTofu.

    **Approfondimento completo →** [Terraform Fondamentali](./fondamentali.md)

??? info "Terraform State Management — Esteso con Encryption"
    La gestione dello state in OpenTofu aggiunge il layer di encryption nativa sopra i backend standard. Tutti i backend remoti di Terraform (S3, GCS, Azure Blob) sono supportati.

    **Approfondimento completo →** [Terraform State Management](./state-management.md)

??? info "Terraform CI/CD — Pipeline con OpenTofu"
    Le stesse strategie di pipeline si applicano a OpenTofu. L'azione GitHub `opentofu/setup-opentofu` è il drop-in replacement di `hashicorp/setup-terraform`.

    **Approfondimento completo →** [Terraform CI/CD](./ci-cd.md)

## Riferimenti

- [Documentazione ufficiale OpenTofu](https://opentofu.org/docs/)
- [OpenTofu GitHub Repository](https://github.com/opentofu/opentofu)
- [Migration guide Terraform → OpenTofu](https://opentofu.org/docs/intro/migration/terraform/)
- [State Encryption docs](https://opentofu.org/docs/language/state/encryption/)
- [opentofu/setup-opentofu — GitHub Action](https://github.com/opentofu/setup-opentofu)
- [tofuenv — gestore versioni OpenTofu](https://github.com/tofuutils/tofuenv)
- [OpenTofu Registry](https://registry.opentofu.org/)
- [BSL 1.1 — analisi Open Source Initiative](https://opensource.org/blog/the-hashicorp-license-change)
- [Linux Foundation — Annuncio OpenTofu](https://www.linuxfoundation.org/press/linux-foundation-joins-opentofu)
