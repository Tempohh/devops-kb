---
title: "Chart Avanzato"
slug: chart-avanzato
category: containers
tags: [helm, chart, templates, helpers, hooks, library-charts, sprig, testing, subcharts]
search_keywords: [helm templates, helm _helpers.tpl, helm named templates, helm hooks pre-install, helm hooks post-upgrade, helm library chart, helm sprig functions, helm chart testing, helm subchart, helm conditionals, helm range, helm toYaml, helm tpl, helm lookup, helm required, helm fail]
parent: containers/helm/_index
related: [containers/helm/_index, containers/helm/deployment-produzione, containers/kubernetes/workloads]
official_docs: https://helm.sh/docs/chart_template_guide/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Chart Avanzato

## Chart.yaml — Metadata e Dipendenze

```yaml
# Chart.yaml
apiVersion: v2                      # Helm 3 (v1 = Helm 2)
name: myapp
description: "MyApp — API Service"
type: application                   # oppure 'library' (no installazione diretta)
version: 1.2.0                      # versione del chart (semver)
appVersion: "3.5.1"                 # versione dell'app impacchettata (informativo)
kubeVersion: ">=1.24.0"             # constraint versione Kubernetes
home: https://github.com/company/myapp
sources:
  - https://github.com/company/myapp
maintainers:
  - name: DevOps Team
    email: devops@company.com
icon: https://company.com/logo.png
keywords: [api, backend, service]
annotations:
  category: "Backend"

# Dipendenze da altri charts (sub-charts)
dependencies:
  - name: postgresql
    version: "13.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: postgresql.enabled       # installata solo se postgresql.enabled=true
    alias: db                           # accesso come .Values.db invece di .Values.postgresql

  - name: redis
    version: "17.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled
    tags:
      - cache                           # helm install --set tags.cache=false

  - name: common                        # library chart interno
    version: "1.x.x"
    repository: "file://../common"      # chart locale
```

```bash
# Scaricare le dipendenze in charts/
helm dependency update ./myapp

# Verificare dipendenze aggiornate
helm dependency list ./myapp
```

---

## values.yaml — Schema e Validazione

```yaml
# values.yaml — struttura raccomandata
image:
  repository: registry.company.com/myapp
  tag: ""                               # override con --set image.tag=1.0.0
  pullPolicy: IfNotPresent
  pullSecrets: []

replicaCount: 2

service:
  type: ClusterIP
  port: 8080
  targetPort: 8080

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

serviceAccount:
  create: true
  name: ""
  annotations: {}                       # es. eks.amazonaws.com/role-arn: arn:aws:iam::xxx

postgresql:
  enabled: true                         # installa subchart
  auth:
    existingSecret: myapp-db-secret
    secretKeys:
      adminPasswordKey: postgres-password
      userPasswordKey: password
    database: myapp
    username: myapp

config:
  logLevel: info
  dbMaxConnections: 25
  features: {}

extraEnv: []                            # injection arbitraria env vars
extraVolumes: []
extraVolumeMounts: []
podAnnotations: {}
podLabels: {}
nodeSelector: {}
tolerations: []
affinity: {}
```

```json
// values.schema.json — validazione automatica dei values
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["image"],
  "properties": {
    "image": {
      "type": "object",
      "required": ["repository"],
      "properties": {
        "repository": {"type": "string", "minLength": 1},
        "tag":        {"type": "string"},
        "pullPolicy": {
          "type": "string",
          "enum": ["Always", "IfNotPresent", "Never"]
        }
      }
    },
    "replicaCount": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100
    },
    "service": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["ClusterIP", "NodePort", "LoadBalancer"]
        }
      }
    }
  }
}
```

---

## _helpers.tpl — Named Templates

Il file `templates/_helpers.tpl` contiene template riutilizzabili (prefix `_`, non generano output diretto).

```yaml
{{/* templates/_helpers.tpl */}}

{{/*
Expand the name of the chart.
*/}}
{{- define "myapp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncated at 63 chars (Kubernetes naming limit).
*/}}
{{- define "myapp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels (standard K8s recommended labels).
*/}}
{{- define "myapp.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "myapp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — usati per matchLabels nei Deployment/Service.
IMPORTANTE: non cambiare mai questi dopo il primo deploy
(selector è immutabile in Deployment).
*/}}
{{- define "myapp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "myapp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "myapp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "myapp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image reference completo con digest o tag.
*/}}
{{- define "myapp.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion }}
{{- printf "%s:%s" .Values.image.repository $tag }}
{{- end }}

{{/*
Validazione: fallire se config richiesta non è impostata.
*/}}
{{- define "myapp.validateValues" -}}
{{- if and .Values.ingress.enabled (not .Values.ingress.hosts) }}
{{- fail "ingress.enabled=true richiede almeno un ingress.hosts entry" }}
{{- end }}
{{- end }}
```

