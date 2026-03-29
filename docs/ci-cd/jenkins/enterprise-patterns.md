---
title: "Jenkins Enterprise Patterns"
slug: enterprise-patterns
category: ci-cd
tags: [jenkins, enterprise, multibranch, monorepo, pipeline-as-code, promotion, governance]
search_keywords: [jenkins enterprise, multibranch pipeline, branch strategy, pipeline governance, build promotion, monorepo pipeline, jenkinsfile, shared library governance, parameterized builds, matrix builds enterprise, blue ocean, pipeline templates, trunk-based development, gitflow jenkins]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/pipeline-fundamentals, ci-cd/jenkins/shared-libraries, ci-cd/jenkins/agent-infrastructure, ci-cd/jenkins/security-governance, ci-cd/gitops/argocd]
official_docs: https://www.jenkins.io/doc/book/pipeline/multibranch/
status: complete
difficulty: expert
last_updated: 2026-03-28
---

# Jenkins Enterprise Patterns

## Panoramica

I pattern enterprise Jenkins riguardano come strutturare pipeline complesse a scala organizzativa: gestione di decine o centinaia di repository, strategie di branching, promozione dei build tra ambienti, governance del codice di pipeline, e architetture CI/CD per monorepo. Questi pattern permettono a team platform/DevOps di fornire CI/CD come servizio interno con guardrail, standardizzazione e autonomia controllata. La differenza rispetto ai pattern base è la gestione della complessità organizzativa e non solo tecnica.

## Multibranch Pipeline

Il **Multibranch Pipeline** è il fondamento della CI/CD moderna con Jenkins: ogni branch del repository ottiene automaticamente la propria pipeline basata sul `Jenkinsfile` nella root.

### Configurazione via JCasC

```yaml
# jenkins-casc.yaml — sezione jobs
jobs:
  - script: |
      multibranchPipelineJob('myapp') {
        branchSources {
          github {
            id('myapp-source')
            repoOwner('my-org')
            repository('myapp')
            repositoryUrl('https://github.com/my-org/myapp')
            credentialsId('github-app-credentials')
            traits {
              gitHubBranchDiscovery {
                strategyId(1)  // 1=Exclude forks, 2=Only forks, 3=All
              }
              gitHubPullRequestDiscovery {
                strategyId(2)  // 2=Merge con target branch
              }
              headWildcardFilter {
                includes('main release/* feature/* hotfix/*')
                excludes('')
              }
            }
          }
        }
        orphanedItemStrategy {
          discardOldItems {
            numToKeep(30)
            daysToKeep(60)
          }
        }
        triggers {
          periodic(5)  // scan ogni 5 minuti se webhook non disponibile
        }
        configure { node ->
          // Abilita filtro per Jenkinsfile personalizzato
          node / 'factory'(class: 'org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory') {
            owner(class: 'com.cloudbees.hudson.plugins.folder.Folder', reference: '../..')
            scriptPath('ci/Jenkinsfile')  // path custom invece di root
          }
        }
      }
```

### Branch-Specific Behavior nel Jenkinsfile

