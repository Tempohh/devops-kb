---
title: "API Gateway"
slug: api-gateway
category: networking
tags: [api-gateway, reverse-proxy, microservizi, routing, rate-limiting, autenticazione]
parent: networking
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# API Gateway

Un API Gateway è un server che agisce come punto di ingresso unico per tutte le richieste verso i servizi backend di un sistema distribuito. Centralizza funzionalità trasversali — routing, autenticazione, rate limiting, logging, trasformazione delle richieste — che altrimenti dovrebbero essere implementate in ogni singolo servizio.

## Perché l'API Gateway

Senza API gateway, ogni client deve conoscere l'indirizzo e il contratto di ogni microservizio. Con un gateway, il client parla con un singolo endpoint, e il gateway gestisce il routing verso i servizi corretti, applica sicurezza, raccoglie metriche e può aggregare più chiamate in una sola risposta.

!!! info "API Gateway vs Load Balancer"
    Un load balancer distribuisce il traffico verso istanze dello **stesso** servizio. Un API gateway instrada verso **servizi diversi** con logica applicativa (routing per path, versione, tenant). I due componenti coesistono: l'API gateway si trova davanti ai load balancer dei singoli servizi.

## Argomenti in questa Sezione

### [Pattern e Concetti Base](pattern-base.md)
I pattern fondamentali dell'API gateway: BFF (Backend for Frontend), Gateway Aggregation, Request/Response transformation, versioning delle API. Confronto tra approcci e quando ciascuno è appropriato.

### [Kong](kong.md)
Kong è l'API gateway open source più diffuso, basato su Nginx/OpenResty. Architettura plugin-based, configurazione dichiarativa, Kong Manager UI, supporto Kubernetes (Kong Ingress Controller). Setup completo con autenticazione JWT, rate limiting e logging.

### [Rate Limiting](rate-limiting.md)
Proteggere le API da abusi e garantire equità d'accesso: token bucket, sliding window, fixed window. Implementazione con Redis per distribuzione multi-istanza, gestione dei burst, risposta 429 con Retry-After header.

## Relazioni con altri Argomenti

- **Load Balancing**: l'API gateway instrada verso pool di backend, spesso delegando il bilanciamento a un LB dedicato
- **Service Mesh**: in architetture avanzate, il service mesh gestisce il traffico east-west (servizio-servizio) mentre il gateway gestisce il traffico nord-sud (client-gateway)
- **Sicurezza/Zero Trust**: l'API gateway è il punto di enforcement delle policy di autenticazione e autorizzazione
