---
title: "PostgreSQL Extensions"
slug: extensions
category: databases
tags: [postgresql, extensions, pgvector, timescaledb, postgis, pg-partman, pg-cron, full-text-search]
search_keywords: [postgresql extensions, pgvector vector search, timescaledb time series, postgis spatial, pg_partman partition management, pg_cron scheduled jobs, pg_trgm trigram similarity, hstore key-value, pg_stat_statements, pgaudit, citus distributed postgresql, pg_repack, logical decoding, wal2json, pgoutput, uuid-ossp, ltree hierarchical data, tablefunc crosstab]
parent: databases/postgresql/_index
related: [databases/sql-avanzato/partitioning, databases/fondamentali/modelli-dati, databases/nosql/redis]
official_docs: https://www.postgresql.org/docs/current/contrib.html
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# PostgreSQL Extensions

## Panoramica

PostgreSQL è estensibile by design: le estensioni aggiungono tipi di dati, funzioni, operatori, metodi di accesso agli indici e perfino esecutori di query — tutto senza fork del codice sorgente. Il catalogo ufficiale [PGXN](https://pgxn.org/) conta oltre 1000 estensioni; AWS RDS, Google Cloud SQL e Azure Database supportano un sottoinsieme selezionato.

Le estensioni più rilevanti in un contesto DevOps/backend si dividono in categorie:

| Categoria | Estensioni |
|-----------|-----------|
| Vector/AI | `pgvector` |
| Time series | `timescaledb` |
| Geospaziale | `postgis` |
| Manutenzione partizioni | `pg_partman` |
| Job scheduling | `pg_cron` |
| Monitoring | `pg_stat_statements`, `pg_activity` |
| Full-text search | `pg_trgm`, built-in `tsvector` |
| Utility | `uuid-ossp`, `hstore`, `ltree`, `pgcrypto` |

```sql
-- Installa un'estensione (richiede superuser o pg_extension_owner)
CREATE EXTENSION pgvector;

-- Lista estensioni installate
SELECT extname, extversion FROM pg_extension;

-- Aggiorna un'estensione
ALTER EXTENSION pgvector UPDATE TO '0.7.0';
```

---

## pgvector — Ricerca Vettoriale

[pgvector](https://github.com/pgml/pgvector) aggiunge il tipo `vector` e indici per nearest-neighbor search. Permette di fare semantic search, recommendation e RAG direttamente su PostgreSQL, senza un vector database separato (Pinecone, Weaviate, ecc.).

```sql
-- Crea tabella con embedding a 1536 dimensioni (OpenAI ada-002)
CREATE TABLE documenti (
    id        BIGSERIAL PRIMARY KEY,
    testo     TEXT,
    embedding vector(1536)   -- tipo aggiunto da pgvector
);

-- Inserisci embedding (generati dall'applicazione)
INSERT INTO documenti (testo, embedding)
VALUES ('La replicazione PostgreSQL usa WAL', '[0.023, -0.041, ...]');

-- Ricerca per similarità coseno (documenti più vicini semanticamente)
SELECT testo,
       1 - (embedding <=> '[0.025, -0.038, ...]') AS similarity
FROM documenti
ORDER BY embedding <=> '[0.025, -0.038, ...]'   -- <=> = cosine distance
LIMIT 10;

-- Operatori disponibili:
-- <=>  cosine distance  (1 - cos_sim, range [0,2])
-- <->  L2 / euclidean distance
-- <#>  negative inner product
```

### Indici per Scale

```sql
-- Exact search (nessun indice): preciso ma O(n) per ogni query
-- Approximate search (con indice): sublineare, accetta recall < 100%

-- IVFFlat: divide lo spazio in celle (lists), cerca nelle celle più vicine
-- Buono per dataset medio (< 1M vettori)
CREATE INDEX ON documenti USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);   -- sqrt(num_rows) è un buon punto di partenza

-- HNSW: grafo navigabile su small world — recall migliore di IVFFlat, build più lenta
-- Preferito per uso generale (PostgreSQL 16+ / pgvector 0.5+)
CREATE INDEX ON documenti USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
-- m = connessioni per nodo (trade-off recall/memoria)
-- ef_construction = dimensione beam search durante build (trade-off qualità/tempo)

-- Query con HNSW: controlla ef_search per recall vs latenza
SET hnsw.ef_search = 100;   -- default 40; aumentare per più recall
SELECT testo FROM documenti ORDER BY embedding <=> $1 LIMIT 10;
```

```python
# Esempio Python con psycopg3 + OpenAI
import psycopg, openai

def semantic_search(query: str, limit: int = 5):
    # Genera embedding della query
    response = openai.embeddings.create(
        input=query,
        model="text-embedding-ada-002"
    )
    query_embedding = response.data[0].embedding

    with psycopg.connect(dsn) as conn:
        rows = conn.execute("""
            SELECT testo, 1 - (embedding <=> %s::vector) AS similarity
            FROM documenti
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, limit)).fetchall()
    return rows
```

---

## TimescaleDB — Time Series

[TimescaleDB](https://www.timescale.com/) estende PostgreSQL per workload time-series: partiziona automaticamente per tempo (hypertable), comprime i chunk storici, e aggiunge funzioni aggregate ottimizzate.

```sql
-- Crea un'hypertable (partizionamento automatico per tempo)
CREATE TABLE metriche (
    time        TIMESTAMPTZ NOT NULL,
    host        TEXT,
    cpu_percent DOUBLE PRECISION,
    mem_bytes   BIGINT
);

SELECT create_hypertable('metriche', 'time', chunk_time_interval => INTERVAL '1 day');
-- Crea automaticamente chunk giornalieri — ogni chunk è una partizione separata

-- INSERT e SELECT funzionano come su una tabella normale
INSERT INTO metriche VALUES (NOW(), 'web-01', 73.2, 4294967296);

-- Query time-series con funzioni TimescaleDB
SELECT
    time_bucket('5 minutes', time) AS bucket,
    host,
    avg(cpu_percent) AS avg_cpu,
    max(cpu_percent) AS peak_cpu
FROM metriche
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY bucket, host
ORDER BY bucket;

-- Compressione chunk storici (riduzione 90%+ su dati monotoni/ripetitivi)
ALTER TABLE metriche SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'host',   -- un segment per host
    timescaledb.compress_orderby = 'time DESC'
);

-- Abilita retention policy: comprimi chunk > 7 giorni
SELECT add_compression_policy('metriche', INTERVAL '7 days');

-- Drop automatico chunk vecchi (retention)
SELECT add_retention_policy('metriche', INTERVAL '90 days');
```

---

## PostGIS — Dati Geospaziali

[PostGIS](https://postgis.net/) aggiunge tipi spaziali (geometry, geography) e centinaia di funzioni GIS. È lo standard de facto per spatial SQL.

```sql
CREATE EXTENSION postgis;

-- Tabella punti geografici
CREATE TABLE negozi (
    id        SERIAL PRIMARY KEY,
    nome      TEXT,
    posizione GEOGRAPHY(POINT, 4326)  -- WGS84, lat/lon
);

INSERT INTO negozi (nome, posizione)
VALUES ('Negozio Roma', ST_MakePoint(12.4964, 41.9028));

-- Trova negozi entro 5km da coordinate (Milano)
SELECT nome,
       ST_Distance(posizione, ST_MakePoint(9.1900, 45.4654)::geography) / 1000 AS km
FROM negozi
WHERE ST_DWithin(
    posizione,
    ST_MakePoint(9.1900, 45.4654)::geography,
    5000   -- 5000 metri
)
ORDER BY km;

-- Indice GiST per query spaziali (obbligatorio per performance)
CREATE INDEX idx_negozi_posizione ON negozi USING GIST (posizione);
```

---

## pg_partman — Lifecycle Partizioni

Vedi [Partitioning](../sql-avanzato/partitioning.md) per la trattazione completa.

```sql
CREATE EXTENSION pg_partman SCHEMA partman;

-- Automatizza creazione e cleanup partizioni
SELECT partman.create_parent(
    p_parent_table => 'public.log_eventi',
    p_control      => 'timestamp',
    p_type         => 'range',
    p_interval     => 'monthly',
    p_premake      => 3
);

UPDATE partman.part_config
SET retention = '12 months', retention_keep_table = false
WHERE parent_table = 'public.log_eventi';

-- Chiama da pg_cron ogni ora (vedi sotto)
SELECT partman.run_maintenance();
```

---

## pg_cron — Job Scheduling

[pg_cron](https://github.com/citusdata/pg_cron) permette di schedulare query SQL come cron job, direttamente nel database:

```ini
# postgresql.conf
shared_preload_libraries = 'pg_cron'
cron.database_name = 'postgres'   # database dove pg_cron è installato
```

```sql
CREATE EXTENSION pg_cron;

-- Schedule vacuum su tabella grande ogni domenica alle 2:00
SELECT cron.schedule(
    'weekly-vacuum-ordini',           -- nome job
    '0 2 * * 0',                      -- cron expression (domenica 02:00)
    'VACUUM ANALYZE ordini'
);

-- Manutenzione partizioni ogni ora
SELECT cron.schedule('partman-maintenance', '0 * * * *',
    'SELECT partman.run_maintenance()');

-- Delete log vecchi ogni giorno a mezzanotte
SELECT cron.schedule('cleanup-logs', '0 0 * * *',
    $$DELETE FROM application_logs WHERE created_at < NOW() - INTERVAL '30 days'$$);

-- Lista job schedulati
SELECT jobid, schedule, command, active FROM cron.job;

-- Storico esecuzioni (successi/fallimenti)
SELECT jobid, start_time, end_time, status, return_message
FROM cron.job_run_details
ORDER BY start_time DESC
LIMIT 20;

-- Rimuovi un job
SELECT cron.unschedule('weekly-vacuum-ordini');
```

---

## pg_stat_statements — Query Analytics

`pg_stat_statements` aggrega statistiche di esecuzione per ogni query unica. È il punto di partenza per qualsiasi ottimizzazione delle performance.

```ini
# postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all          # top, all, none
pg_stat_statements.max = 10000          # quante query diverse tracciare
```

```sql
CREATE EXTENSION pg_stat_statements;

-- Top 10 query per tempo totale (candidati per ottimizzazione)
SELECT
    round(total_exec_time::numeric, 2) AS total_ms,
    calls,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(stddev_exec_time::numeric, 2) AS stddev_ms,
    rows,
    substring(query, 1, 100) AS query_preview
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- Query con alta varianza (intermittenti) — spesso indici mancanti
SELECT
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(stddev_exec_time::numeric, 2) AS stddev_ms,
    round(stddev_exec_time / mean_exec_time * 100, 1) AS cv_pct,  -- coefficient of variation
    calls,
    substring(query, 1, 100) AS query
FROM pg_stat_statements
WHERE calls > 100 AND mean_exec_time > 10
ORDER BY cv_pct DESC
LIMIT 10;

-- Reset statistiche (es. dopo un deploy)
SELECT pg_stat_statements_reset();
```

---

## Utility Extensions

```sql
-- uuid-ossp: genera UUID v1/v4
CREATE EXTENSION "uuid-ossp";
SELECT uuid_generate_v4();   -- UUID casuale
-- Preferire gen_random_uuid() built-in (PostgreSQL 13+, nessuna estensione)

-- pgcrypto: hash sicuri e cifratura simmetrica
CREATE EXTENSION pgcrypto;
SELECT crypt('my_password', gen_salt('bf', 12));  -- bcrypt
SELECT gen_random_bytes(32);                       -- random bytes per token

-- hstore: key-value store in una colonna (alternativa leggera a JSONB)
CREATE EXTENSION hstore;
SELECT 'nome => Andrea, città => Roma'::hstore -> 'nome';  -- 'Andrea'

-- ltree: path gerarchici (categorie, org chart)
CREATE EXTENSION ltree;
-- Esempio: 'IT.Backend.PostgreSQL' è un nodo nella gerarchia
SELECT 'IT.Backend'::ltree @> 'IT.Backend.PostgreSQL'::ltree;  -- true (è antenato)

-- pg_trgm: trigram similarity per fuzzy search e LIKE veloce
CREATE EXTENSION pg_trgm;
SELECT similarity('postgresql', 'postresql');  -- ~0.53 (typo)
CREATE INDEX idx_nome_trgm ON prodotti USING GIN (nome gin_trgm_ops);
SELECT * FROM prodotti WHERE nome % 'postgresq';  -- fuzzy match
SELECT * FROM prodotti WHERE nome ILIKE '%postg%';  -- LIKE veloce con indice trgm
```

---

## Best Practices

- **Preferire built-in a estensioni quando possibile**: `gen_random_uuid()`, `jsonb`, `tsvector` sono built-in da PG13+. Le estensioni hanno overhead di installazione/aggiornamento
- **Verificare supporto su managed service**: non tutte le estensioni sono disponibili su RDS/Cloud SQL. Verificare prima dell'architettura
- **`shared_preload_libraries` richiede restart**: le estensioni che usano questo parametro (pg_stat_statements, pg_cron, timescaledb) richiedono restart di PostgreSQL per l'installazione iniziale
- **pgvector: scegliere le dimensioni con cura**: vettori a 1536 dim (OpenAI) pesano 6KB per riga — con 1M righe = 6GB solo per gli embedding. Considerare quantizzazione o dimensioni ridotte
- **TimescaleDB e pg_partman non coesistono**: non usare entrambi sulla stessa tabella — TimescaleDB gestisce il proprio partizionamento interno

## Troubleshooting

### Scenario 1 — CREATE EXTENSION fallisce con "extension not available"

**Sintomo:** `ERROR: could not open extension control file ".../pgvector.control": No such file or directory`

**Causa:** Il pacchetto OS dell'estensione non è installato sul server, oppure la versione di PostgreSQL non corrisponde al pacchetto.

**Soluzione:**

```bash
# Su Debian/Ubuntu — installa il pacchetto per la versione PG corretta
sudo apt install postgresql-16-pgvector

# Verifica estensioni disponibili (file .control presenti)
ls $(pg_config --sharedir)/extension/*.control

# Su Amazon RDS / Aurora: verifica le estensioni consentite nel parameter group
aws rds describe-db-parameters \
  --db-parameter-group-name my-pg-params \
  --query 'Parameters[?ParameterName==`rds.extensions`]'
```

---

### Scenario 2 — pgvector: query di similarità lente nonostante l'indice

**Sintomo:** Query `ORDER BY embedding <=> $1 LIMIT 10` impiega secondi su tabelle da centinaia di migliaia di righe, anche con indice HNSW creato.

**Causa 1:** L'indice è stato creato prima di popolare la tabella — un indice HNSW/IVFFlat costruito su poche righe non beneficia le query su milioni di righe.
**Causa 2:** `hnsw.ef_search` troppo basso, oppure l'indice IVFFlat ha `lists` sottodimensionato.

**Soluzione:**

```sql
-- Verifica che il planner usi l'indice
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM documenti ORDER BY embedding <=> $1 LIMIT 10;

-- Ricostruisci l'indice dopo il caricamento bulk
REINDEX INDEX CONCURRENTLY idx_documenti_hnsw;

-- Aumenta ef_search per migliorare recall (a scapito della latenza)
SET hnsw.ef_search = 200;

-- Verifica dimensioni embedding coerenti
SELECT MAX(vector_dims(embedding)) AS max_dim,
       MIN(vector_dims(embedding)) AS min_dim
FROM documenti;
-- max_dim e min_dim devono essere uguali
```

---

### Scenario 3 — pg_cron: i job non vengono eseguiti

**Sintomo:** Il job è presente in `cron.job` con `active = true` ma `cron.job_run_details` non registra esecuzioni.

**Causa 1:** `pg_cron` non è in `shared_preload_libraries` — PostgreSQL non ha caricato il background worker.
**Causa 2:** `cron.database_name` punta a un database diverso da quello dove è installata l'estensione.

**Soluzione:**

```bash
# Verifica che pg_cron sia caricato come background worker
psql -c "SELECT name, setting FROM pg_settings WHERE name LIKE '%preload%';"

# postgresql.conf deve contenere:
grep shared_preload_libraries /etc/postgresql/16/main/postgresql.conf
# Output atteso: shared_preload_libraries = 'pg_cron'

# Dopo la modifica: restart obbligatorio (non solo reload)
sudo systemctl restart postgresql
```

```sql
-- Verifica database configurato per pg_cron
SHOW cron.database_name;
-- Deve corrispondere al database corrente

-- Controlla gli errori nelle ultime esecuzioni
SELECT jobid, start_time, status, return_message
FROM cron.job_run_details
WHERE status = 'failed'
ORDER BY start_time DESC
LIMIT 20;
```

---

### Scenario 4 — TimescaleDB: la compressione non riduce lo spazio

**Sintomo:** `add_compression_policy` è attivo ma lo spazio su disco non diminuisce. `select_tablespace` mostra chunk non compressi.

**Causa:** La compression policy si attiva solo sui chunk che soddisfano l'intervallo minimo (`compress_after`). Chunk recenti non vengono mai compressi. Oppure la policy è definita ma il job di background TimescaleDB è disabilitato.

**Soluzione:**

```sql
-- Verifica stato dei job TimescaleDB (background workers)
SELECT job_id, proc_name, schedule_interval, next_start, last_run_status
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

-- Comprimi manualmente un chunk specifico per test
SELECT compress_chunk(c)
FROM show_chunks('metriche', older_than => INTERVAL '8 days') c;

-- Verifica ratio compressione per chunk
SELECT chunk_name,
       pg_size_pretty(before_compression_total_bytes) AS before,
       pg_size_pretty(after_compression_total_bytes)  AS after,
       compression_ratio
FROM chunk_compression_stats('metriche')
ORDER BY chunk_name;

-- Se il job è in pausa, riabilitalo
SELECT alter_job(job_id, scheduled => true)
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';
```

---

## Relazioni

??? info "Partitioning — Gestione lifecycle dati"
    pg_partman automatizza la creazione e il cleanup delle partizioni.

    **Approfondimento →** [Partitioning](../sql-avanzato/partitioning.md)

??? info "Modelli di Dati — Vector, Time-series, Spatial"
    Quando usare pgvector vs un vector database dedicato, TimescaleDB vs InfluxDB.

    **Approfondimento →** [Modelli di Dati](../fondamentali/modelli-dati.md)

## Riferimenti

- [pgvector — Vector Similarity Search](https://github.com/pgml/pgvector)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [pg_cron — Job Scheduling](https://github.com/citusdata/pg_cron)
- [pg_partman](https://github.com/pgpartman/pg_partman)
- [PGXN — PostgreSQL Extension Network](https://pgxn.org/)
