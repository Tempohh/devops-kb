---
title: "Azure Virtual Network (VNet)"
slug: vnet-azure
category: cloud
tags: [azure, vnet, subnet, nsg, asg, route-table, peering, private-endpoint, service-endpoint, bastion]
search_keywords: [Azure VNet, Virtual Network Azure, subnet Azure, NSG Network Security Group, ASG Application Security Group, route table UDR, VNet peering, Private Endpoint, Service Endpoint, Azure Bastion, hub and spoke network topology, forced tunneling, network topology Azure, CIDR Azure, IP address space]
parent: cloud/azure/networking/_index
related: [cloud/azure/networking/load-balancing, cloud/azure/networking/connettivita, cloud/azure/security/_index]
official_docs: https://learn.microsoft.com/azure/virtual-network/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Virtual Network (VNet)

Una **Virtual Network (VNet)** è la rete privata isolata di Azure — equivalente a un datacenter on-premises ma virtualizzato.

## Architettura Hub-and-Spoke

```
                    ┌──────────────────────────┐
                    │       Hub VNet            │
                    │  (10.0.0.0/16)            │
                    │  ┌─────────────────────┐  │
                    │  │   Azure Firewall    │  │
                    │  │   VPN Gateway       │  │
                    │  │   Azure Bastion     │  │
                    │  └─────────────────────┘  │
                    └──────────┬───────────────┘
                               │ VNet Peering
              ┌────────────────┼─────────────────┐
              ▼                ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  Spoke VNet   │  │  Spoke VNet   │  │  Spoke VNet   │
    │  Production   │  │  Staging      │  │  Dev          │
    │  10.1.0.0/16  │  │  10.2.0.0/16  │  │  10.3.0.0/16  │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Creare VNet e Subnet

```bash
# Creare VNet
az network vnet create \
    --resource-group myapp-rg \
    --name production-vnet \
    --address-prefix 10.1.0.0/16 \
    --location italynorth

# Creare subnet
az network vnet subnet create \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name web-subnet \
    --address-prefix 10.1.1.0/24

az network vnet subnet create \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name app-subnet \
    --address-prefix 10.1.2.0/24

az network vnet subnet create \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name data-subnet \
    --address-prefix 10.1.3.0/24

az network vnet subnet create \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name AzureBastionSubnet \        # NOME FISSO obbligatorio per Azure Bastion
    --address-prefix 10.1.255.0/27     # min /27 richiesto

az network vnet subnet create \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name GatewaySubnet \             # NOME FISSO obbligatorio per VPN Gateway
    --address-prefix 10.1.254.0/27
```

**Indirizzi riservati Azure per subnet:**
- `.0` — Network address
- `.1` — Default gateway
- `.2`, `.3` — Azure DNS
- `.255` — Broadcast
→ Una /29 ha 8 IP ma solo **3 utilizzabili**

---

## Network Security Groups (NSG)

Gli **NSG** filtrano il traffico di rete tramite regole allow/deny. Applicabili a **subnet** o **singola NIC**.

```bash
# Creare NSG
az network nsg create \
    --resource-group myapp-rg \
    --name web-nsg

# Regola: allow HTTPS inbound da Internet
az network nsg rule create \
    --resource-group myapp-rg \
    --nsg-name web-nsg \
    --name allow-https-inbound \
    --priority 100 \
    --protocol Tcp \
    --direction Inbound \
    --source-address-prefixes Internet \
    --source-port-ranges '*' \
    --destination-address-prefixes '*' \
    --destination-port-ranges 443 \
    --access Allow

# Regola: allow HTTP inbound (per redirect)
az network nsg rule create \
    --resource-group myapp-rg \
    --nsg-name web-nsg \
    --name allow-http-inbound \
    --priority 110 \
    --protocol Tcp \
    --direction Inbound \
    --source-address-prefixes Internet \
    --destination-port-ranges 80 \
    --access Allow

