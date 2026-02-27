---
title: "Layer 4 vs Layer 7 Load Balancing"
slug: layer4-vs-layer7
category: networking
tags: [load-balancing, layer4, layer7, tcp, http, proxy, nginx, haproxy]
search_keywords: [l4 load balancer, l7 load balancer, tcp load balancing, http load balancing, reverse proxy, content switching, connection proxying, transparency, tls termination, sticky session, x-forwarded-for, aws nlb, aws alb, nginx stream, haproxy]
parent: networking/load-balancing/_index
related: [networking/load-balancing/algoritmi, networking/load-balancing/ha-e-failover, networking/fondamentali/modello-osi, networking/api-gateway/pattern-base]
official_docs: https://nginx.org/en/docs/stream/ngx_stream_core_module.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
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
| Performance | Altissima (~1M+ conn/s) | Alta (limiti sul parsing HTTP) |
| Latenza aggiuntiva | Minima (<0.1ms) | Bassa (1-5ms) |
| Visibilità del contenuto | Nessuna | Completa |
| Sticky session | IP Hash (approssimativo) | Cookie preciso |
| Casi d'uso | Qualsiasi TCP/UDP | HTTP, HTTPS, gRPC, WebSocket |

### Quando usare Layer 4

- **Protocolli non-HTTP**: database (MySQL, PostgreSQL, Redis), DNS, SMTP, protocolli proprietari
- **Massima performance**: gaming servers, streaming media, financial trading
- **Trasparenza totale**: quando il server backend deve vedere l'IP del client originale
- **TLS Passthrough**: quando il backend deve fare mTLS end-to-end senza terminazione al LB

### Quando usare Layer 7

- **Routing basato su contenuto**: `/api/` → servizio API, `/static/` → CDN, `/ws/` → WebSocket server
- **Microservizi**: ogni servizio ha il suo hostname o path prefix
- **A/B testing e canary**: percentuale del traffico verso versioni diverse
- **WAF e sicurezza**: ispezione del payload, protezione da attacchi HTTP
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
    listen 443 ssl http2;
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

        # Preserva IP del client al backend
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

| Sintomo | Layer | Causa | Soluzione |
|---------|-------|-------|-----------|
| Backend vede `127.0.0.1` come IP client | L7 | `X-Forwarded-For` non configurato | Aggiungere `proxy_set_header X-Forwarded-For` |
| TLS handshake fallisce con database | L4 | Il LB non supporta TLS applicativo del DB | Usare TLS passthrough o L4 puro |
| Routing non funziona per `/api/` | L7 | Path matching errato | Verificare con `curl -H "Host: ..."` |
| WebSocket disconnesso dopo 60s | L7 | Timeout del LB | Aumentare `proxy_read_timeout` |
| Distribuzione non uniforme | L4/L7 | Algoritmo non ottimale | Passare da Round Robin a Least Connections |

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
