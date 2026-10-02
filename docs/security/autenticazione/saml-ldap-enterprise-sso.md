---
title: "SAML 2.0 e LDAP — Enterprise SSO"
slug: saml-ldap-enterprise-sso
category: security
tags: [saml, ldap, active-directory, sso, federation, idp, keycloak, enterprise-auth]
search_keywords: [saml, saml 2.0, security assertion markup language, ldap, ldaps, starttls, lightweight directory access protocol, active directory, ad, microsoft entra id, azure ad, okta, keycloak saml, identity provider, idp, service provider, sp, sp-initiated sso, idp-initiated sso, saml assertion, saml metadata, acs url, assertion consumer service, nameid, http-post binding, http-redirect binding, bind authentication, distinguished name, dn, ou, memberOf, ldap referral, clock skew, ntlm, kerberos, single sign-on, federazione identità, sso enterprise, saml vs oidc, ldap fallback, grafana saml, jenkins saml, gitlab ldap, xml signature, certificate rotation]
parent: security/autenticazione/_index
related: [security/autenticazione/oauth2-oidc, security/autenticazione/jwt, security/autorizzazione/rbac-abac-rebac, security/pki-certificati/pki-interna, security/secret-management/vault]
official_docs: https://docs.oasis-open.org/security/saml/v2.0/
status: complete
difficulty: advanced
last_updated: 2026-10-02
---

# SAML 2.0 e LDAP — Enterprise SSO

## Panoramica

**SAML 2.0** (Security Assertion Markup Language) è uno standard OASIS del 2005 per la **federazione di identità** basata su XML: un Identity Provider (IdP) autentica l'utente e consegna al Service Provider (SP) una *assertion* firmata che dichiara "questo utente è stato autenticato, ecco i suoi attributi". **LDAP** (Lightweight Directory Access Protocol) è invece un protocollo di accesso a una *directory* (Active Directory, OpenLDAP, 389-ds): l'applicazione riceve username e password e li verifica con un **bind** sulla directory.

Entrambi sopravvivono perché il mondo enterprise è pieno di sistemi che non parlano OIDC: Jira/Confluence on-prem, ERP, VPN aziendali, appliance, e requisiti di certificazione o contrattuali che citano SAML esplicitamente. LDAP resta il fallback universale dei tool self-hosted (GitLab CE, Grafana, Vault, Jenkins) quando non c'è un IdP federato.

**Quando usarli:** SAML quando il vincolo è enterprise/legacy; LDAP diretto quando esiste solo una directory on-prem senza IdP. **Quando NON usarli:** nuovi sistemi greenfield, SPA, mobile app e API → [OAuth2/OIDC](oauth2-oidc.md) è il default.

!!! warning "LDAP bind diretto = l'applicazione vede la password"
    Con LDAP l'app riceve la password in chiaro dell'utente (poi la inoltra alla directory). Con SAML/OIDC la password resta sull'IdP. Questo è il motivo principale per preferire la federazione: una sola superficie dove inserire credenziali, MFA applicabile centralmente.

---

## Concetti Chiave

### Attori e terminologia SAML

| Termine | Significato |
|---|---|
| **IdP** (Identity Provider) | Autentica l'utente ed emette le assertion (Keycloak, Okta, Entra ID, ADFS) |
| **SP** (Service Provider) | L'applicazione che consuma l'assertion (Grafana, Jenkins, Jira) |
| **Assertion** | Documento XML firmato con identità, attributi e condizioni di validità |
| **Metadata** | XML che descrive entityID, endpoint e certificati di IdP/SP; si scambia a setup |
| **ACS URL** | Assertion Consumer Service: endpoint SP che riceve la assertion (POST) |
| **NameID** | Identificatore dell'utente nella assertion (email, persistent ID, ...) |
| **Binding** | Come viaggia il messaggio: HTTP-Redirect (query string, deflate) o HTTP-POST (form auto-submit) |

### Concetti LDAP

