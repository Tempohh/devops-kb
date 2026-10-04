---
title: "Indici — Strutture e Strategie"
slug: indici
category: databases
tags: [indici, b-tree, hash, gin, gist, brin, performance, query-planner, postgresql]
search_keywords: [database index, b-tree index, hash index, gin index, gist index, brin index, partial index, covering index, composite index, index only scan, bloat index, index selectivity, cardinality, query planner, index scan vs seq scan, full text search, tsvector, multicolumn index, expression index, pgvector, hnsw, ivfflat, index maintenance]
parent: databases/fondamentali/_index
related: [databases/fondamentali/transazioni-concorrenza, databases/sql-avanzato/query-optimizer, databases/postgresql/mvcc-vacuum]
official_docs: https://www.postgresql.org/docs/current/indexes.html
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
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

**Regola pratica per l'ordine**: colonne con `=` prima, poi colonne con range (`<`, `>`, `BETWEEN`), poi colonne per `ORDER BY`. A parità di tipo di condizione (entrambe `=`), mettere prima la colonna più selettiva (es. `user_id`) rende l'indice più utile anche per query sul solo prefisso; ma se molte query filtrano solo su `status`, la colonna di testa deve essere quella usata più spesso.

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

!!! note "Index-only scan e visibility map"
    PostgreSQL non memorizza la visibilità MVCC nell'indice: per evitare il heap access consulta la *visibility map*, aggiornata da `VACUUM`. Su tabelle con molti UPDATE e autovacuum in ritardo, l'`Index Only Scan` mostra `Heap Fetches` elevati e perde il vantaggio.

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

Dalla versione 10 gli hash index sono scritti nel WAL (prima erano non crash-safe e non replicati, da cui la cattiva fama) (WAL — Write-Ahead Log: il meccanismo di durabilità di PostgreSQL che registra le modifiche prima di applicarle, garantendo il recovery dopo un crash). Nella pratica, i B-tree sono quasi sempre preferiti per la loro versatilità — un hash index ha senso solo se la colonna è usata *esclusivamente* per equality e il volume è tale che la differenza di performance è misurabile.

---

## GIN — Generalized Inverted Index

GIN è un indice invertito: mappa ogni *elemento* (parola, chiave JSON, elemento array) alle righe che lo contengono. Ideale per tipi di dato multi-valore.

**Casi d'uso:** Full-text search, ricerca in JSONB (JSON Binary — il formato di storage binario di PostgreSQL per JSON, più veloce da interrogare rispetto a JSON testuale), ricerca in array, `pg_trgm` per LIKE fuzzy.

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

## Indici Vettoriali (pgvector)

Per similarity search su embedding (RAG, ricerca semantica) l'estensione `pgvector` offre indici approssimati (ANN — Approximate Nearest Neighbor): scambiano un po' di recall per latenza molto più bassa rispetto a una scansione esatta.

| Indice | Meccanismo | Trade-off |
|---|---|---|
| `hnsw` | Grafo multilivello navigabile | Recall/latenza migliori, build lento, molta RAM; nessun training, utilizzabile su tabella vuota |
| `ivfflat` | Cluster (liste) con ricerca nelle `probes` più vicine | Build veloce e leggero; richiede dati presenti al build e perde recall se i dati cambiano molto |

```sql
CREATE EXTENSION vector;
CREATE INDEX idx_doc_emb ON documenti USING hnsw (embedding vector_cosine_ops);

-- operatore di distanza coerente con la operator class (<=> = coseno)
SET hnsw.ef_search = 100;  -- più alto = recall maggiore, più lento
SELECT id FROM documenti ORDER BY embedding <=> $1 LIMIT 10;
```

!!! warning "Operator class e filtri"
    La query deve usare lo stesso operatore della operator class (`vector_l2_ops` → `<->`, `vector_cosine_ops` → `<=>`), altrimenti l'indice non viene usato. Con filtri `WHERE` selettivi l'indice ANN può restituire meno righe di `LIMIT`: verifica con `EXPLAIN` e valuta indici parziali o partizionamento.

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
    relname AS tablename,
    indexrelname AS indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS idx_size,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
-- Questa query mostra dimensioni e utilizzo, non il bloat: per misurarlo
-- usa l'estensione pgstattuple (pgstatindex('nome_indice') -> avg_leaf_density)

-- Rebuild indice senza bloccare (PostgreSQL 12+)
REINDEX INDEX CONCURRENTLY idx_ordini_cliente;
```

---

## Strategie Operative

```sql
-- 1. Verifica indici non usati (da rimuovere)
-- (esclude indici UNIQUE/PK: servono come vincolo anche se mai scansionati)
SELECT s.schemaname, s.relname, s.indexrelname, s.idx_scan
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0
  AND NOT i.indisunique
