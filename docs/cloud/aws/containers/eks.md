---
title: "Amazon EKS — Elastic Kubernetes Service"
slug: eks
category: cloud/aws
tags: [aws, eks, kubernetes, node-groups, fargate, irsa, karpenter, add-ons, upgrade, managed-kubernetes]
search_keywords: [Amazon EKS, Elastic Kubernetes Service, EKS managed node group, self-managed node group, EKS Fargate, Fargate profile, IRSA, IAM Roles for Service Accounts, EKS Pod Identity, EKS add-ons, EKS upgrade, eksctl, aws-auth ConfigMap, EKS access entries, Karpenter, Cluster Autoscaler, AWS Load Balancer Controller, EKS networking, VPC CNI, CoreDNS, kube-proxy, EKS Blueprint, EKS Anywhere, EKS Distro, EKS control plane, EKS worker nodes, managed Kubernetes AWS, Kubernetes su AWS, container orchestration AWS, EKS cluster, EKS security groups, EKS RBAC, Pod Security Standards, EKS logging, EKS observability, EKS cost optimization, Graviton EKS, spot instances EKS]
parent: cloud/aws/containers/_index
related: [cloud/aws/compute/containers-ecs-eks, cloud/aws/iam/policies-avanzate, cloud/aws/networking/vpc, cloud/aws/networking/vpc-avanzato, cloud/aws/security/kms-secrets, cloud/aws/monitoring/cloudwatch, cloud/aws/monitoring/observability, containers/kubernetes/architettura, containers/kubernetes/networking, containers/kubernetes/sicurezza]
official_docs: https://docs.aws.amazon.com/eks/latest/userguide/
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# Amazon EKS — Elastic Kubernetes Service

**Amazon EKS** è il servizio Kubernetes gestito di AWS: AWS gestisce il control plane (API server, etcd, controller manager, scheduler) in modo completamente managed, con alta disponibilità multi-AZ garantita, patch automatiche e SLA del 99.95%. Il cliente gestisce i worker nodes, le configurazioni applicative e gli add-on.

EKS è la scelta standard per organizzazioni enterprise che:
- Hanno già competenze Kubernetes o team che utilizzano K8s su altri cloud
- Necessitano di portabilità (workload che girano anche on-premises o multi-cloud)
- Richiedono l'ecosistema Kubernetes completo: CRD, Operators, Helm, service mesh
- Devono rispettare policy di compliance che richiedono Kubernetes come standard

**Quando valutare ECS invece di EKS:**
- Team senza esperienza Kubernetes — ECS ha curva di apprendimento molto più bassa
- Workloads semplici, stateless, solo su AWS — ECS si integra più profondamente con servizi AWS nativi
- Budget limitato — il control plane EKS costa $0.10/ora (~$73/mese) per cluster; ECS è gratuito

---

## Architettura EKS

```
EKS Architecture (semplificata)

  ┌─────────────────────────── AWS Account ──────────────────────────────┐
  │                                                                       │
  │  ┌─── AWS Managed Control Plane ───┐    ┌── Customer VPC ──────────┐ │
  │  │  API Server (HA, multi-AZ)      │◄──►│                          │ │
  │  │  etcd (multi-AZ, encrypted)     │    │  ┌── Private Subnets ──┐ │ │
  │  │  Controller Manager             │    │  │  Node Group 1 (AZ-a)│ │ │
  │  │  Scheduler                      │    │  │  Node Group 2 (AZ-b)│ │ │
  │  └─────────────────────────────────┘    │  │  Node Group 3 (AZ-c)│ │ │
  │                                         │  └─────────────────────┘ │ │
  │  ┌─── AWS EKS Add-ons ─────────────┐    │  ┌── Public Subnets ───┐ │ │
  │  │  VPC CNI (networking)           │    │  │  ALB / NLB          │ │ │
  │  │  CoreDNS                        │    │  └─────────────────────┘ │ │
  │  │  kube-proxy                     │    │                          │ │
  │  │  EBS CSI Driver                 │    │  Fargate Profiles        │ │
  │  │  EFS CSI Driver                 │    │  (namespace-based)       │ │
  │  └─────────────────────────────────┘    └──────────────────────────┘ │
  └───────────────────────────────────────────────────────────────────────┘
```

