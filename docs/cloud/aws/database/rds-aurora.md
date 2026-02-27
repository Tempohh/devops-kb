---
title: "RDS e Aurora — Database Relazionali Managed"
slug: rds-aurora
category: cloud
tags: [aws, rds, aurora, mysql, postgresql, database, multi-az, read-replica, rds-proxy, aurora-serverless, aurora-global, blue-green, pitr, performance-insights]
search_keywords: [rds, relational database service, aurora, multi-az, read replica, rds proxy, aurora serverless v2, aurora global database, aurora backtrack, aurora cluster, parameter group, option group, pitr point in time recovery, enhanced monitoring, performance insights, iam authentication, blue green deployment, aurora io optimized, db2, mariadb, oracle, sql server, failover, automated backup, manual snapshot, reserved instances]
parent: cloud/aws/database/_index
related: [cloud/aws/database/dynamodb, cloud/aws/database/altri-db, cloud/aws/security/kms-secrets, cloud/aws/monitoring/cloudwatch]
official_docs: https://docs.aws.amazon.com/rds/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# RDS e Aurora — Database Relazionali Managed

## Panoramica

Amazon Relational Database Service (RDS) è il servizio managed per database relazionali su AWS. Gestisce automaticamente: provisioning hardware, patching OS e database engine, backup automatici, monitoraggio, failover Multi-AZ e scaling dello storage. Il team operativo si concentra sullo schema e sull'applicazione, non sull'infrastruttura database.

**Amazon Aurora** è la variante cloud-native sviluppata da AWS, compatibile con MySQL e PostgreSQL, con un'architettura di storage completamente ridisegnata che offre prestazioni fino a 5x MySQL e 3x PostgreSQL a costi comparabili, con durabilità e scalabilità superiori.

---

## Amazon RDS

### Engine Supportati

| Engine | Versioni | Note |
|--------|---------|------|
| MySQL | 5.7, 8.0 | Il più comune; compatibile con Aurora MySQL |
| PostgreSQL | 12–16 | Feature-rich; compatibile con Aurora PostgreSQL |
| MariaDB | 10.5, 10.6, 10.11 | Fork MySQL; alcune feature aggiuntive |
| Oracle | 19c, 21c | BYOL (Bring Your Own License) o License Included |
| SQL Server | 2016, 2017, 2019, 2022 | License Included; BYOL per versioni SE2 |
| IBM Db2 | 11.5 | Aggiunto nel 2024 |

### Instance Classes

| Famiglia | vCPU | RAM | Caratteristica |
|---------|------|-----|----------------|
| **db.t3/t4g** | 2–8 | 1–32 GB | Burstable CPU, economiche per dev/test |
| **db.m5/m6g/m7g** | 2–96 | 8–384 GB | General purpose, bilanciato |
| **db.r5/r6g/r7g** | 2–96 | 16–768 GB | Memory optimized, per database grandi |
| **db.x2g** | 4–128 | 64–2.048 GB | Ultra memory, SAP HANA, Oracle in-memory |

*Nota: le istanze Graviton (g) sono ARM-based, circa 20% più economiche e con performance spesso migliori.*

### Multi-AZ Deployment

Multi-AZ crea una replica sincrona del database in una diversa Availability Zone. La replica è completamente trasparente all'applicazione (stesso endpoint).

**Come funziona:**
1. Ogni scrittura sul primario viene replicata in modo sincrono sulla standby prima di essere confermata
2. In caso di guasto (hardware, AZ, OS, database engine), AWS esegue un failover automatico in ~60–120 secondi
3. Il DNS viene aggiornato per puntare alla standby (ora promossa a primario)
4. L'applicazione deve gestire il riconnection (connection pool retry)

!!! warning "Multi-AZ standby NON è leggibile"
    La standby Multi-AZ non è accessibile per le letture. Il suo unico scopo è l'HA. Per scalare le letture, usare Read Replicas.

