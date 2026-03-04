---
title: "JWT — JSON Web Token"
slug: jwt
category: security
tags: [jwt, json-web-token, firma, validazione, sicurezza-token, rs256, es256]
search_keywords: [jwt json web token, jwt structure, jwt header payload signature, jwt claims, jwt signing algorithms, rs256 es256 hs256, jwt validation, jwt attacks, alg none attack, algorithm confusion attack, jwt secret weak, jwt expiration, jti claim, nbf claim, jwt key rotation, jwks json web key set, jwt introspection, opaque token vs jwt, jwt size optimization, jwt compression, nested jwt, jwt encryption jwe, jwt best practices, jwt revocation, jwt blacklist, jwt public key, jwt private key, jwt symmetric asymmetric]
parent: security/autenticazione/_index
related: [security/autenticazione/oauth2-oidc, security/pki-certificati/pki-interna, security/autorizzazione/rbac-abac-rebac]
official_docs: https://jwt.io/
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# JWT — JSON Web Token

## Panoramica

Un **JWT** (pronunciato "jot") è un modo compatto e autoverificabile per trasmettere informazioni tra parti come oggetto JSON firmato digitalmente. La chiave del suo valore: chi riceve il JWT può verificare la firma **offline**, senza fare una chiamata di rete all'issuer — zero latenza, zero dipendenza.

In un'architettura a microservizi, questo è il motivo per cui JWT è lo standard per gli access token: ogni servizio può verificare autonomamente che il token è autentico, non scaduto e destinato a lui, con una semplice operazione crittografica locale.

!!! warning "JWT non è magico"
    JWT risolve l'autenticità e l'integrità del token — non la revoca in tempo reale. Un JWT valido è valido fino alla scadenza, anche se l'utente è stato bannato 10 secondi fa. La progettazione del lifetime e delle strategie di revoca è cruciale.

---

## Struttura

Un JWT è composto da tre parti codificate in Base64URL, separate da punti:

```
header.payload.signature

eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InJzYS0yMDI0LTAxIn0
.
eyJzdWIiOiJ1c2VyLTEyMyIsImlzcyI6Imh0dHBzOi8vaWRwLmV4YW1wbGUuY29tIiwiYXVkIjoiaHR0cHM6Ly9hcGkuZXhhbXBsZS5jb20iLCJpYXQiOjE3MDYxODQwMDAsImV4cCI6MTcwNjE4NDMwMCwibmJmIjoxNzA2MTg0MDAwLCJqdGkiOiI4YjE0M2EyYS1mYzE5LTQ4YzQtYWJlYS04YzY4NjM5MzMxZTUiLCJzY29wZSI6Im9yZGVyczpyZWFkIiwicm9sZXMiOlsidXNlciJdfQ
.
<firma_digitale>
```

### Header

```json
{
  "alg": "RS256",               // algoritmo di firma
  "typ": "JWT",                 // tipo di token
  "kid": "rsa-2024-01"         // key ID → permette al server di scegliere la chiave giusta dal JWKS
}
```

Il `kid` è fondamentale per la **key rotation**: quando l'IdP (Identity Provider — il sistema che autentica gli utenti ed emette i token) ruota le chiavi di firma, emette nuovi JWT con un nuovo `kid`. Il resource server recupera le JWKS (JSON Web Key Set — il documento pubblico che contiene le chiavi di firma del provider) e trova la chiave corrispondente — zero downtime durante la rotazione.

### Payload — I Claims

```json
{
  // ─── Registered Claims (RFC 7519) ───────────────────────────────────────
  "iss": "https://idp.example.com",         // Issuer: chi ha emesso il token
  "sub": "user-123",                         // Subject: chi è il token (user ID)
  "aud": "https://api.example.com",          // Audience: a chi è destinato
  "exp": 1706184300,                         // Expiration: timestamp Unix di scadenza
  "nbf": 1706184000,                         // Not Before: non valido prima di (raro, utile per pre-emissione)
  "iat": 1706184000,                         // Issued At: quando è stato emesso
  "jti": "8b143a2a-fc19-48c4-abea-8c68639331e5",  // JWT ID: identificatore univoco

  // ─── Application Claims ─────────────────────────────────────────────────
  "scope": "orders:read inventory:read",     // permessi OAuth 2.0
  "roles": ["viewer"],                       // ruoli applicativi
  "tenant_id": "acme-corp",                  // multi-tenancy
  "azp": "frontend-spa",                     // Authorized Party: il client che ha ottenuto il token

  // ─── Standard OIDC Claims (se ID Token) ────────────────────────────────
  "name": "Mario Rossi",
  "email": "mario@example.com",
  "email_verified": true,
  "given_name": "Mario",
  "family_name": "Rossi"
}
```

