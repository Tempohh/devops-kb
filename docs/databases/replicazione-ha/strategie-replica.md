---
title: "Strategie di Replica"
slug: strategie-replica
category: databases
tags: [replicazione, alta-disponibilità, rpo, rto, sync, async, read-replica, multi-master]
search_keywords: [synchronous replication, asynchronous replication, semi-synchronous replication, read replica, read scaling, multi-master replication, active-active replication, active-passive replication, rpo zero, replication lag, eventual consistency databases, galera cluster, mysql group replication, postgresql sync commit, replication topology, chain replication, fan-out replication, conflict resolution multi-master]
parent: databases/replicazione-ha/_index
related: [databases/postgresql/replicazione, databases/fondamentali/acid-base-cap, databases/replicazione-ha/failover-recovery]
official_docs: https://www.postgresql.org/docs/current/warm-standby.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Strategie di Replica

## Panoramica

La replica è il meccanismo che copia i dati da un nodo (primary/master) a uno o più nodi secondari (standby/replica/slave). Le strategie differiscono in tre dimensioni:

1. **Timing**: quando il primary considera un write confermato (sync vs async)
2. **Granularità**: cosa viene replicato (fisico vs logico)
3. **Topologia**: come sono connessi i nodi

Ogni scelta è un trade-off tra durabilità, performance e complessità operativa.

## Replica Fisica vs Logica

**WAL** (Write-Ahead Log) è il journal su cui il database scrive ogni modifica prima di applicarla ai data file; è la base della replica.

| | Fisica (streaming) | Logica |
|---|---|---|
| Cosa viaggia | Record WAL a livello di blocco | Modifiche di riga decodificate (INSERT/UPDATE/DELETE) |
| Standby | Copia binaria identica, read-only | Database indipendente, scrivibile |
| Granularità | Intero cluster | Per tabella (publication/subscription) |
| Versioni | Stessa major version | Major version diverse → upgrade senza downtime |
| DDL e sequence | Replicati | **Non** replicati (PostgreSQL) |
| Uso tipico | HA, failover, read replica | Migrazioni, CDC, consolidamento dati, replica selettiva |

**Perché:** la replica fisica riapplica byte-per-byte, quindi è semplice e veloce ma rigida; la logica decodifica le modifiche, quindi è flessibile ma richiede chiave primaria/`REPLICA IDENTITY` e gestione manuale dello schema.

```sql
-- PostgreSQL: replica logica di una tabella (wal_level = logical sul publisher)
CREATE PUBLICATION pub_ordini FOR TABLE ordini;                 -- sul publisher
CREATE SUBSCRIPTION sub_ordini
  CONNECTION 'host=primary dbname=app user=repl'
  PUBLICATION pub_ordini;                                       -- sul subscriber
```

---

## Replicazione Sincrona vs Asincrona

### Asincrona (default in quasi tutti i database)

```
Client               Primary              Standby
  │                     │                    │
  │── COMMIT ──────────>│                    │
  │<── OK ──────────────│                    │
  │                     │── WAL stream ──────>│
  │                     │   (in background)   │ applica WAL
  │                     │                    │
  Commit confermato PRIMA che la standby riceva il dato
  → Performance massima
  → RPO > 0: se primary crasha dopo OK e prima che standby riceva → dati persi
```

**Quando usarla:**
- Latenza di scrittura critica
- RPO > 0 accettabile (es. analytics, log, dati non critici)
- Standby geograficamente distante (latenza rete alta)

### Sincrona

```
Client               Primary              Standby
  │                     │                    │
  │── COMMIT ──────────>│── WAL ────────────>│
  │                     │<── ACK ────────────│
  │<── OK ──────────────│                    │
  │                     │                    │
  Commit confermato SOLO dopo ACK della standby
  → RPO = 0 (nessuna perdita di dati in failover)
  → Latency del commit = latency rete verso standby + ACK
```

