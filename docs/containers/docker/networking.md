---
title: "Docker Networking"
slug: networking
category: containers
tags: [docker, networking, bridge, overlay, macvlan, iptables, dns, veth, container-network]
search_keywords: [docker network bridge, docker overlay network swarm, docker macvlan, docker DNS resolution, docker iptables rules, veth pair container, container network namespace, docker network troubleshooting, docker host network, docker none network, docker network inspect]
parent: containers/docker/_index
related: [containers/docker/architettura-interna, networking/kubernetes/cni, containers/kubernetes/_index]
official_docs: https://docs.docker.com/engine/network/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Docker Networking

## Modelli di Rete — Panoramica

Docker implementa networking tramite driver pluggabili. Ogni container riceve un network namespace isolato (vedi [Architettura Interna](architettura-interna.md)).

```
Driver di Rete Docker

  bridge (default)    → Container su stesso host si parlano via Linux bridge
  host                → Container condivide il net namespace dell'host
  none                → Nessuna interfaccia di rete (isolamento totale)
  overlay             → Container su host diversi (Docker Swarm / multi-host)
  macvlan             → Container con MAC/IP propri sulla rete fisica
  ipvlan              → Come macvlan ma condivide MAC dell'host
  network plugins     → Calico, Weave, Flannel (anche per Kubernetes)
```

---

## Bridge Network — Meccanismo Interno

Il **bridge** è il driver default. Crea un bridge Linux (`docker0`) e connette ogni container con una coppia **veth** (virtual ethernet).

```
Bridge Network — Come funziona

  Host Network Stack
  +------------------------------------------------------------------+
  |                                                                  |
  |  docker0 (bridge)                                               |
  |  172.17.0.1/16                                                  |
  |   |                                                             |
  |   +-- veth7a3b2c (host side) <----+                            |
  |   |                               |  veth pair = cavo virtuale  |
  |   +-- vethb2c3d4 (host side) <----+                            |
  |                                                                  |
  +----------+----------------------+-----------------------------+--+
             |                      |
  Container A namespace    Container B namespace
  +------------------+    +------------------+
  |  eth0            |    |  eth0            |
  |  172.17.0.2/16   |    |  172.17.0.3/16   |
  |  (container side)|    |  (container side)|
  +------------------+    +------------------+

  Container A → Container B: A → veth → docker0 → veth → B
  Container A → Internet: A → veth → docker0 → NAT (iptables) → eth0 host

  Nota: la comunicazione tra container sulla STESSA bridge network
        NON passa per iptables FORWARD in Docker moderno (ottimizzazione):
        passa direttamente nel kernel via bridge switching.
```

**Ispezione della bridge network:**

```bash
# Crea una bridge network custom (preferita alla default docker0)
docker network create \
    --driver bridge \
    --subnet 192.168.100.0/24 \
    --gateway 192.168.100.1 \
    --opt "com.docker.network.bridge.name=br-app" \
    --opt "com.docker.network.driver.mtu=1450" \
    app-network

# Lancia container sulla network custom
docker run -d --name web --network app-network nginx
docker run -d --name api --network app-network myapi

# Ispezione del bridge Linux sottostante
docker network inspect app-network | jq '.[0].Options'
brctl show br-app        # mostra le interfacce collegate al bridge
ip link show type veth   # lista tutti i veth pair

# DNS automatico su network custom:
# i container si raggiungono per NOME (non per IP)
docker exec api ping web  # funziona automaticamente
# La default bridge (docker0) NON ha DNS automatico — usare --link (deprecato)
# o passare a reti custom
```

---

## iptables — Come Docker Gestisce il Traffico

Docker scrive regole iptables per gestire NAT, forwarding e port publishing. Capire queste regole è essenziale per il troubleshooting.

