---
title: "VPC — Virtual Private Cloud"
slug: vpc
category: cloud
tags: [aws, vpc, subnets, routing, internet-gateway, nat-gateway, security-groups, nacl, elastic-ip, vpc-endpoints]
search_keywords: [AWS VPC, Virtual Private Cloud, subnet, public subnet, private subnet, CIDR, route table, Internet Gateway, NAT Gateway, Elastic IP, security group, NACL, network ACL, VPC endpoint, Gateway endpoint, Interface endpoint, VPC flow logs, default VPC, DHCP options, network fundamentals AWS]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/vpc-avanzato, cloud/aws/security/network-security, cloud/aws/compute/ec2]
official_docs: https://docs.aws.amazon.com/vpc/latest/userguide/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# VPC — Virtual Private Cloud

Un **VPC** è una rete virtuale privata isolata logicamente nel cloud AWS. È il fondamento di ogni architettura — ogni risorsa AWS (EC2, RDS, ECS...) vive dentro un VPC.

```
VPC Architecture — Esempio Multi-AZ

Region: eu-central-1 (Francoforte)
VPC: 10.0.0.0/16
│
├── AZ-A (eu-central-1a)
│   ├── Public Subnet:  10.0.0.0/24   ← Internet Gateway route
│   │   └── EC2, NAT Gateway, ALB nodes
│   └── Private Subnet: 10.0.1.0/24  ← No direct Internet
│       └── EC2, RDS, ECS tasks
│
├── AZ-B (eu-central-1b)
│   ├── Public Subnet:  10.0.2.0/24
│   └── Private Subnet: 10.0.3.0/24
│
└── AZ-C (eu-central-1c)
    ├── Public Subnet:  10.0.4.0/24
    └── Private Subnet: 10.0.5.0/24

Internet Gateway (1 per VPC, regionale)
NAT Gateway (1+ per AZ, in subnet pubblica)
```

---

## Progettare un VPC — CIDR Planning

**CIDR block** del VPC: da `/16` (65.536 IP) a `/28` (16 IP)

**Regole:**
- Non sovrapporre CIDR tra VPC che si devono connettere (peering, TGW)
- AWS riserva **5 IP per subnet** (first 4 + last 1)
  - `.0` — Network address
  - `.1` — VPC router
  - `.2` — AWS DNS
  - `.3` — Riservato AWS
  - `.255` — Broadcast (non usato, ma riservato)
- Esempio: `/24` = 256 IP totali - 5 = **251 disponibili**

**Schema CIDR consigliato per produzione:**
```
VPC:            10.0.0.0/16      (65.536 IP)
├── Public-AZ-A:  10.0.0.0/24   (251 IP)
├── Public-AZ-B:  10.0.1.0/24   (251 IP)
├── Public-AZ-C:  10.0.2.0/24   (251 IP)
├── Private-AZ-A: 10.0.10.0/24  (251 IP)
├── Private-AZ-B: 10.0.11.0/24  (251 IP)
├── Private-AZ-C: 10.0.12.0/24  (251 IP)
├── DB-AZ-A:      10.0.20.0/24  (251 IP)
├── DB-AZ-B:      10.0.21.0/24  (251 IP)
└── DB-AZ-C:      10.0.22.0/24  (251 IP)
```

---

## Creare un VPC con AWS CLI

```bash
# 1. Creare VPC
VPC_ID=$(aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=prod-vpc}]' \
    --query 'Vpc.VpcId' \
    --output text)
echo "VPC: $VPC_ID"

# Abilitare DNS hostnames (necessario per alcuni servizi)
aws ec2 modify-vpc-attribute \
    --vpc-id $VPC_ID \
    --enable-dns-hostnames

# 2. Creare Internet Gateway e allegarlo al VPC
IGW_ID=$(aws ec2 create-internet-gateway \
    --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=prod-igw}]' \
    --query 'InternetGateway.InternetGatewayId' \
    --output text)

aws ec2 attach-internet-gateway \
    --vpc-id $VPC_ID \
    --internet-gateway-id $IGW_ID

# 3. Creare subnet pubblica in AZ-A
PUBLIC_SUBNET_A=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.0.0/24 \
    --availability-zone eu-central-1a \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-a}]' \
    --query 'Subnet.SubnetId' \
    --output text)

# Auto-assign public IP alle istanze lanciate in questa subnet
aws ec2 modify-subnet-attribute \
    --subnet-id $PUBLIC_SUBNET_A \
    --map-public-ip-on-launch

# 4. Creare subnet privata in AZ-A
PRIVATE_SUBNET_A=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.10.0/24 \
    --availability-zone eu-central-1a \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=private-a}]' \
    --query 'Subnet.SubnetId' \
    --output text)

# 5. Creare Route Table pubblica
PUBLIC_RT=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=public-rt}]' \
    --query 'RouteTable.RouteTableId' \
    --output text)

# Aggiungere route verso Internet (default route → IGW)
aws ec2 create-route \
    --route-table-id $PUBLIC_RT \
    --destination-cidr-block 0.0.0.0/0 \
    --gateway-id $IGW_ID

# Associare subnet pubblica alla RT pubblica
aws ec2 associate-route-table \
    --route-table-id $PUBLIC_RT \
    --subnet-id $PUBLIC_SUBNET_A

# 6. Creare NAT Gateway (in subnet pubblica)
# Prima: allocare un Elastic IP
EIP=$(aws ec2 allocate-address \
    --domain vpc \
    --query 'AllocationId' \
    --output text)

NAT_GW=$(aws ec2 create-nat-gateway \
    --subnet-id $PUBLIC_SUBNET_A \
    --allocation-id $EIP \
    --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=nat-a}]' \
    --query 'NatGateway.NatGatewayId' \
    --output text)

# Attendere che NAT Gateway sia available
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_GW

# 7. Creare Route Table privata (→ NAT GW)
PRIVATE_RT=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=private-rt}]' \
    --query 'RouteTable.RouteTableId' \
    --output text)

aws ec2 create-route \
    --route-table-id $PRIVATE_RT \
    --destination-cidr-block 0.0.0.0/0 \
    --nat-gateway-id $NAT_GW

aws ec2 associate-route-table \
    --route-table-id $PRIVATE_RT \
    --subnet-id $PRIVATE_SUBNET_A
```

