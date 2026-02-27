---
title: "VPC Avanzato — Connectivity"
slug: vpc-avanzato
category: cloud
tags: [aws, vpc, vpc-peering, transit-gateway, privatelink, vpn, direct-connect, client-vpn, hybrid-cloud, network-architecture]
search_keywords: [VPC Peering, Transit Gateway, AWS PrivateLink, Site-to-Site VPN, Direct Connect, Client VPN, hub-and-spoke, hybrid connectivity, cross-account networking, AWS backbone, BGP, Virtual Private Gateway, Customer Gateway, DX Gateway, AWS Network Firewall, Gateway Load Balancer, VPN CloudHub]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/vpc, cloud/aws/networking/route53, cloud/aws/security/network-security]
official_docs: https://docs.aws.amazon.com/vpc/latest/peering/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# VPC Avanzato — Connectivity

## VPC Peering

Il **VPC Peering** crea una connessione privata tra due VPC — stesso account, account diversi, o Region diverse.

```
VPC-A (10.0.0.0/16) ←──── Peering ────→ VPC-B (10.1.0.0/16)
```

**Caratteristiche:**
- Traffic transita sulla rete backbone AWS (privato, non su Internet)
- Nessun Gateway, VPN o connessione fisica necessaria
- Routing deve essere configurato manualmente in entrambe le route tables
- **Non transitivo**: A↔B e B↔C non implica A↔C (serve peering diretto A↔C)
- CIDR non devono sovrapporsi tra VPC peerati

```bash
# Creare VPC Peering
PEERING_ID=$(aws ec2 create-vpc-peering-connection \
    --vpc-id vpc-AAAA \
    --peer-vpc-id vpc-BBBB \
    --peer-owner-id 999999999999 \    # Account ID se cross-account
    --peer-region eu-west-1 \         # Omettere se stessa Region
    --query 'VpcPeeringConnection.VpcPeeringConnectionId' \
    --output text)

# Accettare la richiesta (da Account B se cross-account)
aws ec2 accept-vpc-peering-connection \
    --vpc-peering-connection-id $PEERING_ID \
    --region eu-west-1

# Aggiungere route in VPC-A verso VPC-B via peering
aws ec2 create-route \
    --route-table-id rtb-AAAA \
    --destination-cidr-block 10.1.0.0/16 \
    --vpc-peering-connection-id $PEERING_ID

# E viceversa in VPC-B
aws ec2 create-route \
    --route-table-id rtb-BBBB \
    --destination-cidr-block 10.0.0.0/16 \
    --vpc-peering-connection-id $PEERING_ID
```

**Limitazioni:**
- Non transitivo (A→B→C non funziona)
- Non supporta Edge-to-Edge routing (on-premises VPN di VPC-A non raggiunge VPC-B via peering)
- Per molti VPC → usare **Transit Gateway**

---

## Transit Gateway (TGW)

Il **Transit Gateway** è un hub di rete regionale che connette VPC, VPN e Direct Connect in un'unica topologia hub-and-spoke.

```
                    ┌──────────────────┐
VPC-A ─────────────→│                  │←─── VPC-B
                    │  Transit Gateway  │
VPC-C ─────────────→│   (Regional Hub) │←─── On-premises (VPN)
                    │                  │←─── Direct Connect
VPC-D ─────────────→│                  │←─── VPC in altra Region (peering TGW)
                    └──────────────────┘
```

**Vantaggi vs VPC Peering:**
- Scalabile: supporta fino a 5.000 attachment (VPC + VPN + DX)
- Transitivo: VPC-A può raggiungere VPC-B e VPC-C tramite TGW
- Route centrali: una singola route table TGW gestisce il routing
- Inter-Region: TGW Peering tra Region diverse

```bash
# Creare Transit Gateway
TGW_ID=$(aws ec2 create-transit-gateway \
    --description "Main TGW" \
    --options '{
        "AmazonSideAsn": 64512,
        "AutoAcceptSharedAttachments": "disable",
        "DefaultRouteTableAssociation": "enable",
        "DefaultRouteTablePropagation": "enable",
        "VpnEcmpSupport": "enable",
        "DnsSupport": "enable",
        "MulticastSupport": "disable"
    }' \
    --query 'TransitGateway.TransitGatewayId' \
    --output text)

# Aggiungere VPC attachment
aws ec2 create-transit-gateway-vpc-attachment \
    --transit-gateway-id $TGW_ID \
    --vpc-id vpc-AAAA \
    --subnet-ids subnet-xxx subnet-yyy \    # subnet in AZ diverse
    --options "ApplianceModeSupport=disable,DnsSupport=enable,Ipv6Support=disable"

# Condividere TGW con altri account via Resource Access Manager
aws ram create-resource-share \
    --name "TGW-Share" \
    --resource-arns arn:aws:ec2:eu-central-1:123456789012:transit-gateway/$TGW_ID \
    --principals 999999999999    # Account B

# Route nelle VPC: aggiungere rotta verso TGW
aws ec2 create-route \
    --route-table-id rtb-AAAA \
    --destination-cidr-block 10.0.0.0/8 \   # Supernet di tutti i VPC
    --transit-gateway-id $TGW_ID
```

