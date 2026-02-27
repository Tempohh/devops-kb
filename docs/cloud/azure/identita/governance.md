---
title: "Azure Governance"
slug: governance-azure
category: cloud
tags: [azure, governance, azure-policy, management-groups, pim, conditional-access, entra-governance, blueprints, tags]
search_keywords: [Azure Governance, Azure Policy, Management Groups, PIM Privileged Identity Management, Conditional Access Azure, Entra ID Governance, Access Reviews, Entitlement Management, Azure Blueprints, policy initiative, policy assignment, compliance Azure, landing zone, Cloud Adoption Framework governance, tagging policy, resource locks]
parent: cloud/azure/identita/_index
related: [cloud/azure/identita/entra-id, cloud/azure/identita/rbac-managed-identity, cloud/azure/fondamentali/well-architected]
official_docs: https://learn.microsoft.com/azure/governance/
status: complete
difficulty: advanced
last_updated: 2026-02-26
---

# Azure Governance

La **governance Azure** garantisce che le risorse siano usate in conformità con le policy aziendali, di sicurezza e di compliance.

---

## Management Groups

I **Management Groups** organizzano subscription in gerarchia per applicare policy e RBAC uniformemente:

```
Root Management Group (Tenant Root Group)
├── Management Group: Produzione
│   ├── Subscription: Prod-EU
│   └── Subscription: Prod-US
├── Management Group: Non-Produzione
│   ├── Subscription: Staging
│   └── Subscription: Dev
└── Management Group: Sandbox
    └── Subscription: Sandbox
```

```bash
# Creare Management Group
az account management-group create \
    --name "mg-production" \
    --display-name "Production"

# Nidificare Management Group
az account management-group update \
    --name "mg-production" \
    --parent-id "mg-company-root"

# Aggiungere subscription a Management Group
az account management-group subscription add \
    --name "mg-production" \
    --subscription $SUBSCRIPTION_ID

# Listare gerarchia
az account management-group list --output table
```

---

## Azure Policy

**Azure Policy** applica e audita regole sulle risorse Azure in modo automatico.

**Tipi di effect (ordine di valutazione):**

| Effect | Comportamento |
|--------|--------------|
| `Disabled` | Policy ignorata |
| `Audit` | Non blocca, registra non-compliance in CloudWatch |
| `AuditIfNotExists` | Audit se una risorsa correlata non esiste |
| `Append` | Aggiunge proprietà alla risorsa |
| `Modify` | Modifica tag o proprietà |
| `DeployIfNotExists` | Deploya risorsa se non esiste |
| `Deny` | Blocca operazione non conforme |
| `DenyAction` | Blocca operazioni di delete/action |

```bash
# Listare policy built-in disponibili
az policy definition list \
    --query "[?policyType=='BuiltIn'].{Name:displayName, ID:name}" \
    --output table | head -20

# Assegnare policy built-in (esempio: require tag)
az policy assignment create \
    --name "require-environment-tag" \
    --display-name "Require Environment tag on Resource Groups" \
    --policy "/providers/Microsoft.Authorization/policyDefinitions/96670d01-0a4d-4649-9c89-2d3abc0a5025" \
    --scope "/subscriptions/$SUBSCRIPTION_ID" \
    --params '{"tagName": {"value": "Environment"}}'

# Creare policy custom (esempio: blocco risorse in region non autorizzate)
cat > allowed-regions-policy.json <<'EOF'
{
  "properties": {
    "displayName": "Allowed locations",
    "description": "Restricts resource deployment to approved Azure regions",
    "policyType": "Custom",
    "mode": "Indexed",
    "parameters": {
      "allowedLocations": {
        "type": "Array",
        "metadata": {
          "displayName": "Allowed locations",
          "description": "The list of allowed locations"
        }
      }
    },
    "policyRule": {
      "if": {
        "not": {
          "field": "location",
          "in": "[parameters('allowedLocations')]"
        }
      },
      "then": {
        "effect": "Deny"
      }
    }
  }
}
EOF

az policy definition create \
    --name "allowed-regions" \
    --rules @allowed-regions-policy.json

# Assegnare con parametri
az policy assignment create \
    --name "restrict-to-eu" \
    --policy "allowed-regions" \
    --scope "/subscriptions/$SUBSCRIPTION_ID" \
    --params '{"allowedLocations": {"value": ["italynorth", "westeurope", "northeurope", "germanywestcentral"]}}'
```

### Policy Initiative (Policy Set)

Un'**Initiative** raggruppa più policy in un'unica assegnazione:

```bash
# Creare initiative
az policy set-definition create \
    --name "company-baseline" \
    --display-name "Company Security Baseline" \
    --definitions '[
        {
            "policyDefinitionId": "/subscriptions/.../providers/Microsoft.Authorization/policyDefinitions/allowed-regions",
            "parameters": {"allowedLocations": {"value": ["italynorth", "westeurope"]}}
        },
        {
            "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/96670d01-0a4d-4649-9c89-2d3abc0a5025",
            "parameters": {"tagName": {"value": "Environment"}}
        }
    ]'

# Assegnare initiative
az policy assignment create \
    --name "company-baseline-assignment" \
    --policy-set-definition "company-baseline" \
    --scope "/subscriptions/$SUBSCRIPTION_ID"

# Verificare compliance
az policy state list \
    --resource-group myapp-rg \
    --query "[?complianceState=='NonCompliant'].{Policy:policyDefinitionName, Resource:resourceId}" \
    --output table

# Remediation task per DeployIfNotExists/Modify
az policy remediation create \
    --name "remediate-tags" \
    --policy-assignment "require-environment-tag" \
    --resource-group myapp-rg
```

