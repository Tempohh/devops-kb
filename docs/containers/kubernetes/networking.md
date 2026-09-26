---
title: "Kubernetes Networking"
slug: networking
category: containers
tags: [kubernetes, networking, cni, services, ingress, networkpolicy, coredns, cilium, calico]
search_keywords: [kubernetes networking, CNI container network interface, kubernetes service clusterip, kubernetes nodeport, kubernetes loadbalancer, kubernetes ingress, kubernetes networkpolicy, coredns kubernetes, service discovery kubernetes, kube-proxy, iptables kubernetes, ipvs kubernetes, kubernetes dns, pod network, kubernetes cluster network, kubernetes overlay network, flannel, calico, cilium, weave net, kubernetes ingress controller, nginx ingress, traefik kubernetes, kubernetes egress, kubernetes east-west traffic, kubernetes north-south traffic, kubernetes service mesh intro, kubernetes pod ip, kubernetes service ip, endpoint kubernetes, endpointslice]
parent: containers/kubernetes/_index
related: [containers/kubernetes/architettura, containers/kubernetes/sicurezza, containers/kubernetes/workloads, containers/docker/networking]
official_docs: https://kubernetes.io/docs/concepts/services-networking/
status: needs-review
difficulty: advanced
last_updated: 2026-09-26
---

# Kubernetes Networking

## Panoramica

Kubernetes implementa un modello di rete **flat**: ogni Pod riceve un IP unico e raggiungibile direttamente da qualsiasi altro Pod nel cluster, senza NAT. Questo è il **Kubernetes Network Model** e si contrappone al Docker bridge model dove i container vivono in reti isolate.

Quattro problemi di comunicazione che K8s risolve:
1. **Container → Container** nello stesso Pod: via `localhost` (stesso network namespace)
2. **Pod → Pod**: via IP Pod diretto, senza NAT (responsabilità del CNI plugin)
3. **Pod → Service**: via Virtual IP gestito da `kube-proxy` (iptables/ipvs)
4. **Esterno → Service**: via NodePort, LoadBalancer, o Ingress

!!! warning "IP Pod sono efimeri"
    L'IP di un Pod cambia ad ogni restart. Non comunicare mai direttamente con l'IP di un Pod in produzione — usare sempre un Service come punto di accesso stabile.

---

## CNI — Container Network Interface

Il **CNI** è lo standard che definisce come i plugin di rete configurano il networking dei container. Quando un Pod viene creato, il kubelet chiama il CNI plugin che:
1. Crea un network namespace per il Pod
2. Crea una coppia di virtual ethernet (veth pair): un'estremità nel namespace del Pod, l'altra nel namespace del nodo
3. Assegna un IP al Pod dal CIDR del nodo
4. Configura le route per raggiungere altri Pod e il resto del cluster

### Plugin CNI Comuni

```
CNI Plugin Comparison

  ┌─────────────┬──────────────┬──────────────┬────────────────────────┐
  │ Plugin      │ Data Plane   │ NetworkPolicy│ Note                   │
  ├─────────────┼──────────────┼──────────────┼────────────────────────┤
  │ Calico      │ iptables/BGP │ ✅ nativo    │ Produzione enterprise  │
  │ Cilium      │ eBPF         │ ✅ esteso    │ Osservabilità avanzata │
  │ Flannel     │ VXLAN        │ ❌ no        │ Semplicità, lab/dev    │
  │ Weave Net   │ VXLAN/PCap   │ ✅ nativo    │ Self-healing mesh      │
  │ AWS VPC CNI │ VPC native   │ ✅ via SG    │ Solo AWS EKS           │
  │ Azure CNI   │ VNet native  │ ✅ via NSG   │ Solo AKS               │
  └─────────────┴──────────────┴──────────────┴────────────────────────┘

  Calico/BGP: ogni nodo annuncia le proprie route via BGP → no encapsulation overhead
  Cilium/eBPF: intercetta syscall a livello kernel → massime performance, L7 visibility
  Flannel/VXLAN: encapsula i pacchetti in UDP → overhead ma compatibilità universale
```

### Indirizzi IP nel Cluster

```yaml
# In kubeadm (kubeadm-config.yaml):
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
networking:
  podSubnet: "10.244.0.0/16"      # CIDR totale per i Pod di tutto il cluster
  serviceSubnet: "10.96.0.0/12"   # CIDR per i Service (ClusterIP)
  dnsDomain: "cluster.local"      # dominio DNS interno

# Ogni nodo riceve un /24 dal podSubnet:
# worker-1: 10.244.1.0/24  → Pod su worker-1 hanno IP 10.244.1.x
# worker-2: 10.244.2.0/24  → Pod su worker-2 hanno IP 10.244.2.x
# worker-3: 10.244.3.0/24  → Pod su worker-3 hanno IP 10.244.3.x
```

### kube-proxy — Implementazione dei Service

`kube-proxy` gira su ogni nodo come DaemonSet e mantiene le regole di rete per i Service. Tre modalità:

```bash
# Verifica modalità kube-proxy attiva
kubectl get configmap kube-proxy -n kube-system -o yaml | grep mode

# iptables (default): regole chains per ogni Service
# Pro: stabile, ben conosciuto
# Contro: O(n) regole con molti Service, no load balancing sofisticato

# ipvs: usa Linux IPVS (IP Virtual Server)
# Pro: O(1) lookup, algoritmi LB avanzati (rr, lc, dh, sh, sed, nq)
# Contro: richiede kernel modules aggiuntivi

# Configurare ipvs in kubeadm:
# kubectl edit configmap kube-proxy -n kube-system
# → mode: "ipvs"
# → ipvs.scheduler: "lc"   # least-connections
```

---

## Services — Accesso Stabile ai Pod

Un **Service** è un oggetto Kubernetes che espone un gruppo di Pod tramite un selector label. Fornisce un Virtual IP (ClusterIP) stabile e un nome DNS che non cambia anche quando i Pod vengono ricreati.

### Come funziona davvero un Service (prerequisito per capire tutti i tipi)

Un Service **non è un processo né un proxy**: è solo un oggetto nell'API server + regole di rete programmate su ogni nodo. Tre componenti collaborano:

| Componente | Cosa fa | Dove gira |
|---|---|---|
| **EndpointSlice controller** | Osserva i Pod che matchano il `selector` **e sono Ready** → mantiene la lista `IP:porta` in oggetti `EndpointSlice` | control plane (kube-controller-manager) |
| **kube-proxy** (o Cilium eBPF) | Osserva Service + EndpointSlice via API server → programma regole iptables/IPVS/eBPF | **ogni nodo** |
| **CNI** | Rende ogni IP Pod raggiungibile da ogni nodo (flat network) | ogni nodo |

```
   API server (fonte di verità cluster-wide)
   ├─ Service api        → ClusterIP 10.96.45.123:80
   └─ EndpointSlice api  → 10.244.1.7:8080 (worker-1)
                           10.244.2.9:8080 (worker-2)
                           10.244.3.4:8080 (worker-3)
          │ watch                │ watch                │ watch
          ▼                      ▼                      ▼
     kube-proxy w1          kube-proxy w2          kube-proxy w3
     (regole DNAT)          (regole DNAT)          (regole DNAT)
```

