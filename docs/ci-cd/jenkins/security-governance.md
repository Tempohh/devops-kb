---
title: "Jenkins Security & Governance"
slug: security-governance
category: ci-cd
tags: [jenkins, security, rbac, credentials, sso, ldap, saml, audit, script-security, compliance]
search_keywords: [jenkins security, jenkins rbac, role strategy plugin, matrix authorization, jenkins credentials api, script approval, script sandbox, jenkins sso, jenkins ldap, jenkins saml, jenkins audit trail, jenkins hardening, jenkins tls, CasC security, pipeline security, withCredentials, kubernetes secrets jenkins, jenkins compliance]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/agent-infrastructure, ci-cd/jenkins/enterprise-patterns, ci-cd/jenkins/shared-libraries, security/secret-management, security/autenticazione]
official_docs: https://www.jenkins.io/doc/book/security/
status: complete
difficulty: expert
last_updated: 2026-03-28
---

# Jenkins Security & Governance

## Panoramica

La security di Jenkins in contesto enterprise copre tre dimensioni: **autenticazione** (chi può accedere), **autorizzazione** (cosa può fare), e **protezione dei segreti** (come gestire credenziali in pipeline). A queste si aggiunge la **governance**, ovvero la tracciabilità di chi ha fatto cosa e quando, la conformità alle policy organizzative, e la protezione del controller stesso da codice Groovy malevolo. Un Jenkins non hardened è di fatto un sistema di esecuzione di codice arbitrario con accesso alle credenziali di produzione.

## Autenticazione — SSO, LDAP, SAML

### Integrazione LDAP/Active Directory

```yaml
# jenkins-casc.yaml — security realm LDAP
jenkins:
  securityRealm:
    ldap:
      configurations:
        - server: "ldaps://dc01.corp.example.com:636"
          rootDN: "dc=corp,dc=example,dc=com"
          managerDN: "cn=jenkins-bind,ou=service-accounts,dc=corp,dc=example,dc=com"
          managerPasswordSecret: "${LDAP_BIND_PASSWORD}"
          userSearchBase: "ou=users,dc=corp,dc=example,dc=com"
          userSearch: "sAMAccountName={0}"       # Active Directory
          groupSearchBase: "ou=groups,dc=corp,dc=example,dc=com"
          groupSearchFilter: "(member={0})"      # memberOf per AD
          groupMembershipStrategy:
            fromGroupSearch:
              filter: "(|(cn=jenkins-*)(cn=devops-*))"
          displayNameAttributeName: "displayName"
          mailAddressAttributeName: "mail"
          # TLS: verificare certificato del DC
          inhibitInferRootDN: false
      userIdStrategy:
        caseInsensitive: {}   # AD non è case-sensitive
      groupIdStrategy:
        caseInsensitive: {}
      cache:
        size: 100
        ttl: 300              # secondi, default 300
```

### Integrazione SAML 2.0 (Okta/Azure AD/Keycloak)

```yaml
# jenkins-casc.yaml — security realm SAML
jenkins:
  securityRealm:
    saml:
      idpMetadataConfiguration:
        # URL del metadata endpoint del provider (si aggiorna automaticamente)
        url: "https://okta.example.com/app/jenkins/sso/saml/metadata"
        period: 3600  # refresh ogni ora
      displayNameAttributeName: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/displayname"
      groupsAttributeName: "groups"    # claim SAML con i gruppi
      usernameAttributeName: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn"
      emailAttributeName: "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
      maximumAuthenticationLifetime: 86400  # 24h
      usernameCaseConversion: "none"
      # SP (Service Provider) configuration
      spMetadataUrl: "https://jenkins.corp.example.com/securityRealm/metadata"
      binding: "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      # Firma e cifratura
      signRequests: true
      keyStorePath: "/var/jenkins_home/saml-keystore.jks"
      keyStorePassword: "${SAML_KEYSTORE_PASSWORD}"
      privateKeyAlias: "jenkins-sp"
      privateKeyPassword: "${SAML_KEY_PASSWORD}"
```

### GitHub OAuth (per ambienti cloud-native)

```yaml
jenkins:
  securityRealm:
    github:
      githubWebUri: "https://github.com"
      githubApiUri: "https://api.github.com"
      clientID: "${GITHUB_OAUTH_CLIENT_ID}"
      clientSecret: "${GITHUB_OAUTH_CLIENT_SECRET}"
      oauthScopes: "read:org,user:email"
```

## Autorizzazione — RBAC con Role Strategy Plugin

### Matrix Authorization (semplice)

