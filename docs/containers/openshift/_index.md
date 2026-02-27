---
title: "OpenShift"
slug: openshift
category: containers
tags: [openshift, ocp, redhat, kubernetes, enterprise, scc, olm, s2i]
search_keywords: [openshift container platform, OCP vs kubernetes, openshift enterprise, openshift security, openshift operators, openshift gitops, ROSA, ARO, openshift SCC, openshift routes]
parent: containers/_index
related: [containers/kubernetes/_index, containers/helm/_index]
official_docs: https://docs.openshift.com/container-platform/latest/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# OpenShift

**OpenShift Container Platform (OCP)** è la distribuzione enterprise Kubernetes di Red Hat. Non è semplicemente "Kubernetes con extra": è un'opinionated platform-as-a-service con un set di operatori che gestiscono ogni aspetto del cluster.

## OpenShift vs Kubernetes Vanilla

```
OpenShift vs Kubernetes — Differenze Fondamentali

  Kubernetes:          OpenShift:
  ─────────────────    ──────────────────────────────────────────
  Installazione:       Installer Provisioned Infrastructure (IPI)
  manuale/kubeadm      o User Provisioned Infrastructure (UPI)
                       Cluster Version Operator (CVO) gestisce tutto

  Sicurezza:          Security Context Constraints (SCC)
  PSA (1.25+)         più restrittive del PSA restricted
  No default deny     Default: container NON possono girare come root

  Image Build:         BuildConfig + ImageStream + S2I (Source-to-Image)
  Non nativo           Build pipeline integrata nel cluster

  Registry:            Registry interno integrato (image-registry operator)
  Esterno              Immagini pushate automaticamente dopo ogni build

  Routing:             Route (HAProxy-based)
  Ingress              Con TLS termination, wildcard, edge/passthrough

  Autenticazione:      OAuth Server integrato
  Delegata             htpasswd, LDAP, GitHub, OIDC providers pronti

  Operators:           Operator Lifecycle Manager (OLM)
  Manuale              OperatorHub, CatalogSource, Subscription

  Console:             Console Web avanzata
  Non inclusa          Developer view + Administrator view separati
```

## Distribuzioni OpenShift

| Piattaforma | Descrizione |
|-------------|-------------|
| **OCP** | OpenShift Container Platform — on-premise o cloud self-managed |
| **ROSA** | Red Hat OpenShift Service on AWS — managed su AWS |
| **ARO** | Azure Red Hat OpenShift — managed su Azure |
| **RHOAI** | Red Hat OpenShift AI — con ML/AI stack integrato |
| **CRC** | CodeReady Containers — development locale (single node) |
| **MicroShift** | OpenShift per edge computing e dispositivi con risorse limitate |

## Sottosezioni

<div class="grid cards" markdown>

-   **Architettura**

    MCO, CVO, machine-api, operators-everywhere, differenze strutturali con K8s.

    → [Architettura](architettura.md)

-   **Build e ImageStream**

    BuildConfig, S2I, ImageStream, Tekton integration, image promotion.

    → [Build e ImageStream](build-imagestream.md)

-   **Sicurezza SCC**

    Security Context Constraints, OAuth Server, identity providers, LDAP.

    → [Sicurezza SCC](sicurezza-scc.md)

-   **Operators OLM**

    Operator Lifecycle Manager, OperatorHub, CSV, Subscription, CatalogSource custom.

    → [Operators OLM](operators-olm.md)

-   **GitOps e Pipelines**

    OpenShift GitOps (ArgoCD), OpenShift Pipelines (Tekton), image promotion workflow.

    → [GitOps e Pipelines](gitops-pipelines.md)

</div>
