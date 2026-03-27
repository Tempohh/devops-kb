---
title: "Google Kubernetes Engine (GKE)"
slug: gke
category: cloud/gcp/containers
tags: [gcp, kubernetes, gke, containers, autopilot, workload-identity, node-pools, managed-kubernetes]
search_keywords: [GKE, Google Kubernetes Engine, Kubernetes managed GCP, Autopilot GKE, Standard GKE, Workload Identity, node pool GKE, release channel GKE, upgrade automatico Kubernetes, cluster GKE, GKE Autopilot vs Standard, container GCP, managed K8s Google, GKE cluster regionale, GKE zonal cluster, kubectl GCP, gcloud container, Binary Authorization GKE, GKE Sandbox, cluster autoscaler GKE, preemptible node pool, spot node pool, GKE logging, GKE monitoring, Cloud Logging GKE, Cloud Monitoring GKE, Artifact Registry GCP, GKE networking, VPC-native cluster, alias IP, GKE ingress, GKE load balancer, GKE upgrade, surge upgrade, blue-green upgrade, node auto-provisioning, GKE ARM, confidential nodes, GKE cost optimization, node taints GKE]
parent: cloud/gcp/containers/_index
related: [containers/kubernetes/architettura, containers/kubernetes/workloads, containers/kubernetes/networking, containers/kubernetes/sicurezza, cloud/gcp/fondamentali/panoramica]
official_docs: https://cloud.google.com/kubernetes-engine/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-25
---

# Google Kubernetes Engine (GKE)

## Panoramica

Google Kubernetes Engine (GKE) è il servizio Kubernetes managed di Google Cloud, disponibile dal 2014 — il primo managed Kubernetes del mercato, costruito da chi ha inventato Kubernetes stesso. GKE gestisce l'intero lifecycle del control plane (API server, etcd, scheduler, controller manager) e offre automazione avanzata per node upgrades, scalabilità e sicurezza.

**Quando usare GKE:**
- Workload containerizzati su GCP che richiedono orchestrazione complessa
- Team che vogliono Kubernetes senza gestire il control plane
- Applicazioni che necessitano di scalabilità automatica fine-grained
- Scenari multi-tenant con isolamento forte tra workload

**Quando valutare alternative:**
- Applicazioni stateless semplici → **Cloud Run** (serverless containers, zero management)
- Jobs batch o pipeline → **Cloud Run Jobs** o **Dataflow**
- Vincoli di budget ridotti con team piccolo → Cloud Run costa meno di un cluster GKE

**Due modalità operative:**
- **Autopilot** → Google gestisce anche i nodi; paghi per Pod, non per nodo
- **Standard** → Gestisci i node pool tu; controllo totale su macchine e configurazione

---

## Autopilot vs Standard

La scelta tra Autopilot e Standard è la decisione architetturale più importante quando si crea un cluster GKE.

### Confronto

| Caratteristica | Autopilot | Standard |
|---|---|---|
| Gestione nodi | Google gestisce tutto | Gestita dall'utente |
| Pricing | Per Pod (CPU+RAM richieste) | Per nodo (VM attive) |
| Node sizing | Automatico | Manuale (scegli il machine type) |
| Scaling | Automatico, immediato | Cluster Autoscaler (più lento) |
| Accesso SSH ai nodi | Non disponibile | Disponibile |
| DaemonSet personalizzati | Non supportati | Supportati |
| Privileged containers | Non supportati | Supportati |
| GPU/TPU | Supportati (selezione automatica) | Supportati |
| Best per | Team che vogliono zero-ops | Team con requisiti infra specifici |

### Quando scegliere Autopilot

```
Autopilot è la scelta giusta se:
├── Non hai competenze infra dedicate a gestire nodi K8s
├── I tuoi workload sono standard (Deployment, StatefulSet, Job)
├── Vuoi pagare solo per le risorse Pod effettive, non per nodi idle
├── Non usi DaemonSet personalizzati o containers privilegiati
└── Priorità: time-to-market e semplicità operativa
```

### Quando scegliere Standard

