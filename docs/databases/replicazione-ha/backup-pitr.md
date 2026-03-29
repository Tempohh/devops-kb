---
title: "Backup e Point-in-Time Recovery"
slug: backup-pitr
category: databases
tags: [backup, pitr, wal-archiving, pg-basebackup, pgbackrest, barman, recovery]
search_keywords: [postgresql backup, point in time recovery, wal archiving, pg_basebackup, pgbackrest, barman, continuous archiving, base backup, wal archive, recovery target time, recovery target lsn, recovery target xid, restore point, pg_dumpall, pg_dump, logical backup, physical backup, incremental backup, differential backup, s3 backup postgresql, rds backup, aurora backup, rpo backup, retention policy backup, pitr postgresql, restore postgresql from backup]
parent: databases/replicazione-ha/_index
related: [databases/replicazione-ha/strategie-replica, databases/postgresql/replicazione, databases/kubernetes-cloud/managed-databases]
official_docs: https://www.postgresql.org/docs/current/continuous-archiving.html
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Backup e Point-in-Time Recovery

## Panoramica

Il backup protegge da scenari che la replica non può coprire: errori dell'operatore (`DROP TABLE` replicato su tutte le standby), corruzione dati (replicata in tempo reale), o disastri che distruggono tutti i nodi del cluster.

**Tipi di backup:**

| Tipo | Tool | Velocità restore | Granularità | Uso |
|------|------|-----------------|-------------|-----|
| **Logico** | `pg_dump`, `pg_dumpall` | Lenta (replay SQL) | Singolo DB/tabella | Migrazioni, archivio selettivo |
| **Fisico (base backup)** | `pg_basebackup`, pgBackRest | Rapida (copia file) | Intero cluster | Produzione, PITR |
| **WAL archiving** | archive_command + pgBackRest | N/A (complementa il fisico) | Ogni transazione | PITR, replica remota |

Il **Point-in-Time Recovery (PITR)** combina un base backup + WAL archiviati per ripristinare il database esattamente a un istante nel tempo (es. 5 minuti prima del `DROP TABLE` accidentale).

## Backup Logico — pg_dump

```bash
# Backup di un singolo database (formato custom, compresso)
pg_dump \
  --host=localhost \
  --username=postgres \
  --format=custom \     # custom = compresso, selettivo in restore
  --compress=9 \
  --file=mydb_20240115.dump \
  mydb

# Restore da dump custom
pg_restore \
  --host=localhost \
  --username=postgres \
  --dbname=mydb_restored \
  --jobs=4 \            # parallelo su 4 worker
  mydb_20240115.dump

# Backup di tutte le tabelle tranne quelle di log (esclusione)
pg_dump --exclude-table='log_*' mydb > mydb_no_logs.sql

# Backup solo schema (no dati)
pg_dump --schema-only mydb > schema.sql

# Backup tutti i database + ruoli + tablespace (cluster-wide)
pg_dumpall --file=cluster_backup.sql
```

!!! warning "pg_dump non è sufficiente per la produzione"
    `pg_dump` è un backup point-in-time: blocca le transazioni durante la lettura (in modalità `--serializable-deferrable`) o produce un backup leggermente inconsistente. Non permette PITR. Per produzione, usare backup fisico + WAL archiving.

---

## pg_basebackup — Backup Fisico

```bash
# Backup fisico completo del cluster PostgreSQL
pg_basebackup \
  --host=localhost \
  --username=replicator \
  --pgdata=/backup/base/20240115 \
  --format=tar \          # comprime in .tar.gz
  --compress=9 \
  --wal-method=stream \   # include WAL durante il backup (coerente senza archivio separato)
  --checkpoint=fast \     # forza checkpoint immediato invece di aspettare
  --progress \
  --verbose

# Dimensione del backup (utile per pianificare lo storage)
du -sh /backup/base/20240115/
```

---

## WAL Archiving — Continuous Archiving

Il WAL archiving conserva ogni file WAL generato su storage esterno. Combinato con un base backup, permette il PITR a qualsiasi secondo dall'ultimo base backup.

