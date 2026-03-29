---
title: "Transazioni Kafka"
slug: transazioni
category: messaging
tags: [kafka, transazioni, transactions, atomic, exactly-once, producer]
search_keywords: [kafka transactions, transactional producer kafka, atomic writes kafka, kafka transaction coordinator, transaction log kafka, zombie fencing kafka, kafka transactional id, transactional.id, exactly-once semantics, EOS kafka, __transaction_state, zombie producer, idempotent producer, sendOffsetsToTransaction, consume-transform-produce, atomic commit offset, begin transaction kafka, abort transaction kafka]
parent: messaging/kafka/sviluppo
related: [messaging/kafka/sviluppo/exactly-once-semantics, messaging/kafka/sviluppo/spring-kafka, messaging/kafka/pattern-microservizi/outbox-pattern, messaging/kafka/fondamenti/broker-cluster]
official_docs: https://kafka.apache.org/documentation/#transactions
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Transazioni Kafka

## Panoramica

Le transazioni Kafka permettono di scrivere su **più topic e partizioni in modo atomico**: o tutti i record vengono committati, o nessuno. Questo è il fondamento del pattern **consume-transform-produce** con garanzia exactly-once. Le transazioni includono anche la capacità di committare gli **offset dei consumer** come parte della stessa transazione, garantendo che il processing di un record e la scrittura dell'output siano un'unica operazione atomica.

**Quando usarle:** Sistemi finanziari, aggregazione di eventi con output multipli, qualsiasi scenario dove è necessario garantire che il processing di un input e la scrittura dell'output siano atomici.

## Concetti Chiave

**transactional.id** — Identificatore stabile del producer. Permette al broker di identificare il producer tra i restart e di eseguire lo **zombie fencing**. Deve essere:
- Univoco per istanza di producer (diverso per ogni istanza parallela)
- Stabile tra i restart dello stesso producer (stesso nome dopo un restart)

**Transaction Coordinator** — Broker speciale che gestisce il ciclo di vita delle transazioni per un dato `transactional.id`. Determinato tramite hash: `hash(transactional.id) % num.partitions` del topic `__transaction_state`.

**Transaction Log** — Topic interno `__transaction_state` dove vengono scritti gli stati delle transazioni (ONGOING, PREPARE_COMMIT, COMPLETE_COMMIT, PREPARE_ABORT, COMPLETE_ABORT).

**Transaction Marker** — Record speciale scritto al termine di ogni transazione (COMMIT o ABORT) in ogni partizione toccata dalla transazione. I consumer `read_committed` attendono il marker prima di consegnare i record.

**Epoch** — Numero incrementale associato al `transactional.id`. Ogni nuovo produttore che si inizializza con lo stesso `transactional.id` riceve un epoch più alto. Il broker rifiuta le richieste con epoch inferiore (zombie fencing).

**Producer ID (PID)** — Identificativo interno del producer assegnato dal broker, usato insieme all'epoch per il tracking della sequenza e l'idempotenza.

## Ciclo di Vita di una Transazione

```mermaid
sequenceDiagram
    participant P as Producer
    participant TC as Transaction Coordinator
    participant B1 as Broker 1 (topic-A part.0)
    participant B2 as Broker 2 (topic-B part.2)

    Note over P,TC: Inizializzazione (una volta all'avvio)
    P->>TC: FindCoordinator(transactional.id)
    TC-->>P: coordinatorId
    P->>TC: InitProducerId(transactional.id)
    TC-->>P: PID + Epoch

    Note over P,TC: Ogni transazione
    P->>TC: AddPartitionsToTxn(topic-A:0, topic-B:2)
    TC-->>P: OK (registra partizioni nel tx log)

    P->>B1: Produce(PID, Epoch, seq=1, topic-A:0)
    B1-->>P: ACK
    P->>B2: Produce(PID, Epoch, seq=1, topic-B:2)
    B2-->>P: ACK

    Note over P,TC: Commit degli offset (opzionale, per consume-transform-produce)
    P->>TC: AddOffsetsToTxn(groupId)
    P->>TC: TxnOffsetCommit(groupId, offsets)

    Note over P,TC: Commit
    P->>TC: EndTxn(COMMIT)
    TC->>B1: WriteTxnMarker(COMMIT)
    TC->>B2: WriteTxnMarker(COMMIT)
    B1-->>TC: ACK
    B2-->>TC: ACK
    TC-->>P: OK
```

## Configurazione & Pratica

### Configurazione producer transazionale

```java
Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);

// ── Configurazioni transazionali obbligatorie ─────────────────────────────
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "payment-processor-instance-1");

// ── Timeout della transazione ────────────────────────────────────────────
// Se la transazione non viene committata/abortita entro questo timeout,
// il coordinator la aborta automaticamente
props.put(ProducerConfig.TRANSACTION_TIMEOUT_CONFIG, 30000);  // 30 secondi

// ── Impliciti con idempotenza ─────────────────────────────────────────────
// acks=all (automatico)
// max.in.flight.requests.per.connection=5 (automatico)
// retries=Integer.MAX_VALUE (automatico)

KafkaProducer<String, String> producer = new KafkaProducer<>(props);

// ── Inizializzazione (UNA SOLA VOLTA all'avvio) ───────────────────────────
// Recupera PID e incrementa l'epoch (zombie fencing)
producer.initTransactions();
```

