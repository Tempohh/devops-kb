---
title: "EC2 Auto Scaling & Load Balancing"
slug: ec2-autoscaling
category: cloud
tags: [aws, autoscaling, asg, alb, nlb, gwlb, load-balancer, target-group, health-check, scaling-policy, launch-template, target-tracking, step-scaling, scheduled-scaling]
search_keywords: [AWS Auto Scaling Group, ASG, Launch Template, Launch Configuration, ALB Application Load Balancer, NLB Network Load Balancer, GWLB Gateway Load Balancer, Target Group, sticky sessions, connection draining, deregistration delay, scaling policy, target tracking, step scaling, scheduled scaling, predictive scaling, warm pool, lifecycle hooks, Instance Refresh, capacity rebalancing]
parent: cloud/aws/compute/_index
related: [cloud/aws/compute/ec2, cloud/aws/networking/vpc, cloud/aws/networking/route53]
official_docs: https://docs.aws.amazon.com/autoscaling/ec2/userguide/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# EC2 Auto Scaling & Load Balancing

## Architettura Completa

```
Internet
   ↓
ALB (Application Load Balancer)
   ├── Target Group: web-servers (80/443)
   │   └── Auto Scaling Group
   │       ├── EC2 (AZ-A) ←── Launch Template
   │       ├── EC2 (AZ-B)
   │       └── EC2 (AZ-C)
   └── Target Group: api-servers (8080)
       └── Auto Scaling Group
           ├── EC2 (AZ-A)
           └── EC2 (AZ-B)
```

---

## Launch Templates

Il **Launch Template** è il template di configurazione per le istanze dell'ASG (Auto Scaling Group — gruppo di istanze EC2 che scala automaticamente; sostituisce Launch Configurations, deprecate).

```bash
# Creare Launch Template
aws ec2 create-launch-template \
    --launch-template-name my-app-lt \
    --version-description "v1 - initial" \
    --launch-template-data '{
        "ImageId": "ami-0a1b2c3d4e5f67890",
        "InstanceType": "t3.medium",
        "KeyName": "my-key",
        "SecurityGroupIds": ["sg-xxxx"],
        "IamInstanceProfile": {"Name": "MyEC2Profile"},
        "EbsOptimized": true,
        "MetadataOptions": {
            "HttpTokens": "required",
            "HttpPutResponseHopLimit": 1
        },
        "BlockDeviceMappings": [{
            "DeviceName": "/dev/xvda",
            "Ebs": {
                "VolumeType": "gp3",
                "VolumeSize": 30,
                "Encrypted": true,
                "DeleteOnTermination": true
            }
        }],
        "UserData": "'$(base64 -w0 userdata.sh)'",
        "TagSpecifications": [{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": "myapp"},
                {"Key": "Environment", "Value": "prod"}
            ]
        }]
    }'

# Creare nuova versione del template
aws ec2 create-launch-template-version \
    --launch-template-name my-app-lt \
    --source-version 1 \
    --version-description "v2 - update AMI" \
    --launch-template-data '{"ImageId": "ami-newami"}'

# Impostare versione default
aws ec2 modify-launch-template \
    --launch-template-name my-app-lt \
    --default-version 2
```

---

## Auto Scaling Group (ASG)

```bash
# Creare ASG
aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name myapp-asg \
    --launch-template LaunchTemplateName=my-app-lt,Version='$Latest' \
    --min-size 2 \
    --max-size 10 \
    --desired-capacity 3 \
    --vpc-zone-identifier "subnet-a,subnet-b,subnet-c" \   # subnet in 3 AZ
    --target-group-arns arn:aws:elasticloadbalancing:...:targetgroup/... \
    --health-check-type ELB \           # EC2 (default) o ELB (raccomandato)
    --health-check-grace-period 300 \   # secondi prima del primo health check
    --default-cooldown 300 \            # secondi tra scaling actions
    --tags 'Key=Name,Value=myapp,PropagateAtLaunch=true' \
          'Key=Environment,Value=prod,PropagateAtLaunch=true' \
    --termination-policies "OldestLaunchTemplate" "OldestInstance"

# Mix di instance types (On-Demand + Spot)
aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name myapp-mixed-asg \
    --mixed-instances-policy '{
        "LaunchTemplate": {
            "LaunchTemplateSpecification": {
                "LaunchTemplateName": "my-app-lt",
                "Version": "$Latest"
            },
            "Overrides": [
                {"InstanceType": "t3.medium"},
                {"InstanceType": "t3a.medium"},
                {"InstanceType": "t3.large"}
            ]
        },
        "InstancesDistribution": {
            "OnDemandBaseCapacity": 1,              # minimo 1 On-Demand
            "OnDemandPercentageAboveBaseCapacity": 25,  # 25% On-Demand, 75% Spot
            "SpotAllocationStrategy": "price-capacity-optimized"
        }
    }' \
    ...
```

