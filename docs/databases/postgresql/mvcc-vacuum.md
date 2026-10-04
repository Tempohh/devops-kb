---
title: "MVCC e Vacuum"
slug: mvcc-vacuum
category: databases
tags: [postgresql, mvcc, vacuum, autovacuum, bloat, dead-tuples, xid-wraparound]
search_keywords: [mvcc multi version concurrency control, dead tuples, table bloat, index bloat, vacuum postgresql, autovacuum, vacuum full, vacuum analyze, xid wraparound, transaction id wraparound, freeze, visibility map, hint bits, pg_stat_user_tables, n_dead_tup, autovacuum_vacuum_scale_factor, autovacuum_vacuum_cost_delay, toast, fillfactor]
parent: databases/postgresql/_index
related: [databases/fondamentali/transazioni-concorrenza, databases/fondamentali/indici, databases/sql-avanzato/query-optimizer]
official_docs: https://www.postgresql.org/docs/current/mvcc.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# MVCC e Vacuum

## Come Funziona MVCC

Ogni riga in PostgreSQL non è un singolo record — è un **tuple** con metadati di visibilità:

```
Struttura fisica di una riga (HeapTuple):
  xmin    : transaction ID che ha creato questa versione
  xmax    : transaction ID che l'ha eliminata/aggiornata (0 = ancora valida)
  infomask: flag di stato (committata? abortita? frozen?)
  ctid    : puntatore fisico alla posizione corrente (heap page, offset)
  data    : colonne effettive
```

Quando esegui un `UPDATE`:
1. PostgreSQL **non modifica** la riga esistente
2. Scrive una **nuova versione** della riga con `xmin = tx_corrente`
3. Marca la vecchia versione con `xmax = tx_corrente`
4. La vecchia versione resta fisicamente presente — è una "dead tuple"

```sql
-- Visualizza le versioni (richiede estensione pageinspect)
CREATE EXTENSION pageinspect;

SELECT lp, t_xmin, t_xmax, t_infomask, t_data
FROM heap_page_items(get_raw_page('utenti', 0));
```

**Perché questo design**: reader non aspettano mai i writer (e viceversa). Una transazione che fa una lunga lettura vede un snapshot consistente dell'intera query, anche se nel frattempo altri stanno scrivendo — perché le versioni vecchie restano fisicamente disponibili finché non ci sono più transazioni che le vedono.

---

## Il Problema del Bloat

Le dead tuples si accumulano. Su una tabella con molti UPDATE/DELETE, la dimensione fisica cresce anche se il numero di righe vive rimane costante:

```sql
-- Diagnosi bloat
SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

Una tabella con 1M di righe vive e 500k dead tuples occupa il 50% in più del necessario, e le query sono più lente perché devono scansionare più pagine (alcune delle quali contengono solo dead tuples).

---

## VACUUM — Rimozione delle Dead Tuples

VACUUM recupera lo spazio delle dead tuples **senza di norma rilasciare spazio al OS** (lo spazio viene marcato riusabile per PostgreSQL; solo le pagine completamente vuote in coda al file possono essere troncate). Gli **indici** non si restringono: servono `REINDEX ... CONCURRENTLY` o `pg_repack`.

```sql
-- VACUUM base: rimuove dead tuples, aggiorna statistiche minime
VACUUM utenti;

-- VACUUM ANALYZE: rimuove dead tuples + aggiorna statistiche del planner
VACUUM ANALYZE utenti;

-- VACUUM FULL: riscrive l'intera tabella compattata — rilascia spazio al OS
-- ⚠ Richiede AccessExclusiveLock — blocca tutte le operazioni per tutta la durata
VACUUM FULL utenti;

-- VACUUM con verbosità
VACUUM (VERBOSE, ANALYZE) utenti;
```

!!! warning "VACUUM FULL è un'operazione pericolosa"
    `VACUUM FULL` riscrive l'intera tabella e richiede un lock esclusivo. Su tabelle grandi in produzione può bloccare le operazioni per minuti/ore (e richiede spazio disco pari alla tabella). Preferire `pg_repack` come alternativa quasi non-bloccante.

```bash
# pg_repack: compatta la tabella senza lock esclusivo prolungato
pg_repack -h localhost -U postgres -d mydb -t utenti
```

!!! note "Limiti di pg_repack"
    Richiede una **primary key o un indice UNIQUE NOT NULL** sulla tabella, spazio disco extra (copia della tabella + indici) e prende un `ACCESS EXCLUSIVE` lock breve all'inizio e alla fine. Sotto carico di scrittura elevato lo swap finale può fare fatica ad acquisire il lock.

---

## Autovacuum — La Manutenzione Automatica

Autovacuum è un daemon di background che esegue VACUUM automaticamente quando necessario. I trigger sono:

```
Trigger VACUUM:  n_dead_tup > autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor × n_live_tup
                 Default: 50 + 0.2 × n_live_tup (20% di dead tuples)

