---
title: "Ansible"
slug: ansible
category: iac
tags: [ansible, configuration-management, agentless, automation, playbook, yaml, devops]
search_keywords: [ansible, playbook, inventory, roles, vault, agentless, ssh, configuration management, automation, red hat, galaxy, collections]
parent: iac/_index
related: [iac/ansible/fondamentali, iac/terraform/fondamentali]
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Ansible

Ansible è lo strumento di configuration management agentless più diffuso nel settore DevOps. Usa SSH per connettersi ai nodi target e YAML per descrivere lo stato desiderato del sistema. Non richiede agent installati sui nodi e garantisce idempotenza per design.

## Argomenti in questa sezione

| Argomento | Contenuto |
|---|---|
| [Fondamentali](fondamentali.md) | Playbook, inventory, moduli, roles, vault, template Jinja2, best practices |

## Quando Usare Ansible

- Configurazione software su VM o server bare-metal dopo il provisioning (complementare a Terraform)
- Deploy di applicazioni su ambienti senza Kubernetes
- Automazione di task operativi ripetitivi (patching, backup, rotazione credenziali)
- Orchestrazione di procedure multi-step su gruppi di host

## Relazioni

- [Terraform](../terraform/_index.md) — Terraform provisiona l'infrastruttura, Ansible la configura
