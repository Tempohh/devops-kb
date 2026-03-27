---
title: "Chaos Engineering"
slug: chaos-engineering
category: monitoring
tags: [sre, chaos-engineering, chaos-monkey, litmus-chaos, resilience, fault-injection, gameday, kubernetes]
search_keywords: [chaos engineering, ingegneria del caos, chaos monkey, chaos mesh, litmus chaos, litmus, gremlin, fault injection, iniezione guasti, fault tolerance, tolleranza ai guasti, resilience testing, test di resilienza, gameday, game day, steady state hypothesis, ipotesi di stato stabile, blast radius, raggio di esplosione, pod failure, network latency, latenza di rete, cpu stress, node drain, kill pod, pod kill, network partition, partizione di rete, failure mode, failure modes, failure scenarios, scenari di guasto, chaos experiment, esperimento chaos, chaos testing, mean time to recovery, mttr, dependency failure, cascading failure, fallimento a cascata, circuit breaker, disruption, service disruption, production chaos, netflix chaos, simian army, chaos gorilla, chaos kong]
parent: monitoring/sre/_index
related: [monitoring/sre/slo-sla-sli, monitoring/sre/incident-management, monitoring/sre/error-budget, containers/kubernetes/architettura, containers/kubernetes/workloads]
official_docs: https://principlesofchaos.org/
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# Chaos Engineering

## Panoramica

Il Chaos Engineering è la disciplina di sperimentare intenzionalmente sui sistemi in produzione (o in ambienti che la simulano fedelmente) per costruire fiducia nella loro capacità di resistere a condizioni turbolente. L'idea non è "rompere le cose a caso", ma condurre esperimenti scientifici controllati: definire uno stato stabile atteso (steady state), introdurre una variabile di fallimento, e osservare se il sistema mantiene quel stato. Nasce in Netflix nel 2011 con Chaos Monkey — uno strumento che terminava istanze EC2 casualmente in produzione per forzare il team a costruire sistemi resilienti. Va usato quando un team ha alta disponibilità e vuole verificare i propri failure modes prima che lo faccia la realtà. Non va usato come sostituto di una buona architettura o in assenza di monitoring, observability e runbook consolidati — il chaos rivela problemi, non li risolve.

## Concetti Chiave

### Steady State Hypothesis

La **steady state hypothesis** (ipotesi di stato stabile) è il cuore di ogni esperimento chaos. Prima di introdurre un guasto, si definisce con precisione come appare il sistema quando funziona correttamente — usando metriche misurabili, non descrizioni vaghe.

```
Steady State (esempio):
  ✓ HTTP success rate API checkout > 99.9%
  ✓ Latenza p99 < 500ms
  ✓ Pod "payment-service" in stato Running: 3/3 repliche
  ✓ Queue depth < 100 messaggi
  ✓ Nessun alert attivo su SLO-critical dashboard

L'esperimento è valido se:
  → il sistema torna allo steady state entro X minuti dopo il guasto
  → lo steady state non viene mai violato durante il guasto (ideale)
  → la violazione è limitata a metriche non-SLO-critical
```

!!! warning "Steady state senza metriche = esperimento inutile"
    Se non si definisce lo steady state in modo quantificabile prima di iniziare, non si può affermare se l'esperimento ha avuto successo o meno. "Il sistema funziona" non è uno steady state — "success rate > 99.5% su Prometheus" lo è.

### Blast Radius

Il **blast radius** (raggio di esplosione) è l'impatto massimo che un esperimento chaos può causare. Iniziare sempre con il blast radius minimo possibile e aumentarlo gradualmente man mano che si acquisisce fiducia.

```
Blast Radius Spectrum (dal più sicuro al più rischioso):

1. MINIMO    → 1 pod in un deployment (non-critical)
2. BASSO     → 1 nodo worker in un cluster (non-prod)
3. MEDIO     → 1 AZ completa (con feature flag disabilitato)
4. ALTO      → 1 servizio critico (con circuit breaker attivo)
5. MASSIMO   → Intera regione / database primario

Regola pratica: iniziare sempre da 1, mai saltare da 1 a 4.
```

