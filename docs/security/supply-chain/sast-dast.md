---
title: "SAST e DAST — Application Security Testing"
slug: sast-dast
category: security
tags: [sast, dast, application-security, sonarqube, semgrep, owasp-zap, nuclei, shift-left, devsecops]
search_keywords: [sast, dast, static analysis, dynamic analysis, application security testing, sonarqube, semgrep, owasp zap, nuclei, shift left security, devsecops, code scanning, vulnerability testing, penetration testing automation, iast, rasp, sca, taint analysis]
parent: security/supply-chain/_index
related: [security/supply-chain/image-scanning, security/supply-chain/sbom-cosign, security/supply-chain/admission-control, ci-cd/github-actions/workflow-avanzati, ci-cd/strategie/pipeline-security]
official_docs: https://owasp.org/www-community/Source_Code_Analysis_Tools
status: complete
difficulty: intermediate
last_updated: 2026-10-03
---

# SAST e DAST — Application Security Testing

## Panoramica

**SAST** (Static Application Security Testing) analizza il codice sorgente o i bytecode **senza eseguire l'applicazione** — trova vulnerabilità direttamente nel codice durante lo sviluppo. **DAST** (Dynamic Application Security Testing) attacca l'applicazione **in esecuzione** simulando un attaccante esterno — trova vulnerabilità che emergono solo a runtime.

I due approcci sono complementari, non alternativi: SAST trova problemi nell'origine (SQL injection nel codice, secrets hardcoded, uso di API deprecate), DAST trova problemi nel comportamento reale (configurazioni errate, header mancanti, endpoint esposti). Inserirli entrambi nella pipeline CI/CD è la base del modello **shift-left security** — rilevare vulnerabilità prima che raggiungano la produzione.

Quando **non** usarli: SAST non può rilevare vulnerabilità di configurazione infrastrutturale (usa tool IaC scanning). DAST non funziona su codice non deployato. Né SAST né DAST sostituiscono il penetration testing manuale per applicazioni ad alto rischio.

## Concetti Chiave

!!! note "Tassonomia: SAST / DAST / IAST / SCA"
    - **SAST** — analisi statica del codice sorgente, whitebox
    - **DAST** — analisi dinamica dell'applicazione in esecuzione, blackbox
    - **IAST** (Interactive AST) — agente runtime dentro l'applicazione, grey-box (es. Contrast Security)
    - **SCA** (Software Composition Analysis) — analisi delle dipendenze (librerie open source), es. Dependabot, Snyk

!!! warning "False Positive e Coverage"
    SAST genera falsi positivi: lo strumento segnala codice che non è realmente vulnerabile. Impostare baseline e regole di soppressione è lavoro obbligatorio nella prima settimana di adozione, altrimenti il team inizia a ignorare tutti i finding.

### Vulnerabilità tipiche trovate da SAST
- SQL injection, XSS, path traversal, command injection (taint analysis)
- Secrets hardcoded (API key, password, certificati)
- Uso di funzioni crittografiche deprecate (`MD5`, `SHA1`, `DES`)
- Dipendenze con CVE note (overlap con SCA)
- Codice unreachable, null pointer dereference

### Vulnerabilità tipiche trovate da DAST
- Configurazioni errate HTTP (header mancanti: `Content-Security-Policy`, `HSTS`, `X-Frame-Options`)
- Autenticazione e gestione sessione difettosa
- Directory listing, file esposti (`.env`, backup, `robots.txt` sensibili)
- CORS misconfiguration
- Open redirect, SSRF, XXE

## Architettura / Come Funziona

### SAST — Pipeline di Analisi Statica

```
Codice Sorgente
      │
      ▼
  Parse AST ──► Control Flow Graph ──► Data Flow Graph
                                              │
                                       Taint Analysis
                                              │
                                       Pattern Matching
                                              │
                                        Finding List
                                              │
                           ┌──────────────────┴──────────────────┐
                           │                                      │
                    False Positive                         True Positive
                    (soppresso)                           (report + PR comment)
```

