---
title: "Kubernetes Resource Management"
slug: resource-management
category: containers
tags: [kubernetes, resources, qos, limits, requests, resourcequota, limitrange, multi-tenant]
search_keywords: [kubernetes requests limits, QoS classes kubernetes, LimitRange, ResourceQuota, OOM kill kubernetes, noisy neighbor kubernetes, Guaranteed Burstable BestEffort, memoria CPU kubernetes, resource starvation, multi-tenant kubernetes, namespace quota, pod resources]
parent: containers/kubernetes/_index
related: [containers/kubernetes/autoscaling, containers/kubernetes/scheduling-avanzato, containers/kubernetes/workloads]
official_docs: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Kubernetes Resource Management

## Panoramica

Il **Resource Management** di Kubernetes è il meccanismo con cui si dichiara quante risorse CPU e memoria ogni container può richiedere e consumare. Senza una corretta configurazione, un singolo workload può esaurire le risorse di un nodo causando OOM kill di altri pod (effetto **noisy neighbor**). Kubernetes usa `requests` e `limits` per tre scopi: prendere decisioni di scheduling (dove piazzare il pod), definire la **QoS class** del pod (chi viene ucciso per primo in caso di pressione), e forzare l'isolamento tra workload in ambienti multi-tenant. Si usa in ogni cluster Kubernetes con più di un team o più di un'applicazione.

---

## Concetti Chiave

### Requests vs Limits

!!! note "Definizioni"
    - **`requests`**: risorse *garantite* al container. Lo scheduler usa questo valore per selezionare il nodo. Il nodo deve avere abbastanza risorse *allocatable* non ancora riservate da altri pod.
    - **`limits`**: soglia massima che il container non può superare. CPU viene throttled (rallentato), memoria causa OOM kill del container se superata.

Il nodo non alloca fisicamente le `requests` — è una prenotazione contabile. Se la somma delle `requests` di tutti i pod su un nodo è pari alle risorse `allocatable`, il nodo è pieno per lo scheduler, anche se i container in realtà consumano molto meno.

```
Risorse nodo:
  allocatable CPU: 4000m
  allocatable Memory: 8Gi

Pod A: requests.cpu=500m, limits.cpu=1000m
Pod B: requests.cpu=1500m, limits.cpu=2000m
Pod C: requests.cpu=2000m, limits.cpu=3000m

Somma requests CPU = 4000m → nodo pieno per lo scheduler
Utilizzo reale CPU = 1200m → molto sotto il limite fisico
```

### Unità di Misura

**CPU:**
- `1` = 1 vCPU = 1000 millicores
- `500m` = 0.5 vCPU
- `100m` = 0.1 vCPU (minimo ragionevole)

**Memoria:**
- `128Mi` = 128 mebibyte (binario, 1 Mi = 1.048.576 byte)
- `1Gi` = 1 gibibyte
- `256M` = 256 megabyte (decimale — evitare, usare sempre `Mi`/`Gi`)

!!! warning "CPU vs Memoria"
    La CPU è una risorsa **comprimibile**: se il container supera il limit, viene throttled ma non ucciso. La memoria è **non comprimibile**: se supera il limit, il container viene ucciso con `OOMKilled`. Configurare i memory limits con attenzione è critico.

---

## Architettura / Come Funziona

### QoS Classes

Kubernetes assegna automaticamente una **Quality of Service class** ad ogni pod in base alla configurazione requests/limits. Questa classe determina chi viene terminato per primo quando il nodo è sotto pressione di memoria (kubelet eviction).

| QoS Class | Condizione | Priorità Eviction |
|-----------|-----------|-------------------|
| **Guaranteed** | `requests == limits` per TUTTI i container, per CPU e memoria | Ultima (più protetta) |
| **Burstable** | Almeno un container ha requests < limits, OPPURE solo memory request impostata | Media |
| **BestEffort** | Nessun request né limit impostato | Prima (meno protetta) |

```yaml
# Guaranteed — requests == limits su tutti i container
spec:
  containers:
  - name: app
    resources:
      requests:
        cpu: "500m"
        memory: "256Mi"
      limits:
        cpu: "500m"
        memory: "256Mi"
```

```yaml
# Burstable — requests < limits
spec:
  containers:
  - name: app
    resources:
      requests:
        cpu: "250m"
        memory: "128Mi"
      limits:
        cpu: "1000m"
        memory: "512Mi"
```

