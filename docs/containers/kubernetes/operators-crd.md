---
title: "Operators e CRD"
slug: operators-crd
category: containers
tags: [kubernetes, operators, crd, controller, kubebuilder, operator-sdk, reconcile, custom-resource]
search_keywords: [kubernetes operators, CRD custom resource definition, kubernetes controller pattern, kubebuilder tutorial, operator SDK, reconcile loop kubernetes, watch informer kubernetes, admission webhook, validating webhook, mutating webhook, controller-runtime, kubernetes finalizer, owner reference, controller-manager leader election]
parent: containers/kubernetes/_index
related: [containers/kubernetes/architettura, containers/openshift/operators-olm, containers/kubernetes/sicurezza]
official_docs: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Operators e CRD

## Il Pattern Operator

Un **Operator** è un controller che gestisce applicazioni complesse su Kubernetes, codificando la logica operativa umana in software. Estende le API di Kubernetes tramite **Custom Resource Definitions (CRD)**.

```
Operator Pattern — Esempio: DatabaseCluster Operator

  Senza Operator (manuale):
  Admin → crea StatefulSet, Service, ConfigMap, PVC, segreti
        → gestisce rolling upgrade (ordine, health check)
        → gestisce failover (promuovi replica → primary)
        → gestisce backup (cronjob personalizzati)
        → gestisce restore → ricostruisce replica da backup

  Con Operator:
  Admin → crea DatabaseCluster CR
  Operator Controller → osserva CR → gestisce tutto il resto

  DatabaseCluster CR:
  apiVersion: database.company.com/v1
  kind: DatabaseCluster
  metadata:
    name: production-db
  spec:
    replicas: 3
    version: "16.2"
    storage: 100Gi
    backup:
      schedule: "0 2 * * *"
      retention: 30d
```

---

## CRD — Custom Resource Definition

Una **CRD** registra un nuovo tipo di oggetto nell'API server.

```yaml
# CRD per un WebApplication custom
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapplications.apps.company.com   # <plural>.<group>
spec:
  group: apps.company.com
  names:
    kind: WebApplication
    plural: webapplications
    singular: webapplication
    shortNames: [webapp]
    categories: [all]       # incluso in "kubectl get all"
  scope: Namespaced         # Namespaced | Cluster
  versions:
    - name: v1
      served: true          # questa versione è accessibile via API
      storage: true         # questa versione è salvata in etcd (una sola)
      # Schema OpenAPI v3 (validazione)
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              required: [replicas, image]  # campi obbligatori
              properties:
                replicas:
                  type: integer
                  minimum: 1
                  maximum: 100
                image:
                  type: string
                  pattern: '^[a-zA-Z0-9][a-zA-Z0-9._/-]*:[a-zA-Z0-9._-]+$'
                resources:
                  type: object
                  properties:
                    cpu:
                      type: string
                      default: "100m"
                    memory:
                      type: string
                      default: "128Mi"
                autoscaling:
                  type: object
                  properties:
                    enabled:
                      type: boolean
                      default: false
                    minReplicas:
                      type: integer
                    maxReplicas:
                      type: integer
            status:
              type: object
              properties:
                phase:
                  type: string
                  enum: [Pending, Running, Degraded, Failed]
                readyReplicas:
                  type: integer
                conditions:
                  type: array
                  items:
                    type: object
                    properties:
                      type:
                        type: string
                      status:
                        type: string
                      lastTransitionTime:
                        type: string
                        format: date-time
                      reason:
                        type: string
                      message:
                        type: string
      # Subresources
      subresources:
        status: {}    # abilita /status subresource (aggiornamento status separato)
        scale:        # abilita /scale subresource (kubectl scale)
          specReplicasPath: .spec.replicas
          statusReplicasPath: .status.readyReplicas
      # Colonne aggiuntive in "kubectl get webapplications"
      additionalPrinterColumns:
        - name: Phase
          type: string
          jsonPath: .status.phase
        - name: Ready
          type: integer
          jsonPath: .status.readyReplicas
        - name: Age
          type: date
          jsonPath: .metadata.creationTimestamp
```

---

## Kubebuilder — Scaffolding del Controller

**Kubebuilder** è il framework raccomandato per sviluppare Operator in Go.

```bash
# Inizializza un progetto Operator
kubebuilder init \
    --domain company.com \
    --repo github.com/company/webapp-operator \
    --plugins go/v4

# Crea API (CRD + Controller)
kubebuilder create api \
    --group apps \
    --version v1 \
    --kind WebApplication

# Struttura generata:
# api/v1/webapplication_types.go        ← definizione dei tipi Go
# internal/controller/webapplication_controller.go  ← controller logic
# config/crd/                           ← manifest CRD generati
# config/rbac/                          ← ClusterRole per il controller
```

