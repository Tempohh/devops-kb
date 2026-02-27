---
title: "Quarkus e Kafka — SmallRye Reactive Messaging"
slug: quarkus-kafka
category: messaging
tags: [kafka, quarkus, smallrye, reactive, messaging]
search_keywords: [quarkus kafka, smallrye reactive messaging, quarkus kafka producer consumer, @incoming @outgoing quarkus, quarkus devservices kafka, mutiny kafka]
parent: messaging/kafka/sviluppo
related: [messaging/kafka/sviluppo/spring-kafka, messaging/kafka/sviluppo/exactly-once-semantics]
official_docs: https://quarkus.io/guides/kafka
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Quarkus e Kafka — SmallRye Reactive Messaging

## Panoramica

Quarkus integra Kafka tramite l'estensione **SmallRye Reactive Messaging**, che fornisce un modello di programmazione reattivo e dichiarativo basato sulle annotazioni `@Incoming` e `@Outgoing`. A differenza di Spring Kafka (imperativo e thread-per-message), SmallRye è costruito su **Mutiny** (libreria reactive) e supporta back-pressure, parallelismo non bloccante e pipeline reattive end-to-end.

**Quando usarlo:** Microservizi cloud-native con Quarkus, quando si vuole un footprint JVM minimo (GraalVM native image supportato), processing reattivo con back-pressure.

## Dipendenze

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-smallrye-reactive-messaging-kafka</artifactId>
</dependency>

<!-- Per Avro e Schema Registry -->
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-confluent-registry-avro</artifactId>
</dependency>
```

## Configurazione & Pratica

### application.properties

```properties
# ── Configurazione generale ────────────────────────────────────────────────
kafka.bootstrap.servers=localhost:9092

# ── Incoming channel (consumer) ───────────────────────────────────────────
mp.messaging.incoming.orders.connector=smallrye-kafka
mp.messaging.incoming.orders.topic=orders
mp.messaging.incoming.orders.group.id=order-processor
mp.messaging.incoming.orders.auto.offset.reset=earliest
mp.messaging.incoming.orders.failure-strategy=dead-letter-queue
mp.messaging.incoming.orders.dead-letter-queue.topic=orders.DLQ
mp.messaging.incoming.orders.dead-letter-queue.key.serializer=org.apache.kafka.common.serialization.StringSerializer

# ── Outgoing channel (producer) ───────────────────────────────────────────
mp.messaging.outgoing.processed-orders.connector=smallrye-kafka
mp.messaging.outgoing.processed-orders.topic=processed-orders
mp.messaging.outgoing.processed-orders.value.serializer=org.apache.kafka.common.serialization.StringSerializer

# ── Concorrenza ───────────────────────────────────────────────────────────
mp.messaging.incoming.orders.partitions=5    # worker virtuals per parallelismo
```

### Consumer semplice con @Incoming

```java
import io.smallrye.reactive.messaging.annotations.Blocking;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import jakarta.enterprise.context.ApplicationScoped;

@ApplicationScoped
public class OrderConsumer {

    @Incoming("orders")                 // canale configurato in application.properties
    @Blocking                           // operazione bloccante (es. DB write) — non blocca il thread reattivo
    public void process(String orderJson) {
        // Kafka deserializza automaticamente con il deserializer configurato
        Order order = Json.decode(orderJson);
        orderRepository.save(order);
    }
}
```

### Consume con Message (accesso a metadati)

```java
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.eclipse.microprofile.reactive.messaging.Message;
import io.smallrye.reactive.messaging.kafka.api.IncomingKafkaRecordMetadata;

@Incoming("orders")
public CompletionStage<Void> process(Message<String> message) {
    // Accesso ai metadati Kafka
    IncomingKafkaRecordMetadata<String, String> meta =
        message.getMetadata(IncomingKafkaRecordMetadata.class).orElseThrow();

    String topic = meta.getTopic();
    int partition = meta.getPartition();
    long offset = meta.getOffset();
    long timestamp = meta.getTimestamp().toEpochMilli();

    String payload = message.getPayload();
    processOrder(payload);

    return message.ack();  // commit manuale dell'offset
}
```

### Pipeline reattiva con @Incoming + @Outgoing

```java
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.eclipse.microprofile.reactive.messaging.Outgoing;
import io.smallrye.mutiny.Uni;

@ApplicationScoped
public class OrderEnrichmentService {

