---
title: "NGINX e HAProxy"
slug: nginx-haproxy
category: networking
tags: [nginx, haproxy, load-balancer, reverse-proxy, tls-termination, health-check, proxy-protocol, zero-downtime]
search_keywords: [nginx, haproxy, reverse proxy, load balancer, upstream, backend, frontend, proxy_pass, least_conn, stick-table, stick table, health check, httpchk, PROXY protocol, runtime API, admin socket, socat, drain, graceful reload, master-worker, stub_status, stats page, haproxy exporter, nginx exporter, limit_req, rate limiting, TLS termination, OCSP stapling, split_clients, canary, X-Forwarded-For, 502 bad gateway, 504 gateway timeout, worker_connections, keepalive upstream, conntrack, L4 L7 proxy, ACL]
parent: networking/load-balancing/_index
related: [networking/load-balancing/algoritmi, networking/load-balancing/layer4-vs-layer7, networking/load-balancing/ha-e-failover, networking/kubernetes/ingress, cloud/aws/networking/elastic-load-balancing, networking/fondamentali/tls-ssl-basics]
official_docs: https://docs.haproxy.org/
status: reviewed
difficulty: intermediate
last_updated: 2026-09-26
last_verified: 2026-09-27
---

# NGINX e HAProxy

## Panoramica

**NGINX** e **HAProxy** sono i due proxy/load balancer open source più diffusi. NGINX nasce come web server ad alte prestazioni ed è oggi usato soprattutto come **reverse proxy + web server + cache** (static file, TLS termination, routing L7). HAProxy nasce come **load balancer puro** L4/L7: meno funzioni "web", ma health check più ricchi, osservabilità nativa, stick-table, runtime API e controllo fine dei server backend.

Entrambi sono event-driven (nessun thread per connessione), gestiscono decine di migliaia di connessioni concorrenti per nodo e sono la base di molti ingress controller Kubernetes e di appliance commerciali. Vanno affiancati a un meccanismo di HA (VIP con keepalived, anycast, LB cloud davanti): vedi [Alta Disponibilità e Failover](ha-e-failover.md).

**Quando NON usarli:** se serve solo un LB gestito su cloud, [Elastic Load Balancing](../../cloud/aws/networking/elastic-load-balancing.md) evita l'operatività; se serve mesh con mTLS e telemetria per servizio, valutare [Envoy](../service-mesh/envoy.md).

## Concetti Chiave

### Quale scegliere

| Esigenza | NGINX | HAProxy |
|---|---|---|
| Servire file statici / cache | Sì (nativo) | No |
| Reverse proxy HTTP con rewrite, auth_request, FastCGI/uWSGI | Ottimo | Limitato |
| LB TCP/UDP generico (DB, MQTT, SMTP) | `stream` module | Ottimo (`mode tcp`) |
| Health check attivi HTTP/TCP | Solo in NGINX Plus (open source: passivi) | Nativi, configurabili (`inter/fall/rise`) |
| Stick-table, rate limit per chiave, ACL complesse | `limit_req`, `map` | Stick-table native, molto flessibili |
| Runtime API (drain, enable/disable server senza reload) | Solo Plus / moduli | Nativa (admin socket) |
| Metriche | `stub_status` (minimali) + exporter | Stats page + endpoint Prometheus nativo |

Regola pratica: **NGINX davanti all'applicazione** (TLS, static, routing), **HAProxy davanti a una flotta** di backend dove servono health check, drain e osservabilità. Molte architetture usano entrambi: HAProxy L4/L7 in edge, NGINX sui nodi applicativi.

!!! note "L4 vs L7"
    `mode tcp` in HAProxy e il blocco `stream {}` di NGINX operano a L4 (nessuna ispezione HTTP, TLS passthrough). `mode http` e `http {}` operano a L7. Dettagli in [Layer 4 vs Layer 7](layer4-vs-layer7.md).

### Terminologia

