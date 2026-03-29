---
title: "Enterprise SDLC per Microservizi"
slug: enterprise-sdlc
category: dev
tags: [sdlc, agile, scrum, tech-lead, adr, feature-flags, release-management, definition-of-done, technical-debt]
search_keywords: [enterprise sdlc, software development lifecycle, ciclo sviluppo software, agile enterprise, scrum microservizi, sprint planning, backlog tecnico, debito tecnico, technical debt, quadrante fowler, tech debt quadrant, definition of done, DoD, quality gate, coverage soglia, SAST, static analysis, feature flags, feature toggle, LaunchDarkly, Unleash, Flagsmith, trunk based, release management, semantic versioning, semver, changelog automatico, hotfix process, hotfix, ADR, architectural decision record, decision record, Tech Lead, responsabilità tech lead, RFC, request for comments, coupling budget, accoppiamento, team topology, SDLC enterprise, process engineering, ingegneria del processo, ingegneria software enterprise, software engineering process, agile at scale, SAFe, team of teams]
parent: dev/processi/_index
related: [dev/processi/developer-workflow]
official_docs: https://martinfowler.com/articles/is-quality-worth-cost.html
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Enterprise SDLC per Microservizi

## Panoramica

L'SDLC (Software Development Lifecycle) enterprise per microservizi è il sistema di processi, cerimonie e artefatti che regola come un team strutturato porta una feature dall'idea al deployment in produzione con qualità e velocità sostenibili. Non è Scrum "di libro" applicato meccanicamente: è l'insieme di accordi espliciti su come si decide cosa costruire, cosa significa "fatto", come si gestisce il debito tecnico, e chi ha quale responsabilità.

In un team enterprise — tipicamente 5+ team che collaborano su decine di microservizi — i problemi non sono tecnici ma di coordinamento e visibilità. Le domande critiche diventano: come si pianifica il lavoro tecnico accanto a quello funzionale? Come si garantisce che ogni microservizio che entra in produzione rispetti gli standard minimi? Come si prendono decisioni architetturali che sopravvivono al turnover del team?

Questo documento copre i pilastri del processo: **sprint planning con gestione del debt tecnico**, **Definition of Done con quality gate**, **feature flags come strumento SDLC**, **release management**, **ADR** come memoria architetturale, e il ruolo del **Tech Lead** come abilitatore del processo.

**Quando non serve questo livello di processo:** team singolo (<= 3 persone) su un progetto senza vincoli di compliance o coordinamento con altri team. In quel caso, la cerimonia supera il beneficio.

---

## Concetti Chiave

!!! note "SDLC vs Agile"
    SDLC è il framework più ampio che include tutte le fasi: pianificazione, design, implementazione, testing, deployment e manutenzione. Agile (Scrum, Kanban) è una metodologia di *esecuzione* di alcune fasi. Un team può essere Agile senza avere un SDLC maturo, e viceversa. L'obiettivo enterprise è avere entrambi: iterazioni brevi (Agile) dentro un processo che garantisce qualità e tracciabilità (SDLC).

!!! note "Debito Tecnico — Quadrante di Fowler"
    Martin Fowler distingue 4 tipi di debito tecnico in un quadrante 2x2:

    | | Deliberato | Accidentale |
    |---|---|---|
    | **Imprudente** | "Non abbiamo tempo per il design" | "Cos'è la layered architecture?" |
    | **Prudente** | "Dobbiamo consegnare ora, rifattorizziamo dopo" | "Ora sappiamo come avremmo dovuto farlo" |

    Solo il debito *deliberato+prudente* è accettabile come scelta consapevole. Il debito accidentale non è mai una scelta: è ignoranza o fretta non gestita. L'SDLC sano crea spazio per riconoscere, quantificare e ridurre il debito nelle sue forme.

!!! warning "La trappola del velocity washing"
    Sprint completati al 100% non significano valore consegnato se il backlog tecnico viene sistematicamente posticipato. Un team che non riserva capacità per il debito tecnico accelera verso il momento in cui il debito stesso diventa il lavoro principale — senza che nessuno se ne sia accorto durante il percorso.

!!! tip "Il principio della finestra rotta"
    Un codebase in cui il debito tecnico visibile non viene mai risolto segnala al team che gli standard non vengono applicati. Questo normalizza il debito nuovo. Risolvere sistematicamente piccoli problemi (zero broken window policy) è più efficace che grandi refactoring occasionali.

---

## Sprint Planning con Backlog Tecnico

### La Struttura del Backlog

In un team enterprise su microservizi, il product backlog deve contenere **due flussi espliciti**: il lavoro funzionale (user story, feature, spike) e il lavoro tecnico (debt tecnico, refactoring, upgrade dipendenze, miglioramenti infrastruttura).

```yaml
# Struttura standard di una Epic tecnica su Jira/Linear
epic:
  type: technical
  title: "Upgrade dipendenze Q2-2026"
  description: |
    Aggiornamento di tutte le dipendenze con CVE critici o major version lag > 6 mesi.
    Non porta valore utente diretto ma riduce rischio sicurezza e facilita futuri upgrade.
  stories:
    - "Upgrade Spring Boot 3.2 → 3.3 per order-service"
    - "Upgrade PostgreSQL driver 42.5 → 42.7"
    - "Sostituire log4j con logback in inventory-service"
  acceptance_criteria:
    - "Pipeline CI verde dopo l'upgrade"
    - "Nessuna regressione nei test di integrazione"
    - "Nessun CVE critico/alto nelle dipendenze (OWASP check)"
  effort_estimate: "3 story points"
  tech_debt_category: "imprudent-accidental"  # per tracking nel quadrante Fowler
```