Il cuore di SAST è il **taint analysis**: traccia i dati non fidati (input utente) attraverso il grafo del programma fino ai sink pericolosi (query SQL, exec shell, file write). Se esiste un path senza sanitizzazione → vulnerabilità.

### DAST — Pipeline di Analisi Dinamica

```
App deployata (staging/test)
        │
        ▼
   Spider / Crawl ──► Mappa endpoint
        │
        ▼
   Active Scan ──► Inietta payload (SQLi, XSS, SSRF...)
        │
        ▼
   Analisi Risposta ──► Finding (status code, pattern nel body)
        │
        ▼
   Report + SARIF output
```

Il DAST richiede un ambiente raggiungibile: tipicamente **staging** o un ambiente dedicato CI/CD. Non eseguire DAST su produzione senza policy esplicita.

## Configurazione & Pratica

### SAST con Semgrep

Semgrep è open source, veloce, e supporta regole custom in YAML. Ha un registry pubblico con migliaia di regole mantenute da r2c e dalla community.

**Installazione e primo scan:**

```bash
# Installazione
pip install semgrep

# Scan con ruleset ufficiali (auto-detect linguaggio)
semgrep --config auto .

# Scan con set specifico OWASP Top 10
semgrep --config p/owasp-top-ten .

# Output SARIF (per GitHub Code Scanning)
semgrep --config auto --sarif -o results.sarif .
```

**Integrazione GitHub Actions:**

```yaml
# .github/workflows/sast.yml
name: SAST

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  semgrep:
    name: Semgrep Scan
    runs-on: ubuntu-latest
    permissions:
      security-events: write  # per upload SARIF

    steps:
      - uses: actions/checkout@v4

      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/owasp-top-ten
            p/secrets
            p/docker
          generateSarif: "1"

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: semgrep.sarif
        if: always()
```

**Regola custom Semgrep (esempio — rilevare hardcoded AWS key):**

```yaml
# .semgrep/custom-rules.yml
rules:
  - id: hardcoded-aws-key
    patterns:
      - pattern: |
          $VAR = "AKIA..."
    message: "Possibile AWS Access Key hardcoded in $VAR"
    languages: [python, go, javascript, java]
    severity: ERROR
    metadata:
      category: security
      cwe: CWE-798
```

**Soppressione falsi positivi:**

```python
# In linea — da usare con parsimonia e commento esplicativo
password = get_from_vault()  # nosemgrep: hardcoded-password — letto da Vault
```

---

### SAST con SonarQube

SonarQube è la soluzione enterprise più usata. Oltre al SAST offre quality gates, coverage, code smells e technical debt tracking.

**Deploy SonarQube Community (Docker):**

```yaml
# docker-compose.yml
services:
  sonarqube:
    image: sonarqube:community
    environment:
      SONAR_JDBC_URL: jdbc:postgresql://db:5432/sonar
      SONAR_JDBC_USERNAME: sonar
      SONAR_JDBC_PASSWORD: sonar
    volumes:
      - sonarqube_data:/opt/sonarqube/data
      - sonarqube_logs:/opt/sonarqube/logs
    ports:
      - "9000:9000"
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: sonar
      POSTGRES_PASSWORD: sonar
      POSTGRES_DB: sonar
    volumes:
      - postgresql:/var/lib/postgresql/data

volumes:
  sonarqube_data:
  sonarqube_logs:
  postgresql:
```

**Quality Gate (configurazione tipica):**

```
Condizioni Quality Gate "Sonar way":
  - Coverage su nuovo codice < 80% → FAIL
  - Duplicazioni su nuovo codice > 3% → FAIL
  - Maintainability rating < A → FAIL
  - Reliability rating < A → FAIL
  - Security rating < A → FAIL
  - Security Hotspots reviewed < 100% → FAIL
```

**Integrazione CI/CD (GitHub Actions + SonarCloud):**

