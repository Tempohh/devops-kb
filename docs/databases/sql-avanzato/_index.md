---
title: "SQL Avanzato"
slug: sql-avanzato
category: databases
tags: [sql, window-functions, query-optimizer, partitioning, performance]
parent: databases
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# SQL Avanzato

SQL è molto più ricco di SELECT, INSERT, UPDATE, DELETE. Le funzionalità avanzate — window functions, il query optimizer, il partitioning — sono quelle che distinguono le query che scalano da quelle che crollano con il volume.

## Argomenti

### [Window Functions](window-functions.md)
Le window function sono la funzionalità SQL più potente che la maggior parte degli sviluppatori non usa. Permettono di calcolare valori aggregati (somme mobili, ranking, percentili, lag/lead) **senza perdere la granularità delle righe**. Inclusi casi d'uso reali: running totals, percentile rankings, time-gap detection, sessioning.

### [Query Optimizer e EXPLAIN](query-optimizer.md)
Come il planner sceglie il piano di esecuzione, cosa significano seq scan, index scan, hash join, nested loop nei piani `EXPLAIN ANALYZE`. Come leggere i costi, identificare i bottleneck, e quando e come intervenire (indici, statistiche, configurazione).

### [Partitioning](partitioning.md)
Il partizionamento locale (su singolo nodo) divide una tabella grande in partizioni fisiche indipendenti. Partition pruning, manutenzione, performance su query di range. Range, List e Hash partitioning in PostgreSQL, con gestione automatica tramite `pg_partman`.
