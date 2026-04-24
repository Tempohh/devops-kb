---
title: "Kubernetes Gateway API"
slug: gateway-api
category: networking
tags: [kubernetes, gateway-api, httproute, gatewayclass, ingress, routing, traffic-management, canary, grpc, tls]
search_keywords: [gateway api, kubernetes gateway api, httproute, grpcroute, tcproute, udproute, gatewayclass, gateway resource, ingress replacement, ingress successor, role-based routing, canary deployment, traffic splitting, header routing, nginx gateway fabric, istio gateway, traefik gateway, cilium gateway, envoy gateway, weight-based routing, path routing, tls passthrough, tlsroute, multi-tenancy routing, kubernetes 1.28, gateway api ga, sigs gateway api, kubernetes networking, ingress alternative, kubernetes traffic management, k8s gateway, policy attachment, backendtlspolicy, referencegrant, cross-namespace routing]
parent: networking/kubernetes/_index
related: [networking/kubernetes/ingress, networking/kubernetes/network-policies, networking/kubernetes/cni, networking/service-mesh/linkerd]
official_docs: https://gateway-api.sigs.k8s.io/
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# Kubernetes Gateway API

## Panoramica

La **Kubernetes Gateway API** è il successore ufficiale di Ingress per la gestione del traffico in entrata nei cluster Kubernetes. Diventata GA (stable) per le funzionalità core con Kubernetes 1.28, risolve i limiti strutturali di Ingress: un singolo tipo di risorsa (`Ingress`) gestiva tutto, costringendo i vendor a proliferare annotations non portabili. Gateway API introduce un modello a tre livelli con tipi separati per ruoli diversi — infra team, platform team, app team — e supporta nativamente protocolli che Ingress non può gestire: gRPC, TCP/UDP, TLS passthrough.

Quando usarla: cluster nuovi su Kubernetes 1.28+, ambienti multi-tenant con teams separati, casi d'uso che richiedono traffic splitting nativo, gRPC routing, o TLS passthrough senza annotations vendor-specific. Quando **non** usarla: cluster legacy con controller che non supportano ancora Gateway API, ambienti dove Ingress funziona e non porta valore aggiunto la migrazione.

!!! warning "GA ≠ tutto stabile"
    Il core (GatewayClass, Gateway, HTTPRoute) è GA. Funzionalità avanzate come `TCPRoute`, `UDPRoute`, `GRPCRoute` e le Policy Attachment sono ancora in canale `experimental` — verificare supporto nel controller specifico prima di usarle in produzione.

## Concetti Chiave

### Il Modello a Tre Livelli

Gateway API separa le responsabilità in tre tipi di risorse, ciascuna gestita da un team diverso:

```
GatewayClass  ←── Infra team / cluster admin
    │              (chi installa e configura il controller)
    ▼
Gateway       ←── Platform team
    │              (chi gestisce l'accesso al cluster per ambiente)
    ▼
HTTPRoute /   ←── App team
TCPRoute /         (chi fa deploy delle applicazioni)
GRPCRoute
```

| Risorsa | Chi la gestisce | Cosa definisce |
|---------|-----------------|----------------|
| `GatewayClass` | Infra/cluster admin | Il tipo di controller (nginx, istio, traefik...) |
| `Gateway` | Platform/ops team | Listener (porta, protocollo, TLS), namespace ammessi |
| `HTTPRoute` | App team | Regole di routing per una specifica applicazione |

### Route Types

| Tipo | Canale | Usa case |
|------|--------|----------|
| `HTTPRoute` | Stable | Routing HTTP/1.1 e HTTP/2 |
| `GRPCRoute` | Experimental | Routing gRPC nativo |
| `TLSRoute` | Experimental | TLS passthrough (senza terminazione) |
| `TCPRoute` | Experimental | TCP generico |
| `UDPRoute` | Experimental | UDP generico |

### Policy Attachment

