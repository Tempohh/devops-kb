---
title: "Scheduling Avanzato"
slug: scheduling-avanzato
category: containers
tags: [kubernetes, scheduling, hpa, vpa, keda, affinity, taints, tolerations, priorityclass, resource-quota, limitrange]
search_keywords: [kubernetes HPA, kubernetes VPA, KEDA kubernetes, pod affinity kubernetes, node affinity kubernetes, taints tolerations kubernetes, PriorityClass kubernetes, resource quota kubernetes, LimitRange kubernetes, kubernetes autoscaling, topologySpreadConstraints, descheduler kubernetes, cluster autoscaler]
parent: containers/kubernetes/_index
related: [containers/kubernetes/workloads, containers/kubernetes/architettura]
official_docs: https://kubernetes.io/docs/concepts/scheduling-eviction/
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Scheduling Avanzato

## Resource Requests e Limits — La Base dello Scheduling

```
Resource Model Kubernetes

  Node Allocatable:
  +---------------------------------+
  | Node Capacity                    |
  |   CPU: 8 cores, RAM: 32GB       |
  | - kube-reserved: 0.5c, 1GB      |
  | - system-reserved: 0.5c, 1GB    |
  | = ALLOCATABLE: 7c, 30GB         |
  +---------------------------------+

  Pod Scheduling Decision:
  scheduler somma le REQUESTS di tutti i pod sul nodo
  Se sum(requests) > allocatable → nodo non candidato

  CPU:
  Request → garantita dallo scheduler (CPU shares in cgroups)
  Limit   → throttling tramite CFS (Completely Fair Scheduler)
           Il processo non viene ucciso, solo rallentato

  Memory:
  Request → garantita dallo scheduler
  Limit   → OOM kill se superato (il kernel uccide il processo)

  Esempio con un container cpu request=250m, limit=1000m:
  cgroups: cpu.shares = 256 (250m = 25% di un core = 256/1024 shares)
           cpu.cfs_quota_us = 100000 (1 core = 100ms per 100ms period)
```

**ResourceQuota — Limiti per Namespace:**

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    # Compute
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    # Oggetti
    pods: "100"
    services: "20"
    services.nodeports: "0"         # vieta NodePort
    services.loadbalancers: "5"
    persistentvolumeclaims: "20"
    requests.storage: 1Ti
    # Storage per StorageClass
    gp3.storageclass.storage.k8s.io/requests.storage: 500Gi
    # Conteggio per tipo
    count/deployments.apps: "50"
    count/jobs.batch: "100"
```

**LimitRange — Default e Bound per Container:**

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
    - type: Container
      default:         # limits di default se non specificati
        cpu: "500m"
        memory: "256Mi"
      defaultRequest:  # requests di default
        cpu: "100m"
        memory: "128Mi"
      max:             # massimo consentito
        cpu: "4"
        memory: "4Gi"
      min:             # minimo consentito
        cpu: "50m"
        memory: "64Mi"
    - type: PersistentVolumeClaim
      max:
        storage: 100Gi
      min:
        storage: 1Gi
```

---

## Node Affinity e NodeSelector

```yaml
spec:
  # ── NodeSelector (semplice, deprecato in favore di affinity) ──
  nodeSelector:
    kubernetes.io/arch: amd64
    node-type: compute

  # ── Node Affinity (flessibile) ───────────────────────────────
  affinity:
    nodeAffinity:
      # HARD: il pod NON viene schedulato se non soddisfatta
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: [eu-west-1a, eu-west-1b]
              - key: kubernetes.io/arch
                operator: In
                values: [amd64]
              - key: gpu
                operator: DoesNotExist  # nodi senza GPU

      # SOFT: preferito ma non obbligatorio
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100     # peso nel scoring (1-100)
          preference:
            matchExpressions:
              - key: node-type
                operator: In
                values: [compute-optimized]
        - weight: 50
          preference:
            matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: [eu-west-1a]  # prefer prima AZ
```

---

## Pod Affinity e Anti-Affinity