# Regola: allow SSH solo da IP corporate
az network nsg rule create \
    --resource-group myapp-rg \
    --nsg-name web-nsg \
    --name allow-ssh-corporate \
    --priority 200 \
    --protocol Tcp \
    --direction Inbound \
    --source-address-prefixes 203.0.113.0/24 \     # IP corporate
    --destination-port-ranges 22 \
    --access Allow

# Regola: deny tutto il resto inbound
# (non necessaria — il default è già Deny per regole senza match)

# Applicare NSG alla subnet
az network vnet subnet update \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name web-subnet \
    --network-security-group web-nsg

# Listare regole NSG (ordinate per priorità)
az network nsg rule list \
    --resource-group myapp-rg \
    --nsg-name web-nsg \
    --include-default \
    --query "sort_by([], &priority)[].{Priority:priority, Name:name, Direction:direction, Access:access, Port:destinationPortRange}" \
    --output table
```

**Regole default NSG (non eliminabili):**

| Priority | Nome | Direzione | Accesso |
|----------|------|-----------|---------|
| 65000 | AllowVnetInBound | Inbound | Allow (VirtualNetwork → VirtualNetwork) |
| 65001 | AllowAzureLoadBalancerInBound | Inbound | Allow (AzureLoadBalancer) |
| 65500 | DenyAllInBound | Inbound | Deny (tutti) |
| 65000 | AllowVnetOutBound | Outbound | Allow (VirtualNetwork) |
| 65001 | AllowInternetOutBound | Outbound | Allow (Internet) |
| 65500 | DenyAllOutBound | Outbound | Deny (tutti) |

---

## Application Security Groups (ASG)

Gli **ASG** raggruppano VM per applicare regole NSG senza specificare IP:

```bash
# Creare ASG per tier applicativo
az network asg create --resource-group myapp-rg --name asg-web
az network asg create --resource-group myapp-rg --name asg-app
az network asg create --resource-group myapp-rg --name asg-db

# NSG con regole basate su ASG (non su IP)
az network nsg rule create \
    --resource-group myapp-rg \
    --nsg-name app-nsg \
    --name web-to-app \
    --priority 100 \
    --direction Inbound \
    --source-asgs asg-web \            # solo VM nel gruppo web
    --destination-asgs asg-app \       # verso VM nel gruppo app
    --destination-port-ranges 8080 \
    --access Allow \
    --protocol Tcp

# Associare NIC di VM all'ASG
az network nic update \
    --resource-group myapp-rg \
    --name myvm-nic \
    --application-security-groups asg-web
```

---

## Route Tables (UDR — User Defined Routes)

```bash
# Creare route table con forced tunneling (tutto via Azure Firewall)
az network route-table create \
    --resource-group myapp-rg \
    --name app-route-table \
    --disable-bgp-route-propagation true    # non propagare route BGP da VPN Gateway

# Route: instrada tutto il traffico Internet via Azure Firewall
az network route-table route create \
    --resource-group myapp-rg \
    --route-table-name app-route-table \
    --name default-to-firewall \
    --address-prefix 0.0.0.0/0 \
    --next-hop-type VirtualAppliance \
    --next-hop-ip-address 10.0.0.4         # IP privato Azure Firewall

# Associare route table alla subnet
az network vnet subnet update \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name app-subnet \
    --route-table app-route-table
```

---

## VNet Peering

Il **VNet Peering** connette due VNet usando la backbone Microsoft (non Internet, bassa latenza):

```bash
# Peering Hub ↔ Spoke (bidirezionale — richiede due operazioni)
az network vnet peering create \
    --resource-group hub-rg \
    --name hub-to-production \
    --vnet-name hub-vnet \
    --remote-vnet /subscriptions/$SUB_ID/resourceGroups/prod-rg/providers/Microsoft.Network/virtualNetworks/production-vnet \
    --allow-vnet-access true \
    --allow-forwarded-traffic true \
    --allow-gateway-transit true           # hub espone il VPN Gateway agli spoke

