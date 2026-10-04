---
title: "MySQL — Architettura e Replicazione"
slug: architettura-replicazione
category: databases
tags: [mysql, mariadb, innodb, replication, binlog, gtid, group-replication, galera, high-availability]
search_keywords: [mysql architecture, innodb storage engine, buffer pool, redo log, undo log, clustered index, binary log, binlog, statement based replication, row based replication, mixed replication, gtid replication, global transaction identifier, semi-sync replication, mysql group replication, galera cluster, percona xtradb cluster, mariadb, mysqldump, percona xtrabackup, show replica status, show engine innodb status, master slave replication, primary replica]
parent: databases/mysql/_index
related: [databases/postgresql/mvcc-vacuum, databases/postgresql/replicazione, databases/replicazione-ha/strategie-replica, databases/replicazione-ha/backup-pitr]
official_docs: https://dev.mysql.com/doc/refman/8.4/en/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# MySQL — Architettura e Replicazione

## Panoramica

MySQL (e il suo fork community-driven MariaDB) è, insieme a PostgreSQL, l'RDBMS open source più diffuso in produzione — soprattutto nello stack LAMP/LEMP, in applicazioni web tradizionali e in molti servizi managed cloud (Amazon RDS/Aurora MySQL, Cloud SQL, Azure Database for MySQL). A differenza di PostgreSQL, MySQL è storicamente un **motore multi-storage-engine**: la sintassi SQL è unica ma il motore di storage sottostante (InnoDB oggi, MyISAM storicamente) determina concorrenza, transazionalità e durabilità. Questa pagina copre l'architettura interna di InnoDB (il motore di default e praticamente unico usato in produzione), i meccanismi di replicazione (binlog, GTID), le soluzioni di alta disponibilità (Group Replication, Galera Cluster) e le strategie di backup. Versioni: MySQL 8.0 è arrivato a end-of-life ad aprile 2026; la linea supportata per produzione è **8.4 LTS** (le 9.x sono release *innovation*, a vita breve). La pagina usa la sintassi 8.0.23+/8.4 e segnala dove differisce. Non copre tuning SQL generico o data modeling — per quello vedere le sezioni [SQL Avanzato](../sql-avanzato/_index.md) e [Fondamentali](../fondamentali/_index.md), che sono agnostiche al motore.

## Concetti Chiave

!!! note "InnoDB è MySQL, in produzione"
    Da MySQL 5.5 InnoDB è il motore di storage di default. MyISAM (non transazionale, senza row-level locking, senza crash recovery affidabile) è ormai da evitare salvo casi legacy molto specifici. Tutto ciò che segue assume InnoDB.

