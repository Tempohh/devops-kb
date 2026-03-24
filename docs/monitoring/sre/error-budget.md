---
title: "Error Budget — Meccanismo Operativo"
slug: error-budget
category: monitoring
tags: [sre, error-budget, burn-rate, reliability, toil, deploy-freeze, slo]
search_keywords: [error budget, budget di errore, burn rate, tasso di consumo, deploy freeze, reliability work, toil, error budget policy, sre, error budget exhaustion, esaurimento budget, finestra di errore, fast burn, slow burn, alert multiwindow]
parent: monitoring/sre/_index
related: [monitoring/sre/slo-sla-sli, monitoring/tools/prometheus, monitoring/alerting/alertmanager, monitoring/tools/grafana]
official_docs: https://sre.google/workbook/error-budget-policy/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Error Budget — Meccanismo Operativo

## Panoramica

L'error budget è la quantità di inaffidabilità che un servizio può permettersi prima di violare il suo SLO. È il complemento matematico del target di affidabilità: se lo SLO è 99.9%, l'error budget mensile è 0.1% del tempo totale — circa 43 minuti. L'error budget trasforma uno SLO da obiettivo astratto in strumento decisionale concreto: quando il budget è disponibile, il team può fare deploy frequenti e sperimentare; quando si esaurisce, la priorità assoluta diventa la reliability. Senza error budget, le discussioni tra dev (che vogliono rilasciare spesso) e ops (che vogliono stabilità) si risolvono con politica aziendale invece che con dati oggettivi.

## Concetti Chiave

### Calcolo del Budget

```
Error budget = 100% - SLO target

Con SLO = 99.9%:
  Budget mensile (30d)  = 0.1% × 30 × 24 × 60 min = 43.2 minuti
  Budget settimanale    = 0.1% × 7 × 24 × 60 min  = 10.1 minuti
  Budget annuale        = 0.1% × 365 × 24 × 60 min = 526 minuti (8.77 ore)
```

!!! note "Budget è finestre di tempo, non eventi"
    L'error budget si esprime in percentuale di "eventi cattivi" (richieste fallite, minuti di downtime, ecc.), non in ore di outage assolute. Un servizio con SLO 99.9% su availability può ricevere 1 errore ogni 1000 richieste per tutto il mese senza violare l'SLO.

### Burn Rate

Il **burn rate** misura a che velocità si consuma l'error budget rispetto alla velocità "normale".

```
Burn rate = 1   → il budget si esaurisce esattamente alla fine della finestra
Burn rate = 10  → il budget si esaurisce in 1/10 della finestra
             con finestra 30d → esaurimento in 3 giorni
Burn rate = 720 → il budget si esaurisce in 1/720 della finestra (30d)
             = esaurimento in 1 ora
```

**Formula burn rate:**
```
burn_rate = (error_rate_corrente) / (1 - SLO_target)

Con SLO 99.9% (error_rate_normale = 0.001):
  Se error_rate = 0.01  → burn_rate = 0.01 / 0.001 = 10
  Se error_rate = 0.001 → burn_rate = 0.001 / 0.001 = 1 (neutro)
```

### Budget Rimanente vs. Budget Consumato

```
Budget consumato (%) =
  (eventi_cattivi_osservati) / (eventi_totali × (1 - SLO_target)) × 100

Budget rimanente (%) = 100% - Budget consumato (%)
```

!!! warning "Budget negativo"
    Un budget rimanente negativo indica che lo SLO è già stato violato nella finestra corrente. Non significa blocco operativo automatico, ma l'error budget policy dovrebbe scattare.

## Architettura / Come Funziona

### Error Budget Policy

L'**error budget policy** è il documento che stabilisce le azioni da intraprendere in base allo stato del budget. Deve essere concordato tra engineering, prodotto e leadership prima che l'emergenza si verifichi.

```
┌──────────────────────────────────────────────────────────┐
│                  Error Budget Policy                      │
│                                                           │
│  Budget > 50%   →  Tutto OK. Deploy liberi.              │
│                    Sperimentazione consentita.            │
│                                                           │
│  Budget 25-50%  →  Attenzione aumentata.                 │
│                    Review pre-deploy più rigorosa.        │
│                                                           │
│  Budget 10-25%  →  Solo deploy critici/hotfix.           │
│                    Incident review obbligatoria.          │
│                    Prioritizzare reliability nel backlog. │
│                                                           │
│  Budget < 10%   →  Freeze deploy non critici.            │
│                    Reliability work obbligatorio.         │
│                    Escalation al management.              │
│                                                           │
│  Budget esaurito →  Stop deploy di feature.              │
│                    Post-mortem obbligatorio.              │
│                    Piano di recupero concordato.          │
└──────────────────────────────────────────────────────────┘
```

