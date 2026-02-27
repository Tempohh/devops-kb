---
title: "Deployment in Produzione"
slug: deployment-produzione
category: containers
tags: [helm, helmfile, oci-charts, upgrade, rollback, atomic, diff, gitops, ci-cd, chart-testing]
search_keywords: [helm production deployment, helmfile multi-release, helm OCI chart, helm diff plugin, helm upgrade atomic, helm rollback, helm --wait, helm chart museum, helmfile environments, helmfile sync, helm CI/CD pipeline, chart testing ct, helm release management, helm monorepo]
parent: containers/helm/_index
related: [containers/helm/_index, containers/helm/chart-avanzato, containers/openshift/gitops-pipelines, containers/registry/_index]
official_docs: https://helm.sh/docs/helm/helm_upgrade/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Deployment in Produzione

## OCI Charts — Registry come Repository

Con Helm 3.8+, i charts possono essere gestiti direttamente come artefatti OCI nel container registry, eliminando la necessità di ChartMuseum o repository HTTP separati.

```bash
# Push di un chart in un OCI registry (Harbor, ECR, GHCR, Docker Hub)
helm package ./mychart                     # crea mychart-1.2.0.tgz
helm push mychart-1.2.0.tgz oci://registry.company.com/helm-charts

# Pull e install da OCI registry
helm install myapp oci://registry.company.com/helm-charts/mychart \
    --version 1.2.0 \
    --namespace production \
    --create-namespace \
    --values values.production.yaml

# Upgrade da OCI
helm upgrade myapp oci://registry.company.com/helm-charts/mychart \
    --version 1.3.0 \
    --namespace production \
    --values values.production.yaml

# Visualizza versions disponibili (richiede registry con OCI catalog API)
helm show chart oci://registry.company.com/helm-charts/mychart
helm show values oci://registry.company.com/helm-charts/mychart --version 1.2.0

# Login al registry (una volta per sessione)
helm registry login registry.company.com \
    --username robot-ci \
    --password "$(cat /run/secrets/harbor-token)"

# Con ECR
aws ecr get-login-password --region eu-west-1 | \
    helm registry login \
        --username AWS \
        --password-stdin \
        123456789.dkr.ecr.eu-west-1.amazonaws.com

# CI: push automatico in pipeline
helm package ./mychart --version "${GIT_TAG}"
helm push "mychart-${GIT_TAG}.tgz" oci://registry.company.com/helm-charts
```

---

## Strategie di Upgrade Sicure

```bash
# --wait: aspetta che tutte le risorse siano Ready prima di completare
# --timeout: timeout massimo (default 5m)
# --atomic: rollback automatico se l'upgrade fallisce
# Combinazione raccomandata per produzione:

helm upgrade myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --set image.tag="${IMAGE_TAG}" \
    --wait \
    --timeout 10m \
    --atomic \
    --cleanup-on-fail               # rimuove risorse create durante upgrade fallito

# --install: combina install + upgrade (utile in CI/CD idempotente)
helm upgrade --install myapp ./mychart \
    --namespace production \
    --create-namespace \
    --values values.production.yaml \
    --wait \
    --atomic

# Dry run per validare prima di applicare
helm upgrade --install myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --dry-run --debug \
    2>&1 | head -100

# --force: forza update anche se non ci sono cambiamenti rilevati
# (utile per secrets rotati o imagePullPolicy=Always)
helm upgrade myapp ./mychart --force --namespace production

# Upgrade con history limit
helm upgrade myapp ./mychart \
    --namespace production \
    --history-max 10               # mantieni solo ultime 10 revisioni
```

---

## Helm Diff Plugin

Il plugin **helm-diff** mostra le differenze tra lo stato attuale e il release applicato, essenziale per review pre-deploy in produzione.

