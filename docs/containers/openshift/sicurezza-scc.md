---
title: "Sicurezza e SCC"
slug: sicurezza-scc
category: containers
tags: [openshift, scc, security-context-constraints, oauth, ldap, identity-providers, rbac]
search_keywords: [openshift SCC, security context constraints, openshift restricted SCC, anyuid SCC, privileged SCC, openshift OAuth server, openshift LDAP authentication, openshift htpasswd, openshift identity provider, openshift service account SCC, openshift RBAC, oc adm policy]
parent: containers/openshift/_index
related: [containers/kubernetes/sicurezza, security/autenticazione/oauth2-oidc, containers/openshift/architettura]
official_docs: https://docs.openshift.com/container-platform/latest/authentication/managing-security-context-constraints.html
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Sicurezza e SCC

## Security Context Constraints — L'Evoluzione di PSP

Le **Security Context Constraints (SCC)** sono il meccanismo OpenShift per controllare le permission dei Pod. Preesistono ai Pod Security Standards Kubernetes e sono più granulari.

```
SCC vs PSA (Kubernetes)

  Kubernetes PSA:
  - 3 livelli (privileged/baseline/restricted)
  - Per namespace (label)
  - Applica a tutti i pod del namespace

  OpenShift SCC:
  - Granulari (10+ SCC predefiniti, custom illimitati)
  - Per ServiceAccount (non per namespace)
  - Il sistema assegna automaticamente la SCC più restrittiva
    compatibile con il pod

  SCC priority: più alto il valore → valutato per primo
  anyuid (10) > restricted-v2 (default) > ...
```

**SCC predefiniti di OpenShift:**

| SCC | Priority | Uso |
|-----|----------|-----|
| `restricted-v2` | default | Default per tutti i pod non privilegiati |
| `restricted` | 0 | Legacy, mantenuto per compatibilità |
| `anyuid` | 10 | Permette qualsiasi UID (incluso root) |
| `privileged` | 100 | Accesso completo (system pods) |
| `hostmount-anyuid` | 0 | Mount di path host |
| `hostnetwork` | 0 | hostNetwork: true |
| `hostnetwork-v2` | 0 | hostNetwork con seccomp runtime |
| `nonroot` | 0 | Forza runAsNonRoot ma permette qualsiasi UID non-root |
| `nonroot-v2` | 0 | Come nonroot ma con seccomp |

```bash
# Lista tutte le SCC nel cluster
oc get scc
oc describe scc restricted-v2
# Name: restricted-v2
# Priority: <none>
# Access:
#   Users: <none>
#   Groups: system:authenticated  ← TUTTI gli utenti autenticati
# Settings:
#   Allow Privileged: false
#   Allow Privilege Escalation: false
#   Allowed Capabilities: <none>   ← nessuna cap aggiuntiva
#   Allowed Seccomp Profiles: runtime/default,localhost/*
#   Default Add Capabilities: <none>
#   Required Drop Capabilities: ALL
#   Allowed Volume Types: configMap,downwardAPI,emptyDir,
#                         ephemeral,persistentVolumeClaim,
#                         projected,secret
#   Run As User Strategy: MustRunAsRange  ← NON può essere root
#   SELinux Context Strategy: MustRunAs   ← contexto SELinux imposto
#   FSGroup Strategy: MustRunAs
#   Supplemental Groups Strategy: RunAsAny
```

---

## Assegnare SCC a ServiceAccount

```bash
# Approccio 1: tramite ClusterRoleBinding (raccomandato)
oc adm policy add-scc-to-user anyuid -z my-service-account -n my-namespace

# Equivalente manuale:
oc create clusterrolebinding my-app-anyuid \
    --clusterrole=system:openshift:scc:anyuid \
    --serviceaccount=my-namespace:my-service-account

# Rimuovi SCC
oc adm policy remove-scc-from-user anyuid -z my-service-account -n my-namespace

# Verifica quale SCC verrebbe assegnata a un pod
oc adm policy scc-subject-review -f pod.yaml
# RESOURCE    NAME    ALLOWED BY
# Pod/my-pod          anyuid    ← questa SCC permette il pod

# Verifica quale SCC è usata da un pod esistente
oc get pod my-pod -o yaml | grep scc
# annotations:
#   openshift.io/scc: restricted-v2
```

