---
title: "Dockerfile Avanzato"
slug: dockerfile-avanzato
category: containers
tags: [dockerfile, multi-stage, buildkit, cache, distroless, best-practices, layer-optimization]
search_keywords: [dockerfile best practices, multi-stage build docker, buildkit docker, layer caching optimization, distroless image, docker build cache, COPY vs ADD dockerfile, ARG vs ENV dockerfile, docker build secrets, slim docker image, dockerfile security hardening, BuildKit cache mount]
parent: containers/docker/_index
related: [containers/docker/sicurezza, containers/registry/_index, containers/docker/architettura-interna]
official_docs: https://docs.docker.com/reference/dockerfile/
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# Dockerfile Avanzato

## BuildKit — Il Build Engine Moderno

**BuildKit** è il build engine di nuova generazione di Docker (default da Docker 23.0). Offre build parallele, migliore gestione della cache, e funzionalità avanzate come mount di segreti e cache bind mount.

```bash
# BuildKit è già default in Docker Desktop e Docker 23+
# Per versioni precedenti:
export DOCKER_BUILDKIT=1
docker build .

# Build con output dettagliato (mostra layer per layer)
docker build --progress=plain .

# Build con BuildKit CLI (buildx)
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --push \
    -t registry.company.com/app:1.0.0 .
```

**Sintassi frontend BuildKit:**

```dockerfile
# syntax=docker/dockerfile:1.6
# Questa riga abilita features avanzate dell'ultima versione
FROM ubuntu:22.04
```

---

## Multi-Stage Builds — Pattern Fondamentale

I **multi-stage build** separano la fase di compilazione da quella di runtime, producendo immagini finali minimali senza tool di build.

```dockerfile
# syntax=docker/dockerfile:1.6

# ──────────────────────────────────────────────────────────
# STAGE 1: deps — installa solo le dipendenze (cacheable)
# ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

# Copia solo i file di dipendenze PRIMA del codice
# Questo layer è cached finché requirements.txt non cambia
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ──────────────────────────────────────────────────────────
# STAGE 2: builder — compila l'applicazione
# ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Copia le dipendenze già installate
COPY --from=deps /root/.local /root/.local

# Copia il codice sorgente
COPY src/ ./src/
COPY pyproject.toml setup.cfg ./

# Compila wheel (se necessario) o prepara il bundle
RUN pip install --no-cache-dir --no-deps -e .

# ──────────────────────────────────────────────────────────
# STAGE 3: runtime — immagine finale minimale
# ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: utente non-root
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copia solo ciò che serve per l'esecuzione
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --from=builder --chown=appuser:appuser /app/src ./src

# Configura PATH per i pacchetti installati con --user
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Multi-stage per Go (immagine ~10MB finale):**

```dockerfile
# syntax=docker/dockerfile:1.6
FROM golang:1.22-alpine AS builder

# Caching delle dipendenze Go separate dal build
WORKDIR /app

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build \
        -ldflags="-w -s -X main.version=$(git describe --tags --always)" \
        -o /app/server \
        ./cmd/server

# ─── runtime: immagine da zero ───
FROM scratch AS runtime

# Certificati TLS (necessari per HTTPS calls)
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Timezone data
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# passwd file per l'utente non-root
COPY --from=builder /etc/passwd /etc/passwd

# Il binario compilato staticamente
COPY --from=builder /app/server /server

# Utente non-root (UID 65534 = nobody in alpine)
USER 65534

ENTRYPOINT ["/server"]
```

---

## BuildKit Cache Mounts — Accelerare i Build

BuildKit introduce i **cache mount** che persistono la cache tra build successivi, evitando di riscaricare dipendenze ogni volta.

```dockerfile
# syntax=docker/dockerfile:1.6

# ── Python: cache pip ──────────────────────────────────
FROM python:3.12-slim
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install fastapi uvicorn[standard] sqlalchemy psycopg2-binary

# ── Node.js: cache npm ────────────────────────────────
FROM node:20-alpine
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

# ── Go: cache moduli e build cache ───────────────────
FROM golang:1.22
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build ./...

# ── Java/Maven: cache .m2 ────────────────────────────
FROM maven:3.9-eclipse-temurin-21
RUN --mount=type=cache,target=/root/.m2 \
    mvn dependency:go-offline

