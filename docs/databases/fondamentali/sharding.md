---
title: "Sharding"
slug: sharding
category: databases
tags: [sharding, distribuzione, scalabilità, partitioning, hotspot, resharding]
search_keywords: [database sharding, horizontal partitioning, vertical partitioning, shard key, partition key, range sharding, hash sharding, directory sharding, consistent hashing, hotspot shard, cross shard query, scatter gather, resharding, vitess, citus, mongodb sharding, dynamodb partitions, read write amplification, secondary index sharding]
parent: databases/fondamentali/_index
related: [databases/fondamentali/acid-base-cap, databases/fondamentali/modelli-dati, databases/nosql/cassandra, databases/nosql/mongodb, databases/sql-avanzato/partitioning]
official_docs: https://vitess.io/docs/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Sharding

## Panoramica

Lo sharding è la distribuzione orizzontale dei dati su più nodi (shard), dove ogni nodo possiede un sottoinsieme esclusivo dei dati. È la tecnica che permette di scalare oltre i limiti di un singolo server — in termini di volume dati, write throughput, e numero di connessioni.

Lo sharding risolve problemi di scalabilità ma introduce costi significativi: la shard key diventa un vincolo architetturale quasi impossibile da cambiare, le query cross-shard diventano costose, e le transazioni distribuite perdono le garanzie ACID.

!!! warning "Sharding come ultima risorsa"
    Prima dello sharding, esaurire le alternative: ottimizzare query e indici, aggiungere read replicas, connection pooling, vertical scaling, table partitioning locale. Lo sharding aumenta la complessità operativa in modo non lineare.

## Partitioning vs Sharding

**Partitioning**: dividere una tabella in più segmenti (per righe) sullo **stesso nodo**. Vedi [Partitioning SQL](../sql-avanzato/partitioning.md). Migliora le performance di query e manutenzione (partition pruning, drop veloce di dati vecchi) ma non scala oltre il singolo server.

**Sharding**: distribuire i dati (per righe) su **nodi diversi**. Scala sia il volume che il throughput di scrittura, perché ogni nodo gestisce solo la propria porzione.

!!! note "Orizzontale vs verticale"
    Sia partitioning che sharding sono **orizzontali** (si dividono le righe). Il partitioning **verticale** è un'altra cosa: separa le *colonne* di una tabella (es. colonne rare o BLOB in una tabella a parte) o interi domini in database distinti (database-per-service).

---

## Strategie di Sharding

### Range Sharding

I dati vengono distribuiti in range ordinati del valore della shard key:

```
Shard 1: user_id [1       – 1.000.000)
Shard 2: user_id [1.000.000 – 2.000.000)
Shard 3: user_id [2.000.000 – 3.000.000)
```

**Vantaggio**: le range query sulla shard key sono efficienti (vanno su pochi shard contigui). Utile per time-series (shard per data).

**Svantaggio critico: hotspot**. Se la shard key ha un pattern di accesso non uniforme — es. i nuovi utenti (ID alti) sono più attivi — un singolo shard riceve la maggior parte del traffico.

```
Range sharding su created_at:
Shard 1: Jan-Jun 2023  → quasi inattivo
Shard 2: Jul-Dec 2023  → quasi inattivo
Shard 3: Jan-Jun 2024  → quasi inattivo
Shard 4: Jul-Dec 2024  → 95% del traffico (dati recenti)
```

### Hash Sharding

Applica una funzione hash alla shard key per determinare lo shard di destinazione:

```python
shard_id = hash(user_id) % numero_shard

# Esempio con 4 shard
shard_id = hash(12345) % 4  → shard 2
shard_id = hash(67890) % 4  → shard 0
shard_id = hash(11111) % 4  → shard 3
```

!!! warning "Il modulo non scala con il numero di shard"
    Con `hash(k) % N`, passare da N a N+1 cambia lo shard di quasi **tutte** le chiavi (circa N/(N+1)): un resharding diventa una migrazione quasi totale. Per questo i sistemi reali usano consistent hashing o un numero elevato di slot/chunk fissi (es. 16384 hash slot in Redis Cluster) assegnati ai nodi. Nota: la funzione `hash()` built-in di Python non è stabile tra processi (randomizzazione); in produzione usare un hash deterministico (murmur3, xxhash, CRC).

**Vantaggio**: distribuzione uniforme del carico — nessun hotspot per shard key con buona distribuzione.

