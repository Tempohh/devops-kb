---
title: "Quarkus e Kafka — SmallRye Reactive Messaging"
slug: quarkus-kafka
category: messaging
tags: [kafka, quarkus, smallrye, reactive, messaging]
search_keywords: [quarkus kafka, smallrye reactive messaging, quarkus kafka producer consumer, "@incoming @outgoing quarkus", quarkus devservices kafka, mutiny kafka, quarkus reactive messaging, microprofile reactive messaging, quarkus kafka emitter, smallrye kafka connector, quarkus kafka avro, quarkus kafka testcontainers, quarkus native kafka, backpressure kafka quarkus]
parent: messaging/kafka/sviluppo
related: [messaging/kafka/sviluppo/spring-kafka, messaging/kafka/sviluppo/exactly-once-semantics]
official_docs: https://quarkus.io/guides/kafka
status: complete
difficulty: advanced
last_updated: 2026-03-29
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
    Configurare `failure-strategy=dead-letter-queue` per inviare i messaggi problematici al DLQ (Dead Letter Queue) invece di bloccare il consumer. Alternative: `ignore` (scarta), `fail` (arresta il consumer).

!!! warning "Emitter e back-pressure"
    `emitter.send()` può sollevare `BackPressureFailure` se il buffer è pieno. Usare `emitter.sendAndAwait()` per attendere lo spazio, oppure `emitter.hasRequests()` per verificare la disponibilità.

## Troubleshooting

### Scenario 1 — Messaggi non ricevuti dopo startup

**Sintomo:** Il consumer è avviato ma non processa messaggi presenti nel topic prima dello startup.

**Causa:** Il default di `auto.offset.reset` è `latest`, quindi il consumer legge solo i nuovi messaggi prodotti dopo la connessione.

**Soluzione:** Impostare `auto.offset.reset=earliest` per i consumer nuovi che devono leggere dalla coda, oppure verificare il `group.id` per ripartire da un offset committato.

```properties
mp.messaging.incoming.orders.auto.offset.reset=earliest
mp.messaging.incoming.orders.group.id=order-processor
```

### Scenario 2 — Offset non avanzano (consumer bloccato)

**Sintomo:** Il consumer riceve messaggi ma gli offset non vengono committati; i messaggi vengono riprocessati dopo ogni restart.

**Causa:** Quando si usa `Message<T>` come parametro, l'ack deve essere chiamato esplicitamente. Se il metodo torna senza chiamare `message.ack()` o `message.nack()`, l'offset non avanza.

**Soluzione:** Chiamare sempre `message.ack()` al termine del processing, o usare il payload diretto (non `Message<T>`) per ack automatico.

```java
@Incoming("orders")
public CompletionStage<Void> process(Message<String> message) {
    try {
        processOrder(message.getPayload());
        return message.ack();       // commit esplicito richiesto
    } catch (Exception e) {
        return message.nack(e);     // manda al DLQ se configurato
    }
}
```

### Scenario 3 — BackPressureFailure durante produzione con Emitter

**Sintomo:** `io.smallrye.reactive.messaging.providers.locals.ContextAwareMessage$BackPressureFailure` al momento di `emitter.send()` sotto carico.

**Causa:** Il buffer dell'Emitter è pieno: il producer genera messaggi più velocemente di quanto Kafka riesca ad accettarli.

**Soluzione:** Usare `sendAndAwait()` per attendere che il buffer si svuoti, oppure aumentare il buffer con `overflow-buffer-size`.

```properties
# Aumentare il buffer (default: 256)
mp.messaging.outgoing.processed-orders.overflow-buffer-size=1024
```

```java
// Alternativa: attesa bloccante (solo se @Blocking)
emitter.sendAndAwait(Json.encode(order));

// Controllo prima di inviare
if (emitter.hasRequests()) {
    emitter.send(Json.encode(order));
}
```

### Scenario 4 — DevServices non avvia il container Kafka

**Sintomo:** In dev mode, l'applicazione fallisce con `Connection refused` verso `localhost:9092` o Docker non viene trovato.

**Causa:** DevServices usa Testcontainers che richiede Docker (o Podman) in esecuzione. Se Docker Desktop è spento o non configurato, il container non parte.

**Soluzione:** Verificare Docker, oppure disabilitare DevServices e configurare un broker manuale.

```bash
# Verificare che Docker sia in esecuzione
docker info

# Oppure usare Podman come alternativa
export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock
```

```properties
# Disabilitare DevServices e puntare a un broker esterno
quarkus.kafka.devservices.enabled=false
kafka.bootstrap.servers=localhost:9092
```

## Riferimenti

- [Quarkus Kafka Guide](https://quarkus.io/guides/kafka)
- [SmallRye Reactive Messaging](https://smallrye.io/smallrye-reactive-messaging/)
- [Mutiny — Reactive programming with Quarkus](https://quarkus.io/guides/mutiny-primer)
