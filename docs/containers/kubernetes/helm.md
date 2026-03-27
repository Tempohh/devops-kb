---
title: "Helm — Package Manager per Kubernetes"
slug: helm
category: containers
tags: [kubernetes, helm, charts, package-manager, templates, values, helmfile, oci, release-management]
search_keywords: [helm tutorial, helm chart kubernetes, helm deploy, helm package manager, helm templates, helm values, helm upgrade, helm rollback, helm hooks, helmfile, helm oci registry, helm repository, helm release, helm secrets, chart museum, artifact hub, helm diff, helm test, helm plugin, helm lint, helm install, helm uninstall, helm list, helm history, charts helmfile, values.yaml helm, helm override values, helm subchart, helm dependency, umbrella chart, helm 3, helm3]
parent: containers/kubernetes/_index
related: [containers/kubernetes/workloads, containers/kubernetes/operators-crd, containers/kubernetes/sicurezza, containers/kubernetes/architettura]
official_docs: https://helm.sh/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-25
---

# Helm — Package Manager per Kubernetes

## Panoramica

**Helm** è il package manager de-facto per Kubernetes: impacchetta un insieme di manifest YAML in un'unità distribuibile chiamata **Chart**, parametrizzabile tramite file `values.yaml`. Ogni installazione di un chart in un cluster è chiamata **Release**, e Helm traccia la storia di ogni release abilitando rollback in un solo comando.

Helm risolve tre problemi fondamentali: la **parametrizzazione** dei manifest (un unico chart per ambienti diversi), il **lifecycle management** delle applicazioni (install/upgrade/rollback/uninstall atomici), e la **distribuzione** tramite repository pubblici e privati. Helm 3 ha eliminato Tiller (il componente server-side di Helm 2), spostando tutta la logica nel client e memorizzando lo stato come Secret nel namespace target.

Quando **non** usare Helm: per applicazioni semplici con un singolo Deployment + Service, `kubectl apply -k` (Kustomize) è spesso sufficiente e non introduce la complessità del templating. Helm brilla con applicazioni complesse, multi-componente, che devono girare in ambienti multipli con configurazioni diverse.

---

## Concetti Chiave

**Chart** — Pacchetto Helm. Struttura di directory con manifest template + metadati.

**Release** — Un'istanza di un chart installata nel cluster. Lo stesso chart può generare più release (es. `myapp-staging`, `myapp-production`).

