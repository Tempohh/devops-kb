---
title: "Sicurezza Applicativa"
slug: sicurezza
category: dev
tags: [sicurezza, tls, mtls, autenticazione, certificati, crittografia]
search_keywords: [sicurezza applicativa, application security, tls da codice, mtls applicazione, certificati client, ssl applicazione, security developer, secure coding]
parent: dev/_index
official_docs: https://owasp.org/www-project-developer-guide/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Sicurezza Applicativa

Questa sezione copre la **prospettiva del developer** sulla sicurezza: come configurare TLS/mTLS nel codice applicativo, come gestire certificati client, come ruotare i certificati senza restart. È complementare alla sezione [Security](../../security/_index.md) che si occupa di infrastruttura (PKI, cert-manager, Vault).

---

## Argomenti

<div class="grid cards" markdown>

-   :material-certificate: **TLS/mTLS da Codice**

    ---
    Java KeyStore/TrustStore, SSLContext. .NET X509Certificate2, SslStream. Go tls.Config, x509.CertPool. Rotation senza restart, debug TLS.

    → [TLS da Codice](tls-da-codice.md)

-   :material-key-variant: **Secrets e Config da Codice**

    ---
    Env var vs volume montato. Hot reload: Spring @RefreshScope, .NET IOptionsMonitor, Go viper.WatchConfig. Vault Agent Sidecar. AWS/Azure SDK. Anti-pattern: segreti nei log.

    → [Secrets e Config](secrets-config.md)

</div>

---

## Prospettiva Developer vs Ops

| Domanda | Sezione giusta |
|---|---|
| Come configuro `SSLContext` in Java con un certificato client? | **Questa sezione** |
| Come emetto e rinnovo certificati con cert-manager? | [Security / PKI](../../security/pki-certificati/cert-manager.md) |
| Come implemento mTLS tra microservizi con SPIFFE/SPIRE? | [Security / mTLS SPIFFE](../../security/autenticazione/mtls-spiffe.md) |
| Come funziona TLS a livello di protocollo? | [Networking / TLS-SSL Basics](../../networking/fondamentali/tls-ssl-basics.md) |
