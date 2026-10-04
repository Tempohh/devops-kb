---
title: "Azure Load Balancing"
slug: load-balancing
category: cloud
tags: [azure, load-balancer, application-gateway, front-door, traffic-manager, waf]
search_keywords: [Azure Load Balancer, ALB Azure, Application Gateway, AGW, WAF Web Application Firewall, Azure Front Door, AFD, Traffic Manager, Layer 4 load balancing, Layer 7 load balancing, global load balancing, URL based routing, SSL termination, health probe, backend pool, Azure CDN, SKU Standard Basic, Application Gateway for Containers, DRS, Default Rule Set]
parent: cloud/azure/networking/_index
related: [cloud/azure/networking/vnet, cloud/azure/networking/dns-cdn, cloud/azure/compute/virtual-machines]
official_docs: https://learn.microsoft.com/azure/load-balancer/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Load Balancing

## Panoramica

Azure non ha un unico load balancer: ne ha quattro, che lavorano a livelli diversi dello stack e si **combinano** (es. Front Door davanti a più Application Gateway regionali, ciascuno davanti a un pool di VM). La scelta si fa su due domande: il traffico è HTTP(S) o generico TCP/UDP? Serve bilanciare dentro una region o tra region?

- **Load Balancer** (L4): inoltra pacchetti TCP/UDP senza ispezionarli, latenza minima, nessun WAF. Adatto a traffico non-HTTP (database, protocolli custom) e a tier interni.
- **Application Gateway** (L7 regionale): termina TLS e legge URL/header, quindi può instradare per path/host e applicare un WAF.
- **Front Door** (L7 globale): punto d'ingresso Anycast sui POP Microsoft; accelera, cachea e fa failover tra region.
- **Traffic Manager** (DNS): non vede il traffico, risponde solo alle query DNS con l'endpoint migliore; funziona anche per endpoint non-HTTP o fuori Azure, ma il failover dipende dal TTL e dalla cache dei client.

!!! note "Servizi correlati"
    Per Kubernetes esiste **Application Gateway for Containers** (evoluzione di AGIC, supporta Gateway API) e per appliance di rete **Gateway Load Balancer**; non trattati qui.

| Servizio | Layer | Scope | Use Case |
|----------|-------|-------|----------|
| **Azure Load Balancer** | 4 (TCP/UDP) | Regionale | VM, VMSS — traffico interno e esterno |
| **Application Gateway** | 7 (HTTP/HTTPS) | Regionale | Web app, API con WAF |
| **Azure Front Door** | 7 (HTTP/HTTPS) | Globale | App globali, CDN, WAF globale |
| **Traffic Manager** | DNS | Globale | Routing DNS tra region/endpoint |

!!! warning "Dismissioni da conoscere (stato 2026)"
    - **Basic Load Balancer** e Basic Public IP: ritirati il 30/09/2025 — usare solo SKU **Standard**.
    - **Application Gateway v1**: ritirato il 28/04/2026 — usare solo SKU v2 (`Standard_v2`/`WAF_v2`).
    - **Front Door (classic)**: ritiro previsto il 31/03/2027 — migrare a Standard/Premium.
    - Standard LB/Public IP sono *secure by default*: il traffico in ingresso è bloccato finché un NSG non lo consente.

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
    --zone 1 2 3 \
    --query id -o tsv)
# --zone 1 2 3 = IP zone-redundant

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
# Attenzione: esporre SSH/RDP su IP pubblico è sconsigliato — preferire Azure Bastion
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
    --private-ip-address 10.1.2.100 \
    --frontend-ip-name FrontendIP \
    --backend-pool-name BackendPool
# --private-ip-address = IP privato fisso del frontend
```

!!! note "Outbound"
    Dal 30/09/2025 le nuove VNet non hanno più *default outbound access*: per l'uscita verso Internet usare **NAT Gateway** (consigliato) o outbound rules del Standard LB.

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
    --sku WAF_v2 \
    --capacity 2 \
    --vnet-name production-vnet \
    --subnet AppGwSubnet \
    --public-ip-address appgw-pip \
    --http-settings-cookie-based-affinity Disabled \
    --http-settings-port 80 \
    --http-settings-protocol Http \
    --frontend-port 80 \
    --routing-rule-type Basic \
    --priority 100
# --sku: Standard_v2 (senza WAF) o WAF_v2; --capacity: istanze fisse (in alternativa autoscaling con --min-capacity/--max-capacity)

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
# Richiede una managed identity user-assigned associata al gateway, con permesso di lettura dei secret su Key Vault

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
# Nota: la regola creata sopra è Basic; per usare la path map serve una rule di tipo PathBasedRouting
az network application-gateway url-path-map create \
    --resource-group myapp-rg \
    --gateway-name production-appgw \
    --name url-routing \
    --paths "/api/*" \
    --address-pool api-backend \
    --http-settings api-settings \
    --default-address-pool web-backend \
    --default-http-settings web-settings

# WAF Policy (modello attuale; waf-config set è la configurazione legacy)
az network application-gateway waf-policy create \
    --resource-group myapp-rg \
    --name myapp-waf-policy

# Modalità: Detection (solo log) o Prevention (blocca)
az network application-gateway waf-policy policy-setting update \
    --resource-group myapp-rg \
    --policy-name myapp-waf-policy \
    --state Enabled \
    --mode Prevention

# Rule set gestito: Default Rule Set 2.1 (successore di OWASP CRS 3.2)
az network application-gateway waf-policy managed-rule rule-set add \
    --resource-group myapp-rg \
    --policy-name myapp-waf-policy \
    --type Microsoft_DefaultRuleSet \
    --version 2.1

# Associare la policy al gateway
az network application-gateway update \
    --resource-group myapp-rg \
    --name production-appgw \
    --set firewallPolicy.id=$(az network application-gateway waf-policy show -g myapp-rg -n myapp-waf-policy --query id -o tsv)
```

