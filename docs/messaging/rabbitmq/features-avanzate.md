---
title: "Features Avanzate"
slug: features-avanzate
category: messaging
tags: [rabbitmq, streams, dead-letter, ttl, priority-queue, federation, shovel, lazy-queue, dlx]
search_keywords: [rabbitmq streams, dead letter exchange dlx, ttl rabbitmq, priority queue rabbitmq, lazy queue, federation rabbitmq, shovel rabbitmq, retry delay rabbitmq, rabbitmq wan, consumer offset rabbitmq streams, message expiry]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/architettura, messaging/rabbitmq/affidabilita, messaging/rabbitmq/clustering-ha, messaging/kafka/_index]
official_docs: https://www.rabbitmq.com/docs/streams
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Features Avanzate

## RabbitMQ Streams — Append-Only Log

Le **Streams** sono un tipo di queue introdotto in RabbitMQ 3.9 che aggiunge capacità di streaming simili a Kafka mantenendo la compatibilità con il broker RabbitMQ. Sono il tipo di queue con le caratteristiche più diverse rispetto alle Classic/Quorum Queues.

```
Classic/Quorum Queue vs Stream — Modello Fondamentale

  QUEUE CLASSICA:
  ┌────────────────────────────┐
  │  msg1 │ msg2 │ msg3 │ msg4 │
  └────────────────────────────┘
       ▲ consumer legge          ▲ producer scrive
       │ e rimuove
       └ msg1 rimosso dopo ack
  Ogni messaggio consumato UNA volta, poi eliminato.
  Un consumer group condivide i messaggi (competing consumers).

  STREAM:
  ┌─────────────────────────────────────────────────────────────┐
  │  msg1 │ msg2 │ msg3 │ msg4 │ msg5 │ msg6 │ ...             │
  └─────────────────────────────────────────────────────────────┘
  offset:  0      1      2      3      4      5
           ▲                                  ▲
           Consumer A (legge da offset 0)     producer scrive
           Consumer B (legge da offset 3)
  I messaggi NON vengono eliminati dopo la lettura.
  Ogni consumer ha il proprio offset. Replay possibile.
```

**Quando scegliere Streams vs Quorum Queues:**

| Scenario | Tipo consigliato |
|----------|-----------------|
| Task queue (ogni task processato 1 volta) | Quorum Queue |
| Replay necessario (nuovi consumer, debug) | Stream |
| Multiple consumer groups indipendenti | Stream |
| Fan-out ad alto volume con storage efficiente | Stream |
| RPC, request-reply | Quorum Queue |
| Event sourcing light (senza Kafka) | Stream |
| Messaggi grandi (>10MB) | Quorum Queue |

```python
# Setup e uso RabbitMQ Streams con Python stream client
from rabbitmq_stream_python.environment import Environment

env = Environment(host="rabbitmq", port=5552)  # porta dedicata streams

# Crea lo stream
await env.create_stream(
    "audit-events",
    arguments={
        "max-length-bytes": 10 * 1024 * 1024 * 1024,  # 10GB retention
        "max-age": "7D",                                # retention per tempo
        "stream-max-segment-size-bytes": 500 * 1024 * 1024  # 500MB per segmento
    }
)

# Producer
producer = await env.create_producer("audit-events")
await producer.send(b'{"event": "user.login", "user_id": 123}')

# Consumer con offset
consumer = await env.create_consumer(
    "audit-events",
    callback=on_message,
    offset_specification=OffsetSpecification.offset(0),  # leggi dall'inizio
    # oppure:
    # OffsetSpecification.last()    → solo nuovi messaggi
    # OffsetSpecification.first()   → dall'inizio
    # OffsetSpecification.timestamp(t) → da un momento specifico
    # OffsetSpecification.next()    → dal prossimo non letto
)
```

**Streams via AMQP 0-9-1 (compatibilità con librerie esistenti):**

```python
# Le Streams sono accessibili anche via AMQP classico
# ma senza tracking dell'offset (ogni consumer ottiene tutti i msg)
channel.queue_declare(
    queue='audit-events',
    durable=True,
    arguments={'x-queue-type': 'stream'}
)

# Consumer via AMQP deve specificare x-stream-offset
channel.basic_consume(
    queue='audit-events',
    on_message_callback=on_message,
    arguments={'x-stream-offset': 'first'}  # o un numero di offset
)
```

