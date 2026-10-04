---
title: "Harbor — Enterprise Registry"
slug: harbor
category: containers
tags: [harbor, registry, proxy-cache, cosign, trivy, replication, robot-accounts, garbage-collection, ldap, oidc]
search_keywords: [harbor registry, harbor proxy cache, harbor replication, harbor cosign signing, harbor trivy scanning, harbor robot accounts, harbor LDAP, harbor garbage collection, harbor air-gap, harbor OCI distribution, harbor helm charts, harbor RBAC, harbor immutable tags, harbor quotas, harbor webhook]
parent: containers/registry/_index
related: [containers/registry/_index, security/supply-chain/image-scanning, security/supply-chain/sbom-cosign, containers/kubernetes/sicurezza]
official_docs: https://goharbor.io/docs/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Harbor — Enterprise Registry

## Architettura e Deploy

**Harbor** è un registry OCI enterprise-grade CNCF, progettato per ambienti con requisiti di sicurezza elevati, air-gap e multi-tenancy.

```
Harbor Component Architecture

  ┌─────────────────────────────────────────────────────────┐
  │                    Harbor Core                          │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
  │  │  Portal  │  │  Core    │  │   JobService          │  │
  │  │  (React) │  │  (Go)    │  │   (async jobs)        │  │
  │  └──────────┘  └────┬─────┘  └──────────────────────┘  │
  │                     │                                   │
  │  ┌──────────┐  ┌────┴─────┐  ┌──────────────────────┐  │
  │  │ Registry │  │ Database │  │   Redis               │  │
  │  │ (distrib)│  │ (Postgres│  │   (cache/queue)       │  │
  │  └──────────┘  └──────────┘  └──────────────────────┘  │
  │                                                         │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
  │  │  Trivy   │  │ Exporter │  │   Proxy (nginx)       │  │
  │  │ (scanner)│  │ (metrics)│  │   (TLS termination)   │  │
  │  └──────────┘  └──────────┘  └──────────────────────┘  │
  └─────────────────────────────────────────────────────────┘
```

!!! note "Notary rimosso"
    Notary v1 (Docker Content Trust) è stato deprecato e rimosso da Harbor a partire dalla v2.8. La firma delle immagini si fa oggi con **Cosign** o **Notation**: le signature sono salvate nel registry come normali artifact OCI (accessori), senza un componente dedicato.

!!! warning "Convenzioni degli esempi API"
    - Gli esempi usano `admin:Harbor12345` (password di default): **va cambiata subito** e in produzione sostituita con robot account / OIDC.
    - I commenti `# ...` dentro i payload JSON servono a spiegare i campi: JSON non li ammette, vanno rimossi prima di eseguire il `curl`.
    - Nei path API un nome di repository che contiene `/` va codificato **due volte** (`myapp/api` → `myapp%252Fapi`).

**Deploy con Helm (raccomandato per Kubernetes):**

```bash
helm repo add harbor https://helm.goharbor.io
helm repo update

# values-harbor.yaml — configurazione produzione
cat > values-harbor.yaml <<'EOF'
expose:
  type: ingress
  tls:
    enabled: true
    certSource: secret
    secret:
      secretName: harbor-tls
  ingress:
    hosts:
      core: registry.company.com
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "0"  # upload senza limite
      nginx.ingress.kubernetes.io/proxy-read-timeout: "600"

externalURL: https://registry.company.com

# Password admin da Secret preesistente (chiave: HARBOR_ADMIN_PASSWORD), non in chiaro nei values
existingSecretAdminPassword: harbor-admin-secret
existingSecretAdminPasswordKey: HARBOR_ADMIN_PASSWORD

persistence:
  enabled: true
  resourcePolicy: keep   # PVC non eliminato su helm uninstall
  persistentVolumeClaim:
    registry:
      storageClass: fast-ssd
      size: 500Gi
    database:
      storageClass: fast-ssd
      size: 10Gi
    redis:
      storageClass: fast-ssd
      size: 2Gi

database:
  type: internal   # oppure 'external' per RDS/Cloud SQL

redis:
  type: internal   # oppure 'external' per ElastiCache

trivy:
  enabled: true
  ignoreUnfixed: false
  offlineScan: false      # true per air-gap (serve mirror vulnerability DB)
  skipUpdate: false
  timeout: 5m0s

metrics:
  enabled: true
  serviceMonitor:
    enabled: true         # richiede prometheus-operator

updateStrategy:
  type: RollingUpdate
EOF

helm upgrade --install harbor harbor/harbor \
    --namespace harbor \
    --create-namespace \
    --values values-harbor.yaml \
    --version "$HARBOR_CHART_VERSION" \
    --wait --timeout 10m
```

