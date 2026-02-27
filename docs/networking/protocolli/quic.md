---
title: "QUIC"
slug: quic
category: networking
tags: [quic, udp, http3, performance, protocolli, google, latenza]
search_keywords: [quick udp internet connections, quic protocol, http/3, udp, 0-rtt, head of line blocking, multiplexing, connection migration, packet loss recovery, google chrome, cloudflare]
parent: networking/protocolli/_index
related: [networking/protocolli/http2-http3, networking/protocolli/tcp-udp, networking/fondamentali/tcpip]
official_docs: https://www.rfc-editor.org/rfc/rfc9000
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# QUIC

## Panoramica

QUIC (RFC 9000, 2021) è un protocollo di trasporto sviluppato da Google e standardizzato dall'IETF come base per HTTP/3. Sostituisce la stack TCP+TLS per le comunicazioni web, operando direttamente su **UDP** e incorporando controllo della congestione, affidabilità e crittografia TLS 1.3 in un unico livello. L'obiettivo è ridurre la latenza eliminando le debolezze strutturali di TCP: head-of-line blocking, handshake lento e impossibilità di migrare le connessioni.

QUIC è già ampiamente deployato: Google (YouTube, Search, Gmail), Cloudflare e la maggior parte delle CDN lo usano in produzione. I browser moderni supportano QUIC/HTTP/3 by default.

## Concetti Chiave

### Perché QUIC invece di TCP?

| Problema TCP | Soluzione QUIC |
|-------------|----------------|
| 3-way handshake (1.5 RTT) + TLS handshake (1-2 RTT) | Connessione + TLS in 1-RTT (0-RTT per sessioni note) |
| HOL blocking: un pacchetto perso blocca tutti gli stream | Stream indipendenti: perdita su uno stream non blocca gli altri |
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

QUIC implementa algoritmi di controllo della congestione equivalenti a TCP (CUBIC, BBR) ma in user space. L'ACK mechanism di QUIC è più preciso di TCP grazie a:
- Packet number monotonicamente crescenti (no ambiguità nei retransmit)
- Timestamp precisi per calcolo RTT
- Selective ACK nativo (no workaround come TCP SACK)

## Configurazione & Pratica

### Abilitare HTTP/3 con Nginx

```nginx
# Richiede Nginx 1.25+ compilato con --with-http_v3_module
server {
    listen 443 ssl;
    listen 443 quic reuseport;  # Abilita QUIC/HTTP/3 su UDP

    http2 on;
    http3 on;

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
# curl con supporto HTTP/3 (curl 7.66+)
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

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| QUIC non negoziato | Firewall blocca UDP 443 | Aprire porta 443/UDP |
| 0-RTT non funziona | Server non supporta early data | Abilitare `ssl_early_data on` |
| Prestazioni peggiori del previsto | Rete con alto packet loss e no QUIC tuning | Verificare configurazione BBR e buffer UDP |
| Client non upgrada a HTTP/3 | Alt-Svc header mancante | Aggiungere `Alt-Svc: h3=":443"; ma=86400` |

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
- [Cloudflare — QUIC Blog](https://blog.cloudflare.com/quic-v1-2/)
- [HTTP/3 Explained](https://http3-explained.haxx.se/)
