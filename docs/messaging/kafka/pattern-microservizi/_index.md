---
title: "Pattern per Microservizi con Kafka"
slug: pattern-microservizi
category: messaging
tags: [kafka, microservizi, pattern, event-driven, architettura]
search_keywords: [kafka microservizi, event driven architecture, event sourcing kafka, saga pattern kafka, outbox pattern, cqrs kafka, dead letter queue]
parent: messaging/kafka
related: []
official_docs: https://kafka.apache.org/documentation/
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Pattern per Microservizi con Kafka

Pattern architetturali e di integrazione per costruire sistemi a microservizi resilienti, consistenti e scalabili con Apache Kafka come backbone di comunicazione.

## Argomenti in questa sezione

| Argomento | Descrizione |
|-----------|-------------|
| [Event-Driven Architecture](event-driven-architecture.md) | Principi e vantaggi dell'architettura orientata agli eventi |
| [Event Sourcing](event-sourcing.md) | Persistere lo stato come sequenza di eventi immutabili |
| [Saga Pattern](saga-pattern.md) | Gestire transazioni distribuite senza lock globali |
| [Outbox Pattern](outbox-pattern.md) | Garantire atomicità tra database e Kafka senza 2PC |
| [CQRS](cqrs.md) | Separare modello di lettura e scrittura con Kafka come bus di sincronizzazione |
| [Dead Letter Queue](dead-letter-queue.md) | Gestire messaggi non processabili senza bloccare il flusso |
