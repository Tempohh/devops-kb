---
title: "OAuth 2.0 e OpenID Connect"
slug: oauth2-oidc
category: security
tags: [oauth2, oidc, openid-connect, autenticazione, autorizzazione-delegata, token, pkce, keycloak]
search_keywords: [oauth2 flows, openid connect, authorization code flow, pkce, client credentials, implicit flow, device flow, token endpoint, authorization endpoint, introspection endpoint, userinfo endpoint, jwks endpoint, keycloak oauth2, aws cognito oauth2, azure entra id oauth2, auth0, token exchange, jwt access token, refresh token rotation, scope, audience, issuer, identity federation, sso single sign on, oauth2 enterprise, oauth2 microservices, service to service oauth2, m2m machine to machine, resource server, authorization server, relying party, claims, id token, access token opaque, token lifetime, silent refresh, bff pattern security]
parent: security/autenticazione/_index
related: [security/autenticazione/jwt, security/autorizzazione/rbac-abac-rebac, security/autenticazione/mtls-spiffe]
official_docs: https://oauth.net/2/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# OAuth 2.0 e OpenID Connect

## Panoramica

**Il problema che OAuth 2.0 risolve**: prima di OAuth, un'applicazione che doveva accedere a risorse di un utente su un servizio terzo richiedeva le credenziali dell'utente. L'app poteva quindi impersonare completamente l'utente senza limiti e senza che l'utente potesse revocare l'accesso senza cambiare password.

**OAuth 2.0** è un framework di **autorizzazione delegata**: consente a un'applicazione (Client) di ottenere accesso limitato a risorse di un utente (Resource Owner) su un servizio (Resource Server), senza mai conoscere le credenziali dell'utente. L'accesso è mediato da un **Authorization Server** che emette token con scope limitati e revocabili.

**OpenID Connect (OIDC)** è uno strato di **identità** costruito sopra OAuth 2.0: aggiunge l'**ID Token** (un JWT che contiene l'identità verificata dell'utente) e il concetto di **autenticazione**, non solo autorizzazione. OIDC trasforma OAuth 2.0 da un sistema di accesso a un sistema di login federato.

!!! tip "Distinzione fondamentale"
    - **OAuth 2.0**: risponde a "può questa app accedere a questa risorsa per conto di questo utente?" → autorizzazione
    - **OpenID Connect**: risponde a "chi è questo utente?" → autenticazione
    - In un'architettura enterprise, li usi **sempre insieme**.

---

