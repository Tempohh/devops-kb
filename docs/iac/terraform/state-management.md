---
title: "Terraform — State Management"
slug: terraform-state-management
category: iac
tags: [terraform, state, remote-state, state-locking, workspace, iac]
search_keywords: [terraform state, remote state, state locking, tfstate, s3 backend, gcs backend, azure blob backend, workspace, state migration, import, drift detection, state corruption, terraform cloud, terraform enterprise]
parent: iac/terraform/_index
related: [iac/terraform/fondamentali, iac/terraform/moduli, cloud/aws/compute/ec2, cloud/aws/iam/_index]
official_docs: https://developer.hashicorp.com/terraform/language/state
status: complete
difficulty: advanced
last_updated: 2026-03-24
---

# Terraform — State Management

## Panoramica

Lo state di Terraform è il meccanismo attraverso cui Terraform mappa le risorse dichiarate nel codice HCL alle risorse reali sul provider cloud. Senza il file di state, Terraform non saprebbe quali risorse gestisce, se sono aggiornate, o se sono ancora necessarie. In ambienti di team, la gestione dello state diventa il punto critico che può causare race condition, corruzione dei dati, o applicazioni parallele distruttive se non gestita correttamente. Il remote state con locking è il prerequisito assoluto per qualsiasi uso collaborativo di Terraform.

## Concetti Chiave

### Cosa Contiene lo State

```json
// terraform.tfstate (struttura semplificata)
{
  "version": 4,
  "terraform_version": "1.6.0",
  "serial": 42,
  "lineage": "12345678-abcd-...",
  "outputs": {
    "vpc_id": { "value": "vpc-0a1b2c3d", "type": "string" }
  },
  "resources": [
    {
      "module": "module.vpc",
      "mode": "managed",
      "type": "aws_vpc",
      "name": "main",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [
        {
          "schema_version": 1,
          "attributes": {
            "id": "vpc-0a1b2c3d",
            "cidr_block": "10.0.0.0/16",
            "tags": { "Name": "main-vpc", "Environment": "prod" }
          }
        }
      ]
    }
  ]
}
```

!!! warning "Non modificare il tfstate manualmente"
    Il file tfstate è un database interno di Terraform. Modificarlo manualmente è rischioso e quasi sempre sbagliato. Usare `terraform state` commands per operazioni sul state.

### State Locking

Il locking previene che due operazioni Terraform in parallelo modifichino lo state contemporaneamente, causando corruzione.

```
Operatore A: terraform apply  ──▶  Acquisce lock  ──▶  Esegue  ──▶  Rilascia lock
Operatore B: terraform apply  ──▶  Attende lock...                    ──▶  Acquisce lock
```

Il backend remoto con locking è **obbligatorio** per team con più di 1 persona.

### Backend

Il backend determina dove viene memorizzato il file di state e se il locking è supportato.

| Backend | Locking | Storage | Note |
|---------|---------|---------|------|
| **local** (default) | No | File locale | Solo per sviluppo singolo |
| **S3 + DynamoDB** | Si (DynamoDB) | S3 | Standard per AWS |
| **GCS** | Si (nativo) | Google Cloud Storage | Standard per GCP |
| **Azure Blob** | Si (nativo) | Azure Blob Storage | Standard per Azure |
| **Terraform Cloud** | Si | HashiCorp Cloud | SaaS, include CI/CD |
| **PostgreSQL** | Si | DB relazionale | Self-hosted |

## Architettura / Come Funziona

```
┌────────────────────────────────────────────────────────────┐
│                   Operazione Terraform                      │
│                                                              │
│  1. Legge .terraform/terraform.tfstate (metadata backend)  │
│  2. Connessione al backend remoto (es. S3)                 │
│  3. Acquisce il lock (es. DynamoDB item)                   │
│  4. Scarica lo state corrente                              │
│  5. Legge la configurazione HCL                            │
│  6. Chiama le API del provider per stato reale             │
│  7. Calcola il diff → plan                                 │
│  8. Esegue le modifiche                                    │
│  9. Aggiorna lo state remoto                               │
│  10. Rilascia il lock                                      │
└────────────────────────────────────────────────────────────┘
```

### State Lineage e Serial

