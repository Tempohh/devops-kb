---
title: "Protezione DDoS"
slug: ddos-protezione
category: networking
tags: [ddos, sicurezza, mitigazione, cloudflare, aws-shield, rate-limiting, anycast]
search_keywords: [distributed denial of service, ddos attack, volumetric attack, protocol attack, application layer attack, l3 ddos, l4 ddos, l7 ddos, syn flood, udp flood, http flood, slowloris, amplification attack, reflection attack, anycast scrubbing, bgp blackholing, null routing, cdn ddos, aws shield, cloudflare ddos, rate limiting ddos, waf ddos, botnet, ip spoofing]
parent: networking/sicurezza/_index
related: [networking/sicurezza/firewall-waf, networking/api-gateway/rate-limiting, networking/fondamentali/tcpip]
official_docs: https://aws.amazon.com/shield/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Protezione DDoS

## Panoramica

Un attacco DDoS (Distributed Denial of Service) cerca di rendere un servizio inaccessibile saturando le risorse (banda, CPU, connessioni) con traffico generato da migliaia di host compromessi (botnet). La difesa contro DDoS richiede una strategia a più livelli: mitigazione in-cloud (CDN, anycast scrubbing), protezione a livello di rete (BGP blackholing, rate limiting), e hardening applicativo (WAF, rate limiting L7, CAPTCHA).

Nessuna singola tecnologia protegge completamente da DDoS — la difesa efficace combina prevenzione, detection e risposta rapida.

## Concetti Chiave

### Classificazione degli Attacchi

| Tipo | Layer | Meccanismo | Esempio |
|------|-------|-----------|---------|
| **Volumetrico** | L3/L4 | Saturare la banda | UDP flood, ICMP flood, DNS amplification |
| **Protocol** | L4 | Esaurire risorse di sistema | SYN flood, Ping of Death, Smurf |
| **Applicativo** | L7 | Esaurire risorse applicative | HTTP flood, Slowloris, SSL exhaustion |

### Attacchi Volumetrici — Amplification

Gli attacchi più potenti usano **amplification**: il attaccante invia richieste piccole a server vulnerabili (DNS, NTP, memcached) con IP sorgente falsificato (spoofing) della vittima. Il server risponde con pacchetti molto più grandi alla vittima.

```
Attaccante                Amplifier (DNS)           Vittima
    │                          │                        │
    │── Query 100 byte ────────>│                        │
    │   (IP sorgente: vittima)  │                        │
    │                          │── Risposta 4000 byte ──>│
    │                          │   (amplification 40x)   │
    │                                                     │
    Botnet di 1000 host × 40x = attacco 40Gbps da 1Gbps traffico attaccante
```

**Amplification factors comuni:**
- DNS: 28-54x
- NTP monlist: 4000x
- memcached UDP: 51000x (!)
- SSDP: 30x

### SYN Flood — Come Funziona

```
Attaccante                              Server Vittima
    │                                        │
    │── SYN (IP spoofato) ───────────────────>│ Server crea half-open connection
    │── SYN (IP spoofato) ───────────────────>│ Slot SYN backlog occupato
    │── SYN (IP spoofato) ───────────────────>│ Slot SYN backlog occupato
    │ (migliaia al secondo)                   │ ... SYN backlog pieno
    │                                        │
    │                                  Nuove connessioni legittime
    │                                  vengono droppate (ECONNREFUSED)
```

**Mitigazione**: SYN cookies — il server non alloca stato finché il client non completa il 3-way handshake.

### Slowloris — Attacco Applicativo Silenzioso

```python
# Slowloris apre molte connessioni HTTP e le mantiene aperte
# inviando header incompleti lentissimamente, esaurendo
# il pool di connessioni del server senza generare traffico significativo

import socket, time

sockets = []
for _ in range(500):  # 500 connessioni "lente"
    s = socket.socket()
    s.connect(('target.com', 80))
    s.send(b"GET / HTTP/1.1\r\nHost: target.com\r\n")
    sockets.append(s)

while True:
    for s in sockets:
        s.send(b"X-Header: value\r\n")  # Header incompleto → connessione rimane aperta
    time.sleep(15)
```

**Mitigazione**: timeout aggressivi sulle connessioni, `LimitRequestLine`, worker process multipli, `mod_reqtimeout`.

## Strategie di Mitigazione

### 1. Anycast Scrubbing (CDN/Cloud Provider)

La mitigazione più efficace per attacchi volumetrici: il traffico viene assorbito dalla rete distribuita del provider (Cloudflare, AWS Shield, Akamai) prima di raggiungere l'infrastruttura:

