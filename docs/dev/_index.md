---
title: "Sviluppo Microservizi"
slug: dev
category: dev
tags: [microservizi, sviluppo, api, resilienza, linguaggi, runtime, integrazione, patterns]
search_keywords: [microservizi, microservices, sviluppo software, software development, api design, rest api, grpc, linguaggi backend, java, golang, python, nodejs, runtime, jvm, graal, resilienza, circuit breaker, retry, timeout, bulkhead, service mesh, integrazione, messaging, event driven, saga pattern, cqrs, domain driven design, ddd, bounded context, developer, backend developer, cloud native development]
parent: /
official_docs: https://microservices.io/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Sviluppo Microservizi

Questa sezione è la prospettiva del **developer** sull'architettura a microservizi: come si progetta, si scrive, si integra e si rende resiliente un singolo servizio — dall'implementazione del codice fino alla sua esposizione su Kubernetes.

È complementare alle sezioni infrastrutturali della KB: qui il focus è *cosa fa il codice*, non *come gira il cluster*.

---

## Prospettiva Developer vs Ops

La DevOps KB copre lo stesso sistema da angolazioni diverse. È importante sapere dove guardare:

| Domanda | Sezione giusta |
|---|---|
| Come scrivo un endpoint REST con retry e circuit breaker? | **Questa sezione** |
| Come configuro un Service Mesh per gestire il traffico? | [Networking / Service Mesh](../networking/service-mesh/_index.md) |
| Come containerizza e deploya un servizio su K8s? | [Containers / Kubernetes](../containers/kubernetes/_index.md) |
| Come gestisco i segreti in produzione? | [Security / Secret Management](../security/secret-management/_index.md) |
| Come strumento il codice per metriche e tracce? | [Monitoring](../monitoring/_index.md) |
| Come costruisco la pipeline CI/CD? | [CI/CD](../ci-cd/_index.md) |
| Come gestisco code e messaggi tra servizi? | [Messaging](../messaging/_index.md) |

!!! tip "Regola pratica"
    Se stai toccando file di codice sorgente (`.go`, `.java`, `.py`, `.ts`…), sei nella prospettiva developer. Se stai toccando YAML di Kubernetes, Helm chart, o configurazioni infrastrutturali, sei nella prospettiva ops.

---

## Macro-Aree

<div class="grid cards" markdown>

-   :material-language-go: **Linguaggi & Runtime**

    ---
    Go, Java (JVM/GraalVM), Python, Node.js. Caratteristiche chiave per microservizi: startup time, memory footprint, concurrency model, ecosystem.

    → [Linguaggi](linguaggi/_index.md)

-   :material-api: **API Design**

    ---
    REST, gRPC, GraphQL, AsyncAPI. Versionamento, contratti, backward compatibility, OpenAPI spec.

    → [API Design](api/_index.md)

-   :material-shield-refresh: **Resilienza**

    ---
    Circuit breaker, retry con backoff esponenziale, timeout, bulkhead, rate limiting. Pattern a livello di codice e a livello di service mesh.

    → [Resilienza](resilienza/_index.md)

-   :material-transit-connection-variant: **Integrazioni**

    ---
    Comunicazione sincrona (REST/gRPC), asincrona (Kafka/RabbitMQ), Saga pattern, CQRS, event sourcing.

    → [Integrazioni](integrazioni/_index.md)

-   :material-database: **Data Layer**

    ---
    Database per microservizio, migrations, connection pooling, read replicas, cache patterns (Redis).

    → [Data Layer](data/_index.md)

-   :material-test-tube: **Testing**

    ---
    Unit, integration, contract testing (Pact), test doubles, test containers, chaos engineering.

    → [Testing](testing/_index.md)

-   :material-certificate: **Sicurezza Applicativa**

    ---
    TLS/mTLS dal codice: Java KeyStore/TrustStore, SSLContext, .NET X509Certificate2, Go tls.Config. Rotation certificati senza restart, debug TLS.

    → [Sicurezza](sicurezza/_index.md)

</div>

---

## Mappa di Lettura

La progressione consigliata segue quattro stadi: dalla scelta del linguaggio/runtime, alla progettazione delle API, alle integrazioni con altri servizi, fino ai pattern di resilienza.

```
STADIO 1: LINGUAGGIO & RUNTIME
┌─────────────────────────────────────────────────────────┐
│  Scegli il linguaggio in base a: startup time,           │
│  throughput atteso, team skill, ecosystem libraries.     │
│                                                          │
│  Go  →  basso footprint, compile-time, ideal per sidecar │
│  Java/GraalVM  →  ecosystem ricco, native image option   │
│  Python  →  ML/AI integration, prototipazione rapida     │
│  Node.js  →  I/O bound, microservizi leggeri             │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
STADIO 2: API DESIGN
┌─────────────────────────────────────────────────────────┐
│  Definisci il contratto prima di scrivere il codice.     │
│                                                          │
│  Sincrono  →  REST (OpenAPI) o gRPC (protobuf)           │
│  Asincrono  →  AsyncAPI + schema registry (Avro/JSON)    │
│  Versionamento  →  URL versioning vs header negotiation  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
STADIO 3: INTEGRAZIONI
┌─────────────────────────────────────────────────────────┐
│  Come questo servizio comunica con gli altri?            │
│                                                          │
│  Sincrono (request/response):                            │
│    HTTP → service discovery via DNS/Kubernetes Service   │
│    gRPC → streaming bidirezionale, protobuf serialization│
│                                                          │
│  Asincrono (event-driven):                               │
│    Kafka → alta throughput, retention, replay            │
│    RabbitMQ → routing flessibile, workload distribution  │
│                                                          │
│  Transazioni distribuite:                                │
│    Saga (choreography vs orchestration)                  │
│    CQRS + Event Sourcing per read/write separation       │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
STADIO 4: RESILIENZA
┌─────────────────────────────────────────────────────────┐
│  Ogni chiamata esterna può fallire. Progetta per questo. │
│                                                          │
│  Timeout  →  sempre definito esplicitamente              │
│  Retry    →  exponential backoff + jitter                │
│  Circuit Breaker  →  Resilience4j, Hystrix, istio        │
│  Bulkhead  →  thread pool / semaphore isolation          │
│  Fallback  →  graceful degradation, cached responses     │
└─────────────────────────────────────────────────────────┘
```

