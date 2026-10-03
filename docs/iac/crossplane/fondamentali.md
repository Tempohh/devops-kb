---
title: "Crossplane — Fondamentali"
slug: fondamentali
category: iac
tags: [crossplane, iac, kubernetes, gitops, platform-engineering, crd, control-loop, cloud]
search_keywords: [crossplane, kubernetes-native iac, terraform via kubernetes, control loop, reconciliation, managed resource, mr, composite resource, xr, composition, xrd, compositeresourcedefinition, provider aws, provider-family, self-service infrastructure, platform engineering, crossplane vs terraform, kubectl apply infra, crd based provisioning, claim namespaced, upbound]
parent: iac/crossplane/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management, containers/kubernetes/operators-crd, ci-cd/gitops/argocd, iac/ansible/roles-collections]
official_docs: https://docs.crossplane.io/
status: needs-review
difficulty: advanced
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# Crossplane — Fondamentali

!!! note "Versione: esempi in stile Crossplane v2 (v2.4.x) e provider-upjet-aws v2.x"
    Gli esempi usano il modello v2: XR **namespaced** (`scope: Namespaced` nella XRD `apiextensions.crossplane.io/v2`), Composition solo `mode: Pipeline` con `function-patch-and-transform`, MR namespaced dei provider v2 (`*.aws.m.upbound.io`) e `managementPolicies`. Versioni di riferimento verificate a ottobre 2026: Crossplane `v2.4.2`, `provider-aws-*` `v2.8.1`, `function-patch-and-transform` `v0.8.2`.

!!! warning "Migrazione v1 → v2"
    Rimossi in v2: patch-and-transform nativo (`mode: Resources`), `ControllerConfig`, external secret store, connection details dell'XR (`connectionDetails`, `publishConnectionDetailsTo`) e registry di default (i package vanno indicati con path completo, es. `xpkg.crossplane.io/crossplane-contrib/...`). I **Claim** esistono solo per XRD legacy (`apiextensions.crossplane.io/v1`, `scope: LegacyCluster`): in v2 lo sviluppatore crea direttamente l'XR nel proprio namespace. Le MR cluster-scoped `*.aws.upbound.io` restano per compatibilità, ma le nuove vanno scritte con le varianti namespaced `*.aws.m.upbound.io`. La maggior parte dei setup v1 che non usano le feature rimosse si aggiorna senza modifiche.

## Panoramica

Crossplane è un progetto CNCF che estende Kubernetes per gestire infrastruttura cloud (VM, database, reti, bucket, cluster) usando le stesse primitive con cui Kubernetes gestisce pod e deployment: **CRD (Custom Resource Definition)** e **controller in control loop**. Invece di eseguire un CLI esterno (`terraform apply`) che legge/scrive uno state file, Crossplane installa provider come operatori nel cluster: ogni risorsa cloud diventa un oggetto Kubernetes (`kubectl get`, `kubectl apply`, `kubectl describe` funzionano su un bucket S3 esattamente come su un pod).

Il valore distintivo è il **self-service infrastructure via Kubernetes API**: un platform team definisce astrazioni (es. "Database", "Cluster") tramite Composition/XRD, e gli sviluppatori le richiedono con un semplice manifest YAML (`claim`) senza conoscere Terraform, HCL o i dettagli del cloud provider sottostante. L'integrazione è nativa con RBAC Kubernetes, namespace, quota, admission policy (Kyverno/OPA) e GitOps (ArgoCD/Flux) — non serve un layer di autenticazione/autorizzazione separato come un backend Terraform Cloud.

**Quando usare Crossplane:**
- Team con cluster Kubernetes già maturo in produzione, che vuole offrire self-service infrastructure ai developer
- Platform engineering: costruire una Internal Developer Platform (IDP) con astrazioni custom (es. "RDS + security group + subnet" esposto come un singolo claim "Database")
- Necessità di riconciliazione continua (drift correction automatica) invece di apply on-demand
- Governance centralizzata via RBAC Kubernetes e policy engine già in uso per i workload

