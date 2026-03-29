---
title: "WAF, Shield, Network Firewall e Sicurezza di Rete AWS"
slug: network-security
category: cloud
tags: [aws, waf, shield, network-firewall, security-groups, nacl, ddos, owasp, suricata, bot-control, managed-rules, prefix-list]
search_keywords: [aws waf, web application firewall, owasp, sql injection, xss, rate limiting, bot control, managed rules, aws shield, shield advanced, ddos protection, srt, network firewall, suricata, stateful firewall, stateless firewall, tls inspection, security groups, nacl, network access control list, managed prefix list, vpc security, layer 7, layer 3 layer 4]
parent: cloud/aws/security/_index
related: [cloud/aws/security/kms-secrets, cloud/aws/security/compliance-audit, cloud/aws/networking, cloud/aws/monitoring/cloudwatch]
official_docs: https://docs.aws.amazon.com/waf/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# WAF, Shield, Network Firewall e Sicurezza di Rete AWS

## Panoramica

La sicurezza di rete su AWS è stratificata su più livelli: protezione a livello applicativo (AWS WAF), protezione DDoS (Distributed Denial of Service — AWS Shield), firewall managed a livello VPC (Network Firewall), e controllo granulare del traffico di rete (Security Groups, NACLs). Ogni livello serve uno scopo specifico e si integra con gli altri.

---

## AWS WAF — Web Application Firewall

### Panoramica

AWS WAF è un firewall a livello applicativo (Layer 7) che protegge le applicazioni web da attacchi comuni: SQL injection, Cross-Site Scripting (XSS), attacchi OWASP (Open Web Application Security Project) Top 10, bot dannosi, scraping, credential stuffing.

**Integrazione con:**
- Application Load Balancer (ALB)
- Amazon CloudFront
- AWS API Gateway
- AWS AppSync (GraphQL)
- Amazon Cognito User Pool
- AWS App Runner
- AWS Verified Access

### Architettura Web ACL

La **Web ACL** (Access Control List) è il container di regole WAF associato a una o più risorse protette.

```
[Internet Traffic]
      │
[Web ACL]
  ├── Rule 1: AWS Managed Rules - CommonRuleSet → Block OWASP Top 10
  ├── Rule 2: Rate-Based Rule → Block >2000 req/5min per IP
  ├── Rule 3: IP Set Rule → Block IP blacklist
  ├── Rule 4: Geo Match → Block specific countries
  ├── Rule 5: String Match → Custom application rules
  └── Default Action → Allow/Block
      │
[Protected Resource: ALB / CloudFront / API GW]
```

**Priority:** Le regole vengono valutate in ordine di priorità (numero più basso = valutato prima). La prima regola che fa match determina l'azione.

### AWS Managed Rule Groups

AWS e vendor di sicurezza forniscono rule groups già pronti:

| Rule Group | Descrizione |
|-----------|-------------|
| `AWSManagedRulesCommonRuleSet` | OWASP Top 10: SQLi, XSS, LFI (Local File Inclusion), RFI (Remote File Inclusion), SSRF (Server-Side Request Forgery) |
| `AWSManagedRulesKnownBadInputsRuleSet` | Pattern di input noti per sfruttare vulnerabilità |
| `AWSManagedRulesSQLiRuleSet` | SQL injection avanzato |
| `AWSManagedRulesLinuxRuleSet` | Attacchi specifici Linux (LFI, path traversal) |
| `AWSManagedRulesWindowsRuleSet` | Attacchi PowerShell, SSRF Windows |
| `AWSManagedRulesAmazonIpReputationList` | IP con cattiva reputazione AWS |
| `AWSManagedRulesAnonymousIpList` | Proxy, VPN, Tor exit nodes |
| `AWSManagedRulesBotControlRuleSet` | Rilevamento bot (Common + Targeted) |
| `AWSManagedRulesACFPRuleSet` | Account creation fraud (ACFP) |
| `AWSManagedRulesATPRuleSet` | Account takeover protection (ATP) |

### Configurare una Web ACL