!!! tip "Perché la WAF Policy"
    La policy è una risorsa separata dal gateway: si riusa su più gateway/listener, permette regole per-listener o per-path e supporta bot protection e rate limiting. La vecchia `waf-config` è per-gateway e non ha queste funzioni.

---

## Azure Front Door

**Azure Front Door** è il load balancer globale L7 — distribuisce traffico tra region Azure, con CDN e WAF globale:

```bash
# Creare Front Door profile
az afd profile create \
    --resource-group myapp-rg \
    --profile-name myapp-afd \
    --sku Premium_AzureFrontDoor
# Standard_AzureFrontDoor: WAF solo con custom rules; Premium_AzureFrontDoor: managed rule set + bot protection + Private Link verso le origin

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
    --origin-host-header "myapp-westeurope.azurewebsites.net" \
    --http-port 80 \
    --https-port 443 \
    --priority 2 \
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
# priority 2 sull'origin west-europe = failover: usato solo se italy-north è unhealthy
```

Perché si usano le probe con `sample-size`/`successful-samples-required`: un'origin è *healthy* se almeno `successful-samples-required` delle ultime `sample-size` probe sono riuscite. Valori più alti di `successful-samples-required` → l'origin viene dichiarata unhealthy **prima** (più sensibile, più falsi positivi).

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
    --routing-method Performance \
    --unique-dns-name myapp-global \
    --monitor-protocol HTTPS \
    --monitor-port 443 \
    --monitor-path /health \
    --ttl 30
# --routing-method alternative: Priority, Weighted, Geographic, Multivalue, Subnet
# --unique-dns-name myapp-global → myapp-global.trafficmanager.net

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
| WAF | No | Sì (WAF_v2) | Sì (Standard: custom rules; Premium: managed rules) | No |
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

**Causa:** La health probe non riceve risposta HTTP 200 dal path configurato, oppure il NSG blocca le sonde. Le probe del Load Balancer partono dall'IP `168.63.129.16` (tag `AzureLoadBalancer`); quelle di Application Gateway v2 partono invece dagli IP della **subnet del gateway** (il NSG del backend deve consentire quella subnet, e il NSG della subnet gateway deve consentire `GatewayManager` su 65200-65535).

**Soluzione:** Verificare che il NSG consenta la sorgente corretta per il servizio in uso e che l'endpoint di health risponda correttamente.

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

**Causa:** Il `probe-interval-in-seconds` è troppo lungo, oppure `successful-samples-required` è troppo basso rispetto a `sample-size` (es. 1 su 4: basta una probe riuscita per restare healthy) — Front Door non dichiara unhealthy l'origin primario. Altre cause: il path `/health` risponde 200 anche con backend degradato, oppure le probe sono disabilitate (con una sola origin nel gruppo Front Door non esegue probe).

**Soluzione:** Ridurre l'intervallo delle probe e alzare `successful-samples-required` (es. 3 su 4) per rilevare prima il guasto; far sì che `/health` verifichi le dipendenze reali. Verificare anche che l'origin secondario risponda alle probe.

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
    --successful-samples-required 3

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

## Best Practices

- **Scegli per layer e scope**: L4 → Load Balancer; HTTP regionale → Application Gateway; HTTP multi-region → Front Door; DNS/non-HTTP multi-region → Traffic Manager.
- **Sempre SKU Standard/v2** e IP zone-redundant: sopravvive al guasto di una Availability Zone e non dipende dalle SKU ritirate.
- **Health endpoint significativo**: `/health` deve verificare le dipendenze critiche e rispondere 200 solo se il nodo può servire traffico; no redirect 301/302.
- **Subnet dedicata** per Application Gateway, con NSG che consenta `GatewayManager` (65200-65535) e il traffico client.
- **WAF in Detection → Prevention**: partire in Detection per individuare falsi positivi, poi passare a Prevention con esclusioni mirate.
- **Front Door + Application Gateway/origin privati**: limitare l'accesso alle origin al solo Front Door (header `X-Azure-FDID`, service tag `AzureFrontDoor.Backend` o Private Link con Premium).
- **TTL basso** su Traffic Manager (10-30 s) se il failover è un requisito, sapendo che alcuni resolver non rispettano il TTL.

---

## Relazioni

??? info "VNet — Approfondimento"
    Load Balancer interno e Application Gateway vivono in subnet della VNet; NSG e NAT Gateway ne regolano ingresso e uscita.

    **Approfondimento completo →** [VNet](vnet.md)

??? info "DNS e CDN — Approfondimento"
    Traffic Manager è un servizio DNS; Front Door integra il CDN e usa domini custom con record CNAME/alias.

    **Approfondimento completo →** [DNS e CDN](dns-cdn.md)

---

## Riferimenti

- [Azure Load Balancer](https://learn.microsoft.com/azure/load-balancer/)
- [Application Gateway](https://learn.microsoft.com/azure/application-gateway/)
- [Azure Front Door](https://learn.microsoft.com/azure/frontdoor/)
- [Traffic Manager](https://learn.microsoft.com/azure/traffic-manager/)
