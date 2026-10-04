---
title: "Connettività Ibrida Azure"
slug: connettivita-azure
category: cloud
tags: [azure, vpn-gateway, expressroute, virtual-wan, site-to-site, point-to-site, hybrid-connectivity]
search_keywords: [Azure VPN Gateway, Site-to-Site VPN, Point-to-Site VPN P2S, ExpressRoute, ExpressRoute Direct, FastPath, Virtual WAN vWAN, hybrid connectivity Azure, on-premises to Azure, BGP Azure VPN, active-active VPN, ExpressRoute circuit, ExpressRoute Global Reach, Azure extended network]
parent: cloud/azure/networking/_index
related: [cloud/azure/networking/vnet, cloud/azure/networking/load-balancing]
official_docs: https://learn.microsoft.com/azure/vpn-gateway/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Connettività Ibrida Azure

## Opzioni di Connettività

| Soluzione | Throughput | Latenza | SLA | Crittografia | Use Case |
|-----------|-----------|---------|-----|--------------|---------|
| **VPN Gateway S2S** | fino a 10 Gbps | variabile (Internet) | 99.95% | IPSec/IKE | Uffici, branch office |
| **ExpressRoute** | 50 Mbps - 100 Gbps | bassa, prevedibile | 99.95% (circuito singolo); 99.99% con Maximum Resiliency (due circuiti in due peering location) | Non di default (MACsec su ExpressRoute Direct, o IPsec sopra ER) | Enterprise, dati sensibili |
| **ExpressRoute + VPN** | - | ExpressRoute + fallback | dipende dalla topologia (VPN come backup sconsigliato per carichi mission-critical/latency-sensitive: preferire Maximum Resiliency) | IPSec | Mission critical + DR |
| **Virtual WAN** | fino a 20 Gbps/branch | ottimizzato | 99.95% | IPSec/SD-WAN | Multi-branch, SDWAN |

---

## VPN Gateway

!!! note "Termini usati in questa sezione"
    **GatewaySubnet**: subnet riservata (nome obbligatorio, consigliato almeno /27) dove Azure inietta le VM del gateway. **Local Network Gateway (LNG)**: oggetto Azure che descrive il router on-premises (IP pubblico + prefissi). **IKE/IPsec**: protocolli di negoziazione chiavi e cifratura del tunnel. **BGP/ASN**: protocollo di routing dinamico e numero di sistema autonomo; con BGP le route si propagano senza prefissi statici, abilitando failover automatico e multi-sito.

!!! warning "SKU non-AZ in dismissione"
    Gli SKU non-AZ `VpnGw1-5` sono **ritirati dal 30 settembre 2026**: dal 1 novembre 2025 non si creano più nuovi gateway, e i gateway esistenti non-AZ non accettano più modifiche di configurazione finché non vengono migrati al corrispondente `VpnGw1AZ-5AZ` (upgrade manuale da portale/PowerShell/CLI, nessun downtime nella stessa famiglia con IP Standard). Usare sempre IP pubblici **Standard**: i Basic public IP vanno migrati con il migration tool (che porta il gateway a Generation 2). Lo SKU VPN Gateway `Basic` **non** è in ritiro, ma non supporta BGP né Entra ID P2S; gli SKU legacy Standard/High Performance sono ritirati (30 settembre 2025).

### Site-to-Site VPN

Connette la rete on-premises ad Azure tramite tunnel IPSec/IKE su Internet:

```bash
# Nota: commenti sopra i comandi; un commento dopo "\" rompe la continuazione di riga.

# 1. Creare VPN Gateway (richiede GatewaySubnet nella VNet)
#    --sku: usare VpnGw1AZ-VpnGw5AZ (SKU non-AZ e Basic sono legacy)
#    --vpn-type: RouteBased (BGP, multi-site, IKEv2); PolicyBased solo su Basic (legacy)
#    --public-ip-addresses: due IP Standard = active-active (HA, due tunnel per sito)
az network vnet-gateway create \
    --resource-group myapp-rg \
    --name production-vpngw \
    --vnet production-vnet \
    --gateway-type Vpn \
    --sku VpnGw2AZ \
    --vpn-gateway-generation Generation2 \
    --vpn-type RouteBased \
    --asn 65515 \
    --public-ip-addresses vpngw-pip1 vpngw-pip2

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
| VpnGw1 (legacy) | 650 Mbps | 30 | No |
| VpnGw2 (legacy) | 1 Gbps | 30 | No |
| VpnGw3 (legacy) | 1.25 Gbps | 30 | No |
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

# Autenticazione con Microsoft Entra ID (ex Azure AD): solo OpenVPN, nessun
# certificato da distribuire, supporta Conditional Access/MFA.
# --aad-audience = App ID Microsoft-registered dell'Azure VPN Client (raccomandato,
#   stesso valore per tutti i cloud, nessuna registrazione/admin consent nel tenant)
# L'issuer richiede lo slash finale; un gateway supporta un solo valore di audience.
az network vnet-gateway update \
    --resource-group myapp-rg \
    --name production-vpngw \
    --vpn-auth-type AAD \
    --aad-tenant "https://login.microsoftonline.com/$TENANT_ID" \
    --aad-audience "c632b3df-fb67-4d84-bdcf-b95ad541b5c8" \
    --aad-issuer "https://sts.windows.net/$TENANT_ID/"
```

