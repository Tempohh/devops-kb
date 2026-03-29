---
title: "Architettura AMQP"
slug: architettura
category: messaging
tags: [rabbitmq, amqp, exchange, queue, binding, routing, channel, prefetch, vhost]
search_keywords: [amqp 0-9-1, exchange types, direct exchange, fanout exchange, topic exchange, headers exchange, rabbitmq routing, queue properties, channel multiplexing, consumer prefetch, qos rabbitmq, virtual host, default exchange, dead letter, rabbitmq architecture]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/affidabilita, messaging/rabbitmq/features-avanzate, messaging/kafka/_index]
official_docs: https://www.rabbitmq.com/tutorials/amqp-concepts
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Architettura AMQP

## Il Modello AMQP 0-9-1

AMQP (Advanced Message Queuing Protocol) 0-9-1 è il protocollo nativo di RabbitMQ. Definisce un modello concettuale preciso con tre entità fondamentali:

```
AMQP 0-9-1 — Entità del Modello

  Producer                    Broker                    Consumer
  ─────────                ──────────────────────────   ────────
                           ┌──────────────────────┐
  app.publish(             │                      │
    exchange="orders",     │  Exchange             │    app.consume(
    routing_key="eu.high", │  ┌─────────────────┐ │      queue="orders-eu-high"
    body=message           │  │  Routing Logic  │ │    )
  )                        │  └────────┬────────┘ │
                           │           │ binding   │
                           │  Queue    ▼           │
                           │  ┌─────────────────┐ │    ack()
                           │  │ orders-eu-high  │ │◄───
                           │  │ orders-eu-low   │ │
                           │  │ orders-us       │ │
                           │  └─────────────────┘ │
                           └──────────────────────┘

  Regola fondamentale: il producer non sa MAI in quale queue finisce il messaggio.
  Invia all'exchange con una routing key; il broker decide.
```

Questo **disaccoppiamento tra producer e consumer** è la proprietà più importante di AMQP: i producer non sono a conoscenza delle code esistenti, i consumer non sanno chi ha prodotto il messaggio.

---

## Connection vs Channel — Il Multiplexing

Una delle decisioni architetturali più importanti in RabbitMQ è la distinzione tra **Connection** e **Channel**.

```
TCP Connection — Costosa da creare (handshake TCP + AMQP + autenticazione)
┌─────────────────────────────────────────────────┐
│  Connection (1 TCP socket)                       │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │Channel │ │Channel │ │Channel │ │Channel │   │
│  │   1    │ │   2    │ │   3    │ │   4    │   │
│  │publish │ │consume │ │publish │ │admin   │   │
│  └────────┘ └────────┘ └────────┘ └────────┘   │
└─────────────────────────────────────────────────┘

  Connection: risorsa TCP reale, ~1 per applicazione (o per thread pool)
  Channel:    canale logico multiplexato sulla connection, ~1 per thread/coroutine
```

| | Connection | Channel |
|---|---|---|
| **Natura** | TCP socket reale | Canale logico virtuale |
| **Costo di creazione** | Alto (TCP handshake + auth) | Basso (segnalazione AMQP) |
| **Costo a riposo** | ~100KB RAM nel broker | ~few KB RAM nel broker |
| **Uso consigliato** | 1 per applicazione (o pool piccolo) | 1 per thread, per consumer, per publisher |
| **Thread-safe** | No | No — mai condividere tra thread |
| **Max per connection** | N/A | 65535 (limite AMQP, pratico ~100-200) |

**Pattern corretto:**

```python
# Pattern: una connection, channel per operazione logica
import pika
import threading

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='rabbitmq',
        heartbeat=60,           # keepalive: rileva connection droppate
        blocked_connection_timeout=300,
        connection_attempts=3,
        retry_delay=2
    )
)

# Thread publisher — ha il suo channel
def publisher_thread():
    channel = connection.channel()  # channel dedicato
    # NOTA: pika BlockingConnection non è thread-safe
    # Usare SelectConnection + callbacks, o un channel per thread
    channel.basic_publish(...)

# In produzione: usare connection pool o un channel per thread
# con SelectConnection asincrona
```