- **Clustered index su Primary Key**: a differenza di PostgreSQL (dove la tabella è un heap indipendente dagli indici), in InnoDB la tabella *è* un B+Tree ordinato per Primary Key. Le righe sono fisicamente memorizzate in ordine di PK. Ogni indice secondario contiene il valore della PK come puntatore alla riga (non un offset fisico) — una query che usa un indice secondario richiede sempre un secondo lookup sul clustered index.
- **Buffer Pool**: cache in-memory di pagine di dati e indici. Equivalente concettuale allo shared_buffers di PostgreSQL, ma tipicamente dimensionato molto più aggressivamente (70-80% della RAM disponibile è comune per un'istanza dedicata).
- **Redo log**: log circolare a dimensione fissa che garantisce durabilità (il "D" di ACID) — ogni modifica viene scritta prima nel redo log (sequenziale, veloce) e solo dopo applicata alle pagine di dati (che possono restare in buffer pool per tempo indefinito, "dirty pages"). Concettualmente analogo al WAL di PostgreSQL.
- **Undo log**: mantiene le versioni precedenti delle righe per supportare MVCC (letture consistenti senza lock) e rollback delle transazioni. È il motivo per cui InnoDB — come PostgreSQL — offre reader che non bloccano writer.
- **Binary log (binlog)**: log separato dal redo log, usato per replicazione e point-in-time recovery. Non è coinvolto nel crash recovery del singolo nodo — la sua unica funzione è propagare i cambiamenti verso replica o backup.

## Architettura / Come Funziona

### InnoDB — Storage Engine

```
Client Query
     │
     ▼
┌─────────────────────────────────────────┐
│           MySQL Server Layer             │
│  Parser → Optimizer → Query Cache (8.0:   │
│  rimossa) → Execution Engine              │
└──────────────────┬────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│            InnoDB Storage Engine          │
│                                            │
│  ┌──────────────┐   ┌──────────────────┐ │
│  │ Buffer Pool  │   │  Change Buffer    │ │
│  │ (dati+indici │   │  (modifiche a     │ │
│  │  in RAM)     │   │  indici secondari │ │
│  └──────┬───────┘   │  non-unique)      │ │
│         │           └──────────────────┘ │
│         ▼                                 │
│  ┌──────────────┐   ┌──────────────────┐ │
│  │  Redo Log     │   │   Undo Log        │ │
│  │ (durabilità,  │   │   (MVCC,          │ │
│  │  circolare)   │   │   rollback)       │ │
│  └──────────────┘   └──────────────────┘ │
└─────────────────────────────────────────┘
                    │
                    ▼
        Tablespace files (.ibd) su disco
```

Quando una transazione fa `COMMIT`:
1. Le modifiche vengono scritte nel **redo log** (fsync, sequenziale — questo è il costo reale del commit)
2. Le pagine modificate restano "dirty" nel buffer pool
3. Un thread di background (checkpoint) scrive le dirty page su disco in modo asincrono, quando conviene per I/O — non ad ogni commit

```sql
-- Verificare lo stato interno di InnoDB: buffer pool hit ratio, transazioni attive, lock
SHOW ENGINE INNODB STATUS\G

-- Metriche chiave da estrarre dall'output:
--   Buffer pool hit rate (deve essere >99% in produzione)
--   TRANSACTIONS: transazioni long-running che bloccano il purge dell'undo log
--   ROW OPERATIONS: query in esecuzione/in coda dentro InnoDB
```

```ini
# my.cnf — parametri InnoDB fondamentali
[mysqld]
innodb_buffer_pool_size = 12G          # 70-80% della RAM su istanza dedicata
innodb_buffer_pool_instances = 8       # Riduce contention su buffer pool grandi (>1GB)
innodb_redo_log_capacity = 2G          # 8.0.30+: capacità totale del redo, ridimensionabile a caldo. Più grande = meno checkpoint, crash recovery più lento
# (prima di 8.0.30: innodb_log_file_size × innodb_log_files_in_group, richiede restart; oggi deprecato)
innodb_flush_log_at_trx_commit = 1     # 1=fsync ad ogni commit (sicuro, default), 0/2=più veloce, rischio perdita dati
innodb_flush_method = O_DIRECT         # Evita double buffering (OS cache + InnoDB buffer pool)
innodb_file_per_table = ON             # Ogni tabella in un file .ibd separato (default da 5.6+)
```

### Replicazione — Binary Log Based

MySQL replica propagando eventi dal **binary log** del source (primary) verso i replica. Tre formati:

```
STATEMENT-BASED (SBR): replica la query SQL testuale
  PRO: binlog compatto
  CONTRO: non-deterministico con funzioni come NOW(), UUID(), RAND() → drift tra nodi

ROW-BASED (RBR): replica le righe effettivamente modificate (before/after image)
  PRO: sempre deterministico, safe by default
  CONTRO: binlog più grande su UPDATE/DELETE massivi

MIXED: MySQL sceglie automaticamente SBR o RBR in base alla query
  Compromesso, ma la scelta automatica resta meno prevedibile di ROW

Default dal 5.7.7: ROW. Consigliato in produzione per evitare inconsistenze silenziose
```

```ini
# my.cnf — configurazione binlog sul source
[mysqld]
server_id = 1                      # Univoco per ogni nodo del cluster (obbligatorio)
log_bin = /var/log/mysql/mysql-bin
binlog_format = ROW                # Deterministico — evitare STATEMENT in produzione
binlog_row_image = FULL            # FULL=riga completa, MINIMAL=solo colonne cambiate (risparmio spazio)
binlog_expire_logs_seconds = 604800   # Retention 7 giorni (default 8.0: 30 giorni). expire_logs_days è deprecato e rimosso in 8.4
sync_binlog = 1                    # fsync ad ogni transazione — sicuro, costo I/O
```

### GTID — Global Transaction Identifier

Prima di GTID (MySQL 5.6+), un replica veniva ripuntato a un source diverso specificando manualmente `(binlog_file, position)` — fragile e propenso a errori durante failover. GTID assegna a ogni transazione un identificatore univoco globale (`source_uuid:transaction_id`), permettendo al replica di sincronizzarsi automaticamente senza conoscere posizione/file.

```ini
# my.cnf — abilitare GTID (su TUTTI i nodi del topology)
[mysqld]
gtid_mode = ON
enforce_gtid_consistency = ON      # Rifiuta statement non GTID-safe (es. CREATE TABLE ... SELECT)
log_replica_updates = ON           # Il replica scrive nel proprio binlog gli eventi applicati (necessario per sub-replica; default ON in 8.0). Nome legacy: log_slave_updates
```

```sql
-- Sul REPLICA: configurare la replicazione con GTID (MySQL 8.0+)
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST = 'source-host',
    SOURCE_USER = 'repl_user',
    SOURCE_PASSWORD = 'strongpassword',
    SOURCE_AUTO_POSITION = 1,      -- GTID auto-position, non serve file/pos manuale
    SOURCE_SSL = 1;                -- con caching_sha2_password (default 8.0) serve TLS, oppure GET_SOURCE_PUBLIC_KEY = 1

START REPLICA;

-- Stato della replica — comando principale per il troubleshooting
SHOW REPLICA STATUS\G
-- Campi critici:
--   Replica_IO_Running / Replica_SQL_Running: devono essere entrambi "Yes"
--   Seconds_Behind_Source: lag in secondi
--   Last_Error / Last_IO_Error / Last_SQL_Error: causa di un'eventuale interruzione
```

!!! warning "Naming legacy: SLAVE vs REPLICA"
    MySQL 8.0.23+ ha rinominato la sintassi (`CHANGE MASTER TO` → `CHANGE REPLICATION SOURCE TO`, `SHOW SLAVE STATUS` → `SHOW REPLICA STATUS`). MariaDB e versioni MySQL precedenti usano ancora la sintassi legacy con `MASTER`/`SLAVE`. Verificare la versione esatta prima di applicare comandi da documentazione trovata online.

### Semi-Sync vs Async Replication

```
ASYNC (default):
  Source COMMIT → risponde al client IMMEDIATAMENTE
                → invia evento al binlog dump thread in background
  RPO: può perdere transazioni committate se il source crasha prima
       che il replica le riceva

SEMI-SYNC:
  Source COMMIT → attende ACK da almeno 1 replica che ha RICEVUTO
                   (non necessariamente applicato) il transaction event
                → poi risponde al client
  RPO: zero transazioni perse per crash del source, a costo di latenza
       aggiuntiva pari alla round-trip verso il replica più lento
```

```sql
-- Abilitare semi-sync (plugin da installare su source e replica)
INSTALL PLUGIN rpl_semi_sync_source SONAME 'semisync_source.so';  -- sul source
INSTALL PLUGIN rpl_semi_sync_replica SONAME 'semisync_replica.so'; -- sul replica

SET GLOBAL rpl_semi_sync_source_enabled = 1;    -- sul source
SET GLOBAL rpl_semi_sync_replica_enabled = 1;   -- sul replica (poi riavviare l'IO thread: STOP/START REPLICA IO_THREAD)
SET GLOBAL rpl_semi_sync_source_timeout = 10000; -- ms prima di degradare ad async
```

### Alta Disponibilità — Group Replication vs Galera Cluster

Due approcci multi-master/consensus-based, alternativi alla replica classica source→replica per failover automatico:

```
MySQL Group Replication (nativo MySQL 8.0+)
  - Basato su Paxos-derived consensus protocol
  - Modalità single-primary (consigliata) o multi-primary
  - Failover automatico: il gruppo elegge un nuovo primary se quello
    corrente diventa irraggiungibile
  - Richiede almeno 3 nodi per tollerare la perdita di 1 membro (maggioranza)
  - In produzione si usa tipicamente via InnoDB Cluster (Group Replication +
    MySQL Shell AdminAPI + MySQL Router per il routing) invece di orchestrarla a mano

Galera Cluster (MariaDB Galera / Percona XtraDB Cluster)
  - Certification-based replication: ogni nodo certifica le transazioni
    prima del commit (write-set replication)
  - Multi-master vero: si può scrivere su QUALSIASI nodo
  - Trade-off: conflitti di certificazione su hot-row contention
    (due nodi scrivono la stessa riga contemporaneamente → uno abortisce)
  - Richiede rete a bassa latenza tra i nodi (sincrono a livello di certificazione)
```

!!! tip "Single-primary è quasi sempre la scelta giusta"
    Sia Group Replication che Galera supportano multi-primary, ma scrivere su più nodi contemporaneamente introduce conflitti di certificazione/consensus che sono difficili da diagnosticare in produzione. Salvo esigenze specifiche di scrittura geo-distribuita, configurare single-primary con failover automatico è più semplice da operare e debuggare.

```sql
-- Group Replication: bootstrap del primo nodo del gruppo
SET GLOBAL group_replication_bootstrap_group = ON;
START GROUP_REPLICATION;
SET GLOBAL group_replication_bootstrap_group = OFF;

-- Stato del gruppo (su qualsiasi nodo)
SELECT * FROM performance_schema.replication_group_members;
-- MEMBER_STATE deve essere ONLINE per tutti i nodi sani
```

```ini
# my.cnf — Galera Cluster (nodo aggiuntivo che si unisce a un cluster esistente)
[mysqld]
wsrep_on = ON
wsrep_provider = /usr/lib/galera/libgalera_smm.so
wsrep_cluster_address = gcomm://node1-ip,node2-ip,node3-ip
wsrep_node_address = this-node-ip
wsrep_sst_method = xtrabackup-v2   # State Snapshot Transfer method per il join
```

## Configurazione & Pratica

### Backup — Logico vs Fisico

```bash
# mysqldump — backup LOGICO (SQL testuale, portabile tra versioni/engine)
# PRO: leggibile, restore selettivo, funziona ovunque
# CONTRO: lento su dataset grandi, richiede lock (o --single-transaction su InnoDB)
# --source-data=2 (8.0.26+; legacy --master-data, rimosso in 8.4) scrive come commento la posizione binlog;
# --set-gtid-purged=ON include il GTID_PURGED per inizializzare un replica. (--gtid è di MariaDB, non MySQL)
mysqldump --single-transaction --routines --triggers \
  --source-data=2 --set-gtid-purged=ON \
  -u backup_user -p mydb > mydb_backup.sql

# Restore
mysql -u root -p mydb < mydb_backup.sql
```

```bash
# Percona XtraBackup — backup FISICO hot (non bloccante) per InnoDB
# PRO: veloce su dataset grandi (TB), backup incrementali, hot backup senza lock lunghi
# CONTRO: legato alla versione/architettura di InnoDB, meno portabile
xtrabackup --backup --target-dir=/backup/full \
  --user=backup_user --password=strongpassword

# Prepare (applica i log delle transazioni raccolte durante il backup)
xtrabackup --prepare --target-dir=/backup/full

# Restore (con il servizio MySQL fermo e datadir vuota; poi chown -R mysql:mysql sul datadir)
xtrabackup --copy-back --target-dir=/backup/full --datadir=/var/lib/mysql
```

!!! tip "Scegliere tra mysqldump e XtraBackup"
    `mysqldump` per dataset piccoli (<10GB), migrazioni cross-version, o backup selettivi di poche tabelle. `xtrabackup` per dataset grandi in produzione dove il tempo di backup/restore e l'impatto sul sistema live contano — è l'equivalente concettuale di `pg_basebackup`/`pgBackRest` lato PostgreSQL, vedi [Backup e PITR](../replicazione-ha/backup-pitr.md).

### Monitoraggio Replica in Produzione

```sql
-- Lag di replicazione (metrica più importante per alerting)
SHOW REPLICA STATUS\G
-- Seconds_Behind_Source: NULL significa replica FERMA (non "zero lag") — attenzione

-- Verifica coerenza dati tra source e replica (checksum tabella per tabella)
-- Richiede Percona Toolkit
pt-table-checksum --host=source-host -u checksum_user -p

-- Elenco dei processi attivi e lock in corso
SHOW FULL PROCESSLIST;

-- Statistiche InnoDB su lock wait
SELECT * FROM sys.innodb_lock_waits;
```

## Best Practices

- **GTID sempre attivo**: semplifica failover, `CHANGE REPLICATION SOURCE` e riduce il rischio di errore umano nella gestione di file/posizione binlog.
- **`binlog_format = ROW`**: evitare STATEMENT in produzione — il rischio di drift silenzioso tra source e replica (dati diversi senza errori visibili) supera il risparmio di spazio.
- **Semi-sync su almeno 1 replica** per workload dove RPO=0 è un requisito (transazioni finanziarie, ordini). Async va bene per read replica pure di scaling.
- **Monitorare `Seconds_Behind_Source` con alerting**, non solo controllo manuale — un replica che accumula lag silenziosamente è la causa più comune di dati stale servito da un load balancer read-only.
- **Testare il restore, non solo il backup**: uno `xtrabackup --backup` che completa senza errori non garantisce un restore funzionante — validare periodicamente su un ambiente separato.
- **Replica parallela**: se il lag cresce con un source molto scritto, abilitare l'applier multi-thread (`replica_parallel_workers` > 1; default 4 da 8.0.27, `replica_parallel_type=LOGICAL_CLOCK`) invece di un solo SQL thread.
- **Non abilitare multi-primary** (Group Replication o Galera) senza una ragione concreta — vedi tip sopra.

!!! warning "Attenzione al replication lag come singolo punto di failure applicativo"
    Un pattern comune e pericoloso: applicazione scrive sul primary e legge immediatamente dopo da un read replica (per bilanciare il carico). Se il replica ha lag anche di pochi secondi, l'utente non vede il proprio dato appena scritto ("read-after-write inconsistency"). Soluzioni: leggere dal primary per un breve periodo dopo la scrittura, attendere sul replica il GTID della propria scrittura (`WAIT_FOR_EXECUTED_GTID_SET()`), o instradare esplicitamente le letture critiche. Semi-sync da solo **non** basta: l'ACK conferma la ricezione, non l'applicazione sul replica.

## Troubleshooting

### Scenario 1 — Replica bloccato con `Seconds_Behind_Source: NULL`

**Sintomo:** `SHOW REPLICA STATUS\G` mostra `Replica_SQL_Running: No` e `Seconds_Behind_Source: NULL` (non zero — fermo).

**Causa:** Il thread SQL del replica ha incontrato un errore nell'applicare un evento (es. duplicate key da uno statement non idempotente, tabella mancante, constraint violation).

**Soluzione:**
```sql
-- Identificare l'errore esatto
SHOW REPLICA STATUS\G
-- Campo Last_SQL_Error contiene il messaggio esatto

-- Senza GTID: saltare un evento (usare con cautela; con gtid_mode=ON è rifiutato)
SET GLOBAL sql_replica_skip_counter = 1;
START REPLICA;

-- Con GTID attivo: iniettare una transazione vuota con il GTID problematico
-- (STOP REPLICA prima; il GTID è in Retrieved_Gtid_Set / Last_SQL_Error)
SET GTID_NEXT = 'source_uuid:transaction_id';
BEGIN; COMMIT;
SET GTID_NEXT = 'AUTOMATIC';
START REPLICA;
```

---

### Scenario 2 — Disco del source pieno per binlog non purgati

**Sintomo:** Partizione con i binlog cresce senza limite; `df -h` mostra utilizzo vicino al 100%.

**Causa:** retention troppo lunga (default 8.0: 30 giorni) o assente (`binlog_expire_logs_seconds = 0`, o `expire_logs_days` ignorato su 8.4), oppure volume di scritture molto alto con `binlog_row_image = FULL`. Attenzione: la purge automatica e `PURGE BINARY LOGS` **non** controllano se un replica ha ancora bisogno dei file — un replica in ritardo oltre la retention perde i binlog e va ricostruito.

**Soluzione:**
```sql
-- Verificare i binlog esistenti e la loro dimensione
SHOW BINARY LOGS;

-- Purge manuale (attenzione: verificare che nessun replica ne abbia bisogno)
PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY;

-- Impostare retention automatica (persistente, MySQL 8.0+; in alternativa a my.cnf)
SET PERSIST binlog_expire_logs_seconds = 604800; -- 7 giorni
```

---

### Scenario 3 — `SHOW ENGINE INNODB STATUS` mostra transazioni long-running e purge lag

**Sintomo:** Lo spazio del tablespace (`ibdata1` o file per-tabella) cresce indefinitamente nonostante nessuna crescita reale dei dati.

**Causa:** Una transazione aperta a lungo (`idle in transaction` equivalente) impedisce al purge thread di InnoDB di liberare le versioni obsolete nell'undo log — concettualmente analogo al blocco di VACUUM da parte di una transazione idle in PostgreSQL.

**Soluzione:**
```sql
-- Identificare transazioni long-running
SELECT trx_id, trx_started, trx_mysql_thread_id, trx_query
FROM information_schema.innodb_trx
ORDER BY trx_started ASC;

-- Terminare la connessione bloccante
KILL <trx_mysql_thread_id>;

-- Verificare lo stato del purge lag nell'output completo
SHOW ENGINE INNODB STATUS\G
-- Sezione TRANSACTIONS: "History list length" alto indica undo log non purgato
```

---

### Scenario 4 — Galera Cluster: nodo in stato `Non-Primary` dopo split di rete

**Sintomo:** Un nodo Galera passa a `wsrep_cluster_status = Non-Primary` e rifiuta scritture (`ERROR: Unknown command` o connessioni rifiutate).

**Causa:** Il nodo ha perso il quorum (partizione di rete, o meno della maggioranza dei nodi raggiungibili). Galera è progettato per rifiutare scritture su un partition minoritario per evitare split-brain.

**Soluzione:**
```bash
# Verificare lo stato del cluster sul nodo isolato
mysql -e "SHOW STATUS LIKE 'wsrep_cluster_status';"
mysql -e "SHOW STATUS LIKE 'wsrep_cluster_size';"

# Se la rete è stata ripristinata, il nodo dovrebbe riunirsi automaticamente
# Se il cluster INTERO ha perso quorum (es. tutti i nodi riavviati), serve
# bootstrap manuale da UN SOLO nodo: quello con seqno più alto
# (/var/lib/mysql/grastate.dat: safe_to_bootstrap: 1, oppure mysqld --wsrep-recover)
galera_new_cluster   # MariaDB Galera (systemd). Percona XtraDB Cluster: systemctl start mysql@bootstrap
```

## Relazioni

??? info "PostgreSQL MVCC e Vacuum — confronto architetturale"
    PostgreSQL usa un heap separato dagli indici e il vacuum per il cleanup delle dead tuple; InnoDB usa un clustered index su PK e un purge thread per l'undo log. Stesso problema concettuale (versioni obsolete da rimuovere), meccanismo diverso.

    **Approfondimento →** [MVCC e Vacuum](../postgresql/mvcc-vacuum.md)

??? info "PostgreSQL Replicazione — streaming vs binlog"
    PostgreSQL replica il WAL fisico o cambiamenti logici; MySQL replica eventi dal binary log. Concetti paralleli: replication slot ↔ GTID, synchronous_commit ↔ semi-sync.

    **Approfondimento →** [Replicazione PostgreSQL](../postgresql/replicazione.md)

??? info "Strategie di Replica — concetti generali sync/async"
    Trade-off RPO/RTO applicabili a qualsiasi RDBMS, non solo MySQL.

    **Approfondimento →** [Strategie di Replica](../replicazione-ha/strategie-replica.md)

??? info "Backup e PITR — approccio generale"
    Concetti di backup fisico vs logico e point-in-time recovery, lato PostgreSQL ma con parallelo diretto a mysqldump/XtraBackup.

    **Approfondimento →** [Backup e PITR](../replicazione-ha/backup-pitr.md)

## Riferimenti

- [MySQL 8.4 Reference Manual — Replication](https://dev.mysql.com/doc/refman/8.4/en/replication.html)
- [MySQL 8.4 Reference Manual — InnoDB Storage Engine](https://dev.mysql.com/doc/refman/8.4/en/innodb-storage-engine.html)
- [MySQL Group Replication Documentation](https://dev.mysql.com/doc/refman/8.4/en/group-replication.html)
- [Galera Cluster Documentation](https://galeracluster.com/library/documentation/)
- [Percona XtraBackup Documentation](https://docs.percona.com/percona-xtrabackup/latest/)
- [MariaDB Knowledge Base — Replication](https://mariadb.com/kb/en/replication/)
