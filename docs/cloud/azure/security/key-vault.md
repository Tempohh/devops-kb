---
title: "Azure Key Vault"
slug: key-vault-azure
category: cloud
tags: [azure, key-vault, secrets, keys, certificates, managed-hsm, rbac-key-vault]
search_keywords: [Azure Key Vault, segreti password connection string, chiavi RSA EC crittografia, certificati X.509 TLS, Managed HSM FIPS 140-2, RBAC Key Vault Secrets User, soft delete purge protection, Key Vault Reference App Settings, EventGrid rotation automatica, DefaultAzureCredential Python SDK]
parent: cloud/azure/security/_index
related: [cloud/azure/compute/app-service-functions, cloud/azure/compute/aks-containers, cloud/azure/database/azure-sql]
official_docs: https://learn.microsoft.com/azure/key-vault/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Azure Key Vault

## Panoramica

Azure Key Vault è il servizio centralizzato per la gestione sicura di segreti, chiavi crittografiche e certificati. Elimina la necessità di hardcodare credenziali nelle applicazioni, permettendo l'accesso tramite identità managed (Managed Identity, Service Principal) con audit trail completo.

**Tre tipi di oggetti:**
- **Secrets**: dati sensibili generici (password, connection string, API key, token)
- **Keys**: chiavi crittografiche RSA/EC per firme, crittografia, decriptazione
- **Certificates**: certificati X.509 con gestione ciclo di vita automatica (auto-renew)

## SKU e Livelli

| SKU | Protezione Chiavi | FIPS Level | Use Case |
|---|---|---|---|
| **Standard** | Software-protected | FIPS 140-2 Level 1 | La maggior parte dei workload |
| **Premium** | HSM-protected (opzione) | FIPS 140-2 Level 2 | Chiavi critiche, compliance normativa |
| **Managed HSM** | Dedicated HSM | FIPS 140-2 Level 3 | Istituzioni finanziarie, settore regolamentato, massima sicurezza |

## Creare Key Vault

```bash
RG="rg-security-prod"
LOCATION="westeurope"
KV_NAME="kv-prod-myapp-2026"  # Globalmente unico, 3-24 char

# Creare Key Vault con RBAC (approccio preferito su access policies)
az keyvault create \
  --resource-group $RG \
  --name $KV_NAME \
  --location $LOCATION \
  --sku Standard \
  --enable-rbac-authorization true \
  --enable-soft-delete true \
  --soft-delete-retention-days 90 \
  --enable-purge-protection true \
  --public-network-access Disabled

# Per chiavi HSM-protected (Premium)
az keyvault create \
  --resource-group $RG \
  --name kv-premium-prod \
  --location $LOCATION \
  --sku Premium \
  --enable-rbac-authorization true \
  --enable-purge-protection true
```

!!! warning "Purge Protection Irreversibile"
    Una volta abilitata la purge protection (`--enable-purge-protection true`), non può essere disabilitata. I segreti eliminati (soft-delete) non possono essere eliminati permanentemente prima dei 90 giorni di retention. Abilita sempre in produzione per proteggere da eliminazioni accidentali o maligne.

## Gestione Segreti

```bash
# Aggiungere un segreto
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "db-connection-string" \
  --value "Server=sqlsrv-prod-2026.database.windows.net;Database=myapp;Authentication=Active Directory MSI;" \
  --expires "2027-01-01T00:00:00Z" \
  --content-type "connection-string"

# Aggiornare un segreto (crea nuova versione, la vecchia rimane)
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "db-connection-string" \
  --value "NEW_CONNECTION_STRING"

# Leggere un segreto
az keyvault secret show \
  --vault-name $KV_NAME \
  --name "db-connection-string" \
  --query "value" -o tsv

# Listare tutti i segreti
az keyvault secret list \
  --vault-name $KV_NAME \
  --output table

# Listare versioni di un segreto
az keyvault secret list-versions \
  --vault-name $KV_NAME \
  --name "db-connection-string" \
  --output table

# Disabilitare versione specifica (soft-delete)
az keyvault secret set-attributes \
  --vault-name $KV_NAME \
  --name "db-connection-string" \
  --version VERSION_ID \
  --enabled false

# Eliminare segreto (soft-delete, recuperabile per 90 giorni)
az keyvault secret delete \
  --vault-name $KV_NAME \
  --name "old-api-key"

# Recuperare segreto eliminato
az keyvault secret recover \
  --vault-name $KV_NAME \
  --name "old-api-key"
```

