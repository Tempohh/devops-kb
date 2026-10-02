---
title: "Online Schema Change — DDL senza downtime"
slug: online-schema-change
category: databases
tags: [database, ddl, schema, zero-downtime, postgresql, mysql, gh-ost, pt-online-schema-change, locking, migrations]
search_keywords: [online schema change, OSC, zero downtime DDL, ddl senza downtime, alter table lock, lock queue, ACCESS EXCLUSIVE, metadata lock, MDL, lock_timeout, statement_timeout, CREATE INDEX CONCURRENTLY, indice INVALID, NOT VALID, VALIDATE CONSTRAINT, add column default, pg_repack, pgroll, ALGORITHM INSTANT, ALGORITHM INPLACE, LOCK NONE, gh-ost, pt-online-schema-change, pt-osc, Percona Toolkit, Vitess online DDL, Spirit, cut-over, ghost table, shadow table, expand contract, backfill, replica lag, schema migration grandi tabelle, rename colonna, large table alter, binlog, trigger-based]
parent: databases/fondamentali/_index
related: [databases/fondamentali/schema-migrations, databases/fondamentali/indici, databases/fondamentali/transazioni-concorrenza, databases/postgresql/mvcc-vacuum, databases/mysql/architettura-replicazione, databases/postgresql/major-version-upgrade]
official_docs: https://www.postgresql.org/docs/current/sql-altertable.html
status: draft
difficulty: advanced
last_updated: 2026-10-03
---

# Online Schema Change — DDL senza downtime

## Panoramica

Un `ALTER TABLE` che su un database di sviluppo termina in un millisecondo può fermare la produzione per minuti su una tabella da centinaia di milioni di righe. Il problema raramente è la durata del DDL in sé: è il **lock** che richiede e la **coda** che crea. I tool di versioning ([Schema Migrations](schema-migrations.md)) dicono *quando* applicare uno script; questa guida spiega *come* scrivere e lanciare il DDL in modo che non blocchi il traffico, su PostgreSQL e MySQL.

Le tre leve sono sempre le stesse: (1) scegliere la variante di DDL che prende il lock più debole o che è solo metadata (`CONCURRENTLY`, `NOT VALID`, `ALGORITHM=INSTANT`); (2) proteggersi dalla lock queue con timeout brevi e retry; (3) quando il DB non offre una variante online, copiare la tabella in background con un tool esterno (gh-ost, pt-online-schema-change, pg_repack, pgroll) e fare uno swap atomico. Sopra a tutto sta il pattern expand/contract, che spezza le modifiche incompatibili (rename, cambio tipo) in release compatibili.

Non serve per tabelle piccole (< qualche milione di righe, DDL < 1 s) dove un lock breve è accettabile, né per modifiche già puramente metadata: in quei casi il tool aggiunge solo complessità.

## Concetti Chiave

!!! note "Lock queue — il vero killer"
    Un `ALTER TABLE` che richiede `ACCESS EXCLUSIVE` (PostgreSQL) o un metadata lock esclusivo (MySQL) deve **attendere** che tutte le transazioni che toccano la tabella finiscano. Mentre attende, **ogni nuova query sulla tabella si accoda dietro di lui**, anche un semplice `SELECT`. Una sola transazione lunga + un ALTER "veloce" = tabella completamente bloccata finché la transazione lunga non termina. Il DDL non è mai stato lento: è stato *in coda*, e ha messo in coda tutti gli altri.

- **Rewrite della tabella**: il DDL riscrive tutte le righe (nuovo file/tablespace). Costo proporzionale alla dimensione, lock esclusivo per tutta la durata, WAL/binlog e I/O enormi, replica lag. È ciò che le varianti online cercano di evitare.
- **Metadata-only**: il DDL modifica solo il catalogo. Istantaneo a prescindere dalla dimensione, ma richiede comunque il lock esclusivo *per un istante* (quindi soggetto alla lock queue).
- **Scansione di validazione**: alcuni DDL (aggiungere un vincolo, `SET NOT NULL`) non riscrivono, ma devono leggere tutta la tabella per verificare i dati. Si può spostare la scansione fuori dal lock esclusivo (`NOT VALID` + `VALIDATE`).
- **Ghost / shadow table**: tabella vuota con lo schema nuovo, popolata in background dal tool OSC e poi scambiata con l'originale via `RENAME` atomico (cut-over).
- **Expand/contract** (a.k.a. parallel change): ogni modifica incompatibile è scomposta in step additivi compatibili con la versione precedente *e* successiva del codice, così deploy e rollback restano sicuri.
- **Backfill**: popolamento dei dati storici di una nuova colonna/tabella, fatto a batch con throttling, mai in una singola `UPDATE` gigante.