```bash
# Creare una Web ACL (regionale — per ALB, API GW)
aws wafv2 create-web-acl \
  --name "MyAppWebACL" \
  --scope REGIONAL \
  --default-action Allow={} \
  --description "WAF per applicazione MyApp" \
  --rules '[
    {
      "Name": "AWSManagedCommonRules",
      "Priority": 10,
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesCommonRuleSet",
          "ExcludedRules": [
            {"Name": "SizeRestrictions_BODY"}
          ]
        }
      },
      "OverrideAction": {"None": {}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "AWSManagedCommonRules"
      }
    },
    {
      "Name": "RateLimitPerIP",
      "Priority": 20,
      "Statement": {
        "RateBasedStatement": {
          "Limit": 2000,
          "AggregateKeyType": "IP"
        }
      },
      "Action": {"Block": {}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "RateLimitPerIP"
      }
    },
    {
      "Name": "BlockBadBots",
      "Priority": 30,
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesBotControlRuleSet",
          "ManagedRuleGroupConfigs": [{
            "AWSManagedRulesBotControlRuleSet": {
              "InspectionLevel": "COMMON"
            }
          }]
        }
      },
      "OverrideAction": {"None": {}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "BotControl"
      }
    }
  ]' \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=MyAppWebACL \
  --region us-east-1

# Associare la Web ACL a un ALB
aws wafv2 associate-web-acl \
  --web-acl-arn arn:aws:wafv2:us-east-1:123456789012:regional/webacl/MyAppWebACL/abc123 \
  --resource-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-alb/abc123
```

### Regole Custom

```bash
# IP Set — lista IP da bloccare
aws wafv2 create-ip-set \
  --name "BlockedIPs" \
  --scope REGIONAL \
  --ip-address-version IPV4 \
  --addresses "198.51.100.0/24" "203.0.113.44/32"

# Regex Pattern Set
aws wafv2 create-regex-pattern-set \
  --name "BadUserAgents" \
  --scope REGIONAL \
  --regular-expression-list '[
    {"RegexString": "python-requests.*"},
    {"RegexString": "curl/.*"},
    {"RegexString": "Go-http-client.*"}
  ]'
```

**Regola Geo-Match (blocca paesi):**
```json
{
  "Name": "BlockHighRiskCountries",
  "Priority": 5,
  "Statement": {
    "GeoMatchStatement": {
      "CountryCodes": ["CN", "RU", "KP", "IR"]
    }
  },
  "Action": {"Block": {}},
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "GeoBlock"
  }
}
```

### Rate-Based Rules Avanzate

```json
{
  "Name": "RateLimitLoginEndpoint",
  "Priority": 15,
  "Statement": {
    "RateBasedStatement": {
      "Limit": 50,
      "AggregateKeyType": "IP",
      "ScopeDownStatement": {
        "ByteMatchStatement": {
          "FieldToMatch": {"UriPath": {}},
          "PositionalConstraint": "STARTS_WITH",
          "SearchString": "/api/auth/login",
          "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}]
        }
      }
    }
  },
  "Action": {"Block": {"CustomResponse": {
    "ResponseCode": 429,
    "CustomResponseBodyKey": "rate-limit-body"
  }}},
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "RateLimitLogin"
  }
}
```

### Logging WAF

```bash
# Configurare logging verso S3
aws wafv2 put-logging-configuration \
  --logging-configuration '{
    "ResourceArn": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/MyAppWebACL/abc123",
    "LogDestinationConfigs": [
      "arn:aws:s3:::my-waf-logs"
    ],
    "RedactedFields": [
      {"SingleHeader": {"Name": "authorization"}},
      {"SingleHeader": {"Name": "cookie"}}
    ]
  }'

# Logging verso CloudWatch Logs (real-time)
aws wafv2 put-logging-configuration \
  --logging-configuration '{
    "ResourceArn": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/MyAppWebACL/abc123",
    "LogDestinationConfigs": [
      "arn:aws:logs:us-east-1:123456789012:log-group:aws-waf-logs-myapp"
    ]
  }'
```

### Pricing WAF

- **$5.00/Web ACL/mese**
- **$1.00/regola/mese** (regole custom)
- **$0.60 per 1 milione di richieste** ispezionate
- **Bot Control:** $10/Web ACL/mese (Common) + $30 (Targeted)
- **Fraud Control ATP/ACFP:** $30/Web ACL/mese + $1 per 1.000 richieste login

---

## AWS Shield

### Shield Standard (gratuito)

