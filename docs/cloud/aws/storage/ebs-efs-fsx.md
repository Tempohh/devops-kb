---
title: "EBS, EFS, FSx, Storage Gateway e Snow Family"
slug: ebs-efs-fsx
category: cloud
tags: [aws, ebs, efs, fsx, storage-gateway, snow-family, block-storage, file-storage, ebs-snapshots, dlm, snowball, snowcone, snowmobile]
search_keywords: [ebs, elastic block store, efs, elastic file system, fsx, fsx lustre, fsx windows, fsx ontap, fsx openzfs, storage gateway, file gateway, volume gateway, tape gateway, snow family, snowball edge, snowcone, snowmobile, gp3, gp2, io2, io1, st1, sc1, multi attach, fast snapshot restore, nfs, smb, iscsi, hpc, active directory, worm, dlm, data lifecycle manager]
parent: cloud/aws/storage/_index
related: [cloud/aws/storage/s3, cloud/aws/compute/ec2, cloud/aws/database/rds-aurora, cloud/aws/security/kms-secrets]
official_docs: https://docs.aws.amazon.com/ebs/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# EBS, EFS, FSx, Storage Gateway e Snow Family

## Panoramica

Questo documento copre tutti i servizi di storage AWS al di fuori di S3: storage a blocchi (EBS) per istanze EC2, file system condivisi (EFS e FSx per diversi workload), il bridge ibrido tra on-premises e cloud (Storage Gateway), e la migrazione fisica di dati su larga scala (Snow Family).

---

## Amazon EBS — Elastic Block Store

EBS fornisce volumi di storage a blocchi persistenti per le istanze EC2. Funziona come un disco rigido virtuale: può essere formattato con qualsiasi file system (ext4, xfs, NTFS) e montato su un'istanza.

**Caratteristiche fondamentali:**
- **Scoped a una singola Availability Zone** — un volume EBS può essere attaccato solo a istanze nella stessa AZ
- **Persistente** — i dati sopravvivono al riavvio e allo stop dell'istanza
- **Detachable** — può essere staccato da un'istanza e riattaccato a un'altra (nella stessa AZ)
- **Dimensione:** da 1 GiB fino a 64 TiB (gp3 e io2 Block Express; gp2, io1, st1, sc1 fino a 16 TiB)

!!! warning "EBS è AZ-locked"
    Se si vuole spostare un volume EBS in un'altra AZ o Region, bisogna creare uno snapshot e poi creare un nuovo volume dallo snapshot nella AZ/Region di destinazione.

### Tipi di Volume EBS

| Tipo | Categoria | IOPS Max | Throughput Max | Capacità | Prezzo Base | Use Case |
|------|-----------|---------|---------------|---------|-------------|---------|
| **gp3** | SSD General Purpose | 80.000 | 2.000 MiB/s | 1 GiB–64 TiB | $0.08/GB/mese | Default per quasi tutto |
| **gp2** | SSD General Purpose | 16.000 | 250 MB/s | 1 GB–16 TB | $0.10/GB/mese | Legacy (preferire gp3) |
| **io2 Block Express** | SSD Provisioned IOPS | 256.000 | 4.000 MB/s | 4 GB–64 TB | $0.125/GB + $0.065/IOPS | DB mission-critical, SAP |
| **io1** | SSD Provisioned IOPS | 64.000 | 1.000 MB/s | 4 GB–16 TB | $0.125/GB + $0.065/IOPS | Database ad alte IOPS |
| **st1** | HDD Throughput Optimized | 500 (burst) | 500 MB/s | 125 GB–16 TB | $0.045/GB/mese | Big data, Hadoop, log sequenziali |
| **sc1** | HDD Cold | 250 (burst) | 250 MB/s | 125 GB–16 TB | $0.015/GB/mese | Dati freddi, costo più basso |

*Prezzi approssimativi us-east-1.*

### gp3 vs gp2 — Differenze Critiche

**gp2:**
- IOPS **legati alla dimensione**: 3 IOPS per GB (baseline), burst fino a 3.000 IOPS per volumi < 1 TB
- Per avere 16.000 IOPS con gp2 → serve un volume da 5.333 GB
- Throughput limitato a 250 MB/s

**gp3:**
- IOPS **separati dalla dimensione**: baseline 3.000 IOPS (gratis, indipendentemente dal size)
- IOPS configurabili a pagamento oltre i 3.000 inclusi ($0.005/IOPS provisioned sopra i 3.000), fino a 80.000 IOPS (volumi ≥ 160 GiB)
- Throughput: baseline 125 MiB/s incluso, configurabile a pagamento fino a 2.000 MiB/s (richiede ≥ 8.000 IOPS e ≥ 16 GiB; rapporto 0,25 MiB/s per IOPS)
- Il rapporto IOPS/GiB è limitato (max 500 IOPS per GiB provisioned)
- Su AWS Outposts gp3 resta limitato a 16 TiB, 16.000 IOPS e 1.000 MiB/s

