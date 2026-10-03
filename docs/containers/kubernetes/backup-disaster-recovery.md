---
title: "Kubernetes Backup & Disaster Recovery"
slug: backup-disaster-recovery
category: containers
tags: [kubernetes, backup, disaster-recovery, velero, etcd, snapshots, restore, rpo-rto]
search_keywords: [kubernetes backup, k8s backup, kubernetes disaster recovery, k8s DR, velero, velero backup, velero restore, velero schedule, BackupStorageLocation, BSL, VolumeSnapshotLocation, etcd snapshot, etcdctl snapshot save, etcdutl snapshot restore, etcd backup, etcd restore, CSI snapshot, VolumeSnapshot, kopia, restic, node-agent, file system backup, FSB, data mover, RPO, RTO, warm standby, cold standby, pilot light, cross-region restore, cluster migration, backup hook, fsfreeze, namespace remapping, game day, restore test, cluster recovery, backup PersistentVolume, kubeadm etcd restore, EKS backup, AKS backup, GKE backup for GKE, Kasten K10, cluster state backup]
parent: containers/kubernetes/_index
related: [containers/kubernetes/storage, containers/kubernetes/architettura, containers/kubernetes/multi-cluster, containers/kubernetes/troubleshooting, databases/kubernetes-cloud/db-su-kubernetes, databases/replicazione-ha/backup-pitr, ci-cd/gitops/argocd]
official_docs: https://velero.io/docs/
status: complete
difficulty: advanced
last_updated: 2026-10-03
---

# Kubernetes Backup & Disaster Recovery

## Panoramica

Un cluster Kubernetes contiene tre tipi di stato con ciclo di vita diverso: lo **stato del control plane** (etcd), le **risorse dichiarative** (Deployment, Service, CRD, RBAC, ConfigMap, Secret) e i **dati applicativi** (contenuto dei PersistentVolume e dei database). Backup e Disaster Recovery (DR) servono a ricostruire tutti e tre dopo cancellazioni accidentali, corruzione, errori di upgrade, ransomware o perdita di una region.

Due strumenti coprono la maggior parte dei casi: gli **snapshot di etcd** (recupero completo del cluster self-managed, granularità cluster intero) e **Velero** (backup/restore a livello di namespace/risorsa/volume, anche cross-cluster). Nessuno dei due sostituisce una strategia DR: servono obiettivi di **RPO/RTO** espliciti, backup in uno storage esterno al cluster (e idealmente a una region/account diverso) e soprattutto **restore testati periodicamente**.

Quando NON basta: un database con requisiti di PITR stringenti richiede il backup nativo del DB (WAL archiving) oltre allo snapshot del volume — vedi [Backup e PITR](../../databases/replicazione-ha/backup-pitr.md).

## Concetti Chiave

### Cosa va protetto

| Livello | Contenuto | Dove vive | Strumento tipico |
|---|---|---|---|
| Control plane | Tutti gli oggetti API serializzati | etcd (solo cluster self-managed) | `etcdctl`/`etcdutl snapshot` |
| Risorse API | Manifest, CRD, RBAC, ConfigMap, Secret | etcd / repository Git | Velero, GitOps |
| Dati persistenti | Contenuto dei PV (DB, file, code) | Storage backend (EBS, Ceph, NFS...) | CSI snapshot, Velero FSB |
| Configurazione esterna | DNS, LB, IAM, certificati, KMS | Cloud provider | IaC (Terraform), backup specifico |

!!! warning "GitOps NON è un backup"
    Con [ArgoCD](../../ci-cd/gitops/argocd.md) il repository Git ricostruisce le **risorse dichiarative**, ma non i **dati dei PersistentVolume**, non i Secret generati a runtime (es. certificati emessi da cert-manager, token di ServiceAccount), non le risorse create fuori da Git (CRD di operatori, PVC dinamici) e non lo stato interno dei database. GitOps copre il "cosa deve girare", il backup copre il "cosa contenevano i dati".

### RPO e RTO