Shield Standard è automaticamente abilitato per tutti i clienti AWS, senza costi aggiuntivi. Protegge da:
- SYN/UDP floods
- Reflection attacks (DNS, NTP, SSDP amplification)
- Layer 3 e Layer 4 DDoS comuni
- Supporta: EC2, Elastic IP, ALB, NLB, CloudFront, Route 53, Global Accelerator

### Shield Advanced ($3.000/mese/organizzazione)

Shield Advanced offre:
- **Protezione DDoS Layer 7** (in combinazione con WAF)
- **SRT (Shield Response Team):** team di esperti AWS disponibili 24/7 per supporto durante attacchi
- **Cost Protection:** rimborso dei costi AWS (EC2, ELB, CloudFront, Route 53) causati da un attacco DDoS
- **WAF gratuito** per le risorse protette da Shield Advanced
- **Real-time visibility** su attacchi in corso (CloudWatch metrics)
- **Protezione avanzata ELB, EC2, CloudFront, Route 53, Global Accelerator**

```bash
# Attivare Shield Advanced
aws shield create-subscription

# Proteggere una risorsa specifica
aws shield create-protection \
  --name "MyALB-Protection" \
  --resource-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-alb/abc123

aws shield create-protection \
  --name "CloudFront-Protection" \
  --resource-arn arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE

# Verificare protezioni attive
aws shield list-protections

# Verificare attacchi recenti
aws shield list-attacks \
  --start-time StartTime=$(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ),EndTime=$(date +%Y-%m-%dT%H:%M:%SZ)
```

!!! note "Shield Advanced e Organizations"
    Con AWS Organizations, il costo di $3.000/mese è per l'organizzazione intera (non per account). Conviene se si hanno molte risorse da proteggere.

---

## AWS Network Firewall

Network Firewall è un firewall managed stateful/stateless per VPC. Si posiziona come gateway per ispezionare il traffico in/out del VPC e tra subnet.

### Architettura di Deployment

```
[Internet]
    │
[Internet Gateway]
    │
[Firewall Subnet] (dedicated subnet per ogni AZ)
    │ → Network Firewall Endpoint
    │ (stateful + stateless inspection)
    │
[Application Subnet]
    │
[EC2 / ECS / EKS workloads]
```

Il traffico viene diretto verso il Network Firewall tramite modifiche alle route tables (Gateway Load Balancer style routing).

### Rule Types

**Stateless Rules (5-tuple matching):**
- Source/destination IP, source/destination port, protocol
- Molto veloce, elaborazione prima delle stateful rules
- Azioni: Pass, Drop, Forward to stateful

**Stateful Rules:**
- Ispezione dello stato della connessione (connection tracking)
- Three engines:
  - **Suricata compatible rules:** IDS/IPS signature-based detection
  - **Domain list:** filtraggio per domain name (FQDN)
  - **Standard stateful rules:** più semplici, simile a iptables

### Configurare Network Firewall

```bash
# Creare regole Suricata per IPS
cat > suricata-rules.rules << 'EOF'
# Blocca SQL injection
alert http any any -> $HOME_NET any (msg:"SQL Injection Attempt"; content:"UNION SELECT"; nocase; http_uri; sid:1000001; rev:1;)

# Blocca port scanning
alert tcp any any -> $HOME_NET any (msg:"Port Scan Detected"; flags:S; threshold:type threshold,track by_src,count 10,seconds 60; sid:1000002; rev:1;)

# Blocca traffico verso domini noti malware
drop dns any any -> any any (msg:"Known Malware Domain"; dns.query; content:"malware-c2.evil.com"; sid:1000003; rev:1;)
EOF

# Creare Rule Group con regole Suricata
aws network-firewall create-rule-group \
  --rule-group-name "SuricataRules" \
  --type STATEFUL \
  --capacity 100 \
  --rule-group '{
    "RulesSource": {
      "RulesString": "'"$(cat suricata-rules.rules | tr '\n' ';' | sed 's/;$//')"'"
    },
    "StatefulRuleOptions": {
      "RuleOrder": "STRICT_ORDER"
    }
  }'

# Creare Rule Group per domain filtering
aws network-firewall create-rule-group \
  --rule-group-name "BlockedDomains" \
  --type STATEFUL \
  --capacity 100 \
  --rule-group '{
    "RulesSource": {
      "RulesSourceList": {
        "Targets": ["malware.example.com", "c2server.evil.net"],
        "TargetTypes": ["HTTP_HOST", "TLS_SNI"],
        "GeneratedRulesType": "DENYLIST"
      }
    }
  }'

# Creare la Firewall Policy
aws network-firewall create-firewall-policy \
  --firewall-policy-name "MyFirewallPolicy" \
  --firewall-policy '{
    "StatelessDefaultActions": ["aws:forward_to_sfe"],
    "StatelessFragmentDefaultActions": ["aws:drop"],
    "StatefulRuleGroupReferences": [
      {"ResourceArn": "arn:aws:network-firewall:us-east-1:123456789012:stateful-rulegroup/SuricataRules"},
      {"ResourceArn": "arn:aws:network-firewall:us-east-1:123456789012:stateful-rulegroup/BlockedDomains"}
    ],
    "StatefulDefaultActions": ["aws:drop_established"],
    "StatefulEngineOptions": {
      "RuleOrder": "STRICT_ORDER",
      "StreamExceptionPolicy": "DROP"
    }
  }'

# Creare il Firewall
aws network-firewall create-firewall \
  --firewall-name "MyVPCFirewall" \
  --firewall-policy-arn arn:aws:network-firewall:us-east-1:123456789012:firewall-policy/MyFirewallPolicy \
  --vpc-id vpc-1234567890 \
  --subnet-mappings '[
    {"SubnetId": "subnet-fw-az1"},
    {"SubnetId": "subnet-fw-az2"}
  ]' \
  --description "Network Firewall for production VPC"
```