Il control plane si trova in un VPC gestito da AWS (non visibile al cliente). La comunicazione tra control plane e worker nodes avviene tramite un endpoint privato o pubblico configurabile.

---

## Creazione Cluster

### Con eksctl (raccomandato)

`eksctl` è lo strumento ufficiale per la gestione del lifecycle di cluster EKS. Genera automaticamente lo stack CloudFormation, le IAM Role necessarie, e configura il networking.

```yaml
# cluster.yaml — configurazione dichiarativa completa
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: production
  region: eu-central-1
  version: "1.31"
  tags:
    Environment: production
    Team: platform

# OIDC provider necessario per IRSA (IAM Roles for Service Accounts)
iam:
  withOIDC: true

# Endpoint privato (nodi comunicano con control plane via VPC, non Internet)
privateCluster:
  enabled: false    # true per cluster completamente privato (richiede VPC endpoints)

vpc:
  id: vpc-xxxxxxxxxx
  subnets:
    private:
      eu-central-1a: { id: subnet-private-a }
      eu-central-1b: { id: subnet-private-b }
      eu-central-1c: { id: subnet-private-c }
    public:
      eu-central-1a: { id: subnet-public-a }
      eu-central-1b: { id: subnet-public-b }
      eu-central-1c: { id: subnet-public-c }

managedNodeGroups:
  # Node group general purpose (Graviton)
  - name: workers-general
    instanceType: m7g.xlarge      # Graviton 3 — ~20% più economico vs x86 equivalente
    amiFamily: AmazonLinux2023
    minSize: 3
    maxSize: 20
    desiredCapacity: 6            # 2 per AZ
    volumeSize: 50
    volumeType: gp3
    privateNetworking: true       # nodi SOLO in subnet private
    updateConfig:
      maxUnavailable: 1           # rolling update: 1 nodo alla volta
    labels:
      workload-type: general
    tags:
      k8s.io/cluster-autoscaler/enabled: "true"
      k8s.io/cluster-autoscaler/production: "owned"
    iam:
      attachPolicyARNs:
        - arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
        - arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
        - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy

  # Node group spot per batch/non-critici
  - name: workers-spot
    instanceTypes: ["m7g.large", "m7g.xlarge", "m6g.xlarge", "m6g.large"]
    spot: true
    minSize: 0
    maxSize: 50
    desiredCapacity: 0
    privateNetworking: true
    taints:
      - key: spot
        value: "true"
        effect: NoSchedule
    labels:
      workload-type: batch

fargateProfiles:
  - name: serverless
    selectors:
      - namespace: serverless
      - namespace: kube-system
        labels:
          fargate: "true"

addons:
  - name: vpc-cni
    version: latest
    configurationValues: |
      enableNetworkPolicy: "true"
  - name: coredns
    version: latest
  - name: kube-proxy
    version: latest
  - name: aws-ebs-csi-driver
    version: latest
    serviceAccountRoleARN: arn:aws:iam::123456789012:role/EKS-EBSCSIRole
  - name: aws-efs-csi-driver
    version: latest
    serviceAccountRoleARN: arn:aws:iam::123456789012:role/EKS-EFSCSIRole

cloudWatch:
  clusterLogging:
    enableTypes: ["api", "audit", "authenticator", "controllerManager", "scheduler"]
    logRetentionInDays: 30
```

```bash
# Creare cluster dalla configurazione
eksctl create cluster -f cluster.yaml

# Aggiungere kubeconfig locale
aws eks update-kubeconfig \
    --region eu-central-1 \
    --name production \
    --alias production   # alias per kubectl context

# Verificare stato cluster
kubectl get nodes -o wide
kubectl get pods -A
eksctl get cluster --name production
```

### Con AWS CLI

```bash
# Creare cluster (solo control plane — nodi da aggiungere separatamente)
aws eks create-cluster \
    --name production \
    --kubernetes-version 1.31 \
    --role-arn arn:aws:iam::123456789012:role/EKSClusterRole \
    --resources-vpc-config \
        subnetIds=subnet-a,subnet-b,subnet-c,\
        securityGroupIds=sg-cluster,\
        endpointPrivateAccess=true,\
        endpointPublicAccess=true,\
        publicAccessCidrs=1.2.3.4/32    # limitare accesso pubblico all'API server

# Abilitare OIDC provider (necessario per IRSA)
aws eks associate-identity-provider-config \
    --cluster-name production \
    --oidc '{
        "issuerUrl": "https://oidc.eks.eu-central-1.amazonaws.com/id/XXXXXXXX"
    }'
```

