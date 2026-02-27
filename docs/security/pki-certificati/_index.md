---
title: "PKI e Certificati"
slug: pki-certificati
category: security
tags: [pki, certificati, tls, ca, x509, cert-manager]
search_keywords: [pki public key infrastructure, certificate authority, tls certificates, x509 certificate, cert-manager kubernetes, internal ca, certificate lifecycle]
parent: security/_index
related: [security/autenticazione/mtls-spiffe, security/secret-management/vault, networking/fondamentali/tls-ssl-basics]
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# PKI e Certificati

Una **PKI (Public Key Infrastructure)** è l'infrastruttura organizzativa e tecnologica che gestisce il ciclo di vita dei certificati digitali: emissione, distribuzione, rinnovo e revoca. In un'architettura enterprise, la PKI è la fondazione su cui poggia la fiducia crittografica — mTLS tra servizi, HTTPS interno, firma dei software artifact.

## Argomenti

<div class="grid cards" markdown>

- **[PKI Interna](pki-interna.md)** — Progettazione della gerarchia CA, CA root e intermedie, CFSSL, step-ca, on-premise vs cloud
- **[cert-manager](cert-manager.md)** — Automazione del ciclo di vita dei certificati su Kubernetes: Let's Encrypt, Vault, CA interna

</div>

## La Gerarchia CA

```
Root CA (offline, HSM-protetta)
      │
      ├── CA Intermedia "Services" (online, emette per microservizi)
      │         ├── orders.production.svc — cert valido 24h
      │         └── payments.production.svc — cert valido 24h
      │
      ├── CA Intermedia "Infrastructure" (online, emette per infra)
      │         ├── *.prod.internal — cert valido 90d
      │         └── monitoring.internal
      │
      └── CA Intermedia "External" (online, integrata con Let's Encrypt)
                ├── api.example.com — cert valido 90d (LE)
                └── *.app.example.com — wildcard (LE)
```

**La root CA non emette mai direttamente certificati leaf** — rimane offline (HSM) e firma solo CA intermedie. Se una CA intermedia è compromessa, viene revocata senza toccare la root.