Gateway API introduce `PolicyAttachment` per applicare policy trasversali (timeout, retry, autenticazione, rate limiting) alle risorse senza annotations. Le policy si "attaccano" a Gateway, HTTPRoute o Service tramite `targetRef`.

```yaml
# BackendLBPolicy (experimental) — esempio di policy attachment
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: BackendLBPolicy
metadata:
  name: orders-lb-policy
spec:
  targetRef:
    group: ""
    kind: Service
    name: orders-service
  sessionPersistence:
    sessionName: orders-session
    type: Cookie
```

## Architettura / Come Funziona

```
Internet
    │ (443/80)
    ▼
Cloud Load Balancer / NodePort
    │
    ▼
Gateway (pod del controller: nginx/istio/traefik/cilium)
    │  Legge GatewayClass → Gateway → Routes dall'API server
    │
    ├── Listener :443 HTTPS ──► HTTPRoute(app team ns: orders)
    │                           ├── /api/v1  → orders-svc:8080 (w:90)
    │                           └── /api/v1  → orders-v2:8080  (w:10)
    │
    ├── Listener :443 HTTPS ──► HTTPRoute(app team ns: frontend)
    │                           └── /        → frontend-svc:80
    │
    └── Listener :5432 TCP  ──► TCPRoute(db ns: postgres)
                                └──          → postgres-svc:5432
```

### Cross-Namespace Routing e ReferenceGrant

Una delle funzionalità chiave di Gateway API è il routing cross-namespace controllato. Un `HTTPRoute` nel namespace `orders` può referenziare un `Gateway` nel namespace `infra`, ma solo se esiste un `ReferenceGrant` che lo autorizza esplicitamente.

```yaml
# Nel namespace infra: autorizza orders a usare il gateway
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-orders-routes
  namespace: infra          # namespace dove sta il Gateway
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: orders       # namespace autorizzato a referenziare
  to:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: prod-gateway
```

Senza `ReferenceGrant`, un HTTPRoute in un namespace non può referenziare risorse in un altro — sicurezza by design.

## Configurazione & Pratica

### Installazione — NGINX Gateway Fabric

NGINX Gateway Fabric è la scelta per chi già usa nginx-ingress e vuole una migrazione naturale.

```bash
# Installa le CRD di Gateway API (prerequisito per qualsiasi controller)
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml

# Installa canale experimental (TCPRoute, GRPCRoute, ecc.)
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/experimental-install.yaml

# Installa NGINX Gateway Fabric tramite Helm
helm install ngf oci://ghcr.io/nginxinc/charts/nginx-gateway-fabric \
  --namespace nginx-gateway \
  --create-namespace \
  --version 1.4.0 \
  --set service.type=LoadBalancer

# Verifica installazione
kubectl get pods -n nginx-gateway
kubectl get gatewayclass
# Output atteso: nginx   gateway.nginx.org/nginx-gateway-controller   True
```

```bash
# Verifica che le CRD siano installate
kubectl get crd | grep gateway.networking.k8s.io
# Output: gateways.gateway.networking.k8s.io
#         httproutes.gateway.networking.k8s.io
#         gatewayclasses.gateway.networking.k8s.io
#         ...
```

### Installazione — Envoy Gateway (CNCF)

Envoy Gateway è il progetto CNCF basato su Envoy proxy, raccomandato per ambienti cloud-native.

```bash
# Installa Envoy Gateway
helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.2.1 \
  --namespace envoy-gateway-system \
  --create-namespace

# Verifica
kubectl wait --timeout=5m -n envoy-gateway-system \
  deployment/envoy-gateway --for=condition=Available
kubectl get gatewayclass
```

### Configurazione Base: GatewayClass → Gateway → HTTPRoute

```yaml
# 1. GatewayClass — gestita dall'infra team (una per cluster)
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: nginx
spec:
  controllerName: gateway.nginx.org/nginx-gateway-controller
  description: "NGINX Gateway Fabric — cluster principale"
```

