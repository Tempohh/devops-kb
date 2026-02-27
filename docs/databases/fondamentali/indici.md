---
title: "Indici — Strutture e Strategie"
slug: indici
category: databases
tags: [indici, b-tree, hash, gin, gist, brin, performance, query-planner, postgresql]
search_keywords: [database index, b-tree index, hash index, gin index, gist index, brin index, partial index, covering index, composite index, index only scan, bloat index, index selectivity, cardinality, query planner, index scan vs seq scan, full text search, tsvector, multicolumn index, expression index, pgvector, hnsw, ivfflat, index maintenance]
parent: databases/fondamentali/_index
related: [databases/fondamentali/transazioni-concorrenza, databases/sql-avanzato/query-optimizer, databases/postgresql/mvcc-vacuum]
official_docs: https://www.postgresql.org/docs/current/indexes.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Indici — Strutture e Strategie

## Panoramica

Un indice è una struttura dati ausiliaria che permette di trovare righe senza scansionare l'intera tabella. La scelta sbagliata degli indici è la causa più comune di query lente in produzione — sia per troppi indici (write overhead) che per indici mancanti o non usati dal planner.

## B-Tree — L'Indice di Default

Il B-tree (Balanced Tree) è l'indice default di PostgreSQL e quasi ogni database relazionale. È una struttura ad albero bilanciato dove le foglie contengono i valori indicizzati con puntatori alle righe corrispondenti.

```
         [30 | 70]
        /    |    \
  [10|20]  [40|60]  [80|90]
  /  |  \    ...      ...
 righe  righe
```

**Supporta**: `=`, `<`, `>`, `<=`, `>=`, `BETWEEN`, `LIKE 'foo%'` (prefix), `IS NULL`, `ORDER BY`.
**Non supporta**: `LIKE '%foo'` (suffix), `LIKE '%foo%'`, operatori vettoriali.

### Composite Index e Ordine delle Colonne

L'ordine delle colonne in un indice composito è fondamentale. Un indice su `(a, b, c)` può essere usato per query su `a`, su `(a, b)`, su `(a, b, c)` — ma **non** per query solo su `b` o `c`.

```sql
-- Indice su (status, created_at)
CREATE INDEX idx_ordini_status_data ON ordini(status, created_at DESC);

-- USATO: filtra su status (colonna di testa)
SELECT * FROM ordini WHERE status = 'pending' ORDER BY created_at DESC;

-- USATO: entrambe le colonne
SELECT * FROM ordini WHERE status = 'shipped' AND created_at > '2024-01-01';

-- NON usato efficacemente: salta la prima colonna
SELECT * FROM ordini WHERE created_at > '2024-01-01';
-- → il planner probabilmente farà seq scan o usa un altro indice
```

**Regola pratica per l'ordine**: colonne con `=` prima, poi colonne con range (`<`, `>`, `BETWEEN`), poi colonne per `ORDER BY`. Le colonne con altissima selettività (es. user_id univoco) prima delle colonne con bassa selettività (es. status con 3 valori).

### Covering Index (Index-Only Scan)

Se un indice contiene tutte le colonne necessarie a soddisfare una query, il database non accede alle pagine della tabella — solo all'indice. In PostgreSQL si usa `INCLUDE` per aggiungere colonne non-chiave all'indice:

```sql
-- Senza covering: indice + heap access per ogni riga
CREATE INDEX idx_ordini_cliente ON ordini(cliente_id);

-- Con covering: index-only scan possibile
CREATE INDEX idx_ordini_cliente_covering
    ON ordini(cliente_id)
    INCLUDE (status, totale, created_at);

-- Questa query usa index-only scan (nessun heap access)
SELECT status, totale, created_at FROM ordini WHERE cliente_id = 123;
```

!!! tip "Quando usare INCLUDE"
    INCLUDE è utile quando le colonne extra vengono sempre lette insieme alla chiave. Non indicizzarle come chiave (non fanno parte del criterio di ricerca) ma includile nel nodo foglia per evitare il heap access.

### Partial Index

Un indice su un sottoinsieme di righe. Molto più piccolo e performante di un indice full quando solo una frazione delle righe viene interrogata:

