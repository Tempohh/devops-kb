---
title: "Pulumi"
slug: pulumi
category: iac
tags: [pulumi, iac, infrastructure-as-code, python, typescript, go, cloud]
search_keywords: [pulumi, infrastructure as code, iac, python iac, typescript iac, sdk iac, pulumi cloud, component resources]
parent: iac/_index
related: [iac/pulumi/fondamentali, iac/terraform/fondamentali, iac/ansible/fondamentali]
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Pulumi

Pulumi è un framework IaC che consente di definire l'infrastruttura cloud usando linguaggi di programmazione reali: Python, TypeScript, Go, C# e Java. Tratta l'infrastruttura come software: test unitari, astrazioni, librerie riusabili, loop e condizioni native del linguaggio.

## Argomenti in questa sezione

| Argomento | Contenuto |
|---|---|
| [Fondamentali](fondamentali.md) | Project, Stack, Resources, Outputs, Config, Secrets, Automation API, testing |
| [Stacks e Multi-Ambiente](stacks-ambienti.md) | Workflow multi-ambiente, Stack Reference, config/segreti per stack, state management, CI/CD, Automation API |

## Quando Scegliere Pulumi

- Team con forte background da developer che preferiscono Python/TypeScript a HCL
- Infrastruttura con logica complessa (loop su regioni, risorse condizionali, calcoli dinamici)
- Necessità di unit test nativi sull'infrastruttura
- Platform team che vuole pubblicare Component Resources come librerie npm/PyPI

## Relazioni

- [Terraform](../terraform/_index.md) — alternativa basata su HCL, più diffusa; i concetti di state e provider sono analoghi
- [Ansible](../ansible/_index.md) — configuration management post-provisioning; complementare a Pulumi
