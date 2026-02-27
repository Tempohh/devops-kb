---
title: "Supply Chain Security"
slug: supply-chain
category: security
tags: [supply-chain, container-security, image-scanning, sbom, cosign, admission-control]
search_keywords: [supply chain security, container image security, image scanning vulnerability, sbom software bill of materials, cosign sigstore, admission controller kubernetes, software supply chain attack]
parent: security/_index
related: [security/pki-certificati/cert-manager, security/compliance/audit-logging]
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Supply Chain Security

La **supply chain security** riguarda la sicurezza di tutto ciò che compone il software — le dipendenze, le immagini container, i tool di build, la pipeline CI/CD. Un attacco alla supply chain compromette il software a monte, prima che arrivi in produzione.

L'attacco SolarWinds (2020) e l'attacco al package npm `event-stream` sono esempi emblematici: non il sistema finale, ma il processo di build o una dipendenza erano il vettore.

## Argomenti

<div class="grid cards" markdown>

- **[Image Scanning](image-scanning.md)** — Analisi vulnerabilità nelle immagini container: Trivy, policy-as-code, CI/CD integration
- **[SBOM e Cosign](sbom-cosign.md)** — Software Bill of Materials, firma degli artifact con Sigstore/cosign, SLSA framework
- **[Admission Control](admission-control.md)** — OPA Gatekeeper, Kyverno, Pod Security Standards: validazione e mutation dei manifest Kubernetes

</div>

## La Catena di Trust

```
Developer → Git commit → CI Build → Image Build → Registry → Kubernetes
    │              │           │           │            │          │
  Firma          Scan       Lint        Sign         Verify    Validate
  (commit)   (SAST/SCA)  (policy)   (cosign)    (admission)  (runtime)
```

Ogni fase della catena può essere un punto di attacco — la difesa in profondità richiede controlli a ogni step.
