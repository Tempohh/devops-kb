---
title: "BigQuery"
slug: bigquery
category: cloud/gcp/dati
tags: [bigquery, gcp, data-warehouse, analytics, sql, serverless, bqml]
search_keywords: [BigQuery, BQ, data warehouse GCP, Google BigQuery, analytics GCP, SQL analitico, OLAP GCP, serverless analytics, slot BigQuery, slot-based pricing, on-demand pricing, partitioned table, clustered table, BigQuery partitioning, BigQuery clustering, federated query, external table, streaming inserts, BigQuery ML, BQML, Dremel, Capacitor, columnar storage, BigQuery Storage API, BigQuery Data Transfer Service, data lake GCP, query optimization BigQuery, cost control BigQuery, DML BigQuery, materialized view BigQuery, authorized view, row-level security BigQuery, column-level security, dataset BigQuery, project BigQuery, reservation BigQuery, flex slots, BigQuery BI Engine, BigQuery Omni, cross-cloud analytics, Redshift alternative, Snowflake alternative, Synapse alternative]
parent: cloud/gcp/dati/_index
related: [cloud/gcp/fondamentali/panoramica, cloud/gcp/_index]
official_docs: https://cloud.google.com/bigquery/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-26
---

# BigQuery

## Panoramica

BigQuery è il **data warehouse serverless e completamente managed** di Google Cloud Platform. Progettato per analisi su scala petabyte, separa fisicamente storage e compute — si paga per i dati scansionati (pricing on-demand) oppure per capacità riservata (slot-based pricing). Non richiede provisioning di server, gestione di cluster o tuning di indici: l'infrastruttura è interamente trasparente all'utente.

**Quando usare BigQuery:**
- Analisi su dataset grandi (GB → petabyte) con query SQL
- Data warehouse centralizzato per reportistica e BI
- Pipeline di analytics con dati provenienti da più sorgenti
- Addestramento di modelli ML direttamente sui dati (BigQuery ML)
- Federazione di query su dati eterogenei (GCS, Bigtable, Drive, database esterni)

**Quando valutare alternative:**
- Workload OLTP ad alta frequenza di scrittura → Cloud Spanner, Cloud SQL, Firestore
- Analisi su flussi in tempo reale con latenza sub-secondo → Apache Kafka + Flink, Cloud Bigtable
- Dataset piccoli (<10GB) con query frequenti → Cloud SQL con indici appropriati

---

## Concetti Chiave

### Gerarchia delle Risorse BigQuery

```
Organization / GCP Project
└── Dataset  (unità di organizzazione e controllo accessi)
    ├── Table  (dati strutturati — schema obbligatorio)
    ├── View  (query SQL salvata come tabella virtuale)
    ├── Materialized View  (cache pre-calcolata di una view)
    └── External Table  (dati su GCS, Bigtable, Drive, RDBMS)
```

- **Project**: contiene i dataset, ha il billing account associato
- **Dataset**: namespace logico per tabelle, con policy IAM proprie e regione fissa
- **Table**: dati con schema forte tipizzato; può essere nativa, partizionata, clustered o external

!!! note "Dataset = regione fissa"
    La regione di un dataset è **immutabile** dopo la creazione. Scegliere con cura (es. `europe-west8` per Milano, `EU` per multi-region Europa). Non è possibile spostare dati tra regioni con un semplice comando — serve la BigQuery Data Transfer Service o un export/import manuale.

### Architettura Interna

BigQuery è costruito su **Dremel** (il motore di query di Google) e **Capacitor** (il formato di storage colonnare proprietario):

```
Query SQL
    │
    ▼
Query Optimizer  ──►  Piano di esecuzione ottimizzato
    │
    ▼
Distributed Execution Layer  (migliaia di worker in parallelo)
    │
    ├── Shuffle Layer  (dati intermedi via Colossus)
    │
    ▼
Capacitor Storage  (formato colonnare compresso su Colossus)
```

