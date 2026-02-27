---
title: "Kubernetes Workloads"
slug: workloads
category: containers
tags: [kubernetes, pod, deployment, statefulset, daemonset, job, cronjob, init-containers, sidecars]
search_keywords: [kubernetes pod spec, kubernetes deployment rolling update, statefulset headless service, kubernetes daemonset, kubernetes job, cronjob kubernetes, init containers kubernetes, sidecar pattern kubernetes, pod lifecycle hooks, pod qos classes, pod disruption budget, pod topology spread]
parent: containers/kubernetes/_index
related: [containers/kubernetes/scheduling-avanzato, containers/kubernetes/storage, containers/kubernetes/sicurezza]
official_docs: https://kubernetes.io/docs/concepts/workloads/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Kubernetes Workloads

## Pod — L'Unità Fondamentale

Il **Pod** è l'oggetto minimo deployabile in Kubernetes. Contiene uno o più container che condividono network namespace, IPC namespace e volumes.

```yaml
# Pod spec completa con tutti i pattern importanti
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
  namespace: production
  labels:
    app: api
    version: "1.0.0"
    tier: backend
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9090"
spec:
  # ── Init Containers ──────────────────────────────────────────
  # Eseguono in sequenza PRIMA dei container principali
  # Se uno fallisce, il pod non si avvia
  initContainers:
    - name: wait-for-db
      image: busybox:1.36
      command: ['sh', '-c', 'until nc -z postgres 5432; do sleep 2; done']

    - name: run-migrations
      image: myapp/migrations:1.0.0
      command: ['python', '-m', 'alembic', 'upgrade', 'head']
      envFrom:
        - secretRef:
            name: db-credentials

  # ── Containers Principali ────────────────────────────────────
  containers:
    - name: api
      image: registry.company.com/api:1.0.0
      imagePullPolicy: IfNotPresent    # Always | Never | IfNotPresent

      ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        - name: metrics
          containerPort: 9090

      # ── Environment ────────────────────────────────────
      env:
        - name: DB_HOST
          value: postgres
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: password
        - name: MY_NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName      # Downward API
        - name: MY_POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        - name: MEMORY_LIMIT
          valueFrom:
            resourceFieldRef:
              resource: limits.memory       # Downward API: resource limits

      envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets

      # ── Resource Requests/Limits ──────────────────────
      resources:
        requests:
          cpu: "250m"        # 0.25 core — usato per scheduling
          memory: "256Mi"    # usato per scheduling
        limits:
          cpu: "1"           # throttle se supera (non uccide)
          memory: "512Mi"    # OOM kill se supera

      # ── Probes ────────────────────────────────────────
      startupProbe:           # blocca liveness finché non passa
        httpGet:
          path: /healthz
          port: http
        failureThreshold: 30  # 30 * 10s = 5 minuti max per startup
        periodSeconds: 10

      livenessProbe:          # uccide e ricrea il container se fallisce
        httpGet:
          path: /healthz
          port: http
        initialDelaySeconds: 0  # non necessario con startupProbe
        periodSeconds: 30
        timeoutSeconds: 5
        failureThreshold: 3

      readinessProbe:         # rimuove da Service endpoint se fallisce
        httpGet:
          path: /ready
          port: http
        periodSeconds: 10
        successThreshold: 1
        failureThreshold: 3

      # ── Security Context ──────────────────────────────
      securityContext:
        runAsUser: 1001
        runAsGroup: 1001
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
        seccompProfile:
          type: RuntimeDefault

      # ── Volumes Mounts ────────────────────────────────
      volumeMounts:
        - name: app-data
          mountPath: /app/data
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: tmp
          mountPath: /tmp

      # ── Lifecycle Hooks ───────────────────────────────
      lifecycle:
        postStart:            # eseguito dopo il container start (async)
          exec:
            command: ["/bin/sh", "-c", "echo started > /tmp/started"]
        preStop:              # eseguito PRIMA di SIGTERM (sync)
          exec:
            command: ["/bin/sh", "-c", "sleep 5; /app/graceful-shutdown.sh"]
            # Dà tempo al load balancer di rimuovere il pod dagli endpoint

    # ── Sidecar Container ────────────────────────────────────────
    - name: log-forwarder
      image: fluent/fluent-bit:2.2
      resources:
        requests:
          cpu: "50m"
          memory: "32Mi"
        limits:
          cpu: "100m"
          memory: "64Mi"
      volumeMounts:
        - name: app-data
          mountPath: /app/data
          readOnly: true

  # ── Volumes ──────────────────────────────────────────────────
  volumes:
    - name: app-data
      persistentVolumeClaim:
        claimName: api-data-pvc
    - name: config
      configMap:
        name: api-config
        defaultMode: 0440
    - name: tmp
      emptyDir:
        medium: Memory    # tmpfs
        sizeLimit: 128Mi

  # ── Pod-level Security ───────────────────────────────────────
  securityContext:
    runAsNonRoot: true
    fsGroup: 1001           # gruppo per i volumes montati
    fsGroupChangePolicy: OnRootMismatch  # efficiente: cambia solo se necessario
    seccompProfile:
      type: RuntimeDefault

  # ── Scheduling ───────────────────────────────────────────────
  serviceAccountName: api-sa
  automountServiceAccountToken: false  # non montare il token SA automaticamente
  terminationGracePeriodSeconds: 60    # tempo tra SIGTERM e SIGKILL
  dnsPolicy: ClusterFirst
  restartPolicy: Always                # Always | OnFailure | Never
```

