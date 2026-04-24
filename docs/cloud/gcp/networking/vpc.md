---
title: "GCP Networking: VPC, Cloud NAT, Firewall e Load Balancing"
slug: vpc
category: cloud/gcp/networking
tags: [gcp, vpc, networking, cloud-nat, firewall, load-balancing, shared-vpc, private-google-access, psc, neg]
search_keywords: [GCP VPC, Virtual Private Cloud GCP, VPC globale Google, subnet GCP, Shared VPC, VPC Peering GCP, Custom mode VPC, Auto mode VPC, Cloud NAT, Private Google Access, PSC, Private Service Connect, firewall GCP, firewall distribuito GCP, firewall rules GCP, firewall policy, Cloud Load Balancing, Application Load Balancer GCP, Network Load Balancer GCP, Internal Load Balancer GCP, NEG, Network Endpoint Group, VPC Flow Logs, Connectivity Tests, gcloud compute networks, gcloud compute firewall-rules, gcloud compute routers, Cloud Router, Cloud NAT setup, Backend Service, Health Check, URL Map, GKE ingress GCP, GCE ingress, Cloud Armor, RFC 1918, CIDR GCP, subnetting GCP, rete GCP, networking GCP fondamentali]
parent: cloud/gcp/networking/_index
related: [networking/fondamentali/indirizzi-ip-subnetting, networking/load-balancing/layer4-vs-layer7, networking/sicurezza/firewall-waf, cloud/gcp/containers/gke, networking/fondamentali/nat]
official_docs: https://cloud.google.com/vpc/docs
status: complete
difficulty: intermediate
last_updated: 2026-03-30
---

# GCP Networking: VPC, Cloud NAT, Firewall e Load Balancing

## Panoramica

La rete su GCP si basa su un modello fondamentalmente diverso da AWS e Azure: il **VPC è una risorsa globale**, non regionale. Questo significa che un singolo VPC attraversa tutte le regioni del mondo, mentre le subnet sono regionali. Questa architettura semplifica il routing interno (non serve il peering tra VPC regionali) e abilita scenari multi-regione con configurazione minima.

**Componenti fondamentali del networking GCP:**

- **VPC (Virtual Private Cloud)** — rete isolata, globale, che contiene subnet regionali
- **Cloud NAT** — outbound internet per VM prive di IP pubblico, gestito a livello di Cloud Router
- **Private Google Access / PSC** — accesso privato a API Google e servizi managed senza IP pubblico
- **Firewall Rules / Firewall Policy** — controllo traffico distribuito, applicato a livello di VM non di perimetro
- **Cloud Load Balancing** — bilanciamento globale (o regionale) per HTTP/S, TCP/UDP, interno

**Quando usare questo argomento:**
- Progettazione della rete per un nuovo progetto GCP
- Configurazione di VM o GKE cluster senza IP pubblico
- Troubleshooting di connettività tra risorse GCP
- Scelta del tipo di load balancer per un'applicazione

---

## VPC su GCP — Differenze da AWS e Azure

### Architettura Globale

La differenza più importante rispetto ad AWS: in GCP il **VPC è globale**. Una VM in `us-central1` e una in `europe-west1` nello stesso VPC comunicano direttamente via IP privato, senza transit gateway, VPC peering interno o route speciali.

```
GCP VPC (globale)
├── subnet us-central1   (10.0.0.0/20)  → VM, GKE nodes
├── subnet europe-west1  (10.1.0.0/20)  → VM, Cloud SQL
├── subnet asia-east1    (10.2.0.0/20)  → VM
└── [comunicazione diretta tra subnet via backbone Google]

AWS VPC (regionale — confronto)
├── VPC us-east-1        (10.0.0.0/16)
│   ├── subnet us-east-1a  (10.0.1.0/24)
│   └── subnet us-east-1b  (10.0.2.0/24)
└── VPC eu-west-1        (10.1.0.0/16)
    └── [serve VPC Peering o Transit Gateway per comunicare]
```

### Auto Mode vs Custom Mode

