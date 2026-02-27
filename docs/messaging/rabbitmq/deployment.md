---
title: "Deployment e Operazioni"
slug: deployment
category: messaging
tags: [rabbitmq, kubernetes, deployment, operator, monitoring, prometheus, grafana, tls, production]
search_keywords: [rabbitmq kubernetes operator, rabbitmq cluster operator, rabbitmq topology operator, rabbitmq production config, rabbitmq tls, rabbitmq prometheus, rabbitmq grafana, rabbitmq.conf, rabbitmq docker, rabbitmq helm, amazon mq, rabbitmq vhost, rabbitmq ldap]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/clustering-ha, messaging/rabbitmq/affidabilita, security/pki-certificati/cert-manager]
official_docs: https://www.rabbitmq.com/kubernetes/operator/operator-overview
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Deployment e Operazioni

## RabbitMQ Cluster Operator per Kubernetes

Il **RabbitMQ Cluster Operator** è il modo raccomandato per deployare RabbitMQ su Kubernetes. È un Kubernetes Operator ufficiale sviluppato dal team RabbitMQ (VMware/Broadcom).

```
Architettura Cluster Operator

  Kubernetes Cluster
  ┌──────────────────────────────────────────────────┐
  │  Namespace: rabbitmq-system                       │
  │  ┌─────────────────────────┐                     │
  │  │  RabbitMQ Cluster       │                     │
  │  │  Operator               │ (controller)        │
  │  └─────────────────────────┘                     │
  │              │ watches/reconciles                 │
  │              ▼                                    │
  │  Namespace: production                            │
  │  ┌─────────────────────────┐                     │
  │  │  RabbitmqCluster CR     │ (custom resource)   │
  │  │  name: production       │                     │
  │  └─────────────────────────┘                     │
  │              │ crea e gestisce                    │
  │  ┌───────────┼───────────────────┐               │
  │  │           │                   │               │
  │  ▼           ▼                   ▼               │
  │  StatefulSet  Services          ConfigMap        │
  │  (3 pod)    (AMQP/Mgmt)         (rabbitmq.conf)  │
  └──────────────────────────────────────────────────┘
```

**Installazione:**

```bash
# Installa il Cluster Operator
kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"

# Verifica
kubectl get pods -n rabbitmq-system
# NAME                                         READY   STATUS    RESTARTS
# rabbitmq-cluster-operator-xxxxxxxxx-xxxxx    1/1     Running   0
```

**RabbitmqCluster — Configurazione Produzione:**

```yaml
# rabbitmq-production.yaml
apiVersion: rabbitmq.com/v1beta1
kind: RabbitmqCluster
metadata:
  name: production
  namespace: messaging
spec:
  replicas: 3

  image: rabbitmq:3.13-management-alpine

  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "4"
      memory: "4Gi"

  persistence:
    storageClassName: gp3
    storage: "50Gi"

  rabbitmq:
    # rabbitmq.conf aggiuntivo (merge con default dell'operator)
    additionalConfig: |
      # Cluster
      cluster_partition_handling = pause_minority

      # Memory
      vm_memory_high_watermark.relative = 0.4
      vm_memory_high_watermark_paging_ratio = 0.75
      disk_free_limit.relative = 1.5

      # Networking
      heartbeat = 60
      channel_max = 2000
      connection_max = 10000

      # Management
      management.load_definitions = /etc/rabbitmq/definitions.json

      # Logging
      log.file.level = info
      log.console.level = info
      log.console = true

    # Plugins abilitati
    additionalPlugins:
      - rabbitmq_peer_discovery_k8s
      - rabbitmq_prometheus
      - rabbitmq_shovel
      - rabbitmq_shovel_management
      - rabbitmq_federation
      - rabbitmq_federation_management

  service:
    type: ClusterIP
    # Per esposizione esterna: LoadBalancer o NodePort

  affinity:
    # Un pod RabbitMQ per nodo K8s (HA reale)
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - production
          topologyKey: kubernetes.io/hostname

  tolerations:
    - key: "rabbitmq"
      operator: "Equal"
      value: "true"
      effect: "NoSchedule"

  override:
    statefulSet:
      spec:
        template:
          spec:
            # Security context
            securityContext:
              runAsNonRoot: true
              runAsUser: 999
              fsGroup: 999
```

**Services creati dall'Operator:**

```bash
kubectl get services -n messaging
# NAME                    TYPE        CLUSTER-IP      PORT(S)
# production              ClusterIP   10.96.x.x       5672/TCP   ← AMQP
# production-nodes        ClusterIP   None            4369/TCP   ← Erlang peer discovery (headless)
# production-management   ClusterIP   10.96.x.x       15672/TCP  ← Management UI + API
# production-prometheus   ClusterIP   10.96.x.x       15692/TCP  ← Prometheus metrics
```

