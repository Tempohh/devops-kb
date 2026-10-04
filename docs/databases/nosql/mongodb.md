---
title: "MongoDB"
slug: mongodb
category: databases
tags: [mongodb, nosql, document, aggregation, replica-set, sharding]
search_keywords: [mongodb document store, mongodb aggregation pipeline, mongodb indexes, mongodb replica set, mongodb sharding, mongodb atlas, mongodb transactions, mongodb schema design, embedding vs referencing, mongodb oplog, mongodb change streams, mongodb atlas search, mongodb timeseries collection, bson, mongosh, mongostat, mongodump, mongorestore, mongodb compass, wiredtiger storage engine, mongodb collation, mongodb text search, mongodb gridfs]
parent: databases/nosql/_index
related: [databases/fondamentali/modelli-dati, databases/fondamentali/sharding, databases/nosql/redis]
official_docs: https://www.mongodb.com/docs/
status: needs-review
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# MongoDB

## Panoramica

MongoDB è il document store più diffuso: archivia dati come documenti BSON (JSON binario), raggruppati in collection. Non c'è schema fisso — ogni documento può avere campi diversi. Questa flessibilità è il punto di forza su dati eterogenei (catalogo prodotti, CMS, user profiles) e su modelli che evolvono frequentemente.

Il modello relazionale normalizza i dati in tabelle collegate via JOIN. MongoDB favorisce l'**embedding** — mettere i dati correlati nello stesso documento — per eliminare i JOIN e accedere a tutto in una sola lettura. La regola d'oro: se leggi sempre insieme due entità, embedded; se le leggi separatamente o una ha cardinalità alta, referencing.

!!! warning "MongoDB non è un database relazionale senza schema"
    MongoDB supporta transazioni ACID multi-documento da v4.0 (con replica set), ma con overhead significativo rispetto alle transazioni single-document (atomiche per default). Progettare lo schema per minimizzare le transazioni multi-documento.

## Concetti Chiave

### Documento e Collection

```javascript
// Documento MongoDB (BSON in memoria, JSON nell'interfaccia)
{
    "_id": ObjectId("65a1b2c3d4e5f67890123456"),  // ID univoco auto-generato
    "titolo": "Redis per DevOps",
    "autore": {                                    // Documento embedded
        "nome": "Andrea",
        "email": "andrea@example.com"
    },
    "tag": ["redis", "nosql", "devops"],          // Array
    "pubblicato": true,
    "created_at": ISODate("2024-01-15T10:00:00Z"),
    "visualizzazioni": 1542
}
```

### Embedding vs Referencing

```javascript
// EMBEDDING — dati letti sempre insieme, cardinalità bassa
// Ordine con prodotti embedded (1 documento = 1 lettura)
{
    "_id": ObjectId("..."),
    "cliente_id": "user-123",
    "totale": 199.50,
    "prodotti": [                      // embedded, mai più di 100 elementi
        { "sku": "P001", "nome": "Redis in Action", "prezzo": 49.50, "qty": 2 },
        { "sku": "P002", "nome": "MongoDB Guide",  "prezzo": 59.50, "qty": 1 }
    ]
}

// REFERENCING — entità indipendenti, cardinalità alta, aggiornamento frequente
// Post con commenti: 1000+ commenti → embedding non scalabile
{
    "_id": "post-1",
    "titolo": "...",
    // commenti: NON embedded — referencing via collection separata
}
{
    // collection: commenti
    "_id": ObjectId("..."),
    "post_id": "post-1",    // foreign key manuale
    "testo": "...",
    "autore": "alice"
}
```

---

## CRUD Operations

