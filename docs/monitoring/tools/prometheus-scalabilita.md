---
title: "Prometheus: Scalabilità e Long-term Storage"
slug: prometheus-scalabilita
category: monitoring
tags: [prometheus, thanos, victoriametrics, mimir, scalabilita, long-term-storage, ha, multi-cluster, remote-write]
search_keywords: [prometheus scalabilità, prometheus ha, prometheus alta disponibilità, thanos, victoriametrics, grafana mimir, cortex, long-term storage, metriche lungo termine, multi-cluster monitoring, remote write, prometheus limiti, cardinality, tsdb limiti, object storage metriche, prometheus federation, thanos sidecar, thanos query, thanos store gateway, thanos compactor, thanos ruler, victoriametrics cluster, vmagent, vmcluster, prometheus beyond single node, prometheus retention, prometheus scalable, prometheus 10 cluster, prometheus distributed, time series database scalabile]
parent: monitoring/tools/_index
related: [monitoring/tools/prometheus, monitoring/tools/grafana, monitoring/alerting/alertmanager, monitoring/fondamentali/opentelemetry]
official_docs: https://thanos.io/tip/thanos/getting-started.md/
status: complete
difficulty: advanced
last_updated: 2026-04-04
---

# Prometheus: Scalabilità e Long-term Storage

## Panoramica

Prometheus è eccellente per il monitoring di un singolo cluster o ambiente, ma ha limiti architetturali intrinseci che emergono quando si scala: nessuna HA nativa per lo storage, retention limitata dalla RAM e dallo spazio disco locale, impossibilità di query cross-cluster out-of-the-box. Questo documento copre le due soluzioni dominanti per superare questi limiti — **Thanos** e **VictoriaMetrics** — più una menzione di Grafana Mimir come terza opzione cloud-native. L'obiettivo è dare strumenti pratici per chi gestisce 5+ cluster, necessita di retention > 30 giorni, o deve consolidare metriche da ambienti eterogenei.

## Concetti Chiave

### Perché Prometheus da Solo Non Basta

!!! warning "Limiti reali di Prometheus single-node"
    Questi limiti non sono bug ma scelte architetturali deliberate. Prometheus è progettato per semplicità e affidabilità locale. Conoscere i limiti è il primo passo per scegliere la soluzione giusta.

| Limite | Soglia critica | Impatto |
|--------|---------------|---------|
| **RAM per alta cardinality** | >5-10M time series attive | OOM, TSDB corrotto al restart |
| **Storage locale** | Disco fisico del nodo | Nessuna ridondanza, perdita dati se il nodo muore |
| **Retention pratica** | 15-90 giorni (dipende da disco e RAM) | Non adatto a compliance, analisi storiche |
| **HA nativa** | Assente | Finestra di downtime durante restart/aggiornamento |
| **Query cross-cluster** | Non supportata nativamente | Nessuna vista unificata su più Prometheus |
| **Multi-tenancy** | Assente | Tutti gli utenti vedono tutti i dati |

### Approcci di Scalabilità

```
┌────────────────────────────────────────────────────────────┐
│           Scegli in base al tuo scenario                   │
│                                                            │
│  1-3 cluster, retention <90d  →  Prometheus + remote_write │
│                                   a VictoriaMetrics single  │
│                                                            │
│  3-20 cluster, retention 1-2y →  Thanos (architettura      │
│                                   a componenti, object store)│
│                                                            │
│  >20 cluster, multi-tenant    →  VictoriaMetrics Cluster   │
│                                   oppure Grafana Mimir      │
└────────────────────────────────────────────────────────────┘
```

## Architettura / Come Funziona

### Thanos — Architettura a Componenti

Thanos estende Prometheus senza modificarlo. Si compone di componenti indipendenti che collaborano tramite gRPC e un object store condiviso (S3, GCS, Azure Blob).

