---
title: "AWS Global Accelerator"
slug: global-accelerator
category: cloud
tags: [aws, global-accelerator, anycast, failover, multi-region, networking, edge]
search_keywords: [AWS Global Accelerator, GA, Global Accelerator, anycast IP, static anycast IP, standard accelerator, custom routing accelerator, endpoint group, traffic dial, client affinity, health check, failover multi-regione, IP anycast statico, edge network AWS, AWS global network, TCP/UDP acceleration, DDoS Shield, disaster recovery multi-region, RTO, bilanciamento globale, anycast load balancing]
parent: cloud/aws/networking/_index
related: [cloud/aws/networking/elastic-load-balancing, cloud/aws/networking/route53, cloud/aws/networking/cloudfront, cloud/aws/networking/vpc]
official_docs: https://docs.aws.amazon.com/global-accelerator/latest/dg/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# AWS Global Accelerator

## Panoramica

**AWS Global Accelerator (GA)** è un servizio di networking che assegna **2 IP anycast statici** e instrada il traffico verso l'endpoint AWS più vicino e più sano (ALB, NLB, EC2, Elastic IP) attraverso la **rete backbone globale di AWS**, non attraverso l'internet pubblico. Il client si connette sempre agli stessi 2 IP; GA decide internamente verso quale regione/endpoint instradare, e in caso di failure sposta il traffico su un altro endpoint in **decine di secondi** (dominati dal tempo di detection dell'health check), senza che il client debba ri-risolvere alcun nome DNS.

È un servizio **completamente diverso** da CloudFront e da Route 53, anche se tutti e tre appaiono nelle discussioni su "traffico globale":

- **CloudFront** è una CDN: cache contenuti HTTP/HTTPS al bordo (edge location) e serve risposte dalla cache più vicina. Non è pensato per protocolli generici (TCP/UDP) né per applicazioni non cacheable.
- **Route 53 failover routing** è **DNS-based**: cambia la risposta DNS quando un health check fallisce, ma il cambiamento si propaga solo dopo che il **TTL** del record scade lato client/resolver — spesso minuti, talvolta più per resolver che ignorano il TTL.
- **Global Accelerator** non fa caching e non è DNS-based per il failover: gli IP anycast restano fissi, e il routing interno alla rete AWS cambia **senza redirigere il client altrove**. Il failover è quindi dell'ordine di **decine di secondi** (con health check a 10s), non dei minuti.

Si usa GA quando serve: un **IP statico** stabile per whitelist su firewall di terzi, un **RTO molto basso** in scenari multi-regione (disaster recovery attivo-passivo o attivo-attivo), traffico **non-HTTP** (gaming UDP, IoT, VoIP) che CloudFront non può accelerare, oppure quando serve instradare il traffico sul backbone AWS invece che sul routing BGP pubblico per ridurre latenza e jitter. **Non serve** per contenuti statici/cacheable via HTTP (CloudFront è più economico ed efficace) e non serve quando un failover di qualche minuto via Route 53 è accettabile (costo inferiore, nessun servizio aggiuntivo).

---

## Concetti Chiave

!!! note "Componenti principali"
    - **Accelerator**: risorsa che possiede i 2 IP anycast statici (o un pool di IP BYOIP) e il DNS name `xxxxxxxx.awsglobalaccelerator.com`.
    - **Listener**: porta/protocollo (TCP e/o UDP) su cui l'accelerator accetta traffico.
    - **Endpoint group**: insieme di endpoint associati a **una Region**; ha un `traffic dial` (0-100%) e health check propri.
    - **Endpoint**: destinazione finale — ALB, NLB, istanza EC2, o Elastic IP.
    - **Traffic dial**: percentuale di traffico instradabile verso un endpoint group; usato per drenare gradualmente una regione o per blue/green a livello regionale.
    - **Client affinity**: `NONE` (default, hash su 5-tuple: IP/porta sorgente, IP/porta destinazione, protocollo) oppure `SOURCE_IP` (hash su IP sorgente + IP destinazione, per protocolli che richiedono che tutte le connessioni di un client finiscano sullo stesso endpoint, es. UDP stateful).

### Standard Accelerator vs Custom Routing Accelerator

| Caratteristica | Standard Accelerator | Custom Routing Accelerator |
|---|---|---|
| Uso tipico | Failover multi-regione, IP fissi per app HTTP/TCP/UDP | Gaming/IoT con migliaia di container/VM dietro pochi IP, porta destinazione custom per client |
| Endpoint | ALB, NLB, EC2, Elastic IP | Solo VPC subnet (mappa porta pubblica → porta privata su istanza specifica) |
| Health check | Sì, per endpoint group | No (GA non esegue health check sugli endpoint custom routing) |
| Porte | Listener espliciti definiti dall'utente | Range di porte mappate 1:1 o N:1 verso destinazioni interne |
| Caso d'uso distintivo | DR multi-region, API globali | Piattaforme multiplayer con matchmaking che assegna client a server specifici |

### Anycast IP: perché conta

Gli IP anycast di GA sono annunciati **da tutti gli edge location AWS contemporaneamente**: il client si connette sempre allo stesso IP, ma il routing BGP di internet lo porta all'edge più vicino, che poi instrada sul backbone privato AWS verso l'endpoint reale. Questo elimina la necessità di risoluzione DNS ripetuta e rende il fail­over indipendente da TTL/cache DNS lato client.

!!! warning "Non è un CDN"
    GA non memorizza né cache alcun contenuto: ogni richiesta arriva comunque all'origin (ALB/NLB/EC2). Per contenuti statici/cacheable HTTP, CloudFront riduce sia latenza che costo egress molto più di GA.

---

## Architettura / Come Funziona

```text
Client
  │  connessione ai 2 IP anycast statici (es. 75.2.x.x, 99.83.x.x)
  ▼
Edge location AWS più vicino (routing BGP anycast)
  │  ingresso nella rete backbone privata AWS
  ▼
Global Accelerator (valuta endpoint group per health + traffic dial)
  │
  ├──► Endpoint group eu-west-1 (traffic dial 100%) ──► ALB / NLB / EC2
  └──► Endpoint group us-east-1 (traffic dial 0%, standby) ──► ALB / NLB / EC2
```

!!! warning "Traffic dial 0% = nessun failover automatico"
    Un endpoint group con dial a 0% **non riceve traffico nemmeno se l'altro è unhealthy**: il dial limita la quota instradabile verso il gruppo. Lo schema sopra è quindi un **failover manuale** (si alza il dial a 100% durante l'incidente). Per failover **automatico** lasciare entrambi i gruppi a 100%: GA instrada alla regione sana più vicina al client (active-active), oppure usare un dial parziale sullo standby.

