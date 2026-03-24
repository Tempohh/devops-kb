---
title: "Monitoring & Observability"
slug: monitoring
category: monitoring
tags: [monitoring, observability, prometheus, grafana, opentelemetry, sre, alerting, metriche, log, tracce]
search_keywords: [monitoring, observability, osservabilità, prometheus, grafana, opentelemetry, loki, jaeger, alertmanager, sre, slo, sla, sli, metriche, log, tracce, tre pilastri]
parent: /
status: complete
difficulty: intermediate
last_updated: 2026-03-24
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

## Sezioni

| Sezione | Contenuto |
|---|---|
| [Fondamentali](fondamentali/_index.md) | OpenTelemetry, concetti base |
| [Tools](tools/_index.md) | Prometheus, Grafana, Loki |
| [Alerting](alerting/_index.md) | Alertmanager, routing, on-call |
| [SRE](sre/_index.md) | SLO/SLA/SLI, error budget |

## Relazioni

- [Kubernetes](../networking/kubernetes/_index.md) — Kube-state-metrics, node-exporter, service monitors
- [CI/CD](../ci-cd/_index.md) — DORA metrics, pipeline observability
- [Cloud AWS](../cloud/aws/monitoring/_index.md) — CloudWatch, X-Ray, AWS Observability
