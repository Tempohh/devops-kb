---
title: "Capacity Planning — SRE"
slug: capacity-planning
category: monitoring
tags: [sre, capacity-planning, load-testing, demand-forecasting, scaling, performance, k6, locust, jmeter, headroom]
search_keywords: [capacity planning, pianificazione capacità, demand forecasting, previsione domanda, load testing, test di carico, stress test, k6, locust, jmeter, gatling, headroom, margine di capacità, over-provisioning, under-provisioning, right-sizing, scalabilità, scalability, vertical scaling, horizontal scaling, auto-scaling, HPA, resource limits, resource requests, cpu throttling, memory pressure, traffic spike, peak traffic, traffic forecast, growth planning, saturation, utilizzo risorse, resource utilization, throughput, latency degradation, capacity model, performance baseline, benchmark, VU, virtual users, ramp-up, soak test, spike test, finops, cost vs performance, sre capacity, google sre, load profile]
parent: monitoring/sre/_index
related: [monitoring/sre/slo-sla-sli, monitoring/sre/error-budget, monitoring/tools/prometheus, monitoring/tools/grafana, monitoring/sre/chaos-engineering]
official_docs: https://sre.google/workbook/capacity-planning/
status: complete
difficulty: intermediate
last_updated: 2026-03-26
---

# Capacity Planning — SRE

## Panoramica

Il capacity planning è il processo con cui un team SRE garantisce che i sistemi abbiano risorse sufficienti per sostenere il traffico previsto — con un adeguato margine di sicurezza (headroom) — senza sprecare risorse e budget. Non è solo "comprare più server": è un ciclo continuo di misurazione, previsione, validazione tramite load test e adeguamento proattivo. Si usa prima di eventi di crescita prevedibili (lanci di prodotto, campagne marketing, stagionalità), prima di migrazioni architetturali, e come pratica periodica (trimestrale o semestrale) per tutti i servizi critici. Non si usa per incidenti in corso — in quell'emergenza si scala empiricamente; il capacity planning si fa a mente fredda per prevenire quegli incidenti.

Il ciclo si articola in quattro fasi: **misurare** (baseline attuale), **prevedere** (demand forecasting), **validare** (load testing), **adeguare** (rightsizing, autoscaling, headroom).

## Concetti Chiave

### Headroom e Margini di Sicurezza

L'headroom è la capacità disponibile oltre al traffico attuale. Troppo poco headroom espone a degradazioni sotto picco; troppo headroom brucia budget.

```
Utilizzo corrente: 70% CPU
Picco storico:     85% CPU
Target headroom:   30% sopra picco previsto

→ Target utilizzo a regime: ~65% CPU
→ Soglia di scaling-out: 75% CPU (prima di saturare)
→ Soglia di alert: 80% CPU (warning proattivo)
```

!!! warning "La latenza degrada prima della saturazione completa"
    Un servizio con CPU al 80% può sembrare "funzionante" ma la latenza p99 è già degradata significativamente. Il capacity planning usa le latenze (p50/p95/p99) come metrica primaria, non solo l'utilizzo CPU/memoria.

### Le Quattro Risorse da Pianificare

| Risorsa | Metrica chiave | Segnale di saturazione |
|---------|---------------|----------------------|
| **CPU** | Utilizzo %, throttling | Latenza in aumento, throttled/total > 5% |
| **Memoria** | RSS, utilizzo heap, OOM | OOMKill, GC pressure, swap usage |
| **I/O (disco/rete)** | Throughput MB/s, IOPS, latenza disk | Queue depth > 1, await > soglia |
| **Connessioni** | Pool connections, file descriptors | Connection timeouts, FD exhaustion |

### Demand Forecasting

Il demand forecasting stima il traffico futuro combinando trend storici e input di business:

```
Domanda futura = Domanda attuale × Fattore di crescita × Fattore stagionale × Fattore eventi

Esempio:
  Traffico attuale:    1000 RPS
  Crescita annua:      +40% (storico ultimi 12 mesi)
  Stagionalità Q4:     +30% (picco natalizio)
  Lancio feature:      +20% (stimato dal product team)

  Picco previsto Q4:   1000 × 1.40 × 1.30 × 1.20 ≈ 2184 RPS
  Con headroom 30%:    2184 × 1.30 ≈ 2840 RPS (capacità da garantire)
```

