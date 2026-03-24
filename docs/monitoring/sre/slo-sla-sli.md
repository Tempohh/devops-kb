---
title: "SLO, SLA, SLI — Reliability Targets"
slug: slo-sla-sli
category: monitoring
tags: [sre, slo, sla, sli, reliability, error-budget, google-sre]
search_keywords: [slo, sla, sli, service level objective, service level agreement, service level indicator, error budget, reliability, affidabilità, uptime, disponibilità, sre, google sre, toil, burn rate, target di disponibilità]
parent: monitoring/sre/_index
related: [monitoring/sre/error-budget, monitoring/tools/prometheus, monitoring/alerting/alertmanager, monitoring/fondamentali/opentelemetry]
official_docs: https://sre.google/sre-book/service-level-objectives/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# SLO, SLA, SLI — Reliability Targets

## Panoramica

SLI, SLO e SLA sono i tre livelli di un framework per misurare e gestire la reliability di un servizio, introdotto dalla cultura SRE di Google. Definiscono in modo rigoroso cosa significa "il servizio funziona" e quanto spesso può non funzionare senza conseguenze. Senza questi strumenti, le discussioni sulla reliability si basano su intuizioni soggettive ("il servizio è lento") invece che su dati oggettivi ("il p99 di latenza ha superato 500ms per il 2% delle richieste nell'ultima settimana"). La triade SLI/SLO/SLA trasforma la reliability da concetto vago a metrica gestibile, con un budget di errore che bilancia la velocità di rilascio con la stabilità.

## Concetti Chiave

### SLI — Service Level Indicator

Un **SLI** è una metrica quantitativa che misura un aspetto del comportamento del servizio dal punto di vista dell'utente.

!!! note "Definizione"
    Un SLI è una **percentuale di "eventi buoni" rispetto al totale degli eventi**.
    Formula: `SLI = (eventi_buoni / eventi_totali) * 100`

**SLI comuni:**

| Tipo di servizio | SLI tipici |
|------------------|------------|
| **API/HTTP** | % richieste con latenza < 500ms; % richieste con status 2xx |
| **Storage** | % operazioni di scrittura andate a buon fine; % dati leggibili |
| **Pipeline batch** | % job completati con successo; % job completati nel tempo target |
| **Streaming** | % messaggi processati correttamente; latenza end-to-end |

```promql
# SLI: % richieste con successo negli ultimi 30 giorni
sum(rate(http_requests_total{status!~"5.."}[30d]))
/
sum(rate(http_requests_total[30d]))
* 100
```

### SLO — Service Level Objective

Un **SLO** è il **target** che vogliamo raggiungere per un SLI. È un obiettivo interno, non un obbligo contrattuale.

!!! note "Definizione"
    `SLO = SLI >= target`
    Esempio: "Il 99.9% delle richieste HTTP deve avere una latenza < 200ms, misurata su una finestra di 30 giorni rolling."

**Struttura di uno SLO:**
- **Metrica (SLI)**: cosa misuriamo
- **Target**: la soglia (es. 99.9%)
- **Finestra temporale**: periodo di misurazione (28-30 giorni rolling)
- **Owner**: chi è responsabile

```yaml
# Esempio di SLO documentato
slo:
  name: "API Gateway Availability"
  description: "Percentuale di richieste all'API Gateway che ricevono una risposta non-5xx"
  sli:
    metric: http_requests_total
    good_events: "status!~'5..'"
    total_events: "tutte le richieste"
  target: 99.9%
  window: 30d_rolling
  owner: team-platform
```

### SLA — Service Level Agreement

Un **SLA** è un accordo **contrattuale** con gli utenti/clienti, generalmente con penali in caso di violazione. È sempre più permissivo dell'SLO interno, per creare un buffer di sicurezza.

| Livello | Audience | Conseguenze violazione | Tipica soglia |
|---------|----------|----------------------|---------------|
| **SLI** | Ingegneri | Nessuna (è solo una misura) | N/A |
| **SLO** | Team interno | Blocco deploy, incident review | 99.9% |
| **SLA** | Clienti/contratti | Penali, crediti, churning | 99.5% |

!!! tip "Regola pratica"
    L'SLA deve essere sempre inferiore all'SLO. Se l'SLO è 99.9%, l'SLA potrebbe essere 99.5%. Questo buffer garantisce che non si violi il contratto ogni volta che si sfora leggermente l'obiettivo interno.

