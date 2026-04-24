---
title: "Prometheus Alert Rules & Recording Rules"
slug: prometheus-rules
category: monitoring
tags: [prometheus, alerting, recording-rules, alert-rules, slo, burn-rate, promql, promtool]
search_keywords: [prometheus rules, alert rules, recording rules, alerting rules, regole prometheus, regole di alerting, burn rate alert, slo-based alerting, multi-window alert, promtool, rule testing, unit test prometheus, USE method, RED method, alert fatigue, flapping alert, for clause, severity, runbook, annotations prometheus, labels alert, gruppi regole, rule groups, prometheus rule validation, ci-cd prometheus, prometheus operator, prometheusrule crd, level:metric:operation, recording rules naming, alert quality, anti-pattern alert, soglie alert, alert threshold, error rate alert, latency alert, saturation alert]
parent: monitoring/alerting/_index
related: [monitoring/tools/prometheus, monitoring/alerting/alertmanager, monitoring/sre/slo-sla-sli, monitoring/sre/error-budget]
official_docs: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
status: complete
difficulty: intermediate
last_updated: 2026-04-03
---

# Prometheus Alert Rules & Recording Rules

## Panoramica

Le Prometheus rules sono il cuore dell'alerting intelligente: definiscono *quando* un sistema è in uno stato anomalo (alerting rules) e *come* pre-calcolare query costose per renderle efficienti (recording rules). Prometheus valuta entrambi i tipi a ogni `evaluation_interval` (default: 15s). Saper scrivere regole di qualità è la differenza tra un sistema di alerting che funziona — preciso, affidabile, azionabile — e uno che produce alert storm, falsi positivi e alert fatigue che portano i team a ignorare le notifiche. Questo file copre la struttura completa delle regole, i pattern di qualità, l'alerting SLO-based, e il tooling per validare e testare le regole in CI/CD.

Il file prometheus.md copre l'architettura e PromQL; il file alertmanager.md copre il routing delle notifiche. Questo file si occupa esclusivamente di **cosa scrivere nelle regole** per generare alert di production quality.

## Concetti Chiave

### Ciclo di Valutazione

Prometheus valuta le rule files ogni `evaluation_interval`. Una alerting rule può trovarsi in tre stati:

| Stato | Significato |
|-------|-------------|
| **Inactive** | L'espressione è false (nessun problema rilevato) |
| **Pending** | L'espressione è true, ma non è ancora trascorso il tempo definito in `for` |
| **Firing** | L'espressione è true da almeno il tempo `for` → alert inviato ad Alertmanager |

Il campo `for` è il meccanismo fondamentale per evitare flapping (alert che si attivano e disattivano rapidamente per spike temporanei). Senza `for`, ogni spike di 15 secondi genera una notifica.

### Anatomia di una Alert Rule

```yaml
groups:
  - name: app.rules                    # nome del gruppo (logicamente coeso)
    interval: 30s                      # override evaluation_interval per questo gruppo
    rules:
      - alert: HighErrorRate           # nome alert — PascalCase per convenzione
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          / rate(http_requests_total[5m]) > 0.05
        for: 5m                        # pending prima di firing
        labels:                        # labels aggiunte all'alert (routing in Alertmanager)
          severity: critical
          team: backend
        annotations:                   # testo human-readable per la notifica
          summary: "High error rate on {{ $labels.service }}"
          description: >
            Service {{ $labels.service }} error rate is
            {{ $value | humanizePercentage }} (threshold: 5%).
          runbook_url: "https://runbooks.company.com/high-error-rate"
```

### Labels vs Annotations

| Campo | Scopo | Comportamento |
|-------|-------|---------------|
| **labels** | Identificano e routano l'alert | Usati da Alertmanager per routing tree e deduplication |
| **annotations** | Descrivono l'alert per chi lo riceve | Non usati per routing; visualizzati nelle notifiche |

!!! warning "Labels e identità dell'alert"
    Le labels fanno parte dell'identità dell'alert: due alert con le stesse labels ma valori diversi sono considerati lo stesso alert e vengono deduplicati. Non inserire nei labels valori dinamici ad alta cardinalità (come `$value`). Quelli vanno nelle annotations.

### Template nelle Annotations

