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
last_updated: 2026-03-28
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

## Troubleshooting

### Scenario 1 — Pipeline bloccata su "Waiting for agent"

**Sintomo:** Il job rimane indefinitamente in stato `Waiting for agent` senza avviarsi.

**Causa:** Nessun agente disponibile nel pool (Microsoft-hosted: limite parallel jobs raggiunto; self-hosted: agente offline o non registrato).

**Soluzione:**
- Per Microsoft-hosted: verificare il limite di parallel jobs nell'organizzazione e attendere o acquistare job aggiuntivi.
- Per self-hosted: verificare che l'agente sia online e nel pool corretto.

```bash
# Verificare stato agenti nel pool via Azure DevOps CLI
az pipelines agent list \
    --pool-id <POOL_ID> \
    --organization https://dev.azure.com/myorg \
    --output table

# Riavviare il servizio agente su Linux
sudo ./svc.sh status
sudo ./svc.sh stop && sudo ./svc.sh start
```

---

### Scenario 2 — Service Connection non autorizzata: "Could not find a linked service"

**Sintomo:** Il pipeline fallisce con errore `Could not find a linked service` o `Service connection not authorized for this pipeline`.

**Causa:** La Service Connection non è autorizzata per la pipeline specifica o il progetto. Può verificarsi dopo una migrazione o con Service Connection a scope limitato.

**Soluzione:**
1. Aprire **Project Settings → Service connections**.
2. Selezionare la Service Connection → **Edit** → **Security**.
3. Abilitare **Grant access permission to all pipelines** oppure aggiungere la pipeline specifica.

```bash
# Verificare le Service Connection disponibili
az devops service-endpoint list \
    --project ecommerce-platform \
    --organization https://dev.azure.com/myorg \
    --output table

# Verificare autorizzazioni su una connection specifica
az devops service-endpoint show \
    --id <ENDPOINT_ID> \
    --project ecommerce-platform \
    --organization https://dev.azure.com/myorg \
    --query "isReady"
```

---

### Scenario 3 — Environment Approval Gate non compare / deployment non richiede approvazione

**Sintomo:** Il deployment in production avviene senza richiedere l'approvazione configurata nel portal.

**Causa:** Il job usa `job:` invece di `deployment:`, oppure il campo `environment` nel YAML non corrisponde esattamente al nome dell'Environment configurato nel portal (case-sensitive).

**Soluzione:**
- Assicurarsi che il job sia di tipo `deployment:` (non `job:`).
- Verificare che il nome nell'`environment:` del YAML corrisponda esattamente all'Environment nel portal.

```yaml
# ERRATO — job normale non usa Environments con approval gates
jobs:
- job: Deploy
  steps:
  - script: echo "deploy"

# CORRETTO — deployment job con environment
jobs:
- deployment: DeployProd
  environment: production        # deve corrispondere esattamente al nome nel portal
  strategy:
    runOnce:
      deploy:
        steps:
        - script: echo "deploy"
```

---

### Scenario 4 — Variable Group non inietta le variabili da Key Vault

**Sintomo:** Le variabili del Variable Group collegato a Key Vault risultano vuote o `$(VAR_NAME)` non viene sostituito.

**Causa:** La Service Connection usata dal Variable Group non ha i permessi `Get` e `List` sui secrets del Key Vault, oppure il Variable Group non è autorizzato per la pipeline.

**Soluzione:**
1. Verificare che la Managed Identity/Service Principal abbia il ruolo **Key Vault Secrets User** sul Key Vault.
2. Aggiornare la lista dei segreti nel Variable Group (pulsante **Refresh**).
3. Autorizzare il Variable Group per la pipeline specifica.

```bash
# Assegnare il ruolo Key Vault Secrets User al Service Principal
az role assignment create \
    --role "Key Vault Secrets User" \
    --assignee $SERVICE_PRINCIPAL_ID \
    --scope /subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.KeyVault/vaults/$KV_NAME

# Verificare i permessi esistenti
az keyvault show \
    --name $KV_NAME \
    --query "properties.accessPolicies" \
    --output table
```

---

## Riferimenti

- [Azure Pipelines Documentation](https://learn.microsoft.com/azure/devops/pipelines/)
- [YAML Schema Reference](https://learn.microsoft.com/azure/devops/pipelines/yaml-schema/)
- [Azure DevOps CLI](https://learn.microsoft.com/azure/devops/cli/)
- [Workload Identity Federation](https://learn.microsoft.com/azure/devops/pipelines/library/connect-to-azure)
- [Self-hosted Agents](https://learn.microsoft.com/azure/devops/pipelines/agents/agents)
- [AZ-400 Study Guide](https://learn.microsoft.com/certifications/exams/az-400)