**Conseguenza chiave:** *ogni nodo conosce la posizione di tutti i Pod di tutti i Service*, anche di quelli che non ospita. Per questo un pacchetto diretto al ClusterIP (o a un NodePort) può arrivare su **qualsiasi** nodo: quel nodo fa DNAT verso un IP Pod scelto tra gli endpoint e il CNI lo recapita, anche se il Pod sta su un altro nodo.

!!! note "Il ClusterIP non esiste su nessuna interfaccia"
    `10.96.45.123` non è assegnato a nessuna NIC e non risponde a `ping`. È solo un match nelle regole di kube-proxy: il pacchetto viene riscritto (DNAT) verso un IP Pod prima ancora di uscire dal nodo. Solo le porte dichiarate nel Service funzionano.

```bash
# Chi sono gli endpoint reali dietro un Service? (solo Pod Ready)
kubectl get endpointslices -n production -l kubernetes.io/service-name=api -o wide

# Pod NotReady (readinessProbe fallita) vengono RIMOSSI dagli endpoint → niente traffico
# È il meccanismo che rende sicuri i rolling update: readinessProbe ben fatta = zero downtime
```

### Scegliere il tipo: visione d'insieme

| Tipo | Raggiungibile da | Livello | Caso d'uso enterprise tipico |
|---|---|---|---|
| **ClusterIP** | Solo dentro il cluster | L4 | Comunicazione **east-west** tra microservizi, DB/cache interni, backend dietro Ingress |
| **NodePort** | `IP-nodo:porta` (rete dei nodi) | L4 | Building block per LB esterni **on-prem** (F5, HAProxy); lab/dev. Raramente esposto direttamente in prod |
| **LoadBalancer** | IP/VIP dedicato del LB | L4 | Esporre **un** servizio TCP/UDP non-HTTP (DB, MQTT, gRPC raw, syslog) o l'Ingress controller stesso |
| **ExternalName** | Solo dentro il cluster | DNS | Alias DNS verso servizi fuori cluster (RDS, SaaS, servizio legacy in migrazione) |
| **Headless** (`clusterIP: None`) | Solo dentro il cluster | DNS | StatefulSet, database cluster, client-side load balancing (Kafka, Cassandra) |

!!! tip "Regola pratica enterprise"
    Il 90% dei Service in un cluster è **ClusterIP**. Il traffico HTTP(S) esterno entra da **un solo** LoadBalancer davanti a un Ingress Controller / Gateway API, che poi instrada verso decine di ClusterIP. Un `type: LoadBalancer` per ogni microservizio è quasi sempre un anti-pattern (costo, IP sprecati, nessun punto centrale per WAF/TLS/auth).

### ClusterIP (default)

Espone il Service solo all'interno del cluster, con un IP virtuale stabile e un nome DNS. È il mattone di base: **tutti gli altri tipi lo includono** (NodePort e LoadBalancer creano anche un ClusterIP).

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: production
spec:
  type: ClusterIP           # default, può essere omesso
  selector:
    app: api                # seleziona Pod con questo label
    # NOTA: selector NON supporta operatori avanzati — solo exact match
  ports:
    - name: http
      port: 80              # porta su cui il Service ascolta
      targetPort: 8080      # porta del container (o nome della porta)
      protocol: TCP
    - name: metrics
      port: 9090
      targetPort: metrics   # usa il nome della porta definita nel Pod spec

# Risultato:
# - ClusterIP: 10.96.45.123 (assegnato automaticamente)
# - DNS: api.production.svc.cluster.local → 10.96.45.123
# - Traffico su 10.96.45.123:80 → distribuito ai Pod su porta 8080
```

**Casi d'uso concreti (enterprise):**

- **Microservizi east-west:** `checkout` chiama `http://payments.production.svc:80`. Il chiamante non sa quanti Pod ci sono, dove girano, né quando vengono ricreati (HPA, rolling update, node drain).
- **Backend di un Ingress:** l'Ingress/Gateway non punta ai Pod ma a un ClusterIP; la HTTP routing vive nell'Ingress, la scoperta dei Pod nel Service.
- **Dipendenze infrastrutturali interne:** Redis, Elasticsearch, Vault agent — mai esposte fuori cluster; l'accesso è ulteriormente ristretto con [NetworkPolicy](#networkpolicy-segmentazione-di-rete).
- **Cross-namespace:** `payments.production.svc.cluster.local` da altri namespace; il perimetro di sicurezza si impone con NetworkPolicy, **non** con il Service.

**Opzioni utili in produzione:**

```yaml
spec:
  sessionAffinity: ClientIP          # sticky per IP client (default: None = round-robin/random)
  sessionAffinityConfig:
    clientIP: { timeoutSeconds: 3600 }
  internalTrafficPolicy: Local       # solo endpoint sullo stesso nodo (es. agent DaemonSet: log/metrics locali)
  trafficDistribution: PreferClose   # preferisce endpoint nella stessa zona → meno costi cross-AZ e latenza
```

!!! tip "Costi cross-AZ"
    Nei cloud il traffico tra Availability Zone è a pagamento e aggiunge latenza. `trafficDistribution: PreferClose` (o Topology Aware Routing) mantiene il traffico east-west nella stessa zona quando ci sono endpoint sufficienti.

```bash
# Verifica Service e i suoi Endpoints
kubectl get service api -n production
kubectl get endpointslices -n production         # IP:porta dei Pod selezionati

# Debug: il Service non raggiunge i Pod?
kubectl describe service api -n production       # verifica selector ed Endpoints (vuoti = selector sbagliato o Pod NotReady)
kubectl get pods -n production -l app=api        # i Pod hanno il label corretto?
```

### NodePort

Apre la **stessa porta** (range default 30000-32767) su **tutti i nodi** del cluster; il traffico ricevuto su `IP-qualsiasi-nodo:nodePort` viene inoltrato al Service (e quindi a un Pod).

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
  namespace: production
spec:
  type: NodePort
  selector:
    app: api
  ports:
    - name: http
      port: 80              # ClusterIP port (accesso interno)
      targetPort: 8080      # porta container
      nodePort: 30080       # porta sul nodo (ometti per auto-assign nel range)
      protocol: TCP

# Accesso:
# Interno:  api-nodeport.production.svc.cluster.local:80
# Esterno:  <IP-qualsiasi-nodo>:30080
```

#### Perché su *tutti* i nodi? Chi sceglie il nodo? Come fa a trovare i Pod?

Le tre domande classiche, in ordine:

**1. Come fa il nodo a sapere dove sono i Pod?** Non "sa" niente di speciale: come visto sopra, ogni kube-proxy ha già la lista completa degli endpoint del Service (da EndpointSlice). Quando arriva un pacchetto su `:30080`, la regola locale fa DNAT verso uno degli IP Pod, e il CNI lo instrada — anche verso un altro nodo.

**2. Perché aprirla su tutti i nodi invece che solo dove stanno i Pod?** Perché i Pod si spostano (scheduler, autoscaling, drain, crash). Se la porta fosse aperta solo sui nodi che ospitano Pod, ogni reschedule cambierebbe la superficie di accesso e chi sta davanti dovrebbe inseguirla. Con la porta aperta ovunque, **la lista dei nodi raggiungibili è stabile** e indipendente dalla posizione dei Pod.

**3. Chi chiama dall'esterno: "ogni tanto un nodo, ogni tanto un altro"?** Qui sta il punto: **in produzione il client non sceglie mai il nodo.** Davanti ai nodi c'è un load balancer esterno che ha come backend `worker-1:30080, worker-2:30080, worker-3:30080` e li controlla con health check. Il client conosce solo il VIP/DNS del load balancer.

```
  Client ──► https://api.azienda.it  (DNS → VIP del load balancer)
                     │
              ┌──────▼───────┐   health check TCP :30080 su ogni nodo
              │  F5 / HAProxy │   (nodo down → rimosso dal pool)
              │  / NLB / ALB  │
              └─┬─────┬─────┬─┘
                │     │     │
      worker-1:30080  │  worker-3:30080        ← stessa porta su tutti i nodi
                │  worker-2:30080
                ▼     ▼     ▼
        kube-proxy (regole DNAT, conoscono TUTTI gli endpoint)
                │
                ▼  (può essere un Pod su un ALTRO nodo → hop extra + SNAT)
        Pod 10.244.x.y:8080
