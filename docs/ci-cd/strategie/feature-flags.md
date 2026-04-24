---
title: "Feature Flags"
slug: feature-flags
category: ci-cd
tags: [feature-flags, release-management, progressive-delivery, openfeature, launchdarkly, unleash, flipt, a-b-testing, canary, trunk-based-development]
search_keywords: [feature flag, feature toggle, feature switch, release toggle, experiment toggle, ops toggle, permission toggle, kill switch, dark launch, gradual rollout, progressive delivery, openfeature, launchdarkly, unleash, flipt, flagd, feature flag debt, stale flag, flag lifecycle, branch by abstraction, canary release, a/b testing, flag evaluation, targeting rule, rollout percentage, flag cleanup, feature management, toggle, runtime configuration, flag debt, combinatorial explosion]
parent: ci-cd/strategie/_index
related: [ci-cd/strategie/deployment-strategies, ci-cd/strategie/trunk-based-development, ci-cd/gitops/argocd, ci-cd/testing/contract-testing]
official_docs: https://openfeature.dev/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Feature Flags

## Panoramica

I feature flag (detti anche feature toggle, feature switch) sono un meccanismo che permette di separare il **deployment del codice** dalla **release di funzionalità** agli utenti. Il codice viene deployato in produzione ma la feature rimane inattiva finché non si decide di attivarla — senza alcun deploy aggiuntivo. Questo disaccoppiamento è uno dei pattern più potenti in DevOps moderno.

Il vantaggio principale è il controllo granulare: una feature può essere attivata per il 5% degli utenti, solo per i beta tester, solo in una regione geografica, o solo quando le metriche rimangono entro soglie predefinite. Il rollback di una feature diventa istantaneo — basta disabilitare il flag, nessun revert di codice.

I feature flag non sono sinonimo di "codice spaghetti con tanti if": con le giuste pratiche, hanno un ciclo di vita definito, vengono rimossi una volta che la feature è stabilizzata, e sono gestiti tramite un sistema centralizzato che offre audit trail, targeting rules, e metriche di utilizzo.

!!! warning "Flag debt — il rischio principale"
    I feature flag sono uno strumento potente ma devono avere un ciclo di vita esplicito. Un flag mai rimosso diventa debito tecnico: aumenta la complessità del codice, rende difficile il testing, e può causare comportamenti imprevisti. Il lifecycle management è tanto importante quanto la creazione del flag.

## Concetti Chiave

### Tipi di Feature Flag

I quattro tipi fondamentali, secondo la tassonomia di Pete Hodgson / Martin Fowler:

| Tipo | Scopo | Durata tipica | Cambio frequente | Esempio |
|------|-------|---------------|------------------|---------|
| **Release flag** | Nasconde feature incompleta durante lo sviluppo | Giorni / settimane | No | Nuovo flusso di checkout ancora in sviluppo |
| **Experiment flag** | A/B test per raccogliere dati di business | Settimane / mesi | Sì (% rollout) | Variante UI A vs B per misurare conversion rate |
| **Ops flag** | Circuit breaker operativo — kill switch | Indefinita | Emergenza | Disabilita modulo AI costoso sotto carico |
| **Permission flag** | Accesso a feature per segmenti specifici | Indefinita | No | Feature solo per utenti Enterprise o beta program |

!!! tip "Release vs Experiment"
    Un **release flag** è binario: off durante sviluppo, on quando pronto, poi rimosso. Un **experiment flag** è graduale: parte al 5%, poi 20%, poi 100%, con raccolta di metriche in ogni fase. Non confonderli: hanno dinamiche e tooling diversi.

### Architettura di Valutazione

Un sistema di feature flag si compone di:

```
┌─────────────────────────────────────────────────────────────┐
│                    Flag Management UI                        │
│  (crea flag, definisce targeting rules, monitora metrics)   │
└────────────────────────┬────────────────────────────────────┘
                         │ Flag configuration (sync)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Flag Server / Store                        │
│  (LaunchDarkly, Unleash, Flipt, flagd, Redis...)            │
│  Espone API gRPC/REST per evaluation e streaming updates    │
└────────────────────────┬────────────────────────────────────┘
                         │ SDK polling o streaming
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application SDK                          │
│  Cache locale + evaluation engine (OpenFeature standard)    │
│  Fallback al default value se server non raggiungibile      │
└────────────────────────┬────────────────────────────────────┘
                         │ Boolean/String/Number/JSON value
                         ▼
                    Codice applicativo
                 if flag_enabled: ... else: ...
```

