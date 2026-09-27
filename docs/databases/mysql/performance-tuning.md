---
title: "MySQL — Performance Tuning e Query Optimizer"
slug: performance-tuning
category: databases
tags: [mysql, mariadb, innodb, performance, explain, optimizer, indici, tuning]
search_keywords: [mysql explain, explain format json, explain analyze mysql, optimizer trace, possible_keys, key_len, using filesort, using temporary, using index, clustered index innodb, secondary index lookup, nested loop join mysql, hash join mysql, innodb buffer pool tuning, adaptive hash index, slow query log, pt-query-digest, percona toolkit, covering index mysql, index merge, sys schema, performance_schema, query optimization mysql, innodb_buffer_pool_size]
parent: databases/mysql/_index
related: [databases/sql-avanzato/query-optimizer, databases/fondamentali/indici, databases/mysql/architettura-replicazione]
official_docs: https://dev.mysql.com/doc/refman/8.0/en/optimization.html
status: complete
difficulty: advanced
last_updated: 2026-09-27
---

# MySQL — Performance Tuning e Query Optimizer

## Panoramica

Questa pagina copre come diagnosticare e risolvere query lente su MySQL/MariaDB con InnoDB: lettura di `EXPLAIN` e `EXPLAIN FORMAT=JSON`, ispezione delle decisioni del planner con `optimizer_trace`, differenze tra clustered index (PK) e indici secondari, algoritmi di join disponibili (nested loop, hash join da 8.0.18), tuning del buffer pool InnoDB e triage con slow query log / `pt-query-digest`. Il modello di costo e gli strumenti di analisi di MySQL sono strutturalmente diversi da Postgres — vedi [Query Optimizer e EXPLAIN](../sql-avanzato/query-optimizer.md) per il confronto lato Postgres — perché l'ottimizzatore InnoDB ragiona su un clustered index invece che su un heap indipendente dagli indici. Non copre architettura InnoDB o replicazione, già trattate in [Architettura e Replicazione](architettura-replicazione.md).

## Concetti Chiave

!!! note "Il piano di query non è opzionale da leggere"
    Come su qualsiasi RDBMS, una query lenta su MySQL è quasi sempre un problema di piano: scan completo invece di uso indice, join nell'ordine sbagliato, filesort non necessario. `EXPLAIN` è il primo strumento, non l'ultimo.

- **Clustered index è la tabella**: in InnoDB i dati sono fisicamente ordinati per Primary Key (o da una PK implicita a 6 byte se non dichiarata — da evitare sempre). Non esiste un heap separato come in Postgres.
- **Secondary index lookup a due passi**: un indice secondario contiene il valore della PK, non un puntatore fisico alla riga. Una query che filtra su un indice secondario e recupera colonne non coperte richiede un secondo accesso al clustered index per ogni riga trovata ("bookmark lookup").
- **`rows` in EXPLAIN è una stima, non un conteggio**: rappresenta quante righe l'optimizer *si aspetta* di esaminare per ottenere il risultato, basata su statistiche degli indici — non il numero di righe restituite.
- **`filtered`**: percentuale stimata di righe che sopravvivono ai filtri aggiuntivi dopo l'accesso via indice. `rows × filtered / 100` = stima righe effettivamente processate dal nodo successivo del piano.
- **Extra è dove si nascondono i problemi**: `Using filesort` (ordinamento non risolto da un indice), `Using temporary` (tabella temporanea per GROUP BY/DISTINCT), `Using index` (covering index, nessun accesso al clustered index) sono i segnali più diagnostici dell'intero output.

## Architettura / Come Funziona

### EXPLAIN — Formato Tradizionale

```sql
EXPLAIN
SELECT o.id, o.totale, c.nome
FROM ordini o
JOIN clienti c ON c.id = o.cliente_id
WHERE o.stato = 'spedito'
  AND o.creato_il > '2026-01-01'
ORDER BY o.totale DESC
LIMIT 20;
```

```
+----+-------------+-------+--------+------------------+---------+---------+--------------------+------+----------------------------------+
| id | select_type | table | type   | possible_keys    | key     | key_len | ref                | rows | Extra                            |
+----+-------------+-------+--------+------------------+---------+---------+--------------------+------+----------------------------------+
|  1 | SIMPLE      | o     | range  | idx_stato_data   | idx_stato_data | 5 | NULL          | 4200 | Using index condition; Using filesort |
|  1 | SIMPLE      | c     | eq_ref | PRIMARY          | PRIMARY | 4       | mydb.o.cliente_id  |    1 | NULL                              |
+----+-------------+-------+--------+------------------+---------+---------+--------------------+------+----------------------------------+
```

