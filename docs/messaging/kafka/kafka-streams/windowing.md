---
title: "Windowing e Aggregazioni Temporali"
slug: windowing
category: messaging
tags: [kafka, streams, windowing, aggregazioni, tumbling, hopping, session]
search_keywords: [kafka streams windowing, tumbling window, hopping window, session window, sliding window, aggregazioni temporali, time-based aggregation, late arriving events, grace period, finestre temporali, windowed aggregation, suppress intermediate results, event time processing time, state store rocksdb, KTable windowed]
parent: messaging/kafka/kafka-streams
related: [messaging/kafka/kafka-streams/topologie, messaging/kafka/fondamenti/broker-cluster, messaging/kafka/kafka-connect/debezium-cdc]
official_docs: https://kafka.apache.org/documentation/streams/developer-guide/dsl-api.html#windowing
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Windowing e Aggregazioni Temporali

## Panoramica

Il windowing in Kafka Streams permette di aggregare eventi in finestre temporali definite. Invece di calcolare un aggregato sull'intero stream (unbounded), si calcolano aggregati su sottoinsiemi di eventi che cadono in un intervallo di tempo. Questo è fondamentale per calcolare metriche come "ordini per minuto", "revenue per ora" o "errori per sessione utente".

**Quando usarlo:** Metriche in tempo reale, alerting, analytics su finestre scorrevoli, calcolo di statistiche periodiche, rilevamento di anomalie.

## Concetti Chiave

**Event Time vs Processing Time**

| Tipo | Descrizione | Uso consigliato |
|------|-------------|-----------------|
| **Event Time** | Timestamp dell'evento alla sorgente | Analisi accurate, tollerante al ritardo |
| **Processing Time** | Timestamp di processing in Kafka Streams | Semplice ma impreciso con ritardi di rete |
| **Ingestion Time** | Timestamp quando il record entra in Kafka | Compromesso tra i due |

Kafka Streams usa di default l'**event time** estratto dai record (campo timestamp del record Kafka).

**Grace Period** — Tempo aggiuntivo dopo la chiusura di una finestra durante il quale eventi in ritardo vengono ancora accettati e l'aggregato viene aggiornato.

**Retention Period** — Quanto a lungo gli aggregati della finestra vengono mantenuti nello state store (deve essere ≥ window size + grace period).

## Tipi di Window

### Tumbling Window

Finestre di dimensione fissa, **non sovrapposte**. Ogni evento appartiene esattamente a una finestra.

```
|----W1----|----W2----|----W3----|
0          5          10         15  (minuti)
```

```java
KStream<String, Order> orders = builder.stream("orders");

KTable<Windowed<String>, Long> orderCountByMinute = orders
    .groupByKey()
    .windowedBy(
        TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(1))
        // oppure con grace period per late events:
        // TimeWindows.ofSizeAndGrace(Duration.ofMinutes(1), Duration.ofSeconds(30))
    )
    .count();

// Output su topic
orderCountByMinute.toStream()
    .map((key, value) -> KeyValue.pair(
        key.key() + "@" + key.window().startTime(),
        value
    ))
    .to("order-counts-per-minute");
```

### Hopping Window

Finestre di dimensione fissa che **si sovrappongono**. Definite da `size` (dimensione) e `advance` (quanto avanza ogni finestra). Un evento può appartenere a più finestre.

```
|--------W1--------|
      |--------W2--------|
            |--------W3--------|
0     2     4     6     8     10  (minuti, size=6, advance=2)
```

```java
KTable<Windowed<String>, Long> rollingCount = orders
    .groupByKey()
    .windowedBy(
        TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(6))
                   .advanceBy(Duration.ofMinutes(2))
    )
    .count();
```

### Session Window

Finestre **dinamiche** basate sull'attività: una sessione si apre al primo evento e si chiude dopo un periodo di inattività (inactivity gap). Finestre consecutive si fondono se gli eventi sono più ravvicinati dell'inactivity gap.

```
[e1 e2 e3]  gap  [e4]  gap  [e5 e6]
|---S1---|       |-S2-|      |--S3--|
```

```java
KTable<Windowed<String>, Long> sessionEvents = clickstream
    .groupByKey()
    .windowedBy(
        SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(30))
    )
    .count();
```

### Sliding Window (Joins)

Usate principalmente per le **join temporali** tra due stream. Una finestra scorrevole comprende tutti gli eventi con timestamp entro un range dall'evento corrente.