```
┌─────────────────────────────────────────────────────────────┐
│  Cluster A                    Cluster B                     │
│                                                             │
│  [Prometheus] ←→ [Sidecar]    [Prometheus] ←→ [Sidecar]    │
│                      │                            │         │
└──────────────────────┼────────────────────────────┼─────────┘
                       │                            │
                       ▼                            ▼
              ┌──────────────────────────────────────┐
              │     Object Store (S3 / GCS / Azure)   │
              └──────────────────┬───────────────────┘
                                 │
              ┌──────────────────▼───────────────────┐
              │           Thanos Store Gateway        │
              │  (serve blocchi storici dall'object   │
              │   store come se fosse Prometheus)     │
              └──────────────────┬───────────────────┘
                                 │
              ┌──────────────────▼───────────────────┐
              │           Thanos Query                │
              │  (fanout query verso Sidecar + Store) │
              │  deduplication automatica             │
              └──────────────────┬───────────────────┘
                                 │
              ┌──────────────────▼───────────────────┐
              │         Thanos Compactor              │
              │  (downsampling + deduplication su     │
              │   object store — un solo compactor    │
              │   per object store)                   │
              └──────────────────────────────────────┘
```

**Componenti Thanos:**

| Componente | Ruolo | Deployment |
|-----------|-------|-----------|
| **Sidecar** | Espone Prometheus via gRPC, carica blocchi su object store | Accanto a ogni Prometheus (sidecar container) |
| **Query** | Layer di query distribuita con deduplication | Stateless, scalabile orizzontalmente |
| **Store Gateway** | Serve dati storici dall'object store | Stateful (cache locale), scalabile |
| **Compactor** | Downsampling (5m, 1h resolution) + compazione | Singleton per object store (non scalabile!) |
| **Ruler** | Valuta recording/alerting rules su dati Thanos | Stateless (con storage per regole) |
| **Receive** | Accetta remote_write e scrive su object store | Alternativa al Sidecar per push-based |

### VictoriaMetrics — Drop-in Semplice

VictoriaMetrics è un TSDB alternativo, compatibile con PromQL e il protocollo remote_write di Prometheus. Non richiede modifiche alla configurazione degli scraper.

```
              ┌────────────────────────────────────┐
              │         Modalità Single-node        │
              │                                    │
              │  [Prometheus A] ──remote_write──▶  │
              │  [Prometheus B] ──remote_write──▶  │  VictoriaMetrics
              │  [vmagent]      ──remote_write──▶  │  (singolo binario)
              │                                    │
              │  Storage: locale, compresso 7-10x  │
              │  Retention: anni senza problemi    │
              └────────────────────────────────────┘

              ┌────────────────────────────────────┐
              │        Modalità Cluster             │
              │                                    │
              │  [vmstorage ×N]  ←── vmstorage      │
              │  [vminsert  ×N]  ←── write path      │
              │  [vmselect  ×N]  ←── query path      │
              │  [vmauth]        ←── authn/routing   │
              └────────────────────────────────────┘
```

**Vantaggi VictoriaMetrics vs Prometheus TSDB:**
- **7-10x meno spazio su disco** grazie a compressione superiore
- **2-5x meno RAM** per lo stesso volume di time series
- **Retention multi-anno** out of the box (flag `-retentionPeriod`)
- **Compatibile PromQL** — Grafana, alerting rules, recording rules funzionano senza modifiche
- **Ingestion più veloce** — ottimizzato per write-heavy workload

## Configurazione & Pratica

### Thanos — Installazione Sidecar

```yaml
# kubernetes/prometheus-deployment.yaml
# Aggiungere il sidecar al pod di Prometheus
apiVersion: monitoring.coreos.com/v1
kind: Prometheus
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 2  # 2 repliche per HA locale
  retention: 2h  # I Sidecar caricano su object store, retention locale breve
  externalLabels:
    cluster: prod-eu-west-1  # OBBLIGATORIO: identifica il cluster per Thanos
    replica: $(POD_NAME)      # Per deduplication tra repliche
  thanos:
    image: quay.io/thanos/thanos:v0.36.0
    objectStorageConfig:
      secret:
        name: thanos-objstore-config
        key: objstore.yaml
```

```yaml
# secret: thanos-objstore-config (objstore.yaml)
type: S3
config:
  bucket: my-thanos-metrics
  endpoint: s3.eu-west-1.amazonaws.com
  region: eu-west-1
  # Usa IAM Role se su EKS (non includere access_key/secret_key)
  # access_key: "..."
  # secret_key: "..."
```

