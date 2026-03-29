---
title: "AKS & Container Instances"
slug: aks-containers-azure
category: cloud
tags: [azure, aks, kubernetes, container-instances, acr, azure-container-registry, workload-identity]
search_keywords: [AKS Azure Kubernetes Service, Azure Container Registry ACR, Container Instances ACI, Azure Container Apps, Workload Identity Federation, node pool, cluster autoscaler, AGIC Application Gateway Ingress, CSI driver Key Vault, KEDA autoscaling]
parent: cloud/azure/compute/_index
related: [cloud/azure/networking/vnet, cloud/azure/security/key-vault, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/aks/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# AKS & Container Instances

## Panoramica

Azure offre diversi servizi per eseguire container, ognuno con livello di astrazione e complessità diversa:

| Servizio | Astrazione | Use Case | Scaling | Costo |
|---|---|---|---|---|
| **AKS** (Azure Kubernetes Service) | Orchestration platform | Microservizi complessi, stateful workload, team DevOps | Cluster autoscaler, HPA, KEDA | VM nodi + networking |
| **Azure Container Apps** | Serverless containers (KEDA+Dapr) | Microservizi event-driven, API, background jobs | KEDA autoscale 0→N | Consumption (vCPU+mem/sec) |
| **Container Instances (ACI)** | Container singoli | Task one-off, burst, sidecar pattern, CI jobs | No autoscale | Per-second (vCPU+mem) |
| **App Service (containers)** | PaaS web hosting | Web app containerizzate semplici | App Service autoscale | App Service Plan |

## Azure Container Registry (ACR)

ACR è il registry privato managed di Azure per immagini Docker/OCI e chart Helm.

### SKU ACR

| SKU | Storage | Throughput | Feature Extra | Use Case |
|---|---|---|---|---|
| **Basic** | 10 GB | Basso | – | Dev/test, CI |
| **Standard** | 100 GB | Medio | – | Produzione standard |
| **Premium** | 500 GB | Alto | Geo-replication, Private Link, Dedicated data endpoints, Token | Enterprise, compliance |

```bash
# Creare ACR
az acr create \
  --resource-group rg-platform-prod \
  --name myacrprod2026 \
  --sku Premium \
  --location westeurope \
  --admin-enabled false \
  --zone-redundancy Enabled

# Build immagine direttamente su ACR (senza Docker locale)
az acr build \
  --registry myacrprod2026 \
  --image myapp:$(git rev-parse --short HEAD) \
  --file Dockerfile \
  .

# ACR Task: build automatica su commit Git
az acr task create \
  --registry myacrprod2026 \
  --name build-myapp \
  --image myapp:{{.Run.ID}} \
  --context https://github.com/myorg/myapp.git \
  --file Dockerfile \
  --git-access-token $GITHUB_PAT

# Geo-replication (Premium): replica immagini in più regioni
az acr replication create \
  --registry myacrprod2026 \
  --location northeurope
```

### Private Endpoint per ACR

```bash
# Disabilitare accesso pubblico
az acr update \
  --name myacrprod2026 \
  --public-network-enabled false

# Creare Private Endpoint
az network private-endpoint create \
  --resource-group rg-platform-prod \
  --name pep-acr-prod \
  --vnet-name vnet-prod \
  --subnet snet-private-endpoints \
  --private-connection-resource-id $(az acr show --name myacrprod2026 --query id -o tsv) \
  --group-ids registry \
  --connection-name conn-acr

# DNS: zona privata per ACR
az network private-dns zone create \
  --resource-group rg-platform-prod \
  --name "privatelink.azurecr.io"
```

## AKS — Cluster Creation

### Creare Cluster AKS con Best Practices

```bash
RG="rg-aks-prod"
CLUSTER_NAME="aks-prod-westeurope"
LOCATION="westeurope"
ACR_NAME="myacrprod2026"
VNET_NAME="vnet-prod"
SUBNET_NODES="snet-aks-nodes"
SUBNET_SERVICES="snet-aks-services"

az aks create \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --location $LOCATION \
  --kubernetes-version 1.31.0 \
  --node-count 3 \
  --node-vm-size Standard_D4s_v5 \
  --nodepool-name systempool \
  --nodepool-labels role=system \
  --os-disk-size-gb 128 \
  --os-disk-type Ephemeral \
  --enable-managed-identity \
  --attach-acr $ACR_NAME \
  --network-plugin azure \
  --network-plugin-mode overlay \
  --network-policy azure \
  --vnet-subnet-id $(az network vnet subnet show --resource-group $RG --vnet-name $VNET_NAME --name $SUBNET_NODES --query id -o tsv) \
  --service-cidr 172.16.0.0/16 \
  --dns-service-ip 172.16.0.10 \
  --enable-cluster-autoscaler \
  --min-count 2 \
  --max-count 10 \
  --enable-oidc-issuer \
  --enable-workload-identity \
  --enable-azure-monitor-metrics \
  --enable-addons monitoring \
  --workspace-resource-id $(az monitor log-analytics workspace show --resource-group $RG --workspace-name law-prod --query id -o tsv) \
  --zones 1 2 3 \
  --tier Standard \
  --auto-upgrade-channel patch \
  --node-os-upgrade-channel NodeImage \
  --enable-defender \
  --generate-ssh-keys
```

!!! note "network-plugin-mode overlay"
    La modalità `overlay` del plugin Azure CNI usa sottoreti più efficienti per i pod (CIDR separato dai nodi), risolvendo il problema di esaurimento IP delle versioni precedenti. Raccomandato per nuovi cluster.

### Ottenere Credenziali kubectl

```bash
# Merge credentials nel kubeconfig locale
az aks get-credentials \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --overwrite-existing

# Verificare connessione
kubectl get nodes -o wide
kubectl get pods --all-namespaces
```

## Node Pools

AKS supporta più node pool, ognuno con dimensioni VM, OS e configurazione diverse.

### System Pool vs User Pool

```bash
# System pool: obbligatorio, ospita pod di sistema (coredns, kube-proxy, metrics-server)
# User pool: workload applicativi

# Aggiungere user node pool per workload applicativi
az aks nodepool add \
  --resource-group $RG \
  --cluster-name $CLUSTER_NAME \
  --name apppool \
  --node-count 3 \
  --node-vm-size Standard_D8s_v5 \
  --node-taints workload=app:NoSchedule \
  --node-labels role=app environment=prod \
  --zones 1 2 3 \
  --enable-cluster-autoscaler \
  --min-count 2 \
  --max-count 20 \
  --os-disk-type Ephemeral \
  --mode User

# Aggiungere GPU node pool per ML workload
az aks nodepool add \
  --resource-group $RG \
  --cluster-name $CLUSTER_NAME \
  --name gpupool \
  --node-count 0 \
  --node-vm-size Standard_NC6s_v3 \
  --node-taints sku=gpu:NoSchedule \
  --enable-cluster-autoscaler \
  --min-count 0 \
  --max-count 5 \
  --mode User

# Spot node pool (fino al 90% sconto, workload preemptible)
az aks nodepool add \
  --resource-group $RG \
  --cluster-name $CLUSTER_NAME \
  --name spotnodepool \
  --priority Spot \
  --eviction-policy Delete \
  --spot-max-price -1 \
  --node-count 0 \
  --enable-cluster-autoscaler \
  --min-count 0 \
  --max-count 50 \
  --node-taints kubernetes.azure.com/scalesetpriority=spot:NoSchedule \
  --mode User
```

### Windows Node Pool

```bash
az aks nodepool add \
  --resource-group $RG \
  --cluster-name $CLUSTER_NAME \
  --name winnodepool \
  --os-type Windows \
  --node-vm-size Standard_D4s_v5 \
  --node-count 2
```

## Upgrade AKS

```bash
# Verificare versioni disponibili per upgrade
az aks get-upgrades \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --output table

# Upgrade control plane e node pool (rolling upgrade)
az aks upgrade \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --kubernetes-version 1.31.2 \
  --yes

# Upgrade solo un node pool
az aks nodepool upgrade \
  --resource-group $RG \
  --cluster-name $CLUSTER_NAME \
  --name apppool \
  --kubernetes-version 1.31.2
```

## Workload Identity Federation

Workload Identity Federation (WIF) è il metodo raccomandato per permettere ai pod di accedere a risorse Azure (Key Vault, Storage, ecc.) senza credenziali. Sostituisce il deprecato Pod Identity.

```bash
# 1. Assicurarsi che il cluster abbia OIDC issuer e Workload Identity abilitati
OIDC_ISSUER=$(az aks show --resource-group $RG --name $CLUSTER_NAME --query "oidcIssuerProfile.issuerUrl" -o tsv)

# 2. Creare Managed Identity per il workload
az identity create \
  --resource-group $RG \
  --name mi-myapp-prod \
  --location $LOCATION

MANAGED_IDENTITY_CLIENT_ID=$(az identity show --resource-group $RG --name mi-myapp-prod --query clientId -o tsv)
MANAGED_IDENTITY_OBJECT_ID=$(az identity show --resource-group $RG --name mi-myapp-prod --query principalId -o tsv)

# 3. Assegnare permessi alla Managed Identity (es. Key Vault Secrets User)
az role assignment create \
  --assignee-object-id $MANAGED_IDENTITY_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name mykeyvault --query id -o tsv)

# 4. Creare Federated Credential: collega il ServiceAccount Kubernetes alla Managed Identity
az identity federated-credential create \
  --name fc-myapp-prod \
  --identity-name mi-myapp-prod \
  --resource-group $RG \
  --issuer $OIDC_ISSUER \
  --subject system:serviceaccount:default:myapp-serviceaccount \
  --audience api://AzureADTokenExchange
```

```yaml
# 5. Creare ServiceAccount Kubernetes con annotation
apiVersion: v1
kind: ServiceAccount
metadata:
  name: myapp-serviceaccount
  namespace: default
  annotations:
    azure.workload.identity/client-id: "MANAGED_IDENTITY_CLIENT_ID"
---
# 6. Pod che usa il ServiceAccount
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      labels:
        azure.workload.identity/use: "true"
    spec:
      serviceAccountName: myapp-serviceaccount
      containers:
      - name: myapp
        image: myacrprod2026.azurecr.io/myapp:latest
        env:
        - name: AZURE_CLIENT_ID
          value: "MANAGED_IDENTITY_CLIENT_ID"
```

```python
# 7. Nel codice applicativo: DefaultAzureCredential funziona automaticamente
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(
    vault_url="https://mykeyvault.vault.azure.net/",
    credential=credential
)
secret = client.get_secret("db-password")
```

## AKS Add-ons

```bash
# Azure Key Vault CSI Driver (montare segreti Key Vault come volume)
az aks addon enable \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --addon azure-keyvault-secrets-provider \
  --enable-secret-rotation

# Monitoring (Container Insights)
az aks addon enable \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --addon monitoring \
  --workspace-resource-id /subscriptions/.../workspaces/law-prod

# Application Gateway Ingress Controller (AGIC)
az aks addon enable \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --addon ingress-appgw \
  --appgw-name agw-aks-prod \
  --appgw-subnet-cidr 10.225.0.0/16
```

### Key Vault CSI Driver: Montare Segreti come Volume

```yaml
# SecretProviderClass: definisce quali segreti montare
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-keyvault-secrets
  namespace: default
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    clientID: "MANAGED_IDENTITY_CLIENT_ID"  # Workload Identity
    keyvaultName: mykeyvault
    tenantId: "YOUR_TENANT_ID"
    objects: |
      array:
        - |
          objectName: db-password
          objectType: secret
          objectVersion: ""
        - |
          objectName: api-key
          objectType: secret
  secretObjects:
  - secretName: app-secrets   # Crea anche un K8s Secret
    type: Opaque
    data:
    - objectName: db-password
      key: DB_PASSWORD
    - objectName: api-key
      key: API_KEY
---
# Pod che usa il CSI driver
apiVersion: v1
kind: Pod
spec:
  volumes:
  - name: secrets-store
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: azure-keyvault-secrets
  containers:
  - name: myapp
    volumeMounts:
    - name: secrets-store
      mountPath: "/mnt/secrets"
      readOnly: true
    envFrom:
    - secretRef:
        name: app-secrets
```

## Application Gateway Ingress Controller (AGIC)

AGIC usa Azure Application Gateway come Ingress controller per AKS, fornendo WAF, SSL termination e load balancing L7 managed.

```yaml
# Ingress con AGIC
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  annotations:
    kubernetes.io/ingress.class: azure/application-gateway
    appgw.ingress.kubernetes.io/ssl-redirect: "true"
    appgw.ingress.kubernetes.io/backend-protocol: "http"
    appgw.ingress.kubernetes.io/waf-policy-for-path: /subscriptions/.../webApplicationFirewallPolicies/waf-prod
spec:
  tls:
  - hosts:
    - myapp.example.com
    secretName: myapp-tls-secret
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

## Container Instances (ACI)

ACI è il modo più semplice per eseguire container su Azure senza gestire infrastruttura. Ideale per:
- Task one-off (elaborazione batch, migration jobs)
- Burst di capacità per AKS
- Applicazioni senza stato leggere
- CI/CD runner
- Sidecar pattern con container multipli

```bash
# Container singolo semplice
az container create \
  --resource-group $RG \
  --name aci-job-processor \
  --image myacrprod2026.azurecr.io/processor:latest \
  --cpu 2 \
  --memory 4 \
  --registry-login-server myacrprod2026.azurecr.io \
  --assign-identity \
  --environment-variables \
    INPUT_BLOB=input-data \
    OUTPUT_BLOB=output-data \
  --restart-policy Never \
  --location $LOCATION

# Container in VNet (accesso a risorse private)
az container create \
  --resource-group $RG \
  --name aci-internal-job \
  --image myacrprod2026.azurecr.io/processor:latest \
  --subnet $(az network vnet subnet show --resource-group $RG --vnet-name vnet-prod --name snet-aci --query id -o tsv) \
  --cpu 4 \
  --memory 8 \
  --restart-policy Never

# Deploy multi-container con YAML
az container create \
  --resource-group $RG \
  --name aci-multi \
  --file aci-multicontainer.yaml
```

```yaml
# aci-multicontainer.yaml — sidecar pattern
apiVersion: '2021-10-01'
location: westeurope
name: aci-multi-sidecar
properties:
  containers:
  - name: app
    properties:
      image: myacrprod2026.azurecr.io/myapp:latest
      resources:
        requests:
          cpu: 1.0
          memoryInGb: 1.5
      ports:
      - port: 8080
        protocol: TCP
      environmentVariables:
      - name: LOG_LEVEL
        value: INFO
  - name: log-collector
    properties:
      image: myacrprod2026.azurecr.io/log-collector:latest
      resources:
        requests:
          cpu: 0.5
          memoryInGb: 0.5
      volumeMounts:
      - name: logs
        mountPath: /var/log/app
  volumes:
  - name: logs
    emptyDir: {}
  osType: Linux
  restartPolicy: OnFailure
  ipAddress:
    type: Private
    ports:
    - protocol: TCP
      port: 8080
tags:
  environment: prod
type: Microsoft.ContainerInstance/containerGroups
```

```bash
# Monitorare stato container
az container show \
  --resource-group $RG \
  --name aci-job-processor \
  --query instanceView.state \
  --output tsv

# Log del container
az container logs \
  --resource-group $RG \
  --name aci-job-processor \
  --follow
```

## Azure Container Apps

Azure Container Apps (ACA) è il servizio più recente per container serverless, basato su Kubernetes (AKS managed da Microsoft) con Dapr e KEDA integrati.

```bash
# Creare environment Container Apps
az containerapp env create \
  --resource-group $RG \
  --name cae-prod \
  --location $LOCATION \
  --logs-workspace-id $(az monitor log-analytics workspace show --resource-group $RG --workspace-name law-prod --query customerId -o tsv) \
  --logs-workspace-key $(az monitor log-analytics workspace get-shared-keys --resource-group $RG --workspace-name law-prod --query primarySharedKey -o tsv)

# Creare Container App con scaling KEDA
az containerapp create \
  --resource-group $RG \
  --name mycontainerapp \
  --environment cae-prod \
  --image myacrprod2026.azurecr.io/myapp:latest \
  --registry-server myacrprod2026.azurecr.io \
  --min-replicas 0 \
  --max-replicas 50 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --target-port 8080 \
  --ingress external \
  --env-vars ENVIRONMENT=production
```

!!! tip "AKS vs Container Apps"
    Usa **Container Apps** quando hai microservizi event-driven semplici, vuoi KEDA autoscaling da zero, e non hai bisogno di customizzazione Kubernetes profonda. Usa **AKS** per workload complessi, stateful, con requisiti specifici di networking/storage, o quando il team ha già expertise Kubernetes.

## Best Practices

- Usa **Ephemeral OS disks** per i nodi AKS (performance migliore e riduzione costi storage)
- Separa sempre **system pool** e **user pool**: non eseguire workload applicativi nel system pool
- Abilita **cluster autoscaler** con min-count > 0 per garantire disponibilità baseline
- Usa **Workload Identity** invece di Service Principal con credenziali statiche
- Configura **PodDisruptionBudget** per garantire disponibilità durante upgrade nodi
- Abilita **Private Cluster** per ambienti altamente sicuri (API server non esposto a Internet)

```bash
# AKS Private Cluster
az aks create \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --enable-private-cluster \
  --private-dns-zone system \
  ...
```

## Troubleshooting

### Scenario 1 — Nodi in stato NotReady dopo upgrade

**Sintomo:** Dopo `az aks upgrade`, uno o più nodi rimangono in stato `NotReady` e i pod non vengono schedulati.

**Causa:** Il node image potrebbe non essere aggiornato correttamente, oppure il kubelet non è riuscito a riavviarsi a causa di conflitti con le extension o i CSI driver.

**Soluzione:** Verificare lo stato dei nodi e forzare il drain/reimaging del nodo problematico.

```bash
# Verificare stato nodi
kubectl get nodes -o wide
kubectl describe node <nome-nodo>

# Controllare eventi recenti sul nodo
kubectl get events --field-selector involvedObject.name=<nome-nodo>

# Upgrade forzato del node image per il pool problematico
az aks nodepool upgrade \
  --resource-group $RG \
  --cluster-name $CLUSTER_NAME \
  --name apppool \
  --node-image-only

# Se il nodo è irrecuperabile: drain e delete (autoscaler ne crea uno nuovo)
kubectl drain <nome-nodo> --ignore-daemonsets --delete-emptydir-data
kubectl delete node <nome-nodo>
```

---

### Scenario 2 — ImagePullBackOff da ACR privato

**Sintomo:** I pod rimangono in `ImagePullBackOff` o `ErrImagePull` con errore `unauthorized: authentication required` quando cercano di pullare immagini da ACR.

**Causa:** L'AKS Managed Identity non ha il ruolo `AcrPull` sull'ACR, oppure il cluster non è stato creato con `--attach-acr`.

**Soluzione:** Assegnare il ruolo `AcrPull` alla kubelet identity del cluster.

```bash
# Ottenere l'Object ID della kubelet identity
KUBELET_IDENTITY=$(az aks show \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --query "identityProfile.kubeletidentity.objectId" -o tsv)

ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)

