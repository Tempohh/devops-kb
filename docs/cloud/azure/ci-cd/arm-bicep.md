---
title: "ARM Templates & Bicep"
slug: arm-bicep
category: cloud
tags: [azure, bicep, arm, iac, infrastructure-as-code, terraform, deployment-stacks, azure-developer-cli]
search_keywords: [ARM Templates, Azure Resource Manager, Bicep, IaC Azure, Infrastructure as Code Azure, Bicep modules, Bicep registry, what-if deployment, Deployment Stacks, Template Specs, Azure Developer CLI azd, Terraform Azure provider, azurerm, Bicep vs Terraform, arm deployment complete incremental]
parent: cloud/azure/ci-cd/_index
related: [cloud/azure/ci-cd/azure-devops, cloud/azure/identita/rbac-managed-identity]
official_docs: https://learn.microsoft.com/azure/azure-resource-manager/bicep/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# ARM Templates & Bicep

## Confronto IaC Azure

| Strumento | Linguaggio | State | Multi-cloud | Curva apprendimento | Consigliato per |
|-----------|-----------|-------|-------------|---------------------|----------------|
| **Bicep** | DSL Azure-native | Nessuno (ARM gestisce) | No (solo Azure) | Bassa | Team Azure-first, produzione |
| **ARM JSON** | JSON | Nessuno | No | Alta (verbose) | Legacy, generazione automatica |
| **Terraform** | HCL | Stato remoto (tfstate) | Sì | Media | Multi-cloud, team già Terraform |
| **Pulumi** | Python/TS/Go/C# | Stato remoto | Sì | Media-Alta | Developer-centric |
| **Azure Developer CLI** | Bicep + convention | Nessuno | No | Bassa | Sviluppo rapido app |

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
var keyVaultName = 'kv-${appName}-${suffix}'    // max 24 chars
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
  dependsOn: [
    keyVaultAccessPolicy               // KV policy deve esistere prima
  ]
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
resource keyVaultAccessPolicy 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
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

### Parametri File

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
# Validare (dry-run sintattico)
az bicep build --file main.bicep

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
module keyVault 'br/public:avm/res/key-vault/vault:0.6.0' = {
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

**Deployment Stacks** (GA 2024) gestisce il lifecycle completo delle risorse: crea, aggiorna e **elimina** le risorse rimosse dal template (simile a Terraform plan/apply):

```bash
# Creare stack
az stack group create \
    --name production-stack \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json \
    --deny-settings-mode none \          # DenyDelete, DenyWriteAndDelete, none
    --action-on-unmanage deleteAll       # deleteAll, deleteResources, detachAll

# Update stack (rimuove risorse non più nel template)
az stack group update \
    --name production-stack \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @prod.parameters.json

# Eliminare stack (e le risorse gestite)
az stack group delete \
    --name production-stack \
    --resource-group myapp-rg \
    --action-on-unmanage deleteAll
```

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
      version = "~> 3.100"
    }
  }
  backend "azurerm" {
    resource_group_name  = "terraform-state-rg"
    storage_account_name = "tfstatemycompany"
    container_name       = "tfstate"
    key                  = "production/main.tfstate"
  }
}

provider "azurerm" {
  features {}
  use_oidc = true                      # GitHub Actions OIDC (no client secret)
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

## Riferimenti

- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Bicep Playground](https://aka.ms/bicepdemo)
- [Azure Verified Modules (Bicep)](https://azure.github.io/Azure-Verified-Modules/)
- [ARM Template Reference](https://learn.microsoft.com/azure/templates/)
- [Deployment Stacks](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Terraform Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