```yaml
# 2. Gateway — gestito dal platform team (uno per ambiente/zona)
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: prod-gateway
  namespace: infra
spec:
  gatewayClassName: nginx
  listeners:
  - name: http
    port: 80
    protocol: HTTP
    allowedRoutes:
      namespaces:
        from: Selector          # Solo namespace con label specifica
        selector:
          matchLabels:
            gateway-access: "true"

  - name: https
    port: 443
    protocol: HTTPS
    tls:
      mode: Terminate           # Termina TLS qui
      certificateRefs:
      - name: wildcard-cert     # Secret TLS nel namespace infra
        namespace: infra
    allowedRoutes:
      namespaces:
        from: Selector
        selector:
          matchLabels:
            gateway-access: "true"
```

```yaml
# 3. HTTPRoute — gestita dall'app team nel proprio namespace
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: orders-route
  namespace: orders             # namespace dell'applicazione
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra            # referenzia gateway in altro namespace
    sectionName: https          # specifica quale listener usare
  hostnames:
  - "orders.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1
    backendRefs:
    - name: orders-service
      port: 8080
      weight: 100
```

```bash
# Verifica stato HTTPRoute
kubectl get httproute orders-route -n orders
# Output: NAME           HOSTNAMES                PARENTS                        AGE
#         orders-route   ["orders.example.com"]   [{"name":"prod-gateway",...}]  5m

kubectl describe httproute orders-route -n orders
# Controllare "Status.Parents" — deve mostrare "Accepted: True"
```

### TLS con cert-manager

```yaml
# ClusterIssuer Let's Encrypt
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        gatewayHTTPRoute:
          parentRefs:
          - name: prod-gateway
            namespace: infra
            kind: Gateway
```

```yaml
# Certificate — cert-manager crea il Secret automaticamente
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-cert
  namespace: infra
spec:
  secretName: wildcard-cert        # usato nel Gateway.spec.listeners[].tls.certificateRefs
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - "*.example.com"
  - "example.com"
```

### Traffic Management Avanzato

#### Canary Release con Weight-Based Routing

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: orders-canary
  namespace: orders
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
  hostnames:
  - "orders.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1
    backendRefs:
    - name: orders-v1          # versione stabile
      port: 8080
      weight: 90               # 90% del traffico
    - name: orders-v2          # canary
      port: 8080
      weight: 10               # 10% del traffico
```

#### Header-Based Routing (per test team)

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: orders-header-routing
  namespace: orders
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
  hostnames:
  - "orders.example.com"
  rules:
  # Prima regola: header X-Canary → sempre v2 (test team)
  - matches:
    - headers:
      - name: X-Canary
        value: "true"
    backendRefs:
    - name: orders-v2
      port: 8080
      weight: 100

  # Seconda regola: traffico normale → split
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1
    backendRefs:
    - name: orders-v1
      port: 8080
      weight: 95
    - name: orders-v2
      port: 8080
      weight: 5
```

#### Redirect e URL Rewrite

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: redirect-route
  namespace: orders
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
    sectionName: http          # listener HTTP per redirect
  rules:
  # Redirect HTTP → HTTPS (301)
  - matches:
    - path:
        type: PathPrefix
        value: /
    filters:
    - type: RequestRedirect
      requestRedirect:
        scheme: https
        statusCode: 301

---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: rewrite-route
  namespace: orders
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
    sectionName: https
  rules:
  # URL Rewrite: /api/v2/orders → /orders (strip prefix)
  - matches:
    - path:
        type: PathPrefix
        value: /api/v2/orders
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplacePrefixMatch
          replacePrefixMatch: /orders
    backendRefs:
    - name: orders-service
      port: 8080
```

#### GRPCRoute (experimental)

```yaml
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: GRPCRoute
metadata:
  name: payment-grpc
  namespace: payments
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
  hostnames:
  - "grpc.example.com"
  rules:
  - matches:
    - method:
        service: payments.PaymentService    # package.ServiceName
        method: ProcessPayment             # metodo specifico
    backendRefs:
    - name: payment-grpc-service
      port: 9090
  - matches:
    - method:
        service: payments.PaymentService   # tutti i metodi del service
    backendRefs:
    - name: payment-grpc-service
      port: 9090
