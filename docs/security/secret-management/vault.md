---
title: "HashiCorp Vault"
slug: vault
category: security
tags: [vault, hashicorp, secret-management, dynamic-secrets, pki, kubernetes-auth]
search_keywords: [hashicorp vault, vault dynamic secrets, vault pki engine, vault kubernetes auth, vault aws auth, vault approle, vault agent, vault sidecar injector, vault transit encryption, vault kv secrets engine, vault lease, vault seal unseal, vault ha raft, vault enterprise, vault namespace, vault audit log, vault token, vault policy, vault acl, vault secrets engine, vault auth method, vault database secrets, vault ssh secrets, vault gcp secrets, vault azure secrets, vault agent injector kubernetes, vault csi driver, vault external secrets, vso vault secrets operator]
parent: security/secret-management/_index
related: [security/secret-management/kubernetes-secrets, security/pki-certificati/pki-interna, databases/postgresql/connection-pooling]
official_docs: https://developer.hashicorp.com/vault/docs
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# HashiCorp Vault

## Panoramica

**Vault** è il sistema di gestione dei secret di riferimento per architetture enterprise. Non è un semplice key-value store per password: è una piattaforma per la gestione del ciclo di vita di qualsiasi tipo di credenziale.

La caratteristica distintiva rispetto a semplici secret store (AWS Secrets Manager, Kubernetes Secrets) sono i **dynamic secrets**: invece di archiviare credenziali database preesistenti, Vault **genera** credenziali nuove on-demand quando un servizio ne ha bisogno, con un TTL limitato. Quando il lease scade, Vault revoca automaticamente le credenziali. Zero password statiche nel sistema.

```
MODELLO STATICO (AWS Secrets Manager, Kubernetes Secrets):
  Admin crea password → archivia in secret store → app legge la password
  Problema: la password esiste da qualche parte, è statica, deve essere ruotata manualmente

MODELLO DINAMICO (Vault):
  App si autentica a Vault → Vault genera credenziale DB al volo →
  DB riceve la credenziale → App usa la credenziale per TTL limitato →
  TTL scade → Vault revoca la credenziale → nessuna pulizia manuale
```

---

## Architettura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HashiCorp Vault                                 │
│                                                                         │
│   ┌────────────────┐   ┌──────────────────┐   ┌─────────────────────┐  │
│   │  Auth Methods  │   │  Secrets Engines  │   │    Audit Devices    │  │
│   │                │   │                  │   │                     │  │
│   │ • Kubernetes   │   │ • KV v2          │   │ • File              │  │
│   │ • AWS IAM      │   │ • Database       │   │ • Syslog            │  │
│   │ • AppRole      │   │ • PKI            │   │ • Socket            │  │
│   │ • JWT/OIDC     │   │ • Transit        │   │                     │  │
│   │ • TLS Cert     │   │ • SSH            │   │  (ogni operazione   │  │
│   │ • GCP/Azure    │   │ • AWS/GCP/Azure  │   │   è loggata)        │  │
│   └────────────────┘   └──────────────────┘   └─────────────────────┘  │
│                                                                         │
│   ┌────────────────────────────────────────────────────────────────┐    │
│   │                       Storage Backend                          │    │
│   │   • Raft (Integrated, HA — raccomandato per self-hosted)       │    │
│   │   • Consul, DynamoDB, S3, Azure Blob (esterni)                │    │
│   └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Vault HA con Raft (Integrated Storage)

```
Node 1 (Active)    Node 2 (Standby)    Node 3 (Standby)
      │                   │                   │
      └──── Raft consensus ───────────────────┘
                  │
           Client requests
           (solo Active serve le richieste)
           (Standby forwarda a Active)

In caso di crash di Node 1:
  → Raft elezione → Node 2 diventa Active in ~5-10s
  → Il SEAL state è condiviso → nessun unseal manuale necessario (auto-unseal)
```

---

## Auto-Unseal — Eliminare il Bootstrap Manuale

