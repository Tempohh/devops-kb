---
title: "MySQL"
slug: mysql
category: databases
tags: [mysql, mariadb, innodb, replication, high-availability]
parent: databases
status: complete
difficulty: intermediate
last_updated: 2026-09-27
---

# MySQL

MySQL (e il fork community MariaDB) è, insieme a PostgreSQL, l'RDBMS open source più diffuso in produzione — la base dello stack LAMP/LEMP e di gran parte dei servizi managed cloud (RDS, Aurora MySQL, Cloud SQL). A differenza di PostgreSQL adotta un'architettura multi-storage-engine, con InnoDB come motore transazionale di fatto standard dal 2010 in avanti.

Questa sezione copre gli aspetti operativi che determinano il comportamento in produzione: architettura interna di InnoDB, replicazione, e alta disponibilità.

## Argomenti

### [Architettura e Replicazione](architettura-replicazione.md)
Storage engine InnoDB (buffer pool, redo/undo log, clustered index), replicazione basata su binary log (statement/row/mixed, GTID), semi-sync vs async, alta disponibilità con Group Replication e Galera Cluster, backup logico (mysqldump) vs fisico (Percona XtraBackup).
