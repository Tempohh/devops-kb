---
title: "AWS Storage"
slug: storage
category: cloud
tags: [aws, storage, s3, ebs, efs, fsx, glacier, snow-family]
search_keywords: [aws storage, s3, ebs, efs, fsx, storage gateway, snow family, object storage, block storage, file storage, glacier, archivio]
parent: cloud/aws/_index
related: [cloud/aws/storage/s3, cloud/aws/storage/s3-avanzato, cloud/aws/storage/ebs-efs-fsx, cloud/aws/database/rds-aurora]
official_docs: https://aws.amazon.com/products/storage/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS Storage

AWS offre un portfolio completo di servizi di storage ottimizzati per diversi pattern di accesso, performance e costi. La scelta del servizio corretto è fondamentale per ottimizzare sia le performance che i costi delle architetture cloud.

## Categorie di Storage

I servizi AWS di storage si dividono in tre macro-categorie fondamentali:

- **Object Storage (S3):** Dati non strutturati, file statici, backup, data lake. Accesso via API HTTP.
- **Block Storage (EBS):** Volumi a bassa latenza per istanze EC2. Come un disco rigido attaccato al server.
- **File Storage (EFS, FSx):** File system condivisi, accessibili da più istanze simultaneamente via NFS/SMB.

---

## Servizi Disponibili

<div class="grid cards" markdown>

-   **Amazon S3**

    ---

    Object storage scalabile e durevole (11 9s di durabilità). Base per data lake, backup, siti statici, distribuzioni software.

    [:octicons-arrow-right-24: S3 Fondamentali](s3.md)

-   **Amazon S3 Avanzato**

    ---

    Sicurezza, encryption, Object Lambda, S3 Select, Event Notifications, Access Points, performance tuning.

    [:octicons-arrow-right-24: S3 Avanzato](s3-avanzato.md)

-   **Amazon EBS / EFS / FSx**

    ---

    Block storage (EBS), file system NFS managed (EFS), file system enterprise (FSx). Snow Family e Storage Gateway.

    [:octicons-arrow-right-24: EBS, EFS, FSx](ebs-efs-fsx.md)

</div>

---

## Quick Reference — Tabella Comparativa

| Servizio | Tipo | Protocollo | Use Case Principale | Durabilità | Latenza |
|----------|------|-----------|---------------------|-----------|---------|
| **S3 Standard** | Object | HTTP/S API | Data lake, backup, static assets | 11 9s | ms-s |
| **S3 Glacier** | Object | HTTP/S API | Archivio a lungo termine | 11 9s | min-ore |
| **EBS gp3** | Block | Attached volume | Boot disk, DB, applicazioni | 99.8-99.9% | sub-ms |
| **EBS io2** | Block | Attached volume | Database I/O intensivo | 99.999% | sub-ms |
| **EFS** | File (NFS) | NFS v4.1 | File condivisi, CMS, EKS | 99.99% (Multi-AZ) | low ms |
| **FSx for Windows** | File (SMB) | SMB 3.x | Active Directory, Windows apps | 99.99% | sub-ms |
| **FSx for Lustre** | File (POSIX) | Lustre | HPC, ML training | 99.99% | sub-ms |
| **FSx for ONTAP** | File (multi) | NFS/SMB/iSCSI | Enterprise storage, lift & shift | 99.99% | sub-ms |
| **Storage Gateway** | Ibrido | NFS/SMB/iSCSI | On-premises → Cloud bridge | N/A | dipende da WAN |
| **Snowball Edge** | Fisico | NFS/S3 API | Migrazione offline, edge computing | N/A | N/A |

---

## Scegliere il Servizio Giusto

### Decision Tree

