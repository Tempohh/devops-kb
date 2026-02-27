---
title: "Performance Tuning di Kafka"
slug: performance-tuning
category: messaging
tags: [kafka, performance, tuning, throughput, latenza, benchmark, ottimizzazione]
search_keywords: [kafka performance, kafka tuning, kafka throughput, kafka latency, batch size, linger ms, compression kafka, kafka producer tuning, kafka consumer tuning, kafka benchmark, kafka-producer-perf-test, num.io.threads, fetch.min.bytes, pagecache, xfs kafka, vm.swappiness kafka]
parent: messaging/kafka/operazioni
related: [messaging/kafka/operazioni/monitoring, messaging/kafka/operazioni/replication-fault-tolerance]
official_docs: https://kafka.apache.org/documentation/#configuration
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Performance Tuning di Kafka

## Panoramica

Le performance di Kafka dipendono dall'interazione tra configurazioni del broker, del producer, del consumer e del sistema operativo sottostante. Il tuning non è universale: le configurazioni ottimali variano significativamente tra casi d'uso orientati all'**alto throughput** (batch processing, log aggregation) e quelli a **bassa latenza** (sistemi di pagamento, trading). Il punto di partenza è sempre la misurazione: usare `kafka-producer-perf-test.sh` e `kafka-consumer-perf-test.sh` per stabilire una baseline, applicare le modifiche in modo iterativo e misurare di nuovo. Il principale vantaggio prestazionale di Kafka deriva dal **sequential disk I/O** e dall'uso aggressivo della **page cache** del kernel Linux.

!!! warning "Testare sempre in staging"
    Modifiche alle configurazioni di broker e OS in produzione senza test precedenti possono causare instabilità. Usare ambienti di staging con carico rappresentativo.

---

## Concetti Chiave

### Il trade-off Throughput vs Latenza

```
ALTA LATENZA ←──────────────────────────────────── BASSA LATENZA
     │                                                     │
     ▼                                                     ▼
ALTO THROUGHPUT                                   BASSO THROUGHPUT
batch grandi                                      batch piccoli
linger.ms alto                                    linger.ms = 0
compressione                                      no compressione
fetch.min.bytes alto                              fetch.min.bytes = 1
```

Le configurazioni per massimizzare il throughput aumentano la latenza e viceversa. Scegliere il punto di equilibrio in base ai requisiti del caso d'uso.

### Perché Kafka è veloce: Sequential I/O e Page Cache

```
Producer → Kafka Log (file sequenziale su disco)
                │
                └── Linux Page Cache (RAM)
                           │
                    Consumer Fetch ← dati serviti direttamente dalla RAM
                    (zero disk read se il consumer è aggiornato)
```

Kafka scrive sempre in append-only e legge sequenzialmente. I dischi moderni (anche HDD) raggiungono 100-600 MB/s in accesso sequenziale. La page cache del kernel garantisce che i consumer recenti leggano dalla RAM senza accesso al disco.

---

## Configurazione & Pratica

### Benchmark Baseline con `kafka-producer-perf-test.sh`

```bash
# Throughput test: 10 milioni di messaggi da 1KB, 1000 msg/thread
kafka-producer-perf-test.sh \
  --topic perf-test \
  --num-records 10000000 \
  --record-size 1024 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=kafka-broker-1.example.com:9092 \
    acks=1 \
    batch.size=131072 \
    linger.ms=5 \
    compression.type=lz4 \
    buffer.memory=67108864

# Output esempio:
# 10000000 records sent, 485623.45 records/sec (474.24 MB/sec), 4.12 ms avg latency, 89.00 ms max latency

# Latency test: throughput limitato a 10000 msg/sec
kafka-producer-perf-test.sh \
  --topic perf-test \
  --num-records 1000000 \
  --record-size 256 \
  --throughput 10000 \
  --producer-props \
    bootstrap.servers=kafka-broker-1.example.com:9092 \
    acks=all \
    linger.ms=0
```

```bash
# Benchmark consumer
kafka-consumer-perf-test.sh \
  --bootstrap-server kafka-broker-1.example.com:9092 \
  --topic perf-test \
  --messages 10000000 \
  --threads 1

# Output esempio:
# start.time, end.time, data.consumed.in.MB, MB.sec, data.consumed.in.nMsg, nMsg.sec
# 2026-02-23 10:00:00, 2026-02-23 10:00:21, 9765.63, 465.03, 10000000, 476190.48
```

---

### Tuning Broker (`server.properties`)

