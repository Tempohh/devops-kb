---
title: "IPv6 e Dual-Stack su AWS"
slug: ipv6-dual-stack
category: cloud
tags: [aws, ipv6, dual-stack, vpc, egress-only-igw, nat64, dns64, eks, public-ipv4-cost]
search_keywords: [IPv6, dual-stack, dualstack, IPv6-only, EIGW, Egress-only Internet Gateway, NAT64, DNS64, 64:ff9b::/96, AAAA record, public IPv4 charge, IPv4 exhaustion, BYOIP, IPAM, Public IPv4 Insights, VPC CIDR IPv6, Happy Eyeballs, EKS IPv6, VPC CNI prefix delegation, ip-address-type dualstack, PreferDualStack, GUA, ULA, Nitro, migrazione IPv6, costo IPv4 pubblico]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/vpc, cloud/aws/networking/vpc-avanzato, cloud/aws/networking/route53, cloud/aws/networking/elastic-load-balancing, cloud/aws/networking/cloudfront, cloud/aws/containers/eks, networking/fondamentali/indirizzi-ip-subnetting]
official_docs: https://docs.aws.amazon.com/vpc/latest/userguide/vpc-migrate-ipv6.html
status: draft
difficulty: advanced
last_updated: 2026-09-26
---

# IPv6 e Dual-Stack su AWS

## Panoramica

IPv6 su AWS è ormai una funzionalità matura: VPC, EC2, ELB, CloudFront, Route 53, EKS e la maggior parte dei servizi gestiti supportano indirizzi IPv6, in modalità **dual-stack** (IPv4 + IPv6 insieme) e, per le subnet, anche **IPv6-only**. La motivazione principale per migrare oggi non è solo tecnica ma **economica**: dal **1 febbraio 2024** AWS addebita **0,005 USD/h (~3,65 USD/mese)** per ogni indirizzo IPv4 pubblico, in uso o meno (Elastic IP inclusi). Un cluster con decine di nodi/LB pubblici accumula rapidamente costi evitabili.

Le altre motivazioni: esaurimento dello spazio RFC1918 (CIDR sovrapposti tra VPC/account, vincolo per peering e Transit Gateway), eliminazione di NAT Gateway per il traffico verso Internet (costo orario + per GB), e semplificazione del routing dei Pod in EKS (nessun overlay, nessuna esaustione di IP).

**Quando NON usarlo:** carichi che dipendono da servizi/SaaS solo-IPv4 senza NAT64, appliance di terze parti o middlebox senza supporto IPv6, ambienti on-premises con firewall/VPN che non gestiscono IPv6. In questi casi restare dual-stack e migrare gradualmente.

## Concetti Chiave

!!! note "Modello di indirizzamento IPv6 in VPC"
    - Il VPC riceve un blocco **/56** (Amazon-provided, da pool AWS) oppure un blocco **BYOIP** (Bring Your Own IP) o allocato da **VPC IPAM**.
    - Ogni subnet riceve un **/64** (fisso, non modificabile).
    - Gli indirizzi sono **GUA (Global Unicast Address)** e quindi **globalmente instradabili**: **non esiste NAT IPv6** "classico". Ciò che rende una subnet "privata" è solo la **route table** + i **security group**.
    - Non c'è il concetto di "IP pubblico vs privato" per IPv6: un'istanza è raggiungibile da Internet solo se la subnet ha route `::/0` verso un **IGW** e l'SG lo consente.