---

## Scaling Policies

### Target Tracking (più semplice, raccomandato)

```bash
# Mantieni CPU al 60%
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name myapp-asg \
    --policy-name cpu-target-tracking \
    --policy-type TargetTrackingScaling \
    --target-tracking-configuration '{
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ASGAverageCPUUtilization"
        },
        "TargetValue": 60.0,
        "ScaleInCooldown": 300,
        "ScaleOutCooldown": 60,
        "DisableScaleIn": false
    }'

# Target tracking su Request Count per Target (per ALB)
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name myapp-asg \
    --policy-name alb-request-tracking \
    --policy-type TargetTrackingScaling \
    --target-tracking-configuration '{
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ALBRequestCountPerTarget",
            "ResourceLabel": "app/myalb/xxxx/targetgroup/myapp/xxxx"
        },
        "TargetValue": 1000.0
    }'
```

### Step Scaling

```bash
# Scale out aggressivo quando CPU molto alta
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name myapp-asg \
    --policy-name cpu-step-out \
    --policy-type StepScaling \
    --adjustment-type PercentChangeInCapacity \
    --step-adjustments '[
        {"MetricIntervalLowerBound": 0, "MetricIntervalUpperBound": 20, "ScalingAdjustment": 25},
        {"MetricIntervalLowerBound": 20, "ScalingAdjustment": 50}
    ]'
# Se allarme scatta a CPU >70%:
# CPU 70-90% → +25% istanze
# CPU >90%   → +50% istanze
```

### Scheduled Scaling

```bash
# Aumentare capacità di notte (batch) e ridurla di giorno
aws autoscaling put-scheduled-update-group-action \
    --auto-scaling-group-name myapp-asg \
    --scheduled-action-name scale-up-for-batch \
    --recurrence "0 22 * * MON-FRI" \    # ogni giorno lavorativo alle 22
    --min-size 5 \
    --desired-capacity 10

aws autoscaling put-scheduled-update-group-action \
    --auto-scaling-group-name myapp-asg \
    --scheduled-action-name scale-down-morning \
    --recurrence "0 7 * * MON-FRI" \     # ogni mattino alle 7
    --min-size 2 \
    --desired-capacity 3
```

### Predictive Scaling

```bash
# Predictive Scaling: usa ML per anticipare il carico
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name myapp-asg \
    --policy-name predictive-scaling \
    --policy-type PredictiveScaling \
    --predictive-scaling-configuration '{
        "MetricSpecifications": [{
            "TargetValue": 70,
            "PredefinedMetricPairSpecification": {
                "PredefinedMetricType": "ASGCPUUtilization"
            }
        }],
        "Mode": "ForecastAndScale",    # ForecastOnly per dry-run
        "SchedulingBufferTime": 300    # prepara 5 min prima
    }'
```

---

## Lifecycle Hooks

I **Lifecycle Hooks** permettono di eseguire azioni durante le transizioni di stato dell'istanza.

```bash
# Hook PRIMA che un'istanza venga aggiunta all'ASG
# (es. registrare in CMDB, installare agenti, warm up)
aws autoscaling put-lifecycle-hook \
    --auto-scaling-group-name myapp-asg \
    --lifecycle-hook-name before-launch \
    --lifecycle-transition autoscaling:EC2_INSTANCE_LAUNCHING \
    --heartbeat-timeout 300 \           # 5 minuti per completare
    --default-result CONTINUE \         # CONTINUE o ABANDON
    --notification-target-arn arn:aws:sns:...:lifecycle-notifications

# Hook PRIMA che un'istanza venga terminata
# (es. drenare connessioni, flush cache, backup)
aws autoscaling put-lifecycle-hook \
    --auto-scaling-group-name myapp-asg \
    --lifecycle-hook-name before-terminate \
    --lifecycle-transition autoscaling:EC2_INSTANCE_TERMINATING \
    --heartbeat-timeout 600 \           # 10 minuti per shutdown graceful
    --default-result CONTINUE

# L'istanza rimane in stato "Pending:Wait" o "Terminating:Wait"
# fino a che non viene segnalato il completamento:
aws autoscaling complete-lifecycle-action \
    --auto-scaling-group-name myapp-asg \
    --lifecycle-hook-name before-terminate \
    --instance-id i-xxxx \
    --lifecycle-action-result CONTINUE
```

---

## Instance Refresh — Zero-Downtime Deployment

```bash
# Aggiornare tutte le istanze con nuova Launch Template version
aws autoscaling start-instance-refresh \
    --auto-scaling-group-name myapp-asg \
    --strategy Rolling \
    --preferences '{
        "MinHealthyPercentage": 90,
        "InstanceWarmup": 300,
        "CheckpointPercentages": [20, 50],
        "CheckpointDelay": 3600,          # attende 1h tra checkpoint
        "SkipMatching": true,             # salta istanze già aggiornate
        "AutoRollback": true              # rollback automatico se health check fallisce
    }'

# Monitorare refresh
aws autoscaling describe-instance-refreshes \
    --auto-scaling-group-name myapp-asg \
    --query 'InstanceRefreshes[0].{Status:Status,Progress:PercentageComplete}'
```

