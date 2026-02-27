---
title: "Azure Database"
slug: database-azure
category: cloud
tags: [azure, database, sql, cosmos-db, postgresql, mysql, redis, synapse]
search_keywords: [Azure SQL Database, Azure Cosmos DB NoSQL, PostgreSQL Flexible Server, MySQL Flexible Server, Azure Cache Redis, Azure Synapse Analytics, managed database Azure, PaaS database]
parent: cloud/azure/_index
related: [cloud/azure/compute/aks-containers, cloud/azure/security/key-vault, cloud/azure/networking/vnet]
official_docs: https://learn.microsoft.com/azure/azure-sql/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Database

Azure offre un portafoglio completo di servizi database managed, coprendo SQL relazionale, NoSQL multi-model, cache in-memory e analytics. La scelta dipende dal motore richiesto, dal livello di compatibilità con sistemi esistenti e dal modello operativo desiderato.

## Panoramica dei Servizi Database

| Servizio | Engine | Managed Level | Compatibility | Use Case |
|---|---|---|---|---|
| **Azure SQL Database** | SQL Server | Fully managed PaaS | T-SQL, SQL Server features | App cloud-native, nuovi progetti SQL |
| **SQL Managed Instance** | SQL Server | Fully managed PaaS | ~100% SQL Server | Lift & shift SQL Server on-premises |
| **SQL Server on VM** | SQL Server | IaaS (self-managed) | 100% SQL Server | Feature specifiche, SA Agent, full control |
| **Azure Cosmos DB** | Multi-model (NoSQL) | Fully managed PaaS | MongoDB, Cassandra, Gremlin, Table APIs | Global distribution, variable workload, IoT |
| **PostgreSQL Flexible** | PostgreSQL | Fully managed PaaS | PostgreSQL 14-16 | App moderne, microservizi, analytics |
| **MySQL Flexible** | MySQL | Fully managed PaaS | MySQL 8.0 | Web app, WordPress, LAMP stack |
| **Azure Cache for Redis** | Redis | Fully managed PaaS | Redis 6+ | Session cache, real-time leaderboard, pub/sub |
| **Azure Synapse Analytics** | MPP + Spark | Fully managed PaaS | T-SQL + Python/Scala | Data warehouse, big data analytics, ETL |

## Come Scegliere

```
Hai bisogno di SQL relazionale?
├── Migrazione da SQL Server on-premises con tutte le feature → SQL Managed Instance
├── Nuovo progetto o app cloud-native → Azure SQL Database
└── Feature SQL Server non disponibili in PaaS → SQL Server on VM

Hai bisogno di NoSQL?
├── Distribuzione globale, latency <10ms, multi-model → Cosmos DB
├── PostgreSQL compatibile → PostgreSQL Flexible Server
└── MySQL compatibile → MySQL Flexible Server

Hai bisogno di cache / performance estreme?
└── Redis compatible → Azure Cache for Redis

Hai bisogno di analytics/data warehouse?
└── Azure Synapse Analytics
```

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   **Azure SQL**

    ---

    Azure SQL Database, SQL Managed Instance, service tiers (DTU vs vCore), Hyperscale, Serverless, Business Critical, geo-replication, failover groups, Entra ID auth.

    [:octicons-arrow-right-24: Vai a Azure SQL](azure-sql.md)

-   **Azure Cosmos DB**

    ---

    Multi-model NoSQL con distribuzione globale, API supportate, partition key strategy, Request Units (RU), livelli di consistency, Change Feed, Free Tier.

    [:octicons-arrow-right-24: Vai a Cosmos DB](cosmos-db.md)

-   **PostgreSQL, MySQL, Redis & Synapse**

    ---

    PostgreSQL/MySQL Flexible Server con HA zone-redundant, Redis clustering e persistence, Azure Synapse per data warehouse e big data.

    [:octicons-arrow-right-24: Vai a Altri Database](altri-db.md)

</div>

## Riferimenti

- [Azure Database Documentation](https://learn.microsoft.com/azure/databases-overview)
- [Prezzi Azure SQL](https://azure.microsoft.com/pricing/details/azure-sql-database/)
- [Prezzi Cosmos DB](https://azure.microsoft.com/pricing/details/cosmos-db/)