**Svantaggio**: le range query diventano scatter-gather (devono interrogare tutti gli shard):

```sql
-- Query range su hash-sharded table:
SELECT * FROM ordini WHERE created_at BETWEEN '2024-01' AND '2024-03';
-- → Broadcast a tutti gli shard, unione dei risultati
-- → Latenza = MAX(latenza_shard_1, shard_2, ..., shard_N)
```

### Consistent Hashing

Variante dell'hash sharding che minimizza il re-hashing quando si aggiungono o rimuovono shard. I nodi e le chiavi vengono mappati su un "ring" — ogni chiave appartiene al primo nodo nel senso orario.

```
Ring hash:
     key A ──→ Nodo 2
     key B ──→ Nodo 3
     key C ──→ Nodo 1

Aggiunta Nodo 4 tra Nodo 2 e Nodo 3:
  Solo le chiavi che erano assegnate a Nodo 3 nel range di Nodo 4 vengono spostate
  → Spostamento minimo dei dati (1/N delle chiavi, con N nodi)
```

Usato da: Apache Cassandra (token ring con virtual nodes), Dynamo (paper originale di Amazon, da cui deriva il modello; DynamoDB gestisce oggi il partizionamento in modo interno e trasparente). **Redis Cluster** non usa un ring vero e proprio: divide lo spazio in 16384 *hash slot* (`CRC16(key) mod 16384`) assegnati ai nodi, e lo resharding sposta slot interi. MongoDB usa invece chunk (range o hash) gestiti dal balancer.

### Directory Sharding

Una lookup table centralizzata mappa ogni chiave (o range) allo shard corretto:

```
Directory:
  tenant_id = "acme"     → shard-db-5
  tenant_id = "bigcorp"  → shard-db-2
  tenant_id = "startup"  → shard-db-1
```

**Vantaggio**: massima flessibilità — uno shard può essere spostato aggiornando solo la directory. Può gestire shard di dimensione disuguale.

**Svantaggio**: la directory è un single point of failure e un collo di bottiglia — ogni query deve prima consultare la directory. Richiede caching aggressivo.

---

## Scelta della Shard Key — La Decisione più Critica

La shard key è (quasi) permanente. Cambiarla richiede di riscrivere tutti i dati — un'operazione costosa e rischiosa. Alcuni sistemi oggi la rendono fattibile online (MongoDB ≥ 5.0 `reshardCollection`, ≥ 4.4 `refineCollectionShardKey` per aggiungere suffissi), ma resta una copia completa del dataset: costo, tempo e carico aggiuntivo restano elevati.

### Criteri di valutazione

**1. Cardinalità**: deve avere abbastanza valori distinti per distribuire su tutti gli shard. `user_id` (milioni di valori) ✓. `country` (200 valori) ✗.

**2. Distribuzione**: i valori devono essere distribuiti uniformemente. `user_id` con accesso uniforme ✓. `created_at` con accesso concentrato sui dati recenti ✗.

**3. Query isolation**: la maggior parte delle query deve poter andare su un singolo shard. `tenant_id` per SaaS multi-tenant ✓ (ogni tenant su un shard). `product_category` per e-commerce con query cross-category ✗.

**4. Granularità**: la chiave deve permettere un numero sufficiente di "chunk" per distribuzione futura. Un UUID o un hash a 64 bit permettono milioni di chunk ✓.

```
# Schema multi-tenant: shard key = tenant_id
Shard 1: tenant A, B, C (dati completamente isolati)
Shard 2: tenant D, E, F
Shard 3: tenant G, H, I

Query "tutti gli ordini del tenant A" → va direttamente su Shard 1 ✓
Query "tutti gli ordini di tutti i tenant" → broadcast su tutti gli shard ✗
```

---

## Problemi dello Sharding

### Cross-Shard Queries (Scatter-Gather)

```sql
-- Query su un singolo shard (efficiente):
SELECT * FROM ordini WHERE tenant_id = 'acme' AND created_at > '2024-01-01';
-- → shard lookup: tenant 'acme' è su Shard 2 → 1 query

-- Query cross-shard (costosa):
SELECT SUM(importo) FROM ordini WHERE created_at BETWEEN '2024-01' AND '2024-12';
-- → broadcast a tutti gli N shard
-- → attesa del risultato di ognuno
-- → aggregazione locale del risultato
-- → latenza = max(shard_latencies) + aggregation time
```

