---
title: "Azure DNS & CDN"
slug: dns-cdn-azure
category: cloud
tags: [azure, dns, private-dns, cdn, front-door, ddos-protection]
search_keywords: [Azure DNS, Azure Private DNS Zone, DNS forwarding Azure, Azure CDN, Azure Front Door CDN, DDoS Protection Standard Basic, Azure DNS resolver, custom domain Azure, DNS record types Azure, CNAME alias Azure, autoregistration DNS, split-horizon DNS Azure]
parent: cloud/azure/networking/_index
related: [cloud/azure/networking/vnet, cloud/azure/networking/load-balancing]
official_docs: https://learn.microsoft.com/azure/dns/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Azure DNS & CDN

## Azure DNS

**Azure DNS** ospita zone DNS (pubbliche e private) sulla stessa infrastruttura globale di Azure.

### Public DNS Zone

```bash
# Creare zona DNS pubblica (delegation del dominio registrar → Azure nameservers)
az network dns zone create \
    --resource-group myapp-rg \
    --name company.com

# Ottenere nameserver Azure (da configurare nel registrar)
az network dns zone show \
    --resource-group myapp-rg \
    --name company.com \
    --query nameServers \
    --output table

# Record A
az network dns record-set a add-record \
    --resource-group myapp-rg \
    --zone-name company.com \
    --record-set-name www \
    --ipv4-address 203.0.113.10

# Record CNAME
az network dns record-set cname set-record \
    --resource-group myapp-rg \
    --zone-name company.com \
    --record-set-name api \
    --cname myapp.italynorth.cloudapp.azure.com

# Record MX (email)
az network dns record-set mx add-record \
    --resource-group myapp-rg \
    --zone-name company.com \
    --record-set-name "@" \
    --exchange mail.company.com \
    --preference 10

# Record TXT (SPF, DKIM, verifica dominio)
az network dns record-set txt add-record \
    --resource-group myapp-rg \
    --zone-name company.com \
    --record-set-name "@" \
    --value "v=spf1 include:spf.protection.outlook.com -all"

# Alias record — punta a risorsa Azure (aggiorna IP automaticamente)
az network dns record-set a create \
    --resource-group myapp-rg \
    --zone-name company.com \
    --record-set-name "@" \
    --target-resource /subscriptions/.../publicIPAddresses/myapp-pip
    # Alias record supporta: Public IP, Load Balancer, Front Door, Traffic Manager

# Impostare TTL
az network dns record-set a update \
    --resource-group myapp-rg \
    --zone-name company.com \
    --name www \
    --set ttl=300
```

### Private DNS Zone

Le **Private DNS Zone** risolvono nomi all'interno delle VNet senza esporre al pubblico:

```bash
# Creare Private DNS Zone
az network private-dns zone create \
    --resource-group myapp-rg \
    --name internal.company.com

# Collegare alla VNet (VNet link)
az network private-dns link vnet create \
    --resource-group myapp-rg \
    --zone-name internal.company.com \
    --name production-link \
    --virtual-network production-vnet \
    --registration-enabled true           # true = autoregistration VM (A records automatici)

# Record A privato (per servizi non-VM)
az network private-dns record-set a add-record \
    --resource-group myapp-rg \
    --zone-name internal.company.com \
    --record-set-name database \
    --ipv4-address 10.1.3.10

# Zone per Private Endpoints (pattern nome fisso)
# Azure SQL: privatelink.database.windows.net
# Blob Storage: privatelink.blob.core.windows.net
# Key Vault: privatelink.vaultcore.azure.net
# App Service: privatelink.azurewebsites.net

az network private-dns zone create \
    --resource-group myapp-rg \
    --name "privatelink.database.windows.net"

az network private-dns link vnet create \
    --resource-group myapp-rg \
    --zone-name "privatelink.database.windows.net" \
    --name sql-dns-link \
    --virtual-network production-vnet \
    --registration-enabled false          # false per zone Private Endpoint
```

### Azure DNS Private Resolver

**Azure DNS Private Resolver** permette di risolvere DNS on-premises → Azure Private DNS e viceversa, senza custom DNS server:

