---
title: "Backup e Point-in-Time Recovery"
slug: backup-pitr
category: databases
tags: [backup, pitr, wal-archiving, pg-basebackup, pgbackrest, barman, recovery]
search_keywords: [postgresql backup, point in time recovery, wal archiving, pg_basebackup, pgbackrest, barman, continuous archiving, base backup, wal archive, recovery target time, recovery target lsn, recovery target xid, restore point, pg_dumpall, pg_dump, logical backup, physical backup, incremental backup, differential backup, s3 backup postgresql, rds backup, aurora backup, rpo backup, retention policy backup, pitr postgresql, restore postgresql from backup]
parent: databases/replicazione-ha/_index
related: [databases/replicazione-ha/strategie-replica, databases/postgresql/replicazione, databases/kubernetes-cloud/managed-databases]
official_docs: https://www.postgresql.org/docs/current/continuous-archiving.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
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
# (custom = compresso, restore selettivo)
pg_dump \
  --host=localhost \
  --username=postgres \
  --format=custom \
  --compress=9 \
  --file=mydb_20240115.dump \
  mydb

# Restore da dump custom (il DB di destinazione deve esistere: createdb mydb_restored)
# --jobs=4 = parallelo su 4 worker
pg_restore \
  --host=localhost \
  --username=postgres \
  --dbname=mydb_restored \
  --jobs=4 \
  mydb_20240115.dump

# Backup di tutte le tabelle tranne quelle di log (esclusione)
pg_dump --exclude-table='log_*' mydb > mydb_no_logs.sql

# Backup solo schema (no dati)
pg_dump --schema-only mydb > schema.sql

# Backup tutti i database + ruoli + tablespace (cluster-wide)
pg_dumpall --file=cluster_backup.sql
```

!!! warning "pg_dump non è sufficiente per la produzione"
    `pg_dump` è consistente (usa uno snapshot MVCC singolo e non blocca scritture/letture normali), ma fotografa **un solo istante**: tutto ciò che è successo dopo è perso (RPO = intervallo fra dump), non permette PITR e il restore è lento (replay SQL + rebuild indici). Tiene però una transazione lunga aperta, che ritarda il vacuum. Per produzione, usare backup fisico + WAL archiving; `pg_dump` resta utile per migrazioni e upgrade major.

---

## pg_basebackup — Backup Fisico

```bash
# Backup fisico completo del cluster PostgreSQL
# --format=tar        un .tar per tablespace (con --compress=gzip:9 → .tar.gz; PG15+ accetta anche lz4/zstd)
# --wal-method=stream include i WAL generati durante il backup → il backup è autoconsistente
# --checkpoint=fast   checkpoint immediato invece di attendere lo spread
pg_basebackup \
  --host=localhost \
  --username=replicator \
  --pgdata=/backup/base/20240115 \
  --format=tar \
  --compress=gzip:9 \
  --wal-method=stream \
  --checkpoint=fast \
  --progress \
  --verbose

# Dimensione del backup (utile per pianificare lo storage)
du -sh /backup/base/20240115/
```

**PostgreSQL 17+ — backup incrementale nativo:** `pg_basebackup --incremental=<backup_manifest del precedente>` salva solo i blocchi modificati (richiede `summarize_wal = on`); il restore si ottiene combinando la catena con `pg_combinebackup`. Per cluster grandi riduce tempo e spazio, ma `pg_basebackup` non gestisce retention, cifratura né repository remoti: per questo servono pgBackRest o Barman.

---

## WAL Archiving — Continuous Archiving

Il WAL archiving conserva ogni file WAL generato su storage esterno. Combinato con un base backup, permette il PITR a qualsiasi secondo dall'ultimo base backup.

```ini
# postgresql.conf  (archive_mode richiede RIAVVIO; archive_command solo reload)
wal_level = replica          # minimo necessario per archiviare
archive_mode = on
archive_timeout = 60         # forza lo switch del WAL ogni 60s → limita la perdita (RPO) nei periodi di basso traffico
archive_command = 'aws s3 cp %p s3://my-wal-archive/wal/%f'
# %p = path completo del file WAL
# %f = nome del file WAL (senza path)
# Il comando DEVE restituire 0 solo se il file è stato archiviato con successo:
# se ≠ 0 PostgreSQL ritenta e il WAL non viene riciclato (pg_wal si riempie).

