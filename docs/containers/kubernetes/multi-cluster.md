---
title: "Multi-Cluster Kubernetes"
slug: multi-cluster
category: containers
tags: [kubernetes, multi-cluster, cluster-api, rancher, fleet, argocd, crossplane, kubefed, federation, gitops]
search_keywords: [kubernetes multi cluster, gestione multi cluster k8s, cluster federation kubernetes, Cluster API CAPI, KubeFed v2, Rancher multi cluster management, Fleet GitOps Rancher, Argo CD multi cluster deploy, Crossplane infrastructure kubernetes, multi cluster networking, cluster mesh, service mesh multi cluster, hub and spoke kubernetes, kubernetes federation pattern, workload distribution cluster, geo distribution kubernetes, dev staging prod cluster separation, multi cluster observability, multi cluster RBAC, vcluster virtual cluster, Loft vcluster, Open Cluster Management OCM, Admiral Istio multi cluster, kubernetes multi tenancy clusters, multi cluster DR disaster recovery, cluster lifecycle management]
parent: containers/kubernetes/_index
related: [containers/kubernetes/architettura, containers/kubernetes/networking, containers/kubernetes/operators-crd, containers/kubernetes/sicurezza, containers/kubernetes/helm]
official_docs: https://kubernetes.io/docs/concepts/cluster-administration/
status: complete
difficulty: expert
last_updated: 2026-03-26
---

# Multi-Cluster Kubernetes

## Panoramica

Una strategia **multi-cluster** distribuisce i workload Kubernetes su più cluster indipendenti invece di un singolo cluster monolitico. Ogni cluster mantiene il proprio control plane, etcd e confini di failure. La gestione centralizzata avviene tramite tool dedicati che operano sopra i cluster.

**Quando adottare multi-cluster:**
- 3+ ambienti da gestire (dev / staging / prod) con isolamento completo
- Requisiti di geo-distribuzione o compliance (GDPR, residenza dati)
- Workload critici che richiedono fault isolation reale (un cluster in crash non impatta gli altri)
- Team multipli con ownership di cluster separati
- Limiti di scalabilità di un singolo cluster (>5000 nodi, >150K pod)

**Quando NON adottare:**
- Meno di 3 cluster → overhead non giustificato, namespaces sufficienti
- Team piccolo senza skill di piattaforma → la complessità operativa è alta
- Workload fortemente interdipendenti che richiedono latenza sub-millisecondo → mantenerli sullo stesso cluster

```
Multi-Cluster Topology — Pattern Hub and Spoke

  ┌──────────────────────────────────────────────┐
  │  MANAGEMENT CLUSTER (Hub)                    │
  │  ┌─────────────┐  ┌──────────────────────┐   │
  │  │ Cluster API │  │ Argo CD / Fleet /    │   │
  │  │ (lifecycle) │  │ Rancher (deploy)     │   │
  │  └──────┬──────┘  └──────────┬───────────┘   │
  └─────────┼────────────────────┼───────────────┘
            │  provision         │  deploy workload
     ┌──────┼──────┬─────────────┼──────────┐
     ▼      ▼      ▼             ▼          ▼
  ┌─────┐ ┌─────┐ ┌─────┐    ┌─────┐   ┌─────┐
  │dev  │ │stg  │ │prod │    │prod │   │prod │
  │EU-W │ │EU-W │ │EU-W │    │US-E │   │AP-SE│
  └─────┘ └─────┘ └─────┘    └─────┘   └─────┘
  Workload Clusters (Spoke)
```

---

## Cluster API (CAPI) — Lifecycle Management

**Cluster API** è lo standard Kubernetes-native per il provisioning e lifecycle management dei cluster. Usa CRD per descrivere cluster come oggetti K8s e riconcilia lo stato desiderato.

### Architettura CAPI

```
Cluster API — Componenti

  Management Cluster
  ┌──────────────────────────────────────────┐
  │  Core Provider (cluster-api)             │
  │  ├── Cluster controller                  │
  │  ├── Machine controller                  │
  │  └── MachineSet/MachineDeployment ctrl   │
  │                                          │
  │  Infrastructure Provider (ex: CAPV, CAPA)│
  │  ├── AWSCluster controller               │
  │  ├── AWSMachine controller               │
  │  └── Crea risorse cloud reali (EC2, VPC) │
  │                                          │
  │  Control Plane Provider (kubeadm, etc.)  │
  │  └── KubeadmControlPlane controller      │
  │                                          │
  │  Bootstrap Provider (kubeadm)            │
  │  └── KubeadmConfig → cloud-init/ignition │
  └──────────────────────────────────────────┘
```

