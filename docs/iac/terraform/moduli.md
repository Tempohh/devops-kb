---
title: "Terraform — Moduli"
slug: terraform-moduli
category: iac
tags: [terraform, iac, moduli, riuso, hashicorp, hcl, registry, composizione]
search_keywords: [terraform modules, moduli terraform, riuso iac, terraform registry, module source, module versioning, composizione infrastruttura, root module, child module, moduli custom, moduli pubblici, gruntwork, terraform cloud, reusable infrastructure, abstraction, encapsulation, module outputs, module variables]
parent: iac/terraform/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management]
official_docs: https://developer.hashicorp.com/terraform/language/modules
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Terraform — Moduli

## Panoramica

I **moduli** sono il meccanismo di astrazione e riuso di Terraform: permettono di incapsulare un insieme di risorse correlate in un'unità autonoma, richiamabile con parametri variabili. Ogni directory contenente file `.tf` è tecnicamente un modulo — il modulo root è quello da cui si esegue `terraform apply`, mentre i *child module* sono i moduli chiamati tramite il blocco `module {}`. I moduli risolvono il problema del codice IaC duplicato tra ambienti e progetti: si scrive la logica una volta (es. un modulo VPC o EKS), la si parametrizza, e la si istanzia con configurazioni diverse per dev, staging e prod. Il [Terraform Registry](https://registry.terraform.io/) offre migliaia di moduli pubblici mantenuti dalla community e da HashiCorp.

## Concetti Chiave

!!! note "Root Module vs Child Module"
    - **Root module**: la directory da cui si esegue `terraform init/plan/apply`. Ogni progetto ne ha uno.
    - **Child module**: qualsiasi modulo richiamato da un blocco `module {}`. Può essere locale (percorso relativo) o remoto (Registry, Git, S3).

### Anatomia di un Modulo

Un modulo ben strutturato contiene tre file fondamentali:

| File | Scopo |
|------|-------|
| `main.tf` | Risorse che il modulo gestisce |
| `variables.tf` | Input del modulo (interfaccia pubblica) |
| `outputs.tf` | Output del modulo (valori esposti al chiamante) |
| `versions.tf` | (Opzionale) Vincoli di versione Terraform/provider |
| `README.md` | (Opzionale ma raccomandato) Documentazione |

### Sorgenti dei Moduli

```hcl
# Modulo locale
module "vpc" {
  source = "./modules/vpc"
}

# Terraform Registry (formato: <namespace>/<module>/<provider>)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
}

# GitHub (tag specifico)
module "vpc" {
  source = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v1.2.0"
}

# Subdirectory di un repo Git
module "security_group" {
  source = "git::https://github.com/myorg/infra-modules.git//modules/security-group?ref=main"
}

# S3 bucket (archivio .zip)
module "lambda" {
  source = "s3::https://s3.amazonaws.com/mybucket/modules/lambda.zip"
}
```

!!! warning "Versioning obbligatorio per moduli remoti"
    Usare sempre il parametro `version` (Registry) o `?ref=` (Git) per fissare la versione. Un modulo non versionato può cambiare comportamento in modo silenzioso dopo un `terraform init -upgrade`.

## Architettura / Come Funziona

```
Root Module (environments/prod/)
├── main.tf
│   ├── module "vpc"        ──▶  modules/vpc/          (locale)
│   ├── module "eks"        ──▶  terraform-aws-modules/eks/aws  (Registry)
│   └── module "rds"        ──▶  modules/rds/          (locale)
│
├── variables.tf            ◀──  terraform.tfvars / CI pipeline
└── outputs.tf              ──▶  downstream systems

         Input Variables
              │
              ▼
    ┌─────────────────────┐
    │    Child Module      │
    │  variables.tf  ─────│── parametri di ingresso
    │  main.tf            │── risorse interne
    │  outputs.tf  ───────│── valori di uscita
    └─────────────────────┘
              │
              ▼
      Root Module output
```

### Scope e Isolamento

Le risorse di un modulo sono **isolate**: non possono accedere direttamente a variabili o risorse di altri moduli. La comunicazione avviene esclusivamente tramite `variables` (input) e `outputs` (output). Questo garantisce incapsulamento e testabilità.