### Lifecycle di un Flag

```
           ┌─────────┐
           │ Creato  │  ← definito nello store, default: OFF
           └────┬────┘
                │ deploy del codice con il flag
                ▼
           ┌──────────┐
           │  Attivo  │  ← targeting rules configurate
           │  (OFF)   │    solo per dev/beta tester
           └────┬─────┘
                │ gradual rollout  5% → 20% → 50% → 100%
                ▼
           ┌──────────┐
           │  Attivo  │  ← monitoraggio metriche in ogni fase
           │  (ON)    │    rollback immediato se anomalie
           └────┬─────┘
                │ feature stabilizzata al 100%
                ▼
           ┌──────────┐
           │ Cleanup  │  ← rimuovi il codice condizionale
           │  ticket  │    poi rimuovi dal flag store
           └──────────┘
```

### OpenFeature — Standard CNCF

OpenFeature è lo standard vendor-neutral per l'integrazione di feature flags, progetto CNCF graduato nel 2024. Definisce un'API uniforme che permette di cambiare provider (LaunchDarkly → Unleash → Flipt) senza modificare il codice applicativo. L'SDK si registra contro un provider e il codice applicativo usa sempre la stessa interfaccia indipendentemente dal backend.

!!! note "Perché OpenFeature"
    Prima di OpenFeature, ogni cambio di provider richiedeva di riscrivere tutte le chiamate all'SDK proprietario. Con OpenFeature, si cambia solo il provider registrato — il codice applicativo resta invariato.

## Architettura / Come Funziona

### Evaluation Pipeline

Quando il codice chiama `getBooleanValue("flag-key", false, context)`, l'SDK esegue questa pipeline:

1. **Lookup del flag** nella cache locale (aggiornata via polling ogni 30s o streaming)
2. **Targeting evaluation**: scorrere le regole in ordine di priorità
   - Regola 1: `userId == "admin-001"` → `true`
   - Regola 2: `plan == "enterprise"` → `true`
   - Regola 3: `rollout 10%` → `true` per 10% degli userId (hash deterministico)
   - Fallthrough: `false`
3. **Fallback**: se il server non è raggiungibile → ritorna il default value dichiarato nel codice
4. **Hook execution**: before/after hooks per logging, metrics, telemetry OpenTelemetry

### Rollout Graduale e Determinismo

Il rollout percentuale usa un hash deterministico sull'`userId` (o altro attributo stabile). Questo garantisce che lo stesso utente veda sempre la stessa variante — nessun switching casuale ad ogni request.

```
userId "abc123" → murmur3(userId) → 0.37 → < 0.40 (40%) → flag ON
userId "xyz789" → murmur3(userId) → 0.82 → > 0.40 (40%) → flag OFF
```

Aumentare la percentuale da 40% a 60% include deterministicamente più utenti — chi era già ON rimane ON. La coerenza dell'esperienza utente è garantita anche con più istanze del servizio.

### Branch by Abstraction con Feature Flags

Pattern per refactoring massicci senza long-lived branches. Permette di fare la migrazione in commit incrementali sul trunk:

```
Step 1: introduce astrazione
  interface HttpClient { get(), post() }
  LegacyHttpClient implements HttpClient (wrapper v1)
  → merge sul trunk, tutti usano LegacyHttpClient

Step 2: implementa nuova versione
  ModernHttpClient implements HttpClient (nuova impl)
  → merge sul trunk, ModernHttpClient esiste ma non è usata

Step 3: feature flag seleziona l'implementazione
  if flag("modern-http-client"): return ModernHttpClient()
  else: return LegacyHttpClient()
  → rollout graduale, monitoraggio, rollback istantaneo

Step 4: cleanup dopo stabilizzazione
  rimuovi LegacyHttpClient, rimuovi l'astrazione
  → il flag viene rimosso insieme al codice legacy
```

### Feature Flags per Canary Release