**Mitigazione**: mantenere indici globali (come in DynamoDB Global Secondary Indexes), denormalizzare i dati per portarli sullo stesso shard, o accettare che alcune query siano costose per design.

### Transazioni Distribuite

```sql
-- Transazione atomica cross-shard:
BEGIN;
  UPDATE ordini SET status = 'shipped' WHERE id = 123;  -- Shard 1
  UPDATE inventario SET quantita = quantita - 1 WHERE id = 456;  -- Shard 3
COMMIT;
-- → richiede 2PC o Saga pattern — nessuna delle due è gratis
```

**Approcci pratici**:
- Progettare il modello per evitare transazioni cross-shard (collocare dati correlati sullo stesso shard)
- Usare Saga/Event Sourcing per eventual consistency
- Accettare che alcune operazioni siano "best-effort" con compensazione

### Secondary Indexes su Database Shardati

Gli indici secondari su sistemi shardati hanno due implementazioni:

**Local (document-partitioned) index** (es. indici secondari di Cassandra, MongoDB): ogni shard indicizza solo i propri dati. Scrittura economica (un solo shard), ma una query sull'indice senza shard key = scatter-gather su tutti gli shard. Nota: il DynamoDB LSI è un caso diverso — condivide la partition key della tabella e si interroga sempre dentro una singola partition.

**Global (term-partitioned) index** (es. DynamoDB GSI, lookup Vindex di Vitess): l'indice è distribuito indipendentemente dai dati, per valore indicizzato. Query su indice secondario = 1 lookup mirato. Costo: write amplification (ogni write aggiorna anche l'indice, su uno shard diverso). In DynamoDB il GSI è aggiornato in modo asincrono (eventual consistency); in Vitess il lookup Vindex è mantenuto nella stessa transazione/flusso di scrittura, con costo di una scrittura cross-shard.

---

## Resharding — La Sfida Operativa

Quando un shard cresce troppo o il carico è sbilanciato, è necessario fare resharding:

```
Prima del resharding:
  Shard 1: 80% carico, 500GB  ← HOT SHARD
  Shard 2: 15% carico, 100GB
  Shard 3: 5%  carico, 50GB

Dopo il resharding:
  Shard 1a: 40% carico, 250GB  ← Split di Shard 1
  Shard 1b: 40% carico, 250GB
  Shard 2:  15% carico, 100GB
  Shard 3:  5%  carico, 50GB
```

Il resharding richiede:
1. Copia snapshot dei dati dai vecchi ai nuovi shard (il vecchio shard continua a servire traffico)
2. Sincronizzazione continua delle modifiche successive allo snapshot tramite CDC (Change Data Capture: lettura di binlog/WAL/oplog). Alternativa meno robusta: doppia scrittura applicativa, soggetta a divergenze
3. Verifica di consistenza (diff dei dati tra sorgente e destinazione)
4. Cutover: breve blocco delle scritture, aggiornamento della routing table, switch del traffico (con possibilità di reverse replication per il rollback)
5. Rimozione dei dati dal vecchio shard

