---
title: "OPA — Open Policy Agent"
slug: opa
category: security
tags: [opa, open-policy-agent, rego, policy-as-code, autorizzazione, kubernetes-admission]
search_keywords: [open policy agent opa, rego language, policy as code, opa kubernetes admission webhook, opa gatekeeper, conftest opa, opa bundle server, opa partial evaluation, opa envoy filter, opa middleware, rego rules, rego functions, opa data input, opa decision log, opa benchmark, opa testing, rego playground, opa sidecar, opa rest api, opa integration microservices, opa terraform, opa ci cd validation, opa external data, opa jwt validation]
parent: security/autorizzazione/_index
related: [security/autorizzazione/rbac-abac-rebac, security/supply-chain/admission-control, networking/kubernetes/network-policies]
official_docs: https://www.openpolicyagent.org/docs/latest/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# OPA — Open Policy Agent

## Panoramica

**OPA (Open Policy Agent)** è un motore di policy general-purpose che separa la logica di autorizzazione dal codice applicativo. Invece di hardcodare le regole di accesso nel servizio, le policy sono scritte in **Rego** (un linguaggio dichiarativo) e evaluate da OPA — che può essere un sidecar, un deployment separato, o una libreria embedded.

**Il principio fondamentale**: la "domanda di autorizzazione" segue sempre la stessa struttura — OPA valuta una policy con il contesto come input e produce una decisione strutturata come output.

```
Microservizio A              OPA
      │                       │
      │── POST /v1/data/authz/allow ──►│
      │   {                            │
      │     "input": {                 │ Valuta la policy
      │       "user": {...},           │ con questi input
      │       "action": "orders:write",│
      │       "resource": {...},       │
      │       "token": "eyJ..."        │
      │     }                          │
      │   }                            │
      │◄─────────────────────────────  │
      │   { "result": true }           │  oppure
      │   { "result": {"allow": false, │
      │     "reason": "..."} }         │
```

**Dove OPA viene usato in un'architettura enterprise:**
- **API Gateway / Envoy filter**: autorizzazione HTTP centralizzata
- **Kubernetes admission webhook** (OPA Gatekeeper): validazione dei manifest
- **Terraform / CI/CD**: validazione della configurazione infrastrutturale
- **Microservizi embedded**: logica di autorizzazione fine-grained

---

## Rego — Il Linguaggio di Policy

Rego è un linguaggio **dichiarativo** (come Prolog o Datalog): si definisce **cosa** è vero, non **come** calcolarlo. OPA valuta le regole e determina i risultati.

### Concetti Fondamentali

```rego
# Ogni file Rego appartiene a un package
package myapp.authz

# Import librerie standard
import future.keywords.if
import future.keywords.in

# Data/Input sono sempre disponibili come oggetti globali
# input = la richiesta inviata a OPA (strutturata dall'applicazione)
# data  = dati caricati in OPA (ruoli, policies, etc.)

# ─── Regola base: default e override ─────────────────────────────────
# La regola "default" si applica quando nessuna altra regola matcha
default allow = false

# Regola che sovrascrive il default
# Sintassi: "allow = true if <condizioni>"
allow if {
    # Ogni riga è una condizione (AND implicito)
    input.user.department == "engineering"
    input.action in {"read", "write"}
    not input.resource.classification == "top-secret"
}

allow if {
    # Regola alternativa (OR implicito tra regole con stesso nome)
    "admin" in input.user.roles
}

# ─── Regola con valore strutturato ────────────────────────────────────
decision := {
    "allow": allow,
    "reason": reason,
}

reason := "Admin ha accesso completo" if {
    "admin" in input.user.roles
}
reason := "Engineering può leggere/scrivere risorse non classificate" if {
    not "admin" in input.user.roles
    allow
}
reason := "Accesso negato: permessi insufficienti" if {
    not allow
}
```

### Comprensioni e Operazioni su Collezioni

```rego
package orders.authz

# Set comprehension: ruoli dell'utente dal JWT validato
user_roles := {role | role := input.token.roles[_]}

# Object comprehension: mappa permessi → bool
user_permissions := {
    perm: granted |
    some perm
    granted := perm in data.roles_permissions[user_roles[_]]
}

# Array comprehension: ordini dell'utente filtrati per stato
open_orders := [order |
    order := data.orders[_]
    order.owner_id == input.user.id
    order.status in {"pending", "processing"}
]

# Operazioni di aggregazione
order_count := count(open_orders)
total_value := sum([order.amount | order := open_orders[_]])
```

### Funzioni Helper

