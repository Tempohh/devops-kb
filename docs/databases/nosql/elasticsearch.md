---
title: "Elasticsearch"
slug: elasticsearch
category: databases
tags: [elasticsearch, nosql, full-text-search, elk, analytics, inverted-index, distributed]
search_keywords: [elasticsearch, elastic search, ES, ELK stack, elastic stack, opensearch, lucene, full text search, log analytics, inverted index, query DSL, aggregazioni elasticsearch, mapping elasticsearch, sharding elasticsearch, kibana, logstash, beats, APM elastic, elasticsearch cluster, indici elasticsearch, relevance scoring, BM25, elasticsearch query, elasticsearch filter, term query, match query, elasticsearch reindex, elasticsearch alias, ILM index lifecycle management, elasticsearch ingest pipeline, hot warm cold, elasticsearch snapshot, elasticsearch security, xpack, elasticsearch vs solr]
parent: databases/nosql/_index
related: [databases/nosql/cassandra, databases/fondamentali/sharding, databases/fondamentali/modelli-dati, monitoring/tools/loki]
official_docs: https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Elasticsearch

## Panoramica

Elasticsearch è un motore di ricerca e analytics distribuito basato su Apache Lucene. Nasce per risolvere un problema preciso: la ricerca full-text scalabile su grandi volumi di dati semi-strutturati. Oggi è il componente centrale dell'Elastic Stack (ex ELK), usato sia per ricerca applicativa (e-commerce, motori di ricerca interni) che per log analytics e APM.

Il modello di dati è **document-oriented**: i dati vengono salvati come documenti JSON all'interno di **indici**. L'accesso avviene tramite una HTTP REST API o tramite il Query DSL in JSON.

**Elasticsearch è ottimale per:**
- Full-text search con ranking di rilevanza (e-commerce, documentazione, knowledge base)
- Log analytics e centralized logging (stack ELK/EFK)
- Analytics su dati semi-strutturati (aggregazioni su campi arbitrari)
- APM e distributed tracing (Elastic APM)
- Ricerca geo-spaziale