# Alternativa raccomandata: pgBackRest gestisce l'archivio (verifica, retry, compressione, async)
# archive_command = 'pgbackrest --stanza=mydb archive-push %p'
```

!!! note "Perché non un semplice `aws s3 cp`"
    Un comando "fatto in casa" non verifica la sovrascrittura di un file già presente, non fa fsync/checksum, non è parallelo e non conosce lo stanza/versione del cluster. pgBackRest `archive-push` fa tutto questo (opzione `archive-async=y` per alti volumi di WAL). In PG15+ in alternativa si può usare un `archive_library` (modulo C) al posto di `archive_command`.

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
repo1-s3-endpoint=s3.us-east-1.amazonaws.com
# Preferire credenziali da IAM role (niente chiavi nel file):
repo1-s3-key-type=auto
# Solo se non si usa un ruolo: repo1-s3-key-type=shared + repo1-s3-key / repo1-s3-key-secret

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
# Inizializza lo stanza (prima volta; PostgreSQL attivo, archive_command già configurato)
pgbackrest --stanza=mydb stanza-create

# Backup completo
pgbackrest --stanza=mydb --type=full backup

# Backup differenziale (delta dall'ultimo full)
pgbackrest --stanza=mydb --type=diff backup

# Backup incrementale (delta dall'ultimo backup qualsiasi)
pgbackrest --stanza=mydb --type=incr backup

# Lista dei backup disponibili
pgbackrest --stanza=mydb info

# Verifica configurazione stanza e funzionamento di archive-push (forza uno switch WAL)
pgbackrest --stanza=mydb check

# Verifica checksum dei file nel repository
pgbackrest --stanza=mydb verify

# Restore (PostgreSQL deve essere fermo)
systemctl stop postgresql
pgbackrest --stanza=mydb --delta restore   # --delta riusa file non cambiati
systemctl start postgresql
```

### Schedule con cron di sistema

I backup si schedulano dal sistema operativo (cron o systemd timer), non da `pg_cron` (che gira dentro PostgreSQL). Il WAL non va schedulato: lo spedisce `archive_command` in continuo.

```bash
# /etc/cron.d/pgbackrest — full la domenica, differenziale lun-sab
0  2  *  *  0    postgres  pgbackrest --stanza=mydb --type=full backup
0  2  *  *  1-6  postgres  pgbackrest --stanza=mydb --type=diff backup
```

---

## PITR — Point-in-Time Recovery

Scenario: `DROP TABLE ordini` eseguito alle 14:32:05. Vuoi ripristinare a 14:31:59.

```bash
# 1. Ferma PostgreSQL
systemctl stop postgresql

# 2. Ripristina il base backup più recente prima del target
# --type=time è OBBLIGATORIO: senza, pgBackRest ignora --target e fa replay fino alla fine del WAL
# --delta riusa i file già presenti nel data directory (che non è vuoto)
# --target-action=pause: ci si ferma al target per VERIFICARE i dati prima di promuovere
pgbackrest --stanza=mydb --delta \
           --type=time \
           --target="2024-01-15 14:31:59+00" \
           --target-action=pause \
           restore

# pgBackRest automaticamente:
# a. Ripristina il backup fisico più recente prima del target
# b. Configura recovery_target_time + restore_command in postgresql.auto.conf e crea recovery.signal
# c. PostgreSQL usa il WAL archiviato per replay fino al target

# 3. Avvia PostgreSQL — esegue il WAL replay automaticamente
systemctl start postgresql

# PostgreSQL loga il progresso del recovery (esempio):
# LOG: starting point-in-time recovery to 2024-01-15 14:31:59+00
# LOG: restored log file "000000010000000000000042" from archive
# LOG: consistent recovery state reached at 0/42000028
# LOG: recovery stopping before commit of transaction 5429, time 2024-01-15 14:32:05+00
# LOG: pausing at the end of recovery
# HINT: Execute pg_wal_replay_resume() to promote.

# 4. Verifica i dati (la tabella esiste?). Se OK → promuovi; se il target era troppo tardi/presto
#    ripeti il restore con un altro target (la promozione è irreversibile sulla timeline).
psql -c "SELECT pg_wal_replay_resume();"
```

