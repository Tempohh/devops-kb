---
title: "Query Optimizer e EXPLAIN"
slug: query-optimizer
category: databases
tags: [query-optimizer, explain, performance, planner, indici, postgresql]
search_keywords: [explain analyze, query plan, seq scan, index scan, index only scan, bitmap index scan, hash join, nested loop join, merge join, cost model, startup cost, total cost, actual rows, estimated rows, buffers, hit ratio, work_mem, enable_seqscan, pg_stat_statements, auto explain, slow query log, statistics target, correlation, n_distinct, planner hints]
parent: databases/sql-avanzato/_index
related: [databases/fondamentali/indici, databases/postgresql/mvcc-vacuum, databases/sql-avanzato/window-functions]
official_docs: https://www.postgresql.org/docs/current/using-explain.html
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Query Optimizer e EXPLAIN

## Panoramica

Il query optimizer trasforma una dichiarazione SQL in un piano fisico di esecuzione. Non esegue la query che hai scritto — esegue il piano che stima essere il più economico, basandosi su statistiche delle tabelle e modelli di costo. Quando le query sono lente, quasi sempre il problema è un piano subottimale: un seq scan invece di un index scan, un nested loop invece di un hash join, stime di cardinalità errate.

## Lettura di EXPLAIN ANALYZE

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.nome, COUNT(o.id) AS n_ordini
FROM utenti u
LEFT JOIN ordini o ON o.utente_id = u.id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.nome
ORDER BY n_ordini DESC
LIMIT 10;
```

Output annotato:
```
Limit  (cost=1240.50..1240.53 rows=10 width=40)
       (actual time=45.123..45.127 rows=10 loops=1)
  ->  Sort  (cost=1240.50..1253.00 rows=5000 width=40)
            (actual time=45.120..45.122 rows=10 loops=1)
        Sort Key: (count(o.id)) DESC
        Sort Method: top-N heapsort  Memory: 25kB
        ->  HashAggregate  (cost=987.50..1037.50 rows=5000 width=40)
                           (actual time=43.200..44.800 rows=4987 loops=1)
              Group Key: u.id
              Batches: 1  Memory Usage: 897kB
              ->  Hash Left Join  (cost=310.00..912.50 rows=15000 width=16)
                                  (actual time=8.500..38.200 rows=15000 loops=1)
                    Hash Cond: (o.utente_id = u.id)
                    ->  Seq Scan on ordini o  (cost=0.00..450.00 rows=30000 width=8)
                                              (actual time=0.100..15.000 rows=30000 loops=1)
                    ->  Hash  (cost=275.00..275.00 rows=2800 width=16)
                              (actual time=8.300..8.300 rows=2800 loops=1)
                          ->  Index Scan using idx_utenti_data on utenti u
                                (cost=0.29..275.00 rows=2800 width=16)
                                (actual time=0.050..7.500 rows=2800 loops=1)
                                Index Cond: (created_at > '2024-01-01')
Planning Time: 1.2 ms
Execution Time: 45.5 ms
```

### Anatomia di un nodo del piano

```
Tipo Nodo  (cost=startup..total rows=stima width=dimensione_riga)
           (actual time=startup..total rows=reali loops=esecuzioni)
```

| Campo | Significato |
|-------|-------------|
| `cost=startup..total` | Costo stimato in unità arbitrarie (default: 1 = sequential page read) |
| `rows=N` | Numero righe stimato (planner) |
| `width=N` | Dimensione media riga in byte |
| `actual time=X..Y` | Tempo reale (ms): startup..completamento |
| `actual rows=N` | Righe realmente prodotte |
| `loops=N` | Quante volte il nodo è stato eseguito |

**Il segnale di allarme principale**: grande discrepanza tra `rows=stima` e `actual rows=reali`. Significa che le statistiche sono outdated o che la distribuzione dei dati è non uniforme.

---

## Tipi di Scan

### Sequential Scan

Legge l'intera tabella pagina per pagina. Non è sempre un problema — su tabelle piccole o quando si leggono >20-30% delle righe, è più efficiente di un index scan.

```
Seq Scan on ordini  (cost=0.00..450.00 rows=30000 width=8)
                    (actual time=0.100..15.000 rows=30000 loops=1)
  Filter: (status = 'shipped')
  Rows Removed by Filter: 5000