| NGINX | HAProxy | Significato |
|---|---|---|
| `server {}` / `listen` | `frontend` | Punto di ingresso (porta, TLS, regole) |
| `upstream {}` | `backend` | Pool di server di destinazione |
| `location {}` + `map` | `acl` + `use_backend` | Routing per path/host/header |
| `proxy_pass` | `default_backend` | Inoltro verso il pool |

## Architettura / Come Funziona

### Modello di processo

- **NGINX**: un processo *master* (legge config, gestisce segnali) + N *worker* (`worker_processes auto`), ciascuno con un event loop `epoll` che gestisce migliaia di connessioni. Il limite è `worker_connections` × `worker_processes` (ogni richiesta proxata usa **2 connessioni**: client e upstream).
- **HAProxy**: modello *master-worker* (`master-worker` / `-W`): il master gestisce i reload, i worker eseguono il traffico con thread multipli (`nbthread`). Il reload avvia un nuovo worker e lascia terminare i vecchi quando le connessioni si chiudono.

### Flusso di una richiesta L7

```
Client ──TLS──► [frontend: ACL, rate limit, header] ──► [backend: algoritmo + health]
                                                             │  keepalive pool
                                                             ▼
                                                        Server app
```

1. Il client apre TCP + TLS verso il proxy (TLS termination).
2. Il proxy applica regole (ACL/map, limiti, rewrite) e sceglie il backend.
3. L'algoritmo ([Algoritmi](algoritmi.md)) sceglie il server tra quelli *healthy*.
4. Il proxy riusa una connessione **keepalive** verso l'upstream, se disponibile, altrimenti ne apre una nuova.
5. La risposta torna al client; log e metriche vengono aggiornati.

### Health check

- **Passivi** (NGINX open source): `max_fails` / `fail_timeout` marcano il server come down dopo errori reali sul traffico di produzione: il client che incontra l'errore lo paga.
- **Attivi** (HAProxy): sonde periodiche indipendenti dal traffico; un server passa a DOWN dopo `fall` fallimenti e torna UP dopo `rise` successi.

## Configurazione & Pratica

### NGINX: reverse proxy con upstream

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 16384;   # x2 per richiesta proxata (client + upstream)
    multi_accept on;
}