| Esigenza | PostgreSQL | MySQL 8.0 |
|---|---|---|
| Aggiungere colonna | metadata-only (anche con default costante, PG11+) | `ALGORITHM=INSTANT` |
| Aggiungere indice | `CREATE INDEX CONCURRENTLY` | `ALGORITHM=INPLACE, LOCK=NONE` |
| Aggiungere vincolo (FK/CHECK) | `NOT VALID` + `VALIDATE CONSTRAINT` | FK: `foreign_key_checks=0` (rischioso) o OSC |
| Cambiare tipo colonna | rewrite (salvo casi binary-coercible) → expand/contract | `ALGORITHM=COPY` → gh-ost / pt-osc |
| Rinominare colonna | metadata, ma rompe il codice → expand/contract | `INSTANT`/`INPLACE`, ma rompe il codice → expand/contract |
| Recuperare bloat / riscrivere | `pg_repack` | OSC (`ALTER TABLE t ENGINE=InnoDB` via gh-ost) |

## Architettura / Come Funziona

### Lock queue in PostgreSQL

`ALTER TABLE` prende `ACCESS EXCLUSIVE`, che confligge con *tutti* i lock inclusi `ACCESS SHARE` (SELECT). Il lock manager serve le richieste in ordine di arrivo: se T1 (transazione lunga) tiene `ACCESS SHARE`, l'ALTER (T2) attende, e le query successive (T3, T4…) si accodano dietro T2 perché confliggerebbero con la sua richiesta in attesa.

```
T1: BEGIN; SELECT ... FROM orders;   -- tiene ACCESS SHARE, transazione "dimenticata" aperta
T2: ALTER TABLE orders ADD ...;      -- attende ACCESS EXCLUSIVE (bloccato da T1)
T3: SELECT ... FROM orders;          -- attende dietro T2  ← l'applicazione è ferma
T4: INSERT INTO orders ...;          -- attende dietro T2
```

La difesa è un `lock_timeout` breve: l'ALTER rinuncia dopo pochi secondi e il traffico riparte; si riprova in un loop. Il costo di un tentativo fallito è quasi zero, quello di un ALTER in coda senza timeout è un incidente.

### Metadata lock in MySQL

In MySQL ogni statement acquisisce un **metadata lock (MDL)** sulle tabelle che tocca, e lo tiene fino a fine transazione. L'`ALTER TABLE` richiede un MDL esclusivo all'inizio e alla fine (anche per DDL "online"): se una transazione lunga ha già un MDL condiviso, l'ALTER attende e tutte le query successive si accodano — stesso meccanismo di PostgreSQL, stesso sintomo (`Waiting for table metadata lock`).

### Algoritmi di ALTER in MySQL (InnoDB)

| `ALGORITHM` | Cosa fa | Concorrenza DML | Costo |
|---|---|---|---|
| `INSTANT` | Solo metadata nel dizionario dati | Piena | Istantaneo |
| `INPLACE` | Modifica sul posto o rebuild interno, senza copia in tabella temporanea | Con `LOCK=NONE` lettura+scrittura permesse (DML loggato e riapplicato a fine) | Proporzionale alla tabella, I/O e replica lag |
| `COPY` | Crea tabella nuova, copia riga per riga, swap | Solo lettura (`LOCK=SHARED`) | Massimo; blocca le scritture |

Specificare **esplicitamente** `ALGORITHM` e `LOCK` è una safety net: se l'operazione non è supportata a quel livello, MySQL fallisce subito con errore invece di degradare silenziosamente a `COPY`.

### OSC esterni: trigger-based vs binlog-based

```
pt-online-schema-change (trigger-based)        gh-ost (binlog-based)
  tabella originale ──trigger INS/UPD/DEL──►     tabella originale ──binlog (ROW)──► gh-ost
        │                                              │                              │
        ▼ copia a chunk                                ▼ copia a chunk                ▼ applica eventi
  tabella _new  ◄──────────────────────┘         tabella _gho  ◄───────────────────────┘
        │ RENAME atomico                                │ cut-over (lock + RENAME)
        ▼                                               ▼
  tabella nuova                                  tabella nuova
```

- **pt-osc**: crea trigger sulla tabella originale che replicano ogni scrittura nella copia. Semplice e maturo, ma i trigger aggiungono overhead *sincrono* a ogni scrittura applicativa, non sono sospendibili (non si può "mettere in pausa" il carico di un trigger) e prendono lock di metadata alla creazione.
- **gh-ost** (GitHub): nessun trigger; legge il **binlog** (di default da una replica) e riapplica gli eventi sulla ghost table. L'overhead sul primario è minimo, la migrazione è **pausabile** e **throttle-able** (replica lag, load) e il cut-over è controllabile da file flag/socket. Richiede `binlog_format=ROW` e `binlog_row_image=FULL`, una PK o unique key sulla tabella, e **non supporta** tabelle con foreign key né trigger.
- **Spirit** (Block/Cash App, successore concettuale di gh-ost, MySQL 8): multi-thread, senza trigger, sempre binlog-based, con checksum di verifica integrata.
- **Vitess online DDL**: strategie `vitess` (nativa), `gh-ost`, `pt-osc` selezionabili via `ddl_strategy`, con scheduling e revert integrati nel cluster.

