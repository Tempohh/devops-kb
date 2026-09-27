---
title: "AWS VPC Lattice"
slug: vpc-lattice
category: cloud
tags: [aws, vpc-lattice, application-networking, service-network, service-mesh, iam, cross-account, ecs, eks, lambda]
search_keywords: [VPC Lattice, application networking, service network, service directory, target group, auth policy, IAM-based auth, L7 routing, Layer 7 networking, service-to-service communication, AWS RAM, Resource Access Manager, cross-account networking, alternativa service mesh, alternativa Transit Gateway, alternativa PrivateLink, Lattice ARN, VPC association, Lattice listener, weighted routing]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/vpc-avanzato, cloud/aws/networking/elastic-load-balancing, cloud/aws/iam/policies-avanzate]
official_docs: https://docs.aws.amazon.com/vpc-lattice/latest/ug/
status: complete
difficulty: advanced
last_updated: 2026-09-27
---

# AWS VPC Lattice

## Panoramica

**VPC Lattice** è un servizio di *application networking* gestito da AWS (GA novembre 2023) che connette, monitora e mette in sicurezza le comunicazioni service-to-service a livello **L7 (HTTP/HTTPS/gRPC)**, senza richiedere sidecar, agent o modifiche al codice applicativo. Al posto di instradare pacchetti tra subnet (come Transit Gateway) o esporre singoli endpoint (come PrivateLink), Lattice ragiona in termini di **servizi**: un servizio consumer si connette a un servizio logico esposto tramite un **service network**, indipendentemente da dove girano i target reali (EC2, container ECS/EKS, pod Kubernetes, funzioni Lambda), anche across VPC e across account.

Si usa quando serve connettività service-to-service governata da policy IAM a livello applicativo — architetture a microservizi multi-team, multi-account, dove ogni servizio deve autenticare ed autorizzare le chiamate in ingresso senza gestire certificati mTLS o un control plane di service mesh. **Non** si usa per instradamento di rete generico L3/L4 (resta compito di VPC Peering/Transit Gateway), né per traffico non-HTTP (Lattice non supporta UDP, e il supporto TCP è limitato rispetto a un NLB diretto).

## Concetti Chiave

!!! note "I tre building block di VPC Lattice"
    - **Service Network** — il "namespace" di rete che raggruppa uno o più servizi e le VPC che possono raggiungerli. È l'unità di condivisione cross-account (via AWS RAM).
    - **Service** — un endpoint logico HTTP/HTTPS/gRPC esposto ad altri servizi. Ha un DNS name generato automaticamente (`<service>.<hash>.vpc-lattice-svcs.<region>.on.aws`) e supporta HTTPS con certificato custom.
    - **Target Group** — l'insieme di risorse compute reali dietro un servizio: istanze EC2, IP, funzioni Lambda, o pod ECS/EKS registrati tramite il controller Kubernetes Gateway API.

**Auth Policy IAM-based**: ogni servizio Lattice può richiedere che il chiamante presenti credenziali IAM valide (SigV4). La policy è scritta come un documento IAM standard (`Effect`, `Principal`, `Action`, `Resource`, `Condition`) e valutata **a livello di servizio**, non di subnet o security group — è autorizzazione applicativa, non network ACL.

**Listener e regole**: ogni servizio ha uno o più listener (porta + protocollo) con regole di routing basate su path, header o metodo HTTP, che instradano verso uno o più target group con **weighted routing** (utile per canary/blue-green).

## Architettura / Come Funziona

```
Consumer VPC                          Service Network                    Provider VPC/Account
─────────────                         ───────────────                    ─────────────────────
EC2/Lambda/ECS  ──DNS lookup──→  Lattice Service (HTTPS)  ──auth policy──→  Target Group
   (client)                      + Listener + Rules                        (ECS/EKS/Lambda/EC2/IP)
                                         │
                                  associata a N VPC
                                  condivisa via AWS RAM
                                  tra N account
```

