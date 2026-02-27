---
title: "Replicazione e Alta Disponibilità"
slug: replicazione-ha
category: databases
tags: [replicazione, alta-disponibilità, failover, backup, pitr, rpo, rto]
search_keywords: [database replication, high availability databases, failover recovery, rpo rto, point in time recovery, backup database, streaming replication, logical replication, synchronous replication, asynchronous replication]
parent: databases/_index
related: [databases/postgresql/replicazione, databases/fondamentali/acid-base-cap]
official_docs: https://www.postgresql.org/docs/current/high-availability.html
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Replicazione e Alta Disponibilità

La replicazione e l'HA non sono la stessa cosa: la replicazione copia i dati su più nodi; l'HA garantisce che il servizio continui anche quando uno o più nodi falliscono. Una replica senza failover automatico non è HA; un failover senza replica rischia di perdere dati.

## Argomenti

<div class="grid cards" markdown>

- **[Strategie di Replica](strategie-replica.md)** — Sync vs async, RPO/RTO, read replicas, multi-master, trade-off
- **[Failover e Recovery](failover-recovery.md)** — Failover automatico (Patroni), procedure di failback, test di failover
- **[Backup e PITR](backup-pitr.md)** — pg_basebackup, WAL archiving, Point-in-Time Recovery, pgBackRest

</div>

## Concetti Chiave

**RPO** (Recovery Point Objective): quanto dato posso perdere? → determina la strategia di backup e il tipo di replicazione (sync vs async).

**RTO** (Recovery Time Objective): quanto downtime è accettabile? → determina se serve failover automatico e quanto veloce.

| RPO | RTO | Architettura |
|-----|-----|-------------|
| 0 (zero data loss) | Secondi | Sync replica + failover automatico (Patroni) |
| < 5 min | Minuti | Async replica + Sentinel/Patroni |
| Ore | Ore | Backup periodico + PITR |
| Giorni | Giorni | Backup su storage esterno |

## Relazioni

??? info "PostgreSQL Replicazione — Implementazione tecnica"
    Streaming replication, logical replication, replication slots, Patroni.

    **Approfondimento →** [PostgreSQL Replicazione](../postgresql/replicazione.md)