```

Senza LB davanti, un client che punta a `worker-1:30080` funziona finché worker-1 è vivo: se cade, il client non fa failover da solo. Per questo NodePort "nudo" è fragile.

#### Quando si usa NodePort (e quando no)

| Scenario | Valutazione |
|---|---|
| **On-prem con LB hardware/software esistente** (F5 BIG-IP, HAProxy, NGINX, Citrix ADC) | ✅ Caso d'uso principale: l'LB aziendale ha i nodi worker come pool member su `:nodePort`. Il team di rete gestisce VIP/TLS/WAF, il team K8s espone il NodePort |
| **Base di un `type: LoadBalancer`** | ✅ Automatico: MetalLB, cloud controller e molti LB provider usano il NodePort come target |
| **Lab, dev, kind/minikube, demo, debug rapido** | ✅ Comodo, nessuna dipendenza esterna |
| **Ingress controller senza LoadBalancer** (bare metal) | ✅ L'Ingress controller viene esposto via NodePort e un LB esterno lo raggiunge |
| **Produzione cloud, servizio HTTP** | ❌ Usare Ingress/Gateway API + LoadBalancer |
| **Esposizione diretta a Internet** | ❌ Apre una porta alta su ogni nodo: superficie d'attacco, gestione firewall/security group per ogni porta |

**Limiti da conoscere:**

- Porte nel range 30000-32767 (non porte "vere" come 443) → serve sempre qualcosa davanti per avere porte standard
- Una porta del range per Service, **globale al cluster** (collisioni, gestione degli assegnamenti)
- I firewall/security group devono aprire il range verso i nodi dall'LB
- Nessun health check applicativo, TLS, routing L7: è puro L4
- Hop extra + SNAT (vedi sotto)

#### externalTrafficPolicy: Cluster vs Local

Il comportamento default (`Cluster`) massimizza la distribuzione ma perde l'IP del client. `Local` preserva l'IP ma cambia il modello.

```
externalTrafficPolicy: Cluster (default)
  LB → worker-1:30080 → kube-proxy sceglie un Pod QUALSIASI del cluster
  ✅ Bilanciamento uniforme tra tutti i Pod    ❌ SNAT: il Pod vede l'IP del nodo, non del client
  ❌ Hop extra tra nodi (latenza, traffico cross-AZ)

externalTrafficPolicy: Local
  LB → worker-1:30080 → SOLO Pod presenti su worker-1
  ✅ IP client originale preservato (whitelisting, audit, rate limit per IP)
  ✅ Nessun hop extra    ❌ Se il nodo non ha Pod → pacchetto scartato
  ❌ Distribuzione sbilanciata se i Pod sono distribuiti in modo non uniforme
```

Con `Local`, chi sta davanti deve sapere **quali nodi hanno Pod**. Con `type: LoadBalancer` Kubernetes alloca un `healthCheckNodePort` su ogni nodo che risponde **200 solo se il nodo ha almeno un endpoint locale Ready**: l'LB lo usa per escludere automaticamente i nodi senza Pod. Con un **NodePort puro** (LB esterno gestito a mano, es. F5) `healthCheckNodePort` non viene allocato: il monitor dell'LB deve sondare la NodePort stessa (un nodo senza Pod locali non risponde → esce dal pool) o direttamente un endpoint di health applicativo.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
spec:
  type: NodePort
  externalTrafficPolicy: Local
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080
```

!!! warning "Local richiede Pod spread"
    Con `Local` usare `topologySpreadConstraints` o `podAntiAffinity` per distribuire le repliche sui nodi: altrimenti un nodo con 3 Pod e uno con 1 ricevono la stessa quota di traffico dal LB, sovraccaricando i Pod del secondo.

### LoadBalancer

Chiede a un **controller esterno al cluster** (cloud controller manager, MetalLB, kube-vip, F5 CIS…) di provisionare un load balancer con un **IP/VIP dedicato**. È di fatto **NodePort + ClusterIP + automazione dell'LB davanti**: lo schema visto nella sezione NodePort (LB esterno → nodi:nodePort) viene creata e mantenuta per te, inclusi health check e aggiornamento del pool quando i nodi cambiano.

```
  Client ─► 34.100.200.50:443 (External IP)
                   │  provisioning automatico da parte del cloud/MetalLB
            ┌──────▼──────┐
            │ Load Balancer│──► nodi :nodePort (NodePort creato automaticamente)
            └─────────────┘          │
                                     ▼ kube-proxy → Pod
  Con AWS LB Controller / GKE NEG / Azure CNI overlay-less:
  LB ──► direttamente IP:porta dei Pod (target-type: ip)  → salta NodePort, niente SNAT, meno hop
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-lb
  namespace: production
  annotations:
    # AWS: personalizza il tipo di LB
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-internal: "true"  # LB interno
    # GCP: static IP pre-allocato
    kubernetes.io/ingress.regional-static-ip-name: "my-static-ip"
    # Azure: internal LB
    service.beta.kubernetes.io/azure-load-balancer-internal: "true"
spec:
  type: LoadBalancer
  externalTrafficPolicy: Local     # preserva IP client; l'LB usa healthCheckNodePort
  selector:
    app: api
  ports:
    - name: http
      port: 80
      targetPort: 8080
    - name: https
      port: 443
      targetPort: 8443
  loadBalancerSourceRanges:
    - "10.0.0.0/8"      # limita accesso al LB a questi CIDR
    - "192.168.0.0/16"

# Stato dopo provisioning:
# kubectl get service api-lb
# NAME    TYPE         CLUSTER-IP     EXTERNAL-IP      PORT(S)
# api-lb  LoadBalancer 10.96.200.100  34.100.200.50    80:30234/TCP, 443:31567/TCP
```

**Casi d'uso concreti (enterprise):**

- **Ingress controller / Gateway:** il caso più comune. **Un** `LoadBalancer` per l'NGINX/Traefik/Envoy Gateway; da lì il routing L7 verso centinaia di ClusterIP. Un solo IP pubblico, un solo punto per WAF, TLS e rate limit.
- **Servizi non-HTTP (TCP/UDP):** database esposti a un'altra VPC/on-prem, broker MQTT, Kafka con listener esterni, syslog, VPN endpoint, game server — protocolli che un Ingress HTTP non gestisce.
- **Load balancer interno (`internal`):** esporre un servizio alla rete corporate/VPC peering/Direct Connect **senza** IP pubblico. In enterprise è la forma di LoadBalancer più usata: API interne condivise tra cluster o tra team.
- **Egress/ingress con IP fisso:** un partner deve mettere in whitelist il tuo IP → static IP pre-allocato assegnato al Service.
- **Multi-cluster / disaster recovery:** ogni cluster espone lo stesso servizio con il proprio LB; il traffico è governato da DNS/GSLB (Route 53, Traffic Manager, F5 GTM).