---

## Resource Locks

I **Resource Locks** prevengono eliminazioni o modifiche accidentali:

```bash
# Lock CanNotDelete — può essere modificato, non eliminato
az lock create \
    --name "no-delete-prod" \
    --resource-group production-rg \
    --lock-type CanNotDelete \
    --notes "Production environment — do not delete"

# Lock ReadOnly — solo lettura (attenzione: blocca anche tag e alcune operazioni)
az lock create \
    --name "readonly-critical" \
    --resource-group critical-rg \
    --lock-type ReadOnly

# Lock su singola risorsa
az lock create \
    --name "no-delete-db" \
    --resource-group production-rg \
    --resource-type Microsoft.Sql/servers \
    --resource-name mydb-server \
    --lock-type CanNotDelete

# Listare lock
az lock list --resource-group production-rg --output table

# Rimuovere lock
az lock delete --name "no-delete-prod" --resource-group production-rg
```

!!! warning "CanNotDelete vs ReadOnly"
    - **CanNotDelete**: permette modifiche, blocca solo delete. Usare per risorse produzione.
    - **ReadOnly**: blocca TUTTO, incluse operazioni che sembrano di lettura ma modificano state (es. `az vm list` può fallire perché richiede una write). Usare con cautela.

---

## Privileged Identity Management (PIM)

**PIM** gestisce l'accesso privilegiato Just-In-Time (JIT) — i ruoli privilegiati vengono attivati solo quando necessari e per un periodo limitato:

```
Senza PIM:
  Utente → sempre Contributor → rischio accesso permanente

Con PIM:
  Utente → ruolo eligible → richiede attivazione → approvazione → Contributor per 4h → scade
```

**Funzionalità PIM:**
- **Eligible assignments:** l'utente ha il ruolo eligible, deve attivarlo per usarlo
- **Active assignments:** classico assignment sempre attivo
- **Time-bound:** assignments con scadenza automatica
- **Approval workflow:** l'attivazione richiede approvazione da un manager
- **MFA at activation:** richiede MFA quando si attiva un ruolo privilegiato
- **Justification:** richiede motivazione per l'attivazione
- **Alerts:** notifica quando si usa un ruolo privilegiato
- **Access reviews:** revisione periodica degli assignment attivi/eligible

PIM si configura tramite **Azure Portal** (Entra ID → Identity Governance → PIM) o **MS Graph API**.

---

## Conditional Access

Le **Conditional Access Policies** di Entra ID controllano l'accesso alle app in base a condizioni:

```
Conditional Access Formula:

  IF (utente + app + segnali) → ALLORA (allow / block / require MFA / require compliant device)

Segnali analizzati:
  - Identità: utente, gruppo, ruolo
  - Location: IP, paese, named location
  - Device: compliant, Entra joined, stato
  - App: quale applicazione
  - Risk: user risk, sign-in risk (da Identity Protection)
  - Client app: browser, mobile app, exchange sync
```

**Policy esempio: richiedi MFA per admin fuori dalla rete aziendale:**

Configurazione (tramite Entra ID portal → Security → Conditional Access):

```json
{
  "displayName": "Require MFA for admins outside corporate network",
  "conditions": {
    "users": {
      "includeRoles": ["62e90394-69f5-4237-9190-012177145e10"]  // Global Admin role ID
    },
    "locations": {
      "excludeLocations": ["named-location-corporate-ip"]
    },
    "applications": {
      "includeApplications": ["All"]
    }
  },
  "grantControls": {
    "operator": "OR",
    "builtInControls": ["mfa"]
  },
  "state": "enabled"
}
```

---

## Entra ID Governance

**Access Reviews** — revisione periodica degli accessi per compliance:

- Revisionare chi ha accesso a gruppi, app o ruoli Azure
- Configurare frequenza (settimanale, mensile, trimestrale)
- Auto-apply: rimuove accessi se non confermati
- Può richiedere ai reviewer di fornire motivazione

**Entitlement Management** — pacchetti di accesso:

- Raggruppa risorse (gruppi, app, SharePoint) in "access packages"
- Flusso di richiesta → approvazione → provisioning automatico
- Gestione lifecycle: scadenza, rinnovo, rimozione automatica

---

## Riferimenti

- [Azure Policy Documentation](https://learn.microsoft.com/azure/governance/policy/)
- [Management Groups](https://learn.microsoft.com/azure/governance/management-groups/)
- [PIM Documentation](https://learn.microsoft.com/azure/active-directory/privileged-identity-management/)
- [Conditional Access](https://learn.microsoft.com/azure/active-directory/conditional-access/)
- [Resource Locks](https://learn.microsoft.com/azure/azure-resource-manager/management/lock-resources)
- [Entra ID Governance](https://learn.microsoft.com/azure/active-directory/governance/)
- [Azure Landing Zones (CAF)](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/)
