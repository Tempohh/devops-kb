---
title: "Route 53 — DNS Managed"
slug: route53
category: cloud
tags: [aws, route53, dns, routing-policies, health-checks, hosted-zones, dnssec, alias, geolocation, latency, failover, geoproximity, weighted]
search_keywords: [AWS Route 53, DNS, hosted zone, public hosted zone, private hosted zone, record types, A record, AAAA, CNAME, alias, routing policy, simple routing, weighted routing, latency routing, failover routing, geolocation routing, geoproximity, multivalue answer, health check, DNSSEC, Route 53 Resolver, DNS Firewall, domain registration]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/vpc, cloud/aws/networking/cloudfront, cloud/aws/compute/ec2-autoscaling]
official_docs: https://docs.aws.amazon.com/route53/latest/developerguide/
status: complete
difficulty: intermediate
last_updated: 2026-03-03
---

# Route 53 — DNS Managed

**Route 53** è il servizio DNS managed di AWS — global, altamente disponibile (SLA — Service Level Agreement — al 100%), scalabile.

!!! note "Il nome"
    "Route 53" si riferisce alla porta 53, la porta standard del DNS.

---

## Hosted Zones

Una **Hosted Zone** è un contenitore di record DNS per un dominio.

| Tipo | Descrizione | Accesso |
|------|-------------|---------|
| **Public Hosted Zone** | Risponde a query DNS da Internet | Pubblico |
| **Private Hosted Zone** | Risponde solo all'interno di VPC specifici | VPC privati |

```bash
# Creare Public Hosted Zone
aws route53 create-hosted-zone \
    --name "company.com" \
    --caller-reference "$(date +%s)" \
    --hosted-zone-config Comment="Production DNS"
# Restituisce 4 nameserver AWS da configurare nel domain registrar

# Creare Private Hosted Zone (per DNS interno al VPC)
aws route53 create-hosted-zone \
    --name "internal.company.com" \
    --caller-reference "$(date +%s)" \
    --hosted-zone-config Comment="Internal DNS",PrivateZone=true \
    --vpc VPCRegion=eu-central-1,VPCId=vpc-xxxxx

# Associare Private HZ a più VPC
aws route53 associate-vpc-with-hosted-zone \
    --hosted-zone-id Z1234567890 \
    --vpc VPCRegion=eu-west-1,VPCId=vpc-yyyyy
```

---

## Tipi di Record

| Tipo | Descrizione | Esempio |
|------|-------------|---------|
| **A** | IPv4 address | `api.company.com → 1.2.3.4` |
| **AAAA** | IPv6 address | `api.company.com → 2001:db8::1` |
| **CNAME** | Alias a un altro hostname (no root domain) | `www.company.com → company.com` |
| **MX** | Mail exchange | Priority + hostname |
| **TXT** | Testo (SPF — Sender Policy Framework, DKIM — DomainKeys Identified Mail — verifica dominio) | `v=spf1 include:...` |
| **NS** | Nameserver della hosted zone | |
| **SOA** | Start of Authority | |
| **SRV** | Service record | `_http._tcp.example.com` |
| **CAA** | Certificate Authority Authorization | |

**Alias Record** (specifico AWS):
- Funziona come CNAME ma può essere usato su root domain (`@`)
- Punta a endpoint AWS (ALB, CloudFront, S3 static, API Gateway, ELB)
- **Gratuito** (nessun costo per query a alias records AWS)
- Supporta health checks sulla risorsa target

```bash
# Creare record A (indirizzo IP)
aws route53 change-resource-record-sets \
    --hosted-zone-id Z1234567890 \
    --change-batch '{
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "api.company.com",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "1.2.3.4"}]
            }
        }]
    }'

# Creare Alias Record (punta ad ALB)
aws route53 change-resource-record-sets \
    --hosted-zone-id Z1234567890 \
    --change-batch '{
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "company.com",
                "Type": "A",
                "AliasTarget": {
                    "HostedZoneId": "Z215JYRZR1TBD5",
                    "DNSName": "myalb-123456.eu-central-1.elb.amazonaws.com",
                    "EvaluateTargetHealth": true
                }
            }
        }]
    }'
```

