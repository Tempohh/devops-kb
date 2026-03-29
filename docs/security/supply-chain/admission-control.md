---
title: "Admission Control — OPA Gatekeeper e Kyverno"
slug: admission-control
category: security
tags: [admission-control, gatekeeper, kyverno, pod-security, kubernetes-policy, opa]
search_keywords: [kubernetes admission control, opa gatekeeper, kyverno policy, pod security standards, admission webhook, validating webhook, mutating webhook, kubernetes policy engine, constraint template gatekeeper, kyverno clusterpolicy, pod security admission, pod security policy deprecated, privileged container policy, resource limits policy, image registry policy, cosign admission policy, sigstore policy controller, kubernetes security policy, runtime security, seccomp apparmor kubernetes, capabilities kubernetes, read-only root filesystem, non-root user kubernetes, network policy enforcement, namespace label policy, label policy kubernetes]
parent: security/supply-chain/_index
related: [security/supply-chain/image-scanning, security/supply-chain/sbom-cosign, security/autorizzazione/opa]
official_docs: https://kyverno.io/docs/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Admission Control — OPA Gatekeeper e Kyverno

## Panoramica

Un **Admission Controller** è un plugin Kubernetes che intercetta le richieste all'API server *prima* che gli oggetti vengano persistiti in etcd. È il punto di enforcement delle policy di sicurezza: può **validare** (accettare/rifiutare) o **mutare** (modificare automaticamente) le risorse prima della creazione.

```
kubectl apply / Helm deploy / Operator
        │
        │ request
        ▼
   kube-apiserver
        │
        │ (1) Authentication: chi è questa richiesta?
        │ (2) Authorization (RBAC): è permessa?
        │ (3) Admission Controllers
        │        ├── Mutating Webhooks   → modificano la risorsa
        │        │     es: inietta sidecar, aggiunge label, imposta defaults
        │        └── Validating Webhooks → accettano o rifiutano
        │              es: blocca immagini non firmate, no privileged, deve avere limits
        │
        │ (se tutti i webhook approvano)
        ▼
      etcd (persistenza) → Kubernetes reconcile loop
```

Esistono due sistemi di policy dominanti: **OPA Gatekeeper** (basato su Rego) e **Kyverno** (YAML-native). Non sono mutualmente esclusivi ma in pratica si sceglie uno dei due.

---

## Pod Security Standards (Built-in)

Prima di discutere Gatekeeper e Kyverno, Kubernetes ha **Pod Security Standards** (PSS) built-in dal v1.25 (sostituisce i deprecati Pod Security Policies):

```yaml
# Label sul namespace per applicare PSS
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # Livelli: privileged / baseline / restricted
    # Modalità: enforce (blocca) / audit (logga) / warn (avvisa)
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: v1.29
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Livelli PSS:**

| Livello | Cosa permette | Uso |
|---------|--------------|-----|
| `privileged` | Tutto | Solo system namespaces (kube-system) |
| `baseline` | No privileged, no hostNetwork/PID | Workload generici che non richiedono restrizioni |
| `restricted` | Richiede non-root, no capabilities, read-only root FS, seccomp | ✅ Standard per applicazioni enterprise |

---

## OPA Gatekeeper

[OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/) porta la potenza di Rego nel Kubernetes admission control tramite due CRD: **ConstraintTemplate** (definisce la policy in Rego) e **Constraint** (applica la policy a risorse specifiche).

```bash
# Installa Gatekeeper
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm install gatekeeper gatekeeper/gatekeeper \
  --namespace gatekeeper-system \
  --create-namespace
```

### Esempio: Blocca Immagini da Registry Non Autorizzati

```yaml
# ConstraintTemplate: definisce la policy in Rego
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8sallowedrepos
spec:
  crd:
    spec:
      names:
        kind: K8sAllowedRepos
      validation:
        openAPIV3Schema:
          type: object
          properties:
            repos:
              type: array
              items:
                type: string
  targets:
  - target: admission.k8s.gatekeeper.sh
    rego: |
      package k8sallowedrepos

      violation[{"msg": msg}] {
        container := input.review.object.spec.containers[_]
        not starts_with_allowed(container.image)
        msg := sprintf(
          "Container '%v' usa immagine '%v' da registry non autorizzato. Consentiti: %v",
          [container.name, container.image, input.parameters.repos]
        )
      }

      # Controlla anche initContainers ed ephemeralContainers
      violation[{"msg": msg}] {
        container := input.review.object.spec.initContainers[_]
        not starts_with_allowed(container.image)
        msg := sprintf("initContainer '%v' usa registry non autorizzato", [container.name])
      }

      starts_with_allowed(image) {
        repo := input.parameters.repos[_]
        startswith(image, repo)
      }