**Perché è veloce:**
- **Storage colonnare**: legge solo le colonne presenti nella `SELECT`, non l'intera riga
- **Massima parallelizzazione**: una query può usare migliaia di worker in parallelo
- **Separazione storage/compute**: lo storage è su Colossus (GFS v2), il compute su Borg — scalano indipendentemente
- **Dremel**: architettura ad albero per aggregazioni distribuite su dataset multi-petabyte

---

## Architettura / Come Funziona

### Modelli di Pricing

BigQuery ha due modelli di pricing incompatibili tra loro a livello di progetto:

#### On-Demand (default)
Si paga per TB di dati **scansionati** dalla query:

```
Costo = TB scansionati × $6.25/TB  (marzo 2026, regione US)
        (Europe: ~$6.25–7.50/TB a seconda della regione)

Primo 1 TB/mese: gratuito
```

!!! warning "SELECT * su tabelle grandi = costo elevato"
    Con il pricing on-demand, `SELECT * FROM tabella_enorme` scansiona ogni byte di ogni colonna. Una tabella da 10TB costa $62.50 per query. Usare sempre proiezioni esplicite e filter su colonne partizionate.

#### Slot-Based (Capacity Pricing)
Si acquistano **slot** (unità di CPU virtuale) in numero fisso:

```
Slot = unità di capacità computazionale BigQuery
       1 slot ≈ 1 vCPU BigQuery (molto semplificando)

Edizioni disponibili (2024):
  Standard:  100 slot min, $0.04/slot/hour  → pay-as-you-go
  Enterprise: 100 slot min, sconto su impegno 1 anno
  Enterprise Plus: 100 slot min, sconto su impegno 3 anni
  Flex Slots: 100 slot min, impegno 60 secondi  → burst temporaneo
```

**Quando preferire Slot-Based:**
- Query frequenti e prevedibili su grandi dataset (costo fisso, non per byte)
- Ambienti con molti utenti condivisi (budget controllato)
- Workload con picchi gestibili tramite autoscaling di slot

### Tipi di Tabelle

#### Tabelle Native
Dati memorizzati in Capacitor (formato colonnare BigQuery):

```sql
-- Creare una tabella nativa con schema esplicito
CREATE TABLE `progetto.dataset.vendite` (
    id          INT64     NOT NULL,
    data_ordine DATE      NOT NULL,
    cliente_id  INT64,
    prodotto    STRING,
    importo     FLOAT64,
    paese       STRING
);
```

#### Tabelle Partizionate
Dividono i dati in segmenti fisici (partizioni) per ottimizzare query filtrate per data o valore:

```sql
-- Partizionamento per colonna DATE/TIMESTAMP (più comune)
CREATE TABLE `progetto.dataset.eventi` (
    event_id   INT64,
    ts         TIMESTAMP,
    user_id    INT64,
    event_type STRING
)
PARTITION BY DATE(ts)
OPTIONS (
    partition_expiration_days = 365,   -- elimina partizioni >1 anno
    require_partition_filter = TRUE    -- forza filtro su ts in ogni query
);

-- Partizionamento per colonna intera (integer range)
CREATE TABLE `progetto.dataset.clienti_segmentati` (
    cliente_id INT64,
    nome       STRING,
    segmento   INT64  -- valori 0-9
)
PARTITION BY RANGE_BUCKET(segmento, GENERATE_ARRAY(0, 10, 1));
```

!!! tip "require_partition_filter"
    Impostare `require_partition_filter = TRUE` sulle tabelle grandi partizionate per tempo. Questo blocca a livello di errore le query senza filtro sulla colonna di partizione, prevenendo scansioni accidentali di tutto lo storico (e costi elevati).

#### Tabelle Clustered
Ordinano fisicamente i dati all'interno di ogni partizione in base a 1-4 colonne:

```sql
-- Partizionamento + clustering combinati (pattern ottimale)
CREATE TABLE `progetto.dataset.log_accessi` (
    ts         TIMESTAMP,
    user_id    INT64,
    azione     STRING,
    ip         STRING,
    paese      STRING
)
PARTITION BY DATE(ts)
CLUSTER BY paese, user_id;

-- Query che beneficia di partition pruning + cluster pruning
SELECT user_id, COUNT(*) as azioni
FROM `progetto.dataset.log_accessi`
WHERE DATE(ts) BETWEEN '2026-01-01' AND '2026-03-01'
  AND paese = 'IT'
GROUP BY user_id;
-- BigQuery legge solo le partizioni Jan-Mar 2026 E solo i blocchi con paese='IT'
```

