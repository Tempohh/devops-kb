---
title: "Jenkins Security & Governance"
slug: security-governance
category: ci-cd
tags: [jenkins, security, rbac, credentials, sso, ldap, saml, audit, script-security, compliance]
search_keywords: [jenkins security, jenkins rbac, role strategy plugin, matrix authorization, jenkins credentials api, script approval, script sandbox, jenkins sso, jenkins ldap, jenkins saml, jenkins audit trail, jenkins hardening, jenkins tls, CasC security, pipeline security, withCredentials, kubernetes secrets jenkins, jenkins compliance]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/agent-infrastructure, ci-cd/jenkins/enterprise-patterns, ci-cd/jenkins/shared-libraries, security/secret-management, security/autenticazione]
official_docs: https://www.jenkins.io/doc/book/security/
status: needs-review
difficulty: expert
last_updated: 2026-10-03
last_verified: 2026-10-03
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
          groupSearchFilter: "(member={0})"      # {0} = DN dell'utente; per AD annidato: (member:1.2.840.113556.1.4.1941:={0})
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
      binding: "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      # <!-- REVIEW: verificare nomi esatti delle chiavi keystore/firma (keyStoreAuthConfiguration / advancedConfiguration) nella versione corrente del saml plugin: la forma piatta keyStorePath/signRequests precedente non è confermata -->
```

Il metadata del Service Provider (SP) è esposto da Jenkins su `https://<jenkins>/securityRealm/metadata`: è l'URL da dare all'IdP, non una chiave CasC. Mantenere l'`Entity ID` dell'SP identico su Jenkins e IdP (vedi Troubleshooting, scenario 3). Con `JENKINS_URL` errata gli assertion vengono rifiutati.

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
        # Non concedere Overall/Read ad anonymous salvo esposizione pubblica voluta
        # Developer: build e lettura log
        - "GROUP:Job/Build:jenkins-developers"
        - "GROUP:Job/Cancel:jenkins-developers"
        - "GROUP:Job/Read:jenkins-developers"
        - "GROUP:Run/Update:jenkins-developers"
        # QA: solo lettura e trigger
        - "GROUP:Job/Build:jenkins-qa"
        - "GROUP:Job/Read:jenkins-qa"
```

!!! note "Sintassi permessi"
    Il formato stringa `GROUP:<permesso>:<nome>` è quello storico del Matrix Authorization plugin; le versioni recenti (3.x) preferiscono la forma strutturata `entries: - group: {name: ..., permissions: [...]}`. Entrambe sono accettate: verificare quale genera la tua versione con *Configuration as Code → Export*.

### Role Strategy (autorizzazione granulare per folder/job)

```yaml
jenkins:
  authorizationStrategy:
    roleStrategy:
      roles:
        # Ruoli globali
        global:
          - name: "admin"
            description: "Amministratori Jenkins"
            permissions:
              - "Overall/Administer"
            entries:
              - group: "jenkins-admins"   # gruppo LDAP/IdP

          - name: "viewer"
            description: "Read-only per tutti"
            permissions:
              - "Overall/Read"
              - "Job/Read"
            entries:
              - group: "authenticated"

        # Ruoli per item/folder: regex sul full name del job
        items:
          - name: "team-backend-developer"
            description: "Developer del team backend"
            patterns: ["backend/.*"]   # match folder backend e tutto sotto
            permissions:
              - "Job/Build"
              - "Job/Cancel"
              - "Job/Read"
              - "Job/Workspace"
              - "Run/Update"
            entries:
              - group: "jenkins-team-backend"

          - name: "team-backend-release"
            description: "Release manager backend"
            patterns: ["backend/.*"]
            permissions:
              - "Job/Build"
              - "Job/Configure"    # può modificare la pipeline: concederlo con parsimonia
              - "Job/Read"
              - "Run/Replay"       # Replay esegue Groovy modificato: equivale a Configure
            entries:
              - group: "jenkins-release-managers"

          - name: "team-frontend-developer"
            patterns: ["frontend/.*"]
            permissions:
              - "Job/Build"
              - "Job/Cancel"
              - "Job/Read"
            entries:
              - group: "jenkins-team-frontend"
