---
title: "Docker Compose"
slug: compose
category: containers
tags: [docker-compose, compose, multi-container, orchestration, development, production]
search_keywords: [docker compose production, docker compose healthcheck, docker compose depends_on, docker compose secrets, docker compose networks, docker compose profiles, docker compose override, compose file v3, docker compose scale, compose watch]
parent: containers/docker/_index
related: [containers/docker/networking, containers/docker/storage, containers/kubernetes/workloads]
official_docs: https://docs.docker.com/compose/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# Docker Compose

## Struttura del Compose File

Docker Compose v2 (plugin integrato in Docker CLI) usa il formato `compose.yaml` (raccomandato) o `docker-compose.yml`.

```yaml
# compose.yaml — struttura completa

name: myapp                        # nome del progetto (default: directory name)

services:
  # ── Ogni servizio è un container (o un gruppo di repliche)
  api:
    # ... definizione servizio

volumes:                           # named volumes dichiarati
  # ...

networks:                          # network dichiarate
  # ...

secrets:                           # secrets dichiarati (Swarm o file)
  # ...

configs:                           # config files (Swarm)
  # ...
```

---

## Definizione Servizio Completa

```yaml
services:
  api:
    # ── Immagine o Build ─────────────────────────────────────
    image: registry.company.com/myapp/api:${APP_VERSION:-latest}
    # oppure:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime          # multi-stage target
      args:
        BUILD_DATE: ${BUILD_DATE}
      cache_from:
        - registry.company.com/myapp/api:latest
      labels:
        org.opencontainers.image.version: "1.0.0"

    # ── Container Metadata ───────────────────────────────────
    container_name: myapp-api   # nome fisso (sconsigliato per scaling)
    hostname: api
    labels:
      app.tier: backend
      monitoring: prometheus

    # ── Porte ────────────────────────────────────────────────
    ports:
      - "8080:8080"             # host:container
      - "127.0.0.1:9090:9090"  # solo loopback (sicurezza)
      # - target: 8080          # forma long (più esplicita)
      #   published: 8080
      #   protocol: tcp
      #   mode: host

    # ── Environment ──────────────────────────────────────────
    environment:
      DATABASE_URL: postgresql://user:${DB_PASS}@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-info}
      APP_ENV: production
    env_file:
      - .env
      - .env.production

    # ── Networking ───────────────────────────────────────────
    networks:
      backend:
        aliases: [api-service]
        ipv4_address: 172.20.0.10  # IP statico (opzionale)
      frontend:

    # ── Volumes ──────────────────────────────────────────────
    volumes:
      - app-data:/app/data
      - ./config/app.yaml:/app/config.yaml:ro
      - /tmp/api:/tmp             # tmpfs alternativo su container

    # ── Risorse ──────────────────────────────────────────────
    deploy:                       # usato da Swarm E da compose (v3.9+)
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          cpus: "0.25"
          memory: 128M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
      replicas: 2                 # solo Swarm mode

    # ── Restart Policy ───────────────────────────────────────
    restart: unless-stopped      # no | always | on-failure | unless-stopped

    # ── Dipendenze e Healthcheck ─────────────────────────────
    depends_on:
      db:
        condition: service_healthy     # attende che db sia healthy
      redis:
        condition: service_started     # attende solo che sia avviato
      migrations:
        condition: service_completed_successfully  # attende job completato

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s          # grace period iniziale

    # ── Sicurezza ────────────────────────────────────────────
    user: "1001:1001"
    read_only: true              # filesystem read-only
    tmpfs:
      - /tmp:size=128m,mode=1777
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE

    # ── Logging ──────────────────────────────────────────────
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"
        labels: "app,tier"
    # oppure: json-file | syslog | journald | gelf | fluentd | awslogs

    # ── Lifecycle ────────────────────────────────────────────
    stop_grace_period: 30s       # tempo prima di SIGKILL dopo SIGTERM
    stop_signal: SIGTERM
    stdin_open: true             # -i
    tty: false                   # -t
    init: true                   # usa tini come PID 1 (gestione zombies)
```

---

## Healthcheck Pattern — depends_on con Condizioni

Il `depends_on` con `condition: service_healthy` è il modo corretto per gestire le dipendenze di avvio.

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: myapp
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s    # Postgres impiega tempo ad inizializzarsi

  redis:
    image: redis:7-alpine
    command: redis-server --save 60 1 --loglevel warning
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  migrations:
    image: myapp/api:latest
    command: python -m alembic upgrade head
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:secret@db:5432/myapp
    # Questo service "esce" (exit 0) quando le migrazioni sono completate

  api:
    image: myapp/api:latest
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrations:
        condition: service_completed_successfully  # aspetta le migrations
    environment:
      DATABASE_URL: postgresql://postgres:secret@db:5432/myapp
