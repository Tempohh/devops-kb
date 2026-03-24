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
last_updated: 2026-03-09
---

# VPC — Virtual Private Cloud

Un **VPC** (Virtual Private Cloud) è una rete virtuale privata, isolata logicamente all'interno del cloud AWS. È il fondamento di ogni architettura: ogni risorsa computazionale (EC2, RDS, ECS, Lambda in VPC...) vive all'interno di un VPC.

Pensalo come il tuo datacenter virtuale nel cloud: puoi definire il range di indirizzi IP, suddividerli in subnet, controllare il routing del traffico e configurare firewall a più livelli. AWS crea un **Default VPC** pre-configurato in ogni Region per permetterti di iniziare subito, ma per ambienti di produzione è sempre consigliabile creare un VPC custom con una progettazione deliberata della rete.

Un VPC è **regionale** — copre tutte le Availability Zone di una Region. Le **subnet** che crei al suo interno sono invece **AZ-specifiche**: ogni subnet risiede in una singola AZ. Distribuire le risorse su subnet in AZ diverse è la base dell'alta disponibilità in AWS.

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

Prima di creare qualsiasi risorsa, è fondamentale pianificare con attenzione il **CIDR block** (Classless Inter-Domain Routing — notazione `IP/prefisso` per definire blocchi di indirizzi, es. `10.0.0.0/16`) del VPC. Una volta creato, il CIDR principale non può essere ridotto e aggiungere CIDR secondari ha limitazioni. La regola più importante: **non sovrapporre mai i CIDR** tra VPC che potrebbero dover comunicare in futuro tramite VPC Peering o Transit Gateway.

Il VPC può avere un CIDR da `/16` (65.536 IP) fino a `/28` (16 IP). Per produzione, `/16` è la scelta standard: offre spazio sufficiente per molte subnet senza essere sprecone.

**Regole:**
- Non sovrapporre CIDR tra VPC che si devono connettere (peering, TGW — Transit Gateway)
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

L'**Internet Gateway** è il componente che connette il VPC a Internet. È il confine tra la tua rete privata nel cloud e Internet pubblico. Senza IGW, nessuna risorsa nel VPC può comunicare con l'esterno.

Come funziona: l'IGW si allega al VPC (non a una subnet specifica). Una subnet diventa "pubblica" quando la sua route table ha una route `0.0.0.0/0 → IGW`, che instradia il traffico verso Internet attraverso il gateway. Le istanze in subnet pubblica devono anche avere un **Public IP** o un **Elastic IP** — senza di esso non sono raggiungibili dall'esterno, anche se la subnet è pubblica.

Caratteristiche:
- **1 IGW per VPC** — è un componente regionale scalabile orizzontalmente da AWS, non è un single point of failure
- L'IGW esegue **NAT 1:1** tra il Public IP dell'istanza e il suo Private IP, trasparentemente
- Non è necessario fare NAT manuale: l'IGW gestisce la traduzione automaticamente

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
    Per alta disponibilità, creare **un NAT Gateway per AZ** e configurare route table private separate per AZ. Un singolo NAT GW è SPOF (Single Point of Failure) per le subnet private delle altre AZ.

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

I **Security Groups** sono firewall **stateful** applicati a livello di singola risorsa (istanza EC2, database RDS, load balancer...). Sono il meccanismo di sicurezza di rete più usato in AWS e il punto di controllo principale per la maggior parte delle architetture.

**Stateful** significa che il Security Group traccia le connessioni: se permetti traffico in ingresso su una porta, la risposta di ritorno è automaticamente permessa, senza dover configurare regole di outbound esplicite per le risposte. Questo semplifica notevolmente la gestione rispetto ai firewall stateless.

**Caratteristiche:**
- **Solo regole Allow** — le regole `Deny` non esistono nei Security Group. Il traffico che non corrisponde a nessuna regola Allow viene automaticamente bloccato (deny implicito).
- Si applicano a: EC2, RDS, ALB/NLB, Lambda in VPC, ECS tasks, ElastiCache, e altri
- Un'istanza può avere più Security Group associati (fino a 5 per interfaccia), e i loro permessi si sommano
- Le regole possono referenziare IP/CIDR oppure **altri Security Group ID** — questa è la caratteristica più potente: permette di dire "accetta traffico solo da risorse che hanno il Security Group X associato", senza dover conoscere i loro IP

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

Le **Network ACL** sono firewall **stateless** applicati a livello di subnet. A differenza dei Security Group, le NACL sono associate a una subnet intera e filtrano il traffico che entra ed esce da essa, indipendentemente dalla risorsa di destinazione.

**Stateless** significa che le NACL non tracciano le connessioni: ogni pacchetto viene valutato indipendentemente. Questo implica che devi configurare regole esplicite sia per il traffico in ingresso che per le risposte in uscita (porte efimere).

Nella maggior parte delle architetture i **Security Group** sono sufficienti. Le NACL sono uno strato di difesa aggiuntivo utile quando vuoi bloccare traffico a livello di intera subnet (es. bloccare un range IP sospetto per tutta una subnet), oppure quando hai requisiti di compliance che richiedono un firewall stateless esplicito.

| Caratteristica | Security Group | NACL |
|---------------|---------------|------|
| Livello | Istanza/ENI | Subnet |
| Stato | Stateful | Stateless |
| Regole | Solo Allow | Allow + Deny |
| Valutazione | Tutte le regole | In ordine numerico (prima match che corrisponde) |
| Applicazione | Risorse specifiche | Tutte le risorse nella subnet |
| Quando usarla | Default per la maggior parte dei casi | Difesa in profondità, blocchi IP-level su subnet |

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

I **VPC Endpoints** permettono alle risorse in subnet private di accedere a servizi AWS **senza passare per Internet**. Senza VPC Endpoints, una Lambda in VPC privato che vuole leggere da S3 dovrebbe uscire su Internet tramite NAT Gateway — con costi di data transfer e un percorso che attraversa la rete pubblica. Con un VPC Endpoint, il traffico rimane sulla rete privata AWS e non passa per il NAT Gateway, riducendo sia i costi che la superficie di attacco.

**Tipi:**

| Tipo | Come funziona | Servizi | Costo |
|------|-------------|---------|-------|
| **Gateway Endpoint** | Aggiunge una route nella route table | Solo S3 e DynamoDB | Gratuito |
| **Interface Endpoint** | Crea una ENI (Elastic Network Interface) nella subnet, accessibile tramite DNS privato (PrivateLink) | Tutti gli altri servizi AWS (100+) | ~$0.01/ora + data processing |

La scelta è semplice: per S3 e DynamoDB usa sempre il Gateway Endpoint (gratuito, nessuna complessità aggiuntiva). Per altri servizi, valuta l'Interface Endpoint quando le risorse in VPC privato devono accedervi frequentemente e vuoi evitare sia i costi del NAT che l'esposizione a Internet.

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

I **VPC Flow Logs** registrano metadati sul traffico IP che attraversa le interfacce di rete del VPC. Non catturano il contenuto dei pacchetti (payload), ma registrano informazioni come IP sorgente/destinazione, porte, protocollo, quantità di byte e se il traffico è stato permesso o rifiutato.

Sono uno strumento essenziale per due scopi principali: **sicurezza** (investigare accessi anomali, trovare quale IP sta tentando connessioni non autorizzate, verificare che le regole dei Security Group funzionino come previsto) e **troubleshooting di rete** (capire perché una connessione viene bloccata).

I log possono essere inviati a CloudWatch Logs (per query in tempo quasi reale con Log Insights) o a S3 (più economico per retention lunga, analizzabile con Athena).

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