### Finestre Temporali e Alerting

L'alerting basato su burn rate usa finestre multiple per bilanciare **velocità di rilevamento** e **false positive rate**.

```
┌──────────────────────────────────────────────────────────┐
│          Strategia Multiwindow Multi-Burnrate             │
│                                                           │
│  Severity   Burn rate  Finestra breve  Finestra lunga    │
│  ─────────  ─────────  ─────────────  ──────────────     │
│  CRITICAL      14.4x      5m              1h             │
│  (≈2h budget)                                            │
│                                                           │
│  HIGH           6x        30m             6h             │
│  (≈1d budget)                                            │
│                                                           │
│  MEDIUM         3x        2h              1d             │
│  (≈3d budget)                                            │
│                                                           │
│  LOW             1x       6h              3d             │
│  (consumo normale ma costante)                           │
└──────────────────────────────────────────────────────────┘
```

La **doppia finestra** è necessaria: solo la finestra breve genera troppi falsi positivi (spike transitori); solo la finestra lunga è troppo lenta per situazioni critiche.

## Configurazione & Pratica

### PromQL: Calcolo Error Budget

```promql
# --- SLI corrente (30 giorni rolling) ---
sum(rate(http_requests_total{status!~"5.."}[30d]))
/
sum(rate(http_requests_total[30d]))

# --- Budget rimanente in percentuale ---
# Con SLO = 99.9%
(
  (
    sum(rate(http_requests_total{status!~"5.."}[30d]))
    /
    sum(rate(http_requests_total[30d]))
  ) - 0.999
) / (1 - 0.999) * 100
# Positivo = budget rimanente, negativo = violazione SLO

# --- Burn rate corrente (finestra 1h) ---
(
  1 - (
    sum(rate(http_requests_total{status!~"5.."}[1h]))
    /
    sum(rate(http_requests_total[1h]))
  )
) / (1 - 0.999)

# --- Budget consumato oggi ---
(
  sum(increase(http_requests_total{status=~"5.."}[1d]))
  /
  (sum(increase(http_requests_total[30d])) * 0.001)
) * 100
```

### Recording Rules Consigliate

```yaml
# rules/slo-recording.yml
groups:
  - name: slo_recording
    interval: 30s
    rules:
      # Error rate su finestre multiple
      - record: job:error_rate:5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m]))

      - record: job:error_rate:30m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[30m]))
          / sum(rate(http_requests_total[30m]))

      - record: job:error_rate:1h
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[1h]))
          / sum(rate(http_requests_total[1h]))

      - record: job:error_rate:6h
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[6h]))
          / sum(rate(http_requests_total[6h]))

      - record: job:error_rate:1d
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[1d]))
          / sum(rate(http_requests_total[1d]))

      # Budget rimanente (SLO 99.9%)
      - record: job:error_budget_remaining:30d
        expr: |
          (
            (sum(rate(http_requests_total{status!~"5.."}[30d]))
             / sum(rate(http_requests_total[30d])))
            - 0.999
          ) / (1 - 0.999) * 100
```

### Alert Rules Multi-Burnrate

```yaml
# rules/slo-alerts.yml
groups:
  - name: slo_burn_rate
    rules:
      # CRITICAL: budget esaurito in ~2h
      - alert: ErrorBudgetBurnCritical
        expr: |
          (job:error_rate:5m > (14.4 * 0.001))
          and
          (job:error_rate:1h > (14.4 * 0.001))
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SLO critico: budget esaurito in ~2h"
          runbook: "https://runbooks.internal/slo-burn-critical"
          description: |
            Burn rate {{ $value | printf "%.1f" }}x su {{ $labels.job }}.
            Budget mensile esaurito in ~{{ printf "%.0f" (div 720.0 $value) }} ore.

      # HIGH: budget esaurito in ~1 giorno
      - alert: ErrorBudgetBurnHigh
        expr: |
          (job:error_rate:30m > (6 * 0.001))
          and
          (job:error_rate:6h > (6 * 0.001))
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "SLO warning: budget esaurito in ~1 giorno"

      # MEDIUM: budget esaurito in ~3 giorni
      - alert: ErrorBudgetBurnMedium
        expr: |
          (job:error_rate:2h > (3 * 0.001))
          and
          (job:error_rate:1d > (3 * 0.001))
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "SLO info: burn rate sostenuto, budget in esaurimento"

      # TICKET: budget consumato > 10% in questo ciclo mensile
      - alert: ErrorBudgetLow
        expr: job:error_budget_remaining:30d < 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Error budget < 10% — attivare reliability work"
```

