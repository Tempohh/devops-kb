---
title: "Pulumi — Stacks e Gestione Multi-Ambiente"
slug: stacks-ambienti
category: iac
tags: [pulumi, stacks, multi-ambiente, ci-cd, secrets, state, iac, devops]
search_keywords: [pulumi stacks, pulumi multi environment, pulumi multi-ambiente, stack management, pulumi config, pulumi secrets, pulumi state, pulumi backend, pulumi cloud, pulumi s3 backend, self-managed state, stack reference, stack output, pulumi ci cd, github actions pulumi, pulumi automation api, pulumi deployments, pulumi kms, aws kms secrets, azure key vault pulumi, hashicorp vault pulumi, pulumi login, stack locking, concurrent deploy, pulumi preview, pulumi up, pulumi destroy, environment promotion, infra promotion]
parent: iac/pulumi/_index
related: [iac/pulumi/fondamentali, iac/terraform/state-management, iac/terraform/fondamentali, ci-cd/pipeline-patterns]
official_docs: https://www.pulumi.com/docs/concepts/stack/
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# Pulumi — Stacks e Gestione Multi-Ambiente

## Panoramica

In Pulumi, uno **Stack** è un'istanza isolata di un progetto: ha il proprio state, la propria configurazione e i propri secrets. Il pattern standard è avere uno stack per ambiente (`dev`, `staging`, `prod`), ma gli stack possono anche rappresentare regioni, tenant, o combinazioni di questi. Questa guida copre il workflow operativo reale per team che gestiscono più ambienti in modo sicuro e riproducibile.

**Problema che risolve:** un singolo repository IaC deve deployare infrastruttura identica (o quasi) in ambienti diversi, con configurazioni diverse (istanze più piccole in dev, segreti diversi, regioni diverse) senza duplicare codice e senza rischiare che un deploy in dev tocchi prod.

**Prerequisiti:** conoscere i fondamentali di Pulumi (Project, Resources, Outputs, Config). Vedere [Pulumi — Fondamentali](fondamentali.md).

---

## Concetti Chiave

### Stack

```
Progetto: my-infra
├── Stack: dev      → state: dev.state,    config: Pulumi.dev.yaml
├── Stack: staging  → state: staging.state, config: Pulumi.staging.yaml
└── Stack: prod     → state: prod.state,   config: Pulumi.prod.yaml
```

Ogni stack è **completamente isolato**: un `pulumi up` su `dev` non legge né modifica lo state di `prod`. Il codice del programma è identico — cambia solo la configurazione che il programma riceve a runtime.

### Stack Name e Organizzazione

Il nome completo di uno stack in Pulumi Cloud è `organization/project/stack`. Per backend self-managed il nome è semplicemente `stack` (senza organizzazione).

```bash
# Pulumi Cloud
pulumi stack init myorg/my-infra/dev
pulumi stack init myorg/my-infra/staging
pulumi stack init myorg/my-infra/prod

# Self-managed (S3, GCS, etc.)
pulumi stack init dev
pulumi stack init prod
```

### Stack Reference

Uno Stack Reference permette a uno stack di leggere gli output di un altro stack. Il pattern classico è lo stack `networking` che esporta il VPC ID, e lo stack `app` che lo consuma.

```typescript
// Stack networking/prod esporta:
export const vpcId = vpc.id;
export const privateSubnetIds = privateSubnets.ids;
export const publicSubnetIds = publicSubnets.ids;
```

```typescript
// Stack app/prod consuma:
const networkStack = new pulumi.StackReference("myorg/networking/prod");

// getOutput restituisce Output<any> (asincrono)
const vpcId = networkStack.getOutput("vpcId");

// requireOutput lancia errore se l'output non esiste (preferito in prod)
const subnetIds = networkStack.requireOutput("privateSubnetIds");

const cluster = new aws.eks.Cluster("app-cluster", {
    vpcConfig: {
        subnetIds: subnetIds.apply(ids => ids as string[]),
        vpcId: vpcId.apply(id => id as string),
    },
});
```

!!! warning "Stack Reference e ambienti"
    Un app stack dev dovrebbe sempre puntare alla Stack Reference del networking stack dev (`myorg/networking/dev`), mai a `prod`. Parametrizzare il nome della reference con `pulumi.getStack()` per evitare hardcoding.