### Installazione e provisioning (AWS esempio)

```bash
# Installa clusterctl
curl -L https://github.com/kubernetes-sigs/cluster-api/releases/latest/download/clusterctl-linux-amd64 \
  -o /usr/local/bin/clusterctl && chmod +x /usr/local/bin/clusterctl

# Inizializza management cluster con provider AWS
export AWS_REGION=eu-west-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
clusterawsadm bootstrap iam create-cloudformation-stack
export AWS_B64ENCODED_CREDENTIALS=$(clusterawsadm bootstrap credentials encode-as-profile)

clusterctl init --infrastructure aws \
  --control-plane kubeadm \
  --bootstrap kubeadm

# Genera manifest per un nuovo workload cluster
clusterctl generate cluster prod-eu-west-1 \
  --kubernetes-version v1.29.0 \
  --control-plane-machine-count=3 \
  --worker-machine-count=5 \
  --infrastructure aws > prod-cluster.yaml

# Deploy del cluster
kubectl apply -f prod-cluster.yaml

# Monitora il provisioning
kubectl get cluster,machine,machinedeployment -n default
clusterctl describe cluster prod-eu-west-1

# Ottieni il kubeconfig del nuovo cluster
clusterctl get kubeconfig prod-eu-west-1 > prod-eu-west-1.kubeconfig
```

### Manifest Cluster CAPI

```yaml
# Cluster object
apiVersion: cluster.x-k8s.io/v1beta1
kind: Cluster
metadata:
  name: prod-eu-west-1
  namespace: default
spec:
  clusterNetwork:
    pods:
      cidrBlocks: ["192.168.0.0/16"]
    services:
      cidrBlocks: ["10.128.0.0/12"]
  controlPlaneRef:
    apiVersion: controlplane.cluster.x-k8s.io/v1beta1
    kind: KubeadmControlPlane
    name: prod-eu-west-1-control-plane
  infrastructureRef:
    apiVersion: infrastructure.cluster.x-k8s.io/v1beta2
    kind: AWSCluster
    name: prod-eu-west-1

---
# MachineDeployment per i worker nodes
apiVersion: cluster.x-k8s.io/v1beta1
kind: MachineDeployment
metadata:
  name: prod-eu-west-1-workers
spec:
  clusterName: prod-eu-west-1
  replicas: 5
  selector:
    matchLabels:
      cluster.x-k8s.io/cluster-name: prod-eu-west-1
  template:
    spec:
      version: v1.29.0
      bootstrap:
        configRef:
          kind: KubeadmConfigTemplate
          name: prod-eu-west-1-worker-bootstrap
      infrastructureRef:
        kind: AWSMachineTemplate
        name: prod-eu-west-1-worker-machine
```

!!! warning "CAPI in produzione"
    CAPI gestisce risorse cloud reali: un errore in un MachineDeployment può terminare nodi in produzione. Usa sempre `--dry-run` per verificare i manifest, e proteggili con policy OPA/Kyverno prima di applicarli.

---

## Argo CD Multi-Cluster

**Argo CD** supporta il deploy su cluster multipli nativamente: un'istanza centralizzata gestisce le ApplicationSet che distribuiscono workload su N cluster registrati.

### Registrazione cluster in Argo CD

```bash
# Aggiungi un cluster remoto (usa il kubeconfig corrente)
argocd cluster add prod-eu-west-1 \
  --kubeconfig ~/.kube/prod-eu-west-1.kubeconfig \
  --name prod-eu-west-1

# Verifica cluster registrati
argocd cluster list
# SERVER                          NAME              STATUS  MESSAGE
# https://10.0.0.1:6443           in-cluster        OK
# https://prod-eu.example.com     prod-eu-west-1    OK
# https://prod-us.example.com     prod-us-east-1    OK
```

### ApplicationSet — Deploy su cluster multipli