**Vitess** (usato da YouTube, Slack, GitHub per parti dell'infrastruttura) automatizza questo flusso su MySQL con i workflow `Reshard`/`MoveTables` basati su VReplication, con cutover di pochi secondi. Nei database sharded nativi (MongoDB, Cassandra, CockroachDB, TiDB, YugabyteDB, Spanner) lo split/rebalance dei chunk/range è invece continuo e gestito dal sistema.

!!! tip "Alternative con auto-sharding (NewSQL)"
    I sistemi *distributed SQL* (CockroachDB, YugabyteDB, TiDB, Google Spanner) frammentano automaticamente i dati in range e li ribilanciano, con transazioni ACID distribuite. Eliminano gran parte del lavoro manuale di sharding applicativo, a fronte di latenza di commit più alta per le scritture cross-range e di un modello operativo diverso dal PostgreSQL/MySQL "classico".

---

## Implementazioni Pratiche

### MongoDB Sharding

MongoDB implementa sharding nativo con un cluster coordinator:

```javascript
// Shard sulla collection ordini usando hashed shard key
// (da MongoDB 6.0 sh.enableSharding() non è più necessario: shardCollection basta)
sh.shardCollection("myapp.ordini", { "tenant_id": "hashed" })

// Verifica distribuzione di dati e documenti per shard
db.ordini.getShardDistribution()

// Cambiare shard key online (MongoDB ≥ 5.0): copia completa della collection
db.adminCommand({ reshardCollection: "myapp.ordini", key: { "tenant_id": 1, "created_at": 1 } })
```

Il **balancer** sposta automaticamente i chunk tra shard per equalizzare la distribuzione. Una hashed shard key evita hotspot da chiavi monotone ma rende le range query scatter-gather.

### Citus (PostgreSQL Sharding)

Citus è un'estensione PostgreSQL che aggiunge sharding trasparente:

```sql
-- Installa estensione (richiede shared_preload_libraries = 'citus' e riavvio)
CREATE EXTENSION citus;

-- Crea tabella distribuita (hash sharding sulla distribution column)
SELECT create_distributed_table('ordini', 'tenant_id');

-- Tabelle di piccole dimensioni replicate su tutti i nodi (per join locali)
SELECT create_reference_table('paesi');

-- Dopo aver aggiunto worker: ribilanciare gli shard
SELECT citus_rebalance_start();

-- Le query rimangono SQL standard
SELECT COUNT(*), SUM(importo)
FROM ordini
WHERE tenant_id = 'acme'
GROUP BY status;
-- → routing automatico al shard corretto
```

Le tabelle **co-locate** (stessa distribution column, `colocate_with`) permettono join e transazioni locali a un singolo shard. Citus è open source ed è la base di Azure Cosmos DB for PostgreSQL; dalla 12 supporta anche lo *schema-based sharding* (un tenant = uno schema).

### DynamoDB Partitioning

DynamoDB gestisce il sharding automaticamente (transparent partitioning) basandosi sulla partition key. Il limite è **3000 RCU e 1000 WCU per partition** (e ~10 GB per partition). L'*adaptive capacity* e lo split automatico per throughput mitigano gli hotspot, ma una singola partition key resta vincolata a questi limiti: una chiave molto "calda" va comunque distribuita.

```python
# Evitare hot partitions in DynamoDB
# Pattern: aggiungere un suffisso random alla partition key

import random

# PROBLEMATICO: tutti i write di oggi sulla stessa partition
item = {
    "pk": f"EVENT#{today}",  # hotspot se molti eventi al giorno
    "sk": event_id
}

# SOLUZIONE: sharding del timestamp con suffix
suffix = random.randint(0, 9)  # 10 shard del giorno
item = {
    "pk": f"EVENT#{today}#{suffix}",  # distribuito su 10 partition
    "sk": event_id
}

# Per leggere tutti gli eventi del giorno: scatter-gather su 10 partition
```

## Troubleshooting

### Scenario 1 — Hot Shard (shard sovraccarico)

**Sintomo**: un singolo shard riceve la quasi totalità del traffico. Latenza elevata, CPU/IO al limite su un nodo mentre gli altri sono idle.

**Causa**: shard key con distribuzione non uniforme (es. range sharding su `created_at`, timestamp sequenziali, tenant di dimensioni molto diverse).

**Soluzione**: identificare la shard key incriminata e valutare resharding con hash sharding o shard key composita. Nel breve periodo, splittare lo shard hot.

```bash
# MongoDB: verificare distribuzione degli chunk
mongosh --eval "db.ordini.getShardDistribution()"

# DynamoDB: consumo a livello di tabella (per le chiavi più calde usare
# CloudWatch Contributor Insights for DynamoDB)
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=ordini \
  --period 60 --statistics Sum \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T01:00:00Z

# Vitess: elenco shard e stato del keyspace
vtctldclient GetShard ks/-80
vtctldclient GetKeyspace ks
```

---

### Scenario 2 — Scatter-Gather con latenza inaccettabile

**Sintomo**: query che dovrebbero essere veloci impiegano secondi. EXPLAIN mostra fan-out su tutti gli shard.

**Causa**: la query non include la shard key nel predicato, obbligando il middleware a fare broadcast su tutti i nodi e aggregare i risultati.

**Soluzione**: riscrivere la query includendo la shard key, oppure aggiungere un global secondary index se il pattern di accesso non è modificabile.

```sql
-- Query problematica (scatter-gather su tutti gli shard):
SELECT * FROM ordini WHERE created_at > NOW() - INTERVAL '7 days';

-- Query riscritta con shard key (single-shard):
SELECT * FROM ordini
WHERE tenant_id = 'acme'               -- shard key inclusa
  AND created_at > NOW() - INTERVAL '7 days';

-- Citus: verificare piano di esecuzione
EXPLAIN (VERBOSE, ANALYZE)
  SELECT * FROM ordini WHERE created_at > NOW() - INTERVAL '7 days';
-- Cercare "Custom Scan (Citus Adaptive)" con "Task Count" = N shard
```

---

### Scenario 3 — Resharding bloccato o dati inconsistenti post-migrazione

**Sintomo**: dopo un resharding, alcune query restituiscono risultati mancanti o duplicati. Oppure il processo di migrazione non avanza.

**Causa**: replica CDC in ritardo o interrotta, oppure cutover eseguito prima che la sincronizzazione fosse completa; routing table aggiornata in modo non atomico (race condition durante il cutover); con doppia scrittura applicativa, divergenza tra le due copie.

**Soluzione**: monitorare il lag di replica, eseguire un diff dei dati prima del cutover e usare un tool che gestisca CDC e switch del traffico in modo coordinato (nessuna doppia scrittura manuale).

```bash
# Vitess (vtctldclient; vtctlclient è deprecato): stato del workflow di resharding
vtctldclient Reshard --target-keyspace ks --workflow reshard1 show
vtctldclient Reshard --target-keyspace ks --workflow reshard1 status

# Verifica che i dati coincidano prima del cutover
vtctldclient VDiff --target-keyspace ks --workflow reshard1 create
vtctldclient VDiff --target-keyspace ks --workflow reshard1 show last

# Cutover; se qualcosa va storto, reverse-traffic o cancel (prima di complete)
vtctldclient Reshard --target-keyspace ks --workflow reshard1 switchtraffic
vtctldclient Reshard --target-keyspace ks --workflow reshard1 reversetraffic
vtctldclient Reshard --target-keyspace ks --workflow reshard1 cancel
```

```javascript
// MongoDB: stato di balancer e migrazioni di chunk
sh.status()
sh.isBalancerRunning()
// reshardCollection in corso:
db.getSiblingDB("admin").aggregate([{ $currentOp: { allUsers: true, localOps: false } }, { $match: { type: "op", "originatingCommand.reshardCollection": { $exists: true } } }])
```

---

### Scenario 4 — Transazione cross-shard fallita parzialmente

**Sintomo**: un'operazione che aggiorna dati su più shard lascia il sistema in uno stato inconsistente (una parte eseguita, l'altra no).

