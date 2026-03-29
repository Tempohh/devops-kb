---
title: "Exactly-Once Semantics (EOS)"
slug: exactly-once-semantics
category: messaging
tags: [kafka, exactly-once, eos, idempotenza, semantics, delivery-guarantee]
search_keywords: [kafka exactly once, exactly once semantics kafka, kafka idempotent producer, kafka eos, at least once at most once kafka, delivery guarantee kafka, kafka processing guarantee, transaction coordinator kafka, kafka transactional id, zombie fencing kafka, kafka read committed, exactly once processing stream, KIP-98, EXACTLY_ONCE_V2, idempotent consumer kafka]
parent: messaging/kafka/sviluppo
related: [messaging/kafka/sviluppo/transazioni, messaging/kafka/fondamenti/produttori]
official_docs: https://kafka.apache.org/documentation/#semantics
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Exactly-Once Semantics (EOS)

## Panoramica

Kafka supporta tre garanzie di delivery: **at-most-once** (possibile perdita dati), **at-least-once** (possibili duplicati) e **exactly-once** (nessuna perdita, nessun duplicato). EOS è la garanzia più forte e la più complessa da implementare. In Kafka, si articola in due livelli distinti: **producer idempotente** (EOS sul singolo topic/partizione) e **transazioni Kafka** (EOS end-to-end su più topic).

**Quando usarlo:** Sistemi finanziari (pagamenti, billing), audit log, qualsiasi scenario dove duplicati o perdita di record hanno impatto concreto.

**Quando NON usarlo:** Sistemi ad alto throughput dove la latenza aggiuntiva è inaccettabile, metriche e log dove qualche perdita o duplicato è tollerabile.

## Concetti Chiave

### Le tre garanzie di delivery

| Garanzia | Perdita dati | Duplicati | Come si ottiene |
|----------|-------------|-----------|-----------------|
| **At-most-once** | Possibile | No | acks=0, no retry |
| **At-least-once** | No | Possibili | acks=all + retry |
| **Exactly-once** | No | No | Idempotenza + transazioni |

### Producer Idempotente

Il producer idempotente garantisce che ogni record venga scritto **esattamente una volta** su una partizione, anche in presenza di retry. Meccanismo:
- Il producer riceve un **Producer ID (PID)** univoco dal broker alla prima connessione
- Ogni record riceve un **sequence number** incrementale per partizione
- Se il broker riceve un record con un sequence number già visto → scarta il duplicato
- Se il sequence number è troppo alto (record perso) → errore

```
Producer (PID=42)  →  Record [PID=42, seq=1]  →  Broker (scrive offset 100)
                   →  Record [PID=42, seq=1]  →  Broker (DUPLICATO → scarta, ritorna OK)
                   →  Record [PID=42, seq=2]  →  Broker (scrive offset 101)
```

### Transazioni Kafka (EOS end-to-end)

Le transazioni permettono di scrivere su **più topic/partizioni in modo atomico**: o tutti i record vengono scritti, o nessuno. Essenziale per il pattern **consume-transform-produce** (leggo da A, processo, scrivo su B — deve essere atomico).

- **Transaction Coordinator** — Broker speciale che gestisce il ciclo di vita delle transazioni
- **Transaction Log** — Topic interno `__transaction_state` dove vengono registrate le transazioni
- **Transaction Marker** — Record speciale (COMMIT o ABORT) scritto al termine di ogni transazione
- **Isolation Level** — I consumer devono usare `isolation.level=read_committed` per non vedere record di transazioni in corso o abortite

## Come Funziona

```mermaid
sequenceDiagram
    participant P as Producer
    participant TC as Transaction Coordinator
    participant B1 as Broker (topic-A)
    participant B2 as Broker (topic-B)
    participant C as Consumer (read_committed)

    P->>TC: initTransactions()
    P->>TC: beginTransaction()
    P->>B1: send(topic-A, record1)
    P->>B2: send(topic-B, record2)
    P->>TC: sendOffsetsToTransaction(groupId, offsets)
    TC-->>TC: Registra offset nel transaction log
    P->>TC: commitTransaction()
    TC->>B1: Write COMMIT marker
    TC->>B2: Write COMMIT marker
    B1-->>C: record1 ora visibile
    B2-->>C: record2 ora visibile
```

## Configurazione & Pratica

### Producer Idempotente

```java
Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);

// ── EOS: Producer Idempotente ─────────────────────────────────────────────
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);   // abilita idempotenza
// Implica automaticamente:
// acks=all
// max.in.flight.requests.per.connection <= 5
// retries = Integer.MAX_VALUE

// Opzionale ma raccomandato
props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");

KafkaProducer<String, String> producer = new KafkaProducer<>(props);
```

