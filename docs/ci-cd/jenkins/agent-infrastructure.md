---
title: "Jenkins Agent Infrastructure"
slug: jenkins-agent-infrastructure
category: ci-cd
tags: [jenkins, kubernetes-agent, docker-agent, jcasc, jnlp, websocket, pod-template, agent-scaling]
search_keywords: [Jenkins Kubernetes plugin, Jenkins Kubernetes agent, Pod Template Jenkins, JCasC Jenkins Configuration as Code, JNLP agent Jenkins, WebSocket agent Jenkins, Jenkins Docker agent, Jenkins agent scaling, Kubernetes plugin Jenkins, Jenkins controller high availability, Jenkins PVC cache, Maven cache Jenkins, NPM cache Jenkins, Jenkins agent resources limits, Jenkins namespace isolation, jenkins-inbound-agent, kaniko Jenkins, ephemeral agents Jenkins]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/pipeline-fundamentals, ci-cd/jenkins/enterprise-patterns, ci-cd/jenkins/security-governance, containers/kubernetes/_index]
official_docs: https://plugins.jenkins.io/kubernetes/
status: complete
difficulty: advanced
last_updated: 2026-02-27
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
| **JNLP/WebSocket** | Dinamico o statico | Configurabile | Ambienti con firewall restrittivi |
| **Inbound Agent** | Statico (agente si connette) | Sempre attivo | On-premises senza esporre il controller |

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
              secretBytes: "${base64:K8S_PROD_KUBECONFIG}"  # base64 encoded
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

  # Maven
  mavenInstallations:
    - name: "Maven 3.9"
      properties:
        - installSource:
            installers:
              - maven:
                  id: "3.9.6"

  # Kubernetes Cloud (agenti dinamici)
  kubernetesClouds:
    - name: "kubernetes"
      serverUrl: ""                        # vuoto = usa la ServiceAccount del pod controller
      namespace: "jenkins"
      jenkinsTunnel: "jenkins-agent:50000"
      jenkinsUrl: "http://jenkins-controller:8080"
      containerCapStr: "50"               # max 50 agenti contemporanei
      maxRequestsPerHostStr: "32"
      retentionTimeout: 5                 # minuti idle prima di terminare pod
      connectTimeout: 5
      readTimeout: 15
      podLabels:
        - key: "jenkins/agent"
          value: "true"
      templates:
        - name: "base-pod"
          label: "kubernetes"
          namespace: "jenkins-agents"
          nodeUsageMode: NORMAL
          serviceAccount: "jenkins-agent-sa"
          imagePullPolicy: IfNotPresent
          automountServiceAccountToken: true
          activeDeadlineSeconds: 3600     # pod si termina dopo 1h (safety)
          containers:
            - name: "jnlp"
              image: "jenkins/inbound-agent:latest-jdk21"
              args: "^${computer.jnlpmac} ^${computer.name}"
              resourceRequestMemory: "256Mi"
              resourceLimitMemory: "512Mi"
              resourceRequestCpu: "100m"
              resourceLimitCpu: "500m"
          volumes:
            - persistentVolumeClaim:
                claimName: "maven-cache"
                mountPath: "/root/.m2/repository"
                readOnly: false
          podAnnotations:
            - key: "cluster-autoscaler.kubernetes.io/safe-to-evict"
              value: "false"

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

  # Disable old API auth methods
  remotingSecurity:
    enabled: true

  # URL Jenkins (necessario per link in notifiche)
  location:
    url: "https://jenkins.company.com/"
    adminAddress: "jenkins-admin@company.com"

  # Agenti: porta inbound JNLP
  slaveAgentPort: 50000    # porta TCP per agenti JNLP

  # Numero di executor sul controller (0 = controller non esegue build)
  numExecutors: 0
```

### Caricare JCasC

```bash
# All'avvio del controller, JCasC si carica automaticamente se:
# 1. Plugin "configuration-as-code" installato
# 2. CASC_JENKINS_CONFIG=/etc/jenkins/jenkins.yaml (env var)

# Oppure mount il file via ConfigMap in Kubernetes (vedi sotto)

# Reload a caldo (senza restart)
curl -X POST https://jenkins.company.com/configuration-as-code/reload \
    -H "Authorization: Bearer $TOKEN"