```rego
package jwt.verify

import future.keywords.if

# Funzione: verifica e decodifica il JWT
verify_and_decode(token) := payload if {
    # Verifica la firma con la chiave pubblica in data
    [_, payload, _] := io.jwt.decode_verify(token, {
        "cert": data.config.jwt_public_key,
        "iss":  data.config.jwt_issuer,
        "aud":  data.config.jwt_audience,
    })
}

# Funzione: controlla se un claim è presente e non scaduto
is_valid_token(token) if {
    payload := verify_and_decode(token)
    payload.exp > time.now_ns() / 1000000000
    payload.iss == data.config.jwt_issuer
}

# Funzione ricorsiva (Rego supporta ricorsione limitata)
# Controlla se un utente è membro di un gruppo (con transitività)
is_member(user, group) if {
    data.memberships[group][_] == user
}

is_member(user, group) if {
    intermediate := data.memberships[group][_]
    is_member(user, intermediate)  # Ricorsione: cerca nelle sotto-appartenenze
}
```

---

## Architettura di Deployment

### OPA come Sidecar

Il pattern più comune nei microservizi: OPA gira come container sidecar nello stesso pod del servizio:

```yaml
# deployment.yaml
spec:
  containers:
  - name: my-service
    image: my-service:1.0
    env:
    - name: OPA_ENDPOINT
      value: "http://localhost:8181"

  - name: opa
    image: openpolicyagent/opa:0.60.0-rootless
    args:
    - "run"
    - "--server"
    - "--addr=0.0.0.0:8181"
    - "--log-format=json"
    - "--log-level=info"
    - "--bundle"
    - "https://bundle-server.example.com/bundles/myservice"   # Bundle remoto
    ports:
    - containerPort: 8181
    readinessProbe:
      httpGet:
        path: /health?bundle=true    # Pronto solo quando il bundle è caricato
        port: 8181
    resources:
      requests:
        memory: "64Mi"
        cpu: "50m"
      limits:
        memory: "256Mi"
        cpu: "500m"
    securityContext:
      runAsNonRoot: true
      runAsUser: 65532
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
```

### Bundle Server — Distribuzione delle Policy

Le policy vengono distribuite come **bundle** — archivi .tar.gz che OPA scarica e aggiorna periodicamente:

```bash
# Struttura del bundle
my-bundle/
  ├── .manifest           # Metadata del bundle
  ├── orders/
  │   └── authz.rego      # Policy ordini
  ├── payments/
  │   └── authz.rego      # Policy pagamenti
  └── data.json           # Dati statici (ruoli, configurazione)

# .manifest
{
  "revision": "v1.2.3",
  "roots": ["orders", "payments"]
}

# Build del bundle
opa build -b my-bundle/ -o bundle.tar.gz

# Serve con nginx (OPA fa polling automatico)
# OPA scarica ogni bundle-reload-interval (default: aggiornamenti automatici via ETag)
```

```bash
# OPA con bundle da S3
opa run \
  --server \
  --bundle "s3://my-policy-bucket/bundles/production/bundle.tar.gz?region=us-east-1"
```

---

## Integrazione nei Microservizi

```python
# Python — middleware FastAPI con OPA
import httpx
from fastapi import Request, HTTPException

OPA_URL = "http://localhost:8181/v1/data/myapp/authz/decision"

async def opa_authorize(request: Request, action: str, resource: dict):
    # Estrai il JWT dalla richiesta
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")

    # Costruisci l'input per OPA
    opa_input = {
        "input": {
            "token": token,
            "user": request.state.user,      # utente estratto dal JWT validato
            "action": action,
            "resource": resource,
            "request": {
                "method": request.method,
                "path": str(request.url.path),
                "ip": request.client.host,
            }
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(OPA_URL, json=opa_input, timeout=0.1)  # 100ms timeout
        response.raise_for_status()

    decision = response.json()["result"]

    if not decision.get("allow"):
        raise HTTPException(
            status_code=403,
            detail={"reason": decision.get("reason", "Accesso negato")}
        )

    return decision

# Usage nei route handler
@app.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    order = await db.get_order(order_id)
    await opa_authorize(request, "orders:read", {
        "id": order_id,
        "owner_id": order["owner_id"],
        "status": order["status"],
        "tenant_id": order["tenant_id"]
    })
    return order
```

### OPA come Envoy External Authz Filter

OPA integra nativamente con Envoy via gRPC per autorizzare ogni richiesta HTTP a livello di proxy, senza modificare il codice dei servizi:

```yaml
# OPA configurato per Envoy gRPC
apiVersion: v1
kind: ConfigMap
metadata:
  name: opa-envoy-config
data:
  config.yaml: |
    plugins:
      envoy_ext_authz_grpc:
        addr: 0.0.0.0:9191
        path: myapp/authz/allow    # Path della regola Rego
        enable-reflection: true
    decision_logs:
      console: true
```

```yaml
# Envoy HttpFilter
http_filters:
- name: envoy.ext_authz
  typed_config:
    "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
    grpc_service:
      envoy_grpc:
        cluster_name: opa-ext-authz
    failure_mode_allow: false    # false = fail closed (nega se OPA non risponde)
    with_request_body:
      max_request_bytes: 8192
      allow_partial_message: true
```

---

## Testing delle Policy