**Repository** — Server HTTP che ospita un indice di chart. I chart pubblici si trovano su [Artifact Hub](https://artifacthub.io/).

**Values** — Variabili che personalizzano un chart. Hanno precedenza a cascata: `values.yaml` del chart → `-f custom-values.yaml` → `--set key=value`.

**OCI Registry** — Helm 3.8+ supporta il push/pull di chart verso registry OCI (es. ECR, GCR, Azure Container Registry, Harbor). Sta diventando lo standard per registry privati.

!!! note "Helm 3 vs Helm 2"
    Helm 3 (2019) ha rimosso **Tiller**, il pod server-side che richiedeva ampi privilegi sul cluster. Oggi Helm è un client-only tool: i permessi dipendono dal kubeconfig dell'utente. Non usare mai Helm 2 in nuovi progetti.

!!! warning "Stato delle release — mai modificare manualmente"
    Helm memorizza lo stato di ogni release come Secret `sh.helm.release.v1.<name>.v<revision>` nel namespace target. Modificare i manifest deployati con `kubectl edit`/`kubectl apply` al di fuori di Helm crea **drift**: il prossimo `helm upgrade` sovrascriverà le modifiche manuali senza avvisi.

---

## Struttura di un Chart

```
mychart/
├── Chart.yaml           # Metadati: name, version, appVersion, dependencies
├── values.yaml          # Valori di default
├── values.schema.json   # (opzionale) Schema JSON per validazione values
├── templates/           # Template Go dei manifest K8s
│   ├── _helpers.tpl     # Named templates / helper functions
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── hpa.yaml
│   ├── serviceaccount.yaml
│   ├── NOTES.txt        # Testo stampato dopo helm install/upgrade
│   └── tests/
│       └── test-connection.yaml  # Test eseguiti da "helm test"
├── charts/              # Subchart (dipendenze scaricate)
└── .helmignore          # File da escludere (come .gitignore)
```

**Chart.yaml:**

```yaml
apiVersion: v2                  # v2 = Helm 3
name: myapp
description: "API backend per il servizio X"
type: application               # application | library
version: 1.4.2                  # versione del chart (SemVer)
appVersion: "2.1.0"             # versione dell'applicazione
keywords:
  - api
  - backend
maintainers:
  - name: Team Platform
    email: platform@company.com
dependencies:
  - name: postgresql
    version: "~15.5.0"          # tilde: patch-level range
    repository: "https://charts.bitnami.com/bitnami"
    condition: postgresql.enabled  # abilita/disabilita via values
  - name: redis
    version: ">=19.0.0 <20.0.0"
    repository: "oci://registry-1.docker.io/bitnamicharts"
    condition: redis.enabled
```

---

## Templating — Go Templates in Helm

I template usano la sintassi **Go templates** estesa con le funzioni della libreria **Sprig** e funzioni Helm-specifiche.

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "myapp.fullname" . }}          # helper da _helpers.tpl
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}   # nindent: indenta e aggiunge newline
  annotations:
    checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    # ↑ forza il rolling restart se la ConfigMap cambia
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}             # .Values → values.yaml
  {{- end }}
  selector:
    matchLabels:
      {{- include "myapp.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "myapp.selectorLabels" . | nindent 8 }}
      annotations:
        {{- with .Values.podAnnotations }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "myapp.serviceAccountName" . }}
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "myapp.fullname" . }}-secrets
                  key: database-url
            {{- range $key, $value := .Values.extraEnv }}
            - name: {{ $key }}
              value: {{ $value | quote }}
            {{- end }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- if .Values.probes.enabled }}
          livenessProbe:
            httpGet:
              path: {{ .Values.probes.liveness.path }}
              port: http
            initialDelaySeconds: {{ .Values.probes.liveness.initialDelaySeconds }}
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: {{ .Values.probes.readiness.path }}
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

**_helpers.tpl — Named templates riusabili:**

```yaml
{{/* Genera il fullname della release */}}
{{- define "myapp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/* Labels standard Helm */}}
{{- define "myapp.labels" -}}
helm.sh/chart: {{ include "myapp.chart" . }}
{{ include "myapp.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/* Selector labels */}}
{{- define "myapp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "myapp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

---

## Values — Configurazione e Override

```yaml
# values.yaml (default, committato nel chart)
replicaCount: 2

image:
  repository: registry.company.com/myapp
  tag: ""              # vuoto = usa Chart.AppVersion
  pullPolicy: IfNotPresent

imagePullSecrets: []

nameOverride: ""
fullnameOverride: ""

serviceAccount:
  create: true
  annotations: {}

podAnnotations: {}

service:
  type: ClusterIP
  port: 8080

ingress:
  enabled: false
  className: nginx
  annotations: {}
  hosts:
    - host: myapp.example.com
      paths:
        - path: /
          pathType: Prefix
  tls: []

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

probes:
  enabled: true
  liveness:
    path: /health
    initialDelaySeconds: 30
  readiness:
    path: /ready

postgresql:
  enabled: true
  auth:
    database: myapp
    existingSecret: myapp-db-secret

redis:
  enabled: false

extraEnv: {}

nodeSelector: {}
tolerations: []
affinity: {}
```

**Override per ambiente:**

```yaml
# values-production.yaml (NON committato con credenziali)
replicaCount: 5

image:
  tag: "2.1.0"          # pin della versione specifica in prod

resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 20

ingress:
  enabled: true
  hosts:
    - host: api.company.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-company-com-tls
      hosts:
        - api.company.com