!!! note "Come si ottiene la performance"
    Su gp2 le IOPS dipendono dalla dimensione perché il volume accumula crediti burst in un bucket (BurstBalance) proporzionale ai GB. gp3 elimina il bucket: IOPS e throughput sono provisioned indipendentemente dalla capacità, quindi la performance è prevedibile e non esiste più il rischio di esaurire il burst.
- Sempre più economico di gp2 a parità di prestazioni

!!! tip "Migra da gp2 a gp3"
    gp3 offre sempre performance uguali o migliori a costo inferiore rispetto a gp2. La migrazione è online (no downtime) tramite Elastic Volumes.

```bash
# Creare un volume gp3 con IOPS personalizzati
aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 100 \
  --volume-type gp3 \
  --iops 6000 \
  --throughput 500 \
  --encrypted \
  --kms-key-id alias/my-ebs-key

# Modificare un volume gp2 esistente a gp3 (Elastic Volumes — online!)
aws ec2 modify-volume \
  --volume-id vol-1234567890abcdef0 \
  --volume-type gp3 \
  --iops 3000 \
  --throughput 125

# Verificare lo stato della modifica
aws ec2 describe-volumes-modifications \
  --volume-ids vol-1234567890abcdef0

# Allegare un volume a un'istanza
aws ec2 attach-volume \
  --volume-id vol-1234567890abcdef0 \
  --instance-id i-1234567890abcdef0 \
  --device /dev/xvdf

# Dopo l'attach, formattare e montare (su Linux)
# Su istanze Nitro il device appare come /dev/nvme1n1, non /dev/xvdf: verificare con lsblk
lsblk
sudo mkfs -t xfs /dev/nvme1n1
sudo mkdir /data
sudo mount /dev/nvme1n1 /data
# Per mount persistente al reboot usare l'UUID (i nomi device NVMe possono cambiare tra reboot)
UUID=$(sudo blkid -s UUID -o value /dev/nvme1n1)
echo "UUID=$UUID /data xfs defaults,nofail 0 2" | sudo tee -a /etc/fstab
```

### Multi-Attach (io1/io2)

I volumi io1 e io2 (non gp3/gp2) supportano Multi-Attach: lo stesso volume può essere attaccato a **più istanze EC2 contemporaneamente nella stessa AZ** (fino a 16 istanze).

**Requisiti e limitazioni:**
- Solo istanze basate su Nitro
- Tutte le istanze nella stessa AZ del volume
- Il file system usato deve supportare la gestione dei cluster (es. GFS2, OCFS2 per Linux); un normale ext4/xfs può corrompere i dati con Multi-Attach
- Non supportato con volumi gp3/gp2/st1/sc1

**Use case:** applicazioni cluster ad alta disponibilità che gestiscono le scritture concorrenti a livello applicativo (es. Oracle RAC, SAP HANA cluster).

```bash
# Creare e attaccare un volume io2 a più istanze
aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 500 \
  --volume-type io2 \
  --iops 50000 \
  --multi-attach-enabled

aws ec2 attach-volume --volume-id vol-xxx --instance-id i-instance1 --device /dev/xvdf
aws ec2 attach-volume --volume-id vol-xxx --instance-id i-instance2 --device /dev/xvdf
```

### EBS Snapshots

Gli snapshot EBS sono backup incrementali del volume archiviati su S3 (gestione trasparente). Solo i blocchi modificati vengono salvati in ogni snapshot successivo.

**Caratteristiche:**
- **Incrementali**: il primo snapshot è completo, i successivi contengono solo le differenze
- **Copiabili cross-Region**: per DR o migrazione
- **Condivisibili**: tra account AWS (snapshot pubblici o privati specifici)
- **Creabili a caldo**: non è necessario detachare il volume (ma è consigliato quiescing per consistency)

```bash
# Creare uno snapshot manuale
aws ec2 create-snapshot \
  --volume-id vol-1234567890abcdef0 \
  --description "Backup pre-deployment $(date +%Y-%m-%d)" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=prod-db-backup},{Key=Env,Value=production}]'

# Listare snapshot
aws ec2 describe-snapshots \
  --owner-ids self \
  --filters "Name=tag:Env,Values=production"

# Copiare uno snapshot in un'altra Region (per DR)
aws ec2 copy-snapshot \
  --source-region us-east-1 \
  --source-snapshot-id snap-1234567890abcdef0 \
  --destination-region eu-west-1 \
  --description "DR copy" \
  --encrypted \
  --kms-key-id alias/aws/ebs

# Creare un volume da uno snapshot
aws ec2 create-volume \
  --snapshot-id snap-1234567890abcdef0 \
  --availability-zone us-east-1b \
  --volume-type gp3

# Condividere snapshot con altro account
aws ec2 modify-snapshot-attribute \
  --snapshot-id snap-1234567890abcdef0 \
  --attribute createVolumePermission \
  --operation-type add \
  --user-ids 999888777666
```

