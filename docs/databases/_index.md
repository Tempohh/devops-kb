---
title: "Databases"
slug: databases
category: databases
tags: [databases, sql, nosql, postgresql, redis, mongodb, cassandra, replicazione, backup]
search_keywords: [database, sql database, nosql database, relational database, postgresql, redis, mongodb, cassandra, database replication, database backup, database kubernetes, managed database]
parent: _index
official_docs: https://www.postgresql.org/docs/current/
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Databases

La sezione copre i fondamentali teorici dei database, SQL avanzato, PostgreSQL in profondità, i principali database NoSQL, strategie di replica e alta disponibilità, backup e recovery, e come deployare database su Kubernetes e cloud managed.

## Sezioni

<div class="grid cards" markdown>

-   **[Fondamentali](fondamentali/_index.md)**

    ---
    ACID, BASE, CAP, modelli di dati, indici, transazioni e concorrenza, sharding.
    Gli aspetti che un'istruzione universitaria base raramente copre in profondità.

-   **[SQL Avanzato](sql-avanzato/_index.md)**

    ---
    Window functions, query optimizer (EXPLAIN ANALYZE), table partitioning.
    SQL oltre il CRUD.

-   **[PostgreSQL](postgresql/_index.md)**

    ---
    MVCC, vacuum, replicazione fisica e logica, connection pooling (PgBouncer), extensions (pgvector, TimescaleDB, PostGIS).

-   **[NoSQL](nosql/_index.md)**

    ---
    Redis (strutture dati, persistenza, Sentinel, Cluster), MongoDB (aggregation pipeline, replica set), Cassandra (wide-column, data modeling, compaction).

-   **[Replicazione e HA](replicazione-ha/_index.md)**

    ---
    Sync vs async, RPO/RTO, failover automatico con Patroni, backup fisico e Point-in-Time Recovery con pgBackRest.

-   **[Kubernetes e Cloud](kubernetes-cloud/_index.md)**

    ---
    StatefulSet, operator pattern (CloudNativePG), managed databases (RDS, Aurora, DynamoDB, Cloud SQL).

</div>

---

## Percorsi di Studio

### Per chi parte da zero con i database

1. [Modelli di Dati](fondamentali/modelli-dati.md) — capire quando usare SQL, document, key-value, graph
2. [ACID, BASE, CAP](fondamentali/acid-base-cap.md) — i fondamentali teorici
3. [Transazioni e Concorrenza](fondamentali/transazioni-concorrenza.md) — anomalie, isolation levels, MVCC
4. [Indici](fondamentali/indici.md) — perché le query sono lente e come risolverlo

### Per chi vuole padroneggiare PostgreSQL

1. [MVCC e Vacuum](postgresql/mvcc-vacuum.md) — come PostgreSQL gestisce la concorrenza
2. [Query Optimizer](sql-avanzato/query-optimizer.md) — leggere EXPLAIN ANALYZE
3. [Replicazione](postgresql/replicazione.md) — streaming e logical replication
4. [Connection Pooling](postgresql/connection-pooling.md) — PgBouncer in produzione
5. [Backup e PITR](replicazione-ha/backup-pitr.md) — non perdere dati

### Per architetture distribuite

1. [Sharding](fondamentali/sharding.md) — quando un singolo nodo non basta
2. [Strategie di Replica](replicazione-ha/strategie-replica.md) — sync vs async, topologie
3. [Cassandra](nosql/cassandra.md) — write-heavy, leaderless
4. [Managed Databases](kubernetes-cloud/managed-databases.md) — RDS, Aurora, DynamoDB

---

## Tutti gli Argomenti

| Argomento | Sezione | Difficoltà |
|-----------|---------|------------|
| [ACID, BASE, CAP, PACELC](fondamentali/acid-base-cap.md) | Fondamentali | Intermediate |
| [Modelli di Dati](fondamentali/modelli-dati.md) | Fondamentali | Intermediate |
| [Indici](fondamentali/indici.md) | Fondamentali | Intermediate |
| [Transazioni e Concorrenza](fondamentali/transazioni-concorrenza.md) | Fondamentali | Advanced |
| [Sharding](fondamentali/sharding.md) | Fondamentali | Advanced |
| [Window Functions](sql-avanzato/window-functions.md) | SQL Avanzato | Intermediate |
| [Query Optimizer](sql-avanzato/query-optimizer.md) | SQL Avanzato | Advanced |
| [Partitioning](sql-avanzato/partitioning.md) | SQL Avanzato | Intermediate |
| [MVCC e Vacuum](postgresql/mvcc-vacuum.md) | PostgreSQL | Advanced |
| [Replicazione](postgresql/replicazione.md) | PostgreSQL | Advanced |
| [Connection Pooling](postgresql/connection-pooling.md) | PostgreSQL | Intermediate |
| [Extensions](postgresql/extensions.md) | PostgreSQL | Intermediate |
| [Redis](nosql/redis.md) | NoSQL | Intermediate |
| [MongoDB](nosql/mongodb.md) | NoSQL | Intermediate |
| [Cassandra](nosql/cassandra.md) | NoSQL | Advanced |
| [Strategie di Replica](replicazione-ha/strategie-replica.md) | Replicazione & HA | Advanced |
| [Failover e Recovery](replicazione-ha/failover-recovery.md) | Replicazione & HA | Advanced |
| [Backup e PITR](replicazione-ha/backup-pitr.md) | Replicazione & HA | Advanced |
| [Database su Kubernetes](kubernetes-cloud/db-su-kubernetes.md) | Kubernetes & Cloud | Advanced |
| [Managed Databases](kubernetes-cloud/managed-databases.md) | Kubernetes & Cloud | Intermediate |