---

## Node Groups

EKS supporta tre modalità per i worker nodes, ognuna con diverso livello di controllo e gestione.

### Managed Node Groups

I **Managed Node Groups** sono il metodo raccomandato: AWS gestisce il provisioning, il lifecycle e gli aggiornamenti dei nodi. Supportano upgrade senza downtime tramite rolling update configurabile.

```bash
# Creare managed node group
aws eks create-nodegroup \
    --cluster-name production \
    --nodegroup-name workers-general \
    --node-role arn:aws:iam::123456789012:role/EKSNodeRole \
    --subnets subnet-a subnet-b subnet-c \
    --instance-types m7g.xlarge \
    --ami-type AL2023_ARM_64_STANDARD \
    --capacity-type ON_DEMAND \
    --scaling-config minSize=3,maxSize=20,desiredSize=6 \
    --disk-size 50 \
    --update-config maxUnavailablePercentage=25 \
    --labels workload-type=general \
    --tags Environment=production

# Aggiornare node group (nuova AMI / cambiare parametri)
aws eks update-nodegroup-version \
    --cluster-name production \
    --nodegroup-name workers-general \
    --release-version latest   # oppure versione specifica

# Scalare manualmente
aws eks update-nodegroup-config \
    --cluster-name production \
    --nodegroup-name workers-general \
    --scaling-config minSize=3,maxSize=20,desiredSize=9
```

### Self-Managed Node Groups

I nodi self-managed offrono il massimo controllo (AMI custom, configurazioni specifiche del kernel, GPU driver personalizzati) ma richiedono gestione manuale degli aggiornamenti.

```bash
# Launch Template per nodi self-managed
aws ec2 create-launch-template \
    --launch-template-name eks-workers \
    --version-description v1 \
    --launch-template-data '{
        "ImageId": "ami-eks-al2023",
        "InstanceType": "m7g.xlarge",
        "IamInstanceProfile": {"Arn": "arn:aws:iam::123456789012:instance-profile/EKSNode"},
        "UserData": "base64-encoded-bootstrap-script",
        "BlockDeviceMappings": [{
            "DeviceName": "/dev/xvda",
            "Ebs": {"VolumeSize": 50, "VolumeType": "gp3", "Encrypted": true}
        }],
        "MetadataOptions": {"HttpTokens": "required", "HttpPutResponseHopLimit": 2}
    }'

# Bootstrap script per unire il nodo al cluster
# (incluso nell'AMI ufficiale EKS)
/etc/eks/bootstrap.sh production \
    --b64-cluster-ca <CA_DATA> \
    --apiserver-endpoint https://ENDPOINT.gr7.eu-central-1.eks.amazonaws.com \
    --kubelet-extra-args '--node-labels=workload-type=custom'
```

### Fargate Profiles

Con **Fargate Profiles**, i pod vengono schedulati su infrastruttura serverless: nessun nodo da gestire, billing per pod (CPU + memoria allocata), scaling automatico. Ideale per workload che non richiedono accesso root o volumi hostPath.

```yaml
# Creare Fargate Profile tramite YAML eksctl
fargateProfiles:
  - name: app-serverless
    selectors:
      # Tutti i pod nel namespace "serverless" usano Fargate
      - namespace: serverless
      # Pod con label specifica in qualsiasi namespace
      - namespace: default
        labels:
          compute: fargate
```

```bash
# Creare via CLI
aws eks create-fargate-profile \
    --cluster-name production \
    --fargate-profile-name app-serverless \
    --pod-execution-role-arn arn:aws:iam::123456789012:role/EKSFargatePodExecutionRole \
    --subnets subnet-private-a subnet-private-b subnet-private-c \
    --selectors '[
        {"namespace": "serverless"},
        {"namespace": "default", "labels": {"compute": "fargate"}}
    ]'
```

