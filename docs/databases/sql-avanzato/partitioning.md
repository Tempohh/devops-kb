---
title: "Partitioning"
slug: partitioning
category: databases
tags: [partitioning, postgresql, performance, manutenzione, tabelle-grandi]
search_keywords: [table partitioning, range partitioning, list partitioning, hash partitioning, partition pruning, declarative partitioning, pg_partman, partition key, default partition, attach partition, detach partition, index partition, constraint exclusion, parallel query, time series partitioning, retention policy]
parent: databases/sql-avanzato/_index
related: [databases/fondamentali/sharding, databases/fondamentali/indici, databases/sql-avanzato/query-optimizer]
official_docs: https://www.postgresql.org/docs/current/ddl-partitioning.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Partitioning

## Panoramica

Il partitioning divide una tabella logica in partizioni fisiche indipendenti sullo **stesso nodo**. A differenza dello sharding (distribuzione su nodi diversi), il partitioning è trasparente all'applicazione — il nome della tabella rimane lo stesso, le query funzionano invariate — ma internamente il database può:

- **Pruning**: escludere partizioni intere dalla scansione quando il filtro lo permette
- **Maintenance**: VACUUM, ANALYZE, CREATE INDEX, DROP su singole partizioni invece che sull'intera tabella
- **Data lifecycle**: eliminare dati vecchi droppando una partizione (istantaneo) invece di DELETE (lento, genera bloat)

## Quando Usare il Partitioning

