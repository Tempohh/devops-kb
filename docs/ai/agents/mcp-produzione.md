---
title: "MCP in Produzione"
slug: mcp-produzione
category: ai
tags: [mcp, model-context-protocol, production, security, kubernetes, oauth, observability]
search_keywords: [MCP production, MCP produzione, deploy MCP server, Model Context Protocol deployment, Streamable HTTP, stdio transport, SSE legacy, Mcp-Session-Id, stateless MCP, OAuth 2.1 MCP, protected resource metadata, RFC 9728, RFC 8707, resource indicators, token passthrough, confused deputy, tool poisoning, rug pull, prompt injection tool result, MCP gateway, MCP registry, allowlist MCP server, human-in-the-loop, audit log tool call, MCP Kubernetes, NetworkPolicy MCP, nginx proxy_buffering, MCP OpenTelemetry, MCP rate limiting]
parent: ai/agents/_index
related: [ai/agents/claude-agent-sdk, ai/agents/agent-patterns, security/autenticazione/oauth2-oidc, security/secret-management/vault, containers/kubernetes/networking, networking/api-gateway/rate-limiting, monitoring/tools/otel-collector-kubernetes]
official_docs: https://modelcontextprotocol.io/specification
status: needs-review
difficulty: advanced
last_updated: 2026-10-02
---

# MCP in Produzione

## Panoramica

Il Model Context Protocol (MCP) espone **tool, resources e prompt** a un client LLM tramite un protocollo JSON-RPC 2.0. Il caso locale — un MCP server lanciato come sottoprocesso via **stdio** dal client (Claude Code, IDE) — è trattato in [Claude Agent SDK](claude-agent-sdk.md); funziona bene per un singolo sviluppatore ma non scala a un team: ogni macchina esegue codice arbitrario con le credenziali dell'utente, nessun controllo centrale, nessun audit.

In produzione l'MCP server diventa un **servizio di rete** come un altro: va autenticato, autorizzato, osservato, limitato in rate e isolato. La differenza rispetto a una normale API è che il chiamante è un LLM influenzabile da contenuto non fidato (tool description, risultati di tool, documenti letti): il threat model include quindi **prompt injection** e abusi di fiducia che una REST API classica non ha.

Questa guida copre: scelta del transport, autenticazione OAuth 2.1, threat model e mitigazioni, deploy su Kubernetes, gateway/registry centralizzato, troubleshooting. **Non** si usa un MCP server remoto quando: il tool è puramente locale (filesystem dello sviluppatore), non c'è un'esigenza di condivisione, o una semplice chiamata API diretta dall'agente è sufficiente.

## Concetti Chiave

!!! note "Ruoli MCP"
    **Host** = applicazione che ospita l'LLM (Claude Code, app custom). **Client** = connettore dentro l'host, uno per server. **Server** = processo che espone tool/resources. Nello schema di autorizzazione MCP il server è un **OAuth resource server**, mentre l'authorization server è un componente separato (Keycloak, Entra ID, Auth0...).

| Concetto | Significato in produzione |
|---|---|
| **stdio** | Server come child process, comunicazione su stdin/stdout. Un utente, una macchina. Nessuna auth di rete: eredita l'ambiente del client |
| **Streamable HTTP** | Transport HTTP standard (spec 2025-03-26, sostituisce il vecchio HTTP+SSE): un unico endpoint (`/mcp`) che accetta `POST` e opzionalmente `GET`; la risposta può essere JSON o stream SSE |
| **Sessione** | Header `Mcp-Session-Id` assegnato dal server in `initialize`; il client lo rimanda su ogni richiesta |
| **Stateless mode** | Server che non mantiene stato di sessione: ogni richiesta è indipendente, scalabile orizzontalmente senza sticky session |
| **Tool annotations** | Hint (`readOnlyHint`, `destructiveHint`, `idempotentHint`) sul tool; **non fidati** se il server non è fidato |
| **Protected Resource Metadata** | Documento RFC 9728 (`/.well-known/oauth-protected-resource`) con cui il server dichiara quale authorization server accetta |

### stdio vs Streamable HTTP