```yaml
# ApplicationSet con ClusterGenerator: deploy automatico su ogni cluster registrato
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: guestbook-all-clusters
  namespace: argocd
spec:
  generators:
    - clusters:
        # Seleziona solo cluster con questo label
        selector:
          matchLabels:
            environment: production
  template:
    metadata:
      name: "guestbook-{{name}}"      # nome dinamico per cluster
    spec:
      project: default
      source:
        repoURL: https://github.com/myorg/guestbook
        targetRevision: HEAD
        path: "k8s/overlays/{{metadata.labels.region}}"  # path per cluster
      destination:
        server: "{{server}}"           # URL cluster automatico
        namespace: guestbook
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

```yaml
# ApplicationSet con Matrix generator: ambiente × cluster
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-matrix
spec:
  generators:
    - matrix:
        generators:
          - list:
              elements:
                - service: frontend
                - service: backend
                - service: worker
          - clusters:
              selector:
                matchLabels:
                  environment: production
  template:
    metadata:
      name: "{{service}}-{{name}}"
    spec:
      source:
        path: "services/{{service}}"
      destination:
        server: "{{server}}"
        namespace: "{{service}}"
```

---

## Rancher & Fleet

**Rancher** è una piattaforma di gestione multi-cluster con UI, RBAC, monitoring integrati. **Fleet** è il motore GitOps di Rancher per la distribuzione continua su fleet di cluster.

### Fleet — GitOps per 1000 cluster

Fleet scala fino a migliaia di cluster tramite concetti di **BundleDeployment** e **GitRepo**.

```yaml
# GitRepo: sorgente Git da sincronizzare su cluster target
apiVersion: fleet.cattle.io/v1alpha1
kind: GitRepo
metadata:
  name: my-app
  namespace: fleet-default    # fleet-default = tutti i downstream cluster
spec:
  repo: https://github.com/myorg/k8s-configs
  branch: main
  paths:
    - apps/my-app             # sincronizza solo questa directory
  targets:
    # Target per label cluster
    - name: production
      clusterSelector:
        matchLabels:
          env: production
      # Override per ambiente production
      helm:
        values:
          replicaCount: 3
          resources:
            limits:
              memory: 512Mi
    - name: staging
      clusterSelector:
        matchLabels:
          env: staging
      helm:
        values:
          replicaCount: 1
```

```bash
# fleet CLI: stato della distribuzione
fleet get gitrepo my-app -n fleet-default
# NAME     REPO                          COMMIT   BUNDLEDEPLOYMENTS-READY
# my-app   https://github.com/myorg/... abc123   45/45

# Dettaglio per cluster
fleet get bundledeployment -A | grep my-app
```

!!! tip "Fleet vs Argo CD"
    Usa **Fleet** quando hai già Rancher e vuoi zero overhead di setup — è integrato nativamente. Usa **Argo CD** quando vuoi più flessibilità nelle sync strategies (hooks, waves, health checks custom) e una UI dedicata al GitOps. Non sono mutualmente esclusivi: alcuni team usano Rancher per cluster lifecycle e Argo CD per application delivery.

---

## Crossplane — Infrastructure as Kubernetes

**Crossplane** trasforma il management cluster in un piano di controllo universale: provisiona risorse cloud (RDS, S3, GKE, AKS) come se fossero oggetti Kubernetes nativi.

### Architettura Crossplane

```
Crossplane — Flusso di provisioning

  Developer             Management Cluster          Cloud Provider
  ┌────────┐           ┌────────────────────┐       ┌──────────┐
  │kubectl │──apply──▶│  Composite Resource │──────▶│  AWS RDS │
  │apply   │           │  (XPostgreSQLDB)   │       │  (reale) │
  │XR.yaml │           │                    │       └──────────┘
  └────────┘           │  Composition       │
                       │  ├── RDSInstance   │       ┌──────────┐
                       │  ├── DBSubnetGroup │──────▶│  VPC SG  │
                       │  └── SecurityGroup │       └──────────┘
                       └────────────────────┘
```

```yaml
# Composite Resource Claim — usata dai developer (API semplice)
apiVersion: database.myplatform.io/v1alpha1
kind: PostgreSQLDatabase
metadata:
  name: my-app-db
  namespace: my-team
spec:
  parameters:
    size: medium          # tradotto in instance type dalla Composition
    version: "15"
    region: eu-west-1
  writeConnectionSecretToRef:
    name: my-app-db-conn  # secret con host/port/user/password creato auto
```

```yaml
# Composition — usata dal platform team (implementazione)
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: postgresql-aws
spec:
  compositeTypeRef:
    apiVersion: database.myplatform.io/v1alpha1
    kind: XPostgreSQLDatabase
  resources:
    - name: rds-instance
      base:
        apiVersion: rds.aws.upbound.io/v1beta1
        kind: Instance
        spec:
          forProvider:
            region: eu-west-1
            engine: postgres
            instanceClass: db.t3.medium
            allocatedStorage: 20
      patches:
        # Il developer specifica "medium" → Composition traduce in instance type
        - fromFieldPath: spec.parameters.size
          toFieldPath: spec.forProvider.instanceClass
          transforms:
            - type: map
              map:
                small: db.t3.small
                medium: db.t3.medium
                large: db.r6g.xlarge