A differenza dei canary deployment infrastrutturali (due versioni del pod), il canary via feature flags opera a livello applicativo:

```
Canary infrastrutturale:          Canary via feature flag:
  90% → pod v1                      100% → pod v2 (unica versione)
  10% → pod v2                        10% → flag ON (nuova feature)
  (routing in ingress/mesh)           90% → flag OFF (comportamento legacy)
```

Il canary via feature flag è più veloce da attivare/disattivare e non richiede modifiche infrastrutturali, ma richiede che entrambe le implementazioni coesistano nello stesso codebase.

## Configurazione & Pratica

### OpenFeature con Flipt (Go)

```go
package main

import (
    "context"
    "fmt"
    "log"

    flipt "github.com/open-feature/go-sdk-contrib/providers/flipt/pkg/provider"
    "github.com/open-feature/go-sdk/openfeature"
)

func main() {
    // Configura il provider Flipt
    provider, err := flipt.New(
        flipt.WithAddress("https://flipt.mycompany.internal:9000"),
        flipt.WithNamespace("production"),
    )
    if err != nil {
        log.Fatal(err)
    }

    // Registra il provider globalmente — una sola volta al bootstrap
    openfeature.SetProvider(provider)
    client := openfeature.NewClient("checkout-service")
    ctx := context.Background()

    // Evaluation context con attributi utente
    evalCtx := openfeature.NewEvaluationContext(
        "user-12345",                          // targeting key — deve essere stabile
        map[string]interface{}{
            "email":      "user@example.com",
            "plan":       "enterprise",
            "country":    "IT",
            "betaTester": true,
        },
    )

    // Valutazione booleana — default false se provider non raggiungibile
    enabled, err := client.BooleanValue(ctx, "new-checkout-flow", false, evalCtx)
    if err != nil {
        // L'errore non blocca: il default è già stato ritornato
        log.Printf("flag evaluation warning: %v", err)
    }

    if enabled {
        fmt.Println("Nuovo checkout attivo per questo utente")
    }

    // Valutazione stringa per A/B test con varianti multiple
    variant, _ := client.StringValue(ctx, "checkout-ui-variant", "control", evalCtx)
    fmt.Printf("UI variant: %s\n", variant)  // "control" | "variant-a" | "variant-b"
}
```

### OpenFeature con LaunchDarkly (Python)

```python
import ldclient
from ldclient.config import Config
from openfeature import api
from openfeature.evaluation_context import EvaluationContext

# Setup provider LaunchDarkly tramite OpenFeature
ldclient.set_config(Config("sdk-your-sdk-key-here"))
ld_client = ldclient.get()

# Wrapper OpenFeature — il codice sotto non sa che backend usa
from openfeature.contrib.provider.launchdarkly import LaunchDarklyProvider
api.set_provider(LaunchDarklyProvider(ld_client))
client = api.get_client("payment-service")

# Context di valutazione — targeting_key deve essere stabile (user ID, non session ID)
context = EvaluationContext(
    targeting_key="user-12345",
    attributes={
        "email":      "user@example.com",
        "plan":       "enterprise",
        "country":    "IT",
        "betaTester": True,
    }
)

# Boolean flag — release toggle
show_new_payment = client.get_boolean_value("new-payment-flow", False, context)

# String flag — experiment con varianti multiple
ui_variant = client.get_string_value("checkout-ui-variant", "control", context)
# Possibili valori: "control", "variant-a", "variant-b"

# Number flag — ops flag per configurazione dinamica
rate_limit = client.get_integer_value("api-rate-limit-per-minute", 100, context)

# Track evento per A/B testing — associa l'utente al risultato
ld_client.track("checkout-completed", context.targeting_key, metric_value=order.total)
```

### Flipt — Deploy Self-Hosted su Kubernetes