| Criterio | stdio | Streamable HTTP |
|---|---|---|
| Deploy | Binario/pacchetto locale | Servizio in container |
| Utenti | 1 | N (multi-tenant) |
| Autenticazione | Nessuna (env var del processo) | OAuth 2.1 / Bearer token |
| Scaling | N/A | Orizzontale (se stateless) |
| Audit centralizzato | No | Sì |
| Aggiornamento | Per macchina | Un deploy |
| Rischio principale | Supply chain del pacchetto, secret in chiaro nel `mcp.json` | Superficie di rete, token theft |

!!! warning "Il transport HTTP+SSE legacy è deprecato"
    Il vecchio transport con due endpoint (`GET /sse` + `POST /messages`) è sostituito da Streamable HTTP. Molti server e proxy esistenti lo usano ancora: verificare la versione del protocollo supportata dal client (`MCP-Protocol-Version` header) prima di scegliere.

## Architettura / Come Funziona

### Flusso di una chiamata remota

```
Client MCP                    MCP Server (resource server)         Authorization Server
    │  POST /mcp (no token)             │                                    │
    │──────────────────────────────────▶│                                    │
    │  401 + WWW-Authenticate:          │                                    │
    │  resource_metadata="…/oauth-protected-resource"                        │
    │◀──────────────────────────────────│                                    │
    │  GET /.well-known/oauth-protected-resource                             │
    │──────────────────────────────────▶│                                    │
    │  { "authorization_servers": ["https://idp.example.com"] }              │
    │◀──────────────────────────────────│                                    │
    │  OAuth 2.1 Authorization Code + PKCE, resource=https://mcp.example.com │
    │───────────────────────────────────────────────────────────────────────▶│
    │  access_token (aud = https://mcp.example.com)                          │
    │◀───────────────────────────────────────────────────────────────────────│
    │  POST /mcp  Authorization: Bearer …  (initialize)                      │
    │──────────────────────────────────▶│  valida firma, iss, aud, exp, scope│
    │  200 + Mcp-Session-Id: abc123     │                                    │
    │◀──────────────────────────────────│                                    │
    │  POST /mcp  Mcp-Session-Id: abc123 (tools/call)                        │
    │──────────────────────────────────▶│                                    │
```

### Sessioni e scaling dietro load balancer

Con sessioni stateful il server tiene in memoria lo stato della sessione (subscription, risultati parziali): una richiesta con `Mcp-Session-Id` deve tornare alla **stessa replica**. Opzioni:

1. **Stateless** (raccomandato quando possibile): nessun `Mcp-Session-Id`, ogni richiesta autosufficiente. Tutte le repliche sono equivalenti, nessuna sticky session. Perde server-initiated notification/sampling.
2. **Sticky session** sull'header `Mcp-Session-Id` (hash consistente nel load balancer).
3. **Stato esterno** (Redis) per la sessione: ogni replica può servire qualsiasi sessione.

!!! tip "Preferire stateless"
    La maggior parte dei tool DevOps (query, lettura, azioni puntuali) non ha bisogno di stato di sessione. Stateless + `readinessProbe` + HPA è il percorso più semplice e robusto.

## Configurazione & Pratica

### Server Streamable HTTP stateless (Python, SDK ufficiale)

```python
# server.py — MCP server remoto stateless con validazione token
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ops-tools", stateless_http=True, json_response=True)

@mcp.tool()
def get_deployment_status(namespace: str, name: str) -> str:
    """Restituisce lo stato di un Deployment Kubernetes (sola lettura)."""
    # Usa un ServiceAccount con RBAC minimo (get/list su deployments)
    ...

if __name__ == "__main__":
    # Ascolta su 0.0.0.0:8000, endpoint /mcp
    mcp.run(transport="streamable-http")
```

### Validazione del token (resource server)

Il server **deve** verificare che il token sia stato emesso *per lui* (`aud`) — mai accettare token generici.

