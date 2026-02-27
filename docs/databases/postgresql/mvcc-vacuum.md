---
title: "MVCC e Vacuum"
slug: mvcc-vacuum
category: databases
tags: [postgresql, mvcc, vacuum, autovacuum, bloat, dead-tuples, xid-wraparound]
search_keywords: [mvcc multi version concurrency control, dead tuples, table bloat, index bloat, vacuum postgresql, autovacuum, vacuum full, vacuum analyze, xid wraparound, transaction id wraparound, freeze, visibility map, hint bits, pg_stat_user_tables, n_dead_tup, autovacuum_vacuum_scale_factor, autovacuum_vacuum_cost_delay, toast, fillfactor]
parent: databases/postgresql/_index
related: [databases/fondamentali/transazioni-concorrenza, databases/fondamentali/indici, databases/sql-avanzato/query-optimizer]
official_docs: https://www.postgresql.org/docs/current/mvcc.html
status: complete
difficulty: advanced
last_updated: 2026-02-24
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
    tablename,
    n_live_tup,
    n_dead_tup,
    round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

Una tabella con 1M di righe vive e 500k dead tuples occupa il 50% in più del necessario, e le query sono più lente perché devono scansionare più pagine (alcune delle quali contengono solo dead tuples).

---

## VACUUM — Rimozione delle Dead Tuples

VACUUM recupera lo spazio delle dead tuples **senza rilasciare spazio al OS** (lo spazio viene marcato riusabile per PostgreSQL):

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
    `VACUUM FULL` riscrive l'intera tabella e richiede un lock esclusivo. Su tabelle grandi in produzione può bloccare le operazioni per minuti/ore. Preferire `pg_repack` come alternativa non-bloccante.

```bash
# pg_repack: compatta la tabella senza lock esclusivo
pg_repack -h localhost -U postgres -d mydb -t utenti
```

---

## Autovacuum — La Manutenzione Automatica

Autovacuum è un daemon di background che esegue VACUUM automaticamente quando necessario. I trigger sono:

```
Trigger VACUUM:  n_dead_tup > autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor × n_live_tup
                 Default: 50 + 0.2 × n_live_tup (20% di dead tuples)

Trigger ANALYZE: n_changed   > autovacuum_analyze_threshold + autovacuum_analyze_scale_factor × n_live_tup
                 Default: 50 + 0.1 × n_live_tup (10% di righe cambiate)
```

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
autovacuum_vacuum_cost_delay = 2ms # Rallenta autovacuum per ridurre impatto I/O
autovacuum_vacuum_cost_limit = 200 # Budget I/O per worker
autovacuum_naptime = 30s           # Intervallo check tra cicli
```

### Monitorare Autovacuum

```sql
-- Autovacuum correntemente attivo
SELECT pid, state, wait_event, query, now() - xact_start AS duration
FROM pg_stat_activity
WHERE query LIKE 'autovacuum%';

-- Tabelle che autovacuum non riesce a tenere al passo
SELECT schemaname, tablename, n_dead_tup, n_live_tup,
       last_autovacuum, last_autoanalyze,
       autovacuum_count, autoanalyze_count
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;
```

---

## Transaction ID Wraparound — L'Emergenza Silenziosa

PostgreSQL usa un transaction ID (xid) a 32 bit — può rappresentare ~4 miliardi di transazioni. Quando si avvicina all'esaurimento, PostgreSQL emette warning, poi inizia a rifiutare tutte le scritture per proteggere la consistenza dei dati.

```sql
-- Distanza dal wraparound per ogni database
SELECT
    datname,
    age(datfrozenxid) AS xid_age,
    2000000000 - age(datfrozenxid) AS xids_rimanenti
FROM pg_database
ORDER BY xid_age DESC;
-- Warning a ~40M: "WARNING: database xxx must be vacuumed within N transactions"
-- Emergenza a ~2M: PostgreSQL si avvia in modalità read-only

-- Tabelle più vicine al wraparound
SELECT schemaname, tablename, age(relfrozenxid) AS xid_age
FROM pg_class JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
WHERE relkind = 'r'
ORDER BY age(relfrozenxid) DESC
LIMIT 20;
```

**VACUUM FREEZE**: aggiorna le righe con xid "vecchio" marcandole come "frozen" (visibili a tutte le transazioni future). Viene eseguito automaticamente quando l'xid si avvicina alla soglia `vacuum_freeze_max_age` (200M transazioni di default).

```sql
-- Forzare il freeze di una tabella specifica
VACUUM FREEZE tabella;

-- Parametri di controllo freeze
-- vacuum_freeze_min_age: età minima per freeze (default 50M)
-- vacuum_freeze_max_age: età massima prima del freeze forzato (default 200M)
```

---

## Visibility Map e Hint Bits

La **visibility map** è un file (per ogni tabella) che traccia quali pagine contengono solo tuple visibili a tutte le transazioni correnti (all-visible) e quali sono frozen. Viene usata da:
- **Index Only Scan**: può restituire dati senza accedere alla heap per pagine all-visible
- **VACUUM**: salta pagine all-visible (nessun cleanup necessario)

Gli **hint bits** sono flag sulla riga che indicano se la transazione che l'ha creata (xmin) è committata o abortita. La prima transazione che accede a una riga con xmin/xmax uncommitted deve controllare il clog (commit log) — questo è l'unico momento in cui un reader tocca il clog. Dopo, il hint bit viene settato e le successive letture sono free.

---

## TOAST — Storage per Valori Grandi

PostgreSQL ha un limite di 8kB per pagina. Valori grandi (TEXT lungo, JSONB, bytea) vengono automaticamente compressi e/o spostati in una TOAST table (The Oversized-Attribute Storage Technique):

```sql
-- Visualizza le TOAST table
SELECT relname, reltoastrelid::regclass AS toast_table
FROM pg_class
WHERE reltoastrelid != 0 AND relname = 'log_eventi';

-- Strategie TOAST per colonna
ALTER TABLE log_eventi ALTER COLUMN payload SET STORAGE MAIN;     -- Comprimi ma non detoast
ALTER TABLE log_eventi ALTER COLUMN payload SET STORAGE EXTERNAL; -- Non comprimere
ALTER TABLE log_eventi ALTER COLUMN payload SET STORAGE EXTENDED; -- Comprimi + detoast (default)
```

**Impatto performance**: query che selezionano colonne TOAST richiedono decompressione/fetch extra. Evitare `SELECT *` su tabelle con colonne TOAST se non necessarie.

---

## Fill Factor — Spazio per gli Update

Il `fillfactor` determina quanto spazio viene lasciato libero in ogni pagina per gli UPDATE futuri. Default: 100% (nessuno spazio libero). Con fillfactor < 100, gli UPDATE possono avvenire "in-place" sulla stessa pagina (HOT update — Heap Only Tuple) senza creare dead tuples su pagine diverse:

```sql
-- Tabella con molti UPDATE: lascia 20% spazio libero per HOT updates
ALTER TABLE sessioni SET (fillfactor = 80);
-- → dopo un VACUUM FULL, ogni pagina sarà riempita all'80%
-- → gli UPDATE che modificano colonne non-indexed trovano spazio sulla stessa pagina
```

HOT updates evitano l'aggiornamento degli indici (sono molto più economici dei normali updates). Si verificano quando: la colonna aggiornata non è indicizzata, e c'è spazio libero nella stessa pagina.

```sql
-- Verifica HOT updates vs updates normali
SELECT n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / nullif(n_tup_upd, 0), 1) AS hot_pct
FROM pg_stat_user_tables
WHERE tablename = 'sessioni';
-- hot_pct > 50% è buono
```

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
