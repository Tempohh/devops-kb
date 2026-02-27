---
title: "Spring Kafka"
slug: spring-kafka
category: messaging
tags: [kafka, spring, java, spring-boot, producer, consumer]
search_keywords: [spring kafka, spring boot kafka, kafkatemplate, kafkalistener, spring kafka producer, spring kafka consumer, embedded kafka test, spring kafka error handler, DLT dead letter topic]
parent: messaging/kafka/sviluppo
related: [messaging/kafka/sviluppo/quarkus-kafka, messaging/kafka/sviluppo/exactly-once-semantics, messaging/kafka/sviluppo/transazioni, messaging/kafka/schema-registry/avro]
official_docs: https://spring.io/projects/spring-kafka
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Spring Kafka

## Panoramica

Spring Kafka è il modulo Spring che integra Apache Kafka nelle applicazioni Spring Boot, offrendo un'astrazione di alto livello sopra il client Kafka nativo. Fornisce `KafkaTemplate` per la produzione di messaggi e l'annotazione `@KafkaListener` per il consumo, gestendo internamente la configurazione, il lifecycle dei consumer e il threading. Spring Kafka include meccanismi avanzati di error handling con retry, backoff esponenziale e Dead Letter Topic (DLT) per i messaggi non elaborabili, tutto configurabile in modo dichiarativo. Il modulo si integra con Spring Transaction Management per supportare le transazioni Kafka e la semantica exactly-once. Rispetto all'uso diretto del client Kafka, Spring Kafka riduce drasticamente il codice boilerplate e offre un'integrazione naturale con gli altri moduli Spring (Security, Data, Cloud Stream).

---

## Concetti Chiave

### Componenti Principali

| Componente | Ruolo |
|-----------|-------|
| `KafkaTemplate<K, V>` | Invia messaggi a topic Kafka |
| `@KafkaListener` | Annota metodi consumatori di messaggi |
| `ConsumerFactory<K, V>` | Crea istanze del consumer Kafka |
| `ProducerFactory<K, V>` | Crea istanze del producer Kafka |
| `ConcurrentKafkaListenerContainerFactory` | Factory dei container dei listener con gestione thread |
| `KafkaListenerEndpointRegistry` | Registry dei listener per controllo lifecycle |
| `DeadLetterPublishingRecoverer` | Invia messaggi falliti alla DLT |
| `DefaultErrorHandler` | Gestisce errori con retry e backoff |

### Threading Model

`ConcurrentKafkaListenerContainerFactory` crea `ConcurrentMessageListenerContainer` che internamente avvia N thread (uno per partizione assegnata, o un numero configurabile). Ogni thread esegue il poll loop del consumer Kafka. La concorrenza si configura con `setConcurrency(n)`.

---

## Architettura / Come Funziona

```
┌──────────────────────────────────────────────────────────────────┐
│                     Spring Application                           │
│                                                                  │
│  ┌─────────────────────────────┐  ┌───────────────────────────┐  │
│  │     Producer Side           │  │      Consumer Side        │  │
│  │                             │  │                           │  │
│  │  OrderService               │  │  OrderEventHandler        │  │
│  │     │                       │  │     │                     │  │
│  │     ▼                       │  │     ▼                     │  │
│  │  KafkaTemplate              │  │  @KafkaListener           │  │
│  │     │                       │  │     │                     │  │
│  │     ▼                       │  │     ▼                     │  │
│  │  ProducerFactory            │  │  ConcurrentKafkaListener  │  │
│  │     │                       │  │  ContainerFactory         │  │
│  │     ▼                       │  │     │                     │  │
│  │  KafkaProducer (native)     │  │     ▼                     │  │
│  └─────────────────────────────┘  │  KafkaConsumer (native)   │  │
│                                   └───────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Error Handling Pipeline                                   │  │
│  │  DefaultErrorHandler → ExponentialBackOff → DLT Recoverer  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Configurazione & Pratica

### Dipendenze Maven

```xml
<dependencies>
    <!-- Spring Boot Kafka Starter -->
    <dependency>
        <groupId>org.springframework.kafka</groupId>
        <artifactId>spring-kafka</artifactId>
        <!-- Versione gestita da Spring Boot BOM -->
    </dependency>

    <!-- Per testing con EmbeddedKafka -->
    <dependency>
        <groupId>org.springframework.kafka</groupId>
        <artifactId>spring-kafka-test</artifactId>
        <scope>test</scope>
    </dependency>

    <!-- Jackson per serializzazione JSON -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>