---
# Constraint: applica la policy ai namespace di produzione
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sAllowedRepos
metadata:
  name: allowed-repos
spec:
  enforcementAction: deny    # deny | dryrun | warn
  match:
    namespaces:
    - production
    - staging
    kinds:
    - apiGroups: [""]
      kinds: ["Pod"]
  parameters:
    repos:
    - "my-registry.azurecr.io/"
    - "ghcr.io/myorg/"
    - "gcr.io/my-project/"
```

### Esempio: Resource Limits Obbligatori

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredresources
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredResources
  targets:
  - target: admission.k8s.gatekeeper.sh
    rego: |
      package k8srequiredresources

      violation[{"msg": msg}] {
        container := input.review.object.spec.containers[_]
        not container.resources.limits.memory
        msg := sprintf("Container '%v' deve avere memory limit definito", [container.name])
      }

      violation[{"msg": msg}] {
        container := input.review.object.spec.containers[_]
        not container.resources.limits.cpu
        msg := sprintf("Container '%v' deve avere CPU limit definito", [container.name])
      }

      violation[{"msg": msg}] {
        container := input.review.object.spec.containers[_]
        not container.resources.requests.memory
        msg := sprintf("Container '%v' deve avere memory request definita", [container.name])
      }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredResources
metadata:
  name: required-resources
spec:
  enforcementAction: deny
  match:
    namespaces: ["production", "staging"]
    kinds:
    - apiGroups: ["apps"]
      kinds: ["Deployment", "StatefulSet", "DaemonSet"]
```

---

## Kyverno — Policy YAML-Native