---

## Deployment — Applicazioni Stateless

Il **Deployment** gestisce ReplicaSets e implementa rolling updates e rollbacks.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  # ── Rolling Update Strategy ───────────────────────────
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1           # max pod in eccesso durante update (default 25%)
      maxUnavailable: 0     # 0 = zero-downtime (default 25%)
      # Con maxSurge=1, maxUnavailable=0:
      # 1. Crea nuovo pod (totale: 4)
      # 2. Attende che sia Ready
      # 3. Termina un vecchio pod (totale: 3)
      # 4. Ripete

  # ── Revision History ──────────────────────────────────
  revisionHistoryLimit: 10      # numero di vecchi ReplicaSet mantenuti

  # ── Selector → template label matching ───────────────
  template:
    metadata:
      labels:
        app: api
        version: "1.0.0"
    spec:
      # ... (come il Pod spec sopra)
```

```bash
# Operazioni Deployment
kubectl rollout status deployment/api -n production    # monitora l'update
kubectl rollout history deployment/api -n production   # lista revisioni
kubectl rollout undo deployment/api -n production      # rollback all'ultima revisione
kubectl rollout undo deployment/api --to-revision=3    # rollback a revisione specifica
kubectl rollout pause deployment/api                   # pausa un rolling update
kubectl rollout resume deployment/api                  # riprende il rolling update

# Aggiorna immagine con rollout
kubectl set image deployment/api api=registry.company.com/api:2.0.0 -n production

# Scala rapidamente
kubectl scale deployment/api --replicas=10 -n production

# Forza re-deploy senza cambiare l'immagine (aggiorna annotation)
kubectl rollout restart deployment/api -n production
```

---

## StatefulSet — Applicazioni Stateful

Il **StatefulSet** garantisce identità stabile (nome, network, storage) per ogni pod. Essenziale per database, message broker, e sistemi distribuiti.

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: production
spec:
  serviceName: postgres-headless   # RICHIESTO: headless service per DNS stabile
  replicas: 3
  selector:
    matchLabels:
      app: postgres

  # ── Update Strategy ───────────────────────────────────
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      partition: 2   # Canary: aggiorna solo pod con ordinal >= 2 (es. postgres-2)
                     # Permette di testare prima di aggiornare tutti

  # ── Pod Management Policy ─────────────────────────────
  podManagementPolicy: OrderedReady  # Parallel | OrderedReady
  # OrderedReady: deploy e scale in ordine (0→1→2, 2→1→0 per delete)
  # Parallel: tutti i pod contemporaneamente (utile per sistemi che si auto-configurano)

  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - name: postgres
              containerPort: 5432
          env:
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            # postgres-0, postgres-1, postgres-2
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
            - name: config
              mountPath: /etc/postgresql

  # ── Volume Claim Templates ────────────────────────────
  # Ogni pod ottiene il proprio PVC, non condiviso
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3
        resources:
          requests:
            storage: 50Gi
```

```yaml
# Headless Service per StatefulSet (DNS stabile)
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
spec:
  clusterIP: None    # headless = nessun VIP, solo DNS records
  selector:
    app: postgres
  ports:
    - name: postgres
      port: 5432

# DNS generati:
# postgres-0.postgres-headless.production.svc.cluster.local → IP di postgres-0
# postgres-1.postgres-headless.production.svc.cluster.local → IP di postgres-1
# postgres-2.postgres-headless.production.svc.cluster.local → IP di postgres-2

# Il pod può scoprire il proprio ordinal dal nome:
# POD_NAME=postgres-2 → sono il replica 2 → configuro come replica secondary
```

**Comportamento di Scaling StatefulSet:**

```
Scale Down: postgres da 3 a 2 pod

  Passo 1: postgres-2 viene terminato (ordine inverso)
           Il suo PVC postgres-data-2 NON viene cancellato
           (reclaimPolicy = Retain per i PVC dei StatefulSet)

  Passo 2 (opzionale): postgres-1 termina
           PVC postgres-data-1 rimane

  Scale up da 2 a 3:
  Il nuovo postgres-2 trova il suo PVC postgres-data-2 esistente
  → Monta lo stesso storage → nessuna perdita di dati
```