Trigger ANALYZE: n_mod_since_analyze > autovacuum_analyze_threshold + autovacuum_analyze_scale_factor × n_live_tup
                 Default: 50 + 0.1 × n_live_tup (10% di righe cambiate)

Trigger INSERT (PG13+): n_ins_since_vacuum > autovacuum_vacuum_insert_threshold (1000)
                 + autovacuum_vacuum_insert_scale_factor (0.2) × n_live_tup
                 → serve a tabelle append-only: aggiorna visibility map e freeze
```

!!! note "Novità PG17/PG18"
    **PG17**: la memoria per tracciare le dead tuples (TidStore) non ha più il limite di 1 GB di `maintenance_work_mem`/`autovacuum_work_mem`, quindi meno passate sugli indici. **PG18**: VACUUM può fare *eager freezing* di pagine all-visible (`vacuum_max_eager_freeze_failure_rate`) e c'è un tetto assoluto alla soglia (`autovacuum_vacuum_max_threshold`, default 100M dead tuples), che rende il default sensato anche per tabelle enormi.

### Tuning Autovacuum per Tabelle ad Alto Traffico

I valori di default sono pensati per tabelle di dimensione media. Tabelle grandi (>100M righe) con il 20% di dead tuples rappresentano 20M di dead tuples — autovacuum si triggera troppo tardi.

```sql
-- Tuning per-tabella (sovrascrive i parametri globali)
ALTER TABLE ordini SET (
    autovacuum_vacuum_scale_factor = 0.01,   -- 1% invece del 20%
    autovacuum_analyze_scale_factor = 0.005, -- 0.5% invece del 10%
    autovacuum_vacuum_cost_delay = 2,        -- ms di pausa tra pagine (ridurre = più aggressivo)
    autovacuum_vacuum_cost_limit = 400       -- budget I/O per ciclo (aumentare = più aggressivo)
);
```

```ini
# postgresql.conf — parametri globali
autovacuum_max_workers = 5         # Processi autovacuum paralleli (default 3)
autovacuum_vacuum_cost_delay = 2ms # Pausa quando il budget è esaurito (default 2ms da PG12, prima 20ms)
autovacuum_vacuum_cost_limit = -1  # -1 = usa vacuum_cost_limit (200). Budget TOTALE ripartito tra i worker attivi
autovacuum_naptime = 30s           # Intervallo check tra cicli (default 1min)
```

!!! warning "Il budget è condiviso"
    Il `cost_limit` globale è diviso tra tutti i worker attivi: aumentare `autovacuum_max_workers` **senza** alzare `cost_limit` rende ogni worker più lento. I parametri per-tabella (`ALTER TABLE ... SET`) escludono quella tabella dal bilanciamento.

### Monitorare Autovacuum

```sql
-- Autovacuum correntemente attivo
SELECT pid, state, wait_event, query, now() - xact_start AS duration
FROM pg_stat_activity
WHERE backend_type = 'autovacuum worker';

-- Progresso dettagliato dei VACUUM in corso
SELECT pid, relid::regclass, phase, heap_blks_total, heap_blks_scanned, heap_blks_vacuumed
FROM pg_stat_progress_vacuum;

-- Tabelle che autovacuum non riesce a tenere al passo
SELECT schemaname, relname, n_dead_tup, n_live_tup,
       last_autovacuum, last_autoanalyze,
       autovacuum_count, autoanalyze_count
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;
```

---

## Transaction ID Wraparound — L'Emergenza Silenziosa

PostgreSQL usa un transaction ID (xid) a 32 bit trattato come spazio **circolare**: per ogni transazione, ~2 miliardi di xid sono "nel passato" (visibili) e ~2 miliardi "nel futuro". Se una riga vecchia non viene "congelata" prima che l'età superi 2^31 (~2,1 miliardi), sembrerebbe improvvisamente nel futuro e sparirebbe. Per evitarlo PostgreSQL emette warning, poi rifiuta di assegnare nuovi xid (cioè nessuna scrittura) finché non si esegue VACUUM.

```sql
-- Distanza dal wraparound per ogni database
SELECT
    datname,
    age(datfrozenxid) AS xid_age,
    2147483647 - age(datfrozenxid) AS xids_rimanenti
