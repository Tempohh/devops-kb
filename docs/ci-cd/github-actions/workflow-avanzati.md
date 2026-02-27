---
title: "GitHub Actions — Workflow Avanzati"
slug: workflow-avanzati
category: ci-cd
tags: [github-actions, matrix, reusable-workflows, composite-actions, oidc, secrets, environments]
search_keywords: [github actions matrix, reusable workflow, workflow_call, composite action, github oidc, github secrets, github environments, concurrency group, artifacts, cache actions, github packages, strategy matrix]
parent: ci-cd/github-actions/_index
related: [ci-cd/github-actions/enterprise, ci-cd/jenkins/pipeline-fundamentals, security/secret-management]
official_docs: https://docs.github.com/en/actions/using-workflows/reusing-workflows
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# GitHub Actions — Workflow Avanzati

## Panoramica

Questo documento copre le funzionalità avanzate di GitHub Actions: matrix strategy per test cross-platform, reusable workflows per riutilizzo del codice CI/CD, composite actions per step riutilizzabili, autenticazione cloud tramite OIDC senza secrets long-lived, environments con protection rules per deployment sicuri, e gestione ottimizzata di artifacts e cache. Queste feature consentono di costruire pipeline enterprise-grade scalabili e sicure, riducendo la duplicazione e aumentando la manutenibilità dei workflow.

## Matrix Strategy

La matrix strategy permette di eseguire un job con combinazioni diverse di variabili (OS, versione linguaggio, configurazione), generando automaticamente N job paralleli.

### Matrix Base

```yaml
name: Cross-Platform Build

on: [push, pull_request]

jobs:
  build:
    name: Build on ${{ matrix.os }} / Java ${{ matrix.java }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false        # Non cancellare gli altri job se uno fallisce
      max-parallel: 4         # Massimo 4 job in parallelo
      matrix:
        os: [ubuntu-latest, windows-latest]
        java: ['11', '17', '21']
        include:
          # Aggiunge proprietà extra per combinazioni specifiche
          - os: ubuntu-latest
            java: '21'
            experimental: true
            deploy: true
          - os: ubuntu-latest
            java: '17'
            sonar: true
        exclude:
          # Rimuove combinazioni non supportate
          - os: windows-latest
            java: '11'

    steps:
      - uses: actions/checkout@v4

      - name: Setup Java ${{ matrix.java }}
        uses: actions/setup-java@v4
        with:
          java-version: ${{ matrix.java }}
          distribution: 'temurin'

      - name: Build
        run: ./mvnw --batch-mode clean package

      - name: SonarQube Analysis
        if: matrix.sonar == true
        run: ./mvnw sonar:sonar
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}

      - name: Deploy
        if: matrix.deploy == true && github.ref == 'refs/heads/main'
        run: echo "Deploying from ${{ matrix.os }} with Java ${{ matrix.java }}"
```

### Matrix Dinamica da JSON

```yaml
jobs:
  generate-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set-matrix.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - id: set-matrix
        run: |
          # Genera la matrice dinamicamente (es. da file o script)
          MATRIX=$(cat .github/test-matrix.json)
          echo "matrix=$MATRIX" >> $GITHUB_OUTPUT

  test:
    needs: generate-matrix
    runs-on: ubuntu-latest
    strategy:
      matrix: ${{ fromJson(needs.generate-matrix.outputs.matrix) }}
    steps:
      - uses: actions/checkout@v4
      - name: Test ${{ matrix.service }}
        run: ./test.sh ${{ matrix.service }}
```

## Reusable Workflows

I reusable workflows permettono di chiamare un workflow da un altro, eliminando duplicazioni tra repository o tra branch dello stesso repo.

### Workflow Chiamante (Caller)

```yaml
# .github/workflows/deploy.yml — nel repository applicativo
name: Deploy Application

on:
  push:
    branches: [main]

jobs:
  run-tests:
    uses: my-org/.github/.github/workflows/reusable-test.yml@main
    with:
      java-version: '21'
      run-sonar: true
    secrets: inherit  # Propaga tutti i secrets del caller al called workflow

  deploy-staging:
    needs: run-tests
    uses: my-org/.github/.github/workflows/reusable-deploy.yml@main
    with:
      environment: staging
      image-tag: ${{ github.sha }}
    secrets:
      deploy-token: ${{ secrets.STAGING_DEPLOY_TOKEN }}
      registry-password: ${{ secrets.REGISTRY_PASSWORD }}

  deploy-production:
    needs: deploy-staging
    uses: my-org/.github/.github/workflows/reusable-deploy.yml@main
    with:
      environment: production
      image-tag: ${{ github.sha }}
    secrets: inherit
```

