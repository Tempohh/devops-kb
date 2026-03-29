---
title: "RabbitMQ vs Kafka"
slug: vs-kafka
category: messaging
tags: [rabbitmq, kafka, confronto, messaging, streaming, architettura]
search_keywords: [rabbitmq vs kafka differenze, quando usare kafka vs rabbitmq, kafka throughput, rabbitmq routing, push vs pull model, message retention kafka, rabbitmq task queue, kafka event streaming, rabbitmq latenza, kafka replay, broker comparison, amqp vs kafka protocol]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/_index, messaging/kafka/_index, messaging/rabbitmq/architettura, messaging/rabbitmq/features-avanzate]
official_docs: https://www.rabbitmq.com/docs/streams
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# RabbitMQ vs Kafka

## Filosofia Fondamentale — Due Visioni del Messaging

Prima dei dettagli tecnici, è essenziale capire che RabbitMQ e Kafka non sono competitor diretti: risolvono problemi diversi con filosofie opposte.

```
DUE FILOSOFIE DEL MESSAGING

  RABBITMQ — "Il broker è intelligente"
  ─────────────────────────────────────
  Modello: SMART BROKER, SIMPLE CLIENTS

  Producer → Exchange (routing logic) → Queue → Consumer
                                                    ↓
                                               basic_ack()
                                                    ↓
                                          Messaggio ELIMINATO

  Il broker decide:
  ✓ Dove va il messaggio (routing)
  ✓ Quando eliminare il messaggio (dopo l'ack)
  ✓ Come bilanciare i consumer (round-robin, single-active)
  ✓ Cosa fare con i messaggi problematici (DLX, TTL)

  Il client non conosce:
  - Dove fisicamente è il messaggio
  - Quanti altri consumer esistono
  - La topologia delle queue

  ─────────────────────────────────────────────────────

  KAFKA — "Il broker è stupido"
  ─────────────────────────────
  Modello: DUMB BROKER (append-only log), SMART CLIENTS

  Producer → Topic (partition log) → Consumer (legge dal proprio offset)
                                            ↓
                                    commit_offset(n)
                                            ↓
                             Messaggio RIMANE nel log (fino a retention)

  Il broker fa solo:
  - Append-only writes
  - Retention-based cleanup
  - Rebalance dei consumer group

  Il client gestisce:
  - Il proprio offset (dove ha letto)
  - Il consumer group (coordinazione con altri consumer)
  - La gestione degli errori e dei retry
```

---

## Modello di Consegna — Push vs Pull

La differenza più operativa tra i due sistemi:

```
RABBITMQ — Push Model
─────────────────────
Broker                  Consumer
  │                        │
  │──── deliver msg ──────►│
  │                        │ elabora
  │◄─── basic_ack() ───────│
  │
  Caratteristiche:
  ✓ Latenza sub-millisecondo (il messaggio arriva appena disponibile)
  ✓ Il consumer non deve fare polling
  ✓ Backpressure via prefetch (il broker rallenta se il consumer è lento)
  ✗ Il consumer non controlla il ritmo di ricezione (oltre il prefetch)
  ✗ Il consumer non può "tornare indietro" nel log

KAFKA — Pull Model
──────────────────
Consumer                  Broker
  │                        │
  │──── fetch(offset=N) ──►│
  │◄─── records[N..N+K] ───│
  │
  Caratteristiche:
  ✓ Il consumer controlla completamente il ritmo di lettura
  ✓ Può leggere in batch ottimizzando throughput
  ✓ Può "tornare indietro" cambiando l'offset (seek)
  ✓ Se lento: rimane indietro ma non blocca il broker
  ✗ Latenza leggermente più alta (polling interval + batching)
  ✗ Consumer deve gestire il proprio offset e la coordinazione
```

---

## Ciclo di Vita del Messaggio

