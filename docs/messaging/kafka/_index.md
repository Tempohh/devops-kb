---
title: "Apache Kafka"
slug: kafka
category: messaging
tags: [streaming, event-driven, pub-sub, distributed-systems, real-time]
search_keywords: [apache kafka, message broker, event streaming, topic, partition,
  consumer group, producer, consumer, offset, broker, zookeeper, kraft,
  log distribuito, coda messaggi, streaming dati, pipeline dati,
  kafka connect, kafka streams, exactly once, at least once, confluent]
parent: messaging/_index
related: [networking/tcp, containers/openshift]
official_docs: https://kafka.apache.org/documentation/
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Apache Kafka

Apache Kafka è una piattaforma di event streaming distribuita, progettata per gestire flussi di dati in tempo reale con alta affidabilità, scalabilità orizzontale e bassa latenza. Originariamente sviluppato da LinkedIn e successivamente donato alla Apache Software Foundation, Kafka è diventato lo standard de facto per architetture event-driven e microservizi.

**Quando usarlo:** Streaming di eventi in tempo reale, pipeline di dati, integrazione tra microservizi, change data capture (CDC), aggregazione di log, activity tracking.

**Quando NON usarlo:** Messaggistica semplice point-to-point con pochi messaggi al secondo (meglio RabbitMQ), storage a lungo termine come database primario, task queue con logica di retry complessa.

---

## 🗂️ Sezioni di questa Documentazione

<div class="grid cards" markdown>

-   :material-cube-outline:{ .lg .middle } **Fondamenti**

    ---

    Architettura, topics, partizioni, produttori, consumatori, broker e KRaft

    [:octicons-arrow-right-24: Esplora](fondamenti/)

-   :material-transit-connection-variant:{ .lg .middle } **Pattern per Microservizi**

    ---

    Event-driven, Event Sourcing, Saga, Outbox, CQRS, Dead Letter Queue

    [:octicons-arrow-right-24: Esplora](pattern-microservizi/)

-   :material-file-document-outline:{ .lg .middle } **Schema Registry**

    ---

    Avro, Protobuf, evoluzione degli schemi, compatibilità

    [:octicons-arrow-right-24: Esplora](schema-registry/)

-   :material-water-outline:{ .lg .middle } **Kafka Streams**

    ---

    Stream processing, topologie, ksqlDB, windowing e aggregazioni

    [:octicons-arrow-right-24: Esplora](kafka-streams/)

-   :material-connection:{ .lg .middle } **Kafka Connect**

    ---

    Connettori source/sink, CDC con Debezium, integrazione dati

    [:octicons-arrow-right-24: Esplora](kafka-connect/)

-   :material-shield-lock:{ .lg .middle } **Sicurezza**

    ---

    TLS/SSL, SASL, ACL, autenticazione e autorizzazione

    [:octicons-arrow-right-24: Esplora](sicurezza/)

-   :material-cog:{ .lg .middle } **Operazioni**

    ---

    Monitoring, performance tuning, replica, log compaction, disaster recovery

    [:octicons-arrow-right-24: Esplora](operazioni/)

-   :material-kubernetes:{ .lg .middle } **Kubernetes & Cloud**

    ---

    Strimzi Operator, Helm, Amazon MSK, deployment cloud-native

    [:octicons-arrow-right-24: Esplora](kubernetes-cloud/)

-   :material-code-braces:{ .lg .middle } **Sviluppo**

    ---

    Spring Kafka, Quarkus, exactly-once semantics, transazioni

    [:octicons-arrow-right-24: Esplora](sviluppo/)

</div>

---

## Architettura in Sintesi

Il cuore di Kafka è un **commit log distribuito**. I messaggi vengono scritti in modo sequenziale e immutabile su **partizioni** di un **topic**, replicati sui **broker** del cluster e consumati da **consumer group** che tracciano la propria posizione tramite **offset**.

```mermaid
flowchart LR
    P1[Producer 1] --> B1["Broker 1\nLeader P0"]
    P2[Producer 2] --> B2["Broker 2\nLeader P1"]
    B1 <-->|Replication| B2
    B1 --> T1P0[Topic A · Partition 0]
    B2 --> T1P1[Topic A · Partition 1]
    T1P0 --> C1["Consumer 1\nGroup X"]
    T1P1 --> C2["Consumer 2\nGroup X"]
```

!!! info "KRaft — Kafka senza ZooKeeper"
    A partire da Kafka 3.3+, il protocollo **KRaft** sostituisce ZooKeeper per la gestione dei metadati. Le nuove installazioni dovrebbero sempre usare KRaft.

---

## Riferimenti

- [Documentazione ufficiale Apache Kafka](https://kafka.apache.org/documentation/)
- [Kafka: The Definitive Guide (Confluent)](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/)
- [Confluent Developer Hub](https://developer.confluent.io/)
- [Strimzi — Kafka su Kubernetes](https://strimzi.io/documentation/)