---

## RabbitMQ Topology Operator

Il **Topology Operator** gestisce le risorse AMQP (exchange, queue, binding, policy) come oggetti Kubernetes. Permette il GitOps completo della topologia RabbitMQ.

```bash
# Installa Topology Operator
kubectl apply -f "https://github.com/rabbitmq/messaging-topology-operator/releases/latest/download/messaging-topology-operator-with-certmanager.yml"
```

```yaml
# Dichiarazione risorse AMQP come CRD Kubernetes

---
apiVersion: rabbitmq.com/v1beta1
kind: Vhost
metadata:
  name: production-vhost
spec:
  name: /production
  rabbitmqClusterReference:
    name: production

---
apiVersion: rabbitmq.com/v1beta1
kind: Exchange
metadata:
  name: orders-exchange
spec:
  name: orders
  type: topic
  durable: true
  vhost: /production
  rabbitmqClusterReference:
    name: production

---
apiVersion: rabbitmq.com/v1beta1
kind: Queue
metadata:
  name: orders-eu-queue
spec:
  name: orders-eu
  durable: true
  vhost: /production
  arguments:
    x-queue-type: quorum
    x-delivery-limit: 5
    x-dead-letter-exchange: dlx
  rabbitmqClusterReference:
    name: production

---
apiVersion: rabbitmq.com/v1beta1
kind: Binding
metadata:
  name: orders-eu-binding
spec:
  source: orders
  destination: orders-eu
  destinationType: queue
  routingKey: "order.*.eu.#"
  vhost: /production
  rabbitmqClusterReference:
    name: production

---
apiVersion: rabbitmq.com/v1beta1
kind: User
metadata:
  name: app-user
spec:
  tags: []  # nessun tag = utente normale
  rabbitmqClusterReference:
    name: production
  # La password è generata automaticamente e salvata in un Secret K8s

---
apiVersion: rabbitmq.com/v1beta1
kind: Permission
metadata:
  name: app-user-permissions
spec:
  vhost: /production
  userReference:
    name: app-user
  permissions:
    write: "orders|events"  # regexp sui nomi di exchange/queue
    read: ".*"
    configure: ""           # non può dichiarare/cancellare risorse
  rabbitmqClusterReference:
    name: production
```

---

## Configurazione TLS

```yaml
# TLS con cert-manager — CRD RabbitmqCluster
apiVersion: rabbitmq.com/v1beta1
kind: RabbitmqCluster
metadata:
  name: production
spec:
  tls:
    secretName: rabbitmq-tls   # Secret con tls.crt + tls.key + ca.crt
    caSecretName: rabbitmq-ca-secret

  rabbitmq:
    additionalConfig: |
      listeners.ssl.default = 5671
      ssl_options.cacertfile = /etc/rabbitmq-tls/ca.crt
      ssl_options.certfile   = /etc/rabbitmq-tls/tls.crt
      ssl_options.keyfile    = /etc/rabbitmq-tls/tls.key
      ssl_options.verify     = verify_peer
      ssl_options.fail_if_no_peer_cert = true  # mTLS obbligatorio
      ssl_options.versions.1 = tlsv1.3
      ssl_options.versions.2 = tlsv1.2
      # Cipher suites sicure
      ssl_options.ciphers.1 = TLS_AES_256_GCM_SHA384
      ssl_options.ciphers.2 = TLS_CHACHA20_POLY1305_SHA256
      ssl_options.ciphers.3 = TLS_AES_128_GCM_SHA256
```

```yaml
# cert-manager Certificate per RabbitMQ
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: rabbitmq-tls
  namespace: messaging
spec:
  secretName: rabbitmq-tls
  issuerRef:
    name: internal-ca
    kind: ClusterIssuer
  commonName: production.messaging.svc.cluster.local
  dnsNames:
    - production.messaging.svc.cluster.local
    - production.messaging.svc
    - "*.production.messaging.svc.cluster.local"  # per i pod del StatefulSet
  duration: 8760h    # 1 anno
  renewBefore: 720h  # rinnova 30 giorni prima
```

---

## Monitoring con Prometheus e Grafana

RabbitMQ espone metriche native in formato Prometheus tramite il plugin `rabbitmq_prometheus`.

```yaml
# ServiceMonitor per Prometheus Operator
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: rabbitmq
  namespace: messaging
spec:
  selector:
    matchLabels:
      app.kubernetes.io/component: rabbitmq
  endpoints:
    - port: prometheus
      interval: 15s
      path: /metrics
      # Anche metriche per-object (queue individuali, exchange):
    - port: prometheus
      interval: 30s
      path: /metrics/per-object
```