**Definizione dei tipi (Go):**

```go
// api/v1/webapplication_types.go

// WebApplicationSpec definisce lo stato desiderato
type WebApplicationSpec struct {
    // +kubebuilder:validation:Minimum=1
    // +kubebuilder:validation:Maximum=100
    Replicas int32  `json:"replicas"`

    // +kubebuilder:validation:Pattern=`^[a-zA-Z0-9][a-zA-Z0-9._/-]*:[a-zA-Z0-9._-]+$`
    Image    string `json:"image"`

    // +optional
    Resources corev1.ResourceRequirements `json:"resources,omitempty"`

    // +optional
    Autoscaling *AutoscalingSpec `json:"autoscaling,omitempty"`
}

type WebApplicationStatus struct {
    // +optional
    Phase string `json:"phase,omitempty"`

    // +optional
    ReadyReplicas int32 `json:"readyReplicas,omitempty"`

    // Standard Kubernetes conditions
    Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:subresource:scale:specpath=.spec.replicas,statuspath=.status.readyReplicas
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Ready",type=integer,JSONPath=`.status.readyReplicas`
type WebApplication struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    Spec   WebApplicationSpec   `json:"spec,omitempty"`
    Status WebApplicationStatus `json:"status,omitempty"`
}
```

---

## Il Reconcile Loop — Cuore del Controller

```go
// internal/controller/webapplication_controller.go

func (r *WebApplicationReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    log := log.FromContext(ctx)

    // ── 1. Fetch l'oggetto CR ─────────────────────────────────
    webapp := &appsv1.WebApplication{}
    if err := r.Get(ctx, req.NamespacedName, webapp); err != nil {
        if errors.IsNotFound(err) {
            // L'oggetto è stato cancellato — nessuna azione
            return ctrl.Result{}, nil
        }
        return ctrl.Result{}, err
    }

    // ── 2. Controlla il finalizer ─────────────────────────────
    // Il finalizer impedisce la cancellazione fino al cleanup
    finalizerName := "apps.company.com/finalizer"
    if webapp.DeletionTimestamp.IsZero() {
        // Non in cancellazione: aggiungi finalizer se mancante
        if !controllerutil.ContainsFinalizer(webapp, finalizerName) {
            controllerutil.AddFinalizer(webapp, finalizerName)
            return ctrl.Result{}, r.Update(ctx, webapp)
        }
    } else {
        // In cancellazione: esegui cleanup
        if controllerutil.ContainsFinalizer(webapp, finalizerName) {
            if err := r.cleanupExternalResources(ctx, webapp); err != nil {
                return ctrl.Result{}, err
            }
            controllerutil.RemoveFinalizer(webapp, finalizerName)
            return ctrl.Result{}, r.Update(ctx, webapp)
        }
        return ctrl.Result{}, nil
    }

    // ── 3. Reconcile Deployment ────────────────────────────────
    deployment := r.desiredDeployment(webapp)

    // SetControllerReference: setta l'owner reference
    // → quando webapp viene cancellato, deployment viene GC automaticamente
    if err := controllerutil.SetControllerReference(webapp, deployment, r.Scheme); err != nil {
        return ctrl.Result{}, err
    }

    // CreateOrUpdate: idempotente
    _, err := controllerutil.CreateOrUpdate(ctx, r.Client, deployment, func() error {
        // Aggiorna solo i campi che gestiamo noi
        deployment.Spec.Replicas = &webapp.Spec.Replicas
        deployment.Spec.Template.Spec.Containers[0].Image = webapp.Spec.Image
        return nil
    })
    if err != nil {
        return ctrl.Result{}, err
    }

    // ── 4. Aggiorna lo Status ─────────────────────────────────
    webapp.Status.Phase = "Running"
    webapp.Status.ReadyReplicas = deployment.Status.ReadyReplicas

    meta.SetStatusCondition(&webapp.Status.Conditions, metav1.Condition{
        Type:    "Ready",
        Status:  metav1.ConditionTrue,
        Reason:  "DeploymentReady",
        Message: fmt.Sprintf("%d/%d replicas ready", deployment.Status.ReadyReplicas, *deployment.Spec.Replicas),
    })

    if err := r.Status().Update(ctx, webapp); err != nil {
        return ctrl.Result{}, err
    }

    // ── 5. Ritorna il risultato ───────────────────────────────
    // ctrl.Result{}: successo, nessun requeue immediato
    // ctrl.Result{RequeueAfter: 30*time.Second}: requeue tra 30s
    // ctrl.Result{Requeue: true}: requeue immediatamente
    return ctrl.Result{}, nil
}

// ── Setup del Controller ──────────────────────────────────────
func (r *WebApplicationReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&appsv1.WebApplication{}).       // watch WebApplication
        Owns(&appsv1beta1.Deployment{}).     // watch Deployment (owned by webapp)
        Watches(
            &corev1.ConfigMap{},
            handler.EnqueueRequestsFromMapFunc(r.configMapToWebApp),
        ).                                   // watch ConfigMap rilevanti
        WithOptions(controller.Options{
            MaxConcurrentReconciles: 10,     // parallelismo
        }).
        Complete(r)
}
```

