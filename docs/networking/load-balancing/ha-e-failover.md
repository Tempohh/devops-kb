---
title: "Alta Disponibilità e Failover"
slug: ha-e-failover
category: networking
tags: [ha, alta-disponibilità, failover, keepalived, vrrp, health-check, draining, redundanza]
search_keywords: [high availability, failover, keepalived, vrrp, virtual ip, active-passive, active-active, health check, graceful draining, upstream down, backup server, sorry server, nginx ha, haproxy ha, passive health check, active health check, circuit breaker, connection draining, zero downtime deployment]
parent: networking/load-balancing/_index
related: [networking/load-balancing/layer4-vs-layer7, networking/load-balancing/algoritmi, networking/kubernetes/ingress]
official_docs: https://www.keepalived.org/manpage.html
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Alta Disponibilità e Failover

## Panoramica

Un load balancer risolve la disponibilità dei backend, ma se il load balancer stesso cade, l'intera infrastruttura è irraggiungibile — diventa un **Single Point of Failure**. L'alta disponibilità (HA) del load balancer richiede ridondanza: almeno due istanze del LB operative, con un meccanismo per trasferire il traffico dalla primaria alla secondaria in caso di guasto. Le tecniche principali sono **active-passive** (una istanza attiva, una in standby) e **active-active** (entrambe attive con distribuzione del carico).

## Prerequisiti

Questo argomento presuppone familiarità con:
- [Layer 4 vs Layer 7](layer4-vs-layer7.md) — capire la differenza tra LB L4 e L7 è necessario per scegliere la strategia HA corretta
- [Algoritmi di Load Balancing](algoritmi.md) — gli algoritmi di load balancing determinano come il traffico è distribuito tra i backend in HA
- [TCP/IP](../fondamentali/tcpip.md) — VRRP e keepalived operano a livello di rete: capire IP e ARP aiuta a comprendere il VIP failover

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

## Concetti Chiave

### Active-Passive con VRRP/Keepalived

Il pattern più comune per HA del load balancer: due istanze Nginx/HAProxy, un **Virtual IP** (VIP) flottante che appartiene sempre all'istanza primaria. In caso di guasto della primaria, il VIP migra automaticamente alla secondaria in 1-3 secondi.

```
                     VIP: 10.0.0.100
                          │
              ┌───────────┴───────────┐
              ▼
     LB-Primary (MASTER)         LB-Secondary (BACKUP)
      10.0.0.1                    10.0.0.2
      [ACTIVE]                   [Standby]
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
  Backend1  Backend2  Backend3
```

**VRRP (Virtual Router Redundancy Protocol)** è il protocollo che gestisce il VIP. Keepalived è la sua implementazione Linux più diffusa.

### Active-Active

Entrambe le istanze del LB sono attive e ricevono traffico. Richiede un meccanismo upstream (DNS round-robin, Anycast, BGP ECMP) per distribuire le connessioni:

```
DNS: lb.example.com → [10.0.0.1, 10.0.0.2]

Client A → 10.0.0.1 (LB-1) → Backend pool
Client B → 10.0.0.2 (LB-2) → Backend pool
```

**Vantaggi:** doppia capacità, nessun failover lento.
**Svantaggi:** più complesso; sessioni sticky difficili; entrambi devono condividere la stessa configurazione.

### Health Check: Passive vs Active

| Tipo | Come funziona | Velocità rilevamento | Overhead |
|------|--------------|---------------------|----------|
| **Passive** | Monitora errori sulle richieste reali | Lento (dipende dal traffico) | Zero |
| **Active** | Sonda periodica al backend (HTTP GET /health) | Veloce (configurabile) | Minimo |

Usare entrambi: passive per rilevamento immediato in produzione, active per rilevare backend degr adati prima che ricevano traffico.

## Architettura / Come Funziona

### Failover con Keepalived

