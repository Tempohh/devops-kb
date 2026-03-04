---
title: "Altri Database AWS — ElastiCache, Redshift, Neptune, DocumentDB e altri"
slug: altri-db
category: cloud
tags: [aws, elasticache, redis, memcached, redshift, neptune, documentdb, memorydb, keyspaces, timestream, qldb, opensearch, data-warehouse, graph-database, in-memory-cache]
search_keywords: [elasticache, redis, memcached, cache aside, write through, write behind, cluster mode, redshift, spectrum, redshift serverless, ra3, concurrency scaling, materialized views, neptune, gremlin, sparql, opencypher, graph analytics, documentdb, mongodb compatible, memorydb for redis, keyspaces, cassandra, cql, timestream, qldb, database selection, cache patterns, redis auth, elasticache serverless]
parent: cloud/aws/database/_index
related: [cloud/aws/database/rds-aurora, cloud/aws/database/dynamodb, cloud/aws/security/kms-secrets, cloud/aws/messaging/sqs-sns]
official_docs: https://aws.amazon.com/products/databases/
status: complete
difficulty: intermediate
last_updated: 2026-03-03
---

# Altri Database AWS — ElastiCache, Redshift, Neptune, DocumentDB e altri

## Panoramica

Questo documento copre l'ampio portfolio di database specializzati AWS: cache in-memory (ElastiCache), data warehouse (Redshift), graph database (Neptune), document store MongoDB-compatible (DocumentDB), cache con durabilità (MemoryDB), wide-column NoSQL (Keyspaces) e altri servizi di specializzazione.

---

## Amazon ElastiCache

ElastiCache è il servizio di cache in-memory managed di AWS. Supporta due engine: **Redis** e **Memcached**.

### Redis vs Memcached — Confronto

| Feature | Redis | Memcached |
|---------|-------|-----------|
| Strutture dati | String, Hash, List, Set, Sorted Set, Stream, HyperLogLog | Solo String |
| Persistenza | Sì (RDB + AOF) | No |
| Replication | Sì (Primary + Replicas) | No |
| Clustering | Sì (Cluster Mode) | Sì (Sharding nativo) |
| Pub/Sub | Sì | No |
| Scripting Lua | Sì | No |
| Backup | Sì (snapshot su S3) | No |
| Multi-thread | No (single-thread per operazione) | Sì |
| Failover automatico | Sì | No |
| **Raccomandazione** | Quasi sempre | Solo se multi-thread è critico |

!!! tip "Scegliere quasi sempre Redis"
    A meno che non si abbia uno specifico bisogno di multi-threading puro per CPU-bound cache operations, Redis è la scelta corretta per la sua ricchezza di funzionalità.

### Redis — Cluster Mode Disabled vs Enabled

**Cluster Mode Disabled:**
- 1 shard: 1 Primary + fino a 5 Replicas
- Massimo ~500 GB per nodo (dipende dal tipo di istanza)
- Singola partition key space
- Multi-AZ con failover automatico

**Cluster Mode Enabled:**
- Fino a 500 shard (sharding automatico)
- Fino a 6.7 TB di storage aggregato (esempio: 500 shard × ~13 GB r6g.large)
- Scaling orizzontale: aggiungere/rimuovere shard online
- Richiede supporto nel client per il routing (Cluster-aware client)

```bash
# Creare un cluster Redis con Cluster Mode Enabled
aws elasticache create-replication-group \
  --replication-group-id my-redis-cluster \
  --description "Redis cluster for session store" \
  --num-node-groups 3 \
  --replicas-per-node-group 2 \
  --cache-node-type cache.r6g.large \
  --engine redis \
  --engine-version "7.1" \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --auth-token "MySecureRedisPassword123!" \
  --cache-parameter-group-name default.redis7.cluster.on \
  --security-group-ids sg-1234567890 \
  --cache-subnet-group-name my-cache-subnet-group

# Creare cluster Redis semplice (Cluster Mode Disabled)
aws elasticache create-replication-group \
  --replication-group-id my-redis-simple \
  --description "Redis single shard" \
  --num-cache-clusters 2 \
  --cache-node-type cache.r6g.large \
  --engine redis \
  --automatic-failover-enabled \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --auth-token "MySecureRedisPassword123!"
```

### ElastiCache Serverless