---

## Admission Webhooks

I **webhook** permettono di intercettare le richieste all'API server per validarle o modificarle.

```go
// Validating Webhook — valida prima di persistere in etcd
func (v *WebApplicationValidator) ValidateCreate(ctx context.Context, obj runtime.Object) (admission.Warnings, error) {
    webapp := obj.(*appsv1.WebApplication)

    var warnings admission.Warnings
    var allErrs field.ErrorList

    // Validazioni custom non esprimibili con OpenAPI schema
    if webapp.Spec.Autoscaling != nil {
        if webapp.Spec.Autoscaling.MaxReplicas < webapp.Spec.Replicas {
            allErrs = append(allErrs, field.Invalid(
                field.NewPath("spec").Child("autoscaling").Child("maxReplicas"),
                webapp.Spec.Autoscaling.MaxReplicas,
                "must be >= spec.replicas",
            ))
        }
    }

    // Warning (non bloccante)
    if webapp.Spec.Replicas < 3 {
        warnings = append(warnings, "Production workloads should have at least 3 replicas")
    }

    if len(allErrs) > 0 {
        return warnings, apierrors.NewInvalid(
            schema.GroupKind{Group: "apps.company.com", Kind: "WebApplication"},
            webapp.Name, allErrs,
        )
    }
    return warnings, nil
}

// Mutating Webhook — modifica l'oggetto prima della validazione
func (m *WebApplicationMutator) Default(ctx context.Context, obj runtime.Object) error {
    webapp := obj.(*appsv1.WebApplication)

    // Imposta valori di default non gestibili da CRD schema defaulting
    if webapp.Spec.Resources.Requests == nil {
        webapp.Spec.Resources.Requests = corev1.ResourceList{
            corev1.ResourceCPU:    resource.MustParse("100m"),
            corev1.ResourceMemory: resource.MustParse("128Mi"),
        }
    }

    // Aggiungi label standard
    if webapp.Labels == nil {
        webapp.Labels = make(map[string]string)
    }
    webapp.Labels["managed-by"] = "webapp-operator"

    return nil
}
```

**Manifest webhook:**

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionWebhook
metadata:
  name: webapp-validator.company.com
webhooks:
  - name: vwebapplication.kb.io
    clientConfig:
      service:
        name: webapp-operator-webhook-service
        namespace: webapp-operator-system
        path: /validate-apps-company-com-v1-webapplication
      caBundle: <base64-ca>   # gestito da cert-manager con annotation
    rules:
      - apiGroups: ["apps.company.com"]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["webapplications"]
    failurePolicy: Fail        # Fail | Ignore
    sideEffects: None
    admissionReviewVersions: ["v1"]
    timeoutSeconds: 10
```

---

## Best Practices per Operator Production-Grade

```
PATTERN ESSENZIALI:

1. IDEMPOTENZA — il reconcile deve essere sicuro se chiamato più volte
   CreateOrUpdate invece di Create/Update separati
   Sempre verifica lo stato attuale prima di agire

2. OWNER REFERENCES — per garbage collection automatica
   SetControllerReference per ogni risorsa child
   → eliminare la CR elimina automaticamente tutte le risorse figlio

3. FINALIZERS — per cleanup ordinato di risorse esterne
   Aggiungi finalizer alla creazione
   Rimuovi solo dopo aver completato il cleanup esterno

4. STATUS CONDITIONS — standard K8s per comunicare lo stato
   Usa meta.SetStatusCondition con types standard (Ready, Available, Progressing)
   Aggiorna sempre lo status, mai solo il spec

5. ERROR HANDLING — differenzia errori transient da permanenti
   Errori transient (network) → ritorna err (requeue con backoff)
   Errori permanenti (invalid config) → aggiorna status → non requeue

6. RATE LIMITING — WorkQueue con backoff esponenziale
   workqueue.NewItemExponentialFailureRateLimiter(5*time.Millisecond, 1000*time.Second)