### Principi del Chaos Engineering (Principlesofchaos.org)

I 5 principi fondamentali definiti dalla community:

1. **Costruire intorno allo steady state** — misurare l'output del sistema, non i dettagli interni
2. **Variare le condizioni del mondo reale** — usare eventi reali (picchi di traffico, fallimenti noti) come ispirazione
3. **Eseguire esperimenti in produzione** — staging non replica mai il comportamento reale in modo completo
4. **Automatizzare gli esperimenti continuamente** — il chaos una-tantum non vale, deve essere ricorrente
5. **Minimizzare il blast radius** — iniziare piccolo, espandere solo con evidenza

## Architettura / Come Funziona

### Flusso di un Esperimento Chaos

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO ESPERIMENTO CHAOS                       │
│                                                                   │
│  1. IPOTESI         2. SCOPE            3. ESECUZIONE            │
│  ──────────         ──────────          ──────────────            │
│  Steady state?      Blast radius?       Inietta guasto            │
│  Cosa si rompe?     Ambiente?           Monitora metriche         │
│  Perché?            Rollback plan?      Misura deviazione         │
│        │                 │                    │                   │
│        ▼                 ▼                    ▼                   │
│  4. OSSERVAZIONE    5. ANALISI          6. AZIONE                 │
│  ───────────────    ──────────          ──────────                 │
│  Steady state OK?   Fallimenti?         Fix vulnerabilità         │
│  Alert scattati?    Latenza aumentata?  Aggiorna runbook          │
│  Recovery time?     Cascading effects?  Aggiungi circuit breaker  │
│                                         Pianifica prossimo exp.   │
└─────────────────────────────────────────────────────────────────┘
```

### Tipologie di Guasti (Failure Scenarios)

| Categoria | Scenario | Strumento | Impatto atteso |
|-----------|----------|-----------|----------------|
| **Resource** | CPU stress | Litmus, Gremlin | Degradazione performance |
| **Resource** | Memory pressure | Litmus, Chaos Mesh | OOMKilled, restart loop |
| **Network** | Latenza artificiale | Litmus, tc netem | Timeout, retry storm |
| **Network** | Perdita pacchetti | Litmus, tc netem | Errori intermittenti |
| **Network** | Partizione di rete | Chaos Mesh | Split brain, failover |
| **Pod/Node** | Pod kill casuale | Chaos Monkey, Litmus | Riavvio, disruption temporanea |
| **Pod/Node** | Node drain | kubectl, Litmus | Rescheduling, PDB test |
| **Pod/Node** | Container OOMKill | Litmus | Restart, backoff |
| **Dipendenze** | Database latency | Gremlin, Litmus | Timeout applicazione |
| **Dipendenze** | External API failure | Gremlin, WireMock | Fallback, degraded mode |
| **Infrastruttura** | AZ failure simulation | Chaos Monkey, AWS FIS | Multi-AZ failover |

### Ecosistema degli Strumenti

```
┌─────────────────────────────────────────────────────┐
│              CHAOS ENGINEERING TOOLS                  │
│                                                       │
│  ┌──────────────────────┐  ┌──────────────────────┐  │
│  │   CHAOS MONKEY       │  │   LITMUS CHAOS        │  │
│  │   (Netflix/OSS)      │  │   (CNCF)              │  │
│  │                      │  │                       │  │
│  │   • Termina EC2/VM   │  │   • Kubernetes-native │  │
│  │   • Spanner, DDB     │  │   • ChaosExperiment   │  │
│  │   • Janitor Monkey   │  │   • Hub experiments   │  │
│  │   • Conformity Mon.  │  │   • Litmus Portal     │  │
│  └──────────────────────┘  └──────────────────────┘  │
│                                                       │
│  ┌──────────────────────┐  ┌──────────────────────┐  │
│  │   CHAOS MESH         │  │   AWS FIS / Gremlin   │  │
│  │   (CNCF Sandbox)     │  │   (Commercial/Cloud)  │  │
│  │                      │  │                       │  │
│  │   • K8s network      │  │   • AWS-native FIS    │  │
│  │   • Time skew        │  │   • Scenario GUI      │  │
│  │   • StressChaos      │  │   • Team features     │  │
│  │   • Dashboard web    │  │   • Scheduling auto   │  │
│  └──────────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Configurazione & Pratica