### Online DDL in PostgreSQL oltre il DDL nativo

- **pg_repack**: ricostruisce tabella/indici online (trigger + tabella di log), con `ACCESS EXCLUSIVE` solo nello swap finale. Pensato per recuperare **bloat** (vedi [MVCC e VACUUM](../postgresql/mvcc-vacuum.md)), non per cambiare lo schema. Richiede PK o unique index NOT NULL e spazio libero ≈ dimensione tabella.
- **pgroll** (Xata): applica migration in modalità expand/contract automatica. Durante la migrazione espone *due versioni di schema* contemporaneamente (viste in schemi separati `public_<migration>`) così la vecchia e la nuova versione dell'app convivono; `complete` consolida, `rollback` annulla.

## Configurazione & Pratica

### PostgreSQL: DDL con retry e timeout

Template per qualunque DDL che richiede un lock forte. `lock_timeout` limita l'attesa del lock (il danno da coda); `statement_timeout` limita l'esecuzione una volta ottenuto il lock.

```sql
-- Sessione dedicata alla migration
SET lock_timeout = '3s';          -- se non prende il lock entro 3s, abbandona (nessuna coda prolungata)
SET statement_timeout = '30s';    -- metadata-only DDL: se dura di più, qualcosa non va
ALTER TABLE orders ADD COLUMN shipped_at timestamptz;
```

Un singolo tentativo spesso fallisce su tabelle molto usate: serve un loop di retry con backoff, a livello di script/CI.

```bash
#!/usr/bin/env bash
# retry-ddl.sh — ritenta il DDL finché prende il lock
set -u
SQL="ALTER TABLE orders ADD COLUMN shipped_at timestamptz;"
for attempt in $(seq 1 20); do
  if psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
       -c "SET lock_timeout='3s'; SET statement_timeout='30s'; ${SQL}"; then
    echo "OK al tentativo ${attempt}"; exit 0
  fi
  echo "tentativo ${attempt} fallito (lock_timeout?), retry tra $((attempt*2))s"
  sleep $((attempt*2))
done
echo "DDL non applicato dopo 20 tentativi" >&2; exit 1
```

!!! warning "Imposta lock_timeout a livello di sessione, non globale"
    `ALTER ROLE migrator SET lock_timeout = '3s'` è una buona default per il ruolo che esegue le migration. **Non** impostarlo globalmente: romperebbe i job applicativi legittimi che attendono lock. Verifica sempre `SHOW lock_timeout;` nella sessione prima di lanciare un DDL pesante.

### PostgreSQL: CREATE INDEX CONCURRENTLY

```sql
-- Non blocca INSERT/UPDATE/DELETE. Non può girare dentro una transazione.
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders (customer_id);

-- Indice unique senza lock lungo
CREATE UNIQUE INDEX CONCURRENTLY uq_orders_ref ON orders (external_ref);
-- ...poi si "promuove" a vincolo, operazione metadata-only
ALTER TABLE orders ADD CONSTRAINT uq_orders_ref UNIQUE USING INDEX uq_orders_ref;
```

`CONCURRENTLY` fa due scansioni della tabella e **attende che terminino tutte le transazioni preesistenti** (anche su altre tabelle, per lo snapshot): una transazione lunga lo rallenta indefinitamente. Se fallisce (deadlock, violazione di unique, cancellazione) lascia un indice **`INVALID`** che continua a pesare sulle scritture ma non è usato dalle query.

```sql
-- Trova indici invalidi lasciati da CONCURRENTLY falliti
SELECT n.nspname, c.relname AS index_name, t.relname AS table_name
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
JOIN pg_class t ON t.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT i.indisvalid;

-- Bonifica e riprova
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_customer_id;
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders (customer_id);
```

Nei tool di migration va disabilitata la transazione implicita: in Flyway `executeInTransaction=false` (file `.conf` di script o header `-- flyway:executeInTransaction=false`); in golang-migrate usare una migration con una sola istruzione senza `BEGIN`; in Liquibase `runInTransaction="false"` sul changeSet.

### PostgreSQL: vincoli con NOT VALID

Aggiungere un FK o CHECK normale scansiona l'intera tabella tenendo un lock forte. La versione in due fasi sposta la scansione fuori dal lock esclusivo.