Al boot, Vault è **sealed**: i dati sono cifrati e inaccessibili. Il traditional unseal richiedeva N/M operatori che inserivano le proprie Shamir key shares. In produzione questo è un collo di bottiglia.

**Auto-unseal** delega la decifratura della master key a un servizio KMS esterno:

```hcl
# vault.hcl — Auto-unseal con AWS KMS
seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "arn:aws:kms:us-east-1:123456789:key/mrk-abc123"
  # Vault cifra la master key con questa KMS key al momento dell'init
  # Al reboot, decifera automaticamente senza intervento umano
}

# Azure Key Vault
seal "azurekeyvault" {
  tenant_id     = "abc-123"
  vault_name    = "vault-prod-kms"
  key_name      = "vault-unseal-key"
}

# GCP Cloud KMS
seal "gcpckms" {
  project    = "my-project"
  region     = "global"
  key_ring   = "vault-keyring"
  crypto_key = "vault-key"
}
```

---

## Auth Methods — Come i Client si Autenticano a Vault

### Kubernetes Auth (più comune per pod)

```bash
# Abilita Kubernetes auth
vault auth enable kubernetes

# Configura con le credenziali del cluster
vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc" \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
  token_reviewer_jwt=@/var/run/secrets/kubernetes.io/serviceaccount/token

# Crea un role: mappa un service account al Vault policy
vault write auth/kubernetes/role/orders-service \
  bound_service_account_names=orders-sa \
  bound_service_account_namespaces=production \
  policies=orders-service-policy \
  ttl=1h
```

```hcl
# Policy per il servizio orders
# File: orders-service-policy.hcl
path "database/creds/orders-db" {
  capabilities = ["read"]    # Può generare credenziali DB
}

path "kv/data/orders/*" {
  capabilities = ["read"]    # Può leggere secrets KV
}

path "pki/issue/orders-cert" {
  capabilities = ["update"]  # Può richiedere certificati TLS
}
```

```python
# Python — autenticazione a Vault con Kubernetes SA token
import hvac

def get_vault_client() -> hvac.Client:
    with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
        jwt_token = f.read()

    client = hvac.Client(url="https://vault.vault.svc.cluster.local:8200",
                          verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
    client.auth.kubernetes.login(
        role="orders-service",
        jwt=jwt_token,
    )
    return client
```

### AWS IAM Auth (per EC2, Lambda, ECS)

```bash
vault auth enable aws

vault write auth/aws/config/client \
  access_key=AKIA... \
  secret_key=...

# Role: le istanze EC2 con questo IAM role accedono a questi secrets
vault write auth/aws/role/orders-lambda \
  auth_type=iam \
  bound_iam_principal_arn="arn:aws:iam::123456789:role/orders-lambda-role" \
  policies=orders-service-policy \
  ttl=1h
```

---

## Secrets Engines

### KV v2 — Secrets Statici con Versioning

```bash
vault secrets enable -path=kv kv-v2

# Scrivi un secret
vault kv put kv/myapp/config \
  api_key="sk-prod-xxx" \
  webhook_secret="whsec_yyy"

# Leggi la versione corrente
vault kv get kv/myapp/config

# Storico versioni (KV v2 mantiene N versioni)
vault kv metadata get kv/myapp/config

# Recupera versione specifica (utile per rollback)
vault kv get -version=2 kv/myapp/config

# Soft delete (reversibile) vs destroy (permanente)
vault kv delete kv/myapp/config           # soft delete
vault kv undelete -versions=3 kv/myapp/config  # restore
vault kv destroy -versions=2 kv/myapp/config   # permanente
```

### Database Secrets Engine — Dynamic Credentials

```bash
vault secrets enable database

# Configura la connessione al PostgreSQL
vault write database/config/orders-db \
  plugin_name=postgresql-database-plugin \
  allowed_roles="orders-service,orders-readonly" \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/orders?sslmode=require" \
  username="vault-admin" \
  password="vault-admin-pass"

# Crea il role: Vault userà questo SQL per creare l'utente dinamico
vault write database/roles/orders-service \
  db_name=orders-db \
  creation_statements="
    CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
    GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO \"{{name}}\";
  " \
  revocation_statements="DROP ROLE IF EXISTS \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"
```

