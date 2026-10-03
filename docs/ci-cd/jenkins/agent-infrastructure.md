---
title: "Jenkins Agent Infrastructure"
slug: jenkins-agent-infrastructure
category: ci-cd
tags: [jenkins, kubernetes-agent, docker-agent, jcasc, jnlp, websocket, pod-template, agent-scaling]
search_keywords: [Jenkins Kubernetes plugin, Jenkins Kubernetes agent, Pod Template Jenkins, JCasC Jenkins Configuration as Code, JNLP agent Jenkins, WebSocket agent Jenkins, Jenkins Docker agent, Jenkins agent scaling, Kubernetes plugin Jenkins, Jenkins controller high availability, Jenkins PVC cache, Maven cache Jenkins, NPM cache Jenkins, Jenkins agent resources limits, Jenkins namespace isolation, jenkins-inbound-agent, kaniko Jenkins, ephemeral agents Jenkins]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/pipeline-fundamentals, ci-cd/jenkins/enterprise-patterns, ci-cd/jenkins/security-governance, containers/kubernetes/_index]
official_docs: https://plugins.jenkins.io/kubernetes/
status: needs-review
difficulty: advanced
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# Jenkins Agent Infrastructure

## Controller vs Agent — Principio Fondamentale

```
Jenkins Controller (1 istanza, o cluster HA)
├── Gestisce code di build
├── Espone UI e REST API
├── Gestisce Credentials
├── NON esegue build (best practice)
└── Provisiona agenti dinamici

Jenkins Agents (N istanze, dinamiche o statiche)
├── Eseguono build, test, deploy
├── Lifetime: per-build (dinamici) o permanenti (statici)
└── Comunicano con controller via JNLP/SSH/WebSocket
```

**Regola:** nel controller non deve girare nessun job. Usare `agent none` a livello `pipeline { }` e specificare agent in ogni stage.

---

## Tipi di Agent

