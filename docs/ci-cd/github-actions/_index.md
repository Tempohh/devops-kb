---
title: "GitHub Actions"
slug: github-actions
category: ci-cd
tags: [github-actions, ci-cd, workflows, automation]
search_keywords: [github actions, workflow yaml, actions marketplace, github ci cd, github runner, reusable workflows, composite actions, workflow dispatch]
parent: ci-cd/_index
related: [ci-cd/github-actions/workflow-avanzati, ci-cd/github-actions/enterprise, ci-cd/jenkins/_index, ci-cd/gitops/argocd]
official_docs: https://docs.github.com/en/actions
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# GitHub Actions

## Panoramica

GitHub Actions è la piattaforma CI/CD nativa di GitHub, integrata direttamente nel repository. Permette di automatizzare build, test, deploy e qualsiasi workflow basato su eventi che accadono nel repository (push, pull request, release, ecc.). A differenza di strumenti esterni come Jenkins, non richiede infrastruttura separata: i workflow sono definiti come file YAML in `.github/workflows/` e vengono eseguiti su runner gestiti da GitHub o su runner self-hosted. L'integrazione con l'ecosistema GitHub (Issues, PRs, Packages, Deployments, Environments) è diretta e profonda, rendendo GitHub Actions la scelta naturale per repository già ospitati su GitHub.

## Concetti Fondamentali

### Gerarchia Workflow → Job → Step → Action

```
Workflow (.github/workflows/*.yml)
└── Job (eseguito su un runner)
    └── Step (unità atomica di esecuzione)
        ├── Action (action riusabile da Marketplace o locale)
        └── run (comando shell diretto)
```

| Concetto | Descrizione |
|----------|-------------|
| **Workflow** | File YAML che definisce l'automazione. Più workflow per repo. |
| **Job** | Gruppo di step che girano sullo stesso runner. I job sono isolati tra loro. |
| **Step** | Singola unità: `uses` (Action) o `run` (comando shell). |
| **Action** | Componente riusabile da Marketplace, repo pubblico o locale (`.github/actions/`). |
| **Runner** | Macchina che esegue il job. GitHub-hosted o self-hosted. |
| **Event** | Trigger che avvia il workflow (push, PR, schedule, ecc.). |

### Struttura Minima di un Workflow

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout codice
        uses: actions/checkout@v4

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Build con Maven
        run: mvn --batch-mode clean package -DskipTests

      - name: Esegui test
        run: mvn --batch-mode test
```

## Trigger — Eventi Principali

| Evento | Descrizione | Uso tipico |
|--------|-------------|------------|
| `push` | Commit pushato su branch/tag | Build, test su ogni commit |
| `pull_request` | PR aperta, aggiornata, sincronizzata | CI check su PR (code review gate) |
| `workflow_dispatch` | Trigger manuale con input opzionali | Deploy manuale, task on-demand |
| `schedule` | Cron expression (UTC) | Nightly builds, security scans |
| `workflow_call` | Chiamato da un altro workflow | Reusable workflows |
| `release` | Release pubblicata/creata | Build di release, publish artifacts |
| `push` + `tags` | Push di un tag | Publish to registry, NPM publish |
| `repository_dispatch` | Evento via API esterna | Trigger da altri sistemi |
| `issue_comment` | Commento su issue/PR | Chatops, `/deploy` commands |

```yaml
# Esempio trigger multipli e filtri avanzati
on:
  push:
    branches:
      - main
      - 'release/**'
    paths:
      - 'src/**'
      - 'pom.xml'
    tags:
      - 'v*.*.*'
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]
  schedule:
    - cron: '0 2 * * 1-5'  # Lun-Ven alle 02:00 UTC
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options: [staging, production]
      dry-run:
        description: 'Dry run mode'
        required: false
        type: boolean
        default: false