```
iptables Rules — docker run -p 8080:80 nginx

  CHAIN: DOCKER-USER (user-defined rules, valutate prima)
  CHAIN: DOCKER (regole auto-generate da Docker)
  CHAIN: DOCKER-ISOLATION-STAGE-1/2 (isolamento tra bridge diverse)

  --- PREROUTING (DNAT) ---
  -A DOCKER -p tcp --dport 8080 -j DNAT --to-destination 172.17.0.2:80
  # Traffico in arrivo su porta 8080 host → reindirizza al container

  --- POSTROUTING (MASQUERADE/SNAT) ---
  -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE
  # Traffico dal container verso l'esterno → maschera con IP host

  --- FORWARD ---
  -A DOCKER -d 172.17.0.2/32 ! -i docker0 -p tcp --dport 80 -j ACCEPT
  -A DOCKER-ISOLATION-STAGE-1 -i br-app ! -o br-app -j DOCKER-ISOLATION-STAGE-2
  -A DOCKER-ISOLATION-STAGE-2 -o docker0 -j DROP
  # Impedisce traffico diretto tra bridge diverse (isolamento per rete)
```

```bash
# Debug iptables rules Docker
iptables -L DOCKER -n -v --line-numbers
iptables -t nat -L DOCKER -n -v
iptables -t nat -L POSTROUTING -n -v

# Troubleshooting: perché il container non raggiunge internet?
# 1. Verifica forwarding abilitato sull'host
sysctl net.ipv4.ip_forward  # deve essere 1

# 2. Verifica regole MASQUERADE
iptables -t nat -L POSTROUTING -n | grep 172.17

# 3. Testa DNS dal container
docker run --rm alpine nslookup google.com
docker run --rm alpine nslookup web app-network  # DNS interno
```

---

## DNS Docker — Service Discovery

Docker implementa un DNS embedded (`127.0.0.11`) per la risoluzione dei nomi dei container nelle network custom.

```
DNS Resolution in Docker

  Container "api" chiede: dig web

  1. Query → 127.0.0.11 (DNS embedded di Docker)
  2. Docker DNS: lookup "web" nella rete "app-network"
  3. Risposta: 192.168.100.3 (IP container "web")

  docker run --dns 8.8.8.8 ...   → overrides il DNS di default
  docker run --dns-search company.internal ...  → aggiunge search domain

  /etc/resolv.conf nel container:
  nameserver 127.0.0.11
  options ndots:0

  Alias multipli per un container:
  docker network connect --alias db-primary app-network postgres-1
  # "db-primary" risolve all'IP di postgres-1 in quella rete
```

---

## Host Network — Accesso Diretto

Con `--network host` il container condivide il net namespace dell'host. Nessun NAT, nessuna isolamento di rete.

```bash
docker run --network host nginx
# nginx ascolta direttamente sulla porta 80 dell'host
# NO port mapping necessario o possibile
# Processo visibile come localhost:80 sull'host

# Casi d'uso:
# - Performance massima (elimina NAT overhead)
# - Accesso a porte privilegiate senza mapping
# - Monitoring: container che deve vedere tutte le interfacce dell'host
# - Applicazioni che usano UDP multicast

# Limitazione: NON funziona su macOS/Windows (la VM host è il Linux sotto Docker Desktop)
```

---

## Overlay Network — Multi-Host

Le **overlay network** abilitano la comunicazione tra container su host fisici diversi. Usano VXLAN per incapsulare il traffico container nel traffico UDP tra host.

```
Overlay Network con VXLAN

  Host 1 (10.0.0.1)              Host 2 (10.0.0.2)
  +----------------------+        +----------------------+
  |  Container A         |        |  Container C         |
  |  172.20.0.2/16       |        |  172.20.0.4/16       |
  |      |               |        |      |               |
  |  overlay0 (VTEP)     |        |  overlay0 (VTEP)     |
  |  10.0.0.1:4789/UDP   |------->|  10.0.0.2:4789/UDP   |
  +----------------------+        +----------------------+

  Pacchetto Container A → Container C:
  1. Container A: IP src=172.20.0.2, dst=172.20.0.4
  2. VTEP host 1: incapsula in VXLAN UDP
     Outer: IP src=10.0.0.1, dst=10.0.0.2, UDP dst=4789
     Inner: VNI (VXLAN Network ID), payload originale
  3. VTEP host 2: decapsula
  4. Container C riceve: IP src=172.20.0.2, dst=172.20.0.4

  Docker usa Gossip Protocol (Serf) per la discovery degli host
  e la propagazione della routing table VXLAN.
```

