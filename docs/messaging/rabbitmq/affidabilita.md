---
title: "Affidabilità e Durabilità"
slug: affidabilita
category: messaging
tags: [rabbitmq, affidabilita, publisher-confirms, ack, nack, quorum-queues, raft, durabilita, persistenza]
search_keywords: [publisher confirms rabbitmq, ack nack requeue, quorum queues raft, message persistence, mandatory flag, transazioni amqp, at-least-once rabbitmq, exactly-once messaging, dead letter queue, delivery guarantees rabbitmq]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/architettura, messaging/rabbitmq/features-avanzate, messaging/rabbitmq/clustering-ha]
official_docs: https://www.rabbitmq.com/docs/reliability
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Affidabilità e Durabilità

## Le Garanzie di Consegna in RabbitMQ

RabbitMQ offre garanzie di consegna configurabili a livello di ogni componente. La comprensione di questi layer è critica per costruire sistemi affidabili.

```
Layer di Affidabilità

  Producer ──► Exchange ──► Queue ──► Consumer
     │              │           │          │
  Publisher      Mandatory   Durabilità  Consumer
  Confirms       Flag        + QueueType  Acks
     │              │           │          │
  "Il broker ha   "Se nessuna "Il msg      "Il msg
   accettato il    queue fa    sopravvive   è stato
   messaggio?"     match,      al restart?" elaborato
                   cosa
                   succede?"
```

---

## Publisher Confirms

I **Publisher Confirms** sono il meccanismo per cui il broker conferma al producer che un messaggio è stato accettato e (se persistent+durable) scritto su disco.

```
Flusso Publisher Confirm

  Producer                     Broker
  ────────                   ──────────
  channel.confirm_select()
  ─────────────────────────►
                              <conferma modalità confirm>
  ◄─────────────────────────

  basic_publish(msg1) ──────►
                              <elabora>
  basic_publish(msg2) ──────►
                              <elabora>
  basic_publish(msg3) ──────►
                              <elabora>
                              <ack deliveryTag=1>
  ◄─────────────────────────
                              <ack deliveryTag=3, multiple=True>
  ◄─────────────────────────
  (ack multiple=True copre tutti i msg fino al tag 3)
```

```python
import pika
import threading
from collections import deque

def reliable_publisher(connection_params, exchange, messages):
    """Publisher con confirms e retry automatico."""
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()

    # Attiva la modalità confirm
    channel.confirm_delivery()

    # Tracking dei messaggi pending
    unconfirmed = {}
    delivery_tag = 0

    for message in messages:
        delivery_tag += 1
        unconfirmed[delivery_tag] = message

        channel.basic_publish(
            exchange=exchange,
            routing_key=message['routing_key'],
            body=message['body'],
            properties=pika.BasicProperties(
                delivery_mode=2,               # persistent
                message_id=message['id']
            ),
            mandatory=True                     # errore se nessun routing match
        )

        # Aspetta conferma (blocking per semplicità)
        # In produzione usare async confirms con callbacks
        if channel.is_open:
            connection.process_data_events(time_limit=0)

    # Attendi tutte le conferme pendenti
    # Se il broker non risponde entro il timeout → retry
    connection.close()
```

**Async Confirms (alta performance):**

```python
import pika
from pika.adapters.blocking_connection import BlockingChannel
import time

class AsyncPublisher:
    def __init__(self, connection_params):
        self.connection = pika.BlockingConnection(connection_params)
        self.channel = self.connection.channel()
        self.channel.confirm_delivery()

        # Callbacks per ack/nack
        self.channel.add_on_return_callback(self._on_return)

        self._pending = {}
        self._delivery_tag = 0

    def _on_return(self, channel, method, properties, body):
        """Chiamato per messaggi mandatory non routable."""
        print(f"Message returned: {method.reply_code} {method.reply_text}")
        # Logica di retry/DLQ

    def publish_batch(self, messages):
        """Pubblica un batch e attende tutte le conferme."""
        for msg in messages:
            self._delivery_tag += 1
            self._pending[self._delivery_tag] = msg

            self.channel.basic_publish(
                exchange=msg['exchange'],
                routing_key=msg['routing_key'],
                body=msg['body'],
                properties=pika.BasicProperties(delivery_mode=2),
                mandatory=True
            )

        # Processa gli eventi (receive acks)
        start = time.time()
        while self._pending and (time.time() - start) < 10:  # 10s timeout
            self.connection.process_data_events(time_limit=0.1)

        if self._pending:
            raise Exception(f"Timeout: {len(self._pending)} messaggi non confermati")
```

