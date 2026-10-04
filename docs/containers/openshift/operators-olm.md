---
title: "Operators e OLM"
slug: operators-olm
category: containers
tags: [openshift, olm, operatorhub, operator-lifecycle-manager, csv, subscription, catalogsource]
search_keywords: [openshift OLM, Operator Lifecycle Manager, OperatorHub, ClusterServiceVersion, Subscription openshift, CatalogSource, operator approval, operator channel, operator upgrade, openshift operator installation, custom catalog openshift, disconnected cluster operators, mirror operator catalog]
parent: containers/openshift/_index
related: [containers/kubernetes/operators-crd, containers/openshift/architettura]
official_docs: https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Operators e OLM

## Operator Lifecycle Manager — Gestione del Ciclo di Vita

L'**OLM (Operator Lifecycle Manager)** è il framework che gestisce l'installazione, l'upgrade e il lifecycle degli Operator su OpenShift (e Kubernetes).

```
OLM Components

  CatalogSource
  +------------------+
  | grpc image with  |   ← catalogo di operator disponibili
  | operator bundles |       (Red Hat, Community, Certified, Custom)
  +--------+---------+
           |
           | packages + channels + bundles
           v
  PackageManifest / OperatorHub UI
  +------------------+
  | Operator:        |
  |  cert-manager    |
  | Channel:stable-v1|
  | Version: 1.X.Y   |
  +--------+---------+
           |
           | admin subscribe
           v
  Subscription
  +------------------+
  | name: openshift- |
  |  cert-manager-.. |
  | channel:stable-v1|
  | approval: Auto   |
  | startingCSV: opt.|
  +--------+---------+
           |
           | OLM installs
           v
  InstallPlan → ClusterServiceVersion (CSV)
  +------------------+
  | CRDs             |
  | RBAC             |
  | Deployments      |
  | ServiceAccounts  |
  | ...              |
  +------------------+
           |
           | CSV creates
           v
  Operator Pod (running)
```

---

## CatalogSource — Sorgenti degli Operator

```yaml
# CatalogSource custom — per operator interni
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: company-operators
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: registry.company.com/operators/catalog:latest
  displayName: "Company Internal Operators"
  publisher: "Platform Team"
  updateStrategy:
    registryPoll:
      interval: 30m    # controlla aggiornamenti ogni 30 minuti

---
# CatalogSource predefiniti in OpenShift
# redhat-operators      → operator Red Hat ufficiali e supportati
# certified-operators   → operator di vendor certificati
# community-operators   → operator community (OperatorHub.io)
# redhat-marketplace    → operator Red Hat Marketplace (a pagamento)

oc get catalogsource -n openshift-marketplace
# NAME                   DISPLAY                TYPE   PUBLISHER
# certified-operators    Certified Operators    grpc   Red Hat
# community-operators    Community Operators    grpc   Red Hat
# redhat-marketplace     Red Hat Marketplace    grpc   Red Hat
# redhat-operators       Red Hat Operators      grpc   Red Hat
```

---

## Subscription — Installazione Operator

!!! note "Esempio illustrativo"
    Gli esempi usano il package reale `openshift-cert-manager-operator` (catalog `redhat-operators`, channel `stable-v1`, installazione tipica in `cert-manager-operator`). Le versioni CSV (`1.X.Y`) sono segnaposto: ricavare quelle reali con `oc get packagemanifest openshift-cert-manager-operator -n openshift-marketplace -o jsonpath='{.status.channels[*].currentCSV}'`.

```yaml
# Installa un operator con approval manuale (produzione)
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-cert-manager-operator
  namespace: cert-manager-operator  # namespace dove installare
spec:
  channel: stable-v1
  name: openshift-cert-manager-operator  # nome del package nel catalog
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Manual       # Manual | Automatic
  startingCSV: cert-manager-operator.v1.X.Y  # opzionale: versione specifica

---
# OperatorGroup — definisce il targeting namespace
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: cert-manager-operator-og
  namespace: cert-manager-operator
spec:
  targetNamespaces:
    - cert-manager-operator                  # single namespace
  # Per installazione cluster-wide (omit targetNamespaces):
  # spec: {}
```

