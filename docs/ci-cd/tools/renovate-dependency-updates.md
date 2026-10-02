---
title: "Renovate — Aggiornamento Automatico delle Dipendenze"
slug: renovate-dependency-updates
category: ci-cd
tags: [renovate, dependency-management, dependabot, automerge, supply-chain, sha-pinning, github-actions, docker, automation]
search_keywords: [renovate, renovatebot, renovate bot, mend renovate, renovate app, renovate self-hosted, renovate.json, renovate config, config:recommended, config:base, dependency updates, aggiornamento dipendenze, aggiornamento automatico dipendenze, dependabot, dependabot vs renovate, packageRules, automerge, minimumReleaseAge, stabilityDays, pinDigests, SHA pinning, digest pinning, github actions pinning, customManagers, regexManagers, custom regex manager, dependency dashboard, onboarding pr, prConcurrentLimit, prHourlyLimit, schedule, lockFileMaintenance, renovate-config-validator, LOG_LEVEL debug, renovate cronjob, renovate github action, renovatebot/github-action, datasource, manager, versioning, monorepo, supply chain attack, tool-versions, asdf, helm values, terraform required_providers, major minor patch, group updates]
parent: ci-cd/tools/_index
related: [ci-cd/github-actions/enterprise, security/supply-chain/_index, ci-cd/gitops/argocd, ci-cd/gitops/flux, iac/terraform/fondamentali, ci-cd/strategie/pipeline-security]
official_docs: https://docs.renovatebot.com/
status: draft
difficulty: intermediate
last_updated: 2026-10-02
---

# Renovate — Aggiornamento Automatico delle Dipendenze

## Panoramica

Renovate è un bot open-source (AGPL-3.0, mantenuto da Mend) che scansiona i repository, individua le dipendenze obsolete e apre automaticamente Pull/Merge Request per aggiornarle. A differenza di strumenti legati a un solo ecosistema, copre **oltre 90 package manager** (npm, pip, Maven, Gradle, Go modules, Cargo, Docker, Helm, Terraform, GitHub Actions, `.tool-versions`, ...) e funziona su GitHub, GitLab, Bitbucket, Azure DevOps, Gitea e Forgejo.

Esiste in due forme: la **Mend Renovate app** (SaaS gratuito per GitHub/GitLab, zero infrastruttura) e la modalità **self-hosted** (CLI/container `renovate/renovate` eseguito come GitHub Action, CronJob Kubernetes o job CI). Si usa quando si vuole tenere le dipendenze aggiornate in modo continuo, con grouping, scheduling e automerge governati da policy. Non sostituisce una strategia di test: senza una CI affidabile, l'automerge è pericoloso.

Rispetto a **Dependabot** (integrato in GitHub), Renovate è molto più configurabile: raggruppa aggiornamenti, supporta custom manager per versioni in file arbitrari, ha una dependency dashboard, `minimumReleaseAge`, preset condivisibili e funziona multi-piattaforma. Dependabot vince in semplicità (nessun setup) e integrazione nativa con GitHub Security Advisories.

## Concetti Chiave

!!! note "Il modello mentale: manager → datasource → versioning"
    Per ogni dipendenza Renovate combina tre concetti:

    - **Manager**: sa *dove* trovare le dipendenze in un tipo di file (`npm`, `dockerfile`, `helm-values`, `terraform`, `github-actions`, `asdf`, ...).
    - **Datasource**: sa *dove* cercare le nuove versioni (`npm`, `docker`, `github-releases`, `github-tags`, `helm`, `terraform-provider`, `pypi`, ...).
    - **Versioning**: sa *come* ordinare e interpretare le versioni (`semver`, `pep440`, `docker`, `loose`, `regex`, ...).

### Tabella comparativa Renovate vs Dependabot

