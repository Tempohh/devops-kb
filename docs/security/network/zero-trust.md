---
title: "Zero Trust Architecture"
slug: zero-trust
category: security
tags: [zero-trust, micro-segmentation, beyondcorp, service-mesh, network-security, mtls, identity]
search_keywords: [zero trust architecture, never trust always verify, zero trust network access ztna, beyondcorp google, nist 800-207, micro-segmentation, software defined perimeter sdp, identity centric security, continuous verification, least privilege access, zero trust workloads, zero trust kubernetes, istio zero trust, cilium network policy, network microsegmentation, zero trust cloud, implicit trust, perimeter security obsolete, east west traffic security, lateral movement prevention, policy enforcement point pep, policy decision point pdp, zero trust maturity model, cisa zero trust, bnd modello zero trust, conditional access zero trust, sase secure access service edge]
parent: security/network/_index
related: [security/autenticazione/mtls-spiffe, security/autorizzazione/opa, security/pki-certificati/pki-interna, security/autorizzazione/rbac-abac-rebac, security/supply-chain/admission-control, networking/sicurezza/zero-trust]
official_docs: https://csrc.nist.gov/publications/detail/sp/800-207/final
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Zero Trust Architecture

## Panoramica

**Zero Trust** è un modello di sicurezza fondato sul principio **"never trust, always verify"** — nessuna richiesta, nessun utente, nessun servizio è considerato fidato per il solo fatto di trovarsi nella rete interna. Ogni accesso deve essere autenticato, autorizzato e continuamente validato, indipendentemente dall'origine.

Il modello nasce dal riconoscimento che il perimetro di rete tradizionale (firewall, VPN, DMZ) è diventato obsoleto: i carichi di lavoro sono distribuiti su cloud pubblici, edge, datacenter on-premise e dispositivi mobili. Una volta che un attaccante supera il perimetro — o che un account interno viene compromesso — il modello perimétrico non offre alcun controllo sull'**east-west traffic** (comunicazione tra servizi interni).

**Il problema che Zero Trust risolve**: nei modelli tradizionali, la rete interna è implicita "zona di fiducia". Un servizio compromesso può muoversi lateralmente senza ostacoli. In un'architettura Zero Trust, ogni hop è autenticato e autorizzato — il movimento laterale è strutturalmente ostacolato.

**Origini e standard di riferimento:**
- **BeyondCorp** (Google, 2014): primo caso d'uso enterprise documentato — accesso alle applicazioni interne senza VPN, basato sull'identità del dispositivo e dell'utente
- **NIST SP 800-207** (2020): definizione formale dei principi Zero Trust e dell'architettura di riferimento
- **CISA Zero Trust Maturity Model**: guida alla progressione per le organizzazioni federali USA, applicabile al settore enterprise

!!! warning "Zero Trust non è un prodotto"
    Zero Trust è un **principio architetturale**, non un tool da installare. Non esiste un singolo prodotto che "implementa Zero Trust". L'implementazione richiede la combinazione di identity, network policy, policy engine, monitoring e cultura operativa.

---

## Concetti Chiave

### I Sette Principi NIST SP 800-207

1. **Tutte le sorgenti dati e i servizi computazionali sono considerate risorse** — dispositivi BYOD, IoT, API, storage sono risorse che richiedono protezione.
2. **Tutta la comunicazione è sicura indipendentemente dall'ubicazione della rete** — non esiste differenza tra traffico interno e esterno.
3. **L'accesso alle singole risorse viene concesso per singola sessione** — nessun accesso permanente; ogni sessione richiede autorizzazione.
4. **L'accesso alle risorse è determinato da policy dinamica** — considera identità, stato del dispositivo, behavioral analytics.
5. **Tutti i dispositivi sono monitorati e verificati quanto a integrità e postura di sicurezza**.
6. **L'autenticazione e l'autorizzazione sono dinamiche e rigidamente imposte prima dell'accesso**.
7. **L'organizzazione raccoglie dati sullo stato della rete, dell'identità e dei workload per migliorare la postura di sicurezza**.

