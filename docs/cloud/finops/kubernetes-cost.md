---
title: "Kubernetes Cost Management — OpenCost e Kubecost"
slug: kubernetes-cost
category: cloud
tags: [finops, kubernetes, cost-management, opencost, kubecost, cost-allocation, chargeback, showback, rightsizing, namespace-cost]
search_keywords: [Kubernetes cost, Kubernetes cost management, OpenCost, Kubecost, cost allocation Kubernetes, chargeback Kubernetes, showback Kubernetes, namespace cost, cost per namespace, cost per team, FinOps Kubernetes, rightsizing Kubernetes, cost visibility K8s, cost monitoring Kubernetes, CNCF OpenCost, Kubecost enterprise, cost center Kubernetes, kubernetes billing, kubernetes spend, kubernetes resource cost, pod cost, container cost, cost per request, unit economics kubernetes, cost allocation labels, kubernetes multi-team cost, kubernetes cost dashboard, savings recommendations kubernetes, request sizing, over-provisioned pods, kubernetes egress cost, persistent volume cost, load balancer cost, cost anomaly kubernetes, budget alert kubernetes, allocation API, grafana cost dashboard, prometheus cost metrics, cloud cost kubernetes, kubernetes FinOps]
parent: cloud/finops/_index
related: [cloud/finops/fondamentali, containers/kubernetes/resource-management, monitoring/tools/prometheus]
official_docs: https://www.opencost.io/
status: needs-review
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---


# Kubernetes Cost Management — OpenCost e Kubecost

## Panoramica

Nei cluster Kubernetes multi-team, la **cloud bill è aggregata**: il provider cloud mostra un singolo addebito per il cluster, rendendo impossibile sapere quale team, namespace o applicazione sta generando quale costo. CPU, memoria e network sono risorse condivise e allocate dinamicamente — senza strumenti dedicati, il costo è una scatola nera.

**OpenCost** e **Kubecost** sono i due strumenti principali per risolvere questo problema: entrambi analizzano l'utilizzo reale delle risorse (CPU, memoria, storage, network) a livello di pod/namespace/label e lo mappano sui prezzi del cloud provider, producendo un costo allocato per ogni entità organizzativa.

**Quando usare questi strumenti:**
- Cluster con più di 2-3 team che condividono l'infrastruttura
- Cloud spend Kubernetes > $2k/mese (sotto questa soglia il ROI è basso)
- Organizzazioni che vogliono implementare showback o chargeback per i workload K8s
- Team FinOps che necessitano di unit economics (costo per richiesta API, costo per utente)

**Quando NON sono necessari:**
- Cluster mono-team con budget fisso e non contestato
- Ambienti on-premises dove il costo infrastruttura è a consumo piatto
- Cluster di sviluppo/test con costi trascurabili rispetto alla produzione

!!! note "OpenCost vs Kubecost"
    **OpenCost** è il progetto CNCF open source (incubating), standard e gratuito — ideale per organizzazioni con stack Prometheus già esistente. Nasce da Kubecost, che ne ha donato il motore di allocazione alla CNCF (2022); **Kubecost** (oggi di proprietà IBM, tramite Apptio) lo usa come base e aggiunge funzionalità commerciali (UI avanzata, savings engine, budget alerts, multi-cluster, riconciliazione con la fattura reale). Per molte organizzazioni OpenCost basta per allocation e showback senza costo di licenza. Kubecost ha un tier gratuito (Foundations: cluster illimitati fino a 250 core, retention metriche 15 giorni); oltre quei limiti serve una licenza.

    OpenCost è CNCF **Incubating** dal 25/10/2024 (accettato come Sandbox il 17/06/2022). La documentazione Kubecost è ora ospitata su IBM Docs.

!!! note "Termini"
    **PVC** = PersistentVolumeClaim (richiesta di storage); **P95** = 95° percentile (valore sotto cui sta il 95% delle misure, ignora i picchi estremi); **OOMKill** = container terminato dal kernel per memoria esaurita.

---

## Concetti Chiave

### Il Problema del Costo Condiviso

Kubernetes è un scheduler di risorse condivise. Quando un nodo da 16 CPU viene usato da 10 pod di team diversi, come si alloca il costo?

OpenCost e Kubecost usano due metriche fondamentali:

| Metrica | Definizione | Quando si applica |
|---------|-------------|-------------------|
| **Cost by request** | Costo proporzionale alle `resources.requests` dichiarate | Risorse prenotate ma non usate |
| **Cost by usage** | Costo proporzionale all'utilizzo effettivo medio nella finestra | Risorse effettivamente consumate |
| **Idle cost** | Capacità dei nodi non allocata a nessun workload | Over-provisioning e nodi sottoutilizzati |

Il modello di default di OpenCost per CPU e RAM è il **massimo tra request e usage** (`max(request, usage)`): il team paga almeno ciò che ha prenotato (lo scheduler gli ha sottratto quella capacità), e di più se consuma oltre la request. Questo crea incentivi a fare rightsizing corretto delle requests. L'**idle** è esposto a parte e può essere ripartito (shared) sui workload o mostrato come voce separata.

### Costi Nascosti in Kubernetes

Oltre a CPU e memoria, i cluster generano costi spesso ignorati:

- **Egress network**: traffico in uscita verso internet o tra availability zone — può essere significativo per microservizi chattosi
- **Persistent Volumes (PV)**: ogni PVC ha un costo mensile di storage; i PVC orfani (non montati) continuano a costare
- **Load Balancer**: ogni `Service` di tipo `LoadBalancer` genera un cloud load balancer → $20-40/mese ciascuno su AWS/GCP/Azure
- **Node overhead**: costo del nodo che non è allocato ad alcun workload (sistema operativo, daemonset, kube-system)

!!! warning "PVC orfani e LB abbandonati"
    Nei cluster con deploy frequenti, PVC orfani e LoadBalancer non più usati sono tra i principali sprechi nascosti. OpenCost li traccia separatamente — configurare alert mensili per risorse non allocate con età > 7 giorni.

### Showback vs Chargeback in Kubernetes

| Approccio | Descrizione | Prerequisiti |
|-----------|-------------|-------------|
| **Showback** | I team vedono i loro costi ma non li pagano direttamente | Tagging consistente sui namespace |
| **Chargeback parziale** | I costi sopra una soglia vengono addebitati al budget del team | Showback maturo + buy-in management |
| **Chargeback completo** | Ogni team ha un budget cloud, i costi K8s vengono detratti | Budget separati per team + processo di approvazione |

La progressione consigliata: iniziare con showback per 3-6 mesi (crea consapevolezza senza conflitti), poi passare a chargeback graduale sui team con utilizzo più alto.

---

## Architettura / Come Funziona

### OpenCost — Architettura

```
┌─────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                  │
│                                                       │
│  ┌─────────────┐    ┌─────────────────────────────┐  │
│  │  OpenCost   │◀───│       Prometheus              │  │
│  │  :9003 API  │───▶│  (usage storico + scrape      │  │
│  │  :9003 /metrics│  │   metriche di costo)         │  │
│  └──────┬──────┘    └──────────────┬──────────────┘  │
│         │                          ▼                  │
│         │                 ┌──────────────┐            │
│         │                 │   Grafana    │            │
│         │                 │  Dashboard   │            │
│         │                 └──────────────┘            │
│         ▼                                             │
│  Pricing cloud provider (listini / billing API)       │
└─────────────────────────────────────────────────────┘
```

OpenCost funziona in due step:
1. **Resource allocation**: legge dalle API Kubernetes lo stato di nodi/pod/PVC e interroga Prometheus (metriche `cadvisor` e `kube-state-metrics`) per sapere quante risorse ogni pod ha richiesto e usato
2. **Cost mapping**: ottiene il prezzo di CPU/memoria/storage dal listino del cloud provider in base al tipo di istanza dei nodi (oppure da prezzi custom configurati a mano)

Il risultato è esposto via API REST e via metriche Prometheus (scrapate da Prometheus stesso).

### Kubecost — Architettura Estesa

Kubecost include OpenCost come backend e aggiunge:
- **UI dedicata** con drill-down per namespace/deployment/pod/label
- **Savings Engine**: analizza in background le opportunità di ottimizzazione
- **Budget Manager**: definisce soglie di spesa per namespace con alert
- **Multi-cluster aggregation**: vista unificata di costi di più cluster (versione Enterprise)

---

## Configurazione & Pratica

### Installazione OpenCost

```bash
# Aggiungere il repo Helm OpenCost
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update

# Installazione base con Prometheus esistente
helm install opencost opencost/opencost \
  --namespace opencost \
  --create-namespace \
  --set opencost.exporter.defaultClusterId="my-cluster" \
  --set opencost.ui.enabled=true
# opencost.exporter.cloudProviderApiKey serve solo per la GCP Pricing API (chiave di valutazione)

# Verifica che i pod siano running
kubectl get pods -n opencost
```

