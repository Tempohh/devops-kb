---
title: "EBS, EFS, FSx, Storage Gateway e Snow Family"
slug: ebs-efs-fsx
category: cloud
tags: [aws, ebs, efs, fsx, storage-gateway, snow-family, block-storage, file-storage, ebs-snapshots, dlm, snowball, snowcone, snowmobile]
search_keywords: [ebs, elastic block store, efs, elastic file system, fsx, fsx lustre, fsx windows, fsx ontap, fsx openzfs, storage gateway, file gateway, volume gateway, tape gateway, snow family, snowball edge, snowcone, snowmobile, gp3, gp2, io2, io1, st1, sc1, multi attach, fast snapshot restore, nfs, smb, iscsi, hpc, active directory, worm, dlm, data lifecycle manager]
parent: cloud/aws/storage/_index
related: [cloud/aws/storage/s3, cloud/aws/compute/ec2, cloud/aws/database/rds-aurora, cloud/aws/security/kms-secrets]
official_docs: https://docs.aws.amazon.com/ebs/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
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
- **Dimensione:** da 1 GB fino a 64 TB (dipende dal tipo)

!!! warning "EBS è AZ-locked"
    Se si vuole spostare un volume EBS in un'altra AZ o Region, bisogna creare uno snapshot e poi creare un nuovo volume dallo snapshot nella AZ/Region di destinazione.

### Tipi di Volume EBS

| Tipo | Categoria | IOPS Max | Throughput Max | Capacità | Prezzo Base | Use Case |
|------|-----------|---------|---------------|---------|-------------|---------|
| **gp3** | SSD General Purpose | 16.000 | 1.000 MB/s | 1 GB–16 TB | $0.08/GB/mese | Default per quasi tutto |
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
- IOPS configurabili fino a 16.000 IOPS aggiuntivi a pagamento ($0.005/IOPS provisioned sopra i 3.000)
- Throughput configurabile fino a 1.000 MB/s
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
lsblk
sudo mkfs -t xfs /dev/xvdf
sudo mkdir /data
sudo mount /dev/xvdf /data
# Per mount persistente al reboot
echo '/dev/xvdf /data xfs defaults,nofail 0 2' | sudo tee -a /etc/fstab
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

- Tutti i dati a riposo sono cifrati con AES-256 tramite AWS KMS
- Tutti i dati in transito tra l'istanza e il volume sono cifrati
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
- Max 35.000 IOPS
- Uso raccomanato per la maggior parte dei workload: web server, CMS, container

**Max I/O:**
- Throughput aggregato più alto
- Latenza più alta (~10ms)
- Progettato per workload massivamente paralleli: HPC, big data analytics, media processing

!!! note "General Purpose vs Max I/O"
    Il 99% dei workload funziona bene con General Purpose. Max I/O è necessario solo per applicazioni con migliaia di thread che accedono al file system contemporaneamente (es. cluster HPC con 1.000+ nodi).

### Throughput Modes

| Modo | Comportamento | Use Case |
|------|-------------|---------|
| **Bursting** (legacy) | Throughput proporzionale allo storage (1 MB/s per TB) con burst; legato alla dimensione | File system piccoli con accesso intermittente |
| **Provisioned** | Throughput fisso indipendentemente dallo storage | Throughput prevedibile richiesto, storage piccolo |
| **Elastic** (raccomandato) | Scale automatico in base al workload, fino a 3 GB/s write / 10 GB/s read | Workload variabile, cloud-native |

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

*Costo di retrieval per IA: $0.01/GB. Prezzi us-east-1.*

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
sudo apt-get install -y amazon-efs-utils  # Ubuntu/Debian

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

File system SMB/CIFS managed, integrato con Active Directory. Per applicazioni Windows che richiedono condivisioni di rete SMB.

**Caratteristiche:**
- Protocollo SMB 2.0, 2.1, 3.0, 3.1.1
- Integrazione AD: join automatico al domain (AWS Managed AD o self-managed AD)
- DFS Namespaces: spazio dei nomi distribuito per aggregare share multiple
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
  - **Persistent** (replicato su 2 server, tolleranza ai guasti): workload ML con dati persistenti

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
    "DataCompressionType": "LZ4",
    "AutoImportPolicy": "NEW_CHANGED_DELETED"
  }'

