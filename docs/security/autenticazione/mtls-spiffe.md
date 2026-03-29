---
title: "mTLS e SPIFFE/SPIRE — Identità dei Workload"
slug: mtls-spiffe
category: security
tags: [mtls, mutual-tls, spiffe, spire, workload-identity, service-mesh, certificati-x509]
search_keywords: [mutual tls, mtls service mesh, spiffe standard, spire identity, workload identity, svid x509, trust domain spiffe, service to service authentication, istio mtls, envoy mtls, certificate rotation automatic, workload attestation, node attestation, x509 svid, jwt svid, spire server agent, spire workload api, zero trust service mesh, kubernetes pod identity, oidc federation spiffe, short lived certificates, pki workload, mtls vs api key, mtls cloud, aws iam roles anywhere]
parent: security/autenticazione/_index
related: [security/pki-certificati/pki-interna, security/pki-certificati/cert-manager, networking/sicurezza/zero-trust, security/autenticazione/oauth2-oidc]
official_docs: https://spiffe.io/docs/latest/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# mTLS e SPIFFE/SPIRE — Identità dei Workload

## Panoramica

In TLS standard (HTTPS), **solo il server si autentica** al client tramite il suo certificato. Il client può verificare di star parlando con `api.example.com`, ma il server non sa chi è il client.

**mTLS (Mutual TLS)** aggiunge l'autenticazione reciproca: anche il client presenta un certificato X.509, e il server lo verifica. In un'architettura a microservizi, questo significa che ogni servizio conosce crittograficamente l'identità dell'altro **prima ancora che passi un singolo byte di applicazione**.

**Il problema che mTLS risolve a livello di microservizi**: le API Key e i client secret sono credenziali statiche che devono essere distribuite, ruotate e protette manualmente — a centinaia di servizi. Con mTLS ogni workload riceve un certificato di identità a breve durata; la rotazione è automatica; nessun segreto condiviso da distribuire.

!!! tip "mTLS vs OAuth 2.0 client credentials"
    Questi non sono mutualmente esclusivi:
    - **mTLS**: autentica il canale di comunicazione e il workload (layer di trasporto)
    - **OAuth 2.0 client credentials**: autorizza le operazioni (layer applicativo)
    In sistemi enterprise maturi entrambi coesistono: mTLS per la comunicazione sicura, JWT per l'autorizzazione delle operazioni.

---

## Handshake mTLS

```
Microservizio A (Client)              Microservizio B (Server)
        │                                      │
        │──── ClientHello ─────────────────────►│
        │◄─── ServerHello + Certificate_B ──────│
        │     (cert B: CN=service-b, CA=interno)│
        │ Verifica cert B:                      │
        │   - CA è nella propria trust store?   │
        │   - È scaduto?                        │
        │   - SPIFFE ID corrisponde?            │
        │──── Certificate_A ────────────────────►│
        │     (cert A: CN=service-a)            │ Verifica cert A:
        │                                       │   - CA è nella trust store?
        │──── CertificateVerify + Finished ─────►│   - Workload autorizzato?
        │◄─── Finished ──────────────────────────│
        │                                       │
        │══ Canale cifrato + autenticato ═══════│
        │   Entrambi i lati hanno verificato    │
        │   l'identità dell'altro               │
```

---

## SPIFFE — Lo Standard per l'Identità dei Workload

**SPIFFE (Secure Production Identity Framework For Everyone)** è uno standard CNCF che definisce come assegnare identità verificabili ai workload in ambienti dinamici (container, serverless, VM effimere).

Il problema che SPIFFE risolve: in Kubernetes, un pod può essere rischedulato su qualsiasi nodo, con un IP diverso, in qualsiasi momento. L'identità non può essere basata sull'IP. SPIFFE assegna identità basate su **chi è il workload** (namespace, service account, nome del servizio) indipendentemente da dove gira.

### SPIFFE ID

L'identità SPIFFE è uno **URI** nel formato:

```
spiffe://trust-domain/path/identificatore

Esempi:
  spiffe://example.com/ns/production/sa/orders-service
  spiffe://example.com/ns/staging/sa/payment-service
  spiffe://on-prem.corp/datacenter/rome/service/auth

trust-domain = il dominio di fiducia dell'organizzazione (può essere multi-domain per federation)
path         = identifica univocamente il workload all'interno del trust domain
```

