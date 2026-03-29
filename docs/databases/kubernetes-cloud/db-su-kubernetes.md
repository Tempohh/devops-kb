---
title: "Database su Kubernetes"
slug: db-su-kubernetes
category: databases
tags: [kubernetes, statefulset, operator, postgresql, storage, persistentvolume, cloudnativepg]
search_keywords: [database kubernetes, statefulset postgresql, persistent volume claim postgresql, kubernetes operator pattern, cloudnativepg operator, zalando postgres operator, crunchy postgres operator, storage class kubernetes, local storage kubernetes, network attached storage kubernetes, EBS CSI driver, GCP persistent disk, azure disk, kubernetes database anti-pattern, pod disruption budget database, init container database, sidecar pgbouncer kubernetes, kubernetes database backup, velero database backup, k8s stateful workloads]
parent: databases/kubernetes-cloud/_index
related: [databases/postgresql/connection-pooling, databases/replicazione-ha/backup-pitr, databases/postgresql/replicazione]
official_docs: https://cloudnative-pg.io/documentation/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Database su Kubernetes

## Panoramica

Eseguire database su Kubernetes è diventato praticabile con l'operatore pattern e i CSI driver per storage persistente. Non è per tutti — richiede competenze di database e Kubernetes contemporaneamente — ma elimina l'eterogeneità dell'infrastruttura e riduce i costi rispetto ai managed service.

**Quando ha senso eseguire database su Kubernetes:**
- Team con competenze sia database che Kubernetes
- Necessità di rimanere on-premise o multi-cloud
- Costo del managed service ingiustificabile rispetto al volume
- Requisiti di configurazione non supportati dal managed service (estensioni, versioni, tuning)

**Quando NON farlo:**
- Team senza un DBA o equivalente esperienza
- SLA stringenti senza budget per il team operativo
- Startup in early stage (costo-opportunità troppo alto)

## StatefulSet — Il Primitivo per i Database

Lo **StatefulSet** è la risorsa Kubernetes progettata per workload stateful. A differenza dei Deployment (pod intercambiabili), StatefulSet garantisce:

- **Identità stabile**: ogni pod ha un nome prevedibile (`postgres-0`, `postgres-1`)
- **Storage persistente**: ogni pod ha il proprio PVC che sopravvive al re-scheduling
- **Ordine di deploy**: pod creati/eliminati in sequenza (pod N+1 parte solo dopo N=Running)
- **Headless Service**: DNS stabile per pod individuali (`postgres-0.postgres-service.namespace.svc.cluster.local`)

```yaml
# StatefulSet PostgreSQL standalone (senza operator — solo per capire il primitivo)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: databases
spec:
  serviceName: postgres       # Headless service per DNS stabile
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      securityContext:
        fsGroup: 999          # Gruppo postgres
        runAsUser: 999

      initContainers:
      - name: init-permissions
        image: busybox
        command: ["sh", "-c", "chown -R 999:999 /var/lib/postgresql/data"]
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data

      containers:
      - name: postgres
        image: postgres:17
        env:
        - name: POSTGRES_DB
          value: mydb
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata  # Sottodirectory necessaria

        ports:
        - containerPort: 5432

        resources:
          requests:
            memory: "2Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"

        # Probes: Kubernetes sa quando il container è pronto e sano
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "$(POSTGRES_USER)", "-d", "$(POSTGRES_DB)"]
          initialDelaySeconds: 10
          periodSeconds: 5

        livenessProbe:
          exec:
            command: ["pg_isready", "-U", "$(POSTGRES_USER)"]
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3

        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        - name: postgres-config
          mountPath: /etc/postgresql/postgresql.conf
          subPath: postgresql.conf

      volumes:
      - name: postgres-config
        configMap:
          name: postgres-config

  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: gp3              # Storage class CSI (es. AWS EBS gp3)
      resources:
        requests:
          storage: 100Gi
---
# Service per accesso dall'applicazione
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: databases
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
```

### Storage Class — Scelta Critica

```yaml
# AWS EBS gp3 — lettura/scrittura singolo pod (ReadWriteOnce)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"              # IOPS allocati (max 16000 per gp3)
  throughput: "125"         # MB/s throughput
  encrypted: "true"
reclaimPolicy: Retain       # RETAIN: non eliminare il volume al delete del PVC
allowVolumeExpansion: true  # Permette resize online
volumeBindingMode: WaitForFirstConsumer  # Crea il volume nella stessa AZ del pod
```