```typescript
const envName = pulumi.getStack(); // "dev", "staging", "prod"
const networkStack = new pulumi.StackReference(`myorg/networking/${envName}`);
```

---

## Configurazione per Stack

### File di Configurazione

Pulumi salva la configurazione di ogni stack in un file `Pulumi.<stack>.yaml`. Questi file vanno **committati in git** (senza segreti in chiaro).

```bash
# Imposta configurazione non-secret (salvata in Pulumi.prod.yaml)
pulumi config set aws:region eu-west-1 --stack prod
pulumi config set instanceType t3.xlarge --stack prod
pulumi config set replicaCount 3 --stack prod
pulumi config set enableDeletion false --stack prod

# Dev: istanze più piccole, deletion consentita
pulumi config set aws:region eu-west-1 --stack dev
pulumi config set instanceType t3.micro --stack dev
pulumi config set replicaCount 1 --stack dev
pulumi config set enableDeletion true --stack dev
```

```yaml
# Pulumi.prod.yaml (committato in git — no segreti in chiaro)
config:
  aws:region: eu-west-1
  my-infra:instanceType: t3.xlarge
  my-infra:replicaCount: "3"
  my-infra:enableDeletion: "false"
  my-infra:dbPassword:
    secure: AAABAGnT3w8r...  # cifrato con la chiave del backend
```

### Lettura della Config nel Codice

```python
import pulumi

config = pulumi.Config()

# require() lancia eccezione se la chiave non c'è — preferito per valori obbligatori
instance_type = config.require("instanceType")
replica_count = config.require_int("replicaCount")
enable_deletion = config.require_bool("enableDeletion")

# get() restituisce None se mancante — per valori opzionali con default
log_level = config.get("logLevel") or "INFO"
```

```typescript
import * as pulumi from "@pulumi/pulumi";

const config = new pulumi.Config();

const instanceType = config.require("instanceType");
const replicaCount = config.requireNumber("replicaCount");
const enableDeletion = config.requireBoolean("enableDeletion");

// Object config (utile per configurazioni strutturate)
interface DbConfig { host: string; port: number; name: string; }
const dbConfig = config.requireObject<DbConfig>("db");
```

### Segreti

I segreti sono cifrati nel file di configurazione e nello state. La chiave di cifratura dipende dal secrets provider scelto.

```bash
# Imposta un segreto (cifrato a riposo nel backend)
pulumi config set --secret dbPassword "s3cr3t-prod-2024" --stack prod
pulumi config set --secret apiToken "tok_live_abc123" --stack prod

# Visualizza la configurazione (i segreti appaiono come [secret])
pulumi config --stack prod
```

```python
config = pulumi.Config()

# require_secret restituisce Output[str] — mai una stringa in chiaro
db_password = config.require_secret("dbPassword")

# Usare in una risorsa che accetta Output[str]
db_instance = aws.rds.Instance("db",
    password=db_password,
    ...
)
```

!!! tip "Segreti come Output[T]"
    `require_secret()` restituisce sempre un `Output[T]`, anche se il valore originale è in chiaro. Questo evita che il segreto venga accidentalmente loggato o serializzato. Pulumi automaticamente cifra tutti i valori che derivano da un Output segreto nello state.

---

## Secrets Providers

Il provider di segreti determina con quale chiave vengono cifrati i segreti nella configurazione e nello state.

| Provider | Comando | Use Case |
|---|---|---|
| **Pulumi Cloud** (default) | `pulumi stack init mystack` | Team che usano Pulumi Cloud |
| **AWS KMS** | `--secrets-provider="awskms://alias/my-key"` | AWS-native, audit trail CloudTrail |
| **Azure Key Vault** | `--secrets-provider="azurekeyvault://vault/key"` | Azure-native |
| **GCP KMS** | `--secrets-provider="gcpkms://projects/.../keys/..."` | GCP-native |
| **HashiCorp Vault** | `--secrets-provider="hashivault://my-key"` | Infrastruttura on-prem |
| **Passphrase** | `--secrets-provider=passphrase` | CI senza cloud KMS (meno sicuro) |