!!! warning "Channel e Thread"
    In Python (pika), un Channel non è thread-safe. La pratica corretta è usare `SelectConnection` con callback asincroni, oppure aprire una connection separata per ogni thread (costoso ma sicuro). Framework come `aio-pika` (asyncio) gestiscono questo correttamente.

---

## Exchange Types — I 4 Tipi di Routing

L'exchange è il cuore del routing in RabbitMQ. Ogni exchange implementa un algoritmo di routing diverso.

### 1. Direct Exchange

**Routing:** il messaggio viene inviato alle code il cui binding key corrisponde **esattamente** alla routing key del messaggio.

```
Direct Exchange "payments"

  Messaggio (routing_key="credit")
        │
        ▼
  ┌─────────────────┐
  │ Exchange:       │
  │  payments       │
  │  type: direct   │
  └────────┬────────┘
           │
     ┌─────┴─────┐
     │           │
  binding:    binding:
  "credit"    "debit"
     │           │
     ▼           ▼
  Queue:       Queue:
  credit-      debit-
  processor    processor

  Solo "credit-processor" riceve il messaggio.
```

```python
# Setup Direct Exchange
channel.exchange_declare(
    exchange='payments',
    exchange_type='direct',
    durable=True
)

channel.queue_declare(queue='credit-processor', durable=True)
channel.queue_bind(
    exchange='payments',
    queue='credit-processor',
    routing_key='credit'       # binding key = routing key esatta
)

# Pubblicazione
channel.basic_publish(
    exchange='payments',
    routing_key='credit',      # → va in credit-processor
    body=json.dumps(payload).encode(),
    properties=pika.BasicProperties(delivery_mode=2)  # persistent
)
```

**Caso d'uso tipico:** distribuzione di task per tipo (log level, payment type, order country).

---

### 2. Fanout Exchange

**Routing:** il messaggio viene inviato a **tutte** le code associate all'exchange, ignorando completamente la routing key.

```
Fanout Exchange "events"

  Messaggio (routing_key ignorata)
        │
        ▼
  ┌─────────────────┐
  │ Exchange:       │
  │  events         │
  │  type: fanout   │
  └──┬──────┬───┬───┘
     │      │   │
     ▼      ▼   ▼
  Queue: Queue: Queue:
  logger audit  notifier

  Tutti e tre ricevono una copia del messaggio.
```

```python
channel.exchange_declare(exchange='events', exchange_type='fanout', durable=True)

# Ogni consumer dichiara la propria queue e la collega
# Le queue temporanee sono tipiche nei fanout (si cancellano al disconnect)
result = channel.queue_declare(queue='', exclusive=True)  # nome auto-generato
queue_name = result.method.queue

channel.queue_bind(exchange='events', queue=queue_name)
```

**Caso d'uso tipico:** broadcast di eventi a tutti i subscriber (pub/sub classico), invalidazione cache distribuita, notifiche a tutti i worker.

---

### 3. Topic Exchange

**Routing:** la routing key è interpretata come un **pattern gerarchico** usando il separatore `.`. I binding possono usare wildcard:

- `*` (asterisco): sostituisce esattamente **una** parola
- `#` (cancelletto): sostituisce **zero o più** parole

```
Topic Exchange "audit"

  routing_key="payment.credit.eu.high-value"
        │
        ▼
  ┌─────────────────────┐
  │ Exchange: audit      │
  │ type: topic         │
  └──────────┬──────────┘
             │
    ┌────────┼─────────┐
    │        │         │
  binding: binding:  binding:
  "payment.#" "*.*.eu.*" "#.high-value"
    │        │         │
    ▼        ▼         ▼
  Queue:  Queue:    Queue:
  all-    eu-       high-value-
  payments region   monitor

  Tutte e tre le code ricevono il messaggio perché tutti e 3 i pattern fanno match.
```