```yaml
# Template user story con tech debt implicito esplicitato
story:
  title: "Come utente voglio pagare con PayPal"
  acceptance_criteria:
    - "Pagamento PayPal completo entro 30s"
    - "Fallback su carta se PayPal non risponde entro 5s"
  tech_debt_tasks:
    # Debito tecnico che emerge durante l'implementazione
    - "Refactoring PaymentGatewayFactory: aggiungere PayPal espone un accoppiamento nascosto"
    - "TODO: estrarre PaymentStrategy come interfaccia separata (scope: sprint successivo)"
  technical_notes: |
    L'aggiunta di PayPal richiede una modifica a PaymentGatewayFactory che attualmente
    assume solo due gateway. Registriamo questo come debito deliberato/prudente da
    affrontare nel prossimo sprint.
```

### Capacità Riservata per il Debito Tecnico

Un principio operativo consolidato: **riservare il 20% della capacità dello sprint per lavoro tecnico non funzionale**. Questa non è una regola fissa — varia tra il 15% (codebase giovane) e il 30% (codebase legacy con debito accumulato) — ma deve essere un accordo esplicito tra team e product manager.

```markdown
## Accordo di Team — Capacità Sprint

| Tipo di Lavoro | Percentuale Capacità | Motivazione |
|---|---|---|
| Feature funzionali (user story) | ~65% | Valore diretto agli utenti |
| Debito tecnico (backlog tecnico) | ~20% | Sostenibilità a lungo termine |
| Support / bug produzione | ~10% | Buffer per imprevisti |
| Cerimonie e overhead | ~5% | Sprint planning, retrospettiva, etc. |

**Regola:** se il debito tecnico supera il 30% del backlog, il team deve comunicare
al management il rischio. Non è una negoziazione: è un fatto tecnico.
```

### Classificazione e Tracking del Debito

```python
# Esempio: label convention per Jira per categorizzare il debito Fowler
TECH_DEBT_LABELS = {
    "td-deliberate-prudent":    "Scelta consapevole, da pagare presto",
    "td-deliberate-imprudent":  "Scorciatoia senza piano — da eliminare",
    "td-accidental-prudent":    "Scoperto dopo, ora lo sappiamo fare meglio",
    "td-accidental-imprudent":  "Bug architetturale non intenzionale",
}

# Dashboard KPI debito tecnico (esempio con query JQL Jira)
JQL_OPEN_TECH_DEBT = """
project = "ORDER-SERVICE"
AND issuetype = Story
AND labels = "technical-debt"
AND status != Done
ORDER BY priority DESC
"""

# Metrica da esporre: Tech Debt Ratio = ore stimate debito / ore totali backlog
# Target: < 20% → sano, 20-40% → attenzione, > 40% → emergenza
```

---

## Definition of Done per Microservizi

La Definition of Done (DoD) è il contratto esplicito che definisce quando una user story o un task possono essere considerati completi. Per microservizi in ambiente enterprise, la DoD deve includere **quality gate automatici** integrati nella pipeline CI/CD — non checklist manuali soggette a dimenticanze.

### Quality Gate Completo

```yaml
# .github/workflows/quality-gate.yaml
# Quality gate obbligatorio — ogni PR deve superare tutti questi check prima del merge

name: Quality Gate

on:
  pull_request:
    branches: [main]

jobs:
  # ── 1. Code Coverage ─────────────────────────────────────────────────────
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests with coverage
        run: ./mvnw test jacoco:report
      - name: Check coverage threshold
        run: |
          COVERAGE=$(python3 -c "
          import xml.etree.ElementTree as ET
          tree = ET.parse('target/site/jacoco/jacoco.xml')
          root = tree.getroot()
          counters = {c.get('type'): c for c in root.iter('counter') if c.get('type') in ['LINE', 'BRANCH']}
          missed = int(counters['LINE'].get('missed'))
          covered = int(counters['LINE'].get('covered'))
          print(f'{covered / (missed + covered) * 100:.1f}')
          ")
          echo "Coverage: ${COVERAGE}%"
          python3 -c "assert float('${COVERAGE}') >= 80, f'Coverage {COVERAGE}% < 80% threshold'"

  # ── 2. SAST — Static Analysis Security Testing ───────────────────────────
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Semgrep SAST
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/owasp-top-ten
            p/java
            p/secrets
      - name: Run SonarQube analysis
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
        run: |
          ./mvnw sonar:sonar \
            -Dsonar.projectKey=${{ github.repository }} \
            -Dsonar.host.url=${{ vars.SONAR_URL }} \
            -Dsonar.qualitygate.wait=true   # fallisce se quality gate SonarQube non passa

  # ── 3. Dependency Vulnerability Scan ─────────────────────────────────────
  dependency-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: OWASP Dependency Check
        uses: dependency-check/Dependency-Check_Action@main
        with:
          project: ${{ github.repository }}
          path: '.'
          format: 'JSON'
          args: '--failOnCVSS 7'   # fallisce su CVE con CVSS >= 7 (High/Critical)

  # ── 4. Performance Baseline ───────────────────────────────────────────────
  performance-baseline:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v4
      - name: Run performance tests
        run: |
          ./mvnw test -Dgroups="performance" -Dtest.performance.baseline=true
      - name: Assert response time baseline
        run: |
          # Fallisce se p99 > 500ms per endpoint critici
          python3 scripts/check-performance-baseline.py \
            --report target/performance-results.json \
            --p99-threshold 500

  # ── 5. Health Probe Validation ────────────────────────────────────────────
  health-probe-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify health endpoints exist and respond
        run: |
          # Avvia il servizio in background e verifica le probe
          docker build -t service-test .
          docker run -d --name service -p 8080:8080 service-test
          sleep 10
          # Liveness probe
          curl -f http://localhost:8080/actuator/health/liveness || exit 1
          # Readiness probe
          curl -f http://localhost:8080/actuator/health/readiness || exit 1
          # Startup probe (se il servizio impiega > 30s ad avviarsi)
          curl -f http://localhost:8080/actuator/health || exit 1
          docker stop service
```