| Aspetto | Renovate | Dependabot |
|---|---|---|
| Piattaforme | GitHub, GitLab, Bitbucket, Azure DevOps, Gitea | Solo GitHub |
| Ecosistemi | 90+ manager + custom regex | ~30 ecosistemi, nessun custom manager |
| Grouping | `packageRules` + `groupName`, preset | `groups` (più limitato) |
| Automerge | Nativo, per regola, con `platformAutomerge` | Richiede workflow separato |
| Release age | `minimumReleaseAge` | `cooldown` (introdotto più di recente) |
| Dashboard | Dependency Dashboard (issue) | Tab Insights → Dependency graph |
| Self-hosted | Sì (container/CLI) | No (solo GitHub-hosted) |
| Config condivisa | `extends` con preset su repo/npm | Non supportata |
| Alert di sicurezza | Via `vulnerabilityAlerts` (GitHub) | Nativo, integrato |

### Flusso di vita di un aggiornamento

```
Scheduler/Webhook → Renovate run
   └─ Repo discovery (autodiscover o lista esplicita)
        └─ Extract: i manager trovano le dipendenze nei file
             └─ Lookup: i datasource cercano nuove versioni
                  └─ Filter: versioning, packageRules, schedule, minimumReleaseAge
                       └─ Branch + PR (limitati da prConcurrentLimit / prHourlyLimit)
                            └─ CI verde? → automerge | revisione umana
```

### Onboarding PR e Dependency Dashboard

- **Onboarding PR**: al primo run su un repository Renovate apre una PR che aggiunge `renovate.json` e mostra in anteprima cosa verrebbe aggiornato. Il bot non crea altre PR finché questa non viene mergiata.
- **Dependency Dashboard**: una issue (`Dependency Dashboard`) tenuta aggiornata dal bot. Elenca PR aperte, aggiornamenti in attesa (rate-limited o fuori schedule) e permette di forzarli spuntando una checkbox. Va lasciata abilitata.

## Architettura / Come Funziona

### Esecuzione: Mend app vs self-hosted

| Modalità | Pro | Contro | Quando usarla |
|---|---|---|---|
| **Mend Renovate app** (GitHub/GitLab) | Zero infrastruttura, aggiornata dal vendor | Config globale limitata, codice gira su infra Mend | Repo pubblici, team piccoli |
| **GitHub Action** (`renovatebot/github-action`) | Semplice, gira nel tuo runner, token controllato | Una run alla volta per schedule, gestione token | Org GitHub che vogliono controllo senza cluster |
| **CronJob Kubernetes** | Scalabile, vicino a registry interni, accesso a rete privata | Va gestito e monitorato | Piattaforme interne, GitLab self-managed, registry privati |
| **Job CI** (GitLab CI schedule, Jenkins) | Riusa la CI esistente | Config manuale delle variabili | Ambienti senza Kubernetes |

La differenza chiave: la **config di repository** (`renovate.json`) definisce *cosa* aggiornare; la **config globale self-hosted** (variabili `RENOVATE_*` o `config.js`) definisce *dove* girare (piattaforma, token, autodiscover, `allowedPostUpgradeCommands`, ecc.). Alcune opzioni (es. `allowedPostUpgradeCommands`, `hostRules` con credenziali) sono accettate solo nella config globale per ragioni di sicurezza.

!!! warning "Renovate esegue codice del repository"
    Con certi manager (`postUpgradeTasks`, `gradle`, `npm` con script di postinstall nei lockfile maintenance) Renovate lancia comandi sul contenuto dei repository. In self-hosted usa un token con il minimo privilegio, limita `allowedPostUpgradeCommands` e non eseguirlo su repository non attendibili con credenziali ampie.

## Configurazione & Pratica