**Quando NON usare Crossplane:**
- Team senza cluster Kubernetes già operativo e maturo: introdurre un cluster solo per Crossplane è overkill
- Nessun bisogno reale di self-service multi-tenant: un singolo team che gestisce poche risorse cloud sta meglio con Terraform, più semplice da imparare e con ecosistema/registry più ampio
- Necessità di importare grandi quantità di infrastruttura legacy già gestita altrove: il path di adozione di Crossplane (installare provider, scrivere Composition) è più lento del `terraform import` diretto
- Team senza esperienza Kubernetes: la curva di apprendimento (CRD, RBAC, controller, reconciliation) si somma a quella del cloud provider

---

## Concetti Chiave

!!! note "I quattro mattoni di Crossplane"
    Provider, Managed Resource, Composite Resource (XR) + Composition, XRD. Capire la relazione tra questi quattro elementi è il prerequisito per tutto il resto.

### Provider
Un **Provider** è un pacchetto (immagine OCI) che installa nel cluster i CRD e i controller per gestire le API di un cloud specifico. Esempi: `provider-aws`, `provider-azure`, `provider-gcp`, `provider-family-aws` (versione modulare che installa solo i sotto-provider necessari, es. `provider-aws-s3`, `provider-aws-rds`).

```yaml
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws-s3
spec:
  package: xpkg.crossplane.io/crossplane-contrib/provider-aws-s3:v2.8.1
```

### Managed Resource (MR)
Una **Managed Resource** è un oggetto Kubernetes 1:1 con una risorsa cloud reale: un `Bucket` MR corrisponde esattamente a un bucket S3, un `RDSInstance` MR a un'istanza RDS. È l'equivalente concettuale di una `resource` Terraform, ma vive come CR (Custom Resource) nell'etcd del cluster invece che in uno state file.

```yaml
apiVersion: s3.aws.m.upbound.io/v1beta1   # variante namespaced (v2)
kind: Bucket
metadata:
  name: my-app-bucket
  namespace: team-checkout
spec:
  forProvider:
    region: eu-west-1
    tags:
      Environment: production
  providerConfigRef:
    kind: ClusterProviderConfig
    name: aws-provider-config
  managementPolicies: ["*"]   # default: controllo completo
```

### Composite Resource (XR) e Composition
Una **Composite Resource (XR)** è un'astrazione custom che aggrega più Managed Resource in un'unica unità logica: ad esempio un XR "Database" che internamente crea `RDSInstance` + `SecurityGroup` + `Subnet`. La **Composition** è il template che definisce QUALI Managed Resource compongono l'XR e come i loro campi si collegano ai parametri esposti. In v2 è sempre una pipeline di funzioni (vedi [Composition Functions](#layered-composition-e-funzioni-composition-functions)).

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: postgresqlinstances.aws.example.org
spec:
  compositeTypeRef:
    apiVersion: example.org/v1alpha1
    kind: PostgreSQLInstance
  mode: Pipeline
  pipeline:
    - step: patch-and-transform
      functionRef:
        name: crossplane-contrib-function-patch-and-transform
      input:
        apiVersion: pt.fn.crossplane.io/v1beta1
        kind: Resources
        resources:
          - name: rdsinstance
            base:
              apiVersion: rds.aws.m.upbound.io/v1beta1
              kind: Instance
              spec:
                forProvider:
                  engine: postgres
                  instanceClass: db.t3.medium
            patches:
              - type: FromCompositeFieldPath
                fromFieldPath: "spec.parameters.storageGB"
                toFieldPath: "spec.forProvider.allocatedStorage"