---

## DaemonSet — Un Pod per Nodo

Il **DaemonSet** garantisce che ogni nodo (o un subset) esegua una copia del Pod. Usato per monitoring agents, log collectors, CNI plugins, storage drivers.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1    # aggiorna un nodo alla volta
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      # DaemonSet spesso necessita tollerazioni per girare sui master
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
        - key: node.kubernetes.io/not-ready
          operator: Exists
          effect: NoExecute
        - key: node.kubernetes.io/unreachable
          operator: Exists
          effect: NoExecute

      # Accesso al filesystem host per metrics
      hostPID: true       # vede i PID dell'host
      hostNetwork: true   # usa il network dell'host

      containers:
        - name: node-exporter
          image: quay.io/prometheus/node-exporter:v1.8.0
          args:
            - '--path.rootfs=/host'
          ports:
            - containerPort: 9100
              hostPort: 9100    # esposizione diretta sulla porta dell'host
          volumeMounts:
            - name: rootfs
              mountPath: /host
              readOnly: true
              mountPropagation: HostToContainer
          securityContext:
            runAsNonRoot: true
            runAsUser: 65534

      volumes:
        - name: rootfs
          hostPath:
            path: /
```

---

## Job e CronJob — Task Batch

```yaml
# Job — task che deve completare una volta
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
spec:
  completions: 1             # quante completions totali
  parallelism: 1             # pod in parallelo
  backoffLimit: 3            # retry massimi prima di fail
  activeDeadlineSeconds: 600 # timeout totale (10 minuti)
  ttlSecondsAfterFinished: 3600  # auto-cleanup dopo 1h
  template:
    spec:
      restartPolicy: OnFailure  # Never | OnFailure (non Always per Job)
      containers:
        - name: migration
          image: myapp/migrations:1.0.0
          command: ["python", "-m", "alembic", "upgrade", "head"]

---
# Job parallelo (multiple completions)
apiVersion: batch/v1
kind: Job
metadata:
  name: image-processor
spec:
  completions: 100      # elabora 100 immagini totali
  parallelism: 10       # 10 pod in parallelo
  completionMode: Indexed  # ogni pod riceve un indice unico (JOB_COMPLETION_INDEX env)
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: processor
          image: myapp/image-processor:1.0.0
          env:
            - name: ITEM_INDEX
              valueFrom:
                fieldRef:
                  fieldPath: metadata.annotations['batch.kubernetes.io/job-completion-index']

---
# CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-report
spec:
  schedule: "0 2 * * *"       # cron syntax: alle 2:00 ogni giorno
  timeZone: "Europe/Rome"
  concurrencyPolicy: Forbid    # Allow | Forbid | Replace
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  startingDeadlineSeconds: 300  # se perde lo schedule, ha 5min per avviarsi
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: reporter
              image: myapp/reporter:1.0.0
```

---

## Pod Quality of Service (QoS)

Kubernetes assegna una classe QoS a ogni Pod in base ai resource requests/limits. Questa classe determina la priorità di eviction sotto memory pressure.

```
QoS Classes — Priority di Eviction (OOM)

  GUARANTEED (mai evicted per memoria, solo se il nodo è in crisis totale):
  → requests.cpu == limits.cpu  E  requests.memory == limits.memory
  resources:
    requests:  {cpu: "500m", memory: "256Mi"}
    limits:    {cpu: "500m", memory: "256Mi"}  ← identici

  BURSTABLE (evicted dopo BestEffort):
  → requests < limits, o solo requests definiti, o solo uno dei due
  resources:
    requests:  {cpu: "100m", memory: "128Mi"}
    limits:    {cpu: "500m", memory: "512Mi"}  ← diversi

  BEST_EFFORT (evicted per primi):
  → nessun request né limit definito
  resources: {}  ← o omesso completamente

  Raccomandazione: GUARANTEED per DB/stateful, BURSTABLE per app standard
```

---

## Pod Disruption Budget

Il **PDB** protegge i workload durante manutenzione del cluster, impedendo che troppi pod vengano evicted simultaneamente.

```yaml
# Garantisce almeno 2 pod disponibili durante node drain/disruption
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
  namespace: production
spec:
  minAvailable: 2        # oppure: maxUnavailable: 1
  selector:
    matchLabels:
      app: api

# Con 3 replicas e minAvailable=2:
# kubectl drain worker-node → può evictare max 1 pod api alla volta
# Il drain aspetta che il pod si riavvii altrove prima di continuare
```

---

## Riferimenti

- [Pods](https://kubernetes.io/docs/concepts/workloads/pods/)
- [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [DaemonSets](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Pod QoS](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)
- [PodDisruptionBudget](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
