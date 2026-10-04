---
title: "Packer — Golden Image Pipeline"
slug: golden-image-pipeline
category: iac
tags: [packer, golden-image, immutable-infrastructure, ami, hcl2, hashicorp, hardening, ci-cd, hcp-packer]
search_keywords: [packer, hashicorp packer, golden image, golden ami, immutable infrastructure, infrastruttura immutabile, AMI, amazon-ebs, azure-arm, compute gallery, managed image, googlecompute, machine image, image baking, bake vs fry, packer hcl2, packer init, packer build, packer validate, packer fmt, manifest post-processor, HCP Packer, packer registry, channel, revoca immagine, ami_regions, copy ami, cross-region ami, IMDSv2, CIS benchmark, InSpec, Goss, instance refresh, launch template, aws_ami data source, packer github actions, packer oidc, cloud-init vs packer, packer ansible provisioner, packer shell provisioner, packer ssh timeout, packer winrm, Error waiting for AMI, vulnerability scan ami, Inspector, Trivy rootfs, pipeline immagini]
parent: iac/_index
related: [iac/terraform/fondamentali, iac/terraform/ci-cd, iac/ansible/fondamentali, cloud/aws/compute/ec2-autoscaling, cloud/aws/compute/ec2, security/supply-chain/image-scanning, ci-cd/github-actions/workflow-avanzati]
official_docs: https://developer.hashicorp.com/packer/docs
status: reviewed
difficulty: intermediate
last_updated: 2026-10-02
last_verified: 2026-10-04
---

# Packer — Golden Image Pipeline

## Panoramica

**HashiCorp Packer** costruisce *machine image* (AMI AWS, Azure Managed Image / Compute Gallery, GCP image, VMware, Docker) a partire da una definizione dichiarativa in HCL2. Il pattern è la **golden image**: un'immagine pre-configurata, hardenizzata, scansionata e versionata, da cui le istanze partono già pronte (*bake*), invece di configurarsi al boot con cloud-init o Ansible pull (*fry*). Si usa quando servono tempi di scale-out rapidi, riproducibilità, assenza di drift e una baseline di sicurezza verificabile. **Non** è la scelta giusta in un'architettura container-first (l'immagine è l'OCI image, il nodo è gestito: EKS/GKE managed node group, Bottlerocket) né per workload effimeri dove un boot script di 20 secondi basta.

Packer è un tool di *build*, non di provisioning dell'infrastruttura: produce l'artefatto, poi [Terraform](../terraform/fondamentali.md) lo referenzia in launch template / ASG.

## Concetti Chiave

### Bake vs Fry

| Aspetto | Golden image (bake) | Configuration at boot (fry) |
|---|---|---|
| Tempo di scale-out | Secondi (software già installato) | Minuti (download pacchetti + config) |
| Drift tra istanze | Nullo: stessa immagine ovunque | Possibile: dipende da repo/mirror al momento del boot |
| Riproducibilità | Alta (immagine versionata, immutabile) | Media (dipende da versioni upstream) |
| Dipendenze al boot | Nessuna (no internet/mirror richiesto) | Repository, Ansible control node, secret |
| Patching | Rebuild + rollout (instance refresh) | Patch in-place o rerun |
| Costo operativo | Pipeline di build da mantenere | Boot script da mantenere |
| Rollback | Torna al tag/AMI precedente | Difficile, stato mutato |

!!! tip "Approccio ibrido"
    Il pattern più robusto: **bake** di OS, hardening, agent e runtime (cambiano raramente); **fry** minimo al boot solo per ciò che è specifico dell'ambiente (hostname, config endpoint, secret via IAM role). Mai bakeare secret nell'immagine.

### Componenti di Packer

| Componente | Ruolo |
|---|---|
| **Plugin** | Distribuiti separatamente dal core (`amazon`, `azure`, `googlecompute`, `ansible`), scaricati con `packer init` |
| **Source** | Come e dove costruire: `source "amazon-ebs" "web"` lancia un'istanza temporanea da una base AMI |
| **Build** | Collega una o più source a provisioner e post-processor |
| **Provisioner** | Configura l'istanza temporanea: `shell`, `file`, `ansible`, `powershell` |
| **Post-processor** | Opera sull'artefatto finale: `manifest`, `compress`, `checksum` |
| **Variable / locals** | Parametrizzazione (`-var`, `-var-file`, `PKR_VAR_*`) |
| **HCP Packer** | Registry SaaS: metadata, channel, revoca delle immagini |