### SVID — SPIFFE Verifiable Identity Document

Un SVID è il documento crittografico che prova l'identità SPIFFE. Esistono due forme:

```
X.509 SVID (forma principale):
  Certificato X.509 standard con:
    Subject Alternative Name (SAN) = URI type = spiffe://...
    Issuer = CA intermedia del SPIRE cluster
    NotAfter = breve durata (tipicamente 1 ora)

  Vantaggi:
    - Usato direttamente come client certificate in mTLS
    - Supportato natively da Envoy, Istio, qualsiasi implementazione TLS
    - Revoca per scadenza — nessuna CRL/OCSP necessaria (lifetime breve)

JWT SVID (forma alternativa):
  JWT firmato con claims SPIFFE standard
    sub = spiffe://trust-domain/workload
    aud = resource identifier
    exp = scadenza breve

  Uso: quando il canale TLS non è disponibile o per integrazione con sistemi OAuth
```

---

## SPIRE — Implementazione di SPIFFE

**SPIRE (SPIFFE Runtime Environment)** è l'implementazione di riferimento SPIFFE. Si compone di due componenti:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        SPIRE Server                                  │
│                     (per cluster o datacenter)                       │
│                                                                      │
│   CA Root privata ──> CA intermedia ──> firma SVID richiesti        │
│   Entry Registry  ──> mappa workload → SPIFFE IDs                   │
│   Node Attestors  ──> verifica identità dei nodi fisici             │
│   Datastore       ──> PostgreSQL/SQLite per entries                 │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ SPIRE Server API (mTLS)
         ┌─────────────┼──────────────┐
         │             │              │
    ┌────▼───┐    ┌────▼───┐    ┌────▼───┐
    │ SPIRE  │    │ SPIRE  │    │ SPIRE  │
    │ Agent  │    │ Agent  │    │ Agent  │
    │ Node 1 │    │ Node 2 │    │ Node 3 │
    └────┬───┘    └────┬───┘    └────┬───┘
         │             │              │
    ┌────▼───┐    ┌────▼───┐    ┌────▼───┐
    │ Pod A  │    │ Pod B  │    │ Pod C  │
    │ Pod D  │    │ Pod E  │    │ Pod F  │
    └────────┘    └────────┘    └────────┘

SPIRE Agent:
  - Gira su ogni nodo come DaemonSet
  - Espone la Workload API via Unix socket (/tmp/spire-agent/public/api.sock)
  - Autentica i workload tramite kernel-level attestation (UID, namespace, pod SA)
  - Consegna SVID ai workload in modo sicuro
```

### Node Attestation

Prima che un Agent possa ricevere certificati da distribuire, deve autenticarsi al Server. SPIRE supporta vari meccanismi:

```
Kubernetes (più comune):
  Agent presenta il service account token del suo pod
  → Server verifica con Kubernetes API
  → Se token valido per il nodo specificato → nodo attestato

AWS:
  Agent usa AWS IID (Instance Identity Document) firmato da AWS
  → Server chiama AWS API per verificare l'istanza
  → Ogni EC2 instance ha un'identità verificabile

On-premise:
  Join token (segreto monouso) per la prima registrazione
  TPM-based attestation per hardware fidato
  x509 certificate con CA aziendale
```

### Workload Attestation

Dopo che il nodo è attestato, l'Agent attesta ogni singolo workload:

```
Pod Kubernetes:
  Agent legge /proc/<PID>/ns/ per il namespace del processo
  Consulta Kubernetes API per il pod che corrisponde al PID
  Verifica: namespace, service account, labels, annotations

Entry nel registry (come il "mapping" workload → SPIFFE ID):
  spiffe_id: "spiffe://example.com/ns/production/sa/orders"
  selector:
    - kubernetes:ns:production
    - kubernetes:sa:orders-service-account
```

---

## Configurazione SPIRE su Kubernetes

```yaml
# spire-server.yaml — ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: spire-server
  namespace: spire
