---
title: "Microsoft Entra ID (Azure AD)"
slug: entra-id
category: cloud
tags: [azure, entra-id, azure-ad, authentication, mfa, sso, b2b, b2c, saml, oidc, oauth2, conditional-access]
search_keywords: [Microsoft Entra ID, Azure Active Directory, AAD, tenant, utenti Azure, gruppi Azure, MFA Multi-Factor Authentication, SSO Single Sign-On, SAML 2.0, OpenID Connect OIDC, OAuth 2.0, Azure AD B2B guest users, Azure AD B2C customer identity, app registration, service principal, enterprise applications, Conditional Access policy, Identity Protection, SSPR Self Service Password Reset]
parent: cloud/azure/identita/_index
related: [cloud/azure/identita/rbac-managed-identity, cloud/azure/identita/governance, cloud/azure/security/key-vault]
official_docs: https://learn.microsoft.com/azure/active-directory/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Microsoft Entra ID (Azure AD)

**Microsoft Entra ID** (rinominato da Azure Active Directory nel 2023) è il servizio cloud di **Identity and Access Management (IAM)** di Microsoft. È il fondamento di tutti gli accessi alle risorse Azure e Microsoft 365.

## Concetti Fondamentali

```
Tenant Entra ID
├── Directory Objects
│   ├── Users (interni + guest B2B)
│   ├── Groups (security / Microsoft 365)
│   ├── Devices (Entra joined/registered)
│   └── Service Principals
│
├── App Registrations → App object (1 per tenant)
│   └── Service Principal → istanza locale dell'app
│
└── Managed Identities
    ├── System-assigned (lifecycle = risorsa Azure)
    └── User-assigned (lifecycle indipendente)
```

---

## Gestione Utenti

```bash
# Creare utente
az ad user create \
    --display-name "Mario Rossi" \
    --user-principal-name mario.rossi@company.onmicrosoft.com \
    --password "InitialP@ssw0rd!" \
    --force-change-password-next-sign-in true

# Listare utenti
az ad user list --query "[].{Name:displayName, UPN:userPrincipalName}" --output table

# Ottenere utente specifico
az ad user show --id mario.rossi@company.onmicrosoft.com

# Aggiornare attributi (jobTitle/department non sono flag di `az ad user update`: usare Graph)
az rest --method PATCH \
    --url "https://graph.microsoft.com/v1.0/users/mario.rossi@company.onmicrosoft.com" \
    --body '{"jobTitle":"Platform Engineer","department":"IT"}'

# Eliminare utente
az ad user delete --id mario.rossi@company.onmicrosoft.com

# Resettare password
az ad user update \
    --id mario.rossi@company.onmicrosoft.com \
    --password "NewP@ssw0rd!" \
    --force-change-password-next-sign-in true
```

---

## Gestione Gruppi

```bash
# Creare gruppo Security
az ad group create \
    --display-name "Platform-Engineers" \
    --mail-nickname "platform-engineers" \
    --description "Platform Engineering team"

# Creare gruppo Dynamic (membership automatica basata su attributi)
# `az ad group create` non supporta i gruppi dinamici: usare Graph (richiede licenza P1)
az rest --method POST \
    --url "https://graph.microsoft.com/v1.0/groups" \
    --body '{
      "displayName": "All-Developers",
      "mailEnabled": false,
      "mailNickname": "all-developers",
      "securityEnabled": true,
      "groupTypes": ["DynamicMembership"],
      "membershipRule": "(user.jobTitle -eq \"Developer\")",
      "membershipRuleProcessingState": "On"
    }'

# Aggiungere membro a gruppo
az ad group member add \
    --group "Platform-Engineers" \
    --member-id "$(az ad user show --id mario.rossi@company.onmicrosoft.com --query id -o tsv)"

# Listare membri gruppo
az ad group member list --group "Platform-Engineers" --output table

# Verificare se utente è in gruppo
az ad group member check \
    --group "Platform-Engineers" \
    --member-id "$(az ad user show --id mario.rossi@company.onmicrosoft.com --query id -o tsv)"
```

---

## App Registration e Service Principal

Ogni applicazione che deve autenticarsi con Entra ID necessita di una **App Registration**:

```bash
# Creare App Registration
# sign-in-audience: AzureADMyOrg / AzureADMultipleOrgs / AzureADandPersonalMicrosoftAccount
APP=$(az ad app create \
    --display-name "myapp-backend" \
    --sign-in-audience AzureADMyOrg \
    --query "{AppId:appId, ObjectId:id}" \
    --output json)

APP_ID=$(echo $APP | jq -r '.AppId')

# Creare Service Principal per l'app
az ad sp create --id $APP_ID

# Creare client secret
az ad app credential reset \
    --id $APP_ID \
    --append \
    --display-name "prod-secret" \
    --end-date "2027-01-01"
# Output: clientSecret — salvare subito, non è visibile dopo

# Creare certificato (più sicuro di client secret)
az ad app credential reset \
    --id $APP_ID \
    --create-cert \
    --keyvault my-keyvault \
    --cert myapp-cert

# Aggiungere API permission
# --api 00000003-0000-0000-c000-000000000000 = Microsoft Graph
# e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope = User.Read (delegated)
az ad app permission add \
    --id $APP_ID \
    --api 00000003-0000-0000-c000-000000000000 \
    --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope

# Grant admin consent (per application permissions)
az ad app permission admin-consent --id $APP_ID
```

### Autenticazione con Service Principal

```bash
# Login con service principal (client secret)
az login \
    --service-principal \
    --username $APP_ID \
    --password $CLIENT_SECRET \
    --tenant $TENANT_ID

# Login con service principal (certificato)
az login \
    --service-principal \
    --username $APP_ID \
    --tenant $TENANT_ID \
    --allow-no-subscriptions \
    --password /path/to/cert.pem   # per i certificati --password è il path del PEM (chiave privata + cert)
```

### Workload Identity Federation (senza segreti)

Un client secret è un segreto a lunga durata che scade e può trapelare. Con le **federated credentials** l'app si fida di un token OIDC emesso da un IdP esterno (GitHub Actions, Kubernetes, GitLab): Entra ID scambia quel token per un access token, **senza alcun secret da conservare**. È l'opzione preferita per le pipeline CI/CD.

```bash
# Federated credential per un workflow GitHub Actions sul branch main
az ad app federated-credential create --id $APP_ID --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:myorg/myrepo:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

Il `subject` deve corrispondere **esattamente** al claim `sub` del token (repo, branch/environment/tag): un mismatch dà `AADSTS70025`/`AADSTS700213`. Nel workflow si usa `azure/login` con `client-id`, `tenant-id`, `subscription-id` e permesso `id-token: write`.

```python
# Python — autenticazione service principal con MSAL
from msal import ConfidentialClientApplication
import os

app = ConfidentialClientApplication(
    client_id=os.environ['AZURE_CLIENT_ID'],
    client_credential=os.environ['AZURE_CLIENT_SECRET'],
    authority=f"https://login.microsoftonline.com/{os.environ['AZURE_TENANT_ID']}"
)

# Acquisire token per Microsoft Graph
result = app.acquire_token_for_client(
    scopes=["https://graph.microsoft.com/.default"]
)

if "access_token" in result:
    token = result["access_token"]
else:
    raise Exception(f"Auth failed: {result.get('error_description')}")
```

---

## Autenticazione Multi-Fattore (MFA)

L'MFA in Entra ID si configura tramite **Conditional Access** (richiede licenza P1) o, per tenant piccoli/senza P1, tramite **Security defaults**. **Per-User MFA** è legacy: evitarlo. I metodi si gestiscono nella **Authentication methods policy** (le vecchie policy MFA/SSPR separate sono state dismesse a favore di questa).

!!! warning "MFA obbligatoria per accessi di gestione Azure"
    Microsoft impone l'MFA per portal Azure, Entra admin center e Intune (fase 1) e, dalla fase 2 (da ottobre 2025, rollout progressivo), anche per Azure CLI, PowerShell, SDK/API e IaC con **utenti**. Le automazioni devono usare **service principal / managed identity / workload identity federation**, non account utente.

```bash
# Elencare i metodi di autenticazione di un utente (MS Graph; serve UserAuthenticationMethod.Read.All)
az rest \
    --method GET \
    --url "https://graph.microsoft.com/v1.0/users/mario.rossi@company.onmicrosoft.com/authentication/methods" \
    --headers "Content-Type=application/json"