---

## Routing Policies

| Policy | Comportamento | Use Case |
|--------|--------------|---------|
| **Simple** | Uno o più IP, risposta casuale | Target singolo, no health check |
| **Weighted** | % di traffico verso target diversi | A/B testing, blue/green |
| **Latency** | Target con minor latenza dalla Region AWS | Multi-Region per performance |
| **Failover** | Primary → Secondary se health check fallisce | DR attivo-passivo |
| **Geolocation** | In base alla posizione geografica del client | Content locale, compliance |
| **Geoproximity** | In base a posizione + bias | Controllo granulare distribuzione |
| **Multivalue Answer** | Fino a 8 IP, con health check | Load balancing lato client |
| **IP-based** | In base al CIDR IP del client | Controllo routing by network |

### Weighted Routing — A/B Testing / Blue-Green

```bash
# Blue-Green deployment: 90% vecchia versione, 10% nuova
aws route53 change-resource-record-sets \
    --hosted-zone-id Z1234567890 \
    --change-batch '{
        "Changes": [
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": "api.company.com",
                    "Type": "A",
                    "SetIdentifier": "Blue",
                    "Weight": 90,
                    "AliasTarget": {
                        "HostedZoneId": "Z215JYRZR1TBD5",
                        "DNSName": "blue-alb.eu-central-1.elb.amazonaws.com",
                        "EvaluateTargetHealth": true
                    }
                }
            },
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": "api.company.com",
                    "Type": "A",
                    "SetIdentifier": "Green",
                    "Weight": 10,
                    "AliasTarget": {
                        "HostedZoneId": "Z215JYRZR1TBD5",
                        "DNSName": "green-alb.eu-central-1.elb.amazonaws.com",
                        "EvaluateTargetHealth": true
                    }
                }
            }
        ]
    }'

# Spostare tutto il traffico su Green (blue-green swap)
# Modificare Weight: Blue=0, Green=100
```

### Failover Routing — Active-Passive DR

```bash
# Record primary con health check
aws route53 change-resource-record-sets \
    --hosted-zone-id Z1234567890 \
    --change-batch '{
        "Changes": [
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": "api.company.com",
                    "Type": "A",
                    "SetIdentifier": "Primary",
                    "Failover": "PRIMARY",
                    "HealthCheckId": "hc-primary-id",
                    "AliasTarget": {
                        "HostedZoneId": "...",
                        "DNSName": "primary.eu-central-1.elb.amazonaws.com",
                        "EvaluateTargetHealth": true
                    }
                }
            },
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": "api.company.com",
                    "Type": "A",
                    "SetIdentifier": "Secondary",
                    "Failover": "SECONDARY",
                    "AliasTarget": {
                        "HostedZoneId": "...",
                        "DNSName": "secondary.eu-west-1.elb.amazonaws.com",
                        "EvaluateTargetHealth": true
                    }
                }
            }
        ]
    }'
```

### Latency Routing — Multi-Region Performance

```bash
# Stesso nome DNS, target diversi per Region
# Route 53 risponde con il target con minor latency dalla Region AWS più vicina al client
# Creare record con Region specifica per ogni target

# Target in eu-central-1
aws route53 change-resource-record-sets \
    --hosted-zone-id Z1234567890 \
    --change-batch '{
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "api.company.com",
                "Type": "A",
                "SetIdentifier": "Frankfurt",
                "Region": "eu-central-1",
                "AliasTarget": {
                    "HostedZoneId": "...",
                    "DNSName": "frankfurt.eu-central-1.elb.amazonaws.com",
                    "EvaluateTargetHealth": true
                }
            }
        }]
    }'
# Ripetere per us-east-1, ap-southeast-1, etc.
```

---

## Health Checks

Route 53 monitora la salute degli endpoint e aggiorna il routing automaticamente.

