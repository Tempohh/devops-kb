---
title: "Network Policies"
slug: network-policies
category: networking
tags: [kubernetes, network-policy, sicurezza, firewall, microsegmentazione, calico, cilium]
search_keywords: [kubernetes network policy, pod firewall, default deny, ingress egress rules, namespace selector, pod selector, ipblock, calico network policy, cilium network policy, micro-segmentation, zero trust kubernetes, egress control, dns egress, multi-tenant kubernetes]
parent: networking/kubernetes/_index
related: [networking/kubernetes/cni, networking/kubernetes/ingress, networking/sicurezza/zero-trust, networking/sicurezza/firewall-waf]
official_docs: https://kubernetes.io/docs/concepts/services-networking/network-policies/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Network Policies

## Panoramica

Le Kubernetes Network Policies sono regole di firewall a livello di pod che controllano quale traffico TCP/UDP può fluire tra pod, namespace e indirizzi IP esterni. Per default, Kubernetes non applica nessuna restrizione di rete: tutti i pod possono comunicare con tutti gli altri. Le Network Policies cambiano questo comportamento implementando un modello **default-deny** per i pod selezionati.

!!! warning "Dipendenza dal CNI"
    Le Network Policies sono **definite** tramite risorse Kubernetes, ma **implementate** dal CNI plugin. Calico, Cilium e Weave supportano NetworkPolicy. **Flannel non le supporta** — installare Calico o Cilium se si ha bisogno di Network Policy enforcement.

## Prerequisiti

Questo argomento presuppone familiarità con:
- [CNI — Container Network Interface](cni.md) — le Network Policies sono definite in Kubernetes ma implementate dal CNI plugin (Flannel non le supporta)
- [Indirizzi IP e Subnetting](../fondamentali/indirizzi-ip-subnetting.md) — CIDR notation per ipBlock rules
- Kubernetes labels e selectors — le NetworkPolicy selezionano pod tramite matchLabels (documentazione non ancora presente in questa KB)

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

## Concetti Chiave

### Modello di Applicazione

Una NetworkPolicy seleziona pod tramite `podSelector` e definisce:
- **ingress rules**: chi può inviare traffico AI pod selezionati
- **egress rules**: verso dove i pod selezionati possono inviare traffico

!!! info "Default Behavior"
    - Pod **senza** NetworkPolicy che li seleziona: accettano tutto il traffico (nessuna restrizione)
    - Pod **con** NetworkPolicy: solo il traffico esplicitamente permesso è consentito
    - Regola "allow all" implicita se si specificano solo ingress rules (egress è non-selezionato = permit all)

### Selettori Disponibili

```yaml
# Seleziona pod per label
podSelector:
  matchLabels:
    app: frontend
    tier: web

# Seleziona namespace per label
namespaceSelector:
  matchLabels:
    environment: production

# Seleziona per IP/CIDR (per traffico esterno)
ipBlock:
  cidr: 10.0.0.0/8
  except:
    - 10.0.1.0/24  # Escludi questa subnet

# Porta
ports:
- protocol: TCP
  port: 8080
- protocol: UDP
  port: 53
```

## Pattern Principali

### 1. Default Deny — Blocca tutto

Il pattern fondamentale: seleziona tutti i pod del namespace e blocca tutto il traffico. Poi aggiungere regole permissive specifiche.

```yaml
# Blocca tutto il traffico in ingresso per i pod nel namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}   # {} = seleziona TUTTI i pod del namespace
  policyTypes:
  - Ingress

---
# Blocca tutto il traffico in uscita
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Egress
```

### 2. Permetti traffico tra pod con label specifiche

```yaml
# Il pod "api" può ricevere traffico solo da pod con label "app: frontend"
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-api
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api      # Policy applicata a questi pod

  policyTypes:
  - Ingress

  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend    # Permetti da questi pod

    ports:
    - protocol: TCP
      port: 8080
```

### 3. Permetti traffico tra namespace