---

## Application Load Balancer (ALB)

L'**ALB** opera al Layer 7 (HTTP/HTTPS/WebSocket) con routing avanzato.

```bash
# Creare ALB
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name myapp-alb \
    --subnets subnet-public-a subnet-public-b subnet-public-c \
    --security-groups sg-alb \
    --scheme internet-facing \
    --type application \
    --ip-address-type ipv4 \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text)

# Creare Target Group
TG_ARN=$(aws elbv2 create-target-group \
    --name myapp-tg \
    --protocol HTTP \
    --port 8080 \
    --vpc-id $VPC_ID \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --healthy-threshold-count 3 \
    --unhealthy-threshold-count 2 \
    --target-type instance \            # instance, ip, lambda
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)

# Creare Listener HTTPS
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTPS \
    --port 443 \
    --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \   # policy TLS moderna
    --certificates CertificateArn=arn:aws:acm:... \
    --default-actions '[{
        "Type": "forward",
        "TargetGroupArn": "'$TG_ARN'"
    }]'

# Redirect HTTP → HTTPS
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions '[{
        "Type": "redirect",
        "RedirectConfig": {
            "Protocol": "HTTPS",
            "Port": "443",
            "StatusCode": "HTTP_301"
        }
    }]'

# Routing rules avanzate (host-based + path-based)
aws elbv2 create-rule \
    --listener-arn $LISTENER_ARN \
    --priority 10 \
    --conditions '[
        {"Field": "host-header", "Values": ["api.company.com"]},
        {"Field": "path-pattern", "Values": ["/v2/*"]}
    ]' \
    --actions '[{"Type": "forward", "TargetGroupArn": "'$TG_API_V2'"}]'

# Sticky Sessions (affinità utente-istanza)
aws elbv2 modify-target-group-attributes \
    --target-group-arn $TG_ARN \
    --attributes '[
        {"Key": "stickiness.enabled", "Value": "true"},
        {"Key": "stickiness.type", "Value": "lb_cookie"},
        {"Key": "stickiness.lb_cookie.duration_seconds", "Value": "86400"}
    ]'
```

**Deregistration Delay (Connection Draining):**
```bash
# Quanti secondi attendere prima di rimuovere istanza da TG (completa richieste in corso)
aws elbv2 modify-target-group-attributes \
    --target-group-arn $TG_ARN \
    --attributes '[{"Key": "deregistration_delay.timeout_seconds", "Value": "30"}]'
```

---

## Network Load Balancer (NLB)

**NLB** opera al Layer 4 (TCP/UDP/TLS) — ultra-bassa latenza, IP statico.

```bash
aws elbv2 create-load-balancer \
    --name myapp-nlb \
    --subnets subnet-a subnet-b subnet-c \
    --scheme internet-facing \
    --type network \
    --ip-address-type ipv4

# NLB caratteristiche:
# - IP statico per AZ (o Elastic IP) → whitelist IP possibile
# - Milioni di richieste/secondo, sub-millisecondo latency
# - Preserva IP sorgente del client
# - Supporta TCP, UDP, TLS, TCP_UDP
# - TLS offloading a livello NLB
```

**ALB vs NLB:**

| Caratteristica | ALB | NLB |
|----------------|-----|-----|
| Layer | 7 (HTTP) | 4 (TCP/UDP) |
| Routing | Path/host/header/query | Solo port/protocol |
| IP statico | No (DNS hostname) | Sì (per AZ) |
| Latenza | ~1-5ms | <1ms |
| WebSocket | Sì | Sì |
| gRPC | Sì | Sì |
| Source IP preservation | X-Forwarded-For | Nativo |
| Costo | Più alto | Più basso |
| Use case | Web app, microservizi | Gaming, IoT, TCP puro |

---

## Gateway Load Balancer (GWLB)

**GWLB** è usato per instradare traffico attraverso appliance di sicurezza di terze parti (Palo Alto, Fortinet, Check Point).

```
Internet → IGW → GWLB → Firewall Appliance → GWLB → Target (EC2, ALB)
```

- Opera al Layer 3/4 con GENEVE encapsulation
- Bilancia il traffico verso fleet di appliance (FW — Firewall, IDS/IPS — Intrusion Detection/Prevention System, DLP — Data Loss Prevention)
- Trasparente all'applicazione

---

## Troubleshooting

### Scenario 1 — Le istanze vengono terminate subito dopo il lancio

