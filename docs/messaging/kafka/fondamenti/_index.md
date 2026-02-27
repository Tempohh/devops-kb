---
title: "Fondamenti di Kafka"
slug: fondamenti
category: messaging
tags: [kafka, fondamenti, architettura, broker, topic, partizione]
search_keywords: [kafka fondamenti, architettura kafka, come funziona kafka, topic partizione offset, broker cluster kafka]
parent: messaging/kafka
related: []
official_docs: https://kafka.apache.org/documentation/
status: complete
difficulty: intermediate
last_updated: 2026-02-23
---

# Fondamenti di Kafka

I concetti fondamentali di Apache Kafka: architettura del sistema, modello di storage, componenti principali e ciclo di vita di un messaggio.

## Argomenti in questa sezione

| Argomento | Descrizione |
|-----------|-------------|
| [Architettura](architettura.md) | Panoramica dell'architettura distribuita di Kafka |
| [Topics e Partizioni](topics-partizioni.md) | Il modello di storage di Kafka: topics, partizioni e offset |
| [Produttori](produttori.md) | Come i producer pubblicano messaggi, configurazioni e garanzie |
| [Consumatori](consumatori.md) | Come i consumer leggono messaggi, polling e commit degli offset |
| [Consumer Groups](consumer-groups.md) | Bilanciamento del carico e rebalancing nei consumer group |
| [Broker e Cluster](broker-cluster.md) | Composizione del cluster, elezione del leader, ISR |
| [ZooKeeper e KRaft](zookeeper-kraft.md) | Gestione dei metadati: dalla dipendenza ZooKeeper al protocollo KRaft |
