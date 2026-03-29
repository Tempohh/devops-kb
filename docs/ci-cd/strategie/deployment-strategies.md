---
title: "Strategie di Deployment"
slug: deployment-strategies
category: ci-cd
tags: [deployment, blue-green, canary, rolling, feature-flags, progressive-delivery, a-b-testing]
search_keywords: [blue green deployment, canary deployment, rolling update, feature flags, progressive delivery, deployment strategy, a/b testing deployment, recreate deployment, shadow deployment, dark launch, launchdarkly, flipt, flagger canary, argo rollouts canary]
parent: ci-cd/strategie/_index
related: [ci-cd/strategie/_index, ci-cd/gitops/argocd, ci-cd/gitops/flux, containers/kubernetes/_index]
official_docs: https://argo-rollouts.readthedocs.io/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# Strategie di Deployment

## Panoramica

Una strategia di deployment definisce come una nuova versione del software viene portata in produzione, bilanciando velocità, rischio e impatto sugli utenti. Non esiste una strategia universalmente superiore: la scelta dipende dal tipo di applicazione, dalla tolleranza al rischio, dalla disponibilità di infrastruttura ridondante e dalla maturità del monitoring. Questa guida copre tutte le strategie principali con implementazioni concrete su Kubernetes, Argo Rollouts e Flagger.

## 1. Recreate (Ricreazione)

La strategia più semplice: termina tutti i pod della versione vecchia, poi crea i pod della versione nuova. Comporta un periodo di **downtime**.

```yaml
# Kubernetes Deployment con strategia Recreate
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 3
  strategy:
    type: Recreate          # Termina tutto, poi ricrea
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:v2.0.0
```

**Quando usarla:**
- Ambienti di sviluppo e test (downtime accettabile)
- Applicazioni con singola istanza (es. CronJob, batch processing)
- Quando la nuova versione è incompatibile con la vecchia (schema DB breaking change) e si accetta la finestra di manutenzione
- Applicazioni che non supportano running di versioni multiple in parallelo

**Quando NON usarla:** Applicazioni production con SLA di disponibilità.

## 2. Rolling Update

Il default di Kubernetes. Sostituisce i pod gradualmente, mantenendo sempre una percentuale di pod in esecuzione.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2           # Max 2 pod extra (oltre i 10 desiderati): fino a 12 pod
      maxUnavailable: 1     # Max 1 pod non disponibile: almeno 9 pod sempre up
      # Valori percentuali sono supportati:
      # maxSurge: 20%
      # maxUnavailable: 10%
  minReadySeconds: 30       # Pod deve essere ready per 30s prima di procedere
  progressDeadlineSeconds: 600  # Fallisce se non completa in 10 minuti
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:v2.0.0
          readinessProbe:           # FONDAMENTALE per rolling update sicuro
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
```

**Rischi con Rolling Update:**
- **Backward compatibility**: durante il rollout, versione V1 e V2 sono in esecuzione contemporaneamente. Le API devono essere backward-compatible (mai rimuovere field in un singolo deploy).
- **Database migrations**: le migration devono essere compatibili con entrambe le versioni (expand-contract pattern: prima si aggiunge il nuovo schema mantenendo quello vecchio, poi si migrano i dati, poi si rimuove il vecchio schema in un deploy successivo).
- Se la readinessProbe non è configurata, Kubernetes non sa quando il pod è davvero pronto e può mandare traffico a pod non funzionanti.

## 3. Blue-Green

Mantiene due ambienti identici (Blue = versione corrente, Green = nuova versione). Lo switch del traffico è istantaneo, il rollback è immediato.

```
                    ┌─────────────────┐
    Utenti ────────►│   Load Balancer  │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   BLUE (v1.0)   │           │   GREEN (v2.0)  │
    │   (live)        │           │   (standby)     │
    │   3 pod         │           │   3 pod         │
    └─────────────────┘           └─────────────────┘