```

**Metodi MFA supportati:**
- Microsoft Authenticator (push notification, passwordless)
- FIDO2 Security Keys (YubiKey, ecc.)
- Windows Hello for Business
- OATH hardware/software token
- SMS / Voice call (meno sicuri — evitare)
- Temporary Access Pass (TAP) — per onboarding

---

## Single Sign-On (SSO)

Entra ID supporta SSO per applicazioni Enterprise tramite:

| Protocollo | Scenario | Configurazione |
|------------|----------|---------------|
| **SAML 2.0** | App enterprise legacy (Salesforce, ServiceNow) | Enterprise applications → SAML |
| **OpenID Connect (OIDC)** | App moderne (web, mobile) | App registrations → OIDC |
| **OAuth 2.0** | API authorization | App registrations → OAuth |
| **WS-Federation** | App Microsoft legacy | Enterprise applications |
| **Password-based** | App senza SSO nativo | Enterprise applications |
| **Linked** | Reindirizza a altro IdP | Enterprise applications |

---

## B2B Collaboration (Guest Users)

**B2B** permette di invitare utenti esterni (guest) da altri tenant o con account personali:

```bash
# Invitare utente esterno (B2B) — via Graph, non esiste `az ad invitation`
az rest --method POST \
    --url "https://graph.microsoft.com/v1.0/invitations" \
    --body '{
      "invitedUserEmailAddress": "partner@external.com",
      "invitedUserDisplayName": "Partner User",
      "inviteRedirectUrl": "https://myapp.company.com",
      "sendInvitationMessage": true
    }'

# Listare guest users
az ad user list \
    --filter "userType eq 'Guest'" \
    --query "[].{Name:displayName, Email:mail}" \
    --output table
```

---

## Customer Identity: Entra External ID (successore di Azure AD B2C)

Per le identità dei clienti (Customer IAM, **CIAM**) Microsoft offre **Microsoft Entra External ID**. **Azure AD B2C** non è più disponibile ai nuovi clienti dal 1 maggio 2025 (i tenant esistenti restano supportati almeno fino a maggio 2030): per nuovi progetti usare External ID.

- Tenant *external* separato dal tenant workforce
- Login social (Google, Facebook, Apple…), email + password / OTP
- User flow configurabili (sign-up, sign-in, password reset) e personalizzazione del branding
- Pricing a **MAU** (Monthly Active Users, utenti attivi nel mese): primi 50.000 MAU gratuiti; verificare le tariffe correnti nella pagina pricing ufficiale
- B2C legacy: custom policies (Identity Experience Framework) per scenari complessi — External ID non le replica 1:1, valutare la migrazione caso per caso

```bash
# Il tenant external si crea dal portal / Entra admin center:
# non è gestibile completamente via CLI standard
```

!!! note "Quando serve cosa"
    **B2B** = partner/collaboratori che accedono a risorse del *tuo* tenant con la loro identità. **External ID (CIAM)** = clienti finali di una tua applicazione pubblica.

---

## Identity Protection

**Entra ID Identity Protection** (licenza P2) rileva rischi di accesso con ML:

| Rilevamento | Descrizione |
|-------------|-------------|
| Leaked credentials | Credenziali trovate nel dark web |
| Anonymous IP address | Accesso da Tor, VPN anonime |
| Atypical travel | Login da due paesi in tempi impossibili |
| Malware linked IP | IP noto per malware C2 |
| Unfamiliar sign-in properties | Nuovo browser/OS/location |
| Password spray attack | Tentativi di login su molti account |

**Risposta automatica:** Conditional Access con condizione `User Risk` o `Sign-in Risk`.

---

## Troubleshooting

### Scenario 1 — AADSTS error durante token acquisition

**Sintomo:** L'applicazione riceve un errore `AADSTS` (es. `AADSTS70011`, `AADSTS65001`, `AADSTS50020`) al momento dell'acquisizione del token.

**Causa:** Cause frequenti: audience/scope errato, admin consent non concesso, tenant non autorizzato, o client secret scaduto.

**Soluzione:** Decodificare il codice AADSTS specifico e agire di conseguenza.

```bash
# Verificare stato client secret (scadenza)
az ad app credential list --id $APP_ID --output table

# Verificare le API permissions e lo stato del consent
az ad app permission list --id $APP_ID --output table
az ad app permission list-grants --id $APP_ID --output table

# Rigenerare client secret se scaduto
az ad app credential reset \
    --id $APP_ID \
    --append \
    --display-name "prod-secret-$(date +%Y%m)" \
    --end-date "2028-01-01"

# Test token acquisition (client credentials flow)
curl -X POST \
    "https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token" \
    -d "client_id=$APP_ID&client_secret=$CLIENT_SECRET&grant_type=client_credentials&scope=https://graph.microsoft.com/.default"
```

---

### Scenario 2 — Service principal non ha accesso alla risorsa Azure

**Sintomo:** Operazioni Azure CLI falliscono con `AuthorizationFailed` o `does not have authorization to perform action`.

**Causa:** Il Service Principal non ha il ruolo RBAC appropriato sulla subscription/resource group, oppure il contesto CLI è autenticato su una subscription diversa.

**Soluzione:** Assegnare il ruolo corretto e verificare il contesto.

```bash
# Verificare identità corrente e subscription attiva
az account show
az ad signed-in-user show 2>/dev/null || echo "Logged in as SP"

