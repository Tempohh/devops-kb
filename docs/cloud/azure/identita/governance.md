---
title: "Azure Governance"
slug: governance-azure
category: cloud
tags: [azure, governance, azure-policy, management-groups, pim, conditional-access, entra-governance, blueprints, tags]
search_keywords: [Azure Governance, Azure Policy, Management Groups, PIM Privileged Identity Management, Conditional Access Azure, Entra ID Governance, Access Reviews, Entitlement Management, Azure Blueprints retired, Deployment Stacks, policy exemption, policy initiative, policy assignment, compliance Azure, landing zone, Cloud Adoption Framework governance, tagging policy, resource locks]
parent: cloud/azure/identita/_index
related: [cloud/azure/identita/entra-id, cloud/azure/identita/rbac-managed-identity, cloud/azure/fondamentali/well-architected]
official_docs: https://learn.microsoft.com/azure/governance/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Azure Governance

La **governance Azure** garantisce che le risorse siano usate in conformità con le policy aziendali, di sicurezza e di compliance.

Strumenti e livello su cui agiscono: **Management Groups** (gerarchia di scope), **Azure Policy** (guardrail sulle risorse), **Resource Locks** (protezione da delete/modify), **PIM** e **Conditional Access** (controllo dell'accesso), **Entra ID Governance** (lifecycle degli accessi).

!!! warning "Azure Blueprints ritirato"
    **Azure Blueprints** è stato deprecato e ritirato (luglio 2026). Per i nuovi ambienti usare **Template Specs** + **Deployment Stacks** (deploy e lifecycle/deny-delete delle risorse) combinati con Policy initiative e Azure Landing Zones (Bicep/Terraform).

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

!!! note "Root group e default"
    Le nuove subscription finiscono di default sotto il **Tenant Root Group**. Per evitare che si accumulino lì senza policy, impostare un *default management group* (Hierarchy settings) e limitare con *require authorization* chi può creare Management Group. Policy e RBAC assegnati a un MG sono **ereditati** da tutti i figli: il perché della gerarchia è applicare una volta sola il guardrail al livello giusto.

---

## Azure Policy

**Azure Policy** applica e audita regole sulle risorse Azure in modo automatico.

**Tipi di effect** (l'ordine reale di valutazione è: `Disabled` → `Append`/`Modify` → `Deny` → `Audit`; `AuditIfNotExists` e `DeployIfNotExists` vengono valutati dopo che il resource provider ha risposto con successo):

| Effect | Comportamento |
|--------|--------------|
| `Disabled` | Policy ignorata |
| `Audit` | Non blocca, registra non-compliance come evento di warning nell'Activity Log |
| `AuditIfNotExists` | Audit se una risorsa correlata non esiste |
| `Append` | Aggiunge proprietà alla risorsa (legacy: preferire `Modify`) |
| `Modify` | Aggiunge/aggiorna/rimuove tag o proprietà; richiede managed identity |
| `DeployIfNotExists` | Deploya risorsa correlata se non esiste; richiede managed identity |
| `Deny` | Blocca operazione non conforme |
| `DenyAction` | Blocca specifiche azioni (oggi `DELETE`) su risorse |
| `Manual` | Compliance attestata manualmente (es. controlli non automatizzabili) |

!!! note "Managed identity per Modify / DeployIfNotExists"
    Questi effect agiscono con una **managed identity dell'assignment** (`--mi-system-assigned --location <region>`) a cui vanno assegnati i ruoli indicati in `roleDefinitionIds` della policy. Senza, la remediation fallisce con errori di autorizzazione.

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
# --rules vuole SOLO il blocco policyRule (if/then); parametri e mode sono flag separati
cat > allowed-regions-rule.json <<'EOF'
{
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
EOF

cat > allowed-regions-params.json <<'EOF'
{
  "allowedLocations": {
    "type": "Array",
    "metadata": {
      "displayName": "Allowed locations",
      "description": "The list of allowed locations"
    }
  }
}
EOF

az policy definition create \
    --name "allowed-regions" \
    --display-name "Allowed locations" \
    --mode Indexed \
    --rules allowed-regions-rule.json \
    --params allowed-regions-params.json

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

# Remediation task: solo per assignment con effect DeployIfNotExists/Modify
# (non ha senso su "require-environment-tag", che è Deny)
az policy remediation create \
    --name "remediate-tags" \
    --policy-assignment "<assignment-con-modify-o-dine>" \
    --resource-group myapp-rg
```

### Exemption ed enforcement mode

Per escludere risorse in modo tracciato e con scadenza usare le **exemption** (`az policy exemption create`, categoria `Waiver` o `Mitigated`, con `--expires-on`), meglio di `notScopes` che esclude senza audit trail. Un assignment con `enforcementMode: DoNotEnforce` valuta la compliance senza applicare `Deny`/remediation: utile per testare una policy prima di attivarla.


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
    - **ReadOnly**: blocca ogni write e ogni operazione che il provider implementa come `POST` (es. `listKeys` su Storage Account, avvio/stop di una VM, scrittura di tag). Le semplici letture (`az vm list`) funzionano. Usare con cautela.
- I lock agiscono solo sul **control plane** (ARM): non impediscono modifiche ai dati (es. scrivere blob o righe SQL).
- I lock sono **ereditati** da risorse figlie; per eliminare una risorsa lockata va prima rimosso il lock (serve `Microsoft.Authorization/locks/*`, quindi Owner o User Access Administrator).

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

PIM copre due famiglie di ruoli: **ruoli Entra ID** (es. Global Administrator), **ruoli Azure RBAC** (Owner, Contributor su MG/subscription/RG) e **gruppi** (PIM for Groups). Si configura dal portale (Entra admin center → ID Governance → Privileged Identity Management) o via **MS Graph API** (ruoli Entra) / **ARM API** (ruoli Azure). Richiede licenze **Entra ID P2** o **Entra ID Governance**.

**Perché:** riduce la finestra di esposizione di un account compromesso: un attaccante che ruba un token non trova privilegi permanenti, e ogni attivazione lascia audit trail.

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

Configurazione (Entra admin center → Entra ID → Conditional Access, o Graph `POST /identity/conditionalAccess/policies`). Il JSON sotto è il body Graph; `62e90394-...` è il role template ID di Global Administrator e `<named-location-id>` l'ID della named location aziendale:

```json
{
  "displayName": "Require MFA for admins outside corporate network",
  "conditions": {
    "users": {
      "includeRoles": ["62e90394-69f5-4237-9190-012177145e10"]
    },
    "locations": {
      "includeLocations": ["All"],
      "excludeLocations": ["<named-location-id>"]
    },
    "applications": {
      "includeApplications": ["All"]
    }
  },
  "grantControls": {
    "operator": "OR",
    "builtInControls": ["mfa"]
  },
  "state": "enabledForReportingButNotEnforced"
}
```

!!! tip "Report-only prima di enforce"
    Creare la policy in **report-only** (`enabledForReportingButNotEnforced`), verificare l'impatto con *Sign-in logs* / Insights workbook, poi passare a `enabled`. Escludere sempre almeno un account **break-glass** per non bloccare l'intero tenant.

!!! note "MFA obbligatoria per Azure"
    Microsoft impone l'MFA per accesso ad Azure portal, Entra admin center e Intune (Phase 1) e, in rollout progressivo, per Azure CLI, PowerShell, SDK e IaC tool (Phase 2) con identità utente. Non sostituisce le Conditional Access policy, ma rende l'MFA un requisito di base; le workload identity usano managed identity/service principal.

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

**Lifecycle Workflows** — automatizzano joiner/mover/leaver (onboarding, cambio ruolo, offboarding) con task come abilitare/disabilitare l'account o rimuovere l'appartenenza a gruppi.

Queste funzioni richiedono la licenza **Microsoft Entra ID Governance** (add-on a P1/P2).

---

## Troubleshooting

### Scenario 1 — Policy assegnata ma le risorse risultano ancora non conformi

**Sintomo:** Dopo aver assegnato una policy, il compliance state rimane `NonCompliant` anche su risorse che sembrano conformi.

**Causa:** L'evaluation cycle di Azure Policy non è immediato. Il ciclo standard avviene ogni 24h; le nuove assegnazioni richiedono fino a 30 minuti per la prima valutazione.

**Soluzione:** Forzare una re-valutazione manuale.

```bash
# Forzare scan di compliance sull'intera subscription
az policy state trigger-scan --subscription $SUBSCRIPTION_ID

# Forzare scan su un resource group specifico
az policy state trigger-scan \
    --resource-group myapp-rg \
    --no-wait

# Verificare stato compliance dopo il trigger
az policy state list \
    --resource-group myapp-rg \
    --query "[?complianceState=='NonCompliant'].{Policy:policyDefinitionName, Resource:resourceId}" \
    --output table
```

---

### Scenario 2 — Resource Lock ReadOnly blocca operazioni di lettura o tag

**Sintomo:** Operazioni come `az storage account keys list`, `az tag update`, o deployment ARM falliscono con `AuthorizationFailed` o `ScopeLocked` su risorse con lock `ReadOnly`.

**Causa:** Il lock `ReadOnly` blocca tutte le operazioni che richiedono una write o una chiamata `POST` sul resource provider, incluse alcune che appaiono come lettura (es. `listKeys`) e la scrittura di tag.

**Soluzione:** Rimuovere temporaneamente il lock, eseguire l'operazione, ripristinare il lock. Oppure usare `CanNotDelete` se il requisito è solo prevenire eliminazioni.

```bash
# Verificare lock esistenti
az lock list --resource-group production-rg --output table

# Rimuovere lock ReadOnly temporaneamente
az lock delete \
    --name "readonly-critical" \
    --resource-group critical-rg

# Eseguire l'operazione necessaria (es. aggiornare tag)
az tag update \
    --resource-id /subscriptions/$SUBSCRIPTION_ID/resourceGroups/critical-rg \
    --operation Merge \
    --tags "CostCenter=IT"

# Ripristinare il lock
az lock create \
    --name "readonly-critical" \
    --resource-group critical-rg \
    --lock-type ReadOnly
```

---

### Scenario 3 — Attivazione PIM fallisce o non viene approvata

**Sintomo:** L'utente tenta di attivare un ruolo eligible in PIM ma riceve errore `ActivationFailed` oppure la richiesta rimane in stato `PendingApproval` indefinitamente.

**Causa 1:** MFA non completata o sessione Entra ID senza claim MFA recente.
**Causa 2:** Nessun approvatore configurato o approvatori non raggiungibili.
**Causa 3:** Il ruolo ha una finestra di attivazione massima inferiore a quanto richiesto.

**Soluzione:** Verificare la configurazione del ruolo in PIM e la presenza di approvatori attivi.

```bash
# Ruoli Entra ID (directory roles) via MS Graph; per ruoli Azure RBAC usare l'ARM API
# Microsoft.Authorization/roleEligibilityScheduleRequests
az rest --method GET \
    --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleEligibilityScheduleRequests?\$filter=principalId eq '$USER_OBJECT_ID'" \
    --headers "Content-Type=application/json"

# Verificare stato richieste di attivazione PIM in sospeso
az rest --method GET \
    --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignmentScheduleRequests?\$filter=principalId eq '$USER_OBJECT_ID' and status eq 'PendingApproval'"
```

!!! tip "Configurazione PIM"
    In caso di approvatori non disponibili, configurare sempre un approvatore di backup. Impostare `maxActivationDuration` adeguato (es. PT8H per turni di lavoro standard).

---

### Scenario 4 — Policy assegnata al Management Group non si applica alle subscription figlie

**Sintomo:** Una policy assegnata a livello di Management Group non viene ereditata dalle subscription o resource group sottostanti; le risorse nelle subscription figlie risultano escluse dalla compliance.

**Causa 1:** La subscription è stata aggiunta al Management Group dopo l'assegnazione della policy e il ciclo di propagazione non è ancora completato.
**Causa 2:** L'assignment padre ha `notScopes` che escludono la subscription, oppure `enforcementMode: DoNotEnforce`. (Un assignment figlio con `Disabled` NON annulla quello del padre: ogni assignment è valutato in modo indipendente.)
**Causa 3:** La subscription ha un'exemption configurata.
**Causa 4:** La policy ha `mode: Indexed` e il tipo di risorsa non supporta tag/location, quindi non viene valutato.

**Soluzione:** Verificare gerarchia, `notScopes`, `enforcementMode` ed exemption.

```bash
# Verificare che la subscription sia nel Management Group corretto
az account management-group show \
    --name "mg-production" \
    --expand --recurse \
    --output json | jq '.children[].id'

# Controllare assignment effettivi sulla subscription (includendo quelli ereditati)
az policy assignment list \
    --subscription $SUBSCRIPTION_ID \
    --query "[].{Name:name, Scope:scope, DisplayName:displayName}" \
    --output table

# Verificare eventuali exemption che escludono la subscription
az policy exemption list \
    --subscription $SUBSCRIPTION_ID \
    --output table

# Controllare notScopes ed enforcement mode degli assignment
az policy assignment list \
    --subscription $SUBSCRIPTION_ID \
    --query "[].{Name:name, EnforcementMode:enforcementMode, NotScopes:notScopes}" \
    --output json
```

---

## Riferimenti

- [Azure Policy Documentation](https://learn.microsoft.com/azure/governance/policy/)
- [Management Groups](https://learn.microsoft.com/azure/governance/management-groups/)
- [PIM Documentation](https://learn.microsoft.com/entra/id-governance/privileged-identity-management/)
- [Conditional Access](https://learn.microsoft.com/entra/identity/conditional-access/)
- [Resource Locks](https://learn.microsoft.com/azure/azure-resource-manager/management/lock-resources)
- [Entra ID Governance](https://learn.microsoft.com/entra/id-governance/)
- [Deployment Stacks](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks)
- [Azure Landing Zones (CAF)](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/landing-zone/)