### Flusso di una build AWS

```
packer build
   │
   ├─ 1. Risolve base AMI (source_ami_filter) e crea key pair + security group temporanei
   ├─ 2. Lancia istanza EC2 temporanea (subnet indicata)
   ├─ 3. Si connette via SSH (o WinRM) con credenziali effimere
   ├─ 4. Esegue i provisioner in ordine (hardening, pacchetti, agent)
   ├─ 5. Ferma l'istanza e crea lo snapshot EBS → registra l'AMI
   ├─ 6. Copia l'AMI nelle region/account indicati (ami_regions, ami_users)
   ├─ 7. Termina istanza, cancella key pair e security group temporanei
   └─ 8. Post-processor (manifest → manifest.json con l'AMI ID)
```

## Architettura / Come Funziona

La pipeline completa non si ferma alla build: l'immagine diventa un artefatto di supply chain che attraversa scan, test e promozione prima di arrivare in produzione.

```
 commit su repo "images"
        │
        ▼
 ┌──────────────┐   OIDC    ┌─────────────────────┐
 │ GitHub       │──────────▶│ AWS IAM role (build) │
 │ Actions      │           └─────────────────────┘
 └──────┬───────┘
        │ packer init / validate / build
        ▼
 AMI candidate  (tag: git_sha, stage=candidate)
        │
        ├─▶ Test: InSpec / Goss su istanza di test
        ├─▶ Scan CVE: Amazon Inspector / Trivy rootfs
        ▼
 Promozione: tag stage=approved  (o HCP Packer channel "production")
        │
        ▼
 Terraform: data "aws_ami" (filtro su tag) → launch template → ASG instance refresh
        │
        ▼
 Rollback = puntare al tag/AMI precedente e rilanciare l'instance refresh
```

!!! note "Immagine = artefatto immutabile"
    Una volta promossa, un'AMI non si modifica mai. Una correzione genera una nuova immagine con nuovo SHA. La sicurezza della pipeline è nella tracciabilità: ogni AMI ha tag `git_sha`, `build_id`, `base_ami`, `packer_version`.

## Configurazione & Pratica

### Struttura del repository

```text
images/
├── web.pkr.hcl            # source + build
├── plugins.pkr.hcl        # blocco packer { required_plugins }
├── variables.pkr.hcl      # variable definitions
├── vars/
│   ├── dev.pkrvars.hcl
│   └── prod.pkrvars.hcl
├── scripts/
│   ├── 00-base.sh
│   ├── 10-hardening.sh
│   └── 99-cleanup.sh
├── tests/
│   └── web.spec.rb        # InSpec (o goss.yaml)
└── .github/workflows/build-image.yml
```

### Plugin e variabili

```hcl
# plugins.pkr.hcl
packer {
  required_version = ">= 1.11.0"

  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1.3"
    }
    ansible = {
      source  = "github.com/hashicorp/ansible"
      version = "~> 1.1"
    }
  }
}
```

```hcl
# variables.pkr.hcl
variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "subnet_id" {
  type = string
}

variable "git_sha" {
  type    = string
  default = "local"
}

variable "kms_key_id" {
  type    = string
  default = ""
}

variable "copy_regions" {
  type    = list(string)
  default = ["eu-central-1"]
}

locals {
  timestamp = formatdate("YYYYMMDD-hhmm", timestamp())
  ami_name  = "web-golden-${var.git_sha}-${local.timestamp}"
}
```

### Source e build (AWS)