```groovy
// Jenkinsfile
@Library('company-shared-libs@main') _

pipeline {
    agent none

    options {
        buildDiscarder(logRotator(numToKeepStr: branchSpecificRetention()))
        skipDefaultCheckout()
    }

    environment {
        IS_MAIN       = "${env.BRANCH_NAME == 'main'}"
        IS_RELEASE    = "${env.BRANCH_NAME?.startsWith('release/')}"
        IS_HOTFIX     = "${env.BRANCH_NAME?.startsWith('hotfix/')}"
        IS_PR         = "${env.CHANGE_ID != null}"
        DEPLOY_ENV    = getDeployEnv()
    }

    stages {
        stage('Checkout') {
            agent { label 'small' }
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.GIT_AUTHOR      = sh(script: 'git log -1 --format="%an"', returnStdout: true).trim()
                    env.SEMVER          = calculateVersion()
                }
                stash name: 'source', includes: '**/*', excludes: '.git/**'
            }
        }

        stage('Build & Test') {
            parallel {
                stage('Unit Tests') {
                    agent { label 'maven' }
                    steps {
                        unstash 'source'
                        sh 'mvn test -T 4 --no-transfer-progress'
                        junit 'target/surefire-reports/**/*.xml'
                    }
                }
                stage('Static Analysis') {
                    agent { label 'sonar' }
                    when { not { changeRequest() } }  // skip su PR draft
                    steps {
                        unstash 'source'
                        withSonarQubeEnv('sonarqube') {
                            sh 'mvn sonar:sonar -Dsonar.branch.name=$BRANCH_NAME'
                        }
                    }
                }
            }
        }

        stage('Quality Gate') {
            agent { label 'small' }
            when { not { changeRequest() } }
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build Image') {
            agent { label 'kaniko' }
            when { anyOf { branch 'main'; branch 'release/*'; branch 'hotfix/*' } }
            steps {
                unstash 'source'
                buildDockerImage(
                    image: "myapp",
                    tag: env.SEMVER,
                    platforms: ['linux/amd64', 'linux/arm64']
                )
            }
        }

        stage('Deploy Staging') {
            agent { label 'helm' }
            when {
                allOf {
                    anyOf { branch 'main'; branch 'release/*' }
                    not { changeRequest() }
                }
            }
            steps {
                deployToEnvironment(env: 'staging', version: env.SEMVER)
            }
        }

        stage('Integration Tests') {
            agent { label 'test-runner' }
            when { expression { env.DEPLOY_ENV != null } }
            steps {
                runIntegrationTests(env: env.DEPLOY_ENV, timeout: 20)
            }
        }

        stage('Deploy Production') {
            agent { label 'helm' }
            when { branch 'main' }
            steps {
                input(
                    message: "Deploy ${env.SEMVER} in produzione?",
                    submitter: 'release-managers',
                    parameters: [
                        choice(
                            name: 'STRATEGY',
                            choices: ['canary', 'blue-green', 'rolling'],
                            description: 'Strategia di deployment'
                        )
                    ]
                )
                deployToProduction(version: env.SEMVER, strategy: params.STRATEGY)
            }
        }
    }

    post {
        always {
            publishBuildMetrics()  // custom step: invia a Prometheus Pushgateway
        }
        failure {
            notifySlack(
                channel: getNotificationChannel(),
                message: "Build FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
            )
        }
        success {
            when { branch 'main' }
            tagGitRelease(version: env.SEMVER)
        }
    }
}

// Funzioni helper (possono stare nel Jenkinsfile o in shared library)
String branchSpecificRetention() {
    if (env.BRANCH_NAME == 'main') return '100'
    if (env.BRANCH_NAME?.startsWith('release/')) return '50'
    return '10'
}

String getDeployEnv() {
    if (env.BRANCH_NAME == 'main') return 'staging'
    if (env.BRANCH_NAME?.startsWith('release/')) return 'staging'
    return null
}
```

## Pipeline Organization per Folder

### Folder Structure con Job DSL

I **Folders** Jenkins permettono di replicare la gerarchia organizzativa (team/squad/prodotto):

```groovy
// seed-job/Jenkinsfile — Job DSL seed job
@Library('company-shared-libs@main') _

pipeline {
    agent { label 'small' }

    parameters {
        string(name: 'REPO_FILTER', defaultValue: '', description: 'Filtra per nome repository')
    }

    stages {
        stage('Seed Jobs') {
            steps {
                jobDsl(
                    targets: 'seed-job/jobs/**/*.groovy',
                    removedJobAction: 'IGNORE',
                    removedViewAction: 'IGNORE',
                    lookupStrategy: 'SEED_JOB',
                    additionalParameters: [
                        REPO_FILTER: params.REPO_FILTER,
                        GITHUB_ORG: 'my-org'
                    ]
                )
            }
        }
    }
}
```

```groovy
// seed-job/jobs/platform-team.groovy — Job DSL script
def teams = [
    [name: 'platform', repos: ['infra-base', 'monitoring-stack', 'security-policies']],
    [name: 'backend',  repos: ['api-gateway', 'auth-service', 'payment-service']],
    [name: 'frontend', repos: ['web-app', 'admin-portal', 'mobile-bff']],
]

teams.each { team ->
    folder("${team.name}") {
        displayName("Team ${team.name.capitalize()}")
        description("Pipeline del team ${team.name}")

        // Credenziali accessibili solo a questo folder
        properties {
            folderCredentialsProperty {
                domainCredentials {
                    domainCredentials {
                        domain { name('') }
                        credentials {
                            string {
                                scope('GLOBAL')
                                id("${team.name}-api-key")
                                secret('')  // placeholder — impostare manualmente
                                description("API Key team ${team.name}")
                            }
                        }
                    }
                }
            }
        }
    }

    team.repos.each { repo ->
        multibranchPipelineJob("${team.name}/${repo}") {
            displayName("${repo}")
            branchSources {
                github {
                    repoOwner(GITHUB_ORG)
                    repository(repo)
                    credentialsId('github-app-global')
                    traits {
                        gitHubBranchDiscovery { strategyId(1) }
                        gitHubPullRequestDiscovery { strategyId(2) }
                    }
                }
            }
            configure { node ->
                node / 'factory'(class: 'org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory') {
                    owner(class: 'com.cloudbees.hudson.plugins.folder.Folder', reference: '../..')
                    scriptPath('Jenkinsfile')
                }
            }
        }
    }
}
```

