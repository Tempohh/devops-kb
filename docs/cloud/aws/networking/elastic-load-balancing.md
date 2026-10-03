---
title: "Elastic Load Balancing (ALB, NLB, GWLB)"
slug: elastic-load-balancing
category: cloud
tags: [aws, elb, alb, nlb, gwlb, load-balancing, target-groups, tls, privatelink, eks]
search_keywords: [ELB, Elastic Load Balancing, ALB, Application Load Balancer, NLB, Network Load Balancer, GWLB, Gateway Load Balancer, CLB, Classic Load Balancer, target group, listener rule, health check, deregistration delay, cross-zone load balancing, proxy protocol v2, client IP preservation, Elastic IP, PrivateLink, endpoint service, GENEVE, ACM, SNI, ELBSecurityPolicy-TLS13, access logs, AWS Load Balancer Controller, target-type ip, weighted forward, canary, sticky sessions, idle timeout, 502, 503, 504, bilanciatore di carico]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/vpc, cloud/aws/networking/route53, cloud/aws/networking/cloudfront, cloud/aws/compute/ec2-autoscaling, cloud/aws/containers/eks, networking/load-balancing/layer4-vs-layer7]
official_docs: https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/
status: reviewed
difficulty: intermediate
last_updated: 2026-09-26
last_verified: 2026-10-03
---

# Elastic Load Balancing (ALB, NLB, GWLB)

## Panoramica

**Elastic Load Balancing (ELB)** è la famiglia di load balancer managed di AWS: distribuisce il traffico in ingresso su target (istanze EC2, IP, container, Lambda) in più Availability Zone, esegue health check e scala automaticamente con il carico. Non si gestiscono istanze né patching: AWS fornisce nodi del load balancer in ogni AZ abilitata, raggiungibili tramite un record DNS che risolve verso più IP.

Esistono tre tipi "correnti": **Application Load Balancer (ALB)** al Layer 7 (HTTP/HTTPS/gRPC/WebSocket), **Network Load Balancer (NLB)** al Layer 4 (TCP/UDP/TLS, ultra-bassa latenza, IP statici) e **Gateway Load Balancer (GWLB)** al Layer 3 (inserimento trasparente di appliance di sicurezza). Il **Classic Load Balancer (CLB)** è legacy: non usarlo per nuovi workload.

Si usa ELB ogni volta che un servizio ha più repliche o deve sopravvivere alla perdita di una AZ. Non serve per un singolo target senza requisiti di HA, o quando basta un record DNS (Route 53) o una CDN (CloudFront) davanti a uno storage statico.

---

## Concetti Chiave

!!! note "Componenti"
    - **Load balancer**: entry point con DNS name `xxx.region.elb.amazonaws.com`, un nodo per AZ abilitata.
    - **Listener**: processo che ascolta su protocollo+porta e applica regole.
    - **Rule** (solo ALB): condizioni (path, host, header, query, IP sorgente) → azione (forward, redirect, fixed-response, authenticate).
    - **Target group**: insieme di target con protocollo, porta e health check propri.
    - **Target**: destinatario finale (instance, ip, lambda, alb).

### ALB vs NLB vs GWLB

| Criterio | ALB | NLB | GWLB |
|---|---|---|---|
| Layer OSI | 7 | 4 | 3 (+ GENEVE) |
| Protocolli | HTTP, HTTPS, gRPC, WebSocket | TCP, UDP, TLS, TCP_UDP, QUIC passthrough | IP (tutti i protocolli) |
| Latenza | ms (parsing HTTP) | ~100 µs, milioni di req/s | Bassa, trasparente |
| IP statici / Elastic IP | No (DNS only; usare Global Accelerator) | Sì, 1 EIP per AZ | No |
| Security group | Sì | Sì (dal 2023, opzionale alla creazione) | No |
| Routing | Path, host, header, query, method | Porta/protocollo | Flow hash 5-tuple |
| Client IP | `X-Forwarded-For` | Preservato (target instance) | Preservato |
| TLS termination | Sì | Sì (listener TLS) | No |
| Target type | instance, ip, lambda | instance, ip, alb | instance, ip |
| Use case tipico | Web app, microservizi, API | Gaming, IoT, DB, PrivateLink, IP fissi | Firewall/IDS/IPS di terze parti |

