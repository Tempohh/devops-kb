---
title: "Infrastruttura Globale Azure"
slug: global-infrastructure-azure
category: cloud
tags: [azure, regions, availability-zones, edge-locations, sovereign-cloud, region-pairs]
search_keywords: [Azure regions, Azure region pairs, Availability Zones AZ, Edge Locations, Azure sovereign cloud, Azure Government, Azure China, Azure datacenter, Azure global network, Azure geography, availability set]
parent: cloud/azure/fondamentali/_index
related: [cloud/azure/fondamentali/shared-responsibility, cloud/azure/networking/vnet]
official_docs: https://azure.microsoft.com/global-infrastructure/
status: complete
difficulty: beginner
last_updated: 2026-02-26
---

# Infrastruttura Globale Azure

## Gerarchia dell'Infrastruttura

```
Geography (es. Europe)
└── Region Pair (es. North Europe ↔ West Europe)
    └── Region (es. Italy North)
        └── Availability Zones (3 zone fisicamente separate)
            └── Datacenter
                └── Server / Storage / Network
```

---

## Region

Una **Region** è un'area geografica contenente uno o più datacenter collegati da una rete a bassa latenza.

**Region italiane:**
- `Italy North` — Milano (GA 2023)

**Region europee principali:**
- `West Europe` — Olanda
- `North Europe` — Irlanda
- `Germany West Central` — Francoforte
- `France Central` — Parigi
- `Switzerland North` — Zurigo
- `UK South` — Londra

```bash
# Listare tutte le region disponibili per la subscription
az account list-locations \
    --query "[?metadata.regionType=='Physical'].{Name:name, DisplayName:displayName, PairedRegion:metadata.pairedRegion[0].name}" \
    --output table

# Verificare disponibilità servizi per region
az provider show \
    --namespace Microsoft.Compute \
    --query "resourceTypes[?resourceType=='virtualMachines'].locations" \
    --output table
```

---

## Availability Zones (AZ)

Le **Availability Zones** sono datacenter fisicamente separati all'interno della stessa region, con alimentazione, raffreddamento e networking indipendenti.

```
Region: Italy North
┌─────────────────────────────────────────┐
│  Zone 1        Zone 2        Zone 3     │
│  ┌──────┐     ┌──────┐     ┌──────┐   │
│  │  DC  │     │  DC  │     │  DC  │   │
│  └──────┘     └──────┘     └──────┘   │
│     ↕ bassa latenza (<2ms) ↕           │
└─────────────────────────────────────────┘
```

**Tipi di servizi rispetto alle zone:**

| Tipo | Descrizione | Esempi |
|------|-------------|--------|
| **Zonal** | Risorsa deployata in una zona specifica | VM, Managed Disks, IP pubblici |
| **Zone-Redundant** | Replicato automaticamente su 3 zone | Azure SQL ZRS, Storage ZRS, Application Gateway |
| **Non-regional** | Servizi globali, non legati a zone | Azure AD, DNS, Traffic Manager |

```bash
# Deploy VM in Availability Zone specifica
az vm create \
    --resource-group myapp-rg \
    --name myvm \
    --image Ubuntu2204 \
    --zone 1 \                    # Zone 1, 2 o 3
    --size Standard_D2s_v3

# Creare Public IP zone-redundant
az network public-ip create \
    --resource-group myapp-rg \
    --name myapp-pip \
    --sku Standard \
    --zone 1 2 3                  # zone-redundant
```

---

## Availability Set

Gli **Availability Set** garantiscono HA distribuendo VM su fault domain e update domain diversi (per VM non zone-aware, es. hardware legacy):

```bash
# Creare Availability Set
az vm availability-set create \
    --resource-group myapp-rg \
    --name myapp-as \
    --platform-fault-domain-count 2 \     # max 3 — diversi rack fisici
    --platform-update-domain-count 5      # max 20 — aggiornamenti sequenziali

# Deploy VM in Availability Set
az vm create \
    --resource-group myapp-rg \
    --name myvm1 \
    --availability-set myapp-as \
    --image Ubuntu2204
```

!!! note "AZ vs Availability Set"
    Preferire **Availability Zones** per nuovi deployment — protezione da guasti datacenter interi.
    Gli Availability Set proteggono da guasti hardware/rack all'interno dello stesso datacenter.

---

## Region Pairs

Ogni Region Azure è accoppiata con un'altra Region nella stessa area geografica per **Disaster Recovery** e aggiornamenti pianificati scaglionati.

| Region | Region Pair |
|--------|-------------|
| Italy North | Germany West Central |
| West Europe | North Europe |
| UK South | UK West |
| France Central | France South |
| Germany West Central | North Europe |
| Switzerland North | Switzerland West |
| Norway East | Norway West |

**Implicazioni pratiche:**
- Geo-redundant storage (GRS) replica nel pair automaticamente
- Azure Site Recovery replica nel pair di default
- Gli aggiornamenti del platform vengono rollati prima su una region, poi sull'altra
- In caso di outage regionale, Microsoft dà priorità al ripristino di una delle due region

---

## Sovereign Clouds

| Cloud | Destinatari | Isolamento |
|-------|-------------|------------|
| **Azure Government** | Agenzie US Federal, State, Local | Fisicamente separato, operato da US citizens screened |
| **Azure China (21Vianet)** | Organizzazioni in Cina | Operato da 21Vianet, separato da Azure globale |
| **Azure Germany** (legacy) | Dati sensibili tedeschi | Sostituito da Azure Germany (regioni standard + policy GDPR) |

---

## Rete Backbone Globale

Microsoft possiede e opera una rete privata **WAN globale** che collega tutte le region Azure:
- Oltre **175.000 km** di fibra sottomarina e terrestre
- Traffico tra region Azure viaggia sulla rete privata Microsoft (non Internet pubblica)
- **Latenza garantita** inter-region europea: tipicamente <10ms

```bash
# Verificare latenza inter-region (da VM Azure)
# Usare Azure Network Watcher Connection Monitor
az network watcher connection-monitor create \
    --name latency-test \
    --resource-group myapp-rg \
    --location italynorth \
    --source-resource myvm \
    --dest-resource myvm-westeurope
```

---

## Riferimenti

- [Azure Global Infrastructure](https://azure.microsoft.com/global-infrastructure/)
- [Azure Geographies](https://azure.microsoft.com/global-infrastructure/geographies/)
- [Availability Zones](https://learn.microsoft.com/azure/reliability/availability-zones-overview)
- [Azure Region Pairs](https://learn.microsoft.com/azure/reliability/cross-region-replication-azure)