### Litmus Chaos — Installazione su Kubernetes

```bash
# Installazione Litmus ChaosCenter (control plane)
kubectl apply -f https://litmuschaos.github.io/litmus/litmus-operator-v3.0.0.yaml

# Verifica installazione
kubectl get pods -n litmus
# NAME                                    READY   STATUS    RESTARTS   AGE
# chaos-operator-ce-6d6fc96464-nfwbd      1/1     Running   0          2m
# chaos-exporter-6c4b775d55-69lpv         1/1     Running   0          2m

# Installazione RBAC per namespace target
kubectl apply -f https://hub.litmuschaos.io/api/chaos/3.0.0?file=charts/generic/pod-delete/rbac.yaml \
  -n production

# Verifica ServiceAccount
kubectl get serviceaccount litmus -n production
```

```yaml
# ChaosEngine: Pod Delete Experiment
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: pod-delete-engine
  namespace: production
spec:
  appinfo:
    appns:    production
    applabel: "app=payment-service"
    appkind:  deployment

  # Azione post-esperimento: delete (pulisce le risorse chaos)
  jobCleanUpPolicy: delete

  # ServiceAccount con permessi chaos
  chaosServiceAccount: litmus

  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            # Quanti pod eliminare in ogni round
            - name: TOTAL_CHAOS_DURATION
              value: "30"           # secondi di chaos
            - name: CHAOS_INTERVAL
              value: "10"           # secondi tra un kill e l'altro
            - name: FORCE
              value: "false"        # false = SIGTERM (graceful), true = SIGKILL
            - name: PODS_AFFECTED_PERC
              value: "50"           # % dei pod del deployment da killare
```

### Litmus Chaos — Network Latency

```yaml
# ChaosEngine: Network Latency su servizio specifico
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: pod-network-latency-engine
  namespace: production
spec:
  appinfo:
    appns:    production
    applabel: "app=api-gateway"
    appkind:  deployment
  chaosServiceAccount: litmus
  experiments:
    - name: pod-network-latency
      spec:
        components:
          env:
            - name: TARGET_CONTAINER
              value: "api-gateway"
            - name: NETWORK_INTERFACE
              value: "eth0"
            - name: NETWORK_LATENCY
              value: "2000"         # millisecondi di latenza artificiale
            - name: JITTER
              value: "100"          # variazione random ±100ms (simula latenza reale)
            - name: TOTAL_CHAOS_DURATION
              value: "60"           # secondi
            - name: PODS_AFFECTED_PERC
              value: "50"           # solo metà dei pod (riduce blast radius)
            - name: DESTINATION_IPS  # opzionale: solo verso questo IP
              value: ""             # vuoto = tutto il traffico
            - name: DESTINATION_HOSTS
              value: "postgres.production.svc.cluster.local"
```

### Litmus Chaos — CPU Stress

```yaml
# ChaosEngine: CPU Stress
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: pod-cpu-hog-engine
  namespace: production
spec:
  appinfo:
    appns:    production
    applabel: "app=worker-service"
    appkind:  deployment
  chaosServiceAccount: litmus
  experiments:
    - name: pod-cpu-hog
      spec:
        components:
          env:
            - name: TARGET_CONTAINER
              value: "worker"
            - name: CPU_CORES
              value: "1"            # quanti core monopolizzare
            - name: CPU_LOAD
              value: "80"           # % di utilizzo del core (80% simula alta load)
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: PODS_AFFECTED_PERC
              value: "50"
```

### Node Drain Chaos

