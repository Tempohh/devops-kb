---
title: "Terraform — Fondamentali"
slug: terraform-fondamentali
category: iac
tags: [terraform, iac, infrastructure-as-code, hcl, hashicorp, provisioning]
search_keywords: [terraform, iac, infrastructure as code, hcl, hashicorp, provider, resource, plan, apply, destroy, state, workspace, moduli, variabili, output, infrastruttura, provisioning, devops, platform engineering]
parent: iac/terraform/_index
related: [iac/terraform/state-management, iac/terraform/moduli, iac/ansible/fondamentali, cloud/aws/compute/ec2, cloud/aws/networking/vpc]
official_docs: https://developer.hashicorp.com/terraform/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Terraform — Fondamentali

## Panoramica

Terraform è lo strumento di Infrastructure as Code (IaC) open-source di HashiCorp, diventato lo standard de-facto per il provisioning dichiarativo di infrastruttura cloud. Permette di descrivere l'infrastruttura desiderata in **HCL** (HashiCorp Configuration Language) e applicarla in modo idempotente su centinaia di provider (AWS, Azure, GCP, Kubernetes, Cloudflare, Vault, etc.). Il principio fondamentale è **dichiarativo**: si descrive lo stato finale desiderato, non i passi per raggiungerlo. Terraform calcola il delta tra lo stato corrente (memorizzato nel *state file*) e lo stato desiderato, pianifica le modifiche e le applica. È lo strumento prioritario da imparare per qualsiasi DevOps o Platform Engineer.

## Concetti Chiave

!!! note "Ciclo di vita Terraform"
    `write` → `terraform init` → `terraform plan` → `terraform apply` → (eventuale `terraform destroy`)

### HCL — HashiCorp Configuration Language

HCL è il linguaggio dichiarativo di Terraform. La sintassi è progettata per essere leggibile dagli umani e parsabile dalle macchine.

```hcl
# Blocco: <tipo> "<provider_tipo>" "<nome_locale>"
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"

  tags = {
    Name = "WebServer"
    Env  = "production"
  }
}
```

### Blocchi Fondamentali

| Blocco | Scopo |
|--------|-------|
| `terraform {}` | Configurazione del backend e versioni richieste |
| `provider {}` | Configura l'autenticazione verso un provider (AWS, Azure, etc.) |
| `resource {}` | Risorsa infrastrutturale da creare/gestire |
| `data {}` | Legge risorse esistenti (read-only) |
| `variable {}` | Input parametrici |
| `output {}` | Valori da esporre dopo l'apply |
| `locals {}` | Variabili locali calcolate |
| `module {}` | Istanzia un modulo riutilizzabile |

### State

Il **state file** (`terraform.tfstate`) è il registro di Terraform: mappa ogni risorsa nel codice HCL alla risorsa reale sul provider. È il componente più critico di Terraform.

!!! warning "State file contiene segreti"
    Il state file può contenere valori sensibili (password, chiavi). Non committarlo mai su Git in chiaro. Usare sempre un backend remoto con encryption at rest.

## Architettura / Come Funziona

```
┌──────────────────────────────────────────────────┐
│                  terraform apply                  │
│                                                    │
│  1. Legge configurazione HCL (.tf files)          │
│  2. Legge lo stato corrente (state file)          │
│  3. Interroga il provider per lo stato reale      │
│  4. Calcola il diff (plan)                        │
│  5. Chiede conferma (o -auto-approve)             │
│  6. Esegue le API call verso il provider          │
│  7. Aggiorna il state file                        │
└──────────────────────────────────────────────────┘

Files .tf  ──▶  Terraform Core  ──▶  Provider Plugin  ──▶  Cloud API
                      │
                      ▼
                State Backend
              (locale / S3 / GCS / etc.)
```

### Terraform Core vs Provider