**Quando usarla:**
- RPO = 0 obbligatorio (transazioni finanziarie, ordini, dati critici)
- Standby nella stessa AZ o con latenza bassa (< 5ms)

**Costo della replica sincrona:**

```
Esempio: latenza di rete one-way primary→standby = 2ms (RTT = 4ms)
  Commit asincrono: 1ms (solo fsync su disco locale)
  Commit sincrono:  1ms + 4ms (RTT: invio WAL + ACK) = 5ms → 5x più lento
  (se la standby fa anche fsync, aggiungere il suo tempo di flush)

Con 3 standby che devono tutte confermare: il commit attende la più lenta
  → In produzione: 1 standby sync + N async (PostgreSQL: synchronous_standby_names)
```

!!! note "synchronous_commit conta solo con standby sincrone"
    In PostgreSQL `synchronous_commit` (`off` / `local` / `remote_write` / `on` / `remote_apply`) decide *fino a dove* aspettare la standby, ma solo se `synchronous_standby_names` non è vuoto. Con la lista vuota la replica resta asincrona qualunque sia il valore.

### Semi-sincrona

Variante: il primary attende che almeno 1 standby abbia *ricevuto* il WAL (non necessariamente applicato). MySQL/MariaDB chiamano questa modalità "semi-sync" (ACK dopo la scrittura nel relay log; se nessun ACK arriva entro `rpl_semi_sync_source_timeout` il primary degrada ad async). PostgreSQL non ha una modalità "semi-sync" nominata: la gradazione è data da `synchronous_commit` — `remote_write` (WAL scritto dal SO della standby, senza fsync), `on` (WAL flushed su disco della standby), `remote_apply` (WAL applicato, le letture sulla standby vedono già il commit).

```ini
# PostgreSQL — livello intermedio (richiede synchronous_standby_names valorizzato)
synchronous_standby_names = 'FIRST 1 (standby1, standby2)'
synchronous_commit = remote_write   # WAL ricevuto dalla standby, non ancora su disco
# più veloce di 'on' (no fsync sulla standby)
# più lento di 'local'/'off' (attende ACK di rete)
# RPO: perdita possibile solo se primary E standby cadono insieme prima del flush
```

Nota: a differenza di MySQL, PostgreSQL **non** degrada ad async da solo: se la standby sincrona sparisce, i commit si bloccano (vedi Scenario 2).

---

## Topologie di Replica

### Primary + N Standby (Standard)

```
Primary ──┬── Standby 1 (sync, stessa AZ)
          ├── Standby 2 (async, AZ diversa)
          └── Standby 3 (async, regione diversa)

Pro: semplice, well-supported, failover automatico chiaro
Contro: write scalability limitata al primary
Uso: PostgreSQL + Patroni, MySQL + Orchestrator
```

### Cascading Replication

```
Primary ── Standby 1 ── Standby 2 ── Standby 3

Standby 1 replica dal Primary; Standby 2 e 3 replicano da Standby 1
Pro: riduce il load di WAL sul primary (un solo WAL sender)
Contro: lag aumenta lungo la catena; failover più complesso
Uso: molte standby geograficamente distribuite
```

### Read Replicas — Scaling delle Letture

```
           ┌── Read Replica 1 ◄── letture app
Primary ───┤── Read Replica 2 ◄── letture app
           └── Read Replica 3 ◄── letture reporting
           │
           └── Standby HA (non esposta alle app — solo failover)

Pro: scala le letture orizzontalmente
Contro: replica lag → read stale possibili (eventual consistency)
Uso: AWS RDS Read Replicas, Aurora Read Replicas, GCP Cloud SQL replicas
```

!!! note "Aurora è diversa"
    RDS e Cloud SQL replicano il log al singolo standby. Le Aurora Replicas leggono invece lo **stesso storage distribuito** del writer: il lag è tipicamente di decine di ms e non c'è WAL da riapplicare sulla replica.

**Pattern applicativo per read replicas:**