```bash
# Creare DNS Private Resolver
az dns-resolver create \
    --resource-group myapp-rg \
    --dns-resolver-name company-resolver \
    --location italynorth \
    --id "/subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet"

# Creare Inbound Endpoint (on-premises → Azure)
# Subnet dedicata /28 minimo
az dns-resolver inbound-endpoint create \
    --dns-resolver-name company-resolver \
    --resource-group myapp-rg \
    --inbound-endpoint-name inbound \
    --ip-configurations '[{"privateIpAllocationMethod": "Dynamic", "id": "/subscriptions/.../subnets/DnsInboundSubnet"}]'

# Creare Outbound Endpoint (Azure → on-premises)
az dns-resolver outbound-endpoint create \
    --dns-resolver-name company-resolver \
    --resource-group myapp-rg \
    --outbound-endpoint-name outbound \
    --id "/subscriptions/.../subnets/DnsOutboundSubnet"

# Creare Forwarding Ruleset per forwarding selettivo
az dns-resolver forwarding-ruleset create \
    --resource-group myapp-rg \
    --forwarding-ruleset-name company-ruleset \
    --outbound-endpoints '[{"id": "/subscriptions/.../outbound"}]'

# Forwarding rule: dominio interno → DNS on-premises
az dns-resolver forwarding-rule create \
    --resource-group myapp-rg \
    --forwarding-ruleset-name company-ruleset \
    --forwarding-rule-name forward-to-onprem \
    --domain-name "corp.internal." \
    --target-dns-servers '[{"ipAddress": "192.168.1.53", "port": 53}]'
```

---

## Azure CDN

**Azure CDN** distribuisce contenuti statici tramite una rete di PoP globali per ridurre latenza:

```bash
# Creare CDN Profile
az cdn profile create \
    --resource-group myapp-rg \
    --name myapp-cdn \
    --sku Standard_Microsoft    # Standard_Microsoft, Standard_Akamai, Standard_Verizon, Premium_Verizon

# Creare CDN Endpoint
az cdn endpoint create \
    --resource-group myapp-rg \
    --profile-name myapp-cdn \
    --name myapp-content \
    --origin mystorageaccount.blob.core.windows.net \
    --origin-host-header mystorageaccount.blob.core.windows.net \
    --query-string-caching-behavior IgnoreQueryString \
    --content-types-to-compress "text/css" "application/javascript" "text/html" \
    --is-compression-enabled true

# Custom domain HTTPS per CDN
az cdn custom-domain create \
    --resource-group myapp-rg \
    --endpoint-name myapp-content \
    --profile-name myapp-cdn \
    --hostname cdn.company.com \
    --name cdn-company-com

az cdn custom-domain enable-https \
    --resource-group myapp-rg \
    --endpoint-name myapp-content \
    --profile-name myapp-cdn \
    --name cdn-company-com \
    --min-tls-version 1.2

# Purge cache CDN
az cdn endpoint purge \
    --resource-group myapp-rg \
    --profile-name myapp-cdn \
    --name myapp-content \
    --content-paths "/*"           # purge tutto
```

---

## Azure DDoS Protection

| Tier | Descrizione | Costo |
|------|-------------|-------|
| **DDoS Network Protection Basic** | Sempre attivo, automatico per tutte le risorse Azure | Gratuito |
| **DDoS Network Protection Standard** | Policy tuning, telemetria, alert, SLA 99.99%, rapid response team | ~$2950/mese per VNet protetta |
| **DDoS IP Protection** | Standard applicato a singolo IP pubblico | ~$199/mese per IP |

```bash
# Abilitare DDoS Protection Standard su VNet
az network ddos-protection create \
    --resource-group myapp-rg \
    --name company-ddos-plan \
    --location italynorth

az network vnet update \
    --resource-group myapp-rg \
    --name production-vnet \
    --ddos-protection true \
    --ddos-protection-plan company-ddos-plan

# Creare alert su metrica DDoS
az monitor alert create \
    --name ddos-attack-alert \
    --resource-group myapp-rg \
    --target /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.Network/publicIPAddresses/myapp-pip \
    --condition "avg Under DDoS attack > 0" \
    --action-group arn:operations-action-group
```

---

## Troubleshooting

### Scenario 1 — DNS privato non risolve dall'interno della VNet

**Sintomo:** Le VM nella VNet non riescono a risolvere nomi nella Private DNS Zone (es. `database.internal.company.com` restituisce NXDOMAIN).

**Causa:** Manca il VNet Link tra la Private DNS Zone e la VNet, oppure la VNet non usa i DNS resolver di Azure (168.63.129.16).

**Soluzione:** Verificare che esista il link e che la VNet sia configurata con DNS di default (168.63.129.16).

