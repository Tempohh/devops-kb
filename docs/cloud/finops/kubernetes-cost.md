---
title: "Kubernetes Cost Management — OpenCost e Kubecost"
slug: kubernetes-cost
category: cloud
tags: [finops, kubernetes, cost-management, opencost, kubecost, cost-allocation, chargeback, showback, rightsizing, namespace-cost]
search_keywords: [Kubernetes cost, Kubernetes cost management, OpenCost, Kubecost, cost allocation Kubernetes, chargeback Kubernetes, showback Kubernetes, namespace cost, cost per namespace, cost per team, FinOps Kubernetes, rightsizing Kubernetes, cost visibility K8s, cost monitoring Kubernetes, CNCF OpenCost, Kubecost enterprise, cost center Kubernetes, kubernetes billing, kubernetes spend, kubernetes resource cost, pod cost, container cost, cost per request, unit economics kubernetes, cost allocation labels, kubernetes multi-team cost, kubernetes cost dashboard, savings recommendations kubernetes, request sizing, over-provisioned pods, kubernetes egress cost, persistent volume cost, load balancer cost, cost anomaly kubernetes, budget alert kubernetes, allocation API, grafana cost dashboard, prometheus cost metrics, cloud cost kubernetes, kubernetes FinOps]
parent: cloud/finops/_index
related: [cloud/finops/fondamentali, containers/kubernetes/resource-management, monitoring/tools/prometheus]
official_docs: https://www.opencost.io/
status: complete
difficulty: intermediate
last_updated: 2026-04-04
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
    **OpenCost** è il progetto CNCF open source, standard e gratuito — ideale per organizzazioni con stack Prometheus già esistente. **Kubecost** nasce da OpenCost e aggiunge funzionalità enterprise (UI avanzata, anomaly detection, budget alerts, multi-cluster). Per la maggior parte delle organizzazioni, OpenCost copre l'80% dei casi d'uso senza costo di licenza.

---

## Concetti Chiave

### Il Problema del Costo Condiviso

Kubernetes è un scheduler di risorse condivise. Quando un nodo da 16 CPU viene usato da 10 pod di team diversi, come si alloca il costo?

OpenCost e Kubecost usano due metriche fondamentali:

| Metrica | Definizione | Quando si applica |
|---------|-------------|-------------------|
| **Cost by request** | Costo proporzionale alle `resources.requests` dichiarate | Risorse prenotate ma non usate |
| **Cost by usage** | Costo proporzionale all'utilizzo effettivo (P95) | Risorse effettivamente consumate |
| **Idle cost** | Costo delle risorse prenotate ma non utilizzate | Over-provisioning e nodi sottoutilizzati |

Il modello di default è **cost by request**: il team paga ciò che ha richiesto, indipendentemente dall'utilizzo reale. Questo crea incentivi a fare rightsizing corretto delle requests.

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
│  │  OpenCost   │───▶│       Prometheus              │  │
│  │  Exporter   │    │  (metriche costo aggregate)  │  │
│  │  :9003      │    └──────────────┬──────────────┘  │
│  └──────┬──────┘                   │                  │
│         │                          ▼                  │
│         │                 ┌──────────────┐            │
│         │                 │   Grafana    │            │
│         │                 │  Dashboard   │            │
│         │                 └──────────────┘            │
│         │                                             │
│         ▼                                             │
│  Cloud Provider API                                   │
│  (AWS Cost API / GCP Billing / Azure Cost Mgmt)       │
└─────────────────────────────────────────────────────┘
```

OpenCost funziona in due step:
1. **Resource allocation**: legge `kube-state-metrics` e `cadvisor` per sapere quante risorse ogni pod ha richiesto e usato
2. **Cost mapping**: chiama le API del cloud provider per ottenere il prezzo corrente di CPU/memoria/storage sul tipo di istanza dei nodi

Il risultato è esposto via API REST e via metriche Prometheus.

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
  --set opencost.exporter.cloudProviderApiKey="YOUR_CLOUD_API_KEY" \
  --set opencost.ui.enabled=true

# Verifica che i pod siano running
kubectl get pods -n opencost
```

Per configurare il cloud provider (es. AWS):

```yaml
# values.yaml — OpenCost con AWS pricing
opencost:
  exporter:
    cloudProviderApiKey: ""   # non necessario per AWS se si usa IAM role
    aws:
      # IAM role con permessi Cost Explorer Read
      serviceAccount:
        annotations:
          eks.amazonaws.com/role-arn: "arn:aws:iam::ACCOUNT:role/opencost-role"
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
# Costo aggregato per namespace — ultimi 7 giorni
curl "http://opencost.opencost.svc:9003/allocation?window=7d&aggregate=namespace&accumulate=false"

# Costo aggregato per label "team" — ultimo mese
curl "http://opencost.opencost.svc:9003/allocation?window=month&aggregate=label:team&accumulate=true"

# Costo per deployment — con breakdown CPU/memoria/storage
curl "http://opencost.opencost.svc:9003/allocation?window=7d&aggregate=deployment&accumulate=true&step=1d"

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
  --set kubecostToken="FREE"  # tier gratuito — rimuovere per enterprise

# Con Prometheus bundled (setup rapido per test)
helm install cost-analyzer kubecost/cost-analyzer \
  --namespace kubecost \
  --create-namespace
```