```
Stato normale:           Failover:
                                          LB-Primary guasta!
Client → VIP → LB-Primary               │
              │                           │ VRRP: MASTER → FAULT
              └─ backends                 │
                                          VIP → LB-Secondary
LB-Secondary (BACKUP):                   │
│ Riceve VRRP advertisements             └─ LB-Secondary diventa MASTER
│ da LB-Primary ogni 1s                  │ Migra VIP in <3s
│ Se cessano → assume MASTER             └─ backends
```

### Graceful Draining

Quando un backend viene rimosso (deploy, shutdown), le connessioni esistenti devono essere servite prima di terminare:

```
1. Backend segnala "stopping" (health check ritorna unhealthy o 503)
2. LB smette di inviare NUOVE connessioni al backend
3. LB aspetta che le connessioni esistenti terminino (drain period: 30-60s)
4. Backend si spegne
```

## Configurazione & Pratica

### Keepalived — Configurazione HA Nginx

```bash
# Installa Keepalived su entrambi i server
apt install keepalived

# Script di check per verificare che Nginx sia up
cat > /etc/keepalived/check_nginx.sh << 'EOF'
#!/bin/bash
if ! pgrep -x nginx > /dev/null; then
    exit 1
fi
if ! curl -sf http://localhost/health > /dev/null 2>&1; then
    exit 1
fi
exit 0
EOF
chmod +x /etc/keepalived/check_nginx.sh
```

```
# /etc/keepalived/keepalived.conf — LB-Primary (MASTER)
global_defs {
    router_id LB_PRIMARY
    script_user root
    enable_script_security
}

vrrp_script check_nginx {
    script "/etc/keepalived/check_nginx.sh"
    interval 2     # Controlla ogni 2 secondi
    weight  -20    # Se fallisce, abbassa la priorità di 20
    fall    2      # 2 fallimenti consecutivi = down
    rise    2      # 2 successi consecutivi = up
}

vrrp_instance VI_1 {
    state  MASTER           # MASTER sul primary
    interface eth0
    virtual_router_id 51    # Stesso su entrambi i nodi
    priority 110            # Priorità più alta sul primary (secondary: 100)
    advert_int 1            # Advertisement VRRP ogni 1 secondo

    authentication {
        auth_type PASS
        auth_pass MySecretPass123
    }

    virtual_ipaddress {
        10.0.0.100/24 dev eth0  # Il VIP
    }

    track_script {
        check_nginx
    }
}
```

```
# /etc/keepalived/keepalived.conf — LB-Secondary (BACKUP)
vrrp_instance VI_1 {
    state  BACKUP           # BACKUP sul secondary
    interface eth0
    virtual_router_id 51    # Stesso valore del primary
    priority 100            # Priorità più bassa
    advert_int 1

    authentication {
        auth_type PASS
        auth_pass MySecretPass123
    }

    virtual_ipaddress {
        10.0.0.100/24 dev eth0
    }

    track_script {
        check_nginx
    }
}
```

### Nginx — Health Check Passivo e Failover Backend

```nginx
upstream backend_pool {
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080 backup;  # Usato solo se tutti gli altri sono down

    # Health check passivo (Nginx open source)
    # max_fails: errori consecutivi prima di marcare come down
    # fail_timeout: quanto tempo restare in stato "down" + finestra per contare i fail
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
}

server {
    location / {
        proxy_pass http://backend_pool;

        # Retry su errori di connessione e timeout (NON su 5xx per evitare double-POST)
        proxy_next_upstream error timeout invalid_header;
        proxy_next_upstream_tries 3;
        proxy_next_upstream_timeout 10s;
    }
}
```

### HAProxy — Health Check Attivo e Circuit Breaker

```
backend app_pool
    balance leastconn
    option httpchk GET /health HTTP/1.1\r\nHost:\ example.com

    # Health check attivo ogni 5 secondi
    # 2 fallimenti = backend down, 2 successi = backend up
    server s1 10.0.0.1:8080 check inter 5s fall 2 rise 2
    server s2 10.0.0.2:8080 check inter 5s fall 2 rise 2
    server s3 10.0.0.3:8080 check inter 5s fall 2 rise 2 backup

    # Sorry server — risponde ai client quando tutti i backend sono down
    server sorry 127.0.0.1:9000 backup

    # Slow start: reintroduce gradualmente il backend dopo un recovery
    # Evita di sovraccaricare un backend appena tornato online
    # server s1 10.0.0.1:8080 check slowstart 60s

    # Timeout
    timeout connect  5s
    timeout server  30s
    timeout tunnel  3600s  # Per WebSocket

    # Graceful draining con connessioni in corso
    option redispatch  # Se un backend cade durante una richiesta, ritenta su altro backend
```