```yaml
# Il namespace "monitoring" può accedere ai pod nel namespace "production"
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-monitoring
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api

  policyTypes:
  - Ingress

  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: monitoring   # Built-in label
      podSelector:
        matchLabels:
          app: prometheus   # AND logic: namespace monitoring E pod prometheus

    ports:
    - protocol: TCP
      port: 9090

---
# Esempio con OR logic: da namespace monitoring O da pod admin
  ingress:
  - from:
    - namespaceSelector:            # Voce 1: OR
        matchLabels:
          kubernetes.io/metadata.name: monitoring
    - podSelector:                  # Voce 2: OR
        matchLabels:
          app: admin-tool
```

!!! warning "AND vs OR nelle NetworkPolicy"
    All'interno di un singolo elemento della lista `from`:
    - `namespaceSelector` + `podSelector` nella stessa voce = **AND** (namespace E pod devono corrispondere)
    - `namespaceSelector` e `podSelector` come voci **separate** nella lista = **OR**

### 4. Egress — Controlla il traffico in uscita

```yaml
# Il pod "backend" può uscire solo verso il database e verso il DNS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend

  policyTypes:
  - Egress

  egress:
  # Permetti DNS (sempre necessario!)
  - ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP

  # Permetti verso il database (nel namespace database)
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: database
      podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432

  # Permetti verso il Redis cache
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

!!! warning "Egress e DNS"
    Se si applica una policy egress-deny, **blocca anche il DNS** (porta 53). Ricordarsi sempre di aggiungere una regola che permette il traffico UDP/TCP 53 verso kube-dns (`kube-system`).

### 5. Architettura Multi-Layer Completa

```yaml
# Namespace: production
#
# Frontend ──80──> API ──8080──> Backend ──5432──> Database (namespace: database)
#                   │                │
#                  443             9090
#                   │                │
#                 Ingress       Prometheus (namespace: monitoring)

---
# 1. Default deny tutto nel namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]

---
# 2. Frontend: riceve da Ingress Controller, esce verso API
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes: [Ingress, Egress]
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - port: 3000
  egress:
  - ports:        # DNS
    - port: 53
      protocol: UDP
  - to:
    - podSelector:
        matchLabels:
          app: api
    ports:
    - port: 8080

---
# 3. API: riceve da frontend, esce verso backend e Prometheus
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes: [Ingress, Egress]
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - port: 8080
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: monitoring
    ports:
    - port: 9090  # Metrics
  egress:
  - ports:
    - port: 53
      protocol: UDP
  - to:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - port: 8080
```

## Configurazione & Pratica

### Calico NetworkPolicy Estesa (CRD)

Calico offre CRD proprietari più potenti delle NetworkPolicy Kubernetes standard:

```yaml
# Calico GlobalNetworkPolicy — si applica a tutti i namespace
apiVersion: projectcalico.org/v3
kind: GlobalNetworkPolicy
metadata:
  name: deny-all-external-egress
spec:
  selector: all()
  order: 1000
  egress:
  # Permetti traffico interno al cluster
  - action: Allow
    destination:
      nets:
        - 10.0.0.0/8   # Cluster CIDR

  # Blocca tutto il resto
  - action: Deny

---
# Calico NetworkPolicy con Layer 7 (richiede Calico Enterprise)
# o Cilium per policy L7 open source
```

### Cilium NetworkPolicy L7

```yaml
# CiliumNetworkPolicy — supporta L7 (HTTP path, gRPC method)
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: api-l7-policy
  namespace: production
spec:
  endpointSelector:
    matchLabels:
      app: api

  ingress:
  - fromEndpoints:
    - matchLabels:
        app: frontend
    toPorts:
    - ports:
      - port: "8080"
        protocol: TCP
      rules:
        http:
        - method: GET
          path: "/api/v1/.*"      # Permette solo GET sulle route pubbliche
        - method: POST
          path: "/api/v1/users"   # Permette solo POST su /users