```yaml
# flipt-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flipt
  namespace: feature-flags
spec:
  replicas: 2      # Alta disponibilità — gli SDK hanno failsafe ma meglio non testarlo
  selector:
    matchLabels:
      app: flipt
  template:
    metadata:
      labels:
        app: flipt
    spec:
      containers:
        - name: flipt
          image: flipt/flipt:v1.39.0
          ports:
            - containerPort: 8080   # HTTP UI e REST API
            - containerPort: 9000   # gRPC (preferito per SDK)
          env:
            - name: FLIPT_DB_URL
              valueFrom:
                secretKeyRef:
                  name: flipt-db-secret
                  key: url
            - name: FLIPT_CACHE_ENABLED
              value: "true"
            - name: FLIPT_CACHE_TTL
              value: "30s"
            - name: FLIPT_CACHE_BACKEND
              value: "redis"
            - name: FLIPT_CACHE_REDIS_HOST
              value: "redis.feature-flags.svc.cluster.local"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: flipt
  namespace: feature-flags
spec:
  selector:
    app: flipt
  ports:
    - name: http
      port: 8080
      targetPort: 8080
    - name: grpc
      port: 9000
      targetPort: 9000
```

```bash
# Creare un flag via Flipt REST API
curl -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/flags \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FLIPT_TOKEN" \
  -d '{
    "key": "new-checkout-flow",
    "name": "New Checkout Flow",
    "description": "Nuovo flusso checkout con Apple Pay e Google Pay",
    "enabled": true,
    "type": "BOOLEAN_FLAG_TYPE"
  }'

# Creare targeting rule — solo utenti con plan=enterprise al 100%
curl -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/flags/new-checkout-flow/rules \
  -H "Content-Type: application/json" \
  -d '{
    "rank": 1,
    "segmentKey": "enterprise-users",
    "distributions": [{"variant_key": "on", "rollout": 100}]
  }'

# Aggiungere rollout percentuale per tutti gli altri utenti (10%)
curl -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/flags/new-checkout-flow/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "rank": 2,
    "threshold": {"percentage": 10.0, "value": true}
  }'

# Verificare la valutazione di un flag per un utente specifico
curl -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/evaluation/boolean \
  -H "Content-Type: application/json" \
  -d '{
    "flag_key": "new-checkout-flow",
    "entity_id": "user-12345",
    "context": {"plan": "enterprise", "country": "IT"}
  }'
```

### Unleash — Feature Flag Open Source

```yaml
# docker-compose per Unleash (sviluppo locale / staging)
version: '3.8'
services:
  unleash:
    image: unleashorg/unleash-server:6
    ports:
      - "4242:4242"
    environment:
      DATABASE_URL: "postgres://unleash:password@db/unleash"
      INIT_FRONTEND_API_TOKENS: "default:development.unleash-insecure-frontend-api-token"
      INIT_CLIENT_API_TOKENS: "default:development.unleash-insecure-api-token"
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: unleash
      POSTGRES_USER: unleash
      POSTGRES_PASSWORD: password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U unleash"]
      interval: 5s
      timeout: 5s
      retries: 5
```

```python
# Python SDK Unleash — uso diretto (senza OpenFeature wrapper)
from UnleashClient import UnleashClient

client = UnleashClient(
    url="https://unleash.mycompany.internal/api",
    app_name="payment-service",
    custom_headers={"Authorization": "Bearer <client-api-token>"},
    # refresh_interval: polling ogni 15s (default)
    # metrics_interval: invio metriche ogni 60s (default)
)
client.initialize_client()

# Valutazione con context utente
context = {"userId": "user-12345", "properties": {"plan": "enterprise"}}
is_enabled = client.is_enabled("new-payment-flow", context)

# Gradual rollout — Unleash gestisce la percentuale con strategy "gradualRolloutUserId"
# configurata nell'UI: 10% degli userId → ON
is_in_rollout = client.is_enabled("beta-dashboard", {"userId": "user-12345"})
```

### Lifecycle Management con GitOps (Flag as Code)

```yaml
# feature-flags/flags.yaml — flag definiti come Infrastructure as Code
flags:
  - key: new-checkout-flow
    description: "Nuovo flusso checkout con Apple Pay — lancio Q2 2026"
    type: boolean
    default_value: false
    owner: team-payments              # Team responsabile del cleanup
    created: "2026-03-01"
    expires: "2026-06-30"             # Data scadenza — OBBLIGATORIA per release/experiment flag
    status: active                    # draft | active | retired
    rollout:
      strategy: gradual
      percentage: 25                  # Aumentare progressivamente dopo monitoring
    targeting:
      - segment: enterprise-users
        value: true
      - segment: beta-testers
        value: true

  - key: legacy-payment-processor
    description: "Kill switch per il vecchio processore pagamenti"
    type: boolean
    default_value: true               # ON per default — disabilitare per completare migrazione
    owner: team-payments
    created: "2025-01-15"
    expires: null                     # Ops flag — nessuna scadenza, review semestrale
    status: active
```

