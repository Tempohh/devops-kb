---
title: "Jenkins Pipeline — Fondamentali"
slug: jenkins-pipeline-fundamentals
category: ci-cd
tags: [jenkins, pipeline, declarative, scripted, groovy, stages, parallel, matrix, cps, jenkinsfile]
search_keywords: [Jenkins Declarative Pipeline, Jenkins Scripted Pipeline, Jenkinsfile, Groovy pipeline, stages Jenkins, parallel stages Jenkins, matrix pipeline, CPS Continuation Passing Style, "@NonCPS Jenkins", stash unstash Jenkins, input step Jenkins, post conditions Jenkins, when directive Jenkins, pipeline options, environment variables Jenkins, withCredentials, timeout retry]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/shared-libraries, ci-cd/jenkins/agent-infrastructure, ci-cd/jenkins/enterprise-patterns]
official_docs: https://www.jenkins.io/doc/book/pipeline/
status: complete
difficulty: intermediate
last_updated: 2026-03-03
---

# Jenkins Pipeline — Fondamentali

## Declarative vs Scripted Pipeline

Jenkins offre due sintassi per le pipeline:

| | Declarative | Scripted |
|---|------------|---------|
| Sintassi | Struttura `pipeline { }` rigida | Groovy puro, massima libertà |
| Leggibilità | Alta | Media-bassa |
| Validazione | Lint preventivo | Solo a runtime |
| Post conditions | `post { }` nativo | try/catch/finally |
| Quando usare | Default per tutto | Logica complessa, casi edge |
| Mescolare | Sì, con `script { }` block | Sì, wrap in `pipeline { }` |

**Regola pratica:** inizia sempre con Declarative. Usa `script { }` per parti Groovy complesse dentro un Declarative Pipeline. Passa a Scripted solo se la struttura Declarative diventa un ostacolo.

---

## Declarative Pipeline — Sintassi Completa

