---
title: "Kubernetes Ingress"
slug: ingress
category: containers
tags: [kubernetes, ingress, nginx, traefik, tls, routing, http, https, canary, rate-limiting]
search_keywords: [ingress controller kubernetes, nginx ingress, traefik kubernetes, ingress tls termination, path routing k8s, host-based routing, canary deployment ingress, rate limiting ingress, kubernetes ingress annotations, ingressclass, ingress 404 502, cert-manager ingress, oauth2-proxy ingress, basic auth ingress, wildcard ingress, fanout ingress, rewrite-target nginx, ingress controller ha, ingress controller produzione, haproxy ingress, aws alb ingress, gateway api]
parent: containers/kubernetes/_index
related: [containers/kubernetes/networking, containers/kubernetes/sicurezza, containers/kubernetes/workloads]
official_docs: https://kubernetes.io/docs/concepts/services-networking/ingress/
status: complete
difficulty: intermediate
last_updated: 2026-03-25
---

# Kubernetes Ingress

## Panoramica

Un **Ingress** è una risorsa Kubernetes (`networking.k8s.io/v1`) che espone servizi HTTP/HTTPS all'esterno del cluster definendo regole di routing basate su host e path. A differenza di un `LoadBalancer` Service (un IP per servizio), un Ingress permette a un singolo punto di ingresso di smistare il traffico verso decine di servizi — riducendo drasticamente il numero di load balancer cloud (e i relativi costi).

La risorsa Ingress da sola **non fa nulla**: richiede un **Ingress Controller** in esecuzione nel cluster che legge le risorse Ingress e configura il reverse proxy/LB sottostante (NGINX, Traefik, HAProxy, AWS ALB, GCE HTTP LB, ecc.). Ogni controller ha le proprie annotations per funzionalità avanzate.

**Quando usare Ingress:** applicazioni HTTP/HTTPS che necessitano di routing per host o path, TLS termination centralizzata, rate limiting, autenticazione.

**Quando NON usare Ingress:** protocolli non-HTTP (TCP/UDP raw → usare Service `LoadBalancer` o `NodePort`), service mesh avanzato con mTLS bidirezionale (→ Istio/Linkerd), ambienti on-premise senza accesso a cloud LB (valutare MetalLB + Ingress).

---

## Concetti Chiave

### IngressClass

Dalla versione 1.18, Kubernetes introduce `IngressClass` come oggetto di primo livello per identificare il controller responsabile di un Ingress. Ogni Ingress deve specificare `spec.ingressClassName` (o impostare una classe default).

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"  # applicato se ingressClassName non specificato
spec:
  controller: k8s.io/ingress-nginx
```

!!! warning "Annotazione vs ingressClassName"
    Il vecchio campo `kubernetes.io/ingress.class` annotation è deprecato dalla 1.18. Usare sempre `spec.ingressClassName`. Se coesistono controller multipli (nginx + Traefik), ogni Ingress deve specificare la classe corretta — altrimenti viene ignorato dal controller sbagliato o applicato da entrambi.

### PathType

Ogni path nell'Ingress ha un `pathType` che determina come viene fatto il match:

| PathType | Comportamento | Esempio |
|---|---|---|
| `Exact` | Match esatto dell'URI | `/api/v1` corrisponde solo a `/api/v1` |
| `Prefix` | Match per prefisso (split su `/`) | `/api` corrisponde a `/api`, `/api/v1`, `/api/v2/users` |
| `ImplementationSpecific` | Dipende dal controller | usare con cautela, comportamento variabile |

### TLS e Terminazione SSL

L'Ingress supporta TLS termination: il traffico esterno arriva cifrato HTTPS, il controller decifra e inoltra in HTTP (o HTTPS) ai backend. I certificati sono memorizzati in `Secret` di tipo `kubernetes.io/tls`.

---

## Architettura / Come Funziona

```
Internet
    │
    ▼
[Cloud Load Balancer / NodePort]
    │  (porta 80/443)
    ▼