ElastiCache Serverless scala automaticamente in base al traffico per Redis e Memcached. Nessun provisioning di nodi o shard.

```bash
# Creare cache serverless Redis
aws elasticache create-serverless-cache \
  --serverless-cache-name my-serverless-redis \
  --engine redis \
  --cache-usage-limits '{
    "DataStorage": {"Maximum": 100, "Unit": "GB"},
    "ECPUPerSecond": {"Maximum": 5000}
  }' \
  --security-group-ids sg-1234567890 \
  --subnet-ids subnet-1234 subnet-5678 \
  --kms-key-id alias/my-elasticache-key
```

### Cache Patterns

**Cache-Aside (Lazy Loading) — il più comune:**
1. L'applicazione cerca in cache
2. Cache miss → legge dal database → scrive in cache
3. La cache contiene solo i dati richiesti (no dati inutilizzati)
4. Problema: cache stampede (molte richieste simultane sulla stessa key mancante)

```python
import redis
import json

r = redis.Redis(host='my-redis.xxx.cache.amazonaws.com', port=6379, ssl=True)

def get_user(user_id: str) -> dict:
    cache_key = f"user:{user_id}"

    # Cerca in cache
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss: legge dal database
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)

    # Scrive in cache con TTL di 5 minuti
    r.setex(cache_key, 300, json.dumps(user))

    return user
```

**Write-Through:**
1. Ogni write va sia nel database che in cache
2. Cache sempre aggiornata, no cache miss per dati recenti
3. Problema: scrive dati in cache che potrebbero non essere mai letti

```python
def update_user(user_id: str, data: dict) -> dict:
    # Scrive nel database
    db.execute("UPDATE users SET ... WHERE id = %s", user_id, data)

    # Aggiorna in cache simultaneamente
    cache_key = f"user:{user_id}"
    user = {**get_user_from_db(user_id), **data}
    r.setex(cache_key, 3600, json.dumps(user))

    return user
```

**Write-Behind (Write-Back):**
1. Scrive prima in cache, poi in batch nel database
2. Performance write molto alta
3. Rischio: dati persi se la cache va giù prima della scrittura nel DB
4. Complessità: richiede gestione della coda di scrittura

**Session Store con Redis:**
```python
import uuid

def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    session_data = {
        'userId': user_id,
        'createdAt': time.time(),
        'permissions': ['read', 'write']
    }
    # Sessione scade dopo 24 ore
    r.setex(f"session:{session_id}", 86400, json.dumps(session_data))
    return session_id

def get_session(session_id: str) -> dict | None:
    data = r.get(f"session:{session_id}")
    if data:
        # Rinnovare TTL ad ogni accesso (sliding window)
        r.expire(f"session:{session_id}", 86400)
        return json.loads(data)
    return None
```

### Redis — Use Case Avanzati

**Leaderboard con Sorted Sets:**
```python
# Aggiungere o aggiornare score
r.zadd('game:leaderboard', {'player123': 9500, 'player456': 12000, 'player789': 8750})

# Top 10 giocatori (ordine decrescente)
top10 = r.zrevrange('game:leaderboard', 0, 9, withscores=True)

# Rank di un giocatore specifico
rank = r.zrevrank('game:leaderboard', 'player123')
score = r.zscore('game:leaderboard', 'player123')
```

**Rate Limiting:**
```python
def is_rate_limited(user_id: str, limit: int = 100, window: int = 60) -> bool:
    key = f"rate_limit:{user_id}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    count, _ = pipe.execute()
    return count > limit
```

---

## Amazon Redshift

Redshift è il data warehouse managed di AWS, basato su PostgreSQL modificato con un'architettura colonnare ottimizzata per analytics e OLAP (Online Analytical Processing).

### Architettura Cluster

- **Leader Node:** riceve le query, pianifica l'esecuzione, aggrega i risultati
- **Compute Nodes:** eseguono le operazioni effettive (query execution, storage)
  - **DC2** (Dense Compute): SSD locale, fino a 2.56 TB per nodo, storage locale
  - **RA3** (Redshift Managed Storage): storage su S3 (Redshift Managed Storage), compute/storage separati

**Nodi RA3 — Separazione Compute/Storage:**
- I dati sono archiviati su S3 (managed storage), non sul disco del nodo
- Possibile scalare compute e storage indipendentemente
- Hot data (accessata di recente) viene automaticamente cachata sui nodi per performance