```bash
# Installazione
helm plugin install https://github.com/databus23/helm-diff

# diff tra release attuale e nuovo chart/values
helm diff upgrade myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --set image.tag=1.3.0

# Output (tipo diff unificato):
# default, myapp/Deployment (apps) has changed:
#   spec.template.spec.containers[0].image:
# -   registry.company.com/myapp:1.2.0
# +   registry.company.com/myapp:1.3.0
#   spec.template.spec.containers[0].resources.limits.memory:
# -   512Mi
# +   1Gi

# diff tra due revisioni dello stesso release
helm diff revision myapp 4 5 -n production

# diff con output in formato json (per parsing automatico)
helm diff upgrade myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --output json \
    | jq '.[] | select(.change != "none") | {kind, name, change}'
```

---

## Rollback

```bash
# Visualizzare la history completa
helm history myapp -n production
# REVISION  UPDATED                  STATUS     CHART          APP VERSION  DESCRIPTION
# 1         Mon Feb 24 10:00:00 2026 superseded myapp-1.0.0    3.4.0       Install complete
# 2         Mon Feb 24 11:00:00 2026 superseded myapp-1.1.0    3.5.0       Upgrade complete
# 3         Mon Feb 24 12:00:00 2026 failed     myapp-1.2.0    3.5.1       Upgrade "myapp" failed
# 4         Mon Feb 24 12:01:00 2026 deployed   myapp-1.1.0    3.5.0       Rollback to 2

# Rollback alla revisione precedente
helm rollback myapp -n production

# Rollback a revisione specifica
helm rollback myapp 2 -n production

# Rollback con wait (aspetta che il rollback sia completato)
helm rollback myapp 2 -n production --wait --timeout 5m

# Stato dopo rollback
helm status myapp -n production
```

---

## Helmfile — Multi-Release Management

**Helmfile** è uno strumento dichiarativo per gestire molteplici Helm releases in un progetto, supportando ambienti differenziati e dipendenze tra releases.

```yaml
# helmfile.yaml — definizione dichiarativa di tutti i releases
repositories:
  - name: bitnami
    url: https://charts.bitnami.com/bitnami
  - name: ingress-nginx
    url: https://kubernetes.github.io/ingress-nginx
  - name: cert-manager
    url: https://charts.jetstack.io
  - name: company
    url: oci://registry.company.com/helm-charts    # OCI registry

helmDefaults:
  wait: true
  timeout: 600
  atomic: true
  cleanupOnFail: true
  historyMax: 10
  createNamespace: true

environments:
  staging:
    values:
      - environments/staging/values.yaml
    secrets:
      - environments/staging/secrets.yaml         # sops-encrypted
  production:
    values:
      - environments/production/values.yaml
    secrets:
      - environments/production/secrets.yaml

releases:
  # Infrastruttura (deploy per prima — needs: garantisce ordine)
  - name: cert-manager
    namespace: cert-manager
    chart: cert-manager/cert-manager
    version: v1.14.0
    values:
      - installCRDs: true
        global:
          leaderElection:
            namespace: cert-manager

  - name: ingress-nginx
    namespace: ingress-nginx
    chart: ingress-nginx/ingress-nginx
    version: 4.9.0
    needs:
      - cert-manager/cert-manager
    values:
      - controller:
          replicaCount: 2
          service:
            type: LoadBalancer
          metrics:
            enabled: true

  # Applicazioni — dipendono dall'infrastruttura
  - name: postgresql
    namespace: data
    chart: bitnami/postgresql
    version: 13.x.x
    needs:
      - cert-manager/cert-manager
    values:
      - primary:
          persistence:
            size: "{{ .Environment.Values.dbSize | default \"10Gi\" }}"

  - name: myapp
    namespace: production
    chart: company/myapp
    version: "{{ requiredEnv \"MYAPP_VERSION\" }}"   # versione da env var CI
    needs:
      - data/postgresql
      - ingress-nginx/ingress-nginx
    values:
      - values/myapp-common.yaml
      - values/myapp-{{ .Environment.Name }}.yaml    # per-env override
    set:
      - name: image.tag
        value: "{{ requiredEnv \"IMAGE_TAG\" }}"
    secrets:
      - secrets/myapp-{{ .Environment.Name }}.yaml  # sops-encrypted secrets
```