| Componente | Ruolo IPv6 |
|---|---|
| **Internet Gateway (IGW)** | Traffico bidirezionale; route `::/0 → igw-xxx` (subnet "pubblica") |
| **Egress-only Internet Gateway (EIGW)** | Solo uscita, connessioni in ingresso bloccate; route `::/0 → eigw-xxx` (equivalente "privato" del NAT GW) |
| **Security Group** | Regole IPv4 e IPv6 **separate** (`0.0.0.0/0` non copre `::/0`) |
| **NACL** | Regole IPv4 e IPv6 separate, stateless; serve una regola `::/0` esplicita |
| **NAT Gateway (NAT64)** | Traduce IPv6 → IPv4 per raggiungere host solo-IPv4 da subnet IPv6-only |
| **DNS64** | Feature di Route 53 Resolver per subnet: sintetizza record AAAA `64:ff9b::/96` per nomi con solo record A |
| **VPC IPAM** | Pianificazione/allocazione CIDR + **Public IP Insights** per individuare IPv4 pubblici e relativi costi |

### Tipi di subnet

| Tipo | Indirizzi | Note |
|---|---|---|
| **IPv4-only** | Solo IPv4 | Default storico |
| **Dual-stack** | IPv4 + IPv6 | Scelta consigliata per la migrazione |
| **IPv6-only** | Solo IPv6 | Solo istanze **Nitro**; usa NAT64/DNS64 per IPv4; nessun costo IPv4 |

!!! warning "IPv6-only: limiti"
    Nelle subnet IPv6-only, le ENI non hanno IPv4: servizi che richiedono IPv4 (es. alcuni agent, `169.254.169.254` IMDS senza endpoint IPv6 abilitato, repository solo-IPv4) richiedono NAT64/DNS64 o endpoint dual-stack. Verificare il supporto IPv6 di ogni componente prima di scegliere IPv6-only.

## Architettura / Come Funziona

```
                        Internet (IPv4 + IPv6)
                               │
                        ┌──────┴───────┐
                        │     IGW      │   ::/0 e 0.0.0.0/0
                        └──────┬───────┘
     ┌─────────────────────────┼──────────────────────────┐
     │ VPC  10.0.0.0/16  +  2600:1f18:xxxx:xx00::/56      │
     │                                                    │
     │  Subnet pubblica (dual-stack)                      │
     │   10.0.1.0/24 + 2600:...:0100::/64                 │
     │   ALB dualstack, NAT GW (per NAT64/IPv4 egress)    │
     │                                                    │
     │  Subnet privata (dual-stack)                       │
     │   ::/0  → eigw-xxx   (solo uscita IPv6)            │
     │   0.0.0.0/0 → nat-xxx (uscita IPv4)                │
     │                                                    │
     │  Subnet IPv6-only                                  │
     │   ::/0 → eigw-xxx                                  │
     │   64:ff9b::/96 → nat-xxx   (NAT64)                 │
     │   DNS64 abilitato sulla subnet                     │
     └────────────────────────────────────────────────────┘
```

### Flusso NAT64 / DNS64

1. Un'istanza IPv6-only risolve `api.legacy.example.com`, che ha solo record `A`.
2. Il **Route 53 Resolver** (con DNS64 abilitato sulla subnet) restituisce un AAAA sintetico `64:ff9b::<IPv4 in esadecimale>`.
3. L'istanza invia il pacchetto; la route `64:ff9b::/96` punta al **NAT Gateway** (in subnet con IPv4), che traduce verso IPv4 e ritorna le risposte.

### Happy Eyeballs

I client moderni implementano **Happy Eyeballs (RFC 8305)**: tentano IPv6 e IPv4 quasi in parallelo, preferendo quello che risponde per primo (IPv6 con un piccolo vantaggio). Se IPv6 è rotto (SG/NACL/route mancanti), il fallback IPv4 maschera il problema con **latenza extra** (tipicamente 100–300 ms) invece di un errore: vanno testati esplicitamente i percorsi IPv6.

## Configurazione & Pratica

### 1. VPC: associare CIDR IPv6 e creare subnet