---

## SCC Custom — Least Privilege per Applicazioni

```yaml
# SCC custom per un'applicazione specifica
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: myapp-scc
allowPrivilegedContainer: false
allowPrivilegeEscalation: false
allowedCapabilities: []
defaultAddCapabilities: []
requiredDropCapabilities:
  - ALL
readOnlyRootFilesystem: true
runAsUser:
  type: MustRunAs          # MustRunAs | RunAsAny | MustRunAsNonRoot | MustRunAsRange
  uid: 1001
seLinuxContext:
  type: MustRunAs
  seLinuxOptions:
    level: "s0:c123,c456"
fsGroup:
  type: MustRunAs
  ranges:
    - min: 1001
      max: 1001
supplementalGroups:
  type: RunAsAny
volumes:
  - configMap
  - downwardAPI
  - emptyDir
  - persistentVolumeClaim
  - projected
  - secret
allowedUnsafeSysctls: []
seccompProfiles:
  - 'runtime/default'
users: []
groups: []
priority: 5
```

---

## OAuth Server — Autenticazione Centralizzata

OpenShift include un **OAuth Server** integrato che fornisce SSO per tutti i componenti (console, API, registry).

```
OpenShift OAuth Flow

  User → OpenShift Console (https://console.apps.cluster.company.com)
       → Redirect a OAuth Server (https://oauth-openshift.apps.cluster.company.com/oauth/authorize)
       → Identity Provider (LDAP/OIDC/htpasswd)
       → Autenticazione
       → OAuth Token emesso
       → Console riceve il token
       → Usa token per chiamate API

  Token types:
  - Session tokens (OAuthAccessToken): scadono dopo ~24h (configurabile)
  - Service Account tokens: JWT, usati da automation
```

**Configurazione Identity Providers:**

```yaml
# Configurazione OAuth in OAuth CR
apiVersion: config.openshift.io/v1
kind: OAuth
metadata:
  name: cluster
spec:
  identityProviders:

    # ── htpasswd (per lab/staging) ─────────────────────
    - name: htpasswd
      mappingMethod: claim
      type: HTPasswd
      htpasswd:
        fileData:
          name: htpasswd-secret   # Secret con il file htpasswd

    # ── LDAP (Active Directory) ─────────────────────────
    - name: corporate-ldap
      mappingMethod: claim
      type: LDAP
      ldap:
        url: "ldaps://ldap.company.com:636/ou=users,dc=company,dc=com?sAMAccountName"
        bindDN: "CN=openshift-svc,OU=Service Accounts,DC=company,DC=com"
        bindPassword:
          name: ldap-bind-secret   # Secret con la password
        ca:
          name: ldap-ca-cert       # ConfigMap con il CA certificate
        insecure: false
        attributes:
          id: [dn]
          email: [mail]
          name: [displayName]
          preferredUsername: [sAMAccountName]

    # ── OIDC (Okta, Azure AD, Google) ─────────────────
    - name: okta
      mappingMethod: claim
      type: OpenID
      openID:
        clientID: openshift-client-id
        clientSecret:
          name: okta-client-secret
        issuer: https://company.okta.com
        claims:
          preferredUsername: [preferred_username, email]
          name: [name]
          email: [email]
          groups: [groups]         # claim per i gruppi
        extraScopes: [groups, profile]

  tokenConfig:
    accessTokenMaxAgeSeconds: 86400     # 24h
    accessTokenInactivityTimeout: 3600  # 1h di inattività → scadenza

```

```bash
# Crea il secret htpasswd
htpasswd -c -B htpasswd.txt admin
htpasswd -B htpasswd.txt developer
oc create secret generic htpasswd-secret \
    --from-file=htpasswd=./htpasswd.txt \
    -n openshift-config

# Aggiorna (add user)
htpasswd -B htpasswd.txt newuser
oc set data secret/htpasswd-secret \
    --from-file=htpasswd=./htpasswd.txt \
    -n openshift-config

# Verifica identità create
oc get identity
oc get users
```

