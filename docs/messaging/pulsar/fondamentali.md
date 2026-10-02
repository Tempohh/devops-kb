---
title: "Apache Pulsar — Fondamentali"
slug: fondamentali
category: messaging
tags: [pulsar, messaging, event-streaming, pub-sub, multi-tenancy, bookkeeper]
search_keywords: [apache pulsar, pulsar broker, bookkeeper, bookie, pulsar vs kafka, pulsar vs rabbitmq, tiered storage, pulsar functions, pulsar tenant namespace topic, subscription model pulsar, key_shared subscription, geo-replication pulsar, pulsar-admin, pulsar client python, pulsar client java, segmented log storage, compute storage separation, multi-tenant messaging, pulsar io connectors]
parent: messaging/_index
related: [messaging/kafka/_index, messaging/rabbitmq/_index, messaging/rabbitmq/vs-kafka]
official_docs: https://pulsar.apache.org/docs/
status: complete
difficulty: advanced
last_updated: 2026-10-02
---

# Apache Pulsar — Fondamentali

## Panoramica

Apache Pulsar è un message broker distribuito nato in LinkedIn (2012) e diventato progetto Apache top-level nel 2018. La sua caratteristica distintiva è la **separazione netta tra compute e storage**: i broker che gestiscono il traffico dei client non conservano dati su disco — lo storage è delegato a un livello separato (Apache BookKeeper). Questo è diverso sia da Kafka (dove ogni broker possiede e serve i propri segmenti di log su disco locale) sia da RabbitMQ (dove il broker gestisce code in memoria/disco e routing).

Pulsar nasce per risolvere problemi che Kafka risolve solo parzialmente: multi-tenancy nativa su larga scala (migliaia di tenant/namespace su un cluster condiviso), elasticità dei broker senza rebalance di dati (perché i broker non possiedono dati), e retention a lungo termine economica tramite tiered storage automatico. Si usa quando serve una piattaforma di streaming condivisa tra molti team/clienti con isolamento forte, quando i pattern di subscription vanno oltre il semplice consumer group, o quando la storia completa dello stream deve restare accessibile senza far lievitare i costi del disco locale.

Non è la scelta giusta quando il team ha già investito pesantemente nell'ecosistema Kafka (Kafka Streams, ksqlDB, Kafka Connect hanno equivalenti Pulsar ma meno maturi/diffusi), quando serve il throughput puro massimo su singola partizione con footprint operativo minimo, o quando la complessità aggiuntiva di gestire due sistemi distribuiti (broker + BookKeeper) non è giustificata dal caso d'uso.

---

## Concetti Chiave

!!! note "Compute/Storage Separation"
    I **broker Pulsar sono stateless**: non conservano dati, solo metadata di routing in cache. Lo storage persistente dei messaggi vive nei **bookie** (nodi BookKeeper), organizzato in **ledger** segmentati. Un broker può essere riavviato, sostituito o scalato senza alcun movimento di dati — il traffico viene semplicemente ridiretto a un altro broker che legge dagli stessi bookie.

- **Broker**: gestisce connessioni client, autenticazione, routing dei topic, dispatch dei messaggi. Nessun dato persistente a riposo.
- **Bookie (BookKeeper)**: nodo di storage che mantiene i **ledger** — segmenti di log append-only, replicati su più bookie (default: write quorum 2, ack quorum 2, ensemble 3).
- **Metadata store**: ZooKeeper (storicamente) o il più recente store basato su RocksDB (Pulsar Metadata Store standalone da Pulsar 2.9+) per coordinamento cluster, configurazione, ownership dei topic.
- **Topic**: unità di pub/sub, può essere **persistent** (scritto su BookKeeper) o **non-persistent** (solo in memoria, a vita del broker — usato per casi latenza-critica dove la perdita di messaggi in caso di crash è accettabile).
- **Partitioned topic**: un topic logico diviso in N sotto-topic (partizioni), ciascuna con il proprio ledger su BookKeeper — analogo concettuale alle partizioni Kafka, ma ogni partizione è a sua volta backed da segmenti distribuiti su bookie diversi, non da un singolo file su un singolo broker.
- **Subscription**: il meccanismo con cui i consumer si collegano a un topic; a differenza di Kafka (solo consumer group) Pulsar offre 4 tipi di subscription (vedi sotto) selezionabili per singolo consumer sullo stesso topic.