### Transazione con scrittura su un singolo topic

```java
try {
    producer.beginTransaction();

    // Scritture atomiche su più partizioni dello stesso topic
    producer.send(new ProducerRecord<>("payments", "payment:101", paymentJson1));
    producer.send(new ProducerRecord<>("payments", "payment:102", paymentJson2));
    producer.send(new ProducerRecord<>("payments", "payment:103", paymentJson3));

    producer.commitTransaction();
    log.info("Transazione committata: 3 pagamenti");

} catch (ProducerFencedException | OutOfOrderSequenceException | AuthorizationException e) {
    // Errori fatali — il producer non è più utilizzabile
    producer.close();
    throw new RuntimeException("Producer fence — restart required", e);
} catch (KafkaException e) {
    // Errori recuperabili — aborta e riprova
    producer.abortTransaction();
    log.warn("Transazione abortita, retry possibile", e);
}
```

### Transazione con scrittura su topic multipli

```java
producer.beginTransaction();
try {
    // Scrittura su topic diversi — atomica
    producer.send(new ProducerRecord<>("orders-created", orderId, orderJson));
    producer.send(new ProducerRecord<>("inventory-reserved", orderId, inventoryJson));
    producer.send(new ProducerRecord<>("payment-requested", orderId, paymentJson));

    producer.commitTransaction();

} catch (Exception e) {
    producer.abortTransaction();
    // Nessuno dei tre record è visibile ai consumer
    throw e;
}
```

### Consume-Transform-Produce con commit degli offset atomico

```java
KafkaConsumer<String, String> consumer = createConsumerWithReadCommitted();
KafkaProducer<String, String> producer = createTransactionalProducer();
producer.initTransactions();

consumer.subscribe(List.of("raw-events"));

while (running) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(200));
    if (records.isEmpty()) continue;

    producer.beginTransaction();
    try {
        // 1. Processare i record
        List<ProducerRecord<String, String>> outputs = records.records("raw-events")
            .stream()
            .map(r -> new ProducerRecord<>("processed-events", r.key(), transform(r.value())))
            .collect(toList());

        // 2. Inviare l'output
        outputs.forEach(producer::send);

        // 3. Committare gli offset DEL CONSUMER come parte della transazione
        // Questo è il meccanismo chiave: se la transazione viene abortita,
        // anche gli offset vengono rollback-ati
        Map<TopicPartition, OffsetAndMetadata> offsetsToCommit = new HashMap<>();
        for (TopicPartition partition : records.partitions()) {
            List<ConsumerRecord<String, String>> partitionRecords = records.records(partition);
            long lastOffset = partitionRecords.get(partitionRecords.size() - 1).offset();
            offsetsToCommit.put(partition, new OffsetAndMetadata(lastOffset + 1));
        }
        producer.sendOffsetsToTransaction(offsetsToCommit, consumer.groupMetadata());

        // 4. Commit atomico: output + offset
        producer.commitTransaction();

    } catch (Exception e) {
        producer.abortTransaction();
        // Il consumer non ha committato → rileggerà gli stessi record al prossimo poll
        log.error("Transazione abortita, record saranno riletti", e);
    }
}
```

### Configurazione broker per le transazioni

```properties
# server.properties
# Replication factor del transaction state log (produzione: 3)
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2

# Timeout massimo per una transazione aperta
transaction.max.timeout.ms=900000    # 15 minuti (default)

# Retention del transaction state log
transactional.id.expiration.ms=604800000  # 7 giorni
```

## Best Practices

!!! tip "transactional.id deve essere unico per istanza"
    In un deployment con 3 istanze dell'applicazione, usare ID come `order-processor-0`, `order-processor-1`, `order-processor-2`. In Kubernetes, usare il nome del pod come suffisso.