## Build Promotion e Artifact Lifecycle

### Immutable Artifact Pattern

Il pattern corretto è: **build once, promote many times**. Un artifact viene buildato una sola volta e promosso tra gli ambienti tramite aggiornamento dei metadati/tags, mai ribuildata.

```groovy
// vars/promoteArtifact.groovy
def call(Map config) {
    /*
     * Promuove un artifact da un registro verso l'ambiente target.
     * Usa `crane` (go-containerregistry) per copiare image senza re-pull/push.
     *
     * config.sourceTag    — tag sorgente (es. "1.2.3-rc.5")
     * config.targetEnv    — ambiente target ('staging', 'production')
     * config.image        — nome image (es. "my-org/myapp")
     * config.approver     — utente Jenkins approvatore
     */
    def registryBase = "registry.my-org.internal"
    def sourceImage  = "${registryBase}/${config.image}:${config.sourceTag}"
    def targetTag    = "${config.targetEnv}-${config.sourceTag}"
    def targetImage  = "${registryBase}/${config.image}:${targetTag}"

    // Verifica prerequisiti
    def scanResult = sh(
        script: "trivy image --exit-code 1 --severity CRITICAL ${sourceImage}",
        returnStatus: true
    )
    if (scanResult != 0) {
        error "Security scan fallito per ${sourceImage}: vulnerabilità CRITICAL trovate"
    }

    // Promuovi con crane (copia manifest senza re-download)
    withCredentials([usernamePassword(
        credentialsId: 'registry-credentials',
        usernameVariable: 'REG_USER',
        passwordVariable: 'REG_PASS'
    )]) {
        sh """
            crane auth login ${registryBase} -u \$REG_USER -p \$REG_PASS
            crane copy ${sourceImage} ${targetImage}
            crane tag ${targetImage} latest-${config.targetEnv}
        """
    }

    // Firma il manifest promosso (Cosign)
    withCredentials([string(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY')]) {
        sh """
            echo "\$COSIGN_KEY" > /tmp/cosign.key
            cosign sign --key /tmp/cosign.key \
                --annotations env=${config.targetEnv} \
                --annotations promoted-by=${config.approver} \
                --annotations promoted-at=\$(date -u +%Y-%m-%dT%H:%M:%SZ) \
                ${targetImage}
            rm /tmp/cosign.key
        """
    }

    // Notifica Jira/Confluence con deployment record
    jiraComment(
        issueKey: env.JIRA_ISSUE ?: extractJiraKey(env.GIT_BRANCH),
        body: "✅ Promoted to **${config.targetEnv}**: `${targetImage}`"
    )

    return targetImage
}
```

### Release Train Pattern

```groovy
// vars/releaseTrain.groovy — coordina il rilascio di più microservizi
def call(Map config = [:]) {
    def services = config.services ?: error("Lista servizi richiesta")
    def targetEnv = config.env ?: 'staging'
    def version   = config.version ?: error("Version richiesta")

    // Build promotion parallela per tutti i servizi
    def promotions = services.collectEntries { service ->
        ["Promote ${service}" : {
            stage("Promote ${service}") {
                def targetImage = promoteArtifact(
                    image: "my-org/${service}",
                    sourceTag: "${version}",
                    targetEnv: targetEnv,
                    approver: env.BUILD_USER_ID
                )
                // Aggiorna Helm values nel GitOps repo
                updateGitOpsManifest(
                    repo: 'gitops-manifests',
                    service: service,
                    env: targetEnv,
                    imageTag: "${targetEnv}-${version}"
                )
            }
        }]
    }

    parallel promotions

    // Smoke tests post-deploy
    stage("Smoke Tests ${targetEnv}") {
        build(
            job: "smoke-tests/${targetEnv}",
            parameters: [string(name: 'VERSION', value: version)],
            propagate: true,
            wait: true
        )
    }
}
```

## Monorepo Strategies

Un monorepo con decine di servizi richiede pipeline intelligenti che buildino SOLO i componenti modificati.

### Changed-Path Detection

```groovy
// vars/getChangedPaths.groovy
@NonCPS
List<String> call() {
    def changeLogSets = currentBuild.changeSets
    def changedFiles = [] as Set

    changeLogSets.each { logSet ->
        logSet.items.each { entry ->
            entry.affectedFiles.each { file ->
                changedFiles << file.path
            }
        }
    }

    return changedFiles.toList()
}
```