!!! tip "Clustering vs Indici"
    BigQuery non ha indici tradizionali — il clustering è il meccanismo equivalente. Le colonne cluster più efficaci sono quelle usate frequentemente in `WHERE`, `JOIN`, e `GROUP BY`. Mettere le colonne a bassa cardinalità prima (es. `paese` prima di `user_id`).

---

## Configurazione & Pratica

### Operazioni Base con bq CLI

```bash
# ── DATASET ──────────────────────────────────────────────────
# Creare un dataset nella regione EU
bq mk \
    --dataset \
    --location=EU \
    --description="Dati analytics produzione" \
    progetto:analytics_prod

# Listare dataset del progetto corrente
bq ls

# Mostrare info di un dataset
bq show progetto:analytics_prod

# ── TABELLE ──────────────────────────────────────────────────
# Caricare un CSV su una nuova tabella
bq load \
    --source_format=CSV \
    --skip_leading_rows=1 \
    --autodetect \
    progetto:analytics_prod.vendite \
    gs://my-bucket/vendite/*.csv

# Caricare dati Parquet (formato consigliato per import bulk)
bq load \
    --source_format=PARQUET \
    progetto:analytics_prod.eventi \
    gs://my-bucket/eventi/year=2026/*.parquet

# Esportare una tabella su GCS (formato Parquet, compresso)
bq extract \
    --destination_format=PARQUET \
    --compression=SNAPPY \
    progetto:analytics_prod.vendite \
    gs://my-bucket/export/vendite-*.parquet

# Mostrare lo schema di una tabella
bq show --schema --format=prettyjson progetto:analytics_prod.vendite

# ── QUERY ────────────────────────────────────────────────────
# Eseguire una query e stampare il risultato
bq query --use_legacy_sql=false \
    'SELECT paese, SUM(importo) as totale
     FROM `progetto.analytics_prod.vendite`
     WHERE DATE(data_ordine) >= "2026-01-01"
     GROUP BY paese
     ORDER BY totale DESC
     LIMIT 10'

# Eseguire query e salvare su tabella di destinazione
bq query \
    --use_legacy_sql=false \
    --destination_table=progetto:analytics_prod.riepilogo_mensile \
    --replace \
    'SELECT ...'
```

### Caricamento Dati: Batch vs Streaming

```python
# ── STREAMING INSERT (Python SDK) ──────────────────────────
# Per dati in tempo reale con latenza secondi (non minuti)
# Costo: $0.01/200MB inseriti (aggiuntivo rispetto allo storage)

from google.cloud import bigquery

client = bigquery.Client()
table_id = "progetto.analytics_prod.eventi_rt"

rows_to_insert = [
    {"ts": "2026-03-26T10:00:00Z", "user_id": 42, "event_type": "login"},
    {"ts": "2026-03-26T10:00:01Z", "user_id": 43, "event_type": "page_view"},
]

errors = client.insert_rows_json(table_id, rows_to_insert)
if errors:
    raise Exception(f"Errori inserimento: {errors}")

# ── BATCH LOAD (consigliato per volumi alti) ────────────────
# Gratuito — non c'è costo per caricare dati via job batch

job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.PARQUET,
    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
)

with open("local-file.parquet", "rb") as f:
    job = client.load_table_from_file(f, table_id, job_config=job_config)

job.result()  # attende completamento
print(f"Caricati {job.output_rows} righe")
```

!!! warning "Streaming Insert: limitazioni"
    Le righe inserite via streaming **non sono immediatamente visibili** per `TABLE_DATE_RANGE` e alcune operazioni DML. Il buffer di streaming ha un ritardo di disponibilità per l'export. Per pipeline ad alta frequenza preferire **Pub/Sub → Dataflow → BigQuery** o **BigQuery Storage Write API** (più efficiente e con semantica exactly-once).

### Federated Queries (External Tables)