```bash
# Associare un /56 Amazon-provided al VPC esistente
aws ec2 associate-vpc-cidr-block \
    --vpc-id vpc-0abc123 \
    --amazon-provided-ipv6-cidr-block

# Leggere il /56 assegnato
aws ec2 describe-vpcs --vpc-ids vpc-0abc123 \
    --query 'Vpcs[0].Ipv6CidrBlockAssociationSet[].Ipv6CidrBlock' --output text

# Associare un /64 a una subnet esistente (dual-stack)
aws ec2 associate-subnet-cidr-block \
    --subnet-id subnet-0aaa111 \
    --ipv6-cidr-block 2600:1f18:1234:5600::/64

# Creare una subnet IPv6-only con DNS64 e assegnazione automatica IPv6
aws ec2 create-subnet \
    --vpc-id vpc-0abc123 \
    --availability-zone eu-west-1a \
    --ipv6-native \
    --ipv6-cidr-block 2600:1f18:1234:5601::/64

aws ec2 modify-subnet-attribute --subnet-id subnet-0bbb222 --enable-dns64
aws ec2 modify-subnet-attribute --subnet-id subnet-0bbb222 --assign-ipv6-address-on-creation
```

### 2. Routing: IGW ed Egress-only IGW

```bash
# Subnet pubblica: ::/0 verso IGW esistente
aws ec2 create-route \
    --route-table-id rtb-public \
    --destination-ipv6-cidr-block ::/0 \
    --gateway-id igw-0abc123

# Subnet privata: creare EIGW e instradare ::/0 (solo uscita)
EIGW_ID=$(aws ec2 create-egress-only-internet-gateway \
    --vpc-id vpc-0abc123 \
    --query 'EgressOnlyInternetGateway.EgressOnlyInternetGatewayId' --output text)

aws ec2 create-route \
    --route-table-id rtb-private \
    --destination-ipv6-cidr-block ::/0 \
    --egress-only-internet-gateway-id $EIGW_ID

# NAT64 per subnet IPv6-only: prefisso well-known verso NAT Gateway
aws ec2 create-route \
    --route-table-id rtb-ipv6only \
    --destination-ipv6-cidr-block 64:ff9b::/96 \
    --nat-gateway-id nat-0abc123
```

### 3. Security group e NACL

```bash
# SG: le regole IPv4 NON coprono IPv6 → aggiungere ::/0 esplicitamente
aws ec2 authorize-security-group-ingress \
    --group-id sg-0abc123 \
    --ip-permissions 'IpProtocol=tcp,FromPort=443,ToPort=443,Ipv6Ranges=[{CidrIpv6=::/0,Description="HTTPS IPv6"}]'

# NACL (stateless): servono regole in ingresso E ephemeral ports in uscita
aws ec2 create-network-acl-entry \
    --network-acl-id acl-0abc123 --rule-number 111 --protocol tcp \
    --port-range From=443,To=443 --ipv6-cidr-block ::/0 --rule-action allow --ingress
aws ec2 create-network-acl-entry \
    --network-acl-id acl-0abc123 --rule-number 111 --protocol tcp \
    --port-range From=1024,To=65535 --ipv6-cidr-block ::/0 --rule-action allow --egress
```

### 4. Terraform equivalente

```hcl
resource "aws_vpc" "main" {
  cidr_block                       = "10.0.0.0/16"
  assign_generated_ipv6_cidr_block = true # /56 Amazon-provided
}

resource "aws_subnet" "private" {
  vpc_id                          = aws_vpc.main.id
  cidr_block                      = "10.0.2.0/24"
  ipv6_cidr_block                 = cidrsubnet(aws_vpc.main.ipv6_cidr_block, 8, 2) # /64
  assign_ipv6_address_on_creation = true
}

resource "aws_egress_only_internet_gateway" "eigw" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route" "private_v6" {
  route_table_id              = aws_route_table.private.id
  destination_ipv6_cidr_block = "::/0"
  egress_only_gateway_id      = aws_egress_only_internet_gateway.eigw.id
}
```

### 5. Load balancer, Route 53, CloudFront