!!! warning "Limitazioni Fargate"
    - Nessun supporto per DaemonSet (i DaemonSet non vengono schedulati su Fargate)
    - Nessun volume `hostPath` o `local`
    - Nessun privileged container
    - Max 4 vCPU e 30 GB RAM per pod
    - Richiede subnet private (i pod Fargate non possono essere in subnet pubbliche)
    - I pod usano un ENI dedicato: verificare i limiti di ENI per subnet

---

## IRSA — IAM Roles for Service Accounts

**IRSA** permette ai pod di assumere IAM Role specifici senza access key statiche. Funziona tramite OIDC Federation: il cluster EKS ha un OIDC provider, e AWS STS valida i token JWT dei ServiceAccount per rilasciare credenziali temporanee.

```bash
# 1. Verificare che OIDC provider sia configurato
aws eks describe-cluster \
    --name production \
    --query "cluster.identity.oidc.issuer" \
    --output text
# Output: https://oidc.eks.eu-central-1.amazonaws.com/id/XXXXXXXX

# 2. Creare OIDC provider in IAM (se non esiste)
eksctl utils associate-iam-oidc-provider \
    --cluster production \
    --approve

# 3. Creare IAM Role con Trust Policy per il ServiceAccount specifico
OIDC_PROVIDER=$(aws eks describe-cluster --name production \
    --query "cluster.identity.oidc.issuer" --output text | sed -e "s/^https:\/\///")

aws iam create-role \
    --role-name EKS-MyApp-S3Role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::123456789012:oidc-provider/'$OIDC_PROVIDER'"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "'$OIDC_PROVIDER':sub": "system:serviceaccount:myapp:myapp-sa",
                    "'$OIDC_PROVIDER':aud": "sts.amazonaws.com"
                }
            }
        }]
    }'

# 4. Attaccare policy al role
aws iam attach-role-policy \
    --role-name EKS-MyApp-S3Role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# 5. Creare ServiceAccount annotato (metodo via eksctl)
eksctl create iamserviceaccount \
    --cluster production \
    --namespace myapp \
    --name myapp-sa \
    --attach-role-arn arn:aws:iam::123456789012:role/EKS-MyApp-S3Role \
    --approve
```

```yaml
# ServiceAccount con annotazione IRSA
apiVersion: v1
kind: ServiceAccount
metadata:
  name: myapp-sa
  namespace: myapp
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/EKS-MyApp-S3Role
    # Token scade dopo 24h di default (configurabile)
    eks.amazonaws.com/token-expiration: "86400"

---
# Deployment che usa il ServiceAccount IRSA
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: myapp
spec:
  template:
    spec:
      serviceAccountName: myapp-sa   # usa SA con IRSA
      containers:
        - name: myapp
          image: 123456789012.dkr.ecr.eu-central-1.amazonaws.com/myapp:v1.0.0
          env:
            - name: AWS_REGION
              value: eu-central-1
          # AWS SDK legge automaticamente le credenziali da:
          # AWS_WEB_IDENTITY_TOKEN_FILE e AWS_ROLE_ARN (iniettati automaticamente)
```

!!! tip "EKS Pod Identity — alternativa moderna a IRSA"
    Dal 2023, AWS ha introdotto **EKS Pod Identity** come alternativa semplificata a IRSA. Non richiede OIDC provider per account, e la configurazione è interamente lato AWS (non richiede annotazioni sul ServiceAccount).

    ```bash
    # Abilitare EKS Pod Identity Agent (add-on)
    aws eks create-addon \
        --cluster-name production \
        --addon-name eks-pod-identity-agent \
        --addon-version latest

    # Creare associazione Pod Identity
    aws eks create-pod-identity-association \
        --cluster-name production \
        --namespace myapp \
        --service-account myapp-sa \
        --role-arn arn:aws:iam::123456789012:role/EKS-MyApp-S3Role
    ```

---

## Add-on Management

Gli **EKS Managed Add-ons** sono componenti di cluster gestiti da AWS: aggiornamenti con un comando, compatibilità verificata con la versione K8s, patch di sicurezza automatiche.

### Add-on Core (obbligatori)