```

!!! tip "Perché ruoli per pattern"
    Il Role Strategy valuta le regex sul *full name* dell'item (`backend/auth-service`): un team ottiene permessi su un intero sotto-albero senza una matrix per ogni job. I permessi sono **cumulativi** tra ruoli globali e di item, quindi un ruolo globale troppo largo (es. `Job/Configure`) vanifica quelli per folder. Un ruolo `viewer` globale deve restare minimo.

### Folder-Level Permissions via Groovy Seed

Alternativa quando i team sono creati dinamicamente: una matrix per folder (Folders plugin). Va eseguita come script con identità amministrativa (Script Console o job trusted), non in una pipeline sandboxed.

```groovy
import com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty
import hudson.model.Item
import hudson.security.Permission

// Permission.fromId vuole l'ID di classe ("hudson.model.Item.Build"), non "Job/Build"
def devPerms  = [Item.READ, Item.BUILD]
def leadPerms = [Item.READ, Item.BUILD, Item.CONFIGURE]

['backend', 'frontend'].each { folderName ->
    def folder = Jenkins.instance.getItem(folderName)
    if (!folder) {
        println "Folder ${folderName} non trovata, skip"
        return
    }

    def auth = new AuthorizationMatrixProperty()
    devPerms.each  { Permission p -> auth.add(p, "jenkins-${folderName}-developers") }  // gruppo LDAP
    leadPerms.each { Permission p -> auth.add(p, "jenkins-${folderName}-leads") }

    // rimuove una matrix preesistente per rendere lo script idempotente
    folder.properties.findAll { it instanceof AuthorizationMatrixProperty }
                     .each { folder.removeProperty(it) }
    folder.addProperty(auth)
    folder.save()
}
```

!!! note "Nota"
    `AuthorizationMatrixProperty.add(Permission, String)` è deprecato nelle versioni recenti del Matrix Authorization plugin a favore di `add(Permission, PermissionEntry)`. <!-- REVIEW: verificare firma corrente di AuthorizationMatrixProperty.add -->

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
                        ssh -i $SSH_KEY -o UserKnownHostsFile=/etc/ssh/jenkins_known_hosts \
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
# External Secrets Operator: sincronizza segreti da Vault/AWS SM a K8s;
# il Secret viene montato nel pod Jenkins e letto da JCasC come file
apiVersion: external-secrets.io/v1
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
        # chiavi = nomi dei file che compaiono in /run/secrets/additional
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
# jenkins-casc.yaml — il Secret K8s è montato in /run/secrets/additional
# (helm chart: controller.additionalExistingSecrets / JCasC secretsFilesDirectory);
# JCasC risolve ${nome-file} leggendo il contenuto del file
credentials:
  system:
    domainCredentials:
      - credentials:
          - usernamePassword:
              scope: GLOBAL
              id: "nexus-credentials"
              username: "${nexus-username}"
              password: "${nexus-password}"
              description: "Nexus Repository (sync da Vault via ESO)"

          - string:
              scope: GLOBAL
              id: "sonar-token"
              secret: "${sonar-token}"
              description: "SonarQube Token (sync da Vault via ESO)"
```

!!! note "Alternativa: Kubernetes Credentials Provider"
    Il plugin *Kubernetes Credentials Provider* espone direttamente i Secret K8s con label `jenkins.io/credentials-type` come credenziali Jenkins, senza passare da CasC. Il vantaggio è la rotazione senza riavvio; il costo è che i permessi sul Secret K8s diventano parte del modello di sicurezza Jenkins.

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

        // Il token passa come env var (single-quote = nessuna interpolazione Groovy):
        // interpolarlo in una stringa "..." lo esporrebbe nel log e nella process list
        withEnv(["VAULT_TOKEN=${token}", "VAULT_FIELD=${field}", "VAULT_PATH=${path}"]) {
            return sh(
                script: 'vault kv get -field="$VAULT_FIELD" "$VAULT_PATH"',
                returnStdout: true
            ).trim()
        }
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