---

## Principi di Architettura a Microservizi

### Single Responsibility per Servizio

Ogni microservizio deve avere un **bounded context** ben definito (Domain-Driven Design). Un servizio che cresce oltre la sua responsabilità diventa un "distributed monolith" — il peggio dei due mondi.

!!! warning "Anti-pattern: il God Service"
    Un servizio che gestisce utenti, ordini E pagamenti non è un microservizio. È un monolite spacchettato su più processi, con tutti i costi dei microservizi e nessun beneficio.

### Database per Servizio

Ogni microservizio ha il **suo** database — o almeno il suo schema isolato. Nessun servizio legge direttamente il database di un altro.

```
✅ Corretto:
  OrderService   → orders_db (PostgreSQL)
  UserService    → users_db  (PostgreSQL)
  ProductService → products_db (MongoDB)

❌ Sbagliato:
  OrderService   ──┐
  UserService    ──┼──→ shared_db
  ProductService ──┘
```

### Comunicazione Asincrona come Default

Per operazioni non critiche in termini di latenza, preferire la comunicazione asincrona via messaggi. Riduce il coupling temporale e aumenta la resilienza complessiva.

!!! tip "Regola del 2 servizi"
    Se un'operazione deve coinvolgere più di 2 servizi in modo sincrono, valuta se ha senso trasformarla in un workflow asincrono con Saga pattern.

---

## Il Developer Stack su Kubernetes

```
Developer Stack — Dal Codice al Cluster

  Source Code (Go/Java/Python/Node)
       |
       ▼
  Build → Container Image (Dockerfile ottimizzato)
       |
       ▼
  Registry (ECR/Harbor/GCR)
       |
       ▼
  Kubernetes Deployment
  ┌────────────────────────────────────────────────────┐
  │  Pod                                               │
  │  ┌─────────────────────┐  ┌─────────────────────┐ │
  │  │  App Container      │  │  Sidecar (opzionale) │ │
  │  │  - Business logic   │  │  - Envoy proxy       │ │
  │  │  - Health endpoints │  │  - Log forwarder     │ │
  │  │  - Metrics /metrics │  │  - Secret injector   │ │
  │  └─────────────────────┘  └─────────────────────┘ │
  └────────────────────────────────────────────────────┘
       |
       ▼
  Service → Ingress / API Gateway
       |
       ▼
  Osservabilità: Metriche + Log + Tracce
```

---

## Percorsi per Obiettivo

| Obiettivo | Percorso consigliato |
|---|---|
| Scegliere il linguaggio per un nuovo microservizio | Linguaggi → confronto startup/footprint/ecosystem |
| Progettare un'API robusta e versionabile | API Design → OpenAPI/gRPC → Versionamento |
| Gestire transazioni su più servizi | Integrazioni → Saga Pattern → CQRS |
| Rendere un servizio fault-tolerant | Resilienza → Circuit Breaker → Retry/Timeout |
| Testare un microservizio in isolamento | Testing → Contract Testing → Testcontainers |
| Ottimizzare il database per un servizio ad alto carico | Data Layer → Connection Pooling → Cache |

---

## Relazioni con Altre Sezioni

??? info "Containers / Kubernetes — Come gira il codice"
    Questa sezione si ferma al confine del codice applicativo. Per la containerizzazione, i Deployment K8s, i ConfigMap/Secret, i resource limits → vedi [Containers](../containers/_index.md).

??? info "Networking / Service Mesh — Resilienza a livello infrastrutturale"
    Circuit breaker e retry si possono implementare a livello di codice (Resilience4j, tenacity) OPPURE a livello di service mesh (Istio, Linkerd). Per la prospettiva infrastrutturale → [Service Mesh](../networking/service-mesh/_index.md).

??? info "Messaging — Integrazioni asincrone"
    I pattern di integrazione asincrona (Kafka, RabbitMQ, NATS) sono documentati in dettaglio nella sezione [Messaging](../messaging/_index.md). Questa sezione si concentra su *come usarli nel codice*, quella su *come configurarli*.

??? info "Security — Autenticazione e autorizzazione"
    JWT, OAuth2, mTLS tra servizi, gestione dei segreti → [Security](../security/_index.md). Questa sezione copre solo l'integrazione lato codice (come validare un JWT, come richiedere un segreto a Vault).

??? info "Monitoring — Strumentazione del codice"
    Come esporre metriche Prometheus, come generare span OpenTelemetry, come strutturare i log → [Monitoring](../monitoring/_index.md). La strumentazione è parte integrante del microservizio, non un'aggiunta.