### TLS Inspection

Network Firewall può decriptare, ispezionare, e ri-cifrare il traffico HTTPS (SSL/TLS inspection) per rilevare minacce nascoste nel traffico cifrato.

```bash
# Creare TLS inspection configuration
aws network-firewall create-tls-inspection-configuration \
  --tls-inspection-configuration-name "TLSInspection" \
  --tls-inspection-configuration '{
    "ServerCertificateConfigurations": [{
      "ServerCertificates": [{
        "ResourceArn": "arn:aws:acm:us-east-1:123456789012:certificate/abc123"
      }],
      "Scopes": [{
        "Sources": [{"AddressDefinition": "0.0.0.0/0"}],
        "Destinations": [{"AddressDefinition": "$HOME_NET"}],
        "SourcePorts": [{"FromPort": 0, "ToPort": 65535}],
        "DestinationPorts": [{"FromPort": 443, "ToPort": 443}],
        "Protocols": [6]
      }]
    }]
  }'
```

### Logging Network Firewall

```bash
# Configurare logging verso S3 e CloudWatch
aws network-firewall update-logging-configuration \
  --firewall-name "MyVPCFirewall" \
  --logging-configuration '{
    "LogDestinationConfigs": [
      {
        "LogType": "FLOW",
        "LogDestinationType": "S3",
        "LogDestination": {"bucketName": "my-nfw-logs", "prefix": "flow/"}
      },
      {
        "LogType": "ALERT",
        "LogDestinationType": "CloudWatchLogs",
        "LogDestination": {"logGroup": "/aws/network-firewall/alerts"}
      }
    ]
  }'
```

---

## Security Groups — Concetti Avanzati

I Security Groups sono il firewall di istanza in AWS: stateful (traccia lo stato delle connessioni), valutano separatamente le inbound e outbound rules.

### Caratteristiche Fondamentali

- **Stateful:** se una connessione inbound è permessa, la risposta outbound è automaticamente permessa (e viceversa)
- **Allow only:** si possono solo aggiungere regole Allow (non Deny)
- **Applicati a risorse:** ogni risorsa (EC2, RDS, Lambda in VPC, ECS container) può avere fino a 5 SG
- **Default:** tutto inbound bloccato, tutto outbound permesso

### Referenziare Altri Security Groups

Invece di specificare CIDR IP, si possono referenziare altri Security Group come sorgente/destinazione. Questo è più robusto: se gli IP cambiano (autoscaling), le regole rimangono valide.

```bash
# Permetti traffico HTTPS da qualsiasi risorsa nel SG degli ALB
aws ec2 authorize-security-group-ingress \
  --group-id sg-app-servers \
  --protocol tcp \
  --port 443 \
  --source-group sg-alb  # tutti i server nell'SG degli ALB possono connettersi

# Permetti MySQL da un SG specifico (esempio: app servers → RDS)
aws ec2 authorize-security-group-ingress \
  --group-id sg-rds-database \
  --protocol tcp \
  --port 3306 \
  --source-group sg-app-servers

# Referenziare SG cross-account (VPC Sharing)
aws ec2 authorize-security-group-ingress \
  --group-id sg-local \
  --protocol tcp \
  --port 80 \
  --source-group sg-remote-account \
  --source-group-owner-id 999888777666
```