```bash
# Creare stack con AWS KMS
pulumi stack init prod \
  --secrets-provider="awskms://alias/pulumi-secrets-prod"

# Creare stack con Azure Key Vault
pulumi stack init prod \
  --secrets-provider="azurekeyvault://myvault.vault.azure.net/keys/pulumi-key"

# Cambiare secrets provider su stack esistente
pulumi stack change-secrets-provider \
  "awskms://alias/pulumi-secrets-prod" \
  --stack prod
```

!!! warning "Rotazione dei segreti KMS"
    Se si ruota la chiave KMS, i segreti cifrati con la vecchia chiave diventano illeggibili. Eseguire `pulumi config refresh` dopo la rotazione per ricifrare con la nuova chiave, oppure usare KMS Key Rotation automatica (che mantiene la decifratura delle versioni precedenti).

---

## State Management

### Pulumi Cloud (Default)

Pulumi Cloud offre storage del state, history dei deploy, diff visivi, concurrency locking, e access control per team.

```bash
# Login a Pulumi Cloud (richiede account su app.pulumi.com)
pulumi login

# Operazioni normali — state gestito automaticamente
pulumi up --stack prod
```

**Funzionalità chiave:**
- Locking automatico (impedisce deploy concorrenti sullo stesso stack)
- History completa di ogni update con diff delle risorse
- Console web con visualizzazione grafica dello state
- Webhook per notifiche su Slack, GitHub, etc.
- Team access control (chi può fare `up` vs solo `preview`)

### Self-Managed: S3 + Locking

```bash
# Login a backend S3 (equivalente a Terraform S3 backend)
pulumi login s3://my-pulumi-state-bucket/prefix

# Con regione esplicita
PULUMI_BACKEND_URL=s3://my-pulumi-state-bucket \
AWS_DEFAULT_REGION=eu-west-1 \
pulumi stack init prod
```

```bash
# Terraform di bootstrap per creare il bucket S3
# (ironico ma comune: usare Terraform per bootstrappare Pulumi)
resource "aws_s3_bucket" "pulumi_state" {
  bucket = "my-pulumi-state-${var.account_id}"
}

resource "aws_s3_bucket_versioning" "pulumi_state" {
  bucket = aws_s3_bucket.pulumi_state.id
  versioning_configuration { status = "Enabled" }
}
```

!!! warning "Locking con S3 self-managed"
    Il backend S3 di Pulumi **non ha locking nativo** a differenza di Terraform (che usa DynamoDB). Per ambienti di team, usare Pulumi Cloud oppure implementare lock esterni nel CI/CD (serializzare i job di deploy).

### Altri Backend Self-Managed

```bash
# Azure Blob Storage
pulumi login azblob://my-pulumi-state-container

# Google Cloud Storage
pulumi login gs://my-pulumi-state-bucket

# Filesystem locale (solo sviluppo)
pulumi login file:///path/to/state
```

### Operazioni di State

```bash
# Esportare lo state corrente (backup o migrazione)
pulumi stack export --stack prod > prod-state-backup.json

# Importare uno state (ripristino o migrazione backend)
pulumi stack import --stack prod < prod-state-backup.json

# Listare le risorse nello state
pulumi stack --show-ids --stack prod

# Rimuovere una risorsa dallo state senza distruggerla
pulumi state delete "urn:pulumi:prod::my-infra::aws:s3/bucket:Bucket::my-bucket" --stack prod

# Rinominare una risorsa nello state (operazione delicata)
pulumi state rename "old-urn" "new-urn" --stack prod
```

---

## CI/CD Integration

### GitHub Actions — Preview su PR

```yaml
# .github/workflows/pulumi-preview.yaml
name: Pulumi Preview

on:
  pull_request:
    branches: [main]

jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Pulumi Preview
        uses: pulumi/actions@v5
        with:
          command: preview
          stack-name: myorg/my-infra/prod
          comment-on-pr: true          # commenta il diff sul PR
          comment-on-summary: true     # summary nel job
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### GitHub Actions — Deploy su Merge

```yaml
# .github/workflows/pulumi-deploy.yaml
name: Pulumi Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-dev:
    runs-on: ubuntu-latest
    environment: dev        # GitHub Environment con approvazione opzionale
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - uses: pulumi/actions@v5
        with:
          command: up
          stack-name: myorg/my-infra/dev
          upsert: true               # crea lo stack se non esiste
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
          AWS_ACCESS_KEY_ID: ${{ secrets.DEV_AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.DEV_AWS_SECRET_ACCESS_KEY }}

  deploy-prod:
    needs: deploy-dev
    runs-on: ubuntu-latest
    environment: production    # richiede approvazione manuale
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - uses: pulumi/actions@v5
        with:
          command: up
          stack-name: myorg/my-infra/prod
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
          AWS_ACCESS_KEY_ID: ${{ secrets.PROD_AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.PROD_AWS_SECRET_ACCESS_KEY }}
