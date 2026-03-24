---
title: "Alertmanager"
slug: alertmanager
category: monitoring
tags: [alertmanager, alerting, prometheus, on-call, routing, pagerduty, slack]
search_keywords: [alertmanager, alert routing, alerting, notifiche, on-call, silencing, inhibition, grouping, prometheus alerts, pagerduty, slack alerts, opsgenie, routing tree, receiver, alert deduplication]
parent: monitoring/alerting/_index
related: [monitoring/tools/prometheus, monitoring/sre/slo-sla-sli, monitoring/tools/grafana]
official_docs: https://prometheus.io/docs/alerting/latest/alertmanager/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Alertmanager

## Panoramica

Alertmanager è il componente dell'ecosistema Prometheus responsabile della gestione del ciclo di vita degli alert: riceve gli alert dalle istanze Prometheus, li aggrega, li de-duplica, li instrada verso i canali di notifica corretti (Slack, PagerDuty, OpsGenie, email), e gestisce silencing e inibizione. È separato da Prometheus per una ragione precisa: la generazione degli alert (dove c'è un problema) è separata dalla politica di notifica (chi deve essere avvisato, come, quando). Alertmanager permette di centralizzare questa politica in un unico luogo anche se si hanno N istanze Prometheus.

## Concetti Chiave

### Routing Tree

Il routing tree è la configurazione centrale di Alertmanager: un albero di nodi che descrive come ogni alert viene instradato.

```
root (catch-all receiver)
├── match: severity=critical  → PagerDuty (on-call immediato)
├── match: team=database       → Slack #db-alerts
├── match: team=platform       → Slack #platform-alerts
└── default                    → Slack #alerts-general
```

### Grouping

Il grouping aggrega alert simili in un'unica notifica per evitare alert flooding.

!!! example "Esempio"
    Se 50 pod crashano contemporaneamente, Alertmanager raggruppa tutti gli alert in **un'unica notifica** invece di inviare 50 messaggi. Il gruppo è definito dai label specificati in `group_by`.

### Silencing

Un silenzio temporaneo che sopprime le notifiche per alert che matchano un selettore di label. Usato durante manutenzioni pianificate.

### Inhibition

Meccanismo che sopprime automaticamente alert "minori" quando un alert "maggiore" è già attivo. Esempio: non inviare alert sui singoli servizi se è già attivo un alert di "cluster down".

### Receivers

Un receiver definisce uno o più metodi di notifica. Ogni route punta a un receiver.

## Architettura / Come Funziona

```
┌─────────────────────────────────────────────────────────┐
│                    Alertmanager                          │
│                                                           │
│  Prometheus ──▶ /api/v1/alerts (POST)                   │
│                        │                                  │
│                 ┌──────▼──────────┐                      │
│                 │  Dispatcher     │                       │
│                 │  (routing tree) │                       │
│                 └──────┬──────────┘                       │
│                        │                                  │
│           ┌────────────┼────────────┐                    │
│           ▼            ▼            ▼                    │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│    │  Group 1 │  │  Group 2 │  │  Group 3 │            │
│    │(platform)│  │(database)│  │(critical)│            │
│    └──────┬───┘  └──────┬───┘  └──────┬───┘            │
│           │             │              │                 │
│    ┌──────▼───┐  ┌──────▼───┐  ┌──────▼───┐            │
│    │  Slack   │  │  Slack   │  │PagerDuty │            │
│    │ #platform│  │   #db    │  │          │            │
│    └──────────┘  └──────────┘  └──────────┘            │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Silence Manager │ Inhibition Engine              │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Timing degli Alert

```
Prometheus: PENDING ──(for: 5m)──▶ FIRING ──▶ Alertmanager
Alertmanager: riceve alert ──(group_wait: 30s)──▶ prima notifica
              continua ──(group_interval: 5m)──▶ aggiornamenti gruppo
              risolto ──(repeat_interval: 4h)──▶ stop notifiche
```

- **`group_wait`**: quanto attendere prima della prima notifica (aggregazione iniziale)
- **`group_interval`**: quanto attendere prima di aggiornare un gruppo già notificato
- **`repeat_interval`**: quanto attendere prima di re-notificare un alert ancora attivo

## Configurazione & Pratica

### Configurazione Base

```yaml
# alertmanager.yml
global:
  # Timeout per i receiver
  resolve_timeout: 5m

  # Configurazione SMTP globale
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alertmanager@example.com'
  smtp_auth_username: 'alertmanager'
  smtp_auth_password: 'password'

  # Slack globale
  slack_api_url: 'https://hooks.slack.com/services/T00000000/B00000000/XXXX'