```bash
# Il servizio chiede le credenziali (Vault le genera al volo)
vault read database/creds/orders-service
# Key                  Value
# ---                  -----
# lease_id             database/creds/orders-service/abc-123
# lease_duration       1h
# lease_renewable      true
# password             A1a-xyz789...    ← password generata casualmente
# username             v-k8s-orders-abc ← username univoco con prefisso

# In PostgreSQL: l'utente esiste con queste credenziali per 1h
# Dopo 1h: Vault revoca l'utente (DROP ROLE)
# Il servizio può rinnovare il lease prima della scadenza (vault lease renew)
```

### Transit Engine — Encryption as a Service

Il **Transit engine** non archivia dati — fornisce operazioni crittografiche come servizio:

```bash
vault secrets enable transit

vault write transit/keys/orders-encryption type=aes256-gcm96

# Cifra (il plaintext deve essere base64)
vault write transit/encrypt/orders-encryption \
  plaintext=$(echo -n "1234-5678-9012-3456" | base64)
# → ciphertext: vault:v1:8SDd3WHDOjf7mq69CyCqYjBXAiQQAVZRkFM13ok481zoCmHnSeDX9vyf7w==

# Decifra
vault write transit/decrypt/orders-encryption \
  ciphertext="vault:v1:8SDd3WHDOjf7..."
# → plaintext: MTIzNC01Njc4LTkwMTItMzQ1Ng== (base64)

# Caso d'uso: PANs, PII — il microservizio cifra prima di salvare nel DB
# Solo il microservizio autorizzato può decifrare
# Il DB vede solo ciphertext → even a DB dump non espone dati sensibili
```

### PKI Engine — CA Interna

```bash
vault secrets enable pki
vault secrets tune -max-lease-ttl=87600h pki  # 10 anni per root CA

# Genera root CA interna
vault write pki/root/generate/internal \
  common_name="My Corp Root CA" \
  ttl=87600h

# Configura URL
vault write pki/config/urls \
  issuing_certificates="https://vault.example.com/v1/pki/ca" \
  crl_distribution_points="https://vault.example.com/v1/pki/crl"

# CA intermedia per i servizi
vault secrets enable -path=pki_int pki
vault write -format=json pki_int/intermediate/generate/internal \
  common_name="Services Intermediate CA" | jq -r .data.csr > pki_int.csr

vault write -format=json pki/root/sign-intermediate \
  csr=@pki_int.csr \
  ttl=43800h | jq -r .data.certificate > signed_intermediate.pem

vault write pki_int/intermediate/set-signed certificate=@signed_intermediate.pem

# Role per emettere certificati ai servizi
vault write pki_int/roles/orders-service \
  allowed_domains="orders.production.svc.cluster.local" \
  allow_subdomains=false \
  max_ttl="24h"                              # Certificati a 24h — rotazione automatica
```

---

## Vault Agent Injector — Kubernetes Integration

Il Vault Agent Injector è un Kubernetes admission webhook che inietta automaticamente i secret nei pod tramite sidecar:

```yaml
# Annotazioni sul Deployment — nessun codice Vault nell'app
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "orders-service"

        # Secret 1: file con credenziali DB dinamiche
        vault.hashicorp.com/agent-inject-secret-db-creds: "database/creds/orders-db"
        vault.hashicorp.com/agent-inject-template-db-creds: |
          {{- with secret "database/creds/orders-db" -}}
          export DB_USERNAME="{{ .Data.username }}"
          export DB_PASSWORD="{{ .Data.password }}"
          {{- end }}

        # Secret 2: KV secret
        vault.hashicorp.com/agent-inject-secret-config: "kv/data/orders/config"
        vault.hashicorp.com/agent-inject-template-config: |
          {{- with secret "kv/data/orders/config" -}}
          {{ .Data.data | toJSON }}
          {{- end }}

        # Rinnova i lease automaticamente
        vault.hashicorp.com/agent-pre-populate-only: "false"    # mantieni agent attivo
```