[Kyverno](https://kyverno.io/) ha una UX diversa da Gatekeeper: le policy sono scritte in YAML, senza un linguaggio di programmazione. È più accessibile per chi non conosce Rego ma meno flessibile per logiche complesse.

```bash
# Installa Kyverno
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set admissionController.replicas=3  # HA: 3 repliche per produzione
```

### Validazione — Blocca Container Privileged

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged-containers
  annotations:
    policies.kyverno.io/title: Disallow Privileged Containers
    policies.kyverno.io/severity: critical
    policies.kyverno.io/description: >
      I container privileged hanno accesso completo all'host.
      Non devono mai girare in ambienti di produzione.
spec:
  validationFailureAction: Enforce    # Enforce | Audit
  background: true                     # Applica anche alle risorse esistenti (audit)

  rules:
  - name: check-privileged
    match:
      any:
      - resources:
          kinds: ["Pod"]
          namespaces: ["production", "staging"]
    validate:
      message: "Container privileged non ammessi in produzione"
      pattern:
        spec:
          containers:
          - =(securityContext):              # = significa "se presente"
              =(privileged): "false | null"  # false o non impostato
          =(initContainers):
          - =(securityContext):
              =(privileged): "false | null"
```

### Mutazione — Aggiunge Automaticamente Security Context

```yaml
# Kyverno può MUTARE le risorse — aggiunge automaticamente security context
# se mancante, invece di bloccare il deploy
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-security-context
spec:
  rules:
  - name: add-security-context
    match:
      any:
      - resources:
          kinds: ["Pod"]
          namespaces: ["production"]
    mutate:
      patchStrategicMerge:
        spec:
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            fsGroup: 1000
            seccompProfile:
              type: RuntimeDefault    # Profilo seccomp di default
          containers:
          - (name): "*"              # Applica a tutti i container
            securityContext:
              allowPrivilegeEscalation: false
              readOnlyRootFilesystem: true
              capabilities:
                drop:
                - ALL
```

### Verifica Firma Cosign (Sigstore Policy Controller)

```yaml
# Kyverno — verifica che l'immagine sia firmata con cosign
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature
spec:
  validationFailureAction: Enforce
  background: false    # Non applicare retroattivamente (verifica solo al momento del deploy)

  rules:
  - name: verify-cosign-signature
    match:
      any:
      - resources:
          kinds: ["Pod"]
          namespaces: ["production"]
    verifyImages:
    - imageReferences:
      - "ghcr.io/myorg/*"    # Verifica solo immagini del nostro registry
      attestors:
      - count: 1             # Almeno 1 attestore deve verificare
        entries:
        - keyless:
            subject: "https://github.com/myorg/myrepo/.github/workflows/build.yml@refs/heads/main"
            issuer: "https://token.actions.githubusercontent.com"
            rekor:
              url: "https://rekor.sigstore.dev"
      # Verifica anche che l'immagine abbia un'attestazione SBOM
      attestations:
      - predicateType: https://cyclonedx.org/bom
        conditions:
        - all:
          - key: "{{ components | length(@) }}"
            operator: GreaterThan
            value: "0"
```

---

## Kyverno Policy Library

Kyverno mantiene una [libreria ufficiale di policy](https://kyverno.io/policies/) pronte all'uso:

```bash
# Applica policy dalla libreria ufficiale
# Best Practices per la sicurezza
kubectl apply -f https://kyverno.io/policies/pod-security/baseline/disallow-host-namespaces/disallow-host-namespaces.yaml
kubectl apply -f https://kyverno.io/policies/pod-security/restricted/require-run-as-nonroot/require-run-as-nonroot.yaml
kubectl apply -f https://kyverno.io/policies/pod-security/restricted/disallow-privilege-escalation/disallow-privilege-escalation.yaml
kubectl apply -f https://kyverno.io/policies/pod-security/restricted/require-ro-rootfs/require-ro-rootfs.yaml
kubectl apply -f https://kyverno.io/policies/best-practices/require-labels/require-labels.yaml
kubectl apply -f https://kyverno.io/policies/best-practices/require-requests-limits/require-requests-limits.yaml
```

---

## Testing delle Policy

```bash
# Kyverno CLI — testa policy localmente prima di applicarle
kyverno test ./policies/

# Output
# Executing require-requests-limits...
# pass: 3 fail: 0 warn: 0 error: 0 skip: 0

# Test con un manifest specifico
cat << 'EOF' > test-pod.yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: test
    image: nginx
    # MANCANO resources.limits
EOF

kyverno apply ./policies/require-resources.yaml \
  --resource test-pod.yaml
# → FAILED: Container 'test' deve avere memory limit definito
```

---

## Audit Mode — Deploy Graduale

Prima di impostare `Enforce`, usare sempre `Audit` per capire l'impatto:

```bash
# Kyverno audit: visualizza le violazioni senza bloccare
kubectl get policyreport -A
kubectl get clusterpolicyreport

# Report dettagliato
kubectl describe policyreport polr-ns-production -n production

# Gatekeeper audit
kubectl get constraint -A
kubectl describe k8srequiredresources required-resources
# Spec:
#   Total Violations: 12
# ...lista dei pod violating
```

---

## Best Practices

- **Inizia in Audit, poi Enforce**: applicare Enforce senza audit prima può bloccare workload esistenti e causare outage. Sempre audit per almeno una settimana
- **Politica di esclusione esplicita**: alcuni namespace di sistema (kube-system, cert-manager, vault) devono essere esclusi o avere policy più permissive — definire le eccezioni esplicitamente, non implicitamente
- **Admission controller in HA**: i webhook di ammissione sono nel critical path — se il controller non risponde, il comportamento dipende da `failurePolicy` (Fail = blocca tutto, Ignore = permette tutto). In produzione usare 3 repliche e `failurePolicy: Fail`
- **Policy as code con GitOps**: le policy devono stare in Git — PR review obbligatoria per qualsiasi modifica a una policy di sicurezza
- **Non duplicare Pod Security Standards**: PSS built-in copre i casi base (privileged, host namespaces) — Gatekeeper/Kyverno per policy custom specifiche del tuo contesto

## Troubleshooting

### Scenario 1 — Pod bloccato con errore generico dall'admission webhook

**Sintomo:** `kubectl apply` fallisce con `Error from server: error when creating "pod.yaml": admission webhook "validate.kyverno.svc" denied the request`

**Causa:** Una policy Kyverno in `Enforce` mode ha rifiutato il Pod, ma il messaggio non indica quale regola ha violato.

**Soluzione:** Recuperare il policy report del namespace o descrivere la policy violata.

```bash
# Visualizza tutte le violazioni nel namespace
kubectl get policyreport -n production -o yaml | grep -A5 "result: fail"

# Identifica la policy specifica
kubectl get clusterpolicy -o wide
# Colonna "READY" deve essere True, "BACKGROUND" mostra se audit attivo

# Testa il manifest in dry-run contro tutte le policy attive
kyverno apply . --resource mypod.yaml

# Per Gatekeeper: elenca tutte le constraint violations
kubectl get constraint -A
kubectl describe <constraint-kind> <constraint-name>
```

---

### Scenario 2 — Admission webhook timeout: API server non raggiunge il controller

**Sintomo:** `kubectl apply` timeout dopo 30s con `context deadline exceeded`; eventi nel namespace mostrano `failed calling webhook`

**Causa:** Il pod Kyverno/Gatekeeper non è healthy, oppure il `failurePolicy` è `Fail` e il webhook non risponde.

**Soluzione:** Verificare lo stato del controller e, se necessario, impostare `failurePolicy: Ignore` temporaneamente.

```bash
# Stato pod Kyverno
kubectl get pods -n kyverno
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller --tail=50

# Stato pod Gatekeeper
kubectl get pods -n gatekeeper-system
kubectl logs -n gatekeeper-system -l control-plane=controller-manager --tail=50

# Visualizza webhook configuration (failurePolicy)
kubectl get validatingwebhookconfiguration kyverno-resource-validating-webhook-cfg -o yaml | grep failurePolicy

# Emergenza: disabilita temporaneamente il webhook (SOLO in cluster di sviluppo!)
# In produzione: scalare a 3 repliche invece di disabilitare
kubectl scale deployment kyverno-admission-controller -n kyverno --replicas=3
```

---

### Scenario 3 — Policy report non si aggiorna / background scan bloccato

**Sintomo:** `kubectl get policyreport -A` restituisce risultati vecchi o vuoti; le violazioni esistenti non appaiono nel report.

**Causa:** Il background controller di Kyverno non è attivo o ha permessi RBAC insufficienti per leggere le risorse del cluster.

**Soluzione:** Verificare il background controller e i suoi log.

```bash
# Verifica che il background controller sia running
kubectl get pods -n kyverno -l app.kubernetes.io/component=background-controller

# Log del background controller
kubectl logs -n kyverno -l app.kubernetes.io/component=background-controller --tail=100 | grep -E "ERROR|WARN"

# Forza ricreazione dei policy report (elimina i vecchi, vengono rigenerati)
kubectl delete policyreport -A --all
kubectl delete clusterpolicyreport --all

# Verifica RBAC del service account Kyverno
kubectl auth can-i list pods --as=system:serviceaccount:kyverno:kyverno-background-controller -A
```

---

### Scenario 4 — Gatekeeper ConstraintTemplate in stato "Not Ready"

**Sintomo:** `kubectl get constrainttemplate` mostra `READY: False`; le Constraint associate non bloccano le violazioni.

**Causa:** Errore di sintassi nel codice Rego, oppure il CRD generato dal template è in conflitto con una versione precedente.

**Soluzione:** Descrivere il template per vedere l'errore Rego e, se necessario, cancellare e riapplicare.

```bash
# Visualizza l'errore di compilazione Rego
kubectl describe constrainttemplate k8sallowedrepos
# Cercare nel campo "Status.By Pod.Errors" il messaggio di errore

# Testa la sintassi Rego localmente prima di applicare
opa check ./rego_policy.rego

# Se il CRD è corrotto, ricrearlo
kubectl delete constrainttemplate k8sallowedrepos
kubectl apply -f constraint-template.yaml

# Verifica che la Constraint referenzi il template corretto
kubectl get k8sallowedrepos -o yaml | grep -A3 "spec:"

# Debug audit Gatekeeper — forza un ciclo di audit
kubectl annotate configs.config.gatekeeper.sh config -n gatekeeper-system force-audit="$(date +%s)"
```

---

## Riferimenti

- [Kyverno Documentation](https://kyverno.io/docs/)
- [OPA Gatekeeper Documentation](https://open-policy-agent.github.io/gatekeeper/)
- [Sigstore Policy Controller](https://docs.sigstore.dev/policy-controller/overview/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kyverno Policy Library](https://kyverno.io/policies/)
