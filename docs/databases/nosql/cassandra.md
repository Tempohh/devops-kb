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
last_updated: 2026-03-29
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

### Scenario 1 — ReadTimeoutException sulle query

**Sintomo:** Le query restituiscono `com.datastax.driver.core.exceptions.ReadTimeoutException` in modo intermittente o sistematico su tabelle specifiche.

**Causa:** Partizione troppo grande (hotspot su singolo nodo), eccesso di tombstone attraversate durante la lettura, o nodo replica non raggiungibile.

**Soluzione:** Identificare la dimensione della partizione e il conteggio tombstone, poi intervenire sulla data model o sui parametri di compaction.

```bash
# Verifica dimensione partizioni e tombstone per tabella
nodetool tablestats mio_keyspace.metriche_sensore

# Cerca le partizioni più grandi (richiede accesso SSTable)
nodetool getendpoints mio_keyspace metriche_sensore "sensor-42"

# Analisi tombstone a livello SSTable (offline)
sstable2json /var/lib/cassandra/data/mio_keyspace/metriche_sensore-*/mc-1-big-Data.db \
  | python3 -c "import sys,json; [print(r) for r in json.load(sys.stdin) if r.get('deletedAt')]" | head -50

# Aumenta timeout lettura in cassandra.yaml (workaround temporaneo)
# read_request_timeout_in_ms: 10000   # default 5000ms
```

```sql
-- Diagnostica: quante righe ha una partizione specifica?
SELECT COUNT(*) FROM metriche_sensore
WHERE sensor_id = 'sensor-42' AND bucket = '2024-01';

-- Se partizioni enormi: rivedere bucketing più granulare (es. per giorno)
-- Soluzione strutturale: aggiungere campo bucket giornaliero alla partition key
```

---

### Scenario 2 — TombstoneOverwhelmingException

**Sintomo:** Le query falliscono con `TombstoneOverwhelmingException: Query over table ... has more than 100000 tombstones`. I log mostrano anche warning con soglie inferiori.

**Causa:** DELETE frequenti o TTL su molte righe creano tombstone che la compaction non ha ancora eliminato. Le query range attraversano migliaia di tombstone prima di trovare dati validi.

**Soluzione:** Intervenire sulla strategia di compaction (TWCS per time series), ridurre `gc_grace_seconds` con cautela, e monitorare le soglie.

```bash
# Vedi tombstone count per tabella
nodetool tablestats mio_keyspace.metriche_sensore | grep -i tomb

# Forza compaction immediata per liberare tombstone
nodetool compact mio_keyspace metriche_sensore

# Controlla i threshold in cassandra.yaml
grep -i tombstone /etc/cassandra/cassandra.yaml
# tombstone_warn_threshold: 1000
# tombstone_fail_threshold: 100000
```

```sql
-- Passa a TWCS per time series: compatta per finestra temporale,
-- le tombstone vengono eliminate intera finestra alla volta
ALTER TABLE metriche_sensore
    WITH compaction = {
        'class': 'TimeWindowCompactionStrategy',
        'compaction_window_unit': 'DAYS',
        'compaction_window_size': 1
    }
    AND default_time_to_live = 2592000;  -- 30 giorni TTL

-- Riduci gc_grace_seconds su tabelle con delete frequenti
-- (solo se repair è eseguito più spesso di gc_grace_seconds)
ALTER TABLE log_eventi WITH gc_grace_seconds = 86400;  -- 1 giorno invece di 10
```

---

### Scenario 3 — Nodo lento o thread pool in saturazione

**Sintomo:** `nodetool status` mostra il nodo come `UN` (Up Normal) ma le latenze sono alte, o `nodetool tpstats` mostra `Pending` o `Blocked` tasks nelle thread pool.

**Causa:** Compaction in corso che consuma I/O, GC pause JVM (heap insufficiente), o coda di operazioni satura (es. `MutationStage` o `ReadStage` bloccati).

**Soluzione:** Ottimizzare heap JVM, limitare la concorrenza della compaction, verificare I/O.