```

### XRD (CompositeResourceDefinition)
La **XRD** definisce lo schema (OpenAPI) dell'astrazione self-service esposta agli sviluppatori: quali campi possono impostare (es. `storageGB`, `engineVersion`), senza vedere i dettagli implementativi della Composition. In v2 la XRD (`apiextensions.crossplane.io/v2`) dichiara lo `scope` dell'XR (`Namespaced` di default, oppure `Cluster`) e genera il CRD dell'XR; non servono più `claimNames` né un tipo `X...` separato.

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: postgresqlinstances.example.org
spec:
  scope: Namespaced
  group: example.org
  names:
    kind: PostgreSQLInstance
    plural: postgresqlinstances
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                parameters:
                  type: object
                  properties:
                    storageGB:
                      type: integer
                    engineVersion:
                      type: string
                  required: [storageGB]
              required: [parameters]
```

### XR namespaced (e Claim legacy)
In v2 lo sviluppatore crea direttamente l'**XR namespaced** nel proprio namespace, senza toccare i dettagli cloud. Il **Claim** (oggetto namespaced che puntava a un XR cluster-scoped) sopravvive solo per le XRD legacy v1:

```yaml
apiVersion: example.org/v1alpha1
kind: PostgreSQLInstance
metadata:
  name: my-app-db
  namespace: team-checkout
spec:
  parameters:
    storageGB: 20
    engineVersion: "15"
```

---

## Architettura / Come Funziona

### Control Loop Kubernetes vs. Plan/Apply Terraform

Crossplane è "Terraform-via-Kubernetes-API": stessa idea dichiarativa (desired state → risorsa cloud), motore di esecuzione radicalmente diverso.

| Aspetto | Terraform | Crossplane |
|---|---|---|
| Stato | State file (locale o remote backend, es. S3 con locking) | Oggetti Kubernetes in etcd (nessuno state file separato) |
| Ciclo di esecuzione | On-demand: `plan` → review → `apply` | Control loop continuo: reconcile ogni N secondi, sempre attivo |
| Drift correction | Manuale: serve rieseguire `plan`/`apply` per rilevare drift | Automatica: il controller rileva e corregge il drift senza intervento umano |
| Autenticazione/autorizzazione | IAM cloud + backend state separato (es. policy S3 bucket) | RBAC Kubernetes nativo (Role/RoleBinding sugli XR/Claim) |
| Interfaccia utente | CLI `terraform` + HCL | `kubectl apply` + YAML, integrabile in qualsiasi tool che parla con l'API server |
| Estensione self-service | Moduli Terraform (riuso di codice HCL) | Composition + XRD (riuso come API Kubernetes) |

Il reconciler di ogni Managed Resource esegue continuamente questo ciclo:

```
┌──────────────────────────────────────────────────┐
│ 1. Osserva (Observe)                              │
│    Legge lo stato reale della risorsa cloud       │
│    tramite l'SDK del provider (es. AWS SDK)       │
└───────────────────┬────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────┐
│ 2. Confronta (Diff)                               │
│    Stato reale vs. spec.forProvider desiderato    │
└───────────────────┬────────────────────────────────┘
                     ▼
          ┌──────────┴──────────┐
          ▼                     ▼
   Nessuna differenza    Differenza rilevata
   → status: Ready       → Create/Update/Delete
          │                     │
          └──────────┬──────────┘
                     ▼
┌──────────────────────────────────────────────────┐
│ 3. Riprogramma (Requeue)                          │
│    Torna in coda per il prossimo ciclo            │
│    (default: ogni 1m, configurabile per provider) │
└──────────────────────────────────────────────────┘
```

Perché è "control loop e non on-demand": non serve che un umano lanci `pulumi up` o `terraform apply` — se qualcuno modifica manualmente il bucket S3 fuori da Crossplane, il reconciler lo rileva al ciclo successivo e lo riporta allo stato desiderato definito nel manifest.

### Layered Composition e Funzioni (Composition Functions)

