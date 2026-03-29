---
title: "Ingress e Ingress Controller"
slug: ingress
category: networking
tags: [kubernetes, ingress, nginx, traefik, tls, routing, cert-manager]
search_keywords: [kubernetes ingress, ingress controller, nginx ingress, traefik ingress, haproxy ingress, cert-manager, lets encrypt, tls termination, path based routing, host based routing, ingress class, gateway api, httproute, grpc route, kubernetes service, nodeport, clusterip, loadbalancer, external traffic]
parent: networking/kubernetes/_index
related: [networking/kubernetes/network-policies, networking/kubernetes/cni, networking/api-gateway/pattern-base, networking/load-balancing/layer4-vs-layer7]
official_docs: https://kubernetes.io/docs/concepts/services-networking/ingress/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Ingress e Ingress Controller

## Panoramica

Un **Ingress** in Kubernetes è una risorsa API che definisce regole per il routing del traffico HTTP/HTTPS esterno verso i servizi interni del cluster. Un **Ingress Controller** è il componente che implementa queste regole — è un reverse proxy (Nginx, Traefik, HAProxy) eseguito come pod nel cluster che legge le risorse Ingress e configura il proxy di conseguenza.

Senza Ingress, l'unico modo per esporre un servizio è tramite `Service.type=LoadBalancer` (1 IP pubblico per servizio, costoso) o `NodePort` (porta alta, non adatta alla produzione). Con Ingress, un singolo IP pubblico espone decine di servizi tramite routing per hostname e path.

## Concetti Chiave

### Tipi di Service Kubernetes

| Type | Esposizione | Uso |
|------|-------------|-----|
| `ClusterIP` | Solo interno al cluster | Comunicazione inter-servizio |
| `NodePort` | Porta sul nodo (30000-32767) | Debug/dev, non produzione |
| `LoadBalancer` | IP pubblico cloud | 1 IP per servizio, costoso |
| `ExternalName` | CNAME DNS | Alias verso servizi esterni |

**Ingress** usa `ClusterIP` internamente e fornisce un singolo `LoadBalancer` per l'Ingress Controller.

### Ingress vs Gateway API

Kubernetes ha due API per il routing HTTP:
- **Ingress** (stabile, ampiamente supportato): semplice, limitato — funziona per la maggior parte dei casi
- **Gateway API** (più nuovo, in GA da Kubernetes 1.28): più espressivo, supporta protocolli multipli (gRPC, TCP), gestione basata su ruoli — la direzione futura

## Architettura / Come Funziona

```
Internet
    │ (porta 80/443)
    ▼
Cloud Load Balancer (AWS ALB / Azure LB)
    │
    ▼
Service: ingress-nginx-controller (LoadBalancer)
    │
    ▼
Pod: nginx-ingress-controller
    │  Legge regole Ingress dall'API server
    ├── Host: app1.example.com → Service: app1-svc:80
    ├── Host: app2.example.com → Service: app2-svc:80
    └── Path: /api → Service: api-svc:8080

    ▼
Services (ClusterIP) → Pods
```

### TLS Termination Flow

```
Client ──[TLS]──> Ingress Controller ──[HTTP]──> Backend Service
                      ↑
             Termina TLS qui
             Usa certificato dal Secret TLS
```

## Configurazione & Pratica

### Installazione Nginx Ingress Controller

```bash
# Con Helm (raccomandato)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set controller.resources.requests.cpu=100m \
  --set controller.resources.requests.memory=128Mi

# Verifica
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx
# Output: ingress-nginx-controller   LoadBalancer   10.96.x.x   <EXTERNAL-IP>   80:30xxx/TCP,443:30xxx/TCP
```

### Ingress Base — Path e Host Routing

```yaml
# ingress-basic.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  namespace: production
  annotations:
    # Rewrite: /api/users → /users (rimuove il prefix /api)
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx  # Specifica quale Ingress Controller usare

  rules:
  # Host-based routing
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80

  - host: api.example.com
    http:
      paths:
      # Path-based routing
      - path: /api/v1/users(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: user-service
            port:
              number: 8080

      - path: /api/v1/orders(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: order-service
            port:
              number: 8080
```