### DoD Checklist — Runbook Obbligatorio

Ogni microservizio che entra in produzione per la prima volta, o che aggiunge funzionalità operative rilevanti, deve avere un **runbook** aggiornato:

```markdown
# Runbook — Order Service

## Informazioni Servizio
- **Repository:** github.com/org/order-service
- **Owner:** team-payments
- **On-call rotation:** PagerDuty - https://org.pagerduty.com/services/ORDER
- **Dashboard:** Grafana - https://grafana.internal/d/order-service
- **Logs:** Loki - https://grafana.internal/explore?query=order-service

## Health Checks
- **Liveness:** GET /actuator/health/liveness → 200 = processo vivo
- **Readiness:** GET /actuator/health/readiness → 200 = pronto a ricevere traffico
- **Metriche:** GET /actuator/prometheus

## Dipendenze Critiche
| Servizio | Tipo | Timeout configurato | Comportamento in caso di errore |
|---|---|---|---|
| PostgreSQL | Sincrono | 5s | Fail fast, 503 all'utente |
| payment-gateway | Sincrono | 10s | Retry 3x, poi fallback |
| order-events (Kafka) | Asincrono | N/A | Buffer, retry con backoff |

## Procedure Operative

### Riavvio Graceful
```bash
# Kubernetes
kubectl rollout restart deployment/order-service -n payments
kubectl rollout status deployment/order-service -n payments --timeout=120s
```

### Rollback
```bash
# Rollback alla versione precedente
kubectl rollout undo deployment/order-service -n payments
# Verifica
kubectl rollout status deployment/order-service -n payments
```

### Scale Out di Emergenza
```bash
# In caso di picco improvviso
kubectl scale deployment/order-service -n payments --replicas=10
```

## Scenari di Incident Comuni

### Ordini non processati (queue lag Kafka)
- **Sintomo:** metrica `kafka.consumer.lag{group=order-processor}` > 1000
- **Causa probabile:** rallentamento DB o payment-gateway
- **Azione:** verificare latency DB e payment-gateway, scale se necessario

### Errori 503 a raffica
- **Sintomo:** alert "order-service 5xx rate > 1%"
- **Causa probabile:** readiness probe fallisce (DB non raggiungibile)
- **Azione:** `kubectl describe pod -l app=order-service -n payments`, controllare events
```

### DoD Minima per uno Story Point

```markdown
## Definition of Done — Accordo di Team

Una story è **Done** quando:

### Codice
- [ ] Implementazione completa del requisito
- [ ] Code review approvata da almeno 1 reviewer (CODEOWNERS per aree critiche: 2)
- [ ] Nessun TODO nel codice senza ticket associato

### Qualità Automatica (pipeline verde)
- [ ] Coverage >= 80% sulle righe modificate
- [ ] SAST green (nessun finding High/Critical)
- [ ] Dependency check: nessun CVE con CVSS >= 7 nelle dipendenze nuove
- [ ] Nessuna regressione performance > 20% vs baseline

### Operabilità
- [ ] Health probes aggiornate se aggiunto nuovo stato operativo
- [ ] Log informativi per i nuovi flow (niente PII, niente secrets)
- [ ] Metriche Prometheus esposte per le nuove funzionalità rilevanti
- [ ] Feature flag configurato se la feature non è safe-to-deploy immediatamente

### Documentazione
- [ ] Runbook aggiornato se cambia il comportamento operativo
- [ ] ADR creato se la story ha introdotto una decisione architetturale
- [ ] API spec aggiornata (OpenAPI/AsyncAPI) se l'interfaccia è cambiata
```

---

## Feature Flags nell'SDLC

### Il Ruolo dei Feature Flag nel Processo

I feature flag non sono solo uno strumento tecnico: sono un componente del processo SDLC che permette di **separare il deployment dal release**. Questo cambia fondamentalmente come si pianifica e si esegue il lavoro:

- Si può fare **continuous deployment** (deploy su main ad ogni merge) senza esporre feature incomplete
- Si può fare **testing in produzione** su un sottoinsieme di utenti reali prima del rollout completo
- Si può fare **rollback immediato** di una feature senza redeployment
- Si può gestire la **dipendenza tra team**: team A deploya il codice, team B controlla quando la feature è visibile

### LaunchDarkly, Unleash, Flagsmith — Confronto

```yaml
# Confronto strumenti feature flag

LaunchDarkly:
  tipo: SaaS managed
  pro:
    - UI potente, targeting avanzato per segmenti utenti
    - SDK per 30+ linguaggi, alta affidabilità (SLA 99.99%)
    - Funzionalità enterprise: approvals, audit log, SSO
    - Experiments A/B integrati
  contro:
    - Costo elevato (enterprise pricing)
    - Dipendenza da vendor esterno
    - Latenza valutazione flag (anche se SDK fa caching locale)
  quando: team > 20 persone, compliance richiede audit trail, budget disponibile

Unleash:
  tipo: Open source, self-hosted (cloud opzionale)
  pro:
    - Self-hosted: nessun dato utente esce dall'infrastruttura
    - Costo: gratuito per il tier open source
    - SDK per Java, Node, Go, Python, Ruby, .NET
    - Flexible strategy: rollout graduale, userId, IP, hostname
  contro:
    - Richiede gestione infrastruttura (PostgreSQL + UI container)
    - Funzionalità enterprise (SSO, audit) a pagamento
    - UI meno ricca di LaunchDarkly
  quando: compliance richiede data residency, team vuole controllo completo, costo è vincolo

Flagsmith:
  tipo: Open source + SaaS
  pro:
    - Simile a Unleash ma con feature di remote config (non solo bool)
    - SDK client-side per mobile/frontend
    - Self-hosted o cloud, pricing più accessibile di LaunchDarkly
  contro:
    - Community più piccola di Unleash
    - Meno integrazioni enterprise out-of-the-box
  quando: serve remote config oltre ai flag booleani, o focus mobile/frontend
```

