---
title: "Monitoring & Observability"
slug: monitoring
category: monitoring
tags: [monitoring, observability, prometheus, grafana, opentelemetry, sre, alerting, metriche, log, tracce]
search_keywords: [monitoring, observability, osservabilità, prometheus, grafana, opentelemetry, loki, jaeger, alertmanager, sre, slo, sla, sli, metriche, log, tracce, tre pilastri]
parent: /
status: needs-review
difficulty: intermediate
last_updated: 2026-09-27
---

# Monitoring & Observability

La sezione copre l'osservabilità nei sistemi distribuiti moderni: dai tre pilastri (metriche, log, tracce) agli strumenti cloud-native, fino alle pratiche SRE per misurare e garantire la reliability.

## I Tre Pilastri

| Pilastro | Strumenti | Risponde a |
|---|---|---|
| **Metriche** | Prometheus, Grafana | "Il sistema è lento?" |
| **Log** | Loki, Elasticsearch | "Cosa è successo esattamente?" |
| **Tracce** | Jaeger, Tempo, Zipkin | "Dove nel sistema è il problema?" |

[OpenTelemetry](fondamentali/opentelemetry.md) è lo standard che unifica i tre pilastri con un unico SDK e protocollo (OTLP).

!!! note "Quarto segnale: profiling continuo"
    Oltre ai tre pilastri classici, il [continuous profiling](tools/continuous-profiling.md) aggiunge un quarto segnale — dati a livello di codice (stack trace, CPU, memoria) campionati in continuo in produzione. Risponde a "quale riga di codice consuma le risorse?", una domanda che metriche/log/tracce da sole non coprono.

## Sezioni

| Sezione | Contenuto |
|---|---|
| [Fondamentali](fondamentali/_index.md) | OpenTelemetry, concetti base |
| [Tools](tools/_index.md) | Prometheus, Grafana, Loki, continuous profiling |
| [Alerting](alerting/_index.md) | Alertmanager, routing, on-call |
| [SRE](sre/_index.md) | SLO/SLA/SLI, error budget |

## Relazioni

- [Kubernetes](../networking/kubernetes/_index.md) — Kube-state-metrics, node-exporter, service monitors
- [CI/CD](../ci-cd/_index.md) — DORA metrics, pipeline observability
- [Cloud AWS](../cloud/aws/monitoring/_index.md) — CloudWatch, X-Ray, AWS Observability