postgresql:
  auth:
    existingSecret: myapp-db-prod-secret
```

---

## Configurazione & Pratica

### Comandi Essenziali

```bash
# ── Repository ──────────────────────────────────────────────────────────────
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update                                     # aggiorna indice locale

# Cerca chart nel repository locale e su Artifact Hub
helm search repo postgresql                          # repository locali
helm search hub nginx --max-col-width 80             # Artifact Hub

# ── Installazione e Upgrade ──────────────────────────────────────────────────
# Installa (crea una nuova release)
helm install myapp ./mychart \
  --namespace myapp \
  --create-namespace \
  -f values-production.yaml \
  --set image.tag=2.1.0 \
  --wait \                     # attende che tutti i pod siano Ready
  --timeout 5m

# Upgrade (aggiorna release esistente)
helm upgrade myapp ./mychart \
  --namespace myapp \
  -f values-production.yaml \
  --set image.tag=2.2.0 \
  --wait --timeout 5m

# Install-or-upgrade in un solo comando (idempotente — usare in CI/CD)
helm upgrade --install myapp ./mychart \
  --namespace myapp \
  --create-namespace \
  -f values-production.yaml \
  --atomic \                   # rollback automatico se upgrade fallisce
  --cleanup-on-fail

# ── Ispezione ────────────────────────────────────────────────────────────────
helm list -n myapp                                   # release nel namespace
helm list -A                                         # tutte le release nel cluster
helm status myapp -n myapp                           # stato release
helm history myapp -n myapp                          # storia revisioni

# Mostra i values effettivi di una release
helm get values myapp -n myapp                       # only overridden values
helm get values myapp -n myapp --all                 # tutti i values (computed)

# Renderizza i template localmente senza installare
helm template myapp ./mychart -f values-production.yaml
helm template myapp ./mychart -f values-production.yaml | kubectl apply --dry-run=server -f -

# Mostra i manifest deployati dalla release corrente
helm get manifest myapp -n myapp

# ── Rollback ─────────────────────────────────────────────────────────────────
helm rollback myapp 3 -n myapp                       # rollback alla revisione 3
helm rollback myapp 0 -n myapp                       # 0 = revisione precedente

# ── Rimozione ────────────────────────────────────────────────────────────────
helm uninstall myapp -n myapp
helm uninstall myapp -n myapp --keep-history         # mantieni storia per audit

# ── Lint e Test ──────────────────────────────────────────────────────────────
helm lint ./mychart                                  # valida sintassi e struttura
helm lint ./mychart -f values-production.yaml        # lint con values specifici
helm test myapp -n myapp                             # esegui test pods del chart
```

### Gestione Dipendenze

```bash
# Scarica le dipendenze dichiarate in Chart.yaml
helm dependency update ./mychart
# → scarica chart in mychart/charts/
# → genera Chart.lock (pin delle versioni)

# Lista dipendenze
helm dependency list ./mychart

# Build (usa Chart.lock se esiste, altrimenti equivale a update)
helm dependency build ./mychart
```

### OCI Registry (Standard per Registry Privati)

```bash
# Login al registry
helm registry login registry.company.com \
  --username $REGISTRY_USER \
  --password $REGISTRY_PASSWORD

# Push chart su OCI registry
helm package ./mychart                               # crea mychart-1.4.2.tgz
helm push mychart-1.4.2.tgz oci://registry.company.com/helm-charts

# Pull e install da OCI registry
helm pull oci://registry.company.com/helm-charts/mychart --version 1.4.2
helm install myapp oci://registry.company.com/helm-charts/mychart \
  --version 1.4.2 \
  -f values-production.yaml

# ECR (AWS) — autenticazione tramite aws CLI
aws ecr get-login-password --region eu-west-1 | \
  helm registry login --username AWS --password-stdin \
  123456789.dkr.ecr.eu-west-1.amazonaws.com
