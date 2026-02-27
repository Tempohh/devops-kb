---
title: "RabbitMQ"
slug: rabbitmq
category: messaging
tags: [rabbitmq, amqp, message-broker, queue, exchange, routing]
search_keywords: [rabbitmq, amqp broker, message queue, task queue, pub sub rabbitmq, rabbitmq enterprise, rabbitmq vs kafka, rabbitmq microservizi]
parent: messaging/_index
related: [messaging/kafka/_index, security/autenticazione/oauth2-oidc]
official_docs: https://www.rabbitmq.com/documentation.html
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# RabbitMQ

## Cos'è RabbitMQ — e Qual è la Sua Identità

RabbitMQ è un **message broker tradizionale**: il suo ruolo è ricevere messaggi dai producer, applicare logica di routing complessa, e recapitarli ai consumer nel modo più preciso possibile. Il broker è intelligente; i client sono semplici. Questo è l'opposto del modello Kafka, dove il broker è volutamente stupido (log append-only) e i client sono intelligenti (gestiscono gli offset).

**Il protocollo nativo è AMQP 0-9-1** — uno standard internazionale per il messaging che definisce una semantica ricca: scambi, code, binding, acknowledgement, transazioni. RabbitMQ supporta anche MQTT (IoT), STOMP (testo semplice), AMQP 1.0 e HTTP — fatto che lo rende naturale in ambienti eterogenei dove dispositivi diversi devono comunicare.

Scritto in **Erlang/OTP**, RabbitMQ eredita le proprietà del runtime Erlang: alta concorrenza, fault-tolerance intrinseca, hot code swapping. Il modello ad attori di Erlang è particolarmente adatto al messaging: ogni connection, channel e queue è un processo Erlang leggero e isolato.

---

## Il Modello Mentale: Smart Broker

```
KAFKA — Dumb Broker, Smart Clients
  Producer → Topic (log) → Consumer legge dall'offset X
  Il broker non sa chi ha letto cosa; il consumer decide

RABBITMQ — Smart Broker, Simple Clients
  Producer → Exchange → [routing logic] → Queue → Consumer
  Il broker decide DOVE va il messaggio; il client dichiara cosa vuole
```

Questa differenza architetturale fondamentale si traduce in casi d'uso diversi:

- RabbitMQ: **routing complesso, task queue, RPC, messaggi a vita breve** — "invia questo ordine al servizio corretto in base al paese e alla priorità"
- Kafka: **event streaming, audit log, event sourcing, replay** — "registra tutto quello che succede, i consumer decidono cosa fare e quando"

---

## Pro e Contro

### ✅ Pro

| Vantaggio | Dettaglio |
|-----------|-----------|
| **Routing sofisticato** | 4 tipi di exchange + binding chains: routing impossibile da replicare in Kafka senza codice applicativo |
| **Flessibilità protocolli** | AMQP, MQTT, STOMP, HTTP in un unico broker — ideale per sistemi eterogenei (IoT + backend) |
| **Semantica di consegna ricca** | Acknowledgement, reject, nack, requeue, DLX, TTL, priority — controllo fine-grained sul ciclo di vita |
| **Latenza bassa** | Push model con prefetch: sub-millisecondo per messaggi piccoli su rete locale |
| **RPC pattern nativo** | Request-reply con `reply_to` e `correlation_id` — pattern built-in, non workaround |
| **Back pressure integrata** | Credit-based flow control: il producer viene rallentato se il broker è sotto pressione |
| **Gestione risorse intelligente** | Memory/disk alarms: il broker blocca i producer prima di saturarsi |
| **Management UI** | Dashboard web ricca, HTTP API completa, metriche granulari per queue/connection/channel |
| **Maturità** | 18+ anni di produzione, community vasta, operatori Kubernetes maturi |

### ❌ Contro

| Svantaggio | Dettaglio |
|------------|-----------|
| **Nessun replay nativo** | I messaggi consumati vengono eliminati (salvo Streams) — impossibile rileggere da un offset come Kafka |
| **Throughput limitato rispetto a Kafka** | ~50K-150K msg/s per nodo vs Kafka a 1M+/s — non adatto a ingestion ad alto volume |
| **Clustering su WAN complesso** | Erlang distribution è progettato per LAN/datacenter, non WAN — usare Federation/Shovel per multi-region |
| **Ordering non globale** | Garantito per queue singola, non attraverso exchange con multiple queue |
| **Mnesia come datastore** | Il database interno (Mnesia) può diventare un bottleneck con molte code e ha limitazioni di scala |
| **Network partitions pericolose** | Una partizione di rete può portare a split-brain — la configurazione del partition handling è critica |
| **Mirrored queues deprecate** | Le classic mirrored queues (HA pre-3.8) sono state deprecate in favore di Quorum Queues |
| **Erlang stack** | Troubleshooting profondo richiede conoscenza del runtime Erlang — non familiare alla maggior parte dei team |

---

## Quando Scegliere RabbitMQ

```
USA RABBITMQ quando:
  ✓ Il routing è complesso e basato sul contenuto/attributi del messaggio
  ✓ Hai bisogno di task queue con worker pool (job processing, background tasks)
  ✓ Devi implementare RPC su messaging (request-reply)
  ✓ I messaggi sono processati una volta e possono essere eliminati
  ✓ Hai ambienti eterogenei (IoT MQTT + backend AMQP)
  ✓ Hai bisogno di priority queue (messaggi urgenti processati prima)
  ✓ Il team non ha esperienza con event sourcing o stream processing

USA KAFKA quando:
  ✓ Devi fare replay degli eventi (debugging, nuovi consumer, event sourcing)
  ✓ Throughput molto alto (>100K msg/s sostenuto)
  ✓ Hai bisogno di audit trail permanente
  ✓ Stream processing in tempo reale (Kafka Streams, ksqlDB)
  ✓ Multiple consumer groups che leggono indipendentemente lo stesso stream
  ✓ Integrazione CDC (Debezium)

USA ENTRAMBI quando:
  ✓ Kafka per l'event backbone (high-volume streams)
  ✓ RabbitMQ per task routing e job queue (business logic)
```

---

## Argomenti

<div class="grid cards" markdown>

- **[Architettura AMQP](architettura.md)** — Exchange, queue, binding, routing keys, channel multiplexing, prefetch QoS
- **[Affidabilità e Durabilità](affidabilita.md)** — Publisher confirms, ack/nack, Quorum Queues (Raft), transazioni vs confirms
- **[Features Avanzate](features-avanzate.md)** — RabbitMQ Streams, Dead Letter Exchange, TTL, priority queues, Federation, Shovel
- **[Clustering e HA](clustering-ha.md)** — Cluster Erlang, network partitions, Quorum Queues HA, policy management
- **[Deployment](deployment.md)** — Kubernetes Cluster Operator, configurazione production, monitoring, security
- **[RabbitMQ vs Kafka](vs-kafka.md)** — Confronto tecnico approfondito: modelli, semantiche, casi d'uso, trade-off

</div>