```javascript
// mongosh — shell interattiva

// INSERT
db.articoli.insertOne({ titolo: "Redis", tag: ["cache", "nosql"] })
db.articoli.insertMany([{ titolo: "A" }, { titolo: "B" }])

// FIND (equivalente di SELECT)
db.articoli.findOne({ _id: ObjectId("...") })

db.articoli.find(
    { tag: "nosql", pubblicato: true },         // filter
    { titolo: 1, "autore.nome": 1, _id: 0 }    // projection (1=includi, 0=escludi)
).sort({ created_at: -1 }).limit(10)

// Operatori di confronto
db.prodotti.find({
    prezzo: { $gte: 10, $lte: 100 },   // 10 <= prezzo <= 100
    categoria: { $in: ["elettronica", "informatica"] },
    descrizione: { $exists: true }
})

// UPDATE
db.articoli.updateOne(
    { _id: ObjectId("...") },
    {
        $set: { pubblicato: true },            // aggiorna campi
        $inc: { visualizzazioni: 1 },          // incremento atomico
        $push: { tag: "featured" },            // aggiunge elemento all'array
        $currentDate: { modified_at: true }    // imposta data corrente
    }
)

// Upsert: insert se non esiste, update se esiste
db.counters.updateOne(
    { _id: "visite:homepage" },
    { $inc: { count: 1 } },
    { upsert: true }
)

// DELETE
db.log.deleteMany({ created_at: { $lt: new Date("2023-01-01") } })
```

---

## Aggregation Pipeline

L'aggregation pipeline è il modo principale per analisi e trasformazioni complesse — alternativa ai GROUP BY, JOIN e subquery SQL:

```javascript
db.ordini.aggregate([
    // Stage 1: FILTER (equivalente WHERE)
    { $match: {
        created_at: { $gte: ISODate("2024-01-01") },
        stato: "completato"
    }},

    // Stage 2: JOIN (equivalente LEFT JOIN con collection clienti)
    { $lookup: {
        from: "clienti",
        localField: "cliente_id",
        foreignField: "_id",
        as: "cliente"
    }},
    { $unwind: "$cliente" },    // array [cliente] → oggetto cliente

    // Stage 3: GROUP BY + aggregazioni
    { $group: {
        _id: "$cliente.regione",
        fatturato_totale: { $sum: "$totale" },
        num_ordini: { $count: {} },
        avg_ordine: { $avg: "$totale" },
        clienti_unici: { $addToSet: "$cliente_id" }
    }},

    // Stage 4: computed fields
    { $addFields: {
        num_clienti_unici: { $size: "$clienti_unici" }
    }},

    // Stage 5: SORT e LIMIT
    { $sort: { fatturato_totale: -1 } },
    { $limit: 10 },

    // Stage 6: reshape output
    { $project: {
        regione: "$_id",
        fatturato_totale: { $round: ["$fatturato_totale", 2] },
        num_ordini: 1,
        avg_ordine: { $round: ["$avg_ordine", 2] },
        num_clienti_unici: 1,
        _id: 0
    }}
])
```

---

## Indici

```javascript
// Indice singolo
db.articoli.createIndex({ created_at: -1 })   // -1 = descending

// Indice composto (ordine importa; regola ESR: Equality, Sort, Range.
// Qui: uguaglianza su tag, poi ordinamento per data)
db.articoli.createIndex({ tag: 1, created_at: -1 })

// Indice unique
db.utenti.createIndex({ email: 1 }, { unique: true })

// Indice parziale — solo sui documenti pubblicati (più piccolo, più veloce)
db.articoli.createIndex(
    { created_at: -1 },
    { partialFilterExpression: { pubblicato: true } }
)

// Indice TTL — elimina automaticamente documenti dopo N secondi
db.sessioni.createIndex(
    { created_at: 1 },
    { expireAfterSeconds: 86400 }    // elimina dopo 24h
)

// Text index per full-text search
db.articoli.createIndex({ titolo: "text", contenuto: "text" })
db.articoli.find({ $text: { $search: "redis nosql" } }, { score: { $meta: "textScore" } })
           .sort({ score: { $meta: "textScore" } })

// EXPLAIN per analizzare query
db.articoli.find({ tag: "nosql" }).explain("executionStats")
// Verificare: IXSCAN (buono) vs COLLSCAN (brutte notizie)
```

---

## Replica Set — Alta Disponibilità

```
Primary          Secondary 1       Secondary 2
   │                 │                 │
   │── oplog ───────>│                 │
   │── oplog ──────────────────────────>│
   │                 │                 │
   Tutte le write vanno al Primary
   Le read possono essere distribuite sui Secondary (con readPreference)
```

