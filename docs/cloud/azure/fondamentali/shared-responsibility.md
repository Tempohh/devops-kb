---
title: "Modello di Responsabilità Condivisa Azure"
slug: shared-responsibility-azure
category: cloud
tags: [azure, shared-responsibility, security, compliance, iaas, paas, saas]
search_keywords: [Azure shared responsibility model, responsabilità condivisa Azure, sicurezza cloud Azure, IaaS responsabilità, PaaS responsabilità, SaaS responsabilità, Microsoft responsabilità, compliance Azure, GDPR Azure, customer responsibility]
parent: cloud/azure/fondamentali/_index
related: [cloud/azure/security/_index, cloud/azure/identita/_index]
official_docs: https://learn.microsoft.com/azure/security/fundamentals/shared-responsibility
status: complete
difficulty: beginner
last_updated: 2026-03-28
---

# Modello di Responsabilità Condivisa Azure

Il **Modello di Responsabilità Condivisa** definisce la ripartizione delle responsabilità di sicurezza tra Microsoft Azure e il cliente.

> **Microsoft** è responsabile della sicurezza **del** cloud.
> **Il cliente** è responsabile della sicurezza **nel** cloud.

---

## Matrice delle Responsabilità

| Responsabilità | On-Premises | IaaS | PaaS | SaaS |
|---------------|-------------|------|------|------|
| Dati e contenuti | Cliente | Cliente | Cliente | Cliente |
| Endpoint / dispositivi | Cliente | Cliente | Cliente | Condivisa |
| Account e identità | Cliente | Cliente | Condivisa | Condivisa |
| Applicazioni | Cliente | Cliente | Condivisa | Microsoft |
| Controlli di rete | Cliente | Condivisa | Microsoft | Microsoft |
| Sistema operativo | Cliente | Cliente | Microsoft | Microsoft |
| Host fisico | Cliente | Microsoft | Microsoft | Microsoft |
| Rete fisica | Cliente | Microsoft | Microsoft | Microsoft |
| Datacenter fisico | Cliente | Microsoft | Microsoft | Microsoft |

---

## Responsabilità Microsoft (sempre)

- Sicurezza fisica dei datacenter (accesso, sorveglianza, climatizzazione)
- Infrastruttura di rete fisica (fibra, switch, router backbone)
- Hypervisor e virtualizzazione dell'hardware
- Patch e aggiornamenti del firmware hardware
- Conformità del datacenter (ISO 27001, SOC 1/2/3, PCI DSS, ecc.)

---

## Responsabilità del Cliente (sempre)

- **Dati**: classificazione, crittografia, backup
- **Identità e accessi**: account, password, MFA, privilegi minimi
- **Endpoint**: dispositivi che accedono ai servizi Azure
- **Configurazione corretta dei servizi**: NSG, firewall, policy

---

## Dettaglio per Tipo di Servizio

=== "IaaS (es. Virtual Machines)"
    Il cliente gestisce TUTTO sopra l'hypervisor:

    | Area | Responsabilità |
    |------|---------------|
    | OS (patching, hardening) | **Cliente** |
    | Runtime (Java, .NET, Python) | **Cliente** |
    | Middleware (web server, app server) | **Cliente** |
    | Applicazione | **Cliente** |
    | Dati applicativi | **Cliente** |
    | Network security (NSG, firewall) | **Cliente** |
    | Backup e DR | **Cliente** |
    | Identità (OS-level) | **Cliente** |

=== "PaaS (es. App Service, Azure SQL)"
    Microsoft gestisce infrastruttura + OS + runtime:

    | Area | Responsabilità |
    |------|---------------|
    | OS patching | **Microsoft** |
    | Runtime patching | **Microsoft** |
    | Scaling infrastructure | **Microsoft** |
    | Applicazione e codice | **Cliente** |
    | Configurazione servizio | **Cliente** |
    | Dati applicativi | **Cliente** |
    | Identità applicativa (Managed Identity) | **Condivisa** |

=== "SaaS (es. Microsoft 365)"
    Microsoft gestisce quasi tutto:

    | Area | Responsabilità |
    |------|---------------|
    | Infrastruttura completa | **Microsoft** |
    | Applicazione SaaS | **Microsoft** |
    | Dati degli utenti | **Cliente** |
    | Configurazione (policy, permessi) | **Cliente** |
    | Accessi e identità (account) | **Cliente** |

---

## Compliance e Certificazioni Azure

Microsoft Azure è certificato per i principali standard di compliance:

| Standard | Descrizione | Scope |
|----------|-------------|-------|
| **ISO 27001** | Sicurezza informazioni | Globale |
| **ISO 27017** | Sicurezza cloud | Globale |
| **ISO 27018** | Privacy dati cloud (PII) | Globale |
| **SOC 1, 2, 3** | Controlli servizi | Globale |
| **PCI DSS Level 1** | Carte di pagamento | Globale |
| **GDPR** | Protezione dati EU | Europa |
| **HIPAA/HITECH** | Dati sanitari USA | USA |
| **FedRAMP High** | Governo federale USA | Azure Government |
| **C5** | Sicurezza cloud (BSI Germania) | Europa |
| **ENS High** | Sicurezza nazionale spagnola | Spagna |

```bash
# Azure Compliance Manager — verificare postura compliance
# Disponibile in Microsoft Defender for Cloud o Microsoft Purview Compliance Manager

# Verificare policy compliance (Azure Policy)
az policy state list \
    --resource-group myapp-rg \
    --query "[?complianceState=='NonCompliant'].{Policy:policyDefinitionName, Resource:resourceId}" \
    --output table
```

---

## Strumenti per la Conformità

