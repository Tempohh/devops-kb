---
title: "Envoy Proxy"
slug: envoy
category: networking
tags: [envoy, proxy, service-mesh, sidecar, xds, load-balancing, observability]
search_keywords: [envoy proxy, envoy xds, data plane, control plane, sidecar proxy, listener, cluster, route, endpoint, xds api, envoy filter, wasm, grpc, http/2, circuit breaker, outlier detection, tracing, access log, admin api, istio data plane]
parent: networking/service-mesh/_index
related: [networking/service-mesh/istio, networking/service-mesh/concetti-base, networking/protocolli/grpc]
official_docs: https://www.envoyproxy.io/docs/
status: reviewed
difficulty: advanced
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# Envoy Proxy

## Panoramica

Envoy è un proxy L4/L7 open source ad alte prestazioni, progettato da Lyft e ora gestito dalla CNCF. È il **data plane** di riferimento per service mesh come Istio e il componente centrale di molti API gateway basati su Kubernetes Gateway API (Envoy Gateway, Emissary-ingress, Contour, Gloo). A differenza di Nginx e HAProxy, Envoy è progettato nativamente per ambienti cloud-native: configurazione dinamica via API (xDS), osservabilità integrata (metriche, tracing, access log), e supporto nativo per gRPC, HTTP/2 e HTTP/3.

Envoy opera solitamente come **sidecar proxy** — un container affiancato ad ogni istanza applicativa — intercettando tutto il traffico in entrata e uscita. Questo pattern centralizza il networking (retry, circuit breaking, mTLS, tracing) senza modificare il codice applicativo.

## Prerequisiti

Questo argomento presuppone familiarità con:
- [Service Mesh — Concetti Base](concetti-base.md) — il ruolo del sidecar proxy nel service mesh, data plane vs control plane
- [HTTP/2 e HTTP/3](../protocolli/http2-http3.md) — HTTP/2 multiplexing e stream (Envoy lo usa come trasporto nativo)
- [gRPC](../protocolli/grpc.md) — gRPC usa Envoy come proxy nativo in molti deployment

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

## Concetti Chiave

### Architettura xDS — Configurazione Dinamica

Il sistema di configurazione di Envoy è basato su API gRPC/REST chiamate **xDS** (x Discovery Service):

| API | Acronimo | Gestisce |
|-----|----------|---------|
| LDS | Listener Discovery Service | Listener (porte di ascolto) |
| RDS | Route Discovery Service | Routing rules (path, header matching) |
| CDS | Cluster Discovery Service | Upstream cluster (backend services) |
| EDS | Endpoint Discovery Service | Indirizzi degli endpoint (IP:porta) |
| RTDS | Runtime Discovery Service | Feature flags runtime |
| SDS | Secret Discovery Service | Certificati TLS |

Il control plane (Istio Pilot, Consul, custom) aggiorna Envoy in tempo reale via queste API senza riavvio.

### Concetti Fondamentali

```
Traffico in entrata
      │
   Listener         ← Su quale porta/protocollo ascoltare
      │
   Filter Chain     ← Filtri L4 (TLS, TCP proxy) + L7 (HTTP, gRPC)
      │
   Router           ← Smista verso quale Cluster basandosi su host/path/headers
      │
   Cluster          ← Definisce il gruppo di backend (upstream service)
      │
   Endpoint         ← IP:porta delle singole istanze backend
      │
  Backend Service
```

### Filtri HTTP

I filtri HTTP di Envoy processano le richieste in pipeline:

```yaml
http_filters:
  - name: envoy.filters.http.jwt_authn      # Verifica JWT
  - name: envoy.filters.http.cors           # CORS
  - name: envoy.filters.http.ratelimit      # Rate limiting globale (servizio esterno)
  - name: envoy.filters.http.router         # Routing (sempre ultimo)
```

## Architettura / Come Funziona

### Configurazione Statica

```yaml
# envoy.yaml — Configurazione base
static_resources:
  listeners:
  - name: listener_0
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 10000

    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          codec_type: AUTO    # HTTP/1.1, HTTP/2 o HTTP/3 auto-detect

          # Route configuration
          route_config:
            name: local_route
            virtual_hosts:
            - name: backend
              domains: ["*"]
              routes:
              - match:
                  prefix: "/api/v1"
                route:
                  cluster: service_api
                  timeout: 5s
                  retry_policy:
                    retry_on: "5xx,connect-failure"
                    num_retries: 3
              - match:
                  prefix: "/"
                route:
                  cluster: service_frontend

          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router

  clusters:
  - name: service_api
    connect_timeout: 1s
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN

    # Circuit breaker
    circuit_breakers:
      thresholds:
      - priority: DEFAULT
        max_connections: 1000
        max_requests: 1000
        max_retries: 3

    # Health check attivo
    health_checks:
    - timeout: 1s
      interval: 5s
      unhealthy_threshold: 2
      healthy_threshold: 1
      http_health_check:
        path: "/health"

    load_assignment:
      cluster_name: service_api
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: api-service
                port_value: 8080

admin:
  address:
    socket_address:
      address: 127.0.0.1   # Admin solo su loopback (vedi Best Practices)
      port_value: 9901
```