# Routing tree
route:
  # Receiver di default (catch-all)
  receiver: 'slack-general'

  # Raggruppa per alertname e cluster
  group_by: ['alertname', 'cluster', 'namespace']

  # Prima notifica dopo 30 secondi
  group_wait: 30s

  # Aggiornamenti ogni 5 minuti
  group_interval: 5m

  # Re-notifica ogni 4 ore se ancora attivo
  repeat_interval: 4h

  # Sotto-route (override del comportamento predefinito)
  routes:
    # Alert critici → PagerDuty immediato
    - match:
        severity: critical
      receiver: pagerduty-critical
      group_wait: 10s
      repeat_interval: 1h
      continue: false  # stop: non valutare altre route

    # Alert del team database
    - match:
        team: database
      receiver: slack-database
      group_by: ['alertname', 'instance']

    # Alert di infra → Slack + email
    - match_re:
        alertname: "^(Node|Disk|CPU|Memory).*"
      receiver: slack-infra
      routes:
        # Sotto-sotto-route: se anche severity=critical, PagerDuty
        - match:
            severity: critical
          receiver: pagerduty-critical

# Receiver definitions
receivers:
  - name: 'slack-general'
    slack_configs:
      - channel: '#alerts-general'
        title: '{{ template "slack.title" . }}'
        text: '{{ template "slack.text" . }}'
        send_resolved: true
        color: '{{ if eq .Status "firing" }}danger{{ else }}good{{ end }}'

  - name: 'slack-database'
    slack_configs:
      - channel: '#db-alerts'
        send_resolved: true

  - name: 'slack-infra'
    slack_configs:
      - channel: '#infra-alerts'
        send_resolved: true
    email_configs:
      - to: 'infra-team@example.com'
        send_resolved: true

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - routing_key: 'YOUR_PAGERDUTY_ROUTING_KEY'
        severity: '{{ if eq .CommonLabels.severity "critical" }}critical{{ else }}warning{{ end }}'
        description: '{{ .CommonAnnotations.summary }}'
        details:
          firing: '{{ .Alerts.Firing | len }}'
          resolved: '{{ .Alerts.Resolved | len }}'
          namespace: '{{ .CommonLabels.namespace }}'
        send_resolved: true

# Regole di inibizione
inhibit_rules:
  # Se il cluster è down, non notificare i singoli pod/service
  - source_match:
      alertname: 'ClusterDown'
    target_match_re:
      alertname: '^(PodCrashLooping|ServiceDown|HighErrorRate)$'
    equal: ['cluster']

  # Se un nodo è down, non notificare i pod su quel nodo
  - source_match:
      alertname: 'NodeDown'
    target_match_re:
      alertname: '^(Pod.*)$'
    equal: ['node']
```

### Template Personalizzati

```yaml
# alertmanager.yml — aggiungere i file template
templates:
  - '/etc/alertmanager/templates/*.tmpl'
```

```
{{/* /etc/alertmanager/templates/slack.tmpl */}}
{{ define "slack.title" }}
  [{{ .Status | toUpper }}{{ if eq .Status "firing" }}:{{ .Alerts.Firing | len }}{{ end }}]
  {{ .CommonLabels.alertname }} @ {{ .CommonLabels.cluster }}
{{ end }}

{{ define "slack.text" }}
  {{ range .Alerts }}
  *Alert:* {{ .Annotations.summary }}
  *Description:* {{ .Annotations.description }}
  *Severity:* `{{ .Labels.severity }}`
  *Namespace:* `{{ .Labels.namespace }}`
  {{ if .Annotations.runbook_url }}*Runbook:* <{{ .Annotations.runbook_url }}|Link>{{ end }}
  ---
  {{ end }}
{{ end }}
```

### Deploy su Kubernetes con Helm

```bash
# Alertmanager è incluso in kube-prometheus-stack
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set alertmanager.config.global.slack_api_url="https://hooks.slack.com/..." \
  --values alertmanager-values.yaml
```

```yaml
# alertmanager-values.yaml
alertmanager:
  config:
    global:
      resolve_timeout: 5m
    route:
      receiver: 'slack-default'
      group_by: ['alertname', 'namespace']
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 12h
    receivers:
      - name: 'slack-default'
        slack_configs:
          - api_url: 'https://hooks.slack.com/services/...'
            channel: '#alerts'
            send_resolved: true
```

### Alta Disponibilità

```bash
# Alertmanager supporta clustering nativo
# Ogni istanza conosce le altre tramite --cluster.peer

alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --cluster.listen-address="0.0.0.0:9094" \
  --cluster.peer="alertmanager-0.alertmanager:9094" \
  --cluster.peer="alertmanager-1.alertmanager:9094"
```

```yaml
# Kubernetes StatefulSet per HA
# Helm kube-prometheus-stack
alertmanager:
  alertmanagerSpec:
    replicas: 3
    podAntiAffinity: hard  # una replica per nodo
```

### Silencing via API

```bash
# Creare un silenzio via curl (manutenzione pianificata)
curl -X POST http://alertmanager:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "namespace", "value": "staging", "isRegex": false},
      {"name": "alertname", "value": ".*", "isRegex": true}
    ],
    "startsAt": "2026-03-24T22:00:00Z",
    "endsAt": "2026-03-25T06:00:00Z",
    "comment": "Manutenzione pianificata staging",
    "createdBy": "ops-team"
  }'

# Elencare silences attivi
curl http://alertmanager:9093/api/v2/silences

