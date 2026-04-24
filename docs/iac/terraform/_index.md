---
title: "Terraform"
slug: terraform
category: iac
tags: [terraform, iac, hashicorp, hcl, provisioning, cloud]
search_keywords: [terraform, hcl, hashicorp, provider, resource, state, plan, apply, destroy, workspace, moduli, remote state, backend]
parent: iac/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management, iac/terraform/moduli]
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Terraform

Terraform è lo strumento IaC più usato per il provisioning di infrastruttura cloud e on-premise. Usa un linguaggio dichiarativo (HCL) per descrivere lo stato desiderato dell'infrastruttura, e riconcilia automaticamente lo stato attuale con quello desiderato.

## Argomenti in questa sezione

| Argomento | Contenuto |
|---|---|
| [Fondamentali](fondamentali.md) | HCL, provider, resource, ciclo plan/apply, struttura progetto |
| [State Management](state-management.md) | Remote state, locking, backend, workspace, import |
| [Moduli](moduli.md) | Riuso, Terraform Registry, composizione |
| [Testing e Quality Gate](testing.md) | Terratest, tflint, checkov, conftest/OPA, pre-commit hooks |
| [Workflow CI/CD](ci-cd.md) | Atlantis, GitHub Actions, multi-ambiente, drift detection, OIDC |

## Quando Usare Terraform

- Provisioning di risorse cloud (VM, reti, database, IAM)
- Infrastruttura multi-provider (AWS + Cloudflare + GitHub in un unico piano)
- Team che necessitano di revisione delle modifiche infrastrutturali via PR

## Relazioni

- [AWS EC2](../../cloud/aws/compute/ec2.md) — Terraform è il metodo preferito per creare EC2
- [AWS VPC](../../cloud/aws/networking/vpc.md) — Gestione reti AWS via Terraform
- [GitOps / ArgoCD](../../ci-cd/gitops/argocd.md) — Terraform + ArgoCD per infrastruttura + app
