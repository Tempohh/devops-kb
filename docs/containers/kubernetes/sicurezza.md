---
title: "Kubernetes Sicurezza"
slug: sicurezza
category: containers
tags: [kubernetes, sicurezza, psa, rbac, admission, seccomp, falco, networkpolicy, serviceaccount]
search_keywords: [kubernetes security hardening, Pod Security Admission, PSA kubernetes, kubernetes RBAC, SecurityContext pod kubernetes, seccomp kubernetes, kubernetes admission controller, OPA Gatekeeper kubernetes, Kyverno, Falco kubernetes runtime security, kubernetes audit logging, workload identity kubernetes, service account token projection]
parent: containers/kubernetes/_index
related: [security/autenticazione/mtls-spiffe, security/autorizzazione/opa, security/supply-chain/admission-control, containers/kubernetes/workloads]
official_docs: https://kubernetes.io/docs/concepts/security/
status: reviewed
difficulty: expert
last_updated: 2026-10-04
last_verified: 2026-10-04
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

  Ogni layer difende indipendentemente (defense in depth):
  la compromissione di un layer non deve bastare a compromettere gli altri.
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
    # Pin della versione delle regole del profilo (default: latest).
    # Pinnare evita che un upgrade del cluster inasprisca il profilo di colpo.
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
            runAsNonRoot: true (e nessun runAsUser: 0)
            seccompProfile: RuntimeDefault o Localhost
            capabilities.drop: ["ALL"]
  Ammette: add solo di NET_BIND_SERVICE
  Blocca: volume types limitati (solo configMap, csi, downwardAPI,
          emptyDir, ephemeral, persistentVolumeClaim, projected, secret)
```

!!! note "Eccezioni PSA"
    PSA non è un policy engine: ha solo 3 profili fissi, nessuna eccezione per singolo pod.
    Esenzioni per utenti, namespace o RuntimeClass si configurano a livello di API server
    (`AdmissionConfiguration` del plugin `PodSecurity`). Per regole custom serve un
    admission controller (vedi sezione Admission e ValidatingAdmissionPolicy).

```bash
# Testa se un pod viola il profilo senza applicarlo
kubectl apply --dry-run=server -f pod.yaml
# Error: pods "my-pod" is forbidden: violates PodSecurity "restricted:latest":
# allowPrivilegeEscalation != false (container "app")

# Vedi violazioni in audit mode (senza bloccare)
kubectl label namespace staging \
    pod-security.kubernetes.io/audit=restricted

# Poi controlla l'audit log dell'API server: l'evento di create del pod porta
# l'annotation  pod-security.kubernetes.io/audit-violations: "would violate PodSecurity ..."

# Prima di abilitare enforce su un namespace esistente: simula l'impatto
# sui pod già in esecuzione (warning per ogni pod non conforme, nessuna modifica)
kubectl label --dry-run=server --overwrite ns --all \
    pod-security.kubernetes.io/enforce=restricted
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
      - name: net.ipv4.ip_local_port_range
        value: "1024 65535"      # sysctl "safe": ammesso di default.
                                 # Gli "unsafe" (es. net.core.somaxconn) richiedono
                                 # kubelet --allowed-unsafe-sysctls e sono bloccati da PSA baseline
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
    verbs: ["get"]
    resourceNames: ["api-config", "api-secrets"]  # solo risorse specifiche
    # NB: "list"/"watch" con resourceNames funziona solo se il client filtra con
    # fieldSelector metadata.name=<nome>; un list generico verrebbe negato
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

# plugin krew: rakkess (access matrix)
kubectl access-matrix --sa production:api-sa
```

**Projected Service Account Tokens:**

Dal 1.22 i token SA montati di default nei pod sono già *bound* (JWT legati a pod e SA,
scadenza 1h, rinnovati dal kubelet). Dal 1.24 non vengono più creati Secret `kubernetes.io/service-account-token`
automatici: quelli (non scadono mai) esistono solo se creati a mano o ereditati da cluster vecchi.
Il volume `projected` serve per ottenere un token con **audience dedicata** verso un servizio terzo.

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
# (path dipende dal volumeMount, es. mountPath: /var/run/secrets/sa-token)
# /var/run/secrets/sa-token/token  ← token JWT con exp e aud limitati
# expirationSeconds minimo: 600. Il kubelet rinnova il token al ~80% del TTL.
# Se il pod non parla con l'API server: automountServiceAccountToken: false
# Elimina i Secret di tipo service-account-token legacy: sono credenziali senza scadenza.
```

---

## Workload Identity — IRSA, Pod Identity e GKE WI

