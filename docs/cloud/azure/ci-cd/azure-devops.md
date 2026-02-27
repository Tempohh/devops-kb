---
title: "Azure DevOps"
slug: azure-devops
category: cloud
tags: [azure, devops, pipelines, repos, artifacts, boards, yaml-pipeline, service-connection, environments, variable-groups]
search_keywords: [Azure DevOps, Azure Pipelines, Azure Repos, Azure Artifacts, YAML pipeline Azure, multi-stage pipeline, deployment environment approval, variable group, service connection, release gate, self-hosted agent, parallel jobs, AZ-400 DevOps certification, Azure Boards, sprint, backlog, Kanban]
parent: cloud/azure/ci-cd/_index
related: [cloud/azure/ci-cd/arm-bicep, cloud/azure/identita/rbac-managed-identity, cloud/azure/compute/aks-containers]
official_docs: https://learn.microsoft.com/azure/devops/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure DevOps

**Azure DevOps** è la piattaforma Microsoft per DevOps end-to-end: gestione progetto, repository Git, CI/CD, testing e package management.

## Servizi Azure DevOps

| Servizio | Funzione | Alternativa GitHub |
|---------|----------|-------------------|
| **Boards** | Project management (Epic/Feature/Story/Task), sprint, Kanban | GitHub Projects |
| **Repos** | Git repositories privati, pull request, code review | GitHub Repos |
| **Pipelines** | CI/CD YAML, multi-stage, self-hosted agents | GitHub Actions |
| **Test Plans** | Test management, test case tracking, load testing | GitHub (parziale) |
| **Artifacts** | Feed privati npm/NuGet/Maven/Python/Universal | GitHub Packages |

**Gerarchia:**
```
Organization (es. contoso.visualstudio.com)
└── Project (es. ecommerce-platform)
    ├── Repos (multiple)
    ├── Pipelines
    ├── Boards
    ├── Test Plans
    └── Artifacts Feeds
```

---

## Azure Pipelines — Pipeline YAML Multi-Stage