```python
channel.exchange_declare(exchange='audit', exchange_type='topic', durable=True)

# Binding con pattern
channel.queue_bind(
    exchange='audit',
    queue='all-payments',
    routing_key='payment.#'    # qualsiasi routing key che inizia con "payment."
)

channel.queue_bind(
    exchange='audit',
    queue='eu-region',
    routing_key='*.*.eu.*'     # 4 parole, terza = "eu"
)

channel.queue_bind(
    exchange='audit',
    queue='high-value-monitor',
    routing_key='#.high-value' # termina con "high-value", qualsiasi prefisso
)

# Pattern di routing key consigliato per topic exchange:
# <domain>.<type>.<region>.<priority>
# es: "payment.credit.eu.high-value"
#     "order.cancel.us.normal"
#     "auth.failure.*.critical"
```

**Caso d'uso tipico:** routing multi-dimensionale, log routing (app.module.level), eventi con attributi multipli.

---

### 4. Headers Exchange

**Routing:** non usa la routing key ma i **message headers** (AMQP header table). Supporta matching `all` (AND logico) o `any` (OR logico).

```
Headers Exchange "notifications"

  Messaggio con headers:
    x-priority: high
    x-type: billing
        │
        ▼
  ┌─────────────────────────┐
  │ Exchange: notifications  │
  │ type: headers           │
  └────────────┬────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
  Binding A:          Binding B:
  x-match: all        x-match: any
  x-priority: high    x-type: billing
  x-type: billing     x-region: eu
    │                     │
    ▼                     ▼
  Queue:             Queue:
  urgent-billing     billing-or-eu

  Binding A: match (entrambe le condizioni soddisfatte)
  Binding B: match (x-type=billing soddisfatta, basta una)
```

```python
channel.exchange_declare(
    exchange='notifications',
    exchange_type='headers',
    durable=True
)

# Binding con headers
channel.queue_bind(
    exchange='notifications',
    queue='urgent-billing',
    routing_key='',             # ignorata per headers exchange
    arguments={
        'x-match': 'all',       # AND: tutti gli header devono matchare
        'x-priority': 'high',
        'x-type': 'billing'
    }
)

# Pubblicazione con headers
channel.basic_publish(
    exchange='notifications',
    routing_key='',
    body=message_body,
    properties=pika.BasicProperties(
        headers={
            'x-priority': 'high',
            'x-type': 'billing',
            'x-region': 'eu'
        }
    )
)
```

**Caso d'uso tipico:** routing basato su attributi multipli del messaggio quando la routing key gerarchica non è sufficiente; filtri complessi con logica booleana.

---

### Il Default Exchange

RabbitMQ crea automaticamente un **default exchange** (exchange anonimo, nome = `""`). È un direct exchange speciale:

- Ogni queue è automaticamente legata al default exchange con una binding key uguale al nome della queue
- Pubblicare al default exchange con `routing_key="my-queue"` recapita direttamente alla queue `my-queue`

```python
# Pubblicazione diretta a una queue tramite default exchange
channel.basic_publish(
    exchange='',           # default exchange
    routing_key='my-queue' # = nome della queue
    body=b'Hello'
)
# Equivale a: exchange="" → binding automatica → queue "my-queue"
```

!!! note "Quando usare il default exchange"
    Il default exchange è utile per casi semplici e per test. In produzione, preferire exchange nominati espliciti: rendono l'architettura visibile nella management UI e permettono di evolvere il routing senza cambiare il codice dei producer.

---

## Queue Properties

Le code in RabbitMQ hanno proprietà che ne definiscono comportamento e ciclo di vita:

```python
channel.queue_declare(
    queue='orders',
    durable=True,          # sopravvive al restart del broker
    exclusive=False,       # non esclusiva alla connection
    auto_delete=False,     # non si cancella quando l'ultimo consumer si disconnette
    arguments={
        'x-message-ttl': 86400000,          # TTL messaggi: 24h in ms
        'x-max-length': 10000,              # max messaggi in coda
        'x-max-length-bytes': 104857600,    # max 100MB
        'x-overflow': 'reject-publish',    # rifiuta nuovi msg quando piena (vs drop-head)
        'x-dead-letter-exchange': 'dlx',   # DLX: dove vanno i msg rifiutati/scaduti
        'x-dead-letter-routing-key': 'orders.dlq',
        'x-queue-type': 'quorum',           # quorum queue (raft) vs classic
        'x-single-active-consumer': True   # solo un consumer attivo alla volta
    }
)
```