```bash
# Deploy Thanos Query (Helm — bitnami/thanos)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install thanos bitnami/thanos \
  --namespace monitoring \
  --set query.enabled=true \
  --set query.stores[0]=dnssrv+_grpc._tcp.prometheus-operated.monitoring.svc.cluster.local \
  --set storegateway.enabled=true \
  --set compactor.enabled=true \
  --set compactor.retentionResolutionRaw=30d \
  --set compactor.retentionResolution5m=90d \
  --set compactor.retentionResolution1h=1y \
  --set objstoreConfig="$(cat objstore.yaml)"
```

### Thanos — Sidecar come Container Standalone (senza Operator)

```yaml
# Aggiungere al pod Prometheus esistente
containers:
  - name: thanos-sidecar
    image: quay.io/thanos/thanos:v0.36.0
    args:
      - sidecar
      - --tsdb.path=/prometheus           # Stesso volume di Prometheus
      - --prometheus.url=http://localhost:9090
      - --grpc-address=0.0.0.0:10901     # Endpoint gRPC per Thanos Query
      - --http-address=0.0.0.0:10902     # Health check
      - --objstore.config-file=/etc/thanos/objstore.yaml
    ports:
      - name: http-sidecar
        containerPort: 10902
      - name: grpc
        containerPort: 10901
    volumeMounts:
      - name: prometheus-storage
        mountPath: /prometheus
      - name: objstore-config
        mountPath: /etc/thanos
```

### VictoriaMetrics — Single Node

```bash
# Docker — sostituisce Prometheus per un cluster singolo
docker run -d \
  --name victoriametrics \
  -v /path/to/storage:/victoria-metrics-data \
  -p 8428:8428 \
  victoriametrics/victoria-metrics:v1.101.0 \
  -storageDataPath=/victoria-metrics-data \
  -retentionPeriod=1y \          # Retention annuale
  -maxLabelsPerTimeseries=40 \   # Limite label per serie (default 30)
  -search.maxUniqueTimeseries=5000000  # Limite cardinality per query

# Verificare che sia up
curl http://localhost:8428/metrics | grep vm_app_version
```

```yaml
# Configurazione remote_write in prometheus.yml
# Prometheus continua a fare scraping, VictoriaMetrics riceve e archivia
remote_write:
  - url: http://victoriametrics:8428/api/v1/write
    queue_config:
      capacity: 50000
      max_samples_per_send: 10000
      max_shards: 10
      min_backoff: 30ms
      max_backoff: 5s
    # Opzionale: filtrare quali metriche inviare
    write_relabel_configs:
      - source_labels: [__name__]
        regex: "go_.*|process_.*"  # Escludi metriche di runtime interne
        action: drop
```

### VictoriaMetrics — Cluster Mode

```yaml
# kubernetes/vmcluster.yaml (usando VictoriaMetrics Operator)
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMCluster
metadata:
  name: vmcluster
  namespace: monitoring
spec:
  retentionPeriod: "12"  # mesi
  replicationFactor: 2
  vmstorage:
    replicaCount: 3
    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: gp3
          resources:
            requests:
              storage: 500Gi
    resources:
      requests:
        memory: 4Gi
        cpu: 1
  vminsert:
    replicaCount: 3
    resources:
      requests:
        memory: 512Mi
        cpu: 500m
  vmselect:
    replicaCount: 3
    resources:
      requests:
        memory: 2Gi
        cpu: 500m
```

### Remote Write — Tuning per Alta Frequenza

!!! warning "Perdita campioni sotto carico"
    Con queue_config non ottimizzata, Prometheus scarterà campioni durante picchi di scrittura. Monitorare `prometheus_remote_storage_samples_dropped_total` in produzione.

```yaml
# prometheus.yml — configurazione ottimizzata per ambienti ad alto volume
remote_write:
  - url: "http://victoriametrics:8428/api/v1/write"
    # Timeout e retry
    remote_timeout: 30s

    queue_config:
      # Dimensione buffer in memoria (campioni)
      capacity: 100000

      # Numero di goroutine parallele per invio
      # Aumentare se la rete verso il backend è il collo di bottiglia
      max_shards: 50
      min_shards: 2

      # Campioni per singolo batch HTTP
      max_samples_per_send: 10000

      # Batch WAL letti per shard prima di bloccare
      max_samples_per_send_deadline: 5s

      # Retry con backoff esponenziale
      min_backoff: 30ms
      max_backoff: 5s

    # Metadata forwarding (Prometheus 2.37+)
    metadata_config:
      send: true
      send_interval: 1m
```