```bash
# Simulazione manuale node drain (utile per verificare PodDisruptionBudget)
# 1. Identifica un nodo worker non-critical
kubectl get nodes
# NAME                STATUS   ROLES    AGE   VERSION
# node-worker-1       Ready    <none>   30d   v1.28.0
# node-worker-2       Ready    <none>   30d   v1.28.0

# 2. Drain del nodo (evita di drainare control plane)
kubectl drain node-worker-1 \
  --ignore-daemonsets \    # ignora DaemonSet (non possono essere rischedulati)
  --delete-emptydir-data \ # elimina emptyDir (dati effimeri)
  --grace-period=30        # 30 secondi per shutdown graceful

# 3. Verifica rescheduling dei pod
kubectl get pods -n production -o wide | grep node-worker-1
# → atteso: nessun pod su node-worker-1 dopo il drain

# 4. Verifica steady state
kubectl get pods -n production
# → tutti i pod devono essere Running/Ready senza interruzioni significative

# 5. Restore del nodo
kubectl uncordon node-worker-1
```

```yaml
# PodDisruptionBudget — prerequisito per testare node drain in sicurezza
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-service-pdb
  namespace: production
spec:
  minAvailable: 2           # minimo 2 repliche always available durante disruption
  selector:
    matchLabels:
      app: payment-service
```

### Chaos Monkey — Setup (Netflix OSS)

```bash
# Chaos Monkey è un'applicazione Spring Boot — deploy come sidecar o job
# Configurazione tramite properties

# application-chaos.yml
chaos:
  monkey:
    enabled: true
    watcher:
      component:     true
      controller:    true
      restController: true
      service:       true
    assaults:
      level: 1                  # 1-10, frequenza degli attacchi (1=1 req su 1000)
      latencyActive: true
      latencyRangeStart: 1000   # ms
      latencyRangeEnd: 3000     # ms
      exceptionsActive: false   # non abilitare in produzione inizialmente
      killApplicationActive: false

# Attivazione via Actuator endpoint
curl -X POST http://localhost:8080/actuator/chaosmonkey/enable \
  -H "Content-Type: application/json"

# Verifica stato
curl http://localhost:8080/actuator/chaosmonkey/status
```

### Monitoring durante gli Esperimenti

```bash
# Dashboard da tenere aperte durante un esperimento:
# 1. Grafana SLO dashboard (steady state check)
# 2. Kubernetes events in real time

# Monitor events Kubernetes live
kubectl get events -n production --watch --sort-by='.lastTimestamp'

# Monitor metriche Prometheus con watch
watch -n5 "curl -s 'http://prometheus:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{status=~\"5..\",namespace=\"production\"}[1m]))/sum(rate(http_requests_total{namespace=\"production\"}[1m]))*100' \
  | jq -r '.data.result[0].value[1]'"

# Alert Prometheus per chaos experiments (utile per rilevare regressioni)
# In rules.yaml:
groups:
  - name: chaos-steady-state
    rules:
      - alert: ChaosExperimentSLOViolation
        expr: |
          sum(rate(http_requests_total{status=~"5..",namespace="production"}[1m]))
          /
          sum(rate(http_requests_total{namespace="production"}[1m])) > 0.001
        for: 1m
        labels:
          severity: warning
          context: chaos-experiment
        annotations:
          summary: "Chaos experiment: SLO violato - error rate {{ $value | humanizePercentage }}"
```

## Best Practices

### GameDay — Esercitazione Strutturata

Un **GameDay** è una sessione pianificata in cui il team esegue esperimenti chaos in modo coordinato, spesso con scenari più complessi di quelli automatizzati. Simula incidenti reali in ambiente controllato.

