---
title: "QUIC"
slug: quic
category: networking
tags: [quic, udp, http3, performance, protocolli, google, latenza]
search_keywords: [quick udp internet connections, quic protocol, http/3, udp, 0-rtt, head of line blocking, multiplexing, connection migration, packet loss recovery, google chrome, cloudflare]
parent: networking/protocolli/_index
related: [networking/protocolli/http2-http3, networking/protocolli/tcp-udp, networking/fondamentali/tcpip, networking/fondamentali/tls-ssl-basics]
official_docs: https://www.rfc-editor.org/rfc/rfc9000
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# QUIC

## Panoramica

QUIC (RFC 9000, 2021) è un protocollo di trasporto sviluppato da Google e standardizzato dall'IETF come base per HTTP/3. Sostituisce la stack TCP+TLS per le comunicazioni web, operando direttamente su **UDP** e incorporando controllo della congestione, affidabilità e crittografia TLS 1.3 in un unico livello. L'obiettivo è ridurre la latenza eliminando le debolezze strutturali di TCP: head-of-line blocking, handshake lento e impossibilità di migrare le connessioni.

QUIC è già ampiamente deployato: Google (YouTube, Search, Gmail), Cloudflare e la maggior parte delle CDN lo usano in produzione. I browser moderni supportano QUIC/HTTP/3 by default.

## Concetti Chiave

### Perché QUIC invece di TCP?

| Problema TCP | Soluzione QUIC |
|-------------|----------------|
| 3-way handshake (1.5 RTT, round-trip time = andata e ritorno) + TLS handshake (1-2 RTT) | Connessione + TLS in 1-RTT (0-RTT per sessioni note) |
| HOL (head-of-line) blocking: un pacchetto perso blocca tutti gli stream | Stream indipendenti: perdita su uno stream non blocca gli altri |
| Connection migration impossibile (basata su IP:porta) | Connection ID: cambia IP/rete senza riconnettersi |
| Implementazione nel kernel OS | Implementazione in user space: aggiornabile indipendentemente |
| Nessuna crittografia nativa | TLS 1.3 integrato e obbligatorio |

### Stream Multiplexing

QUIC permette di inviare più stream indipendenti su una singola connessione UDP. A differenza di HTTP/2 su TCP, la perdita di un pacchetto impatta solo lo stream a cui appartiene, non l'intera connessione.

```
Connessione QUIC
├── Stream 1: GET /index.html     ← perdita pacchetto qui
├── Stream 2: GET /style.css      ← NON impattato
├── Stream 3: GET /app.js         ← NON impattato
└── Stream 4: GET /logo.png       ← NON impattato
```

Confronto con TCP+HTTP/2:
```
Connessione TCP
└── Tutti i frame HTTP/2 multiplexati
    └── Se un pacchetto TCP è perso → TUTTO aspetta (HOL blocking TCP)
```

### 0-RTT Connection Establishment

Per sessioni riprese con un server già noto, QUIC può iniziare a inviare dati **prima** che la connessione sia completamente stabilita:

```
Prima connessione (1-RTT):
Client → Initial (ClientHello)     ──>
       <── Initial (ServerHello)
       <── Handshake (Certificate)
Client → Handshake (Finished)      ──>
       <── 1-RTT data

Sessione ripresa (0-RTT):
Client → Initial + 0-RTT data     ──>   ← dati subito!
       <── Initial + 1-RTT data
```

!!! warning "Rischio Replay in 0-RTT"
    I dati inviati in modalità 0-RTT possono essere soggetti ad attacchi replay. Usare 0-RTT solo per operazioni idempotenti (GET, non POST con side effects).

### Connection Migration

