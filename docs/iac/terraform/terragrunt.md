---
title: "Terragrunt"
slug: terragrunt
category: iac
tags: [terragrunt, terraform, opentofu, iac, dry, orchestration, gruntwork, hcl, stacks]
search_keywords: [terragrunt, terragrunt.hcl, root.hcl, terragrunt run --all, run-all, terragrunt run-all, terragrunt stack, terragrunt.stack.hcl, terragrunt dag graph, dependency block, mock_outputs, find_in_parent_folders, read_terragrunt_config, remote_state, generate provider, DRY terraform, terraform wrapper, orchestrazione multi-modulo, multi-environment terraform, terragrunt opentofu, TG_TF_PATH, terraform_binary, TG_PROVIDER_CACHE, provider cache, terragrunt-cache, .terragrunt-cache, terragrunt_version_constraint, terragrunt filter, --filter, --parallelism, --non-interactive, terragrunt atlantis, gruntwork, unit, stack, catalog, terragrunt backend bootstrap, TG_BACKEND_BOOTSTRAP, cli redesign, --terragrunt-non-interactive]
parent: iac/terraform/_index
related: [iac/terraform/ci-cd, iac/terraform/state-management, iac/terraform/moduli, iac/terraform/opentofu, iac/terraform/fondamentali]
official_docs: https://docs.terragrunt.com/
status: needs-review
last_verified: 2026-10-04
difficulty: advanced
last_updated: 2026-10-04
---

# Terragrunt

## Panoramica

**Terragrunt** (Gruntwork) è un thin wrapper attorno a OpenTofu/Terraform che risolve tre problemi dei repo IaC multi-ambiente: la **duplicazione** di `backend`/`provider` in decine di root module, l'**orchestrazione** di più root module interdipendenti (ordine di apply, output passati tra stack) e il **riuso** di layout infrastrutturali interi (dev/staging/prod con le stesse unit). Non sostituisce Terraform: genera la configurazione, risolve le dipendenze e invoca il binary `tofu`/`terraform` unit per unit.

Il modello mentale: ogni directory con un `terragrunt.hcl` è una **unit** (un root module + il suo state); una collezione di unit è uno **stack** (implicito = albero di directory, esplicito = file `terragrunt.stack.hcl`).

!!! note "Versioni di riferimento"
    Documentazione allineata alla **CLI redesign** (comando `run`, flag senza prefisso `--terragrunt-`, default che non inoltra più comandi sconosciuti a OpenTofu dalla v0.88). Le feature `stack` e `--filter` evolvono rapidamente: verificare le release notes su <https://docs.terragrunt.com/> prima di copiare i comandi in CI.

### Quando NON serve

| Situazione | Alternativa più semplice |
|---|---|
| Pochi ambienti (2-3) con un solo root module | `-var-file` per ambiente + backend config parametrizzata (`-backend-config`) |
| Differenze tra ambienti solo di valori | Terraform **workspaces** (con i limiti descritti in [State Management](state-management.md)) o directory per ambiente con moduli condivisi |
| Orchestrazione multi-stack gestibile dalla CI | Pipeline con `needs` / Atlantis `depends_on` ([CI/CD](ci-cd.md)) |
| Team che vuole un solo tool | Terraform Stacks (HCP) o OpenTofu puri |

Terragrunt paga quando i root module sono **molti** (decine), si ripete lo stesso scheletro per account/regione/ambiente e serve un grafo di dipendenze eseguibile localmente e in CI.

!!! warning "Costo di adozione"
    Terragrunt aggiunge un livello di indirezione (cache, generazione file, un DSL in più). Debugging e onboarding diventano più difficili: adottarlo solo se la duplicazione è un dolore reale, non per "pulizia" preventiva.

## Concetti Chiave