Crossplane v2 ha rimosso il patching nativo delle Composition: l'unica modalità è `mode: Pipeline` con **Composition Functions**, pipeline di funzioni (container OCI, tipicamente scritte in Go/Python) che ricevono l'XR in input e producono le risorse composte in output, abilitando logica condizionale complessa (loop, if/else) impossibile con il solo patching YAML. Le funzioni vanno installate con un oggetto `Function`:

```yaml
apiVersion: pkg.crossplane.io/v1
kind: Function
metadata:
  name: crossplane-contrib-function-patch-and-transform
spec:
  package: xpkg.crossplane.io/crossplane-contrib/function-patch-and-transform:v0.8.2
---
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: postgresqlinstances.aws.example.org
spec:
  compositeTypeRef:
    apiVersion: example.org/v1alpha1
    kind: PostgreSQLInstance
  mode: Pipeline
  pipeline:
    - step: compose-rds
      functionRef:
        name: crossplane-contrib-function-patch-and-transform
      input:
        apiVersion: pt.fn.crossplane.io/v1beta1
        kind: Resources
        resources:
          - name: rdsinstance
            base:
              apiVersion: rds.aws.m.upbound.io/v1beta1
              kind: Instance
```

---

## Configurazione & Pratica

### Installazione via Helm

```bash
# Aggiungere il repo Helm ufficiale
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm repo update

# Installare Crossplane nel namespace dedicato
helm install crossplane crossplane-stable/crossplane \
  --namespace crossplane-system \
  --create-namespace \
  --version 2.4.2   # pinnare la versione; v2.x richiede package con path registry completo

# Verificare che i pod siano Running
kubectl get pods -n crossplane-system
```

### Installare e Configurare il Provider AWS

```bash
# Installare il provider (versione modulare consigliata: solo S3 + RDS)
cat <<EOF | kubectl apply -f -
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws-s3
spec:
  package: xpkg.crossplane.io/crossplane-contrib/provider-aws-s3:v2.8.1
---
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws-rds
spec:
  package: xpkg.crossplane.io/crossplane-contrib/provider-aws-rds:v2.8.1
EOF

# Verificare che il provider sia installato e healthy
kubectl get providers
```

```yaml
# Credenziali AWS come Secret + ProviderConfig
apiVersion: v1
kind: Secret
metadata:
  name: aws-secret
  namespace: crossplane-system
type: Opaque
data:
  creds: <base64 di un file credentials AWS>
---
apiVersion: aws.m.upbound.io/v1beta1
kind: ClusterProviderConfig   # ProviderConfig (namespaced) vale solo per le MR dello stesso namespace
metadata:
  name: aws-provider-config
spec:
  credentials:
    source: Secret
    secretRef:
      namespace: crossplane-system
      name: aws-secret
      key: creds
```

### Composition Completa — Astrazione "Database"

Composizione che espone un'astrazione "Database" nascondendo RDS + Security Group + Subnet Group (esempio semplificato, pipeline con `function-patch-and-transform`, XR namespaced):

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: databases.platform.example.org
spec:
  scope: Namespaced
  group: platform.example.org
  names:
    kind: Database
    plural: databases
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                parameters:
                  type: object
                  properties:
                    storageGB: { type: integer }
                    instanceClass: { type: string, default: "db.t3.micro" }
                  required: [storageGB]
---
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: databases-aws
  labels:
    provider: aws