http {
    # Mappa per preservare l'header Connection con upgrade WebSocket
    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }

    upstream app_backend {
        least_conn;                         # oppure: hash $request_uri consistent;
        server 10.0.1.11:8080 max_fails=3 fail_timeout=10s;
        server 10.0.1.12:8080 max_fails=3 fail_timeout=10s;
        server 10.0.1.13:8080 backup;       # usato solo se gli altri sono down
        keepalive 64;                       # pool di connessioni idle verso upstream
        keepalive_requests 1000;
        keepalive_timeout 60s;
    }

    server {
        listen 80;
        server_name app.example.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        http2 on;
        server_name app.example.com;

        location / {
            proxy_pass http://app_backend;

            # keepalive verso upstream richiede HTTP/1.1 e Connection vuoto
            proxy_http_version 1.1;
            proxy_set_header Connection "";

            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_connect_timeout 3s;
            proxy_send_timeout    30s;
            proxy_read_timeout    60s;

            proxy_next_upstream error timeout http_502 http_503;
            proxy_next_upstream_tries 2;

            proxy_buffering on;             # off per streaming/SSE
            proxy_buffers 16 16k;
        }

        location /ws/ {
            proxy_pass http://app_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade    $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 3600s;
        }
    }
}
```

!!! warning "Keepalive verso upstream"
    Senza `proxy_http_version 1.1` e `proxy_set_header Connection ""` la direttiva `keepalive` **non ha effetto**: NGINX apre e chiude una connessione TCP per ogni richiesta, esaurendo porte effimere (`TIME_WAIT`) sotto carico.

### NGINX: TLS termination, rate limit e canary

```nginx
http {
    # Rate limit: 10 req/s per IP, burst 20
    limit_req_zone $binary_remote_addr zone=perip:10m rate=10r/s;
    limit_conn_zone $binary_remote_addr zone=connperip:10m;

    # Canary: 10% del traffico verso il pool canary, deterministico per IP
    split_clients "${remote_addr}" $pool {
        10%  app_canary;
        *    app_backend;
    }

    upstream app_canary { server 10.0.2.11:8080; }

    server {
        listen 443 ssl;
        server_name app.example.com;

        ssl_certificate     /etc/ssl/app.example.com.fullchain.pem;
        ssl_certificate_key /etc/ssl/app.example.com.key;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers off;
        ssl_session_cache   shared:SSL:20m;
        ssl_session_timeout 1d;
        ssl_session_tickets off;

        # OCSP stapling
        ssl_stapling on;
        ssl_stapling_verify on;
        ssl_trusted_certificate /etc/ssl/chain.pem;
        resolver 1.1.1.1 valid=300s;

        add_header Strict-Transport-Security "max-age=63072000" always;

        location /api/ {
            limit_req zone=perip burst=20 nodelay;
            limit_conn connperip 50;
            limit_req_status 429;
            proxy_pass http://$pool;     # variabile: risoluzione tramite upstream nominato
        }
    }
}
```

Alternativa per canary basato su header: `map $http_x_canary $pool { "1" app_canary; default app_backend; }`.

### NGINX: LB TCP (stream)

```nginx
stream {
    upstream postgres_ro {
        least_conn;
        server 10.0.3.11:5432 max_fails=2 fail_timeout=5s;
        server 10.0.3.12:5432 max_fails=2 fail_timeout=5s;
    }
    server {
        listen 5433;
        proxy_pass postgres_ro;
        proxy_connect_timeout 2s;
        proxy_timeout 10m;
    }
}
```

### HAProxy: frontend/backend con health check

```haproxy
# /etc/haproxy/haproxy.cfg
global
    log /dev/log local0
    maxconn 50000
    nbthread 4
    stats socket /run/haproxy/admin.sock mode 660 level admin expose-fd listeners
    ssl-default-bind-options ssl-min-ver TLSv1.2

defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    option  forwardfor                # aggiunge X-Forwarded-For
    timeout connect 3s
    timeout client  30s
    timeout server  60s
    timeout http-request 10s
    retries 2
    option redispatch

frontend fe_https
    bind :443 ssl crt /etc/haproxy/certs/app.pem alpn h2,http/1.1
    bind :80
    http-request redirect scheme https unless { ssl_fc }
    http-request set-header X-Forwarded-Proto https if { ssl_fc }

    acl is_api  path_beg /api/
    acl is_ws   hdr(Upgrade) -i websocket
    use_backend be_ws  if is_ws
    use_backend be_api if is_api
    default_backend be_web

backend be_api
    balance leastconn
    option httpchk GET /healthz
    http-check expect status 200
    default-server check inter 2s fall 3 rise 2 slowstart 30s maxconn 500
    server api1 10.0.1.11:8080
    server api2 10.0.1.12:8080
    server api3 10.0.1.13:8080 backup

backend be_web
    balance roundrobin
    cookie SRV insert indirect nocache httponly secure
    option httpchk GET /
    server web1 10.0.4.11:80 check cookie w1
    server web2 10.0.4.12:80 check cookie w2

backend be_ws
    balance source
    timeout tunnel 1h
    server ws1 10.0.5.11:8080 check
```

### HAProxy: stick-table, rate limit e TCP mode

```haproxy
frontend fe_public
    bind :443 ssl crt /etc/haproxy/certs/app.pem
    # Tabella per IP: contatore richieste ultimi 10s
    stick-table type ip size 1m expire 10m store http_req_rate(10s),conn_cur
    http-request track-sc0 src
    http-request deny deny_status 429 if { sc_http_req_rate(0) gt 100 }
    default_backend be_web