```bash
# Comandi Helmfile
helmfile -e staging sync              # deploy tutto in staging
helmfile -e production sync           # deploy tutto in production
helmfile -e production diff           # mostra differenze
helmfile -e production apply          # sync solo se ci sono differenze
helmfile -e production destroy        # rimuovi tutti i releases
helmfile -e staging status            # stato di tutti i releases

# Deploy solo specifici releases
helmfile -e production -l name=myapp sync
helmfile -e production -l namespace=data sync

# Dry run
helmfile -e production sync --dry-run

# Con sops per secrets cifrati
helmfile -e production secrets decrypt   # test decrypt
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
helmfile -e production sync
```

**Struttura directory con Helmfile:**

```
gitops/
├── helmfile.yaml
├── values/
│   ├── myapp-common.yaml             # valori condivisi
│   ├── myapp-staging.yaml            # override staging
│   └── myapp-production.yaml         # override production
├── secrets/
│   ├── myapp-staging.yaml            # cifrati con sops
│   └── myapp-production.yaml         # cifrati con sops
└── environments/
    ├── staging/
    │   ├── values.yaml               # variabili ambiente
    │   └── secrets.yaml              # variabili cifrate
    └── production/
        ├── values.yaml
        └── secrets.yaml
```

---

## Chart Testing — ct (Chart Testing Tool)

```bash
# Installazione
helm plugin install https://github.com/helm/chart-testing

# ct lint — lint di tutti i charts modificati vs branch main
ct lint \
    --chart-dirs charts \
    --target-branch main

# ct install — test su cluster reale (richiede kind/k3d)
ct install \
    --chart-dirs charts \
    --target-branch main \
    --build-id "${CI_BUILD_ID}"

# Configurazione ct
cat > ct.yaml <<'EOF'
target-branch: main
chart-dirs:
  - charts
helm-extra-args: --timeout 5m
validate-maintainers: false
check-version-increment: true     # forza bump Chart.version su ogni modifica
EOF
```

---

## Pipeline CI/CD con Helm

```yaml
# .github/workflows/helm-deploy.yml
name: Helm Deploy

on:
  push:
    branches: [main]
    paths:
      - 'charts/**'
      - 'values/**'

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0             # necessario per ct (confronto con target-branch)

      - uses: azure/setup-helm@v3
        with:
          version: v3.14.0

      - name: Install ct
        uses: helm/chart-testing-action@v2

      - name: Lint charts
        run: ct lint --target-branch main

      - name: Create test cluster
        uses: helm/kind-action@v1
        if: steps.list-changed.outputs.changed == 'true'

      - name: Test charts
        run: ct install --target-branch main

  build-push-chart:
    needs: lint-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Harbor
        run: |
          helm registry login registry.company.com \
            --username "${{ secrets.HARBOR_USER }}" \
            --password "${{ secrets.HARBOR_PASSWORD }}"

      - name: Package and push chart
        run: |
          VERSION="${{ github.ref_name }}-${{ github.sha }}"
          helm package ./charts/myapp --version "${VERSION}"
          helm push "myapp-${VERSION}.tgz" oci://registry.company.com/helm-charts

  deploy-staging:
    needs: build-push-chart
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          helmfile -e staging sync
        env:
          MYAPP_VERSION: "${{ github.ref_name }}-${{ github.sha }}"
          IMAGE_TAG: "${{ github.sha }}"
          KUBECONFIG: "${{ secrets.KUBECONFIG_STAGING }}"

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production            # richiede approvazione manuale (GitHub Environments)
    steps:
      - name: Deploy to production
        run: |
          helmfile -e production sync
        env:
          MYAPP_VERSION: "${{ github.ref_name }}-${{ github.sha }}"
          IMAGE_TAG: "${{ github.sha }}"
          KUBECONFIG: "${{ secrets.KUBECONFIG_PRODUCTION }}"
```

---

## GitOps con Helm e ArgoCD

