---
title: "Incident Management — SRE"
slug: incident-management
category: monitoring
tags: [sre, incident-management, on-call, postmortem, runbook, pagerduty, opsgenie, mttr, severity]
search_keywords: [incident management, gestione incidenti, on-call, oncall, on call rotation, reperibilità, pagerduty, opsgenie, victorops, runbook, playbook, war room, blameless postmortem, post mortem, postmortem, retrospettiva incidente, severity, severità, severity level, incident severity, mttr, mean time to recover, mean time to resolve, mtta, mean time to acknowledge, mttd, mean time to detect, incident commander, incident response, escalation, escalation policy, sre, site reliability engineering, slo violation, on-call fatigue, alert fatigue, incident retrospective, root cause analysis, rca]
parent: monitoring/sre/_index
related: [monitoring/sre/slo-sla-sli, monitoring/sre/error-budget, monitoring/alerting/alertmanager, monitoring/tools/prometheus, monitoring/tools/grafana]
official_docs: https://sre.google/sre-book/managing-incidents/
status: complete
difficulty: intermediate
last_updated: 2026-03-25
---

# Incident Management — SRE

## Panoramica

L'incident management è il processo strutturato con cui un team rileva, risponde, risolve e impara dai problemi che impattano i sistemi in produzione. In un contesto SRE, non è solo "spegnere l'incendio": è un ciclo continuo che va dalla detection (alert → on-call) alla resolution (mitigazione) fino al learning (postmortem → azioni preventive). Un buon processo di incident management riduce il MTTR (Mean Time To Recover), previene la ripetizione degli stessi errori e costruisce fiducia nei team. Va usato sistematicamente per ogni incidente che supera una certa severity — non solo per i grandi outage. Non va usato per problemi di routine già coperti da runbook automatici o per degradazioni che rientrano nell'error budget senza impatto utente.

## Concetti Chiave

### Severity Levels

La severity classifica l'impatto di un incidente e determina la risposta attesa. Ogni organizzazione definisce i propri livelli, ma il pattern a 4 livelli (SEV1–SEV4) è lo standard de facto.

| Severity | Nome | Impatto | Risposta attesa | Esempio |
|----------|------|---------|-----------------|---------|
| **SEV1** | Critical | Produzione completamente down o perdita dati | Immediata (< 5 min ACK); war room attiva | API non raggiungibile; DB inaccessibile |
| **SEV2** | Major | Funzionalità core degradata per > X% utenti | Entro 15 min; escalation in corso | Latenza p99 > 5s; errori 5xx su pagamenti |
| **SEV3** | Minor | Funzionalità non-core impattata o workaround disponibile | Entro 1-2 ore | Dashboard lente; ricerche parzialmente broken |
| **SEV4** | Low | Impatto minimo, nessun utente bloccato | Next business day | Warning log ricorrenti; metrica di poca importanza anomala |

!!! warning "La severity si può cambiare durante l'incidente"
    Un incidente può partire SEV3 e diventare SEV1 man mano che si capisce l'impatto reale. Non aspettare la conferma completa per alzare la severity — è meglio over-escalate e abbassare che sotto-escalare e perdere tempo.

### Ruoli nell'Incidente

Un incidente ben gestito ha ruoli chiari e separati:

```
┌───────────────────────────────────────────────────────┐
│                    War Room / Bridge                   │
│                                                        │
│  ┌──────────────────────┐  ┌─────────────────────┐    │
│  │  Incident Commander  │  │  Communications Lead │    │
│  │  (IC)                │  │  (Comms)             │    │
│  │  - Coordina il team  │  │  - Aggiorna stakeh.  │    │
│  │  - Prende decisioni  │  │  - Status page       │    │
│  │  - Mantiene il focus │  │  - Comunicaz. esterna│    │
│  └──────────────────────┘  └─────────────────────┘    │
│                                                        │
│  ┌──────────────────────┐  ┌─────────────────────┐    │
│  │  Tech Lead / Ops     │  │  Scribe               │    │
│  │  - Indaga la causa   │  │  - Documenta timeline │    │
│  │  - Applica fix       │  │  - Registra azioni   │    │
│  │  - Esegue rollback   │  │  - Raccoglie evidenze│    │
│  └──────────────────────┘  └─────────────────────┘    │
└───────────────────────────────────────────────────────┘
```

!!! tip "L'IC non deve fare debug"
    L'Incident Commander coordina e prende decisioni — non si immerge nel codice. Se l'IC inizia a fare debug, perde la visione d'insieme e l'incidente si disorganizza. Devono essere persone diverse.