- **lineage**: UUID generato alla creazione dello state, identifica univocamente questo state
- **serial**: contatore incrementale, aumenta ad ogni scrittura. Previene applicazione di state "vecchi"

Se Terraform rileva che il serial locale è inferiore al remoto, si rifiuta di sovrascrivere per prevenire perdite di dati.

## Configurazione & Pratica

### Backend S3 + DynamoDB (AWS)

```hcl
# versions.tf
terraform {
  backend "s3" {
    bucket         = "mycompany-terraform-state"
    key            = "prod/us-east-1/networking/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:us-east-1:123456789:key/abcd-1234"

    # DynamoDB per il locking
    dynamodb_table = "terraform-state-lock"
  }
}
```

```hcl
# bootstrap/main.tf — Crea le risorse per il backend
# (bootstrapping: applicato una volta manualmente)
resource "aws_s3_bucket" "terraform_state" {
  bucket = "mycompany-terraform-state"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_state_lock" {
  name           = "terraform-state-lock"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

### Backend GCS (Google Cloud)

```hcl
terraform {
  backend "gcs" {
    bucket  = "mycompany-terraform-state"
    prefix  = "prod/networking"
    # GCS supporta locking nativo — niente DynamoDB
  }
}
```

### Backend Azure Blob

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "terraform-state-rg"
    storage_account_name = "mycompanytfstate"
    container_name       = "tfstate"
    key                  = "prod.networking.tfstate"
  }
}
```

### Organizzazione dei State File

La struttura dei key S3 deve riflettere la gerarchia dell'infrastruttura:

```
s3://mycompany-terraform-state/
├── global/
│   ├── iam/terraform.tfstate
│   └── route53/terraform.tfstate
├── prod/
│   ├── eu-west-1/
│   │   ├── networking/terraform.tfstate
│   │   ├── eks/terraform.tfstate
│   │   └── rds/terraform.tfstate
│   └── us-east-1/
│       └── networking/terraform.tfstate
├── staging/
│   └── eu-west-1/
│       └── networking/terraform.tfstate
└── dev/
    └── eu-west-1/
        └── networking/terraform.tfstate
```

### Remote State Data Source

Condividere output tra state file separati tramite `terraform_remote_state`:

```hcl
# networking/main.tf — Esporta il VPC ID
output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
```

```hcl
# eks/main.tf — Legge l'output del networking
data "terraform_remote_state" "networking" {
  backend = "s3"
  config = {
    bucket = "mycompany-terraform-state"
    key    = "prod/eu-west-1/networking/terraform.tfstate"
    region = "us-east-1"
  }
}

resource "aws_eks_cluster" "main" {
  name = "prod-cluster"

  vpc_config {
    subnet_ids = data.terraform_remote_state.networking.outputs.private_subnet_ids
  }
}
```

### Comandi di State Management

```bash
# Vedere tutte le risorse nel state
terraform state list

# Vedere i dettagli di una risorsa specifica
terraform state show aws_instance.web

# Spostare una risorsa (rinominare nel codice senza ricreare)
terraform state mv aws_instance.web aws_instance.web_server

# Rimuovere una risorsa dal state (senza distruggerla)
terraform state rm aws_instance.legacy

# Importare una risorsa esistente nel state
terraform import aws_instance.web i-1234567890abcdef0

# Pull dello state corrente (stampa JSON)
terraform state pull > current-state.json

# Push dello state (usare con ESTREMA cautela)
terraform state push modified-state.json

# Forzare la rimozione di un lock bloccato
terraform force-unlock LOCK_ID

# Verificare se il state è sincronizzato con la realtà
terraform plan -refresh-only
```

### Migrazione Backend

```bash
# Migrare da local a S3
# 1. Aggiungere la configurazione backend in versions.tf
# 2. Eseguire init — Terraform chiede se migrare lo state

terraform init -migrate-state

# Oppure per rifiutare la migrazione automatica
terraform init -reconfigure
```

### Workspace

I workspace sono copie separate del state nella stessa configurazione.

```bash
# Workspace predefinito: "default"
terraform workspace list
terraform workspace new staging
terraform workspace select staging
terraform workspace show       # workspace corrente
terraform workspace delete staging
```

```hcl
# Usare il workspace nel codice
resource "aws_instance" "web" {
  instance_type = terraform.workspace == "prod" ? "t3.large" : "t3.micro"

  tags = {
    Environment = terraform.workspace
  }
}
```

