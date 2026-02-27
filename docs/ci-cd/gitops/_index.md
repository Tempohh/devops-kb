---
title: "GitOps"
slug: gitops
category: ci-cd
tags: [gitops, argocd, flux, kubernetes, declarative, continuous-delivery]
search_keywords: [gitops, gitops principles, gitops vs cicd, pull-based deployment, argocd, flux, git as source of truth, declarative infrastructure, drift detection, reconciliation loop]
parent: ci-cd/_index
related: [ci-cd/gitops/argocd, ci-cd/gitops/flux, ci-cd/jenkins/enterprise-patterns, containers/kubernetes/_index]
official_docs: https://opengitops.dev/
status: complete
difficulty: intermediate
last_updated: 2026-02-27
---

# GitOps

## Panoramica

GitOps è un framework operativo per la gestione di infrastrutture e applicazioni in cui Git è la singola fonte di verità per lo stato desiderato del sistema. Invece di eseguire comandi imperativi (`kubectl apply`, `helm upgrade`) dalla pipeline CI/CD, in GitOps si descrive lo stato desiderato nel repository Git e un agente in esecuzione nel cluster (ArgoCD, Flux) lo confronta continuamente con lo stato reale, applicando le correzioni necessarie (reconciliation). Questo approccio migliora la sicurezza (il cluster non è accessibile dalla CI), l'auditabilità (ogni cambio è un commit), e la resilienza (lo stato desiderato sopravvive a disastri e può essere ripristinato con `git clone`).

## I 4 Principi GitOps (OpenGitOps v1.0)