</dependencies>
```

### application.yml — Configurazione Completa

```yaml
spring:
  kafka:
    bootstrap-servers: kafka.kafka.svc.cluster.local:9093
    properties:
      security.protocol: SSL
      ssl.truststore.location: /etc/kafka/ssl/truststore.jks
      ssl.truststore.password: ${KAFKA_TRUSTSTORE_PASSWORD}
      ssl.keystore.location: /etc/kafka/ssl/keystore.jks
      ssl.keystore.password: ${KAFKA_KEYSTORE_PASSWORD}
      ssl.key.password: ${KAFKA_KEY_PASSWORD}

    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
      acks: all                    # Attendere conferma da tutti gli ISR
      retries: 3
      properties:
        enable.idempotence: true   # Producer idempotente
        max.in.flight.requests.per.connection: 5
        delivery.timeout.ms: 120000
        request.timeout.ms: 30000
        linger.ms: 5               # Batching lieve per throughput
        batch.size: 32768          # 32 KB batch size
        compression.type: lz4

    consumer:
      group-id: order-service-group
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      auto-offset-reset: earliest
      enable-auto-commit: false    # Commit manuale per exactly-once semantics
      max-poll-records: 100
      properties:
        spring.json.trusted.packages: "com.example.events"
        fetch.min.bytes: 1
        fetch.max.wait.ms: 500
        max.poll.interval.ms: 300000
        session.timeout.ms: 45000
        heartbeat.interval.ms: 3000
```

### Configurazione Programmatica (KafkaConfig.java)

```java
package com.example.config;

import com.example.events.OrderEvent;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.*;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.support.serializer.JsonDeserializer;
import org.springframework.kafka.support.serializer.JsonSerializer;
import org.springframework.util.backoff.ExponentialBackOff;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class KafkaConfig {

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    // ─── PRODUCER ──────────────────────────────────────────────────

    @Bean
    public ProducerFactory<String, OrderEvent> producerFactory() {
        Map<String, Object> config = new HashMap<>();
        config.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        config.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        config.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);
        config.put(ProducerConfig.ACKS_CONFIG, "all");
        config.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        config.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 5);
        config.put(ProducerConfig.RETRIES_CONFIG, 3);
        config.put(ProducerConfig.LINGER_MS_CONFIG, 5);
        config.put(ProducerConfig.BATCH_SIZE_CONFIG, 32768);
        config.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");
        return new DefaultKafkaProducerFactory<>(config);
    }

    @Bean
    public KafkaTemplate<String, OrderEvent> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }

    // ─── CONSUMER ──────────────────────────────────────────────────

    @Bean
    public ConsumerFactory<String, OrderEvent> consumerFactory() {
        Map<String, Object> config = new HashMap<>();
        config.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        config.put(ConsumerConfig.GROUP_ID_CONFIG, "order-service-group");
        config.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        config.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        config.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);

        JsonDeserializer<OrderEvent> deserializer = new JsonDeserializer<>(OrderEvent.class);
        deserializer.addTrustedPackages("com.example.events");

        return new DefaultKafkaConsumerFactory<>(
            config,
            new StringDeserializer(),
            deserializer
        );
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, OrderEvent>
            kafkaListenerContainerFactory(
                ConsumerFactory<String, OrderEvent> consumerFactory,
                KafkaTemplate<String, OrderEvent> kafkaTemplate) {

        ConcurrentKafkaListenerContainerFactory<String, OrderEvent> factory =
            new ConcurrentKafkaListenerContainerFactory<>();

        factory.setConsumerFactory(consumerFactory);
        factory.setConcurrency(3); // 3 thread consumer, uno per partizione assegnata

        // Commit manuale dopo elaborazione
        factory.getContainerProperties()
               .setAckMode(ContainerProperties.AckMode.MANUAL_IMMEDIATE);

        // Error handler con retry esponenziale e DLT
        DeadLetterPublishingRecoverer recoverer =
            new DeadLetterPublishingRecoverer(kafkaTemplate);

        ExponentialBackOff backOff = new ExponentialBackOff(1000L, 2.0);
        backOff.setMaxElapsedTime(30000L); // Max 30 secondi di retry

        DefaultErrorHandler errorHandler = new DefaultErrorHandler(recoverer, backOff);
        // Alcune eccezioni non devono essere ritentate (es. DeserializationException)
        errorHandler.addNotRetryableExceptions(
            org.springframework.kafka.support.serializer.DeserializationException.class
        );

        factory.setCommonErrorHandler(errorHandler);

        return factory;
    }
}
```

### Modello Evento e Servizio Completo

```java
// events/OrderEvent.java
package com.example.events;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record OrderEvent(
    String orderId,
    String customerId,
    BigDecimal amount,
    String currency,
    String status,
    Instant timestamp
) {
    @JsonCreator
    public OrderEvent(
        @JsonProperty("orderId") String orderId,
        @JsonProperty("customerId") String customerId,
        @JsonProperty("amount") BigDecimal amount,
        @JsonProperty("currency") String currency,
        @JsonProperty("status") String status,
        @JsonProperty("timestamp") Instant timestamp) {
        this.orderId = orderId != null ? orderId : UUID.randomUUID().toString();
        this.customerId = customerId;
        this.amount = amount;
        this.currency = currency;
        this.status = status;
        this.timestamp = timestamp != null ? timestamp : Instant.now();
    }
}

