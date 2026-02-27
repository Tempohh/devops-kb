---
title: "Strategie di Replica"
slug: strategie-replica
category: databases
tags: [replicazione, alta-disponibilità, rpo, rto, sync, async, read-replica, multi-master]
search_keywords: [synchronous replication, asynchronous replication, semi-synchronous replication, read replica, read scaling, multi-master replication, active-active replication, active-passive replication, rpo zero, replication lag, eventual consistency databases, galera cluster, mysql group replication, postgresql sync commit, replication topology, chain replication, fan-out replication, conflict resolution multi-master]
parent: databases/replicazione-ha/_index
related: [databases/postgresql/replicazione, databases/fondamentali/acid-base-cap, databases/replicazione-ha/failover-recovery]
official_docs: https://www.postgresql.org/docs/current/warm-standby.html
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Strategie di Replica

## Panoramica

La replica è il meccanismo che copia i dati da un nodo (primary/master) a uno o più nodi secondari (standby/replica/slave). Le strategie differiscono in tre dimensioni:

1. **Timing**: quando il primary considera un write confermato (sync vs async)
2. **Granularità**: cosa viene replicato (fisico vs logico)
3. **Topologia**: come sono connessi i nodi

Ogni scelta è un trade-off tra durabilità, performance e complessità operativa.

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
Esempio: latenza rete primary→standby = 2ms
  Commit asincrono: 1ms (solo disco locale)
  Commit sincrono:  1ms + 2ms + 2ms (RTT) = 5ms → 5x più lento

Con 3 standby sincrone: il commit attende la più lenta
  → In produzione: 1 standby sync + N async (PostgreSQL: synchronous_standby_names)
```

### Semi-sincrona

Variante: il primary attende che almeno 1 standby abbia ricevuto il WAL (non necessariamente applicato). MySQL/MariaDB chiamano questa modalità "semi-sync". PostgreSQL ha `remote_write` (WAL ricevuto) vs `remote_apply` (WAL applicato).

```ini
# PostgreSQL — modalità semi-sincrona
synchronous_commit = remote_write   # WAL ricevuto dalla standby, non ancora applicato
# più veloce di 'on' (no fsync sulla standby)
# più lento di 'off' (attende ACK di rete)
# RPO: può perdere al massimo le write in transito → accettabile per molti use case
```

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
- **Application-level resolution**: il conflitto viene rilevato e passato all'applicazione (es. CouchDB, Cassandra con LWT)
- **CRDT (Conflict-free Replicated Data Types)**: strutture dati matematicamente prive di conflitti (contatori, set) — usati in Redis Cluster, Riak
- **Serializable consistency**: coordinamento distribuito (2PC, Paxos) — elimina conflitti ma sacrifica disponibilità

**Quando usare multi-master:**
- Active-active geografico obbligatorio (disaster recovery senza downtime)
- Write throughput > capacità di un singolo nodo (raro con hardware moderno)
- Galera Cluster (MySQL), Patroni con multi-master sperimentale, CockroachDB, YugabyteDB

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
```

```yaml
# Alert Prometheus — lag > 30s
- alert: ReplicationLagHigh
  expr: pg_replication_lag > 30
  for: 2m
  annotations:
    summary: "PostgreSQL replica lag {{ $value }}s — rischio RPO violato"
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