### Circuit Breaking e Outlier Detection

Sono due meccanismi distinti. I **circuit breaker** (`circuit_breakers`, sopra) limitano le risorse verso un cluster (connessioni, richieste pendenti, retry): superata la soglia Envoy risponde subito 503 con flag `UO`, proteggendo il backend dal sovraccarico. L'**outlier detection** *espelle* temporaneamente i singoli host che falliscono, così il load balancer smette di usarli.

```yaml
clusters:
- name: backend_service
  outlier_detection:
    # Espelle l'host dopo 5 errori 5xx CONSECUTIVI
    consecutive_5xx: 5
    interval: 10s              # ogni quanto Envoy analizza gli host (sweep)
    base_ejection_time: 30s    # durata base espulsione (cresce a ogni espulsione successiva)
    max_ejection_percent: 50   # Max 50% degli endpoint rimossi contemporaneamente (default 10%)
    consecutive_gateway_failure: 5
    enforcing_consecutive_gateway_failure: 100  # default 0: senza questo il rilevamento gateway non espelle
    success_rate_minimum_hosts: 3
```

### mTLS con SDS

```yaml
# Certificati gestiti dinamicamente via SDS
transport_socket:
  name: envoy.transport_sockets.tls
  typed_config:
    "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
    common_tls_context:
      tls_certificate_sds_secret_configs:
      - name: "spiffe://cluster.local/ns/default/sa/my-service"
        sds_config:
          api_config_source:
            api_type: GRPC
            transport_api_version: V3
            grpc_services:
            - envoy_grpc:
                cluster_name: xds_cluster
      validation_context_sds_secret_config:
        name: "ROOTCA"
        sds_config: ...
```

## Configurazione & Pratica

### Admin API

```bash
# Envoy espone una Admin API sulla porta 9901

# Stato generale
curl localhost:9901/ready

# Statistiche (Prometheus-compatibili)
curl localhost:9901/stats/prometheus

# Configurazione corrente (dump completo)
curl localhost:9901/config_dump | jq .

# Cluster e loro endpoint
curl localhost:9901/clusters

# Log level dinamico
curl -X POST localhost:9901/logging?level=debug

# Draining graceful
curl -X POST localhost:9901/healthcheck/fail  # Segnala unhealthy
```

### Envoy come Sidecar con Docker

```yaml
# docker-compose.yaml
services:
  app:
    image: myapp:latest
    # NON esporre porte direttamente
    expose:
      - "8080"

  envoy:
    # Fissare una release supportata (le vecchie minor non ricevono patch di sicurezza)
    image: envoyproxy/envoy:v1.34-latest
    ports:
      - "10000:10000"            # Proxy port
      - "127.0.0.1:9901:9901"    # Admin port, solo loopback host
    volumes:
      - ./envoy.yaml:/etc/envoy/envoy.yaml
    # In container l'admin deve fare bind su 0.0.0.0 (nell'envoy.yaml) perché il port
    # mapping funzioni: l'esposizione è limitata dal "127.0.0.1:" sopra.
    command: ["envoy", "-c", "/etc/envoy/envoy.yaml"]
    depends_on:
      - app
```

### Tracing con Zipkin/Jaeger

```yaml
http_connection_manager:
  tracing:
    provider:
      name: envoy.tracers.zipkin
      typed_config:
        "@type": type.googleapis.com/envoy.config.trace.v3.ZipkinConfig
        collector_cluster: zipkin_cluster
        collector_endpoint: "/api/v2/spans"
        collector_endpoint_version: HTTP_JSON
    # Jaeger accetta Zipkin (qui) o OTLP: il tracer nativo Jaeger è stato rimosso,
    # per nuovi setup preferire envoy.tracers.opentelemetry (OTLP).
    # Campionamento 1% del traffico in produzione (value è una percentuale:
    # 100 = tutto, troppo costoso in produzione per volume di span e overhead)
    random_sampling:
      value: 1.0
```

## Best Practices

- **xDS dinamico in produzione**: non usare configurazione statica — usare control plane (Istio, Consul) per aggiornare senza riavvii
- **Admin API**: non esporre mai la porta Admin (9901) pubblicamente — solo localhost o rete interna
- **Circuit breaker**: configurare sempre outlier detection per isolare backend difettosi
- **Timeout a livelli**: `timeout` di route (richiesta totale, default 15s), `connect_timeout` di cluster (solo handshake TCP), idle timeout di connessione/stream — sono indipendenti, non si sovrascrivono: dimensionarli coerentemente (il timeout di route deve coprire retry × per-try timeout)
- **Header propagation**: propagare `x-request-id`, `x-b3-traceid` etc. — Envoy li usa per il tracing distribuito
- **Graceful shutdown**: usare `healthcheck/fail` prima di fermare Envoy per drenare le connessioni

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| `upstream connect error` | Backend non raggiungibile | Verificare endpoint e health check |
| `upstream request timeout` | Backend lento | Aumentare timeout nella route config |
| `no healthy upstream` (`UH`) | Tutti gli host unhealthy o espulsi da outlier detection | Verificare health check e outlier_detection, ridurre `max_ejection_percent` |
| 503 con flag `UO` | Circuit breaker (limiti `max_connections`/`max_pending_requests`/`max_requests`) superato | Alzare le soglie o scalare il backend; controllare `upstream_rq_pending_overflow` |
| `431 Request Header Fields Too Large` | Header troppo grandi | Aumentare `max_request_headers_kb` |
| Latenza anomala | Retry storm | Verificare retry policy, aggiungere retry budget |