### Managed Prefix Lists

Le Managed Prefix Lists sono liste di CIDR gestite centralmente, usabili nelle regole dei Security Groups. AWS mantiene prefix lists aggiornate per i propri servizi.

```bash
# Listare le Managed Prefix Lists AWS
aws ec2 describe-managed-prefix-lists \
  --filters Name=owner-id,Values=AWS

# Esempio: permettere accesso solo da CloudFront
# Trovare il prefix list ID di CloudFront
CF_PREFIX_LIST_ID=$(aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' \
  --output text)

# Usare nelle regole SG
aws ec2 authorize-security-group-ingress \
  --group-id sg-alb \
  --ip-permissions '[{
    "IpProtocol": "tcp",
    "FromPort": 443,
    "ToPort": 443,
    "PrefixListIds": [{"PrefixListId": "'"$CF_PREFIX_LIST_ID"'"}]
  }]'

# Creare una Managed Prefix List custom
aws ec2 create-managed-prefix-list \
  --prefix-list-name "OfficeIPs" \
  --max-entries 20 \
  --address-family IPv4

# Aggiungere CIDR alla lista
aws ec2 modify-managed-prefix-list \
  --prefix-list-id pl-1234567890 \
  --current-version 1 \
  --add-entries '[
    {"Cidr": "203.0.113.0/24", "Description": "Ufficio Milano"},
    {"Cidr": "198.51.100.10/32", "Description": "VPN aziendale"}
  ]'
```

---

## Network ACLs (NACLs) — Avanzate

A differenza dei Security Groups, le NACLs operano a livello di subnet e sono **stateless** (le risposte devono essere esplicitamente permesse).

**NACLs vs Security Groups:**

| | Security Groups | NACLs |
|--|----------------|------|
| Applicazione | Istanza/risorsa | Subnet |
| Stateful | Sì | No |
| Regole | Solo Allow | Allow + Deny |
| Valutazione | Tutte le regole | Prima che fa match (per number) |
| Default | Deny all in, Allow all out | Allow all (default NACL) |

```bash
# Creare una NACL custom
NACL_ID=$(aws ec2 create-network-acl \
  --vpc-id vpc-1234567890 \
  --tag-specifications 'ResourceType=network-acl,Tags=[{Key=Name,Value=app-subnet-nacl}]' \
  --query 'NetworkAcl.NetworkAclId' \
  --output text)

# Aggiungere regole (rule number = priorità, più basso = prima)
# Allow HTTP inbound
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 100 \
  --protocol tcp \
  --port-range From=80,To=80 \
  --cidr-block 0.0.0.0/0 \
  --rule-action allow \
  --ingress

# Allow HTTPS inbound
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 110 \
  --protocol tcp \
  --port-range From=443,To=443 \
  --cidr-block 0.0.0.0/0 \
  --rule-action allow \
  --ingress

# Allow ephemeral ports per risposte outbound (stateless!)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 900 \
  --protocol tcp \
  --port-range From=1024,To=65535 \
  --cidr-block 0.0.0.0/0 \
  --rule-action allow \
  --ingress

# Deny all inbound (rule number 1000 = catch-all)
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 1000 \
  --protocol -1 \
  --cidr-block 0.0.0.0/0 \
  --rule-action deny \
  --ingress

# Associare la NACL a una subnet
aws ec2 replace-network-acl-association \
  --association-id aclassoc-1234567890 \
  --network-acl-id $NACL_ID
```

!!! warning "NACLs e porte effimere"
    Poiché le NACLs sono stateless, bisogna sempre permettere le **porte effimere** (1024-65535) in entrambe le direzioni per permettere le risposte TCP. Dimenticare questo è un errore frequente.

---

## Best Practices Sicurezza di Rete

### Layered Defense

```
Internet
  → CloudFront + AWS WAF (L7, DDoS CloudFront)
  → Shield Advanced (DDoS protection)
  → ALB (TLS termination, WAF)
  → Network Firewall (VPC-level inspection)
  → Security Groups (istanza-level)
  → NACLs (subnet-level, come backup)
  → Applicazione (input validation, authentication)
```

