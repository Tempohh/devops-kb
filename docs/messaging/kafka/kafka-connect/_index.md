---
title: "Kafka Connect"
slug: kafka-connect
category: messaging
tags: [kafka, connect, connectors, cdc, debezium, integrazione]
search_keywords: [kafka connect, source connector, sink connector, debezium cdc, change data capture kafka, integrazione dati kafka, jdbc connector]
parent: messaging/kafka
related: []
official_docs: https://kafka.apache.org/documentation/#connect
status: complete
difficulty: intermediate
last_updated: 2026-02-23
---

# Kafka Connect

Kafka Connect è il framework di integrazione dati di Kafka: permette di importare dati da sorgenti esterne (database, file, API) verso topic Kafka, e di esportare dati da topic Kafka verso destinazioni esterne, senza scrivere codice.

## Argomenti in questa sezione

| Argomento | Descrizione |
|-----------|-------------|
| [Source Connectors](source-connectors.md) | Importare dati verso Kafka: JDBC, File, Debezium |
| [Sink Connectors](sink-connectors.md) | Esportare dati da Kafka: Elasticsearch, S3, JDBC |
| [Debezium e CDC](debezium-cdc.md) | Change Data Capture con Debezium per database relazionali |
