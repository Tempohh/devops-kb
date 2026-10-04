---
title: "PostgreSQL Replicazione"
slug: replicazione
category: databases
tags: [postgresql, replicazione, streaming, logical, wal, alta-disponibilità, failover]
search_keywords: [postgresql replication, streaming replication, logical replication, wal archiving, wal sender, wal receiver, replication slot, synchronous commit, synchronous standby, hot standby, pg_basebackup, recovery.conf, primary_conninfo, recovery_target, patroni, repmgr, pg_replication_lag, logical decoding, pgoutput, wal2json, publication, subscription, slot lag]
parent: databases/postgresql/_index
related: [databases/replicazione-ha/strategie-replica, databases/replicazione-ha/failover-recovery, databases/postgresql/mvcc-vacuum]
official_docs: https://www.postgresql.org/docs/current/high-availability.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# PostgreSQL Replicazione

## Streaming Replication — Replica Fisica

La streaming replication è il meccanismo standard per HA in PostgreSQL. Il primary invia il WAL (Write-Ahead Log) in streaming alle standby, che lo applicano in tempo reale. Le standby sono repliche fisiche esatte del primary — stessa struttura fisica, stesso contenuto.

### Architettura

```
Primary                        Standby 1 (sync)      Standby 2 (async)
  │                                  │                      │
  │ WAL Sender ──── streaming ──────> WAL Receiver           │
  │                                  │                      │
  │ WAL Sender ──────────────────────────── streaming ──────>│
  │                                  │ applica WAL           │
  │ (attende ack da Standby 1        │ invia ack al primary  │
  │  prima di confermare COMMIT)     │                      │ applica WAL
```

### Configurazione Primary

```ini
# postgresql.conf
wal_level = replica          # Minimo per streaming replication
max_wal_senders = 10         # Connessioni WAL sender simultanee
wal_keep_size = 1GB          # Mantieni 1GB di WAL per le standby lente
synchronous_standby_names = 'standby1'  # Sincrona con standby1

# Commit sincrono vs asincrono
synchronous_commit = on      # Attende ack dalla standby prima di rispondere al client
# synchronous_commit = off   # Non attende — possibile perdita di transazioni confermate (finestra max 3×wal_writer_delay), ma nessuna corruzione
# synchronous_commit = remote_write  # Standby ha ricevuto il WAL ma non ha fatto fsync
# synchronous_commit = remote_apply  # Standby ha applicato il WAL (più sicuro, più lento)
```

!!! note "Nome della standby sincrona"
    I valori di `synchronous_standby_names` (es. `standby1`) sono confrontati con l'`application_name` che la standby dichiara nella sua `primary_conninfo`. Senza `application_name=standby1` la standby resta `async` e, se nessuna standby corrisponde, i COMMIT **si bloccano** in attesa di un ack che non arriva. Per tollerare la perdita di una standby usare un quorum: `ANY 1 (standby1, standby2)`.

```sql
-- pg_hba.conf: permetti connessioni di replicazione
host  replication  replicator  standby-ip/32  scram-sha-256

-- Crea utente replicazione
CREATE USER replicator REPLICATION LOGIN PASSWORD 'strongpassword';
```

### Inizializzazione Standby con pg_basebackup

```bash
# Sul nodo standby:
pg_basebackup \
  --host=primary-host \
  --username=replicator \
  --pgdata=/var/lib/postgresql/data \
  --wal-method=stream \
  --checkpoint=fast \
  --progress \
  --verbose

# Crea il file standby.signal (PostgreSQL 12+)
touch /var/lib/postgresql/data/standby.signal

# postgresql.conf sul standby
primary_conninfo = 'host=primary-host user=replicator application_name=standby1'  # password via ~/.pgpass o PGPASSFILE, non in chiaro
primary_slot_name = 'standby1_slot'  # usa lo slot creato sul primary (vedi sotto)
hot_standby = on                  # Permette letture in read-only sulla standby
hot_standby_feedback = on         # Informa il primary delle query attive sul standby
```

### Monitoraggio Replication Lag

```sql
-- Sul primary: stato di tutte le standby
SELECT
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replication_lag_bytes,
    write_lag,
    flush_lag,
    replay_lag,
    sync_state
FROM pg_stat_replication;

-- Sulla standby: quanti secondi di lag
SELECT
    now() - pg_last_xact_replay_timestamp() AS replication_lag,
    pg_is_in_recovery() AS is_standby,
    pg_last_wal_receive_lsn() AS received_lsn,
    pg_last_wal_replay_lsn() AS replayed_lsn;
```

