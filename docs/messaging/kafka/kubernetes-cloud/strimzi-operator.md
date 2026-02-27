---
title: "Strimzi Operator"
slug: strimzi-operator
category: messaging
tags: [kafka, kubernetes, operator, strimzi, crds]
search_keywords: [strimzi, kafka operator, kubernetes kafka, kafka su k8s, KafkaTopic, KafkaUser, KafkaMirrorMaker2, KafkaConnect, operatore kafka, kafka cluster operator]
parent: messaging/kafka/kubernetes-cloud
related: [messaging/kafka/kubernetes-cloud/helm, messaging/kafka/sicurezza/ssl-tls, messaging/kafka/fondamenti/architettura]
official_docs: https://strimzi.io/documentation/
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Strimzi Operator

## Panoramica

Strimzi è un Kubernetes Operator open source che automatizza il deploy, la configurazione e la gestione di cluster Apache Kafka su Kubernetes. Implementa il pattern Operator tramite Custom Resource Definitions (CRD), permettendo di gestire Kafka con la stessa API dichiarativa di Kubernetes. Strimzi gestisce l'intero ciclo di vita del cluster: provisioning, configurazione TLS, gestione utenti e topic, rolling update, scaling e monitoraggio. Rispetto a un'installazione manuale di Kafka su Kubernetes, Strimzi riduce drasticamente la complessità operativa e garantisce che il cluster rimanga sempre in uno stato coerente con la configurazione dichiarata.

!!! tip "Perché Strimzi"
    Strimzi è il modo raccomandato per eseguire Kafka su Kubernetes in produzione. Gestisce automaticamente rolling update, rinnovo certificati TLS, rebalancing e failover, operazioni che richiederebbero script complessi se gestite manualmente.

---

## Concetti Chiave

### Custom Resource Definitions (CRD)

Strimzi estende l'API di Kubernetes con le seguenti risorse custom:

| CRD | Scopo |
|-----|-------|
| `Kafka` | Definisce un cluster Kafka completo (broker + ZooKeeper/KRaft) |
| `KafkaTopic` | Gestisce un singolo topic Kafka |
| `KafkaUser` | Gestisce un utente con credenziali e ACL |
| `KafkaConnect` | Deploy di un cluster Kafka Connect |
| `KafkaConnector` | Configura un singolo connector in un cluster KafkaConnect |
| `KafkaMirrorMaker2` | Replica topic tra cluster Kafka diversi |
| `KafkaBridge` | HTTP bridge per produrre/consumare senza client Kafka nativo |
| `KafkaRebalance` | Richiede un rebalancing delle partizioni tramite Cruise Control |

### Cluster Operator

Il Cluster Operator è il controller principale di Strimzi. Osserva le risorse `Kafka`, `KafkaConnect`, `KafkaMirrorMaker2` e crea le risorse Kubernetes corrispondenti: StatefulSet, Deployment, Service, ConfigMap, Secret, PersistentVolumeClaim.

### Entity Operator

Parte del cluster Strimzi, composto da:
- **Topic Operator**: sincronizza le risorse `KafkaTopic` con i topic reali nel cluster
- **User Operator**: sincronizza le risorse `KafkaUser` con gli utenti e le ACL nel cluster

---

## Architettura / Come Funziona

```
┌─────────────────────────────────────────────┐
│                  Kubernetes                  │
│                                             │
│  ┌──────────────┐    watches    ┌─────────┐ │
│  │ Cluster      │◄──────────────│ Kafka   │ │
│  │ Operator     │               │   CR    │ │
│  └──────┬───────┘               └─────────┘ │
│         │ creates/manages                    │
│         ▼                                   │
│  ┌──────────────────────────────────────┐   │
│  │  StatefulSet (Kafka Brokers)         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌────────┐ │   │
│  │  │Broker-0 │ │Broker-1 │ │Broker-2│ │   │
│  │  └─────────┘ └─────────┘ └────────┘ │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌──────────────┐    watches    ┌─────────┐ │
│  │ Entity       │◄──────────────│KafkaTopic│ │
│  │ Operator     │◄──────────────│KafkaUser │ │
│  └──────────────┘               └─────────┘ │
└─────────────────────────────────────────────┘
```

### Flusso di riconciliazione

1. L'utente applica una CR (es. `Kafka`) con `kubectl apply`
2. Il Cluster Operator rileva il cambiamento tramite informer
3. Calcola le differenze rispetto allo stato attuale
4. Applica i cambiamenti in modo sicuro (rolling update se necessario)
5. Aggiorna lo `status` della CR con lo stato corrente

---

## Configurazione & Pratica

### Installazione con kubectl