**On-prem / bare metal — chi fornisce il LoadBalancer?**

Senza cloud provider, `type: LoadBalancer` resta in `<pending>` finché non installi un'implementazione:

| Soluzione | Come annuncia il VIP | Note |
|---|---|---|
| **MetalLB** (L2 mode) | ARP/NDP da un nodo "leader" | Semplice; il traffico entra da **un solo nodo** alla volta (failover, non load balancing) |
| **MetalLB** (BGP mode) | BGP verso i router ToR (ECMP) | Vero bilanciamento tra nodi; richiede router BGP-capable |
| **Cilium LB-IPAM + BGP** | BGP control plane di Cilium | Consigliato se già CNI Cilium; L2/BGP integrati |
| **kube-vip** | ARP o BGP | Usato anche per il VIP del control plane |
| **F5 CIS / NetScaler CIC** | Programma l'appliance esistente | Integra l'infrastruttura di rete enterprise già presente |

**Costi e limiti:**

- Nei cloud **ogni Service LoadBalancer = un LB fatturato** (~16-25 $/mese + traffico) e un IP: 50 microservizi = 50 LB → **usare Ingress/Gateway condiviso**
- Provisioning lento (30-180 s) e con quote per account/regione
- Le annotation sono **provider-specifiche** (non portabili tra AWS/GCP/Azure); preferire `loadBalancerClass` per selezionare l'implementazione esplicitamente
- L4 puro: nessun routing per host/path, nessuna terminazione TLS L7 (salvo annotation cloud specifiche)
- `loadBalancerSourceRanges` è una difesa base; per la sicurezza reale usare security group/NSG + NetworkPolicy

### ExternalName

Non instrada traffico né usa kube-proxy: crea solo un **record DNS CNAME** dentro CoreDNS. Un Pod che risolve `external-db.production.svc` ottiene il CNAME verso l'hostname esterno.

```yaml
# ExternalName: CNAME verso servizio esterno al cluster
apiVersion: v1
kind: Service
metadata:
  name: external-db
  namespace: production
spec:
  type: ExternalName
  externalName: mydb.abc123.eu-west-1.rds.amazonaws.com   # risolve in CNAME, no ClusterIP
```

**Casi d'uso concreti:**

- **Astrarre un database gestito** (RDS, Cloud SQL, Azure SQL): le app usano sempre `external-db`; ambienti diversi (dev/staging/prod) puntano a hostname diversi cambiando **solo** il Service, non la configurazione delle app
- **Migrazione graduale verso Kubernetes:** oggi `payments` è una VM legacy → `ExternalName: payments.legacy.corp`; domani è un Deployment → si sostituisce l'ExternalName con un ClusterIP con **lo stesso nome**. I client non cambiano
- **Servizi SaaS/terzi con dominio stabile** (es. `smtp.provider.com`) con un nome interno uniforme
- **Alias cross-namespace:** `db` in `app-ns` → `postgres.data-ns.svc.cluster.local`

**Limiti:**

- Nessun load balancing, health check o selezione porte: è solo DNS
- Con HTTP/HTTPS l'header `Host` e il certificato TLS del client restano quelli del **nome interno** (`external-db`), non dell'hostname reale → errori di validazione TLS/SNI. Va bene per protocolli TCP dove il nome non compare (PostgreSQL, Redis), problematico per HTTPS
- Non è filtrabile per IP con NetworkPolicy standard (la destinazione reale è nota solo dopo la risoluzione DNS) → per l'egress controllato servono policy FQDN (Cilium) o egress gateway
- Non usare per puntare a un IP: `externalName` deve essere un hostname (usare Service senza selector + EndpointSlice manuale)

### Headless Service

Con `clusterIP: None` non esiste VIP né kube-proxy: il DNS restituisce **direttamente gli IP dei Pod** (record A multipli). Il client sceglie a chi connettersi.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
  namespace: production
spec:
  clusterIP: None          # headless
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432

# DNS headless:
# postgres-headless.production.svc.cluster.local → A records di tutti i Pod Ready
# Con StatefulSet: postgres-0.postgres-headless.production.svc.cluster.local → IP pod-0
```

**Casi d'uso concreti:**

- **Database in cluster con identità stabile (StatefulSet):** in un cluster PostgreSQL/Patroni, MongoDB, Cassandra, Elasticsearch, Kafka, ZooKeeper i nodi devono **indirizzarsi singolarmente** (`kafka-0`, `kafka-1`…) per replica, elezione del leader, bootstrap dei peer. Un ClusterIP che sceglie a caso li renderebbe inutilizzabili
- **Primary/replica:** scrittura su `pg-0.pg-headless`, lettura distribuita sugli altri
- **Client-side load balancing / gRPC:** un client gRPC con round-robin lato client risolve tutti gli IP e bilancia per conto proprio (il L4 di kube-proxy bilancerebbe per *connessione*, e con HTTP/2 long-lived tutto il traffico finirebbe su un solo Pod)
- **Service discovery per sistemi di membership** (Consul, Hazelcast, Akka cluster): la query DNS restituisce l'elenco dei peer

**Limiti:** il client deve gestire failover e refresh DNS (attenzione alla cache DNS della JVM: `networkaddress.cache.ttl`); nessun VIP unico da usare come punto d'ingresso stabile.

### Latenza: da dove vengono i millisecondi (e come sceglierne il percorso)

In enterprise la scelta tra le alternative non si fa "per abitudine" ma sommando i **contributi di latenza** lungo il percorso. Ordini di grandezza tipici (dipendono da provider, regione, carico: **misurare sempre nel proprio ambiente** con `curl -w`, `iperf3`, `tcpdump`):

| Contributo al percorso | Ordine di grandezza | Perché costa |
|---|---|---|
| Hop kube-proxy/DNAT sullo stesso nodo | ~0,01-0,1 ms | Solo riscrittura pacchetto in kernel; trascurabile |
| Hop extra verso un altro nodo, **stessa AZ** | ~0,1-0,5 ms | Un salto di rete in più (NodePort/ClusterIP verso Pod remoto) |
| Hop verso altra AZ, **stessa regione** | ~1-2 ms | Distanza fisica tra datacenter + costo del traffico cross-AZ |
| Load balancer L4 (NLB, F5, MetalLB) | ~0,1-1 ms | Un proxy/NAT in più nel percorso |
| Load balancer L7 / Ingress / WAF | ~1-5 ms (anche più con WAF) | Termina TLS, ispeziona HTTP, apre una seconda connessione verso il backend |
| Handshake TLS nuovo (non riusato) | +1-2 RTT (~2-10 ms+) | Round trip aggiuntivi prima del primo byte applicativo |
| **Rotta pubblica** (Internet, CDN/WAF, NAT gateway, egress) | ~5-50+ ms, **variabile** | Percorso non controllato, più hop/AS, terminazioni multiple, jitter |
| Collegamento privato stessa regione (VPC peering, Transit Gateway, Direct Connect/ExpressRoute) | ~1-5 ms, stabile | Percorso diretto sulla rete del provider/dorsale privata |
| Inter-regione | ~30-150 ms | Limite fisico (velocità della luce in fibra ≈ 1 ms ogni ~100 km andata/ritorno) |

Due punti contano più del valore medio in enterprise:

- **La latenza si moltiplica per le chiamate sequenziali.** Un servizio che fa 20 chiamate seriali a un backend remoto paga 20 × RTT. 2 ms in più diventano 40 ms per richiesta utente; su un flusso di 200 chiamate, 400 ms. Per questo "qualche millisecondo" pesa.
- **Conta la coda (p99), non solo la media.** La rotta pubblica ha jitter e variabilità molto più alti di un collegamento privato: il p99 è spesso peggiore di un ordine di grandezza. Un SLA di latenza si rompe sui percorsi non deterministici.

### Caso: migrazione tra cluster (cluster-to-cluster)

Scenario tipico: si migra un'applicazione da un cluster **vecchio** (A) a uno **nuovo** (B), servizio per servizio. Durante la migrazione (settimane/mesi) i servizi già migrati e quelli ancora su A devono parlarsi. Esempio: `checkout` è già su B, ma chiama ancora `payments` che è su A.

**Il punto non è NodePort in sé, ma il percorso.** La strada "pubblica" (Ingress pubblico di A → Internet → WAF/CDN → Ingress di B) è lenta perché attraversa più terminazioni TLS, WAF, NAT e tratti Internet variabili. La strada "privata" tiene il traffico dentro la rete aziendale/provider: meno hop, nessuna terminazione ripetuta, latenza stabile. NodePort è **uno dei modi** per costruire questa strada privata: si espone il servizio del cluster di destinazione su `IP-nodo:nodePort`, raggiungibile direttamente dalla rete privata (peering/VPN/Direct Connect) con regole firewall/security group dedicate.

```
  Cluster A (vecchio)                                  Cluster B (nuovo)
  ┌───────────────────────┐                            ┌───────────────────────┐
  │ checkout ──► Service  │                            │ Service payments      │
  │            "payments" │     rete PRIVATA           │  (NodePort 30443 /     │
  │  (ExternalName o      │ ─────────────────────────► │   LB interno)          │
  │   Endpoints manuali   │  peering / TGW / VPN /     │        │               │
  │   → IP nodi B:30443)  │  Direct Connect            │        ▼               │
  └───────────────────────┘  (regole SG/firewall       │   Pod payments         │
                              solo su :30443)          └───────────────────────┘

  vs. percorso pubblico:  A → NAT/egress → Internet → CDN/WAF → Ingress pubblico B → Service → Pod
