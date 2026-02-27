---
title: "Jenkins"
slug: jenkins
category: ci-cd
tags: [jenkins, pipeline, groovy, ci-cd, automation, shared-libraries, jcasc, kubernetes-agents]
search_keywords: [Jenkins, Jenkins pipeline, Jenkinsfile, Groovy pipeline, declarative pipeline, scripted pipeline, Jenkins shared libraries, Jenkins Kubernetes plugin, JCasC Jenkins Configuration as Code, Jenkins RBAC, multi-branch pipeline, Blue Ocean, Jenkins agent, Jenkins controller, Jenkins master slave, Jenkins enterprise, Jenkins LTS]
parent: ci-cd/_index
related: [ci-cd/jenkins/pipeline-fundamentals, ci-cd/jenkins/shared-libraries, ci-cd/jenkins/agent-infrastructure, ci-cd/jenkins/enterprise-patterns, ci-cd/jenkins/security-governance]
official_docs: https://www.jenkins.io/doc/
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Jenkins

**Jenkins** è il server di automazione open source più diffuso nell'enterprise — scritto in Java, estensibile tramite oltre 1900 plugin, completamente self-hosted. È lo standard de facto per CI/CD in ambienti enterprise che richiedono massima flessibilità e controllo.

## Architettura Jenkins

```
Jenkins Controller (ex Master)
├── Web UI / REST API / CLI
├── Job Scheduler & Queue
├── Credential Store
├── Plugin Registry
└── Configuration (JCasC)
         │
         │ JNLP / SSH / WebSocket
         ▼
┌────────────────────────────────────────────────────────┐
│  Agent Pool                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ Static   │  │ Docker   │  │ Kubernetes Pod        │ │
│  │ Agent    │  │ Agent    │  │ (dynamic, ephemeral)  │ │
│  │ (SSH)    │  │          │  │                       │ │
│  └──────────┘  └──────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

**Principio fondamentale:** il **Controller non esegue build** — orchestra gli agenti che eseguono il lavoro effettivo.

## Versioni e Release

| Canale | Cadenza | Raccomandato per |
|--------|---------|-----------------|
| **LTS (Long-Term Support)** | Ogni 12 settimane | Produzione enterprise |
| **Weekly** | Settimanale | Test nuove feature, bleeding edge |

!!! tip "LTS in Enterprise"
    In un contesto enterprise usare sempre **Jenkins LTS**. Aggiornare ogni 2-3 release LTS (non saltare più di 6 mesi) per evitare gap di sicurezza e problemi di compatibilità plugin.

## Plugin Essenziali Enterprise

| Categoria | Plugin | Funzione |
|-----------|--------|---------|
| **Pipeline** | Pipeline, Pipeline Shared Groovy Libraries | Core pipeline |
| **SCM** | Git, GitHub, GitLab, Bitbucket Branch Source | Source code management |
| **Agenti** | Kubernetes, Docker, SSH Build Agents | Agent provisioning |
| **Config** | Configuration as Code (JCasC) | Jenkins-as-code |
| **Security** | Matrix Authorization Strategy, Role Strategy | RBAC |
| **Credentials** | Credentials, Credentials Binding | Secret management |
| **Notifiche** | Slack, Email Extension, Microsoft Teams | Alerting |
| **Qualità** | SonarQube Scanner, Warnings Next Generation | Code quality |
| **Artifacts** | Nexus Artifact Uploader, Artifactory | Artifact management |
| **UI** | Blue Ocean, Build Monitor View, Dashboard View | Visualization |
| **Audit** | Audit Trail, Job Config History | Governance |

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-pipe: **[Pipeline Fundamentals](pipeline-fundamentals.md)**

    ---
    Declarative vs Scripted pipeline, sintassi completa, stages paralleli, matrix, CPS, @NonCPS, input step, post conditions

-   :material-library: **[Shared Libraries](shared-libraries.md)**

    ---
    Global Shared Libraries, struttura vars/src/resources, custom steps, utility classes, versioning, testing con JenkinsPipelineUnit

-   :material-server-network: **[Agent Infrastructure](agent-infrastructure.md)**

    ---
    JCasC, Kubernetes Plugin con Pod Templates, Docker agents, JNLP vs WebSocket, caching dipendenze, scaling controller/agent

-   :material-office-building: **[Enterprise Patterns](enterprise-patterns.md)**

    ---
    Multi-branch pipeline, template pipeline, build promotion, parameterized pipelines, Multistage matrix, architetture CI/CD enterprise

-   :material-shield-lock: **[Security & Governance](security-governance.md)**

    ---
    Matrix Authorization, RBAC fine-grained, Credentials API, Script Security, SSO/LDAP/SAML, Audit Trail, hardening

</div>
