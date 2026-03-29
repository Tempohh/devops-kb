---
title: "MongoDB"
slug: mongodb
category: databases
tags: [mongodb, nosql, document, aggregation, replica-set, sharding]
search_keywords: [mongodb document store, mongodb aggregation pipeline, mongodb indexes, mongodb replica set, mongodb sharding, mongodb atlas, mongodb transactions, mongodb schema design, embedding vs referencing, mongodb oplog, mongodb change streams, mongodb atlas search, mongodb timeseries collection, bson, mongosh, mongostat, mongodump, mongorestore, mongodb compass, wiredtiger storage engine, mongodb collation, mongodb text search, mongodb gridfs]
parent: databases/nosql/_index
related: [databases/fondamentali/modelli-dati, databases/fondamentali/sharding, databases/nosql/redis]
official_docs: https://www.mongodb.com/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
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
    "_id": ObjectId("65a1b2c3d4e5f6789012345"),  // ID univoco auto-generato
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
    "_id": ObjectId("post-1"),
    "titolo": "...",
    // commenti: NON embedded — referencing via collection separata
}
{
    // collection: commenti
    "_id": ObjectId("..."),
    "post_id": ObjectId("post-1"),    // foreign key manuale
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

// Indice composto (ordine importa: filtra per tag, poi ordina per data)
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
rs.isMaster()   // o rs.hello() (MongoDB 5+)
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
// w: 1 (default) — solo primary ha scritto (può essere perso in failover)

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
// Abilita sharding su un database
sh.enableSharding("ecommerce")

// Shard su hashed field (distribuzione uniforme)
sh.shardCollection("ecommerce.ordini", { cliente_id: "hashed" })

// Shard su range (meglio per query range, peggio per hotspot)
sh.shardCollection("ecommerce.log_eventi", { created_at: 1 })

// Stato dello sharding
sh.status()
```

**Scelta del shard key** (identici principi di [Sharding](../fondamentali/sharding.md)):
- Alta cardinalità (non boolean, non enum piccolo)
- Distribuzione uniforme dei write (evitare monotonic keys su range shard)
- Query isolation: la maggior parte delle query dovrebbe includere la shard key

---

## Best Practices

- **Schema design prima di tutto**: a differenza di SQL, lo schema errato in MongoDB è costoso da cambiare. Modellare in base ai pattern di accesso, non alla struttura dati
- **Embedded per default, referencing quando necessario**: embedding → 1 lettura, referencing → 2 letture. Eccezioni: documento > 16MB (limite BSON), array che crescono senza limite, entità lette spesso da sole
- **Write concern majority in produzione**: `w:1` rischia perdita di dati in caso di failover — non accettabile per dati critici
- **Indice su ogni campo filtrato frequentemente**: MongoDB non ha statistiche automatiche come PostgreSQL — l'ottimizzatore dipende dagli indici. Usare `explain()` per verificare
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

// 3. Se il secondary è in RECOVERING, forzare risincronizzazione
// Sul secondary (mongosh):
db.adminCommand({ resync: 1 })

// 4. Aumentare la finestra dell'oplog se troppo piccola (richiede riavvio)
// mongod.conf:
// replication:
//   oplogSizeMB: 10240   # default: 5% del disco, minimo 990MB
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

## Riferimenti

- [MongoDB Documentation](https://www.mongodb.com/docs/)
- [MongoDB University — Free Courses](https://learn.mongodb.com/)
- [MongoDB Schema Design Patterns](https://www.mongodb.com/blog/post/building-with-patterns-a-summary)
- [The Little MongoDB Book](https://github.com/karlseguin/the-little-mongodb-book)