```yaml
# .github/workflows/flag-cleanup.yml — controllo automatico flag scaduti
name: Feature Flag Cleanup Check

on:
  schedule:
    - cron: '0 9 * * 1'   # Ogni lunedì mattina

jobs:
  check-expired-flags:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check expired and near-expiry flags
        run: |
          python scripts/check_flag_expiry.py \
            --flags-file feature-flags/flags.yaml \
            --warn-days 14 \
            --error-days 0

      - name: Create cleanup issue if flags expired
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Flag cleanup required — expired feature flags detected',
              body: 'Automated check found feature flags past expiry date. Review feature-flags/flags.yaml.',
              labels: ['tech-debt', 'feature-flags']
            })
```

## Best Practices

### Naming e Organizzazione

```python
# ✅ Nomi con namespace e descrizione chiara
"payments.checkout.new-flow-v2"
"auth.login.passwordless-enabled"
"infra.cache.redis-fallback-active"
"experiments.homepage.hero-cta-variant"

# ❌ Nomi ambigui, generici, o senza contesto
"new_feature"
"test_flag"
"flag1"
"temp"
```

!!! tip "Namespace nei nomi dei flag"
    Usare il formato `[dominio].[servizio].[descrizione]` rende i flag ordinabili, filtrabili, e associabili chiaramente al team owner. Nei sistemi come Unleash o Flipt i namespace sono anche una feature nativa — sfruttarla per separare flag per ambiente o dominio.

### Regole del Lifecycle