!!! warning "Non condividere un producer transazionale tra thread"
    Il `KafkaProducer` è thread-safe per le operazioni di `send`, ma le transazioni devono essere gestite sequenzialmente da un singolo thread (un thread non può aprire una nuova transazione mentre un altro thread ne sta gestendo un'altra).

!!! tip "Gestire ProducerFencedException come errore fatale"
    Quando si riceve `ProducerFencedException`, il producer è stato sostituito da un'istanza più recente con lo stesso `transactional.id`. Non tentare di recuperare — creare un nuovo producer.

!!! warning "transaction.timeout troppo lungo aumenta il rischio di dangling transactions"
    Una transazione lunga blocca la garbage collection del log per tutte le partizioni toccate. Mantenere `transaction.timeout.ms` proporzionale alla durata effettiva delle transazioni.

## Troubleshooting

**Tabella eccezioni e azioni**

| Eccezione | Causa | Azione |
|-----------|-------|--------|
| `ProducerFencedException` | Altro producer con stesso transactional.id | Chiudere il producer e creare un nuovo |
| `OutOfOrderSequenceException` | Sequenza degli offset non valida | Chiudere il producer e creare un nuovo |
| `InvalidTransactionStateException` | Chiamata API fuori ordine | Correggere il flusso del codice |
| `TransactionAbortedException` | Il coordinator ha abortito la transazione | Abortire e riprovare |
| `KafkaException` (altri) | Errori recuperabili | `abortTransaction()` + retry |

### Scenario 1 — Consumer vede record di transazioni abortite

**Sintomo:** Il consumer riceve record che dovevano essere eliminati perché la transazione è stata abortita.

**Causa:** Il consumer è configurato con `isolation.level=read_uncommitted` (il default), che rende visibili tutti i record indipendentemente dallo stato della transazione.

**Soluzione:** Impostare esplicitamente `read_committed` nel consumer.

```java
Properties consumerProps = new Properties();
consumerProps.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
// Verifica il valore corrente
KafkaConsumer<String, String> consumer = new KafkaConsumer<>(consumerProps);

// Da CLI: controlla la configurazione del consumer group
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group my-consumer-group
```

### Scenario 2 — ProducerFencedException al riavvio dell'applicazione

**Sintomo:** L'applicazione lancia `ProducerFencedException` subito dopo l'avvio, prima ancora di processare un record.

**Causa:** Un'altra istanza (o la stessa prima del crash) è ancora attiva con lo stesso `transactional.id`, oppure l'epoch precedente è più recente di quello che il nuovo producer ha ricevuto. Il broker rifiuta il producer con epoch inferiore.

**Soluzione:** Verificare che non ci siano istanze zombie. Il `transactional.id` deve essere univoco per ogni istanza running contemporaneamente. Chiudere il producer fencato e inizializzarne uno nuovo.

```bash
# Verifica producer attivi tramite describe del topic
kafka-transactions.sh --bootstrap-server kafka:9092 \
  --describe --transactional-id payment-processor-instance-1

# In Kubernetes: verifica che non ci siano pod duplicati
kubectl get pods -l app=payment-processor --all-namespaces

# Log da cercare per confermare il fencing
grep "ProducerFenced\|transactional.id\|epoch" app.log
```

### Scenario 3 — Transazione bloccata / timeout del coordinator

**Sintomo:** Le transazioni impiegano molto tempo e alla fine falliscono con `TimeoutException` o vengono abortite dal coordinator. Il throughput cala drasticamente.

**Causa:** Il `transaction.timeout.ms` del producer è troppo basso per la durata effettiva del processing, oppure il Transaction Coordinator è sovraccarico. Ogni transazione aperta blocca la garbage collection del log sulle partizioni toccate.

**Soluzione:** Aumentare il timeout in modo proporzionale alla durata effettiva delle transazioni. Ridurre il numero di partizioni per transazione. Verificare la latenza verso il coordinator.

```bash
# Verifica timeout configurato nel producer (default: 60000ms)
kafka-configs.sh --bootstrap-server kafka:9092 \
  --describe --entity-type brokers --entity-default | grep transaction

# Controlla transazioni aperte (dangling)
kafka-transactions.sh --bootstrap-server kafka:9092 \
  --list | grep ONGOING

# Metrics del Transaction Coordinator (JMX)
kafka.server:type=transaction-coordinator-metrics,name=transaction-avg-time-ms
kafka.server:type=transaction-coordinator-metrics,name=transaction-failure-rate
```

### Scenario 4 — Offset non committati dopo crash nel consume-transform-produce

**Sintomo:** Dopo un crash, il consumer rilegge record già processati, causando duplicati nell'output anche con EOS abilitato.

**Causa:** Il commit degli offset non è stato incluso nella transazione tramite `sendOffsetsToTransaction`. Se gli offset vengono committati separatamente con `consumer.commitSync()`, il crash tra la commit della transazione e la commit degli offset crea un gap.

**Soluzione:** Usare esclusivamente `producer.sendOffsetsToTransaction()` per committare gli offset come parte della transazione. Non chiamare mai `consumer.commitSync()` in un loop EOS.

```java
// SBAGLIATO: offset committati separatamente
producer.commitTransaction();
consumer.commitSync(offsetsToCommit);  // ← se crasha qui, i record vengono riletti

// CORRETTO: offset come parte della transazione
producer.sendOffsetsToTransaction(offsetsToCommit, consumer.groupMetadata());
producer.commitTransaction();  // offset + output: operazione atomica

// Verifica: controlla che il consumer group NON usi auto.commit
props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
```

## Riferimenti

- [Kafka Transactions](https://kafka.apache.org/documentation/#transactions)
- [KIP-98: Exactly Once Delivery and Transactional Messaging](https://cwiki.apache.org/confluence/display/KAFKA/KIP-98+-+Exactly+Once+Delivery+and+Transactional+Messaging)
- [Confluent: Transactions in Apache Kafka](https://www.confluent.io/blog/transactions-apache-kafka/)