```java
KStream<String, Click> clicks = builder.stream("clicks");
KStream<String, Purchase> purchases = builder.stream("purchases");

// Join: purchase con click avvenuto nei 5 minuti precedenti
KStream<String, EnrichedPurchase> enriched = purchases.join(
    clicks,
    (purchase, click) -> new EnrichedPurchase(purchase, click),
    JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5))
);
```

## Configurazione & Pratica

### Aggregazione con windowing completa

```java
StreamsBuilder builder = new StreamsBuilder();

// Stream di ordini con chiave = customerId
KStream<String, Order> orders = builder.stream(
    "orders",
    Consumed.with(Serdes.String(), orderSerde)
);

// Revenue per cliente per ora (tumbling window di 1 ora)
KTable<Windowed<String>, Double> hourlyRevenue = orders
    .groupByKey()
    .windowedBy(
        TimeWindows.ofSizeAndGrace(
            Duration.ofHours(1),
            Duration.ofMinutes(10)  // accetta eventi fino a 10 min in ritardo
        )
    )
    .aggregate(
        () -> 0.0,                                    // initializer
        (key, order, agg) -> agg + order.getAmount(), // aggregator
        Materialized.<String, Double, WindowStore<Bytes, byte[]>>as("hourly-revenue-store")
            .withValueSerde(Serdes.Double())
            .withRetention(Duration.ofHours(2))       // retention dello state store
    );

hourlyRevenue.toStream()
    .to("hourly-revenue-output", Produced.with(windowedStringSerde, Serdes.Double()));
```

### Soppressione degli aggiornamenti intermedi

Con le finestre, Kafka Streams emette un aggiornamento per ogni nuovo evento nella finestra. Per emettere un solo risultato finale quando la finestra si chiude:

```java
KTable<Windowed<String>, Long> finalCounts = orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeAndGrace(Duration.ofMinutes(5), Duration.ofSeconds(30)))
    .count()
    .suppress(
        Suppressed.untilWindowCloses(
            Suppressed.BufferConfig.unbounded()
        )
    );
```

!!! warning "Suppress richiede grace period > 0"
    `untilWindowCloses` funziona solo con finestre che hanno un grace period definito. Il risultato viene emesso solo dopo `window size + grace period`.

### Configurazione properties

```properties
# Dimensione dello state store in memoria prima di scrivere su disco (RocksDB)
cache.max.bytes.buffering=10485760   # 10MB

# Frequenza di commit degli offset
commit.interval.ms=100               # bassa latenza
# commit.interval.ms=30000           # alta produttività

# Handling dei late events oltre il grace period (ignorati di default)
# Non configurabile direttamente — vengono scartati
```

## Best Practices

!!! tip "Usare event time, non processing time"
    Event time garantisce risultati corretti anche in caso di reprocessing o ritardi nella rete. Assicurarsi che i producer impostino correttamente il timestamp del record.

!!! tip "Dimensionare il grace period con attenzione"
    Un grace period troppo grande aumenta la latenza dei risultati. Un grace period troppo piccolo causa perdita di dati per eventi in ritardo. Analizzare la distribuzione dei ritardi nel proprio sistema.

!!! warning "Session window e scalabilità"
    Le session window sono computazionalmente più costose delle tumbling/hopping window perché richiedono il merge di sessioni. In scenari ad alto volume, valutare se è veramente necessaria.

**Confronto tipi di window:**

| Tipo | Sovrapposizione | Dimensione | Use Case |
|------|----------------|------------|----------|
| Tumbling | No | Fissa | Metriche per periodo |
| Hopping | Sì | Fissa | Moving average |
| Session | N/A | Variabile | Sessioni utente |
| Sliding (join) | Sì | Fissa | Join temporali |

## Troubleshooting

### Scenario 1 — Risultati mancanti per eventi in ritardo

**Sintomo:** Aggregati di finestre che non includono eventi noti, o count più bassi del previsto per window recenti.

**Causa:** Il grace period è troppo corto, oppure il `TimestampExtractor` usa il processing time invece dell'event time, facendo scartare eventi con timestamp più vecchi.

**Soluzione:** Aumentare il grace period e verificare l'estrattore di timestamp.

```java
// Verificare il TimestampExtractor configurato
Properties props = new Properties();
props.put(StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG,
    WallclockTimestampExtractor.class);  // ← processing time, potenzialmente sbagliato

// Usare event time con fallback:
props.put(StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG,
    FailOnInvalidTimestamp.class);       // ← lancia eccezione su timestamp invalido

// Oppure custom extractor per campo embedded nel payload:
public class OrderTimestampExtractor implements TimestampExtractor {
    @Override
    public long extract(ConsumerRecord<Object, Object> record, long partitionTime) {
        Order order = (Order) record.value();
        return order.getEventTime();  // timestamp dalla sorgente
    }
}
```