!!! warning "Non approvare in blocco"
    Ogni signature approvata vale per **tutti** gli script non-sandbox e, per le signature non whitelisted, apre l'accesso a classi interne. Approvare `jenkins.model.Jenkins getInstance` o simili dà a chiunque possa modificare una pipeline l'accesso all'oggetto `Jenkins` (credenziali, configurazione): è una privilege escalation verso admin. Ogni signature va letta e giustificata; le signature "pericolose" sono evidenziate dalla UI di approvazione.

```groovy
// Audit delle approvazioni (eseguire in Script Console, sola lettura)
import org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval

def sa = ScriptApproval.get()

println "== PENDING =="
sa.pendingSignatures.each { println it.signature }

println "== GIA' APPROVATE =="
sa.approvedSignatures.sort().each { println it }

// Approvazione puntuale, dopo revisione manuale:
// sa.approveSignature('method java.util.Map entrySet')   // salva da sé
```

```yaml
# jenkins-casc.yaml — pre-approvazione di signature innocue (riduce intervento manuale)
security:
  scriptApproval:
    approvedSignatures:
      - "staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods collect java.util.Collection groovy.lang.Closure"
      - "staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods findAll java.util.Collection groovy.lang.Closure"
      - "staticMethod java.util.Collections unmodifiableList java.util.List"
      - "new java.util.LinkedHashMap"
```

Per il parsing JSON preferire gli step `readJSON`/`writeJSON` (Pipeline Utility Steps) a `JsonSlurper`, che richiede approvazioni.

## Audit Trail e Compliance

### Audit Trail Plugin

```yaml
# jenkins-casc.yaml
unclassified:
  auditTrailPlugin:
    loggers:
      - logFileAuditLogger:
          log: "/var/jenkins_home/logs/audit.log"   # su volume persistente
          limit: 50         # MB per file
          count: 10         # file ruotati da mantenere
    # Regex sugli URL loggati. Il default copre solo azioni mutanti (build, config, delete...).
    # ".*" logga ANCHE ogni GET/polling: volume enorme e rumore. Estendere solo se serve.
    pattern: ".*/(?:configSubmit|doDelete|postBuildResult|enable|disable|cancelQueue|stop|toggleLogKeep|doWipeOutWorkspace|createItem|createView|build|buildWithParameters|script|scriptText)/?.*"
    # <!-- REVIEW: verificare nomi chiave CasC (logFileAuditLogger/pattern) e disponibilità output JSON del plugin Audit Trail nella versione in uso -->
```

L'Audit Trail registra **richieste HTTP** (chi, cosa, da quale IP): è la fonte per rispondere a "chi ha lanciato/cancellato questo job". Il formato nativo è testo; per ELK/Splunk normalizzarlo in JSON con l'agente di log (Filebeat/Fluent Bit) oppure usare il logger `syslog`/`console` del plugin. Record illustrativo dopo normalizzazione:

```json
{
  "timestamp": "2026-02-27T14:32:10.123Z",
  "who": "john.doe@corp.example.com",
  "what": "POST /job/backend/auth-service/build",
  "remoteAddr": "10.0.1.50",
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
    showChangeReasonCommentWindow: true  # richiede commento al cambio config
    # <!-- REVIEW: verificare chiavi CasC (es. excludePattern) nella versione corrente -->
```

Complementa l'Audit Trail: questo risponde a "*cosa* è cambiato" (diff del `config.xml`), l'altro a "*chi* e *quando*". Con pipeline da SCM la storia vera sta in Git: Job Config History serve per job UI-defined e configurazione di sistema.

### SIEM Integration — Forwarding a Splunk/ELK