!!! warning "App ID registrata manualmente in ritiro"
    L'audience legacy `41b23e61-6c1e-4545-b367-cd054e0ed4b4` (app registrata a mano, Azure Public) smette di funzionare il **31 marzo 2028** (31 marzo 2029 per Azure Government e 21Vianet): migrare a quella Microsoft-registered. Il client Azure VPN per Linux (preview) è stato ritirato il 31 agosto 2026; client supportati: Windows e macOS.


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

### Peering ExpressRoute

Ogni circuito trasporta uno o più *peering* (sessioni BGP separate; l'equivalente AWS è la VIF):

| Peering | Descrizione |
|---------|-------------|
| **Private Peering** | Accesso a risorse Azure (VM, VNet) — IP privati |
| **Microsoft Peering** | Accesso a Microsoft 365 e endpoint pubblici dei servizi PaaS Azure (Storage, SQL) — IP pubblici, richiede NAT con prefissi pubblici del cliente. L'ex *Azure Public Peering* è deprecato |

```bash
# Creare circuito ExpressRoute
az network express-route create \
    --resource-group myapp-rg \
    --name production-circuit \
    --bandwidth 1000 \                        # Mbps: 50, 100, 200, 500, 1000, 2000, 5000, 10000
    --peering-location "Milan" \              # location del provider
    --provider "Equinix" \
    --sku-family MeteredData \                # MeteredData o UnlimitedData
    --sku-tier Standard \                     # Standard o Premium (Premium: cross-geopolitical region, più route/VNet)
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
# - Routing tra branch e Internet solo se l'hub è "secured" (Azure Firewall Manager + routing intent)
```

---

## Troubleshooting

### Scenario 1 — Tunnel VPN Site-to-Site non si connette

**Sintomo:** La connessione VPN rimane in stato `Unknown` o `NotConnected` dopo la creazione.

**Causa:** Mismatch nei parametri IKE/IPSec (pre-shared key, algoritmi di crittografia, DH group) tra il VPN Gateway Azure e il dispositivo on-premises, oppure firewall che blocca le porte UDP 500/4500.

**Soluzione:** Verificare i parametri di negoziazione IKE e lo stato della connessione:

```bash
# Verificare stato connessione e dettagli errore
az network vpn-connection show \
    --resource-group myapp-rg \
    --name on-premises-connection \
    --query "{status:connectionStatus, ingress:ingressBytesTransferred, egress:egressBytesTransferred}"

# Generare lo script di configurazione del dispositivo on-premises
# (confrontare parametri IKE/IPsec con quelli effettivi del device)
az network vpn-connection show-device-config-script \
    --resource-group myapp-rg \
    --name on-premises-connection \
    --vendor Cisco --device-family ISR --firmware-version IOS-12.x

# Avviare packet capture sul VPN Gateway per debug IKE (poi stop-packet-capture con SAS URL)
az network vnet-gateway start-packet-capture \
    --resource-group myapp-rg \
    --name production-vpngw

# Controllare BGP peers (se BGP abilitato)
az network vnet-gateway list-bgp-peer-status \
    --resource-group myapp-rg \
    --name production-vpngw
```

---

### Scenario 2 — Circuito ExpressRoute in stato "Not Provisioned"

**Sintomo:** Il circuito ExpressRoute mostra `CircuitProvisioningState: NotProvisioned` o `ServiceProviderProvisioningState: NotProvisioned` e non è possibile instradare traffico.

**Causa:** Il provider di connettività non ha ancora completato il provisioning fisico del cross-connect, oppure il `serviceKey` non è stato comunicato correttamente al provider.

**Soluzione:**

```bash
# Verificare stato corrente del circuito
az network express-route show \
    --resource-group myapp-rg \
    --name production-circuit \
    --query "{provisioningState:provisioningState, serviceProviderState:serviceProviderProvisioningState, serviceKey:serviceKey}"

# Verificare che i peering siano configurati correttamente
az network express-route peering list \
    --resource-group myapp-rg \
    --circuit-name production-circuit \
    --output table

# Controllare le route apprese dal circuito
az network express-route list-route-tables \
    --resource-group myapp-rg \
    --name production-circuit \
    --peering-name AzurePrivatePeering \
    --path primary
```

> Il `serviceKey` deve essere fornito al provider prima che possa procedere. Se il provider conferma il provisioning ma lo stato rimane `NotProvisioned`, aprire un ticket Microsoft Support.

---

### Scenario 3 — Route BGP non propagate alle VNet spoke

**Sintomo:** Le VM nelle VNet spoke non raggiungono la rete on-premises nonostante il tunnel VPN o ExpressRoute sia attivo e il BGP mostri peers connessi.

**Causa:** Route mancanti nella route table del gateway, policy BGP che filtrano i prefissi, propagazione delle route del gateway disabilitata, oppure (hub-spoke) peering VNet senza *Allow gateway transit* sull'hub e *Use remote gateways* sullo spoke: senza questi flag lo spoke non apprende le route del gateway dell'hub.

**Soluzione:**

```bash
# Verificare route effettive propagate al gateway
az network vnet-gateway list-advertised-routes \
    --resource-group myapp-rg \
    --name production-vpngw \
    --peer 169.254.21.1   # IP BGP peer on-premises

# Verificare route learned (ricevute dall'on-premises)
az network vnet-gateway list-learned-routes \
    --resource-group myapp-rg \
    --name production-vpngw

# Verificare che la subnet spoke abbia propagazione route gateway abilitata
az network vnet subnet show \
    --resource-group myapp-rg \
    --vnet-name spoke-vnet \
    --name default \
    --query routeTable

# Abilitare propagazione route gateway su una route table esistente
az network route-table update \
    --resource-group myapp-rg \
    --name spoke-rt \
    --disable-bgp-route-propagation false
```

---

### Scenario 4 — Client Point-to-Site non riesce a connettersi

**Sintomo:** Il client VPN P2S riceve errore di autenticazione o il tunnel si connette ma non raggiunge le risorse Azure.

**Causa:** Certificato client scaduto o revocato, pool di indirizzi P2S in conflitto con subnet Azure/on-premises, oppure mancata aggiunta dei DNS custom al profilo VPN.

**Soluzione:**

```bash
# Verificare certificati root caricati sul gateway
az network vnet-gateway show \
    --resource-group myapp-rg \
    --name production-vpngw \
    --query vpnClientConfiguration.vpnClientRootCertificates

# Revocare un certificato client specifico
az network vnet-gateway revoked-cert create \
    --resource-group myapp-rg \
    --gateway-name production-vpngw \
    --name compromised-client-cert \
    --thumbprint "ABCDEF1234567890..."

# Scaricare profilo VPN aggiornato (dopo modifiche)
az network vnet-gateway vpn-client generate \
    --resource-group myapp-rg \
    --name production-vpngw \
    --processor-architecture Amd64

# Verificare configurazione P2S corrente (pool IP, protocolli)
az network vnet-gateway show \
    --resource-group myapp-rg \
    --name production-vpngw \
    --query vpnClientConfiguration
```

---

## ExpressRoute: FastPath, Direct e MACsec

- **FastPath**: il traffico on-premises → VM bypassa il gateway ExpressRoute (meno hop, più throughput). Richiede gateway `UltraPerformance`, `ErGw3AZ` o `ErGwScale` (≥10 scale unit). Solo su **ExpressRoute Direct**: VNet peering (stessa region, no global peering), UDR, IPv6, Private Link (limited GA con enrollment). Non copre ILB/PaaS/Azure Firewall/DNS Private Resolver nelle spoke: il traffico passa dal gateway. Limiti IP: 25.000 (provider ≤10 Gbps), 100.000 (Direct 10 Gbps), 200.000 (Direct 100/400 Gbps).
- **ExpressRoute Direct**: porte fisiche dirette sul backbone Microsoft (due porte per risorsa), 10/100 Gbps (taglie superiori su alcune location).
- **MACsec** (solo Direct): cifratura L2 tra i tuoi router e gli MSEE. CAK/CKN in Key Vault (soft-delete attivo, **non** dietro private endpoint) + user-assigned managed identity. Cifrari: `GcmAes128/256` (10 Gbps); su ≥40 Gbps preferire `GcmAesXpn128/256`. Con router Cisco abilitare SCI.

```powershell
$erDirect.Links[0].MacSecConfig.Cipher = "GcmAes256"   # poi Set-AzExpressRoutePort
```

## Scegliere: VPN vs ExpressRoute vs Virtual WAN

| Esigenza | Scelta |
|----------|--------|
| Pochi siti/sviluppatori, costo basso, Internet accettabile | VPN Gateway S2S/P2S |
| Latenza prevedibile, banda alta, dati sensibili | ExpressRoute (Maximum Resiliency per SLA 99.99%) |
| Molti branch/SD-WAN, routing transit automatico | Virtual WAN |
| Backup di un circuito ER | Secondo circuito in altra location (preferito); VPN S2S coesistente solo per carichi non critici |

Coesistenza ER + VPN: stessa VNet, due gateway nella `GatewaySubnet` (ER gateway + VPN gateway con BGP); le route ER hanno precedenza sulle VPN a parità di prefisso, la VPN subentra in caso di failure.

## Riferimenti

- [VPN Gateway Documentation](https://learn.microsoft.com/azure/vpn-gateway/)
- [ExpressRoute Documentation](https://learn.microsoft.com/azure/expressroute/)
- [Virtual WAN](https://learn.microsoft.com/azure/virtual-wan/)
- [ExpressRoute Global Reach](https://learn.microsoft.com/azure/expressroute/expressroute-global-reach)
- [Hybrid Network Reference Architectures](https://learn.microsoft.com/azure/architecture/reference-architectures/hybrid-networking/)