```bash
# Analisi errori in tempo reale
curl -s localhost:9901/stats | grep -E "upstream_rq_(5xx|4xx|timeout|retry)"

# Verifica configurazione listener
curl -s localhost:9901/config_dump | jq '.configs[] | select(.["@type"] | contains("ListenersConfigDump"))'
```

### Scenario 1 — `no healthy upstream` (503, flag `UH`)

**Sintomo**: richieste fallite con 503 e response flag `UH`; nessun backend riceve traffico.

**Causa**: tutti gli endpoint del cluster sono marcati unhealthy (health check falliti) o espulsi da outlier detection. Con `max_ejection_percent` alto Envoy può espellere quasi tutto il cluster.

**Soluzione**: controllare lo stato per host; correggere il `/health` del backend o ridurre `max_ejection_percent`. Il panic threshold (default 50%) fa ignorare lo stato di salute quando troppi host sono unhealthy, evitando il blackout totale.

```bash
curl -s localhost:9901/clusters | grep -E "service_api::.*(health_flags|cx_active)"
curl -s localhost:9901/stats | grep -E "service_api.*(outlier_detection.ejections_active|membership_healthy)"
```

### Scenario 2 — Config xDS non applicata (NACK)

**Sintomo**: il control plane invia modifiche ma Envoy continua col comportamento vecchio.

**Causa**: Envoy rifiuta (NACK) la risorsa perché invalida (typo, `@type` errato, filtro router non ultimo); mantiene l'ultima config valida.

**Soluzione**: leggere i contatori di update rifiutati e il log del control plane/Envoy, correggere la risorsa.

```bash
curl -s localhost:9901/stats | grep -E "(update_rejected|update_failure|update_success)"
curl -s localhost:9901/config_dump?resource=dynamic_listeners | jq '.configs[].error_state'
```

### Scenario 3 — 503 con flag `UF`/`UC` o timeout `UT`

**Sintomo**: `upstream connect error`, `connection termination` o `upstream request timeout` intermittenti.

**Causa**: `UF` = connessione upstream fallita; `UC` = connessione chiusa dall'upstream (spesso keep-alive del backend più corto di quello di Envoy, che riusa una connessione già chiusa); `UT` = timeout della route (default 15s) superato.

**Soluzione**: allineare idle timeout (backend > Envoy), aumentare `timeout` di route se legittimo, limitare i retry per evitare retry storm.

```bash
# Attivare access log con %RESPONSE_FLAGS% e verificare i flag
kubectl logs <pod> -c istio-proxy | grep -E '"(UF|UC|UT|UH)"'
curl -s localhost:9901/stats | grep -E "upstream_cx_(connect_fail|destroy_remote)|upstream_rq_timeout"
```

### Scenario 4 — Connessioni rifiutate sul listener

**Sintomo**: `connection refused` sulla porta del proxy; `/ready` risponde non-200.

**Causa**: Envoy non ha ancora ricevuto LDS/CDS iniziali (stato `PRE_INITIALIZING`/`INITIALIZING`) oppure il listener non è in bind (porta occupata, address errato).

**Soluzione**: verificare stato e listener attivi; controllare conflitti di porta.

```bash
curl -s localhost:9901/ready            # LIVE solo a init completato
curl -s localhost:9901/listeners
curl -s localhost:9901/server_info | jq .state
```

## Relazioni

??? info "Istio — Control Plane per Envoy"
    Istio usa Envoy come sidecar proxy e lo configura tramite le API xDS.

    **Approfondimento →** [Istio](istio.md)

!!! note "Istio ambient mode"
    In Istio ambient mode il L4 (mTLS, identità) è gestito da `ztunnel` per nodo, un proxy Rust **non** basato su Envoy; Envoy resta nei *waypoint proxy* per le funzioni L7. Il sidecar Envoy rimane il modello classico.

??? info "Service Mesh — Concetti Base"
    Envoy implementa il data plane del pattern service mesh.

    **Approfondimento →** [Concetti Base Service Mesh](concetti-base.md)

## Riferimenti

- [Envoy Proxy Documentation](https://www.envoyproxy.io/docs/)
- [Envoy xDS API Reference](https://www.envoyproxy.io/docs/envoy/latest/api-docs/xds_protocol)
- [CNCF Envoy Project](https://www.cncf.io/projects/envoy/)