### Integrazione Feature Flag nel SDLC e Trunk-Based Development

```java
// Pattern standard per integrare feature flags nel codice
// Regole:
// 1. Ogni flag ha un nome esplicito nel codice + in Unleash/LaunchDarkly
// 2. Ogni flag ha una data di scadenza nel commento (per tech debt tracking)
// 3. Il codice "sotto flag" deve essere testabile indipendentemente

@Service
public class CheckoutService {

    private final FeatureFlags flags;
    private final LegacyPricingEngine legacyPricing;
    private final NewPricingEngine newPricing;

    // TODO(2026-06-01): rimuovere flag DYNAMIC_PRICING dopo rollout completo
    // Ticket: https://jira.org/PROJ-1234
    private static final String FLAG_DYNAMIC_PRICING = "dynamic-pricing-v2";

    public CheckoutResult checkout(Cart cart, User user) {
        Price price;

        if (flags.isEnabled(FLAG_DYNAMIC_PRICING, user.getId())) {
            // Nuovo motore: attivo in rollout graduale
            price = newPricing.calculate(cart, user);
        } else {
            // Legacy: default per tutti gli altri utenti
            price = legacyPricing.calculate(cart);
        }

        return processCheckout(cart, price);
    }
}
```

```yaml
# unleash-flags.yaml — file di riferimento flags con metadati SDLC
# Tenuto nel repository per tracciabilità

flags:
  dynamic-pricing-v2:
    description: "Nuovo motore pricing con sconti dinamici per segmento"
    owner: "team-pricing"
    created: "2026-02-01"
    expires: "2026-06-01"         # data prevista per cleanup
    type: "release"               # release | experiment | ops | permission
    rollout_strategy: "gradual"   # percentuale crescente
    rollout_current: 25           # 25% degli utenti ora
    rollout_target: 100
    environments:
      dev: enabled
      staging: enabled
      production: 25%

  order-service-v2-api:
    description: "Nuova versione API ordini (breaking change in /v2)"
    owner: "team-orders"
    created: "2026-03-01"
    expires: "2026-07-01"
    type: "release"
    rollout_strategy: "userIds"   # rollout per lista utenti specifici (beta)
```

```bash
# Script per trovare feature flag scaduti nel codebase
# Da eseguire in CI come check settimanale

#!/bin/bash
# check-expired-flags.sh

TODAY=$(date +%Y-%m-%d)
EXPIRED=()

while IFS= read -r line; do
  if [[ $line =~ TODO\(([0-9]{4}-[0-9]{2}-[0-9]{2})\) ]]; then
    EXPIRY="${BASH_REMATCH[1]}"
    if [[ "$EXPIRY" < "$TODAY" ]]; then
      EXPIRED+=("$line")
    fi
  fi
done < <(grep -r "TODO(" src/ --include="*.java" --include="*.go" --include="*.py")

if [ ${#EXPIRED[@]} -gt 0 ]; then
  echo "❌ Feature flags scaduti trovati:"
  printf '%s\n' "${EXPIRED[@]}"
  exit 1
fi

echo "✅ Nessun feature flag scaduto"
```

---

## Release Management

### Semantic Versioning nel Contesto Enterprise

```bash
# Semantic Versioning (SemVer 2.0): MAJOR.MINOR.PATCH[-prerelease][+build]
#
# MAJOR: breaking change nell'API pubblica (REST, eventi Kafka, gRPC)
# MINOR: nuova funzionalità backward-compatible
# PATCH: bugfix backward-compatible
#
# Regole per microservizi:
# - I microservizi interni senza API pubblica possono usare semver "per convenzione"
# - I microservizi con API consumer esterni (altri team, clienti) DEVONO rispettare semver strict
# - Gli eventi Kafka/AsyncAPI sono "API" e richiedono semver per gli schema

# Esempi changelog automatico con conventional-commits → semantic-release
git log --oneline | head -20
# feat(pricing): add dynamic discount engine               → 1.2.0
# fix(checkout): handle null cart in edge case             → 1.1.1
# feat!: remove deprecated /v1/orders endpoint            → 2.0.0
# chore: update Spring Boot to 3.3.1                      → nessun bump
# feat(auth): add OAuth2 scope validation                 → 1.2.0
```

```json
// .releaserc.json — semantic-release configurazione enterprise completa
{
  "branches": [
    "main",
    { "name": "release/+([0-9])?(.+([0-9]))", "channel": "release-${name.replace(/^release\\//, '')}" },
    { "name": "beta", "prerelease": true }
  ],
  "plugins": [
    "@semantic-release/commit-analyzer",
    ["@semantic-release/release-notes-generator", {
      "preset": "conventionalcommits",
      "presetConfig": {
        "types": [
          { "type": "feat",     "section": "Features" },
          { "type": "fix",      "section": "Bug Fixes" },
          { "type": "perf",     "section": "Performance Improvements" },
          { "type": "revert",   "section": "Reverts" },
          { "type": "security", "section": "Security Fixes" }
        ]
      }
    }],
    ["@semantic-release/changelog", {
      "changelogFile": "CHANGELOG.md"
    }],
    ["@semantic-release/exec", {
      "prepareCmd": "mvn versions:set -DnewVersion=${nextRelease.version} -DgenerateBackupPoms=false"
    }],
    ["@semantic-release/git", {
      "assets": ["CHANGELOG.md", "pom.xml"],
      "message": "chore(release): ${nextRelease.version} [skip ci]"
    }],
    ["@semantic-release/github", {
      "successComment": false,
      "failTitle": "Release failed for ${nextRelease.version}"
    }]
  ]
}
```

