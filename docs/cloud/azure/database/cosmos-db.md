---
title: "Azure Cosmos DB"
slug: cosmos-db
category: cloud
tags: [azure, cosmos-db, nosql, multi-model, global-distribution, consistency]
search_keywords: [Cosmos DB NoSQL, Azure Cosmos DB global distribution, Request Units RU throughput, partition key strategy, consistency levels strong eventual session, Change Feed event streaming, Cosmos DB MongoDB API, Cosmos DB Cassandra, multi-region write, Cosmos DB Free Tier, serverless Cosmos, Cosmos DB analytical store HTAP]
parent: cloud/azure/database/_index
related: [cloud/azure/compute/aks-containers, cloud/azure/messaging/event-hubs, cloud/azure/security/key-vault]
official_docs: https://learn.microsoft.com/azure/cosmos-db/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Cosmos DB

## Panoramica

Azure Cosmos DB è il database NoSQL multi-model, distribuito globalmente di Azure. Progettato per workload che richiedono letture puntuali <10ms al P99 (nella stessa regione), scala elastica orizzontale e disponibilità fino al 99.999% (SLA raggiunto con account multi-regione; single-region è 99.99%). È completamente managed (no infrastructure da gestire) e supporta più modelli di dati tramite API compatibili. Include anche vector search (indice DiskANN) per workload AI/RAG.

Usare Cosmos DB quando:
- Latency estrema (<10ms read P99)
- Distribuzione globale multi-regione
- Workload con throughput variabile e imprevedibile
- Modello di dati document, graph, key-value o column-family
- IoT, gaming, e-commerce, real-time personalization

Non usare Cosmos DB quando: hai dati altamente relazionali, necessiti di JOIN complessi tra entità o transazioni multi-tabella (le transazioni sono limitate a una singola logical partition) → scegli Azure SQL / PostgreSQL. Cosmos DB inoltre non è conveniente per scan analitici ampi: costa RU proporzionali ai dati letti.

## API Supportate

| API | Modello Dati | Compatibilità | Use Case |
|---|---|---|---|
| **NoSQL (native)** | Document JSON | Cosmos-native SDK | Nuovi progetti, massima feature parity |
| **MongoDB** | Document BSON | MongoDB wire protocol (modello RU-based; esiste anche il modello **vCore**, a nodi dedicati e con pricing diverso) | Migrazione MongoDB, team MongoDB |
| **Cassandra** | Wide-column (CQL) | Cassandra CQL v4 | Migrazione Cassandra, time-series |
| **Gremlin** | Graph | Apache TinkerPop | Social networks, fraud detection, knowledge graph |
| **Table** | Key-Value | Azure Table Storage API | Migrazione Table Storage, dati strutturati semplici |
| **PostgreSQL** *(in dismissione)* | Relazionale | PostgreSQL + Citus | Non più disponibile per nuovi progetti |

!!! warning "Cosmos DB for PostgreSQL: in retirement"
    Il nuovo deployment è bloccato; i cluster esistenti restano supportati. Per Postgres distribuito (Citus) usare **Azure Database for PostgreSQL – Elastic Clusters**, con tool di migrazione dedicato. Le API Gremlin/Table/Cassandra sono mantenute per compatibilità: per nuovi progetti document la scelta di default è l'API **NoSQL**.

## Creare Account Cosmos DB

