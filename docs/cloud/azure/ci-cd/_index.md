---
title: "Azure CI/CD & IaC"
slug: cicd-azure
category: cloud
tags: [azure, devops, pipelines, iac, bicep, arm, terraform, github-actions, azure-devops]
search_keywords: [Azure DevOps, Azure Pipelines, GitHub Actions Azure, ARM templates, Bicep, Terraform Azure, Infrastructure as Code, CI/CD Azure, deployment automation, YAML pipeline, service connection, Azure Developer CLI azd]
parent: cloud/azure/_index
related: [cloud/azure/identita/rbac-managed-identity, cloud/azure/compute/aks-containers, cloud/azure/security/key-vault]
official_docs: https://learn.microsoft.com/azure/devops/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure CI/CD & IaC

## Panoramica

| Strumento | Tipo | Uso Principale |
|-----------|------|---------------|
| **Azure DevOps Pipelines** | CI/CD | Pipeline YAML multi-stage, ambienti con approval, release gate |
| **GitHub Actions + Azure** | CI/CD | Integrazione nativa GitHub + az login OIDC |
| **ARM Templates** | IaC | JSON dichiarativo, nativo Azure (legacy → Bicep) |
| **Bicep** | IaC | DSL Azure nativo, transpila in ARM, leggibile |
| **Terraform** | IaC | Multi-cloud, HCL, state management, moduli community |
| **Azure Developer CLI (azd)** | IaC + CI/CD | Developer-friendly workflow end-to-end |

## Azure DevOps vs GitHub Actions

| Caratteristica | Azure DevOps Pipelines | GitHub Actions |
|----------------|------------------------|----------------|
| Repository | Azure Repos o GitHub | GitHub |
| Hosting | Microsoft SaaS | GitHub SaaS |
| YAML CI/CD | Sì (stage/job/step) | Sì (workflow/job/step) |
| Environments + Approval | Sì (nativo, avanzato) | Sì (Environment protection rules) |
| Release Gates | Sì (query metrics, REST) | Parziale (via actions) |
| Parallel jobs free | 1800 min/mese | 2000 min/mese (public) |
| Self-hosted runners | Sì | Sì |
| Package Registry | Azure Artifacts | GitHub Packages |
| Project Management | Azure Boards | GitHub Projects |
| Use case | Enterprise, complesso | Open source, GitHub-first |

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-pipe: **[Azure DevOps](azure-devops.md)**

    ---
    Azure Pipelines YAML, ambienti, approval gates, Variable Groups, Key Vault integration, Artifacts, self-hosted agents

-   :material-file-code: **[ARM Templates & Bicep](arm-bicep.md)**

    ---
    Bicep DSL (sintassi, moduli, registry), ARM Templates, what-if deploy, Deployment Stacks, Azure Developer CLI (azd)

</div>