| Colonna | Significato |
|---|---|
| `type` | Metodo di accesso: `const`/`eq_ref` (ottimo, 1 riga) → `ref` → `range` → `index` → `ALL` (full table scan, il peggiore) |
| `possible_keys` | Indici che il planner ha *considerato* — non necessariamente usati |
| `key` | Indice effettivamente scelto (`NULL` = nessun indice usato) |
| `key_len` | Byte dell'indice effettivamente usati — utile per capire se un indice composito è sfruttato parzialmente |
| `ref` | Colonna o costante confrontata con l'indice |
| `rows` | Stima righe esaminate (non restituite) |
| `filtered` | % stimata di righe sopravvissute ai filtri extra (visibile con `EXPLAIN FORMAT=TREE` o `EXTENDED`) |
| `Extra` | Informazioni critiche: `Using filesort`, `Using temporary`, `Using index`, `Using index condition` |

!!! warning "`type: ALL` su tabelle grandi è quasi sempre un problema"
    A differenza di Postgres, dove un Seq Scan può essere la scelta corretta anche su tabelle grandi (>20-30% di righe lette), su InnoDB un `type: ALL` in produzione va quasi sempre indagato: il costo del full scan è dominato dal fatto che le pagine potrebbero non essere in buffer pool, a differenza di un ambiente Postgres ben tarato con `effective_cache_size`.

### EXPLAIN FORMAT=JSON — Dettaglio Completo

`EXPLAIN` tradizionale nasconde informazioni sul costo stimato per singolo nodo. `FORMAT=JSON` le espone:

```sql
EXPLAIN FORMAT=JSON
SELECT o.id, o.totale, c.nome
FROM ordini o
JOIN clienti c ON c.id = o.cliente_id
WHERE o.stato = 'spedito'
ORDER BY o.totale DESC
LIMIT 20\G
```

```json
{
  "query_block": {
    "select_id": 1,
    "cost_info": {
      "query_cost": "1024.60"
    },
    "ordering_operation": {
      "using_filesort": true,
      "nested_loop": [
        {
          "table": {
            "table_name": "o",
            "access_type": "range",
            "possible_keys": ["idx_stato_data"],
            "key": "idx_stato_data",
            "used_key_parts": ["stato"],
            "rows_examined_per_scan": 4200,
            "rows_produced_per_join": 4200,
            "filtered": "100.00",
            "cost_info": {
              "read_cost": "850.20",
              "eval_cost": "420.00",
              "prefix_cost": "1270.20"
            }
          }
        },
        {
          "table": {
            "table_name": "c",
            "access_type": "eq_ref",
            "key": "PRIMARY",
            "rows_examined_per_scan": 1
          }
        }
      ]
    }
  }
}
```

`cost_info.query_cost` è il numero che l'optimizer usa per confrontare piani alternativi — analogo concettuale al `cost` di Postgres, ma calibrato su costanti diverse (`optimizer_switch`, `mysql.server_cost`, `mysql.engine_cost`).

### EXPLAIN ANALYZE — Numeri Reali (MySQL 8.0.18+)

A differenza di Postgres, dove `EXPLAIN ANALYZE` è disponibile da sempre, MySQL lo ha introdotto solo in 8.0.18, con un formato ad albero testuale invece che tabellare:

```sql
EXPLAIN ANALYZE
SELECT o.id, o.totale, c.nome
FROM ordini o
JOIN clienti c ON c.id = o.cliente_id
WHERE o.stato = 'spedito'
ORDER BY o.totale DESC
LIMIT 20;
```

```
-> Limit: 20 row(s)  (actual time=12.4..12.5 rows=20 loops=1)
    -> Sort: o.totale DESC, limit input to 20 row(s) per chunk  (actual time=12.4..12.4 rows=20 loops=1)
        -> Stream results  (cost=1024.60 rows=4200) (actual time=0.8..11.9 rows=4180 loops=1)
            -> Nested loop inner join  (cost=1024.60 rows=4200) (actual time=0.7..10.5 rows=4180 loops=1)
                -> Filter: (o.stato = 'spedito')  (cost=850.20 rows=4200) (actual time=0.4..6.2 rows=4180 loops=1)
                    -> Index range scan on o using idx_stato_data  (cost=850.20 rows=4200) (actual time=0.3..5.1 rows=4180 loops=1)
                -> Single-row index lookup on c using PRIMARY (id=o.cliente_id)  (cost=0.15 rows=1) (actual time=0.001..0.001 rows=1 loops=4180)
```