**Causa**: assenza di coordinamento transazionale distribuito. Il 2PC non è supportato dal middleware, oppure uno shard è temporaneamente irraggiungibile.

**Soluzione**: implementare il pattern Saga con compensating transactions, oppure ridisegnare il modello dati per collocare i dati correlati sullo stesso shard.

```python
# Saga pattern con compensating transaction
def trasferisci_ordine(order_id, from_tenant, to_tenant):
    step1_done = False
    try:
        # Step 1: aggiorna shard del tenant sorgente
        shard_from.execute(
            "UPDATE ordini SET tenant_id = %s WHERE id = %s",
            (to_tenant, order_id)
        )
        step1_done = True
        # Step 2: aggiorna shard del tenant destinazione
        shard_to.execute(
            "INSERT INTO ordini_log VALUES (%s, %s, NOW())",
            (order_id, to_tenant)
        )
    except Exception:
        # Compensating transaction: annulla step 1 solo se è stato eseguito.
        # Deve essere idempotente e ritentabile (anche la compensazione può fallire).
        if step1_done:
            shard_from.execute(
                "UPDATE ordini SET tenant_id = %s WHERE id = %s",
                (from_tenant, order_id)
            )
        raise
```

## Relazioni

??? info "Partitioning SQL — Partizionamento locale"
    Partizionamento su singolo nodo come alternativa allo sharding.

    **Approfondimento →** [Partitioning](../sql-avanzato/partitioning.md)

??? info "Cassandra — Sharding nativo con consistent hashing"
    Come Cassandra distribuisce i dati con virtual nodes.

    **Approfondimento →** [Cassandra](../nosql/cassandra.md)

??? info "MongoDB — Sharded cluster"
    Architettura mongos/config server/shard, chunk e balancer.

    **Approfondimento →** [MongoDB](../nosql/mongodb.md)

## Riferimenti

- [Vitess — MySQL Sharding](https://vitess.io/docs/)
- [Citus — PostgreSQL Sharding](https://docs.citusdata.com/)
- [Amazon DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Designing Data-Intensive Applications — Cap. 6](https://dataintensive.net/)
