---
title: "AWS Monitoring e Observability"
slug: monitoring
category: cloud
tags: [aws, cloudwatch, x-ray, opentelemetry, grafana, prometheus, monitoring, observability, tracing, metrics, logs]
search_keywords: [cloudwatch, x-ray, distributed tracing, opentelemetry, adot, aws distro opentelemetry, managed grafana, managed prometheus, container insights, application insights, emf embedded metric format, log insights, alarms, dashboards, monitoring observability]
parent: cloud/aws/_index
related: [cloud/aws/monitoring/cloudwatch, cloud/aws/monitoring/observability, cloud/aws/security/compliance-audit]
official_docs: https://aws.amazon.com/cloudwatch/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS Monitoring e Observability

L'observability in AWS si basa sui tre pilastri tradizionali — **Metrics**, **Logs** e **Traces** — integrati da servizi managed che eliminano l'overhead operativo di gestire stack di monitoring self-hosted.

---

## Servizi di Monitoring AWS

<div class="grid cards" markdown>

-   **Amazon CloudWatch**

    ---

    Il servizio di monitoring principale: metriche, log, allarmi, dashboards, Log Insights, EMF. Integrazione nativa con tutti i servizi AWS.

    [:octicons-arrow-right-24: CloudWatch](cloudwatch.md)

-   **X-Ray, OpenTelemetry e Observability**

    ---

    Distributed tracing (X-Ray), AWS Distro for OpenTelemetry (ADOT), Amazon Managed Grafana, Amazon Managed Service for Prometheus.

    [:octicons-arrow-right-24: Observability](observability.md)

</div>

---

## I Tre Pilastri dell'Observability

```
METRICS                LOGS                   TRACES
─────────              ────────               ──────────
Cosa sta               Cosa è                 Dove va il
succedendo             successo               tempo nella
(numeri nel            (eventi                richiesta
 tempo)                testuali)              (latency map)

CloudWatch             CloudWatch             AWS X-Ray
Metrics                Logs                   ADOT
Prometheus             OpenSearch             Jaeger
(AMP)                  S3 + Athena            Zipkin
```

---

## Quick Reference — Strumenti

| Scenario | Strumento | Note |
|---------|----------|------|
| Metriche AWS native | CloudWatch Metrics | Automatico per servizi managed |
| Metriche OS/App custom | CloudWatch Agent + Custom Metrics | Richiede SDK/agent |
| Log da servizi AWS | CloudWatch Logs | Lambda, ECS, EKS via Fluent Bit |
| Analisi log | CloudWatch Log Insights | SQL-like query |
| Allarmi | CloudWatch Alarms | SNS, Auto Scaling, EC2 actions |
| Dashboard | CloudWatch Dashboards + Grafana | Cross-account, cross-Region |
| Distributed tracing | AWS X-Ray | Integra con Lambda, ECS, EC2, API GW |
| Vendor-neutral tracing | ADOT (OpenTelemetry) | Multi-backend |
| Prometheus metrics | AMP (Amazon Managed Prometheus) | PromQL, remote write |
| Grafana managed | Amazon Managed Grafana | SSO, multi-datasource |

---

## Architettura di Observability Consigliata

### Per Applicazioni Cloud-Native AWS

```
EC2 / ECS / Lambda
  └── CloudWatch Agent (metriche OS + log applicativi)
  └── X-Ray SDK (distributed tracing)
  └── EMF (embedded metrics nel log)

ALB / API Gateway / Lambda
  └── CloudWatch Metrics (automatiche)
  └── Access Logs → CloudWatch Logs o S3

CloudWatch Logs
  └── Log Insights (query ad-hoc)
  └── Subscription Filters → Lambda / Kinesis (real-time)
  └── Metric Filters (estrarre metriche da log)

CloudWatch Alarms
  └── SNS → PagerDuty / Slack
  └── Auto Scaling (scale out/in)
  └── EC2 Auto Recovery

X-Ray
  └── Service Map (visualizzazione dipendenze)
  └── Trace Analytics (latency, error rate per endpoint)
```

### Per Applicazioni Kubernetes (EKS)

```
EKS Pods
  └── ADOT Collector (DaemonSet)
      ├── Metriche → AMP (Prometheus Remote Write)
      ├── Traces → X-Ray
      └── Logs → CloudWatch Container Insights

Amazon Managed Grafana
  └── Data Sources: CloudWatch + AMP + X-Ray
  └── SSO via IAM Identity Center
  └── Alerting → SNS / PagerDuty
```

---

## Costi di Monitoring

| Servizio | Modello Pricing |
|---------|----------------|
| CloudWatch Metrics (AWS) | Gratuito (metriche di base), $0.30/metrica custom/mese |
| CloudWatch Logs Ingestion | $0.50/GB |
| CloudWatch Logs Storage | $0.03/GB/mese |
| CloudWatch Log Insights | $0.005/GB scansionato |
| CloudWatch Alarms | $0.10/alarm standard/mese |
| CloudWatch Dashboard | $3.00/dashboard/mese (3 gratis) |
| X-Ray Traces | $5.00/1M trace registrati ($0.50/1M retrieve) |
| AMP (Prometheus) | $0.90/1M sample ingestiti/mese |
| Managed Grafana | $9/utente/mese (Editor) |

---

## Riferimenti

- [Amazon CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- [AWS X-Ray Documentation](https://docs.aws.amazon.com/xray/)
- [ADOT Documentation](https://aws-otel.github.io/)
- [Amazon Managed Grafana](https://docs.aws.amazon.com/grafana/)
- [Amazon Managed Service for Prometheus](https://docs.aws.amazon.com/prometheus/)
- [AWS Observability Best Practices](https://aws-observability.github.io/observability-best-practices/)