```yaml
spec:
  affinity:
    # ── Pod Anti-Affinity: spread su nodi diversi ────────────
    podAntiAffinity:
      # HARD: non schedula se c'è già un pod con app=api sul NODO
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels:
              app: api
          topologyKey: kubernetes.io/hostname  # uno per nodo

      # SOFT: preferisce non stare nella stessa AZ
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 50
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app: api
            topologyKey: topology.kubernetes.io/zone

    # ── Pod Affinity: co-locate con cache ────────────────────
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app: redis-cache
            topologyKey: kubernetes.io/hostname  # stessa VM di Redis
```

---

## Topology Spread Constraints

Più flessibile dell'anti-affinity: distribuisce i pod uniformemente attraverso zone/nodi.

```yaml
spec:
  topologySpreadConstraints:
    # Distribuisce uniformemente per AZ (max 1 pod di differenza)
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule   # FailTolerate | ScheduleAnyway
      labelSelector:
        matchLabels:
          app: api
      matchLabelKeys:
        - pod-template-hash              # considera solo i pod dello stesso RS
      minDomains: 3                      # richiede almeno 3 AZ disponibili

    # Distribuisce per nodo (max 2 pod per nodo)
    - maxSkew: 2
      topologyKey: kubernetes.io/hostname
      whenUnsatisfiable: ScheduleAnyway # preferenza, non hard constraint
      labelSelector:
        matchLabels:
          app: api
```

---

## Taints e Tolerations

I **taint** "macchiano" un nodo per impedire scheduling. Le **toleration** permettono a specifici pod di ignorare i taint.

```bash
# Taint un nodo (es. dedicato a GPU workloads)
kubectl taint nodes gpu-node-1 dedicated=gpu:NoSchedule
kubectl taint nodes gpu-node-1 dedicated=gpu:NoExecute     # evicts existing pods
kubectl taint nodes gpu-node-1 dedicated=gpu:PreferNoSchedule  # soft

# Rimuovi un taint
kubectl taint nodes gpu-node-1 dedicated=gpu:NoSchedule-
```

```yaml
spec:
  tolerations:
    # Tolera il taint specifico (key+value+effect)
    - key: dedicated
      operator: Equal
      value: gpu
      effect: NoSchedule

    # Tolera qualsiasi valore per questa key
    - key: dedicated
      operator: Exists
      effect: NoSchedule

    # Tolera node not-ready per 300s (eviction delay)
    - key: node.kubernetes.io/not-ready
      operator: Exists
      effect: NoExecute
      tolerationSeconds: 300

    # Tolera unreachable per 300s
    - key: node.kubernetes.io/unreachable
      operator: Exists
      effect: NoExecute
      tolerationSeconds: 300
```

**Pattern comuni con taint:**

```bash
# Master node isolation (taint di default)
kubectl taint nodes master-1 node-role.kubernetes.io/control-plane:NoSchedule

# Dedicated node pool per team diversi
kubectl taint nodes team-a-node-1 team=a:NoSchedule
kubectl taint nodes team-b-node-1 team=b:NoSchedule

# Drain con cordon + taint
kubectl cordon worker-1          # NoSchedule implicito
kubectl drain worker-1 \
    --ignore-daemonsets \
    --delete-emptydir-data \
    --grace-period=60
```

---

## HPA — Horizontal Pod Autoscaler

L'**HPA** scala automaticamente il numero di pod in base a metriche.

```yaml
# HPA con metriche CPU e custom (KEDA-style multi-metric)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 50

  metrics:
    # CPU (metrica resource)
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70   # target 70% della request cpu

    # Memory (metrica resource)
    - type: Resource
      resource:
        name: memory
        target:
          type: AverageValue
          averageValue: 400Mi    # 400MB per pod

    # Custom metric (da Prometheus via prometheus-adapter)
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: 1000     # 1000 req/s per pod

    # External metric (da sistemi esterni)
    - type: External
      external:
        metric:
          name: sqs_queue_length
          selector:
            matchLabels:
              queue: orders-queue
        target:
          type: Value
          value: 500    # scala se > 500 messaggi in coda

  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # attesa prima di scale down
      policies:
        - type: Percent
          value: 25              # max 25% di riduzione alla volta
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0    # scala su subito
      policies:
        - type: Pods
          value: 4               # max 4 pod in più alla volta
          periodSeconds: 15
        - type: Percent
          value: 100             # oppure raddoppia
          periodSeconds: 15
      selectPolicy: Max          # usa la policy che permette il più rapido scale up
```

