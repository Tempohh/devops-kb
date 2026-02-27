---
title: "Load Balancing"
slug: load-balancing
category: networking
tags: [load-balancing, alta-disponibilità, distribuzione-traffico, reverse-proxy, scalabilità]
parent: networking
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Load Balancing

Il load balancing (bilanciamento del carico) è la tecnica per distribuire il traffico di rete su più server backend, aumentando la capacità di elaborazione, eliminando i single point of failure e migliorando la latenza. È uno dei pattern fondamentali per costruire sistemi scalabili e ad alta disponibilità.

## Perché il Load Balancing è Fondamentale

Senza load balancing, un singolo server deve gestire tutto il traffico: quando supera la capacità, le richieste iniziano a fallire o rallentare. Con un load balancer davanti a un pool di server, il sistema scala orizzontalmente e continua a funzionare anche se uno o più server backend vanno offline.

!!! info "Scalabilità Orizzontale vs Verticale"
    Il load balancing abilita la **scalabilità orizzontale** (aggiungere server) invece della **scalabilità verticale** (server più potenti). La scalabilità orizzontale è più economica, più resiliente e virtualmente illimitata.

## Argomenti in questa Sezione

### [Layer 4 vs Layer 7](layer4-vs-layer7.md)
Differenza fondamentale tra load balancing a livello di trasporto (TCP/UDP) e a livello applicativo (HTTP). Layer 4 è più veloce; Layer 7 permette routing intelligente basato su contenuto (host, path, header). Analisi di casi d'uso, trade-off di performance e quando scegliere quale approccio.

### [Algoritmi di Load Balancing](algoritmi.md)
I principali algoritmi: Round Robin, Least Connections, IP Hash, Random, Weighted Round Robin, Least Response Time. Analisi comparativa, scenari ottimali per ciascuno e come configurarli in Nginx e HAProxy.

### [Alta Disponibilità e Failover](ha-e-failover.md)
Eliminare il load balancer come single point of failure: active-passive con VRRP/Keepalived, active-active, health check attivi e passivi, graceful draining. Configurazioni di HA per Nginx e HAProxy in produzione.

## Relazioni con altri Argomenti

- **DNS**: il DNS Load Balancing (Round Robin DNS, GeoDNS) è un complemento al load balancing tradizionale
- **Service Mesh**: Istio e Linkerd implementano load balancing L7 tra microservizi direttamente nel data plane
- **Kubernetes**: i Kubernetes Services implementano load balancing interno; gli Ingress Controller gestiscono il traffico esterno
- **API Gateway**: spesso include load balancing integrato verso i backend upstream