```

### Implementazione con Kubernetes Service Selector

```yaml
# Deployment Blue (versione corrente)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: blue
  template:
    metadata:
      labels:
        app: myapp
        version: blue
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:v1.0.0

---
# Deployment Green (nuova versione)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: green
  template:
    metadata:
      labels:
        app: myapp
        version: green
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:v2.0.0

---
# Service: switcha tra blue e green modificando il selector
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    version: blue    # ← Cambia in "green" per switchare il traffico
  ports:
    - port: 80
      targetPort: 8080
```

```bash
# Script di switch Blue-Green
CURRENT=$(kubectl get svc myapp -o jsonpath='{.spec.selector.version}')
if [ "$CURRENT" = "blue" ]; then
  NEW="green"
else
  NEW="blue"
fi

echo "Switching da $CURRENT a $NEW"

# Test del nuovo deployment
kubectl run test-pod --image=curlimages/curl --rm -it --restart=Never -- \
  curl http://myapp-$NEW.default.svc.cluster.local/health

# Switch del traffico
kubectl patch svc myapp \
  -p "{\"spec\":{\"selector\":{\"version\":\"$NEW\"}}}"

echo "Switch completato. Rollback: patch svc con version: $CURRENT"
```

### Blue-Green con Argo Rollouts

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
spec:
  replicas: 5
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: myapp
          image: ghcr.io/my-org/myapp:v2.0.0
          ports:
            - containerPort: 8080

  strategy:
    blueGreen:
      activeService: myapp-active          # Service che riceve traffico live
      previewService: myapp-preview        # Service per test pre-switch
      autoPromotionEnabled: false          # Richiede approvazione manuale
      scaleDownDelaySeconds: 600           # Mantieni il vecchio deployment per 10 min (rollback rapido)
      prePromotionAnalysis:               # Test automatici prima della promozione
        templates:
          - templateName: smoke-test-analysis
      postPromotionAnalysis:              # Verifica post-switch
        templates:
          - templateName: error-rate-check
```

```bash
# Comandi Argo Rollouts CLI
kubectl argo rollouts get rollout myapp --watch
kubectl argo rollouts promote myapp     # Promuovi il green a active
kubectl argo rollouts abort myapp       # Aborta e rollback
```

**Pro:** Rollback in secondi (solo modifica del Service selector), zero downtime, ambiente identico testato prima dello switch.
**Contro:** Costo doppio dell'infrastruttura durante il rollout, switching di connessioni stateful può essere problematico.

## 4. Canary

Distribuisce la nuova versione a un sottoinsieme di utenti, aumentando gradualmente la percentuale mentre si monitorano le metriche. Il rollback automatico viene triggherato se le metriche degradano.

```
100% traffico         90%/10%            50%/50%           0%/100%
┌────────────┐       ┌──────────┐       ┌──────────┐      ┌─────────────┐
│  v1.0 (10) │  →   │v1(9)/v2(1)│  →   │v1(5)/v2(5)│ →  │  v2.0 (10)  │
└────────────┘       └──────────┘       └──────────┘      └─────────────┘
```

### Canary con NGINX Ingress Controller

```yaml
# Ingress principale (v1)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-stable
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp-stable
                port:
                  number: 80

---
# Ingress canary (v2) con weight
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"    # 10% del traffico
    # Oppure canary per header (test mirati):
    # nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
    # nginx.ingress.kubernetes.io/canary-by-header-value: "true"
    # Oppure canary per cookie:
    # nginx.ingress.kubernetes.io/canary-by-cookie: "canary-cookie"
spec:
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp-canary
                port:
                  number: 80
```

```bash
# Aggiornare il peso del canary progressivamente
kubectl annotate ingress myapp-canary \
  nginx.ingress.kubernetes.io/canary-weight="25" \
  --overwrite

kubectl annotate ingress myapp-canary \
  nginx.ingress.kubernetes.io/canary-weight="50" \
  --overwrite

# Deploy completo: disabilita canary, aggiorna stable
kubectl annotate ingress myapp-canary \
  nginx.ingress.kubernetes.io/canary="false" \
  --overwrite
```