| Termine | Significato |
|---|---|
| **DN** (Distinguished Name) | Percorso univoco di una entry: `uid=mrossi,ou=People,dc=example,dc=com` |
| **OU** | Organizational Unit: contenitore logico (People, Groups, ServiceAccounts) |
| **Base DN** | Radice da cui parte la ricerca (`dc=example,dc=com`) |
| **Bind** | Operazione di autenticazione sulla directory |
| **Search filter** | Query, es. `(&(objectClass=person)(sAMAccountName=mrossi))` |
| **memberOf** | Attributo (AD) che elenca i gruppi di cui l'utente è membro |

!!! note "SAML vs OIDC in pratica"
    Stesso obiettivo (SSO federato), tecnologia diversa: SAML usa **XML + firma XML-DSig + redirect/POST** del browser; OIDC usa **JSON + JWT + REST**. SAML è nato per il web browser e non ha un modello nativo per API o mobile. Un SAML assertion non è utilizzabile come bearer token verso API; un access token OIDC sì. Vedi [JWT](jwt.md).

---

## Architettura / Come Funziona

### SP-initiated SSO (flusso consigliato)

L'utente parte dall'applicazione. È il flusso più sicuro perché l'SP può correlare la risposta alla richiesta tramite `InResponseTo`.

```text
Browser            SP (Grafana)                 IdP (Keycloak)
   │  GET /app        │                              │
   │─────────────────>│                              │
   │  302 → IdP + AuthnRequest (Redirect binding)    │
   │<─────────────────│                              │
   │  GET /saml?SAMLRequest=...                      │
   │────────────────────────────────────────────────>│
   │            login form / MFA / sessione SSO      │
   │<────────────────────────────────────────────────│
   │  HTML form auto-submit: SAMLResponse (POST)     │
   │─────────────────>│  POST /saml/acs              │
   │                  │  valida firma, Audience,     │
   │                  │  NotOnOrAfter, InResponseTo  │
   │  Set-Cookie sessione, 302 /app                  │
   │<─────────────────│                              │
```

### IdP-initiated SSO

L'utente clicca l'icona dell'app dal portale IdP (Okta dashboard, My Apps). L'IdP invia una `SAMLResponse` **non sollecitata** (nessun `InResponseTo`).

!!! warning "IdP-initiated: superficie d'attacco maggiore"
    Senza `AuthnRequest` l'SP non può verificare che la risposta sia attesa → rischio di replay e login CSRF. Disabilitare IdP-initiated sull'SP quando possibile, o accettarlo solo con `RelayState` controllato e assertion con vita brevissima.

### Anatomia di una assertion

```xml
<saml2:Assertion ID="_a75adf55" IssueInstant="2026-10-02T09:00:00Z" Version="2.0">
  <saml2:Issuer>https://sso.example.com/realms/corp</saml2:Issuer>
  <ds:Signature>...</ds:Signature>              <!-- XML-DSig: firma IdP -->
  <saml2:Subject>
    <saml2:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">
      mario.rossi@example.com
    </saml2:NameID>
    <saml2:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
      <saml2:SubjectConfirmationData InResponseTo="_req123"
          Recipient="https://grafana.example.com/saml/acs"
          NotOnOrAfter="2026-10-02T09:05:00Z"/>
    </saml2:SubjectConfirmation>
  </saml2:Subject>
  <saml2:Conditions NotBefore="2026-10-02T08:59:30Z" NotOnOrAfter="2026-10-02T09:05:00Z">
    <saml2:AudienceRestriction>
      <saml2:Audience>https://grafana.example.com/saml/metadata</saml2:Audience>
    </saml2:AudienceRestriction>
  </saml2:Conditions>
  <saml2:AttributeStatement>
    <saml2:Attribute Name="groups">
      <saml2:AttributeValue>devops</saml2:AttributeValue>
      <saml2:AttributeValue>grafana-admins</saml2:AttributeValue>
    </saml2:Attribute>
  </saml2:AttributeStatement>
</saml2:Assertion>
```