### Flusso di failover

1. Il **health check** dell'endpoint group (configurabile: path HTTP/HTTPS, porta, intervallo, soglia) rileva un endpoint o un'intera regione come unhealthy.
2. GA **smette di instradare nuovo traffico** verso quell'endpoint group, redistribuendo secondo i `traffic dial` degli endpoint group rimanenti sani.
3. Il client continua a usare gli stessi 2 IP: non c'è nessuna propagazione DNS da attendere. Il tempo di failover è dominato dal tempo di detection del health check (default: 3 controlli falliti a intervalli di 30s = ~90s, configurabile fino a 10s di intervallo).

### Traffic dial e drenaggio regionale

Il `traffic dial` non è un semplice on/off: riducendolo gradualmente (es. 100% → 50% → 0%) si drena il traffico da una regione senza interrompere le connessioni esistenti bruscamente, utile per maintenance window pianificate o migrazioni.

### Zonal shift e zonal autoshift

Lo **zonal shift** (Route 53 Application Recovery Controller) non è una funzione di GA ma dei load balancer ALB/NLB che stanno dietro: sposta il traffico fuori da una singola Availability Zone quando il problema è isolato a quella AZ. GA gestisce il failover a livello di endpoint/Region; i due meccanismi si combinano.

---

## Configurazione & Pratica

### CLI: creazione accelerator con 2 endpoint group

```bash
# 1. Creare l'accelerator (IP anycast statici assegnati automaticamente)
ACCELERATOR_ARN=$(aws globalaccelerator create-accelerator \
  --name prod-api-accelerator \
  --ip-address-type IPV4 \
  --enabled \
  --region us-west-2 \
  --query 'Accelerator.AcceleratorArn' --output text)   # il control plane di GA vive sempre in us-west-2

# 2. Recuperare gli IP statici assegnati
aws globalaccelerator describe-accelerator \
  --accelerator-arn "$ACCELERATOR_ARN" \
  --query 'Accelerator.IpSets[0].IpAddresses' --region us-west-2

# 3. Creare listener TCP/443
LISTENER_ARN=$(aws globalaccelerator create-listener \
  --accelerator-arn "$ACCELERATOR_ARN" \
  --protocol TCP \
  --port-ranges FromPort=443,ToPort=443 \
  --client-affinity NONE \
  --region us-west-2 \
  --query 'Listener.ListenerArn' --output text)

# 4. Endpoint group primario (eu-west-1, 100% traffico)
aws globalaccelerator create-endpoint-group \
  --listener-arn "$LISTENER_ARN" \
  --endpoint-group-region eu-west-1 \
  --traffic-dial-percentage 100 \
  --health-check-protocol HTTPS \
  --health-check-path /healthz \
  --health-check-interval-seconds 10 \
  --threshold-count 3 \
  --endpoint-configurations EndpointId="$ALB_ARN_EUWEST1",Weight=100 \
  --region us-west-2

# 5. Endpoint group secondario (us-east-1, standby a 0%)
aws globalaccelerator create-endpoint-group \
  --listener-arn "$LISTENER_ARN" \
  --endpoint-group-region us-east-1 \
  --traffic-dial-percentage 0 \
  --health-check-protocol HTTPS \
  --health-check-path /healthz \
  --endpoint-configurations EndpointId="$ALB_ARN_USEAST1",Weight=100 \
  --region us-west-2
```