### `renovate.json` di partenza

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    ":dependencyDashboard",
    ":semanticCommitTypeAll(chore)"
  ],
  "timezone": "Europe/Rome",
  "schedule": ["before 6am on monday"],
  "prConcurrentLimit": 5,
  "prHourlyLimit": 2,
  "labels": ["dependencies"],
  "rebaseWhen": "conflicted"
}
```

`config:recommended` (nome attuale; in versioni precedenti `config:base`) abilita il set di preset consigliati: dependency dashboard, raggruppamento dei monorepo noti, regole sensate per le immagini Docker, ecc. Parti da qui e aggiungi regole solo quando serve.

!!! tip "Preset condivisi per l'organizzazione"
    Metti la config comune in un repo `renovate-config` (file `default.json`) e usala con `"extends": ["github>mia-org/renovate-config"]`. Ogni repository diventa un `renovate.json` di poche righe e le policy si cambiano in un punto solo.

### packageRules: grouping, automerge, major vs minor

```json
{
  "extends": ["config:recommended"],
  "packageRules": [
    {
      "description": "Patch e minor di dev dependencies: raggruppati e automerge se CI verde",
      "matchDepTypes": ["devDependencies"],
      "matchUpdateTypes": ["minor", "patch"],
      "groupName": "dev dependencies (non-major)",
      "automerge": true,
      "automergeType": "pr",
      "platformAutomerge": true
    },
    {
      "description": "Major: mai automerge, label dedicata, PR separata per package",
      "matchUpdateTypes": ["major"],
      "automerge": false,
      "labels": ["dependencies", "major-update"],
      "dependencyDashboardApproval": true
    },
    {
      "description": "Aggiornamenti di sicurezza non seguono lo schedule",
      "matchCategories": ["security"],
      "schedule": ["at any time"]
    },
    {
      "description": "Bloccare un package noto problematico",
      "matchPackageNames": ["node"],
      "allowedVersions": "<23"
    }
  ]
}
```

- `dependencyDashboardApproval: true` fa sì che la PR major venga creata **solo** dopo che qualcuno spunta la checkbox nella dashboard.
- `platformAutomerge: true` delega il merge alla piattaforma (GitHub auto-merge): richiede che nel repository sia abilitato l'auto-merge e che la branch protection definisca i check obbligatori.

!!! warning "Automerge senza check obbligatori = merge alla cieca"
    Se la branch protection non richiede status check, Renovate considera "verde" una PR senza check e la mergia. Configura sempre **required status checks** sul branch di default prima di abilitare `automerge`.

### Schedule e limiti di PR

```json
{
  "schedule": ["after 22:00 every weekday", "before 05:00 every weekday", "every weekend"],
  "timezone": "Europe/Rome",
  "prConcurrentLimit": 10,
  "prHourlyLimit": 4,
  "branchConcurrentLimit": 15,
  "lockFileMaintenance": {
    "enabled": true,
    "schedule": ["before 4am on the first day of the month"]
  }
}
```

La sintassi dello schedule usa il formato human-readable di `later.js` (default) o cron. `prConcurrentLimit` limita le PR aperte contemporaneamente (0 = illimitate), `prHourlyLimit` la velocità di creazione. Le PR oltre i limiti restano elencate nella dashboard come *Pending* o *Rate-limited*.

### Pinning dei digest: immagini Docker e GitHub Actions

Il tag di un'immagine o di una action è **mutabile**: `node:22` oggi e domani può puntare a contenuti diversi. Il pinning del digest (`@sha256:...`) lo rende immutabile; Renovate poi aggiorna il digest in modo controllato, con una PR visibile.

```json
{
  "extends": [
    "config:recommended",
    "docker:pinDigests",
    "helpers:pinGitHubActionDigests"
  ]
}
```

Effetto su un workflow GitHub Actions (Renovate mantiene il commento con la versione leggibile):

```yaml
# Prima
- uses: actions/checkout@v4

# Dopo (PR di Renovate)
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

Effetto su un Dockerfile:

```dockerfile
# Prima
FROM node:22-alpine

# Dopo
FROM node:22-alpine@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

??? info "SHA pinning delle GitHub Actions — Approfondimento"
    Il pinning a SHA di commit impedisce che un tag riscritto (es. incidente tj-actions/changed-files, 2025) inietti codice nei tuoi workflow. Renovate è lo strumento che rende sostenibile la pratica, perché aggiorna lo SHA e il commento di versione insieme.

    **Approfondimento completo →** [GitHub Actions Enterprise](../github-actions/enterprise.md)

### minimumReleaseAge: difesa contro supply-chain attack

Molti pacchetti malevoli vengono scoperti e rimossi nelle ore o nei giorni successivi alla pubblicazione. Ritardare l'adozione delle nuove release riduce drasticamente l'esposizione.

```json
{
  "packageRules": [
    {
      "description": "Attendi 7 giorni dalla pubblicazione prima di aprire la PR (npm/pypi)",
      "matchDatasources": ["npm", "pypi"],
      "minimumReleaseAge": "7 days"
    },
    {
      "description": "Immagini Docker e Actions: 3 giorni",
      "matchDatasources": ["docker", "github-tags", "github-releases"],
      "minimumReleaseAge": "3 days"
    }
  ],
  "internalChecksFilter": "strict"
}
```

Con `internalChecksFilter: "strict"` Renovate non crea nemmeno il branch finché la regola di età non è soddisfatta (senza, la PR esiste con uno status check `renovate/stability-days` pendente). Eccezione utile: gli aggiornamenti di sicurezza possono avere una regola separata con `minimumReleaseAge: null`.

!!! tip "Combina età minima e SHA pinning"
    `minimumReleaseAge` protegge dalle release appena pubblicate e poi ritirate; il pinning protegge da tag riscritti *dopo* il merge. Insieme coprono le due finestre di attacco più comuni. Vedi anche [Supply Chain Security](../../security/supply-chain/_index.md).

### Custom regex manager

Quando la versione vive in un file che nessun manager conosce (ARG nei Dockerfile, valori Helm, script, Makefile) si usa un **custom manager** di tipo `regex`. Si annota il file con un commento e si definisce l'estrazione.

```dockerfile
# Dockerfile
# renovate: datasource=github-releases depName=hashicorp/terraform
ARG TERRAFORM_VERSION=1.9.8
# renovate: datasource=github-releases depName=kubernetes-sigs/kustomize extractVersion=^kustomize/v(?<version>.*)$
ARG KUSTOMIZE_VERSION=5.4.3
```

```json
{
  "customManagers": [
    {
      "customType": "regex",
      "description": "Versioni annotate con '# renovate:' in Dockerfile, Makefile, shell",
      "managerFilePatterns": ["/(^|/)Dockerfile$/", "/(^|/)Makefile$/", "/\\.sh$/"],
      "matchStrings": [
        "#\\s*renovate:\\s*datasource=(?<datasource>[a-z-]+?)\\s+depName=(?<depName>[^\\s]+?)(?:\\s+extractVersion=(?<extractVersion>[^\\s]+))?\\s*\\n\\s*(?:ARG|ENV)?\\s*\\w+[= ](?<currentValue>[^\\s]+)"
      ]
    }
  ]
}
```

!!! note "Naming: `customManagers` e `managerFilePatterns`"
    Nelle versioni recenti `regexManagers` è stato sostituito da `customManagers` con `customType: "regex"`, e `fileMatch` da `managerFilePatterns` (regex racchiuse tra `/`). Se usi un'istanza self-hosted datata, controlla la versione: `renovate-config-validator` segnala le opzioni deprecate e propone la migrazione. Esistono anche preset pronti come `customManagers:dockerfileVersions` e `customManagers:helmChartYamlAppVersions`.

Esempio per Helm values (tag immagine in un file `values.yaml`):

```yaml
# values.yaml
image:
  # renovate: datasource=docker depName=ghcr.io/mia-org/api
  tag: "1.14.2"
```

```json
{
  "customManagers": [
    {
      "customType": "regex",
      "managerFilePatterns": ["/(^|/)values[^/]*\\.ya?ml$/"],
      "matchStrings": [
        "#\\s*renovate:\\s*datasource=(?<datasource>[a-z-]+?)\\s+depName=(?<depName>[^\\s]+)\\s*\\n\\s*tag:\\s*\"?(?<currentValue>[^\\s\"]+)\"?"
      ]
    }
  ]
}
```

### Terraform, `.tool-versions` e altri manager nativi

Non serve un custom manager per i casi più comuni: Renovate li supporta già.

```hcl
# versions.tf — il manager `terraform` aggiorna sia provider che versione di Terraform
terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}
```

```text
# .tool-versions — il manager `asdf` aggiorna le versioni dei tool
terraform 1.9.8
nodejs 22.11.0
kubectl 1.31.2
```

```json
{
  "packageRules": [
    {
      "description": "Provider Terraform: PR separata per ogni major, minor/patch raggruppate",
      "matchManagers": ["terraform"],
      "matchDepTypes": ["required_provider"],
      "matchUpdateTypes": ["minor", "patch"],
      "groupName": "terraform providers"
    }
  ],
  "lockFileMaintenance": { "enabled": true }
}
```

Con `lockFileMaintenance` Renovate rigenera `.terraform.lock.hcl` (hash dei provider) e gli altri lockfile. Per i dettagli sui provider vedi [Terraform — Fondamentali](../../iac/terraform/fondamentali.md).

### Esecuzione self-hosted: GitHub Action

```yaml
# .github/workflows/renovate.yml
name: Renovate
on:
  schedule:
    - cron: "0 */4 * * *"
  workflow_dispatch:
    inputs:
      log_level:
        description: "Livello di log"
        default: "info"