```yaml
# jenkins-casc.yaml — matrice globale
jenkins:
  authorizationStrategy:
    globalMatrix:
      permissions:
        # Amministratori
        - "GROUP:Overall/Administer:jenkins-admins"
        # Read-only per tutti gli autenticati
        - "GROUP:Overall/Read:authenticated"
        - "GROUP:Overall/Read:anonymous"   # rimuovere se non richiesto
        # Developer: build e lettura log
        - "GROUP:Job/Build:jenkins-developers"
        - "GROUP:Job/Cancel:jenkins-developers"
        - "GROUP:Job/Read:jenkins-developers"
        - "GROUP:Run/Update:jenkins-developers"
        # QA: solo lettura e trigger
        - "GROUP:Job/Build:jenkins-qa"
        - "GROUP:Job/Read:jenkins-qa"
```

### Role Strategy (autorizzazione granulare per folder/job)

```yaml
jenkins:
  authorizationStrategy:
    roleStrategy:
      dangerouslyAllowAnyoneToCreateRoles: false
      rolesToCreate:
        # Ruoli globali
        global:
          - name: "admin"
            description: "Amministratori Jenkins"
            permissions:
              - "Overall/Administer"
            assignments:
              - "jenkins-admins"   # gruppo LDAP

          - name: "viewer"
            description: "Read-only per tutti"
            permissions:
              - "Overall/Read"
              - "Job/Read"
              - "Run/Replay"       # solo se si vuole allow replay
            assignments:
              - "authenticated"

        # Ruoli per folder (pattern regex)
        items:
          - name: "team-backend-developer"
            description: "Developer del team backend"
            pattern: "backend/.*"   # regex: match folder backend e tutto sotto
            permissions:
              - "Job/Build"
              - "Job/Cancel"
              - "Job/Read"
              - "Job/Workspace"
              - "Run/Update"
              - "View/Read"
            assignments:
              - "jenkins-team-backend"

          - name: "team-backend-release"
            description: "Release manager backend"
            pattern: "backend/.*"
            permissions:
              - "Job/Build"
              - "Job/Configure"    # può modificare la pipeline
              - "Job/Read"
              - "Run/Replay"
              - "View/Read"
              - "Credentials/View" # può vedere (non leggere) le credenziali
            assignments:
              - "jenkins-release-managers"

          - name: "team-frontend-developer"
            pattern: "frontend/.*"
            permissions:
              - "Job/Build"
              - "Job/Cancel"
              - "Job/Read"
            assignments:
              - "jenkins-team-frontend"
```

### Folder-Level Permissions via Groovy Seed

```groovy
// seed-job: assegna permessi a livello di folder programmaticamente
import com.cloudbees.hudson.plugins.folder.Folder
import com.michelin.cio.hudson.plugins.rolestrategy.RoleBasedAuthorizationStrategy

def folderPermissions = [
    'backend':  [developers: ['Job/Build', 'Job/Read'], leads: ['Job/Configure', 'Job/Build', 'Job/Read']],
    'frontend': [developers: ['Job/Build', 'Job/Read'], leads: ['Job/Configure', 'Job/Build', 'Job/Read']],
    'platform': [developers: ['Job/Read'],              admins:  ['Overall/Administer']],
]

folderPermissions.each { folderName, roles ->
    def folder = Jenkins.instance.getItem(folderName)
    if (!folder) {
        echo "Folder ${folderName} non trovata, skip"
        return
    }

    // Abilita sicurezza a livello folder (override globale)
    def auth = new com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty()
    roles.each { role, perms ->
        perms.each { perm ->
            auth.add(
                hudson.security.Permission.fromId(perm),
                "jenkins-${folderName}-${role}"   // gruppo LDAP
            )
        }
    }
    folder.addProperty(auth)
    folder.save()
}
```

## Gestione Credenziali

### Credentials API — Binding Types

