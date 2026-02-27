---
title: "Apache Cassandra"
slug: cassandra
category: databases
tags: [cassandra, nosql, wide-column, distributed, consistency, compaction]
search_keywords: [apache cassandra, cassandra data modeling, cassandra partition key, clustering key, cassandra consistency levels, quorum consistency, cassandra replication factor, cassandra compaction, leveled compaction, size tiered compaction, cassandra read repair, hinted handoff, cassandra tombstone, cassandra cql, cassandra materialized views, cassandra secondary index, cassandra vnodes, gossip protocol, cassandra nodetool, datastax, cassandra write path, memtable sstable, bloom filter cassandra, cassandra time series, cassandra write heavy, cassandra vs mongodb]
parent: databases/nosql/_index
related: [databases/fondamentali/acid-base-cap, databases/fondamentali/sharding, databases/nosql/mongodb]
official_docs: https://cassandra.apache.org/doc/latest/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Apache Cassandra

## Panoramica

Cassandra è un database distribuito wide-column progettato da Facebook per gestire l'inbox search — miliardi di record, write intensive, nessun single point of failure. Il suo modello di distribuzione è **leaderless** (ogni nodo è uguale), il che permette write throughput praticamente lineare aggiungendo nodi.

Cassandra sacrifica la flessibilità delle query sull'altare della scalabilità: **il modello di dati deve essere progettato in funzione delle query**, non della struttura dei dati. Una query che non usa la partition key diventa una full scan costosa. Questo inverte completamente il processo di progettazione rispetto a SQL o MongoDB.

**Cassandra è ottimale per:**
- Write ad alto throughput (IoT, telemetria, event sourcing, time series)
- Dataset che non entrano in un singolo nodo (TB-PB scale)
- Disponibilità sempre-on (nessun SPOF, downtime zero per manutenzione)

**Cassandra è sbagliata per:**
- Query ad hoc su campi arbitrari
- JOIN o aggregazioni complesse
- Dataset piccoli o write poco frequenti (PostgreSQL è più semplice e capace)

## Architettura

### Ring e Consistent Hashing

```
         Token Ring (hash dei partition key)

              Node A (tok 0-85)
             /                 \
    Node D (tok 255-85)    Node B (tok 85-170)
             \                 /
              Node C (tok 170-255)

Replication Factor = 3:
  Una row con partition key hash=100 → B, C, D (3 repliche consecutive)
```

Ogni nodo gestisce un range di token. Con Virtual Nodes (vnodes), ogni nodo fisico possiede ~256 token virtuali distribuiti sul ring — bilanciamento automatico anche con nodi eterogenei.

### Write Path

```
1. Client scrive su qualsiasi nodo (Coordinator)
2. Coordinator calcola: hash(partition_key) → nodo responsabile
3. Scrive in parallelo su RF nodi
4. Ogni nodo:
   a. Scrive sul CommitLog (durabilità on-disk)
   b. Scrive sulla Memtable (in-memory)
5. Quando Memtable è piena → flush su SSTable (immutabile su disco)
6. Compaction: unisce SSTable multiple in background
```

Le write Cassandra sono **append-only** — non c'è update in-place. Un UPDATE è in realtà un nuovo record con timestamp più recente; la versione vecchia viene eliminata durante la compaction.

### Read Path

```
1. Coordinator riceve query
2. Determina nodi responsabili (partition key)
3. Invia richiesta ai nodi (secondo consistency level)
4. Ogni nodo:
   a. Controlla Memtable (più recente)
   b. Controlla Row Cache (se abilitata)
   c. Consulta Bloom Filter → se probabile hit, legge SSTable
   d. Merge dei risultati da più SSTable (per timestamp)
5. Coordinator riceve risposte, ritorna la versione più recente
```

Le **tombstone** sono il meccanismo di cancellazione: un DELETE crea una tombstone con timestamp, non elimina immediatamente il dato. La compaction rimuove fisicamente i dati cancellati.

---

## Data Modeling — Query-First Design

### Regole Fondamentali

1. **Progetta la tabella in funzione della query, non dei dati** — crea tabelle denormalizzate, una per ogni pattern di accesso
2. **La partition key determina dove vivono i dati** — tutte le row con la stessa partition key stanno sullo stesso nodo
3. **La clustering key ordina i dati all'interno della partizione** — permette range query efficienti
4. **No JOIN**: denormalizza, duplica i dati se necessario
5. **Partizioni grandi sono un problema**: una singola partizione non può essere distribuita — tenerle sotto 100MB/100K row

### Esempio: Feed Attività Utente