```python
# Routing automatico read/write
class DBRouter:
    def __init__(self):
        self.primary = psycopg2.connect(PRIMARY_DSN)
        self.replicas = [psycopg2.connect(r) for r in REPLICA_DSNS]
        self._replica_idx = 0

    def write(self):
        return self.primary

    def read(self):
        # Round-robin tra repliche
        conn = self.replicas[self._replica_idx % len(self.replicas)]
        self._replica_idx += 1
        return conn

# ATTENZIONE: read-your-own-writes
# Dopo un write, leggi dal primary per evitare read stale
def aggiorna_utente(user_id, dati):
    with db.write() as conn:
        conn.execute("UPDATE utenti SET ... WHERE id = %s", (user_id,))
        conn.commit()
    # Leggi dal primary per conferma immediata
    return conn.execute("SELECT * FROM utenti WHERE id = %s", (user_id,)).fetchone()
```

### Multi-Master (Active-Active)

```
Master A ◄──────── replication ────────► Master B
   │                (bidirezionale)           │
   │ write                              write │
   ▼                                         ▼
App Server A                          App Server B

Entrambi i nodi accettano write contemporaneamente
```

Il problema del multi-master è la **gestione dei conflitti**: se Master A e B aggiornano contemporaneamente la stessa riga, quale vince?

**Strategie di risoluzione conflitti:**
- **Last-Write-Wins (LWW)**: vince il timestamp più recente. Semplice, ma può perdere write legittime
- **Application-level resolution**: il conflitto viene rilevato e passato all'applicazione (es. CouchDB: sceglie un vincitore deterministico ma conserva le revisioni in conflitto da risolvere)
- **CRDT (Conflict-free Replicated Data Types)**: strutture dati matematicamente prive di conflitti (contatori, set) — usati in Riak e Redis Enterprise/Redis Cloud Active-Active (non in Redis Cluster open source, che è single-writer per shard)
- **Serializable consistency**: coordinamento distribuito (2PC, Paxos) — elimina conflitti ma sacrifica disponibilità

**Quando usare multi-master:**
- Active-active geografico obbligatorio (disaster recovery senza downtime)
- Write throughput > capacità di un singolo nodo (raro con hardware moderno)
- Galera Cluster (MariaDB/Percona XtraDB), MySQL Group Replication in modalità multi-primary, CockroachDB, YugabyteDB (questi ultimi due: consenso Raft per range, non vero multi-master LWW)
- PostgreSQL nativo **non** offre multi-master: servono estensioni/prodotti (pglogical, EDB Postgres Distributed/BDR, pgEdge). Patroni gestisce solo topologie single-primary.

---

## RPO e RTO — Definire i Requisiti

```
RPO (Recovery Point Objective) = quanto dato puoi perdere
RTO (Recovery Time Objective)  = quanto downtime puoi tollerare

        Write accettate                Failover
             │                            │
─────────────┼────────────────────────────┼──────────────► tempo
             │◄── RPO ───►│               │
         Ultimo backup  Crash          Servizio
          / replica                    ripreso
                              │◄── RTO ───►│
```

**Matrice RPO/RTO:**

| RPO | RTO | Strategia | Costo |
|-----|-----|-----------|-------|
| 0 | < 30s | Sync replica + Patroni | Alto |
| < 1 min | < 2 min | Async replica + Patroni | Medio-alto |
| < 15 min | < 30 min | Async replica + failover manuale | Medio |
| < 1 ora | Ore | Backup orario su S3 + PITR | Basso |
| Giorni | Giorni | Backup giornaliero | Minimo |

---

## Monitoring del Lag di Replica

Il lag è il ritardo tra il momento in cui un dato viene scritto sul primary e il momento in cui è disponibile sulla standby:

```sql
-- PostgreSQL: lag su tutte le standby (dal primary)
SELECT
    client_addr,
    state,
    sync_state,
    pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)   AS send_lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), write_lsn)  AS write_lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn)  AS flush_lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;

-- Dalla standby: quanti secondi di lag
SELECT
    now() - pg_last_xact_replay_timestamp() AS replica_lag_seconds,
    pg_is_in_recovery()                      AS is_standby;
-- ATTENZIONE: se il primary è idle (nessuna transazione) questo valore cresce
-- senza che ci sia vero lag. Incrociare con i byte di lag (pg_stat_replication).
```