```bash
RG="rg-database-prod"
LOCATION="westeurope"
COSMOS_ACCOUNT="cosmos-myapp-prod"

# Creare account Cosmos DB NoSQL multi-region
az cosmosdb create \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --kind GlobalDocumentDB \
  --locations regionName=westeurope failoverPriority=0 isZoneRedundant=true \
  --locations regionName=northeurope failoverPriority=1 isZoneRedundant=true \
  --default-consistency-level Session \
  --enable-multiple-write-locations false \
  --enable-automatic-failover true \
  --backup-policy-type Continuous \
  --continuous-tier Continuous30Days

# Account con multi-region write (ogni regione può ricevere write)
az cosmosdb create \
  --resource-group $RG \
  --name cosmos-global-prod \
  --kind GlobalDocumentDB \
  --locations regionName=westeurope failoverPriority=0 isZoneRedundant=true \
  --locations regionName=northeurope failoverPriority=1 isZoneRedundant=true \
  --locations regionName=eastus failoverPriority=2 isZoneRedundant=true \
  --default-consistency-level BoundedStaleness \
  --enable-multiple-write-locations true \
  --max-interval 5 \
  --max-staleness-prefix 100000

# Aggiungere una nuova regione a un account esistente
az cosmosdb update \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --locations regionName=westeurope failoverPriority=0 isZoneRedundant=true \
  --locations regionName=northeurope failoverPriority=1 isZoneRedundant=true \
  --locations regionName=uksouth failoverPriority=2 isZoneRedundant=false
```

## Livelli di Consistency

Il livello di consistency è il trade-off fondamentale in un sistema distribuito: coerenza dei dati vs latency vs disponibilità.

| Livello | Garanzia | Latency Write | Disponibilità | RU Cost Read |
|---|---|---|---|---|
| **Strong** | Letture sempre aggiornate (linearizzabilità) | Alta (2x RTT inter-region) | Ridotta (non supporta multi-write) | 2x |
| **Bounded Staleness** | Letture in ritardo al massimo di K versioni o T secondi | Medio | Alta | 2x |
| **Session** *(default)* | Consistency garantita all'interno della sessione utente | Bassa | Alta | 1x |
| **Consistent Prefix** | Le letture vedono sempre un prefisso ordinato delle scritture (mai "buchi" o ordine invertito), ma possono essere in ritardo | Bassa | Alta | 1x |
| **Eventual** | Nessuna garanzia di ordine né di freschezza; convergenza solo a lungo termine | Minima | Massima | 1x |

!!! note "Vincoli"
    **Strong** non è utilizzabile con multi-region write. Il livello si può solo *allentare* per singola richiesta (override a livello SDK), non rafforzare oltre il default dell'account. **Session** vale per un session token: due istanze di client (o due pod dietro un load balancer) che non si scambiano il token non godono di read-your-writes.

!!! tip "Session Consistency: Il Giusto Compromesso"
    **Session** è il livello default e il più usato in produzione. Garantisce che un utente veda sempre le sue scritture (read-your-writes) e quelle della sua sessione in ordine, senza l'overhead di Strong. Perfetto per applicazioni web e mobile.

```bash
# Cambiare consistency level su account esistente
az cosmosdb update \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --default-consistency-level BoundedStaleness \
  --max-interval 10 \
  --max-staleness-prefix 200000
```

## Database e Container

```bash
# Creare database
az cosmosdb sql database create \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --name myapp-db

# Creare container con throughput provisionato
az cosmosdb sql container create \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --partition-key-path "/customerId" \
  --throughput 1000

# Creare container con Autoscale
az cosmosdb sql container create \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name sessions \
  --partition-key-path "/userId" \
  --max-throughput 10000

# Creare container Serverless (per account serverless)
# Nota: il tipo serverless si configura a livello di account al momento della creazione
az cosmosdb sql container create \
  --resource-group $RG \
  --account-name cosmos-serverless \
  --database-name myapp-db \
  --name events \
  --partition-key-path "/deviceId"

# TTL a livello container (in secondi, -1 = nessun default)
az cosmosdb sql container update \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name sessions \
  --ttl 86400
```

## Partition Key: Scelta Critica

La partition key determina come i dati vengono distribuiti fisicamente nelle partizioni. Una scelta sbagliata causa "hot partitions" (sovraccarico su poche partizioni) e degrada le performance.

### Regole per una Buona Partition Key