**Claims obbligatori da validare sempre:**

| Claim | Validazione | Perché è critica |
|-------|-------------|-----------------|
| `iss` | Deve essere uguale all'issuer atteso | Previene accettazione di token da IdP non fidati |
| `aud` | Deve contenere l'identifier del tuo servizio | Previene che un token per service-A sia usato su service-B |
| `exp` | Deve essere > now | Token scaduti non devono essere accettati |
| `nbf` | Deve essere ≤ now (se presente) | Token pre-emessi non ancora validi |
| `alg` (header) | Deve essere in una whitelist | Previene algorithm confusion attacks |

### Signature

La firma è calcolata su `BASE64URL(header) + "." + BASE64URL(payload)`:

```
RSASSA-PKCS1-v1_5(SHA-256,
  private_key,
  BASE64URL(header) + "." + BASE64URL(payload)
)
```

La firma garantisce **autenticità** (solo chi ha la chiave privata può creare il token) e **integrità** (qualsiasi modifica al payload invalida la firma).

---

## Algoritmi di Firma — Scegliere Correttamente

```
HS256 (HMAC-SHA256)
  Tipo: simmetrico
  Chiave: un secret condiviso tra issuer e verifier
  Problema: tutti i servizi che devono verificare devono conoscere il secret
            → se un servizio è compromesso, l'attacker può forgiare token per tutti
  Uso: solo in sistemi monolitici o quando issuer == verifier

RS256 (RSA-SHA256, 2048+ bit)
  Tipo: asimmetrico
  Chiave privata: solo l'IdP — firma i token
  Chiave pubblica: tutti i servizi — solo verificano, non possono forgiare
  Problema: operazione RSA è computazionalmente costosa (ma cachata in pratica)
  Uso: ✅ Standard per token OAuth 2.0 / OIDC in produzione

ES256 (ECDSA P-256)
  Tipo: asimmetrico (curva ellittica)
  Vantaggi vs RS256: chiavi più piccole (256 bit vs 2048 bit), firma più veloce
  Sicurezza equivalente: ES256 ≈ RS256 2048-bit per forza crittografica
  Uso: ✅ Preferito per sistemi ad alta frequenza, IoT

PS256 (RSASSA-PSS + SHA-256)
  Tipo: asimmetrico RSA con padding probabilistico
  Più sicuro di RS256 in teoria, stessa chiave RSA
  Uso: ambienti con requisiti FIPS o normative specifiche
```

**La regola**: in un'architettura microservizi enterprise, usa sempre algoritmi **asimmetrici** (RS256 o ES256). L'IdP firma con la chiave privata; i microservizi verificano con la chiave pubblica scaricata dal JWKS endpoint. Nessun microservizio conosce mai il secret.

---

## Attacchi Noti e Mitigazioni

### Attacco 1: `alg: none`

Il JWT RFC originariamente permetteva `"alg": "none"` per token non firmati. Alcune librerie vecchie o mal configurate **accettano ancora** token con alg:none, ignorando la firma.

```
Payload originale: {"sub":"user-1","roles":["user"]}
                                    ↓
Attacker modifica: {"sub":"user-1","roles":["admin"]}
Crea header:       {"alg":"none"}
Firma:             (vuota)
Risultato:         eyJhbGciOiJub25lIn0.eyJzdWIiOiJ1c2VyLTEiLCJyb2xlcyI6WyJhZG1pbiJdfQ.
```

**Mitigazione**: whitelist esplicita degli algoritmi accettati (`["RS256", "ES256"]`) — mai accettare la lista dall'header del token stesso.

```python
# ✅ Corretto: algoritmo specificato dal verifier, non dal token
jwt.decode(token, public_key, algorithms=["RS256", "ES256"])

# ❌ Sbagliato: il token decide quale algoritmo usare
algorithms = jwt.get_unverified_header(token)["alg"]  # ATTACK VECTOR
jwt.decode(token, public_key, algorithms=[algorithms])
```

