---
title: "Container Image Scanning"
slug: image-scanning
category: security
tags: [image-scanning, trivy, vulnerabilità, cve, container-security, snyk]
search_keywords: [container image scanning, trivy vulnerability scanner, snyk container, grype anchore, cve container, docker image scan, kubernetes image scan, image scanning ci cd, vulnerability policy, critical cve blocking, image scanning admission, image registry scan, ecr image scanning, artifact registry scanning, oci image scanning, base image security, dockerfile security, layer scanning, sbom generation trivy, license scanning trivy, secret scanning trivy, trivy operator kubernetes, trivy helm, trivy configuration scan, misconfiguration scan, compliance scan cis]
parent: security/supply-chain/_index
related: [security/supply-chain/sbom-cosign, security/supply-chain/admission-control, security/compliance/audit-logging]
official_docs: https://aquasecurity.github.io/trivy/
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Container Image Scanning

## Panoramica

Un'immagine container è un sistema operativo minimale + dipendenze applicative + il codice. Ognuno di questi strati può contenere vulnerabilità note (CVE — Common Vulnerabilities and Exposures).

Lo scanning delle immagini rileva queste vulnerabilità prima che l'immagine arrivi in produzione. Ma lo scanning non è sufficiente da solo: deve essere integrato in un processo con policy chiare su cosa blocca il deploy e cosa è un warning accettabile — altrimenti si finisce in uno dei due estremi: bloccare tutto (impossibile deployare) o ignorare tutto.

**Trivy** (AquaSecurity) è lo scanner di riferimento open source: scansiona OS packages, dipendenze applicative (npm, pip, Maven, Go modules), configurazioni (Dockerfile, Kubernetes manifests, Terraform), secret accidentalmente inclusi, e genera SBOM.

---

## Trivy — Utilizzo Base

```bash
# Installa Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin v0.50.0

# Scan di un'immagine locale o remota
trivy image python:3.12-slim

# Output (estratto):
# python:3.12-slim (debian 12.4)
# ================================
# Total: 31 (UNKNOWN: 0, LOW: 21, MEDIUM: 7, HIGH: 3, CRITICAL: 0)
# ┌───────────────┬────────────────┬──────────┬──────────────┬──────────────────┐
# │    Library    │ Vulnerability  │ Severity │   Installed  │    Fixed Version │
# ├───────────────┼────────────────┼──────────┼──────────────┼──────────────────┤
# │ libc6         │ CVE-2023-4156  │ HIGH     │ 2.36-9+deb12 │                  │
# │ openssl       │ CVE-2023-5363  │ MEDIUM   │ 3.0.11-1~deb │ 3.0.12-1~deb12u1 │
# └───────────────┴────────────────┴──────────┴──────────────┴──────────────────┘
```

```bash
# Scan con output JSON (per integrazione CI)
trivy image --format json --output results.json myapp:latest

# Scan con exit code non-zero se ci sono vulnerabilità sopra la soglia
trivy image \
  --exit-code 1 \
  --severity CRITICAL,HIGH \
  --ignore-unfixed \       # Ignora CVE senza fix disponibile
  myapp:latest

# Scan di un filesystem locale (no Docker)
trivy fs --scanners vuln,secret,misconfig ./

# Scan Dockerfile (misconfigurazioni)
trivy config Dockerfile
# WARN  Dockerfile: Specify a tag in the FROM statement
# FAIL  Dockerfile: Don't use root user

# Scan dei secret nel codice sorgente
trivy fs --scanners secret ./src/
```

---

## Integrazione CI/CD

```yaml
# GitHub Actions — scan obbligatorio prima del push
name: Security Scan
on: [push, pull_request]

jobs:
  trivy-scan:
    runs-on: ubuntu-latest
    permissions:
      security-events: write    # Per upload a GitHub Security
      contents: read
    steps:
    - uses: actions/checkout@v4

    - name: Build image
      run: docker build -t ${{ github.repository }}:${{ github.sha }} .

    - name: Run Trivy — fail on CRITICAL/HIGH
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: '${{ github.repository }}:${{ github.sha }}'
        format: 'sarif'
        output: 'trivy-results.sarif'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
        ignore-unfixed: true

    - name: Upload Trivy results to GitHub Security
      uses: github/codeql-action/upload-sarif@v3
      if: always()    # Upload anche se il job ha fallito
      with:
        sarif_file: 'trivy-results.sarif'

    - name: Run Trivy — genera SBOM
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: '${{ github.repository }}:${{ github.sha }}'
        format: 'cyclonedx'
        output: 'sbom.json'

    - name: Upload SBOM artifact
      uses: actions/upload-artifact@v4
      with:
        name: sbom
        path: sbom.json
```

---

## Policy di Vulnerabilità — Cosa Bloccare, Cosa Accettare

La gestione delle vulnerabilità richiede una policy esplicita, non "blocco tutto":