```
Buona partition key:
✓ Alta cardinalità (molti valori diversi): /userId, /deviceId, /orderId
✓ Distribuisce uniformemente write e read
✓ Appare in quasi tutte le query (evita cross-partition queries)
✓ Non causa "hot partition" (nessun singolo valore riceve il 100% del traffico)

Cattiva partition key:
✗ Bassa cardinalità: /country (solo ~200 valori), /status (active/inactive)
✗ Valore monotonicamente crescente senza distribuzione: /timestamp
✗ Non presente nelle query frequenti
✗ Un valore riceve la maggior parte del traffico: /userId se il 90% delle richieste è per userId="admin"
```

```python
# Esempio buono: ordini partitionati per customerId
{
  "id": "order-001",
  "customerId": "cust-abc123",   # partition key
  "items": [...],
  "total": 129.99,
  "status": "completed"
}

# Esempio problema: tutti gli ordini del giorno nella stessa partizione
{
  "id": "order-001",
  "date": "2026-02-26",   # BAD partition key: tutti gli ordini di oggi qui
  "customerId": "cust-abc123",
  "total": 129.99
}

# Soluzione con synthetic partition key per distribuire:
{
  "id": "order-001",
  "partitionKey": "cust-abc123_2026-02-26",  # combina userId + date
  ...
}
```

### Limiti e Hierarchical Partition Keys

Ogni *logical partition* (tutti i documenti con lo stesso valore di partition key) può contenere al massimo **20 GB** e le transazioni (stored procedure, transactional batch) operano solo al suo interno. Le logical partition sono mappate su *physical partition* (max ~10.000 RU/s e 50 GB ciascuna) che Cosmos DB crea e splitta in automatico. Se una singola key rischia di superare i limiti (es. tenant molto grandi), usare le **hierarchical partition keys** (fino a 3 livelli, es. `/tenantId`, `/userId`, `/sessionId`): permettono di far scalare un tenant oltre 20 GB mantenendo query single-partition sul prefisso.

## Request Units (RU)

Le Request Unit (RU) sono l'unità di misura del throughput in Cosmos DB. 1 RU = lettura di un documento da 1 KB. Le operazioni di scrittura, query complesse e documenti grandi costano più RU.

| Operazione | RU Approssimate |
|---|---|
| Lettura puntuale 1KB (GET by id + partition key) | 1 RU |
| Scrittura 1KB | ~5 RU |
| Query semplice cross-partition | 10-100 RU |
| Query con ORDER BY cross-partition | 20-200 RU |
| Scrittura 10KB | ~50 RU |

```python
# Monitorare RU consumate in Python SDK
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = CosmosClient(
    url="https://cosmos-myapp-prod.documents.azure.com",
    credential=credential
)

db = client.get_database_client("myapp-db")
container = db.get_container_client("orders")

# Lettura puntuale (più efficiente, 1 RU)
response = container.read_item(
    item="order-001",
    partition_key="cust-abc123"
)
print(f"RU consumed: {response.get_response_headers()['x-ms-request-charge']}")  # azure-cosmos >= 4.7

# Upsert
item = {
    "id": "order-002",
    "customerId": "cust-abc123",
    "total": 45.00,
    "status": "pending"
}
response = container.upsert_item(body=item)

# Query (più costosa)
query = "SELECT * FROM c WHERE c.customerId = @customerId AND c.status = 'completed'"
items = container.query_items(
    query=query,
    parameters=[{"name": "@customerId", "value": "cust-abc123"}],
    partition_key="cust-abc123"  # partition key elimina cross-partition = più efficiente
)
```

!!! warning "Entra ID richiede RBAC del data plane"
    `DefaultAzureCredential` funziona solo se l'identità ha un ruolo **Cosmos DB native RBAC** (non basta il ruolo Azure RBAC "Contributor", che copre solo il control plane). In produzione assegnare il ruolo e disabilitare le chiavi di account (`disableLocalAuth`) per eliminare secret condivisi:

    ```bash
    az cosmosdb sql role assignment create \
      --resource-group $RG --account-name $COSMOS_ACCOUNT \
      --role-definition-name "Cosmos DB Built-in Data Contributor" \
      --principal-id <object-id-managed-identity> --scope "/"
    ```