```sql
-- Indice solo sugli ordini non processati (es. 2% del totale)
CREATE INDEX idx_ordini_pending ON ordini(created_at)
    WHERE status = 'pending';

-- Indice su email solo per utenti attivi
CREATE INDEX idx_utenti_email_attivi ON utenti(email)
    WHERE deleted_at IS NULL;

-- Indice per unique constraint su subset
CREATE UNIQUE INDEX idx_slug_published ON articoli(slug)
    WHERE pubblicato = true;
```

### Expression Index

Indice su un'espressione calcolata, non su una colonna raw:

```sql
-- Ricerca case-insensitive senza full-text
CREATE INDEX idx_utenti_email_lower ON utenti(lower(email));

-- Ora questa query usa l'indice
SELECT * FROM utenti WHERE lower(email) = lower('Alice@Example.com');

-- Indice su JSON nested field
CREATE INDEX idx_metadata_tenant ON eventi((payload->>'tenant_id'));
```

---

## Hash Index

Un indice hash memorizza un hash del valore indicizzato. È più veloce di B-tree per `=` puro, ma non supporta range queries né ordinamenti.

```sql
CREATE INDEX idx_session_token_hash ON sessioni USING hash(token);
-- Ottimo per: WHERE token = 'abc123'
-- Inutile per: WHERE token > 'abc123', ORDER BY token
```

In PostgreSQL moderno (9.1+) gli hash index sono WAL-safe. Nella pratica, i B-tree sono quasi sempre preferiti per la loro versatilità — un hash index ha senso solo se la colonna è usata *esclusivamente* per equality e il volume è tale che la differenza di performance è misurabile.

---

## GIN — Generalized Inverted Index

GIN è un indice invertito: mappa ogni *elemento* (parola, chiave JSON, elemento array) alle righe che lo contengono. Ideale per tipi di dato multi-valore.

**Casi d'uso:** Full-text search, ricerca in JSONB, ricerca in array, `pg_trgm` per LIKE fuzzy.

```sql
-- Full-text search con GIN
CREATE INDEX idx_articoli_fts ON articoli USING gin(to_tsvector('italian', corpo));

SELECT * FROM articoli
WHERE to_tsvector('italian', corpo) @@ plainto_tsquery('italian', 'machine learning');

-- Ricerca in JSONB
CREATE INDEX idx_prodotti_tags ON prodotti USING gin(tags);

SELECT * FROM prodotti WHERE tags @> '["electronics", "sale"]';

-- Ricerca in array PostgreSQL
CREATE INDEX idx_ordini_labels ON ordini USING gin(labels);

SELECT * FROM ordini WHERE labels && ARRAY['urgent', 'vip'];

-- pg_trgm: LIKE fuzzy e similarity
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_prodotti_nome_trgm ON prodotti USING gin(nome gin_trgm_ops);

SELECT * FROM prodotti WHERE nome ILIKE '%wirel%';  -- usa l'indice trigram
```

**Trade-off**: GIN ha insert più costosi (aggiorna la struttura invertita per ogni elemento). Le scritture possono essere ottimizzate con `gin_pending_list_limit` — i nuovi item vanno in una pending list e vengono consolidati periodicamente.

---

## GiST — Generalized Search Tree

GiST è un framework generico per strutture ad albero che supportano operatori spaziali, geometrici, e di range. Usato per dati che non si mappano su un ordinamento lineare.

```sql
-- Range queries con GiST
CREATE INDEX idx_prenotazioni_periodo ON prenotazioni USING gist(periodo);
-- periodo è di tipo tsrange (timestamp range)

-- Trova prenotazioni che si sovrappongono a un periodo
SELECT * FROM prenotazioni
WHERE periodo && '[2024-03-01, 2024-03-07)'::tsrange;

-- PostGIS: indice geografico
CREATE INDEX idx_negozi_posizione ON negozi USING gist(posizione);

SELECT nome FROM negozi
WHERE ST_DWithin(posizione, ST_MakePoint(12.4924, 41.8902)::geography, 5000);
-- Negozi entro 5km da Roma centro
```

---

## BRIN — Block Range INdex

