---
title: "Zero Trust Networking"
slug: zero-trust
category: networking
tags: [zero-trust, sicurezza, identità, ztna, microsegmentazione, mtls, iam]
search_keywords: [zero trust network, ztna, zero trust architecture, never trust always verify, identity aware proxy, iap, beyondcorp, nist 800-207, software defined perimeter, sdp, micro-segmentation, conditional access, device posture, continuous verification, service mesh mtls, bpf, sidecar proxy, identity provider, okta, azure ad, google workspace]
parent: networking/sicurezza/_index
related: [networking/sicurezza/vpn-ipsec, networking/sicurezza/firewall-waf, networking/service-mesh/istio, networking/kubernetes/network-policies]
official_docs: https://csrc.nist.gov/publications/detail/sp/800-207/final
status: complete
difficulty: advanced
last_updated: 2026-03-09
---

# Zero Trust Networking

## Panoramica

Zero Trust (ZT) è un paradigma di sicurezza basato sul principio **"never trust, always verify"**: nessun utente, dispositivo o servizio è considerato fidato per default, indipendentemente dalla sua posizione di rete (interno o esterno). Ogni accesso viene autenticato, autorizzato e continuamente verificato. Zero Trust sostituisce il modello tradizionale "castle and moat" dove tutto dentro il perimetro è fidato.

Il modello è definito da NIST SP 800-207 e deriva dall'esperienza di Google con BeyondCorp (2011). I pilastri principali sono: **verifica esplicita dell'identità**, **accesso con privilegi minimi**, e **assunzione di breach** (assumere che la rete interna sia già compromessa).

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
**Policy Engine** = decide se l'accesso è consentito basandosi su policy e data sources
**Policy Enforcement Point** = l'entità che concede/nega l'accesso fisicamente (proxy, gateway, sidecar)

## Architettura / Come Funziona

### Zero Trust per Accesso Utente (ZTNA)

```
Utente remoto
  │
  ├── Identity Provider (Okta, Azure AD)
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
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT   # PERMISSIVE durante migrazione, STRICT in produzione

---
# 2. Authorization Policy — chi può chiamare chi
apiVersion: security.istio.io/v1beta1
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

```yaml
# terraform/cloudflare_access.tf

# Definisce l'applicazione protetta
resource "cloudflare_access_application" "internal_app" {
  zone_id          = var.zone_id
  name             = "Internal Dashboard"
  domain           = "dashboard.example.com"
  type             = "self_hosted"
  session_duration = "8h"

  # Abilita CORS per browser
  cors_headers {
    allowed_origins = ["https://dashboard.example.com"]
    allow_all_methods = true
  }
}

# Policy di accesso: solo utenti del gruppo engineering con dispositivo compliant
resource "cloudflare_access_policy" "engineering_only" {
  application_id = cloudflare_access_application.internal_app.id
  zone_id        = var.zone_id
  name           = "Engineering Access"
  precedence     = 1
  decision       = "allow"

  include {
    group = [cloudflare_access_group.engineering.id]
  }

  require {
    device_posture = [cloudflare_device_posture_rule.os_version.id]
  }
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
  ✓ Identity Provider centralizzato (Okta, Azure AD)
  ✓ SSO per tutte le applicazioni
  ✓ Device enrollment nell'MDM
  ✓ Revoca accesso VPN per le app migrate a IAP

Fase 3 — Rete (mesi 3-6):
  ✓ Micro-segmentazione (Network Policies in K8s, Security Groups in cloud)
  ✓ mTLS tra microservizi (service mesh)
  ✓ Egress filtering — blocca traffico verso destinazioni non autorizzate

Fase 4 — Dati (mesi 6-12):
  ✓ Data classification
  ✓ DLP (Data Loss Prevention)
  ✓ Encrypt-at-rest con key management (Vault, KMS)
  ✓ Monitoraggio anomalie (UEBA)
```

### SPIFFE/SPIRE — Identità per i Workload

SPIFFE (Secure Production Identity Framework for Everyone) standardizza l'identità dei workload tramite certificati X.509 con URI SAN (SPIFFE ID):

```bash
# Installa SPIRE Server (gestisce l'identità dei workload)
docker run -d --name spire-server \
  -p 8081:8081 \
  ghcr.io/spiffe/spire-server:1.8.0 \
  -config /opt/spire/conf/server/server.conf

# Registra un workload
spire-server entry create \
  -spiffeID spiffe://example.org/ns/production/sa/api-service \
  -parentID spiffe://example.org/spire/agent/k8s_psat/production/node1 \
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
resource "cloudflare_device_posture_rule" "os_version" {
  account_id = var.account_id
  name       = "Minimum OS Version"
  type       = "os_version"

  input {
    version          = "14.0"  # macOS 14+
    operator         = ">="
    operating_system = "mac"
  }
}

# Check: certificato aziendale installato
resource "cloudflare_device_posture_rule" "client_cert" {
  account_id = var.account_id
  name       = "Corporate Certificate"
  type       = "client_certificate"
}
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

# Verifica SPIFFE ID certificato in un pod
kubectl exec mypod -- cat /var/run/secrets/... | openssl x509 -noout -text | grep URI

# Log Cloudflare Access
# Dashboard → Zero Trust → Logs → Access Requests
```

## Relazioni

??? info "VPN — L'approccio che Zero Trust sostituisce"
    La VPN concede accesso a rete; Zero Trust concede accesso per risorsa.

    **Approfondimento →** [VPN e IPsec](vpn-ipsec.md)

??? info "Istio — Service Mesh con mTLS e AuthorizationPolicy"
    Istio implementa Zero Trust per i microservizi.

    **Approfondimento →** [Istio](../service-mesh/istio.md)

??? info "Network Policies — Micro-segmentazione Kubernetes"
    Le Kubernetes Network Policies sono un elemento Zero Trust per il cluster.

    **Approfondimento →** [Network Policies](../kubernetes/network-policies.md)

## Riferimenti

- [NIST SP 800-207 — Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final)
- [Google BeyondCorp](https://cloud.google.com/beyondcorp)
- [SPIFFE/SPIRE Project](https://spiffe.io/)
- [Cloudflare Zero Trust](https://www.cloudflare.com/zero-trust/)