### Policy Enforcement Point e Policy Decision Point

```
                    ┌──────────────────────┐
                    │  Policy Admin Point  │
                    │  (orchestrazione)    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Policy Decision     │◄── Identity Provider
                    │  Point (PDP)         │◄── Device Posture DB
                    │  (es. OPA, Envoy     │◄── Threat Intelligence
                    │   RBAC, Gatekeeper)  │◄── Behavioral Analytics
                    └──────────┬───────────┘
                               │ allow / deny + context
              ┌────────────────▼──────────────────────┐
              │         Policy Enforcement             │
              │         Point (PEP)                    │
              │  (es. API Gateway, Envoy sidecar,      │
              │   Kubernetes Network Policy, WAF)      │
              └────────────────┬──────────────────────┘
                               │ (solo se autorizzato)
                    ┌──────────▼───────────┐
                    │      Risorsa /       │
                    │      Servizio        │
                    └──────────────────────┘
```

**PDP** (Policy Decision Point): decide se concedere l'accesso sulla base delle policy e del contesto.
**PEP** (Policy Enforcement Point): impone la decisione del PDP intercettando il traffico.

### Micro-segmentazione

La micro-segmentazione divide la rete in segmenti logici minimi — idealmente uno per workload — e definisce policy esplicite per ogni copie sorgente/destinazione. In Kubernetes si implementa con:

- **Network Policy** (layer 3/4): restrizioni basate su IP, porta, namespace, label
- **Cilium** (layer 7): policy basate su HTTP method, path, gRPC, DNS
- **Service Mesh** (Istio/Linkerd): AuthorizationPolicy a livello applicativo con identità SPIFFE

---

## Architettura / Come Funziona

### Modello Zero Trust in Kubernetes

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    Cluster Kubernetes                           │
  │                                                                 │
  │  ┌───────────────┐    mTLS (SPIFFE)    ┌───────────────────┐   │
  │  │  Namespace A  │◄──────────────────►│  Namespace B      │   │
  │  │  service-a    │    AuthzPolicy      │  service-b        │   │
  │  │  ──────────── │   (Istio/OPA)       │  ────────────────  │   │
  │  │  SVID: ns/a/  │                    │  SVID: ns/b/      │   │
  │  │  sa/svc-a     │                    │  sa/svc-b         │   │
  │  └───────┬───────┘                    └────────┬──────────┘   │
  │          │                                     │               │
  │          │     ┌───────────────────────┐       │               │
  │          └─────►   Envoy Sidecar (PEP) ◄───────┘               │
  │                │   - verifica mTLS     │                        │
  │                │   - consulta OPA(PDP) │                        │
  │                │   - enforce AuthzPol  │                        │
  │                └───────────┬───────────┘                        │
  │                            │                                    │
  │                    ┌───────▼───────┐                            │
  │                    │  SPIRE Server │                            │
  │                    │  (identità    │                            │
  │                    │   workload)   │                            │
  │                    └───────────────┘                            │
  │                                                                 │
  │  Network Policy (Cilium/Calico): default-deny + regole minime  │
  └─────────────────────────────────────────────────────────────────┘
```

### Flusso di Autorizzazione Completo

Ogni richiesta da `service-a` a `service-b` segue questo flusso:

1. **Identità**: `service-a` presenta il suo SVID (certificato X.509 SPIFFE) all'handshake mTLS
2. **Autenticazione**: `service-b` (via Envoy sidecar) verifica il certificato contro la CA SPIFFE
3. **Autorizzazione**: il sidecar chiede all'Authorization Policy (Istio) o a OPA se `spiffe://cluster/ns/a/sa/svc-a` può fare `GET /api/orders`
4. **Decisione**: allow/deny con eventuale logging
5. **Enforcement**: la richiesta passa o viene bloccata con 403

Tutto questo senza che `service-b` debba implementare logica di autenticazione nel codice applicativo.

### BeyondCorp — Zero Trust per l'Accesso Umano

Il modello BeyondCorp si applica all'accesso degli utenti alle applicazioni interne:

```
  Utente (browser)
       │
       │ HTTPS
       ▼
  Access Proxy (PEP)
  ├── verifica identità utente (SSO/OIDC)
  ├── verifica postura dispositivo (MDM, cert device)
  ├── consulta Access Control Engine (PDP)
  │   ├── gruppo AD / claim JWT
  │   ├── device trust level
  │   ├── ora del giorno, geo-location
  │   └── risk score comportamentale
  └── proxy verso applicazione interna (solo se allow)

  Applicazione interna: non esposta su rete, raggiungibile solo via proxy
```

**Implementazioni cloud:**
- **Google BeyondCorp Enterprise** / **IAP (Identity-Aware Proxy)**
- **AWS Verified Access** (valuta identità + postura prima di dare accesso)
- **Azure AD Conditional Access** + Application Proxy
- **Cloudflare Access** (SASE)
- **Zscaler ZPA** (Zero Trust Network Access)

---

## Configurazione & Pratica

### 1. Network Policy Kubernetes — Default Deny

Il punto di partenza: isolare ogni namespace con una default-deny policy, poi aprire solo i flussi necessari.

```yaml
# default-deny-all.yaml — Applica a ogni namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}       # seleziona tutti i pod del namespace
  policyTypes:
    - Ingress
    - Egress
  # Nessuna regola ingress/egress = tutto bloccato
---
# Permetti DNS (necessario per la resolution dei service)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
```

```yaml
# allow-service-a-to-service-b.yaml
# Permette solo service-a di chiamare service-b sulla porta 8080
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-service-a-ingress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: service-b
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: service-a
          namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: production
      ports:
        - port: 8080
          protocol: TCP
```

### 2. Istio AuthorizationPolicy — Zero Trust mTLS

Con Istio, si impone mTLS STRICT e si definiscono policy di autorizzazione granulari.

```yaml
# peer-authentication-strict.yaml
# Impone mTLS su tutto il namespace — nessuna connessione plaintext
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default-mtls-strict
  namespace: production
spec:
  mtls:
    mode: STRICT   # rifiuta connessioni non-mTLS
```

```yaml
# authorizationpolicy-orders.yaml
# Solo service-frontend (con identità SPIFFE verificata) può chiamare
# il metodo GET su /api/orders del service-orders
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: orders-service-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: orders
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              # SPIFFE ID del chiamante autorizzato
              - "cluster.local/ns/production/sa/frontend"
      to:
        - operation:
            methods: ["GET"]
            paths: ["/api/orders", "/api/orders/*"]
    - from:
        - source:
            principals:
              - "cluster.local/ns/production/sa/billing"
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/orders/*/confirm"]
```

```yaml
# deny-all-baseline.yaml
# Policy di default: nega tutto ciò che non è esplicitamente permesso
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: production
spec:
  {}   # selector vuoto = si applica a tutti i workload
  # action: DENY è il default quando non ci sono rules
```

### 3. Cilium — Network Policy Layer 7

Cilium permette policy più granulari che includono layer applicativo (HTTP, DNS, Kafka).

```yaml
# cilium-policy-orders.yaml
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: orders-l7-policy
  namespace: production
spec:
  endpointSelector:
    matchLabels:
      app: orders
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
              # Solo GET su /api/orders è permesso da frontend
              - method: "GET"
                path: "^/api/orders(/.*)?$"
    - fromEndpoints:
        - matchLabels:
            app: billing
      toPorts:
        - ports:
            - port: "8080"
              protocol: TCP
          rules:
            http:
              - method: "GET"
                path: "^/api/orders/[^/]+$"
              - method: "POST"
                path: "^/api/orders/[^/]+/confirm$"
  egress:
    # orders può chiamare solo il database e vault
    - toEndpoints:
        - matchLabels:
            app: postgres
      toPorts:
        - ports:
            - port: "5432"
    - toEndpoints:
        - matchLabels:
            app: vault
      toPorts:
        - ports:
            - port: "8200"
```

### 4. Verifica della Postura Zero Trust

