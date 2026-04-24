---
title: "Google Cloud Platform"
slug: gcp
category: cloud
tags: [gcp, google-cloud, cloud, devops, infrastructure]
search_keywords: [GCP, Google Cloud Platform, Google Cloud, cloud provider, Google cloud certification, Professional Cloud DevOps Engineer, Professional Cloud Architect, Google compute engine, GKE, BigQuery]
parent: cloud/_index
related: [cloud/aws/_index, cloud/azure/_index]
official_docs: https://cloud.google.com/docs
status: complete
difficulty: beginner
last_updated: 2026-03-25
---

# Google Cloud Platform

GCP è il cloud provider di Google, terzo per quota di mercato globale. Distingue per eccellenza in **data analytics, machine learning e Kubernetes** (GKE è il Kubernetes managed più maturo del mercato, nato internamente in Google). Questa sezione copre GCP dalla prospettiva di un **Cloud/DevOps Engineer**.

## Punti di Forza GCP

```
GCP vs AWS vs Azure — differenziatori chiave

  GCP eccelle in:
  ├── Kubernetes (GKE) — nato in Google, il managed K8s più maturo
  ├── Big Data / Analytics — BigQuery, Dataflow, Pub/Sub
  ├── Machine Learning — Vertex AI, TPU, AutoML
  ├── Networking — rete privata globale Google (200+ PoP)
  └── Prezzi Compute — preemptible/spot VM più economiche
```

---

## Mappa dei Servizi

<div class="grid cards" markdown>

- :material-book-open: **[Fondamentali](fondamentali/_index.md)**

    Progetti, IAM, billing, regioni/zone, Google Cloud SDK

- :material-kubernetes: **[Containers](containers/_index.md)**

    GKE — Autopilot vs Standard, Workload Identity, node pool, autoscaling

- :material-database-search: **[Dati & Analytics](dati/_index.md)**

    BigQuery — data warehouse serverless, slot pricing, partitioning, clustering, BQML

- :material-chart-line: **[Monitoring & Observability](monitoring/_index.md)**

    Cloud Monitoring, Cloud Logging, Managed Prometheus (MSP), alerting policy, SLO nativi, Cloud Trace, integrazione OTEL

- :material-bucket: **[Storage](storage/_index.md)**

    Cloud Storage (GCS) — object storage, storage class, lifecycle policy, versioning, IAM, Terraform state backend

</div>

---

## Certificazioni GCP

| Certificazione | Livello | Target |
|---|---|---|
| **Cloud Digital Leader** | Foundational | Manager/Executive, non tecnico |
| **Associate Cloud Engineer** | Associate | Engineer operativo |
| **Professional Cloud Architect** | Professional | Architettura soluzioni cloud |
| **Professional Cloud DevOps Engineer** | Professional | CI/CD, SRE, operations |
| **Professional Data Engineer** | Professional | Pipeline dati, BigQuery |
| **Professional ML Engineer** | Professional | MLOps, Vertex AI |
