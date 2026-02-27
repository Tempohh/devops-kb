---
title: "Connettività Ibrida Azure"
slug: connettivita-azure
category: cloud
tags: [azure, vpn-gateway, expressroute, virtual-wan, site-to-site, point-to-site, hybrid-connectivity]
search_keywords: [Azure VPN Gateway, Site-to-Site VPN, Point-to-Site VPN P2S, ExpressRoute, ExpressRoute Direct, FastPath, Virtual WAN vWAN, hybrid connectivity Azure, on-premises to Azure, BGP Azure VPN, active-active VPN, ExpressRoute circuit, ExpressRoute Global Reach, Azure extended network]
parent: cloud/azure/networking/_index
related: [cloud/azure/networking/vnet, cloud/azure/networking/load-balancing]
official_docs: https://learn.microsoft.com/azure/vpn-gateway/
status: complete
difficulty: advanced
last_updated: 2026-02-26
---

# Connettività Ibrida Azure

## Opzioni di Connettività

| Soluzione | Throughput | Latenza | SLA | Crittografia | Use Case |
|-----------|-----------|---------|-----|--------------|---------|
| **VPN Gateway S2S** | fino a 10 Gbps | variabile (Internet) | 99.95% | IPSec/IKE | Uffici, branch office |
| **ExpressRoute** | 50 Mbps - 100 Gbps | bassa, prevedibile | 99.95% | No (layer 3) | Enterprise, dati sensibili |
| **ExpressRoute + VPN** | - | ExpressRoute + fallback | 99.99%+ | IPSec | Mission critical + DR |
| **Virtual WAN** | fino a 20 Gbps/branch | ottimizzato | 99.95% | IPSec/SD-WAN | Multi-branch, SDWAN |

---

## VPN Gateway

### Site-to-Site VPN

Connette la rete on-premises ad Azure tramite tunnel IPSec/IKE su Internet:

```bash
# 1. Creare VPN Gateway (richiede GatewaySubnet nella VNet)
az network vnet-gateway create \
    --resource-group myapp-rg \
    --name production-vpngw \
    --vnet production-vnet \
    --gateway-type Vpn \
    --sku VpnGw2 \                     # Basic, VpnGw1-5, VpnGw1AZ-5AZ
    --vpn-gateway-generation Generation2 \
    --vpn-type RouteBased \            # RouteBased (BGP, multi-site) o PolicyBased (legacy)
    --public-ip-address vpngw-pip1 \
    --public-ip-address-2 vpngw-pip2   # Active-Active per HA (due IP pubblici)

# 2. Creare Local Network Gateway (rappresenta la rete on-premises)
az network local-gateway create \
    --resource-group myapp-rg \
    --name on-premises-lgw \
    --gateway-ip-address 203.0.113.1 \   # IP pubblico del router on-premises
    --local-address-prefixes 192.168.0.0/16 10.0.0.0/8 \   # subnet on-premises
    --asn 65001 \                          # BGP ASN (se BGP abilitato)
    --bgp-peering-address 169.254.21.1     # BGP peer IP on-premises

# 3. Creare VPN Connection
az network vpn-connection create \
    --resource-group myapp-rg \
    --name on-premises-connection \
    --vnet-gateway1 production-vpngw \
    --local-gateway2 on-premises-lgw \
    --shared-key "your-pre-shared-key-here" \    # PSK — usare stringa lunga e casuale
    --connection-type IPSec \
    --enable-bgp true \
    --routing-weight 10

# Verificare stato connessione
az network vpn-connection show \
    --resource-group myapp-rg \
    --name on-premises-connection \
    --query connectionStatus
```

**SKU VPN Gateway:**

| SKU | Max throughput | Max tunnel S2S | Zone-redundant |
|-----|---------------|----------------|----------------|
| VpnGw1 | 650 Mbps | 30 | No |
| VpnGw2 | 1 Gbps | 30 | No |
| VpnGw3 | 1.25 Gbps | 30 | No |
| VpnGw1AZ | 650 Mbps | 30 | **Sì** |
| VpnGw2AZ | 1 Gbps | 30 | **Sì** |
| VpnGw5AZ | 10 Gbps | 100 | **Sì** |

### Point-to-Site VPN (P2S)

Connessione VPN per singoli client (laptop, developers):

```bash
# Configurare P2S con autenticazione certificato
az network vnet-gateway update \
    --resource-group myapp-rg \
    --name production-vpngw \
    --address-prefixes 172.16.0.0/24 \    # pool IP per client VPN
    --client-protocol OpenVPN IkeV2        # OpenVPN (cross-platform), IkeV2 (Windows/Mac nativo)

# Autenticazione con Azure AD (Entra ID) — più comoda per Azure AD joined devices
az network vnet-gateway update \
    --resource-group myapp-rg \
    --name production-vpngw \
    --aad-tenant "https://login.microsoftonline.com/$TENANT_ID" \
    --aad-audience "41b23e61-6c1e-4545-b367-cd054e0ed4b4" \    # Azure VPN App ID fisso
    --aad-issuer "https://sts.windows.net/$TENANT_ID/"
```