```bash
# Verifica che mTLS STRICT sia attivo su tutti i workload
istioctl x check-inject -n production

# Analizza la configurazione di autenticazione
istioctl authn tls-check <pod-name>.<namespace>

# Verifica le AuthorizationPolicy applicate a un servizio
istioctl x authz check <pod-name>.<namespace>

# Test di connettività tra pod — dovrebbe fallire se non autorizzato
kubectl exec -it -n production deploy/service-c -- \
  curl -sv http://orders:8080/api/orders
# Atteso: RBAC: access denied (403)

# Verifica Network Policy con cilium
kubectl exec -n kube-system ds/cilium -- \
  cilium policy get

# Controlla i flussi di rete effettivi
kubectl exec -n kube-system ds/cilium -- \
  cilium monitor --type drop
```

---

## Best Practices

!!! tip "Inizia da Observe, non da Enforce"
    Prima di impostare `STRICT` o `DENY`, usa la modalità **permissiva/audit** (Istio `PERMISSIVE`, OPA `dry-run`, Cilium `audit`) per osservare il traffico reale senza interrompere i servizi. Mappa i flussi legittimiprima di bloccare quelli non autorizzati.

**Principi operativi:**

1. **Default deny, explicit allow**: le policy devono bloccare tutto per default e aprire solo i flussi documentati e approvati. Questo vale per network policy, RBAC e service mesh.

2. **Identità strong, non IP-based**: le IP cambiano in ambienti dinamici. Usare SPIFFE ID, certificati X.509 o JWT come fonte di identità — mai IP sorgente come meccanismo di autenticazione.

3. **Least privilege per workload**: ogni service account ha accesso solo alle risorse che usa effettivamente. Vietare l'uso del service account `default` — creare account dedicati per ogni servizio.

4. **Separazione del piano di controllo**: il PDP (OPA, Istio istiod, SPIRE server) deve essere protetto e altamente disponibile — è il componente critico dell'intera architettura.

5. **Continuous verification**: non basta autenticare una volta per sessione. Implementare refresh frequente dei token/certificati (TTL breve) e revocare accessi in real-time in caso di compromissione.

6. **Log di tutti i deny**: ogni richiesta negata è un segnale di sicurezza. Raccogliere e analizzare i deny log per identificare tentativi di movimento laterale o configurazioni errate.

!!! warning "mTLS STRICT può rompere la comunicazione con sistemi legacy"
    Prima di attivare `PeerAuthentication: STRICT` su un namespace, verificare che tutti i servizi abbiano sidecar Envoy iniettato. I servizi senza sidecar (es. job batch, DaemonSet di infra) non possono fare mTLS e verranno bloccati. Usare namespace separati o esclusioni esplicite per questi casi.

---

## Troubleshooting

### 1. Servizio bloccato con RBAC: access denied

**Sintomo**: `curl: (22) The requested URL returned error: 403 RBAC: access denied`

**Causa**: AuthorizationPolicy di Istio non copre il chiamante o l'operazione richiesta.

```bash
# Identifica la policy che blocca
istioctl x authz check <pod-name>.<namespace> \
  --header "x-forwarded-client-cert: ..."

# Visualizza le policy attive sul workload target
kubectl get authorizationpolicy -n production -o yaml

# Controlla il SPIFFE ID effettivo del chiamante
istioctl proxy-config secret <pod-name>.<namespace> | grep spiffe

# Log Envoy del pod target per vedere il deny dettagliato
kubectl logs <pod-name> -n production -c istio-proxy | \
  grep "RBAC\|deny\|403" | tail -20
```

**Soluzione**: aggiungere il principal SPIFFE del chiamante alla AuthorizationPolicy, o creare una nuova policy `ALLOW` per il flusso necessario.

---

### 2. Network Policy blocca traffico inaspettato

**Sintomo**: i pod non si raggiungono ma non ci sono errori Istio — timeout o connection refused.

**Causa**: una NetworkPolicy blocca il traffico prima che arrivi all'Envoy sidecar.