!!! tip "Distingui traffico user-facing e batch"
    Il traffico batch (ETL, analytics, job notturni) non richiede lo stesso headroom del traffico user-facing. Pianifica le due dimensioni separatamente — un job batch può essere throttled senza impatto utente, un'API no.

### Modelli di Scaling

```
Scaling verticale (scale-up):
  Pro: semplice, nessuna modifica architetturale
  Contro: limite fisico, single point of failure, downtime per alcuni provider
  Quando: DB primari, state machine, workload non parallelizzabili

Scaling orizzontale (scale-out):
  Pro: limite teoricamente illimitato, alta disponibilità
  Contro: richiede stateless o state esternalizzato
  Quando: API layer, worker pool, microservizi

Auto-scaling:
  Pro: risponde dinamicamente al carico, ottimizza costi
  Contro: cold start, instabilità se mal configurato (flapping)
  Quando: workload con traffico variabile e prevedibile
```

## Architettura / Come Funziona

### Il Ciclo di Capacity Planning

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ciclo Capacity Planning                        │
│                                                                   │
│  1. BASELINE          2. FORECAST          3. VALIDATE           │
│  ─────────────        ─────────────        ────────────          │
│  Misura utilizzo      Proietta domanda     Load test fino        │
│  attuale di CPU,      futura (trend,       al volume previsto    │
│  memoria, I/O,        stagionalità,        + headroom 30%.       │
│  connessioni.         eventi).             Misura la SLO.        │
│       │                    │                    │                 │
│       └────────────────────┴────────────────────┘                │
│                            │                                      │
│                      4. ADEGUARE                                  │
│                      ──────────                                   │
│                      Rightsizing (se over-prov.),                 │
│                      Scale-out (se under-prov.),                  │
│                      Config autoscaler,                           │
│                      Review soglie alert.                         │
│                            │                                      │
│                      Ciclo successivo in 90 giorni                │
└─────────────────────────────────────────────────────────────────┘
```

### Tipi di Load Test

| Tipo | Scopo | Durata tipica | Quando usarlo |
|------|-------|--------------|---------------|
| **Smoke test** | Verifica che il sistema funzioni sotto carico minimo | 5–15 min | Post-deploy, sanity check |
| **Load test** | Valida comportamento al carico atteso (SLO verification) | 30–60 min | Baseline, capacity review |
| **Stress test** | Trova il breaking point del sistema | Fino al failure | Prima di eventi di crescita |
| **Spike test** | Simula picchi improvvisi (marketing, viral) | 10–20 min con spike | Campagne, lanci |
| **Soak test** | Rileva degradazione nel tempo (memory leak, GC pressure) | 4–24 ore | Post-refactor, nuovi release |

### Architettura k6

k6 esegue script JavaScript con virtual users (VU) che simulano comportamenti reali:

```
┌─────────────────────────────────────────────────────┐
│                    k6 Architecture                   │
│                                                      │
│  ┌──────────┐    ┌──────────────────────────────┐   │
│  │  Script  │    │         k6 Engine            │   │
│  │  (JS)    │───▶│  VU1: scenario A             │   │
│  │          │    │  VU2: scenario A             │──▶│ Target
│  │  options │    │  VU3: scenario B             │   │ System
│  │  stages  │    │  ...                         │   │
│  └──────────┘    └──────────────────────────────┘   │
│                            │                         │
│                     ┌──────▼──────┐                  │
│                     │  Output     │                  │
│                     │  stdout     │                  │
│                     │  InfluxDB   │                  │
│                     │  Grafana    │                  │
│                     │  Cloud      │                  │
│                     └─────────────┘                  │
└─────────────────────────────────────────────────────┘
```

## Configurazione & Pratica

### Load Test con k6 — Template Completo

```javascript
// load-test.js — Template per capacity planning
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Metriche custom
const errorRate = new Rate('errors');
const checkoutDuration = new Trend('checkout_duration');