!!! note "Definizioni"
    - **RPO (Recovery Point Objective)**: quanta perdita di dati è tollerabile, misurata in tempo. Determina la frequenza dei backup.
    - **RTO (Recovery Time Objective)**: quanto tempo può durare il ripristino. Determina il pattern DR (cold/warm/hot).

### Oggetti Velero

| CRD | Ruolo |
|---|---|
| `Backup` | Richiesta one-shot di backup (selettori namespace/label, TTL, hook) |
| `Schedule` | Genera `Backup` periodici da un template (cron) |
| `Restore` | Ripristino da un `Backup`, con filtri e remapping |
| `BackupStorageLocation` (BSL) | Bucket object storage dove finiscono i tarball di manifest e metadata |
| `VolumeSnapshotLocation` (VSL) | Dove vengono creati gli snapshot nativi del provider (non serve con CSI) |
| `PodVolumeBackup` / `PodVolumeRestore` | Backup file-system di un volume via node-agent |
| `DataUpload` / `DataDownload` | Data mover: sposta il contenuto di uno snapshot CSI nell'object storage |

## Architettura / Come Funziona

### Backup di etcd

etcd contiene **tutto** lo stato del cluster. Uno snapshot è consistente (point-in-time) ed è il modo più rapido per ripristinare un cluster self-managed (kubeadm, RKE2, k3s con etcd). Non cattura i dati dei PV.

Nei servizi **managed** (EKS, AKS, GKE) etcd non è accessibile: il provider lo gestisce e lo replica, ma **non offre restore self-service** di singoli oggetti. Il backup delle risorse e dei dati si fa quindi a livello API con Velero (o prodotti nativi come *Backup for GKE*, *AKS Backup*, *AWS Backup for EKS*).

### Come Velero esegue un backup

1. Il client `velero` (o un `Schedule`) crea un oggetto `Backup`.
2. Il controller interroga l'API server, serializza in JSON le risorse selezionate e le carica come tarball nel bucket del BSL.
3. Per ogni PVC dei Pod selezionati sceglie la strategia volumi:
    - **CSI snapshot**: crea un `VolumeSnapshot` (richiede `external-snapshotter` e una `VolumeSnapshotClass` con label `velero.io/csi-volumesnapshot-class: "true"`). Lo snapshot resta nello storage del provider (stessa region/zona del volume).
    - **CSI snapshot + data mover** (`snapshotMoveData: true`): il contenuto dello snapshot viene copiato nel bucket (Kopia), rendendo il backup portabile cross-region/cross-cloud.
    - **File-system backup (FSB)**: il `node-agent` (DaemonSet) legge il filesystem montato dal Pod e lo carica con **Kopia** (Restic è deprecato nelle versioni recenti). Funziona con qualunque tipo di volume, ma è meno consistente e più lento.
4. Esegue gli eventuali **hook** pre/post nei container.

!!! info "Snapshot vs backup"
    Uno snapshot CSI che resta sullo stesso storage backend **non protegge** da perdita del backend o della region. Per un vero DR serve una copia in un luogo indipendente (data mover, replica cross-region, copia dello snapshot).

### Pattern DR

| Pattern | RTO | Costo | Descrizione |
|---|---|---|---|
| **Backup & restore (cold)** | ore | basso | Nessun cluster secondario; in caso di disastro si crea un cluster (IaC) e si fa il restore |
| **Pilot light** | 30-60 min | medio | Cluster minimo già pronto con add-on e operatori; dati ripristinati o replicati; scale-up al failover |
| **Warm standby** | minuti-30 min | alto | Cluster secondario ridotto, restore continuo da backup frequenti o replica dati |
| **Active/active** | ~0 | molto alto | Due cluster attivi con traffico bilanciato — vedi [Multi-cluster](multi-cluster.md) |

## Configurazione & Pratica

### Snapshot etcd (kubeadm)

