---
title: "Processi di Sviluppo"
slug: processi
category: dev
tags: [workflow, processi, developer-experience, sdlc, git, testing, ci-cd]
search_keywords: [processi sviluppo, developer workflow, development process, inner loop, outer loop, branching strategy, git workflow, sdlc, software development lifecycle, developer experience, dx]
parent: dev/_index
official_docs: https://www.atlassian.com/continuous-delivery/software-testing/shift-left-testing
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Processi di Sviluppo

Questa sezione copre il **ciclo di vita del developer** su microservizi: come si configura l'ambiente locale, come si struttura il lavoro con Git, come si valida il codice prima e dopo il merge.

## Argomenti

<div class="grid cards" markdown>

-   :material-source-branch: **Developer Workflow**

    ---
    Ambiente locale con Docker Compose, inner loop su Kubernetes con Skaffold/Tilt, Devcontainer, branch strategy, conventional commits, PR workflow, shift-left testing e feature toggles.

    → [Developer Workflow](developer-workflow.md)

-   :material-sitemap: **Enterprise SDLC per Microservizi**

    ---
    Sprint planning con debito tecnico (quadrante Fowler), Definition of Done con quality gate, feature flags (LaunchDarkly/Unleash/Flagsmith), release management, ADR e ruolo del Tech Lead.

    → [Enterprise SDLC](enterprise-sdlc.md)

-   :material-chart-timeline: **Project Management Tecnico**

    ---
    Team Topologies (stream-aligned, enabling, platform, complicated-subsystem), DORA metrics, flow metrics vs story points, tech debt register, capacity allocation 20%, governance dipendenze tra team, roadmap tecnica vs product roadmap, engineering metrics non-vanity.

    → [PM Tecnico per Microservizi](pm-sviluppo.md)

</div>