```groovy
// Esempi completi di withCredentials binding
pipeline {
    agent { label 'standard' }

    stages {
        stage('Credential Usage Examples') {
            steps {
                // Username + Password (es. registry Docker, Nexus)
                withCredentials([usernamePassword(
                    credentialsId: 'nexus-credentials',
                    usernameVariable: 'NEXUS_USER',
                    passwordVariable: 'NEXUS_PASS'
                )]) {
                    sh 'mvn deploy -Dsettings.security.password=$NEXUS_PASS'
                    // Jenkins maschera automaticamente NEXUS_PASS nei log
                }

                // Secret text (token API, chiavi)
                withCredentials([string(
                    credentialsId: 'sonar-token',
                    variable: 'SONAR_TOKEN'
                )]) {
                    sh 'sonar-scanner -Dsonar.token=$SONAR_TOKEN'
                }

                // File segreto (kubeconfig, certificati)
                withCredentials([file(
                    credentialsId: 'prod-kubeconfig',
                    variable: 'KUBECONFIG_FILE'
                )]) {
                    sh 'kubectl --kubeconfig=$KUBECONFIG_FILE get pods -n production'
                }

                // SSH private key
                withCredentials([sshUserPrivateKey(
                    credentialsId: 'deploy-ssh-key',
                    keyFileVariable: 'SSH_KEY',
                    passphraseVariable: 'SSH_PASSPHRASE',
                    usernameVariable: 'SSH_USER'
                )]) {
                    sh '''
                        chmod 600 $SSH_KEY
                        ssh -i $SSH_KEY -o StrictHostKeyChecking=no \
                            $SSH_USER@deploy.corp.example.com "systemctl restart myapp"
                    '''
                }

                // Certificate (P12 per firma)
                withCredentials([certificate(
                    credentialsId: 'code-signing-cert',
                    keystoreVariable: 'KEYSTORE',
                    passwordVariable: 'KEYSTORE_PASS',
                    aliasVariable: 'CERT_ALIAS'
                )]) {
                    sh 'jarsigner -keystore $KEYSTORE -storepass $KEYSTORE_PASS myapp.jar $CERT_ALIAS'
                }

                // Multi-binding in un solo blocco (scope minimo)
                withCredentials([
                    usernamePassword(credentialsId: 'aws-iam', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY'),
                    string(credentialsId: 'aws-region', variable: 'AWS_DEFAULT_REGION')
                ]) {
                    sh 'aws sts get-caller-identity'
                }
            }
        }
    }
}
```

### Kubernetes Secrets come Jenkins Credentials

```yaml
# External Secrets Operator: sincronizza segreti da Vault/AWS SM a K8s,
# poi Jenkins li legge come credenziali
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: jenkins-credentials-sync
  namespace: jenkins
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: jenkins-credentials-k8s
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        # Formato atteso dal Kubernetes Credentials plugin
        nexus-username: "{{ .nexus_user }}"
        nexus-password: "{{ .nexus_pass }}"
        sonar-token: "{{ .sonar_token }}"
        registry-username: "{{ .registry_user }}"
        registry-password: "{{ .registry_pass }}"
  data:
    - secretKey: nexus_user
      remoteRef: { key: "secret/jenkins/nexus", property: "username" }
    - secretKey: nexus_pass
      remoteRef: { key: "secret/jenkins/nexus", property: "password" }
    - secretKey: sonar_token
      remoteRef: { key: "secret/jenkins/sonar", property: "token" }
```

```yaml
# jenkins-casc.yaml — legge le credenziali dallo secret K8s
credentials:
  system:
    domainCredentials:
      - credentials:
          - usernamePassword:
              scope: GLOBAL
              id: "nexus-credentials"
              username: "${kubernetes:jenkins-credentials-k8s/nexus-username}"
              password: "${kubernetes:jenkins-credentials-k8s/nexus-password}"
              description: "Nexus Repository (sync da Vault via ESO)"

          - string:
              scope: GLOBAL
              id: "sonar-token"
              secret: "${kubernetes:jenkins-credentials-k8s/sonar-token}"
              description: "SonarQube Token (sync da Vault via ESO)"
```

### HashiCorp Vault Integration

```groovy
// Approccio 1: Vault Plugin (declarativo)
pipeline {
    agent { label 'standard' }
    environment {
        VAULT_ADDR = 'https://vault.corp.example.com'
    }
    stages {
        stage('Deploy') {
            steps {
                withVault(
                    configuration: [
                        vaultUrl: "${VAULT_ADDR}",
                        authTokenCredentialId: 'vault-token',
                        engineVersion: 2
                    ],
                    vaultSecrets: [
                        [
                            path: 'secret/data/prod/db',
                            secretValues: [
                                [vaultKey: 'username', envVar: 'DB_USER'],
                                [vaultKey: 'password', envVar: 'DB_PASS']
                            ]
                        ],
                        [
                            path: 'secret/data/prod/api',
                            secretValues: [
                                [vaultKey: 'token', envVar: 'API_TOKEN']
                            ]
                        ]
                    ]
                ) {
                    sh 'deploy.sh --db-user=$DB_USER --db-pass=$DB_PASS'
                }
            }
        }
    }
}
```