```

### ReferenceGrant — Cross-Namespace completo

```yaml
# Scenario: HTTPRoute nel namespace "orders" referenzia un Secret TLS nel namespace "infra"
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-orders-to-read-tls
  namespace: infra               # namespace dove sta il Secret
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: orders            # chi può referenziare
  to:
  - group: ""
    kind: Secret
    name: wildcard-cert          # Secret specifico autorizzato
```

## Best Practices

!!! tip "Organizzazione per ruolo"
    Mantenere GatewayClass e Gateway in un namespace dedicato (`infra`, `platform`, `gateway-system`). Gli app team non devono avere accesso a questi namespace. Ogni namespace applicativo espone solo HTTPRoute.

- **ReferenceGrant espliciti**: non usare `allowedRoutes.namespaces.from: All` in produzione — preferire `Selector` con label che i platform team controllano
- **Una GatewayClass per controller**: se si usano più controller (nginx per HTTP, istio per service mesh), creare GatewayClass distinte con nomi descrittivi
- **`sectionName` nei parentRefs**: specificare sempre il listener esatto — evita ambiguità quando il Gateway ha listener multipli (80, 443, 9443...)
- **Status conditions**: monitorare `status.parents[].conditions` nelle HTTPRoute — `Accepted: False` indica un problema di configurazione (spesso ReferenceGrant mancante)
- **cert-manager + Gateway API**: usare l'integrazione nativa `gatewayHTTPRoute` solver invece del solver Ingress — supporto diretto senza risorse intermedie
- **Gateway API + Ingress coesistono**: durante la migrazione, entrambi possono girare sullo stesso cluster senza conflitti — migrare un namespace alla volta

!!! warning "allowedRoutes.namespaces.from: All è un rischio"
    Con `from: All`, qualsiasi namespace del cluster può agganciare HTTPRoute al Gateway — inclusi namespace di tenant non fidati. In ambienti multi-tenant usare sempre `Selector` con label controlled by platform team.

## Confronto con Ingress

| Feature | Ingress | Gateway API |
|---------|---------|-------------|
| TLS passthrough | annotation vendor | `TLSRoute` nativo (experimental) |
| Traffic splitting/canary | annotation nginx/traefik | spec nativo `weight` |
| Header-based routing | annotation nginx | spec nativo `headers` matcher |
| URL rewrite | annotation nginx | `URLRewrite` filter nativo |
| Redirect | annotation nginx | `RequestRedirect` filter nativo |
| Role-based management | risorsa monolitica | GatewayClass/Gateway/Route separati |
| TCP/UDP routing | non supportato | `TCPRoute`/`UDPRoute` (experimental) |
| gRPC routing | workaround annotation | `GRPCRoute` nativo (experimental) |
| Cross-namespace routing | non supportato | supportato via `ReferenceGrant` |
| Portabilità config | annotations vendor-lock | spec standard multi-controller |
| Maturità | GA, ampio supporto | Core GA da K8s 1.28 |

## Migrazione da Ingress

### Strategia di Migrazione Graduale

La migrazione non è big-bang: Gateway API e Ingress coesistono sullo stesso cluster. Ogni controller che supporta entrambi (nginx-ingress ≥ 1.9, Traefik v3, Istio, Cilium) può gestirli in parallelo.

```bash
# Verifica se il controller già supporta Gateway API
kubectl get gatewayclass
# Se vuoto: installare il nuovo controller Gateway API-native

# Verifica versione Kubernetes (deve essere >= 1.28 per core GA)
kubectl version --short
```

```bash
# Tool di migrazione automatica (converte Ingress → HTTPRoute)
# Installa il plugin kubectl
kubectl krew install gateway-api

