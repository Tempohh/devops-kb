---
title: "OpenTelemetry Collector su Kubernetes"
slug: otel-collector-kubernetes
category: monitoring
tags: [opentelemetry, otel-collector, kubernetes, observability, metrics, tracing, logs, daemonset, deployment, operator]
search_keywords: [OTel Collector, OpenTelemetry Collector, otelcol, OTLP, collector kubernetes, collector k8s, DaemonSet collector, gateway collector, sidecar collector, OpenTelemetry Operator, OTel Operator, cert-manager, auto-instrumentation, zero-code instrumentation, k8sattributes, filelog receiver, kubeletstats, memory_limiter, batch processor, prometheusremotewrite, collector helm, opentelemetry-collector helm, collector agent, collector gateway, pipeline telemetria, infrastruttura osservabilità, otelcol_receiver, otelcol_exporter, Instrumentation CRD, OpenTelemetryCollector CRD, resource detection, arricchimento metadati k8s, collector sizing, collector RBAC]
parent: monitoring/tools/_index
related: [monitoring/fondamentali/opentelemetry, monitoring/tools/prometheus, monitoring/tools/loki, monitoring/tools/jaeger-tempo, monitoring/tools/grafana]
official_docs: https://opentelemetry.io/docs/collector/
status: complete
difficulty: advanced
last_updated: 2026-03-31
---

# OpenTelemetry Collector su Kubernetes

## Panoramica

L'**OpenTelemetry Collector** è il componente infrastrutturale che raccoglie, processa ed esporta metriche, tracce e log verso i backend appropriati (Prometheus, Tempo/Jaeger, Loki). Su Kubernetes rappresenta il **layer intermedio** tra le applicazioni instrumentate con SDK OTel e i sistemi di storage/visualizzazione: evita che ogni applicazione debba configurare direttamente l'endpoint del backend, centralizza il processing (batching, enrichment, sampling) e consente di cambiare backend senza toccare il codice applicativo.

Si usa quando si vuole:
- raccogliere log dai container via `filelog` senza dipendere da DaemonSet separati (es. Fluentd)
- arricchire ogni segnale con metadati Kubernetes (namespace, pod, deployment, node)
- instradare metriche → Prometheus, tracce → Tempo/Jaeger, log → Loki con un'unica pipeline configurabile
- abilitare auto-instrumentation zero-code tramite l'Operator

Non si usa in sostituzione dei backend di storage (Prometheus, Loki, Tempo): il Collector non conserva dati, li instrada.

!!! note "Contesto nella KB"
    Questo documento copre il **layer infrastrutturale** del Collector su K8s. Per la teoria OTel (SDK, segnali, context propagation) vedi [OpenTelemetry](../fondamentali/opentelemetry.md). Per il lato applicativo (come instrumentare il codice) vedi `dev/resilienza/observability-code.md`.

---

## Concetti Chiave

### Pipeline: Receivers → Processors → Exporters

Ogni Collector è configurato come una **pipeline** di tre stadi:

| Stadio | Ruolo | Esempi |
|---|---|---|
| **Receivers** | Ingestione dati da sorgenti diverse | `otlp`, `kubeletstats`, `filelog`, `prometheus` |
| **Processors** | Trasformazione, arricchimento, filtraggio, batching | `k8sattributes`, `batch`, `memory_limiter`, `resourcedetection` |
| **Exporters** | Invio ai backend | `prometheusremotewrite`, `otlp/tempo`, `loki`, `otlp/gateway` |

Una pipeline è tipata per segnale: `traces`, `metrics`, `logs`. Un Collector può eseguire più pipeline in parallelo.

```yaml
# Struttura logica di una pipeline
service:
  pipelines:
    metrics:
      receivers: [otlp, kubeletstats]
      processors: [memory_limiter, k8sattributes, batch]
      exporters: [prometheusremotewrite]
    traces:
      receivers: [otlp]
      processors: [memory_limiter, k8sattributes, batch]
      exporters: [otlp/tempo]
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, k8sattributes, batch]
      exporters: [loki]
```

### Topologie di Deployment

