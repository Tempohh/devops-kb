---
title: "ECS, EKS & Containers AWS"
slug: containers-ecs-eks
category: cloud
tags: [aws, ecs, eks, ecr, fargate, containers, kubernetes, app-runner, ecs-anywhere, copilot]
search_keywords: [AWS ECS, Elastic Container Service, EKS, Elastic Kubernetes Service, Fargate, ECR, Elastic Container Registry, App Runner, ECS task definition, ECS service, ECS cluster, Fargate vs EC2, EKS managed node group, EKS Fargate profile, EKS add-ons, EKS Blueprint, IRSA, pod identity, ECS Anywhere, AWS Copilot, container orchestration, service mesh, App Mesh]
parent: cloud/aws/compute/_index
related: [cloud/aws/iam/policies-avanzate, cloud/aws/networking/vpc, cloud/aws/security/kms-secrets, cloud/aws/monitoring/cloudwatch, containers/kubernetes/_index]
official_docs: https://docs.aws.amazon.com/ecs/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# ECS, EKS & Containers AWS

## ECS vs EKS — Quando Usare Cosa

| Aspetto | ECS | EKS |
|---------|-----|-----|
| Curva apprendimento | Bassa (API AWS native) | Alta (Kubernetes) |
| Portabilità | AWS-only | Kubernetes (multi-cloud) |
| Pricing control plane | Gratuito | $0.10/hr per cluster |
| Fargate support | Sì (nativo) | Sì (Fargate profiles) |
| Service mesh | App Mesh / ECS native | Istio, AWS App Mesh, Linkerd |
| Advanced scheduling | Limitato | Completo (K8s scheduler) |
| CRD (Custom Resource Definition) / Operators | No | Sì |
| Integrazione AWS | Nativa profonda | Buona (via add-ons) |
| Use case | Nuovo su AWS, workloads semplici | Team K8s già formato, portabilità |

---

## Amazon ECS

### Componenti ECS

```
ECS Architecture

  ECS Cluster
  ├── Capacity Providers
  │   ├── FARGATE (serverless)
  │   └── FARGATE_SPOT (spot serverless)
  │   └── EC2 ASG (EC2 launch type)
  │
  ├── Task Definition (blueprint del container)
  │   ├── Container definitions
  │   ├── CPU / Memory
  │   ├── Network mode
  │   └── IAM Roles (execution + task)
  │
  └── Services (long-running) | Tasks (one-off)
      ├── Desired Count
      ├── Load Balancer integration
      ├── Service Discovery (Cloud Map)
      └── Auto Scaling
```

### Task Definition

```json
{
  "family": "myapp",
  "networkMode": "awsvpc",               // richiesto per Fargate
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",                          // 0.5 vCPU
  "memory": "1024",                      // 1 GB
  "executionRoleArn": "arn:aws:iam::...:role/ECSTaskExecutionRole",   // pull image, logs
  "taskRoleArn": "arn:aws:iam::...:role/ECSTaskRole",                // permessi app
  "containerDefinitions": [
    {
      "name": "myapp",
      "image": "123456789012.dkr.ecr.eu-central-1.amazonaws.com/myapp:1.0.0",
      "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
      "environment": [
        {"name": "ENV", "value": "production"},
        {"name": "LOG_LEVEL", "value": "info"}
      ],
      "secrets": [
        {
          "name": "DB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:...:secret:myapp/db-password"
        },
        {
          "name": "API_KEY",
          "valueFrom": "arn:aws:ssm:...:parameter/myapp/api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/myapp",
          "awslogs-region": "eu-central-1",
          "awslogs-stream-prefix": "myapp"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "readonlyRootFilesystem": true,
      "user": "1000"
    }
  ]
}
```

```bash
# Registrare Task Definition
aws ecs register-task-definition \
    --cli-input-json file://task-definition.json

# Creare cluster
aws ecs create-cluster \
    --cluster-name production \
    --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy \
        capacityProvider=FARGATE,weight=1,base=1 \
        capacityProvider=FARGATE_SPOT,weight=3
    # 75% Spot, 25% On-Demand (con almeno 1 On-Demand)
```

### ECS Service