```javascript
// Inizializza replica set (da mongosh sul primary)
rs.initiate({
    _id: "rs0",
    members: [
        { _id: 0, host: "mongo1:27017", priority: 2 },   // preferred primary
        { _id: 1, host: "mongo2:27017", priority: 1 },
        { _id: 2, host: "mongo3:27017", priority: 1 }
    ]
})

// Stato
rs.status()
rs.hello()      // sostituisce isMaster (deprecato da 4.4.2)
```

```python
# Python — Connection string con replica set
from pymongo import MongoClient, ReadPreference

client = MongoClient(
    "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0",
    readPreference="secondaryPreferred",   # leggi dai secondary se disponibili
    w="majority",           # write concern: attendi ack dalla maggioranza
    journal=True            # write confermata dopo journal flush
)
```

### Write Concern e Read Concern

```javascript
// Write concern: quanti nodi devono confermare
db.ordini.insertOne(
    { ... },
    { writeConcern: { w: "majority", j: true, wtimeout: 5000 } }
)
// w: "majority" — durabile: sopravvive al failover
// j: true — attendere journal flush (durabilità disco)
// w: 1 — solo il primary ha scritto (può essere perso in failover).
//   Dal 5.0 il default implicito è "majority" (non se ci sono arbiter che
//   impediscono la maggioranza dei data-bearing node: allora resta 1). Prima del 5.0 era 1.

// Read concern: quale snapshot di dati leggere
db.ordini.find({}).readConcern("majority")
// "majority" — legge solo dati confermati dalla maggioranza (no dirty read)
// "local" (default) — può leggere dati non ancora confermati
// "linearizable" — garanzia più forte, più lenta
```

---

## Change Streams — CDC

Change streams permettono di reagire in tempo reale ai cambiamenti nel database:

```python
# Python — ascolta cambiamenti su una collection
with db.ordini.watch(
    pipeline=[{"$match": {"operationType": {"$in": ["insert", "update"]}}}]
) as stream:
    for change in stream:
        op = change["operationType"]
        doc = change.get("fullDocument") or change.get("updateDescription")
        print(f"{op}: {doc}")
        # Idempotency: usa change["_id"] come checkpoint per resume
```

---

## Sharding

MongoDB integra lo sharding nativo tramite `mongos` router. Il shard key determina come i documenti vengono distribuiti:

```javascript
// Abilita sharding su un database (dal 6.0 non è più necessario: shardCollection
// lo fa implicitamente; serve solo per scegliere il primary shard)
sh.enableSharding("ecommerce")

// Shard su hashed field (distribuzione uniforme)
sh.shardCollection("ecommerce.ordini", { cliente_id: "hashed" })

// Shard su range (meglio per query range, peggio per hotspot)
sh.shardCollection("ecommerce.log_eventi", { created_at: 1 })

// Stato dello sharding
sh.status()
```

Dal 5.0 la shard key si può cambiare con `reshardCollection` (online, ma costoso) e dal 4.4 raffinare con `refineCollectionShardKey`: la scelta resta comunque critica.

**Scelta del shard key** (identici principi di [Sharding](../fondamentali/sharding.md)):
- Alta cardinalità (non boolean, non enum piccolo)
- Distribuzione uniforme dei write (evitare monotonic keys su range shard)
- Query isolation: la maggior parte delle query dovrebbe includere la shard key

---

## Sicurezza

Una installazione self-managed parte **senza autenticazione**: va abilitata esplicitamente. Atlas la abilita sempre.

### Autenticazione

| Meccanismo | Edizione | Uso tipico |
|---|---|---|
| `SCRAM-SHA-256` | Community/Enterprise | Default per utenti applicativi (SCRAM-SHA-1 solo per compatibilità) |
| `x.509` | Community/Enterprise | Autenticazione client e membership interna del cluster via certificati |
| `LDAP`, `Kerberos` | Solo Enterprise | Integrazione con directory aziendale |
| `OIDC` (workforce/workload) | Solo Enterprise (da 7.0) | SSO / identità di workload cloud |

