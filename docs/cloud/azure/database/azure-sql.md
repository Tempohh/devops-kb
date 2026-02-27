---
title: "Azure SQL"
slug: azure-sql
category: cloud
tags: [azure, azure-sql, sql-database, sql-managed-instance, sql-server, rds, paas-database]
search_keywords: [Azure SQL Database, SQL Managed Instance, Azure SQL Database Hyperscale, Serverless SQL, Business Critical tier, General Purpose tier, DTU vCore, geo-replication failover group, Azure SQL elastic pool, Transparent Data Encryption TDE, Entra ID authentication Azure SQL]
parent: cloud/azure/database/_index
related: [cloud/azure/security/key-vault, cloud/azure/networking/vnet, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/azure-sql/database/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure SQL

## Panoramica

Azure SQL è la famiglia di servizi SQL Server managed di Azure. Comprende tre opzioni con livelli crescenti di compatibilità e gestione:

- **Azure SQL Database**: database relazionale PaaS cloud-native, ottimizzato per nuove applicazioni
- **SQL Managed Instance**: istanza SQL Server completa come PaaS, ideale per lift & shift
- **SQL Server on Azure VM**: SQL Server completo su VM IaaS, massimo controllo

## Confronto Deployment Options

| Caratteristica | SQL Database | SQL Managed Instance | SQL Server on VM |
|---|---|---|---|
| **SQL Server Compatibility** | ~90% | ~99% | 100% |
| **SQL Server Agent** | No | Sì | Sì |
| **Cross-DB queries** | No | Sì | Sì |
| **Linked Servers** | No | Sì (limitato) | Sì |
| **CLR** | No | Sì | Sì |
| **Replication** | Subscriber only | Publisher/Subscriber | Completo |
| **Networking** | Shared endpoint / PE | VNet native | VNet (VM NIC) |
| **Management overhead** | Minimo | Medio | Alto |
| **OS Access** | No | No | Sì |
| **Use Case** | App cloud-native, SaaS | Lift & shift SQL Server | Feature specifiche OS/SQL |

## Service Tiers

### Modello DTU (legacy)

Il modello DTU (Database Transaction Unit) combina CPU, memoria e I/O in un'unità singola. Più semplice ma meno flessibile.

| Tier | DTU Range | Max Storage | HA | Backup Retention |
|---|---|---|---|---|
| **Basic** | 5 DTU | 2 GB | Locale | 7 giorni |
| **Standard** | 10-3000 DTU | 1 TB | Locale | 35 giorni |
| **Premium** | 125-4000 DTU | 4 TB | Zone-redundant (opzione) | 35 giorni |

### Modello vCore (consigliato)

Il modello vCore separa CPU, memoria e storage, con più flessibilità e Azure Hybrid Benefit.

| Tier | IOPS | SLA | HA | In-Memory OLTP | Replica Lettura |
|---|---|---|---|---|---|
| **General Purpose** | 7000 IOPS/file | 99.99% | Remote storage | No | No (a pagamento) |
| **Business Critical** | Local SSD, 200K IOPS | 99.99% | Local SSD HA | Sì | 1 gratuita |
| **Hyperscale** | Scalabile | 99.99% | Multi-layer | No | Fino a 30 named replicas |

```bash
RG="rg-database-prod"
LOCATION="westeurope"
SERVER_NAME="sqlsrv-prod-2026"
DB_NAME="myapp-production"
ADMIN_USER="sqladmin"

# Creare SQL Server (server logico)
az sql server create \
  --resource-group $RG \
  --name $SERVER_NAME \
  --location $LOCATION \
  --admin-user $ADMIN_USER \
  --admin-password "$(openssl rand -base64 32)" \
  --enable-ad-only-auth \
  --external-admin-principal-type Group \
  --external-admin-name "DBA-Team" \
  --external-admin-sid $(az ad group show --group "DBA-Team" --query id -o tsv)

# Creare database General Purpose vCore — Provisioned
az sql db create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name $DB_NAME \
  --edition GeneralPurpose \
  --family Gen5 \
  --capacity 4 \
  --compute-model Provisioned \
  --zone-redundant true \
  --backup-storage-redundancy Geo \
  --max-size 100GB

# Creare database Business Critical
az sql db create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name myapp-critical \
  --edition BusinessCritical \
  --family Gen5 \
  --capacity 8 \
  --zone-redundant true
```

## Serverless

Il tier Serverless scala automaticamente le vCore in base al carico e si mette in pausa automaticamente dopo un periodo di inattività definito, eliminando i costi di compute durante l'idle.

```bash
# Creare database Serverless
az sql db create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name myapp-serverless \
  --edition GeneralPurpose \
  --family Gen5 \
  --capacity 2 \
  --compute-model Serverless \
  --auto-pause-delay 60 \
  --min-capacity 0.5 \
  --max-capacity 4

# Aggiornare auto-pause delay su database esistente
az sql db update \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name myapp-serverless \
  --auto-pause-delay 120 \
  --min-capacity 1
```

!!! tip "Serverless: Quando Usarlo"
    Serverless è ideale per database di dev/test, applicazioni con picchi imprevedibili, o SaaS con molti tenant piccoli. Non usarlo per workload con latency critica: il resume dopo auto-pause può richiedere qualche secondo.

## Hyperscale

Hyperscale è l'opzione di scalabilità estrema di Azure SQL Database: storage fino a 100 TB, scaling quasi istantaneo, named replicas per read-scaling, rapid restore.

```bash
# Creare database Hyperscale
az sql db create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name myapp-hyperscale \
  --edition Hyperscale \
  --family Gen5 \
  --capacity 4 \
  --backup-storage-redundancy Geo

# Aggiungere named replica (read replica indipendente con proprio compute)
az sql db replica create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name myapp-hyperscale \
  --partner-resource-group $RG \
  --partner-server $SERVER_NAME \
  --secondary-type Named \
  --partner-database myapp-hyperscale-read1 \
  --family Gen5 \
  --capacity 2
```

!!! note "Hyperscale vs Business Critical"
    Hyperscale scala storage illimitato e ha rapid restore, ma non ha in-memory OLTP. Business Critical ha local SSD per massima performance I/O e una read replica gratuita. Scegli in base al bottleneck: storage/scale (Hyperscale) vs latency I/O (Business Critical).

## Elastic Pool

Gli Elastic Pool permettono a più database di condividere un pool di risorse (vCore o DTU), ottimizzando i costi per workload con picchi distribuiti nel tempo (come applicazioni SaaS multi-tenant).

```bash
# Creare Elastic Pool
az sql elastic-pool create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name pool-saas-tenants \
  --edition GeneralPurpose \
  --family Gen5 \
  --capacity 8 \
  --zone-redundant true

# Creare database nel pool
az sql db create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name tenant-001 \
  --elastic-pool pool-saas-tenants

# Spostare database esistente nel pool
az sql db update \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name existing-db \
  --elastic-pool pool-saas-tenants
```

## Geo-Replication e Failover Groups

### Active Geo-Replication

Crea una replica leggibile del database in un'altra regione. Consente failover manuale.

```bash
# Creare replica geo-distribuita in secondaria
az sql db replica create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name $DB_NAME \
  --partner-server sqlsrv-dr-northeurope \
  --partner-resource-group rg-database-dr

# Failover manuale (promuove la secondaria a primaria)
az sql db replica set-primary \
  --resource-group rg-database-dr \
  --server sqlsrv-dr-northeurope \
  --name $DB_NAME
```

### Failover Groups (Auto-Failover)

I Failover Groups automatizzano il failover geo-distribuito con un endpoint DNS stabile che si aggiorna automaticamente.

```bash
# Creare failover group
az sql failover-group create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name fg-myapp-prod \
  --partner-server sqlsrv-dr-northeurope \
  --partner-resource-group rg-database-dr \
  --failover-policy Automatic \
  --grace-period 1

# Aggiungere database al failover group
az sql failover-group update \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name fg-myapp-prod \
  --add-db $DB_NAME

# Connessione con endpoint Failover Group (si aggiorna automaticamente)
# Read-Write: fg-myapp-prod.database.windows.net
# Read-Only:  fg-myapp-prod.secondary.database.windows.net

# Failover manuale (test o manutenzione pianificata)
az sql failover-group set-primary \
  --resource-group rg-database-dr \
  --server sqlsrv-dr-northeurope \
  --name fg-myapp-prod
```

!!! warning "Grace Period"
    `--grace-period 1` significa: Azure aspetta 1 ora prima di eseguire il failover automatico dopo aver perso il contatto con la primaria. Valori bassi riducono RTO ma aumentano il rischio di split-brain. In produzione, valuta almeno 1 ora.

## Backup

Azure SQL esegue backup automatici:
- Full backup: settimanale
- Differential backup: ogni 12-24 ore
- Transaction log backup: ogni 5-10 minuti

```bash
# Configurare retention PITR (Point-in-Time Restore)
az sql db update \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name $DB_NAME \
  --backup-storage-redundancy Geo \
  --retention 35

# Long-Term Retention (LTR) — fino a 10 anni
az sql db ltr-policy set \
  --resource-group $RG \
  --server $SERVER_NAME \
  --database $DB_NAME \
  --weekly-retention P4W \
  --monthly-retention P12M \
  --yearly-retention P5Y \
  --week-of-year 1

# Restore database a punto temporale specifico
az sql db restore \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name $DB_NAME \
  --dest-name myapp-restored \
  --time "2026-02-25T10:00:00" \
  --dest-resource-group $RG \
  --dest-server $SERVER_NAME
```

## Auditing e Microsoft Defender for SQL

```bash
# Abilitare auditing su server SQL
az sql server audit-policy update \
  --resource-group $RG \
  --name $SERVER_NAME \
  --state Enabled \
  --log-analytics-workspace-resource-id $(az monitor log-analytics workspace show --resource-group rg-monitoring --workspace-name law-prod --query id -o tsv) \
  --log-analytics-target-state Enabled

# Abilitare Defender for SQL (rileva SQL injection, anomalie accesso)
az sql server advanced-threat-protection-setting update \
  --resource-group $RG \
  --server $SERVER_NAME \
  --state Enabled

# Abilitare Vulnerability Assessment
az sql server vulnerability-assessment setting update \
  --resource-group $RG \
  --server $SERVER_NAME \
  --storage-account mystorageaccount2026 \
  --storage-key $(az storage account keys list --resource-group $RG --account-name mystorageaccount2026 --query "[0].value" -o tsv) \
  --recurr-scans-day-of-week Sunday \
  --recurr-scans-time 00:00
```

## Autenticazione

```bash
# Abilitare autenticazione Entra ID sul server SQL
az sql server ad-admin create \
  --resource-group $RG \
  --server $SERVER_NAME \
  --display-name "DBA-Team" \
  --object-id $(az ad group show --group "DBA-Team" --query id -o tsv)

# Connettersi con Entra ID auth (da Azure CLI)
az account get-access-token --resource https://database.windows.net --query accessToken -o tsv

# Connection string con Managed Identity
# Nel codice Python:
# import pyodbc
# conn = pyodbc.connect(
#   "Driver={ODBC Driver 18 for SQL Server};"
#   "Server=sqlsrv-prod-2026.database.windows.net;"
#   "Database=myapp-production;"
#   "Authentication=ActiveDirectoryMsi"
# )
```

## Private Endpoint per Azure SQL

```bash
# Disabilitare accesso pubblico
az sql server update \
  --resource-group $RG \
  --name $SERVER_NAME \
  --restrict-outbound-network-access false \
  --public-network-access Disabled

# Creare Private Endpoint
az network private-endpoint create \
  --resource-group $RG \
  --name pep-sql-prod \
  --vnet-name vnet-prod \
  --subnet snet-private-endpoints \
  --private-connection-resource-id $(az sql server show --resource-group $RG --name $SERVER_NAME --query id -o tsv) \
  --group-ids sqlServer \
  --connection-name conn-sql-prod

# DNS zona privata
az network private-dns zone create \
  --resource-group $RG \
  --name "privatelink.database.windows.net"
```

## Transparent Data Encryption (TDE) con CMK

```bash
# Abilitare TDE con Customer-managed Key (CMK)
az sql server tde-key set \
  --resource-group $RG \
  --server $SERVER_NAME \
  --server-key-type AzureKeyVault \
  --kid $(az keyvault key show --vault-name mykeyvault-cmk --name sql-tde-key --query key.kid -o tsv)

az sql db tde set \
  --resource-group $RG \
  --server $SERVER_NAME \
  --database $DB_NAME \
  --status Enabled
```

## SQL Managed Instance

SQL Managed Instance (SQL MI) è un deployment di SQL Server quasi completo come servizio PaaS, con VNet native deployment. Ideale per lift & shift senza modifiche applicative.

```bash
# Creare subnet delegata per SQL MI (/27 minimo, /24 consigliato)
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name vnet-prod \
  --name snet-sql-mi \
  --address-prefixes 10.0.20.0/24 \
  --delegations Microsoft.Sql/managedInstances

# Creare SQL Managed Instance (operazione richiede 4-6 ore)
az sql mi create \
  --resource-group $RG \
  --name sqlmi-prod-2026 \
  --location $LOCATION \
  --admin-user sqladmin \
  --admin-password "$(openssl rand -base64 32)" \
  --subnet $(az network vnet subnet show --resource-group $RG --vnet-name vnet-prod --name snet-sql-mi --query id -o tsv) \
  --sku-name GP_Gen5 \
  --vcores 8 \
  --storage-size-in-gb 256 \
  --license-type BasePrice \
  --zone-redundant true

# Link Feature: replica asincrona da SQL Server on-premises a SQL MI
# (per migrazione zero-downtime e disaster recovery)
az sql mi link create \
  --resource-group $RG \
  --instance-name sqlmi-prod-2026 \
  --name my-link \
  --primary-availability-group-name AGPrimary \
  --target-database myapp \
  --source-endpoint "192.168.1.100:5022"
```

## Best Practices

- Usa sempre `--zone-redundant true` per database di produzione (99.99% SLA)
- Usa **Failover Groups** invece di geo-replication manuale per endpoint DNS stabile
- Abilita **Defender for SQL** su tutti i server (rileva SQL injection, accessi anomali)
- Usa **Entra ID authentication** e disabilita la SQL authentication dove possibile
- Configura **Private Endpoint** e disabilita l'accesso pubblico per sicurezza
- Per Elastic Pool, monitora `eDTU_used` / vCore: se un tenant usa sempre >50%, spostarlo fuori dal pool
- Usa **Azure SQL Analytics** workbook in Azure Monitor per visibilità performantica

## Troubleshooting

```bash
# Verificare dimensione database e spazio usato
az sql db show \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name $DB_NAME \
  --query "{name:name, size:maxSizeBytes, currentSize:currentSku}" \
  --output json

# Listare connessioni attive (richiede query T-SQL)
# SELECT session_id, login_name, program_name, host_name, status
# FROM sys.dm_exec_sessions WHERE is_user_process = 1

# Controllare lo stato del failover group
az sql failover-group show \
  --resource-group $RG \
  --server $SERVER_NAME \
  --name fg-myapp-prod \
  --query "replicationState" -o tsv
```

## Riferimenti

- [Documentazione Azure SQL Database](https://learn.microsoft.com/azure/azure-sql/database/)
- [SQL Managed Instance](https://learn.microsoft.com/azure/azure-sql/managed-instance/)
- [Failover Groups](https://learn.microsoft.com/azure/azure-sql/database/failover-group-overview)
- [Hyperscale Architecture](https://learn.microsoft.com/azure/azure-sql/database/service-tier-hyperscale)
- [Serverless Computing Tier](https://learn.microsoft.com/azure/azure-sql/database/serverless-tier-overview)
- [Prezzi Azure SQL](https://azure.microsoft.com/pricing/details/azure-sql-database/)