### Zero-Downtime Deployment con Draining

```bash
# Script per deploy zero-downtime con HAProxy

# 1. Segnala al LB di smettere di inviare traffico al backend da aggiornare
echo "disable server app_pool/s1" | socat stdio /run/haproxy/admin.sock

# 2. Aspetta che le connessioni esistenti terminino (max 60s)
for i in {1..30}; do
    CONNS=$(echo "show stat" | socat stdio /run/haproxy/admin.sock \
            | awk -F',' '/app_pool,s1/{print $18}')
    echo "Connessioni attive s1: $CONNS"
    [ "$CONNS" -eq "0" ] && break
    sleep 2
done

# 3. Aggiorna il backend
docker pull myapp:v2
docker stop myapp-s1
docker run -d --name myapp-s1 -p 8080:8080 myapp:v2

# 4. Verifica health check
sleep 5
curl -f http://10.0.0.1:8080/health

# 5. Reintegra nel pool
echo "enable server app_pool/s1" | socat stdio /run/haproxy/admin.sock
```

## Best Practices

- **Sempre almeno 2 istanze LB**: eliminare il SPOF è il primo requisito di HA
- **Health check attivi su endpoint dedicato**: `/health` deve rispondere 200 solo se l'applicazione è genuinamente pronta (connessioni DB ok, cache ok, ecc.) — non un semplice 200 statico
- **Slow start**: evitare di inondare un backend appena reintegrato dopo un recovery
- **Backup server (sorry page)**: avere sempre un backend di fallback che risponde con un messaggio di manutenzione invece che un timeout
- **Connection draining**: sempre drenare prima di spegnere un backend — non terminarlo bruscamente
- **Monitorare lo stato di Keepalived**: loggare i failover VRRP per capire la frequenza e le cause

## Troubleshooting

### Scenario 1 — VIP non migra al failover

**Sintomo:** Il nodo primary cade ma il VIP non passa al secondary; il servizio rimane irraggiungibile.

**Causa:** Keepalived non attivo sul secondary, misconfiguration di `virtual_router_id`, o firewall blocca i pacchetti VRRP multicast (224.0.0.18).

**Soluzione:** Verificare lo stato di Keepalived su entrambi i nodi, controllare che `virtual_router_id` sia identico, aprire il traffico VRRP sul firewall.

```bash
# Stato keepalived su entrambi i nodi
systemctl status keepalived
journalctl -u keepalived -n 50

# Verifica che il VIP sia presente sul nodo attivo
ip addr show eth0 | grep 10.0.0.100

# Test: simula failure manuale (abbassa priorità)
# Sul primary, abbassa la priorità temporaneamente
kill -STOP $(pgrep keepalived)   # oppure systemctl stop keepalived
# Controlla se il VIP migra al secondary entro 3s
ssh secondary "ip addr show eth0 | grep 10.0.0.100"

# Verifica multicast VRRP (il traffico deve passare tra i nodi)
tcpdump -i eth0 -n proto vrrp
```

---

### Scenario 2 — Backend oscilla tra up e down (flapping)

**Sintomo:** HAProxy o Nginx alternano continuamente un backend tra stato `UP` e `DOWN`; i log mostrano health check failures intermittenti.

**Causa:** Il backend ha latenza elevata che supera il timeout dell'health check, oppure `fall`/`rise` configurati troppo aggressivi, oppure il backend è genuinamente instabile (GC pause, memoria).

**Soluzione:** Aumentare `fail_timeout` e il valore di `fall`/`rise`, controllare la latenza dell'endpoint `/health`, investigare le cause lato applicazione.