### Metriche di Performance

```
MTTD (Mean Time To Detect):
  Tempo tra l'inizio del problema e il primo alert/rilevamento.
  Target: < 5 min per SEV1, < 15 min per SEV2.

MTTA (Mean Time To Acknowledge):
  Tempo tra l'alert e il primo ACK da parte dell'on-call.
  Target: < 5 min (dipende dall'escalation policy).

MTTR (Mean Time To Recover/Resolve):
  Tempo tra l'inizio del problema e la risoluzione completa.
  Metrica principale per valutare l'efficacia del processo.

MTBF (Mean Time Between Failures):
  Tempo medio tra incidenti dello stesso tipo.
  Misura l'efficacia delle azioni preventive post-postmortem.
```

## Architettura / Come Funziona

### Ciclo di Vita di un Incidente

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO INCIDENT MANAGEMENT                     │
│                                                                   │
│  1. DETECT         2. RESPOND          3. RESOLVE                │
│  ──────────        ───────────         ──────────                 │
│  Alert fired       On-call ACK         Mitigazione               │
│  SLO violation     Severity assigned   o fix temporaneo          │
│  User report       Ruoli assegnati     Servizio ripristinato      │
│  Anomaly detect.   War room aperta     All-clear dichiarato       │
│        │                 │                    │                   │
│        ▼                 ▼                    ▼                   │
│  4. DOCUMENT       5. LEARN            6. PREVENT                │
│  ───────────       ──────────          ──────────                 │
│  Timeline scritta  Postmortem          Action items               │
│  Root cause doc.   Blameless review    Fix permanente             │
│  Impatto misurato  Lezioni apprese     Runbook aggiornato         │
│                                        SLO/alert rivalutati       │
└─────────────────────────────────────────────────────────────────┘
```

### On-Call Rotation

L'on-call rotation definisce chi è responsabile di rispondere agli alert in un dato momento. Una buona rotation bilancia responsabilità e sostenibilità.

```yaml
# Esempio configurazione rotation in OpsGenie/PagerDuty (concettuale)
rotation:
  name: "Platform Team On-Call"
  type: weekly           # o daily, bi-weekly
  participants:
    - user: alice@company.com
    - user: bob@company.com
    - user: carol@company.com
    - user: dave@company.com

escalation_policy:
  - level: 1
    targets: [current_on_call]
    timeout: 5m          # Se non ack entro 5 min → escalate

  - level: 2
    targets: [backup_on_call]
    timeout: 10m         # Se non ack entro 10 min → escalate

  - level: 3
    targets: [team_lead, engineering_manager]
    timeout: 15m
```

!!! warning "On-call fatigue è un problema reale"
    Troppi alert non-actionable, rotazioni troppo frequenti o turni notturni ricorrenti portano a burnout. Monitorare: numero di alert per turno, % alert che richiedono azione reale, ore di sonno interrotte. Se un on-call riceve più di 3 page per notte, il sistema di alerting va rivisto prima della persona.

### Struttura di un Runbook

Un runbook (o playbook) è la guida operativa per rispondere a un tipo specifico di alert. Deve essere eseguibile senza conoscenza pregressa del sistema.

```markdown
# Runbook: API Gateway — Alta Latenza (SEV2)

## Trigger
Alert: `APIGatewayLatencyHigh` — p99 > 2s per > 5 minuti

## Impatto stimato
Tutti gli utenti che usano l'API sperimentano rallentamenti.
Severity: SEV2 se p99 > 2s; SEV1 se p99 > 10s o error rate > 5%.

## Diagnostic Checklist (< 5 minuti)

### Step 1 — Verifica l'alert
```bash
# Controlla la latenza corrente
curl -s "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))' \
  | jq '.data.result[0].value[1]'
```

### Step 2 — Identifica il componente
```bash
# Latenza per servizio upstream
# Dashboard: https://grafana.internal/d/api-latency
# Controlla: database, cache, external API
```

### Step 3 — Azioni immediate

**Se la causa è il database:**
- Controlla connection pool: `kubectl exec -it db-pod -- psql -c "SELECT count(*) FROM pg_stat_activity;"`
- Se connection pool saturato → scala il pool o riavvia l'applicazione

**Se la causa è un deploy recente:**
- Rollback immediato: `kubectl rollout undo deployment/api-gateway`
- Verifica: `kubectl rollout status deployment/api-gateway`