```hcl
# web.pkr.hcl
source "amazon-ebs" "web" {
  region        = var.region
  instance_type = "t3.medium"
  ami_name      = local.ami_name
  subnet_id     = var.subnet_id              # evita errore "no default VPC"
  ssh_username  = "ec2-user"
  ssh_timeout   = "10m"

  # Base AMI: ultima Amazon Linux 2023 ufficiale
  source_ami_filter {
    filters = {
      name                = "al2023-ami-2023.*-x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners      = ["amazon"]
    most_recent = true
  }

  # Cifratura EBS dell'immagine risultante
  encrypt_boot = true
  kms_key_id   = var.kms_key_id != "" ? var.kms_key_id : null

  # IMDSv2 (Instance Metadata Service v2, accesso ai metadata solo con token di sessione,
  # mitiga il furto di credenziali via SSRF): obbligatorio di default per le istanze
  # lanciate dall'AMI (imds_support) e già nell'istanza di build (metadata_options)
  imds_support = "v2.0"
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  # Distribuzione cross-region. Una KMS key è regionale: con una CMK custom serve
  # una chiave per ogni region di destinazione, altrimenti la copia fallisce
  ami_regions = var.copy_regions
  # region_kms_key_ids = { "eu-central-1" = "alias/golden-image" }

  tags = {
    Name       = local.ami_name
    git_sha    = var.git_sha
    stage      = "candidate"
    managed_by = "packer"
  }
  snapshot_tags = {
    git_sha = var.git_sha
  }
}

build {
  name    = "web"
  sources = ["source.amazon-ebs.web"]

  provisioner "shell" {
    scripts = [
      "scripts/00-base.sh",
      "scripts/10-hardening.sh",
    ]
    execute_command = "sudo -E bash '{{ .Path }}'"
  }

  provisioner "ansible" {
    playbook_file   = "../ansible/web.yml"
    use_proxy       = false
    extra_arguments = ["--extra-vars", "env=golden"]
  }

  # SEMPRE ultimo: rimuove chiavi, history, log, machine-id
  provisioner "shell" {
    script          = "scripts/99-cleanup.sh"
    execute_command = "sudo -E bash '{{ .Path }}'"
  }

  post-processor "manifest" {
    output     = "manifest.json"
    strip_path = true
  }
}
```

### Comandi essenziali

```bash
packer init .                                   # scarica i plugin dichiarati
packer fmt -check -recursive .                  # formattazione (in CI: -check)
packer validate -var-file=vars/prod.pkrvars.hcl .
packer build -var-file=vars/prod.pkrvars.hcl -var "git_sha=$(git rev-parse --short HEAD)" .

# Debug: ferma e chiede conferma a ogni step, non distrugge l'istanza in caso di errore
packer build -debug -on-error=ask .

# Estrarre l'AMI ID prodotto
jq -r '.builds[-1].artifact_id | split(":")[1]' manifest.json
```

### Hardening e baseline

```bash
#!/usr/bin/env bash
# scripts/10-hardening.sh — baseline minima (adattare al benchmark CIS scelto)
set -euo pipefail

# Aggiornamenti di sicurezza.
# Su AL2023 i repo sono versionati (deterministici): senza --releasever=latest si
# ottengono solo i pacchetti della release della base AMI, quindi tieni la base aggiornata
dnf -y upgrade --security

# SSH: no password, no root
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'             /etc/ssh/sshd_config

# Parametri kernel
cat >/etc/sysctl.d/99-hardening.conf <<'EOF'
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.tcp_syncookies = 1
kernel.kptr_restrict = 2
EOF

# Servizi inutili
systemctl disable --now postfix 2>/dev/null || true

# Audit
dnf -y install audit && systemctl enable auditd
```

```bash
#!/usr/bin/env bash
# scripts/99-cleanup.sh — nessuna credenziale deve restare nell'immagine
set -euo pipefail

rm -f  /home/*/.ssh/authorized_keys /root/.ssh/authorized_keys
rm -f  /etc/ssh/ssh_host_*             # host key uniche per istanza: rigenerate al primo boot
rm -rf /tmp/* /var/tmp/*
rm -f  /var/log/*.log /var/log/messages
find /var/log -type f -exec truncate -s 0 {} \;
: > /etc/machine-id                    # rigenerato al primo boot
cloud-init clean --logs --seed
history -c; rm -f /home/*/.bash_history /root/.bash_history
```

!!! warning "Chiavi SSH e credenziali temporanee"
    Packer inietta una key pair effimera per la connessione: rimuoverla (`authorized_keys`) nello script finale, altrimenti resta valida nell'AMI. Non passare mai secret con `-var` in chiaro nei log: usa variabili `sensitive = true` e credenziali da ruolo IAM/OIDC, non da file.

