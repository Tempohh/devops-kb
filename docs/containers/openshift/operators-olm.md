---
title: "Operators e OLM"
slug: operators-olm
category: containers
tags: [openshift, olm, operatorhub, operator-lifecycle-manager, csv, subscription, catalogsource]
search_keywords: [openshift OLM, Operator Lifecycle Manager, OperatorHub, ClusterServiceVersion, Subscription openshift, CatalogSource, operator approval, operator channel, operator upgrade, openshift operator installation, custom catalog openshift, disconnected cluster operators, mirror operator catalog]
parent: containers/openshift/_index
related: [containers/kubernetes/operators-crd, containers/openshift/architettura]
official_docs: https://docs.openshift.com/container-platform/latest/operators/understanding/olm/olm-understanding-olm.html
status: complete
difficulty: advanced
last_updated: 2026-03-29
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
  | Operator: Vault  |
  | Channel: stable  |
  | Version: 1.16.0  |
  +--------+---------+
           |
           | admin subscribe
           v
  Subscription
  +------------------+
  | name: vault      |
  | channel: stable  |
  | approval: Auto   |
  | startingCSV:     |
  |   vault.v1.16.0  |
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

```yaml
# Installa un operator con approval manuale (produzione)
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: vault-operator
  namespace: vault-system           # namespace dove installare
spec:
  channel: stable
  name: vault                       # nome del package nel catalog
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Manual       # Manual | Automatic
  startingCSV: vault.v1.16.0       # opzionale: versione specifica

---
# OperatorGroup — definisce il targeting namespace
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: vault-og
  namespace: vault-system
spec:
  targetNamespaces:
    - vault-system                  # single namespace
  # Per installazione cluster-wide (omit targetNamespaces):
  # spec: {}
```

```bash
# Workflow installazione manuale

# 1. Crea namespace e OperatorGroup
oc new-project vault-system
oc apply -f operator-group.yaml

# 2. Crea Subscription
oc apply -f subscription.yaml

# 3. Approvazione manuale dell'InstallPlan
oc get installplan -n vault-system
# NAME            CSV                    APPROVAL   APPROVED
# install-abc123  vault.v1.16.0          Manual     false

# Approva l'installazione (review prima!)
oc patch installplan install-abc123 \
    --type merge \
    -p '{"spec":{"approved":true}}' \
    -n vault-system

# 4. Verifica installazione
oc get csv -n vault-system
# NAME             DISPLAY         VERSION   PHASE
# vault.v1.16.0    HashiCorp Vault  1.16.0   Succeeded

oc get pods -n vault-system
```

---

## ClusterServiceVersion — Il Manifesto dell'Operator

Il **CSV** è il manifesto che descrive tutto ciò che un Operator installa e gestisce.

```yaml
# Estratto di un CSV (semplificato)
apiVersion: operators.coreos.com/v1alpha1
kind: ClusterServiceVersion
metadata:
  name: vault.v1.16.0
  namespace: vault-system
  annotations:
    operators.openshift.io/valid-subscription: '["OpenShift Platform Plus"]'
spec:
  displayName: HashiCorp Vault
  version: 1.16.0
  replaces: vault.v1.15.3    # upgradepath: questa versione sostituisce la precedente
  description: |
    HashiCorp Vault secures, stores, and tightly controls access to tokens,
    passwords, certificates, API keys...

  # CRDs gestite da questo operator
  customresourcedefinitions:
    owned:
      - name: vaultservers.vault.banzaicloud.com
        version: v1alpha1
        kind: VaultServer
        description: "Represents a Vault server cluster"
      - name: vaultauthengines.vault.banzaicloud.com
        version: v1alpha1
        kind: VaultAuthEngine

  # RBAC richiesto dall'operator
  install:
    strategy: deployment
    spec:
      permissions:    # namespace-scoped
        - serviceAccountName: vault-operator
          rules:
            - apiGroups: [""]
              resources: [secrets, configmaps, pods]
              verbs: [get, list, watch, create, update, patch, delete]
      clusterPermissions:    # cluster-scoped
        - serviceAccountName: vault-operator
          rules:
            - apiGroups: [vault.banzaicloud.com]
              resources: ["*"]
              verbs: ["*"]

      deployments:
        - name: vault-operator
          spec:
            replicas: 1
            selector:
              matchLabels:
                app: vault-operator
            template:
              metadata:
                labels:
                  app: vault-operator
              spec:
                containers:
                  - name: vault-operator
                    image: banzaicloud/vault-operator:1.16.0
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
oc get subscription vault-operator -n vault-system -o yaml | grep -A5 installedCSV
# installedCSV: vault.v1.15.3   ← versione corrente

# OLM crea un InstallPlan per l'upgrade
oc get installplan -n vault-system
# NAME            CSV                APPROVAL   APPROVED
# upgrade-xyz789  vault.v1.16.0     Manual     false   ← upgrade disponibile

# Review del CSV prima di approvare
oc get csv vault.v1.16.0 -n vault-system -o yaml | grep -A20 'spec.description'

# Approva upgrade
oc patch installplan upgrade-xyz789 \
    --type merge \
    -p '{"spec":{"approved":true}}' \
    -n vault-system
```

---

## Disconnected Cluster — Mirroring del Catalog

In ambienti air-gapped o disconnected, il catalog deve essere specchiato localmente.

```bash
# Mirror del Red Hat Operators catalog (richiede pull secret Red Hat)
oc mirror \
    --config ./imageset-config.yaml \
    docker://registry.company.com/mirror

# imageset-config.yaml:
# kind: ImageSetConfiguration
# apiVersion: mirror.openshift.io/v1alpha2
# storageConfig:
#   registry:
#     imageURL: registry.company.com/mirror/metadata
# mirror:
#   operators:
#   - catalog: registry.redhat.io/redhat/redhat-operator-index:v4.15
#     packages:
#     - name: vault
#       channels:
#       - name: stable
#     - name: cert-manager
#       channels:
#       - name: stable-v1

# Dopo il mirror, applica i manifesti generati
oc apply -f ./oc-mirror-workspace/results-*/

# Crea CatalogSource che punta al mirror locale
# (generato automaticamente da oc mirror)
```

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