## Attori del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Resource Owner          Authorization Server        Resource Server│
│  (Utente finale          (Keycloak / Entra ID /      (Il tuo API,  │
│   o sistema M2M)          Cognito / Auth0)            Microservizio)│
│                                                                     │
│       │                         │                         │         │
│       │                         │                         │         │
│       └─── Client ──────────────┘─────────────────────────┘         │
│            (La tua app:                                             │
│             SPA, mobile,                                            │
│             backend, lambda)                                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Client types** (con implicazioni di sicurezza diverse):
- **Confidential client**: può mantenere un segreto (backend server, servizio M2M). Usa `client_secret`
- **Public client**: non può mantenere un segreto (SPA, mobile app — il codice è nelle mani dell'utente). **Non deve avere un `client_secret`**; usa PKCE

---

## I Grant Type — Quando Usare Cosa

### 1. Authorization Code + PKCE — Utenti Umani

Il flusso corretto per **qualsiasi applicazione che autentica utenti**: SPA, app mobile, web app con server.

```
                     Browser / App Mobile (Public Client)
                             │
               1. Naviga verso /authorize
               ──────────────────────────────────────────>  Authorization Server
                             │
                             │  2. Login dell'utente
                             │     (form di login, MFA)
               <──────────────────────────────────────────
                             │  3. Redirect con code + state
               4. Scambia code → tokens
               ──────────────────────────────────────────>  Token Endpoint
               <──────────────────────────────────────────
                             │  Access Token + Refresh Token + ID Token
                             │
               5. Chiama API con Access Token
               ──────────────────────────────────────────>  Resource Server
               <──────────────────────────────────────────  risposta protetta
```

**PKCE (Proof Key for Code Exchange)** — obbligatorio per public client, raccomandato per tutti:

```
App genera:
  code_verifier = 43-128 caratteri casuali (base64url)  → es. "dBjftJeZ4CVP-mB92K..."
  code_challenge = BASE64URL(SHA256(code_verifier))     → es. "E9Melhoa2OwvFrEMTJgu..."

1. /authorize?code_challenge=E9Melhoa...&code_challenge_method=S256
                    (code_verifier rimane segreto nell'app)

2. Authorization Server salva code_challenge associato al code

3. /token?code=xxx&code_verifier=dBjftJeZ4CVP...
   Authorization Server verifica: SHA256(code_verifier) == code_challenge → OK

ATTACCO MITIGATO: se un malicious app intercetta il code (redirect URI hijack),
non può scambiarlo in token perché non conosce il code_verifier originale.
```

```python
import secrets, hashlib, base64

# Generazione PKCE (lato client)
def generate_pkce():
    code_verifier = secrets.token_urlsafe(96)  # 128 char base64url-safe
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return code_verifier, code_challenge

code_verifier, code_challenge = generate_pkce()

# URL di authorization
auth_url = (
    f"https://idp.example.com/oauth2/authorize"
    f"?client_id=my-spa"
    f"&response_type=code"
    f"&redirect_uri=https://app.example.com/callback"
    f"&scope=openid+profile+email+api:read"
    f"&state={secrets.token_urlsafe(32)}"  # CSRF protection
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
)
```

---

### 2. Client Credentials — Machine-to-Machine (M2M)

Il flusso per **comunicazione servizio-servizio** senza utente coinvolto. Non c'è interazione umana, non c'è redirect browser.

```
Microservizio A (Confidential Client)
         │
         │ POST /token
         │  client_id=service-a
         │  client_secret=xxx (oppure client_assertion JWT firmato)
         │  grant_type=client_credentials
         │  scope=service-b:read service-b:write
         ▼
   Authorization Server
         │
         ◄─ Access Token (JWT, scadenza breve: 5-15 min)
         │
         │ Authorization: Bearer <access_token>
         ▼
   Microservizio B (Resource Server)
         │
         │ Verifica JWT localmente (firma + claims)
         ◄─ risposta
```

```python
# Acquisizione token M2M con client_credentials (httpx)
import httpx
from functools import lru_cache
from datetime import datetime, timedelta

class TokenCache:
    def __init__(self):
        self._token = None
        self._expires_at = None

    def get_token(self, token_endpoint: str, client_id: str, client_secret: str, scope: str) -> str:
        # Rinnova 30s prima della scadenza
        if self._token and datetime.utcnow() < self._expires_at - timedelta(seconds=30):
            return self._token

        response = httpx.post(token_endpoint, data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        })
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
        return self._token

_cache = TokenCache()

def call_service_b(endpoint: str) -> dict:
    token = _cache.get_token(
        "https://idp.example.com/oauth2/token",
        "service-a", SECRET_FROM_VAULT, "service-b:read"
    )
    resp = httpx.get(endpoint, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json()
```

!!! warning "Client secret vs JWT client assertion"
    In contesti enterprise/cloud, preferire **JWT client assertion** (`private_key_jwt`) al posto del `client_secret`:
    - Il secret è una password statica — può essere rubata
    - JWT assertion: il client firma un JWT con la propria chiave privata → il server verifica con la chiave pubblica registrata
    - La chiave privata può essere rotata senza cambiare la configurazione del server
    - AWS, Azure e GCP supportano workload identity federation come alternativa a client credentials fissi

---

### 3. Device Flow — Dispositivi Senza Browser

```
Smart TV, CLI tool, IoT device:

1. POST /device/authorize → device_code, user_code, verification_uri
2. Mostra all'utente: "Vai su https://device.example.com e inserisci il codice ABCD-1234"
3. Polling su /token ogni 5s finché l'utente completa
4. Utente su browser: login + inserisce user_code → autorizza
5. Polling riceve Access Token
```

---

## I Token — Struttura e Scopo

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Token Types                                      │
├──────────────────┬──────────────────────────────────────────────────┤
│ Access Token     │ Autorizza l'accesso a una risorsa.               │
│                  │ Lifetime breve (5 min - 1h)                      │
│                  │ JWT (verificabile offline) o Opaque (introspect) │
│                  │ NON deve essere consegnato all'utente finale      │
├──────────────────┼──────────────────────────────────────────────────┤
│ Refresh Token    │ Rinnova l'access token senza nuovo login.         │
│                  │ Lifetime lungo (giorni/settimane)                 │
│                  │ Sempre opaque (non JWT), ruotato a ogni uso       │
│                  │ Storage sicuro obbligatorio (httpOnly cookie)     │
├──────────────────┼──────────────────────────────────────────────────┤
│ ID Token         │ Identità dell'utente autenticato.                 │
│                  │ Sempre JWT, contiene claims utente                │
│                  │ Solo per il client che ha fatto il login          │
│                  │ NON usare come bearer token verso API             │
└──────────────────┴──────────────────────────────────────────────────┘
```

**La confusione più comune in produzione**: usare l'ID Token come Access Token per chiamare API. L'ID Token contiene le info dell'utente; l'Access Token contiene i permessi sulle risorse. Sono oggetti distinti con audience diversa.

---

## Endpoint OIDC — Il Discovery Document

Tutti gli Authorization Server conformi OIDC pubblicano un discovery document:

```bash
curl https://idp.example.com/.well-known/openid-configuration
```

```json
{
  "issuer": "https://idp.example.com",
  "authorization_endpoint": "https://idp.example.com/oauth2/authorize",
  "token_endpoint": "https://idp.example.com/oauth2/token",
  "userinfo_endpoint": "https://idp.example.com/oauth2/userinfo",
  "jwks_uri": "https://idp.example.com/.well-known/jwks.json",
  "introspection_endpoint": "https://idp.example.com/oauth2/introspect",
  "revocation_endpoint": "https://idp.example.com/oauth2/revoke",
  "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "scopes_supported": ["openid", "profile", "email", "offline_access"]
}
```

---

## Validazione del Token nel Resource Server

Un Resource Server (microservizio che riceve access token) deve validare:

```python
import jwt
import httpx
from jwt import PyJWKClient

# 1. Recupera le chiavi pubbliche dal jwks_uri (con cache)
jwks_client = PyJWKClient("https://idp.example.com/.well-known/jwks.json")

def validate_access_token(token: str) -> dict:
    try:
        # 2. Ottieni la chiave corrispondente al kid nel header del JWT
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # 3. Verifica firma, scadenza, issuer, audience
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],   # NON HS256 per token pubblici
            audience="https://api.example.com",  # il tuo resource server
            issuer="https://idp.example.com",
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_exp": True,
                "verify_iat": True,
                "leeway": 5,    # 5s di tolleranza per clock skew
            }
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise Unauthorized("Token scaduto")
    except jwt.InvalidAudienceError:
        raise Unauthorized("Token non valido per questo servizio")
    except jwt.InvalidIssuerError:
        raise Unauthorized("Issuer non riconosciuto")
    except jwt.PyJWTError as e:
        raise Unauthorized(f"Token non valido: {e}")