| Concetto | Descrizione |
|---|---|
| **Unit** | Directory con un `terragrunt.hcl`: un root module + uno state |
| **Stack** | Insieme di unit eseguite insieme (implicito da directory o esplicito da `terragrunt.stack.hcl`) |
| **`root.hcl`** | File radice con configurazione comune (`remote_state`, `generate`); convenzione moderna al posto di un `terragrunt.hcl` radice |
| **`include`** | Eredita configurazione da un file padre |
| **`dependency`** | Legge gli output di un'altra unit e definisce l'ordine di esecuzione |
| **`terraform { source }`** | Punta al modulo (locale, git con `?ref=`, registry) che l'unit istanzia |
| **`inputs`** | Mappa tradotta in `TF_VAR_*` per il modulo |
| **`.terragrunt-cache`** | Directory per unit con la copia del modulo scaricato + file generati |

!!! note "Perché `root.hcl` e non `terragrunt.hcl` radice"
    Un `terragrunt.hcl` nella radice viene scoperto come unit dai comandi `--all`. Chiamare il file radice `root.hcl` evita che venga trattato come unit; si include con `include "root" { path = find_in_parent_folders("root.hcl") }`.

## Architettura / Come Funziona

Esecuzione di `terragrunt run --all apply`:

1. **Discovery**: cerca ricorsivamente le unit (`terragrunt.hcl`) sotto la working dir.
2. **Parsing**: risolve `include`, `locals`, `dependency`, funzioni (`find_in_parent_folders`, `read_terragrunt_config`, `get_env`...).
3. **DAG**: costruisce il grafo dalle `dependency`/`dependencies`; le unit senza dipendenze vanno per prime, in parallelo fino a `--parallelism`.
4. **Per unit**: scarica il `source` in `.terragrunt-cache/`, scrive i file `generate` (provider, backend), esegue `init` e il comando richiesto con i `TF_VAR_*` derivati da `inputs`.
5. Per `destroy` l'ordine è invertito.

```text
live/
├── root.hcl                  # remote_state + generate "provider" comuni
├── _envcommon/               # (opzionale) config condivisa per componente
│   └── vpc.hcl
├── prod/
│   ├── account.hcl           # locals: account_id, profile
│   ├── eu-west-1/
│   │   ├── region.hcl        # locals: aws_region
│   │   ├── vpc/terragrunt.hcl
│   │   └── eks/terragrunt.hcl   # dependency -> ../vpc
└── dev/
    └── ...
```

??? info "State management — Approfondimento"
    Terragrunt crea una chiave di state per unit tramite `path_relative_to_include()`, evitando di scrivere un backend a mano in ogni root module.

    **Approfondimento completo →** [State Management](state-management.md)

## Configurazione & Pratica

### 1. `root.hcl`: backend e provider DRY

```hcl
# live/root.hcl
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))

  account_id = local.account_vars.locals.account_id
  aws_region = local.region_vars.locals.aws_region
}

# Versioni minime: evita il drift tra sviluppatori e CI
terragrunt_version_constraint = ">= 0.88, < 1.0"
terraform_version_constraint  = ">= 1.10"   # richiesto da use_lockfile

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "acme-tfstate-${local.account_id}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    use_lockfile   = true   # lock nativo S3 (Terraform >= 1.10 / OpenTofu >= 1.10)
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "aws" {
      region              = "${local.aws_region}"
      allowed_account_ids = ["${local.account_id}"]
    }
  EOF
}

inputs = {
  environment = local.account_vars.locals.environment
}
```

```hcl
# live/prod/account.hcl
locals {
  account_id  = "111111111111"
  environment = "prod"
}

# live/prod/eu-west-1/region.hcl
locals {
  aws_region = "eu-west-1"
}
```

!!! warning "Bootstrap del backend"
    Con la CLI redesign il provisioning automatico del bucket/tabella di backend non è più implicito: usare `terragrunt backend bootstrap` oppure `--backend-bootstrap` / `TG_BACKEND_BOOTSTRAP=true`. In caso contrario `init` fallisce con "bucket does not exist".

### 2. Unit che istanzia un modulo

```hcl
# live/prod/eu-west-1/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  # Pin esplicito del modulo: mai branch mobili
  source = "git::git@github.com:acme/tf-modules.git//vpc?ref=v3.2.0"
}

inputs = {
  name       = "prod-vpc"
  cidr_block = "10.10.0.0/16"
  azs        = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}
```