---

## Templates — Pattern Comuni

```yaml
{{/* templates/deployment.yaml */}}
{{- include "myapp.validateValues" . }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "myapp.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
  annotations:
    {{- toYaml .Values.podAnnotations | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "myapp.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "myapp.selectorLabels" . | nindent 8 }}
        {{- with .Values.podLabels }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
      annotations:
        # Forza restart su cambio ConfigMap
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      {{- with .Values.image.pullSecrets }}
      imagePullSecrets:
        {{- range . }}
        - name: {{ . }}
        {{- end }}
      {{- end }}
      serviceAccountName: {{ include "myapp.serviceAccountName" . }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: {{ .Chart.Name }}
          image: {{ include "myapp.image" . }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.targetPort }}
          env:
            - name: LOG_LEVEL
              value: {{ .Values.config.logLevel | quote }}
            - name: DB_MAX_CONNECTIONS
              value: {{ .Values.config.dbMaxConnections | quote }}
            {{- if .Values.postgresql.enabled }}
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "myapp.fullname" . }}-db
                  key: url
            {{- end }}
            {{- with .Values.extraEnv }}
            {{- toYaml . | nindent 12 }}
            {{- end }}
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 15
            periodSeconds: 20
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- with .Values.extraVolumeMounts }}
          volumeMounts:
            {{- toYaml . | nindent 12 }}
          {{- end }}
      {{- with .Values.extraVolumes }}
      volumes:
        {{- toYaml . | nindent 8 }}
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

```yaml
{{/* templates/ingress.yaml — condizionale con tpl per annotation */}}
{{- if .Values.ingress.enabled -}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "myapp.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.ingress.className }}
  ingressClassName: {{ .Values.ingress.className }}
  {{- end }}
  {{- if .Values.ingress.tls }}
  tls:
    {{- range .Values.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "myapp.fullname" $ }}
                port:
                  number: {{ $.Values.service.port }}
          {{- end }}
    {{- end }}
{{- end }}
```

```yaml
{{/* templates/hpa.yaml — range su metrics dinamiche */}}
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "myapp.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "myapp.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
{{- end }}
```

---

## Funzioni Sprig Utili

```yaml
{{/* Stringhe */}}
{{ "hello world" | upper }}               # HELLO WORLD
{{ "myapp" | title }}                     # Myapp
{{ printf "%s-%s" "app" "v1" }}           # app-v1
{{ "  spaces  " | trim }}                 # spaces
{{ "hello" | b64enc }}                    # aGVsbG8=
{{ "aGVsbG8=" | b64dec }}                # hello
{{ "hello" | sha256sum }}                 # hash sha256
{{ list "a" "b" "c" | join "," }}         # a,b,c
{{ "nginx:latest" | splitList ":" | first }} # nginx

{{/* Numeri e booleani */}}
{{ add 1 2 }}                             # 3
{{ .Values.replicaCount | int64 }}
{{ "true" | toBool }}                     # true

{{/* Dizionari */}}
{{ $d := dict "key" "value" "key2" "val2" }}
{{ $d | toYaml }}
{{ merge $d .Values.extraConfig }}         # merge di due dicts
{{ get $d "key" }}                         # value
{{ hasKey $d "key" }}                      # true

{{/* Liste */}}
{{ $list := list 1 2 3 }}
{{ $list | len }}                          # 3
{{ append $list 4 }}                       # [1 2 3 4]
{{ without $list 2 }}                      # [1 3]
{{ has $list 2 }}                          # true

{{/* File e lookup */}}
{{/* lookup(apiVersion, kind, namespace, name) — query cluster live */}}
{{- $existing := lookup "v1" "Secret" .Release.Namespace "my-secret" }}
{{- if $existing }}
  {{/* secret esiste già: non sovrascrivere */}}
{{- end }}

{{/* Condizionali avanzati */}}
{{ if and .Values.ingress.enabled .Values.ingress.tls }}
{{/* TLS ingress */}}
{{ end }}

{{ .Values.config.feature | default "disabled" }}   # valore default
{{ required "image.repository è obbligatorio" .Values.image.repository }}
{{ .Values.something | tpl . }}                     # render Values come template

{{/* range con indice */}}
{{- range $index, $item := .Values.items }}
- name: item-{{ $index }}
  value: {{ $item }}
{{- end }}

{{/* range su dict */}}
{{- range $key, $val := .Values.extraLabels }}
{{ $key }}: {{ $val | quote }}
{{- end }}
```

---

## Hooks — Lifecycle del Release

Gli **Hooks** eseguono Job Kubernetes in momenti specifici del lifecycle del release.

```yaml
{{/* templates/hooks/pre-upgrade-migration.yaml */}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "myapp.fullname" . }}-pre-upgrade-migration
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "myapp.labels" . | nindent 4 }}
  annotations:
    # Tipo di hook: quando eseguire
    "helm.sh/hook": pre-upgrade
    # Peso: ordine tra hook dello stesso tipo (numerico, ascending)
    "helm.sh/hook-weight": "0"
    # Cosa fare con il Job dopo l'esecuzione
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  template:
    metadata:
      name: migration
    spec:
      restartPolicy: Never
      serviceAccountName: {{ include "myapp.serviceAccountName" . }}
      containers:
        - name: migration
          image: {{ include "myapp.image" . }}
          command: ["python", "manage.py", "migrate", "--noinput"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "myapp.fullname" . }}-db
                  key: url
  backoffLimit: 3
  activeDeadlineSeconds: 300             # 5 minuti max