```
Internet
    │
    │ (Attacco 100Gbps)
    ▼
Cloudflare / AWS Shield Network
    ├── PoP New York: assorbe 30Gbps
    ├── PoP Londra: assorbe 25Gbps
    ├── PoP Frankfurt: assorbe 20Gbps
    ├── PoP Tokyo: assorbe 15Gbps
    └── altri PoP...
    │
    │ (Traffico lecito filtrato)
    ▼
Infrastruttura cliente
```

Cloudflare e AWS Shield Advanced operano su reti da >100 Tbps — praticamente immuni agli attacchi volumetrici.

### 2. BGP Blackholing / Null Routing

In caso di attacco massiccio, annunciare via BGP che il target IP deve essere scartato da tutti i provider upstream. Il traffico viene droppato il più vicino possibile all'attaccante.

```bash
# Comunica all'ISP di fare null routing via BGP community
# (ogni ISP ha la propria community di blackholing)

# Esempio Juniper: annuncia la route con community 65535:666 (RTBH)
set routing-options static route 203.0.113.100/32 discard

# Via BGP verso l'ISP (community RTBH)
set policy-options policy-statement blackhole-community term match from route-filter 203.0.113.100/32 exact
set policy-options policy-statement blackhole-community term match then community add RTBH accept
set policy-options community RTBH members 65535:666
```

!!! warning "Tradeoff del Blackholing"
    Il blackholing protegge l'infrastruttura ma rende irraggiungibile il target — è una "vittoria di Pirro". Usarlo solo quando il costo del downtime è inferiore al costo del servizio degradato durante l'attacco.

### 3. Rate Limiting e Filtri L7

```nginx
# Nginx — Protezione anti-DDoS L7
http {
    # Limita connessioni per IP
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

    # Limita richieste per IP
    limit_req_zone $binary_remote_addr zone=req_limit:10m rate=30r/m;

    # Blocca User-Agent noti di bot DDoS
    map $http_user_agent $bad_bot {
        ~*(masscan|nikto|sqlmap|nmap) 1;
        default 0;
    }

    server {
        # Max 20 connessioni simultanee per IP
        limit_conn conn_limit 20;

        # Max 30 richieste al minuto con burst di 10
        limit_req zone=req_limit burst=10 nodelay;

        # Blocca bad bot
        if ($bad_bot = 1) {
            return 444;   # Chiude connessione senza risposta
        }

        # Timeout aggressivi contro Slowloris
        client_body_timeout   10s;
        client_header_timeout 10s;
        send_timeout          10s;
        keepalive_timeout     30s;

        # SYN cookies
        # (configurato in sysctl, non nginx)

        location / {
            # Anti-scraping: CAPTCHA challenge per rate alto
            limit_req zone=req_limit burst=5;
            proxy_pass http://backend;
        }
    }
}
```

```bash
# sysctl — Hardening kernel contro SYN flood
# /etc/sysctl.d/99-ddos-protection.conf

# SYN Cookies — protegge SYN backlog
net.ipv4.tcp_syncookies = 1

# Riduce il tempo di attesa per connessioni half-open
net.ipv4.tcp_synack_retries = 2

# Aumenta la dimensione del backlog SYN
net.ipv4.tcp_max_syn_backlog = 2048

# Abilita il filtraggio del percorso inverso (blocca IP spoofati)
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Ignora broadcast ICMP (Smurf attack)
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Limita la velocità dei pacchetti ICMP
net.ipv4.icmp_ratelimit = 100

# Applica
sysctl -p /etc/sysctl.d/99-ddos-protection.conf
```

### 4. AWS Shield e WAF

```bash
# Abilitare AWS Shield Advanced su una risorsa
aws shield associate-drt-log-bucket \
  --log-bucket my-access-logs-bucket

# Abilita protezione Shield Advanced su CloudFront distribution
aws shield create-protection \
  --name "prod-cloudfront" \
  --resource-arn arn:aws:cloudfront::123456789:distribution/ABCDEF

# WAF Rule per rate limiting IP
aws wafv2 create-ip-set \
  --name block-ips \
  --scope CLOUDFRONT \
  --ip-address-version IPV4 \
  --addresses "203.0.113.0/24"

# Rate limiting: max 2000 req/5min per IP
aws wafv2 create-web-acl \
  --name "ddos-protection" \
  --scope CLOUDFRONT \
  --default-action Allow={} \
  --rules '[{
    "Name": "IPRateLimit",
    "Priority": 1,
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
      "MetricName": "IPRateLimit"
    }
  }]'
```

### 5. Cloudflare — Configurazione Anti-DDoS