spec:
  compositeTypeRef:
    apiVersion: platform.example.org/v1alpha1
    kind: Database
  mode: Pipeline
  pipeline:
    - step: compose-resources
      functionRef:
        name: crossplane-contrib-function-patch-and-transform
      input:
        apiVersion: pt.fn.crossplane.io/v1beta1
        kind: Resources
        resources:
          - name: subnetgroup
            base:
              apiVersion: rds.aws.m.upbound.io/v1beta1
              kind: SubnetGroup
              spec:
                forProvider:
                  region: eu-west-1
          - name: securitygroup
            base:
              apiVersion: ec2.aws.m.upbound.io/v1beta1
              kind: SecurityGroup
              spec:
                forProvider:
                  region: eu-west-1
          - name: rdsinstance
            base:
              apiVersion: rds.aws.m.upbound.io/v1beta1
              kind: Instance
              spec:
                forProvider:
                  engine: postgres
                  engineVersion: "15"
                  region: eu-west-1
                managementPolicies: ["*"]
            patches:
              - type: FromCompositeFieldPath
                fromFieldPath: "spec.parameters.storageGB"
                toFieldPath: "spec.forProvider.allocatedStorage"
              - type: FromCompositeFieldPath
                fromFieldPath: "spec.parameters.instanceClass"
                toFieldPath: "spec.forProvider.instanceClass"
              # connection secret: scritto dalla MR nel namespace dell'XR
              - type: FromCompositeFieldPath
                fromFieldPath: "metadata.name"
                toFieldPath: "spec.writeConnectionSecretToRef.name"
                transforms:
                  - type: string
                    string:
                      type: Format
                      fmt: "%s-conn"
```

<!-- CURRENCY: non verificato (2026-10) — patch del connection secret MR namespaced (writeConnectionSecretToRef) e securitygroup/subnet wiring omessi per brevità; controllare la reference del provider -->

!!! note "Connection details in v2"
    L'XR non espone più `connectionDetails`/`writeConnectionSecretToRef`. Il Secret con le credenziali lo scrive la singola MR (o una funzione, es. `function-go-templating`) nello stesso namespace dell'XR.

Richiesta self-service dello sviluppatore (XR namespaced, nessun Claim):

```yaml
apiVersion: platform.example.org/v1alpha1
kind: Database
metadata:
  name: checkout-db
  namespace: team-checkout
spec:
  parameters:
    storageGB: 50
    instanceClass: db.t3.medium
```

```bash
# Lo sviluppatore applica l'XR: nessuna conoscenza di RDS/VPC richiesta
kubectl apply -f database.yaml -n team-checkout

# Verificare lo stato di provisioning
kubectl get database checkout-db -n team-checkout
kubectl describe database checkout-db -n team-checkout

# Le credenziali sono in un Secret Kubernetes standard
kubectl get secret checkout-db-conn -n team-checkout -o yaml
```

### Testing di Composition/XRD prima del merge

Il warning in [Best Practices](#best-practices) dice di trattare una Composition come un'API pubblica con "test automatici prima del merge" — ecco come farlo concretamente, su due livelli.

**Livello 1 — `crossplane render` (offline, nessun cluster)**

Il comando `crossplane render` (introdotto come `crossplane beta render` in v1.14, ora stabile) compila claim + composite + function-pipeline di una Composition e stampa i Managed Resource risultanti, senza toccare alcun cluster reale. Serve a validare che il patching/function pipeline produca l'output atteso, in locale o in CI, in pochi secondi:

```bash
# render.sh — xr.yaml è l'XR di esempio, composition.yaml la Composition sotto test,
# functions.yaml dichiara le function usate dalla pipeline (se mode: Pipeline)
# Le function della pipeline girano come container: serve Docker locale
crossplane render xr.yaml composition.yaml functions.yaml > rendered-output.yaml

# Diff contro uno snapshot committato: se cambia senza che il PR lo documenti, fallisce
diff rendered-output.yaml tests/snapshots/xdatabase-aws.yaml
```

`crossplane render` non applica nulla al cluster: è equivalente concettuale di `terraform plan` con output renderizzato invece che un piano testuale, utile come gate rapido pre-merge.

**Livello 2 — Chainsaw/kuttl (end-to-end, cluster ephemeral)**

`crossplane render` non verifica che il provider accetti davvero i campi generati né che il reconciler converga. Per questo serve un test end-to-end: applicare il claim in un cluster kind/k3d usa-e-getta e asserire sullo stato finale delle Managed Resource. [Chainsaw](https://kyverno.github.io/chainsaw/) (dal progetto Kyverno) o il suo predecessore kuttl fanno esattamente questo, dichiarativamente:

```yaml
# chainsaw-test.yaml
apiVersion: chainsaw.kyverno.io/v1alpha1
kind: Test
metadata:
  name: xdatabase-aws-provisioning
