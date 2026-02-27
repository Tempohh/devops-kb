---
title: "Autenticazione"
slug: autenticazione
category: security
tags: [autenticazione, oauth2, oidc, jwt, mtls, spiffe, identity]
search_keywords: [autenticazione microservizi, oauth2 openid connect, jwt token, mutual tls, spiffe spire, identity provider, keycloak, auth0, aws cognito, azure ad entra id, service to service auth]
parent: security/_index
related: [security/autorizzazione/rbac-abac-rebac, security/pki-certificati/pki-interna, networking/sicurezza/zero-trust]
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Autenticazione

L'autenticazione risponde alla domanda **"chi sei?"** — stabilisce l'identità di chi sta operando. In un'architettura a microservizi, ci sono due tipi fondamentalmente diversi di identità che occorre gestire:

- **Identità umana** (utenti finali, operatori): gestita via OAuth 2.0 / OIDC con Identity Provider centralizzato
- **Identità macchina** (servizi, pod, lambda): gestita via mTLS con certificati SPIFFE/SPIRE o via client credentials OAuth 2.0

La complessità di un'architettura enterprise nasce dal fatto che queste due dimensioni coesistono e si intrecciano: un utente chiama un API Gateway che delega a un microservizio che a sua volta chiama altri microservizi — ogni hop ha requisiti di identità diversi.

## Argomenti

<div class="grid cards" markdown>

- **[OAuth 2.0 e OpenID Connect](oauth2-oidc.md)** — Il protocollo di delega e federazione delle identità. Authorization Code + PKCE, Client Credentials per M2M, token lifecycle
- **[JWT — JSON Web Token](jwt.md)** — Struttura, algoritmi di firma, validazione, attacchi noti e mitigazioni
- **[mTLS e SPIFFE/SPIRE](mtls-spiffe.md)** — Autenticazione mutua servizio-a-servizio con certificati X.509 e identità workload criptografiche

</div>

## Mappa dei Meccanismi di Autenticazione

```
         Utente Browser / Mobile App
                     │
                     │ OAuth 2.0 Authorization Code + PKCE
                     ▼
              Identity Provider
          (Keycloak / Entra ID / Cognito)
                     │
                     │ emette Access Token (JWT)
                     ▼
               API Gateway               ←── verifica JWT firma + claims
                     │
                     │ propaga identità (header o token ridotto)
                     ▼
          Microservizio A ─────────────── Microservizio B
                  │    mTLS (SPIFFE SVID)      │
                  │    Client Credentials       │
                  └────────────────────────────┘
                           Service Mesh
```

**Regola fondamentale**: ogni hop deve autenticare l'hop precedente. Un token utente non deve mai essere usato come prova di identità tra servizi — usa mTLS o client credentials per la comunicazione M2M.