| Proprietà | Comportamento | Quando usare |
|-----------|---------------|--------------|
| `durable=True` | Sopravvive al restart del broker | **Sempre in produzione** |
| `durable=False` | Cancellata al restart | Solo per code temporanee |
| `exclusive=True` | Solo la connection che la crea può usarla; cancellata alla disconnect | Risposte RPC, code temporanee per consumer specifici |
| `auto_delete=True` | Cancellata quando l'ultimo consumer si disconnette | Pub/sub dinamico, code temporanee |
| `x-queue-type: quorum` | Raft consensus replication | **Produzione HA: preferire sempre** |
| `x-queue-type: classic` | Mirroring deprecato | Evitare per nuove applicazioni |
| `x-queue-type: stream` | Append-only log con consumer offset | Replay, multiple consumer groups |

---

## Consumer Prefetch — QoS e Fair Dispatch

Il **prefetch** è uno dei parametri più critici per le performance e la correttezza di RabbitMQ.

```
SENZA prefetch (default, prefetch=0 = illimitato):

  Broker                Worker A              Worker B
  ──────               ──────────            ──────────
  Queue: 1000 msg
    ├─────────── 500 msg ──────►  (Worker A riceve metà
    │                              dei messaggi subito,
    └─────────── 500 msg ──────►   anche se non riesce
                                   a processarli)
  Problema: Worker A è lento → accumula 500 msg in memoria
            Worker B ha finito → idle, aspetta

CON prefetch=10:

  Broker                Worker A              Worker B
  ──────               ──────────            ──────────
  Queue: 1000 msg
    ├── 10 msg ──────►  processa 10 msg     ◄── 10 msg ──┤
    │                   ack → broker invia  processa 10   │
    │                   altri 10 msg        ack → broker   │
    └── 10 msg ──────►  ecc.               invia altri 10 ┘

  Distribuzione fair: i messaggi sono distribuiti in base
  alla capacità effettiva di elaborazione.
```

```python
# QoS: impostare prima di iniziare a consumare
channel.basic_qos(
    prefetch_size=0,    # 0 = nessun limite sulla dimensione (in bytes) — lasciare 0
    prefetch_count=10,  # max 10 messaggi non-acked per consumer
    global_=False       # False = per-consumer (consigliato); True = per-channel
)

# Consumer con ack manuale (obbligatorio con prefetch)
def on_message(ch, method, properties, body):
    try:
        process(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except ProcessingError as e:
        # nack con requeue=False → va nel DLX
        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False
        )

channel.basic_consume(
    queue='orders',
    on_message_callback=on_message,
    auto_ack=False  # SEMPRE False in produzione
)
```

**Regole pratiche per il prefetch:**

```
prefetch=1   → massima fairness, throughput basso
              (il broker aspetta ogni ack prima di inviare il prossimo)
              Usare se: ogni messaggio ha tempo di elaborazione molto variabile

prefetch=10  → buon compromesso per la maggior parte dei task queue
              Usare se: elaborazione moderata, latenza variabile

prefetch=100 → alto throughput per messaggi piccoli e veloci
              Usare se: batch processing, messaggi leggeri

prefetch=0   → illimitato (default, quasi mai corretto in produzione)
              Usare solo se: certezza assoluta che il consumer non accumula
```

!!! warning "auto_ack=True è pericoloso"
    Con `auto_ack=True`, RabbitMQ considera il messaggio consegnato nel momento in cui lo mette sul TCP socket. Se il consumer crasha durante l'elaborazione, il messaggio è perso. **Usare sempre `auto_ack=False` in produzione** e chiamare `basic_ack` esplicitamente a elaborazione completata.

---

## Binding Chains — Exchange-to-Exchange Routing

AMQP 0-9-1 in RabbitMQ supporta il binding tra exchange (non solo exchange → queue), abilitando architetture di routing complesse senza modificare il codice dei producer.

```
Exchange-to-Exchange Binding

  Producer
    │
    ▼
  Exchange: "app.events" (topic)
    │  routing_key = "order.created.eu"
    ├──► Exchange: "eu-events" (fanout)  ←── binding: "*.*.eu"
    │         ├──► Queue: eu-logger
    │         └──► Queue: eu-analytics
    │
    └──► Exchange: "critical-events" (direct)  ←── binding: "#.critical"
              └──► Queue: ops-alerts

  Vantaggio: si possono aggiungere nuovi consumer "subscribendo" a un exchange
  intermedio senza toccare il producer o il primo exchange.
```