- **Terraform Core**: motore che interpreta HCL, gestisce il DAG delle dipendenze, calcola il plan
- **Provider**: plugin (scritto in Go) che traduce le risorse HCL in chiamate API verso il cloud/servizio target. Ogni provider è distribuito separatamente tramite il [Terraform Registry](https://registry.terraform.io/).

## Configurazione & Pratica

### Struttura di un Progetto

```
infra/
├── main.tf           # Risorse principali
├── variables.tf      # Definizioni variabili
├── outputs.tf        # Output values
├── providers.tf      # Configurazione provider
├── versions.tf       # Vincoli di versione
├── terraform.tfvars  # Valori variabili (non committare se contiene segreti)
└── modules/          # Moduli custom locali
    └── vpc/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

### versions.tf — Vincoli di Versione

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # >= 5.0.0 e < 6.0.0
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.23"
    }
  }

  # Backend remoto (AWS S3)
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

### providers.tf

```hcl
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Environment = var.environment
      Project     = var.project_name
    }
  }
}

# Multi-region: alias provider
provider "aws" {
  alias  = "us-east-1"
  region = "us-east-1"
}
```

### variables.tf e terraform.tfvars

```hcl
# variables.tf
variable "aws_region" {
  type        = string
  description = "AWS region dove deployare le risorse"
  default     = "eu-west-1"
}

variable "environment" {
  type        = string
  description = "Ambiente (dev, staging, prod)"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "L'ambiente deve essere dev, staging o prod."
  }
}

variable "instance_count" {
  type    = number
  default = 2
}

variable "db_password" {
  type      = string
  sensitive = true  # nascosto negli output del plan
}
```

```hcl
# terraform.tfvars (o prod.tfvars)
aws_region     = "eu-west-1"
environment    = "prod"
instance_count = 3
```

### main.tf — Esempio Completo AWS

```hcl
# Data source: legge la VPC esistente
data "aws_vpc" "main" {
  tags = {
    Name = "main-vpc"
  }
}

# Risorsa: Security Group
resource "aws_security_group" "web" {
  name        = "${var.environment}-web-sg"
  description = "Security group per web server"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Risorsa: EC2 Instance con count
resource "aws_instance" "web" {
  count         = var.instance_count
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"

  vpc_security_group_ids = [aws_security_group.web.id]

  tags = {
    Name = "${var.environment}-web-${count.index + 1}"
  }
}

# Locals: evitare ripetizioni
locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  web_instance_ids = aws_instance.web[*].id
}
```

### outputs.tf

```hcl
output "web_instance_ids" {
  description = "IDs delle EC2 instance web"
  value       = aws_instance.web[*].id
}

output "web_public_ips" {
  description = "IP pubblici delle EC2 instance web"
  value       = aws_instance.web[*].public_ip
}

output "security_group_id" {
  value = aws_security_group.web.id
}
```

### Comandi Principali

```bash
# Inizializzare la directory (scarica provider, configura backend)
terraform init

# Aggiornare i provider alle versioni compatibili
terraform init -upgrade

# Validare la sintassi HCL
terraform validate

# Formattare il codice secondo lo stile standard
terraform fmt -recursive

# Pianificare le modifiche (dry-run)
terraform plan

# Pianificare su un file specifico di variabili
terraform plan -var-file=prod.tfvars -out=tfplan

# Applicare (chiede conferma)
terraform apply

# Applicare il plan salvato (senza chiedere conferma)
terraform apply tfplan

# Applicare senza conferma (CI/CD)
terraform apply -auto-approve

# Distruggere tutte le risorse
terraform destroy

# Distruggere solo una risorsa specifica
terraform destroy -target=aws_instance.web[0]

# Vedere lo state corrente
terraform show
terraform state list

# Importare una risorsa esistente nello state
terraform import aws_s3_bucket.my_bucket my-bucket-name

# Rimuovere una risorsa dallo state (senza distruggerla)
terraform state rm aws_instance.web[0]

# Output values
terraform output web_public_ips
```

### Dipendenze: Implicite vs Esplicite

```hcl
# Dipendenza IMPLICITA: Terraform la riconosce dal riferimento
resource "aws_instance" "web" {
  # Terraform sa che questo dipende da aws_security_group.web
  vpc_security_group_ids = [aws_security_group.web.id]
}