!!! tip "Versione chart"
    Fissare sempre `--version` (la versione del chart Helm non coincide con quella di Harbor: es. chart 1.14 → Harbor 2.10). Cercare la corrente con `helm search repo harbor/harbor --versions | head`. Per HA reale servono `database.type: external` (PostgreSQL gestito), `redis.type: external`, storage oggetti (S3/GCS) al posto del PVC `registry` e `replicas > 1` su core/registry/portal/jobservice.

---

## Struttura Multi-Tenant: Projects e RBAC

Harbor organizza le immagini in **Projects** con policy di accesso indipendenti.

```bash
# Creare un project via CLI (Harbor API)
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/projects" \
    -H "Content-Type: application/json" \
    -d '{
        "project_name": "myteam",
        "metadata": {
            "public": "false",
            "enable_content_trust_cosign": "true", # pull solo di immagini firmate con cosign
            "prevent_vul": "true",               # blocca pull con CVE critical
            "severity": "critical",              # soglia CVE
            "auto_scan": "true",                 # scan automatico al push
            "reuse_sys_cve_allowlist": "false"
        },
        "storage_limit": 107374182400            # 100 GB limit
    }'

# Aggiungere membro al project (LDAP group)
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/projects/myteam/members" \
    -H "Content-Type: application/json" \
    -d '{
        "role_id": 2,                            # 1=admin, 2=developer, 3=guest, 4=maintainer, 5=limited guest
        "member_group": {
            "group_name": "devs",
            "ldap_group_dn": "cn=devs,ou=groups,dc=company,dc=com",
            "group_type": 1                      # 1=LDAP, 2=HTTP, 3=OIDC
        }
    }'
```

**Ruoli Harbor:**

| Ruolo | Pull | Push | Delete | Admin Project |
|-------|------|------|--------|---------------|
| Guest | ✓ | ✗ | ✗ | ✗ |
| Developer | ✓ | ✓ | ✗ | ✗ |
| Maintainer | ✓ | ✓ | ✓ | ✗ |
| Admin | ✓ | ✓ | ✓ | ✓ |

---

## Robot Accounts — Service Identità

I **Robot Accounts** sono identità non umane per CI/CD pipeline con scope granulari.

```bash
# Creare robot account con scope pull-only su project
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/robots" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "ci-pipeline",
        "description": "CI/CD pipeline robot - read only",
        "duration": 365,                         # scadenza in giorni (-1 = mai)
        "level": "project",                      # oppure "system"
        "permissions": [
            {
                "kind": "project",
                "namespace": "myteam",
                "access": [
                    {"resource": "repository", "action": "pull"},
                    {"resource": "artifact",   "action": "read"},
                    {"resource": "scan",       "action": "create"}
                ]
            }
        ]
    }'
# Risposta: {"name":"robot$myteam+ci-pipeline","secret":"xxxx..."}
# Il nome completo include il prefisso del project: robot$<project>+<name>

# Robot con push access (per CI build)
# access: pull + push + delete (per cleanup)
# Conservare il secret: non è recuperabile in seguito (solo rigenerabile)

# Uso in Docker login
docker login registry.company.com \
    -u 'robot$myteam+ci-pipeline' \
    -p "secret-from-creation"

# In Kubernetes Secret per imagePullSecrets
kubectl create secret docker-registry harbor-robot \
    --docker-server=registry.company.com \
    --docker-username='robot$myteam+ci-pipeline' \
    --docker-password='secret-from-creation' \
    -n myapp
```