az network vnet peering create \
    --resource-group prod-rg \
    --name production-to-hub \
    --vnet-name production-vnet \
    --remote-vnet /subscriptions/$SUB_ID/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet \
    --allow-vnet-access true \
    --allow-forwarded-traffic true \
    --use-remote-gateways true             # spoke usa il VPN Gateway dell'hub
```

!!! warning "VNet Peering non è transitivo"
    Se Hub ↔ Spoke1 e Hub ↔ Spoke2, Spoke1 NON può comunicare direttamente con Spoke2.
    Il traffico deve passare per l'hub (via Azure Firewall o NVA).
    Alternativa: **Azure Virtual WAN** per topologie spoke-to-spoke automatiche.

---

## Private Endpoints e Service Endpoints

### Private Endpoint

Porta un **servizio PaaS** (Azure SQL, Storage, Key Vault) dentro la VNet con un IP privato:

```bash
# Creare Private Endpoint per Azure SQL
az network private-endpoint create \
    --resource-group myapp-rg \
    --name sql-private-endpoint \
    --vnet-name production-vnet \
    --subnet data-subnet \
    --private-connection-resource-id \
        "/subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Sql/servers/mydb-server" \
    --group-ids sqlServer \
    --connection-name sql-connection

# Creare Private DNS Zone per risoluzione nomi (obbligatorio)
az network private-dns zone create \
    --resource-group myapp-rg \
    --name "privatelink.database.windows.net"

az network private-dns link vnet create \
    --resource-group myapp-rg \
    --zone-name "privatelink.database.windows.net" \
    --name sql-dns-link \
    --virtual-network production-vnet \
    --registration-enabled false

# Creare record DNS per il PE
az network private-endpoint dns-zone-group create \
    --resource-group myapp-rg \
    --endpoint-name sql-private-endpoint \
    --name sql-dns-group \
    --private-dns-zone "privatelink.database.windows.net" \
    --zone-name sql
```

### Service Endpoint

Estende l'identità della VNet ai servizi Azure (meno sicuro di Private Endpoint, accesso via backbone ma IP pubblico):

```bash
# Abilitare Service Endpoint su subnet per Storage
az network vnet subnet update \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name app-subnet \
    --service-endpoints Microsoft.Storage Microsoft.Sql Microsoft.KeyVault

# Limitare Storage Account alla subnet (via firewall regola)
az storage account network-rule add \
    --resource-group myapp-rg \
    --account-name mystorageaccount \
    --vnet-name production-vnet \
    --subnet app-subnet
```

---

## Azure Bastion

**Azure Bastion** fornisce accesso RDP/SSH sicuro alle VM tramite browser — senza IP pubblico:

```bash
# Creare Public IP per Bastion
az network public-ip create \
    --resource-group myapp-rg \
    --name bastion-pip \
    --sku Standard \
    --location italynorth

# Creare Azure Bastion
az network bastion create \
    --resource-group myapp-rg \
    --name production-bastion \
    --public-ip-address bastion-pip \
    --vnet-name production-vnet \
    --location italynorth \
    --sku Standard \          # Basic (SSH/RDP solo), Standard (file transfer, tunneling)
    --enable-tunneling true   # Standard: permette native RDP/SSH client via tunnel

# Connettersi a VM via Bastion (dalla CLI — richiede Bastion Standard)
az network bastion ssh \
    --name production-bastion \
    --resource-group myapp-rg \
    --target-resource-id /subscriptions/.../resourceGroups/myapp-rg/providers/Microsoft.Compute/virtualMachines/myvm \
    --auth-type "AAD"              # AAD (Entra ID), password, ssh-key
```

---

## Riferimenti

- [VNet Documentation](https://learn.microsoft.com/azure/virtual-network/)
- [NSG Documentation](https://learn.microsoft.com/azure/virtual-network/network-security-groups-overview)
- [Private Endpoints](https://learn.microsoft.com/azure/private-link/private-endpoint-overview)
- [VNet Peering](https://learn.microsoft.com/azure/virtual-network/virtual-network-peering-overview)
- [Azure Bastion](https://learn.microsoft.com/azure/bastion/)