```

---

## Override e Profili — Dev vs Production

```yaml
# compose.yaml — BASE (comune a tutti gli ambienti)
services:
  api:
    image: myapp/api:${APP_VERSION}
    environment:
      DATABASE_URL: ${DATABASE_URL}
    networks:
      - backend

  db:
    image: postgres:16-alpine
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - backend

networks:
  backend:

volumes:
  db-data:
```

```yaml
# compose.override.yaml — DEV (applicato automaticamente in locale)
services:
  api:
    build: .                         # build locale invece di immagine
    volumes:
      - .:/app                       # hot reload
    environment:
      DEBUG: "true"
      LOG_LEVEL: debug
    ports:
      - "8080:8080"
      - "5678:5678"                  # debugger

  db:
    ports:
      - "5432:5432"                  # espone DB all'host per tool locali

  # Servizi solo in dev
  mailhog:
    image: mailhog/mailhog
    ports:
      - "8025:8025"
    profiles: [dev]
```

```yaml
# compose.production.yaml — PRODUZIONE
services:
  api:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "2"
          memory: 1G
    restart: always
    logging:
      driver: "awslogs"
      options:
        awslogs-group: "/myapp/api"
        awslogs-region: "eu-west-1"

  db:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    external: true
```

```bash
# Comandi
docker compose up -d                                    # usa base + override
docker compose -f compose.yaml -f compose.production.yaml up -d  # produzione
docker compose --profile dev up -d                      # abilita profili dev
```

**Profiles — Servizi Opzionali:**

```yaml
services:
  api:
    image: myapp/api          # nessun profile = sempre avviato

  docs:
    image: myapp/docs
    profiles: [docs]          # solo con: docker compose --profile docs up

  debug-tools:
    image: nicolaka/netshoot
    profiles: [debug]
    network_mode: service:api # stesso namespace rete del servizio api
```

---

## Secrets in Compose

```yaml
services:
  api:
    image: myapp/api
    secrets:
      - db_password
      - api_key
    # I secrets sono montati come file in /run/secrets/<name>
    # Leggili nel codice: open('/run/secrets/db_password').read().strip()
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password

secrets:
  # Modalità 1: file locale (dev)
  db_password:
    file: ./secrets/db_password.txt

  # Modalità 2: variabile d'ambiente
  api_key:
    environment: API_KEY_VALUE

  # Modalità 3: Swarm secret (produzione con Swarm)
  tls_cert:
    external: true              # creato con: docker secret create tls_cert cert.pem
```

---

## Compose Watch — Hot Reload Avanzato

**Compose Watch** (introdotto in Compose 2.22) sostituisce bind mount per hot reload con una logica più granulare.

```yaml
services:
  api:
    build: .
    develop:
      watch:
        # Sincronizza codice senza rebuild (hot reload)
        - action: sync
          path: ./src
          target: /app/src
          ignore:
            - "**/__pycache__"
            - "**/*.pyc"

        # Rebuild se cambiano le dipendenze
        - action: rebuild
          path: requirements.txt

        # Rebuild se cambia il Dockerfile
        - action: rebuild
          path: Dockerfile

        # Sincronizza e riavvia il container (più veloce del rebuild)
        - action: sync+restart
          path: ./config
          target: /app/config
```

```bash
# Avvia con watch mode
docker compose watch

# Equivalente ma più verboso
docker compose up --watch
```

---

## Comandi Essenziali

```bash
# Lifecycle
docker compose up -d                   # avvia in background
docker compose up --build              # forza rebuild immagini
docker compose down                    # ferma e rimuove container
docker compose down --volumes          # rimuove anche i volumi
docker compose down --remove-orphans   # rimuove container di servizi rimossi

# Scaling
docker compose up -d --scale api=3    # 3 repliche del servizio api

# Logs
docker compose logs -f                 # tutti i servizi
docker compose logs -f api db         # solo api e db
docker compose logs --since 1h api   # ultimi 60 minuti

# Exec e Run
docker compose exec api bash          # exec nel container del servizio
docker compose run --rm api python manage.py shell  # container one-shot

# Status
docker compose ps                     # status container
docker compose top                    # processi in esecuzione
docker compose port api 8080          # porta host mappata

# Config
docker compose config                  # merge e validazione del compose file
docker compose config --services      # lista servizi
docker compose config --volumes       # lista volumi

# Cleanup
docker compose images                 # immagini usate
docker system prune -a --volumes      # cleanup completo (ATTENZIONE in prod!)
```

---

## Riferimenti

- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Compose Watch](https://docs.docker.com/compose/file-watch/)
- [Compose Profiles](https://docs.docker.com/compose/profiles/)
- [Compose Secrets](https://docs.docker.com/compose/use-secrets/)
