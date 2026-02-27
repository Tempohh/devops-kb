---
title: "App Service & Azure Functions"
slug: app-service-functions
category: cloud
tags: [azure, app-service, functions, serverless, paas, web-app, deployment-slots]
search_keywords: [App Service Plan, Azure Web App, Azure Functions serverless, deployment slots, swap slot, VNet integration, private endpoint, App Service Environment ASE, Durable Functions orchestrator, cold start, managed identity app service, custom domain TLS certificate]
parent: cloud/azure/compute/_index
related: [cloud/azure/security/key-vault, cloud/azure/networking/vnet, cloud/azure/monitoring/application-insights]
official_docs: https://learn.microsoft.com/azure/app-service/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# App Service & Azure Functions

## Panoramica

**Azure App Service** è una piattaforma PaaS (Platform-as-a-Service) per l'hosting di applicazioni web, REST API e backend mobile. Gestisce automaticamente OS patching, scaling, load balancing e SSL/TLS. Il modello di pricing è basato sul piano (istanza fissa pagata anche se idle).

**Azure Functions** è la piattaforma serverless di Azure per l'esecuzione di codice event-driven. Si scala automaticamente da zero e nel Consumption plan si paga solo per le esecuzioni effettive. Ideale per task asincroni, automazioni, microservizi leggeri.

Scegliere App Service quando: l'applicazione ha traffico continuativo, richiede deployment slots, o necessita di runtime persistente. Scegliere Functions quando: il codice risponde a eventi, ha picchi irregolari, o si vuole minimizzare i costi per workload intermittenti.

## App Service Plans

Il piano App Service determina risorse compute disponibili, feature e costo:

| Tier | Piano | vCPU | RAM | Storage | Feature Chiave | Use Case |
|---|---|---|---|---|---|---|
| **Free** | F1 | Condiviso | 1 GB | 1 GB | Nessuna | Solo sviluppo/testing |
| **Shared** | D1 | Condiviso | 1 GB | 1 GB | Custom domain | Dev/test con dominio |
| **Basic** | B1-B3 | 1-4 dedicati | 1.75-7 GB | 10 GB | SSL, 3 istanze | Dev/test, workload semplici |
| **Standard** | S1-S3 | 1-4 dedicati | 1.75-7 GB | 50 GB | Deployment slots, autoscale, VNet | Produzione standard |
| **Premium v3** | P1v3-P3v3 | 2-8 dedicati | 8-32 GB | 250 GB | VNet integration enhanced, zone redundancy | Produzione enterprise |
| **Isolated v2** | I1v2-I3v2 | 2-8 dedicati | 8-32 GB | 1 TB | ASE (VNet-private), compliance | Workload altamente sicuri, regulated |

### Creare App Service Plan e Web App

```bash
RG="rg-webapp-prod"
LOCATION="westeurope"
PLAN_NAME="asp-prod-westeurope"
APP_NAME="myapp-prod-2026"   # Deve essere globalmente unico

# Creare resource group
az group create --name $RG --location $LOCATION

# Creare App Service Plan (Linux, Premium v3)
az appservice plan create \
  --resource-group $RG \
  --name $PLAN_NAME \
  --location $LOCATION \
  --is-linux \
  --sku P1V3 \
  --number-of-workers 2

# Creare Web App Python
az webapp create \
  --resource-group $RG \
  --plan $PLAN_NAME \
  --name $APP_NAME \
  --runtime "PYTHON:3.12" \
  --assign-identity SystemAssigned

# Configurare App Settings (variabili d'ambiente)
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings \
    ENVIRONMENT=production \
    APP_LOG_LEVEL=INFO \
    DB_HOST=mydbserver.postgres.database.azure.com \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=..."

# Abilitare HTTPS-only e TLS 1.2 minimo
az webapp update \
  --resource-group $RG \
  --name $APP_NAME \
  --https-only true

az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --min-tls-version 1.2 \
  --ftps-state Disabled
```

### Runtime Supportati

```bash
# Listare tutti i runtime disponibili
az webapp list-runtimes --os-type linux --output table

# Esempi comuni
# PYTHON:3.12, PYTHON:3.11
# NODE:20-lts, NODE:18-lts
# DOTNETCORE:8.0
# JAVA:21-java21
# PHP:8.3
# Containers: usa --deployment-container-image-name
```

## Deployment Slots

I deployment slot sono ambienti separati della stessa app (staging, canary, A/B testing) che condividono lo stesso App Service Plan senza costo aggiuntivo di compute.

