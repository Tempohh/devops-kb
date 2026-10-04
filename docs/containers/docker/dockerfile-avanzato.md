---
title: "Dockerfile Avanzato"
slug: dockerfile-avanzato
category: containers
tags: [dockerfile, multi-stage, buildkit, cache, distroless, best-practices, layer-optimization]
search_keywords: [dockerfile best practices, multi-stage build docker, buildkit docker, layer caching optimization, distroless image, docker build cache, COPY vs ADD dockerfile, ARG vs ENV dockerfile, docker build secrets, slim docker image, dockerfile security hardening, BuildKit cache mount]
parent: containers/docker/_index
related: [containers/docker/sicurezza, containers/registry/_index, containers/docker/architettura-interna]
official_docs: https://docs.docker.com/reference/dockerfile/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
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
# syntax=docker/dockerfile:1
# ":1" segue l'ultima release stabile 1.x del frontend (fix e feature senza pin al minor);
# per build riproducibili al bit si pinna anche il digest: docker/dockerfile:1@sha256:...
FROM ubuntu:24.04
```

---

## Multi-Stage Builds — Pattern Fondamentale

I **multi-stage build** separano la fase di compilazione da quella di runtime, producendo immagini finali minimali senza tool di build.

```dockerfile
# syntax=docker/dockerfile:1

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

# Pre-compila il bytecode: lo stage finale copia solo src/ e le dipendenze
RUN python -m compileall -q src

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
# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM golang:1.25-alpine AS builder

# Valorizzati da buildx per ogni piattaforma target (cross-compile nativo, senza QEMU)
ARG TARGETOS
ARG TARGETARCH
# Alpine non ha git e .git è in .dockerignore: la versione si passa da fuori
ARG VERSION=dev

# Caching delle dipendenze Go separate dal build
WORKDIR /app

COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build \
        -ldflags="-w -s -X main.version=${VERSION}" \
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

# Utente non-root (UID 65534 = nobody; con /etc/passwd copiato risolve anche il nome)
USER 65534

ENTRYPOINT ["/server"]
```

---

## BuildKit Cache Mounts — Accelerare i Build

BuildKit introduce i **cache mount** che persistono la cache tra build successivi, evitando di riscaricare dipendenze ogni volta.

```dockerfile
# syntax=docker/dockerfile:1

# ── Python: cache pip ──────────────────────────────────
FROM python:3.12-slim
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install fastapi uvicorn[standard] sqlalchemy psycopg2-binary

# ── Node.js: cache npm ────────────────────────────────
FROM node:24-alpine
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

# ── Go: cache moduli e build cache ───────────────────
FROM golang:1.25
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build ./...

# ── Java/Maven: cache .m2 ────────────────────────────
FROM maven:3.9-eclipse-temurin-21
RUN --mount=type=cache,target=/root/.m2 \
    mvn dependency:go-offline

# ── Apt: cache packages (evita re-fetch dello stesso apt index) ──
FROM ubuntu:24.04
# Le immagini Debian/Ubuntu hanno docker-clean che svuota la cache dopo ogni apt:
# va disattivato, altrimenti il cache mount resta vuoto
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
# NIENTE "rm -rf /var/lib/apt/lists/*" qui: cancellerebbe il contenuto del mount.
# I mount non finiscono nel layer, quindi non serve ripulire.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev
```

!!! note "Il cache mount non è nel layer"
    Il contenuto di `--mount=type=cache` vive nella cache del builder, **non** nell'immagine finale: velocizza il build ma non riduce la dimensione. Su runner CI effimeri la cache è persa a ogni job, salvo export esplicito (`--cache-to type=gha` / `type=registry`).

**Build Secrets — Credenziali sicure senza leak:**

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Secret montato come tmpfs, NON scritto nei layer dell'immagine
RUN --mount=type=secret,id=pypi_token \
    pip install \
        --index-url https://token:$(cat /run/secrets/pypi_token)@pypi.company.com/simple \
        private-package

# Clona repository privato durante il build
RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN --mount=type=ssh \
    git clone git@github.com:company/private-lib.git /app/private-lib
# (serve un'immagine con git + openssh-client; python:slim non li include)
```