Per configurare il cloud provider (es. AWS) con IAM Roles for Service Accounts (IRSA):

Le chiavi `serviceAccount.annotations`, `opencost.exporter.defaultClusterId`, `opencost.prometheus.internal.*` e `opencost.ui.*` sono quelle del chart ufficiale. Per la Cloud Cost (fatture reali) esiste la sezione `opencost.cloudCost`, con permessi IAM dedicati: vedere la documentazione del chart.

```yaml
# values.yaml — OpenCost su EKS con IRSA
serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: "arn:aws:iam::ACCOUNT:role/opencost-role"
opencost:
  exporter:
    defaultClusterId: "my-cluster"
  prometheus:
    internal:
      enabled: true
      serviceName: prometheus-operated
      namespaceName: monitoring
      port: 9090
  ui:
    enabled: true
    ingress:
      enabled: true
      hosts:
        - host: opencost.internal.example.com
          paths:
            - path: /
              pathType: Prefix
```

### Query API OpenCost

L'API REST di OpenCost è il modo programmatico per estrarre dati di costo:

```bash
# Costo aggregato per namespace — ultimi 7 giorni, un risultato per giorno
curl "http://opencost.opencost.svc:9003/allocation/compute?window=7d&aggregate=namespace&accumulate=false"

# Costo aggregato per label "team" — mese corrente, un solo totale
curl "http://opencost.opencost.svc:9003/allocation/compute?window=month&aggregate=label:team&accumulate=true"

# Costo per deployment — con breakdown CPU/memoria/storage
curl "http://opencost.opencost.svc:9003/allocation/compute?window=7d&aggregate=deployment&accumulate=true"

# Response example (JSON):
# {
#   "code": 200,
#   "data": [{
#     "payments/nginx-api": {
#       "cpuCost": 12.45,
#       "memoryCost": 3.21,
#       "pvCost": 0.80,
#       "networkCost": 0.45,
#       "totalCost": 16.91
#     }
#   }]
# }
```

### Installazione Kubecost

```bash
# Aggiungere il repo Helm Kubecost
helm repo add kubecost https://kubecost.github.io/cost-analyzer/
helm repo update

# Installazione con Prometheus esistente (consigliato — evita duplicazione)
helm install cost-analyzer kubecost/cost-analyzer \
  --namespace kubecost \
  --create-namespace \
  --set global.prometheus.enabled=false \
  --set global.prometheus.fqdn="http://prometheus-operated.monitoring.svc:9090" \
  --set kubecostToken="TOKEN_DA_KUBECOST_IO"  # token del tier gratuito (registrazione su kubecost.com); con licenza enterprise usare quello della licenza
# <!-- CURRENCY: non verificato (2026-10): modalità di attivazione del tier gratuito (kubecostToken) e chiavi values del chart cost-analyzer -->  (IBM Docs non lo riporta nella first-time-user-guide)

# Con Prometheus bundled (setup rapido per test)
helm install cost-analyzer kubecost/cost-analyzer \
  --namespace kubecost \
  --create-namespace
```

### Configurazione Kubecost — Budget Alert per Namespace

Gli alert si definiscono nei values Helm del chart (non in un ConfigMap creato a mano, che Kubecost non legge):

Path confermato: `global.notifications.alertConfigs`. I budget alert accettano `window` da 1 a 7 giorni (o 1-24 ore), non `month`. Webhook Slack: `slackWebhookUrl` per alert, oppure `globalSlackWebhookUrl` a livello globale.

```yaml
# values.yaml — alert budget Kubecost
global:
  notifications:
    alertConfigs:
      enabled: true
      alerts:
        - type: budget
          threshold: 250             # $250 su finestra di 7 giorni
          window: 7d
          aggregation: namespace
          filter: "payments"
          slackWebhookUrl: "https://hooks.slack.com/services/..."
        - type: spendChange
          relativeThreshold: 0.20    # alert se +20% rispetto al periodo precedente
          window: 7d
          aggregation: label:team
          slackWebhookUrl: "https://hooks.slack.com/services/..."
```

### Tagging Workload per Cost Allocation

La cost allocation per team funziona solo se i workload sono etichettati in modo consistente:

