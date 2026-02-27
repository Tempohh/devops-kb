---
title: "Azure Compute"
slug: compute-azure
category: cloud
tags: [azure, compute, vm, vmss, app-service, functions, aks, container-instances, batch]
search_keywords: [Azure compute, Virtual Machines VM, VMSS Scale Set, App Service, Azure Functions serverless, AKS Kubernetes, Container Instances ACI, Azure Batch, Spot VM, proximity placement group]
parent: cloud/azure/_index
related: [cloud/azure/networking/vnet, cloud/azure/storage/_index, cloud/azure/identita/rbac-managed-identity]
official_docs: https://learn.microsoft.com/azure/virtual-machines/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Compute

Azure Compute offre un portafoglio completo di servizi per eseguire workload di ogni tipo: macchine virtuali tradizionali, piattaforme managed PaaS, container orchestrati e architetture serverless. La scelta del servizio giusto dipende dal controllo richiesto, dal modello di pricing e dalla natura del workload.

## Panoramica dei Servizi Compute

| Servizio | Tipo | Use Case Principale | Pricing Model |
|---|---|---|---|
| **Virtual Machines (VM)** | IaaS | Workload legacy, OS customization, lift & shift | Pay-per-hour (PAYG, RI, Spot) |
| **VM Scale Sets (VMSS)** | IaaS | Scalabilità orizzontale automatica per VM | Pay-per-VM + autoscale |
| **App Service** | PaaS | Web app, REST API, backend mobile | Pay-per-plan (istanza fissa) |
| **Azure Functions** | Serverless/PaaS | Event-driven, microservizi, task asincroni | Consumption (per esecuzione) / Premium |
| **AKS (Kubernetes)** | PaaS/CaaS | Container orchestration, microservizi complessi | Pay-per-nodo (VM sottostante) |
| **Container Instances (ACI)** | Serverless | Container one-off, burst, sidecar pattern | Pay-per-second (vCPU + memoria) |
| **Azure Batch** | PaaS | HPC, elaborazione parallela massiva, rendering | Pay-per-VM durante esecuzione job |
| **Spot VMs** | IaaS | Workload fault-tolerant, CI/CD, batch | Sconto fino al 90% su PAYG |

## Quando Scegliere Quale Servizio

```
Hai bisogno di pieno controllo OS / software specifico?
└── SÌ → Virtual Machines (IaaS)
    └── Scalabilità automatica orizzontale? → VM Scale Sets

Workload containerizzato?
├── Orchestrazione complessa, microservizi → AKS
└── Task one-off, burst, no orchestrazione → Container Instances

Applicazione web / API?
├── Semplice, managed, no container → App Service
└── Event-driven, pay-per-use → Azure Functions

Elaborazione batch / HPC?
└── Azure Batch
```

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   **Virtual Machines & VMSS**

    ---

    IaaS tradizionale: famiglie VM, sizing, VMSS con autoscale, Managed Disks, Availability Zones, Spot VM, Azure Bastion, Just-In-Time Access.

    [:octicons-arrow-right-24: Vai a Virtual Machines](virtual-machines.md)

-   **App Service & Azure Functions**

    ---

    PaaS e Serverless: App Service Plans, deployment slots, VNet integration, Azure Functions trigger, Durable Functions, cold start, Managed Identity.

    [:octicons-arrow-right-24: Vai a App Service & Functions](app-service-functions.md)

-   **AKS & Container Instances**

    ---

    Container orchestration con AKS, Azure Container Registry, Workload Identity, node pools, Container Instances per task one-off, Azure Container Apps.

    [:octicons-arrow-right-24: Vai a AKS & Containers](aks-containers.md)

</div>

## Riferimenti

- [Documentazione Azure Compute](https://learn.microsoft.com/azure/architecture/guide/technology-choices/compute-decision-tree)
- [Azure Compute Decision Tree](https://learn.microsoft.com/azure/architecture/guide/technology-choices/compute-decision-tree)
- [Prezzi VM Azure](https://azure.microsoft.com/pricing/details/virtual-machines/)