# ── Apt: cache packages (evita re-fetch dello stesso apt index) ──
FROM ubuntu:22.04
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*
```

**Build Secrets — Credenziali sicure senza leak:**

```dockerfile
# syntax=docker/dockerfile:1.6

FROM python:3.12-slim

# Secret montato come tmpfs, NON scritto nei layer dell'immagine
RUN --mount=type=secret,id=pypi_token \
    pip install \
        --index-url https://token:$(cat /run/secrets/pypi_token)@pypi.company.com/simple \
        private-package

# Clona repository privato durante il build
RUN --mount=type=ssh \
    git clone git@github.com:company/private-lib.git /app/private-lib
```

```bash
# Build con secrets
docker buildx build \
    --secret id=pypi_token,src=~/.pypi_token \
    --ssh default=$SSH_AUTH_SOCK \
    .
```

!!! warning "Secrets nei layer"
    Senza `--mount=type=secret`, qualsiasi `RUN` che usa credenziali le scrive nel layer dell'immagine, anche se cancellate in step successivi. Con `docker history` o `docker save` i layer sono ispezionabili. **Usare sempre** `--mount=type=secret` per credenziali durante il build.

---

## Layer Caching Strategy

La cache BuildKit invalida un layer solo se i layer precedenti cambiano. L'**ordine delle istruzioni** è critico.

```dockerfile
# ✗ SBAGLIATO — la cache si invalida ad ogni modifica del codice
FROM python:3.12-slim
WORKDIR /app
COPY . .                          # invalida cache sempre
RUN pip install -r requirements.txt   # reinstalla SEMPRE

# ✓ CORRETTO — dipendenze cached separatamente
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .           # invalida cache solo se requirements.txt cambia
RUN pip install -r requirements.txt   # cached finché requirements.txt non cambia
COPY . .                          # codice: invalida solo il layer finale
```

**Regola del layer caching:**

```
ORDINE OTTIMALE PER MASSIMA CACHE HIT:

1. Immagine base (raramente cambia)
2. Dipendenze di sistema (apt/apk) — cambiano raramente
3. File di configurazione dipendenze (package.json, requirements.txt, go.mod)
4. Installazione dipendenze (npm install, pip install, go mod download)
5. Codice sorgente (cambia spesso)
6. Build del codice
7. Config runtime (ENTRYPOINT, CMD, EXPOSE)
```

**Cache invalidation esplicita:**

```bash
# Forza rebuild da un punto specifico con ARG
docker build --build-arg CACHEBUST=$(date +%s) .
```

```dockerfile
# Forza invalidazione di un singolo layer
ARG CACHEBUST=1
RUN --mount=type=cache,id=fetch-deps,target=/cache \
    CACHEBUST=${CACHEBUST} fetch-latest-deps.sh
```

---

## Immagini Distroless e Scratch

Le immagini **distroless** (Google) rimuovono shell, package manager e tutti i tool non necessari per l'esecuzione, riducendo drasticamente la superficie di attacco.

```dockerfile
# ── Esempio: Java con Distroless ───────────────────────
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /app
COPY . .
RUN ./gradlew bootJar --no-daemon

FROM gcr.io/distroless/java21-debian12 AS runtime
# Nessuna shell, nessun apt, nessun curl, nessun wget
# Solo JRE + librerie minime
WORKDIR /app
COPY --from=builder /app/build/libs/app.jar ./
USER nonroot
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

**Confronto superfici di attacco** — le **CVE** (Common Vulnerabilities and Exposures — identificativi standard delle vulnerabilità di sicurezza note, rilevate da scanner come Trivy o Grype):

| Base Image | Dimensione | Vulnerabilità CVE (tipico) | Shell |
|------------|-----------|---------------------------|-------|
| ubuntu:22.04 | ~80MB | 20-50 | ✓ |
| debian:slim | ~50MB | 15-30 | ✓ |
| alpine:3.19 | ~7MB | 2-5 | ✓ ash |
| distroless/static | ~2MB | 0-2 | ✗ |
| scratch | 0MB | 0 | ✗ |