## Configurazione & Pratica

### Creare un Modulo Locale

```
modules/
└── vpc/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    └── versions.tf
```

```hcl
# modules/vpc/variables.tf
variable "vpc_cidr" {
  type        = string
  description = "CIDR block della VPC"
  default     = "10.0.0.0/16"
}

variable "environment" {
  type        = string
  description = "Nome dell'ambiente (dev, staging, prod)"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR delle subnet pubbliche"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR delle subnet private"
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "azs" {
  type        = list(string)
  description = "Availability Zones da usare"
}
```

```hcl
# modules/vpc/main.tf
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-vpc"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.environment}-igw"
  }
}

resource "aws_subnet" "public" {
  count             = length(var.public_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]

  map_public_ip_on_launch = true

  tags = {
    Name = "${var.environment}-public-${count.index + 1}"
    Tier = "public"
  }
}

resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]

  tags = {
    Name = "${var.environment}-private-${count.index + 1}"
    Tier = "private"
  }
}
```

```hcl
# modules/vpc/outputs.tf
output "vpc_id" {
  description = "ID della VPC"
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "IDs delle subnet pubbliche"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs delle subnet private"
  value       = aws_subnet.private[*].id
}
```

### Chiamare il Modulo

```hcl
# environments/prod/main.tf

module "vpc" {
  source = "../../modules/vpc"

  environment          = "prod"
  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24"]
  azs                  = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

# Accedere agli output del modulo
resource "aws_eks_cluster" "main" {
  name = "prod-eks"

  vpc_config {
    subnet_ids = module.vpc.private_subnet_ids  # output del modulo vpc
  }
}
```

### Usare Moduli dal Terraform Registry

```hcl
# Modulo ufficiale AWS VPC — uno dei più usati
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.1"

  name = "prod-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false  # true in dev per risparmiare, false in prod per HA
  enable_dns_hostnames = true

  tags = {
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}

# Modulo EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "prod-eks"
  cluster_version = "1.29"

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    general = {
      desired_size = 3
      min_size     = 2
      max_size     = 6
      instance_types = ["m5.large"]
    }
  }
}
```

### Istanze Multiple dello Stesso Modulo

```hcl
# Stesso modulo, ambienti diversi — with count
module "app" {
  count  = var.environment == "prod" ? 3 : 1
  source = "./modules/app-server"

  index       = count.index
  environment = var.environment
}

# With for_each — raccomandato per istanze denominate
module "service" {
  for_each = {
    frontend = { port = 80,  replicas = 3 }
    backend  = { port = 8080, replicas = 2 }
    worker   = { port = 0,   replicas = 5 }
  }

  source = "./modules/service"

  name        = each.key
  port        = each.value.port
  replicas    = each.value.replicas
  environment = var.environment
}

# Accedere agli output di istanze for_each
output "service_ips" {
  value = { for k, v in module.service : k => v.ip_address }
}
```

### Passare Provider a un Modulo

```hcl
# Per moduli che gestiscono risorse multi-region o multi-account
provider "aws" {
  alias  = "eu"
  region = "eu-west-1"
}

provider "aws" {
  alias  = "us"
  region = "us-east-1"
}

module "cdn_cert" {
  source = "./modules/acm-certificate"

  # Certificati ACM per CloudFront devono essere in us-east-1
  providers = {
    aws = aws.us
  }

  domain_name = "example.com"
}
```

## Best Practices

### Struttura Repository

```
infra/
├── modules/               # Moduli riutilizzabili interni
│   ├── vpc/
│   ├── eks/
│   ├── rds/
│   └── lambda-function/
├── environments/
│   ├── dev/
│   │   ├── main.tf        # Istanzia moduli con config dev
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── backend.tf     # State separato per ambiente
│   ├── staging/
│   └── prod/
└── shared/                # Risorse condivise tra ambienti
    ├── ecr/
    └── route53/
```

!!! tip "Monorepo vs repository separati"
    - **Monorepo** (tutti i moduli nello stesso repo): più semplice, versionamento implicito tramite Git tag del repo
    - **Repository separati** (un repo per modulo): maggiore indipendenza, versionamento granulare — preferito per team grandi o moduli condivisi tra più organizzazioni

