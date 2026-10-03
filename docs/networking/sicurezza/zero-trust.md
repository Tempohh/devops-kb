---
title: "Zero Trust Networking"
slug: zero-trust
category: networking
tags: [zero-trust, sicurezza, identità, ztna, microsegmentazione, mtls, iam]
search_keywords: [zero trust network, ztna, zero trust architecture, never trust always verify, identity aware proxy, iap, beyondcorp, nist 800-207, software defined perimeter, sdp, micro-segmentation, conditional access, device posture, continuous verification, service mesh mtls, bpf, sidecar proxy, identity provider, okta, azure ad, google workspace]
parent: networking/sicurezza/_index
related: [networking/sicurezza/vpn-ipsec, networking/sicurezza/firewall-waf, networking/sicurezza/wireguard, networking/service-mesh/istio, networking/kubernetes/network-policies, security/network/zero-trust]
official_docs: https://csrc.nist.gov/publications/detail/sp/800-207/final
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Zero Trust Networking

## Panoramica

Zero Trust (ZT) è un paradigma di sicurezza basato sul principio **"never trust, always verify"**: nessun utente, dispositivo o servizio è considerato fidato per default, indipendentemente dalla sua posizione di rete (interno o esterno). Ogni accesso viene autenticato, autorizzato e continuamente verificato. Zero Trust sostituisce il modello tradizionale "castle and moat" dove tutto dentro il perimetro è fidato.

Il modello è definito da NIST SP 800-207 (2020) e deriva dall'esperienza di Google con BeyondCorp (iniziato internamente nel 2011, pubblicato dal 2014). I pilastri principali sono: **verifica esplicita dell'identità**, **accesso con privilegi minimi**, e **assunzione di breach** (assumere che la rete interna sia già compromessa).

## Prerequisiti

Questo argomento presuppone familiarità con:
- [VPN e IPsec](vpn-ipsec.md) — Zero Trust è l'alternativa moderna alla VPN tradizionale: capire la VPN aiuta a capire perché Zero Trust la supera
- [Firewall e WAF](firewall-waf.md) — il modello perimetrale che Zero Trust sostituisce si basa su firewall di confine
- [TLS/SSL Basics](../fondamentali/tls-ssl-basics.md) — mTLS e certificati sono la base dell'identità crittografica in Zero Trust

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

## Concetti Chiave

### Perché Zero Trust

Il modello perimetrale tradizionale presuppone:
- La rete interna è sicura
- La rete esterna è pericolosa
- Connettiti alla VPN → accesso a tutto

Questo fallisce in scenari moderni:
- **Insider threat**: utenti interni malintenzionati hanno accesso a tutto
- **Lateral movement**: un attaccante che compromette un host interno si muove liberamente
- **Cloud e BYOD**: i confini della rete non esistono più — utenti ovunque, carichi di lavoro su cloud pubblici
- **Supply chain attacks**: codice di terze parti compromette il perimetro dall'interno

### Principi NIST 800-207

Sintesi dei 7 *tenets* di NIST SP 800-207 (il tenet sulla raccolta di telemetria per migliorare la postura è assorbito nel monitoraggio continuo):

1. **Tutte le risorse sono considerate non fidate** indipendentemente dalla posizione di rete
2. **Tutte le comunicazioni sono cifrate** — anche nella rete interna
3. **Accesso per risorsa singola** — non accesso all'intera rete
4. **Accesso dinamico basato su policy** — identità + postura del dispositivo + contesto
5. **Monitoraggio continuo** — nessuna fiducia implicita derivante dall'autenticazione passata
6. **Autenticazione e autorizzazione strong** — MFA, certificati, non solo password

### Componenti Architetturali

```
                    Policy Engine
                   (decisioni accesso)
                         │
                    Policy Administrator
                   (applica le decisioni)
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
       Policy           Data         App
    Enforcement       Sources       Access
      Point (PEP)   (IdP, MDM,    Gateway
           │         SIEM, CVE)
           │
    ┌──────┴──────┐
    ▼             ▼
 Resource      Subject
 (App, DB,    (User +
  API)         Device)
```