```groovy
// Approccio 2: Vault CLI direttamente (più controllo)
// vars/vaultRead.groovy
def call(String path, String field) {
    withCredentials([string(credentialsId: 'vault-role-id', variable: 'VAULT_ROLE_ID'),
                     string(credentialsId: 'vault-secret-id', variable: 'VAULT_SECRET_ID')]) {
        def token = sh(
            script: """
                vault write -field=token auth/approle/login \
                    role_id=\$VAULT_ROLE_ID \
                    secret_id=\$VAULT_SECRET_ID
            """,
            returnStdout: true
        ).trim()

        return sh(
            script: "VAULT_TOKEN=${token} vault kv get -field=${field} ${path}",
            returnStdout: true
        ).trim()
    }
}
```

## Script Security — Sandbox e Approvazione

Jenkins usa due livelli per controllare il codice Groovy in pipeline:

### Come Funziona il Sandbox

```
Pipeline Groovy code
        │
        ▼
┌───────────────────────────────────────────┐
│          Script Security Plugin            │
│                                           │
│  ┌─────────────────────────────────────┐  │
│  │  Sandbox Mode (DEFAULT)             │  │
│  │  - Whitelist di metodi/classi OK   │  │
│  │  - Accesso bloccato per default    │  │
│  │  - Non richiede approvazione admin │  │
│  └─────────────────────────────────────┘  │
│                                           │
│  ┌─────────────────────────────────────┐  │
│  │  Script Approval (fuori sandbox)    │  │
│  │  - Codice non in whitelist         │  │
│  │  - Richiede approvazione manuale   │  │
│  │  - Solo amministratori approvano   │  │
│  └─────────────────────────────────────┘  │
└───────────────────────────────────────────┘
```

### Pattern Sicuri per Script Security

```groovy
// ❌ SBAGLIATO: accede a classi non in sandbox, richiede approvazione
def files = new File('/var/jenkins_home/workspace').listFiles()

// ✅ CORRETTO: usa le API Pipeline approvate
def files = findFiles(glob: '**/*.xml')

// ❌ SBAGLIATO: HTTP direttamente, non approvato nel sandbox
def response = new URL('https://api.example.com').text

// ✅ CORRETTO: usa httpRequest plugin (approvato)
def response = httpRequest url: 'https://api.example.com', authentication: 'api-creds'

// ❌ SBAGLIATO: System.getenv (potrebbe esporre segreti)
def secret = System.getenv('MY_SECRET')

// ✅ CORRETTO: withCredentials con scope minimo
withCredentials([string(credentialsId: 'my-secret', variable: 'MY_SECRET')]) {
    sh 'use-secret.sh $MY_SECRET'  // mascherato nei log
}

// Per logica complessa che richiede Groovy avanzato → classe in src/
// src/com/example/Utils.groovy — FUORI dal sandbox ma APPROVATO come shared library
package com.example

class Utils implements Serializable {
    static String processComplexData(List<Map> data) {
        // Qui si può usare Groovy completo perché la libreria è approvata in blocco
        return data.findAll { it.status == 'active' }
                   .collect { it.name }
                   .join(', ')
    }
}
```

### Gestione Approvazioni Script

```groovy
// Script per gestire le approvazioni in blocco (eseguire in Script Console)
import org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval

def sa = ScriptApproval.get()

// Lista signature pending
sa.pendingSignatures.each { sig ->
    println "PENDING: ${sig.signature}"
}

// Approva tutte le signature pending (ATTENZIONE: verificare prima cosa si approva)
def approved = []
sa.pendingSignatures.each { sig ->
    // Filtra: approva solo signature della shared library aziendale
    if (sig.signature.contains('com.example.') || sig.signature.contains('jenkins.')) {
        sa.approveSignature(sig.signature)
        approved << sig.signature
    }
}
println "Approvati ${approved.size()} signature"
sa.save()
```

```yaml
# jenkins-casc.yaml — pre-approvazione signature note (riduce intervento manuale)
security:
  scriptApproval:
    approvedSignatures:
      # Classi base Groovy sicure
      - "method groovy.json.JsonSlurperClassic parseText java.lang.String"
      - "method groovy.json.JsonOutput toJson java.lang.Object"
      - "staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods collect java.util.Collection groovy.lang.Closure"
      - "staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods findAll java.util.Collection groovy.lang.Closure"
      # Jenkins API
      - "method hudson.model.ItemGroup getItem java.lang.String"
      - "method jenkins.model.Jenkins getInstance"
      # Groovy utility
      - "staticMethod java.util.Collections unmodifiableList java.util.List"
      - "new java.util.LinkedHashMap"
```

## Audit Trail e Compliance

### Audit Trail Plugin

```yaml
# jenkins-casc.yaml
unclassified:
  auditTrailPlugin:
    # Log su file rotante
    loggers:
      - logFileAuditLogger:
          log: "/var/log/jenkins/audit.log"
          limit: 50         # MB per file
          count: 10         # file da mantenere
          output: "JSON"    # JSON per parsing facile con ELK/Splunk
    # Include TUTTE le azioni (default include solo build)
    pattern: ".*"           # regex su URL — .* = tutto
```