```yaml
- name: SonarCloud Scan
  uses: SonarSource/sonarcloud-github-action@master
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
  with:
    args: >
      -Dsonar.projectKey=my-org_my-project
      -Dsonar.organization=my-org
      -Dsonar.sources=src
      -Dsonar.tests=tests
      -Dsonar.python.coverage.reportPaths=coverage.xml
```

---

### DAST con OWASP ZAP

OWASP ZAP (Zed Attack Proxy) è il DAST open source di riferimento. Supporta modalità active scan (aggressiva) e passive scan (solo osservazione del traffico).

!!! warning "Ambiente target"
    Eseguire ZAP solo su ambienti di test/staging dedicati. Lo scan attivo inietta payload e può corrompere dati o triggerare alert nei sistemi di monitoraggio.

**Scan base via Docker:**

```bash
# Full scan (spider + active scan) contro un'applicazione
docker run --rm \
  -v $(pwd)/zap-reports:/zap/wrk \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-full-scan.py \
  -t https://staging.myapp.example.com \
  -r report.html \
  -J report.json

# Baseline scan (passivo, più veloce — adatto per PR check)
docker run --rm \
  -v $(pwd)/zap-reports:/zap/wrk \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
  -t https://staging.myapp.example.com \
  -r baseline-report.html
```

**Integrazione GitHub Actions:**

```yaml
# .github/workflows/dast.yml
name: DAST

on:
  push:
    branches: [main]

jobs:
  dast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Deploy app su ambiente ephemeral (es. docker-compose)
      - name: Start application
        run: docker compose up -d

      - name: Wait for app
        run: |
          for i in {1..30}; do
            curl -sf http://localhost:8080/health && break
            sleep 2
          done

      - name: OWASP ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.12.0
        with:
          target: 'http://localhost:8080'
          rules_file_name: '.zap/rules.tsv'
          cmd_options: '-a'  # include ajax spider

      - name: Upload ZAP Report
        uses: actions/upload-artifact@v4
        with:
          name: zap-report
          path: report_html.html
        if: always()
```

**File di soppressione ZAP (`.zap/rules.tsv`):**

```tsv
10015	IGNORE	(Incomplete or No Cache-control Header Set)
10027	IGNORE	(Information Disclosure - Suspicious Comments)
90022	IGNORE	(Application Error Disclosure)
```

---

### DAST con Nuclei

Nuclei è un tool di vulnerability scanning basato su **template YAML**. Più flessibile di ZAP per scanning di API e infrastruttura; eccellente per CVE specifici e misconfiguration check.

```bash
# Installazione
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# Update template (obbligatorio alla prima run)
nuclei -update-templates

# Scan con template di severity alta/critica
nuclei -u https://staging.myapp.example.com \
       -severity high,critical \
       -o nuclei-results.txt

# Scan per categoria specifica
nuclei -u https://staging.myapp.example.com \
       -tags misconfig,exposure,cve \
       -o nuclei-results.txt \
       -json

# Scan su lista di target (utile per microservizi)
nuclei -list targets.txt \
       -tags api \
       -severity medium,high,critical \
       -o results.json \
       -json
```

**Template Nuclei custom (esempio — check header di sicurezza):**

```yaml
# templates/security-headers.yaml
id: missing-security-headers

info:
  name: Missing Security Headers
  author: team-security
  severity: medium
  tags: misconfig,headers

http:
  - method: GET
    path:
      - "{{BaseURL}}"
    matchers-condition: or
    matchers:
      - type: dsl
        dsl:
          - "!contains(tolower(header), 'x-frame-options')"
        name: missing-x-frame-options
      - type: dsl
        dsl:
          - "!contains(tolower(header), 'content-security-policy')"
        name: missing-csp
```

---

### Pipeline Security Completa — Esempio Integrato