```
Standard è necessario se:
├── Usi DaemonSet personalizzati (log forwarder, security agent)
├── Hai containers privilegiati o con capabilities avanzate
├── Hai bisogno di SSH/debug diretto sui nodi
├── Usi hardware specifico (GPU/TPU con configurazioni non standard)
├── Hai node pool con SO personalizzati o immagini custom
└── Vuoi ottimizzare costi con nodi preemptible/spot a gestione manuale
```

!!! tip "Autopilot per nuovi cluster"
    Per la maggior parte dei nuovi cluster GCP, **Autopilot è la scelta consigliata da Google**. Riduce la superficie di attacco (nodi non accessibili), garantisce SLA sul control plane e semplifica la gestione operativa. Valuta Standard solo per requisiti tecnici specifici.

---

## Architettura / Come Funziona

### Control Plane

In GKE il control plane è **completamente managed da Google**:

```
┌─────────────────────────────────────────────────────────────────┐
│  Control Plane (Google-managed, fatturato separatamente)        │
│  ├── API Server    (endpoint pubblico o privato)                │
│  ├── etcd          (HA con replica automatica)                  │
│  ├── Scheduler     (assegnazione Pod → nodi)                    │
│  └── Controller Manager                                         │
└─────────────────┬───────────────────────────────────────────────┘
                  │  kubelet + kube-proxy
         ┌────────┴────────┐
         │   Node Pool 1   │   Node Pool 2   │   Node Pool N
         │  (e2-standard)  │   (n2-highmem)  │   (spot VMs)
         └─────────────────┘─────────────────┘──────────────────
```

**Cluster Zonale vs Regionale:**

| Tipo | Control Plane | Nodi | Disponibilità | Costo |
|------|--------------|------|---------------|-------|
| **Zonale** | 1 zona | 1 zona | Downtime durante upgrade | Gratuito |
| **Regionale** | 3 zone | 3 zone (distribuite) | Upgrade senza downtime | ~$0.10/h |

!!! warning "Cluster Zonale in Produzione"
    Un cluster **zonale** ha il control plane in una sola zona: durante un upgrade del control plane (che avviene automaticamente), l'API server è irraggiungibile per alcuni minuti. **In produzione usare sempre cluster regionali.**

### Node Pool

Un **node pool** è un gruppo omogeneo di VM (stesso machine type, stesso SO, stessa configurazione) all'interno del cluster. Un cluster può avere N node pool.

```
Cluster GKE "production"
├── Node Pool "general" — e2-standard-4, 3 nodi, 3 zone
├── Node Pool "highmem"  — n2-highmem-8, 2 nodi, europe-west8-b
├── Node Pool "spot"     — e2-standard-2, 0-10 nodi, spot VM, autoscaling
└── Node Pool "gpu"      — n1-standard-4 + nvidia-tesla-t4, 1 nodo
```

Ogni node pool può avere:
- Machine type diverso
- Autoscaling abilitato con min/max nodi
- Taint per isolare tipi di workload
- Labels per lo scheduling via nodeSelector/affinity
- SO diverso (Container-Optimized OS, Ubuntu, Windows)

### Networking VPC-native

GKE utilizza **VPC-native networking** (Alias IP): ogni Pod riceve un IP direttamente dalla subnet VPC, senza NAT o overlay network.

```
VPC "production-vpc"
└── Subnet "europe-west8-subnet" — 10.0.0.0/20
    ├── Nodi: 10.0.0.0/24       (primary range)
    ├── Pod:  10.4.0.0/14       (alias IP range — secondary range)
    └── Services: 10.8.0.0/20   (cluster services range)
```

Vantaggi VPC-native:
- Pod IP routabili direttamente nella VPC (nessun tunneling)
- Firewall rules applicate direttamente ai Pod
- Integrazione nativa con Cloud Load Balancing
- Performance di rete identica alle VM

---

## Configurazione & Pratica

### Creazione Cluster