```bash
# Health check HTTP
HC_ID=$(aws route53 create-health-check \
    --caller-reference "$(date +%s)" \
    --health-check-config '{
        "IPAddress": "1.2.3.4",
        "Port": 443,
        "Type": "HTTPS",
        "ResourcePath": "/health",
        "FullyQualifiedDomainName": "api.company.com",
        "RequestInterval": 30,
        "FailureThreshold": 3,
        "MeasureLatency": true
    }' \
    --query 'HealthCheck.Id' \
    --output text)

# Health check calcolato (aggregato di altri health checks)
aws route53 create-health-check \
    --caller-reference "$(date +%s)" \
    --health-check-config '{
        "Type": "CALCULATED",
        "ChildHealthChecks": ["hc-1", "hc-2"],
        "HealthThreshold": 1,
        "Inverted": false
    }'

# Monitorare stato health check
aws route53 get-health-check-status \
    --health-check-id $HC_ID
```

**Tipi di health check:**
- **Endpoint** — HTTP/HTTPS/TCP verso IP o hostname
- **Calculated** — aggregazione di più health check (AND/OR)
- **CloudWatch Alarm** — basato su allarme CloudWatch (per risorse private)

**Route 53 Health Checkers** si trovano in 15 Region globali — il target deve essere accessibile da tutte per passare.

---

## Route 53 Resolver

**Route 53 Resolver** gestisce la risoluzione DNS ibrida tra VPC e on-premises.

```bash
# Inbound Resolver Endpoint: on-premises → AWS (risolve .internal.company.com)
aws route53resolver create-resolver-endpoint \
    --name "inbound-resolver" \
    --host-vpc-id $VPC_ID \
    --security-group-ids $SG_RESOLVER \
    --direction INBOUND \
    --ip-addresses SubnetId=$PRIVATE_SUBNET_A SubnetId=$PRIVATE_SUBNET_B

# Outbound Resolver Endpoint: VPC → on-premises (risolve .corp.local)
aws route53resolver create-resolver-endpoint \
    --name "outbound-resolver" \
    --host-vpc-id $VPC_ID \
    --security-group-ids $SG_RESOLVER \
    --direction OUTBOUND \
    --ip-addresses SubnetId=$PRIVATE_SUBNET_A SubnetId=$PRIVATE_SUBNET_B

# Forwarding Rule: .corp.local → DNS server on-premises
aws route53resolver create-resolver-rule \
    --name "forward-corp-local" \
    --rule-type FORWARD \
    --domain-name "corp.local" \
    --resolver-endpoint-id rslvr-out-xxxx \
    --target-ips Ip=192.168.1.53,Port=53 Ip=192.168.1.54,Port=53
```

---

## Route 53 DNS Firewall

Blocca query DNS verso domini malevoli dal VPC:

```bash
# Creare Domain List con blocklist
aws route53resolver create-firewall-domain-list \
    --name "malware-blocklist"

aws route53resolver update-firewall-domains \
    --firewall-domain-list-id fdl-xxxx \
    --operation ADD \
    --domains "malware.example.com" "phishing.example.com"

# AWS managed domain lists (aggiornate automaticamente)
# - AWSManagedDomainsBotnetCommandandControl
# - AWSManagedDomainsMalwareDomainList

# Creare Rule Group e associare al VPC
aws route53resolver create-firewall-rule-group \
    --name "VPC-DNS-Protection"

aws route53resolver associate-firewall-rule-group \
    --firewall-rule-group-id rslvr-frg-xxxx \
    --vpc-id $VPC_ID \
    --priority 100 \
    --name "association"
```

---

## Riferimenti

- [Route 53 Developer Guide](https://docs.aws.amazon.com/route53/latest/developerguide/)
- [Routing Policies](https://docs.aws.amazon.com/route53/latest/developerguide/routing-policy.html)
- [Health Checks](https://docs.aws.amazon.com/route53/latest/developerguide/dns-failover.html)
- [Route 53 Resolver](https://docs.aws.amazon.com/route53/latest/developerguide/resolver.html)