```
Struttura di un GameDay (durata tipica: 2-4 ore):

PRE-GAMEDAY (1 settimana prima):
  □ Definire 2-4 scenari da testare
  □ Documentare lo steady state per ogni scenario
  □ Preparare rollback plan esplicito
  □ Comunicare a stakeholder (no sorprese per il supporto)
  □ Verificare che monitoring sia operativo

DURANTE IL GAMEDAY:
  □ Un facilitatore coordina (come IC in incident management)
  □ Uno scribe documenta osservazioni in real time
  □ Eseguire scenari in ordine di blast radius crescente
  □ Dichiarare STOP se SLO viene violato oltre la soglia
  □ Osservare: tempi di recovery, alert scattati, comportamenti inattesi

POST-GAMEDAY (entro 48 ore):
  □ Retrospettiva: cosa ha funzionato, cosa no
  □ Creare ticket per ogni vulnerabilità scoperta
  □ Aggiornare runbook con i comportamenti osservati
  □ Pianificare il prossimo GameDay (cadenza: trimestrale)
```

!!! tip "Inizia con un chaos piccolo, non un GameDay"
    Prima del primo GameDay, esegui almeno 3-4 esperimenti singoli automatizzati in staging o production-like. Il GameDay presuppone che il team abbia già esperienza con chaos e sia in grado di reagire rapidamente.

### Automazione Continua con Litmus Workflows

```yaml
# LitmusChaos Workflow: Scheduled weekly chaos
apiVersion: argoproj.io/v1alpha1
kind: CronWorkflow
metadata:
  name: weekly-pod-delete-chaos
  namespace: litmus
spec:
  schedule: "0 10 * * 2"   # Ogni martedì alle 10:00 (orario business)
  timezone: "Europe/Rome"
  workflowSpec:
    entrypoint: chaos-workflow
    templates:
      - name: chaos-workflow
        steps:
          - - name: run-chaos
              template: pod-delete-chaos
          - - name: verify-steady-state
              template: steady-state-check

      - name: pod-delete-chaos
        resource:
          action: create
          manifest: |
            apiVersion: litmuschaos.io/v1alpha1
            kind: ChaosEngine
            metadata:
              name: weekly-pod-delete
              namespace: production
            spec:
              appinfo:
                appns: production
                applabel: "app=api-gateway"
                appkind: deployment
              chaosServiceAccount: litmus
              experiments:
                - name: pod-delete
                  spec:
                    components:
                      env:
                        - name: TOTAL_CHAOS_DURATION
                          value: "30"
                        - name: PODS_AFFECTED_PERC
                          value: "33"  # 1 pod su 3

      - name: steady-state-check
        script:
          image: curlimages/curl:latest
          command: [sh]
          source: |
            # Verifica error rate < 0.1% dopo il chaos
            RATE=$(curl -s 'http://prometheus.monitoring:9090/api/v1/query' \
              --data-urlencode 'query=sum(rate(http_requests_total{status=~"5.."}[5m]))/sum(rate(http_requests_total[5m]))*100' \
              | grep -o '"[0-9.]*"' | tail -1 | tr -d '"')
            echo "Current error rate: $RATE%"
            if [ $(echo "$RATE > 0.1" | bc -l) -eq 1 ]; then
              echo "STEADY STATE VIOLATED"
              exit 1
            fi
            echo "Steady state maintained"
```

### Chaos con Circuit Breaker

!!! warning "Chaos senza circuit breaker = chaos distruttivo"
    Se il sistema non ha circuit breaker o retry con backoff esponenziale sui servizi dipendenti, un pod failure può causare una cascata di errori che si propagano a tutta la call chain. Verificare che i pattern di resilienza siano implementati PRIMA di eseguire failure injection su servizi critici.

```yaml
# Esempio: circuit breaker Kubernetes-native tramite Istio VirtualService
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: payment-service-cb
spec:
  host: payment-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        h2UpgradePolicy: UPGRADE
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
    outlierDetection:
      consecutive5xxErrors: 5         # 5 errori 5xx consecutivi → eject
      interval: 30s                   # finestra di valutazione
      baseEjectionTime: 30s           # durata eject iniziale
      maxEjectionPercent: 50          # max 50% degli endpoint ejected
```

### Metriche da Tracciare per gli Esperimenti