---

## Proxy Cache — Pull-Through per Registri Esterni

Il **Proxy Cache** riduce la dipendenza dai registri pubblici e supporta scenari air-gap.

```bash
# 1. Creare endpoint (Endpoint Registry)
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/registries" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "docker-hub-proxy",
        "type": "docker-hub",
        "url": "https://hub.docker.com",
        "credential": {
            "access_key": "dockerhub-username",
            "access_secret": "dockerhub-password"
        },
        "insecure": false
    }'
# Risposta: {"id": 1, "name": "docker-hub-proxy", ...}

# 2. Creare project di tipo proxy cache
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/projects" \
    -H "Content-Type: application/json" \
    -d '{
        "project_name": "docker-hub",
        "registry_id": 1,                        # ID dell'endpoint sopra
        "metadata": {"public": "false"}
    }'

# 3. Pull trasparente attraverso Harbor
# Invece di: docker pull nginx:1.25
# (le immagini "ufficiali" di Docker Hub stanno nel namespace library/)
docker pull registry.company.com/docker-hub/library/nginx:1.25
# Harbor → controlla cache → cache miss → pull da Docker Hub → conserva localmente

# Stessa cosa per altri registri (il nome del project lo scegli tu, 1 project = 1 endpoint):
# quay.io    → registry.company.com/quay-io/<image>
# gcr.io     → registry.company.com/gcr/<image>
# ghcr.io    → registry.company.com/ghcr/<image>
# registry.k8s.io → registry.company.com/k8s/<image>
```

**Cache invalidation e refresh:**

```bash
# Non c'è un TTL configurabile. A ogni pull Harbor fa una HEAD sul manifest upstream:
#  - digest cambiato (es. tag mutabile come :latest) → scarica la nuova versione
#  - upstream irraggiungibile → serve la copia in cache
# La HEAD non conta nel rate limit di Docker Hub, quindi il proxy cache riduce
# il rischio di "429 Too Many Requests" in cluster con molti nodi.
# Per forzare un refresh: eliminare l'artifact dal proxy cache project.

# Verificare se un'immagine è in cache
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/projects/docker-hub/repositories/nginx/artifacts?page=1&page_size=10" \
    | jq '.[].digest'
```

---

## Replication — Multi-Registry e Multi-Cloud

```bash
# Replication Rule: Harbor → ECR (push replication)
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/replication/policies" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "replicate-to-ecr-prod",
        "enabled": true,
        "src_registry": null,                    # null = registry locale
        "dest_registry": {"id": 2},              # ECR endpoint
        "dest_namespace": "myapp",
        "filters": [
            {"type": "name",   "value": "myteam/**"},
            {"type": "tag",    "value": "v*"},   # solo tag version (v1.0.0)
            {"type": "label",  "value": "approved"}  # solo immagini con label
        ],
        "trigger": {
            "type": "event_based",               # oppure "scheduled"
            "trigger_settings": {}
        },
        "override": true,                        # sovrascrive se esiste
        "speed": -1,                             # -1 = no limit
        "copy_by_chunk": false,
        "deletion": false                        # non cancellare da dest se rimosso da src
    }'

# Trigger manuale di una replication policy
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/replication/executions" \
    -H "Content-Type: application/json" \
    -d '{"policy_id": 1}'

# Monitor execution
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/replication/executions/1/tasks" \
    | jq '.[] | {status, artifact}'
```

**Topologie di replicazione comuni:**

```
Active-Active (DR):
  Harbor-EU ←──── push ──→ Harbor-US
  (ogni push si replica sull'altro sito)

Hub-and-Spoke (centrale → edge):
  Harbor-Central ──push──→ Harbor-Site-A
                 ──push──→ Harbor-Site-B
                 ──push──→ Harbor-Site-C
  (replication policy per ogni spoke)

Harbor → Cloud Registry:
  Harbor-Prod ──push──→ ECR (failover)
              ──push──→ ACR (multi-cloud)
```

---

## Vulnerability Scanning — Trivy Policy