```

---

## Helm Hooks

I **Hooks** permettono di eseguire Job in momenti precisi del lifecycle di una release.

```yaml
# templates/job-db-migrate.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "myapp.fullname" . }}-db-migrate
  annotations:
    "helm.sh/hook": pre-upgrade,pre-install    # quando eseguire
    "helm.sh/hook-weight": "-5"               # ordine (minore = prima)
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
    # ↑ cancella il job precedente prima di crearne uno nuovo E dopo successo
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: db-migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          command: ["python", "manage.py", "migrate", "--noinput"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "myapp.fullname" . }}-secrets
                  key: database-url
```

**Hook types disponibili:**

| Hook | Quando si esegue |
|------|-----------------|
| `pre-install` | Prima del rendering dei template |
| `post-install` | Dopo l'installazione di tutti i manifest |
| `pre-upgrade` | Prima dell'upgrade |
| `post-upgrade` | Dopo l'upgrade completato |
| `pre-rollback` | Prima del rollback |
| `post-rollback` | Dopo il rollback completato |
| `pre-delete` | Prima dell'uninstall |
| `post-delete` | Dopo l'uninstall |
| `test` | Eseguito da `helm test` |

!!! warning "Hook e --atomic"
    Con `--atomic`, se un hook fallisce Helm esegue automaticamente il rollback. Assicurarsi che i hook siano **idempotenti**: un hook `pre-upgrade` potrebbe girare su una release già parzialmente aggiornata durante un rollback.

---

## Helmfile — GitOps per Helm

**Helmfile** è uno strumento che dichiara l'intero stato delle release Helm di un cluster in un file YAML, abilitando un approccio GitOps senza Argo CD o Flux.

```yaml
# helmfile.yaml
repositories:
  - name: bitnami
    url: https://charts.bitnami.com/bitnami
  - name: ingress-nginx
    url: https://kubernetes.github.io/ingress-nginx
  - name: company
    url: oci://registry.company.com/helm-charts
    oci: true

environments:
  staging:
    values:
      - environments/staging/globals.yaml
  production:
    values:
      - environments/production/globals.yaml

releases:
  - name: ingress-nginx
    namespace: ingress-nginx
    createNamespace: true
    chart: ingress-nginx/ingress-nginx
    version: "4.10.0"
    values:
      - charts/ingress-nginx/values.yaml
      - charts/ingress-nginx/values-{{ .Environment.Name }}.yaml   # env-specific

  - name: myapp
    namespace: myapp
    createNamespace: true
    chart: company/myapp
    version: "~1.4.0"
    values:
      - charts/myapp/values.yaml
      - charts/myapp/values-{{ .Environment.Name }}.yaml
    secrets:
      - charts/myapp/secrets-{{ .Environment.Name }}.yaml          # helm-secrets
    needs:
      - ingress-nginx/ingress-nginx                                 # dipendenza
    hooks:
      - events: ["presync"]
        command: "bash"
        args: ["scripts/pre-deploy-check.sh", "{{ .Release.Namespace }}"]

  - name: postgresql
    namespace: myapp
    chart: bitnami/postgresql
    version: "15.5.x"
    values:
      - charts/postgresql/values.yaml
    condition: postgresql.enabled
```

```bash
# Comandi Helmfile
helmfile sync                             # sincronizza tutte le release
helmfile sync -e production               # solo environment production
helmfile diff                             # mostra diff senza applicare
helmfile apply                            # sync solo se ci sono diff
helmfile destroy                          # rimuove tutte le release
helmfile -l name=myapp sync               # solo la release "myapp"
helmfile template                         # renderizza tutti i template
```

---

## Sicurezza e Secrets

```bash
# Installazione helm-secrets plugin (integrazione con SOPS / Vault)
helm plugin install https://github.com/jkroepke/helm-secrets

# Encrypt/Decrypt con SOPS + KMS
sops --encrypt \
  --kms arn:aws:kms:eu-west-1:123456789:key/mrk-abc123 \
  --encrypted-regex '^(data|stringData)$' \
  secrets.yaml > secrets.enc.yaml