**TGW Route Tables:**
```bash
# Isolare VPC (segmentazione): creare RT separate
# VPC prod → RT-prod (vede solo VPC prod)
# VPC dev  → RT-dev  (vede VPC dev + Internet)
aws ec2 create-transit-gateway-route-table \
    --transit-gateway-id $TGW_ID \
    --tag-specifications 'ResourceType=transit-gateway-route-table,Tags=[{Key=Name,Value=RT-Prod}]'
```

**Costi TGW:**
- $0.05/hr per TGW attachment
- $0.02/GB dati processati
- Per 10 VPC: $0.05 × 10 × 24 × 30 = ~$360/mese (solo attachment)

---

## AWS PrivateLink

**PrivateLink** permette di esporre un servizio (tuo o di un vendor) in modo privato tramite **Interface Endpoint**, senza passare per Internet.

```
Consumer VPC                        Provider VPC
─────────────                       ────────────
Interface Endpoint ←─ PrivateLink ─→ NLB → Servizio
(ENI privata nella subnet)
```

**Use case:**
- Accedere a servizi AWS (Secrets Manager, ECR, SSM...) da subnet private
- Acquistare servizi SaaS esposti su AWS Marketplace via PrivateLink
- Esporre microservizi interni ad altri team/account senza VPC peering

```bash
# Lato Provider: creare Endpoint Service (dietro a NLB)
aws ec2 create-vpc-endpoint-service-configuration \
    --network-load-balancer-arns arn:aws:elasticloadbalancing:... \
    --acceptance-required \       # accettazione manuale richiesta
    --private-dns-name "api.company.internal"

# Lato Consumer: creare Interface Endpoint
aws ec2 create-vpc-endpoint \
    --vpc-id vpc-CONSUMER \
    --service-name com.amazonaws.vpce.eu-central-1.vpce-svc-xxxxx \
    --vpc-endpoint-type Interface \
    --subnet-ids subnet-private-a subnet-private-b \
    --security-group-ids sg-endpoint \
    --private-dns-enabled
```

---

## Site-to-Site VPN

Il **Site-to-Site VPN** connette la rete on-premises al VPC via Internet con tunnel IPSec cifrati.

```
On-premises                                    AWS
──────────────                                 ──────────────────
Customer Gateway ←── IPSec Tunnel ──→ Virtual Private Gateway
(Router/Firewall)    (2 tunnel per      (allegato al VPC)
                      HA)
```

```bash
# 1. Creare Customer Gateway (rappresenta il tuo router on-premises)
CGW_ID=$(aws ec2 create-customer-gateway \
    --type ipsec.1 \
    --public-ip 203.0.113.1 \        # IP pubblico del tuo router
    --bgp-asn 65000 \                 # tuo ASN (o 65000 se static routing)
    --query 'CustomerGateway.CustomerGatewayId' \
    --output text)

# 2. Creare Virtual Private Gateway e allegarlo al VPC
VGW_ID=$(aws ec2 create-vpn-gateway \
    --type ipsec.1 \
    --amazon-side-asn 64512 \
    --query 'VpnGateway.VpnGatewayId' \
    --output text)

aws ec2 attach-vpn-gateway \
    --vpn-gateway-id $VGW_ID \
    --vpc-id $VPC_ID

# 3. Creare VPN Connection (genera 2 tunnel IPSec per HA)
aws ec2 create-vpn-connection \
    --type ipsec.1 \
    --customer-gateway-id $CGW_ID \
    --vpn-gateway-id $VGW_ID \
    --options '{"StaticRoutesOnly": false}' \   # false = BGP
    --query 'VpnConnection.VpnConnectionId' \
    --output text

# 4. Scaricare configurazione per il tuo router
aws ec2 describe-vpn-connections \
    --vpn-connection-ids vpn-xxxx \
    --query 'VpnConnections[0].CustomerGatewayConfiguration'
# Output XML con config per Cisco/Juniper/Palo Alto/pfSense...

# 5. Abilitare route propagation nella route table VPC
aws ec2 enable-vgw-route-propagation \
    --route-table-id $PRIVATE_RT \
    --gateway-id $VGW_ID
```

**Caratteristiche:**
- 2 tunnel IPSec per HA (diversi IP AWS endpoint)
- Throughput: fino a 1.25 Gbps per tunnel
- Supporta BGP (dynamic routing) o static routing
- Costo: $0.05/hr per connessione VPN