```bash
# ── AUTOPILOT ────────────────────────────────────────────────────
# Cluster Autopilot regionale (consigliato per produzione)
gcloud container clusters create-auto my-cluster \
    --region=europe-west8 \
    --project=my-project-id

# Cluster Autopilot con VPC e subnet specifiche
gcloud container clusters create-auto my-cluster \
    --region=europe-west8 \
    --network=production-vpc \
    --subnetwork=europe-west8-subnet \
    --cluster-secondary-range-name=pods \
    --services-secondary-range-name=services

# ── STANDARD ─────────────────────────────────────────────────────
# Cluster Standard regionale con 1 node pool
gcloud container clusters create my-cluster \
    --region=europe-west8 \
    --num-nodes=2 \
    --machine-type=e2-standard-4 \
    --disk-size=100 \
    --disk-type=pd-ssd \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=5 \
    --release-channel=regular \
    --workload-pool=my-project-id.svc.id.goog \
    --enable-ip-alias \
    --network=production-vpc \
    --subnetwork=europe-west8-subnet

# Recuperare le credenziali kubectl
gcloud container clusters get-credentials my-cluster \
    --region=europe-west8 \
    --project=my-project-id

# Verificare la connessione
kubectl cluster-info
kubectl get nodes
```

### Gestione Node Pool

```bash
# Aggiungere un node pool GPU al cluster esistente
gcloud container node-pools create gpu-pool \
    --cluster=my-cluster \
    --region=europe-west8 \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --num-nodes=1 \
    --enable-autoscaling \
    --min-nodes=0 \
    --max-nodes=4 \
    --node-taints=dedicated=gpu:NoSchedule \
    --node-labels=workload=gpu

# Aggiungere un node pool Spot (preemptible di seconda generazione)
gcloud container node-pools create spot-pool \
    --cluster=my-cluster \
    --region=europe-west8 \
    --machine-type=e2-standard-4 \
    --spot \
    --enable-autoscaling \
    --min-nodes=0 \
    --max-nodes=20 \
    --node-taints=cloud.google.com/gke-spot=true:NoSchedule

# Ridimensionare un node pool manualmente
gcloud container clusters resize my-cluster \
    --node-pool=default-pool \
    --num-nodes=4 \
    --region=europe-west8

# Eliminare un node pool (le VM vengono terminate)
gcloud container node-pools delete old-pool \
    --cluster=my-cluster \
    --region=europe-west8
```

### Release Channel e Upgrade

GKE organizza gli upgrade Kubernetes in 3 **release channel**:

| Channel | Kubernetes Version | Cadenza | Use Case |
|---------|-------------------|---------|----------|
| **Rapid** | Più recente | Settimane | Test, bleeding-edge features |
| **Regular** | N-1 minor | ~1 mese | Produzione standard (consigliato) |
| **Stable** | N-2 minor | ~3 mesi | Produzione con requisiti di stabilità massima |

```bash
# Impostare il release channel (solo al momento della creazione per il control plane)
gcloud container clusters create my-cluster \
    --release-channel=regular \
    ...

# Cambiare release channel su cluster esistente
gcloud container clusters update my-cluster \
    --release-channel=stable \
    --region=europe-west8

# Verificare la versione corrente e disponibile
gcloud container get-server-config --region=europe-west8

# Aggiornare manualmente il control plane a una versione specifica
gcloud container clusters upgrade my-cluster \
    --master \
    --cluster-version=1.30.5-gke.1234567 \
    --region=europe-west8

# Aggiornare un node pool (surge upgrade: 1 nodo extra durante upgrade)
gcloud container clusters upgrade my-cluster \
    --node-pool=default-pool \
    --cluster-version=1.30.5-gke.1234567 \
    --region=europe-west8
```

!!! warning "Ordine degli upgrade"
    Il **control plane deve essere aggiornato prima dei nodi**. GKE non permette l'upgrade dei nodi a una versione superiore al control plane. In un cluster regionale, GKE aggiorna il control plane zona per zona senza downtime.

!!! tip "Surge Upgrade per zero-downtime"
    Con **surge upgrade** (default), GKE aggiunge temporaneamente `max-surge` nodi extra durante l'upgrade, sposta i Pod, poi rimuove i vecchi nodi. Configura `--max-surge=1 --max-unavailable=0` per upgrade senza impatto ai workload.

---

## Workload Identity

**Workload Identity** è il meccanismo consigliato per permettere ai Pod GKE di accedere ai servizi GCP senza chiavi JSON. Mappa un Kubernetes Service Account a un Google Service Account tramite federazione IAM.

### Architettura