Esempio record di audit in JSON:

```json
{
  "timestamp": "2026-02-27T14:32:10.123Z",
  "who": "john.doe@corp.example.com",
  "what": "POST /job/backend/auth-service/build",
  "remoteAddr": "10.0.1.50",
  "userAgent": "Mozilla/5.0...",
  "result": "302 Found"
}
```

### Job Config History Plugin

```yaml
# jenkins-casc.yaml — traccia ogni modifica alla configurazione dei job
unclassified:
  jobConfigHistory:
    maxHistoryEntries: 50       # storico modifiche per job
    saveSystemConfiguration: true
    saveItemConfiguration: true
    excludedClasses:             # esclude elementi rumorosi
      - "hudson.model.RunMap"
    showChangeReasonCommentWindow: true  # richiede commento al cambio config
```

### SIEM Integration — Forwarding a Splunk/ELK

```yaml
# Pipeline che invia eventi di audit a Splunk HEC
// vars/auditEvent.groovy
def call(Map config) {
    def event = [
        time:       System.currentTimeMillis() / 1000,
        host:       env.JENKINS_URL?.replaceAll('https?://', '').replaceAll('/', ''),
        source:     'jenkins:pipeline',
        sourcetype: 'jenkins:audit',
        index:      'devops',
        event: [
            job:        env.JOB_NAME,
            build:      env.BUILD_NUMBER,
            branch:     env.GIT_BRANCH,
            user:       env.BUILD_USER_ID ?: 'automation',
            action:     config.action,
            result:     config.result ?: 'in-progress',
            duration:   config.duration,
            env:        config.env,
            version:    config.version,
            change_id:  env.CHANGE_ID,
            timestamp:  new Date().format("yyyy-MM-dd'T'HH:mm:ss'Z'", TimeZone.getTimeZone('UTC'))
        ]
    ]

    withCredentials([string(credentialsId: 'splunk-hec-token', variable: 'SPLUNK_TOKEN')]) {
        def payload = groovy.json.JsonOutput.toJson(event)
        sh """
            curl -k -s --retry 3 \
                -H "Authorization: Splunk \$SPLUNK_TOKEN" \
                -H "Content-Type: application/json" \
                --data '${payload}' \
                https://splunk-hec.corp.example.com:8088/services/collector
        """
    }
}
```

## Hardening del Controller

### Configurazione di Sicurezza Base

```yaml
# jenkins-casc.yaml — hardening completo
jenkins:
  # Disabilita esecuzioni sul controller
  numExecutors: 0

  # CSRF Protection (Cross-Site Request Forgery)
  crumbIssuer:
    standard:
      excludeClientIPFromCrumb: false  # false = include IP nel crumb

  # Disabilita CLI via remoting (usa REST API)
  remotingSecurity:
    enabled: true

  # Security Headers
  globalNodeProperties:
    - envVars:
        env:
          - key: "JENKINS_OPTS"
            value: "--httpPort=-1 --httpsPort=8443"  # solo HTTPS

security:
  # Globale: disabilita accesso anonimo
  globalJobDslSecurityConfiguration:
    useScriptSecurity: true   # forza sandbox su Job DSL

  # Disable old remoting protocol
  queueItemAuthenticator:
    authenticators:
      - global:
          strategy: "triggeringUsersAuthorizationStrategy"  # build con perms dell'utente che triggera

unclassified:
  # HTTPS/TLS — configurare nel processo di avvio Jenkins, non in CasC
  # Aggiungere al Deployment K8s:
  # args: ["--httpsPort=8443", "--httpsCertificate=/certs/tls.crt", "--httpsPrivateKey=/certs/tls.key"]

  # Content Security Policy — riduce XSS surface
  globalDefaultFlowDurabilityLevel:
    durabilityHint: "PERFORMANCE_OPTIMIZED"  # per durability in K8s

  # Nasconde la versione Jenkins dagli header HTTP
  systemMessage: "Jenkins CI/CD Platform — Uso autorizzato"
```

### TLS e Ingress Kubernetes

```yaml
# K8s: configurazione TLS con cert-manager
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: jenkins-ingress
  namespace: jenkins
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    # Security headers
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "X-Frame-Options: SAMEORIGIN";
      more_set_headers "X-Content-Type-Options: nosniff";
      more_set_headers "X-XSS-Protection: 1; mode=block";
      more_set_headers "Referrer-Policy: strict-origin-when-cross-origin";
      more_set_headers "Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';";
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - jenkins.corp.example.com
      secretName: jenkins-tls
  rules:
    - host: jenkins.corp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: jenkins
                port:
                  number: 8080
```

