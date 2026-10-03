---
title: "Layer 4 vs Layer 7 Load Balancing"
slug: layer4-vs-layer7
category: networking
tags: [load-balancing, layer4, layer7, tcp, http, proxy, nginx, haproxy]
search_keywords: [l4 load balancer, l7 load balancer, tcp load balancing, http load balancing, reverse proxy, content switching, connection proxying, transparency, tls termination, sticky session, x-forwarded-for, aws nlb, aws alb, nginx stream, haproxy]
parent: networking/load-balancing/_index
related: [networking/load-balancing/algoritmi, networking/load-balancing/ha-e-failover, networking/fondamentali/modello-osi, networking/api-gateway/pattern-base]
official_docs: https://nginx.org/en/docs/stream/ngx_stream_core_module.html
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# Layer 4 vs Layer 7 Load Balancing

## Panoramica

I load balancer operano a livelli diversi dello stack OSI, con implicazioni fondamentali su performance, flessibilità e capacità di routing. **Layer 4** (trasporto) bilancia basandosi su indirizzi IP e porte TCP/UDP — è trasparente e ultra-veloce ma "cieco" al contenuto. **Layer 7** (applicativo) legge il contenuto delle richieste HTTP — permette routing intelligente ma aggiunge latenza e complessità. La scelta tra i due dipende dal requisito dominante: performance bruta vs flessibilità di routing.

## Concetti Chiave

### Confronto Principale

| Aspetto | Layer 4 | Layer 7 |
|---------|---------|---------|
| Livello OSI | 4 (Transport) | 7 (Application) |
| Criteri di routing | IP, porta | Host, path, header, cookie, body |
| TLS | Passthrough o terminazione | Terminazione obbligatoria (per leggere HTTP) |
| Performance | Altissima (nessun parsing, poco stato per connessione) | Alta (costo del parsing HTTP e, se presente, della TLS) |
| Latenza aggiuntiva (ordine di grandezza) | Sub-millisecondo | Pochi ms |
| Visibilità del contenuto | Nessuna | Completa |
| Sticky session | IP Hash (approssimativo) | Cookie preciso |
| Casi d'uso | Qualsiasi TCP/UDP | HTTP, HTTPS, gRPC, WebSocket |

### Quando usare Layer 4

- **Protocolli non-HTTP**: database (MySQL, PostgreSQL, Redis), DNS, SMTP, protocolli proprietari
- **Massima performance**: gaming servers, streaming media, financial trading
- **Trasparenza**: quando il backend deve vedere l'IP del client originale — con L4 a packet forwarding (NLB, IPVS) è nativo; con L4 proxy serve il PROXY protocol
- **TLS Passthrough**: quando il backend deve fare mTLS end-to-end senza terminazione al LB

### Quando usare Layer 7

- **Routing basato su contenuto**: `/api/` → servizio API, `/static/` → CDN, `/ws/` → WebSocket server
- **Microservizi**: ogni servizio ha il suo hostname o path prefix
- **A/B testing e canary**: percentuale del traffico verso versioni diverse
- **WAF (Web Application Firewall) e sicurezza**: ispezione del payload, protezione da attacchi HTTP
- **Caching**: il LB può cacheare risposte HTTP

## Architettura / Come Funziona

### Layer 4 — TCP Proxy

```
Client                    LB L4                   Backend
  |                         |                         |
  |── TCP SYN ─────────────>|                         |
  |<── TCP SYN+ACK ─────────|                         |
  |── TCP ACK ─────────────>|                         |
  |                         |── TCP SYN ─────────────>|
  |                         |<── TCP SYN+ACK ──────────|
  |                         |── TCP ACK ─────────────>|
  |══ dati (opachi) ════════|══ dati (identici) ══════|
```

Il LB L4 crea due connessioni TCP indipendenti ma proxy-forwarda i byte in modo trasparente. Non "vede" il protocollo applicativo — che sia HTTP, MySQL o FTP è irrilevante.

!!! note "Due modalità di L4: proxy vs packet forwarding"
    Il diagramma sopra descrive un **L4 proxy** (Nginx `stream`, HAProxy `mode tcp`): termina la connessione TCP del client e ne apre una nuova verso il backend, quindi il backend vede l'**IP del LB** (serve PROXY protocol per recuperare quello del client).
    Altri L4 (AWS NLB con target di tipo `instance`, IPVS/LVS in NAT o DSR, Maglev/eBPF) fanno **packet forwarding**: inoltrano i pacchetti riscrivendo/incapsulando solo gli indirizzi, senza terminare TCP. In questo caso il backend vede l'IP originale del client ("trasparenza"), ma il percorso di ritorno deve passare dal LB (NAT) o essere gestito esplicitamente (DSR).

### Layer 7 — HTTP Proxy