Per condividere la parte comune tra ambienti, usare un `include` con `expose = true` e un file in `_envcommon/`:

```hcl
# live/prod/eu-west-1/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path   = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/vpc.hcl"
  expose = true
}

# Override locale: gli inputs della unit hanno precedenza su quelli ereditati
# (merge_strategy dell'include: "shallow" di default; alternative "deep", "no_merge")
inputs = {
  cidr_block = "10.10.0.0/16"
}
```

### 3. Dipendenze e grafo

```hcl
# live/prod/eu-west-1/eks/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "git::git@github.com:acme/tf-modules.git//eks?ref=v5.0.1"
}

dependency "vpc" {
  config_path = "../vpc"

  # Permette plan/validate quando la vpc non è ancora applicata (stato vuoto)
  mock_outputs = {
    vpc_id          = "vpc-00000000"
    private_subnets = ["subnet-00000000", "subnet-11111111"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
  mock_outputs_merge_strategy_with_state  = "shallow"
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnets
}
```

- `dependency` = lettura output **+** ordinamento. `dependencies { paths = [...] }` = solo ordinamento (nessun output).
- Limitare `mock_outputs_allowed_terraform_commands` a `plan`/`validate`: un `apply` con mock scriverebbe ID finti nelle risorse.

```bash
# Visualizzare il DAG (formato DOT, renderizzabile con graphviz)
terragrunt dag graph | dot -Tsvg > dag.svg

# Elenco unit con le dipendenze, in JSON
terragrunt find --dag --json
```

### 4. CLI (redesign)

```bash
# Singola unit (comando esplicito: i comandi sconosciuti non sono più inoltrati)
cd live/prod/eu-west-1/vpc
terragrunt plan
terragrunt run -- workspace ls        # passthrough esplicito a tofu/terraform

# Tutte le unit sotto la directory corrente, rispettando il DAG
cd live/prod
terragrunt run --all plan
terragrunt run --all apply --non-interactive --parallelism 4

# Filtrare le unit (query sintassi --filter; verificare i dettagli nella versione in uso)
# <!-- REVIEW: verificare in quale versione di Terragrunt --filter è stabile (la CI sotto pinna 0.88.0) e la sintassi 'eks...' -->
# <!-- REVIEW: verificare che 'dag graph', 'find --dag' e '--backend-bootstrap' esistano in 0.88 e che il no-forwarding parta da 0.88 -->

terragrunt run --all --filter './eu-west-1/**' plan
terragrunt run --all --filter 'eks...' plan     # eks + dipendenze (sintassi grafo)
```

**Migrazione dai flag legacy** (i vecchi funzionano ancora con warning di deprecazione, ma verranno rimossi):

| Legacy | Nuovo |
|---|---|
| `terragrunt run-all plan` | `terragrunt run --all plan` |
| `--terragrunt-non-interactive` | `--non-interactive` |
| `--terragrunt-working-dir` | `--working-dir` |
| `--terragrunt-parallelism N` | `--parallelism N` |
| `--terragrunt-modules-that-include X` | `--units-that-include X` |
| `--terragrunt-debug` | `--inputs-debug` |
| `terragrunt graph-dependencies` | `terragrunt dag graph` |
| `terragrunt hclfmt` | `terragrunt hcl fmt` |
| `terragrunt validate-inputs` | `terragrunt hcl validate --inputs` |
| `TERRAGRUNT_*` (env) | `TG_*` (es. `TG_NON_INTERACTIVE`) |

!!! tip "Migrazione graduale"
    Cercare i residui con `grep -rE 'run-all|--terragrunt-|TERRAGRUNT_' .github/ scripts/ Makefile` e sostituire in blocco. In CI le variabili `TG_*` sono preferibili ai flag: una sola riga di `env:`.

### 5. Stacks espliciti

Uno stack esplicito descrive un layout riusabile e lo **genera** in `.terragrunt-stack/`.