---

## Internet Gateway (IGW)

- **1 IGW per VPC** — scalabile orizzontalmente, non è un single point of failure
- Si allega al VPC (non alla subnet)
- Una subnet è "pubblica" se la sua route table ha `0.0.0.0/0 → IGW`
- Le istanze in subnet pubblica devono avere un **public IP** o **Elastic IP**
- **NAT non è richiesto** — l'IGW esegue NAT 1:1 tra Public IP e Private IP

---

## NAT Gateway

Il **NAT Gateway** permette alle istanze in subnet private di accedere a Internet (outbound only) senza essere raggiungibili dall'esterno.

**Caratteristiche:**
- Managed da AWS — no patching, alta disponibilità nell'AZ
- Deve risiedere in una **subnet pubblica**
- Richiede un **Elastic IP** associato
- Bandwidth: da 5 Gbps fino a 100 Gbps (scaling automatico)
- **Non supporta** IPv6 (per IPv6 usare Egress-only IGW)
- **Costo:** $0.045/hr + $0.045/GB processato → significativo per alti volumi

!!! warning "NAT Gateway per AZ"
    Per alta disponibilità, creare **un NAT Gateway per AZ** e configurare route table private separate per AZ. Un singolo NAT GW è SPOF per le subnet private delle altre AZ.

```bash
# Costo NAT Gateway (approssimativo)
# $0.045/hr × 24 × 30 = ~$32/mese + data processing
# Per workload con molto traffico outbound → considerare NAT Instance (EC2) come alternativa più economica
```

---

## Elastic IP (EIP)

Un **Elastic IP** è un indirizzo IPv4 pubblico statico allocato al tuo account.

```bash
# Allocare EIP
EIP_ID=$(aws ec2 allocate-address \
    --domain vpc \
    --query 'AllocationId' \
    --output text)

# Associare EIP a una EC2 instance
aws ec2 associate-address \
    --instance-id i-1234567890abcdef0 \
    --allocation-id $EIP_ID

# Disassociare
aws ec2 disassociate-address --association-id eipassoc-xxxxx

# Rilasciare (attenzione: l'IP potrebbe essere assegnato ad altri)
aws ec2 release-address --allocation-id $EIP_ID
```

**Note:**
- **Gratuito** se associato a un'istanza running
- **$0.005/hr** se non associato (AWS disincentiva EIP "parcheggiati")
- Rimane nel tuo account fino a rilascio esplicito

---

## Security Groups

I **Security Groups** sono firewall **stateful** a livello di istanza/interfaccia.

**Caratteristiche:**
- **Stateful**: se un pacchetto è permesso in ingresso, la risposta è automaticamente permessa in uscita
- Solo regole `Allow` — le regole `Deny` non esistono (il non-match è automaticamente deny)
- Applicati a: EC2, RDS, ELB, Lambda in VPC, ECS tasks, ecc.
- Un'istanza può avere più SG (fino a 5 per interfaccia)
- Le regole referenziano IP/CIDR o altri Security Group ID

```bash
# Creare Security Group
SG_WEB=$(aws ec2 create-security-group \
    --group-name web-sg \
    --description "Web servers - HTTP/HTTPS" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text)

# Regola inbound: HTTP da Internet
aws ec2 authorize-security-group-ingress \
    --group-id $SG_WEB \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0

# Regola inbound: HTTPS da Internet
aws ec2 authorize-security-group-ingress \
    --group-id $SG_WEB \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0

# Creare SG per Application server
SG_APP=$(aws ec2 create-security-group \
    --group-name app-sg \
    --description "App servers - dal web tier" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text)

# Regola inbound: solo dal Web SG (reference a SG, non IP)
aws ec2 authorize-security-group-ingress \
    --group-id $SG_APP \
    --protocol tcp \
    --port 8080 \
    --source-group $SG_WEB

# SG per RDS: solo dall'App SG
SG_DB=$(aws ec2 create-security-group \
    --group-name db-sg \
    --description "RDS - dal app tier" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text)

aws ec2 authorize-security-group-ingress \
    --group-id $SG_DB \
    --protocol tcp \
    --port 5432 \
    --source-group $SG_APP
```

