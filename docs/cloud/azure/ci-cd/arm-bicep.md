---
title: "ARM Templates & Bicep"
slug: arm-bicep
category: cloud
tags: [azure, bicep, arm, iac, infrastructure-as-code, terraform, deployment-stacks, azure-developer-cli]
search_keywords: [ARM Templates, Azure Resource Manager, Bicep, IaC Azure, Infrastructure as Code Azure, Bicep modules, Bicep registry, what-if deployment, Deployment Stacks, Template Specs, Azure Developer CLI azd, Terraform Azure provider, azurerm, Bicep vs Terraform, arm deployment complete incremental]
parent: cloud/azure/ci-cd/_index
related: [cloud/azure/ci-cd/azure-devops, cloud/azure/identita/rbac-managed-identity]
official_docs: https://learn.microsoft.com/azure/azure-resource-manager/bicep/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# ARM Templates & Bicep

**ARM** (Azure Resource Manager) è il layer di controllo di Azure: ogni deploy, da portale, CLI o IaC (*Infrastructure as Code*), diventa una chiamata ARM. Un **ARM template** è il formato JSON dichiarativo accettato da ARM; **Bicep** è un DSL (*Domain-Specific Language*) che viene transpilato in ARM JSON prima del deploy. Perché esiste: il JSON è verboso e difficile da leggere/modularizzare. Come funziona: `az deployment` compila il `.bicep` in JSON e lo invia ad ARM, che calcola le dipendenze e crea le risorse in parallelo. Nessun tfstate da gestire: lo stato "vero" è quello delle risorse in Azure.

## Confronto IaC Azure

| Strumento | Linguaggio | State | Multi-cloud | Curva apprendimento | Consigliato per |
|-----------|-----------|-------|-------------|---------------------|----------------|
| **Bicep** | DSL Azure-native | Nessuno (ARM gestisce) | No (solo Azure) | Bassa | Team Azure-first, produzione |
| **ARM JSON** | JSON | Nessuno | No | Alta (verbose) | Legacy, generazione automatica |
| **Terraform** | HCL | Stato remoto (tfstate) | Sì | Media | Multi-cloud, team già Terraform |
| **Pulumi** | Python/TS/Go/C# | Stato remoto | Sì | Media-Alta | Developer-centric |
| **Azure Developer CLI** | Bicep (o Terraform) + convention | Nessuno (solo config ambiente locale in `.azure/`) | No | Bassa | Sviluppo rapido app |

!!! note "Terraform vs OpenTofu"
    OpenTofu è il fork open source di Terraform (Linux Foundation) e usa lo stesso provider `azurerm` e gli stessi backend: gli esempi Terraform di questa pagina valgono per entrambi.

---

## Bicep

**Bicep** è il linguaggio DSL nativo di Azure per Infrastructure as Code. Transpila in ARM JSON ma ha sintassi molto più leggibile. È la scelta raccomandata da Microsoft per IaC su Azure.

### Sintassi Completa — Esempio App Service + SQL