```groovy
// vars/auditEvent.groovy — invia eventi di pipeline a Splunk HEC
def call(Map config) {
    def event = [
        time:       (long) (System.currentTimeMillis() / 1000),
        host:       env.JENKINS_URL?.replaceAll('https?://', '')?.replaceAll('/', ''),
        source:     'jenkins:pipeline',
        sourcetype: 'jenkins:audit',
        index:      'devops',
        event: [
            job:        env.JOB_NAME,
            build:      env.BUILD_NUMBER,
            branch:     env.GIT_BRANCH,
            user:       env.BUILD_USER_ID ?: 'automation',  // richiede build-user-vars-plugin
            action:     config.action,
            result:     config.result ?: 'in-progress',
            env:        config.env,
            version:    config.version,
            change_id:  env.CHANGE_ID
        ]
    ]

    withCredentials([string(credentialsId: 'splunk-hec-token', variable: 'SPLUNK_TOKEN')]) {
        // httpRequest evita l'injection di shell dal payload e mantiene la verifica TLS
        httpRequest url: 'https://splunk-hec.corp.example.com:8088/services/collector',
                    httpMode: 'POST',
                    contentType: 'APPLICATION_JSON',
                    customHeaders: [[name: 'Authorization', value: "Splunk ${SPLUNK_TOKEN}", maskValue: true]],
                    requestBody: groovy.json.JsonOutput.toJson(event),
                    validResponseCodes: '200'
    }
}
```

## Hardening del Controller

### Configurazione di Sicurezza Base

```yaml
# jenkins-casc.yaml — hardening di base
jenkins:
  # Nessuna build sul controller: una build che gira lì legge JENKINS_HOME
  # (credentials.xml, master.key) e può impersonare Jenkins. Si builda solo su agent.
  numExecutors: 0

  # CSRF protection: ogni POST richiede un crumb legato alla sessione
  crumbIssuer:
    standard:
      excludeClientIPFromCrumb: false  # false = il crumb include l'IP del client

security:
  # Job DSL: forza sandbox sugli script dei seed job
  globalJobDslSecurityConfiguration:
    useScriptSecurity: true

  # Le build girano con i permessi dell'utente che le avvia, non di SYSTEM
  # (richiede il plugin Authorize Project)
  queueItemAuthenticator:
    authenticators:
      - global:
          strategy: "triggeringUsersAuthorizationStrategy"

unclassified:
  # Messaggio mostrato in home (banner di uso autorizzato)
  systemMessage: "Jenkins CI/CD Platform — Uso autorizzato"
```

!!! note "Cosa non serve più configurare"
    L'*Agent → Controller Access Control* (ex `remotingSecurity`) è sempre attivo dalle versioni recenti del core e non è disattivabile da UI: non esiste più un toggle da "abilitare". Anche la CSP (Content Security Policy) di Jenkins è impostata dal core; **non** sovrascriverla dall'Ingress, perché le regole `'unsafe-inline'` indeboliscono quella nativa.

Oltre alla configurazione, la parte più efficace dell'hardening è operativa: tenere core (LTS) e plugin aggiornati e seguire i **Jenkins Security Advisories** (pubblicati sul sito jenkins.io e via mailing list `jenkinsci-advisories`). La maggior parte delle compromissioni reali passa da CVE in plugin non aggiornati, non da misconfigurazioni di CasC. Rimuovere i plugin inutilizzati riduce la superficie d'attacco.

### TLS e Ingress Kubernetes

TLS termina sull'Ingress; tra Ingress e pod Jenkins il traffico resta HTTP 8080 dentro il cluster (protetto da NetworkPolicy). Terminare TLS direttamente su Jenkins (`--httpsPort`) serve solo senza reverse proxy.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: jenkins-ingress
  namespace: jenkins
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
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

!!! warning "ingress-nginx è in fine vita"
    Il progetto Ingress NGINX (kubernetes/ingress-nginx) è stato dismesso a marzo 2026: nessuna patch di sicurezza oltre quella data. Per nuovi deploy valutare Gateway API o un altro controller (es. Traefik, Envoy Gateway). Inoltre le `configuration-snippet` sono disabilitate di default nelle versioni recenti (`allow-snippet-annotations: false`) per motivi di sicurezza, quindi non contare su header custom via snippet. Jenkins imposta già da sé `X-Frame-Options` e `X-Content-Type-Options`; `X-XSS-Protection` è obsoleto e va omesso.