```
Client                    LB L7                   Backend
  |                         |                         |
  |── HTTP Request ─────────>|                         |
  |   GET /api/users         |                         |
  |   Host: api.example.com  |── Parse HTTP ──>        |
  |                         |   Seleziona backend      |
  |                         |── HTTP Request ─────────>|
  |                         |   GET /api/users         |
  |                         |   X-Forwarded-For: <IP>  |
  |                         |<── HTTP Response ─────────|
  |<── HTTP Response ────────|                         |
```

Il LB L7 termina la connessione HTTP dal client, analizza la richiesta, sceglie il backend in base a regole L7, e stabilisce una nuova connessione verso il backend.

### TLS Termination vs Passthrough

```
# Terminazione TLS al LB (L7 standard)
Client ──[TLS]──> LB ──[HTTP cleartext]──> Backend
                  ↑ Decifratura avviene qui

# TLS Passthrough (L4 — backend vede il client direttamente)
Client ──[TLS]──> LB ──[TLS]──> Backend
                  ↑ Il LB non vede il contenuto

# TLS Re-encryption (L7 con sicurezza end-to-end)
Client ──[TLS]──> LB ──[TLS]──> Backend
                  ↑ Decifratura + re-cifratura
```

## Configurazione & Pratica

### Nginx — Layer 7 (HTTP)

```nginx
upstream api_backends {
    least_conn;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080;
}

upstream websocket_backends {
    ip_hash;  # Sticky per WebSocket
    server 10.0.0.4:8081;
    server 10.0.0.5:8081;
}

server {
    listen 443 ssl;
    http2 on;  # nginx >= 1.25.1; la forma "listen ... http2" è deprecata
    server_name api.example.com;

    # TLS termination al LB
    ssl_certificate /etc/ssl/certs/api.crt;
    ssl_certificate_key /etc/ssl/private/api.key;

    # Routing L7 basato su path
    location /api/ {
        proxy_pass http://api_backends;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /ws/ {
        proxy_pass http://websocket_backends;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static/ {
        # Backend dedicato per contenuto statico
        # (upstream static_cdn e proxy_cache_path static_cache definiti altrove)
        proxy_pass http://static_cdn;
        proxy_cache static_cache;
        proxy_cache_valid 200 1d;
    }
}
```

### Nginx — Layer 4 (TCP/UDP)

```nginx
# Modulo stream per L4 (in nginx.conf, fuori dal blocco http)
stream {
    upstream mysql_cluster {
        server db1.internal:3306;
        server db2.internal:3306;
        server db3.internal:3306;
    }

    upstream dns_servers {
        server 10.0.0.10:53;
        server 10.0.0.11:53;
    }

    # TCP Load Balancing per MySQL
    server {
        listen 3306;
        proxy_pass mysql_cluster;
        proxy_connect_timeout 1s;
        proxy_timeout 3600s;

        # Preserva IP del client al backend: il backend DEVE supportare il
        # PROXY protocol (es. MariaDB con proxy_protocol_networks, HAProxy,
        # Nginx). MySQL community NON lo supporta: rimuovere la direttiva.
        proxy_protocol on;
    }

    # UDP Load Balancing per DNS
    server {
        listen 53 udp;
        proxy_pass dns_servers;
        proxy_responses 1;  # 1 risposta per query DNS
        proxy_timeout 1s;
    }
}
```

### HAProxy — Layer 7 con content switching

```
frontend https_frontend
    bind :443 ssl crt /etc/ssl/combined.pem alpn h2,http/1.1
    mode http

    # ACL per routing L7
    acl is_api     path_beg /api/
    acl is_admin   path_beg /admin/
    acl is_static  path_beg /static/
    acl host_ws    hdr(Upgrade) -i websocket

    # Content switching
    use_backend api_pool     if is_api
    use_backend admin_pool   if is_admin
    use_backend static_pool  if is_static
    use_backend ws_pool      if host_ws
    default_backend app_pool

frontend tcp_frontend
    bind :3306
    mode tcp  # L4 per MySQL

    default_backend mysql_pool

backend api_pool
    mode http
    balance leastconn
    option httpchk GET /health
    http-check expect status 200
    server api1 10.0.0.1:8080 check inter 5s
    server api2 10.0.0.2:8080 check inter 5s

backend mysql_pool
    mode tcp
    balance roundrobin
    option mysql-check user haproxy_check
    server db1 10.0.0.10:3306 check
    server db2 10.0.0.11:3306 check backup  # Backup: usato solo se db1 è giù
```

### AWS — NLB (L4) vs ALB (L7)

```bash
# NLB — Network Load Balancer (L4)
# Casi d'uso: TCP generico, TLS passthrough, ultra-bassa latenza, static IP
aws elbv2 create-load-balancer \
  --name my-nlb \
  --type network \
  --subnets subnet-abc123

# ALB — Application Load Balancer (L7)
# Casi d'uso: HTTP/HTTPS, microservizi, WebSocket, autenticazione integrata
aws elbv2 create-load-balancer \
  --name my-alb \
  --type application \
  --subnets subnet-abc123 subnet-def456

# Regola di routing ALB basata su path
aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:... \
  --priority 10 \
  --conditions Field=path-pattern,Values='/api/*' \
  --actions Type=forward,TargetGroupArn=arn:aws:...
```