!!! tip "Regola pratica"
    HTTP(S) → **ALB**. Serve un IP fisso, UDP, protocolli non HTTP o throughput estremo → **NLB**. Serve ispezione centralizzata del traffico → **GWLB**. Serve IP fisso *e* routing L7 → NLB davanti ad ALB (target type `alb`) oppure Global Accelerator davanti ad ALB.

### Target group

| Target type | Registra | Note |
|---|---|---|
| `instance` | ID istanza EC2 | Traffico verso la porta dell'istanza; ideale con Auto Scaling Group |
| `ip` | IP privati (anche on-prem via Direct Connect/VPN, peering) | Obbligatorio per Fargate e per EKS con VPC CNI in modalità pod IP |
| `lambda` | Una funzione Lambda | Solo ALB; payload JSON, limite 1 MB |
| `alb` | Un ALB | Solo NLB; combina IP statici e routing L7 |

### Health check e deregistration delay

- Il load balancer invia periodicamente una richiesta di health check; un target diventa `unhealthy` dopo `UnhealthyThresholdCount` fallimenti consecutivi e torna `healthy` dopo `HealthyThresholdCount` successi.
- Se **tutti** i target di un TG sono unhealthy, ELB fa **fail-open**: instrada comunque a tutti (meglio che scartare tutto il traffico).
- **Deregistration delay** (default 300 s): quando un target viene rimosso, resta in stato `draining` e completa le richieste in corso prima di essere scollegato. Per API brevi 30 s bastano e velocizzano i deploy.
- **Slow start**: aumenta gradualmente il traffico verso target appena registrati (ALB, 30–900 s).

---

## Architettura / Come Funziona

Ogni load balancer crea un **nodo per ogni subnet/AZ** abilitata. Il DNS restituisce gli IP dei nodi; il client sceglie uno di essi e il nodo inoltra verso i target.

```text
Client ──► DNS (myalb-123.eu-west-1.elb.amazonaws.com)
              │
      ┌───────┴────────┐
      ▼                ▼
 Nodo ELB AZ-a    Nodo ELB AZ-b     (uno per subnet abilitata)
      │                │
 [cross-zone ON: ogni nodo distribuisce su TUTTI i target]
      ▼                ▼
  Target AZ-a      Target AZ-b
```

### Cross-zone load balancing

| Tipo | Default | Costo data transfer inter-AZ |
|---|---|---|
| ALB | **Attivo** (non disattivabile a livello LB, sì a livello TG) | Gratuito |
| NLB | **Disattivo** | A pagamento se attivato (~0,01 $/GB per direzione) |
| GWLB | **Disattivo** | A pagamento se attivato |

Con cross-zone disattivo ogni nodo invia traffico solo ai target della propria AZ: con 2 AZ e distribuzione target sbilanciata (es. 2 target in a, 8 in b) ogni nodo riceve ~50% del traffico: i 2 target di a ne prendono il 25% ciascuno, gli 8 di b solo il 6,25% → **hot spot** su a. Attivarlo su NLB migliora la distribuzione ma introduce costo e latenza inter-AZ.

### Preservazione client IP e Proxy Protocol v2

