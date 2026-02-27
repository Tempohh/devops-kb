---
title: "SBOM e Cosign — Firma e Provenienza degli Artifact"
slug: sbom-cosign
category: security
tags: [sbom, cosign, sigstore, slsa, supply-chain, firma-artifact, provenance]
search_keywords: [sbom software bill of materials, cosign sigstore, artifact signing, image signing kubernetes, slsa supply chain levels software artifacts, cyclonedx sbom, spdx sbom, rekor transparency log, fulcio certificate authority, keyless signing cosign, cosign verify kubernetes, policy controller cosign, image provenance, build attestation, in-toto attestation, supply chain attack prevention, software composition analysis, sigstore github actions, cosign github actions oidc, cosign aws ecr, artifact trust chain, verified builds, reproducible builds, software factory security]
parent: security/supply-chain/_index
related: [security/supply-chain/image-scanning, security/supply-chain/admission-control, security/pki-certificati/pki-interna]
official_docs: https://docs.sigstore.dev/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# SBOM e Cosign — Firma e Provenienza degli Artifact

## Panoramica

Sapere che un'immagine non ha CVE note non è sufficiente per fidarsi di essa — bisogna anche sapere **chi l'ha prodotta, quando, e da quale sorgente**. Gli attacchi moderni alla supply chain (SolarWinds, XZ Utils, typosquatting su npm) dimostrano che un artefatto può essere malicious non perché ha un bug noto, ma perché è stato compromesso nel processo di build.

**SBOM (Software Bill of Materials)**: un documento che elenca tutti i componenti di un software — come una lista ingredienti per il codice. Permette di rispondere rapidamente a "quali dei nostri servizi usano la libreria X con CVE Y?"

**Cosign + Sigstore**: un sistema per firmare crittograficamente gli artifact software (immagini, file, attestazioni) e verificare la firma al deployment. Chi verifica sa che l'immagine è stata prodotta da un sistema di build autorizzato, non da un attacker che ha compromesso il registro.

---

## SBOM — Software Bill of Materials

### Standard SBOM

Esistono due standard principali, entrambi supportati da Trivy:

```
CycloneDX:
  Formato JSON/XML creato da OWASP
  Più orientato alla sicurezza: VEX (Vulnerability Exploitability eXchange) integrato
  Supporto tool: Trivy, Syft, cdxgen, Dependency-Track

SPDX:
  Formato creato da Linux Foundation / ISO standard (ISO 5962:2021)
  Più orientato alla compliance e licensing
  Supporto tool: Trivy, Syft, Tern
```

### Generare un SBOM con Trivy

```bash
# Genera SBOM in formato CycloneDX da un'immagine
trivy image \
  --format cyclonedx \
  --output sbom.json \
  myapp:1.2.3

# Genera SBOM in SPDX
trivy image \
  --format spdx-json \
  --output sbom.spdx.json \
  myapp:1.2.3

# Da un filesystem (applicabile in CI prima del build dell'immagine)
trivy fs \
  --format cyclonedx \
  --output sbom.json \
  ./

# Genera SBOM con Syft (alternativa)
syft myapp:1.2.3 -o cyclonedx-json > sbom.json
```

### Struttura SBOM CycloneDX (estratto)

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "version": 1,
  "metadata": {
    "timestamp": "2024-01-15T14:32:00Z",
    "tools": [{"name": "trivy", "version": "0.50.0"}],
    "component": {
      "name": "myapp",
      "version": "1.2.3",
      "type": "container"
    }
  },
  "components": [
    {
      "type": "library",
      "name": "fastapi",
      "version": "0.109.0",
      "purl": "pkg:pypi/fastapi@0.109.0",
      "licenses": [{"license": {"id": "MIT"}}]
    },
    {
      "type": "operating-system",
      "name": "debian",
      "version": "12.4",
      "cpe": "cpe:2.3:o:debian:debian_linux:12.4:*:*:*:*:*:*:*"
    }
  ],
  "vulnerabilities": [
    {
      "id": "CVE-2023-XXXX",
      "ratings": [{"severity": "HIGH", "score": 8.1}],
      "affects": [{"ref": "pkg:pypi/requests@2.28.0"}]
    }
  ]
}
```

### Dependency-Track — SBOM Management Platform

```yaml
# docker-compose.yml — Dependency-Track
services:
  dependency-track-api:
    image: dependencytrack/apiserver:4.10
    environment:
      ALPINE_DATABASE_MODE: "external"
      ALPINE_DATABASE_URL: "jdbc:postgresql://db:5432/dtrack"
    volumes:
    - dt-data:/data
    ports: ["8080:8080"]

  dependency-track-ui:
    image: dependencytrack/frontend:4.10
    environment:
      API_BASE_URL: "http://dependency-track-api:8080"
    ports: ["8081:8080"]
