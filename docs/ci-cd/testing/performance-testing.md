---
title: "Performance Testing in CI/CD"
slug: performance-testing
category: ci-cd
tags: [performance-testing, load-testing, k6, gatling, stress-testing, ci-cd, slo, latency]
search_keywords: [performance testing, load testing, stress testing, soak testing, spike testing, k6, gatling, locust, jmeter, throughput, latency, p95, p99, percentile, concurrent users, ramp-up, thresholds, baseline, regressione performance, grafana k6 cloud, artillery, ngrinder, wrk, vegeta, pipeline performance gate, non-functional testing, NFR, resilience testing, scalability testing, endurance testing, volume testing, bottleneck, TPS, RPS, requests per second, response time, error rate]
parent: ci-cd/testing/_index
related: [ci-cd/testing/test-strategy, ci-cd/testing/contract-testing, monitoring/sre/slo-sla-sli, monitoring/tools/grafana, monitoring/sre/chaos-engineering]
official_docs: https://k6.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# Performance Testing in CI/CD

## Panoramica

Il performance testing verifica che il sistema risponda entro tempi accettabili sotto carico reale o simulato. A differenza dei test funzionali (che verificano il *cosa*), i performance test verificano il *quanto veloce* e il *fino a quando* — domande che diventano critiche quando un sistema va in produzione con traffico reale.

Integrare il performance testing nel CI/CD pipeline trasforma questi test da attività manuali pre-release (spesso saltate per mancanza di tempo) in gate automatici che bloccano un deploy se le performance regrediscono rispetto alla baseline. Il risultato è che le regressioni vengono scoperte nel PR, non dopo il deploy in produzione.

Lo strumento principale in questo documento è **k6** (Grafana): scritto in Go, scripting in JavaScript/TypeScript, ottimo per CI grazie alla sua natura CLI-first. Come alternativa enterprise viene trattato **Gatling** (JVM), più adatto ad ambienti Java o quando servono report HTML ricchi.

**Quando integrare performance test nel pipeline:**
- API o servizi esposti a traffico esterno con SLO definiti
- Servizi che hanno subito regressioni di performance in passato
- Ogni release introduce modifiche a query database, cache, o logica di aggregazione
- Il servizio ha requisiti di scalabilità verificabili (es. "deve reggere 1000 req/s")

**Quando NON è la scelta giusta (ancora):**
- MVP o prototipi senza SLO definiti — prima definisci i requisiti, poi misurarli
- Servizi interni a basso traffico senza requisiti di latenza
- Prima di avere un ambiente staging isolato — i test su produzione causano danni reali

---

## Concetti Chiave

!!! note "Tipi di Performance Test"
    - **Load test**: simula il carico atteso in condizioni normali. Verifica che il sistema regga il traffico previsto entro i threshold definiti.
    - **Stress test**: aumenta progressivamente il carico fino a identificare il punto di rottura. Risponde a: "quanto regge il sistema prima di degradare?"
    - **Soak test (endurance)**: mantiene un carico moderato per ore/giorni. Individua memory leak, connection pool exhaustion, e degradazione progressiva.
    - **Spike test**: simula picchi improvvisi di traffico (es. Black Friday, lancio campagna). Verifica che il sistema si stabilizzi dopo il picco senza crash permanente.

!!! note "Metriche Fondamentali"
    - **p50 / p95 / p99 latency**: percentile della distribuzione dei tempi di risposta. p95 < 500ms significa che il 95% delle richieste ha risposto in meno di 500ms.
    - **Throughput (req/s, TPS)**: quante richieste al secondo il sistema elabora con successo.
    - **Error rate**: percentuale di richieste che terminano con errore (HTTP 4xx/5xx, timeout, connessione rifiutata).
    - **Concurrent users (VUs)**: numero di utenti virtuali che fanno richieste simultaneamente.

!!! warning "p99 senza p95 è fuorviante"
    Il p99 mostra casi estremi (spesso outlier infrastrutturali). Il p95 è la metrica operativa principale: rappresenta l'esperienza del 95% degli utenti. Guardare solo il p99 porta a ottimizzare casi rari ignorando il bulk del traffico.

