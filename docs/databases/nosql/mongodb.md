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
last_updated: 2026-02-24
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

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Query lenta con COLLSCAN | Indice mancante | `createIndex` sul campo filtrato |
| Write lente | Write concern troppo stringente o nodo lento | Verificare `rs.status()`, rete tra nodi |
| Replica lag alto | Operazione pesante in oplog | Analizzare oplog, aumentare `oplogSize` |
| `Cursor timeout` su aggregation | Pipeline lenta, cursor non letto | Aggiungere `{ allowDiskUse: true }`, ottimizzare pipeline |
| Documento > 16MB | Array cresce senza limite | Refactoring verso referencing |

## Riferimenti

- [MongoDB Documentation](https://www.mongodb.com/docs/)
- [MongoDB University — Free Courses](https://learn.mongodb.com/)
- [MongoDB Schema Design Patterns](https://www.mongodb.com/blog/post/building-with-patterns-a-summary)
- [The Little MongoDB Book](https://github.com/karlseguin/the-little-mongodb-book)
