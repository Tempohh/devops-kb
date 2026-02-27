---
title: "Kafka con Helm"
slug: helm
category: messaging
tags: [kafka, kubernetes, helm, bitnami, deploy]
search_keywords: [kafka helm chart, bitnami kafka, helm install kafka, kafka kubernetes deploy, helm values kafka, kafka helm produzione]
parent: messaging/kafka/kubernetes-cloud
related: [messaging/kafka/kubernetes-cloud/strimzi-operator, messaging/kafka/kubernetes-cloud/msk-aws, messaging/kafka/fondamenti/architettura]
official_docs: https://artifacthub.io/packages/helm/bitnami/kafka
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Kafka con Helm

## Panoramica

Helm è il package manager de facto per Kubernetes e permette di installare Kafka tramite chart preconfigurati, gestendo template di risorse Kubernetes complessi con valori personalizzabili. Il chart Bitnami Kafka è il più utilizzato per deploy Kafka su Kubernetes: mantiene aggiornato alle ultime versioni di Kafka, supporta sia la modalità KRaft (senza ZooKeeper) sia quella legacy con ZooKeeper, e offre un ampio set di parametri di configurazione. Rispetto all'approccio Strimzi Operator, Helm è più semplice da adottare inizialmente ma offre meno automazione operativa: rolling update, gestione utenti e rinnovo certificati richiedono più intervento manuale. Helm è indicato per ambienti di sviluppo, staging e produzione di media complessità dove non si vuole introdurre la dipendenza da un Operator.

!!! note "Helm vs Strimzi Operator"
    Per ambienti di produzione con requisiti stringenti di alta disponibilità e gestione automatizzata del ciclo di vita, valutare Strimzi Operator. Helm è ottimo per setup più semplici o quando si preferisce un approccio più controllato agli aggiornamenti.

---

## Concetti Chiave

### Chart Disponibili

| Chart | Maintainer | Link |
|-------|-----------|------|
| `bitnami/kafka` | VMware/Bitnami | https://artifacthub.io/packages/helm/bitnami/kafka |
| `strimzi/strimzi-kafka-operator` | Strimzi | https://artifacthub.io/packages/helm/strimzi/strimzi-kafka-operator |
| `kafka-ui/kafka-ui` | Provectus | Interfaccia web per gestione cluster |

### Struttura del Chart Bitnami

Il chart Bitnami crea automaticamente:
- **StatefulSet** per i broker Kafka
- **Service** headless e ClusterIP per comunicazione interna
- **PersistentVolumeClaim** per i dati
- **ConfigMap** con la configurazione `server.properties`
- **Secret** per credenziali (se autenticazione abilitata)
- **ServiceAccount**, **Role**, **RoleBinding** per RBAC

---

## Architettura / Come Funziona

```
┌──────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │            kafka Namespace                             │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │         StatefulSet: kafka-broker                │  │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │  │  │
│  │  │  │ broker-0 │  │ broker-1 │  │ broker-2 │      │  │  │
│  │  │  │  PVC:    │  │  PVC:    │  │  PVC:    │      │  │  │
│  │  │  │ 100Gi    │  │ 100Gi    │  │ 100Gi    │      │  │  │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘      │  │  │
│  │  └───────┼─────────────┼─────────────┼────────────┘  │  │
│  │          └─────────────┼─────────────┘               │  │
│  │                        │                             │  │
│  │    ┌───────────────────▼──────────────────────┐      │  │
│  │    │  Service: kafka-headless (ClusterIP None) │      │  │
│  │    │  Service: kafka (ClusterIP)               │      │  │
│  │    │  Service: kafka-external (LoadBalancer)   │      │  │
│  │    └──────────────────────────────────────────┘      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Configurazione & Pratica

### Aggiungere il Repository Bitnami

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Verifica versioni disponibili
helm search repo bitnami/kafka --versions | head -10
```

### Installazione Rapida (Development)

```bash
helm install kafka bitnami/kafka \
  --namespace kafka \
  --create-namespace \
  --set replicaCount=1 \
  --set kraft.enabled=true \
  --set persistence.size=10Gi
```

### values.yaml per Produzione

