---
title: "Gestione Cardinalità e Costo delle Metriche"
slug: cardinality-cost-management
category: monitoring
tags: [prometheus, cardinality, cost-management, thanos, mimir, victoriametrics, finops, tsdb]
search_keywords: [cardinalità metriche, metric cardinality, cardinality explosion, esplosione cardinalità, high cardinality labels, label ad alta varianza, costo metriche, monitoring cost, finops observability, prometheus tsdb head series, scrape_series_added, tsdb_head_series, sample_limit, label_limit, metric_relabel_configs, labeldrop, labelkeep, recording rules aggregazione, otel collector filter processor, otel transform processor, cardinality killer, time series explosion, prometheus oom cardinality, remote_write saturazione, mimir ingestion cost, thanos storage cost, promtool tsdb analyze, bolletta monitoring]
parent: monitoring/tools/_index
related: [monitoring/tools/prometheus, monitoring/tools/prometheus-scalabilita, monitoring/tools/otel-collector-kubernetes, monitoring/alerting/prometheus-rules]
official_docs: https://prometheus.io/docs/practices/instrumentation/#do-not-overuse-labels
status: complete
difficulty: advanced
last_updated: 2026-10-02
---

# Gestione Cardinalità e Costo delle Metriche

## Panoramica

La cardinalità di una metrica è il numero di combinazioni uniche di label associate a quel nome metrica: ogni combinazione genera una time series indipendente nel TSDB. Più serie attive significano più RAM nel head block di Prometheus, più dati scritti su object storage (Thanos) o ingested (Mimir/VictoriaMetrics), e bollette cloud monitoring che crescono in modo non lineare rispetto al valore informativo aggiunto. Il problema non è la quantità di metriche in sé, ma le **label ad alta varianza** — `user_id`, `pod_name` con suffisso random, `trace_id` usato come label, path HTTP non normalizzato — che moltiplicano le serie senza un corrispondente aumento di insight. Questo documento copre diagnosi, mitigazione e governance della cardinalità in uno stack Prometheus/Thanos/Mimir/VictoriaMetrics a scala, con focus su impatto economico diretto: ogni nuova label su una metrica ad alto traffico è una decisione di costo, non solo tecnica.

## Concetti Chiave

!!! note "Definizione: serie = metrica × combinazione label"
    Una serie temporale (time series) è identificata univocamente da `__name__` + l'insieme ordinato di tutte le coppie label=valore. `http_requests_total{method="GET", path="/users/123", status="200"}` e `http_requests_total{method="GET", path="/users/456", status="200"}` sono due serie distinte se `path` non è normalizzato — non una metrica con due valori.

### Perché la Cardinalità Esplode

| Causa | Esempio concreto | Moltiplicatore |
|-------|------------------|-----------------|
| **ID ad alta varianza come label** | `user_id`, `order_id`, `session_id` | Una serie per ogni utente/ordine attivo |
| **Nomi pod/container come label** | `pod_name="app-7d9f8b-x7k2p"` (hash deployment) | Una serie per ogni rollout/scale event |
| **trace_id / request_id come label** | `trace_id="a1b2c3..."` su una metrica custom | Praticamente infinita (una serie per richiesta) |
| **Path HTTP non normalizzato** | `/users/123`, `/users/456`, `/users/789` invece di `/users/:id` | Una serie per ogni valore path reale |
| **Timestamp o valori float come label** | `version="1.2.3-a1b2c3-20260102"` (build hash + data) | Una serie per ogni build/deploy |
| **Label geografiche granulari** | `client_ip` invece di `region`/`az` | Una serie per ogni IP client |

!!! warning "La cardinalità cresce moltiplicativamente, non additivamente"
    Una metrica con 3 label a bassa cardinalità (`method`: 5 valori, `status`: 10 valori, `region`: 4 valori) genera al massimo 200 serie. Aggiungere una quarta label `user_id` con 500.000 valori univoci porta il totale a 100 milioni di serie potenziali — anche se nella pratica non tutte le combinazioni si verificano, il head block di Prometheus deve comunque allocare memoria per ogni serie realmente osservata.

### Cardinalità Attiva vs Cardinalità Cumulativa

- **Cardinalità attiva** (`prometheus_tsdb_head_series`): serie con almeno un campione nel blocco head corrente. Determina la RAM istantanea.
- **Cardinalità cumulativa** (churn): serie totali viste nel tempo, incluse quelle "morte" (es. da pod riavviati con nome diverso). Determina lo spazio su disco/object storage nel lungo periodo, anche se la cardinalità attiva resta stabile.