### Workflow Riutilizzabile (Called)

```yaml
# .github/workflows/reusable-deploy.yml — nel repository .github dell'org
name: Reusable Deploy Workflow

on:
  workflow_call:
    inputs:
      environment:
        description: 'Target deployment environment'
        required: true
        type: string
      image-tag:
        description: 'Docker image tag to deploy'
        required: true
        type: string
      namespace:
        description: 'Kubernetes namespace'
        required: false
        type: string
        default: 'default'
      dry-run:
        description: 'Perform dry run only'
        required: false
        type: boolean
        default: false
    secrets:
      deploy-token:
        description: 'Token per il deploy'
        required: true
      registry-password:
        required: false
    outputs:
      deployment-url:
        description: 'URL del deployment completato'
        value: ${{ jobs.deploy.outputs.url }}

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    outputs:
      url: ${{ steps.deploy.outputs.deployment-url }}
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to ${{ inputs.environment }}
        id: deploy
        run: |
          echo "Deploying image tag: ${{ inputs.image-tag }}"
          echo "Environment: ${{ inputs.environment }}"
          echo "Namespace: ${{ inputs.namespace }}"
          if [ "${{ inputs.dry-run }}" = "true" ]; then
            echo "DRY RUN — nessun deploy effettivo"
          else
            # Deploy reale
            kubectl set image deployment/myapp \
              app=my-registry/myapp:${{ inputs.image-tag }} \
              -n ${{ inputs.namespace }}
            echo "deployment-url=https://${{ inputs.environment }}.example.com" >> $GITHUB_OUTPUT
          fi
        env:
          DEPLOY_TOKEN: ${{ secrets.deploy-token }}
```

!!! note "Limitazioni Reusable Workflows"
    - Massimo **4 livelli** di nesting (workflow che chiama workflow che chiama workflow...)
    - Non è possibile usare una **matrix strategy** per chiamare reusable workflows (workaround: matrix nel called workflow)
    - I secrets devono essere esplicitamente passati con `secrets:` o con `secrets: inherit`
    - Il called workflow deve trovarsi in un repository accessibile al caller (stesso repo o repository pubblico/stesso org)

## Composite Actions

Una composite action è una action personalizzata che combina più step in un unico componente riusabile, distribuibile come file `action.yml` in `.github/actions/` o in un repository dedicato.

```yaml
# .github/actions/build-and-push/action.yml
name: 'Build and Push Docker Image'
description: 'Build Docker image, scan con Trivy, push a GHCR'

inputs:
  image-name:
    description: 'Nome dell immagine Docker (senza tag)'
    required: true
  image-tag:
    description: 'Tag dell immagine Docker'
    required: false
    default: ${{ github.sha }}
  registry:
    description: 'Container registry URL'
    required: false
    default: 'ghcr.io'
  dockerfile:
    description: 'Path al Dockerfile'
    required: false
    default: './Dockerfile'
  push:
    description: 'Se fare il push dell immagine'
    required: false
    default: 'true'

outputs:
  image-digest:
    description: 'SHA256 digest dell immagine pushata'
    value: ${{ steps.build.outputs.digest }}
  full-image-ref:
    description: 'Referenza completa immagine:tag'
    value: ${{ steps.meta.outputs.tags }}

runs:
  using: 'composite'
  steps:
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ inputs.registry }}/${{ inputs.image-name }}
        tags: |
          type=raw,value=${{ inputs.image-tag }}
          type=sha,prefix=sha-
          type=semver,pattern={{version}}

    - name: Build Docker image
      id: build
      uses: docker/build-push-action@v5
      with:
        context: .
        file: ${{ inputs.dockerfile }}
        push: ${{ inputs.push == 'true' }}
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

    - name: Scan immagine con Trivy
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ inputs.registry }}/${{ inputs.image-name }}:${{ inputs.image-tag }}
        format: 'sarif'
        output: 'trivy-results.sarif'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'  # Fallisce se trovate vuln CRITICAL/HIGH

    - name: Upload Trivy results to GitHub Security
      uses: github/codeql-action/upload-sarif@v3
      if: always()
      with:
        sarif_file: 'trivy-results.sarif'
      shell: bash
```