!!! warning "Ambienti isolati sono obbligatori"
    Non eseguire mai load test su produzione. Un load test genera traffico artificiale che può degradare il servizio per gli utenti reali, triggerare alert, consumare risorse fatturate, e corrompere dati. L'ambiente staging deve essere rappresentativo della produzione in termini di risorse (CPU, memoria, database tier), non necessariamente in scala 1:1.

---

## Architettura / Come Funziona

### Flusso di un Performance Test in CI/CD

```
PR aperta
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  CI Pipeline (GitHub Actions / GitLab CI)                    │
│                                                             │
│  1. Build & unit test  ──────────────────────────────────►  │
│  2. Deploy su staging  ──────────────────────────────────►  │
│  3. Smoke test (funzionale)  ────────────────────────────►  │
│  4. Performance test (k6)    ────────────────────────────►  │
│     ├── esegui script k6                                    │
│     ├── raccoglie metriche (latency, throughput, errors)    │
│     └── confronta con baseline salvata                      │
│                                                             │
│  5. Gate decision:                                          │
│     ├── thresholds OK + no regressione → ✅ merge consentito│
│     └── threshold fallito → ❌ PR bloccata + report         │
└─────────────────────────────────────────────────────────────┘
```

### Struttura di uno Script k6

Ogni script k6 ha tre componenti principali:

```
┌──────────────────────────────────────────────────────┐
│  options {}           ← configurazione del test       │
│  ├── stages[]         ← profilo di carico (VU nel t)  │
│  └── thresholds {}    ← criteri di successo/fallimento│
│                                                       │
│  setup()              ← eseguito 1 volta all'inizio   │
│  ├── autenticazione                                   │
│  └── preparazione dati                                │
│                                                       │
│  default function()   ← eseguito da ogni VU in loop   │
│  ├── http.get/post/put/delete                         │
│  ├── check() → verifica response                      │
│  └── sleep() → pausa realistica tra richieste         │
│                                                       │
│  teardown()           ← eseguito 1 volta alla fine    │
│  └── pulizia dati di test                             │
└──────────────────────────────────────────────────────┘
```

---

## Configurazione & Pratica

### Script k6 — Load Test Base

```javascript
// tests/performance/load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Metriche custom per questo servizio
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency', true); // true = in millisecondi

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // ramp-up: 0 → 50 VU in 2 minuti
    { duration: '5m', target: 50 },   // steady state: 50 VU per 5 minuti
    { duration: '1m', target: 100 },  // ramp-up a picco: 50 → 100 VU
    { duration: '3m', target: 100 },  // picco: 100 VU per 3 minuti
    { duration: '2m', target: 0 },    // ramp-down: 100 → 0 VU
  ],
  thresholds: {
    // 95% delle richieste deve rispondere in < 500ms
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    // Tasso di errore HTTP < 1%
    http_req_failed: ['rate<0.01'],
    // Metrica custom: latency endpoint specifico
    api_latency: ['p(95)<300'],
  },
};

// Variabili d'ambiente (iniettate dal CI)
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const API_KEY = __ENV.API_KEY || '';

export function setup() {
  // Verifica che il servizio sia raggiungibile prima di iniziare
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`Servizio non raggiungibile: ${res.status}`);
  }
  console.log(`Load test avviato su: ${BASE_URL}`);
}

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  };

  // Scenario 1: GET lista utenti (read-heavy workload)
  const listRes = http.get(`${BASE_URL}/api/users?page=1&limit=20`, { headers });
  const listOk = check(listRes, {
    'users list: status 200': (r) => r.status === 200,
    'users list: body non vuoto': (r) => r.json('data') !== null,
    'users list: latency < 300ms': (r) => r.timings.duration < 300,
  });
  errorRate.add(!listOk);
  apiLatency.add(listRes.timings.duration);

  sleep(1); // pausa realistica tra azioni utente

  // Scenario 2: POST crea ordine (write workload)
  const payload = JSON.stringify({
    userId: Math.floor(Math.random() * 1000) + 1,
    items: [{ productId: 'prod-001', quantity: 2 }],
  });
  const postRes = http.post(`${BASE_URL}/api/orders`, payload, { headers });
  check(postRes, {
    'create order: status 201': (r) => r.status === 201,
    'create order: orderId presente': (r) => r.json('orderId') !== undefined,
  });
  errorRate.add(postRes.status !== 201);

  sleep(2); // wait più lungo dopo un'operazione write
}
```

### Script k6 — Stress Test