```yaml
# Deployment con label per cost allocation
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
  namespace: payments
  labels:
    app: payment-api
    team: payments                 # identifica il team owner
    cost-center: CC-1234           # centro di costo Finance
    environment: prod              # evita di aggregare prod e staging
    product: checkout              # prodotto business di riferimento
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-api
  template:
    metadata:
      labels:
        app: payment-api
        team: payments
        cost-center: CC-1234
        environment: prod
        product: checkout
    spec:
      containers:
      - name: api
        image: payment-api:v1.2.0
        resources:
          requests:
            cpu: "500m"            # rightsizing corretto = cost allocation corretta
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
```

!!! tip "Label nei namespace oltre che nei pod"
    Applicare le label `team` e `cost-center` anche a livello di `Namespace` — OpenCost e Kubecost aggregano per namespace label, permettendo di catturare risorse (PVC, LB) che non appartengono a un singolo deployment.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payments
  labels:
    team: payments
    cost-center: CC-1234
    environment: prod
```

---

## Best Practices

### Governance del Tagging

Il tagging inconsistente è il principale motivo per cui i report di cost allocation sono inaffidabili. Imporre il tagging come gate nel CI/CD:

```bash
#!/bin/bash
# pre-deploy-check.sh — verifica label obbligatorie prima del deploy
REQUIRED_LABELS=("team" "cost-center" "environment")
MANIFEST=$1

for label in "${REQUIRED_LABELS[@]}"; do
  if ! grep -q "\"$label\"" "$MANIFEST" && ! grep -q "$label:" "$MANIFEST"; then
    echo "ERROR: label '$label' mancante nel manifest $MANIFEST"
    exit 1
  fi
done
echo "Label check OK"
```

Alternativa più robusta: usare un **OPA/Gatekeeper policy** (admission controller che valida le risorse al momento della creazione) che nega il deploy se le label obbligatorie mancano. Richiede la `ConstraintTemplate` `K8sRequiredLabels` (dalla libreria Gatekeeper) già installata; il constraint sotto controlla le label sull'oggetto Deployment, non sul pod template, quindi aggiungere le stesse label anche in `spec.template.metadata.labels`, che è dove OpenCost le legge sui pod:

```yaml
# gatekeeper-required-labels.yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-cost-labels
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment", "StatefulSet", "DaemonSet"]
  parameters:
    labels:
      - key: team
      - key: cost-center
      - key: environment
```

### Rightsizing Sistematico

Over-provisioning è la fonte principale di costo evitabile in Kubernetes. Il workflow consigliato:

1. **Baseline**: raccogliere dati di utilizzo per almeno 7 giorni (meglio 30)
2. **Query Kubecost API** per raccomandazioni rightsizing:

L'endpoint corrente è `/model/savings/requestSizingV2` (parametri: `window`, `algorithmCPU`/`algorithmRAM` = `quantileOfMaxes`|`quantileOfAverages`, `qCPU`/`qRAM`, `targetCPUUtilization`/`targetRAMUtilization` — default 0.7, `filter`, `minRecCPUMillicores`, `minRecRAMBytes`).

```bash
# Raccomandazioni rightsizing — target utilization 80%
curl "http://cost-analyzer.kubecost.svc:9090/model/savings/requestSizingV2?window=30d&targetCPUUtilization=0.8&targetRAMUtilization=0.8"

# Filtrare per namespace specifico
curl -G "http://cost-analyzer.kubecost.svc:9090/model/savings/requestSizingV2" \
  --data-urlencode "window=30d" --data-urlencode "targetCPUUtilization=0.8" \
  --data-urlencode 'filter=namespace:"payments"'