```groovy
// vars/monorepoMatrix.groovy — determina quali servizi buildare
def call(Map config = [:]) {
    def changedFiles = getChangedPaths()
    def services = config.services
    def forceBuildAll = config.forceBuildAll ?: false

    if (forceBuildAll || env.BRANCH_NAME == 'main') {
        echo "Build completo: tutti ${services.size()} servizi"
        return services
    }

    def servicesToBuild = services.findAll { service ->
        def serviceDir = config.serviceDir ?: service
        def relevantChange = changedFiles.any { file ->
            file.startsWith("${serviceDir}/") ||
            file.startsWith("shared-libs/") ||      // dipendenza condivisa
            file == 'pom.xml' ||                    // POM root cambiato
            file == '.jenkins/defaults.groovy'      // config CI globale
        }
        if (relevantChange) {
            echo "Servizio ${service}: modificato, verrà buildato"
        }
        return relevantChange
    }

    if (servicesToBuild.isEmpty()) {
        echo "Nessun servizio modificato. Skip build."
        currentBuild.result = 'NOT_BUILT'
    }

    return servicesToBuild
}
```

### Monorepo Pipeline Completa

```groovy
// Jenkinsfile — root del monorepo
@Library('company-shared-libs@main') _

// Definizione centralizzata dei servizi
def SERVICES = [
    [name: 'api-gateway',      dir: 'services/api-gateway',   type: 'java'],
    [name: 'auth-service',     dir: 'services/auth-service',  type: 'java'],
    [name: 'payment-service',  dir: 'services/payment',       type: 'node'],
    [name: 'notification-svc', dir: 'services/notification',  type: 'python'],
    [name: 'frontend',         dir: 'frontend',               type: 'node'],
]

pipeline {
    agent { label 'small' }

    options {
        buildDiscarder(logRotator(numToKeepStr: '50'))
        skipDefaultCheckout()
        disableConcurrentBuilds(abortPrevious: true)  // cancella build precedente stesso branch
    }

    parameters {
        booleanParam(name: 'FORCE_BUILD_ALL', defaultValue: false, description: 'Forzare build di tutti i servizi')
        string(name: 'SPECIFIC_SERVICE', defaultValue: '', description: 'Buildare solo un servizio specifico')
    }

    stages {
        stage('Checkout & Detect Changes') {
            steps {
                checkout scm
                script {
                    env.VERSION = sh(script: './scripts/calculate-version.sh', returnStdout: true).trim()

                    def servicesToBuild = params.SPECIFIC_SERVICE ?
                        SERVICES.findAll { it.name == params.SPECIFIC_SERVICE } :
                        monorepoMatrix(
                            services: SERVICES.collect { it.name },
                            serviceDir: SERVICES.collectEntries { [(it.name): it.dir] },
                            forceBuildAll: params.FORCE_BUILD_ALL
                        ).collect { name -> SERVICES.find { it.name == name } }

                    env.SERVICES_TO_BUILD = groovy.json.JsonOutput.toJson(
                        servicesToBuild.collect { it.name }
                    )

                    echo "Servizi da buildare: ${servicesToBuild.collect { it.name }}"

                    if (servicesToBuild.isEmpty()) {
                        currentBuild.result = 'NOT_BUILT'
                        return
                    }

                    // Stash source per gli agent paralleli
                    stash name: 'monorepo-source', includes: '**/*', excludes: '.git/**'
                }
            }
        }

        stage('Build & Test') {
            when { expression { currentBuild.result != 'NOT_BUILT' } }
            steps {
                script {
                    def services = groovy.json.JsonParser.parseText(env.SERVICES_TO_BUILD)
                    def buildStages = SERVICES
                        .findAll { it.name in services }
                        .collectEntries { service ->
                            ["Build ${service.name}" : {
                                stage("Build ${service.name}") {
                                    node(getBuildAgent(service.type)) {
                                        unstash 'monorepo-source'
                                        dir(service.dir) {
                                            runBuildForType(service)
                                        }
                                    }
                                }
                            }]
                        }

                    parallel buildStages
                }
            }
        }

        stage('Security Scan') {
            when {
                allOf {
                    expression { currentBuild.result != 'NOT_BUILT' }
                    anyOf { branch 'main'; branch 'release/*' }
                }
            }
            steps {
                script {
                    def services = groovy.json.JsonParser.parseText(env.SERVICES_TO_BUILD)
                    def scanStages = services.collectEntries { name ->
                        ["Scan ${name}" : {
                            node('kaniko') {
                                sh "trivy image my-org/${name}:${env.VERSION}-ci --exit-code 1 --severity CRITICAL,HIGH"
                            }
                        }]
                    }
                    parallel scanStages
                }
            }
        }
    }
}

String getBuildAgent(String type) {
    switch(type) {
        case 'java':   return 'maven'
        case 'node':   return 'node'
        case 'python': return 'python'
        default:       return 'small'
    }
}

void runBuildForType(Map service) {
    switch(service.type) {
        case 'java':
            sh 'mvn package -DskipTests=false --no-transfer-progress'
            junit 'target/surefire-reports/**/*.xml'
            break
        case 'node':
            sh 'npm ci && npm test && npm run build'
            junit 'test-results/**/*.xml'
            break
        case 'python':
            sh 'pip install -r requirements-dev.txt && pytest --junitxml=test-results.xml'
            junit 'test-results.xml'
            break
    }

    // Build e push image
    withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
        sh """
            /kaniko/executor \
                --context=. \
                --dockerfile=Dockerfile \
                --destination=registry.my-org.internal/my-org/${service.name}:${env.VERSION}-ci \
                --cache=true \
                --cache-repo=registry.my-org.internal/cache
        """
    }
}
```

