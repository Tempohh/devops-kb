---
title: "Kubernetes Sicurezza"
slug: sicurezza
category: containers
tags: [kubernetes, sicurezza, psa, rbac, admission, seccomp, falco, networkpolicy, serviceaccount]
search_keywords: [kubernetes security hardening, Pod Security Admission, PSA kubernetes, kubernetes RBAC, SecurityContext pod kubernetes, seccomp kubernetes, kubernetes admission controller, OPA Gatekeeper kubernetes, Kyverno, Falco kubernetes runtime security, kubernetes audit logging, workload identity kubernetes, service account token projection]
parent: containers/kubernetes/_index
related: [security/autenticazione/mtls-spiffe, security/autorizzazione/opa, security/supply-chain/admission-control, containers/kubernetes/workloads]
official_docs: https://kubernetes.io/docs/concepts/security/
status: complete
difficulty: expert
last_updated: 2026-02-25
---

# Kubernetes Sicurezza

## Il Modello 4C della Cloud-Native Security

```
4C Security Model

  Cloud Provider (IAM, VPC, KMS, disk encryption)
  +---------------------------------------------------+
  |  Cluster (K8s RBAC, Network Policies, PSA, etcd) |
  |  +-----------------------------------------------+|
  |  |  Container (Image scanning, rootless, caps)   ||
  |  |  +---------------------------------------------||
  |  |  |  Code (SAST, dependencies, secrets mgmt)  |||
  |  |  +---------------------------------------------||
  |  +-----------------------------------------------+|
  +---------------------------------------------------+

  Ogni layer difende indipendentemente.
  Un attaccante deve compromettere TUTTI i layer.
```

---

## Pod Security Admission (PSA)

Il **PSA** (Kubernetes 1.25+, sostituisce PodSecurityPolicy) applica profili di sicurezza a namespace interi.

```yaml
# Configura PSA per namespace tramite label
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # Tre livelli: privileged | baseline | restricted
    # Tre modalità: enforce | audit | warn
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: v1.29
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**I tre profili PSA:**

```
PSA Profiles:

PRIVILEGED: nessuna restrizione
  → Solo per system namespaces (kube-system)

BASELINE: restrizioni minime, compatibile con la maggior parte delle app
  Blocca: privileged containers, hostPID, hostIPC, hostNetwork
           HostPath volumes, hostPorts
           CAP_SYS_ADMIN e altre caps pericolose
           seccomp: nessun profilo richiesto

RESTRICTED: sicurezza massima, alcune app devono essere adattate
  Tutto ciò che blocca BASELINE più:
  Richiede: allowPrivilegeEscalation: false
            runAsNonRoot: true
            seccompProfile: RuntimeDefault o Localhost
  Blocca: capabilities diverse da NET_BIND_SERVICE
           volume types limitati (no hostPath, no NFS senza CSI)
```

```bash
# Testa se un pod viola il profilo senza applicarlo
kubectl apply --dry-run=server -f pod.yaml
# Error: pods "my-pod" is forbidden: violates PodSecurity "restricted:latest":
# allowPrivilegeEscalation != false (container "app")

# Vedi violazioni in audit mode (senza bloccare)
kubectl label namespace staging \
    pod-security.kubernetes.io/audit=restricted

# Poi controlla l'audit log:
# audit.k8s.io/level: RequestResponse
# annotations.pod-security.kubernetes.io/audit: would violate PodSecurity...
```

---

## SecurityContext — Hardening per Pod e Container

```yaml
spec:
  # ── Pod-level Security Context ────────────────────────────
  securityContext:
    runAsNonRoot: true          # fallisce se l'immagine usa root
    runAsUser: 1001
    runAsGroup: 1001
    fsGroup: 1001               # gruppo per i filesystem mount
    fsGroupChangePolicy: OnRootMismatch  # performance: cambia solo se necessario
    supplementalGroups: [2000]  # gruppi aggiuntivi
    sysctls:
      - name: net.core.somaxconn
        value: "65535"           # solo sysctls "safe" (non richiede privileged)
    seccompProfile:
      type: RuntimeDefault       # profilo seccomp del container runtime

  containers:
    - name: app
      # ── Container-level Security Context ─────────────────
      securityContext:
        allowPrivilegeEscalation: false   # no setuid/setgid
        readOnlyRootFilesystem: true      # filesystem root in sola lettura
        runAsNonRoot: true
        runAsUser: 1001
        capabilities:
          drop: ["ALL"]
          add: ["NET_BIND_SERVICE"]    # solo se necessario (porta < 1024)
        seccompProfile:
          type: Localhost
          localhostProfile: profiles/my-seccomp.json  # profilo custom