```hcl
# live/prod/terragrunt.stack.hcl
locals {
  version = "v1.4.0"
}

unit "vpc" {
  source = "git::git@github.com:acme/catalog.git//units/vpc?ref=${local.version}"
  path   = "vpc"
  values = {
    cidr = "10.10.0.0/16"
  }
}

unit "eks" {
  source = "git::git@github.com:acme/catalog.git//units/eks?ref=${local.version}"
  path   = "eks"
  values = {
    vpc_path = "../vpc"
  }
}

# Stack annidato riusabile
stack "observability" {
  source = "git::git@github.com:acme/catalog.git//stacks/observability?ref=${local.version}"
  path   = "observability"
}
```

```hcl
# catalog: units/eks/terragrunt.hcl — legge "values" invece di hardcodare
dependency "vpc" {
  config_path = values.vpc_path
  mock_outputs = { vpc_id = "vpc-00000000" }
}

inputs = {
  vpc_id = dependency.vpc.outputs.vpc_id
}
```

```bash
terragrunt stack generate            # crea .terragrunt-stack/ con le unit
terragrunt stack run plan            # genera + esegue sul DAG
terragrunt stack output              # output aggregati
terragrunt stack clean               # elimina .terragrunt-stack/
```

!!! note "Git"
    Aggiungere `.terragrunt-stack/` e `.terragrunt-cache/` al `.gitignore`: sono artefatti rigenerabili.

### 6. OpenTofu, CI e cache

```bash
# Usare OpenTofu al posto di Terraform
export TG_TF_PATH=tofu          # equivale a terraform_binary = "tofu" in HCL

# Cache condivisa dei provider: evita N download per N unit
export TG_PROVIDER_CACHE=1
terragrunt run --all plan
```

```hcl
# root.hcl — equivalente dichiarativo
terraform_binary = "tofu"
```

```yaml
# .github/workflows/plan.yml (estratto)
jobs:
  plan:
    runs-on: ubuntu-latest
    permissions: { id-token: write, contents: read }
    env:
      TG_NON_INTERACTIVE: "true"
      TG_PROVIDER_CACHE: "1"
      TG_TF_PATH: tofu
    steps:
      - uses: actions/checkout@v4
      - uses: opentofu/setup-opentofu@v1
        with: { tofu_version: "1.10.x" }
      - uses: gruntwork-io/terragrunt-action@v3
        with:
          tg_version: "0.88.0"
          tofu_version: "1.10.x"
          tg_dir: live/prod
          tg_command: "run --all plan"
```

**Atlantis**: usare `atlantis.yaml` con `workflows` che invocano `terragrunt plan`/`apply` per directory, oppure un generatore (`terragrunt` `find`/`list`) per produrre i `projects` con le `depends_on` corrette. Vedi [CI/CD](ci-cd.md) per il flusso PR-based.

## Best Practices

- **Pin ovunque**: `terragrunt_version_constraint`, `terraform_version_constraint`, `?ref=` sui `source`. Versionare il binary in `.tool-versions`/mise.
- **Una unit = un blast radius ragionevole**: separare rete, cluster, database; evitare unit "monolitiche".
- **`mock_outputs` solo per plan/validate**, mai per apply.
- **Config gerarchica** (`account.hcl` → `region.hcl` → `env.hcl`) letta con `read_terragrunt_config`: niente `if` per ambiente nei moduli.
- **Moduli senza conoscenza di Terragrunt**: restano usabili da Terraform/OpenTofu puri ([Moduli](moduli.md)).
- **`run --all apply` in CI solo con approvazione**: preferire `plan` su PR e `apply` post-merge su ambienti protetti.
- **Limitare `--parallelism`** (es. 4-8) per non saturare le API del cloud e i lock.
- **Evitare dipendenze circolari**: il DAG deve essere aciclico; estrarre la parte comune in una terza unit.
- **Anti-pattern**: `terragrunt.hcl` radice incluso come unit; `dependency` verso unit in altri stack cross-account senza permessi di lettura dello state; logica complessa in `locals` (diventa illeggibile).