**Confirms vs Transazioni AMQP:**

| | Publisher Confirms | AMQP Transactions |
|---|---|---|
| **Semantica** | Async ack dal broker | Commit atomico (begin/publish/commit) |
| **Performance** | ~250-300 msg/s per singola sync confirm; batch async → alta | ~10-50x più lente dei confirms |
| **Uso** | **Raccomandato** in produzione | Evitare — overhead enorme, mantenute per compatibilità |
| **Garanzia** | At-least-once (broker ha ricevuto) | Atomicità multi-publish (raramente necessaria) |

---

## Message Persistence

La persistenza è il secondo layer: anche se il producer ha ricevuto un confirm, il messaggio deve sopravvivere a un restart del broker.

```
Dual Durability — Entrambi devono essere true:

  1. Queue durable=True
     channel.queue_declare(queue='orders', durable=True)
     → la queue sopravvive al restart

  2. Message delivery_mode=2 (persistent)
     properties=BasicProperties(delivery_mode=2)
     → il messaggio è scritto su disco

  Se solo uno dei due è True:
  - Queue durable + message transient → messaggio perso al restart
  - Queue non-durable + message persistent → irrelevante (la queue sparisce)
```

**Come RabbitMQ scrive su disco (Classic Queues):**

```
Message Write Path (Classic Queue, persistent)

  1. Message arriva al broker
  2. Scritto nel Journal (WAL) — append-only, flush sincrono
  3. Periodicamente: scritto nei Segment Files (storage permanente)
  4. Journal entry marcata come committed
  5. Publish confirm inviato al producer

  In caso di crash:
  - Recovery dal Journal + Segment Files al restart
  - Messaggi già confirmed ma non nel Segment: recuperati dal Journal

  Nota: il Journal è fsync() per ogni confirm in default config.
  Per throughput maggiore: x-queue-mode=lazy o Quorum Queues
```

---

## Consumer Acknowledgements

Il layer finale: il consumer deve confermare che ha elaborato con successo il messaggio.

```python
def process_order(ch, method, properties, body):
    """Consumer con gestione completa degli acknowledgement."""
    delivery_tag = method.delivery_tag

    try:
        order = json.loads(body)

        # Operazione idempotente (chiave per at-least-once)
        result = order_service.process(order)

        if result.success:
            # ACK: messaggio elaborato, rimuovi dalla queue
            ch.basic_ack(delivery_tag=delivery_tag)

        elif result.should_retry:
            # NACK con requeue: rimetti in coda per un altro consumer
            # ATTENZIONE: può creare loop infiniti se il messaggio è sempre bad
            ch.basic_nack(delivery_tag=delivery_tag, requeue=True)

        else:
            # NACK senza requeue: messaggio va nel DLX (se configurato)
            # oppure è semplicemente scartato
            ch.basic_nack(delivery_tag=delivery_tag, requeue=False)

    except json.JSONDecodeError:
        # Messaggio malformato → DLX, non ritentare
        ch.basic_reject(delivery_tag=delivery_tag, requeue=False)

    except TemporaryError:
        # Errore temporaneo → requeue con backoff
        # NOTA: RabbitMQ non ha backoff nativo;
        # usare DLX con TTL per retry con delay (vedi features-avanzate.md)
        ch.basic_nack(delivery_tag=delivery_tag, requeue=True)

    except Exception as e:
        # Errore inatteso → log + DLX
        logger.exception(f"Unexpected error processing delivery {delivery_tag}")
        ch.basic_nack(delivery_tag=delivery_tag, requeue=False)
```

**Tabella delle semantiche di ack:**

| Operazione | Effetto | Quando usare |
|------------|---------|--------------|
| `basic_ack(delivery_tag)` | Messaggio rimosso definitivamente | Elaborazione completata con successo |
| `basic_ack(delivery_tag, multiple=True)` | Ack di tutti i msg fino al tag | Batch processing completato |
| `basic_nack(delivery_tag, requeue=True)` | Rimesso in coda (al front) | Errore temporaneo, il messaggio è valido |
| `basic_nack(delivery_tag, requeue=False)` | Scartato o mandato al DLX | Messaggio non processabile |
| `basic_reject(delivery_tag, requeue=False)` | Equivalente a nack, solo 1 msg | Messaggio singolo non valido |
| `auto_ack=True` | Ack automatico alla consegna | **Evitare** — nessuna garanzia |