## Gestione Chiavi Crittografiche

```bash
# Creare chiave RSA 4096-bit (software-protected)
az keyvault key create \
  --vault-name $KV_NAME \
  --name "signing-key" \
  --kty RSA \
  --size 4096 \
  --ops sign verify encrypt decrypt wrapKey unwrapKey \
  --expires "2027-01-01T00:00:00Z"

# Creare chiave EC per ECDSA (elliptic curve)
az keyvault key create \
  --vault-name $KV_NAME \
  --name "jwt-signing-ec" \
  --kty EC \
  --curve P-384 \
  --ops sign verify

# Creare chiave HSM-protected (Premium vault)
az keyvault key create \
  --vault-name kv-premium-prod \
  --name "master-encryption-key" \
  --kty RSA-HSM \
  --size 4096 \
  --ops wrapKey unwrapKey

# Backup e restore chiave
az keyvault key backup \
  --vault-name $KV_NAME \
  --name "signing-key" \
  --file signing-key-backup.blob

az keyvault key restore \
  --vault-name $KV_NAME \
  --file signing-key-backup.blob

# Importare chiave esistente
az keyvault key import \
  --vault-name $KV_NAME \
  --name "imported-key" \
  --pem-file my-private-key.pem \
  --pem-password "passphrase"

# Operazioni crittografiche
az keyvault key encrypt \
  --vault-name $KV_NAME \
  --name "signing-key" \
  --algorithm RSA-OAEP-256 \
  --value "$(echo 'data to encrypt' | base64)" \
  --output json
```

## Gestione Certificati

```bash
# Creare certificato self-signed (per dev/test)
cat > cert-policy.json << 'EOF'
{
  "issuerParameters": {
    "name": "Self"
  },
  "keyProperties": {
    "curve": null,
    "exportable": true,
    "keySize": 2048,
    "keyType": "RSA",
    "reuseKey": false
  },
  "lifetimeActions": [
    {
      "action": {
        "actionType": "AutoRenew"
      },
      "trigger": {
        "daysBeforeExpiry": 30
      }
    }
  ],
  "secretProperties": {
    "contentType": "application/x-pkcs12"
  },
  "x509CertificateProperties": {
    "ekus": ["1.3.6.1.5.5.7.3.1", "1.3.6.1.5.5.7.3.2"],
    "keyUsage": ["digitalSignature", "keyEncipherment"],
    "subject": "CN=myapp.example.com",
    "subjectAlternativeNames": {
      "dnsNames": ["myapp.example.com", "www.myapp.example.com"]
    },
    "validityInMonths": 12
  }
}
EOF

az keyvault certificate create \
  --vault-name $KV_NAME \
  --name "myapp-tls-cert" \
  --policy @cert-policy.json

# Creare certificato con CA pubblica (DigiCert o GlobalSign — richiede integrazione)
az keyvault certificate create \
  --vault-name $KV_NAME \
  --name "myapp-prod-cert" \
  --policy @digicert-policy.json

# Importare certificato PFX/PEM esistente
az keyvault certificate import \
  --vault-name $KV_NAME \
  --name "existing-cert" \
  --file mycert.pfx \
  --password "pfx-password"

# Listare certificati
az keyvault certificate list \
  --vault-name $KV_NAME \
  --output table

# Scaricare certificato come PEM
az keyvault certificate download \
  --vault-name $KV_NAME \
  --name "myapp-tls-cert" \
  --encoding PEM \
  --file myapp-cert.pem
```