### Error Budget Policy — Template

```markdown
## Error Budget Policy: [Nome Servizio]

**SLO:** 99.9% availability (30d rolling)
**Budget mensile:** 43.2 minuti
**Owner:** [Team]
**Ultimo aggiornamento:** [Data]
**Approvato da:** [Engineering Lead] + [Product Manager]

### Livelli di azione

| Budget rimanente | Azione richiesta |
|-----------------|-----------------|
| > 50% | Nessuna restrizione |
| 25-50% | Review pre-deploy rafforzata; nessun deploy di rischio alto senza approvazione senior |
| 10-25% | Solo hotfix e miglioramenti reliability; stop feature non critiche |
| < 10% | Freeze deploy; almeno 50% della sprint capacity su reliability |
| Esaurito | Stop completo deploy feature; post-mortem entro 48h; piano recupero |

### Esclusioni dal budget
- Manutenzione pianificata con > 72h preavviso (comunicata agli utenti)
- Incident causati documentati da outage fornitore (AWS/GCP/Azure con status page)
- Downtime approvato per migrazione pianificata

### Review
- Monthly review: ogni 1° del mese
- Post-mortem: dopo ogni alert ErrorBudgetBurnCritical
- Annual review: rivalutare target SLO se budget sempre > 80% o sempre < 20%
```

### Dashboard Grafana: Error Budget

```json
{
  "title": "Error Budget Dashboard",
  "panels": [
    {
      "title": "Budget Rimanente (%)",
      "type": "gauge",
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              { "color": "red",    "value": 0  },
              { "color": "orange", "value": 10 },
              { "color": "yellow", "value": 25 },
              { "color": "green",  "value": 50 }
            ]
          },
          "min": -50,
          "max": 100,
          "unit": "percent"
        }
      },
      "targets": [{
        "expr": "job:error_budget_remaining:30d"
      }]
    },
    {
      "title": "Burn Rate (1h)",
      "type": "stat",
      "targets": [{
        "expr": "job:error_rate:1h / 0.001"
      }]
    },
    {
      "title": "Budget Consumato nel Tempo",
      "type": "timeseries",
      "targets": [{
        "expr": "100 - job:error_budget_remaining:30d",
        "legendFormat": "budget consumato %"
      }]
    }
  ]
}
```

## Best Practices

### Toil vs. Reliability Work

Il concetto di **toil** (Google SRE) è direttamente collegato all'error budget: quando il budget si esaurisce troppo spesso, la causa è spesso lavoro operativo manuale non eliminato.

```
Toil = lavoro operativo manuale, ripetitivo, automatizzabile
       che scala con il traffico e non produce miglioramento duraturo

Esempi:
  - Riavvio manuale di pod che crashano
  - Rollback manuali di deploy falliti
  - Pulizia manuale di log/storage
  - Risposta ad alert non actionable

Reliability work = automazione, eliminazione toil, riduzione failure modes
```

!!! tip "Regola del 50%"
    Google SRE raccomanda che gli SRE non spendano più del 50% del tempo in toil. Se il toil supera questa soglia, i team non hanno capacità di fare reliability work e il budget continuerà a esaurirsi.

### Error Budget Review Mensile

Struttura di una review efficace:

1. **Stato budget**: quanto è rimasto? Trend rispetto ai mesi precedenti?
2. **Incident analysis**: quali eventi hanno consumato più budget?
3. **Root cause pattern**: ci sono failure modes ricorrenti?
4. **Azioni intraprese**: reliability work fatto nel mese
5. **Azioni pianificate**: affrontare i failure modes ricorrenti
6. **Rivalutazione SLO**: il target è ancora appropriato?

### Quando Rivalutare il Target SLO

```
Budget sempre > 80%:
  → Il target è troppo permissivo
  → Aumentare il target per creare incentivi a migliorare
  → O abbassare per riflettere le aspettative reali degli utenti

Budget sempre < 20%:
  → Il target è troppo ambizioso per il sistema attuale
  → Investire in reliability o abbassare temporaneamente il target
  → Non mantenere un SLO che non si può rispettare: erode la fiducia

Varianza alta (a volte 90%, a volte 5%):
  → Il servizio è fragile e non predicibile
  → Focus su riduzione variance prima di alzare il target
```