data:
  server.conf: |
    server {
      bind_address = "0.0.0.0"
      bind_port = "8081"
      socket_path = "/tmp/spire-server/private/api.sock"
      trust_domain = "example.com"
      data_dir = "/run/spire/data"
      log_level = "INFO"

      ca_ttl = "24h"            # Durata CA intermedia
      default_svid_ttl = "1h"   # Durata SVID — 1h è il bilanciamento rotation/overhead
    }

    plugins {
      DataStore "sql" {
        plugin_data {
          database_type = "postgres"
          connection_string = "postgresql://spire@spire-db:5432/spire?sslmode=require"
        }
      }

      NodeAttestor "k8s_psat" {
        plugin_data {
          clusters = {
            "k8s-cluster-prod" = {
              service_account_allow_list = ["spire:spire-agent"]
              audience = ["spire-server"]
            }
          }
        }
      }

      KeyManager "disk" {
        plugin_data {
          keys_path = "/run/spire/data/keys.json"
        }
      }

      UpstreamAuthority "disk" {
        plugin_data {
          cert_file_path = "/run/spire/tls/root-cert.pem"
          key_file_path  = "/run/spire/tls/root-key.pem"
        }
      }
    }
```

```yaml
# spire-agent.yaml — ConfigMap
data:
  agent.conf: |
    agent {
      data_dir = "/run/spire"
      log_level = "INFO"
      trust_domain = "example.com"
      server_address = "spire-server"
      server_port = "8081"
      socket_path = "/tmp/spire-agent/public/api.sock"
    }

    plugins {
      NodeAttestor "k8s_psat" {
        plugin_data {
          cluster = "k8s-cluster-prod"
          token_path = "/var/run/secrets/tokens/spire-agent"
        }
      }

      WorkloadAttestor "k8s" {
        plugin_data {
          skip_kubelet_verification = false
        }
      }

      KeyManager "memory" {}
    }
```

### Registrare una Entry (Workload → SPIFFE ID)

```bash
# Registra il servizio "orders" con il suo SPIFFE ID
kubectl exec -n spire spire-server-0 -- \
  spire-server entry create \
    -spiffeID "spiffe://example.com/ns/production/sa/orders" \
    -parentID "spiffe://example.com/k8s-cluster-prod/ns/spire/sa/spire-agent" \
    -selector "k8s:ns:production" \
    -selector "k8s:sa:orders-service-account" \
    -ttl 3600

# Verifica entries
kubectl exec -n spire spire-server-0 -- spire-server entry show

# Verifica SVID su un workload (dal pod)
kubectl exec -n production orders-pod -- \
  spire-agent api fetch x509 -socketPath /tmp/spire-agent/public/api.sock
```

---

## Integrazione con Istio — mTLS Automatico

Istio integra SPIFFE nativamente: ogni sidecar Envoy riceve automaticamente un SVID SPIFFE tramite SPIRE o il sistema PKI interno di Istio (Citadel/istiod).

```yaml
# PeerAuthentication: imposta la policy mTLS a livello di namespace
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT    # STRICT = solo mTLS, nessun testo in chiaro
                    # PERMISSIVE = accetta sia mTLS che plaintext (transizione)
                    # DISABLE = disabilita mTLS
---
# AuthorizationPolicy: chi può parlare con chi
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: orders-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: orders-service
  rules:
  - from:
    - source:
        principals:
        # Solo il frontend e il payment service possono chiamare orders
        - "cluster.local/ns/production/sa/frontend-service-account"
        - "cluster.local/ns/production/sa/payment-service-account"
    to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/orders*"]
```

```
Con STRICT mTLS in Istio, il traffico tra pod appare così:

Pod A  ──plaintext──► Envoy A ══mTLS══ Envoy B ──plaintext──► Pod B
           (loopback)    (SPIFFE cert)    (SPIFFE cert)   (loopback)

L'applicazione non sa nulla di TLS — è trasparente.
La comunicazione tra Envoy A e Envoy B è mTLS con SPIFFE SVID.
```

---

## SPIFFE Federation — Multi-Cluster e Hybrid Cloud

In un'architettura che spanna più cluster Kubernetes o cloud + on-premise, ogni cluster ha il suo trust domain. La federation permette ai workload di trust domain diversi di comunicare con mTLS verificato:

```
Cluster A (trust-domain: prod.example.com)     Cluster B (trust-domain: staging.example.com)
        │                                               │
        │                                               │
   SPIRE Server A ◄──── Federation Bundle ────── SPIRE Server B
        │                                               │
   (sa certificati dal                          (sa certificati dal
    SPIRE Server A)                              SPIRE Server B)

