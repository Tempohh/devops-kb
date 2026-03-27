---
title: "Kubernetes Networking"
slug: networking
category: containers
tags: [kubernetes, networking, cni, services, ingress, networkpolicy, coredns, cilium, calico]
search_keywords: [kubernetes networking, CNI container network interface, kubernetes service clusterip, kubernetes nodeport, kubernetes loadbalancer, kubernetes ingress, kubernetes networkpolicy, coredns kubernetes, service discovery kubernetes, kube-proxy, iptables kubernetes, ipvs kubernetes, kubernetes dns, pod network, kubernetes cluster network, kubernetes overlay network, flannel, calico, cilium, weave net, kubernetes ingress controller, nginx ingress, traefik kubernetes, kubernetes egress, kubernetes east-west traffic, kubernetes north-south traffic, kubernetes service mesh intro, kubernetes pod ip, kubernetes service ip, endpoint kubernetes, endpointslice]
parent: containers/kubernetes/_index
related: [containers/kubernetes/architettura, containers/kubernetes/sicurezza, containers/kubernetes/workloads, containers/docker/networking]
official_docs: https://kubernetes.io/docs/concepts/services-networking/
status: complete
difficulty: advanced
last_updated: 2026-03-25
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

### ClusterIP (default)

Espone il Service solo all'interno del cluster. Il ClusterIP è un IP virtuale gestito da kube-proxy.

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

```bash
# Verifica Service e i suoi Endpoints
kubectl get service api -n production
kubectl get endpoints api -n production          # IP:porta dei Pod selezionati
kubectl get endpointslices -n production         # versione scalabile degli endpoints

# Debug: il Service non raggiunge i Pod?
kubectl describe service api -n production       # verifica selector
kubectl get pods -n production -l app=api        # i Pod hanno il label corretto?
```

### NodePort

Espone il Service su una porta statica su ogni nodo del cluster (range default: 30000-32767).

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
#
# ATTENZIONE: kube-proxy fa SNAT sul traffico NodePort
# → il Pod vede l'IP del nodo, non l'IP del client originale
# → Per preservare l'IP sorgente: externalTrafficPolicy: Local
```

```yaml
# externalTrafficPolicy: Local — preserva IP client ma limita bilanciamento
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
spec:
  type: NodePort
  externalTrafficPolicy: Local   # traffico va SOLO ai Pod sul nodo ricevente
  # Pro: IP client originale preservato nel Pod
  # Contro: se il nodo non ha Pod, il traffico viene droppato → richiede LB esterno
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080
```

### LoadBalancer

Richiede un cloud provider o un controller esterno (MetalLB per bare metal) che provvede un External IP.

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

### ExternalName e Headless Service

```yaml
# ExternalName: CNAME verso servizio esterno al cluster
apiVersion: v1
kind: Service
metadata:
  name: external-db
  namespace: production
spec:
  type: ExternalName
  externalName: mydb.rds.amazonaws.com   # risolve in CNAME, no ClusterIP
  # Uso: permette al codice di usare "external-db" come hostname
  # → facile switch tra DB esterno e interno senza cambiare config app

---
# Headless Service: ClusterIP: None → DNS ritorna direttamente gli IP dei Pod
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
# postgres-headless.production.svc.cluster.local → A records di tutti i Pod
# Con StatefulSet: postgres-0.postgres-headless.production.svc.cluster.local → IP pod-0
# Usato per: StatefulSet, service discovery client-side, database cluster
```

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