```bash
# Installa Strimzi (sostituire VERSION con l'ultima stabile)
kubectl create namespace kafka
kubectl apply -f "https://strimzi.io/install/latest?namespace=kafka" -n kafka

# Verifica che il Cluster Operator sia avviato
kubectl get pods -n kafka -w
```

### Installazione con Helm

```bash
helm repo add strimzi https://strimzi.io/charts/
helm repo update

helm install strimzi-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --set watchNamespaces="{kafka,kafka-dev}" \
  --version 0.43.0
```

### CR Kafka — Cluster Completo (KRaft + TLS + Storage Persistente)

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: production-cluster
  namespace: kafka
spec:
  kafka:
    version: 3.7.0
    metadataVersion: "3.7"  # KRaft mode
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
        authentication:
          type: tls
      - name: external
        port: 9094
        type: loadbalancer
        tls: true
        authentication:
          type: tls
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
      inter.broker.protocol.version: "3.7"
      log.retention.hours: 168
      log.segment.bytes: 1073741824
      log.retention.check.interval.ms: 300000
    storage:
      type: jbod
      volumes:
        - id: 0
          type: persistent-claim
          size: 100Gi
          class: fast-ssd
          deleteClaim: false
    resources:
      requests:
        memory: 4Gi
        cpu: "1"
      limits:
        memory: 8Gi
        cpu: "4"
    jvmOptions:
      -Xms: 2g
      -Xmx: 6g
    template:
      pod:
        affinity:
          podAntiAffinity:
            requiredDuringSchedulingIgnoredDuringExecution:
              - labelSelector:
                  matchExpressions:
                    - key: strimzi.io/name
                      operator: In
                      values:
                        - production-cluster-kafka
                topologyKey: kubernetes.io/hostname
        tolerations:
          - key: "kafka"
            operator: "Equal"
            value: "true"
            effect: "NoSchedule"
  entityOperator:
    topicOperator:
      resources:
        requests:
          memory: 256Mi
          cpu: "100m"
        limits:
          memory: 512Mi
          cpu: "500m"
    userOperator:
      resources:
        requests:
          memory: 256Mi
          cpu: "100m"
        limits:
          memory: 512Mi
          cpu: "500m"
```

!!! warning "ZooKeeper vs KRaft"
    Da Kafka 3.3+ è disponibile la modalità KRaft (senza ZooKeeper). Strimzi supporta KRaft da v0.37. Per nuovi cluster usare sempre KRaft. La migrazione da ZooKeeper a KRaft richiede una procedura specifica documentata da Strimzi.

### CR KafkaTopic

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: ordini-v1
  namespace: kafka
  labels:
    strimzi.io/cluster: production-cluster  # Nome del cluster Kafka
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: "604800000"       # 7 giorni
    segment.bytes: "1073741824"     # 1 GB
    compression.type: lz4
    cleanup.policy: delete
    min.insync.replicas: "2"
```

### CR KafkaUser con ACL

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaUser
metadata:
  name: order-service
  namespace: kafka
  labels:
    strimzi.io/cluster: production-cluster
spec:
  authentication:
    type: tls                         # Autenticazione via certificato TLS
  authorization:
    type: simple
    acls:
      # Produttore: può scrivere su ordini-v1
      - resource:
          type: topic
          name: ordini-v1
          patternType: literal
        operations: [Write, Describe, Create]
        host: "*"
      # Consumatore: può leggere da ordini-v1 con consumer group
      - resource:
          type: topic
          name: ordini-v1
          patternType: literal
        operations: [Read, Describe]
        host: "*"
      - resource:
          type: group
          name: order-service-group
          patternType: literal
        operations: [Read]
        host: "*"
```

Dopo la creazione, Strimzi genera automaticamente un `Secret` con il certificato TLS client:

```bash
# Estrai il certificato utente
kubectl get secret order-service -n kafka -o jsonpath='{.data.user\.crt}' | base64 -d > user.crt
kubectl get secret order-service -n kafka -o jsonpath='{.data.user\.key}' | base64 -d > user.key
kubectl get secret production-cluster-cluster-ca-cert -n kafka \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > ca.crt
```

### Monitoraggio con Prometheus e Grafana

```yaml
# PodMonitor per Kafka brokers
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: kafka-brokers
  namespace: kafka
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      strimzi.io/kind: Kafka
  podMetricsEndpoints:
    - path: /metrics
      port: tcp-prometheus

---
# Aggiungere al CR Kafka per abilitare l'esportazione metriche
spec:
  kafka:
    metricsConfig:
      type: jmxPrometheusExporter
      valueFrom:
        configMapKeyRef:
          name: kafka-metrics
          key: kafka-metrics-config.yml