```bash
# Creare un'istanza RDS Multi-AZ
aws rds create-db-instance \
  --db-instance-identifier my-prod-db \
  --db-instance-class db.r6g.large \
  --engine mysql \
  --engine-version 8.0 \
  --master-username admin \
  --master-user-password MySecurePassword123! \
  --allocated-storage 100 \
  --storage-type gp3 \
  --iops 3000 \
  --multi-az \
  --vpc-security-group-ids sg-1234567890 \
  --db-subnet-group-name my-db-subnet-group \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "Mon:05:00-Mon:06:00" \
  --storage-encrypted \
  --kms-key-id alias/my-rds-key \
  --enable-iam-database-authentication \
  --deletion-protection \
  --tags Key=Environment,Value=production Key=Project,Value=myapp

# Forzare un failover manuale (per testare)
aws rds reboot-db-instance \
  --db-instance-identifier my-prod-db \
  --force-failover
```

**Multi-AZ Cluster (Novità):** RDS supporta ora anche un deployment Multi-AZ con 1 writer + 2 reader automatici (diverso dalle Read Replicas classiche), con failover < 35 secondi.

### Read Replicas

Le Read Replicas sono copie asincrone del database primario, accessibili per le operazioni di sola lettura. Riducono il carico sul primario per query di report, analytics, o applicazioni read-heavy.

**Caratteristiche:**
- Replica **asincrona** (possibile lag, non garantisce consistency immediata)
- Fino a **15 Read Replicas** per istanza RDS (5 per MySQL)
- Possono essere in **Region diverse** (Cross-Region Read Replica) per DR o utenti globali
- Ogni replica ha il proprio endpoint di connessione
- Possono essere **promosse** a database standalone (irreversibile — non è più una replica)
- Promozione utile per: migrazione, split read/write, test in isolamento

```bash
# Creare una Read Replica nella stessa Region
aws rds create-db-instance-read-replica \
  --db-instance-identifier my-read-replica-1 \
  --source-db-instance-identifier my-prod-db \
  --db-instance-class db.r6g.large \
  --availability-zone us-east-1b \
  --auto-minor-version-upgrade \
  --tags Key=Role,Value=read-replica

# Creare una Cross-Region Read Replica
aws rds create-db-instance-read-replica \
  --db-instance-identifier my-read-replica-eu \
  --source-db-instance-identifier arn:aws:rds:us-east-1:123456789012:db:my-prod-db \
  --db-instance-class db.r6g.large \
  --region eu-west-1 \
  --storage-encrypted

# Promuovere una replica a standalone
aws rds promote-read-replica \
  --db-instance-identifier my-read-replica-1
```

### Storage RDS

| Tipo Storage | IOPS | Throughput | Use Case |
|-------------|------|-----------|---------|
| **gp2** | 3 IOPS/GB (min 100, max 16.000) | 250 MB/s | Legacy |
| **gp3** | 3.000 IOPS base + provisioned | 125 MB/s + provisioned | Default, economico |
| **io1/io2** | Fino a 256.000 IOPS | 4.000 MB/s | Database I/O intensivo |
| **magnetic** | Basso | Basso | Legacy, non raccomandato |

**Storage Auto-scaling:** RDS può aumentare automaticamente lo storage quando si avvicina ai limiti. Configurare `MaxAllocatedStorage` per abilitarlo.

```bash
# Abilitare storage autoscaling
aws rds modify-db-instance \
  --db-instance-identifier my-prod-db \
  --max-allocated-storage 1000 \
  --apply-immediately
```

### RDS Proxy

RDS Proxy è un proxy fully managed che si interpone tra l'applicazione e RDS, gestendo un pool di connessioni. Essenziale per applicazioni serverless (Lambda) che aprono e chiudono connessioni frequentemente.

**Problemi che risolve:**
- Lambda apre molte connessioni contemporaneamente → esaurisce le connessioni disponibili del database
- Overhead di ogni nuova connessione TCP/SSL è elevato
- Failover più veloce (RDS Proxy mantiene le connessioni durante il failover)

**Caratteristiche:**
- Connection pooling multiplex: centinaia di connessioni Lambda → poche decine al database
- IAM authentication (token IAM invece di password)
- Integrazione con Secrets Manager (rotazione automatica credenziali)
- Failover ridotto del 66% rispetto a connessione diretta
- Supporta: MySQL, PostgreSQL, SQL Server, Aurora MySQL/PostgreSQL