### Network Policy — Isolamento Controller

```yaml
# Blocca tutto il traffico in ingress tranne quello necessario
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: jenkins-controller-netpol
  namespace: jenkins
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: jenkins
      app.kubernetes.io/component: jenkins-controller
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # HTTPS dal cluster Ingress
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
    # Agent JNLP/WebSocket
    - from:
        - namespaceSelector:
            matchLabels:
              jenkins-agent: "true"
      ports:
        - protocol: TCP
          port: 50000   # JNLP
        - protocol: TCP
          port: 8080    # WebSocket
  egress:
    # LDAP/AD
    - to: []
      ports:
        - protocol: TCP
          port: 636   # LDAPS
    # GitHub
    - to: []
      ports:
        - protocol: TCP
          port: 443
    # Kubernetes API (per creare agent pod)
    - to:
        - ipBlock:
            cidr: 10.0.0.1/32  # IP API server
      ports:
        - protocol: TCP
          port: 6443
```

## Compliance — Pipeline Security Controls

### SAST/DAST Integration come Quality Gate

```groovy
// vars/securityGate.groovy — blocca pipeline se fail security scan
def call(Map config = [:]) {
    def severity    = config.severity ?: 'HIGH'
    def fail        = config.failOnFinding ?: true

    parallel(
        'SAST — Semgrep': {
            sh """
                semgrep scan \
                    --config=p/jenkins \
                    --config=p/owasp-top-ten \
                    --sarif \
                    --output=semgrep-results.sarif \
                    .
            """
            // Pubblica risultati in GitHub PR / SonarQube
            recordIssues(
                tools: [sarif(pattern: 'semgrep-results.sarif', id: 'semgrep', name: 'Semgrep SAST')]
            )
        },
        'Dependency Check — OWASP': {
            sh """
                dependency-check \
                    --scan . \
                    --format JSON \
                    --format HTML \
                    --out dependency-check-report \
                    --failOnCVSS 7 \
                    --nvdApiKey \$NVD_API_KEY
            """
            dependencyCheckPublisher pattern: 'dependency-check-report/dependency-check-report.xml'
        },
        'Container Scan — Trivy': {
            sh """
                trivy image \
                    --exit-code ${fail ? 1 : 0} \
                    --severity ${severity},CRITICAL \
                    --format sarif \
                    --output trivy-results.sarif \
                    ${env.IMAGE_NAME}:${env.VERSION}
            """
        }
    )
}
```

### SBOM Generation e Supply Chain

```groovy
// vars/generateSBOM.groovy
def call(Map config) {
    def image   = config.image
    def version = config.version
    def format  = config.format ?: 'spdx-json'  // spdx-json, cyclonedx-json

    // Genera SBOM dall'immagine container
    sh """
        syft ${image}:${version} \
            -o ${format}=sbom.json \
            -o table
    """

    // Attesta l'SBOM con Cosign
    withCredentials([string(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY')]) {
        sh """
            echo "\$COSIGN_KEY" > /tmp/cosign.key
            cosign attest \
                --key /tmp/cosign.key \
                --type spdxjson \
                --predicate sbom.json \
                ${image}:${version}
            rm /tmp/cosign.key
        """
    }

    // Upload SBOM a Dependency Track
    withCredentials([string(credentialsId: 'deptrack-api-key', variable: 'DT_KEY')]) {
        sh """
            curl -s -X POST \
                -H "X-API-Key: \$DT_KEY" \
                -H "Content-Type: multipart/form-data" \
                -F "project=${config.projectName}" \
                -F "version=${version}" \
                -F "bom=@sbom.json" \
                https://deptrack.corp.example.com/api/v1/bom
        """
    }

    archiveArtifacts artifacts: 'sbom.json', fingerprint: true
}
```

### Policy as Code — OPA per Pipeline

```groovy
// vars/opaCheck.groovy — verifica policy OPA prima di operazioni critiche
def call(Map config) {
    def policy  = config.policy   ?: 'deploy'
    def input   = config.input    ?: [:]
    def opaUrl  = config.opaUrl   ?: 'http://opa.policy-system.svc.cluster.local:8181'

    def inputJson = groovy.json.JsonOutput.toJson([
        input: input + [
            build_user:    env.BUILD_USER_ID,
            branch:        env.GIT_BRANCH,
            job:           env.JOB_NAME,
            timestamp:     new Date().format("yyyy-MM-dd'T'HH:mm:ss'Z'", TimeZone.getTimeZone('UTC'))
        ]
    ])

    def result = sh(
        script: """
            echo '${inputJson}' | curl -s -X POST \
                -H "Content-Type: application/json" \
                --data @- \
                ${opaUrl}/v1/data/${policy}/allow
        """,
        returnStdout: true
    ).trim()

    def parsed = readJSON text: result
    if (!parsed.result) {
        def violations = parsed.explanation ?: 'Violazione policy senza dettagli'
        error "OPA Policy ${policy}: DENIED — ${violations}"
    }
    echo "OPA Policy ${policy}: ALLOWED ✅"
}
```