```python
# auth.py — validazione JWT Bearer per MCP resource server
import jwt  # PyJWT
from jwt import PyJWKClient

ISSUER = "https://idp.example.com/realms/platform"
AUDIENCE = "https://mcp.example.com"          # canonical URI del server
REQUIRED_SCOPE = "mcp:tools:read"
jwks = PyJWKClient(f"{ISSUER}/protocol/openid-connect/certs", cache_keys=True)

def validate(token: str) -> dict:
    key = jwks.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token, key,
        algorithms=["RS256", "ES256"],   # allowlist esplicita, mai "none"
        audience=AUDIENCE,               # rifiuta token emessi per altri servizi
        issuer=ISSUER,
        options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        leeway=30,
    )
    if REQUIRED_SCOPE not in claims.get("scope", "").split():
        raise PermissionError("insufficient_scope")
    return claims
```

La risposta di errore deve usare gli header standard così il client sa come procedere:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"

HTTP/1.1 403 Forbidden
WWW-Authenticate: Bearer error="insufficient_scope", scope="mcp:tools:write"
```

Documento di metadata:

```json
{
  "resource": "https://mcp.example.com",
  "authorization_servers": ["https://idp.example.com/realms/platform"],
  "scopes_supported": ["mcp:tools:read", "mcp:tools:write"],
  "bearer_methods_supported": ["header"]
}
```

!!! warning "Token passthrough: anti-pattern vietato dalla spec"
    Il server MCP **non deve** inoltrare il token ricevuto dal client a un'API downstream. Quel token ha `aud` = MCP server; riusarlo bypassa i controlli del downstream, rompe l'audit (chi ha chiamato?) ed è un vettore di **confused deputy**. Per chiamare API a valle usare credenziali proprie del server (client credentials, workload identity) oppure **token exchange** (RFC 8693) che produce un nuovo token con `aud` corretto e identità dell'utente.

### Gestione secret

I secret di backend (token API, password DB) vivono **nel server**, mai nel client né nel `mcp.json`. Vedi [Vault](../security/secret-management/vault.md).

```yaml
# ExternalSecret / Vault Agent: il Pod riceve i secret come file, non come env var committate
apiVersion: v1
kind: Pod
metadata:
  name: mcp-ops
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "mcp-ops"
    vault.hashicorp.com/agent-inject-secret-backend: "kv/data/mcp/ops"
```

### Deployment Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-ops
  namespace: mcp
spec:
  replicas: 3
  selector:
    matchLabels: {app: mcp-ops}
  template:
    metadata:
      labels: {app: mcp-ops}
    spec:
      serviceAccountName: mcp-ops        # RBAC minimo, solo get/list necessari
      automountServiceAccountToken: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: server
          image: registry.example.com/mcp/ops@sha256:<digest>   # pin per digest
          ports: [{containerPort: 8000}]
          env:
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: http://otel-collector.observability:4317
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: ["ALL"]}
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {memory: 256Mi}
          readinessProbe:
            tcpSocket: {port: 8000}
            periodSeconds: 5
          livenessProbe:
            tcpSocket: {port: 8000}
            initialDelaySeconds: 10
---
apiVersion: v1
kind: Service
metadata: {name: mcp-ops, namespace: mcp}
spec:
  selector: {app: mcp-ops}
  ports: [{port: 80, targetPort: 8000}]
```

NetworkPolicy: ingresso solo dall'ingress controller, egress solo verso ciò che serve (default-deny). Approfondimento: [Kubernetes Networking](../../containers/kubernetes/networking.md).

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: mcp-ops, namespace: mcp}
spec:
  podSelector: {matchLabels: {app: mcp-ops}}
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels: {kubernetes.io/metadata.name: ingress-nginx}
      ports: [{port: 8000}]
  egress:
    - to:   # DNS
        - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}
      ports: [{port: 53, protocol: UDP}]
    - to:   # solo API interna necessaria
        - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: observability}}
      ports: [{port: 4317}]
    - to:   # IdP per fetch JWKS
        - ipBlock: {cidr: 10.20.0.0/24}
      ports: [{port: 443}]