---

## Dead Letter Exchange (DLX)

Il **Dead Letter Exchange** è il meccanismo per cui RabbitMQ gestisce i messaggi che non possono essere consegnati o elaborati correttamente.

Un messaggio diventa "dead letter" quando:
1. **Rejected** via `basic_reject` o `basic_nack` con `requeue=False`
2. **TTL scaduto** — il messaggio è rimasto in coda oltre il `x-message-ttl`
3. **Queue piena** — `x-max-length` o `x-max-length-bytes` raggiunto
4. **Delivery limit raggiunto** (solo Quorum Queues con `x-delivery-limit`)

```
DLX Pattern — Architettura

  Queue principale           DLX                  Dead Queue
  ┌──────────────┐          ┌──────────────┐      ┌────────────────┐
  │ orders       │ ─reject─►│ orders-dlx   │─────►│ orders-dlq     │
  │ durable      │ ─ttl────►│ (direct)     │      │ durable        │
  │ x-dlx:       │ ─full───►│              │      │ per analisi/   │
  │  orders-dlx  │          └──────────────┘      │ replay manuale │
  └──────────────┘                                └────────────────┘
                                                         │
                                                    Consumer DLQ
                                                  (alert, log, UI)
```

```python
# Setup DLX completo

# 1. Dichiarare il DLX (è un exchange normale)
channel.exchange_declare(
    exchange='orders-dlx',
    exchange_type='direct',
    durable=True
)

# 2. Dichiarare la Dead Letter Queue
channel.queue_declare(
    queue='orders-dlq',
    durable=True,
    arguments={
        # Opzionale: TTL sulla DLQ (per evitare accumulo infinito)
        'x-message-ttl': 7 * 24 * 3600 * 1000  # 7 giorni
    }
)

# 3. Bind DLQ al DLX
channel.queue_bind(
    exchange='orders-dlx',
    queue='orders-dlq',
    routing_key='orders.dead'    # routing key per i messaggi morti
)

# 4. Dichiarare la queue principale con DLX configurato
channel.queue_declare(
    queue='orders',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'orders-dlx',
        'x-dead-letter-routing-key': 'orders.dead',  # opzionale, usa la orig. key se omesso
        'x-queue-type': 'quorum',
        'x-delivery-limit': 3    # dopo 3 tentativi → DLX (solo quorum)
    }
)
```

**Ispezione dei messaggi morti:**

```python
# I messaggi nella DLQ contengono headers con metadata del decesso
def inspect_dead_letter(ch, method, properties, body):
    death_info = properties.headers.get('x-death', [])
    for death in death_info:
        print(f"Queue: {death['queue']}")
        print(f"Reason: {death['reason']}")  # rejected/expired/maxlen/delivery-limit
        print(f"Time: {death['time']}")
        print(f"Exchange: {death['exchange']}")
        print(f"Routing keys: {death['routing-keys']}")
        print(f"Count: {death['count']}")    # quante volte è "morto"

    # Decisione: retry manuale, log per analisi, alert ops
    ch.basic_ack(delivery_tag=method.delivery_tag)
```

---

## Retry con Delay — Pattern Dead Letter TTL

RabbitMQ non ha un meccanismo di delay nativo per i retry, ma il pattern DLX + TTL permette di implementare retry con backoff esponenziale.

```
Retry Pattern con DLX + TTL

  Flusso per errore temporaneo:

  Queue: orders          Queue: retry-30s      Queue: retry-5m
  ──────────────        ─────────────────     ──────────────────
  Msg arriva           Msg con ttl=30000      Msg con ttl=300000
  │                    │                     │
  Consumer fails       [30 secondi]          [5 minuti]
  nack(requeue=False)  TTL scade             TTL scade
       │                    │                    │
       ▼                    ▼                    ▼
  DLX: retry-exchange  DLX: orders-exchange  DLX: orders-exchange
       │                    │                    │
       routing: retry       routing: orders      routing: orders
       │                    │                    │
       ▼ (per tentativi     ▼ (retry #1)         ▼ (retry #2)
       1,2)
       ▼ (per tentativi 3+)
  DLX: dlq-exchange
       │
       ▼
  Queue: orders-dlq (permanente)
```