```rego
# policy/deploy.rego — OPA policy per deploy
package deploy

import future.keywords.in

default allow = false

# Permetti deploy se tutte le condizioni sono soddisfatte
allow {
    valid_branch
    not production_during_freeze
    authorized_user
}

# Solo da branch approvati
valid_branch {
    input.branch in ["main", "release/current"]
}

# No deploy in production durante freeze (venerdì 17-24, weekend)
production_during_freeze {
    input.job contains "production"
    time.weekday(time.now_ns()) in [5, 6, 0]  # ven, sab, dom
}

production_during_freeze {
    input.job contains "production"
    hour := time.clock(time.now_ns())[0]
    hour >= 17
    time.weekday(time.now_ns()) == 4  # giovedì sera = freeze anticipato
}

# Solo utenti nel gruppo release-managers per production
authorized_user {
    not input.job contains "production"  # ambienti non-prod: tutti OK
}

authorized_user {
    input.job contains "production"
    input.build_user in data.release_managers  # caricato da file JSON esterno
}
```

## Tabella Rischi e Controlli

| Rischio | Impatto | Controllo Jenkins | Frequenza review |
|---------|---------|-------------------|-----------------|
| Credenziali in chiaro nel Jenkinsfile | Critico | Script Security sandbox + `withCredentials` | Ad ogni code review |
| Accesso non autorizzato al controller | Alto | RBAC Role Strategy + SSO/MFA | Trimestrale |
| Codice Groovy malevolo in pipeline | Alto | Script Security sandbox + approvazioni | Continua (automatica) |
| Secret leakage nei log | Alto | Masking automatico + log access control | Mensile |
| Supply chain attack su shared library | Alto | Library versioning pinned + firma commit | Ad ogni update libreria |
| Accesso ad agent senza isolamento | Medio | Namespace K8s isolati + NetworkPolicy | Trimestrale |
| Build history con dati sensibili | Medio | Build discarder policy + log encryption | Mensile |
| Script approval accumulati non verificati | Medio | Review periodica signature approvate | Mensile |

## Troubleshooting

### Scenario 1 — "Access Denied" su job con ruolo apparentemente corretto

**Sintomo:** Un utente con il ruolo assegnato correttamente riceve `AccessDeniedException` o "403 Forbidden" quando tenta di accedere o eseguire un job.

**Causa:** Il folder contiene un'override di autorizzazione locale (Block Inheritance) che sovrascrive i ruoli globali del Role Strategy Plugin.

**Soluzione:** Verificare le properties del folder e rimuovere o correggere l'override locale:

```bash
# Via Jenkins Script Console (Manage Jenkins → Script Console)
Jenkins.instance.getAllItems(com.cloudbees.hudson.plugins.folder.Folder).each { folder ->
  def prop = folder.getProperties().find { it instanceof com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty }
  if (prop) println "Folder: ${folder.fullName} — override presente: ${prop.class.simpleName}"
}
```

```groovy
// Oppure verificare via REST API
// GET /job/<folder>/config.xml  → cercare <properties> con AuthorizationMatrix
```

### Scenario 2 — Credenziali non trovate da shared library step

**Sintomo:** `withCredentials([usernamePassword(credentialsId: 'my-creds', ...)])` fallisce con `CredentialsUnavailableException` o le variabili risultano vuote.

