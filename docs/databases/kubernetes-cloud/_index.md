---
title: "Database su Kubernetes e Cloud"
slug: kubernetes-cloud
category: databases
tags: [kubernetes, cloud, statefulset, operator, managed-database, rds, aurora]
search_keywords: [database kubernetes, statefulset database, kubernetes operator database, managed database cloud, rds postgresql, aurora postgresql, cloud sql, azure database, database as a service, dbaas, cloudnativepg, postgres operator]
parent: databases/_index
related: [databases/postgresql/replicazione, databases/replicazione-ha/backup-pitr, databases/postgresql/connection-pooling]
official_docs: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Database su Kubernetes e Cloud

Eseguire database su Kubernetes e scegliere tra database self-managed e managed cloud service sono due delle decisioni architetturali più impattanti in un progetto backend. Non esiste una risposta universale — dipende dal team, dagli SLA, e dal budget.

## Argomenti

<div class="grid cards" markdown>

- **[Database su Kubernetes](db-su-kubernetes.md)** — StatefulSet, PersistentVolume, operator pattern, CloudNativePG
- **[Managed Databases](managed-databases.md)** — RDS, Aurora, DynamoDB, Cloud SQL — quando usarli e trade-off

</div>

## Il Trade-off Fondamentale

```
Self-managed (Kubernetes)          Managed (RDS, Aurora, Cloud SQL)
  Pro:                               Pro:
  ✓ Controllo totale                 ✓ Operatività a carico del provider
  ✓ Costo inferiore a parità hw      ✓ Backup, patch, HA integrati
  ✓ Stessa piattaforma dell'app      ✓ SLA garantiti dal provider
  ✓ Portabilità multi-cloud          ✓ RTO/RPO ben definiti

  Contro:                            Contro:
  ✗ Richiede expertise database      ✗ Costo superiore (10-50% premium)
  ✗ DBA on-call obbligatorio         ✗ Meno controllo su configurazione
  ✗ Backup/HA da implementare        ✗ Vendor lock-in
  ✗ Storage persistente su k8s       ✗ Limitazioni versioni/extensions
```