### Hotfix Process

Il processo di hotfix riguarda i fix urgenti su produzione che non possono attendere il normale ciclo di sprint. In trunk-based development, il processo è diverso da Gitflow.

```bash
# ── Hotfix Process in Trunk-Based Development ─────────────────────────────

# 1. Il bug è su produzione (versione 2.3.1)
# 2. Fix direttamente su main (se il fix è piccolo e sicuro)
git checkout main
git pull origin main
# ... applica il fix ...
git commit -m "fix(orders): prevent double-charge on payment retry

Closes #456. Root cause: idempotency key non veniva passato correttamente
al payment gateway su retry. Fix: pass order UUID come idempotency key.

HOTFIX: critico, doppio addebito in produzione."

git push origin main
# CI/CD pipeline fa il deployment automatico su staging
# ... verifica in staging ...
# Deploy su produzione via promozione dell'immagine staging

# 3. Se main ha commit in-flight non pronti per prod → cherry-pick su release branch
git checkout -b hotfix/2.3.2 v2.3.1   # branch dal tag di release, non da main
git cherry-pick <commit-hash-del-fix>
git tag v2.3.2
git push origin hotfix/2.3.2 --tags
# Deploy su produzione dall'immagine builddata dal tag v2.3.2

# 4. Dopo il deploy: porta il fix su main se non già presente
git checkout main
git cherry-pick <commit-hash-del-fix>  # se non già incluso
```

```yaml
# Pipeline CI specifica per hotfix (deploy fast-track)
# .github/workflows/hotfix.yaml

name: Hotfix Fast-Track

on:
  push:
    tags:
      - 'v*.*.*-hotfix*'   # es: v2.3.2-hotfix.1

jobs:
  hotfix-deploy:
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://api.myapp.com
    steps:
      - uses: actions/checkout@v4
      - name: Run critical tests only (fast gate)
        run: |
          # Solo smoke test e test critici — non la suite completa
          ./mvnw test -Dgroups="smoke,critical" -T 4
      - name: Build and push image
        run: |
          docker build -t ghcr.io/org/order-service:${{ github.ref_name }} .
          docker push ghcr.io/org/order-service:${{ github.ref_name }}
      - name: Deploy to production
        run: |
          kubectl set image deployment/order-service \
            order-service=ghcr.io/org/order-service:${{ github.ref_name }} \
            -n production
          kubectl rollout status deployment/order-service -n production --timeout=120s
      - name: Notify on-call
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: '#incidents'
          payload: |
            { "text": "🚨 Hotfix ${{ github.ref_name }} deployed to production by ${{ github.actor }}" }
```

---

## Architectural Decision Records (ADR)

### Cos'è un ADR e Perché è Necessario

Un ADR (Architectural Decision Record) è un documento breve che cattura una decisione architetturale significativa: il **contesto** che ha portato alla decisione, la **decisione stessa**, le **alternative considerate**, e le **conseguenze** attese. È la memoria a lungo termine del team: risponde alla domanda "perché abbiamo scelto X invece di Y?" quando X crea problemi 18 mesi dopo e nessuno del team originale è ancora presente.

!!! warning "ADR non sono documentazione generica"
    Un ADR si scrive SOLO per decisioni che: (1) hanno alternative reali che il team ha valutato, (2) sono difficili da cambiare una volta implementate, (3) non sono ovvie da leggere dal codice. Non scrivere ADR per scelte banali o reversibili.

### Template ADR (MADR — Markdown Architectural Decision Records)

```markdown
# ADR-0042: Scelta del message broker per event streaming

## Status
Accepted  <!-- Proposed | Accepted | Deprecated | Superseded by ADR-XXXX -->

## Context
Il sistema di ordini deve emettere eventi di dominio (OrderCreated, OrderPaid,
OrderShipped) consumati da 5 servizi downstream. Attualmente usiamo chiamate HTTP
sincrone che creano accoppiamento temporale e overhead di gestione errori.

Il team ha valutato il passaggio a un message broker per disaccoppiare i producer
dai consumer e abilitare replay degli eventi per nuovi consumer.

## Decision
Adottiamo **Apache Kafka** come message broker per gli event stream di dominio.

## Alternatives Considered

### RabbitMQ
- **Pro:** più semplice da operare, ottimo per task queue e work queue
- **Contro:** non è pensato per event streaming (replay, log compaction);
  la retention dei messaggi è limitata; scaling orizzontale più complesso
- **Scartato perché:** avremmo bisogno del replay per il consumer
  di analytics che sarà aggiunto in Q3

### AWS EventBridge
- **Pro:** fully managed, nessun overhead operativo
- **Contro:** lock-in AWS; latenza media più alta (100-500ms vs <10ms Kafka);
  nessun replay nativo (solo 24h archive)
- **Scartato perché:** il team prevede un deployment on-premise per un cliente enterprise

### Redis Streams
- **Pro:** bassa latenza, già in uso come cache
- **Contro:** durabilità limitata senza configurazione persistence;
  community e tooling molto più piccoli di Kafka
- **Scartato perché:** manca il supporto per consumer groups maturi e schema registry

## Consequences

### Positive
- Disaccoppiamento temporale tra producer e consumer
- Replay degli eventi per nuovi consumer o per recovery
- Schema Registry Confluent per evoluzione degli schema sicura
- Standard de facto nell'ecosistema microservizi: tooling ricco (Kafka Connect, etc.)

### Negative
- Overhead operativo: cluster Kafka (3 broker minimo), Schema Registry, Kafka UI
- Curva di apprendimento per il team (stima: 2 settimane per gli sviluppatori senior)
- Latenza aggiuntiva vs chiamata HTTP sincrona (~10-20ms per il roundtrip Kafka)
- I test di integrazione richiedono Testcontainers per Kafka

### Rischi
- Vendor ecosystem consolidation (Confluent vs open source Kafka vs Redpanda)
- Monitoring di Kafka richiede attenzione a lag consumer e under-replicated partitions

## References
- [Confluent — Kafka vs RabbitMQ](https://www.confluent.io/blog/kafka-vs-rabbitmq/)
- ADR-0038: Schema Registry per Avro
- [docs/messaging/kafka/](../../messaging/kafka/)
```