| Caratteristica | Auto Mode | Custom Mode |
|---|---|---|
| Subnet pre-create | Sì, una per regione automaticamente | No, definite manualmente |
| Range CIDR | Fisso (10.128.0.0/9 suddiviso) | Libero (RFC 1918) |
| Uso consigliato | PoC, test, ambienti temporanei | **Produzione — sempre** |
| Espandibilità | Limitata (range predefiniti) | Totale controllo |
| Rischio overlap | Alto in ambienti multi-VPC | Nessuno se pianificato |

!!! warning "Custom Mode in produzione"
    Usare sempre **Custom Mode** in produzione. Auto Mode crea subnet con range CIDR fissi in tutte le regioni, rendendo impossibile personalizzare l'addressing e causando problemi di overlap quando si aggiungono VPC Peering o connessioni on-premises. Una volta creato un VPC in Auto Mode non è convertibile in Custom Mode — serve ricreare la rete.

```bash
# Creare VPC in Custom Mode
gcloud compute networks create my-vpc \
  --subnet-mode=custom \
  --bgp-routing-mode=regional \
  --description="VPC produzione"

# Creare subnet regionale
gcloud compute networks subnets create subnet-prod-europe \
  --network=my-vpc \
  --region=europe-west1 \
  --range=10.10.0.0/20 \
  --enable-private-ip-google-access \
  --enable-flow-logs \
  --logging-aggregation-interval=interval-5-sec \
  --logging-flow-sampling=0.5

# Creare subnet con secondary ranges (necessario per GKE VPC-native)
gcloud compute networks subnets create subnet-gke-europe \
  --network=my-vpc \
  --region=europe-west1 \
  --range=10.20.0.0/20 \
  --secondary-range pods=10.100.0.0/16,services=10.200.0.0/22
```

### Shared VPC

Shared VPC permette di centralizzare la gestione della rete in un **host project** e di condividerla con **service project** multipli. Equivale concettualmente ad AWS RAM (Resource Access Manager) per VPC sharing.

```
Host Project (network team)
├── VPC produzione
│   ├── subnet-backend  (10.10.0.0/20)
│   └── subnet-data     (10.20.0.0/20)
└── [condivide subnet a Service Project]

Service Project A (team applicativo)
└── VM, GKE cluster → usano subnet-backend del Host Project

Service Project B (team dati)
└── Cloud SQL, Dataflow → usano subnet-data del Host Project
```

**Shared VPC vs VPC Peering:**

| Aspetto | Shared VPC | VPC Peering |
|---|---|---|
| Centralizzazione | Unico VPC, risorse in progetti diversi | Due VPC separati collegati |
| Gestione firewall | Centralizzata nel host project | Separata per ogni VPC |
| Limite | Max 100 service project per host | Peering non transitivo |
| Uso ideale | Organizzazioni con team separati | Connessione a terze parti / SaaS |
| Route | Un solo routing table | Route esplicite tra VPC |

!!! tip "Shared VPC per ambienti enterprise"
    In organizzazioni con più team, Shared VPC è il pattern consigliato. Il team di networking gestisce il VPC nel host project; i team applicativi ottengono accesso alle subnet necessarie senza poter modificare la topologia di rete. Richiede `roles/compute.networkUser` nel service project per usare subnet condivise.

```bash
# Abilitare Shared VPC su un host project
gcloud compute shared-vpc enable HOST_PROJECT_ID

# Associare un service project
gcloud compute shared-vpc associated-projects add SERVICE_PROJECT_ID \
  --host-project=HOST_PROJECT_ID

# Concedere accesso a subnet specifica (non all'intero VPC)
gcloud compute networks subnets add-iam-policy-binding subnet-backend \
  --region=europe-west1 \
  --project=HOST_PROJECT_ID \
  --role=roles/compute.networkUser \
  --member=serviceAccount:SA_SERVICE_PROJECT@developer.gserviceaccount.com
```

---

## Private Google Access e Cloud NAT

### Private Google Access

Private Google Access consente a VM **prive di IP pubblico** di raggiungere le API Google (Storage, BigQuery, Pub/Sub, ecc.) tramite la rete interna di Google, senza uscire su internet.

