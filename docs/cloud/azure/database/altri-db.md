---
title: "Azure Database — PostgreSQL, MySQL, Redis, Synapse"
slug: altri-db-azure
category: cloud
tags: [azure, postgresql, mysql, redis, synapse, mariadb, managed-database]
search_keywords: [Azure Database PostgreSQL Flexible Server, Azure Database MySQL Flexible Server, Azure Cache for Redis clustering, Azure Synapse Analytics data warehouse, PgBouncer connection pooling, pgvector vector database AI, zone-redundant HA PostgreSQL, Redis enterprise, Synapse Serverless SQL Pool, Synapse Link HTAP]
parent: cloud/azure/database/_index
related: [cloud/azure/security/key-vault, cloud/azure/networking/vnet, cloud/azure/compute/aks-containers]
official_docs: https://learn.microsoft.com/azure/postgresql/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Database — PostgreSQL, MySQL, Redis, Synapse

## Panoramica

Oltre ad Azure SQL e Cosmos DB, Azure offre servizi managed per i principali engine open-source (PostgreSQL, MySQL) e per use case specializzati come cache in-memory (Redis) e analytics su petabyte (Synapse Analytics).

## Azure Database for PostgreSQL Flexible Server

Azure Database for PostgreSQL Flexible Server è il servizio PaaS per PostgreSQL, con funzionalità avanzate di HA, replica e tuning rispetto alla versione Single Server (deprecata).

### Tier Compute

| Tier | vCPU Range | RAM | Use Case |
|---|---|---|---|
| **Burstable** | 1-2 vCPU (creditario) | 2-8 GB | Dev/test, workload intermittenti |
| **General Purpose** | 2-96 vCPU | 8-384 GB | La maggior parte dei workload produzione |
| **Memory Optimized** | 2-96 vCPU | 16-768 GB | Database in-memory, workload analytics pesanti |

```bash
RG="rg-database-prod"
LOCATION="westeurope"
PG_SERVER="pg-prod-westeurope-2026"

# Creare PostgreSQL Flexible Server con HA Zone-Redundant
az postgres flexible-server create \
  --resource-group $RG \
  --name $PG_SERVER \
  --location $LOCATION \
  --tier GeneralPurpose \
  --sku-name Standard_D4s_v3 \
  --version 16 \
  --storage-size 256 \
  --storage-auto-grow Enabled \
  --storage-auto-grow-iops-per-gb 3 \
  --backup-retention 35 \
  --geo-redundant-backup Enabled \
  --high-availability ZoneRedundant \
  --standby-zone 2 \
  --zone 1 \
  --admin-user pgadmin \
  --admin-password "$(openssl rand -base64 32)" \
  --vnet vnet-prod \
  --subnet snet-postgresql \
  --private-dns-zone "$PG_SERVER.private.postgres.database.azure.com" \
  --public-access Disabled

# Creare database
az postgres flexible-server db create \
  --resource-group $RG \
  --server-name $PG_SERVER \
  --database-name myapp-production

# Creare read replica (cross-region)
az postgres flexible-server replica create \
  --resource-group $RG \
  --replica-name pg-replica-northeurope \
  --source-server $PG_SERVER \
  --location northeurope

# Promuovere replica a standalone (durante failover manuale)
az postgres flexible-server replica stop-replication \
  --resource-group $RG \
  --name pg-replica-northeurope
```

### Configurazione PgBouncer (Connection Pooling)

PgBouncer è integrato in Azure Database for PostgreSQL Flexible Server, riducendo l'overhead di connessioni per applicazioni con molte connessioni brevi.

```bash
# Abilitare PgBouncer
az postgres flexible-server update \
  --resource-group $RG \
  --name $PG_SERVER \
  --pgbouncer-enabled true

# Connettersi tramite PgBouncer (porta 6432 invece di 5432)
# connection string: postgresql://pgadmin@pg-prod-westeurope-2026:6432/myapp-production?sslmode=require
```

### Extensions Importanti

