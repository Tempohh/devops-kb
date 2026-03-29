---
title: "Azure Load Balancing"
slug: load-balancing-azure
category: cloud
tags: [azure, load-balancer, application-gateway, front-door, traffic-manager, waf]
search_keywords: [Azure Load Balancer, ALB Azure, Application Gateway, WAF Web Application Firewall, Azure Front Door, Traffic Manager, Layer 4 load balancing, Layer 7 load balancing, global load balancing, URL based routing, SSL termination, health probe, backend pool, Azure CDN, SKU Standard Basic]
parent: cloud/azure/networking/_index
related: [cloud/azure/networking/vnet, cloud/azure/networking/dns-cdn, cloud/azure/compute/virtual-machines]
official_docs: https://learn.microsoft.com/azure/load-balancer/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Azure Load Balancing

Azure offre quattro servizi di load balancing complementari per scenari diversi:

| Servizio | Layer | Scope | Use Case |
|----------|-------|-------|----------|
| **Azure Load Balancer** | 4 (TCP/UDP) | Regionale | VM, VMSS — traffico interno e esterno |
| **Application Gateway** | 7 (HTTP/HTTPS) | Regionale | Web app, API con WAF |
| **Azure Front Door** | 7 (HTTP/HTTPS) | Globale | App globali, CDN, WAF globale |
| **Traffic Manager** | DNS | Globale | Routing DNS tra region/endpoint |

---

## Azure Load Balancer

**Load Balancer** standard opera al Layer 4 — distribuisce traffico TCP/UDP tra VM/VMSS.

```bash
# Creare Public IP Standard
PIP_ID=$(az network public-ip create \
    --resource-group myapp-rg \
    --name myapp-pip \
    --sku Standard \
    --allocation-method Static \
    --zone 1 2 3 \                  # Zone-redundant
    --query id -o tsv)

# Creare Load Balancer Standard
LB_ID=$(az network lb create \
    --resource-group myapp-rg \
    --name myapp-lb \
    --sku Standard \
    --public-ip-address myapp-pip \
    --frontend-ip-name FrontendIP \
    --backend-pool-name BackendPool \
    --query loadBalancer.id -o tsv)

# Creare Health Probe
az network lb probe create \
    --resource-group myapp-rg \
    --lb-name myapp-lb \
    --name healthprobe \
    --protocol Http \
    --port 80 \
    --path /health \
    --interval 15 \
    --threshold 2

# Creare Load Balancing Rule
az network lb rule create \
    --resource-group myapp-rg \
    --lb-name myapp-lb \
    --name http-rule \
    --protocol Tcp \
    --frontend-port 80 \
    --backend-port 80 \
    --frontend-ip-name FrontendIP \
    --backend-pool-name BackendPool \
    --probe-name healthprobe \
    --idle-timeout 4 \
    --enable-tcp-reset true \
    --disable-outbound-snat false

# Creare NAT Rule (accesso diretto a VM specifica)
az network lb inbound-nat-rule create \
    --resource-group myapp-rg \
    --lb-name myapp-lb \
    --name ssh-vm1 \
    --protocol Tcp \
    --frontend-port 2222 \
    --backend-port 22 \
    --frontend-ip-name FrontendIP

# Aggiungere VM al Backend Pool (tramite NIC)
az network nic ip-config address-pool add \
    --resource-group myapp-rg \
    --nic-name myvm1-nic \
    --ip-config-name ipconfig1 \
    --lb-name myapp-lb \
    --address-pool BackendPool
```

**Internal Load Balancer (ILB)** — per traffico privato tra tier:

```bash
az network lb create \
    --resource-group myapp-rg \
    --name internal-lb \
    --sku Standard \
    --vnet-name production-vnet \
    --subnet app-subnet \
    --private-ip-address 10.1.2.100 \   # IP privato fisso
    --frontend-ip-name FrontendIP \
    --backend-pool-name BackendPool
```

---

## Application Gateway

**Application Gateway** è il reverse proxy L7 di Azure con WAF, SSL termination e URL routing:

```bash
# Creare subnet dedicata per Application Gateway (non condividere con altre risorse)
az network vnet subnet create \
    --resource-group myapp-rg \
    --vnet-name production-vnet \
    --name AppGwSubnet \
    --address-prefix 10.1.10.0/24

# Public IP per Application Gateway
az network public-ip create \
    --resource-group myapp-rg \
    --name appgw-pip \
    --sku Standard \
    --zone 1 2 3

# Creare Application Gateway v2 con WAF
az network application-gateway create \
    --resource-group myapp-rg \
    --name production-appgw \
    --location italynorth \
    --sku WAF_v2 \                      # Standard_v2 (no WAF) o WAF_v2
    --capacity 2 \                      # istanze fisse o auto-scale
    --vnet-name production-vnet \
    --subnet AppGwSubnet \
    --public-ip-address appgw-pip \
    --http-settings-cookie-based-affinity Disabled \
    --http-settings-port 80 \
    --http-settings-protocol Http \
    --frontend-port 80 \
    --routing-rule-type Basic \
    --priority 100

# Aggiungere backend pool (VM o VMSS o FQDN)
az network application-gateway address-pool update \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --name appGatewayBackendPool \
    --servers 10.1.2.10 10.1.2.11 10.1.2.12

# Aggiungere HTTPS listener con certificato
az network application-gateway ssl-cert create \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --name myapp-cert \
    --key-vault-secret-id "https://myvault.vault.azure.net/secrets/myapp-tls"

az network application-gateway frontend-port create \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --name port443 \
    --port 443

az network application-gateway http-listener create \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --name https-listener \
    --frontend-port port443 \
    --ssl-cert myapp-cert \
    --host-name "myapp.company.com"

# Path-based routing (URL routing)
az network application-gateway url-path-map create \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --name url-routing \
    --paths "/api/*" \
    --address-pool api-backend \
    --http-settings api-settings \
    --default-address-pool web-backend \
    --default-http-settings web-settings

# Abilitare WAF Policy
az network application-gateway waf-policy create \
    --resource-group myapp-rg \
    --name myapp-waf-policy \
    --type OWASP \
    --version 3.2

az network application-gateway waf-config set \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --enabled true \
    --firewall-mode Prevention \         # Detection (log only) o Prevention (block)
    --rule-set-type OWASP \
    --rule-set-version 3.2
```

---

## Azure Front Door

**Azure Front Door** è il load balancer globale L7 — distribuisce traffico tra region Azure, con CDN e WAF globale:

```bash
# Creare Front Door profile
az afd profile create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --sku Premium_AzureFrontDoor       # Standard_AzureFrontDoor o Premium_AzureFrontDoor (WAF avanzato)

# Creare endpoint
az afd endpoint create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --endpoint-name myapp \
    --enabled-state Enabled

# Creare origin group (backend pool multi-region)
az afd origin-group create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --origin-group-name production-origins \
    --probe-request-type GET \
    --probe-protocol Https \
    --probe-interval-in-seconds 30 \
    --probe-path /health \
    --sample-size 4 \
    --successful-samples-required 3 \
    --additional-latency-in-milliseconds 50

# Aggiungere origini (regioni diverse)
az afd origin create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --origin-group-name production-origins \
    --origin-name italy-north \
    --host-name "myapp-italynorth.azurewebsites.net" \
    --http-port 80 \
    --https-port 443 \
    --origin-host-header "myapp-italynorth.azurewebsites.net" \
    --priority 1 \
    --weight 100 \
    --enabled-state Enabled

az afd origin create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --origin-group-name production-origins \
    --origin-name west-europe \
    --host-name "myapp-westeurope.azurewebsites.net" \
    --priority 2 \                     # failover — usato solo se italy-north non disponibile
    --weight 100 \
    --enabled-state Enabled

# Creare route
az afd route create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --endpoint-name myapp \
    --route-name default-route \
    --origin-group production-origins \
    --supported-protocols Https \
    --https-redirect Enabled \
    --forwarding-protocol HttpsOnly \
    --patterns-to-match "/*"
```

---

## Traffic Manager

**Traffic Manager** è un load balancer DNS globale — indirizza gli utenti all'endpoint migliore basandosi su profili di routing:

| Metodo di routing | Descrizione |
|-------------------|-------------|
| **Performance** | Endpoint con latenza più bassa per l'utente |
| **Priority** | Failover — endpoint primario con fallback |
| **Weighted** | Distribuzione percentuale (blue/green deploy) |
| **Geographic** | Utenti EU → EU endpoint, US → US endpoint |
| **Multivalue** | Ritorna tutti gli endpoint healthy (per DNS resiliente) |
| **Subnet** | Routing basato su IP range del client |

```bash
# Creare Traffic Manager profile
az network traffic-manager profile create \
    --resource-group myapp-rg \
    --name myapp-tm \
    --routing-method Performance \      # o Priority, Weighted, Geographic
    --unique-dns-name myapp-global \    # myapp-global.trafficmanager.net
    --monitor-protocol HTTPS \
    --monitor-port 443 \
    --monitor-path /health \
    --ttl 30

# Aggiungere endpoint (Azure App Service)
az network traffic-manager endpoint create \
    --resource-group myapp-rg \
    --profile-name myapp-tm \
    --name endpoint-eu \
    --type azureEndpoints \
    --target-resource-id /subscriptions/$SUB_ID/.../sites/myapp-italynorth \
    --endpoint-status Enabled

az network traffic-manager endpoint create \
    --resource-group myapp-rg \
    --profile-name myapp-tm \
    --name endpoint-us \
    --type azureEndpoints \
    --target-resource-id /subscriptions/$SUB_ID/.../sites/myapp-eastus \
    --endpoint-status Enabled
```

---

## Confronto Load Balancing

| Caratteristica | Load Balancer | Application Gateway | Front Door | Traffic Manager |
|----------------|---------------|---------------------|------------|-----------------|
| Layer | 4 (TCP/UDP) | 7 (HTTP) | 7 (HTTP) | DNS |
| Scope | Regionale | Regionale | Globale | Globale |
| WAF | No | Sì (v2) | Sì (Premium) | No |
| SSL Termination | No | Sì | Sì | No |
| URL Routing | No | Sì | Sì | No |
| CDN | No | No | Sì | No |
| Caching | No | No | Sì | No |
| IP Statico | Sì | Sì | No (Anycast) | No (DNS) |
| Internal | Sì | Sì | No | No |

---

## Troubleshooting

### Scenario 1 — Health probe fallisce, backend pool vuoto

**Sintomo:** Il Load Balancer o Application Gateway mostra tutti i backend come "unhealthy"; il traffico non viene instradato.

**Causa:** La health probe non riceve risposta HTTP 200 dal path configurato, oppure il NSG blocca le sonde (Azure Load Balancer usa IP `168.63.129.16`).

**Soluzione:** Verificare che il NSG consenta il traffico dal tag `AzureLoadBalancer` e che l'endpoint di health risponda correttamente.

```bash
# Verificare lo stato dei backend nel Load Balancer
az network lb show \
    --resource-group myapp-rg \
    --name myapp-lb \
    --query "backendAddressPools[].backendIPConfigurations[].id" -o tsv

# Controllare le health probe dell'Application Gateway
az network application-gateway show-backend-health \
    --resource-group myapp-rg \
    --name production-appgw \
    --query "backendAddressPools[].backendHttpSettingsCollection[].servers[]" -o table

# Assicurarsi che il NSG abbia la regola per le probe
az network nsg rule create \
    --resource-group myapp-rg \
    --nsg-name myvm-nsg \
    --name AllowAzureLoadBalancer \
    --priority 100 \
    --source-address-prefixes AzureLoadBalancer \
    --destination-port-ranges 80 443 \
    --access Allow \
    --protocol Tcp
```

---

### Scenario 2 — Application Gateway restituisce 502 Bad Gateway

**Sintomo:** I client ricevono errore `502 Bad Gateway` dall'Application Gateway.

**Causa:** Il backend non risponde sulla porta/protocollo configurato nelle HTTP Settings, oppure il certificato backend non è trusted dall'Application Gateway (in modalità HTTPS end-to-end).

**Soluzione:** Verificare le HTTP Settings e, per HTTPS backend, aggiungere il certificato root del backend come "trusted root certificate".