### Pipeline GitHub Actions con OIDC

```yaml
# .github/workflows/build-image.yml
name: build-golden-image
on:
  push:
    branches: [main]
    paths: ["images/**"]
  workflow_dispatch:

permissions:
  id-token: write      # richiesto per OIDC
  contents: read

jobs:
  bake:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: images
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/packer-build
          aws-region: eu-west-1

      - uses: hashicorp/setup-packer@v3     # mai @main: supply chain della pipeline
        with:
          version: "1.11.2"

      - run: packer init .
      - run: packer fmt -check -recursive .
      - run: packer validate -var "subnet_id=${{ vars.BUILD_SUBNET_ID }}" .

      - name: Build
        run: >
          packer build
          -var "subnet_id=${{ vars.BUILD_SUBNET_ID }}"
          -var "git_sha=${GITHUB_SHA::8}" .

      - name: Estrai AMI ID
        id: ami
        run: echo "id=$(jq -r '.builds[-1].artifact_id | split(":")[1]' manifest.json)" >> "$GITHUB_OUTPUT"

      - name: Scan CVE (Amazon Inspector)
        run: ./scripts/inspector-scan.sh "${{ steps.ami.outputs.id }}"

      - name: Test InSpec su istanza effimera
        run: ./scripts/run-inspec.sh "${{ steps.ami.outputs.id }}"

      - name: Promuovi (tag stage=approved)
        run: |
          aws ec2 create-tags --resources "${{ steps.ami.outputs.id }}" \
            --tags Key=stage,Value=approved
```

**OIDC** (OpenID Connect) permette a GitHub di ottenere credenziali AWS temporanee assumendo un ruolo IAM, senza access key di lunga durata salvate nei secret. La trust policy del ruolo `packer-build` deve limitare il `sub` del token OIDC al repo e branch corretti (`repo:org/images:ref:refs/heads/main`). Permessi minimi: `ec2:RunInstances`, `CreateImage`, `CopyImage`, `CreateTags`, `CreateKeyPair`, `CreateSecurityGroup` e relative operazioni di cleanup (vedi documentazione plugin amazon).

### Test dell'immagine prima della promozione

```ruby
# tests/web.spec.rb — InSpec
describe service('sshd') do
  it { should be_enabled }
end

describe sshd_config do
  its('PasswordAuthentication') { should eq 'no' }
  its('PermitRootLogin')        { should eq 'no' }
end

# Le host key SSH non devono essere bakeate: ogni istanza genera le proprie al boot
describe command('ls /etc/ssh/ssh_host_* 2>/dev/null | wc -l') do
  its('stdout.strip') { should eq '0' }   # da eseguire su istanza lanciata prima di sshd, o su volume montato
end

# IMDSv2 obbligatorio: una GET senza token di sessione deve essere rifiutata (401)
describe command('curl -s -o /dev/null -w "%{http_code}" http://169.254.169.254/latest/meta-data/') do
  its('stdout') { should eq '401' }
end
```

```yaml
# Alternativa leggera: goss.yaml
service:
  amazon-ssm-agent:
    enabled: true
    running: true
port:
  tcp:22:
    listening: true
```

### Integrazione con Terraform

```hcl
# Lookup dell'ultima AMI approvata, filtrata per tag
data "aws_ami" "web" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "tag:managed_by"
    values = ["packer"]
  }
  filter {
    name   = "tag:stage"
    values = ["approved"]
  }
  filter {
    name   = "name"
    values = ["web-golden-*"]
  }
}

resource "aws_launch_template" "web" {
  name_prefix   = "web-"
  image_id      = data.aws_ami.web.id
  instance_type = "t3.medium"

  metadata_options {
    http_tokens = "required"
  }
}

resource "aws_autoscaling_group" "web" {
  min_size            = 2
  max_size            = 6
  vpc_zone_identifier = var.private_subnet_ids

  launch_template {
    id      = aws_launch_template.web.id
    version = aws_launch_template.web.latest_version
  }

  # Rollout automatico quando cambia la AMI
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 90
      instance_warmup        = 120
    }
  }
}
```

**Rollback**: marcare l'AMI difettosa con `stage=revoked` e promuovere la precedente (`stage=approved`); `terraform apply` aggiorna il launch template e l'instance refresh riporta il fleet alla versione buona. In alternativa, pinnare l'AMI ID esplicito in una variabile (più prevedibile, meno automatico).