---

## VPA — Vertical Pod Autoscaler

Il **VPA** aggiorna automaticamente i resource requests/limits dei container.

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-vpa
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  updatePolicy:
    updateMode: "Auto"    # Off | Initial | Recreate | Auto
    # Off:        solo raccomandazioni, nessun update automatico
    # Initial:    applica al pod creation, non a quelli esistenti
    # Recreate:   evicts e ricrea i pod per applicare i nuovi valori
    # Auto:       come Recreate + in-place update quando supportato
  resourcePolicy:
    containerPolicies:
      - containerName: api
        minAllowed:
          cpu: 100m
          memory: 128Mi
        maxAllowed:
          cpu: 4
          memory: 4Gi
        controlledResources: ["cpu", "memory"]
        controlledValues: RequestsAndLimits  # o RequestsOnly
```

```bash
# Vedi raccomandazioni VPA senza applicarle (mode=Off)
kubectl describe vpa api-vpa
# Recommendation:
#   Container Recommendations:
#     Container Name: api
#     Lower Bound:
#       cpu: 200m
#       memory: 256Mi
#     Target:
#       cpu: 500m      ← valore raccomandato
#       memory: 512Mi
#     Upper Bound:
#       cpu: 2
#       memory: 2Gi
```

!!! warning "HPA + VPA"
    Non usare HPA (basato su CPU%) e VPA (che cambia le CPU requests) insieme sullo stesso deployment. Il VPA che cambia le requests invalida la baseline dell'HPA. Eccezione: VPA per memoria + HPA per CPU o metriche custom.

---

## KEDA — Event-Driven Autoscaling

**KEDA** (Kubernetes Event-Driven Autoscaler) estende l'HPA con scale-to-zero e decine di trigger supportati.

```yaml
# KEDA ScaledObject — scala basandosi su una coda Kafka
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: kafka-consumer-scaler
  namespace: production
spec:
  scaleTargetRef:
    name: kafka-consumer
  minReplicaCount: 0    # scale-to-zero! (0 pod quando la coda è vuota)
  maxReplicaCount: 50
  pollingInterval: 15   # secondi tra i check
  cooldownPeriod: 300   # secondi prima di scale-to-zero
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: order-processors
        topic: orders
        lagThreshold: "100"    # 1 pod ogni 100 messaggi in lag
        offsetResetPolicy: latest
      authenticationRef:
        name: kafka-keda-auth

---
# KEDA TriggerAuthentication
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: kafka-keda-auth
spec:
  secretTargetRef:
    - parameter: sasl.password
      name: kafka-sasl-secret
      key: password

---
# KEDA Cron Scaler — scaling programmato
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: api-business-hours-scaler
spec:
  scaleTargetRef:
    name: api
  triggers:
    - type: cron
      metadata:
        timezone: Europe/Rome
        start: "0 8 * * 1-5"   # lunedì-venerdì alle 8:00
        end: "0 20 * * 1-5"    # lunedì-venerdì alle 20:00
        desiredReplicas: "20"   # scale up a 20 repliche durante ore lavorative
```

---

## PriorityClass — Priorità di Scheduling ed Eviction

```yaml
# PriorityClass per workload critici
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical-services
value: 1000000          # valore più alto = priorità più alta
globalDefault: false
description: "Per servizi core che non devono essere evicted"
preemptionPolicy: PreemptLowerPriority  # può preemptare pod a bassa priorità

---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: batch-jobs
value: 100
globalDefault: false
description: "Per job batch a bassa priorità"
preemptionPolicy: Never  # non può preemptare nessuno
```

```yaml
# Uso nella definizione del pod
spec:
  priorityClassName: critical-services
  # Se il cluster è pieno, lo scheduler preempta pod con priorità inferiore