```bash
# Creare slot staging (richiede tier Standard+)
az webapp deployment slot create \
  --resource-group $RG \
  --name $APP_NAME \
  --slot staging \
  --configuration-source $APP_NAME

# Deploy su staging
az webapp deploy \
  --resource-group $RG \
  --name $APP_NAME \
  --slot staging \
  --src-path ./dist/app.zip \
  --type zip

# Visualizzare URL slot staging
echo "Staging URL: https://$APP_NAME-staging.azurewebsites.net"

# Swap: promuovi staging a production (zero-downtime)
az webapp deployment slot swap \
  --resource-group $RG \
  --name $APP_NAME \
  --slot staging \
  --target-slot production

# Traffic splitting: 10% su canary per A/B testing
az webapp traffic-routing set \
  --resource-group $RG \
  --name $APP_NAME \
  --distribution staging=10

# Cancella routing (100% su production)
az webapp traffic-routing clear \
  --resource-group $RG \
  --name $APP_NAME
```

!!! tip "Sticky Settings"
    Alcune configurazioni (Connection Strings, App Settings marcate come "slot setting") sono "sticky" al slot e NON vengono scambiate durante lo swap. Usare per impostazioni specifiche dell'ambiente (es. database di staging vs produzione).

```bash
# Marcare un'impostazione come slot-sticky
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --slot staging \
  --slot-settings \
    DATABASE_URL="postgres://staging-db..." \
    ENVIRONMENT=staging
```

## Metodi di Deployment

### ZipDeploy (deployment diretto)

```bash
# Build e deploy del pacchetto zip
zip -r app.zip . -x "*.git*" "node_modules/*" "__pycache__/*"

az webapp deploy \
  --resource-group $RG \
  --name $APP_NAME \
  --src-path app.zip \
  --type zip \
  --restart true
```

### Container Registry Deploy

```bash
# Deploy da Azure Container Registry
az webapp create \
  --resource-group $RG \
  --plan $PLAN_NAME \
  --name $APP_NAME \
  --deployment-container-image-name myacr.azurecr.io/myapp:latest \
  --assign-identity SystemAssigned

# Autorizzare App Service a pullare da ACR via Managed Identity
az role assignment create \
  --assignee $(az webapp identity show --resource-group $RG --name $APP_NAME --query principalId -o tsv) \
  --role AcrPull \
  --scope $(az acr show --name myacr --query id -o tsv)

# Abilita pull da ACR con Managed Identity
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --generic-configurations '{"acrUseManagedIdentityCreds": true}'
```

### GitHub Actions Integration

```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure App Service

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies and test
        run: |
          pip install -r requirements.txt
          pytest tests/

      - name: Login to Azure
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Deploy to App Service
        uses: azure/webapps-deploy@v3
        with:
          app-name: myapp-prod-2026
          slot-name: staging
          package: .
```

## VNet Integration e Private Endpoints

### VNet Integration (Outbound — accesso a risorse private)

La VNet integration permette all'App Service di raggiungere risorse nella VNet (database privati, Key Vault con private endpoint, ecc.). Richiede tier Standard+.

```bash
# Creare subnet delegata per App Service VNet integration
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name vnet-prod \
  --name snet-appservice-outbound \
  --address-prefixes 10.0.10.0/28 \
  --delegations Microsoft.Web/serverFarms

# Abilitare VNet integration
az webapp vnet-integration add \
  --resource-group $RG \
  --name $APP_NAME \
  --vnet vnet-prod \
  --subnet snet-appservice-outbound

# Forzare tutto il traffico uscente attraverso la VNet (incluso Internet)
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings WEBSITE_VNET_ROUTE_ALL=1
```

### Private Endpoint (Inbound — accesso solo da VNet)

Il private endpoint rende l'App Service raggiungibile solo dalla VNet (non da Internet pubblico).

```bash
# Creare private endpoint per App Service
az network private-endpoint create \
  --resource-group $RG \
  --name pep-appservice \
  --vnet-name vnet-prod \
  --subnet snet-private-endpoints \
  --private-connection-resource-id $(az webapp show --resource-group $RG --name $APP_NAME --query id -o tsv) \
  --group-ids sites \
  --connection-name conn-appservice

# DNS: zona privata per azurewebsites.net
az network private-dns zone create \
  --resource-group $RG \
  --name "privatelink.azurewebsites.net"

az network private-dns link vnet create \
  --resource-group $RG \
  --zone-name "privatelink.azurewebsites.net" \
  --name link-vnet-prod \
  --virtual-network vnet-prod \
  --registration-enabled false
```

## Custom Domains e Certificati TLS