```yaml
# mongod.conf — hardening minimo
security:
  authorization: enabled            # abilita RBAC (richiede utenti)
  keyFile: /etc/mongo/keyfile       # auth interna replica set (alternativa: x509 con clusterAuthMode)
net:
  bindIp: 10.0.0.12                 # mai 0.0.0.0 senza firewall
  tls:
    mode: requireTLS
    certificateKeyFile: /etc/mongo/tls/server.pem
    CAFile: /etc/mongo/tls/ca.pem
```

!!! warning "Localhost exception"
    Con `authorization: enabled` e nessun utente, MongoDB accetta da localhost la creazione del **primo** utente admin. Crearlo subito: dopo, l'eccezione si chiude.

### RBAC

```javascript
use admin
db.createUser({
    user: "admin",
    pwd: passwordPrompt(),            // non scrivere la password in chiaro nello storico
    roles: [{ role: "userAdminAnyDatabase", db: "admin" }, "readWriteAnyDatabase"]
})

// Principio del minimo privilegio: ruolo custom per un servizio
use ecommerce
db.createRole({
    role: "ordiniWriter",
    privileges: [
        { resource: { db: "ecommerce", collection: "ordini" }, actions: ["find", "insert", "update"] }
    ],
    roles: []
})
db.createUser({ user: "svc-ordini", pwd: passwordPrompt(), roles: ["ordiniWriter"] })
```

Ruoli built-in utili: `read`, `readWrite`, `dbAdmin`, `userAdmin`, `clusterMonitor` (per exporter Prometheus), `backup`, `restore`. Evitare `root` per le applicazioni.

### Encryption at rest e in use

- **Encryption at rest nativa**: WiredTiger encryption (AES-256) è **solo Enterprise/Atlas**, con chiavi gestite da KMIP. Su Community: cifrare il volume (LUKS, dm-crypt, EBS/Azure Disk encryption).
- **Client-Side Field Level Encryption (CSFLE)**: il driver cifra campi specifici prima dell'invio; il server non vede mai il plaintext.
- **Queryable Encryption**: evoluzione di CSFLE che permette query su dati cifrati. Equality GA da 7.0, **range query** da 8.0. Le chiavi (DEK) stanno in una key vault collection, protette da una CMK in KMS esterno (AWS KMS, Azure Key Vault, GCP KMS, KMIP).
- **Auditing**: Enterprise (`auditLog`); su Community usare i log del processo e Percona Server for MongoDB, che include audit.

---

## Backup e Restore

| Strategia | Consistenza | Note |
|---|---|---|
| `mongodump`/`mongorestore` | Logica, point-in-time con `--oplog` | Adatta a dataset piccoli/medi; non cattura gli indici come dati (li ricostruisce) |
| Snapshot di volume (EBS, LVM, CSI `VolumeSnapshot`) | Crash-consistent | Con journal sullo stesso volume del dbPath lo snapshot è consistente; su sharded cluster serve coordinamento |
| Atlas Backup | Cloud backup + **Continuous PITR** | Gestito, restore a un timestamp arbitrario |
| Ops Manager / Cloud Manager | PITR | Enterprise self-managed |
| Percona Backup for MongoDB (PBM) | PITR anche su sharded cluster | Open source, oplog slicing su object storage |

```bash
# Dump consistente di un replica set (include l'oplog durante il dump)
mongodump --uri="mongodb://backup:secret@mongo1:27017/?replicaSet=rs0&authSource=admin" \
          --oplog --gzip --archive=/backup/rs0-$(date +%F).archive

# Restore con replay dell'oplog
mongorestore --uri="mongodb://admin:secret@mongo1:27017/?authSource=admin" \
             --gzip --archive=/backup/rs0-2026-10-04.archive --oplogReplay

# Point-in-time: ferma il replay a un timestamp (formato <secondi epoch>:<ordinale>)
mongorestore --oplogReplay --oplogLimit=1759560000:1 --gzip --archive=...
```

!!! warning "Limiti di mongodump"
    `--oplog` non è compatibile con `--db`/`--collection` e non produce uno snapshot coerente su un **sharded cluster** (shard e config server vanno fermati in modo coordinato o si usa PBM/Ops Manager). Un backup mai ripristinato non è un backup: schedulare restore test periodici e misurare RTO.

---

## Time Series Collection

Da 5.0: collection ottimizzate per misurazioni (metriche, IoT, log). I documenti vengono raggruppati internamente in bucket per `metaField` e tempo, con forte compressione.