**Se la causa è traffico anomalo:**
- Controlla rate limiting: `kubectl logs -l app=rate-limiter --tail=100`
- Scala orizzontalmente: `kubectl scale deployment/api-gateway --replicas=10`

## Escalation
Se non risolto entro 15 minuti → Escalate a SEV1, chiama il Tech Lead.

## Post-incident
- Aggiornare questo runbook con nuovi casi osservati
- Aprire ticket per fix permanente se necessario
```

## Configurazione & Pratica

### PagerDuty — Setup via Terraform

```hcl
# PagerDuty service e escalation policy
resource "pagerduty_service" "api_gateway" {
  name              = "API Gateway"
  escalation_policy = pagerduty_escalation_policy.platform.id
  alert_creation    = "create_alerts_and_incidents"

  incident_urgency_rule {
    type = "use_support_hours"
    during_support_hours {
      type    = "constant"
      urgency = "high"
    }
    outside_support_hours {
      type    = "constant"
      urgency = "low"   # non svegliare di notte per SEV3
    }
  }
}

resource "pagerduty_escalation_policy" "platform" {
  name = "Platform Team Escalation"

  rule {
    escalation_delay_in_minutes = 5
    target {
      type = "schedule_reference"
      id   = pagerduty_schedule.platform_oncall.id
    }
  }

  rule {
    escalation_delay_in_minutes = 10
    target {
      type = "user_reference"
      id   = pagerduty_user.team_lead.id
    }
  }
}

resource "pagerduty_schedule" "platform_oncall" {
  name      = "Platform On-Call"
  time_zone = "Europe/Rome"

  layer {
    name                         = "Weekly Rotation"
    start                        = "2026-01-01T00:00:00+01:00"
    rotation_virtual_start       = "2026-01-01T08:00:00+01:00"
    rotation_turn_length_seconds = 604800  # 1 settimana

    users = [
      pagerduty_user.alice.id,
      pagerduty_user.bob.id,
      pagerduty_user.carol.id,
    ]
  }
}
```

### Alertmanager — Routing verso PagerDuty/OpsGenie

```yaml
# alertmanager.yml — routing basato su severity
route:
  group_by: [alertname, cluster, service]
  group_wait:      30s
  group_interval:  5m
  repeat_interval: 4h
  receiver: slack-default

  routes:
    # SEV1/SEV2 → PagerDuty (sveglia l'on-call)
    - match_re:
        severity: "critical|warning"
      receiver: pagerduty-oncall
      continue: true   # invia anche a Slack

    # SEV1 → canale Slack dedicato agli incidenti
    - match:
        severity: critical
      receiver: slack-incidents

    # Tutto → Slack default
    - receiver: slack-default

receivers:
  - name: pagerduty-oncall
    pagerduty_configs:
      - routing_key: "${PAGERDUTY_INTEGRATION_KEY}"
        severity: "{{ if eq .CommonLabels.severity \"critical\" }}critical{{ else }}warning{{ end }}"
        description: "{{ .CommonAnnotations.summary }}"
        details:
          runbook: "{{ .CommonAnnotations.runbook }}"
          dashboard: "{{ .CommonAnnotations.dashboard }}"

  - name: slack-incidents
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#incidents"
        title: ":rotating_light: SEV1 — {{ .CommonAnnotations.summary }}"
        text: |
          *Alert:* {{ .CommonLabels.alertname }}
          *Service:* {{ .CommonLabels.service }}
          *Runbook:* {{ .CommonAnnotations.runbook }}

  - name: slack-default
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#monitoring"
        title: "[{{ .Status | toUpper }}] {{ .CommonAnnotations.summary }}"
```

### Template Postmortem

```markdown
# Postmortem: [Titolo Incidente]

**Data:** 2026-03-25
**Durata:** 14:32 → 16:05 (93 minuti)
**Severity:** SEV1 → SEV2 (declassato alle 15:10)
**Autore:** [Nome IC]
**Reviewer:** [Team Lead]
**Status:** Draft / In Review / Final

---

## Sommario

Breve descrizione dell'incidente in 2-3 frasi. Cosa è successo, qual è stato l'impatto, come è stato risolto.

---

## Impatto

| Metrica | Valore |
|---------|--------|
| Utenti impattati | ~12.000 (35% del traffico EU) |
| Servizi coinvolti | API Gateway, Auth Service |
| Error rate picco | 45% (normale: < 0.1%) |
| Latenza p99 picco | 8.2s (normale: 120ms) |
| Revenue stimata persa | ~€2.400 |
| SLO impatto | Error budget consumato: 18% del budget mensile |