```yaml
# Harbor Scan Policy — blocco pull su CVE critical
# Configurabile via UI: Project → Configuration → Vulnerability

# Equivalente API:
# POST /api/v2.0/projects
# "prevent_vul": "true"
# "severity": "critical"    # blocca se CVE ≥ critical
# Valori: none, low, medium, high, critical
```

```bash
# Trigger scan manuale su artifact specifico
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/projects/myteam/repositories/myapp%252Fapi/artifacts/sha256:abc123/scan"

# Get scan report
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/projects/myteam/repositories/myapp%252Fapi/artifacts/sha256:abc123/additions/vulnerabilities" \
    | jq '.["application/vnd.security.vulnerability.report; version=1.1"].vulnerabilities
          | group_by(.severity) | map({severity: .[0].severity, count: length})'
# Output: [{"severity":"Critical","count":2},{"severity":"High","count":8}]

# Scan all artifacts (system-wide), schedulata ogni notte:
# serve a rilevare CVE pubblicate DOPO il push di immagini già nel registry
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/system/scanAll/schedule" \
    -H "Content-Type: application/json" \
    -d '{"schedule": {"type": "Custom", "cron": "0 0 1 * * *"}}'

# Allowlist CVE per progetto (eccezioni motivate)
curl -s -u "admin:Harbor12345" \
    -X PUT "https://registry.company.com/api/v2.0/projects/myteam" \
    -H "Content-Type: application/json" \
    -d '{
        "metadata": {},
        "cve_allowlist": {
            "items": [
                {"cve_id": "CVE-2023-12345"},   # accepted risk, workaround applied
                {"cve_id": "CVE-2023-67890"}
            ],
            "expires_at": 1798761600            # expiry Unix timestamp (2027-01-01): oltre, l'eccezione decade
        }
    }'
```

---

## Cosign Image Signing Policy

```bash
# Abilitare l'enforcement su un project:
# Project → Configuration → Deployment security → "Cosign" (enable_content_trust_cosign)
# (l'opzione "Content Trust" legacy era basata su Notary, rimosso dalla v2.8)

# Cosign: firma un'immagine e il signature viene conservato nel registry
# come artifact OCI accessorio (tag sha256-<digest>.sig / referrer)
# Harbor mostra il badge "Signed" nella UI

# Firma un'immagine (keyless con Sigstore OIDC):
cosign sign \
    --yes \
    --rekor-url=https://rekor.sigstore.dev \
    registry.company.com/myteam/myapp:1.0.0@sha256:abc123

# Verifica prima del pull (in pipeline):
cosign verify \
    --rekor-url=https://rekor.sigstore.dev \
    --certificate-identity="https://github.com/company/myapp/.github/workflows/build.yaml@refs/heads/main" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    registry.company.com/myteam/myapp:1.0.0

# Con chiave organizzativa (infrastructure-managed):
cosign generate-key-pair   # genera cosign.key + cosign.pub

cosign sign \
    --key cosign.key \
    registry.company.com/myteam/myapp:1.0.0

cosign verify \
    --key cosign.pub \
    registry.company.com/myteam/myapp:1.0.0

# Kubernetes: Kyverno policy per verificare firma
# (Harbor blocca il pull se enable_content_trust_cosign=true e l'immagine non è firmata;
#  Harbor controlla solo la PRESENZA di una signature, non identità/issuer:
#  quella verifica resta a cosign verify in pipeline o a Kyverno/policy-controller nel cluster)
```

---

## Immutable Tags

```bash
# Immutable Tag Rule: nessun overwrite dei tag v* (versioni)
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/projects/myteam/immutabletagrules" \
    -H "Content-Type: application/json" \
    -d '{
        "scope_selectors": {
            "repository": [{
                "kind": "doublestar",
                "decoration": "repoMatches",
                "pattern": "**"       # tutti i repository nel project
            }]
        },
        "tag_selectors": [{
            "kind": "doublestar",
            "decoration": "matches",
            "pattern": "v*"           # tag che iniziano con v
        }]
    }'

# Con immutable tags attivi:
# docker push registry.company.com/myteam/myapp:v1.0.0  → OK (primo push)
# docker push registry.company.com/myteam/myapp:v1.0.0  → ERRORE (tag già esiste, immutable)
# docker push registry.company.com/myteam/myapp:latest  → OK (non corrisponde a v*)
```