---

## RBAC OpenShift — Estensioni

OpenShift estende il RBAC Kubernetes con ClusterRole aggiuntivi e un layer di project-level RBAC.

```bash
# ClusterRole predefiniti importanti in OpenShift
oc get clusterroles | grep openshift

# Ruoli common:
# cluster-admin         → admin completo (usare con parsimonia)
# cluster-reader        → lettura di tutto (read-only cluster-wide)
# admin                 → admin di un namespace/project
# edit                  → può creare/modificare risorse nel namespace
# view                  → lettura risorse nel namespace
# registry-admin        → gestisce l'image registry
# registry-editor       → pusha/tira immagini

# Assegna cluster-admin temporaneo (con scadenza)
oc adm policy add-cluster-role-to-user cluster-admin alice \
    --rolebinding-name=temp-admin

# Assegna admin a un namespace
oc adm policy add-role-to-user admin bob -n production

# Assegna role a un gruppo LDAP
oc adm policy add-role-to-group view "corporate-ldap:developers" -n production

# Rimuovi tutti i role di un utente da un namespace
oc adm policy remove-user alice -n production

# Audit: chi può fare cosa
oc adm policy who-can create pods -n production
oc adm policy who-can delete secrets -n production
```

**Group Sync con LDAP:**

```yaml
# LDAPSyncConfig — sincronizza gruppi LDAP → Gruppi OpenShift
apiVersion: v1
kind: LDAPSyncConfig
url: ldaps://ldap.company.com:636
bindDN: "CN=openshift-svc,OU=Service Accounts,DC=company,DC=com"
bindPassword:
  file: /etc/secrets/ldap-password
ca: /etc/pki/ca-trust/ldap-ca.crt
insecure: false
groupUIDNameMapping:
  "CN=k8s-admins,OU=Groups,DC=company,DC=com": "cluster-admins"
  "CN=developers,OU=Groups,DC=company,DC=com": "developers"
augmentedActiveDirectory:
  groupsQuery:
    baseDN: "OU=Groups,DC=company,DC=com"
    scope: sub
    derefAliases: never
    filter: (objectClass=group)
  groupUIDAttribute: dn
  groupNameAttributes: [cn]
  usersQuery:
    baseDN: "OU=users,DC=company,DC=com"
    scope: sub
    derefAliases: never
    filter: (objectClass=person)
  userNameAttributes: [sAMAccountName]
  groupMembershipAttributes: [memberOf]
```

```bash
# Esegui la sync
oc adm groups sync \
    --sync-config=ldap-sync-config.yaml \
    --confirm

# Schedulato via CronJob:
oc apply -f - <<'EOF'
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ldap-group-sync
  namespace: openshift-authentication
spec:
  schedule: "*/15 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: ldap-sync-sa
          containers:
            - name: sync
              image: registry.redhat.io/openshift4/ose-cli:latest
              command: [oc, adm, groups, sync, --sync-config=/etc/ldap/sync.yaml, --confirm]
              volumeMounts:
                - {name: config, mountPath: /etc/ldap}
          volumes:
            - name: config
              configMap:
                name: ldap-sync-config
EOF
```

---

## Troubleshooting

### Scenario 1 — Pod non si avvia per violazione SCC

**Sintomo:** Il pod rimane in `Pending` o fallisce con `Error creating: pods ... is forbidden: unable to validate against any security context constraint`.

**Causa:** Nessuna SCC nel cluster è compatibile con i requisiti del pod (es. richiede `runAsUser: 0` ma non ha accesso a `anyuid`).

**Soluzione:** Identificare quale SCC serve e assegnarla al ServiceAccount del pod.

```bash
# Verifica quale SCC è necessaria
oc adm policy scc-subject-review -f pod.yaml

# Verifica a quale SCC ha accesso il ServiceAccount
oc adm policy scc-review -z my-service-account -n my-namespace

# Assegna la SCC necessaria
oc adm policy add-scc-to-user anyuid -z my-service-account -n my-namespace

# Controlla gli eventi del pod per il messaggio preciso
oc describe pod my-pod -n my-namespace | grep -A5 Events
```