```bash
# Verificare i VNet link esistenti
az network private-dns link vnet list \
    --resource-group myapp-rg \
    --zone-name internal.company.com \
    --output table

# Verificare DNS server configurato nella VNet (deve essere vuoto = default Azure)
az network vnet show \
    --resource-group myapp-rg \
    --name production-vnet \
    --query "dhcpOptions.dnsServers"

# Creare il link mancante
az network private-dns link vnet create \
    --resource-group myapp-rg \
    --zone-name internal.company.com \
    --name production-link \
    --virtual-network production-vnet \
    --registration-enabled false
```

---

### Scenario 2 — Private Endpoint non risolve tramite nome privato

**Sintomo:** La connessione a un servizio PaaS (es. Azure SQL) tramite nome privato (`server.database.windows.net`) restituisce l'IP pubblico invece del 10.x.x.x del Private Endpoint.

**Causa:** La Private DNS Zone `privatelink.database.windows.net` non è collegata alla VNet corrente, oppure il record A non punta all'IP del Private Endpoint.

**Soluzione:**

```bash
# Verificare il record A nella zona privatelink
az network private-dns record-set a list \
    --resource-group myapp-rg \
    --zone-name "privatelink.database.windows.net" \
    --output table

# Verificare l'IP del Private Endpoint (deve corrispondere)
az network private-endpoint show \
    --resource-group myapp-rg \
    --name myapp-sql-pe \
    --query "customDnsConfigs[].ipAddresses" \
    --output table

# Verificare link VNet
az network private-dns link vnet list \
    --resource-group myapp-rg \
    --zone-name "privatelink.database.windows.net" \
    --output table

# Test risoluzione dall'interno della VM
# nslookup server.database.windows.net 168.63.129.16
```

---

### Scenario 3 — CDN Endpoint restituisce contenuto non aggiornato (cache stale)

**Sintomo:** Dopo aver aggiornato file nello storage/origin, l'endpoint CDN continua a servire la versione precedente.

**Causa:** Il contenuto è ancora in cache nei PoP CDN con TTL non scaduto. Il `Cache-Control` dell'origin non è configurato correttamente.

**Soluzione:** Eseguire purge manuale o configurare TTL appropriato.

```bash
# Purge di file specifici
az cdn endpoint purge \
    --resource-group myapp-rg \
    --profile-name myapp-cdn \
    --name myapp-content \
    --content-paths "/assets/app.js" "/assets/style.css"

# Purge completo
az cdn endpoint purge \
    --resource-group myapp-rg \
    --profile-name myapp-cdn \
    --name myapp-content \
    --content-paths "/*"

# Verificare stato endpoint e regole caching
az cdn endpoint show \
    --resource-group myapp-rg \
    --profile-name myapp-cdn \
    --name myapp-content \
    --query "{origin: origins, queryStringCaching: queryStringCachingBehavior}"
```

---

### Scenario 4 — DNS Private Resolver non esegue forwarding verso on-premises

**Sintomo:** Le query per domini interni (es. `corp.internal`) non vengono inoltrate al DNS on-premises; la risoluzione fallisce o restituisce NXDOMAIN.

**Causa:** Il Forwarding Ruleset non è collegato alla VNet, oppure la Forwarding Rule per il dominio target è disabilitata o non esiste.

**Soluzione:**

```bash
# Verificare le forwarding rules nel ruleset
az dns-resolver forwarding-rule list \
    --resource-group myapp-rg \
    --forwarding-ruleset-name company-ruleset \
    --output table

# Verificare che il ruleset sia associato alla VNet
az dns-resolver vnet-link list \
    --resource-group myapp-rg \
    --forwarding-ruleset-name company-ruleset \
    --output table

# Abilitare una rule disabilitata
az dns-resolver forwarding-rule update \
    --resource-group myapp-rg \
    --forwarding-ruleset-name company-ruleset \
    --forwarding-rule-name forward-to-onprem \
    --forwarding-rule-state Enabled

# Verificare connettività verso il DNS on-premises (porta 53)
# Test dall'outbound subnet: nc -zv 192.168.1.53 53
```

---

## Riferimenti

- [Azure DNS Documentation](https://learn.microsoft.com/azure/dns/)
- [Azure Private DNS](https://learn.microsoft.com/azure/dns/private-dns-overview)
- [DNS Private Resolver](https://learn.microsoft.com/azure/dns/dns-private-resolver-overview)
- [Azure CDN Documentation](https://learn.microsoft.com/azure/cdn/)
- [Azure DDoS Protection](https://learn.microsoft.com/azure/ddos-protection/)