---

## Architettura / Come Funziona

```
Apache Pulsar — Architettura a 3 Livelli

  ┌─────────────────────────────────────────────────────┐
  │                     CLIENT LAYER                     │
  │   Producer          Consumer         pulsar-admin    │
  └──────────┬──────────────┬──────────────────┬─────────┘
             │              │                  │
  ┌──────────▼──────────────▼──────────────────▼─────────┐
  │                   BROKER LAYER (stateless)            │
  │   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
  │   │ Broker 1 │   │ Broker 2 │   │ Broker 3 │         │
  │   │ (topic   │   │ (topic   │   │ (topic   │         │
  │   │  owner)  │   │  owner)  │   │  owner)  │         │
  │   └────┬─────┘   └────┬─────┘   └────┬─────┘         │
  └────────┼──────────────┼──────────────┼────────────────┘
           │              │              │
  ┌────────▼──────────────▼──────────────▼────────────────┐
  │              BOOKKEEPER LAYER (storage)                │
  │   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
  │   │ Bookie 1│   │ Bookie 2│   │ Bookie 3│             │
  │   │ ledgers │   │ ledgers │   │ ledgers │             │
  │   └─────────┘   └─────────┘   └─────────┘             │
  └──────────────────────────────────────────────────────┘
           │
  ┌────────▼────────────────────────────────────────────┐
  │   METADATA STORE (ZooKeeper o Pulsar Metadata Store)  │
  │   coordinamento cluster, ownership, configurazione    │
  └────────────────────────────────────────────────────────┘

  Differenza chiave vs Kafka:
  Kafka    → Broker = compute + storage (stesso processo, stesso disco)
  Pulsar   → Broker = compute, Bookie = storage (processi/host separati,
             scalabili indipendentemente)
```

**Implicazione operativa della separazione:** in Kafka, aggiungere capacità di storage significa aggiungere broker e ribilanciare partizioni (operazione costosa in I/O e rete). In Pulsar, si possono aggiungere bookie per più storage senza toccare i broker, o aggiungere broker per più throughput di connessioni senza spostare un singolo byte di dati — l'ownership dei topic viene semplicemente riassegnata a livello di metadata.

### Topic: Persistent vs Non-Persistent

```
Persistent topic (default, produzione):
  Producer → Broker → scrittura su ledger BookKeeper (ack dopo quorum)
  Sopravvive a crash broker e restart cluster.

Non-persistent topic (prefisso "non-persistent://"):
  Producer → Broker → dispatch diretto in memoria ai consumer connessi
  Nessuna scrittura su disco. Se il broker crasha, i messaggi in transito
  sono persi. Usato per: metriche ad altissimo volume, telemetria dove
  un data point perso è accettabile, casi latenza-critica estrema.
```

### Subscription Model — 4 Modalità sullo Stesso Topic

```
1. EXCLUSIVE — un solo consumer può collegarsi alla subscription.
   Un secondo tentativo di connessione viene rifiutato.
   Uso: ordinamento stretto garantito, singolo processore.

2. FAILOVER — più consumer, uno attivo (master) e gli altri standby.
   Se il master cade, uno standby prende il controllo automaticamente.
   Uso: HA con ordinamento preservato, zero downtime su crash.

3. SHARED (round-robin) — più consumer, messaggi distribuiti round-robin
   tra tutti. Nessuna garanzia di ordinamento.
   Uso: worker pool, task processing ad alto parallelismo (come le
   competing consumers di RabbitMQ).

4. KEY_SHARED — più consumer, messaggi con la stessa chiave (key) vanno
   sempre allo stesso consumer; chiavi diverse si distribuiscono tra i
   consumer disponibili.
   Uso: parallelismo con ordinamento per entità (es. tutti gli eventi
   di un customer_id allo stesso consumer) — equivalente concettuale al
   partitioning per-key di Kafka, ma senza dover pre-dimensionare il
   numero di partizioni: la distribuzione è dinamica tra i consumer attivi.
```