```bash
# Testa la connettività raw (bypass Istio)
kubectl exec -it -n production <source-pod> -- \
  nc -zv <target-service> <port>
# Se fallisce: è un problema di NetworkPolicy, non di Istio

# Lista tutte le NetworkPolicy nel namespace
kubectl get networkpolicy -n production -o wide

# Descrivi la policy specifica per vedere le regole
kubectl describe networkpolicy <policy-name> -n production

# Con Cilium: identifica i drop a livello di rete
kubectl exec -n kube-system ds/cilium -- \
  cilium monitor --type drop 2>&1 | head -50
```

**Soluzione**: aggiungere una regola ingress/egress nella NetworkPolicy che permetta il flusso legittimo. Verificare che i `podSelector` e `namespaceSelector` usino le label corrette.

---

### 3. mTLS STRICT blocca health check del kubelet

**Sintomo**: i pod risultano `Unhealthy` e vengono restartati anche se l'applicazione funziona. Il liveness/readiness probe fallisce con connection refused.

**Causa**: il kubelet non usa mTLS, quindi viene bloccato dalla PeerAuthentication STRICT.

```yaml
# Soluzione: escludere la porta del probe dalla policy mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default-mtls-strict
  namespace: production
spec:
  mtls:
    mode: STRICT
  portLevelMtls:
    # Porta del health check: esclusa da mTLS
    "15021":     # porta Istio health check
      mode: DISABLE
    "8081":      # porta app health (adattare al proprio servizio)
      mode: DISABLE
```

---

### 4. OPA nega richieste legittime dopo aggiornamento policy

**Sintomo**: dopo il deploy di una nuova policy Rego, alcune operazioni legittime tornano 403.

**Causa**: la policy Rego ha un bug logico o manca un caso d'uso.

```bash
# Test della policy in isolamento con OPA CLI
cat > input.json << 'EOF'
{
  "user": "svc-orders",
  "action": "GET",
  "resource": "/api/payments/123",
  "token": { "sub": "svc-orders", "groups": ["services"] }
}
EOF

opa eval -d policy.rego -i input.json "data.authz.allow"
# Expected: {"result": true}

# Dry-run della policy su OPA in produzione
curl -X POST http://opa:8181/v1/data/authz/allow \
  -H "Content-Type: application/json" \
  -d @input.json

# Abilita decision log su OPA per vedere i deny in dettaglio
# Nel config OPA:
# decision_logs:
#   console: true
kubectl logs -n security deploy/opa | grep '"result":false' | tail -20
```

**Soluzione**: correggere la logica Rego nel caso mancante. Usare `opa test` per aggiungere un test case che copra lo scenario.

---

### 5. SPIRE non rilascia SVID al workload

**Sintomo**: il pod non riesce ad ottenere il certificato SPIFFE — nel log Envoy: `failed to load certificate and key`.

**Causa**: la SPIRE Registration Entry non corrisponde al service account o namespace del workload.

```bash
# Verifica le entry registrate in SPIRE per il namespace
kubectl exec -n spire deploy/spire-server -- \
  spire-server entry show -selector k8s:ns:production

# Controlla il log dello SPIRE agent sul nodo
kubectl logs -n spire daemonset/spire-agent | grep "error\|attestation"

# Verifica la connessione Workload API
kubectl exec -n production <pod-name> -- \
  /opt/spire/bin/spire-agent api fetch x509

# Re-registra il workload se l'entry manca
kubectl exec -n spire deploy/spire-server -- \
  spire-server entry create \
    -spiffeID spiffe://cluster.local/ns/production/sa/orders \
    -parentID spiffe://cluster.local/spire/agent/k8s_psat/... \
    -selector k8s:ns:production \
    -selector k8s:sa:orders
```

---

## Relazioni

Zero Trust è un principio trasversale che coinvolge molteplici componenti della KB:

??? info "mTLS e SPIFFE/SPIRE — Fondamento dell'Identità Workload"
    SPIFFE/SPIRE fornisce l'identità crittografica dei workload (SVID) che è il prerequisito per implementare Zero Trust a livello di servizi. Senza identità strong, non si può implementare "never trust".

    **Approfondimento completo →** [mTLS e SPIFFE/SPIRE](../autenticazione/mtls-spiffe.md)