Controlli obbligatori lato SP: firma valida (certificato del metadata IdP), `Issuer`, `Audience`, `Recipient`, finestra `NotBefore/NotOnOrAfter`, `InResponseTo`, e **replay protection** (ID assertion già visto).

### Flusso LDAP bind authentication

Pattern a due fasi (search-then-bind), usato da quasi tutti i tool:

1. L'app fa **bind con un service account** (read-only) sulla directory.
2. Cerca l'utente col filtro (`sAMAccountName=mrossi`) e ottiene il DN completo.
3. Esegue un **secondo bind con il DN trovato e la password dell'utente**: successo = autenticato.
4. Legge `memberOf` / ricerca gruppi → mappa a ruoli applicativi ([RBAC](../autorizzazione/rbac-abac-rebac.md)).

### LDAPS vs StartTLS

| | LDAPS | StartTLS |
|---|---|---|
| Porta | 636 | 389 (upgrade a TLS in-band) |
| TLS | Fin dall'inizio della connessione | Dopo comando `STARTTLS` |
| Rischio | Basso | Downgrade se l'app non impone TLS |
| Note | Deprecato in teoria, standard de facto in AD | Preferito da RFC 4513; configurare "TLS required" |

Mai LDAP in chiaro (389 senza TLS): le password viaggiano in chiaro.

---

## Configurazione & Pratica

### Keycloak come IdP SAML

```bash
# Crea client SAML via kcadm (realm "corp")
kcadm.sh create clients -r corp -s protocol=saml \
  -s clientId="https://grafana.example.com/saml/metadata" \
  -s 'redirectUris=["https://grafana.example.com/saml/acs"]' \
  -s 'attributes."saml.assertion.signature"=true' \
  -s 'attributes."saml.client.signature"=true' \
  -s 'attributes."saml_name_id_format"=email'

# Metadata IdP da dare all'SP
curl -s https://sso.example.com/realms/corp/protocol/saml/descriptor -o idp-metadata.xml
```

Aggiungere un **mapper** "Group list" (attributo `groups`) al client, altrimenti l'SP non riceve i gruppi.

### Grafana come SP SAML

```ini
# grafana.ini  (Grafana Enterprise / Cloud: SAML non è in OSS)
[auth.saml]
enabled = true
certificate_path = /etc/grafana/saml/sp.crt
private_key_path = /etc/grafana/saml/sp.key
idp_metadata_path = /etc/grafana/saml/idp-metadata.xml
max_issue_delay = 90s
metadata_valid_duration = 48h
assertion_attribute_login = email
assertion_attribute_name = displayName
assertion_attribute_groups = groups
role_values_admin = grafana-admins
role_values_editor = devops
allow_sign_up = true
```

```bash
# Esporre il metadata SP da caricare sull'IdP
curl https://grafana.example.com/saml/metadata
# Generare coppia chiavi SP (rinnovo: vedi Best Practices)
openssl req -x509 -newkey rsa:3072 -nodes -days 730 \
  -keyout sp.key -out sp.crt -subj "/CN=grafana.example.com"
```

### Jenkins come SP SAML (plugin `saml`)

```yaml
# JCasC — jenkins.yaml
jenkins:
  securityRealm:
    saml:
      idpMetadataConfiguration:
        url: "https://sso.example.com/realms/corp/protocol/saml/descriptor"
        period: 1440            # refresh metadata ogni 24h (minuti)
      displayNameAttributeName: "displayName"
      groupsAttributeName: "groups"
      usernameAttributeName: "email"
      maximumAuthenticationLifetime: 86400
      binding: "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
  authorizationStrategy:
    roleBased:
      roles:
        global:
          - name: "admin"
            permissions: ["Overall/Administer"]
            entries:
              - group: "jenkins-admins"
```

### LDAP/AD: GitLab e Grafana