## Best Practices

- **Preferire L7** per qualsiasi traffico HTTP/HTTPS: routing più flessibile, visibility, health check applicativi
- **L4 per non-HTTP**: database, Redis, SMTP, DNS — dove non si può terminare TLS o leggere il protocollo
- **Health check applicativi** (L7): verificare `/health` con risposta 200 invece di semplice TCP connect
- **Preservare l'IP del client**: configurare `X-Forwarded-For` (L7) o `proxy_protocol` (L4) per logging e sicurezza
- **TLS Termination al LB**: semplifica la gestione dei certificati — gestione centralizzata invece che su ogni backend
- **Timeout**: configurare timeout appropriati — connessioni WebSocket necessitano timeout molto più alti di HTTP standard

## Troubleshooting

### Scenario 1 — Backend vede l'IP del LB invece del client

**Sintomo**: log applicativi e rate limiting mostrano sempre l'IP (o `127.0.0.1`) del load balancer.

**Causa**: il LB (L7 o L4) apre una nuova connessione verso il backend, quindi l'IP sorgente è il suo. L'IP originale viaggia solo se esplicitamente propagato: header `X-Forwarded-For` (L7) o PROXY protocol (L4, header binario/testuale prima dei dati).

**Soluzione**: L7 → impostare gli header; L4 → abilitare `proxy_protocol` sul LB **e** farlo accettare al backend (altrimenti il backend riceve byte spuri e rifiuta la connessione).

```bash
# Verifica header ricevuti dal backend
curl -s -H "X-Forwarded-For: 203.0.113.9" https://api.example.com/debug/headers
# Verifica PROXY protocol (nginx backend: listen 80 proxy_protocol;)
curl -s --haproxy-protocol http://10.0.0.1:80/
```

### Scenario 2 — Handshake TLS fallisce verso il database

**Sintomo**: `SSL routines:ssl3_get_record:wrong version number` o handshake timeout connettendosi al DB tramite LB.

**Causa**: MySQL/PostgreSQL negoziano TLS *dentro* il protocollo applicativo (STARTTLS-like). Un LB che tenta di terminare TLS (L7) non capisce questo scambio e lo corrompe.

**Soluzione**: usare L4 puro (`mode tcp` / `stream`) senza terminazione, lasciando che client e DB negozino TLS end-to-end.

```bash
openssl s_client -starttls postgres -connect lb.example.com:5432
mysql -h lb.example.com --ssl-mode=REQUIRED -u app -p
```

### Scenario 3 — Routing `/api/` non applicato

**Sintomo**: richieste a `/api/...` finiscono nel backend di default o rispondono 404.

**Causa**: ordine/ACL errati (in HAProxy `use_backend` è valutato in ordine), `Host` header diverso da `server_name`, o `proxy_pass` con/senza slash finale che riscrive il path.

**Soluzione**: testare con `Host` esplicito e validare la configurazione prima del reload.

```bash
curl -v -H "Host: api.example.com" https://10.0.0.1/api/users --resolve api.example.com:443:10.0.0.1
nginx -t && nginx -s reload
haproxy -c -f /etc/haproxy/haproxy.cfg
```

### Scenario 4 — WebSocket o connessioni lunghe cadono dopo 60s

**Sintomo**: la connessione si chiude esattamente dopo ~60s di inattività (`1006 abnormal closure`, `504`).

**Causa**: timeout di idle del LB (`proxy_read_timeout` Nginx = 60s di default; ALB idle timeout = 60s; NLB chiude i flussi TCP inattivi dopo 350s) più basso dell'intervallo tra i messaggi.

**Soluzione**: alzare il timeout e/o inviare ping/keepalive applicativi più frequenti del timeout.

```bash
# Nginx: location /ws/ { proxy_read_timeout 3600s; }
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn <alb-arn> \
  --attributes Key=idle_timeout.timeout_seconds,Value=3600
```

## Relazioni

??? info "Algoritmi di Load Balancing"
    Come vengono selezionati i backend in Round Robin, Least Connections, ecc.

    **Approfondimento →** [Algoritmi](algoritmi.md)

??? info "Alta Disponibilità e Failover"
    Come evitare che il load balancer stesso sia un single point of failure.

    **Approfondimento →** [HA e Failover](ha-e-failover.md)

## Riferimenti

- [Nginx Load Balancing](https://nginx.org/en/docs/http/load_balancing.html)
- [HAProxy Documentation](https://www.haproxy.org/download/2.8/doc/configuration.txt)
- [AWS ALB vs NLB vs CLB](https://aws.amazon.com/elasticloadbalancing/features/)
