---
title: "Kubernetes Storage"
slug: storage
category: containers
tags: [kubernetes, storage, pv, pvc, storageclass, csi, statefulset, volumes]
search_keywords: [kubernetes persistent volume, PVC PV kubernetes, StorageClass kubernetes, CSI driver kubernetes, kubernetes storage provisioning, ReadWriteMany kubernetes, kubectl storage, volume binding mode, reclaim policy kubernetes, kubernetes NFS, kubernetes EBS, kubernetes Ceph, volume snapshot kubernetes]
parent: containers/kubernetes/_index
related: [containers/kubernetes/workloads, containers/kubernetes/scheduling-avanzato]
official_docs: https://kubernetes.io/docs/concepts/storage/
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# Kubernetes Storage

## Il Modello PV/PVC/StorageClass

Kubernetes separa il provisioning dello storage (come viene creato) dall'utilizzo (come viene richiesto):

```
Kubernetes Storage Model

  StorageClass (come provisionare)
  +--------------------------------+
  | provisioner: ebs.csi.aws.com  |
  | parameters:                   |
  |   type: gp3                   |
  |   fsType: ext4                |
  | reclaimPolicy: Delete         |
  | volumeBindingMode:            |
  |   WaitForFirstConsumer        |
  +-------------+------------------+
                |
                | dynamic provisioning
                v
  PersistentVolume (cosa esiste)
  +--------------------------------+
  | capacity: 50Gi                |
  | accessModes: [RWO]            |
  | persistentVolumeReclaimPolicy:|
  |   Retain/Delete/Recycle       |
  | storageClassName: gp3         |
  | volumeMode: Filesystem/Block  |
  | csi:                         |
  |   driver: ebs.csi.aws.com    |
  |   volumeHandle: vol-0abc...  |
  +-------------+------------------+
                ^
                | binding
                |
  PersistentVolumeClaim (cosa chiede il pod)
  +--------------------------------+
  | accessModes: [ReadWriteOnce]  |
  | resources.requests.storage:   |
  |   50Gi                        |
  | storageClassName: gp3         |
  +-------------+------------------+
                ^
                | volumeMount
                |
  Pod → Container → /data
```

---

## AccessModes — Chi può Montare il Volume

| AccessMode | Abbreviazione | Semantica |
|------------|--------------|-----------|
| `ReadWriteOnce` | RWO | Montabile in R/W da UN SOLO nodo |
| `ReadOnlyMany` | ROX | Montabile in R da MOLTI nodi |
| `ReadWriteMany` | RWX | Montabile in R/W da molti nodi (NFS, CephFS, Azure Files) |
| `ReadWriteOncePod` | RWOP | Montabile in R/W da UN SOLO pod (Kubernetes 1.22+) |

```
AccessMode e Storage Backend

  EBS (AWS): solo RWO (block device, un attaccamento per volta)
  EFS (AWS): RWX (filesystem condiviso NFS-based)
  GCE PD: solo RWO
  Azure Disk: solo RWO
  Azure Files: RWX
  CephRBD: RWO
  CephFS: RWX
  NFS: RWX
  local volume: RWO (solo sul nodo dove è il disco fisico)
```

---

## StorageClass — Dynamic Provisioning

```yaml
# StorageClass AWS EBS gp3 — produzione
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"  # default SC
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4
  # gp3 performance tuning:
  iops: "3000"         # baseline 3000, max 16000
  throughput: "125"    # MB/s baseline, max 1000
  encrypted: "true"
  kmsKeyId: arn:aws:kms:eu-west-1:123456789:key/mrk-xxx
reclaimPolicy: Retain  # Delete = cancella il volume al PVC delete (pericoloso in prod)
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer  # non provisionare fino a quando il pod non viene schedulato (importante per AZ awareness)
mountOptions:
  - discard    # TRIM support per gp3 (risparmia spazio/costo)
```

```yaml
# StorageClass NFS — multi-AZ RWX
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nfs-rwx
provisioner: nfs.csi.k8s.io
parameters:
  server: nfs.internal.company.com
  share: /exports/k8s
  mountPermissions: "0755"
reclaimPolicy: Retain
volumeBindingMode: Immediate   # NFS è accessibile da qualsiasi nodo
allowVolumeExpansion: true

---
# StorageClass local — alta performance (SSD locale)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-ssd
provisioner: kubernetes.io/no-provisioner  # manuale, non dynamic
volumeBindingMode: WaitForFirstConsumer     # CRITICO: aspetta il pod
```

---

## PersistentVolume — Definizione Manuale

```yaml
# PV manuale (static provisioning) — per storage esistente
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgres-pv-eu-west-1a
  labels:
    topology.kubernetes.io/zone: eu-west-1a
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: gp3
  volumeMode: Filesystem   # Filesystem (default) | Block (raw device)
  csi:
    driver: ebs.csi.aws.com
    volumeHandle: vol-0abc123def456       # ID del volume su AWS
    fsType: ext4
    volumeAttributes:
      partition: ""
  # Node affinity per local volumes:
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: topology.kubernetes.io/zone
              operator: In
              values: [eu-west-1a]
```

---

## PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: production
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 100Gi
  # Per bind a uno specifico PV (static provisioning):
  # selector:
  #   matchLabels:
  #     topology.kubernetes.io/zone: eu-west-1a
  volumeMode: Filesystem
