---
title: "Infrastruttura Globale Azure"
slug: global-infrastructure-azure
category: cloud
tags: [azure, regions, availability-zones, edge-locations, sovereign-cloud, region-pairs]
search_keywords: [Azure regions, Azure region pairs, Availability Zones AZ, Edge Locations, Azure sovereign cloud, Azure Government, Azure China, Azure datacenter, Azure global network, Azure geography, availability set]
parent: cloud/azure/fondamentali/_index
related: [cloud/azure/fondamentali/shared-responsibility, cloud/azure/networking/vnet]
official_docs: https://azure.microsoft.com/global-infrastructure/
status: reviewed
difficulty: beginner
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Infrastruttura Globale Azure

## Gerarchia dell'Infrastruttura

```
Geography (es. Europe, Italy: perimetro di data residency/compliance)
└── Region (es. Italy North, West Europe)   ← alcune region hanno un Region Pair
    └── Availability Zones (min. 3 zone fisicamente separate, nelle region con AZ)
        └── Datacenter
            └── Server / Storage / Network
```

!!! note "Perché esistono le Geography"
    Una **Geography** garantisce che dati e applicazioni restino entro un confine geopolitico/regolatorio (es. UE, Italia). Region e Region Pair di una geography sono scelte per rispettare data residency e compliance.

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
- `Spain Central` — Madrid, `Poland Central` — Varsavia (region recenti, senza Region Pair)

Le region più recenti possono avere disponibilità limitata di servizi/SKU rispetto a quelle mature: verificare sempre prima di scegliere la region.

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
| **Non-regional** (always-available) | Servizi globali, non legati a una region/zona | Microsoft Entra ID, Azure DNS, Traffic Manager, Front Door |

```bash
# Deploy VM in Availability Zone specifica
az vm create \
    --resource-group myapp-rg \
    --name myvm \
    --image Ubuntu2204 \
    --zone 1 \
    --size Standard_D2s_v5
# --zone accetta 1, 2 o 3

# Creare Public IP zone-redundant
az network public-ip create \
    --resource-group myapp-rg \
    --name myapp-pip \
    --sku Standard \
    --zone 1 2 3
# più zone insieme = IP zone-redundant
```

---

## Availability Set

Gli **Availability Set** garantiscono HA distribuendo VM su fault domain e update domain diversi (per VM non zone-aware, es. hardware legacy):

```bash
# Creare Availability Set
az vm availability-set create \
    --resource-group myapp-rg \
    --name myapp-as \
    --platform-fault-domain-count 2 \
    --platform-update-domain-count 5
# fault domain: max 3 (rack fisici diversi); update domain: max 20 (riavvii di piattaforma sequenziali)

# Deploy VM in Availability Set
az vm create \
    --resource-group myapp-rg \
    --name myvm1 \
    --availability-set myapp-as \
    --image Ubuntu2204
```

!!! warning "Mapping logico → fisico delle zone"
    I numeri di zona (1, 2, 3) sono **logici e per-subscription**: la "zona 1" della subscription A può essere un datacenter fisico diverso dalla "zona 1" della subscription B. Per co-locare risorse di subscription diverse nella stessa zona fisica leggere `availabilityZoneMappings` (`az rest --method get --url "/subscriptions/<sub-id>/locations?api-version=2022-12-01"`) invece di assumere che i numeri coincidano.

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
| Germany West Central | Germany North |
| Switzerland North | Switzerland West |
| Norway East | Norway West |

!!! note "Region Pair: modello in evoluzione"
    Le region più recenti (es. Spain Central, Poland Central) **non hanno un pair**: Microsoft le progetta con Availability Zones come primo livello di resilienza. Per il DR cross-region non assumere il pair: scegliere esplicitamente la region secondaria (stessa geography se richiesto da data residency). La tabella sopra è indicativa: la fonte autorevole è la pagina Microsoft *cross-region replication* (vedi Riferimenti). Alcuni pair non sono simmetrici.

**Implicazioni pratiche (per le region con pair):**
- Geo-redundant storage (GRS/GZRS) replica nel pair automaticamente, in modo asincrono (nessun SLA di RPO, tipicamente <15 min)
- Azure Site Recovery propone il pair come target di default (modificabile)
- Gli aggiornamenti pianificati del platform vengono rollati su una region alla volta
- In caso di outage regionale, Microsoft dà priorità al ripristino di una delle due region

---

## Sovereign Clouds

| Cloud | Destinatari | Isolamento |
|-------|-------------|------------|
| **Azure Government** | Agenzie US Federal, State, Local | Fisicamente separato, operato da US citizens screened |
| **Azure China (21Vianet)** | Organizzazioni in Cina | Operato da 21Vianet, separato da Azure globale |
| **Azure Germany** (legacy, chiuso 2021) | Dati sensibili tedeschi (data trustee T-Systems) | Dismesso: sostituito dalle region standard `Germany West Central`/`Germany North` con garanzie di data residency |
| **Microsoft Sovereign Cloud** | Organizzazioni UE con requisiti di sovranità | Offerta a livelli sopra Azure pubblico (controlli di sovranità, Data Guardian, opzioni private/in-country): verificare la disponibilità corrente |

Azure Government include anche ambienti per classificazioni elevate (Secret/Top Secret) accessibili solo a clienti autorizzati.

---

## Rete Backbone Globale