```

### Verifica e Debug

```bash
# Verifica NetworkPolicy applicate
kubectl get networkpolicies -n production
kubectl describe networkpolicy api-policy -n production

# Test connettività tra pod
kubectl exec -n production frontend-pod -- curl -s http://api-service:8080/health

# Test che la policy blocchi correttamente
kubectl exec -n production frontend-pod -- curl -s --connect-timeout 3 http://backend-service:8080
# Expected: Connection timed out (bloccato dalla policy)

# Con Cilium — visualizza policy enforcement
kubectl exec -n kube-system cilium-pod -- cilium endpoint list
kubectl exec -n kube-system cilium-pod -- cilium policy get

# Debug: flow log con Hubble
hubble observe --namespace production --verdict DROPPED
# Mostra tutti i pacchetti droppati dalle policy

# Con Calico — verifica policy
calicoctl get networkpolicies -n production
```

## Best Practices

- **Default-deny come punto di partenza**: applicare `default-deny-ingress` e `default-deny-egress` a ogni namespace e poi aggiungere eccezioni specifiche
- **Sempre allowlist il DNS**: dimenticare la porta 53/UDP rompe la risoluzione DNS e rende il sistema inutilizzabile
- **Label consistenti**: definire una convenzione di labeling stabile — `app`, `tier`, `environment` — usata sia per i pod che per i selettori
- **Testare prima di applicare**: in ambienti critici, testare le policy su un namespace di staging che replichi la produzione
- **Audit regolare**: rivedere periodicamente le policy — le applicazioni cambiano e le policy devono riflettere l'architettura attuale
- **Cilium per L7**: se si ha bisogno di policy a livello di path HTTP o metodo gRPC, usare Cilium NetworkPolicy (open source) invece delle policy Kubernetes standard (solo L3/L4)

## Troubleshooting

### Scenario 1 — Tutto il traffico bloccato dopo default-deny (DNS mancante)

**Sintomo:** Dopo aver applicato una policy `default-deny-egress`, i pod non riescono a risolvere i nomi DNS. Qualsiasi richiesta verso servizi interni fallisce con `name resolution failure` anche se la connessione diretta via IP funzionerebbe.

**Causa:** La policy egress blocca anche il traffico verso il kube-dns sulla porta 53 UDP/TCP. Senza DNS, i pod non riescono a raggiungere nessun servizio tramite hostname.

**Soluzione:** Aggiungere sempre una regola egress che permette la porta 53 prima di applicare default-deny. Verificare anche che `kube-system` non abbia un `namespaceSelector` che lo escluda.

```bash
# Verifica se il pod riesce a risolvere il DNS
kubectl exec -n production mypod -- nslookup kubernetes.default.svc.cluster.local

# Verifica le policy egress attive sul namespace
kubectl get networkpolicy -n production -o yaml | grep -A10 "egress"

# Applica la fix: aggiungi la regola DNS alla policy egress esistente
# Nel manifest aggiungere sotto egress:
# - ports:
#   - port: 53
#     protocol: UDP
#   - port: 53
#     protocol: TCP
kubectl apply -f backend-egress-with-dns.yaml
```

### Scenario 2 — NetworkPolicy definita ma non applicata (CNI incompatibile)

**Sintomo:** Si applica una NetworkPolicy senza errori (`kubectl apply` ha successo), ma il traffico che dovrebbe essere bloccato continua a passare indisturbato.

**Causa:** Il CNI plugin installato nel cluster non supporta l'enforcement delle NetworkPolicy. Flannel, in particolare, ignora completamente le NetworkPolicy — le risorse vengono create in etcd ma non producono nessuna regola di firewall reale.

**Soluzione:** Verificare il CNI in uso e, se necessario, migrare a Calico o Cilium che supportano le NetworkPolicy.

```bash
# Identifica il CNI installato
kubectl get pods -n kube-system | grep -E "calico|cilium|flannel|weave"
kubectl get daemonset -n kube-system