```

`Rows Removed by Filter: 5000` indica che il planner ha scansionato 35000 righe per trovarne 30000 — l'indice potrebbe aiutare se la selectivity fosse migliore.

### Index Scan

Attraversa l'indice B-tree e poi accede alle pagine heap per ogni riga trovata. Ideale quando si recuperano poche righe con alta selectivity.

### Index Only Scan

Come Index Scan ma non accede alle pagine heap — tutte le colonne necessarie sono nell'indice (covering index). Molto più veloce quando la visibility map è aggiornata (post-VACUUM).

### Bitmap Index Scan

Usato quando l'indice produce molte righe. Il planner prima costruisce una bitmap di quali pagine contengono righe che soddisfano la condizione, poi legge quelle pagine una sola volta (invece di accedere alla stessa pagina più volte).

```
Bitmap Heap Scan on ordini  (cost=...)
  Recheck Cond: (status = 'pending')
  ->  Bitmap Index Scan on idx_ordini_status
        Index Cond: (status = 'pending')
```

---

## Tipi di Join

### Nested Loop

Per ogni riga del lato "outer", cerca nel lato "inner". O(N×M) nel caso peggiore. Efficiente quando il lato outer è piccolo e il lato inner ha un indice.

```
Nested Loop  (cost=0.42..1500.00 rows=1000 width=32)
  ->  Index Scan on utenti (outer — 100 righe)
  ->  Index Scan on ordini using idx_ordini_utente (inner — indice)
        Index Cond: (utente_id = utenti.id)
```

### Hash Join

Costruisce una hash table dal lato minore, poi scansiona il lato maggiore usando la hash per trovare corrispondenze. O(N+M). Ideale quando entrambi i lati sono grandi e non c'è indice utile.

```
Hash Join  (cost=310.00..912.50 rows=15000 width=16)
  Hash Cond: (o.utente_id = u.id)
  ->  Seq Scan on ordini o       ← probing table (lato grande)
  ->  Hash                        ← build side (lato piccolo)
        ->  Seq Scan on utenti u
```

`work_mem` determina quanto memoria può usare l'hash table. Se non basta, usa disk (batches > 1 nell'output = spill to disk).

### Merge Join

Richiede entrambi i lati ordinati sulla join key. Efficiente quando i dati sono già ordinati (es. da un indice).

---

## Stime Errate — La Causa più Comune di Piani Subottimali

### Statistiche Obsolete

```sql
-- Verifica ultima analisi di una tabella
SELECT schemaname, tablename, last_analyze, last_autoanalyze, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;

-- Forza aggiornamento statistiche
ANALYZE ordini;
ANALYZE;  -- Tutte le tabelle

-- Aumenta la granularità delle statistiche per colonne con distribuzione non uniforme
ALTER TABLE ordini ALTER COLUMN status SET STATISTICS 500;  -- Default 100
ANALYZE ordini;
```

### Cardinalità Errata con Correlazioni

```sql
-- Il planner non capisce le correlazioni tra colonne di default
-- "WHERE citta = 'Milano' AND nazione = 'Italia'" → stima indipendente
-- ma praticamente tutti i milanesi hanno nazione=Italia

-- PostgreSQL 14+: statistiche multicolonna
CREATE STATISTICS stat_citta_nazione ON citta, nazione FROM indirizzi;
ANALYZE indirizzi;

-- Verifica le extended statistics
SELECT stxname, stxkind FROM pg_statistic_ext;
```

---

## Buffers — Cache Hit Ratio

L'opzione `BUFFERS` in EXPLAIN ANALYZE mostra gli accessi alla cache:

```
Seq Scan on ordini  (actual time=0.1..150.0 rows=30000)
  Buffers: shared hit=2000 read=800
