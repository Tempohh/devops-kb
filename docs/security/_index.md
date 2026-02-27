---
title: "Security"
slug: security
category: security
tags: [security, autenticazione, autorizzazione, pki, vault, supply-chain, compliance, zero-trust]
search_keywords: [security microservizi, enterprise security, oauth2, jwt, mtls, spiffe, opa, rbac, abac, vault secrets, cert-manager, cosign, falco, admission control, kubernetes security]
parent: _index
official_docs: https://owasp.org/www-project-top-ten/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Security

La sicurezza di un'architettura a microservizi enterprise non è un singolo componente — è un sistema di controlli stratificati (defense in depth) che operano a livelli diversi: dal canale di comunicazione, all'identità dei workload, alla gestione dei secret, alla verifica degli artifact, fino all'audit runtime.

Questa sezione copre la sicurezza nel contesto specifico di microservizi cloud-native con deployment Kubernetes, con attenzione agli ambienti on-premise e ibridi.

## Sezioni

<div class="grid cards" markdown>

-   **[Autenticazione](autenticazione/_index.md)**

    ---
    OAuth 2.0 / OIDC, JWT, mTLS con SPIFFE/SPIRE.
    "Chi sei?" — stabilire l'identità di utenti e workload.

-   **[Autorizzazione](autorizzazione/_index.md)**

    ---
    RBAC, ABAC, ReBAC (Zanzibar/OpenFGA), OPA policy as code.
    "Puoi farlo?" — decidere cosa è permesso.

-   **[Secret Management](secret-management/_index.md)**

    ---
    HashiCorp Vault (dynamic secrets, PKI, Kubernetes auth), Sealed Secrets, External Secrets Operator.
    Zero secret statici a lungo termine.

-   **[PKI e Certificati](pki-certificati/_index.md)**

    ---
    PKI interna (CFSSL, step-ca), cert-manager per automazione su Kubernetes.
    Il fondamento della fiducia crittografica.

-   **[Supply Chain Security](supply-chain/_index.md)**

    ---
    Image scanning (Trivy), SBOM, firma artifact (cosign/Sigstore), OPA Gatekeeper, Kyverno.
    Sicurezza da git commit alla produzione.

-   **[Compliance e Audit](compliance/_index.md)**

    ---
    Audit logging strutturato, Falco runtime security, Kubernetes audit log, SIEM.
    "Cosa è successo?" — audit trail e rilevazione anomalie.

</div>

---

## Modello di Sicurezza Enterprise — Vista d'Insieme

```
                    Utente Finale
                        │
                        │ OAuth 2.0 / OIDC + MFA
                        ▼
                 Identity Provider
            (Keycloak / Entra ID / Okta)
                        │
                        │ JWT (Access Token)
                        ▼
                   API Gateway ─────────────────── OPA (autorizzazione)
                        │                               │
                        │ mTLS + JWT propagazione        │
                        ▼                               │
              ┌─────────────────────┐                  │
              │   Service Mesh      │◄──────────────────┘
              │   (Istio/Envoy)     │
              │   STRICT mTLS       │
              │   SPIFFE/SPIRE      │
              └────────┬────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     Service A    Service B    Service C
          │            │            │
          └────────────┴────────────┘
                       │
               Vault (Dynamic Secrets)
               cert-manager (TLS certs)
               Kubernetes Secrets (cifrati)

Ogni layer:
  API Gateway     → autenticazione JWT + rate limiting
  Service Mesh    → mTLS obbligatorio + network policy
  OPA             → autorizzazione ABAC/ReBAC
  Vault           → nessun secret statico
  cert-manager    → rinnovo automatico certificati
  Falco           → rilevazione anomalie runtime
  Admission       → policy enforcement al deploy
  Audit Log       → trail completo
```

---

## Percorsi di Studio

### Security Engineering di Base (nuovo nel dominio)

1. [OAuth 2.0 e OIDC](autenticazione/oauth2-oidc.md) — il protocollo di identità universale
2. [JWT](autenticazione/jwt.md) — struttura, validazione, attacchi
3. [RBAC, ABAC, ReBAC](autorizzazione/rbac-abac-rebac.md) — modelli di autorizzazione
4. [Kubernetes Secrets](secret-management/kubernetes-secrets.md) — limitazioni e soluzioni

### Architettura Zero Trust per Microservizi

1. [mTLS e SPIFFE/SPIRE](autenticazione/mtls-spiffe.md) — identità dei workload
2. [OPA](autorizzazione/opa.md) — policy as code
3. [HashiCorp Vault](secret-management/vault.md) — dynamic secrets
4. [PKI Interna](pki-certificati/pki-interna.md) — gerarchia CA

### DevSecOps — Security nel CI/CD

1. [Image Scanning](supply-chain/image-scanning.md) — Trivy in CI
2. [SBOM e Cosign](supply-chain/sbom-cosign.md) — firma e provenienza
3. [Admission Control](supply-chain/admission-control.md) — policy al deploy
4. [Audit Logging](compliance/audit-logging.md) — visibilità runtime

---

## Tutti gli Argomenti

| Argomento | Sezione | Difficoltà |
|-----------|---------|------------|
| [OAuth 2.0 e OIDC](autenticazione/oauth2-oidc.md) | Autenticazione | Advanced |
| [JWT](autenticazione/jwt.md) | Autenticazione | Advanced |
| [mTLS e SPIFFE/SPIRE](autenticazione/mtls-spiffe.md) | Autenticazione | Advanced |
| [RBAC, ABAC, ReBAC](autorizzazione/rbac-abac-rebac.md) | Autorizzazione | Advanced |
| [OPA — Open Policy Agent](autorizzazione/opa.md) | Autorizzazione | Advanced |
| [HashiCorp Vault](secret-management/vault.md) | Secret Management | Advanced |
| [Kubernetes Secrets](secret-management/kubernetes-secrets.md) | Secret Management | Intermediate |
| [PKI Interna](pki-certificati/pki-interna.md) | PKI e Certificati | Advanced |
| [cert-manager](pki-certificati/cert-manager.md) | PKI e Certificati | Intermediate |
| [Image Scanning](supply-chain/image-scanning.md) | Supply Chain | Intermediate |
| [SBOM e Cosign](supply-chain/sbom-cosign.md) | Supply Chain | Advanced |
| [Admission Control](supply-chain/admission-control.md) | Supply Chain | Advanced |
| [Audit Logging e Runtime Security](compliance/audit-logging.md) | Compliance | Advanced |

## Riferimenti Fondamentali

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST SP 800-204 — Security Strategies for Microservices](https://csrc.nist.gov/publications/detail/sp/800-204/final)
- [CNCF Cloud Native Security Whitepaper](https://github.com/cncf/tag-security/blob/main/security-whitepaper/v2/CNCF_cloud-native-security-whitepaper-May2022-v2.pdf)
- [NIST SP 800-207 — Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final)