```bicep
// main.bicep

// ── Parametri ─────────────────────────────────────────────────────────────
@description('Nome dell ambiente di deploy')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Region Azure per le risorse')
param location string = resourceGroup().location

@description('Nome applicazione (deve essere globalmente unico)')
@minLength(3)
@maxLength(24)
param appName string

@description('SKU App Service Plan')
param appServiceSku string = environment == 'prod' ? 'P1v3' : 'B1'

@secure()                             // marcato @secure = non loggato/stampato
@description('Password admin database')
param sqlAdminPassword string

// ── Variabili ─────────────────────────────────────────────────────────────
var suffix = uniqueString(resourceGroup().id)
var appServicePlanName = 'asp-${appName}-${environment}'
var webAppName = '${appName}-${environment}-${suffix}'
var sqlServerName = 'sql-${appName}-${environment}-${suffix}'
var sqlDbName = '${appName}-db'
var keyVaultName = take('kv-${appName}-${suffix}', 24)    // max 24 chars: take() evita l'overflow
var tags = {
  Environment: environment
  Application: appName
  ManagedBy: 'Bicep'
}

// ── App Service Plan ───────────────────────────────────────────────────────
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: appServiceSku
  }
  properties: {
    reserved: true                    // Linux
  }
}

// ── Web App ────────────────────────────────────────────────────────────────
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'            // Managed Identity per accesso Key Vault
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          // Key Vault reference — nessuna credenziale in chiaro
          name: 'DB_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault::dbConnectionString.properties.secretUri})'
        }
      ]
    }
  }
  // NIENTE dependsOn su keyVaultRoleAssignment: la role assignment usa
  // webApp.identity.principalId, quindi dipende già da webApp → sarebbe una dipendenza circolare.
  // I Key Vault reference vengono risolti a runtime da App Service, non al deploy.
}

// ── Deployment Slot (staging) — solo prod ─────────────────────────────────
resource stagingSlot 'Microsoft.Web/sites/slots@2023-12-01' = if (environment == 'prod') {
  parent: webApp
  name: 'staging'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
  }
}

// ── Azure SQL Server ───────────────────────────────────────────────────────
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: sqlServerName
  location: location
  tags: tags
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'   // solo Private Endpoint
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: sqlDbName
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'GP_Gen5_2' : 'Basic'
    tier: environment == 'prod' ? 'GeneralPurpose' : 'Basic'
  }
  properties: {
    zoneRedundant: environment == 'prod'
    requestedBackupStorageRedundancy: environment == 'prod' ? 'Geo' : 'Local'
  }
}

// ── Key Vault ──────────────────────────────────────────────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true      // RBAC invece di access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }

  // Nested resource: secret
  resource dbConnectionString 'secrets' = {
    name: 'db-connection-string'
    properties: {
      value: 'Server=${sqlServer.properties.fullyQualifiedDomainName};Database=${sqlDbName};...'
    }
  }
}

// ── RBAC: Web App → Key Vault ─────────────────────────────────────────────
resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, webApp.id, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'  // Key Vault Secrets User
    )
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Output ─────────────────────────────────────────────────────────────────
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output webAppPrincipalId string = webApp.identity.principalId
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output keyVaultName string = keyVault.name
```

!!! warning "Rete privata"
    Con `publicNetworkAccess: 'Disabled'` su SQL e Key Vault l'esempio **non è funzionante end-to-end**: servono Private Endpoint + Private DNS Zone e VNet Integration sulla Web App (non mostrati). Senza, l'app non risolve i Key Vault reference e non raggiunge il DB. Il secret con la connection string va inoltre preferibilmente sostituito da autenticazione Entra ID (managed identity) verso SQL.

### Parametri File

Formato nativo consigliato: **`.bicepparam`** (GA da Bicep 0.18), tipizzato e validato contro il template tramite `using`; il JSON sotto resta valido e necessario per ARM puro.

```bicep
// prod.bicepparam
using './main.bicep'

param environment = 'prod'
param appName = 'ecommerce'
param appServiceSku = 'P2v3'
// secret letto da Key Vault a deploy-time (il vault deve avere enabledForTemplateDeployment)
param sqlAdminPassword = az.getSecret('<SUB_ID>', 'secrets-rg', 'deploy-secrets', 'sql-admin-password')
```

Equivalente in JSON:

```json
// prod.parameters.json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environment": { "value": "prod" },
    "appName": { "value": "ecommerce" },
    "appServiceSku": { "value": "P2v3" },
    "sqlAdminPassword": {
      "reference": {
        "keyVault": {
          "id": "/subscriptions/XXXX/resourceGroups/secrets-rg/providers/Microsoft.KeyVault/vaults/deploy-secrets"
        },
        "secretName": "sql-admin-password"
      }
    }
  }
}
```

---

### Deploy Bicep