!!! warning "Il problema del requeue loop"
    `basic_nack(requeue=True)` rimette il messaggio in testa alla queue, dove verrà immediatamente consegnato di nuovo allo stesso (o un altro) consumer. Se il messaggio è intrinsecamente "bad" (es. dati corrotti, dipendenza mancante), questo crea un loop infinito che satura la queue e il CPU. **Soluzione:** usare un Dead Letter Exchange + contatore retry nell'header, oppure sempre `requeue=False` per errori deterministi.

---

## Quorum Queues — High Availability con Raft

Le **Quorum Queues** sono il tipo di queue raccomandato per la produzione a partire da RabbitMQ 3.8+. Sostituiscono le Classic Mirrored Queues (deprecate).

```
Quorum Queue — Architettura Raft

  RabbitMQ Cluster (3 nodi)
  ┌─────────┐   ┌─────────┐   ┌─────────┐
  │ Node 1  │   │ Node 2  │   │ Node 3  │
  │ (Leader)│   │(Follower│   │(Follower│
  │         │   │         │   │         │
  │Queue:   │   │Queue:   │   │Queue:   │
  │orders   │   │orders   │   │orders   │
  │[replica]│   │[replica]│   │[replica]│
  └────┬────┘   └────┬────┘   └────┬────┘
       │              │              │
       └──────────────┴──────────────┘
                    Raft Log

  Publish:  Producer → Leader → followers confermano (quorum=2/3)
            → Leader invia ack al producer
  Consume:  Consumer → Leader → dispatch
  Failover: Se Leader muore → elezione Raft → nuovo Leader in pochi secondi
```

**Come funziona Raft per le queue:**

```
Raft Write Path (quorum=3 nodi):

  1. Producer invia msg al Leader
  2. Leader appende al proprio Raft log
  3. Leader replica ai 2 Follower
  4. Almeno 1 Follower conferma (quorum = majority = 2/3)
  5. Leader marca l'entry come "committed"
  6. Invia publisher confirm al Producer
  7. Follower applicano l'entry committed ai loro stati locali

  Failover:
  - Leader crash → Follower con log più aggiornato viene eletto
  - Nessun messaggio committed può essere perso (garantito da Raft)
  - In-flight messages (non ancora committed) possono essere persi
    → il producer deve gestire il timeout + republish
```

```python
# Dichiarazione Quorum Queue
channel.queue_declare(
    queue='orders',
    durable=True,               # DEVE essere durable
    arguments={
        'x-queue-type': 'quorum',
        # Opzioni avanzate:
        'x-quorum-initial-group-size': 3,    # quorum size (default = tutti i nodi)
        'x-delivery-limit': 5,               # max delivery attempts prima di DLX
        'x-dead-letter-exchange': 'orders-dlx',
        'x-dead-letter-strategy': 'at-least-once',  # garantisce DLX delivery
    }
)
```

**x-delivery-limit (Built-in Retry con Quorum Queues):**

```
Quorum Queue con Delivery Limit

  Messaggio: delivery_count=0
  │
  ├── Consumer 1: nack(requeue=True) → delivery_count=1
  ├── Consumer 2: nack(requeue=True) → delivery_count=2
  ├── Consumer 3: nack(requeue=True) → delivery_count=3
  ├── Consumer 1: nack(requeue=True) → delivery_count=4
  ├── Consumer 2: nack(requeue=True) → delivery_count=5
  └── [delivery_count >= x-delivery-limit=5]
      → messaggio automaticamente inviato al Dead Letter Exchange
      → nessun loop infinito

  A differenza delle Classic Queues, le Quorum Queues tracciano
  nativamente il delivery_count nell'header x-delivery-count.
```

**Classic Queues vs Quorum Queues — Quando usare cosa:**

| | Classic Queue | Quorum Queue |
|---|---|---|
| **Replica** | Opzionale (mirroring, deprecato) | Sempre (Raft) |
| **Consistenza** | AP (disponibilità > consistenza) | CP (consistenza > disponibilità) |
| **Durabilità** | Opzionale | Sempre durable |
| **Performance write** | Più veloce (single node) | ~20-30% overhead per replicazione |
| **Delivery limit** | Non nativo | Nativo (x-delivery-limit) |
| **Lazy mode** | Supportato | Always lazy (messages su disco) |
| **Poison messages** | Manuale | Automatico con delivery limit |
| **Raccomandazione** | Evitare per nuove app | **Usare sempre in produzione** |