```javascript
// tests/performance/stress-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '5m', target: 100 },   // carico normale
    { duration: '5m', target: 200 },   // doppio del normale
    { duration: '5m', target: 500 },   // stress: 5x normale
    { duration: '5m', target: 1000 },  // breaking point
    { duration: '5m', target: 0 },     // recovery — fondamentale!
  ],
  thresholds: {
    // Nello stress test i threshold sono più permissivi
    // l'obiettivo è trovare il breaking point, non fallire
    http_req_duration: ['p(95)<2000'],  // fino a 2s è "ancora vivo"
    http_req_failed: ['rate<0.10'],     // fino al 10% di errori
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
  const res = http.get(`${BASE_URL}/api/products`);
  check(res, {
    'status 200 o 503': (r) => [200, 503].includes(r.status),
  });
  sleep(0.5);
}
```

### Script k6 — Soak Test (Endurance)

```javascript
// tests/performance/soak-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const memoryErrors = new Counter('memory_errors'); // proxy: errori che aumentano nel tempo

export const options = {
  stages: [
    { duration: '5m', target: 50 },    // ramp-up
    { duration: '8h', target: 50 },    // steady state per 8 ore
    { duration: '5m', target: 0 },     // ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
    // Se memory_errors aumenta nel tempo → possibile memory leak
    memory_errors: ['count<100'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
  const res = http.get(`${BASE_URL}/api/session`);
  const ok = check(res, { 'status 200': (r) => r.status === 200 });
  
  // Logghiamo errori che potrebbero indicare resource exhaustion
  if (res.status === 500 || res.status === 503) {
    memoryErrors.add(1);
  }
  
  sleep(1);
}
```

### k6 in GitHub Actions

```yaml
# .github/workflows/performance-test.yml
name: Performance Tests

on:
  # Esegui su PR verso main (leggero, threshold stretti)
  pull_request:
    branches: [main]
  # Esegui nightly su main (completo, con baseline update)
  schedule:
    - cron: '0 2 * * *'  # ogni notte alle 02:00

env:
  BASE_URL: https://staging.example.com
  K6_VERSION: '0.51.0'

jobs:
  performance-test:
    runs-on: ubuntu-latest
    environment: staging  # usa secrets dell'ambiente staging

    steps:
      - uses: actions/checkout@v4

      - name: Run k6 load test
        uses: grafana/k6-action@v0.3.0
        with:
          filename: tests/performance/load-test.js
          flags: >
            --out json=results/k6-results.json
            --out csv=results/k6-metrics.csv
            --summary-trend-stats="min,avg,med,p(90),p(95),p(99),max"
        env:
          BASE_URL: ${{ env.BASE_URL }}
          API_KEY: ${{ secrets.STAGING_API_KEY }}

      # k6 esce con codice 99 se i threshold falliscono
      # GitHub Actions fallisce il job automaticamente — nessun check aggiuntivo necessario

      - name: Upload risultati
        if: always()  # anche se il test fallisce, vogliamo i risultati
        uses: actions/upload-artifact@v4
        with:
          name: k6-results-${{ github.sha }}
          path: results/
          retention-days: 30

      - name: Commenta PR con summary
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            // Leggi il summary prodotto da k6
            const summary = fs.readFileSync('results/k6-summary.txt', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Performance Test Results\n\`\`\`\n${summary}\n\`\`\``
            });
```

### k6 in GitLab CI

```yaml
# .gitlab-ci.yml (estratto stage performance)
performance-test:
  stage: performance
  image: grafana/k6:latest
  variables:
    BASE_URL: "https://staging.example.com"
  script:
    - k6 run
        --out json=results/k6-results.json
        --summary-trend-stats="min,avg,med,p(90),p(95),p(99),max"
        --env BASE_URL=$BASE_URL
        --env API_KEY=$STAGING_API_KEY
        tests/performance/load-test.js
  artifacts:
    when: always
    paths:
      - results/
    expire_in: 30 days
    reports:
      # GitLab legge il report JUnit per mostrare pass/fail inline
      junit: results/k6-junit.xml
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main" && $CI_PIPELINE_SOURCE == "schedule"
```

### Baseline e Rilevamento Regressioni

```bash
#!/bin/bash
# scripts/compare-baseline.sh
# Confronta i risultati correnti con la baseline salvata