```

**Come si realizza in pratica** (lato cluster chiamante A):

```yaml
# Service SENZA selector + EndpointSlice manuale → nome DNS stabile "payments" dentro A
apiVersion: v1
kind: Service
metadata:
  name: payments
  namespace: production
spec:
  ports:
    - port: 443
      targetPort: 30443        # NodePort del cluster B
---
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: payments-b
  namespace: production
  labels:
    kubernetes.io/service-name: payments
addressType: IPv4
ports:
  - port: 30443
endpoints:
  - addresses: ["10.20.1.11"]   # IP privato worker-1 di B
  - addresses: ["10.20.1.12"]   # worker-2 di B
  - addresses: ["10.20.1.13"]   # worker-3 di B
```

I client in A continuano a chiamare `payments.production.svc`: quando `payments` viene migrato, basta sostituire l'EndpointSlice con un vero selector locale (o il contrario per un rollback). Nessuna modifica alle applicazioni.

**Alternative a confronto (dalla più semplice alla più performante)**

| Alternativa | Percorso / cosa aggiunge | Latenza relativa | Quando è la scelta migliore |
|---|---|---|---|
| **Rotta pubblica** (Ingress pubblico + WAF) | Internet, terminazioni TLS/WAF ripetute, NAT/egress | Alta e **variabile** (jitter, p99 pessimo) | Solo per traffico realmente esterno; **da evitare** per servizi interni tra cluster |
| **NodePort su rete privata** + EndpointSlice manuale | Rete privata → nodo B → (kube-proxy) → Pod. 1 hop extra se il Pod è su un altro nodo; SNAT con `Cluster` | Bassa, stabile | Migrazione **temporanea**, setup rapido, nessun LB da approvare/provisionare; nodi B raggiungibili dalla rete di A |
| **Internal LoadBalancer** (NLB/ILB/MetalLB) su rete privata | VIP stabile → nodi (o Pod con `target-type: ip`) con health check | Bassa (+ ~0,1-1 ms del LB), stabile | Migrazione **lunga o servizio critico**: un VIP unico, failover/health check automatici, nessun elenco di nodi da mantenere |
| **Ingress/Gateway interno** su rete privata | Come sopra + TLS/routing L7 | Media (+1-5 ms L7) | Servizi HTTP con routing per host/path condiviso; overhead L7 accettabile |
| **Service mesh multi-cluster** / **Cilium ClusterMesh** / **Submariner** | Service discovery e routing cross-cluster nativi; mTLS incluso; con rotte Pod CIDR dirette, **Pod-to-Pod senza hop né NAT** | La più bassa (nessun proxy/NodePort intermedio) | Migrazione **lunga** con molti servizi interdipendenti, o architettura **multi-cluster permanente**; richiede CIDR Pod **non sovrapposti** e più lavoro di setup |

**Perché NodePort (o LB interno) e non altro? Il ragionamento.** Il criterio è: *il minimo percorso che rende raggiungibile il servizio, con il minimo lavoro operativo*.

- Se i Pod di B **non** sono raggiungibili dalla rete di A (CIDR overlay non instradati, sovrapposti, o CNI overlay senza esportazione delle route) l'unico indirizzo raggiungibile è quello dei **nodi** → NodePort o LB davanti ai nodi. È il motivo storico per cui NodePort compare nelle migrazioni.
- Se **si riesce** a instradare i Pod CIDR tra i cluster (CNI VPC-native come AWS VPC CNI/Azure CNI, oppure BGP/ClusterMesh), si può parlare direttamente ai Pod: **si elimina l'hop NodePort e l'SNAT**, e si guadagna anche l'IP sorgente originale.
- Se la migrazione è breve e tocca pochi servizi → NodePort (meno pezzi da gestire). Se è lunga o critica → LB interno o mesh: il costo di setup si ripaga in stabilità e osservabilità.

**Come ridurre ulteriormente i millisecondi con NodePort:**

- `externalTrafficPolicy: Local` sul Service di B, con il monitor che sonda solo i nodi che ospitano Pod → **niente hop tra nodi e niente SNAT** (e si preserva l'IP del chiamante per audit/whitelist). Richiede Pod distribuiti sui nodi
- Elencare nei nodi dell'EndpointSlice **solo i nodi della stessa AZ del chiamante** (o dare priorità ad essi) per evitare il salto cross-AZ (~1-2 ms in più, più traffico fatturato)
- **Riusare le connessioni** (keep-alive, HTTP/2, connection pool): il costo dell'handshake TCP+TLS si paga una volta, non a ogni richiesta
- Mantenere il TLS **end-to-end** (o mTLS) sul canale privato: non serve una terminazione intermedia, e i dati non viaggiano in chiaro anche se la rete è privata

!!! warning "Rischi da gestire (la rotta privata non è gratis)"
    - **Sicurezza:** una NodePort aperta su tutti i nodi di B amplia la superficie. Limitare con security group/firewall **alla sola sorgente** (IP/CIDR dei nodi di A e solo sulla porta specifica) + NetworkPolicy + mTLS
    - **Elenco nodi manuale = debito tecnico:** se i nodi di B cambiano (scale, upgrade, sostituzioni) l'EndpointSlice manuale va aggiornato → automatizzare (controller/script/Terraform) oppure passare a un LB interno che segue i nodi da solo
    - **Failover:** un client che usa un elenco statico di nodi senza health check perde richieste quando un nodo cade → sempre health check o LB davanti
    - **Provvisorio:** documentare e schedulare la rimozione a fine migrazione, altrimenti diventa dipendenza permanente non tracciata
    - **CIDR sovrapposti:** se i due cluster usano la stessa rete Pod/Service, il routing diretto è impossibile (NodePort/LB restano l'unica strada), ma va pianificato prima: rinumerare dopo è molto costoso

### Ragionamento per caso d'uso: perché *questa* scelta

| Caso d'uso | Scelta migliore | Perché (in termini di percorso e latenza) | Alternativa peggiore e motivo |
|---|---|---|---|
| Microservizi nello stesso cluster | **ClusterIP** (+ `trafficDistribution: PreferClose`) | DNAT locale (~0,01-0,1 ms); `PreferClose` evita il salto cross-AZ (~1-2 ms × ogni chiamata) | Passare da Ingress/LB per traffico interno: aggiunge proxy L7 (~1-5 ms) e costi senza alcun beneficio |
| Agent locale (log, metrics) su ogni nodo | **ClusterIP con `internalTrafficPolicy: Local`** | Il traffico resta sul nodo: zero rete fisica | ClusterIP standard: il pacchetto può finire su un altro nodo |
| API HTTP pubbliche | **1 LB L4 → Ingress/Gateway → ClusterIP** | I ms del L7 (TLS, WAF) si pagano **una volta sola** al bordo, non a ogni microservizio | 1 LB per servizio: stessa latenza ma costi e IP moltiplicati |
| Preservare IP client con latenza minima | **`externalTrafficPolicy: Local`** + Pod spread | Nessun hop tra nodi, nessun SNAT | `Cluster`: +0,1-0,5 ms (stessa AZ) o +1-2 ms (cross-AZ) e IP perso |
| Servizio TCP non-HTTP (DB, MQTT) | **LoadBalancer L4** (interno se possibile) | Nessun parsing L7: overhead minimo (~0,1-1 ms) | Ingress HTTP: non gestisce il protocollo |
| Bare metal, alta banda | **MetalLB BGP (ECMP)** | Il traffico entra da tutti i nodi con hash sui router: niente collo di bottiglia su un nodo | MetalLB L2: un solo nodo riceve tutto (limite di banda + failover più lento) |
| Cluster A ↔ B, migrazione **breve**, pochi servizi | **NodePort su rete privata** | Una sola rete privata (~1-5 ms stabili), zero componenti da provisionare | Rotta pubblica: 5-50+ ms variabili, WAF/TLS ripetuti |
| Cluster A ↔ B, migrazione **lunga/critica** | **Internal LB** oppure **Cilium ClusterMesh/Submariner** | VIP + health check (LB) o Pod-to-Pod diretto (mesh): niente elenco nodi manuale | NodePort con nodi a mano: rischio operativo che cresce col tempo |
| Client gRPC/HTTP2 long-lived | **Headless** + LB lato client (o mesh) | kube-proxy bilancia per **connessione**: una connessione HTTP/2 resta su un solo Pod, quindi sbilanciamento e latenze di coda; il client-side LB distribuisce per **richiesta** | ClusterIP: p99 peggiore per Pod sovraccarico |

!!! tip "Come decidere: procedura in 3 domande"
    1. **Chi è il chiamante?** Stesso cluster → ClusterIP. Altro cluster → percorso privato. Esterno → LB + Ingress.
    2. **Quanti ms posso spendere e quante chiamate sequenziali faccio?** Somma i contributi della tabella sopra: se il budget è stretto, elimina prima i salti cross-AZ e i proxy L7 non necessari.
    3. **Quanto dura e quanto è critico?** Temporaneo → soluzione semplice (NodePort). Permanente/critico → soluzione con health check e failover (LB interno, mesh).

### Pattern enterprise: come si combinano

```
  Internet / rete corporate
        │
  [ CDN / WAF / DDoS protection ]                 ← perimetro (Cloudflare, AWS WAF, Akamai)
        │
  [ LoadBalancer L4 (1 solo) ]  ──► NLB/F5/MetalLB, IP fisso, whitelist
        │        (NodePort automatico o target-type: ip)
  [ Ingress Controller / Gateway API ]            ← TLS, routing host/path, auth, rate limit
        │
   ┌────┼────────────┬──────────────┐
   ▼    ▼            ▼              ▼
 svc-A  svc-B      svc-C          svc-D           ← ClusterIP (east-west, stabili)
 (web)  (api)    (payments)     (search)
                     │
                     ├─► ExternalName → RDS.eu-west-1...        ← DB gestito
                     └─► Headless   → kafka-0/1/2 (StatefulSet) ← broker con identità