```bash
# Metriche chiave da monitorare per il remote write
# Campioni in coda (non devono crescere indefinitamente)
prometheus_remote_storage_queue_highest_sent_timestamp_seconds

# Campioni droppati (deve essere 0)
prometheus_remote_storage_samples_dropped_total

# Lag tra WAL e invio (deve essere < 30s)
prometheus_remote_storage_samples_pending

# Tasso di invio vs scraping
rate(prometheus_remote_storage_samples_in_total[5m])
rate(prometheus_remote_storage_samples_total[5m])
```

### vmagent — Alternativa a Prometheus per Scraping

VictoriaMetrics include `vmagent`, un agente leggero che può sostituire Prometheus per la fase di scraping, con minor consumo di RAM e sharding nativo.

```yaml
# kubernetes/vmagent.yaml
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMAgent
metadata:
  name: vmagent
  namespace: monitoring
spec:
  serviceScrapeSelector: {}   # Seleziona tutti i VMServiceScrape nel namespace
  podScrapeSelector: {}       # Seleziona tutti i VMPodScrape
  remoteWrite:
    - url: "http://vminsert.monitoring.svc.cluster.local:8480/insert/0/prometheus"
  shardCount: 3  # Sharding automatico tra repliche
  resources:
    requests:
      memory: 512Mi
      cpu: 250m
    limits:
      memory: 1Gi
      cpu: 1
```

## Best Practices

### Thanos — Regole d'Oro

!!! tip "external_labels — il requisito più importante"
    Ogni Prometheus che invia dati a Thanos DEVE avere `external_labels` unici: `cluster` e `replica`. Thanos usa queste label per identificare la sorgente e fare deduplication. Senza di esse, i dati vengono mescolati e le query diventano inaffidabili.

```yaml
# prometheus.yml — external_labels obbligatori per Thanos
global:
  external_labels:
    cluster: "prod-eu-west-1"      # Identifica il cluster fisico
    environment: "production"       # Contesto ambiente
    replica: $(POD_NAME)           # Identifica la replica (per HA dedup)
    region: "eu-west-1"            # Utile per query geografiche
```

- **Compactor è singleton**: mai eseguire più istanze del Compactor sullo stesso object store — corrompe i dati
- **Retention per risoluzione**: configurare `--retention.resolution-raw=30d`, `--retention.resolution-5m=90d`, `--retention.resolution-1h=1y` — i dati storici vengono downsampled automaticamente
- **Store Gateway con cache**: abilitare cache in-memory o Redis per velocizzare query storiche
- **Query Replica Labels**: configurare `--query.replica-label=replica` su Thanos Query per la deduplication automatica

### VictoriaMetrics — Best Practices

!!! tip "VictoriaMetrics come drop-in"
    VictoriaMetrics è compatibile con il formato di query Prometheus. Grafana può connettersi direttamente usando il datasource Prometheus standard, puntando all'endpoint VictoriaMetrics.

```bash
# Configurazione Grafana datasource (equivalente a Prometheus)
# URL: http://victoriametrics:8428
# Type: Prometheus
# Nessuna altra modifica necessaria
```

- **Non aumentare `-maxLabelsPerTimeseries` troppo**: default 30 è sufficiente per quasi tutti i casi; valori alti peggiorano le performance
- **Monitoring del monitoring**: esporre metriche di VictoriaMetrics stessa su Prometheus (endpoint `/metrics`) per monitorare lo stato interno
- **Backup**: usare `vmbackup` per backup periodici su object store — non affidare la sola retention a un singolo volume
- **Cardinality control**: VictoriaMetrics ha endpoint `/api/v1/cardinality` per analisi delle time series ad alta cardinality

## Confronto Thanos vs VictoriaMetrics