# Output: per ogni container, requests consigliate vs attuali
# {
#   "container": "payment-api",
#   "currentCpuRequest": "2000m",
#   "recommendedCpuRequest": "350m",   # utilizzo P95 = 280m → 350m con buffer
#   "cpuSavings": "$18.50/month",
#   ...
# }
```

3. **Applicare gradualmente**: non tagliare le request bruscamente — ridurre del 30-50% e monitorare per 48h prima di un'ulteriore riduzione.

!!! warning "Non tagliare i limits insieme alle requests"
    Ridurre solo le `requests` (non i `limits`) è la strategia sicura: il pod ottiene le risorse garantite più basse, ma può burstare se il nodo ha capacità disponibile. Ridurre i `limits` può causare OOMKill o CPU throttling — farlo solo dopo aver verificato il profilo di utilizzo con dati reali.

### Metriche Prometheus per Cost Monitoring

OpenCost espone metriche Prometheus (`container_cpu_allocation`, `container_memory_allocation_bytes`, `node_cpu_hourly_cost`, `node_ram_hourly_cost`, `pv_hourly_cost`…) che permettono di costruire alert custom. Nota: sono senza prefisso `opencost_`; il nome esatto va verificato con `curl :9003/metrics`. <!-- REVIEW: verificare nomi metriche sulla versione OpenCost in uso -->

```yaml
# prometheus-cost-alerts.yaml
groups:
  - name: kubernetes-cost
    interval: 1h
    rules:
      # Alert se il costo mensile stimato (solo CPU) del namespace supera soglia
      # core allocati × costo orario per core del nodo × ~730 ore/mese
      - alert: NamespaceMonthlyCostHigh
        expr: |
          sum by (namespace) (
            container_cpu_allocation * on(node) group_left()
            node_cpu_hourly_cost
          ) * 730 > 1000
        for: 2h
        labels:
          severity: warning
        annotations:
          summary: "Namespace {{ $labels.namespace }} costo mensile > $1000"
          description: "Costo stimato: ${{ $value | humanize }}/mese"

      # Alert su PVC non utilizzati da più di 7 giorni
      - alert: OrphanedPVCDetected
        expr: |
          kube_persistentvolumeclaim_status_phase{phase="Bound"} == 1
          unless on(persistentvolumeclaim, namespace)
          kube_pod_spec_volumes_persistentvolumeclaims_info
        for: 7d
        labels:
          severity: info
        annotations:
          summary: "PVC orfano rilevato: {{ $labels.persistentvolumeclaim }}"
```

### Unit Economics — Costo per Richiesta API

L'obiettivo finale di FinOps per Kubernetes è calcolare il costo per unità di business:

```bash
# Script shell (curl + jq + bc) per calcolare costo per richiesta API
# Combina dati OpenCost (costo namespace) con Prometheus (request rate)

NAMESPACE_COST=$(curl -s "http://opencost:9003/allocation/compute?window=1d&aggregate=namespace&accumulate=true" \
  | jq '.data[0]["payments"].totalCost')

REQUEST_COUNT=$(curl -s "http://prometheus:9090/api/v1/query?query=sum(increase(http_requests_total{namespace='payments'}[1d]))" \
  | jq '.data.result[0].value[1]')

echo "Costo per richiesta API: $(echo "$NAMESPACE_COST / $REQUEST_COUNT" | bc -l | head -c 8) USD"
# Output: 0.000023 USD per richiesta
```

---

## Troubleshooting

### OpenCost mostra costo $0.00 per tutti i namespace

**Sintomo:** la dashboard/API restituisce costi zero o null per tutti i workload.

**Causa più comune:** OpenCost non riesce a recuperare i prezzi dal cloud provider.

**Diagnosi e soluzione:**
```bash
# Verificare i log del pod OpenCost
kubectl logs -n opencost deployment/opencost -c opencost

# Cercare errori di autenticazione/pricing verso il cloud provider
# (messaggi indicativi, il testo esatto varia per versione):
# "NoCredentialProviders", "permission denied"

# Per AWS: verificare che il ServiceAccount abbia il role IAM corretto
kubectl describe sa opencost -n opencost
# Deve mostrare: eks.amazonaws.com/role-arn annotation

# Per GCP: verificare Workload Identity
kubectl get sa opencost -n opencost -o yaml | grep annotations

# Verificare anche che Prometheus sia raggiungibile da OpenCost:
# senza metriche di usage tutti i costi risultano 0
kubectl logs -n opencost deployment/opencost -c opencost | grep -i prometheus

# Fallback: prezzi custom manuali (chart opencost; verificare chiavi nella versione in uso)
helm upgrade opencost opencost/opencost -n opencost --reuse-values \
  --set opencost.customPricing.enabled=true \
  --set opencost.customPricing.costModel.CPU=0.031 \
  --set opencost.customPricing.costModel.RAM=0.004