RESULTS_FILE="results/k6-results.json"
BASELINE_FILE="baselines/performance-baseline.json"
REGRESSION_THRESHOLD=10  # % di regressione tollerata

if [ ! -f "$BASELINE_FILE" ]; then
  echo "Nessuna baseline trovata. Salvando la run corrente come baseline."
  cp "$RESULTS_FILE" "$BASELINE_FILE"
  exit 0
fi

# Estrai p95 dalla run corrente e dalla baseline
CURRENT_P95=$(jq '.metrics.http_req_duration.values["p(95)"]' "$RESULTS_FILE")
BASELINE_P95=$(jq '.metrics.http_req_duration.values["p(95)"]' "$BASELINE_FILE")

echo "Baseline p95: ${BASELINE_P95}ms"
echo "Current p95: ${CURRENT_P95}ms"

# Calcola la variazione percentuale
DIFF_PCT=$(echo "scale=2; ($CURRENT_P95 - $BASELINE_P95) / $BASELINE_P95 * 100" | bc)
echo "Variazione: ${DIFF_PCT}%"

# Fallisci se la regressione supera la soglia
if (( $(echo "$DIFF_PCT > $REGRESSION_THRESHOLD" | bc -l) )); then
  echo "❌ REGRESSIONE: p95 aumentato del ${DIFF_PCT}% (soglia: ${REGRESSION_THRESHOLD}%)"
  exit 1
else
  echo "✅ Performance OK: variazione entro la soglia (${DIFF_PCT}%)"
  # Aggiorna la baseline se la run è migliore
  if (( $(echo "$DIFF_PCT < 0" | bc -l) )); then
    echo "Baseline aggiornata (miglioramento del performance)"
    cp "$RESULTS_FILE" "$BASELINE_FILE"
  fi
fi
```

```yaml
# GitHub Actions: salva la baseline come artifact persistente
- name: Download baseline (se esiste)
  uses: dawidd6/action-download-artifact@v3
  continue-on-error: true  # prima esecuzione non ha baseline
  with:
    name: performance-baseline
    path: baselines/

- name: Run performance test
  uses: grafana/k6-action@v0.3.0
  with:
    filename: tests/performance/load-test.js
    flags: --out json=results/k6-results.json

- name: Verifica regressione vs baseline
  run: bash scripts/compare-baseline.sh

- name: Salva nuova baseline (solo su main)
  if: github.ref == 'refs/heads/main' && success()
  uses: actions/upload-artifact@v4
  with:
    name: performance-baseline
    path: results/k6-results.json
    overwrite: true
```

### Gatling — Alternativa JVM

Gatling è preferibile quando il team è Java/Scala-oriented o quando servono report HTML dettagliati con grafici interattivi. La DSL è più verbosa ma più potente per scenari complessi.

```scala
// src/gatling/scala/simulations/UserLoadSimulation.scala
package simulations

import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

class UserLoadSimulation extends Simulation {

  val httpProtocol = http
    .baseUrl("https://staging.example.com")
    .acceptHeader("application/json")
    .contentTypeHeader("application/json")
    .header("X-API-Key", System.getenv("API_KEY"))

  // Feeder: dati variabili per ogni utente virtuale
  val userFeeder = csv("data/users.csv").random

  val listUsersScenario = scenario("Browse Users")
    .feed(userFeeder)
    .exec(
      http("GET /api/users")
        .get("/api/users")
        .queryParam("page", 1)
        .queryParam("limit", 20)
        .check(
          status.is(200),
          jsonPath("$.data").exists,
          responseTimeInMillis.lte(500),  // threshold inline
        )
    )
    .pause(1.second, 3.seconds)  // pausa random tra 1 e 3 secondi
    .exec(
      http("GET /api/users/:id")
        .get("/api/users/#{userId}")  // usa il feeder
        .check(status.is(200))
    )