# Genera HTTPRoute equivalenti a tutti gli Ingress nel namespace
kubectl get ingress -n production -o yaml | \
  kubectl gateway-api convert --from ingress --namespace production

# Preview: mostra le HTTPRoute che verrebbe generate senza applicarle
kubectl gateway-api convert --from ingress -n production --dry-run=client
```

```yaml
# Prima (Ingress)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: orders-ingress
  namespace: orders
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
  - host: orders.example.com
    http:
      paths:
      - path: /api/v1(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: orders-service
            port:
              number: 8080
```

```yaml
# Dopo (HTTPRoute equivalente)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: orders-route
  namespace: orders
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
  hostnames:
  - "orders.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplacePrefixMatch
          replacePrefixMatch: /
    backendRefs:
    - name: orders-service
      port: 8080
```

## Troubleshooting

### Scenario 1 — HTTPRoute in stato `Not Accepted`

**Sintomo:** `kubectl get httproute` mostra la route ma il traffico non viene instradato. `kubectl describe httproute` mostra `Accepted: False` nei conditions.

**Causa:** Il Gateway non accetta la route — quasi sempre per un problema di `allowedRoutes` (namespace non autorizzato) o `ReferenceGrant` mancante.

**Soluzione:**

```bash
# Ispeziona i conditions della HTTPRoute
kubectl describe httproute orders-route -n orders
# Cercare:   Status:
#              Parents:
#                Conditions:
#                  Message: namespace "orders" is not allowed
#                  Reason: NotAllowedByListeners

# Verifica la configurazione allowedRoutes del Gateway
kubectl get gateway prod-gateway -n infra -o yaml | grep -A10 allowedRoutes

# Controlla che il namespace orders abbia il label corretto
kubectl get namespace orders --show-labels
# Se manca il label: aggiungilo
kubectl label namespace orders gateway-access=true

# Verifica ReferenceGrant se la route referenzia risorse cross-namespace
kubectl get referencegrant -n infra
```

---

### Scenario 2 — Gateway in `Programmed: False`

**Sintomo:** Il Gateway esiste ma non ha un IP assegnato. `kubectl get gateway` mostra colonna `ADDRESS` vuota.

**Causa:** Il controller non riesce a creare il Service LoadBalancer (cloud provider non configurato, quota IP esaurita) oppure il controller non è in esecuzione.

**Soluzione:**

```bash
# Stato del Gateway
kubectl describe gateway prod-gateway -n infra
# Cercare: Conditions:
#            Reason: AddressNotAssigned
#            Message: ...

# Verifica che il controller sia Running
kubectl get pods -n nginx-gateway
kubectl logs -n nginx-gateway -l app=nginx-gateway --tail=50

# Verifica Service del controller
kubectl get svc -n nginx-gateway
# Se TYPE=LoadBalancer e EXTERNAL-IP è <pending> → problema cloud provider

# Su cluster locale (kind/minikube): usa NodePort o metallb
kubectl get svc -n nginx-gateway -o yaml | grep -A5 "type:"
```

---

### Scenario 3 — 404 per regole che sembrano corrette

**Sintomo:** Il Gateway risponde 404 su path che sono definiti nell'HTTPRoute.

**Causa:** Il `sectionName` nel `parentRef` non corrisponde al nome del listener nel Gateway, oppure l'hostname nell'HTTPRoute non matcha l'hostname nella richiesta.

**Soluzione:**

```bash
# Verifica i nomi dei listener nel Gateway
kubectl get gateway prod-gateway -n infra -o jsonpath='{.spec.listeners[*].name}'
# Output: http https (assicurarsi che sectionName in parentRef sia esatto)

# Testa con curl specificando l'host corretto
curl -v -H "Host: orders.example.com" https://<GATEWAY-IP>/api/v1/orders

# Verifica tutti gli hostnames configurati
kubectl get httproute -n orders -o jsonpath='{.items[*].spec.hostnames}'

# Debug: lista tutte le route accettate dal gateway
kubectl get httproute -A -o custom-columns=\
  NS:.metadata.namespace,NAME:.metadata.name,\
  HOSTS:.spec.hostnames,ACCEPTED:.status.parents[0].conditions[0].status
```

---

### Scenario 4 — Traffic splitting non funziona (tutti su v1)

**Sintomo:** Nonostante `weight: 10` su orders-v2, tutto il traffico va su orders-v1.

**Causa:** Il controller non supporta il traffic splitting (non tutti i controller implementano la feature — verificare la conformance matrix). Oppure il `weight: 0` non viene interpretato come "rimuovi" ma come "uguale".

**Soluzione:**

```bash
# Verifica la conformance del controller per HTTPRoute
# Documentazione: https://gateway-api.sigs.k8s.io/implementations/

# Test rapido: invia 100 richieste e conta la distribuzione
for i in $(seq 1 100); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Host: orders.example.com" \
    https://<GATEWAY-IP>/api/v1/orders
done | sort | uniq -c

# Verifica che entrambi i Service abbiano endpoint
kubectl get endpoints orders-v1 -n orders
kubectl get endpoints orders-v2 -n orders
# Se uno mostra <none>: i pod non sono Ready

# Log del controller per errori di configurazione
kubectl logs -n nginx-gateway -l app=nginx-gateway | grep -i "weight\|split\|error"
```

---

### Scenario 5 — ReferenceGrant non risolve il problema cross-namespace

**Sintomo:** `ReferenceGrant` creato ma la HTTPRoute continua a mostrare `RefNotPermitted`.

**Causa:** Il `ReferenceGrant` deve essere nel namespace della risorsa referenziata (non nel namespace dell'HTTPRoute), e i campi `from`/`to` devono corrispondere esattamente.

**Soluzione:**

```bash
# Verifica posizione e configurazione del ReferenceGrant
kubectl get referencegrant -A
# Il ReferenceGrant DEVE essere nel namespace del Gateway/Secret, non dell'HTTPRoute

kubectl describe referencegrant allow-orders-routes -n infra
# Verificare:
#   From: [ {Group: gateway.networking.k8s.io, Kind: HTTPRoute, Namespace: orders} ]
#   To:   [ {Group: gateway.networking.k8s.io, Kind: Gateway, Name: prod-gateway} ]

# Verifica case-sensitive: "HTTPRoute" non "Httproute"
kubectl get referencegrant -n infra -o yaml | grep -A5 "from:"
```

## Relazioni

??? info "Ingress — Il predecessore"
    Gateway API è il successore di Ingress. Durante la migrazione, entrambi coesistono. Ingress rimane la scelta per cluster pre-1.28 o controller legacy.

    **Approfondimento →** [Ingress e Ingress Controller](ingress.md)

??? info "Service Mesh — Integrazione"
    Istio e Linkerd supportano Gateway API come data plane. Con Istio, il Gateway API controlla anche il traffico est-ovest via `HTTPRoute` cross-mesh.

    **Approfondimento →** [Linkerd Service Mesh](../../networking/service-mesh/linkerd.md)

??? info "Network Policies — Sicurezza a complemento"
    Gateway API gestisce il traffico ingress, ma Network Policies controllano il traffico inter-pod. Usarle insieme per un modello di sicurezza completo.

    **Approfondimento →** [Network Policies](network-policies.md)

## Riferimenti

- [Kubernetes Gateway API — Documentazione ufficiale](https://gateway-api.sigs.k8s.io/)
- [Gateway API Implementations — Conformance matrix](https://gateway-api.sigs.k8s.io/implementations/)
- [NGINX Gateway Fabric](https://docs.nginx.com/nginx-gateway-fabric/)
- [Envoy Gateway](https://gateway.envoyproxy.io/)
- [KEP-1867: Gateway API](https://github.com/kubernetes/enhancements/tree/master/keps/sig-network/1867-gateway-api)
- [cert-manager Gateway API Integration](https://cert-manager.io/docs/usage/gateway/)