```bash
# HAProxy: mostra stato backend in tempo reale
watch -n1 'echo "show stat" | socat stdio /run/haproxy/admin.sock \
  | awk -F"," "NR==1 || /app_pool/" | cut -d, -f1,2,18,19,43'

# HAProxy: log degli ultimi state change
grep "Server app_pool" /var/log/haproxy.log | tail -30

# Test manuale health check endpoint
curl -v -m 5 http://10.0.0.1:8080/health

# Nginx: verifica errori passivi nel log degli errori
tail -f /var/log/nginx/error.log | grep "upstream"
```

---

### Scenario 3 — Spike di errori 502/503 durante deploy

**Sintomo:** Durante un rolling deploy si registrano errori HTTP 5xx per 10-30 secondi prima del ripristino.

**Causa:** Il backend viene spento prima che le connessioni attive vengano drenate, oppure il nuovo container risponde al health check prima di essere pronto a gestire traffico reale.

**Soluzione:** Implementare graceful drain prima dello spegnimento, aggiungere `slow_start` per la reintegrazione, e assicurarsi che l'health check verifichi la readiness applicativa completa (non solo che il processo sia up).

```bash
# HAProxy: drain manuale prima dello spegnimento
echo "disable server app_pool/s1" | socat stdio /run/haproxy/admin.sock

# Attendi connessioni a zero
until [ "$(echo 'show stat' | socat stdio /run/haproxy/admin.sock \
  | awk -F',' '/app_pool,s1/{print $18}')" = "0" ]; do
  echo "Waiting for connections to drain..."; sleep 2
done

# Nginx: verifica connessioni attive su un backend prima di spegnerlo
ss -tnp | grep 8080 | wc -l

# Dopo il deploy: riabilita gradualmente (HAProxy slowstart)
# Aggiungere nel config: server s1 10.0.0.1:8080 check slowstart 60s
echo "enable server app_pool/s1" | socat stdio /run/haproxy/admin.sock
```

---

### Scenario 4 — Backend rimane in stato DOWN dopo recovery

**Sintomo:** Un backend torna operativo (risponde 200 a `/health`) ma HAProxy o Nginx non lo reintegrano nel pool.

**Causa:** Il valore di `rise` è troppo alto e richiede molti successi consecutivi, oppure il health check attivo è disabilitato, oppure il backend è stato disabilitato manualmente via socket admin.

**Soluzione:** Verificare la configurazione `rise`, controllare lo stato via socket admin, forzare la reintegrazione manuale se necessario.

```bash
# HAProxy: verifica stato dettagliato del backend
echo "show stat" | socat stdio /run/haproxy/admin.sock \
  | awk -F',' 'NR==1{print} /app_pool,s1/{print}' \
  | cut -d, -f1,2,17,18,19,43

# HAProxy: forza reintegrazione manuale
echo "enable server app_pool/s1" | socat stdio /run/haproxy/admin.sock
echo "set server app_pool/s1 state ready" | socat stdio /run/haproxy/admin.sock

# Nginx Plus: verifica stato upstream (richiede API)
curl http://localhost/api/6/http/upstreams/backend_pool/servers

# Verifica che il check script di Keepalived passi manualmente
/etc/keepalived/check_nginx.sh && echo "OK" || echo "FAIL"
```

## Relazioni

??? info "Layer 4 vs Layer 7 — Architettura del load balancer"
    La scelta del layer impatta le opzioni di HA disponibili.

    **Approfondimento →** [Layer 4 vs Layer 7](layer4-vs-layer7.md)

??? info "Kubernetes Ingress — HA nativa in Kubernetes"
    In Kubernetes l'HA del load balancer è gestita dal cluster stesso.

    **Approfondimento →** [Kubernetes Ingress](../kubernetes/ingress.md)

## Riferimenti

- [Keepalived User Guide](https://www.keepalived.org/manpage.html)
- [HAProxy Configuration Manual](https://www.haproxy.org/download/2.8/doc/configuration.txt)
- [Nginx Active Health Checks](https://docs.nginx.com/nginx/admin-guide/load-balancer/http-health-check/)