```groovy
// Jenkinsfile
pipeline {

    // ── Agent ──────────────────────────────────────────────────────────────
    agent {
        kubernetes {                        // agent Kubernetes (Pod dinamico)
            inheritFrom 'base-pod'
            yaml """
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: maven
    image: maven:3.9-eclipse-temurin-21
    command: [sleep, infinity]
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1000m"
    volumeMounts:
    - name: m2-cache
      mountPath: /root/.m2
  volumes:
  - name: m2-cache
    persistentVolumeClaim:
      claimName: maven-cache-pvc
"""
        }
    }

    // ── Options ────────────────────────────────────────────────────────────
    options {
        timeout(time: 60, unit: 'MINUTES')        // timeout globale build
        retry(2)                                   // retry in caso di failure infrastrutturale
        buildDiscarder(logRotator(
            numToKeepStr: '20',                    // mantieni ultimi 20 build
            artifactNumToKeepStr: '5'              // ma solo 5 con artifact
        ))
        timestamps()                               // timestamp su ogni riga di log
        skipDefaultCheckout(true)                  // checkout esplicito (più controllo)
        disableConcurrentBuilds(abortPrevious: true)  // annulla build precedente se nuovo push
        parallelsAlwaysFailFast()                  // parallel: fallisci tutto se uno fallisce
        ansiColor('xterm')                         // colori ANSI nei log
    }

    // ── Environment Variables ───────────────────────────────────────────────
    environment {
        // Variabili statiche
        APP_NAME     = 'myapp'
        DOCKER_REPO  = 'registry.company.com/myteam'
        IMAGE_TAG    = "${env.GIT_COMMIT[0..7]}"  // prime 8 char del commit SHA
        REGISTRY_URL = 'registry.company.com'

        // Secret da Jenkins Credential Store
        DOCKER_CREDS     = credentials('docker-registry-creds')  // username/password
        SONAR_TOKEN      = credentials('sonarqube-token')        // string secret
        GPG_KEY          = credentials('gpg-signing-key')        // file credential

        // Variabile derivata da credenziale (sintassi _USR / _PSW)
        // DOCKER_CREDS_USR e DOCKER_CREDS_PSW disponibili automaticamente
    }

    // ── Parameters (per build parametrizzati) ──────────────────────────────
    parameters {
        booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Skip test fase')
        choice(name: 'DEPLOY_ENV', choices: ['dev', 'staging', 'prod'], description: 'Target environment')
        string(name: 'IMAGE_TAG_OVERRIDE', defaultValue: '', description: 'Override image tag')
        text(name: 'CHANGELOG', defaultValue: '', description: 'Release notes')
        password(name: 'EMERGENCY_TOKEN', defaultValue: '', description: 'Emergency bypass token')
    }

    // ── Triggers ───────────────────────────────────────────────────────────
    triggers {
        cron('H 2 * * 1-5')               // nightly build (lunedì-venerdì, ore 2)
        pollSCM('H/5 * * * *')            // poll ogni 5 minuti (alternativa a webhook)
        // upstream(threshold: SUCCESS, upstreamProjects: 'other-project/main')
    }

    // ── Stages ─────────────────────────────────────────────────────────────
    stages {

        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "${env.GIT_BRANCH}"]],
                    extensions: [
                        [$class: 'CloneOption', depth: 0, noTags: false, shallow: false],
                        [$class: 'SubmoduleOption', recursiveSubmodules: true]
                    ],
                    userRemoteConfigs: [[
                        url: 'https://git.company.com/myteam/myapp.git',
                        credentialsId: 'git-credentials'
                    ]]
                ])
            }
        }

        stage('Build & Test') {
            // Condizione: skip se parametro attivato
            when {
                not { expression { return params.SKIP_TESTS } }
            }
            parallel {
                stage('Unit Tests — Java') {
                    steps {
                        container('maven') {
                            sh 'mvn test -pl :core -Dsurefire.rerunFailingTestsCount=2'
                        }
                    }
                    post {
                        always {
                            junit 'target/surefire-reports/**/*.xml'
                            recordCoverage(
                                tools: [[parser: 'JACOCO', pattern: 'target/site/jacoco/jacoco.xml']],
                                qualityGates: [[threshold: 80.0, metric: 'LINE', baseline: 'PROJECT']]
                            )
                        }
                    }
                }
                stage('Lint & SAST') {
                    steps {
                        container('maven') {
                            sh 'mvn checkstyle:check pmd:check spotbugs:spotbugs'
                        }
                    }
                    post {
                        always {
                            recordIssues(
                                tools: [checkStyle(), pmdParser(), spotBugs()],
                                qualityGates: [[threshold: 5, type: 'TOTAL_HIGH', unstable: true]]
                            )
                        }
                    }
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('company-sonarqube') {
                    container('maven') {
                        sh """
                            mvn sonar:sonar \
                              -Dsonar.projectKey=${APP_NAME} \
                              -Dsonar.branch.name=${env.BRANCH_NAME} \
                              -Dsonar.token=${SONAR_TOKEN}
                        """
                    }
                }
                // Quality Gate: attende risultato da SonarQube (timeout 10 minuti)
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build Container Image') {
            steps {
                container('kaniko') {
                    sh """
                        /kaniko/executor \
                          --context=dir://. \
                          --dockerfile=Dockerfile \
                          --destination=${DOCKER_REPO}/${APP_NAME}:${IMAGE_TAG} \
                          --destination=${DOCKER_REPO}/${APP_NAME}:latest \
                          --cache=true \
                          --cache-repo=${DOCKER_REPO}/cache
                    """
                }
            }
        }

        stage('Matrix — Integration Tests') {
            matrix {
                axes {
                    axis {
                        name 'DATABASE'
                        values 'postgres-14', 'postgres-15', 'mysql-8'
                    }
                    axis {
                        name 'JAVA_VERSION'
                        values '17', '21'
                    }
                }
                excludes {
                    exclude {
                        axis { name 'DATABASE'; values 'mysql-8' }
                        axis { name 'JAVA_VERSION'; values '17' }
                    }
                }
                stages {
                    stage('Integration Test') {
                        steps {
                            echo "Testing ${DATABASE} on Java ${JAVA_VERSION}"
                            sh """
                                docker compose -f docker-compose.${DATABASE}.yml up -d
                                mvn verify -Djava.version=${JAVA_VERSION} -Pintegration
                                docker compose down
                            """
                        }
                    }
                }
            }
        }

        stage('Stash Artifacts') {
            steps {
                // Stash: salva file per usarli in stage successivi (anche su agent diverso)
                stash name: 'app-jar',
                      includes: 'target/*.jar,target/surefire-reports/**',
                      allowEmpty: false
                stash name: 'k8s-manifests',
                      includes: 'k8s/**/*.yaml'
            }
        }

        stage('Security Scan') {
            parallel {
                stage('Trivy — Container') {
                    agent { label 'security-scanner' }
                    steps {
                        sh """
                            trivy image \
                              --severity HIGH,CRITICAL \
                              --exit-code 1 \
                              --format sarif \
                              --output trivy-results.sarif \
                              ${DOCKER_REPO}/${APP_NAME}:${IMAGE_TAG}
                        """
                    }
                }
                stage('OWASP Dependency Check') {
                    steps {
                        container('maven') {
                            sh 'mvn org.owasp:dependency-check-maven:check -DfailBuildOnCVSS=7'
                        }
                        dependencyCheckPublisher pattern: 'target/dependency-check-report.xml'
                    }
                }
            }
        }

        stage('Deploy Staging') {
            when {
                branch 'main'
            }
            steps {
                unstash 'k8s-manifests'
                withKubeConfig([credentialsId: 'k8s-staging-kubeconfig']) {
                    sh """
                        kubectl set image deployment/${APP_NAME} \
                          app=${DOCKER_REPO}/${APP_NAME}:${IMAGE_TAG} \
                          -n staging \
                          --record
                        kubectl rollout status deployment/${APP_NAME} -n staging --timeout=5m
                    """
                }
            }
        }

        stage('Approval — Production') {
            when {
                branch 'main'
                environment name: 'DEPLOY_ENV', value: 'prod'
            }
            steps {
                // Gate manuale con timeout e abort
                timeout(time: 4, unit: 'HOURS') {
                    input(
                        message: "Deploy ${APP_NAME}:${IMAGE_TAG} in PRODUCTION?",
                        ok: 'Approve & Deploy',
                        submitter: 'release-managers,ops-lead',  // solo questi utenti possono approvare
                        parameters: [
                            choice(name: 'DEPLOY_STRATEGY',
                                   choices: ['rolling', 'blue-green', 'canary'],
                                   description: 'Deployment strategy')
                        ]
                    )
                }
            }
        }

        stage('Deploy Production') {
            when {
                branch 'main'
                environment name: 'DEPLOY_ENV', value: 'prod'
            }
            steps {
                withKubeConfig([credentialsId: 'k8s-prod-kubeconfig']) {
                    sh """
                        helm upgrade --install ${APP_NAME} ./helm/${APP_NAME} \
                          --namespace production \
                          --set image.tag=${IMAGE_TAG} \
                          --set image.repository=${DOCKER_REPO}/${APP_NAME} \
                          --atomic \
                          --timeout 10m \
                          --wait
                    """
                }
            }
        }
    }

    // ── Post Conditions ────────────────────────────────────────────────────
    post {
        always {
            // Eseguito SEMPRE (anche in caso di abort)
            cleanWs()                    // pulizia workspace
            publishHTML([
                allowMissing: true,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'target/site',
                reportFiles: 'index.html',
                reportName: 'Test Report'
            ])
        }
        success {
            slackSend(
                channel: '#deployments',
                color: 'good',
                message: "✅ ${APP_NAME}:${IMAGE_TAG} deployed to ${params.DEPLOY_ENV}"
            )
        }
        failure {
            slackSend(
                channel: '#alerts-cicd',
                color: 'danger',
                message: "❌ Build FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}\n${env.BUILD_URL}"
            )
            emailext(
                subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: '${SCRIPT, template="groovy-html.template"}',
                recipientProviders: [[$class: 'DevelopersRecipientProvider'], culprits()]
            )
        }
        unstable {
            slackSend(channel: '#alerts-cicd', color: 'warning',
                message: "⚠️ UNSTABLE: ${env.JOB_NAME} #${env.BUILD_NUMBER}")
        }
        aborted {
            echo 'Pipeline aborted — cleanup'
        }
        fixed {
            // Eseguito solo quando torna GREEN dopo un FAILURE
            slackSend(channel: '#deployments', color: 'good',
                message: "💚 FIXED: ${env.JOB_NAME} is back to green")
        }
        regression {
            // Eseguito solo quando passa da GREEN a FAILURE
            slackSend(channel: '#alerts-cicd', color: 'danger',
                message: "💔 REGRESSION: ${env.JOB_NAME} broke!")
        }
    }
}
```