```dockerfile
# ── scratch: solo per binari statici (Go, Rust) ─────────
FROM scratch
COPY --from=builder /app/binary /binary
COPY --from=builder /etc/ssl/certs/ /etc/ssl/certs/
ENTRYPOINT ["/binary"]
# Limitazione: nessun exec su container in debug, nessun ps, nessun sh
# Usare ephemeral debug containers: kubectl debug
```

---

## Best Practices — Checklist Completa

```dockerfile
# syntax=docker/dockerfile:1.6

# ✓ 1. Versione specifica dell'immagine base (no "latest")
FROM python:3.12.3-slim-bookworm AS base

# ✓ 2. Metadati OCI standard
LABEL org.opencontainers.image.title="My App" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/company/app" \
      org.opencontainers.image.vendor="Company Name"

# ✓ 3. Variabili d'ambiente documentate
ENV APP_PORT=8080 \
    APP_LOG_LEVEL=info \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1

# ✓ 4. Utente non-root creato prima di qualsiasi operazione
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup \
            --no-create-home --shell /bin/false appuser

# ✓ 5. Dipendenze sistema con versione pinned e cleanup in UN layer
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5=15.* \
        curl=7.88.* && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ✓ 6. Dipendenze applicazione con cache mount
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# ✓ 7. Codice sorgente (ultimo, massima cache reuse)
COPY --chown=appuser:appgroup . .

# ✓ 8. Utente non-root
USER appuser

# ✓ 9. Porta documentata
EXPOSE 8080

# ✓ 10. Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ✓ 11. Entrypoint + Cmd separati (entrypoint = eseguibile, cmd = args default)
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

**Anti-pattern comuni:**

```dockerfile
# ✗ Tag "latest" — imprevedibile, non riproducibile
FROM node:latest

# ✗ Layer separati per install + rm (il file è ancora nei layer!)
RUN apt-get update
RUN apt-get install -y build-essential
RUN rm -rf /var/lib/apt/lists/*
# Soluzioni: un solo RUN con && oppure BuildKit cache mount

# ✗ Root come utente finale
USER root

# ✗ Secrets hardcoded
ENV AWS_SECRET_KEY=xxx

# ✗ ADD per file locali (usa COPY — ADD è per URL e tar extraction)
ADD . /app

# ✗ COPY . . troppo presto
COPY . .
RUN pip install ...  # invalida cache ad ogni cambio di codice

# ✗ Doppio shell form (non riceve SIGTERM)
CMD "python server.py"     # eseguito come: /bin/sh -c "python server.py"
# Corretto: exec form
CMD ["python", "server.py"]  # riceve SIGTERM direttamente
```

---

## .dockerignore — Ridurre il Build Context

```dockerignore
# .dockerignore — esclude file dal build context
# Critico: riduce il trasferimento al daemon e impedisce leak di dati sensibili

# Version control
.git
.gitignore

# Secrets e configurazione locale
.env
.env.*
*.pem
*.key
secrets/

# Dipendenze (installate nel Dockerfile)
node_modules/
__pycache__/
*.pyc
.venv/
vendor/

# Output di build
dist/
build/
*.egg-info/
target/

# IDE e OS files
.idea/
.vscode/
*.DS_Store
Thumbs.db

# Test e docs (non servono nel container)
tests/
docs/
*.md
!README.md

# CI/CD files
.github/
.gitlab-ci.yml
Jenkinsfile

# Docker files di sviluppo alternativi
docker-compose*.yml
Dockerfile.dev
```

---

## Multi-Platform Builds — buildx

```bash
# Setup builder multi-piattaforma
docker buildx create \
    --name multiarch-builder \
    --driver docker-container \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --use

# Build e push multi-platform (manifest list OCI)
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag registry.company.com/app:1.0.0 \
    --tag registry.company.com/app:latest \
    --push \
    --provenance=true \       # SLSA provenance attestation
    --sbom=true \             # SBOM attestation
    .

# Verifica il manifest multi-platform
docker buildx imagetools inspect registry.company.com/app:1.0.0
```

---

## Riferimenti

- [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/)
- [BuildKit](https://docs.docker.com/build/buildkit/)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [BuildKit Cache Mounts](https://docs.docker.com/build/guide/mounts/)
- [Google Distroless](https://github.com/GoogleContainerTools/distroless)
- [docker buildx](https://docs.docker.com/build/builders/)
