---
title: "Linguaggi & Runtime"
slug: linguaggi
category: dev
tags: [linguaggi, runtime, java, go, python, nodejs, microservizi]
search_keywords: [linguaggi backend, runtime, java, go, golang, python, nodejs, node.js, spring boot, quarkus, graalvm, native image, startup time, footprint, microservizi, linguaggi per microservizi]
parent: dev/_index
related: []
official_docs: https://microservices.io/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Linguaggi & Runtime

Questa sezione documenta le scelte di linguaggio e runtime per microservizi Kubernetes-native, con focus su caratteristiche rilevanti per il deployment cloud: startup time, memory footprint, modello di concorrenza, ecosistema di librerie.

---

## Criteri di Scelta

| Criterio | Go | Java (Spring Boot) | Java (Quarkus/Native) | Python | Node.js |
|---|---|---|---|---|---|
| Startup time | ~10ms | ~2-5s | ~50ms | ~500ms | ~200ms |
| Memory footprint | ~10-30 MB | ~200-500 MB | ~50-100 MB | ~50-150 MB | ~50-100 MB |
| Throughput (HTTP) | Eccellente | Eccellente (JIT warm) | Eccellente | Buono | Buono (I/O bound) |
| Ecosystem | Buono (cloud-native) | Eccellente | Buono | Eccellente (ML/AI) | Buono |
| Ideal per | Sidecar, CLI, infra | CRUD enterprise | Serverless, FaaS | ML/AI, scripting | I/O bound, BFF |

!!! tip "Regola pratica"
    Per microservizi con SLA stringenti su startup (scale-to-zero, FaaS): Go o Quarkus Native. Per applicazioni enterprise con team Java esistente e ricco ecosistema: Spring Boot 3.x.

---

## Argomenti in questa sezione

- [Java Spring Boot](java-spring-boot.md) — Spring Boot 3.x per microservizi Kubernetes
- [Java Quarkus](java-quarkus.md) — Quarkus cloud-native: native build GraalVM, dev mode, MicroProfile, Panache
- [ASP.NET Core 8+](dotnet.md) — Minimal API vs Controller, DI lifetimes, BackgroundService, gRPC, .NET Aspire, HealthChecks
- [Go](go.md) — Goroutine, channel, GOMAXPROCS containerizzazione, framework HTTP (Gin/Echo), gRPC, graceful shutdown
- [Python](python.md) — FastAPI async, Pydantic v2, Uvicorn/Gunicorn workers, SQLAlchemy 2 async, GIL e containerizzazione