### Canary con Argo Rollouts e AnalysisTemplate

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
spec:
  replicas: 10
  strategy:
    canary:
      stableService: myapp-stable
      canaryService: myapp-canary
      trafficRouting:
        nginx:
          stableIngress: myapp-stable
      steps:
        - setWeight: 5                    # 5% traffico
        - pause: {duration: 2m}
        - analysis:
            templates:
              - templateName: error-rate
        - setWeight: 20
        - pause: {duration: 5m}
        - analysis:
            templates:
              - templateName: error-rate
              - templateName: latency-p99
        - setWeight: 50
        - pause: {duration: 10m}
        - analysis:
            templates:
              - templateName: error-rate
              - templateName: latency-p99
              - templateName: saturation
        - setWeight: 100

---
# AnalysisTemplate con query Prometheus
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: error-rate
spec:
  args:
    - name: service-name
  metrics:
    - name: error-rate
      interval: 1m
      count: 5                         # Misura 5 volte
      successCondition: result[0] <= 0.02   # Max 2% errori
      failureLimit: 2                  # Fallisce dopo 2 misurazioni fallite
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(http_requests_total{
              service="{{ args.service-name }}",
              status=~"5.."
            }[2m]))
            /
            sum(rate(http_requests_total{
              service="{{ args.service-name }}"
            }[2m]))
```

## 5. Feature Flags

I feature flag separano il deployment del codice dalla release di funzionalità agli utenti. Il codice viene deployato in produzione ma la feature è nascosta finché non viene attivata.

```
Deploy ─────────────────────────────────────────────────►
         │ codice v2 in prod,       │ feature attivata
         │ feature disabilitata     │ per tutti
         ▼                          ▼
Release ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─►
```

### Tipi di Feature Flag

| Tipo | Scopo | Durata | Esempio |
|------|-------|--------|---------|
| **Release flag** | Nasconde feature incompleta | Giorni/settimane | Nuovo dashboard, riattivato al completamento |
| **Experiment flag** | A/B test per dati business | Settimane/mesi | Variante UI A vs B |
| **Ops flag** | Circuit breaker operativo | Indefinita | Kill switch per feature costosa |
| **Permission flag** | Accesso per segmenti utenti | Indefinita | Feature solo per utenti premium |

### OpenFeature — Standard Vendor-Neutral

```java
// Integrazione OpenFeature (Java)
import dev.openfeature.sdk.*;

// Configurare il provider (Flipt, flagd, LaunchDarkly, Unleash...)
OpenFeatureAPI api = OpenFeatureAPI.getInstance();
api.setProvider(new FliptProvider(
    FliptProviderConfig.newBuilder()
        .host("https://flipt.mycompany.internal")
        .build()
));

Client client = api.getClient("my-service");

// Uso nel codice
EvaluationContext ctx = new ImmutableContext(
    Map.of(
        "userId", new Value("user-12345"),
        "email", new Value("user@example.com"),
        "plan", new Value("enterprise")
    )
);

boolean newCheckoutEnabled = client.getBooleanValue(
    "new-checkout-flow",   // Nome del flag
    false,                  // Default (fallback se provider non raggiungibile)
    ctx
);

if (newCheckoutEnabled) {
    return newCheckoutService.process(order);
} else {
    return legacyCheckoutService.process(order);
}
```

### Flipt — Self-Hosted Feature Flag Server

```yaml
# docker-compose.yml per Flipt
version: '3.8'
services:
  flipt:
    image: flipt/flipt:v1.39.0
    ports:
      - "8080:8080"    # UI e REST API
      - "9000:9000"    # gRPC
    environment:
      FLIPT_DB_URL: "postgres://flipt:flipt@postgres:5432/flipt?sslmode=disable"
      FLIPT_CACHE_ENABLED: "true"
      FLIPT_CACHE_TTL: "60s"
    volumes:
      - flipt-data:/var/opt/flipt
    depends_on:
      - postgres

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: flipt
      POSTGRES_USER: flipt
      POSTGRES_PASSWORD: flipt
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  flipt-data:
  postgres-data:
```

```bash
# Creare un flag via Flipt API
curl -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/flags \
  -H "Content-Type: application/json" \
  -d '{
    "key": "new-checkout-flow",
    "name": "New Checkout Flow",
    "description": "Nuovo flusso di checkout con Apple Pay",
    "enabled": true,
    "type": "BOOLEAN_FLAG_TYPE"
  }'

# Creare una rollout rule (attiva per 10% degli utenti)
curl -X POST https://flipt.mycompany.internal/api/v1/namespaces/default/flags/new-checkout-flow/rollouts \
  -H "Content-Type: application/json" \
  -d '{
    "rank": 1,
    "threshold": {
      "percentage": 10.0,
      "value": true
    }
  }'
```

### Feature Flag con LaunchDarkly (SaaS)

```python
# Python SDK LaunchDarkly
import ldclient
from ldclient.config import Config

ldclient.set_config(Config("sdk-your-sdk-key"))

client = ldclient.get()

# Valutazione del flag con contesto utente
context = ldclient.Context.builder("user-12345") \
    .set("email", "user@example.com") \
    .set("plan", "enterprise") \
    .set("country", "IT") \
    .build()

show_new_feature = client.variation("new-feature", context, False)

if show_new_feature:
    # Nuova implementazione
    pass
else:
    # Implementazione legacy
    pass

# Track evento per A/B testing
client.track("checkout-completed", context, metric_value=order.total)
```

## 6. A/B Testing vs Canary

| Aspetto | Canary Deployment | A/B Testing |
|---------|------------------|-------------|
| **Obiettivo** | Stabilità tecnica (errori, latenza) | Metriche di business (conversion, engagement) |
| **Rollback trigger** | Errori tecnici (5xx, latenza alta) | Metriche business (conversion rate bassa) |
| **Durata** | Ore/giorni | Giorni/settimane (significatività statistica) |
| **Segmentazione** | Casuale (% traffico) | Casuale o targetizzata (es. utenti mobile) |
| **Metriche** | Error rate, latency, saturation | Click-through rate, conversion, revenue |
| **Tool** | Argo Rollouts, Flagger, NGINX | Feature flags (LaunchDarkly, Flipt), Optimizely |
| **Decisione finale** | Automatica (se metriche OK) | Statistica (A/B test significance) |

```yaml
# A/B Test con Istio e Feature Flag combinati
# - Il traffico viene splittato via Istio VirtualService
# - La metrica di business viene raccolta nel codice
# - La decisione viene presa dopo analisi statistica

apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts:
    - myapp.example.com
  http:
    - match:
        - headers:
            x-user-segment:
              exact: "experiment-b"    # Header da feature flag
      route:
        - destination:
            host: myapp-variant-b
            port:
              number: 80
    - route:
        - destination:
            host: myapp-variant-a     # Controllo (variante A = default)
            port:
              number: 80
```

## 7. Shadow Deployment (Dark Launch)

Il shadow deployment replica il traffico in produzione verso la nuova versione, senza che gli utenti ricevano la risposta dalla nuova versione. Utile per testare performance e correttezza senza impatto.

```yaml
# Con Istio: mirroring del traffico
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts:
    - myapp.example.com
  http:
    - route:
        - destination:
            host: myapp-v1             # Risponde agli utenti reali
            port:
              number: 80
      mirror:
        host: myapp-v2               # Riceve copia del traffico (shadow)
        port:
          number: 80
      mirrorPercentage:
        value: 100.0                   # Replica il 100% del traffico (o meno)