### HCP Packer: channel e revoca

```hcl
build {
  hcp_packer_registry {
    bucket_name = "web-golden"
    description = "Immagine web hardenizzata"
    bucket_labels = { team = "platform", os = "al2023" }
    build_labels  = { git_sha = var.git_sha }
  }
  sources = ["source.amazon-ebs.web"]
  # ...provisioner...
}
```

```hcl
# Terraform: consuma il channel invece di cercare per tag
data "hcp_packer_artifact" "web" {
  bucket_name  = "web-golden"
  channel_name = "production"
  platform     = "aws"
  region       = "eu-west-1"
}

# image_id = data.hcp_packer_artifact.web.external_identifier
```

Con HCP Packer i **channel** (`dev`, `staging`, `production`) puntano a una *iteration/version*: promuovere = riassegnare il channel. La **revoca** di una versione vulnerabile fa fallire i `terraform plan` che la usano e permette di individuare chi la sta ancora eseguendo.

## Best Practices

- **Base image pinnata e tracciata**: filtra su owner ufficiale, registra l'AMI sorgente nei tag; ricostruisci a cadenza regolare (settimanale) per incorporare le patch OS anche senza modifiche al codice.
- **Un'immagine per ruolo**, composta da layer: `base-hardened` → `web`, `worker`. La base si ricostruisce meno spesso e si ereditano le fix.
- **Zero secret nell'immagine**: configurazione sensibile a runtime via IAM role, SSM Parameter Store, Secrets Manager, Vault.
- **Cifratura e privacy**: `encrypt_boot = true` con KMS CMK; per condividere cross-account usa `ami_users` + condivisione della chiave KMS, non AMI pubbliche.
- **Build in subnet privata dedicata**, con security group minimale e (se possibile) VPC endpoint per i repository.
- **Tag obbligatori**: `git_sha`, `stage`, `managed_by`, `base_ami`, `build_date`; permettono lookup, audit e cleanup.
- **Lifecycle delle AMI**: Data Lifecycle Manager o job schedulato per deregistrare AMI e snapshot vecchi (mantieni le ultime N + quelle in uso).
- **Scan e test come gate**: nessuna AMI diventa `approved` senza scan CVE (Inspector/Trivy) e test InSpec/Goss superati. Vedi [Image Scanning](../../security/supply-chain/image-scanning.md).
- **Provisioner idempotenti e deterministici**: versioni pacchetti pinnate dove possibile; `set -euo pipefail` negli script.
- **`packer fmt -check` e `validate` in ogni PR**; `build` solo su `main`.

!!! tip "Ansible come provisioner"
    Se hai già ruoli Ansible per la configurazione, riusali come provisioner `ansible` con `use_proxy = false` o `ansible-local`: stessa logica in fase di bake e (se serve) di patching in-place. Vedi [Ansible Fondamentali](../ansible/fondamentali.md).

## Troubleshooting

### `Timeout waiting for SSH` / `WinRM not responding`

**Sintomo**: `==> amazon-ebs.web: Waiting for SSH to become available...` poi `Timeout waiting for SSH.`

**Cause**: security group senza ingresso porta 22 dall'host di build; subnet senza IP pubblico (e runner fuori dalla VPC); `ssh_username` errato per la base AMI (`ec2-user`, `ubuntu`, `admin`); istanza che non completa il boot (user-data bloccato); su Windows UserData WinRM mancante.

**Soluzione**:

```hcl
source "amazon-ebs" "web" {
  associate_public_ip_address = true     # oppure ssh_interface = "session_manager" / "private_ip"
  ssh_timeout                 = "15m"
  temporary_security_group_source_cidrs = ["0.0.0.0/0"]  # restringere al CIDR del runner
}
```

Per istanze private usa `ssh_interface = "session_manager"` (richiede SSM agent e instance profile) oppure un runner self-hosted nella VPC. Debug: `PACKER_LOG=1 packer build -debug .`

### `Error waiting for AMI` / `AMI is in failed state`

**Sintomo**: `Error waiting for AMI: ResourceNotReady: exceeded wait attempts` oppure stato `failed` con `Client.InternalError`.