```

- `shared hit=2000`: 2000 pagine trovate in shared_buffers (cache PostgreSQL) — veloce
- `read=800`: 800 pagine lette dal disco (o OS cache) — lento

**Cache hit ratio** = hit / (hit + read) → valore target: >95%

```sql
-- Hit ratio globale
SELECT
    sum(blks_hit)::float / nullif(sum(blks_hit) + sum(blks_read), 0) AS cache_ratio
FROM pg_stat_database;
```

---

## Strumenti di Diagnosi

### pg_stat_statements

```sql
-- Abilita estensione
CREATE EXTENSION pg_stat_statements;

-- Query più lente (per total_exec_time)
SELECT
    round(total_exec_time::numeric, 2) AS total_ms,
    calls,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(stddev_exec_time::numeric, 2) AS stddev_ms,
    rows,
    left(query, 100) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Query con stima righe peggiore
SELECT
    query,
    calls,
    rows / calls AS avg_rows,
    -- rows_examined / rows_returned è un proxy del costo
FROM pg_stat_statements
ORDER BY calls DESC;
```

### auto_explain

Logga automaticamente i piani delle query lente:

```sql
-- In postgresql.conf o ALTER SYSTEM:
shared_preload_libraries = 'auto_explain'
auto_explain.log_min_duration = '1s'    -- Log query > 1 secondo
auto_explain.log_analyze = true
auto_explain.log_buffers = true
auto_explain.log_nested_statements = true
```

---

## Interventi Correttivi

### 1. Aggiornare le Statistiche

```sql
ANALYZE tabella;
ALTER TABLE tabella ALTER COLUMN col SET STATISTICS 500;
```

### 2. Forzare un Piano (Temporaneo/Debug)

```sql
-- Disabilita seq scan per testare se un indice migliora le cose
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT ...;
SET enable_seqscan = on;  -- Reimpostare sempre!

-- Aumenta work_mem per join/sort che fanno spill a disco
SET work_mem = '256MB';  -- Solo per questa sessione
EXPLAIN ANALYZE SELECT ...;
```

### 3. Indice Mancante

```sql
-- EXPLAIN mostra un Seq Scan su una tabella grande con filtro selettivo
-- → creare l'indice appropriato (vedi sezione Indici)
CREATE INDEX CONCURRENTLY idx_ordini_status_data ON ordini(status, created_at DESC);
```

### 4. Aumentare work_mem

Se `EXPLAIN ANALYZE` mostra `Batches: N` (N > 1) in un hash join o `Sort Method: external merge Disk`, aumentare `work_mem`:

```sql
-- In postgresql.conf
work_mem = '64MB'  -- Default 4MB — spesso troppo basso

-- Per sessioni specifiche (es. report pesanti)
SET work_mem = '512MB';
```

## Troubleshooting

### Scenario 1 — Seq Scan su tabella grande nonostante indice esistente

**Sintomo:** `EXPLAIN` mostra `Seq Scan` su una tabella con milioni di righe anche se esiste un indice sulla colonna filtrata. Query lenta (>1s).

**Causa:** Le statistiche sono obsolete e il planner sottostima la selectivity del filtro, oppure la query recupera una frazione troppo alta delle righe (>20-30%) rendendo il seq scan genuinamente preferibile, oppure il `random_page_cost` è troppo alto rispetto ai costi reali (SSD vs HDD).

**Soluzione:**
```sql
-- 1. Aggiorna le statistiche
ANALYZE nome_tabella;

-- 2. Verifica se le statistiche sono davvero aggiornate
SELECT last_analyze, last_autoanalyze, n_live_tup
FROM pg_stat_user_tables
WHERE tablename = 'nome_tabella';

-- 3. Se usi SSD, abbassa random_page_cost
SET random_page_cost = 1.1;  -- Default 4.0, troppo alto per SSD
EXPLAIN ANALYZE SELECT ...;