Le annotations supportano Go template con accesso a:
- `{{ $labels.nome_label }}` — valore di una label dell'alert
- `{{ $value }}` — valore numerico dell'espressione al momento dell'alert
- `{{ $value | humanize }}` — formattato (es. 1.5k)
- `{{ $value | humanizePercentage }}` — formattato come percentuale
- `{{ $value | humanizeDuration }}` — formattato come durata

```yaml
annotations:
  summary: "Disk almost full on {{ $labels.instance }}"
  description: >
    Instance {{ $labels.instance }} has {{ $value | humanizePercentage }}
    disk space remaining on {{ $labels.mountpoint }}.
    Predicted full in {{ with query "predict_linear(node_filesystem_avail_bytes[1h], 4*3600)" }}
    {{ . | first | value | humanizeDuration }}{{ end }}.
  runbook_url: "https://runbooks.company.com/disk-space"
```

## Architettura / Come Funziona

### Struttura dei File di Regole

```
rules/
├── infrastructure.rules.yml   # CPU, memoria, disco, rete
├── kubernetes.rules.yml       # pod, deployment, node
├── application.rules.yml      # error rate, latency, saturazione
├── slo.rules.yml              # burn rate alerts SLO-based
└── recording.rules.yml        # tutte le recording rules
```

!!! tip "Un file per dominio"
    Organizzare le regole per dominio funzionale (non per severità) facilita la manutenzione: chi è responsabile di Kubernetes trova tutte le sue regole in un solo file. La severità appartiene alle labels, non ai nomi dei file.

### Caricamento in Prometheus

```yaml
# prometheus.yml
rule_files:
  - "rules/*.yml"              # glob pattern — include tutti i file
  - "rules/recording.rules.yml"  # oppure file specifici

# Reload senza restart (invia SIGHUP)
# curl -X POST http://prometheus:9090/-/reload
```

### PrometheusRule CRD (Kubernetes)

Con Prometheus Operator, le regole si gestiscono come risorse Kubernetes:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: app-alert-rules
  namespace: monitoring
  labels:
    prometheus: kube-prometheus   # selector usato dal Prometheus CR
    role: alert-rules
spec:
  groups:
    - name: app.rules
      rules:
        - alert: HighErrorRate
          expr: |
            rate(http_requests_total{status=~"5.."}[5m])
            / rate(http_requests_total[5m]) > 0.05
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "High error rate on {{ $labels.service }}"
```

```bash
# Applicare la PrometheusRule
kubectl apply -f app-rules.yaml

# Verificare che Prometheus l'abbia caricata
kubectl exec -n monitoring prometheus-0 -- \
  curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].name'
```

## Configurazione & Pratica

### Recording Rules — Ottimizzazione PromQL

Le recording rules pre-calcolano espressioni e salvano il risultato come nuove time series. Usarle quando:
1. La stessa query costosa è usata in più alert o dashboard
2. Si vuole calcolare aggregazioni cross-job per federation
3. La query ha un range vector lungo (es. `[1h]`) che rende lenta ogni valutazione

**Naming convention obbligatoria:** `level:metric:operation`

| Componente | Significato | Esempio |
|------------|-------------|---------|
| `level` | Livello di aggregazione | `job`, `instance`, `cluster`, `dc` |
| `metric` | Nome della metrica di base | `http_requests_total`, `latency_seconds` |
| `operation` | Operazione applicata | `rate5m`, `p99`, `count`, `sum` |

```yaml
# rules/recording.rules.yml
groups:
  - name: http_recording
    interval: 1m
    rules:
      # Rate di richieste per job (usato in alert e dashboard)
      - record: job:http_requests_total:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))

      # Rate di errori per job (usato per calcolare error ratio)
      - record: job:http_errors_total:rate5m
        expr: sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))

      # Error ratio (usato negli alert SLO)
      - record: job:http_error_ratio:rate5m
        expr: |
          job:http_errors_total:rate5m
          / job:http_requests_total:rate5m

      # Latenza p99 per job
      - record: job:http_request_duration_seconds:p99
        expr: |
          histogram_quantile(0.99,
            sum by (job, le) (
              rate(http_request_duration_seconds_bucket[5m])
            )
          )

  - name: slo_recording
    interval: 1m
    rules:
      # Rate su finestra 1h (per burn rate alerts)
      - record: job:http_errors_total:rate1h
        expr: sum by (job) (rate(http_requests_total{status=~"5.."}[1h]))

      - record: job:http_requests_total:rate1h
        expr: sum by (job) (rate(http_requests_total[1h]))

      # Rate su finestra 6h (per burn rate slow)
      - record: job:http_errors_total:rate6h
        expr: sum by (job) (rate(http_requests_total{status=~"5.."}[6h]))

      - record: job:http_requests_total:rate6h
        expr: sum by (job) (rate(http_requests_total[6h]))