```

!!! warning "Shadow e Idempotenza"
    Le richieste replicate in shadow vengono eseguite due volte sul backend. Assicurarsi che le operazioni non siano double-write (es. operazioni di scrittura su DB devono essere idempotenti o eseguite su un DB separato per il shadow).

## 8. Tabella Comparativa

| Strategia | Downtime | Costo Infra | Rollback | Complessità | Rischio | Indicato per |
|-----------|----------|-------------|----------|-------------|---------|--------------|
| **Recreate** | Sì | Basso (1x) | Lento | Minima | Alto | Dev/test, app batch |
| **Rolling Update** | No | Basso (1.2x) | Lento (re-roll) | Bassa | Medio | Applicazioni stateless standard |
| **Blue-Green** | No | Alto (2x) | Istantaneo | Media | Basso | App critiche, release pianificate |
| **Canary** | No | Basso (1.1x) | Automatico | Alta | Molto basso | Microservizi, alta frequenza deploy |
| **Feature Flags** | No | Basso | Istantaneo (toggle) | Alta (SDK) | Molto basso | Feature release decoupled dal deploy |
| **A/B Testing** | No | Basso | Instantaneo | Alta | Basso | Decisioni product, ottimizzazione UX |
| **Shadow** | No | Alto (2x) | N/A (non in prod) | Alta | Nessuno | Validazione pre-produzione |

**Raccomandazioni per contesto:**

| Contesto | Strategia raccomandata |
|----------|----------------------|
| Startup, app semplici | Rolling Update (default K8s) |
| E-commerce, fintech | Blue-Green + Feature Flags |
| Microservizi ad alto traffico | Canary con Argo Rollouts/Flagger |
| Release di feature significative | Feature Flags |
| Validazione ML model | Shadow Deployment |
| Database migration | Recreate in finestra + expand-contract |

## Troubleshooting

### Scenario 1 — Rolling Update bloccato in `Progressing`

**Sintomo:** Il deployment rimane in stato `Progressing` indefinitamente; alcuni pod restano in `Pending` o `CrashLoopBackOff`.

**Causa:** La readinessProbe fallisce (app non risponde entro `failureThreshold`), oppure il cluster non ha risorse sufficienti per i pod extra definiti da `maxSurge`.

**Soluzione:** Ispezionare i pod nuovi e i loro log; verificare le risorse disponibili nei nodi.

```bash
# Stato del rollout
kubectl rollout status deployment/myapp

# Dettaglio dei pod in stato anomalo
kubectl get pods -l app=myapp
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous

# Verifica risorse nodi
kubectl describe nodes | grep -A 5 "Allocated resources"

# Rollback immediato
kubectl rollout undo deployment/myapp

# Cronologia revisioni
kubectl rollout history deployment/myapp
```

---

### Scenario 2 — Blue-Green: il Service non switcha al nuovo deployment

**Sintomo:** Dopo aver modificato il selector del Service, il traffico continua ad arrivare ai pod della versione vecchia.

**Causa:** I pod del deployment Green non hanno il label corrispondente al selector aggiornato, oppure i pod Green non sono in stato `Ready`.

**Soluzione:** Verificare che i label dei pod Green corrispondano esattamente al selector del Service.

```bash
# Confronta selector del Service con label dei pod
kubectl get svc myapp -o jsonpath='{.spec.selector}'
kubectl get pods -l app=myapp,version=green --show-labels

# Verifica che i pod Green siano Ready
kubectl get pods -l version=green
kubectl describe endpoints myapp

# Se i pod non compaiono negli endpoint, controllare readinessProbe
kubectl describe pod <green-pod-name> | grep -A 10 "Readiness"