FROM pg_database
ORDER BY xid_age DESC;
-- Warning a ~40M xid rimanenti: "WARNING: database "xxx" must be vacuumed within N transactions"
-- Stop a ~3M xid rimanenti: rifiuta nuovi xid, serve VACUUM (in single-user mode nelle versioni vecchie)

-- Tabelle più vicine al wraparound
SELECT n.nspname, c.relname, age(c.relfrozenxid) AS xid_age
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm', 't')
ORDER BY age(c.relfrozenxid) DESC
LIMIT 20;
```

**VACUUM FREEZE**: marca le righe con xid "vecchio" come "frozen" (visibili a tutte le transazioni future). Autovacuum lo avvia **anche se autovacuum è disabilitato** quando `age(relfrozenxid)` supera `autovacuum_freeze_max_age` (200M di default; richiede restart per essere cambiato).

```sql
-- Forzare il freeze di una tabella specifica
VACUUM FREEZE tabella;

-- Parametri di controllo freeze
-- vacuum_freeze_min_age:       età minima di una riga per essere congelata (default 50M)
-- vacuum_freeze_table_age:     età oltre cui VACUUM diventa "aggressivo" e scansiona anche pagine all-visible (default 150M)
-- autovacuum_freeze_max_age:   età oltre cui autovacuum parte comunque (default 200M)
-- vacuum_failsafe_age (PG14+): età oltre cui VACUUM salta cost delay e cleanup indici (default 1.6B)
```

Esiste un meccanismo analogo per i **MultiXact ID** (lock di riga condivisi): `autovacuum_multixact_freeze_max_age` (default 400M) e `age(datminmxid)`/`mxid_age(relminmxid)`.

---

## Visibility Map e Hint Bits

La **visibility map** è un file (per ogni tabella) che traccia quali pagine contengono solo tuple visibili a tutte le transazioni correnti (all-visible) e quali sono frozen. Viene usata da:
- **Index Only Scan**: può restituire dati senza accedere alla heap per pagine all-visible
- **VACUUM**: salta pagine all-visible (nessun cleanup necessario)

Gli **hint bits** sono flag sulla riga che indicano se la transazione che l'ha creata (xmin) è committata o abortita. La prima transazione che accede a una riga con stato non ancora noto deve consultare `pg_xact` (il commit log, ex `pg_clog`); dopo, imposta l'hint bit e le letture successive evitano la lookup. Per questo una prima `SELECT` dopo un grosso caricamento può scrivere pagine (dirty) — VACUUM le sistema in anticipo.

---

## TOAST — Storage per Valori Grandi

Una tupla non può attraversare pagine da 8kB. Quando una riga supera ~2kB (`TOAST_TUPLE_THRESHOLD`), i valori grandi (TEXT lungo, JSONB, bytea) vengono automaticamente compressi e/o spostati in una TOAST table (The Oversized-Attribute Storage Technique). Anche le TOAST table accumulano dead tuples e vengono vacuumate:

```sql
-- Visualizza le TOAST table
SELECT relname, reltoastrelid::regclass AS toast_table
FROM pg_class
WHERE reltoastrelid != 0 AND relname = 'log_eventi';

-- Strategie TOAST per colonna
ALTER TABLE log_eventi ALTER COLUMN payload SET STORAGE MAIN;     -- Comprime, ma evita lo storage out-of-line finché possibile
ALTER TABLE log_eventi ALTER COLUMN payload SET STORAGE EXTERNAL; -- Out-of-line senza compressione (substring più veloci su text/bytea)
ALTER TABLE log_eventi ALTER COLUMN payload SET STORAGE EXTENDED; -- Compressione + out-of-line (default)