**Cause**: snapshot molto grande che supera il polling di default; chiave KMS senza permessi per il ruolo di build (`kms:CreateGrant`, `kms:GenerateDataKeyWithoutPlaintext`); limite di quota snapshot/AMI.

**Soluzione**:

```bash
export AWS_MAX_ATTEMPTS=240
export AWS_POLL_DELAY_SECONDS=15     # variabili usate dal plugin amazon per il polling
```

Verifica la key policy KMS e le quote (Service Quotas → EC2 → snapshots).

### `VPCIdNotSpecified: No default VPC for this user`

**Causa**: account senza default VPC e `subnet_id`/`vpc_id` non indicati.

**Soluzione**: imposta `subnet_id` (la VPC è dedotta) o `vpc_filter`/`subnet_filter`:

```hcl
subnet_filter {
  filters = { "tag:Purpose" = "packer-build" }
  random  = true
}
```

### `Missing plugin` / `Unsupported block type` dopo `packer init`

**Sintomo**: `Error: Unknown source type "amazon-ebs"` o `The builder/provisioner ... plugin is not installed`.

**Cause**: `packer init` non eseguito; blocco `required_plugins` mancante o con `source` errata; cache plugin non persistita in CI; vincolo di versione incompatibile con la versione di Packer.

**Soluzione**:

```bash
packer init -upgrade .                       # riscarica rispettando i vincoli
packer plugins installed                     # elenca i plugin disponibili
export PACKER_PLUGIN_PATH="$HOME/.config/packer/plugins"
export PACKER_GITHUB_API_TOKEN=<token>       # evita il rate limit di GitHub in CI
```

### Build riuscita ma istanze con chiavi residue o host key duplicate

**Causa**: cleanup incompleto, `authorized_keys` effimera rimasta, `machine-id` o host key duplicati tra istanze.

**Soluzione**: verifica `99-cleanup.sh` come ultimo provisioner, rigenera host key al boot (`ssh-keygen -A` via cloud-init) e testa con InSpec che nessuna chiave Packer sia presente.

### Instance refresh bloccato dopo cambio AMI

**Sintomo**: ASG in stato `InProgress` per ore; health check falliti.

**Cause**: AMI senza agent/servizio che avvia l'applicazione; `instance_warmup` troppo corto; `min_healthy_percentage` troppo alto per un fleet piccolo.

**Soluzione**: `aws autoscaling describe-instance-refreshes --auto-scaling-group-name web`; annulla con `cancel-instance-refresh`, ripristina il launch template precedente e correggi l'immagine.

## Relazioni

??? info "Terraform — Approfondimento"
    Terraform consuma l'AMI prodotta da Packer tramite `data "aws_ami"` (filtro su tag) o `hcp_packer_artifact`, e orchestra launch template e ASG.

    **Approfondimento completo →** [Terraform Fondamentali](../terraform/fondamentali.md) · [Terraform CI/CD](../terraform/ci-cd.md)

??? info "EC2 Auto Scaling — Approfondimento"
    L'instance refresh dell'ASG è il meccanismo di rollout di una nuova golden image con health check e warmup.

    **Approfondimento completo →** [EC2 Auto Scaling](../../cloud/aws/compute/ec2-autoscaling.md)

??? info "Image Scanning — Approfondimento"
    Scansione CVE come gate di promozione dell'immagine (Trivy, Inspector).

    **Approfondimento completo →** [Image Scanning](../../security/supply-chain/image-scanning.md)

??? info "Ansible — Approfondimento"
    Ruoli Ansible riusabili come provisioner Packer per l'hardening e la configurazione.

    **Approfondimento completo →** [Ansible Fondamentali](../ansible/fondamentali.md)

## Riferimenti

- [Packer Documentation](https://developer.hashicorp.com/packer/docs)
- [Amazon EBS builder](https://developer.hashicorp.com/packer/integrations/hashicorp/amazon/latest/components/builder/ebs)
- [HCP Packer](https://developer.hashicorp.com/hcp/docs/packer)
- [Packer GitHub Actions — setup-packer](https://github.com/hashicorp/setup-packer)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks)
- [InSpec](https://docs.chef.io/inspec/) · [Goss](https://github.com/goss-org/goss)