---

## Tag Retention — Garbage Collection

Due meccanismi distinti e da concatenare: la **Retention** rimuove tag/artifact secondo regole (non libera ancora spazio su disco); la **Garbage Collection** elimina poi i blob non più referenziati e libera lo storage.

```bash
# Retention Policy: mantieni solo ultimi 10 artifact con tag v*
# (ref = ID numerico del project, da GET /projects/myteam)
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/retentions" \
    -H "Content-Type: application/json" \
    -d '{
        "algorithm": "or",
        "rules": [
            {
                "priority": 1,
                "disabled": false,
                "action": "retain",
                "template": "latestPushedK",
                "params": {"latestPushedK": 10},
                "tag_selectors": [{"kind": "doublestar", "decoration": "matches", "pattern": "v*"}],
                "scope_selectors": {
                    "repository": [{"kind": "doublestar", "decoration": "repoMatches", "pattern": "**"}]
                }
            },
            {
                "priority": 2,
                "disabled": false,
                "action": "retain",
                "template": "nDaysSinceLastPull",
                "params": {"nDaysSinceLastPull": 30},
                "tag_selectors": [{"kind": "doublestar", "decoration": "matches", "pattern": "latest"}],
                "scope_selectors": {
                    "repository": [{"kind": "doublestar", "decoration": "repoMatches", "pattern": "**"}]
                }
            }
        ],
        "scope": {"level": "project", "ref": 1},
        "trigger": {
            "kind": "Schedule",
            "settings": {"cron": "0 0 2 * * 0"}  # domenica notte alle 2:00
        }
    }'

# Garbage Collection — elimina i blob non referenziati
# Dalla v2.1 la GC è non-blocking (push/pull restano possibili); nelle versioni
# precedenti il registry andava in sola lettura. Schedulare comunque off-peak:
# la GC genera I/O intenso sullo storage.

curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/system/gc/schedule" \
    -H "Content-Type: application/json" \
    -d '{
        "schedule": {
            "type": "Custom",
            "cron": "0 0 3 * * 0"           # domenica notte alle 3:00
        },
        "parameters": {
            "delete_untagged": true,         # elimina artifact senza tag
            "dry_run": false,                # true per test senza cancellazione
            "workers": 4                     # parallelismo
        }
    }'

# Monitor GC execution
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/system/gc?page=1&page_size=5" \
    | jq '.[] | {id, status, creation_time}'
```

---

## LDAP / OIDC Integration

```bash
# Configurazione LDAP (via Harbor UI: Administration → Configuration → Auth)
curl -s -u "admin:Harbor12345" \
    -X PUT "https://registry.company.com/api/v2.0/configurations" \
    -H "Content-Type: application/json" \
    -d '{
        "auth_mode": "ldap_auth",
        "ldap_url": "ldaps://ldap.company.com:636",
        "ldap_base_dn": "dc=company,dc=com",
        "ldap_search_dn": "cn=harbor-bind,ou=service-accounts,dc=company,dc=com",
        "ldap_search_password": "bind-password",
        "ldap_filter": "(objectClass=person)",
        "ldap_uid": "sAMAccountName",          # attributo per username
        "ldap_group_base_dn": "ou=groups,dc=company,dc=com",
        "ldap_group_attribute_name": "memberOf",
        "ldap_group_search_filter": "(objectClass=group)",
        "ldap_group_search_scope": 2,          # 2=subtree
        "ldap_verify_cert": true
    }'

# Test LDAP connection
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/ldap/ping"

# Test LDAP user search
curl -s -u "admin:Harbor12345" \
    -X GET "https://registry.company.com/api/v2.0/ldap/users/search?username=johndoe"
```

