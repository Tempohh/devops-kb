---
title: "Modelli dei Dati"
slug: modelli-dati
category: databases
tags: [modelli-dati, relazionale, nosql, document, key-value, wide-column, graph, time-series, vettoriale]
search_keywords: [database models, relational model, document database, key value store, wide column store, column family, graph database, time series database, vector database, polyglot persistence, impedance mismatch, denormalization, normalization, embedding vs referencing, data locality, write amplification, read amplification]
parent: databases/fondamentali/_index
related: [databases/fondamentali/acid-base-cap, databases/nosql/redis, databases/nosql/mongodb, databases/nosql/cassandra]
official_docs: https://martinfowler.com/articles/nosql-distilled.html
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Modelli dei Dati

## Panoramica

Il modello dei dati non è solo "SQL vs NoSQL" — è la scelta fondamentale che determina come l'applicazione accede ai dati, come scalano le query, e quale tipo di inconsistenza è accettabile. Ogni modello risolve un problema strutturale diverso; scegliere quello sbagliato significa riscrivere l'accesso ai dati quando i volumi crescono.

## Il Modello Relazionale

Il modello relazionale (Codd, 1970) organizza i dati in **relazioni** (tabelle) con schemi fissi, collegate da chiavi. La potenza sta nella flessibilità delle query tramite algebra relazionale — ogni relazione può essere combinata con qualsiasi altra tramite JOIN.

**Punto di forza unico**: il modello relazionale non presuppone i pattern di accesso. Puoi fare query ad hoc su qualsiasi combinazione di colonne senza ristrutturare i dati. È l'unico modello che non ti fa pagare il costo di "sapere in anticipo come accederai ai dati".

### Normalizzazione — Il Principio, Non il Dogma

La normalizzazione elimina la ridondanza: ogni fatto è memorizzato una sola volta. La 3NF (Terza Forma Normale) garantisce che ogni attributo dipenda solo dalla chiave primaria.

```sql
-- Forma denormalizzata (ridondante)
ordini(id, cliente_id, cliente_nome, cliente_email, prodotto, prezzo)
-- cliente_nome e cliente_email si ripetono per ogni ordine

-- Forma normalizzata
clienti(id, nome, email)
ordini(id, cliente_id FK, data)
ordini_righe(id, ordine_id FK, prodotto_id FK, quantita, prezzo_unitario)
prodotti(id, nome, prezzo_base)
```

**Il costo della normalizzazione**: più JOIN per ricostruire i dati. In sistemi OLAP o con pattern di lettura molto specifici, la denormalizzazione deliberata (materializzare join, duplicare dati) è una strategia valida — non un errore.

### Impedance Mismatch

Il modello relazionale non mappa naturalmente sulle strutture dati degli linguaggi OOP. Un `User` con una lista di `Address` richiede 2 tabelle e un JOIN — ma è un singolo oggetto in memoria. Gli ORM tentano di nascondere questo mismatch, ma lo amplificano con il problema N+1.

```python
# N+1 problem classico (ORM)
users = User.query.all()          # 1 query
for user in users:
    print(user.orders.count())    # N query (1 per ogni user)

# Soluzione: eager loading esplicito
users = User.query.options(joinedload(User.orders)).all()  # 1 query con JOIN
```

---

## Modello Document

I database document (MongoDB, CouchDB, Firestore) memorizzano dati come documenti semi-strutturati (JSON/BSON). Il documento è l'unità atomica di lettura/scrittura.

**Problema che risolve**: l'impedance mismatch. Un oggetto applicativo corrisponde direttamente a un documento — nessun JOIN per ricostruirlo.

### Embedding vs Referencing

La scelta critica nel document model:

```json
// Embedding: tutto in un documento
{
  "_id": "order-123",
  "customer": {
    "name": "Alice",
    "email": "alice@example.com"
  },
  "items": [
    {"product": "Widget A", "qty": 2, "price": 9.99},
    {"product": "Widget B", "qty": 1, "price": 24.99}
  ]
}

// Referencing: documenti separati con riferimenti
{
  "_id": "order-123",
  "customer_id": "customer-456",  // riferimento
  "item_ids": ["item-789", "item-790"]
}
```