| Strumento | Funzione |
|-----------|----------|
| **Microsoft Defender for Cloud** | Postura sicurezza, raccomandazioni, compliance dashboard |
| **Azure Policy** | Policy enforcement automatico su risorse |
| **Microsoft Purview** | Governance dati, classificazione, compliance |
| **Azure Blueprints** (legacy) | Template ambiente conforme (sostituito da Template Specs + Policy) |
| **Microsoft Compliance Manager** | Assessment compliance, action items, punteggio |

```bash
# Verificare il Secure Score corrente con Defender for Cloud
az security secure-score list --output table

# Elencare raccomandazioni attive di sicurezza
az security task list --output table

# Verificare le assegnazioni di Azure Policy su una subscription
az policy assignment list --query "[].{Name:name, Scope:scope, Policy:policyDefinitionId}" --output table

# Verificare risorse non conformi a una policy specifica
az policy state list \
    --filter "complianceState eq 'NonCompliant'" \
    --query "[].{Resource:resourceId, Policy:policyDefinitionName}" \
    --output table
```

---

## Troubleshooting

### Scenario 1 — Risorse non conformi dopo assegnazione policy

**Sintomo:** Dopo aver assegnato una Azure Policy, le risorse esistenti risultano `NonCompliant` nel dashboard.

**Causa:** Le policy Azure hanno un ritardo di valutazione (fino a 30 minuti) e non si applicano retroattivamente in modo automatico alle risorse già esistenti senza un trigger di remediation.

**Soluzione:** Avviare un task di remediation esplicito per applicare la policy alle risorse esistenti.

```bash
# Creare un task di remediation per risorse non conformi
az policy remediation create \
    --name "remediation-task-01" \
    --policy-assignment "/subscriptions/<sub-id>/providers/Microsoft.Authorization/policyAssignments/<assignment-name>" \
    --resource-discovery-mode ReEvaluateCompliance

# Monitorare lo stato della remediation
az policy remediation show \
    --name "remediation-task-01" \
    --query "{Status:provisioningState, Succeeded:deploymentStatus.successfulDeployments}" \
    --output table
```

---

### Scenario 2 — Defender for Cloud mostra raccomandazioni per servizi PaaS/SaaS

**Sintomo:** Il Secure Score di Defender for Cloud segnala vulnerabilità su risorse PaaS (es. App Service, Azure SQL) che si ritenevano gestite da Microsoft.

**Causa:** In PaaS, la responsabilità è condivisa: Microsoft gestisce OS e runtime, ma la configurazione dell'applicazione, le variabili d'ambiente, le connessioni e i permessi rimangono responsabilità del cliente.

**Soluzione:** Verificare le raccomandazioni specifiche per categoria e applicare le correzioni sulle aree di competenza del cliente.

```bash
# Filtrare raccomandazioni per risorsa PaaS specifica (es. App Service)
az security task list \
    --query "[?contains(resourceId,'Microsoft.Web/sites')].{Task:name, Severity:severity, State:state}" \
    --output table

# Abilitare HTTPS-only su App Service (remediation tipica)
az webapp update \
    --name myapp \
    --resource-group myapp-rg \
    --https-only true
```

---

### Scenario 3 — Confusione sulle responsabilità di backup in IaaS

**Sintomo:** Dati persi su una VM Azure; si credeva che Azure gestisse automaticamente i backup.

**Causa:** In IaaS il backup è responsabilità del cliente. Azure non abilita automaticamente Azure Backup sulle VM; l'infrastruttura di storage sottostante è protetta da Microsoft, ma i dati applicativi no.

**Soluzione:** Abilitare Azure Backup per le VM critiche e verificare la policy di retention.

```bash
# Abilitare Azure Backup su una VM esistente
az backup protection enable-for-vm \
    --resource-group myapp-rg \
    --vault-name myRecoveryVault \
    --vm myVM \
    --policy-name DefaultPolicy

# Verificare lo stato di protezione di tutte le VM
az backup item list \
    --resource-group myapp-rg \
    --vault-name myRecoveryVault \
    --backup-management-type AzureIaasVM \
    --query "[].{VM:name, Status:properties.currentProtectionState}" \
    --output table
```

---

### Scenario 4 — Accesso non autorizzato a dati in un servizio SaaS (Microsoft 365)

**Sintomo:** Un utente ha acceduto a dati riservati in SharePoint Online pur non dovendo averne i permessi.

**Causa:** In SaaS la gestione delle identità, dei gruppi e dei permessi di accesso è responsabilità del cliente. Microsoft fornisce la piattaforma ma non gestisce le autorizzazioni applicative.

**Soluzione:** Rivedere i permessi via Microsoft Entra ID (ex Azure AD) e abilitare Conditional Access per imporre il principio del privilegio minimo.

```bash
# Verificare i membri di un gruppo di sicurezza in Entra ID (via Azure CLI)
az ad group member list \
    --group "SharePoint-Finance-Readers" \
    --query "[].{Name:displayName, UPN:userPrincipalName}" \
    --output table

# Elencare le assegnazioni di ruolo su una risorsa Azure
az role assignment list \
    --scope "/subscriptions/<sub-id>" \
    --query "[].{Principal:principalName, Role:roleDefinitionName, Scope:scope}" \
    --output table
```

---

## Riferimenti

- [Shared Responsibility in the Cloud](https://learn.microsoft.com/azure/security/fundamentals/shared-responsibility)
- [Azure Compliance Documentation](https://learn.microsoft.com/azure/compliance/)
- [Azure Trust Center](https://www.microsoft.com/trust-center)
- [Azure Security Benchmark](https://learn.microsoft.com/security/benchmark/azure/)
