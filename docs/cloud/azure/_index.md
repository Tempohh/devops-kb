---
title: "Microsoft Azure"
slug: azure
category: cloud
tags: [azure, microsoft, cloud, certification, az-900, az-104, az-305, az-400]
search_keywords: [Microsoft Azure, Azure cloud, AZ-900 Azure Fundamentals, AZ-104 Azure Administrator, AZ-204 Azure Developer, AZ-305 Azure Architect, AZ-400 Azure DevOps, Azure certification path, Azure services, cloud computing Microsoft, Azure regions, Azure subscription]
parent: cloud/_index
related: [cloud/aws/_index]
official_docs: https://docs.microsoft.com/azure/
status: complete
difficulty: beginner
last_updated: 2026-02-26
---

# Microsoft Azure

**Microsoft Azure** è la piattaforma cloud di Microsoft — secondo provider cloud al mondo per quota di mercato. Offre oltre 200 servizi in 60+ region distribuite globalmente, con forte integrazione con l'ecosistema Microsoft (Active Directory, Microsoft 365, Visual Studio, GitHub).

---

## Percorso Certificazioni Azure

```
Ruolo                    Certificazione               Prerequisiti
─────                    ─────────────                ────────────

Fondamentali        →    AZ-900: Azure Fundamentals   Nessuno
                         DP-900: Data Fundamentals    Nessuno
                         AI-900: AI Fundamentals      Nessuno
                         SC-900: Security Fundamentals Nessuno

Administrator       →    AZ-104: Azure Administrator  AZ-900 consigliato

Developer           →    AZ-204: Azure Developer      AZ-900 consigliato

Security            →    AZ-500: Security Engineer    AZ-104 consigliato

DevOps              →    AZ-400: DevOps Engineer      AZ-104 + AZ-204

Architect           →    AZ-305: Solutions Architect  AZ-104

AI Engineer         →    AI-102: AI Engineer          AZ-900 / AI-900

Data Engineer       →    DP-203: Data Engineer        DP-900 consigliato
```

!!! tip "Percorso Consigliato Cloud/DevOps Engineer"
    **AZ-900** (fondamentali, 2-4 settimane) →
    **AZ-104** (amministrazione, 2-3 mesi) →
    **AZ-400** (DevOps, 2-3 mesi) →
    **AZ-305** (architettura, 3-4 mesi)

---

## Gerarchia Risorse Azure

```
Azure Account (Microsoft Account o Work Account)
└── Tenant (Microsoft Entra ID)
    └── Management Groups (organizzazione gerarchica — max 6 livelli)
        └── Subscriptions (unità di billing e limite di policy)
            └── Resource Groups (contenitore logico per risorse)
                └── Resources (VM, Storage, App Service, ecc.)
```

**Concetti chiave:**
- **Tenant:** Istanza dedicata di Microsoft Entra ID (ex Azure Active Directory)
- **Subscription:** Unità di billing + limite per quota e policy. Una subscription = 1 tenant, 1 tenant = N subscription
- **Resource Group:** Contenitore logico — stessa lifecycle, stessa region consigliata. Le risorse devono essere in un RG
- **Management Group:** Organizza subscription in gerarchia per applicare policy e RBAC uniformi (fino a 6 livelli annidati + root)
- **ARM (Azure Resource Manager):** Layer unificato per tutte le operazioni (portal, CLI, PowerShell, API, IaC)

---

## Infrastruttura Globale

| Elemento | Numero (2026) | Descrizione |
|----------|---------------|-------------|
| Region | 60+ | Aree geografiche con datacenter Azure |
| Availability Zones | 3 per region (dove disponibili) | Datacenter fisicamente separati nella stessa region |
| Edge Locations CDN | 190+ PoP | Azure CDN / Front Door Points of Presence |
| Sovereign Clouds | 3 | Azure Government, Azure China (21Vianet), Azure Germany |

**Region pair:** ogni region Azure è accoppiata con un'altra region nella stessa area geografica. I servizi geo-ridondanti replicano nel pair automaticamente. Esempio: `Italy North` ↔ `West Europe`.

---

## Mappa Servizi Azure

<div class="grid cards" markdown>

-   :material-earth: **[Fondamentali](fondamentali/_index.md)**

    ---
    Infrastruttura globale, modello responsabilità condivisa, Well-Architected Framework, pricing e gestione costi

-   :material-shield-account: **[Identità (Entra ID)](identita/_index.md)**

    ---
    Microsoft Entra ID (Azure AD), RBAC, Managed Identity, PIM, Conditional Access, Governance