```ruby
# /etc/gitlab/gitlab.rb  (GitLab CE supporta LDAP)
gitlab_rails['ldap_enabled'] = true
gitlab_rails['ldap_servers'] = {
  'main' => {
    'label'           => 'Corp AD',
    'host'            => 'dc01.corp.example.com',
    'port'            => 636,
    'encryption'      => 'simple_tls',          # LDAPS
    'verify_certificates' => true,
    'bind_dn'         => 'CN=svc-gitlab,OU=ServiceAccounts,DC=corp,DC=example,DC=com',
    'password'        => ENV['LDAP_BIND_PASSWORD'],   # da secret manager, non in chiaro
    'uid'             => 'sAMAccountName',
    'base'            => 'OU=People,DC=corp,DC=example,DC=com',
    'user_filter'     => '(memberOf=CN=gitlab-users,OU=Groups,DC=corp,DC=example,DC=com)',
    'active_directory'=> true
  }
}
```

```toml
# /etc/grafana/ldap.toml  (grafana.ini: [auth.ldap] enabled = true)
[[servers]]
host = "dc01.corp.example.com"
port = 636
use_ssl = true
start_tls = false
ssl_skip_verify = false
bind_dn = "CN=svc-grafana,OU=ServiceAccounts,DC=corp,DC=example,DC=com"
bind_password = "$__env{LDAP_BIND_PASSWORD}"
search_filter = "(sAMAccountName=%s)"
search_base_dns = ["OU=People,DC=corp,DC=example,DC=com"]

[servers.attributes]
name = "givenName"
surname = "sn"
username = "sAMAccountName"
email = "mail"
member_of = "memberOf"

[[servers.group_mappings]]
group_dn = "CN=grafana-admins,OU=Groups,DC=corp,DC=example,DC=com"
org_role = "Admin"
[[servers.group_mappings]]
group_dn = "*"
org_role = "Viewer"
```

### Diagnostica da riga di comando

```bash
# Test bind + ricerca utente (LDAPS)
ldapsearch -H ldaps://dc01.corp.example.com:636 \
  -D "CN=svc-grafana,OU=ServiceAccounts,DC=corp,DC=example,DC=com" -W \
  -b "OU=People,DC=corp,DC=example,DC=com" "(sAMAccountName=mrossi)" memberOf mail

# Verifica certificato del DC
openssl s_client -connect dc01.corp.example.com:636 -showcerts </dev/null | openssl x509 -noout -dates -subject

# Decodifica SAMLResponse catturata (POST binding: base64)
echo "$SAML_RESPONSE" | base64 -d | xmllint --format -
```

---

## Tabella decisionale: OIDC vs SAML vs LDAP

| Criterio | OIDC | SAML 2.0 | LDAP diretto |
|---|---|---|---|
| Formato | JSON / JWT | XML / XML-DSig | Protocollo binario (BER) |
| Password vista dall'app | No | No | **Sì** |
| SSO tra applicazioni | Sì | Sì | No (ri-login per app) |
| MFA centralizzato | Sì (sull'IdP) | Sì (sull'IdP) | Limitato/assente |
| API / mobile / SPA | Ottimo | Scarso | Non applicabile |
| Single Logout | Front/back-channel | SLO (fragile) | N/A |
| Scegliere quando | Nuovo sistema, default | App legacy/enterprise o requisito di certificazione | Directory on-prem senza IdP federato |

Regola pratica: se **puoi** scegliere, OIDC. SAML è quasi sempre un **vincolo del contesto** (il prodotto supporta solo SAML, il cliente lo impone). LDAP diretto è l'ultima spiaggia o un fallback "break-glass". Soluzione comune: un IdP (Keycloak/Entra ID) che **federa** la directory LDAP/AD a monte e parla OIDC o SAML a valle.

---

## Best Practices