| Tipo | Provisioning | Lifetime | Use Case |
|------|-------------|---------|---------|
| **Kubernetes Pod** | Dinamico (Kubernetes Plugin) | Per-build, ephemeral | Cloud-native, massima elasticità |
| **Docker** | Dinamico (Docker Plugin) | Per-build | Docker disponibile sul nodo |
| **SSH** | Statico, permanente | Sempre attivo | Macchine fisiche, GPU, licenze software |
| **Inbound Agent (JNLP/WebSocket)** | Statico o dinamico (è l'agente che si connette al controller) | Configurabile | On-premises/NAT/firewall: il controller non deve raggiungere l'agente |

!!! note "JNLP"
    **JNLP** (Java Network Launch Protocol) è il nome storico del protocollo *inbound*: l'agente (`agent.jar`/`remoting`) apre una connessione TCP verso il controller. Oggi il nome resta nell'immagine/container `jnlp` del Kubernetes Plugin, ma il protocollo JNLP originale (Java Web Start) non è più usato; si usa `jenkins/inbound-agent` (remoting su TCP o WebSocket).

---

## JCasC — Jenkins Configuration as Code

**JCasC** (Plugin: `configuration-as-code`) permette di definire l'intera configurazione Jenkins in YAML. Zero click manuali.

### File di Configurazione Completo

```yaml
# jenkins.yaml — configurazione completa del controller

# ── Credenziali di Sistema ─────────────────────────────────────────────────
credentials:
  system:
    domainCredentials:
      - credentials:
          - usernamePassword:
              id: "git-credentials"
              username: "jenkins-bot"
              password: "${GIT_PASSWORD}"       # env var → sicuro
              description: "Git service account"
              scope: GLOBAL

          - string:
              id: "sonarqube-token"
              secret: "${SONAR_TOKEN}"
              description: "SonarQube authentication token"
              scope: GLOBAL

          - file:
              id: "k8s-prod-kubeconfig"
              fileName: "kubeconfig"
              secretBytes: "${base64:${K8S_PROD_KUBECONFIG}}"  # il kubeconfig in chiaro viene codificato base64 da JCasC
              description: "Production Kubernetes kubeconfig"

          - basicSSHUserPrivateKey:
              id: "ssh-deploy-key"
              username: "deploy"
              privateKeySource:
                directEntry:
                  privateKey: "${DEPLOY_SSH_KEY}"

# ── Plugin Configuration ───────────────────────────────────────────────────
unclassified:
  # Shared Libraries
  globalLibraries:
    libraries:
      - name: "company-pipeline-lib"
        defaultVersion: "main"
        implicit: false
        allowVersionOverride: true
        retriever:
          modernSCM:
            scm:
              git:
                remote: "https://git.company.com/platform/jenkins-library.git"
                credentialsId: "git-credentials"

  # SonarQube
  sonarGlobalConfiguration:
    buildWrapperEnabled: true
    installations:
      - name: "company-sonarqube"
        serverUrl: "https://sonar.company.com"
        credentialsId: "sonarqube-token"

  # Slack
  slackNotifier:
    teamDomain: "company-workspace"
    tokenCredentialId: "slack-bot-token"
    iconEmoji: ":jenkins:"
    botUser: true

  # URL Jenkins (necessario per link in notifiche)
  location:
    url: "https://jenkins.company.com/"
    adminAddress: "jenkins-admin@company.com"

# ── Tool (Maven/JDK/...): sezione top-level `tool`, non `unclassified` ─────
# Con agenti a container il Maven è già nell'immagine: serve solo per agenti statici.
tool:
  maven:
    installations:
      - name: "Maven 3.9"
        properties:
          - installSource:
              installers:
                - maven:
                    id: "3.9.9"

# ── Security ───────────────────────────────────────────────────────────────
jenkins:
  securityRealm:
    ldap:
      configurations:
        - server: "ldap.company.com:636"
          rootDN: "dc=company,dc=com"
          userSearchBase: "ou=Users"
          userSearch: "uid={0}"
          groupSearchBase: "ou=Groups"
          managerDN: "cn=jenkins-bind,ou=ServiceAccounts,dc=company,dc=com"
          managerPasswordSecret: "${LDAP_BIND_PASSWORD}"
          displayNameAttributeName: "cn"
          mailAddressAttributeName: "mail"

  authorizationStrategy:
    roleBased:
      roles:
        global:
          - name: "admin"
            description: "Jenkins administrators"
            permissions:
              - "Overall/Administer"
            entries:
              - group: "jenkins-admins"
          - name: "developer"
            description: "Developers — read + build"
            permissions:
              - "Overall/Read"
              - "Job/Build"
              - "Job/Cancel"
              - "Job/Read"
              - "View/Read"
            entries:
              - group: "all-developers"

  # CSRF protection
  crumbIssuer:
    standard:
      excludeClientIPFromCrumb: false

  # Agenti: porta TCP inbound (-1 = disabilitata, se si usa solo WebSocket)
  slaveAgentPort: 50000

  # Kubernetes Cloud (agenti dinamici): sta sotto `jenkins.clouds`, non in `unclassified`
  clouds:
    - kubernetes:
        name: "kubernetes"
        serverUrl: ""                      # vuoto = usa la ServiceAccount del pod controller
        namespace: "jenkins-agents"        # namespace in cui vengono creati i pod agente
        jenkinsUrl: "http://jenkins-controller.jenkins.svc.cluster.local:8080"
        jenkinsTunnel: "jenkins-agent.jenkins.svc.cluster.local:50000"  # ignorato con webSocket: true
        webSocket: true                    # agenti via HTTP(S) WebSocket invece della porta 50000
        containerCapStr: "50"              # max 50 agenti contemporanei
        maxRequestsPerHostStr: "32"
        retentionTimeout: 5                # minuti idle prima di terminare pod
        connectTimeout: 5
        readTimeout: 15
        podLabels:
          - key: "jenkins/agent"
            value: "true"
        templates:
          - name: "base-pod"
            label: "kubernetes"
            nodeUsageMode: NORMAL
            serviceAccount: "jenkins-agent-sa"
            idleMinutes: 0
            activeDeadlineSeconds: 3600    # pod si termina dopo 1h (safety)
            # Nessun `args`: il plugin inietta JENKINS_URL/JENKINS_SECRET/JENKINS_AGENT_NAME
            # come env var e l'entrypoint di jenkins/inbound-agent le usa da solo.
            containers:
              - name: "jnlp"
                image: "jenkins/inbound-agent:latest-jdk21"   # in produzione: pinnare un tag/digest
                resourceRequestMemory: "256Mi"
                resourceLimitMemory: "512Mi"
                resourceRequestCpu: "100m"
                resourceLimitCpu: "500m"
            volumes:
              - persistentVolumeClaim:
                  claimName: "maven-cache-pvc"
                  mountPath: "/home/jenkins/.m2/repository"
                  readOnly: false
            annotations:
              - key: "cluster-autoscaler.kubernetes.io/safe-to-evict"
                value: "false"

  # Numero di executor sul controller (0 = controller non esegue build)
  numExecutors: 0
```

### Caricare JCasC

```bash
# All'avvio del controller, JCasC si carica automaticamente se:
# 1. Plugin "configuration-as-code" installato
# 2. CASC_JENKINS_CONFIG=/etc/jenkins/jenkins.yaml (env var)

# Oppure mount il file via ConfigMap in Kubernetes (vedi sotto)

# Reload a caldo (senza restart). Jenkins non accetta "Bearer": usare utente + API token
# (con API token il crumb CSRF non è richiesto)
curl -X POST https://jenkins.company.com/configuration-as-code/reload \
    -u "admin-user:$API_TOKEN"
```

---

## Kubernetes Plugin — Pod Templates

### Pod Template Avanzato (YAML inline)

```groovy
// vars/buildJavaApp.groovy — step con pod template dedicato
def call(Closure body) {
    // Il label deve essere identico in podTemplate e node(): generarlo UNA volta sola
    def label = "java-build-${UUID.randomUUID().toString().take(8)}"
    // Nota: `tolerations` non è un parametro dello step podTemplate: per nodi tainted
    // usare il pod template YAML (sezione successiva).
    podTemplate(
        label: label,
        namespace: 'jenkins-agents',
        serviceAccount: 'jenkins-agent-sa',
        nodeSelector: 'workload=build',                               // nodo specifico
        activeDeadlineSeconds: 3600,
        containers: [
            containerTemplate(
                name: 'jnlp',
                image: 'jenkins/inbound-agent:latest-jdk21',
                resourceRequestMemory: '256Mi',
                resourceLimitMemory: '512Mi',
                resourceRequestCpu: '100m',
                resourceLimitCpu: '500m'
            ),
            containerTemplate(
                name: 'maven',
                image: 'maven:3.9-eclipse-temurin-21',
                command: 'sleep',
                args: '99d',
                resourceRequestMemory: '2Gi',
                resourceLimitMemory: '4Gi',
                resourceRequestCpu: '1000m',
                resourceLimitCpu: '2000m',
                envVars: [
                    envVar(key: 'MAVEN_OPTS', value: '-Xmx3g -XX:+UseG1GC'),
                    envVar(key: 'JAVA_TOOL_OPTIONS', value: '-Djdk.tls.client.protocols=TLSv1.2')
                ]
            ),
            containerTemplate(
                name: 'kaniko',
                image: 'gcr.io/kaniko-project/executor:v1.23.0-debug',   // vedi nota Kaniko archiviato
                command: 'sleep',
                args: '99d',
                resourceRequestMemory: '1Gi',
                resourceLimitMemory: '2Gi',
                resourceRequestCpu: '500m',
                resourceLimitCpu: '1000m'
            ),
            containerTemplate(
                name: 'sonar-scanner',
                image: 'sonarsource/sonar-scanner-cli:5',
                command: 'sleep',
                args: '99d',
                resourceRequestMemory: '512Mi',
                resourceLimitMemory: '1Gi'
            )
        ],
        volumes: [
            // Cache Maven — PVC condiviso tra build (velocizza dipendenze Maven)
            persistentVolumeClaim(
                claimName: 'maven-cache-pvc',
                mountPath: '/root/.m2/repository',
                readOnly: false
            ),
            // Docker socket (se necessario, ma preferire Kaniko)
            // hostPathVolume(mountPath: '/var/run/docker.sock', hostPath: '/var/run/docker.sock'),

            // Kaniko config (credentials per push su registry)
            secretVolume(
                secretName: 'registry-docker-config',
                mountPath: '/kaniko/.docker'
            ),

            // Cache condivisa per npm/node_modules
            persistentVolumeClaim(
                claimName: 'npm-cache-pvc',
                mountPath: '/root/.npm',
                readOnly: false
            ),

            // Temp per build intermedi
            emptyDirVolume(mountPath: '/tmp/build', memory: false)
        ],
        annotations: [
            podAnnotation(key: 'cluster-autoscaler.kubernetes.io/safe-to-evict', value: 'false'),
            podAnnotation(key: 'prometheus.io/scrape', value: 'false')
        ],
        imagePullSecrets: ['registry-pull-secret']
    ) {
        node(label) {
            body()
        }
    }
}
```

!!! warning "Kaniko: progetto archiviato"
    Il repository `GoogleContainerTools/kaniko` è stato **archiviato da Google** (giugno 2025): niente più release né fix di sicurezza dall'upstream, e le immagini `gcr.io/kaniko-project/executor` non ricevono nuovi tag. Per i build di immagini in pod senza Docker socket valutare **Buildah** (daemonless, rootless), **BuildKit** rootless (`moby/buildkit:rootless`) o un fork mantenuto (es. quello di Chainguard). Il pattern (container dedicato + `sleep` + `container('...')`) resta identico; cambia solo l'immagine e il comando di build.
    <!-- REVIEW: verificare tag/registry del fork mantenuto di Kaniko e aggiungere un esempio Buildah/BuildKit rootless -->

### Pod Template via YAML (più manutenibile)

```yaml
# jenkins-library/resources/pod-templates/java-build.yaml
apiVersion: v1
kind: Pod
metadata:
  labels:
    jenkins/agent: "true"
spec:
  serviceAccountName: jenkins-agent-sa
  automountServiceAccountToken: true
  securityContext:
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
  tolerations:
  - key: "workload"
    operator: "Equal"
    value: "build"
    effect: "NoSchedule"
  nodeSelector:
    workload: build
  # fsGroup rende i volumi scrivibili dall'utente 1000: niente init container con chmod 777.
  # Il workspace del build (/home/jenkins/agent) è un emptyDir aggiunto dal plugin.
  containers:
  - name: jnlp
    image: jenkins/inbound-agent:latest-jdk21
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "500m"
  - name: maven
    image: maven:3.9-eclipse-temurin-21
    command: ["sleep", "infinity"]
    env:
    - name: MAVEN_OPTS
      # il pod gira come UID 1000 (non root): $HOME non è /root, quindi la cache va
      # puntata esplicitamente
      value: "-Xmx3g -XX:+UseG1GC -Dmaven.repo.local=/cache/m2"
    resources:
      requests:
        memory: "2Gi"
        cpu: "1000m"
      limits:
        memory: "4Gi"
        cpu: "2000m"
    volumeMounts:
    - name: maven-cache
      mountPath: /cache/m2
  - name: kaniko
    image: gcr.io/kaniko-project/executor:v1.23.0-debug   # archiviato, vedi warning sopra
    command: ["sleep", "infinity"]
    securityContext:
      runAsUser: 0          # Kaniko deve essere root per operare sul filesystem dei layer
    resources:
      requests:
        memory: "512Mi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1000m"
    volumeMounts:
    - name: docker-config
      mountPath: /kaniko/.docker
  volumes:
  - name: maven-cache
    persistentVolumeClaim:
      claimName: maven-cache-pvc
  - name: docker-config
    secret:
      secretName: registry-docker-config
      items:
      - key: .dockerconfigjson
        path: config.json
  activeDeadlineSeconds: 3600
```

```groovy
// Uso del Pod Template da YAML in pipeline
pipeline {
    agent {
        kubernetes {
            yaml libraryResource('pod-templates/java-build.yaml')
            defaultContainer 'maven'     // container di default per sh steps
        }
    }
    stages {
        stage('Build') {
            steps {
                // Eseguito in container 'maven' (default)
                sh 'mvn package -DskipTests'
            }
        }
        stage('Docker') {
            steps {
                container('kaniko') {
                    // stringa Groovy (doppi apici): `${...}` è interpolato da Jenkins, non dalla shell
                    sh "/kaniko/executor --context=dir://${env.WORKSPACE} --destination=registry.company.com/myapp:${env.GIT_COMMIT.take(8)}"
                }
            }
        }
    }
}
```

---

## Caching delle Dipendenze

```yaml
# PVC per cache Maven (ReadWriteMany per accesso da più pod contemporaneamente)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: maven-cache-pvc
  namespace: jenkins-agents
spec:
  accessModes:
    - ReadWriteMany           # NFS o storage che supporta RWX
  resources:
    requests:
      storage: 50Gi
  storageClassName: nfs-storage

---
# PVC per cache npm
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: npm-cache-pvc
  namespace: jenkins-agents
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
  storageClassName: nfs-storage

---
# PVC per cache Gradle
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: gradle-cache-pvc
  namespace: jenkins-agents
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 30Gi
  storageClassName: nfs-storage
```

!!! warning "Cache condivisa in scrittura = rischio di corruzione"
    Maven/Gradle/npm non coordinano scritture concorrenti sulla stessa directory: due build parallele che scaricano la stessa dipendenza possono lasciare file parziali nella cache (`.lastUpdated`, checksum errati). Su NFS si aggiunge latenza di metadata che spesso annulla il guadagno. Mitigazioni: cache **per-job/per-branch** (PVC `ReadWriteOnce` o `volumeClaimTemplate` di un pod template), cache in sola lettura pre-popolata + scrittura locale, oppure un **repository proxy** (Nexus/Artifactory) davanti a Maven/npm, che è la soluzione più robusta.

**Alternative alla PVC per cache:**
- **Kaniko `--cache`**: cache layer Docker su registry
- **Buildkit remote cache**: cache build su registry OCI
- **Nexus/Artifactory proxy**: proxy repository che cachea dipendenze upstream
- **Init container**: pre-popola cache da snapshot S3/GCS all'avvio del pod

---

## JNLP vs WebSocket Inbound Agents

```
JNLP (porta TCP 50000):
  Agent → [apre connessione TCP] → Controller:50000

  Vantaggi: nessuna dipendenza dal reverse proxy, protocollo storico
  Svantaggi: serve una porta aggiuntiva (50000) esposta/instradata e un Service dedicato

WebSocket (stessa porta HTTP/HTTPS della UI):
  Agent → [HTTP upgrade → WebSocket] → Controller:443

  Vantaggi: una sola porta (443) già aperta, niente Service/porta 50000, TLS terminato
            dal reverse proxy/ingress
  Svantaggi: ingress/LB devono supportare l'upgrade WebSocket e timeout lunghi
```

**Perché WebSocket:** la connessione resta una singola richiesta HTTP "upgradata", quindi passa dove è aperta solo la 443 e riusa TLS/auth dell'ingress. Richiede Jenkins ≥ 2.217 e agent remoting ≥ 4.0 (le immagini `jenkins/inbound-agent` correnti lo soddisfano). Non è "più sicuro" in sé: la sicurezza dipende da TLS e dal secret dell'agente in entrambi i casi.

**Abilitare WebSocket per agenti Kubernetes:** è un'opzione del *cloud* (`webSocket: true`, vedi `jenkins.clouds` in JCasC sopra, o checkbox "WebSocket" nella configurazione del cloud). Il plugin passa all'agente `JENKINS_URL`, `JENKINS_SECRET`, `JENKINS_AGENT_NAME` e `JENKINS_WEB_SOCKET=true`; l'entrypoint dell'immagine li traduce negli argomenti giusti, quindi non serve scrivere `args` a mano.

Per un agente **statico** avviato a mano:

```bash
java -jar agent.jar -url https://jenkins.company.com -webSocket \
     -name build-agent-1 -secret "$AGENT_SECRET" -workDir /home/jenkins/agent
```

---

## Jenkins Controller HA

Il controller Jenkins open source è **single-active**: tiene stato (code, build in corso, config) in `JENKINS_HOME` e non supporta più repliche attive. Con `replicas: 1` si ottiene quindi **recovery automatico** (Kubernetes riavvia il pod, anche su un altro nodo se lo storage lo consente), non vera alta disponibilità: durante il riavvio la UI è giù e le build in corso su agenti dinamici falliscono o restano in attesa di riconnessione. Vera HA active/active esiste solo in prodotti commerciali (CloudBees CI). In pratica si riduce l'impatto con: storage veloce e replicato, backup frequenti, JCasC + pipeline versionati (ricostruibili da zero), agenti effimeri.

### 1. Controller su Kubernetes StatefulSet (recovery automatico)

```yaml
# jenkins-controller StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: jenkins-controller
  namespace: jenkins
spec:
  serviceName: jenkins-controller       # headless Service associato (obbligatorio in uno StatefulSet)
  replicas: 1                           # Jenkins tradizionale: SEMPRE 1 replica (non distribuito)
  selector:
    matchLabels:
      app: jenkins-controller
  template:
    spec:
      serviceAccountName: jenkins-controller-sa
      securityContext:
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: jenkins
        image: jenkins/jenkins:lts-jdk21
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 50000
          name: agent
        env:
        - name: JAVA_OPTS
          value: >-
            -Xmx4g -Xms2g
            -XX:+UseG1GC
            -XX:MaxGCPauseMillis=200
            -Djenkins.install.runSetupWizard=false
        - name: CASC_JENKINS_CONFIG
          value: /etc/jenkins/jenkins.yaml
        resources:
          requests:
            memory: "4Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
        volumeMounts:
        - name: jenkins-home
          mountPath: /var/jenkins_home
        - name: jenkins-config
          mountPath: /etc/jenkins
          readOnly: true
        livenessProbe:
          httpGet:
            path: /login
            port: 8080
          initialDelaySeconds: 90
          periodSeconds: 30
          failureThreshold: 5
        readinessProbe:
          httpGet:
            path: /login
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 10
      volumes:
      - name: jenkins-config
        configMap:
          name: jenkins-casc-config
  volumeClaimTemplates:
  - metadata:
      name: jenkins-home
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi

```

!!! warning "Niente PodDisruptionBudget `minAvailable: 1` con 1 replica"
    Con una sola replica un PDB `minAvailable: 1` blocca **ogni** eviction volontaria: `kubectl drain` non completa mai e gli upgrade dei nodi si bloccano. Accettare il riavvio controllato (il controller riparte da `JENKINS_HOME`) oppure far drenare il nodo a un orario concordato, dopo `Manage Jenkins → Prepare for Shutdown` per non interrompere le build.

### 2. Backup JENKINS_HOME

```bash
#!/bin/bash
# backup-jenkins.sh — backup JENKINS_HOME su S3 (eseguire da CronJob K8s)
# Nota: il PVC del controller è RWO, quindi il CronJob deve girare sullo stesso nodo del
# controller; in alternativa preferire VolumeSnapshot CSI o il plugin ThinBackup.
# Con JCasC + pipeline in Git, il backup serve soprattutto per cronologia build e credenziali.

set -euo pipefail

JENKINS_HOME="/var/jenkins_home"
S3_BUCKET="s3://company-jenkins-backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="jenkins-home-${TIMESTAMP}.tar.gz"

echo "Creating backup ${BACKUP_FILE}..."
tar czf /tmp/${BACKUP_FILE} \
    --exclude="${JENKINS_HOME}/workspace" \
    --exclude="${JENKINS_HOME}/logs" \
    --exclude="${JENKINS_HOME}/.cache" \
    ${JENKINS_HOME}

echo "Uploading to S3..."
aws s3 cp /tmp/${BACKUP_FILE} ${S3_BUCKET}/${BACKUP_FILE}

# Mantieni solo ultimi 30 backup
aws s3 ls ${S3_BUCKET}/ | sort | head -n -30 | awk '{print $4}' | \
    xargs -I {} aws s3 rm ${S3_BUCKET}/{}

echo "Backup completed: ${BACKUP_FILE}"
rm /tmp/${BACKUP_FILE}
```

---

## Namespace Isolation per Team

```yaml
# Separare gli agenti per team: ogni team ha il proprio namespace

# namespace team-payments
apiVersion: v1
kind: Namespace
metadata:
  name: jenkins-agents-payments
  labels:
    team: payments
---
# ServiceAccount dei pod agente: nessun permesso sull'API Kubernetes, a meno che
# la pipeline non debba deployare (in quel caso Role dedicata e minima)
apiVersion: v1
kind: ServiceAccount
metadata:
  name: jenkins-agent-sa
  namespace: jenkins-agents-payments
automountServiceAccountToken: false
---
# Chi crea/elimina i pod agente è il CONTROLLER (Kubernetes Plugin), non l'agente:
# la Role va concessa alla ServiceAccount del controller, nel namespace del team
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: jenkins-controller-agents
  namespace: jenkins-agents-payments
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["create", "delete", "get", "list", "patch", "update", "watch"]
- apiGroups: [""]
  resources: ["pods/exec"]
  verbs: ["create", "get"]            # usato da container('x') { sh ... }
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: jenkins-controller-agents
  namespace: jenkins-agents-payments
subjects:
- kind: ServiceAccount
  name: jenkins-controller-sa
  namespace: jenkins
roleRef:
  kind: Role
  name: jenkins-controller-agents
  apiGroup: rbac.authorization.k8s.io
---
# ResourceQuota per il namespace del team
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: jenkins-agents-payments
spec:
  hard:
    pods: "20"
    requests.cpu: "10"
    requests.memory: "40Gi"
    limits.cpu: "20"
    limits.memory: "80Gi"
```

---

## Troubleshooting

### Scenario 1 — Pod agente bloccato in Pending

**Sintomo:** Il job Jenkins rimane in coda indefinitamente, il pod agente risulta `Pending` nel namespace `jenkins-agents`.

**Causa:** Risorse insufficienti nel cluster (CPU/memory), nessun nodo con il `nodeSelector` richiesto, o PVC non legato (Unbound).

**Soluzione:** Verificare eventi del pod e stato dei PVC.

```bash
# Controllare eventi del pod bloccato
kubectl describe pod -n jenkins-agents -l jenkins/agent=true | grep -A 20 Events

# Verificare nodi disponibili con il label richiesto
kubectl get nodes -l workload=build

# Controllare stato PVC
kubectl get pvc -n jenkins-agents
kubectl describe pvc maven-cache-pvc -n jenkins-agents

# Verificare risorse disponibili sui nodi
kubectl describe nodes | grep -A 10 "Allocated resources"
```

---

### Scenario 2 — Agente non riesce a connettersi al controller (JNLP timeout)

**Sintomo:** Il pod agente viene creato ma il container `jnlp` crasha con errori `Connection refused` o `Failed to connect to jenkins-controller:50000`.

**Causa:** La porta 50000 non è raggiungibile dal namespace agenti (NetworkPolicy restrittiva), il Service `jenkins-agent` non punta al controller, o `jenkinsTunnel` in JCasC è configurato erroneamente.

**Soluzione:**

```bash
# Verificare che il Service jenkins-agent esista e punti alla porta 50000
kubectl get svc -n jenkins jenkins-agent
kubectl describe svc -n jenkins jenkins-agent

# Test di connettività dalla NetworkPolicy
kubectl run test-conn --rm -it --image=busybox -n jenkins-agents -- \
    nc -zv jenkins-agent.jenkins.svc.cluster.local 50000

# Controllare log del container jnlp
kubectl logs -n jenkins-agents <pod-name> -c jnlp --previous

# Se si usa WebSocket: verificare che l'ingress/LB supporti upgrade WebSocket
kubectl get ingress -n jenkins
```

---

### Scenario 3 — Build lenta per mancanza di cache dipendenze

**Sintomo:** Ogni build Maven/NPM scarica tutte le dipendenze da zero, anche con PVC di cache configurato.

**Causa:** Il PVC `ReadWriteMany` non è montato correttamente, il `mountPath` non corrisponde alla directory di cache del tool, o il `storageClassName` NFS non è disponibile.

**Soluzione:**

```bash
# Verificare che il PVC sia montato nel pod agente
kubectl exec -n jenkins-agents <pod-name> -c maven -- df -h /root/.m2/repository

# Verificare contenuto della cache
kubectl exec -n jenkins-agents <pod-name> -c maven -- ls -la /root/.m2/repository

# Controllare che lo StorageClass NFS sia disponibile e funzionante
kubectl get storageclass
kubectl get pv | grep maven-cache

# Se la cache è vuota: pre-popolare con un job di warm-up
kubectl exec -n jenkins-agents <pod-name> -c maven -- \
    mvn dependency:resolve -f /path/to/pom.xml
```

---

### Scenario 4 — JCasC non viene applicato all'avvio del controller

**Sintomo:** Il controller Jenkins si avvia con la configurazione di default (wizard di setup attivo, nessun cloud Kubernetes configurato), ignorando il file `jenkins.yaml`.

**Causa:** La variabile d'ambiente `CASC_JENKINS_CONFIG` non è impostata, il ConfigMap non è montato correttamente, o il plugin `configuration-as-code` non è installato.

**Soluzione:**

```bash
# Verificare che la env var sia presente nel pod controller
kubectl exec -n jenkins <jenkins-pod> -- env | grep CASC

# Controllare che il ConfigMap sia montato
kubectl exec -n jenkins <jenkins-pod> -- ls -la /etc/jenkins/
kubectl exec -n jenkins <jenkins-pod> -- cat /etc/jenkins/jenkins.yaml | head -20

# Verificare che il plugin JCasC sia installato
kubectl exec -n jenkins <jenkins-pod> -- \
    ls /var/jenkins_home/plugins/ | grep configuration-as-code

# Forzare reload della configurazione a caldo (senza restart)
JENKINS_URL="https://jenkins.company.com"
curl -s -o /dev/null -w "%{http_code}" -X POST \
    "${JENKINS_URL}/configuration-as-code/reload" \
    -u "admin-user:${API_TOKEN}"

# Verificare log di avvio per errori JCasC
kubectl logs -n jenkins <jenkins-pod> | grep -i "casc\|configuration-as-code"
```

---

## Riferimenti

- [Kubernetes Plugin for Jenkins](https://plugins.jenkins.io/kubernetes/)
- [JCasC Plugin](https://plugins.jenkins.io/configuration-as-code/)
- [Kaniko on Kubernetes](https://github.com/GoogleContainerTools/kaniko)
- [Jenkins in Kubernetes Best Practices](https://www.jenkins.io/doc/book/installing/kubernetes/)
- [JNLP vs WebSocket Agents](https://www.jenkins.io/doc/book/using/using-agents/)