```

| Esigenza | Soluzione consigliata |
|---|---|
| API HTTP(S) pubbliche multi-servizio | 1 LoadBalancer → Ingress/Gateway → ClusterIP |
| API HTTP interne (solo rete corporate) | LoadBalancer **internal** → Ingress/Gateway interno |
| Servizio TCP/UDP non-HTTP (DB, MQTT, syslog) | LoadBalancer dedicato (interno se possibile) |
| Bare metal con F5/HAProxy aziendale | NodePort + pool member `nodi:nodePort` (con `Local`: monitor sulla NodePort) |
| Bare metal senza LB | MetalLB / Cilium LB-IPAM (BGP) + LoadBalancer |
| Preservare IP client (audit, whitelist) | `externalTrafficPolicy: Local` **oppure** PROXY protocol / header `X-Forwarded-For` sul LB L7 |
| Database su StatefulSet | Headless + eventuale ClusterIP separato per i client applicativi |
| DB gestito cloud / servizio legacy | ExternalName |
| Ridurre costi cross-AZ | `trafficDistribution: PreferClose` + Pod spread per zona |

!!! warning "Anti-pattern comuni"
    - **Un LoadBalancer per ogni microservizio:** costo e sprawl di IP → Ingress/Gateway condiviso
    - **NodePort esposto direttamente a Internet:** porte alte aperte su tutti i nodi, nessun WAF/TLS
    - **Client che puntano a un singolo nodo:NodePort:** nessun failover; sempre un LB con health check davanti
    - **`externalTrafficPolicy: Local` senza spread dei Pod:** distribuzione sbilanciata e nodi scartati
    - **Comunicare con IP Pod o ClusterIP hard-coded:** usare sempre il nome DNS del Service
    - **Selector troppo largo o duplicato:** Service che cattura Pod di altri workload → verificare sempre gli endpoint

---

## DNS Interno — CoreDNS

**CoreDNS** è il server DNS del cluster, deployato come Deployment in `kube-system`. Risponde alle query DNS dai Pod e risolve i nomi dei Service.

### Schema di Risoluzione DNS

```
DNS Record Format per un Service:
  <service-name>.<namespace>.svc.<cluster-domain>