```bash
# Overlay network richiede Docker Swarm mode per la discovery
docker swarm init --advertise-addr 10.0.0.1

# Crea overlay network
docker network create \
    --driver overlay \
    --subnet 172.20.0.0/16 \
    --opt encrypted \          # VXLAN con AES-128 encryption
    prod-overlay

# I container nei servizi Swarm usano automaticamente overlay
docker service create \
    --name web \
    --network prod-overlay \
    --replicas 3 \
    nginx
```

---

## Macvlan — Container con IP della Rete Fisica

**Macvlan** assegna a ogni container un indirizzo MAC e IP distinto, rendendolo visibile sulla rete fisica come se fosse una macchina fisica separata.

```
Macvlan — Topologia

  Rete Fisica: 192.168.1.0/24
                    |
  Switch Fisico ----+---- Host (192.168.1.10)
                    |         |
                    |    +----+----+
                    |    |  eth0   | (Physical NIC in promiscuous mode)
                    |    +---------+
                    |        |
                    |   macvlan0 parent=eth0
                    |    +--------+--------+
                    |    |                 |
                Container A          Container B
                192.168.1.20         192.168.1.21
                MAC: 02:42:c0:a8:01:14  MAC: 02:42:c0:a8:01:15

  Container A è raggiungibile dalla rete fisica come qualsiasi host.
  ATTENZIONE: Container A e Host non si raggiungono via macvlan
              (limitazione macvlan) → usare un bridge macvlan se necessario.
```

```bash
# Macvlan mode bridge (più comune)
docker network create \
    --driver macvlan \
    --subnet 192.168.1.0/24 \
    --gateway 192.168.1.1 \
    --ip-range 192.168.1.128/25 \  # pool IP per container (evita conflitti con DHCP)
    -o parent=eth0 \               # NIC fisica
    macvlan-prod

# NIC fisica DEVE essere in modalità promiscua
ip link set eth0 promisc on

docker run -d \
    --network macvlan-prod \
    --ip 192.168.1.130 \
    nginx
```

---

## Troubleshooting Network

```bash
# 1. Container non si raggiungono — debug connettività
docker run --rm --network app-network nicolaka/netshoot \
    ping web      # test ICMP
    curl http://web:80  # test TCP

# 2. Port mapping non funziona
docker ps | grep PORTS     # verifica il mapping
ss -tlnp | grep :8080      # verifica che l'host ascolti sulla porta
iptables -t nat -L DOCKER  # verifica regola DNAT

# 3. DNS non risolve
docker run --rm --network app-network nicolaka/netshoot \
    nslookup web 127.0.0.11   # interroga il DNS Docker direttamente
    dig @127.0.0.11 web       # versione dettagliata

# 4. Performance: misura latenza container-to-container
docker run --rm --network app-network nicolaka/netshoot \
    iperf3 -c web -t 10    # dopo aver avviato un server iperf nel container "web"

# 5. Traccia il percorso del pacchetto (con NFTables/iptables)
docker run --rm --network host nicolaka/netshoot \
    tcpdump -i any -n host 172.17.0.2

# 6. Ispeziona tutti i dettagli della network
docker network inspect app-network --format '{{json .Containers}}' | jq
```

---

## Riferimenti

- [Docker Networking Overview](https://docs.docker.com/engine/network/)
- [Bridge Networks](https://docs.docker.com/engine/network/drivers/bridge/)
- [Overlay Networks](https://docs.docker.com/engine/network/drivers/overlay/)
- [Macvlan](https://docs.docker.com/engine/network/drivers/macvlan/)
- [iptables and Docker](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
