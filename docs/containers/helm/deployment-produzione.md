---
title: "Deployment in Produzione"
slug: deployment-produzione
category: containers
tags: [helm, helmfile, oci-charts, upgrade, rollback, atomic, diff, gitops, ci-cd, chart-testing]
search_keywords: [helm production deployment, helmfile multi-release, helm OCI chart, helm diff plugin, helm upgrade atomic, helm rollback, helm --wait, helm chart museum, helmfile environments, helmfile sync, helm CI/CD pipeline, chart testing ct, helm release management, helm monorepo]
parent: containers/helm/_index
related: [containers/helm/_index, containers/helm/chart-avanzato, containers/openshift/gitops-pipelines, containers/registry/_index]
official_docs: https://helm.sh/docs/helm/helm_upgrade/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
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

# Metadata e values di una versione (senza --version prende la più recente)
helm show chart oci://registry.company.com/helm-charts/mychart --version 1.2.0
helm show values oci://registry.company.com/helm-charts/mychart --version 1.2.0

# Elenco versioni: `helm search repo` NON funziona con OCI, serve un tool esterno
# (crane / oras interrogano la tag list del registry)
crane ls registry.company.com/helm-charts/mychart
oras repo tags registry.company.com/helm-charts/mychart

# Login al registry (una volta per sessione); --password-stdin evita
# di esporre il token negli argomenti del processo
helm registry login registry.company.com \
    --username robot-ci \
    --password-stdin < /run/secrets/harbor-token

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
# --wait: aspetta che Deployment/StatefulSet/Job/PVC/Service siano Ready prima di
#         marcare il release `deployed` (senza, Helm torna appena i manifest sono applicati)
# --timeout: timeout massimo del wait (default 5m)
# --atomic: se upgrade/wait fallisce, esegue rollback automatico alla revisione precedente
#           (implica --wait)
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
# =server invia i manifest all'API server (validazione schema, admission, CRD);
# il dry-run client-side (default) non rileva questi errori
helm upgrade --install myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --dry-run=server --debug \
    2>&1 | head -100

# --force: elimina e ricrea le risorse che non si possono aggiornare con patch
# (es. campo immutabile). NON è "forza il restart": per rotazione di Secret/ConfigMap
# usare l'annotation checksum/config nel pod template. Causa downtime: da evitare in prod.
helm upgrade myapp ./mychart --force --namespace production

# Upgrade con history limit
helm upgrade myapp ./mychart \
    --namespace production \
    --history-max 10               # mantieni solo ultime 10 revisioni