### Configurazione Kubecost — Budget Alert per Namespace

```yaml
# kubecost-budget-alert.yaml — ConfigMap per alert budget
apiVersion: v1
kind: ConfigMap
metadata:
  name: kubecost-budget-alert
  namespace: kubecost
data:
  alerts.yaml: |
    alerts:
      - type: budget
        threshold: 1000            # $1000/mese
        window: month
        aggregation: namespace
        filter: "namespace:payments"
        slackWebhookAddress: "https://hooks.slack.com/services/..."
      - type: budget
        threshold: 500
        window: month
        aggregation: namespace
        filter: "namespace:staging"
        slackWebhookAddress: "https://hooks.slack.com/services/..."
      - type: spendChange
        relativeThreshold: 0.20   # alert se +20% rispetto settimana precedente
        window: week
        aggregation: label:team
        slackWebhookAddress: "https://hooks.slack.com/services/..."
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

Alternativa più robusta: usare un **OPA/Gatekeeper policy** che nega il deploy se le label obbligatorie mancano:

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

```bash
# Raccomandazioni rightsizing — target utilization 80%
curl "http://cost-analyzer.kubecost.svc:9090/savings/requestSizing?window=30d&targetUtilization=0.8"

# Filtrare per namespace specifico
curl "http://cost-analyzer.kubecost.svc:9090/savings/requestSizing?window=30d&targetUtilization=0.8&filterNamespaces=payments"

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

OpenCost espone metriche Prometheus che permettono di costruire alert custom:

```yaml
# prometheus-cost-alerts.yaml
groups:
  - name: kubernetes-cost
    interval: 1h
    rules:
      # Alert se il costo mensile stimato del namespace supera soglia
      - alert: NamespaceMonthlyCostHigh
        expr: |
          sum by (namespace) (
            opencost_container_cpu_allocation_hours * on(node) group_left()
            opencost_node_cpu_hourly_cost
          ) * 720 > 1000
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
# Script Python per calcolare costo per richiesta API
# Combina dati OpenCost (costo namespace) con Prometheus (request rate)

NAMESPACE_COST=$(curl -s "http://opencost:9003/allocation?window=1d&aggregate=namespace&accumulate=true" \
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

# Cercare errori di autenticazione cloud provider
# Common errors:
# "Error fetching AWS pricing: NoCredentialProviders"
# "Failed to get GCP pricing: permission denied"

# Per AWS: verificare che il ServiceAccount abbia il role IAM corretto
kubectl describe sa opencost -n opencost
# Deve mostrare: eks.amazonaws.com/role-arn annotation

# Per GCP: verificare Workload Identity
kubectl get sa opencost -n opencost -o yaml | grep annotations

# Fallback: usare custom pricing manuale
helm upgrade opencost opencost/opencost \
  --set opencost.exporter.defaultClusterId="my-cluster" \
  --set opencost.exporter.cloudCostEnabled=false \
  # Senza cloud API, usa prezzi on-demand di default
```

### Kubecost mostra costi diversi da OpenCost per lo stesso namespace

**Sintomo:** i due tool mostrano valori significativamente diversi per lo stesso namespace nello stesso periodo.

**Causa:** differenze nel modello di allocation (request-based vs usage-based) o nel prezzo usato.

**Soluzione:**
```bash
# Verificare quale modello usa ciascuno
# OpenCost default: request-based
# Kubecost default: può variare — verificare nella UI Settings > Allocation

# Per allineare: configurare entrambi su request-based
# In Kubecost values.yaml:
kubecostProductConfigs:
  defaultModelType: "request"  # o "usage"

# Verificare anche che usino lo stesso endpoint Prometheus
kubectl get cm -n kubecost kubecost-cost-analyzer-frontend-config -o yaml
```

### Alert budget non arrivano su Slack

**Sintomo:** i budget sono configurati ma gli alert non vengono inviati.

**Diagnosi:**
```bash
# Verificare che il ConfigMap degli alert sia montato correttamente
kubectl describe deployment -n kubecost cost-analyzer | grep -A5 "Mounts"

# Verificare i log del cost-analyzer per errori webhook
kubectl logs -n kubecost deployment/cost-analyzer | grep -i "slack\|webhook\|alert"

# Test manuale del webhook Slack
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test alert Kubecost"}' \
  "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Causa comune:** il ConfigMap non viene ricaricato dopo la modifica — fare rolling restart:
```bash
kubectl rollout restart deployment/cost-analyzer -n kubecost
```

### Raccomandazioni rightsizing appaiono troppo aggressive

**Sintomo:** Kubecost suggerisce di ridurre le requests a valori molto bassi che causerebbero problemi in produzione.

**Causa:** la finestra di analisi è troppo corta o non copre i picchi di traffico.

**Soluzione:**
```bash
# Usare finestra più lunga e target utilization più conservativo
curl "http://cost-analyzer.kubecost.svc:9090/savings/requestSizing?window=30d&targetUtilization=0.65"
# targetUtilization=0.65 → le nuove requests = utilizzo_P95 / 0.65 (buffer del 35%)

# Per workload con picchi stagionali (es. e-commerce a Natale):
# usare window=90d per catturare i picchi storici
curl "http://cost-analyzer.kubecost.svc:9090/savings/requestSizing?window=90d&targetUtilization=0.70"
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