```

---

## Kubernetes Plugin — Pod Templates

### Pod Template Avanzato (YAML inline)

```groovy
// vars/buildJavaApp.groovy — step con pod template dedicato
def call(Map config) {
    podTemplate(
        label: "java-build-${UUID.randomUUID().toString()[0..7]}",   // label unico
        namespace: 'jenkins-agents',
        serviceAccount: 'jenkins-agent-sa',
        nodeSelector: 'workload=build',                               // nodo specifico
        activeDeadlineSeconds: 3600,
        tolerations: [                                                // per nodi tainted
            [key: 'build-node', operator: 'Exists', effect: 'NoSchedule']
        ],
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
                image: 'gcr.io/kaniko-project/executor:v1.23.0-debug',
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
        node("java-build-${UUID.randomUUID().toString()[0..7]}") {
            config.body.call()
        }
    }
}
```

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
  initContainers:
  - name: init-workspace
    image: busybox:1.36
    command: ['sh', '-c', 'chmod -R 777 /workspace']
    volumeMounts:
    - name: workspace
      mountPath: /workspace
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
      value: "-Xmx3g -XX:+UseG1GC -Djava.io.tmpdir=/tmp/maven"
    resources:
      requests:
        memory: "2Gi"
        cpu: "1000m"
      limits:
        memory: "4Gi"
        cpu: "2000m"
    volumeMounts:
    - name: maven-cache
      mountPath: /root/.m2/repository
    - name: workspace
      mountPath: /workspace
  - name: kaniko
    image: gcr.io/kaniko-project/executor:v1.23.0-debug
    command: ["sleep", "infinity"]
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
    - name: workspace
      mountPath: /workspace
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
  - name: workspace
    emptyDir: {}
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
                    sh '/kaniko/executor --context=dir://. --destination=registry.company.com/myapp:${GIT_COMMIT[0..7]}'
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

  Vantaggi: bassa latenza, supporto legacy
  Svantaggi: firewall deve permettere porta 50000

WebSocket (porta 443/HTTPS):
  Agent → [WebSocket su HTTPS] → Controller:443/ws

  Vantaggi: passa firewall enterprise (solo 443), più sicuro
  Svantaggi: latenza leggermente maggiore
```

**Configurare WebSocket per agenti Kubernetes:**

```yaml
# JCasC: abilitare WebSocket per agenti
jenkins:
  inboundAgents:
    webSocket:
      enabled: true

# Nel Pod Template Kubernetes Plugin
containers:
- name: jnlp
  image: jenkins/inbound-agent:latest-jdk21
  args:
    - -url
    - https://jenkins.company.com
    - -webSocket         # usa WebSocket invece di TCP JNLP
    - -secret
    - $(JENKINS_SECRET)
    - -name
    - $(JENKINS_AGENT_NAME)
```

---

## Jenkins Controller HA

In ambienti enterprise, il controller Jenkins deve essere **ad alta disponibilità**. Opzioni:

### 1. Jenkins HA con Kubernetes Statefulset

```yaml
# jenkins-controller StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: jenkins-controller
  namespace: jenkins
spec:
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
            -Dcasc.jenkins.config=/etc/jenkins/jenkins.yaml
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

---
# Pod Disruption Budget — non evictare il controller durante manutenzione nodi
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: jenkins-controller-pdb
  namespace: jenkins
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: jenkins-controller
```

### 2. Backup JENKINS_HOME

```bash
#!/bin/bash
# backup-jenkins.sh — backup JENKINS_HOME su S3 (eseguire da CronJob K8s)

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
# RBAC: Jenkins agent ServiceAccount nel namespace team
apiVersion: v1
kind: ServiceAccount
metadata:
  name: jenkins-agent-sa
  namespace: jenkins-agents-payments
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: jenkins-agent-role
  namespace: jenkins-agents-payments
rules:
- apiGroups: [""]
  resources: ["pods", "pods/exec", "pods/log", "secrets"]
  verbs: ["get", "list", "create", "delete", "patch"]
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["get", "list"]
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

## Riferimenti

- [Kubernetes Plugin for Jenkins](https://plugins.jenkins.io/kubernetes/)
- [JCasC Plugin](https://plugins.jenkins.io/configuration-as-code/)
- [Kaniko on Kubernetes](https://github.com/GoogleContainerTools/kaniko)
- [Jenkins in Kubernetes Best Practices](https://www.jenkins.io/doc/book/installing/kubernetes/)
- [JNLP vs WebSocket Agents](https://www.jenkins.io/doc/book/using/using-agents/)