### Attacco 2: Algorithm Confusion (RS256 → HS256)

Se un server accetta sia RS256 che HS256, un attacker può ingannarlo:

```
Setup legittimo:
  Token firmato con private_key RSA → verificato con public_key RSA

Attacco:
  1. Attacker ottiene la public_key RSA del server (è pubblica per definizione)
  2. Forgia un token con header: {"alg": "HS256"}
  3. Firma il token con la public_key RSA usata come HMAC secret
  4. Il server mal configurato, vedendo HS256, usa la public_key come HMAC secret
  5. La verifica HMAC passa → token forgiato accettato
```

**Mitigazione**: accettare **un solo algoritmo** per tipo di token. Non mescolare HS256 e RS256 nello stesso sistema.

### Attacco 3: JWT Secret Brute-Force (HS256)

I token HS256 firmati con secret deboli sono vulnerabili a offline brute-force:

```bash
# Hashcat riesce a rompere HS256 con secret deboli in secondi/minuti
hashcat -a 0 -m 16500 target.jwt /wordlists/rockyou.txt
```

**Mitigazione**: non usare HS256 in produzione; se lo usi, il secret deve essere almeno 256 bit di entropia pura (32 byte casuali da un CSPRNG).

### Attacco 4: JWT Token Theft e Replay

Un token JWT rubato (da XSS, log, man-in-the-middle su HTTP) è completamente valido fino alla scadenza. L'attacker può impersonare l'utente senza problemi.

**Mitigazioni stratificate:**
1. **Lifetime breve** (5-15 min) — limita la finestra di utilizzo
2. **DPoP** (Demonstrating Proof-of-Possession, RFC 9449): il token è legato alla chiave privata del client originale — inutile se rubato
3. **Token Binding**: legare il token alla sessione TLS (sperimentale)
4. **Audience ristretta**: `aud` al resource server specifico — non utilizzabile altrove

---

## Checklist di Validazione Completa

```python
from datetime import datetime, timezone
import jwt
from jwt import PyJWKClient

JWKS_CLIENT = PyJWKClient("https://idp.example.com/.well-known/jwks.json",
                           cache_jwk_set=True, lifespan=300)  # cache 5 min

ALLOWED_ALGORITHMS = frozenset(["RS256", "ES256"])
EXPECTED_ISSUER = "https://idp.example.com"
EXPECTED_AUDIENCE = "https://api.myservice.example.com"

def validate_jwt(token: str) -> dict:
    # Step 1: Estrai header SENZA verifica (solo per leggere kid e alg)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as e:
        raise InvalidTokenError(f"Token malformato: {e}")

    # Step 2: Verifica algoritmo in whitelist
    if unverified_header.get("alg") not in ALLOWED_ALGORITHMS:
        raise InvalidTokenError(f"Algoritmo non ammesso: {unverified_header.get('alg')}")

    # Step 3: Recupera chiave pubblica via kid
    try:
        signing_key = JWKS_CLIENT.get_signing_key_from_jwt(token)
    except Exception as e:
        raise InvalidTokenError(f"Chiave di firma non trovata: {e}")

    # Step 4: Verifica completa (firma + claims temporali + iss + aud)
    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=list(ALLOWED_ALGORITHMS),
            audience=EXPECTED_AUDIENCE,
            issuer=EXPECTED_ISSUER,
            leeway=5,  # 5s clock skew tollerance
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", "jti"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
            }
        )
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token scaduto")
    except jwt.InvalidAudienceError:
        raise InvalidTokenError("Audience non valida — token non destinato a questo servizio")
    except jwt.InvalidIssuerError:
        raise InvalidTokenError("Issuer non riconosciuto")
    except jwt.MissingRequiredClaimError as e:
        raise InvalidTokenError(f"Claim obbligatorio mancante: {e}")
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"Validazione fallita: {e}")

    # Step 5 (opzionale): Revocation check via JTI — solo se RPO di revoca breve è obbligatorio
    # if is_token_revoked(payload["jti"]):
    #     raise InvalidTokenError("Token revocato")

    return payload
```

---

## Revoca dei JWT

La revoca è il punto debole dei JWT. Quattro strategie, ordinate per complessità crescente:

```
1. Lifetime breve (5-15 min)
   Pro: semplice, no infrastruttura
   Contro: finestra di 5-15 min è ancora ampia per alcune minacce

2. Refresh Token rotation + invalidazione sessione
   Quando l'utente fa logout → invalida il refresh token sull'IdP
   → L'access token corrente rimane valido fino a exp, ma non può essere rinnovato
   → Finestra = durata access token rimanente

3. JTI Blocklist (revocation list)
   IdP mantiene una lista di jti revocati (in Redis con TTL = exp - now)
   Il resource server consulta Redis per ogni richiesta
   Pro: revoca immediata
   Contro: latenza + Redis diventa un SPOF (Single Point of Failure — nodo la cui interruzione causa un'interruzione del servizio intero) + dataset cresce con i token attivi
   Uso: solo per scenari critici (logout forzato, account compromesso)

4. Token Introspection (RFC 7662)
   Il resource server chiama /introspect sull'IdP per ogni token
   → Lo stato live viene restituito {"active": true/false}
   Pro: revoca immediata, verità single source
   Contro: latenza di rete per ogni richiesta, IdP diventa hot path
   Uso: sistemi ad alta sicurezza dove latenza < 1ms non è richiesta
   Ottimizzazione: cache con TTL 30s = revoca in max 30s
```

---

## Dimensioni e Performance

```
Un JWT tipico ha questa dimensione (gzip prima della trasmissione):
  Header:  ~80 byte
  Payload: ~400 byte (con claims standard + custom)
  Firma:   RS256 = 342 byte, ES256 = ~96 byte
  Totale:  ~500-900 byte non compresso

Per HTTP/2 con header compression (HPACK):
  Il primo invio trasmette il JWT completo
  Le richieste successive usano riferimenti → overhead quasi nullo

Implicazione: ES256 produce token ~30% più piccoli di RS256.
In ambienti ad alta frequenza (IoT, API ad alto volume) la differenza è misurabile.
```

**Claims da non includere:**
- Nessun dato sensibile (PII, password, chiavi) — il payload è solo Base64URL, non cifrato
- Nessun dato che cambia frequentemente (come l'avatar URL) — invaliderebbe il caching
- Nessun dato ridondante se già nel Resource Server — ogni byte in più è overhead

---

## JWE — JWT Cifrato (Quando Serve)

Un JWT standard è firmato ma **non cifrato** — il payload è leggibile da chiunque intercetti il token. Per payload con dati sensibili, usa **JWE (JSON Web Encryption)**:

```
JWE = header . encrypted_key . iv . ciphertext . tag
                    (chiave simmetrica              (payload cifrato
                     cifrata con chiave pubblica     con AES-GCM)
                     del destinatario)
```

**Quando usare JWE:**
- Il token passa attraverso sistemi non fidati (es. in un URL parameter → NO, ma se obbligato)
- Il payload contiene informazioni riservate che non devono essere visibili (es. informazioni mediche in contesti HIPAA — Health Insurance Portability and Accountability Act, normativa USA sulla privacy dei dati sanitari)
- In genere: preferire **non mettere dati sensibili nel JWT** invece di cifrarlo — più semplice e meno rischi

---

## Best Practices Riassuntive

- **RS256 o ES256** per i token di produzione — mai HS256 in sistemi multi-servizio
- **Whitelist algoritmi** nel verifier — mai accettare l'algoritmo dall'header del token
- **Valida sempre `aud`**: ogni microservizio deve avere un audience unica e verificarla
- **`exp` breve (5-15 min)**: bilancia usabilità e sicurezza
- **`jti` per audit trail**: ogni token ha un ID univoco → rintraccibilità in caso di incidente
- **Non mettere segreti nel payload**: il JWT è firmato, non cifrato
- **Key rotation regolare**: RS256/ES256 keys devono essere ruotate almeno ogni 6-12 mesi con `kid` tracking

## Riferimenti

- [RFC 7519 — JSON Web Token (JWT)](https://www.rfc-editor.org/rfc/rfc7519)
- [RFC 7515 — JSON Web Signature (JWS)](https://www.rfc-editor.org/rfc/rfc7515)
- [RFC 7516 — JSON Web Encryption (JWE)](https://www.rfc-editor.org/rfc/rfc7516)
- [JWT.io — Debugger e Librerie](https://jwt.io/)
- [PortSwigger — JWT Attacks](https://portswigger.net/web-security/jwt)