### TLS con cert-manager e Let's Encrypt

```bash
# Installa cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true
```

```yaml
# cluster-issuer.yaml — Configurazione Let's Encrypt
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
        ingress:
          ingressClassName: nginx

---
# ingress-tls.yaml — Ingress con TLS automatico
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: secure-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - app.example.com
    - api.example.com
    secretName: example-tls  # cert-manager crea questo Secret automaticamente

  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

### Annotazioni Nginx Ingress Avanzate

```yaml
metadata:
  annotations:
    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "100"
    nginx.ingress.kubernetes.io/limit-connections: "20"

    # Autenticazione Basic Auth
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: basic-auth-secret
    nginx.ingress.kubernetes.io/auth-realm: "Authentication Required"

    # Autenticazione OAuth2 (con oauth2-proxy)
    nginx.ingress.kubernetes.io/auth-url: "http://oauth2-proxy.auth.svc/oauth2/auth"
    nginx.ingress.kubernetes.io/auth-signin: "https://auth.example.com/oauth2/start"

    # Whitelist IP
    nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,192.168.0.0/16"

    # Timeout custom
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"

    # WebSocket
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"

    # CORS
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.example.com"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE, OPTIONS"

    # gRPC backend
    nginx.ingress.kubernetes.io/backend-protocol: "GRPC"
```

### Gateway API (Kubernetes 1.28+ GA)

```yaml
# GatewayClass — definisce il tipo di gateway
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: nginx
spec:
  controllerName: k8s.nginx.org/nginx-gateway-controller

---
# Gateway — istanza del gateway con listener
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: main-gateway
spec:
  gatewayClassName: nginx
  listeners:
  - name: https
    port: 443
    protocol: HTTPS
    tls:
      certificateRefs:
      - name: example-tls

---
# HTTPRoute — regole di routing
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
spec:
  parentRefs:
  - name: main-gateway
  hostnames:
    - api.example.com
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v1/users
    backendRefs:
    - name: user-service
      port: 8080
      weight: 90     # 90% del traffico (canary)
    - name: user-service-v2
      port: 8080
      weight: 10     # 10% del traffico
```

## Best Practices

- **IngressClass esplicita**: specificare sempre `spec.ingressClassName` — evita ambiguità in cluster con più Ingress Controller
- **cert-manager per TLS**: automatizzare completamente il ciclo di vita dei certificati — non gestirli manualmente
- **2+ repliche dell'Ingress Controller**: il controller è un componente critico — deve avere alta disponibilità
- **Resource requests e limits**: il pod nginx-ingress deve avere limits definiti per evitare che consumi tutto il CPU in caso di spike
- **`ssl-redirect: "true"` sempre**: forzare HTTPS in produzione
- **Monitorare le metriche Nginx**: l'Ingress Controller espone metriche Prometheus — configurare alert su error rate e latenza
- **Gateway API per nuovi cluster**: se si parte da zero su Kubernetes 1.28+, preferire Gateway API per la sua flessibilità futura

## Troubleshooting

### Scenario 1 — 404 su path configurato correttamente

**Sintomo:** Le richieste a un path definito nell'Ingress restituiscono `404 Not Found` anche se il service backend è attivo.

**Causa:** `ingressClassName` mancante o sbagliata, oppure il controller non ha recepito la risorsa Ingress. Con più Ingress Controller nel cluster, un Ingress senza IngressClass viene ignorato da tutti.

**Soluzione:** Verificare che `spec.ingressClassName` corrisponda al controller installato e controllare gli eventi della risorsa.

```bash
kubectl describe ingress my-ingress -n production
# Controllare il campo "Class" e la sezione "Events"

kubectl get ingressclass
# Lista le IngressClass disponibili nel cluster