**Elasticsearch è sbagliato per:**
- Transazioni ACID (non c'è supporto nativo, nessun rollback)
- Primary data store (Elasticsearch è spesso affiancato a un DB principale)
- Relazioni complesse tra documenti (JOIN non esistono: si usa nesting o parent-child)
- Write ad alto throughput stabile (Cassandra o Kafka sono più adatti)

!!! note "Elasticsearch vs OpenSearch"
    Nel 2021 Amazon ha forkato Elasticsearch (v7.10) creando OpenSearch sotto licenza Apache 2.0. Le API sono quasi identiche, ma le versioni recenti di Elasticsearch (8.x+) hanno introdotto funzionalità non presenti in OpenSearch. In questo documento si fa riferimento a Elasticsearch OSS/SSPL.

---

## Concetti Chiave

### Indice e Documento

Un **indice** è l'equivalente di una tabella — ma senza schema fisso. Un **documento** è l'equivalente di una riga, serializzato come JSON. Ogni documento ha un `_id` (auto-generato o specificato) e appartiene a un indice.

```json
PUT /prodotti/_doc/1
{
  "nome": "Laptop Pro X",
  "categoria": "elettronica",
  "prezzo": 1299.99,
  "descrizione": "Laptop ad alte prestazioni con display 4K",
  "tags": ["laptop", "4k", "professionale"]
}
```

### Inverted Index

Il meccanismo che rende la ricerca full-text efficiente. Per ogni campo testuale, Elasticsearch costruisce un **inverted index**: una mappa da ogni termine unico → lista dei documenti che lo contengono, con posizione e frequenza.

```
termine       → documenti
"laptop"      → [doc1, doc5, doc12]
"prestazioni" → [doc1, doc3]
"display"     → [doc1, doc8]
```

Questo permette query full-text in O(1) invece di O(n) (no full scan).

### Sharding e Replica

Ogni indice è suddiviso in **primary shards** (default: 1 in ES 7.x+, storicamente 5). Ogni shard è un'istanza Lucene indipendente. I **replica shards** sono copie dei primary per alta disponibilità e read scaling.

```
Indice "logs" con 3 primary shards e 1 replica:

Nodo 1: P0, R1, R2
Nodo 2: P1, R0, R2
Nodo 3: P2, R0, R1
```

!!! warning "Il numero di primary shard è immutabile"
    Una volta creato l'indice, il numero di primary shard non può essere modificato (solo con reindex). Pianifica la capacità prima della creazione. Per workload che crescono usa **index aliases** + **reindex** + **ILM**.

### Mapping

Il **mapping** definisce i tipi di campo di un documento — equivalente allo schema. Il dynamic mapping crea automaticamente i mapping all'inserimento del primo documento; quello esplicito offre controllo preciso.

| Tipo campo | Uso |
|------------|-----|
| `text` | Full-text search, viene analizzato (tokenizzato) |
| `keyword` | Valori esatti, aggregazioni, ordinamento (non analizzato) |
| `integer`, `float`, `double` | Numeri |
| `date` | Date (formato ISO 8601 o epoch) |
| `boolean` | true/false |
| `object` | Oggetto JSON annidato |
| `nested` | Array di oggetti con query indipendenti per ciascuno |
| `geo_point` | Coordinate lat/lon per ricerca geo-spaziale |
| `dense_vector` | Vettori per kNN/semantic search (ES 8.x) |

```json
PUT /prodotti
{
  "mappings": {
    "properties": {
      "nome":       { "type": "text", "analyzer": "italian" },
      "categoria":  { "type": "keyword" },
      "prezzo":     { "type": "float" },
      "tags":       { "type": "keyword" },
      "created_at": { "type": "date", "format": "yyyy-MM-dd" }
    }
  }
}
```

!!! tip "text vs keyword"
    Usa `text` per campi su cui farai full-text search. Usa `keyword` per filtri esatti, aggregazioni, e ordinamento. Per campi che servono entrambi (es. titolo cercabile e aggregabile), usa **multi-fields**:
    ```json
    "titolo": {
      "type": "text",
      "fields": { "raw": { "type": "keyword" } }
    }
    ```

---

## Architettura / Come Funziona

### Cluster e Nodi

Un cluster Elasticsearch è composto da uno o più nodi. Ogni nodo può avere uno o più ruoli:

| Ruolo | Descrizione |
|-------|-------------|
| `master` | Gestisce lo stato del cluster (indici, shards) |
| `data` | Archivia dati e gestisce le query |
| `data_hot` | Nodi ad alte performance per dati recenti |
| `data_warm` | Nodi a basso costo per dati meno recenti |
| `data_cold` | Nodi economici per dati storici (searchable snapshots) |
| `ingest` | Pipeline di pre-processamento documenti |
| `coordinating` | Solo routing query (no dati), bilancimento del carico |

In produzione, separare sempre i ruoli master-eligible dai data nodes.

### Routing dei Documenti

Quando un documento viene indicizzato, Elasticsearch calcola su quale shard inviarlo:

```
shard = hash(_id) % numero_primary_shards
```

Per query, il nodo coordinatore fa **scatter-gather**: distribuisce la query su tutti i shard, raccoglie i risultati, merge e restituisce.

### Processo di Indicizzazione

```
Client → REST API → Coordinating Node
                         ↓
                    Routing → Primary Shard
                         ↓
                    Translog (durabilità)
                    In-memory buffer (refresh)
                         ↓
                    Replica Shards (async)
                         ↓
                    Segment merge (background)
```

Il **refresh** (default ogni 1s) rende i documenti ricercabili scrivendo i buffer su segmenti Lucene. Il **flush** scrive i segmenti su disco e svuota il translog.

---

## Configurazione & Pratica

### Deploy con Docker Compose (sviluppo)

```yaml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    environment:
      - discovery.type=single-node
      - ELASTIC_PASSWORD=changeme
      - xpack.security.enabled=true
      - xpack.security.http.ssl.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    ports:
      - "9200:9200"
    volumes:
      - esdata:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.12.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=changeme
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

volumes:
  esdata:
```

### Query DSL

Il Query DSL distingue tra **query context** (influenza il relevance score) e **filter context** (sì/no, cacheable):

```json
GET /prodotti/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "descrizione": "laptop prestazioni" } }
      ],
      "filter": [
        { "term":  { "categoria": "elettronica" } },
        { "range": { "prezzo": { "gte": 500, "lte": 2000 } } }
      ],
      "should": [
        { "term": { "tags": "4k" } }
      ],
      "must_not": [
        { "term": { "disponibile": false } }
      ]
    }
  },
  "sort": [
    { "_score": "desc" },
    { "prezzo": "asc" }
  ],
  "from": 0,
  "size": 10
}
```

**Query principali:**

| Query | Uso |
|-------|-----|
| `match` | Full-text search su campo `text` |
| `match_phrase` | Frase esatta con ordine preservato |
| `multi_match` | `match` su più campi contemporaneamente |
| `term` | Match esatto su `keyword`/numero/boolean |
| `terms` | Match su lista di valori (IN) |
| `range` | Intervallo numerico o temporale |
| `exists` | Campo non null/vuoto |
| `wildcard` | Pattern con `*` e `?` (costoso) |
| `fuzzy` | Ricerca con tolleranza typo (edit distance) |
| `geo_distance` | Punti entro raggio da coordinate |
| `knn` | K-nearest neighbor per vector search |

### Aggregazioni

Le aggregazioni sono lo strumento analytics di Elasticsearch. Si eseguono in parallelo alla query di ricerca.

```json
GET /logs-2026-03/_search
{
  "size": 0,
  "query": {
    "range": { "@timestamp": { "gte": "now-1h" } }
  },
  "aggs": {
    "per_servizio": {
      "terms": { "field": "service.name", "size": 10 },
      "aggs": {
        "livelli_log": {
          "terms": { "field": "log.level" }
        },
        "latenza_media": {
          "avg": { "field": "http.response.duration_ms" }
        },
        "latenza_percentili": {
          "percentiles": {
            "field": "http.response.duration_ms",
            "percents": [50, 95, 99]
          }
        }
      }
    }
  }
}
```

**Tipi di aggregazione principali:**

| Tipo | Esempi |
|------|--------|
| **Bucket** | `terms`, `date_histogram`, `range`, `geohash_grid` |
| **Metric** | `avg`, `sum`, `min`, `max`, `percentiles`, `cardinality` |
| **Pipeline** | `moving_avg`, `derivative`, `bucket_sort` |

### Index Lifecycle Management (ILM)

ILM automatizza la gestione del ciclo di vita degli indici (tipico per log):

```json
PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_primary_shard_size": "50gb",
            "max_age": "1d"
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink":    { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "s3-repo"
          }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

### Data Streams (log moderni)

I **data streams** sostituiscono l'approccio manuale con indici con rollover automatico — raccomandati per log e time series:

```json
PUT _index_template/logs-template
{
  "index_patterns": ["logs-*"],
  "data_stream": {},
  "template": {
    "settings": {
      "index.lifecycle.name": "logs-policy"
    }
  }
}

POST logs-myapp/_doc
{
  "@timestamp": "2026-03-24T10:00:00Z",
  "message": "Request completed",
  "level": "INFO"
}
```

### Ingest Pipeline

Pre-processa i documenti prima dell'indicizzazione (parse, transform, enrich):

```json
PUT _ingest/pipeline/logs-parse
{
  "processors": [
    {
      "grok": {
        "field": "message",
        "patterns": ["%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:msg}"]
      }
    },
    {
      "date": {
        "field": "timestamp",
        "formats": ["ISO8601"],
        "target_field": "@timestamp"
      }
    },
    {
      "remove": { "field": "timestamp" }
    },
    {
      "set": {
        "field": "environment",
        "value": "production"
      }
    }
  ]
}

POST logs-myapp/_doc?pipeline=logs-parse
{ "message": "2026-03-24T10:00:00Z INFO Request completed" }
```

---

## Best Practices

### Dimensionamento Shards
- Punta a shard tra **10-50 GB** ciascuno per log; fino a **100 GB** per ricerca
- Troppi shard piccoli consumano memoria heap e overhead di coordinazione
- Formula orientativa: `numero_shard = (dimensione_indice_GB / 30)`
- Usa **rollover** + **ILM** per indici time-based invece di pre-shardare

### Mapping Esplicito
- Disabilita il dynamic mapping in produzione: `"dynamic": "strict"` o `"false"`
- Evita campi che crescono senza controllo (object con chiavi dinamiche)
- `"dynamic": "false"` ignora campi non mappati; `"strict"` li rifiuta con errore

### Performance Query
- Usa sempre **filter context** per filtri non-relevance (range, term, exists)
- Evita `wildcard` e `regex` su campi ad alta cardinalità — sono O(n)
- Usa `keyword` per aggregazioni, non `text`
- Limita `from` + `size` per deep pagination — usa `search_after` per grandi dataset
- Abilita `request_cache` per query aggregate ripetute

```json
GET /logs/_search?request_cache=true
{
  "size": 0,
  "aggs": { "errori": { "filter": { "term": { "level": "ERROR" } } } }
}
```

### Heap e Risorse
- Heap JVM: massimo **50% della RAM**, mai oltre **31 GB** (limite compressed OOPs)
- Lascia la restante RAM al filesystem cache di Lucene
- Usa SSD per nodi hot; HDD o object storage per cold
- Monitora: `JVM heap used %`, `search latency p99`, `indexing rate`, `shard count`

### Alias per Zero-Downtime Reindex

```bash
# Crea indice v2 con nuovo mapping
PUT /prodotti-v2
{ ... }

# Reindex da v1 a v2
POST _reindex
{
  "source": { "index": "prodotti-v1" },
  "dest":   { "index": "prodotti-v2" }
}

# Sposta alias atomicamente
POST _aliases
{
  "actions": [
    { "remove": { "index": "prodotti-v1", "alias": "prodotti" } },
    { "add":    { "index": "prodotti-v2", "alias": "prodotti" } }
  ]
}
```

---

## Troubleshooting

### Cluster Red / Yellow

```bash
# Stato cluster
GET _cluster/health?level=shards

# Shards non assegnati
GET _cat/shards?h=index,shard,prirep,state,unassigned.reason&v

# Allocazione spiegata
GET _cluster/allocation/explain
```

| Stato | Causa comune | Soluzione |
|-------|--------------|-----------|
| RED | Primary shard non assegnato | Verifica nodi disponibili, disk watermark |
| YELLOW | Replica non assegnata | Aggiungi nodo o abbassa `number_of_replicas` |
| YELLOW mono-nodo | Solo 1 nodo, replica impossibile | `PUT /indice/_settings {"number_of_replicas": 0}` |

### Disk Watermark

Elasticsearch blocca l'indicizzazione quando il disco supera le soglie:

```json
PUT _cluster/settings
{
  "transient": {
    "cluster.routing.allocation.disk.watermark.low":  "85%",
    "cluster.routing.allocation.disk.watermark.high": "90%",
    "cluster.routing.allocation.disk.watermark.flood_stage": "95%"
  }
}
```

### Query Lente

```bash
# Abilita slow log (soglia 1s)
PUT /indice/_settings
{
  "index.search.slowlog.threshold.query.warn": "1s",
  "index.search.slowlog.threshold.fetch.warn": "500ms"
}

# Profiling query
GET /indice/_search
{
  "profile": true,
  "query": { "match": { "campo": "valore" } }
}
```

### Heap Alto (> 80%)

- Riduci il numero di shard (merge indici piccoli con `_shrink` o `reindex`)
- Aumenta heap (fino al 31 GB max)
- Controlla aggregazioni su campi `text` (convertile in `keyword`)
- Abilita `indices.breaker.total.limit` per evitare OOM

### Problemi di Reindexing Lento

```json
POST _reindex?wait_for_completion=false
{
  "source": {
    "index": "vecchio-indice",
    "size": 5000
  },
  "dest": { "index": "nuovo-indice" }
}

# Monitora il task
GET _tasks?actions=*reindex&detailed
```

---

## ELK / Elastic Stack

L'Elastic Stack (ex ELK) è la combinazione più comune per log analytics:

```
Sorgenti log          Raccolta            Store + Index      Visualizzazione
──────────────    ──────────────────    ────────────────    ────────────────
App / Container → Filebeat / Logstash → Elasticsearch    → Kibana
Server / VMs    → Metricbeat          →
K8s             → Elastic Agent       →
```

**Componenti principali:**

| Componente | Ruolo |
|------------|-------|
| **Elasticsearch** | Storage, indexing, search, analytics |
| **Kibana** | Dashboard, Discover, Lens, Maps, Alerting |
| **Logstash** | ETL pesante: parse, transform, filter, multiple output |
| **Beats** | Agent leggero: Filebeat (log), Metricbeat (metrics), Packetbeat (network) |
| **Elastic Agent** | Agent unificato (sostituisce tutti i Beats) |
| **Fleet** | Gestione centralizzata degli Elastic Agent |

**Alternativa cloud-native (log):** Grafana Loki è significativamente più economico per pure log aggregation perché non indicizza il contenuto — Elasticsearch indicizza tutto e offre full-text search ma a costo di storage e risorse molto più elevati.

---

## Relazioni

??? info "Apache Cassandra — Confronto per write-heavy"
    Cassandra è preferibile a Elasticsearch per write ad alto throughput (IoT, event sourcing) dove la ricerca full-text non è necessaria. Elasticsearch ha latenza di indicizzazione più alta e non supporta transazioni.

    **Approfondimento →** [Apache Cassandra](cassandra.md)

??? info "Grafana Loki — Alternativa log analytics"
    Loki non indicizza il contenuto dei log (solo le label), quindi è più economico di Elasticsearch per pure log aggregation. Elasticsearch è necessario quando servono ricerche full-text sul contenuto dei log.

    **Approfondimento →** [Grafana Loki](../../monitoring/tools/loki.md)

??? info "Sharding — Fondamentali distribuzione dati"
    Il concetto di sharding di Elasticsearch segue gli stessi principi del sharding nei database relazionali — con la differenza che in ES il routing è automatico basato sull'`_id`.

    **Approfondimento →** [Sharding](../fondamentali/sharding.md)

---

## Riferimenti

- [Elasticsearch Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html) — documentazione ufficiale completa
- [Elasticsearch: The Definitive Guide](https://www.elastic.co/guide/en/elasticsearch/guide/master/index.html) — guida concettuale (ES 2.x ma ancora valida concettualmente)
- [Elastic Blog — Sizing Guide](https://www.elastic.co/blog/found-sizing-elasticsearch) — dimensionamento cluster
- [Query DSL Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html) — riferimento completo Query DSL
- [ILM Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html) — gestione ciclo di vita indici
