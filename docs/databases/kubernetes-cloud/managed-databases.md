---
title: "Managed Databases"
slug: managed-databases
category: databases
tags: [managed-database, rds, aurora, dynamodb, cloud-sql, azure-database, dbaas]
search_keywords: [managed database service, aws rds, amazon aurora, aurora serverless, dynamodb, google cloud sql, azure database postgresql, azure cosmos db, rds multi-az, rds read replicas, aurora global database, aurora storage auto scaling, rds proxy, database as a service, dbaas, database cloud comparison, rds vs aurora, aurora vs dynamodb, managed vs self-managed database, cloud database cost, rds instance types, aurora serverless v2, planetscale, neon serverless postgres, cockroachdb cloud, supabase]
parent: databases/kubernetes-cloud/_index
related: [databases/replicazione-ha/backup-pitr, databases/replicazione-ha/failover-recovery, databases/postgresql/connection-pooling]
official_docs: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Managed Databases

## Panoramica

I database managed trasferiscono la responsabilità operativa (patch, backup, HA, failover, monitoring di base) al cloud provider. Il trade-off: si paga un premium (tipicamente 20-50% rispetto all'istanza EC2 equivalente) in cambio di **riduzione della complessità operativa** e garanzie SLA.

!!! tip "Regola pratica"
    Se il tuo team non ha un DBA (o equivalente seniority) disponibile h24, il managed database è quasi sempre la scelta corretta — il costo del downtime supera il premium mensile del managed service.

---

## AWS RDS — Il Managed Relazionale Standard

Amazon RDS gestisce PostgreSQL, MySQL, MariaDB, Oracle e SQL Server con le stesse API. È il punto di riferimento per database relazionali managed su AWS.

### Multi-AZ — Alta Disponibilità

```
Primary (AZ-a)    ──── replication sincrona ────    Standby (AZ-b)
      │                                                    │
      │ Serve write + read                                │ Non serve traffico
      │                                                    │ (hot standby)
                    Failover automatico 60-120s
                    (DNS endpoint invariato)
```

```bash
# Crea istanza RDS Multi-AZ
aws rds create-db-instance \
  --db-instance-identifier prod-postgres \
  --db-instance-class db.r6g.xlarge \
  --engine postgres \
  --engine-version 17 \
  --master-username dbadmin \
  --master-user-password "$(aws secretsmanager get-secret-value --secret-id db-password --query SecretString --output text)" \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --multi-az \                          # Abilita standby in AZ diversa
  --backup-retention-period 30 \        # 30 giorni PITR
  --preferred-backup-window "02:00-03:00" \
  --preferred-maintenance-window "sun:04:00-sun:05:00" \
  --deletion-protection \               # Impedisce delete accidentale
  --enable-performance-insights \       # Performance Insights incluso
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name prod-db-subnet-group

# Crea read replica (per scaling letture)
aws rds create-db-instance-read-replica \
  --db-instance-identifier prod-postgres-replica-1 \
  --source-db-instance-identifier prod-postgres \
  --db-instance-class db.r6g.large     # Read replica può essere più piccola
```

### RDS Proxy — Connection Pooling Managed

```bash
# RDS Proxy: gestisce connection pooling + failover trasparente per Lambda e container
aws rds create-db-proxy \
  --db-proxy-name prod-postgres-proxy \
  --engine-family POSTGRESQL \
  --auth '[{
    "AuthScheme": "SECRETS",
    "SecretArn": "arn:aws:secretsmanager:us-east-1:123456789:secret:db-credentials",
    "IAMAuth": "REQUIRED"
  }]' \
  --role-arn arn:aws:iam::123456789:role/rds-proxy-role \
  --vpc-subnet-ids subnet-xxx subnet-yyy \
  --vpc-security-group-ids sg-xxx

# Connessione tramite Proxy: usa endpoint del proxy, non dell'istanza
# Il proxy gestisce automaticamente il failover (nessun DNS TTL da aspettare)
psql "host=prod-postgres-proxy.proxy-xxx.us-east-1.rds.amazonaws.com \
      user=dbadmin dbname=mydb sslmode=require"
```

---

## Amazon Aurora — Il Managed Relazionale Avanzato

Aurora è l'evoluzione proprietaria di RDS: PostgreSQL e MySQL compatibili, ma con architettura storage completamente ridisegnata da AWS. Lo storage è distribuito su 6 copie in 3 AZ — separato dal compute.

```
Aurora Cluster:
  ┌─────────────────────────────────────────────────────────────────┐
  │ Aurora Shared Storage (6 copie, 3 AZ, auto-scaling 10GB→128TB) │
  └────────────┬────────────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
 Writer      Reader     Reader
 Instance   Instance   Instance
 (primary)  (replica)  (replica)
```

**Vantaggi rispetto a RDS Multi-AZ:**
- Failover in ~30s (vs 60-120s RDS) — le repliche sono già sincronizzate sullo stesso storage
- Fino a 15 Read Replica (vs 5 RDS) — tutte con lag < 1s
- Storage si scala automaticamente (nessun provisioning manuale)
- Aurora Global Database: replica cross-region con RPO < 1s

### Aurora Serverless v2 — Auto-scaling Compute

Aurora Serverless v2 scala le ACU (Aurora Capacity Units) in base al carico, in incrementi di 0.5 ACU:

```bash
# Crea cluster Aurora PostgreSQL Serverless v2
aws rds create-db-cluster \
  --db-cluster-identifier prod-aurora \
  --engine aurora-postgresql \
  --engine-version 16.1 \
  --serverless-v2-scaling-configuration '{"MinCapacity": 0.5, "MaxCapacity": 64}' \
  --master-username dbadmin \
  --manage-master-user-password \      # Gestisce la password in Secrets Manager
  --storage-encrypted \
  --backup-retention-period 30 \
  --db-subnet-group-name prod-db-subnet-group \
  --vpc-security-group-ids sg-xxx

# Aggiunge writer instance Serverless v2
aws rds create-db-instance \
  --db-instance-identifier prod-aurora-writer \
  --db-cluster-identifier prod-aurora \
  --db-instance-class db.serverless \   # Classe speciale per Serverless v2
  --engine aurora-postgresql
```

**Quando usare Serverless v2 vs istanza fissa:**
- Serverless v2: workload variabile, dev/staging, picchi imprevedibili
- Istanza fissa: produzione con carico prevedibile, latenza critica (Serverless ha ~10ms di warm-up per scale-up)

---

## Amazon DynamoDB — Key-Value/Document Serverless

DynamoDB è il database NoSQL serverless di AWS: throughput provisioned o on-demand, latenza sub-10ms a qualsiasi scala, zero administration.

### Modello di Dati

```
Table: Ordini
  Partition Key: user_id (TEXT)    ← hash → distribuzione su shard
  Sort Key:      created_at (STRING, ISO8601)  ← range query su stessa partizione

  Item:
    { "user_id": "u-123",
      "created_at": "2024-01-15T14:00:00Z",
      "totale": 199.50,
      "stato": "completato",
      "prodotti": [...]             ← attributi flessibili, nessuno schema
    }
```

```python
import boto3
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Ordini')

# Write (PutItem)
table.put_item(Item={
    'user_id': 'u-123',
    'created_at': '2024-01-15T14:00:00Z',
    'totale': Decimal('199.50'),
    'stato': 'completato'
})

# Read (Query sulla partition key + sort key range)
response = table.query(
    KeyConditionExpression=Key('user_id').eq('u-123') &
                           Key('created_at').between('2024-01-01', '2024-01-31'),
    FilterExpression=Attr('stato').eq('completato')
)
ordini = response['Items']

# Transazione atomica multi-item (stessa o diverse tabelle)
dynamodb.meta.client.transact_write(
    TransactItems=[
        {'Update': {
            'TableName': 'Inventario',
            'Key': {'sku': 'P001'},
            'UpdateExpression': 'SET quantita = quantita - :qty',
            'ConditionExpression': 'quantita >= :qty',
            'ExpressionAttributeValues': {':qty': Decimal('2')}
        }},
        {'Put': {
            'TableName': 'Ordini',
            'Item': {'user_id': 'u-123', 'created_at': '...', ...}
        }}
    ]
)
```

**DynamoDB è la scelta sbagliata se:**
- Hai bisogno di query flessibili su campi diversi dalla partition key → costoso (Global Secondary Index) o impossibile
- Hai transazioni multi-item frequenti → overhead significativo
- Il team non conosce il data modeling NoSQL → errori di design costosi da correggere

---

## Google Cloud SQL e Azure Database

### Cloud SQL (GCP)

Equivalente GCP di RDS — PostgreSQL, MySQL, SQL Server.

```bash
# Crea istanza Cloud SQL PostgreSQL con HA
gcloud sql instances create prod-postgres \
  --database-version=POSTGRES_17 \
  --cpu=4 \
  --memory=16GB \
  --region=us-central1 \
  --availability-type=REGIONAL \  # HA con failover automatico (equivalente Multi-AZ)
  --backup-location=us \
  --enable-bin-log \
  --backup-start-time=02:00 \
  --retained-backups-count=30 \
  --retained-transaction-log-days=7 \  # PITR window
  --storage-size=100GB \
  --storage-auto-increase \
  --deletion-protection

# Crea read replica
gcloud sql instances create prod-postgres-replica \
  --master-instance-name=prod-postgres \
  --region=us-east1 \          # Replica in regione diversa
  --availability-type=ZONAL
```

### Azure Database for PostgreSQL — Flexible Server

```bash
# Crea server PostgreSQL Flexible (zona-ridondante)
az postgres flexible-server create \
  --resource-group prod-rg \
  --name prod-postgres \
  --version 17 \
  --sku-name Standard_D4s_v3 \   # 4 vCPU, 16GB RAM
  --tier GeneralPurpose \
  --storage-size 128 \
  --high-availability ZoneRedundant \   # HA cross-zona (equivalente Multi-AZ)
  --backup-retention 30 \
  --geo-redundant-backup Enabled \      # Backup cross-region
  --location westeurope
```

---

## Confronto Managed Services

| Servizio | Latenza | Write Scaling | Read Scaling | Schema | Costo |
|----------|---------|---------------|--------------|--------|-------|
| RDS PostgreSQL | ~1ms | Verticale | 5 repliche | SQL rigido | Medio |
| Aurora PostgreSQL | ~1ms | Verticale | 15 repliche | SQL rigido | Medio-alto |
| Aurora Serverless v2 | ~1-10ms | Auto | Auto | SQL rigido | Variabile |
| DynamoDB | <10ms | Infinita | Infinita | Flessibile | Variabile (on-demand) |
| Cloud SQL | ~1ms | Verticale | Read replicas | SQL rigido | Medio |
| Azure DB PG | ~1ms | Verticale | Read replicas | SQL rigido | Medio |

---

## Best Practices

- **Terraform/IaC per tutte le risorse database**: non creare database managed dalla console — la configurazione viene persa e non è riproducibile
- **Secrets Manager per le credenziali**: non mettere password in variabili d'ambiente o ConfigMap — usare AWS Secrets Manager/Azure Key Vault/GCP Secret Manager con rotation automatica
- **Activation di Performance Insights (RDS/Aurora)**: costo quasi zero, fornisce query analysis senza `pg_stat_statements` manuale
- **Dimensionare per il picco + buffer 30%**: i managed service scalano verticalmente, non orizzontalmente — il ridimensionamento richiede finestre di manutenzione
- **Deletion protection sempre attiva in produzione**: un `terraform destroy` accidentale o `aws rds delete-db-instance` senza deletion protection è irrecuperabile

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| RDS CPU alta durante backup | Backup window sovrapposto con peak traffic | Spostare backup window in orario off-peak |
| Aurora replica lag alto | Replica instance undersized | Aumentare la classe dell'istanza replica |
| DynamoDB `ProvisionedThroughputExceededException` | Throttling su partizione hot | Aumentare RCU/WCU, passare a on-demand, rivedere partition key |
| Connessione RDS timeout da Lambda | Troppe connessioni Lambda esauriscono il pool | Usare RDS Proxy davanti a RDS |
| Cloud SQL connection refused | IP non autorizzato in authorized networks | Aggiungere IP in Cloud SQL → Connections → Authorized networks |

## Riferimenti

- [AWS RDS Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/)
- [Amazon Aurora Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Google Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Azure Database for PostgreSQL](https://docs.microsoft.com/azure/postgresql/)