**Subject** = chi accede (utente + dispositivo + servizio)
**Policy Engine (PE)** = decide se l'accesso è consentito, valutando policy e *data sources* (IdP, MDM, SIEM, threat intelligence)
**Policy Administrator (PA)** = traduce la decisione del PE in comandi al PEP (es. emette il token/sessione di accesso)
**Policy Enforcement Point (PEP)** = l'entità che concede/nega l'accesso fisicamente (proxy, gateway, sidecar)

PE + PA formano il **Policy Decision Point (PDP)** (control plane); il PEP è il data plane. Separarli permette di cambiare policy senza toccare i punti di enforcement. Il PEP non decide mai da solo: se il PDP è irraggiungibile, la scelta tra fail-closed (sicuro, ma blocca) e cache dell'ultima decisione è un compromesso da definire esplicitamente.

!!! note "Sigle"
    **IdP** = Identity Provider (autentica e rilascia token); **MDM** = Mobile Device Management (inventario e conformità dei dispositivi); **SIEM** = Security Information and Event Management (correlazione log di sicurezza); **IAP** = Identity-Aware Proxy (proxy che autorizza per identità, non per IP); **ZTNA** = Zero Trust Network Access.

## Architettura / Come Funziona

### Zero Trust per Accesso Utente (ZTNA)

```
Utente remoto
  │
  ├── Identity Provider (Okta, Microsoft Entra ID, già Azure AD)
  │     ├── Autenticazione MFA
  │     ├── SSO (SAML/OIDC)
  │     └── Emissione token (JWT)
  │
  ├── Device Posture Check (MDM: Intune, Jamf)
  │     ├── OS aggiornato?
  │     ├── Antivirus attivo?
  │     └── Disco cifrato?
  │
  ▼
Identity-Aware Proxy (IAP: Google IAP, Cloudflare Access, Zscaler)
  │
  ├── Verifica token + postura + contesto (ora, geo, rete)
  ├── Policy: user ∈ group "devs" AND device.compliant = true AND hour 9-18
  │
  ▼
Risorsa specifica (solo quella richiesta, non l'intera rete)
```

### Zero Trust per Microservizi (mTLS)

```
Service A                          Service B
    │                                  │
    ├── Certificato: spiffe://...       ├── Certificato: spiffe://...
    │   /ns/app/sa/service-a           │   /ns/app/sa/service-b
    │                                  │
    └────── mTLS (mutual TLS) ─────────┘
            Ogni servizio verifica
            l'identità dell'altro

Policy: service-a PUÒ chiamare service-b su /api/v1/users
        service-a NON PUÒ chiamare service-db direttamente
```

### Implementazione con Istio (Service Mesh)

```yaml
# 1. Abilita mTLS strict in tutto il namespace (ogni comunicazione cifrata e autenticata)
# security.istio.io/v1 è GA dalla 1.22; v1beta1 resta accettata sulle versioni precedenti
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT   # PERMISSIVE durante migrazione, STRICT in produzione

---
# 2. Authorization Policy — chi può chiamare chi
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: api-service-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-service

  rules:
  # Permetti solo dal frontend (identità SPIFFE)
  - from:
    - source:
        principals:
          - "cluster.local/ns/production/sa/frontend-service"
    to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/v1/*"]

  # Permetti dal monitoring per metriche
  - from:
    - source:
        namespaces: ["monitoring"]
    to:
    - operation:
        ports: ["9090"]   # Metrics port
```

### Identity-Aware Proxy con Cloudflare Access