```bash
# Su un nodo control plane. I certificati sono quelli del Pod etcd statico.
export ETCDCTL_API=3
etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  snapshot save /backup/etcd-$(date +%Y%m%d-%H%M).db

# Verifica integrità (da etcd 3.5 si usa etcdutl per operazioni offline)
etcdutl snapshot status /backup/etcd-20261002-0300.db --write-out=table
```

Automazione minima con un CronJob sul control plane (sempre con copia fuori dal nodo):

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: etcd-backup
  namespace: kube-system
spec:
  schedule: "0 */4 * * *"          # RPO control plane = 4h
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          hostNetwork: true
          nodeSelector:
            node-role.kubernetes.io/control-plane: ""
          tolerations:
            - key: node-role.kubernetes.io/control-plane
              operator: Exists
              effect: NoSchedule
          restartPolicy: OnFailure
          containers:
            - name: backup
              image: registry.k8s.io/etcd:3.5.15-0   # stessa versione del cluster
              command: ["/bin/sh", "-c"]
              args:
                - |
                  etcdctl --endpoints=https://127.0.0.1:2379 \
                    --cacert=/pki/ca.crt --cert=/pki/server.crt --key=/pki/server.key \
                    snapshot save /backup/etcd-$(date +%Y%m%d-%H%M).db
              volumeMounts:
                - {name: pki, mountPath: /pki, readOnly: true}
                - {name: backup, mountPath: /backup}
          volumes:
            - name: pki
              hostPath: {path: /etc/kubernetes/pki/etcd}
            - name: backup
              hostPath: {path: /var/backups/etcd, type: DirectoryOrCreate}
```

!!! tip "Esportare lo snapshot"
    Il file su hostPath è inutile se il nodo muore. Aggiungere uno step di upload (es. `aws s3 cp`, `rclone`) con cifratura e retention, oppure montare uno storage esterno.

### Restore di etcd (kubeadm, single control plane)

```bash
# 1. Fermare l'API server e etcd spostando i manifest degli static pod
mkdir -p /etc/kubernetes/manifests-stopped
mv /etc/kubernetes/manifests/kube-apiserver.yaml /etc/kubernetes/manifests/etcd.yaml \
   /etc/kubernetes/manifests-stopped/

# 2. Ripristinare lo snapshot in una nuova data-dir
etcdutl snapshot restore /backup/etcd-20261002-0300.db \
  --data-dir /var/lib/etcd-restore

# 3. Puntare il manifest di etcd alla nuova directory
#    (campo volumes.hostPath.path: /var/lib/etcd -> /var/lib/etcd-restore)
sed -i 's#/var/lib/etcd$#/var/lib/etcd-restore#' \
  /etc/kubernetes/manifests-stopped/etcd.yaml