```yaml
# .trivyignore — CVE accettati con motivazione e scadenza
# Sintassi: CVE-ID [expiry_date] [commento]

# Accettato: nessuna versione fissa disponibile, workaround applicato
CVE-2023-XXXX exp:2024-06-01 # libssl - workaround: TLS 1.3 only, monitored

# Accettato: non applicabile per il nostro use case (non esposto a input non fidato)
CVE-2023-YYYY exp:2024-03-01 # libxml2 - not exposed to untrusted XML input
```

```yaml
# Trivy policy as code (OPA/Rego integration)
# trivy.yaml — configurazione policy
vulnerability:
  ignore-unfixed: true
  severity:
    - CRITICAL    # sempre bloccante
    - HIGH        # bloccante salvo eccezioni documentate

misconfigurations:
  ignore:
    - AVD-DS-0001  # Specific Dockerfile check non applicabile

secret:
  enabled: true   # Blocca se trovati secret nel layer
```

---

## Trivy Operator — Scanning Continuo in Kubernetes

Il **Trivy Operator** scansiona continuamente tutte le immagini nel cluster, generando report come CRD Kubernetes:

```bash
# Installa Trivy Operator
helm install trivy-operator aquasecurity/trivy-operator \
  -n trivy-system \
  --create-namespace \
  --set trivy.ignoreUnfixed=true

# I report sono CRD standard Kubernetes
kubectl get vulnerabilityreports -A
# NAMESPACE    NAME                                        REPOSITORY       TAG     SCANNER   AGE
# production   replicaset-orders-789f-orders-container    my-registry/...  1.2.3   Trivy     2h

# Dettaglio
kubectl describe vulnerabilityreport replicaset-orders-789f-orders-container -n production

# Aggregato: quanti container hanno CVE critiche?
kubectl get vulnerabilityreports -A -o json | \
  jq '[.items[] | .report.summary | select(.criticalCount > 0)] | length'
```

```yaml
# Grafana dashboard per Trivy Operator metrics
# Metriche Prometheus esposte:
# trivy_image_vulnerabilities{severity="CRITICAL"} 3
# trivy_image_vulnerabilities{severity="HIGH"} 15

# Alert: nuova immagine con CVE critica in produzione
- alert: CriticalVulnerabilityInProduction
  expr: |
    trivy_image_vulnerabilities{
      severity="CRITICAL",
      namespace="production",
      fixed_version!=""
    } > 0
  for: 1h
  annotations:
    summary: "Immagine {{ $labels.image_tag }} ha {{ $value }} CVE critiche con fix disponibile"
```

---

## Scanning del Registro — ECR, Artifact Registry

I cloud registry offrono scanning integrato:

```bash
# AWS ECR — abilita enhanced scanning (usa Inspector)
aws ecr put-registry-scanning-configuration \
  --scan-type ENHANCED \
  --rules '[{
    "repositoryFilters": [{"filter": "*", "filterType": "WILDCARD"}],
    "scanFrequency": "CONTINUOUS_SCAN"
  }]'

# Recupera i risultati dello scan
aws ecr describe-image-scan-findings \
  --repository-name my-app \
  --image-id imageTag=latest

# Policy: blocca il pull di immagini con CVE critiche
# (da integrare nel deployment workflow)
CRITICAL_COUNT=$(aws ecr describe-image-scan-findings \
  --repository-name my-app \
  --image-id imageTag=$IMAGE_TAG \
  --query 'imageScanFindings.findingSeverityCounts.CRITICAL' \
  --output text)

if [ "$CRITICAL_COUNT" -gt "0" ]; then
  echo "BLOCCO: $CRITICAL_COUNT CVE critiche trovate"
  exit 1
fi
```

---

## Dockerfile Best Practices per Ridurre le Vulnerabilità

```dockerfile
# ✅ Base image minimale + version pinned
FROM python:3.12.1-slim-bookworm

# ✅ Non girare come root
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash appuser

# ✅ Update e cleanup in un singolo layer (riduce dimensione + vulnerabilità OS)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 && \
    rm -rf /var/lib/apt/lists/*

# ✅ Dipendenze separate dal codice (cache Docker più efficiente)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ✅ Utente non-root
USER appuser

# ✅ No SUID/SGID
RUN find / -perm /4000 -type f -exec chmod a-s {} \; 2>/dev/null || true

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Best Practices

- **Scan in CI/CD prima del build + scan del registry**: doppio check — il Trivy in CI cattura i problemi early; il registry scan (ECR/Artifact Registry) è la rete di sicurezza per immagini non passate per il CI
- **Bloccare solo CRITICAL con fix disponibile**: bloccare CVE senza fix costringe a restare su versioni vecchie. `--ignore-unfixed` + soglia CRITICAL è il bilanciamento corretto
- **Base image da organizzazione**: gestire un catalogo di base image approvate e aggiornate — ogni team non deve scegliere la propria
- **Trivy Operator per drift detection**: un'immagine sicura oggi può avere nuove CVE domani — il continual scanning nel cluster rileva il drift senza re-deploy

## Riferimenti

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Trivy Operator](https://aquasecurity.github.io/trivy-operator/)
- [AWS ECR Enhanced Scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning-enhanced.html)
- [OWASP Docker Security Cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