```bash
# Compilare/validare sintassi (genera main.json, non contatta Azure)
az bicep build --file main.bicep

# Validazione lato ARM (controlla anche parametri e quote, senza creare nulla)
az deployment group validate \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json

# What-if — mostra cosa cambierà SENZA applicare
az deployment group what-if \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json

# Deploy effettivo
az deployment group create \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json \
    --name "deploy-$(date +%Y%m%d-%H%M%S)"

# Controllare output del deployment
az deployment group show \
    --resource-group myapp-rg \
    --name deploy-20260226-143000 \
    --query properties.outputs

# Deploy a livello Subscription (es. creare Resource Groups)
az deployment sub create \
    --location italynorth \
    --template-file subscription.bicep

# Deploy a livello Management Group (es. policy)
az deployment mg create \
    --management-group-id mg-production \
    --location italynorth \
    --template-file mg-policy.bicep
```

---

### Moduli Bicep

```bicep
// modules/app-service.bicep — modulo riutilizzabile
@description('Nome App Service')
param name string
param location string
param planId string
param environmentVars object = {}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'            // necessario per l'output principalId
  }
  properties: {
    serverFarmId: planId
    siteConfig: {
      appSettings: [for key in objectKeys(environmentVars): {
        name: key
        value: environmentVars[key]
      }]
    }
  }
}

output appUrl string = 'https://${webApp.properties.defaultHostName}'
output principalId string = webApp.identity.principalId
```

```bicep
// main.bicep — usa il modulo
module frontendApp './modules/app-service.bicep' = {
  name: 'frontendDeploy'
  params: {
    name: 'myapp-frontend'
    location: location
    planId: appServicePlan.id
    environmentVars: {
      API_URL: 'https://api.myapp.com'
      ENVIRONMENT: environment
    }
  }
}

output frontendUrl string = frontendApp.outputs.appUrl
```

### Bicep Registry (Moduli Condivisi su ACR)

```bash
# Pubblicare modulo su ACR
az bicep publish \
    --file modules/app-service.bicep \
    --target br:myacr.azurecr.io/bicep/app-service:v1.0

# Usare modulo da registry
# in main.bicep:
module webApp 'br:myacr.azurecr.io/bicep/app-service:v1.0' = {
  name: 'webAppDeploy'
  params: { ... }
}

# Public Bicep Registry (Microsoft)
# (AVM = Azure Verified Modules; fissare sempre una versione esistente, vedi tag nel registry)
module keyVault 'br/public:avm/res/key-vault/vault:<VERSIONE>' = {
  name: 'keyVaultDeploy'
  params: { ... }
}
```

---

## ARM Templates (JSON)

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "storageAccountName": {
      "type": "string",
      "minLength": 3,
      "maxLength": 24
    }
  },
  "variables": {
    "sku": "Standard_LRS"
  },
  "resources": [
    {
      "type": "Microsoft.Storage/storageAccounts",
      "apiVersion": "2023-01-01",
      "name": "[parameters('storageAccountName')]",
      "location": "[resourceGroup().location]",
      "sku": {
        "name": "[variables('sku')]"
      },
      "kind": "StorageV2",
      "properties": {
        "minimumTlsVersion": "TLS1_2",
        "allowBlobPublicAccess": false,
        "supportsHttpsTrafficOnly": true
      }
    }
  ],
  "outputs": {
    "storageEndpoint": {
      "type": "string",
      "value": "[reference(parameters('storageAccountName')).primaryEndpoints.blob]"
    }
  }
}
```

**Deployment modes:**
- `--mode Incremental` (default): aggiunge/modifica risorse, non elimina quelle assenti nel template
- `--mode Complete`: elimina TUTTE le risorse nel Resource Group non presenti nel template — **usare con cautela**

---

## Deployment Stacks

**Deployment Stacks** (GA 2024) trattano il deployment come un'unità gestita: ARM ricorda quali risorse appartengono allo stack e, al redeploy, **elimina o scollega** quelle rimosse dal template (`--action-on-unmanage`). Perché: il deploy Bicep standard è incrementale e lascia orfane le risorse tolte dal codice; la modalità Complete le elimina ma agisce sull'intero RG ed è rischiosa. Differenza da Terraform: non c'è file di stato (lo stack vive in ARM) e non esiste un `plan` equivalente (il `what-if` non è supportato sugli stack).

```bash
# Creare stack (lo stesso comando aggiorna uno stack esistente; non c'è "az stack group update")
# --deny-settings-mode: none | denyDelete | denyWriteAndDelete
# --action-on-unmanage: detachAll | deleteResources | deleteAll
az stack group create \
    --name production-stack \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json \
    --deny-settings-mode denyDelete \
    --action-on-unmanage deleteResources