```javascript
db.createCollection("metriche", {
    timeseries: {
        timeField: "ts",               // obbligatorio, tipo Date
        metaField: "host",             // identifica la serie (non cambia nel tempo)
        granularity: "seconds"         // seconds | minutes | hours
    },
    expireAfterSeconds: 2592000        // retention automatica: 30 giorni
})

db.metriche.insertOne({ ts: new Date(), host: { name: "web-1", dc: "mi1" }, cpu: 0.42 })

// Query tipica: media a finestre di 5 minuti
db.metriche.aggregate([
    { $match: { "host.name": "web-1", ts: { $gte: ISODate("2026-10-04T00:00:00Z") } } },
    { $group: {
        _id: { $dateTrunc: { date: "$ts", unit: "minute", binSize: 5 } },
        cpu_avg: { $avg: "$cpu" }
    }},
    { $sort: { _id: 1 } }
])
```

Limiti da conoscere: la `timeField`/`metaField` non si cambiano dopo la creazione; update e delete sono limitati rispetto a una collection normale; la scelta di `metaField` a bassa cardinalità e stabile è critica per l'efficienza dei bucket.

---

## Atlas Search e Vector Search

Funzionalità di **MongoDB Atlas** (cloud) basate su Apache Lucene, eseguite dal processo `mongot` accanto a `mongod`. Non fanno parte del server MongoDB Community standard: il text index nativo (sopra) resta l'alternativa self-managed.

```javascript
// Atlas Search: full-text con fuzzy, autocomplete, facet (stage $search)
db.articoli.aggregate([
    { $search: {
        index: "default",
        text: { query: "kubernetes operator", path: ["titolo", "contenuto"], fuzzy: { maxEdits: 1 } }
    }},
    { $limit: 10 },
    { $project: { titolo: 1, score: { $meta: "searchScore" } } }
])

// Atlas Vector Search: similarità su embedding (stage $vectorSearch), base per RAG
db.documenti.aggregate([
    { $vectorSearch: {
        index: "vector_index",
        path: "embedding",
        queryVector: [0.12, -0.03, /* ... */],
        numCandidates: 200,           // candidati ANN da valutare
        limit: 5
    }}
])
```

I search index si definiscono via API/UI Atlas (o `createSearchIndex`), non con `createIndex`. Il supporto a Search/Vector Search per deployment self-managed è in evoluzione: verificare la documentazione ufficiale della versione in uso prima di basarvi un design.

---

## Novità della serie 8.x

La 8.0 (ottobre 2024) è la major corrente; le release 8.x successive seguono il nuovo ciclo di rilasci rapidi.

- **Performance**: miglioramenti di throughput su read/write e bulk insert, e query time series più rapide, dichiarati da MongoDB rispetto alla 7.0 (misurare sul proprio workload).
- **Queryable Encryption**: range query su dati cifrati.
- **Sharding**: `moveCollection` e `unshardCollection` per spostare/riportare collection senza downtime applicativo; config server utilizzabile anche come shard (*embedded config server*) per ridurre i nodi minimi.
- **`bulkWrite` a livello di cluster**: un solo round-trip per scritture su più collection/namespace.
- **`defaultMaxTimeMS`**: timeout di default a livello cluster per proteggere da query runaway.
- **Upgrade**: passare per una major alla volta (7.0 → 8.0), verificare `featureCompatibilityVersion` e impostarla alla nuova versione solo dopo la validazione (`setFeatureCompatibilityVersion`).

```javascript
db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 })
// Dopo l'upgrade dei binari e la validazione:
db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true })
```

---

## MongoDB su Kubernetes

Opzioni principali:

| Operator | CRD | Note |
|---|---|---|
| MongoDB Community Operator | `MongoDBCommunity` | Open source, replica set con SCRAM/TLS; nessun sharding |
| MongoDB Enterprise Kubernetes Operator | `MongoDB`, `MongoDBMultiCluster` | Richiede Ops Manager/Cloud Manager; sharding, multi-cluster |
| MongoDB Atlas Kubernetes Operator | `AtlasDeployment` | Gestisce risorse Atlas (cloud) da manifest |
| Percona Operator for MongoDB | `PerconaServerMongoDB` | Open source, include sharding e PBM integrato |