```
Cosa fa il Vault Agent Injector:
  1. Il pod viene creato con le annotazioni
  2. Il webhook inietta un init container (vault-agent-init) e un sidecar (vault-agent)
  3. Init container: autentica a Vault + scarica tutti i secret → file in /vault/secrets/
  4. App container parte e trova i file in /vault/secrets/
  5. Sidecar agent: monitora i lease e rinnova i secret prima della scadenza
  6. Se un secret ruota → il file viene aggiornato → l'app può fare reload (inotify/signal)
```

---

## Vault Secrets Operator (VSO) — Approccio Kubernetes-Native

Il VSO è il modo più moderno di integrare Vault con Kubernetes: sincronizza i Vault secrets in native Kubernetes Secrets:

```yaml
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultStaticSecret
metadata:
  name: orders-config
  namespace: production
spec:
  vaultAuthRef: orders-vault-auth    # VaultAuth CRD con le credenziali
  mount: kv
  type: kv-v2
  path: orders/config
  destination:
    name: orders-config-k8s-secret   # Nome del Kubernetes Secret creato
    create: true
  refreshAfter: 30s                  # Refresh ogni 30s

---
apiVersion: secrets.hashicorp.com/v1beta1
kind: VaultDynamicSecret
metadata:
  name: orders-db-creds
  namespace: production
spec:
  vaultAuthRef: orders-vault-auth
  mount: database
  path: creds/orders-db
  destination:
    name: orders-db-k8s-secret
    create: true
  rolloutRestartTargets:
  - kind: Deployment
    name: orders-service              # Riavvia il deployment quando le creds ruotano
```

---

## Best Practices

- **Vault in HA (almeno 3 nodi Raft)**: Vault è un componente critico — se è down, i servizi che richiedono nuovi secret/lease falliscono. HA con Raft integrato è la configurazione raccomandata
- **Auto-unseal sempre in produzione**: il bootstrap manuale con Shamir shares è incompatibile con restart automatici (es. nodi Kubernetes che ripartono di notte)
- **Dynamic secrets per database**: nessun motivo per usare password statiche per PostgreSQL, MySQL, MongoDB se Vault è disponibile
- **TTL brevi per i lease**: 1h per credenziali applicative, 24h max. Il Vault Agent gestisce il rinnovo — il costo operativo è zero
- **Audit logging sempre attivo**: `vault audit enable file file_path=/vault/logs/audit.log` — ogni operazione Vault deve essere loggata per compliance e incident response
- **Namespace Vault per multi-team (Enterprise)**: i team isolati usano Vault namespace separati con policy indipendenti — un team non vede i secret di un altro

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Pod stuck in init (vault-agent-init) | Service account non autorizzato / role sbagliato | Controllare `kubectl logs <pod> -c vault-agent-init` |
| `permission denied` sulla policy | Policy non assegnata o path errato | `vault token lookup`, `vault policy read <name>` |
| Credenziali DB scadono prima del rinnovo | TTL troppo breve o agent non funziona | Verificare vault-agent logs, aumentare TTL |
| Vault sealed dopo restart | Auto-unseal non configurato o KMS irraggiungibile | Verificare network, IAM role per KMS |
| `too many open requests` | Rate limiting Vault | Aumentare `max_lease_count`, ottimizzare l'acquisizione token |

## Riferimenti

- [HashiCorp Vault Documentation](https://developer.hashicorp.com/vault/docs)
- [Vault Kubernetes Auth Method](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
- [Vault Agent Injector](https://developer.hashicorp.com/vault/docs/platform/k8s/injector)
- [Vault Secrets Operator](https://developer.hashicorp.com/vault/docs/platform/k8s/vso)