Il traffico non attraversa mai route table o Internet Gateway del consumer: Lattice inietta un endpoint di rete gestito nella VPC associata (simile concettualmente a un Interface Endpoint PrivateLink, ma condiviso per l'intero service network invece che per singolo servizio). Il **data plane è gestito da AWS** — non ci sono sidecar da patchare, nessun control plane da operare (a differenza di un service mesh come Istio o App Mesh).

**Confronto pratico con le alternative già coperte in [VPC Avanzato](vpc-avanzato.md):**

| Alternativa | Perché non basta / quando preferire Lattice |
|---|---|
| **Transit Gateway** | TGW instrada a L3 tra intere VPC (hub-and-spoke); non conosce il concetto di "servizio" né applica policy per singola chiamata HTTP. Usa Lattice quando il controllo deve essere a livello di API/servizio, non di subnet. |
| **AWS PrivateLink** | PrivateLink espone **un** servizio per Interface Endpoint, con setup 1:1 per ogni consumer VPC. Lattice condivide un intero service network tra molte VPC/account con un'unica associazione, e aggiunge routing L7 (path/header) che PrivateLink non ha. |
| **Service Mesh (Istio, App Mesh)** | Un mesh richiede sidecar proxy su ogni pod/istanza e un control plane da mantenere. Lattice è completamente gestito da AWS, senza sidecar: minore complessità operativa ma minore flessibilità (no traffic mirroring avanzato, no circuit breaking custom). |

## Configurazione & Pratica

### Creare un service network e associare una VPC

```bash
# 1. Creare il service network
SN_ID=$(aws vpc-lattice create-service-network \
    --name "prod-service-network" \
    --auth-type AWS_IAM \
    --query 'id' --output text)

# 2. Associare la VPC consumer (necessario per risolvere il DNS dei servizi)
aws vpc-lattice create-service-network-vpc-association \
    --service-network-identifier $SN_ID \
    --vpc-identifier vpc-CONSUMER \
    --security-group-ids sg-lattice-consumer

# 3. Creare il servizio
SVC_ID=$(aws vpc-lattice create-service \
    --name "orders-api" \
    --auth-type AWS_IAM \
    --query 'id' --output text)

# 4. Associare il servizio al service network
aws vpc-lattice create-service-network-service-association \
    --service-network-identifier $SN_ID \
    --service-identifier $SVC_ID
```

### Registrare un target group ECS/EKS e creare listener + regole

```bash
# Target group verso task ECS (IP target type, tipico con awsvpc network mode)
TG_ID=$(aws vpc-lattice create-target-group \
    --name "orders-tg" \
    --type IP \
    --config '{
        "port": 8080,
        "protocol": "HTTP",
        "vpcIdentifier": "vpc-PROVIDER",
        "healthCheck": {
            "enabled": true,
            "path": "/healthz",
            "healthyThresholdCount": 3,
            "unhealthyThresholdCount": 3,
            "intervalSeconds": 15
        }
    }' \
    --query 'id' --output text)

# Registrare i target (IP dei task ECS)
aws vpc-lattice register-targets \
    --target-group-identifier $TG_ID \
    --targets id=10.0.1.15,port=8080 id=10.0.1.16,port=8080

# Listener HTTPS sul servizio
LISTENER_ID=$(aws vpc-lattice create-listener \
    --service-identifier $SVC_ID \
    --name "https-listener" \
    --protocol HTTPS \
    --port 443 \
    --default-action '{"forward":{"targetGroups":[{"targetGroupIdentifier":"'$TG_ID'","weight":100}]}}' \
    --query 'id' --output text)

# Regola: instradare /v2/* verso un target group canary con peso 10%
aws vpc-lattice create-rule \
    --service-identifier $SVC_ID \
    --listener-identifier $LISTENER_ID \
    --name "canary-v2" \
    --priority 10 \
    --match '{"httpMatch":{"pathMatch":{"match":{"prefix":"/v2/"}}}}' \
    --action '{"forward":{"targetGroups":[{"targetGroupIdentifier":"'$TG_ID'","weight":90},{"targetGroupIdentifier":"'$TG_ID'_CANARY","weight":10}]}}'
```

Per **EKS**, la registrazione dei target group avviene tipicamente tramite il [Gateway API Controller per VPC Lattice](https://github.com/aws/aws-application-networking-k8s), che mappa risorse Kubernetes `HTTPRoute`/`Gateway` direttamente su servizi e target group Lattice — evitando chiamate CLI manuali per ogni deploy.

### Auth policy IAM a livello di servizio

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::111111111111:role/checkout-service-role"
      },
      "Action": "vpc-lattice-svcs:Invoke",
      "Resource": "arn:aws:vpc-lattice:eu-central-1:222222222222:service/svc-0123456789abcdef",
      "Condition": {
        "StringEquals": {
          "vpc-lattice-svcs:RequestMethod": ["GET", "POST"]
        }
      }
    }
  ]
}
```

```bash
aws vpc-lattice put-auth-policy \
    --resource-identifier $SVC_ID \
    --policy file://orders-api-auth-policy.json
