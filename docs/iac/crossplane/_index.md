---
title: "Crossplane"
slug: crossplane
category: iac
tags: [crossplane, iac, kubernetes, platform-engineering, cloud]
search_keywords: [crossplane, kubernetes-native iac, control loop, managed resource, composite resource, xrd, self-service infrastructure]
parent: iac/_index
related: [iac/crossplane/fondamentali, iac/terraform/fondamentali, iac/pulumi/fondamentali]
status: complete
difficulty: advanced
last_updated: 2026-09-27
---

# Crossplane

Crossplane è un progetto CNCF che estende Kubernetes per provisionare infrastruttura cloud tramite CRD e controller in control loop, invece di un CLI esterno con state file. Abilita self-service infrastructure via `kubectl apply`, con RBAC e GitOps nativi.

## Argomenti in questa sezione

| Argomento | Contenuto |
|---|---|
| [Fondamentali](fondamentali.md) | Provider, Managed Resource, Composite Resource (XR), Composition, XRD, claim, control loop, esempi AWS |

## Quando Scegliere Crossplane

- Cluster Kubernetes già maturo, con bisogno di offrire self-service infrastructure ai team applicativi
- Platform engineering: costruire una Internal Developer Platform con astrazioni custom
- Necessità di riconciliazione continua (drift correction automatica) invece di apply on-demand

## Relazioni

- [Terraform](../terraform/_index.md) — paradigma dichiarativo on-demand via CLI/HCL, alternativa più diffusa e con curva di apprendimento più bassa
- [Pulumi](../pulumi/_index.md) — IaC imperativo con linguaggi reali, complementare per la logica di provisioning fuori dal cluster