```
Pod
└── usa K8s Service Account (KSA) "my-app-ksa"
    └── annotato con → IAM Service Account (GSA) "my-app-sa@project.iam.gserviceaccount.com"
        └── ha ruoli → roles/storage.objectViewer, roles/cloudsql.client
```

Il Pod ottiene un token OIDC dall'API server GKE → le librerie client GCP lo scambiano con un token IAM → accesso al servizio GCP senza segreti.

### Configurazione Step-by-Step

```bash
# 1. Abilitare Workload Identity sul cluster (se non già abilitato alla creazione)
gcloud container clusters update my-cluster \
    --workload-pool=my-project-id.svc.id.goog \
    --region=europe-west8

# 2. Abilitare Workload Identity sul node pool
gcloud container node-pools update default-pool \
    --cluster=my-cluster \
    --workload-metadata=GKE_METADATA \
    --region=europe-west8

# 3. Creare il Google Service Account (GSA)
gcloud iam service-accounts create my-app-sa \
    --display-name="My App Service Account"

# 4. Assegnare i ruoli necessari al GSA
gcloud projects add-iam-policy-binding my-project-id \
    --member="serviceAccount:my-app-sa@my-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# 5. Permettere al KSA di impersonare il GSA (il binding IAM chiave)
gcloud iam service-accounts add-iam-policy-binding \
    my-app-sa@my-project-id.iam.gserviceaccount.com \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:my-project-id.svc.id.goog[my-namespace/my-app-ksa]"
```

```yaml
# 6. Creare il Kubernetes Service Account con l'annotazione
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-ksa
  namespace: my-namespace
  annotations:
    iam.gke.io/gcp-service-account: my-app-sa@my-project-id.iam.gserviceaccount.com

---
# 7. Usare il KSA nel Pod/Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  template:
    spec:
      serviceAccountName: my-app-ksa  # il KSA con l'annotazione
      containers:
      - name: app
        image: gcr.io/my-project-id/my-app:latest
        # Le librerie client GCP rilevano automaticamente le credenziali
        # via Application Default Credentials (ADC)
```

```bash
# 8. Verificare che Workload Identity funzioni
kubectl exec -it my-pod -n my-namespace -- \
    curl -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
# Deve ritornare: my-app-sa@my-project-id.iam.gserviceaccount.com
```

!!! warning "Mai usare chiavi JSON in produzione"
    Con Workload Identity non servono chiavi JSON nei secret Kubernetes. Le chiavi JSON sono credenziali a lungo termine che se trapelate danno accesso illimitato. Workload Identity usa token OIDC a breve scadenza (1 ora) con rotazione automatica.

---

## Autoscaling

GKE offre tre livelli di autoscaling complementari:

### 1. Horizontal Pod Autoscaler (HPA)

Scala il numero di repliche di un Deployment/StatefulSet in base a CPU, memoria o metriche custom.

```yaml
# HPA basato su CPU — nativo K8s
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 2. Cluster Autoscaler (CA)

Scala il numero di nodi nel node pool in base ai Pod in stato `Pending` (insufficiente capacità) o nodi sottoutilizzati.

```bash
# Abilitare autoscaling su un node pool esistente
gcloud container node-pools update default-pool \
    --cluster=my-cluster \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=10 \
    --region=europe-west8

# Verificare le decisioni del cluster autoscaler
kubectl describe configmap cluster-autoscaler-status \
    -n kube-system
```

```yaml
# Annotation per evitare che il CA dreni un nodo specifico
# (utile per nodi con workload con stato che non devono essere migrati)
cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
```

### 3. Node Auto-Provisioning (NAP)

Con NAP, GKE **crea automaticamente nuovi node pool** quando nessun node pool esistente può soddisfare la richiesta (es. Pod con richiesta GPU, memoria molto alta, taint specifici).

```bash
# Abilitare Node Auto-Provisioning
gcloud container clusters update my-cluster \
    --enable-autoprovisioning \
    --max-cpu=100 \
    --max-memory=1000 \
    --region=europe-west8

# Con limiti per tipo di acceleratore
gcloud container clusters update my-cluster \
    --enable-autoprovisioning \
    --max-cpu=200 \
    --max-memory=2000 \
    --autoprovisioning-resource-limits=nvidia-tesla-t4=4 \
    --region=europe-west8