---

## Timeline

```
14:32  Alert `APIGatewayLatencyHigh` fired (Prometheus)
14:33  PagerDuty notifica Alice (on-call)
14:37  Alice ACK (MTTA: 5 min)
14:38  War room aperta (#incident-20260325) — Alice (IC), Bob (ops), Carol (comms)
14:45  Carol aggiorna status page: "Investigating elevated latency"
14:52  Bob identifica: deploy delle 14:20 ha introdotto una query N+1 nel DB
14:55  Decisione: rollback del deploy
15:04  Rollback completato — latenza torna nella norma
15:10  Severity declassata a SEV2; monitoraggio esteso
15:30  Carol aggiorna status page: "Resolved"
16:05  All-clear dichiarato; incident chiuso
```

---

## Root Cause

**Causa diretta:** Deploy v2.8.3 dell'API Gateway ha introdotto una query N+1 nella gestione dei permessi utente. Ogni richiesta API generava 1 query per utente invece di 1 query per batch.

**Causa radice:** La query N+1 non è stata rilevata in staging perché il dataset di test ha < 100 utenti, mentre in produzione ci sono 300.000+ utenti attivi. Il load test pre-deploy non copriva lo scenario di accesso concorrente con molti utenti distinti.

---

## Cosa Ha Funzionato Bene

- Tempo di ACK rapido (5 min)
- Runbook per "alta latenza API" ha guidato il debug efficacemente
- Rollback eseguito in < 10 minuti dalla decisione
- Comunicazione esterna chiara e tempestiva

---

## Cosa Non Ha Funzionato

- Load test pre-deploy non ha simulato il traffico produzione realistico
- Nessun alert sul numero di query DB per richiesta (avrebbe rilevato il problema prima)
- La war room è rimasta aperta troppo a lungo senza obiettivo chiaro dopo il rollback

---

## Action Items

| Azione | Owner | Deadline | Priorità |
|--------|-------|----------|----------|
| Aggiungere query-count alert su DB (> 50 query/req → warning) | Bob | 2026-04-01 | P1 |
| Aggiornare load test con dataset realistico (> 10k utenti attivi) | Alice | 2026-04-08 | P1 |
| Fix permanente query N+1 in v2.8.4 | Dev Team | 2026-04-05 | P1 |
| Aggiungere staging DB con subset dati produzione (anonimizzato) | Platform | 2026-04-30 | P2 |
| Aggiornare runbook: aggiungere sezione "query DB anomale" | Bob | 2026-04-01 | P2 |
```

### Script: Metriche Incidente da Prometheus

```bash
#!/bin/bash
# incident-metrics.sh — Calcola MTTR e impatto da Prometheus
# Usage: ./incident-metrics.sh "2026-03-25T14:32:00Z" "2026-03-25T16:05:00Z"

START="$1"
END="$2"
PROM="${PROMETHEUS_URL:-http://localhost:9090}"

echo "=== Incident Metrics ==="
echo "Start: $START"
echo "End:   $END"
echo ""

# Error rate durante l'incidente
ERROR_RATE=$(curl -s "${PROM}/api/v1/query_range" \
  --data-urlencode "query=rate(http_requests_total{status=~\"5..\"}[5m])/rate(http_requests_total[5m])*100" \
  --data-urlencode "start=${START}" \
  --data-urlencode "end=${END}" \
  --data-urlencode "step=60" \
  | jq '[.data.result[0].values[].1 | tonumber] | max')
echo "Peak error rate: ${ERROR_RATE}%"

# Latenza p99 durante l'incidente
P99=$(curl -s "${PROM}/api/v1/query_range" \
  --data-urlencode "query=histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))" \
  --data-urlencode "start=${START}" \
  --data-urlencode "end=${END}" \
  --data-urlencode "step=60" \
  | jq '[.data.result[0].values[].1 | tonumber] | max')
echo "Peak p99 latency: ${P99}s"

# Budget consumato
BUDGET_CONSUMED=$(curl -s "${PROM}/api/v1/query" \
  --data-urlencode "query=100 - job:error_budget_remaining:30d" \
  | jq -r '.data.result[0].value[1]')
