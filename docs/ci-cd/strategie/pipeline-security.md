---
title: "Pipeline Security — DevSecOps"
slug: pipeline-security
category: ci-cd
tags: [devsecops, sast, dast, sca, sbom, supply-chain, sigstore, cosign, slsa, secret-scanning]
search_keywords: [devsecops, shift left security, sast, dast, sca, sbom, software supply chain security, sigstore, cosign, slsa framework, in-toto, syft, grype, trivy, snyk, semgrep, ghas codeql, secrets scanning, gitleaks, trufflehog, attestation, provenance, supply chain attack]
parent: ci-cd/strategie/_index
related: [ci-cd/strategie/_index, ci-cd/github-actions/enterprise, ci-cd/jenkins/security-governance, security/supply-chain]
official_docs: https://slsa.dev/
status: complete
difficulty: expert
last_updated: 2026-03-28
---

# Pipeline Security — DevSecOps

## Panoramica

DevSecOps integra la sicurezza in ogni fase del ciclo di sviluppo software, trasformandola da un controllo finale (post-build, pre-deploy) a una responsabilità condivisa del team. Il principio "shift left" sposta i controlli di sicurezza il prima possibile nel processo: un secret trovato in un pre-commit hook costa ordini di grandezza meno di uno trovato in un security audit post-release. Questa guida copre tutti i livelli della pipeline security: dalla prevenzione dei secret leak, all'analisi statica e dinamica, alla firma crittografica degli artefatti e alla certificazione della supply chain secondo SLSA.

## 1. Shift Left — Sicurezza in Ogni Fase

```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│  Pre-commit  │    CI Build  │   CI Test    │  CD Deploy   │  Production  │
├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ gitleaks     │ SAST         │ Integration  │ Container    │ Runtime      │
│ trufflehog   │ (Semgrep,    │ test security│ scanning     │ scanning     │
│ hadolint     │  CodeQL)     │              │ (Trivy)      │ (Falco)      │
│ pre-commit   │ Hadolint     │ DAST (ZAP)   │ SBOM gen     │ SIEM         │
│ hooks        │ IaC scanning │              │ Image sign   │ monitoring   │
│              │ (tfsec, kics)│              │ (Cosign)     │              │
├──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│  Costo:  1x  │   Costo: 10x │  Costo: 50x  │ Costo: 100x  │ Costo: 1000x │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

## 2. Secret Scanning

### Pre-commit Hook con gitleaks

```bash
# Installazione gitleaks
brew install gitleaks   # macOS
# Linux: scaricare da github.com/gitleaks/gitleaks/releases

# Scansione manuale
gitleaks detect --source . --report-path gitleaks-report.json

# Scansione di un commit specifico
gitleaks detect --source . --log-opts="HEAD~1..HEAD"

# Installazione come pre-commit hook con pre-commit framework
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
        name: Detect secrets with gitleaks
        language: golang
        entry: gitleaks protect --staged --redact -v
        pass_filenames: false
```

### Configurazione gitleaks Custom

```toml
# .gitleaks.toml nella root del repository
title = "MyOrg Gitleaks Configuration"

# Estendi la configurazione di default
[extend]
useDefault = true

# Pattern aggiuntivi per secrets custom
[[rules]]
  id = "myorg-api-key"
  description = "MyOrg Internal API Key"
  regex = '''MYORG_[A-Z0-9]{32}'''
  keywords = ["MYORG_"]
  severity = "Critical"
  tags = ["api-key", "myorg"]

[[rules]]
  id = "internal-jwt-secret"
  description = "JWT Secret (base64 encoded > 32 chars)"
  regex = '''(?i)jwt[_\-\s]*secret[_\-\s]*[=:]\s*['"]{0,1}([A-Za-z0-9+/=]{32,})['"]{0,1}'''
  tags = ["jwt", "auth"]