# Dipendenza ESPLICITA: per risorse senza riferimento diretto
resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = data.aws_iam_policy_document.logs.json

  depends_on = [aws_s3_bucket_public_access_block.logs]
}
```

### For Each e Dynamic Blocks

```hcl
# for_each su map
variable "buckets" {
  type = map(object({
    region      = string
    versioning  = bool
  }))
  default = {
    logs    = { region = "eu-west-1", versioning = false }
    backups = { region = "eu-west-1", versioning = true }
  }
}

resource "aws_s3_bucket" "this" {
  for_each = var.buckets
  bucket   = "${var.environment}-${each.key}"
}

# Dynamic block per ridurre la ripetizione
resource "aws_security_group" "dynamic_example" {
  name = "dynamic-sg"

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

## Best Practices

### Struttura per Ambiente

```
infra/
├── modules/           # Moduli riutilizzabili
│   ├── vpc/
│   ├── eks/
│   └── rds/
└── environments/
    ├── dev/
    │   ├── main.tf    # Istanzia moduli con parametri dev
    │   └── backend.tf
    ├── staging/
    └── prod/
```

!!! tip "Un state per ambiente"
    Non usare workspace per separare prod/dev/staging in ambienti reali. Usare directory separate con state file separati. I workspace sono utili per test temporanei.

### Naming Convention

```hcl
# Formato: {env}-{servizio}-{tipo}
resource "aws_instance" "web" {
  tags = {
    Name = "${var.environment}-web-server"
  }
}
```

### Gestione Segreti

```hcl
# MAI hardcodare segreti in HCL
# ✗ SBAGLIATO
resource "aws_db_instance" "main" {
  password = "mysecretpassword"
}

# ✓ CORRETTO: variabile sensitive + recupero da secrets manager
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "prod/db/password"
}

resource "aws_db_instance" "main" {
  password = data.aws_secretsmanager_secret_version.db_password.secret_string
}
```

### Prevenire Distruzioni Accidentali

```hcl
resource "aws_rds_cluster" "main" {
  # Impedisce terraform destroy o recreate accidentale
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [engine_version]  # ignora aggiornamenti minor
  }
}
```

## Troubleshooting

### Lock State

```bash
# Se un'operazione precedente è fallita lasciando il lock
terraform force-unlock LOCK_ID
```

### Refresh State

```bash
# Sincronizzare lo state con la realtà del provider
terraform refresh

# Dalla v0.15+, incluso in plan/apply automaticamente
terraform plan -refresh-only
```

### Errori di Provider

```bash
# Pulire la cache e reinstallare i provider
rm -rf .terraform
terraform init

# Abilitare il logging di debug
TF_LOG=DEBUG terraform plan 2>&1 | head -100
```

## Relazioni

??? info "State Management — Concetto critico"
    La gestione del state è il tema più importante di Terraform in team. Remote state, locking, workspace, import.

    **Approfondimento completo →** [Terraform State Management](./state-management.md)

??? info "Moduli Terraform — Riuso del codice IaC"
    I moduli sono il meccanismo di astrazione e riuso in Terraform. Terraform Registry, moduli custom, versioning.

    **Approfondimento completo →** [Terraform Moduli](./moduli.md)

??? info "Ansible — Configuration Management"
    Ansible complementa Terraform: Terraform provvisiona l'infrastruttura, Ansible configura il software sopra di essa.

    **Approfondimento completo →** [Ansible Fondamentali](../ansible/fondamentali.md)

## Riferimenti

- [Documentazione ufficiale Terraform](https://developer.hashicorp.com/terraform/docs)
- [Terraform Registry](https://registry.terraform.io/)
- [AWS Provider docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Best Practices — Anton Babenko](https://www.terraform-best-practices.com/)
- [tfenv — gestione versioni Terraform](https://github.com/tfutils/tfenv)
- [tflint — linter per HCL](https://github.com/terraform-linters/tflint)
- [Terragrunt — DRY wrapper per Terraform](https://terragrunt.gruntwork.io/)
