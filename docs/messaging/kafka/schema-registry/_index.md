---
title: "Schema Registry"
slug: schema-registry
category: messaging
tags: [kafka, schema-registry, avro, protobuf, schema-evolution]
search_keywords: [confluent schema registry, avro kafka, protobuf kafka, schema evolution, compatibilità schemi, serializzazione kafka]
parent: messaging/kafka
related: []
official_docs: https://docs.confluent.io/platform/current/schema-registry/index.html
status: complete
difficulty: intermediate
last_updated: 2026-02-23
---

# Schema Registry

Lo Schema Registry è un servizio centralizzato per la gestione degli schemi dei messaggi Kafka. Garantisce la compatibilità dei contratti tra producer e consumer nel tempo, abilitando l'evoluzione controllata delle strutture dati.

## Argomenti in questa sezione

| Argomento | Descrizione |
|-----------|-------------|
| [Avro](avro.md) | Il formato di serializzazione più diffuso con Kafka |
| [Protobuf](protobuf.md) | Protocol Buffers come alternativa tipizzata ad Avro |
| [Evoluzione degli Schemi](schema-evolution.md) | Compatibilità forward, backward e full: regole e strategie |