  // Profilo di carico
  setUp(
    listUsersScenario.inject(
      rampUsersPerSec(1).to(50).during(2.minutes),   // ramp-up
      constantUsersPerSec(50).during(5.minutes),      // steady state
      rampUsersPerSec(50).to(0).during(1.minute),     // ramp-down
    )
  )
  .protocols(httpProtocol)
  .assertions(
    global.responseTime.percentile(95).lt(500),       // p95 < 500ms
    global.successfulRequests.percent.gt(99),         // >99% success rate
  )
}
```

```xml
<!-- pom.xml — plugin Gatling per Maven -->
<plugin>
  <groupId>io.gatling</groupId>
  <artifactId>gatling-maven-plugin</artifactId>
  <version>4.9.6</version>
  <configuration>
    <simulationClass>simulations.UserLoadSimulation</simulationClass>
    <resultsFolder>${project.build.directory}/gatling-results</resultsFolder>
    <failOnError>true</failOnError>
  </configuration>
</plugin>
```

```yaml
# GitHub Actions con Gatling
- name: Run Gatling simulation
  run: |
    mvn gatling:test \
      -DAPI_KEY=${{ secrets.STAGING_API_KEY }} \
      -DBASE_URL=https://staging.example.com

- name: Upload Gatling report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: gatling-report
    path: target/gatling-results/
```

### Output e Dashboard con Grafana

k6 può inviare le metriche in real-time a Grafana tramite InfluxDB o Prometheus Remote Write:

```bash
# Output su InfluxDB (Grafana stack locale)
k6 run \
  --out influxdb=http://localhost:8086/k6 \
  tests/performance/load-test.js

# Output su Prometheus Remote Write (Grafana Cloud)
K6_PROMETHEUS_RW_SERVER_URL=https://prometheus-prod.grafana.net/api/prom/push \
K6_PROMETHEUS_RW_USERNAME=your-user-id \
K6_PROMETHEUS_RW_PASSWORD=your-api-key \
k6 run --out experimental-prometheus-rw tests/performance/load-test.js
```

```yaml
# docker-compose per stack locale k6 + InfluxDB + Grafana
version: "3.8"
services:
  influxdb:
    image: influxdb:1.8-alpine
    ports: ["8086:8086"]
    environment:
      INFLUXDB_DB: k6
      INFLUXDB_HTTP_AUTH_ENABLED: "false"

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: "Admin"
    volumes:
      - ./grafana-provisioning:/etc/grafana/provisioning
    depends_on: [influxdb]