### Fast Snapshot Restore (FSR)

Normalmente, quando si crea un volume da uno snapshot, le performance iniziali sono ridotte (lazy initialization: i blocchi vengono caricati da S3 solo quando acceduti). FSR pre-carica tutti i blocchi, eliminando questo "cold start".

**Costo:** $0.75/snapshot/ora in ogni AZ in cui è abilitato.

```bash
# Abilitare Fast Snapshot Restore
aws ec2 enable-fast-snapshot-restores \
  --availability-zones us-east-1a us-east-1b \
  --source-snapshot-ids snap-1234567890abcdef0
```

### Amazon DLM — Data Lifecycle Manager

DLM automatizza la creazione, retention e copia di snapshot EBS tramite policy.

```bash
# Creare una policy DLM per backup giornaliero
aws dlm create-lifecycle-policy \
  --description "Daily EBS backup" \
  --state ENABLED \
  --execution-role-arn arn:aws:iam::123456789012:role/AWSDataLifecycleManagerDefaultRole \
  --policy-details '{
    "PolicyType": "EBS_SNAPSHOT_MANAGEMENT",
    "ResourceTypes": ["VOLUME"],
    "TargetTags": [{"Key": "Backup", "Value": "true"}],
    "Schedules": [{
      "Name": "DailyBackup",
      "CreateRule": {
        "Interval": 24,
        "IntervalUnit": "HOURS",
        "Times": ["03:00"]
      },
      "RetainRule": {
        "Count": 14
      },
      "CopyTags": true,
      "CrossRegionCopyRules": [{
        "TargetRegion": "eu-west-1",
        "Encrypted": true,
        "CopyTags": true,
        "RetainRule": {
          "Interval": 30,
          "IntervalUnit": "DAYS"
        }
      }]
    }]
  }'
```

### Cifratura EBS

- La cifratura è **opt-in** per volume (o per default a livello account/Region, vedi sotto): i volumi cifrati usano AES-256 tramite AWS KMS
- Su un volume cifrato sono cifrati dati a riposo, dati in transito tra istanza e volume, snapshot e volumi derivati (sulle istanze supportate)
- Snapshot di volumi cifrati sono automaticamente cifrati
- Volumi creati da snapshot cifrati sono automaticamente cifrati
- Si può abilitare la cifratura di default a livello account/Region

```bash
# Abilitare cifratura EBS di default per la Region
aws ec2 enable-ebs-encryption-by-default --region us-east-1

# Verificare impostazione di default
aws ec2 get-ebs-encryption-by-default --region us-east-1

# Creare volume cifrato esplicitamente
aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 100 \
  --encrypted \
  --kms-key-id arn:aws:kms:us-east-1:123456789012:key/mrk-1234

# Come cifrare un volume NON cifrato esistente:
# 1. Creare snapshot del volume
# 2. Copiare lo snapshot con cifratura abilitata
# 3. Creare nuovo volume cifrato dallo snapshot cifrato
# 4. Sostituire il volume nell'istanza
```

---

## Amazon EFS — Elastic File System

EFS è un file system NFS (Network File System) managed, scalabile e condiviso. A differenza di EBS, può essere montato contemporaneamente su **migliaia di istanze EC2 in più AZ** (e anche da on-premises tramite Direct Connect o VPN).

**Caratteristiche:**
- **Scalabilità automatica**: cresce e si riduce senza gestione manuale (da pochi KB a petabyte)
- **Multi-AZ**: i dati sono automaticamente ridondati su più AZ
- **NFS v4.0 e v4.1** compatibile
- Disponibile **solo per Linux** (no Windows — per Windows usare FSx for Windows)

```bash
# Creare un EFS file system
aws efs create-file-system \
  --creation-token my-efs-token \
  --performance-mode generalPurpose \
  --throughput-mode elastic \
  --encrypted \
  --kms-key-id alias/my-efs-key \
  --tags Key=Name,Value=my-efs

# Creare mount targets in ogni AZ
aws efs create-mount-target \
  --file-system-id fs-1234567890 \
  --subnet-id subnet-1234567890 \
  --security-groups sg-1234567890
```

### Performance Modes

**General Purpose (default):**
- Latenza più bassa (sub-ms per operazioni metadata)
- Fino a 250.000 operazioni di file al secondo (con Elastic i limiti IOPS sono quelli indicati sotto)
- Uso raccomandato per la maggior parte dei workload: web server, CMS, container

