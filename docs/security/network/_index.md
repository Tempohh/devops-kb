---
title: "Network Security"
slug: network-security
category: security
tags: [network-security, zero-trust, micro-segmentation, network-policy]
search_keywords: [network security kubernetes, zero trust network, micro-segmentation, network policy k8s, istio security, cilium policy, service mesh security]
parent: security/_index
related: [security/autenticazione/mtls-spiffe, security/autorizzazione/opa]
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# Network Security

La sicurezza di rete in un'architettura cloud-native va oltre il perimetro tradizionale: ogni comunicazione — anche all'interno del cluster — deve essere autenticata, autorizzata e cifrata. Questa sezione copre i modelli e gli strumenti per implementare Zero Trust a livello di rete.

## Argomenti

<div class="grid cards" markdown>

- **[Zero Trust Architecture](zero-trust.md)** — Il modello "never trust, always verify": micro-segmentazione, identità workload, policy enforcement. BeyondCorp, NIST 800-207, Istio AuthorizationPolicy, Cilium.

</div>