```bash
# ALB dual-stack (o "dualstack-without-public-ipv4" per evitare IPv4 pubblici sul LB)
aws elbv2 set-ip-address-type \
    --load-balancer-arn arn:aws:elasticloadbalancing:eu-west-1:111122223333:loadbalancer/app/web/abc \
    --ip-address-type dualstack

# Target group: IP type separato (non modificabile dopo la creazione)
aws elbv2 create-target-group --name web-v6 --protocol HTTP --port 80 \
    --vpc-id vpc-0abc123 --ip-address-type ipv6 --target-type ip

# Route 53: alias AAAA verso il LB (affiancare sempre il record A)
aws route53 change-resource-record-sets --hosted-zone-id Z123 --change-batch '{
  "Changes":[{"Action":"UPSERT","ResourceRecordSet":{
    "Name":"www.example.com","Type":"AAAA",
    "AliasTarget":{"HostedZoneId":"Z32O12XQLNTSW2","DNSName":"dualstack.web-123.eu-west-1.elb.amazonaws.com","EvaluateTargetHealth":true}}}]}'

# CloudFront: abilitare IPv6 sulla distribuzione e creare alias AAAA
aws cloudfront get-distribution-config --id E123ABC --query 'DistributionConfig.IsIPV6Enabled'
```

!!! tip "Alias A + AAAA"
    Per ogni nome pubblico con IPv6 creare **entrambi** i record alias (`A` e `AAAA`) verso lo stesso target. Un AAAA senza un target realmente raggiungibile via IPv6 causa errori intermittenti per i client IPv6.

### 6. EKS con IPv6

```bash
# ip-family è IMMUTABILE: va scelto alla creazione del cluster
eksctl create cluster -f - <<'EOF'
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata: { name: demo-v6, region: eu-west-1, version: "1.33" }
kubernetesNetworkConfig:
  ipFamily: IPv6
addons:
  - { name: vpc-cni }
  - { name: coredns }
  - { name: kube-proxy }
managedNodeGroups:
  - { name: ng, instanceType: m6i.large, desiredCapacity: 2 }  # solo Nitro
EOF

# Equivalente con AWS CLI
aws eks create-cluster --name demo-v6 --role-arn $ROLE_ARN \
    --resources-vpc-config subnetIds=subnet-a,subnet-b \
    --kubernetes-network-config ipFamily=ipv6
```

Punti chiave EKS IPv6:

- **Pod IPv6 non-NAT'd**: ogni Pod riceve un IPv6 dal prefisso `/80` assegnato all'ENI del nodo (**prefix delegation**), niente esaurimento IP e niente limiti ENI/IP per nodo tipici di IPv4.
- **Solo istanze Nitro**; VPC CNI ≥ 1.10.1, AWS Load Balancer Controller ≥ 2.3.
- Il traffico Pod → IPv4 esterno esce via **egress IPv4 del nodo** (NAT locale del CNI su `169.254.172.0/22`); i nodi restano dual-stack.
- Le subnet del cluster devono avere CIDR IPv6 associato e `assign-ipv6-address-on-creation`.

```yaml
# Service Kubernetes dual-stack
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: ClusterIP
  ipFamilyPolicy: PreferDualStack   # SingleStack | PreferDualStack | RequireDualStack
  ipFamilies: [IPv6, IPv4]
  selector: { app: web }
  ports: [{ port: 80, targetPort: 8080 }]
---
# Ingress su ALB dualstack (AWS Load Balancer Controller)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/ip-address-type: dualstack
spec:
  ingressClassName: alb
  rules:
    - http:
        paths:
          - { path: /, pathType: Prefix, backend: { service: { name: web, port: { number: 80 } } } }
```

!!! note "EKS IPv4 vs IPv6"
    In un cluster `ipv6` i Service `ClusterIP` ricevono indirizzi IPv6 ULA (`fd00::/8`, range gestito da EKS). Non è possibile convertire un cluster IPv4 esistente: si crea un nuovo cluster e si migra i workload (blue/green).