```bash
# Creare un cluster Redshift RA3
aws redshift create-cluster \
  --cluster-identifier my-redshift-cluster \
  --cluster-type multi-node \
  --node-type ra3.xlplus \
  --number-of-nodes 2 \
  --master-username admin \
  --master-user-password MySecurePassword123! \
  --db-name analytics \
  --vpc-security-group-ids sg-1234567890 \
  --cluster-subnet-group-name my-redshift-subnet \
  --encrypted \
  --kms-key-id alias/my-redshift-key \
  --enable-logging \
  --logging-properties BucketName=my-redshift-logs,S3KeyPrefix=audit/
```

### Redshift Serverless

Redshift Serverless scala automaticamente la capacità di compute in base alle query. Nessun cluster da gestire.

```bash
# Creare Redshift Serverless namespace e workgroup
aws redshift-serverless create-namespace \
  --namespace-name my-namespace \
  --admin-username admin \
  --admin-user-password MySecurePassword123! \
  --db-name analytics \
  --kms-key-id alias/my-redshift-key

aws redshift-serverless create-workgroup \
  --workgroup-name my-workgroup \
  --namespace-name my-namespace \
  --base-capacity 32 \
  --max-capacity 512 \
  --security-group-ids sg-1234567890 \
  --subnet-ids subnet-1234 subnet-5678
```

### Redshift Spectrum

Spectrum permette di eseguire query SQL direttamente su dati S3 (Parquet, ORC, CSV, JSON) senza caricarli nel cluster. Essenziale per architetture data lake ibride.

```sql
-- Creare un external schema che punta a Glue Data Catalog
CREATE EXTERNAL SCHEMA spectrum_schema
FROM DATA CATALOG
DATABASE 'my_glue_database'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftSpectrumRole'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

-- Query su dati S3 tramite Spectrum
SELECT
  s.order_date,
  s.product_category,
  SUM(s.revenue) as total_revenue
FROM spectrum_schema.s3_orders s
JOIN redshift_internal.customers c ON s.customer_id = c.id
WHERE s.order_date >= '2024-01-01'
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
```

### COPY Command — Caricamento Dati

Il modo più efficiente per caricare dati in Redshift è il comando COPY (caricamento parallelo da S3).

```sql
-- COPY da S3 (Parquet — il formato più efficiente)
COPY sales
FROM 's3://my-data-lake/sales/year=2024/'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftS3Role'
FORMAT AS PARQUET;

-- COPY da S3 (CSV con header)
COPY products
FROM 's3://my-bucket/products.csv'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftS3Role'
CSV
IGNOREHEADER 1
DATEFORMAT 'YYYY-MM-DD'
TIMEFORMAT 'YYYY-MM-DD HH:MI:SS'
NULL AS 'NULL';

-- COPY da DynamoDB
COPY orders
FROM 'dynamodb://Orders'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftRole'
READRATIO 50;  -- usa max 50% del throughput DynamoDB
```

### Concurrency Scaling e Materialized Views

**Concurrency Scaling:** aggiunge automaticamente capacità di compute burst per gestire picchi di query concorrenti.

```sql
-- Abilitare Concurrency Scaling per workgroup specifici
ALTER WORKLOAD 'analytics_team'
SET concurrency_scaling = auto;
```

**Materialized Views:** pre-calcola e materializza il risultato di query complesse per accesso rapido.

```sql
-- Creare Materialized View
CREATE MATERIALIZED VIEW daily_sales_summary AS
SELECT
  DATE_TRUNC('day', order_date) as day,
  product_id,
  SUM(quantity) as total_qty,
  SUM(revenue) as total_revenue,
  COUNT(DISTINCT customer_id) as unique_customers
FROM orders
GROUP BY 1, 2;

-- Refresh della Materialized View
REFRESH MATERIALIZED VIEW daily_sales_summary;

-- Query sulla Materialized View (molto più veloce)
SELECT * FROM daily_sales_summary WHERE day = CURRENT_DATE - 1;
```

### Redshift ML

Permette di creare e fare inference di modelli ML direttamente con SQL, usando SageMaker Autopilot in background.