---

## Mandatory Flag e Unroutable Messages

Il flag `mandatory=True` nella pubblicazione causa un errore (return al producer) se il messaggio non può essere instradato a nessuna queue.

```python
# Setup handler per messaggi non routable
channel.add_on_return_callback(on_message_returned)

def on_message_returned(channel, method, properties, body):
    """
    Chiamato quando un messaggio mandatory non trova routing.
    method.reply_code: 312 = NO_ROUTE
    """
    print(f"Message returned: {method.reply_code} - {method.reply_text}")
    # Salva su DLQ manuale, log, alert

# Pubblicazione con mandatory
channel.basic_publish(
    exchange='orders',
    routing_key='unknown.route',    # nessun binding corrisponde
    body=b'important message',
    mandatory=True,                  # → ritornato al producer via on_return callback
    properties=pika.BasicProperties(delivery_mode=2)
)
```

!!! note "Mandatory e Confirms"
    Mandatory e Publisher Confirms sono indipendenti. Il confirm dice "il broker ha accettato il messaggio"; il mandatory dice "il messaggio è stato instradato a una queue". In produzione usarli entrambi per garanzie complete.

---

## Schema At-Least-Once End-to-End

Combinando tutti i layer, RabbitMQ offre garanzie **at-least-once** complete:

```
At-Least-Once Delivery — Configurazione Completa

  PRODUCER (side):
  ✓ Publisher Confirms abilitati
  ✓ mandatory=True
  ✓ delivery_mode=2 (persistent)
  ✓ Retry su timeout/nack con backoff esponenziale
  ✓ Idempotency key nel message_id

  BROKER:
  ✓ Queue durable=True
  ✓ x-queue-type: quorum (Raft consensus)
  ✓ Cluster con ≥3 nodi
  ✓ x-delivery-limit: N (anti-poison-message)
  ✓ Dead Letter Exchange per messaggi non processabili

  CONSUMER (side):
  ✓ auto_ack=False
  ✓ basic_qos(prefetch_count=N) appropriato
  ✓ Elaborazione idempotente (il messaggio può arrivare più volte!)
  ✓ basic_ack solo dopo completamento confermato
  ✓ basic_nack(requeue=False) per errori deterministi

  RISULTATO: Nessun messaggio viene perso.
  TRADE-OFF: Un messaggio può essere consegnato più di una volta
             (es. crash del consumer dopo elaborazione ma prima dell'ack).
             → L'idempotenza dell'elaboratore è NON NEGOZIABILE.
```

**Implementare idempotenza:**

```python
import redis
from datetime import timedelta

deduplication_store = redis.Redis(host='redis', decode_responses=True)

def idempotent_process(message_id: str, payload: dict) -> bool:
    """
    Processa il messaggio solo se non già processato.
    Usa Redis con TTL per deduplicazione sliding window.
    """
    lock_key = f"processed:{message_id}"

    # SET NX (set if not exists) — atomico
    if not deduplication_store.set(lock_key, '1', nx=True, ex=3600):
        # Già processato → skip idempotente
        logger.info(f"Duplicate message {message_id}, skipping")
        return True  # ack comunque per non rimettere in coda

    try:
        # Elaborazione effettiva
        result = process_order(payload)
        return result.success
    except Exception:
        # Rimuovi il lock per permettere retry
        deduplication_store.delete(lock_key)
        raise
```

---

## Troubleshooting

### Scenario 1 — Publisher Confirms non ricevuti / timeout

**Sintomo:** Il producer non riceve ack entro il timeout atteso; i messaggi sembrano persi o la connessione rimane in attesa indefinitamente.

**Causa:** La modalità confirm non è stata abilitata con `confirm_select()` prima di pubblicare, oppure il canale è stato chiuso prima che tutti gli ack venissero processati. In ambienti ad alto carico, i batch di confirm possono accumularsi nel buffer TCP.

**Soluzione:** Verificare che `confirm_select()` sia chiamato sul canale dopo l'apertura, e che `process_data_events()` venga invocato per scaricare la coda di eventi. In caso di timeout ricorrenti, aumentare il prefetch e usare async confirms.