```
RABBITMQ — Messaggi a Vita Breve
─────────────────────────────────
                     consumer ACK
                         │
  Queue:  [msg1][msg2][msg3][msg4][msg5]
                              ▲
                         msg3 eliminato
                         dopo ACK

  I messaggi esistono solo quanto necessario per essere consumati.
  Non c'è concetto di "log" — è una queue FIFO con semantica di coda.

  Retention: determinata dal consumer (ack) o da TTL/max-length.

KAFKA — Log Permanente
──────────────────────
  Partition 0:
  [msg1][msg2][msg3][msg4][msg5][msg6]...[msg_N]
   off=0  off=1  off=2  off=3  off=4
            ▲               ▲
         Consumer A      Consumer B
         (offset=1)      (offset=3)
  I messaggi RIMANGONO nel log.
  Consumer A e B leggono indipendentemente dallo stesso log.
  Eliminazione: solo per policy di retention (time/size).

  Retention default: 7 giorni
  Retention configurabile: da ore a infinito (compaction per event sourcing)
```

---

## Routing e Filtri

```
RABBITMQ — Routing nel Broker
──────────────────────────────
Producer: routing_key = "payment.credit.eu.high-value"

Exchange (topic)
    ├── binding "payment.#"          → queue: all-payments-processor
    ├── binding "*.*.eu.*"           → queue: eu-team-monitor
    ├── binding "#.high-value"       → queue: risk-alert
    └── binding "payment.credit.*"  → queue: credit-team

4 queue ricevono lo stesso messaggio (o subset) con routing puro nel broker.
Il producer non conosce l'esistenza delle queue.
Aggiungere un nuovo consumer = aggiungere una queue + binding (zero code change).

KAFKA — Filtri nel Consumer
─────────────────────────────
Producer: topic = "payments" (nessun routing key applicato dal broker)

Consumer A: legge il topic completo, filtra in codice: if event.country == "eu"
Consumer B: legge il topic completo, filtra in codice: if event.amount > 10000
Consumer C: legge il topic completo, senza filtri

Alternativa con Kafka Streams / ksqlDB:
  CREATE STREAM eu_payments AS
  SELECT * FROM payments WHERE country = 'eu';
  → crea un nuovo topic filtrato, con overhead di stream processing

IMPLICAZIONE:
  RabbitMQ: routing nel broker = zero overhead applicativo
  Kafka: filtering nel client = ogni consumer legge TUTTI i messaggi
         e decide cosa ignorare (overhead CPU + rete per messaggi ignorati)
```

---

## Ordering e Garanzie

```
ORDERING RABBITMQ:
  - Garantito all'interno di una singola queue: FIFO strict
  - NON garantito attraverso exchange con multiple queue (per design)
  - Con Single Active Consumer: ordering globale per una queue

ORDERING KAFKA:
  - Garantito all'interno di una singola partizione: strict
  - NON garantito tra partizioni diverse dello stesso topic
  - Con partition key costante: tutti i messaggi della stessa "entità"
    vanno nella stessa partizione → ordering globale per chiave
    es: partition_key = customer_id → tutti gli eventi di un cliente
        sono in ordine

  Kafka per ordering globale:
  topic con 1 sola partizione = ordering assoluto ma nessuna parallelizzazione
  → Anti-pattern in produzione per topic ad alto volume
```

---

## Throughput — Numeri Reali

```
THROUGHPUT APPROSSIMATIVO (hardware medio, rete LAN)

  RabbitMQ (Classic/Quorum Queue, msg piccoli ~1KB):
  ├── 1 publisher, 1 consumer, no confirm:     ~150K msg/s
  ├── Publisher confirms (sync):               ~10K-20K msg/s
  ├── Publisher confirms (async batch 100):    ~80K-100K msg/s
  ├── Quorum Queues (Raft overhead):           ~50K-80K msg/s
  └── Con large messages (100KB+):             ~5K-10K msg/s

  Kafka (default config, msg ~1KB):
  ├── 1 producer, batch default:               ~300K-500K msg/s/partition
  ├── Produzione ottimizzata (linger, batch):  ~1M-2M msg/s
  ├── Multi-partition parallelism:             scalabilità lineare
  └── Replication factor 3:                   ~200K-400K msg/s

  CONCLUSIONE:
  - Kafka è 5-20x più veloce di RabbitMQ per ingestion pura
  - RabbitMQ è più che sufficiente per la maggior parte dei microservizi
    (< 100K msg/s è normale per la maggior parte delle applicazioni)
  - Il throughput non è il criterio discriminante per la scelta
```