# 4. Riavviare i componenti
mv /etc/kubernetes/manifests-stopped/*.yaml /etc/kubernetes/manifests/
kubectl get nodes
```

!!! warning "Cluster etcd multi-membro"
    Con 3+ control plane il restore va eseguito su **tutti** i membri con lo stesso snapshot e con i parametri `--name`, `--initial-cluster`, `--initial-advertise-peer-urls` corretti (nuovo `--initial-cluster-token`). Ripristinare un solo membro causa split-brain. Lo stato ripristinato è quello di T0: i Pod e i nodi nati dopo possono risultare orfani e vanno riconciliati.

### Installare Velero (AWS, CSI + node-agent)

```bash
# Credenziali IAM (o meglio IRSA / Pod Identity, evitando chiavi statiche)
cat > credentials-velero <<EOF
[default]
aws_access_key_id=AKIA...
aws_secret_access_key=...
EOF

velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:vX.Y.Z \
  --features=EnableCSI \
  --bucket kb-velero-backups \
  --backup-location-config region=eu-west-1 \
  --secret-file ./credentials-velero \
  --use-node-agent \
  --default-volumes-to-fs-backup=false

velero backup-location get          # PHASE deve essere Available
```

Le versioni dei plugin vanno scelte dalla matrice di compatibilità della release Velero (non usare `latest` in produzione). Azure e GCP usano gli analoghi `velero-plugin-for-microsoft-azure` e `velero-plugin-for-gcp`.

### Backup e Schedule

```bash
# Backup on-demand di un namespace
velero backup create shop-$(date +%Y%m%d) \
  --include-namespaces shop \
  --snapshot-move-data \
  --ttl 720h
velero backup describe shop-20261002 --details
velero backup logs shop-20261002
```

```yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: shop-daily
  namespace: velero
spec:
  schedule: "0 2 * * *"            # ogni giorno alle 02:00 (UTC)
  useOwnerReferencesInBackup: false
  template:
    includedNamespaces: ["shop"]
    excludedResources: ["events"]
    snapshotVolumes: true
    snapshotMoveData: true         # copia i dati nel bucket (portabile cross-region)
    ttl: 720h0m0s                  # retention 30 giorni
    storageLocation: default
    hooks:
      resources:
        - name: postgres-quiesce
          includedNamespaces: ["shop"]
          labelSelector:
            matchLabels: {app: postgres}
          pre:
            - exec:
                container: postgres
                command: ["/bin/bash", "-c", "psql -U postgres -c 'CHECKPOINT;'"]
                onError: Fail
                timeout: 60s
```

### Hook tramite annotation (fsfreeze)

Gli hook si possono definire anche sul Pod, senza modificare il `Backup`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-volume
  annotations:
    pre.hook.backup.velero.io/container: fsfreeze
    pre.hook.backup.velero.io/command: '["/sbin/fsfreeze", "--freeze", "/data"]'
    post.hook.backup.velero.io/container: fsfreeze
    post.hook.backup.velero.io/command: '["/sbin/fsfreeze", "--unfreeze", "/data"]'
    backup.velero.io/backup-volumes: data   # opt-in FSB per questo volume
spec:
  containers:
    - name: app
      image: nginx
      volumeMounts: [{name: data, mountPath: /data}]
    - name: fsfreeze
      image: ubuntu:24.04
      securityContext: {privileged: true}
      command: ["/bin/sleep", "infinity"]
      volumeMounts: [{name: data, mountPath: /data}]
  volumes:
    - name: data
      persistentVolumeClaim: {claimName: data-pvc}
```

!!! warning "Consistenza dei database"
    Uno snapshot di volume "crash-consistent" di un database può richiedere recovery all'avvio, e in casi limite essere inutilizzabile. Per Postgres/MySQL usare hook di quiesce (`pg_backup_start`/`CHECKPOINT`, `FLUSH TABLES WITH READ LOCK`) oppure il backup nativo dell'operatore (es. CloudNativePG con barman) e considerare lo snapshot di Velero come seconda linea. Dettagli in [Database su Kubernetes](../../databases/kubernetes-cloud/db-su-kubernetes.md).

### Restore

```bash
# Restore completo
velero restore create --from-backup shop-20261002

# Restore parziale e in un nuovo namespace (clone / test)
velero restore create shop-restore-test \
  --from-backup shop-20261002 \
  --include-resources deployments,services,persistentvolumeclaims,secrets,configmaps \
  --namespace-mappings shop:shop-restore \
  --preserve-nodeports=false

velero restore describe shop-restore-test --details
kubectl -n shop-restore get pods,pvc
```

Remapping delle StorageClass (utile in migrazioni o DR su cloud diverso):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: change-storage-class-config
  namespace: velero
  labels:
    velero.io/plugin-config: ""
    velero.io/change-storage-class: RestoreItemAction
data:
  gp2: gp3                 # StorageClass sorgente: destinazione
  managed-premium: premium-ssd-v2
```

### Restore su cluster nuovo (DR cross-region)

```bash
# Sul cluster di DR: stesso BSL in sola lettura, così i backup sono visibili
velero install ... --bucket kb-velero-backups --backup-location-config region=eu-west-1
velero backup-location set default --access-mode=ReadOnly   # evita sovrascritture
velero backup get                                           # sincronizzazione automatica dal bucket
velero restore create dr-$(date +%Y%m%d) --from-backup shop-20261002
```

## Best Practices

- **Regola 3-2-1**: 3 copie, 2 media/sistemi diversi, 1 off-site (altra region/account). Abilitare Object Lock/immutabilità sul bucket contro ransomware.
- **Backup in account/progetto separato** da quello del cluster: un'identità compromessa nel cluster non deve poter cancellare i backup.
- **Frequenza = RPO**: etcd ogni 1-4 h; Velero giornaliero/orario per i dati critici; DB con WAL archiving per RPO di secondi.
- **TTL esplicito** su ogni `Backup`/`Schedule` (`ttl`), con retention coerente con i requisiti di compliance.
- **Cifrare** bucket e snapshot (KMS); i Secret finiscono nei tarball in chiaro (base64) se il bucket non è cifrato.
- **Includere i prerequisiti nel DR**: CRD e operatori installati prima del restore (ordine: CRD → operatori → namespace applicativi), versioni compatibili.
- **Monitorare i backup**: metriche Prometheus di Velero (`velero_backup_failure_total`, `velero_backup_last_successful_timestamp`) con alert se il backup non riesce da > 2 intervalli.
- **Automatizzare il cluster**: DR realistico richiede IaC (Terraform) per ricreare cluster, rete, IAM; Velero ripristina solo ciò che sta *dentro* il cluster.
- **Game day**: restore trimestrale in un cluster/namespace isolato, misurando RTO reale e validando i dati; registrare il runbook.

!!! tip "Runbook minimo di DR"
    1) Dichiarare l'incidente e fissare il punto di ripristino. 2) Creare il cluster da IaC. 3) Installare Velero con BSL `ReadOnly`. 4) Ripristinare CRD/operatori e poi i namespace per priorità. 5) Verificare PVC `Bound`, Pod `Ready`, smoke test applicativi. 6) Spostare DNS/traffico. 7) Post-mortem e aggiornamento del runbook.

## Troubleshooting

### Scenario 1 — Backup in stato `PartiallyFailed`

**Sintomo**: `velero backup describe` mostra `Phase: PartiallyFailed` ed `Errors: N`.

**Causa**: alcune risorse o volumi non sono stati salvati (permessi RBAC, hook falliti, snapshot non riuscito, API di CRD non più servita).

**Soluzione**:

```bash
velero backup describe <nome> --details
velero backup logs <nome> | grep -iE "error|level=error"
kubectl -n velero logs deploy/velero | tail -100
```
Correggere la causa (spesso hook con `onError: Fail` o timeout) e rilanciare il backup. Un backup `PartiallyFailed` **è ripristinabile solo per le parti salvate**: non considerarlo valido per il DR.

### Scenario 2 — Volumi non inclusi nel backup

**Sintomo**: il restore crea i PVC vuoti o li omette.

**Causa**: il PVC non ha `VolumeSnapshotClass` etichettata, il driver CSI non supporta snapshot, oppure con FSB il volume non è stato opt-in (`--default-volumes-to-fs-backup` assente e nessuna annotation `backup.velero.io/backup-volumes`).

**Soluzione**:

```bash
kubectl get volumesnapshotclass -o yaml | grep -B3 velero.io/csi-volumesnapshot-class
kubectl -n shop get pod <pod> -o jsonpath='{.metadata.annotations}'
velero backup describe <nome> --details | sed -n '/Volumes:/,$p'
```
Etichettare la `VolumeSnapshotClass` o attivare l'FSB. I volumi `emptyDir`, `hostPath` e i `projected` non vengono salvati come dati.

### Scenario 3 — Restore che lascia i PVC in `Pending`

**Sintomo**: `kubectl get pvc` mostra `Pending` dopo il restore.

**Causa**: la StorageClass originale non esiste sul cluster di destinazione, `volumeBindingMode: WaitForFirstConsumer` senza Pod schedulabili, zona diversa per il volume.

**Soluzione**: creare la StorageClass mancante o usare la ConfigMap `change-storage-class`; verificare gli eventi `ProvisioningFailed`. Vedi [Storage](storage.md).

```bash
kubectl describe pvc <nome> -n shop-restore | sed -n '/Events:/,$p'
kubectl get storageclass
```

### Scenario 4 — BSL in stato `Unavailable`

**Sintomo**: `velero backup-location get` mostra `Unavailable`, i backup restano in `New`/`FailedValidation`.

**Causa**: Secret delle credenziali errato o scaduto, bucket inesistente, policy IAM senza `s3:PutObject/GetObject/DeleteObject/ListBucket`, endpoint o region sbagliata.

**Soluzione**:

```bash
kubectl -n velero get secret cloud-credentials -o jsonpath='{.data.cloud}' | base64 -d
kubectl -n velero logs deploy/velero | grep -i "backup store"
velero backup-location get
```
Aggiornare il Secret e riavviare il Deployment `velero`. Preferire identità federate (IRSA, Workload Identity) alle chiavi statiche, che scadono o ruotano.

### Scenario 5 — Restore con errori su CRD / versioni API

**Sintomo**: `Restore` in `PartiallyFailed` con `no matches for kind "X" in version "Y"` o `the server could not find the requested resource`.

**Causa**: il cluster di destinazione ha una versione di Kubernetes diversa (API rimosse) o i CRD non sono ancora installati.

**Soluzione**: installare prima operatori/CRD (via Helm/ArgoCD), poi lanciare il restore; Velero ripristina la versione preferita dell'API (`EnableAPIGroupVersions` aiuta tra versioni). Per upgrade difficili ripristinare prima su un cluster di staging della stessa versione.

```bash
velero restore describe <nome> --details | grep -i "no matches"
kubectl api-resources | grep -i <kind>
```

### Scenario 6 — Restore che salta oggetti esistenti

**Sintomo**: `Warning: already exists` nel log del restore, risorse non aggiornate.

**Causa**: comportamento standard, Velero non modifica risorse esistenti (`--existing-resource-policy=none`) per non sovrascrivere stato vivo.

**Soluzione**: usare `--existing-resource-policy=update` oppure eliminare prima il namespace.

```bash
velero restore create --from-backup shop-20261002 --existing-resource-policy=update
```

## Relazioni

??? info "Storage Kubernetes — Approfondimento"
    PV, PVC, StorageClass e `VolumeSnapshot` sono la base del backup dei dati: senza driver CSI con supporto snapshot si ricade nel file-system backup.

    **Approfondimento completo →** [Kubernetes Storage](storage.md)

??? info "Architettura — etcd e control plane"
    etcd è il datastore del control plane; la sua natura (Raft, quorum) determina come si esegue e si ripristina uno snapshot.

    **Approfondimento completo →** [Architettura Kubernetes](architettura.md)

??? info "Multi-cluster — DR attivo/standby"
    I pattern warm standby e active/active si appoggiano a topologie multi-cluster e al failover del traffico.

    **Approfondimento completo →** [Multi-cluster](multi-cluster.md)

??? info "Database su Kubernetes e PITR"
    Per i dati transazionali il backup applicativo (WAL, PITR) affianca quello del volume.

    **Approfondimento completo →** [Database su Kubernetes](../../databases/kubernetes-cloud/db-su-kubernetes.md) · [Backup e PITR](../../databases/replicazione-ha/backup-pitr.md)

??? info "GitOps — ricostruzione dichiarativa"
    ArgoCD riapplica le risorse da Git dopo il ripristino del cluster, riducendo la superficie da coprire con Velero.

    **Approfondimento completo →** [ArgoCD](../../ci-cd/gitops/argocd.md)

## Riferimenti

- [Velero — documentazione ufficiale](https://velero.io/docs/)
- [Velero — CSI snapshot data movement](https://velero.io/docs/main/csi-snapshot-data-mover/)
- [Velero — Backup hooks](https://velero.io/docs/main/backup-hooks/)
- [Kubernetes — Operating etcd clusters (backup e restore)](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/)
- [Kubernetes — Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
- [etcd — Disaster recovery](https://etcd.io/docs/latest/op-guide/recovery/)