## Parameterized Build Patterns

### Dynamic Parameters con Active Choices Plugin

```groovy
// Jenkinsfile con parametri dinamici
properties([
    parameters([
        // Selezione environment
        choice(
            name: 'TARGET_ENV',
            choices: ['dev', 'staging', 'staging-eu', 'production', 'production-eu'],
            description: 'Ambiente target del deploy'
        ),
        // Parametro attivo: versioni dipendono da TARGET_ENV
        [$class: 'CascadeChoiceParameter',
            name: 'VERSION',
            description: 'Versione da deployare',
            referencedParameters: 'TARGET_ENV',
            choiceType: 'PT_SINGLE_SELECT',
            script: [$class: 'GroovyScript',
                script: [
                    classpath: [],
                    sandbox: true,
                    script: '''
                        // Script eseguito dinamicamente nel browser
                        def env = TARGET_ENV ?: 'dev'
                        def apiUrl = "https://registry-api.my-org.internal/v2/myapp/tags/list"
                        def conn = new URL(apiUrl).openConnection()
                        conn.setRequestProperty("Accept", "application/json")
                        def json = new groovy.json.JsonSlurper().parse(conn.inputStream)
                        return json.tags.findAll {
                            env == 'production' ? it.matches('\\d+\\.\\d+\\.\\d+') : true
                        }.sort().reverse().take(20)
                    ''',
                    fallbackScript: [classpath: [], sandbox: true, script: 'return ["latest"]']
                ]
            ]
        ],
        booleanParam(
            name: 'DRY_RUN',
            defaultValue: false,
            description: 'Simula deploy senza applicare modifiche'
        ),
        text(
            name: 'EXTRA_VALUES',
            defaultValue: '',
            description: 'Helm values override in formato YAML'
        )
    ])
])
```

### Build con Approval Matrix per Ambiente

```groovy
// vars/deployWithApproval.groovy
def call(Map config) {
    def env         = config.env
    def version     = config.version
    def approvers   = getApproversForEnv(env)
    def timeoutMins = getTimeoutForEnv(env)

    // Gate di approvazione
    timeout(time: timeoutMins, unit: 'MINUTES') {
        def approval = input(
            message: """
🚀 Deploy ${version} → **${env.toUpperCase()}**

Repository: ${env.GIT_URL}
Branch: ${env.GIT_BRANCH}
Commit: ${env.GIT_COMMIT_SHORT}
""",
            submitter: approvers,
            submitterParameter: 'APPROVER',
            parameters: [
                booleanParam(name: 'CONFIRM', defaultValue: false, description: 'Confermo il deploy'),
                text(name: 'REASON', defaultValue: '', description: 'Motivo del deploy (obbligatorio per production)')
            ]
        )

        if (!approval.CONFIRM) {
            error "Deploy annullato dall'approvatore ${approval.APPROVER}"
        }

        if (env == 'production' && !approval.REASON?.trim()) {
            error "Motivo obbligatorio per deploy in produzione"
        }

        // Audit log
        auditLog(action: 'deploy', env: env, version: version, approver: approval.APPROVER, reason: approval.REASON)
    }

    // Deploy effettivo
    sh """
        helm upgrade --install myapp ./helm/myapp \
            --namespace ${env} \
            --set image.tag=${version} \
            ${config.dryRun ? '--dry-run' : ''} \
            --atomic \
            --timeout 10m \
            --history-max 5
    """
}

@NonCPS
private String getApproversForEnv(String env) {
    def matrix = [
        'dev':          'developers,qa-engineers',
        'staging':      'senior-developers,qa-leads',
        'production':   'release-managers,tech-leads',
        'production-eu':'release-managers,compliance-team'
    ]
    return matrix[env] ?: 'release-managers'
}

@NonCPS
private int getTimeoutForEnv(String env) {
    return env.contains('production') ? 30 : 15
}
```

