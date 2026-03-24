---
title: "Kubernetes Autoscaling"
slug: autoscaling
category: containers
tags: [kubernetes, autoscaling, hpa, vpa, keda, cluster-autoscaler, scaling]
search_keywords: [horizontal pod autoscaler, vertical pod autoscaler, KEDA, cluster autoscaler, custom metrics, event-driven scaling, scale-to-zero, metrics server, prometheus adapter, resource scaling, pod scaling, node scaling, autoscaler k8s]
parent: containers/kubernetes/_index
related: [containers/kubernetes/workloads, containers/kubernetes/scheduling-avanzato, containers/kubernetes/resource-management, monitoring/tools/prometheus]
official_docs: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
status: complete
difficulty: advanced
last_updated: 2026-03-24
---

# Kubernetes Autoscaling

## Panoramica

Kubernetes offre quattro meccanismi principali di autoscaling che operano su livelli diversi: **HPA** (Horizontal Pod Autoscaler) scala il numero di repliche di un pod, **VPA** (Vertical Pod Autoscaler) regola le risorse CPU/memory di un pod, **KEDA** estende l'HPA con trigger event-driven e scale-to-zero, e il **Cluster Autoscaler** gestisce il numero di nodi del cluster. Questi sistemi sono complementari e spesso usati insieme in produzione. L'autoscaling è abilitato dal Metrics Server (metriche di base) o da adattatori custom come il Prometheus Adapter (metriche applicative).

---

## Concetti Chiave