```bash
# Listare extensions disponibili
az postgres flexible-server list-capabilities \
  --location $LOCATION \
  --query "supportedFlexibleServerVersions[].supportedVersionsToUpgrade[]" -o tsv

# Abilitare extensions (aggiungere a shared_preload_libraries)
az postgres flexible-server parameter set \
  --resource-group $RG \
  --server-name $PG_SERVER \
  --name shared_preload_libraries \
  --value "pg_stat_statements,pgaudit,pg_cron,vector"

# Connettersi e creare extension
# CREATE EXTENSION IF NOT EXISTS vector;       -- per AI/embeddings
# CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- per query analytics
# CREATE EXTENSION IF NOT EXISTS pgaudit;      -- per auditing
# CREATE EXTENSION IF NOT EXISTS pg_cron;      -- per job schedulati
```

### pgvector — Database Vettoriale per AI

pgvector trasforma PostgreSQL in un database vettoriale, permettendo similarity search per applicazioni AI/ML, RAG (Retrieval-Augmented Generation) e semantic search.

```sql
-- Abilitare extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Creare tabella con colonna vettoriale (embedding 1536 dim per OpenAI ada-002)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Creare indice HNSW per similarity search veloce
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Similarity search (cosine distance)
SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

```python
# Python: generare embedding e inserire
from openai import AzureOpenAI
import psycopg2
from psycopg2.extras import execute_values

client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_key=API_KEY)

def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(model="text-embedding-ada-002", input=text)
    return response.data[0].embedding

# Inserimento
with psycopg2.connect(PG_CONNECTION_STRING) as conn:
    with conn.cursor() as cur:
        embedding = get_embedding("Il documento da cercare")
        cur.execute(
            "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
            ("Il documento da cercare", embedding)
        )
```

### Monitoring e Troubleshooting PostgreSQL

```bash
# Abilitare query insights (pg_stat_statements)
az postgres flexible-server parameter set \
  --resource-group $RG \
  --server-name $PG_SERVER \
  --name pg_stat_statements.track \
  --value all

# Inviare log a Log Analytics
az monitor diagnostic-settings create \
  --resource-group $RG \
  --resource $(az postgres flexible-server show --resource-group $RG --name $PG_SERVER --query id -o tsv) \
  --name diag-pg-prod \
  --workspace $(az monitor log-analytics workspace show --resource-group rg-monitoring --workspace-name law-prod --query id -o tsv) \
  --logs '[{"category": "PostgreSQLLogs", "enabled": true}]' \
  --metrics '[{"category": "AllMetrics", "enabled": true}]'
```

## Azure Database for MySQL Flexible Server

MySQL Flexible Server è equivalente a PostgreSQL Flexible ma per MySQL 8.0. Funzionalità simili: HA zone-redundant, read replica, VNet integration, PgBouncer (ProxySQL), extensions.

```bash
# Creare MySQL Flexible Server
az mysql flexible-server create \
  --resource-group $RG \
  --name mysql-prod-2026 \
  --location $LOCATION \
  --tier GeneralPurpose \
  --sku-name Standard_D4s_v3 \
  --version 8.0.21 \
  --storage-size 256 \
  --storage-auto-grow Enabled \
  --backup-retention 35 \
  --geo-redundant-backup Enabled \
  --high-availability ZoneRedundant \
  --zone 1 \
  --standby-zone 2 \
  --admin-user mysqladmin \
  --admin-password "$(openssl rand -base64 32)" \
  --vnet vnet-prod \
  --subnet snet-mysql \
  --private-dns-zone "mysql-prod-2026.private.mysql.database.azure.com" \
  --public-access Disabled

# Creare database
az mysql flexible-server db create \
  --resource-group $RG \
  --server-name mysql-prod-2026 \
  --database-name mywebapp

# Read replica
az mysql flexible-server replica create \
  --resource-group $RG \
  --replica-name mysql-replica-northeurope \
  --source-server $(az mysql flexible-server show --resource-group $RG --name mysql-prod-2026 --query id -o tsv) \
  --location northeurope