```

```bash
# Carica un SBOM su Dependency-Track via API
curl -X PUT \
  "http://dependency-track:8080/api/v1/bom" \
  -H "X-Api-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d "{
    \"project\": \"orders-service\",
    \"version\": \"1.2.3\",
    \"bom\": \"$(base64 -w 0 sbom.json)\"
  }"

# Query: quali servizi usano log4j 2.14.1?
curl "http://dependency-track:8080/api/v1/component/search?purl=pkg:maven/log4j/log4j%402.14.1" \
  -H "X-Api-Key: your-api-key"
```

---

## Cosign e Sigstore — Firma degli Artifact

### Il Problema: Verifica di Provenienza

```
SENZA firma:
  CI build → push myapp:1.2.3 → registry → pull in produzione
  Come sai che myapp:1.2.3 nel registry è QUELLO che ha buildato la CI?
  Se un attacker ha accesso al registry → sovrascrive l'immagine → nessuno se ne accorge

CON firma (cosign):
  CI build → firma myapp:1.2.3 con chiave CI → push immagine + firma → registry
  Al pull: verifica firma → se non corrisponde alla chiave CI autorizzata → blocco
```

### Keyless Signing — OIDC + Transparency Log

Il modello tradizionale (chiave privata statica per firmare) ha il problema della gestione della chiave. **Sigstore Keyless** risolve questo: invece di una chiave privata, il sistema di build si autentica con OIDC (GitHub Actions, Google Cloud, etc.) e riceve un certificato di firma effimero (5 minuti di validità) dalla CA **Fulcio**. La firma viene registrata nel transparency log **Rekor** — un log append-only pubblicamente verificabile.

```
GitHub Actions workflow
      │
      │ OIDC token (identity: github.com/myorg/myrepo/.github/workflows/build.yml)
      ▼
  Fulcio CA (sigstore.dev)
      │
      │ certificato X.509 effimero (TTL: 5 minuti)
      │ Subject: https://github.com/myorg/myrepo/.github/workflows/build.yml@refs/heads/main
      ▼
  cosign firma l'immagine con il certificato effimero
      │
      ├─► registro: firma salvata come OCI artifact accanto all'immagine
      └─► Rekor: entry nel transparency log (immutabile, pubblicamente verificabile)
```

```yaml
# GitHub Actions — firma keyless con Sigstore
name: Build and Sign
on: [push]
permissions:
  contents: read
  id-token: write   # OBBLIGATORIO per keyless signing

jobs:
  build-and-sign:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Login to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Build and push image
      id: docker_build
      uses: docker/build-push-action@v5
      with:
        push: true
        tags: ghcr.io/${{ github.repository }}:${{ github.sha }}

    - name: Install cosign
      uses: sigstore/cosign-installer@v3

    - name: Sign image (keyless — usa OIDC GitHub)
      env:
        COSIGN_EXPERIMENTAL: "1"
      run: |
        cosign sign \
          --yes \
          ghcr.io/${{ github.repository }}@${{ steps.docker_build.outputs.digest }}
        # La firma è legata al digest (non al tag) — i tag sono mutabili!

    - name: Attach SBOM as attestation
      run: |
        trivy image --format cyclonedx --output sbom.json \
          ghcr.io/${{ github.repository }}@${{ steps.docker_build.outputs.digest }}

        cosign attest \
          --yes \
          --predicate sbom.json \
          --type cyclonedx \
          ghcr.io/${{ github.repository }}@${{ steps.docker_build.outputs.digest }}