### Replication Slots

Un replication slot garantisce che il primary conservi il WAL finché la standby non lo ha consumato. Protegge la standby da un primary che avanza troppo — ma può causare accumulo WAL illimitato se la standby è ferma.

```sql
-- Crea uno slot di replicazione
SELECT pg_create_physical_replication_slot('standby1_slot');

-- Monitora il lag degli slot (CRITICO: se slot_lag cresce indefinitamente → disastre I/O)
SELECT
    slot_name,
    slot_type,
    active,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS slot_lag
FROM pg_replication_slots;
-- restart_lsn = il WAL più vecchio che lo slot trattiene (vale per slot fisici e logici;
-- confirmed_flush_lsn è NULL sugli slot fisici)

-- ⚠ Elimina uno slot inattivo se il consumer è perso (evita riempimento disco)
SELECT pg_drop_replication_slot('standby1_slot');
```

---

## Logical Replication — Replica Selettiva

La logical replication replica a livello di cambiamenti logici (INSERT/UPDATE/DELETE su righe specifiche) invece che a livello di WAL fisico. Permette:
- Replicare solo alcune tabelle (non l'intero database)
- Replicare verso una versione diversa di PostgreSQL (anche major version)
- Zero-downtime major version upgrades
- CDC (Change Data Capture) verso sistemi esterni

### Architettura

```
Primary (Publisher)          Standby (Subscriber)
  Publication                  Subscription
  ├── tabella ordini    →→→→   tabella ordini (replica)
  ├── tabella prodotti  →→→→   tabella prodotti (replica)
  └── tabella utenti    →→→→   (non replicata — non nella publication)
```

### Configurazione

```ini
# Primary postgresql.conf
wal_level = logical  # Necessario per logical replication
```

```sql
-- Sul PRIMARY: crea una publication
CREATE PUBLICATION mia_publication
    FOR TABLE ordini, prodotti, categorie;
    -- oppure: FOR ALL TABLES
    -- oppure: FOR TABLE ordini WHERE (created_at > '2024-01-01')  -- row filter (PG 15+)

-- Controlla cosa è pubblicato
SELECT * FROM pg_publication_tables WHERE pubname = 'mia_publication';
```

```sql
-- Sul SUBSCRIBER:
-- 1. La tabella deve esistere già (con schema compatibile)
CREATE TABLE ordini (LIKE ordini_primary INCLUDING ALL);

-- 2. Crea la subscription
CREATE SUBSCRIPTION mia_subscription
    CONNECTION 'host=primary-host dbname=mydb user=replicator password=strongpass'
    PUBLICATION mia_publication;

-- Monitora il lag della subscription
SELECT subname, received_lsn, latest_end_lsn,
       pg_wal_lsn_diff(latest_end_lsn, received_lsn) AS lag_bytes
FROM pg_stat_subscription;
```

### Limitazioni della Logical Replication

- Non replica DDL (ALTER TABLE, CREATE INDEX, ecc.) — deve essere applicato manualmente
- Non replica sequenze (i valori SERIAL/BIGSERIAL non vengono sincronizzati): prima dello switchover vanno allineate a mano (`setval`)
- TRUNCATE è replicato dalla PG 11 (opzione `publish` della publication, default `insert, update, delete, truncate`)
- UPDATE/DELETE richiedono una `REPLICA IDENTITY` (di default la primary key): tabelle senza PK vanno configurate
- Non replica Large Objects
- Il subscriber è un database scrivibile: scritture locali sulle tabelle replicate generano conflitti

!!! tip "Novità PG 15-17"
    PG 15: row filter e column list nelle publication, `ALTER SUBSCRIPTION ... SKIP (lsn = ...)`. PG 16: logical decoding dalla standby. PG 17: **failover degli slot logici** (`failover = true` sulla subscription + `sync_replication_slots` sulla standby) e `pg_createsubscriber` per convertire una standby fisica in subscriber logico. <!-- REVIEW: verificare novità PG 18 su logical replication (es. conflict logging) -->

---

## Zero-Downtime Major Version Upgrade

La logical replication permette di fare upgrade tra major version (es. da PostgreSQL 15 a 17) con downtime minimo (secondi). Alternativa più semplice se è accettabile una finestra più lunga: `pg_upgrade --link` (vedi [Major Version Upgrade](major-version-upgrade.md)).

```
Phase 1: Setup replica sulla nuova versione
  PG15 (primary) --logical replication--> PG17 (subscriber)
  (schema copiato prima con pg_dump --schema-only)

Phase 2: Catchup
  Attendi che PG17 sia allineato con PG15 (lag ≈ 0)

Phase 3: Switchover (maintenance window minima ~30s)
  1. Blocca scritture su PG15 (default_transaction_read_only = on + termina le sessioni attive)
  2. Verifica che PG17 sia completamente allineato
  3. Allinea le sequenze su PG17 (setval dai valori di PG15)
  4. DROP SUBSCRIPTION su PG17: diventa il nuovo primary
  5. Aggiorna la stringa di connessione dell'applicazione
```

---

## WAL Archiving e Point-in-Time Recovery

WAL archiving conserva i file WAL su storage esterno (S3, NFS) per permettere PITR:

```ini
# postgresql.conf
archive_mode = on
archive_command = 'aws s3 cp %p s3://my-wal-archive/%f'
# %p = path del file WAL, %f = nome file
```

`archive_command` deve restituire exit 0 solo a copia riuscita e non sovrascrivere file esistenti; in produzione si preferiscono tool dedicati (pgBackRest, WAL-G: `archive_command = 'pgbackrest ... archive-push %p'`) che comprimono, verificano e gestiscono retention. Il PITR è trattato in dettaglio nella sezione [Backup e PITR](../replicazione-ha/backup-pitr.md).

---

## Patroni — HA con Failover Automatico

[Patroni](https://github.com/zalando/patroni) è il tool standard per gestire un cluster PostgreSQL con failover automatico. Usa etcd, Consul o ZooKeeper come distributed lock per eleggere il primary:

```yaml
# patroni.yml
scope: postgres-cluster
namespace: /db/
name: pg-node-1

restapi:
  listen: 0.0.0.0:8008
  connect_address: node1-ip:8008

etcd:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 30
    maximum_lag_on_failover: 1048576  # 1MB max lag per failover
    synchronous_mode: true            # Patroni gestisce da solo synchronous_standby_names

postgresql:
  listen: 0.0.0.0:5432
  connect_address: node1-ip:5432
  data_dir: /var/lib/postgresql/data
  parameters:
    synchronous_commit: "on"
    # NON impostare synchronous_standby_names qui: con synchronous_mode lo scrive Patroni
```

```bash
# Stato del cluster
patronictl -c /etc/patroni.yml list

# Failover manuale
patronictl -c /etc/patroni.yml failover postgres-cluster --leader pg-node-1 --candidate pg-node-2

# Reinizializza una standby (es. dopo failover e promozione)
patronictl -c /etc/patroni.yml reinit postgres-cluster pg-node-1
```

## Troubleshooting

### Scenario 1 — Standby accumula lag e non recupera

**Sintomo:** `replication_lag_bytes` in `pg_stat_replication` cresce costantemente; la standby è indietro di minuti o ore.

**Causa:** La standby non riesce a applicare il WAL alla velocità con cui il primary lo genera. Possibili cause: I/O lento sulla standby, query long-running con `hot_standby_feedback = on` che blocca il vacuum sul primary, rete congestionata.

**Soluzione:**
1. Verificare I/O della standby e confrontare con il primary.
2. Se `hot_standby_feedback = on`, valutare se disabilitarlo o accettare il conflitto.
3. Aumentare `max_standby_streaming_delay` per ridurre i conflitti di recovery.

```sql
-- Sul primary: verifica lag per ogni standby
SELECT client_addr, write_lag, flush_lag, replay_lag, sync_state
FROM pg_stat_replication;

-- Sulla standby: lag in secondi
SELECT now() - pg_last_xact_replay_timestamp() AS lag_seconds;
```

---

### Scenario 2 — Replication slot inattivo riempie il disco

**Sintomo:** Disco del primary si riempie con WAL; `pg_replication_slots` mostra slot inattivi con `slot_lag` enorme.

**Causa:** Un replication slot (fisico o logico) è rimasto definito dopo la disconnessione permanente del consumer (`active = false`). Il primary non può rimuovere il WAL finché lo slot non avanza.

**Soluzione:** Se il consumer è permanentemente perso, eliminare lo slot. Prima verificare che nessun processo attivo lo stia usando.

```sql
-- Identifica slot inattivi con lag elevato
SELECT slot_name, active, slot_type, wal_status,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS lag
FROM pg_replication_slots
ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;

-- Elimina lo slot inattivo (irreversibile)
SELECT pg_drop_replication_slot('nome_slot_inattivo');

-- Imposta un limite massimo per prevenire il problema
-- postgresql.conf (PG 13+): oltre il limite lo slot diventa 'lost' (wal_status) e il consumer
-- va reinizializzato, ma il primary non finisce il disco:
-- max_slot_wal_keep_size = 10GB
```

---

### Scenario 3 — Errore di connessione WAL sender / receiver

**Sintomo:** Log della standby riporta `could not connect to the primary server` o `FATAL: replication terminated by primary server`. La standby scompare da `pg_stat_replication` (o resta in `startup`/`catchup`).

**Causa:** Password errata, `pg_hba.conf` non include la standby, firewall, max_wal_senders raggiunto, o il WAL richiesto è già stato eliminato (slot non configurato e `wal_keep_size` troppo basso).

**Soluzione:**

```bash
# Verifica connettività dalla standby verso il primary
psql "host=primary-host user=replicator replication=true" -c "IDENTIFY_SYSTEM;"

# Controlla i log della standby
tail -f /var/log/postgresql/postgresql.log | grep -E "FATAL|ERROR|replication"

```

```sql
-- Sul primary: max_wal_senders esaurito? (richiede restart per aumentarlo)
SELECT count(*) FROM pg_stat_replication;
-- Se uguale a max_wal_senders → aumentare il parametro e riavviare
```

Se il WAL necessario non è più disponibile → reinizializzare la standby con `pg_basebackup`.

---

### Scenario 4 — Subscription logica bloccata / lag in crescita

**Sintomo:** `pg_stat_subscription` mostra `received_lsn` fermo; il subscriber non applica nuovi cambiamenti. La tabella sul subscriber è ferma mentre il primary avanza.

**Causa:** Errore di applicazione su una riga (es. violazione di constraint, chiave duplicata), worker della subscription crashato, o connessione interrotta senza riconnessione automatica.

**Soluzione:**

```sql
-- Sul subscriber: stato di tutte le subscription
SELECT subname, pid, received_lsn, latest_end_lsn, last_msg_receipt_time
FROM pg_stat_subscription;

-- Controlla errori nei log o in pg_subscription_rel
SELECT srrelid::regclass, srsubstate, srsublsn
FROM pg_subscription_rel;
-- srsubstate: 'i'=initialize, 'd'=data copy, 'f'=finished copy, 's'=synchronized, 'r'=ready
-- (non esiste uno stato di errore: cercarlo nel log o in pg_stat_subscription_stats.apply_error_count)

-- Disabilita e riabilita la subscription per forzare riconnessione
ALTER SUBSCRIPTION mia_subscription DISABLE;
ALTER SUBSCRIPTION mia_subscription ENABLE;

-- Se la causa è un conflitto di dati: risolverlo manualmente sulla tabella subscriber
-- oppure saltare la transazione problematica (PG 15+; LSN dal log: "finished at 0/XXXX")
ALTER SUBSCRIPTION mia_subscription SKIP (lsn = '0/14C0378');
-- Prima di PG 15: SELECT pg_replication_origin_advance('pg_<oid_subscription>', 'LSN');
```

---



??? info "Strategie di Replica — Concetti generali"
    Sync vs async, trade-off RPO/RTO.

    **Approfondimento →** [Strategie di Replica](../replicazione-ha/strategie-replica.md)

??? info "Backup e PITR — Point-in-Time Recovery"
    Come usare il WAL archiving per il recovery.

    **Approfondimento →** [Backup e PITR](../replicazione-ha/backup-pitr.md)

## Riferimenti

- [PostgreSQL High Availability](https://www.postgresql.org/docs/current/high-availability.html)
- [Patroni Documentation](https://patroni.readthedocs.io/)
- [Zalando — Patroni](https://github.com/zalando/patroni)