permissions:
  contents: read
concurrency:
  group: renovate
  cancel-in-progress: false
jobs:
  renovate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: renovatebot/github-action@v41.0.0   # pinnare a SHA in produzione
        with:
          token: ${{ secrets.RENOVATE_TOKEN }}     # PAT fine-grained o GitHub App token
        env:
          RENOVATE_REPOSITORIES: ${{ github.repository }}
          LOG_LEVEL: ${{ inputs.log_level || 'info' }}
```

!!! warning "Usa un token dedicato, non `GITHUB_TOKEN`"
    Le PR create con `GITHUB_TOKEN` **non innescano altri workflow** (regola anti-ricorsione di GitHub): la CI non partirebbe e l'automerge non vedrebbe mai i check. Usa una GitHub App o un PAT fine-grained con permessi `contents`, `pull-requests`, `issues`, `workflows` (quest'ultimo serve per modificare i file in `.github/workflows`).

### Esecuzione self-hosted: CronJob Kubernetes

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: renovate
  namespace: renovate
spec:
  schedule: "0 */4 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 0
      activeDeadlineSeconds: 3000
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: renovate
              image: ghcr.io/renovatebot/renovate:39   # pinnare a digest
              env:
                - name: RENOVATE_PLATFORM
                  value: github
                - name: RENOVATE_AUTODISCOVER
                  value: "true"
                - name: RENOVATE_AUTODISCOVER_FILTER
                  value: "mia-org/*"
                - name: LOG_LEVEL
                  value: info
                - name: RENOVATE_TOKEN
                  valueFrom:
                    secretKeyRef:
                      name: renovate-secrets
                      key: token
                - name: RENOVATE_GIT_AUTHOR
                  value: "Renovate Bot <renovate@example.com>"
              resources:
                requests: { cpu: 500m, memory: 1Gi }
                limits: { memory: 2Gi }
```

```bash
# Esecuzione manuale di un giro per test
kubectl -n renovate create job --from=cronjob/renovate renovate-manual-$(date +%s)
kubectl -n renovate logs -f job/renovate-manual-<timestamp>
```

L'immagine `renovate/renovate` (Docker Hub) e `ghcr.io/renovatebot/renovate` sono equivalenti; la variante `-full` include più toolchain per i `postUpgradeTasks`.

### Integrazione con la CI e GitOps

- **Automerge solo se verde**: affidalo ai required status checks (vedi sopra); per le PR Renovate è comune restringere la CI pesante con `if: github.actor == 'renovate[bot]'` o path filter.
- **Aggiornamento tag immagine in repo GitOps**: Renovate può aggiornare i tag in manifest Kubernetes, `kustomization.yaml` e `values.yaml` (manager `kubernetes`, `kustomize`, `helm-values`, `argocd`, `flux`). La PR mergiata è il trigger del deploy: ArgoCD/Flux rilevano il commit. Alternativa per immagini ad alta frequenza: Argo CD Image Updater / Flux image automation.
- **Ambienti progressivi**: usa `packageRules` con `matchFileNames` per aggiornare prima `envs/staging/**` con automerge e `envs/prod/**` solo con approvazione manuale.

??? info "GitOps — Approfondimento"
    Renovate si inserisce nel ciclo GitOps come "autore" delle PR che cambiano la versione desiderata; il controller (ArgoCD o Flux) riconcilia lo stato.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md) · [Flux](../gitops/flux.md)

### Monorepo