```yaml
# BestEffort — nessuna risorsa dichiarata (evitare in produzione)
spec:
  containers:
  - name: app
    resources: {}
```

!!! tip "Quando usare Guaranteed"
    Workload critici (database, sistema di pagamenti, componenti di infrastruttura) devono essere `Guaranteed`. I pod `Guaranteed` non vengono evicati a meno che non superino i propri limits. Il costo è che lo scheduler non piazza il pod se il nodo non ha abbastanza risorse allocatable pari ai limits.

### Flusso di Scheduling e Enforcement

```
1. Utente crea Pod con requests/limits dichiarati
        ↓
2. kube-scheduler seleziona nodo:
   sum(existing pod requests) + new pod requests ≤ node allocatable
        ↓
3. kubelet ammette il pod sul nodo (ammission control)
        ↓
4. Container Runtime (containerd) applica:
   - CPU: cgroups cpu.shares (requests) + cpu.cfs_quota (limits)
   - Memory: cgroups memory.limit_in_bytes (limits)
        ↓
5. Runtime enforcement:
   - CPU oltre limits → throttling (container rallenta, non muore)
   - Memory oltre limits → OOMKiller uccide il container
        ↓
6. Kubelet eviction (node pressure):
   - Ordine: BestEffort → Burstable (oltre requests) → Guaranteed
```

---

## Configurazione & Pratica

### Dichiarazione Risorse nel Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:1.0
    resources:
      requests:
        cpu: "250m"
        memory: "256Mi"
      limits:
        cpu: "1000m"
        memory: "512Mi"
  - name: sidecar
    image: envoy:latest
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"
```

!!! note "Init containers"
    Gli init container hanno anch'essi requests/limits propri. Per il calcolo della QoS class del pod si considerano TUTTI i container (init + sidecar + app).

### LimitRange — Policy di Default per Namespace

`LimitRange` definisce valori di default e bound (min/max) per container, pod e PersistentVolumeClaim in un namespace. Se un container non dichiara requests/limits, li eredita dai default del LimitRange.

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
  # Default per container
  - type: Container
    default:           # limits di default (se container non li specifica)
      cpu: "500m"
      memory: "256Mi"
    defaultRequest:    # requests di default
      cpu: "100m"
      memory: "128Mi"
    max:               # limite massimo consentito
      cpu: "4"
      memory: "4Gi"
    min:               # minimo obbligatorio
      cpu: "50m"
      memory: "64Mi"
    maxLimitRequestRatio:  # limit/request ratio massimo
      cpu: 10
      memory: 4
  # Default per pod (somma di tutti i container)
  - type: Pod
    max:
      cpu: "8"
      memory: "8Gi"
  # Limite per PVC
  - type: PersistentVolumeClaim
    max:
      storage: 50Gi
    min:
      storage: 1Gi
```

!!! warning "LimitRange e BestEffort"
    Se un namespace ha un LimitRange con `defaultRequest` e `default`, tutti i container senza risorse dichiarate ricevono quei valori automaticamente — e diventano almeno `Burstable`, eliminando il `BestEffort` indesiderato. Questo è un modo efficace per evitare pod senza risorse in produzione.

### ResourceQuota — Budget per Namespace

`ResourceQuota` limita il consumo totale di risorse in un namespace. Usato per garantire isolamento tra team in cluster multi-tenant.

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-alpha-quota
  namespace: team-alpha
spec:
  hard:
    # Risorse compute
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    # Oggetti Kubernetes
    pods: "50"
    services: "10"
    services.loadbalancers: "2"
    services.nodeports: "0"
    # Storage
    persistentvolumeclaims: "20"
    requests.storage: 500Gi
    # Per StorageClass specifica
    standard.storageclass.storage.k8s.io/requests.storage: 200Gi
    # ConfigMap e Secret
    configmaps: "20"
    secrets: "30"