!!! tip "Perché Key_Shared batte le partizioni fisse"
    Con Kafka, l'ordinamento per chiave richiede partizioni fisse: se sotto-dimensioni il topic, non puoi aggiungere parallelismo senza un repartitioning costoso. Con `Key_Shared` su Pulsar, aggiungere un consumer aumenta subito il parallelismo — la redistribuzione delle chiavi tra consumer è gestita dal broker in automatico, senza downtime né migrazione di dati.

Più subscription type possono coesistere **sullo stesso topic simultaneamente** — un topic può avere una subscription `Exclusive` per l'audit log e una `Shared` per il worker pool, senza duplicare il topic o il dato.

---

## Multi-Tenancy Nativa

```
Gerarchia Pulsar — Tenant → Namespace → Topic

  Cluster Pulsar
  ├── Tenant: "team-payments"
  │   ├── Namespace: "team-payments/production"
  │   │   ├── Topic: persistent://team-payments/production/orders
  │   │   └── Topic: persistent://team-payments/production/refunds
  │   └── Namespace: "team-payments/staging"
  │       └── Topic: persistent://team-payments/staging/orders
  │
  ├── Tenant: "team-analytics"
  │   └── Namespace: "team-analytics/events"
  │       └── Topic: persistent://team-analytics/events/clickstream
  │
  └── Tenant: "cliente-acme-corp"            ← caso multi-cliente SaaS
      └── Namespace: "cliente-acme-corp/prod"
          └── Topic: persistent://cliente-acme-corp/prod/webhooks

  Policy applicabili per namespace: quota storage, retention, TTL,
  rate limit producer/consumer, geo-replication, autenticazione/ACL.
```

**Caso d'uso tipico**: una piattaforma che serve decine o centinaia di team interni, o un vendor SaaS multi-cliente, può eseguire **un solo cluster Pulsar** condiviso invece di provisionare cluster Kafka separati per isolamento. Ogni tenant ha quota, retention e permessi indipendenti, amministrabili via `pulsar-admin` senza toccare la configurazione degli altri tenant. Con Kafka, l'isolamento equivalente richiede ACL su topic con naming convention disciplinata, oppure cluster fisicamente separati (costo operativo moltiplicato).

```bash
# Creare tenant, namespace, topic con pulsar-admin
pulsar-admin tenants create team-payments \
  --admin-roles payments-admin \
  --allowed-clusters cluster-eu

pulsar-admin namespaces create team-payments/production

# Policy sul namespace: retention 7 giorni, TTL messaggi 24h
pulsar-admin namespaces set-retention team-payments/production \
  --size -1 --time 7d

pulsar-admin namespaces set-message-ttl team-payments/production \
  --messageTTL 86400

# Quota storage per namespace (backpressure quando superata)
pulsar-admin namespaces set-backlog-quota team-payments/production \
  --limit 10G --policy producer_exception

# Creare un partitioned topic con 6 partizioni
pulsar-admin topics create-partitioned-topic \
  persistent://team-payments/production/orders --partitions 6
```

---

## Tiered Storage

```
Tiered Storage — Offload Automatico su Object Storage

  BookKeeper (hot storage, SSD/NVMe)
  ┌─────────────────────────────────┐
  │ Ledger recenti (ultimi N giorni) │ ← letture/scritture frequenti
  └───────────────┬───────────────────┘
                  │ offload automatico (policy-based)
                  ▼
  Object Storage (cold storage, S3/GCS/Azure Blob)
  ┌─────────────────────────────────┐
  │ Ledger più vecchi (storia lunga)  │ ← letture occasionali, costo
  └─────────────────────────────────┘    storage molto più basso

  Il topic rimane interrogabile in modo trasparente: un consumer che
  fa seek su un offset "freddo" legge automaticamente da S3, senza
  differenze nell'API client.
```