# Verifica se Calico è attivo e operativo
kubectl exec -n kube-system -l k8s-app=calico-node -- calico-node -version

# Con Cilium: verifica lo stato dell'enforcement
kubectl exec -n kube-system -l k8s-app=cilium -- cilium status
kubectl exec -n kube-system -l k8s-app=cilium -- cilium policy get
```

### Scenario 3 — AND vs OR errato nelle regole (label mismatch logico)

**Sintomo:** Una NetworkPolicy con `namespaceSelector` + `podSelector` nella stessa voce `from` non funziona come atteso: blocca traffico legittimo oppure permette traffico che dovrebbe essere bloccato.

**Causa:** Confusione tra logica AND (selettori nella stessa voce della lista) e OR (selettori come voci separate). Un singolo elemento con entrambi i selettori applica AND — entrambe le condizioni devono essere vere contemporaneamente.

**Soluzione:** Separare i selettori in voci distinte della lista `from` per ottenere OR, oppure mantenerli nella stessa voce per AND. Testare con netshoot prima di applicare in produzione.

```bash
# Test connettività con un pod temporaneo che simula le label del sorgente
kubectl run netshoot --image=nicolaka/netshoot -n monitoring \
  --labels="app=prometheus" --rm -it -- curl -v http://api-service.production:8080/health

# Verifica le label effettive di un pod (fonte di mismatch frequente)
kubectl get pod prometheus-0 -n monitoring -o jsonpath='{.metadata.labels}' | jq

# Verifica le label del namespace
kubectl get namespace monitoring --show-labels

# Debug flow con Hubble (Cilium)
hubble observe --namespace production --verdict DROPPED --follow
```

### Scenario 4 — Prometheus non raggiunge le metriche dei pod applicativi

**Sintomo:** Dopo aver abilitato default-deny nel namespace `production`, Prometheus non riesce a fare scraping delle metriche dei pod (`/metrics`). I target risultano DOWN nella UI di Prometheus.

**Causa:** La policy ingress sui pod applicativi non include una regola che permette il traffico in entrata dal namespace `monitoring`. Anche se Prometheus può uscire, i pod in `production` bloccano le sue connessioni entranti.

**Soluzione:** Aggiungere una regola `ingress` sui pod applicativi che permette traffico dalla porta di metriche (tipicamente 9090 o 8080) dal namespace `monitoring`.

```bash
# Verifica lo stato dei target Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Aprire http://localhost:9090/targets

# Testa manualmente la connessione dal namespace monitoring
kubectl run curl-test --image=curlimages/curl -n monitoring --rm -it \
  --labels="app=prometheus" -- curl -v http://api-pod-ip:9090/metrics

# Verifica tutte le ingress rules per i pod applicativi
kubectl describe networkpolicy -n production | grep -A20 "Allowing ingress"

# Applica la regola mancante
kubectl patch networkpolicy api-policy -n production --type='json' \
  -p='[{"op":"add","path":"/spec/ingress/-","value":{"from":[{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"monitoring"}}}],"ports":[{"port":9090,"protocol":"TCP"}]}}]'
```

## Relazioni

??? info "CNI — Implementazione delle Network Policy"
    Le NetworkPolicy sono implementate dal CNI — Calico e Cilium le supportano, Flannel no.

    **Approfondimento →** [CNI](cni.md)

??? info "Zero Trust — Principi di sicurezza"
    Le NetworkPolicy sono lo strumento Kubernetes per implementare Zero Trust.

    **Approfondimento →** [Zero Trust Networking](../sicurezza/zero-trust.md)

## Riferimenti

- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Network Policy Editor (visualizzatore)](https://editor.networkpolicy.io/)
- [Cilium Network Policy](https://docs.cilium.io/en/stable/security/policy/)
- [Calico Network Policy](https://docs.tigera.io/calico/latest/network-policy/)