```properties
# ─── Thread Pool ──────────────────────────────────────────────────────────────
# num.io.threads: thread per operazioni I/O disco. Default: 8.
# Regola: (numero core CPU) oppure 2x per NVMe
num.io.threads=16

# num.network.threads: thread per elaborazione richieste di rete. Default: 3.
# Aumentare se ci sono molti client concorrenti
num.network.threads=8

# num.replica.fetchers: thread per replicare dati dagli altri broker. Default: 1.
# Aumentare con alto throughput inter-broker
num.replica.fetchers=4

# ─── Log e Disco ─────────────────────────────────────────────────────────────
# Distribuire i log su più dischi per parallelizzare l'I/O
log.dirs=/data/kafka1,/data/kafka2,/data/kafka3

# Dimensione del segmento di log. Default: 1GB.
# Segmenti più grandi = meno file aperti, meno overhead compaction
log.segment.bytes=536870912  # 512MB

# ─── Socket e Buffer ──────────────────────────────────────────────────────────
socket.send.buffer.bytes=1048576      # 1MB
socket.receive.buffer.bytes=1048576   # 1MB
socket.request.max.bytes=104857600    # 100MB

# ─── Retention (non performance diretta ma impatta uso disco) ─────────────────
log.retention.hours=168    # 7 giorni
log.retention.bytes=-1     # -1 = nessun limite per dimensione

# ─── Replica fetch ────────────────────────────────────────────────────────────
replica.fetch.max.bytes=10485760      # 10MB per replica fetch
replica.fetch.wait.max.ms=500
```

---

### Tuning Producer

```java
// Configurazione producer Java ottimizzata per alto throughput
Properties props = new Properties();
props.put("bootstrap.servers", "kafka-broker-1.example.com:9092");
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.ByteArraySerializer");

// ─── Batching ──────────────────────────────────────────────────────────────
// batch.size: dimensione massima del batch in bytes. Default: 16384 (16KB).
// Aumentare per throughput: 64KB-256KB.
props.put("batch.size", 131072);       // 128KB

// linger.ms: attesa massima prima di inviare un batch parziale. Default: 0.
// 0 = invia subito (bassa latenza), >0 = accumula (alto throughput)
props.put("linger.ms", 5);

// ─── Compressione ──────────────────────────────────────────────────────────
// none < gzip < snappy < lz4 < zstd (compressione crescente, CPU crescente)
// lz4: buon bilanciamento velocità/compressione
// zstd: migliore compression ratio, più CPU
props.put("compression.type", "lz4");

// ─── Buffer ────────────────────────────────────────────────────────────────
// Memoria totale disponibile per il buffer del producer. Default: 32MB.
props.put("buffer.memory", 67108864);  // 64MB

// ─── Acks e affidabilità ───────────────────────────────────────────────────
// acks=0: nessuna conferma (max throughput, zero garanzie)
// acks=1: leader ha ricevuto (default, buon equilibrio)
// acks=all: tutti gli ISR hanno ricevuto (max affidabilità, latenza maggiore)
props.put("acks", "all");

// Idempotenza: previene duplicati in caso di retry (richiede acks=all)
props.put("enable.idempotence", true);

// max.in.flight.requests.per.connection: con idempotenza, max 5
props.put("max.in.flight.requests.per.connection", 5);

// ─── Retry ────────────────────────────────────────────────────────────────
props.put("retries", Integer.MAX_VALUE);
props.put("delivery.timeout.ms", 120000);   // 2 minuti
props.put("request.timeout.ms", 30000);     // 30 secondi
```

```properties
# Equivalente in client.properties (per strumenti CLI)
batch.size=131072
linger.ms=5
compression.type=lz4
buffer.memory=67108864
acks=all
enable.idempotence=true
```

---

### Tuning Consumer

```properties
# ─── Fetch ────────────────────────────────────────────────────────────────────
# fetch.min.bytes: attendi almeno N bytes prima di rispondere al consumer.
# Default: 1 (risponde subito). Aumentare per throughput: 1MB-10MB.
fetch.min.bytes=1048576         # 1MB

# fetch.max.wait.ms: attesa massima se non ci sono abbastanza bytes. Default: 500ms.
fetch.max.wait.ms=500

# fetch.max.bytes: dimensione massima della risposta fetch. Default: 50MB.
fetch.max.bytes=52428800        # 50MB

# max.partition.fetch.bytes: dati max per partizione per fetch. Default: 1MB.
max.partition.fetch.bytes=10485760  # 10MB

# ─── Poll e Processing ────────────────────────────────────────────────────────
# max.poll.records: record massimi restituiti da poll(). Default: 500.
# Aumentare se il processing è veloce; diminuire se è lento (evitare session timeout)
max.poll.records=2000

# max.poll.interval.ms: tempo massimo tra due poll() prima che il consumer sia
# considerato morto. Default: 300000ms (5 min). Aumentare per processing lenti.
max.poll.interval.ms=600000     # 10 minuti

# session.timeout.ms: timeout heartbeat. Default: 45000ms.
session.timeout.ms=45000

# heartbeat.interval.ms: frequenza heartbeat. Default: 3000ms.
# Deve essere << session.timeout.ms
heartbeat.interval.ms=10000

# ─── Auto-commit ──────────────────────────────────────────────────────────────
# Disabilitare auto-commit per controllo esatto degli offset (raccomandato)
enable.auto.commit=false
```