### Struttura Completa

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main
      - release/*
  paths:
    exclude:
      - docs/**
      - '*.md'

pr:
  branches:
    include:
      - main
  drafts: false

# Pool di default per tutti i job
pool:
  vmImage: ubuntu-latest     # ubuntu-latest, windows-latest, macos-latest

variables:
  - group: production-secrets          # Variable Group (vedi sotto)
  - name: imageRepository
    value: myapp
  - name: containerRegistry
    value: myacr.azurecr.io
  - name: tag
    value: $(Build.BuildId)

stages:

# ─── STAGE: Build & Test ──────────────────────────────────────────────────
- stage: Build
  displayName: 'Build & Test'
  jobs:
  - job: BuildAndTest
    displayName: 'Build, Test, Push Image'
    steps:
    - checkout: self
      fetchDepth: 0                    # full history per SonarQube/git depth

    - task: UsePythonVersion@0
      inputs:
        versionSpec: '3.12'
        addToPath: true

    - script: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
      displayName: 'Install dependencies'

    - script: |
        pytest tests/ \
          --junitxml=junit/test-results.xml \
          --cov=src \
          --cov-report=xml:coverage.xml
      displayName: 'Run tests'

    - task: PublishTestResults@2
      condition: succeededOrFailed()
      inputs:
        testResultsFormat: JUnit
        testResultsFiles: 'junit/test-results.xml'

    - task: PublishCodeCoverageResults@1
      inputs:
        codeCoverageTool: Cobertura
        summaryFileLocation: coverage.xml

    - task: Docker@2
      displayName: 'Build & Push Docker image'
      inputs:
        command: buildAndPush
        repository: $(imageRepository)
        dockerfile: Dockerfile
        containerRegistry: acr-service-connection      # Service Connection
        tags: |
          $(tag)
          latest

    - task: PublishPipelineArtifact@1
      inputs:
        targetPath: k8s/
        artifact: manifests

# ─── STAGE: Deploy Staging ────────────────────────────────────────────────
- stage: DeployStaging
  displayName: 'Deploy to Staging'
  dependsOn: Build
  condition: succeeded()
  variables:
    - group: staging-vars
  jobs:
  - deployment: DeployStaging
    displayName: 'Deploy to AKS Staging'
    environment: 'staging.default'       # Environment "staging", namespace "default"
    strategy:
      runOnce:
        deploy:
          steps:
          - download: current
            artifact: manifests

          - task: KubernetesManifest@0
            displayName: 'Deploy to AKS'
            inputs:
              action: deploy
              kubernetesServiceConnection: aks-staging-connection
              namespace: default
              manifests: |
                $(Pipeline.Workspace)/manifests/deployment.yaml
                $(Pipeline.Workspace)/manifests/service.yaml
              containers: |
                $(containerRegistry)/$(imageRepository):$(tag)

          - task: AzureAppServiceManage@0
            displayName: 'Warm up staging slot'
            inputs:
              azureSubscription: azure-service-connection
              Action: Start Azure App Service
              WebAppName: myapp-staging

# ─── STAGE: Integration Tests ─────────────────────────────────────────────
- stage: IntegrationTests
  displayName: 'Integration Tests'
  dependsOn: DeployStaging
  jobs:
  - job: RunIntegrationTests
    steps:
    - script: |
        pip install pytest httpx
        pytest tests/integration/ --base-url="https://myapp-staging.azurewebsites.net"
      displayName: 'Run integration tests'

# ─── STAGE: Deploy Production ─────────────────────────────────────────────
- stage: DeployProduction
  displayName: 'Deploy to Production'
  dependsOn: IntegrationTests
  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
  jobs:
  - deployment: DeployProduction
    displayName: 'Deploy to Production'
    environment: production              # ha approval gate configurato nel portal
    strategy:
      runOnce:
        deploy:
          steps:
          - task: AzureWebApp@1
            inputs:
              azureSubscription: azure-service-connection
              appType: webAppLinux
              appName: myapp-production
              deployToSlotOrASE: true
              resourceGroupName: myapp-rg
              slotName: staging           # deploy su slot staging

          - task: AzureAppServiceManage@0
            displayName: 'Swap slots (staging → production)'
            inputs:
              azureSubscription: azure-service-connection
              Action: Swap Slots
              WebAppName: myapp-production
              ResourceGroupName: myapp-rg
              SourceSlot: staging
```

---

## Service Connections

Le **Service Connection** collegano Azure DevOps a Azure o altri sistemi esterni:

```bash
# Creare Service Connection ARM con OIDC (Workload Identity Federation — no secret)
# Via Azure DevOps CLI
az devops service-endpoint azurerm create \
    --azure-rm-service-principal-id $APP_ID \
    --azure-rm-subscription-id $SUBSCRIPTION_ID \
    --azure-rm-subscription-name "Production" \
    --azure-rm-tenant-id $TENANT_ID \
    --name azure-service-connection
```

**Tipi di Service Connection:**
- **Azure Resource Manager** — accesso Azure (Managed Identity/OIDC/Service Principal)
- **Docker Registry / ACR** — push/pull immagini
- **Kubernetes** — deploy su AKS (kubeconfig o Service Account)
- **GitHub** — checkout da GitHub Repos
- **NuGet/npm/Maven** — feed Artifacts esterni
- **SSH / Generic** — sistemi custom

**Best practice:** usare **Workload Identity Federation (OIDC)** — nessun secret/certificato da ruotare.

---

## Environments e Approval Gates

Gli **Environments** in Azure Pipelines gestiscono deployment con policy di sicurezza:

```bash
# Creare environment via CLI
az devops environment create \
    --name production \
    --project ecommerce-platform
```

**Configurazione approvazioni (via portal Azure DevOps → Environments → Approvals and checks):**

| Check | Descrizione |
|-------|-------------|
| **Approvals** | Reviewer manuale (1 o più persone, timeout, istruzioni) |
| **Required template** | Il pipeline deve estendere un template approvato |
| **Evaluate artifact** | Verifica policy su container image (vulnerability, compliance) |
| **Business hours** | Deploy solo in orari specificati |
| **Azure Monitor alerts** | Blocca se ci sono alert attivi |
| **Query Work Items** | Verifica che non ci siano bug aperti critici |
| **Invoke Azure Function** | Gate custom tramite Function |
| **Invoke REST API** | Gate custom tramite API |

---

## Variable Groups e Key Vault Integration

```bash
# Creare Variable Group collegato a Key Vault
az pipelines variable-group create \
    --name production-secrets \
    --authorize true \
    --variables placeholder=placeholder \  # variabile placeholder iniziale
    --project ecommerce-platform

# Collegare Key Vault al Variable Group (tramite portal DevOps o API)
# Le variabili del KV sono iniettate come variabili sicure nel pipeline
```

```yaml
# Usare Variable Group nel pipeline
variables:
  - group: production-secrets          # secrets da Key Vault
  - group: production-config           # variabili non-secret
  - name: myLocalVar
    value: localvalue

steps:
  - script: echo "DB host is $(DB_HOST)"    # variabile dal group
    env:
      DB_PASSWORD: $(DB_PASSWORD)           # variabile secret (mascherata nei log)
```

---

## Template Riutilizzabili

```yaml
# templates/deploy-webapp.yml (template condiviso)
parameters:
  - name: appName
    type: string
  - name: environment
    type: string
  - name: azureSubscription
    type: string

steps:
  - task: AzureWebApp@1
    displayName: 'Deploy ${{ parameters.appName }} to ${{ parameters.environment }}'
    inputs:
      azureSubscription: ${{ parameters.azureSubscription }}
      appName: ${{ parameters.appName }}-${{ parameters.environment }}

---
# Pipeline che usa il template
stages:
- stage: Deploy
  jobs:
  - deployment: Deploy
    environment: production
    strategy:
      runOnce:
        deploy:
          steps:
          - template: templates/deploy-webapp.yml
            parameters:
              appName: myapp
              environment: production
              azureSubscription: azure-service-connection
```

---

## Agenti — Microsoft Hosted vs Self-Hosted

### Microsoft-Hosted Agents

| Pool | OS | Pre-installed |
|------|----|----|
| `ubuntu-latest` | Ubuntu 22.04 | Docker, Python, Node, .NET, Azure CLI |
| `windows-latest` | Windows 2022 | Visual Studio, .NET, Node, Azure CLI |
| `macos-latest` | macOS 14 | Xcode, Python, Node |

**Limiti free:** 1800 minuti/mese per organization. Job paralleli: 1 free, $40/mese per job aggiuntivo.

### Self-Hosted Agent

```bash
# Download e configurazione agente su VM Linux
mkdir myagent && cd myagent
wget https://vstsagentpackage.azureedge.net/agent/3.x.x/vsts-agent-linux-x64-3.x.x.tar.gz
tar zxvf vsts-agent-linux-x64-*.tar.gz

./config.sh \
    --url https://dev.azure.com/myorganization \
    --auth pat \
    --token $PAT_TOKEN \
    --pool MySelfHostedPool \
    --agent myagent-01 \
    --acceptTeeEula

# Installare come servizio
sudo ./svc.sh install
sudo ./svc.sh start
```

**Vantaggi self-hosted:** accesso a rete privata, tooling custom, nessun limite di minuti, GPU per ML.

---

## Azure Artifacts

```bash
# Creare feed
az artifacts universal publish \
    --organization https://dev.azure.com/myorg \
    --project ecommerce-platform \
    --scope project \
    --feed myapp-packages \
    --name myapp-sdk \
    --version 1.2.3 \
    --path ./dist

# Configurare pip per usare feed privato
pip install keyring artifacts-keyring
pip config set global.index-url \
    https://pkgs.dev.azure.com/myorg/ecommerce-platform/_packaging/myapp-packages/pypi/simple/
```

---

## Riferimenti

- [Azure Pipelines Documentation](https://learn.microsoft.com/azure/devops/pipelines/)
- [YAML Schema Reference](https://learn.microsoft.com/azure/devops/pipelines/yaml-schema/)
- [Azure DevOps CLI](https://learn.microsoft.com/azure/devops/cli/)
- [Workload Identity Federation](https://learn.microsoft.com/azure/devops/pipelines/library/connect-to-azure)
- [Self-hosted Agents](https://learn.microsoft.com/azure/devops/pipelines/agents/agents)
- [AZ-400 Study Guide](https://learn.microsoft.com/certifications/exams/az-400)