| Modalità | Workload K8s | Raccolta tipica | Quando usarla |
|---|---|---|---|
| **Agent (DaemonSet)** | 1 pod per nodo | Log da `/var/log/pods`, metriche nodo, span locali | Raccolta infrastrutturale su ogni nodo |
| **Gateway (Deployment)** | N repliche centrali | Riceve da Agent, fa batching/routing verso backend | Processing centrale, fan-out verso più backend |
| **Sidecar** | 1 container per pod | Telemetria isolata per tenant o app legacy | Multi-tenancy, isolamento, app senza SDK OTel |

!!! tip "Pattern raccomandato per produzione"
    **DaemonSet (Agent) + Deployment (Gateway)**. L'Agent è leggero e raccoglie dati locali al nodo; il Gateway centralizza il processing pesante (batching ampio, resource detection, fan-out verso più backend). Questo separa le responsabilità e permette di scalare il Gateway indipendentemente.

---

## Architettura / Come Funziona

### Flusso dati: Agent DaemonSet → Gateway → Backend

```
┌─────────────────────────────────────────────────────────┐
│                      NODO K8S                           │
│  ┌──────────────┐  OTLP/gRPC   ┌─────────────────────┐ │
│  │  App Pod     │ ────────────▶│  OTel Agent         │ │
│  │  (SDK OTel)  │              │  (DaemonSet)        │ │
│  └──────────────┘              │                     │ │
│                                │  Receivers:         │ │
│  ┌──────────────┐              │  - otlp             │ │
│  │  /var/log/   │ ─filelog───▶ │  - kubeletstats     │ │
│  │  pods/       │              │  - filelog          │ │
│  └──────────────┘              │                     │ │
│                                │  Processors:        │ │
│                                │  - k8sattributes    │ │
│                                │  - memory_limiter   │ │
│                                │  - batch            │ │
└────────────────────────────────┴─────────┬───────────┘ │
                                           │ OTLP/gRPC
                                           ▼
                              ┌─────────────────────────┐
                              │  OTel Gateway           │
                              │  (Deployment, N repliche)│
                              │                         │
                              │  Processors:            │
                              │  - batch (ampio)        │
                              │  - resourcedetection    │
                              │                         │
                              │  Exporters:             │
                              │  - prometheusremotewrite│
                              │  - otlp/tempo           │
                              │  - loki                 │
                              └────────────┬────────────┘
                                           │
                    ┌──────────────────────┼──────────────┐
                    ▼                      ▼              ▼
              Prometheus               Tempo/Jaeger      Loki
```

### K8s Attributes Processor

Il `k8sattributes` processor arricchisce ogni segnale con metadati K8s interrogando l'API server:

- `k8s.namespace.name`
- `k8s.pod.name`, `k8s.pod.uid`
- `k8s.deployment.name`, `k8s.replicaset.name`
- `k8s.node.name`
- `k8s.container.name`

Questo è fondamentale per poter filtrare/aggregare in Grafana per namespace o deployment senza che le applicazioni debbano propagare questi attributi manualmente.

!!! warning "RBAC obbligatorio per k8sattributes"
    Il collector deve poter fare `list` e `watch` su `pods`, `namespaces`, `replicasets`, `deployments`. Senza il ClusterRole corretto il processor si avvia ma non arricchisce i segnali — i dati arrivano senza metadati K8s e il problema è silenzioso. Verificare sempre con `kubectl logs` del collector all'avvio.

---

## Configurazione & Pratica

### Installazione con Helm Chart (approccio semplice)

```bash
# Aggiungere il repo Helm di OpenTelemetry
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Installare il collector come DaemonSet (Agent)
helm install otel-agent open-telemetry/opentelemetry-collector \
  --namespace monitoring \
  --create-namespace \
  --values otel-agent-values.yaml

# Installare il collector come Deployment (Gateway)
helm install otel-gateway open-telemetry/opentelemetry-collector \
  --namespace monitoring \
  --values otel-gateway-values.yaml
```

### Configurazione Agent DaemonSet (otel-agent-values.yaml)