## Troubleshooting

### `dependency` senza output su stato vuoto

**Sintomo**: `Error: There is no variable named "dependency"` oppure `Module ../vpc has finished successfully, but no outputs`; `plan --all` fallisce al primo giro.

**Causa**: la unit dipendente non è mai stata applicata, quindi non ha output.

**Soluzione**: definire `mock_outputs` con le chiavi usate e `mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]`. Per l'apply, eseguire `terragrunt run --all apply` (il DAG applica prima la dipendenza e poi legge gli output reali).

### Lock contention in parallelo

**Sintomo**: `Error acquiring the state lock` / `ConditionalCheckFailedException` su più unit.

**Causa**: unit diverse con la **stessa chiave di state** (manca `path_relative_to_include()`), oppure un precedente run interrotto ha lasciato il lock.

**Soluzione**:

```bash
# Verificare che le key siano uniche (una riga per unit, nessun duplicato)
grep -rh --include=backend.tf '  key ' .terragrunt-cache live | sort | uniq -d
# Rilascio manuale (solo dopo aver verificato che nessun run sia attivo)
terragrunt run -- force-unlock <LOCK_ID>
# Ridurre il parallelismo
terragrunt run --all apply --parallelism 2
```

### `.terragrunt-cache` obsoleta

**Sintomo**: modifiche al modulo `source` non applicate; errori `Module not installed` o provider lock incoerente.

**Causa**: cache locale con versione vecchia del modulo o `.terraform.lock.hcl` non allineato.

**Soluzione**:

```bash
# Linux/macOS
find . -type d -name ".terragrunt-cache" -prune -exec rm -rf {} +
# Windows PowerShell
Get-ChildItem -Recurse -Directory -Filter .terragrunt-cache | Remove-Item -Recurse -Force
terragrunt run --all -- init -upgrade
```

### Drift tra versioni di Terragrunt

**Sintomo**: lo stesso repo funziona in locale ma fallisce in CI con `unknown flag`, `unsupported block` o comando non riconosciuto (`terragrunt workspace ls` non inoltrato).

**Causa**: versioni diverse del binary dopo la CLI redesign (v0.88: niente forwarding implicito).

**Soluzione**: impostare `terragrunt_version_constraint` in `root.hcl`, fissare la versione in CI (`tg_version`) e nel tool manager, usare `terragrunt run -- <cmd>` per i passthrough.

### `run-all` / `--terragrunt-*` deprecati

**Sintomo**: warning `The command run-all is deprecated` o flag ignorati.

**Causa**: sintassi pre-redesign.

**Soluzione**: usare la tabella di migrazione sopra; verificare con `terragrunt --help` e `terragrunt run --help` la sintassi esatta della versione in uso.

## Relazioni

??? info "CI/CD per Terraform — Approfondimento"
    La sezione 7 di CI/CD mostra l'uso base di `run-all` in pipeline; questo file ne è l'approfondimento (nota: usa ancora la sintassi legacy).

    **Approfondimento completo →** [Terraform CI/CD](ci-cd.md)

??? info "OpenTofu — Approfondimento"
    Terragrunt supporta OpenTofu via `terraform_binary = "tofu"` o `TG_TF_PATH`.

    **Approfondimento completo →** [OpenTofu](opentofu.md)

??? info "Moduli — Approfondimento"
    Le unit istanziano moduli versionati; la qualità dei moduli determina quanto resta nel layer Terragrunt.

    **Approfondimento completo →** [Moduli Terraform](moduli.md)

## Riferimenti

- [Terragrunt — Documentazione ufficiale](https://docs.terragrunt.com/)
- [Terragrunt — CLI Redesign migration](https://docs.terragrunt.com/migrate/cli-redesign/)
- [Terragrunt — Stacks](https://docs.terragrunt.com/features/stacks/)
- [Gruntwork — terragrunt-infrastructure-live-example](https://github.com/gruntwork-io/terragrunt-infrastructure-live-example)
- [OpenTofu — Documentazione](https://opentofu.org/docs/)