```

---

## RBAC — Controllo Accessi

```yaml
# ServiceAccount — identità per i pod
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-sa
  namespace: production
  annotations:
    # AWS IRSA (IAM Roles for Service Accounts)
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/api-role
    # GKE Workload Identity
    # iam.gke.io/gcp-service-account: api@project.iam.gserviceaccount.com

---
# Role — permessi namespace-scoped
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: api-role
  namespace: production
rules:
  - apiGroups: [""]           # core group
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
    resourceNames: ["api-config", "api-secrets"]  # solo risorse specifiche
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list"]

---
# ClusterRole — permessi cluster-scoped
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader
rules:
  - apiGroups: [""]
    resources: ["nodes", "nodes/metrics", "nodes/stats"]
    verbs: ["get", "list", "watch"]
  - nonResourceURLs: ["/metrics", "/healthz"]
    verbs: ["get"]

---
# RoleBinding — associa Role a ServiceAccount
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-sa-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: api-sa
    namespace: production
  # Oppure utente/gruppo:
  # - kind: User
  #   name: alice@company.com
  # - kind: Group
  #   name: system:masters  ← PERICOLO: cluster admin
roleRef:
  kind: Role
  name: api-role
  apiGroup: rbac.authorization.k8s.io
```

```bash
# Audit RBAC
kubectl auth can-i create pods --as=system:serviceaccount:production:api-sa
kubectl auth can-i list secrets --as=system:serviceaccount:production:api-sa -n production

# Tutte le permission di un soggetto
kubectl get rolebindings,clusterrolebindings -A -o json | \
    jq '.items[] | select(.subjects[].name=="api-sa") | {name:.metadata.name, role:.roleRef.name}'

# tool: rakkess (access matrix)
kubectl-access_matrix --sa production:api-sa
```

**Projected Service Account Tokens:**

```yaml
# Token con scadenza e audience limitate (Kubernetes 1.22+)
volumes:
  - name: sa-token
    projected:
      defaultMode: 0440
      sources:
        - serviceAccountToken:
            path: token
            expirationSeconds: 3600      # scade dopo 1h (kubelet lo rinnova auto)
            audience: "https://api.company.com"  # solo per questo audience

# Nel pod:
# /var/run/secrets/sa-token/token  ← token JWT con exp e aud limitati
# NON usare automountServiceAccountToken: true + il token default che non scade mai
```

---

## Workload Identity — IRSA e GKE WI

Il **Workload Identity** permette ai pod di assumere IAM role cloud senza credenziali hardcoded.

```
AWS IRSA (IAM Roles for Service Accounts)

  1. EKS cluster espone OIDC provider
  2. IAM Role trust policy: permette al SA specifico di assumerlo
  3. Pod usa il projected SA token per chiamare STS AssumeRoleWithWebIdentity
  4. Riceve credenziali AWS temporanee

  ServiceAccount annotation:
  eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/s3-reader-role

  IAM Trust Policy:
  {
    "Condition": {
      "StringEquals": {
        "oidc.eks.eu-west-1.amazonaws.com/id/xxx:sub":
          "system:serviceaccount:production:api-sa",
        "oidc.eks.eu-west-1.amazonaws.com/id/xxx:aud": "sts.amazonaws.com"
      }
    }
  }
```

```bash
# Setup IRSA su EKS
eksctl utils associate-iam-oidc-provider \
    --cluster my-cluster \
    --approve