```bash
# Creare service con ALB integration
aws ecs create-service \
    --cluster production \
    --service-name myapp \
    --task-definition myapp:5 \
    --desired-count 3 \
    --launch-type FARGATE \
    --platform-version LATEST \
    --network-configuration '{
        "awsvpcConfiguration": {
            "subnets": ["subnet-private-a", "subnet-private-b"],
            "securityGroups": ["sg-myapp"],
            "assignPublicIp": "DISABLED"
        }
    }' \
    --load-balancers '[{
        "targetGroupArn": "arn:aws:elasticloadbalancing:...:targetgroup/myapp/xxx",
        "containerName": "myapp",
        "containerPort": 8080
    }]' \
    --service-registries '[{
        "registryArn": "arn:aws:servicediscovery:...:service/xxx"
    }]' \
    --deployment-configuration '{
        "deploymentCircuitBreaker": {"enable": true, "rollback": true},
        "maximumPercent": 200,
        "minimumHealthyPercent": 100
    }' \
    --health-check-grace-period-seconds 60

# Deploy nuova versione (aggiornare task definition version)
aws ecs update-service \
    --cluster production \
    --service myapp \
    --task-definition myapp:6 \
    --force-new-deployment

# Auto Scaling sul service
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --resource-id service/production/myapp \
    --scalable-dimension ecs:service:DesiredCount \
    --min-capacity 2 \
    --max-capacity 20

aws application-autoscaling put-scaling-policy \
    --service-namespace ecs \
    --resource-id service/production/myapp \
    --scalable-dimension ecs:service:DesiredCount \
    --policy-name cpu-target \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
        "PredefinedMetricSpecification": {"PredefinedMetricType": "ECSServiceAverageCPUUtilization"},
        "TargetValue": 70
    }'
```

---

## ECR — Elastic Container Registry

```bash
# Login ECR
aws ecr get-login-password --region eu-central-1 | \
    docker login \
        --username AWS \
        --password-stdin \
        123456789012.dkr.ecr.eu-central-1.amazonaws.com

# Creare repository
aws ecr create-repository \
    --repository-name myapp \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability IMMUTABLE \    # tag immutabili — best practice
    --encryption-configuration encryptionType=KMS

# Lifecycle Policy: mantieni solo 10 immagini tagged + elimina untagged dopo 1 giorno
aws ecr put-lifecycle-policy \
    --repository-name myapp \
    --lifecycle-policy-text '{
        "rules": [
            {
                "rulePriority": 1,
                "description": "Keep last 10 tagged images",
                "selection": {
                    "tagStatus": "tagged",
                    "tagPrefixList": ["v"],
                    "countType": "imageCountMoreThan",
                    "countNumber": 10
                },
                "action": {"type": "expire"}
            },
            {
                "rulePriority": 2,
                "description": "Expire untagged after 1 day",
                "selection": {
                    "tagStatus": "untagged",
                    "countType": "sinceImagePushed",
                    "countUnit": "days",
                    "countNumber": 1
                },
                "action": {"type": "expire"}
            }
        ]
    }'

# Push immagine
docker build -t myapp:v1.0.0 .
docker tag myapp:v1.0.0 123456789012.dkr.ecr.eu-central-1.amazonaws.com/myapp:v1.0.0
docker push 123456789012.dkr.ecr.eu-central-1.amazonaws.com/myapp:v1.0.0

# Pull-through cache (ECR come proxy per Docker Hub / ECR Public)
aws ecr create-pull-through-cache-rule \
    --ecr-repository-prefix docker-hub \
    --upstream-registry-url registry-1.docker.io

# Usare immagini Docker Hub tramite ECR (caching automatico):
# 123456789012.dkr.ecr.eu-central-1.amazonaws.com/docker-hub/nginx:latest
```

---

## Amazon EKS

### Creare un Cluster EKS

```bash
# eksctl (raccomandato per gestione cluster)
cat > cluster.yaml <<'EOF'
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: production
  region: eu-central-1
  version: "1.31"

iam:
  withOIDC: true                    # IRSA support

managedNodeGroups:
  - name: workers
    instanceType: m6g.xlarge        # Graviton
    amiFamily: AmazonLinux2023
    minSize: 3
    maxSize: 20
    desiredCapacity: 5
    volumeSize: 50
    volumeType: gp3
    privateNetworking: true         # nodi in subnet private
    tags:
      Environment: production
    iam:
      attachPolicyARNs:
        - arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
        - arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
        - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy

  - name: spot-workers
    instanceTypes: ["m6g.large", "m6g.xlarge", "m6a.xlarge"]
    spot: true
    minSize: 0
    maxSize: 30
    desiredCapacity: 0
    taints:
      - key: spot
        value: "true"
        effect: NoSchedule

fargateProfiles:
  - name: serverless
    selectors:
      - namespace: serverless

addons:
  - name: vpc-cni
    version: latest
  - name: coredns
    version: latest
  - name: kube-proxy
    version: latest
  - name: aws-ebs-csi-driver
    version: latest
    serviceAccountRoleARN: arn:aws:iam::123456789012:role/EBSCSIRole
  - name: aws-efs-csi-driver
    version: latest
EOF

eksctl create cluster -f cluster.yaml
```

```bash
# Accesso al cluster
aws eks update-kubeconfig \
    --region eu-central-1 \
    --name production

kubectl get nodes
kubectl get pods -A
```

