---
title: "Azure Monitoring & Observability"
slug: monitoring-azure
category: cloud
tags: [azure, monitoring, log-analytics, application-insights, azure-monitor, kql]
search_keywords: [Azure Monitor metriche logs, Log Analytics Workspace KQL, Application Insights APM, Azure Monitor Agent AMA, Container Insights AKS, Network Watcher, Azure Advisor recommendations, distributed tracing, diagnostic settings, alert action group]
parent: cloud/azure/_index
related: [cloud/azure/compute/virtual-machines, cloud/azure/compute/aks-containers, cloud/azure/security/defender-sentinel]
official_docs: https://learn.microsoft.com/azure/azure-monitor/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Monitoring & Observability

Azure offre una piattaforma di observability unificata basata su Azure Monitor, che copre i tre pilastri classici: metrics (metriche), logs (dati testuali strutturati) e traces (distributed tracing). Log Analytics è il repository centrale per tutti i log, mentre Application Insights estende il monitoring a livello applicativo.

## Panoramica dei Servizi di Monitoring

| Servizio | Tipo | Dati | Use Case |
|---|---|---|---|
| **Azure Monitor** | Platform | Metriche (time-series), logs, traces | Monitoring infrastruttura, alerting |
| **Log Analytics Workspace** | Repository | Logs (structured, KQL queryable) | Centralizzazione log, analisi, SIEM |
| **Application Insights** | APM | Request, dependency, exception, trace | Monitoring applicativo, debugging |
| **Container Insights** | Container | Node/pod metrics, container logs | AKS monitoring |
| **Network Watcher** | Network | NSG flow logs, packet capture, topology | Debugging rete, security analysis |
| **Azure Advisor** | Recommendations | Best practices analysis | Cost, security, performance suggestions |
| **Service Health** | Platform status | Planned maintenance, incidents | Awareness Azure outage impact |

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   **Azure Monitor & Log Analytics**

    ---

    Piattaforma unificata metrics + logs, KQL query language, Azure Monitor Agent, Diagnostic Settings, Alert types, Action Groups, Workbooks, Container Insights, retention policy.

    [:octicons-arrow-right-24: Vai a Monitor & Log Analytics](monitor-log-analytics.md)

-   **Application Insights**

    ---

    APM per web app e microservizi: SDK integration, distributed tracing, Application Map, Availability Tests, Live Metrics, Profiler, Snapshot Debugger, sampling, Kusto queries.

    [:octicons-arrow-right-24: Vai a Application Insights](application-insights.md)

</div>

## Riferimenti

- [Documentazione Azure Monitor](https://learn.microsoft.com/azure/azure-monitor/)
- [Log Analytics Workspace](https://learn.microsoft.com/azure/azure-monitor/logs/log-analytics-workspace-overview)
- [Application Insights](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview)
