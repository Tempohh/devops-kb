---
title: "Algoritmi di Load Balancing"
slug: algoritmi
category: networking
tags: [load-balancing, algoritmi, round-robin, least-connections, ip-hash, weighted, nginx, haproxy]
search_keywords: [round robin, least connections, least conn, ip hash, random, weighted round robin, least response time, resource based, consistent hashing, power of two choices, sticky session, session affinity, upstream, backend selection]
parent: networking/load-balancing/_index
related: [networking/load-balancing/layer4-vs-layer7, networking/load-balancing/ha-e-failover]
official_docs: https://nginx.org/en/docs/http/ngx_http_upstream_module.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Algoritmi di Load Balancing

## Panoramica

L'algoritmo di load balancing determina come il traffico viene distribuito tra i server backend. La scelta dell'algoritmo ha impatto diretto su distribuzione del carico, latenza, utilizzo delle risorse e comportamento in caso di richieste asimmetriche. Non esiste un algoritmo universalmente migliore: la scelta dipende dalle caratteristiche del workload (richieste uniformi vs eterogenee), dalla natura delle sessioni (stateless vs stateful) e dalla variabilità dei backend.

## Confronto Algoritmi

| Algoritmo | Stato server | Richieste eterogenee | Sessioni | Overhead |
|-----------|-------------|---------------------|----------|----------|
| Round Robin | No | No | No | Minimo |
| Weighted Round Robin | No | No | No | Minimo |
| Least Connections | Sì | Sì | Parziale | Basso |
| IP Hash | No | No | Sì (per IP) | Minimo |
| Least Response Time | Sì | Sì | No | Medio |
| Random | No | No | No | Minimo |
| Consistent Hash | No | No | Sì | Medio |

## Algoritmi Principali

### Round Robin

Il più semplice: distribuisce le richieste in sequenza ciclica. Funziona ottimamente quando le richieste hanno costo uniforme e i backend hanno capacità identica.

```
Richiesta 1 → Server A
Richiesta 2 → Server B
Richiesta 3 → Server C
Richiesta 4 → Server A (ciclo riparte)
```

**Quando usare:** Backend omogenei, richieste di costo uniforme, API stateless semplici.
**Quando evitare:** Richieste con latenza molto variabile (alcune durano 10ms, altre 5s) — backend lenti si saturano.

```nginx
upstream backend {
    # Round Robin è il default in Nginx — nessuna direttiva necessaria
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080;
}
```

### Weighted Round Robin

Estende Round Robin con un peso per ogni server. I server con peso maggiore ricevono proporzionalmente più traffico. Utile quando i backend hanno capacità diverse.

```
Server A (weight 5) → 5 richieste ogni 8
Server B (weight 2) → 2 richieste ogni 8
Server C (weight 1) → 1 richiesta ogni 8
```

```nginx
upstream backend {
    server 10.0.0.1:8080 weight=5;  # Server potente
    server 10.0.0.2:8080 weight=2;  # Server medio
    server 10.0.0.3:8080 weight=1;  # Server debole o canary (1%)
}
```

**Uso pratico:** Canary deployment (inviare 1-5% del traffico a una nuova versione), migrazione graduale, backend con hardware diverso.

### Least Connections

Invia la richiesta al server con il minor numero di connessioni attive in quel momento. Tiene conto del carico reale — un server lento accoderà più connessioni e riceverà meno nuove richieste.

```
Server A: 150 connessioni attive
Server B:  30 connessioni attive  ← nuova richiesta va qui
Server C:  75 connessioni attive
```

**Quando usare:** Richieste con latenza molto variabile (mix di richieste veloci e lente), API con processing time eterogeneo, long-polling.
**Svantaggio:** Richiede tracking dello stato delle connessioni — overhead minimo ma presente.

```nginx
upstream backend {
    least_conn;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080;
}
```

```
# HAProxy
backend app_pool
    balance leastconn
    server s1 10.0.0.1:8080 check
    server s2 10.0.0.2:8080 check
```

### IP Hash

Calcola un hash dell'IP del client e lo mappa in modo deterministico a un server backend. Lo stesso client andrà sempre sullo stesso backend (finché il backend è disponibile). Implementa la **session affinity** basata su IP.

```
Client 192.168.1.10 → hash(192.168.1.10) % 3 = 1 → Server B (sempre)
Client 10.0.0.50    → hash(10.0.0.50) % 3 = 0    → Server A (sempre)
```