## RBAC per Key Vault

Con RBAC abilitato (`--enable-rbac-authorization true`), i permessi si gestiscono con Azure Role Assignments invece delle legacy Access Policies.

### Ruoli Principali

| Ruolo | Permessi | Use Case |
|---|---|---|
| **Key Vault Administrator** | Full control | Amministratori, automation |
| **Key Vault Secrets Officer** | CRUD secrets | App che gestiscono segreti |
| **Key Vault Secrets User** | Read secrets | App che leggono segreti (minimo privilegio) |
| **Key Vault Keys Officer** | CRUD keys | App che gestiscono chiavi |
| **Key Vault Crypto User** | Encrypt/Decrypt | App che usano chiavi per crittografia |
| **Key Vault Crypto Service Encryption User** | Wrap/Unwrap key | Servizi Azure (Storage, SQL) per CMK |
| **Key Vault Certificates Officer** | CRUD certificates | App che gestiscono certificati |
| **Key Vault Reader** | Read metadata (no values) | Audit, monitoring |

```bash
# Assegnare Secrets User a una Managed Identity
PRINCIPAL_ID=$(az identity show --resource-group rg-webapp-prod --name mi-myapp --query principalId -o tsv)
KV_ID=$(az keyvault show --name $KV_NAME --query id -o tsv)

az role assignment create \
  --assignee-object-id $PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" \
  --scope $KV_ID

# Assegnare Secrets Officer a un gruppo Entra ID
az role assignment create \
  --assignee $(az ad group show --group "DevOps-Team" --query id -o tsv) \
  --role "Key Vault Secrets Officer" \
  --scope $KV_ID

# Assegnare accesso solo a un segreto specifico (scope granulare)
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope "$KV_ID/secrets/db-connection-string"
```

## Network Rules e Private Endpoint

```bash
# Aggiungere regola network per subnet VNet specifica
az keyvault network-rule add \
  --resource-group $RG \
  --name $KV_NAME \
  --vnet-name vnet-prod \
  --subnet snet-app

# Aggiungere IP range specifico (es: ufficio)
az keyvault network-rule add \
  --resource-group $RG \
  --name $KV_NAME \
  --ip-address 203.0.113.0/24

# Impostare default action a Deny
az keyvault update \
  --resource-group $RG \
  --name $KV_NAME \
  --default-action Deny \
  --bypass AzureServices

# Private Endpoint (accesso solo da VNet)
az network private-endpoint create \
  --resource-group $RG \
  --name pep-keyvault-prod \
  --vnet-name vnet-prod \
  --subnet snet-private-endpoints \
  --private-connection-resource-id $KV_ID \
  --group-ids vault \
  --connection-name conn-keyvault-prod

# DNS zona privata per Key Vault
az network private-dns zone create \
  --resource-group $RG \
  --name "privatelink.vaultcore.azure.net"

az network private-dns link vnet create \
  --resource-group $RG \
  --zone-name "privatelink.vaultcore.azure.net" \
  --name link-vnet-prod \
  --virtual-network vnet-prod \
  --registration-enabled false
```

## Key Vault References per App Service / Functions

I Key Vault References permettono di referenziare segreti direttamente nelle App Settings senza copia locale del valore.

```bash
# Sintassi Key Vault Reference
# @Microsoft.KeyVault(SecretUri=https://kv-prod-myapp-2026.vault.azure.net/secrets/db-password/)
# Oppure con versione specifica:
# @Microsoft.KeyVault(SecretUri=https://kv-prod-myapp-2026.vault.azure.net/secrets/db-password/abc123def456)

# Configurare App Settings con Key Vault Reference
az webapp config appsettings set \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --settings \
    "DB_PASSWORD=@Microsoft.KeyVault(SecretUri=https://$KV_NAME.vault.azure.net/secrets/db-password/)" \
    "API_KEY=@Microsoft.KeyVault(SecretUri=https://$KV_NAME.vault.azure.net/secrets/api-key/)" \
    "REDIS_CONNECTION=@Microsoft.KeyVault(SecretUri=https://$KV_NAME.vault.azure.net/secrets/redis-conn/)"

# Verificare che i riferimenti siano risolti correttamente
az webapp config appsettings list \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --output json
```