## Pipeline-as-Code Governance

### Validazione Jenkinsfile in CI

```groovy
// validate-jenkinsfile-job/Jenkinsfile — job dedicato alla validazione
pipeline {
    agent { label 'small' }

    stages {
        stage('Validate Jenkinsfiles') {
            steps {
                script {
                    def findResult = sh(
                        script: "find . -name 'Jenkinsfile*' -not -path './.git/*'",
                        returnStdout: true
                    ).trim()

                    if (!findResult) {
                        echo "Nessun Jenkinsfile trovato"
                        return
                    }

                    def jenkinsfiles = findResult.split('\n')
                    def failures = []

                    jenkinsfiles.each { jf ->
                        def status = sh(
                            script: """
                                curl -s --fail \
                                    -X POST \
                                    -F "jenkinsfile=<${jf}" \
                                    ${env.JENKINS_URL}pipeline-model-converter/validate
                            """,
                            returnStatus: true
                        )

                        if (status != 0) {
                            failures << jf
                            echo "❌ Invalido: ${jf}"
                        } else {
                            echo "✅ Valido: ${jf}"
                        }
                    }

                    if (failures) {
                        error "Jenkinsfile non validi: ${failures.join(', ')}"
                    }
                }
            }
        }

        stage('Check Required Sections') {
            steps {
                script {
                    def requiredSections = ['agent', 'stages', 'post']
                    def violations = []

                    sh("find . -name 'Jenkinsfile' -not -path './.git/*'").split('\n').each { jf ->
                        def content = readFile(jf)
                        requiredSections.each { section ->
                            if (!content.contains(section)) {
                                violations << "${jf}: manca sezione '${section}'"
                            }
                        }
                        // Verifica che non usino password in chiaro
                        if (content =~ /password\s*=\s*['"][^'"]+['"]/) {
                            violations << "${jf}: possibile password in chiaro"
                        }
                    }

                    if (violations) {
                        violations.each { echo "⚠️ ${it}" }
                        unstable("Violazioni policy trovate nel Jenkinsfile")
                    }
                }
            }
        }
    }
}
```

### Pipeline Template Catalog

Il **Pipeline Template Catalog** (feature CloudBees o pattern custom) permette di centralizzare template approvati:

```groovy
// vars/catalogPipeline.groovy — entry point del template catalog
def call(Map config) {
    def pipelineType = config.type ?: error("Tipo pipeline richiesto: java-service, node-app, python-lib, helm-chart")

    // Carica template corrispondente
    switch(pipelineType) {
        case 'java-service':
            javaServicePipeline(config)
            break
        case 'node-app':
            nodeAppPipeline(config)
            break
        case 'python-lib':
            pythonLibPipeline(config)
            break
        case 'helm-chart':
            helmChartPipeline(config)
            break
        default:
            error "Tipo pipeline non supportato: ${pipelineType}"
    }
}
```

```groovy
// Jenkinsfile minimalissimo nel repository applicativo
@Library('company-shared-libs@main') _

catalogPipeline(
    type: 'java-service',
    serviceName: 'auth-service',
    helmChart: 'auth-service',
    sonarProjectKey: 'auth-service',
    deployTo: ['staging', 'production'],
    notifications: [slack: '#team-backend']
)
```

## Ottimizzazione Build Time

### Analisi Timing con Build History

```groovy
// vars/analyzeBuildTiming.groovy — analizza colli di bottiglia
@NonCPS
def call() {
    def build = currentBuild
    def stageTimings = []

    build.stages.each { stage ->
        stageTimings << [
            name:     stage.name,
            duration: stage.durationMillis,
            status:   stage.status
        ]
    }

    // Identifica stage più lenti
    def sorted = stageTimings.sort { -it.duration }
    def report = "=== Build Timing Report ===\n"
    sorted.each { s ->
        def minutes = s.duration / 60000
        report += sprintf("%-30s %5.1f min [%s]\n", s.name, minutes, s.status)
    }

    echo report

    // Invia a Prometheus Pushgateway per dashboard Grafana
    def metricsPayload = stageTimings.collect { s ->
        "jenkins_stage_duration_ms{job=\"${env.JOB_NAME}\",stage=\"${s.name}\"} ${s.duration}"
    }.join('\n')

    sh """
        echo '${metricsPayload}' | curl --data-binary @- \
            http://pushgateway.monitoring:9091/metrics/job/jenkins/instance/${env.JOB_NAME}
    """
}
```

## Trunk-Based Development vs GitFlow