spec:
  steps:
    - try:
        - apply:
            file: database-claim.yaml
        - assert:
            file: assert-rdsinstance-ready.yaml   # asserisce Managed Resource Ready: True
        - assert:
            resource:
              apiVersion: platform.example.org/v1alpha1
              kind: Database
              metadata:
                name: checkout-db
              status:
                conditions:
                  - type: Ready
                    status: "True"
```

**Pipeline CI (GitHub Actions) — bloccare il merge su diff non documentato**

```yaml
# .github/workflows/test-compositions.yml
on:
  pull_request:
    paths: ["compositions/**"]
jobs:
  render-diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Installare crossplane CLI
        run: |
          curl -sL https://raw.githubusercontent.com/crossplane/crossplane/main/install.sh | sh
          sudo mv crossplane /usr/local/bin/
      - name: Render e confronta con snapshot
        run: |
          crossplane render compositions/xdatabase/xr.yaml \
            compositions/xdatabase/composition.yaml \
            compositions/xdatabase/functions.yaml > /tmp/rendered.yaml
          diff compositions/xdatabase/snapshot.yaml /tmp/rendered.yaml
  e2e-chainsaw:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: helm/kind-action@v1
      - uses: actions/setup-go@v5
        with:
          go-version: stable
      - run: go install github.com/kyverno/chainsaw@latest   # pinnare una versione in produzione
      - run: chainsaw test compositions/xdatabase/chainsaw-test.yaml