### Network Policy — Isolamento Controller

```yaml
# Default deny + solo i flussi necessari
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
    # HTTP dall'Ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
    # Agent: JNLP (50000) e WebSocket (8080)
    - from:
        - namespaceSelector:
            matchLabels:
              jenkins-agent: "true"
      ports:
        - protocol: TCP
          port: 50000
        - protocol: TCP
          port: 8080
  egress:
    # DNS: senza questa regola, con Egress in policyTypes, nessun nome si risolve
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    # LDAPS e HTTPS (GitHub, plugin update center): `to` omesso = qualunque destinazione
    # su quella porta. Restringere con ipBlock/FQDN policy (CNI che le supportano)
    - ports:
        - protocol: TCP
          port: 636
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
// vars/securityGate.groovy — blocca la pipeline se uno scan security fallisce
def call(Map config = [:]) {
    def severity = config.severity ?: 'HIGH'
    // attenzione: `config.failOnFinding ?: true` renderebbe impossibile passare false
    def fail     = config.containsKey('failOnFinding') ? config.failOnFinding : true

    parallel(
        'SAST — Semgrep': {
            sh """
                semgrep scan \
                    --config=p/owasp-top-ten \
                    --sarif \
                    --output=semgrep-results.sarif \
                    ${fail ? '--error' : ''} \
                    .
            """
            recordIssues(
                tools: [sarif(pattern: 'semgrep-results.sarif', id: 'semgrep', name: 'Semgrep SAST')]
            )
        },
        'Dependency Check — OWASP': {
            withCredentials([string(credentialsId: 'nvd-api-key', variable: 'NVD_API_KEY')]) {
                sh '''
                    dependency-check \
                        --scan . \
                        --format XML --format HTML \
                        --out dependency-check-report \
                        --failOnCVSS 7 \
                        --nvdApiKey "$NVD_API_KEY"
                '''
            }
            // il publisher legge l'XML: il formato XML va richiesto esplicitamente sopra
            dependencyCheckPublisher pattern: 'dependency-check-report/dependency-check-report.xml'
        },
        'Container Scan — Trivy': {
            sh """
                trivy image \
                    --exit-code ${fail ? 1 : 0} \
                    --severity ${severity == 'CRITICAL' ? 'CRITICAL' : severity + ',CRITICAL'} \
                    --format sarif \
                    --output trivy-results.sarif \
                    ${env.IMAGE_NAME}:${env.VERSION}
            """
        }
    )
}
```

Il gate è "shift-left" ma va applicato sul percorso che porta in produzione, non solo sulle PR: uno scan non bloccante produce solo rumore. Senza `--nvdApiKey` il download del database NVD è fortemente rate-limitato.

### SBOM Generation e Supply Chain

```groovy
// vars/generateSBOM.groovy
def call(Map config) {
    def image   = config.image
    def version = config.version
    def format  = config.format ?: 'spdx-json'  // spdx-json, cyclonedx-json

    // SBOM dall'immagine container
    sh "syft ${image}:${version} -o ${format}=sbom.json -o table"

    // Attestation firmata. La chiave è un credential di tipo *file*: Jenkins la scrive in un
    // temp dir dell'agent e la cancella a fine blocco (niente cat/rm manuali).
    withCredentials([file(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY'),
                     string(credentialsId: 'cosign-password', variable: 'COSIGN_PASSWORD')]) {
        sh """
            cosign attest --yes \
                --key \$COSIGN_KEY \
                --type spdxjson \
                --predicate sbom.json \
                ${image}:${version}
        """
    }

    // Upload a Dependency-Track (API v1: multipart con projectName/projectVersion)
    withCredentials([string(credentialsId: 'deptrack-api-key', variable: 'DT_KEY')]) {
        sh """
            curl -sf -X POST \
                -H "X-API-Key: \$DT_KEY" \
                -F "autoCreate=true" \
                -F "projectName=${config.projectName}" \
                -F "projectVersion=${version}" \
                -F "bom=@sbom.json" \
                https://deptrack.corp.example.com/api/v1/bom
        """
    }

    archiveArtifacts artifacts: 'sbom.json', fingerprint: true
}
```