```json
{
  "extends": ["config:recommended"],
  "packageRules": [
    {
      "description": "Servizi backend: gruppo per directory",
      "matchFileNames": ["services/backend/**"],
      "additionalBranchPrefix": "backend/",
      "addLabels": ["team-backend"]
    },
    {
      "description": "Frontend: solo patch automerge",
      "matchFileNames": ["apps/web/**"],
      "matchUpdateTypes": ["patch"],
      "automerge": true
    },
    {
      "description": "Raggruppa tutti i pacchetti @angular/* (stessa release train)",
      "matchPackageNames": ["@angular/**"],
      "groupName": "angular"
    }
  ],
  "ignorePaths": ["**/node_modules/**", "**/examples/**", "**/testdata/**"]
}
```

Usa `ignorePaths` per escludere fixture e directory di esempio (fonte tipica di PR inutili) e `matchFileNames` (ex `matchPaths`) per applicare regole per cartella.

## Best Practices

- **Parti piano**: onboarding con `config:recommended`, schedule settimanale e `prConcurrentLimit` basso; allenta dopo aver visto il volume reale.
- **Automerge solo dove il rischio è basso**: patch/minor di devDependencies, digest di immagini base, GitHub Actions con test solidi. Mai automerge dei major.
- **Raggruppa per release train** (`groupName`) per ridurre il rumore, ma non raggruppare major diversi in un'unica PR illeggibile.
- **Pinning + età minima**: `pinDigests` e `minimumReleaseAge` sono il binomio anti supply-chain; vedi [Pipeline Security](../strategie/pipeline-security.md).
- **Un solo preset aziendale** in un repo dedicato, versionato e usato via `extends`.
- **Valida la config in CI** con `renovate-config-validator` prima del merge di modifiche a `renovate.json`.
- **Lascia attiva la Dependency Dashboard**: è l'unico posto dove vedi cosa è in attesa o bloccato.
- **Anti-pattern**: `"extends": ["config:recommended"]` + automerge globale senza required checks; token personale di un utente come identità del bot; ignorare le PR per mesi (il debito di aggiornamento cresce e i major si accumulano).

## Troubleshooting

### Scenario 1 — PR flood: decine di PR al primo giorno

**Sintomo:** dopo l'onboarding arrivano 40+ PR in poche ore, la CI si intasa.

**Causa:** `prConcurrentLimit` e `prHourlyLimit` troppo alti o assenti, nessun grouping, nessuno schedule.

**Soluzione:**

```json
{
  "prConcurrentLimit": 5,
  "prHourlyLimit": 2,
  "schedule": ["before 6am on monday"],
  "packageRules": [
    { "matchUpdateTypes": ["minor", "patch"], "groupName": "non-major", "groupSlug": "non-major" }
  ]
}
```

Chiudi le PR non volute: con `dependencyDashboardApproval: true` per i major non vengono ricreate finché non le approvi dalla dashboard.

### Scenario 2 — `Rate limit exceeded` sulle API della piattaforma

**Sintomo:** nei log `API rate limit exceeded` / `403` o `secondary rate limit`, il run termina senza completare i repository.

**Causa:** troppi repository con un solo token, `autodiscover` su un'intera organizzazione, run troppo frequenti.

**Soluzione:** usa una **GitHub App** (limite per installazione, molto più alto del PAT), distribuisci i repository su più run con `RENOVATE_AUTODISCOVER_FILTER`, riduci la frequenza dello schedule e imposta un token per accedere a `github.com` (`RENOVATE_GITHUB_COM_TOKEN`) per le release note, che altrimenti consumano la quota anonima:

```bash
# Verifica quota residua del token usato
curl -sH "Authorization: Bearer $RENOVATE_TOKEN" https://api.github.com/rate_limit | jq '.resources.core'
```

### Scenario 3 — Lockfile non aggiornato nella PR

**Sintomo:** la PR cambia `package.json` ma non `package-lock.json` (o `poetry.lock`, `go.sum`), la CI fallisce con `npm ci` incoerente.

**Causa:** nel self-hosted manca il toolchain per rigenerare il lockfile (versione di Node/Poetry non corrispondente), oppure l'aggiornamento del lockfile fallisce (errori visibili nei log come `Artifact file update failure`).

**Soluzione:**

```bash
# Esegui in debug solo su un repository e leggi la sezione "artifactErrors"
LOG_LEVEL=debug RENOVATE_REPOSITORIES=mia-org/api renovate 2>&1 | tee renovate.log
grep -n "artifactErrors\|Artifact file update failure" renovate.log
```