Workload in Cluster A può verificare il certificato di
un workload in Cluster B perché conosce il trust bundle del Cluster B.

Questo è l'equivalente mTLS della federazione OIDC tra Identity Provider.
```

```bash
# Configurare la federation tra due SPIRE server
# Su SPIRE Server A: stabilire trust con SPIRE Server B
spire-server bundle show -format spiffe > bundle-a.json

# Su SPIRE Server B: importare il bundle di A
spire-server bundle set \
  -format spiffe \
  -id "spiffe://prod.example.com" \
  -path bundle-a.json
```

---

## On-Premise — SPIRE senza Kubernetes

Su VM o bare metal, SPIRE usa attestatori diversi:

```hcl
# Agent su VM Linux — node attestation via join token (bootstrap)
agent {
  data_dir    = "/var/lib/spire/agent"
  trust_domain = "corp.example.com"
  server_address = "spire-server.corp.example.com"
  server_port = "8081"
  socket_path = "/var/run/spire/agent.sock"
}

plugins {
  NodeAttestor "join_token" {
    plugin_data {}
  }

  WorkloadAttestor "unix" {
    plugin_data {
      # Attesta workload basandosi su UID/GID Unix
    }
  }
}
```

```bash
# Genera un join token (monouso) sul server per registrare un nuovo agente
spire-server token generate -spiffeID spiffe://corp.example.com/agent/vm-prod-01

# Avvia l'agent con il token
spire-agent run -joinToken <token>
```

---

## Confronto: mTLS vs API Key vs Password

| | API Key | Password / JWT M2M | mTLS + SPIFFE |
|---|---------|-------------------|---------------|
| Durata credenziale | Permanente | Configurata | Breve (1h) — rotazione auto |
| Distribuzione | Manuale | Manuale / Vault | Automatica (SPIRE) |
| Revoca | Manuale | Lifetime o blacklist | Scadenza naturale (< 1h) |
| Protezione replay | No | JWT nbf/jti | TLS session |
| Zero Trust alignment | Bassa | Media | Alta |
| Complessità operativa | Bassa | Media | Alta |
| Scala a migliaia di servizi | Problematica | Gestibile | Progettato per questo |

---

## Best Practices

- **SVID lifetime 1h**: è il bilanciamento tra sicurezza (rotazione frequente) e overhead (ogni rotazione è una chiamata al SPIRE server). Mai usare lifetime > 24h
- **STRICT mTLS in produzione**: PERMISSIVE è utile solo durante la migrazione — in produzione, zero testo in chiaro tra servizi
- **Separare trust domain per ambiente**: `prod.example.com`, `staging.example.com`, `dev.example.com` — un certificato di staging non funziona in produzione
- **SPIRE in HA**: SPIRE Server deve essere deployato in modo HA (multi-replica con datastore PostgreSQL) — è un componente critico: se il Server è down, gli agenti continuano a funzionare con i SVID attuali finché non scadono
- **Audit delle entries**: ogni SPIFFE ID registrato deve essere revisionato — un'entry non necessaria è una superficie di attacco

## Troubleshooting

### Scenario 1 — Workload non riceve SVID (attestation fallita)

**Sintomo:** Il workload ottiene errore `no identity issued` o `no registration entries found` quando consulta la Workload API.

**Causa:** Nessuna entry nel registry corrisponde ai selector del pod (namespace, service account, labels), oppure il SPIRE Agent non ha completato il node attestation.

**Soluzione:**
```bash
# Verifica le entries registrate sul server
kubectl exec -n spire spire-server-0 -- spire-server entry show

# Controlla i log dell'agent per errori di attestation
kubectl logs -n spire -l app=spire-agent --tail=50 | grep -E "error|warn|attestation"

# Verifica che il pod abbia il service account corretto
kubectl get pod <pod-name> -n production -o jsonpath='{.spec.serviceAccountName}'

# Registra manualmente l'entry mancante
kubectl exec -n spire spire-server-0 -- \
  spire-server entry create \
    -spiffeID "spiffe://example.com/ns/production/sa/my-service" \
    -parentID "spiffe://example.com/k8s-cluster-prod/ns/spire/sa/spire-agent" \
    -selector "k8s:ns:production" \
    -selector "k8s:sa:my-service-account"