```bash
# Build con secrets
docker buildx build \
    --secret id=pypi_token,src=${HOME}/.pypi_token \
    --ssh default \
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
# Un ARG diverso dal precedente invalida la cache da qui in poi
ARG CACHEBUST=1
RUN fetch-latest-deps.sh
```

Alternative più mirate: `docker build --no-cache-filter <stage>` (ignora la cache di un solo stage) o `--no-cache` (tutto).

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
| ubuntu:24.04 | ~80MB | 20-50 | ✓ |
| debian:slim | ~50MB | 15-30 | ✓ |
| alpine:3.x | ~7MB | 2-5 | ✓ ash |
| distroless/static | ~2MB | 0-2 | ✗ |
| scratch | 0MB | 0 | ✗ |

!!! note "Valori indicativi"
    Dimensioni e conteggi CVE sono ordini di grandezza e variano nel tempo e con lo scanner: misurare sulla propria immagine (`trivy image`, `grype`). Per il debug di immagini senza shell esistono i tag `:debug` di distroless (con busybox) e gli ephemeral container.

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
# syntax=docker/dockerfile:1

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
        curl=7.88.*
# (con cache mount niente rm di /var/lib/apt/lists: vedi sezione cache mount;
#  senza cache mount: un solo RUN che termina con rm -rf /var/lib/apt/lists/*)

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

# ✗ Shell form (il PID 1 è /bin/sh, che di norma non inoltra SIGTERM)
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
# vendor/: togliere dall'ignore se Go usa `go mod vendor` nel build
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
    --provenance=mode=max \
    --sbom=true \
    .
# --provenance = attestation SLSA; --sbom = attestation SBOM (non usare commenti
# dopo il "\": spezzerebbero la riga di comando)

# Verifica il manifest multi-platform
docker buildx imagetools inspect registry.company.com/app:1.0.0
```

---

## Funzionalità Dockerfile Moderne

```dockerfile
# syntax=docker/dockerfile:1

# Heredoc: script multi-riga in un solo layer, senza catene di &&
RUN <<EOF
set -e
apt-get update
apt-get install -y --no-install-recommends ca-certificates
EOF

# COPY --link: il layer è indipendente dai precedenti, quindi non si invalida
# se cambia lo stage/base sottostante (cache e push più efficienti)
COPY --link --from=builder /app/server /server
```

**`ARG` vs `ENV`:** `ARG` esiste solo durante il build (non nel container a runtime) ma compare in `docker history`: **mai** per segreti (usare `--mount=type=secret`). `ENV` persiste nell'immagine e nel container. Un `ARG` dichiarato prima di `FROM` è visibile solo in `FROM`; va ridichiarato nello stage per usarlo.

**`COPY` vs `ADD`:** `COPY` copia e basta; `ADD` aggiunge download da URL e auto-estrazione di tar locali, comportamenti impliciti da evitare tranne in casi mirati.

```bash
# Lint del Dockerfile con le build checks integrate (buildx)
docker buildx build --check .
```

---

## Troubleshooting

### Scenario 1 — La cache BuildKit non viene riutilizzata tra build

**Sintomo:** Ogni `docker build` reinstalla le dipendenze da zero anche se `requirements.txt` / `package.json` non è cambiato. Il log `--progress=plain` mostra gli step `RUN` eseguiti (senza `CACHED`) su layer che dovrebbero essere cached.

**Causa:** Le cause più comuni sono: (a) il build context include file che cambiano spesso e vengono copiati troppo presto con `COPY . .`; (b) si usa un builder diverso tra run (ad es. `docker build` vs `docker buildx build --builder custom`); (c) i `--mount=type=cache` sono condivisi con `id` diversi.

**Soluzione:** Verificare l'ordine dei layer (dipendenze prima del codice), usare sempre lo stesso builder, e fissare l'id del cache mount.

```bash
# Ispeziona quali layer vengono invalidati
docker build --progress=plain . 2>&1 | grep -E "(CACHED|RUN)"

