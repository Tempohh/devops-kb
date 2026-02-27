---
title: "Linkerd"
slug: linkerd
category: networking
tags: [linkerd, service-mesh, kubernetes, mtls, rust, sidecar, osservabilità]
search_keywords: [linkerd2, linkerd service mesh, rust proxy, linkerd-proxy, ultra-light, mTLS automatico, golden signals, latency percentiles, linkerd viz, multicluster, policy, serviceprofile, traffic split, retries, timeouts, cncf, buoyant]
parent: networking/service-mesh/_index
related: [networking/service-mesh/istio, networking/service-mesh/concetti-base, networking/kubernetes/network-policies]
official_docs: https://linkerd.io/2.x/overview/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Linkerd

## Panoramica

Linkerd è un service mesh per Kubernetes, sviluppato da Buoyant e progetto CNCF graduated. Si distingue da Istio per la filosofia **operativa**: minimalismo, facilità di installazione e un proxy scritto in **Rust** (linkerd-proxy) ultra-leggero e performante, a differenza di Envoy usato da Istio. Linkerd si concentra sul fare bene le cose essenziali: **mTLS automatico**, **osservabilità dei golden signals** (latency, success rate, requests/sec) e **reliability features** (retry, timeout, circuit breaking) — senza la complessità e i CRD di Istio.

Linkerd è ideale quando si vuole ottenere sicurezza mTLS e osservabilità di base senza un overhead operativo elevato. Istio è da preferire quando si ha bisogno di traffico management avanzato (canary, mirroring, fault injection configurabile via CRD), WebAssembly extensibility, o integrazione con ecosistemi non-Kubernetes.

## Concetti Chiave

### Linkerd vs Istio

| Aspetto | Linkerd | Istio |
|---------|---------|-------|
| Proxy | linkerd-proxy (Rust) | Envoy (C++) |
| Footprint | ~10MB proxy, ~200MB control plane | ~60MB proxy, ~1GB+ control plane |
| Installazione | Linkerd CLI, semplice | Helm/istioctl, più complesso |
| mTLS | Automatico, cert rotation | Automatico ma più configurabile |
| Traffic management | ServiceProfile, HTTPRoute | VirtualService, DestinationRule (ricchi) |
| Extensibility | Limitata | WebAssembly, Lua |
| Multicluster | Sì (Service Mirroring) | Sì (più complesso) |
| Curva di apprendimento | Bassa | Alta |

### Golden Signals

Linkerd misura automaticamente i **golden signals** per ogni servizio e route:

- **Success Rate**: percentuale di richieste riuscite (2xx vs 4xx/5xx)
- **Request Rate**: richieste per secondo (RPS)
- **Latency Distribution**: p50, p95, p99, p999

Queste metriche sono disponibili senza nessuna instrumentazione del codice applicativo — Linkerd le deriva intercettando il traffico nel proxy.

## Architettura / Come Funziona

### Componenti

```
┌─────────────────────────────────────────────────┐
│                   Control Plane                  │
│   destination   │   identity   │   proxy-injector│
│  (discovery,    │  (cert mgmt, │  (mutating       │
│   routing)      │   mTLS)      │   webhook)       │
└────────────────────────────────────┬────────────┘
                                     │ xDS-like API
        ┌────────────────────────────┼─────────────────┐
        │                            │                  │
   ┌────┴─────┐                ┌────┴─────┐      ┌────┴─────┐
   │  Pod A   │                │  Pod B   │      │  Pod C   │
   │ ┌──────┐ │                │ ┌──────┐ │      │ ┌──────┐ │
   │ │ App  │ │                │ │ App  │ │      │ │ App  │ │
   │ └──────┘ │                │ └──────┘ │      │ └──────┘ │
   │ ┌──────┐ │◄── mTLS ──────►│ ┌──────┐ │      │ ┌──────┐ │
   │ │proxy │ │                │ │proxy │ │      │ │proxy │ │
   │ └──────┘ │                │ └──────┘ │      │ └──────┘ │
   └──────────┘                └──────────┘      └──────────┘
        Data Plane (linkerd-proxy sidecar)
```

### mTLS Automatico

Linkerd inietta certificati mTLS in ogni pod e li ruota ogni 24 ore senza interruzione del servizio. Il trust anchor (Root CA) è gestito dal componente `identity`:

```
1. Pod A vuole comunicare con Pod B
2. Il proxy di A chiede un certificato al control plane identity
3. identity rilascia un certificato con SPIFFE ID:
   spiffe://cluster.local/ns/default/sa/service-a
4. Il proxy di A usa questo cert per TLS con il proxy di B
5. Il proxy di B verifica il cert e autorizza la connessione
6. Tutto trasparente per l'applicazione
```

### ServiceProfile — Routing e Reliability

`ServiceProfile` è il CRD principale di Linkerd per definire comportamento per singola route:

```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: users-api.default.svc.cluster.local
  namespace: default
spec:
  routes:
  - name: "GET /users/{id}"
    condition:
      method: GET
      pathRegex: "/users/[^/]+"
    responseClasses:
    - condition:
        status:
          min: 500
          max: 599
      isFailure: true  # 5xx conta come failure per success rate

    # Retry automatico sulle richieste che falliscono
    retryBudget:
      retryRatio: 0.2        # Max 20% di retry in più del traffico originale
      minRetriesPerSecond: 10
      ttl: 10s

    timeout: 500ms          # Timeout per questa route specifica

  - name: "POST /users"
    condition:
      method: POST
      pathRegex: "/users"
    # No retry per POST (non idempotente)
    timeout: 2s
```