# LB TCP con PROXY protocol verso il server (mantiene l'IP client)
listen db_ro
    bind :5433
    mode tcp
    balance leastconn
    option tcp-check
    server pg1 10.0.3.11:5432 check inter 3s fall 2 rise 2 send-proxy-v2
    server pg2 10.0.3.12:5432 check inter 3s fall 2 rise 2 send-proxy-v2

# Ricevere PROXY protocol da un LB a monte (es. NLB, altro HAProxy)
frontend fe_behind_lb
    bind :8443 accept-proxy ssl crt /etc/haproxy/certs/app.pem
    default_backend be_web
```

!!! warning "PROXY protocol"
    Il PROXY protocol va abilitato **su entrambi i lati**: se il backend non lo aspetta, vede byte spuri e chiude la connessione; se il proxy non lo invia ma il backend lo richiede, la connessione si blocca. Accettarlo solo da IP fidati (`accept-proxy` su listener non esposti pubblicamente), altrimenti un client può falsificare il proprio IP.

### HAProxy: runtime API e drain di un server

```bash
# Stato dei server del backend
echo "show servers state be_api" | socat stdio /run/haproxy/admin.sock

# Drain: nessuna nuova connessione (sessioni persistenti escluse), quelle in corso terminano
echo "set server be_api/api1 state drain" | socat stdio /run/haproxy/admin.sock

# Attendere che le sessioni si azzerino
echo "show stat" | socat stdio /run/haproxy/admin.sock | cut -d, -f1,2,5 | grep api1

# Manutenzione completa, poi riattivazione
echo "set server be_api/api1 state maint" | socat stdio /run/haproxy/admin.sock
echo "set server be_api/api1 state ready" | socat stdio /run/haproxy/admin.sock

# Cambiare peso a caldo (canary progressivo)
echo "set server be_api/api2 weight 10" | socat stdio /run/haproxy/admin.sock
```

!!! tip "Deploy senza downtime"
    Sequenza tipica: `drain` → attesa `scur=0` → deploy → health check verde (`rise` + `slowstart`) → `ready`. Automatizzabile con Ansible o script di deploy; le modifiche via socket non persistono al reload, quindi vanno riflesse nel file di config.

### Reload senza downtime

```bash
# NGINX: verifica la config, poi reload graceful (nuovi worker, i vecchi terminano le richieste in corso)
nginx -t && nginx -s reload
# oppure
systemctl reload nginx

# HAProxy: verifica e reload (master-worker: il master avvia i nuovi worker)
haproxy -c -f /etc/haproxy/haproxy.cfg && systemctl reload haproxy

# HAProxy senza systemd: passaggio dei listener al vecchio processo
haproxy -f /etc/haproxy/haproxy.cfg -sf $(cat /run/haproxy.pid)
```

Sui vecchi worker HAProxy con connessioni lunghe (WebSocket, TCP) impostare `hard-stop-after 30m` in `global` per evitare processi zombie accumulati dopo reload frequenti.

### Logging e metriche

```nginx
# NGINX: stub_status protetto, solo da localhost/rete di monitoraggio
server {
    listen 127.0.0.1:8081;
    location /nginx_status {
        stub_status;
        allow 127.0.0.1;
        deny all;
    }
}

log_format main '$remote_addr "$request" $status $body_bytes_sent '
                'rt=$request_time uct=$upstream_connect_time urt=$upstream_response_time '
                'ua="$upstream_addr" us=$upstream_status';
access_log /var/log/nginx/access.log main;
```

```haproxy
# HAProxy: stats page + endpoint Prometheus nativo (>= 2.0)
frontend stats
    bind 127.0.0.1:8404
    http-request use-service prometheus-exporter if { path /metrics }
    stats enable
    stats uri /stats
    stats refresh 10s