echo "Budget consumed (current): ${BUDGET_CONSUMED}%"
```

## Best Practices

### Blameless Postmortem

Il concetto di **blameless postmortem** (Google SRE) parte dal presupposto che gli incidenti sono fallimenti di sistema, non di persone. Un ingegnere che ha fatto un errore lo ha fatto in un contesto — con tool, processi e informazioni disponibili in quel momento — che ha reso possibile quell'errore.

!!! tip "Le domande giuste in un postmortem"
    Non chiedere "Chi ha causato l'incidente?" ma:
    - "Quale informazione mancava al momento della decisione?"
    - "Quale tool o processo ha reso possibile questo errore?"
    - "Come possiamo rendere impossibile ripetere questo errore?"
    Il focus sui sistemi, non sulle persone, produce action items più efficaci e crea una cultura in cui gli errori vengono segnalati invece che nascosti.

### Ridurre l'On-Call Fatigue

```
Regole pratiche per un on-call sostenibile:

1. Ogni alert deve essere actionable
   → Se un alert non richiede azione → eliminarlo o abbassare la severity
   → Target: < 5 alert per turno notturno

2. Runbook per ogni alert ripetuto
   → Se lo stesso alert si ripete 3+ volte senza runbook → creare il runbook

3. Compensazione
   → Turni notturni devono avere compensazione (economica o tempo libero)
   → Non mettere in on-call chi non conosce il sistema

4. Shadowing prima dell'on-call autonomo
   → Nuovi membri del team: 1-2 turni shadow prima di diventare primary

5. Review della rotation mensile
   → Analizzare: # page, MTTA, tipi di alert, orario degli alert
   → Eliminare alert rumorosi sistematicamente
```

### MTTR Improvement Loop

```
┌──────────────────────────────────────────────────────┐
│            MTTR Improvement Continuo                  │
│                                                        │
│  Misura MTTR ──▶ Identifica collo di bottiglia        │
│                          │                             │
│                          ▼                             │
│  Detect lento?     Improve alerting e SLI definition  │
│  ACK lento?        Migliorare escalation policy        │
│  Debug lento?      Aggiornare runbook e dashboard      │
│  Fix lento?        Automatizzare rollback o mitigaz.   │
│  Ricorrenza?       Fix permanente, non solo mitigation │
│                          │                             │
│                          ▼                             │
│            Misura di nuovo → ciclo continuo            │
└──────────────────────────────────────────────────────┘
```

### Gestione della War Room

```
Regole per una war room efficace:

✓ Aprire un canale dedicato (non usare canali generici)
✓ IC dichiara apertamente chi ha quale ruolo
✓ Scribe documenta in real time (futuro postmortem)
✓ Un task alla volta — IC assegna, non si sovrappongono le azioni
✓ Status update ogni 15-30 min verso gli stakeholder
✓ Dichiarare esplicitamente "all-clear" con motivazione
✓ Chiudere la war room non appena il servizio è stabile

✗ Non fare debug e coordinare contemporaneamente
✗ Non coinvolgere più persone del necessario
✗ Non prendere decisioni senza comunicarle all'IC
✗ Non applicare fix senza informare il team
```

## Troubleshooting

### Alert Storm: Troppi Alert Simultanei

**Sintomo:** Decine di alert si attivano contemporaneamente, l'on-call non riesce a capire qual è la causa radice.

**Causa:** Mancanza di correlazione degli alert — ogni sintomo genera un alert separato invece di groupare per causa.

**Soluzione:** Configurare grouping in Alertmanager e usare una dependency tree per silenziare alert figli quando scatta il parent.

```yaml
# alertmanager.yml — inibizione alert dipendenti
inhibit_rules:
  # Se il DB è down, silenzia gli alert applicazione (sono conseguenze)
  - source_match:
      alertname: "DatabaseDown"
    target_match_re:
      alertname: "APIGateway.*"
    equal: [cluster, namespace]

  # Se il nodo è down, silenzia tutti gli alert dei pod su quel nodo
  - source_match:
      alertname: "NodeDown"
    target_match_re:
      alertname: "Pod.*"
    equal: [node]
```

### On-Call Non Risponde (No ACK)

**Sintomo:** Alert inviato ma nessun ACK entro il timeout di escalation.

**Causa:** On-call non raggiungibile (sonno profondo, problemi di notifica), o escalation policy non configurata correttamente.

**Soluzione:**

```bash
# Verifica che l'escalation policy sia attiva in PagerDuty
# Test manuale dell'escalation:
curl -X POST https://api.pagerduty.com/incidents \
  -H "Authorization: Token token=${PD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "type": "incident",
      "title": "TEST - Verifica escalation policy",
      "service": {"id": "SERVICE_ID", "type": "service_reference"},
      "urgency": "low",
      "body": {"type": "incident_body", "details": "Test escalation - ignorare"}
    }
  }'