```python
def setup_retry_queues(channel):
    """Setup completo per retry con backoff."""

    exchange_name = 'orders'

    # Exchange principale
    channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)
    channel.exchange_declare(exchange='retry-exchange', exchange_type='direct', durable=True)
    channel.exchange_declare(exchange='dlq-exchange', exchange_type='direct', durable=True)

    # Queue principale
    channel.queue_declare(
        queue='orders',
        durable=True,
        arguments={
            'x-dead-letter-exchange': 'retry-exchange',
            'x-dead-letter-routing-key': 'retry-orders',
            'x-queue-type': 'quorum',
            'x-delivery-limit': 1   # max 1 tentativo prima di andare in retry
        }
    )
    channel.queue_bind(exchange=exchange_name, queue='orders', routing_key='orders')

    # Retry queue con 30 secondi di delay
    channel.queue_declare(
        queue='orders-retry-30s',
        durable=True,
        arguments={
            'x-dead-letter-exchange': exchange_name,    # ritorna alla queue principale
            'x-dead-letter-routing-key': 'orders',
            'x-message-ttl': 30_000,                    # 30 secondi
            'x-queue-type': 'quorum'
        }
    )
    channel.queue_bind(
        exchange='retry-exchange',
        queue='orders-retry-30s',
        routing_key='retry-orders'
    )

    # DLQ finale (dopo tutti i retry)
    channel.queue_declare(queue='orders-dlq', durable=True)
    channel.queue_bind(exchange='dlq-exchange', queue='orders-dlq', routing_key='dlq-orders')
```

!!! note "Plugin rabbitmq-delayed-message-exchange"
    Esiste un plugin ufficiale `rabbitmq-delayed-message-exchange` che implementa delay nativo. È più semplice ma ha overhead di performance e non supporta Quorum Queues. Il pattern DLX+TTL è più robusto per produzione.

---

## Message TTL

Il TTL (Time-To-Live) può essere configurato a livello di queue o di singolo messaggio.

```python
# TTL a livello di queue (tutti i messaggi scadono insieme)
channel.queue_declare(
    queue='notifications',
    durable=True,
    arguments={'x-message-ttl': 3600_000}  # 1 ora in ms
)

# TTL a livello di messaggio (per messaggio specifico)
channel.basic_publish(
    exchange='',
    routing_key='notifications',
    body=b'Flash sale in 30 minutes!',
    properties=pika.BasicProperties(
        expiration='1800000',    # 30 minuti in ms (stringa, non int!)
        delivery_mode=2
    )
)
```

!!! warning "TTL per-message vs per-queue"
    Quando entrambi sono configurati, il TTL minore ha precedenza. I messaggi con TTL per-queue scadono in ordine FIFO (il broker li controlla quando arrivano in testa alla queue). I messaggi con TTL per-message possono scadere ovunque nella queue, ma il broker li controlla solo quando arrivano in testa — questo può causare accumulo temporaneo di messaggi scaduti.

---

## Priority Queues

Le code con priorità permettono di processare messaggi ad alta priorità prima di quelli a bassa priorità.

```python
# Dichiarazione queue con priorità (max priority levels)
channel.queue_declare(
    queue='orders-priority',
    durable=True,
    arguments={
        'x-max-priority': 10,    # livelli da 0 (basso) a 10 (alto)
        # Nota: x-max-priority > 10 ha overhead crescente
        # In pratica, usare 3-5 livelli è sufficiente
    }
)

# Pubblicazione con priorità
channel.basic_publish(
    exchange='',
    routing_key='orders-priority',
    body=json.dumps(order).encode(),
    properties=pika.BasicProperties(
        priority=9,      # alta priorità (0=basso, max=alto)
        delivery_mode=2
    )
)
```