```yaml
# kafka-production-values.yaml

global:
  storageClass: "fast-ssd"

# Numero di broker
replicaCount: 3

# Modalità KRaft (senza ZooKeeper) — raccomandato
kraft:
  enabled: true

# Configurazione broker Kafka
heapOpts: "-Xmx4g -Xms4g"

config: |
  auto.create.topics.enable=false
  default.replication.factor=3
  offsets.topic.replication.factor=3
  transaction.state.log.replication.factor=3
  transaction.state.log.min.isr=2
  min.insync.replicas=2
  log.retention.hours=168
  log.segment.bytes=1073741824
  compression.type=lz4
  message.max.bytes=10485760
  replica.fetch.max.bytes=10485760

# Listeners
listeners:
  client:
    protocol: SASL_SSL
  interbroker:
    protocol: SASL_SSL
  external:
    protocol: SASL_SSL

# Autenticazione SASL/SCRAM
sasl:
  enabledMechanisms: "SCRAM-SHA-512"
  interBrokerMechanism: "SCRAM-SHA-512"
  client:
    users:
      - "admin"
      - "app-producer"
      - "app-consumer"
    passwords: ""  # Generare con: --set sasl.client.passwords="pass1,pass2,pass3"

# TLS
tls:
  enabled: true
  autoGenerated: true

# Storage persistente
persistence:
  enabled: true
  size: 100Gi
  storageClass: "fast-ssd"

# Risorse compute
resources:
  requests:
    memory: "4Gi"
    cpu: "1000m"
  limits:
    memory: "8Gi"
    cpu: "4000m"

# Anti-affinità: garantisce broker su nodi diversi
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
            - key: app.kubernetes.io/name
              operator: In
              values:
                - kafka
        topologyKey: kubernetes.io/hostname

# Tollerazioni per nodi dedicati
tolerations:
  - key: "kafka"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"

nodeSelector:
  kafka: "true"

# Metriche Prometheus
metrics:
  kafka:
    enabled: true
    serviceMonitor:
      enabled: true
      namespace: monitoring

# External access per client fuori dal cluster
externalAccess:
  enabled: true
  broker:
    service:
      type: LoadBalancer
      ports:
        external: 9094
      annotations:
        service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
        service.beta.kubernetes.io/aws-load-balancer-internal: "true"
  autoDiscovery:
    enabled: true
    image:
      registry: docker.io
      repository: bitnami/kubectl
      tag: latest

# Probe configuration
livenessProbe:
  enabled: true
  initialDelaySeconds: 60
  periodSeconds: 30
  failureThreshold: 6

readinessProbe:
  enabled: true
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 6

# Provisioning: topic e utenti creati automaticamente
provisioning:
  enabled: true
  topics:
    - name: ordini-v1
      partitions: 12
      replicationFactor: 3
      config:
        retention.ms: "604800000"
        cleanup.policy: "delete"
    - name: pagamenti-v1
      partitions: 6
      replicationFactor: 3
      config:
        retention.ms: "2592000000"
        cleanup.policy: "delete"
  users:
    - name: app-producer
      acls:
        - resource:
            type: topic
            name: ordini-v1
          operations: ["Write", "Describe"]
```

### Installazione con values personalizzato

```bash
helm install kafka bitnami/kafka \
  --namespace kafka \
  --create-namespace \
  --values kafka-production-values.yaml \
  --set sasl.client.passwords="adminPass,producerPass,consumerPass"

# Verifica lo stato
helm status kafka -n kafka
kubectl get pods -n kafka -w
```

### Upgrade con Helm

```bash
# Aggiorna il chart a una nuova versione
helm upgrade kafka bitnami/kafka \
  --namespace kafka \
  --values kafka-production-values.yaml \
  --set sasl.client.passwords="adminPass,producerPass,consumerPass" \
  --version 28.0.0

# Verifica la revisione corrente
helm history kafka -n kafka
```

### Rollback

```bash
# Rollback alla revisione precedente
helm rollback kafka -n kafka

# Rollback a una revisione specifica
helm rollback kafka 2 -n kafka
```

!!! warning "Rollback e dati persistenti"
    Il rollback di Helm ripristina la configurazione del chart ma non i dati nei PersistentVolume. Se l'upgrade ha causato incompatibilità nel formato dei dati, il rollback potrebbe non essere sufficiente. Testare sempre gli upgrade in un ambiente non produttivo.

### External Access: NodePort, LoadBalancer, Ingress

**NodePort (sviluppo/testing):**

```yaml
externalAccess:
  enabled: true
  broker:
    service:
      type: NodePort
      nodePorts:
        - 30092
        - 30093
        - 30094
```

