---
title: "Tools di Monitoring"
slug: monitoring-tools
category: monitoring
tags: [prometheus, grafana, loki, monitoring, observability, tools]
parent: monitoring/_index
related: [monitoring/fondamentali/opentelemetry, monitoring/alerting/alertmanager, monitoring/sre/slo-sla-sli]
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Tools di Monitoring

Gli strumenti principali per metriche, visualizzazione e log nell'ecosistema cloud-native.

## Argomenti

- [Prometheus](prometheus.md) — Scraping, PromQL, TSDB, alerting rules
- [Grafana](grafana.md) — Dashboard, visualizzazione, alerting multi-source
- [Loki](loki.md) — Log aggregation con labels, LogQL, stack PLG
- [Jaeger & Tempo](jaeger-tempo.md) — Backend distributed tracing, OTLP, sampling
- [OTel Collector su Kubernetes](otel-collector-kubernetes.md) — DaemonSet/Gateway pattern, pipeline receivers/processors/exporters, Operator
- [Prometheus: Scalabilità e Long-term Storage](prometheus-scalabilita.md) — Thanos, VictoriaMetrics, Grafana Mimir, remote write tuning, multi-cluster