**Sintomo:** Le istanze entrano in `InService` e poi vengono subito terminate dall'ASG.

**Causa:** L'health check ELB fallisce prima che l'applicazione sia pronta (grace period troppo basso o `/health` endpoint non disponibile).

**Soluzione:** Aumentare `health-check-grace-period` oppure correggere l'endpoint di health check.

```bash
# Verificare lo stato degli health check
aws elbv2 describe-target-health \
    --target-group-arn $TG_ARN \
    --query 'TargetHealthDescriptions[*].{Id:Target.Id,State:TargetHealth.State,Reason:TargetHealth.Reason}'

# Aumentare il grace period
aws autoscaling update-auto-scaling-group \
    --auto-scaling-group-name myapp-asg \
    --health-check-grace-period 600

# Verificare attività recenti dell'ASG (scaling events, terminate)
aws autoscaling describe-scaling-activities \
    --auto-scaling-group-name myapp-asg \
    --max-items 10
```

---

### Scenario 2 — L'ASG non scala nonostante il carico elevato

**Sintomo:** CPU al 90%+ ma il numero di istanze non aumenta. La scaling policy sembra inattiva.

**Causa:** Cooldown period attivo, allarme CloudWatch non in stato `ALARM`, o policy non collegata correttamente all'ASG.

**Soluzione:** Verificare lo stato degli allarmi CloudWatch e controllare il cooldown.

```bash
# Verificare stato allarmi CloudWatch legati all'ASG
aws cloudwatch describe-alarms \
    --alarm-name-prefix myapp-asg \
    --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue,Reason:StateReason}'

# Verificare le scaling policies configurate
aws autoscaling describe-policies \
    --auto-scaling-group-name myapp-asg

# Forzare uno scaling manuale per test
aws autoscaling set-desired-capacity \
    --auto-scaling-group-name myapp-asg \
    --desired-capacity 5 \
    --honor-cooldown false

# Verificare se c'è un cooldown attivo
aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names myapp-asg \
    --query 'AutoScalingGroups[0].{DefaultCooldown:DefaultCooldown,DesiredCapacity:DesiredCapacity}'
```

---

### Scenario 3 — Instance Refresh bloccato o in stato Failed

**Sintomo:** `start-instance-refresh` risulta in stato `Failed` o rimane a `InProgress` senza avanzare.

**Causa:** `MinHealthyPercentage` troppo alto, istanze che non superano gli health check dopo il refresh, o `AutoRollback` scattato.

**Soluzione:** Controllare il motivo del fallimento e le attività di rollback.

```bash
# Verificare stato del refresh e motivo del fallimento
aws autoscaling describe-instance-refreshes \
    --auto-scaling-group-name myapp-asg \
    --query 'InstanceRefreshes[0].{Status:Status,Reason:StatusReason,Progress:PercentageComplete}'

# Annullare un refresh in corso
aws autoscaling cancel-instance-refresh \
    --auto-scaling-group-name myapp-asg

# Riprovare con MinHealthyPercentage più basso
aws autoscaling start-instance-refresh \
    --auto-scaling-group-name myapp-asg \
    --strategy Rolling \
    --preferences '{
        "MinHealthyPercentage": 70,
        "InstanceWarmup": 300,
        "AutoRollback": false
    }'
```

---

### Scenario 4 — L'ALB restituisce 502/503 intermittenti sotto carico

**Sintomo:** Utenti ricevono errori HTTP 502 o 503, specialmente durante eventi di scaling o deploy.

**Causa:** Istanze rimosse dal Target Group prima del completamento delle richieste in corso (deregistration delay troppo basso) o nuove istanze aggiunte troppo presto (warmup insufficiente).

**Soluzione:** Aumentare il deregistration delay e verificare lo stato dei target.

```bash
# Verificare metriche di errore sull'ALB
aws cloudwatch get-metric-statistics \
    --namespace AWS/ApplicationELB \
    --metric-name HTTPCode_ELB_5XX_Count \
    --dimensions Name=LoadBalancer,Value=app/myapp-alb/xxxx \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 60 \
    --statistics Sum

# Aumentare il deregistration delay (default 300s, ridurlo può causare 502)
aws elbv2 modify-target-group-attributes \
    --target-group-arn $TG_ARN \
    --attributes '[{"Key": "deregistration_delay.timeout_seconds", "Value": "60"}]'

# Verificare target unhealthy nel TG
aws elbv2 describe-target-health \
    --target-group-arn $TG_ARN \
    --query 'TargetHealthDescriptions[?TargetHealth.State!=`healthy`]'
```

---

## Riferimenti

- [Auto Scaling User Guide](https://docs.aws.amazon.com/autoscaling/ec2/userguide/)
- [ALB User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)
- [NLB User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/)
- [Scaling Policies](https://docs.aws.amazon.com/autoscaling/ec2/userguide/scaling_plan.html)