---

## ExpressRoute

**ExpressRoute** connette la rete on-premises ad Azure tramite connessione privata dedicata (non su Internet pubblica) attraverso un provider di connettività:

```
On-Premises                 Provider                    Azure
─────────                   ────────                    ─────
Router ─── Cross-connect ──► ExpressRoute Location ──► Microsoft Edge ──► VNet
                             (es. Equinix Milan)
```

### Tipi di Circuito

| Tipo | Bandwidth | Descrizione |
|------|-----------|-------------|
| **Dedicated** | 50 Mbps - 10 Gbps | Circuito dedicato tramite provider (AT&T, Equinix, ecc.) |
| **ExpressRoute Direct** | 10 Gbps, 100 Gbps | Connessione diretta al backbone Microsoft |

### Virtual Network Interface (VIF)

| VIF | Descrizione |
|-----|-------------|
| **Private Peering** | Accesso a risorse Azure (VM, VNet) — IP privati |
| **Microsoft Peering** | Accesso a Microsoft 365, Azure Public Services (Storage, SQL) — IP pubblici |

```bash
# Creare circuito ExpressRoute
az network express-route create \
    --resource-group myapp-rg \
    --name production-circuit \
    --bandwidth 1000 \                        # Mbps: 50, 100, 200, 500, 1000, 2000, 5000, 10000
    --peering-location "Milan" \              # location del provider
    --provider "Equinix" \
    --sku-family MeteredData \                # MeteredData o UnlimitedData
    --sku-tier Standard \                     # Standard o Premium (Global Reach, più prefissi)
    --query serviceKey

# Fornire il serviceKey al provider per provisioning fisico del circuito
# Dopo provisioning, lo stato diventa "Provisioned"

# Creare VNet Gateway per ExpressRoute (tipo ExpressRoute, non VPN)
az network vnet-gateway create \
    --resource-group myapp-rg \
    --name er-gateway \
    --vnet production-vnet \
    --gateway-type ExpressRoute \
    --sku ErGw2AZ \                           # ErGw1, ErGw2, ErGw3, UltraPerformance, ErGwAZ variants
    --public-ip-address er-gw-pip

# Connettere circuito alla VNet
az network vpn-connection create \
    --resource-group myapp-rg \
    --name er-connection \
    --vnet-gateway1 er-gateway \
    --express-route-circuit2 production-circuit \
    --routing-weight 0
```

### ExpressRoute Global Reach

Connette due siti on-premises tra loro tramite la backbone Microsoft (senza passare per Internet):

```bash
# Collegare due circuiti ExpressRoute (es. Milano ↔ Londra)
az network express-route peering connection create \
    --resource-group myapp-rg \
    --circuit-name milan-circuit \
    --peering-name AzurePrivatePeering \
    --name milan-to-london \
    --peer-circuit /subscriptions/.../london-circuit \
    --address-prefix 192.168.100.0/29   # /29 per la connessione
```

---

## Azure Virtual WAN

**Azure Virtual WAN** è una piattaforma di networking gestita per connettere branch, utenti remoti e VNet in un'unica topologia hub-and-spoke:

```bash
# Creare Virtual WAN
az network vwan create \
    --resource-group myapp-rg \
    --name company-vwan \
    --type Standard              # Basic (solo VPN S2S) o Standard (tutto)

# Creare Virtual Hub in una region
az network vhub create \
    --resource-group myapp-rg \
    --name eu-hub \
    --vwan company-vwan \
    --location italynorth \
    --address-prefix 10.100.0.0/24   # spazio indirizzi dell'hub

# Connettere VNet all'hub
az network vhub connection create \
    --resource-group myapp-rg \
    --vhub-name eu-hub \
    --name production-connection \
    --remote-vnet /subscriptions/.../production-vnet

# Creare VPN Gateway nell'hub (per branch office)
az network vpn-gateway create \
    --resource-group myapp-rg \
    --name eu-hub-vpngw \
    --vhub eu-hub \
    --scale-unit 2                    # 2 = 1 Gbps, ogni unit = 500 Mbps

# Virtual WAN gestisce automaticamente:
# - Routing tra spoke VNet
# - Routing tra branch e VNet
# - Routing tra branch e Internet (via Azure Firewall nell'hub)
```

---

## Riferimenti

- [VPN Gateway Documentation](https://learn.microsoft.com/azure/vpn-gateway/)
- [ExpressRoute Documentation](https://learn.microsoft.com/azure/expressroute/)
- [Virtual WAN](https://learn.microsoft.com/azure/virtual-wan/)
- [ExpressRoute Global Reach](https://learn.microsoft.com/azure/expressroute/expressroute-global-reach)
- [Hybrid Network Reference Architectures](https://learn.microsoft.com/azure/architecture/reference-architectures/hybrid-networking/)