[Ingress Controller Pod]   ← legge risorse Ingress via API Server
    │  (reverse proxy: NGINX/Traefik/...)
    │
    ├─── host: api.company.com / path: /v1  ──▶  Service api-v1 (ClusterIP)
    │                                                 │
    │                                                 ▼
    │                                             Pod api-v1-xxx
    │
    ├─── host: api.company.com / path: /v2  ──▶  Service api-v2 (ClusterIP)
    │
    └─── host: app.company.com / path: /   ──▶  Service frontend (ClusterIP)
```

Il controller esegue un watch continuo sull'API Server: ogni modifica a una risorsa Ingress viene recepita e il proxy viene riconfigurato (senza downtime per NGINX: hot reload).

---

## Configurazione & Pratica

### NGINX Ingress Controller — Installazione

```bash
# Installazione via Helm (consigliato per produzione)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Installazione base con 2 repliche
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.nodeSelector."kubernetes\.io/os"=linux \
  --set controller.resources.requests.cpu=100m \
  --set controller.resources.requests.memory=256Mi \
  --set controller.resources.limits.cpu=500m \
  --set controller.resources.limits.memory=512Mi

# Verifica installazione
kubectl get pods -n ingress-nginx
kubectl get service -n ingress-nginx   # External-IP = IP del LB cloud
```

```yaml
# values.yaml — configurazione production-grade
controller:
  replicaCount: 3

  # Anti-affinity: un pod per nodo
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
          topologyKey: kubernetes.io/hostname

  # HPA per auto-scaling del controller
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

  # Metriche Prometheus
  metrics:
    enabled: true
    serviceMonitor:
      enabled: true

  # ConfigMap globale
  config:
    use-forwarded-headers: "true"
    proxy-body-size: "50m"
    keep-alive: "75"
    worker-processes: "auto"
```

### Ingress Base — Host e Path Routing

```yaml
# Ingress con routing multi-host e multi-path
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: production
  annotations:
    # Redirect automatico HTTP → HTTPS
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  ingressClassName: nginx

  # TLS: un solo blocco può coprire più host
  tls:
    - hosts:
        - api.company.com
        - app.company.com
      secretName: company-tls-wildcard   # Secret tipo kubernetes.io/tls

  rules:
    # API backend — path-based routing con rewrite
    - host: api.company.com
      http:
        paths:
          - path: /v1(/|$)(.*)
            pathType: Prefix
            backend:
              service:
                name: api-v1
                port:
                  number: 8080
          - path: /v2(/|$)(.*)
            pathType: Prefix
            backend:
              service:
                name: api-v2
                port:
                  number: 8080

    # Frontend SPA — tutto il traffico verso un servizio
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
```

### Rate Limiting

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress-ratelimited
  namespace: production
  annotations:
    # Limite per connessioni al secondo per IP
    nginx.ingress.kubernetes.io/limit-rps: "20"
    # Limite per connessioni al minuto per IP
    nginx.ingress.kubernetes.io/limit-rpm: "300"
    # Numero massimo di connessioni simultanee per IP
    nginx.ingress.kubernetes.io/limit-connections: "10"
    # Dimensione burst (spike temporanei ammessi)
    nginx.ingress.kubernetes.io/limit-burst-multiplier: "5"
    # Whitelist IP esenti da rate limit (monitoring, CI/CD)
    nginx.ingress.kubernetes.io/limit-whitelist: "10.0.0.0/8,172.16.0.0/12"
spec:
  ingressClassName: nginx
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
                  number: 8080
```

!!! tip "Rate limit per URL specifica"
    Per applicare rate limit solo a endpoint sensibili (es. `/auth/login`) creare Ingress separati con lo stesso host: uno per `/auth/login` con rate limit, uno per il resto senza. I controller elaborano le regole in ordine di specificità.

### Autenticazione — Basic Auth e OAuth2