# Usa secrets encryptati direttamente con Helm
helm secrets upgrade --install myapp ./mychart \
  -f values.yaml \
  -f secrets.enc.yaml    # helm-secrets decrypta on-the-fly prima del deploy
```

```yaml
# Esempio secrets.enc.yaml (encryptato con SOPS)
# Helm-secrets decrypta automaticamente prima del template rendering
stringData:
    database-url: ENC[AES256_GCM,data:abc123...,type:str]
    api-key: ENC[AES256_GCM,data:xyz789...,type:str]
sops:
    kms:
        - arn: arn:aws:kms:eu-west-1:123456789:key/mrk-abc123
    lastmodified: "2026-03-25T10:00:00Z"
    version: 3.8.1
```

!!! tip "Secrets in CI/CD"
    In pipeline CI/CD, non passare mai secrets con `--set password=xxx` — appaiono nei log e nella history di Helm (`helm get values`). Usare `--set-string` con variabili d'ambiente o `helm-secrets` con SOPS. In alternativa, usare `ExternalSecrets Operator` per iniettare i segreti direttamente da Vault/AWS Secrets Manager senza passarli a Helm.

---

## Best Practices

```
STRUTTURA E SVILUPPO:

1. VERSIONAMENTO SEMANTICO — chart version e appVersion sempre aggiornati
   chart version: cambia ad ogni modifica del chart (template, values)
   appVersion: versione dell'applicazione deployata

2. VALUES SCHEMA — definisci sempre values.schema.json per chart riusabili
   Helm valida i values prima del deploy: errori immediatamente leggibili
   vs errori Go template a runtime difficili da debuggare

3. NAMING — usa "helm.sh/chart" e "app.kubernetes.io/*" labels standard
   Necessario per helm list, helm status, e tool di observability

4. CHECKSUM ANNOTATIONS — forza restart su config change
   checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}

5. RESOURCES — imposta SEMPRE requests e limits nel values.yaml di default
   Un chart senza risorse default è pericoloso in produzione

DEPLOY:

6. --atomic in CI/CD — rollback automatico su fallimento
   helm upgrade --install --atomic --cleanup-on-fail

7. --wait — attendi la disponibilità reale prima di dichiarare successo
   Senza --wait, helm upgrade ritorna OK anche se i pod crashano

8. IMMUTABLE TAGS — in produzione usa tag specifici, mai "latest"
   image.tag: "2.1.0"   # non "latest" o "main"

9. HISTORY LIMIT — limita il numero di revisioni conservate
   helm upgrade ... --history-max 10

SICUREZZA:

10. RBAC MINIMO — ServiceAccount dedicato per ogni release
    Non usare default ServiceAccount in produzione

11. SECRETS — mai in values.yaml in chiaro, usare helm-secrets + SOPS
    oppure ExternalSecrets/Vault Agent Injector
```

!!! tip "helm diff plugin"
    Prima di ogni upgrade in produzione, usa `helm plugin install https://github.com/databus23/helm-diff` e `helm diff upgrade myapp ./mychart -f values-production.yaml`. Mostra esattamente quali manifest cambieranno, come un `git diff` per K8s.

---

## Troubleshooting

**Symptom:** `Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress`

```bash
# Causa: release bloccata in stato "pending-upgrade" (upgrade precedente crashato)
helm history myapp -n myapp
# Cerca revisioni in stato "pending-upgrade" o "pending-install"

# Soluzione: rollback all'ultima revisione buona
helm rollback myapp -n myapp   # rollback alla revisione precedente

# Se rollback non funziona: reset forzato (rimuove la release dallo stato Helm)
# ATTENZIONE: le risorse K8s rimangono nel cluster
kubectl delete secret -n myapp -l owner=helm,name=myapp
# Poi reinstalla da zero
helm install myapp ./mychart -n myapp -f values-production.yaml
```

---

**Symptom:** `Error: rendered manifests contain a resource that already exists`