**Max I/O (legacy):**
- Throughput aggregato più alto, a scapito della latenza (più alta)
- Progettato per workload massivamente paralleli: HPC, big data analytics, media processing
- **Non supportato** con Elastic throughput né con i file system One Zone

!!! note "General Purpose vs Max I/O"
    AWS raccomanda General Purpose per tutti i workload: con Elastic throughput elimina quasi sempre la necessità di Max I/O. Il performance mode si sceglie solo alla creazione e non è modificabile dopo.

### Throughput Modes

| Modo | Comportamento | Use Case |
|------|-------------|---------|
| **Bursting** (legacy) | Baseline proporzionale allo storage (50 MiB/s per TiB) con burst a crediti; legato alla dimensione | File system grandi con accesso intermittente |
| **Provisioned** | Throughput fisso indipendentemente dallo storage, pagato a parte | Throughput prevedibile richiesto, storage piccolo |
| **Elastic** (raccomandato) | Scale automatico in base al workload; si paga il throughput effettivamente usato | Workload variabile/imprevedibile, cloud-native |

Limiti default Elastic per file system Regional: in 11 Region principali (us-east-1/2, us-west-2, ap-south-1, ap-northeast-2, ap-southeast-1/2, ap-northeast-1, eu-central-1, eu-west-1/2) fino a **60 GiB/s read** e **5 GiB/s write**; nelle altre Region 20 GiB/s read e 1 GiB/s write. IOPS max Elastic: 250.000 read (dati frequenti), 90.000 read (dati infrequenti), 50.000 write; i limiti sono aumentabili via AWS Support. Per client NFS: 1.500 MiB/s con Elastic e amazon-efs-utils ≥ 2.0 (500 MiB/s altrimenti).

!!! tip "Elastic vs Provisioned"
    Elastic costa per GB trasferito: conviene se l'utilizzo medio è sotto circa il 5% del picco. Con carico alto e costante Provisioned può costare meno.

```bash
# Cambiare throughput mode a Elastic
aws efs update-file-system \
  --file-system-id fs-1234567890 \
  --throughput-mode elastic
```

### Storage Tiers EFS

| Tier | Costo/GB/mese | Latenza | Descrizione |
|------|--------------|---------|-------------|
| **Standard** | $0.30 | sub-ms | Dati acceduti frequentemente |
| **Standard-IA** | $0.025 | slightly higher | Accesso infrequente (risparmio ~92% vs Standard) |
| **Archive** | $0.008 | slightly higher | Dati acceduti raramente (risparmio ~97% vs Standard) |

*Costo di retrieval per IA: $0.01/GB. Prezzi us-east-1. Esistono anche le classi One Zone (singola AZ, ~47% più economiche) per dati ricreabili. L'Archive richiede throughput Elastic o Provisioned.*

**EFS Lifecycle Management:** transizione automatica tra tieri in base all'ultimo accesso.

```bash
# Configurare lifecycle per EFS
aws efs put-lifecycle-configuration \
  --file-system-id fs-1234567890 \
  --lifecycle-policies '[
    {"TransitionToIA": "AFTER_30_DAYS"},
    {"TransitionToArchive": "AFTER_90_DAYS"},
    {"TransitionToPrimaryStorageClass": "AFTER_1_ACCESS"}
  ]'
```

### Mount via amazon-efs-utils

```bash
# Installare il mount helper
sudo yum install -y amazon-efs-utils  # Amazon Linux
# Ubuntu/Debian: il pacchetto non è nei repository ufficiali, va compilato (.deb) dal repo aws/efs-utils su GitHub
# In alternativa montare con il client NFS standard (senza TLS):
# sudo apt-get install -y nfs-common
# sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport fs-1234567890.efs.us-east-1.amazonaws.com:/ /mnt/efs

# Montare il file system (con TLS — raccomandato)
sudo mount -t efs -o tls fs-1234567890:/ /mnt/efs

# Mount specifico AZ (per latenza ottimale)
sudo mount -t efs -o tls,az=us-east-1a fs-1234567890:/ /mnt/efs

# Mount permanente in /etc/fstab
echo 'fs-1234567890:/ /mnt/efs efs defaults,_netdev,tls 0 0' | sudo tee -a /etc/fstab

# Mount con Access Point
sudo mount -t efs -o tls,accesspoint=fsap-1234567890 fs-1234567890:/ /mnt/efs-app
```

### EFS Access Points

Gli Access Points forniscono entry point applicativi al file system con: path radice configurabile, UID/GID forzati (i client vedono un user specifico), isolamento tra applicazioni.