### 7. Individuare IPv4 pubblici e costi

```bash
# Public IPv4 Insights in VPC IPAM (Public IP Insights)
aws ec2 describe-public-ipv4-pools 2>/dev/null
aws ec2 describe-addresses --query 'Addresses[].[PublicIp,AssociationId,InstanceId]' --output table

# Costo: cost explorer, usage type "PublicIPv4:InUseAddress" e "PublicIPv4:IdleAddress"
aws ce get-cost-and-usage --time-period Start=2026-08-01,End=2026-09-01 \
    --granularity MONTHLY --metrics UnblendedCost \
    --filter '{"Dimensions":{"Key":"USAGE_TYPE_GROUP","Values":["EC2: Public IPv4 Addresses"]}}'
```

## Best Practices

- **Migra per fasi**: 1) dual-stack sul VPC, 2) dual-stack su LB/CloudFront/Route 53, 3) workload IPv6-preferring, 4) IPv6-only dove possibile.
- **Sostituisci NAT Gateway con EIGW** per il traffico IPv6 in uscita: nessun costo orario né per GB di elaborazione (traffico dati standard escluso).
- Usa **`dualstack-without-public-ipv4`** sugli ALB internet-facing per evitare i costi IPv4 del load balancer quando i client sono IPv6.
- Concentra l'ingresso IPv4 su pochi punti (CloudFront/ALB condiviso) e tieni i workload dietro IPv6/private.
- **Regole SG/NACL simmetriche** IPv4/IPv6: gestiscile in IaC (moduli Terraform) per evitare dimenticanze.
- Usa endpoint **dual-stack** dei servizi AWS (`*.dualstack.<region>.amazonaws.com` o il nuovo formato `*.<region>.api.aws`) e abilita `AWS_USE_DUALSTACK_ENDPOINT=true` negli SDK/CLI.
- Pianifica gli indirizzi con **VPC IPAM**; tieni i log (VPC Flow Logs) con campi IPv6.
- **Evita** di hard-codare IP IPv4 in config/allowlist: passa a hostname o prefix list (`aws_ec2_managed_prefix_list` supporta `IPv6`).
- Testa con `curl -6`/`curl -4` e con client IPv6-only reali: Happy Eyeballs nasconde i guasti.

!!! warning "Sicurezza: IPv6 non è NAT"
    Con IPv6 ogni istanza è potenzialmente raggiungibile globalmente: la **sola** barriera è SG + route. Non mettere mai `::/0` in ingresso su porte di amministrazione (22, 3389) e verifica che le subnet private usino EIGW, non IGW. Un SG con solo regole IPv4 non protegge da traffico IPv6 se poi aggiungi `::/0` "per fare un test".

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---|---|---|
| Servizio raggiungibile **solo via IPv4**, `curl -6` va in timeout | Manca record `AAAA`, o LB non dualstack | `aws elbv2 describe-load-balancers --query 'LoadBalancers[].IpAddressType'`; impostare `dualstack` e creare alias AAAA |
| ALB dualstack ma target `unhealthy` con IPv6 | **Target group** di tipo IPv4, oppure target IPv6 non in ascolto su `::` | Creare TG con `--ip-address-type ipv6`; verificare che l'app faccia bind su `::`, non solo `0.0.0.0` (`ss -lnt \| grep 8080`) |
| Connessione IPv6 rifiutata / timeout con IPv4 OK | SG senza regola `::/0` (o NACL senza regola IPv6 e ephemeral in uscita) | `aws ec2 describe-security-groups --group-ids sg-x --query '...IpPermissions[].Ipv6Ranges'`; aggiungere le regole IPv6; controllare NACL |
| Istanza privata non esce su IPv6 | Route `::/0` mancante o punta a IGW/NAT GW invece che EIGW | Verificare route table: `::/0 → eigw-xxx` per subnet private |
| Subnet IPv6-only: `curl https://host-solo-ipv4` fallisce | DNS64 disabilitato o route `64:ff9b::/96` mancante | `modify-subnet-attribute --enable-dns64`; aggiungere route verso NAT GW **in subnet con IPv4** |
| `aws eks create-cluster` ipv6 fallisce / Pod senza IP | Subnet senza CIDR IPv6, istanze non Nitro, VPC CNI vecchio | Associare IPv6 alle subnet; usare famiglie Nitro (m5+/c5+); aggiornare il CNI ≥ 1.10.1; `ipFamily` non modificabile → ricreare |
| Lentezza intermittente (100–300 ms extra) | Happy Eyeballs fa fallback su IPv4 perché il path IPv6 è rotto | Testare `curl -6 -v`; correggere SG/NACL/route; verificare che il target risponda su IPv6 |
| SDK/CLI chiamano endpoint solo IPv4 in subnet IPv6-only | Servizio senza endpoint dual-stack o SDK non configurato | Impostare `AWS_USE_DUALSTACK_ENDPOINT=true`; verificare in doc AWS che il servizio supporti dual-stack; se assente usare NAT64 |