### Scenario 2 — State store che cresce indefinitamente

**Sintomo:** Heap o disco RocksDB cresce nel tempo, OutOfMemoryError o disco pieno sulla macchina del task.

**Causa:** La `retention` del `Materialized` non è configurata o è inferiore a `window size + grace period`. Le vecchie finestre non vengono mai ripulite.

**Soluzione:** Impostare la retention esplicitamente nel `Materialized`.

```java
// Retention minima consigliata: window + grace + margine
Duration windowSize = Duration.ofHours(1);
Duration gracePeriod = Duration.ofMinutes(10);
Duration retention = windowSize.plus(gracePeriod).plus(Duration.ofMinutes(10)); // margine

KTable<Windowed<String>, Double> hourlyRevenue = orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeAndGrace(windowSize, gracePeriod))
    .aggregate(
        () -> 0.0,
        (key, order, agg) -> agg + order.getAmount(),
        Materialized.<String, Double, WindowStore<Bytes, byte[]>>as("hourly-revenue-store")
            .withValueSerde(Serdes.Double())
            .withRetention(retention)   // ← critico
    );

// Monitoraggio via JMX / metrics:
// kafka.streams:type=stream-state-metrics,task-id=*,store-name=*
// record-e2e-latency-avg, rocksdb-estimated-num-keys
```

### Scenario 3 — Suppress non emette risultati finali

**Sintomo:** Il topic di output rimane vuoto o riceve aggiornamenti intermedi anziché solo il valore finale della finestra.

**Causa:** `Suppressed.untilWindowCloses` richiede che la finestra abbia un grace period > 0. Senza grace period, Kafka Streams non sa quando la finestra è definitivamente chiusa. Oppure il buffer si riempie e scarica presto.

**Soluzione:** Assicurarsi che il grace period sia definito e dimensionare il buffer.

```java
// ERRATO: ofSizeWithNoGrace → suppress non funziona
KTable<Windowed<String>, Long> wrong = orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5)))
    .count()
    .suppress(Suppressed.untilWindowCloses(Suppressed.BufferConfig.unbounded()));

// CORRETTO: grace period esplicito
KTable<Windowed<String>, Long> correct = orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeAndGrace(
        Duration.ofMinutes(5),
        Duration.ofSeconds(30)      // ← obbligatorio per suppress
    ))
    .count()
    .suppress(Suppressed.untilWindowCloses(
        Suppressed.BufferConfig.maxBytes(50 * 1024 * 1024L)  // 50MB buffer
            .emitEarlyWhenFull()    // scarica se buffer pieno invece di crashare
    ));
```

### Scenario 4 — Session window genera sessioni non attese o troppo frammentate

**Sintomo:** Sessioni utente spezzate in molte sessioni piccole, o sessioni che si fondono erroneamente con inactivity gap molto grande.

**Causa:** L'inactivity gap non è calibrato correttamente per il dominio applicativo. Con gap troppo piccolo, brevi pause generano nuove sessioni. Con gap troppo grande, sessioni distinte vengono aggregate.

**Soluzione:** Analizzare la distribuzione degli inter-arrival time degli eventi per scegliere il gap ottimale, e verificare che la chiave di raggruppamento sia quella giusta.

```java
// Debug: stampare le sessioni con le loro finestre temporali
sessionEvents.toStream()
    .foreach((windowedKey, count) -> {
        Windowed<String> wk = windowedKey;
        System.out.printf("User=%s | Start=%s | End=%s | Events=%d%n",
            wk.key(),
            Instant.ofEpochMilli(wk.window().start()),
            Instant.ofEpochMilli(wk.window().end()),
            count);
    });

// Calibrare il gap in base alla distribuzione reale degli inter-arrival:
// P95 dei gap tra eventi della stessa sessione → inactivity gap ottimale
SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(15))
// oppure con grace period per eventi in ritardo:
SessionWindows.ofInactivityGapAndGrace(Duration.ofMinutes(15), Duration.ofSeconds(30))
```

## Riferimenti

- [Kafka Streams Windowing](https://kafka.apache.org/documentation/streams/developer-guide/dsl-api.html#windowing)
- [Confluent: Windowing in Kafka Streams](https://developer.confluent.io/courses/kafka-streams/windowing/)
- [KIP-328: Suppress Intermediate Results](https://cwiki.apache.org/confluence/display/KAFKA/KIP-328)