MongoDB sta consolidando i primi due in un operator unico (*MongoDB Controllers for Kubernetes*): verificare lo stato nella documentazione ufficiale prima di scegliere.

```yaml
apiVersion: mongodbcommunity.mongodb.com/v1
kind: MongoDBCommunity
metadata:
  name: mongo-rs
spec:
  members: 3
  type: ReplicaSet
  version: "8.0.4"
  security:
    authentication:
      modes: ["SCRAM"]
  users:
    - name: app
      db: admin
      passwordSecretRef:
        name: app-password            # Secret con chiave "password"
      roles:
        - name: readWrite
          db: ecommerce
      scramCredentialsSecretName: app-scram
  statefulSet:
    spec:
      volumeClaimTemplates:
        - metadata:
            name: data-volume
          spec:
            accessModes: ["ReadWriteOnce"]
            storageClassName: fast-ssd
            resources:
              requests:
                storage: 100Gi
```

!!! tip "Regole per database stateful su K8s"
    PVC su storage a bassa latenza, `podAntiAffinity` per distribuire i membri su nodi/zone diversi, PodDisruptionBudget (`maxUnavailable: 1`), resource `requests=limits` (cache WiredTiger dimensionata sulla memoria del container), backup su object storage fuori dal cluster.
---

## Best Practices

- **Sicurezza non opzionale**: `authorization: enabled`, TLS `requireTLS`, `bindIp` ristretto, ruoli a minimo privilegio, mai MongoDB esposto su Internet (le istanze aperte sono bersaglio continuo di ransomware)
- **Backup testati**: PITR attivo e restore verificato a intervalli regolari; per sharded cluster usare strumenti coordinati (Atlas, Ops Manager, PBM)
- **Schema design prima di tutto**: a differenza di SQL, lo schema errato in MongoDB è costoso da cambiare. Modellare in base ai pattern di accesso, non alla struttura dati
- **Embedded per default, referencing quando necessario**: embedding → 1 lettura, referencing → 2 letture. Eccezioni: documento > 16MB (limite BSON), array che crescono senza limite, entità lette spesso da sole
- **Write concern majority in produzione**: `w:1` rischia perdita di dati in caso di failover — non accettabile per dati critici
- **Indice su ogni campo filtrato frequentemente**: il query planner di MongoDB non usa statistiche di tabella come PostgreSQL: sceglie il piano provando gli indici candidati e cacheando il vincitore, quindi senza indice adatto fa COLLSCAN. Usare `explain()` per verificare
- **Evitare transazioni multi-documento quando possibile**: le transazioni MongoDB hanno overhead rilevante e impattano il throughput. Se possibile, progettare per atomicità single-document

## Troubleshooting

### Scenario 1 — Query lenta / COLLSCAN

**Sintomo:** Query impiega secondi, `explain()` mostra `COLLSCAN` invece di `IXSCAN`.

**Causa:** Nessun indice sul campo usato nel filtro, oppure l'indice esiste ma non viene usato (campo non in testa all'indice composto, o cardinalità troppo bassa).

**Soluzione:** Verificare il piano di esecuzione, creare l'indice mancante.

```javascript
// 1. Analizzare il piano di esecuzione
db.articoli.find({ tag: "nosql", pubblicato: true }).explain("executionStats")
// Cercare: winningPlan.stage — IXSCAN = buono, COLLSCAN = indice mancante
// Cercare: executionStats.totalDocsExamined >> nReturned = indice non selettivo

// 2. Vedere indici esistenti sulla collection
db.articoli.getIndexes()

// 3. Creare l'indice mancante
db.articoli.createIndex({ tag: 1, created_at: -1 })

// 4. Verificare indici non usati (overhead inutile)
db.articoli.aggregate([{ $indexStats: {} }])
// Eliminare indici con accesses.ops = 0 da settimane
db.articoli.dropIndex("nome_indice")
```

---

### Scenario 2 — Replica lag alto / secondary in ritardo

**Sintomo:** `rs.status()` mostra `optimeDate` del secondary molto indietro rispetto al primary; letture da secondary restituiscono dati vecchi.