---

## CPS — Continuation Passing Style

Il **CPS (Continuation Passing Style)** è il meccanismo con cui Jenkins pipeline Groovy è compilato e eseguito. Comprendere il CPS è essenziale per evitare errori oscuri.

### Come funziona

Jenkins trasforma (tramite `groovy-cps` library) il codice Groovy della pipeline in un flusso CPS che:
1. Può essere **sospeso e serializzato su disco** (durability — riprendere dopo restart del controller)
2. Può essere **pausato** (es. `input` step, `sleep`)
3. Ogni variabile e stato è **serializzabile** (implementa `Serializable`)

### Il Problema: Classi/Metodi Non-Serializzabili

```groovy
// ❌ SBAGLIATO: Iterator non è serializzabile in CPS
def list = ['a', 'b', 'c']
def iter = list.iterator()    // CPS non può serializzare Iterator
while(iter.hasNext()) {
    echo iter.next()          // NotSerializableException se pipeline si sospende qui
}

// ✅ CORRETTO: for loop su lista — serializzabile
for (item in list) {
    echo item
}

// ✅ CORRETTO: .each() con Groovy closure semplice
list.each { item ->
    echo item
}
```

### @NonCPS — Uscire dal CPS per Logica Complessa

```groovy
import groovy.transform.Field

// @NonCPS: eseguito fuori dal CPS transformer — usa codice Groovy standard
// Limitazione: non può chiamare step Jenkins (echo, sh, etc.)
// Limitazione: non può essere sospeso — deve completare velocemente
@NonCPS
def parseJsonResponse(String jsonText) {
    def json = new groovy.json.JsonSlurper().parseText(jsonText)
    // Qui puoi usare Iterator, Stream, qualsiasi classe Java/Groovy
    return json.items
        .stream()
        .filter { it.status == 'ACTIVE' }
        .collect { [id: it.id, name: it.name] }
}

// Chiamata dalla pipeline (metodo @NonCPS non può chiamare step Jenkins)
def items = parseJsonResponse(readFile('response.json'))
items.each { item ->
    echo "Processing: ${item.name}"    // echo è uno step Jenkins — OK fuori da @NonCPS
}
```