Un sistema con alto **churn** (serie che nascono e muoiono di continuo, tipico di deployment Kubernetes con nomi pod randomici) può avere cardinalità attiva accettabile ma costo di storage storico molto alto, perché ogni blocco TSDB compattato porta con sé tutte le serie storiche.

## Architettura / Come Funziona

### Percorso Serie → Memoria → Costo

```
┌─────────────────────────────────────────────────────────────┐
│  1. Scrape/Push                                              │
│     Ogni combinazione label univoca → nuova entry TSDB       │
│                                                                │
│  2. Head Block (RAM)                                          │
│     prometheus_tsdb_head_series cresce linearmente con        │
│     le serie attive. ~3-5 KB RAM per serie attiva (stima)     │
│                                                                │
│  3. Compattazione su disco locale                             │
│     Blocchi da 2h → merge periodico. Più serie = blocchi      │
│     più grandi = compattazione più lenta                      │
│                                                                │
│  4. Remote write / Sidecar upload                              │
│     Ogni serie = più campioni da trasferire in rete            │
│     Rischio: saturazione banda, queue drop                     │
│                                                                │
│  5. Long-term storage (Thanos object store / Mimir / VM)        │
│     Costo storage proporzionale a serie × retention            │
│     Costo ingestion (Mimir/VM Cloud) spesso a serie/campioni    │
│     attivi al minuto — fatturazione diretta sulla cardinalità   │
└─────────────────────────────────────────────────────────────┘
```

Il punto critico è che il costo si propaga: una label ad alta cardinalità aggiunta allo scrape endpoint si moltiplica per ogni hop successivo (RAM locale, rete remote_write, storage a lungo termine, query engine). Una mitigazione a monte (nell'exporter o nell'OTel Collector) è ordini di grandezza più efficace di una mitigazione a valle (drop su Thanos Compactor, che ha già pagato il costo di ingestion).

## Configurazione & Pratica

### Diagnosi — Trovare le Metriche/Label più Costose

```bash
# Top metriche per numero di serie attive (via PromQL, endpoint /api/v1/query)
# Eseguire contro Prometheus o VictoriaMetrics (sintassi compatibile)
curl -s -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=topk(10, count by (__name__)({__name__=~".+"}))' \
  | jq '.data.result[] | {metric: .metric.__name__, series: .value[1]}'

# Endpoint nativo Prometheus per analisi cardinalità (Prometheus 2.14+)
# Top 10 metriche e label per cardinalità, senza dover fare query pesanti
curl -s http://localhost:9090/api/v1/status/tsdb | jq '{
  head_series: .data.headStats.numSeries,
  top_metrics: .data.seriesCountByMetricName[:10],
  top_labels: .data.labelValueCountByLabelName[:10]
}'

# Dimensione della symbol table (cresce con label/valori univoci — indicatore precoce)
curl -s http://localhost:9090/api/v1/query \
  --data-urlencode 'query=prometheus_tsdb_symbol_table_size_bytes' | jq
```

```bash
# promtool tsdb analyze — analisi offline su un blocco TSDB già scritto su disco
# Utile per investigare un problema storico senza impattare Prometheus live
promtool tsdb analyze /prometheus/data

# Output tipico (estratto):
# Top 10 metrics with highest cardinality:
#   http_request_duration_seconds   1245032
#   kube_pod_container_status_...    842110
#
# Top 10 label pairs with highest cardinality:
#   path=/api/v1/users/12345         1
#   path=/api/v1/users/67890         1
#   (migliaia di valori unici → path non normalizzato)
```

```bash
# VictoriaMetrics — endpoint nativo di cardinality explorer
curl "http://victoriametrics:8428/api/v1/cardinality/label_names?topN=20"
curl "http://victoriametrics:8428/api/v1/cardinality/label_values?labelName=path&topN=20"
# Interfaccia web equivalente: http://victoriametrics:8428/vmui -> tab Cardinality Explorer
```

### Mitigazione 1 — Drop e Labeldrop in Fase di Scrape