!!! note "Versione provider"
    Esempio per il provider Terraform Cloudflare **v5** (`~> 5.0`). Rispetto alla v4: risorse rinominate `cloudflare_zero_trust_*`; i blocchi annidati diventano *attributi* (`cors_headers = { ... }`, `include = [{ ... }]`); la policy è un oggetto **riutilizzabile a livello account** (niente `application_id`/`precedence` sulla policy) e si collega all'applicazione tramite l'attributo `policies`.

```hcl
# terraform/cloudflare_access.tf (provider cloudflare ~> 5.x)

# Policy riutilizzabile: solo utenti del gruppo engineering con dispositivo compliant
resource "cloudflare_zero_trust_access_policy" "engineering_only" {
  account_id = var.account_id
  name       = "Engineering Access"
  decision   = "allow"

  # include = OR tra le regole; require = AND
  include = [{
    group = { id = cloudflare_zero_trust_access_group.engineering.id }
  }]

  require = [{
    device_posture = { integration_uid = cloudflare_zero_trust_device_posture_rule.os_version.id }
  }]
}

# Definisce l'applicazione protetta e le associa la policy
resource "cloudflare_zero_trust_access_application" "internal_app" {
  zone_id          = var.zone_id
  name             = "Internal Dashboard"
  domain           = "dashboard.example.com"
  type             = "self_hosted"
  session_duration = "8h"

  # Abilita CORS per browser
  cors_headers = {
    allowed_origins   = ["https://dashboard.example.com"]
    allow_all_methods = true
  }

  policies = [{
    id         = cloudflare_zero_trust_access_policy.engineering_only.id
    precedence = 1
  }]
}
```

## Configurazione & Pratica

### Implementazione Graduale Zero Trust

Zero Trust non si implementa in un giorno — richiede un approccio incrementale:

```
Fase 1 — Visibilità (settimane 1-4):
  ✓ Inventario completo di utenti, dispositivi, applicazioni
  ✓ Log centralizzati di tutti gli accessi
  ✓ MFA per tutti gli utenti

Fase 2 — Identità (mesi 1-3):
  ✓ Identity Provider centralizzato (Okta, Microsoft Entra ID)
  ✓ SSO per tutte le applicazioni
  ✓ Device enrollment nell'MDM
  ✓ Revoca accesso VPN per le app migrate a IAP

Fase 3 — Rete (mesi 3-6):
  ✓ Micro-segmentazione (Network Policies in K8s, Security Groups in cloud)
  ✓ mTLS tra microservizi (service mesh)
  ✓ Egress filtering — blocca traffico verso destinazioni non autorizzate

Fase 4 — Dati (mesi 6-12):
  ✓ Data classification
  ✓ DLP (Data Loss Prevention — impedisce l'uscita di dati sensibili)
  ✓ Encrypt-at-rest con key management (Vault, KMS)
  ✓ Monitoraggio anomalie (UEBA, User and Entity Behavior Analytics — rileva comportamenti anomali rispetto alla baseline)
```

### SPIFFE/SPIRE — Identità per i Workload

SPIFFE (Secure Production Identity Framework for Everyone) standardizza l'identità dei workload tramite certificati X.509 con URI SAN (SPIFFE ID):

```bash
# Installa SPIRE Server (gestisce l'identità dei workload).
# Per prove locali; in Kubernetes usare l'Helm chart ufficiale (spiffe/helm-charts-hardened)
# e fissare una versione 1.x corrente invece di "latest".
docker run -d --name spire-server \
  -p 8081:8081 \
  ghcr.io/spiffe/spire-server:<versione-1.x> \
  -config /opt/spire/conf/server/server.conf

# Registra un workload
# parentID = SPIFFE ID dell'agent del nodo (formato k8s_psat: .../agent/k8s_psat/<cluster>/<node-uid>)
spire-server entry create \
  -spiffeID spiffe://example.org/ns/production/sa/api-service \
  -parentID spiffe://example.org/spire/agent/k8s_psat/<cluster>/<node-uid> \
  -selector k8s:ns:production \
  -selector k8s:sa:api-service

# Il workload ottiene automaticamente un certificato X.509 con SPIFFE ID
# Istio, Linkerd e altri service mesh usano SPIRE o implementazioni compatibili
```