```

Verificare anche: notifiche push attive sul telefono, volume non in modalità silenziosa, numero di telefono aggiornato nel profilo PagerDuty/OpsGenie.

### Postmortem Non Produce Miglioramenti

**Sintomo:** I postmortem vengono scritti ma gli stessi incidenti si ripetono.

**Causa:** Action items senza owner/deadline, o action items mai implementati.

**Soluzione strutturale:**

```
1. Ogni action item DEVE avere: owner nominale + deadline specifica
2. Action items P1 entrano nello sprint immediatamente dopo il postmortem
3. Review degli action items aperti in ogni retrospettiva di sprint
4. Metric da tracciare: "% action items completati entro deadline"
5. Se un incidente si ripete: aprire postmortem separato che includa
   lo storico degli action items non completati — rende visibile la ricorrenza
```

### Incidente Dichiarato Risolto ma Sintomi Persistono

**Sintomo:** L'all-clear viene dichiarato ma gli utenti continuano a segnalare problemi.

**Causa:** La metrica di risoluzione (es. error rate) è tornata nella norma, ma non si è verificata la user experience reale. Oppure il fix ha risolto solo parte del problema.

**Soluzione:**

```bash
# Prima di dichiarare all-clear, verificare:
# 1. SLI torna sopra il target
curl -s "${PROM}/api/v1/query" \
  --data-urlencode 'query=sum(rate(http_requests_total{status!~"5.."}[5m]))/sum(rate(http_requests_total[5m]))*100' \
  | jq '.data.result[0].value[1]'
# Atteso: >= 99.9

# 2. Latenza p99 nella norma
curl -s "${PROM}/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))' \
  | jq '.data.result[0].value[1]'
# Atteso: < 0.5s

# 3. Nessun error nel log recente
kubectl logs -l app=api-gateway --since=5m | grep -c "ERROR"
# Atteso: 0 o molto basso

# 4. Test end-to-end manuale del flusso critico
curl -X POST https://api.production.com/v1/checkout \
  -H "Authorization: Bearer ${TEST_TOKEN}" \
  -d '{"items": [{"id": "test-item", "qty": 1}]}'
```

## Relazioni

??? info "SLO, SLA, SLI — Il Contesto di Reliability"
    Un incidente SEV1 di solito implica la violazione di uno o più SLO. Il concetto di severity map direttamente al burn rate dell'error budget: SEV1 = burn rate > 14.4x.

    **Approfondimento completo →** [SLO/SLA/SLI](./slo-sla-sli.md)

??? info "Error Budget — Impatto degli Incidenti"
    Ogni incidente consuma error budget. L'incident management efficace (MTTR basso) minimizza il budget consumato. La policy di budget esaurito spesso scatta dopo un SEV1 grave.

    **Approfondimento completo →** [Error Budget](./error-budget.md)

??? info "Alertmanager — Routing degli Alert all'On-Call"
    Alertmanager è il componente che instrada gli alert verso PagerDuty/OpsGenie, applica le inhibition rules per ridurre l'alert storm e gestisce il silencing durante la manutenzione pianificata.

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

??? info "Prometheus — Metriche per il Triage"
    Durante un incidente, le query PromQL sui SLI (error rate, latenza p99, saturation) sono il primo strumento di diagnosi. Dashboard Grafana con queste metriche devono essere bookmarkate nell'escalation policy.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Grafana — Dashboard per la War Room"
    Le dashboard Grafana sono lo strumento visivo principale durante una war room. Dashboard di servizio ben progettate riducono il MTTD e accelerano il triage.

    **Approfondimento completo →** [Grafana](../tools/grafana.md)

## Riferimenti

- [Google SRE Book — Managing Incidents](https://sre.google/sre-book/managing-incidents/)
- [Google SRE Workbook — Incident Management](https://sre.google/workbook/incident-response/)
- [Google SRE Book — Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- [PagerDuty Incident Response Guide](https://response.pagerduty.com/)
- [OpsGenie Best Practices](https://www.atlassian.com/incident-management)
- [Atlassian Incident Management Handbook](https://www.atlassian.com/incident-management/handbook)
- [The On-Call Handbook — Charity Majors](https://github.com/charitymajors/on-call-handbook)
