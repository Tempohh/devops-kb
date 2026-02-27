---
title: "NoSQL"
slug: nosql
category: databases
tags: [nosql, redis, mongodb, cassandra, document, key-value, wide-column]
search_keywords: [nosql databases, non-relational databases, document store, key value store, wide column store, graph database, redis cache, mongodb aggregation, cassandra consistency]
parent: databases/_index
related: [databases/fondamentali/modelli-dati, databases/fondamentali/acid-base-cap, databases/fondamentali/sharding]
official_docs: https://www.mongodb.com/nosql-explained
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# NoSQL

I database NoSQL nascono per risolvere problemi specifici che i database relazionali gestiscono male: latenza sub-millisecondo su dati caldi, scalabilità write orizzontale, modelli di dati flessibili senza schema fisso. La scelta tra SQL e NoSQL non è ideologica — è una questione di allineamento tra il modello di dati, i pattern di accesso e i requisiti di consistenza.

## Argomenti

<div class="grid cards" markdown>

- **[Redis](redis.md)** — Cache in-memory, strutture dati avanzate, Pub/Sub, Streams, Sentinel e Cluster
- **[MongoDB](mongodb.md)** — Document store, aggregation pipeline, replica set, sharding
- **[Cassandra](cassandra.md)** — Wide-column store, modello di dati guidato dalle query, consistency levels, compaction

</div>

## Quando NoSQL

| Caso d'uso | Soluzione NoSQL | Perché non SQL |
|------------|----------------|----------------|
| Cache, sessioni, rate limiting | Redis | Latenza <1ms, eviction LRU, TTL nativo |
| Catalogo prodotti, CMS, user profiles | MongoDB | Schema flessibile, embedding document |
| Write ad alta frequenza, IoT, analytics | Cassandra | Write throughput lineare, nessun single point |
| Grafi sociali, raccomandazioni | Neo4j | JOIN ricorsivi sono O(n!) in SQL |
| Time series ad alta cardinalità | InfluxDB / TimescaleDB | Specializzato per serie temporali |

## Approfondimenti Prerequisiti

??? info "Modelli di Dati — Guida alla scelta"
    Confronto strutturato tra tutti i modelli: relazionale, document, key-value, wide-column, graph, vector.

    **Approfondimento →** [Modelli di Dati](../fondamentali/modelli-dati.md)

??? info "CAP e PACELC — Fondamentali teorici"
    I trade-off di consistenza che determinano il comportamento dei database NoSQL in caso di partizione.

    **Approfondimento →** [ACID, BASE, CAP](../fondamentali/acid-base-cap.md)