```sql
-- Tabella esterna su GCS (Parquet — dati non replicati in BQ)
CREATE EXTERNAL TABLE `progetto.analytics_prod.raw_logs_gcs`
OPTIONS (
    format = 'PARQUET',
    uris = ['gs://my-bucket/raw-logs/year=2026/month=*/day=*/*.parquet'],
    hive_partition_uri_prefix = 'gs://my-bucket/raw-logs'
);

-- Query federata verso Cloud Spanner (senza export)
SELECT s.order_id, s.amount, c.nome
FROM EXTERNAL_QUERY(
    'projects/my-project/locations/europe-west8/instances/my-spanner/databases/mydb',
    'SELECT order_id, amount FROM orders WHERE status = ''PENDING'''
) AS s
JOIN `progetto.analytics_prod.clienti` c ON s.client_id = c.id;
```

### BigQuery ML (BQML)

BigQuery ML consente di addestrare e fare inference su modelli ML direttamente in SQL, senza estrarre i dati:

```sql
-- Creare un modello di regressione logistica per churn prediction
CREATE OR REPLACE MODEL `progetto.ml_models.churn_predictor`
OPTIONS (
    model_type = 'LOGISTIC_REG',
    input_label_cols = ['is_churned'],
    max_iterations = 20,
    l2_reg = 0.1
) AS
SELECT
    giorni_dall_ultimo_accesso,
    numero_ordini_30gg,
    importo_totale_90gg,
    piano_abbonamento,
    is_churned
FROM `progetto.analytics_prod.features_clienti`
WHERE data_partizione >= '2025-01-01';

-- Valutare il modello sul test set
SELECT *
FROM ML.EVALUATE(
    MODEL `progetto.ml_models.churn_predictor`,
    (SELECT * FROM `progetto.analytics_prod.features_clienti`
     WHERE data_partizione >= '2026-01-01')
);

-- Inference: predire churn per i clienti attivi
SELECT
    cliente_id,
    predicted_is_churned,
    predicted_is_churned_probs
FROM ML.PREDICT(
    MODEL `progetto.ml_models.churn_predictor`,
    (SELECT * FROM `progetto.analytics_prod.clienti_attivi`)
);
```

**Tipi di modelli supportati in BQML:**

| Tipo | Use Case |
|------|----------|
| `LINEAR_REG` | Regressione su valori numerici |
| `LOGISTIC_REG` | Classificazione binaria/multiclasse |
| `KMEANS` | Clustering non supervisionato |
| `MATRIX_FACTORIZATION` | Recommendation system |
| `AUTOML_CLASSIFIER` / `AUTOML_REGRESSOR` | Modelli AutoML (Vertex AI sotto) |
| `BOOSTED_TREE_CLASSIFIER` | XGBoost-based classificazione |
| `TF_MODEL` | Import di modelli TensorFlow esistenti |
| `LLMB` | Integrazione con modelli Gemini via Vertex AI |

---

## Best Practices

!!! tip "Partition Pruning: il risparmio più immediato"
    Usa sempre un filtro sulla colonna di partizionamento in ogni query. Con tabelle partizionate per data, `WHERE DATE(ts) = CURRENT_DATE()` legge una sola partizione invece di tutta la storia. Il query planner mostra i byte stimati prima dell'esecuzione — verificarli sempre.

!!! tip "Clustering per colonne ad alta selettività"
    Colonne ideali per il clustering: colonne usate spesso in `WHERE` con alta cardinalità (user_id, product_id) o bassa cardinalità ma con query filtrate (paese, categoria). Mettere sempre la colonna più filtrata per prima nell'elenco CLUSTER BY.

!!! warning "Evitare funzioni sulle colonne di partizione"
    `WHERE ts >= TIMESTAMP('2026-01-01')` è corretto.
    `WHERE CAST(ts AS DATE) >= '2026-01-01'` **disabilita il partition pruning** perché applica una funzione alla colonna prima del confronto. Usare `WHERE DATE(ts) >= '2026-01-01'` oppure comparare con TIMESTAMP direttamente.

### Ottimizzazione Query