# Assegnare ruolo AcrPull
az role assignment create \
  --assignee-object-id $KUBELET_IDENTITY \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull \
  --scope $ACR_ID

# Verificare role assignment
az role assignment list --scope $ACR_ID --output table

# In alternativa: attach ACR al cluster esistente
az aks update \
  --resource-group $RG \
  --name $CLUSTER_NAME \
  --attach-acr $ACR_NAME
```

---

### Scenario 3 — Pod OOMKilled o evicted per memory pressure

**Sintomo:** Pod terminati con status `OOMKilled` (exit code 137) o evicted con messaggio `The node was low on resource: memory`.

**Causa:** I container non hanno `resources.limits` definiti, oppure il workload consuma più memoria del previsto. In caso di eviction, il nodo è sotto pressione di memoria per troppi pod senza limiti.

**Soluzione:** Impostare resource requests e limits, e configurare VPA o KEDA se il consumo è variabile.

```bash
# Verificare consumo risorse dei pod
kubectl top pods --all-namespaces --sort-by=memory
kubectl top nodes

# Descrivere il pod per vedere OOMKilled
kubectl describe pod <nome-pod> -n <namespace>

# Verificare eventi di eviction sul nodo
kubectl get events --all-namespaces --field-selector reason=Evicted
```

```yaml
# Aggiungere resource requests e limits al deployment
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