# Path da ignorare (fixtures, documentazione)
[allowlist]
  paths = [
    '''(^|/)tests?/fixtures?/''',
    '''(^|/)docs?/''',
    '''\.example$''',
    '''\.sample$''',
  ]
  # Ignorare pattern specifici (es. placeholder)
  regexes = [
    '''EXAMPLE_SECRET_DO_NOT_USE''',
    '''your-secret-here''',
    '''<your-api-key>''',
  ]
  commits = [
    # SHA da ignorare (es. commit storico già ripulito)
    "a1b2c3d4e5f6",
  ]
```

### Integrazione in GitHub Actions

```yaml
name: Secret Scanning

on: [push, pull_request]

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0    # Full history per scan completo

      - name: Run gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}  # Per uso commercial

  trufflehog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: TruffleHog — scan secrets
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified    # Solo secrets verificati (meno falsi positivi)
```

## 3. SAST — Static Application Security Testing

### Semgrep (Open Source)

Semgrep è un motore di analisi statica basato su pattern matching. Supporta decine di linguaggi e ha migliaia di regole open source.

```yaml
# GitHub Actions con Semgrep
name: SAST — Semgrep

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read
  security-events: write  # Per upload SARIF

jobs:
  semgrep:
    runs-on: ubuntu-latest
    container:
      image: semgrep/semgrep:latest
    steps:
      - uses: actions/checkout@v4

      - name: Semgrep scan
        run: |
          semgrep ci \
            --config auto \
            --sarif \
            --output semgrep-results.sarif \
            --severity ERROR \
            --error   # Exit code non-zero se vulnerabilità trovate
        env:
          SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}  # Opzionale per Semgrep Cloud

      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: semgrep-results.sarif
```

### Regole Semgrep Custom

```yaml
# rules/security/no-sql-injection.yml
rules:
  - id: sql-injection-risk
    patterns:
      - pattern: |
          String $QUERY = "SELECT * FROM " + $INPUT;
      - pattern: |
          $STMT.execute("... " + $INPUT + " ...");
    message: >
      Potenziale SQL injection: costruzione diretta della query con input non sanitizzato.
      Usare PreparedStatement o parametri named.
    severity: ERROR
    languages: [java]
    metadata:
      cwe: CWE-89
      owasp: A03:2021

  - id: hardcoded-password
    patterns:
      - pattern: |
          String PASSWORD = "...";
      - pattern: |
          password = "$VALUE"
          where:
            - metavariable-regex:
                metavariable: $VALUE
                regex: '^[A-Za-z0-9!@#$%^&*()_+]{8,}$'
    message: Password hardcoded nel codice. Usare variabili d'ambiente o secret manager.
    severity: WARNING
    languages: [java, python, javascript]