### Test di failover manuale (drenaggio regionale)

```bash
# Simulare failover: portare eu-west-1 a 0% e us-east-1 a 100%
aws globalaccelerator update-endpoint-group \
  --endpoint-group-arn "$EG_EUWEST1_ARN" \
  --traffic-dial-percentage 0 --region us-west-2

aws globalaccelerator update-endpoint-group \
  --endpoint-group-arn "$EG_USEAST1_ARN" \
  --traffic-dial-percentage 100 --region us-west-2

# Verificare stato health degli endpoint
aws globalaccelerator describe-endpoint-group \
  --endpoint-group-arn "$EG_EUWEST1_ARN" --region us-west-2 \
  --query 'EndpointGroup.EndpointDescriptions[].[EndpointId,HealthState,HealthReason]' \
  --output table
```

### Terraform

```hcl
# Le API di GA sono servite solo da us-west-2: il provider AWS va configurato
# con region = "us-west-2" (o un alias dedicato) per queste risorse.
resource "aws_globalaccelerator_accelerator" "api" {
  name            = "prod-api-accelerator"
  ip_address_type = "IPV4"
  enabled         = true
}

resource "aws_globalaccelerator_listener" "https" {
  accelerator_arn = aws_globalaccelerator_accelerator.api.id
  client_affinity = "NONE"
  protocol        = "TCP"

  port_range {
    from_port = 443
    to_port   = 443
  }
}

resource "aws_globalaccelerator_endpoint_group" "primary" {
  listener_arn          = aws_globalaccelerator_listener.https.id
  endpoint_group_region = "eu-west-1"
  traffic_dial_percentage = 100

  health_check_protocol = "HTTPS"
  health_check_path     = "/healthz"
  health_check_interval_seconds = 10
  threshold_count       = 3

  endpoint_configuration {
    endpoint_id = aws_lb.eu_west_1.arn
    weight      = 100
  }
}

resource "aws_globalaccelerator_endpoint_group" "standby" {
  listener_arn          = aws_globalaccelerator_listener.https.id
  endpoint_group_region = "us-east-1"
  traffic_dial_percentage = 0

  health_check_protocol = "HTTPS"
  health_check_path     = "/healthz"

  endpoint_configuration {
    endpoint_id = aws_lb.us_east_1.arn
    weight      = 100
  }
}
```

---

## Best Practices

- **Preferire GA a Route 53 failover routing** quando l'RTO richiesto è dell'ordine dei secondi, non dei minuti: DNS failover dipende da TTL e da resolver che spesso ignorano il TTL indicato (caching aggressivo lato ISP/browser).
- **Non usare GA per contenuti HTTP cacheable**: CloudFront è più economico (nessun costo per-ora e data transfer generalmente inferiore) e più efficace grazie alla cache.
- **Combinare GA con ALB o NLB**, non con EC2 direttamente, salvo casi semplici: mantiene health check e scaling delegati al load balancer.
- **Client affinity `SOURCE_IP`** solo se il protocollo applicativo richiede stickiness per IP client (es. sessioni UDP stateful); altrimenti lasciare `NONE` per distribuzione migliore.
- **Health check path dedicato** e leggero, come per ALB/NLB — evitare dipendenze a cascata che marcano l'intero endpoint group unhealthy per un problema isolato.
- **Traffic dial per migrazioni**: drenare gradualmente (100→50→0) invece di uno switch brusco, per non concentrare tutte le connessioni attive sull'altra regione in un istante.
- **BYOIP** se serve mantenere IP esistenti già whitelisted da clienti/partner: GA supporta il bring-your-own-IP per gli anycast.

!!! tip "Quando NON serve Global Accelerator"
    Se il traffico è HTTP(S) cacheable → CloudFront. Se un failover di qualche minuto è accettabile e non serve IP statico → Route 53 failover routing (gratuito con Alias record). GA aggiunge valore solo quando conta la combinazione IP-fisso + failover-in-secondi + backbone-privato.

---

## Troubleshooting

### Costo superiore alle attese