```sql
-- Creare un modello ML con SQL
CREATE MODEL customer_churn_model
FROM (
  SELECT age, tenure, monthly_charges, total_charges, churn
  FROM customers
  WHERE churn IS NOT NULL
)
TARGET churn
FUNCTION predict_churn
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftMLRole'
SETTINGS (S3_BUCKET 'my-redshift-ml-bucket');

-- Usare il modello per prediction
SELECT customer_id, predict_churn(age, tenure, monthly_charges, total_charges) as churn_probability
FROM customers
WHERE churn IS NULL;
```

---

## Amazon Neptune

Neptune è il graph database managed di AWS, ottimizzato per archiviare e navigare relazioni altamente connesse.

### Modelli di Query Supportati

| Query Language | Standard | Use Case |
|---------------|---------|---------|
| **Gremlin** | Apache TinkerPop | Property Graph, traversal-oriented |
| **SPARQL** | W3C | RDF (Resource Description Framework), linked data |
| **openCypher** | Neo4j | Property Graph, SQL-like syntax, più leggibile |

**Property Graph (Gremlin/openCypher):** nodi con proprietà + edges con proprietà. Il modello più comune.

**RDF (SPARQL):** soggetto-predicato-oggetto, standard W3C, per linked data e knowledge graphs governativi.

### Architettura

- Storage condiviso simile ad Aurora: 6 copie su 3 AZ, crescita automatica fino a 64 TB
- Primary + fino a 15 Read Replicas
- Failover automatico < 30s

```python
from gremlin_python.driver import client, serializer

# Connettere a Neptune via Gremlin
neptune_client = client.Client(
    'wss://my-neptune.cluster.region.amazonaws.com:8182/gremlin',
    'g',
    message_serializer=serializer.GraphSONSerializersV2d0()
)

# Query Gremlin — trovare amici di amici di un utente
query = """
g.V().has('User', 'userId', 'user123')
  .out('FOLLOWS')
  .out('FOLLOWS')
  .has('userId', neq('user123'))
  .dedup()
  .valueMap('name', 'userId')
"""

result = neptune_client.submit(query).all().result()
```

```cypher
// openCypher — rilevamento frodi
// Trova account che condividono lo stesso indirizzo e hanno transazioni sospette
MATCH (a1:Account)-[:HAS_ADDRESS]->(addr:Address)<-[:HAS_ADDRESS]-(a2:Account)
WHERE a1 <> a2
  AND a1.riskScore > 7
MATCH (a1)-[:MADE_TRANSACTION {amount_over: 10000}]->(merchant:Merchant)
RETURN a1.accountId, a2.accountId, addr.address, merchant.name
```

### Neptune Analytics

Neptune Analytics è un motore in-memory per analytics su grafi (fino a 30 milioni di nodi), con algoritmi graph built-in (PageRank, shortest path, community detection).

```bash
# Creare un Neptune Analytics graph
aws neptune-graph create-graph \
  --graph-name fraud-analysis \
  --provisioned-memory 16 \
  --vector-search-configuration dimension=128 \
  --public-connectivity false

# Caricare dati da S3
aws neptune-graph create-graph-using-import-task \
  --graph-id graph-id \
  --source "s3://my-bucket/graph-data/" \
  --role-arn arn:aws:iam::123456789012:role/NeptuneRole \
  --import-options '{"neptune": {"preserveDefaultVertexLabels": true}}'
```

### Use Case Neptune

- **Fraud Detection:** identificare anelli di frode, account che condividono informazioni
- **Knowledge Graph:** relazioni tra entità in testi, motori di ricerca avanzati
- **Social Network:** feed personalizzato, raccomandazione amici
- **Recommendation Engine:** "utenti simili a te hanno acquistato..."
- **IT Asset Management:** grafo delle dipendenze tra infrastrutture
- **Identity Graph:** collegare identità diverse (email, cookie, device) allo stesso utente

---

## Amazon DocumentDB

DocumentDB è un database di documenti JSON managed, compatibile con l'API MongoDB. Non è MongoDB: è una reimplementazione parziale dell'API MongoDB da zero da parte di AWS.

!!! warning "DocumentDB NON è MongoDB"
    DocumentDB emula il driver wire protocol di MongoDB 4.0/5.0 ma non è 100% compatibile. Alcune feature di MongoDB non sono supportate. Verificare la compatibility matrix prima della migrazione.

### Architettura