```

```yaml
# ConfigMap con configurazione metriche JMX
apiVersion: v1
kind: ConfigMap
metadata:
  name: kafka-metrics
  namespace: kafka
data:
  kafka-metrics-config.yml: |
    lowercaseOutputName: true
    rules:
      - pattern: kafka.server<type=(.+), name=(.+), clientId=(.+), topic=(.+), partition=(.*)><>Value
        name: kafka_server_$1_$2
        type: GAUGE
        labels:
          clientId: "$3"
          topic: "$4"
          partition: "$5"
      - pattern: kafka.server<type=(.+), name=(.+), clientId=(.+), brokerHost=(.+), brokerPort=(.+)><>Value
        name: kafka_server_$1_$2
        type: GAUGE
        labels:
          clientId: "$3"
          broker: "$4:$5"
      - pattern: kafka.server<type=(.+), name=(.+)><>OneMinuteRate
        name: kafka_server_$1_$2_rate1m
        type: GAUGE
```

---

## Best Practices

- **Anti-affinità obbligatoria**: Configurare sempre `podAntiAffinity` con `requiredDuringScheduling` per garantire che i broker siano su nodi distinti. Un nodo down non deve portare a perdita di quorum.
- **Dedicare nodi a Kafka**: Usare `tolerations` e `nodeSelector` per riservare nodi specifici ai broker, evitando la contesa di risorse.
- **Storage separato per log**: Usare JBOD con volumi dedicati, preferibilmente SSD NVMe. Non usare storage condiviso (NFS).
- **Replication factor 3, min.insync.replicas 2**: Configurazione standard per alta disponibilità. Mai impostare `min.insync.replicas` uguale al replication factor.
- **Gestire i topic solo tramite CR**: Non creare topic manualmente con `kafka-topics.sh` su cluster gestiti da Strimzi. Il Topic Operator li sovrascriverà o creerà inconsistenze.
- **Versioning dei certificati**: Strimzi rinnova automaticamente i certificati TLS. Configurare `renewalPercentage` per controllare quando avviene il rinnovo.
- **Cruise Control per rebalancing**: Abilitare Cruise Control nel CR `Kafka` per gestire il rebalancing automatico delle partizioni dopo aggiunta/rimozione di broker.

!!! warning "Modifica del numero di partizioni"
    Il numero di partizioni di un topic può solo aumentare, mai diminuire. Pianificare il numero di partizioni iniziale considerando il parallelismo massimo previsto dei consumer.

---

## Troubleshooting

### Broker in stato NotReady

```bash
# Controlla gli eventi del pod
kubectl describe pod production-cluster-kafka-0 -n kafka

# Controlla i log del broker
kubectl logs production-cluster-kafka-0 -n kafka --previous

# Controlla lo stato della CR
kubectl get kafka production-cluster -n kafka -o jsonpath='{.status.conditions}'
```

### Topic Operator non sincronizza il topic

```bash
# Controlla i log dell'Entity Operator
kubectl logs -n kafka \
  $(kubectl get pod -n kafka -l strimzi.io/name=production-cluster-entity-operator -o name) \
  -c topic-operator

# Verifica che il topic abbia la label corretta
kubectl get kafkatopic ordini-v1 -n kafka -o yaml | grep strimzi.io/cluster
```

### Rolling update bloccato

```bash
# Strimzi blocca i rolling update se il cluster non è in stato sano
# Verificare la presenza di under-replicated partitions
kubectl exec -it production-cluster-kafka-0 -n kafka -- \
  kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --under-replicated-partitions

# Forzare la riconciliazione della CR
kubectl annotate kafka production-cluster -n kafka \
  strimzi.io/manual-rolling-update=true --overwrite
```

### Certificato TLS scaduto

```bash
# Verificare la scadenza del CA certificate
kubectl get secret production-cluster-cluster-ca-cert -n kafka \
  -o jsonpath='{.data.ca\.crt}' | base64 -d | openssl x509 -noout -dates

# Forzare il rinnovo del CA certificate
kubectl annotate secret production-cluster-cluster-ca \
  strimzi.io/force-renew=true -n kafka --overwrite
```

---

## Riferimenti

- [Documentazione ufficiale Strimzi](https://strimzi.io/documentation/)
- [Strimzi GitHub Repository](https://github.com/strimzi/strimzi-kafka-operator)
- [Strimzi Blog — KRaft migration guide](https://strimzi.io/blog/)
- [Strimzi Grafana Dashboards](https://github.com/strimzi/strimzi-kafka-operator/tree/main/examples/metrics)
- [Cruise Control Integration](https://strimzi.io/docs/operators/latest/deploying.html#cruise-control-concepts-str)