```sql
-- ✗ MALE: SELECT * scansiona tutte le colonne
SELECT * FROM `progetto.dataset.tabella_grande`
WHERE paese = 'IT';

-- ✓ BENE: proiezione esplicita
SELECT id, nome, importo
FROM `progetto.dataset.tabella_grande`
WHERE paese = 'IT'
  AND DATE(ts) = CURRENT_DATE();  -- partition pruning

-- ✗ MALE: subquery non correlata rieseguita per ogni riga
SELECT *
FROM `progetto.dataset.ordini`
WHERE cliente_id IN (
    SELECT id FROM `progetto.dataset.clienti` WHERE piano = 'PREMIUM'
);

-- ✓ BENE: JOIN esplicito (BigQuery ottimizza meglio)
SELECT o.*
FROM `progetto.dataset.ordini` o
JOIN `progetto.dataset.clienti` c ON o.cliente_id = c.id
WHERE c.piano = 'PREMIUM';

-- ✓ Usare APPROX_COUNT_DISTINCT invece di COUNT(DISTINCT) su dataset enormi
-- COUNT(DISTINCT) richiede shuffle completo; APPROX_COUNT_DISTINCT è 99%+ accurato
SELECT
    paese,
    APPROX_COUNT_DISTINCT(user_id) AS utenti_unici_approx
FROM `progetto.dataset.eventi`
WHERE DATE(ts) = CURRENT_DATE()
GROUP BY paese;
```

### Controllo Costi

```sql
-- Stimare i byte scansionati PRIMA di eseguire (dry run)
-- Via bq CLI:
bq query --dry_run --use_legacy_sql=false \
    'SELECT paese, COUNT(*) FROM `progetto.dataset.eventi` GROUP BY paese'
-- Output: "Query successfully validated. Bytes processed: 1234567890"

-- Impostare un limite massimo di byte per query (protezione costi)
bq query \
    --maximum_bytes_billed=10737418240 \  # 10 GB max
    --use_legacy_sql=false \
    'SELECT ...'
```

```python
# Limite di byte via SDK Python
job_config = bigquery.QueryJobConfig(
    maximum_bytes_billed=10 * 1024**3  # 10 GB
)
query_job = client.query(sql, job_config=job_config)
# Se la query supera 10GB, solleva google.api_core.exceptions.BadRequest
```

### IAM e Sicurezza

```bash
# Ruoli BigQuery principali
# roles/bigquery.admin          → accesso totale
# roles/bigquery.dataEditor     → read/write su dati + crea tabelle
# roles/bigquery.dataViewer     → solo lettura dati
# roles/bigquery.jobUser        → eseguire query (+ dataViewer per leggere)
# roles/bigquery.user           → eseguire query su dataset dove si ha accesso

# Assegnare accesso a un dataset specifico (non al progetto intero)
bq add-iam-policy-binding \
    --member="user:analyst@example.com" \
    --role="roles/bigquery.dataViewer" \
    progetto:analytics_prod
```

```sql
-- Row-Level Security: policy di accesso per riga
CREATE ROW ACCESS POLICY accesso_italia
ON `progetto.analytics_prod.vendite`
GRANT TO ("group:team-italia@example.com")
FILTER USING (paese = 'IT');

-- Column-Level Security: mascherare dati sensibili
-- (richiede policy tag creati in Data Catalog)
-- Le colonne con policy tag vengono mascherate per chi non ha il ruolo 'roles/datacatalog.categoryFineGrainedReader'
```

---

## Troubleshooting

**Problema: query lenta nonostante partition filter**
```sql
-- Causa: la colonna di partizione è TIMESTAMP ma il filtro è su DATE con CAST
-- Sbagliato:
WHERE CAST(ts AS DATE) = '2026-03-26'

-- Corretto:
WHERE ts >= TIMESTAMP('2026-03-26')
  AND ts < TIMESTAMP('2026-03-27')
-- oppure (se la partizione è per DATE(ts)):
WHERE DATE(ts) = '2026-03-26'

-- Verificare il piano di esecuzione nella console BQ > Query > Execution Details
-- Cercare "Partitions read: 1 of 365" per confermare il pruning
```