- Simile ad Aurora: cluster volume condiviso, 6 copie su 3 AZ, crescita automatica fino a 64 TB
- 1 Primary + fino a 15 Read Replicas
- Failover automatico

```bash
# Creare un cluster DocumentDB
aws docdb create-db-cluster \
  --db-cluster-identifier my-docdb-cluster \
  --engine docdb \
  --master-username admin \
  --master-user-password MySecurePassword123! \
  --vpc-security-group-ids sg-1234567890 \
  --db-subnet-group-name my-docdb-subnet \
  --storage-encrypted \
  --kms-key-id alias/my-docdb-key

# Creare istanza nel cluster
aws docdb create-db-instance \
  --db-instance-identifier my-docdb-writer \
  --db-instance-class db.r6g.large \
  --engine docdb \
  --db-cluster-identifier my-docdb-cluster
```

```python
from pymongo import MongoClient

# Connettere a DocumentDB (richiede TLS + bundle CA)
client = MongoClient(
    'mongodb://admin:password@my-docdb-cluster.cluster-xxxxxxx.us-east-1.docdb.amazonaws.com:27017',
    tls=True,
    tlsCAFile='global-bundle.pem',
    retryWrites=False  # DocumentDB non supporta retryWrites
)

db = client['myapp']
collection = db['products']

# Insert
collection.insert_one({'name': 'Widget', 'category': 'electronics', 'price': 29.99})

# Find con query
results = collection.find({'category': 'electronics', 'price': {'$lt': 50}})

# Aggregation pipeline
pipeline = [
    {'$match': {'category': 'electronics'}},
    {'$group': {'_id': '$brand', 'total': {'$sum': '$price'}, 'count': {'$sum': 1}}},
    {'$sort': {'total': -1}}
]
results = collection.aggregate(pipeline)
```

---

## Amazon MemoryDB for Redis

MemoryDB è un database Redis fully managed con **durabilità** (a differenza di ElastiCache che è cache). Usa un transaction log Multi-AZ per garantire che i dati non vengano mai persi.

**Differenza fondamentale con ElastiCache Redis:**
- ElastiCache Redis: cache, può perdere dati in caso di failover (a seconda della config)
- MemoryDB: database primary, durabilità garantita via transaction log, RPO quasi zero

**Caratteristiche:**
- Compatibile con Redis API (stessi comandi, stessi client)
- Multi-AZ con transaction log su ogni write
- Snapshot su S3 per backup
- Cluster Mode per sharding

**Use case:** applicazioni che usano Redis come database primario (non solo cache), microservizi che usano Redis per state, leaderboard con garanzia di durabilità.

```bash
# Creare cluster MemoryDB
aws memorydb create-cluster \
  --cluster-name my-memorydb \
  --node-type db.r6g.large \
  --acl-name open-access \
  --subnet-group-name my-memorydb-subnet \
  --security-group-ids sg-1234567890 \
  --num-shards 2 \
  --num-replicas-per-shard 1 \
  --tls-enabled \
  --snapshot-retention-limit 7 \
  --kms-key-id alias/my-memorydb-key
```

---

## Amazon Keyspaces (for Apache Cassandra)

Keyspaces è il servizio managed per Apache Cassandra su AWS. Compatibile con il driver Cassandra e CQL (Cassandra Query Language).

**Caratteristiche:**
- Serverless: scala automaticamente in base al traffico
- Compatibile con CQL e driver Cassandra esistenti
- Replica multi-AZ automatica (3 AZ)
- Encryption, IAM auth, VPC support

**Use case:** migrazione di workload Cassandra esistenti, wide-column NoSQL per time-series e IoT.

```python
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from ssl import SSLContext, PROTOCOL_TLSv1_2, CERT_REQUIRED

ssl_context = SSLContext(PROTOCOL_TLSv1_2)
ssl_context.verify_mode = CERT_REQUIRED
ssl_context.load_verify_locations('AmazonRootCA1.pem')

auth_provider = PlainTextAuthProvider(
    username='my-iam-user-at-12345678901',  # formato speciale per Keyspaces
    password='service_specific_password'
)

cluster = Cluster(
    ['cassandra.us-east-1.amazonaws.com'],
    ssl_context=ssl_context,
    auth_provider=auth_provider,
    port=9142
)
session = cluster.connect()

# CQL
session.execute("""
    CREATE TABLE IF NOT EXISTS my_keyspace.sensors (
        device_id text,
        timestamp timestamp,
        temperature decimal,
        humidity decimal,
        PRIMARY KEY (device_id, timestamp)
    ) WITH CLUSTERING ORDER BY (timestamp DESC)
""")

session.execute("""
    INSERT INTO my_keyspace.sensors (device_id, timestamp, temperature, humidity)
    VALUES (%s, %s, %s, %s)
""", ('sensor-001', datetime.now(), 23.5, 65.0))
```