Questo risolve un trade-off reale di Kafka: retention lunga (mesi/anni) su Kafka significa disco locale costoso che scala con il volume totale storico, oppure l'adozione di Kafka tiered storage (disponibile solo in distribuzioni enterprise recenti come Confluent o versioni Apache Kafka 3.9+/KIP-405). Pulsar ha il tiered storage come feature nativa dalla versione 2.4, configurabile per namespace.

```bash
# Configurare offload su S3 per un namespace
pulsar-admin namespaces set-offload-threshold team-payments/production \
  --size 10G   # offload i ledger quando il backlog supera 10GB

pulsar-admin namespaces set-offload-policies team-payments/production \
  --driver aws-s3 \
  --region eu-west-1 \
  --bucket pulsar-tiered-storage \
  --maxBlockSizeInBytes 67108864
```

!!! warning "Costo delle letture da tiered storage"
    Leggere dati offload su S3/GCS ha latenza molto più alta (centinaia di ms vs sub-ms da BookKeeper) e costi di egress/richieste object storage. Il tiered storage è pensato per accesso occasionale (replay storico, audit, compliance), non per workload che leggono costantemente dati vecchi — in quel caso la retention va aumentata su BookKeeper direttamente.

---

## Pulsar Functions

**Pulsar Functions** è il motore di stream processing lightweight integrato nel broker: funzioni scritte in Java/Python/Go che leggono da uno o più topic di input e scrivono su topic di output, eseguite senza un cluster di stream processing separato (a differenza di Kafka Streams, che gira nell'applicazione client, o Flink/Spark Streaming, cluster esterni dedicati).

```python
# Esempio: Pulsar Function in Python — enrichment semplice
from pulsar import Function

class EnrichOrderFunction(Function):
    def process(self, input_bytes, context):
        import json
        order = json.loads(input_bytes)
        order['enriched_at'] = context.get_current_message_properties()
        order['processed_by'] = context.get_function_name()

        # Routing condizionale: pubblica su topic diverso se alto valore
        if order.get('amount', 0) > 10000:
            context.publish('persistent://team-payments/production/high-value',
                             json.dumps(order).encode())
            return None  # non pubblicare anche sull'output di default

        return json.dumps(order).encode()
```

```bash
# Deploy della function sul cluster
pulsar-admin functions create \
  --tenant team-payments \
  --namespace production \
  --name enrich-order \
  --py enrich_order.py \
  --classname enrich_order.EnrichOrderFunction \
  --inputs persistent://team-payments/production/orders-raw \
  --output persistent://team-payments/production/orders-enriched \
  --parallelism 3
```

**Confronto con l'ecosistema stream processing Kafka:**

| | Pulsar Functions | Kafka Streams | ksqlDB |
|---|---|---|---|
| **Dove gira** | Dentro il cluster broker (o worker dedicati) | Libreria embedded nell'app client | Cluster ksqlDB separato |
| **Linguaggi** | Java, Python, Go | JVM (Java/Scala/Kotlin) | SQL dichiarativo |
| **Deploy** | `pulsar-admin functions create` | Deploy dell'applicazione come un normale servizio | Query SQL su cluster ksqlDB |
| **Scaling** | `--parallelism N`, gestito dal cluster | Scaling dell'applicazione (orizzontale via partizioni) | Scaling del cluster ksqlDB |
| **Maturità** | Più recente, ecosistema più piccolo | Molto maturo, ampia adozione produzione | Maturo, ma seconda scelta vs Flink per casi complessi |

Per pipeline di stream processing complesse (join multi-stream, windowing avanzato, stato distribuito) sia Pulsar che Kafka in produzione spesso delegano a **Apache Flink**, che integra nativamente connector per entrambi.

---

## Esempio Pratico — Setup Completo

```bash
# 1. Creare tenant e namespace
pulsar-admin tenants create ecommerce --allowed-clusters standalone
pulsar-admin namespaces create ecommerce/orders

# 2. Creare un partitioned topic (6 partizioni)
pulsar-admin topics create-partitioned-topic \
  persistent://ecommerce/orders/order-events --partitions 6

# 3. Verificare stato topic
pulsar-admin topics stats persistent://ecommerce/orders/order-events
pulsar-admin topics partitioned-stats persistent://ecommerce/orders/order-events
```

```python
# Producer Python — pubblica con chiave per Key_Shared
import pulsar

client = pulsar.Client('pulsar://localhost:6650')
producer = client.create_producer(
    'persistent://ecommerce/orders/order-events',
    send_timeout_millis=30000
)

producer.send(
    content=b'{"order_id": "ORD-1001", "customer_id": "CUST-42", "amount": 150.0}',
    partition_key='CUST-42'   # chiave di partizionamento logico
)

client.close()
```

```python
# Consumer Python — subscription Key_Shared per parallelismo con ordering per cliente
import pulsar

client = pulsar.Client('pulsar://localhost:6650')
consumer = client.subscribe(
    'persistent://ecommerce/orders/order-events',
    subscription_name='order-processor',
    consumer_type=pulsar.ConsumerType.KeyShared
)

while True:
    msg = consumer.receive()
    try:
        print(f"Processing: {msg.data()}")
        consumer.acknowledge(msg)
    except Exception:
        consumer.negative_acknowledge(msg)  # redelivery dopo backoff

client.close()
```

```java
// Producer Java — equivalente minimale
PulsarClient client = PulsarClient.builder()
    .serviceUrl("pulsar://localhost:6650")
    .build();

Producer<byte[]> producer = client.newProducer()
    .topic("persistent://ecommerce/orders/order-events")
    .create();

producer.newMessage()
    .key("CUST-42")
    .value("{\"order_id\":\"ORD-1001\"}".getBytes())
    .send();

producer.close();
client.close();
```

---

## Tabella Comparativa — Kafka vs Pulsar vs RabbitMQ

| Dimensione | Kafka | Pulsar | RabbitMQ |
|------------|-------|--------|----------|
| **Modello storage** | Broker = compute+storage | Broker/Bookie separati (compute/storage) | Broker in-memory/disco, no log persistente |
| **Throughput** | Molto alto (~1M+ msg/s/broker) | Alto, comparabile a Kafka con più overhead di rete (broker↔bookie) | Moderato (~100K msg/s/nodo) |
| **Multi-tenancy** | Via ACL/naming convention, manuale | Nativa (tenant→namespace→topic con policy dedicate) | Via virtual host, meno granulare su quota/retention |
| **Subscription model** | Solo consumer group (pull, offset per gruppo) | 4 modalità: Exclusive, Failover, Shared, Key_Shared | Competing consumers, routing via exchange |
| **Replay/retention lunga** | Sì, ma disco locale costoso salvo tiered storage enterprise | Sì, tiered storage nativo su object storage | No (salvo RabbitMQ Streams) |
| **Scaling storage** | Richiede rebalance partizioni tra broker | Aggiungere bookie, zero rebalance broker | Scaling verticale + federation |
| **Routing nel broker** | No (filtro lato consumer) | No (filtro lato consumer, o Pulsar Functions) | Sì (exchange: direct/topic/fanout/headers) |
| **Stream processing integrato** | Kafka Streams, ksqlDB (ecosistema maturo) | Pulsar Functions (più leggero, meno maturo) | Nessuno nativo |
| **Complessità operativa** | Alta (ZooKeeper/KRaft, ISR, rebalance) | Più alta (broker + BookKeeper + metadata store: 3 sistemi) | Bassa-media (singolo sistema Erlang) |
| **Ecosistema** | Vastissimo, standard de facto industry | Crescente ma più piccolo, forte in Asia/telco | Maturo, multi-protocollo (AMQP/MQTT/STOMP) |
| **Quando scegliere** | Standard default per event streaming ad alto volume | Piattaforma multi-tenant condivisa, retention lunga economica, subscription flessibili | Routing complesso, task queue, RPC, ambienti eterogenei |

---

## Best Practices

- **Dimensionare l'ensemble BookKeeper correttamente**: write quorum e ack quorum devono essere `< ensemble size` per tollerare la perdita di un bookie senza bloccare le scritture; produzione tipica: ensemble 3, write quorum 2, ack quorum 2.
- **Usare `Key_Shared` invece di partizioni fisse quando il parallelismo deve crescere senza repartitioning** — evita il problema classico Kafka di dover sovradimensionare le partizioni in anticipo.
- **Separare i namespace per ambiente (prod/staging) e per team**, non solo per topic — le policy di retention/quota si applicano a livello namespace, non topic singolo.
- **Abilitare il tiered storage solo su namespace con pattern di accesso "write-once, read-raramente"** — per workload che leggono costantemente la storia recente, tenere i dati su BookKeeper.
- **Monitorare il backlog per subscription**, non solo il lag del topic: con 4 subscription type coesistenti, un consumer lento su una subscription `Exclusive` non blocca le altre, ma consuma comunque storage fino al consumo.

!!! warning "Non sotto-dimensionare i bookie"
    I bookie sono il collo di bottiglia I/O del cluster. Sottodimensionarli (storage lento, pochi nodi) degrada tutte le operazioni di scrittura su tutti i topic del cluster, indipendentemente da quanti broker si aggiungono — i broker senza bookie sufficienti non risolvono un problema di storage.

---

## Troubleshooting

### Scenario 1 — Bookie under-replication

**Sintomo:** Comando `pulsar-admin bookies` o metriche mostrano ledger con fattore di replica inferiore a quello configurato (`write quorum`). Rischio di perdita dati se un ulteriore bookie cade.

**Causa:** Un bookie è stato marcato down (crash, manutenzione, problema di rete) e BookKeeper non ha ancora completato la re-replicazione dei suoi ledger sugli altri bookie disponibili — oppure l'auto-recovery è disabilitato.

**Soluzione:**

```bash
# Verificare bookie under-replicati
bin/bookkeeper shell listunderreplicated

# Verificare che l'auto-recovery sia attivo (deve girare come demone)
bin/bookkeeper autorecovery -c conf/bookkeeper.conf

# Forzare la re-replicazione manuale se l'auto-recovery è fermo
bin/bookkeeper shell triggeraudit

# Verificare lo stato generale del cluster BookKeeper
bin/bookkeeper shell bookiesanity
```

---

### Scenario 2 — Backlog quota exceeded

**Sintomo:** I producer ricevono errori `TopicTerminatedException` o `ProducerBlockedQuotaExceededException`; i publish falliscono o vengono bloccati.

**Causa:** Il backlog (messaggi non ancora consumati/acked da tutte le subscription) ha superato la quota configurata sul namespace, e la policy è `producer_exception` o `producer_request_hold`.

**Soluzione:**

```bash
# Verificare la quota configurata e il backlog attuale
pulsar-admin namespaces get-backlog-quotas ecommerce/orders
pulsar-admin topics stats persistent://ecommerce/orders/order-events \
  | grep -A5 "backlogSize"

# Opzione 1: aumentare la quota se il volume è legittimo
pulsar-admin namespaces set-backlog-quota ecommerce/orders \
  --limit 50G --policy producer_exception

# Opzione 2: identificare e sbloccare subscription inattive che accumulano backlog
pulsar-admin topics subscriptions persistent://ecommerce/orders/order-events
pulsar-admin topics unsubscribe persistent://ecommerce/orders/order-events \
  -s subscription-abbandonata

# Opzione 3: cambiare policy a "producer_request_hold" per backpressure
# graduale invece di eccezioni immediate
pulsar-admin namespaces set-backlog-quota ecommerce/orders \
  --limit 50G --policy producer_request_hold
```

---

### Scenario 3 — Topic non trovato / ownership lookup fallito

**Sintomo:** Client riceve `Failed to get topic lookup result` o timeout alla connessione, pur sapendo che il topic esiste.

**Causa:** Il broker che possedeva il topic è crashato e il metadata store non ha ancora ricompletato la riassegnazione dell'ownership a un altro broker, oppure c'è un problema di connettività verso il metadata store (ZooKeeper/Pulsar Metadata Store).

**Soluzione:**

```bash
# Verificare lo stato del metadata store
pulsar-admin clusters list
pulsar-admin brokers list standalone

# Verificare l'owner attuale del topic
pulsar-admin topics lookup persistent://ecommerce/orders/order-events

# Forzare unload e reload del topic (riassegna l'ownership)
pulsar-admin topics unload persistent://ecommerce/orders/order-events
```

---

### Scenario 4 — Consumer riceve messaggi duplicati dopo redelivery

**Sintomo:** Lo stesso messaggio arriva più volte allo stesso consumer group/subscription.

**Causa:** Il consumer ha chiamato `negative_acknowledge` o non ha fatto `acknowledge` entro l'`ackTimeout` configurato — Pulsar reinvia il messaggio per redelivery, come comportamento at-least-once standard.

**Soluzione:** Implementare idempotenza lato consumer (come per Kafka/RabbitMQ) e dimensionare correttamente l'ack timeout.

```python
consumer = client.subscribe(
    'persistent://ecommerce/orders/order-events',
    subscription_name='order-processor',
    consumer_type=pulsar.ConsumerType.Shared,
    unacked_messages_timeout_ms=60000  # ack timeout: 60s, non troppo corto
)

# Deduplicazione lato applicativo con message_id
processed = set()
msg = consumer.receive()
msg_id = str(msg.message_id())
if msg_id not in processed:
    processed.add(msg_id)
    # elabora
consumer.acknowledge(msg)
```

---

## Relazioni

??? info "RabbitMQ vs Kafka — Approfondimento"
    Pulsar si posiziona concettualmente tra i due modelli: come Kafka è un log persistente con subscription indipendenti, come RabbitMQ offre subscription type ricche (incluso un routing-like behaviour con Key_Shared). Per il confronto filosofico smart-broker/dumb-broker che chiarisce dove Pulsar si inserisce.

    **Approfondimento completo →** [RabbitMQ vs Kafka](../rabbitmq/vs-kafka.md)

??? info "Apache Kafka — Fondamentali"
    Il punto di riferimento architetturale più vicino: stesso modello di log distribuito, ma con broker che possiedono storage locale invece della separazione compute/storage di Pulsar.

    **Approfondimento completo →** [Kafka](../kafka/_index.md)

??? info "RabbitMQ — Fondamentali"
    Utile per confrontare il modello smart-broker (routing nel broker) con l'approccio Pulsar, dove il routing resta lato consumer/subscription.

    **Approfondimento completo →** [RabbitMQ](../rabbitmq/_index.md)

---

## Riferimenti

- [Apache Pulsar — Documentazione ufficiale](https://pulsar.apache.org/docs/)
- [Pulsar Concepts and Architecture](https://pulsar.apache.org/docs/concepts-architecture-overview/)
- [Apache BookKeeper — Documentazione](https://bookkeeper.apache.org/docs/overview/)
- [Pulsar Functions](https://pulsar.apache.org/docs/functions-overview/)
- [Tiered Storage](https://pulsar.apache.org/docs/tiered-storage-overview/)
- [Pulsar vs Kafka — StreamNative](https://streamnative.io/blog/pulsar-vs-kafka)
