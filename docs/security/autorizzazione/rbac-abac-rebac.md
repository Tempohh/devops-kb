---
title: "RBAC, ABAC e ReBAC — Modelli di Autorizzazione"
slug: rbac-abac-rebac
category: security
tags: [rbac, abac, rebac, autorizzazione, permessi, ruoli, attributi, relazioni]
search_keywords: [role based access control rbac, attribute based access control abac, relationship based access control rebac, zanzibar google authorization, spicedb openfga, authorization models comparison, fine grained authorization, coarse grained authorization, permission model, enterprise rbac, rbac vs abac, rbac kubernetes, abac policy, rebac social graph, multi-tenant authorization, row level security, column level security, privilege escalation, least privilege, scim provisioning, rbac design patterns, role explosion problem, attribute based policy, context aware authorization, dynamic authorization]
parent: security/autorizzazione/_index
related: [security/autorizzazione/opa, security/autenticazione/jwt, security/autenticazione/oauth2-oidc]
official_docs: https://csrc.nist.gov/publications/detail/sp/800-162/final
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# RBAC, ABAC e ReBAC — Modelli di Autorizzazione

## Panoramica

Un **modello di autorizzazione** definisce come rispondere alla domanda: _può il soggetto X eseguire l'azione Y sulla risorsa Z?_

I tre modelli principali risolvono classi di problemi diverse e spesso coesistono nella stessa architettura. La scelta non è ideologica ma dipende dal tipo di risorsa, dalla granularità richiesta e dalla complessità del dominio.

```
Continuum di complessità:

RBAC ─────────── ABAC ─────────────── ReBAC
(ruoli statici)  (attributi dinamici)  (grafi di relazioni)
Semplice         Flessibile             Potente ma complesso
Es: admin/user   Es: dept + livello     Es: "proprietario del documento"
                     + orario           "membro del team che ha accesso"
```

---

## RBAC — Role-Based Access Control

**Idea**: i permessi non sono assegnati direttamente agli utenti, ma ai **ruoli**. Gli utenti ricevono i ruoli. Questo separa la gestione dei permessi (cosa può fare il ruolo X) dalla gestione delle assegnazioni (chi è il ruolo X).

```
Utente ─── assegnato a ─── Ruolo ─── ha ─── Permesso
  │                          │                  │
mario.rossi           admin           orders:write
                      viewer          orders:read
                      billing         payments:read
                                      invoices:write
```

### Gerarchia dei Ruoli (RBAC gerarchico)

```
RBAC flat: ogni ruolo è indipendente → "role explosion" con molti servizi

RBAC gerarchico: i ruoli ereditano i permessi dai ruoli padre

    super-admin
       │
       ├── admin ─── user-admin, system-config
       │      └── developer ─── code:read, code:write, deploy:dev
       │             └── viewer ─── code:read, logs:read
       └── billing-admin ─── payments:*, invoices:*
              └── billing-viewer ─── payments:read, invoices:read
```

### RBAC in JWT

```json
// JWT payload con ruoli nel claim "roles"
{
  "sub": "user-123",
  "roles": ["developer", "billing-viewer"],
  "tenant_id": "acme-corp"
}
```

```python
# Autorizzazione RBAC nel microservizio
from functools import wraps
from typing import List

PERMISSIONS: dict[str, List[str]] = {
    "admin":          ["orders:read", "orders:write", "orders:delete", "users:*"],
    "developer":      ["orders:read", "orders:write", "logs:read"],
    "billing-viewer": ["payments:read", "invoices:read"],
    "viewer":         ["orders:read"],
}

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_roles = get_current_user_roles()  # dal JWT validato
            allowed = any(
                permission in PERMISSIONS.get(role, []) or
                f"{permission.split(':')[0]}:*" in PERMISSIONS.get(role, [])
                for role in user_roles
            )
            if not allowed:
                raise Forbidden(f"Permesso richiesto: {permission}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/orders", methods=["POST"])
@require_permission("orders:write")
def create_order():
    ...
```

### Il Problema del "Role Explosion"

Con molti servizi e granularità fine, il numero di ruoli esplode:

```
Con 10 servizi e 5 livelli di accesso per servizio:
  10 × 5 = 50 ruoli base

Con combinazioni (un utente può avere accesso read a service-A
                  e write a service-B ma non C):
  Possibili combinazioni = 2^50 (impossibile gestire)
```