| Criterio | Thanos | VictoriaMetrics Single | VictoriaMetrics Cluster |
|---------|--------|----------------------|------------------------|
| **Complessità operativa** | Alta (5+ componenti) | Bassa (1 binario) | Media (3 componenti) |
| **HA storage** | Sì (object store) | No (locale) | Sì (replication) |
| **Multi-cluster query** | Sì (nativo) | Sì (via remote_write) | Sì (via remote_write) |
| **Multi-tenancy** | Parziale (con Receiver) | No | Sì (con vmauth) |
| **Efficienza storage** | Simile a Prometheus | 7-10x migliore | 7-10x migliore |
| **Compatibilità PromQL** | Completa + estensioni | Completa + MetricsQL | Completa + MetricsQL |
| **Compatibilità Grafana** | Datasource Thanos/Prometheus | Datasource Prometheus | Datasource Prometheus |
| **Object store richiesto** | Sì (S3/GCS/Azure) | No | No |
| **Downsampling automatico** | Sì (Compactor) | No | No |
| **Licensing** | Apache 2.0 | Apache 2.0 | Enterprise per alcune features |
| **Caso d'uso tipico** | Multi-cluster grandi, auditing | Single cluster con retention lunga | Multi-tenant, alto throughput |

## Grafana Mimir — Terza Opzione

Grafana Mimir è la versione open-source e cloud-native di Cortex, sviluppata da Grafana Labs. Progettata per scale estremo (miliardi di time series, petabyte di dati).

```yaml
# mimir — distribuzione su Kubernetes (helm)
helm repo add grafana https://grafana.github.io/helm-charts

helm install mimir grafana/mimir-distributed \
  --namespace monitoring \
  --set minio.enabled=true \      # Object store embedded per test
  --set nginx.enabled=true         # Ingress interno

# remote_write da Prometheus verso Mimir
# prometheus.yml
remote_write:
  - url: http://mimir-nginx.monitoring.svc.cluster.local/api/v1/push
    headers:
      X-Scope-OrgID: "tenant-a"   # Multi-tenancy obbligatorio
```

**Quando scegliere Mimir:**
- Già nell'ecosistema Grafana Cloud / Grafana Enterprise
- Necessità di multi-tenancy nativa con isolamento completo
- Volume di time series nell'ordine delle centinaia di milioni
- Team con esperienza Kubernetes e risorse per gestire un sistema distribuito complesso

## Decision Tree

```
Quanti cluster Prometheus?
│
├── 1-3 cluster
│   ├── Retention < 90 giorni?  →  Prometheus standalone (nessuna modifica)
│   └── Retention > 90 giorni?  →  VictoriaMetrics single-node + remote_write
│
├── 3-20 cluster
│   ├── Budget ops basso?       →  VictoriaMetrics single-node centralizzato
│   │                               (tutti i cluster remote_write verso uno)
│   └── Vuoi query storiche     →  Thanos con object store (S3/GCS)
│       cross-cluster native?
│
└── >20 cluster / multi-tenant
    ├── Team piccolo?           →  VictoriaMetrics Cluster (più semplice)
    └── Ecosistema Grafana?     →  Grafana Mimir
```

## Troubleshooting

### Thanos Query — Dati Mancanti o Duplicati

**Sintomo:** Query su Thanos Query restituisce meno dati di quanto atteso, o vede doppioni di serie.

**Causa:** `external_labels` mancanti o non unici tra le repliche Prometheus, oppure `--query.replica-label` non configurato.

```bash
# Verificare external_labels configurati su ogni Prometheus
kubectl exec -n monitoring prometheus-0 -- \
  curl -s http://localhost:9090/api/v1/labels | jq '.data | map(select(startswith("cluster") or . == "replica"))'

# Verificare connessione Thanos Query → Sidecar
kubectl logs -n monitoring deploy/thanos-query | grep -E "store|endpoint"

# Test query con deduplication esplicita
curl "http://thanos-query:10902/api/v1/query?query=up&dedup=true&replicaLabels=replica"
```

### Thanos Store Gateway — Query Lente su Dati Storici

**Sintomo:** Query su range temporali > 7 giorni sono molto lente (> 30s).

**Causa:** Cache del Store Gateway non configurata o insufficiente; troppi blocchi non compattati sull'object store.

```bash
# Verificare stato blocchi sull'object store tramite Compactor
kubectl logs -n monitoring deploy/thanos-compactor | grep -E "compacted|block"

# Verificare numero di blocchi non compatti
curl http://thanos-storegateway:10902/metrics | grep thanos_bucket_store_blocks_loaded

# Aumentare cache in-memory (Store Gateway)
# Aggiungere al deployment thanos-storegateway:
# --store.caching-bucket.config='{"type":"IN-MEMORY","config":{"max_size":"4GB","max_item_size":"1GB"}}'
```

