---
title: "Monitoring di Kafka"
slug: monitoring
category: messaging
tags: [kafka, monitoring, prometheus, grafana, jmx, observability, consumer-lag]
search_keywords: [kafka monitoring, jmx kafka, prometheus kafka, grafana kafka, consumer lag, under replicated partitions, kafka exporter, akhq, kafka ui, kafka metrics, jmx exporter, alerting kafka]
parent: messaging/kafka/operazioni
related: [messaging/kafka/operazioni/performance-tuning, messaging/kafka/operazioni/replication-fault-tolerance]
official_docs: https://kafka.apache.org/documentation/#monitoring
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Monitoring di Kafka

## Panoramica

Il monitoring di Kafka è essenziale per garantire la salute del cluster, identificare bottleneck di performance e rilevare problemi prima che impattino i consumatori. Kafka espone metriche attraverso **JMX (Java Management Extensions)**, che possono essere raccolte da strumenti come **JMX Exporter** (per Prometheus) o soluzioni SaaS. Le metriche si dividono in tre livelli: broker, producer e consumer. Il **consumer lag** è la metrica operativa più critica per le applicazioni: indica quanti messaggi i consumer devono ancora processare. Lo stack di monitoring più diffuso nell'ecosistema open source è JMX Exporter → Prometheus → Grafana.

!!! note "KRaft e metriche"
    A partire da Kafka 3.x con KRaft (senza ZooKeeper), alcune metriche JMX sono cambiate. Verificare la compatibilità delle dashboard Grafana con la versione del cluster.

---

## Concetti Chiave

### Tre livelli di metriche

```
┌──────────────────────────────────────────────────────────┐
│  BROKER METRICS          │ Salute del cluster e I/O      │
│  kafka.server.*          │                               │
├──────────────────────────┼───────────────────────────────┤
│  PRODUCER METRICS        │ Throughput e latenza lato     │
│  kafka.producer.*        │ produzione                    │
├──────────────────────────┼───────────────────────────────┤
│  CONSUMER METRICS        │ Lag, throughput e latenza     │
│  kafka.consumer.*        │ lato consumo                  │
└──────────────────────────┴───────────────────────────────┘
```

---

## Come Funziona

### Architettura dello stack di monitoring

```
Kafka Broker
   │
   │ espone JMX (porta 9999)
   ▼
JMX Exporter (Java Agent)
   │
   │ HTTP scrape (porta 7071)
   ▼
Prometheus
   │
   │ query PromQL
   ▼
Grafana Dashboard
   │
   │ alert rules
   ▼
AlertManager → PagerDuty / Slack / Email
```

Kafka Exporter (progetto open-source separato) si affianca al JMX Exporter per esporre metriche di consumer lag non disponibili via JMX standard.

---

## Configurazione & Pratica

### JMX Exporter — Configurazione

```bash
# Scaricare il JMX Exporter Java Agent
wget https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar \
  -O /opt/kafka/libs/jmx_prometheus_javaagent.jar
```

```yaml
# /etc/kafka/jmx-exporter-config.yaml
startDelaySeconds: 0
lowercaseOutputName: false
lowercaseOutputLabelNames: false

rules:
  # Under-replicated partitions
  - pattern: 'kafka.server<type=ReplicaManager, name=UnderReplicatedPartitions><>Value'
    name: kafka_server_replica_manager_under_replicated_partitions
    type: GAUGE

  # Offline partitions
  - pattern: 'kafka.controller<type=KafkaController, name=OfflinePartitionsCount><>Value'
    name: kafka_controller_offline_partitions_count
    type: GAUGE

  # Active controller count (deve essere sempre 1)
  - pattern: 'kafka.controller<type=KafkaController, name=ActiveControllerCount><>Value'
    name: kafka_controller_active_controller_count
    type: GAUGE

  # Bytes in/out per secondo
  - pattern: 'kafka.server<type=BrokerTopicMetrics, name=BytesInPerSec><>OneMinuteRate'
    name: kafka_server_broker_topic_metrics_bytes_in_per_sec
    type: GAUGE

  - pattern: 'kafka.server<type=BrokerTopicMetrics, name=BytesOutPerSec><>OneMinuteRate'
    name: kafka_server_broker_topic_metrics_bytes_out_per_sec
    type: GAUGE

  # Request handler idle ratio
  - pattern: 'kafka.server<type=KafkaRequestHandlerPool, name=RequestHandlerAvgIdlePercent><>OneMinuteRate'
    name: kafka_server_request_handler_avg_idle_percent
    type: GAUGE

  # Produce/Fetch request latency
  - pattern: 'kafka.network<type=RequestMetrics, name=TotalTimeMs, request=Produce><>99thPercentile'
    name: kafka_network_request_metrics_produce_total_time_ms_p99
    type: GAUGE

  - pattern: 'kafka.network<type=RequestMetrics, name=TotalTimeMs, request=FetchConsumer><>99thPercentile'
    name: kafka_network_request_metrics_fetch_consumer_total_time_ms_p99
    type: GAUGE

  # ISR Shrink/Expand
  - pattern: 'kafka.server<type=ReplicaManager, name=IsrShrinksPerSec><>OneMinuteRate'
    name: kafka_server_replica_manager_isr_shrinks_per_sec
    type: GAUGE
```