```

### Verifica della Firma

```bash
# Verifica che l'immagine sia stata firmata dal workflow autorizzato
cosign verify \
  --certificate-identity-regexp "^https://github.com/myorg/myrepo/.github/workflows/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/myorg/myrepo@sha256:abc123...

# Output se valido:
# Verification for ghcr.io/myorg/myrepo@sha256:abc123... --
# The following checks were performed on each of these signatures:
#   - The cosign claims were validated
#   - Existence of the claims in the transparency log was verified offline
#   - The code-signing certificate was verified using trusted certificate chain

# Verifica e mostra l'attestazione SBOM
cosign verify-attestation \
  --certificate-identity-regexp "^https://github.com/myorg/myrepo/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --type cyclonedx \
  ghcr.io/myorg/myrepo@sha256:abc123... | \
  jq '.payload | @base64d | fromjson'
```

---

## SLSA — Supply-chain Levels for Software Artifacts

**SLSA** (pronunciato "salsa") è un framework di sicurezza graduale per la supply chain del software, sviluppato da Google e ora CNCF:

```
SLSA Levels:

Level 1 — Build Scripted
  → Il processo di build è automatizzato (no build manuali)
  → Genera provenance (SBOM, build info)
  → Qualsiasi CI/CD con log soddisfa questo livello

Level 2 — Build Service
  → Il build avviene su un sistema controllato (GitHub Actions, Cloud Build)
  → La provenance è firmata dal build service
  → Impedisce che sviluppatori modifichino il build localmente

Level 3 — Hardened Builds
  → Il build environment è isolato (sandbox)
  → Ogni artefatto ha provenance crittograficamente verificabile
  → La chiave di firma è generata per ogni build e non persiste

Level 4 — Two-Person Review (aspirational)
  → Il codice richiede review da due persone diverse
  → Il build è ermeticamente isolato
  → Dipendenze reproducibili (deterministic build)
```

```yaml
# Generare provenance SLSA con GitHub Actions (slsa-github-generator)
name: Build with SLSA Provenance
on: [push]
permissions:
  id-token: write
  contents: write
  actions: read

jobs:
  build:
    uses: slsa-framework/slsa-github-generator/.github/workflows/container_workflow.yml@v2
    with:
      image: ghcr.io/${{ github.repository }}
      registry-username: ${{ github.actor }}
    secrets:
      registry-password: ${{ secrets.GITHUB_TOKEN }}
```

```bash
# Verifica SLSA provenance con slsa-verifier
slsa-verifier verify-image \
  ghcr.io/myorg/myrepo@sha256:abc123... \
  --source-uri github.com/myorg/myrepo \
  --source-branch main \
  --slsa-verifier-config slsa-verifier-config.yaml
```

---

## Best Practices

- **Firmare i digest, non i tag**: i tag Docker sono mutabili (`:latest` cambia continuamente). Firmando il digest SHA256 si garantisce che si sta verificando esattamente quell'immagine
- **Keyless signing per CI/CD**: evita di gestire chiavi private statiche nel sistema di build. Ogni firma è legata all'identità OIDC del workflow specifico che ha eseguito il build
- **Verificare la firma prima del deploy**: integrare la verifica cosign nell'admission controller (vedi admission-control.md) — immagini non firmate non entrano in produzione
- **SBOM in Dependency-Track**: caricare automaticamente ogni SBOM generato in CI su Dependency-Track → alert automatica quando una nuova CVE colpisce una dipendenza usata da qualsiasi servizio
- **Rekor per audit trail**: ogni firma in Rekor è immutabile e pubblica — in caso di incidente, si può risalire esattamente quale workflow ha prodotto quale immagine e quando

## Riferimenti

- [Sigstore / Cosign Documentation](https://docs.sigstore.dev/)
- [SLSA Framework](https://slsa.dev/)
- [OWASP CycloneDX SBOM Standard](https://cyclonedx.org/)
- [Dependency-Track](https://dependencytrack.org/)
- [Rekor Transparency Log](https://rekor.sigstore.dev/)