---

### Scenario 4 — Workload Identity: token non acquisito (pod accede a Key Vault con 403)

**Sintomo:** Il pod ottiene errore `403 Forbidden` o `DefaultAzureCredential authentication failed` quando accede a Key Vault o altri servizi Azure. Il log mostra `EnvironmentCredential`, `ManagedIdentityCredential` falliti.

**Causa:** Il Federated Credential non è configurato correttamente (subject sbagliato), la label `azure.workload.identity/use: "true"` manca dal pod, oppure il ruolo non è stato assegnato alla Managed Identity.

**Soluzione:** Verificare ogni step della catena WIF.

```bash
# 1. Verificare che il cluster abbia OIDC e WI abilitati
az aks show --resource-group $RG --name $CLUSTER_NAME \
  --query "{oidc: oidcIssuerProfile.enabled, wi: securityProfile.workloadIdentity.enabled}"

# 2. Verificare il ServiceAccount ha l'annotation corretta
kubectl get serviceaccount <sa-name> -n <namespace> -o yaml

# 3. Verificare che il pod abbia la label azure.workload.identity/use: "true"
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.metadata.labels}'

# 4. Verificare il Federated Credential (subject deve corrispondere namespace:sa-name)
az identity federated-credential list \
  --identity-name mi-myapp-prod \
  --resource-group $RG \
  --output table

# 5. Verificare role assignment della Managed Identity
MANAGED_IDENTITY_ID=$(az identity show --resource-group $RG --name mi-myapp-prod --query principalId -o tsv)
az role assignment list --assignee $MANAGED_IDENTITY_ID --output table
```

## Riferimenti

- [Documentazione AKS](https://learn.microsoft.com/azure/aks/)
- [Azure Container Registry](https://learn.microsoft.com/azure/container-registry/)
- [Workload Identity AKS](https://learn.microsoft.com/azure/aks/workload-identity-overview)
- [Key Vault CSI Driver](https://learn.microsoft.com/azure/aks/csi-secrets-store-driver)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [AKS Best Practices](https://learn.microsoft.com/azure/aks/best-practices)