```yaml
# 1. Creare il file htpasswd e il Secret
# htpasswd -c auth admin  → inserisce la password interattivamente
# kubectl create secret generic basic-auth --from-file=auth -n production

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: protected-ingress
  namespace: production
  annotations:
    # Basic Auth
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: basic-auth   # nome del Secret
    nginx.ingress.kubernetes.io/auth-realm: "Area Riservata"
spec:
  ingressClassName: nginx
  rules:
    - host: admin.company.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-panel
                port:
                  number: 3000
```

```yaml
# OAuth2 Proxy — delega autenticazione a provider esterno (Google, GitHub, Okta)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: oauth-protected
  namespace: production
  annotations:
    # Redirect richieste non autenticate all'OAuth2 Proxy
    nginx.ingress.kubernetes.io/auth-url: "https://$host/oauth2/auth"
    nginx.ingress.kubernetes.io/auth-signin: "https://$host/oauth2/start?rd=$escaped_request_uri"
    nginx.ingress.kubernetes.io/auth-response-headers: "X-Auth-Request-User,X-Auth-Request-Email"
spec:
  ingressClassName: nginx
  rules:
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
          # OAuth2 Proxy gestisce il callback
          - path: /oauth2
            pathType: Prefix
            backend:
              service:
                name: oauth2-proxy
                port:
                  number: 4180
```

### Canary Deployments

```yaml
# Ingress principale — versione stabile (90% del traffico)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-stable
  namespace: production
spec:
  ingressClassName: nginx
  rules:
    - host: app.company.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app-v1
                port:
                  number: 80
---
# Ingress canary — versione nuova (10% del traffico)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-canary
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    # Strategia 1: peso percentuale
    nginx.ingress.kubernetes.io/canary-weight: "10"
    # Strategia 2 (alternativa): header specifico
    # nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
    # nginx.ingress.kubernetes.io/canary-by-header-value: "true"
    # Strategia 3 (alternativa): cookie
    # nginx.ingress.kubernetes.io/canary-by-cookie: "canary_user"
spec:
  ingressClassName: nginx
  rules:
    - host: app.company.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app-v2   # nuova versione
                port:
                  number: 80
```

!!! warning "Un solo canary Ingress per host"
    NGINX Ingress supporta un solo Ingress con `canary: "true"` per host+path. Per rollout più complessi (A/B testing multi-variante) valutare Argo Rollouts o Flagger che gestiscono automaticamente i pesi e le metriche.

### Traefik — Installazione e Configurazione

```bash
# Installazione Traefik via Helm
helm repo add traefik https://helm.traefik.io/traefik
helm repo update

helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace \
  --set ingressClass.enabled=true \
  --set ingressClass.isDefaultClass=false \
  --set ports.websecure.tls.enabled=true \
  --set deployment.replicas=2
```

```yaml
# IngressRoute (CRD Traefik) — più espressivo del Ingress standard
apiVersion: traefik.containo.us/v1alpha1
kind: IngressRoute
metadata:
  name: app-route
  namespace: production
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`api.company.com`) && PathPrefix(`/v1`)
      kind: Rule
      services:
        - name: api-v1
          port: 8080
      middlewares:
        - name: rate-limit
        - name: compress
    - match: Host(`app.company.com`)
      kind: Rule
      services:
        - name: frontend
          port: 80
  tls:
    certResolver: letsencrypt
---
# Middleware Traefik — rate limiting
apiVersion: traefik.containo.us/v1alpha1
kind: Middleware
metadata:
  name: rate-limit
  namespace: production
spec:
  rateLimit:
    average: 100
    burst: 200
    period: 1m
    sourceCriterion:
      ipStrategy:
        depth: 1
```

!!! tip "Traefik vs NGINX Ingress"
    Traefik usa CRD nativi (`IngressRoute`, `Middleware`) con configurazione più type-safe rispetto alle annotations NGINX. Supporta natively service discovery, circuit breaker, e dashboard web. NGINX Ingress è più maturo e ha una community più ampia; preferibile se si usa già nginx e si vuole il modello annotations-based standard K8s.

---

## Best Practices