```bash
# Configurare nel broker (kafka-env.sh o variabile d'ambiente)
export KAFKA_OPTS="-javaagent:/opt/kafka/libs/jmx_prometheus_javaagent.jar=7071:/etc/kafka/jmx-exporter-config.yaml"
```

### Kafka Exporter — Consumer Lag

```bash
# Kafka Exporter espone metriche di lag per consumer group
# https://github.com/danielqsj/kafka_exporter

docker run -d \
  --name kafka-exporter \
  -p 9308:9308 \
  danielqsj/kafka-exporter \
    --kafka.server=kafka-broker-1.example.com:9092 \
    --kafka.version=3.6.0 \
    --sasl.enabled \
    --sasl.username=monitoring \
    --sasl.password=monitoring-pwd \
    --sasl.mechanism=SCRAM-SHA-512 \
    --tls.enabled \
    --tls.ca-file=/etc/ssl/kafka-ca.pem
```

### Prometheus — Configurazione Scrape

```yaml
# prometheus.yml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  # JMX Exporter sui broker
  - job_name: 'kafka-brokers'
    static_configs:
      - targets:
          - 'kafka-broker-1.example.com:7071'
          - 'kafka-broker-2.example.com:7071'
          - 'kafka-broker-3.example.com:7071'
    relabel_configs:
      - source_labels: [__address__]
        target_label: broker
        regex: '([^:]+):.*'
        replacement: '$1'

  # Kafka Exporter per consumer lag
  - job_name: 'kafka-exporter'
    static_configs:
      - targets:
          - 'kafka-exporter:9308'
```

### Consumer Lag — Analisi con `kafka-consumer-groups.sh`

```bash
# Listare tutti i consumer group attivi
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1.example.com:9092 \
  --command-config admin.properties \
  --list

# Descrivere il lag di un consumer group specifico
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1.example.com:9092 \
  --command-config admin.properties \
  --describe \
  --group order-processor

# Output esempio:
# GROUP           TOPIC     PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG  CONSUMER-ID
# order-processor orders    0          12450           12452           2    consumer-1-...
# order-processor orders    1          9871            9875            4    consumer-2-...
# order-processor orders    2          15300           15300           0    consumer-3-...

# Lag totale = somma della colonna LAG (in questo caso: 2 + 4 + 0 = 6)

# Verificare tutti i consumer group e il loro lag
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1.example.com:9092 \
  --command-config admin.properties \
  --describe \
  --all-groups 2>/dev/null | awk 'NR>1 {lag+=$NF} END {print "Total lag:", lag}'
```

### Alert Prometheus — Regole Critiche

```yaml
# kafka-alerts.yml
groups:
  - name: kafka.critical
    rules:
      # CRITICO: partizioni non replicate
      - alert: KafkaUnderReplicatedPartitions
        expr: kafka_server_replica_manager_under_replicated_partitions > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Kafka: partizioni under-replicated su {{ $labels.broker }}"
          description: "{{ $value }} partizioni non sono correttamente replicate. Rischio di perdita dati."

      # CRITICO: nessun controller attivo
      - alert: KafkaNoActiveController
        expr: sum(kafka_controller_active_controller_count) != 1
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Kafka: controller count anomalo ({{ $value }})"
          description: "Deve esserci esattamente 1 controller attivo. Il cluster potrebbe essere instabile."

      # CRITICO: partizioni offline
      - alert: KafkaOfflinePartitions
        expr: kafka_controller_offline_partitions_count > 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Kafka: {{ $value }} partizioni offline"
          description: "Partizioni offline significano messaggi non accessibili a producer e consumer."

      # WARNING: consumer lag elevato
      - alert: KafkaConsumerLagHigh
        expr: kafka_consumergroup_lag_sum > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Consumer lag elevato per {{ $labels.consumergroup }}"
          description: "Il consumer group {{ $labels.consumergroup }} ha {{ $value }} messaggi in arretrato."

      # WARNING: request handler saturo
      - alert: KafkaRequestHandlerIdleLow
        expr: kafka_server_request_handler_avg_idle_percent < 0.2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Kafka request handler quasi saturo ({{ $value | humanizePercentage }})"
          description: "I thread del request handler sono quasi saturi. Il broker potrebbe rallentare."

      # WARNING: ISR shrink frequente
      - alert: KafkaIsrShrinksFrequent
        expr: rate(kafka_server_replica_manager_isr_shrinks_per_sec[5m]) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Kafka ISR si sta restringendo frequentemente"
          description: "Frequenti ISR shrink indicano problemi di replica. Verificare la rete e il I/O dei broker."
```