```bash
# Aggiungere custom domain
az webapp config hostname add \
  --resource-group $RG \
  --webapp-name $APP_NAME \
  --hostname myapp.example.com

# Creare Managed Certificate gratuito (solo per tier Basic+)
az webapp config ssl create \
  --resource-group $RG \
  --name $APP_NAME \
  --hostname myapp.example.com

# Abilitare SSL binding
az webapp config ssl bind \
  --resource-group $RG \
  --name $APP_NAME \
  --certificate-thumbprint $(az webapp config ssl show --resource-group $RG --name $APP_NAME --query thumbprint -o tsv) \
  --ssl-type SNI

# Importare certificato custom da Key Vault
az webapp config ssl import \
  --resource-group $RG \
  --name $APP_NAME \
  --key-vault mykeyvault \
  --key-vault-certificate-name mycert
```

## App Service Environment (ASE)

L'App Service Environment (ASEv3) è un deployment completamente isolato all'interno di una VNet. Adatto a workload che richiedono:
- Compliance (PCI-DSS, HIPAA, ISO 27001)
- Isolamento di rete completo
- Latency garantita verso risorse on-premises
- Scaling fino a 200 istanze

```bash
# ASE richiede subnet /24 dedicata (256 indirizzi)
# Deployment tipicamente dal portale o ARM/Bicep per complessità

# Creare App Service Plan su ASE esistente
az appservice plan create \
  --resource-group $RG \
  --name asp-ase-prod \
  --app-service-environment myase \
  --sku I1V2 \
  --is-linux
```

## Azure Functions

### Piani di Hosting Functions

| Piano | Cold Start | Scaling | Max Timeout | Use Case |
|---|---|---|---|---|
| **Consumption** | Sì (alcune sec) | Auto 0→∞ | 5 min (default), 10 min (max) | Workload intermittenti, pay-per-use |
| **Premium** | No (pre-warmed) | Auto 1→∞ | Illimitato | Cold start sensibile, VNet, lunga esecuzione |
| **Dedicated (App Service)** | No | Manuale/autoscale | Illimitato | Costo prevedibile, già su App Service Plan |

### Creare Function App

```bash
# Creare storage account per Functions (obbligatorio)
az storage account create \
  --resource-group $RG \
  --name stfunc${RANDOM} \
  --sku Standard_LRS \
  --allow-blob-public-access false

# Creare Function App Python — Consumption Plan
az functionapp create \
  --resource-group $RG \
  --name func-processor-prod \
  --storage-account stfunc12345 \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.12 \
  --functions-version 4 \
  --os-type Linux \
  --assign-identity SystemAssigned

# Creare Function App — Premium Plan (no cold start, VNet support)
az functionapp plan create \
  --resource-group $RG \
  --name asp-functions-premium \
  --location $LOCATION \
  --sku EP1 \
  --is-linux

az functionapp create \
  --resource-group $RG \
  --name func-critical-prod \
  --storage-account stfunc12345 \
  --plan asp-functions-premium \
  --runtime python \
  --runtime-version 3.12 \
  --functions-version 4 \
  --os-type Linux
```

### Trigger Types — Esempi

#### HTTP Trigger (Python)

```python
# function_app.py
import azure.functions as func
import logging
import json

app = func.FunctionApp()

@app.route(route="hello", methods=["GET", "POST"], auth_level=func.AuthLevel.FUNCTION)
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("HTTP trigger function processed a request.")

    name = req.params.get("name") or req.get_json().get("name", "World")

    return func.HttpResponse(
        json.dumps({"message": f"Hello, {name}!"}),
        mimetype="application/json",
        status_code=200
    )
```

#### Timer Trigger (Node.js)

```javascript
// timerFunction/index.js
const { app } = require('@azure/functions');

app.timer('timerTrigger', {
    schedule: '0 */5 * * * *',  // ogni 5 minuti (cron NCRONTAB)
    handler: async (myTimer, context) => {
        context.log(`Timer trigger executed at: ${new Date().toISOString()}`);

        if (myTimer.isPastDue) {
            context.log('Timer is running late!');
        }

        // Business logic here
        await processQueue();
    }
});
```

#### Blob Storage Trigger (Python)

```python
@app.blob_trigger(
    arg_name="myblob",
    path="incoming/{name}",
    connection="AzureWebJobsStorage"
)
def blob_trigger(myblob: func.InputStream, context: func.Context):
    logging.info(
        f"Python blob trigger processed blob: {myblob.name}, "
        f"Size: {myblob.length} bytes"
    )
    # Elabora il blob
    data = myblob.read()
    process_uploaded_file(data, myblob.name)
```