```

Per NGINX si usa `nginx-prometheus-exporter` (legge `stub_status`); per HAProxy l'endpoint nativo è preferibile all'exporter separato. Le metriche vanno raccolte con [Prometheus](../../monitoring/tools/prometheus.md): metriche chiave sono richieste/s, `5xx` per backend, `scur`/`qcur` (sessioni e code), `upstream_response_time` e server in DOWN.

## Best Practices

- **Timeout espliciti** su ogni hop (`connect`, `send/read`, `client`, `server`): i default raramente corrispondono al comportamento voluto.
- **Keepalive verso upstream** sempre attivo: riduce latenza e `TIME_WAIT`; dimensionare il pool sul numero di worker e sul carico.
- **Health check applicativi** (`/healthz` che verifica dipendenze critiche) invece di semplici check TCP; evitare che un check "profondo" causi cascading failure (non interrogare DB pesanti ogni 2 s da 20 LB).
- **`slowstart`** (HAProxy) o warm-up dopo restart: evita di travolgere un server appena rientrato.
- **Retry solo su richieste idempotenti**: `proxy_next_upstream` e `retries` possono duplicare POST se non limitati (`proxy_next_upstream_tries`, `non_idempotent` escluso di default).
- **Config sotto version control**, validazione (`nginx -t`, `haproxy -c`) in CI, deploy tramite reload, mai restart.
- **Nascondere versione** (`server_tokens off`) e non esporre stats/status pubblicamente.
- **Ridondanza del proxy** con VIP/keepalived o LB cloud davanti: vedi [Alta Disponibilità e Failover](ha-e-failover.md).
- Su Kubernetes preferire un ingress controller (NGINX Ingress, HAProxy Ingress): vedi [Ingress](../kubernetes/ingress.md).

## Troubleshooting

### 502 Bad Gateway

**Sintomo:** `502 Bad Gateway` dal proxy; nel log NGINX `connect() failed (111: Connection refused) while connecting to upstream` oppure `upstream prematurely closed connection`.
**Causa:** upstream spento, in crash, in ascolto su altra porta/interfaccia, oppure chiude la connessione keepalive prima del proxy (timeout idle dell'app inferiore a quello del proxy).
**Soluzione:**
```bash
curl -v http://10.0.1.11:8080/healthz          # raggiungibilità diretta dal proxy
ss -tlnp | grep 8080                           # sull'upstream: è in ascolto?
tail -f /var/log/nginx/error.log
```
Se è un problema di keepalive, il timeout idle dell'applicazione deve essere **maggiore** di `keepalive_timeout` di NGINX (e del timeout di HAProxy `timeout server`).

### 504 Gateway Timeout

**Sintomo:** `504` dopo esattamente `proxy_read_timeout` secondi; in HAProxy `sH` / `504` nel log con termination state `sH--`.
**Causa:** backend lento (query, lock, GC) oltre il timeout.
**Soluzione:** individuare la richiesta lenta con `$upstream_response_time` nel log; aumentare il timeout solo per la `location` che lo richiede (report, upload), non globalmente. Per elaborazioni lunghe usare pattern asincroni.

### Upstream keepalive esauriti / porte effimere a `TIME_WAIT`

**Sintomo:** `cannot assign requested address`, migliaia di socket in `TIME_WAIT` verso gli upstream, latenza in aumento.
**Causa:** `keepalive` mancante o troppo basso, oppure `proxy_http_version 1.1` / `Connection ""` non impostati.
**Soluzione:**
```bash
ss -s                                            # riepilogo socket
ss -tan state time-wait | wc -l
sysctl net.ipv4.ip_local_port_range              # ampliare se necessario: 1024 65000
```
Aumentare `keepalive` nell'`upstream`, verificare header e versione HTTP; in HAProxy usare `http-reuse safe|always`.

### "worker_connections are not enough"

**Sintomo:** nel log NGINX `worker_connections are not enough` oppure `socket() failed (24: Too many open files)`.
**Causa:** ogni richiesta proxata consuma 2 connessioni; il limite di file descriptor del processo è inferiore a `worker_connections`.
**Soluzione:** alzare `worker_connections` e `worker_rlimit_nofile` (deve essere ≥ 2× `worker_connections`) e `LimitNOFILE` nel unit systemd:
```bash
systemctl edit nginx        # [Service]  LimitNOFILE=65535
cat /proc/$(pgrep -o nginx)/limits | grep "open files"
```
Per HAProxy il limite equivalente è `maxconn` (in `global` e per `frontend`); ogni connessione client+server conta.

### `nf_conntrack: table full, dropping packet`

**Sintomo:** connessioni intermittenti perse o in timeout; `dmesg` mostra `nf_conntrack: table full`.
**Causa:** su nodi con iptables/NAT la tabella conntrack si satura sotto alto numero di connessioni.
**Soluzione:**
```bash
sysctl net.netfilter.nf_conntrack_count net.netfilter.nf_conntrack_max
sysctl -w net.netfilter.nf_conntrack_max=1048576
# oppure bypassare conntrack per il traffico del LB:
iptables -t raw -A PREROUTING -p tcp --dport 443 -j NOTRACK
```

### IP client errato / X-Forwarded-For spoofato

**Sintomo:** i log applicativi mostrano l'IP del proxy o un IP falsificato dal client.
**Causa:** header `X-Forwarded-For` non impostato, oppure accodato senza sanificazione a un valore fornito dal client.
**Soluzione:** su NGINX usare `real_ip_header X-Forwarded-For; set_real_ip_from <IP LB fidati>; real_ip_recursive on;` sul secondo livello di proxy e `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`. Sul primo livello esposto a Internet **sovrascrivere** l'header (`$remote_addr`) invece di accodare. In HAProxy: `option forwardfor` (o `http-request set-header X-Forwarded-For %[src]` per sovrascrivere). Per protocolli non-HTTP usare il PROXY protocol.

## Relazioni

??? info "Algoritmi di Load Balancing — Approfondimento"
    `least_conn`, `hash ... consistent` (NGINX) e `balance leastconn|source|uri` (HAProxy) implementano gli algoritmi descritti nella pagina dedicata; la scelta influisce su sticky session e distribuzione del carico.

    **Approfondimento completo →** [Algoritmi](algoritmi.md)

??? info "Layer 4 vs Layer 7 — Approfondimento"
    `mode tcp` / `stream {}` vs `mode http` / `http {}`: cosa può vedere e modificare il proxy a ciascun livello, e impatto su TLS passthrough e latenza.

    **Approfondimento completo →** [Layer 4 vs Layer 7](layer4-vs-layer7.md)

??? info "Alta Disponibilità — Approfondimento"
    Proxy ridondati con VIP keepalived/VRRP, drain e failover: rendono NGINX e HAProxy non più Single Point of Failure.

    **Approfondimento completo →** [Alta Disponibilità e Failover](ha-e-failover.md)

??? info "Kubernetes Ingress — Approfondimento"
    NGINX Ingress Controller e HAProxy Ingress traducono oggetti `Ingress` in configurazione dei due proxy descritti qui.

    **Approfondimento completo →** [Ingress](../kubernetes/ingress.md)

??? info "Elastic Load Balancing — Approfondimento"
    Alternativa gestita AWS (ALB/NLB); spesso si mettono NGINX/HAProxy dietro un NLB usando il PROXY protocol per preservare l'IP client.

    **Approfondimento completo →** [Elastic Load Balancing](../../cloud/aws/networking/elastic-load-balancing.md)

## Riferimenti

- [HAProxy documentation](https://docs.haproxy.org/)
- [NGINX documentation](https://nginx.org/en/docs/)
- [NGINX — ngx_http_upstream_module](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [PROXY protocol specification](https://www.haproxy.org/download/2.9/doc/proxy-protocol.txt)
- [HAProxy Runtime API](https://www.haproxy.com/documentation/haproxy-runtime-api/)