```
VM (solo IP privato)
  ↓ richiesta a storage.googleapis.com
  ↓ Private Google Access abilitato sulla subnet
  ↓ traffico rimane sulla rete Google (no internet)
  → Cloud Storage risponde

Senza Private Google Access:
VM (solo IP privato) → ✗ nessun accesso alle API Google
```

Si abilita a livello di subnet con il flag `--enable-private-ip-google-access` (mostrato sopra) oppure via Console. Non richiede configurazione aggiuntiva sulle VM.

### Cloud NAT

Cloud NAT fornisce connettività **outbound verso internet** per VM senza IP pubblico. È un NAT managed, scalabile automaticamente, che non introduce un singolo punto di failure (non è una VM NAT).

```
VM (10.10.0.5, no IP pubblico)
  ↓
Cloud Router (europe-west1)
  ↓
Cloud NAT (IP pubblico NAT pool: 34.90.x.x)
  ↓
Internet (server esterno vede IP NAT, non IP privato VM)
```

```bash
# Step 1: creare Cloud Router (prerequisito per Cloud NAT)
gcloud compute routers create router-europe-west1 \
  --network=my-vpc \
  --region=europe-west1

# Step 2: creare Cloud NAT
gcloud compute routers nats create nat-europe-west1 \
  --router=router-europe-west1 \
  --region=europe-west1 \
  --nat-all-subnet-ip-ranges \
  --auto-allocate-nat-external-ips \
  --enable-logging

# Verifica stato NAT
gcloud compute routers get-status router-europe-west1 \
  --region=europe-west1

# Cloud NAT con IP statico (per whitelist IP su sistemi esterni)
gcloud compute addresses create nat-ip-static \
  --region=europe-west1

gcloud compute routers nats create nat-static-ip \
  --router=router-europe-west1 \
  --region=europe-west1 \
  --nat-all-subnet-ip-ranges \
  --nat-external-ip-pool=nat-ip-static \
  --enable-logging
```

!!! tip "Log Cloud NAT per troubleshooting"
    Abilitare i log NAT (`--enable-logging`) è essenziale per il debug. I log vengono scritti in Cloud Logging e mostrano ogni connessione NAT con IP sorgente, destinazione, porta, e tipo di operazione (ALLOCATED/DROPPED). Utile quando si investigano connessioni rifiutate da sistemi esterni o esaurimento porte NAT.

### Private Service Connect (PSC)

PSC è l'evoluzione di VPC Peering per accedere a **servizi GCP managed** (Cloud SQL, Memorystore, Vertex AI, ecc.) e a **servizi di terze parti** tramite endpoint IP privato nel proprio VPC.

```
VPC aziendale (10.10.0.0/16)
├── subnet-app (10.10.1.0/24)
│   └── VM applicativa
└── PSC Endpoint (10.10.99.5) ←── mappa a Cloud SQL managed
    |
    [rete Google interna — no IP pubblico, no internet]
    |
    Cloud SQL (progetto Google-managed)
```

```bash
# Creare endpoint PSC per Cloud SQL
gcloud compute addresses create psc-sql-endpoint \
  --region=europe-west1 \
  --subnet=subnet-app \
  --purpose=GCE_ENDPOINT

gcloud compute forwarding-rules create psc-cloudsql \
  --region=europe-west1 \
  --network=my-vpc \
  --address=psc-sql-endpoint \
  --target-service-attachment=SERVICE_ATTACHMENT_URI
```

---

## Firewall Rules

### Modello Distribuito GCP

Il firewall GCP è **distribuito**: le regole vengono applicate direttamente al livello dell'hypervisor di ogni VM, non a un dispositivo di perimetro. Questo significa:

- Il traffico bloccato non attraversa mai la VM target (zero overhead di rete)
- Ogni VM ha il suo stato di firewall indipendente
- Non esiste un "security group" centralizzato come in AWS — le regole si applicano tramite **network tag** o **service account**

### Struttura di una Firewall Rule