!!! note "Metrics Server"
    Il [Metrics Server](https://github.com/kubernetes-sigs/metrics-server) è il componente che raccoglie le metriche di utilizzo CPU/memory dai kubelet. È un prerequisito per HPA e VPA basati su metriche di risorse. Va installato separatamente dalla maggior parte delle distribuzioni (non incluso nel cluster vanilla).

!!! note "Tipi di metriche per HPA"
    - **Resource metrics** — CPU e memory dei container (via Metrics Server), fonte `metrics.k8s.io`
    - **Custom metrics** — metriche applicative (es. RPS, queue depth), fonte `custom.metrics.k8s.io` (via Prometheus Adapter)
    - **External metrics** — metriche esterne al cluster (es. lunghezza coda SQS), fonte `external.metrics.k8s.io`

!!! warning "HPA e VPA non vanno combinati sulle stesse risorse"
    HPA e VPA non devono scalare entrambi CPU/memory sullo stesso workload: generano conflitti. VPA va usato in modalità `Off` o `Initial` se HPA controlla lo stesso deployment, oppure si usano su risorse diverse (es. VPA su memory, HPA su custom metric).

---

## Architettura / Come Funziona

### Flusso HPA

```
┌─────────────────────────────────────────────────────────┐
│  HPA Control Loop (ogni 15s default)                    │
│                                                         │
│  1. Legge metrica corrente (Metrics API)                │
│  2. Calcola desiredReplicas:                            │
│     desiredReplicas = ceil(currentReplicas *            │
│                       (currentMetric / desiredMetric))  │
│  3. Applica min/max replicas bounds                     │
│  4. Applica stabilization window (scale-down: 5m)       │
│  5. Aggiorna spec.replicas del Deployment               │
└─────────────────────────────────────────────────────────┘
```

### Stack completo per custom metrics

```
Applicazione → Prometheus (scrape) → Prometheus Adapter
                                          ↓
                              custom.metrics.k8s.io API
                                          ↓
                                    HPA Controller
```

### Cluster Autoscaler

Il Cluster Autoscaler monitora i pod in stato `Pending` (non schedulabili per mancanza di risorse) e i nodi sottoutilizzati. Opera su node groups del cloud provider (AWS ASG, GCP MIG, Azure VMSS).

```
Pod Pending → CA verifica se nuovo nodo risolverebbe il problema
           → Richiede scale-up al cloud provider
           → Nodo viene aggiunto al cluster

Nodo <50% utilizzo per 10m → CA verifica se i pod possono migrare
                           → Evicts i pod (rispettando PDB)
                           → Nodo rimosso dal cluster
```

---

## Configurazione & Pratica

### Metrics Server — Installazione

```bash
# Helm
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm upgrade --install metrics-server metrics-server/metrics-server \
  --namespace kube-system

# Verifica
kubectl top nodes
kubectl top pods -A
```

### HPA — Basato su CPU

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-app-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70   # target 70% del CPU request
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # aspetta 5m prima di fare scale-down
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60              # max -10% ogni 60s
    scaleUp:
      stabilizationWindowSeconds: 0    # reagisce immediatamente allo scale-up
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15              # raddoppia ogni 15s se necessario
      - type: Pods
        value: 4
        periodSeconds: 15              # max +4 pod ogni 15s
      selectPolicy: Max                # usa il valore più alto tra le policy
```

### HPA — Basato su custom metric (RPS da Prometheus)

```yaml
# Prima: installare prometheus-adapter con la regola di mapping
# prometheus-adapter/values.yaml (excerpt)
rules:
  custom:
  - seriesQuery: 'http_requests_total{namespace!="",pod!=""}'
    resources:
      overrides:
        namespace: {resource: "namespace"}
        pod: {resource: "pod"}
    name:
      matches: "^(.*)"
      as: "http_requests_per_second"
    metricsQuery: 'rate(http_requests_total{<<.LabelMatchers>>}[2m])'
```

```yaml
# HPA che usa la custom metric
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-app-rps-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  minReplicas: 2
  maxReplicas: 50
  metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"    # target: 100 RPS per pod
```

### VPA — Vertical Pod Autoscaler

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: web-app-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  updatePolicy:
    updateMode: "Auto"    # Auto | Initial | Recreate | Off
    # Auto: evict e ricrea pod con nuove risorse
    # Initial: applica solo ai nuovi pod
    # Off: solo raccomandazioni, nessuna modifica automatica
  resourcePolicy:
    containerPolicies:
    - containerName: web-app
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: 4
        memory: 4Gi
      controlledResources: ["cpu", "memory"]
```

```bash
# Verificare le raccomandazioni VPA
kubectl describe vpa web-app-vpa
# Campo "Recommendation" mostra: Lower Bound, Target, Upper Bound
```

!!! tip "VPA con HPA — Configurazione compatibile"
    Per usare VPA e HPA sullo stesso deployment senza conflitti:
    ```yaml
    # VPA controlla solo memory
    resourcePolicy:
      containerPolicies:
      - containerName: app
        controlledResources: ["memory"]
    # HPA scala su CPU o custom metric (non memory)
    ```

### KEDA — Event-Driven Autoscaling

KEDA estende l'HPA con 50+ scalers (Kafka, RabbitMQ, Redis, AWS SQS, Cron, HTTP, Prometheus, ecc.) e supporta lo **scale-to-zero** (minReplicas: 0).

```bash
# Installazione
helm repo add kedacore https://kedacore.github.io/charts
helm upgrade --install keda kedacore/keda --namespace keda --create-namespace
```

```yaml
# ScaledObject — scaling su coda Kafka
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: kafka-consumer-scaler
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: kafka-consumer
  minReplicaCount: 0      # scale-to-zero quando la coda è vuota
  maxReplicaCount: 30
  cooldownPeriod: 300     # secondi prima di scale-to-zero
  pollingInterval: 30     # frequenza check metrica
  triggers:
  - type: kafka
    metadata:
      bootstrapServers: kafka-broker:9092
      consumerGroup: my-consumer-group
      topic: events-topic
      lagThreshold: "100"   # 1 replica ogni 100 messaggi in lag
      activationLagThreshold: "5"  # scala da 0 a 1 quando lag > 5
```

```yaml
# ScaledObject — scaling su metrica Prometheus
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: prometheus-scaler
spec:
  scaleTargetRef:
    name: worker-deployment
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-operated.monitoring:9090
      metricName: active_jobs
      threshold: "10"
      query: sum(active_jobs{namespace="production"})
```

```yaml
# ScaledJob — per job batch (non Deployment)
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: report-generator
spec:
  jobTargetRef:
    template:
      spec:
        containers:
        - name: report
          image: report-generator:latest
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
  - type: rabbitmq
    metadata:
      host: amqp://rabbitmq.production:5672
      queueName: reports
      queueLength: "1"    # 1 job per messaggio in coda
```

### Cluster Autoscaler — AWS EKS

```yaml
# Helm values (cluster-autoscaler)
autoDiscovery:
  clusterName: my-production-cluster
awsRegion: eu-west-1

extraArgs:
  scale-down-delay-after-add: 10m
  scale-down-unneeded-time: 10m
  scale-down-utilization-threshold: "0.5"
  skip-nodes-with-local-storage: "false"
  skip-nodes-with-system-pods: "true"
  balance-similar-node-groups: "true"   # bilancia pod tra node groups simili
  expander: least-waste                 # scegli node group che spreca meno risorse

rbac:
  create: true
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/ClusterAutoscalerRole
```

```yaml
# Annotazione su node group per CA
# Aggiungere sui nodi (gestito da ASG tags in AWS):
cluster-autoscaler.kubernetes.io/safe-to-evict: "true"
```

!!! warning "PodDisruptionBudget con Cluster Autoscaler"
    Il CA rispetta i PDB durante il drain dei nodi. Se un PDB blocca l'eviction, il nodo non viene rimosso. Assicurarsi che i PDB permettano almeno 1 pod indisponibile per ogni deployment critico:
    ```yaml
    apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: web-app-pdb
    spec:
      minAvailable: "50%"  # non usare minAvailable: 100%
      selector:
        matchLabels:
          app: web-app
    ```

---

## Best Practices

**Requests accurate — prerequisito fondamentale**
- HPA usa la percentuale di utilizzo rispetto ai `requests`. Se requests è troppo basso → HPA scala troppo tardi; se troppo alto → scala troppo presto.
- Usare VPA in modalità `Off` qualche settimana per ottenere raccomandazioni, poi impostare requests realistici.

**Stabilization window per evitare flapping**
- Scale-down aggressivo causa thrashing (su/giù continuo). Usare `stabilizationWindowSeconds: 300` per scale-down.
- Scale-up deve essere rapido: `stabilizationWindowSeconds: 0`.

**minReplicas ≥ 2 per alta disponibilità**
- Con `minReplicas: 1` il pod è un SPOF durante node drain o aggiornamenti.
- Eccezione: workload KEDA con scale-to-zero accettabile (es. job batch, consumer non critici).

**KEDA per workload event-driven**
- Preferire KEDA a HPA custom quando il driver dello scaling è una coda, un topic, o un evento esterno.
- KEDA gestisce automaticamente il fallback a HPA nativo e supporta scale-to-zero nativamente.

**Cluster Autoscaler + node groups specializzati**
- Configurare node groups separati per workload diversi (general-purpose, GPU, memory-optimized).
- Usare `nodeSelector` o `nodeAffinity` per garantire che KEDA/HPA scale sul node group corretto.

**Evitare conflitti HPA + VPA**
- Non lasciare che VPA in modalità `Auto` controli le stesse risorse che HPA usa come metrica.
- Pattern sicuro: VPA su `memory` + HPA su `cpu` o custom metric.

---

## Troubleshooting

**HPA bloccato a minReplicas / non scala**
```bash
# Verificare stato HPA
kubectl describe hpa web-app-hpa

# Errori comuni:
# "unable to get metrics for resource cpu" → Metrics Server non installato/funzionante
# "missing request for cpu" → Il container non ha requests definiti (OBBLIGATORIO)
# "invalid metrics (0 invalid out of 1)"  → Regola Prometheus Adapter errata

# Verificare Metrics Server
kubectl get deployment metrics-server -n kube-system
kubectl top pods -n production
```

**HPA scala ma non raggiunge il valore atteso**
```bash
# Calcolo manuale per debug
kubectl get hpa web-app-hpa -o yaml
# Verificare: status.currentMetrics vs spec.metrics[].target
# Verificare: status.conditions (ScalingLimited = MaxReplicas raggiunto)
```

**VPA rimuove risorse invece di aumentarle**
```bash
# Vedere raccomandazioni correnti
kubectl get vpa web-app-vpa -o jsonpath='{.status.recommendation}'

# Se VPA evict loop → controllare minAllowed/maxAllowed troppo stretti
# Se VPA non aggiorna → verificare che admission webhook sia attivo
kubectl get pods -n kube-system | grep vpa
```

**KEDA non scala**
```bash
# Stato ScaledObject
kubectl describe scaledobject kafka-consumer-scaler

# Verificare trigger (es. connettività Kafka)
kubectl logs -n keda deployment/keda-operator | grep kafka-consumer-scaler

# Metriche KEDA esposte come external metrics
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1" | jq .
```

**Cluster Autoscaler non aggiunge nodi**
```bash
# Log CA
kubectl logs -n kube-system deployment/cluster-autoscaler | grep "scale up"

# Errori comuni:
# "pod didn't trigger scale-up" → Pod è schedulabile su nodo esistente
# "node group min size reached" → ASG min size = current nodes
# "waiting for initial delay" → scale-down-delay-after-add non ancora scaduto
# Verificare che i pod Pending abbiano tollerazioni corrette per i node groups
```

---

## Relazioni

??? info "Workloads — Deployment e ReplicaSet"
    HPA e VPA operano su oggetti Workload (Deployment, StatefulSet, ecc.). La configurazione di replicas nel Deployment viene gestita automaticamente dall'HPA.

    **Approfondimento completo →** [Kubernetes Workloads](./workloads.md)

??? info "Scheduling Avanzato — Node Affinity e Taints"
    Il Cluster Autoscaler scala i nodi tenendo conto di node affinity, taints e tollerazioni. Un pod con requisiti di scheduling molto selettivi può impedire al CA di trovare un nodo idoneo.

    **Approfondimento completo →** [Scheduling Avanzato](./scheduling-avanzato.md)

??? info "Prometheus — Metriche custom per HPA"
    Il Prometheus Adapter traduce le metriche Prometheus nell'API `custom.metrics.k8s.io` consumata dall'HPA. KEDA usa direttamente il server Prometheus come trigger.

    **Approfondimento completo →** [Prometheus](../../monitoring/tools/prometheus.md)

---

## Riferimenti

- [HPA — Documentazione ufficiale](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [VPA — GitHub](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [KEDA — Documentazione ufficiale](https://keda.sh/docs/)
- [Cluster Autoscaler — GitHub](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)
- [Prometheus Adapter](https://github.com/kubernetes-sigs/prometheus-adapter)
- [KEDA Scalers Catalog](https://keda.sh/docs/latest/scalers/)