# Eliminare stack (e le risorse gestite)
az stack group delete \
    --name production-stack \
    --resource-group myapp-rg \
    --action-on-unmanage deleteAll
```

!!! warning "Attenzione"
    `deleteAll` elimina anche i resource group gestiti dallo stack. Con dati stateful usare `detachAll` o `deleteResources` e `--deny-settings-mode denyDelete` per proteggere le risorse da cancellazioni fuori dallo stack.

---

## Azure Developer CLI (azd)

**azd** è il CLI developer-friendly per applicazioni Azure: combina IaC (Bicep) + deployment applicativo + CI/CD setup in un unico workflow:

```bash
# Installare azd
winget install microsoft.azd    # Windows
brew tap azure/azd && brew install azd    # macOS

# Inizializzare progetto (da template o da codice esistente)
azd init --template todo-nodejs-mongo    # da template galleria
azd init                                  # da progetto esistente (analizza codice)

# Struttura generata:
# ├── azure.yaml          # definizione servizi
# ├── infra/
# │   ├── main.bicep
# │   ├── main.parameters.json
# │   └── modules/
# └── src/

# Provision infrastruttura + Deploy applicazione
azd up                          # = azd provision + azd deploy

# Solo infrastruttura
azd provision

# Solo deploy applicazione
azd deploy

# Configurare pipeline CI/CD automaticamente
azd pipeline config             # GitHub Actions o Azure DevOps

# Eliminare tutto (infra + risorse)
azd down --force --purge

# Variabili e secrets
azd env set MY_VAR value
azd env get-values
```

**`azure.yaml` esempio:**
```yaml
name: ecommerce-platform
metadata:
  template: todo-nodejs@0.0.1-beta
services:
  api:
    project: ./src/api
    language: python
    host: appservice
  web:
    project: ./src/web
    language: js
    host: staticwebapp
hooks:
  predeploy:
    shell: sh
    run: ./scripts/seed-db.sh
```

---

## Terraform su Azure

```hcl
# main.tf
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
  backend "azurerm" {
    resource_group_name  = "terraform-state-rg"
    storage_account_name = "tfstatemycompany"
    container_name       = "tfstate"
    key                  = "production/main.tfstate"
    use_oidc             = true        # backend: OIDC (Entra ID) invece di access key
    use_azuread_auth     = true
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id   # obbligatorio da azurerm 4.0
  use_oidc        = true                  # GitHub Actions OIDC (no client secret)
}

resource "azurerm_resource_group" "main" {
  name     = "myapp-${var.environment}-rg"
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_service_plan" "main" {
  name                = "asp-myapp-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.environment == "prod" ? "P1v3" : "B1"
}
```

```bash
# Workflow Terraform
terraform init
terraform plan -var-file=prod.tfvars -out=tfplan
terraform apply tfplan
terraform destroy
```

---

## Troubleshooting

### Scenario 1 — Deployment fallisce con "Conflict" su risorsa esistente

**Sintomo:** `az deployment group create` restituisce errore `409 Conflict` su una risorsa già presente nel Resource Group.

**Causa:** La risorsa esiste ma con proprietà incompatibili (es. SKU non modificabile dopo creazione, o nome già preso da altra subscription).

**Soluzione:** Verificare lo stato della risorsa con `az resource show`, usare `what-if` per identificare i conflitti prima del deploy. Per risorse non modificabili, eliminare e ricreare (attenzione alla perdita di dati su risorse stateful).

```bash
# Identificare la risorsa in conflitto
az resource show \
    --ids /subscriptions/<SUB>/resourceGroups/<RG>/providers/Microsoft.Web/serverfarms/<NAME>