```
Firewall Rule
├── Network: my-vpc
├── Direction: INGRESS | EGRESS
├── Priority: 0-65535 (più basso = più prioritario)
├── Action: ALLOW | DENY
├── Target: tag "web-server" | SA "app@project.iam..."
├── Source/Destination: range CIDR | tag | SA
└── Protocol/Port: tcp:80,443 | udp:53 | icmp | all
```

```bash
# Regola ingress basata su service account (best practice)
gcloud compute firewall-rules create allow-lb-to-app \
  --network=my-vpc \
  --direction=INGRESS \
  --priority=1000 \
  --action=ALLOW \
  --rules=tcp:8080 \
  --source-service-accounts=lb-sa@PROJECT.iam.gserviceaccount.com \
  --target-service-accounts=app-sa@PROJECT.iam.gserviceaccount.com \
  --description="Load balancer → App backend"

# Regola ingress basata su tag (meno sicura ma più semplice)
gcloud compute firewall-rules create allow-ssh-iap \
  --network=my-vpc \
  --direction=INGRESS \
  --priority=1000 \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=ssh-allowed \
  --description="SSH via IAP (range IP IAP tunneling)"

# Listare regole filtrando per VPC
gcloud compute firewall-rules list \
  --filter="network=my-vpc" \
  --format="table(name,direction,priority,sourceRanges,allowed,targetTags,targetServiceAccounts)"

# Descrivere regola specifica
gcloud compute firewall-rules describe allow-lb-to-app
```

!!! warning "Tag-based firewall: rischio sicurezza"
    Le **network tag** sono attributi stringa assegnabili da chiunque abbia `roles/compute.instanceAdmin`. Un utente malevolo con tale ruolo può aggiungere tag a una VM e bypassare regole firewall. Preferire sempre **firewall rules basate su service account** in ambienti di produzione: il SA deve essere esplicitamente assegnato alla VM e richiede `roles/iam.serviceAccountUser`.

### Firewall Rules vs Firewall Policy

| Caratteristica | Firewall Rules (legacy) | Firewall Policy |
|---|---|---|
| Scope | Singolo VPC | Organizzazione, folder, VPC |
| Gestione | Per-VPC | Centralizzata |
| Delegation | No | Sì (ereditarietà gerarchica) |
| Stateful | Sì | Sì |
| FQDN rules | No | Sì (dominio come sorgente/dest) |
| Geo-based | No | Sì (country filtering) |
| Raccomandato | Ambienti semplici | **Produzione enterprise** |

```bash
# Creare Firewall Policy a livello organizzazione
gcloud compute firewall-policies create org-baseline-policy \
  --short-name=org-baseline \
  --organization=ORG_ID

# Aggiungere regola alla policy
gcloud compute firewall-policies rules create 1000 \
  --firewall-policy=POLICY_ID \
  --organization=ORG_ID \
  --direction=INGRESS \
  --action=allow \
  --layer4-configs=tcp:443 \
  --src-ip-ranges=0.0.0.0/0 \
  --description="Allow HTTPS inbound"

# Associare la policy a un VPC
gcloud compute firewall-policies associations create \
  --firewall-policy=POLICY_ID \
  --network=projects/PROJECT/global/networks/my-vpc \
  --organization=ORG_ID
```

---

## Load Balancing su GCP — Tassonomia

GCP offre diversi tipi di load balancer. La scelta dipende dal protocollo, dalla portata (globale vs regionale) e dalla visibilità (esterno vs interno).

### Panoramica Tipi

```
Cloud Load Balancing
│
├── Application LB (Layer 7 — HTTP/S)
│   ├── Global External ALB   → traffico internet globale, anycast, Cloud Armor
│   ├── Regional External ALB → traffico internet regionale
│   └── Regional Internal ALB → traffico interno GKE/VM (istio-less mesh)
│
├── Network LB (Layer 4 — TCP/UDP/SSL)
│   ├── Global External NLB   → pass-through, IP anycast globale
│   ├── Regional External NLB → pass-through, IP statico regionale
│   └── Regional Internal NLB → ILB pass-through per traffico interno
│
└── [deprecati: Classic HTTP LB, TCP/UDP legacy ILB]
```