BRIN è un indice compatto che memorizza il min/max di ogni blocco fisico di pagine. Efficace solo quando i dati sono fisicamente ordinati (es. colonne auto-increment, timestamp di insert):

```sql
-- BRIN su tabella log con insert sequenziali per timestamp
CREATE INDEX idx_log_timestamp_brin ON log_eventi USING brin(created_at);
-- L'indice è ~100x più piccolo di un B-tree equivalente

-- Efficace perché i log vengono inseriti in ordine cronologico:
-- Blocco 1: Jan 1-10, Blocco 2: Jan 11-20, ...
-- Per WHERE created_at > '2024-02-01', salta quasi tutti i blocchi
```

!!! warning "Quando BRIN non funziona"
    BRIN è inutile se i dati non sono correlati fisicamente con il valore della colonna. Su una tabella `UPDATE`-heavy dove le righe vengono riordinate fisicamente (dead tuples, VACUUM), il BRIN perde correlazione e diventa inefficace.

---

## Selectivity e Cardinalità — Come il Planner Decide

Il query planner sceglie se usare un indice basandosi sul **costo stimato**. Le statistiche di selectivity (distribuzione dei valori) sono fondamentali:

```sql
-- Vedi statistiche del planner sulla colonna
SELECT attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'ordini' AND attname = 'status';

-- n_distinct: numero stimato di valori distinti
--   > 0: numero assoluto
--   < 0: frazione delle righe (es. -0.5 = 50% di righe ha valori distinti)
-- correlation: correlazione fisica (1.0 = ordinato, 0 = random)
```

**Quando il planner ignora l'indice:**
1. **Low selectivity**: `WHERE status = 'shipped'` con 90% delle righe in stato shipped → seq scan è più veloce
2. **Small table**: tabelle < ~1000 righe → seq scan ha overhead minore
3. **Stale statistics**: dopo bulk insert/delete senza ANALYZE → il planner usa stime errate
4. **Correlation bassa con random_page_cost alto**: accessi random a heap sono costosi su HDD (meno su SSD)

```sql
-- Aggiorna statistiche dopo operazioni massive
ANALYZE ordini;

-- Aumenta il campione per colonne con distribuzione non uniforme
ALTER TABLE ordini ALTER COLUMN status SET STATISTICS 500;
ANALYZE ordini;
```

---

## Index Bloat — Il Problema Silenzioso

Gli indici B-tree in PostgreSQL non compattano automaticamente. Le pagine con entry cancellate restano occupate ("dead tuples nell'indice"). Su tabelle con molti UPDATE/DELETE, l'indice può diventare 2-5x più grande del necessario.

```sql
-- Verifica bloat degli indici
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS idx_size,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;

-- Rebuild indice senza bloccare (PostgreSQL 12+)
REINDEX INDEX CONCURRENTLY idx_ordini_cliente;
```

---

## Strategie Operative

```sql
-- 1. Verifica indici non usati (da rimuovere)
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE 'pg_%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- 2. Crea indici in produzione senza lock
CREATE INDEX CONCURRENTLY idx_ordini_data ON ordini(created_at);
-- CONCURRENTLY: non blocca scritture, ma richiede più tempo

-- 3. Verifica che una query usi l'indice
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM ordini WHERE status = 'pending';
-- Cerca "Index Scan" o "Index Only Scan" nell'output
-- Buffers: mostra hit cache vs disk I/O
```

## Relazioni

??? info "Query Optimizer — Come il planner usa gli indici"
    EXPLAIN ANALYZE in dettaglio, cost model, hints.

    **Approfondimento →** [Query Optimizer](../sql-avanzato/query-optimizer.md)

??? info "MVCC e Vacuum — Indici e dead tuples"
    Come VACUUM compatta gli indici e gestisce il bloat.

    **Approfondimento →** [MVCC e Vacuum](../postgresql/mvcc-vacuum.md)

## Riferimenti

- [PostgreSQL — Index Types](https://www.postgresql.org/docs/current/indexes-types.html)
- [Use the Index, Luke](https://use-the-index-luke.com/)
- [pganalyze — Index Advisor](https://pganalyze.com/docs/index-advisor)