```
KPI di un programma Chaos Engineering maturo:

1. Recovery Time per tipo di failure
   → Pod delete: < 30s per Kubernetes (con readinessProbe)
   → Node drain: < 2 min con PDB correttamente configurato
   → Network latency: steady state mantenuto (retry + timeout)

2. Mean Time to Detect (durante chaos)
   → I tuoi alert hanno rilevato il chaos in < 5 min?
   → Se no: alert mancanti o threshold troppo alti

3. % Esperimenti Superati
   → Baseline iniziale: 40-60% (normale trovare vulnerability)
   → Target dopo 6 mesi: > 80% degli esperimenti superati

4. Vulnerabilità trovate → ticket risolti
   → Ogni chaos experiment che fallisce deve produrre un ticket
   → Tracciare tempo medio di risoluzione vulnerabilità chaos
```

## Troubleshooting

### Esperimento Chaos Non Termina

**Sintomo:** Un ChaosEngine rimane in stato `Running` indefinitamente, anche dopo il timeout.

**Causa:** Il chaos runner job è in crash loop o non riesce a connettersi all'API server Kubernetes. Spesso un problema di RBAC o di network policy.

**Soluzione:**

```bash
# Verifica stato ChaosEngine
kubectl describe chaosengine pod-delete-engine -n production
# Cercare Events alla fine dell'output

# Verifica che il chaos runner job sia in esecuzione
kubectl get jobs -n production | grep pod-delete
kubectl logs job/pod-delete-chaos-runner -n production

# RBAC: verifica che il ServiceAccount abbia i permessi necessari
kubectl auth can-i delete pods -n production \
  --as=system:serviceaccount:production:litmus
# Risposta attesa: yes

# Se "no": applicare RBAC corretto
kubectl apply -f https://hub.litmuschaos.io/api/chaos/3.0.0?file=charts/generic/pod-delete/rbac.yaml -n production

# Cleanup manuale di un ChaosEngine bloccato
kubectl patch chaosengine pod-delete-engine -n production \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/engineState", "value": "stop"}]'
```

### Il Sistema Non Si Riprende dopo il Chaos

**Sintomo:** Dopo la fine dell'esperimento, il sistema rimane in stato degradato — pod in CrashLoopBackOff, metriche non tornano allo steady state.

**Causa:** Dependency esterna non raggiungibile (connessione DB persa), readiness probe fallisce per un check non idempotente, o il guasto ha esposto un bug latente.

**Soluzione:**

```bash
# 1. Identifica i pod non Running
kubectl get pods -n production | grep -v Running
# NAME                          READY   STATUS             RESTARTS   AGE
# payment-svc-7c9f9b7d4-xk2pq   0/1     CrashLoopBackOff   5          3m

# 2. Leggi i log dell'ultimo crash
kubectl logs -n production payment-svc-7c9f9b7d4-xk2pq --previous

# 3. Controlla gli eventi Kubernetes
kubectl describe pod -n production payment-svc-7c9f9b7d4-xk2pq | tail -20

# 4. Verifica connessione al database (spesso il vero problema)
kubectl exec -it payment-svc-7c9f9b7d4-xk2pq -n production -- \
  nc -zv postgres.production.svc.cluster.local 5432
# → se fallisce: connessione DB interrotta dal chaos di rete

# 5. Rollback di emergenza se bug scoperto
kubectl rollout undo deployment/payment-service -n production
kubectl rollout status deployment/payment-service -n production
```

### Chaos Causa Cascading Failure Inatteso

**Sintomo:** Un pod delete su servizio A causa la caduta di servizi B e C (non target del chaos).

**Causa:** Mancanza di circuit breaker, timeout non configurati, o dipendenze sincrone non documentate.

**Azioni immediate:**

```bash
# 1. Attivare il rollback del chaos se ancora in corso
kubectl patch chaosengine pod-delete-engine -n production \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/engineState", "value": "stop"}]'

# 2. Scalare temporaneamente i servizi impattati
kubectl scale deployment/service-b -n production --replicas=5
kubectl scale deployment/service-c -n production --replicas=5

# 3. Verifica dependency graph
kubectl get endpoints -n production  # quali servizi hanno endpoint attivi?

# 4. Documenta la cascata → creare issue alta priorità
# Il cascading failure è informazione preziosa:
# rivela dipendenze nascoste che devono essere protette con retry + circuit breaker
```

