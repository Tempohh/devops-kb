---
title: "Azure Messaging"
slug: messaging-azure
category: cloud
tags: [azure, messaging, service-bus, event-grid, event-hubs, storage-queue, event-driven]
search_keywords: [Azure messaging, Service Bus, Event Grid, Event Hubs, Storage Queue, decoupling Azure, event-driven architecture Azure, pub-sub Azure, message queue Azure, Kafka Azure, streaming Azure]
parent: cloud/azure/_index
related: [cloud/azure/messaging/service-bus-event-grid, cloud/azure/messaging/event-hubs, cloud/azure/compute/app-service-functions]
official_docs: https://learn.microsoft.com/azure/service-bus-messaging/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Messaging

I servizi di messaging Azure permettono di **disaccoppiare** i componenti di un'architettura distribuita e costruire sistemi **event-driven**, **resilienti** e **scalabili**.

## Confronto Servizi

| Servizio | Paradigma | Delivery | Ordering | Retention | Use Case |
|----------|-----------|----------|----------|-----------|----------|
| **Service Bus Queue** | Queue | At-least-once | FIFO (opzionale) | 14 giorni | Decoupling, transazioni, job worker |
| **Service Bus Topic** | Pub/Sub | At-least-once | Per subscription | 14 giorni | Fan-out con filtri, notifiche |
| **Event Grid** | Pub/Sub (eventi) | At-least-once | No | 24h (retry) | Event routing da Azure Services/SaaS |
| **Event Hubs** | Streaming | At-least-once | Per partition | 1-90 giorni | Log, clickstream, telemetria IoT |
| **Storage Queue** | Queue | At-least-once | Best-effort | 7 giorni | Semplice decoupling, economico |

## Quando Usare Cosa

| Scenario | Servizio |
|----------|---------|
| Decoupling microservizi (ordini, pagamenti) | Service Bus Queue |
| Publish/subscribe con filtri per subscriber | Service Bus Topic |
| Reagire a eventi Azure (Blob created, VM started) | Event Grid (System Topic) |
| Integrare SaaS (GitHub, Salesforce) | Event Grid (Partner Topic) |
| Real-time log processing / telemetria IoT | Event Hubs |
| Kafka workloads su Azure | Event Hubs (Kafka API) |
| Queue semplice e low-cost per background task | Storage Queue |

## Architettura Fan-Out

```
Producer (microservizio)
    │
    ▼
Service Bus Topic
    ├── Subscription A (filtro: event=order.created) → Lambda-like Function → DB
    ├── Subscription B (filtro: event=order.created) → Email Service
    └── Subscription C (filtro: event=order.*) → Analytics → Event Hubs
```

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-message-processing: **[Service Bus & Event Grid](service-bus-event-grid.md)**

    ---
    Azure Service Bus (Queue, Topic/Subscription, sessions, DLQ), Event Grid (System Topics, routing, filtri, CloudEvents)

-   :material-lightning-bolt: **[Event Hubs](event-hubs.md)**

    ---
    Streaming ad alto volume, partizioni, consumer groups, Capture su Blob, compatibilità Kafka, Stream Analytics

</div>