```yaml
mode: daemonset

# Resource limits per il DaemonSet — sizing conservativo per nodo
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 200m
    memory: 512Mi

# ServiceAccount con RBAC per k8sattributes
serviceAccount:
  create: true
  name: otel-collector-agent

clusterRole:
  create: true
  rules:
    - apiGroups: [""]
      resources: ["pods", "namespaces", "nodes", "nodes/proxy"]
      verbs: ["get", "list", "watch"]
    - apiGroups: ["apps"]
      resources: ["replicasets", "deployments"]
      verbs: ["get", "list", "watch"]

config:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

    # Metriche del kubelet: CPU, memoria, rete per ogni pod/container/nodo
    kubeletstats:
      collection_interval: 30s
      auth_type: serviceAccount
      endpoint: "https://${env:K8S_NODE_NAME}:10250"
      insecure_skip_verify: true
      metric_groups: [node, pod, container]

    # Log dai container via file system del nodo
    filelog:
      include:
        - /var/log/pods/*/*/*.log
      exclude:
        - /var/log/pods/monitoring_*/*.log  # evita loop: log del collector stesso
      include_file_path: true
      include_file_name: false
      operators:
        # Parser per formato log containerd/Docker
        - type: container
          id: container-parser

  processors:
    # CRITICO: previene OOM — deve essere il primo processor in ogni pipeline
    memory_limiter:
      check_interval: 1s
      limit_percentage: 80      # usa max 80% del memory limit del container
      spike_limit_percentage: 25

    # Arricchisce ogni segnale con metadati K8s
    k8sattributes:
      auth_type: serviceAccount
      passthrough: false
      extract:
        metadata:
          - k8s.namespace.name
          - k8s.deployment.name
          - k8s.replicaset.name
          - k8s.statefulset.name
          - k8s.daemonset.name
          - k8s.pod.name
          - k8s.pod.uid
          - k8s.node.name
          - k8s.container.name
        labels:
          - tag_name: app
            key: app
            from: pod
          - tag_name: version
            key: app.kubernetes.io/version
            from: pod
      pod_association:
        - sources:
            - from: resource_attribute
              name: k8s.pod.ip
        - sources:
            - from: resource_attribute
              name: k8s.pod.uid
        - sources:
            - from: connection

    # Batching per ridurre il numero di request verso il Gateway
    batch:
      send_batch_size: 512
      timeout: 1s
      send_batch_max_size: 1024

  exporters:
    # Forwarda tutto al Gateway centrale
    otlp/gateway:
      endpoint: otel-gateway-collector.monitoring.svc.cluster.local:4317
      tls:
        insecure: true  # interno al cluster — in prod usare mTLS

  service:
    pipelines:
      metrics:
        receivers: [otlp, kubeletstats]
        processors: [memory_limiter, k8sattributes, batch]
        exporters: [otlp/gateway]
      traces:
        receivers: [otlp]
        processors: [memory_limiter, k8sattributes, batch]
        exporters: [otlp/gateway]
      logs:
        receivers: [otlp, filelog]
        processors: [memory_limiter, k8sattributes, batch]
        exporters: [otlp/gateway]

# Monta /var/log/pods dal nodo host (necessario per filelog)
extraVolumes:
  - name: varlogpods
    hostPath:
      path: /var/log/pods
extraVolumeMounts:
  - name: varlogpods
    mountPath: /var/log/pods
    readOnly: true
```

### Configurazione Gateway Deployment (otel-gateway-values.yaml)

```yaml
mode: deployment
replicaCount: 2  # HA — scalare in base al throughput

resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

config:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

  processors:
    memory_limiter:
      check_interval: 1s
      limit_percentage: 80
      spike_limit_percentage: 25

    # Batching più ampio nel Gateway: aggrega da tutti gli Agent
    batch:
      send_batch_size: 1000
      timeout: 1s
      send_batch_max_size: 2000

    # Aggiunge attributi cloud/infra rilevati automaticamente
    resourcedetection:
      detectors: [env, k8snode, gcp, aws, azure]
      timeout: 2s
      override: false

  exporters:
    # Metriche → Prometheus (remote write)
    prometheusremotewrite:
      endpoint: http://prometheus-server.monitoring.svc.cluster.local:9090/api/v1/write
      tls:
        insecure: true
      resource_to_telemetry_conversion:
        enabled: true  # converte resource attributes in labels Prometheus

    # Tracce → Grafana Tempo
    otlp/tempo:
      endpoint: http://tempo.monitoring.svc.cluster.local:4317
      tls:
        insecure: true

    # Log → Loki
    loki:
      endpoint: http://loki.monitoring.svc.cluster.local:3100/loki/api/v1/push
      tls:
        insecure: true
      default_labels_enabled:
        exporter: false
        job: true

  service:
    pipelines:
      metrics:
        receivers: [otlp]
        processors: [memory_limiter, resourcedetection, batch]
        exporters: [prometheusremotewrite]
      traces:
        receivers: [otlp]
        processors: [memory_limiter, batch]
        exporters: [otlp/tempo]
      logs:
        receivers: [otlp]
        processors: [memory_limiter, batch]
        exporters: [loki]
```