**VPN CloudHub:** molteplici Customer Gateway collegati allo stesso VGW → comunicano tra loro (hub-and-spoke per multi-sede).

---

## AWS Direct Connect (DX)

**Direct Connect** è una connessione fisica dedicata tra la tua rete e AWS, tramite un **DX Location** (datacenter neutro con AWS).

```
On-premises ── fibra dedicata ── DX Location ── AWS Network ── Region/VPC
                                 (Colocation)
```

**Tipi di connessione:**

| Tipo | Bandwidth | Descrizione |
|------|-----------|-------------|
| **Dedicated** | 1/10/100 Gbps | Connessione fisica dedicata, vai al DX Location |
| **Hosted** | 50 Mbps - 10 Gbps | Partner gestisce la connessione fisica |

**Virtual Interfaces (VIF):**
- **Private VIF** → accesso a VPC specifico via VGW
- **Public VIF** → accesso a tutti i servizi AWS pubblici (S3, DynamoDB...) bypassando Internet
- **Transit VIF** → accesso a TGW (per molti VPC)

```bash
# Direct Connect si gestisce prevalentemente via Console
# Processo:
# 1. Richiedere DX connection (o tramite partner)
# 2. Ricevere Letter of Authorization (LOA-CFA)
# 3. Presentare LOA al DX Location per cross-connect fisico
# 4. Creare Virtual Interface (VIF) sul DX
# 5. Configurare BGP sul proprio router con ASN AWS

# Creare Private VIF via CLI
aws directconnect create-private-virtual-interface \
    --connection-id dxcon-xxxx \
    --new-private-virtual-interface '{
        "virtualInterfaceName": "my-private-vif",
        "vlan": 101,
        "asn": 65000,
        "mtu": 1500,
        "authKey": "bgp-auth-key",
        "amazonAddress": "175.45.176.1/30",
        "customerAddress": "175.45.176.2/30",
        "virtualGatewayId": "vgw-xxxx"
    }'
```

**Direct Connect Gateway:**
Connette un singolo DX a molteplici VPC (anche in Region diverse).

```
On-premises ── DX ── DX Gateway ── VGW ── VPC-A (eu-central-1)
                                 ── VGW ── VPC-B (eu-west-1)
                                 ── TGW ── VPC-C, VPC-D...
```

**DX vs VPN:**

| Caratteristica | Direct Connect | Site-to-Site VPN |
|----------------|---------------|------------------|
| Connessione | Dedicata (fibra) | Via Internet |
| Latency | Bassa, prevedibile | Variabile |
| Bandwidth | 1-100 Gbps | ≤1.25 Gbps/tunnel |
| Ridondanza | Necessita 2 connessioni | 2 tunnel inclusi |
| Setup time | Settimane/mesi | Ore |
| Costo | $$$ (porta + dati) | $ |
| Cifratura | No (opzionale MACsec) | Sì (IPSec) |

**Best practice:** DX per traffico primario + VPN come failover.

---

## Client VPN

**AWS Client VPN** è un servizio VPN gestito per accesso individuale (developer → VPC).

```bash
# Creare Client VPN Endpoint
aws ec2 create-client-vpn-endpoint \
    --client-cidr-block 10.100.0.0/22 \      # IP assegnati ai client
    --server-certificate-arn arn:aws:acm:... \
    --authentication-options Type=certificate-authentication,\
        MutualAuthentication={ClientRootCertificateChainArn=arn:aws:acm:...} \
    --connection-log-options Enabled=true,CloudwatchLogGroup=/aws/clientvpn \
    --split-tunnel true \                     # Solo traffico VPC via tunnel
    --vpc-id $VPC_ID

# Associare subnet (endpoint disponibile nell'AZ)
aws ec2 associate-client-vpn-target-network \
    --client-vpn-endpoint-id cvpn-endpoint-xxxx \
    --subnet-id $PRIVATE_SUBNET_A

# Aggiungere authorization rule
aws ec2 authorize-client-vpn-ingress \
    --client-vpn-endpoint-id cvpn-endpoint-xxxx \
    --target-network-cidr 10.0.0.0/16 \
    --authorize-all-groups
```

**Costo:** $0.10/hr per endpoint + $0.05/hr per connessione attiva.

---

## Riferimenti

- [VPC Peering](https://docs.aws.amazon.com/vpc/latest/peering/)
- [Transit Gateway](https://docs.aws.amazon.com/vpc/latest/tgw/)
- [AWS PrivateLink](https://docs.aws.amazon.com/vpc/latest/privatelink/)
- [Site-to-Site VPN](https://docs.aws.amazon.com/vpn/latest/s2svpn/)
- [Direct Connect](https://docs.aws.amazon.com/directconnect/latest/UserGuide/)
