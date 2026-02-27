---
title: "AWS Messaging & Streaming"
slug: messaging
category: cloud
tags: [aws, messaging, sqs, sns, eventbridge, kinesis, msk, kafka, event-driven]
search_keywords: [AWS messaging, event driven architecture, SQS Simple Queue Service, SNS Simple Notification Service, EventBridge, Kinesis, MSK Managed Streaming Kafka, message queue, pub sub, fan-out, streaming, decoupling]
parent: cloud/aws/_index
related: [cloud/aws/messaging/sqs-sns, cloud/aws/messaging/eventbridge-kinesis, cloud/aws/compute/lambda]
official_docs: https://aws.amazon.com/messaging/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# AWS Messaging & Streaming

I servizi di messaging AWS permettono di **disaccoppiare** i componenti di un'architettura e costruire sistemi **event-driven**, **resilienti** e **scalabili**.

## Panoramica Servizi

```
AWS Messaging Portfolio

  ┌─────────────────────────────────────────────────────────────────┐
  │                        Message Queue                           │
  │  SQS ─── Coda distribuita, pull-based, at-least-once delivery  │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                     Pub/Sub Notification                        │
  │  SNS ─── Fan-out, push-based, topic → N subscriber             │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                      Event Bus / Router                         │
  │  EventBridge ─── Event bus, rules, Pipes, cross-account         │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                       Data Streaming                            │
  │  Kinesis Data Streams ─── Real-time streaming, shard-based      │
  │  Kinesis Firehose    ─── Delivery to S3/Redshift/OpenSearch     │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                     Managed Kafka                               │
  │  MSK ─── Apache Kafka fully managed + Serverless               │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Confronto Rapido

| Servizio | Paradigma | Delivery | Ordering | Retention | Use Case |
|----------|-----------|----------|----------|-----------|----------|
| SQS Standard | Queue | At-least-once | Best-effort | 14 giorni | Decoupling, worker pool |
| SQS FIFO | Queue | Exactly-once | Garantito | 14 giorni | Ordini, transazioni |
| SNS | Pub/Sub | At-least-once | No | No | Notifiche, fan-out |
| EventBridge | Event Bus | At-least-once | No | 24h archive | Event routing, orchestrazione |
| Kinesis Streams | Streaming | At-least-once | Per shard | 1-365 giorni | Real-time analytics, log |
| Kinesis Firehose | Delivery | At-least-once | No | No (buffer) | ETL → S3/Redshift |
| MSK | Kafka | At-least-once | Per partition | Configurabile | Kafka workloads, streaming |

---

## Architetture Comuni

### Fan-Out Pattern (SNS → SQS)

```
Producer
   │
   ▼
 SNS Topic
   ├──────────────────────────────┐
   ▼                              ▼
SQS Queue A                  SQS Queue B
(processing)                 (notification)
   │                              │
   ▼                              ▼
Lambda/ECS                   Lambda/Email
```

**Vantaggi:** ogni consumer processa indipendentemente, retry separati, filtraggio per tipo.

### Event-Driven con EventBridge

```
Microservizio A
   │ emette evento
   ▼
EventBridge Event Bus
   ├── Rule: pattern "order.created" → Lambda Process Order
   ├── Rule: pattern "order.created" → SQS → Inventory Service
   └── Rule: pattern "order.created" → SNS → Notification
```

### Stream Processing con Kinesis

```
IoT Devices / App Logs / Clickstream
   │
   ▼
Kinesis Data Streams (shard 1..N)
   ├── Consumer 1: Lambda (real-time alerts)
   ├── Consumer 2: KCL App (aggregation)
   └── Consumer 3: Kinesis Firehose → S3 (archivio)
```

---

## Quando Usare Cosa

| Scenario | Servizio Raccomandato |
|----------|----------------------|
| Job queue workers (email, resize immagini) | SQS Standard |
| Processamento ordinato (ordini, pagamenti) | SQS FIFO |
| Notifiche push (email, SMS, mobile) | SNS |
| Fan-out a multiple code SQS | SNS → SQS |
| Routing eventi tra microservizi | EventBridge |
| Integrare SaaS (Salesforce, Zendesk, Auth0) | EventBridge |
| Real-time log/clickstream processing | Kinesis Data Streams |
| ETL streaming → data lake S3 | Kinesis Firehose |
| Apache Kafka managed | MSK |
| Kafka workloads senza gestione infrastruttura | MSK Serverless |
| Scheduler tasks (cron, one-time) | EventBridge Scheduler |

---

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-message-processing: **[SQS & SNS](sqs-sns.md)**

    ---
    Code SQS (Standard e FIFO), SNS pub/sub, fan-out pattern, Dead Letter Queues, filtri messaggi

-   :material-lightning-bolt: **[EventBridge & Kinesis](eventbridge-kinesis.md)**

    ---
    EventBridge event bus, rules, Pipes, Scheduler; Kinesis Streams e Firehose; MSK Kafka managed

</div>