```

### Self-Managed Backend in CI

```yaml
# Con backend S3 invece di Pulumi Cloud
- uses: pulumi/actions@v5
  with:
    command: up
    stack-name: prod
    cloud-url: s3://my-pulumi-state-bucket
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    # Nota: nessun PULUMI_ACCESS_TOKEN necessario con S3 backend
```

!!! tip "Pulumi Deployments (SaaS)"
    Pulumi Cloud offre **Pulumi Deployments**: trigger da Git, audit log, rollback con un click, e OIDC per credenziali temporanee senza segreti statici. Alternativa gestita ai workflow GitHub Actions custom.

---

## Automation API

L'Automation API permette di usare Pulumi programmaticamente senza CLI. Utile per provisioning self-service, test di infrastruttura (create → test → destroy), e tool interni.

```python
import pulumi
from pulumi.automation import LocalWorkspace, UpOptions, Stack

def pulumi_program():
    """Il programma Pulumi normale."""
    import pulumi_aws as aws
    bucket = aws.s3.Bucket("test-bucket", force_destroy=True)
    pulumi.export("bucket_name", bucket.id)

# Crea o seleziona uno stack
stack = LocalWorkspace.create_or_select_stack(
    stack_name="dev",
    project_name="myinfra",
    program=pulumi_program,
    work_dir=".",           # usa Pulumi.yaml nella directory corrente
)

# Imposta configurazione programmaticamente
stack.set_config("aws:region", ConfigValue(value="eu-west-1"))

# Esegui l'update (equivale a pulumi up)
result = stack.up(on_output=print)
print(f"Outputs: {result.outputs}")

# Teardown (per ambienti temporanei di test)
stack.destroy(on_output=print)
stack.workspace.remove_stack("dev")
```

```go
// Go — Automation API per CLI tool interno
package main

import (
    "context"
    "fmt"
    "github.com/pulumi/pulumi/sdk/v3/go/auto"
)

func main() {
    ctx := context.Background()
    
    stackName := auto.FullyQualifiedStackName("myorg", "myproject", "dev")
    
    stack, err := auto.UpsertStackLocalSource(ctx, stackName, "./infra")
    if err != nil {
        panic(err)
    }
    
    result, err := stack.Up(ctx, auto.WithOnOutput(func(msg string) {
        fmt.Print(msg)
    }))
    if err != nil {
        panic(err)
    }
    
    fmt.Printf("Update succeeded: %s\n", result.Summary.Message)
}
```

**Use case tipici:**

| Use Case | Descrizione |
|---|---|
| **Provisioning self-service** | API interna che crea ambienti su richiesta degli sviluppatori |
| **Testing IaC** | Test di integrazione: crea infra → esegui test → distruggi |
| **Multi-tenant SaaS** | Crea uno stack per ogni cliente con la sua configurazione |
| **GitOps controller** | Controller che reconcilia lo state Kubernetes con l'infra Pulumi |

---

## Confronto con Terraform per Team

| Aspetto | Pulumi | Terraform |
|---|---|---|
| **Linguaggio** | Python, TS, Go, C# (linguaggi reali) | HCL (DSL dichiarativo) |
| **Loop / Condizioni** | Nativi del linguaggio | `count`, `for_each`, `dynamic` block |
| **Type safety** | Completa (compile-time) | Limitata (runtime) |
| **Testing** | Unit test standard del linguaggio | `terraform test` (recente) |
| **Moduli riusabili** | Librerie npm/PyPI/Go modules | Terraform Registry |
| **State management** | Pulumi Cloud o self-managed | Terraform Cloud o self-managed |
| **Ecosistema provider** | Buono (usa Terraform provider sotto) | Eccellente (Registry più maturo) |
| **Curva di apprendimento** | Bassa per developer, alta per ops | Moderata (HCL è semplice) |
| **Multi-ambiente** | Stack nativi per ambiente | Workspace o directory separate |

**Migrazione da Terraform:**

```bash
# Converte HCL Terraform in codice Pulumi (Python, TypeScript, etc.)
pulumi convert --from terraform --language python --out ./pulumi-infra