## Architettura / Come Funziona

### Calcolo degli SLO

La finestra temporale è fondamentale. Le due modalità principali:

**1. Rolling window (30 giorni):**
```
Oggi - 30 giorni ──────────────────▶ Oggi
                  [misura continua]
```
Più sensibile ai problemi recenti. Standard nella pratica SRE.

**2. Calendar window (mese solare):**
```
1° del mese ────────────────────── Fine mese
```
Più semplice per i report, ma meno reattiva.

### Error Budget

**Error budget** = 100% - SLO target

```
SLO = 99.9%  →  Error budget = 0.1%
                              = 43.8 minuti/mese (su finestra 30d)
                              = 8.7 ore/anno
```

L'error budget è il meccanismo che bilancia reliability e velocità:
- **Budget disponibile** → il team può procedere con deploy e sperimentazione
- **Budget esaurito** → si sospendono i deploy non critici, si prioritizza la reliability

```
┌─────────────────────────────────────────────────────┐
│               Decision Framework                     │
│                                                       │
│  Error budget > 50%  ──▶  Velocità di deploy OK     │
│  Error budget 10-50% ──▶  Cautela, monitorare       │
│  Error budget < 10%  ──▶  Solo hotfix, no features  │
│  Error budget = 0%   ──▶  Freeze deploy,            │
│                           reliability work obbligato │
└─────────────────────────────────────────────────────┘
```

## Configurazione & Pratica

### Implementare SLO con Prometheus

```promql
# --- Calcolo SLI availability (30 giorni rolling) ---
# Metrica: % richieste non-5xx
(
  sum(increase(http_requests_total{status!~"5.."}[30d]))
  /
  sum(increase(http_requests_total[30d]))
) * 100

# --- Error budget rimanente ---
# Con SLO = 99.9%
(
  (
    sum(increase(http_requests_total{status!~"5.."}[30d]))
    /
    sum(increase(http_requests_total[30d]))
  ) - 0.999
) / (1 - 0.999) * 100
# Positivo = budget rimanente, negativo = budget esaurito
```

### Burn Rate Alerts

Il burn rate misura quanto velocemente si consuma l'error budget. È la metrica più utile per l'alerting SLO-based.

```
Burn rate = 1  →  il budget viene consumato alla velocità "normale"
                  (esaurimento esatto al termine della finestra)
Burn rate = 10 →  budget esaurito in 1/10 del tempo della finestra
                  (con finestra 30d: esaurimento in 3 giorni)
```

```promql
# Burn rate nelle ultime 1h
(
  1 - (
    sum(rate(http_requests_total{status!~"5.."}[1h]))
    /
    sum(rate(http_requests_total[1h]))
  )
) / (1 - 0.999)

# Alert: burn rate critico (esaurimento in 2h)
# Burn rate > 14.4 su finestra 5m + 1h
```

### Alerting Multiwindow Multiburnrate (Google SRE)

La strategia di alerting raccomandata da Google usa due finestre e due burn rate per bilanciare velocità di rilevamento e false positives.

```yaml
# rules/slo-alerts.yml
groups:
  - name: slo_alerts
    rules:
      # P0: Consumo rapido — esaurimento in ~2h
      - alert: SLOBurnRateCritical
        expr: |
          (
            error_rate:5m > (14.4 * 0.001)
            and
            error_rate:1h > (14.4 * 0.001)
          )
        for: 2m
        labels:
          severity: critical
          slo: api-availability
        annotations:
          summary: "SLO: burn rate critico su {{ $labels.service }}"
          description: "Burn rate {{ $value | humanizePercentage }} — budget esaurito in ~2h"

      # P1: Consumo elevato — esaurimento in ~1 giorno
      - alert: SLOBurnRateHigh
        expr: |
          (
            error_rate:30m > (6 * 0.001)
            and
            error_rate:6h > (6 * 0.001)
          )
        for: 15m
        labels:
          severity: warning
          slo: api-availability

      # P2: Consumo moderato — esaurimento in ~3 giorni
      - alert: SLOBurnRateMedium
        expr: |
          (
            error_rate:2h > (3 * 0.001)
            and
            error_rate:1d > (3 * 0.001)
          )
        for: 1h
        labels:
          severity: info
          slo: api-availability
```