```bash
# Creare RDS Proxy
aws rds create-db-proxy \
  --db-proxy-name my-rds-proxy \
  --engine-family MYSQL \
  --auth '[{
    "AuthScheme": "SECRETS",
    "SecretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-db-secret",
    "IAMAuth": "REQUIRED"
  }]' \
  --role-arn arn:aws:iam::123456789012:role/rds-proxy-role \
  --vpc-subnet-ids subnet-1234 subnet-5678 \
  --vpc-security-group-ids sg-1234567890 \
  --require-tls

# Registrare il target (istanza RDS)
aws rds register-db-proxy-targets \
  --db-proxy-name my-rds-proxy \
  --db-instance-identifiers my-prod-db
```

### Parameter Groups e Option Groups

**Parameter Group:** configurazione del motore database (innodb_buffer_pool_size, max_connections, etc.). Ogni istanza è associata a un parameter group.

**Option Group:** feature aggiuntive del database engine (es. Oracle APEX, SQL Server SSIS/SSRS, MySQL memcached plugin).

```bash
# Creare un parameter group custom
aws rds create-db-parameter-group \
  --db-parameter-group-name my-mysql8-params \
  --db-parameter-group-family mysql8.0 \
  --description "Custom MySQL 8.0 parameters"

# Modificare un parametro
aws rds modify-db-parameter-group \
  --db-parameter-group-name my-mysql8-params \
  --parameters '[{
    "ParameterName": "max_connections",
    "ParameterValue": "500",
    "ApplyMethod": "immediate"
  },{
    "ParameterName": "innodb_buffer_pool_size",
    "ParameterValue": "{DBInstanceClassMemory*3/4}",
    "ApplyMethod": "pending-reboot"
  }]'

# Associare il parameter group a un'istanza
aws rds modify-db-instance \
  --db-instance-identifier my-prod-db \
  --db-parameter-group-name my-mysql8-params \
  --apply-immediately
```

### Backup e Recovery

**Automated Backups:**
- Abilitati di default; retention da 0 a 35 giorni (0 = disabilita)
- Include: backup completo giornaliero + transaction logs (ogni 5 minuti)
- Permettono Point-In-Time Recovery (PITR): ripristino a qualsiasi secondo negli ultimi N giorni
- Archiviati su S3 (non visibili direttamente, gestiti da RDS)

**Manual Snapshots:**
- Non scadono — persistono finché non vengono eliminati manualmente
- Copiabili cross-region
- Condivisibili con altri account AWS
- Utili per: snapshot pre-migrazione, archivio storico, condivisione con altri ambienti

```bash
# Creare manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier my-prod-db \
  --db-snapshot-identifier snap-pre-upgrade-20240115 \
  --tags Key=Reason,Value=pre-upgrade

# PITR — ripristinare a un punto specifico nel tempo
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier my-prod-db \
  --target-db-instance-identifier my-restored-db \
  --restore-time "2024-01-15T14:30:00Z" \
  --db-instance-class db.r6g.large \
  --multi-az \
  --vpc-security-group-ids sg-1234567890

# Ripristinare da snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier my-restored-from-snap \
  --db-snapshot-identifier snap-pre-upgrade-20240115 \
  --db-instance-class db.r6g.large

# Copiare snapshot in altra Region
aws rds copy-db-snapshot \
  --source-db-snapshot-identifier arn:aws:rds:us-east-1:123456789012:snapshot:snap-pre-upgrade \
  --target-db-snapshot-identifier snap-pre-upgrade-copy \
  --region eu-west-1 \
  --kms-key-id alias/aws/rds
```

### Encryption RDS

- Abilitata al momento della creazione (non modificabile su istanza esistente)
- Usa AWS KMS (Customer Managed Key o AWS Managed Key `aws/rds`)
- Snapshot di istanze cifrate sono automaticamente cifrati
- Per cifrare un'istanza non cifrata: snapshot → copia snapshot con encryption → restore

```bash
# Cifrare un'istanza esistente non cifrata
# 1. Creare snapshot
aws rds create-db-snapshot --db-instance-identifier my-unencrypted-db --db-snapshot-identifier snap-to-encrypt

# 2. Copiare snapshot con encryption
aws rds copy-db-snapshot \
  --source-db-snapshot-identifier snap-to-encrypt \
  --target-db-snapshot-identifier snap-encrypted \
  --kms-key-id alias/my-rds-key

# 3. Ripristinare da snapshot cifrato
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier my-encrypted-db \
  --db-snapshot-identifier snap-encrypted
```