## Configurazione & Pratica

### Installazione

```bash
# Installa CLI Linkerd
curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | sh
export PATH=$PATH:$HOME/.linkerd2/bin

# Pre-flight check
linkerd check --pre

# Installa control plane
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -

# Verifica installazione
linkerd check

# Installa Linkerd Viz (dashboard e metriche)
linkerd viz install | kubectl apply -f -
linkerd viz check

# Apri dashboard
linkerd viz dashboard
```

### Inject del Proxy

```bash
# Metodo 1: Annotazione namespace (auto-inject su tutti i pod)
kubectl annotate namespace default linkerd.io/inject=enabled

# Metodo 2: Inject manuale di un deployment
kubectl get deploy my-app -o yaml \
  | linkerd inject - \
  | kubectl apply -f -

# Verifica che il proxy sia stato iniettato
linkerd check --proxy -n default

# Statistiche in tempo reale
linkerd viz stat deploy
linkerd viz stat -n default deploy/my-app

# Top delle route con più traffico
linkerd viz top deploy/my-app

# Tap — ispezione del traffico live
linkerd viz tap deploy/my-app
```

### Output di linkerd viz stat

```bash
$ linkerd viz stat deploy -n production
NAME          MESHED  SUCCESS     RPS  LATENCY_P50  LATENCY_P95  LATENCY_P99
api-gateway   3/3      99.8%  125.3rps         12ms         45ms         98ms
user-service  2/2      99.9%   48.2rps          8ms         23ms         67ms
order-service 3/3      97.2%   31.1rps         34ms        201ms        487ms
```

### Multicluster con Service Mirroring

```bash
# Cluster source (esporta il servizio)
linkerd multicluster install | kubectl apply -f -
linkerd multicluster link --cluster-name east | kubectl apply -f -

# Cluster target (importa il servizio)
# Il ServiceMirror crea automaticamente un Service mirror per ogni
# Service annotato con mirror.linkerd.io/exported=true

# Annotare il service da esportare nel cluster source
kubectl annotate svc user-service mirror.linkerd.io/exported=true

# Nel cluster target comparirà automaticamente:
# user-service-east.default.svc.cluster.local
```

### Policy — Controllo Accesso

```yaml
# Server: definisce chi può accedere a una porta
apiVersion: policy.linkerd.io/v1beta3
kind: Server
metadata:
  name: user-service-grpc
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: user-service
  port: 50051
  proxyProtocol: gRPC

---
# ServerAuthorization: chi può accedere al Server
apiVersion: policy.linkerd.io/v1beta3
kind: ServerAuthorization
metadata:
  name: allow-api-gateway
  namespace: default
spec:
  server:
    name: user-service-grpc
  client:
    meshTLS:
      serviceAccounts:
      - name: api-gateway
        namespace: default
```

## Best Practices

- **Iniziare con mTLS e osservabilità**: il valore immediato di Linkerd — non c'è bisogno di configurare nulla di complesso
- **ServiceProfile per ogni servizio**: definire le route con timeout e retry — iniziare dai servizi critici
- **Namespace injection**: preferire l'annotazione al namespace piuttosto che inject manuale pod per pod
- **Monitorare success rate, non solo availability**: un servizio può essere "up" ma con 30% di errori — Linkerd lo mostra subito
- **Retry budget, non retry illimitati**: il `retryBudget` previene retry storm durante incidenti
- **Policy per default-deny**: usare Server + ServerAuthorization per micro-segmentazione

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Pod senza sidecar iniettato | Namespace non annotato | `kubectl annotate ns <ns> linkerd.io/inject=enabled` |
| Success rate bassa | Errori applicativi o infra | `linkerd viz tap` per ispezionare traffico live |
| mTLS non funziona | Identity non raggiungibile | `linkerd check` per verificare control plane |
| `linkerd check` fallisce | Certificati scaduti | `linkerd upgrade --reset-identities` |
| Latenze alte | Proxy overhead | Verificare CPU limits sul proxy container |

```bash
# Debug connettività tra due pod
linkerd viz tap pod/pod-a --to pod/pod-b

# Verifica certificati mTLS
linkerd identity pod/my-pod

# Log del proxy
kubectl logs pod/my-pod -c linkerd-proxy
```

## Relazioni

??? info "Istio — Service Mesh alternativo"
    Istio offre più funzionalità di traffic management a costo di maggiore complessità.

    **Approfondimento →** [Istio](istio.md)

??? info "Concetti Base Service Mesh"
    Architettura sidecar, data plane e control plane.

    **Approfondimento →** [Concetti Base](concetti-base.md)

## Riferimenti

- [Linkerd Documentation](https://linkerd.io/2.x/overview/)
- [Linkerd vs Istio Comparison](https://buoyant.io/resources/linkerd-vs-istio)
- [CNCF Linkerd Project](https://www.cncf.io/projects/linkerd/)