kubectl get events -n production --field-selector reason=Sync
# Events emessi dal controller durante la sincronizzazione
```

---

### Scenario 2 — 502 Bad Gateway

**Sintomo:** L'Ingress risponde `502 Bad Gateway` per uno o più path.

**Causa:** Il Service backend non ha endpoint attivi — i pod sono in CrashLoop, non hanno superato il readiness probe, oppure il Service seleziona label sbagliate.

**Soluzione:** Verificare che gli endpoint del Service siano popolati e che i pod siano in Running/Ready.

```bash
kubectl get endpoints <service-name> -n production
# Se "Endpoints: <none>" il Service non trova pod matching

kubectl get pods -n production -l app=my-app
# Verifica stato pod

kubectl describe pod <pod-name> -n production
# Controllare eventi e readiness probe failures

# Log del controller per dettagli sull'errore upstream
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50 | grep "502\|upstream"
```

---

### Scenario 3 — Certificato TLS non generato o scaduto

**Sintomo:** Il browser mostra "Connessione non sicura" o il certificato è scaduto/autofirmato nonostante cert-manager sia installato.

**Causa:** cert-manager non riesce a completare la challenge ACME (HTTP-01 o DNS-01), oppure la `ClusterIssuer` non è configurata correttamente, oppure manca l'annotazione `cert-manager.io/cluster-issuer` nell'Ingress.

**Soluzione:** Ispezionare la catena di risorse cert-manager: Certificate → CertificateRequest → Order → Challenge.

```bash
kubectl get certificate -n production
# Verificare colonna "READY" — deve essere True

kubectl describe certificate example-tls -n production
# Sezione "Events" mostra il motivo del fallimento

kubectl describe certificaterequest -n production
# Dettagli sulla richiesta verso Let's Encrypt

kubectl get challenges -n production
# Challenge in pending = problema di raggiungibilità HTTP-01

# Verifica annotazione nell'Ingress
kubectl get ingress my-ingress -n production -o yaml | grep cert-manager
```

---

### Scenario 4 — ERR_TOO_MANY_REDIRECTS (loop HTTP↔HTTPS)

**Sintomo:** Il browser va in loop di redirect e mostra `ERR_TOO_MANY_REDIRECTS`. Il problema si verifica tipicamente dopo aver abilitato `ssl-redirect`.

**Causa:** Il load balancer termina TLS e passa traffico HTTP al controller senza il header `X-Forwarded-Proto: https`. Il controller vede HTTP e continua a fare redirect verso HTTPS all'infinito.

**Soluzione:** Configurare il controller per fidarsi dell'header `X-Forwarded-Proto` dal load balancer, oppure usare `use-forwarded-headers: "true"` nella ConfigMap.

```bash
# Verifica header ricevuti dal controller
kubectl exec -n ingress-nginx <nginx-pod> -- curl -sI http://localhost/healthz

# Abilita proxy headers nella ConfigMap del controller
kubectl edit configmap ingress-nginx-controller -n ingress-nginx
# Aggiungere: use-forwarded-headers: "true"
#             compute-full-forwarded-for: "true"

# Oppure, per Ingress specifico, disabilitare ssl-redirect se il LB gestisce già TLS
kubectl annotate ingress my-ingress -n production \
  nginx.ingress.kubernetes.io/ssl-redirect="false"

# Verifica configurazione nginx generata
kubectl exec -n ingress-nginx <nginx-pod> -- nginx -T | grep -A3 "ssl_redirect"
```

## Relazioni

??? info "cert-manager — Gestione Automatica TLS"
    cert-manager integra Let's Encrypt per il rinnovo automatico dei certificati.

    **Approfondimento →** [TLS/SSL Basics](../../networking/fondamentali/tls-ssl-basics.md)

??? info "Network Policies — Sicurezza inter-pod"
    Limitare il traffico verso i pod dell'Ingress Controller.

    **Approfondimento →** [Network Policies](network-policies.md)

## Riferimenti

- [Kubernetes Ingress Documentation](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)