Allinea il toolchain (usa l'immagine `-full`, oppure `binarySource: "install"` per far scaricare a Renovate la versione richiesta da `engines`/`.nvmrc`), e per Go aggiungi `"postUpdateOptions": ["gomodTidy"]`.

### Scenario 4 — Renovate non crea nessuna PR

**Sintomo:** nessun branch né PR, la dashboard mostra aggiornamenti *Awaiting Schedule* o non esiste.

**Causa:** config JSON invalida (Renovate apre una issue/PR "Action Required: Fix Renovate Configuration"), `schedule` non soddisfatto, `minimumReleaseAge` non ancora trascorso, repository non incluso nell'autodiscover, onboarding PR non mergiata.

**Soluzione:**

```bash
# Valida la config del repository (anche in pre-commit/CI)
npx --yes --package renovate -- renovate-config-validator renovate.json

# Se usi preset: valida anche la config globale e controlla migrazioni
npx --yes --package renovate -- renovate-config-validator --strict
```

Poi lancia con `LOG_LEVEL=debug` e cerca `"Repository finished"`, `"Branch cannot be updated"`, `"Skipping branch creation"` e il riepilogo `packageFiles with updates`: indicano quale filtro ha scartato l'aggiornamento.

### Scenario 5 — Custom manager non rileva la versione

**Sintomo:** la riga annotata con `# renovate:` non viene mai aggiornata.

**Causa:** `managerFilePatterns` non corrisponde al path, la regex non cattura i named group obbligatori (`currentValue`, `depName`, `datasource`), oppure la versione non corrisponde al `versioning` del datasource.

**Soluzione:** nel log debug cerca il manager `custom.regex` e le dipendenze estratte; testa la regex su regex101 (flavor JavaScript); aggiungi `extractVersion` per tag con prefisso (`v1.2.3`, `kustomize/v5.4.3`) e `versioningTemplate` se serve (`semver`, `loose`).

## Relazioni

??? info "GitHub Actions Enterprise — SHA pinning"
    Renovate automatizza l'aggiornamento degli SHA delle action pinnate e delle versioni nei workflow riutilizzabili.

    **Approfondimento completo →** [GitHub Actions Enterprise](../github-actions/enterprise.md)

??? info "Supply Chain Security"
    Pinning dei digest, `minimumReleaseAge` e revisione delle PR di aggiornamento sono controlli di supply chain; si integrano con SBOM e scansione delle immagini.

    **Approfondimento completo →** [Supply Chain Security](../../security/supply-chain/_index.md)

??? info "Pipeline Security"
    Hardening della pipeline CI/CD: permessi minimi dei token, pinning, ambienti protetti. Il bot Renovate è un'identità da governare come le altre.

    **Approfondimento completo →** [Pipeline Security](../strategie/pipeline-security.md)

??? info "ArgoCD e Flux — aggiornamento dei tag immagine"
    Le PR di Renovate sul repo GitOps sono il meccanismo "pull request driven" per promuovere nuove versioni; il controller GitOps applica il cambio dopo il merge.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md) · [Flux](../gitops/flux.md)

??? info "Terraform"
    Il manager `terraform` aggiorna `required_providers`, versioni dei moduli e `.terraform.lock.hcl`.

    **Approfondimento completo →** [Terraform — Fondamentali](../../iac/terraform/fondamentali.md)

## Riferimenti

- [Renovate — Documentazione ufficiale](https://docs.renovatebot.com/)
- [Configuration Options](https://docs.renovatebot.com/configuration-options/)
- [Preset ufficiali (config:recommended, helpers, docker)](https://docs.renovatebot.com/presets-config/)
- [Custom Managers (regex)](https://docs.renovatebot.com/modules/manager/regex/)
- [Self-hosting Renovate](https://docs.renovatebot.com/getting-started/running/)
- [renovatebot/github-action](https://github.com/renovatebot/github-action)
- [Renovate — GitHub repository](https://github.com/renovatebot/renovate)
- [Mend Renovate — Dependency Dashboard](https://docs.renovatebot.com/key-concepts/dashboard/)
- [Dependabot — Documentazione](https://docs.github.com/en/code-security/dependabot)