# Controllare ruoli assegnati al service principal
SP_OBJECT_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
az role assignment list --assignee $SP_OBJECT_ID --all --output table

# Assegnare ruolo Contributor a livello resource group
az role assignment create \
    --assignee $SP_OBJECT_ID \
    --role "Contributor" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME"

# Verificare l'assegnazione
az role assignment list --assignee $SP_OBJECT_ID \
    --scope "/subscriptions/$SUBSCRIPTION_ID" \
    --output table
```

---

### Scenario 3 — Conditional Access blocca l'accesso utente

**Sintomo:** L'utente riceve `AADSTS53003` ("Access has been blocked by Conditional Access policies") o viene forzato a soddisfare requisiti inattesi (MFA, compliant device).

**Causa:** Una o più policy di Conditional Access corrispondono alla sessione dell'utente (location, app, ruolo, rischio).

**Soluzione:** Identificare quale policy si applica tramite Sign-in logs e agire sulla policy o sull'utente.

```bash
# Consultare i sign-in logs per trovare la policy CA applicata
az rest \
    --method GET \
    --url "https://graph.microsoft.com/v1.0/auditLogs/signIns?\$filter=userPrincipalName eq 'user@company.com'&\$top=5" \
    --query "value[].{Status:status.errorCode, CA:appliedConditionalAccessPolicies[0].displayName, Reason:status.failureReason}"

# Listare tutte le policy Conditional Access attive
az rest \
    --method GET \
    --url "https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies?\$filter=state eq 'enabled'" \
    --query "value[].{Name:displayName, State:state}" \
    --output table

# Escludere utente specifico da una policy (via Graph PATCH — usare portal per sicurezza)
# Portal: Entra ID → Security → Conditional Access → selezionare policy → Exclude users/groups
```

---

### Scenario 4 — Utente guest B2B non riesce ad accedere all'applicazione

**Sintomo:** L'utente invitato riceve `AADSTS65005` o accede al tenant ma non vede l'applicazione o riceve errori di autorizzazione.

**Causa:** L'app registration non è configurata per utenti multi-tenant/guest, oppure al guest manca il ruolo applicativo, oppure la policy B2B del tenant blocca gli account esterni.

**Soluzione:** Verificare la configurazione dell'app e i permessi del guest.

```bash
# Verificare sign-in audience dell'app
az ad app show --id $APP_ID --query "signInAudience" -o tsv
# I guest B2B sono oggetti del TUO tenant: funzionano anche con AzureADMyOrg.
# AzureADMultipleOrgs serve solo se utenti di altri tenant accedono con la propria identità (non come guest).

# Verificare che il guest esista nel tenant
az ad user show --id "partner@external.com" --query "{UPN:userPrincipalName, Type:userType}" -o json

# Assegnare ruolo applicativo al guest (Graph; `az ad app role assignment` non esiste)
GUEST_ID=$(az ad user show --id "partner@external.com" --query id -o tsv)
SP_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
az rest --method POST \
    --url "https://graph.microsoft.com/v1.0/users/$GUEST_ID/appRoleAssignments" \
    --body "{\"principalId\":\"$GUEST_ID\",\"resourceId\":\"$SP_ID\",\"appRoleId\":\"<app-role-id>\"}"

# Listare External Collaboration Settings (accettabilità domini)
az rest \
    --method GET \
    --url "https://graph.microsoft.com/v1.0/policies/authorizationPolicy" \
    --query "{GuestAccess:allowInvitesFrom, DefaultGuestRole:guestUserRoleId}"
```

---

## Relazioni

??? info "RBAC e Managed Identity — Approfondimento"
    Entra ID autentica (chi sei); Azure RBAC autorizza sulle risorse (cosa puoi fare). Le managed identity eliminano i secret per le risorse Azure.

    **Approfondimento completo →** `cloud/azure/identita/rbac-managed-identity`

## Riferimenti

- [Microsoft Entra ID Documentation](https://learn.microsoft.com/azure/active-directory/)
- [App Registrations Guide](https://learn.microsoft.com/azure/active-directory/develop/quickstart-register-app)
- [MSAL Library](https://learn.microsoft.com/azure/active-directory/develop/msal-overview)
- [B2C Documentation](https://learn.microsoft.com/azure/active-directory-b2c/)
- [Identity Protection](https://learn.microsoft.com/azure/active-directory/identity-protection/)