```
Priority Queue — Come funziona internamente

  Queue: orders-priority (x-max-priority=10)
  Internamente gestita come N sub-queue ordinate per priorità:

  Priority 10: [msg_A] [msg_B]         ← processati prima
  Priority  7: [msg_C]
  Priority  5: [msg_D] [msg_E] [msg_F]
  Priority  1: [msg_G] [msg_H]         ← processati dopo

  Il consumer riceve sempre dalla sub-queue con priorità più alta
  che ha messaggi disponibili.

  ATTENZIONE: se arrivano continuamente messaggi ad alta priorità,
  i messaggi a bassa priorità possono non essere mai processati (starvation).
  Soluzione: limitare il prefetch + monitorare le queue per priorità.
```

!!! warning "Priority Queues e Quorum Queues"
    Le Priority Queues sono supportate solo per Classic Queues. Le Quorum Queues non supportano `x-max-priority`. Se hai bisogno di HA + priorità, considera architetture alternative (code separate per priorità + consumer multipli, oppure logica applicativa).

---

## Lazy Queues

Le **Lazy Queues** memorizzano i messaggi su disco il prima possibile invece di mantenerli in RAM.

```
Standard Queue vs Lazy Queue

  Standard Queue (default):
  ┌────────────────────────────────────────────────────┐
  │ RAM: [msg1][msg2][msg3]...[msg_N]                  │
  └──────────────────────────────────────────┬─────────┘
                                             │ pagina su disco
                                             ▼ solo se RAM pressure
                                     [Disk: overflow]

  Lazy Queue:
  ┌──────────────┐
  │ RAM: (index) │  ← solo i metadati dei messaggi
  └──────┬───────┘
         │ scrive immediatamente
         ▼
  [Disk: tutti i messaggi]

  Trade-off:
  Lazy: throughput write simile, throughput read leggermente più basso
        ma memory footprint predictable anche con backlog enorme
```

```python
channel.queue_declare(
    queue='batch-jobs',
    durable=True,
    arguments={
        'x-queue-mode': 'lazy',    # Classic Queue: lazy mode
        # Nota: Quorum Queues sono SEMPRE lazy per design
    }
)
```

**Quando usare Lazy Queues:**
- Queue con backlog potenzialmente molto grande (milioni di messaggi)
- Consumer più lenti dei producer
- Ambienti con RAM limitata
- In genere: preferire Quorum Queues (sempre lazy) per nuove applicazioni

---

## Single Active Consumer

Il pattern **Single Active Consumer** garantisce che solo un consumer alla volta possa consumare da una queue, anche se ci sono più consumer connessi. Gli altri sono in standby.

```python
channel.queue_declare(
    queue='serial-processor',
    durable=True,
    arguments={
        'x-single-active-consumer': True,
        'x-queue-type': 'quorum'      # SAC supportato su quorum queues
    }
)

# Con più consumer connessi:
# Consumer A → ATTIVO (riceve messaggi)
# Consumer B → STANDBY
# Consumer C → STANDBY
# Se A crasha → B diventa attivo (failover automatico)
# Ordering garantito: i messaggi arrivano in ordine a un consumer alla volta
```

**Caso d'uso:** processing ordinato su una queue condivisa, job di manutenzione schedulati che devono girare su un singolo worker alla volta.

---

## Federation

La **Federation** è il meccanismo per collegare exchange o queue tra broker RabbitMQ separati, tipicamente in WAN multi-datacenter. A differenza del clustering (che richiede connettività LAN), Federation è progettata per reti con latenza alta e connessioni intermittenti.

```
Federation — Architettura Multi-Datacenter

  Datacenter EU (Primary)          Datacenter US
  ─────────────────────────        ────────────────────────
  RabbitMQ Broker EU               RabbitMQ Broker US
  ┌──────────────────────┐         ┌──────────────────────┐
  │ Exchange: orders     │◄────────│ Federation Link      │
  │ (upstream)           │  AMQP   │ (downstream/consumer)│
  │                      │  pull   │                      │
  │ Queue: orders-eu     │         │ Queue: orders-us     │
  └──────────────────────┘         └──────────────────────┘

  Il broker US "consuma" dall'exchange EU tramite un link AMQP.
  I messaggi vengono pulled su richiesta (quando ci sono consumer US attivi).
  Se il link cade: i messaggi restano nel broker EU, vengono sincronizzati
  quando il link si ripristina.
```