```

Il job `render-diff` fallisce se l'output della Composition cambia senza che lo snapshot committato nel PR sia stato aggiornato consapevolmente (forza a rivedere/documentare ogni cambiamento di comportamento). Il job `e2e-chainsaw` verifica che il provider reale (in un kind effimero) accetti i campi generati e che il reconciler converga a `Ready: True`.

!!! note "Differenza con Molecule (Ansible)"
    [Molecule](../ansible/roles-collections.md) testa **convergenza e idempotenza** di un role Ansible su una VM/container: applica il role due volte e verifica che la seconda esecuzione non produca modifiche. Chainsaw/`crossplane render` testano invece la **generazione dichiarativa di manifest Kubernetes**: non c'è "seconda esecuzione" da confrontare, ma l'output di una pipeline di patching/funzioni contro uno schema atteso. Stesso principio (test automatico pre-merge di codice IaC), motore di verifica diverso perché il modello di esecuzione sottostante (convergenza imperativa vs. reconciliation dichiarativa) è diverso.

---

## Best Practices

!!! tip "Preferire Crossplane a Terraform quando emerge un pattern platform engineering"
    Se più team devono richiedere lo stesso tipo di risorsa (database, cluster, topic Kafka) con parametri limitati e in self-service, Crossplane con Composition/XRD converte quel bisogno in un'API Kubernetes versionata e validata da schema — Terraform richiederebbe un layer aggiuntivo (Terraform Cloud + Sentinel, o Atlantis) per ottenere un self-service equivalente.

- **Platform engineering e multi-tenancy**: usare XRD per definire il "menu" di astrazioni disponibili (Database, Cluster, Topic) e RBAC Kubernetes per limitare chi può creare claim in quale namespace
- **Pattern GitOps**: versionare Composition e XRD in Git, sincronizzarle nel cluster via ArgoCD/Flux; i claim degli sviluppatori vivono in repository applicative separate, seguendo lo stesso flusso GitOps dei Deployment applicativi
- **Provider modulari (`provider-family`)**: installare solo i sotto-provider necessari (es. `provider-aws-s3` invece del monolitico `provider-aws`) per ridurre il numero di CRD installati e il tempo di avvio
- **Connection secrets**: non esporre mai credenziali cloud generate nei log o nello status dell'XR; propagarle sempre come Secret Kubernetes nello stesso namespace dell'XR (`publishConnectionDetailsTo` e external secret store sono rimossi in v2)
- **Versionare le Composition Functions**: se si usa `mode: Pipeline`, taggare le immagini delle funzioni con versioni semantiche esplicite, mai `latest`, per evitare comportamento non riproducibile del reconciler

!!! warning "Rischio: Composition come single point of failure organizzativo"
    Una Composition mal progettata (troppo rigida o troppo permissiva) blocca tutti i team che la usano contemporaneamente. Trattarla come un'API pubblica: versionamento esplicito (`v1alpha1` → `v1beta1` → `v1`), deprecazione controllata, test automatici prima del merge.

### Anti-Pattern da Evitare

| Anti-pattern | Problema | Soluzione |
|---|---|---|
| Un XRD con decine di parametri opzionali | Astrazione che espone troppa complessità implementativa | Limitare i parametri del claim al minimo indispensabile per lo sviluppatore |
| Modificare Managed Resource manualmente con `kubectl edit` | Il reconciler la sovrascrive al ciclo successivo | Modificare sempre la Composition o l'XR, mai la MR generata |
| Provider monolitico (`provider-aws` intero) per un solo servizio | CRD e RBAC surface inutilmente ampi | Usare `provider-family-aws` con solo i sotto-provider richiesti |
| Nessuna `managementPolicies` esplicita su risorse critiche | Cancellazione accidentale dell'XR distrugge il database in produzione | `managementPolicies: ["Observe", "Create", "Update", "LateInitialize"]` (senza `Delete`) su MR critiche, per scollegare senza distruggere; `deletionPolicy` è deprecato |

---

## Troubleshooting

### Provider bloccato in stato non pronto (CRD non installate)
**Sintomo:** `kubectl get providers` mostra `INSTALLED: True` ma `HEALTHY: False` o vuoto; le CRD del provider (es. `buckets.s3.aws.upbound.io`) non compaiono in `kubectl get crds`.
**Causa:** il pod del provider non è ancora partito, oppure ha crashato per mancanza di risorse o immagine non raggiungibile.
```bash
# Verificare lo stato dettagliato del provider
kubectl describe provider provider-aws-s3

# Controllare i pod del provider (girano nel namespace crossplane-system)
kubectl get pods -n crossplane-system | grep provider-aws

# Log del pod provider per errori di pull immagine o crash
kubectl logs -n crossplane-system deploy/provider-aws-s3-<hash>
```
**Soluzione:** verificare connettività al registry OCI (`xpkg.upbound.io`), risorse CPU/memoria disponibili nel cluster, e che la versione del pacchetto esista.

### Composition che non converge (XR resta in `Synced: False`)
**Sintomo:** l'XR/claim resta indefinitamente in stato non pronto, `kubectl describe` mostra eventi ripetuti di errore.
**Causa:** tipicamente un patch nella Composition referenzia un `fromFieldPath` inesistente nello schema XRD, oppure una Managed Resource ha un campo `forProvider` non valido per l'API cloud.
```bash
# Vedere eventi e condizioni dell'XR
kubectl describe database <nome> -n <namespace>

# Vedere lo stato delle singole Managed Resource generate
kubectl get managed -l crossplane.io/composite=<nome-xr>