### Processo ADR nel Team

```markdown
## Processo ADR — Linee Guida

### Quando scrivere un ADR
- Scelta di un nuovo framework, libreria, o strumento con impatto > 1 team
- Decisione architetturale che è difficile da invertire
- Pattern di design applicato uniformemente (es. tutti i servizi usano X per Y)
- Quando il Tech Lead o un senior dev dice "questa è una decisione importante"

### Chi scrive
- Proposto da: chiunque abbia identificato la necessità
- Revisionato da: Tech Lead + almeno 1 senior del team coinvolto
- Approvato da: Tech Lead (o Engineering Manager per decisioni cross-team)

### Dove vivono
docs/adr/ADR-XXXX-titolo-kebab-case.md  # nel repository principale del team
                                          # o nel repository shared-docs per ADR cross-team

### Ciclo di vita
Proposed → in discussione, commenti aperti (max 1 settimana per decisioni urgenti)
Accepted  → implementazione può iniziare
Deprecated → la decisione non è più valida ma non è stata sostituita
Superseded by ADR-YYYY → rimpiazzata da una decisione successiva

### Numerazione
ADR-0001, ADR-0002, ... (padding a 4 cifre per ordinamento)
Non riusare i numeri di ADR annullate.
```

---

## Tech Lead — Responsabilità, RFC e Coupling Budget

### Il Ruolo del Tech Lead nell'SDLC

Il Tech Lead non è il developer più senior che fa architettura. È il ruolo che garantisce la **coerenza tecnica del processo** e che le decisioni vengono prese con il livello giusto di analisi, né troppo velocemente (debito architetturale) né troppo lentamente (over-engineering paralysis).

```yaml
# Responsabilità Tech Lead — framework chiaro

responsabilita_tecniche:
  - Revisionare e approvare ADR per il proprio team o dominio
  - Mantenere l'engineering excellence: DoD rispettata, qualità del codice, test coverage
  - Condurre design review per feature ad alto rischio o complessità
  - Tenere il coupling budget del sistema sotto controllo (vedi sotto)
  - Supportare il processo di RFC per decisioni cross-team

responsabilita_di_processo:
  - Garantire che il backlog tecnico abbia visibilità e venga pianificato
  - Facilitare le retrospettive tecniche trimestrali (tech health review)
  - Mentoring dei developer: code review educative, pair programming, learning budget
  - Interfaccia tra team tecnico e Product Manager su trade-off tecnici

responsabilita_organizzative:
  - Comunicare rischi tecnici al management in linguaggio business
  - Partecipare alle decisioni di hiring per il team
  - Allinearsi con gli altri Tech Lead su standard condivisi (platform decisions)

NON_responsabilita:  # confini importanti
  - Non è responsabile del delivery (il team lo è collettivamente)
  - Non approva ogni PR — solo quelle ad alto impatto o fuori DoD
  - Non è il collo di bottiglia per le decisioni quotidiane
```

### Request for Comments (RFC)

L'RFC è il meccanismo per raccogliere feedback su decisioni tecniche significative **prima** di iniziare l'implementazione. È particolarmente utile per decisioni cross-team o che hanno impatto su più servizi.

```markdown
# RFC-0023: Standardizzazione Health Check API

## Summary
Proponiamo di standardizzare il formato delle health check API su tutti i microservizi
del dominio payments adottando il formato Spring Boot Actuator / Kubernetes-native.

## Motivation
Attualmente ogni servizio espone health check in formato diverso, rendendo difficile
la configurazione uniforme delle probe Kubernetes e dei dashboard di monitoring.

## Detailed Design

### Endpoint standard
- `GET /health/liveness` → `{"status": "UP"}` / `{"status": "DOWN"}`
- `GET /health/readiness` → `{"status": "UP", "checks": {...}}`
- `GET /metrics` → formato Prometheus

### Migration path
1. Tutti i nuovi servizi adottano il formato da subito
2. Servizi esistenti: migrazione entro Q2-2026 (pianificata nel backlog tecnico)
3. Durante la migrazione: mantenere il vecchio endpoint come alias per compatibilità

## Alternatives
- **OpenAPI Health extension** (non standardizzata abbastanza)
- **Custom JSON** (scartato: non interopera con gli strumenti di monitoring standard)

## Open Questions
- [ ] Come gestire health check per servizi asincroni (consumer Kafka)?
- [ ] Il timeout del readiness check deve essere configurabile per servizio?

## Timeline
- RFC aperta: 2026-01-15
- Periodo di feedback: 2 settimane
- Decisione finale: 2026-01-29

## Stakeholders
- Richiede feedback da: team-orders, team-inventory, team-platform
- Decisione finale: Tech Lead area payments + Principal Engineer
```

### Coupling Budget

Il coupling budget è il limite esplicito di accoppiamento tra microservizi che il team si impone per evitare che l'architettura degradi in un "distributed monolith" mascherato da microservizi.