A differenza di TCP, le connessioni QUIC sono identificate da un **Connection ID** (non dall'IP:porta). Quando un client cambia rete (WiFi → 4G), può continuare la sessione senza riconnettersi.

## Architettura / Come Funziona

### Stack di rete

```
Applicazione (HTTP/3)
        │
      QUIC
        │  ← Crittografia TLS 1.3 integrata
      UDP
        │
       IP
        │
   Ethernet/WiFi
```

### Formato Pacchetto QUIC

```
┌─────────────────────────────────────┐
│ Header (Long o Short)               │
│  ├── Connection ID                  │
│  ├── Packet Number                  │
│  └── Version (solo Long header)     │
├─────────────────────────────────────┤
│ Payload (cifrato con TLS 1.3)       │
│  ├── STREAM frame (dati applicativi)│
│  ├── ACK frame (acknowledgment)     │
│  ├── MAX_DATA frame (flow control)  │
│  └── CONNECTION_CLOSE              │
└─────────────────────────────────────┘
```

### Controllo della Congestione

QUIC implementa algoritmi di controllo della congestione equivalenti a TCP (NewReno come baseline in RFC 9002, più CUBIC e BBR) ma in user space: ogni libreria può sceglierli e aggiornarli senza toccare il kernel. Il loss recovery (RFC 9002) è più preciso di TCP grazie a:
- Packet number monotonicamente crescenti: un pacchetto ritrasmesso ha un nuovo number, quindi nessuna ambiguità tra originale e retransmit nel calcolo RTT
- Campo `ACK Delay` nell'ACK frame: il ricevente dichiara quanto ha trattenuto l'ACK, così il mittente sottrae il ritardo dal campione RTT
- Range di ACK (equivalente di SACK) sempre presenti nel frame, non un'opzione negoziata

### Perché UDP e perché cifrato

QUIC usa UDP per **ossification**: i middlebox (NAT, firewall) di Internet ispezionano e talvolta bloccano header TCP non standard, rendendo impossibile evolvere TCP. Sopra UDP, QUIC cifra anche quasi tutti i metadati di trasporto (packet number, frame): i middlebox vedono solo pochi campi invarianti (RFC 8999) e non possono più dipendere da dettagli che bloccherebbero future evoluzioni (esiste già QUIC v2, RFC 9369, per evitare ossification della versione).

### Connection ID e load balancer

Poiché la connessione sopravvive al cambio di IP:porta, un load balancer L4 che instrada per 4-tupla manderebbe i pacchetti migrati a un backend sbagliato. Servono LB *QUIC-aware* che instradano sul Connection ID (es. QUIC-LB, draft IETF, o eBPF/Katran in ambienti hyperscale). Senza, la migration funziona solo con un singolo server o con hashing consistente sul CID.

## Configurazione & Pratica

### Abilitare HTTP/3 con Nginx

```nginx
# Richiede Nginx 1.25+ compilato con --with-http_v3_module
server {
    listen 443 ssl;
    listen 443 quic reuseport;  # Abilita QUIC/HTTP/3 su UDP

    http2 on;
    http3 on;
    quic_retry on;  # address validation: mitiga amplification/spoofing

    ssl_certificate     /etc/ssl/certs/example.crt;
    ssl_certificate_key /etc/ssl/private/example.key;

    # Necessario per QUIC
    ssl_protocols TLSv1.3;
    ssl_early_data on;  # Abilita 0-RTT

    # Annuncia supporto HTTP/3 al browser
    add_header Alt-Svc 'h3=":443"; ma=86400';

    location / {
        root /var/www/html;
    }
}
```

### Verifica supporto QUIC

```bash
# curl compilato con backend HTTP/3 (ngtcp2+nghttp3 o quiche); verificare con: curl -V | grep HTTP3
# --http3 prova h3 con fallback; --http3-only forza solo h3
curl --http3 https://example.com -I

# Output atteso:
# HTTP/3 200
# content-type: text/html

# Verifica con browser: Chrome DevTools → Network → Protocol → h3

# Test con quiche (tool Cloudflare)
quiche-client https://example.com

# Verifica header Alt-Svc
curl -I https://example.com | grep alt-svc
```

### Configurazione HAProxy con QUIC

```
# Richiede HAProxy 2.6+ (stabile dalla 2.8) e una libreria TLS con API QUIC (OpenSSL 3.5+, quictls, AWS-LC)
frontend https_frontend
    bind :443 ssl crt /etc/ssl/combined.pem alpn h2,http/1.1
    bind quic4@:443 ssl crt /etc/ssl/combined.pem alpn h3

    http-response set-header alt-svc 'h3=":443"; ma=86400'

    default_backend app_servers

backend app_servers
    server app1 10.0.0.1:8080 check
    server app2 10.0.0.2:8080 check
```

## Best Practices

- **Abilitare HTTP/3 in aggiunta a HTTP/2**: i browser negoziano automaticamente la versione migliore
- **Alt-Svc header**: necessario per annunciare il supporto QUIC ai client
- **UDP firewall**: assicurarsi che la porta 443/UDP sia aperta — molti firewall bloccano UDP per default
- **0-RTT solo per idempotenti**: non usare 0-RTT per operazioni con side effects
- **Monitorare metriche separatamente**: HTTP/3 e HTTP/2 hanno caratteristiche diverse; separare i dashboard
- **Fallback a TCP**: i client che non supportano QUIC tornano automaticamente a TCP — non è necessario configurarlo

## Troubleshooting

### Scenario 1 — QUIC non negoziato, traffico sempre su TCP

**Sintomo**: DevTools mostra `h2` invece di `h3`; `curl --http3` va in timeout.

**Causa**: firewall/security group blocca UDP 443. QUIC viaggia su UDP, ma molte regole aprono solo TCP 443.

**Soluzione**: aprire 443/UDP e verificare che arrivi al server.

```bash
# Server: il listener UDP esiste?
ss -ulnp | grep :443

# Cattura pacchetti QUIC in ingresso
sudo tcpdump -ni any udp port 443 -c 10

# Security group AWS: aggiungere regola UDP 443
aws ec2 authorize-security-group-ingress --group-id sg-0123 --protocol udp --port 443 --cidr 0.0.0.0/0
```

### Scenario 2 — Il client non passa mai a HTTP/3

**Sintomo**: la prima richiesta e le successive restano su HTTP/2, pur con QUIC attivo.

**Causa**: il browser scopre HTTP/3 tramite header `Alt-Svc` ricevuto su HTTP/1.1 o HTTP/2 (la prima visita resta quindi su TCP), oppure in anticipo via record DNS `HTTPS` (SVCB, RFC 9460) con `alpn=h3`; se mancano (o un proxy rimuove l'header) non tenta QUIC.

**Soluzione**: aggiungere l'header e verificare che arrivi al client.

```bash
curl -sI https://example.com | grep -i alt-svc
# atteso: alt-svc: h3=":443"; ma=86400
```

### Scenario 3 — 0-RTT non funziona

**Sintomo**: ogni riconnessione richiede 1-RTT completo, nessun early data.

**Causa**: il server non accetta early data, oppure il client non ha un session ticket valido (scaduto o mai ricevuto).

**Soluzione**: abilitare early data lato server e, se dietro proxy, inoltrare l'header `Early-Data` al backend.

```nginx
ssl_early_data on;
proxy_set_header Early-Data $ssl_early_data;
```

### Scenario 4 — Prestazioni peggiori di TCP

**Sintomo**: throughput più basso o CPU alta rispetto a HTTP/2.

**Causa**: QUIC gira in user space (costo CPU per pacchetto più alto, niente offload del kernel) e i buffer UDP di default sono piccoli, causando drop.

**Soluzione**: aumentare i buffer socket UDP, valutare GSO/offload UDP e controllare i drop.

```bash
# Buffer UDP (valori in byte)
sudo sysctl -w net.core.rmem_max=7500000 net.core.wmem_max=7500000

# Drop UDP per buffer pieno
nstat -az UdpRcvbufErrors
```

## Relazioni

??? info "HTTP/3 — Protocollo applicativo su QUIC"
    QUIC è il trasporto su cui HTTP/3 opera.

    **Approfondimento →** [HTTP/2 e HTTP/3](http2-http3.md)

??? info "TCP/UDP — Confronto con i protocolli tradizionali"
    Capire TCP e UDP aiuta a comprendere le scelte di design di QUIC.

    **Approfondimento →** [TCP e UDP](tcp-udp.md)

## Riferimenti

- [RFC 9000 — QUIC Transport Protocol](https://www.rfc-editor.org/rfc/rfc9000)
- [RFC 9114 — HTTP/3](https://www.rfc-editor.org/rfc/rfc9114)
- [RFC 9001 — Using TLS to Secure QUIC](https://www.rfc-editor.org/rfc/rfc9001)
- [RFC 9002 — QUIC Loss Detection and Congestion Control](https://www.rfc-editor.org/rfc/rfc9002)
- [RFC 9369 — QUIC Version 2](https://www.rfc-editor.org/rfc/rfc9369)
- [HTTP/3 Explained](https://http3-explained.haxx.se/)