---

## Database Selection Matrix (Completa)

| Use Case | Servizio | Perché |
|----------|---------|--------|
| **OLTP relazionale** | RDS MySQL/PostgreSQL | SQL standard, ACID completo |
| **OLTP alto throughput cloud-native** | Aurora MySQL/PostgreSQL | 5x MySQL, failover < 30s |
| **OLTP serverless variabile** | Aurora Serverless v2 | Auto-scale 0.5-256 ACU |
| **NoSQL chiave-valore/documento** | DynamoDB | Serverless, single-digit ms, infinite scale |
| **Cache, sessioni, pub/sub** | ElastiCache Redis | Sub-ms latency, strutture dati avanzate |
| **Cache semplice e veloce** | ElastiCache Memcached | Multi-thread, semplice |
| **Redis come database primario** | MemoryDB for Redis | Durabilità + Redis API |
| **Data Warehouse / OLAP** | Amazon Redshift | Colonnare, petabyte scale, SQL |
| **Analytics serverless** | Redshift Serverless | No cluster management |
| **Data lake queries** | Athena | SQL su S3, serverless, pay-per-query |
| **Graph database** | Amazon Neptune | Property graph o RDF |
| **MongoDB workloads** | DocumentDB | MongoDB-compatible API |
| **Apache Cassandra workloads** | Amazon Keyspaces | CQL-compatible, serverless |
| **Time series (IoT, metriche)** | Amazon Timestream | Time series ottimizzato |
| **Ledger immutabile** | Amazon QLDB | Cryptographically verifiable |
| **Search full-text** | OpenSearch Service | Elasticsearch/OpenSearch managed |

---

## Amazon Timestream

Database specializzato per dati time-series (IoT, metriche, telemetria). Ordini di grandezza più veloce e meno costoso di un database relazionale per time-series.

**Caratteristiche:**
- Scritture: scala automaticamente a miliardi di eventi/giorno
- Query: SQL-like con funzioni time-series built-in
- Storage tiering: memoria (query veloci) → magnetico (archivio economico)
- Integrazione nativa: Kinesis Data Streams, IoT Core, Lambda, Grafana

```python
import boto3
import time

timestream = boto3.client('timestream-write', region_name='us-east-1')

# Scrivere metriche IoT
timestream.write_records(
    DatabaseName='iot-metrics',
    TableName='sensor-data',
    Records=[{
        'Dimensions': [
            {'Name': 'device_id', 'Value': 'sensor-001'},
            {'Name': 'location', 'Value': 'warehouse-A'},
        ],
        'MeasureName': 'temperature',
        'MeasureValue': '23.5',
        'MeasureValueType': 'DOUBLE',
        'Time': str(int(time.time() * 1000)),
        'TimeUnit': 'MILLISECONDS'
    }]
)

# Query con Timestream Query Engine
query_client = boto3.client('timestream-query')
result = query_client.query(
    QueryString="""
    SELECT device_id,
           BIN(time, 5m) as bin_time,
           AVG(measure_value::double) as avg_temp,
           MAX(measure_value::double) as max_temp
    FROM "iot-metrics"."sensor-data"
    WHERE measure_name = 'temperature'
      AND time BETWEEN ago(1h) AND now()
    GROUP BY device_id, BIN(time, 5m)
    ORDER BY bin_time DESC
    """
)
```

---

## Amazon QLDB

QLDB (Quantum Ledger Database) è un database ledger completamente managed, immutabile e crittograficamente verificabile. Ogni modifica è registrata in un journal append-only con digest SHA-256.

**Caratteristiche:**
- Tutte le modifiche sono verificabili crittograficamente (impossibile alterare la storia)
- SQL-like query language (PartiQL)
- Serverless
- Export delle transazioni verso Kinesis Data Streams

**Use case:** sistemi di registrazione che richiedono audit trail immutabile e verificabile (finanza, supply chain, sanità, voto elettronico).