```yaml
# Cloudflare Firewall Rules (via Terraform)
resource "cloudflare_ruleset" "ddos_l7" {
  zone_id     = var.zone_id
  name        = "DDoS L7 Override"
  description = "DDoS L7 protection rules"
  kind        = "zone"
  phase       = "ddos_l7"

  rules {
    action = "execute"
    action_parameters {
      id = "4d21379b4f9f4bb088e0729962c8b3cf"
      overrides {
        rules {
          id                = "fdfdac75430c4c47a959592f0aa5e68a"
          sensitivity_level = "high"
          action            = "block"
        }
      }
    }
    expression  = "true"
    description = "Execute DDoS L7 managed ruleset"
    enabled     = true
  }
}

# Bot Management Rule
resource "cloudflare_ruleset" "bot_management" {
  zone_id = var.zone_id
  name    = "Bot Management"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules {
    action = "challenge"   # CAPTCHA challenge
    expression  = "(cf.bot_management.score lt 30) and not (cf.bot_management.verified_bot)"
    description = "Challenge low bot score"
    enabled     = true
  }
}
```

## Detection e Monitoraggio

### Segnali di un Attacco in Corso

```bash
# Traffico di rete anomalo
iftop -i eth0 -n    # Traffico in tempo reale per connessione
nethogs eth0        # Traffico per processo

# Connessioni TCP in stato SYN_RECV (SYN flood)
ss -n state syn-recv | wc -l
# Normale: < 100 | In attacco: migliaia

# Connessioni per IP (top offender)
ss -n | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn | head -20

# Saturazione CPU Nginx
top -p $(pgrep -d, nginx)

# Analisi access log — richieste per IP ultimo minuto
awk -v d="$(date -d '1 minute ago' '+%d/%b/%Y:%H:%M')" '$4 > "["d' /var/log/nginx/access.log \
  | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
```

### Alert con Prometheus + Grafana

```yaml
# alerting rules
groups:
- name: ddos
  rules:
  - alert: HighConnectionsPerIP
    expr: |
      sum by (remote_addr) (
        rate(nginx_http_requests_total[1m])
      ) > 100
    for: 1m
    annotations:
      summary: "IP {{ $labels.remote_addr }} fa {{ $value }} req/s"

  - alert: HighErrorRate
    expr: |
      rate(nginx_http_requests_total{status=~"5.."}[5m]) /
      rate(nginx_http_requests_total[5m]) > 0.1
    for: 2m
    annotations:
      summary: "Error rate > 10% — possibile attacco L7"

  - alert: BandwidthAnomaly
    expr: |
      rate(node_network_receive_bytes_total{device="eth0"}[5m]) > 1e9
    annotations:
      summary: "Traffico in entrata > 1Gbps — possibile attacco volumetrico"
```

## Best Practices

- **CDN sempre davanti**: Cloudflare, AWS CloudFront o simili assorbono attacchi volumetrici prima che raggiungano la tua infrastruttura — il costo è inferiore al downtime
- **Nascondere l'IP origine**: se l'attaccante conosce il tuo IP diretto (non quello della CDN), la CDN non protegge — usare IP filtering per accettare connessioni solo dalla CDN
- **Rate limiting a più livelli**: CDN + WAF + applicativo — ogni livello filtra una parte del traffico malevolo
- **SYN cookies sempre attivi**: costo zero, protezione immediata contro SYN flood
- **Runbook per DDoS**: documentare la procedura di risposta — non improvvisare durante l'attacco
- **Test regolari**: simulare attacchi in ambienti di staging per verificare che la protezione funzioni prima che sia necessaria

## Troubleshooting

| Sintomo | Tipo Attacco | Azione Immediata |
|---------|-------------|-----------------|
| Alta banda, pochi IP | Amplification volumetrico | BGP blackholing, contatta ISP/CDN |
| Molte conn. in SYN_RECV | SYN flood | Verificare SYN cookies attivi |
| CPU alta, poche richieste | Slowloris / SSL exhaustion | Timeout aggressivi, CAPTCHA |
| CPU media, molte richieste | HTTP flood L7 | Rate limiting, bot challenge |
| Solo un endpoint colpito | DDoS applicativo mirato | WAF rule specifica, aumentare cache |

## Relazioni

??? info "Firewall e WAF — Protezione L3-L7"
    Il WAF è il componente di filtraggio principale per attacchi L7.

    **Approfondimento →** [Firewall e WAF](firewall-waf.md)

??? info "Rate Limiting — Throttling delle API"
    Il rate limiting è la prima linea di difesa contro attacchi applicativi.

    **Approfondimento →** [Rate Limiting](../../networking/api-gateway/rate-limiting.md)

## Riferimenti

- [AWS Shield — DDoS Protection](https://aws.amazon.com/shield/)
- [Cloudflare DDoS Protection](https://www.cloudflare.com/ddos/)
- [NIST — DDoS Guidance](https://www.cisa.gov/sites/default/files/publications/understanding-and-responding-to-ddos-attacks_508c.pdf)
- [Nginx Anti-DDoS](https://www.nginx.com/blog/mitigating-ddos-attacks-with-nginx-and-nginx-plus/)
