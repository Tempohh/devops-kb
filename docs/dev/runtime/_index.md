---
title: "Runtime & Performance"
slug: runtime
category: dev
tags: [runtime, performance, jvm, tuning, profiling]
search_keywords: [runtime performance, jvm tuning, heap sizing, garbage collector, profiling, ottimizzazione microservizi]
parent: dev/_index
related: [dev/linguaggi/java-spring-boot, dev/linguaggi/java-quarkus]
official_docs: https://docs.oracle.com/en/java/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Runtime & Performance

Questa sezione documenta la configurazione e l'ottimizzazione dei runtime per microservizi in produzione su Kubernetes, con focus su heap sizing, garbage collector selection, profiling e prevenzione degli OOM.

---

## Argomenti in questa sezione

- [JVM Tuning per Kubernetes](jvm-tuning.md) — Heap sizing container-aware, scelta GC (G1GC/ZGC/Shenandoah), OOMKiller, profiling con async-profiler e JFR, JVM vs GraalVM Native
- [Resource Tuning Multi-Linguaggio](resource-tuning.md) — GOMAXPROCS/automaxprocs (Go), .NET ThreadPool sizing, Node.js UV_THREADPOOL_SIZE e cluster mode, Gunicorn worker formula (Python), CPU throttling CFS, profiling in produzione