// service/OrderService.java — Producer
package com.example.service;

import com.example.events.OrderEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.concurrent.CompletableFuture;

@Slf4j
@Service
@RequiredArgsConstructor
public class OrderService {

    private static final String TOPIC_ORDINI = "ordini-v1";
    private final KafkaTemplate<String, OrderEvent> kafkaTemplate;

    public CompletableFuture<SendResult<String, OrderEvent>> creaOrdine(
            String customerId, BigDecimal amount) {

        OrderEvent event = new OrderEvent(
            null, customerId, amount, "EUR", "CREATED", null
        );

        // La key è l'orderId: garantisce che tutti gli eventi dello stesso ordine
        // vadano nella stessa partizione (ordinamento garantito)
        return kafkaTemplate.send(TOPIC_ORDINI, event.orderId(), event)
            .whenComplete((result, ex) -> {
                if (ex == null) {
                    log.info("Ordine {} inviato a partizione {} offset {}",
                        event.orderId(),
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
                } else {
                    log.error("Errore invio ordine {}: {}", event.orderId(), ex.getMessage());
                }
            });
    }
}

// handler/OrderEventHandler.java — Consumer
package com.example.handler;

import com.example.events.OrderEvent;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.DltHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.annotation.RetryableTopic;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.retry.annotation.Backoff;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class OrderEventHandler {

    @KafkaListener(
        topics = "ordini-v1",
        groupId = "order-service-group",
        containerFactory = "kafkaListenerContainerFactory"
    )
    public void handleOrderEvent(
            ConsumerRecord<String, OrderEvent> record,
            Acknowledgment acknowledgment,
            @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
            @Header(KafkaHeaders.OFFSET) long offset) {

        OrderEvent event = record.value();
        log.info("Ricevuto ordine {} da partizione {} offset {}",
            event.orderId(), partition, offset);

        try {
            processOrder(event);
            acknowledgment.acknowledge(); // Commit offset dopo elaborazione
        } catch (Exception e) {
            log.error("Errore elaborazione ordine {}: {}", event.orderId(), e.getMessage());
            throw e; // Rilanciare per attivare il retry/DLT
        }
    }

    // Gestisce i messaggi finiti nella Dead Letter Topic
    @DltHandler
    public void handleDlt(
            ConsumerRecord<String, OrderEvent> record,
            @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {

        log.error("Messaggio non elaborabile ricevuto dalla DLT topic={}, orderId={}",
            topic, record.value().orderId());
        // Qui: alert, salvataggio in DB per analisi manuale, etc.
    }

    private void processOrder(OrderEvent event) {
        // Business logic di elaborazione ordine
        log.info("Elaborazione ordine: {} per cliente {} importo {}{}",
            event.orderId(), event.customerId(), event.amount(), event.currency());
    }
}
```

### Batch Listener

```java
@KafkaListener(
    topics = "ordini-v1",
    containerFactory = "batchKafkaListenerContainerFactory"  // factory con setBatchListener(true)
)
public void handleBatch(
        List<ConsumerRecord<String, OrderEvent>> records,
        Acknowledgment acknowledgment) {

    log.info("Ricevuto batch di {} messaggi", records.size());

    records.forEach(record -> {
        try {
            processOrder(record.value());
        } catch (Exception e) {
            log.error("Errore nel batch su ordine {}", record.value().orderId(), e);
        }
    });

    acknowledgment.acknowledge();
}
```

### Testing con EmbeddedKafka

```java
package com.example;

import com.example.events.OrderEvent;
import com.example.service.OrderService;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.test.EmbeddedKafkaBroker;
import org.springframework.kafka.test.context.EmbeddedKafka;
import org.springframework.kafka.test.utils.KafkaTestUtils;
import org.springframework.test.context.TestPropertySource;

import java.math.BigDecimal;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@EmbeddedKafka(
    partitions = 3,
    topics = {"ordini-v1", "ordini-v1.DLT"},
    brokerProperties = {
        "listeners=PLAINTEXT://localhost:9092",
        "port=9092"
    }
)
@TestPropertySource(properties = {
    "spring.kafka.bootstrap-servers=${spring.embedded.kafka.brokers}",
    "spring.kafka.consumer.auto-offset-reset=earliest"
})
class OrderServiceIntegrationTest {

    @Autowired
    private OrderService orderService;

    @Autowired
    private EmbeddedKafkaBroker embeddedKafka;

    @Autowired
    private ConsumerFactory<String, OrderEvent> consumerFactory;

    @Test
    void dovrebbeInviareLOrdineAlTopic() throws Exception {
        // Arrange
        Map<String, Object> consumerProps =
            KafkaTestUtils.consumerProps("test-group", "true", embeddedKafka);

        // Act
        var futureResult = orderService.creaOrdine("cliente-123", new BigDecimal("99.99"));
        var result = futureResult.get(); // Attende il completamento

        // Assert
        assertThat(result.getRecordMetadata().topic()).isEqualTo("ordini-v1");
        assertThat(result.getRecordMetadata().offset()).isGreaterThanOrEqualTo(0);
    }
}
```

---

## Best Practices

- **Commit manuale sempre**: Impostare `enable-auto-commit: false` e usare `AckMode.MANUAL_IMMEDIATE`. Il commit automatico può causare perdita di messaggi se l'applicazione crasha dopo il poll ma prima dell'elaborazione.
- **Producer idempotente come default**: Abilitare `enable.idempotence=true` sempre. Non ha overhead significativo e previene duplicati in caso di retry.
- **Key significativa sui messaggi**: Usare una key semantica (es. orderId, customerId) per garantire l'ordinamento degli eventi correlati nella stessa partizione.
- **Dead Letter Topic per i messaggi problematici**: Configurare sempre un `DeadLetterPublishingRecoverer` con retry esponenziale. Non perdere mai un messaggio silenziosamente.
- **Evitare elaborazione lunga nel listener**: Il listener deve completare entro `max.poll.interval.ms`. Per elaborazioni lunghe, delegare a un thread separato e fare attenzione alla gestione degli offset.
- **Thread safety di KafkaTemplate**: `KafkaTemplate` è thread-safe e può essere iniettato come singleton.
- **Monitoring**: Esporre le metriche Kafka tramite Micrometer con `management.metrics.enable.kafka=true`.

!!! warning "Deserializzazione fallita e DLT"
    Se un messaggio non può essere deserializzato (es. schema incompatibile), l'eccezione viene lanciata prima del listener. Configurare `ErrorHandlingDeserializer` come wrapper per gestire questi casi e inviarli alla DLT invece di bloccare il consumer.

---

## Troubleshooting

### Consumer si disconnette frequentemente (poll timeout)

```yaml
# Aumentare il timeout se l'elaborazione è lenta
spring:
  kafka:
    consumer:
      properties:
        max.poll.interval.ms: 600000  # 10 minuti
        max.poll.records: 10          # Ridurre i record per poll
```

### Messaggi duplicati dopo restart

```bash
# Verificare che enable-auto-commit sia false
# Verificare che l'ACK venga chiamato dopo ogni elaborazione
# Controllare i log per "Offset commit failed"
```

### KafkaTemplate non trova il broker

```java
// Aggiungere log verboso per debugging
logging.level.org.springframework.kafka=DEBUG
logging.level.org.apache.kafka=INFO
```

---

## Riferimenti

- [Spring for Apache Kafka Reference Documentation](https://docs.spring.io/spring-kafka/docs/current/reference/html/)
- [Spring Boot Kafka Auto-Configuration](https://docs.spring.io/spring-boot/docs/current/reference/html/messaging.html#messaging.kafka)
- [Spring Kafka GitHub](https://github.com/spring-projects/spring-kafka)
- [Error Handling in Spring Kafka](https://docs.spring.io/spring-kafka/docs/current/reference/html/#error-handlers)
- [Embedded Kafka Testing](https://docs.spring.io/spring-kafka/docs/current/reference/html/#testing)