### EKS — IRSA (IAM Roles for Service Accounts)

```bash
# Creare IAM Role per ServiceAccount con IRSA
eksctl create iamserviceaccount \
    --cluster production \
    --namespace myapp \
    --name myapp-sa \
    --attach-policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
    --approve

# Verificare annotazione
kubectl describe sa myapp-sa -n myapp
# Annotations: eks.amazonaws.com/role-arn: arn:aws:iam::...:role/eksctl-...
```

```yaml
# Pod che usa IRSA — nessuna access key necessaria
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: myapp
spec:
  template:
    spec:
      serviceAccountName: myapp-sa    # usa il SA con IRSA
      containers:
        - name: myapp
          image: 123456789012.dkr.ecr.eu-central-1.amazonaws.com/myapp:v1.0.0
          # AWS SDK legge automaticamente le credenziali dal IRSA token
```

### EKS Add-ons Essenziali

```bash
# Cluster Autoscaler
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm install cluster-autoscaler autoscaler/cluster-autoscaler \
    --set autoDiscovery.clusterName=production \
    --set awsRegion=eu-central-1 \
    --namespace kube-system

# AWS Load Balancer Controller (sostituisce ELB in-tree)
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
    --set clusterName=production \
    --set serviceAccount.create=false \
    --set serviceAccount.name=aws-load-balancer-controller \
    --namespace kube-system

# Karpenter (scheduler di nuova generazione — sostituisce Cluster Autoscaler)
helm upgrade --install karpenter oci://public.ecr.aws/karpenter/karpenter \
    --version "1.0.0" \
    --namespace kube-system \
    --set settings.clusterName=production \
    --set controller.resources.requests.cpu=1 \
    --set controller.resources.requests.memory=1Gi
```

```yaml
# Karpenter NodePool — definisce quali nodi creare
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["arm64"]              # Graviton preferito
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]  # spot prima
        - key: karpenter.k8s.aws/instance-family
          operator: In
          values: ["m6g", "m7g", "c6g"]
  limits:
    cpu: "1000"
    memory: 4000Gi
  disruption:
    consolidationPolicy: WhenUnderutilized
    consolidateAfter: 30s
```

---

## AWS App Runner

**App Runner** è il servizio PaaS per container — deploy con zero configurazione infrastruttura.

```bash
# Creare App Runner service da ECR
aws apprunner create-service \
    --service-name myapp \
    --source-configuration '{
        "ImageRepository": {
            "ImageIdentifier": "123456789012.dkr.ecr.eu-central-1.amazonaws.com/myapp:latest",
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
                "Port": "8080",
                "RuntimeEnvironmentVariables": {
                    "ENV": "production"
                }
            }
        },
        "AutoDeploymentsEnabled": true      # deploy automatico su nuovo push ECR
    }' \
    --instance-configuration '{
        "Cpu": "1 vCPU",
        "Memory": "2 GB",
        "InstanceRoleArn": "arn:aws:iam::...:role/AppRunnerRole"
    }' \
    --auto-scaling-configuration-arn arn:aws:apprunner:...:autoscalingconfiguration/...
```

**App Runner vs ECS Fargate:**

| | App Runner | ECS Fargate |
|---|-----------|-------------|
| Networking | Solo pubblico (con VPC egress) | Completo (VPC, private) |
| Configurazione | Minimale | Completa |
| Autoscaling | Automatico (basato su req/s) | Configurabile |
| Cold start | A 0 richieste scala a 0 | Minimo configurabile |
| Costo idle | ~$0 (scale-to-zero) | Minimo configurabile |
| Use case | MVP, microservizi semplici | Produzione enterprise |

---

## Troubleshooting

### Scenario 1 — ECS Task si ferma immediatamente (Essential container exited)

**Sintomo:** Il task ECS passa da `PROVISIONING` a `STOPPED` con exit code non-zero; il service non raggiunge il desired count.

**Causa:** Il container principale termina subito per errore applicativo, OOM kill, o mancanza di permessi IAM per leggere secrets/SSM.

**Soluzione:** Controllare i log CloudWatch del container e verificare i permessi della execution role.

```bash
# Vedere gli ultimi stop reason del service
aws ecs describe-tasks \
    --cluster production \
    --tasks $(aws ecs list-tasks --cluster production --service-name myapp --desired-status STOPPED --query 'taskArns[0]' --output text) \
    --query 'tasks[0].{stopCode:stopCode,stoppedReason:stoppedReason,containers:containers[*].{name:name,exitCode:exitCode,reason:reason}}'

# Log del container (awslogs driver)
aws logs get-log-events \
    --log-group-name /ecs/myapp \
    --log-stream-name myapp/myapp/<task-id> \
    --limit 50

# Verificare che la execution role abbia accesso a Secrets Manager
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:role/ECSTaskExecutionRole \
    --action-names secretsmanager:GetSecretValue \
    --resource-arns arn:aws:secretsmanager:eu-central-1:123456789012:secret:myapp/db-password
```