#### Service Bus Queue Trigger

```python
@app.service_bus_queue_trigger(
    arg_name="azservicebus",
    queue_name="myqueue",
    connection="SERVICE_BUS_CONNECTION"
)
def servicebus_queue_trigger(azservicebus: func.ServiceBusMessage):
    message_body = azservicebus.get_body().decode("utf-8")
    logging.info(f"Processing message: {message_body}")
```

### Durable Functions

Durable Functions estende Azure Functions con pattern di orchestrazione stateful: orchstrator coordinano activity in sequenza o in parallelo, con checkpoint automatici.

```python
# orchestrator function
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    # Esegui activity in sequenza
    result1 = yield context.call_activity("ProcessStep1", "input data")
    result2 = yield context.call_activity("ProcessStep2", result1)

    # Esegui activity in parallelo (fan-out/fan-in)
    parallel_tasks = [
        context.call_activity("ParallelTask", item)
        for item in ["a", "b", "c", "d"]
    ]
    results = yield context.task_all(parallel_tasks)

    return results

main = df.Orchestrator.create(orchestrator_function)
```

```python
# activity function
import azure.functions as func

def main(inputData: str) -> str:
    # Logica business qui
    return f"Processed: {inputData}"
```

Pattern Durable Functions:
- **Function Chaining**: esecuzione sequenziale con passaggio output
- **Fan-out/Fan-in**: esecuzione parallela e aggregazione risultati
- **Async HTTP API**: poll del completamento via HTTP
- **Monitor**: polling periodico fino a condizione soddisfatta
- **Human Interaction**: attesa approvazione umana con timeout

## Managed Identity per Key Vault

```bash
# Recuperare il principalId dell'App Service
PRINCIPAL_ID=$(az webapp identity show \
  --resource-group $RG \
  --name $APP_NAME \
  --query principalId -o tsv)

# Assegnare ruolo Key Vault Secrets User
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name mykeyvault --query id -o tsv)
```

```python
# Accedere a Key Vault da App Service con Managed Identity
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://mykeyvault.vault.azure.net/", credential=credential)

secret = client.get_secret("my-database-password")
db_password = secret.value
```

### Key Vault References in App Settings

```bash
# Invece di mettere il segreto in App Settings direttamente,
# usa un riferimento a Key Vault (si aggiorna automaticamente)
az webapp config appsettings set \
  --resource-group $RG \
  --name $APP_NAME \
  --settings \
    "DB_PASSWORD=@Microsoft.KeyVault(SecretUri=https://mykeyvault.vault.azure.net/secrets/db-password/)"
```

## Best Practices

- Usa sempre **Deployment Slots** per zero-downtime deploy in produzione
- Abilita **Always On** su tier Basic+ per evitare che la app si "addormenti" (non disponibile su Free/Shared)
- Per Functions in produzione, usa **Premium Plan** se hai requisiti di latency o VNet integration
- Configura **Health Check** endpoint per rilevare istanze unhealthy
- Usa **Key Vault References** invece di credenziali dirette nelle App Settings
- Imposta `WEBSITE_RUN_FROM_PACKAGE=1` per deploy immutabile da zip (performance migliore)

```bash
# Abilitare Always On
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --always-on true

# Health check endpoint
az webapp config set \
  --resource-group $RG \
  --name $APP_NAME \
  --generic-configurations '{"healthCheckPath": "/health"}'
```

## Troubleshooting

```bash
# Streaming log real-time
az webapp log tail \
  --resource-group $RG \
  --name $APP_NAME

# Abilitare diagnostica dettagliata
az webapp log config \
  --resource-group $RG \
  --name $APP_NAME \
  --application-logging filesystem \
  --level verbose \
  --web-server-logging filesystem

# Scaricare log
az webapp log download \
  --resource-group $RG \
  --name $APP_NAME \
  --log-file webapp_logs.zip

# SSH nel container (solo Linux)
az webapp ssh \
  --resource-group $RG \
  --name $APP_NAME
```

## Riferimenti

- [Documentazione App Service](https://learn.microsoft.com/azure/app-service/)
- [Documentazione Azure Functions](https://learn.microsoft.com/azure/azure-functions/)
- [Durable Functions Documentation](https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview)
- [App Service Pricing](https://azure.microsoft.com/pricing/details/app-service/linux/)
- [Functions Pricing](https://azure.microsoft.com/pricing/details/functions/)
- [VNet Integration App Service](https://learn.microsoft.com/azure/app-service/overview-vnet-integration)