```

---

### Scenario 2 — mTLS handshake fallisce (CERTIFICATE_VERIFY_FAILED)

**Sintomo:** Connessione rifiutata con errore `certificate verify failed` o `PEER_CERTIFICATE_REQUIRED`; nei log Envoy appare `SSL handshake failed`.

**Causa:** I certificati dei due workload sono stati emessi da trust domain diversi, oppure i bundle di fiducia non sono sincronizzati dopo una rotazione della CA radice.

**Soluzione:**
```bash
# Recupera e ispeziona l'SVID corrente dal workload
kubectl exec -n production <pod-name> -- \
  spire-agent api fetch x509 \
  -socketPath /tmp/spire-agent/public/api.sock \
  -write /tmp/svid

openssl x509 -in /tmp/svid/svid.0.pem -noout -text | grep -E "Subject|SAN|Issuer|Not After"

# Verifica il trust bundle in uso sull'agent
kubectl exec -n spire <spire-agent-pod> -- \
  spire-agent api fetch bundle -socketPath /tmp/spire-agent/public/api.sock

# In Istio: controlla il certificato del sidecar Envoy
istioctl proxy-config secret <pod-name>.production
```

---

### Scenario 3 — SPIRE Agent non raggiunge il Server (bootstrap failure)

**Sintomo:** L'agent non parte; nei log appare `failed to dial server` o `node attestation failed: connection refused`.

**Causa:** Il SPIRE Server non è raggiungibile per motivi di rete/DNS, il join token è scaduto (monouso), oppure il service account token proiettato non è disponibile.

**Soluzione:**
```bash
# Verifica che il SPIRE Server sia running e raggiungibile
kubectl get pods -n spire
kubectl exec -n spire <spire-agent-pod> -- \
  nc -zv spire-server 8081

# Controlla la disponibilità del token proiettato sul DaemonSet
kubectl exec -n spire <spire-agent-pod> -- \
  cat /var/run/secrets/tokens/spire-agent

# Rigenera un join token per l'on-premise (se scaduto)
spire-server token generate \
  -spiffeID spiffe://corp.example.com/agent/vm-prod-01 \
  -ttl 600

# Verifica i log del server per la fase di attestation
kubectl logs -n spire spire-server-0 --tail=100 | grep -E "error|attestation|node"
```

---

### Scenario 4 — mTLS STRICT rifiuta traffico legittimo in Istio

**Sintomo:** Dopo aver impostato `PeerAuthentication` a `STRICT`, alcune chiamate HTTP tra servizi iniziano a fallire con `503` o `connection reset`.

**Causa:** Uno o più servizi chiamanti non hanno il sidecar Envoy iniettato (mancano di mTLS), oppure c'è traffico diretto che bypassa il mesh (chiamate a IP esterni o porte non intercettate da Envoy).

**Soluzione:**
```yaml
# Passo 1: usa PERMISSIVE per diagnosticare senza interrompere il traffico
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: PERMISSIVE    # Permetti sia mTLS che plaintext durante l'analisi
```
```bash
# Identifica i pod senza sidecar Envoy nel namespace
kubectl get pods -n production \
  -o jsonpath='{range .items[?(!@.spec.containers[*].name=="istio-proxy")]}{.metadata.name}{"\n"}{end}'

# Abilita l'injection sul namespace e fai rolling restart
kubectl label namespace production istio-injection=enabled
kubectl rollout restart deployment -n production

# Dopo la verifica, riporta a STRICT
kubectl patch peerauthentication default -n production \
  --type=merge -p '{"spec":{"mtls":{"mode":"STRICT"}}}'

# Verifica lo stato mTLS con istioctl
istioctl authn tls-check <pod-name>.production
```

---

## Riferimenti

- [SPIFFE/SPIRE Documentation](https://spiffe.io/docs/latest/)
- [CNCF SPIRE GitHub](https://github.com/spiffe/spire)
- [Istio mTLS Documentation](https://istio.io/latest/docs/concepts/security/#mutual-tls-authentication)
- [NIST SP 800-204B — Attribute-based Access Control for Microservices](https://csrc.nist.gov/publications/detail/sp/800-204b/final)