---

## Tabella di Confronto Completa

| Dimensione | RabbitMQ | Kafka |
|------------|----------|-------|
| **Modello broker** | Smart broker (routing logic) | Dumb broker (log append-only) |
| **Modello consegna** | Push (broker → consumer) | Pull (consumer ← broker) |
| **Routing** | Nel broker: exchange types, binding keys | Nel consumer: filtri applicativi |
| **Retention messaggi** | Eliminati dopo ack (o TTL/max-length) | Persistenti per policy temporale/dimensionale |
| **Replay** | Non nativo (salvo Streams) | Nativo: seek a qualsiasi offset |
| **Ordering** | Per queue, strict FIFO | Per partizione, strict |
| **Consumer multipli** | Competing consumers (un consumer per msg) | Consumer groups indipendenti (tutti leggono tutto) |
| **Throughput** | ~100K msg/s per broker | ~1M+ msg/s per broker |
| **Latenza** | Sub-millisecondo | 1-10ms tipicamente |
| **Protocollo** | AMQP 0-9-1, MQTT, STOMP, HTTP | Kafka Wire Protocol (proprietario) |
| **Scaling** | Verticale + Federation orizzontale | Partizioni: scaling lineare orizzontale |
| **Ecosistema** | AMQP multi-vendor, librerie per tutti i linguaggi | JVM-first, Kafka Connect, Kafka Streams, ksqlDB |
| **Operatività** | Più semplice per team piccoli | Più complesso (ZooKeeper/KRaft, ISR, offset management) |
| **Use case primario** | Task queue, routing complesso, RPC, IoT | Event streaming, analytics, audit log, CDC |

---

## Decision Framework — Come Scegliere

```
DOMANDA 1: Il messaggio può/deve essere eliminato dopo l'elaborazione?
  SÌ → RabbitMQ candidato principale
  NO (serve replay/audit trail) → Kafka

DOMANDA 2: Il routing è complesso (basato su attributi, multi-destinazione)?
  SÌ → RabbitMQ (exchange types, binding patterns)
  NO (topic semplici) → Kafka o entrambi

DOMANDA 3: Hai bisogno di più consumer group che leggono lo stesso stream?
  SÌ → Kafka (consumer groups con offset indipendenti)
  NO (un consumer group per topic) → RabbitMQ o Kafka equivalenti

DOMANDA 4: Il throughput supera ~100K msg/s sostenuti?
  SÌ → Kafka obbligatorio
  NO → RabbitMQ più che sufficiente

DOMANDA 5: Hai bisogno di analisi storica, event sourcing, CDC?
  SÌ → Kafka
  NO → RabbitMQ

DOMANDA 6: Ambienti eterogenei (IoT, MQTT, legacy)?
  SÌ → RabbitMQ (multi-protocol: MQTT, STOMP, AMQP 1.0)
  NO → Kafka

DOMANDA 7: Il team ha esperienza con stream processing?
  NO → RabbitMQ (più intuitivo per sviluppatori OOP)
  SÌ → Kafka (accede a un ecosistema più potente)
```

---

## Pattern di Coesistenza — Usarli Insieme

La scelta non è sempre binaria. Molte architetture enterprise usano entrambi per sfruttare i punti di forza di ciascuno.