```

**Verifica quota consumata:**

```bash
kubectl describe resourcequota team-alpha-quota -n team-alpha
# Output:
# Name: team-alpha-quota
# Namespace: team-alpha
# Resource                  Used    Hard
# --------                  ----    ----
# limits.cpu                4800m   20
# limits.memory             8Gi     40Gi
# pods                      12      50
# requests.cpu              2400m   10
# requests.memory           4Gi     20Gi
```

!!! warning "ResourceQuota e LimitRange insieme"
    Se un namespace ha una ResourceQuota su `requests.cpu`, TUTTI i pod in quel namespace devono dichiarare `resources.requests.cpu`. Altrimenti la creazione fallisce. Per questo LimitRange con `defaultRequest` è quasi sempre necessario insieme a ResourceQuota.

### ResourceQuota per QoS Class

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: guaranteed-only
  namespace: critical-apps
spec:
  hard:
    pods: "10"
  scopeSelector:
    matchExpressions:
    - operator: In
      scopeName: PriorityClass
      values: ["system-cluster-critical", "high-priority"]
```

```yaml
# Quota separata per BestEffort (ambienti dev)
apiVersion: v1
kind: ResourceQuota
metadata:
  name: best-effort-quota
  namespace: dev-sandbox
spec:
  hard:
    pods: "20"
  scopes:
  - BestEffort
```

---

## Best Practices

### Dimensionamento Corretto (Right-sizing)

Il problema più comune è il **over-provisioning**: requests molto più alte del consumo reale, che spreca capacità del cluster.

```bash
# Vedere consumo reale con kubectl top
kubectl top pods -n production --sort-by=memory
kubectl top nodes

# Vedere VPA recommendations (se VPA installato)
kubectl get vpa -n production
kubectl describe vpa myapp-vpa -n production
```

**Regola empirica per avvio:**
- `requests.cpu` = 50-70% del consumo medio rilevato
- `limits.cpu` = 2-4x le requests (burst temporaneo accettabile)
- `requests.memory` = consumo medio + 20% buffer
- `limits.memory` = requests.memory × 1.5-2 (non troppo alto — OOM kill è violento)

!!! tip "Memory limits stretti"
    Impostare `limits.memory` molto vicino a `requests.memory` (ratio 1.0-1.5) aumenta la stabilità: il container va in OOM e si riavvia pulito invece di occupare memoria in modo irregolare. Meglio un restart controllato che un nodo degradato.

### Pattern Multi-tenant

```
Namespace ┌─────────────────────────────┐
team-alpha │  LimitRange (default+bounds) │
           │  ResourceQuota (hard limits) │
           └─────────────────────────────┘
                         ↓
           Pod A: requests=100m/128Mi, limits=500m/256Mi
           Pod B: requests=200m/256Mi, limits=1/512Mi
           ...
           Totale: ≤ quota namespace
```

Struttura tipica per cluster multi-tenant:

```yaml
# Per ogni namespace team:
# 1. LimitRange con default ragionevoli
# 2. ResourceQuota con budget del team
# 3. NetworkPolicy per isolamento rete
# 4. RBAC per isolamento permessi
```

### CPU Throttling e Limits

Il CPU throttling è invisibile ma degrada le performance. Un container che usa `500m` con `limits.cpu=500m` non viene mai throttled. Uno con `requests.cpu=100m` e `limits.cpu=500m` viene throttled quando la domanda supera il tempo CPU disponibile.

```bash
# Verificare CPU throttling (richiede accesso ai nodi o metrics server avanzato)
# Con Prometheus:
# rate(container_cpu_cfs_throttled_seconds_total[5m])
# / rate(container_cpu_cfs_periods_total[5m])
# > 0.25 → throttling significativo (>25%)
```

!!! warning "CPU Limits e Java/JVM"
    Applicazioni JVM in container richiedono `-XX:+UseContainerSupport` (default da Java 8u191+) per rispettare i CPU limits. Senza questo flag, la JVM vede i core del nodo fisico e crea thread pool oversized. Verificare sempre `JAVA_OPTS` nelle immagini legacy.

### Anti-pattern da Evitare

| Anti-pattern | Problema | Soluzione |
|-------------|---------|-----------|
| Nessun request/limit | BestEffort pod evicati per primi, nessuna garanzia | Impostare sempre, o usare LimitRange |
| requests = 0, limits alti | Scheduling sbagliato — nodo sembra vuoto ma si satura | requests deve riflettere il consumo reale |
| limits.memory molto sopra requests | Pod occupa molta memoria senza essere evictable | ratio memory limit/request ≤ 2 |
| CPU limits uguale a requests per batch | Batch job non può fare burst → lento | Batch: limits.cpu >> requests.cpu |
| ResourceQuota senza LimitRange | Pods senza resources.requests rifiutati | Sempre LimitRange + ResourceQuota insieme |