-- PG14+: algoritmo di compressione per colonna (lz4 è più veloce di pglz di default)
ALTER TABLE log_eventi ALTER COLUMN payload SET COMPRESSION lz4;
```

**Impatto performance**: query che selezionano colonne TOAST richiedono decompressione/fetch extra. Evitare `SELECT *` su tabelle con colonne TOAST se non necessarie.

---

## Fill Factor — Spazio per gli Update

Il `fillfactor` determina quanto spazio viene lasciato libero in ogni pagina per gli UPDATE futuri. Default: 100% (nessuno spazio libero). Con fillfactor < 100, la nuova versione della riga può essere scritta nella **stessa pagina** della vecchia (HOT update — Heap Only Tuple), senza toccare gli indici; la catena HOT viene poi potata (pruning) anche senza VACUUM completo:

```sql
-- Tabella con molti UPDATE: lascia 20% spazio libero per HOT updates
ALTER TABLE sessioni SET (fillfactor = 80);
-- → dopo un VACUUM FULL, ogni pagina sarà riempita all'80%
-- → gli UPDATE che modificano colonne non-indexed trovano spazio sulla stessa pagina
```

HOT updates evitano l'aggiornamento degli indici (sono molto più economici dei normali updates). Si verificano quando: nessuna colonna indicizzata viene modificata (da PG16 fanno eccezione gli indici *summarizing* come BRIN), e c'è spazio libero nella stessa pagina. Indicizzare colonne aggiornate di frequente li impedisce.

```sql
-- Verifica HOT updates vs updates normali
SELECT n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / nullif(n_tup_upd, 0), 1) AS hot_pct
FROM pg_stat_user_tables
WHERE relname = 'sessioni';
-- hot_pct > 50% è buono
```

## Troubleshooting

### Scenario 1 — Tabella continua a crescere nonostante VACUUM

**Sintomo:** `pg_total_relation_size()` non diminuisce dopo `VACUUM`; `n_dead_tup` resta alto.

**Causa:** Una transazione idle-in-transaction/lunga, una prepared transaction dimenticata, una replica con `hot_standby_feedback` o uno slot di replica mantengono un `xmin` vecchio (l'"orizzonte"). VACUUM non può rimuovere dead tuples ancora potenzialmente visibili a quell'orizzonte.

**Soluzione:** Identificare e terminare chi tiene l'orizzonte.

```sql
-- Trovare le transazioni con l'orizzonte xmin più vecchio
SELECT pid, usename, state, xact_start, now() - xact_start AS duration,
       age(backend_xmin) AS xmin_age, query
FROM pg_stat_activity
WHERE backend_xmin IS NOT NULL
ORDER BY age(backend_xmin) DESC
LIMIT 10;

-- Terminare la transazione bloccante (prima pg_cancel_backend)
SELECT pg_cancel_backend(pid);   -- Soft: cancella la query
SELECT pg_terminate_backend(pid); -- Hard: disconnette la sessione

-- Prepared transactions dimenticate (2PC)
SELECT gid, prepared, owner FROM pg_prepared_xacts ORDER BY prepared;
-- ROLLBACK PREPARED 'gid';

-- Replication slot che tengono indietro l'orizzonte
SELECT slot_name, active, xmin, catalog_xmin,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes
FROM pg_replication_slots;
-- Uno slot inattivo trattiene xmin/catalog_xmin (blocca VACUUM) e WAL (riempie il disco)
-- Se non necessario: SELECT pg_drop_replication_slot('nome_slot');
```

Prevenzione: impostare `idle_in_transaction_session_timeout` (es. `5min`) e, da PG13, `max_slot_wal_keep_size` per limitare il WAL trattenuto dagli slot.

---

### Scenario 2 — Autovacuum non si attiva o è troppo lento

**Sintomo:** `n_dead_tup` cresce oltre la soglia ma `last_autovacuum` non si aggiorna; oppure autovacuum è attivo ma non tiene il passo.

**Causa 1:** Autovacuum è throttled dal cost delay/limit (budget I/O troppo basso). **Causa 2:** Soglie di scala troppo alte per tabelle grandi. **Causa 3:** Autovacuum viene cancellato da lock conflittuali (es. `ALTER TABLE`/`LOCK` frequenti) o un orizzonte xmin vecchio gli impedisce di rimuovere tuple (vedi Scenario 1).

**Soluzione:** Ridurre lo scale factor e aumentare il budget I/O per la tabella specifica.

```sql
-- Verificare stato autovacuum
SELECT schemaname, relname, n_dead_tup, n_live_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
       last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;