| Aspetto | Trunk-Based Development | GitFlow |
|---------|------------------------|---------|
| Branch principali | `main` (+ feature branch brevi) | `main`, `develop`, `release/*`, `hotfix/*` |
| Durata feature branch | Ore o 1-2 giorni | Settimane |
| Integration | Continua (più volte al giorno) | Periodica (merge in develop) |
| Release | Qualsiasi commit in main è releasable | Da `release/*` branch |
| CI complexity | Semplice (1 pipeline) | Complessa (pipeline per tipo branch) |
| Indicato per | Team maturi, microservizi, CD | Monoliti, release schedulate, team numerosi |
| Rischio merge conflict | Basso (branch piccoli e frequenti) | Alto (branch longevi) |
| Feature flags | Richiesto per hide WIP | Opzionale |

### Configurazione Jenkins per TBD

```groovy
// Jenkinsfile per Trunk-Based Development
// Ogni commit su main → deploy automatico in staging
// Tag semver → deploy in production

pipeline {
    agent { label 'standard' }

    triggers {
        githubPush()  // webhook su ogni push
    }

    stages {
        stage('Fast Check') {
            // Build veloci per feedback immediato (<5 min)
            parallel {
                stage('Lint') { steps { sh 'make lint' } }
                stage('Unit Tests') { steps { sh 'make test-unit' } }
                stage('Security Baseline') { steps { sh 'make snyk-test' } }
            }
        }

        stage('Build & Push') {
            when { branch 'main' }
            steps {
                sh "make docker-build docker-push VERSION=${env.GIT_COMMIT_SHORT}"
            }
        }

        stage('Auto Deploy Staging') {
            when { branch 'main' }
            steps {
                // Deploy automatico senza approvazione
                sh "make deploy ENV=staging VERSION=${env.GIT_COMMIT_SHORT}"
                sh "make smoke-test ENV=staging"
            }
        }

        stage('Deploy Production') {
            when {
                // Deploy solo se il commit è taggato con semver
                tag pattern: /^v\d+\.\d+\.\d+$/, comparator: 'REGEXP'
            }
            steps {
                deployWithApproval(
                    env: 'production',
                    version: env.TAG_NAME
                )
            }
        }
    }
}
```

## Best Practices

| Pattern | Raccomandazione |
|---------|----------------|
| Checkout | Usare `checkout scm` + `skipDefaultCheckout()` con stash per cache efficiente |
| Concorrenza | `disableConcurrentBuilds(abortPrevious: true)` su feature branch |
| Retries | Solo su operazioni idempotenti (push image, deploy ArgoCD) |
| Secrets | Mai in env variabili globali; usare sempre `withCredentials` con scope minimo |
| Build artifacts | Immutable + promotion: build once, tag many times |
| Monorepo | Changed-path detection + parallel per-service builds |
| Timeout | Sempre sui gate manuali (`input`) e chiamate esterne |
| Post | `always { cleanWs() }` su agent con storage limitato |
| Versioning | SemVer automatico da commit (conventional commits + semantic-release) |
| Observability | Metriche build a Prometheus, log strutturati, distributed tracing per pipeline |

## Troubleshooting

### Scenario 1 — Pipeline bloccata in "waiting for next executor"

**Sintomo:** La pipeline resta in coda con messaggio `Waiting for next available executor` e non parte.

**Causa:** L'agent pool è esaurito: tutti gli executor (statici o pod dinamici) sono occupati da altre build. Su Kubernetes, può indicare ResourceQuota esaurita o nodi insufficienti.

**Soluzione:** Verificare lo stato degli agent e aumentare la capacità:

```bash
# Verificare pod Jenkins agent su Kubernetes
kubectl get pods -n jenkins -l jenkins=agent
kubectl describe quota -n jenkins          # controlla ResourceQuota

# Aumentare max agent nel JCasC (jenkins-casc.yaml)
# kubernetes.maxRequestsPerHostStr: "32"
# oppure ridurre parallelism nel Pod Template

# Verificare executor occupati via API
curl -s "$JENKINS_URL/computer/api/json?pretty=true" | \
  jq '.computer[] | {name: .displayName, busy: .countBusyExecutors, total: .countTotalExecutors}'
```

---

### Scenario 2 — `RejectedAccessException` in script sandbox

**Sintomo:** Build fallisce con `org.jenkinsci.plugins.scriptsecurity.sandbox.RejectedAccessException: Scripts not permitted to use method...`

**Causa:** Il codice nella shared library o nel Jenkinsfile usa API Java/Groovy non incluse nella whitelist della Groovy Sandbox. È una misura di sicurezza Jenkins.

**Soluzione:** Approvare il metodo in *Manage Jenkins → In-process Script Approval* oppure refactoring del codice:

```groovy
// PRIMA (causa l'errore): iterazione diretta su tipo non approvato
def result = someList.collectEntries { ... }

// DOPO opzione 1: annotare con @NonCPS i metodi che usano API Groovy native
@NonCPS
def myHelper(List items) {
    return items.collectEntries { [it.name, it.value] }
}

// DOPO opzione 2: spostare in classe src/ (fuori dalla sandbox)
// src/com/myorg/Utils.groovy — eseguito fuori sandbox
```

```bash
# Vedere tutti i metodi in attesa di approvazione
curl -s "$JENKINS_URL/scriptApproval/api/json" | jq '.pendingScripts[].script'
```

---

### Scenario 3 — Build time in crescita costante nel tempo

**Sintomo:** Pipeline che in passato durava 8 min ora impiega 25 min senza modifiche significative al codice.

**Causa:** Accumulo di problemi: repository git cresciuto (checkout lento), dipendenze non cachate tra build, test non parallelizzati, agent che non riusa layer Docker cache.

**Soluzione:** Diagnosticare con timing analysis e applicare ottimizzazioni mirate:

```groovy
// Aggiungere al Jenkinsfile per diagnostica
post { always { analyzeBuildTiming() } }
```

```bash
# Shallow clone per ridurre checkout time
git clone --depth=50 <repo>

# Nel Jenkinsfile: limitare la profondità del checkout
checkout([$class: 'GitSCM',
    branches: [[name: env.BRANCH_NAME]],
    extensions: [[$class: 'CloneOption', depth: 50, shallow: true]],
    userRemoteConfigs: scm.userRemoteConfigs
])

# Verificare hit/miss cache Maven (PVC)
kubectl exec -n jenkins <agent-pod> -- du -sh /root/.m2/repository
```

---

### Scenario 4 — Multibranch non rileva nuovi branch o PR

**Sintomo:** Un nuovo branch o PR creato su GitHub non compare automaticamente in Jenkins. Scan manuale funziona ma webhook no.

**Causa:** GitHub App non ha i permessi corretti, oppure il webhook non è configurato/raggiungibile, oppure il pattern di inclusione branch esclude il branch in questione.

**Soluzione:** Verificare permessi, webhook e pattern filtro:

```bash
# Verificare che il webhook arrivi (ispezionare in GitHub → repo → Settings → Webhooks)
# Payload URL: https://<jenkins-url>/github-webhook/
# Content type: application/json
# Events: Push + Pull Requests

# Verificare log scanning in Jenkins
# Manage Jenkins → System Log → filtro "com.cloudbees.jenkins.plugins.bitbucket"
# o "org.jenkinsci.plugins.github_branch_source"

# Testare manualmente la connessione con curl
curl -I -H "Authorization: Bearer <github-app-token>" \
  https://api.github.com/repos/my-org/my-repo/branches
```

Controllare che il filtro `headWildcardFilter` includa il pattern del branch:

```groovy
// Verificare che il pattern copra il branch
headWildcardFilter {
    includes('main release/* feature/* hotfix/* fix/*')
    excludes('dependabot/*')
}
```

---

### Scenario 5 — `ConcurrentModificationException` su liste Groovy in pipeline

**Sintomo:** Build fallisce con `java.util.ConcurrentModificationException` durante iterazione su liste o mappe in codice pipeline.

**Causa:** Pattern tipico del CPS (Continuation-Passing Style) transformation di Jenkins: alcune operazioni Groovy su collezioni non sono thread-safe nel contesto CPS serializzabile.

**Soluzione:** Usare `.toList()` / `.clone()` per creare copie prima di iterare, oppure isolare il codice con `@NonCPS`:

```groovy
// PROBLEMATICO: iterazione diretta su lista condivisa
def myList = [1, 2, 3]
myList.each { item ->
    myList.remove(item)  // ConcurrentModificationException
}

// CORRETTO opzione 1: copia prima di iterare
myList.toList().each { item ->
    myList.remove(item)
}

// CORRETTO opzione 2: metodo @NonCPS per logica complessa
@NonCPS
List<String> filterServices(List<Map> services, List<String> changed) {
    return services
        .findAll { svc -> changed.any { f -> f.startsWith("${svc.dir}/") } }
        .collect { it.name }
}
```

## Riferimenti

- [Jenkins Pipeline Best Practices](https://www.jenkins.io/doc/book/pipeline/pipeline-best-practices/)
- [Multibranch Pipeline](https://www.jenkins.io/doc/book/pipeline/multibranch/)
- [Job DSL Plugin Reference](https://jenkinsci.github.io/job-dsl-plugin/)
- [Trunk Based Development](https://trunkbaseddevelopment.com/)
- [DORA Metrics — State of DevOps Report](https://cloud.google.com/devops/state-of-devops/)