```bash
# Verifica stato del canale e pending confirms tramite Management API
curl -u guest:guest http://localhost:15672/api/channels | \
  python3 -m json.tool | grep -E '"confirm"|"pending_raft_commands"'

# Log broker per errori di publish
docker logs rabbitmq 2>&1 | grep -i "confirm\|nack\|channel"
```

---

### Scenario 2 — Messaggi persi al restart del broker

**Sintomo:** Dopo un riavvio di RabbitMQ, la queue risulta vuota o contiene meno messaggi di quanti attesi.

**Causa:** Uno dei due layer di persistenza non è configurato correttamente: la queue non è `durable=True` oppure i messaggi sono pubblicati con `delivery_mode=1` (transient). Con Classic Queues, i messaggi transient vengono tenuti in RAM e non sopravvivono al restart.

**Soluzione:** Verificare entrambi i layer. Per Quorum Queues la persistenza è sempre abilitata. Per Classic Queues assicurarsi che queue e messaggi siano entrambi durable/persistent.

```bash
# Controlla la configurazione della queue via Management API
curl -u guest:guest http://localhost:15672/api/queues/%2F/orders | \
  python3 -m json.tool | grep -E '"durable"|"type"|"arguments"'

# Verifica tipo e durabilità di tutte le queues
rabbitmqctl list_queues name durable arguments type
```

---

### Scenario 3 — Requeue loop infinito (poison message)

**Sintomo:** Un consumer continua a ricevere lo stesso messaggio in loop, CPU al 100%, messaggi nella queue non decrescono mai.

**Causa:** Il consumer usa `basic_nack(requeue=True)` per un messaggio che non può essere elaborato (dati corrotti, dipendenza mancante, bug nel codice). RabbitMQ rimette il messaggio in testa alla queue, dove viene immediatamente riconsegnato.

**Soluzione:** Configurare `x-delivery-limit` sulle Quorum Queues per invio automatico al DLX dopo N tentativi. Per Classic Queues, implementare un contatore retry nell'header del messaggio e usare `requeue=False` dopo il limite.

```python
# Gestione esplicita del delivery count (Classic Queue)
def consumer_callback(ch, method, properties, body):
    headers = properties.headers or {}
    retry_count = headers.get('x-retry-count', 0)

    try:
        process(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        if retry_count >= 3:
            # Supera il limite → DLX, non rimettere in coda
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            # Republica con incremento contatore
            new_headers = {**headers, 'x-retry-count': retry_count + 1}
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            ch.basic_publish(
                exchange='',
                routing_key=method.routing_key,
                body=body,
                properties=pika.BasicProperties(headers=new_headers, delivery_mode=2)
            )
```

```bash
# Monitora messaggi in stato "unacknowledged" per identificare loop
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged
```

---

### Scenario 4 — Quorum Queue non raggiunge il quorum / queue unavailable

**Sintomo:** La queue restituisce errori `PRECONDITION_FAILED` o i publish bloccano; nella Management UI la queue appare in stato `stopped` o `minority`.

**Causa:** Il cluster ha perso la maggioranza dei nodi che ospitano la quorum queue (es. 2 nodi su 3 sono down). Raft non può eleggere un leader senza il quorum, quindi la queue è temporaneamente indisponibile.

**Soluzione:** Riportare online abbastanza nodi per ristabilire il quorum. Non forzare mai la rimozione di nodi che contengono dati committed senza un piano di recovery controllato.

```bash
# Stato del cluster e dei nodi
rabbitmqctl cluster_status

# Stato specifico delle quorum queues
rabbitmq-diagnostics quorum_status <queue_name> -p <vhost>

# Elenco dei membri e leader di ogni quorum queue
rabbitmqctl list_quorum_queue_statuses

# Se un nodo è temporaneamente offline e va rimosso (ATTENZIONE: dati potenzialmente persi)
rabbitmqctl forget_cluster_node rabbit@node2
```

---

## Riferimenti

- [RabbitMQ Reliability Guide](https://www.rabbitmq.com/docs/reliability)
- [Publisher Confirms](https://www.rabbitmq.com/docs/confirms)
- [Consumer Acknowledgements](https://www.rabbitmq.com/docs/confirms#consumer-acknowledgements)
- [Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues)
- [Classic vs Quorum Queue Feature Comparison](https://www.rabbitmq.com/docs/queues#optional-arguments)