**Sicurezza:**
- Abilitare sempre `ssl-redirect` e `force-ssl-redirect` — non lasciare mai HTTP esposto
- Usare `cert-manager` con Let's Encrypt per TLS automatico (no certificati gestiti manualmente)
- Applicare rate limiting su tutti gli endpoint pubblici, in particolare `/auth`, `/login`, `/register`
- Non esporre endpoint di admin su Ingress pubblici — usare Ingress separato su namespace dedicato con NetworkPolicy restrittive

**Performance:**
- Deployare il controller con minimo 2 repliche e anti-affinity per nodi diversi
- Abilitare HPA sull'Ingress Controller per gestire picchi di traffico
- Configurare `externalTrafficPolicy: Local` sul Service del controller se si ha bisogno del vero IP client (attenzione: richiede che il traffico arrivi al nodo corretto)
- Impostare timeout appropriati: `proxy-read-timeout`, `proxy-connect-timeout`, `proxy-send-timeout`

**Organizzazione:**
- Un Ingress per namespace/team — evita conflitti su regole e annotations
- Separare Ingress pubblici (internet-facing) da interni (intra-cluster o VPN-only) con classi diverse
- Usare `pathType: Exact` per endpoint API specifici, `Prefix` solo dove il routing generale è intenzionale
- Documentare ogni annotation non ovvia con un commento nel manifest

!!! warning "Limite dimensione corpo richiesta"
    Per default `proxy-body-size` è 1m. Upload di file, payload JSON grandi, o webhook con body voluminosi falliscono con `413 Request Entity Too Large`. Aumentare a livello di annotation sul singolo Ingress: `nginx.ingress.kubernetes.io/proxy-body-size: "50m"`.

---

## Troubleshooting

### Scenario 1: Ingress non raggiungibile — Timeout di connessione

**Sintomo:** `curl https://app.company.com` restituisce `Connection timed out` o `ERR_CONNECTION_TIMED_OUT`.

**Causa probabile:** l'Ingress Controller non ha un External IP, il Service è in `Pending`, o le porte firewall sono chiuse.

```bash
# Verifica External IP del controller
kubectl get service -n ingress-nginx ingress-nginx-controller
# Se EXTERNAL-IP è <pending> → problema con cloud LB provisioning

# Verifica evento sul Service
kubectl describe service -n ingress-nginx ingress-nginx-controller

# Verifica che il pod controller sia Running
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=50

# Test diretto al nodo (bypass LB) — usa NodePort se disponibile
kubectl get service -n ingress-nginx ingress-nginx-controller -o jsonpath='{.spec.ports}'
curl -v http://<NODE_IP>:<NODE_PORT>/healthz
```

### Scenario 2: 404 Not Found — Ingress non trova la regola

**Sintomo:** Il controller risponde ma tutte le richieste ritornano `404 default backend`.

**Causa probabile:** `ingressClassName` errato, namespace errato, o path non corrisponde.

```bash
# Verifica che l'Ingress esista nel namespace corretto
kubectl get ingress -A

# Verifica IngressClass
kubectl get ingressclass
kubectl describe ingress app-ingress -n production
# Controlla: "Events" — il controller ha processato l'Ingress?

# Verifica la ingressClassName
kubectl get ingress app-ingress -n production -o jsonpath='{.spec.ingressClassName}'

# Controlla i log del controller per vedere le regole caricate
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller | grep "app.company.com"

# Test manuale con header Host
curl -v -H "Host: app.company.com" http://<EXTERNAL-IP>/
```

### Scenario 3: 502 Bad Gateway — Il backend non risponde

**Sintomo:** L'Ingress riceve la richiesta ma ritorna `502 Bad Gateway`.

**Causa probabile:** il Service backend non ha endpoint attivi, il Pod è in crash, porta errata.

```bash
# Verifica che il Service esista e abbia endpoints
kubectl get service frontend -n production
kubectl get endpoints frontend -n production   # deve avere IP:porta, non "<none>"

# Se Endpoints è vuoto → label selector del Service non corrisponde ai Pod
kubectl describe service frontend -n production   # controlla Selector
kubectl get pods -n production --show-labels      # controlla i labels dei pod

# Test diretto al Service bypassando Ingress
kubectl run test-pod --image=curlimages/curl -it --rm -- \
  curl -v http://frontend.production.svc.cluster.local:80/

# Log del controller per l'errore specifico
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller \
  | grep -E "502|upstream|connect()"
```