Utilizzo della composite action nel workflow:

```yaml
# .github/workflows/ci.yml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push
        id: docker
        uses: ./.github/actions/build-and-push  # Riferimento locale
        with:
          image-name: ${{ github.repository }}
          image-tag: ${{ github.sha }}

      - name: Usa output dell action
        run: |
          echo "Image digest: ${{ steps.docker.outputs.image-digest }}"
          echo "Full ref: ${{ steps.docker.outputs.full-image-ref }}"
```

## OIDC — Autenticazione Cloud senza Secrets Long-Lived

GitHub Actions supporta OpenID Connect (OIDC) per ottenere token temporanei dai cloud provider, eliminando la necessità di conservare credenziali come `AWS_ACCESS_KEY_ID` nei secrets di GitHub.

### Meccanismo OIDC

```
GitHub Actions Runner
       │
       │  Richiede JWT token (OIDC)
       ▼
GitHub OIDC Provider (https://token.actions.githubusercontent.com)
       │
       │  JWT firmato con claims: repo, branch, workflow, job_workflow_ref
       ▼
Cloud Provider (AWS/Azure/GCP)
       │
       │  Verifica JWT firma + claims (trust policy)
       │  Emette credenziali temporanee (TTL breve)
       ▼
GitHub Actions Runner riceve credenziali temporanee
```

### Configurazione OIDC per AWS

**Step 1: Configurare l'Identity Provider in AWS IAM**

```json
{
  "Type": "AWS::IAM::OIDCProvider",
  "Properties": {
    "Url": "https://token.actions.githubusercontent.com",
    "ClientIdList": ["sts.amazonaws.com"],
    "ThumbprintList": ["6938fd4d98bab03faadb97b34396831e3780aea1"]
  }
}
```

**Step 2: Creare il ruolo IAM con Trust Policy**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": [
            "repo:my-org/my-repo:ref:refs/heads/main",
            "repo:my-org/my-repo:environment:production"
          ]
        }
      }
    }
  ]
}
```

**Step 3: Workflow GitHub Actions**

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

permissions:
  id-token: write   # OBBLIGATORIO per richiedere il JWT OIDC
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-deploy-role
          role-session-name: GitHubActions-${{ github.run_id }}
          aws-region: eu-west-1
          # role-duration-seconds: 3600  # Default: 1h

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Push a ECR
        run: |
          docker build -t ${{ steps.login-ecr.outputs.registry }}/myapp:${{ github.sha }} .
          docker push ${{ steps.login-ecr.outputs.registry }}/myapp:${{ github.sha }}

      - name: Deploy su ECS
        run: |
          aws ecs update-service \
            --cluster production \
            --service myapp \
            --force-new-deployment
```

### OIDC per Azure

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - name: Azure login via OIDC
    uses: azure/login@v2
    with:
      client-id: ${{ secrets.AZURE_CLIENT_ID }}        # Application (client) ID
      tenant-id: ${{ secrets.AZURE_TENANT_ID }}        # Directory (tenant) ID
      subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      # Non serve client-secret: autenticazione tramite Federated Identity Credential
```

### OIDC per Google Cloud

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - name: Authenticate to Google Cloud
    uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
      service_account: 'github-actions@my-project.iam.gserviceaccount.com'
```

## Environments con Protection Rules

Gli Environments permettono di modellare gli ambienti di deployment (staging, production) con controlli di accesso, secrets separati e regole di protezione.

```yaml
# Workflow che usa un environment
jobs:
  deploy-production:
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://myapp.example.com  # Link mostrato nell'UI di GitHub
    steps:
      - name: Deploy
        run: ./deploy.sh production
        env:
          DB_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}  # Secret dell'environment
```

**Configurazione via GitHub UI / API (`POST /repos/{owner}/{repo}/environments`):**

```json
{
  "wait_timer": 15,
  "reviewers": [
    {
      "type": "Team",
      "id": 1234567
    },
    {
      "type": "User",
      "id": 9876543
    }
  ],
  "deployment_branch_policy": {
    "protected_branches": true,
    "custom_branch_policies": false
  }
}
```

**Protection Rules disponibili:**
- **Required reviewers**: 1-6 persone/team devono approvare prima che il job parta
- **Wait timer**: delay in minuti prima dell'esecuzione (0-43.200 minuti)
- **Deployment branches**: solo branch protetti o pattern specifici possono fare deploy
- **Environment secrets**: secrets visibili solo ai job che usano quell'environment