```

### Confronto PostgreSQL vs MySQL vs Cosmos DB

| Caratteristica | PostgreSQL Flexible | MySQL Flexible | Cosmos DB |
|---|---|---|---|
| **Modello dati** | Relazionale (ACID) | Relazionale (ACID) | NoSQL multi-model |
| **JSON support** | Nativo (JSONB) | JSON (limitato) | Nativo (document) |
| **Extensions** | Ricche (PostGIS, pgvector) | Limitate | No (API native) |
| **Performance read** | Alta | Alta | <10ms latency globale |
| **Scale-out read** | Read replicas | Read replicas | Multi-region nativo |
| **Geolocalizzazione** | PostGIS | No | Nativo (geo-distribution) |
| **AI/ML** | pgvector | No | N/A |
| **Use case ideale** | App moderne, analytics, AI | Web app tradizionali, CMS | IoT, gaming, global app |

## Azure Cache for Redis

Azure Cache for Redis è il servizio Redis managed di Azure, fondamentale per: session cache, database query caching, real-time analytics, pub/sub, leaderboard.

### SKU e Tier

| SKU | Max Memory | Cluster | Persistence | Geo-Replication | Use Case |
|---|---|---|---|---|---|
| **Basic** | 53 GB | No | No | No | Dev/test |
| **Standard** | 53 GB | No | No | No | Produzione senza clustering |
| **Premium** | 530 GB | Sì (fino a 10 shard) | RDB + AOF | Sì (passive) | Alta disponibilità, persistence |
| **Enterprise** | 2 TB | Sì (Redis Cluster) | AOF | Sì (active) | Massime performance, 99.999% SLA |
| **Enterprise Flash** | 2 TB + NVMe | Sì | AOF | Sì (active) | Dataset molto grandi, costo ridotto |

```bash
# Creare Redis Cache Standard (2 nodi replicati)
az redis create \
  --resource-group $RG \
  --name redis-prod-2026 \
  --location $LOCATION \
  --sku Standard \
  --vm-size C3 \
  --enable-non-ssl-port false \
  --minimum-tls-version 1.2 \
  --redis-version 7

# Creare Redis Premium con clustering (4 shard)
az redis create \
  --resource-group $RG \
  --name redis-premium-prod \
  --location $LOCATION \
  --sku Premium \
  --vm-size P3 \
  --shard-count 4 \
  --enable-non-ssl-port false \
  --minimum-tls-version 1.2 \
  --subnet-id $(az network vnet subnet show --resource-group $RG --vnet-name vnet-prod --name snet-redis --query id -o tsv)

# Abilitare persistenza RDB (snapshot) su Premium
az redis update \
  --resource-group $RG \
  --name redis-premium-prod \
  --set redisConfiguration.rdb-backup-enabled=true \
  --set redisConfiguration.rdb-backup-frequency=60 \
  --set redisConfiguration.rdb-storage-connection-string="$(az storage account show-connection-string --resource-group $RG --name mystorageaccount2026 -o tsv)"

# Abilitare geo-replication (Premium)
az redis force-reboot \
  --resource-group $RG \
  --name redis-premium-prod \
  --reboot-type AllNodes

# Ottenere connection string
az redis list-keys \
  --resource-group $RG \
  --name redis-prod-2026 \
  --output json
```

### Eviction Policies

| Policy | Comportamento | Use Case |
|---|---|---|
| `noeviction` | Errore su nuovi write quando memoria piena | DB primario, dati che non si possono perdere |
| `allkeys-lru` | Rimuove chiavi meno usate recentemente (LRU) | Cache generica, qualsiasi dato |
| `volatile-lru` | LRU solo su chiavi con TTL | Cache mista (TTL = cache, no TTL = persistent) |
| `allkeys-lfu` | Rimuove chiavi meno frequenti (LFU) | Cache con accessi molto asimmetrici |
| `volatile-ttl` | Rimuove prima le chiavi con TTL più basso | Cache con priorità basata su scadenza |

```bash
# Impostare eviction policy
az redis update \
  --resource-group $RG \
  --name redis-prod-2026 \
  --set redisConfiguration.maxmemory-policy=allkeys-lru
```

### Uso da Python

```python
import redis
from azure.identity import DefaultAzureCredential
import ssl