```yaml
# .github/workflows/security.yml — pipeline completa SAST + DAST
name: Security Pipeline

on:
  push:
    branches: [main]
  pull_request:

jobs:
  sast:
    name: SAST (Semgrep)
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: returntocorp/semgrep-action@v1
        with:
          config: p/owasp-top-ten p/secrets
          generateSarif: "1"
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: semgrep.sarif
        if: always()

  secrets-scan:
    name: Secret Detection (Gitleaks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # storia completa per scan retroattivo
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  dast:
    name: DAST (ZAP Baseline)
    runs-on: ubuntu-latest
    needs: []  # parallelo con SAST
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Start app
        run: docker compose up -d --wait
      - uses: zaproxy/action-baseline@v0.12.0
        with:
          target: 'http://localhost:8080'
      - uses: actions/upload-artifact@v4
        with:
          name: zap-report
          path: report_html.html
        if: always()
```

## Best Practices

**Shift-left graduale:**

1. Iniziare con **secrets scanning** (Gitleaks, git-secrets) — zero falsi positivi, impatto immediato
2. Aggiungere SAST con regole conservative (solo severity HIGH/CRITICAL) — espandere dopo aver stabilito la baseline
3. Introdurre DAST su ambiente staging con scan passivo (baseline) prima di quello attivo
4. Solo dopo stabilizzazione → Quality Gate bloccante in pipeline

**Gestione finding:**

```
Finding rilevato
       │
       ├── True Positive → fix entro SLA (CRITICAL: 24h, HIGH: 7gg, MEDIUM: 30gg)
       │
       ├── False Positive → soppressione con commento (nosemgrep / ZAP rules)
       │                    + registrazione nel tracking system
       │
       └── Accepted Risk → eccezione documentata con approvazione security team
                           + data di scadenza (max 90gg per HIGH)
```

**Regole pratiche:**

- Non bloccare le PR finché non si hanno baseline consolidate — in fase iniziale usare `continue-on-error: true` e raccogliere dati
- Separare DAST in job dedicato su ambienti effimeri — mai sullo stesso ambiente condiviso dal QA
- Aggiornare i template Nuclei e i ruleset Semgrep almeno ogni 30 giorni
- Per SonarQube: non abbassare il Quality Gate per "far passare" le build — è il segnale che il progetto ha debito tecnico reale

!!! tip "Secrets First"
    Secrets hardcoded sono il finding più critico e quello con **zero falsi positivi** se configurato correttamente. Aggiungere Gitleaks o `truffleHog` è il primo passo da fare, prima ancora di SAST completo.

## Troubleshooting

### Scenario 1 — Semgrep: troppi falsi positivi

**Sintomo**: la PR si riempie di finding irrilevanti, il team inizia a ignorare i commenti del bot.

**Causa**: `--config auto` carica regole generiche (anche `audit`, a bassa precisione) che non conoscono le sanitizzazioni custom del progetto.

**Soluzione**: individuare le regole più rumorose, escluderle con `--exclude-rule` o `.semgrepignore` (per path) e restringere la severity.

```bash
# Regole con più finding
semgrep --config auto --json . | \
  jq '[.results[].check_id] | group_by(.) | map({rule: .[0], count: length}) | sort_by(-.count)'

# Escludi una regola rumorosa e tieni solo severity ERROR
semgrep --config p/owasp-top-ten \
  --exclude-rule javascript.express.security.audit.xss.mustache.missing-escaping \
  --severity ERROR .

# Escludi path non rilevanti (test, vendor)
printf 'tests/\nvendor/\nnode_modules/\n' > .semgrepignore
```

### Scenario 2 — ZAP: scan troppo lento o in timeout

**Sintomo**: il job DAST supera il timeout della CI o l'applicazione staging risponde 5xx durante lo scan.

**Causa**: spider e active scan generano migliaia di richieste con troppi thread paralleli per host, saturando un ambiente di test piccolo.

**Soluzione**: limitare la durata dello spider (`-m`) e dello scan (`-T`), ridurre i thread per host; usare `zap-baseline.py` (passivo) sulle PR e il full scan solo in schedule notturno. I commenti non possono stare dopo il `\` di continuazione riga (rompono il comando).

```bash
# -m: minuti max spider | -T: minuti max totali | -z: opzioni ZAP interne
zap-full-scan.py \
  -t https://staging.myapp.example.com \
  -m 5 \
  -T 30 \
  -z "-config scanner.threadPerHost=2"