export const options = {
  // Definizione degli stage (ramp-up → steady state → ramp-down)
  stages: [
    { duration: '5m',  target: 50   },  // Ramp-up: 0 → 50 VU in 5 min
    { duration: '10m', target: 50   },  // Steady state: 50 VU per 10 min
    { duration: '5m',  target: 200  },  // Spike: 50 → 200 VU in 5 min
    { duration: '10m', target: 200  },  // Steady state ad alto carico
    { duration: '5m',  target: 0    },  // Ramp-down
  ],

  // Thresholds — il test FALLISCE se queste soglie vengono violate
  thresholds: {
    http_req_duration:        ['p(95)<500', 'p(99)<1500'], // Latenza SLO
    http_req_failed:          ['rate<0.01'],                // < 1% errori
    errors:                   ['rate<0.01'],
    checkout_duration:        ['p(99)<2000'],
  },
};

const BASE_URL = __ENV.TARGET_URL || 'https://api.example.com';

export default function () {
  // --- Scenario 1: Browse prodotti ---
  const listRes = http.get(`${BASE_URL}/api/products`, {
    tags: { scenario: 'browse' },
  });
  check(listRes, {
    'products list 200': (r) => r.status === 200,
    'products latency OK': (r) => r.timings.duration < 300,
  }) || errorRate.add(1);

  sleep(1);

  // --- Scenario 2: Checkout (path critico) ---
  const payload = JSON.stringify({
    product_id: `prod-${Math.floor(Math.random() * 100)}`,
    quantity: 1,
  });
  const checkoutRes = http.post(
    `${BASE_URL}/api/checkout`,
    payload,
    { headers: { 'Content-Type': 'application/json' }, tags: { scenario: 'checkout' } }
  );
  checkoutDuration.add(checkoutRes.timings.duration);
  check(checkoutRes, {
    'checkout 200 or 201': (r) => [200, 201].includes(r.status),
    'checkout latency OK': (r) => r.timings.duration < 1000,
  }) || errorRate.add(1);

  sleep(Math.random() * 2 + 1); // Think time variabile
}
```

### Esecuzione k6 e Output

```bash
# Esecuzione locale con output standard
k6 run load-test.js

# Con variabili d'ambiente e output su InfluxDB
k6 run \
  --env TARGET_URL=https://api.staging.example.com \
  --out influxdb=http://localhost:8086/k6 \
  load-test.js

# Stress test: continua a scalare fino al breaking point
k6 run --vus 10 --stage "10m:10,10m:100,10m:500,10m:1000" load-test.js

# Soak test: 4 ore a carico costante
k6 run --vus 50 --duration 4h load-test.js

# Output riassuntivo (esempio)
# ✓ products list 200 ............... 10000/10000 (100%)
# ✓ checkout 200 or 201 .............. 9987/10000 (99.87%)
# http_req_duration p(95)=312ms p(99)=891ms
# http_req_failed rate=0.13%
```

### Load Test con Locust — Template Python

```python
# locustfile.py — Template Locust per capacity planning
from locust import HttpUser, task, between, constant_throughput
from locust import events
import random