| Tipo | Protocollo | Scope | IP pubblico | Tipico uso |
|---|---|---|---|---|
| Global External ALB | HTTP/S | Globale | Sì | SaaS, API pubbliche |
| Regional External ALB | HTTP/S | Regionale | Sì | App regionali |
| Regional Internal ALB | HTTP/S | Regionale | No | Microservizi interni, GKE |
| Global External NLB | TCP/UDP | Globale | Sì | Gaming, IoT, VoIP globale |
| Regional Internal NLB | TCP/UDP | Regionale | No | Database, servizi TCP interni |

### Struttura Logica del ALB

Il Global External Application Load Balancer è composto da risorse GCP distinte che si combinano:

```
Internet
  ↓
[Forwarding Rule] — IP anycast globale + porta → protocol: HTTP/HTTPS
  ↓
[Target HTTP(S) Proxy] — termina TLS, gestisce certificati
  ↓
[URL Map] — routing basato su host/path
  ├── example.com/api/* → Backend Service "api-backend"
  ├── example.com/static/* → Backend Bucket (Cloud Storage)
  └── example.com/* → Backend Service "web-backend"
           ↓
    [Backend Service]
    ├── Health Check (HTTP :8080 /healthz)
    ├── Session affinity: NONE | CLIENT_IP | GENERATED_COOKIE
    ├── Timeout: 30s
    └── Backend
        ├── Instance Group (MIG us-central1, weight 100)
        ├── Instance Group (MIG europe-west1, weight 100)
        └── NEG — Network Endpoint Group
```

### NEG — Network Endpoint Group

I NEG sono il modo moderno per integrare il load balancer con GKE, Cloud Run e servizi esterni.

```bash
# Tipi di NEG
# Zonal NEG → VM o Pod GKE in una zona
# Serverless NEG → Cloud Run, App Engine, Cloud Functions
# Internet NEG → backend esterni (hybrid/on-prem)
# Private Service Connect NEG → PSC endpoints

# NEG per GKE (creato automaticamente dal GKE Ingress controller)
# Configurazione via annotation sull'Ingress:
```

```yaml
# Ingress GKE con GCE Ingress class (Global ALB)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app-ingress
  annotations:
    kubernetes.io/ingress.class: "gce"                      # Global External ALB
    kubernetes.io/ingress.global-static-ip-name: "my-app-ip"  # IP statico pre-creato
    networking.gke.io/managed-certificates: "my-app-cert"   # Certificate managed GCP
    kubernetes.io/ingress.allow-http: "false"               # HTTPS only
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
---
# Internal ALB per traffico interno GKE
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: internal-ingress
  annotations:
    kubernetes.io/ingress.class: "gce-internal"             # Regional Internal ALB
    kubernetes.io/ingress.regional-static-ip-name: "internal-ip"
spec:
  rules:
  - host: api.internal.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: internal-service
            port:
              number: 8080
```

```bash
# Backend Service via gcloud
gcloud compute backend-services create api-backend \
  --protocol=HTTP \
  --port-name=http \
  --health-checks=api-health-check \
  --global

# Health Check
gcloud compute health-checks create http api-health-check \
  --request-path=/healthz \
  --port=8080 \
  --check-interval=10s \
  --timeout=5s \
  --healthy-threshold=2 \
  --unhealthy-threshold=3

# URL Map
gcloud compute url-maps create my-url-map \
  --default-service=api-backend

# Path matcher
gcloud compute url-maps add-path-matcher my-url-map \
  --path-matcher-name=path-matcher \
  --default-service=api-backend \
  --path-rules=/api/*=api-backend,/static/*=static-backend
```

---

## Best Practices

!!! tip "Pianificazione CIDR: pensare in anticipo"
    Definire i range CIDR con spazio di crescita **prima** di creare il primo VPC. In GCP i range di subnet possono essere espansi (mai ridotti) ma non è possibile cambiare il range principale. Schema tipico enterprise: `/16` per VPC, `/20` per subnet per-regione (4094 IP), `/16-/22` per secondary ranges GKE (pods/services).