**Pattern 3-tier con Security Group:**
```
Internet
   ↓
ALB (SG: 443 from 0.0.0.0/0)
   ↓
App EC2 (SG: 8080 from ALB-SG)
   ↓
RDS (SG: 5432 from App-SG)
```

---

## Network ACLs (NACLs)

Le **NACL** sono firewall **stateless** a livello di subnet.

| Caratteristica | Security Group | NACL |
|---------------|---------------|------|
| Livello | Istanza/ENI | Subnet |
| Stato | Stateful | Stateless |
| Regole | Solo Allow | Allow + Deny |
| Valutazione | Tutte le regole | In ordine numerico (prima match) |
| Applicazione | Istanze specifiche | Tutte le istanze nella subnet |

```bash
# NACLs — esempio di configurazione
# Ogni regola ha: numero (ordine), protocollo, porta, CIDR, Allow/Deny

# NACL pubblica (esempio):
# Inbound:
# 100: Allow TCP 80 from 0.0.0.0/0
# 110: Allow TCP 443 from 0.0.0.0/0
# 120: Allow TCP 1024-65535 from 0.0.0.0/0  (ephemeral ports per responses!)
# *:   Deny All

# Outbound:
# 100: Allow TCP 80 to 0.0.0.0/0
# 110: Allow TCP 443 to 0.0.0.0/0
# 120: Allow TCP 1024-65535 to 0.0.0.0/0    (ephemeral ports)
# *:   Deny All

aws ec2 create-network-acl-entry \
    --network-acl-id acl-xxxx \
    --rule-number 100 \
    --protocol 6 \     # 6=TCP
    --port-range From=80,To=80 \
    --cidr-block 0.0.0.0/0 \
    --ingress \
    --rule-action allow
```

!!! warning "NACL stateless — ephemeral ports"
    Poiché la NACL è stateless, devi esplicitamente permettere le **porte efimere** (1024-65535) in entrambe le direzioni, altrimenti le risposte TCP vengono bloccate.

---

## VPC Endpoints

I **VPC Endpoints** permettono di accedere a servizi AWS dalla subnet privata **senza passare per Internet** — più sicuro e più economico (nessun costo NAT Gateway/Internet).

**Tipi:**

| Tipo | Come funziona | Servizi |
|------|-------------|---------|
| **Gateway Endpoint** | Route nella route table | S3, DynamoDB |
| **Interface Endpoint** | ENI nella subnet (PrivateLink) | Tutti gli altri (100+) |

```bash
# Gateway Endpoint per S3 (gratuito)
aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --service-name com.amazonaws.eu-central-1.s3 \
    --vpc-endpoint-type Gateway \
    --route-table-ids $PRIVATE_RT

# Interface Endpoint per Secrets Manager
aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --service-name com.amazonaws.eu-central-1.secretsmanager \
    --vpc-endpoint-type Interface \
    --subnet-ids $PRIVATE_SUBNET_A \
    --security-group-ids $SG_ENDPOINT \
    --private-dns-enabled    # usa il DNS standard (*.secretsmanager.eu-central-1.amazonaws.com)
```

---

## VPC Flow Logs

I **VPC Flow Logs** registrano il traffico IP che attraversa le interfacce di rete del VPC.

```bash
# Abilitare Flow Logs su VPC (verso CloudWatch Logs)
aws ec2 create-flow-logs \
    --resource-type VPC \
    --resource-ids $VPC_ID \
    --traffic-type ALL \           # ALL | ACCEPT | REJECT
    --log-destination-type cloud-watch-logs \
    --log-group-name /aws/vpc/flowlogs \
    --deliver-logs-permission-arn arn:aws:iam::123456789012:role/VPCFlowLogsRole

# Verso S3 (più economico per retention lunga)
aws ec2 create-flow-logs \
    --resource-type VPC \
    --resource-ids $VPC_ID \
    --traffic-type REJECT \        # Solo REJECT per analisi security
    --log-destination-type s3 \
    --log-destination arn:aws:s3:::my-flowlogs-bucket \
    --log-format '${version} ${account-id} ${interface-id} ${srcaddr} ${dstaddr} ${srcport} ${dstport} ${protocol} ${packets} ${bytes} ${start} ${end} ${action} ${log-status}'
```

**Analisi con Athena:**
```sql
-- Query top talkers (Security Investigation)
SELECT srcaddr, dstaddr, SUM(bytes) AS total_bytes
FROM vpc_flow_logs
WHERE action = 'REJECT'
  AND start BETWEEN 1700000000 AND 1700100000
GROUP BY srcaddr, dstaddr
ORDER BY total_bytes DESC
LIMIT 20;
```

---

## Riferimenti

- [VPC User Guide](https://docs.aws.amazon.com/vpc/latest/userguide/)
- [VPC Endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints.html)
- [VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)
- [Security Groups vs NACLs](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Security.html)