```bash
# Listare add-on disponibili per la versione K8s
aws eks describe-addon-versions \
    --kubernetes-version 1.31 \
    --query 'addons[].{Name:addonName, Versions:addonVersions[0].addonVersion}' \
    --output table

# Installare/aggiornare add-on
aws eks create-addon \
    --cluster-name production \
    --addon-name vpc-cni \
    --addon-version v1.19.0-eksbuild.1 \
    --service-account-role-arn arn:aws:iam::123456789012:role/EKS-VPCCNIRole \
    --configuration-values '{"enableNetworkPolicy":"true"}' \
    --resolve-conflicts OVERWRITE   # OVERWRITE: sovrascrive config esistente; PRESERVE: mantiene

# Aggiornare add-on esistente
aws eks update-addon \
    --cluster-name production \
    --addon-name coredns \
    --addon-version latest \
    --resolve-conflicts OVERWRITE

# Status add-on
aws eks describe-addon \
    --cluster-name production \
    --addon-name vpc-cni \
    --query 'addon.{Status:status, Version:addonVersion, Health:health}'
```

### Add-on Helm Essenziali

```bash
# ─── AWS Load Balancer Controller ───────────────────────────────────────────
# Gestisce ALB (Ingress) e NLB (Service type LoadBalancer)
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
    --namespace kube-system \
    --set clusterName=production \
    --set serviceAccount.create=false \
    --set serviceAccount.name=aws-load-balancer-controller \
    --set region=eu-central-1 \
    --set vpcId=vpc-xxxxxxxxxx

# ─── Karpenter (node autoprovisioner) ───────────────────────────────────────
# Sostituisce Cluster Autoscaler: provisioning nodi in secondi (non minuti)
helm upgrade --install karpenter oci://public.ecr.aws/karpenter/karpenter \
    --version "1.0.4" \
    --namespace kube-system \
    --set settings.clusterName=production \
    --set settings.interruptionQueue=production-karpenter \
    --set controller.resources.requests.cpu=1 \
    --set controller.resources.requests.memory=1Gi

# ─── External Secrets Operator ──────────────────────────────────────────────
# Sincronizza segreti da AWS Secrets Manager / Parameter Store in K8s Secrets
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
    --namespace external-secrets \
    --create-namespace \
    --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=\
arn:aws:iam::123456789012:role/EKS-ExternalSecretsRole
```

```yaml
# Karpenter NodePool — definisce caratteristiche dei nodi da creare
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general
spec:
  template:
    metadata:
      labels:
        workload-type: general
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["arm64"]             # Graviton — preferito per costo
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"] # prova spot, fallback on-demand
        - key: karpenter.k8s.aws/instance-family
          operator: In
          values: ["m7g", "m6g", "c7g", "c6g"]
        - key: karpenter.k8s.aws/instance-size
          operator: NotIn
          values: ["nano", "micro", "small"]
  limits:
    cpu: "500"
    memory: 2000Gi
  disruption:
    consolidationPolicy: WhenUnderutilized
    consolidateAfter: 30s
    budgets:
      - nodes: "10%"                    # al massimo 10% dei nodi rimossi in una volta

---
# EC2NodeClass — definisce la configurazione EC2
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2023
  role: EKSNodeRole
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: production
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: production
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 50Gi
        volumeType: gp3
        encrypted: true
```

---

## Networking

### VPC CNI

Il **VPC CNI** (aws-node DaemonSet) assegna IP VPC nativi ai pod — ogni pod ottiene un IP direttamente dalla subnet VPC. Questo semplifica il networking (nessun overlay NAT) ma richiede pianificazione degli IP.

```bash
# Calcolo IP disponibili per pod
# Ogni nodo può avere al massimo (max_ENI × max_IPs_per_ENI - 1) pod
# m7g.xlarge: 4 ENI × 15 IP = 60 pod max

# Abilitare prefix delegation (aumenta drasticamente la capacità pod)
# Ogni ENI può avere prefissi /28 invece di IP singoli → 16× più pod
kubectl set env daemonset aws-node \
    -n kube-system \
    ENABLE_PREFIX_DELEGATION=true \
    WARM_PREFIX_TARGET=1

# Verificare configurazione CNI
kubectl describe daemonset aws-node -n kube-system | grep -A5 "Environment"
```

```yaml
# Security Group per Pod (EKS-specific)
# Permette di applicare Security Group AWS direttamente ai pod
apiVersion: vpcresources.k8s.aws/v1beta1
kind: SecurityGroupPolicy
metadata:
  name: myapp-sgp
  namespace: myapp
spec:
  podSelector:
    matchLabels:
      app: myapp
  securityGroups:
    groupIds:
      - sg-myapp-pods    # Security Group specifico per i pod myapp
```