# Log del controller Crossplane core per errori di patching
kubectl logs -n crossplane-system deploy/crossplane -f
```
**Soluzione:** correggere il path del patch o il valore di default nello schema XRD, poi riapplicare la Composition (il reconciler la rilegge automaticamente al prossimo ciclo).

### Permessi IAM delle credenziali del provider insufficienti
**Sintomo:** la Managed Resource resta in `Ready: False` con evento `AccessDenied` o `UnauthorizedOperation` nei log, pur avendo un `ProviderConfig` valido.
**Causa:** le credenziali cloud referenziate nel `ProviderConfig` non hanno i permessi IAM necessari per l'azione richiesta (es. `rds:CreateDBInstance`).
```bash
# Verificare quale ProviderConfig usa la risorsa
kubectl get bucket my-app-bucket -o jsonpath='{.spec.providerConfigRef.name}'

# Controllare gli eventi della risorsa per il messaggio di errore IAM esatto
kubectl describe bucket my-app-bucket
```
**Soluzione:** estendere la policy IAM associata alle credenziali nel Secret referenziato dal `ProviderConfig`, seguendo il principio del privilegio minimo per le sole azioni richieste dal provider.

### XR creato ma nessuna Composition selezionata (`no matching composition`)
**Sintomo:** l'XR resta in stato vuoto/pending, evento `cannot find a Composition matching the composite resource's compositionSelector`.
**Causa:** la Composition non è stata applicata, oppure `compositionSelector.matchLabels` nell'XR non corrisponde alle label della Composition installata.
```bash
# Elencare le Composition disponibili e le loro label
kubectl get compositions --show-labels

# Verificare il selector richiesto dal claim
kubectl get database checkout-db -n team-checkout -o yaml | grep -A3 compositionSelector
```
**Soluzione:** applicare la Composition mancante o correggere le label/selector affinché combacino, oppure impostare `spec.crossplane.compositionRef.name` esplicito nell'XR (in v2 i campi di macchinario stanno sotto `spec.crossplane`) se si vuole bypassare la selezione per label.

---

## Relazioni

??? info "Terraform — Paradigma Dichiarativo On-Demand"
    Terraform resta lo standard de-facto per provisioning multi-cloud via CLI e HCL, con state file esplicito e cicli plan/apply on-demand. Crossplane copre lo stesso bisogno (provisionare risorse cloud) ma con un motore di esecuzione radicalmente diverso: control loop Kubernetes invece di CLI esterna.

    **Approfondimento →** [Terraform Fondamentali](../terraform/fondamentali.md)

??? info "Terraform State Management — Confronto Gestione Stato"
    Il problema di stato condiviso, locking e drift che Terraform risolve con backend remoti (es. S3 con locking) è risolto in Crossplane nativamente da etcd e dal control loop, senza bisogno di un layer separato di locking.

    **Approfondimento →** [Terraform State Management](../terraform/state-management.md)

??? info "Kubernetes Operators e CRD — Fondamento Tecnico di Crossplane"
    Crossplane è costruito sullo stesso pattern Operator/CRD usato per estendere Kubernetes con logica custom (es. operator per database, per certificati). Capire come funzionano CRD e controller aiuta a capire perché Crossplane si comporta come un operatore e non come un tool CLI.

    **Approfondimento →** [Operators e CRD](../../containers/kubernetes/operators-crd.md)

??? info "GitOps con ArgoCD — Sincronizzazione Composition e Claim"
    Composition, XRD e claim sono manifest YAML: si prestano naturalmente al pattern GitOps, sincronizzati automaticamente nel cluster da ArgoCD o Flux esattamente come i Deployment applicativi.

    **Approfondimento →** [ArgoCD](../../ci-cd/gitops/argocd.md)

---

## Riferimenti

- [Documentazione ufficiale Crossplane](https://docs.crossplane.io/)
- [Crossplane — Composition Functions](https://docs.crossplane.io/latest/concepts/composition-functions/)
- [Upbound Marketplace — Provider e Configuration](https://marketplace.upbound.io/)
- [Crossplane GitHub](https://github.com/crossplane/crossplane)
- [CNCF — Crossplane Project Page](https://www.cncf.io/projects/crossplane/)
