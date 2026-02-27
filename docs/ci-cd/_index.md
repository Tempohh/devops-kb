---
title: "CI/CD & DevOps Automation"
slug: ci-cd
category: ci-cd
tags: [cicd, jenkins, github-actions, gitlab-ci, gitops, argocd, flux, pipeline, automation, devops]
search_keywords: [CI/CD, continuous integration, continuous delivery, continuous deployment, pipeline automation, Jenkins, GitHub Actions, GitLab CI, ArgoCD, Flux, GitOps, DORA metrics, DevOps pipeline, deployment pipeline enterprise, blue green canary, SBOM supply chain, SLSA]
parent: _index
related: [containers/kubernetes/_index, containers/helm/_index]
official_docs: https://www.jenkins.io/doc/
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# CI/CD & DevOps Automation

La **Continuous Integration / Continuous Delivery** è la pratica fondamentale del DevOps: automatizzare build, test e rilascio del software per ridurre il rischio e accelerare il time-to-market.

---

## Concetti Fondamentali

```
Developer Push
     │
     ▼
┌────────────────────────────────────────────────────────────┐
│  CONTINUOUS INTEGRATION                                     │
│  ① Checkout source code                                    │
│  ② Build (compile, package)                                │
│  ③ Unit Test + Code Coverage                               │
│  ④ Static Analysis (SAST, linting, style)                  │
│  ⑤ Artifact publishing (container image, JAR, npm pkg)     │
└──────────────────────────┬─────────────────────────────────┘
                           │ artefatto verificato
                           ▼
┌────────────────────────────────────────────────────────────┐
│  CONTINUOUS DELIVERY (Staging)                              │
│  ⑥ Deploy in ambiente di test                              │
│  ⑦ Integration Test / E2E Test                             │
│  ⑧ Dynamic Analysis (DAST, penetration)                    │
│  ⑨ Performance Test                                        │
│  ⑩ Approvazione manuale (gate umano)                       │
└──────────────────────────┬─────────────────────────────────┘
                           │ approvato
                           ▼
┌────────────────────────────────────────────────────────────┐
│  CONTINUOUS DEPLOYMENT (Production)                         │
│  ⑪ Deploy progressivo (canary / blue-green)                │
│  ⑫ Smoke Test / Rollback automatico                        │
│  ⑬ Osservabilità (metrics, tracing, alerting)              │
└────────────────────────────────────────────────────────────┘
```

---

## DORA Metrics — Misurare la Performance DevOps

I **DORA Metrics** (DevOps Research and Assessment) sono i KPI standard per valutare la maturità di un team DevOps:

| Metrica | Elite | High | Medium | Low |
|---------|-------|------|--------|-----|
| **Deployment Frequency** | Su richiesta (>1/giorno) | 1/settimana - 1/mese | 1/mese - 1/6mesi | < 1/6 mesi |
| **Lead Time for Changes** | < 1 ora | 1 giorno - 1 settimana | 1 settimana - 1 mese | > 6 mesi |
| **Change Failure Rate** | 0-15% | 16-30% | 16-30% | 16-30% |
| **Time to Restore** | < 1 ora | < 1 giorno | 1 giorno - 1 settimana | > 6 mesi |

---

## Confronto Strumenti CI/CD

| Strumento | Tipo | Hosting | Curva apprendimento | Use Case |
|-----------|------|---------|---------------------|---------|
| **Jenkins** | Self-hosted, Groovy | On-prem / Cloud | Alta | Enterprise legacy, massima flessibilità |
| **GitHub Actions** | SaaS + Self-hosted | GitHub | Bassa | Open source, GitHub-first |
| **GitLab CI** | SaaS + Self-managed | GitLab | Media | GitLab monorepo, DevSecOps integrato |
| **Azure DevOps Pipelines** | SaaS | Microsoft | Media | Ecosistema Microsoft |
| **Tekton** | Kubernetes-native | On-prem | Alta | Cloud-native, Kubernetes-native pipeline |
| **Argo Workflows** | Kubernetes-native | On-prem | Alta | DAG workflow complessi, ML pipeline |
| **CircleCI** | SaaS | Cloud | Bassa | Startup, velocità di setup |
| **Drone CI** | Self-hosted | On-prem | Bassa | Docker-native, leggero |

---

## GitOps vs CI/CD Tradizionale

```
PUSH-BASED (CI/CD tradizionale)
Pipeline → kubectl apply / helm upgrade → Cluster

PULL-BASED (GitOps)
Git Repo ← sincronizzazione ← ArgoCD/Flux agente nel cluster
Il cluster si auto-configura dallo stato desiderato in Git
```

**Vantaggi GitOps:**
- Git come single source of truth
- Audit trail completo (chi ha cambiato cosa e quando)
- Rollback = `git revert`
- Drift detection automatica
- Nessuna credenziale cluster esposta all'esterno

---

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :fontawesome-brands-jenkins: **[Jenkins](jenkins/_index.md)**

    ---
    Pipeline Declarative/Scripted, Shared Libraries, Kubernetes Agents, JCasC, RBAC enterprise, Multi-branch, Pattern avanzati

-   :fontawesome-brands-github: **[GitHub Actions](github-actions/_index.md)**

    ---
    Workflow YAML, Matrix, Reusable Workflows, OIDC zero-secret auth, Self-hosted Runners enterprise

-   :fontawesome-brands-gitlab: **[GitLab CI](gitlab-ci/_index.md)**

    ---
    Pipeline DAG, Multi-project, Compliance Frameworks, Protected Environments, Auto DevOps

-   :material-source-branch: **[GitOps](gitops/_index.md)**

    ---
    ArgoCD (App of Apps, ApplicationSets, multi-cluster, SSO), Flux (GitRepository, HelmRelease, Flagger)

-   :material-rocket-launch: **[Strategie di Deployment](strategie/_index.md)**

    ---
    Blue/Green, Canary, Rolling, Feature Flags, Progressive Delivery, Pipeline Security, SBOM, SLSA, Sigstore

</div>