```ini
# postgresql.conf
archive_mode = on
archive_command = 'aws s3 cp %p s3://my-wal-archive/wal/%f'
# %p = path completo del file WAL
# %f = nome del file WAL (senza path)

# Verifica che il comando ha successo (exit code 0)
archive_status = 'check'

# Alternativa: pgBackRest gestisce l'archivio direttamente
archive_command = 'pgbackrest --stanza=mydb archive-push %p'
```

```bash
# Verifica che l'archivio funzioni
psql -c "SELECT * FROM pg_stat_archiver;"
# Se archived_count non cresce → problema con archive_command
```

---

## pgBackRest — Backup Enterprise

[pgBackRest](https://pgbackrest.org/) è il tool di backup più avanzato per PostgreSQL: gestisce backup fisici, WAL archiving, backup incrementali/differenziali, compressione, cifratura e restore in parallelo.

```ini
# /etc/pgbackrest/pgbackrest.conf

[global]
repo1-path=/backup/pgbackrest           # Locale
# oppure S3:
repo1-type=s3
repo1-s3-bucket=my-postgres-backups
repo1-s3-region=us-east-1
repo1-s3-key=AKIA...
repo1-s3-key-secret=...

repo1-retention-full=2                  # Mantieni 2 backup full
repo1-retention-diff=7                  # Mantieni 7 backup differenziali
repo1-cipher-type=aes-256-cbc          # Cifratura del backup
repo1-cipher-pass=secure-passphrase

# Compressione
compress-type=lz4                       # lz4 (veloce) o zst (migliore compressione)
compress-level=3

[mydb]
pg1-path=/var/lib/postgresql/17/main
pg1-port=5432
pg1-user=postgres
```

### Comandi pgBackRest

```bash
# Inizializza lo stanza (prima volta)
pgbackrest --stanza=mydb stanza-create

# Backup completo
pgbackrest --stanza=mydb --type=full backup

# Backup differenziale (delta dall'ultimo full)
pgbackrest --stanza=mydb --type=diff backup

# Backup incrementale (delta dall'ultimo backup qualsiasi)
pgbackrest --stanza=mydb --type=incr backup

# Lista dei backup disponibili
pgbackrest --stanza=mydb info

# Verifica integrità del backup
pgbackrest --stanza=mydb check

# Restore (PostgreSQL deve essere fermo)
systemctl stop postgresql
pgbackrest --stanza=mydb --delta restore   # --delta riusa file non cambiati
systemctl start postgresql
```

### Schedule con pg_cron

```sql
-- Backup automatici schedulati (da pg_cron)
-- Full il domenica, differenziale ogni giorno, WAL ogni minuto
SELECT cron.schedule('full-backup',  '0 2 * * 0', 'SELECT pg_catalog.pg_switch_wal()');
-- ↑ In realtà il backup viene schedulato sul sistema operativo con cron di sistema

-- /etc/cron.d/pgbackrest
-- 0  2  *  *  0   postgres  pgbackrest --stanza=mydb --type=full backup
-- 0  2  *  *  1-6 postgres  pgbackrest --stanza=mydb --type=diff backup
```

---

## PITR — Point-in-Time Recovery

Scenario: `DROP TABLE ordini` eseguito alle 14:32:05. Vuoi ripristinare a 14:31:59.

```bash
# 1. Ferma PostgreSQL
systemctl stop postgresql

# 2. Ripristina il base backup più recente
pgbackrest --stanza=mydb \
           --target="2024-01-15 14:31:59" \
           --target-action=promote \
           restore

# pgBackRest automaticamente:
# a. Ripristina il backup fisico più recente prima del target
# b. Configura recovery_target_time in postgresql.auto.conf
# c. Usa il WAL archiviato per replay fino al target

# 3. Avvia PostgreSQL — esegue il WAL replay automaticamente
systemctl start postgresql

# PostgreSQL loga il progresso del recovery:
# LOG: starting point-in-time recovery to 2024-01-15 14:31:59+00
# LOG: restored log file "000000010000000000000042" from archive
# LOG: consistent recovery state reached at 0/42000028
# LOG: recovery stopping before commit of transaction 5429, time 2024-01-15 14:32:05+00
# LOG: pausing at the end of recovery
# HINT: execute pg_wal_replay_resume() to promote
```

### Target di Recovery

```sql
-- Tipi di target (configurati in postgresql.conf o postgresql.auto.conf):

-- Per timestamp (il più comune)
recovery_target_time = '2024-01-15 14:31:59'

-- Per LSN (Log Sequence Number — preciso al byte)
recovery_target_lsn = '0/42000020'

-- Per transaction ID (XID)
recovery_target_xid = '5428'

-- Per named restore point (creato prima con pg_create_restore_point())
recovery_target_name = 'before-migration'

-- Azione dopo aver raggiunto il target
recovery_target_action = 'promote'    # promuovi a primary (default)
recovery_target_action = 'pause'      # fermati e aspetta istruzione manuale
recovery_target_action = 'shutdown'   # fermati e aspetta riavvio
```

---

## Backup su Managed Services

### AWS RDS

```bash
# RDS gestisce automaticamente backup e WAL archiving

# Configura retention window
aws rds modify-db-instance \
  --db-instance-identifier mydb \
  --backup-retention-period 30 \         # 30 giorni di WAL + snapshot giornalieri
  --preferred-backup-window "02:00-03:00" \
  --apply-immediately

# Restore a punto nel tempo (AWS Console o CLI)
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier mydb \
  --target-db-instance-identifier mydb-restored \
  --restore-time "2024-01-15T14:31:59Z"

# Crea snapshot manuale
aws rds create-db-snapshot \
  --db-instance-identifier mydb \
  --db-snapshot-identifier mydb-before-migration

# Restore da snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier mydb-from-snapshot \
  --db-snapshot-identifier mydb-before-migration
```

---

## Backup Testing — Fondamentale

**Un backup non testato non è un backup.** Testare regolarmente il restore:

```bash
#!/bin/bash
# Script di test restore settimanale (da eseguire su istanza di test)

set -euo pipefail

TARGET_HOST="test-postgres"
STANZA="mydb"
LOG_FILE="/var/log/backup-test-$(date +%Y%m%d).log"

echo "=== Backup restore test - $(date) ===" | tee -a "$LOG_FILE"

# 1. Ripristina backup più recente su istanza di test
systemctl stop postgresql@test
pgbackrest --stanza="$STANZA" \
           --pg1-path=/var/lib/postgresql/test \
           --target-action=promote \
           restore 2>&1 | tee -a "$LOG_FILE"
systemctl start postgresql@test

# 2. Verifica che PostgreSQL si avvii e sia consistente
sleep 10
psql -h "$TARGET_HOST" -c "SELECT count(*) FROM ordini;" 2>&1 | tee -a "$LOG_FILE"
psql -h "$TARGET_HOST" -c "CHECKPOINT;" 2>&1 | tee -a "$LOG_FILE"

# 3. Verifica integrità dati
psql -h "$TARGET_HOST" -c "
    SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 10;
" 2>&1 | tee -a "$LOG_FILE"

echo "=== Test completato: $(date) ===" | tee -a "$LOG_FILE"
```

---

## Best Practices

- **3-2-1 rule**: 3 copie dei dati, su 2 media diversi, 1 offsite. WAL archivio su S3 + snapshot RDS + export S3 cross-region
- **Testare restore ogni settimana**: automatizzare il test restore su un'istanza separata, verificare l'integrità dei dati
- **Cifrare il backup**: `pgbackrest` supporta AES-256 nativo — i backup contengono dati sensibili
- **Monitorare il WAL archivio**: se `pg_stat_archiver.last_failed_wal` cresce o `archive_command` fallisce → PITR non funzionerà → alert immediato
- **RPO = retention WAL**: il PITR è disponibile fino a `backup_retention_period` (RDS) o finché il WAL esiste nell'archivio. Se WAL viene eliminato → PITR impossibile per quel periodo

## Troubleshooting

### Scenario 1 — PITR si ferma prima del target

**Sintomo:** Il recovery termina prima del timestamp richiesto. PostgreSQL loga `recovery stopping before ...` con un tempo precedente al target, oppure si ferma con `requested WAL segment ... has already been removed`.

**Causa:** Uno o più file WAL necessari per il replay non sono presenti nell'archivio. Questo accade se `archive_command` ha fallito silenziosamente, se il bucket S3 ha subito una cancellazione, o se la retention policy ha eliminato WAL ancora necessari.

**Soluzione:** Verificare lo stato dell'archivio e identificare il gap.

```bash
# Controlla l'ultimo WAL archiviato correttamente e gli errori
psql -c "SELECT archived_count, last_archived_wal, last_archived_time,
                failed_count, last_failed_wal, last_failed_time
         FROM pg_stat_archiver;"

# Con pgBackRest: verifica integrità archivio WAL
pgbackrest --stanza=mydb check

# Lista i WAL disponibili nel bucket S3
aws s3 ls s3://my-wal-archive/wal/ --recursive | sort | tail -20

# Verifica che il WAL mancante esista nel backup corrente
pgbackrest --stanza=mydb info
```

---

### Scenario 2 — `archive_command` fallisce silenziosamente

**Sintomo:** `pg_stat_archiver.failed_count` cresce, `last_failed_wal` aggiornato di recente, ma nessun alert ha notificato il problema. Il PITR risulterà incompleto se si tenta un restore.

**Causa:** L'`archive_command` configurato in `postgresql.conf` restituisce exit code 0 anche quando il trasferimento non avviene (es. script bash con `|| true` implicito, permessi S3 scaduti, bucket pieno).

**Soluzione:**

```bash
# Testa manualmente l'archive_command con un WAL reale
WAL_FILE=$(ls /var/lib/postgresql/17/main/pg_wal/*.history 2>/dev/null | head -1)
# Simula il comando (sostituisci %p e %f)
aws s3 cp "$WAL_FILE" s3://my-wal-archive/wal/test-wal && echo "OK: exit $?" || echo "FAIL: exit $?"

# Verifica permessi IAM per l'utente che esegue PostgreSQL
aws sts get-caller-identity
aws s3api put-object --bucket my-wal-archive --key wal/test --body /dev/null

# Reset contatore errori dopo fix (richiede pg_reload_conf)
psql -c "SELECT pg_reload_conf();"
psql -c "SELECT pg_stat_reset_shared('archiver');"
```

---

### Scenario 3 — pg_basebackup fallisce con "could not connect"

**Sintomo:** `pg_basebackup` esce con `FATAL: no pg_hba.conf entry for replication connection` oppure `FATAL: number of requested standby connections exceeds max_wal_senders`.

**Causa:** Il server non è configurato per accettare connessioni di replica (manca entry in `pg_hba.conf`) oppure `max_wal_senders` è troppo basso per supportare backup + repliche esistenti.

**Soluzione:**

```bash
# Verifica configurazione corrente
psql -c "SHOW max_wal_senders;"
psql -c "SELECT count(*) FROM pg_stat_replication;"

# Fix: aumenta max_wal_senders in postgresql.conf (richiede riavvio)
# max_wal_senders = 10   (default: 10, aumentare se necessario)

# Fix: aggiungi entry in pg_hba.conf per il backup user
echo "host  replication  replicator  backup-server-ip/32  scram-sha-256" >> /etc/postgresql/17/main/pg_hba.conf
psql -c "SELECT pg_reload_conf();"

# Testa connessione di replica
psql -h localhost -U replicator -c "IDENTIFY_SYSTEM;" replication=1
```

---

### Scenario 4 — Restore pgBackRest lento (ore per dati di pochi GB)

**Sintomo:** Il restore impiega molto più tempo del previsto. Il progresso di pgBackRest mostra un basso throughput.

**Causa:** pgBackRest usa di default 1 processo per il restore. Su repository S3 con molti file, il download single-thread diventa il collo di bottiglia.

**Soluzione:**

```bash
# Verifica quanti processi sta usando (output pgBackRest info)
pgbackrest --stanza=mydb info

# Restore parallelo con più processi
pgbackrest --stanza=mydb \
           --process-max=8 \          # usa 8 thread paralleli
           --delta \                   # riusa file locali non cambiati
           restore

# Aggiungi process-max come default nel config per futuri restore
# /etc/pgbackrest/pgbackrest.conf
# [global]
# process-max=8

# Monitora velocità durante il restore
watch -n 5 'du -sh /var/lib/postgresql/17/main/'
```

## Riferimenti

- [PostgreSQL Continuous Archiving](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [pgBackRest User Guide](https://pgbackrest.org/user-guide.html)
- [Barman — Backup and Recovery Manager](https://www.pgbarman.org/documentation/)
- [AWS RDS PITR](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIT.html)