```

!!! tip "Recording rules riducono il carico"
    Se 5 alert diversi usano `rate(http_requests_total[5m])` senza recording rules, Prometheus ricalcola questa espressione 5 volte a ogni ciclo. Con una recording rule, il calcolo avviene una volta sola e i 5 alert leggono il risultato pre-calcolato. Su grandi cardinality, questo riduce il carico della rule evaluation di ordini di grandezza.

### Alert Rules — Pattern USE e RED

#### USE Method (infrastruttura)

Il **USE Method** (Brendan Gregg) guida la creazione di alert per risorse fisiche: **U**tilization, **S**aturation, **E**rrors.

```yaml
groups:
  - name: use_method.rules
    rules:
      # --- CPU ---
      # Utilization: CPU usage sopra 80% per 10 minuti
      - alert: HighCPUUtilization
        expr: |
          100 - (avg by (instance) (
            rate(node_cpu_seconds_total{mode="idle"}[5m])
          ) * 100) > 80
        for: 10m
        labels:
          severity: warning
          method: USE
          resource: cpu
        annotations:
          summary: "High CPU utilization on {{ $labels.instance }}"
          description: "CPU utilization is {{ $value | humanize }}% (threshold: 80%)"
          runbook_url: "https://runbooks.company.com/high-cpu"

      # Saturation: load average > numero di core
      - alert: CPUSaturation
        expr: |
          node_load1 / count without(cpu, mode) (
            node_cpu_seconds_total{mode="idle"}
          ) > 1
        for: 5m
        labels:
          severity: warning
          method: USE
          resource: cpu
        annotations:
          summary: "CPU saturation on {{ $labels.instance }}"
          description: "Load average/core ratio is {{ $value | humanize }}"
          runbook_url: "https://runbooks.company.com/cpu-saturation"

      # --- Memoria ---
      # Utilization: memoria > 90%
      - alert: HighMemoryUtilization
        expr: |
          (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 90
        for: 5m
        labels:
          severity: critical
          method: USE
          resource: memory
        annotations:
          summary: "High memory utilization on {{ $labels.instance }}"
          description: "Memory usage is {{ $value | humanize }}% on {{ $labels.instance }}"
          runbook_url: "https://runbooks.company.com/high-memory"

      # --- Disco ---
      # Utilization: spazio disco > 85%
      - alert: DiskSpaceHigh
        expr: |
          (1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}
               / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) * 100 > 85
        for: 10m
        labels:
          severity: warning
          method: USE
          resource: disk
        annotations:
          summary: "Disk space high on {{ $labels.instance }}:{{ $labels.mountpoint }}"
          description: "{{ $value | humanize }}% used (threshold: 85%)"
          runbook_url: "https://runbooks.company.com/disk-space"

      # Saturation: predizione di esaurimento entro 24h
      - alert: DiskWillFillIn24h
        expr: |
          predict_linear(node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}[6h], 24*3600) < 0
        for: 30m
        labels:
          severity: critical
          method: USE
          resource: disk
        annotations:
          summary: "Disk predicted to fill in 24h on {{ $labels.instance }}"
          description: "Extrapolating current growth, disk will fill within 24 hours"
          runbook_url: "https://runbooks.company.com/disk-space"