```bash
# Workflow installazione manuale

# 1. Crea namespace e OperatorGroup
oc new-project cert-manager-operator
oc apply -f operator-group.yaml

# 2. Crea Subscription
oc apply -f subscription.yaml

# 3. Approvazione manuale dell'InstallPlan
oc get installplan -n cert-manager-operator
# NAME            CSV                               APPROVAL   APPROVED
# install-abc123  cert-manager-operator.v1.X.Y      Manual     false

# Approva l'installazione (review prima!)
oc patch installplan install-abc123 \
    --type merge \
    -p '{"spec":{"approved":true}}' \
    -n cert-manager-operator
# Nota: senza OperatorGroup nel namespace la CSV resta in fallimento
# (condizione "no operator group found"): crearlo PRIMA della Subscription.

# 4. Verifica installazione
oc get csv -n cert-manager-operator
# NAME                           DISPLAY                                       VERSION   PHASE
# cert-manager-operator.v1.X.Y   cert-manager Operator for Red Hat OpenShift   1.X.Y     Succeeded

oc get pods -n cert-manager-operator
```

---

## ClusterServiceVersion — Il Manifesto dell'Operator

Il **CSV** è il manifesto che descrive tutto ciò che un Operator installa e gestisce.

```yaml
# Estratto di un CSV (semplificato)
apiVersion: operators.coreos.com/v1alpha1
kind: ClusterServiceVersion
metadata:
  name: cert-manager-operator.v1.X.Y
  namespace: cert-manager-operator
  annotations:
    operators.openshift.io/valid-subscription: '["OpenShift Platform Plus"]'
spec:
  displayName: cert-manager Operator for Red Hat OpenShift
  version: 1.X.Y
  replaces: cert-manager-operator.v1.X.(Y-1)    # upgrade path: questa versione sostituisce la precedente
  # alternativa: olm.skipRange (annotation) per saltare versioni intermedie, es. ">=1.14.0 <1.X.Y"
  description: |
    Gestisce il rilascio e il rinnovo di certificati X.509 nel cluster
    (Issuer, ClusterIssuer, Certificate).

  # CRDs gestite da questo operator
  customresourcedefinitions:
    owned:
      - name: certificates.cert-manager.io
        version: v1
        kind: Certificate
        description: "Richiesta di certificato gestita da cert-manager"
      - name: clusterissuers.cert-manager.io
        version: v1
        kind: ClusterIssuer

  # RBAC richiesto dall'operator
  install:
    strategy: deployment
    spec:
      permissions:    # namespace-scoped
        - serviceAccountName: cert-manager-operator-sa
          rules:
            - apiGroups: [""]
              resources: [secrets, configmaps, pods]
              verbs: [get, list, watch, create, update, patch, delete]
      clusterPermissions:    # cluster-scoped
        - serviceAccountName: cert-manager-operator-sa
          rules:
            - apiGroups: [cert-manager.io]
              resources: ["*"]
              verbs: ["*"]

      deployments:
        - name: cert-manager-operator
          spec:
            replicas: 1
            selector:
              matchLabels:
                app: cert-manager-operator
            template:
              metadata:
                labels:
                  app: cert-manager-operator
              spec:
                containers:
                  - name: cert-manager-operator
                    image: registry.redhat.io/cert-manager/cert-manager-operator-rhel9:v1.X.Y  # esempio illustrativo
```

---

## Upgrade degli Operator

```bash
# Upgrade automatico (installPlanApproval: Automatic)
# → OLM installa automaticamente la nuova versione quando disponibile
# → Rischio: upgrade improvvisi senza review

# Upgrade manuale (installPlanApproval: Manual)
# → Notification quando disponibile upgrade
# → Admin approva esplicitamente

# Controlla upgrade disponibili
oc get subscription openshift-cert-manager-operator -n cert-manager-operator -o yaml | grep -A5 installedCSV
# installedCSV: cert-manager-operator.v1.X.(Y-1)   ← versione corrente

# OLM crea un InstallPlan per l'upgrade
oc get installplan -n cert-manager-operator
# NAME            CSV                            APPROVAL   APPROVED
# upgrade-xyz789  cert-manager-operator.v1.X.Y   Manual     false   ← upgrade disponibile

# Review del CSV prima di approvare
oc get csv cert-manager-operator.v1.X.Y -n cert-manager-operator -o yaml | grep -A20 'spec.description'

# Approva upgrade
oc patch installplan upgrade-xyz789 \
    --type merge \
    -p '{"spec":{"approved":true}}' \
    -n cert-manager-operator
```

---

## OLM v1 — Operator Controller (ClusterExtension)

OLM "classico" (v0, descritto sopra) rimane il default per gli Operator su OpenShift, ma da OpenShift 4.18 è GA **OLM v1**, riscrittura basata su due componenti: **catalogd** (serve i contenuti dei catalog come `ClusterCatalog`) e **operator-controller** (installa/aggiorna estensioni tramite `ClusterExtension`).