# Montare FSx for Lustre su un'istanza EC2
sudo amazon-linux-extras install -y lustre
sudo mount -t lustre -o relatime,flock \
  fs-1234567890.fsx.us-east-1.amazonaws.com@tcp:/fsx \
  /mnt/fsx
```

### FSx for NetApp ONTAP

File system enterprise basato su NetApp ONTAP managed da AWS. Il più versatile: supporta NFS, SMB, iSCSI contemporaneamente, con feature enterprise come deduplica, compressione, thin provisioning.

**Caratteristiche:**
- Multi-protocol: NFS v3/v4, SMB 2.x/3.x, iSCSI
- Deduplica e compressione dei dati (riduzione storage significativa)
- Thin provisioning (allocazione virtuale)
- SnapMirror: replica ONTAP verso ONTAP (on-premises a FSx ONTAP)
- FlexClone: cloni istantanei di volumi (utili per test/dev)
- Scalabilità: storage capacity fino a 192 TB per storage virtual machine (SVM)
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
    "FsxAdminPassword": "SecurePassword123!"
  }'
```

### FSx for OpenZFS

File system ZFS managed ad alte performance. Snapshot istantanei, cloni, compressione nativa.

**Caratteristiche:**
- Throughput fino a 12,5 GB/s, IOPS fino a 1 milione
- NFS v3 e v4.x
- Snapshot istantanei (zero-copy), cloni da snapshot
- Compressione Z-Standard
- Deployment: Single-AZ (ottimizzato per performance) o Multi-AZ
- Use case: database analitici, data science, applicazioni POSIX ad alta performance

### Confronto FSx

| | FSx Windows | FSx Lustre | FSx ONTAP | FSx OpenZFS |
|--|------------|-----------|----------|------------|
| Protocollo | SMB | Lustre/POSIX | NFS/SMB/iSCSI | NFS |
| OS | Windows | Linux | Linux/Windows | Linux |
| AD Integration | Sì | No | Sì (con AD) | No |
| S3 Integration | No | Nativa | Via SnapMirror | No |
| Multi-AZ | Sì | Persistent only | Sì | Sì |
| Deduplica | No | No | Sì | No |
| Use case | Windows workload | HPC/ML | Enterprise/lift&shift | POSIX ad alte perf |

---

## AWS Storage Gateway

Storage Gateway è un servizio ibrido che connette il datacenter on-premises ad AWS, fornendo accesso a storage cloud tramite protocolli standard (NFS, SMB, iSCSI, VTL). Viene installato come appliance virtuale (VMware, Hyper-V, KVM) o hardware fisico.

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

### Tape Gateway

Emula una Virtual Tape Library (VTL) iSCSI. Le applicazioni di backup (Veeam, Backup Exec, NetBackup) scrivono su nastri virtuali che vengono archiviati su S3 o S3 Glacier.

```
Backup Software → Tape Gateway (VTL) → S3 / S3 Glacier
```

**Use case:** sostituire infrastruttura tape fisica, archiviazione a lungo termine dei backup su Glacier.

---

## AWS Snow Family

La Snow Family è una suite di dispositivi fisici per il trasferimento di dati offline e per l'edge computing in location senza connettività affidabile.

**Quando usare Snow invece di trasferimento via Internet:**
- Quantità di dati > 10 TB (con connessione a 1 Gbps il trasferimento prenderebbe > 1 giorno)
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
   - Snowball Client: aws snowball cp per trasferimenti
   - AWS OpsHub: GUI per gestione dispositivo
5. Rispedire il dispositivo ad AWS
6. AWS carica i dati su S3
7. AWS cancella il dispositivo (certificazione E-Ink)
```

```bash
# Usare la CLI per copiare su Snowball (tramite manifest e unlock code ricevuti via email)
snowball cp /local/data/ s3://my-bucket/data/ \
  --profile snowball

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
2. Verificare che l'istanza sia nella stessa VPC del file system
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