---

### Scenario 2 — EKS Pod in CrashLoopBackOff o ImagePullBackOff

**Sintomo:** Pod rimane in `CrashLoopBackOff` o `ImagePullBackOff` dopo il deploy; `kubectl get pods` mostra restart count crescente.

**Causa:** Per `ImagePullBackOff`: credenziali ECR scadute, IRSA non configurato per il kubelet, o immagine inesistente. Per `CrashLoopBackOff`: errore applicativo o liveness probe troppo aggressiva.

**Soluzione:** Verificare i permessi del node group su ECR e i log del pod.

```bash
# Stato dettagliato del pod
kubectl describe pod <pod-name> -n myapp

# Log del container (inclusi i restart precedenti)
kubectl logs <pod-name> -n myapp --previous

# Verificare che il node group IAM role abbia AmazonEC2ContainerRegistryReadOnly
aws iam list-attached-role-policies \
    --role-name eksctl-production-nodegroup-NodeInstanceRole-XXXX | \
    grep -i ecr

# Per ImagePullBackOff da ECR: controllare che il token sia valido
aws ecr get-authorization-token --region eu-central-1 \
    --query 'authorizationData[0].expiresAt'

# Forzare ricreazione dei pod
kubectl rollout restart deployment/myapp -n myapp
kubectl rollout status deployment/myapp -n myapp
```

---

### Scenario 3 — ECS Service non si stabilizza (deployment bloccato)

**Sintomo:** `aws ecs describe-services` mostra `deployments` con due entry attive (NEW e ACTIVE); il deployment non converge mai e scatta il circuit breaker.

**Causa:** Le nuove task falliscono l'health check del load balancer (grace period troppo corto, porta sbagliata, o app troppo lenta al boot).

**Soluzione:** Aumentare `healthCheckGracePeriodSeconds` e verificare la target group health check configuration.

```bash
# Vedere lo stato del deployment
aws ecs describe-services \
    --cluster production \
    --services myapp \
    --query 'services[0].{status:status,deployments:deployments[*].{status:status,runningCount:runningCount,failedTasks:failedTasks,rolloutState:rolloutState}}'

# Aumentare il grace period per app lente al boot
aws ecs update-service \
    --cluster production \
    --service myapp \
    --health-check-grace-period-seconds 120

# Verificare health checks sulla target group
aws elbv2 describe-target-health \
    --target-group-arn arn:aws:elasticloadbalancing:...:targetgroup/myapp/xxx

# Forzare rollback manuale se circuit breaker non è abilitato
aws ecs update-service \
    --cluster production \
    --service myapp \
    --task-definition myapp:5 \   # versione precedente funzionante
    --force-new-deployment
```

---

### Scenario 4 — EKS Nodi non si aggiungono con Karpenter / Cluster Autoscaler

**Sintomo:** Pod in stato `Pending` con evento `0/3 nodes are available: 3 Insufficient cpu`; nessun nodo viene aggiunto automaticamente.

**Causa:** Karpenter non ha i permessi IAM corretti, il NodePool ha raggiunto i limits, oppure i pod hanno taints/affinity incompatibili con i node requirements definiti.

**Soluzione:** Verificare i log di Karpenter e i limiti del NodePool.

```bash
# Log di Karpenter
kubectl logs -n kube-system -l app.kubernetes.io/name=karpenter --tail=50

# Stato dei NodePool e utilizzo corrente dei limiti
kubectl get nodepools
kubectl describe nodepool default

# Vedere perché il pod è pending (scheduling events)
kubectl describe pod <pending-pod> -n myapp | grep -A 20 Events

# Verificare che IRSA di Karpenter sia corretto
kubectl describe sa karpenter -n kube-system

# Vedere nodi gestiti da Karpenter
kubectl get nodeclaims
kubectl get nodes -l karpenter.sh/nodepool=default

# Se si usa Cluster Autoscaler: vedere i log
kubectl logs -n kube-system -l app.kubernetes.io/name=cluster-autoscaler --tail=50
```

---

## Riferimenti

- [ECS User Guide](https://docs.aws.amazon.com/ecs/latest/developerguide/)
- [EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/)
- [ECR User Guide](https://docs.aws.amazon.com/ecr/latest/userguide/)
- [App Runner](https://docs.aws.amazon.com/apprunner/)
- [eksctl](https://eksctl.io/)
- [Karpenter](https://karpenter.sh/)
- [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