```yaml
# prometheus.yml — rimuovere label ad alta cardinalità prima di ingerire la serie
scrape_configs:
  - job_name: 'app-backend'
    static_configs:
      - targets: ['app:8080']
    metric_relabel_configs:
      # Elimina del tutto le serie di una metrica non necessaria
      - source_labels: [__name__]
        regex: 'go_gc_duration_seconds.*'
        action: drop

      # Rimuove la label 'instance_build_hash' da TUTTE le serie che matchano
      # (riduce cardinalità senza perdere la metrica)
      - regex: 'instance_build_hash'
        action: labeldrop

      # Normalizza path HTTP ad alta cardinalità PRIMA che diventi una serie
      - source_labels: [path]
        regex: '/users/[0-9]+'
        target_label: path
        replacement: '/users/:id'

      # sample_limit: rifiuta l'intero scrape se supera N serie (safety net)
    sample_limit: 10000
    # label_limit: rifiuta target con troppe label per serie
    label_limit: 30
    label_value_length_limit: 200
```

### Mitigazione 2 — Aggregazione via Recording Rules Prima del Remote Write

```yaml
# recording-rules.yml — pre-aggregare prima di spedire a long-term storage
# Riduce drasticamente la cardinalità che arriva a Thanos/Mimir
groups:
  - name: http_aggregation
    interval: 30s
    rules:
      # Da una metrica con label path/user_id/pod ad alta cardinalità,
      # genera un'aggregazione per sola 'method' + 'status' (bassa cardinalità)
      - record: job:http_requests:rate5m
        expr: sum by (job, method, status) (rate(http_requests_total[5m]))
```

```yaml
# prometheus.yml — inviare a remote storage SOLO le serie aggregate,
# non le serie grezze ad alta cardinalità (write_relabel_configs)
remote_write:
  - url: http://thanos-receive:19291/api/v1/receive
    write_relabel_configs:
      # Invia solo metriche aggregate (prefisso job:) e drop il resto
      - source_labels: [__name__]
        regex: 'job:.*'
        action: keep
```

### Mitigazione 3 — OTel Collector per Normalizzazione Path

```yaml
# otel-collector-config.yaml — processor transform per normalizzare
# attributi ad alta cardinalità prima dell'export verso il backend metriche
processors:
  transform:
    metric_statements:
      - context: datapoint
        statements:
          # Sostituisce segmenti numerici del path con placeholder
          - replace_pattern(attributes["http.route"], "/users/[0-9]+", "/users/{id}")
          - replace_pattern(attributes["http.route"], "/orders/[a-f0-9-]{36}", "/orders/{uuid}")

  filter:
    metrics:
      datapoint:
        # Scarta datapoint con cardinalità nota come problematica
        - 'attributes["user_id"] != nil'

service:
  pipelines:
    metrics:
      processors: [filter, transform, batch]
```

### Stimare il Costo di una Nuova Label Prima della Produzione

```bash
# Procedura pratica: stimare la cardinalità aggiuntiva PRIMA del rollout
# 1. Contare i valori distinti attesi per la nuova label (es. da un DB)
#    SELECT COUNT(DISTINCT customer_tier) FROM customers;  -- es. 4 valori: OK
#    SELECT COUNT(DISTINCT customer_id) FROM customers;    -- es. 500000: NO

# 2. Calcolare la cardinalità moltiplicativa attesa
#    serie_attuali_metrica × nuovi_valori_label = serie_totali_attese
#    Es: http_requests_total ha oggi 200 serie (method×status×region)
#        aggiungere customer_tier (4 valori) -> 800 serie: accettabile
#        aggiungere customer_id (500k valori) -> 100M serie: BLOCCARE

# 3. Verificare contro budget RAM disponibile
#    stima: ~3-5 KB RAM per serie attiva nel head block
#    100M serie × 4KB = ~400GB RAM solo per il head block -> impraticabile
```

## Best Practices

!!! tip "Normalizza alla sorgente, non a valle"
    La mitigazione più efficace è nell'instrumentation del codice applicativo (usare `/users/:id` come label di default, non il path grezzo) o nell'OTel Collector il più vicino possibile alla sorgente. Ogni hop a valle (Prometheus scrape, remote_write, Thanos Compactor) ha già pagato il costo di CPU/rete/storage per la serie ad alta cardinalità prima di poterla scartare.

- **Mai usare come label**: `user_id`, `session_id`, `trace_id`, `request_id`, `email`, indirizzi IP completi, timestamp, UUID generati runtime
- **`sample_limit` e `label_limit` come safety net**: configurare sempre sugli scrape config di produzione — un bug nell'exporter che genera cardinalità esplosiva deve far fallire lo scrape, non saturare Prometheus
- **Preferire histogram/summary predefiniti** a metriche custom con molte label per bucket di latenza
- **Recording rules per dashboard**: se una dashboard usa solo aggregazioni (`sum by (region)`), non serve conservare la serie grezza a lungo termine — aggregare e droppare l'originale dal remote_write
- **Cardinality budget per team**: assegnare un tetto di serie attive per namespace/team (enforcement via `sample_limit` per job) così la responsabilità del costo è distribuita, non centralizzata sul team platform