Il **Workload Identity** permette ai pod di assumere IAM role cloud senza credenziali hardcoded.
Il pod presenta il proprio token SA (OIDC JWT firmato dal cluster); il cloud IAM si fida
dell'issuer del cluster e lo scambia con credenziali temporanee legate a quel SA.

| Cloud | Meccanismo | Note |
|---|---|---|
| AWS | **IRSA** (OIDC provider per cluster + trust policy per SA) | Richiede un OIDC provider IAM per ogni cluster; limite sulla dimensione della trust policy |
| AWS | **EKS Pod Identity** (add-on agent + `aws eks create-pod-identity-association`) | Alternativa più recente: nessun OIDC provider, trust policy unica verso `pods.eks.amazonaws.com`, niente annotation sul SA |
| GCP | **Workload Identity Federation for GKE** | Si può dare accesso IAM direttamente al principal `principal://...svc.id.goog/subject/ns/<ns>/sa/<sa>`; l'annotation `iam.gke.io/gcp-service-account` serve solo per l'impersonation di un GSA |
| Azure | **Microsoft Entra Workload Identity** | Federated credential sul managed identity + label `azure.workload.identity/use` |

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
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::123456789:oidc-provider/oidc.eks.eu-west-1.amazonaws.com/id/xxx" },
    "Action": "sts:AssumeRoleWithWebIdentity",
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

!!! warning "Serve un CNI che le implementa"
    Le NetworkPolicy sono solo oggetti API: le applica il CNI plugin. Con CNI che non le
    supportano (es. Flannel puro) `kubectl apply` ha successo ma **nulla viene filtrato**,
    senza alcun errore. Usare Calico, Cilium o equivalente e verificare con un test reale.

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

Le regole sono valutate **in ordine e vince la prima che corrisponde**: le eccezioni
specifiche (`None`, `Metadata` sui secrets) vanno sopra quelle generiche. L'API server
va avviato con `--audit-policy-file` e `--audit-log-path` (o `--audit-webhook-config-file`);
sui cluster managed (EKS/GKE/AKS) l'audit log si abilita dal provider, non da questo file.

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
# Nessun filtro su .verb: con il transport WebSocket di kubectl exec il verbo può essere "get" invece di "create"
jq -r 'select(.objectRef.subresource=="exec") |
    [.requestReceivedTimestamp, .user.username, .objectRef.namespace, .objectRef.name, .responseStatus.code] |
    @csv' /var/log/kubernetes/audit.log
```

---

## Falco — Runtime Security

Vedi [security/compliance/audit-logging.md](../../security/compliance/audit-logging.md) per la configurazione completa di Falco. In sintesi per Kubernetes:

```yaml
# Falco DaemonSet con modern eBPF (CO-RE: nessun kernel module né compilazione probe)
# Helm values.yaml
driver:
  kind: modern_ebpf       # modern_ebpf | kmod | ebpf (probe legacy, deprecato) | auto

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
# 6. Secrets crittografati in etcd (EncryptionConfiguration con provider KMS v2;
#    KMS v1 è deprecato)
# 7. Audit logging abilitato e analizzato
# 8. Falco o equivalente per runtime monitoring
# 9. Image scanning nel CI e continuous scanning con Trivy Operator
# 10. Policy enforcement: ValidatingAdmissionPolicy (nativa, CEL) per regole semplici,
#     Gatekeeper o Kyverno per regole complesse/mutation/generation
```

### Admission e ValidatingAdmissionPolicy

PSA copre solo i profili standard. Per regole custom (registry ammessi, label obbligatorie,
niente tag `latest`) i **ValidatingAdmissionPolicy** (VAP, GA dal 1.30) valutano espressioni CEL
direttamente nell'API server: nessun webhook esterno, quindi nessun componente in più da
mantenere né latenza di rete nel path di admission. Gatekeeper e Kyverno restano la scelta
quando servono mutation, generazione di risorse, o logica non esprimibile in CEL.

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: no-latest-tag
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
      - apiGroups: ["apps"]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["deployments"]
  validations:
    - expression: "object.spec.template.spec.containers.all(c, !c.image.endsWith(':latest'))"
      message: "Tag :latest non ammesso"
---
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicyBinding
metadata:
  name: no-latest-tag-prod
spec:
  policyName: no-latest-tag
  validationActions: [Deny]      # Warn | Audit per un rollout graduale
  matchResources:
    namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: production
```

Approfondimento: [Admission Control](../../security/supply-chain/admission-control.md), [OPA](../../security/autorizzazione/opa.md).

---

## Troubleshooting

### Scenario 1 — Pod rifiutato da PSA con violazione "restricted"

**Sintomo:** `kubectl apply` restituisce `Error from server (Forbidden): pods "my-pod" is forbidden: violates PodSecurity "restricted:latest"`.