```bash
# Setup Federation via rabbitmqctl o Management API
# 1. Abilitare il plugin
rabbitmq-plugins enable rabbitmq_federation
rabbitmq-plugins enable rabbitmq_federation_management

# 2. Configurare upstream (il broker da cui federarsi)
rabbitmqctl set_parameter federation-upstream eu-primary \
    '{"uri":"amqp://user:pass@rabbitmq-eu.internal:5672",
      "prefetch-count":1000,
      "reconnect-delay":5,
      "ack-mode":"on-confirm",
      "trust-user-id":false}'

# 3. Policy per applicare la federazione all'exchange
rabbitmqctl set_policy --apply-to exchanges federate-orders \
    "^orders$" \
    '{"federation-upstream":"eu-primary"}'
```

**Federation Exchange vs Federation Queue:**

| | Exchange Federation | Queue Federation |
|---|---|---|
| **Uso** | Publish da qualsiasi nodo; i consumer locali ricevono messaggi che arrivano da altri datacenter | Consumer possono consumare da qualsiasi nodo; i messaggi vengono spostati dove ci sono consumer |
| **Direzione flusso** | Upstream → Downstream (push semantics: i messaggi scorrono verso i consumer) | Consumer-driven (pull: i messaggi si muovono verso i consumer attivi) |
| **Caso d'uso** | Pub/sub multi-region | Task queue distribuita geograficamente |

---

## Shovel

Lo **Shovel** trasferisce messaggi da una source (queue o exchange) a una destination, anche su broker diversi. A differenza della Federation (dinamica, policy-based), Shovel è una configurazione statica di forwarding.

```
Shovel — Forwarding Messaggi

  Broker A (source)              Broker B (destination)
  ────────────────              ─────────────────────
  Queue: legacy-orders ────────────────────────────► Exchange: new-orders
                        AMQP connection

  Shovel:
  - Consuma dalla source
  - Pubblica alla destination
  - Ack solo dopo conferma del publish (at-least-once)
  - Funziona tra versioni diverse di RabbitMQ
  - Funziona anche tra RabbitMQ e altri broker AMQP
```

```bash
# Shovel tramite Management API
rabbitmqctl set_parameter shovel migrate-orders \
    '{"src-protocol": "amqp091",
      "src-uri": "amqp://source-broker:5672",
      "src-queue": "legacy-orders",
      "src-prefetch-count": 100,
      "dest-protocol": "amqp091",
      "dest-uri": "amqp://dest-broker:5672",
      "dest-exchange": "new-orders",
      "dest-exchange-key": "orders.migrated",
      "ack-mode": "on-confirm",
      "reconnect-delay": 5}'
```

**Casi d'uso Shovel:**
- Migrazione da un broker a un altro con zero downtime
- Bridge tra ambienti (staging → production per replay di messaggi reali)
- Forwarding permanente tra sistemi con topologie diverse
- DR (Disaster Recovery): shovel da primary a secondary in modalità warm standby

---

## Troubleshooting

### Scenario 1 — Messages stuck in queue, consumers present but not consuming

**Sintomo:** La queue ha messaggi non consegnati (`messages_ready > 0`) ma i consumer sono connessi e `messages_unacknowledged` è basso o zero.

**Causa:** Il consumer ha raggiunto il limite `prefetch_count` (basic_qos) e sta bloccando perché non ha ancora ackato i messaggi in volo, oppure la queue è una Priority Queue con messaggi a bassa priorità mai processati (starvation).

**Soluzione:**
```bash
# Ispezionare lo stato della queue e dei consumer
rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
rabbitmqctl list_consumers queue_name channel_pid prefetch_count

# Verificare prefetch del consumer (valore 0 = illimitato, valori bassi = bottleneck)
rabbitmqctl list_channels name prefetch_count messages_unacknowledged

# Se starvation in priority queue: aumentare prefetch e monitorare per priorità
rabbitmqctl list_queues name messages_ready --formatter=pretty_table
```

---

### Scenario 2 — DLQ si riempie inaspettatamente

**Sintomo:** Messaggi arrivano continuamente nella Dead Letter Queue anche senza errori evidenti nei log del consumer.