**Causa:** Operazione bulk (import, migration, aggregation con `$out`) genera un picco di oplog che il secondary non riesce a consumare. Può anche essere dovuto a rete lenta o secondary sovraccarico.

**Soluzione:**

```javascript
// 1. Controllare lo stato del replica set e il lag
rs.status()
// Campo: members[N].optimeDate vs members[0].optimeDate (primary)
// Campo: members[N].stateStr — SECONDARY ok, RECOVERING = problema grave

// 2. Dimensione e utilizzo dell'oplog
rs.printReplicationInfo()      // primary: dimensione oplog e window temporale
rs.printSecondaryReplicationInfo()  // lag per ogni secondary

// 3. Se il secondary è in RECOVERING (oplog superato, "too stale"), serve una
// initial sync: fermare mongod sul secondary, svuotare il dbPath, riavviare.
// Il nodo riscarica tutti i dati dal primary. (Il comando `resync` esiste solo
// nei vecchi master/slave, NON nei replica set.)

// 4. Aumentare la finestra dell'oplog se troppo piccola 
// mongod.conf:
// replication:
//   oplogSizeMB: 10240   # default: 5% dello spazio libero, min 990MB, max 50GB; ridimensionabile a caldo con replSetResizeOplog
```

---

### Scenario 3 — Connessione esaurita / connection pool saturo

**Sintomo:** Errori `connection pool timeout` o `too many open connections` nell'applicazione; `mongostat` mostra `conn` vicino al limite.

**Causa:** L'applicazione apre troppe connessioni (istanze multiple senza pool condiviso, pool mal configurato) oppure il `maxConnections` del server è troppo basso.

**Soluzione:**

```bash
# 1. Monitorare connessioni in tempo reale
mongostat --host mongo1:27017 -u admin -p secret --authenticationDatabase admin 1
# Colonne rilevanti: conn, qr|qw (query read/write queue)

# 2. Connessioni attuali per database
mongosh --eval 'db.serverStatus().connections'
# current: connessioni aperte ora
# available: connessioni ancora disponibili
# totalCreated: connessioni create dall'avvio (alta = leak)
```

```python
# 3. Configurare correttamente il pool lato applicazione
from pymongo import MongoClient

client = MongoClient(
    "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0",
    maxPoolSize=50,        # default 100 — ridurre se molte istanze app
    minPoolSize=5,         # mantieni connessioni pre-aperte
    maxIdleTimeMS=60000,   # chiudi connessioni idle dopo 60s
    connectTimeoutMS=5000,
    serverSelectionTimeoutMS=5000
)
# IMPORTANTE: creare il client UNA SOLA VOLTA e riutilizzarlo (singleton)
```

---

### Scenario 4 — Aggregation fallisce con errore di memoria

**Sintomo:** Aggregation pipeline restituisce `Exceeded memory limit for $group` o `Sort exceeded memory limit`.

**Causa:** Uno stage della pipeline (tipicamente `$group`, `$sort`, `$lookup`) supera il limite di 100MB di RAM per stage.

**Soluzione:**

```javascript
// 1. Aggiungere allowDiskUse per usare spill su disco
// (dal 6.0 è già attivo di default via allowDiskUseByDefault; prima era obbligatorio.
// Il limite di 100MB per stage resta: oltre, lo stage scrive su disco)
db.ordini.aggregate(
    [
        { $match: { created_at: { $gte: ISODate("2023-01-01") } } },
        { $group: { _id: "$cliente_id", totale: { $sum: "$importo" } } },
        { $sort: { totale: -1 } }
    ],
    { allowDiskUse: true }   // abilita spill temporaneo su disco
)

// 2. Ottimizzare la pipeline — $match e $project il prima possibile
// MALE: prima $group (processa tutti i documenti), poi $match
// BENE: prima $match (riduce i documenti), poi $group
db.ordini.aggregate([
    { $match: { stato: "completato" } },      // ← prima del $group
    { $project: { cliente_id: 1, importo: 1 } },  // ← riduce campi
    { $group: { _id: "$cliente_id", totale: { $sum: "$importo" } } }
])

// 3. Verificare che $match usi un indice
db.ordini.aggregate(
    [{ $match: { stato: "completato" } }],
    { explain: true }
)
// Cercare: queryPlanner.winningPlan — deve essere IXSCAN non COLLSCAN
```