### Error Budget Sharing

In architetture a microservizi, un singolo servizio può avere dipendenze che consumano il suo budget. Tracking della **dipendenza budget**:

```promql
# Budget consumato per causa (se si ha il tag upstream_service)
sum by (upstream_service) (
  rate(http_client_requests_total{status=~"5.."}[30d])
) / sum(rate(http_client_requests_total[30d]))
```

## Troubleshooting

### Alert Frequenti per Spike Transitori

**Problema:** Alert `ErrorBudgetBurnCritical` che si risolve in pochi minuti — falso positivo.

**Causa:** La finestra breve (5m) è troppo sensibile a picchi isolati.

**Soluzione:** Verificare che la doppia finestra sia configurata correttamente. L'alert deve richiedere burn rate elevato SIA sulla finestra breve che su quella lunga. In alternativa, aumentare il `for:` a 5-10m.

```promql
# Corretto: doppia finestra
(job:error_rate:5m > threshold) AND (job:error_rate:1h > threshold)

# Sbagliato: solo finestra breve (troppi falsi positivi)
job:error_rate:5m > threshold
```

### Budget Sempre Esaurito Nonostante Pochi Incident

**Causa probabile:** SLI mal calibrato — include traffico non user-facing (health check, monitoring scrape).

```promql
# Verificare: quanto traffico è health check?
sum(rate(http_requests_total{path="/health"}[5m]))
/
sum(rate(http_requests_total[5m]))
* 100
# Se > 5%: escludere esplicitamente dal calcolo SLI
```

### Burn Rate PromQL Restituisce NaN

**Causa:** Nessuna metrica nell'intervallo specificato (servizio down, scrape failure).

```promql
# Protezione con fallback
(
  sum(rate(http_requests_total{status!~"5.."}[1h])) or vector(0)
)
/
(
  sum(rate(http_requests_total[1h])) or vector(1)
)
```

### Policy Non Rispettata dal Team

**Problema:** La policy esiste ma i deploy avvengono anche con budget esaurito.

**Soluzione strutturale:** Integrare il controllo del budget nel CI/CD pipeline come gate automatico.

```bash
# Esempio gate nel CI/CD (bash + curl Prometheus)
BUDGET=$(curl -s "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode 'query=job:error_budget_remaining:30d' \
  | jq -r '.data.result[0].value[1]')

if (( $(echo "$BUDGET < 10" | bc -l) )); then
  echo "ERROR: Error budget < 10% (${BUDGET}%). Deploy bloccato."
  exit 1
fi
echo "Error budget: ${BUDGET}%. Deploy autorizzato."
```

## Relazioni

??? info "SLO, SLA, SLI — La Base Teorica"
    SLI è la metrica, SLO è il target. L'error budget è derivato dall'SLO e reso operativo dai meccanismi descritti in questo file.

    **Approfondimento completo →** [SLO/SLA/SLI](./slo-sla-sli.md)

??? info "Prometheus — Calcolo del Budget"
    Le recording rules e le alert rules dell'error budget vivono in Prometheus. PromQL è il linguaggio per calcolare SLI e burn rate.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Alertmanager — Routing degli Alert"
    Gli alert `ErrorBudgetBurnCritical` e `ErrorBudgetBurnHigh` vengono routati da Alertmanager verso PagerDuty (on-call) o Slack.

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

??? info "Grafana — Dashboard Error Budget"
    Grafana ospita i dashboard di error budget tracking. Il gauge del budget rimanente è un componente standard delle SRE dashboard.

    **Approfondimento completo →** [Grafana](../tools/grafana.md)

## Riferimenti

- [Google SRE Workbook — Error Budget Policy](https://sre.google/workbook/error-budget-policy/)
- [Google SRE Book — Embracing Risk](https://sre.google/sre-book/embracing-risk/)
- [Alerting on SLOs — Multiwindow Multi-Burnrate](https://sre.google/workbook/alerting-on-slos/)
- [sloth — SLO generator per Prometheus](https://github.com/slok/sloth)
- [pyrra — Kubernetes SLO tool con error budget tracking](https://github.com/pyrra-dev/pyrra)
- [OpenSLO — Standard aperto per definire SLO](https://github.com/OpenSLO/OpenSLO)