### Load Balancer con AWS LB Controller

```yaml
# Ingress con ALB (Application Load Balancer)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: myapp
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing     # o internal
    alb.ingress.kubernetes.io/target-type: ip             # ip (raccomandato) o instance
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...:certificate/xxx
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/group.name: production-apps # condivide ALB tra più Ingress
spec:
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp
                port:
                  number: 8080

---
# Service con NLB (Network Load Balancer)
apiVersion: v1
kind: Service
metadata:
  name: myapp-nlb
  namespace: myapp
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: external
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
    service.beta.kubernetes.io/aws-load-balancer-scheme: internal
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
spec:
  type: LoadBalancer
  selector:
    app: myapp
  ports:
    - port: 443
      targetPort: 8443
```

---

## Sicurezza e RBAC

### Access Management (aws-auth e Access Entries)

```bash
# Metodo moderno: EKS Access Entries (sostituisce aws-auth ConfigMap)
# Creare access entry per un utente IAM
aws eks create-access-entry \
    --cluster-name production \
    --principal-arn arn:aws:iam::123456789012:user/developer \
    --type STANDARD

# Associare policy di accesso
aws eks associate-access-policy \
    --cluster-name production \
    --principal-arn arn:aws:iam::123456789012:user/developer \
    --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy \
    --access-scope '{"type": "namespace", "namespaces": ["myapp", "staging"]}'

# Policy disponibili:
# AmazonEKSClusterAdminPolicy — cluster-admin
# AmazonEKSAdminPolicy        — admin su tutti i namespace
# AmazonEKSEditPolicy         — edit (no RBAC)
# AmazonEKSViewPolicy         — read-only

# Abilitare Access Entries sul cluster (disabilita aws-auth)
aws eks update-cluster-config \
    --name production \
    --access-config authenticationMode=API_AND_CONFIG_MAP  # o API
```

```yaml
# RBAC per team applicativo
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer
  namespace: myapp
rules:
  - apiGroups: ["", "apps", "batch"]
    resources: ["pods", "deployments", "services", "jobs", "configmaps"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
  - apiGroups: [""]
    resources: ["pods/log", "pods/exec"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: []   # nessun accesso ai secrets (IRSA/External Secrets gestisce i segreti)

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developer-binding
  namespace: myapp
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: developer
subjects:
  - kind: Group
    name: myapp-developers   # mappato a IAM role/user via Access Entry
    apiGroup: rbac.authorization.k8s.io
```

### Pod Security Standards

```yaml
# Abilitare Pod Security Standards per namespace (K8s 1.25+)
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted    # più restrittivo
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

!!! warning "Security Group per nodi EKS"
    I nodi EKS necessitano di regole specifiche nei Security Group:

    - **Nodi → API Server**: porta 443 outbound verso il Security Group del cluster
    - **API Server → Nodi**: porte 10250 (kubelet) e range 1025-65535 (webhook) inbound
    - **Nodi → Nodi**: tutto il traffico sulla porta 0-65535 all'interno del cluster SG
    - **Fargate → API Server**: porta 443 outbound

    Usare sempre Security Group separati per nodi, pod (SG per pod), e ALB.

---

## Upgrade Strategy

L'upgrade di un cluster EKS richiede pianificazione: il control plane viene aggiornato da AWS, ma i node groups e gli add-on devono essere aggiornati separatamente.

!!! warning "Ordine obbligatorio per l'upgrade"
    1. Aggiornare il **control plane** (EKS versione K8s)
    2. Aggiornare gli **add-on managed** (vpc-cni, coredns, kube-proxy)
    3. Aggiornare i **node groups** (rolling update)
    4. Verificare workload applicativi

```bash
# ─── Step 1: Pre-upgrade check ──────────────────────────────────────────────
# Verificare versione corrente e target disponibili
aws eks describe-cluster \
    --name production \
    --query 'cluster.{Version:version, Status:status}'

# Listare versioni disponibili
aws eks describe-addon-versions \
    --kubernetes-version 1.32 \
    --query 'addons[].addonName' \
    --output text

# Controllare deprecated APIs (fondamentale prima di ogni upgrade)
# kubectl convert è il comando per controllare compatibility
kubectl api-versions | sort