**LoadBalancer con advertised listeners automatici:**

```bash
# Il chart configura automaticamente gli advertised.listeners
# con gli IP dei LoadBalancer creati
externalAccess:
  enabled: true
  broker:
    service:
      type: LoadBalancer
  autoDiscovery:
    enabled: true
```

**Ingress con NGINX (per protocolli basati su TCP):**

```yaml
# Configurare TCP passthrough in NGINX Ingress Controller
# Il traffico Kafka (TCP) non può passare per un Ingress HTTP standard
# Usare la ConfigMap tcp-services di NGINX Ingress

# configmap nginx-ingress-tcp-services
data:
  9092: "kafka/kafka:9092"
  9093: "kafka/kafka:9093"
```

### Connessione al cluster dopo l'installazione

```bash
# Recupera la password SASL
KAFKA_PASSWORD=$(kubectl get secret kafka-user-passwords \
  --namespace kafka \
  -o jsonpath='{.data.client-passwords}' | base64 -d | cut -d , -f 1)

# Test con kafka-console-producer dal pod
kubectl run kafka-client --restart=Never --image bitnami/kafka \
  --namespace kafka --command -- sleep infinity

kubectl exec -it kafka-client -n kafka -- bash

# Produce un messaggio di test
kafka-console-producer.sh \
  --bootstrap-server kafka.kafka.svc.cluster.local:9092 \
  --producer.config /tmp/client.properties \
  --topic test-topic
```

---

## Best Practices

- **Usare sempre un `values.yaml` versionato**: Non passare valori solo via `--set`. Il file `values.yaml` deve essere committato in Git e trattato come codice.
- **Separare le password dal values.yaml**: Usare `--set` per le password in fase di install/upgrade, oppure referenziare Secret Kubernetes esistenti.
- **Testare upgrade in staging**: Il chart Bitnami rilascia breaking changes nelle major version. Leggere sempre il CHANGELOG prima di upgrading.
- **KRaft in produzione**: Abilitare sempre `kraft.enabled=true` per nuovi cluster. ZooKeeper è deprecato.
- **Disabilitare `auto.create.topics.enable`**: In produzione i topic devono essere creati esplicitamente tramite provisioning o IaC.
- **Monitorare le `ServiceMonitor`**: Abilitare `metrics.kafka.serviceMonitor.enabled=true` per l'integrazione con Prometheus Operator.
- **Non usare Helm per gestire i topic dopo il deploy**: Usare invece gli script Kafka CLI, Terraform o Strimzi KafkaTopic CR se si migra a Strimzi.

---

## Troubleshooting

### Broker non si avvia (PVC non bound)

```bash
# Verifica lo stato dei PVC
kubectl get pvc -n kafka

# Se Pending, controlla la StorageClass
kubectl describe pvc kafka-kafka-0 -n kafka
kubectl get storageclass

# StorageClass "fast-ssd" deve esistere nel cluster
kubectl describe storageclass fast-ssd
```

### Errore autenticazione SASL

```bash
# Recupera le password configurate
kubectl get secret kafka-user-passwords -n kafka \
  -o jsonpath='{.data.client-passwords}' | base64 -d

# Verifica il file client.properties
cat /tmp/client.properties
# Deve contenere:
# security.protocol=SASL_SSL
# sasl.mechanism=SCRAM-SHA-512
# sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="..." password="...";
```

### Helm upgrade fallisce (StatefulSet immutabile)

```bash
# Alcuni campi del StatefulSet non possono essere modificati in-place
# Verificare l'errore
helm upgrade --dry-run kafka bitnami/kafka -n kafka --values values.yaml

# In caso di campi immutabili, potrebbe essere necessario:
# 1. Eliminare il StatefulSet mantenendo i PVC
kubectl delete statefulset kafka-kafka -n kafka --cascade=orphan
# 2. Rieseguire l'upgrade
helm upgrade kafka bitnami/kafka -n kafka --values values.yaml
```

---

## Riferimenti

- [Bitnami Kafka Chart su ArtifactHub](https://artifacthub.io/packages/helm/bitnami/kafka)
- [Bitnami Kafka Chart Parameters](https://github.com/bitnami/charts/tree/main/bitnami/kafka#parameters)
- [Helm Official Documentation](https://helm.sh/docs/)
- [Kafka External Access on Kubernetes](https://strimzi.io/blog/2019/04/17/accessing-kafka-part-1/)