- **Mai usare Auto Mode in produzione** — impossibile personalizzare CIDR, problemi certi con peering
- **Preferire service account alle network tag** per le firewall rules — superficie di attacco minore
- **Abilitare VPC Flow Logs** con sampling rate 0.5 nelle subnet critiche — costo basso, debugging inestimabile
- **Private Google Access su tutte le subnet** — le VM senza IP pubblico devono accedere alle API Google
- **Cloud NAT con IP statico** quando sistemi esterni devono whitelistare IP di uscita
- **Shared VPC per organizzazioni multi-team** — il team networking centralizza, i team app consumano
- **Usare Firewall Policy gerarchica** per regole baseline comuni a tutti i VPC dell'organizzazione
- **NEG over Instance Groups** per GKE — i NEG mappano direttamente i Pod, eliminando un hop di rete
- **Regional Internal ALB** per traffico interno GKE invece di NodePort + kube-proxy — latenza minore e nessuna dipendenza da iptables

---

## Troubleshooting

### VPC Flow Logs: Abilitazione e Analisi

VPC Flow Logs cattura campioni del traffico di rete a livello di subnet. Essenziale per diagnosticare problemi di connettività e analizzare pattern di traffico.

```bash
# Abilitare Flow Logs su subnet esistente
gcloud compute networks subnets update subnet-prod-europe \
  --region=europe-west1 \
  --enable-flow-logs \
  --logging-flow-sampling=0.5 \
  --logging-aggregation-interval=interval-5-sec \
  --logging-metadata=include-all

# Query Flow Logs in Cloud Logging (Log Explorer)
# Filtrare per IP sorgente specifico:
# resource.type="gce_subnetwork"
# logName="projects/PROJECT/logs/compute.googleapis.com%2Fvpc_flows"
# jsonPayload.connection.src_ip="10.10.0.5"
```

### Symptom: VM non raggiunge API Google (Storage, BigQuery, ecc.)

**Causa:** Private Google Access non abilitato sulla subnet, oppure la VM ha solo IP privato ma la subnet non ha PGA attivo.

**Soluzione:**
```bash
# Verificare stato PGA sulla subnet
gcloud compute networks subnets describe subnet-prod-europe \
  --region=europe-west1 \
  --format="get(privateIpGoogleAccess)"

# Abilitare PGA
gcloud compute networks subnets update subnet-prod-europe \
  --region=europe-west1 \
  --enable-private-ip-google-access

# Verificare anche le route (deve esistere route 0.0.0.0/0 → default-internet-gateway
# per Private Google Access, oppure route specifica per 199.36.153.4/30)
gcloud compute routes list --filter="network=my-vpc"
```

### Symptom: VM non raggiunge internet (timeout su download, apt update, ecc.)

**Causa:** VM senza IP pubblico e Cloud NAT non configurato o non copre la subnet.

**Soluzione:**
```bash
# Verificare che Cloud NAT esista per la regione
gcloud compute routers nats list --router=router-europe-west1 --region=europe-west1

# Verificare che la subnet sia coperta dal NAT
gcloud compute routers nats describe nat-europe-west1 \
  --router=router-europe-west1 \
  --region=europe-west1 \
  --format="get(subnetworks,natIpAllocateOption,sourceSubnetworkIpRangesToNat)"

# Controllare i log NAT per vedere se le connessioni vengono droppate
# In Cloud Logging: resource.type="nat_gateway" AND jsonPayload.allocation_status="DROPPED"
```

### Symptom: Traffico bloccato tra VM nonostante firewall rule apparentemente corretta

**Causa comune:** Priority errata (regola DENY più prioritaria), tag non applicato alla VM, SA sbagliato, direzione errata (INGRESS vs EGRESS).

**Soluzione:**
```bash
# Usare Connectivity Tests — strumento di diagnosi managed GCP
gcloud network-connectivity tests create test-vm-to-vm \
  --source-ip=10.10.0.5 \
  --destination-ip=10.20.0.8 \
  --protocol=TCP \
  --destination-port=8080 \
  --project=my-project

# Controllare i risultati
gcloud network-connectivity tests describe test-vm-to-vm \
  --format="get(reachabilityDetails)"

# Verificare quale firewall rule si applica effettivamente alla VM
gcloud compute instances describe my-vm \
  --zone=europe-west1-b \
  --format="get(networkInterfaces[0].network,tags.items,serviceAccounts[0].email)"
```