Esempi (cluster.local è il dominio di default):

  Service "api" in namespace "production":
  → api.production.svc.cluster.local     (FQDN completo)
  → api.production.svc                    (abbreviato se stesso cluster-domain)
  → api.production                        (da Pod nello stesso cluster)
  → api                                   (da Pod nello stesso namespace)

  Pod "api-abc123" in namespace "production" con IP 10.244.1.5:
  → 10-244-1-5.production.pod.cluster.local   (A record pod — raro, usare Service)

  StatefulSet "postgres" headless in "production":
  → postgres-0.postgres-headless.production.svc.cluster.local
  → postgres-1.postgres-headless.production.svc.cluster.local
```

```yaml
# ConfigMap CoreDNS — personalizzazioni
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
           lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
           ttl 30
        }
        prometheus :9153        # metriche CoreDNS
        forward . /etc/resolv.conf {   # forward query esterne al DNS del nodo
           max_concurrent 1000
        }
        cache 30                # cache TTL in secondi
        loop
        reload
        loadbalance
    }

    # Stub zone: forward query per dominio specifico a DNS dedicato
    # Utile per: risolvere hostname on-premise da cluster cloud
    internal.company.com:53 {
        forward . 10.0.0.53
    }
```

```bash
# Debug DNS — da un Pod di test
kubectl run dns-debug --image=busybox:1.36 --rm -it -- sh

# Dentro il Pod:
nslookup api.production.svc.cluster.local     # risolve il Service
nslookup kubernetes.default.svc.cluster.local  # API server
cat /etc/resolv.conf                            # verifica search domains

# Da fuori (kubectl exec)
kubectl exec -n production deploy/api -- nslookup postgres-headless

# Verifica CoreDNS è healthy
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50

# Aumenta log level CoreDNS per debug
# kubectl edit configmap coredns -n kube-system
# Aggiungere: log (plugin di logging)
```

---

## Ingress — Routing HTTP/HTTPS

Un **Ingress** è una risorsa Kubernetes che definisce regole di routing per traffico HTTP/HTTPS in ingresso. Richiede un **Ingress Controller** deployato nel cluster (nginx, Traefik, HAProxy, AWS ALB, GCE, ecc.).

!!! warning "Ingress richiede un Controller"
    La risorsa Ingress da sola non fa nulla. Deve esserci un Ingress Controller in esecuzione nel cluster che legge le risorse Ingress e configura il proxy/LB sottostante.

### Ingress Controller — Installazione

```bash
# NGINX Ingress Controller (opzione più comune)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.nodeSelector."kubernetes\.io/os"=linux \
  --set controller.admissionWebhooks.patch.nodeSelector."kubernetes\.io/os"=linux

# Verifica
kubectl get pods -n ingress-nginx
kubectl get service -n ingress-nginx   # External IP del controller
```

### Regole Ingress

```yaml
# Ingress con host-based e path-based routing
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: "nginx"
    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "100"
    # Redirect HTTP → HTTPS
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    # Timeout
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "10"
    # Rewrite path: /api/v1/users → /users
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx    # alternativa all'annotation (K8s 1.18+)

  # TLS
  tls:
    - hosts:
        - api.company.com
        - app.company.com
      secretName: company-tls-cert   # Secret tipo kubernetes.io/tls

  rules:
    # Host-based routing
    - host: api.company.com
      http:
        paths:
          - path: /v1(/|$)(.*)       # regex path (con rewrite-target: /$2)
            pathType: Prefix
            backend:
              service:
                name: api-v1
                port:
                  number: 80
          - path: /v2(/|$)(.*)
            pathType: Prefix
            backend:
              service:
                name: api-v2
                port:
                  number: 80

    - host: app.company.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80

    # Wildcard host
    - host: "*.company.com"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: default-backend
                port:
                  number: 80
```

```yaml
# IngressClass — definisce il controller responsabile
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"  # default se non specificato
spec:
  controller: k8s.io/ingress-nginx

---
# TLS Secret (cert-manager lo crea automaticamente)
apiVersion: v1
kind: Secret
metadata:
  name: company-tls-cert
  namespace: production
type: kubernetes.io/tls
data:
  tls.crt: <base64-encoded-cert>    # cat cert.pem | base64 -w0
  tls.key: <base64-encoded-key>     # cat key.pem | base64 -w0
```

!!! tip "cert-manager per TLS automatico"
    Usa `cert-manager` con Let's Encrypt per gestire automaticamente i certificati TLS. Aggiunge l'annotation `cert-manager.io/cluster-issuer: letsencrypt-prod` all'Ingress e crea/rinnova i Secret TLS automaticamente.

---

## NetworkPolicy — Segmentazione di Rete

Per default, tutti i Pod in un cluster Kubernetes possono comunicare liberamente tra loro. Le **NetworkPolicy** implementano microsegmentazione: definiscono whitelist di traffico ingress/egress per gruppi di Pod.

!!! warning "Il CNI deve supportare NetworkPolicy"
    Flannel non implementa NetworkPolicy. Serve Calico, Cilium, Weave Net, o un cloud CNI con supporto. Creare una NetworkPolicy su un cluster con CNI non supportato non avrà effetto silenziosamente.

### Default Deny — Pattern Fondamentale

```yaml
# Default deny-all ingress per il namespace production
# BEST PRACTICE: applicare in ogni namespace e poi aprire solo il necessario
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}          # {} = seleziona TUTTI i Pod del namespace
  policyTypes:
    - Ingress              # applica solo a ingress (lascia egress libero)
  # ingress: []            # implicito: nessuna regola = nessun ingress permesso

---
# Default deny-all (ingress + egress)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  # Nessun ingress né egress permesso — isola completamente il namespace
```

### Regole Ingress/Egress

```yaml
# NetworkPolicy completa per un'app API
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-networkpolicy
  namespace: production
spec:
  # Applica a: Pod con label app=api
  podSelector:
    matchLabels:
      app: api

  policyTypes:
    - Ingress
    - Egress

  ingress:
    # Regola 1: permetti traffico dall'Ingress Controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
          podSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080

    # Regola 2: permetti traffic da altri Pod nella stessa namespace con label tier=frontend
    - from:
        - podSelector:
            matchLabels:
              tier: frontend
      ports:
        - protocol: TCP
          port: 8080

    # Regola 3: permetti monitoring dal namespace monitoring
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
      ports:
        - protocol: TCP
          port: 9090   # metrics endpoint

  egress:
    # Permetti accesso al database
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432

    # Permetti DNS (CRITICO: senza questo il Pod non risolve nomi)
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53

    # Permetti traffico HTTPS verso Internet (es. API esterne)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8       # escludi rete interna
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443
```

```yaml
# NetworkPolicy con ipBlock — per servizi on-premise o range IP specifici
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-datacenter
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: legacy-connector
  policyTypes:
    - Ingress
  ingress:
    - from:
        - ipBlock:
            cidr: 10.10.0.0/16        # range datacenter on-premise
            except:
              - 10.10.50.0/24         # escludi subnet non autorizzata
      ports:
        - protocol: TCP
          port: 8443