Il progetto [OpenGitOps](https://opengitops.dev/) definisce 4 principi fondamentali:

### 1. Declarative (Dichiarativo)
Il sistema gestito deve essere descritto in modo dichiarativo. Lo stato desiderato è espresso tramite manifesti (YAML Kubernetes, Helm values, Terraform HCL) che descrivono **cosa** deve esistere, non **come** crearlo.

```yaml
# ✅ Dichiarativo: "voglio 3 repliche di nginx 1.25"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: nginx
          image: nginx:1.25.4

# ❌ Imperativo: "crea un deployment, poi scalalo a 3"
# kubectl create deployment nginx --image=nginx:1.25.4
# kubectl scale deployment nginx --replicas=3
```

### 2. Versioned and Immutable (Versionato e Immutabile)
Lo stato desiderato è conservato in modo da preservare la storia completa e rendere ogni versione immutabile. Git fornisce questo nativamente: ogni commit è identificato da un SHA immutabile.

```bash
# Ogni cambio di configurazione è tracciato
git log --oneline apps/myapp/
# a3f8c2d feat: scale myapp to 5 replicas for peak traffic
# 7b1e9f0 fix: increase memory limit to prevent OOMKill
# 2c4a1b3 feat: add liveness probe
# 9e7d5a2 chore: initial deployment configuration
```

### 3. Pulled Automatically (Pull Automatico)
L'agente GitOps fa il pull dei manifesti dal repository Git e li applica al sistema. Il CI/CD non ha accesso diretto al cluster — riduce drasticamente la superficie di attacco.

### 4. Continuously Reconciled (Riconciliazione Continua)
L'agente monitora continuamente lo stato reale del sistema e lo confronta con quello desiderato. Se divergono (drift), corregge automaticamente. Se qualcuno fa un `kubectl edit` manuale, l'agente lo ripristina.

## Push-Based vs Pull-Based Deployment

### Push-Based (CI/CD Tradizionale)

```
Repository Git
      │
      │ push/commit
      ▼
   Pipeline CI/CD
   (GitHub Actions, Jenkins, GitLab CI)
      │
      │ kubectl apply / helm upgrade
      │ (richiede credenziali cluster in CI)
      ▼
   Cluster Kubernetes
```

**Problemi:**
- Le credenziali del cluster devono essere conservate nel CI/CD (secrets a rischio)
- Il CI/CD ha accesso privilegiato a potenzialmente tutti i cluster
- Drift non rilevato: se qualcuno modifica manualmente il cluster, la CI non lo sa
- Il cluster deve essere raggiungibile dalla rete del CI/CD

### Pull-Based (GitOps)

```
Repository Git
   ▲       ▲
   │ push  │ poll (ogni 1-5 min)
   │       │
Developer  GitOps Agent (ArgoCD/Flux)
           in esecuzione NEL cluster
                  │
                  │ applica solo delta
                  ▼
           Cluster Kubernetes
```

**Vantaggi:**
- Nessuna credenziale cluster nel CI/CD
- Il cluster non deve essere raggiungibile dall'esterno
- Drift detection e auto-healing integrati
- Audit trail completo: ogni cambio è un commit Git

### Confronto Sicurezza

| Aspetto | Push-Based | Pull-Based (GitOps) |
|---------|-----------|---------------------|
| Credenziali cluster nel CI | Sì (secrets a rischio) | No |
| Superficie di attacco | Ampia (CI può fare tutto) | Ridotta (solo agent nel cluster) |
| Accesso da rete esterna al cluster | Richiesto | Non richiesto |
| Drift detection | No | Sì (automatica) |
| Rollback | Manuale o re-run pipeline | `git revert` + reconciliation |
| Audit trail | Log pipeline | Git history |
| Multi-cluster management | Complesso | Nativo (ArgoCD/Flux) |

## Repository Strategy

### Mono-Repo

Codice applicativo e manifesti di configurazione nello stesso repository.

```
my-service/
├── src/                    # Codice sorgente
├── Dockerfile
├── k8s/                    # Manifesti Kubernetes
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
├── .github/workflows/
│   └── ci.yml              # Build + update image tag
└── README.md
```

**Pro:** Semplice, un solo repo da gestire, PR include sia codice che config.
**Contro:** La pipeline CI deve fare commit nel repo per aggiornare l'image tag (loop di trigger possibile), meno sicuro (developer app ha accesso alla config di produzione).

### Poly-Repo (Raccomandato per produzione)

Repository separati per codice applicativo e manifesti di configurazione.

```
app-source/                 # Codice dell'applicazione
├── src/
├── Dockerfile
└── .github/workflows/
    └── ci.yml              # Build image, poi aggiorna gitops-manifests

gitops-manifests/           # Repository GitOps (separato)
├── apps/
│   ├── myapp/
│   │   ├── base/
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   └── kustomization.yaml
│   │   └── overlays/
│   │       ├── dev/
│   │       │   └── kustomization.yaml  # replica: 1, resources: small
│   │       ├── staging/
│   │       │   └── kustomization.yaml  # replica: 2
│   │       └── production/
│   │           └── kustomization.yaml  # replica: 5, resources: large
│   └── other-service/
│       └── ...
├── infrastructure/
│   ├── cert-manager/
│   ├── ingress-nginx/
│   └── monitoring/
└── environments/
    ├── dev/
    │   └── apps.yaml       # Lista app in dev con sorgente
    ├── staging/
    │   └── apps.yaml
    └── production/
        └── apps.yaml
```

**Pro:** Separazione chiara di responsabilità, developer non hanno accesso diretto a prod, history Git pulita per la configurazione, ArgoCD/Flux possono avere accesso in sola lettura al repo.
**Contro:** Due repository da gestire, la CI deve fare un commit nel repo gitops dopo ogni build.

### Flusso Completo Poly-Repo

```
1. Developer fa push su app-source (nuovo feature)
       │
       ▼
2. CI Pipeline (GitHub Actions / GitLab CI)
   - Build e test
   - Build Docker image
   - Push a Container Registry (ghcr.io, ECR, GCR)
   - Aggiorna gitops-manifests:
     git clone gitops-manifests
     # Aggiorna il tag dell'immagine in overlays/staging/
     sed -i "s|image: myapp:.*|image: myapp:${NEW_TAG}|" ...
     git commit -m "chore: update myapp to ${NEW_TAG}"
     git push
       │
       ▼
3. ArgoCD/Flux detecta il commit in gitops-manifests
   - Confronta stato desiderato (Git) con stato reale (K8s)
   - Applica le modifiche (nuova image tag → rolling update)
       │
       ▼
4. Deployment completato nel cluster
   - ArgoCD/Flux riporta lo stato nella UI
   - Notifiche (Slack, PagerDuty)
```

## ArgoCD vs Flux — Confronto

| Feature | ArgoCD | Flux |
|---------|--------|------|
| **Architettura** | Monolite (server, repo-server, controller) | Microcontroller separati (source, kustomize, helm, notif) |
| **UI** | Web UI ricca e visuale | Minimal (Weave GitOps per UI completa) |
| **Multi-cluster** | Hub-and-spoke nativo | Bootstrap per cluster |
| **ApplicationSet** | Sì (generator potenti) | Sì (via Flux Kustomization) |
| **Helm support** | Nativo | HelmRelease CRD |
| **Kustomize support** | Nativo | Kustomization CRD |
| **SOPS secrets** | Plugin (argocd-vault-plugin) | Nativo (`decryption:`) |
| **OCI artifacts** | Sì (da v2.6) | Sì (OCIRepository) |
| **Progressive Delivery** | Argo Rollouts | Flagger |
| **Image Automation** | ArgoCD Image Updater | Image Automation Controller (nativo) |
| **RBAC** | Sì (argocd-rbac-cm) | Via Kubernetes RBAC |
| **SSO** | Dex (OIDC) integrato | Via Kubernetes OIDC |
| **Notifiche** | argocd-notifications | Notification Controller |
| **CNCF status** | Graduated | Graduated |
| **Curva apprendimento** | Moderata | Alta (controller multipli da capire) |

**Quando scegliere ArgoCD:**
- UI importante per il team (visibilità dello stato del deployment)
- Multi-cluster complesso con ApplicationSet
- Team che preferisce un agente centralizzato

**Quando scegliere Flux:**
- Architettura GitOps "pura" con controller separati
- Integrazione profonda con Kustomize e SOPS
- Image automation nativa senza strumenti aggiuntivi
- Filosofia "everything is a CRD" allineata con Kubernetes

## Relazioni

??? info "ArgoCD — Approfondimento"
    Architettura dettagliata, Application CRD, App of Apps, ApplicationSet, multi-cluster, SSO, RBAC, sync hooks, Image Updater, Argo Rollouts.

    **Approfondimento completo →** [ArgoCD](argocd.md)

??? info "Flux CD — Approfondimento"
    GitOps Toolkit, bootstrap, GitRepository, Kustomization, HelmRelease, SOPS, Image Automation, Flagger.

    **Approfondimento completo →** [Flux CD](flux.md)

??? info "Kubernetes"
    Concetti Kubernetes necessari per GitOps: Deployment, Service, Namespace, RBAC, CRD.

    **Approfondimento completo →** [Kubernetes](../../containers/kubernetes/_index.md)

## Riferimenti

- [OpenGitOps — Principi ufficiali](https://opengitops.dev/)
- [CNCF GitOps Working Group](https://github.com/cncf/tag-app-delivery/tree/main/gitops-wg)
- [GitOps: What You Need To Know (Weaveworks)](https://www.weave.works/technologies/gitops/)
- [ArgoCD documentation](https://argo-cd.readthedocs.io/)
- [Flux documentation](https://fluxcd.io/flux/)
- [GitOps Con talks (KubeCon)](https://www.youtube.com/playlist?list=PLj6h78yzYM2PyrvCoOii4rAopBswfz1p7)