```

## GitHub-Hosted Runners

GitHub offre runner gestiti senza costi di setup. Le specifiche variano per piano:

| Runner Label | OS | CPU | RAM | Storage | Note |
|---|---|---|---|---|---|
| `ubuntu-latest` | Ubuntu 22.04 | 2 vCPU | 7 GB | 14 GB SSD | Piano Free/Pro |
| `ubuntu-22.04` | Ubuntu 22.04 | 2 vCPU | 7 GB | 14 GB SSD | Label esplicita (stabile) |
| `ubuntu-24.04` | Ubuntu 24.04 | 2 vCPU | 7 GB | 14 GB SSD | Versione recente |
| `windows-latest` | Windows Server 2022 | 2 vCPU | 7 GB | 14 GB SSD | |
| `macos-latest` | macOS 14 (Sonoma) | 3 vCPU | 14 GB | 14 GB SSD | Piano a pagamento |
| `ubuntu-latest` (Large) | Ubuntu 22.04 | 4–64 vCPU | 16–256 GB | Variabile | Larger runners (a pagamento) |

**Limiti importanti:**
- **Timeout massimo per job**: 6 ore (360 minuti)
- **Timeout massimo per workflow**: 35 giorni
- **Job concurrenti**: 20 (Free), 40 (Pro), fino a 500 (Enterprise)
- **Storage artifacts**: 90 giorni retention (default), configurabile
- **GitHub-hosted runner network**: IP pubblici non fissi (range pubblicato da GitHub)

!!! warning "Network privata"
    I GitHub-hosted runner non hanno accesso diretto a risorse in VPC privati. Per accedere a database, registri privati o servizi interni, occorre usare **self-hosted runners** o tunnel sicuri (es. Tailscale, AWS SSM, Cloudflare Tunnel).

## Confronto con Jenkins e GitLab CI

| Feature | GitHub Actions | Jenkins | GitLab CI |
|---------|---------------|---------|-----------|
| **Setup infrastruttura** | Zero (managed) | Alto (server + plugins) | Medio (GitLab instance o SaaS) |
| **Configurazione** | YAML in repo | Jenkinsfile (Groovy DSL) | `.gitlab-ci.yml` |
| **Marketplace Actions** | 20.000+ actions | Plugin ecosystem maturo | Templates limitati |
| **Integrazione SCM** | Nativa GitHub | Tramite plugin | Nativa GitLab |
| **Self-hosted runner** | Sì (semplice) | Sì (agenti) | Sì (runner) |
| **Reusable workflows** | Sì (workflow_call) | Shared Libraries | Include templates |
| **OIDC per cloud auth** | Nativo | Manuale | Nativo |
| **Environments + approvals** | Sì | Nativo (stages) | Sì (environments) |
| **Security scanning** | GHAS (a pagamento) | Plugin terze parti | Built-in (Ultimate) |
| **Costo runner** | Minuti inclusi + a consumo | Infrastruttura propria | Minuti inclusi (SaaS) |
| **Curva apprendimento** | Bassa | Alta | Media |

**Punti di forza GitHub Actions:**
- Nessuna infrastruttura da gestire per il caso comune
- Integrazione profonda con PR, Issues, Deployments API
- Marketplace con migliaia di action pronte
- OIDC per autenticazione cloud senza secrets long-lived
- Secrets e Environments con protection rules

**Limiti rispetto a Jenkins:**
- Meno flessibile per pipeline enterprise complesse con logica custom
- Costo significativo per organizzazioni con molti minuti CI
- Vendor lock-in su GitHub
- Customizzazione avanzata richiede self-hosted runner

## Marketplace Actions e Versioning

Il [GitHub Marketplace](https://github.com/marketplace?type=actions) ospita migliaia di action riusabili. Ogni action è referenziata con `uses: owner/repo@ref`.

### Strategia di Versioning

```yaml
# ❌ Non fare: tag mutabile (il codice può cambiare)
- uses: actions/checkout@main

# ⚠️ Accettabile: semver tag (immutabile se il maintainer non fa force push)
- uses: actions/checkout@v4