```

### Scenario 3 — SonarQube: Quality Gate rosso su codice legacy

**Sintomo**: ogni PR fallisce il Quality Gate per problemi che non ha introdotto.

**Causa**: il "New Code Period" copre tutta la storia, quindi il debito pregresso viene contato come codice nuovo.

**Soluzione**: definire il New Code relativo a un branch di riferimento (o alla versione precedente), così il gate valuta solo le modifiche della PR.

```properties
# sonar-project.properties
sonar.newCode.referenceBranch=main
```

```bash
# Verifica lo stato del gate via API
curl -s -u "$SONAR_TOKEN:" \
  "https://sonar.example.com/api/qualitygates/project_status?projectKey=my-org_my-project" | jq '.projectStatus'
```

### Scenario 4 — Nuclei: falsi positivi o scan vuoto su endpoint autenticati

**Sintomo**: Nuclei segnala "exposure" su pagine di login/redirect (HTTP 302/401) oppure non trova nulla sulle API protette.

**Causa**: senza credenziali il template vede solo redirect o errori, che alcuni matcher interpretano male; le API protette non vengono mai raggiunte.

**Soluzione**: passare l'header di autenticazione, limitare ai tag pertinenti e fare debug sul singolo template con `-debug`.

```bash
nuclei -u https://staging.myapp.example.com \
       -H "Authorization: Bearer $TOKEN" \
       -tags api \
       -severity high,critical

# Debug di un singolo template
nuclei -u https://staging.myapp.example.com -t templates/security-headers.yaml -debug
```

### Scenario 5 — Upload SARIF fallisce su GitHub Code Scanning

**Sintomo**: lo step `upload-sarif` termina con `Resource not accessible by integration` oppure il file non viene trovato.

**Causa**: mancano i permessi `security-events: write` (es. PR da fork, dove il token è read-only) oppure il nome del file SARIF non coincide con quello prodotto dal tool.

**Soluzione**: dichiarare i permessi nel job, saltare l'upload per le PR da fork e verificare il path del SARIF prima dell'upload.

```bash
# Verifica che il SARIF esista e sia JSON valido
ls -l semgrep.sarif && jq '.runs[0].results | length' semgrep.sarif
```

```yaml
permissions:
  security-events: write
  contents: read
```

## Relazioni

??? info "Image Scanning — Complementarietà"
    Image scanning (Trivy) analizza le vulnerabilità nelle **immagini container e nelle dipendenze** (CVE nei package OS e librerie). SAST analizza le vulnerabilità nel **codice applicativo custom**. Insieme coprono la supply chain completa: codice sorgente + dipendenze + runtime.

    **Approfondimento completo →** [Image Scanning](image-scanning.md)

??? info "SBOM e Cosign — Firma degli Artifact"
    SBOM documenta le dipendenze (risultato complementare a SCA). Cosign firma gli artifact dopo che SAST/DAST sono passati — la firma attesta che il codice ha superato i security gate.

    **Approfondimento completo →** [SBOM e Cosign](sbom-cosign.md)

??? info "Admission Control — Enforcement a Runtime"
    OPA Gatekeeper e Kyverno possono bloccare deployment di immagini che non hanno associato un report SAST/DAST approvato, chiudendo il ciclo shift-left.

    **Approfondimento completo →** [Admission Control](admission-control.md)

## Riferimenti

- [OWASP SAST Tools](https://owasp.org/www-community/Source_Code_Analysis_Tools)
- [OWASP DAST Tools](https://owasp.org/www-community/Vulnerability_Scanning_Tools)
- [Semgrep Rules Registry](https://semgrep.dev/r)
- [OWASP ZAP Documentation](https://www.zaproxy.org/docs/)
- [Nuclei Templates](https://github.com/projectdiscovery/nuclei-templates)
- [OWASP Top 10 2021](https://owasp.org/www-project-top-ten/)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