```

---

## KubeFed v2 — Federation Control Plane

!!! warning "Status KubeFed"
    KubeFed v2 è in stato di bassa adozione. Il progetto è stato archiviato nel 2023. Per nuovi deployment preferire **Open Cluster Management (OCM)** o **Clusternet** come alternative attive.

```yaml
# FederatedDeployment — propaga un Deployment su cluster federati
apiVersion: types.kubefed.io/v1beta1
kind: FederatedDeployment
metadata:
  name: my-app
  namespace: production
spec:
  template:
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: my-app
  placement:
    clusters:
      - name: cluster-eu
      - name: cluster-us
  overrides:
    - clusterName: cluster-eu
      clusterOverrides:
        - path: /spec/replicas
          value: 3
    - clusterName: cluster-us
      clusterOverrides:
        - path: /spec/replicas
          value: 5
```

---

## Networking Multi-Cluster

Connettere cluster separati richiede soluzioni dedicate per service discovery e traffico cross-cluster.

### Opzioni di connettività

```
Multi-Cluster Network Options

  1. VPN/Peering (base)
     cluster-A pod CIDR ←→ VPN/VPC Peering ←→ cluster-B pod CIDR
     ✓ Semplice  ✗ No service discovery K8s  ✗ CIDR overlap risk

  2. Service Mesh (Istio multi-cluster)
     cluster-A istio ←→ East-West Gateway ←→ cluster-B istio
     ✓ mTLS automatico  ✓ service discovery  ✓ traffic management

  3. Cluster Mesh (Cilium)
     cluster-A ←→ Cilium clustermesh-apiserver ←→ cluster-B
     ✓ L3/L4 policies cross-cluster  ✓ GlobalService  ✓ no overhead proxy

  4. Submariner
     cluster-A ←→ Broker ←→ cluster-B
     ✓ open source  ✓ multi-provider  ✗ single point of failure broker
```

### Cilium Cluster Mesh

```bash
# Abilita cluster mesh su entrambi i cluster
cilium clustermesh enable --context cluster-eu
cilium clustermesh enable --context cluster-us

# Connetti i cluster (bidirezionale)
cilium clustermesh connect \
  --context cluster-eu \
  --destination-context cluster-us

# Verifica connessione
cilium clustermesh status --context cluster-eu
```

```yaml
# GlobalService: service visibile in tutti i cluster del mesh
apiVersion: v1
kind: Service
metadata:
  name: my-service
  annotations:
    service.cilium.io/global: "true"         # visibile cross-cluster
    service.cilium.io/shared: "true"         # includi endpoint locali nel LB
spec:
  selector:
    app: my-service
  ports:
    - port: 80
```

### Istio Multi-Cluster (Primary-Remote)

```bash
# Setup Primary cluster (ha il control plane Istio)
istioctl install --set profile=default \
  --set values.pilot.env.EXTERNAL_ISTIOD=true \
  --context primary-cluster

# Setup Remote cluster (usa il control plane del primary)
istioctl install --set profile=remote \
  --set values.global.remotePilotAddress=$(kubectl get svc istiod \
    -n istio-system --context primary-cluster \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}') \
  --context remote-cluster

# Verifica connettività
istioctl remote-clusters --context primary-cluster
```

---

## Best Practices

!!! tip "Separazione cluster per ambiente"
    Usa cluster separati per prod/staging/dev: **non** usare namespace come sostituto dell'isolamento di cluster. Un bug nel control plane o un CRD mal configurato in staging non deve mai poter impattare prod. Il costo di cluster multipli è giustificato dall'isolamento dei blast radius.

!!! tip "Management cluster dedicato"
    Il management cluster (che ospita CAPI, Argo CD, Crossplane) NON deve eseguire workload applicativi. Mantienilo leggero, altamente disponibile (3 control plane nodes), e con accesso ristretto al solo platform team.

!!! warning "Kubeconfig e accesso multi-cluster"
    Non distribuire mai kubeconfig con permessi cluster-admin ai developer. Usa strumenti come **Rancher RBAC**, **Teleport**, o **kubelogin** con OIDC per accesso federato. Il kubeconfig del management cluster è la chiave di tutto il tuo fleet.

**Pattern di naming cluster:**
```
{ambiente}-{provider}-{region}-{indice}
prod-aws-eu-west-1-01
staging-gke-us-central-01
dev-kind-local-01
```

**Struttura GitOps raccomandata:**
```
infra-repo/
├── clusters/                  # 1 dir per cluster
│   ├── prod-aws-eu-west-1/
│   │   ├── cluster.yaml       # CAPI Cluster object
│   │   └── apps/              # ApplicationSet o Helm values
│   └── staging-gke-us/
│       └── ...
├── platform/                  # componenti platform-wide (monitoring, security)
│   ├── argocd/
│   ├── cert-manager/
│   └── external-secrets/
└── apps/                      # applicazioni business (per team)
    ├── team-checkout/
    └── team-catalog/