---

## Troubleshooting

### OOMKilled

```bash
# Identificare pod in OOMKilled
kubectl get pods -n production | grep OOMKilled
kubectl describe pod <pod-name> -n production
# Cercare: "OOMKilled" in Reason, "Exit Code: 137"

# Ultimo stato container
kubectl get pod <pod-name> -n production -o jsonpath='{.status.containerStatuses[*].lastState}'
```

**Cause comuni:**
- `limits.memory` troppo basso per il carico reale
- Memory leak nell'applicazione
- JVM senza flag container-aware (heap cresce oltre il limite)

**Fix rapido:**
```bash
kubectl set resources deployment myapp \
  --limits=memory=1Gi \
  --requests=memory=512Mi \
  -n production
```

### Pod in Pending per Risorse Insufficienti

```bash
kubectl describe pod <pod-name> -n production
# Cercare: "Insufficient cpu" o "Insufficient memory" in Events

# Vedere risorse disponibili per nodo
kubectl describe nodes | grep -A5 "Allocated resources"

# Vedere tutti i pod con requests alto
kubectl get pods -n production -o custom-columns=\
"NAME:.metadata.name,\
CPU_REQ:.spec.containers[*].resources.requests.cpu,\
MEM_REQ:.spec.containers[*].resources.requests.memory"
```

### ResourceQuota Exceeded

```bash
# Il pod non viene creato — errore nella creazione
kubectl describe quota -n team-alpha
# Cercare campi Used vs Hard

# Trovare chi consuma più risorse nel namespace
kubectl top pods -n team-alpha --sort-by=cpu
```

### CPU Throttling Eccessivo

```bash
# Con kubectl top — non mostra throttling direttamente
# Verificare con Prometheus se disponibile:
# sum(rate(container_cpu_cfs_throttled_seconds_total{namespace="production"}[5m]))
# by (pod, container)
# / sum(rate(container_cpu_cfs_periods_total{namespace="production"}[5m]))
# by (pod, container)

# Fix: aumentare limits.cpu o usare VPA in modo Off (solo recommendations)
```

### LimitRange Non Applica Default

```bash
# LimitRange applica default solo ai nuovi pod
# Pod esistenti NON vengono modificati

# Verificare che LimitRange esista nel namespace corretto
kubectl get limitrange -n production
kubectl describe limitrange default-limits -n production

# Verificare che il pod sia stato creato DOPO il LimitRange
kubectl describe pod <pod-name> | grep -A10 "Limits:"
```

---

## Relazioni

??? info "Autoscaling — Connessione con HPA/VPA"
    HPA usa `requests.cpu` come baseline per calcolare la percentuale di utilizzo target. Se requests sono sovrastimate, HPA scala troppo tardi; se sottostimate, scala troppo presto. VPA in modalità `Off` fornisce recommendations per correggere requests/limits senza modificarli automaticamente.

    **Approfondimento completo →** [Kubernetes Autoscaling](./autoscaling.md)

??? info "Scheduling Avanzato — ResourceQuota e Priority"
    PriorityClass interagisce con resource management: pod ad alta priorità possono far evictare pod a bassa priorità se le risorse del nodo sono sature. ResourceQuota può essere scopata per PriorityClass per separare budget tra workload critici e batch.

    **Approfondimento completo →** [Scheduling Avanzato](./scheduling-avanzato.md)

??? info "Workloads — Configurazione per tipo"
    Deployment, StatefulSet, DaemonSet e Job hanno pattern di resource management diversi: i Job batch beneficiano di limits.cpu >> requests.cpu per il burst; i DaemonSet devono avere resources contenute perché occupano ogni nodo.

    **Approfondimento completo →** [Kubernetes Workloads](./workloads.md)

---

## Riferimenti

- [Kubernetes Docs — Managing Resources for Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes Docs — Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes Docs — Limit Ranges](https://kubernetes.io/docs/concepts/policy/limit-range/)
- [Kubernetes Docs — Configure Quality of Service for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/)
- [Google SRE — Handling Overload](https://sre.google/sre-book/handling-overload/)
- [Kubernetes Best Practices — Resource Requests and Limits](https://cloud.google.com/blog/products/containers-kubernetes/kubernetes-best-practices-resource-requests-and-limits)