```

!!! tip "Spot VM per ridurre i costi"
    I node pool con **Spot VM** (preemptible di seconda generazione) costano fino all'80% in meno rispetto alle VM standard. Usare per workload batch, job non critici, o sviluppo. I Pod devono tollerare il taint `cloud.google.com/gke-spot=true:NoSchedule` e supportare l'interruzione improvvisa.

---

## Best Practices

!!! warning "Non usare il namespace `default`"
    In produzione, creare namespace dedicati per ogni applicazione/team. Il namespace `default` non ha quote, network policy, o resource limits — un bug può saturare il cluster intero.

!!! warning "Impostare sempre requests e limits"
    Senza `resources.requests`, il Cluster Autoscaler non sa quanta capacità serve e scala male. Senza `resources.limits`, un container buggy può consumare tutto il nodo. In GKE Autopilot i limits sono **obbligatori** — il Pod viene rifiutato senza.

```yaml
# Template risorse corretto per GKE
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "512Mi"
```

!!! tip "Cluster Privato per Produzione"
    Un **cluster privato** ha i nodi senza IP pubblico. L'accesso al control plane avviene tramite IP privato o via Cloud NAT per il traffico uscente. Riduce drasticamente la superficie di attacco. Da abilitare al momento della creazione (non modificabile dopo).

```bash
# Cluster Standard privato (nodi senza IP pubblici)
gcloud container clusters create my-private-cluster \
    --region=europe-west8 \
    --enable-private-nodes \
    --enable-private-endpoint \
    --master-ipv4-cidr=172.16.0.0/28 \
    --enable-master-authorized-networks \
    --master-authorized-networks=10.0.0.0/8
```

**Checklist best practices GKE:**

- [ ] Usare cluster **regionale** (non zonale) in produzione
- [ ] Abilitare **Workload Identity** — mai chiavi JSON
- [ ] Cluster **privato** (nodi senza IP pubblici)
- [ ] **Release channel Regular** per produzione
- [ ] Resource `requests` e `limits` su tutti i container
- [ ] **PodDisruptionBudget** su servizi critici per upgrade senza downtime
- [ ] **NetworkPolicy** per isolare namespace
- [ ] Abilitare **Binary Authorization** per trusted images
- [ ] Separare node pool per workload diversi (spot, GPU, highmem)
- [ ] Monitoring con **Cloud Monitoring** e alert su CPU/memory node pressure

---

## Troubleshooting

**Problema: Pod in stato `Pending` — `0/3 nodes are available`**
```bash
# Causa 1: risorse insufficienti nei nodi
# Diagnosi
kubectl describe pod <pod-name> -n <namespace>
# Cercare: "Insufficient cpu", "Insufficient memory"

# Soluzione: verificare l'autoscaling del node pool
kubectl describe configmap cluster-autoscaler-status -n kube-system

# Verificare se il CA sta aspettando di scalare
gcloud container operations list --filter="status=RUNNING" --region=europe-west8

# Causa 2: nodeSelector o affinity non soddisfatta
kubectl get nodes --show-labels
# Verificare che esista almeno 1 nodo con il label richiesto

# Causa 3: taint sul nodo senza toleration nel Pod
kubectl describe nodes | grep -A5 Taints
```

**Problema: `Error: failed to create containerd task` — immagine non trovata**
```bash
# Causa: il nodo non ha permessi per pullare da Artifact Registry / Container Registry
# Diagnosi
kubectl get events --field-selector reason=Failed -n <namespace>

# Soluzione 1: verificare i permessi del service account del nodo
gcloud container clusters describe my-cluster --region=europe-west8 \
    --format="value(nodeConfig.serviceAccount)"
# Assicurarsi che questo SA abbia roles/artifactregistry.reader

# Soluzione 2: configurare imagePullSecrets se si usa un registry privato esterno
kubectl create secret docker-registry my-registry-secret \
    --docker-server=REGISTRY_HOST \
    --docker-username=USERNAME \
    --docker-password=PASSWORD
```

**Problema: Workload Identity non funziona — `401 Unauthorized` sui servizi GCP**
```bash
# Diagnosi 1: verificare l'annotazione sul KSA
kubectl describe serviceaccount my-app-ksa -n my-namespace
# Cercare: iam.gke.io/gcp-service-account