# Connessione con TLS e autenticazione con access key
r = redis.Redis(
    host="redis-prod-2026.redis.cache.windows.net",
    port=6380,
    password="PRIMARY_KEY_FROM_AZURE",
    ssl=True,
    ssl_cert_reqs=ssl.CERT_REQUIRED,
    decode_responses=True
)

# Operazioni base
r.set("session:user123", '{"user_id": "123", "role": "admin"}', ex=3600)  # TTL 1h
session = r.get("session:user123")

# Cache con fallback al database
def get_user(user_id: str) -> dict:
    cache_key = f"user:{user_id}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss: carica da DB
    user = db.query(f"SELECT * FROM users WHERE id = '{user_id}'")
    r.setex(cache_key, 300, json.dumps(user))  # Cache 5 minuti
    return user

# Pub/Sub
publisher = redis.Redis(host="...", password="...", ssl=True)
subscriber = redis.Redis(host="...", password="...", ssl=True)

# Publisher
publisher.publish("notifications", json.dumps({"type": "order_created", "order_id": "123"}))

# Subscriber
pubsub = subscriber.pubsub()
pubsub.subscribe("notifications")
for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        print(f"Received: {data}")
```

## Azure Synapse Analytics

Azure Synapse Analytics è la piattaforma unificata per data warehouse, big data e analytics in tempo reale. Combina SQL (T-SQL), Spark e integrazione Data Lake in un unico workspace.

### Componenti Principali

| Componente | Tipo | Use Case |
|---|---|---|
| **Dedicated SQL Pool** | MPP data warehouse | Query analitiche su centinaia di TB, reporting |
| **Serverless SQL Pool** | On-demand query | Query ad hoc su data lake, discovery, ELT |
| **Apache Spark Pool** | Spark managed | ML, data transformation, Python/Scala/R |
| **Data Integration (ADF)** | ETL/ELT pipeline | Orchestrazione dati, ingest da sorgenti diverse |
| **Synapse Link** | HTAP | Query analytics su dati operativi Cosmos DB/SQL |

```bash
# Creare Synapse Workspace
az synapse workspace create \
  --resource-group $RG \
  --name synapseWorkspaceProd2026 \
  --location $LOCATION \
  --storage-account mystorageaccount2026 \
  --file-system synapse \
  --sql-admin-login-user synapsedba \
  --sql-admin-login-password "$(openssl rand -base64 32)"

# Creare Dedicated SQL Pool (data warehouse)
az synapse sql pool create \
  --resource-group $RG \
  --workspace-name synapseWorkspaceProd2026 \
  --name DWH_PROD \
  --performance-level DW1000c

# Scalare su/giù il SQL Pool (solo dedicated)
az synapse sql pool update \
  --resource-group $RG \
  --workspace-name synapseWorkspaceProd2026 \
  --name DWH_PROD \
  --performance-level DW2000c

# Sospendere SQL Pool (stop billing compute, mantieni storage)
az synapse sql pool pause \
  --resource-group $RG \
  --workspace-name synapseWorkspaceProd2026 \
  --name DWH_PROD

# Riprendere SQL Pool
az synapse sql pool resume \
  --resource-group $RG \
  --workspace-name synapseWorkspaceProd2026 \
  --name DWH_PROD

# Creare Apache Spark Pool
az synapse spark pool create \
  --resource-group $RG \
  --workspace-name synapseWorkspaceProd2026 \
  --name SparkPool01 \
  --node-size Medium \
  --min-executors 3 \
  --max-executors 10 \
  --enable-auto-scale true \
  --delay 15 \
  --spark-version 3.4
```

### Serverless SQL Pool — Query su Data Lake

Il Serverless SQL Pool permette query T-SQL direttamente su file Parquet, CSV, JSON in Azure Data Lake senza caricare dati in un database.

```sql
-- Query su file Parquet in Data Lake (OPENROWSET)
SELECT TOP 100
    year,
    month,
    region,
    SUM(sales) AS total_sales
FROM
    OPENROWSET(
        BULK 'https://mydatalake.dfs.core.windows.net/raw/sales/year=2026/**',
        FORMAT = 'PARQUET'
    ) AS [result]