ORDER BY pg_relation_size(s.indexrelid) DESC;
-- Le statistiche si azzerano con pg_stat_reset(): valuta su un periodo lungo
-- e controlla anche le repliche prima di rimuovere

-- 2. Crea indici in produzione senza lock
CREATE INDEX CONCURRENTLY idx_ordini_data ON ordini(created_at);
-- CONCURRENTLY: non blocca scritture, ma richiede più tempo

-- 3. Verifica che una query usi l'indice
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM ordini WHERE status = 'pending';
-- Cerca "Index Scan" o "Index Only Scan" nell'output
-- Buffers: mostra hit cache vs disk I/O
```

## Troubleshooting

### Scenario 1 — L'indice esiste ma il planner non lo usa

**Sintomo:** `EXPLAIN ANALYZE` mostra `Seq Scan` su una tabella grande nonostante esista un indice sulla colonna filtrata.

**Causa:** Statistiche stale, bassa selettività della colonna, o `random_page_cost` non calibrato per SSD.

**Soluzione:**
```sql
-- Aggiorna le statistiche
ANALYZE nome_tabella;

-- Verifica la selettività della colonna
SELECT attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'nome_tabella' AND attname = 'nome_colonna';

-- Se l'infrastruttura usa SSD, abbassa random_page_cost
SET random_page_cost = 1.1;  -- default 4.0 (ottimizzato per HDD)

-- Forza l'uso dell'indice temporaneamente per isolare il problema
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT * FROM nome_tabella WHERE colonna = 'valore';
SET enable_seqscan = on;
```

### Scenario 2 — Index bloat: indice lento e di dimensioni eccessive

**Sintomo:** Query con indice sempre più lente nel tempo, `pg_relation_size(indexrelid)` mostra dimensioni anomale, `idx_scan` alto ma throughput basso.

**Causa:** Molti UPDATE/DELETE lasciano dead tuples nell'indice. PostgreSQL non compatta automaticamente le pagine interne del B-tree.

**Soluzione:**
```sql
-- Verifica la dimensione e il numero di scan degli indici
SELECT
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE relname = 'nome_tabella'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Rebuild senza lock (PostgreSQL 12+)
REINDEX INDEX CONCURRENTLY idx_nome;

-- Alternativa: ricrea l'indice manualmente
CREATE INDEX CONCURRENTLY idx_nome_new ON tabella(colonna);
DROP INDEX CONCURRENTLY idx_nome;
ALTER INDEX idx_nome_new RENAME TO idx_nome;
```

### Scenario 3 — Indice composito non usato per colonne intermedie

**Sintomo:** Un indice su `(a, b, c)` non viene usato per query che filtrano solo su `b` o `c`. Oppure un range filter su `a` impedisce l'uso di `b` nell'indice.

**Causa:** Il B-tree composito è navigabile efficacemente da sinistra: un range su `a` "consuma" il prefix e le colonne successive vengono solo filtrate dentro l'indice, non usate per posizionarsi. Dalla PostgreSQL 18 esiste lo *skip scan*, che permette di usare l'indice anche senza condizione sulla colonna di testa, ma solo se questa ha pochi valori distinti; nelle versioni precedenti resta il limite descritto.

**Soluzione:**
```sql
-- Verifica quale parte dell'indice viene usata
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ordini WHERE status = 'pending' AND created_at > now() - interval '7 days';

-- Se status ha poca selettività, considera l'ordine inverso
CREATE INDEX idx_ordini_data_status ON ordini(created_at DESC, status)
WHERE status IN ('pending', 'processing');

-- Per query solo su colonne intermedie: indice separato
CREATE INDEX idx_ordini_created ON ordini(created_at DESC);
```

### Scenario 4 — CREATE INDEX blocca le scritture in produzione

**Sintomo:** `CREATE INDEX` su tabella grande blocca INSERT/UPDATE/DELETE per minuti o ore, causando timeout a cascata sulle applicazioni.

**Causa:** `CREATE INDEX` standard acquisisce un lock `ShareLock` che blocca le scritture per tutta la durata della build.

**Soluzione:**
```sql
-- Usa CONCURRENTLY: nessun lock su scritture (richiede più tempo)
CREATE INDEX CONCURRENTLY idx_ordini_cliente ON ordini(cliente_id);

-- Verifica il progresso (PostgreSQL 12+)
SELECT phase, blocks_done, blocks_total,
       round(100.0 * blocks_done / nullif(blocks_total, 0), 1) AS pct
FROM pg_stat_progress_create_index
WHERE relid = 'ordini'::regclass;

-- Se CONCURRENTLY fallisce (es. per violazione unique), rimuovi l'indice invalido
SELECT indexname, indisvalid
FROM pg_indexes
JOIN pg_index ON indexrelid = (schemaname||'.'||indexname)::regclass
WHERE tablename = 'ordini';

DROP INDEX CONCURRENTLY idx_ordini_cliente;  -- rimuovi l'indice invalido e riprova
```

---

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