```bash
# Creare un Access Point per una specifica applicazione
aws efs create-access-point \
  --file-system-id fs-1234567890 \
  --posix-user Uid=1000,Gid=1000 \
  --root-directory '{
    "Path": "/app1",
    "CreationInfo": {
      "OwnerUid": 1000,
      "OwnerGid": 1000,
      "Permissions": "755"
    }
  }' \
  --tags Key=App,Value=app1
```

### Replicazione EFS Cross-Region

```bash
# Abilitare replication verso un'altra Region
aws efs create-replication-configuration \
  --source-file-system-id fs-1234567890 \
  --destinations '[{
    "Region": "eu-west-1",
    "KmsKeyId": "arn:aws:kms:eu-west-1:123456789012:key/mrk-5678"
  }]'
```

---

## Amazon FSx

FSx è la famiglia di file system managed di AWS per workload specifici che richiedono protocolli o caratteristiche non disponibili in EFS.

### FSx for Windows File Server

File system SMB (Server Message Block)/CIFS (Common Internet File System) managed, integrato con Active Directory. Per applicazioni Windows che richiedono condivisioni di rete SMB.

**Caratteristiche:**
- Protocollo SMB 2.0, 2.1, 3.0, 3.1.1
- Integrazione AD: join automatico al domain (AWS Managed AD o self-managed AD)
- DFS (Distributed File System) Namespaces: spazio dei nomi distribuito per aggregare share multiple
- Shadow Copies (Volume Shadow Copy Service) per backup a livello utente
- Scalabilità: fino a 64 TB per file system, throughput fino a 2 GB/s
- Deployment: Single-AZ (economico) o Multi-AZ (HA con failover automatico)

```bash
# Creare FSx for Windows File Server
aws fsx create-file-system \
  --file-system-type WINDOWS \
  --storage-capacity 300 \
  --storage-type SSD \
  --subnet-ids subnet-1234567890 subnet-abcdef1234 \
  --security-group-ids sg-1234567890 \
  --windows-configuration '{
    "ActiveDirectoryId": "d-1234567890",
    "ThroughputCapacity": 512,
    "DeploymentType": "MULTI_AZ_1",
    "PreferredSubnetId": "subnet-1234567890",
    "AutomaticBackupRetentionDays": 30,
    "DailyAutomaticBackupStartTime": "03:00"
  }'
```

### FSx for Lustre

File system Lustre managed ad alte performance, progettato per HPC, ML training, simulazioni, elaborazione video.