```

**Priority Classes di sistema predefinite:**

```bash
kubectl get priorityclasses
# NAME                          VALUE        GLOBAL-DEFAULT
# system-cluster-critical       2000000000   false   ← kube-dns, coredns
# system-node-critical          2000001000   false   ← kubelet, kube-proxy
```

---

## Troubleshooting

### Scenario 1 — Pod bloccato in Pending: nodo non trovato dallo scheduler

**Sintomo:** Il pod rimane in stato `Pending` per più di qualche secondo. `kubectl describe pod` mostra `0/N nodes are available`.

**Causa:** Le resource requests del pod superano le risorse allocabili di tutti i nodi, oppure node affinity/taints impediscono il placement.

**Soluzione:** Ispezionare il messaggio dell'evento e verificare risorse disponibili sui nodi.

```bash
kubectl describe pod <pod-name> -n <namespace>
# Cercare: "Events:" in fondo — il messaggio indica la causa esatta

# Verifica risorse allocabili sui nodi
kubectl describe nodes | grep -A 5 "Allocated resources"

# Verifica risorse residue per nodo
kubectl top nodes

# Verifica se ci sono taint che bloccano il pod
kubectl describe node <node-name> | grep -i taint
```

---

### Scenario 2 — HPA non scala: replica count invariato nonostante carico elevato

**Sintomo:** Il deployment è sotto carico ma l'HPA non aumenta le repliche. `kubectl describe hpa` mostra `<unknown>` nelle metriche.

**Causa:** Il metrics-server non è installato o non risponde, oppure i pod non hanno CPU requests definite (required per `Utilization` target).

**Soluzione:** Verificare che metrics-server sia attivo e che i pod abbiano resource requests.

```bash
# Verifica stato HPA e metriche attuali
kubectl describe hpa <hpa-name> -n <namespace>
# Cercare: "Conditions:" e "Metrics:"

# Verifica metrics-server
kubectl get pods -n kube-system | grep metrics-server
kubectl top pods -n <namespace>   # deve funzionare

# Se metrics-server KO, reinstallarlo
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verifica che i pod target abbiano resource requests
kubectl get deployment <name> -o jsonpath='{.spec.template.spec.containers[*].resources}'
```

---

### Scenario 3 — OOMKilled: container terminato per memory exceeded

**Sintomo:** I pod si riavviano ciclicamente con `OOMKilled` come reason. `kubectl describe pod` mostra `Last State: Terminated, Reason: OOMKilled`.

**Causa:** Il container ha superato il memory limit impostato. Il kernel termina il processo con SIGKILL.

**Soluzione:** Aumentare il memory limit oppure identificare il memory leak tramite VPA recommendations.

```bash
# Verifica restart count e causa
kubectl get pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace> | grep -A 3 "Last State"

# Visualizza consumo memoria attuale
kubectl top pods -n <namespace> --containers

# Usa VPA in mode Off per ottenere recommendations senza impatto
kubectl apply -f - <<EOF
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: debug-vpa
  namespace: <namespace>
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: <deployment-name>
  updatePolicy:
    updateMode: "Off"
EOF
kubectl describe vpa debug-vpa -n <namespace>
```

---

### Scenario 4 — Pod evicted: workload rimosso dal nodo per pressione risorse

**Sintomo:** Pod in stato `Evicted`. Il cluster ha node pressure (DiskPressure, MemoryPressure).

**Causa:** Il nodo ha esaurito le risorse (disco o memoria). Il kubelet evicts i pod con QoS class `BestEffort` prima, poi `Burstable`, poi `Guaranteed`.

**Soluzione:** Assegnare resource requests/limits corretti per garantire QoS `Guaranteed`, e monitorare la pressione sui nodi.

```bash
# Verifica pod evicted
kubectl get pods -n <namespace> --field-selector=status.phase=Failed | grep Evicted

# Pulisci pod evicted (non hanno restart automatico)
kubectl delete pods --field-selector=status.phase=Failed -n <namespace>

# Verifica condizioni del nodo (pressione risorse)
kubectl describe node <node-name> | grep -A 10 "Conditions:"

# Verifica QoS class assegnata ai pod (Guaranteed richiede requests==limits)
kubectl get pod <pod-name> -o jsonpath='{.status.qosClass}'

# Imposta PriorityClass per proteggere i workload critici dall'eviction
kubectl get priorityclasses
```

---

## Riferimenti

- [Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Pod Scheduling](https://kubernetes.io/docs/concepts/scheduling-eviction/)
- [HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [VPA](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [KEDA](https://keda.sh/docs/latest/concepts/)
- [Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