```
Hai bisogno di:
│
├── Accedere ai dati tramite API HTTP (non filesystem)?
│   └── → Amazon S3
│
├── Un disco per la tua istanza EC2?
│   └── → Amazon EBS
│       ├── Workload generale → gp3
│       ├── Database ad alte IOPS → io2 Block Express
│       └── Dati sequenziali (log, Hadoop) → st1
│
├── Un file system condiviso tra più istanze?
│   ├── Linux / NFS → Amazon EFS
│   ├── Windows / SMB → FSx for Windows File Server
│   ├── HPC / ML → FSx for Lustre
│   └── Enterprise multi-protocol → FSx for NetApp ONTAP
│
├── Connettere il datacenter on-premises a S3?
│   └── AWS Storage Gateway
│       ├── NFS/SMB → File Gateway
│       ├── iSCSI → Volume Gateway
│       └── Tape backup → Tape Gateway
│
└── Migrare terabyte/petabyte offline?
    └── AWS Snow Family
        ├── < 14 TB → Snowcone
        ├── < 80 TB → Snowball Edge Storage Optimized
        └── > 100 PB → Snowmobile
```

---

## Storage Classes S3 — Riepilogo Costi

| Storage Class | Costo/GB/mese | Min. durata | Retrieval | Latenza | Use Case |
|--------------|--------------|-------------|-----------|---------|---------|
| Standard | $0.023 | Nessuna | Gratuita | ms | Dati acceduti frequentemente |
| Intelligent-Tiering | $0.023 + $0.0025/1K obj | Nessuna | Gratuita | ms | Pattern di accesso variabile |
| Standard-IA | $0.0125 | 30 giorni | $0.01/GB | ms | Accesso infrequente, rapido |
| One Zone-IA | $0.01 | 30 giorni | $0.01/GB | ms | IA, singola AZ |
| Glacier Instant Retrieval | $0.004 | 90 giorni | $0.03/GB | ms | Archivio con accesso rapido |
| Glacier Flexible Retrieval | $0.0036 | 90 giorni | $0.01/GB (Bulk) | min-ore | Archivio standard |
| Glacier Deep Archive | $0.00099 | 180 giorni | $0.02/GB (Bulk) | 12-48h | Archiviazione a lungo termine |

*Prezzi indicativi us-east-1. Verificare pricing attuale su aws.amazon.com/pricing*

---

## Confronto EBS — Tipi di Volume

| Tipo | IOPS Max | Throughput Max | Costo | Use Case |
|------|---------|---------------|-------|---------|
| **gp3** | 16.000 | 1.000 MB/s | $0.08/GB/mese | Default per qualsiasi workload |
| **gp2** | 16.000 | 250 MB/s | $0.10/GB/mese | Legacy (preferire gp3) |
| **io2 Block Express** | 256.000 | 4.000 MB/s | $0.125/GB + $0.065/IOPS | Database mission-critical |
| **io1** | 64.000 | 1.000 MB/s | $0.125/GB + $0.065/IOPS | Database ad alte IOPS |
| **st1** | 500 | 500 MB/s | $0.045/GB/mese | Hadoop, log, sequential reads |
| **sc1** | 250 | 250 MB/s | $0.015/GB/mese | Cold data, lowest cost |

---

## Architetture Comuni

### Data Lake su S3

```
Ingestion Layer:
  Kinesis Firehose / AWS Glue → S3 Raw (Standard)

Processing Layer:
  EMR / Athena → S3 Processed (Standard-IA)

Archive Layer:
  S3 Lifecycle Rules → Glacier Deep Archive (dopo 1 anno)
```

### Backup e DR

```
EC2 Instance (EBS) → AWS Backup → EBS Snapshot → S3 (opaque)
RDS → Automated Backup → S3 (opaque)
On-premises → Storage Gateway (File/Volume) → S3/EBS
Bulk migration → Snow Family → S3
```

### File System Condiviso per ECS/EKS

```
ECS Tasks / EKS Pods → EFS (NFS mount)
  EFS Access Points → directory isolation per servizio
  EFS Lifecycle → Standard-IA dopo 30 giorni di inattività
```

---

## Riferimenti

- [Panoramica Storage AWS](https://aws.amazon.com/products/storage/)
- [S3 Documentazione](https://docs.aws.amazon.com/s3/)
- [EBS Documentazione](https://docs.aws.amazon.com/ebs/)
- [EFS Documentazione](https://docs.aws.amazon.com/efs/)
- [FSx Documentazione](https://docs.aws.amazon.com/fsx/)
- [Storage Gateway](https://docs.aws.amazon.com/storagegateway/)
- [Snow Family](https://aws.amazon.com/snow/)
- [AWS Storage Blog](https://aws.amazon.com/blogs/storage/)