# Verifica builder attivo
docker buildx ls

# Pulisce la cache BuildKit per ripartire da zero
docker builder prune --filter type=exec.cachemount
```

---

### Scenario 2 — Errore "failed to solve: secret not found" durante il build

**Sintomo:** Il build fallisce con `failed to solve: secret not found: <id>` quando si usa `--mount=type=secret`.

**Causa:** Il secret dichiarato nel Dockerfile con `--mount=type=secret,id=<nome>` non è stato passato al comando `docker buildx build` tramite `--secret`.

**Soluzione:** Abbinare il parametro `--secret` al corrispondente `id` nel Dockerfile. Verificare che il file sorgente esista e sia leggibile.

```bash
# Il Dockerfile usa: --mount=type=secret,id=pypi_token
# Il comando build DEVE includere:
docker buildx build \
    --secret id=pypi_token,src=${HOME}/.secrets/pypi_token \
    .

# Verifica che il file sorgente esista
ls -la ${HOME}/.secrets/pypi_token

# Alternativa: passare il secret da variabile d'ambiente
docker buildx build \
    --secret id=pypi_token,env=PYPI_TOKEN \
    .
```

---

### Scenario 3 — Immagine multi-platform produce errore "exec format error" su ARM

**Sintomo:** Il container si avvia su `linux/amd64` ma fallisce con `exec /server: exec format error` su `linux/arm64` o viceversa.

**Causa:** Il builder multi-platform non è configurato o non ha i QEMU emulators installati. Oppure il binario è stato compilato staticamente per una sola architettura ma spinto come manifest multi-platform.

**Soluzione:** Configurare correttamente `buildx` con il driver `docker-container` e installare `binfmt` per QEMU.

```bash
# Installa emulatori QEMU per cross-compilation
docker run --privileged --rm tonistiigi/binfmt --install all

# Crea builder con driver container (supporta multi-platform)
docker buildx create \
    --name multiarch \
    --driver docker-container \
    --use

docker buildx inspect --bootstrap

# Verifica piattaforme supportate
docker buildx inspect multiarch | grep Platforms

# Build e verifica manifest
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --push \
    -t registry.company.com/app:1.0.0 .

docker buildx imagetools inspect registry.company.com/app:1.0.0
```

---

### Scenario 4 — Build lento per build context troppo grande

**Sintomo:** Il trasferimento del build context impiega decine di secondi prima che inizi il primo step. Il log mostra `transferring context: 500MB` (BuildKit; il vecchio builder: `Sending build context to Docker daemon  500MB`).

**Causa:** Manca o è incompleto il file `.dockerignore`. Cartelle come `node_modules/`, `.git/`, `dist/`, file di test o binari compilati vengono inclusi nel context anche se non usati nel Dockerfile.

**Soluzione:** Aggiungere un `.dockerignore` completo e verificare la dimensione del context prima del build.

```bash
# Misura la dimensione del build context senza fare il build
# (simula cosa viene inviato al daemon)
tar -czh . | wc -c

# Alternativa: usa un Dockerfile temporaneo per vedere i file nel context
docker build -f - . <<'EOF'
FROM alpine
COPY . /ctx
RUN du -sh /ctx && find /ctx -type f | head -50
EOF

# Verifica che .dockerignore sia applicato correttamente
cat .dockerignore

# Dopo aver aggiunto .dockerignore, confronta la dimensione
tar -czh --exclude-from=.dockerignore . | wc -c
```

!!! tip "Usa --file per build context minimo"
    Se il Dockerfile è in una sottocartella o vuoi limitare il context, specifica la directory esplicitamente:
    `docker build -f docker/Dockerfile ./src` invia solo `./src` come context.

---

## Riferimenti

- [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/)
- [BuildKit](https://docs.docker.com/build/buildkit/)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [BuildKit Cache Mounts](https://docs.docker.com/build/guide/mounts/)
- [Google Distroless](https://github.com/GoogleContainerTools/distroless)
- [docker buildx](https://docs.docker.com/build/builders/)