### SLO Document Template

Ogni SLO dovrebbe avere un documento scritto concordato tra engineering e prodotto.

```markdown
## SLO: API Gateway Availability

**Servizio:** API Gateway (api.example.com)
**Owner:** Team Platform
**Review:** Trimestrale

### SLI
Percentuale di richieste HTTP che ricevono una risposta con status code != 5xx.

### Target
| Tier | SLO | SLA cliente |
|------|-----|-------------|
| Production | 99.9% (30d rolling) | 99.5% |
| Staging | 99.0% | N/A |

### Error Budget
- Budget mensile: 43.8 minuti di downtime
- Policy di esaurimento: blocco deploy non critici, post-mortem obbligatorio

### Esclusioni
- Manutenzione pianificata con > 48h di preavviso
- Incident causati da dependency tier-1 (AWS outage documentato)

### Come si misura
```promql
sum(rate(http_requests_total{status!~"5.."}[30d]))
/
sum(rate(http_requests_total[30d]))
```

### Contatti
- On-call: #on-call-platform
- Escalation: @platform-lead
```

## Best Practices

### Scegliere i Giusti SLI

- **Misura ciò che l'utente percepisce**, non metriche infrastrutturali
- CPU al 90% non è un SLI diretto → la latenza che ne consegue lo è
- Iniziare con **3-5 SLO per servizio**, non di più
- Preferire **disponibilità** e **latenza** come primi SLO

!!! warning "Evitare SLO al 100%"
    Un SLO al 100% è impossibile da rispettare e crea incentivi sbagliati (paura di fare deploy). Il costo di raggiungere il "quinto 9" (99.999%) è sproporzionato. La reliability ha un costo, e il costo marginale cresce esponenzialmente.

### Tabella Uptime di Riferimento

| SLO | Downtime/anno | Downtime/mese | Downtime/settimana |
|-----|--------------|---------------|-------------------|
| 99% | 3.65 giorni | 7.3 ore | 1.68 ore |
| 99.5% | 1.83 giorni | 3.65 ore | 50.4 min |
| 99.9% | 8.77 ore | 43.8 min | 10.1 min |
| 99.95% | 4.38 ore | 21.9 min | 5 min |
| 99.99% | 52.6 min | 4.38 min | 1 min |
| 99.999% | 5.26 min | 26.3 sec | 6 sec |

### Review degli SLO

- **Review mensile**: confrontare SLO target vs SLO reale, trend error budget
- **Review trimestrale**: rivalutare se il target è ancora appropriato
- **Post-mortem**: dopo ogni burn rate alert critico

## Troubleshooting

### SLO Troppo Basso (budget sempre pieno)

Il target è troppo permissivo. Aumentare il target SLO per creare incentivi a migliorare.

### SLO Costantemente Violato

- Il target è troppo alto → abbassarlo temporaneamente mentre si lavora alla reliability
- Oppure: il servizio ha problemi strutturali → prioritizzare reliability work nel backlog

### Calcolo SLI Inaccurato

Verificare che la query PromQL escluda correttamente:
- Health check interni (non user-facing)
- Richieste di monitoring (Prometheus stesso)
- Traffico di test/canary

```promql
# Escludere health check e monitoring
http_requests_total{
  status!~"5..",
  path!="/health",
  path!="/metrics",
  source!="monitoring"
}
```

## Relazioni

??? info "Error Budget — Meccanismo Operativo"
    L'error budget è il concetto pratico che rende gli SLO actionable. Burn rate, policy, freeze deploy.

    **Approfondimento completo →** [Error Budget](./error-budget.md)

??? info "Prometheus — Strumento di Misurazione"
    Prometheus è il tool standard per misurare gli SLI e calcolare l'error budget con PromQL.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Alertmanager — Routing degli Alert SLO"
    Gli alert di burn rate vengono routati tramite Alertmanager verso Slack, PagerDuty o altri canali.

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

## Riferimenti

- [Google SRE Book — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Multiwindow, Multi-Burn-Rate Alerts](https://sre.google/workbook/alerting-on-slos/)
- [sloth — SLO generator per Prometheus](https://github.com/slok/sloth)
- [pyrra — SLO tool per Kubernetes](https://github.com/pyrra-dev/pyrra)