!!! tip "Auto-refresh dei Key Vault References"
    Quando il segreto viene aggiornato in Key Vault, l'App Service/Functions aggiorna automaticamente il valore **senza necessità di redeploy**. Il refresh avviene entro 24 ore, o immediatamente riavviando l'app.

## Rotation Automatica con EventGrid + Functions

```python
# Azure Function per rotazione automatica di un segreto
import azure.functions as func
import logging
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import random
import string

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="event")
def secret_rotation(event: func.EventGridEvent):
    """
    Triggered da EventGrid quando un segreto sta per scadere.
    EventGrid event type: Microsoft.KeyVault.SecretNearExpiry
    """
    event_data = event.get_json()
    secret_name = event_data.get("ObjectName")
    vault_url = event_data.get("VaultUrl")

    logging.info(f"Rotating secret: {secret_name} in vault: {vault_url}")

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)

    # Generare nuovo valore segreto
    new_value = generate_secure_password(32)

    # Aggiornare il segreto nel Key Vault
    client.set_secret(secret_name, new_value)

    # Aggiornare anche nel servizio esterno (es: database password)
    update_database_password(new_value)

    logging.info(f"Secret {secret_name} rotated successfully")

def generate_secure_password(length: int) -> str:
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.SystemRandom().choice(characters) for _ in range(length))
```

```bash
# Creare Event Grid subscription per notifiche Key Vault
az eventgrid event-subscription create \
  --source-resource-id $KV_ID \
  --name sub-keyvault-rotation \
  --endpoint-type azurefunction \
  --endpoint $(az functionapp function show --resource-group rg-security-prod --name func-secret-rotation --function-name secret_rotation --query id -o tsv) \
  --included-event-types \
    Microsoft.KeyVault.SecretNearExpiry \
    Microsoft.KeyVault.SecretExpired \
    Microsoft.KeyVault.SecretNewVersionCreated
```

## Azure App Configuration

App Configuration è un servizio complementare a Key Vault per centralizzare la configurazione applicativa (non i segreti). Permette feature flags, configurazione per environment, e integrazione con Key Vault.

```bash
# Creare App Configuration
az appconfig create \
  --resource-group $RG \
  --name appconf-myapp-prod \
  --location $LOCATION \
  --sku Standard

# Aggiungere configurazioni
az appconfig kv set \
  --name appconf-myapp-prod \
  --key "App:MaxRetries" \
  --value "3" \
  --label prod

az appconfig kv set \
  --name appconf-myapp-prod \
  --key "App:FeatureFlags:NewDashboard" \
  --value "true" \
  --label prod

# Key Vault reference in App Configuration
az appconfig kv set-keyvault \
  --name appconf-myapp-prod \
  --key "App:DatabasePassword" \
  --secret-identifier "https://$KV_NAME.vault.azure.net/secrets/db-password/"
```

## SDK Python: DefaultAzureCredential

