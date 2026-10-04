---
title: "Windowing e Aggregazioni Temporali"
slug: windowing
category: messaging
tags: [kafka, streams, windowing, aggregazioni, tumbling, hopping, session]
search_keywords: [kafka streams windowing, tumbling window, hopping window, session window, sliding window, aggregazioni temporali, time-based aggregation, late arriving events, grace period, finestre temporali, windowed aggregation, suppress intermediate results, event time processing time, state store rocksdb, KTable windowed]
parent: messaging/kafka/kafka-streams
related: [messaging/kafka/kafka-streams/topologie, messaging/kafka/fondamenti/broker-cluster, messaging/kafka/kafka-connect/debezium-cdc]
official_docs: https://kafka.apache.org/documentation/streams/developer-guide/dsl-api.html#windowing
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
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

**Stream Time** — Il massimo timestamp (event time) osservato finora dal task su una partizione. Non è l'orologio di sistema: una finestra si **chiude** quando lo stream time supera `window end + grace`. Conseguenza: se non arrivano nuovi eventi, lo stream time resta fermo e le finestre aperte non si chiudono (rilevante per `suppress`).

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

### Sliding Window

Esistono due usi distinti del termine "sliding":

**1. Aggregazioni (`SlidingWindows`, KIP-450)** — finestre di durata fissa il cui bordo è ancorato ai timestamp degli eventi (non a una griglia come l'hopping): si crea una nuova finestra solo quando il contenuto cambia. Utile per "numero di eventi negli ultimi 5 minuti" con risultati esatti senza il costo di un `advance` molto piccolo.

```java
KTable<Windowed<String>, Long> last5min = orders
    .groupByKey()
    .windowedBy(SlidingWindows.ofTimeDifferenceAndGrace(
        Duration.ofMinutes(5), Duration.ofSeconds(30)))
    .count();
```

**2. Join temporali (`JoinWindows`)** — due record si uniscono se i timestamp distano meno di un intervallo. Le chiavi devono essere co-partizionate (stesso numero di partizioni e stesso partitioner).

```java
KStream<String, Click> clicks = builder.stream("clicks");
KStream<String, Purchase> purchases = builder.stream("purchases");

// Join: purchase con click avvenuto nei 5 minuti precedenti.
// ofTimeDifference* è simmetrico (±5 min): after(ZERO) esclude i click successivi.
KStream<String, EnrichedPurchase> enriched = purchases.join(
    clicks,
    (purchase, click) -> new EnrichedPurchase(purchase, click),
    JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5))
               .after(Duration.ZERO)
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

!!! warning "Latenza di emissione e stream time"
    `untilWindowCloses` emette solo quando lo stream time supera `window end + grace`. Con grace lungo la latenza cresce di pari passo; se il traffico si ferma (o una partizione è inattiva) l'ultimo risultato **non viene mai emesso** finché non arrivano nuovi eventi. Il buffer è in memoria, con backup su changelog topic.

!!! note "Alternativa: EmitStrategy"
    Nelle versioni 3.x recenti (KIP-825) `windowedBy(...).emitStrategy(EmitStrategy.onWindowClose())` ottiene lo stesso risultato direttamente nello state store, senza buffer di `suppress` né topic changelog aggiuntivo. `suppress` resta valido e molto diffuso.

### Configurazione properties

```properties
# Record cache per istanza (default 10MB). NON è la dimensione dello state store:
# deduplica gli aggiornamenti successivi sulla stessa chiave prima di emetterli/scriverli,
# quindi riduce gli aggiornamenti intermedi di una finestra.
# Dal 3.4 (KIP-770) il nome è statestore.cache.max.bytes; cache.max.bytes.buffering è deprecato (rimosso in 4.0).
statestore.cache.max.bytes=10485760

# Frequenza di commit e flush della cache (default 30000 in at-least-once, 100 con exactly_once_v2).
# Più basso = più aggiornamenti intermedi emessi e latenza minore.
commit.interval.ms=30000
```

I record oltre grace period (late) vengono **scartati** e non è configurabile: monitorare la metrica `dropped-records-total` / `dropped-records-rate` (gruppo `stream-task-metrics`) per accorgersene.

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

**Causa:** Il grace period è troppo corto rispetto al ritardo reale degli eventi (con `ofSizeWithNoGrace` qualsiasi record con timestamp più vecchio dello stream time meno la finestra è scartato), oppure il `TimestampExtractor` non estrae l'event time corretto.

**Soluzione:** Confermare lo scarto con la metrica `dropped-records-total`, poi aumentare il grace period e verificare l'estrattore di timestamp.

```java
// Verificare il TimestampExtractor configurato
Properties props = new Properties();
props.put(StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG,
    WallclockTimestampExtractor.class);  // ← processing time: finestre non riproducibili in reprocessing

// Default: timestamp del record Kafka, eccezione se negativo/invalido:
props.put(StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG,
    FailOnInvalidTimestamp.class);

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

**Causa:** La `retention` del window store è troppo alta per la cardinalità delle chiavi (spazio ≈ chiavi × finestre mantenute; con hopping ogni evento finisce in `size/advance` finestre). Una retention inferiore a `window size + grace period` non è invece accettata: Kafka Streams lancia un'eccezione alla costruzione della topologia.

**Soluzione:** Impostare la retention esplicitamente nel `Materialized` al minimo necessario (anche per interrogare le finestre passate via Interactive Queries) e valutare la cardinalità delle chiavi.

```java
// Retention minima valida: window + grace; il margine serve solo per le query sullo store
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
// kafka.streams:type=stream-state-metrics,task-id=*,rocksdb-window-state-id=*
// estimate-num-keys, total-sst-files-size (richiedono metrics.recording.level=DEBUG)
```

### Scenario 3 — Suppress non emette risultati finali

**Sintomo:** Il topic di output rimane vuoto o riceve aggiornamenti intermedi anziché solo il valore finale della finestra.

**Causa:** (1) Lo stream time non avanza: nessun nuovo evento (anche su altre chiavi della stessa partizione) dopo `window end + grace`, quindi la finestra non risulta chiusa. (2) Il grace period è lungo e il risultato arriva tardi. (3) Con `maxBytes`/`maxRecords` il buffer è pieno: `untilWindowCloses` accetta solo configurazioni *strict* e `emitEarlyWhenFull()` è rifiutato (violerebbe la semantica "solo risultato finale").

**Soluzione:** Verificare che il traffico faccia avanzare lo stream time, dimensionare il grace, e usare un buffer `unbounded()` oppure limitato con `shutDownWhenFull()` (l'app si ferma invece di emettere risultati parziali).

```java
KTable<Windowed<String>, Long> finalOnly = orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeAndGrace(
        Duration.ofMinutes(5),
        Duration.ofSeconds(30)
    ))
    .count()
    .suppress(Suppressed.untilWindowCloses(
        Suppressed.BufferConfig.maxBytes(50 * 1024 * 1024L)  // 50MB buffer
            .shutDownWhenFull()     // strict: fallisce invece di emettere risultati parziali
    ));
// Se si accettano risultati anticipati usare invece
// Suppressed.untilTimeLimit(Duration.ofMinutes(1), BufferConfig.maxBytes(...).emitEarlyWhenFull())
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
