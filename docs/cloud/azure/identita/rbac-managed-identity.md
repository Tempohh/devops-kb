---
title: "Azure RBAC & Managed Identity"
slug: rbac-managed-identity
category: cloud
tags: [azure, rbac, role-based-access-control, managed-identity, workload-identity, least-privilege]
search_keywords: [Azure RBAC, Role Based Access Control Azure, ruoli Azure, built-in roles, custom roles, scope Azure RBAC, Managed Identity system assigned user assigned, Workload Identity Federation, service principal vs managed identity, az role assignment, Owner Contributor Reader, Azure role definition, privilegio minimo Azure, ABAC Azure]
parent: cloud/azure/identita/_index
related: [cloud/azure/identita/entra-id, cloud/azure/identita/governance, cloud/azure/security/key-vault]
official_docs: https://learn.microsoft.com/azure/role-based-access-control/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure RBAC & Managed Identity

## Azure RBAC — Role-Based Access Control

**Azure RBAC** controlla chi può fare cosa sulle risorse Azure. Si basa su tre elementi: **security principal** (chi), **role definition** (cosa), **scope** (dove).

```
Security Principal + Role Definition + Scope = Role Assignment

Chi?            Che cosa?         Dove?
────            ─────────         ────
User            Owner             Subscription
Group           Contributor       Resource Group
Service         Reader            Resource
Principal       Custom Role       Management Group
Managed
Identity
```

### Gerarchia degli Scope

```
Management Group
└── Subscription
    └── Resource Group
        └── Resource

I permessi si ereditano verso il basso (padre → figlio).
Un assignment su Subscription vale per tutti i Resource Group e risorse figli.
Un Deny assignment blocca anche i permessi ereditati.
```

---

### Ruoli Built-in Fondamentali

| Ruolo | Permessi | Scope tipico |
|-------|----------|--------------|
| **Owner** | Tutto + gestione accessi (RBAC) | Subscription (limitato) |
| **Contributor** | Crea/modifica risorse ma NON gestisce accessi | Resource Group |
| **Reader** | Solo lettura | Ovunque |
| **User Access Administrator** | Solo gestione RBAC, non risorse | Subscription |

**Ruoli specifici per servizio (selezione):**

| Ruolo | Servizio |
|-------|---------|
| Virtual Machine Contributor | VM — crea/gestisce ma non rete |
| Network Contributor | Networking |
| Storage Blob Data Contributor | Blob Storage — lettura/scrittura dati |
| Storage Blob Data Reader | Blob Storage — solo lettura dati |
| Key Vault Secrets Officer | Key Vault — gestione secrets |
| Key Vault Secrets User | Key Vault — solo lettura secrets |
| AcrPull | Azure Container Registry — pull immagini |
| AcrPush | Azure Container Registry — push immagini |
| AKS Cluster Admin | AKS — accesso cluster-admin |
| Monitoring Reader | Azure Monitor — solo lettura |
| Log Analytics Reader | Log Analytics — solo lettura |

```bash
# Listare tutti i ruoli built-in
az role definition list --query "[?roleType=='BuiltInRole'].{Name:roleName, ID:name}" --output table

# Descrivere un ruolo
az role definition list --name "Contributor" --output json
```

---

### Assegnare Ruoli

```bash
# Assegnare ruolo a utente su Resource Group
az role assignment create \
    --assignee mario.rossi@company.onmicrosoft.com \
    --role "Contributor" \
    --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/myapp-rg

# Assegnare ruolo a gruppo
az role assignment create \
    --assignee-object-id "$(az ad group show --group Platform-Engineers --query id -o tsv)" \
    --assignee-principal-type Group \
    --role "Reader" \
    --scope /subscriptions/$SUBSCRIPTION_ID

# Assegnare ruolo a service principal
az role assignment create \
    --assignee $SERVICE_PRINCIPAL_APP_ID \
    --role "Storage Blob Data Contributor" \
    --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/data-rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount

# Listare assignment su un resource group
az role assignment list \
    --resource-group myapp-rg \
    --include-inherited \
    --query "[].{Principal:principalName, Role:roleDefinitionName, Scope:scope}" \
    --output table

# Rimuovere assignment
az role assignment delete \
    --assignee mario.rossi@company.onmicrosoft.com \
    --role "Contributor" \
    --resource-group myapp-rg
```

---

### Ruoli Custom

Quando i ruoli built-in non sono sufficienti, si creano ruoli custom:

```json
{
  "Name": "Custom VM Operator",
  "Description": "Può avviare, fermare e riavviare VM, ma non crearle o eliminarle",
  "Actions": [
    "Microsoft.Compute/virtualMachines/read",
    "Microsoft.Compute/virtualMachines/start/action",
    "Microsoft.Compute/virtualMachines/powerOff/action",
    "Microsoft.Compute/virtualMachines/restart/action",
    "Microsoft.Compute/virtualMachines/deallocate/action"
  ],
  "NotActions": [],
  "DataActions": [],
  "NotDataActions": [],
  "AssignableScopes": [
    "/subscriptions/SUBSCRIPTION_ID"
  ]
}
```

```bash
# Creare ruolo custom
az role definition create --role-definition @custom-vm-operator.json

# Aggiornare ruolo custom
az role definition update --role-definition @custom-vm-operator-v2.json

# Eliminare ruolo custom
az role definition delete --name "Custom VM Operator"
```

---

## Managed Identity