eksctl create iamserviceaccount \
    --name api-sa \
    --namespace production \
    --cluster my-cluster \
    --role-name api-role \
    --attach-policy-arn arn:aws:iam::123456789:policy/api-policy \
    --approve
```

---

## Network Policy — Microsegmentazione

```yaml
# Default deny-all — baseline di sicurezza zero-trust
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}     # seleziona TUTTI i pod
  policyTypes: [Ingress, Egress]
  # nessuna regola = nega tutto

---
# Permette al pod api di ricevere traffico solo da api-gateway
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-ingress-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
          namespaceSelector:     # AND con podSelector (stesso block)
            matchLabels:
              kubernetes.io/metadata.name: ingress
      ports:
        - protocol: TCP
          port: 8080

    - from:
        - namespaceSelector:
            matchLabels:
              monitoring: "true"   # namespace monitoring per Prometheus
      ports:
        - protocol: TCP
          port: 9090               # metrics

---
# Egress: l'api può parlare solo con db e redis
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-egress-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes: [Egress]
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
    # DNS è necessario
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

---

## Audit Logging Kubernetes

```yaml
# /etc/kubernetes/audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # Non loggare GET su endpoints e healthz
  - level: None
    nonResourceURLs: ["/healthz", "/readyz", "/livez", "/metrics"]

  # Non loggare watch di events (rumoroso)
  - level: None
    resources:
      - group: ""
        resources: ["events"]

  # Secrets: log solo metadata (no body — contiene dati sensibili)
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]
      - group: "authentication.k8s.io"
        resources: ["tokenreviews"]

  # Accessi con privilege elevato: log completo (request + response body)
  - level: RequestResponse
    users:
      - "system:admin"
      - "kubernetes-admin"
    verbs: ["create", "update", "patch", "delete"]

  # Tutto il resto: log metadata
  - level: Metadata
    omitStages: [RequestReceived]
```

```bash
# Analisi audit log
# Trova chi ha acceduto ai secrets
jq -r 'select(.objectRef.resource=="secrets") |
    [.requestReceivedTimestamp, .user.username, .verb, .objectRef.namespace, .objectRef.name] |
    @csv' /var/log/kubernetes/audit.log

# Trova exec su container (possibile segnale di compromissione)
jq -r 'select(.verb=="create" and .objectRef.subresource=="exec") |
    [.requestReceivedTimestamp, .user.username, .objectRef.namespace, .objectRef.name, .responseStatus.code] |
    @csv' /var/log/kubernetes/audit.log
```

---

## Falco — Runtime Security

Vedi [security/compliance/audit-logging.md](../../security/compliance/audit-logging.md) per la configurazione completa di Falco. In sintesi per Kubernetes:

```yaml
# Falco DaemonSet con eBPF (no kernel module necessario)
# Helm values.yaml
driver:
  kind: ebpf              # ebpf | module | modern_ebpf

falcosidekick:
  enabled: true
  config:
    slack:
      webhookurl: https://hooks.slack.com/...
    alertmanager:
      hostport: http://alertmanager:9093

# Regole critiche per K8s:
# - Shell aperta in un container in produzione
# - Scrittura in /etc o /bin/
# - Lettura del token del ServiceAccount
# - Attach a un container esistente (kubectl exec)
# - Modifica ai file del kubelet
```

---

## Checklist Sicurezza Kubernetes

```yaml
# 10 hardening essenziali:

# 1. PSA restricted su tutti i namespace applicativi
# 2. NetworkPolicy default-deny-all + allowlist espliciti
# 3. RBAC: least privilege per ogni ServiceAccount
# 4. Non automountare il token SA (automountServiceAccountToken: false)
# 5. ResourceQuota su ogni namespace (anti-DoS)
# 6. Secrets crittografati in etcd (EncryptionConfiguration KMS)
# 7. Audit logging abilitato e analizzato
# 8. Falco o equivalente per runtime monitoring
# 9. Image scanning nel CI e continuous scanning con Trivy Operator
# 10. Admission controller: Gatekeeper o Kyverno per policy enforcement
```

---

## Riferimenti

- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Audit Logging](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)
- [Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