## Modelli di Throughput

| Modello | Scaling | Billing | Use Case |
|---|---|---|---|
| **Provisioned** | Fisso (es: 1000 RU/s) | Per ora, anche se idle | Workload prevedibili, SLA garantito |
| **Autoscale** | Da 0.1x a max (es: 100-1000 RU/s) | Per ora al max raggiunto | Workload variabili, picchi improvvisi |
| **Serverless** | Auto, burst fino a 5.000 RU/s per container | Per RU effettivamente consumate | Dev/test, workload sporadici, spike brevi |

!!! note "Limiti Serverless"
    Solo **una regione**, storage max 1 TB per container, nessun Free Tier sullo stesso account e la modalità non è modificabile dopo la creazione dell'account (serve migrazione dati).

```bash
# Creare account serverless
az cosmosdb create \
  --resource-group $RG \
  --name cosmos-serverless-dev \
  --kind GlobalDocumentDB \
  --locations regionName=westeurope failoverPriority=0 \
  --capabilities EnableServerless

# Verificare throughput corrente di un container
az cosmosdb sql container throughput show \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders

# Aumentare throughput manualmente (provisioned)
az cosmosdb sql container throughput update \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --throughput 5000

# Migrare da provisioned a autoscale
az cosmosdb sql container throughput migrate \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --throughput-type autoscale
```

## Change Feed

Il Change Feed è un log persistente delle modifiche (insert/update) ai documenti in un container Cosmos DB, **ordinato per modifica all'interno di ciascuna partition key** (non globalmente). Alimenta pattern event-driven e di sync tra sistemi.

!!! warning "Delete non visibili"
    In modalità *latest version* (default) le cancellazioni e le versioni intermedie non compaiono. Per propagare i delete usare un soft-delete (flag `deleted: true` + TTL sul container) oppure la modalità *all versions and deletes* (richiede continuous backup).

```python
# Leggere Change Feed con Azure Functions (CosmosDB Trigger)
import azure.functions as func
import logging

@app.cosmos_db_trigger(
    arg_name="documents",
    database_name="myapp-db",
    container_name="orders",
    connection="CosmosDBConnection",
    create_lease_container_if_not_exists=True
)
def cosmosdb_trigger(documents: func.DocumentList):
    if documents:
        for doc in documents:
            logging.info(f"Processing changed document: {doc['id']}")
            # Sincronizzare con altro sistema, inviare evento, aggiornare cache
            process_order_change(doc)
```

```python
# Leggere Change Feed con SDK (modalità pull)
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

client = CosmosClient(url=COSMOS_URL, credential=DefaultAzureCredential())
container = client.get_database_client("myapp-db").get_container_client("orders")

# Iterare change feed dall'inizio
feed_iterator = container.query_items_change_feed(start_time="Beginning")
for change in feed_iterator:
    print(f"Changed: {change['id']} - {change['status']}")
    # Salvare continuation token per resume
```

## Cosmos DB Free Tier

Ogni subscription Azure ha diritto a **1 account Cosmos DB Free Tier**:
- 1000 RU/s guaranteed throughput gratuiti (permanente, non trial)
- 25 GB storage gratuito (permanente)
- Utile per piccoli progetti in produzione, dev/test, portfolio projects
- Non combinabile con account serverless; l'eccedenza oltre 1000 RU/s / 25 GB è fatturata normalmente

```bash
az cosmosdb create \
  --resource-group $RG \
  --name cosmos-free-tier \
  --kind GlobalDocumentDB \
  --locations regionName=westeurope failoverPriority=0 \
  --enable-free-tier true
```

## Backup Continuo (PITR)