!!! tip "EXPLAIN ANALYZE ESEGUE davvero la query"
    Come su Postgres, `EXPLAIN ANALYZE` esegue realmente la query (poi scarta i risultati). Su una `UPDATE`/`DELETE` lenta o su un ambiente di produzione, preferire `EXPLAIN` semplice o testare su una replica.

### Optimizer Trace — Quando EXPLAIN Non Basta

Per capire *perché* il planner ha scartato un indice o un ordine di join, `optimizer_trace` espone il ragionamento passo-passo:

```sql
SET optimizer_trace = "enabled=on";

SELECT o.id FROM ordini o WHERE o.stato = 'spedito' AND o.creato_il > '2026-01-01';

SELECT TRACE FROM information_schema.OPTIMIZER_TRACE\G

SET optimizer_trace = "enabled=off";  -- Disabilitare sempre dopo l'uso: overhead per sessione
```

L'output JSON include le fasi `join_optimization`, `considered_execution_plans` (con costo di ogni combinazione di indici/join valutata) e `rejected_access_paths` con il motivo dello scarto (es. `"cause": "cost"`).

!!! warning "optimizer_trace ha overhead e non è pensato per produzione"
    Abilitarlo solo per la sessione di debug, mai globalmente. La trace può diventare molto grande su query con molti join — `SET optimizer_trace_max_mem_size = 1048576;` per limitarne la dimensione.

### Clustered Index vs Secondary Index — Impatto sulle Query

```sql
-- Tabella con PK su id (clustered index)
CREATE TABLE ordini (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    stato VARCHAR(20),
    totale DECIMAL(10,2),
    creato_il DATETIME,
    INDEX idx_stato_data (stato, creato_il)
) ENGINE=InnoDB;

-- Query che usa SOLO l'indice secondario (covering index) — NESSUN lookup al clustered index
EXPLAIN SELECT stato, creato_il FROM ordini WHERE stato = 'spedito';
-- Extra: Using index  ← ottimo, dato interamente nell'indice secondario

-- Query che richiede colonne non coperte — lookup extra per ogni riga
EXPLAIN SELECT stato, creato_il, totale FROM ordini WHERE stato = 'spedito';
-- Extra: NULL (nessun "Using index")  ← ogni riga richiede un secondo accesso al clustered index via PK
```

Questo è il motivo per cui **troppi indici secondari penalizzano write-heavy workload su InnoDB più che su Postgres**: ogni INSERT/UPDATE deve mantenere sia il clustered index sia ogni indice secondario, e ogni indice secondario aggiunge un livello di indirection (il valore PK) che su Postgres non esiste — lì tutti gli indici puntano direttamente all'heap con lo stesso costo.

### Algoritmi di Join

```
NESTED LOOP (unico algoritmo prima di 8.0.18):
  Per ogni riga del lato outer, cerca nel lato inner (idealmente via indice)
  Efficiente con indice sul lato inner; degrada rapidamente senza indice
  utilizzabile sulla join condition

HASH JOIN (introdotto in MySQL 8.0.18, default per join senza indice utile
  dalla 8.0.20 in poi):
  Costruisce hash table dal lato più piccolo, poi scansiona l'altro lato
  MySQL lo sceglie automaticamente quando NON esiste un indice utilizzabile
  sulla condizione di join — prima di 8.0.18 questo caso forzava sempre
  un nested loop con Block Nested Loop (BNL), molto più lento
```

```sql
-- Forzare la visualizzazione dell'algoritmo di join scelto
EXPLAIN FORMAT=TREE
SELECT o.id, l.prodotto
FROM ordini o
JOIN log_spedizioni l ON l.ordine_id = o.id  -- nessun indice su l.ordine_id
WHERE o.stato = 'spedito';

-- Se l.ordine_id non è indicizzato, l'output mostra "Hash join" (8.0.20+)
-- invece del vecchio "Block Nested Loop" — miglioramento significativo
-- di throughput su join senza indice disponibile
```

!!! tip "Hash join non sostituisce l'indice mancante"
    Il fatto che MySQL 8.0.20+ scelga automaticamente un hash join invece di un lentissimo Block Nested Loop non significa che l'indice mancante vada ignorato: un `eq_ref`/`ref` con indice resta quasi sempre più veloce di un hash join su tabelle grandi. L'hash join è una rete di sicurezza, non un sostituto del disegno degli indici.