---

## Metriche JMX Essenziali

### Broker — Metriche Critiche

| Metrica JMX | Tipo | Soglia Alert | Descrizione |
|-------------|------|--------------|-------------|
| `ReplicaManager/UnderReplicatedPartitions` | Gauge | > 0 | Partizioni non completamente replicate |
| `KafkaController/OfflinePartitionsCount` | Gauge | > 0 | Partizioni inaccessibili |
| `KafkaController/ActiveControllerCount` | Gauge | != 1 | Controller del cluster (deve essere 1) |
| `BrokerTopicMetrics/BytesInPerSec` | Rate | dipende dal capacity | Throughput in ingresso |
| `BrokerTopicMetrics/BytesOutPerSec` | Rate | dipende dal capacity | Throughput in uscita |
| `KafkaRequestHandlerPool/RequestHandlerAvgIdlePercent` | Gauge | < 20% | Saturazione thread pool |
| `ReplicaManager/IsrShrinksPerSec` | Rate | > 0 sostenuto | Restringimento ISR |

### Consumer — Metriche Chiave

| Metrica JMX | Tipo | Descrizione |
|-------------|------|-------------|
| `consumer-fetch-manager-metrics/records-lag-max` | Gauge | Lag massimo tra tutte le partizioni |
| `consumer-fetch-manager-metrics/fetch-latency-avg` | Gauge | Latenza media delle fetch request |
| `consumer-coordinator-metrics/commit-latency-avg` | Gauge | Latenza del commit degli offset |

---

## Strumenti Grafici

### AKHQ (ex Kafka HQ)

```bash
# docker-compose.yml per AKHQ
version: "3"
services:
  akhq:
    image: tchiotludo/akhq:latest
    environment:
      AKHQ_CONFIGURATION: |
        akhq:
          connections:
            kafka-prod:
              properties:
                bootstrap.servers: "kafka-broker-1.example.com:9094"
                security.protocol: SASL_SSL
                sasl.mechanism: SCRAM-SHA-512
                sasl.jaas.config: >
                  org.apache.kafka.common.security.scram.ScramLoginModule required
                  username="monitoring" password="monitoring-pwd";
                ssl.truststore.location: /certs/kafka.truststore.jks
                ssl.truststore.password: changeit
    ports:
      - "8080:8080"
    volumes:
      - ./certs:/certs
```

---

## Best Practices

- **Monitorare il lag per consumer group, non per topic**: il lag è significativo solo nel contesto del consumer group specifico.
- **Separare le metriche business da quelle infrastrutturali**: es. "ordini processati per secondo" vs "bytes/sec Kafka".
- **Impostare retention di Prometheus adeguata**: le metriche Kafka sono preziose per analisi post-incidente (30-90 giorni).
- **Dashboard gerarchiche in Grafana**: overview → drill-down per broker → drill-down per topic/consumer group.
- **Non fare scrape troppo frequente**: ogni 15-30 secondi è sufficiente; scrape troppo frequente impatta le performance del broker.

---

## Troubleshooting

### Scenario 1 — Consumer lag che non scende

**Sintomo:** `kafka_consumergroup_lag_sum` rimane costante o cresce anche con il consumer attivo.

**Causa:** Il consumer non riesce a tenere il passo con la produzione: processing troppo lento, consumer group con partizioni non assegnate, o istanze consumer crashate.

**Soluzione:** Verificare lo stato del gruppo e identificare se è un problema di throughput o di assignment.