### Target di Recovery

```ini
# Tipi di target (postgresql.conf / postgresql.auto.conf). Se ne può impostare UNO solo.

# Per timestamp (il più comune; specificare il fuso orario)
recovery_target_time = '2024-01-15 14:31:59+00'

# Per LSN (Log Sequence Number — preciso al byte)
recovery_target_lsn = '0/42000020'

# Per transaction ID (XID)
recovery_target_xid = '5428'

# Per named restore point (creato prima con SELECT pg_create_restore_point('before-migration'))
recovery_target_name = 'before-migration'

# Inclusivo o no del target (default on = include la transazione al target)
recovery_target_inclusive = on

# Azione dopo aver raggiunto il target (default: pause)
recovery_target_action = 'pause'      # fermati in read-only e aspetta pg_wal_replay_resume()
# recovery_target_action = 'promote'  # promuovi subito a primary
# recovery_target_action = 'shutdown' # spegni il server
```

Con pgBackRest gli equivalenti sono `--type=time|lsn|xid|name|immediate` e `--target=...`. Dopo la promozione PostgreSQL apre una **nuova timeline**: i WAL della vecchia timeline restano nell'archivio e, per un secondo PITR, si può selezionare la timeline con `--target-timeline`.

---

## Backup su Managed Services

### AWS RDS

```bash
# RDS gestisce automaticamente backup e WAL archiving

# Configura retention window
aws rds modify-db-instance \
  --db-instance-identifier mydb \
  --backup-retention-period 30 \
  --preferred-backup-window "02:00-03:00" \
  --apply-immediately
# retention 1-35 giorni (0 = backup disabilitati): snapshot giornalieri + WAL continui per PITR

# Restore a punto nel tempo (AWS Console o CLI)
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier mydb \
  --target-db-instance-identifier mydb-restored \
  --restore-time "2024-01-15T14:31:59Z"
# (oppure --use-latest-restorable-time). Il restore crea SEMPRE una nuova istanza
# con nuovo endpoint: l'applicazione va ripuntata.

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
- **RPO e finestra PITR sono cose diverse**: l'RPO dipende dal ritardo dell'archiviazione WAL (`archive_timeout`, o replica sincrona per RPO≈0); la finestra di PITR dipende dalla retention (`backup_retention_period` su RDS, `repo1-retention-*` su pgBackRest). Se un WAL viene eliminato → PITR impossibile oltre quel punto
- **Barman** è l'alternativa a pgBackRest (server di backup dedicato, supporto a `pg_receivewal` per RPO≈0 in streaming); stesse regole: stanza/server dedicato, retention, `barman check`, restore testati

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

**Causa:** `failed_count` cresce perché `archive_command` esce con codice ≠ 0 (credenziali/permessi S3 scaduti, bucket irraggiungibile, rete). Il pericolo è doppio: PostgreSQL non ricicla i WAL non archiviati, quindi `pg_wal` cresce fino a riempire il disco (e il primary si ferma), e il PITR ha un buco. Il caso opposto — comando che esce 0 senza aver copiato (es. wrapper con `|| true`) — non è rilevabile da `pg_stat_archiver` ed è il motivo per cui serve `pgbackrest check`/restore test.

**Soluzione:**

```bash
# Testa manualmente l'archive_command come utente postgres con un file reale
sudo -u postgres aws s3 cp /var/lib/postgresql/17/main/PG_VERSION s3://my-wal-archive/wal/test-wal \
  && echo "OK: exit 0" || echo "FAIL"

# Verifica identità/permessi IAM dell'utente che esegue PostgreSQL
sudo -u postgres aws sts get-caller-identity

# Dopo il fix l'archiver riprende da solo i WAL pendenti (nessun reload necessario
# se il comando non è cambiato). Opzionale: azzera i contatori per il monitoraggio
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
# --process-max=8 = 8 processi paralleli; --delta = riusa file locali non cambiati
pgbackrest --stanza=mydb \
           --process-max=8 \
           --delta \
           restore

# Aggiungi process-max come default nel config per futuri backup/restore
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