# ─── Step 2: Upgrade control plane ──────────────────────────────────────────
# Solo 1 minor version per volta (1.30 → 1.31, poi 1.31 → 1.32)
aws eks update-cluster-version \
    --name production \
    --kubernetes-version 1.32

# Monitorare progresso (può richiedere 10-20 minuti)
aws eks describe-update \
    --name production \
    --update-id $(aws eks list-updates --name production \
        --query 'updateIds[0]' --output text)

# ─── Step 3: Aggiornare add-on managed ──────────────────────────────────────
for addon in vpc-cni coredns kube-proxy aws-ebs-csi-driver; do
    echo "Aggiornamento add-on: $addon"
    aws eks update-addon \
        --cluster-name production \
        --addon-name $addon \
        --addon-version latest \
        --resolve-conflicts OVERWRITE

    # Attendere completamento
    aws eks wait addon-active \
        --cluster-name production \
        --addon-name $addon
done

# ─── Step 4: Aggiornare node groups ─────────────────────────────────────────
# Managed Node Groups: rolling update automatico
aws eks update-nodegroup-version \
    --cluster-name production \
    --nodegroup-name workers-general \
    --release-version latest

# Monitorare (può richiedere 20-40 minuti per node group grande)
eksctl get nodegroup \
    --cluster production \
    --name workers-general

# ─── Step 5: Verifiche post-upgrade ─────────────────────────────────────────
kubectl get nodes   # tutti Running con nuova versione K8s
kubectl get pods -A | grep -v Running | grep -v Completed   # nessun pod in errore
kubectl get events --sort-by='.lastTimestamp' | tail -20
```

### Upgrade con eksctl (automatico)

```bash
# Upgrade completo automatizzato con eksctl
eksctl upgrade cluster \
    --name production \
    --version 1.32 \
    --approve

# Upgrade node group con eksctl
eksctl upgrade nodegroup \
    --cluster production \
    --name workers-general \
    --kubernetes-version 1.32
```

---

## Osservabilità

```bash
# Abilitare Control Plane Logging su CloudWatch
aws eks update-cluster-config \
    --name production \
    --logging '{"clusterLogging":[{
        "types": ["api","audit","authenticator","controllerManager","scheduler"],
        "enabled": true
    }]}'

# Log Groups creati in CloudWatch:
# /aws/eks/production/cluster

# Container Insights (metriche pod/node su CloudWatch)
aws eks create-addon \
    --cluster-name production \
    --addon-name amazon-cloudwatch-observability \
    --addon-version latest \
    --service-account-role-arn arn:aws:iam::123456789012:role/EKS-CWObservabilityRole
```

```yaml
# Prometheus + Grafana via Helm (stack di osservabilità standard)
# kube-prometheus-stack include: Prometheus, Grafana, AlertManager, node-exporter
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

helm install kube-prometheus-stack \
    prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace \
    --set grafana.adminPassword=changeme \
    --set prometheus.prometheusSpec.retention=30d \
    --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=gp3 \
    --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi
```

---

## Best Practices

!!! tip "Cost Optimization"
    - Usare **Graviton** (ARM) per tutti i workload compatibili: 20-40% risparmio
    - Configurare **Spot Instances** per workload non critici/batch con Karpenter
    - Abilitare **Savings Plans** a livello di account per la quota EC2 baseline
    - Monitorare i pod con `requests` troppo alti vs utilizzo reale con Vertical Pod Autoscaler
    - Usare **Fargate** solo per workload che ne giustificano il costo (billing per pod)

!!! tip "Affidabilità"
    - Distribuire sempre i node group su **almeno 3 AZ** con `minSize ≥ 3`
    - Configurare `PodDisruptionBudget` per tutti i servizi critici
    - Usare `topologySpreadConstraints` per distribuire i pod sulle AZ
    - Impostare `maxUnavailable: 1` sugli upgrade dei node group in produzione
    - Testare gli upgrade su un cluster di staging prima della produzione

!!! tip "Sicurezza"
    - Abilitare sempre **IRSA** o **EKS Pod Identity** — mai access key statiche nei pod
    - Usare **External Secrets Operator** per sincronizzare segreti da Secrets Manager
    - Impostare `endpointPublicAccess: false` e usare VPN/Direct Connect per l'API server
    - Abilitare **AWS GuardDuty EKS Protection** per rilevare attività anomale nel cluster
    - Impostare `HttpTokens: required` (IMDSv2) nel Launch Template dei nodi

---

## Troubleshooting

**Nodi in stato `NotReady`**

```bash
# Verificare stato nodi e causa
kubectl describe node <NODE_NAME>
kubectl get events --field-selector involvedObject.name=<NODE_NAME>