```yaml
# Alert Prometheus — lag > 30s (metrica di postgres_exporter; il nome esatto
# dipende da versione/query custom: verificare sul proprio /metrics)
- alert: ReplicationLagHigh
  expr: pg_replication_lag_seconds > 30
  for: 2m
  annotations:
    summary: "PostgreSQL replica lag {{ $value }}s — rischio RPO violato"
```

## Troubleshooting

### Scenario 1 — Replica lag in crescita costante

**Sintomo:** `replica_lag_seconds` aumenta nel tempo; le read replica servono dati sempre più vecchi; alert `ReplicationLagHigh` continuo.

**Causa:** Il primary genera WAL più velocemente di quanto la standby riesca ad applicarlo. Cause tipiche: query pesanti sulla standby (hot standby conflict), I/O della standby saturo, standby sotto-dimensionata.

**Soluzione:**
```sql
-- 1. Verificare il lag corrente e lo stato di replica
SELECT client_addr, state, sync_state,
       replay_lag, write_lag, flush_lag
FROM pg_stat_replication;

-- 2. Sulla standby: query lunghe e conflitti di recovery
SELECT pid, now() - query_start AS durata, state, query
FROM pg_stat_activity
WHERE state <> 'idle' ORDER BY durata DESC;

SELECT datname, confl_snapshot, confl_lock, confl_bufferpin
FROM pg_stat_database_conflicts;

-- 3. Opzioni (postgresql.conf della standby):
-- max_standby_streaming_delay = 120s  -- il replay aspetta le query fino a 120s:
--                                     -- meno query cancellate, MA più lag (default 30s)
-- hot_standby_feedback = on           -- il primary non fa VACUUM di righe ancora
--                                     -- viste dalla standby: meno cancellazioni,
--                                     -- ma possibile bloat sul primary
-- In alternativa: spostare il reporting pesante su una replica dedicata.

-- 4. Se la standby è I/O bound: pg_stat_io (PostgreSQL 16+) oppure iostat/iotop sull'host
```

---

### Scenario 2 — Primary bloccato: standby sincrona non raggiungibile

**Sintomo:** Tutti i COMMIT si bloccano indefinitamente. Nessun nuovo write riesce. La standby sincrona è offline o irraggiungibile dalla rete.

**Causa:** Con `synchronous_commit = on`, il primary attende l'ACK di almeno una standby sincrona. Se nessuna standby è disponibile, il commit si blocca finché non ne ritorna una.

**Soluzione:**
```sql
-- 1. Verificare quali standby sono connesse
SELECT application_name, client_addr, state, sync_state
FROM pg_stat_replication;

-- 2. Fallback temporaneo: disabilitare replica sincrona
-- (OPERAZIONE CRITICA: RPO > 0 fino al ripristino della standby)
ALTER SYSTEM SET synchronous_standby_names = '';
SELECT pg_reload_conf();

-- 3. Verificare che i commit sbloccati
-- Poi ripristinare la standby e riabilitare:
ALTER SYSTEM SET synchronous_standby_names = 'standby1';
SELECT pg_reload_conf();

-- 4. Per evitare blocchi futuri: elencare più candidate, basta che 1 risponda
-- synchronous_standby_names = 'FIRST 1 (standby1, standby2)'  -- per priorità
-- synchronous_standby_names = 'ANY 1 (standby1, standby2)'    -- quorum
-- (con un solo nome in lista, quella standby è un single point of failure per i commit)
```

---

### Scenario 3 — Replica slot inattivo: WAL accumulation e disco pieno

**Sintomo:** Il disco del primary si riempie di file WAL. `pg_wal/` cresce senza stop. La standby associata allo slot non è connessa.