```

Solo `checkout-service-role` (account 111111111111) può invocare `orders-api` (account 222222222222), e solo con `GET`/`POST` — autorizzazione fine-grained senza toccare Security Group o NACL.

### Cross-account: condivisione del service network via AWS RAM

```bash
# Nell'account "hub" proprietario del service network
aws ram create-resource-share \
    --name "prod-service-network-share" \
    --resource-arns arn:aws:vpc-lattice:eu-central-1:222222222222:servicenetwork/$SN_ID \
    --principals 111111111111 333333333333

# Nell'account consumer: accettare l'invito
aws ram accept-resource-share-invitation \
    --resource-share-invitation-arn arn:aws:ram:eu-central-1:111111111111:resource-share-invitation/xxxx

# Poi, nell'account consumer, associare la propria VPC allo stesso service network
aws vpc-lattice create-service-network-vpc-association \
    --service-network-identifier arn:aws:vpc-lattice:eu-central-1:222222222222:servicenetwork/$SN_ID \
    --vpc-identifier vpc-CONSUMER-B
```

Una volta accettata la resource share, qualunque VPC associata al service network — in qualsiasi account partecipante — può risolvere e chiamare i servizi condivisi, soggetta all'auth policy IAM del singolo servizio.

## Best Practices

!!! tip "Un service network per dominio/ambiente, non uno globale"
    Creare service network separati per `prod`/`staging`/`dev` (o per bounded context) invece di un unico service network aziendale: limita il blast radius di una auth policy errata e semplifica l'auditing con AWS RAM.

- Abilitare **access logging** (`vpc-lattice:AccessLogSubscription` verso CloudWatch Logs, S3 o Kinesis Firehose) su ogni servizio in produzione: è l'unico modo per avere visibilità sulle richieste L7 senza sidecar.
- Preferire **IP target type** per task ECS in modalità `awsvpc` e per pod EKS — evita di dover gestire target group per singola istanza EC2 sottostante.
- Usare **weighted routing** per canary release invece di deployment blue/green completi: riduce il rischio senza duplicare l'infrastruttura compute.
- Applicare auth policy con `Condition` su `vpc-lattice-svcs:RequestMethod` o header custom per un controllo più granulare del semplice allow/deny per principal.

!!! warning "Limiti noti da verificare prima di adottare Lattice in produzione"
    - **Nessun supporto UDP** — solo TCP-based (HTTP/HTTPS/gRPC, e TCP generico in preview/GA parziale a seconda della region). Per DNS, syslog o altri protocolli UDP serve un'alternativa (NLB diretto, TGW).
    - **Latenza aggiuntiva** rispetto a un NLB diretto o a PrivateLink puro — il data plane Lattice introduce un hop L7 in più; misurare con test di carico prima di usarlo su path critici a bassissima latenza.
    - **Quote da controllare**: numero massimo di service-network-service-association per service network, numero di VPC associabili, numero di target per target group — verificare i valori correnti in [AWS Service Quotas](https://docs.aws.amazon.com/vpc-lattice/latest/ug/quotas.html) prima del design, perché cambiano nel tempo.
    - Il DNS name generato è pensato per risoluzione interna al service network: per esporlo con un nome custom serve comunque un CNAME/alias Route 53 verso il DNS name di Lattice.

## Troubleshooting

### Scenario 1 — Il consumer non risolve il DNS del servizio Lattice

**Sintomo:** `nslookup orders-api.xxxx.vpc-lattice-svcs.eu-central-1.on.aws` fallisce o restituisce NXDOMAIN dalla VPC consumer.

**Causa:** La VPC consumer non è associata al service network, oppure `enableDnsSupport`/`enableDnsHostnames` sono disabilitati sulla VPC.

**Soluzione:**
```bash
# Verificare l'associazione VPC ↔ service network
aws vpc-lattice list-service-network-vpc-associations \
    --service-network-identifier $SN_ID \
    --query 'items[?vpcId==`vpc-CONSUMER`]'