# Patch manuale del selector
kubectl patch svc myapp -p '{"spec":{"selector":{"app":"myapp","version":"green"}}}'
```

---

### Scenario 3 — Canary Argo Rollouts: AnalysisRun fallisce con errore Prometheus

**Sintomo:** Il Rollout si blocca o viene abortito con `AnalysisPhase: Error`; nei log compare `no data returned from Prometheus query`.

**Causa:** L'indirizzo Prometheus nell'AnalysisTemplate non è raggiungibile dal pod di analisi, oppure la query usa label non ancora presenti per la nuova versione (il canary ha ricevuto troppo poco traffico per generare metriche).

**Soluzione:** Verificare la connettività al server Prometheus e controllare che i metric label corrispondano al servizio canary.

```bash
# Stato del Rollout e degli AnalysisRun
kubectl argo rollouts get rollout myapp --watch
kubectl get analysisrun -l rollouts-pod-template-hash=<hash>
kubectl describe analysisrun <analysisrun-name>

# Test query Prometheus da dentro il cluster
kubectl run prom-test --image=curlimages/curl --rm -it --restart=Never -- \
  curl "http://prometheus.monitoring.svc.cluster.local:9090/api/v1/query?query=up"

# Ispeziona i log del controller Argo Rollouts
kubectl logs -n argo-rollouts deployment/argo-rollouts | grep -i error

# Annulla il rollout e torna alla versione stabile
kubectl argo rollouts abort myapp
kubectl argo rollouts undo myapp
```

---

### Scenario 4 — Feature Flag: il flag non viene valutato correttamente (fallback costante)

**Sintomo:** L'applicazione restituisce sempre il valore di default del flag, indipendentemente dalla configurazione sul server (Flipt, LaunchDarkly, ecc.).

**Causa:** Il provider non riesce a raggiungere il server dei feature flag (network policy, DNS, certificato), oppure la chiave SDK è errata. In failsafe mode, tutti i flag tornano al valore di default.

**Soluzione:** Verificare la connettività al server dei flag, il corretto caricamento della chiave SDK e le NetworkPolicy in Kubernetes.

```bash
# Verifica che il pod possa raggiungere il server Flipt
kubectl exec -it <app-pod> -- curl -v http://flipt.flipt.svc.cluster.local:8080/health

# Controlla i log dell'applicazione per errori di connessione al provider
kubectl logs <app-pod> | grep -i "feature\|flag\|flipt\|provider"

# Verifica le NetworkPolicy che potrebbero bloccare il traffico
kubectl get networkpolicy -A
kubectl describe networkpolicy <policy-name>

# Test diretto dell'API Flipt
curl -X GET http://flipt.mycompany.internal/api/v1/namespaces/default/flags/new-checkout-flow \
  -H "Authorization: Bearer <token>"

# Verifica che il Secret con la SDK key sia montato correttamente
kubectl get secret feature-flag-sdk-key -o jsonpath='{.data.key}' | base64 -d
```

## Relazioni

??? info "GitOps con ArgoCD"
    Argo Rollouts per canary e blue-green, integrazione con ArgoCD per progressive delivery GitOps-style.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

??? info "Flux con Flagger"
    Flagger come operator di progressive delivery integrato con Flux CD.

    **Approfondimento completo →** [Flux CD](../gitops/flux.md)

??? info "Strategie CI/CD"
    DORA metrics, principi di design pipeline, testing pyramid, environment promotion.

    **Approfondimento completo →** [Strategie CI/CD](_index.md)

## Riferimenti

- [Argo Rollouts documentation](https://argo-rollouts.readthedocs.io/)
- [Flagger documentation](https://docs.flagger.app/)
- [NGINX Canary annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/#canary)
- [OpenFeature specification](https://openfeature.dev/)
- [Flipt documentation](https://www.flipt.io/docs)
- [Istio Traffic Management](https://istio.io/latest/docs/tasks/traffic-management/)
- [Martin Fowler — Feature Toggles](https://martinfowler.com/articles/feature-toggles.html)
- [Google SRE — Release Engineering](https://sre.google/sre-book/release-engineering/)
