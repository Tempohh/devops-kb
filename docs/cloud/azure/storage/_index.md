---
title: "Azure Storage"
slug: storage-azure
category: cloud
tags: [azure, storage, blob, files, queue, table, managed-disks, data-lake]
search_keywords: [Azure Storage Account, Blob Storage object storage, Azure Files SMB NFS, Queue Storage, Table Storage NoSQL, Managed Disks SSD, Data Lake Gen2 ADLS, AzCopy, lifecycle management, SAS token]
parent: cloud/azure/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/database/cosmos-db, cloud/azure/security/key-vault]
official_docs: https://learn.microsoft.com/azure/storage/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Storage

Azure Storage è la piattaforma di archiviazione cloud managed di Azure, progettata per alta disponibilità, durabilità e scalabilità. Offre diversi tipi di storage per coprire ogni scenario: dati strutturati e non strutturati, file condivisi, code di messaggi e dischi virtuali.

## Panoramica dei Servizi Storage

| Servizio | Tipo | Protocollo | Use Case | Pricing |
|---|---|---|---|---|
| **Blob Storage** | Object store | HTTP/HTTPS, AzCopy | File, immagini, backup, log, data lake | Per GB archiviato + operazioni |
| **Azure Files** | File share | SMB 3.0, NFS 4.1 | Condivisione file tra VM, lift & shift NAS | Per GB provisionato |
| **Queue Storage** | Message queue | HTTP/HTTPS | Decoupling componenti, task async | Per operazioni |
| **Table Storage** | NoSQL key-value | HTTP/HTTPS | Dati strutturati semplici, IoT | Per GB + operazioni |
| **Managed Disks** | Block storage | Interno (iSCSI) | OS disk e data disk per VM | Per GB provisionato |
| **Data Lake Gen2** | Object + filesystem | HTTP, HDFS | Analytics, big data, ML datasets | Per GB + operazioni |

## Gerarchia Storage Account

```
Storage Account (contenitore logico con endpoint unico)
├── Blob Storage
│   ├── Container 1
│   │   ├── Blob A (Block Blob — file generici)
│   │   ├── Blob B (Append Blob — log)
│   │   └── Blob C (Page Blob — VHD)
│   └── Container 2
├── Azure Files
│   ├── Share A
│   └── Share B
├── Queue Storage
│   └── Queue A
└── Table Storage
    └── Table A
```

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   **Blob Storage & Data Lake**

    ---

    Storage account, tipi di ridondanza, tier accesso (Hot/Cool/Cold/Archive), lifecycle management, SAS token, AzCopy, Data Lake Gen2, Immutable Storage (WORM).

    [:octicons-arrow-right-24: Vai a Blob Storage](blob-storage.md)

-   **Storage Avanzato**

    ---

    Azure Files (SMB/NFS), Azure File Sync, Managed Disks (Premium SSD v2, Ultra), Queue Storage, Table Storage, network rules, Customer-managed Keys.

    [:octicons-arrow-right-24: Vai a Storage Avanzato](storage-avanzato.md)

</div>

## Riferimenti

- [Documentazione Azure Storage](https://learn.microsoft.com/azure/storage/)
- [Prezzi Azure Storage](https://azure.microsoft.com/pricing/details/storage/)
- [Scegliere il servizio storage giusto](https://learn.microsoft.com/azure/storage/common/storage-introduction)