class APIUser(HttpUser):
    # Simula utente con 1-3 secondi di think time
    wait_time = between(1, 3)

    def on_start(self):
        """Setup per ogni VU: login e recupero token."""
        resp = self.client.post("/api/auth/login", json={
            "username": f"user_{random.randint(1, 1000)}",
            "password": "test123",
        })
        if resp.status_code == 200:
            self.token = resp.json().get("token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(5)  # Peso 5: scenario più frequente
    def browse_products(self):
        with self.client.get(
            "/api/products",
            name="/api/products [browse]",
            catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status: {resp.status_code}")
            elif resp.elapsed.total_seconds() > 0.5:
                resp.failure(f"Too slow: {resp.elapsed.total_seconds():.2f}s")

    @task(2)  # Peso 2: scenario meno frequente
    def checkout(self):
        with self.client.post(
            "/api/checkout",
            json={"product_id": f"prod-{random.randint(1, 100)}", "quantity": 1},
            name="/api/checkout",
            catch_response=True,
        ) as resp:
            if resp.status_code not in [200, 201]:
                resp.failure(f"Checkout failed: {resp.status_code}")

    @task(1)
    def search(self):
        query = random.choice(["laptop", "phone", "tablet", "headphones"])
        self.client.get(f"/api/search?q={query}", name="/api/search")
```

```bash
# Avvio Locust (web UI su :8089)
locust -f locustfile.py --host=https://api.staging.example.com

# Headless (CI/CD): 100 utenti, spawn rate 10/s, per 10 minuti
locust -f locustfile.py \
  --host=https://api.staging.example.com \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 10m \
  --html report.html \
  --csv results
```

### Analisi della Capacità con Prometheus

```promql
# --- Utilizzo CPU medio per pod (ultimi 30 min) ---
avg by (pod) (
  rate(container_cpu_usage_seconds_total{namespace="production"}[30m])
) / avg by (pod) (
  kube_pod_container_resource_requests{resource="cpu", namespace="production"}
)

# --- Trend crescita RPS (slope degli ultimi 7 giorni) ---
# Stima quanto crescerà il traffico in base al trend
deriv(
  sum(rate(http_requests_total{job="api"}[1h]))[7d:1h]
)

# --- Proiezione utilizzo CPU tra 30 giorni ---
predict_linear(
  avg(container_cpu_usage_seconds_total{namespace="production"})[7d:1h],
  30 * 24 * 3600   -- 30 giorni in secondi
)

# --- Headroom disponibile per namespace ---
1 - (
  sum(container_cpu_usage_seconds_total{namespace="production"}) by (namespace)
  /
  sum(kube_pod_container_resource_requests{resource="cpu", namespace="production"}) by (namespace)
)

# --- Saturazione connessioni DB ---
sum(pg_stat_activity_count{datname="mydb"})
/
sum(pg_settings_max_connections{datname="mydb"})
```

### Rightsizing Kubernetes — Resource Requests e Limits

```yaml
# Esempio: configurazione rightsized dopo capacity planning
# Prima del rightsizing: requests sovrastimate del 300%
# Dopo: basate su p95 dell'utilizzo reale + 30% headroom

apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api
          resources:
            requests:
              # p95 CPU usage storico: 150m → +30% headroom = 200m
              cpu: "200m"
              # p95 memoria storica: 256Mi → +30% headroom = 330Mi (arrotondato)
              memory: "330Mi"
            limits:
              # Limit CPU: 2x request (permette burst temporanei)
              cpu: "400m"
              # Limit memoria: uguale a request (OOM prevedibile invece di throttling)
              memory: "330Mi"
---
# HPA — Horizontal Pod Autoscaler configurato su utilizzo CPU
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          # Scale-out quando CPU > 65% (non aspettare la saturazione)
          averageUtilization: 65
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      # Scala velocemente in caso di spike
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 4        # Max 4 pod aggiunti per volta
          periodSeconds: 60
    scaleDown:
      # Scala giù lentamente per evitare flapping
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10       # Max 10% pod rimossi ogni 5 minuti
          periodSeconds: 300
```

## Best Practices

### Costruire un Capacity Model

Un capacity model formale risponde a tre domande: quante risorse servono ora, quante ne serviranno fra N mesi, e qual è il punto di rottura del sistema.

```
Capacity Model — Template

Servizio: api-service
Data: 2026-03-26
Owner: team-platform

BASELINE (misurata):
  RPS medi:           800 RPS
  RPS picco storico:  2100 RPS (Black Friday 2025)
  CPU p95 a 800 RPS:  180m per pod
  Memoria p95:        290Mi per pod
  Repliche attive:    5 pod
  Latenza p99 attuale: 210ms

FORECAST (next 6 mesi):
  Crescita mensile:   +8% (storico 12 mesi)
  RPS previsti a 6m:  800 × 1.08^6 ≈ 1270 RPS
  Evento Q4:          +150% su picco → ~3175 RPS massimi

VALIDAZIONE (load test):
  Test eseguito a:    3500 RPS (picco + 10% headroom)
  Risultato:          SLO rispettato fino a 3200 RPS
  Breaking point:     3600 RPS (latenza p99 > 2s)
  Headroom effettivo: ~11% oltre il picco previsto

ADEGUAMENTO:
  Azione: Aumentare maxReplicas HPA da 10 a 20
  Azione: Pre-scale manuale in anticipo per Black Friday
  Azione: Aggiungere read replica DB per query analytics
  Review: Settembre 2026 (90 giorni prima del Q4)
```

!!! tip "Automatizza il pre-scaling per eventi noti"
    Per campagne marketing e lanci pianificati, usa `kubectl scale` o KEDA ScaledObject con schedule per pre-scalare prima del picco. Aspettare che l'HPA reagisca al traffico reale introduce latenza e potenziali degradazioni nella fase di ramp-up.

### Anti-pattern da Evitare

```
❌ Over-provisioning permanente
   Symptom: CPU sempre < 20%, memoria sempre < 30%
   Impatto: Costi 3-5x superiori al necessario
   Fix: Rightsizing periodico (ogni 90 giorni)

❌ Under-provisioning con alert tardivi
   Symptom: Alert CPU > 90% prima dello scaling
   Impatto: Degradazione SLO durante il ramp-up dell'autoscaler
   Fix: Soglie di scaling al 65-70%, non all'80-90%

❌ Load test in produzione senza isolare il traffico
   Symptom: Test contamina metriche reali, potenziale danno agli utenti
   Fix: Usare staging dedicato o header di canary routing

❌ Capacity planning solo annuale
   Symptom: Sorprese a ogni lancio o campagna
   Fix: Review trimestrale per servizi critici, semestrale per il resto

❌ Pianificare CPU senza pianificare le dipendenze
   Symptom: API scala perfettamente ma il DB satura
   Fix: Includere DB connections, cache hit rate, downstream services nel model
```

### Integrazione con Error Budget

Il capacity planning e l'error budget si parlano: un sistema sotto-provisioned esaurisce l'error budget durante i picchi. Il target di headroom deve garantire che, anche sotto stress, il sistema rimanga entro i valori di latenza dello SLO.

```
Regola pratica:
  Load test fino al 2x del traffico previsto → se la SLO regge, il sistema ha headroom sufficiente.
  Se la SLO viene violata sotto 1.5x il traffico previsto → troppo vicini al limite.
  Obiettivo: sistema che regge il picco previsto + 30% senza violare SLO.
```

## Troubleshooting

### Il Sistema Scala ma la Latenza Rimane Alta

**Sintomo:** L'HPA aggiunge pod, il CPU si abbassa, ma p99 rimane elevata.

**Causa più probabile:** Bottleneck non sulla CPU ma su una dipendenza downstream: DB connections, cache miss, downstream API lenta.

```bash
# 1. Verificare connection pool saturo (PostgreSQL)
kubectl exec -it postgres-pod -- psql -U admin -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
# Se active ≈ max_connections → connection pool esaurito

# 2. Verificare cache hit rate (Redis)
kubectl exec -it redis-pod -- redis-cli info stats | grep -E "keyspace_hits|keyspace_misses"
# Se miss rate > 20% → cache non efficace, molte query passano al DB

# 3. Verificare latenza downstream con tracing (Jaeger/Tempo)
# Cercare span con durata anomala nelle chiamate HTTP upstream
```

**Soluzione:** Aumentare il pool di connessioni DB, aggiungere una read replica per query non critiche, o ottimizzare le query ad alto costo.

### CPU Throttling Elevato Nonostante Utilizzo Basso

**Sintomo:** `container_cpu_throttled_seconds_total` alto, ma utilizzo CPU medio basso (< 50%).

**Causa:** Il CPU limit è troppo basso rispetto al CPU request. Il throttling avviene nei burst, non nel medio periodo. L'utilizzo medio può essere basso perché il container è throttled durante i picchi.

```bash
# Verificare il throttling ratio
kubectl top pods -n production
# Confrontare con il throttling in Prometheus:
# rate(container_cpu_throttled_seconds_total[5m]) / rate(container_cpu_usage_seconds_total[5m])

# Se throttling ratio > 20%: aumentare il CPU limit (non il request)
# Regola: limit = 2-4x request per workload con burst brevi
```

```yaml
# Prima (throttling elevato)
resources:
  requests: { cpu: "200m" }
  limits:   { cpu: "200m" }   # Limit = Request → nessun burst permesso

# Dopo (burst consentito)
resources:
  requests: { cpu: "200m" }
  limits:   { cpu: "800m" }   # 4x request → burst fino a 800m permesso
```

### HPA Non Scala Durante un Picco

**Sintomo:** Traffico aumenta, CPU supera la soglia, ma i pod non vengono aggiunti.

**Causa possibile 1:** `stabilizationWindowSeconds` troppo alto — l'HPA aspetta prima di scalare.

**Causa possibile 2:** `maxReplicas` già raggiunto. Verificare con `kubectl get hpa -n production`.

**Causa possibile 3:** Metriche non disponibili — metrics-server non funzionante.

```bash
# Diagnostica HPA
kubectl describe hpa api-service-hpa -n production
# Cercare nella sezione Events: "DesiredReplicas" e messaggi di errore

# Verificare metrics-server
kubectl top pods -n production
# Se il comando fallisce, metrics-server non risponde

# Verificare il motivo del mancato scaling
kubectl get events -n production --sort-by='.lastTimestamp' | grep -i hpa
```

### Previsione Errata — Traffico Reale Molto Diverso dal Forecast

**Sintomo:** Capacity plan basato su +8% mensile, ma il traffico è cresciuto del +40% in un mese dopo un lancio non comunicato.

**Causa:** Il demand forecast non includeva input dal product team su feature launch, campagne, integrazioni con partner.

**Soluzione strutturale:** Implementare un processo formale di capacity review che includa il product manager e i team di marketing — non solo i dati storici.

```bash
# Alert proattivo: traffico cresciuto > 20% rispetto alla settimana scorsa
# PromQL per alert di crescita anomala del traffico
(
  sum(rate(http_requests_total[1h]))
  /
  sum(rate(http_requests_total[1h] offset 7d))
) > 1.20
# Se questo alert scatta → avviare un capacity review di emergenza
```

## Relazioni

??? info "SLO/SLA/SLI — La Base degli Obiettivi"
    Il capacity planning lavora per garantire che i sistemi rispettino gli SLO anche sotto carico. La latenza p99 e la disponibilità del load test devono rimanere entro i target SLO definiti.

    **Approfondimento completo →** [SLO/SLA/SLI](./slo-sla-sli.md)

??? info "Error Budget — Capacità e Reliability"
    Un sistema sotto-provisioned consuma error budget durante i picchi. Il capacity planning è il meccanismo proattivo per mantenere il budget sempre disponibile.

    **Approfondimento completo →** [Error Budget](./error-budget.md)

??? info "Prometheus — Metriche per il Capacity Model"
    Le query PromQL di utilizzo CPU, memoria, throughput e le funzioni `predict_linear` e `deriv` sono i mattoni fondamentali del capacity model quantitativo.

    **Approfondimento completo →** [Prometheus](../tools/prometheus.md)

??? info "Chaos Engineering — Validazione della Resilienza"
    Il load testing valida la capacità sotto carico normale e di picco. Il chaos engineering valida la resilienza in condizioni di failure parziale. Sono pratiche complementari.

    **Approfondimento completo →** [Chaos Engineering](./chaos-engineering.md)

## Riferimenti

- [Google SRE Workbook — Capacity Planning](https://sre.google/workbook/capacity-planning/)
- [k6 — Documentazione ufficiale e script examples](https://k6.io/docs/)
- [Locust — Documentazione ufficiale](https://docs.locust.io/)
- [Kubernetes HPA — Documentazione ufficiale](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [KEDA — Kubernetes Event-driven Autoscaling](https://keda.sh/)
- [Grafana k6 Cloud](https://grafana.com/products/cloud/k6/)
- [Netflix: Capacity Engineering at Scale](https://netflixtechblog.com/tag/capacity)