### Producer Transazionale (EOS end-to-end)

```java
Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);

// ── EOS: Transazioni ─────────────────────────────────────────────────────
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-processor-1");
// transactional.id DEVE essere univoco per istanza del producer e stabile tra restart
// Esempio: "order-processor-{pod-name}" in Kubernetes

props.put(ProducerConfig.TRANSACTION_TIMEOUT_CONFIG, 60000);  // 60 secondi

KafkaProducer<String, String> producer = new KafkaProducer<>(props);

// Inizializzare le transazioni una volta sola all'avvio
producer.initTransactions();
```

### Pattern Consume-Transform-Produce con EOS

```java
KafkaConsumer<String, String> consumer = createConsumer();
KafkaProducer<String, String> producer = createTransactionalProducer();
producer.initTransactions();

consumer.subscribe(List.of("input-orders"));

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(500));
    if (records.isEmpty()) continue;

    producer.beginTransaction();
    try {
        // ── 1. Processare e produrre output ───────────────────────────────
        for (ConsumerRecord<String, String> record : records) {
            String processed = transform(record.value());
            producer.send(new ProducerRecord<>("processed-orders", record.key(), processed));
        }

        // ── 2. Committare gli offset come parte della transazione ─────────
        // Questo garantisce che gli offset siano committati atomicamente con i record prodotti
        Map<TopicPartition, OffsetAndMetadata> offsets = new HashMap<>();
        for (TopicPartition partition : records.partitions()) {
            List<ConsumerRecord<String, String>> partitionRecords = records.records(partition);
            long lastOffset = partitionRecords.get(partitionRecords.size() - 1).offset();
            offsets.put(partition, new OffsetAndMetadata(lastOffset + 1));
        }
        producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata());

        // ── 3. Commit atomico ─────────────────────────────────────────────
        producer.commitTransaction();

    } catch (Exception e) {
        producer.abortTransaction();
        // Il consumer verrà ribilanciato o rilascerà gli offset
        throw e;
    }
}
```

### Consumer con read_committed

```java
Properties consumerProps = new Properties();
consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "my-consumer-group");
consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);

// ── Essenziale per EOS ────────────────────────────────────────────────────
consumerProps.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
// read_committed: vede solo record di transazioni committate
// read_uncommitted (default): vede tutti i record, inclusi quelli di transazioni in corso/abortite
```

### Kafka Streams EOS

```java
Properties streamsProps = new Properties();
streamsProps.put(StreamsConfig.APPLICATION_ID_CONFIG, "my-streams-app");
streamsProps.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");

// ── EOS in Kafka Streams ──────────────────────────────────────────────────
streamsProps.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG,
    StreamsConfig.EXACTLY_ONCE_V2);  // raccomandato (Kafka 2.6+)
    // Alternativa legacy: StreamsConfig.EXACTLY_ONCE_BETA
```

## Best Practices

!!! tip "Usare transactional.id stabile e unico per istanza"
    Il `transactional.id` deve essere lo stesso tra i restart del producer (così Kafka può fare zombie fencing) ma **diverso** per ogni istanza parallela del producer (per evitare conflitti di fencing).

!!! warning "EOS ha un overhead di latenza"
    Le transazioni aggiungono latenza (commit del transaction coordinator + marker nei topic). In sistemi ad alto throughput, valutare se EOS è necessario o se at-least-once + idempotenza lato consumer è sufficiente.

!!! warning "Non mischiare consumer read_committed e read_uncommitted"
    In un sistema EOS, tutti i consumer del topic devono usare `read_committed`, altrimenti alcuni consumer vedranno record di transazioni abortite.

!!! tip "Zombie fencing"
    Se un producer con lo stesso `transactional.id` di un producer "zombie" (es. pod riavviato lentamente) tenta di usare lo stesso ID, Kafka scarta il producer vecchio tramite l'**epoch** delle transazioni. Questo è automatico ma richiede `transactional.id` stabile.

## Troubleshooting

### Scenario 1 — ProducerFencedException al riavvio del producer

**Sintomo:** Il producer lancia `ProducerFencedException` all'avvio o durante `initTransactions()`.

**Causa:** Esiste già un producer attivo con lo stesso `transactional.id`. Kafka utilizza l'epoch per fare zombie fencing: quando un nuovo producer si registra con lo stesso ID, l'epoch viene incrementato e il vecchio producer viene invalidato. Se il vecchio producer è ancora attivo o non ha completato la pulizia, si genera il conflitto.