```sql
-- Obiettivo query: "dammi le ultime 50 attività dell'utente X"

-- SCHEMA ERRATO (pensa come SQL, non funziona in Cassandra):
CREATE TABLE attivita (
    id UUID PRIMARY KEY,
    user_id UUID,
    tipo TEXT,
    timestamp TIMESTAMP
);
-- Problema: filtrare per user_id → full scan

-- SCHEMA CORRETTO (query-first):
CREATE TABLE attivita_per_utente (
    user_id UUID,
    timestamp TIMESTAMP,
    id UUID,
    tipo TEXT,
    metadati MAP<TEXT, TEXT>,
    PRIMARY KEY ((user_id), timestamp, id)
-- ↑ partition key     ↑ clustering key (ordine decrescente per default → recenti prima)
) WITH CLUSTERING ORDER BY (timestamp DESC, id DESC);

-- La query ora è efficiente:
SELECT * FROM attivita_per_utente
WHERE user_id = f47ac10b-58cc-4372-a567-0e02b2c3d479
LIMIT 50;
-- → accede a una singola partizione, legge i primi 50 record (già ordinati)
```

### Time Series con Bucketing

```sql
-- Problema: una partizione per sensore cresce infinitamente nel tempo
-- Soluzione: bucket per mese (partizione limitata)

CREATE TABLE metriche_sensore (
    sensor_id TEXT,
    bucket    TEXT,           -- es. '2024-01' (mese)
    timestamp TIMESTAMP,
    valore    DOUBLE,
    PRIMARY KEY ((sensor_id, bucket), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC);

-- Insert
INSERT INTO metriche_sensore (sensor_id, bucket, timestamp, valore)
VALUES ('sensor-42', '2024-01', toTimestamp(now()), 73.2);

-- Query ultime 24h (bucket corrente)
SELECT * FROM metriche_sensore
WHERE sensor_id = 'sensor-42'
  AND bucket = '2024-01'
  AND timestamp >= '2024-01-15 00:00:00'
LIMIT 1440;
```

---

## Consistency Levels

Cassandra permette di scegliere il trade-off CAP per ogni operazione:

| Consistency Level | Write (quante repliche) | Read (quante repliche) | Note |
|-------------------|------------------------|------------------------|------|
| `ANY` | 1 (anche hinted handoff) | — | Disponibilità massima |
| `ONE` | 1 | 1 | Write/read velocissime |
| `QUORUM` | majority (RF/2+1) | majority | **Bilancio consigliato** |
| `LOCAL_QUORUM` | majority (datacenter locale) | majority locale | Multi-DC |
| `ALL` | tutte | tutte | Consistenza forte, bassa disponibilità |

**Quorum**: con RF=3, quorum=2. Se scivi con `QUORUM` e leggi con `QUORUM`, hai **strong consistency** garantita (i set si sovrappongono).

```python
from cassandra.cluster import Cluster, ConsistencyLevel
from cassandra.query import SimpleStatement

cluster = Cluster(['cassandra1', 'cassandra2', 'cassandra3'])
session = cluster.connect('mio_keyspace')

# Write con quorum
insert = SimpleStatement(
    "INSERT INTO metriche_sensore (sensor_id, bucket, timestamp, valore) VALUES (%s, %s, %s, %s)",
    consistency_level=ConsistencyLevel.LOCAL_QUORUM
)
session.execute(insert, ('sensor-42', '2024-01', datetime.now(), 73.2))

# Read con quorum
select = SimpleStatement(
    "SELECT * FROM metriche_sensore WHERE sensor_id=%s AND bucket=%s LIMIT 100",
    consistency_level=ConsistencyLevel.LOCAL_QUORUM
)
rows = session.execute(select, ('sensor-42', '2024-01'))
```

---

## Configurazione e Operazioni

### Keyspace e Replication

```sql
-- Crea keyspace con replication strategy
-- SimpleStrategy: singolo datacenter
CREATE KEYSPACE mio_app
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 3};

-- NetworkTopologyStrategy: multi-datacenter (produzione)
CREATE KEYSPACE mio_app
    WITH replication = {
        'class': 'NetworkTopologyStrategy',
        'dc-east': 3,
        'dc-west': 2
    };

-- Verifica
DESCRIBE KEYSPACE mio_app;
```

### CQL Essenziali

```sql
-- Tipi di dato CQL
CREATE TABLE esempio (
    id      UUID DEFAULT uuid(),
    nome    TEXT,
    counter COUNTER,        -- tipo speciale, solo INCR/DECR
    tags    SET<TEXT>,      -- insieme di valori unici
    metadati MAP<TEXT, TEXT>, -- key-value
    storico LIST<TEXT>,     -- lista ordinata
    PRIMARY KEY (id)
);

-- Batch atomico (solo same partition, limitate operazioni)
BEGIN BATCH
    INSERT INTO utenti (id, nome) VALUES (uuid(), 'Alice');
    INSERT INTO utenti_per_email (email, id) VALUES ('alice@ex.com', uuid());
APPLY BATCH;

-- Lightweight Transaction (CAS — Compare and Swap)
-- Solo quando strettamente necessario: ha overhead (~4x)
INSERT INTO sessioni (id, user_id) VALUES (uuid(), 'user-1')
IF NOT EXISTS;   -- atomico, nessun duplicato

UPDATE account SET saldo = 900
WHERE id = 'acc-1'
IF saldo = 1000;   -- update solo se valore attuale è 1000
```