```bash
# Causa: risorsa K8s creata manualmente (o da altro tool) con lo stesso nome
# Helm non "adotta" risorse esistenti per default

# Soluzione: adotta le risorse esistenti con --force-adopt (Helm 3.13+)
helm upgrade --install myapp ./mychart --force-adopt -n myapp

# Alternativa: annota manualmente la risorsa come gestita da questa release
kubectl annotate deployment myapp \
  meta.helm.sh/release-name=myapp \
  meta.helm.sh/release-namespace=myapp \
  --overwrite
kubectl label deployment myapp \
  app.kubernetes.io/managed-by=Helm \
  --overwrite
```

---

**Symptom:** `helm upgrade` ritorna success ma i pod rimangono in CrashLoopBackOff

```bash
# Causa: --wait non specificato, Helm considera completato il deploy
#        quando le risorse sono accettate dall'API server (non quando sono Ready)

# Debug: guarda cosa è effettivamente deployato
helm get manifest myapp -n myapp | kubectl get -f - --show-kind
kubectl rollout status deployment/myapp -n myapp
kubectl describe pod -l app.kubernetes.io/instance=myapp -n myapp

# Soluzione permanente: usa sempre --wait --timeout 5m in CI/CD
# Soluzione immediata: rollback manuale
helm rollback myapp -n myapp
```

---

**Symptom:** `Error: values don't meet the specifications of the schema(s)`

```bash
# Causa: values.schema.json definisce il tipo/formato e i values forniti non matchano

# Debug: visualizza lo schema
cat mychart/values.schema.json

# Trova il valore che causa il problema (helm template mostra l'errore con più contesto)
helm template myapp ./mychart -f values-bad.yaml 2>&1 | head -30

# Esempio tipico: numero passato come stringa
# Sbagliato:   --set replicaCount="2"
# Corretto:    --set replicaCount=2
```

---

**Symptom:** Template rendering error: `nil pointer evaluating interface {}.field`

```bash
# Causa: values.yaml non definisce una chiave che il template usa senza check
# Esempio: {{ .Values.ingress.tls.secretName }} quando tls non è definito

# Fix nel template: usa "if" per campi opzionali
{{- if .Values.ingress.tls }}
tls:
  - secretName: {{ .Values.ingress.tls.secretName }}
{{- end }}

# Oppure usa "default":
secretName: {{ .Values.ingress.tls.secretName | default "default-tls" }}

# Verifica localmente senza installare:
helm template myapp ./mychart -f values.yaml --debug 2>&1 | less
```

---

## Relazioni

??? info "Workloads Kubernetes — Deployment, StatefulSet"
    Helm genera e gestisce Deployment, StatefulSet e altri workload object K8s. Conoscere i workload è necessario per scrivere template Helm efficaci.

    **Approfondimento completo →** [Workloads](./workloads.md)

??? info "Operators e CRD — estensione di Kubernetes"
    Gli Operator spesso distribuiscono la propria CRD e vengono installati via Helm. Helmfile può orchestrare sia l'Operator che le CR dell'applicazione.

    **Approfondimento completo →** [Operators e CRD](./operators-crd.md)

??? info "Sicurezza Kubernetes — RBAC e ServiceAccount"
    I chart Helm creano ServiceAccount e ClusterRoleBinding: è fondamentale capire RBAC per scrivere chart sicuri.

    **Approfondimento completo →** [Sicurezza](./sicurezza.md)

---

## Riferimenti

- [Helm Documentation](https://helm.sh/docs/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Artifact Hub — public charts](https://artifacthub.io/)
- [Helmfile](https://helmfile.readthedocs.io/)
- [helm-secrets plugin](https://github.com/jkroepke/helm-secrets)
- [helm-diff plugin](https://github.com/databus23/helm-diff)
- [Sprig template functions](https://masterminds.github.io/sprig/)
- [Chart Museum — self-hosted registry](https://chartmuseum.com/)