```bash
# Diagnostica rapida IPv6 end-to-end
curl -6 -sS -o /dev/null -w '%{http_code} %{time_total}s\n' https://www.example.com
dig AAAA www.example.com +short
aws ec2 describe-network-interfaces --network-interface-ids eni-0abc \
    --query 'NetworkInterfaces[0].Ipv6Addresses'
# Reachability Analyzer supporta IPv6 tra ENI/IGW/EIGW
aws ec2 create-network-insights-path --source eni-0abc --destination igw-0abc \
    --protocol tcp --destination-port 443
```

## Relazioni

??? info "VPC — Fondamenti"
    Subnet, route table, IGW, NAT Gateway e security group su cui si innesta il dual-stack.

    **Approfondimento completo →** [VPC](vpc.md)

??? info "VPC Avanzato — Peering e Transit Gateway"
    Peering, TGW e VPN supportano IPv6; con IPv6 i problemi di CIDR sovrapposti spariscono.

    **Approfondimento completo →** [VPC Avanzato](vpc-avanzato.md)

??? info "Route 53"
    Record `AAAA`, alias, health check e Resolver (DNS64) per il dual-stack.

    **Approfondimento completo →** [Route 53](route53.md)

??? info "Elastic Load Balancing"
    ALB/NLB con `ip-address-type` dualstack e target group IPv6.

    **Approfondimento completo →** [Elastic Load Balancing](elastic-load-balancing.md)

??? info "CloudFront"
    IPv6 abilitato per distribuzione, alias `AAAA` verso il dominio CloudFront.

    **Approfondimento completo →** [CloudFront](cloudfront.md)

??? info "EKS"
    Cluster con `ipFamily: ipv6`, VPC CNI e prefix delegation.

    **Approfondimento completo →** [EKS](../containers/eks.md)

??? info "Indirizzi IP e subnetting"
    Teoria di IPv4/IPv6, prefissi e notazione.

    **Approfondimento completo →** [Indirizzi IP e subnetting](../../../networking/fondamentali/indirizzi-ip-subnetting.md)

## Riferimenti

- [AWS — Migrate your VPC from IPv4 to IPv6](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-migrate-ipv6.html)
- [AWS — Egress-only internet gateways](https://docs.aws.amazon.com/vpc/latest/userguide/egress-only-internet-gateway.html)
- [AWS — DNS64 and NAT64](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-nat64-dns64.html)
- [AWS — EKS: Run IPv6 clusters](https://docs.aws.amazon.com/eks/latest/userguide/cni-ipv6.html)
- [AWS — Public IPv4 address charge](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/)
- [AWS — Services that support IPv6](https://docs.aws.amazon.com/vpc/latest/userguide/aws-ipv6-support.html)
- [RFC 8305 — Happy Eyeballs v2](https://datatracker.ietf.org/doc/html/rfc8305)