```yaml
# Coupling Budget — linee guida per l'architettura

metriche_accoppiamento:
  fan_out_sincrono:
    descrizione: "Numero di servizi che un microservizio chiama sincronamente"
    soglia_warning: 3    # > 3 chiamate sincrone in un singolo flow → valutare
    soglia_critica: 5    # > 5 → quasi certamente un problema architetturale
    motivazione: |
      Ogni chiamata sincrona aggiunge latenza e un punto di failure. Un servizio
      che fa 6 chiamate sincrone in una request ha un SLA che è il prodotto
      delle disponibilità di tutti e 6 (0.999^6 = 99.4%).

  dipendenze_shared_database:
    descrizione: "Numero di servizi che condividono lo stesso schema DB"
    soglia_critica: 1    # > 1 = mai accettabile per microservizi
    motivazione: |
      Un database condiviso è un accoppiamento nascosto: un team può cambiare
      lo schema e rompere gli altri servizi silenziosamente. Database per servizio
      è il pattern obbligatorio.

  numero_consumer_evento:
    descrizione: "Numero di consumer di un singolo evento Kafka"
    soglia_warning: 10
    motivazione: |
      Un evento con 20 consumer è un evento con 20 dipendenze. Se il formato
      dell'evento cambia, si ha un breaking change con impatto enorme.
      Valutare se un evento del dominio è usato da troppe cose: potrebbe essere
      un segnale che il dominio non è ben delimitato.

revisione_trimestrale:
  quando: "Ultimo venerdì del quarter"
  agenda:
    - Revisione metriche coupling (fan-out, shared state, event consumers)
    - Identificazione servizi che superano le soglie
    - Pianificazione refactoring nel prossimo quarter se necessario
  output: "ADR se si decide un cambio architetturale, altrimenti backlog items"
```

```python
# Script per misurare il fan-out sincrono analizzando il codice
# Analizza le chiamate HTTP/gRPC e produce un report di coupling

#!/usr/bin/env python3
"""
analyze_coupling.py — analizza le dipendenze sincrone tra microservizi
Legge i file di configurazione (application.yaml) e il codice sorgente
per costruire una mappa di accoppiamento.
"""
import re
import yaml
import pathlib
from collections import defaultdict

def find_http_clients(repo_path: str) -> dict:
    """Trova tutti i RestTemplate/WebClient/HttpClient nel codebase."""
    coupling_map = defaultdict(list)
    src = pathlib.Path(repo_path) / "src"

    # Pattern per URL di altri servizi (environment variables come best practice)
    url_patterns = [
        r'@Value\(".*\$\{([\w-]+\.url)\}.*"\)',
        r'getenv\("([\w_]+_URL)"\)',
        r'os\.Getenv\("([\w_]+_URL)"\)',
    ]

    for java_file in src.rglob("*.java"):
        content = java_file.read_text(encoding="utf-8", errors="ignore")
        for pattern in url_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                coupling_map[str(java_file.relative_to(repo_path))].append(match)

    return dict(coupling_map)

if __name__ == "__main__":
    import sys
    import json
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    coupling = find_http_clients(repo)

    # Report fan-out per file
    for file, deps in sorted(coupling.items(), key=lambda x: len(x[1]), reverse=True):
        status = "❌" if len(deps) >= 5 else "⚠️" if len(deps) >= 3 else "✅"
        print(f"{status} {file}: {len(deps)} dipendenze sincrone → {deps}")
```

---

## Best Practices

### Sprint Planning
- Pianifica il debito tecnico **durante** lo sprint planning, non "quando ci sarà tempo" — quel tempo non arriva mai
- Usa le **velocity storiche** reali, non la capacity teorica: includere cerimonie, supporto, e interruzioni
- Un'Epic tecnica che supera 13 story point è troppo grande: spezzala in rilasci incrementali misurabili
- Dopo ogni sprint review, analizza se il debito tecnico non pianificato ha impattato la velocity — se sì, aumenta la percentuale riservata

### Definition of Done
- La DoD **non si negozia per scadenze**: abbassare i quality gate sotto pressione accumula debito imprudente
- Rendi la DoD visibile: appendila alla board fisica/virtuale del team, non solo nel wiki
- Rivedi la DoD **ogni trimestre**: le soglie cambiano man mano che il sistema matura
- Se una story non supera la DoD, non deployarla — deployarla è un prestito con interesse molto alto

### Feature Flags
- Ogni flag deve avere **un owner e una data di scadenza** — senza questi, si accumulano indefinitamente
- Testa entrambi i rami del flag nei test automatici: `enabled=true` e `enabled=false`
- Non usare feature flag per **configurazione**: usa ConfigMap/Secret/environment variables per quello
- Fai il **cleanup** del flag come parte della story successiva al rollout completo — mai "dopo"

### ADR
- Scrivi l'ADR **prima** di implementare, non dopo — l'obiettivo è il processo decisionale, non la documentazione post-hoc
- Un ADR di una pagina è meglio di un ADR di dieci pagine che nessuno legge
- Se hai dubbi su "se scrivere l'ADR": scrivilo — il costo è basso, il beneficio è l'allineamento del team

### Release Management
- Non fare hotfix senza un ticket associato — anche l'hotfix più piccolo deve avere tracciabilità
- Il CHANGELOG deve essere generato automaticamente dai commit message — mantenuto manualmente è sempre obsoleto
- **Freeze window**: comunicare le finestre di blocco deploy in anticipo, specialmente durante periodi critici (fine anno, rilasci major del cliente)

---

## Troubleshooting

### Sprint Planning — Velocity instabile

**Sintomo:** la velocity varia del 40%+ tra sprint, rendendo la pianificazione inaffidabile.

**Causa:** interruzioni non contabilizzate (supporto, bug produzione, meeting improvvisi) o story point non calibrati uniformemente nel team.

```markdown
# Diagnosi in retrospettiva
1. Conta le ore effettivamente spese su lavoro non pianificato (tracking obbligatorio)
2. Verifica: i punti stimati dal team hanno stessa magnitudine per tutti i membri?
3. Usa una sessione di Planning Poker su story già completate per ricalibrare

# Fix strutturale
- Buffer esplicito del 10% per supporto/interruzioni non pianificate
- Revisione della stima media ogni 3 sprint con running average
- Definire la "velocità sostenibile" come media delle ultime 3-5 sprint, non il massimo
```