**Causa:** I replication slot garantiscono che il WAL non venga rimosso finché la standby non lo consuma. Se la standby è offline a lungo, il WAL si accumula sul primary.

**Soluzione:**
```sql
-- 1. Identificare gli slot inattivi e il WAL trattenuto
SELECT slot_name, active, pg_size_pretty(
    pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
) AS wal_retained
FROM pg_replication_slots
ORDER BY wal_retained DESC;

-- 2. Se la standby non tornerà presto → droppare lo slot
-- (la standby dovrà fare base backup + resync)
SELECT pg_drop_replication_slot('nome_slot');

-- 3. Prevenzione: impostare un limite di WAL trattenuto
-- In postgresql.conf:
-- max_slot_wal_keep_size = 10GB   -- PostgreSQL 13+
-- Oltre questo limite lo slot viene invalidato automaticamente

-- 4. Verificare che il WAL venga liberato dopo il drop
SELECT pg_walfile_name(pg_current_wal_lsn());
```

---

### Scenario 4 — Split-brain in topologia multi-master

**Sintomo:** Dopo una partizione di rete i nodi non formano più un cluster unico. In Galera i nodi in minoranza passano a `wsrep_cluster_status = non-Primary` e rifiutano query (`WSREP has not yet prepared node for application use`); con un cluster a 2 nodi, o dopo il crash simultaneo di tutti i nodi, nessuno ha il quorum. Nei sistemi multi-master senza quorum (LWW) le righe divergono davvero.

**Causa:** Partizione di rete tra i nodi. Galera applica il quorum: la minoranza si auto-sospende invece di divergere (scelta CP del teorema CAP), quindi il rischio reale è l'**indisponibilità** e la necessità di un bootstrap manuale. Il vero split-brain con dati divergenti avviene in sistemi senza quorum o forzando `pc.bootstrap` su entrambi i lati.

**Soluzione:**
```bash
# 1. Verificare stato del cluster Galera
mysql -e "SHOW STATUS LIKE 'wsrep_%';" | grep -E "cluster_size|cluster_status|local_state|ready"
# wsrep_cluster_status deve essere Primary; cluster_size >= quorum (N/2 + 1)
# Se una componente ha ancora quorum, NON fare bootstrap: i nodi rientrano da soli.

# 2. Identificare il nodo con dati più aggiornati (seqno più alto)
mysql -e "SHOW STATUS LIKE 'wsrep_last_committed';"

# 3. Forzare il bootstrap dal nodo più aggiornato
# Sul nodo con seqno più alto, editare /var/lib/mysql/grastate.dat:
# safe_to_bootstrap: 1
# Poi riavviare come bootstrap:
galera_new_cluster   # oppure: mysqld --wsrep-new-cluster

# 4. Aggiungere gli altri nodi (si sincronizzano via SST/IST)
systemctl start mysql   # sui nodi secondari

# 5. Prevenzione: usare numero dispari di nodi (3, 5) e un arbitro
# per garantire sempre il quorum in caso di partizione
```

## Relazioni

??? info "PostgreSQL Replicazione — Implementazione"
    Streaming replication, replication slots, synchronous_commit, Patroni.

    **Approfondimento →** [PostgreSQL Replicazione](../postgresql/replicazione.md)

??? info "Failover e Recovery — Gestire l'interruzione"
    Come il failover automatico funziona in pratica con Patroni.

    **Approfondimento →** [Failover e Recovery](failover-recovery.md)

??? info "ACID, BASE, CAP — Fondamenti teorici"
    Il teorema CAP e PACELC spiegano i trade-off di consistenza in sistemi distribuiti.

    **Approfondimento →** [ACID, BASE, CAP](../fondamentali/acid-base-cap.md)

## Riferimenti

- [PostgreSQL High Availability](https://www.postgresql.org/docs/current/high-availability.html)
- [AWS — Replication in RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [Designing Data-Intensive Applications — Martin Kleppmann (cap. 5)](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/)