# Diagnosi 2: verificare il binding IAM
gcloud iam service-accounts get-iam-policy \
    my-app-sa@my-project-id.iam.gserviceaccount.com
# Cercare: serviceAccount:my-project-id.svc.id.goog[namespace/ksa-name]

# Diagnosi 3: verificare che il node pool abbia GKE_METADATA
gcloud container node-pools describe default-pool \
    --cluster=my-cluster \
    --region=europe-west8 \
    --format="value(config.workloadMetadataConfig.mode)"
# Deve essere: GKE_METADATA

# Test diretto dal Pod
kubectl exec -it <pod> -- curl -s -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email
```

**Problema: nodi in stato `NotReady`**
```bash
# Causa comune: disk pressure, memory pressure, PID pressure
# Diagnosi
kubectl describe node <node-name> | grep -A20 Conditions

# Verificare i log del node (richiede accesso SSH — solo cluster Standard)
gcloud compute ssh <node-name> --zone=<zone>
sudo journalctl -u kubelet --since "10 minutes ago"

# In Autopilot: segnalare a Google tramite Cloud Support
# Controllare gli eventi recenti sul nodo
kubectl get events --field-selector involvedObject.name=<node-name>

# Force drain e ricrea il nodo (Standard)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
gcloud compute instances delete <node-name> --zone=<zone>
# Il cluster autoscaler ricrea il nodo automaticamente
```

**Problema: upgrade del cluster bloccato — `UPGRADE_FAILED`**
```bash
# Verificare lo stato delle operazioni
gcloud container operations list \
    --filter="status=RUNNING OR status=ABORTING" \
    --region=europe-west8

# Ottenere dettagli sull'operazione specifica
gcloud container operations describe OPERATION_ID \
    --region=europe-west8

# Cause comuni:
# - PodDisruptionBudget che blocca lo svuotamento del nodo
kubectl get pdb --all-namespaces
kubectl describe pdb <pdb-name> -n <namespace>

# - Pod con hostPort che non possono essere rischedulati
kubectl get pods --all-namespaces -o wide | grep <node-name>
```

---

## Relazioni

??? info "Kubernetes — Architettura di Base"
    GKE implementa Kubernetes standard. Concetti come Pod, Deployment, Service, Ingress e RBAC funzionano identicamente su GKE e su qualsiasi altro cluster K8s.

    **Approfondimento →** [Architettura Kubernetes](../../../containers/kubernetes/architettura.md)

??? info "Workload Kubernetes — Deployment, StatefulSet, Job"
    I tipi di workload K8s (Deployment, StatefulSet, DaemonSet, Job, CronJob) si applicano su GKE senza modifiche. GKE Autopilot ha alcune restrizioni sui DaemonSet e sui Pod privilegiati.

    **Approfondimento →** [Workload Kubernetes](../../../containers/kubernetes/workloads.md)

??? info "Networking Kubernetes su GKE"
    GKE usa VPC-native networking (Alias IP). Le NetworkPolicy K8s sono supportate nativamente. Per Ingress, GKE integra il GKE Ingress Controller con Google Cloud Load Balancer.

    **Approfondimento →** [Networking Kubernetes](../../../containers/kubernetes/networking.md)

??? info "GCP IAM e Service Account"
    Workload Identity richiede una comprensione di IAM GCP, service account, e binding di policy. La gerarchia IAM (Organization > Folder > Project > Risorsa) si applica anche ai permessi assegnati ai GSA usati da GKE.

    **Approfondimento →** [Panoramica GCP](../fondamentali/panoramica.md)

---

## Riferimenti

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Autopilot Overview](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [Release Channels](https://cloud.google.com/kubernetes-engine/docs/concepts/release-channels)
- [Cluster Autoscaler](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler)
- [Node Auto-Provisioning](https://cloud.google.com/kubernetes-engine/docs/how-to/node-auto-provisioning)
- [GKE Security Best Practices](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster)
- [GKE Pricing](https://cloud.google.com/kubernetes-engine/pricing)
- [Spot VMs on GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/spot-vms)
- [Private Clusters](https://cloud.google.com/kubernetes-engine/docs/how-to/private-clusters)
