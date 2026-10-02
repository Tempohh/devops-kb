---
title: "Packer"
slug: packer
category: iac
tags: [packer, golden-image, immutable-infrastructure, ami, hashicorp, image-building]
search_keywords: [packer, hashicorp packer, golden image, immutable infrastructure, ami, machine image, image baking, hcp packer, hcl2, infrastruttura immutabile]
parent: iac/_index
related: [iac/packer/golden-image-pipeline, iac/terraform/fondamentali]
status: complete
difficulty: intermediate
last_updated: 2026-10-02
---

# Packer

HashiCorp Packer costruisce immagini macchina (AMI, Azure Managed Image / Compute Gallery, GCP image) da definizioni HCL2 versionate. Abilita il pattern della *golden image* e dell'infrastruttura immutabile: scale-out rapido, zero drift, baseline di sicurezza verificabile.

## Argomenti in questa sezione

| Argomento | Contenuto |
|---|---|
| [Golden Image Pipeline](golden-image-pipeline.md) | HCL2, hardening, pipeline GitHub Actions con OIDC, scan e test, integrazione Terraform/ASG, HCP Packer, troubleshooting |

## Relazioni

- [Terraform](../terraform/_index.md) — consuma le immagini via `data "aws_ami"` / launch template
- [Ansible](../ansible/_index.md) — usabile come provisioner durante la build