    @Incoming("orders")
    @Outgoing("processed-orders")
    public Uni<String> enrich(String orderJson) {
        // Trasformazione asincrona non bloccante
        return customerService.fetchCustomer(orderId)
            .map(customer -> enrichOrder(orderJson, customer))
            .map(Json::encode);
    }
}
```

### Producer con @Outgoing e Emitter

```java
import org.eclipse.microprofile.reactive.messaging.Channel;
import org.eclipse.microprofile.reactive.messaging.Emitter;
import org.eclipse.microprofile.reactive.messaging.Message;
import io.smallrye.reactive.messaging.kafka.api.OutgoingKafkaRecordMetadata;

@ApplicationScoped
public class OrderService {

    @Inject
    @Channel("processed-orders")
    Emitter<String> emitter;

    public void publishOrder(Order order) {
        // Produzione semplice
        emitter.send(Json.encode(order));
    }

    public void publishWithKey(Order order) {
        // Produzione con chiave e headers custom
        OutgoingKafkaRecordMetadata<String> metadata =
            OutgoingKafkaRecordMetadata.<String>builder()
                .withKey(order.getCustomerId())
                .withHeaders(new RecordHeaders()
                    .add("correlation-id", correlationId.getBytes()))
                .build();

        emitter.send(Message.of(Json.encode(order))
            .addMetadata(metadata));
    }
}
```

### Configurazione con Avro e Schema Registry

```properties
# Schema Registry
mp.messaging.connector.smallrye-kafka.apicurio.registry.url=http://schema-registry:8080/apis/registry/v2
# oppure Confluent Schema Registry:
# mp.messaging.connector.smallrye-kafka.schema.registry.url=http://schema-registry:8081

mp.messaging.incoming.orders.value.deserializer=io.apicurio.registry.serde.avro.AvroKafkaDeserializer
mp.messaging.incoming.orders.apicurio.registry.avro.datum.provider=io.apicurio.registry.serde.avro.ReflectAvroDatumProvider
```

### DevServices (Kafka automatico in dev mode)

Quarkus DevServices avvia automaticamente un container Kafka per lo sviluppo locale senza configurazione aggiuntiva:

```properties
# Dev mode: Kafka avviato automaticamente via Testcontainers
# Non serve configurare bootstrap.servers in dev mode

# Configurare la versione se necessario
quarkus.kafka.devservices.image-name=apache/kafka:3.9.0

# Per condividere l'istanza tra test e dev
quarkus.kafka.devservices.shared=true
```

### Test con @QuarkusTest e TestContainers

```java
@QuarkusTest
@TestProfile(KafkaTestProfile.class)
class OrderConsumerTest {

    @Inject
    @Channel("orders")
    Emitter<String> emitter;

    @Test
    void testOrderProcessing() {
        // Pubblica un messaggio di test
        emitter.send("{\"id\":\"123\",\"amount\":99.99}");

        // Verifica l'output (attesa asincrona)
        await().atMost(5, SECONDS)
            .until(() -> orderRepository.count() == 1);
    }
}
```

## Best Practices

!!! tip "Usare @Blocking per operazioni bloccanti"
    SmallRye opera su thread non bloccanti (Vert.x event loop). Operazioni bloccanti come accessi a DB, chiamate HTTP sincrone o I/O devono essere annotate con `@Blocking` per non bloccare l'event loop.

!!! tip "Gestire i fallimenti con failure-strategy"
    Configurare `failure-strategy=dead-letter-queue` per inviare i messaggi problematici al DLQ invece di bloccare il consumer. Alternative: `ignore` (scarta), `fail` (arresta il consumer).

!!! warning "Emitter e back-pressure"
    `emitter.send()` può sollevare `BackPressureFailure` se il buffer è pieno. Usare `emitter.sendAndAwait()` per attendere lo spazio, oppure `emitter.hasRequests()` per verificare la disponibilità.

## Troubleshooting

**Messaggi non ricevuti dopo startup**
- Verificare `auto.offset.reset=earliest` se il consumer è nuovo e vuole leggere messaggi esistenti
- Verificare che il canale nel `application.properties` corrisponda al nome nell'annotazione `@Incoming`

**OutOfMemoryError durante test**
- DevServices usa Testcontainers che richiedono Docker. Verificare che Docker sia in esecuzione.
- Configurare `quarkus.kafka.devservices.shared=true` per riusare il container tra test

**Messaggi non committati (offset non avanzano)**
- Se si usa `Message<T>`, chiamare esplicitamente `message.ack()`
- Con payload diretto (non Message), il commit è automatico al termine del metodo

## Riferimenti

- [Quarkus Kafka Guide](https://quarkus.io/guides/kafka)
- [SmallRye Reactive Messaging](https://smallrye.io/smallrye-reactive-messaging/)
- [Mutiny — Reactive programming with Quarkus](https://quarkus.io/guides/mutiny-primer)