```bash
# Descrivere lo stato del consumer group
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties \
  --describe --group order-processor

# Verificare se ci sono partizioni senza consumer assegnato (campo CONSUMER-ID vuoto)
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties \
  --describe --group order-processor | awk '$NF == "-" || $NF == "" {print "Unassigned:", $0}'

# Se il gruppo è DEAD/EMPTY, resettare gli offset solo se i messaggi non devono essere riprocessati
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties \
  --reset-offsets --to-latest \
  --group order-processor --topic orders --execute
```

### Scenario 2 — JMX non raggiungibile da JMX Exporter

**Sintomo:** Prometheus restituisce errori di scrape per il job `kafka-brokers`; `kafka_server_*` metrics assenti in Grafana.

**Causa:** JMX Exporter non configurato come Java Agent nel broker, porta JMX bloccata da firewall, o hostname RMI non corretto (frequente in ambienti containerizzati).

**Soluzione:** Verificare le variabili d'ambiente del broker e la raggiungibilità della porta.

```bash
# Verificare che il processo Kafka abbia il javaagent attivo
ps aux | grep kafka | grep jmx_prometheus_javaagent

# Testare il scrape endpoint dell'exporter
curl -s http://kafka-broker-1.example.com:7071/metrics | head -20

# Se JMX remoto è necessario, impostare l'hostname RMI esplicito
export KAFKA_JMX_OPTS="-Dcom.sun.jmx.remote.ssl=false \
  -Dcom.sun.jmx.remote.authenticate=false \
  -Djava.rmi.server.hostname=kafka-broker-1.example.com \
  -Dcom.sun.management.jmxremote \
  -Dcom.sun.management.jmxremote.port=9999 \
  -Dcom.sun.management.jmxremote.rmi.port=9999"
```

### Scenario 3 — Under-replicated partitions persistenti

**Sintomo:** Alert `KafkaUnderReplicatedPartitions > 0` persistente; `kafka_server_replica_manager_under_replicated_partitions` > 0 per più di qualche minuto.

**Causa:** Un broker è lento nel replicare (I/O disk saturo, GC pause lunghe, rete degradata) oppure un broker è down e le repliche non sono state riassegnate.

**Soluzione:** Identificare il broker problematico e verificare I/O e replica lag.

```bash
# Trovare le partizioni under-replicated
kafka-topics.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties \
  --describe --under-replicated-partitions

# Verificare lo stato di tutti i broker
kafka-broker-api-versions.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties

# Controllare il replica lag via JMX (ReplicaFetcherManager)
# Su ogni broker sospetto, verificare il valore di:
# kafka.server:type=ReplicaFetcherManager,name=MaxLag,clientId=Replica

# Riavviare il broker problematico se i log mostrano GC pause o I/O errors
journalctl -u kafka --since "1 hour ago" | grep -E "GC|IOException|TimeoutException"
```

### Scenario 4 — Metriche consumer lag mancanti in Prometheus

**Sintomo:** `kafka_consumergroup_lag` non è visibile in Prometheus nonostante Kafka Exporter sia up.

**Causa:** Il consumer group non è attivo (nessun consumer connesso in quel momento) oppure Kafka Exporter non ha i permessi ACL per leggere gli offset dei gruppi.

**Soluzione:** Verificare i permessi ACL e la connettività di Kafka Exporter verso il broker.

```bash
# Verificare che Kafka Exporter raggiunga il broker
curl -s http://kafka-exporter:9308/metrics | grep kafka_consumergroup

# Controllare i log di Kafka Exporter per errori di autenticazione
docker logs kafka-exporter 2>&1 | grep -E "error|WARN|auth|SASL"

# Aggiungere ACL per l'utente monitoring se mancanti
kafka-acls.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties \
  --add \
  --allow-principal User:monitoring \
  --operation Describe \
  --group '*'

# Verificare che almeno un consumer del gruppo sia attivo
kafka-consumer-groups.sh \
  --bootstrap-server kafka-broker-1:9092 \
  --command-config admin.properties \
  --list | grep order-processor
```

---

## Riferimenti

- [Documentazione ufficiale Kafka Monitoring](https://kafka.apache.org/documentation/#monitoring)
- [JMX Exporter](https://github.com/prometheus/jmx_exporter)
- [Kafka Exporter](https://github.com/danielqsj/kafka_exporter)
- [AKHQ](https://akhq.io/)
- [Grafana Dashboard per Kafka (ID 7589)](https://grafana.com/grafana/dashboards/7589)
- [Confluent Monitoring Guide](https://docs.confluent.io/platform/current/kafka/monitoring.html)