```
Pattern: Kafka come Event Backbone + RabbitMQ per Task Queue
────────────────────────────────────────────────────────────

  Sorgenti dati          Kafka (event backbone)       RabbitMQ (task routing)
  ────────────          ──────────────────────────   ──────────────────────────
  Microservizi         Topic: orders                  Exchange: task-router
  Database CDC    ───► Topic: inventory    ────────►  Queue: email-worker
  API Events           Topic: users                   Queue: pdf-generator
                            │                          Queue: notification-eu
                            │ Kafka Streams             Queue: notification-us
                            ▼
                       Topic: order-enriched
                            │
                            ▼
                    Analytics / Data Warehouse

  Kafka gestisce:
  - Alto volume di eventi
  - Audit trail permanente
  - Enrichment con stream processing
  - Alimentazione data warehouse / analytics

  RabbitMQ gestisce:
  - Distribuzione task ai worker (email, PDF, notifiche)
  - Routing per paese/tipo/priorità
  - RPC interni tra microservizi
  - Retry con backoff, DLX per fallimenti

  BRIDGE: Kafka → RabbitMQ
  Un consumer Kafka legge da "order-enriched" e pubblica
  su RabbitMQ con routing appropriato per il task processing.
```

**Implementazione del bridge:**

```python
from kafka import KafkaConsumer
import pika
import json

class KafkaToRabbitMQBridge:
    """Consuma da Kafka e pubblica su RabbitMQ con routing."""

    def __init__(self):
        self.kafka_consumer = KafkaConsumer(
            'order-enriched',
            bootstrap_servers=['kafka:9092'],
            group_id='rabbitmq-bridge',
            value_deserializer=lambda m: json.loads(m.decode()),
            auto_offset_reset='earliest',
            enable_auto_commit=False
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rabbitmq')
        )
        self.rmq_channel = connection.channel()
        self.rmq_channel.confirm_delivery()

    def run(self):
        for msg in self.kafka_consumer:
            order = msg.value
            routing_key = self._determine_routing(order)

            try:
                self.rmq_channel.basic_publish(
                    exchange='task-router',
                    routing_key=routing_key,
                    body=json.dumps(order).encode(),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        message_id=order['order_id']
                    ),
                    mandatory=True
                )
                # Commit Kafka offset solo dopo successful RabbitMQ publish
                self.kafka_consumer.commit()

            except Exception as e:
                # Non committare l'offset → il messaggio verrà riletto
                raise

    def _determine_routing(self, order: dict) -> str:
        region = order.get('region', 'default')
        priority = 'high' if order.get('amount', 0) > 1000 else 'normal'
        return f"order.{region}.{priority}"
```

---

## Migrazione da RabbitMQ a Kafka (o viceversa)

```
QUANDO migrare RabbitMQ → Kafka:
  ✓ Il volume di messaggi ha superato ~200K msg/s sostenuti
  ✓ Nuovi use case richiedono replay/event sourcing
  ✓ Si sta adottando un'architettura event-driven con stream processing
  ✓ Serve CDC (Debezium) o integrazione con sistemi di analytics

QUANDO migrare Kafka → RabbitMQ (raro, ma possibile):
  ✓ La complessità operativa di Kafka supera i benefici
  ✓ Il routing complesso è gestito con codice applicativo costoso
  ✓ Latenza sub-millisecondo è un requisito hard
  ✓ Il team non ha competenze Kafka e il workload non lo richiede

STRATEGIA DI MIGRAZIONE ZERO-DOWNTIME:
  1. Deploy bridge (consumer da sorgente → producer verso destinazione)
  2. Doppio-write: il producer scrive su entrambi i sistemi
  3. Shift graduale dei consumer verso il nuovo sistema
  4. Verifica che gli offset/ack siano allineati
  5. Rimuovi il vecchio sistema quando tutti i consumer sono migrati
  6. Rimuovi il doppio-write dal producer
```

---

## Troubleshooting

### Scenario 1 — Consumer RabbitMQ lento, messaggi si accumulano nella queue

**Sintomo:** La queue cresce indefinitamente; i consumer non riescono a tenere il passo dei producer.

**Causa:** Prefetch count troppo alto (consumer prende più messaggi di quanti riesce a processare) oppure consumer single-threaded con latenza elevata per messaggio.

**Soluzione:** Ridurre il prefetch e scalare orizzontalmente i consumer.

```bash
# Verificare la profondità della queue e il consumer utilisation
rabbitmqctl list_queues name messages consumers consumer_utilisation

# Nel codice: impostare prefetch basso per task pesanti
channel.basic_qos(prefetch_count=1)  # un messaggio alla volta per consumer

# Scalare i consumer con Docker
docker-compose up --scale worker=5
```