---

### Scenario 2 — Login OAuth fallisce (Identity Provider non raggiungibile)

**Sintomo:** La console OpenShift mostra "An error occurred. Please try again." dopo il redirect all'Identity Provider. Il login via `oc login` restituisce `401 Unauthorized`.

**Causa:** Configurazione OAuth errata (URL LDAP/OIDC non raggiungibile, certificato CA mancante, credenziali del Secret non valide).

**Soluzione:** Verificare i log dell'OAuth server e la connettività all'Identity Provider.

```bash
# Controlla i log dell'OAuth server
oc logs -n openshift-authentication deployment/oauth-openshift --tail=50

# Verifica che il secret con le credenziali esista
oc get secret -n openshift-config
oc describe secret ldap-bind-secret -n openshift-config

# Testa la connettività LDAP dal cluster
oc run -it --rm ldap-test --image=registry.access.redhat.com/ubi9/ubi \
    --restart=Never -- ldapsearch -H ldaps://ldap.company.com:636 -x

# Verifica la configurazione OAuth attuale
oc get oauth cluster -o yaml
```

---

### Scenario 3 — LDAP Group Sync non funziona

**Sintomo:** I gruppi LDAP non vengono creati/aggiornati in OpenShift. Il CronJob esiste ma i gruppi non si sincronizzano.

**Causa:** ServiceAccount del CronJob manca di permessi, ConfigMap con la config non montata correttamente, o filtro LDAP non restituisce risultati.

**Soluzione:** Eseguire la sync manualmente per intercettare l'errore, verificare i permessi del ServiceAccount.

```bash
# Esegui sync manualmente con dry-run per vedere errori
oc adm groups sync \
    --sync-config=ldap-sync-config.yaml

# Verifica i log del CronJob
oc logs -n openshift-authentication job/ldap-group-sync-<id>

# Verifica che il ServiceAccount abbia il ClusterRole necessario
oc adm policy who-can create groups

# Assegna il ClusterRole corretto se mancante
oc adm policy add-cluster-role-to-user \
    system:auth-delegator -z ldap-sync-sa -n openshift-authentication

# Lista i gruppi sincronizzati
oc get groups
```

---

### Scenario 4 — SCC custom non viene applicata al pod

**Sintomo:** Il pod usa `restricted-v2` invece della SCC custom assegnata, oppure `oc adm policy scc-subject-review` non mostra la SCC custom.

**Causa:** La SCC custom ha una `priority` troppo bassa rispetto ad altre SCC assegnate al ServiceAccount, oppure il pod non usa il ServiceAccount corretto.

**Soluzione:** Aumentare la priority della SCC custom o verificare il ServiceAccount nel pod spec.

```bash
# Verifica quale SCC usa il pod in esecuzione
oc get pod my-pod -o yaml | grep 'openshift.io/scc'

# Lista SCC assegnate a un ServiceAccount con priorità
oc adm policy scc-subject-review \
    -z my-service-account -n my-namespace

# Verifica la priority della SCC custom
oc get scc myapp-scc -o jsonpath='{.priority}'

# Aumenta la priority della SCC custom (edit inline)
oc patch scc myapp-scc --type=json \
    -p='[{"op":"replace","path":"/priority","value":20}]'

# Verifica che il pod usi il ServiceAccount corretto
oc get pod my-pod -o jsonpath='{.spec.serviceAccountName}'
```

---

## Riferimenti

- [Managing SCCs](https://docs.openshift.com/container-platform/latest/authentication/managing-security-context-constraints.html)
- [Configuring Identity Providers](https://docs.openshift.com/container-platform/latest/authentication/understanding-identity-provider.html)
- [LDAP Group Sync](https://docs.openshift.com/container-platform/latest/authentication/ldap-syncing.html)
- [RBAC](https://docs.openshift.com/container-platform/latest/authentication/using-rbac.html)