```bash
# Controllare i log di diagnostica dell'Application Gateway
az monitor diagnostic-settings list \
    --resource-group myapp-rg \
    --resource production-appgw \
    --resource-type "Microsoft.Network/applicationGateways"

# Abilitare i log se non attivi
az monitor diagnostic-settings create \
    --resource-group myapp-rg \
    --resource production-appgw \
    --resource-type "Microsoft.Network/applicationGateways" \
    --name appgw-diag \
    --workspace /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.OperationalInsights/workspaces/myapp-law \
    --logs '[{"category":"ApplicationGatewayAccessLog","enabled":true},{"category":"ApplicationGatewayFirewallLog","enabled":true}]'

# Query Log Analytics per errori 502
az monitor log-analytics query \
    --workspace /subscriptions/$SUB_ID/resourceGroups/myapp-rg/providers/Microsoft.OperationalInsights/workspaces/myapp-law \
    --analytics-query 'AzureDiagnostics | where ResourceType == "APPLICATIONGATEWAYS" | where httpStatus_d == 502 | take 20'
```

---

### Scenario 3 — Front Door non fa failover sull'origin di backup

**Sintomo:** Quando l'origin primario è down, Front Door non reindirizza il traffico all'origin secondario; i client ricevono errori.

**Causa:** Il `successful-samples-required` è impostato troppo alto, oppure il `probe-interval-in-seconds` è troppo lungo — Front Door non ha ancora dichiarato unhealthy l'origin primario.

**Soluzione:** Abbassare la soglia di failure detection o aumentare la frequenza delle probe. Verificare anche che l'origin secondario risponda alle probe.

```bash
# Controllare lo stato attuale delle origini
az afd origin list \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --origin-group-name production-origins \
    --query "[].{name:name,enabled:enabledState,priority:priority,weight:weight}" -o table

# Aggiornare l'origin group per rilevamento più rapido
az afd origin-group update \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --origin-group-name production-origins \
    --probe-interval-in-seconds 10 \
    --sample-size 4 \
    --successful-samples-required 2

# Forzare disable di un'origin per test failover
az afd origin update \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --origin-group-name production-origins \
    --origin-name italy-north \
    --enabled-state Disabled
```

---

### Scenario 4 — Traffic Manager continua a risolvere verso endpoint unhealthy

**Sintomo:** Il DNS di Traffic Manager continua a puntare a un endpoint non disponibile; alcuni utenti ricevono errori nonostante il failover configurato.

**Causa:** Il TTL DNS è troppo alto (client cacheano la risposta), oppure il monitor di Traffic Manager non ha ancora rilevato il down perché `--ttl` e gli intervalli di probe non sono allineati.

**Soluzione:** Ridurre il TTL per failover più rapido e verificare che il path `/health` risponda correttamente (non redirect 301/302, che Traffic Manager non segue per default).

```bash
# Verificare lo stato degli endpoint
az network traffic-manager endpoint show \
    --resource-group myapp-rg \
    --profile-name myapp-tm \
    --name endpoint-eu \
    --type azureEndpoints \
    --query "{status:endpointStatus,monitorStatus:endpointMonitorStatus}" -o table

# Ridurre TTL e intervallo di monitoring
az network traffic-manager profile update \
    --resource-group myapp-rg \
    --name myapp-tm \
    --ttl 10 \
    --monitor-interval 10 \
    --monitor-timeout 5 \
    --monitor-tolerated-failures 2

# Disabilitare manualmente un endpoint per test
az network traffic-manager endpoint update \
    --resource-group myapp-rg \
    --profile-name myapp-tm \
    --name endpoint-eu \
    --type azureEndpoints \
    --endpoint-status Disabled

# Verificare la risoluzione DNS corrente
nslookup myapp-global.trafficmanager.net
dig myapp-global.trafficmanager.net
```

---

## Riferimenti

- [Azure Load Balancer](https://learn.microsoft.com/azure/load-balancer/)
- [Application Gateway](https://learn.microsoft.com/azure/application-gateway/)
- [Azure Front Door](https://learn.microsoft.com/azure/frontdoor/)
- [Traffic Manager](https://learn.microsoft.com/azure/traffic-manager/)