```

!!! tip "Combinazione di selettori in NetworkPolicy"
    All'interno di un elemento `from`/`to`, i campi `namespaceSelector` e `podSelector` sono in AND logico (entrambi devono essere soddisfatti). Elementi separati nella lista sono in OR. Questa distinzione è critica per scrivere policy corrette.

---

## Best Practices

**Services:**
- Usare sempre i nomi delle porte nel `targetPort` invece dei numeri — disaccoppia Service dal Pod
- Definire `readinessProbe` nei Pod per evitare traffico verso Pod non pronti
- Usare `ClusterIP` per servizi interni, `Ingress` per HTTP/HTTPS esterno, `LoadBalancer` solo per TCP/UDP non-HTTP
- Non esporre servizi di infrastruttura (DB, cache) con NodePort/LoadBalancer

**DNS:**
- Usare nomi FQDN nelle configurazioni cross-namespace per evitare ambiguità
- Configurare stub zone CoreDNS per risolvere hostname interni aziendali
- Monitorare le metriche CoreDNS (latenza DNS alta causa problemi a cascata)

**NetworkPolicy:**
- Adottare sempre il pattern default-deny per namespace di produzione
- Ricordare di includere sempre la regola egress per DNS (porta 53 UDP/TCP)
- Etichettare i namespace con `kubernetes.io/metadata.name` per policy cross-namespace
- Testare le policy in staging prima di applicare in produzione

**Ingress:**
- Usare un Ingress Controller dedicato per produzione (non lo stesso del dev)
- Configurare `cert-manager` per TLS automatico
- Definire `resource limits` per l'Ingress Controller (può diventare collo di bottiglia)
- Usare `externalTrafficPolicy: Local` su LoadBalancer Service per Ingress se serve IP client reale

---

## Troubleshooting

### Scenario 1: Pod non raggiunge Service interno

**Sintomo:** `curl http://api.production.svc.cluster.local` timeout o NXDOMAIN da un Pod.

**Causa possibile A — DNS non funziona:**
```bash
# Test DNS dall'interno del Pod
kubectl exec -n staging deploy/my-app -- nslookup api.production.svc.cluster.local
kubectl exec -n staging deploy/my-app -- cat /etc/resolv.conf

# Verifica CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system deployment/coredns --tail=100

# Se CoreDNS è crashato, riavvialo
kubectl rollout restart deployment/coredns -n kube-system
```

**Causa possibile B — Nessun Endpoint:**
```bash
# Il Service seleziona Pod inesistenti o non Ready
kubectl get endpoints api -n production
# Se "Endpoints: <none>" → i label del selector non matchano nessun Pod

kubectl get pods -n production -l app=api --show-labels   # verifica i label
kubectl describe service api -n production                 # verifica il selector
```

**Causa possibile C — NetworkPolicy blocca il traffico:**
```bash
# Elenca NetworkPolicy nel namespace target
kubectl get networkpolicy -n production
kubectl describe networkpolicy -n production

# Test senza NetworkPolicy (solo debug, mai in prod)
kubectl label namespace production network-policy-exempt=true  # non ha effetto diretto
# → usa un Pod privilegiato per tracciare il traffico
```

---

### Scenario 2: Ingress ritorna 404 o 502

**Sintomo:** Browser riceve 404 Not Found o 502 Bad Gateway su un host configurato nell'Ingress.

```bash
# 404 — Ingress Controller non trova regola
kubectl get ingress -n production                           # esiste l'Ingress?
kubectl describe ingress app-ingress -n production          # regole corrette?

# Verifica IngressClass
kubectl get ingressclass                                    # esiste la class?
kubectl get ingress app-ingress -n production -o jsonpath='{.spec.ingressClassName}'

# 502 — Ingress Controller raggiunge il Service ma il Pod non risponde
kubectl get endpoints api -n production                     # endpoints presenti?
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=100

# Test diretto al Service bypassando Ingress
kubectl port-forward service/api 8080:80 -n production
curl http://localhost:8080/healthz
```

---

### Scenario 3: NetworkPolicy blocca traffico legittimo

**Sintomo:** Dopo aver applicato una NetworkPolicy, un servizio smette di funzionare.

```bash
# Identifica quale policy sta bloccando
kubectl get networkpolicy -n production -o yaml | grep -A 20 "podSelector"

# Strumento di verifica Calico (se CNI è Calico)
kubectl exec -n kube-system ds/calico-node -- calicoctl get networkpolicy -o wide

# Strumento Cilium (se CNI è Cilium)
kubectl exec -n kube-system ds/cilium -- cilium policy trace \
  --src-pod production/api-xxx --dst-pod production/postgres-yyy --dport 5432

# Errore comune: dimenticato il permesso DNS egress
# Aggiungi immediatamente se i Pod non risolvono nomi dopo default-deny:
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: production
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
EOF
```

---

### Scenario 4: Service LoadBalancer bloccato in `<pending>` External IP

**Sintomo:** `kubectl get service` mostra `EXTERNAL-IP: <pending>` da molto tempo.

```bash
# Verifica eventi del Service
kubectl describe service api-lb -n production
# Cercare eventi tipo: "Error creating load balancer" o "Timeout"

# Su cluster bare metal — serve MetalLB o simile
# Senza un cloud provider o MetalLB, LoadBalancer non può ottenere un IP
kubectl get pods -n metallb-system    # MetalLB installato?

# Su EKS — verifica permessi IAM
# Il node IAM role deve avere permessi EC2 per creare ELB
aws iam get-role-policy --role-name <NodeInstanceRole> --policy-name <policy>

# Workaround temporaneo: usa NodePort invece di LoadBalancer
kubectl patch service api-lb -n production -p '{"spec": {"type": "NodePort"}}'

# Alternativa: usa Ingress + ClusterIP per traffico HTTP/HTTPS
# → più efficiente, un solo LB per tutto il cluster
```

---

## Relazioni

??? info "Architettura Kubernetes — Approfondimento"
    Il networking si integra con i componenti del control plane: API server usa il cluster network, `kube-proxy` legge gli oggetti Service via API server, etcd conserva lo stato di tutti i Service e NetworkPolicy.

    **Approfondimento completo →** [Architettura Kubernetes](architettura.md)

??? info "Sicurezza Kubernetes — RBAC e Pod Security"
    NetworkPolicy è il layer 3/4 della sicurezza di rete. Per il layer applicativo (authn/authz, mutual TLS tra Pod) serve un service mesh (Istio, Linkerd) o mTLS nativo via cert-manager.

    **Approfondimento completo →** [Sicurezza Kubernetes](sicurezza.md)

??? info "Workloads — StatefulSet e Headless Service"
    I Headless Service sono fondamentali per i StatefulSet: permettono DNS stabile per ogni replica (postgres-0, postgres-1, …).

    **Approfondimento completo →** [Kubernetes Workloads](workloads.md)

---

## Riferimenti

- [Kubernetes Networking Model](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [DNS per Service e Pod](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [CoreDNS](https://coredns.io/plugins/kubernetes/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [Cilium NetworkPolicy](https://docs.cilium.io/en/stable/security/policy/)
- [Calico NetworkPolicy](https://docs.tigera.io/calico/latest/network-policy/)