```

!!! note "Helm 4"
    Con Helm 4 (rilasciato nel 2025) i flag sono rinominati: `--atomic` → `--rollback-on-failure`
    e `--force` → `--force-replace` (i vecchi nomi restano come alias deprecati). Il wait
    usa di default la strategia *watcher* basata su eventi invece del polling. Gli esempi
    di questa pagina usano la sintassi Helm 3, ancora valida.

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

# In CI: exit code 2 se ci sono differenze, 0 se nessuna, 1 se errore
helm diff upgrade myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --detailed-exitcode
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
    url: registry.company.com/helm-charts          # OCI: senza schema oci://
    oci: true                                      # + flag oci (login: helm registry login)

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
    version: v1.17.0
    values:
      - crds:                      # sostituisce installCRDs (deprecato da v1.15)
          enabled: true
          keep: true               # i CRD sopravvivono a helm uninstall
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

!!! warning "Chart di esempio non più raccomandati"
    `ingress-nginx` (progetto Kubernetes) è stato dismesso a marzo 2026: nessuna
    patch di sicurezza successiva, per nuovi deploy preferire Gateway API o un altro
    controller. Anche il catalogo **Bitnami** (`bitnami/postgresql`) è cambiato nel 2025:
    le immagini gratuite versionate non sono più pubblicate, serve il tier a pagamento
    o un'alternativa (es. operator CloudNativePG). Gli esempi restano per illustrare
    `needs` e gli ambienti, non come scelta di stack.

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

# Anteprima senza applicare: diff (usa il plugin helm-diff)
helmfile -e production diff

# Con sops per secrets cifrati (la decifratura usa il plugin helm-secrets)
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
helm secrets decrypt secrets/myapp-production.yaml   # test decrypt
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
# Installazione: ct è un binario standalone (non un plugin Helm) — release GitHub
# o brew install chart-testing; richiede helm, git e (per lint) yamllint/yamale
ct version

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

      - uses: azure/setup-helm@v4
        with:
          version: v3.19.0

      - name: Install ct
        uses: helm/chart-testing-action@v2

      - name: List changed charts
        id: list-changed
        run: |
          changed=$(ct list-changed --target-branch main)
          if [[ -n "$changed" ]]; then echo "changed=true" >> "$GITHUB_OUTPUT"; fi

      - name: Lint charts
        run: ct lint --target-branch main

      - name: Create test cluster
        uses: helm/kind-action@v1
        if: steps.list-changed.outputs.changed == 'true'

      - name: Test charts
        if: steps.list-changed.outputs.changed == 'true'
        run: ct install --target-branch main

  build-push-chart:
    needs: lint-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: azure/setup-helm@v4

      - name: Login to Harbor
        run: |
          echo "${{ secrets.HARBOR_PASSWORD }}" | helm registry login registry.company.com \
            --username "${{ secrets.HARBOR_USER }}" \
            --password-stdin

      - name: Package and push chart
        run: |
          # La versione del chart deve essere SemVer valido: "main-<sha>" non lo è.
          # Prerelease SemVer univoca per commit:
          VERSION="0.0.0-sha-${{ github.sha }}"
          helm package ./charts/myapp --version "${VERSION}"
          helm push "myapp-${VERSION}.tgz" oci://registry.company.com/helm-charts

  deploy-staging:
    needs: build-push-chart
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4          # serve helmfile.yaml
      - uses: azure/setup-helm@v4
      # helmfile + plugin (helm-diff, helm-secrets) installati qui, es. helmfile/helmfile-action
      - name: Deploy to staging
        run: |
          helmfile -e staging sync
        env:
          MYAPP_VERSION: "0.0.0-sha-${{ github.sha }}"
          IMAGE_TAG: "${{ github.sha }}"
          KUBECONFIG: "${{ secrets.KUBECONFIG_STAGING }}"

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production            # richiede approvazione manuale (GitHub Environments)
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-helm@v4
      # come per staging: installare helmfile + plugin; KUBECONFIG deve puntare a un
      # file (scrivere il secret su disco) — in alternativa OIDC verso il cluster
      - name: Deploy to production
        run: |
          helmfile -e production sync
        env:
          MYAPP_VERSION: "0.0.0-sha-${{ github.sha }}"
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
          value: "sha-abc123"      # tag immutabile per commit (più sicuro: digest @sha256:...)
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
yq -i '(.spec.source.helm.parameters[] | select(.name == "image.tag") | .value) = "sha-abc123"' \
    apps/production/myapp-application.yaml

git commit -m "chore: bump myapp image to sha-abc123"
git push

# 3. ArgoCD rileva il cambio Git → sync automatico
# 4. la pipeline attende l'esito (Healthy) prima di promuovere
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

## Troubleshooting

### Scenario 1 — Release bloccato in `pending-upgrade`

**Sintomo:** `helm upgrade` fallisce con errore `another operation (install/upgrade/rollback) is in progress`.

**Causa:** Un processo helm precedente è stato interrotto (SIGKILL, timeout CI, pod ucciso) mentre l'upgrade era in corso, lasciando il secret di stato in `pending-upgrade`.

**Soluzione:** Verificare lo stato del secret Helm e forzare un rollback.

```bash
# Identificare il secret con stato pending
kubectl get secret -n production \
    -l owner=helm,status=pending-upgrade \
    -o jsonpath='{.items[*].metadata.name}'

# Rollback alla revisione precedente (resetta lo stato)
helm rollback myapp -n production