- **Sintomo**: bolletta AWS con voce `Global Accelerator` significativamente più alta del previsto.
- **Causa**: GA ha un costo **fisso per ora** (accelerator fee, indipendente dal traffico) **più** un **premium per-GB di data transfer** superiore al transfer standard EC2/ELB — il traffico attraversa il backbone privato AWS, che ha un costo diverso dal transfer pubblico.
- **Soluzione**: verificare con Cost Explorer la voce `AWSGlobalAccelerator`; per workload a basso traffico ma che richiedono solo IP fisso, valutare NLB con Elastic IP (nessun costo per-ora aggiuntivo) invece di GA se non serve failover multi-regione.

### Health check cross-region marca erroneamente unhealthy

- **Sintomo**: `describe-endpoint-group` mostra `HealthState: UNHEALTHY` per un endpoint group anche se l'ALB/NLB target risulta sano se testato direttamente.
- **Causa**: il **security group** dell'endpoint (ALB/NLB) non consente il traffico di health check di GA, che arriva da IP range specifici pubblicati da AWS (non dagli IP anycast stessi); oppure il path di health check richiede autenticazione che GA non fornisce.
- **Soluzione**: aprire il security group ai range IP pubblicati in `ip-ranges.json` (filtro `service: GLOBALACCELERATOR`); usare un path `/healthz` pubblico senza auth.

```bash
curl -s https://ip-ranges.amazonaws.com/ip-ranges.json | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print([p['ip_prefix'] for p in d['prefixes'] if p['service']=='GLOBALACCELERATOR'])"
```

### Failover più lento del previsto

- **Sintomo**: durante un test di interruzione regionale, il traffico continua a raggiungere l'endpoint group unhealthy per 60-90+ secondi.
- **Causa**: il tempo di detection dipende da `health-check-interval-seconds` × `threshold-count`; con i default (30s × 3) il rilevamento richiede fino a 90s prima che GA smetta di instradare.
- **Soluzione**: ridurre `health-check-interval-seconds` a 10s e `threshold-count` a 2-3 per rilevamento più rapido (~20-30s), bilanciando contro falsi positivi da blip transitori.

### Connessioni esistenti interrotte durante drenaggio traffic dial

- **Sintomo**: riducendo il `traffic-dial-percentage` di un endpoint group, alcune connessioni TCP attive vengono interrotte immediatamente invece di completarsi gracefully.
- **Causa**: il traffic dial influenza solo le **nuove** connessioni; connessioni esistenti dovrebbero proseguire verso lo stesso endpoint, ma un endpoint marcato unhealthy (non solo drenato) chiude i flussi attivi.
- **Soluzione**: distinguere drenaggio pianificato (traffic dial, connessioni esistenti preservate) da rimozione per unhealthy (interruzione immediata); per maintenance pianificate preferire il traffic dial graduale e non disabilitare l'endpoint stesso finché le connessioni non sono terminate naturalmente.

---

## Relazioni

??? info "Elastic Load Balancing — endpoint tipico di GA"
    ALB e NLB sono gli endpoint più comuni dietro un accelerator; GA aggiunge IP anycast statici e failover multi-regione in secondi davanti a load balancer che di per sé sono regionali.

    **Approfondimento completo →** [Elastic Load Balancing](elastic-load-balancing.md)

??? info "Route 53 — failover DNS-based alternativo"
    Route 53 failover routing è l'alternativa più economica quando un RTO di minuti (bound dal TTL del record) è accettabile e non serve un IP statico.

    **Approfondimento completo →** [Route 53](route53.md)

??? info "CloudFront — CDN per contenuti cacheable"
    Per traffico HTTP(S) cacheable, CloudFront riduce latenza e costo tramite cache all'edge; GA non fa caching e serve per protocolli generici o quando serve IP fisso.

    **Approfondimento completo →** [CloudFront](cloudfront.md)

??? info "VPC — endpoint nella rete privata"
    Gli endpoint di GA (ALB, NLB, EC2) vivono nelle subnet della VPC; i security group degli endpoint devono ammettere i range IP di health check di GA.

    **Approfondimento completo →** [VPC](vpc.md)

---

## Riferimenti

- [AWS Global Accelerator — Developer Guide](https://docs.aws.amazon.com/global-accelerator/latest/dg/)
- [Global Accelerator — Endpoint groups e traffic dial](https://docs.aws.amazon.com/global-accelerator/latest/dg/about-endpoint-groups.html)
- [Global Accelerator — Custom routing accelerator](https://docs.aws.amazon.com/global-accelerator/latest/dg/about-custom-routing-accelerators.html)
- [AWS IP ranges (ip-ranges.json)](https://docs.aws.amazon.com/vpc/latest/userguide/aws-ip-ranges.html)
- [Global Accelerator pricing](https://aws.amazon.com/global-accelerator/pricing/)