```

### Ingress con streaming corretto (nginx)

Le risposte SSE/streaming si rompono se il proxy bufferizza o chiude connessioni idle.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-ops
  namespace: mcp
  annotations:
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
    nginx.ingress.kubernetes.io/limit-rps: "20"
spec:
  ingressClassName: nginx
  tls: [{hosts: [mcp.example.com], secretName: mcp-tls}]
  rules:
    - host: mcp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: {service: {name: mcp-ops, port: {number: 80}}}
```

Equivalente su nginx puro:

```nginx
location /mcp {
    proxy_pass http://mcp_backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;          # SSE: niente buffering
    proxy_cache off;
    proxy_read_timeout 3600s;
    chunked_transfer_encoding on;
    add_header X-Accel-Buffering no;
}
```

### Audit log strutturato e osservabilità

Ogni `tools/call` va loggata con identità, tool, hash degli argomenti, esito e durata. Non loggare argomenti/risultati in chiaro se possono contenere dati sensibili.

```python
import hashlib, json, logging, time
from opentelemetry import trace

log = logging.getLogger("mcp.audit")
tracer = trace.get_tracer("mcp-ops")

def audited(tool_name, claims, args, fn):
    start = time.monotonic()
    with tracer.start_as_current_span(f"mcp.tool/{tool_name}") as span:
        span.set_attribute("mcp.tool", tool_name)
        span.set_attribute("enduser.id", claims["sub"])
        outcome = "ok"
        try:
            return fn(**args)
        except Exception:
            outcome = "error"
            raise
        finally:
            log.info(json.dumps({
                "event": "tool_call", "tool": tool_name, "sub": claims["sub"],
                "client_id": claims.get("azp"), "outcome": outcome,
                "args_sha256": hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest(),
                "duration_ms": round((time.monotonic() - start) * 1000),
                "trace_id": format(span.get_span_context().trace_id, "032x"),
            }))
```

Metriche minime: richieste/s per tool, latenza p95, errori 401/403/5xx, tool call rifiutati da policy. Pipeline di raccolta: [OTel Collector su Kubernetes](../../monitoring/tools/otel-collector-kubernetes.md).

## Threat Model e Mitigazioni