### IAM Database Authentication

Permette di connettere al database usando token IAM temporanei invece di username/password statiche.

```bash
# Abilitare IAM auth
aws rds modify-db-instance \
  --db-instance-identifier my-prod-db \
  --enable-iam-database-authentication

# Creare utente IAM nel database (MySQL)
# mysql> CREATE USER 'iam_user'@'%' IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS';
# mysql> GRANT SELECT ON mydb.* TO 'iam_user'@'%';

# Generare token e connettere (valido 15 minuti)
TOKEN=$(aws rds generate-db-auth-token \
  --hostname my-prod-db.xxxxx.rds.amazonaws.com \
  --port 3306 \
  --username iam_user \
  --region us-east-1)

mysql --host=my-prod-db.xxxxx.rds.amazonaws.com \
      --port=3306 \
      --user=iam_user \
      --password="$TOKEN" \
      --ssl-ca=rds-ca-2019-root.pem \
      --enable-cleartext-plugin
```

### Enhanced Monitoring e Performance Insights

**Enhanced Monitoring:** metriche OS con granularità fino a 1 secondo (CPU per processo, memoria, I/O, filesystem). Dati inviati a CloudWatch Logs.

**Performance Insights:** strumento di analisi delle query. Identifica quali query consumano più risorse, breakdown per wait event, top SQL, top host.

```bash
# Abilitare Enhanced Monitoring
aws rds modify-db-instance \
  --db-instance-identifier my-prod-db \
  --monitoring-interval 5 \
  --monitoring-role-arn arn:aws:iam::123456789012:role/rds-monitoring-role

# Abilitare Performance Insights
aws rds modify-db-instance \
  --db-instance-identifier my-prod-db \
  --enable-performance-insights \
  --performance-insights-retention-period 731 \
  --performance-insights-kms-key-id alias/my-rds-key
```

---

## Amazon Aurora

Aurora è un database relazionale cloud-native sviluppato da AWS, compatibile con MySQL 5.7/8.0 e PostgreSQL 12–16. Non è semplicemente MySQL/PostgreSQL su un'architettura migliorata: l'engine di storage è stato completamente riscritto per il cloud.

### Architettura Aurora — Storage Cluster

L'elemento distintivo di Aurora è il **Cluster Volume** condiviso:

- Unico volume logico condiviso da tutti i nodi del cluster (writer + readers)
- I dati vengono automaticamente replicati su **6 copie in 3 Availability Zone**
- Crescita automatica in incrementi da 10 GB, fino a **128 TB**
- Healing automatico: Aurora ripara continuamente i data block corrotti
- **Nessun provisioning manuale dello storage** — cresce automaticamente

**Quorum per writes:** 4/6 copie devono confermare la scrittura
**Quorum per reads:** 3/6 copie devono confermare la lettura
**Tolleranza ai guasti:** sopravvive alla perdita di 2 copie (su 6) per scritture, 3 copie per letture

!!! note "Aurora vs RDS — Differenza architetturale fondamentale"
    In RDS Multi-AZ, ogni byte di dato viene replicato via rete tra il writer e la standby (Synchronous replication overhead). In Aurora, solo i "redo log records" (molto più piccoli) vengono inviati al cluster volume; lo storage gestisce la replica internamente. Questo riduce drasticamente il traffico di rete e migliora le performance di scrittura.

### Aurora Replicas

- Fino a **15 Aurora Replicas** per cluster (condividono lo stesso storage)
- Latenza di replicazione tipicamente < 100ms (vs secondi per RDS Read Replicas)
- Failover automatico in **< 30 secondi** (priorità configurabile per ogni replica)
- Endpoint separato: **Cluster Endpoint** (writer), **Reader Endpoint** (load balancing lettori)