### Installazione con OpenTelemetry Operator

L'Operator aggiunge CRD Kubernetes per gestire il lifecycle del Collector e l'auto-instrumentation.

```bash
# Prerequisito: cert-manager (necessario per i webhook dell'Operator)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl wait --for=condition=ready pod -l app=cert-manager -n cert-manager --timeout=120s

# Installare l'Operator via Helm
helm install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace monitoring \
  --set "manager.collectorImage.repository=otel/opentelemetry-collector-contrib" \
  --set admissionWebhooks.certManager.enabled=true
```

### CRD OpenTelemetryCollector (via Operator)

```yaml
# otel-collector-cr.yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel-agent
  namespace: monitoring
spec:
  mode: daemonset          # daemonset | deployment | sidecar | statefulset
  serviceAccount: otel-collector-agent
  resources:
    limits:
      cpu: 200m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 256Mi

  # Volumi host per filelog
  volumes:
    - name: varlogpods
      hostPath:
        path: /var/log/pods
  volumeMounts:
    - name: varlogpods
      mountPath: /var/log/pods
      readOnly: true

  config: |
    receivers:
      otlp:
        protocols:
          grpc: {}
          http: {}
      kubeletstats:
        collection_interval: 30s
        auth_type: serviceAccount
        endpoint: "https://${K8S_NODE_NAME}:10250"
        insecure_skip_verify: true
      filelog:
        include: [/var/log/pods/*/*/*.log]
        operators:
          - type: container
            id: container-parser
    processors:
      memory_limiter:
        check_interval: 1s
        limit_percentage: 80
        spike_limit_percentage: 25
      k8sattributes: {}
      batch: {}
    exporters:
      otlp/gateway:
        endpoint: otel-gateway-collector:4317
        tls:
          insecure: true
    service:
      pipelines:
        metrics:
          receivers: [otlp, kubeletstats]
          processors: [memory_limiter, k8sattributes, batch]
          exporters: [otlp/gateway]
        traces:
          receivers: [otlp]
          processors: [memory_limiter, k8sattributes, batch]
          exporters: [otlp/gateway]
        logs:
          receivers: [otlp, filelog]
          processors: [memory_limiter, k8sattributes, batch]
          exporters: [otlp/gateway]
```

### Auto-Instrumentation con CRD Instrumentation

L'Operator può iniettare automaticamente gli SDK OTel come init container, senza modificare il codice applicativo:

```yaml
# instrumentation.yaml — definisce la configurazione per linguaggio
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: auto-instrumentation
  namespace: monitoring
spec:
  # Endpoint del Collector dove inviare la telemetria
  exporter:
    endpoint: http://otel-agent-collector.monitoring.svc.cluster.local:4318

  propagators:
    - tracecontext  # W3C Trace Context
    - baggage
    - b3            # compatibilità Zipkin

  sampler:
    type: parentbased_traceidratio
    argument: "0.1"   # 10% sampling in produzione

  java:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:latest
    env:
      - name: OTEL_INSTRUMENTATION_JDBC_ENABLED
        value: "true"

  python:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:latest

  nodejs:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-nodejs:latest

  dotnet:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-dotnet:latest
```

```yaml
# Deployment che usa auto-instrumentation Java — basta l'annotation
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spring-app
  namespace: production
spec:
  template:
    metadata:
      annotations:
        # Inietta l'agent Java OTel come init container
        instrumentation.opentelemetry.io/inject-java: "monitoring/auto-instrumentation"
        # Per Python:  instrumentation.opentelemetry.io/inject-python: "monitoring/auto-instrumentation"
        # Per Node.js: instrumentation.opentelemetry.io/inject-nodejs: "monitoring/auto-instrumentation"
    spec:
      containers:
        - name: app
          image: spring-app:latest
          # Nessuna modifica al codice — l'agent viene iniettato dall'Operator
```

---

## Best Practices