### Alert Non Scattano durante il Chaos

**Sintomo:** Si esegue pod delete su 2/3 dei pod di un servizio critico ma nessun alert si attiva.

**Causa:** Threshold degli alert troppo alti, finestra di valutazione troppo lunga, o l'alert non esiste per questo scenario.

**Soluzione:**

```yaml
# Verificare la copertura degli alert:
# 1. Controlla regole Prometheus per il servizio
kubectl get prometheusrule -n monitoring -o yaml | grep -A5 "payment-service"

# 2. Aggiungi alert per pod disponibili sotto soglia
- alert: DeploymentReplicasLow
  expr: |
    (
      kube_deployment_status_replicas_available{namespace="production"}
      /
      kube_deployment_spec_replicas{namespace="production"}
    ) < 0.8
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Deployment {{ $labels.deployment }}: solo {{ $value | humanizePercentage }} repliche disponibili"

# 3. Chaos-specific: alert se error rate sale anche solo del 0.5%
- alert: ErrorRateSpike
  expr: |
    sum(rate(http_requests_total{status=~"5..",namespace="production"}[2m]))
    /
    sum(rate(http_requests_total{namespace="production"}[2m])) > 0.005
  for: 30s   # finestra breve per rilevare spike rapidi durante chaos
  labels:
    severity: warning
    context: reliability
  annotations:
    summary: "Error rate spike: {{ $value | humanizePercentage }}"
```

## Relazioni

??? info "SLO/SLA/SLI — Definizione dello Steady State"
    Il chaos engineering si basa sulla violazione (o non-violazione) degli SLI per determinare il successo di un esperimento. Gli SLO definiscono il target — lo steady state hypothesis è una formalizzazione degli SLO da applicare durante il chaos.

    **Approfondimento completo →** [SLO/SLA/SLI](./slo-sla-sli.md)

??? info "Incident Management — GameDay come Simulazione"
    Il GameDay segue lo stesso processo dell'incident management: ruoli definiti, IC, scribe, postmortem. La differenza è che è pianificato. Un buon processo di incident management è prerequisito per eseguire chaos in sicurezza.

    **Approfondimento completo →** [Incident Management](./incident-management.md)

??? info "Error Budget — Quanto Chaos Possiamo Permetterci"
    Gli esperimenti chaos consumano error budget se violano gli SLO. Pianificare i GameDay tenendo conto del budget disponibile: non eseguire chaos quando il budget è < 20% della finestra mensile.

    **Approfondimento completo →** [Error Budget](./error-budget.md)

??? info "Kubernetes Workloads — Target degli Esperimenti"
    Deployment, StatefulSet, DaemonSet — ognuno ha comportamenti diversi durante il chaos (rescheduling, PDB, affinity). Comprendere i workload Kubernetes è prerequisito per disegnare esperimenti efficaci.

    **Approfondimento completo →** [Kubernetes Workloads](../../containers/kubernetes/workloads.md)

## Riferimenti

- [Principles of Chaos Engineering](https://principlesofchaos.org/)
- [Netflix Tech Blog — Chaos Engineering](https://netflixtechblog.com/tagged/chaos-engineering)
- [Litmus Chaos Documentation](https://docs.litmuschaos.io/)
- [Chaos Mesh Documentation](https://chaos-mesh.org/docs/)
- [AWS Fault Injection Simulator (FIS)](https://docs.aws.amazon.com/fis/)
- [Google SRE Workbook — Eliminating Toil](https://sre.google/workbook/eliminating-toil/)
- [Chaos Engineering Book — O'Reilly (Rosenthal et al.)](https://www.oreilly.com/library/view/chaos-engineering/9781492043850/)
- [CNCF Chaos Engineering Landscape](https://landscape.cncf.io/card-mode?category=chaos-engineering)