Le **Managed Identity** eliminano la necessità di gestire credenziali (client secret, certificati) per le risorse Azure che devono accedere ad altri servizi Azure.

```
Senza Managed Identity (problematico):
VM → [usa client_secret salvato in env var] → Key Vault

Con Managed Identity (sicuro):
VM → [token automatico da Entra ID] → Key Vault
```

### System-Assigned vs User-Assigned

| | System-Assigned | User-Assigned |
|---|----------------|---------------|
| Lifecycle | = Risorsa Azure | Indipendente (rimane anche se la risorsa viene eliminata) |
| Condivisione | 1:1 (solo quella risorsa) | 1:N (condivisa tra più risorse) |
| Gestione | Automatica | Manuale |
| Use case | Singola VM/Function/App | VMSS, multiple VMs, ambienti identici |

```bash
# Abilitare System-Assigned Managed Identity su VM
az vm identity assign \
    --resource-group myapp-rg \
    --name myvm

# Ottenere Principal ID della system-assigned MI
PRINCIPAL_ID=$(az vm show \
    --resource-group myapp-rg \
    --name myvm \
    --query "identity.principalId" \
    --output tsv)

# Assegnare ruolo alla MI (Key Vault Secrets User)
az role assignment create \
    --assignee-object-id $PRINCIPAL_ID \
    --assignee-principal-type ServicePrincipal \
    --role "Key Vault Secrets User" \
    --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/myapp-rg/providers/Microsoft.KeyVault/vaults/my-keyvault

# Creare User-Assigned Managed Identity
az identity create \
    --resource-group myapp-rg \
    --name myapp-identity

# Assegnare alla VM
az vm identity assign \
    --resource-group myapp-rg \
    --name myvm \
    --identities /subscriptions/$SUBSCRIPTION_ID/resourceGroups/myapp-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/myapp-identity
```

### Usare Managed Identity nel Codice

```python
# Python — autenticazione con Managed Identity (zero credenziali nel codice)
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient

# DefaultAzureCredential = prova in ordine:
# 1. EnvironmentCredential (env vars)
# 2. WorkloadIdentityCredential (AKS + Workload Identity)
# 3. ManagedIdentityCredential (VM, App Service, Functions)
# 4. AzureCliCredential (sviluppo locale)
# 5. AzurePowerShellCredential (sviluppo locale)
credential = DefaultAzureCredential()

# Key Vault
kv_client = SecretClient(
    vault_url="https://my-keyvault.vault.azure.net/",
    credential=credential
)
secret = kv_client.get_secret("database-password")

# Blob Storage
blob_client = BlobServiceClient(
    account_url="https://mystorageaccount.blob.core.windows.net",
    credential=credential
)
```

```bash
# Dall'interno di una VM con Managed Identity — ottenere token manualmente
# (utile per debug o script bash)
TOKEN=$(curl -s 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/' \
    -H 'Metadata: true' | jq -r '.access_token')

# Usare il token per ARM API
curl -s -H "Authorization: Bearer $TOKEN" \
    "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups?api-version=2021-04-01"
```

---

## Managed Identity su Servizi Azure

```bash
# App Service con System-Assigned MI
az webapp identity assign \
    --resource-group myapp-rg \
    --name mywebapp

# Azure Functions con MI
az functionapp identity assign \
    --resource-group myapp-rg \
    --name myfunctionapp

# AKS — nodo pool con User-Assigned MI
az aks create \
    --resource-group myapp-rg \
    --name myaks \
    --enable-managed-identity \
    --assign-identity /subscriptions/$SUBSCRIPTION_ID/.../myapp-identity

# Container Instances
az container create \
    --resource-group myapp-rg \
    --name mycontainer \
    --image myapp:latest \
    --assign-identity /subscriptions/$SUBSCRIPTION_ID/.../myapp-identity
```

---

## Workload Identity Federation (GitHub Actions / GCP / AWS)

**Workload Identity Federation** permette a identity esterne (GitHub Actions, Kubernetes SA, GCP, AWS) di ottenere token Entra ID senza client secret:

```bash
# Creare federated credential su App Registration per GitHub Actions
az ad app federated-credential create \
    --id $APP_ID \
    --parameters '{
        "name": "github-actions-main",
        "issuer": "https://token.actions.githubusercontent.com",
        "subject": "repo:myorg/myrepo:ref:refs/heads/main",
        "description": "GitHub Actions main branch",
        "audiences": ["api://AzureADTokenExchange"]
    }'

# Per PR:
# "subject": "repo:myorg/myrepo:pull_request"

# Per environment:
# "subject": "repo:myorg/myrepo:environment:production"
```

```yaml
# GitHub Actions — login Azure senza segreti (OIDC)
name: Deploy to Azure
on:
  push:
    branches: [main]

permissions:
  id-token: write      # richiesto per OIDC
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Azure Login (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          # Nessun client secret! Usa OIDC token

      - name: Deploy Bicep
        run: |
          az deployment group create \
            --resource-group myapp-rg \
            --template-file main.bicep
```

---

## Riferimenti

- [Azure RBAC Documentation](https://learn.microsoft.com/azure/role-based-access-control/)
- [Built-in Roles](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles)
- [Managed Identities](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/)
- [Workload Identity Federation](https://learn.microsoft.com/azure/active-directory/develop/workload-identity-federation)
- [Azure Identity SDK](https://learn.microsoft.com/azure/developer/python/sdk/authentication-overview)