**Causa comune 1:** Il consumer esegue `basic_nack(requeue=False)` anche per errori transitori (connessione DB, timeout), mandando il messaggio in DLX invece di farlo riaccodare.
**Causa comune 2:** `x-message-ttl` troppo basso rispetto ai tempi di processing; i messaggi scadono prima di essere consumati.
**Causa comune 3:** `x-delivery-limit` su Quorum Queue raggiunto per messaggi che falliscono troppo velocemente.

**Soluzione:**
```python
# Ispezionare gli headers x-death del messaggio nella DLQ per capire la causa
def inspect_dead_letter(ch, method, properties, body):
    death_info = properties.headers.get('x-death', [])
    for death in death_info:
        # 'reason' può essere: rejected / expired / maxlen / delivery-limit
        print(f"Reason: {death['reason']}, Queue: {death['queue']}, Count: {death['count']}")

# Controllare TTL configurato sulla queue
rabbitmqctl list_queues name arguments --formatter=pretty_table | grep -i ttl

# Verificare delivery-limit
rabbitmqctl list_queues name arguments | grep delivery-limit
```

---

### Scenario 3 — Stream consumer riceve messaggi dall'inizio ad ogni restart

**Sintomo:** Un consumer su una Stream Queue rilegge tutti i messaggi dall'offset 0 ad ogni riavvio dell'applicazione, causando elaborazione duplicata.

**Causa:** L'applicazione non persiste l'offset consumato. Con `OffsetSpecification.first()` o `OffsetSpecification.offset(0)` senza storage dell'offset, il consumer riparte sempre dall'inizio.

**Soluzione:**
```python
# Salvare e ripristinare l'offset tra restart
import redis

r = redis.Redis()
OFFSET_KEY = "stream:audit-events:consumer-group-A:offset"

async def on_message(msg):
    # ... processa il messaggio ...
    # Salva l'offset DOPO il processing
    await r.set(OFFSET_KEY, msg.offset)

# Al restart: recupera l'ultimo offset salvato
last_offset = await r.get(OFFSET_KEY)
offset_spec = (
    OffsetSpecification.offset(int(last_offset) + 1)
    if last_offset
    else OffsetSpecification.next()  # nuovi messaggi se prima esecuzione
)

consumer = await env.create_consumer(
    "audit-events",
    callback=on_message,
    offset_specification=offset_spec,
)
```

---

### Scenario 4 — Federation link DOWN, messaggi non sincronizzati

**Sintomo:** Il Federation link risulta in stato `{state, down}` o `{state, starting}`. I messaggi si accumulano sull'upstream ma non arrivano al downstream.

**Causa:** Connettività di rete interrotta, credenziali errate, o policy di federation non applicata correttamente all'exchange.

**Soluzione:**
```bash
# Verificare lo stato dei link federation
rabbitmqctl list_parameters --vhost / component federation-upstream
rabbitmqctl eval 'rabbit_federation_status:status().'

# Controllare lo stato dei link tramite Management API
curl -u admin:password http://rabbitmq:15672/api/federation-links

# Forzare il restart del link (se la causa è transiente)
# Tramite Management UI: Admin > Federation Status > Restart link
# Oppure via policy: ri-applicare la policy per forzare re-inizializzazione
rabbitmqctl clear_policy federate-orders
rabbitmqctl set_policy --apply-to exchanges federate-orders \
    "^orders$" '{"federation-upstream":"eu-primary"}'

# Verificare connettività verso l'upstream
rabbitmq-diagnostics check_port_connectivity --hostname rabbitmq-eu.internal --port 5672
```

---

## Riferimenti

- [RabbitMQ Streams](https://www.rabbitmq.com/docs/streams)
- [Dead Letter Exchanges](https://www.rabbitmq.com/docs/dlx)
- [TTL](https://www.rabbitmq.com/docs/ttl)
- [Priority Queues](https://www.rabbitmq.com/docs/priority)
- [Lazy Queues](https://www.rabbitmq.com/docs/lazy-queues)
- [Federation](https://www.rabbitmq.com/docs/federation)
- [Shovel](https://www.rabbitmq.com/docs/shovel)
- [Single Active Consumer](https://www.rabbitmq.com/docs/consumers#single-active-consumer)
