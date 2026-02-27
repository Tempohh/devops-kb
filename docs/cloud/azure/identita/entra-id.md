---
title: "Microsoft Entra ID (Azure AD)"
slug: entra-id
category: cloud
tags: [azure, entra-id, azure-ad, authentication, mfa, sso, b2b, b2c, saml, oidc, oauth2, conditional-access]
search_keywords: [Microsoft Entra ID, Azure Active Directory, AAD, tenant, utenti Azure, gruppi Azure, MFA Multi-Factor Authentication, SSO Single Sign-On, SAML 2.0, OpenID Connect OIDC, OAuth 2.0, Azure AD B2B guest users, Azure AD B2C customer identity, app registration, service principal, enterprise applications, Conditional Access policy, Identity Protection, SSPR Self Service Password Reset]
parent: cloud/azure/identita/_index
related: [cloud/azure/identita/rbac-managed-identity, cloud/azure/identita/governance, cloud/azure/security/key-vault]
official_docs: https://learn.microsoft.com/azure/active-directory/
status: complete
difficulty: intermediate
last_updated: 2026-02-26
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

# Aggiornare utente
az ad user update \
    --id mario.rossi@company.onmicrosoft.com \
    --job-title "Platform Engineer" \
    --department "IT"

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
az ad group create \
    --display-name "All-Developers" \
    --mail-nickname "all-developers" \
    --group-types "DynamicMembership" \
    --membership-rule "(user.jobTitle -eq \"Developer\")" \
    --membership-rule-processing-state "On"

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
APP=$(az ad app create \
    --display-name "myapp-backend" \
    --sign-in-audience AzureADMyOrg \        # AzureADMyOrg / AzureADMultipleOrgs / AzureADandPersonalMicrosoftAccount
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
az ad app permission add \
    --id $APP_ID \
    --api 00000003-0000-0000-c000-000000000000 \   # Microsoft Graph
    --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope  # User.Read (delegated)

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
    -- certificate /path/to/cert.pem
```

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

L'MFA in Entra ID si configura tramite **Conditional Access** (metodo moderno) o **Per-User MFA** (legacy):

```bash
# Verificare stato MFA per utente (tramite MS Graph)
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
# Invitare utente esterno (B2B)
az ad invitation create \
    --invited-user-email-address "partner@external.com" \
    --invite-redirect-url "https://myapp.company.com" \
    --send-invitation-message true \
    --invited-user-display-name "Partner User"

# Listare guest users
az ad user list \
    --filter "userType eq 'Guest'" \
    --query "[].{Name:displayName, Email:mail}" \
    --output table
```

---

## Azure AD B2C (Customer Identity)

**Azure AD B2C** è un servizio separato per gestire identità clienti (Consumer Identity and Access Management — CIAM):

- Supporta login social (Google, Facebook, Apple, GitHub)
- Flussi utente personalizzabili (sign-up, sign-in, password reset)
- Custom policies (Identity Experience Framework) per scenari complessi
- Scalabilità: miliardi di utenti
- Pricing: primi 50.000 MAU gratuiti, poi $0.0016/MAU

```bash
# B2C è un tenant separato — creare tramite portal
# Non è gestibile completamente via CLI standard
```

---

## Identity Protection

**Entra ID Identity Protection** rileva rischi di accesso con ML:

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

## Riferimenti

- [Microsoft Entra ID Documentation](https://learn.microsoft.com/azure/active-directory/)
- [App Registrations Guide](https://learn.microsoft.com/azure/active-directory/develop/quickstart-register-app)
- [MSAL Library](https://learn.microsoft.com/azure/active-directory/develop/msal-overview)
- [B2C Documentation](https://learn.microsoft.com/azure/active-directory-b2c/)
- [Identity Protection](https://learn.microsoft.com/azure/active-directory/identity-protection/)