**Regola empirica per l'embedding:**
- Usa embedding quando i dati embedded sono sempre letti insieme al documento padre
- Usa embedding quando la lista embedded ha cardinalità limitata e non cresce indefinitamente
- Usa referencing quando i dati embedded sono condivisi tra più documenti (es. informazioni prodotto)
- Usa referencing quando la lista embedded può crescere in modo illimitato (array unbounded = document bloat)

!!! warning "Document Size Limit"
    MongoDB ha un limite di 16MB per documento. Un documento con un array di commenti non limitato può raggiungere il limite — usare referencing per relazioni one-to-many con cardinalità alta.

---

## Modello Key-Value

Il modello più semplice: una hash table distribuita. Una chiave identifica univocamente un valore opaco. Nessuna struttura interna, nessuna query sul contenuto.

**Problema che risolve**: latenza di accesso O(1) a milioni di oggetti, scalabilità orizzontale semplice.

```
GET user:session:a1b2c3d4     → {user_id: 123, expires: 1708780800}
SET cache:product:456 300 "..." → (expiry 300s)
INCR rate:ip:192.168.1.1      → 47
```

Redis estende il modello key-value con strutture dati (liste, hash, sorted set) — è un "data structure server", non solo un cache. Vedi [Redis](../nosql/redis.md).

**Limitazione fondamentale**: non è possibile fare query sul valore. Per trovare tutti gli utenti con `role=admin`, o si mantiene un indice separato o si fa una full scan (impraticabile a scale).

---

## Modello Wide-Column (Column Family)

