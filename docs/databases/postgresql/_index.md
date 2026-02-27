---
title: "PostgreSQL"
slug: postgresql
category: databases
tags: [postgresql, postgres, mvcc, vacuum, replicazione, pooling, extensions]
parent: databases
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# PostgreSQL

PostgreSQL è il database relazionale open source più avanzato disponibile. È l'opzione di default per quasi ogni nuovo progetto che necessita di un database relazionale — non per abitudine ma perché la sua combinazione di estensibilità (pgvector, PostGIS, TimescaleDB, Citus), garanzie ACID robuste, e performance rende l'alternativa difficile da giustificare.

Questa sezione copre gli aspetti operativi avanzati che non appaiono nella documentazione introduttiva ma che determinano il comportamento in produzione.

## Argomenti

### [MVCC e Vacuum](mvcc-vacuum.md)
Il meccanismo MVCC (Multi-Version Concurrency Control) è il core di PostgreSQL: ogni scrittura crea nuove versioni delle righe, i reader non bloccano i writer. Il rovescio della medaglia: le versioni obsolete ("dead tuples") si accumulano causando bloat. VACUUM e autovacuum sono la manutenzione ordinaria — capire quando e perché tunarli è essenziale in produzione.

### [Replicazione](replicazione.md)
Streaming replication per alta disponibilità (primary + replica sincrona/asincrona), logical replication per replica selettiva e upgrade a zero-downtime. Replica slots, WAL archiving, e le operazioni che non replicano.

### [Connection Pooling — PgBouncer](connection-pooling.md)
PostgreSQL usa un processo per connessione — con centinaia di connessioni contemporanee il database si degrada. PgBouncer è il pooler standard: transaction mode, session mode, statement mode, sizing del pool, e configurazione per applicazioni moderne.

### [Extensions](extensions.md)
Le estensioni trasformano PostgreSQL in un sistema specializzato: `pgvector` per similarity search AI, `TimescaleDB` per time-series, `PostGIS` per GIS, `pg_partman` per lifecycle management, `pg_cron` per job scheduling interno.