**Alert Rules critiche:**

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: rabbitmq-alerts
  namespace: messaging
spec:
  groups:
    - name: rabbitmq
      rules:
        # Nodo giù
        - alert: RabbitMQNodeDown
          expr: rabbitmq_identity_info == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "RabbitMQ node {{ $labels.instance }} is down"

        # Queue con backlog alto
        - alert: RabbitMQHighQueueDepth
          expr: rabbitmq_queue_messages > 100000
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Queue {{ $labels.queue }} in vhost {{ $labels.vhost }} has {{ $value }} messages"

        # Consumer assenti su queue attiva
        - alert: RabbitMQNoConsumers
          expr: |
            rabbitmq_queue_messages > 0
            and
            rabbitmq_queue_consumers == 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Queue {{ $labels.queue }} has messages but no consumers"

        # Memory alarm (broker blocca i publisher)
        - alert: RabbitMQMemoryAlarm
          expr: rabbitmq_alarms_memory_used_watermark == 1
          for: 0m
          labels:
            severity: critical
          annotations:
            summary: "RabbitMQ memory alarm triggered on {{ $labels.instance }}"

        # Disk alarm
        - alert: RabbitMQDiskAlarm
          expr: rabbitmq_alarms_free_disk_space_watermark == 1
          for: 0m
          labels:
            severity: critical
          annotations:
            summary: "RabbitMQ disk alarm triggered on {{ $labels.instance }}"

        # Quorum queue non in quorum
        - alert: RabbitMQQuorumQueueNotMajority
          expr: |
            rabbitmq_quorum_queue_followers < (rabbitmq_quorum_queue_servers / 2)
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "Quorum queue {{ $labels.queue }} has lost quorum"

        # Connessioni bloccate (back pressure attiva)
        - alert: RabbitMQBlockedConnections
          expr: rabbitmq_connections_blocked > 0
          for: 2m
          labels:
            severity: warning
          annotations:
            summary: "{{ $value }} connections are blocked on {{ $labels.instance }}"

        # Consumer utilization bassa (consumer troppo lenti)
        - alert: RabbitMQLowConsumerUtilization
          expr: |
            rabbitmq_queue_consumer_utilisation < 0.5
            and rabbitmq_queue_messages > 1000
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Queue {{ $labels.queue }} consumer utilization is {{ $value | humanizePercentage }}"
```

**Dashboard Grafana:** L'ID `10991` su Grafana.com è il dashboard ufficiale RabbitMQ Overview. Importabile direttamente.

---

## Configurazione Production-Ready — rabbitmq.conf Completo

```ini
# /etc/rabbitmq/rabbitmq.conf

## Cluster
cluster_name = production-rabbitmq
cluster_partition_handling = pause_minority

## Networking
listeners.tcp.default = 5672
listeners.ssl.default = 5671
heartbeat = 60
channel_max = 2000
connection_max = 10000
tcp_listen_options.backlog = 4096
tcp_listen_options.recbuf  = 131072
tcp_listen_options.sndbuf  = 131072
tcp_listen_options.keepalive = true

## Memory Management
# Blocca publisher quando RabbitMQ usa il 40% della RAM
vm_memory_high_watermark.relative = 0.4
# Inizia a paginare su disco quando raggiunge il 75% del watermark
vm_memory_high_watermark_paging_ratio = 0.75

## Disk Management
# Blocca publisher se lo spazio libero scende sotto 1.5x la RAM installata
disk_free_limit.relative = 1.5

## Queue Settings
# Default per Classic Queues — preferire policy per Quorum
queue_index_embed_msgs_below = 4096  # msg < 4KB direttamente nell'index

## Management Plugin
management.tcp.port = 15672
management.load_definitions = /etc/rabbitmq/definitions.json
management.http_log_dir = /var/log/rabbitmq/management_access

## Prometheus
prometheus.tcp.port = 15692
prometheus.return_per_object_metrics = true

## Logging
log.file.level = info
log.console = true
log.console.level = info
log.connection.level = warning  # riduce il rumore da connect/disconnect