Il partitioning vale la pena quando:
- La tabella supera i 10-50GB (dipende da RAM e access pattern)
- La maggior parte delle query filtra sulla colonna di partitioning (altrimenti non c'è pruning)
- Ci sono operazioni di bulk delete/archive periodiche (es. eliminare dati > 2 anni)
- VACUUM sull'intera tabella diventa un problema operativo

!!! warning "Costo del partitioning"
    Il partitioning aggiunge overhead al planning (il planner deve esaminare le partition metadata) e complessità operativa. Su tabelle con query che non usano la partition key, può peggiorare le performance invece di migliorarle.

---

## Tipi di Partitioning in PostgreSQL

### Range Partitioning

La scelta più comune per serie temporali e dati con progressione naturale:

```sql
-- Tabella padre (solo struttura, nessun dato diretto)
CREATE TABLE log_eventi (
    id         BIGSERIAL,
    timestamp  TIMESTAMPTZ NOT NULL,
    servizio   TEXT,
    livello    TEXT,
    messaggio  TEXT
) PARTITION BY RANGE (timestamp);

-- Partizioni per mese
CREATE TABLE log_eventi_2024_01
    PARTITION OF log_eventi
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE log_eventi_2024_02
    PARTITION OF log_eventi
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ... una per ogni mese ...

-- Partizione default: cattura righe non coperte da nessuna altra partizione
CREATE TABLE log_eventi_default
    PARTITION OF log_eventi DEFAULT;
```

```sql
-- Il planner usa solo la partizione corretta (partition pruning)
EXPLAIN SELECT * FROM log_eventi
WHERE timestamp BETWEEN '2024-01-15' AND '2024-01-20';

-- → Index Scan on log_eventi_2024_01 (solo questa partizione!)
-- → log_eventi_2024_02, _03, ecc. sono skippate completamente
```

### List Partitioning

Per colonne con un set discreto di valori (es. region, tenant, status):

```sql
CREATE TABLE ordini (
    id         BIGSERIAL,
    regione    TEXT NOT NULL,
    importo    NUMERIC,
    created_at TIMESTAMPTZ
) PARTITION BY LIST (regione);

CREATE TABLE ordini_emea   PARTITION OF ordini FOR VALUES IN ('IT', 'DE', 'FR', 'ES', 'UK');
CREATE TABLE ordini_amer   PARTITION OF ordini FOR VALUES IN ('US', 'CA', 'BR', 'MX');
CREATE TABLE ordini_apac   PARTITION OF ordini FOR VALUES IN ('JP', 'AU', 'SG', 'IN');
CREATE TABLE ordini_altri  PARTITION OF ordini DEFAULT;
```

### Hash Partitioning

Distribuisce uniformemente le righe tra un numero fisso di partizioni tramite hash della chiave. Utile quando non c'è un ordinamento naturale ma si vuole distribuire per ridurre la dimensione di ogni partizione:

```sql
CREATE TABLE sessioni (
    id         UUID DEFAULT gen_random_uuid(),
    user_id    BIGINT NOT NULL,
    dati       JSONB,
    created_at TIMESTAMPTZ
) PARTITION BY HASH (user_id);

-- 8 partizioni, distribuzione uniforme
CREATE TABLE sessioni_0 PARTITION OF sessioni FOR VALUES WITH (MODULUS 8, REMAINDER 0);
CREATE TABLE sessioni_1 PARTITION OF sessioni FOR VALUES WITH (MODULUS 8, REMAINDER 1);
-- ... fino a sessioni_7
```

---

## Indici e Partizioni

Gli indici si creano separatamente su ogni partizione (ma PostgreSQL li crea automaticamente sulle partizioni figlie quando si crea l'indice sulla tabella padre):

```sql
-- Indice sulla tabella padre → creato automaticamente su tutte le partizioni
CREATE INDEX idx_log_servizio ON log_eventi (servizio);

-- Crea automaticamente:
--   idx_log_eventi_2024_01_servizio
--   idx_log_eventi_2024_02_servizio
--   ...

-- Index only scan funziona su partizioni individuali
EXPLAIN SELECT servizio, COUNT(*)
FROM log_eventi
WHERE timestamp > '2024-01-01' AND servizio = 'api-gateway'
GROUP BY servizio;
-- → Index Only Scan on log_eventi_2024_01, _2024_02, ... (solo partizioni recenti)
```

---

## Lifecycle Management — Aggiungere e Rimuovere Partizioni

```sql
-- Aggiungere una nuova partizione (operazione fast, nessun lock sulla tabella)
CREATE TABLE log_eventi_2025_01
    PARTITION OF log_eventi
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Eliminare una partizione intera (istantaneo, no bloat, no VACUUM necessario)
DROP TABLE log_eventi_2022_01;  -- Elimina tutti i dati di quel mese in O(1)

-- Detach una partizione (separa dalla tabella padre, diventa tabella indipendente)
ALTER TABLE log_eventi DETACH PARTITION log_eventi_2022_01;
-- Ora log_eventi_2022_01 è una tabella normale — puoi archiviarla su storage più lento

-- Attach una tabella esistente come partizione
ALTER TABLE log_eventi ATTACH PARTITION log_eventi_2025_03
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
```

**Pattern archiving**: invece di DELETE su milioni di righe (lento, genera WAL), fare DETACH e poi DROP o dump su storage S3/cold.

---

## pg_partman — Gestione Automatica delle Partizioni

[pg_partman](https://github.com/pgpartman/pg_partman) è un'estensione che automatizza la creazione e il cleanup delle partizioni:

```sql
-- Installa estensione
CREATE EXTENSION pg_partman SCHEMA partman;

-- Setup partitioning automatico per mese
SELECT partman.create_parent(
    p_parent_table => 'public.log_eventi',
    p_control      => 'timestamp',
    p_type         => 'range',
    p_interval     => 'monthly',
    p_premake      => 3          -- Crea 3 partizioni future in anticipo
);

-- Configura retention (elimina partizioni > 12 mesi)
UPDATE partman.part_config
SET retention            = '12 months',
    retention_keep_table = false  -- DROP invece di DETACH
WHERE parent_table = 'public.log_eventi';

-- Chiama periodicamente (es. da cron ogni ora)
SELECT partman.run_maintenance();
```

---

## Partitioning e Query Cross-Partition

Le query senza filtro sulla partition key toccano tutte le partizioni (full scan distribuito):

```sql
-- EFFICIENTE: filtra sulla partition key → pruning
SELECT * FROM log_eventi
WHERE timestamp > NOW() - INTERVAL '7 days' AND servizio = 'api';
-- → scansiona solo le ultime 7-8 partizioni

-- INEFFICIENTE: nessun filtro sulla partition key
SELECT COUNT(*) FROM log_eventi WHERE livello = 'ERROR';
-- → scansiona TUTTE le partizioni in parallelo (o in sequenza)
-- → considera un indice globale o una tabella summary separata
```

**Parallel query su partizioni**: PostgreSQL può eseguire query multi-partizione in parallelo se `max_parallel_workers_per_gather > 0`. Utile per query analytics.

---

## Partitioning vs Sharding — Quando usare quale

| Aspetto | Partitioning | Sharding |
|---------|-------------|---------|
| Distribuzione | Stesso nodo | Nodi diversi |
| Trasparenza app | Totale | Richiede shard routing |
| Scalabilità | Fino ai limiti del nodo | Orizzontale illimitata |
| Cross-partition ops | JOIN locali, transazioni ACID | JOIN costosi, no ACID semplice |
| Complessità | Bassa-media | Alta |
| Caso d'uso | Tabelle grandi, lifecycle management | Volume > singolo nodo, write throughput estremo |

## Relazioni

??? info "Sharding — Quando il singolo nodo non basta"
    Distribuzione su più nodi quando il partitioning non è sufficiente.

    **Approfondimento →** [Sharding](../fondamentali/sharding.md)

??? info "pg_partman — Gestione operativa"
    Automazione del lifecycle delle partizioni.

    **Approfondimento →** [PostgreSQL Extensions](../postgresql/extensions.md)

## Riferimenti

- [PostgreSQL Declarative Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [pg_partman — Partition Management](https://github.com/pgpartman/pg_partman)