```bash
# Creare un cluster Aurora
aws rds create-db-cluster \
  --db-cluster-identifier my-aurora-cluster \
  --engine aurora-mysql \
  --engine-version 8.0.mysql_aurora.3.04.0 \
  --master-username admin \
  --master-user-password MySecurePassword123! \
  --vpc-security-group-ids sg-1234567890 \
  --db-subnet-group-name my-db-subnet-group \
  --backup-retention-period 7 \
  --storage-encrypted \
  --kms-key-id alias/my-aurora-key \
  --enable-iam-database-authentication \
  --deletion-protection

# Creare l'istanza writer
aws rds create-db-instance \
  --db-instance-identifier my-aurora-writer \
  --db-cluster-identifier my-aurora-cluster \
  --db-instance-class db.r7g.large \
  --engine aurora-mysql

# Aggiungere una replica reader
aws rds create-db-instance \
  --db-instance-identifier my-aurora-reader-1 \
  --db-cluster-identifier my-aurora-cluster \
  --db-instance-class db.r7g.large \
  --engine aurora-mysql \
  --promotion-tier 1  # 0 = massima priorità failover

# Endpoints del cluster
aws rds describe-db-clusters \
  --db-cluster-identifier my-aurora-cluster \
  --query 'DBClusters[0].{Endpoint:Endpoint,ReaderEndpoint:ReaderEndpoint}'
```

### Aurora Serverless v2

Aurora Serverless v2 scala automaticamente in base al carico, da 0.5 a 256 ACU (Aurora Capacity Units). Ogni ACU corrisponde approssimativamente a 2 GB RAM + vCPU proporzionale.

**Vantaggi:**
- Non paghi per capacità non utilizzata
- Scale in/out in frazioni di secondo (vs v1 che aveva cold start di minuti)
- Può coesistere con istanze provisioniali nello stesso cluster

**Use case ideali:**
- Ambienti dev/test con utilizzo intermittente
- Applicazioni con picchi imprevedibili
- Nuove applicazioni con traffico inizialmente sconosciuto

```bash
# Creare un cluster Aurora Serverless v2
aws rds create-db-cluster \
  --db-cluster-identifier my-serverless-cluster \
  --engine aurora-postgresql \
  --engine-version 15.4 \
  --master-username admin \
  --master-user-password MySecurePassword123! \
  --serverless-v2-scaling-configuration MinCapacity=0.5,MaxCapacity=64 \
  --storage-encrypted

# Creare un'istanza Serverless v2
aws rds create-db-instance \
  --db-instance-identifier my-serverless-writer \
  --db-cluster-identifier my-serverless-cluster \
  --db-instance-class db.serverless \
  --engine aurora-postgresql

# Modificare i limiti di scaling
aws rds modify-db-cluster \
  --db-cluster-identifier my-serverless-cluster \
  --serverless-v2-scaling-configuration MinCapacity=1,MaxCapacity=128
```

### Aurora Global Database

Aurora Global Database permette di avere **un primary** in una Region e fino a **5 secondary** in altre Region, con:
- **RPO < 1 secondo** (replication lag tipicamente < 1s)
- **RTO < 1 minuto** (failover gestito manualmente)
- Secondary Region è read-only (può essere promossa a primary in caso di disaster)

```bash
# Creare un Aurora Global Database
aws rds create-global-cluster \
  --global-cluster-identifier my-global-db \
  --engine aurora-mysql \
  --engine-version 8.0.mysql_aurora.3.04.0

# Associare il cluster primario
aws rds modify-db-cluster \
  --db-cluster-identifier my-aurora-cluster \
  --global-cluster-identifier my-global-db

# Aggiungere una Region secondaria
aws rds create-db-cluster \
  --db-cluster-identifier my-aurora-eu \
  --engine aurora-mysql \
  --global-cluster-identifier my-global-db \
  --region eu-west-1 \
  --storage-encrypted \
  --kms-key-id arn:aws:kms:eu-west-1:123456789012:key/mrk-5678

# Failover managed (promuovi region secondaria)
aws rds failover-global-cluster \
  --global-cluster-identifier my-global-db \
  --target-db-cluster-arn arn:aws:rds:eu-west-1:123456789012:cluster:my-aurora-eu
```

### Aurora Backtrack

Backtrack permette di "tornare indietro nel tempo" su un cluster Aurora MySQL senza dover ripristinare da uno snapshot. Non richiede la creazione di un nuovo cluster.

- Massimo **72 ore** nel passato
- Granularità: al secondo
- Non disponibile per Aurora PostgreSQL

**Use case:** recupero da un DROP TABLE accidentale, test di un aggiornamento, debug di un problema.