```sql
-- Fase 1: istantanea, il vincolo vale solo per le NUOVE scritture
SET lock_timeout = '3s';
ALTER TABLE order_items
  ADD CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders (id) NOT VALID;

-- Fase 2: scansione completa, ma con lock SHARE UPDATE EXCLUSIVE (non blocca DML)
ALTER TABLE order_items VALIDATE CONSTRAINT fk_items_order;
```

`SET NOT NULL` su una tabella grande richiede una scansione sotto `ACCESS EXCLUSIVE`. Da PostgreSQL 12 se esiste già un CHECK validato che implica il NOT NULL, la scansione viene saltata:

```sql
ALTER TABLE users ADD CONSTRAINT users_email_nn CHECK (email IS NOT NULL) NOT VALID;
ALTER TABLE users VALIDATE CONSTRAINT users_email_nn;     -- scansione senza blocco DML
ALTER TABLE users ALTER COLUMN email SET NOT NULL;        -- istantaneo (usa il CHECK validato)
ALTER TABLE users DROP CONSTRAINT users_email_nn;         -- pulizia
```

### PostgreSQL: ADD COLUMN, cambio tipo

```sql
-- PG11+: metadata-only anche con DEFAULT, se il default NON è volatile
ALTER TABLE users ADD COLUMN status text NOT NULL DEFAULT 'active';   -- istantaneo
ALTER TABLE users ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(); -- ok: now() è STABLE, valutato una volta

-- Default volatile → rewrite completo della tabella (lock esclusivo per tutta la durata)
ALTER TABLE users ADD COLUMN token uuid NOT NULL DEFAULT gen_random_uuid();   -- ATTENZIONE
-- Alternativa: aggiungi nullable senza default, poi backfill a batch, poi SET NOT NULL via CHECK.
```

Cambi di tipo: `varchar(50)` → `varchar(200)` (aumento di lunghezza) e `varchar` → `text` sono metadata-only; `int` → `bigint` **riscrive** la tabella e tutti gli indici. Per `int` → `bigint` su tabelle grandi si usa expand/contract (sotto).

### PostgreSQL: pg_repack e pgroll

```bash
# Ricostruisce tabella e indici online (bloat). Estensione da installare nel DB.
psql -c "CREATE EXTENSION pg_repack;" mydb
pg_repack --dbname=mydb --table=public.orders --jobs=2 --wait-timeout=60

# Solo gli indici
pg_repack --dbname=mydb --table=public.orders --only-indexes
```

```bash
# pgroll: migration expand/contract con due versioni di schema attive
pgroll init --postgres-url "$DATABASE_URL"
pgroll start migrations/0007_add_status.json --complete=false   # fase expand: vecchio+nuovo schema visibili
# ...deploy della nuova versione dell'app che usa lo schema public_0007_add_status...
pgroll complete        # contract: rimuove la vecchia versione
pgroll rollback        # alternativa: annulla se qualcosa non va prima di complete
```

### MySQL: ALGORITHM e LOCK espliciti

```sql
SET SESSION lock_wait_timeout = 5;   -- l'ALTER rinuncia se non ottiene il MDL entro 5s (default: 1 anno!)

-- Metadata-only (MySQL 8.0.12+; qualsiasi posizione dalla 8.0.29)
ALTER TABLE orders ADD COLUMN shipped_at DATETIME NULL, ALGORITHM=INSTANT;

-- Indice secondario online
ALTER TABLE orders ADD INDEX idx_customer (customer_id), ALGORITHM=INPLACE, LOCK=NONE;

-- Se non supportato → errore immediato (ER_ALTER_OPERATION_NOT_SUPPORTED_REASON), nessuna sorpresa
ALTER TABLE orders MODIFY COLUMN amount DECIMAL(14,4), ALGORITHM=INPLACE, LOCK=NONE;
```

Quando `INSTANT`/`INPLACE` non bastano (cambio tipo di colonna, cambio di charset, `DROP PRIMARY KEY`, molte altre operazioni su colonne): l'operazione è `COPY` e va fatta con un OSC esterno.

!!! note "Limiti di INSTANT"
    `INSTANT` non è usabile su tabelle `ROW_FORMAT=COMPRESSED`, tabelle con indici FULLTEXT o tabelle temporanee, e il numero di modifiche instant consecutive su una tabella è limitato (≈64 versioni di riga in 8.0.29+): oltre il limite serve un rebuild (`ALTER TABLE t ENGINE=InnoDB` o OSC) che azzeri il contatore.

### MySQL: gh-ost