**Caratteristiche:**
- Throughput: fino a centinaia di GB/s, milioni di IOPS
- File system POSIX
- **Integrazione nativa con S3**: i file S3 appaiono come file nel file system Lustre; le scritture possono essere sincronizzate indietro su S3
- Deployment types:
  - **Scratch** (temporaneo, no replication, altissima performance, economico): HPC jobs che non necessitano di persistenza
  - **Persistent** (dati replicati all'interno della stessa AZ, file server sostituiti automaticamente): workload ML con dati persistenti

!!! warning "Solo singola AZ"
    FSx for Lustre vive sempre in una sola AZ: in caso di perdita dell'AZ i dati persistent non sono disponibili. Per DR usare backup o export su S3.

```bash
# Creare FSx for Lustre collegato a S3
aws fsx create-file-system \
  --file-system-type LUSTRE \
  --storage-capacity 1200 \
  --subnet-ids subnet-1234567890 \
  --lustre-configuration '{
    "ImportPath": "s3://my-ml-data/datasets/",
    "ExportPath": "s3://my-ml-data/results/",
    "DeploymentType": "PERSISTENT_2",
    "PerUnitStorageThroughput": 250,
    "DataCompressionType": "LZ4"
  }'

# Per PERSISTENT_2 il link a S3 si crea con una Data Repository Association
# (ImportPath/ExportPath nel create-file-system valgono solo per SCRATCH_1/SCRATCH_2/PERSISTENT_1)
aws fsx create-data-repository-association \
  --file-system-id fs-1234567890 \
  --file-system-path /datasets \
  --data-repository-path s3://my-ml-data/datasets/ \
  --s3 '{"AutoImportPolicy":{"Events":["NEW","CHANGED","DELETED"]},"AutoExportPolicy":{"Events":["NEW","CHANGED","DELETED"]}}'

# Montare FSx for Lustre su un'istanza EC2 (Amazon Linux 2023)
sudo dnf install -y lustre-client
# <mount-name> si ottiene da: aws fsx describe-file-systems (LustreConfiguration.MountName)
sudo mount -t lustre -o relatime,flock \
  fs-1234567890.fsx.us-east-1.amazonaws.com@tcp:/<mount-name> \
  /mnt/fsx
```

### FSx for NetApp ONTAP

File system enterprise basato su NetApp ONTAP managed da AWS. Il più versatile: supporta NFS, SMB, iSCSI (Internet Small Computer System Interface) contemporaneamente, con feature enterprise come deduplica, compressione, thin provisioning.

**Caratteristiche:**
- Multi-protocol: NFS v3/v4, SMB 2.x/3.x, iSCSI e NVMe/TCP (NVMe/TCP solo su file system di seconda generazione, dal luglio 2024)
- Deduplica e compressione dei dati (riduzione storage significativa)
- Thin provisioning (allocazione virtuale)
- SnapMirror: replica ONTAP verso ONTAP (on-premises a FSx ONTAP)
- FlexClone: cloni istantanei di volumi (utili per test/dev)
- Scalabilità: tier SSD fino a 192 TiB (prima generazione), 512 TiB (seconda generazione Multi-AZ) o fino a 1 PiB (seconda generazione Single-AZ scale-out, 512 TiB per HA pair, fino a 12 HA pair, 200.000 IOPS per pair), più un capacity pool tier (storage a oggetti, economico) per i dati freddi
- Throughput max seconda generazione: 6.144 MBps Multi-AZ, 73.728 MBps Single-AZ con 12 HA pair
- Le SVM (Storage Virtual Machine) sono i contenitori logici di volumi, con endpoint e credenziali admin propri
- Use case: lift & shift di applicazioni enterprise NetApp, SAP, Oracle

```bash
# Creare FSx for NetApp ONTAP
aws fsx create-file-system \
  --file-system-type ONTAP \
  --storage-capacity 1024 \
  --subnet-ids subnet-1234567890 subnet-abcdef1234 \
  --ontap-configuration '{
    "DeploymentType": "MULTI_AZ_1",
    "ThroughputCapacity": 512,
    "AutomaticBackupRetentionDays": 30,
    "PreferredSubnetId": "subnet-1234567890",
    "RouteTableIds": ["rtb-1234567890"],
    "FsxAdminPassword": "<password-da-secrets-manager>"
  }'
```

!!! warning "Password admin"
    Non scrivere la password `fsxadmin` in chiaro nella shell history o negli script: recuperarla da Secrets Manager.

!!! note "Nota"
    FSx for ONTAP ha come riferimento il tool NetApp per la replica: **SnapMirror** replica ONTAP→ONTAP (non verso S3).

### FSx for OpenZFS

File system ZFS managed ad alte performance. Snapshot istantanei, cloni, compressione nativa.

**Caratteristiche:**
- Fino a 21 GB/s e milioni di IOPS (latenza di centinaia di µs) per dati in cache; fino a 10 GB/s e 400.000 IOPS da disco (Single-AZ 2 e Multi-AZ; Single-AZ 1 ha limiti inferiori)
- Solo NFS (v3, v4.0, v4.1, v4.2): nessun supporto SMB né iSCSI
- Deployment: Multi-AZ (HA), Single-AZ (HA) e Single-AZ (non-HA); storage class SSD (provisioned) o Intelligent-Tiering (elastico)
- Snapshot istantanei (zero-copy), cloni da snapshot
- Compressione Z-Standard
- Use case: database analitici, data science, applicazioni POSIX ad alta performance

### Confronto FSx

| | FSx Windows | FSx Lustre | FSx ONTAP | FSx OpenZFS |
|--|------------|-----------|----------|------------|
| Protocollo | SMB | Lustre/POSIX | NFS/SMB/iSCSI | NFS |
| OS | Windows | Linux | Linux/Windows | Linux |
| AD Integration | Sì | No | Sì (con AD) | No |
| S3 Integration | No | Nativa | Indiretta (es. DataSync) | No |
| Multi-AZ | Sì | No (solo singola AZ) | Sì | Sì |
| Deduplica | No | No | Sì | No |
| Use case | Windows workload | HPC/ML | Enterprise/lift&shift | POSIX ad alte perf |

---

## AWS Storage Gateway

Storage Gateway è un servizio ibrido che connette il datacenter on-premises ad AWS, fornendo accesso a storage cloud tramite protocolli standard (NFS, SMB, iSCSI, VTL). Viene installato come appliance virtuale (VMware, Hyper-V, KVM — Kernel-based Virtual Machine) o hardware fisico.

### File Gateway

Espone bucket S3 come condivisioni di file NFS o SMB. I file scritti vengono automaticamente sincronizzati su S3 con storage class configurabile. Cache locale per i dati acceduti di recente.

```
On-premises (NFS/SMB client) → File Gateway → S3 (backend)
```

**Use case:** backup di file server, migrazione a S3 con accesso NFS, archiviazione condivisione file on-premises su S3.

### Volume Gateway

Fornisce volumi iSCSI all'ambiente on-premises. Due modalità:

**Cached Mode:**
- Il volume "principale" è su S3
- Cache locale solo per i dati più recenti
- Può gestire volumi molto grandi senza hardware locale

**Stored Mode:**
- Tutti i dati primari sono on-premises
- Backup asincrono su S3 come EBS snapshots
- Per ambienti che devono mantenere tutti i dati on-premises

```
On-premises (iSCSI client) → Volume Gateway → S3/EBS Snapshots
```

!!! note "FSx File Gateway"
    Il tipo *Amazon FSx File Gateway* (cache locale verso FSx for Windows) non è più disponibile ai nuovi clienti dal 2024: per nuovi progetti usare File Gateway verso S3 o accesso diretto a FSx via Direct Connect/VPN.

### Tape Gateway

Emula una Virtual Tape Library (VTL) iSCSI. Le applicazioni di backup (Veeam, Backup Exec, NetBackup) scrivono su nastri virtuali che vengono archiviati su S3 o S3 Glacier.

```
Backup Software → Tape Gateway (VTL) → S3 / S3 Glacier
```

**Use case:** sostituire infrastruttura tape fisica, archiviazione a lungo termine dei backup su Glacier.

---

## AWS Snow Family

La Snow Family è una suite di dispositivi fisici per il trasferimento di dati offline e per l'edge computing in location senza connettività affidabile.

!!! warning "Disponibilità ridotta"
    Snowcone è stato dismesso il 12 novembre 2024 (non ordinabile né da nuovi né da clienti esistenti); Snowball Edge è disponibile solo ai clienti esistenti da novembre 2025; Snowmobile è stato dismesso nel 2024. Per nuove migrazioni usare AWS DataSync, AWS Transfer Family, Direct Connect o Data Transfer Terminal. Le sezioni seguenti restano come riferimento per clienti esistenti e per l'esame di certificazione.

**Quando usare Snow invece di trasferimento via Internet:**
- Quantità di dati > 10 TB (con connessione a 1 Gbps il trasferimento prende circa 1 giorno, e la banda è raramente dedicata al 100%)
- Connettività limitata o inaffidabile
- Necessità di elaborazione edge in ambienti remoti (navi, miniere, zone di conflitto)

### Snowcone

Il dispositivo più piccolo e leggero della famiglia.

| Variante | Storage | CPU | RAM | Use Case |
|---------|---------|-----|-----|---------|
| Snowcone HDD | 8 TB HDD | 2 vCPU | 4 GB | Edge computing base, piccole migrazioni |
| Snowcone SSD | 14 TB SSD | 2 vCPU | 4 GB | Edge computing con storage più veloce |

**Caratteristiche:** batteria integrata opzionale, può lavorare offline, AWS DataSync agent pre-installato per sincronizzazione automatica verso AWS.

### Snowball Edge

**Storage Optimized (80 TB):**
- 80 TB di HDD
- 40 vCPU, 80 GB RAM
- Trasferimento bulk di dati, migrazione data center
- Cluster mode: fino a 10 dispositivi per capacità aggregata

**Compute Optimized:**
- 28 TB NVMe SSD, 40 TB HDD
- 52 vCPU, 208 GB RAM
- Opzionale: NVIDIA V100 GPU
- ML inference in edge, image processing, real-time analytics

**Capacità cluster:** 10 dispositivi Snowball Edge in cluster → fino a 800 TB di storage aggregato, 400+ vCPU.

### Snowmobile

Un camion (container 45 piedi) con fino a **100 PB di storage**. Per migrazioni exabyte-scale.

**Use case:** migrazione di interi data center, grandi provider video/media.

**Processo:** AWS porta il Snowmobile on-site, si collega al datacenter tramite fibra, si trasferiscono i dati, il Snowmobile torna ad AWS dove i dati vengono caricati su S3 o Glacier.

### Confronto Snow Family

| Dispositivo | Capacità | Compute | Dimensione | Use Case Principale |
|------------|---------|---------|-----------|-------------------|
| Snowcone HDD | 8 TB | 2 vCPU/4 GB | 2,1 kg | Edge/IoT, piccole migrazioni |
| Snowcone SSD | 14 TB | 2 vCPU/4 GB | 2,1 kg | Edge/IoT, piccole migrazioni |
| Snowball Edge Storage | 80 TB | 40 vCPU/80 GB | ~22 kg | Migrazione bulk |
| Snowball Edge Compute | 28 TB NVMe | 52 vCPU/208 GB | ~22 kg | Edge computing/ML |
| Snowmobile | 100 PB | N/A | 45-ft container | Data center migration |

### Processo di Migrazione con Snow

```
1. Console AWS → ordinare il dispositivo
2. AWS spedisce il dispositivo
3. Collegare al network on-premises
4. Copiare dati (NFS, S3 compatible endpoint, SMB)
   - Endpoint S3-compatible del dispositivo con AWS CLI
   - AWS OpsHub: GUI per gestione dispositivo
5. Rispedire il dispositivo ad AWS (l'etichetta di spedizione E Ink si aggiorna da sola)
6. AWS carica i dati su S3
7. AWS cancella i dati dal dispositivo secondo lo standard NIST 800-88
```

```bash
# Copiare su Snowball Edge via endpoint S3-compatible (credenziali ottenute con snowballEdge unlock-device / list-access-keys)
aws s3 cp /local/data/ s3://my-bucket/data/ --recursive \
  --endpoint-url https://192.0.2.10:8443 \
  --ca-bundle snowball-ca.pem \
  --profile snowballEdge

# Copiare su Snowcone via DataSync
aws datasync create-task \
  --source-location-arn arn:aws:datasync:us-east-1:123456789012:location/loc-snowcone \
  --destination-location-arn arn:aws:datasync:us-east-1:123456789012:location/loc-s3
```

---

## Best Practices

### EBS
- Usare gp3 come default invece di gp2 (più economico, più flessibile)
- Abilitare cifratura di default EBS a livello Region
- Configurare DLM per backup automatici con retention policy
- Monitorare `VolumeQueueLength` e `BurstBalance` in CloudWatch
- Per database production: io2 Block Express con IOPS provisionati

### EFS
- Usare Elastic throughput mode per workload variabili
- Configurare lifecycle management (transizione a IA/Archive)
- Usare Access Points per isolamento tra applicazioni
- Montare con TLS (`-o tls`) per cifratura in transito
- Separare file system per workload diversi (non condividere un unico EFS grande)

### FSx
- FSx for Lustre Scratch per job HPC temporanei (più economico)
- FSx for Lustre Persistent per ML training con dati preziosi
- FSx for ONTAP Multi-AZ per workload enterprise critici
- Abilitare backup automatici su tutti i file system FSx

---

## Troubleshooting

### EBS: Volume Non Si Monta dopo Reboot

Verificare `/etc/fstab` — usare `nofail` option:
```bash
# Corretto (con nofail, il sistema parte anche se il volume non c'è)
/dev/xvdf /data xfs defaults,nofail 0 2
```

### EFS: Errore di Mount "Connection Timed Out"

1. Verificare Security Group del mount target (porta 2049 NFS deve essere aperta dall'istanza EC2)
2. Verificare che l'istanza abbia routing verso il mount target (stessa VPC, oppure peering/Transit Gateway/VPN/Direct Connect) e che il DNS risolva il mount target
3. Verificare che il mount helper `amazon-efs-utils` sia installato

```bash
# Debug connessione NFS
nc -zv fs-1234567890.efs.us-east-1.amazonaws.com 2049
```

### EBS: "Disk I/O Error" o Performance Degrada

```bash
# Verificare metriche EBS in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/EBS \
  --metric-name VolumeQueueLength \
  --dimensions Name=VolumeId,Value=vol-1234567890abcdef0 \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T01:00:00Z \
  --period 300 \
  --statistics Average

# Per gp2: verificare BurstBalance (se < 20%, si sta consumando il burst)
aws cloudwatch get-metric-statistics \
  --namespace AWS/EBS \
  --metric-name BurstBalance \
  --dimensions Name=VolumeId,Value=vol-xxx \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T01:00:00Z \
  --period 300 \
  --statistics Average
```

---

## Relazioni

??? info "S3 — Object Storage"
    EBS Snapshots sono archiviati su S3 (gestione trasparente). FSx for Lustre può importare/esportare dati da S3.

    **Approfondimento completo →** [S3 Fondamentali](s3.md)

??? info "EC2 — Compute"
    EBS è il sistema di storage primario per EC2. La scelta del tipo di volume dipende dal workload dell'istanza.

??? info "KMS — Encryption"
    Cifratura EBS e EFS usa AWS KMS. Comprendere KMS è fondamentale per gestire la cifratura dello storage.

    **Approfondimento completo →** [KMS e Secrets Manager](../security/kms-secrets.md)

---

## Riferimenti

- [EBS User Guide](https://docs.aws.amazon.com/ebs/latest/userguide/)
- [EBS Volume Types](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)
- [EFS User Guide](https://docs.aws.amazon.com/efs/latest/ug/)
- [FSx for Lustre](https://docs.aws.amazon.com/fsx/latest/LustreGuide/)
- [FSx for Windows](https://docs.aws.amazon.com/fsx/latest/WindowsGuide/)
- [FSx for NetApp ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/)
- [Storage Gateway](https://docs.aws.amazon.com/storagegateway/latest/userguide/)
- [Snow Family](https://docs.aws.amazon.com/snowball/latest/developer-guide/)
- [EBS Pricing](https://aws.amazon.com/ebs/pricing/)
- [EFS Pricing](https://aws.amazon.com/efs/pricing/)