| Aspetto | OLM v0 (classico) | OLM v1 |
|---|---|---|
| Risorse utente | `Subscription` + `OperatorGroup` + `InstallPlan` | `ClusterExtension` (+ `ServiceAccount` dedicato) |
| Catalog | `CatalogSource` | `ClusterCatalog` |
| Permessi installazione | OLM usa privilegi propri (cluster-admin implicito) | L'installazione usa il `ServiceAccount` indicato: least privilege esplicito |
| Dipendenze | Resolver tra package | Nessun resolver di dipendenze tra operator |
| Scope | Per namespace via OperatorGroup | Orientato a installazione cluster-wide |

```yaml
apiVersion: olm.operatorframework.io/v1
kind: ClusterExtension
metadata:
  name: cert-manager
spec:
  namespace: cert-manager-operator
  serviceAccount:
    name: cert-manager-installer   # SA con i soli permessi per applicare i manifest del bundle
  source:
    sourceType: Catalog
    catalog:
      packageName: openshift-cert-manager-operator
      channels: [stable-v1]
```

Perché esiste: v0 concentra privilegi enormi in OLM (un bundle può creare RBAC arbitrario) e il modello `OperatorGroup` è fragile; v1 rende espliciti permessi e scope. Limiti verificati su OCP 4.20: l'estensione deve usare il bundle format `registry+v1`, supportare l'install mode `AllNamespaces` e non usare webhook; non sono supportate dipendenze dichiarate via `olm.gvk.required`/`olm.package.required`/`olm.constraint`. `SingleNamespace`/`OwnNamespace` e webhook sono solo Technology Preview in 4.20. Le procedure documentate sono solo CLI (la console non mostra ancora le risorse OLM v1). Se il vincolo non è soddisfatto, l'errore compare nelle condition della `ClusterExtension`.

---

## Disconnected Cluster — Mirroring del Catalog

In ambienti air-gapped o disconnected, il catalog deve essere specchiato localmente.

!!! warning "oc-mirror v1 deprecato"
    Il plugin `oc-mirror` v1 (`apiVersion: mirror.openshift.io/v1alpha2`, `storageConfig`, directory `oc-mirror-workspace/`) è deprecato da OpenShift 4.18 in favore di **oc-mirror v2** (`--v2`, `apiVersion: mirror.openshift.io/v2alpha1`). v2 non usa più `storageConfig` (niente metadata nel registry): lo stato è in una *workspace* locale. Verificato su 4.20/4.21: senza flag viene ancora eseguito v1 (il default passerà a v2 in una release futura), quindi specificare sempre `--v2` (o `--v1` per restare sul vecchio plugin); v1 non è ancora rimosso.

```bash
# imageset-config.yaml (oc-mirror v2)
# kind: ImageSetConfiguration
# apiVersion: mirror.openshift.io/v2alpha1
# mirror:
#   operators:
#   - catalog: registry.redhat.io/redhat/redhat-operator-index:v4.20
#     packages:
#     - name: openshift-cert-manager-operator
#       channels:
#       - name: stable-v1

# Mirror-to-mirror (host con accesso a internet E al registry interno).
# Richiede pull secret Red Hat in ~/.docker/config.json o $XDG_RUNTIME_DIR/containers/auth.json
oc mirror --v2 \
    -c ./imageset-config.yaml \
    --workspace file:///data/oc-mirror \
    docker://registry.company.com/mirror

# Variante air-gapped vera: due passi con trasporto fisico dell'archivio
#   1) mirror-to-disk (host connesso)
oc mirror --v2 -c ./imageset-config.yaml file:///data/oc-mirror
#   2) disk-to-mirror (host nella rete isolata)
oc mirror --v2 -c ./imageset-config.yaml \
    --from file:///data/oc-mirror docker://registry.company.com/mirror

# Applica le risorse generate (IDMS/ITMS + CatalogSource + ClusterCatalog)
oc apply -f /data/oc-mirror/working-dir/cluster-resources/
```

Perché servono **IDMS/ITMS** (`ImageDigestMirrorSet`/`ImageTagMirrorSet`): i bundle OLM referenziano immagini per digest su `registry.redhat.io`; i mirror set istruiscono i nodi (CRI-O) a risolverle sul registry interno senza riscrivere i manifest. Il `CatalogSource` generato punta all'indice mirrorato; i vecchi `ImageContentSourcePolicy` (ICSP) sono deprecati.

---

## Troubleshooting