**Soluzione**: RBAC per accesso **coarse-grained** (chi può accedere a quale servizio) + ABAC per accesso **fine-grained** (quali risorse specifiche all'interno del servizio).

---

## ABAC — Attribute-Based Access Control

**Idea**: la decisione di accesso è basata su **attributi** del soggetto, della risorsa, dell'azione e del contesto ambientale — non solo sul ruolo.

```
Soggetto:
  user.department = "engineering"
  user.level = "senior"
  user.location = "IT"

Risorsa:
  document.classification = "confidential"
  document.owner_department = "engineering"
  document.region = "EU"

Azione:
  action.type = "read"
  action.time = "14:32 UTC"

Ambiente:
  env.network = "corporate-vpn"
  env.device_trusted = true

Policy ABAC:
  ALLOW IF
    user.department == resource.owner_department AND
    user.level IN ["senior", "principal"] AND
    document.classification IN ["internal", "confidential"] AND
    env.device_trusted == true AND
    action.time BETWEEN "08:00" AND "22:00"
```

### ABAC con OPA (Policy as Code)

```rego
# Rego — linguaggio di policy di OPA
package orders.authz

# Regola: accesso all'ordine
default allow = false

allow {
    # L'utente può leggere i propri ordini
    input.action == "read"
    input.resource.owner_id == input.user.id
}

allow {
    # Gli admin possono leggere tutti gli ordini
    input.action == "read"
    "admin" in input.user.roles
}

allow {
    # Il team support può leggere ordini della propria regione
    input.action == "read"
    "support" in input.user.roles
    input.resource.region == input.user.region
    time.now_ns() >= time.parse_rfc3339_ns("08:00:00Z")  # solo in orario lavorativo
}

allow {
    # Il proprietario può modificare l'ordine solo se in stato "draft"
    input.action == "write"
    input.resource.owner_id == input.user.id
    input.resource.status == "draft"
}
```

**ABAC è potente ma complesso**: le policy diventano difficili da ragionare e testare. La disciplina di test (vedi sezione OPA) è fondamentale.

---

## ReBAC — Relationship-Based Access Control

**Idea**: i permessi derivano dalle **relazioni** nel grafo degli oggetti. "Mario può leggere il documento X perché è membro del team Y che ha accesso alla cartella Z che contiene X."

Questo è il modello che usa Google per Drive, Docs, Calendar — documentato nel paper **Google Zanzibar**.

```
Grafo delle relazioni:

mario ──── member ──►  Team Engineering
                              │
                              └── viewer ──►  Folder /projects
                                                    │
                                                    └── contains ──►  Document A
                                                                          │
                                                                          └── owner: alice

Domanda: "mario può leggere Document A?"

Traversata del grafo:
  mario è member di Team Engineering
  Team Engineering è viewer di Folder /projects
  Document A è in Folder /projects
  viewer di una folder → viewer dei documenti contenuti (per transitività)
  → SÌ, mario può leggere Document A
```

### Quando ReBAC è Necessario

- Strutture gerarchiche profonde (cartelle, organizzazioni, team annidati)
- "Proprietà" e "appartenenza" come driver di accesso (il mio documento, il mio team)
- Permessi che si propagano attraverso relazioni (member of group that owns resource)
- Social/collaborative features (condivisione con un utente specifico, con un link)

### OpenFGA / SpiceDB — Implementazioni di Zanzibar

[OpenFGA](https://openfga.dev/) (Fork di Okta) e [SpiceDB](https://github.com/authzed/spicedb) (AuthZed) sono le implementazioni open source del modello Zanzibar:

```yaml
# OpenFGA — definizione del modello (authorization schema)
model
  schema 1.1

type user

type team
  relations
    define member: [user]

type folder
  relations
    define owner: [user]
    define viewer: [user, user:*, team#member]  # team#member = tutti i member del team
    define can_read: viewer or owner

type document
  relations
    define parent_folder: [folder]
    define owner: [user]
    define viewer: [user, user:*, team#member]
    define can_read: viewer or owner or (can_read from parent_folder)  # transitività!
    define can_write: owner or (owner from parent_folder)
```

```python
# Python — query OpenFGA
from openfga_sdk import OpenFgaClient, CheckRequest, TupleKey

client = OpenFgaClient(configuration)

# Scrivi le relazioni (quando l'utente agisce)
await client.write({
    "writes": {
        "tuple_keys": [
            {"user": "user:mario", "relation": "member", "object": "team:engineering"},
            {"user": "team:engineering#member", "relation": "viewer", "object": "folder:projects"},
            {"user": "folder:projects", "relation": "parent_folder", "object": "document:report-q4"},
        ]
    }
})

# Query: mario può leggere document:report-q4?
result = await client.check(CheckRequest(
    tuple_key=TupleKey(
        user="user:mario",
        relation="can_read",
        object="document:report-q4"
    )
))
print(result.allowed)  # True
```

---

## Combinare i Modelli in Produzione

Un sistema enterprise reale usa tipicamente tutti e tre i modelli a livelli diversi:

```
Layer 1 — API Gateway (RBAC coarse-grained):
  "Questo client ha il ruolo che gli permette di chiamare /orders?"
  → JWT claims + scope OAuth 2.0

Layer 2 — Microservizio (ABAC):
  "Questo utente, con questi attributi, può eseguire questa azione
   su questo tipo di risorsa, in questo contesto?"
  → OPA policy

Layer 3 — Database (ReBAC / Row-Level Security):
  "Questo utente può vedere questa specifica riga?"
  → PostgreSQL RLS + membership nel grafo OpenFGA
```

```sql
-- PostgreSQL Row-Level Security (RBAC/ReBAC a livello DB)
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Policy: un utente vede solo i propri ordini
-- (o tutti se ha il ruolo admin)
CREATE POLICY orders_isolation ON orders
  USING (
    owner_id = current_setting('app.current_user_id')::uuid
    OR
    current_setting('app.current_user_role') = 'admin'
  );

-- L'applicazione imposta il contesto prima di ogni query
SET LOCAL app.current_user_id = '123e4567-e89b-12d3-a456-426614174000';
SET LOCAL app.current_user_role = 'user';
```

---

## Multi-Tenancy — Isolamento degli Accessi

In sistemi SaaS multi-tenant, il tenant è un attributo fondamentale di ogni decisione:

```python
# Il tenant_id nel JWT è la chiave dell'isolamento
def authorize(user_jwt: dict, resource: dict, action: str) -> bool:
    # Regola base multi-tenant: MAI permettere cross-tenant access
    if user_jwt["tenant_id"] != resource["tenant_id"]:
        raise Forbidden("Cross-tenant access denied")

    # Poi applica le regole RBAC/ABAC normali
    return check_rbac(user_jwt["roles"], action) and \
           check_abac(user_jwt, resource, action)
```

**Errore critico da evitare**: il tenant isolation deve essere un controllo separato e non bypassabile, non una condizione della policy RBAC. Un bug nella policy RBAC non deve mai esporre dati di un altro tenant.

---

## Principio del Least Privilege

**Regola fondamentale**: ogni entità (utente, servizio, processo) deve avere esattamente i permessi necessari per svolgere il proprio compito — niente di più.

```
SBAGLIATO:
  Servizio di notifica email → ha accesso a payments:read, orders:*
  (se compromesso, può leggere tutti i pagamenti e modificare tutti gli ordini)

CORRETTO:
  Servizio di notifica email → ha accesso a notifications:send, users:email:read
  (se compromesso, può solo inviare notifiche)

SBAGLIATO:
  Database user dell'applicazione → SUPERUSER

CORRETTO:
  Database user dell'applicazione → SELECT/INSERT/UPDATE/DELETE sulle proprie tabelle
  Database user per migration → ALTER TABLE, CREATE TABLE (solo durante deploy)
  Database user per backup → CONNECT, SELECT su tutte le tabelle
```

---

## Best Practices

- **Immutabilità dei ruoli nel JWT**: i ruoli nel JWT sono snapshot al momento dell'emissione. Se un ruolo viene revocato, l'utente deve ri-autenticarsi per il nuovo JWT → lifetime breve del token
- **Separazione authorization server vs enforcement**: le policy devono essere centralizzate (OPA, OpenFGA), l'enforcement è distribuito nei servizi
- **Audit di ogni decisione di accesso**: ogni `allow` e `deny` deve essere loggato con soggetto, risorsa, azione, contesto
- **Testare le policy**: le policy ABAC/ReBAC sono codice — devono avere test unitari (OPA ha `opa test`, OpenFGA ha test suite)
- **Evitare policy condivise tra ambienti**: prod e staging devono avere policy isolate — un errore in staging non deve influenzare prod

## Riferimenti

- [NIST SP 800-162 — ABAC Guide](https://csrc.nist.gov/publications/detail/sp/800-162/final)
- [Google Zanzibar Paper](https://research.google/pubs/pub48190/)
- [OpenFGA Documentation](https://openfga.dev/docs)
- [SpiceDB — AuthZed](https://docs.authzed.com/)
- [OWASP — Broken Access Control](https://owasp.org/Top10/A01_2021-Broken_Access_Control/)