## Configurazione & Pratica

### InnoDB Buffer Pool Tuning

```ini
# my.cnf — parametri buffer pool per throughput OLTP
[mysqld]
innodb_buffer_pool_size = 24G           # 70-80% RAM su istanza dedicata; deve contenere il working set
innodb_buffer_pool_instances = 16       # 1 istanza per GB fino a un massimo pratico di 16-32; riduce mutex contention
innodb_buffer_pool_chunk_size = 128M    # innodb_buffer_pool_size deve essere multiplo di instances*chunk_size
innodb_adaptive_hash_index = ON         # Hash index automatico su pagine "calde" — vedi warning sotto
innodb_stats_persistent = ON            # Statistiche persistenti su disco invece che ricalcolate ad ogni restart
innodb_stats_persistent_sample_pages = 128  # Più campioni = stime più precise, più costo su ANALYZE TABLE
```

```sql
-- Verificare hit ratio del buffer pool (target: >99% in produzione)
SELECT
    (1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)) * 100 AS hit_ratio_pct
FROM (
    SELECT
        VARIABLE_VALUE AS Innodb_buffer_pool_reads
    FROM performance_schema.global_status
    WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads'
) reads,
(
    SELECT
        VARIABLE_VALUE AS Innodb_buffer_pool_read_requests
    FROM performance_schema.global_status
    WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'
) requests;

-- Stato dettagliato del buffer pool (pagine dirty, free, LRU)
SHOW ENGINE INNODB STATUS\G
-- Sezione BUFFER POOL AND MEMORY
```

!!! warning "Adaptive Hash Index può peggiorare le performance sotto certi workload"
    L'Adaptive Hash Index (AHI) costruisce automaticamente una hash table in-memory per le pagine più accedute, utile per lookup puntuali ripetuti. Su workload con molte query concorrenti che competono per il lock dell'AHI (`btr_search_latch`), o con pattern di accesso molto variabili (nessuna pagina "calda" stabile), l'AHI diventa overhead puro. Se `SHOW ENGINE INNODB STATUS` mostra un hit rate basso per l'AHI insieme a contention visibile, disabilitarlo e misurare: `SET GLOBAL innodb_adaptive_hash_index = OFF;` (richiede test A/B, non è una scelta universale).

### Slow Query Log e pt-query-digest

```ini
# my.cnf — abilitare slow query log
[mysqld]
slow_query_log = ON
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 1                    # Soglia in secondi
log_queries_not_using_indexes = ON     # Logga anche query veloci ma senza indice (utile per triage preventivo)
```

```bash
# Percona Toolkit — aggregare lo slow log per pattern di query (non singola query)
pt-query-digest /var/log/mysql/slow.log > digest_report.txt

# Output: query raggruppate per fingerprint, ordinate per tempo totale consumato
# Sezioni chiave nel report:
#   Query 1: 0.15QPS, 0.02x concurrency — tempo totale, per-query, distribuzione
#   EXPLAIN: incluso automaticamente per la query di esempio

# Analizzare solo un intervallo temporale specifico
pt-query-digest --since '2026-09-27 00:00:00' --until '2026-09-27 06:00:00' \
  /var/log/mysql/slow.log

# Analizzare direttamente da performance_schema invece che dal file di log
pt-query-digest --processlist h=localhost,u=monitor_user,p=password
```

!!! tip "log_queries_not_using_indexes va acceso solo temporaneamente"
    Su un'istanza con molte query legittimamente senza indice (es. report batch notturni), questa opzione può gonfiare lo slow log fino a renderlo inutilizzabile. Abilitarla per una finestra di triage, poi disattivarla.

### Index Strategy — Covering Index e Index Merge

```sql
-- Covering index: include tutte le colonne necessarie alla query, evitando
-- il secondo accesso al clustered index
CREATE INDEX idx_covering ON ordini (stato, creato_il, totale);

EXPLAIN SELECT stato, creato_il, totale FROM ordini WHERE stato = 'spedito';
-- Extra: Using index  ← covering, nessun lookup

-- Index merge: MySQL può combinare PIÙ indici singola-colonna con AND/OR
-- invece di richiedere sempre un indice composito
EXPLAIN SELECT * FROM ordini WHERE stato = 'spedito' OR cliente_id = 42;
-- type: index_merge
-- Extra: Using union(idx_stato,idx_cliente_id); Using where
```

