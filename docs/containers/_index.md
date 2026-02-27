---
title: "Containers"
slug: containers
category: containers
tags: [docker, kubernetes, openshift, containers, orchestration, helm, registry, runtime]
search_keywords: [container orchestration, kubernetes enterprise, openshift, docker production, helm, harbor registry, containerd, container runtime, cri-o, gvisor, kata containers]
official_docs: https://kubernetes.io/docs/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Containers

La containerizzazione è il fondamento dell'infrastruttura cloud-native moderna. Questa sezione copre l'intero stack: dal runtime di basso livello fino all'orchestrazione enterprise, con profondità tecnica massima su Docker, Kubernetes e OpenShift.

## Macro-Aree

<div class="grid cards" markdown>

-   :simple-docker: **Docker**

    ---
    Runtime, Dockerfile avanzato, networking, storage, sicurezza container.

    → [Docker](docker/_index.md)

-   :simple-kubernetes: **Kubernetes**

    ---
    Architettura control plane, workloads, storage, scheduling avanzato, operators, sicurezza.

    → [Kubernetes](kubernetes/_index.md)

-   :simple-redhat: **OpenShift**

    ---
    Enterprise Kubernetes: SCC, OLM, BuildConfig, S2I, GitOps con Tekton e ArgoCD.

    → [OpenShift](openshift/_index.md)

-   :material-cog: **Container Runtime**

    ---
    CRI, containerd, CRI-O, runc, sandboxing con gVisor e Kata Containers.

    → [Container Runtime](container-runtime/_index.md)

-   :material-warehouse: **Registry**

    ---
    OCI distribution spec, Harbor, ECR, proxy cache, air-gap, firma immagini.

    → [Registry](registry/_index.md)

-   :simple-helm: **Helm**

    ---
    Package manager Kubernetes: chart avanzati, hooks, helmfile, gestione ciclo di vita.

    → [Helm](helm/_index.md)

</div>

---

## Il Container Stack

```
Container Stack — Dalla Applicazione al Hardware

  Application Code
       |
  +----+--------------------------------------------+
  |  Container Image (OCI)                           |
  |  Layers: base OS + runtime + deps + app          |
  +----+--------------------------------------------+
       |
  +----+--------------------------------------------+
  |  Container Runtime                               |
  |  High-level: containerd / CRI-O  (CRI spec)     |
  |  Low-level:  runc / gVisor / Kata (OCI runtime) |
  +----+--------------------------------------------+
       |
  +----+--------------------------------------------+
  |  Linux Kernel                                    |
  |  Namespaces: pid, net, mnt, uts, ipc, user      |
  |  cgroups v2:  CPU/memory/IO accounting           |
  |  Syscall filter: seccomp + AppArmor/SELinux      |
  +----+--------------------------------------------+
       |
  +----+--------------------------------------------+
  |  Orchestration Layer                             |
  |  Kubernetes / OpenShift                          |
  |  Scheduling, scaling, self-healing, discovery   |
  +--------------------------------------------------+
```

---

## Percorsi di Studio

| Obiettivo | Percorso consigliato |
|-----------|----------------------|
| Capire come funzionano i container internamente | Docker Architettura → Container Runtime |
| Deployare applicazioni su Kubernetes | Kubernetes Workloads → Storage → Scheduling |
| Kubernetes enterprise con sicurezza avanzata | Kubernetes Sicurezza → OpenShift SCC |
| Estendere Kubernetes con custom controllers | Kubernetes Operators/CRD |
| Pipeline CI/CD e GitOps K8s | OpenShift GitOps + Helm Deployment |
| Gestire immagini in enterprise / air-gap | Registry Harbor |