### VictoriaMetrics — Campioni Rifiutati

**Sintomo:** Log VictoriaMetrics mostrano "too many labels" o "sample out of order".

**Causa:** Time series con più label del limite configurato, oppure campioni arrivati fuori ordine dall'agent.

```bash
# Verificare errori di ingestion
curl http://victoriametrics:8428/metrics | grep vm_rows_invalid_total

# Analizzare cardinality per trovare time series anomale
curl "http://victoriametrics:8428/api/v1/cardinality/label_names?topN=20"
curl "http://victoriametrics:8428/api/v1/cardinality/label_values?labelName=__name__&topN=20"

# Aumentare limite label se necessario (con cautela)
# Aggiungere flag: -maxLabelsPerTimeseries=50
```

### Remote Write — Lag Crescente

**Sintomo:** `prometheus_remote_storage_samples_pending` cresce continuamente; dati in ritardo nel backend.

**Causa:** Backend saturo, rete congestionata, o `max_shards` troppo basso per il volume di dati.

```bash
# Verificare il lag del remote write
# In Grafana o PromQL:
# (time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds) > 60

# Aumentare shards e capacity in prometheus.yml
# queue_config:
#   max_shards: 100    # Da 30 a 100
#   capacity: 200000   # Buffer più grande

# Verificare saturazione backend
kubectl top pod -n monitoring -l app=victoriametrics

# Controllare errori HTTP dal Prometheus verso backend
curl http://prometheus:9090/metrics | grep remote_storage_failed
```

### Compactor Thanos — Blocco su Conflitti

**Sintomo:** Compactor non avanza, log mostrano "conflict" o "block overlap".

**Causa:** Compactor crashato a metà operazione ha lasciato blocchi parziali; oppure (errore grave) due istanze Compactor attive sullo stesso bucket.

```bash
# MAI avere 2 Compactor sullo stesso bucket — controllare prima
kubectl get pods -n monitoring -l app=thanos-compactor

# Visualizzare stato blocchi con thanos tools
kubectl run thanos-debug --rm -it --image=quay.io/thanos/thanos:v0.36.0 -- \
  tools bucket inspect \
  --objstore.config-file=/etc/thanos/objstore.yaml

# In caso di overlap: usare thanos tools bucket mark --mark=no-compact
# per escludere blocchi problematici (operazione distruttiva — fare backup prima)
```

## Relazioni

??? info "Prometheus — Base"
    Questo documento estende `prometheus.md`. Prima di implementare qualsiasi soluzione di scalabilità, è necessario avere una configurazione Prometheus base funzionante con external_labels corretti.

    **Approfondimento completo →** [Prometheus](./prometheus.md)

??? info "Grafana — Visualizzazione"
    Sia Thanos che VictoriaMetrics si integrano nativamente con Grafana come datasource. Thanos espone un endpoint compatibile con Prometheus; VictoriaMetrics è completamente compatibile con il datasource Prometheus standard.

    **Approfondimento completo →** [Grafana](./grafana.md)

??? info "Alertmanager — Alerting Distribuito"
    Con Thanos, le alerting rules possono essere gestite da Thanos Ruler (che ha visibilità cross-cluster). Con VictoriaMetrics, si usa `vmalert` come alternativa a Prometheus Alertmanager.

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

## Riferimenti

- [Thanos — Getting Started](https://thanos.io/tip/thanos/getting-started.md/)
- [Thanos — Deployment Options](https://thanos.io/tip/thanos/deployment.md/)
- [VictoriaMetrics — Quick Start](https://docs.victoriametrics.com/Quick-Start.html)
- [VictoriaMetrics — Cluster Setup](https://docs.victoriametrics.com/Cluster-VictoriaMetrics.html)
- [Grafana Mimir — Getting Started](https://grafana.com/docs/mimir/latest/get-started/)
- [Prometheus Remote Write — Tuning](https://prometheus.io/docs/practices/remote_write/)
- [Bitnami Helm Chart — Thanos](https://github.com/bitnami/charts/tree/main/bitnami/thanos)
- [Prometheus vs Thanos vs VictoriaMetrics — Comparison](https://last9.io/blog/prometheus-vs-thanos-vs-victoriametrics/)