```bash
# 1) Test su replica: esegue l'intera migrazione sulla replica e poi la scarta, senza toccare il primario
gh-ost \
  --host=replica1.db.internal --user=ghost --password="$GHOST_PW" \
  --database=shop --table=orders \
  --alter="ADD COLUMN shipped_at DATETIME NULL, ADD INDEX idx_shipped (shipped_at)" \
  --test-on-replica --switch-to-rbr \
  --chunk-size=1000 --max-lag-millis=1500 \
  --verbose --execute

# 2) Esecuzione reale: cut-over manuale tramite flag file
gh-ost \
  --host=replica1.db.internal --user=ghost --password="$GHOST_PW" \
  --database=shop --table=orders \
  --alter="ADD COLUMN shipped_at DATETIME NULL" \
  --chunk-size=1000 \
  --max-lag-millis=1500 --throttle-control-replicas="replica2.db.internal,replica3.db.internal" \
  --max-load=Threads_running=40 --critical-load=Threads_running=200 \
  --cut-over=default --cut-over-lock-timeout-seconds=3 \
  --postpone-cut-over-flag-file=/tmp/ghost.postpone.flag \
  --serve-socket-file=/tmp/gh-ost.shop.orders.sock \
  --initially-drop-ghost-table --initially-drop-old-table \
  --verbose --execute
```

Senza `--execute` gh-ost fa solo un dry-run (verifica prerequisiti e crea/droppa la ghost table). Con `--postpone-cut-over-flag-file`, la copia procede ma il **cut-over attende** finché il file esiste: lo si cancella quando si è pronti (in una finestra di basso traffico) e la migrazione si chiude.

```bash
# Monitoraggio e controllo a runtime via socket
echo status   | nc -U /tmp/gh-ost.shop.orders.sock    # progresso, ETA, lag
echo throttle | nc -U /tmp/gh-ost.shop.orders.sock    # pausa la copia
echo "no-throttle" | nc -U /tmp/gh-ost.shop.orders.sock
echo "chunk-size=500" | nc -U /tmp/gh-ost.shop.orders.sock   # cambio parametri a caldo

# Via al cut-over quando si è pronti
rm /tmp/ghost.postpone.flag
```

Per girare direttamente sul primario (senza replica con binlog ROW) servono `--allow-on-master` e `--assume-rbr`; è meno sicuro: il default raccomandato è leggere il binlog da una replica.

### MySQL: pt-online-schema-change

```bash
# Dry-run: verifica prerequisiti, crea e droppa la tabella _new, NON applica la modifica
pt-online-schema-change \
  --alter "ADD COLUMN shipped_at DATETIME NULL" \
  D=shop,t=orders,h=primary.db.internal,u=osc,p="$OSC_PW" \
  --dry-run

# Esecuzione reale con throttling
pt-online-schema-change \
  --alter "ADD COLUMN shipped_at DATETIME NULL" \
  D=shop,t=orders,h=primary.db.internal,u=osc,p="$OSC_PW" \
  --chunk-time=0.5 --max-lag=2 --check-interval=1 \
  --max-load="Threads_running=50" --critical-load="Threads_running=200" \
  --alter-foreign-keys-method=auto \
  --progress=time,30 \
  --execute
```

`--alter-foreign-keys-method` gestisce le tabelle *figlie* che hanno FK verso quella modificata: `rebuild_constraints` (consigliato dove possibile, ricrea i FK sulle figlie puntando alla nuova tabella), `drop_swap` (rischioso: la tabella non esiste per un istante), `auto` sceglie il più sicuro.

### Diagnostica dei lock

```sql
-- PostgreSQL: chi blocca chi
SELECT blocked.pid  AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.state AS blocking_state,
       now() - blocking.xact_start AS blocking_xact_age,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS b(pid) ON true
JOIN pg_stat_activity blocking ON blocking.pid = b.pid
WHERE blocked.wait_event_type = 'Lock';

-- Transazioni aperte da più tempo (candidate a bloccare un DDL)
SELECT pid, state, now() - xact_start AS age, left(query, 80) AS query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY xact_start LIMIT 10;

-- Progresso di CREATE INDEX CONCURRENTLY
SELECT phase, blocks_done, blocks_total, tuples_done, tuples_total
FROM pg_stat_progress_create_index;
```

```sql
-- MySQL 8.0: metadata lock detenuti/in attesa
SELECT object_schema, object_name, lock_type, lock_status, owner_thread_id
FROM performance_schema.metadata_locks
WHERE object_schema = 'shop' AND object_name = 'orders';

-- Chi blocca l'ALTER (vista sys)
SELECT waiting_pid, waiting_query, blocking_pid, blocking_query, wait_age
FROM sys.schema_table_lock_waits
WHERE object_name = 'orders';

-- Transazioni aperte da più tempo
SELECT trx_mysql_thread_id, trx_started, TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS age_s, trx_query
FROM information_schema.innodb_trx ORDER BY trx_started LIMIT 10;
```

### Expand/contract applicato al DDL: rinominare una colonna

Un `ALTER TABLE ... RENAME COLUMN` è metadata-only ma **rompe istantaneamente** tutti i client che usano il nome vecchio durante il rolling deploy. La procedura sicura richiede più release.