## Concurrency Groups

Il blocco `concurrency` permette di gestire run concorrenti dello stesso workflow, utile per evitare deploy paralleli sullo stesso ambiente.

```yaml
# A livello workflow: applica a tutti i job
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Cancella il run precedente quando parte uno nuovo

# A livello job: granularità maggiore
jobs:
  deploy:
    concurrency:
      group: deploy-${{ inputs.environment }}
      cancel-in-progress: false  # Non cancellare un deploy in corso!
```

**Casi d'uso:**

```yaml
# CI su PR: cancella i run precedenti quando si pusha un nuovo commit
on:
  pull_request:

concurrency:
  group: ci-${{ github.event.pull_request.number }}
  cancel-in-progress: true

---

# Deploy production: non cancellare mai un deploy in corso
jobs:
  deploy-prod:
    concurrency:
      group: deploy-production
      cancel-in-progress: false
    environment: production
```

## Artifacts e Cache

### Artifacts — Condivisione tra Job

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build
        run: mvn --batch-mode package -DskipTests

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: jar-artifact-${{ github.sha }}
          path: |
            target/*.jar
            !target/*-sources.jar
          retention-days: 30        # Default: 90 giorni
          compression-level: 9      # 0-9, default 6
          if-no-files-found: error  # error | warn | ignore

  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: jar-artifact-${{ github.sha }}
          path: ./target

      - name: Esegui test con il JAR
        run: java -jar target/myapp.jar --test

  # Download tutti gli artifacts del run
  publish:
    needs: [build, test]
    runs-on: ubuntu-latest
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          path: ./artifacts   # Crea sottocartelle per ogni artifact
          pattern: jar-*      # Filtra per nome
          merge-multiple: true
```

### Cache — Dipendenze tra Run

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Cache Maven
      - name: Cache Maven dependencies
        uses: actions/cache@v4
        with:
          path: ~/.m2/repository
          key: ${{ runner.os }}-maven-${{ hashFiles('**/pom.xml') }}
          restore-keys: |
            ${{ runner.os }}-maven-${{ hashFiles('**/pom.xml') }}
            ${{ runner.os }}-maven-

      # Cache npm
      - name: Cache npm dependencies
        uses: actions/cache@v4
        with:
          path: |
            ~/.npm
            node_modules
          key: ${{ runner.os }}-npm-${{ hashFiles('package-lock.json') }}
          restore-keys: |
            ${{ runner.os }}-npm-

      # Cache Gradle
      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: ${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle*', '**/gradle-wrapper.properties') }}
          restore-keys: |
            ${{ runner.os }}-gradle-

      # Cache pip
      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Build
        run: mvn --batch-mode clean package
```

!!! tip "Cache vs Artifacts"
    - **Cache**: dati che possono essere rigenerati (dipendenze, build cache). Condiviso tra run, non tra workflow diversi. Max 10 GB per repository.
    - **Artifacts**: output del build da condividere tra job dello stesso run o da scaricare. Retention configurabile, non condiviso tra run.

## GitHub Packages — Publish Docker Image

```yaml
name: Publish Docker Image to GHCR

on:
  push:
    branches: [main]
    tags: ['v*.*.*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}  # es. my-org/my-app

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write    # Necessario per pushare su GHCR
      attestations: write
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}  # GITHUB_TOKEN ha il permesso packages: write

      - name: Extract Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix=sha-,format=short
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        id: push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: true
          sbom: true

      - name: Generate artifact attestation
        uses: actions/attest-build-provenance@v1
        with:
          subject-name: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          subject-digest: ${{ steps.push.outputs.digest }}
          push-to-registry: true
```

## Relazioni

??? info "GitHub Actions Enterprise"
    Self-hosted runner, Actions Runner Controller (ARC) su Kubernetes, GitHub Advanced Security, governance e audit log.

    **Approfondimento completo →** [GitHub Actions Enterprise](enterprise.md)

??? info "Secret Management"
    Best practice per gestione secrets, HashiCorp Vault integration, rotation automatica.

    **Approfondimento completo →** [Secret Management](../../security/secret-management/_index.md)

## Riferimenti

- [Reusing workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
- [Matrix strategy](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)
- [Using OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Using OIDC with Azure](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)
- [Composite Actions](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action)
- [Environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [Caching dependencies](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