### Scenario 4: TLS — Certificato non valido o scaduto

**Sintomo:** Browser mostra `NET::ERR_CERT_INVALID` o `ERR_CERT_DATE_INVALID`.

**Causa probabile:** Secret TLS non trovato, certificato nel Secret è scaduto, cert-manager non rinnova.

```bash
# Verifica che il Secret TLS esista nel namespace dell'Ingress
kubectl get secret company-tls-wildcard -n production
kubectl get secret company-tls-wildcard -n production \
  -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -dates

# Se usi cert-manager, verifica lo stato del Certificate
kubectl get certificate -n production
kubectl describe certificate company-tls-wildcard -n production
# Controlla "Conditions" e "Events" per errori ACME/Let's Encrypt

# Verifica CertificateRequest e Order
kubectl get certificaterequest -n production
kubectl get order -n production

# Forzare il rinnovo manuale (cert-manager)
kubectl annotate certificate company-tls-wildcard -n production \
  cert-manager.io/issuer-kind=ClusterIssuer  # no-op, forza riconciliazione
# oppure: eliminare il Secret (cert-manager lo ricrea)
kubectl delete secret company-tls-wildcard -n production
```

### Scenario 5: Rate Limit troppo aggressivo — 429 su traffico legittimo

**Sintomo:** Utenti ricevono `429 Too Many Requests` anche con traffico normale. Frequente dietro NAT (tutti gli utenti condividono un IP pubblico).

```bash
# Verifica le annotation di rate limit sull'Ingress
kubectl get ingress app-ingress -n production -o yaml | grep limit

# Controlla i log per vedere gli IP bloccati
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller \
  | grep "limiting requests"

# Soluzione: aumentare il limite o aggiungere whitelist
kubectl annotate ingress app-ingress -n production \
  nginx.ingress.kubernetes.io/limit-rps=100 --overwrite

# Se il problema è il NAT — usare X-Forwarded-For e configurare use-forwarded-headers
# Nel ConfigMap del controller:
kubectl edit configmap ingress-nginx-controller -n ingress-nginx
# Aggiungere: use-forwarded-headers: "true", compute-full-forwarded-for: "true"
```

---

## Relazioni

??? info "Kubernetes Networking — Contesto di rete"
    L'Ingress è uno dei pattern di accesso esterno ai Service. Comprendere Services (ClusterIP, NodePort, LoadBalancer) e come i Pod comunicano è prerequisito per configurare correttamente l'Ingress.

    **Approfondimento completo →** [Kubernetes Networking](networking.md)

??? info "Kubernetes Sicurezza — NetworkPolicy e TLS"
    Le NetworkPolicy devono essere configurate per permettere il traffico dall'Ingress Controller ai Pod backend. La gestione dei certificati TLS si integra con cert-manager e i Secret K8s.

    **Approfondimento completo →** [Kubernetes Sicurezza](sicurezza.md)

??? info "Kubernetes Workloads — Deployment dei backend"
    I Service esposti tramite Ingress sono solitamente frontend di Deployment o StatefulSet. Strategie di rolling update, canary e blue/green impattano direttamente sulla configurazione Ingress.

    **Approfondimento completo →** [Kubernetes Workloads](workloads.md)

---

## Riferimenti

- [Kubernetes Ingress — Documentazione ufficiale](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [NGINX Ingress Annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
- [Traefik Kubernetes Ingress](https://doc.traefik.io/traefik/providers/kubernetes-ingress/)
- [cert-manager — TLS automatico](https://cert-manager.io/docs/)
- [Kubernetes Gateway API — successore di Ingress](https://gateway-api.sigs.k8s.io/)
- [Canary Deployments con Argo Rollouts](https://argoproj.github.io/rollouts/)