### Interfaccia Pulita

```hcl
# ✓ CORRETTO: variabili con tipo, descrizione e validation
variable "environment" {
  type        = string
  description = "Nome ambiente per tagging e naming delle risorse"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Valori consentiti: dev, staging, prod."
  }
}

# ✓ CORRETTO: output con descrizione
output "database_endpoint" {
  description = "Endpoint di connessione al database RDS"
  value       = aws_db_instance.main.endpoint
}

# ✓ CORRETTO: output sensitive per valori segreti
output "database_password" {
  description = "Password generata per il database"
  value       = random_password.db.result
  sensitive   = true
}
```

### Versionamento dei Moduli Interni

```hcl
# Usare tag Git per i moduli interni
module "vpc" {
  source = "git::https://github.com/myorg/infra-modules.git//modules/vpc?ref=v2.1.0"
}

# In dev è accettabile puntare a un branch, mai in prod
module "vpc_experimental" {
  source = "git::https://github.com/myorg/infra-modules.git//modules/vpc?ref=feature/ipv6"
}
```

### Anti-pattern da Evitare

```hcl
# ✗ SBAGLIATO: modulo senza versione da Registry
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  # Manca version — si aggiorna silenziosamente!
}

# ✗ SBAGLIATO: passare tutto come variabile (over-abstraction)
module "everything" {
  source         = "./modules/kitchen-sink"
  create_vpc     = true
  create_eks     = true
  create_rds     = true
  # Questo non è un modulo, è un "mega-modulo" — difficile da testare e mantenere
}

# ✗ SBAGLIATO: hardcodare valori specifici dell'ambiente in un modulo
resource "aws_instance" "web" {
  ami = "ami-0c55b159cbfafe1f0"  # AMI specifica eu-west-1 — rompe in altre region
}
# ✓ CORRETTO: usare data source
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}
```

## Troubleshooting

### Modulo non trovato dopo modifica della sorgente

```bash
# Sempre eseguire init dopo aver cambiato source o version di un modulo
terraform init -upgrade

# Se il modulo è locale e le modifiche non si riflettono
# verificare che non ci sia una cache .terraform
rm -rf .terraform
terraform init
```

### Conflitti di Provider tra Moduli

```hcl
# Errore: "Provider configuration not present"
# Soluzione: dichiarare esplicitamente i provider richiesti nel modulo
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
      # Necessario se il modulo è chiamato con providers = {}
      configuration_aliases = [aws.primary, aws.secondary]
    }
  }
}
```

### Refactoring: Spostare Risorse in un Modulo

```hcl
# Scenario: la risorsa aws_vpc.main esisteva nel root module
# e ora vuoi spostarla nel modulo ./modules/vpc

# PRIMA (terraform.tfstate puntava a aws_vpc.main)
resource "aws_vpc" "main" { ... }

# DOPO (nel root module)
module "vpc" {
  source = "./modules/vpc"
}

# Aggiornare lo state senza distruggere la risorsa:
terraform state mv aws_vpc.main module.vpc.aws_vpc.this
```

## Relazioni

??? info "Fondamentali Terraform — Prerequisito"
    I moduli usano gli stessi blocchi HCL (`resource`, `variable`, `output`, `data`). Prima di studiare i moduli, comprendere HCL e il ciclo plan/apply è essenziale.

    **Approfondimento completo →** [Terraform Fondamentali](./fondamentali.md)

??? info "State Management — Moduli e state"
    Con i moduli, le risorse nello state vengono prefissate con il percorso del modulo (es. `module.vpc.aws_vpc.this`). La gestione dello state diventa più complessa con moduli annidati.

    **Approfondimento completo →** [Terraform State Management](./state-management.md)

## Riferimenti

- [Documentazione ufficiale — Modules](https://developer.hashicorp.com/terraform/language/modules)
- [Terraform Registry](https://registry.terraform.io/)
- [terraform-aws-modules — GitHub](https://github.com/terraform-aws-modules)
- [Standard Module Structure — HashiCorp](https://developer.hashicorp.com/terraform/language/modules/develop/structure)
- [Terraform Best Practices — Modules](https://www.terraform-best-practices.com/modules)