```

---

## Troubleshooting

**1. Cluster non raggiungibile da Argo CD**

```bash
# Sintomo: cluster in "Unknown" o "Error" state in Argo CD
# Causa: certificato scaduto o kubeconfig non aggiornato

# Verifica connettività diretta
kubectl cluster-info --kubeconfig ~/.kube/prod-eu.kubeconfig

# Rigenera e re-registra il cluster secret in Argo CD
argocd cluster rm prod-eu-west-1
argocd cluster add prod-eu-west-1 \
  --kubeconfig ~/.kube/prod-eu-west-1.kubeconfig
```

**2. CAPI Machine stuck in Provisioning**

```bash
# Sintomo: kubectl get machine mostra Phase: Provisioning per >15 minuti
# Causa: quota cloud, security group, AMI non trovata

# Leggi gli eventi della Machine
kubectl describe machine <machine-name> -n default

# Leggi i log del provider controller
kubectl logs -n capi-system deployment/capi-controller-manager
kubectl logs -n capa-system deployment/capa-controller-manager  # per AWS

# Verifica quota AWS
aws service-quotas list-service-quotas --service-code ec2 \
  | jq '.Quotas[] | select(.QuotaName | contains("Running"))'
```

**3. Fleet BundleDeployment in error state**

```bash
# Sintomo: bundle non si propaga su alcuni cluster
# Verifica lo stato per cluster
kubectl get bundledeployment -A | grep -v Ready

# Dettaglio dell'errore
kubectl describe bundledeployment <name> -n fleet-default

# Forza re-sincronizzazione del GitRepo
kubectl annotate gitrepo my-app -n fleet-default \
  fleet.cattle.io/force-sync="$(date)"
```

**4. Latenza elevata cross-cluster con Cluster Mesh**

```bash
# Sintomo: latenza >50ms tra pod di cluster diversi
# Causa: routing subottimale o MTU mismatch

# Verifica stato cluster mesh Cilium
cilium clustermesh status --wait

# Controlla MTU configurato
kubectl exec -n kube-system ds/cilium -- cilium config | grep mtu

# Abilita direct routing (bypassa overlay quando possibile)
# In cilium values.yaml:
# tunnel: disabled
# autoDirectNodeRoutes: true
```

---

## Relazioni

??? info "Cluster API e Operators"
    CAPI usa il pattern Operator (controller + CRD) per gestire il lifecycle dei cluster. Comprendere come funzionano gli Operators è prerequisito per estendere CAPI con provider custom.

    **Approfondimento →** [Operators e CRD](operators-crd.md)

??? info "Networking intra-cluster"
    Prima di affrontare il networking multi-cluster, è fondamentale avere solide basi sul networking intra-cluster: CNI, Service types, DNS interno.

    **Approfondimento →** [Kubernetes Networking](networking.md)

??? info "Sicurezza multi-cluster"
    In ambiente multi-cluster, RBAC e mTLS diventano ancora più critici: un'identità compromessa su un cluster non deve propagarsi agli altri.

    **Approfondimento →** [Sicurezza Kubernetes](sicurezza.md)

---

## Riferimenti

- [Cluster API Book](https://cluster-api.sigs.k8s.io/) — documentazione ufficiale CAPI
- [Argo CD ApplicationSet](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/) — multi-cluster deploy
- [Fleet Documentation](https://fleet.rancher.io/) — GitOps per fleet di cluster
- [Crossplane Docs](https://docs.crossplane.io/) — infrastructure as Kubernetes
- [Cilium Cluster Mesh](https://docs.cilium.io/en/stable/network/clustermesh/) — networking multi-cluster
- [Open Cluster Management](https://open-cluster-management.io/) — alternativa a KubeFed