### Quality Gate — Coverage in calo continuo

**Sintomo:** la code coverage scende ogni sprint nonostante la soglia dell'80% sia tecnicamente applicata.

**Causa:** la coverage è misurata sul totale del codebase, non sui nuovi file. Codice legacy non coperto "diluisce" il coverage di codice nuovo ben testato.

```bash
# Fix: misura la coverage DIFFERENZIALE (solo sulle righe modificate nella PR)
# JaCoCo + Danger.js per report differenziale

# In CI — genera report solo sulle linee cambiate nel PR
./mvnw jacoco:report

# dangerfile.js — applica la soglia solo alle righe modificate
import { danger, fail } from 'danger'

const changedFiles = danger.git.modified_files.filter(f => f.endsWith('.java'))
for (const file of changedFiles) {
  const coverage = getCoverageForFile(file)  // da jacoco.xml
  if (coverage < 80) {
    fail(`${file}: coverage ${coverage}% < 80% threshold su righe modificate`)
  }
}
```

### ADR — Nessuno le legge o le aggiorna

**Sintomo:** gli ADR vengono scritti ma mai consultati, e le decisioni architetturali vengono prese nuovamente senza consapevolezza di quelle precedenti.

**Causa:** gli ADR non sono integrati nel processo — non si linkano alle PR, non si citano nelle code review, non si verificano nelle onboarding.

```markdown
# Fix: integrare gli ADR nel workflow quotidiano

1. Template PR: aggiungi "ADR relevant?" come campo obbligatorio nel PR template
2. Code review: "Questa decisione è coerente con ADR-0042?" come commento attivo
3. Onboarding checklist: "Leggi gli ultimi 10 ADR del tuo team"
4. Sprint planning: "Questa epic richiede un nuovo ADR?" come domanda standard
5. Quarterly: review degli ADR "Accepted" per verificare se sono ancora validi
```

### Hotfix — Deploy in produzione rompe altro

**Sintomo:** il hotfix risolve il bug originale ma introduce una regressione.

**Causa:** il fast-track del hotfix bypassa i test di integrazione completi.

```bash
# Prevenzione: definire una smoke test suite che gira sempre, anche nei hotfix

# test/smoke/SmokeTestSuite.java — test critici che non possono mai essere saltati
@Tag("smoke")
class SmokeTestSuite {
    @Test void orderCreation_happyPath() { ... }
    @Test void paymentProcessing_happyPath() { ... }
    @Test void orderRetrieval_byId() { ... }
    // Massimo 10 test, devono girare in < 2 minuti
}

# In hotfix pipeline: esegui SOLO smoke + critical
./mvnw test -Dgroups="smoke,critical" -Dsurefire.failIfNoSpecifiedTests=false
```

### Feature Flag — Performance degradata

**Sintomo:** la valutazione dei feature flag aggiunge 50-100ms a ogni request.

**Causa:** l'SDK chiama il server remoto ad ogni valutazione invece di usare la cache locale.

```java
// Fix: configurare correttamente la cache locale dell'SDK
// Unleash SDK — configurazione con polling e cache locale

UnleashConfig config = UnleashConfig.builder()
    .appName("order-service")
    .instanceId(hostname)
    .unleashAPI(unleashUrl)
    // Cache locale: i flag vengono valutati in-memory, aggiornati ogni 15s
    .fetchTogglesInterval(15)           // polling ogni 15 secondi (non ad ogni call)
    .synchronousFetchOnInitialisation(true)  // blocca all'avvio finché non ha i flag
    .build();

// LaunchDarkly equivalente
LDConfig ldConfig = new LDConfig.Builder()
    .dataSource(Components.streamingDataSource())  // SSE streaming: sub-ms latency
    .build();
// LDClient usa una cache in-memory locale — latenza < 1ms per valutazione
```

---

## Relazioni

??? info "Developer Workflow — Il processo quotidiano"
    Il workflow del singolo developer: inner loop, Skaffold, Devcontainer, conventional commits, PR workflow. L'SDLC enterprise è il framework che contiene il developer workflow come sotto-processo. → [Developer Workflow](developer-workflow.md)

??? info "CI/CD Pipeline — L'automazione del quality gate"
    I quality gate della DoD sono implementati come job nella pipeline CI/CD. → [CI/CD Pipeline](../../ci-cd/strategie/deployment-strategies.md)

---

## Riferimenti

- [Martin Fowler — Technical Debt Quadrant](https://martinfowler.com/bliki/TechnicalDebtQuadrant.html) — la tassonomia del debito tecnico
- [Martin Fowler — Is High Quality Software Worth the Cost?](https://martinfowler.com/articles/is-quality-worth-cost.html) — la relazione tra qualità e velocity
- [MADR — Markdown Architecture Decision Records](https://adr.github.io/madr/) — template e tooling per ADR
- [Unleash Documentation](https://docs.getunleash.io/) — feature flag self-hosted
- [LaunchDarkly Documentation](https://docs.launchdarkly.com/) — feature flag enterprise SaaS
- [Flagsmith Documentation](https://docs.flagsmith.com/) — feature flags + remote config
- [Semantic-Release](https://semantic-release.gitbook.io/) — automated versioning and changelog
- [Team Topologies](https://teamtopologies.com/) — Conway's Law e organizzazione dei team per ridurre il coupling
- [Accelerate — DORA Metrics](https://dora.dev/research/) — metriche di performance ingegneristica (deployment frequency, lead time, MTTR, change failure rate)
- [Google Engineering Practices — Technical writing](https://google.github.io/eng-practices/) — standard per documentazione tecnica e code review