```sql
-- Verificare indici inutilizzati (candidati alla rimozione — riducono write cost)
SELECT
    object_schema, object_name, index_name
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE index_name IS NOT NULL
  AND count_star = 0
  AND object_schema = 'mydb'
ORDER BY object_schema, object_name;
```

## Best Practices

- **Preferire pochi indici compositi ben scelti a molti indici singola-colonna**: ogni indice aggiuntivo raddoppia il costo di scrittura su InnoDB (mantenimento clustered + secondario), più che su Postgres dove tutti gli indici hanno lo stesso costo relativo all'heap.
- **`EXPLAIN FORMAT=JSON` per capire il costo reale**, non solo `EXPLAIN` tabellare — la vista tradizionale nasconde `cost_info` per nodo.
- **Usare `optimizer_trace` solo per query specifiche in debug**, mai abilitato globalmente per l'overhead.
- **Monitorare `log_queries_not_using_indexes` a finestre**, non permanentemente.
- **Buffer pool dimensionato sul working set reale**, non solo % di RAM — un working set che eccede il buffer pool causa evizioni continue anche con `innodb_buffer_pool_size` alto.
- **`pt-query-digest` per triage aggregato**, non leggere lo slow log riga per riga — il valore è nel pattern, non nella singola occorrenza.

!!! warning "Statistiche InnoDB sono stimate, non esatte come rowcount"
    A differenza di un `COUNT(*)` esatto, `SHOW TABLE STATUS` e le colonne `rows` in `information_schema.TABLES` per InnoDB sono **stime statistiche**, ricalcolate periodicamente o su `ANALYZE TABLE`. Non usarle per logica applicativa che richiede un conteggio esatto — solo per capacity planning e diagnosi.

## Troubleshooting

### Scenario 1 — `EXPLAIN` mostra `type: ALL` nonostante l'indice esista

**Sintomo:** Query lenta, `EXPLAIN` mostra `type: ALL`, `key: NULL` anche se `possible_keys` elenca un indice pertinente.