```bash
# Abilitare Backtrack alla creazione del cluster
aws rds create-db-cluster \
  --db-cluster-identifier my-aurora-cluster \
  --engine aurora-mysql \
  --backtrack-window 72 \  # ore
  # ... altri parametri ...

# Eseguire il backtrack
aws rds backtrack-db-cluster \
  --db-cluster-identifier my-aurora-cluster \
  --backtrack-to "2024-01-15T14:30:00+00:00"
```

### Blue/Green Deployments

Blue/Green permette aggiornamenti zero-downtime per RDS e Aurora: crea una copia "green" del database, applica le modifiche, esegue il switchover in <1 minuto.

**Use case:** aggiornamento major version engine, cambio parameter group, cambio instance class.

```bash
# Creare un Blue/Green Deployment
aws rds create-blue-green-deployment \
  --blue-green-deployment-name upgrade-to-8-0 \
  --source arn:aws:rds:us-east-1:123456789012:db:my-prod-db \
  --target-engine-version 8.0.35 \
  --target-db-instance-class db.r7g.large

# Switchover (redirect traffico da blue a green)
aws rds switchover-blue-green-deployment \
  --blue-green-deployment-identifier bgd-1234567890 \
  --switchover-timeout 300  # secondi di attesa per completamento transazioni

# Eliminare il blue (vecchio) dopo verifica
aws rds delete-blue-green-deployment \
  --blue-green-deployment-identifier bgd-1234567890 \
  --delete-source
```

### Aurora I/O-Optimized

Aurora I/O-Optimized è un pricing alternativo per workload I/O intensivi. Invece di pagare per ogni operazione I/O, si paga un prezzo per storage più alto ma con I/O illimitato.

**Quando conviene:** se il costo delle I/O supera il 25% del costo totale del cluster Aurora.

```bash
# Cambiare cluster a I/O-Optimized storage
aws rds modify-db-cluster \
  --db-cluster-identifier my-aurora-cluster \
  --storage-type aurora-iopt1 \
  --apply-immediately
```

### Aurora ML Integration

Aurora può fare chiamate dirette a SageMaker (per inferenza ML custom) e Amazon Comprehend (per analisi del sentiment) tramite SQL.

```sql
-- Aurora MySQL + SageMaker: classificare il sentiment di review
SELECT product_id, review_text,
  aws_sagemaker_invoke_endpoint(
    'my-sentiment-endpoint',
    '{"text": "', review_text, '"}'
  ) AS sentiment_prediction
FROM product_reviews
WHERE review_date > '2024-01-01';

-- Aurora PostgreSQL + Comprehend: analisi sentiment nativa
SELECT review_id,
  aws_comprehend_detect_sentiment(review_text, 'en') AS sentiment
FROM product_reviews;
```

---

## Confronto RDS vs Aurora

| Feature | RDS MySQL/PostgreSQL | Aurora MySQL/PostgreSQL |
|---------|---------------------|------------------------|
| Storage | EBS (provisioned) | Cluster Volume (auto-growing) |
| Max Storage | 64 TB | 128 TB |
| Replicas | 5 Read Replicas | 15 Aurora Replicas |
| Failover | ~60–120s (Multi-AZ) | < 30s |
| Replication | Asincrona | Near-sync (< 100ms) |
| Storage durability | 99.99% (Multi-AZ EBS) | 6 copie su 3 AZ |
| Backtrack | No | Sì (solo Aurora MySQL) |
| Serverless | No | Aurora Serverless v2 |
| Global Database | No | Sì (Global Database) |
| Costo | Inferiore | ~20% superiore a RDS |
| Compatibilità | 100% engine nativo | Parziale (alcune feature specifiche) |

!!! tip "Quando scegliere Aurora su RDS"
    Aurora conviene quando si ha bisogno di: failover più veloce, più Read Replicas, crescita automatica dello storage, Aurora Serverless v2 o Global Database. Per carichi di lavoro semplici o database piccoli, RDS è sufficiente e più economico.

---

## Best Practices

### Produzione