---

### OS Tuning — Linux

```bash
# ─── Swappiness: ridurre lo swap per preservare la page cache ─────────────────
# Default: 60. Per Kafka: 1 (quasi nessuno swap, preferisce tenere RAM per cache)
echo 1 | sudo tee /proc/sys/vm/swappiness
# Rendere permanente in /etc/sysctl.conf:
echo "vm.swappiness=1" | sudo tee -a /etc/sysctl.conf

# ─── File Descriptors ─────────────────────────────────────────────────────────
# Kafka apre molti file (un file per segmento di log). Default Linux: 1024 (troppo basso)
echo "* soft nofile 100000" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 100000" | sudo tee -a /etc/security/limits.conf

# ─── Network Buffers ──────────────────────────────────────────────────────────
sudo sysctl -w net.core.wmem_max=134217728    # 128MB
sudo sysctl -w net.core.rmem_max=134217728    # 128MB
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 134217728"
sudo sysctl -w net.ipv4.tcp_rmem="4096 65536 134217728"

# ─── Dirty Page Ratio ─────────────────────────────────────────────────────────
# Ridurre dirty_ratio per evitare grandi flush sincroni
sudo sysctl -w vm.dirty_background_ratio=5
sudo sysctl -w vm.dirty_ratio=60

# ─── Filesystem XFS ───────────────────────────────────────────────────────────
# Formattare i dischi Kafka con XFS (migliore delle alternative per Kafka)
# sudo mkfs.xfs -f /dev/sdb
# Montare con opzioni ottimali:
# /dev/sdb /data/kafka1 xfs defaults,noatime,nodiratime 0 2
```

---

### Tabella Configurazioni per Use Case

| Parametro | Alto Throughput | Bassa Latenza | Bilanciato |
|-----------|----------------|---------------|------------|
| `batch.size` | 256KB | 16KB | 64KB |
| `linger.ms` | 10-20ms | 0ms | 5ms |
| `compression.type` | zstd | none | lz4 |
| `acks` | 1 | 1 | all |
| `fetch.min.bytes` | 10MB | 1 byte | 1MB |
| `fetch.max.wait.ms` | 500ms | 10ms | 500ms |
| `max.poll.records` | 2000 | 100 | 500 |
| `num.io.threads` | 2x CPU | CPU | 1.5x CPU |
| `num.network.threads` | 8+ | 4 | 6 |

---

## Best Practices

!!! tip "Misurare prima di ottimizzare"
    Non applicare tuning "a occhio". Stabilire sempre una baseline con i tool di benchmark, applicare una modifica alla volta, e misurare l'impatto. Cambiamenti multipli in contemporanea rendono impossibile identificare la causa del miglioramento o del peggioramento.

- **XFS per i log di Kafka**: XFS gestisce meglio i file di grandi dimensioni rispetto a ext4.
- **Dischi separati per log.dirs**: più path in `log.dirs` permettono a Kafka di parallelizzare le scritture su più dischi fisici.
- **NVMe > SAS > SATA**: per cluster ad alto throughput, i dischi NVMe ridramaticamente le latenze di I/O.
- **Monitorare `RequestHandlerAvgIdlePercent`**: se scende sotto il 30%, aumentare `num.io.threads`.
- **Compressione lato producer**: la compressione avviene sul client (meno rete e disco sul broker), non sul broker stesso.
- **Non usare RAID 5/6 per Kafka**: la replication di Kafka sostituisce il RAID. Usare JBOD o RAID 0.

---

## Troubleshooting

### Producer lento: latenza alta su `send()`

1. Verificare `linger.ms`: se è alto, i messaggi aspettano il riempimento del batch.
2. Verificare `buffer.memory`: se il buffer è pieno, il producer blocca per `max.block.ms`.
3. Controllare la latenza di rete verso il broker.

### Consumer lag che cresce costantemente

1. Il consumer non riesce a stare al passo con la produzione.
2. Aumentare il numero di istanze consumer (fino al numero di partizioni).
3. Verificare se il processing è il bottleneck: profilare il consumer.
4. Aumentare `max.poll.records` se il processing per record è veloce.
5. Verificare `max.poll.interval.ms`: se il consumer impiega troppo, viene rimosso dal group.

### Broker: `OutOfMemoryError`

```bash
# Aumentare la JVM heap size del broker (tipicamente 4-8GB)
# Non superare il 50% della RAM totale (lasciare spazio alla page cache)
export KAFKA_HEAP_OPTS="-Xms6g -Xmx6g"
```

---

## Riferimenti

- [Documentazione ufficiale Kafka Configuration](https://kafka.apache.org/documentation/#configuration)
- [Kafka Performance Tuning — Confluent Blog](https://developer.confluent.io/learn-kafka/apache-kafka/performance/)
- [Linux Tuning for Kafka](https://kafka.apache.org/documentation/#os)
- [Jay Kreps — The Log: What every software engineer should know](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying)