```

**JWT vs Opaque Token per Access Token:**

| | JWT | Opaque |
|---|-----|--------|
| Verifica | Offline (firma) — latenza 0 | Online (introspection) — latenza + I/O |
| Revoca immediata | No — valido fino a `exp` | Sì — introspection reflect lo stato live |
| Dimensione | Grande (0.5-3 KB) | Piccola (32-64 byte) |
| Uso tipico | Access token per microservizi | Refresh token |
| Cache necessaria? | No | Sì (TTL breve) |

---

## Token Lifetime e Refresh Strategy

```
Lifetime consigliato per produzione enterprise:

Access Token:     5 - 15 minuti
  → breve per limitare la finestra di compromissione
  → i microservizi cachano e rinnovano internamente

Refresh Token:    24h - 7 giorni (con rotation)
  → rotation: ogni utilizzo emette un nuovo refresh token + invalida il vecchio
  → absolute lifetime: max 30 giorni → forza re-login

ID Token:        stessa durata dell'access token
  → usato solo per l'UI, non per le API
```

```
Refresh Token Rotation:

1. App ha: AT(exp=14:05) + RT(valid)
2. AT scade alle 14:05
3. App chiama /token con grant_type=refresh_token + RT-1
4. Server emette: AT-2(exp=14:20) + RT-2 + invalida RT-1
5. Se un attacker aveva rubato RT-1 e lo usa dopo il punto 4:
   → Token reuse detected → Authorization Server invalida TUTTA la session
   → Sia l'attacker che l'utente legittimo vengono disconnessi → utente si ri-autentica
```

---

## Configurazione Keycloak (Self-hosted IdP)

```yaml
# docker-compose.yml — Keycloak + PostgreSQL per sviluppo/staging
services:
  keycloak:
    image: quay.io/keycloak/keycloak:25
    command: start-dev --import-realm
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://keycloak-db:5432/keycloak
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: ${KC_DB_PASSWORD}
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: ${KC_ADMIN_PASSWORD}
      KC_HOSTNAME: auth.example.com
      KC_HTTPS_CERTIFICATE_FILE: /tls/tls.crt
      KC_HTTPS_CERTIFICATE_KEY_FILE: /tls/tls.key
    ports:
      - "8443:8443"
    volumes:
      - ./keycloak/realm-export.json:/opt/keycloak/data/import/realm.json
      - ./tls:/tls
    depends_on:
      keycloak-db:
        condition: service_healthy
