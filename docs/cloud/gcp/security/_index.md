---
title: "GCP Security"
slug: security
category: cloud
tags: [gcp, security, kms, secret-manager, encryption, cmek]
search_keywords: [GCP security, Google Cloud security, sicurezza GCP, protezione dati GCP, data protection GCP, encryption GCP]
parent: cloud/gcp/_index
related: [cloud/gcp/security/kms-secret-manager, cloud/gcp/iam/iam-service-accounts, cloud/aws/security/_index]
official_docs: https://cloud.google.com/security
status: complete
difficulty: intermediate
last_updated: 2026-10-02
---

# GCP Security

Sicurezza e protezione dati su Google Cloud Platform: gestione chiavi crittografiche, secret applicativi, cifratura at-rest. Per il controllo degli accessi (identità, ruoli, Service Account) vedi [IAM](../iam/_index.md).

## Servizi Security GCP

<div class="grid cards" markdown>

-   **Cloud KMS e Secret Manager**

    ---

    Key hierarchy (keyring/key/version), CMEK vs CSEK vs Google-managed, envelope encryption, Cloud HSM, rotazione, IAM binding su chiavi, versioning e replica dei secret, integrazione Workload Identity.

    [:octicons-arrow-right-24: Cloud KMS e Secret Manager](kms-secret-manager.md)

</div>