```python
# Pattern standard per accesso Key Vault da Python
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.keyvault.certificates import CertificateClient
from azure.identity import DefaultAzureCredential

# DefaultAzureCredential prova in ordine:
# 1. EnvironmentCredential (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
# 2. WorkloadIdentityCredential (AKS Workload Identity)
# 3. ManagedIdentityCredential (VM, App Service, Functions)
# 4. SharedTokenCacheCredential
# 5. VisualStudioCodeCredential
# 6. AzureCliCredential (az login)
# 7. AzurePowerShellCredential

VAULT_URL = "https://kv-prod-myapp-2026.vault.azure.net/"
credential = DefaultAzureCredential()

# Secrets
secrets_client = SecretClient(vault_url=VAULT_URL, credential=credential)

# Lettura semplice
db_password = secrets_client.get_secret("db-password").value

# Scrittura
secrets_client.set_secret(
    "new-api-key",
    "super-secret-value",
    expires_on=datetime(2027, 1, 1, tzinfo=timezone.utc)
)

# Listare segreti
for secret_props in secrets_client.list_properties_of_secrets():
    print(f"Name: {secret_props.name}, Enabled: {secret_props.enabled}")

# Keys
keys_client = KeyClient(vault_url=VAULT_URL, credential=credential)

# Creare chiave
key = keys_client.create_rsa_key("my-key", size=4096)

# Firma e verifica (tramite CryptographyClient)
from azure.keyvault.keys.crypto import CryptographyClient, SignatureAlgorithm

crypto_client = CryptographyClient(key, credential=credential)
import hashlib
message = b"data to sign"
digest = hashlib.sha256(message).digest()

sign_result = crypto_client.sign(SignatureAlgorithm.rs256, digest)
verify_result = crypto_client.verify(SignatureAlgorithm.rs256, digest, sign_result.signature)
print(f"Signature valid: {verify_result.is_valid}")
```

## Best Practices

- Usa sempre **RBAC** (`--enable-rbac-authorization true`) invece delle legacy Access Policies
- Abilita sempre **soft-delete** e **purge protection** in produzione
- Separa Key Vault per ambiente: `kv-dev-*`, `kv-staging-*`, `kv-prod-*`
- Imposta sempre `--public-network-access Disabled` in produzione + Private Endpoint
- Usa il **principio del minimo privilegio**: assegna `Key Vault Secrets User` (read-only) alle app, `Secrets Officer` solo dove necessario write
- Non mettere Key Vault in una subscription condivisa con altri tenant: ogni subscription di produzione deve avere il suo Key Vault
- Configura notifiche EventGrid per `SecretNearExpiry` per rotation proattiva

## Troubleshooting

### Scenario 1 — Access Denied (403) da Managed Identity

**Sintomo:** L'applicazione riceve `403 Forbidden` o `ForbiddenByPolicy` quando tenta di leggere un segreto.

**Causa:** La Managed Identity non ha un Role Assignment sul Key Vault, oppure il RBAC non è abilitato e si usa ancora Access Policies senza aggiornamento.

**Soluzione:** Verificare l'assegnazione del ruolo e aggiungerla se mancante.

```bash
# Ottenere l'object ID della Managed Identity
MI_OBJECT_ID=$(az identity show \
  --resource-group rg-webapp-prod \
  --name mi-myapp \
  --query principalId -o tsv)

# Verificare ruoli assegnati sul Key Vault
az role assignment list \
  --scope $KV_ID \
  --assignee $MI_OBJECT_ID \
  --output table

# Se non ci sono assegnazioni, aggiungere Key Vault Secrets User
az role assignment create \
  --assignee-object-id $MI_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" \
  --scope $KV_ID

# Attendere propagazione (1-5 min) poi testare
az keyvault secret show \
  --vault-name $KV_NAME \
  --name my-secret
```

---

### Scenario 2 — Key Vault Reference non risolta in App Service

**Sintomo:** L'App Setting mostra `@Microsoft.KeyVault(...)` come stringa letterale invece del valore del segreto. Il portale mostra l'icona di errore accanto al setting.

**Causa:** La System-Assigned Managed Identity dell'App Service non è abilitata, oppure non ha il ruolo `Key Vault Secrets User`, oppure la sintassi della reference è errata.

**Soluzione:**

```bash
# 1. Abilitare System-Assigned Identity sull'App Service
az webapp identity assign \
  --resource-group rg-webapp-prod \
  --name myapp-prod

APP_PRINCIPAL_ID=$(az webapp identity show \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --query principalId -o tsv)

# 2. Assegnare il ruolo
az role assignment create \
  --assignee-object-id $APP_PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" \
  --scope $KV_ID

# 3. Verificare lo stato delle reference (portale o REST API)
az webapp config appsettings list \
  --resource-group rg-webapp-prod \
  --name myapp-prod \
  --query "[?contains(value, 'KeyVault')]" \
  --output table

# 4. Forzare refresh riavviando l'app
az webapp restart \
  --resource-group rg-webapp-prod \
  --name myapp-prod
```