### Memory Limiter — Mai omettere

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    # limit_percentage: % della memoria del container (non della RAM del nodo)
    limit_percentage: 80
    spike_limit_percentage: 25
    # Con questi valori, su un container da 512Mi:
    # hard limit = 409Mi, spike limit = 128Mi
    # Quando si supera il limit, il processor inizia a droppare dati (refuse)
    # Quando si supera hard limit, il processor dropa tutto fino a rientrare
```

!!! warning "Ordine dei processor"
    `memory_limiter` DEVE essere il **primo** processor in ogni pipeline. Se lo si mette dopo `k8sattributes` o `batch`, i dati sono già stati arricchiti/bufferizzati quando si raggiunge il limite — si spreca memoria senza protezione.

### Sizing DaemonSet vs Gateway

| Componente | CPU Request | CPU Limit | Memory Request | Memory Limit | Note |
|---|---|---|---|---|---|
| Agent DaemonSet | 100m | 200m | 256Mi | 512Mi | Per nodo con ~100 pod/nodo |
| Gateway (baseline) | 500m | 1000m | 512Mi | 1Gi | Per cluster fino a ~500 pod |
| Gateway (high throughput) | 1000m | 2000m | 1Gi | 2Gi | Oltre 1000 pod o alto trace rate |

Monitorare `otelcol_process_memory_rss` per verificare che si stia effettivamente entro i limiti.

### Regola per memory_limiter

```
limit_mib = floor(container_memory_limit_mib * 0.80)
spike_limit_mib = floor(container_memory_limit_mib * 0.25)
```

### RBAC minimale per k8sattributes

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: otel-collector-k8sattributes
rules:
  - apiGroups: [""]
    resources: ["pods", "namespaces", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["replicasets", "deployments", "statefulsets", "daemonsets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: otel-collector-k8sattributes
subjects:
  - kind: ServiceAccount
    name: otel-collector-agent
    namespace: monitoring
roleRef:
  kind: ClusterRole
  name: otel-collector-k8sattributes
  apiGroup: rbac.authorization.k8s.io
```

### Anti-pattern da evitare

- **Non usare solo Deployment per raccogliere log**: senza DaemonSet non si accede a `/var/log/pods` di ogni nodo. Il filelog receiver su un Deployment centrale non può vedere i file di tutti i nodi.
- **Non omettere il `batch` processor**: senza batching ogni span/metrica genera una singola request HTTP verso il backend. Su cluster di medie dimensioni questo satura i backend e introduce latenza elevata.
- **Non configurare filelog senza `exclude` per i propri log**: il collector legge i propri log e li reinvia → loop infinito. Sempre escludere il namespace/pod del collector.
- **Non usare `insecure: true` fuori dal cluster**: il flag è accettabile per traffico interno al cluster (svc.cluster.local), ma mai per endpoint esterni o cross-cluster.

---

## Troubleshooting

### Scenario 1: Segnali arrivano senza attributi K8s (namespace, pod non presenti)

**Sintomo:** Span e metriche arrivano ai backend ma mancano i label `k8s.namespace.name`, `k8s.pod.name`.

