---
title: "AWS Database Services"
slug: database
category: cloud
tags: [aws, database, rds, aurora, dynamodb, elasticache, redshift, neptune, documentdb, memorydb, keyspaces]
search_keywords: [aws database, rds, aurora, dynamodb, elasticache, redis, memcached, redshift, neptune, documentdb, memorydb, keyspaces, timestream, qldb, database managed, nosql, sql, olap, oltp, data warehouse, graph database, in-memory]
parent: cloud/aws/_index
related: [cloud/aws/database/rds-aurora, cloud/aws/database/dynamodb, cloud/aws/database/altri-db, cloud/aws/storage/s3, cloud/aws/security/kms-secrets]
official_docs: https://aws.amazon.com/products/databases/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS Database Services

AWS offre oltre 15 servizi di database managed, ognuno ottimizzato per uno specifico modello di dati e pattern di accesso. La filosofia AWS è "use the right tool for the right job": non esiste un singolo database che sia ottimale per tutti i casi d'uso.

---

## Servizi Database AWS

<div class="grid cards" markdown>

-   **RDS e Aurora**

    ---

    Database relazionali managed. RDS supporta MySQL, PostgreSQL, Oracle, SQL Server, MariaDB, Db2. Aurora è la variante cloud-native con performance fino a 5x MySQL e 3x PostgreSQL.

    [:octicons-arrow-right-24: RDS e Aurora](rds-aurora.md)

-   **Amazon DynamoDB**

    ---

    Database NoSQL serverless chiave-valore e documento. Performance a singola cifra di ms a qualsiasi scala. Ideale per workload ad alto throughput.

    [:octicons-arrow-right-24: DynamoDB](dynamodb.md)

-   **Altri Database AWS**

    ---

    ElastiCache (Redis/Memcached), Redshift (data warehouse), Neptune (graph), DocumentDB (MongoDB-compatible), MemoryDB, Keyspaces.

    [:octicons-arrow-right-24: Altri Database](altri-db.md)

</div>

---

## Database Selection Matrix

| Use Case | Servizio Raccomandato | Alternativa |
|----------|-----------------------|-------------|
| **OLTP relazionale** | RDS MySQL/PostgreSQL | RDS MariaDB |
| **OLTP alto throughput, cloud-native** | Aurora MySQL/PostgreSQL | RDS |
| **OLTP serverless, scaling variabile** | Aurora Serverless v2 | DynamoDB |
| **NoSQL chiave-valore, milioni di req/s** | DynamoDB On-Demand | ElastiCache Redis |
| **NoSQL documento (MongoDB workloads)** | DocumentDB | DynamoDB |
| **Cache in-memory, sessioni** | ElastiCache Redis | MemoryDB |
| **Cache semplice, multi-thread** | ElastiCache Memcached | ElastiCache Redis |
| **Data Warehouse / OLAP** | Amazon Redshift | Athena (serverless) |
| **Graph database** | Amazon Neptune | N/A |
| **Wide-column NoSQL (Cassandra)** | Amazon Keyspaces | DynamoDB |
| **Time series** | Amazon Timestream | InfluxDB su EC2 |
| **Ledger immutabile** | Amazon QLDB | N/A |
| **Search full-text** | OpenSearch Service | Elasticsearch su EC2 |

---

## Concetti Fondamentali

### OLTP vs OLAP

**OLTP (Online Transaction Processing):**
- Molte transazioni piccole e frequenti
- INSERT/UPDATE/DELETE/SELECT su singole righe
- Bassa latenza (ms)
- Servizi: RDS, Aurora, DynamoDB

**OLAP (Online Analytical Processing):**
- Query complesse su grandi dataset
- Aggregazioni, join, report
- Throughput elevato, latenza accettabile (secondi/minuti)
- Servizi: Redshift, Athena

### Database Managed vs Self-Managed

I database managed AWS gestiscono automaticamente: patching OS e database engine, backup, failover Multi-AZ, scaling dello storage, monitoring, replica.

**Responsabilità cliente:** schema design, query optimization, configurazione applicativa, security group/networking.

### Multi-AZ vs Read Replicas

| | Multi-AZ | Read Replica |
|--|---------|-------------|
| Scopo | Alta disponibilità (HA) | Scalabilità letture |
| Replica | Sincrona | Asincrona |
| Endpoint | 1 (automatic failover) | Endpoint separato |
| Latenza scrittura | Leggermente più alta | Non impatta scrittore |
| Failover | Automatico (~60s) | Manuale (promuovi) |
| Accettabile per letture? | No (standby passivo) | Sì |

---

## Panoramica Prezzi

I database AWS hanno modelli di pricing diversi:

| Modello | Servizi | Descrizione |
|---------|---------|-------------|
| **Per ora di istanza + storage** | RDS, Aurora | Paghi per l'istanza attiva + GB di storage |
| **Serverless (per utilizzo)** | Aurora Serverless v2, DynamoDB On-Demand | Paghi per ACU/RCU/WCU consumati |
| **Per nodo + storage** | ElastiCache, Redshift | Paghi per il cluster + storage |
| **Serverless puro** | DynamoDB, Keyspaces Serverless | Paghi per le operazioni |

### Ottimizzazione Costi Database

- **Reserved Instances** (RDS/Aurora/ElastiCache/Redshift): 1 o 3 anni → fino al 69% di sconto
- **Snapshot S3**: molto più economico dell'istanza running per ambienti dev/test
- **Multi-AZ solo in production**: non necessario in dev/staging
- **Right-sizing**: monitorare CPU/RAM con Performance Insights e scalare le istanze
- **Aurora Serverless v2**: per ambienti con utilizzo variabile (evita pagare per istanza idle)

---

## Sicurezza Database AWS

Tutti i database managed AWS supportano:

- **Encryption at rest**: AWS KMS (Customer Managed Key o AWS Managed Key)
- **Encryption in transit**: TLS/SSL obbligatorio (configurabile)
- **IAM Authentication**: token temporanei IAM invece di username/password (RDS, Redshift, DynamoDB)
- **VPC**: isolamento di rete, Security Groups, no accesso pubblico per default (raccomandato)
- **Secrets Manager**: rotazione automatica delle password database

```bash
# Abilitare accesso tramite IAM auth per RDS
aws rds modify-db-instance \
  --db-instance-identifier my-db \
  --enable-iam-database-authentication

# Generare token IAM per connessione
TOKEN=$(aws rds generate-db-auth-token \
  --hostname my-db.xxxxx.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --region us-east-1 \
  --username iam_user)

# Connettere con psql usando il token come password
PGPASSWORD="$TOKEN" psql \
  "host=my-db.xxxxx.us-east-1.rds.amazonaws.com \
   port=5432 \
   dbname=mydb \
   user=iam_user \
   sslmode=require \
   sslrootcert=rds-ca-2019-root.pem"
```

---

## Riferimenti

- [AWS Database Products](https://aws.amazon.com/products/databases/)
- [Choosing the Right Database](https://aws.amazon.com/blogs/database/how-to-choose-the-right-database-for-your-use-case/)
- [AWS Database Blog](https://aws.amazon.com/blogs/database/)
- [RDS Pricing](https://aws.amazon.com/rds/pricing/)
- [DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
- [ElastiCache Pricing](https://aws.amazon.com/elasticache/pricing/)