### Verifica Postura Dispositivo

```yaml
# Cloudflare WARP + Device Posture
# Controlla se il dispositivo è conforme prima di concedere accesso

# Check: versione OS minima
# (provider cloudflare ~> 5.x: `input` è un attributo, non un blocco)
resource "cloudflare_zero_trust_device_posture_rule" "os_version" {
  account_id = var.account_id
  name       = "Minimum OS Version"
  type       = "os_version"

  input = {
    version          = "14.0"  # macOS 14+
    version_operator = ">="
    operating_system = "mac"
  }
}

# Altri type disponibili: disk_encryption, firewall, client_certificate_v2,
# domain_joined, e integrazioni EDR/MDM (crowdstrike_s2s, intune, kolide, ...)
```

## Best Practices

- **Iniziare dall'identità**: l'IdP centralizzato con MFA è il prerequisito di tutto Zero Trust — implementarlo prima di qualsiasi altra cosa
- **Non tutto in una volta**: la migrazione da VPN perimetrale a Zero Trust è un percorso di mesi — procedere per applicazione, non per rete intera
- **Privilegio minimo per default**: ogni risorsa deve avere una policy esplicita "chi può accedere" — non "tutti possono accedere"
- **Monitora e fai alert**: Zero Trust senza visibilità è inutile — ogni accesso negato è un segnale da investigare
- **mTLS nelle rete interna**: cifrare il traffico inter-servizio anche "dentro" il cluster — un attaccante che compromette un pod interno non deve vedere tutto
- **Ruotare i certificati frequentemente**: cert-manager (Kubernetes) o Istio lo fanno automaticamente ogni 24h — usare questa funzionalità
- **Test regolari**: simulare attacchi di lateral movement per verificare che le policy funzionino

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Accesso negato nonostante policy corretta | Postura dispositivo non verificata | Controllare log MDM e aggiornare device posture rule |
| mTLS fallisce tra servizi | Certificati scaduti o trust store errato | `istioctl proxy-config secret` per verificare certificati |
| Accesso intermittente | Policy engine non raggiungibile | Alta disponibilità del policy engine |
| Latenza alta | Ogni richiesta viene verificata | Caching dei token JWT, ottimizzare policy evaluation |
| Utente bloccato fuori | Device non compliant | Guida l'utente al remediation device |

```bash
# Debug Istio mTLS
istioctl proxy-config secret <pod> -n production
istioctl analyze -n production

# Verifica SPIFFE ID del certificato workload di Istio (il sidecar lo tiene in memoria, non su disco)
istioctl proxy-config secret <pod> -n production -o json \
  | jq -r '.dynamicActiveSecrets[0].secret.tlsCertificate.certificateChain.inlineBytes' \
  | base64 -d | openssl x509 -noout -text | grep URI

# Log Cloudflare Access
# Dashboard → Zero Trust → Logs → Access Requests
```

### Scenario 1 — Richieste 503/"upstream connect error" dopo `STRICT` mTLS

**Sintomo**: dopo aver applicato `PeerAuthentication` in modalità `STRICT`, i client senza sidecar (job, pod fuori mesh, health check del load balancer) ricevono connection reset o 503.

**Causa**: in `STRICT` il sidecar accetta solo traffico mTLS; i client che parlano in plaintext vengono rifiutati durante l'handshake.

**Soluzione**: tornare a `PERMISSIVE`, individuare i client non-mesh, iniettare il sidecar (o escludere la porta) e solo poi riabilitare `STRICT`.

```bash
# Quali workload hanno il sidecar?
kubectl get pods -n production -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].name}{"\n"}{end}'
# Stato mTLS effettivo per pod
istioctl x describe pod <pod> -n production
# Rollback temporaneo
kubectl patch peerauthentication default -n production --type merge -p '{"spec":{"mtls":{"mode":"PERMISSIVE"}}}'
```