-- Tuning aggressivo per tabelle grandi
ALTER TABLE ordini SET (
    autovacuum_vacuum_scale_factor = 0.01,  -- 1% invece del 20%
    autovacuum_vacuum_cost_delay = 0,       -- Nessuna pausa I/O (solo se lo puoi permettere)
    autovacuum_vacuum_cost_limit = 800      -- Budget I/O 4x rispetto al default (200)
);

-- Forzare VACUUM manuale se autovacuum non basta
VACUUM (ANALYZE, VERBOSE) ordini;
```

---

### Scenario 3 — Warning "database must be vacuumed" / rischio XID wraparound

**Sintomo:** Nei log PostgreSQL appare `WARNING: database "mydb" must be vacuumed within N transactions`. In casi estremi, il database entra in modalità read-only.

**Causa:** L'`age(datfrozenxid)` di un database o tabella si avvicina a ~2,1 miliardi. Il freeze non avanza: tipicamente per le stesse cause dello Scenario 1 (orizzonte xmin bloccato da transazioni/slot/prepared xact), o autovacuum troppo lento su tabelle enormi.

**Soluzione:** Rimuovere ciò che blocca l'orizzonte (Scenario 1), poi eseguire `VACUUM FREEZE` urgente sulle tabelle più vecchie.

```sql
-- Diagnosi immediata: distanza dal wraparound
SELECT datname,
       age(datfrozenxid) AS xid_age,
       2147483647 - age(datfrozenxid) AS xids_rimanenti
FROM pg_database
ORDER BY xid_age DESC;

-- Tabelle più critiche
SELECT n.nspname, c.relname, age(c.relfrozenxid) AS xid_age
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm', 't')
ORDER BY age(c.relfrozenxid) DESC
LIMIT 10;

-- Freeze urgente sulle tabelle critiche (la più vecchia per prima)
VACUUM (FREEZE, VERBOSE) tabella_critica;
```

Correzione strutturale: rendere autovacuum più aggressivo sulle tabelle grandi (per-tabella `autovacuum_freeze_max_age`, `autovacuum_vacuum_cost_limit`) e monitorare `age(datfrozenxid)` con alert (es. > 1 miliardo). Abbassare `autovacuum_freeze_max_age` globale fa partire i freeze prima ma richiede restart e genera più I/O.

---

### Scenario 4 — Bloat massivo e impossibilità di recuperare spazio

**Sintomo:** `pg_total_relation_size()` è molto più grande del previsto; VACUUM libera le dead tuples ma non riduce la dimensione su disco.

**Causa:** VACUUM standard non compatta le pagine né rilascia spazio al filesystem. Le pagine liberate restano riutilizzabili da PostgreSQL ma non vengono restituite all'OS.

**Soluzione:** Usare `pg_repack` (lock solo brevi) invece di `VACUUM FULL` (bloccante); per soli indici bloated `REINDEX INDEX CONCURRENTLY` (PG12+).

```bash
# Installare pg_repack (richiede accesso superuser)
# Su Debian/Ubuntu: apt install postgresql-xx-repack
# Verificare estensione installata nel db
psql -c "CREATE EXTENSION IF NOT EXISTS pg_repack;"

# Stimare bloat prima dell'operazione
psql -c "
SELECT relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_relation_size(relid)) AS table_only
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;"
# Per una stima reale del bloat: estensione pgstattuple (pgstattuple_approx) o query check_postgres

# Repack senza lock esclusivo prolungato
pg_repack -h localhost -U postgres -d mydb -t tabella_bloated

# Repack di un intero schema (attenzione: lungo su DB grandi, serve spazio disco extra)
pg_repack -h localhost -U postgres -d mydb -s public
```

---

## Relazioni

??? info "Indici — Index bloat e REINDEX"
    Il bloat colpisce anche gli indici — come diagnosticarlo e risolverlo.

    **Approfondimento →** [Indici](../fondamentali/indici.md)

??? info "Transazioni e Concorrenza — MVCC dal punto di vista applicativo"
    Come MVCC si manifesta nei livelli di isolamento.

    **Approfondimento →** [Transazioni e Concorrenza](../fondamentali/transazioni-concorrenza.md)

## Riferimenti

- [PostgreSQL MVCC Documentation](https://www.postgresql.org/docs/current/mvcc.html)
- [PostgreSQL Autovacuum Tuning](https://www.enterprisedb.com/blog/autovacuum-tuning-basics)
- [pg_repack](https://github.com/reorg/pg_repack)