**Quando usare:** Applicazioni con sessioni server-side (state nel filesystem, in-memory), WebSocket (le connessioni sono persistenti), applicazioni che non possono usare sessioni distribuite.
**Svantaggio:** Se un backend cade, tutti i suoi client devono migrare. Distribuzione potenzialmente sbilanciata se pochi IP grandi (NAT aziendale).

```nginx
upstream backend {
    ip_hash;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080 down;  # Temporaneamente fuori senza invalidare le hash
}
```

### Least Response Time (Nginx Plus / HAProxy)

Combina connessioni attive e latenza misurata: invia la richiesta al server con il minor numero di connessioni attive E il minor tempo di risposta medio. Più sofisticato di Least Connections ma richiede misurazioni attive.

```nginx
# Nginx Plus (commerciale)
upstream backend {
    least_time header;  # last_byte per considerare la risposta completa
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}
```

```
# HAProxy
backend app_pool
    balance leastconn
    option http-server-close  # Necessario per misurare latenza
```

### Consistent Hashing

Variante di IP Hash che usa un **ring hash** — quando un server viene aggiunto o rimosso, solo le richieste mappate su quel server vengono riassegnate, non tutte. Cruciale per sistemi di caching distribuito.

```nginx
# Nginx — hash su un campo applicativo (es. X-User-ID)
upstream backend {
    hash $http_x_user_id consistent;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080;
}
```

**Quando usare:** Backend stateful con caching (Memcached, Varnish), quando aggiungere/rimuovere server deve impattare il minimo di client.

## Sticky Sessions con Cookie

Per applicazioni stateful, IP Hash è approssimativo (più client dietro NAT vanno sullo stesso server). La soluzione migliore è la **sticky session con cookie**:

```
# HAProxy — Cookie-based sticky session
backend app_pool
    balance roundrobin
    cookie SERVERID insert indirect nocache httponly secure
    server s1 10.0.0.1:8080 check cookie s1
    server s2 10.0.0.2:8080 check cookie s2
    server s3 10.0.0.3:8080 check cookie s3
```

```nginx
# Nginx Plus — sticky cookie
upstream backend {
    sticky cookie srv_id expires=1h httponly secure;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
}
```

Il LB inserisce un cookie nella risposta con l'ID del server. Le richieste successive con quel cookie vengono sempre inviate allo stesso backend.

!!! warning "Sticky Sessions e Scalabilità"
    Le sticky session riducono la flessibilità del load balancing. Se un backend cade, tutte le sue sessioni sono perse. Preferire architetture stateless con sessioni in Redis/database condiviso.

## Best Practices

- **Stateless → Round Robin o Least Connections**: la maggior parte delle API moderne non necessita di session affinity
- **Least Connections per workload eterogeneo**: quando le richieste variano molto in durata, Least Connections distribuisce il carico reale meglio di Round Robin
- **Weighted per canary**: usare weight=1 su 100 per inviare l'1% del traffico alla nuova versione
- **Evitare IP Hash in produzione**: i client enterprise (tutto il traffico da 1 IP) possono sovraccaricare un singolo backend; preferire cookie sticky
- **Health check sempre attivi**: un backend lento o degradato deve essere rimosso automaticamente dal pool

## Troubleshooting

| Sintomo | Causa Probabile | Soluzione |
|---------|-----------------|-----------|
| Distribuzione sbilanciata con Round Robin | Connessioni persistenti (keep-alive) | Passare a Least Connections |
| Stesso backend sempre sovraccarico con IP Hash | Molti client dietro NAT stesso IP | Passare a sticky cookie |
| Client perde sessione dopo scaling | Session affinity non configurata | Implementare sessioni distribuite (Redis) o sticky cookie |
| Canary riceve troppo traffico | Weight non proporzionale | Verificare calcolo: `weight/(sum of weights)` |

## Relazioni

??? info "Layer 4 vs Layer 7"
    Gli algoritmi disponibili dipendono dal layer del load balancer.

    **Approfondimento →** [Layer 4 vs Layer 7](layer4-vs-layer7.md)

??? info "Alta Disponibilità e Failover"
    Come gestire la rimozione e reintegrazione dei backend.

    **Approfondimento →** [HA e Failover](ha-e-failover.md)

## Riferimenti

- [Nginx Upstream Module](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HAProxy Load Balancing Algorithms](https://www.haproxy.com/blog/fundamentals-of-haproxy-load-balancing/)