---

### Scenario 2 — Kafka: consumer group bloccato, offset non avanza (consumer lag in crescita)

**Sintomo:** Il consumer lag aumenta costantemente; i messaggi vengono letti ma gli offset non vengono committati.

**Causa:** Il consumer crasha dopo aver ricevuto il messaggio ma prima del commit dell'offset (o `enable.auto.commit=true` con intervallo troppo lungo).

**Soluzione:** Verificare lo stato del consumer group e abilitare commit manuale.

```bash
# Ispezionare il lag del consumer group
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group my-group --describe

# Reset dell'offset a latest (se i messaggi persi sono accettabili)
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group my-group --topic my-topic \
  --reset-offsets --to-latest --execute

# Reset a un timestamp specifico
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --group my-group --topic my-topic \
  --reset-offsets --to-datetime 2026-03-29T00:00:00.000 --execute
```

---

### Scenario 3 — Messaggi duplicati dopo failover (RabbitMQ o Kafka)

**Sintomo:** I consumer ricevono lo stesso messaggio più volte dopo un riavvio o un rebalance.

**Causa:** RabbitMQ: messaggio consegnato ma non ancora acknowledged quando il consumer va down → il broker lo reinvia. Kafka: l'offset non era stato committato al momento del crash.

**Soluzione:** Implementare idempotenza lato consumer con deduplication key.

```python
# RabbitMQ: usare message_id per deduplication
import redis

redis_client = redis.Redis()

def process_message(ch, method, properties, body):
    msg_id = properties.message_id
    if redis_client.setnx(f"processed:{msg_id}", "1"):
        redis_client.expire(f"processed:{msg_id}", 86400)  # TTL 24h
        # elabora il messaggio
        do_work(body)
    # sempre ack per evitare reinvii infiniti
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Kafka: commit manuale dopo elaborazione idempotente
consumer.poll(timeout_ms=1000)
process_records(records)  # idempotente
consumer.commit()          # solo dopo elaborazione completata
```

---

### Scenario 4 — Bridge Kafka→RabbitMQ perde messaggi durante riavvio

**Sintomo:** Dopo il riavvio del bridge, alcuni messaggi non arrivano su RabbitMQ pur essendo presenti in Kafka.

**Causa:** Il bridge committava l'offset Kafka prima di ricevere la conferma di publish da RabbitMQ (`mandatory=True` + conferma publish non attesa).

**Soluzione:** Committare l'offset Kafka solo dopo la conferma sincrona di RabbitMQ e implementare publisher confirms.

```python
# Configurazione corretta: disable auto-commit Kafka
consumer = KafkaConsumer(
    'topic',
    enable_auto_commit=False,   # commit manuale
    auto_offset_reset='earliest'
)

# Abilitare publisher confirms su RabbitMQ
channel.confirm_delivery()  # abilita modo sincrono

for msg in consumer:
    try:
        channel.basic_publish(
            exchange='my-exchange',
            routing_key='my-key',
            body=msg.value,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        # basic_publish in confirm_delivery mode è sincrono:
        # ritorna solo quando RabbitMQ ha confermato la ricezione
        consumer.commit()  # offset committato DOPO conferma RabbitMQ
    except pika.exceptions.UnroutableError:
        # Messaggio non routable: loggare e decidere (DLQ o skip)
        logger.error("Messaggio non routable: %s", msg.value)
```

---

## Riferimenti

- [RabbitMQ vs Kafka — Analisi ufficiale Broadcom](https://www.rabbitmq.com/docs/streams#compared-to-kafka)
- [Confluent: RabbitMQ vs Kafka](https://www.confluent.io/learn/rabbitmq-vs-apache-kafka/)
- [Martin Fowler: Messaging Patterns](https://www.enterpriseintegrationpatterns.com/)
- [RabbitMQ Streams (alternativa Kafka-like)](https://www.rabbitmq.com/docs/streams)
