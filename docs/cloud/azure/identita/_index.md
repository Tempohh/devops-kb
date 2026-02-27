---
title: "Azure Identità & Accessi"
slug: identita-azure
category: cloud
tags: [azure, entra-id, azure-ad, rbac, managed-identity, pim, conditional-access, identity]
search_keywords: [Azure identità, Microsoft Entra ID, Azure Active Directory AAD, RBAC Azure, Managed Identity, PIM Privileged Identity Management, Conditional Access, Azure AD B2C, Azure AD B2B, MFA Multi Factor Authentication, SSO Azure, SAML OIDC OAuth2 Azure, service principal]
parent: cloud/azure/_index
related: [cloud/azure/security/_index, cloud/azure/identita/entra-id, cloud/azure/identita/rbac-managed-identity, cloud/azure/identita/governance]
official_docs: https://learn.microsoft.com/azure/active-directory/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
---

# Azure Identità & Accessi

La gestione delle identità in Azure è basata su **Microsoft Entra ID** (ex Azure Active Directory) — il servizio cloud di identity management di Microsoft.

## Panoramica

```
Microsoft Entra ID (Tenant)
├── Users (interni, guest B2B, B2C)
├── Groups (security, Microsoft 365)
├── Service Principals (app identities)
├── Managed Identities (Azure resources)
└── Devices (Entra joined, registered)

Controllo Accessi
├── RBAC (ruoli su risorse Azure)
├── Conditional Access (politiche accesso)
├── PIM (gestione accessi privilegiati)
└── Entitlement Management (pacchetti accesso)
```

## Argomenti in questa Sezione

<div class="grid cards" markdown>

-   :material-microsoft-azure: **[Microsoft Entra ID](entra-id.md)**

    ---
    Tenant, utenti, gruppi, app registrations, service principals, B2B, B2C, MFA, SSO, SAML/OIDC/OAuth2

-   :material-shield-key: **[RBAC & Managed Identity](rbac-managed-identity.md)**

    ---
    Role-Based Access Control, ruoli built-in e custom, scope, Managed Identity (system/user assigned), Workload Identity Federation

-   :material-cog: **[Governance & Policy](governance.md)**

    ---
    Azure Policy, Management Groups, Blueprints, PIM, Conditional Access, Entra ID Governance

</div>