**Causa:** Il namespace ha `pod-security.kubernetes.io/enforce: restricted` e il pod manca di `allowPrivilegeEscalation: false`, `runAsNonRoot: true` o `seccompProfile`.

**Soluzione:** Aggiungere i campi mancanti nel `securityContext` del container, oppure usare la modalità `warn`/`audit` per identificare le violazioni senza bloccare.

```bash
# Identifica cosa viola il profilo senza applicare
kubectl apply --dry-run=server -f pod.yaml

# Passa temporaneamente a warn per vedere le violazioni senza blocco
kubectl label namespace production \
    pod-security.kubernetes.io/enforce=baseline \
    pod-security.kubernetes.io/warn=restricted --overwrite

# Verifica cosa manca nel SecurityContext del container
kubectl explain pod.spec.containers.securityContext
```

---

### Scenario 2 — ServiceAccount con accesso negato a risorse Kubernetes

**Sintomo:** Il pod riceve `403 Forbidden` quando chiama l'API server (es. il controller non riesce a listare i ConfigMap).

**Causa:** Il `RoleBinding` manca o è legato al namespace sbagliato; oppure il pod usa il ServiceAccount `default` che non ha permessi.

**Soluzione:** Verificare che esista un `RoleBinding` corretto che associ il SA al `Role` giusto nel namespace del pod.

```bash
# Verifica se il SA può eseguire l'azione richiesta
kubectl auth can-i list configmaps \
    --as=system:serviceaccount:production:api-sa \
    -n production

# Lista tutti i RoleBinding per il SA
kubectl get rolebindings -n production -o json | \
    jq '.items[] | select(.subjects[]? | .kind=="ServiceAccount" and .name=="api-sa")'

# Controlla se il pod monta il token SA corretto
kubectl get pod <pod-name> -n production -o jsonpath='{.spec.serviceAccountName}'
```

---

### Scenario 3 — NetworkPolicy blocca traffico inatteso

**Sintomo:** Il servizio smette di rispondere dopo l'applicazione di una NetworkPolicy; le chiamate tra pod vanno in timeout.

**Causa:** La policy `default-deny-all` blocca tutto il traffico, ma mancano le regole allow esplicite per i percorsi necessari (DNS, metrics, database).

**Soluzione:** Verificare la connettività tra pod e aggiungere le regole `ingress`/`egress` mancanti. Il traffico DNS sulla porta 53 verso `kube-dns` è spesso dimenticato.

```bash
# Verifica quali NetworkPolicy si applicano a un pod
kubectl get networkpolicies -n production
kubectl describe networkpolicy default-deny-all -n production

# Test connettività con un pod temporaneo di debug
kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never \
    -n production -- curl -v http://api:8080

# Osserva i drop: Cilium li espone via Hubble; Calico NON logga i drop di default
# (serve una regola con action: Log nella policy Calico)
hubble observe --namespace production --verdict DROPPED --last 50

# NB: se il namespace ha PSA restricted, questo pod di debug (netshoot, root) viene rifiutato:
# usa un namespace baseline/di test o un'immagine conforme

# Verifica che DNS sia raggiungibile
kubectl run dnstest --image=busybox --rm -it --restart=Never \
    -n production -- nslookup kubernetes.default
```

---

### Scenario 4 — Token IRSA non valido: credenziali AWS negate al pod

**Sintomo:** Il pod su EKS riceve `InvalidIdentityToken` o `AccessDenied` quando chiama AWS SDK, nonostante la ServiceAccount abbia l'annotation IRSA corretta.

**Causa:** L'OIDC provider non è stato associato al cluster, oppure la trust policy dell'IAM Role non corrisponde esattamente al namespace e al nome del ServiceAccount.

**Soluzione:** Verificare che l'OIDC provider sia registrato in IAM e che la trust policy usi i valori esatti (case-sensitive) di namespace e SA.

```bash
# Verifica che l'OIDC provider sia associato al cluster
aws eks describe-cluster --name my-cluster \
    --query "cluster.identity.oidc.issuer" --output text

# Controlla se l'OIDC provider è registrato in IAM
aws iam list-open-id-connect-providers

# Verifica il token proiettato nel pod
kubectl exec -n production <pod-name> -- \
    cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token | \
    cut -d'.' -f2 | tr '_-' '/+' | base64 -d 2>/dev/null | jq '{sub, aud, exp}'
# (il JWT è base64url: tr converte l'alfabeto; se base64 lamenta il padding aggiungi "==")

# Controlla le variabili d'ambiente AWS impostate da IRSA
kubectl exec -n production <pod-name> -- env | grep -E 'AWS_|ROLE'
```

---

## Riferimenti

- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Audit Logging](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)
- [Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [ValidatingAdmissionPolicy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/)
- [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