!!! warning "Workspace non sono ambienti prod/staging"
    I workspace condividono lo stesso backend e lo stesso codice. Per ambienti realmente separati (prod, staging, dev), usare **directory separate** con state file separati. I workspace sono adatti per feature branch temporanei o test, non per la separazione prod/staging.

### Importare Risorse Esistenti

```bash
# Importare una risorsa già esistente sul provider
terraform import aws_vpc.main vpc-0a1b2c3d4e5f6a7b8

# Import di risorse con for_each (v1.5+, tramite import block)
```

```hcl
# Import block (Terraform >= 1.5) — dichiarativo
import {
  to = aws_vpc.main
  id = "vpc-0a1b2c3d4e5f6a7b8"
}

import {
  to = aws_subnet.private["eu-west-1a"]
  id = "subnet-0a1b2c3d4e5f6a7b8"
}
```

## Best Practices

### Struttura per Minimizzare il Raggio d'Esplosione

Separare lo state per componente: se un `terraform apply` fallisce, impatta solo lo state di quel componente.

```
# ✓ State separati
prod/networking/    # VPC, subnet, routing
prod/eks/           # Cluster EKS
prod/rds/           # Database
prod/apps/service-a # Deployment applicativo

# ✗ Un unico state per tutto
prod/                # TUTTO — ogni apply è rischioso
```

### Proteggere il State File

```hcl
# IAM policy per il bucket S3 dello state
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::mycompany-terraform-state/*",
      "Condition": {
        "StringEquals": { "s3:prefix": ["prod/"] }
      }
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-lock"
    }
  ]
}
```

### State in CI/CD

```yaml
# .github/workflows/terraform.yml
- name: Terraform Plan
  run: |
    terraform init \
      -backend-config="bucket=${{ secrets.TF_STATE_BUCKET }}" \
      -backend-config="key=${{ env.TF_STATE_KEY }}" \
      -backend-config="region=${{ env.AWS_REGION }}"
    terraform plan -out=tfplan

- name: Terraform Apply (main only)
  if: github.ref == 'refs/heads/main'
  run: terraform apply -auto-approve tfplan
```

## Troubleshooting

### State Corrotto

```bash
# Recuperare una versione precedente dello state (se S3 versioning abilitato)
aws s3api list-object-versions \
  --bucket mycompany-terraform-state \
  --prefix prod/networking/terraform.tfstate

# Scaricare una versione precedente
aws s3api get-object \
  --bucket mycompany-terraform-state \
  --key prod/networking/terraform.tfstate \
  --version-id "PREVIOUS_VERSION_ID" \
  recovered-state.json

# Push del state recuperato
terraform state push recovered-state.json
```

### Drift Detection

```bash
# Rilevare risorse che sono cambiate fuori da Terraform
terraform plan -refresh-only

# In CI/CD — alert se c'è drift
terraform plan -refresh-only -detailed-exitcode
# exit code 0 = nessun drift
# exit code 2 = drift rilevato
```

### Lock Bloccato

```bash
# Verificare il lock su DynamoDB
aws dynamodb get-item \
  --table-name terraform-state-lock \
  --key '{"LockID": {"S": "mycompany-terraform-state/prod/networking/terraform.tfstate"}}'

# Rimuovere il lock (con cautela, verificare prima che nessuno stia applicando)
terraform force-unlock "LOCK_ID_FROM_ERROR_MESSAGE"
```

## Relazioni

??? info "Terraform Fondamentali — Prerequisito"
    Concetti base di Terraform: HCL, provider, resource, plan/apply.

    **Approfondimento completo →** [Terraform Fondamentali](./fondamentali.md)

??? info "Terraform Moduli — Riuso del Codice"
    I moduli condividono output tramite remote state data source.

    **Approfondimento completo →** [Terraform Moduli](./moduli.md)

## Riferimenti

- [Terraform Backends documentation](https://developer.hashicorp.com/terraform/language/backend)
- [S3 Backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [State Management commands](https://developer.hashicorp.com/terraform/cli/state)
- [Import blocks (v1.5+)](https://developer.hashicorp.com/terraform/language/import)
- [Terraform Cloud — remote state](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/state)