```yaml
# Configurazione OIDC (OpenID Connect — es. Okta, Keycloak)
# auth_mode: oidc_auth
# oidc_name: "Company SSO"
# oidc_endpoint: "https://company.okta.com/oauth2/default"
# oidc_client_id: "harbor"
# oidc_client_secret: "client-secret"
# oidc_scope: "openid,email,profile,groups"
# oidc_groups_claim: "groups"         # claim JWT per i gruppi
# oidc_admin_group: "harbor-admins"   # gruppo = Harbor admin
# oidc_verify_cert: true
# oidc_auto_onboard: true             # crea utente Harbor al primo login
# oidc_user_claim: "email"            # attributo JWT per username
```

!!! warning "OIDC e client Docker"
    Con `auth_mode: oidc_auth` `docker login` con la password SSO **non funziona**: l'utente usa il **CLI secret** (profilo utente nella UI), mentre le pipeline devono usare robot account. Inoltre `auth_mode` non è modificabile una volta che esistono utenti non-admin locali.

---

## Webhook e Notifiche

```bash
# Webhook: notifica un endpoint su eventi Harbor
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/projects/myteam/webhook/policies" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "ci-notifications",
        "description": "Notifica CI su push/scan",
        "enabled": true,
        "targets": [{
            "type": "http",
            "address": "https://ci.company.com/harbor-webhook",
            "auth_header": "Bearer ci-token",
            "skip_cert_verify": false
        }],
        "event_types": [
            "PUSH_ARTIFACT",
            "PULL_ARTIFACT",
            "DELETE_ARTIFACT",
            "SCANNING_COMPLETED",
            "SCANNING_FAILED",
            "QUOTA_EXCEED",
            "QUOTA_WARNING",
            "REPLICATION"
        ]
    }'

# Payload webhook (esempio PUSH_ARTIFACT):
# {
#   "type": "PUSH_ARTIFACT",
#   "occur_at": 1700000000,
#   "operator": "robot$myteam+ci-pipeline",
#   "event_data": {
#     "resources": [{
#       "resource_url": "registry.company.com/myteam/myapp:v1.0.0",
#       "tag": "v1.0.0",
#       "digest": "sha256:abc123...",
#       "resource_type": "artifact"
#     }],
#     "repository": {
#       "name": "myapp",
#       "namespace": "myteam",
#       "full_name": "myteam/myapp",
#       "type": "private"
#     }
#   }
# }
```

---

## Quotas — Resource Limiting

```bash
# Quota su project (storage e artifact count)
# L'ID quota NON è l'ID project: ricavarlo con
#   curl -s -u admin:... "https://registry.company.com/api/v2.0/quotas?reference=project&reference_id=<project_id>" | jq '.[].id'
curl -s -u "admin:Harbor12345" \
    -X PUT "https://registry.company.com/api/v2.0/quotas/1" \
    -H "Content-Type: application/json" \
    -d '{
        "hard": {
            "storage": 107374182400,     # 100 GiB in bytes (-1 = unlimited)
            "count": 1000                # max artifact count (-1 = unlimited)
        }
    }'

# Quota globale (default per nuovi project)
curl -s -u "admin:Harbor12345" \
    -X PUT "https://registry.company.com/api/v2.0/configurations" \
    -H "Content-Type: application/json" \
    -d '{
        "storage_per_project": 107374182400,
        "count_per_project": -1
    }'

# Visualizza utilizzo quota
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/quotas?page=1&page_size=20" \
    | jq '.[] | {id, ref, hard, used: .used}'
```

---

## Harbor in Kubernetes — Considerazioni Operative