## Governance

### Checklist PR per Nuove Metriche/Label

!!! warning "Ogni nuova label è una decisione di costo, non solo di instrumentation"
    Richiedere esplicitamente nella code review la stima di cardinalità per qualsiasi nuova label su una metrica ad alto traffico (>1000 req/s).

Checklist da includere nel template PR per chi aggiunge/modifica metriche:

- [ ] La nuova label ha cardinalità nota e limitata (enum, non ID)?
- [ ] È stata stimata la cardinalità moltiplicativa attesa (vedi sezione precedente)?
- [ ] Esiste un `sample_limit` sullo scrape config target?
- [ ] La metrica è davvero necessaria a livello di serie grezza, o basta un'aggregazione?
- [ ] È stato verificato l'impatto su `prometheus_tsdb_head_series` in staging prima del merge in produzione?

### Alerting su Crescita Anomala di Cardinalità

```yaml
# prometheus-rules.yml — alert su crescita cardinalità non spiegata da traffico
groups:
  - name: cardinality_governance
    rules:
      - alert: CardinalityGrowthAnomaly
        expr: |
          (
            prometheus_tsdb_head_series
            -
            prometheus_tsdb_head_series offset 1h
          ) > 50000
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Crescita anomala serie attive su {{ $labels.instance }}"
          description: "Head series cresciute di oltre 50k nell'ultima ora. Verificare deploy recenti o nuove metriche."

      - alert: HighSeriesChurnRate
        expr: |
          sum(rate(prometheus_tsdb_head_series_created_total[10m])) > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Alto tasso di creazione nuove serie (churn)"
          description: "Possibile label ad alta varianza (es. pod_name randomico) che genera churn costante."

      - alert: ScrapeSeriesAddedSpike
        expr: |
          scrape_series_added > 5000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Target {{ $labels.instance }} ha aggiunto {{ $value }} nuove serie in un singolo scrape"
          description: "Probabile bug nell'exporter o label non normalizzata (path, ID)."
```

- **Review periodica obbligatoria**: ogni trimestre, estrarre le top 20 metriche per cardinalità (`/api/v1/status/tsdb`) e validare con i team owner se sono ancora necessarie a quella granularità
- **Budget per cluster/namespace**: collegare l'alert `CardinalityGrowthAnomaly` a un processo di escalation verso il team che ha introdotto la nuova label, non solo al team platform

## Troubleshooting

### Prometheus OOM Dopo un Deploy

**Sintomo:** Prometheus crasha con OOM pochi minuti dopo un rollout applicativo; al restart il TSDB impiega molto tempo a ricostruire il WAL.

**Causa:** Una nuova versione dell'app ha introdotto una label ad alta cardinalità (es. `pod_name` o `revision_hash`), moltiplicando le serie attive oltre la RAM disponibile.

```bash
# Verificare la crescita delle serie attorno all'orario del deploy
curl -s http://localhost:9090/api/v1/query_range \
  --data-urlencode 'query=prometheus_tsdb_head_series' \
  --data-urlencode 'start=2026-10-02T08:00:00Z' \
  --data-urlencode 'end=2026-10-02T09:00:00Z' \
  --data-urlencode 'step=60s'

# Identificare la metrica/label responsabile post-mortem (se Prometheus riparte)
promtool tsdb analyze /prometheus/data | head -30

# Mitigazione immediata: aggiungere drop temporaneo via metric_relabel_configs
# e fare reload senza restart completo
curl -X POST http://localhost:9090/-/reload
```

### Remote Write Satura la Rete

**Sintomo:** `prometheus_remote_storage_samples_pending` cresce senza fermarsi; latenza di rete verso il backend aumenta; altri servizi sulla stessa rete rallentano.

**Causa:** Esplosione di cardinalità lato scrape ha moltiplicato il volume di campioni da trasferire via remote_write, saturando la banda disponibile verso Thanos Receive/Mimir/VictoriaMetrics.