1. **Ogni flag ha un owner** — team responsabile della creazione, del monitoring, e del cleanup
2. **Release/experiment flag: data di scadenza obbligatoria** — non superare 90 giorni senza revisione esplicita
3. **Ops flag e permission flag**: nessuna scadenza fissa, ma review semestrale obbligatoria
4. **Flag rimossi in due fasi**:
   - Fase 1: rimuovere il codice condizionale (scegliere il ramo definitivo, eliminare l'altro)
   - Fase 2: rimuovere il flag dallo store (dopo deploy confermato stabile)
5. **Mai rimuovere dal store senza aver rimosso dal codice** — causerebbe fallback silenziosi

### Evitare la Combinatorial Explosion

Con N flag booleani attivi contemporaneamente sullo stesso code path si hanno 2^N combinazioni possibili. Con 10 flag: 1024 combinazioni. La maggior parte non viene mai testata e possono emergere bug impossibili da riprodurre.

```python
# ❌ Anti-pattern — flag interdipendenti che si combinano
if flag_a and flag_b:
    do_thing_a_and_b()
elif flag_a and not flag_b:
    do_thing_a_only()
elif not flag_a and flag_b:
    do_thing_b_only()

# ✅ Flag indipendenti — ogni flag governa una feature distinta
# Nessuna logica condizionale tra flag diversi
if flag_a:
    # Feature A completamente isolata — non sa di flag_b
    ...
if flag_b:
    # Feature B completamente isolata — non sa di flag_a
    ...
```

!!! warning "Mai più di 2-3 flag attivi nello stesso code path"
    Se un code path ha più di 3 flag attivi contemporaneamente, è un segnale di flag debt accumulato o di design scorretto. Rimuovere i flag stabili prima di aggiungerne di nuovi. Il numero di combinazioni di test cresce esponenzialmente.

### Testing con Feature Flags

```python
# Test parametrizzati per coprire entrambe le varianti del flag
import pytest
from unittest.mock import patch

@pytest.mark.parametrize("flag_enabled", [True, False])
def test_checkout_flow(flag_enabled, mock_openfeature):
    mock_openfeature.set_flag("new-checkout-flow", flag_enabled)

    response = client.post("/checkout", json=order_data)

    if flag_enabled:
        assert response.json()["processor"] == "new-processor"
    else:
        assert response.json()["processor"] == "legacy-processor"

# In CI: eseguire sempre entrambe le varianti
# Evitare di mockare i flag in modo che siano sempre ON — si perde la copertura del ramo legacy
```

## Troubleshooting

### Scenario 1 — Flag valutato sempre come default (fallback costante)

**Sintomo:** La feature non appare per nessun utente anche con il flag abilitato nel pannello di controllo. I log mostrano il valore di default ritornato.

**Causa:** L'SDK non riesce a raggiungere il flag server (NetworkPolicy bloccante, DNS non risolto, certificato TLS scaduto, API token errato o scaduto). In failsafe mode, tutti i flag ritornano il valore di default configurato nel codice.

**Diagnosi:**
```bash
# Verificare connettività dal pod al flag server
kubectl exec -it deployment/my-app -n production -- \
  curl -v https://flipt.feature-flags.svc.cluster.local:8080/health

# Verificare NetworkPolicy — il pod deve poter raggiungere il namespace feature-flags
kubectl get networkpolicy -n production
kubectl describe networkpolicy allow-egress-feature-flags -n production

# Verificare che il secret con l'API token sia presente e valido
kubectl get secret feature-flag-sdk-token -n production \
  -o jsonpath='{.data.token}' | base64 -d | wc -c   # deve essere > 0

# Cercare errori di connessione nei log dell'applicazione
kubectl logs -l app=my-app -n production --since=10m \
  | grep -i "openfeature\|flipt\|unleash\|launchdarkly\|provider\|connection"
```

**Soluzione:** Correggere la NetworkPolicy per permettere l'egress verso il namespace `feature-flags` su porta 9000 (gRPC) e 8080 (HTTP). Se il token è scaduto, ruotarlo e aggiornare il Secret Kubernetes.

---

### Scenario 2 — Flag attivato ma il comportamento non cambia

**Sintomo:** I log dell'SDK mostrano `flag: true` ma il codice non segue il ramo corretto.

**Causa comune 1 — Cache stale:** Il TTL della cache locale è 30-60s. Se il flag è stato appena cambiato, l'SDK non l'ha ancora ricevuto.

```bash
# Verificare il TTL configurato nell'SDK
grep -rn "cache\|ttl\|polling\|refresh" src/config/feature-flags.*

# Attendere il prossimo polling cycle o forzare refresh se l'SDK lo supporta
curl -X POST https://my-app.internal/admin/flags/refresh
```

**Causa comune 2 — Targeting key errata:** L'evaluation context usa `session_id` come targeting key, ma le regole del flag sono definite su `userId`. Le due evaluations puntano a identità diverse.

```python
# Debug: loggare il contesto esatto inviato al server
from openfeature import api
from openfeature.hook import Hook

class DebugHook(Hook):
    def before(self, hook_context, hints):
        print(f"[FLAG DEBUG] key={hook_context.flag_key} "
              f"targeting_key={hook_context.evaluation_context.targeting_key} "
              f"attrs={hook_context.evaluation_context.attributes}")

client = api.get_client()
client.add_hooks([DebugHook()])
```

---

### Scenario 3 — Flag debt: flag obsoleti non rimossi

**Sintomo:** Avviso di CI "flag 'old-feature' scaduto il 2026-01-15", oppure code review che scopre 15+ flag attivi nello stesso modulo con logiche sovrapposte.

**Diagnosi — Audit automatico:**
```bash
# Trovare tutti i flag referenziati nel codice sorgente
grep -r "is_enabled\|getBooleanValue\|variation\|isEnabled\|get_flag" src/ \
  | grep -oP '"[a-z][a-z0-9\-\.]+[a-z0-9]"' \
  | tr -d '"' | sort -u > /tmp/code_flags.txt

# Estrarre i flag attivi nel store Flipt
curl -s https://flipt.mycompany.internal/api/v1/namespaces/default/flags \
  | jq -r '.flags[].key' | sort > /tmp/store_flags.txt

# Flag nel codice ma NON nel store → zombie flags (il codice punta a flag eliminati)
comm -23 /tmp/code_flags.txt /tmp/store_flags.txt

# Flag nel store ma NON nel codice → orphan flags (mai usati o già rimossi dal codice)
comm -13 /tmp/code_flags.txt /tmp/store_flags.txt
```

**Soluzione:** Per ogni zombie flag, verificare se il flag era stato eliminato per errore o se il codice deve essere ripulito. Per gli orphan flags, eliminarli dal store dopo verifica.

---

### Scenario 4 — Rollout percentuale non deterministico (flag "flickering")

**Sintomo:** Lo stesso utente vede la feature attiva a volte sì e a volte no, senza spiegazione. Le segnalazioni degli utenti sono inconsistenti.

**Causa:** La targeting key è un attributo volatile (session ID, request ID, timestamp) invece di un ID stabile. Oppure il flag server è stato riconfigurato con un seed di hashing diverso.

```python
# ✅ Targeting key stabile — stesso utente, sempre stesso risultato
context = EvaluationContext(
    targeting_key=user.id,              # UUID persistente nel DB, mai cambia
    attributes={"plan": "enterprise"}
)

# ❌ Targeting key volatile — diversa ad ogni sessione
context = EvaluationContext(
    targeting_key=request.session_id,   # Nuovo ad ogni login / scadenza sessione
    attributes={"plan": "enterprise"}
)

# ❌ Nessuna targeting key — l'SDK usa random o hostname
context = EvaluationContext(attributes={"plan": "enterprise"})
```

**Verifica:**
```bash
# Testare la valutazione dello stesso userId più volte — deve essere identica
for i in {1..5}; do
  curl -s -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/evaluation/boolean \
    -d '{"flag_key": "new-feature", "entity_id": "user-12345"}' \
    | jq .enabled
done
# Tutti i risultati devono essere uguali
```

## Relazioni

??? info "Deployment Strategies — Combinazione con Feature Flags"
    Feature flags e deployment strategies si complementano: la deployment strategy (blue/green, canary) controlla **come il codice va in produzione a livello infrastrutturale**, mentre i feature flags controllano **chi vede la funzionalità a livello applicativo**. I canary release possono essere pilotati interamente via feature flags senza rollout infrastrutturale, oppure i due meccanismi si combinano per un controllo a doppio livello.

    **Approfondimento →** [Deployment Strategies](./deployment-strategies.md)

??? info "Trunk-Based Development — Feature Flags come abilitatore"
    Senza feature flags, TBD è praticabile solo per modifiche complete e non rischiose. Con i feature flags, qualsiasi work-in-progress può arrivare nel trunk senza rischio per la produzione: il codice incompleto viene deployato ma rimane inattivo. Feature flags e TBD sono quasi inseparabili nelle organizzazioni ad alto ritmo di delivery.

    **Approfondimento →** [Trunk-Based Development](./trunk-based-development.md)

??? info "ArgoCD / GitOps — Flag come Infrastructure as Code"
    I flag possono essere definiti in YAML e gestiti via GitOps, con ArgoCD o Flux che riconciliano lo stato del flag store. Questo porta audit trail Git, code review, e approvals agli stessi flag che controllano il comportamento in produzione — lo stesso principio "Git as source of truth" applicato alla configurazione dei flag.

    **Approfondimento →** [ArgoCD](../gitops/argocd.md)

## Riferimenti

- [Feature Toggles (aka Feature Flags)](https://martinfowler.com/articles/feature-toggles.html) — Pete Hodgson / Martin Fowler — articolo fondamentale sulla tassonomia dei flag
- [OpenFeature](https://openfeature.dev/) — standard CNCF vendor-neutral, documentazione SDK per tutti i linguaggi
- [Flipt Docs](https://www.flipt.io/docs) — feature flag server open source self-hosted, supporta gRPC e OpenFeature
- [Unleash Docs](https://docs.getunleash.io/) — piattaforma open source con self-hosted enterprise e SaaS
- [LaunchDarkly Docs](https://docs.launchdarkly.com/) — soluzione SaaS enterprise con analytics avanzati e experimentation
- [CNCF Feature Flags Landscape](https://landscape.cncf.io/?category=feature-flag-management) — panoramica tool nel CNCF landscape
- [Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) — Martin Fowler — pattern per refactoring con feature flags