```

```bash
# Ciclo di vita PVC
kubectl get pvc -n production
# NAME            STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# postgres-data   Bound    pvc-abc123def456-...                       100Gi      RWO            gp3            5d

kubectl describe pvc postgres-data -n production

# Espansione del volume (storageClass deve allowVolumeExpansion: true)
kubectl patch pvc postgres-data -n production \
    -p '{"spec": {"resources": {"requests": {"storage": "200Gi"}}}}'
# → crea una request di expansion → CSI driver ridimensiona il volume
# → Per ext4/xfs: redimensionamento automatico al prossimo pod restart
# → In place (senza restart) se il CSI lo supporta
```

---

## CSI — Container Storage Interface

**CSI** è lo standard per implementare driver di storage per Kubernetes. Sostituisce i volume plugin in-tree (EBS, GCEPersistentDisk, ecc.).

```
CSI Architecture

  kubelet                    CSI Driver (Pod nel cluster)
  +----------+              +----------------------------------+
  |          |  gRPC        |  CSI Controller Plugin          |
  | node-    |<------------>|  (DeploymenSet / StatefulSet)   |
  | driver-  |              |  CreateVolume()                 |
  | registrar|              |  DeleteVolume()                 |
  |          |              |  ControllerPublishVolume()      |
  | CSI Node |  gRPC        |  (attacca volume al nodo)       |
  | Plugin   |<------------>|                                 |
  | (socket  |              |  CSI Node Plugin                |
  |  /var/   |              |  (DaemonSet su ogni nodo)       |
  |  lib/    |              |  NodeStageVolume()              |
  |  kubelet)|              |  NodePublishVolume()            |
  +----------+              |  (monta nel pod)                |
                            +----------------------------------+
                                         |
                            Storage Backend (AWS EBS, NFS, Ceph)
```

**CSI Driver comuni:**

| Driver | Provider | Funzionalità |
|--------|----------|--------------|
| `ebs.csi.aws.com` | AWS EBS | Block storage, snapshot, resize |
| `efs.csi.aws.com` | AWS EFS | NFS RWX, multi-AZ |
| `disk.csi.azure.com` | Azure Disk | Block storage, snapshot |
| `file.csi.azure.com` | Azure Files | SMB/NFS RWX |
| `pd.csi.storage.gke.io` | GCE PD | Block storage, regional PD |
| `cephfs.csi.ceph.com` | CephFS | RWX filesystem |
| `rbd.csi.ceph.com` | Ceph RBD | Block storage RWO |
| `nfs.csi.k8s.io` | NFS | NFS RWX generico |

---

## Volume Snapshots

```yaml
# VolumeSnapshotClass
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: csi-aws-vsc
driver: ebs.csi.aws.com
deletionPolicy: Delete   # Delete | Retain
parameters:
  tagSpecification_1: "kubernetes:true"

---
# VolumeSnapshot — crea uno snapshot da un PVC
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-data-snapshot-20260225
  namespace: production
spec:
  volumeSnapshotClassName: csi-aws-vsc
  source:
    persistentVolumeClaimName: postgres-data

---
# Restore da snapshot (PVC da snapshot)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data-restored
  namespace: production
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 100Gi
  dataSource:
    name: postgres-data-snapshot-20260225
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

---

## Volume Populators e Data Sources

```yaml
# PVC clonata da un'altra PVC (stesso StorageClass, stesso namespace)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data-clone
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 100Gi   # >= dimensione sorgente
  dataSource:
    kind: PersistentVolumeClaim
    name: postgres-data   # PVC esistente
```

---

## StatefulSet Storage — Ciclo di Vita PVC

```bash
# I PVC dei StatefulSet NON vengono eliminati con il StatefulSet (sicurezza)
kubectl delete statefulset postgres    # cancella i pod ma NON i PVC
kubectl get pvc -n production
# NAME                STATUS   VOLUME   CAPACITY   ...
# data-postgres-0    Bound    ...      50Gi       ← rimane
# data-postgres-1    Bound    ...      50Gi       ← rimane

# Per eliminare manualmente (DESTRUCTIVE)
kubectl delete pvc data-postgres-0 data-postgres-1 data-postgres-2

# Per mantenere i dati ma eliminare il StatefulSet e ricrearlo:
kubectl delete statefulset postgres --cascade=orphan
# → elimina solo il StatefulSet object, i pod rimangono
# → i PVC rimangono
# → rideployando lo StatefulSet, i pod riutilizzano i PVC esistenti
```

---

## Local Volumes — Performance Massima

```yaml
# Local PV — per database che richiedono I/O massimo
apiVersion: v1
kind: PersistentVolume
metadata:
  name: local-pv-worker-1
spec:
  capacity:
    storage: 1Ti
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-ssd
  volumeMode: Block   # raw block device (per DB che gestiscono loro il FS)
  local:
    path: /dev/nvme1n1   # SSD locale sul nodo
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values: [worker-1]
```

!!! warning "Local Volumes e HA"
    I local volume sono legati fisicamente a un nodo. Se il nodo muore, i dati sono irraggiungibili fino a quando il nodo non torna online. **Non adatti per applicazioni critiche senza replica applicativa.** Usare per database che implementano la propria replica (Cassandra, TiKV, Raft-based DBs).

---

## Riferimenti

- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [CSI Drivers](https://kubernetes-csi.github.io/docs/)
- [Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
- [Local Volumes](https://kubernetes.io/docs/concepts/storage/volumes/#local)