```

#### RED Method (servizi)

Il **RED Method** (Tom Wilkie) guida la creazione di alert per servizi: **R**ate, **E**rrors, **D**uration.

```yaml
groups:
  - name: red_method.rules
    rules:
      # Rate: alert se il servizio non riceve richieste (possibile outage)
      - alert: ServiceNoTraffic
        expr: |
          sum by (service) (rate(http_requests_total[10m])) == 0
        for: 5m
        labels:
          severity: warning
          method: RED
          resource: rate
        annotations:
          summary: "No traffic on {{ $labels.service }}"
          description: "Service {{ $labels.service }} has received no requests in the last 10 minutes"
          runbook_url: "https://runbooks.company.com/no-traffic"

      # Errors: error rate > 5% per 5 minuti
      - alert: HighErrorRate
        expr: |
          sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
          / sum by (service) (rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
          method: RED
          resource: errors
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: >
            Error rate is {{ $value | humanizePercentage }} on {{ $labels.service }}
            (threshold: 5%)
          runbook_url: "https://runbooks.company.com/high-error-rate"

      # Duration: p99 latency > 1 secondo
      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum by (service, le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 1.0
        for: 5m
        labels:
          severity: warning
          method: RED
          resource: duration
        annotations:
          summary: "High p99 latency on {{ $labels.service }}"
          description: >
            P99 latency is {{ $value | humanizeDuration }} on {{ $labels.service }}
            (threshold: 1s)
          runbook_url: "https://runbooks.company.com/high-latency"
```

### SLO-Based Burn Rate Alerts

Gli alert SLO-based sono il pattern più maturo per i servizi production: invece di alertare su soglie arbitrarie, si alerta quando il budget di errore si sta esaurendo troppo velocemente.

**Concetto:** con uno SLO del 99.9% su 30 giorni, il budget di errore totale è 0.1% × 30gg × 24h × 60min = ~43.2 minuti di downtime. Se il sistema ha un error rate tale da esaurire questo budget in 1 ora (burn rate = 720x), bisogna alertare immediatamente.

**Multi-window, multi-burn-rate:** si usa una finestra corta per rilevare incidenti rapidi e una finestra lunga per confermare la tendenza, evitando falsi positivi.

| Burn Rate | Finestra corta | Finestra lunga | Severity | Budget consumato in |
|-----------|----------------|----------------|----------|---------------------|
| 14.4x | 1h | 5m | critical (page) | ~2 ore |
| 6x | 6h | 30m | warning (ticket) | ~5 ore |
| 3x | 3 giorni | 6h | info | ~10 giorni |

```yaml
# rules/slo.rules.yml
groups:
  - name: slo_burn_rate.rules
    rules:
      # --- Fast burn (critical) ---
      # Budget si esaurisce in ~2 ore: alert immediato
      - alert: SLOBurnRateCritical
        expr: |
          (
            job:http_errors_total:rate1h / job:http_requests_total:rate1h > 14.4 * 0.001
          ) and (
            job:http_errors_total:rate5m / job:http_requests_total:rate5m > 14.4 * 0.001
          )
        for: 2m
        labels:
          severity: critical
          slo: "availability-99.9"
        annotations:
          summary: "SLO critical burn rate for {{ $labels.job }}"
          description: >
            Error budget burning at 14.4x rate for {{ $labels.job }}.
            At this rate, the monthly error budget will be exhausted in ~2 hours.
          runbook_url: "https://runbooks.company.com/slo-burn-rate"

      # --- Medium burn (warning) ---
      # Budget si esaurisce in ~5 ore: ticket urgente
      - alert: SLOBurnRateHigh
        expr: |
          (
            job:http_errors_total:rate6h / job:http_requests_total:rate6h > 6 * 0.001
          ) and (
            job:http_errors_total:rate30m / job:http_requests_total:rate30m > 6 * 0.001
          )
        for: 15m
        labels:
          severity: warning
          slo: "availability-99.9"
        annotations:
          summary: "SLO elevated burn rate for {{ $labels.job }}"
          description: >
            Error budget burning at 6x rate for {{ $labels.job }}.
            At this rate, the monthly error budget will be exhausted in ~5 days.
          runbook_url: "https://runbooks.company.com/slo-burn-rate"
```

!!! note "Il valore 0.001 negli alert SLO"
    `0.001` rappresenta l'error budget: `1 - SLO = 1 - 0.999 = 0.001`. Per uno SLO del 99.5% usare `0.005`, per 99% usare `0.01`. Il moltiplicatore (14.4, 6) è il burn rate factor — quante volte più veloce del normale si sta consumando il budget.

### Alert Kubernetes

```yaml
groups:
  - name: kubernetes.rules
    rules:
      # Pod in CrashLoopBackOff
      - alert: PodCrashLooping
        expr: |
          increase(kube_pod_container_status_restarts_total[15m]) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} is crash looping"
          description: >
            Container {{ $labels.container }} in pod {{ $labels.pod }}
            has restarted {{ $value | humanize }} times in the last 15 minutes.
          runbook_url: "https://runbooks.company.com/pod-crash-loop"

      # Deployment non raggiunge il numero di repliche desiderate
      - alert: DeploymentReplicasMismatch
        expr: |
          kube_deployment_spec_replicas != kube_deployment_status_available_replicas
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Deployment {{ $labels.namespace }}/{{ $labels.deployment }} has unavailable replicas"
          description: >
            Deployment {{ $labels.deployment }} in {{ $labels.namespace }}
            has {{ $value | humanize }} unavailable replicas.
          runbook_url: "https://runbooks.company.com/deployment-replicas"

      # PersistentVolumeClaim in stato Pending
      - alert: PVCPending
        expr: kube_persistentvolumeclaim_status_phase{phase="Pending"} == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "PVC {{ $labels.namespace }}/{{ $labels.persistentvolumeclaim }} is pending"
          description: "PVC has been in Pending state for more than 5 minutes."
          runbook_url: "https://runbooks.company.com/pvc-pending"

      # Node NotReady
      - alert: NodeNotReady
        expr: kube_node_status_condition{condition="Ready", status="true"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Node {{ $labels.node }} is not ready"
          description: "Node {{ $labels.node }} has been in NotReady state for more than 5 minutes."
          runbook_url: "https://runbooks.company.com/node-not-ready"
```

## Best Practices

### Severity Levels — Convezione Operativa

!!! warning "Alert fatigue: il rischio principale"
    Usare `severity: critical` per tutto è l'anti-pattern più pericoloso. Quando ogni alert è critico, nessun alert è critico. I team iniziano a ignorare le notifiche, e un incidente reale viene sommerso dal rumore.

| Severity | Significato | Azione | Canale |
|----------|-------------|--------|--------|
| `critical` | Impatto immediato su utenti; SLO a rischio ora | Page on-call immediato | PagerDuty, SMS |
| `warning` | Tendenza preoccupante; intervento in ore | Ticket Jira, Slack #alerts | Slack |
| `info` | Informazione operativa; intervento in giorni | Slack #monitoring | Slack (low-priority) |

### Campo `for` — Linee Guida

| Tipo di alert | `for` consigliato | Motivo |
|---------------|-------------------|--------|
| Infrastruttura critica (node down) | `1m` - `2m` | Breve, ma evita falsi positivi da restart |
| Error rate servizi | `5m` | Spike brevi (deploy) non devono generare page |
| Disk filling | `10m` - `30m` | Tendenza, non emergenza immediata |
| SLO burn rate fast | `2m` | Fast burn richiede risposta rapida |
| Latenza degradata | `5m` - `10m` | La latenza può variare temporaneamente |

!!! warning "Alert senza `for`: il flapping killer"
    Senza `for`, un'anomalia di 15 secondi genera una notifica. Se l'anomalia persiste 30 secondi, genera resolved + firing in sequenza. Questo pattern — chiamato flapping — satura Alertmanager e i canali di notifica, e porta il team a silenziare gli alert invece di risolverli.

### Runbook URL — Obbligatorio in Produzione

Ogni alert production deve avere un `runbook_url` nelle annotations. Un runbook contiene:

```markdown
## High Error Rate — Runbook

### Sintomi
- Alert: HighErrorRate firing per servizio X
- Dashboard: https://grafana.company.com/d/xxx

### Causa comune
1. Deploy recente con regressione
2. Dipendenza a valle in errore
3. Database connection pool esaurito

### Diagnosi
\`\`\`bash
# Verificare deploy recenti
kubectl rollout history deployment/service-x

# Controllare i log degli errori
kubectl logs -l app=service-x --since=10m | grep ERROR

# Verificare dipendenze
curl http://service-x/health/dependencies
\`\`\`

### Risoluzione
- Se deploy recente: `kubectl rollout undo deployment/service-x`
- Se dipendenza: segui runbook della dipendenza
```

### Anti-Pattern da Evitare

| Anti-Pattern | Problema | Soluzione |
|---|---|---|
| Alert senza `for` | Flapping per spike brevi | Aggiungere `for: 5m` minimo |
| Tutto `severity: critical` | Alert fatigue, nessuno risponde | Usare la scala critical/warning/info |
| Alert su raw counter senza `rate()` | Sempre firing dopo restart | Usare `rate()` o `increase()` |
| `for` troppo lungo su critical | Incidente non rilevato in tempo | Max 5m per critical |
| Labels con `$value` | Deduplication rotta in Alertmanager | `$value` solo nelle annotations |
| Alert ridondanti (overlap) | Notifiche duplicate | Usare inhibition rules in Alertmanager |
| Soglia fissa senza baseline | Troppi falsi positivi in peak | Usare percentili o burn rate |

## Tooling — Validazione e Test

### promtool check rules

```bash
# Validare la sintassi di un file di regole
promtool check rules rules/application.rules.yml

# Validare tutti i file
promtool check rules rules/*.yml

# Output atteso (no errori)
# Checking rules/application.rules.yml
#   SUCCESS: 12 rules found

# Output con errore
# rules/application.rules.yml: 15:5: unknown field "fore" in rule
```

### promtool test rules — Unit Test

Prometheus supporta unit test nativi per le regole: si definisce una serie temporale sintetica, si esegue la rule, si verifica che l'alert si attivi come atteso.

```yaml
# tests/application.rules.test.yml
rule_files:
  - ../rules/recording.rules.yml
  - ../rules/application.rules.yml

evaluation_interval: 1m

tests:
  # Test: HighErrorRate si attiva quando error rate > 5%
  - interval: 1m
    input_series:
      # Simula 100 richieste al minuto, 10 con errore (10%)
      - series: 'http_requests_total{service="api", status="200"}'
        values: '0+90x10'    # 0, 90, 180, ... (90 req buone al minuto)
      - series: 'http_requests_total{service="api", status="500"}'
        values: '0+10x10'    # 0, 10, 20, ... (10 req errore al minuto)
    alert_rule_test:
      - eval_time: 10m
        alertname: HighErrorRate
        exp_alerts:
          - exp_labels:
              severity: critical
              team: backend
              service: api
            exp_annotations:
              summary: "High error rate on api"

  # Test: HighErrorRate NON si attiva con error rate sotto soglia
  - interval: 1m
    input_series:
      - series: 'http_requests_total{service="api", status="200"}'
        values: '0+98x10'
      - series: 'http_requests_total{service="api", status="500"}'
        values: '0+2x10'    # solo 2%, sotto il 5%
    alert_rule_test:
      - eval_time: 10m
        alertname: HighErrorRate
        exp_alerts: []  # nessun alert atteso
```

```bash
# Eseguire i test
promtool test rules tests/application.rules.test.yml

# Output successo
# Unit Testing:  tests/application.rules.test.yml
#   SUCCESS
```

### Integrazione CI/CD

```yaml
# .github/workflows/prometheus-rules.yml
name: Validate Prometheus Rules

on:
  pull_request:
    paths:
      - 'rules/**'
      - 'tests/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install promtool
        run: |
          PROMETHEUS_VERSION="2.50.0"
          wget -q https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz
          tar xzf prometheus-*.tar.gz
          sudo mv prometheus-*/promtool /usr/local/bin/

      - name: Check rule syntax
        run: |
          promtool check rules rules/*.yml
          echo "✓ All rules are syntactically valid"

      - name: Run unit tests
        run: |
          promtool test rules tests/*.test.yml
          echo "✓ All unit tests passed"
```

```yaml
# Versione GitLab CI
validate-prometheus-rules:
  image: prom/prometheus:latest
  stage: validate
  script:
    - promtool check rules rules/*.yml
    - promtool test rules tests/*.test.yml
  rules:
    - changes:
        - rules/**
        - tests/**
```

## Troubleshooting

### Alert non si attiva nonostante la condizione sia vera

**Sintomo:** L'expression restituisce valori in PromQL UI ma l'alert non va in Firing.

**Causa 1:** Il campo `for` non è trascorso — l'alert è in `Pending`.
```bash
# Verificare lo stato nella UI Prometheus: /alerts
# Oppure via API
curl http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="HighErrorRate")'
# Cercare "state": "pending" vs "firing"
```

**Causa 2:** La metrica ha label cardinality che non matcha il selettore.
```promql
# Debug: verificare esattamente le labels disponibili
http_requests_total{status=~"5.."}
# Se non restituisce risultati, il problema è nel selettore di labels
```

---

### Alert che va in Firing e Resolved ogni pochi minuti (flapping)

**Sintomo:** Notifiche continue di FIRING e RESOLVED per lo stesso alert.

**Causa:** Campo `for` assente o troppo breve; il segnale oscilla intorno alla soglia.

**Soluzione:**
```yaml
# Prima (flapping)
- alert: HighCPU
  expr: cpu_usage > 80
  # nessun for

# Dopo (stabile)
- alert: HighCPU
  expr: cpu_usage > 80
  for: 10m  # deve rimanere sopra soglia per 10 minuti

# Alternativa: smussare il segnale con media mobile
- alert: HighCPU
  expr: avg_over_time(cpu_usage[10m]) > 80
  for: 5m
```

---

### Recording rule non produce time series

**Sintomo:** La recording rule è definita ma la metrica non appare in Prometheus.

**Causa 1:** Errore di sintassi nel nome della recording rule.
```bash
promtool check rules rules/recording.rules.yml
# Verificare che non ci siano errori
```

**Causa 2:** L'espressione non restituisce risultati (metrica sorgente assente).
```promql
# Testare l'espressione direttamente nella UI
rate(http_requests_total[5m])
# Se non ritorna nulla, la metrica sorgente non esiste
```

**Causa 3:** Il file non è incluso in `rule_files`.
```bash
# Verificare la configurazione Prometheus
curl http://prometheus:9090/api/v1/status/config | jq '.data.yaml' | grep rule_files -A 5
```

---

### Alert con `for` che non rispetta il tempo configurato

**Sintomo:** Un alert con `for: 5m` va in Firing dopo 3 minuti.

**Causa:** L'`evaluation_interval` influenza la granularità. Con `evaluation_interval: 1m`, il `for: 5m` richiede 5 cicli di valutazione consecutivi positivi. Se il ciclo salta (Prometheus restart, overload), il timer si azzera.

**Soluzione:** Per alert critici con `for` breve, ridurre `evaluation_interval` nel gruppo:
```yaml
groups:
  - name: critical.rules
    interval: 15s  # override — valutazione più frequente
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
```

---

### Troppi alert contemporaneamente (alert storm)

**Sintomo:** Decine di alert si attivano in simultanea durante un incidente.

**Causa:** Mancanza di aggregazione e inhibition. Un'unica causa radice genera cascata di sintomi.

**Soluzione 1:** Aggregare nella expr invece di avere N alert per N istanze:
```yaml
# Prima: un alert per ogni pod (N alert)
expr: container_memory_usage_bytes > 500000000

# Dopo: un alert con count dei pod affetti
expr: count(container_memory_usage_bytes > 500000000) by (namespace) > 3
```

**Soluzione 2:** Inhibition rules in Alertmanager (sopprime alert derivati):
```yaml
# alertmanager.yml
inhibit_rules:
  # Se un node è down, sopprimi tutti gli alert dei pod su quel node
  - source_matchers: [alertname="NodeNotReady"]
    target_matchers: [alertname=~"Pod.*"]
    equal: [node]
```

## Relazioni

??? info "Prometheus — Architettura e PromQL"
    Prometheus è il motore che valuta le regole. Conoscere l'architettura (TSDB, scraping, evaluation loop) e PromQL è prerequisito per scrivere regole efficaci.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Alertmanager — Routing delle Notifiche"
    Le alert rules definiscono *quando* generare un alert; Alertmanager definisce *chi notificare, come, e quando*. I labels definiti nelle rules sono usati da Alertmanager per il routing tree.

    **Approfondimento completo →** [Alertmanager](./alertmanager.md)

??? info "SLO/SLA/SLI — Reliability Targets"
    Gli SLO definiscono i target di affidabilità; le SLO-based burn rate alerts sono il modo più robusto per tradurre quegli SLO in alert azionabili.

    **Approfondimento completo →** [SLO/SLA/SLI](../sre/slo-sla-sli.md)

??? info "Error Budget — Gestione del Budget"
    Il budget di errore è il concetto che rende sensato il burn rate alerting: gli alert SLO-based si attivano quando il budget si sta esaurendo troppo velocemente.

    **Approfondimento completo →** [Error Budget](../sre/error-budget.md)

## Riferimenti

- [Documentazione ufficiale — Alerting Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Documentazione ufficiale — Recording Rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Documentazione ufficiale — Unit Testing](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/)
- [Google SRE Book — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Awesome Prometheus Alerts — Libreria di regole pronte](https://awesome-prometheus-alerts.grep.to/)
- [Prometheus Operator — PrometheusRule CRD](https://prometheus-operator.dev/docs/user-guides/alerting/)
- [Runbook template — Robust Perception](https://www.robustperception.io/why-does-a-prometheus-alert-have-both-a-for-and-annotations/)