## Auth — LDAP (opzionale)
# auth_backends.1 = ldap
# auth_backends.2 = internal
# auth_ldap.servers.1 = ldap.internal.company.com
# auth_ldap.user_dn_pattern = cn=${username},ou=users,dc=company,dc=com
# auth_ldap.use_ssl = true
```

**Pre-load definitions (exchange/queue al boot):**

```json
// /etc/rabbitmq/definitions.json
{
  "vhosts": [
    {"name": "/production"}
  ],
  "users": [
    {
      "name": "app-user",
      "password_hash": "...",
      "hashing_algorithm": "rabbit_password_hashing_sha256",
      "tags": ""
    }
  ],
  "permissions": [
    {
      "user": "app-user",
      "vhost": "/production",
      "configure": "",
      "write": ".*",
      "read": ".*"
    }
  ],
  "exchanges": [
    {
      "name": "orders",
      "vhost": "/production",
      "type": "topic",
      "durable": true,
      "auto_delete": false,
      "arguments": {}
    }
  ],
  "queues": [
    {
      "name": "orders-eu",
      "vhost": "/production",
      "durable": true,
      "auto_delete": false,
      "arguments": {
        "x-queue-type": "quorum",
        "x-delivery-limit": 5
      }
    }
  ],
  "bindings": [
    {
      "source": "orders",
      "vhost": "/production",
      "destination": "orders-eu",
      "destination_type": "queue",
      "routing_key": "order.*.eu.#",
      "arguments": {}
    }
  ],
  "policies": [
    {
      "vhost": "/production",
      "name": "ha-quorum",
      "pattern": ".*",
      "apply-to": "queues",
      "definition": {"x-queue-type": "quorum"},
      "priority": 1
    }
  ]
}
```

---

## Amazon MQ — RabbitMQ Managed

Per chi preferisce evitare la gestione operativa del cluster, **Amazon MQ for RabbitMQ** è il servizio managed di AWS.

```bash
# Creazione cluster Amazon MQ (RabbitMQ) via CLI
aws mq create-broker \
    --broker-name production-rabbitmq \
    --engine-type RABBITMQ \
    --engine-version 3.13 \
    --deployment-mode CLUSTER_MULTI_AZ \
    --host-instance-type mq.m5.large \
    --publicly-accessible false \
    --subnet-ids subnet-xxx subnet-yyy subnet-zzz \
    --security-groups sg-xxx \
    --auto-minor-version-upgrade \
    --maintenance-window-start-time \
        DayOfWeek=SUNDAY,TimeOfDay=03:00,TimeZone=UTC \
    --logs General=true \
    --user Username=admin,Password=SecurePass123!
```

**Confronto Amazon MQ vs Self-managed:**

| | Amazon MQ | Self-managed K8s |
|---|---|---|
| **Overhead operativo** | Basso (patch, backup, HA automatici) | Alto |
| **Controllo** | Limitato (no plugin custom) | Totale |
| **Costo** | Alto per workload intensi | Più economico su larga scala |
| **Networking** | VPC, private endpoints | Kubernetes networking |
| **Plugin** | Solo plugin ufficiali supportati | Qualsiasi plugin |
| **Monitoring** | CloudWatch + dashboard base | Prometheus/Grafana completo |

---

## Operazioni Quotidiane

```bash
# Stato cluster
rabbitmq-diagnostics cluster_status
rabbitmq-diagnostics check_running
rabbitmq-diagnostics check_local_alarms   # memory/disk alarms

# Liste risorse
rabbitmqctl list_queues name messages consumers memory
rabbitmqctl list_exchanges name type durable
rabbitmqctl list_connections name state channels

# Gestione code
rabbitmqctl purge_queue orders-stale      # svuota una queue
rabbitmqctl delete_queue orders-old       # cancella una queue

# Gestione utenti
rabbitmqctl add_user new-service password
rabbitmqctl set_user_tags new-service monitoring
rabbitmqctl set_permissions -p /production new-service "" "orders|events" ".*"
rabbitmqctl list_user_permissions new-service

# Export/Import della configurazione
rabbitmqctl export_definitions /tmp/definitions-backup.json
rabbitmqctl import_definitions /tmp/definitions-backup.json

# Performance test (strumento ufficiale)
rabbitmq-perf-test \
    --uri amqp://user:pass@rabbitmq:5672 \
    --producers 10 \
    --consumers 10 \
    --queue-pattern "perf-test-%" \
    --queue-count 5 \
    --rate 1000 \
    --time 30
```

---

## Riferimenti

- [RabbitMQ Cluster Operator](https://www.rabbitmq.com/kubernetes/operator/operator-overview)
- [RabbitMQ Topology Operator](https://www.rabbitmq.com/kubernetes/operator/using-topology-operator)
- [Production Checklist](https://www.rabbitmq.com/docs/production-checklist)
- [Monitoring with Prometheus](https://www.rabbitmq.com/docs/prometheus)
- [TLS Support](https://www.rabbitmq.com/docs/ssl)
- [Amazon MQ for RabbitMQ](https://docs.aws.amazon.com/amazon-mq/latest/developer-guide/rabbitmq.html)
- [Configuration Reference](https://www.rabbitmq.com/docs/configure)