---

### Scenario 3 — Impossibile eliminare permanentemente un segreto (purge)

**Sintomo:** `az keyvault secret purge` restituisce errore `Conflict` o `SecretIsPurgeProtected`.

**Causa:** La purge protection è abilitata sul vault. Con purge protection attiva i segreti soft-deleted non possono essere eliminati permanentemente prima dello scadere del retention period (default 90 giorni).

**Soluzione:** Attendere il retention period oppure, se il vault non è in produzione e si vuole eliminarlo completamente, procedere alla cancellazione del vault intero dopo il retention period.

```bash
# Verificare se purge protection è attiva
az keyvault show \
  --name $KV_NAME \
  --query "{softDelete:properties.enableSoftDelete, purgeProtection:properties.enablePurgeProtection}" \
  --output json

# Verificare i segreti nel deleted state
az keyvault secret list-deleted \
  --vault-name $KV_NAME \
  --output table

# Recuperare la data di scadenza per il purge
az keyvault secret show-deleted \
  --vault-name $KV_NAME \
  --name my-secret \
  --query "scheduledPurgeDate"

# Se purge protection NON è attiva, si può forzare il purge
az keyvault secret purge \
  --vault-name $KV_NAME \
  --name my-secret
```

---

### Scenario 4 — Timeout di connessione al Key Vault da VM o AKS

**Sintomo:** L'applicazione imposta un timeout cercando di raggiungere `https://<vault>.vault.azure.net`. L'errore è di tipo network (connection refused o DNS resolution failure).

**Causa:** Il vault ha `--public-network-access Disabled` e non è configurato il Private Endpoint o le network rules per la subnet del caller. Oppure il DNS non risolve il private endpoint.

**Soluzione:**

```bash
# 1. Verificare le network rules del vault
az keyvault show \
  --name $KV_NAME \
  --query "properties.networkAcls" \
  --output json

# 2. Aggiungere la subnet del caller alle network rules
az keyvault network-rule add \
  --resource-group $RG \
  --name $KV_NAME \
  --vnet-name vnet-prod \
  --subnet snet-app

# 3. Verificare la risoluzione DNS dal pod/VM (deve puntare all'IP privato)
# Da dentro il cluster/VM:
# nslookup kv-prod-myapp-2026.vault.azure.net
# Deve restituire un IP in 10.x.x.x (private endpoint IP), non un IP pubblico

# 4. Verificare che il Private DNS Zone Link sia configurato
az network private-dns link vnet list \
  --resource-group $RG \
  --zone-name "privatelink.vaultcore.azure.net" \
  --output table

# 5. Verificare log diagnostici
az monitor log-analytics query \
  --workspace $(az monitor log-analytics workspace list --resource-group $RG --query "[0].id" -o tsv) \
  --analytics-query "AzureDiagnostics | where ResourceType == 'VAULTS' | where OperationName == 'SecretGet' | project TimeGenerated, CallerIPAddress, ResultType | order by TimeGenerated desc | take 20" \
  --output table
```

## Riferimenti

- [Documentazione Azure Key Vault](https://learn.microsoft.com/azure/key-vault/)
- [Key Vault RBAC](https://learn.microsoft.com/azure/key-vault/general/rbac-guide)
- [Key Vault References per App Service](https://learn.microsoft.com/azure/app-service/app-service-key-vault-references)
- [Secret Rotation Best Practices](https://learn.microsoft.com/azure/key-vault/secrets/tutorial-rotation)
- [Azure Key Vault Python SDK](https://learn.microsoft.com/azure/key-vault/secrets/quick-create-python)
- [Managed HSM](https://learn.microsoft.com/azure/key-vault/managed-hsm/)