Microsoft possiede e opera una rete privata **WAN globale** che collega tutte le region Azure:
- Centinaia di migliaia di km di fibra sottomarina e terrestre, con punti di presenza (**edge locations / PoP**) vicini agli utenti
- Traffico tra region Azure viaggia sulla rete privata Microsoft (non Internet pubblica)
- Microsoft pubblica le **statistiche di round-trip latency** tra region (non è una latenza garantita da SLA): intra-Europa tipicamente decine di ms; verificare le tabelle ufficiali

Gli edge PoP servono Front Door, CDN, ExpressRoute e l'ingresso del traffico sul backbone (*early exit*: il traffico entra nella rete Microsoft il prima possibile). **Azure Extended Zones** estendono una region parent a città specifiche per workload a bassissima latenza.

```bash
# Misurare latenza inter-region da una VM Azure con Connection Monitor
# (richiede l'agente Network Watcher installato sulla VM sorgente)
az network watcher connection-monitor create \
    --name latency-test \
    --resource-group myapp-rg \
    --location italynorth \
    --source-resource myvm \
    --dest-resource myvm-westeurope
```

---

## Troubleshooting

### Scenario 1 — Il servizio non è disponibile nella region selezionata

**Sintomo:** Al momento del deploy di una risorsa (es. VM SKU, servizio PaaS) compare l'errore `SkuNotAvailable` / `The requested size is not available in the location`.

**Causa:** Non tutti i servizi o SKU sono disponibili in tutte le region. Le region più recenti (es. Italy North) hanno disponibilità limitata rispetto alle region mature.

**Soluzione:** Verificare la disponibilità del servizio nella region target e, se necessario, usare la region pair come alternativa.

```bash
# Verificare quali SKU VM sono disponibili in una region
az vm list-skus \
    --location italynorth \
    --query "[?resourceType=='virtualMachines'].{Name:name, Restrictions:restrictions}" \
    --output table

# Verificare disponibilità di un servizio specifico per region
az provider show \
    --namespace Microsoft.Sql \
    --query "resourceTypes[?resourceType=='servers'].locations" \
    --output table
```

---

### Scenario 2 — VM deployata in una zona non corrisponde alle aspettative di HA

**Sintomo:** Due VM dello stesso tier vengono deployate nella stessa zona fisica, vanificando la ridondanza di zona.

**Causa:** Se non si specifica la zona, la VM è **regionale (non zonale)**: Azure la colloca dove vuole nella region, senza garanzia di separazione tra datacenter. Anche con zone indicate, ricordare il mapping logico→fisico per-subscription.

**Soluzione:** Specificare zone diverse esplicitamente per ciascuna VM critica (o usare una VM Scale Set multi-zona, che distribuisce le istanze automaticamente).

```bash
# Deploy VM in zone diverse (zona 1 e zona 2)
az vm create \
    --resource-group myapp-rg \
    --name myvm-zone1 \
    --image Ubuntu2204 \
    --zone 1 \
    --size Standard_D2s_v5

az vm create \
    --resource-group myapp-rg \
    --name myvm-zone2 \
    --image Ubuntu2204 \
    --zone 2 \
    --size Standard_D2s_v5

# Verificare la zona assegnata a ciascuna VM
az vm list \
    --resource-group myapp-rg \
    --query "[].{Name:name, Zone:zones}" \
    --output table
```

---

### Scenario 3 — Geo-redundant storage non replica nella region attesa

**Sintomo:** I dati di uno storage account GRS non risultano nella region pair prevista (es. Italy North → Germany West Central).

**Causa:** La region pair è assegnata da Microsoft e non è configurabile; la tabella della KB può essere superata o non simmetrica. La replica GRS è asincrona: i dati possono non essere ancora presenti nella secondary (Last Sync Time).

**Soluzione:** Verificare la region pair reale tramite CLI e controllare `lastSyncTime`.

```bash
# Verificare la region pair di uno storage account
az storage account show \
    --name mystorageaccount \
    --resource-group myapp-rg \
    --expand geoReplicationStats \
    --query "{Primary:primaryLocation, Secondary:secondaryLocation, Sku:sku.name, LastSyncTime:geoReplicationStats.lastSyncTime}" \
    --output table

# Ottenere la region pair di una location
az account list-locations \
    --query "[?name=='italynorth'].{Name:name, PairedRegion:metadata.pairedRegion[0].name}" \
    --output table
```

---

### Scenario 4 — Accesso a Azure Government o Azure China fallisce con credenziali globali

**Sintomo:** Il login con `az login` riesce ma i comandi falliscono con `AuthorizationFailed` o resource non trovate quando si tenta di accedere a risorse sovereign cloud.

**Causa:** Azure Government e Azure China sono endpoint separati dal cloud globale. Le credenziali e i token del cloud globale non sono validi nei sovereign cloud.

**Soluzione:** Effettuare il login specificando l'ambiente corretto con `az cloud set` prima di `az login`.

```bash
# Login su Azure Government
az cloud set --name AzureUSGovernment
az login

# Login su Azure China (21Vianet)
az cloud set --name AzureChinaCloud
az login

# Verificare l'ambiente attivo
az cloud show --query name --output tsv

# Tornare al cloud pubblico globale
az cloud set --name AzureCloud
az login
```

---

## Riferimenti

- [Azure Global Infrastructure](https://azure.microsoft.com/global-infrastructure/)
- [Azure Geographies](https://azure.microsoft.com/global-infrastructure/geographies/)
- [Availability Zones](https://learn.microsoft.com/azure/reliability/availability-zones-overview)
- [Azure Region Pairs / cross-region replication](https://learn.microsoft.com/azure/reliability/cross-region-replication-azure)