```yaml
# ArgoCD Application che deploya da chart OCI
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-production
  namespace: argocd
spec:
  project: production
  source:
    chart: myapp
    repoURL: oci://registry.company.com/helm-charts
    targetRevision: "1.3.0"        # versione chart pinnata
    helm:
      valueFiles:
        - values.production.yaml   # file nel repo GitOps
      parameters:
        - name: image.tag
          value: "sha-abc123"      # digest immagine pinnata
      releaseName: myapp           # nome Helm release
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true       # richiesto per risorse con managed fields complessi
```

```bash
# Pattern di aggiornamento GitOps (image promotion automation)
# 1. CI build immagine → push tag
# 2. CI aggiorna Application nel repo GitOps:
yq -i '.spec.source.helm.parameters[] |=
        select(.name == "image.tag").value = "sha-abc123"' \
    apps/production/myapp-application.yaml

git commit -m "chore: bump myapp image to sha-abc123"
git push

# 3. ArgoCD rileva il cambio Git → sync automatico
# 4. oc rollout / kubectl rollout monitora il deployment
argocd app wait myapp-production --health --timeout 300
```

---

## Best Practices Produzione

```
Helm Production Checklist

  Chart Development:
  ✓ values.schema.json per validazione types e required fields
  ✓ checksum/config annotation per restart su ConfigMap change
  ✓ Pre-upgrade hook per database migrations
  ✓ Helm test per smoke test post-deploy
  ✓ Chart version bump ad ogni modifica (check-version-increment)
  ✓ Semantic versioning: MAJOR.MINOR.PATCH
  ✓ Named templates in _helpers.tpl (no inline duplication)

  Releases Management:
  ✓ --atomic --wait in tutte le pipeline CI/CD
  ✓ --history-max 10 per limitare secrets K8s
  ✓ helm diff prima di ogni upgrade in produzione
  ✓ Ambienti separati (staging/production) con values distinti
  ✓ Secrets cifrati con SOPS (non plaintext in git)
  ✓ Pinning versione chart (non range aperte in production)

  OCI Registry:
  ✓ Immutable tags per chart di produzione
  ✓ Vulnerability scan sulle immagini base
  ✓ Robot accounts dedicati per CI (scope: push solo su charts/)
  ✓ Pull secrets configurati per ambienti air-gap

  GitOps:
  ✓ App configuration in git (ApplicationSet o Application per ambiente)
  ✓ Image tag update automatizzato (non manual)
  ✓ Review + approval manuale per produzione
  ✓ ArgoCD Application Health: monitorare stato post-sync
```

---

## Troubleshooting Comuni

```bash
# Helm release in stato "failed" — reset manuale
helm rollback myapp -n production           # torna alla revisione precedente

# Helm release bloccato in "pending-upgrade"
# (es. helm process interrotto durante upgrade)
kubectl get secret -n production | grep myapp
# sh.helm.release.v1.myapp.v3 → status=pending-upgrade
# Soluzione: rollback o patch diretta al secret
helm rollback myapp -n production

# Debug template rendering
helm template myapp ./mychart \
    --values values.yaml \
    --debug \
    2>&1 | grep -A5 "Error"

# Verificare values effettivi di un release
helm get values myapp -n production           # values espliciti
helm get values myapp -n production --all     # tutti i values (inclusi default)

# Esportare tutti i manifest applicati da un release
helm get manifest myapp -n production

# Verificare note post-install
helm get notes myapp -n production

# Helm con kubectl diff (alternativa a helm-diff per cluster)
helm template myapp ./mychart --values values.yaml \
    | kubectl diff -f -
```

---

## Riferimenti

- [Helm Upgrade Command](https://helm.sh/docs/helm/helm_upgrade/)
- [Helm OCI Support](https://helm.sh/docs/topics/registries/)
- [Helmfile](https://helmfile.readthedocs.io/)
- [helm-diff Plugin](https://github.com/databus23/helm-diff)
- [Chart Testing (ct)](https://github.com/helm/chart-testing)
- [SOPS + Helm Secrets](https://github.com/jkroepke/helm-secrets)
