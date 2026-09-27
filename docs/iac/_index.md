---
title: "Infrastructure as Code"
slug: iac
category: iac
tags: [iac, infrastructure-as-code, terraform, ansible, pulumi, crossplane, automazione, provisioning]
search_keywords: [infrastructure as code, iac, terraform, ansible, pulumi, crossplane, hashicorp, hcl, provisioning, automazione infrastruttura, gitops, immutable infrastructure]
parent: /
status: complete
difficulty: intermediate
last_updated: 2026-09-27
---

# Infrastructure as Code

La sezione IaC copre gli strumenti e le pratiche per gestire l'infrastruttura come codice versionabile, testabile e riproducibile. L'adozione di IaC è uno dei passaggi fondamentali verso una cultura DevOps matura: elimina la configurazione manuale, garantisce ambienti identici e abilita il provisioning automatizzato.

## Strumenti Coperti

| Strumento | Paradigma | Caso d'uso principale |
|---|---|---|
| **Terraform** | Dichiarativo, agentless | Provisioning cloud multi-provider |
| **Ansible** | Dichiarativo, agentless | Configuration management, provisioning VM |
| **Pulumi** | Imperativo (linguaggi reali) | IaC per team developer-oriented |
| **Crossplane** | Dichiarativo, Kubernetes-native | Self-service infrastructure via control loop K8s |

## Percorso di Apprendimento

1. **Terraform Fondamentali** — HCL, provider, resource, ciclo plan/apply
2. **Terraform State Management** — Remote state, locking, workspace
3. **Terraform Moduli** — Riuso, registry, composizione
4. **Ansible Fondamentali** — Playbook, inventory, roles
5. **Pulumi Fondamentali** — quando preferire un linguaggio reale a HCL
6. **Crossplane Fondamentali** — quando l'astrazione self-service via Kubernetes ha senso

## Relazioni con altri argomenti

- [CI/CD](../ci-cd/_index.md) — IaC si integra nei pipeline per infrastructure automation
- [Cloud AWS](../cloud/aws/_index.md) — Terraform è lo standard per provisioning AWS
- [GitOps](../ci-cd/gitops/argocd.md) — IaC + GitOps = infrastruttura dichiarativa a ciclo chiuso