# Import di risorse Terraform esistenti in Pulumi
pulumi import aws:s3/bucket:Bucket my-bucket my-existing-bucket
```

!!! tip "Quando scegliere Pulumi vs Terraform"
    Scegli **Pulumi** se il team ha background da developer e vuole unit test, astrazioni riusabili come librerie, o logica condizionale complessa. Scegli **Terraform** se il team è già esperto HCL, il Terraform Registry copre i provider necessari, o usi Terraform Cloud/Enterprise per governance centralizzata. Entrambi sono production-ready — la scelta è culturale più che tecnica.

---

## Best Practices

!!! tip "Struttura consigliata per multi-repo o mono-repo"
    **Mono-repo con directory separate per stack layer:**
    ```
    infra/
    ├── networking/     # VPC, subnet, peering
    │   ├── Pulumi.yaml
    │   ├── Pulumi.dev.yaml
    │   └── Pulumi.prod.yaml
    ├── platform/       # EKS, RDS, cache
    │   ├── Pulumi.yaml
    │   ├── Pulumi.dev.yaml
    │   └── Pulumi.prod.yaml
    └── apps/           # Deployment applicazioni
        └── ...
    ```
    Ogni layer ha il proprio stato — il networking non viene ridployato quando cambiano le app.

**Pratiche operative:**

- **Mai fare `pulumi up` su prod senza preview approvato.** Sempre usare `pulumi preview` prima di `up` in produzione.
- **Proteggere lo stack prod:** in Pulumi Cloud, usare i permessi di team per limitare chi può fare `up` su prod.
- **Config per ambiente in git:** i file `Pulumi.<stack>.yaml` vanno committati — rendono riproducibile il deploy su qualsiasi macchina/CI.
- **Segreti mai in chiaro:** usare sempre `--secret` per valori sensibili. Verificare con `pulumi config` che i valori appaiano come `[secret]`.
- **Tagging sistematico:** aggiungere tag `Environment` e `ManagedBy: pulumi` a tutte le risorse per identificarle nel cloud.

```python
# Pattern: tags comuni derivati dallo stack name
import pulumi

env = pulumi.get_stack()
project = pulumi.get_project()

common_tags = {
    "Environment": env,
    "ManagedBy": "pulumi",
    "Project": project,
}

# Usare in ogni risorsa
bucket = aws.s3.Bucket("bucket", tags=common_tags)
```

- **Stack locking CI:** serializzare i job di deploy in CI per evitare deploy concorrenti sullo stesso stack (Pulumi Cloud fa locking automatico; con self-managed S3 usare job `needs:` in GitHub Actions).
- **Refresh periodico:** eseguire `pulumi refresh --stack prod` periodicamente per rilevare drift (modifiche manuali fuori da Pulumi).

---

## Troubleshooting

### Stack bloccato (lock non rilasciato)

**Sintomo:** `error: the stack is currently locked by another update` anche dopo che il deploy precedente è terminato.

**Causa:** Un deploy in CI è stato killato senza rilasciare il lock, o un errore di rete ha impedito il rilascio.

**Soluzione:**
```bash
# Forzare il rilascio del lock (usare con cautela — assicurarsi che non ci siano deploy attivi)
pulumi cancel --stack prod

# Verificare che non ci siano update in corso prima
pulumi stack history --stack prod | head -5
```

---

### Segreto illeggibile dopo cambio KMS key

**Sintomo:** `error: failed to decrypt secret: ...` durante `pulumi up` o `pulumi config`.

**Causa:** La chiave KMS usata per cifrare il segreto è stata eliminata o disabilitata, oppure il secrets provider è cambiato.

**Soluzione:**
```bash
# Verificare il secrets provider dello stack
pulumi stack --stack prod --show-secrets-provider