# ✅ Best practice sicurezza: SHA commit immutabile
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
- uses: actions/setup-java@99b8673ff64fbf99d8d7b505bd5d0459996d8ad # v4.2.1
```

!!! warning "SHA Pinning"
    Con SHA pinning si garantisce che l'action non possa essere modificata senza che il workflow cambi. Per organizzazioni con requisiti di sicurezza elevati (SOC2, ISO 27001), questa pratica è obbligatoria. Strumenti come [Dependabot](https://docs.github.com/en/code-security/dependabot) e [Renovate](https://docs.renovatebot.com/) aggiornano automaticamente i SHA mantenendo la sicurezza.

### Action Comuni e Affidabili

```yaml
steps:
  # Checkout del codice
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0  # Full history per git blame, versioning
      submodules: recursive

  # Setup linguaggi
  - uses: actions/setup-node@v4
    with:
      node-version: '20'
      cache: 'npm'

  - uses: actions/setup-java@v4
    with:
      java-version: '21'
      distribution: 'temurin'
      cache: 'maven'

  - uses: actions/setup-python@v5
    with:
      python-version: '3.12'
      cache: 'pip'

  # Cache generica
  - uses: actions/cache@v4
    with:
      path: ~/.m2/repository
      key: ${{ runner.os }}-maven-${{ hashFiles('**/pom.xml') }}
      restore-keys: |
        ${{ runner.os }}-maven-

  # Upload/Download artifacts
  - uses: actions/upload-artifact@v4
    with:
      name: build-output
      path: target/*.jar
      retention-days: 7

  # Docker
  - uses: docker/setup-buildx-action@v3
  - uses: docker/login-action@v3
    with:
      registry: ghcr.io
      username: ${{ github.actor }}
      password: ${{ secrets.GITHUB_TOKEN }}
  - uses: docker/build-push-action@v5
    with:
      context: .
      push: true
      tags: ghcr.io/my-org/my-app:${{ github.sha }}
```

## Gestione Secrets e Variables

```yaml
# Secrets: cifrati, non visibili nei log
env:
  DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
  AWS_ACCESS_KEY: ${{ secrets.AWS_ACCESS_KEY_ID }}

# Variables: plaintext, visibili, per configurazione non sensibile
env:
  APP_ENV: ${{ vars.ENVIRONMENT }}
  API_BASE_URL: ${{ vars.API_BASE_URL }}

# GITHUB_TOKEN: token automatico per operazioni su GitHub
- name: Publish release
  run: gh release create v${{ github.ref_name }}
  env:
    GH_TOKEN: ${{ github.token }}
```

**Scope dei secrets:**
- **Repository secrets**: visibili solo ai workflow del repository specifico
- **Environment secrets**: disponibili solo quando il job usa quell'environment
- **Organization secrets**: condivisibili tra repository dell'org (con filtro)

## Relazioni

??? info "Workflow Avanzati — Approfondimento"
    Matrix strategy, reusable workflows, OIDC, composite actions, environments e gestione avanzata degli artifacts.

    **Approfondimento completo →** [GitHub Actions — Workflow Avanzati](workflow-avanzati.md)

??? info "Enterprise & Self-Hosted Runners"
    Actions Runner Controller (ARC), runner su Kubernetes, security hardening, GitHub Advanced Security, governance enterprise.

    **Approfondimento completo →** [GitHub Actions — Enterprise](enterprise.md)

??? info "GitOps con ArgoCD"
    Come integrare GitHub Actions con ArgoCD per un workflow GitOps: aggiornamento immagini nel repo Git, sync automatico.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

## Riferimenti

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Actions Marketplace](https://github.com/marketplace?type=actions)
- [GitHub-hosted runners specs](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners)
- [Workflow syntax reference](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [GitHub Actions Cheat Sheet (GitHub)](https://github.github.io/actions-cheat-sheet/)