# Rimuovere un silenzio
curl -X DELETE http://alertmanager:9093/api/v2/silences/SILENCE_ID
```

### amtool — CLI per Alertmanager

```bash
# Installazione
go install github.com/prometheus/alertmanager/cmd/amtool@latest

# Configurazione
cat > ~/.config/amtool/config.yml << EOF
alertmanager.url: http://localhost:9093
EOF

# Verificare la configurazione
amtool check-config /etc/alertmanager/alertmanager.yml

# Elencare alert attivi
amtool alert

# Filtrare alert
amtool alert --filter='severity=critical'

# Creare un silenzio
amtool silence add alertname=~".*" --comment="Manutenzione" --duration=2h

# Elencare silences
amtool silence

# Verificare il routing (quale receiver riceverà l'alert)
amtool config routes test --verify-receivers=pagerduty-critical \
  alertname=HighErrorRate severity=critical namespace=prod
```

## Best Practices

### Struttura delle Route

```yaml
routes:
  # Regola 1: Più specifica prima
  - matchers:
      - alertname="KubernetesPodCrashLooping"
      - severity="critical"
    receiver: pagerduty-critical

  # Regola 2: Meno specifica dopo
  - matchers:
      - severity="critical"
    receiver: pagerduty-general

  # Regola 3: Default
  # (implicita: receiver del nodo padre)
```

### Avoidance del Notification Fatigue

- Usare `group_by` per aggregare alert correlati
- Impostare `repeat_interval` ragionevole (non ogni 5 minuti)
- Usare inhibition per sopprimere i sintomi quando è nota la causa root
- Separare gli alert "da svegliare qualcuno" (PagerDuty) da quelli "da guardare domani" (Slack)
- Mai alertare su metriche infrastrutturali senza correlazione con l'impatto utente

!!! tip "Regola d'oro"
    Ogni alert che ti sveglia di notte deve essere **actionable**. Se non sai cosa fare quando arriva quell'alert, o è un alert non necessario (abbassa la severità), o manca il runbook (scrivilo).

### Routing per Ambiente

```yaml
routes:
  # Prod → on-call
  - matchers:
      - env="prod"
      - severity="critical"
    receiver: pagerduty-prod
    repeat_interval: 1h

  # Staging → solo Slack, nessun on-call
  - matchers:
      - env="staging"
    receiver: slack-staging
    repeat_interval: 24h

  # Dev → silenzio fuori orario
  - matchers:
      - env="dev"
    receiver: slack-dev
    mute_time_intervals:
      - out-of-business-hours

time_intervals:
  - name: out-of-business-hours
    time_intervals:
      - times:
          - start_time: '00:00'
            end_time: '08:00'
          - start_time: '18:00'
            end_time: '24:00'
        weekdays: ['monday:friday']
      - weekdays: ['saturday', 'sunday']
```

## Troubleshooting

### Alert Non Arrivano

```bash
# Verificare che Prometheus stia inviando alert ad Alertmanager
curl http://prometheus:9090/api/v1/alerts

# Verificare che Alertmanager riceva gli alert
curl http://alertmanager:9093/api/v2/alerts

# Debug del routing
amtool config routes test alertname=MyAlert severity=critical

# Verificare i log di Alertmanager
kubectl logs -n monitoring alertmanager-pod

# Verificare se l'alert è silenced
amtool silence query alertname=MyAlert
```

### Troppe Notifiche

1. Aumentare `group_wait` per dare più tempo all'aggregazione
2. Aumentare `repeat_interval` per ridurre le re-notifiche
3. Aggiungere regole di inibizione per sopprimere i sintomi
4. Verificare se alcuni alert sono falsi positivi e alzare le soglie

### Config Non Valida

```bash
amtool check-config /etc/alertmanager/alertmanager.yml
# oppure
curl -X POST http://alertmanager:9093/-/reload
# e verificare i log per errori di parsing
```

## Relazioni

??? info "Prometheus — Sorgente degli Alert"
    Prometheus valuta le alerting rules e invia gli alert attivi ad Alertmanager tramite HTTP.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "SLO/SLA/SLI — Alert SLO-based"
    Gli alert di burn rate per gli SLO vengono gestiti e routati tramite Alertmanager.

    **Approfondimento completo →** [SLO/SLA/SLI](../sre/slo-sla-sli.md)

??? info "Grafana — Unified Alerting"
    Grafana v9+ ha un proprio alerting engine che può usare Alertmanager come backend o sostituirlo.

    **Approfondimento completo →** [Grafana](../tools/grafana.md)

## Riferimenti

- [Documentazione ufficiale Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Alertmanager configuration reference](https://prometheus.io/docs/alerting/latest/configuration/)
- [amtool CLI](https://github.com/prometheus/alertmanager?tab=readme-ov-file#amtool)
- [Routing tree editor (Prometheus)](https://prometheus.io/webtools/alerting/routing-tree-editor/)
- [Alertmanager Helm chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/alertmanager)
- [PagerDuty integration](https://www.pagerduty.com/docs/guides/prometheus-integration-guide/)