### Serializzabilità e `@Field`

```groovy
import groovy.transform.Field

// Variabile a livello di script (non locale) — deve essere serializzabile
// o annotata @Field
@Field String globalConfig = loadConfig()

// Oggetti non serializzabili: usare come variabili locali in blocchi @NonCPS
// oppure ricrearli ogni volta che servono
```

---

## Parallel Stages e failFast

```groovy
stage('Parallel Tests') {
    failFast true          // se uno fallisce, cancella gli altri (o: options { parallelsAlwaysFailFast() })
    parallel {
        stage('Test Suite A') {
            steps { sh 'mvn test -pl :module-a' }
        }
        stage('Test Suite B') {
            steps { sh 'mvn test -pl :module-b' }
        }
        stage('Test Suite C') {
            steps { sh 'mvn test -pl :module-c' }
        }
    }
}
```

---

## Matrix — Build su Combinazioni

```groovy
stage('Cross-Platform Build') {
    matrix {
        axes {
            axis {
                name 'PLATFORM'
                values 'linux-amd64', 'linux-arm64', 'windows-2022'
            }
            axis {
                name 'NODE_VERSION'
                values '18', '20', '22'
            }
        }
        // Escludere combinazioni non supportate
        excludes {
            exclude {
                axis { name 'PLATFORM'; values 'windows-2022' }
                axis { name 'NODE_VERSION'; values '18' }
            }
        }
        // Agent per ogni cella della matrice
        agent {
            label "${PLATFORM}"    // label dinamico
        }
        stages {
            stage('Build') {
                steps {
                    sh "nvm use ${NODE_VERSION} && npm ci && npm run build"
                }
            }
            stage('Test') {
                steps {
                    sh "npm test"
                }
                post {
                    always {
                        junit 'test-results/**/*.xml'
                    }
                }
            }
        }
    }
}
```

---

## Script Block — Groovy in Declarative

```groovy
stage('Dynamic Logic') {
    steps {
        script {
            // Dentro script { } puoi usare Groovy completo
            def services = readYaml(file: 'services.yaml').services

            def buildJobs = [:]
            services.each { svc ->
                def svcName = svc.name    // cattura variabile per closure
                buildJobs["Build ${svcName}"] = {
                    stage("Build ${svcName}") {
                        sh "docker build -t ${svcName}:${IMAGE_TAG} ./services/${svcName}"
                    }
                }
            }
            parallel buildJobs          // parallel dinamico da lista YAML
        }
    }
}
```

