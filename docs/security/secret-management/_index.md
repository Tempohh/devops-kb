---
title: "Secret Management"
slug: secret-management
category: security
tags: [secret-management, vault, kubernetes-secrets, credenziali, rotazione]
search_keywords: [secret management, hashicorp vault, kubernetes secrets, credenziali rotazione, dynamic secrets, secret store, secret injection]
parent: security/_index
related: [security/autenticazione/oauth2-oidc, security/pki-certificati/pki-interna]
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Secret Management

Un **secret** è qualsiasi credenziale che non deve essere pubblica: password database, API key, certificati TLS, chiavi crittografiche, token OAuth. La gestione sicura dei secret è uno dei problemi più sottovalutati nell'ingegneria del software — e uno dei più frequentemente bucati.

## Il Problema

```
Anti-pattern comune (e pericoloso):
  secret hardcodato nel codice     → nel repository Git → storico permanente
  secret in ConfigMap Kubernetes   → base64 ≠ cifratura, visibile a tutti i viewer
  secret in variabile d'ambiente   → visibile in `kubectl describe pod`, in ps aux
  secret in env file committato    → .env in Git = compromissione completa
  secret mai ruotato               → se rubato, valido a vita
```

La soluzione non è "nascondere meglio" i secret — è **non avere secret statici a lungo termine**.

## Argomenti

<div class="grid cards" markdown>

- **[HashiCorp Vault](vault.md)** — Il secret manager di riferimento: dynamic secrets, PKI engine, auth methods, Kubernetes integration
- **[Kubernetes Secrets](kubernetes-secrets.md)** — Native secrets e i loro limiti, Sealed Secrets, External Secrets Operator

</div>

## Principi

- **Short-lived over long-lived**: credenziali che scadono in ore/giorni limitano la finestra di compromissione
- **Dynamic over static**: generare credenziali on-demand (Vault dynamic secrets) — zero password da distribuire
- **Rotation automatica**: ogni secret deve avere una scadenza e un meccanismo di rinnovo automatico
- **Audit trail completo**: ogni accesso a un secret deve essere loggato