GROUP BY year, month, region
ORDER BY year DESC, total_sales DESC;

-- Creare External Table per accesso strutturato
CREATE EXTERNAL DATA SOURCE DataLakeSource
WITH (
    LOCATION = 'https://mydatalake.dfs.core.windows.net/processed/'
);

CREATE EXTERNAL FILE FORMAT ParquetFormat
WITH (FORMAT_TYPE = PARQUET);

CREATE EXTERNAL TABLE dbo.SalesAnalytics (
    order_date DATE,
    customer_id VARCHAR(50),
    product_id VARCHAR(50),
    quantity INT,
    revenue DECIMAL(18,2)
)
WITH (
    DATA_SOURCE = DataLakeSource,
    LOCATION = 'sales/',
    FILE_FORMAT = ParquetFormat
);

-- Ora si può fare query come una tabella normale
SELECT customer_id, SUM(revenue) as total_revenue
FROM dbo.SalesAnalytics
WHERE order_date >= '2026-01-01'
GROUP BY customer_id
ORDER BY total_revenue DESC;
```

### Synapse Link — Cosmos DB Analytics

```python
# Query Analytics su Cosmos DB tramite Synapse Link (Spark)
df = spark.read \
    .format("cosmos.olap") \
    .option("spark.synapse.linkedService", "CosmosDBLinkedService") \
    .option("spark.cosmos.container", "orders") \
    .load()

# Analisi aggregata senza toccare il database operativo
daily_revenue = df \
    .filter(df["status"] == "completed") \
    .groupBy("date") \
    .agg({"total": "sum"}) \
    .orderBy("date")

daily_revenue.show()
```

## MariaDB (Legacy)

!!! warning "Fine Vita MariaDB"
    Azure Database for MariaDB ha raggiunto End of Life il 19 settembre 2025. Se stai usando MariaDB su Azure, migra ad Azure Database for MySQL Flexible Server (MySQL 8.0 è compatibile con la maggior parte delle applicazioni MariaDB).

```bash
# Migrazione da MariaDB a MySQL Flexible Server
# 1. Dump del database MariaDB
mysqldump -h old-mariadb.mariadb.database.azure.com \
  -u mariadbadmin@old-mariadb -p mydb > mydb_dump.sql

# 2. Creare MySQL Flexible Server di destinazione
az mysql flexible-server create \
  --resource-group $RG \
  --name mysql-migrated-prod \
  --version 8.0.21 \
  ...

# 3. Restore su MySQL
mysql -h mysql-migrated-prod.mysql.database.azure.com \
  -u mysqladmin -p mydb < mydb_dump.sql
```

## Best Practices

- Per PostgreSQL in produzione, usa sempre `ZoneRedundant` HA e `Geo-redundant-backup`
- Abilita PgBouncer su PostgreSQL per applicazioni con molte connessioni concorrenti brevi
- Su Redis, imposta sempre `maxmemory-policy` appropriata — default `noeviction` è pericoloso in cache
- Su Redis Premium, abilita persistenza RDB per recovery rapido dopo restart
- Su Synapse, usa **Serverless SQL Pool** per esplorazione e ELT ad hoc; **Dedicated Pool** solo per workload DWH persistenti (sospendilo quando non serve)
- Per pgvector, usa sempre un indice HNSW o IVFFlat per similarit search su scala

## Riferimenti

- [Documentazione PostgreSQL Flexible Server](https://learn.microsoft.com/azure/postgresql/flexible-server/)
- [pgvector Extension](https://learn.microsoft.com/azure/postgresql/flexible-server/how-to-use-pgvector)
- [Azure Cache for Redis](https://learn.microsoft.com/azure/azure-cache-for-redis/)
- [Azure Synapse Analytics](https://learn.microsoft.com/azure/synapse-analytics/)
- [MySQL Flexible Server](https://learn.microsoft.com/azure/mysql/flexible-server/)
- [Migrazione da MariaDB a MySQL](https://learn.microsoft.com/azure/mysql/migrate/whats-happening-to-mariadb)