### Scenario 5 — `Authentication failed` / `not authorized`

**Sintomo:** `MongoServerError: Authentication failed` al login, oppure `not authorized on <db> to execute command` dopo il login.

**Causa:** `authSource` errato (l'utente è definito in `admin` ma si autentica sul database applicativo), meccanismo non supportato dall'utente (creato con SCRAM-SHA-1 vs client che richiede SHA-256), oppure ruolo mancante sul database/collection target.

**Soluzione:**

```bash
# 1. Specificare authSource corretto
mongosh "mongodb://app:secret@mongo1:27017/ecommerce?authSource=admin&replicaSet=rs0"
```

```javascript
// 2. Verificare ruoli e privilegi effettivi della sessione corrente
db.runCommand({ connectionStatus: 1, showPrivileges: true })

// 3. Verificare l'utente (da admin) e concedere il ruolo mancante
use admin
db.getUser("app")
db.grantRolesToUser("app", [{ role: "readWrite", db: "ecommerce" }])
```

---

### Scenario 6 — Errori TLS (`SSL handshake failed`, `certificate verify failed`)

**Sintomo:** i client non si connettono dopo `requireTLS`; nei log di `mongod` compare `SSL peer certificate validation failed`.

**Causa:** CA non fidata dal client, hostname non presente nei SAN del certificato (si usa l'IP o un alias), certificato scaduto, oppure `certificateKeyFile` senza chiave privata nel PEM.

**Soluzione:**

```bash
# Ispezionare SAN e scadenza del certificato server
openssl x509 -in /etc/mongo/tls/server.pem -noout -subject -ext subjectAltName -enddate

# Testare handshake con la CA corretta
openssl s_client -connect mongo1:27017 -CAfile /etc/mongo/tls/ca.pem </dev/null

# Connessione con CA esplicita
mongosh --tls --tlsCAFile /etc/mongo/tls/ca.pem --host mongo1 -u admin --authenticationDatabase admin
```

Il nome host usato dal client deve comparire nei SAN. Evitare `--tlsAllowInvalidCertificates` fuori dai test.

---

### Scenario 7 — Restore fallito o incompleto

**Sintomo:** `mongorestore` termina con errori `duplicate key`, utenti/ruoli mancanti dopo il restore, o dati non allineati al momento atteso.

**Causa:** restore su collection già popolate senza `--drop`; dump di un singolo database che non include `admin` (utenti e ruoli); dump senza `--oplog` quindi non point-in-time; versioni di `mongodump`/`mongorestore` incompatibili con il server.

**Soluzione:**

```bash
# Ripristino pulito: elimina le collection esistenti prima di reinserirle
mongorestore --drop --gzip --archive=/backup/rs0.archive --oplogReplay

# Includere utenti/ruoli: dump del database admin con le collection di sistema
mongodump --db=admin --collection=system.users --archive=/backup/users.archive
mongorestore --nsInclude="admin.*" --archive=/backup/users.archive

# Verifica post-restore
mongosh --eval 'db.getSiblingDB("ecommerce").ordini.countDocuments({})'
```

Usare tool della stessa versione major del server e provare sempre il restore su un ambiente isolato prima di un incidente reale.

---

## Relazioni

??? info "Redis — Approfondimento"
    Redis è un key-value in-memory: complementare a MongoDB come cache e store di sessioni davanti al document store.

    **Approfondimento completo →** [Redis](redis.md)

??? info "Sharding — Approfondimento"
    I principi di scelta della shard key e di distribuzione dei dati valgono per MongoDB come per altri datastore.

    **Approfondimento completo →** [Sharding](../fondamentali/sharding.md)

## Riferimenti

- [MongoDB Documentation](https://www.mongodb.com/docs/)
- [MongoDB University — Free Courses](https://learn.mongodb.com/)
- [MongoDB Schema Design Patterns](https://www.mongodb.com/blog/post/building-with-patterns-a-summary)
- [The Little MongoDB Book](https://github.com/karlseguin/the-little-mongodb-book)