```python
# Binding exchange-to-exchange
channel.exchange_bind(
    destination='eu-events',   # exchange destinazione
    source='app.events',       # exchange sorgente
    routing_key='*.*.eu'       # pattern topic
)
```

---

## Virtual Hosts — Multi-Tenancy

I **Virtual Host** (vhost) sono namespace isolati all'interno del broker: exchange, code, binding e permessi sono separati per vhost.

```
RabbitMQ Broker
├── vhost: /           (default, development/testing)
│   ├── exchange: amq.direct
│   ├── exchange: amq.topic
│   └── queue: test-queue
├── vhost: /production
│   ├── exchange: orders
│   ├── exchange: events
│   └── queue: orders-eu
└── vhost: /staging
    ├── exchange: orders
    └── queue: orders-eu      (stesso nome, namespace separato)
```

```bash
# Gestione vhost via CLI
rabbitmqctl add_vhost /production
rabbitmqctl add_user app-user strong-password
rabbitmqctl set_permissions -p /production app-user \
    ".*"    # configure (declare/delete exchange/queue/binding)
    ".*"    # write (publish)
    ".*"    # read (consume, purge)

# Permessi granulari: regexp sulle risorse
rabbitmqctl set_permissions -p /production read-only-user \
    ""      # configure: nessun permesso (non può dichiarare)
    ""      # write: nessun permesso (non può pubblicare)
    ".*"    # read: accesso a tutto (può consumare)
```

---

## Flusso Completo: Anatomia di un Messaggio

```
1. Producer → Connection → Channel → Exchange
   channel.basic_publish(
       exchange='orders',
       routing_key='eu.high',
       body=payload,
       properties=BasicProperties(
           content_type='application/json',
           delivery_mode=2,          # 2=persistent (scritto su disco)
           message_id=str(uuid4()),
           timestamp=int(time()),
           correlation_id='req-123', # per RPC
           reply_to='reply-queue',   # per RPC
           headers={'x-retry': 0}
       )
   )

2. Exchange applica routing → Queue (se nessun match → messaggio scartato
                                     o ritornato se mandatory=True)

3. Queue: messaggio in attesa
   - Se durable+persistent: scritto su disco (Journal → Segment files)
   - Se transient: solo in memoria

4. Consumer ← Channel ← Connection ← Broker (push model)
   - Il broker invia fino a prefetch_count messaggi non-acked
   - Consumer elabora
   - Consumer chiama basic_ack(delivery_tag)

5. Broker riceve ack → rimuove il messaggio dalla queue (e dal disco se persistent)
```

---

## Troubleshooting

### Scenario 1 — Consumer riceve messaggi ma non li processa (stuck delivery)

**Sintomo:** I messaggi rimangono nello stato "Unacked" nella management UI. Il consumer è attivo ma non processa. La coda non si svuota.

**Causa:** `prefetch_count` troppo alto combinato con consumer lento, oppure il consumer ha chiamato `basic_consume` senza ack manuale e senza `auto_ack=True`. Frequente anche se il consumer è bloccato in un'operazione I/O con `auto_ack=False`.

**Soluzione:** Ridurre `prefetch_count`, verificare che ogni messaggio venga ackato o nackato, controllare i thread bloccati.

```bash
# Verificare messaggi unacked per queue
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged

# Verificare i consumer attivi e il loro prefetch
rabbitmqctl list_consumers queue_name channel_pid consumer_tag prefetch_count

# Se i consumer sono bloccati: forzare la chiusura del channel per rimettere in coda i msg
rabbitmqctl close_connection <conn-name> "stuck consumer cleanup"
```

---

### Scenario 2 — Messaggi persi dopo restart del broker

**Sintomo:** Dopo il riavvio di RabbitMQ, alcune o tutte le code risultano vuote. I messaggi pubblicati prima del restart sono scomparsi.

