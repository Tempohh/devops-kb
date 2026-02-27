---
title: "Sicurezza in Kafka"
slug: sicurezza
category: messaging
tags: [kafka, sicurezza, tls, ssl, sasl, acl, autenticazione, autorizzazione]
search_keywords: [kafka sicurezza, kafka tls ssl, kafka sasl, kafka acl, autenticazione kafka, autorizzazione kafka, kafka mTLS, kafka kerberos]
parent: messaging/kafka
related: [security/mutual-tls]
official_docs: https://kafka.apache.org/documentation/#security
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Sicurezza in Kafka

Kafka supporta più livelli di sicurezza: cifratura del trasporto con TLS/SSL, autenticazione tramite SASL (con diversi meccanismi), e autorizzazione granulare tramite ACL. In ambienti produttivi, tutti e tre i livelli devono essere attivi.

## Argomenti in questa sezione

| Argomento | Descrizione |
|-----------|-------------|
| [TLS/SSL](tls-ssl.md) | Cifratura del canale di comunicazione client-broker e broker-broker |
| [SASL](sasl.md) | Autenticazione: PLAIN, SCRAM, GSSAPI (Kerberos), OAUTHBEARER |
| [ACL e Autorizzazione](acl-autorizzazione.md) | Controllo granulare degli accessi a topic, consumer group e operazioni |