```

---

## Best Practices

**Definire i threshold prima di scrivere il test:** i threshold devono derivare dagli SLO del servizio, non essere scelti a posteriori guardando i risultati. Se lo SLO è "p95 < 300ms", il threshold è `p(95)<300`. Non alzare il threshold per far passare il test.

**Warm-up obbligatorio:** i primi secondi di ogni test sono dominati da cold start (JIT compilation, connection pool fill, DNS lookup). Usare sempre uno stage di ramp-up di almeno 1-2 minuti prima del carico steady-state. Ignorare i dati del warm-up nell'analisi.

**Test dati realistici:** uno script che chiama sempre lo stesso endpoint con lo stesso ID porta a cache hit al 100% — un pattern irrealistico. Usare feeder o generator per dati variabili che simulino il comportamento reale degli utenti.

**Isolare gli scenari:** non mescolare scenari con profili di carico molto diversi nello stesso script. Un endpoint di upload file e uno di lettura hanno pattern radicalmente diversi — tenerli separati per capire dove si trova il collo di bottiglia.

!!! tip "Usa percentili, non medie"
    La latenza media è quasi sempre fuorviante: una distribuzione con molte richieste veloci e poche lentissime può avere una media "accettabile" mentre gli utenti sperimentano p99 di 5 secondi. Guardare sempre p50, p95, p99 — mai solo la media.

!!! tip "Regressione automatica vs threshold fissi"
    I threshold fissi (p95 < 500ms) sono necessari ma non sufficienti. Aggiungere il confronto con la baseline per rilevare regressioni anche all'interno dei threshold — se in questa release p95 è passato da 150ms a 450ms, è un segnale da investigare anche se ancora sotto la soglia.

!!! warning "Test da laptop = risultati inutili"
    Eseguire k6 o Gatling dalla propria macchina introduce variabili incontrollabili: latenza di rete variabile, throttling del sistema operativo, interruzioni di altri processi. I test di performance devono girare sempre in ambienti CI con risorse dedicate e rete stabile verso lo staging.

!!! warning "Non interpretare errori HTTP come errori di performance"
    Un'error rate alta può indicare un bug funzionale, non un problema di performance. Se i check falliscono su status code o struttura della response, prima risolvere il problema funzionale, poi interpretare i dati di latenza.

---

## Troubleshooting

**k6 esce con codice 99 ma non capisco quale threshold ha fallito**
: Il summary a fine test elenca esplicitamente i threshold falliti con i valori attuali vs richiesti. Se il summary è tagliato nel log CI, aggiungere `--summary-trend-stats` per includere tutti i percentili, o leggere il file JSON di output con `jq '.metrics | to_entries[] | select(.value.thresholds != null)'`.

**I risultati variano molto tra run diverse**
: Cause comuni: (1) staging non isolato — altri job o test girano in parallelo. (2) Ramp-up troppo breve — il sistema non ha raggiunto lo steady state. (3) Dimensione del test troppo piccola — con poche centinaia di richieste, un outlier sposta significativamente i percentili. Aumentare la durata dello steady state a minimo 5 minuti.

**La latenza è alta solo all'inizio poi si stabilizza**
: È il comportamento atteso durante il warm-up: JVM/Node.js JIT, riempimento del connection pool, cache warming. Soluzione: aggiungere uno stage di ramp-up di 2+ minuti e ignorare i primi dati nell'analisi. Se la latenza alta persiste oltre il warm-up, il problema è strutturale.

**k6 su GitHub Actions fallisce con "too many open files"**
: Con molti VU (500+), k6 apre molte connessioni simultanee. Aggiungere al job: `run: ulimit -n 65536 && k6 run ...`. Su runner self-hosted, configurare `/etc/security/limits.conf`.

**Gatling non genera il report HTML**
: Il report viene generato solo al termine dello script, non durante l'esecuzione. Se il job CI viene interrotto (timeout), il report è incompleto. Aggiungere `if: always()` all'upload dell'artifact per recuperare i risultati parziali.

**Error rate sale durante il load test ma non si vede nei log del servizio**
: L'errore può essere a livello di rete o load balancer prima di raggiungere l'applicazione. Verificare: (1) health check del load balancer — se il servizio supera il connection limit, le richieste vengono rifiutate dal LB. (2) `ulimit` del processo applicativo. (3) metriche del database — connection pool esaurito causa timeout upstream.

---

## Relazioni

??? info "Test Strategy — Piramide dei Test"
    Il performance testing si posiziona fuori dalla piramide classica (unit/integration/E2E) come livello non-funzionale. test-strategy.md definisce quando e come integrarlo nel pipeline.

    **Approfondimento →** [Test Strategy](./test-strategy.md)

??? info "SLO, SLA, SLI — Definire i Threshold"
    I threshold dei performance test devono derivare dagli SLO definiti per il servizio. Un test senza SLO è un test senza obiettivo — prima stabilisci cosa è "abbastanza veloce", poi misuralo.

    **Approfondimento →** [SLO, SLA, SLI](../../monitoring/sre/slo-sla-sli.md)

??? info "Grafana — Dashboard per i Risultati"
    I risultati k6 possono essere inviati a Grafana tramite InfluxDB o Prometheus Remote Write per dashboard real-time durante il test e confronto storico tra run.

    **Approfondimento →** [Grafana](../../monitoring/tools/grafana.md)

??? info "Chaos Engineering — Failure Testing"
    Il performance testing verifica il comportamento sotto carico normale e stress. Il chaos engineering completa il quadro verificando il comportamento sotto failure — le due pratiche sono complementari.

    **Approfondimento →** [Chaos Engineering](../../monitoring/sre/chaos-engineering.md)

---

## Riferimenti

- [k6 Documentation](https://k6.io/docs/) — documentazione ufficiale k6
- [k6 GitHub Action](https://github.com/grafana/k6-action) — action ufficiale Grafana per GitHub Actions
- [Grafana k6 Cloud](https://grafana.com/products/cloud/k6/) — per test distribuiti da multiple location geografiche
- [Gatling Documentation](https://docs.gatling.io/) — documentazione ufficiale Gatling
- [k6 Examples](https://github.com/grafana/k6/tree/master/examples) — script di esempio per scenari comuni
- [Google SRE Book — Chapter 20: Load Testing](https://sre.google/sre-book/load-testing/) — approccio Google al load testing in produzione-like environments
- [Grafana k6 grafana dashboard](https://grafana.com/grafana/dashboards/2587-k6-load-testing-results/) — dashboard Grafana ufficiale per k6 + InfluxDB
