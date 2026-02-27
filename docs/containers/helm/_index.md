---
title: "Helm"
slug: helm
category: containers
tags: [helm, kubernetes, package-manager, charts, releases, repositories, oci-charts]
search_keywords: [helm package manager, helm chart, helm release, helm repository, helm upgrade, helm rollback, helm template, helm values, helm hooks, helm OCI, helm helmfile, kubernetes deployment]
parent: containers/_index
related: [containers/kubernetes/workloads, containers/openshift/gitops-pipelines, containers/helm/chart-avanzato, containers/helm/deployment-produzione]
official_docs: https://helm.sh/docs/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# Helm

**Helm** è il package manager de facto per Kubernetes. Impacchetta risorse Kubernetes in **Charts** riutilizzabili e gestisce il ciclo di vita dei **Releases** (installazione, upgrade, rollback).

```
Helm Architecture

  Developer                    Kubernetes Cluster
  ──────────                   ──────────────────
  Chart Sources                Release State
  ┌──────────┐                 ┌────────────────┐
  │  Chart   │  helm install   │    Release     │
  │ (YAML    │ ─────────────→  │  (Secret in    │
  │ templates│  helm upgrade   │   namespace)   │
  │ + values)│ ─────────────→  │                │
  └──────────┘  helm rollback  └────────────────┘
       ↑        ─────────────→        ↓
  ┌──────────┐                 ┌────────────────┐
  │  Chart   │                 │  K8s Objects   │
  │  Repos   │                 │  (Deployments, │
  │ (HTTP /  │                 │  Services,     │
  │  OCI)    │                 │  ConfigMaps...)│
  └──────────┘                 └────────────────┘
```

## Concetti Fondamentali

| Concetto | Descrizione |
|----------|-------------|
| **Chart** | Pacchetto con templates K8s + valori default + metadata |
| **Release** | Istanza di un chart installata nel cluster (ha nome e storia revisioni) |
| **Values** | Parametri configurabili iniettati nei template al momento del render |
| **Repository** | Index HTTP di charts scaricabili, oppure OCI registry |
| **Revision** | Ogni install/upgrade crea una nuova revisione; rollback torna a revisione precedente |

## Struttura di un Chart

```
mychart/
├── Chart.yaml          # metadata: name, version, appVersion, dependencies
├── values.yaml         # valori default
├── values.schema.json  # (opzionale) validazione JSON Schema dei values
├── charts/             # sub-charts (dipendenze unpacked)
├── crds/               # CRD installate PRIMA di tutto il resto
└── templates/
    ├── _helpers.tpl    # named templates riutilizzabili (no output diretto)
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── hpa.yaml
    ├── serviceaccount.yaml
    ├── configmap.yaml
    ├── NOTES.txt       # messaggio post-install all'utente
    └── tests/
        └── test-connection.yaml
```

## Comandi Essenziali

```bash
# Repository management
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Ricerca chart
helm search repo nginx
helm search hub postgresql          # ricerca su Artifact Hub

# Installazione
helm install my-nginx ingress-nginx/ingress-nginx \
    --namespace ingress \
    --create-namespace \
    --set controller.replicaCount=2

# Con values file
helm install my-app ./mychart \
    --namespace production \
    --values values.production.yaml \
    --set image.tag=1.2.0

# Upgrade
helm upgrade my-app ./mychart \
    --namespace production \
    --values values.production.yaml \
    --set image.tag=1.3.0

# Rollback a revisione precedente
helm rollback my-app 2 --namespace production

# Status e history
helm list -n production
helm history my-app -n production
helm status my-app -n production

# Debug: render senza installare
helm template my-app ./mychart --values values.yaml
helm install my-app ./mychart --dry-run --debug

# Uninstall (mantieni history con --keep-history)
helm uninstall my-app -n production
```

## Sezioni

<div class="grid cards" markdown>

- :material-file-code: **[Chart Avanzato](chart-avanzato.md)**

    Templating con Go templates, helpers, hooks, library charts, testing

- :material-rocket-launch: **[Deployment in Produzione](deployment-produzione.md)**

    OCI charts, Helmfile, upgrade strategies, diff plugin, CI/CD integration

</div>

---

## Riferimenti

- [Helm Documentation](https://helm.sh/docs/)
- [Artifact Hub](https://artifacthub.io/)
- [Helm Chart Best Practices](https://helm.sh/docs/chart_best_practices/)