| Release | Schema | Codice applicativo |
|---|---|---|
| 1 — **Expand** | Aggiungi `full_name` (nullable). Trigger o dual-write che copia `name` → `full_name` | Scrive entrambe, legge `name` |
| 2 — **Backfill** | Backfill delle righe storiche a batch | Scrive entrambe, legge `name` |
| 3 — **Switch** | Verifica coerenza (`COUNT` dove differiscono = 0) | Legge `full_name`, scrive entrambe |
| 4 — **Contract** | `DROP COLUMN name` (dopo un periodo di sicurezza) | Usa solo `full_name` |

Ogni passo è reversibile fino al punto 4; il rollback del codice non incontra mai uno schema incompatibile.

```sql
-- Release 1: expand + sync (PostgreSQL)
ALTER TABLE users ADD COLUMN full_name text;
CREATE OR REPLACE FUNCTION users_sync_name() RETURNS trigger AS $$
BEGIN
  NEW.full_name := COALESCE(NEW.full_name, NEW.name);
  NEW.name      := COALESCE(NEW.name, NEW.full_name);
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_users_sync_name BEFORE INSERT OR UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION users_sync_name();
```

### Backfill a batch con throttling

Una singola `UPDATE users SET full_name = name` su 300 milioni di righe genera una transazione enorme: bloat, WAL/binlog massivo, replica lag, lock di riga prolungati. Si procede per range di PK con pause e controllo del lag.

```sql
-- PostgreSQL: un batch (da ripetere finché rowcount = 0). Commit per ogni batch.
WITH batch AS (
  SELECT id FROM users
  WHERE full_name IS NULL
  ORDER BY id
  LIMIT 5000
  FOR UPDATE SKIP LOCKED
)
UPDATE users u SET full_name = u.name
FROM batch WHERE u.id = batch.id;
```

```bash
#!/usr/bin/env bash
# backfill.sh — batch + pausa adattiva sul replica lag (PostgreSQL)
while :; do
  n=$(psql "$DATABASE_URL" -Atc "
    WITH b AS (SELECT id FROM users WHERE full_name IS NULL ORDER BY id LIMIT 5000 FOR UPDATE SKIP LOCKED),
         u AS (UPDATE users x SET full_name = x.name FROM b WHERE x.id = b.id RETURNING 1)
    SELECT count(*) FROM u;")
  [ "$n" -eq 0 ] && break
  lag=$(psql "$REPLICA_URL" -Atc "SELECT COALESCE(EXTRACT(EPOCH FROM now()-pg_last_xact_replay_timestamp()),0)::int;")
  [ "$lag" -gt 5 ] && sleep 10 || sleep 0.2
done
```

!!! tip "Rollback plan sempre scritto prima"
    Per ogni migration pesante definisci in anticipo: (1) cosa succede se interrompi a metà (gh-ost: `echo panic`/kill del processo lascia la ghost table da droppare; pt-osc: i trigger vanno rimossi; PG: indice INVALID da droppare); (2) il comando esatto di rollback; (3) il punto di non ritorno (tipicamente il `DROP COLUMN` finale o il cut-over). Il **cut-over di un OSC è effettivamente irreversibile** senza un secondo OSC inverso: tenere la tabella `_del`/`_old` finché non sei certo.

## Best Practices

- **Un DDL = una migration = una sola istruzione "pericolosa"**. Mescolare un `CREATE INDEX CONCURRENTLY` con altro DDL nella stessa migration impedisce di eseguirlo fuori transazione.
- **Timeout sempre**: `lock_timeout` (PG) / `lock_wait_timeout` (MySQL) nella sessione di migration, mai attesa infinita. Retry con backoff in CI o nello script.
- **Elimina le transazioni lunghe prima del DDL**: controlla `pg_stat_activity` / `information_schema.innodb_trx`; usa `idle_in_transaction_session_timeout` per le connessioni che "dimenticano" una transazione aperta.
- **Esplicita sempre `ALGORITHM`/`LOCK` in MySQL**: preferisci un errore immediato a un `COPY` silenzioso che blocca le scritture.
- **Testa su dati di produzione-like**: un OSC su tabella piccola non rivela i problemi di throttling, replica lag, spazio disco (la ghost table ≈ 100% della tabella + indici) e durata.
- **Spazio disco**: pianifica spazio libero ≥ dimensione tabella (+ indici) per gh-ost/pt-osc/pg_repack; il WAL/binlog generato può saturare il disco prima della fine.
- **Monitora replica lag e carico** durante la migrazione, con soglie di throttle (`--max-lag-millis`, `--max-load`) *e* soglie critiche di abort (`--critical-load`).
- **Cut-over in finestra di basso traffico** (flag file per gh-ost) e con `--cut-over-lock-timeout-seconds` breve: meglio riprovare che bloccare.
- **Mai rename/cambio tipo "in place" in un rolling deploy**: usa sempre expand/contract.
- **Backward compatibility del codice**: ogni release deve funzionare con lo schema *prima* e *dopo* la migration. Dettagli sul flusso di deploy in [Schema Migrations](schema-migrations.md).
- **Evita `ALTER TABLE` mentre gira un `VACUUM FREEZE`/anti-wraparound o una lunga analisi** su PostgreSQL: i lock si sovrappongono e allungano le code (vedi [MVCC e VACUUM](../postgresql/mvcc-vacuum.md)).