**Causa:** Le credenziali sono cercate nel contesto del controller (non dell'agent) e l'ID specificato non esiste nello scope accessibile al job, oppure il job non ha il permesso implicito `Credentials/Use`.

**Soluzione:** Verificare l'esistenza e lo scope delle credenziali:

```bash
# Script Console — lista credenziali accessibili da un folder specifico
def store = Jenkins.instance.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0]
store.getCredentials(com.cloudbees.plugins.credentials.domains.Domain.global()).each {
  println "ID: ${it.id} — Type: ${it.class.simpleName}"
}
```

```bash
# Verifica via CLI Jenkins
java -jar jenkins-cli.jar -s https://jenkins.corp.example.com/ \
  -auth admin:${API_TOKEN} \
  list-credentials-as-xml "folder/subfolder"
```

### Scenario 3 — SAML redirect loop dopo login

**Sintomo:** Dopo il reindirizzamento al provider SAML (Okta/Azure AD), Jenkins rispedisce l'utente all'IdP in loop infinito, mai completando il login.

**Causa:** Il `Service Provider Entity ID` configurato nel provider non corrisponde esattamente all'URL base Jenkins, oppure il load balancer non gestisce le sessioni in modo sticky (le richieste SAML richiedono che assertion e callback arrivino allo stesso nodo).

**Soluzione:**

```bash
# Verificare il metadata SP generato da Jenkins
curl -s https://jenkins.corp.example.com/securityRealm/metadata | \
  grep -o 'entityID="[^"]*"'

# Il valore deve corrispondere ESATTAMENTE a quello configurato in Okta/AzureAD
# Verificare anche i cookie di sessione
curl -I https://jenkins.corp.example.com/ | grep -i set-cookie
```

```yaml
# Nginx — configurazione sticky session per Jenkins HA
upstream jenkins_cluster {
  ip_hash;  # sticky per IP — alternativa: cookie_hash
  server jenkins-node1:8080;
  server jenkins-node2:8080;
}
```

### Scenario 4 — Script approval svuotato dopo restart o re-deploy

**Sintomo:** Pipeline precedentemente funzionanti falliscono con `org.jenkinsci.plugins.scriptsecurity.sandbox.RejectedAccessException` dopo un restart del controller o un re-deploy del pod.

**Causa:** Il file `scriptApproval.xml` non è incluso nel backup o nel PVC Kubernetes, quindi le approvazioni accumulate vengono perse.

**Soluzione:** Includere `scriptApproval.xml` nel backup e/o pre-popolare via JCasC:

```yaml
# jenkins-casc.yaml — pre-approvazione signature note
security:
  scriptApproval:
    approvedSignatures:
      - "method groovy.lang.GroovyObject getProperty java.lang.String"
      - "staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods collect java.util.Collection groovy.lang.Closure"
      - "method java.util.Map entrySet"
```

```bash
# Backup manuale di scriptApproval.xml
kubectl cp jenkins-0:/var/jenkins_home/scriptApproval.xml ./backup/scriptApproval.xml
# Restore
kubectl cp ./backup/scriptApproval.xml jenkins-0:/var/jenkins_home/scriptApproval.xml
kubectl exec jenkins-0 -- /bin/bash -c "chown jenkins:jenkins /var/jenkins_home/scriptApproval.xml"
```

### Scenario 5 — Audit log incompleto o assente

**Sintomo:** Il log di audit non registra alcune azioni (es. esecuzioni di pipeline via API, modifiche via script Groovy), rendendo impossibile tracciare chi ha eseguito cosa.

**Causa:** Il plugin Audit Trail logga solo le richieste HTTP in ingresso. Le azioni interne avviate da Groovy (es. `Jenkins.instance.*`) o da trigger interni non passano per il layer HTTP.

**Soluzione:** Integrare il logging a livello di pipeline e abilitare il log verboso del plugin:

```groovy
// In pipeline — logging esplicito delle azioni critiche
pipeline {
  stages {
    stage('Deploy') {
      steps {
        script {
          def user = currentBuild.getBuildCauses('hudson.model.Cause$UserIdCause')?.userId ?: 'timer/api'
          echo "AUDIT: deploy eseguito da ${user} — build #${env.BUILD_NUMBER} — ${new Date()}"
        }
        // ... passi di deploy
      }
    }
  }
}
```

```bash
# Verifica configurazione Audit Trail plugin
# Manage Jenkins → Configure System → Audit Trail
# Assicurarsi che "Log Location" punti a un path persistente
# e che "Log File Size" sia adeguato (default 100MB)

# Lettura diretta del log audit
tail -f /var/jenkins_home/logs/audit.log | grep -E "(POST|DELETE|PUT)"
```

## Riferimenti

- [Jenkins Security — Documentazione Ufficiale](https://www.jenkins.io/doc/book/security/)
- [Role Strategy Plugin](https://plugins.jenkins.io/role-strategy/)
- [Script Security Plugin](https://plugins.jenkins.io/script-security/)
- [Credentials Plugin](https://plugins.jenkins.io/credentials/)
- [Vault Plugin](https://plugins.jenkins.io/hashicorp-vault-plugin/)
- [Audit Trail Plugin](https://plugins.jenkins.io/audit-trail/)
- [OWASP Top 10 CI/CD Security Risks](https://owasp.org/www-project-top-10-ci-cd-security-risks/)
- [SLSA Framework](https://slsa.dev/)