**Causa:** Bassa selettività della colonna (l'optimizer stima che leggere via indice costerebbe più del full scan), statistiche obsolete, o un mismatch di tipo/collation tra colonna e valore di confronto che impedisce l'uso dell'indice.

**Soluzione:**
```sql
-- 1. Verificare la cardinalità reale dell'indice
SHOW INDEX FROM ordini WHERE Key_name = 'idx_stato_data';
-- Cardinality basso rispetto al numero di righe = colonna poco selettiva

-- 2. Aggiornare le statistiche
ANALYZE TABLE ordini;

-- 3. Verificare mismatch di tipo (causa comune e silenziosa)
-- Se cliente_id è INT ma la query filtra con stringa:
EXPLAIN SELECT * FROM ordini WHERE cliente_id = '42';  -- conversione implicita, indice ignorato
EXPLAIN SELECT * FROM ordini WHERE cliente_id = 42;    -- corretto

-- 4. Forzare l'uso dell'indice per confermare il sospetto (solo debug)
EXPLAIN SELECT * FROM ordini FORCE INDEX (idx_stato_data) WHERE stato = 'spedito';
```

---

### Scenario 2 — `Using filesort` su query con ORDER BY e LIMIT

**Sintomo:** `EXPLAIN` mostra `Using filesort` nell'`Extra`; query con `ORDER BY` + `LIMIT` piccolo comunque lenta su tabella grande.

**Causa:** L'indice usato per il filtro `WHERE` non copre anche l'ordinamento richiesto — MySQL deve materializzare e ordinare il result set in memoria (o su disco se supera `sort_buffer_size`).

**Soluzione:**
```sql
-- 1. Creare un indice composito che copra SIA il filtro SIA l'ordinamento,
--    nell'ordine giusto: colonne WHERE (uguaglianza) prima, colonna ORDER BY dopo
CREATE INDEX idx_stato_totale ON ordini (stato, totale DESC);

EXPLAIN SELECT id, totale FROM ordini
WHERE stato = 'spedito'
ORDER BY totale DESC
LIMIT 20;
-- Extra: Using index condition  ← filesort eliminato

-- 2. Se il filesort è inevitabile (ordinamento su colonna non indicizzabile),
--    aumentare sort_buffer_size per la sessione
SET sort_buffer_size = 4194304;  -- 4MB, default spesso troppo basso per sort grandi

-- 3. Verificare se il filesort avviene su disco (sintomo di sort_buffer_size insufficiente)
SHOW STATUS LIKE 'Sort_merge_passes';
-- Valore alto e crescente = molti sort spillano su disco
```

---

### Scenario 3 — Query con JOIN lenta, nessun indice sulla foreign key

**Sintomo:** `EXPLAIN` mostra `type: ALL` sul lato "molti" di un join, con `rows` altissimo; la query impiega secondi su tabelle con milioni di righe.

**Causa:** La colonna di join non è indicizzata — prima di MySQL 8.0.20 questo forzava un Block Nested Loop molto lento; da 8.0.20 in poi MySQL sceglie un hash join automaticamente, più veloce ma comunque subottimale rispetto a un `eq_ref` con indice.

**Soluzione:**
```sql
-- 1. Verificare quale algoritmo di join viene usato
EXPLAIN FORMAT=TREE
SELECT o.id, l.evento
FROM ordini o
JOIN log_spedizioni l ON l.ordine_id = o.id
WHERE o.stato = 'spedito';
-- Cerca "Hash join" (8.0.20+) o "Block Nested Loop" (versioni precedenti)

-- 2. Creare l'indice sulla foreign key mancante
CREATE INDEX idx_log_ordine_id ON log_spedizioni (ordine_id);

-- 3. Rieseguire EXPLAIN — dovrebbe passare a eq_ref/ref con rows molto più basso
EXPLAIN FORMAT=TREE
SELECT o.id, l.evento
FROM ordini o
JOIN log_spedizioni l ON l.ordine_id = o.id
WHERE o.stato = 'spedito';
```

---

### Scenario 4 — `SELECT COUNT(*)` lentissimo su tabella InnoDB grande

**Sintomo:** `SELECT COUNT(*) FROM tabella` impiega secondi/minuti su una tabella InnoDB con decine di milioni di righe, mentre su MyISAM (storicamente) era istantaneo.

**Causa:** InnoDB, a differenza di MyISAM, non mantiene un contatore di righe esatto per tabella — un `COUNT(*)` senza filtro richiede una scansione completa dell'indice più piccolo disponibile (di solito una PK o un covering index).

**Soluzione:**
```sql
-- 1. Se una stima è accettabile (dashboard, capacity planning), usare le statistiche
SELECT TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'mydb' AND TABLE_NAME = 'ordini';
-- Approssimato, aggiornato da ANALYZE TABLE o automaticamente

-- 2. Se serve un conteggio esatto e frequente, mantenere un contatore applicativo
--    (tabella separata aggiornata via trigger o transazione) invece di COUNT(*) ripetuto

-- 3. Se il conteggio è filtrato, assicurarsi che il filtro sia coperto da un
--    indice stretto (covering) per minimizzare le pagine lette
CREATE INDEX idx_stato_covering ON ordini (stato);
EXPLAIN SELECT COUNT(*) FROM ordini WHERE stato = 'spedito';
-- Extra: Using index  ← scan del solo indice, non del clustered index intero
```

## Relazioni

??? info "Query Optimizer PostgreSQL — confronto diretto"
    Stesso problema (piano subottimale, stime di cardinalità errate) ma modello di costo e strumenti diagnostici diversi: `EXPLAIN ANALYZE` nativo da sempre, `pg_stat_statements` invece di `pt-query-digest`, `work_mem` invece di `sort_buffer_size`.

    **Approfondimento →** [Query Optimizer e EXPLAIN](../sql-avanzato/query-optimizer.md)

??? info "Indici — fondamentali agnostici al motore"
    Concetti di selettività, covering index e composite index applicabili a qualsiasi RDBMS.

    **Approfondimento →** [Indici](../fondamentali/indici.md)

??? info "Architettura InnoDB — buffer pool, redo/undo log"
    Il contesto architetturale (clustered index, buffer pool, MVCC via undo log) su cui si basa questo tuning.

    **Approfondimento →** [Architettura e Replicazione](architettura-replicazione.md)

## Riferimenti

- [MySQL 8.0 Reference Manual — Optimization](https://dev.mysql.com/doc/refman/8.0/en/optimization.html)
- [MySQL 8.0 Reference Manual — EXPLAIN Output Format](https://dev.mysql.com/doc/refman/8.0/en/explain-output.html)
- [MySQL 8.0 Reference Manual — Tracing the Optimizer](https://dev.mysql.com/doc/refman/8.0/en/optimizer-trace.html)
- [MySQL 8.0 Reference Manual — Hash Join Optimization](https://dev.mysql.com/doc/refman/8.0/en/hash-joins.html)
- [Percona Toolkit — pt-query-digest Documentation](https://docs.percona.com/percona-toolkit/pt-query-digest.html)