```

```json
// Configurazione realm (estratto)
{
  "realm": "enterprise",
  "enabled": true,
  "sslRequired": "external",
  "accessTokenLifespan": 300,           // 5 minuti
  "ssoSessionIdleTimeout": 1800,         // 30 minuti idle
  "ssoSessionMaxLifespan": 36000,        // 10 ore max sessione
  "refreshTokenMaxReuse": 0,             // 0 = rotation obbligatoria
  "bruteForceProtected": true,
  "failureFactor": 5,                    // lock dopo 5 tentativi falliti
  "waitIncrementSeconds": 60,
  "clients": [
    {
      "clientId": "frontend-spa",
      "publicClient": true,              // Public client: no secret
      "redirectUris": ["https://app.example.com/callback"],
      "webOrigins": ["https://app.example.com"],
      "attributes": {
        "pkce.code.challenge.method": "S256"  // PKCE obbligatorio
      }
    },
    {
      "clientId": "service-a",
      "serviceAccountsEnabled": true,    // Abilita client_credentials
      "standardFlowEnabled": false,
      "directAccessGrantsEnabled": false
    }
  ]
}
```

---

## Token Exchange — Propagazione dell'Identità Utente tra Servizi

Quando il microservizio A riceve un token utente e deve chiamare il microservizio B **portando l'identità dell'utente originale**, non deve passare il token dell'utente direttamente (security anti-pattern). Usa **Token Exchange** (RFC 8693):

```
Utente → API Gateway → Service A → [TOKEN EXCHANGE] → Service B

Service A:
  POST /token
    grant_type=urn:ietf:params:oauth:grant-type:token-exchange
    subject_token=<token_utente>
    subject_token_type=urn:ietf:params:oauth:token-type:access_token
    requested_token_type=urn:ietf:params:oauth:token-type:access_token
    audience=service-b
    scope=service-b:read

→ Service A riceve un nuovo token scoped per service-b, con il sub dell'utente originale
   ma con i permessi limitati a ciò che service-a può delegare a service-b
```

---

## Errori Comuni e Come Evitarli

| Anti-pattern | Rischio | Soluzione |
|---|---|---|
| Implicit Flow (senza PKCE) | Token nell'URL → leakage in log, referrer | Authorization Code + PKCE |
| `client_secret` in SPA/mobile | Secret esposto nel codice client | Public client senza secret |
| Access Token in localStorage | XSS ruba il token | httpOnly cookie per refresh token; in-memory per access token |
| ID Token usato come bearer | Audience errata, claims non progettati per API | Usare Access Token per API, ID Token solo per UI |
| Nessuna validazione `aud` | Un token per service-A accettato da service-B | Validare sempre `aud` = identifier del resource server |
| Token lifetime troppo lungo | Finestra di compromissione ampia | Max 15 min per access token |
| Nessuna revoca in logout | After-logout il token è ancora valido | Implementare logout dal'IdP + token revocation |

---

## Best Practices Enterprise

- **Un solo Identity Provider per l'intera organizzazione**: federare tutti i servizi su un unico IdP (Keycloak / Entra ID / Okta). SSO, audit centralizzato, gestione utenti unica
- **Scope granulari per ogni servizio**: `orders:read`, `orders:write`, `payments:process` — non un unico scope generico `api:access`. Permette least privilege a livello di authorization server
- **Rotazione automatica chiavi di firma**: l'IdP deve ruotare le chiavi RS256/ES256 almeno ogni 6 mesi. Il resource server deve cachare le JWKS con TTL breve per pick up automatico della nuova chiave
- **Client credentials da Vault o Workload Identity**: non hardcodare `client_secret` in env var o ConfigMap — usa HashiCorp Vault o cloud workload identity (AWS IRSA, GCP Workload Identity)
- **Token binding per ambienti ad alto rischio**: considera DPoP (Demonstrating Proof-of-Possession, RFC 9449) per legare il token alla chiave privata del client — un token rubato non è riutilizzabile senza la chiave corrispondente

## Riferimenti

- [RFC 6749 — OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/rfc/rfc6749)
- [RFC 7636 — PKCE](https://www.rfc-editor.org/rfc/rfc7636)
- [RFC 8693 — Token Exchange](https://www.rfc-editor.org/rfc/rfc8693)
- [RFC 9449 — DPoP](https://www.rfc-editor.org/rfc/rfc9449)
- [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)
- [OAuth 2.0 Security Best Current Practice](https://www.ietf.org/archive/id/draft-ietf-oauth-security-topics-25.txt)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