### Compaction Strategies

```sql
-- STCS (SizeTieredCompactionStrategy) — default
-- Unisce SSTable di dimensioni simili. Ottimo per write-heavy, ma usa più spazio durante compaction
ALTER TABLE metriche_sensore
    WITH compaction = {'class': 'SizeTieredCompactionStrategy', 'min_threshold': 4};

-- LCS (LeveledCompactionStrategy)
-- Mantiene i dati in livelli dimensionati. Meglio per read-heavy, overhead I/O costante
ALTER TABLE catalogo_prodotti
    WITH compaction = {'class': 'LeveledCompactionStrategy', 'sstable_size_in_mb': 160};

-- TWCS (TimeWindowCompactionStrategy) — per time series
-- Crea una finestra di compaction per ogni periodo temporale (minuti, ore, giorni)
-- Elimina efficientemente dati scaduti (TTL) senza dover leggere SSTable misti
ALTER TABLE metriche_sensore
    WITH compaction = {
        'class': 'TimeWindowCompactionStrategy',
        'compaction_window_unit': 'DAYS',
        'compaction_window_size': 1        -- una finestra per giorno
    }
    AND default_time_to_live = 7776000;    -- TTL: 90 giorni
```

### nodetool — Operazioni Cluster

```bash
# Stato del cluster
nodetool status
# Output:
# DC: datacenter1
# UN → Up Normal (nodo operativo)
# DN → Down Normal (nodo irraggiungibile)
# Status=U(p)/D(own), State=N(ormal)/L(eaving)/J(oining)

nodetool info      # info sul nodo corrente (memoria, cache hit, compaction)
nodetool tpstats   # thread pool stats (coda operazioni)

# Repair: sincronizza dati tra repliche (eseguire regolarmente)
nodetool repair mio_keyspace

# Compaction manuale
nodetool compact mio_keyspace metriche_sensore

# Flush memtable su disco
nodetool flush

# Decommission nodo (rimuovi gracefully dal cluster)
nodetool decommission

# Diagnostica tombstone
nodetool tablestats mio_keyspace.metriche_sensore | grep "Tombstone"
```

---

## Tombstone e Garbage Collection

Le tombstone sono uno dei problemi operativi più comuni in Cassandra:

```
Un DELETE → crea una tombstone (record di cancellazione con timestamp)
La compaction rimuove fisicamente i dati dopo gc_grace_seconds (default: 10 giorni)

PROBLEMA: query che attraversano molte tombstone → timeout, "too many tombstones"
CAUSE: DELETE frequenti, TTL su molte righe, materialized views

SOLUZIONE:
1. Ridurre gc_grace_seconds su tabelle con molti delete (con attenzione: riduce la finestra di repair)
2. Usare TTL invece di DELETE quando possibile
3. Usare TWCS su time series (compaction per finestra temporale elimina tombstone efficientemente)
4. Monitorare tombstone_warn_threshold e tombstone_fail_threshold in cassandra.yaml
```

```sql
-- Imposta TTL per gestire lifecycle dati senza tombstone eccessive
INSERT INTO sessioni (id, user_id, data) VALUES (uuid(), 'u1', '...')
USING TTL 86400;   -- scade dopo 24h

-- TTL su tutta la tabella
ALTER TABLE log_eventi WITH default_time_to_live = 2592000;  -- 30 giorni
```

---

## Best Practices

- **Query-first design è non negoziabile**: creare una tabella per ogni query pattern. La duplicazione dei dati è normale e attesa in Cassandra
- **Partition size**: tenere partizioni < 100MB e < 100K righe. Partizioni enormi causano hotspot, read lente e problemi di compaction
- **TWCS per time series**: è l'unica strategia di compaction sensata per dati temporali con TTL
- **Repair regolare**: senza repair, dopo un nodo down i dati replicati possono divergere (eventual consistency). `nodetool repair` settimanale è la norma
- **Evitare ALLOW FILTERING**: `ALLOW FILTERING` forza una full scan di partizione/tabella — pericoloso in produzione su dataset grandi

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| `ReadTimeoutException` | Partizione troppo grande, tombstone eccessive | Analizzare partition size, ridurre tombstone |
| `TombstoneOverwhelmingException` | Troppe tombstone attraversate | Rivedere pattern delete, usare TTL/TWCS |
| Nodo lento (UN ma lento) | Compaction in corso, GC pause | `nodetool tpstats`, aumentare heap JVM, ottimizzare compaction |
| Write latenza alta | Nodi sotto load, coordinatore lontano | Token aware policy sul client, aggiungere nodi |
| Read inconsistente | Repair mancante dopo nodo down | `nodetool repair` sul keyspace |

## Riferimenti

- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/)
- [DataStax — Cassandra Data Modeling](https://www.datastax.com/learn/data-modeling-by-example)
- [Cassandra: The Definitive Guide](https://www.oreilly.com/library/view/cassandra-the-definitive/9781098115159/)
- [Awesome Cassandra](https://github.com/Anant/awesome-cassandra)