```

### Kubecost mostra costi diversi da OpenCost per lo stesso namespace

**Sintomo:** i due tool mostrano valori significativamente diversi per lo stesso namespace nello stesso periodo.

**Causa:** tipicamente (1) Kubecost riconcilia i prezzi con la fattura reale del provider (sconti, Savings Plans, spot) mentre OpenCost usa i listini on-demand o i prezzi custom; (2) diversa ripartizione dei costi idle/shared; (3) finestra temporale o timezone diverse; (4) endpoint Prometheus diversi.

**Soluzione:**
```bash
# Confrontare con gli stessi parametri: stessa window, idle/shared nello stesso stato
# Verificare che usino lo stesso Prometheus
kubectl get cm -n kubecost -o yaml | grep -i prometheus
kubectl logs -n opencost deployment/opencost -c opencost | grep -i prometheus
```
Confrontare poi il prezzo orario per nodo nelle due UI: se differisce, la causa è il pricing, non l'allocation.

### Alert budget non arrivano su Slack

**Sintomo:** i budget sono configurati ma gli alert non vengono inviati.

**Diagnosi:**
```bash
# Verificare che gli alert siano presenti nella configurazione applicata
helm get values cost-analyzer -n kubecost | grep -A10 -i alert

# Verificare i log del cost-analyzer per errori webhook
kubectl logs -n kubecost deployment/cost-analyzer | grep -i "slack\|webhook\|alert"

# Test manuale del webhook Slack
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test alert Kubecost"}' \
  "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Causa comune:** i values Helm non sono stati applicati o il pod non ha ricaricato la configurazione — fare `helm upgrade` e poi rolling restart:
```bash
kubectl rollout restart deployment/cost-analyzer -n kubecost
```

### Raccomandazioni rightsizing appaiono troppo aggressive

**Sintomo:** Kubecost suggerisce di ridurre le requests a valori molto bassi che causerebbero problemi in produzione.

**Causa:** la finestra di analisi è troppo corta o non copre i picchi di traffico.

**Soluzione:**
```bash
# Usare finestra più lunga e target utilization più conservativo
curl "http://cost-analyzer.kubecost.svc:9090/model/savings/requestSizingV2?window=30d&targetCPUUtilization=0.65"
# targetCPUUtilization=0.65 → le nuove requests = utilizzo_P95 / 0.65 (buffer del 35%)

# Per workload con picchi stagionali (es. e-commerce a Natale):
# usare window=90d per catturare i picchi storici
curl "http://cost-analyzer.kubecost.svc:9090/model/savings/requestSizingV2?window=90d&targetCPUUtilization=0.70"
```

---

## Relazioni

??? info "FinOps Fondamentali — Framework e Principi"
    OpenCost e Kubecost implementano la fase **INFORM** del lifecycle FinOps: visibilità e allocazione dei costi. Per il framework completo (showback, chargeback, unit economics, rightsizing a livello cloud) leggere la guida base.
    
    **Approfondimento completo →** [FinOps Fondamentali](fondamentali.md)

??? info "Kubernetes Resource Management — Requests e Limits"
    Il rightsizing suggerito da Kubecost agisce sulle `resources.requests` dei container. Per capire come requests e limits influenzano lo scheduling e i QoS class, e come applicare ResourceQuota per namespace.
    
    **Approfondimento completo →** [Kubernetes Resource Management](../../containers/kubernetes/resource-management.md)

??? info "Prometheus — Metriche e Alerting"
    OpenCost espone metriche in formato Prometheus. Per configurare alert custom sui costi e integrare le metriche di costo nei dashboard operativi esistenti.
    
    **Approfondimento completo →** [Prometheus](../../monitoring/tools/prometheus.md)

---

## Riferimenti

- [OpenCost — Documentazione Ufficiale](https://www.opencost.io/docs/) — installazione, API reference, integrazione cloud provider
- [OpenCost Helm Chart](https://github.com/opencost/opencost-helm-chart) — repository Helm con values di riferimento
- [Kubecost Documentazione](https://docs.kubecost.com/) — guida completa incluse funzionalità enterprise
- [CNCF FinOps for Kubernetes](https://www.cncf.io/blog/2021/06/29/opencost-open-source-collaboration-on-kubernetes-cost-standards/) — standard CNCF per cost allocation K8s
- [OpenCost Allocation API Reference](https://www.opencost.io/docs/integrations/allocation-api) — documentazione completa dell'API REST
- [Kubecost Savings API](https://docs.kubecost.com/apis/savings-apis) — API per rightsizing e ottimizzazione
- [FinOps for Kubernetes (FinOps Foundation)](https://www.finops.org/projects/calculating-container-costs/) — white paper su cost calculation per container