**Problema: `quotaExceeded` durante streaming insert**
```bash
# Causa: superato il limite di 1GB/secondo per tabella in streaming insert
# Soluzione 1: usare BigQuery Storage Write API (limite 3GB/sec per tabella)
# Soluzione 2: sharding su più tabelle (tabella_IT, tabella_DE, ecc.)
# Soluzione 3: bufferizzare su Pub/Sub e usare Dataflow per batch da 100MB+

# Verificare i limiti attuali del progetto
gcloud services quota list --service=bigquery.googleapis.com \
    --project=my-project --filter="quotaId:StreamingInsertBytes"
```

**Problema: `Resources exceeded during query execution`**
```sql
-- Causa: query che produce risultati intermedi troppo grandi (shuffle data skew)
-- Diagnostica: nella console, Execution Details > vedere "Slot time consumed" e "Shuffle bytes"

-- Soluzione 1: aggiungere filtri per ridurre il dataset
-- Soluzione 2: spezzare la query in CTEs con tabelle intermedie
-- Soluzione 3: riscrivere JOIN con data skew usando hints
SELECT /*+ BROADCAST(small_table) */
    a.*, b.info
FROM `grossa_tabella` a
JOIN `piccola_tabella` b ON a.id = b.id;
```

**Problema: dataset non trovato cross-region**
```bash
# Causa: query su dataset in regione diversa dalla regione di processing
# BigQuery non permette JOIN tra dataset in regioni diverse nella stessa query

# Diagnostica
bq show --format=json progetto:dataset_a | grep location
bq show --format=json progetto:dataset_b | grep location

# Soluzione: copiare il dataset nella stessa regione
bq mk --dataset --location=EU progetto:dataset_b_eu
bq cp progetto:dataset_b.tabella progetto:dataset_b_eu.tabella
# oppure usare BigQuery Data Transfer Service per sync periodico
```

**Problema: costo query inaspettatamente alto**
```bash
# Causa: query senza partition filter su tabella grande partizionata
# Verifica: dry run per stimare bytes scansionati prima di eseguire
bq query --dry_run --use_legacy_sql=false 'SELECT ...'

# Verifica storico query e costi
bq query --use_legacy_sql=false \
    'SELECT job_id, total_bytes_processed, total_slot_ms, creation_time
     FROM `region-eu`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
     WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
     ORDER BY total_bytes_processed DESC
     LIMIT 20'
```

---

## Relazioni

BigQuery si integra strettamente con l'ecosistema GCP per formare pipeline dati end-to-end:

```
Sorgenti dati
├── Applicazioni  ──► Pub/Sub  ──► Dataflow  ──► BigQuery (streaming)
├── File/Batch    ──► Cloud Storage  ──► BigQuery Load Job (batch)
├── Database      ──► Datastream  ──► BigQuery (CDC replication)
└── SaaS tools    ──► BigQuery Data Transfer Service  ──► BigQuery

BigQuery
├── BI / Reporting  ──► Looker, Looker Studio, Tableau, Power BI
├── ML              ──► BigQuery ML (in-BQ) / Vertex AI (export)
├── Data Catalog    ──► Dataplex (governance, lineage, profiling)
└── Export          ──► Cloud Storage  ──► altri sistemi
```

??? info "GCP Fondamentali — IAM e Progetti"
    BigQuery eredita il modello IAM di GCP: ogni dataset appartiene a un project con billing account. I ruoli si assegnano a livello di organization, project o singolo dataset.

    **Approfondimento →** [Panoramica GCP](../fondamentali/panoramica.md)

---

## Riferimenti

- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-overview)
- [BigQuery ML Supported Models](https://cloud.google.com/bigquery/docs/bqml-introduction)
- [Storage Write API](https://cloud.google.com/bigquery/docs/write-api)
- [Row-Level Security](https://cloud.google.com/bigquery/docs/row-level-security-intro)
- [INFORMATION_SCHEMA Views](https://cloud.google.com/bigquery/docs/information-schema-intro)
- [BigQuery Reservations (Slots)](https://cloud.google.com/bigquery/docs/reservations-intro)