- **Preferire la federazione al bind diretto**: introdurre un IdP davanti ad AD/LDAP; le app parlano SAML/OIDC, solo l'IdP conosce le password.
- **SP-initiated, IdP-initiated disabilitato** se il prodotto lo permette; validare sempre `Audience`, `Recipient`, `InResponseTo`.
- **Firmare le assertion** (non solo la response) e, per dati sensibili, cifrarle (`EncryptedAssertion`).
- **Rotazione certificati pianificata**: pubblicare il nuovo certificato nel metadata *prima* di usarlo (periodo di overlap con due chiavi), poi rimuovere il vecchio. Automatizzare il refresh del metadata (`period` / `metadata_valid_duration`).
- **Monitorare la scadenza** dei certificati di firma IdP/SP e dei certificati LDAPS dei DC (alert a 60/30/14 giorni).
- **Service account LDAP** a privilegi minimi (sola lettura sull'OU richiesta), password in [Vault](../secret-management/vault.md), non in `gitlab.rb`/`ldap.toml` in chiaro.
- **Mapping gruppi → ruoli** sempre con default a minimo privilegio (`Viewer`), mai fallback ad admin; vedi [RBAC/ABAC](../autorizzazione/rbac-abac-rebac.md).
- **TLS sempre** su LDAP, con `verify_certificates` attivo; trust della CA interna ([PKI interna](../pki-certificati/pki-interna.md)).
- **Account break-glass locale** per l'app: se IdP/LDAP è down non devi restare chiuso fuori.

!!! tip "Gruppi annidati in AD"
    `memberOf` NON risolve i gruppi annidati. Usare il matching rule OID `1.2.840.113556.1.4.1941` (`LDAP_MATCHING_RULE_IN_CHAIN`): `(memberOf:1.2.840.113556.1.4.1941:=CN=gitlab-users,OU=Groups,DC=corp,DC=example,DC=com)`.

!!! warning "XML Signature Wrapping (XSW)"
    Parser SAML artigianali o non aggiornati sono vulnerabili a XSW: l'attaccante sposta/duplica la parte firmata e fa processare una assertion non firmata. Usare solo librerie mantenute (OpenSAML, python3-saml, passport-saml aggiornato) e applicarne le patch di sicurezza.

---

## Troubleshooting

### 1. SAML: `Assertion is not yet valid` / `Assertion expired` (clock skew)

- **Sintomo**: login fallisce con `NotBefore`/`NotOnOrAfter` violato; spesso intermittente.
- **Causa**: orologi di IdP e SP non sincronizzati; le assertion durano pochi minuti.
- **Soluzione**: sincronizzare NTP e verificare l'offset.

```bash
chronyc tracking            # offset sistema
timedatectl status          # "System clock synchronized: yes"
```
Se serve tolleranza, alzare lo skew sull'SP (es. 60-90 s), mai oltre.

### 2. SAML: `Signature validation failed` dopo giorni/mesi senza modifiche

- **Sintomo**: tutti gli utenti non riescono ad accedere improvvisamente.
- **Causa**: il certificato di firma IdP è scaduto o ruotato e l'SP ha ancora il metadata vecchio.
- **Soluzione**: riscaricare il metadata e verificare la scadenza.

```bash
curl -s https://sso.example.com/realms/corp/protocol/saml/descriptor \
 | xmllint --xpath "string(//*[local-name()='X509Certificate'])" - \
 | base64 -d | openssl x509 -inform der -noout -enddate
```
Prevenzione: alert di scadenza e refresh automatico del metadata.

### 3. SAML: `Recipient mismatch` / `Invalid audience`

- **Sintomo**: errore dopo il redirect di ritorno dall'IdP.
- **Causa**: ACS URL o `entityID` registrati sull'IdP non coincidono con l'URL reale (reverse proxy, `http` vs `https`, porta, trailing slash).
- **Soluzione**: allineare `root_url`/`entityID`; dietro proxy impostare `X-Forwarded-Proto` e l'URL pubblico. Confrontare con la assertion decodificata (`base64 -d | xmllint`).

### 4. LDAP: `Invalid credentials (49)` con password corretta

- **Sintomo**: bind del service account o dell'utente respinto.
- **Causa**: DN errato, account scaduto/bloccato in AD, o password con caratteri speciali non escapati nella config.
- **Soluzione**: `ldapsearch` col DN esatto; leggere il sub-code nel messaggio AD (`data 775` = locked, `data 532` = password scaduta, `data 52e` = credenziali errate).

### 5. LDAP: ricerche lentissime o timeout con `Referral` / `Operations error`

- **Sintomo**: login che impiega 30+ secondi, errore `Operations error ... a successful bind must be completed`.
- **Causa**: **referral chasing** verso altri DC/domini non raggiungibili, tipico con ricerche sulla porta 389 a livello di dominio.
- **Soluzione**: disabilitare il chasing nel client (`REFERRALS off` in `ldap.conf`, `follow_referrals=false`), o puntare al **Global Catalog** (porta 3269 LDAPS) per ricerche multi-dominio.

### 6. LDAPS: `certificate verify failed`

- **Sintomo**: `TLS: peer cert untrusted or revoked`.
- **Causa**: la CA che ha firmato il certificato dei DC non è nel trust store dell'app, oppure il certificato non ha il SAN corretto per l'hostname usato.
- **Soluzione**: installare la CA aziendale nel trust store, usare l'FQDN presente nel SAN (non l'IP); mai `ssl_skip_verify = true` in produzione.

