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
last_updated: 2026-03-29
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

## Troubleshooting

### Scenario 1 — PVC bloccato in stato `Pending`

**Sintomo:** Il PVC non diventa `Bound`, rimane `Pending` indefinitamente.

**Causa:** Può dipendere da più cause: nessuna StorageClass default, `volumeBindingMode: WaitForFirstConsumer` senza pod associato, provisioner CSI non disponibile, o mismatch tra richiesta e PV disponibili.

**Soluzione:**
```bash
# Ispeziona gli eventi del PVC
kubectl describe pvc <nome-pvc> -n <namespace>
# Cerca: "no persistent volumes available" / "no nodes available" / "waiting for first consumer"

# Verifica la StorageClass default
kubectl get storageclass
# La SC default ha l'annotation: storageclass.kubernetes.io/is-default-class: "true"

# Controlla i log del CSI controller
kubectl logs -n kube-system -l app=ebs-csi-controller -c csi-provisioner --tail=50

# Se il PV è manual/static, verifica che status sia Available (non Bound ad altro PVC)
kubectl get pv
```

---

### Scenario 2 — Pod bloccato in `ContainerCreating` con errore di mount

**Sintomo:** Il pod rimane in `ContainerCreating` per minuti, `kubectl describe pod` mostra errori come `Unable to attach or mount volumes`.

**Causa:** Il volume è ancora attaccato al nodo precedente (Volume Attach Error), il nodo target non è raggiungibile, oppure il CSI node plugin non è in esecuzione sul nodo.

**Soluzione:**
```bash
# Ispeziona il pod
kubectl describe pod <nome-pod> -n <namespace>
# Cerca: "Multi-Attach error" / "timed out waiting for the condition"

# Verifica il CSI node plugin sul nodo target
kubectl get pods -n kube-system -l app=ebs-csi-node -o wide
# Deve esserci un pod su ogni nodo

# In caso di Multi-Attach error (volume ancora legato al vecchio nodo):
# Attendi che k8s rilevi il nodo come NotReady (default ~5 min)
# Oppure verifica e forza il detach tramite cloud console (es. AWS EC2 → Volumes)

# Verifica lo stato del VolumeAttachment
kubectl get volumeattachment
kubectl describe volumeattachment <nome>
```

---

### Scenario 3 — Espansione PVC fallita o non applicata al filesystem

**Sintomo:** Dopo il patch del PVC la `CAPACITY` non aumenta, oppure il PVC mostra `FileSystemResizePending` ma il filesystem nel pod è ancora alla dimensione originale.

**Causa:** La StorageClass non ha `allowVolumeExpansion: true`, oppure il CSI ha ridimensionato il volume ma il filesystem necessita di un restart del pod per essere ridimensionato in-pod.

**Soluzione:**
```bash
# Controlla lo stato dell'espansione
kubectl describe pvc <nome-pvc> -n <namespace>
# Cerca: "Resizing" / "FileSystemResizePending" nelle Conditions

# Verifica che la StorageClass supporti l'espansione
kubectl get storageclass <nome-sc> -o yaml | grep allowVolumeExpansion

# Se FileSystemResizePending: riavvia il pod per triggerare il resize del FS
kubectl rollout restart deployment/<nome-deploy> -n <namespace>
# Oppure per StatefulSet:
kubectl rollout restart statefulset/<nome-sts> -n <namespace>

# Verifica dimensione FS nel pod dopo restart
kubectl exec -n <namespace> <nome-pod> -- df -h /data
```

---

### Scenario 4 — PV rimasto in stato `Released` e non riutilizzabile

**Sintomo:** Un PV ha `reclaimPolicy: Retain` e dopo la cancellazione del PVC rimane in stato `Released`. Un nuovo PVC non riesce a fare bind a quel PV.

**Causa:** Lo stato `Released` indica che il PV aveva un riferimento a un PVC precedente (`claimRef`) che impedisce il binding a nuovi PVC. Kubernetes non fa bind automatico di PV in stato `Released`.

**Soluzione:**
```bash
# Verifica lo stato e il claimRef
kubectl describe pv <nome-pv>
# Cerca: "claimRef" con namespace/name del vecchio PVC

# Rimuovi il claimRef per rendere il PV Available
kubectl patch pv <nome-pv> -p '{"spec":{"claimRef": null}}'

# Il PV torna in stato Available e può essere riutilizzato
kubectl get pv <nome-pv>
# STATUS: Available

# Poi crea o aggiorna il PVC per fare il bind (usa selector se necessario)
```

!!! warning "Attenzione"
    Prima di eseguire `patch claimRef: null`, verifica che i dati nel PV non siano necessari o siano già stati salvati. L'operazione non cancella i dati, ma consente il loro sovrascrittura da parte di un nuovo PVC.

---

## Riferimenti

- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [CSI Drivers](https://kubernetes-csi.github.io/docs/)
- [Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
- [Local Volumes](https://kubernetes.io/docs/concepts/storage/volumes/#local)