### Security Group Design

1. **Principio del minimo privilegio:** permettere solo le porte necessarie
2. **Referenziare SG** invece di CIDR dove possibile (più robusto all'autoscaling)
3. **SG per tier:** sg-alb, sg-web, sg-app, sg-db (ogni tier comunica solo col successivo)
4. **Managed Prefix Lists** per IP AWS (CloudFront, S3 gateway, etc.)
5. **Audit regolare:** usare Security Hub + Inspector per trovare SG troppo permissivi

```bash
# Trovare Security Groups con 0.0.0.0/0 su porte sensibili
aws ec2 describe-security-groups \
  --query 'SecurityGroups[?IpPermissions[?IpRanges[?CidrIp==`0.0.0.0/0`] && (FromPort==`22` || FromPort==`3389`)]].[GroupId,GroupName]' \
  --output table
```

### WAF Best Practices

1. **Iniziare in COUNT mode** — monitora senza bloccare per verificare falsi positivi
2. **AWS Managed Rules** sono il punto di partenza, poi aggiungere regole custom
3. **Rate limiting** su tutti gli endpoint sensibili (login, registrazione, API)
4. **Logging sempre attivo** — essenziale per analisi e forensics
5. **Usare WAF con CloudFront** per protezione globale edge

---

## Troubleshooting

### Scenario 1 — WAF Blocca Traffico Legittimo

**Sintomo:** Richieste legitimate vengono bloccate con HTTP 403; utenti reali segnalano accesso negato.

**Causa:** Una o più AWS Managed Rules generano falsi positivi su payload legittimi (es. corpo JSON con caratteri speciali, User-Agent non standard, header grandi).

**Soluzione:** Passare la regola sospetta in COUNT mode per isolarla senza impatto, analizzare i sample requests, poi escludere la regola specifica o creare un'eccezione.

```bash
# Analizzare i sample request bloccati dalla regola sospetta
aws wafv2 get-sampled-requests \
  --web-acl-arn arn:aws:wafv2:us-east-1:123456789012:regional/webacl/MyAppWebACL/abc123 \
  --rule-metric-name AWSManagedCommonRules \
  --scope REGIONAL \
  --time-window StartTime=$(date -d '1 hour ago' +%s),EndTime=$(date +%s) \
  --max-items 100

# Elencare le regole della Web ACL per identificare quale escludere
aws wafv2 get-web-acl \
  --name "MyAppWebACL" \
  --scope REGIONAL \
  --id abc123 \
  --query 'WebACL.Rules[*].[Name,Priority,OverrideAction,Action]' \
  --output table
```

Dopo aver identificato la regola: impostare `ExcludedRules` nel `ManagedRuleGroupStatement` per escluderla, oppure aggiungere una regola Allow con priorità più bassa che fa match sul traffico legittimo prima che arrivi alle Managed Rules.

### Scenario 2 — Connettività EC2 Bloccata (Security Group / NACL)

**Sintomo:** Un'istanza EC2 non è raggiungibile su una porta specifica nonostante il Security Group sembri corretto; `telnet` / `curl` timeout.

**Causa:** NACL della subnet blocca il traffico (statefulness diversa rispetto ai SG), oppure il Security Group di destinazione non referenzia correttamente la sorgente, oppure mancano le porte effimere nel NACL outbound.

**Soluzione:** Usare VPC Reachability Analyzer per individuare il blocco esatto nel path di rete.

```bash
# Creare un path di analisi da ENI sorgente a ENI destinazione
aws ec2 create-network-insights-path \
  --source eni-1234567890 \
  --destination eni-abcdef1234 \
  --protocol TCP \
  --destination-port 443

# Avviare l'analisi
aws ec2 start-network-insights-analysis \
  --network-insights-path-id nip-1234567890

# Recuperare i risultati (attendere che lo stato diventi succeeded)
aws ec2 describe-network-insights-analyses \
  --network-insights-analysis-ids nia-1234567890 \
  --query 'NetworkInsightsAnalyses[0].{Status:Status,Explanations:Explanations[0]}' \
  --output json

# Verifica rapida NACL della subnet
aws ec2 describe-network-acls \
  --filters Name=association.subnet-id,Values=subnet-1234567890 \
  --query 'NetworkAcls[0].Entries[*].[RuleNumber,Protocol,RuleAction,CidrBlock,PortRange]' \
  --output table
```

### Scenario 3 — Network Firewall Scarta Traffico Inatteso

**Sintomo:** Dopo il deployment del Network Firewall il traffico verso/da alcune destinazioni viene droppato silenziosamente; la connettività era funzionante prima.

**Causa:** Le route tables del VPC non sono state aggiornate correttamente per dirigere il traffico attraverso il Firewall Endpoint, oppure le stateful rules hanno `StatefulDefaultActions: aws:drop_established` che scarta connessioni non esplicitamente permesse.

**Soluzione:** Verificare che le route tables usino il Firewall Endpoint come next-hop, e controllare i log ALERT/FLOW per identificare i pacchetti droppati.

```bash
# Verificare lo stato del Firewall e gli endpoint per ogni AZ
aws network-firewall describe-firewall \
  --firewall-name "MyVPCFirewall" \
  --query 'FirewallStatus.SyncStates' \
  --output json

# Recuperare gli endpoint ID da usare nelle route tables
aws network-firewall describe-firewall \
  --firewall-name "MyVPCFirewall" \
  --query 'FirewallStatus.SyncStates.*.Attachment.EndpointId' \
  --output text

# Cercare alert recenti nei log CloudWatch
aws logs filter-log-events \
  --log-group-name "/aws/network-firewall/alerts" \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern "{ $.event.action = \"blocked\" }" \
  --limit 50 \
  --query 'events[*].message' \
  --output text
```

### Scenario 4 — NACL Blocca Risposte TCP (Porte Effimere)

**Sintomo:** Le connessioni TCP da una subnet verso risorse esterne si avviano ma non ricevono risposta; SYN inviato, mai SYN-ACK ricevuto o risposta droppata al ritorno.

**Causa:** Le NACLs sono stateless: le risposte TCP tornano su porte effimere (1024–65535). Se la NACL di inbound non permette esplicitamente queste porte, le risposte vengono scartate anche se la connessione outbound era permessa.

**Soluzione:** Aggiungere una regola NACL inbound che permette le porte effimere 1024–65535 dal CIDR di destinazione.

```bash
# Verificare le regole NACL della subnet (cercare porte effimere)
NACL_ID=$(aws ec2 describe-network-acls \
  --filters Name=association.subnet-id,Values=subnet-1234567890 \
  --query 'NetworkAcls[0].NetworkAclId' --output text)

aws ec2 describe-network-acls \
  --network-acl-ids $NACL_ID \
  --query 'NetworkAcls[0].Entries[?!Egress].[RuleNumber,Protocol,RuleAction,CidrBlock,PortRange]' \
  --output table

# Aggiungere regola per porte effimere (inbound) se mancante
aws ec2 create-network-acl-entry \
  --network-acl-id $NACL_ID \
  --rule-number 900 \
  --protocol tcp \
  --port-range From=1024,To=65535 \
  --cidr-block 0.0.0.0/0 \
  --rule-action allow \
  --ingress
```

---

## Relazioni

??? info "KMS — TLS e Certificati"
    ACM usa KMS internamente. Per TLS inspection con Network Firewall si usano certificati ACM.

    **Approfondimento completo →** [KMS e Secrets Manager](kms-secrets.md)

??? info "GuardDuty — Threat Detection"
    GuardDuty analizza il VPC Flow Logs per rilevare comportamenti anomali di rete.

    **Approfondimento completo →** [Compliance e Audit](compliance-audit.md)

??? info "CloudWatch — WAF Metrics"
    Le metriche WAF (blocked requests, sampled requests) sono visibili in CloudWatch.

    **Approfondimento completo →** [CloudWatch](../monitoring/cloudwatch.md)

---

## Riferimenti

- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/latest/developerguide/)
- [AWS WAF Managed Rules](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-list.html)
- [AWS Shield Documentation](https://docs.aws.amazon.com/shield/)
- [Network Firewall Documentation](https://docs.aws.amazon.com/network-firewall/)
- [Suricata Rule Format](https://suricata.readthedocs.io/en/suricata-6.0.0/rules/intro.html)
- [VPC Security Best Practices](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-best-practices.html)
- [WAF Pricing](https://aws.amazon.com/waf/pricing/)
- [Shield Pricing](https://aws.amazon.com/shield/pricing/)
