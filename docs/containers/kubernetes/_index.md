---
title: "Kubernetes"
slug: kubernetes
category: containers
tags: [kubernetes, k8s, orchestration, control-plane, pod, deployment, statefulset]
search_keywords: [kubernetes overview, k8s enterprise, kubernetes production, kubernetes architecture, kubernetes components, kubernetes learning path]
parent: containers/_index
related: [containers/openshift/_index, containers/helm/_index, networking/kubernetes/_index]
official_docs: https://kubernetes.io/docs/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Kubernetes

Kubernetes (K8s) è il sistema di orchestrazione di container de facto per ambienti enterprise. Automatizza deployment, scaling, self-healing e gestione della configurazione di applicazioni containerizzate.

## Sottosezioni

<div class="grid cards" markdown>

-   **Architettura**

    Control plane (API server, etcd, scheduler), node components, request lifecycle.

    → [Architettura](architettura.md)

-   **Workloads**

    Pod lifecycle, Deployment, StatefulSet, DaemonSet, Job, CronJob, init containers.

    → [Workloads](workloads.md)

-   **Storage**

    PV/PVC/StorageClass, CSI drivers, StatefulSet storage, volume lifecycle.

    → [Storage](storage.md)

-   **Scheduling Avanzato**

    Resource requests/limits, HPA/VPA/KEDA, affinity, taints/tolerations, PriorityClass.

    → [Scheduling Avanzato](scheduling-avanzato.md)

-   **Sicurezza**

    PSA, SecurityContext, RBAC, OPA Gatekeeper, Kyverno, seccomp, Falco.

    → [Sicurezza](sicurezza.md)

-   **Operators e CRD**

    Controller pattern, CRD, kubebuilder, reconcile loop, operator SDK.

    → [Operators e CRD](operators-crd.md)

-   **Troubleshooting**

    kubectl avanzato, events, ephemeral debug containers, profiling, common issues.

    → [Troubleshooting](troubleshooting.md)

</div>

!!! note "Networking Kubernetes"
    CNI, Ingress, NetworkPolicy e Service Mesh sono documentati nella sezione [Networking → Kubernetes](../../networking/kubernetes/_index.md).
