---
title: "Fondamentali dei Database"
slug: fondamentali-database
category: databases
tags: [database, fondamentali, acid, cap, nosql, indici, transazioni]
parent: databases
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Fondamentali dei Database

I concetti in questa sezione sono quelli che la maggior parte dei corsi universitari non approfondisce abbastanza: non il DDL o il SELECT base, ma i meccanismi che determinano il comportamento dei database sotto carico, sotto failure, e a scale non banali. Capire ACID a livello operativo (non solo la definizione), il CAP theorem come strumento decisionale, come funzionano davvero gli indici, e cosa succede quando si entra nel territorio delle transazioni concorrenti — questi sono i prerequisiti per ogni scelta architetturale seria.

## Argomenti

### [ACID, BASE e Teorema CAP](acid-base-cap.md)
Le garanzie fondamentali dei database distribuiti: ACID (Atomicity, Consistency, Isolation, Durability) vs BASE (Basically Available, Soft state, Eventually consistent). Il teorema CAP e la sua versione più precisa PACELC. Come usarli come strumenti decisionali, non solo come definizioni.

### [Modelli dei Dati](modelli-dati.md)
Relazionale, document, key-value, wide-column, graph, time-series, vettoriale. Non solo "quando usare cosa" ma perché ogni modello esiste, quali problemi risolve strutturalmente, e i costi nascosti di ogni scelta.

### [Indici — Strutture e Strategie](indici.md)
B-tree, Hash, GIN, GiST, BRIN, indici parziali, covering index, indici compositi. Come il query planner sceglie un indice (e quando decide di non usarlo). Index bloat, manutenzione, e indici vettoriali per similarity search.

### [Transazioni e Concorrenza](transazioni-concorrenza.md)
Livelli di isolamento (Read Uncommitted → Serializable), i fenomeni che evitano (dirty read, non-repeatable read, phantom read), MVCC come alternativa ai lock. Deadlock: rilevamento, prevenzione, come compaiono in produzione.

### [Sharding](sharding.md)
La distribuzione orizzontale dei dati: range sharding, hash sharding, directory-based. Hotspot, resharding, cross-shard queries, distributed transactions. Differenza tra sharding applicativo, middleware (Vitess, Citus) e sharding nativo (MongoDB, Cassandra, DynamoDB).