```rego
# orders_test.rego — test suite per le policy degli ordini
package orders.authz_test

import data.orders.authz.allow

# Test: owner può leggere il proprio ordine
test_owner_can_read if {
    allow with input as {
        "user": {"id": "user-1", "roles": ["user"], "department": "engineering"},
        "action": "orders:read",
        "resource": {"id": "order-1", "owner_id": "user-1", "status": "pending"}
    }
}

# Test: utente non-owner NON può leggere l'ordine di un altro
test_non_owner_cannot_read if {
    not allow with input as {
        "user": {"id": "user-2", "roles": ["user"]},
        "action": "orders:read",
        "resource": {"id": "order-1", "owner_id": "user-1", "status": "pending"}
    }
}

# Test: admin può fare tutto
test_admin_can_delete if {
    allow with input as {
        "user": {"id": "admin-1", "roles": ["admin"]},
        "action": "orders:delete",
        "resource": {"id": "order-1", "owner_id": "user-1", "status": "completed"}
    }
}

# Test: nessuno può modificare un ordine completato (anche il proprietario)
test_owner_cannot_write_completed_order if {
    not allow with input as {
        "user": {"id": "user-1", "roles": ["user"]},
        "action": "orders:write",
        "resource": {"id": "order-1", "owner_id": "user-1", "status": "completed"}
    }
}
```

```bash
# Esegui i test
opa test ./policies/ -v

# Output
data.orders.authz_test.test_owner_can_read: PASS (1.2ms)
data.orders.authz_test.test_non_owner_cannot_read: PASS (0.8ms)
data.orders.authz_test.test_admin_can_delete: PASS (0.9ms)
data.orders.authz_test.test_owner_cannot_write_completed_order: PASS (1.1ms)

4 tests, 0 failures

# Coverage report
opa test --coverage ./policies/ | opa eval --format pretty -I -d - data.coverage
```

---

## OPA per Validazione Infrastruttura (Conftest)

OPA non è solo per i microservizi — è usato per validare configurazioni Kubernetes, Terraform, Dockerfile, GitHub Actions:

```rego
# deny-privileged-containers.rego (Conftest — CI/CD)
package main

deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    container.securityContext.privileged == true
    msg := sprintf("Container '%v' non può girare come privileged", [container.name])
}

deny[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.resources.limits
    msg := sprintf("Container '%v' deve avere resource limits definiti", [container.name])
}

warn[msg] {
    input.kind == "Deployment"
    container := input.spec.template.spec.containers[_]
    not container.readinessProbe
    msg := sprintf("Container '%v' non ha readinessProbe — considerare di aggiungerla", [container.name])
}
```

```yaml
# .github/workflows/security-check.yml
- name: Validate Kubernetes manifests with Conftest
  run: |
    conftest test k8s/ \
      --policy policies/kubernetes/ \
      --fail-on-warn \
      --output github
```

---

## Decision Log — Audit Trail

```yaml
# OPA con decision logging su stdout (raccogliere con Fluentbit/Loki)
decision_logs:
  console: true
  # oppure plugin per S3, Elastic, ecc.

# Ogni decisione produce un log strutturato:
{
  "decision_id": "8f4e9c2a-...",
  "input": {
    "user": {"id": "user-123"},
    "action": "orders:write",
    "resource": {"id": "order-456", "status": "draft"}
  },
  "result": {"allow": true, "reason": "Owner può modificare ordini in draft"},
  "path": "myapp/authz/decision",
  "timestamp": "2024-01-15T14:32:01Z",
  "metrics": {
    "timer_rego_query_eval_ns": 45000    // 45 microseconds
  }
}
```

---

## Best Practices

- **Policy come codice nel repository**: le policy Rego vivono nel repo del servizio (o in un repo dedicato per policy condivise) — PR review, versioning, CI/CD come per qualsiasi codice
- **Test coverage obbligatoria**: ogni regola deve avere test. Le policy senza test sono bombe a orologeria — un cambiamento innocente può aprire o chiudere accessi inaspettati
- **Fail closed (`failure_mode_allow: false`)**: se OPA non è raggiungibile → nega l'accesso, non permetterlo. Il fail-open è un rischio di sicurezza
- **Performance**: OPA tipicamente risponde in 0.1-1ms per policy semplici. Per regole complesse con large data sets, usa partial evaluation o pre-computing dei risultati
- **Separare data dalla policy**: le policy descrivono la logica, i dati (ruoli, configurazioni) vengono caricati separatamente — questo permette di aggiornare la configurazione senza cambiare la policy

## Riferimenti

- [OPA Documentation](https://www.openpolicyagent.org/docs/latest/)
- [Rego Playground](https://play.openpolicyagent.org/)
- [Conftest](https://www.conftest.dev/)
- [OPA Ecosystem — Integrations](https://www.openpolicyagent.org/ecosystem/)
- [The Rego Reference](https://www.openpolicyagent.org/docs/latest/policy-reference/)