### Scenario 1 — CSV rimane in fase `Installing` o `Failed`

**Sintomo:** `oc get csv -n <namespace>` mostra il CSV con `PHASE: Installing` o `PHASE: Failed` indefinitamente.

**Causa:** Immagine dell'operator non raggiungibile, RBAC insufficiente, o CRD già esistente in conflitto.

**Soluzione:** Ispezionare gli eventi e i log del pod OLM.

```bash
# Verifica lo stato dettagliato del CSV
oc describe csv <csv-name> -n <namespace>
# Cercare sezione "Conditions" per il messaggio di errore

# Log del catalog operator
oc logs -n openshift-operator-lifecycle-manager \
    deployment/catalog-operator -f

# Log del packageserver
oc logs -n openshift-operator-lifecycle-manager \
    deployment/packageserver -f

# Controlla eventi nel namespace
oc get events -n <namespace> --sort-by=.lastTimestamp | tail -20
```

---

### Scenario 2 — InstallPlan non viene creato dopo la Subscription

**Sintomo:** La Subscription esiste ma `oc get installplan -n <namespace>` non mostra nulla.

**Causa:** CatalogSource non raggiungibile o pod del catalog in errore. OLM non riesce a risolvere il package dalla sorgente.

**Soluzione:** Verificare lo stato dei CatalogSource e del pod associato.

```bash
# Controlla lo stato dei CatalogSource
oc get catalogsource -n openshift-marketplace
oc describe catalogsource <source-name> -n openshift-marketplace
# Cercare: "READY" nel campo CONNECTION STATE

# Verifica il pod del catalog (grpc server)
oc get pods -n openshift-marketplace
oc logs <catalog-pod> -n openshift-marketplace

# Controlla se il package è disponibile nel catalog
oc get packagemanifest <package-name> -n openshift-marketplace

# Forza riconciliazione eliminando e ricreando la Subscription
oc delete subscription <name> -n <namespace>
oc apply -f subscription.yaml
```

---

### Scenario 3 — Upgrade bloccato, nuova versione non compare

**Sintomo:** Esiste una versione più recente sul catalog ma OLM non crea un InstallPlan di upgrade per la Subscription esistente.

**Causa:** La versione corrente non ha un `replaces` che copre il CSV installato, oppure il channel è stato rinominato/rimosso.

**Soluzione:** Verificare il grafo degli upgrade e il channel attivo.

```bash
# Controlla il channel e il CSV installato
oc get subscription <name> -n <namespace> -o yaml
# Campi importanti: channel, installedCSV, currentCSV

# Verifica i canali disponibili per il package
oc get packagemanifest <package-name> \
    -o jsonpath='{.status.channels[*].name}'

# Verifica il grafo di upgrade (replaces chain)
oc get packagemanifest <package-name> \
    -o jsonpath='{.status.channels[?(@.name=="stable")].entries[*]}'

# Se il channel è cambiato, aggiorna la Subscription
oc patch subscription <name> -n <namespace> \
    --type merge \
    -p '{"spec":{"channel":"stable-v2"}}'
```

---

### Scenario 4 — Operator installato ma CR non viene riconciliata

**Sintomo:** Il CSV è in `Succeeded` e l'operator pod è Running, ma la Custom Resource creata non produce risultati (pod non creati, status vuoto).

**Causa:** Il pod dell'operator è in crash loop, manca RBAC sul namespace target, o la CR ha un campo non valido.

**Soluzione:** Controllare log dell'operator e RBAC.

```bash
# Verifica lo stato del pod dell'operator
oc get pods -n <operator-namespace>
oc logs deployment/<operator-deployment> -n <operator-namespace> -f

# Controlla se ci sono errori di RBAC
oc auth can-i list pods \
    --as=system:serviceaccount:<operator-namespace>:<operator-sa> \
    -n <target-namespace>

# Descrivi la CR per vedere gli eventi e lo status
oc describe <cr-kind> <cr-name> -n <namespace>

# Verifica che la CRD sia installata correttamente
oc get crd | grep <group>
oc describe crd <crd-name>
```

---

## Riferimenti

- [OLM Concepts](https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html)
- [Installing Operators](https://docs.openshift.com/container-platform/latest/operators/admin/olm-adding-operators-to-cluster.html)
- [Creating Operator Catalogs](https://docs.openshift.com/container-platform/latest/operators/admin/olm-custom-catalog.html)
- [Disconnected Install](https://docs.openshift.com/container-platform/latest/installing/disconnected_install/installing-mirroring-installation-images.html)