### NTLM vs Kerberos (contesto)

Negli ambienti Windows l'SSO "trasparente" via browser (Integrated Windows Authentication) usa **Kerberos** (ticket, KDC, SPN) oppure ripiega su **NTLM** (challenge/response, più debole, soggetto a relay). Se vedi prompt di login inattesi o fallback NTLM, controllare gli SPN e il DNS. Un IdP come ADFS/Entra ID spesso fa da ponte: Kerberos verso l'utente, SAML/OIDC verso l'app. Non approfondito qui.

---

## Relazioni

??? info "OAuth2 / OIDC — l'alternativa moderna"
    OIDC copre lo stesso caso d'uso SSO con JSON/JWT ed è adatto a API, SPA e mobile. È il default per nuovi sistemi; SAML resta per vincoli legacy.

    **Approfondimento completo →** [OAuth2 e OIDC](oauth2-oidc.md)

??? info "JWT — formato dei token OIDC"
    Differenza chiave con SAML: la assertion XML non è usabile come bearer token verso API; i JWT sì, e sono verificabili offline.

    **Approfondimento completo →** [JWT](jwt.md)

??? info "RBAC / ABAC — mapping gruppi → permessi"
    I gruppi AD/LDAP o l'attributo `groups` della assertion alimentano il modello di autorizzazione dell'applicazione.

    **Approfondimento completo →** [RBAC, ABAC e ReBAC](../autorizzazione/rbac-abac-rebac.md)

??? info "PKI interna — certificati LDAPS e firma SAML"
    I certificati dei domain controller e le chiavi di firma SAML hanno ciclo di vita e rotazione da gestire.

    **Approfondimento completo →** [PKI interna](../pki-certificati/pki-interna.md)

??? info "Vault — credenziali del service account LDAP"
    Il bind account non va in chiaro nei file di configurazione.

    **Approfondimento completo →** [HashiCorp Vault](../secret-management/vault.md)

---

## Riferimenti

- [SAML 2.0 Technical Overview (OASIS)](https://docs.oasis-open.org/security/saml/Post2.0/sstc-saml-tech-overview-2.0.html)
- [RFC 4511 — LDAP Protocol](https://datatracker.ietf.org/doc/html/rfc4511)
- [RFC 4513 — LDAP Authentication Methods and Security Mechanisms](https://datatracker.ietf.org/doc/html/rfc4513)
- [Keycloak — Server Administration: SAML clients](https://www.keycloak.org/docs/latest/server_admin/)
- [Grafana — Configure SAML authentication](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/saml/)
- [Grafana — Configure LDAP authentication](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/ldap/)
- [GitLab — LDAP integration](https://docs.gitlab.com/ee/administration/auth/ldap/)
- [OWASP SAML Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SAML_Security_Cheat_Sheet.html)