# Se rollback non è disponibile (primo deploy fallito), rimuovere il release
helm uninstall myapp -n production --no-hooks
```

---

### Scenario 2 — `helm upgrade --atomic` esegue rollback inatteso

**Sintomo:** L'upgrade parte, i pod vengono creati ma dopo qualche minuto `--atomic` fa rollback automatico senza errori evidenti.

**Causa:** Uno o più pod non raggiungono lo stato `Ready` entro il `--timeout`. Può essere causato da probe liveness/readiness troppo stretti, immagine non disponibile, o risorse (CPU/memory) insufficienti.

**Soluzione:** Investigare i pod prima che vengano rimossi dal rollback.

```bash
# Senza --atomic il release resta `failed` e i pod difettosi restano in cluster
# per l'analisi (con --atomic il rollback li sostituisce subito). Solo in staging
# o con traffico già spostato: in produzione lascia la revisione rotta attiva.
helm upgrade myapp ./mychart \
    --namespace production \
    --values values.production.yaml \
    --wait --timeout 10m

# Analizzare perché i pod non sono Ready
kubectl get pods -n production -l app.kubernetes.io/name=myapp
kubectl describe pod -n production -l app.kubernetes.io/name=myapp | grep -A20 "Events:"
kubectl logs -n production -l app.kubernetes.io/name=myapp --previous

# Verificare events del namespace
kubectl get events -n production --sort-by='.lastTimestamp' | tail -20
```

---

### Scenario 3 — Login OCI registry fallisce in CI

**Sintomo:** `helm push` fallisce con `Error: failed to authorize: failed to fetch anonymous token` oppure `unauthorized: authentication required`.

**Causa:** Il token di autenticazione al registry OCI non è configurato correttamente nella pipeline, oppure il robot account non ha i permessi di push.

**Soluzione:** Verificare le credenziali e il path del registry.

```bash
# Test login manuale con debug
helm registry login registry.company.com \
    --username robot-ci \
    --password "${HARBOR_TOKEN}" \
    --debug

# Per ECR: verificare che il token sia aggiornato (scade ogni 12h)
aws ecr get-login-password --region eu-west-1 | \
    helm registry login \
        --username AWS \
        --password-stdin \
        123456789.dkr.ecr.eu-west-1.amazonaws.com

# Verificare che il chart sia stato pubblicato (pull del metadata)
helm show chart oci://registry.company.com/helm-charts/mychart --version 1.2.0 2>&1

# Lista charts disponibili nel registry (Harbor API)
curl -s -u "robot-ci:${HARBOR_TOKEN}" \
    "https://registry.company.com/api/v2.0/projects/helm-charts/repositories" \
    | jq '.[].name'
```

---

### Scenario 4 — Helmfile sync fallisce per ordine dipendenze non rispettato

**Sintomo:** `helmfile sync` fallisce con `Error: timed out waiting for the condition` su un release che dipende da CRD installate da un altro release (es. cert-manager).

**Causa:** Helmfile non aspetta che i CRD siano registrati nell'API server prima di procedere con i release dipendenti, anche se `needs:` è configurato correttamente. I CRD richiedono tempo per la propagazione.

**Soluzione:** Aggiungere un hook post-install per attendere i CRD, oppure usare `--concurrency 1`.

```bash
# Deploy sequenziale (più lento ma sicuro)
helmfile -e production sync --concurrency 1

# Deploy solo cert-manager prima, poi il resto
helmfile -e production -l name=cert-manager sync
helmfile -e production sync

# Verificare che i CRD siano registrati prima di continuare
kubectl wait --for=condition=Established \
    crd/certificates.cert-manager.io \
    crd/issuers.cert-manager.io \
    --timeout=120s

# Debug: vedere lo stato di tutti i release helmfile
helmfile -e production status

# Log dettagliato per identificare quale release fallisce
helmfile -e production sync --log-level debug 2>&1 | grep -E "(ERROR|WARN|failed)"
```

---

## Riferimenti

- [Helm Upgrade Command](https://helm.sh/docs/helm/helm_upgrade/)
- [Helm OCI Support](https://helm.sh/docs/topics/registries/)
- [Helmfile](https://helmfile.readthedocs.io/)
- [helm-diff Plugin](https://github.com/databus23/helm-diff)
- [Chart Testing (ct)](https://github.com/helm/chart-testing)
- [SOPS + Helm Secrets](https://github.com/jkroepke/helm-secrets)