```bash
# Verifica stato componenti Harbor
kubectl get pods -n harbor
kubectl logs -n harbor deployment/harbor-core --tail=50
kubectl logs -n harbor deployment/harbor-jobservice --tail=50

# Backup database Harbor (PostgreSQL interno)
# (il database interno è uno StatefulSet, non un Deployment)
kubectl exec -n harbor statefulset/harbor-database -- \
    pg_dump -U postgres registry > harbor-db-backup-$(date +%Y%m%d).sql
# Il dump copre solo metadati (project, RBAC, policy): i blob stanno nel PVC/bucket
# `registry` e vanno salvati a parte (snapshot volume / versioning del bucket).

# Restore
kubectl exec -i -n harbor statefulset/harbor-database -- \
    psql -U postgres registry < harbor-db-backup-20260225.sql

# Upgrade Harbor via Helm: un minor alla volta, dopo backup DB, leggendo le release notes
helm upgrade harbor harbor/harbor \
    --namespace harbor \
    --values values-harbor.yaml \
    --version "$HARBOR_NEXT_CHART_VERSION" \
    --wait --timeout 15m

# Harbor storage usage
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/statistics" \
    | jq '{
        total_project_count,
        total_repo_count,
        total_artifact_count,
        total_storage_consumption
    }'

# Health check completo
curl -s "https://registry.company.com/api/v2.0/health" \
    | jq '.components[] | select(.status != "healthy")'
```

---

## Troubleshooting

### Scenario 1 — Harbor Core in CrashLoopBackOff dopo deploy

**Sintomo:** `kubectl get pods -n harbor` mostra `harbor-core-xxx` in `CrashLoopBackOff` o `Error`.

**Causa:** Connessione fallita al database PostgreSQL (password errata, PVC non montato) oppure `externalURL` non corrisponde all'hostname effettivo.

**Soluzione:**
```bash
# Verificare i log del core
kubectl logs -n harbor deployment/harbor-core --tail=100

# Errore tipico: "failed to ping db" → verificare credenziali database
# (con release "harbor"; per DB esterno: Secret/values con la password configurata)
kubectl get secret -n harbor harbor-database -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
kubectl logs -n harbor statefulset/harbor-database --tail=50

# Verificare che il PVC database sia Bound
kubectl get pvc -n harbor

# Verificare externalURL nel ConfigMap
kubectl get cm -n harbor harbor-harbor-core -o yaml | grep -i externalurl

# Restart forzato dopo fix
kubectl rollout restart deployment/harbor-core -n harbor
kubectl rollout status deployment/harbor-core -n harbor
```

---

### Scenario 2 — Push fallisce con "401 Unauthorized" anche con credenziali corrette

**Sintomo:** `docker push registry.company.com/myteam/myapp:v1.0.0` restituisce `401 Unauthorized` o `denied: requested access to the resource is denied`.

**Causa:** Il robot account non ha permesso `push` sul project, oppure il token è scaduto, oppure Harbor non è raggiungibile in HTTPS con certificato valido.

**Soluzione:**
```bash
# Verificare che docker sia autenticato correttamente
docker login registry.company.com
cat ~/.docker/config.json | jq '.auths["registry.company.com"]'

# Verificare scadenza e permessi del robot account via API
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/robots?page=1&page_size=20" \
    | jq '.[] | select(.name | contains("ci-pipeline")) | {name, duration, expiration_time, permissions}'

# Verificare che il certificato TLS sia valido
openssl s_client -connect registry.company.com:443 -servername registry.company.com < /dev/null 2>&1 | grep -E "Verify|issuer"

# Su Kubernetes: aggiornare il secret con nuovo token
kubectl delete secret harbor-robot -n myapp
kubectl create secret docker-registry harbor-robot \
    --docker-server=registry.company.com \
    --docker-username='robot$myteam+ci-pipeline' \
    --docker-password='new-secret' \
    -n myapp
```

---

### Scenario 3 — Garbage Collection degrada push/pull in produzione

**Sintomo:** Durante la GC push e pull rallentano o falliscono con timeout / `503 Service Unavailable`.

**Causa:** Dalla v2.1 la GC è non-blocking, ma su storage con molti blob genera I/O intenso e può saturare registry/jobservice. Su Harbor < 2.1 il registry veniva messo in sola lettura per tutta la durata. In entrambi i casi la GC in orario di punta impatta il traffico produzione.