```bash
# Backup continuo con retention 30 giorni (--backup-policy-type Continuous --continuous-tier Continuous30Days)
# Il restore crea SEMPRE un nuovo account; i dati vanno poi riallineati/rimappati dall'applicazione
az cosmosdb restore \
  --resource-group $RG \
  --target-database-account-name cosmos-restored \
  --account-name $COSMOS_ACCOUNT \
  --restore-timestamp "2026-02-25T10:00:00Z" \
  --location westeurope \
  --databases-to-restore name=myapp-db collections=orders
```

Il PITR (point-in-time restore) è il default consigliato rispetto al backup *periodic*: permette di tornare a un istante preciso (es. subito prima di un `DELETE` errato). Il tier 7 giorni è gratuito, quello 30 giorni è a pagamento.

## Integrated Cache (Dedicated Gateway)

Il Dedicated Gateway è un cluster di nodi di calcolo dedicati (non una cache in-process nell'app) che si pone davanti al backend e mantiene una cache di point read e query: un *cache hit* costa **0 RU** e riduce la latency. Disponibile per account NoSQL API; la cache funziona solo con consistency Session o Eventual e le richieste devono passare dall'endpoint dedicato (`<account>.sqlx.cosmos.azure.com`), in modalità Gateway.

```bash
# Aggiungere Dedicated Gateway (cache)
az cosmosdb service create \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --name SqlDedicatedGateway \
  --kind SqlDedicatedGateway \
  --count 1 \
  --size Cosmos.D4s
```

```python
# Connessione tramite dedicated gateway: cambia l'endpoint (sqlx), non il codice di accesso
client = CosmosClient(
    url="https://cosmos-myapp-prod.sqlx.cosmos.azure.com",
    credential=DefaultAzureCredential()
)
```

In .NET/Java impostare inoltre `ConnectionMode.Gateway` e, se serve, `MaxIntegratedCacheStaleness` per tollerare dati più vecchi in cache.

## Private Endpoint per Cosmos DB

```bash
az network private-endpoint create \
  --resource-group $RG \
  --name pep-cosmos-prod \
  --vnet-name vnet-prod \
  --subnet snet-private-endpoints \
  --private-connection-resource-id $(az cosmosdb show --resource-group $RG --name $COSMOS_ACCOUNT --query id -o tsv) \
  --group-ids Sql \
  --connection-name conn-cosmos-prod

# DNS zona privata per Cosmos DB
az network private-dns zone create \
  --resource-group $RG \
  --name "privatelink.documents.azure.com"

# Collegare la zona alla VNet e registrare il record A del private endpoint (senza questi due passi
# il nome risolve ancora l'IP pubblico)
az network private-dns link vnet create \
  --resource-group $RG --zone-name "privatelink.documents.azure.com" \
  --name link-vnet-prod --virtual-network vnet-prod --registration-enabled false

az network private-endpoint dns-zone-group create \
  --resource-group $RG --endpoint-name pep-cosmos-prod --name default \
  --private-dns-zone "privatelink.documents.azure.com" --zone-name cosmos
```

## Synapse Link (HTAP — Analytical Store)

!!! warning "Synapse Link: non per nuovi progetti"
    Microsoft raccomanda **Cosmos DB Mirroring per Microsoft Fabric** (GA): replica quasi real-time in OneLake in formato Delta Parquet, senza consumare RU né usare l'analytical store. Quanto segue vale per carichi Synapse esistenti.

Synapse Link abilita analytics in real-time su dati operativi senza impatto sulle performance del database, copiando automaticamente i dati in un analytical store columnar (formato Parquet).

```bash
# Abilitare analytical store sull'account
az cosmosdb update \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --enable-analytical-storage true

# Abilitare analytical store su un container specifico
az cosmosdb sql container update \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --analytical-storage-ttl -1   # -1 = illimitato, >0 = TTL in secondi

# Collegare a Synapse Analytics
az synapse linked-service create \
  --workspace-name mysynapseworkspace \
  --name CosmosDBLinkedService \
  --file @cosmosdb-linked-service.json
```

## Best Practices

- Scegli la partition key con la maggiore cardinalità possibile che appare nelle query frequenti
- Usa **Session consistency** come default (eccetto casi specifici che richiedono Strong)
- Dimensiona il throughput con **Autoscale** per workload variabili; usa Provisioned fisso solo per throughput costante predicibile
- Per letture frequenti degli stessi documenti, considera **Dedicated Gateway** (cache)
- Abilita **Change Feed** per sincronizzazione con altri sistemi anziché polling
- Usa **letture puntuali** (GET by id + partition key) invece di query quando possibile: costano 1 RU invece di 10-100
- Non usare `SELECT *` nelle query: specifica solo i campi necessari
- Usare un **singleton `CosmosClient`** per applicazione (non uno per richiesta) e impostare le `preferred regions`: il client gestisce retry su 429 e failover regionale
- Usare Entra ID + RBAC del data plane e disabilitare le chiavi; i private endpoint chiudono l'accesso pubblico
- Preferire il backup **Continuous** (PITR) al periodic per account di produzione
- Per vector search (RAG): definire *vector embedding policy* e *vector index* (DiskANN/quantizedFlat) sul container in fase di creazione; escludere il path del vettore dall'indice generale

## Troubleshooting

### Scenario 1 — Request Rate Too Large (HTTP 429)

**Sintomo:** Le operazioni restituiscono `429 TooManyRequests` con header `x-ms-retry-after-ms`. Latency aumenta bruscamente, operazioni falliscono a raffica.

**Causa:** Il throughput provisionato (RU/s) è esaurito. Può essere causato da hot partition (una partition key riceve troppo traffico), query cross-partition costose, o throughput sottodimensionato.

**Soluzione:**
1. Verificare la partition key — se una singola key riceve la maggior parte del traffico, riprogettare con synthetic key
2. Aumentare temporaneamente il throughput
3. Abilitare Autoscale per assorbire i picchi automaticamente

```bash
# Controllare throughput corrente e RU consumate (metriche Azure Monitor)
az monitor metrics list \
  --resource $(az cosmosdb show --resource-group $RG --name $COSMOS_ACCOUNT --query id -o tsv) \
  --metric "TotalRequestUnits" \
  --interval PT1M \
  --aggregation Total

# Aumentare throughput del container
az cosmosdb sql container throughput update \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --throughput 5000

# Migrare a autoscale per gestire picchi
az cosmosdb sql container throughput migrate \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --throughput-type autoscale
```

Per distinguere hot partition da throughput insufficiente guardare la metrica `NormalizedRUConsumption` per partition key range: ~100% su un solo range = hot partition (aumentare le RU non risolve, serve cambiare la key); ~100% su tutti = throughput sottodimensionato. Gli SDK ritentano in automatico i 429 (rispettando `x-ms-retry-after-ms`): l'errore emerge all'app solo a retry esauriti.

---

### Scenario 2 — Query Lenta / Costo RU Elevato

**Sintomo:** Query restituisce risultati ma impiega centinaia di ms e consuma 100+ RU. L'header `x-ms-request-charge` ha valori molto alti.

**Causa:** Query cross-partition (la partition key non è nel filtro WHERE), assenza di indici compositi per ORDER BY, o uso di `SELECT *` con documenti grandi.

**Soluzione:**
1. Aggiungere la partition key al WHERE della query
2. Aggiungere indici compositi per query con ORDER BY o filtri multipli
3. Selezionare solo i campi necessari invece di `SELECT *`

```bash
# Aggiungere indice composito per query ORDER BY
az cosmosdb sql container update \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name myapp-db \
  --name orders \
  --idx '[{"indexingMode":"consistent","automatic":true,"includedPaths":[{"path":"/*"}],"excludedPaths":[{"path":"/\"_etag\"/?"}],"compositeIndexes":[[{"path":"/customerId","order":"ascending"},{"path":"/createdAt","order":"descending"}]]}]'
```

```python
# Query ottimizzata: partition key nel filtro + campi specifici
items = container.query_items(
    query="SELECT c.id, c.total, c.status FROM c WHERE c.customerId = @customerId AND c.status = 'completed' ORDER BY c.createdAt DESC",
    parameters=[{"name": "@customerId", "value": "cust-abc123"}],
    partition_key="cust-abc123"  # evita cross-partition scan
)
```

---

### Scenario 3 — Failover Automatico Non Avviene / Regione Non Disponibile

**Sintomo:** La regione primaria è down ma l'applicazione continua a ricevere errori invece di fare failover alla regione secondaria.

**Causa:** Il failover automatico non è abilitato, oppure l'account ha una sola regione configurata, oppure il cliente usa endpoint regione-specifici invece dell'endpoint globale. Nota: `enableAutomaticFailover` riguarda gli account single-write; con multi-region write il client SDK reindirizza le scritture alle altre regioni secondo le `preferred regions`.

**Soluzione:**
1. Verificare che `--enable-automatic-failover true` sia impostato
2. Verificare che l'applicazione usi l'endpoint globale (`.documents.azure.com`) non quello regionale
3. Se necessario, eseguire failover manuale

```bash
# Verificare configurazione failover
az cosmosdb show \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --query "{regions:locations, automaticFailover:enableAutomaticFailover}"

# Abilitare failover automatico
az cosmosdb update \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --enable-automatic-failover true

# Failover manuale (promuove la regione secondaria a primaria)
az cosmosdb failover-priority-change \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --failover-policies "northeurope=0" "westeurope=1"
```

---

### Scenario 4 — Documenti Non Compaiono Nelle Letture (Consistency Issues)

**Sintomo:** Un documento è stato scritto con successo (HTTP 201/200) ma una lettura immediata non lo trova, oppure due client leggono versioni diverse dello stesso documento.

**Causa:** Il consistency level è `Eventual` o `Consistent Prefix` — letture da repliche diverse possono restituire dati non aggiornati. Con `Session` il caso tipico è un'app con più istanze/pod che non propagano il *session token* dalla scrittura alla lettura successiva. In multi-region write, possono esistere conflitti di scrittura.

**Soluzione:**
1. Alzare il consistency level a `Session` (default consigliato) o `Strong` se necessario (non compatibile con multi-write); con `Session` e più istanze, propagare il session token (header `x-ms-session-token`) o usare sticky routing
2. Per multi-region write, implementare una conflict resolution policy
3. Usare sempre la partition key nelle letture puntuali per leggere dalla partizione corretta

```bash
# Verificare consistency level corrente
az cosmosdb show \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --query "consistencyPolicy"

# Impostare Session consistency (read-your-writes garantito)
az cosmosdb update \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT \
  --default-consistency-level Session
```

```python
# Lettura puntuale (get by id + partition key): instradata alla partizione corretta, il
# livello di consistency effettivo resta quello dell'account/sessione
response = container.read_item(
    item="order-001",
    partition_key="cust-abc123"
)
```

## Riferimenti

- [Documentazione Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/)
- [Partition Key Best Practices](https://learn.microsoft.com/azure/cosmos-db/partitioning-overview)
- [Request Units](https://learn.microsoft.com/azure/cosmos-db/request-units)
- [Consistency Levels](https://learn.microsoft.com/azure/cosmos-db/consistency-levels)
- [Change Feed](https://learn.microsoft.com/azure/cosmos-db/change-feed)
- [Synapse Link](https://learn.microsoft.com/azure/cosmos-db/synapse-link)
- [Prezzi Cosmos DB](https://azure.microsoft.com/pricing/details/cosmos-db/)