??? info "OPA — Policy Engine per il PDP"
    OPA funge da Policy Decision Point in un'architettura Zero Trust: riceve il contesto della richiesta (chi, cosa, su quale risorsa) e restituisce allow/deny basandosi su policy Rego dichiarative.

    **Approfondimento completo →** [OPA — Open Policy Agent](../autorizzazione/opa.md)

??? info "PKI Interna — Radice di Fiducia"
    La PKI interna è la radice di fiducia crittografica su cui si basa Zero Trust: le CA interne firmano i certificati SPIFFE, i certificati TLS dei servizi e le identità dei dispositivi.

    **Approfondimento completo →** [PKI Interna](../pki-certificati/pki-interna.md)

??? info "Admission Control — Zero Trust al Deploy"
    Le policy di Admission Control (Kyverno, OPA Gatekeeper) garantiscono che solo workload conformi — con i label corretti, senza privilegi eccessivi, con le annotation SPIFFE — possano essere deployati nel cluster.

    **Approfondimento completo →** [Admission Control](../supply-chain/admission-control.md)

??? info "Zero Trust Networking — ZTNA per Utenti e Roadmap di Migrazione"
    Questo file copre Zero Trust dal punto di vista dei workload Kubernetes. Per l'implementazione dal punto di vista di rete e accesso utente — ZTNA con Cloudflare Access, IAP, device posture, e roadmap di migrazione da VPN a Zero Trust — vedi il file complementare nella sezione networking.

    **Approfondimento →** [Zero Trust Networking](../../networking/sicurezza/zero-trust.md)

---

## Maturità Zero Trust — Modello a Livelli

Il CISA Zero Trust Maturity Model definisce 5 aree e 3 livelli di maturità:

| Area | Tradizionale | Avanzato | Ottimale |
|------|-------------|---------|---------|
| **Identità** | Password statiche, MFA parziale | MFA ovunque, IdP centralizzato | Continua rivalutazione del rischio, passwordless |
| **Dispositivi** | Inventario manuale | MDM con compliance check | Attestazione automatica, postura in tempo reale |
| **Reti** | Perimetro flat, VPN | Micro-segmentazione namespace | Policy layer 7 per flusso, default deny assoluto |
| **Applicazioni** | Auth applicativa variabile | SSO centralizzato, mTLS M2M | Autorizzazione per sessione, SPIFFE identity |
| **Dati** | Cifratura at rest | Cifratura + DLP base | Accesso data-centric con attributi utente+dispositivo |

**In Kubernetes**, un'organizzazione "Avanzato" ha tipicamente:
- Default-deny NetworkPolicy su tutti i namespace
- mTLS PERMISSIVE o STRICT via service mesh
- SPIFFE/SPIRE per identità workload
- OPA o Kyverno per policy as code

Un'organizzazione "Ottimale" ha inoltre:
- mTLS STRICT ovunque + AuthorizationPolicy per ogni flusso
- Certificati con TTL ≤ 1h con rotazione automatica
- Decision log analizzati in tempo reale (SIEM)
- Continuous compliance automatizzata

---

## Riferimenti

- [NIST SP 800-207 — Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final) — definizione formale
- [CISA Zero Trust Maturity Model v2.0](https://www.cisa.gov/zero-trust-maturity-model) — guida pratica alla progressione
- [Google BeyondCorp: A New Approach to Enterprise Security](https://research.google/pubs/pub43231/) — paper originale
- [Istio Security Documentation](https://istio.io/latest/docs/concepts/security/) — implementazione service mesh
- [Cilium Network Policy](https://docs.cilium.io/en/stable/security/policy/) — layer 7 policy in Kubernetes
- [SPIFFE Standard](https://spiffe.io/docs/latest/spiffe-about/overview/) — workload identity per Zero Trust
- [NIST SP 800-204 — Security Strategies for Microservices](https://csrc.nist.gov/publications/detail/sp/800-204/final)