**Soluzione:**
```bash
# Verificare se GC è in corso
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/system/gc?page=1&page_size=5" \
    | jq '.[] | {id, status, creation_time, update_time}'

# Interrompere una GC in esecuzione: ultima risorsa, riavviare jobservice
# (verificare nello swagger della propria versione se esiste lo stop del job)
kubectl rollout restart deployment/harbor-jobservice -n harbor

# Riprogrammare GC in orario off-peak (domenica 3:00)
curl -s -u "admin:Harbor12345" \
    -X PUT "https://registry.company.com/api/v2.0/system/gc/schedule" \
    -H "Content-Type: application/json" \
    -d '{"schedule": {"type": "Custom", "cron": "0 0 3 * * 0"}}'

# Prima di GC: eseguire dry_run per stimare lo spazio liberabile
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/system/gc/schedule" \
    -H "Content-Type: application/json" \
    -d '{"schedule": {"type": "Manual"}, "parameters": {"dry_run": true, "delete_untagged": true}}'
```

---

### Scenario 4 — Replication verso ECR fallisce silenziosamente

**Sintomo:** Le replication policy mostrano status `Success` ma le immagini non arrivano su ECR, oppure lo stato è `Failed` senza messaggi chiari.

**Causa:** Endpoint registrato come registry generico con token `get-login-password` (scade dopo 12h), endpoint ECR non raggiungibile dalla rete Harbor, oppure filtri della policy troppo restrittivi.

**Fix strutturale:** registrare l'endpoint con `"type": "aws-ecr"` e un'access key/secret IAM (permessi ECR push) invece del token temporaneo: l'adapter Harbor ottiene e rinnova da solo i token ECR, quindi non c'è nulla da ruotare ogni 12h.

**Soluzione:**
```bash
# Verificare i task di una replication execution
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/replication/executions?policy_id=1&page=1&page_size=5" \
    | jq '.[] | {id, status, start_time, end_time, failed, succeed, stopped}'

# Dettaglio errori sui task falliti
EXEC_ID=42
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/replication/executions/${EXEC_ID}/tasks" \
    | jq '.[] | select(.status == "Failed") | {id, status, job_id}'

# Log del task specifico
TASK_ID=123
curl -s -u "admin:Harbor12345" \
    "https://registry.company.com/api/v2.0/replication/executions/${EXEC_ID}/tasks/${TASK_ID}/log"

# Testare connettività all'endpoint ECR
curl -s -u "admin:Harbor12345" \
    -X POST "https://registry.company.com/api/v2.0/registries/2/info"

# Workaround con endpoint generico: rinnovare il token 12h
curl -s -u "admin:Harbor12345" \
    -X PUT "https://registry.company.com/api/v2.0/registries/2" \
    -H "Content-Type: application/json" \
    -d "{\"credential\": {\"type\": \"basic\", \"access_key\": \"AWS\", \"access_secret\": \"$(aws ecr get-login-password --region eu-west-1)\"}}"
```

---

## Best Practices

- **Un project per team/ambiente**, accesso via gruppi OIDC/LDAP; admin Harbor ridotti al minimo.
- **Robot account per ogni pipeline**, con scope minimo e scadenza (`duration`), mai l'utente admin.
- **Proxy cache davanti ai registry pubblici**: elimina i rate limit di Docker Hub e riduce la superficie supply-chain (insieme a scan + `prevent_vul`).
- **Immutable tags sui tag di release** (`v*`) e retention per non far crescere lo storage all'infinito; GC schedulata dopo la retention.
- **Scan on push + scanAll notturno**: le CVE nuove escono dopo il push.
- **Backup**: DB (metadati) + storage blob; provare il restore.
- **HA**: DB e Redis esterni, storage oggetti, repliche multiple; upgrade un minor alla volta.

---

## Riferimenti

- [Harbor Documentation](https://goharbor.io/docs/)
- [Harbor Helm Chart](https://github.com/goharbor/harbor-helm)
- [Harbor API v2](https://editor.swagger.io/?url=https://raw.githubusercontent.com/goharbor/harbor/main/api/v2.0/swagger.yaml)
- [Cosign + Harbor Integration](https://goharbor.io/docs/edge/working-with-projects/working-with-images/cosign-integration/)
- [Harbor Replication](https://goharbor.io/docs/latest/administration/configuring-replication/)