### Scenario 2 — `RBAC: access denied` con mTLS funzionante

**Sintomo**: la connessione TLS si stabilisce ma la richiesta riceve HTTP 403 `RBAC: access denied`.

**Causa**: l'`AuthorizationPolicy` non contiene il principal SPIFFE del chiamante (service account o namespace errato), oppure `paths`/`methods` non combaciano. Con almeno una policy `ALLOW` presente, tutto ciò che non è elencato è negato.

**Soluzione**: leggere il principal reale del chiamante nei log del proxy e correggere la policy.

```bash
kubectl logs <pod-api> -c istio-proxy -n production | grep "rbac_access_denied"
istioctl x authz check <pod-api> -n production
kubectl get authorizationpolicy -n production -o yaml
```

### Scenario 3 — Utenti bloccati da IAP per device posture

**Sintomo**: utente autenticato con MFA ma `Access denied` sull'applicazione; da altri dispositivi funziona.

**Causa**: il client (es. WARP) non riporta la postura — agente non connesso, OS sotto la versione minima della regola, o certificato aziendale mancante.

**Soluzione**: verificare lo stato del client sul dispositivo, poi la regola di posture e il log Access per il motivo esatto del rifiuto.

```bash
warp-cli status
warp-cli settings | grep -i organization
# Dashboard → Zero Trust → Logs → Access → dettaglio richiesta (campo "Reason")
```

### Scenario 4 — Workload senza SVID (SPIRE)

**Sintomo**: il workload non ottiene il certificato SPIFFE; i log dell'agent riportano `no identity issued` / `no registration entry`.

**Causa**: nessuna registration entry combacia con i selector del pod (namespace o service account diversi), oppure l'agent non è attestato presso il server.

**Soluzione**: elencare le entry, confrontare i selector con il pod reale e verificare la salute di agent e server.

```bash
spire-server entry show
spire-server agent list
spire-server healthcheck
kubectl get pod <pod> -o jsonpath='{.metadata.namespace}{" "}{.spec.serviceAccountName}{"\n"}'
```

## Relazioni

??? info "WireGuard — VPN moderna spesso usata come building block ZTNA"
    WireGuard fornisce il tunnel cifrato punto-punto su cui alcune soluzioni ZTNA (es. Cloudflare WARP) costruiscono le proprie policy di accesso.

    **Approfondimento →** [WireGuard](wireguard.md)

??? info "VPN — L'approccio che Zero Trust sostituisce"
    La VPN concede accesso a rete; Zero Trust concede accesso per risorsa.

    **Approfondimento →** [VPN e IPsec](vpn-ipsec.md)

??? info "Istio — Service Mesh con mTLS e AuthorizationPolicy"
    Istio implementa Zero Trust per i microservizi.

    **Approfondimento →** [Istio](../service-mesh/istio.md)

??? info "Network Policies — Micro-segmentazione Kubernetes"
    Le Kubernetes Network Policies sono un elemento Zero Trust per il cluster.

    **Approfondimento →** [Network Policies](../kubernetes/network-policies.md)

??? info "Zero Trust Architecture — Implementazione per Workload Kubernetes"
    Questo file copre Zero Trust dal punto di vista del networking e dell'accesso utente (ZTNA). Per l'implementazione profonda lato workload — Kubernetes Network Policy, Istio AuthorizationPolicy, Cilium L7, OPA come PDP, SPIFFE/SPIRE e troubleshooting dettagliato — vedi il file complementare nella sezione security.

    **Approfondimento →** [Zero Trust Architecture](../../security/network/zero-trust.md)

## Riferimenti

- [NIST SP 800-207 — Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final)
- [Google BeyondCorp](https://cloud.google.com/beyondcorp)
- [SPIFFE/SPIRE Project](https://spiffe.io/)
- [Cloudflare Zero Trust](https://www.cloudflare.com/zero-trust/)