7. METRICS — esponi metriche per observability
   controller-runtime espone già: reconcile_total, reconcile_errors_total, reconcile_duration
```

---

## Troubleshooting

### Scenario 1 — CRD non registrata / "no kind is registered"

**Sintomo:** `kubectl apply -f cr.yaml` ritorna `error: no kind "WebApplication" is registered for version "apps.company.com/v1"` oppure il controller logga `no kind is registered for the type`.

**Causa:** La CRD non è stata installata nel cluster prima del CR, oppure il controller è stato avviato prima che la CRD fosse established.

**Soluzione:** Installare prima la CRD e attendere che sia in stato `Established`.

```bash
# Installa CRD
kubectl apply -f config/crd/bases/

# Verifica che sia Established
kubectl wait crd/webapplications.apps.company.com \
    --for=condition=Established --timeout=30s

# Controlla lo stato dettagliato
kubectl get crd webapplications.apps.company.com -o jsonpath='{.status.conditions}'
```

---

### Scenario 2 — Reconcile loop in crash continuo / CrashLoopBackOff del controller

**Sintomo:** Il pod dell'operator è in `CrashLoopBackOff`. I log mostrano panic o errori di connessione all'API server al bootstrap.

**Causa:** Permessi RBAC insufficienti, certificati webhook non validi, o impossibilità di connettersi all'API server.

**Soluzione:**

```bash
# Verifica i log del controller
kubectl logs -n webapp-operator-system \
    deploy/webapp-operator-controller-manager \
    --previous

# Verifica i ClusterRole e i binding
kubectl get clusterrolebinding -l app=webapp-operator
kubectl auth can-i list webapplications \
    --as=system:serviceaccount:webapp-operator-system:webapp-operator-controller-manager

# Se usa webhook: verifica il Secret del certificato TLS
kubectl get secret -n webapp-operator-system webhook-server-cert
# Rigenera con cert-manager se scaduto
kubectl delete secret -n webapp-operator-system webhook-server-cert
```

---

### Scenario 3 — CR bloccata in Terminating (finalizer non rimosso)

**Sintomo:** `kubectl delete` di una CR rimane bloccato. `kubectl get <cr>` mostra `Terminating` da minuti/ore.

**Causa:** Il controller non riesce a completare il cleanup esterno (es. risorsa cloud non raggiungibile) e non rimuove il finalizer. Oppure il controller stesso è down.

**Soluzione:**

```bash
# Verifica il finalizer presente
kubectl get webapp production-db -o jsonpath='{.metadata.finalizers}'

# Opzione 1: correggi il problema a monte e lascia che il controller rimuova il finalizer
kubectl logs -n webapp-operator-system deploy/webapp-operator-controller-manager

# Opzione 2 (emergenza): rimuovi il finalizer manualmente
kubectl patch webapp production-db \
    -p '{"metadata":{"finalizers":[]}}' \
    --type=merge

# Attenzione: le risorse esterne non verranno pulite automaticamente
```

---

### Scenario 4 — Webhook rifiuta oggetti validi / timeout webhook

**Sintomo:** `kubectl apply` ritorna `Error from server (InternalError): Internal error occurred: failed calling webhook` oppure `context deadline exceeded`.

**Causa 1 — Timeout:** Il pod webhook non è raggiungibile (crashato, non schedulato) o risponde lentamente.
**Causa 2 — failurePolicy: Fail:** Il webhook è configurato con `failurePolicy: Fail` e il service è irraggiungibile.

**Soluzione:**

```bash
# Verifica stato del pod webhook
kubectl get pods -n webapp-operator-system
kubectl describe pod -n webapp-operator-system -l control-plane=controller-manager

# Verifica il ValidatingWebhookConfiguration
kubectl get validatingwebhookconfigurations webapp-validator.company.com -o yaml | \
    grep -A3 failurePolicy

# Bypass temporaneo di emergenza (solo in ambienti non-prod):
kubectl patch validatingwebhookconfiguration webapp-validator.company.com \
    --type=json \
    -p='[{"op":"replace","path":"/webhooks/0/failurePolicy","value":"Ignore"}]'

# Verifica connettività dal cluster al service webhook
kubectl run debug --image=curlimages/curl --restart=Never -- \
    curl -k https://webapp-operator-webhook-service.webapp-operator-system.svc/healthz
```

---

- [Kubernetes Operators](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Kubebuilder Book](https://book.kubebuilder.io/)
- [controller-runtime](https://pkg.go.dev/sigs.k8s.io/controller-runtime)
- [Operator SDK](https://sdk.operatorframework.io/docs/)
- [CRD versioning](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/)
- [Admission Webhooks](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