```

**Hook delete policies:**

| Policy | Comportamento |
|--------|---------------|
| `before-hook-creation` | Elimina l'hook precedente prima di crearne uno nuovo |
| `hook-succeeded` | Elimina dopo esecuzione con successo |
| `hook-failed` | Elimina se l'hook fallisce |

**Tipi di hook disponibili:**

| Hook | Quando |
|------|--------|
| `pre-install` | Prima di creare le risorse (primo install) |
| `post-install` | Dopo che le risorse sono create |
| `pre-upgrade` | Prima di applicare le modifiche upgrade |
| `post-upgrade` | Dopo upgrade completato |
| `pre-rollback` | Prima del rollback |
| `post-rollback` | Dopo rollback |
| `pre-delete` | Prima di `helm uninstall` |
| `post-delete` | Dopo uninstall completato |
| `test` | Eseguito da `helm test` |

---

## Helm Test

```yaml
{{/* templates/tests/test-connection.yaml */}}
apiVersion: v1
kind: Pod
metadata:
  name: {{ include "myapp.fullname" . }}-test-connection
  namespace: {{ .Release.Namespace }}
  annotations:
    "helm.sh/hook": test                 # eseguito solo da helm test
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox
      command: ['wget', '--no-verbose', '--tries=3',
                '--spider', 'http://{{ include "myapp.fullname" . }}:{{ .Values.service.port }}/healthz']
    - name: db-check
      image: postgres:15
      command:
        - sh
        - -c
        - pg_isready -h {{ include "myapp.fullname" . }}-postgresql -U myapp
```

```bash
# Eseguire i test dopo l'installazione
helm test my-app -n production

# Con output dei log (utile per debug)
helm test my-app -n production --logs
```

---

## Library Charts

Un **Library Chart** (`type: library`) fornisce template riutilizzabili tra più charts ma non genera risorse standalone.

```yaml
{{/* Library chart: common/templates/_deployment.tpl */}}
{{- define "common.deployment" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "common.fullname" . }}
  labels:
    {{- include "common.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount | default 1 }}
  selector:
    matchLabels:
      {{- include "common.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "common.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          {{- with .Values.resources }}
          resources:
            {{- toYaml . | nindent 12 }}
          {{- end }}
{{- end }}
```

```yaml
{{/* App chart che usa la library: templates/deployment.yaml */}}
{{- include "common.deployment" . }}
```

```yaml
# App chart Chart.yaml — dipende dalla library
dependencies:
  - name: common
    version: "1.x.x"
    repository: "oci://registry.company.com/helm-charts"
```

---

## Subcharts e Values Override

```yaml
# values.yaml dell'app parent
# I values per i subcharts usano il nome del chart come chiave

postgresql:                      # corrisponde al nome del subchart
  enabled: true
  primary:
    persistence:
      size: 20Gi
    resources:
      requests:
        memory: 256Mi
      limits:
        memory: 1Gi
  auth:
    existingSecret: myapp-db-secret

# Global values — accessibili da parent E da tutti i subcharts
global:
  imageRegistry: registry.company.com
  imagePullSecrets:
    - name: harbor-pull-secret
  storageClass: fast-ssd
```

```yaml
{{/* Accedere ai global values in qualsiasi subchart */}}
image: "{{ .Values.global.imageRegistry }}/{{ .Values.image.repository }}"
```

---

## Riferimenti

- [Helm Template Guide](https://helm.sh/docs/chart_template_guide/)
- [Sprig Function Documentation](https://masterminds.github.io/sprig/)
- [Helm Hooks](https://helm.sh/docs/topics/charts_hooks/)
- [Helm Chart Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Helm Library Charts](https://helm.sh/docs/topics/library_charts/)