# Se la chiave è ancora accessibile, ricifrare con la nuova chiave
pulumi stack change-secrets-provider "awskms://alias/nuova-chiave" --stack prod

# Se i segreti sono irrecuperabili, reimpostarli manualmente
pulumi config set --secret dbPassword "nuovo-valore" --stack prod
```

---

### Stack Reference non trovata

**Sintomo:** `error: failed to locate stack: myorg/networking/prod` durante `pulumi up`.

**Causa:** Lo stack referenziato non esiste, o le credenziali del CI non hanno accesso allo stack nel backend.

**Soluzione:**
```bash
# Verificare che lo stack esista
pulumi stack ls --all

# Verificare i permessi (Pulumi Cloud)
# → Console > Settings > Access Tokens > verificare scope

# Con self-managed: verificare che il PULUMI_BACKEND_URL sia lo stesso
echo $PULUMI_BACKEND_URL
pulumi login
pulumi stack ls
```

---

### Drift tra state e infrastruttura reale

**Sintomo:** `pulumi up` mostra modifiche inattese, o risorse mostrano `~` (update) senza cambiamenti al codice.

**Causa:** Qualcuno ha modificato manualmente una risorsa nel cloud (es. via console AWS), creando drift tra state e realtà.

**Soluzione:**
```bash
# Refresh: allinea lo state con la realtà attuale del cloud
pulumi refresh --stack prod

# Dopo il refresh, preview per vedere lo stato
pulumi preview --stack prod

# Se il drift è intenzionale (risorsa modificata a mano e da mantenere),
# aggiornare il codice Pulumi per riflettere il nuovo stato desiderato
```

---

### `pulumi up` cancella risorse inaspettatamente

**Sintomo:** Il preview mostra `[-]` (delete) su risorse che non dovrebbero essere toccate.

**Causa frequente 1:** Il nome di una risorsa è cambiato nel codice (Pulumi usa il nome come chiave nello state).

**Causa frequente 2:** Una resource è stata spostata fuori dallo scope di una condizione (es. `if enableCache:`).

**Soluzione:**
```bash
# Prima di up, studiare attentamente il preview
pulumi preview --diff --stack prod

# Se il delete è un falso positivo da rename, usare aliases
# (in TypeScript/Python) per mantenere la URN vecchia durante la transizione
bucket = aws.s3.Bucket("new-bucket-name",
    opts=pulumi.ResourceOptions(
        aliases=[pulumi.Alias(name="old-bucket-name")]
    )
)

# Per proteggere risorse critiche dalla cancellazione accidentale
bucket = aws.s3.Bucket("prod-data",
    opts=pulumi.ResourceOptions(protect=True)
)
```

---

## Relazioni

??? info "Pulumi — Fondamentali"
    Prerequisito per questa guida: Project, Stack, Resources, Outputs, Config base, Automation API, testing unitario.
    
    **Approfondimento completo →** [Pulumi — Fondamentali](fondamentali.md)

??? info "Terraform — State Management"
    Il concetto di remote state, locking, e backend in Terraform è analogo alla gestione dello state in Pulumi. Utile per confronto o migrazione.
    
    **Approfondimento completo →** [Terraform — State Management](../terraform/state-management.md)

??? info "Terraform — Fondamentali"
    Confronto architetturale: HCL vs linguaggi reali, workspace Terraform vs stack Pulumi, provider ecosystem.
    
    **Approfondimento completo →** [Terraform — Fondamentali](../terraform/fondamentali.md)

---

## Riferimenti

- [Pulumi Stacks — Documentazione ufficiale](https://www.pulumi.com/docs/concepts/stack/)
- [Pulumi Config & Secrets](https://www.pulumi.com/docs/concepts/config/)
- [Pulumi Secrets Providers](https://www.pulumi.com/docs/concepts/secrets/)
- [Pulumi GitHub Actions](https://www.pulumi.com/docs/using-pulumi/continuous-delivery/github-actions/)
- [Pulumi Automation API](https://www.pulumi.com/docs/using-pulumi/automation-api/)
- [Pulumi Deployments](https://www.pulumi.com/docs/pulumi-cloud/deployments/)
- [Stack References](https://www.pulumi.com/docs/concepts/stack/#stackreferences)