!!! warning "Local Storage vs Network Storage"
    Local storage (NVMe sul nodo) è 10x più veloce di EBS/GCP PD/Azure Disk, ma il pod è vincolato a quel nodo fisico — se il nodo muore, il pod non può essere schedulato altrove.
    Network storage (EBS, GCP PD) permette re-scheduling ma ha latenza I/O maggiore (tipicamente 1-5ms vs 0.1ms per NVMe locale).
    Per database ad alto IOPS, valutare local storage con replica PostgreSQL per HA.

---

## CloudNativePG — L'Operator PostgreSQL

Gestire PostgreSQL su Kubernetes manualmente (StatefulSet + script custom) è complesso e error-prone. Gli **operator** incapsulano le best practice di gestione del database come logica Kubernetes.

**[CloudNativePG](https://cloudnative-pg.io/)** (CNPG) è l'operator più maturo per PostgreSQL su Kubernetes, sviluppato da EDB e donato alla CNCF.

```yaml
# Cluster PostgreSQL con CloudNativePG (3 nodi: 1 primary + 2 replica)
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-cluster
  namespace: databases
spec:
  instances: 3              # 1 primary + 2 replica
  primaryUpdateStrategy: unsupervised   # Rolling update automatico
  imageName: ghcr.io/cloudnative-pg/postgresql:17

  postgresql:
    parameters:
      shared_buffers: "2GB"
      max_connections: "200"
      wal_level: "replica"
      synchronous_commit: "remote_write"

  bootstrap:
    initdb:
      database: mydb
      owner: myapp
      secret:
        name: mydb-credentials

  storage:
    size: 100Gi
    storageClass: gp3

  walStorage:            # Storage separato per WAL (migliori performance I/O)
    size: 20Gi
    storageClass: gp3

  # Backup su S3 via WAL archiving
  backup:
    retentionPolicy: "30d"
    barmanObjectStore:
      destinationPath: "s3://my-cnpg-backups/postgres-cluster"
      s3Credentials:
        accessKeyId:
          name: s3-credentials
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-credentials
          key: SECRET_ACCESS_KEY
      wal:
        compression: brotli
        maxParallel: 4

  # Monitoring con Prometheus
  monitoring:
    enablePodMonitor: true    # Crea automaticamente PodMonitor per Prometheus

  # Resources
  resources:
    requests:
      memory: "4Gi"
      cpu: "1"
    limits:
      memory: "8Gi"
      cpu: "4"

  affinity:
    enablePodAntiAffinity: true   # Distribuisce pod su nodi fisici diversi
    topologyKey: kubernetes.io/hostname
```

### Service e Connessione con CNPG

CloudNativePG crea automaticamente i Service:

```bash
# Service creati da CNPG:
# postgres-cluster-rw   → Primary (read-write)
# postgres-cluster-ro   → Replica (read-only, load balanced)
# postgres-cluster-r    → Qualsiasi nodo (incluso primary)

# Connessione dal pod applicativo
psql "host=postgres-cluster-rw.databases.svc.cluster.local \
      user=myapp \
      dbname=mydb \
      sslmode=require"
```

### Backup e PITR con CNPG

```yaml
# Backup on-demand
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: postgres-backup-20240115
spec:
  method: barmanObjectStore
  cluster:
    name: postgres-cluster

---
# Restore a punto nel tempo (PITR) — crea un nuovo cluster
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-restored
spec:
  instances: 1
  bootstrap:
    recovery:
      source: postgres-cluster-backup
      recoveryTarget:
        targetTime: "2024-01-15T14:31:59+00:00"
  externalClusters:
  - name: postgres-cluster-backup
    barmanObjectStore:
      destinationPath: "s3://my-cnpg-backups/postgres-cluster"
      s3Credentials: ...
```

### Operazioni con kubectl e plugin CNPG

```bash
# Installa plugin kubectl
kubectl krew install cnpg

# Stato del cluster
kubectl cnpg status postgres-cluster -n databases

# Switchover manuale (promuove una replica)
kubectl cnpg promote postgres-cluster -n databases

# Psql interattivo sul primary
kubectl cnpg psql postgres-cluster -n databases

# Backup immediato
kubectl cnpg backup postgres-cluster -n databases

# Verifica backup
kubectl cnpg status postgres-cluster -n databases --verbose
```

---

## PodDisruptionBudget — Protezione durante Manutenzione

```yaml
# Garantisce che almeno 2 nodi siano sempre disponibili durante drain/upgrade
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: postgres-pdb
  namespace: databases
spec:
  minAvailable: 2           # Almeno 2 pod su 3 devono essere Running
  selector:
    matchLabels:
      cnpg.io/cluster: postgres-cluster
```

---

## Best Practices

- **Usare un operator**: non gestire PostgreSQL su Kubernetes manualmente — usare CloudNativePG, Zalando Postgres Operator, o Crunchy PGO. Il costo operativo del self-managing supera il vantaggio
- **Storage class con `reclaimPolicy: Retain`**: il `Delete` default elimina il PV quando il PVC viene cancellato — catastrofico per un database. Sempre `Retain` in produzione
- **Separare WAL e data su storage diversi**: reduce la contesa I/O e permette sizing indipendente
- **PodAntiAffinity**: distribuire le repliche su nodi fisici diversi — altrimenti un nodo down elimina il quorum
- **Risorse definite con `requests` e `limits`**: senza limits, il database può consumare tutta la RAM del nodo causando OOM kill di altri pod; senza requests, lo scheduler non garantisce le risorse

## Troubleshooting

### Scenario 1 — Pod rimane in `Pending` dopo la creazione

**Sintomo:** Il pod del database resta in stato `Pending` indefinitamente; nessun evento di scheduling.

**Causa:** Il PVC non viene provisioned — cause tipiche: StorageClass inesistente o errata, CSI driver non installato, PVC in AZ diversa dal nodo disponibile.

**Soluzione:** Ispezionare il PVC e gli eventi del pod per identificare l'errore esatto.

```bash
# Controlla lo stato del PVC
kubectl get pvc -n databases

# Dettagli del PVC (eventi di errore in fondo)
kubectl describe pvc postgres-data-postgres-0 -n databases

# Verifica CSI driver installati
kubectl get csidrivers

# Verifica le StorageClass disponibili
kubectl get storageclass

# Se il pod è in Pending, controlla gli eventi di scheduling
kubectl describe pod postgres-0 -n databases | grep -A 20 "Events:"
```

---

### Scenario 2 — Pod `OOMKilled` — container ucciso per memoria esaurita

**Sintomo:** Il pod si riavvia ciclicamente con stato `OOMKilled`; `kubectl describe pod` mostra `Exit Code: 137`.

**Causa:** Il consumo di memoria PostgreSQL supera il `limits.memory` del container. Formula critica: `max_connections × work_mem` può eccedere il limite, specialmente sotto carico.

**Soluzione:** Ridurre `max_connections` o `work_mem`, oppure aumentare il `limits.memory`. Con CNPG modificare i parametri nel manifest del Cluster.

```bash
# Verifica il motivo del crash
kubectl describe pod postgres-0 -n databases | grep -A 5 "Last State"

# Controlla l'utilizzo corrente di memoria
kubectl top pod -n databases

# Con CNPG: aggiorna i parametri PostgreSQL nel Cluster
kubectl patch cluster postgres-cluster -n databases --type=merge \
  -p '{"spec":{"postgresql":{"parameters":{"max_connections":"100","work_mem":"16MB"}}}}'

# Verifica che il rolling restart sia avvenuto
kubectl cnpg status postgres-cluster -n databases
```

---

### Scenario 3 — Replica non sincronizzata / lag elevato

**Sintomo:** La replica mostra lag crescente o stato `Streaming` assente; `kubectl cnpg status` riporta replica non allineata al primary.

**Causa:** NetworkPolicy che blocca la porta 5432 tra pod, oppure storage della replica troppo lento per seguire il WAL rate del primary.

**Soluzione:** Verificare le NetworkPolicy nel namespace e misurare il WAL lag con query su PostgreSQL.

```bash
# Stato del cluster CNPG (replica lag visibile)
kubectl cnpg status postgres-cluster -n databases

# Controlla NetworkPolicy attive nel namespace
kubectl get networkpolicy -n databases
kubectl describe networkpolicy -n databases

# Query sul primary per verificare lo stato di replica
kubectl cnpg psql postgres-cluster -n databases -- \
  -c "SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn,
             (sent_lsn - replay_lsn) AS replication_lag
      FROM pg_stat_replication;"

# Se NetworkPolicy è il problema, aggiungere una regola permissiva tra pod CNPG
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-cnpg-replication
  namespace: databases
spec:
  podSelector:
    matchLabels:
      cnpg.io/cluster: postgres-cluster
  ingress:
  - from:
    - podSelector:
        matchLabels:
          cnpg.io/cluster: postgres-cluster
    ports:
    - port: 5432
EOF
```

---

### Scenario 4 — Backup CNPG fallisce con errore S3

**Sintomo:** Il Backup object è in stato `Failed`; `kubectl describe backup` mostra errori di autenticazione S3 o bucket non trovato.

**Causa:** Secret con credenziali S3 errate o assenti, IAM role non associato al service account, bucket inesistente o policy S3 troppo restrittiva.

**Soluzione:** Verificare il Secret, il ServiceAccount e le policy S3.

```bash
# Stato del backup
kubectl get backup -n databases
kubectl describe backup postgres-backup-20240115 -n databases

# Verifica il Secret delle credenziali S3
kubectl get secret s3-credentials -n databases -o jsonpath='{.data}' | \
  python3 -c "import sys,json,base64; d=json.load(sys.stdin); \
  [print(k, base64.b64decode(v).decode()) for k,v in d.items()]"

# Log del controller CNPG per errori dettagliati
kubectl logs -n cnpg-system -l app.kubernetes.io/name=cloudnative-pg --tail=50

# Test manuale della connessione S3 dall'interno del namespace
kubectl run s3-test --rm -it --image=amazon/aws-cli --restart=Never \
  --env="AWS_ACCESS_KEY_ID=<key>" \
  --env="AWS_SECRET_ACCESS_KEY=<secret>" \
  -- s3 ls s3://my-cnpg-backups/

# Verifica che il bucket esista e sia raggiungibile
aws s3 ls s3://my-cnpg-backups/ --region eu-west-1
```

---

### Scenario 5 — Performance I/O degradate rispetto all'atteso

**Sintomo:** Query lente, alta latenza sui write, `pg_stat_bgwriter` mostra checkpoint frequenti.

**Causa:** Storage network (EBS, Azure Disk) con latenza 1-5ms vs NVMe locale; `shared_buffers` e `checkpoint_completion_target` non ottimizzati per il volume di workload.

**Soluzione:** Profilare l'I/O del storage, ottimizzare i parametri PostgreSQL, e valutare local SSD per workload ad alto IOPS.

```bash
# Misura le performance I/O dello storage dal pod
kubectl exec -it postgres-0 -n databases -- \
  dd if=/dev/zero of=/var/lib/postgresql/data/testfile bs=1M count=1000 oflag=direct

# Query PostgreSQL per statistiche I/O
kubectl cnpg psql postgres-cluster -n databases -- \
  -c "SELECT * FROM pg_stat_bgwriter;"

# Verifica checkpoint troppo frequenti
kubectl cnpg psql postgres-cluster -n databases -- \
  -c "SELECT checkpoints_timed, checkpoints_req, checkpoint_write_time,
             checkpoint_sync_time FROM pg_stat_bgwriter;"

# Aumenta shared_buffers al 25% della RAM disponibile (via CNPG patch)
kubectl patch cluster postgres-cluster -n databases --type=merge \
  -p '{"spec":{"postgresql":{"parameters":{
    "shared_buffers":"2GB",
    "checkpoint_completion_target":"0.9",
    "wal_buffers":"64MB"
  }}}}'
```

## Riferimenti

- [CloudNativePG Documentation](https://cloudnative-pg.io/documentation/)
- [Zalando Postgres Operator](https://github.com/zalando/postgres-operator)
- [Kubernetes — StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Crunchy Postgres Operator (PGO)](https://access.crunchydata.com/documentation/postgres-operator/)