1. **Multi-AZ sempre** per istanze production — il costo raddoppia ma l'HA vale
2. **Storage encryption** sempre — con Customer Managed Key per audit
3. **RDS Proxy** per applicazioni Lambda o con molte connessioni concorrenti
4. **Performance Insights** abilitato — aiuta nella diagnosi delle query lente
5. **Deletion protection** abilitata — evita eliminazioni accidentali
6. **Backup retention** almeno 7 giorni; 35 giorni per ambienti critici
7. **Parameter Group custom** — non usare il default che non permette modifiche

### Costi

1. **Reserved Instances** (1 anno): ~40% di sconto; 3 anni: ~60%
2. **Fermare le istanze dev** nelle ore notturne (max 7 giorni ferme prima dello stop automatico di AWS)
3. **gp3** invece di io1 dove possibile (IOPS separati dal size)
4. **Aurora Serverless v2** per ambienti dev/staging con utilizzo intermittente
5. **Right-sizing** con CloudWatch + Performance Insights

### Sicurezza

```bash
# Checklist sicurezza RDS
# 1. No publicly accessible
aws rds modify-db-instance \
  --db-instance-identifier my-db \
  --no-publicly-accessible

# 2. Deletion protection
aws rds modify-db-instance \
  --db-instance-identifier my-db \
  --deletion-protection

# 3. Verificare configurazione sicurezza
aws rds describe-db-instances \
  --db-instance-identifier my-db \
  --query 'DBInstances[0].{PubliclyAccessible:PubliclyAccessible,Encrypted:StorageEncrypted,DeletionProtection:DeletionProtection,MultiAZ:MultiAZ}'
```

---

## Troubleshooting

### Connessione Rifiutata

1. Security Group: porta 3306 (MySQL) o 5432 (PostgreSQL) aperta dall'applicazione
2. Istanza in VPC privata: accessibile solo dall'interno della VPC o via VPN/Direct Connect
3. `PubliclyAccessible = false`: non raggiungibile da Internet

```bash
# Verificare configurazione di rete
aws rds describe-db-instances \
  --db-instance-identifier my-db \
  --query 'DBInstances[0].{PubliclyAccessible:PubliclyAccessible,VpcSecurityGroups:VpcSecurityGroups,DBSubnetGroup:DBSubnetGroup}'
```

### "Too Many Connections"

1. Aumentare `max_connections` nel Parameter Group
2. Usare RDS Proxy per connection pooling
3. Verificare che le applicazioni chiudano correttamente le connessioni

```bash
# Verificare connections attuali (MySQL)
# SELECT COUNT(*), USER FROM information_schema.processlist GROUP BY USER;

# Verificare max_connections nel parameter group
aws rds describe-db-parameters \
  --db-parameter-group-name my-mysql8-params \
  --query 'Parameters[?ParameterName==`max_connections`]'
```

### Failover Non Avviene (Multi-AZ)

Verificare:
- L'evento di failover in CloudWatch Events / RDS Events
- L'applicazione usa il DNS endpoint (non l'IP diretto che non cambia)
- Il timeout di connessione è configurato correttamente (es. `connect_timeout=5`)

---

## Relazioni

??? info "DynamoDB — NoSQL Alternativa"
    Per workload non relazionali o che richiedono scaling estremo (>1M req/s), DynamoDB è l'alternativa serverless.

    **Approfondimento completo →** [DynamoDB](dynamodb.md)

??? info "ElastiCache — Caching Layer"
    Aggiungere ElastiCache Redis davanti a RDS/Aurora per ridurre il carico di lettura del 90%+.

    **Approfondimento completo →** [Altri Database AWS](altri-db.md)

??? info "KMS — Encryption"
    Cifratura RDS usa KMS. Fondamentale per compliance e audit dei data access.

    **Approfondimento completo →** [KMS e Secrets Manager](../security/kms-secrets.md)

---

## Riferimenti

- [RDS User Guide](https://docs.aws.amazon.com/rds/latest/userguide/)
- [Aurora User Guide](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/)
- [RDS Proxy](https://docs.aws.amazon.com/rds/latest/userguide/rds-proxy.html)
- [Aurora Serverless v2](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [Aurora Global Database](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html)
- [Blue/Green Deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/blue-green-deployments.html)
- [Performance Insights](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html)
- [RDS Pricing](https://aws.amazon.com/rds/pricing/)
- [Aurora Pricing](https://aws.amazon.com/rds/aurora/pricing/)