!!! note "QLDB vs Blockchain"
    QLDB è centralizzato e gestito da AWS. È appropriato quando un singolo ente fidato gestisce il ledger. Per sistemi decentralizzati con più parti non fidate, Amazon Managed Blockchain (Hyperledger Fabric) è l'alternativa.

---

## Best Practices

### ElastiCache

1. **Usare Redis** in quasi tutti i casi (ricco di feature vs Memcached)
2. **TTL sempre** — evitare cache stale a lunga vita
3. **Eviction policy appropriata:** `allkeys-lru` per cache generale, `volatile-lru` se si mixano dati con e senza TTL
4. **Cluster Mode** per carichi elevati che superano la capacità di un singolo nodo
5. **Redis AUTH + TLS** sempre in produzione

### Redshift

1. **RA3** per nuovi cluster (compute/storage separati, più flessibile)
2. **Distribution key e sort key** corrette per le query più frequenti
3. **WLM (Workload Management)** per separare query heavy da quelle leggere
4. **VACUUM e ANALYZE** regolari per performance ottimali
5. **Spectrum** per query rare su dati storici (evita di caricarli nel cluster)

### Selezione Database

1. Mai usare RDS/Aurora per analytics di grandi volumi → Redshift/Athena
2. Mai usare Redshift per OLTP → RDS/Aurora
3. Non usare DynamoDB per query relazionali complesse
4. ElastiCache davanti a qualsiasi database per hot data

---

## Troubleshooting

### ElastiCache: Alta Latenza

```bash
# Verificare metriche Redis in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/ElastiCache \
  --metric-name CacheHitRate \
  --dimensions Name=CacheClusterId,Value=my-redis-cluster \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-16T00:00:00Z \
  --period 3600 \
  --statistics Average
```

Cause comuni:
- Hot keys (un singolo key acceduto da tutti i client) — soluzioni: client-side caching, sharding della key
- Connessioni esaurite — aumentare `maxclients` o usare connection pooling
- Memory piena + eviction → aumentare dimensione nodo o aggiungere shard

### Redshift: Query Lente

```sql
-- Identificare query lente
SELECT query, duration, userid, starttime
FROM stl_query
WHERE duration > 60000000  -- > 60 secondi
ORDER BY duration DESC
LIMIT 20;

-- Analizzare un piano di esecuzione
EXPLAIN SELECT * FROM large_table WHERE category = 'A';

-- Verificare la distribuzione dei dati (skew)
SELECT slice, COUNT(*)
FROM stv_blocklist
WHERE tbl = (SELECT id FROM stv_tbl_perm WHERE name = 'my_table')
GROUP BY slice
ORDER BY slice;
```

---

## Relazioni

??? info "DynamoDB — NoSQL Scalabile"
    Per workload NoSQL chiave-valore o documento con requisiti di scaling estremo, DynamoDB è la soluzione serverless nativa.

    **Approfondimento completo →** [DynamoDB](dynamodb.md)

??? info "RDS/Aurora — Database Relazionali"
    Per OLTP relazionale managed, RDS e Aurora sono la scelta principale.

    **Approfondimento completo →** [RDS e Aurora](rds-aurora.md)

??? info "Kinesis — Streaming verso Redshift"
    Kinesis Firehose può consegnare dati in streaming direttamente a Redshift.

    **Approfondimento completo →** [EventBridge e Kinesis](../messaging/eventbridge-kinesis.md)

---

## Riferimenti

- [ElastiCache Documentation](https://docs.aws.amazon.com/elasticache/)
- [Redis Documentation](https://redis.io/documentation)
- [Redshift User Guide](https://docs.aws.amazon.com/redshift/latest/dg/)
- [Neptune User Guide](https://docs.aws.amazon.com/neptune/latest/userguide/)
- [DocumentDB User Guide](https://docs.aws.amazon.com/documentdb/)
- [MemoryDB Documentation](https://docs.aws.amazon.com/memorydb/)
- [Keyspaces Documentation](https://docs.aws.amazon.com/keyspaces/)
- [Timestream Documentation](https://docs.aws.amazon.com/timestream/)
- [QLDB Documentation](https://docs.aws.amazon.com/qldb/)
- [AWS Database Blog](https://aws.amazon.com/blogs/database/)