---

## Stash / Unstash — Condivisione Tra Agent

```groovy
stage('Build') {
    agent { label 'builder' }
    steps {
        sh 'mvn package -DskipTests'
        stash(
            name: 'compiled-artifacts',
            includes: 'target/*.jar,target/classes/**',
            excludes: 'target/test-classes/**',
            allowEmpty: false
        )
    }
}

stage('Test') {
    agent { label 'tester' }     // agent diverso!
    steps {
        unstash 'compiled-artifacts'    // ripristina i file
        sh 'mvn test'
    }
}
```

!!! warning "Stash Size"
    Lo stash viene serializzato sul controller Jenkins. Per artefatti grandi (>100 MB) preferire uno storage esterno (Nexus, S3, Artifactory) per non saturare la memoria del controller.

---

## Retry e Timeout Granulari

```groovy
steps {
    // Retry solo per step specifico (rete flaky, API instabile)
    retry(3) {
        sh 'curl -f https://flaky-api.internal/check'
    }

    // Timeout su singolo step
    timeout(time: 5, unit: 'MINUTES') {
        sh './run-slow-task.sh'
    }

    // Retry con backoff (serve script block)
    script {
        def maxRetries = 5
        def attempt = 0
        def success = false
        while (!success && attempt < maxRetries) {
            try {
                sh 'deploy.sh'
                success = true
            } catch (e) {
                attempt++
                if (attempt >= maxRetries) throw e
                sleep(time: Math.pow(2, attempt).toLong(), unit: 'SECONDS')  // exp backoff
            }
        }
    }
}
```

---

## When — Condizioni di Esecuzione Stage

```groovy
stage('Deploy') {
    when {
        allOf {
            branch 'main'                                     // solo su branch main
            not { changeRequest() }                           // non è una PR
            environment name: 'CI', value: 'true'            // var env impostata
            expression { return currentBuild.result == null || currentBuild.result == 'SUCCESS' }
        }
    }
    steps { ... }
}

// Condizioni disponibili:
// branch 'pattern'           — nome branch
// tag 'pattern'              — build da tag Git
// changeRequest()            — è una Pull Request
// buildingTag()              — build triggdata da tag
// triggeredBy 'TimerTrigger' — build schedulata
// environment name: 'K', value: 'V'
// expression { groovy }      — espressione Groovy custom
// not { ... }                — negazione
// allOf { ... }              — AND logico
// anyOf { ... }              — OR logico
// beforeAgent true           — valuta before che l'agent venga allocato (risparmio risorse)
```

---

## Scripted Pipeline — Pattern Avanzati

```groovy
// Scripted Pipeline per logica veramente complessa
node('master') {
    // catchError: continua pipeline ma marca come FAILURE/UNSTABLE
    catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
        stage('Risky Step') {
            sh './risky-operation.sh'
        }
    }

    // Parallelo dinamico da mappa
    def branches = [:]
    ['eu-west-1', 'us-east-1', 'ap-southeast-1'].each { region ->
        branches["Deploy ${region}"] = {
            node("agent-${region}") {
                sh "kubectl --context=${region} apply -f manifests/"
            }
        }
    }
    parallel branches

    // waitUntil: polling su condizione (es. health check)
    timeout(time: 15, unit: 'MINUTES') {
        waitUntil(initialRecurrencePeriod: 5000) {
            def result = sh(
                script: 'curl -sf https://myapp.prod.internal/health',
                returnStatus: true
            )
            return result == 0
        }
    }
}
```

---

## Riferimenti

- [Jenkins Pipeline Syntax Reference](https://www.jenkins.io/doc/book/pipeline/syntax/)
- [Pipeline Steps Reference](https://www.jenkins.io/doc/pipeline/steps/)
- [Groovy CPS](https://github.com/jenkinsci/workflow-cps-plugin)
- [Pipeline Best Practices](https://www.jenkins.io/doc/book/pipeline/pipeline-best-practices/)
- [Matrix Documentation](https://www.jenkins.io/blog/2019/11/22/welcome-to-the-matrix/)
