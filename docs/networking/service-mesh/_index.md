---
title: "Service Mesh"
slug: service-mesh
category: networking
tags: [service-mesh, istio, envoy, linkerd, microservizi, mtls]
search_keywords: [service mesh microservizi, sidecar proxy pattern, istio service mesh, envoy proxy, linkerd lightweight, mtls automatico, traffic management service mesh, observability service mesh, circuit breaker service mesh]
parent: networking
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Service Mesh

Un **service mesh** è uno strato di infrastruttura dedicato alla gestione della comunicazione service-to-service in architetture a microservizi. Implementa cross-cutting concerns come mTLS, retry, timeout, circuit breaking e distributed tracing in modo trasparente alle applicazioni, tramite sidecar proxy affiancati a ogni servizio.

## Contenuti di questa sezione

| Argomento | Descrizione | Difficoltà |
|-----------|-------------|------------|
| [Concetti Base](concetti-base.md) | Fondamentali del service mesh: data plane, control plane, sidecar pattern | Advanced |
| [Istio](istio.md) | Il service mesh più diffuso in Kubernetes: CRDs, traffic management, sicurezza | Advanced |
| [Envoy Proxy](envoy.md) | Il data plane de-facto dei service mesh: architettura xDS, filtri, configurazione | Advanced |
| [Linkerd](linkerd.md) | Service mesh leggero scritto in Rust: semplicità, mTLS automatico, basso overhead | Advanced |

## Quando usare un Service Mesh

Un service mesh diventa vantaggioso quando:

- Il numero di microservizi supera la soglia in cui gestire manualmente retry, timeout e mTLS diventa insostenibile
- E' richiesta visibilità (observability) sulla comunicazione tra servizi senza modificare il codice applicativo
- La sicurezza zero-trust (mTLS obbligatorio tra ogni coppia di servizi) e' un requisito non negoziabile
- Si implementano pattern avanzati di traffic management: canary deployment, A/B testing, fault injection per chaos engineering

## Relazioni con altri argomenti

- **API Gateway** — Il service mesh gestisce il traffico east-west (tra servizi); l'API Gateway gestisce il traffico north-south (client esterni verso i servizi). I due si complementano.
- **Ingress Controller** — Il punto di ingresso del traffico esterno in Kubernetes; il service mesh opera all'interno del cluster.
- **Kubernetes** — Il service mesh vive tipicamente all'interno di un cluster Kubernetes, sfruttando le API per sidecar injection e service discovery.