**Causa:** Il `k8sattributes` processor non riesce ad arricchire i segnali. Possibili cause:
1. RBAC mancante — il collector non può fare `list/watch` su pods/namespaces
2. Il processor non è nella pipeline (dimenticato in `service.pipelines`)
3. `pod_association` non trova corrispondenza (l'IP del pod non è propagato)

**Soluzione:**
```bash
# Verificare RBAC
kubectl auth can-i list pods --as=system:serviceaccount:monitoring:otel-collector-agent
kubectl auth can-i watch namespaces --as=system:serviceaccount:monitoring:otel-collector-agent

# Controllare i log del collector per errori k8sattributes
kubectl logs -l app.kubernetes.io/name=opentelemetry-collector -n monitoring | grep -i k8sattr

# Verificare che il processor sia nella pipeline
kubectl get configmap -n monitoring -o yaml | grep -A5 "k8sattributes"
```

### Scenario 2: Collector in OOMKill continuo

**Sintomo:** Pod del collector con `OOMKilled`, restart loop visibile con `kubectl get pods`.

**Causa:** `memory_limiter` assente o mal configurato; oppure picchi di telemetria (es. deploy massivo) superano il limite.

**Soluzione:**
```bash
# Verificare la causa del restart
kubectl describe pod <otel-pod-name> -n monitoring | grep -A10 "Last State"

# Controllare le metriche interne del collector
kubectl port-forward svc/otel-agent-collector -n monitoring 8888:8888
curl http://localhost:8888/metrics | grep otelcol_process_memory

# Aumentare il memory limit e ricalcolare il memory_limiter
# Se il container ha 512Mi e continua a crashare → portare a 1Gi
# Poi impostare: limit_percentage: 80 → limit_mib ~= 819Mi
```

### Scenario 3: Log dei container non arrivano a Loki

**Sintomo:** Metriche e tracce funzionano, ma Loki non riceve log dai container.

**Causa:** Il DaemonSet non ha il volume `hostPath: /var/log/pods` montato, oppure il `filelog` receiver ha un pattern `include` errato.

**Soluzione:**
```bash
# Verificare che il volume sia montato
kubectl exec -it <otel-daemonset-pod> -n monitoring -- ls /var/log/pods/

# Se il directory è vuoto o non accessibile, controllare il manifest del DaemonSet
kubectl get daemonset otel-agent-collector -n monitoring -o yaml | grep -A20 "volumes:"

# Testare il pattern del filelog manualmente
kubectl exec -it <otel-daemonset-pod> -n monitoring -- \
  ls /var/log/pods/production_myapp-*/myapp/*.log
```

### Scenario 4: Throughput elevato — span/metriche droppati

**Sintomo:** `otelcol_exporter_send_failed_metric_points` o `otelcol_exporter_send_failed_spans` > 0.

**Causa:** Il backend non riesce ad assorbire il rate del Collector, oppure il Gateway è sottodimensionato.

**Soluzione:**
```bash
# Metriche interne del Collector (porta 8888 o 55679)
kubectl port-forward svc/otel-gateway-collector -n monitoring 8888:8888

# Metriche chiave da monitorare
curl -s http://localhost:8888/metrics | grep -E \
  "otelcol_receiver_accepted|otelcol_exporter_sent|otelcol_exporter_send_failed|otelcol_processor_dropped"

# zPages per debugging live (porta 55679)
kubectl port-forward svc/otel-gateway-collector -n monitoring 55679:55679
# Aprire: http://localhost:55679/debug/tracez
```

```yaml
# Tuning del batch processor per ridurre il rate verso il backend
processors:
  batch:
    send_batch_size: 2000      # aumentare batch size
    timeout: 5s                # aumentare timeout per accumulare più dati
    send_batch_max_size: 4000
```

---

## Relazioni

??? info "OpenTelemetry — Teoria e SDK"
    OTel Collector è il componente infrastrutturale; il protocollo OTLP, i concetti di span/trace/metric e gli SDK per instrumentare il codice sono coperti separatamente.

    **Approfondimento completo →** [OpenTelemetry](../fondamentali/opentelemetry.md)

??? info "Prometheus — Backend metriche"
    Il Collector esporta metriche via `prometheusremotewrite`. Prometheus ha un proprio ecosistema (PromQL, Alertmanager, recording rules) indipendente dal Collector.

    **Approfondimento completo →** [Prometheus](prometheus.md)

??? info "Loki — Backend log"
    Il Collector raccoglie log con `filelog` e li invia a Loki. Loki gestisce indexing, retention e query con LogQL.

    **Approfondimento completo →** [Loki](loki.md)

??? info "Jaeger & Tempo — Backend tracce"
    Il Collector forwarda tracce via OTLP ai backend di tracing. La scelta tra Jaeger e Tempo dipende dai requisiti di storage e integrazione Grafana.

    **Approfondimento completo →** [Jaeger & Grafana Tempo](jaeger-tempo.md)

---

## Riferimenti

- [OpenTelemetry Collector — documentazione ufficiale](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Operator — Getting Started](https://opentelemetry.io/docs/kubernetes/operator/)
- [Helm Chart opentelemetry-collector](https://github.com/open-telemetry/opentelemetry-helm-charts)
- [k8sattributes processor — riferimento](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/k8sattributesprocessor)
- [filelog receiver — riferimento](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/filelogreceiver)
- [memory_limiter processor — riferimento](https://github.com/open-telemetry/opentelemetry-collector/tree/main/processor/memorylimiterprocessor)