### Symptom: Load balancer restituisce 502/503 intermittenti

**Causa:** Health check fallisce su alcuni backend (configurazione errata, app non risponde sul path/porta dell'health check), oppure timeout Backend Service troppo basso.

```bash
# Verificare stato backend nel Backend Service
gcloud compute backend-services get-health api-backend \
  --global \
  --format="table(status.healthStatus[].instance,status.healthStatus[].healthState)"

# Controllare health check configuration
gcloud compute health-checks describe api-health-check

# Aumentare timeout se l'app è lenta ad avviarsi
gcloud compute backend-services update api-backend \
  --timeout=60 \
  --global
```

### Firewall Insights — Regole non Usate

```bash
# Firewall Insights identifica regole mai utilizzate (richiede abilitazione API)
gcloud services enable firewallinsights.googleapis.com

# Le insight sono visibili in Console → Network Security → Firewall Insights
# Via API:
gcloud beta network-management firewall-insights list \
  --filter="insightType=SHADOWED_FIREWALL_RULE" \
  --location=global
```

---

## Relazioni

La rete GCP si integra con altri componenti della KB:

??? info "VPC-native GKE — Approfondimento"
    GKE in modalità VPC-native usa secondary ranges della subnet per assegnare IP direttamente ai Pod (Alias IP). Ogni nodo riserva un blocco `/24` dal range pods. Questo elimina la necessità di kube-proxy per il routing Pod-to-Pod e migliora le performance.

    **Approfondimento completo →** [Google Kubernetes Engine](../containers/gke.md)

??? info "Firewall WAF e DDoS — Approfondimento"
    Cloud Armor è il WAF/DDoS di GCP, integrato nel Global External ALB. Supporta regole OWASP, geo-blocking, rate limiting e protezione adattiva contro DDoS volumetrici.

    **Approfondimento completo →** [Firewall e WAF](../../../networking/sicurezza/firewall-waf.md)

??? info "NAT — Principi Fondamentali"
    Cloud NAT implementa SNAT (Source NAT) mantenendo una tabella di connessioni stateful. A differenza di un NAT su VM, non introduce un singolo punto di failure e scala automaticamente al numero di connessioni.

    **Approfondimento completo →** [NAT](../../../networking/fondamentali/nat.md)

??? info "Load Balancing Layer 4 vs Layer 7 — Principi"
    La distinzione tra Application LB (L7) e Network LB (L4) su GCP segue gli stessi principi architetturali del load balancing generico: L7 termina il protocollo applicativo, L4 è pass-through.

    **Approfondimento completo →** [Layer 4 vs Layer 7](../../../networking/load-balancing/layer4-vs-layer7.md)

---

## Riferimenti

- [Documentazione VPC GCP](https://cloud.google.com/vpc/docs/vpc) — guida completa alla Virtual Private Cloud
- [Cloud NAT Overview](https://cloud.google.com/nat/docs/overview) — architettura e configurazione Cloud NAT
- [Cloud Load Balancing Overview](https://cloud.google.com/load-balancing/docs/load-balancing-overview) — tassonomia completa dei load balancer GCP
- [Firewall Rules Overview](https://cloud.google.com/vpc/docs/firewalls) — modello di firewall distribuito GCP
- [Hierarchical Firewall Policies](https://cloud.google.com/vpc/docs/firewall-policies) — firewall policy a livello organizzazione
- [VPC Flow Logs](https://cloud.google.com/vpc/docs/flow-logs) — abilitazione e analisi dei flow log
- [Connectivity Tests](https://cloud.google.com/network-intelligence-center/docs/connectivity-tests/concepts/overview) — diagnosi connettività managed
- [Private Service Connect](https://cloud.google.com/vpc/docs/private-service-connect) — accesso privato a servizi managed