- **ALB**: termina la connessione; il client IP arriva in `X-Forwarded-For`, protocollo in `X-Forwarded-Proto`, porta in `X-Forwarded-Port`.
- **NLB target `instance`**: il client IP sorgente è preservato. **Target `ip`**: di default preservazione disattivata (il target vede l'IP del NLB) salvo attributo `preserve_client_ip.enabled=true`.
- **Proxy Protocol v2**: header binario prefissato al flusso TCP con IP/porta originali; abilitare `proxy_protocol_v2.enabled=true` sul TG e configurare il backend (nginx `proxy_protocol`, HAProxy `accept-proxy`) per interpretarlo.

!!! warning "Proxy Protocol non retrocompatibile"
    Se abiliti Proxy Protocol v2 sul target group ma il backend non lo interpreta, ogni connessione fallisce (header letto come dati corrotti). Abilitare backend e TG in modo coordinato.

### NLB con Elastic IP e PrivateLink

- NLB permette di assegnare **un Elastic IP per subnet** (`SubnetMappings`): utile per whitelist su firewall di clienti. L'associazione si decide **alla creazione**.
- Un NLB può essere esposto come **VPC Endpoint Service** (PrivateLink): i consumer creano un Interface Endpoint nella propria VPC senza peering né sovrapposizione CIDR; il provider vede il traffico originato dal NLB.

### GWLB e appliance di sicurezza

Il **Gateway Load Balancer** si inserisce nel percorso di rete tramite **Gateway Load Balancer Endpoint (GWLBE)** e route table: il traffico viene incapsulato in **GENEVE** (Generic Network Virtualization Encapsulation, UDP 6081; preserva il pacchetto originale e porta metadati di flusso) e inviato a una flotta di appliance (firewall, IDS/IPS, DPI) che lo restituisce dopo l'ispezione. Mantiene i flussi "sticky" (5-tuple) sulla stessa appliance e scala orizzontalmente.

```text
Client ─► IGW ─► [route table] ─► GWLBE ─► GWLB ─(GENEVE:6081)─► Appliance fleet
                                                         ◄────────────────┘
                                   ◄─ GWLBE ◄─ GWLB ◄─ (dopo ispezione) ─► App subnet
```

### TLS termination, ACM, SNI

- ALB e NLB (listener TLS) terminano TLS con certificati **AWS Certificate Manager (ACM)** — rinnovo automatico, gratuiti per uso con ELB — o importati.
- **SNI**: un listener HTTPS/TLS può avere più certificati (fino a 25 oltre al default); il client indica l'hostname e ELB seleziona il certificato.
- **Security policy**: definisce versioni TLS e cipher. Usare `ELBSecurityPolicy-TLS13-1-2-2021-06` (TLS 1.3 + 1.2) o `ELBSecurityPolicy-TLS13-1-3-2021-06` (solo 1.3); policy con suffisso `FIPS`/`PQ` per requisiti specifici. Le policy vecchie (`ELBSecurityPolicy-2016-08`) ammettono TLS 1.0/1.1.
- **mTLS** (ALB): modalità `verify` o `passthrough` con trust store su S3.

### Osservabilità

- **Access logs** su S3 (attributo `access_logs.s3.enabled`): campi come `request_processing_time`, `target_processing_time`, `elb_status_code`, `target_status_code`. Il bucket richiede una policy che autorizzi il principal ELB regionale.
- **Connection logs** (ALB): dettagli handshake TLS.
- **Metriche CloudWatch** (namespace `AWS/ApplicationELB`, `AWS/NetworkELB`):

| Metrica | Significato | Allarme tipico |
|---|---|---|
| `TargetResponseTime` | Latenza dal target (p99) | > SLO |
| `HTTPCode_ELB_5XX_Count` | 5xx generati dal **LB** (502/503/504) | > 0 sostenuto |
| `HTTPCode_Target_5XX_Count` | 5xx generati dall'**applicazione** | > soglia % |
| `UnHealthyHostCount` | Target unhealthy per TG/AZ | ≥ 1 |
| `RejectedConnectionCount` | Connessioni rifiutate (limite raggiunto) | > 0 |
| `ActiveFlowCount`, `TCP_Target_Reset_Count` (NLB) | Flussi attivi / reset dai target | Picchi anomali |

---

## Configurazione & Pratica

### Comandi `aws elbv2`

```bash
# Creare ALB internet-facing su 2 subnet pubbliche con security group
aws elbv2 create-load-balancer \
  --name prod-alb --type application --scheme internet-facing \
  --subnets subnet-0aaa subnet-0bbb --security-groups sg-0123

# Target group per servizio HTTP con health check personalizzato
aws elbv2 create-target-group \
  --name api-tg --protocol HTTP --port 8080 --vpc-id vpc-0abc \
  --target-type ip --health-check-path /healthz \
  --health-check-interval-seconds 10 --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 --matcher HttpCode=200-299

# Ridurre deregistration delay e abilitare slow start
aws elbv2 modify-target-group-attributes --target-group-arn "$TG_ARN" \
  --attributes Key=deregistration_delay.timeout_seconds,Value=30 \
               Key=slow_start.duration_seconds,Value=60

# Listener HTTPS con certificato ACM e policy TLS 1.3
aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" \
  --protocol HTTPS --port 443 \
  --certificates CertificateArn=arn:aws:acm:eu-west-1:111122223333:certificate/xxxx \
  --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \
  --default-actions Type=forward,TargetGroupArn="$TG_ARN"

# Redirect HTTP → HTTPS
aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" --protocol HTTP --port 80 \
  --default-actions 'Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'

# Stato di salute dei target
aws elbv2 describe-target-health --target-group-arn "$TG_ARN" \
  --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State,TargetHealth.Reason]' \
  --output table

# Attivare cross-zone su NLB
aws elbv2 modify-load-balancer-attributes --load-balancer-arn "$NLB_ARN" \
  --attributes Key=load_balancing.cross_zone.enabled,Value=true
```

### Listener rules: path, host, header e canary

```bash
# Path-based routing: /api/* → api-tg (priorità più bassa = valutata prima)
aws elbv2 create-rule --listener-arn "$LISTENER_ARN" --priority 10 \
  --conditions Field=path-pattern,Values='/api/*' \
  --actions Type=forward,TargetGroupArn="$API_TG"

# Host-based + header
aws elbv2 create-rule --listener-arn "$LISTENER_ARN" --priority 20 \
  --conditions Field=host-header,Values='admin.company.com' \
               Field=http-header,HttpHeaderConfig='{HttpHeaderName=X-Team,Values=[ops]}' \
  --actions Type=forward,TargetGroupArn="$ADMIN_TG"

# Canary: 90% stable / 10% canary con weighted forward
aws elbv2 modify-rule --rule-arn "$RULE_ARN" --actions '[{
  "Type":"forward",
  "ForwardConfig":{
    "TargetGroups":[
      {"TargetGroupArn":"'"$STABLE_TG"'","Weight":90},
      {"TargetGroupArn":"'"$CANARY_TG"'","Weight":10}
    ],
    "TargetGroupStickiness":{"Enabled":true,"DurationSeconds":600}
  }}]'
```

### Terraform

```hcl
resource "aws_lb" "app" {
  name               = "prod-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]

  idle_timeout               = 60
  drop_invalid_header_fields = true
  enable_deletion_protection = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "prod-alb"
    enabled = true
  }
}

resource "aws_lb_target_group" "api" {
  name                 = "api-tg"
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    path                = "/healthz"
    matcher             = "200-299"
    interval            = 10
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.app.certificate_arn

  default_action {
    type = "forward"
    forward {
      target_group {
        arn    = aws_lb_target_group.api.arn
        weight = 90
      }
      target_group {
        arn    = aws_lb_target_group.api_canary.arn
        weight = 10
      }
    }
  }
}

# NLB con Elastic IP statici (uno per AZ)
resource "aws_lb" "nlb" {
  name               = "prod-nlb"
  load_balancer_type = "network"
  enable_cross_zone_load_balancing = false

  dynamic "subnet_mapping" {
    for_each = zipmap(var.public_subnet_ids, aws_eip.nlb[*].id)
    content {
      subnet_id     = subnet_mapping.key
      allocation_id = subnet_mapping.value
    }
  }
}
```

### Integrazione EKS: AWS Load Balancer Controller

Il **AWS Load Balancer Controller** (installato via Helm, con IAM role tramite IRSA/Pod Identity) crea ALB da risorse `Ingress` e NLB da `Service` di tipo `LoadBalancer`.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip          # pod IP diretti, salta kube-proxy
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:eu-west-1:111122223333:certificate/xxxx
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06
    alb.ingress.kubernetes.io/ssl-redirect: "443"
    alb.ingress.kubernetes.io/healthcheck-path: /healthz
    alb.ingress.kubernetes.io/group.name: shared-public   # più Ingress → stesso ALB (riduce costi)
    alb.ingress.kubernetes.io/target-group-attributes: deregistration_delay.timeout_seconds=30
spec:
  ingressClassName: alb
  rules:
    - host: api.company.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
---
apiVersion: v1
kind: Service
metadata:
  name: tcp-gateway
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
spec:
  type: LoadBalancer
  loadBalancerClass: service.k8s.aws/nlb
  selector: { app: tcp-gateway }
  ports:
    - port: 443
      targetPort: 8443
```

Con `target-type: ip` il rolling update di un Deployment può rimuovere un pod prima che l'ALB smetta di inviargli traffico: aggiungere un **pod readiness gate** (`elbv2.k8s.aws/pod-readiness-gate-inject: enabled` sul namespace) e un `preStop` sleep pari al deregistration delay.

!!! warning "Costo"
    Ogni Ingress senza `group.name` crea un **ALB dedicato** (~16–22 $/mese + LCU, *Load Balancer Capacity Unit*, l'unità di fatturazione basata su connessioni, richieste e byte; più i costi per IPv4 pubblici). Raggruppare gli Ingress con `group.name` o usare un solo ALB con regole per host.

---

## Best Practices

- **Multi-AZ**: abilitare almeno 2 AZ e distribuire i target in modo uniforme; con NLB valutare cross-zone se sbilanciato.
- **Security group ALB → target**: consentire sul target solo traffico dal SG del load balancer (SG reference), non da `0.0.0.0/0`.
- **Health check dedicato**: endpoint `/healthz` leggero che verifica dipendenze critiche ma non profonde (evitare che un DB lento faccia uscire tutti i target).
- **Allineare i timeout**: keep-alive del backend **maggiore** dell'idle timeout del LB (vedi Troubleshooting).
- **Deregistration delay** allineato alla durata massima delle richieste; `preStop` hook + `SIGTERM` graceful nell'app.
- **TLS moderno**: policy TLS13 e redirect 80→443; HSTS gestito dall'applicazione o da regola ALB con header response (`routing.http.response.strict_transport_security`).
- **WAF**: associare AWS WAF all'ALB per filtraggio L7; Shield Advanced per DDoS.
- **Deletion protection** e access log attivi in produzione.
- **Stickiness solo se necessaria**: preferire applicazioni stateless; le sticky session (cookie `AWSALB`) riducono la distribuzione uniforme.
- **Dimensionamento**: ALB scala automaticamente ma non istantaneamente; per picchi noti (lanci, eventi) richiedere **pre-warming** al supporto AWS o usare LCU reservation.

!!! tip "IP fissi con ALB"
    Metti **AWS Global Accelerator** davanti ad ALB per avere 2 anycast IP statici e failover multi-regione, oppure NLB → target type `alb`.

---

## Troubleshooting

### 502 Bad Gateway

- **Sintomo**: `HTTPCode_ELB_502_Count` > 0, client vede `502`.
- **Cause**: il target chiude la connessione o restituisce risposta malformata; keep-alive del backend inferiore all'idle timeout del LB (il LB riusa una connessione già chiusa dal backend); protocollo TG errato (HTTP verso porta HTTPS); Lambda con risposta non valida.
- **Soluzione**: verificare nei log `elb_status_code=502` con `target_status_code=-`; portare il keep-alive del backend > idle timeout (es. nginx `keepalive_timeout 75s`, Node.js `server.keepAliveTimeout = 65000`); controllare protocollo/porta del TG.

### 503 Service Unavailable

- **Sintomo**: `503` generato dal LB (`target_status_code=-`).
- **Cause**: nessun target **registrato** nel TG (con target registrati ma tutti unhealthy scatta il fail-open, quindi di norma non 503); TG vuoto dopo un deploy; regola con peso 0 su tutti i TG; capacità del LB in scaling.
- **Soluzione**:
```bash
aws elbv2 describe-target-health --target-group-arn "$TG_ARN"
```
  Verificare registrazione, health check path, security group. Per picchi improvvisi: pre-warming.

### 504 Gateway Timeout

- **Sintomo**: `504` dopo esattamente `idle_timeout` secondi (default 60).
- **Cause**: il target non risponde entro l'idle timeout; SG/NACL del target blocca; backend saturo o query lenta.
- **Soluzione**: controllare `TargetResponseTime`; aumentare `idle_timeout.timeout_seconds` solo per richieste realmente lunghe (o usare polling/WebSocket); verificare che il SG del target ammetta il SG del LB sulla porta del traffico **e** dell'health check.
```bash
aws elbv2 modify-load-balancer-attributes --load-balancer-arn "$ALB_ARN" \
  --attributes Key=idle_timeout.timeout_seconds,Value=120
```

### Target unhealthy

- **Sintomo**: `Target.FailedHealthChecks`, `Target.Timeout`, `Target.ResponseCodeMismatch` in `describe-target-health`.
- **Cause**: SG non consente il traffico di health check; path errato; matcher troppo stretto (es. redirect 301 non in `200`); app lenta all'avvio (grace period insufficiente); porta di health check diversa dalla porta traffico.
- **Soluzione**: `curl` dell'endpoint dall'interno della VPC; correggere matcher (`200-399`); aumentare `HealthCheckTimeout`/`UnhealthyThreshold`; in ASG impostare `health_check_grace_period`.

### Drain lento durante deploy

- **Sintomo**: rolling deploy o scale-in impiega 5+ minuti per terminare i target.
- **Causa**: `deregistration_delay` default 300 s, anche se le richieste finiscono in secondi.
- **Soluzione**: ridurre a 15–60 s (`deregistration_delay.timeout_seconds`); su EKS abbinare `terminationGracePeriodSeconds` e `preStop: sleep` coerenti; NLB: attivare `deregistration_delay.connection_termination.enabled` se le connessioni long-lived bloccano il drain.

### NLB: connessioni che falliscono con target `ip`/client IP

- **Sintomo**: backend vede IP del NLB o timeout con hairpin (client e target nella stessa istanza/NLB interno).
- **Causa**: client IP preservation e NLB interno con target che è anche il client → loop bloccato.
- **Soluzione**: disattivare `preserve_client_ip.enabled` o usare Proxy Protocol v2 e ricavare l'IP dall'header.

---

## Relazioni

??? info "VPC — Subnet, SG e NACL"
    Il load balancer vive nelle subnet della VPC (pubbliche per internet-facing, private per internal) e usa security group per filtrare. Le regole SG dei target devono referenziare il SG del LB.

    **Approfondimento completo →** [VPC](vpc.md)

??? info "Route 53 — Alias verso ELB"
    I record **Alias** puntano al DNS name del LB (gratuiti, con `EvaluateTargetHealth`); routing weighted/latency/failover tra load balancer di più Region.

    **Approfondimento completo →** [Route 53](route53.md)

??? info "CloudFront — CDN davanti all'ALB"
    ALB come origin di CloudFront: cache e protezione DDoS al bordo, limitando l'origin con header segreto o managed prefix list.

    **Approfondimento completo →** [CloudFront](cloudfront.md)

??? info "EC2 Auto Scaling — target dinamici"
    Un ASG registra e deregistra automaticamente istanze nei target group e può usare i check ELB come health check.

    **Approfondimento completo →** [EC2 Auto Scaling](../compute/ec2-autoscaling.md)

??? info "EKS — Ingress e Service LoadBalancer"
    Il AWS Load Balancer Controller traduce Ingress/Service in ALB/NLB con target type `ip`.

    **Approfondimento completo →** [EKS](../containers/eks.md)

??? info "Layer 4 vs Layer 7 — concetti generali"
    Differenze concettuali indipendenti dal provider tra bilanciamento L4 e L7.

    **Approfondimento completo →** [Layer 4 vs Layer 7](../../../networking/load-balancing/layer4-vs-layer7.md)

---

## Riferimenti

- [Elastic Load Balancing — User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/)
- [Application Load Balancer — Listener rules](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-listeners.html)
- [Network Load Balancer — Target groups](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/load-balancer-target-groups.html)
- [Gateway Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/gateway/)
- [Security policies per ALB](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/describe-ssl-policies.html)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [ELB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/)