!!! tip "Keyless"
    Con un OIDC token del CI, `cosign` può firmare in modalità *keyless* (Fulcio/Rekor): niente chiave privata da custodire in Jenkins. Su Jenkins richiede un provider OIDC (plugin) e un'identity policy lato verifica; la chiave statica resta la scelta più semplice in ambienti air-gapped.

### Policy as Code — OPA per Pipeline

```groovy
// vars/opaCheck.groovy — verifica policy OPA prima di operazioni critiche
def call(Map config) {
    def policy = config.policy ?: 'deploy'
    def opaUrl = config.opaUrl ?: 'http://opa.policy-system.svc.cluster.local:8181'

    def body = groovy.json.JsonOutput.toJson([
        input: (config.input ?: [:]) + [
            build_user: env.BUILD_USER_ID,
            branch:     env.GIT_BRANCH,
            job:        env.JOB_NAME
        ]
    ])

    def res = httpRequest url: "${opaUrl}/v1/data/${policy}/allow",
                          httpMode: 'POST',
                          contentType: 'APPLICATION_JSON',
                          requestBody: body,
                          validResponseCodes: '200'

    // OPA risponde {"result": true|false}; se la regola è indefinita risponde {} (= negato)
    def parsed = readJSON text: res.content
    if (parsed.result != true) {
        error "OPA Policy ${policy}: DENIED"
    }
    echo "OPA Policy ${policy}: ALLOWED"
}
```

```rego
# policy/deploy.rego — sintassi Rego v1 (default da OPA 1.0)
package deploy

import rego.v1

default allow := false

# Deploy permesso se tutte le condizioni sono soddisfatte
allow if {
    valid_branch
    not production_during_freeze
    authorized_user
}

valid_branch if input.branch in {"main", "release/current"}

is_production if contains(input.job, "production")

# Freeze produzione: da venerdì 17:00 a domenica (orario UTC).
# time.weekday restituisce il NOME del giorno ("Friday"), non un numero.
production_during_freeze if {
    is_production
    time.weekday(time.now_ns()) in {"Saturday", "Sunday"}
}

production_during_freeze if {
    is_production
    time.weekday(time.now_ns()) == "Friday"
    time.clock(time.now_ns())[0] >= 17
}

# Ambienti non-prod: tutti gli utenti
authorized_user if not is_production

# Production: solo release manager (data.release_managers caricato come bundle/data JSON)
authorized_user if {
    is_production
    input.build_user in data.release_managers
}
```

!!! note "OPA 1.0"
    Dal 2025 (OPA 1.0) la sintassi v1 è quella di default: le regole richiedono `if` e `contains`/`in` sono keyword native; i vecchi `allow { ... }` e `import future.keywords` non compilano senza `--v0-compatible`. `time.now_ns()` cambia a ogni valutazione: per test deterministici passare l'ora via `input`.

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

```groovy
// Script Console — lista le credenziali dello store di sistema (dominio global)
def store = Jenkins.instance.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0]
store.getCredentials(com.cloudbees.plugins.credentials.domains.Domain.global()).each {
  println "ID: ${it.id} — Type: ${it.class.simpleName}"
}
```

```bash
# Verifica via CLI Jenkins
java -jar jenkins-cli.jar -s https://jenkins.corp.example.com/ \
  -auth admin:${API_TOKEN} \
  list-credentials-as-xml system::system::jenkins   # store di sistema; per un folder: folder::items::<nome-folder>
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
          def user = currentBuild.getBuildCauses('hudson.model.Cause$UserIdCause')[0]?.userId ?: 'timer/api'
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
# Assicurarsi che "Log Location" punti a un path persistente (PVC)
# e che "Log File Size" / "Log File Count" siano adeguati alla retention richiesta

# Lettura diretta del log audit (stesso path configurato in CasC)
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