```bash
# Verificare il tasso di campioni in uscita vs normale
rate(prometheus_remote_storage_samples_total[5m])

# Confrontare con baseline storica — se 10x il normale, sospettare cardinalità
# Applicare drop temporaneo in write_relabel_configs per la metrica sospetta
# poi fare reload (non richiede restart)
curl -X POST http://localhost:9090/-/reload

# Verificare errori/backpressure dal backend
curl http://localhost:9090/metrics | grep remote_storage_failed
```

### Bolletta Cloud Monitoring Inattesa (Mimir Cloud / VictoriaMetrics Cloud / Grafana Cloud)

**Sintomo:** Fattura mensile del provider di monitoring gestito cresce in modo sproporzionato rispetto al traffico applicativo.

**Causa:** Provider SaaS fatturano tipicamente su "active series" o "samples ingested al minuto" — una singola label ad alta cardinalità aggiunta settimane prima può passare inosservata fino all'arrivo della fattura.

```bash
# Grafana Cloud / Mimir: verificare le top serie per tenant
# (richiede accesso API con X-Scope-OrgID del tenant)
curl -H "X-Scope-OrgID: tenant-a" \
  "https://<mimir-endpoint>/api/v1/status/tsdb" | jq '.data.seriesCountByMetricName[:20]'

# Confrontare la data di introduzione della label sospetta con lo storico fatture
# (correlazione manuale: git log sull'istrumentazione + date fattura)
git log --all --oneline -- '**/metrics.go' '**/instrumentation*'
```

### `sample_limit` Scarta un Intero Target

**Sintomo:** Un target smette improvvisamente di riportare metriche; log Prometheus mostra `sample_limit exceeded`.

**Causa:** Il safety net configurato (`sample_limit`) ha funzionato come previsto: un bug nell'exporter o una nuova label ad alta cardinalità ha fatto superare la soglia, e Prometheus ha rifiutato l'intero scrape per proteggere il TSDB.

```bash
# Verificare l'evento nei log
kubectl logs -n monitoring prometheus-0 | grep "sample_limit"

# Contare le serie che l'exporter sta effettivamente esponendo
curl -s http://app-backend:8080/metrics | grep -v '^#' | wc -l

# Identificare la metrica responsabile
curl -s http://app-backend:8080/metrics | grep -v '^#' \
  | sed -E 's/\{.*//' | sort | uniq -c | sort -rn | head -10

# Fix: correggere l'exporter (rimuovere la label) prima di alzare sample_limit
# Alzare il limite senza fix è un cerotto, non una soluzione
```

## Relazioni

??? info "Prometheus — Base e Limiti Architetturali"
    La tabella limiti di `prometheus-scalabilita.md` include la cardinalità come soglia critica per RAM e OOM. Questo documento approfondisce diagnosi e mitigazione pratica; l'altro copre le soluzioni architetturali (Thanos, VictoriaMetrics) per scalare oltre quei limiti.

    **Approfondimento completo →** [Prometheus: Scalabilità e Long-term Storage](./prometheus-scalabilita.md)

??? info "OTel Collector — Normalizzazione alla Sorgente"
    Il processor `transform`/`filter` di OpenTelemetry Collector è il punto più efficiente per normalizzare attributi ad alta cardinalità prima che diventino serie, specialmente in ambienti Kubernetes con nomi pod/container volatili.

    **Approfondimento completo →** [OTel Collector su Kubernetes](./otel-collector-kubernetes.md)

??? info "Alerting Rules — Integrazione con Governance"
    Gli alert su crescita anomala di cardinalità (`CardinalityGrowthAnomaly`, `ScrapeSeriesAddedSpike`) seguono le stesse convenzioni di naming e struttura delle recording/alerting rules documentate per Prometheus.

    **Approfondimento completo →** [Prometheus Rules](../alerting/prometheus-rules.md)

## Riferimenti

- [Prometheus — Instrumentation Best Practices (label cardinality)](https://prometheus.io/docs/practices/instrumentation/#do-not-overuse-labels)
- [Prometheus — TSDB Status API](https://prometheus.io/docs/prometheus/latest/querying/api/#tsdb-stats)
- [Grafana Labs — Controlling Metrics Cardinality](https://grafana.com/docs/grafana-cloud/cost-management-and-billing/reduce-costs/metrics-costs/control-metrics-usage/)
- [VictoriaMetrics — Cardinality Explorer](https://docs.victoriametrics.com/#cardinality-explorer)
- [OpenTelemetry Collector — Transform Processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/transformprocessor)
- [Prometheus — promtool tsdb analyze](https://prometheus.io/docs/prometheus/latest/command-line/promtool/)
