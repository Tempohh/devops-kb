---
title: "Sink Connectors"
slug: sink-connectors
category: messaging
tags: [kafka, connect, sink, elasticsearch, s3, jdbc]
search_keywords: [kafka connect sink, sink connector kafka, elasticsearch sink kafka, s3 sink connector, jdbc sink connector, kafka to database, kafka export data]
parent: messaging/kafka/kafka-connect
related: [messaging/kafka/kafka-connect/source-connectors]
official_docs: https://kafka.apache.org/documentation/#connect
status: complete
difficulty: intermediate
last_updated: 2026-02-23
---

# Sink Connectors

## Panoramica

I **sink connector** esportano dati da topic Kafka verso destinazioni esterne: database relazionali, motori di ricerca, data lake su object storage, sistemi di cache, API HTTP. Consumano record dai topic Kafka e li scrivono nella destinazione, gestendo automaticamente offset, retry, batching e scaling.

**Quando usarli:** Materializzazione di dati su database per query, indicizzazione su Elasticsearch, archiviazione su S3/GCS per data lake, sincronizzazione verso sistemi legacy.

## Concetti Chiave

**Consumer group** — Ogni sink connector agisce come un consumer group Kafka. Le partizioni del topic vengono distribuite tra i task del connector.

**Idempotency** — I sink connector migliori supportano scritture idempotenti: se un record viene scritto due volte (at-least-once), il risultato è lo stesso di una singola scrittura.

**Exactly-once (sink)** — Alcuni connector (es. JDBC Sink) supportano l'esatto-once tramite transazioni sul lato destinazione.

**Flush** — I record vengono accumulati in buffer e scritti in batch verso la destinazione. La frequenza di flush è controllabile.

## Configurazione & Pratica

### Elasticsearch Sink Connector

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "elasticsearch-orders-sink",
    "config": {
      "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
      "connection.url": "http://elasticsearch:9200",
      "type.name": "_doc",
      "topics": "orders",
      "key.ignore": "false",
      "schema.ignore": "true",

      "behavior.on.null.values": "DELETE",
      "behavior.on.malformed.documents": "WARN",

      "batch.size": 2000,
      "max.buffered.records": 20000,
      "flush.timeout.ms": 10000,
      "max.retries": 5,
      "retry.backoff.ms": 3000,

      "transforms": "addMetadata",
      "transforms.addMetadata.type": "org.apache.kafka.connect.transforms.InsertField$Value",
      "transforms.addMetadata.timestamp.field": "indexed_at"
    }
  }'
```

### S3 Sink Connector (Confluent)

Archivia record Kafka su Amazon S3, organizzandoli in partizioni per tempo o campo.

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "s3-archive-sink",
    "config": {
      "connector.class": "io.confluent.connect.s3.S3SinkConnector",
      "s3.region": "eu-west-1",
      "s3.bucket.name": "my-kafka-archive",
      "s3.part.size": "67108864",

      "topics": "orders,payments",
      "flush.size": "1000",
      "rotate.interval.ms": "3600000",
      "rotate.schedule.interval.ms": "3600000",

      "storage.class": "io.confluent.connect.s3.storage.S3Storage",
      "format.class": "io.confluent.connect.s3.format.parquet.ParquetFormat",

      "partitioner.class": "io.confluent.connect.storage.partitioner.TimeBasedPartitioner",
      "path.format": "'\''year'\''=YYYY/'\''month'\''=MM/'\''day'\''=dd/'\''hour'\''=HH",
      "locale": "en_US",
      "timezone": "UTC",

      "schema.compatibility": "FULL"
    }
  }'
```

**Struttura S3 risultante:**
```
s3://my-kafka-archive/
└── orders/
    └── year=2026/
        └── month=02/
            └── day=23/
                └── hour=14/
                    ├── orders+0+0000001000.parquet
                    └── orders+1+0000001500.parquet
```

### JDBC Sink Connector

Scrive record Kafka su tabelle di database relazionali. Supporta upsert (insert or update) tramite chiave primaria.

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "jdbc-orders-sink",
    "config": {
      "connector.class": "io.confluent.connect.jdbc.JdbcSinkConnector",
      "connection.url": "jdbc:postgresql://db:5432/analytics",
      "connection.user": "writer",
      "connection.password": "secret",

      "topics": "orders",
      "table.name.format": "${topic}",

      "insert.mode": "upsert",
      "pk.mode": "record_value",
      "pk.fields": "order_id",

      "auto.create": "true",
      "auto.evolve": "true",

      "batch.size": 500
    }
  }'
```

### HTTP Sink Connector (open source)

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "http-webhook-sink",
    "config": {
      "connector.class": "io.github.clescot.kafka.connect.http.sink.HttpSinkConnector",
      "http.url": "https://api.example.com/webhooks/orders",
      "http.request.method": "POST",
      "http.headers": "Content-Type:application/json,Authorization:Bearer ${env:API_TOKEN}",
      "topics": "orders",
      "tasks.max": "3"
    }
  }'
```

### Gestione errori e DLQ

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "elasticsearch-sink-with-dlq",
    "config": {
      "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
      "...": "...",

      "errors.tolerance": "all",
      "errors.log.enable": "true",
      "errors.log.include.messages": "true",

      "errors.deadletterqueue.topic.name": "orders.DLQ",
      "errors.deadletterqueue.topic.replication.factor": "3",
      "errors.deadletterqueue.context.headers.enable": "true"
    }
  }'
```

## Best Practices

!!! tip "Aumentare batch.size per throughput"
    I sink connector sono più efficienti quando scrivono in batch. `batch.size=1000` è un buon punto di partenza per la maggior parte dei sistemi.

!!! tip "Usare upsert con JDBC Sink"
    La modalità `insert.mode=upsert` con `pk.mode=record_value` e `pk.fields` rende il connector idempotente: riprocessare gli stessi messaggi non crea duplicati nel database.

!!! warning "S3 Sink e latenza"
    Il connector S3 scrive solo dopo che `flush.size` record sono stati accumulati o `rotate.interval.ms` è scaduto. Per analisi near-real-time, considerare un approccio differente (es. Kafka Streams → output topic → query).

!!! warning "Schema evolution con JDBC Sink"
    `auto.evolve=true` aggiunge colonne automaticamente, ma non rimuove colonne obsolete. Gestire le migration dello schema con cura in produzione.

## Troubleshooting

**Record scritti in ritardo (elevato lag)**
- Aumentare `tasks.max` (distribuisce le partizioni su più task)
- Aumentare `batch.size`
- Verificare performance della destinazione (es. Elasticsearch slow log)

**Errori di schema (schema mismatch)**
- Verificare che `value.converter` del connector corrisponda al formato effettivo dei record
- Con Schema Registry: verificare la compatibilità degli schemi

**Connector che reprocessa record dopo restart**
- Normale in at-least-once; la destinazione deve gestire duplicati
- Con JDBC Sink + upsert mode, il reprocessing è idempotente

## Riferimenti

- [Kafka Connect Documentation](https://kafka.apache.org/documentation/#connect)
- [Confluent S3 Sink Connector](https://docs.confluent.io/kafka-connectors/s3-sink/current/overview.html)
- [Confluent Elasticsearch Sink Connector](https://docs.confluent.io/kafka-connectors/elasticsearch/current/overview.html)
- [JDBC Sink Connector](https://docs.confluent.io/kafka-connectors/jdbc/current/sink-connector/overview.html)