# Cause comuni:
# - DiskPressure: disco pieno → aumentare volumeSize nel node group
# - MemoryPressure: RAM esaurita → ridurre density o aumentare instance type
# - NetworkPlugin not ready → problema VPC CNI, verificare aws-node pods
kubectl get pods -n kube-system -l k8s-app=aws-node

# Verificare logs VPC CNI
kubectl logs -n kube-system -l k8s-app=aws-node --tail=50
```

**Pod bloccati in `Pending`**

```bash
# Verificare eventi del pod
kubectl describe pod <POD_NAME> -n <NAMESPACE>

# Causa 1: Insufficient resources — nessun nodo con CPU/memoria disponibile
# → Karpenter/Cluster Autoscaler non ha provisioned un nuovo nodo?
kubectl get nodeclaim -A   # Karpenter
kubectl logs -n kube-system -l app.kubernetes.io/name=karpenter

# Causa 2: Taint/Toleration mismatch
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints

# Causa 3: Pod affinità non soddisfatta
kubectl get nodes --show-labels

# Causa 4: Fargate profile non matcha il namespace/labels del pod
aws eks describe-fargate-profile \
    --cluster-name production \
    --fargate-profile-name app-serverless
```

**Errore `ImagePullBackOff`**

```bash
# Verificare accesso ECR dal nodo
# Il node group deve avere AmazonEC2ContainerRegistryReadOnly policy

# Verificare se è un problema di rete (subnet privata senza NAT Gateway?)
kubectl describe pod <POD_NAME> -n <NAMESPACE> | grep -A5 "Events"

# Per Fargate: verificare che la Fargate pod execution role abbia ECR access
aws iam list-attached-role-policies \
    --role-name EKSFargatePodExecutionRole
```

**IRSA non funziona (credenziali non disponibili)**

```bash
# Verificare annotazione sul ServiceAccount
kubectl describe sa <SA_NAME> -n <NAMESPACE>
# Deve avere: eks.amazonaws.com/role-arn: arn:aws:iam::...

# Verificare che OIDC provider esista in IAM
aws iam list-open-id-connect-providers

# Verificare trust policy del role IAM
aws iam get-role --role-name <ROLE_NAME> \
    --query 'Role.AssumeRolePolicyDocument'

# Test manuale dal pod
kubectl exec -it <POD> -- aws sts get-caller-identity
```

**Upgrade fallisce o cluster bloccato**

```bash
# Verificare status update in corso
aws eks list-updates --name production
aws eks describe-update --name production --update-id <UPDATE_ID>

# Se bloccato per webhook admission, trovare i webhook che fanno timeout
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# Verificare che tutti i kube-system pods siano healthy
kubectl get pods -n kube-system
```

---

## Relazioni

??? info "VPC e Networking — Foundation per EKS"
    La rete EKS si basa sulla VPC: subnets (almeno 2 AZ), route tables, NAT Gateway per nodi privati.

    **Approfondimento →** [VPC Avanzato](../networking/vpc-avanzato.md)

??? info "IAM Policies Avanzate"
    IRSA e EKS Pod Identity si basano su OIDC federation e policy IAM. Per capire il modello di permission boundaries e policy avanzate.

    **Approfondimento →** [IAM Policies Avanzate](../iam/policies-avanzate.md)

??? info "Kubernetes Core — Prerequisiti"
    EKS è Kubernetes managed: architettura, workloads, networking K8s sono prerequisiti.

    **Approfondimento →** [Architettura Kubernetes](../../../containers/kubernetes/architettura.md)

---

## Riferimenti

- [EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/)
- [eksctl documentation](https://eksctl.io/)
- [Karpenter documentation](https://karpenter.sh/)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/)
- [IRSA Documentation](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [EKS Upgrade Guide](https://docs.aws.amazon.com/eks/latest/userguide/update-cluster.html)