-   :material-network: **[Networking](networking/_index.md)**

    ---
    Virtual Network, NSG, Load Balancer, Application Gateway, Azure Firewall, VPN Gateway, ExpressRoute, DNS, Front Door

-   :material-server: **[Compute](compute/_index.md)**

    ---
    Virtual Machines, VMSS, App Service, Azure Functions, AKS, Container Instances, Azure Batch

-   :material-database: **[Storage](storage/_index.md)**

    ---
    Blob Storage, Azure Files, Queue Storage, Table Storage, Disk Storage, Data Lake Storage Gen2

-   :material-table: **[Database](database/_index.md)**

    ---
    Azure SQL, SQL Managed Instance, Cosmos DB, Azure Database for PostgreSQL/MySQL, Redis Cache

-   :material-lock: **[Security](security/_index.md)**

    ---
    Azure Key Vault, Defender for Cloud, Microsoft Sentinel, Azure Policy, DDoS Protection

-   :material-chart-line: **[Monitoring](monitoring/_index.md)**

    ---
    Azure Monitor, Log Analytics, Application Insights, Alerts, Dashboards, Workbooks

-   :material-pipe: **[CI/CD & IaC](ci-cd/_index.md)**

    ---
    Azure DevOps (Pipelines, Repos, Artifacts), GitHub Actions + Azure, ARM Templates, Bicep

-   :material-message-processing: **[Messaging](messaging/_index.md)**

    ---
    Service Bus, Event Grid, Event Hubs, Storage Queues — decoupling e event-driven architecture

</div>

---

## Azure vs AWS — Confronto Servizi

| Categoria | AWS | Azure |
|-----------|-----|-------|
| Compute VM | EC2 | Virtual Machines |
| Serverless | Lambda | Azure Functions |
| Container managed | ECS/Fargate | Container Instances (ACI) |
| Kubernetes | EKS | AKS |
| PaaS app | Elastic Beanstalk | App Service |
| Object storage | S3 | Blob Storage |
| Block storage | EBS | Managed Disks |
| File storage | EFS | Azure Files |
| SQL managed | RDS | Azure SQL / SQL MI |
| NoSQL multi-model | DynamoDB | Cosmos DB |
| CDN | CloudFront | Azure CDN / Front Door |
| DNS | Route 53 | Azure DNS |
| IAM | IAM + Organizations | Entra ID + RBAC + Policy |
| Secrets | Secrets Manager / SSM | Key Vault |
| CI/CD | CodePipeline / CodeBuild | Azure DevOps Pipelines |
| IaC | CloudFormation / CDK | ARM Templates / Bicep |
| Message Queue | SQS | Service Bus / Storage Queue |
| Pub/Sub | SNS | Event Grid / Service Bus Topics |
| Streaming | Kinesis | Event Hubs |
| Monitoring | CloudWatch | Azure Monitor |
| Log aggregation | CloudWatch Logs | Log Analytics |
| APM | X-Ray | Application Insights |

---

## Azure CLI — Comandi Essenziali

```bash
# Login
az login
az login --use-device-code     # per ambienti headless/CI

# Gestione subscription
az account list --output table
az account set --subscription "Nome o ID Subscription"
az account show

# Gestione Resource Group
az group create --name myapp-rg --location italynorth
az group list --output table
az group delete --name myapp-rg --yes --no-wait

# Trovare le location disponibili
az account list-locations --query "[].{Name:name, DisplayName:displayName}" --output table

# Tag su resource group
az group update --name myapp-rg --tags Environment=production Team=platform

# Listare risorse in un RG
az resource list --resource-group myapp-rg --output table

# Deploy ARM/Bicep
az deployment group create \
    --resource-group myapp-rg \
    --template-file main.bicep \
    --parameters @params.json

# Logout
az logout
```

---

## Riferimenti Ufficiali

- [Azure Documentation](https://docs.microsoft.com/azure/)
- [Azure Architecture Center](https://learn.microsoft.com/azure/architecture/)
- [Azure Well-Architected Framework](https://learn.microsoft.com/azure/well-architected/)
- [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
- [Azure CLI Reference](https://docs.microsoft.com/cli/azure/)
- [Microsoft Learn](https://learn.microsoft.com/azure/)
- [AZ-900 Study Guide](https://learn.microsoft.com/certifications/exams/az-900)
- [AZ-104 Study Guide](https://learn.microsoft.com/certifications/exams/az-104)