| Minaccia | Descrizione | Mitigazione |
|---|---|---|
| **Tool poisoning** | Istruzioni malevole nascoste nella `description` di un tool (invisibili all'utente, lette dal modello) che inducono es. a leggere `~/.ssh` | Review delle description prima dell'approvazione; mostrare la description completa all'utente; solo server da registry approvato |
| **Rug pull** | Server fidato che dopo l'approvazione cambia description/comportamento dei tool | Pin per versione/digest; hash della tool list e alert su cambiamento (`notifications/tools/list_changed` → ri-approvazione) |
| **Prompt injection via tool result** | Contenuto restituito dal tool (pagina web, ticket, commit message) contiene istruzioni che il modello esegue | Trattare ogni risultato come dato non fidato; separare tool "lettura di contenuto esterno" da tool "azioni con effetti"; limitare i tool disponibili nella stessa sessione (lethal trifecta: dati privati + contenuto non fidato + canale di uscita) |
| **Confused deputy** | Il server agisce con privilegi propri su richiesta di un utente che non li avrebbe | Autorizzare per utente (claim `sub`/gruppi) ad ogni call; niente token passthrough; token exchange |
| **Tool shadowing** | Un server malevolo dichiara un tool con lo stesso nome/description che altera l'uso di un altro server | Namespacing dei tool per server; un client per server; gateway che rinomina con prefisso |
| **Over-privileged tool** | Un tool `run_shell` o `kubectl` generico | Tool granulari a scopo ristretto, RBAC minimo del ServiceAccount, scope OAuth per tool |
| **DNS rebinding / origin spoofing** | Pagina web che raggiunge un server locale | Validare l'header `Origin`, bind su `127.0.0.1` per server locali, autenticazione sempre |
| **Session hijacking** | `Mcp-Session-Id` rubato e riusato | Session ID non deterministici (UUID casuale); associare la sessione all'identità autenticata; le sessioni non sostituiscono l'auth |

!!! warning "Human-in-the-loop sui tool distruttivi"
    I tool con effetti irreversibili (delete, apply, send, deploy) richiedono **approvazione esplicita** dell'utente a ogni invocazione. Non affidarsi a `destructiveHint` dichiarato dal server: la classificazione va mantenuta dal lato client/gateway.

Esempio di policy client-side in Claude Code (allowlist esplicita, deny per default sul resto):

```json
{
  "permissions": {
    "allow": ["mcp__ops__get_deployment_status", "mcp__ops__list_pods"],
    "ask":   ["mcp__ops__rollout_restart"],
    "deny":  ["mcp__ops__delete_namespace"]
  },
  "enabledMcpjsonServers": ["ops"]
}
```

## Gateway e Registry Centralizzato

Per un team, invece di far configurare a ogni sviluppatore N server, si introduce un **MCP gateway** (reverse proxy MCP-aware) davanti ai server approvati:

```
 Claude Code / agenti ──▶ MCP Gateway ──┬─▶ mcp-ops      (K8s read)
   (1 URL, 1 login SSO)   │ authN SSO   ├─▶ mcp-docs     (wiki)
                          │ authZ per   └─▶ mcp-tickets  (Jira)
                          │ gruppo/tool
                          │ rate limit, audit, redaction
```

Responsabilità del gateway:

- **Autenticazione unica** (SSO/OIDC) e token exchange verso i backend.
- **Autorizzazione per tool** in base a gruppo IdP (es. `team-sre` può chiamare `rollout_restart`).
- **Registry/governance**: elenco dei server approvati con owner, versione (digest), review della description, data ultima verifica; processo di onboarding con review di sicurezza.
- **Rate limiting** per utente/tool ([Rate Limiting](../../networking/api-gateway/rate-limiting.md)), **audit log** centralizzato, **redaction** di secret nei risultati.
- **Rilevamento rug pull**: hash della tool list confrontato ad ogni connessione.

```yaml
# Esempio di registry (concettuale) — server approvati
servers:
  - name: ops
    url: https://mcp-ops.mcp.svc/mcp
    owner: team-platform
    image_digest: sha256:3f1c…
    tools_hash: sha256:9ab2…        # alert se cambia
    allowed_groups: [team-sre, team-platform]
    destructive_tools: [rollout_restart]   # richiedono approvazione
    reviewed_at: 2026-09-25
```

## Best Practices

- **Stateless HTTP** dove possibile; TLS ovunque; mai esporre un MCP server senza autenticazione, anche "interno".
- **OAuth 2.1 + PKCE**, token di breve durata, `aud` verificato, **scope minimi** per tool, `resource` indicator (RFC 8707) nelle richieste di token.
- **Zero token passthrough**; credenziali downstream proprie o token exchange.
- **Tool piccoli e specifici** con schema di input rigoroso (JSON Schema con enum, pattern, maxLength); validare lato server, mai fidarsi dell'output del modello.
- **Container hardening**: non-root, read-only FS, drop capabilities, immagine pinned per digest, SBOM e firma (vedi supply chain).
- **Default-deny di rete** con NetworkPolicy; egress limitato.
- **Audit e tracing** di ogni tool call con identità utente; alert su picchi di 403 e su cambio della tool list.
- **Allowlist dei server** lato client; nessun server MCP community installato senza review del codice e pin della versione.
- **Separare tool di lettura da tool di azione** e limitare le combinazioni nella stessa sessione.

!!! tip "Pattern anti-trifecta"
    Se un agente ha accesso a dati privati *e* legge contenuto non fidato *e* può comunicare verso l'esterno, un'iniezione può esfiltrare i dati. Rompere almeno una delle tre condizioni (es. niente egress libero, oppure agente separato per contenuto esterno).

## Troubleshooting

### Stream SSE si interrompe o arriva tutto alla fine
- **Sintomo**: il client resta in attesa, notifiche di progresso arrivano a blocchi o mai; `tools/call` lunghi vanno in timeout.
- **Causa**: il proxy (nginx, ALB, CDN) bufferizza la risposta o chiude la connessione idle (default `proxy_read_timeout 60s`).
- **Soluzione**: `proxy_buffering off`, `proxy_http_version 1.1`, `Connection ""`, timeout elevati (vedi sezione Ingress). Verifica: `curl -N -H "Accept: text/event-stream" -H "Authorization: Bearer $T" https://mcp.example.com/mcp`. Su AWS ALB alzare `idle_timeout`.

### `404 Session not found` / sessione persa dopo scale-out
- **Sintomo**: dopo il `initialize` le chiamate successive danno 404 o `Bad Request: No valid session ID`.
- **Causa**: la richiesta è finita su una replica diversa da quella che ha creato la sessione.
- **Soluzione**: passare a stateless (`stateless_http=True`), oppure sticky session sull'header `Mcp-Session-Id`, oppure stato di sessione su Redis. Controllo: `kubectl logs -l app=mcp-ops --prefix | grep session`.

### 401 ripetuti dopo il refresh del token
- **Sintomo**: dopo ~1 h (scadenza access token) il client riceve 401 anche se il refresh sembra riuscire.
- **Causa**: (a) il refresh token non è stato emesso (manca scope `offline_access`) o è ruotato e il client riusa quello vecchio; (b) il nuovo token ha `aud` diverso perché manca `resource=` nella richiesta di refresh; (c) clock skew tra IdP e server.
- **Soluzione**: verificare il payload (`echo $T | cut -d. -f2 | base64 -d | jq '{aud,iss,exp,scope}'`), includere `resource` nel token request, aggiungere `leeway=30` alla validazione, sincronizzare NTP. Dopo un 401 il client deve rieseguire la discovery da `WWW-Authenticate`.

### `403 insufficient_scope` su un tool
- **Sintomo**: `tools/list` funziona ma `tools/call` fallisce con 403.
- **Causa**: il token ha solo scope di lettura.
- **Soluzione**: rispondere con `WWW-Authenticate: Bearer error="insufficient_scope", scope="…"` per consentire al client la step-up authorization; assegnare lo scope al ruolo corretto nell'IdP.

### Il server non è raggiungibile dal Pod / timeout sul JWKS
- **Sintomo**: `PyJWKClientError: Fail to fetch data from the url`, 500 su ogni richiesta autenticata.
- **Causa**: NetworkPolicy di egress troppo restrittiva verso l'IdP, o DNS non permesso.
- **Soluzione**: aggiungere regola egress verso l'IdP (443) e DNS (53/UDP+TCP); test: `kubectl exec -n mcp deploy/mcp-ops -- python -c "import urllib.request as u;print(u.urlopen('https://idp.example.com/.well-known/openid-configuration').status)"`.

### Tool list cambiata inaspettatamente (sospetto rug pull)
- **Sintomo**: alert sull'hash della tool list, o il modello inizia a usare tool in modo anomalo.
- **Causa**: nuova versione del server con description modificate (legittima o malevola).
- **Soluzione**: bloccare il server nel gateway, confrontare le description (`tools/list` → diff), verificare digest dell'immagine e changelog, ri-approvare con review prima di riabilitare.

## Relazioni

??? info "Claude Agent SDK — MCP locale (stdio)"
    Configurazione di server MCP stdio in Claude Code (`mcp.json`, `claude mcp add`). Questa guida estende il caso al deploy remoto multi-utente.

    **Approfondimento completo →** [Claude Agent SDK](claude-agent-sdk.md)

??? info "OAuth 2.0 e OIDC"
    Authorization Code + PKCE, discovery, JWT validation sono la base dell'autenticazione MCP remota.

    **Approfondimento completo →** [OAuth2 / OIDC](../../security/autenticazione/oauth2-oidc.md)

??? info "Vault — secret management"
    Iniezione dei secret di backend nei Pod del server MCP.

    **Approfondimento completo →** [Vault](../../security/secret-management/vault.md)

??? info "Agent Patterns"
    Pattern di agenti, human-in-the-loop e guardrail che determinano quali tool esporre.

    **Approfondimento completo →** [Agent Patterns](agent-patterns.md)

## Riferimenti

- [MCP Specification — Transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [MCP Specification — Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
- RFC 9728 — OAuth 2.0 Protected Resource Metadata; RFC 8707 — Resource Indicators; RFC 8693 — Token Exchange
- [OWASP — Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/)