**Causa:** Queue o messaggi non durable/persistent. Una queue dichiarata con `durable=False` viene eliminata al restart. Messaggi pubblicati con `delivery_mode=1` (transient) non vengono scritti su disco anche su queue durable.

**Soluzione:** Verificare la combinazione durable (queue) + persistent (messaggio). Entrambi devono essere abilitati per la persistenza.

```python
# Queue durable
channel.queue_declare(queue='orders', durable=True)

# Messaggio persistent (delivery_mode=2)
channel.basic_publish(
    exchange='',
    routing_key='orders',
    body=payload,
    properties=pika.BasicProperties(delivery_mode=2)  # persistent
)
```

```bash
# Verificare se la queue è durable
rabbitmqctl list_queues name durable auto_delete
```

---

### Scenario 3 — Exchange non recapita messaggi (silent drop)

**Sintomo:** Il producer pubblica senza errori, ma il consumer non riceve nulla. La queue rimane vuota. Nessuna eccezione lato producer.

**Causa:** Mancata corrispondenza tra routing key del messaggio e binding key dell'exchange. Per direct/topic exchange, un mismatch silenzioso scarta il messaggio. Altra causa: la queue non è legata all'exchange corretto, o è legata a un vhost diverso.

**Soluzione:** Verificare binding nella management UI o via CLI. Abilitare `mandatory=True` per ricevere un `basic.return` se nessuna queue fa match.

```bash
# Ispezionare i binding di un exchange
rabbitmqctl list_bindings -p /production

# Oppure filtrare per exchange specifico
rabbitmqctl list_bindings -p /production | grep "orders"

# Verificare exchange esistenti e tipo
rabbitmqctl list_exchanges -p /production name type durable
```

```python
# mandatory=True: il broker ritorna il messaggio se non trova binding
channel.basic_publish(
    exchange='orders',
    routing_key='eu.high',
    body=payload,
    mandatory=True   # genera basic.return se nessun binding fa match
)

# Handler per messaggi ritornati
channel.add_on_return_callback(lambda ch, method, props, body:
    logger.error(f"Message returned: {method.reply_text}")
)
```

---

### Scenario 4 — Too many connections / channel error 504

**Sintomo:** L'applicazione riceve errori `AMQPChannelError: channel error; protocol method: (Channel.Close) reply-code=504` oppure il broker rifiuta nuove connessioni con `connection refused` o limiti superati.

**Causa:** Apertura di una nuova connection per ogni messaggio/thread invece di riutilizzare le connessioni. Oppure channel non chiusi correttamente dopo l'uso. RabbitMQ ha un limite di connessioni configurabile (default 65536, ma spesso il sistema operativo limita prima).

**Soluzione:** Implementare un connection pool, riutilizzare channels, monitorare le connessioni attive.

```bash
# Monitorare connessioni attive
rabbitmqctl list_connections name peer_host peer_port state channels

# Numero totale connessioni
rabbitmqctl list_connections | wc -l

# Chiudere connessioni idle da un host specifico
rabbitmqctl list_connections name peer_host | grep "10.0.0.5" | \
  awk '{print $1}' | xargs -I{} rabbitmqctl close_connection {} "cleanup"

# Verificare limite connessioni nel broker
rabbitmqctl environment | grep max_connections
```

```python
# Pattern corretto: una connection, channel per operazione
import pika
from contextlib import contextmanager

_connection = None

def get_connection():
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rabbitmq', heartbeat=60)
        )
    return _connection

@contextmanager
def get_channel():
    conn = get_connection()
    channel = conn.channel()
    try:
        yield channel
    finally:
        channel.close()  # sempre chiudere il channel
```

---

## Riferimenti

- [AMQP 0-9-1 Model Explained](https://www.rabbitmq.com/tutorials/amqp-concepts)
- [Exchanges, Routing Keys and Bindings](https://www.rabbitmq.com/tutorials/tutorial-four-python)
- [Consumer Prefetch](https://www.rabbitmq.com/docs/consumer-prefetch)
- [Exchange-to-Exchange Bindings](https://www.rabbitmq.com/docs/e2e)
- [Virtual Hosts](https://www.rabbitmq.com/docs/vhosts)