# What-if per vedere differenze senza applicare
az deployment group what-if \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json

# Se necessario: eliminare e ricreare la risorsa problematica
az resource delete \
    --ids /subscriptions/<SUB>/resourceGroups/<RG>/providers/Microsoft.Web/serverfarms/<NAME>
```

---

### Scenario 2 — Errore "BCP057: The name does not exist in the current context"

**Sintomo:** `az bicep build` fallisce con errore `BCP057` riferito a un simbolo non trovato (es. variabile, resource, modulo).

**Causa:** Typo nel nome simbolico (case-sensitive), simbolo definito in un altro file/modulo non importato, o accesso a una risorsa figlia fuori scope. L'ordine delle dichiarazioni **non** conta: Bicep costruisce il grafo delle dipendenze dai riferimenti, quindi `dependsOn` esplicito serve solo per dipendenze non espresse da un riferimento (e mai per BCP057).

**Soluzione:** Verificare il nome esatto del simbolo, che sia dichiarato nello stesso file (o esposto come `output` del modulo), e che `param`/`var` esistano.

```bash
# Compilare e vedere tutti gli errori
az bicep build --file main.bicep

# Linting con regole estese
az bicep lint --file main.bicep

# Installare/aggiornare Bicep CLI
az bicep upgrade
az bicep version
```

---

### Scenario 3 — What-if mostra "NoChange" ma le risorse non vengono create

**Sintomo:** Il comando `what-if` non mostra modifiche, ma le risorse attese non esistono nel Resource Group.

**Causa:** Spesso dovuto a condizioni `if (...)` nel template che valutano a `false` per i parametri forniti, oppure il deployment punta al Resource Group sbagliato.

**Soluzione:** Verificare i parametri passati, controllare le condizioni nei blocchi `if`, e confermare il Resource Group target.

```bash
# Verificare che il Resource Group sia quello corretto
az group show --name myapp-rg

# Controllare i parametri effettivi del deployment
az deployment group show \
    --resource-group myapp-rg \
    --name deploy-20260226-143000 \
    --query properties.parameters

# Elencare tutte le risorse nel RG per confronto
az resource list --resource-group myapp-rg --output table
```

---

### Scenario 4 — Terraform: "Error acquiring the state lock"

**Sintomo:** `terraform plan` o `terraform apply` fallisce con `Error acquiring the state lock` su Azure Blob Storage.

**Causa:** Il backend `azurerm` implementa il lock come **lease sul blob dello state stesso** (`production/main.tfstate`), non come blob `.lock` separato. Un processo terminato in modo anomalo, o una pipeline concorrente, lascia il lease attivo.

**Soluzione:** Verificare che non ci siano operazioni Terraform attive in altre pipeline, poi sbloccare.

```bash
# Verificare lo stato del lease sul blob di state
az storage blob show \
    --account-name tfstatemycompany \
    --container-name tfstate \
    --name "production/main.tfstate" \
    --auth-mode login \
    --query "properties.lease"

# Forzare sblocco (solo se si è certi che nessun altro processo è attivo)
terraform force-unlock <LOCK_ID>      # LOCK_ID è riportato nel messaggio di errore

# In alternativa: rompere il lease direttamente
az storage blob lease break \
    --account-name tfstatemycompany \
    --container-name tfstate \
    --blob-name "production/main.tfstate" \
    --auth-mode login
```

!!! danger "Non eliminare il blob"
    Cancellare `main.tfstate` distrugge lo state: Terraform perderebbe traccia di tutte le risorse gestite.

---

## Riferimenti

- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Bicep Playground](https://aka.ms/bicepdemo)
- [Azure Verified Modules (Bicep)](https://azure.github.io/Azure-Verified-Modules/)
- [ARM Template Reference](https://learn.microsoft.com/azure/templates/)
- [Deployment Stacks](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Terraform Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