!!! warning "Foreign key e trigger incompatibili con gh-ost"
    gh-ost rifiuta tabelle con foreign key (come figlia o come padre) e tabelle con trigger. Per quelle tabelle usa pt-osc (con `--alter-foreign-keys-method`) oppure una strategia expand/contract applicativa. Verifica in anticipo con `SELECT * FROM information_schema.referential_constraints` e `information_schema.triggers`.

## Troubleshooting

### L'applicazione si blocca durante un ALTER "veloce"

**Sintomo**: picco di connessioni in attesa, timeout dell'applicazione; in PostgreSQL `wait_event_type = 'Lock'`, in MySQL stato `Waiting for table metadata lock` su decine di thread; l'ALTER stesso risulta fermo.
**Causa**: lock queue — una transazione lunga (spesso `idle in transaction`) tiene un lock compatibile con il traffico ma non con l'ALTER, che a sua volta blocca tutti.
**Soluzione**: individua e termina il bloccante (non l'ALTER, di solito).

```sql
-- PostgreSQL
SELECT pid, state, now()-xact_start AS age, left(query,60) FROM pg_stat_activity
WHERE xact_start IS NOT NULL ORDER BY xact_start LIMIT 5;
SELECT pg_terminate_backend(<pid_bloccante>);   -- oppure pg_cancel_backend per cancellare solo la query
```

```sql
-- MySQL
SELECT * FROM sys.schema_table_lock_waits WHERE object_name='orders'\G
KILL <blocking_pid>;
```

Poi riprova con `lock_timeout`/`lock_wait_timeout` brevi, così il prossimo tentativo non genera più la coda.

### gh-ost: il cut-over non avviene / resta in attesa

**Sintomo**: la copia è al 100% ma il log mostra `Waiting for postpone-cut-over-flag-file` oppure ripetuti `Cut-over failed` / `Lock wait timeout exceeded` / `cut-over lock timeout`.
**Causa**: (1) è presente il file `--postpone-cut-over-flag-file` (comportamento voluto); (2) transazioni lunghe sulla tabella impediscono a gh-ost di prendere il lock di cut-over entro `--cut-over-lock-timeout-seconds`.
**Soluzione**:

```bash
rm /tmp/ghost.postpone.flag                       # (1) dai il via al cut-over
# (2) trova transazioni lunghe e liberale
mysql -e "SELECT trx_mysql_thread_id, trx_started FROM information_schema.innodb_trx ORDER BY trx_started LIMIT 5;"
echo "unpostpone" | nc -U /tmp/gh-ost.shop.orders.sock   # equivalente a rimuovere il flag
```

gh-ost ritenta il cut-over automaticamente (`--default-retries`, 60 per default); aumenta il timeout solo se il traffico lo consente.

### Replica lag che esplode durante l'OSC / il backfill

**Sintomo**: `Seconds_Behind_Source` (MySQL) o `replay_lag` (PostgreSQL) in crescita costante, letture stantie dalle repliche, alert di lag.
**Causa**: chunk troppo grandi → transazioni grandi da riapplicare in modo seriale sulla replica (anche con replica parallela); `ALGORITHM=INPLACE` rebuild che genera binlog enorme.
**Soluzione**: riduci i chunk e attiva il throttling basato su lag.

```bash
echo "chunk-size=250" | nc -U /tmp/gh-ost.shop.orders.sock
echo "max-lag-millis=1000" | nc -U /tmp/gh-ost.shop.orders.sock
echo throttle | nc -U /tmp/gh-ost.shop.orders.sock   # pausa se necessario, riprendi con no-throttle
```

Per i backfill SQL riduci `LIMIT`, aumenta la pausa e usa il controllo lag del loop mostrato sopra. Per replica MySQL vedi [Architettura e replicazione MySQL](../mysql/architettura-replicazione.md).

### gh-ost / pt-osc rifiutano la tabella (foreign key, trigger, niente PK)

**Sintomo**: gh-ost esce con `FOREIGN KEY constraints are not supported` oppure `Triggers found on table`; `No shared unique key can be found after ALTER` quando l'alter rimuove la PK/unique key usata per la copia.
**Causa**: limiti architetturali di gh-ost (niente FK/trigger; serve una unique key condivisa tra tabella originale e ghost).
**Soluzione**: usa pt-osc con `--alter-foreign-keys-method=rebuild_constraints`, oppure expand/contract applicativo; assicura sempre una PK sulla tabella *prima* di avviare l'OSC (aggiungila con una migration separata). Non fare mai un `ALTER` che droppa l'unica unique key e ne crea una nuova nella stessa operazione.

### Indice INVALID dopo CREATE INDEX CONCURRENTLY fallito

**Sintomo**: `ERROR: deadlock detected` / `could not create unique index ... Key (...) is duplicated` durante `CREATE INDEX CONCURRENTLY`; in `\d tabella` l'indice compare con `INVALID`; le scritture sono rallentate ma l'indice non è usato dal planner.
**Causa**: il build concorrente è stato interrotto (cancel, timeout, duplicati per indice unique, deadlock). L'indice resta nel catalogo, mantenuto a ogni scrittura ma inutilizzabile.
**Soluzione**:

```sql
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
DROP INDEX CONCURRENTLY idx_orders_customer_id;
-- Per unique: risolvi prima i duplicati
SELECT external_ref, count(*) FROM orders GROUP BY 1 HAVING count(*) > 1;
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders (customer_id);
```

Per ricostruire un indice esistente usa `REINDEX INDEX CONCURRENTLY` (PG12+). Vedi anche [Indici](indici.md).

### ALTER ... ADD COLUMN DEFAULT riscrive la tabella in PostgreSQL

**Sintomo**: un `ADD COLUMN` che doveva essere istantaneo tiene `ACCESS EXCLUSIVE` per minuti, WAL in forte crescita.
**Causa**: il default è **volatile** (`gen_random_uuid()`, `random()`, `clock_timestamp()`) oppure la versione è < PG11: serve valutare il default riga per riga e riscrivere la tabella.
**Soluzione**: aggiungi la colonna nullable senza default, imposta il default solo per le nuove righe (`ALTER COLUMN ... SET DEFAULT`), esegui il backfill a batch e infine applica `NOT NULL` via CHECK `NOT VALID` + `VALIDATE`.

## Relazioni

??? info "Schema Migrations — i tool di versioning"
    Flyway, Liquibase, Atlas e golang-migrate decidono *quali* script applicare e in che ordine; non rendono il DDL non bloccante. Le tecniche di questa pagina si scrivono *dentro* le migration (con `lock_timeout`, `CONCURRENTLY`, `NOT VALID`).

    **Approfondimento completo →** [Schema Migrations](schema-migrations.md)

??? info "Indici — creazione e manutenzione"
    Struttura degli indici, `REINDEX CONCURRENTLY` e gestione di indici invalidi o gonfi.

    **Approfondimento completo →** [Indici](indici.md)

??? info "Transazioni e Concorrenza — lock e isolation"
    Il modello di lock che sta alla base della lock queue, deadlock e transazioni lunghe.

    **Approfondimento completo →** [Transazioni e Concorrenza](transazioni-concorrenza.md)

??? info "MVCC e VACUUM — bloat e pg_repack"
    Perché le tabelle PostgreSQL si gonfiano e quando serve riscriverle online.

    **Approfondimento completo →** [MVCC e VACUUM](../postgresql/mvcc-vacuum.md)

??? info "Replicazione MySQL — impatto del lag"
    Binlog ROW, replica parallela e lag: prerequisiti e vincoli di gh-ost.

    **Approfondimento completo →** [Architettura e replicazione MySQL](../mysql/architettura-replicazione.md)

??? info "Major Version Upgrade PostgreSQL"
    Le stesse tecniche expand/contract e lock-queue si applicano alle migration eseguite prima/dopo un upgrade di versione.

    **Approfondimento completo →** [Major Version Upgrade](../postgresql/major-version-upgrade.md)

## Riferimenti

- [PostgreSQL — ALTER TABLE (lock e rewrite)](https://www.postgresql.org/docs/current/sql-altertable.html)
- [PostgreSQL — Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL — CREATE INDEX CONCURRENTLY](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [MySQL 8.0 — Online DDL Operations](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html)
- [gh-ost — GitHub](https://github.com/github/gh-ost) (doc: `doc/` — command-line-flags, cheatsheet, requirements-and-limitations)
- [Percona Toolkit — pt-online-schema-change](https://docs.percona.com/percona-toolkit/pt-online-schema-change.html)
- [pg_repack](https://reorg.github.io/pg_repack/)
- [pgroll — Xata](https://github.com/xataio/pgroll)
- [Spirit — Block / Cash App](https://github.com/block/spirit)
- [Vitess — Online DDL](https://vitess.io/docs/user-guides/schema-changes/)