```

```bash
# Scansione locale con regole custom
semgrep --config rules/security/ --config p/owasp-top-ten --config p/cwe-top-25 src/
```

### CodeQL (GitHub Advanced Security)

```yaml
# .github/workflows/codeql.yml
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 6 * * 1'

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    strategy:
      matrix:
        language: [java-kotlin, javascript-typescript, python]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
          queries: security-and-quality
          config: |
            paths-ignore:
              - test/**
              - vendor/**
      - if: matrix.language == 'java-kotlin'
        run: mvn --batch-mode compile -DskipTests
      - uses: github/codeql-action/analyze@v3
```

## 4. SCA — Software Composition Analysis

SCA analizza le dipendenze del progetto per vulnerabilità note (CVE) e problemi di licenza.

### OWASP Dependency-Check

```yaml
# GitHub Actions con OWASP Dependency-Check
- name: OWASP Dependency-Check
  uses: dependency-check/Dependency-Check_Action@main
  with:
    project: 'myapp'
    path: '.'
    format: 'HTML JUNIT SARIF'
    out: 'reports'
    args: >
      --enableRetired
      --failOnCVSS 7
      --suppression suppression.xml

- name: Upload results
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: reports/dependency-check-report.sarif
```

### Grype (Anchore) — Vuln Scanner

```bash
# Installazione
brew install anchore/grype/grype
# o: curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh

# Scan di un'immagine Docker
grype ghcr.io/my-org/myapp:v1.2.3 \
  --fail-on high \
  --output sarif \
  --file grype-results.sarif

# Scan del filesystem (analizza go.sum, pom.xml, package-lock.json, requirements.txt...)
grype dir:. \
  --fail-on medium \
  --output json \
  --file grype-results.json

# Formato tabella per output leggibile
grype ghcr.io/my-org/myapp:v1.2.3 -o table
```

### SBOM Generation con Syft

```bash
# Installazione Syft (Anchore)
brew install syft
# o: curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh

# Genera SBOM in formato CycloneDX JSON (raccomandato)
syft ghcr.io/my-org/myapp:v1.2.3 \
  -o cyclonedx-json \
  --file sbom.cdx.json

# Genera SBOM in formato SPDX (richiesto da alcune compliance)
syft ghcr.io/my-org/myapp:v1.2.3 \
  -o spdx-json \
  --file sbom.spdx.json

# Scan del codice sorgente (analizza manifest)
syft dir:. \
  -o cyclonedx-json \
  --file sbom-source.cdx.json

# Integrare con Grype per vulnerability scan del SBOM
grype sbom:./sbom.cdx.json --fail-on high
```

```yaml
# Pipeline completa SBOM + vuln scan
- name: Generate SBOM
  run: |
    curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
    syft ${{ env.IMAGE }}:${{ github.sha }} -o cyclonedx-json --file sbom.cdx.json

- name: Upload SBOM as artifact
  uses: actions/upload-artifact@v4
  with:
    name: sbom-${{ github.sha }}
    path: sbom.cdx.json
    retention-days: 90

- name: Scan SBOM for vulnerabilities
  run: |
    curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin
    grype sbom:./sbom.cdx.json --fail-on high --output sarif --file grype-results.sarif

- name: Upload vulnerability results
  uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: grype-results.sarif
```

## 5. Container Security

### Trivy — Vulnerability Scanner

```yaml
# GitHub Actions con Trivy
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE }}:${{ github.sha }}
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'         # Fallisce se trovate vuln CRITICAL/HIGH
    ignore-unfixed: true    # Ignora vuln senza patch disponibile
    vuln-type: 'os,library'
    scanners: 'vuln,config,secret'

# Trivy per IaC (Terraform, Kubernetes, Dockerfile)
- name: Trivy IaC scan
  uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'config'
    scan-ref: '.'
    format: 'table'
    exit-code: '1'
    severity: 'CRITICAL,HIGH,MEDIUM'
    trivy-config: trivy.yaml  # Configurazione custom

# trivy.yaml
severity:
  - CRITICAL
  - HIGH
misconfiguration:
  ignore-unfixed: false
  exit-code: 1
scan:
  security-checks:
    - vuln
    - config
    - secret
```

```bash
# Trivy da CLI: scan completo di un'immagine
trivy image \
  --severity CRITICAL,HIGH \
  --exit-code 1 \
  --format table \
  ghcr.io/my-org/myapp:v1.2.3

# Scan di un filesystem (per Dockerfile e config)
trivy config \
  --severity HIGH,CRITICAL \
  --exit-code 1 \
  ./k8s/

# Trivy con ignorelist (per falsi positivi noti)
trivy image \
  --ignorefile .trivyignore \
  ghcr.io/my-org/myapp:v1.2.3

# .trivyignore
# CVE-2023-12345  # Falso positivo: non raggiungibile nel nostro contesto
# CVE-2023-67890  # Patch disponibile in versione successiva (sprint 42)
```

### Hadolint — Dockerfile Linting

```yaml
# GitHub Actions con Hadolint
- name: Lint Dockerfile
  uses: hadolint/hadolint-action@v3.1.0
  with:
    dockerfile: Dockerfile
    format: sarif
    output-file: hadolint-results.sarif
    no-fail: false       # Fallisce se lint errors
    config: .hadolint.yaml

# .hadolint.yaml
failure-threshold: warning
ignore:
  - DL3008   # Pin versioni in apt: troppo restrittivo per alcune immagini base
  - DL3018   # Pin Alpine packages
trustedRegistries:
  - registry.mycompany.internal
  - gcr.io
  - ghcr.io
```

## 6. DAST — Dynamic Application Security Testing

DAST testa l'applicazione in esecuzione, simulando attacchi reali su endpoint HTTP.

```yaml
# OWASP ZAP — Baseline scan (veloce, ~5 min)
name: DAST — OWASP ZAP

on:
  workflow_dispatch:
  # Eseguito dopo deploy in staging
  deployment:
    environments: [staging]

jobs:
  dast:
    runs-on: ubuntu-latest
    steps:
      - name: ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.11.0
        with:
          target: 'https://staging.myapp.example.com'
          rules_file_name: '.zap/rules.tsv'    # Override di specifiche regole
          cmd_options: '-a'                     # Accetta certificati self-signed
          allow_issue_writing: true
          issue_title: 'ZAP Baseline Report'
          token: ${{ secrets.GITHUB_TOKEN }}

      # ZAP Full Scan (più approfondito, ~30-60 min)
      # Solo in scheduled pipeline, non in ogni PR
      - name: ZAP Full Scan
        if: github.event_name == 'schedule'
        uses: zaproxy/action-full-scan@v0.10.0
        with:
          target: 'https://staging.myapp.example.com'
          rules_file_name: '.zap/rules.tsv'
```

```tsv
# .zap/rules.tsv — Override delle regole ZAP
# WARN = warning, FAIL = failure, IGNORE = skip
# ID	Azione	Descrizione
10016	IGNORE	Web Browser XSS Protection Not Enabled (obsoleto in modern browser)
10020	IGNORE	X-Frame-Options Header Not Set (gestito da CSP)
10021	WARN	X-Content-Type-Options Header Missing
10038	FAIL	Content Security Policy (CSP) Header Not Set
10040	FAIL	Secure Pages Include Mixed Content
40012	FAIL	Cross Site Scripting (Reflected)
40014	FAIL	Cross Site Scripting (Persistent)
40018	FAIL	SQL Injection
```

## 7. Software Supply Chain Security

### Sigstore/Cosign — Firma Immagini Container

Cosign permette di firmare e verificare le immagini container. Con keyless signing (OIDC), non è necessario gestire chiavi crittografiche a lungo termine.

```yaml
# GitHub Actions — Firma keyless con OIDC
name: Build and Sign Container Image

on:
  push:
    branches: [main]

permissions:
  contents: read
  packages: write
  id-token: write           # OBBLIGATORIO per keyless signing

jobs:
  build-sign:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push image
        id: build
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          # Digest viene usato per la firma (non il tag mutabile)

      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign image with Cosign (keyless)
        run: |
          cosign sign \
            --yes \
            ghcr.io/${{ github.repository }}@${{ steps.build.outputs.digest }}
        # keyless signing:
        # - Cosign richiede un token OIDC da GitHub (id-token: write)
        # - Ottiene un certificato temporaneo da Fulcio (CA pubblica Sigstore)
        # - Registra la firma in Rekor (log di trasparenza pubblico)
        # - NON richiede una chiave privata da conservare

      - name: Attach SBOM attestation
        run: |
          # Genera SBOM
          syft ghcr.io/${{ github.repository }}@${{ steps.build.outputs.digest }} \
            -o cyclonedx-json > sbom.cdx.json

          # Firma e attacca il SBOM come attestazione all'immagine
          cosign attest \
            --yes \
            --predicate sbom.cdx.json \
            --type cyclonedx \
            ghcr.io/${{ github.repository }}@${{ steps.build.outputs.digest }}
```

```bash
# Verifica della firma in produzione (prima di pullare l'immagine)
cosign verify \
  --certificate-identity-regexp "https://github.com/my-org/my-repo/.github/workflows/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/my-org/my-repo:latest

# Verifica dell'attestazione SBOM
cosign verify-attestation \
  --certificate-identity-regexp "https://github.com/my-org/my-repo/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --type cyclonedx \
  ghcr.io/my-org/my-repo:latest
```

### SLSA Framework (Supply chain Levels for Software Artifacts)

SLSA definisce 4 livelli di sicurezza per la supply chain del software:

| Livello | Requisiti | Come raggiungere |
|---------|-----------|-----------------|
| **SLSA 1** | Provenance (origine) documentata | Build automatizzato con SBOM generato |
| **SLSA 2** | Build service non modificabile, versionato | CI/CD su piattaforma managed (GitHub Actions, GitLab CI) |
| **SLSA 3** | Build isolato, firma dell'artefatto | Runner ephemeral, Cosign firma, OIDC keyless |
| **SLSA 4** | Two-party review, hermetic build | Build hermetic (no network), code review obbligatorio, reproducible build |

**Raggiungere SLSA 3 con GitHub Actions:**

```yaml
# Genera provenance SLSA con action ufficiale
name: SLSA Build

on:
  push:
    tags: ['v*.*.*']

permissions:
  contents: read
  id-token: write           # Per keyless signing
  actions: read             # Per leggere il workflow

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      digests: ${{ steps.hash.outputs.digests }}
    steps:
      - uses: actions/checkout@v4

      - name: Build artifact
        run: |
          mvn --batch-mode package -DskipTests
          sha256sum target/myapp.jar > checksums.txt

      - name: Generate digest
        id: hash
        run: |
          echo "digests=$(sha256sum target/myapp.jar | base64 -w0)" >> $GITHUB_OUTPUT

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: myapp-jar
          path: target/myapp.jar

  # Job separato per generare la provenance
  provenance:
    needs: [build]
    permissions:
      actions: read
      id-token: write
      contents: write
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.0.0
    with:
      base64-subjects: ${{ needs.build.outputs.digests }}
      upload-assets: true    # Carica provenance come release asset
```

```bash
# Verifica SLSA provenance prima di usare l'artefatto
slsa-verifier verify-artifact target/myapp.jar \
  --provenance-path myapp.jar.intoto.jsonl \
  --source-uri github.com/my-org/my-repo \
  --source-tag v1.2.3
```

### in-toto — Attestazioni della Pipeline

```python
# in-toto permette di descrivere e verificare ogni step della pipeline
# come una catena di attestazioni (link files)

# Ogni step firma un "link" che descrive:
# - Material: input (file, immagini, commits)
# - Product: output (artefatti prodotti)
# - Command: comando eseguito
# - Environment: ambiente di esecuzione

# Esempio: generare una link file per il build step
import in_toto

# Il maintainer genera il layout (descrive i passaggi obbligatori)
layout = in_toto.models.layout.Layout()
layout.set_relative_expiration(months=1)

# Aggiungi i passi obbligatori
build_step = in_toto.models.step.Step(name="build")
build_step.expected_materials = ["MATCH src/* WITH PRODUCTS FROM checkout"]
build_step.expected_products = [
    "CREATE target/myapp.jar",
    "DISALLOW *"
]

test_step = in_toto.models.step.Step(name="test")
test_step.expected_materials = ["MATCH target/myapp.jar WITH PRODUCTS FROM build"]
```

## 8. Policy Gates con OPA/Conftest

```bash
# Installare Conftest
brew install conftest

# Struttura delle policy OPA
policies/
├── kubernetes.rego
├── dockerfile.rego
└── pipeline.rego
```

```rego
# policies/kubernetes.rego — Policy per manifesti Kubernetes
package kubernetes

import future.keywords.contains
import future.keywords.if

# DENY: container senza limiti di risorse
deny contains msg if {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.limits.cpu
    msg := sprintf("Container '%s' non ha limiti CPU configurati", [container.name])
}

deny contains msg if {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.limits.memory
    msg := sprintf("Container '%s' non ha limiti memoria configurati", [container.name])
}

# DENY: container in privileged mode
deny contains msg if {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    container.securityContext.privileged == true
    msg := sprintf("Container '%s' non deve essere eseguito in privileged mode", [container.name])
}

# DENY: immagine con tag 'latest'
deny contains msg if {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    endswith(container.image, ":latest")
    msg := sprintf("Container '%s' usa il tag 'latest' (non deterministico)", [container.name])
}

# WARN: no readiness probe
warn contains msg if {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.readinessProbe
    msg := sprintf("Container '%s' non ha readinessProbe configurato", [container.name])
}
```

```rego
# policies/dockerfile.rego — Policy per Dockerfile
package dockerfile

import future.keywords.contains
import future.keywords.if

# DENY: utente root nel Dockerfile
deny contains msg if {
    input[i].Cmd == "user"
    user := input[i].Value[0]
    lower(user) == "root"
    msg := "Dockerfile non deve eseguire come root. Aggiungere USER non-root."
}

# DENY: ADD invece di COPY (ADD può scaricare da URL)
deny contains msg if {
    input[i].Cmd == "add"
    not startswith(input[i].Value[0], "http")  # ADD locale (non URL)
    msg := "Usare COPY invece di ADD per file locali"
}

# WARN: EXPOSE di porta privilegiata (< 1024)
warn contains msg if {
    input[i].Cmd == "expose"
    port := to_number(input[i].Value[0])
    port < 1024
    msg := sprintf("Porta privilegiata %d esposta. Considerare porta > 1024", [port])
}
```

```yaml
# GitHub Actions — Policy gates in pipeline
- name: Validate Kubernetes manifests
  run: |
    curl -L https://github.com/open-policy-agent/conftest/releases/latest/download/conftest_Linux_x86_64.tar.gz \
      | tar xzf - -C /usr/local/bin conftest
    conftest test k8s/ \
      --policy policies/ \
      --output=json \
      --all-namespaces \
      --fail-on-warn    # Fallisce anche sui warning

- name: Validate Dockerfile
  run: |
    conftest test Dockerfile \
      --policy policies/dockerfile.rego \
      --parser dockerfile
```

## 9. Tabella Tools DevSecOps

| Tool | Categoria | Open Source | Integrazione principale | Note |
|------|-----------|-------------|------------------------|------|
| **gitleaks** | Secret scanning | Sì (MIT) | Pre-commit, CI/CD | ~20k stars, veloce |
| **trufflehog** | Secret scanning | Sì (AGPL-3) | CI/CD, pre-commit | Verifica secrets reali via API |
| **Semgrep** | SAST | Core OSS (LGPL) | CI/CD, IDE | 2500+ regole, custom rules |
| **CodeQL** | SAST | Gratis per OSS | GitHub (GHAS) | Profondo, analisi semantica |
| **SonarQube** | SAST + Quality | Community free | CI/CD, IDE | Quality gates configurabili |
| **OWASP Dep-Check** | SCA | Sì (Apache-2) | Maven, Gradle, CI/CD | NVD database |
| **Snyk** | SCA | Freemium | CI/CD, IDE | Veloce, fix suggeriti |
| **Grype** | SCA + Container | Sì (Apache-2) | CI/CD, CLI | Ancora da Anchore |
| **Trivy** | Container + IaC | Sì (Apache-2) | CI/CD, Docker Hub | All-in-one, raccomandato |
| **Hadolint** | Dockerfile lint | Sì (GPL-3) | CI/CD, IDE | Best practices Dockerfile |
| **OWASP ZAP** | DAST | Sì (Apache-2) | CI/CD, standalone | Standard per DAST |
| **Syft** | SBOM generation | Sì (Apache-2) | CI/CD, CLI | CycloneDX e SPDX |
| **Cosign** | Image signing | Sì (Apache-2) | CI/CD, K8s admission | Parte di Sigstore |
| **Conftest** | Policy gates | Sì (Apache-2) | CI/CD | OPA policy per qualsiasi config |
| **tfsec** / **tflint** | IaC SAST | Sì | CI/CD | Terraform security scanning |
| **kube-bench** | K8s hardening | Sì (Apache-2) | CI/CD, cluster audit | CIS Kubernetes Benchmark |

## Troubleshooting

### Scenario 1 — gitleaks rileva falsi positivi bloccando la pipeline

**Sintomo:** La pipeline fallisce per un "secret" rilevato che in realtà è un placeholder o un valore di test (es. `your-api-key-here`, valori in fixture di test).

**Causa:** gitleaks usa regex agressive che possono colpire valori non reali presenti in documentazione, test fixtures o file di esempio.

**Soluzione:** Aggiungere il pattern all'`allowlist` in `.gitleaks.toml`, oppure aggiungere un commento inline `# gitleaks:allow` per soppressioni puntuali.

```toml
# .gitleaks.toml — soppressione globale di placeholder noti
[allowlist]
  regexes = [
    '''your-api-key-here''',
    '''EXAMPLE_SECRET_DO_NOT_USE''',
    '''<replace-with-real-value>''',
  ]
  paths = [
    '''(^|/)tests?/fixtures?/''',
    '''\.example$''',
  ]
```

```bash
# Soppressione inline (aggiungere al file sorgente)
api_key = "your-api-key-here"  # gitleaks:allow

# Verifica che il file .gitleaks.toml venga rilevato
gitleaks detect --source . --config .gitleaks.toml --verbose
```

---

### Scenario 2 — Cosign sign fallisce con errore OIDC / permission denied

**Sintomo:** Il job di firma immagine fallisce con `error: getting ID token: failed to get token from GitHub Actions OIDC` o `403 Forbidden`.

**Causa:** Il workflow non ha il permesso `id-token: write` necessario per il keyless signing tramite OIDC. Frequente dopo refactoring del workflow o quando il job di firma è estratto in un job separato senza ridichiarare i permessi.

**Soluzione:** Aggiungere `id-token: write` ai permessi del job specifico che esegue `cosign sign`. I permessi si ereditano a livello workflow ma devono essere esplicitati per ogni job se il workflow usa la sezione `permissions` top-level.

```yaml
jobs:
  build-sign:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write    # OBBLIGATORIO per keyless signing Cosign
    steps:
      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign image
        run: |
          cosign sign --yes ghcr.io/${{ github.repository }}@${{ steps.build.outputs.digest }}
```

```bash
# Verifica locale che la firma sia stata registrata correttamente
cosign verify \
  --certificate-identity-regexp "https://github.com/my-org/my-repo/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  ghcr.io/my-org/my-repo@sha256:<digest>
```

---

### Scenario 3 — Trivy / Grype riportano vulnerabilità senza patch disponibile che bloccano la pipeline

**Sintomo:** La pipeline fallisce su CVE che hanno `fix: not available` — non esiste ancora una versione corretta del pacchetto a monte.

**Causa:** Il flag `--fail-on high` (o equivalente `exit-code: 1`) è applicato anche a vulnerabilità per cui non è disponibile alcuna patch, rendendo impossibile far passare la pipeline fino alla disponibilità della fix.

**Soluzione:** Usare `--ignore-unfixed` per escludere le vulnerabilità senza patch dal blocco. Per CVE specifici con falso positivo documentato, aggiungere all'ignorelist.

```yaml
# Trivy: ignora vuln senza patch
- name: Run Trivy
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE }}:${{ github.sha }}
    severity: 'CRITICAL,HIGH'
    exit-code: '1'
    ignore-unfixed: true    # Non blocca su CVE senza patch
```

```bash
# Grype: equivalente con --only-fixed
grype ghcr.io/my-org/myapp:latest \
  --fail-on high \
  --only-fixed        # Considera solo le vuln con fix disponibile

# Trivy: aggiungi CVE specifici da ignorare (falsi positivi documentati)
# .trivyignore
# CVE-2023-12345  # FP: libreria non raggiungibile nel runtime (commento obbligatorio)

trivy image --ignorefile .trivyignore ghcr.io/my-org/myapp:latest
```

---

### Scenario 4 — Semgrep genera troppi falsi positivi rallentando il processo di review

**Sintomo:** Il SAST con Semgrep produce decine di finding irrilevanti per il contesto del progetto (es. regole Java su un progetto Python, o pattern troppo generici), rendendo difficile identificare le vulnerabilità reali.

**Causa:** La config `--config auto` scarica l'intero ruleset automatico che include regole non pertinenti al linguaggio/framework del progetto. Oppure regole specifiche producono falsi positivi sistematici sul codebase.

**Soluzione:** Passare da `--config auto` a configurazioni mirate per linguaggio e framework. Sopprimere le regole rumorose con `# nosemgrep` inline o con `paths` di ignore nel file di configurazione.

```yaml
# .semgrep.yml — configurazione mirata al posto di --config auto
rules: []  # Nessuna regola custom locale

# In GitHub Actions: usare ruleset specifici
- name: Semgrep scan mirato
  run: |
    semgrep ci \
      --config p/python \
      --config p/django \
      --config p/owasp-top-ten \
      --severity ERROR \
      --sarif \
      --output semgrep.sarif
```

```bash
# Soppressione inline per un finding specifico (documentare il motivo)
result = eval(user_input)  # nosemgrep: dangerous-eval -- input validato upstream da schema JSON

# Verifica quale regola genera un finding specifico
semgrep --config auto --verbose src/app.py 2>&1 | grep "rule-id"

# Escludere directory dalla scansione
semgrep --config p/python \
  --exclude "tests/" \
  --exclude "migrations/" \
  src/
```

---

## Relazioni

??? info "Strategie CI/CD"
    DORA metrics, principi pipeline, shift left — il contesto strategico della pipeline security.

    **Approfondimento completo →** [Strategie CI/CD](_index.md)

??? info "GitHub Actions Enterprise"
    GHAS, CodeQL, Secret scanning, Dependabot, required workflows — implementazione security in GitHub.

    **Approfondimento completo →** [GitHub Actions Enterprise](../github-actions/enterprise.md)

??? info "Jenkins Security Governance"
    Hardening Jenkins, credential management, auditability, plugin security.

    **Approfondimento completo →** [Jenkins Security Governance](../jenkins/security-governance.md)

## Riferimenti

- [SLSA Framework](https://slsa.dev/)
- [Sigstore / Cosign documentation](https://docs.sigstore.dev/)
- [Sigstore Keyless Signing](https://docs.sigstore.dev/cosign/keyless/)
- [OWASP DevSecOps Guideline](https://owasp.org/www-project-devsecops-guideline/)
- [NIST SP 800-204D: DevSecOps](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-204D.pdf)
- [gitleaks configuration](https://github.com/gitleaks/gitleaks#configuration)
- [Semgrep rules registry](https://semgrep.dev/r)
- [Trivy documentation](https://aquasecurity.github.io/trivy/)
- [OWASP ZAP documentation](https://www.zaproxy.org/docs/)
- [in-toto specification](https://in-toto.io/in-toto/)
- [Conftest / OPA Rego](https://www.conftest.dev/)
- [CNCF Supply Chain Security paper](https://github.com/cncf/tag-security/blob/main/supply-chain-security/supply-chain-security-paper/CNCF_SSCP_v1.pdf)