```bash
# Stato thread pool (cerca Pending > 0 o Blocked > 0)
nodetool tpstats

# Compaction in corso e percentuale completamento
nodetool compactionstats

# Limita compaction throughput per ridurre impatto I/O
nodetool setcompactionthroughput 64   # MB/s (default 64, 0 = illimitato)

# GC pause: controlla i log Cassandra
grep -i "gc" /var/log/cassandra/system.log | tail -50

# Verifica heap JVM (da jvm.options o cassandra-env.sh)
# Regola: heap = min(1/4 RAM, 8GB). Per server con 32GB → MAX_HEAP_SIZE=8G
grep -i "heap" /etc/cassandra/jvm.options

# I/O stats per identificare saturazione disco
iostat -x 1 10
```

---

### Scenario 4 — Dati inconsistenti dopo nodo down

**Sintomo:** Dopo che un nodo è stato down per un periodo, le letture con `LOCAL_QUORUM` restituiscono dati obsoleti o mancanti. Oppure `nodetool repair` mostra differenze tra repliche.

**Causa:** Durante il downtime, il nodo non ha ricevuto le write indirizzate a lui. L'**hinted handoff** copre solo brevi interruzioni (default: 3h). Se il downtime supera questa finestra, le repliche divergono.

**Soluzione:** Eseguire `nodetool repair` dopo ogni intervento su un nodo. Monitorare il repair coverage regolarmente.

```bash
# Repair sul keyspace specifico (può essere lungo su dataset grandi)
nodetool repair mio_keyspace

# Repair su singola tabella (più veloce per test)
nodetool repair mio_keyspace metriche_sensore

# Repair incrementale (solo cambiamenti dall'ultimo repair — Cassandra 4+)
nodetool repair --incremental mio_keyspace

# Verifica che l'hinted handoff sia attivo e controlla i pending hint
nodetool info | grep "Dropped Hints"
nodetool tpstats | grep "HintedHandoff"

# Monitora i repair in corso
nodetool compactionstats  # i repair appaiono come compaction di tipo "VALIDATION"
```

```yaml
# cassandra.yaml — parametri hinted handoff
hinted_handoff_enabled: true
max_hint_window_in_ms: 10800000   # 3 ore (aumentare se downtime frequenti)
hinted_handoff_throttle_in_kb: 1024
```

---

### Scenario 5 — Write latenza alta e hotspot

**Sintomo:** Le write latenze aumentano su specifiche partizioni, mentre altre partizioni rimangono veloci. `nodetool status` mostra distribuzione sbilanciata del load.

**Causa:** **Hotspot**: la partition key scelta concentra le write su pochi nodi (es. partition key con bassa cardinalità come `country_code`, o timestamp come partition key). Con vnodes mal configurati, il bilanciamento può essere sub-ottimale.

**Soluzione:** Rivedere la partition key, aggiungere un campo di salting/bucketing, verificare la distribuzione dei token.

```bash
# Vedi la distribuzione dei dati per nodo (ownership percentuale)
nodetool status mio_keyspace

# Verifica distribuzione token (output esteso con ownership)
nodetool ring mio_keyspace | head -40

# Se distribuzione sbilanciata dopo aggiunta di nodi → ribalancia
nodetool rebalance   # Cassandra 4.1+

# Token aware policy nel driver Python (write diretta al nodo proprietario)
```

```python
from cassandra.cluster import Cluster
from cassandra.policies import TokenAwarePolicy, DCAwareRoundRobinPolicy

cluster = Cluster(
    ['cassandra1', 'cassandra2'],
    load_balancing_policy=TokenAwarePolicy(
        DCAwareRoundRobinPolicy(local_dc='datacenter1')
    )
)
# Token-aware routing: il coordinator è il nodo proprietario della partizione
# → elimina un hop di rete, riduce latenza write del 30-50%
```

## Riferimenti

- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/)
- [DataStax — Cassandra Data Modeling](https://www.datastax.com/learn/data-modeling-by-example)
- [Cassandra: The Definitive Guide](https://www.oreilly.com/library/view/cassandra-the-definitive/9781098115159/)
- [Awesome Cassandra](https://github.com/Anant/awesome-cassandra)