**Soluzione:** Assicurarsi che `transactional.id` sia unico per istanza (es. includere il nome del pod Kubernetes). Se il pod si è riavviato rapidamente, attendere la scadenza del timeout della transazione precedente.

```bash
# Verificare le transazioni attive sul broker
kafka-transactions.sh --bootstrap-server kafka:9092 describe \
  --transactional-id order-processor-1

# Verificare il transaction timeout configurato
kafka-configs.sh --bootstrap-server kafka:9092 --describe \
  --entity-type brokers --entity-name 1 | grep transaction.max.timeout.ms
```

### Scenario 2 — InvalidTxnStateException durante send o commit

**Sintomo:** `InvalidTxnStateException` con messaggio "Invalid transition attempted from state X to state Y".

**Causa:** Il producer ha chiamato operazioni fuori dal ciclo di vita corretto della transazione. Ad esempio: `send()` prima di `beginTransaction()`, `commitTransaction()` dopo un'eccezione senza `abortTransaction()`, o `beginTransaction()` senza aver chiamato `initTransactions()` all'avvio.

**Soluzione:** Verificare che il flusso rispetti sempre: `initTransactions()` → `beginTransaction()` → `send()`/`sendOffsetsToTransaction()` → `commitTransaction()` oppure `abortTransaction()` in caso di errore.

```java
// Pattern corretto con gestione errori
producer.initTransactions();  // una sola volta all'avvio
while (true) {
    producer.beginTransaction();
    try {
        // operazioni...
        producer.commitTransaction();
    } catch (Exception e) {
        producer.abortTransaction();  // SEMPRE in caso di errore
        // poi gestire il consumer (seek, rethrow, ecc.)
    }
}
```

### Scenario 3 — Consumer vede record duplicati con read_committed

**Sintomo:** Il consumer con `isolation.level=read_committed` riceve comunque record duplicati o record di transazioni abortite.

**Causa:** Il producer non sta usando correttamente le transazioni: manca `transactional.id`, `initTransactions()` non viene chiamato, oppure `sendOffsetsToTransaction()` non include tutti gli offset del consumer. In alternativa, alcuni consumer del gruppo usano `read_uncommitted` (default).

**Soluzione:** Verificare la configurazione del producer e di tutti i consumer del gruppo.

```bash
# Verificare la configurazione del consumer group
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group my-consumer-group

# Verificare i transaction marker scritti nel topic
kafka-dump-log.sh --files /var/kafka/logs/processed-orders-0/00000000000000000000.log \
  --print-data-log | grep -E "COMMIT|ABORT"
```

### Scenario 4 — Transazione bloccata, consumer lag cresce

**Sintomo:** Il consumer lag aumenta anche se i messaggi sembrano arrivare. Il consumer con `read_committed` non avanza.

**Causa:** Una transazione aperta (non committata né abortita) blocca il Last Stable Offset (LSO). I consumer con `read_committed` non possono avanzare oltre l'LSO. Questo accade quando un producer si blocca, va in crash durante una transazione, o il `transaction.timeout.ms` è molto alto.

**Soluzione:** Identificare il producer con la transazione aperta e terminarlo, oppure attendere che scada il timeout della transazione. Abbassare `transaction.timeout.ms` per minimizzare il blocco in futuro.

```bash
# Verificare il Last Stable Offset vs Log End Offset
kafka-log-dirs.sh --bootstrap-server kafka:9092 \
  --topic-list processed-orders --describe | grep -E "offsetLag|size"

# Elencare le transazioni in stato "Ongoing"
kafka-transactions.sh --bootstrap-server kafka:9092 list | grep Ongoing

# Abbassare il timeout sulle transazioni lente (config dinamica)
kafka-configs.sh --bootstrap-server kafka:9092 --alter \
  --entity-type brokers --entity-default \
  --add-config transaction.max.timeout.ms=300000
```

## Riferimenti

- [Kafka Exactly-Once Semantics](https://kafka.apache.org/documentation/#semantics)
- [KIP-98: Exactly Once Delivery](https://cwiki.apache.org/confluence/display/KAFKA/KIP-98+-+Exactly+Once+Delivery+and+Transactional+Messaging)
- [Kafka Streams EOS](https://kafka.apache.org/documentation/streams/developer-guide/config-streams.html#processing-guarantee)
- [Confluent: Exactly-Once Semantics](https://developer.confluent.io/courses/architecture/exactly-once-semantics/)