-- 4. Forza test con indice (solo debug)
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT ...;
SET enable_seqscan = on;
```

---

### Scenario 2 — Stima righe molto errata (rows stima vs actual rows)

**Sintomo:** Nel piano EXPLAIN ANALYZE, il campo `rows=` stimato differisce di 10x o più rispetto ad `actual rows=`. Il piano risultante usa join o scan inefficienti.

**Causa:** Le statistiche non catturano la distribuzione reale dei dati (colonna con valori molto skewed), correlazioni tra colonne non modellate, o `statistics target` troppo basso.

**Soluzione:**
```sql
-- 1. Aumenta la granularità delle statistiche sulla colonna problematica
ALTER TABLE ordini ALTER COLUMN status SET STATISTICS 500;
ANALYZE ordini;

-- 2. Per correlazioni tra più colonne (PostgreSQL 14+)
CREATE STATISTICS stat_col1_col2 ON col1, col2 FROM tabella;
ANALYZE tabella;

-- 3. Verifica le statistiche attuali sulla colonna
SELECT attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'ordini' AND attname = 'status';

-- 4. Verifica extended statistics create
SELECT stxname, stxkind, stxkeys FROM pg_statistic_ext;
```

---

### Scenario 3 — Hash Join con spill a disco (Batches > 1)

**Sintomo:** `EXPLAIN ANALYZE` mostra `Batches: N` con N > 1 in un nodo Hash Join, oppure `Sort Method: external merge Disk`. Query usa molto I/O e risulta lenta.

**Causa:** `work_mem` insufficiente per contenere la hash table o il sort in memoria. Il planner crea file temporanei su disco.

**Soluzione:**
```sql
-- 1. Conferma il problema
EXPLAIN (ANALYZE, BUFFERS)
SELECT ... FROM a JOIN b ON ...;
-- Cerca: Batches: N (N > 1) oppure "external merge Disk"

-- 2. Aumenta work_mem per la sessione e ri-esegui
SET work_mem = '256MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT ... FROM a JOIN b ON ...;
-- Verifica che Batches torni a 1

-- 3. Se risolve, valuta aumento permanente in postgresql.conf
-- work_mem = '64MB'  -- Il default 4MB è spesso troppo basso
-- ATTENZIONE: work_mem si moltiplica per numero sessioni × nodi nel piano

-- 4. Alternativa: partition pruning o riscrivere la query
-- per ridurre il dataset prima del join
```

---

### Scenario 4 — Query lenta non identificabile senza EXPLAIN

**Sintomo:** L'applicazione segnala query lente ma non è chiaro quale. Non c'è accesso diretto ai log.

**Causa:** Mancanza di visibilità sulle query eseguite e sui loro piani.

**Soluzione:**
```sql
-- 1. Abilita pg_stat_statements se non attivo
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
-- Aggiungi shared_preload_libraries = 'pg_stat_statements' in postgresql.conf e riavvia

-- 2. Trova le query con maggior tempo totale
SELECT
    round(total_exec_time::numeric, 2) AS total_ms,
    calls,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    left(query, 120) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 3. Configura auto_explain per loggare i piani automaticamente
-- In postgresql.conf:
-- shared_preload_libraries = 'auto_explain'
-- auto_explain.log_min_duration = '500ms'
-- auto_explain.log_analyze = true
-- auto_explain.log_buffers = true

-- 4. Reset statistiche dopo aver applicato fix
SELECT pg_stat_statements_reset();
```

---

## Relazioni

??? info "Indici — Strutture e quando il planner li usa"
    Come costruire indici che il planner effettivamente utilizzerà.

    **Approfondimento →** [Indici](../fondamentali/indici.md)

??? info "MVCC e Vacuum — Statistiche e bloat"
    Come VACUUM mantiene le statistiche aggiornate.

    **Approfondimento →** [MVCC e Vacuum](../postgresql/mvcc-vacuum.md)

## Riferimenti

- [PostgreSQL EXPLAIN Documentation](https://www.postgresql.org/docs/current/using-explain.html)
- [explain.depesz.com — Visualizzatore EXPLAIN](https://explain.depesz.com/)
- [PEV2 — Plan visualizer](https://explain.dalibo.com/)