Hybrido tra relazionale e key-value. I dati sono organizzati per **partition key** (identifica il nodo) e **clustering key** (ordinamento all'interno della partition). Ogni riga può avere colonne diverse.

```
Partition Key: user_id=123
  Clustering Key: timestamp=2024-01-15 → {event: "login", ip: "10.0.0.1"}
  Clustering Key: timestamp=2024-01-16 → {event: "purchase", amount: 49.99}
  Clustering Key: timestamp=2024-01-17 → {event: "logout"}
```

**Problema che risolve**: letture sequenziali di grandi volumi di dati ordinati per una chiave — time series, log, activity feed. La colocation dei dati sulla stessa partition garantisce letture in una singola operazione I/O.

**Limitazione fondamentale**: il modello dei dati deve essere progettato partendo dalle query. Non è possibile fare query efficienti su colonne diverse dalla partition key senza indici secondari (costosi). Vedi [Cassandra](../nosql/cassandra.md).

---

## Modello Graph

I database graph (Neo4j, Amazon Neptune, ArangoDB) modellano i dati come nodi e archi con proprietà. Le query traversano relazioni — la complessità non cresce con il volume totale dei dati ma con la profondità della traversal.

**Problema che risolve**: query su relazioni multi-hop che in SQL richiederebbero JOIN ricorsivi o CTE ricorsivi:

```cypher
-- Neo4j Cypher: trova tutti gli amici di amici a distanza ≤ 3
MATCH (p:Person {name: "Alice"})-[:FRIENDS_WITH*1..3]-(friend)
WHERE NOT friend = p
RETURN DISTINCT friend.name, LENGTH(path) AS hops
```

```sql
-- Equivalente in SQL — ricorsivo e molto più lento su grafi profondi
WITH RECURSIVE amici AS (
  SELECT amico_id, 1 AS livello FROM friendships WHERE utente_id = 1
  UNION ALL
  SELECT f.amico_id, a.livello + 1
  FROM friendships f INNER JOIN amici a ON f.utente_id = a.amico_id
  WHERE a.livello < 3
)
SELECT DISTINCT amico_id FROM amici;
```

**Casi d'uso**: social network, recommendation engine, fraud detection (reti di connessioni), knowledge graph, dipendenze tra servizi.

**Limitazione**: non scala bene per query che richiedono aggregazioni su larga scala (somma, conteggio su milioni di nodi). I database graph sono ottimizzati per traversal, non per analytics OLAP.

---

## Modello Time-Series

Database specializzati per dati con timestamp (InfluxDB, TimescaleDB, Prometheus, VictoriaMetrics). Ottimizzati per:
- **Write throughput altissimo** (metriche ogni secondo da migliaia di sorgenti)
- **Compressione** (i valori vicini nel tempo sono simili — delta encoding, gorilla compression)
- **Downsampling automatico** (aggregazione di dati vecchi per risparmiare spazio)
- **Window functions** su intervalli temporali

```sql
-- TimescaleDB (PostgreSQL extension)
-- Query su serie temporali con aggregazione automatica
SELECT
  time_bucket('1 hour', time) AS ora,
  avg(cpu_usage) AS cpu_medio,
  max(cpu_usage) AS cpu_picco
FROM metriche
WHERE time > NOW() - INTERVAL '7 days'
  AND host = 'web-01'
GROUP BY ora
ORDER BY ora;
```

**Perché non usare PostgreSQL normale**: su tabelle con miliardi di righe di metriche, l'insert diventa un collo di bottiglia (index maintenance) e le query temporali richiedono partition pruning manuale. TimescaleDB automatizza entrambi tramite hypertable con partitioning temporale automatico.

---

## Modello Vettoriale

I database vettoriali (pgvector per PostgreSQL, Pinecone, Weaviate, Qdrant, Milvus) indicizzano embedding numerici ad alta dimensionalità per **similarity search**.

```python
# Similarity search su embedding testuali
embedding = model.encode("Come funziona il rate limiting?")  # vettore 1536 dim

results = db.query(
    vector=embedding,
    top_k=5,
    filter={"category": "networking"}
)
# Restituisce i 5 documenti semanticamente più simili alla query
```

**Indici per similarity search:**
- **HNSW** (Hierarchical Navigable Small World): alta recall, bassa latenza, alto uso memoria
- **IVF** (Inverted File Index): più scalabile in memoria, recall leggermente inferiore
- **Flat**: brute-force esatto, impraticabile oltre ~1M vettori

!!! note "pgvector in PostgreSQL"
    pgvector permette di fare similarity search all'interno di PostgreSQL, combinando il modello relazionale con la ricerca vettoriale. Ottimo per applicazioni che già usano Postgres — evita la complessità di un sistema separato.

---

## Polyglot Persistence

In sistemi complessi, usare il modello giusto per ogni caso d'uso è più efficiente che forzare tutto in un unico database:

```
E-commerce moderno:
├── PostgreSQL        → Ordini, pagamenti, inventario (ACID, relazioni complesse)
├── Redis             → Sessioni, carrello (key-value, TTL, latenza <1ms)
├── Elasticsearch     → Ricerca prodotti full-text
├── MongoDB           → Catalogo prodotti (schemi flessibili per categorie diverse)
├── Cassandra         → Activity log utenti (time-series, write-heavy)
└── Neo4j             → Recommendation engine ("chi ha comprato X ha comprato anche Y")
```

**Il costo del polyglot persistence**: complessità operativa, sincronizzazione dei dati tra sistemi (CDC, event sourcing), più failure domain da gestire.

## Troubleshooting

### Scenario 1 — Query lente con molti JOIN (N+1 problem)

**Sintomo**: l'applicazione esegue centinaia di query al secondo anche per pagine semplici; APM mostra query identiche replicate N volte.

**Causa**: ORM che esegue lazy loading: carica una collezione e poi itera su ogni elemento eseguendo una query separata per le relazioni.

**Soluzione**: abilitare eager loading esplicito o usare query con JOIN manuali.

```python
# Django — eager loading con select_related e prefetch_related
# select_related: JOIN SQL (FK, OneToOne)
orders = Order.objects.select_related('customer').all()

# prefetch_related: query separata ottimizzata (ManyToMany, reverse FK)
users = User.objects.prefetch_related('orders__items').all()

# Verifica con Django Debug Toolbar o logging delle query
import logging
logging.getLogger('django.db.backends').setLevel(logging.DEBUG)
```

---

### Scenario 2 — Document MongoDB con crescita incontrollata

**Sintomo**: errore `Document exceeds maximum size 16793600` oppure letture sempre più lente su una collection; documenti nella collection superano i 16MB.

**Causa**: array embedded non limitato (commenti, log, eventi) che cresce indefinitamente all'interno di un singolo documento.

**Soluzione**: refactoring da embedding a referencing; spostare l'array in una collection separata.

```javascript
// Diagnosi: trovare documenti vicini al limite
db.posts.find({}).forEach(doc => {
  const size = Object.bsonsize(doc);
  if (size > 10 * 1024 * 1024) { // > 10MB
    print(`${doc._id}: ${(size/1024/1024).toFixed(2)} MB`);
  }
});

// Migrazione: spostare commenti embedded in collection separata
db.posts.find({}).forEach(post => {
  if (post.comments && post.comments.length > 0) {
    post.comments.forEach(comment => {
      db.comments.insertOne({ ...comment, post_id: post._id });
    });
    db.posts.updateOne({ _id: post._id }, { $unset: { comments: "" } });
  }
});
```

---

### Scenario 3 — Query Cassandra con ALLOW FILTERING

**Sintomo**: query con `ALLOW FILTERING` in produzione con latenze elevate e timeout; warnings nei log del driver.

**Causa**: query su colonne che non fanno parte della partition key o clustering key — Cassandra deve scansionare tutte le partizioni (full table scan distribuito).

**Soluzione**: riprogettare il data model creando una tabella dedicata per il pattern di query necessario (query-driven design).

```cql
-- PROBLEMA: query su colonna non chiave
SELECT * FROM events WHERE user_id = 123 AND status = 'pending' ALLOW FILTERING;
-- Questo scansiona TUTTE le partizioni — inaccettabile in produzione

-- SOLUZIONE: tabella dedicata al pattern di query
CREATE TABLE events_by_status (
  status TEXT,
  created_at TIMESTAMP,
  user_id UUID,
  event_data TEXT,
  PRIMARY KEY ((status), created_at, user_id)
) WITH CLUSTERING ORDER BY (created_at DESC);

-- Query efficiente sulla nuova tabella
SELECT * FROM events_by_status
WHERE status = 'pending' AND created_at > '2024-01-01';

-- Verificare execution plan
TRACING ON;
SELECT * FROM events_by_status WHERE status = 'pending' LIMIT 100;
```

---

### Scenario 4 — Similarity search vettoriale con bassa precisione (recall)

**Sintomo**: il database vettoriale restituisce risultati non pertinenti; aggiungendo documenti la qualità peggiora progressivamente.

**Causa**: indice HNSW con parametri `ef_construction` o `m` troppo bassi, oppure embedding generati da modelli diversi (spazi vettoriali incompatibili).

**Soluzione**: ricreare l'indice con parametri più alti e verificare la coerenza del modello di embedding.

```python
# pgvector — verifica e ricreazione indice con parametri ottimizzati
# ef_construction: qualità costruzione (default 64, aumentare per recall alta)
# m: connessioni per nodo (default 16, range 4-64)

# Diagnosi: misurare recall con ground truth
import psycopg2
conn = psycopg2.connect("...")
cur = conn.cursor()

# Ricrea indice con parametri migliori
cur.execute("DROP INDEX IF EXISTS embeddings_hnsw_idx;")
cur.execute("""
  CREATE INDEX embeddings_hnsw_idx ON documents
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 32, ef_construction = 128);
""")

# Imposta ef per query (bilanciamento recall/latenza a runtime)
cur.execute("SET hnsw.ef_search = 100;")

# Verifica che tutti gli embedding usino lo stesso modello
cur.execute("""
  SELECT COUNT(*), AVG(vector_dims(embedding)) as avg_dims
  FROM documents;
""")
print(cur.fetchone())  # Se avg_dims != 1536 (o atteso) ci sono embedding eterogenei
conn.commit()
```

---

## Relazioni

??? info "ACID, BASE e CAP — Garanzie dei sistemi"
    Come i modelli si posizionano rispetto alle garanzie di consistenza.

    **Approfondimento →** [ACID, BASE e CAP](acid-base-cap.md)

??? info "Sharding — Distribuzione orizzontale"
    Come ogni modello gestisce la distribuzione dei dati su più nodi.

    **Approfondimento →** [Sharding](sharding.md)

## Riferimenti

- [NoSQL Distilled — Fowler, Sadalage](https://martinfowler.com/articles/nosql-distilled.html)
- [Designing Data-Intensive Applications — Kleppmann, Capitolo 2](https://dataintensive.net/)
- [MongoDB Data Modeling Patterns](https://www.mongodb.com/blog/post/building-with-patterns-a-summary)
