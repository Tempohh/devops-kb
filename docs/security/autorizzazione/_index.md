---
title: "Autorizzazione"
slug: autorizzazione
category: security
tags: [autorizzazione, rbac, abac, rebac, opa, policy, permessi]
search_keywords: [authorization microservizi, rbac role based access control, abac attribute based, rebac relationship based, opa open policy agent, policy as code, zanzibar google, authorization server]
parent: security/_index
related: [security/autenticazione/oauth2-oidc, security/autenticazione/jwt]
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Autorizzazione

L'autorizzazione risponde alla domanda **"puoi fare questa cosa?"** — dopo che l'identità è stata stabilita (autenticazione), il sistema decide se l'operazione è permessa.

In un'architettura a microservizi enterprise, l'autorizzazione è un problema difficile perché le decisioni devono essere:
- **Consistenti** tra tutti i servizi (lo stesso utente non può avere permessi diversi su servizi diversi per la stessa risorsa)
- **Centrali** ma **eseguite localmente** (per latenza e resilienza)
- **Auditabili** (ogni decisione deve essere tracciabile)
- **Dinamiche** (i permessi cambiano senza re-deploy)

## Argomenti

<div class="grid cards" markdown>

- **[RBAC, ABAC, ReBAC](rbac-abac-rebac.md)** — I tre modelli di controllo accessi: quando usare quale, combinazioni, pattern enterprise
- **[OPA — Open Policy Agent](opa.md)** — Policy as code con Rego: architettura, integrazione con Kubernetes e microservizi, testing

</div>

## Dove Applicare l'Autorizzazione

```
                        Livello di autorizzazione
                              ┌─────────────────────────────────┐
API Gateway            ───►   │ Autenticazione + scope basici   │ ◄ "Hai un token valido?"
                              │ Rate limiting per client        │
                              └─────────────────────────────────┘
                              ┌─────────────────────────────────┐
Microservizio          ───►   │ Autorizzazione business logic   │ ◄ "Puoi leggere questo ordine?"
                              │ RBAC / ABAC / ReBAC             │
                              └─────────────────────────────────┘
                              ┌─────────────────────────────────┐
Data Layer             ───►   │ Row-level security              │ ◄ "Solo le tue righe"
                              │ Column masking                  │
                              └─────────────────────────────────┘
```

**Principio**: non affidarsi mai a un solo livello di autorizzazione. La difesa in profondità si applica anche qui.