# Verificare DNS support sulla VPC
aws ec2 describe-vpc-attribute --vpc-id vpc-CONSUMER --attribute enableDnsSupport
aws ec2 describe-vpc-attribute --vpc-id vpc-CONSUMER --attribute enableDnsHostnames
```

### Scenario 2 — Richieste rifiutate con `403 AccessDeniedException`

**Sintomo:** Il client riceve `403` con corpo `AccessDeniedException` nonostante il servizio sia raggiungibile a livello di rete.

**Causa:** L'auth policy IAM del servizio non include il principal chiamante, oppure le credenziali della richiesta non sono firmate con SigV4 (richiesto quando `auth-type` del servizio è `AWS_IAM`).

**Soluzione:**
```bash
# Ispezionare l'auth policy corrente
aws vpc-lattice get-auth-policy --resource-identifier $SVC_ID

# Verificare che il ruolo chiamante abbia anche il permesso IAM lato client
# (serve ENTRAMBI: permesso IAM del caller + Resource Policy del servizio)
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::111111111111:role/checkout-service-role \
    --action-names vpc-lattice-svcs:Invoke \
    --resource-arns arn:aws:vpc-lattice:eu-central-1:222222222222:service/$SVC_ID
```

### Scenario 3 — Target group in stato `Unhealthy`, servizio irraggiungibile

**Sintomo:** Tutti i target registrati risultano `Unhealthy` in `list-targets`, il servizio risponde `503`.

**Causa:** Il Security Group associato ai target (task ECS/pod EKS) non permette traffico in ingresso dal Security Group associato al service network sulla porta di health check, oppure il path di health check configurato non esiste nell'applicazione.

**Soluzione:**
```bash
# Controllare stato e reason dei target
aws vpc-lattice list-targets --target-group-identifier $TG_ID \
    --query 'items[*].[id,status,reasonCode]' --output table

# Verificare che il SG dei target permetta ingresso dal SG lattice-consumer sulla porta configurata
aws ec2 describe-security-groups --group-ids sg-TARGET \
    --query 'SecurityGroups[0].IpPermissions'
```

### Scenario 4 — La resource share RAM non appare nell'account consumer

**Sintomo:** Dopo `create-resource-share`, l'account consumer non vede alcun invito e non può associare la propria VPC.

**Causa:** Il principal specificato in `--principals` è errato (Account ID sbagliato, o si è usato un OU ARN quando serve un Account ID diretto), oppure la resource share è stata creata senza `--principals` (share "privata" senza destinatari).

**Soluzione:**
```bash
# Elencare gli inviti pendenti nell'account consumer
aws ram get-resource-share-invitations \
    --query 'resourceShareInvitations[?status==`PENDING`]'

# Se assente, verificare i principal configurati sulla share nell'account hub
aws ram get-resource-share-associations \
    --association-type PRINCIPAL \
    --resource-share-arns arn:aws:ram:eu-central-1:222222222222:resource-share/xxxx
```

## Relazioni

??? info "VPC Avanzato — Transit Gateway, PrivateLink, VPN, Direct Connect"
    VPC Lattice copre la connettività **applicativa L7** tra servizi; per instradamento L3 tra intere VPC, esposizione di singoli endpoint privati o connettività ibrida on-premises, restano gli strumenti descritti in dettaglio.

    **Approfondimento completo →** [VPC Avanzato](vpc-avanzato.md)

??? info "Elastic Load Balancing — NLB/ALB come target"
    I target group Lattice possono puntare a un Network Load Balancer esistente davanti a un servizio, utile per migrare gradualmente un'architettura già basata su ALB/NLB verso Lattice senza riscrivere il load balancing applicativo.

    **Approfondimento completo →** [Elastic Load Balancing](elastic-load-balancing.md)

??? info "IAM Policies Avanzate — sintassi delle auth policy"
    Le auth policy di Lattice sono documenti IAM standard: la sintassi di `Condition`, `Principal` e valutazione allow/deny segue le stesse regole delle policy IAM generiche.

    **Approfondimento completo →** [Policies Avanzate](../iam/policies-avanzate.md)

## Riferimenti

- [AWS VPC Lattice — User Guide](https://docs.aws.amazon.com/vpc-lattice/latest/ug/)
- [VPC Lattice — Service Quotas](https://docs.aws.amazon.com/vpc-lattice/latest/ug/quotas.html)
- [AWS Gateway API Controller for VPC Lattice (EKS)](https://github.com/aws/aws-application-networking-k8s)
- [AWS Resource Access Manager — User Guide](https://docs.aws.amazon.com/ram/latest/userguide/)
