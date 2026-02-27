---
title: "Jenkins Shared Libraries"
slug: jenkins-shared-libraries
category: ci-cd
tags: [jenkins, shared-libraries, groovy, dsl, pipeline-template, reusable-pipeline, global-library]
search_keywords: [Jenkins Shared Libraries, Global Shared Library, Jenkins vars, Jenkins src, Groovy DSL Jenkins, custom pipeline steps, Jenkins library versioning, implicit loading library, explicit loading library, JenkinsPipelineUnit, pipeline testing Jenkins, Groovy class Jenkins, @Library annotation, loadLibrary, pipeline template, vars groovy call, resources Jenkins library, Jenkins DSL extension]
parent: ci-cd/jenkins/_index
related: [ci-cd/jenkins/pipeline-fundamentals, ci-cd/jenkins/enterprise-patterns]
official_docs: https://www.jenkins.io/doc/book/pipeline/shared-libraries/
status: complete
difficulty: advanced
last_updated: 2026-02-27
---

# Jenkins Shared Libraries

Le **Shared Libraries** sono il meccanismo per condividere codice Groovy tra pipeline Jenkins — equivalente a un SDK interno per le tue pipeline. In ambienti enterprise è lo standard per standardizzare, governare e riutilizzare pattern CI/CD.

## Struttura della Shared Library

```
my-jenkins-library/
├── vars/                         # ← Custom DSL steps (entry point principale)
│   ├── buildDocker.groovy        # chiamabile come: buildDocker(...)
│   ├── deployHelm.groovy         # chiamabile come: deployHelm(...)
│   ├── notifySlack.groovy        # chiamabile come: notifySlack(...)
│   ├── standardPipeline.groovy   # pipeline template completa
│   └── buildDocker.txt           # (opzionale) documentazione del custom step
│
├── src/                          # ← Classi Groovy riutilizzabili (utility, helper)
│   └── com/
│       └── company/
│           └── jenkins/
│               ├── Docker.groovy
│               ├── Kubernetes.groovy
│               ├── Slack.groovy
│               └── Utils.groovy
│
└── resources/                    # ← File statici (template, script, config)
    ├── com/company/jenkins/
    │   ├── Dockerfile.template
    │   ├── sonar-project.properties
    │   └── helm-values-template.yaml
    └── scripts/
        └── health-check.sh
```

**Regola fondamentale:**
- `vars/` → **step** chiamabili direttamente nella pipeline (CPS-safe, entrypoint)
- `src/` → **classi Groovy** per logica complessa (istanziate dentro `script { }` block)
- `resources/` → **file statici** accessibili con `libraryResource()`

---

## Configurare la Shared Library in Jenkins

### Via JCasC (Production Setup)

```yaml
# jenkins.yaml (JCasC)
unclassified:
  globalLibraries:
    libraries:
      - name: "company-pipeline-lib"
        defaultVersion: "main"
        implicit: false               # false = deve essere dichiarata nel Jenkinsfile
                                      # true  = automaticamente disponibile in tutte le pipeline
        allowVersionOverride: true    # permette @Library('name@branch') nel Jenkinsfile
        includeInChangesets: false    # non triggera build su cambiamento library
        retriever:
          modernSCM:
            scm:
              git:
                remote: "https://git.company.com/platform/jenkins-library.git"
                credentialsId: "git-library-credentials"
                traits:
                  - gitBranchDiscovery: {}
                  - gitTagDiscovery: {}
```

### Caricare la Library nel Jenkinsfile

```groovy
// Versione specifica (produzione — mai usare 'main' in prod)
@Library('company-pipeline-lib@v2.3.1') _

// Branch (sviluppo e testing)
@Library('company-pipeline-lib@feature/new-step') _

// Multiple libraries
@Library(['company-pipeline-lib@v2.3.1', 'security-lib@stable']) _

// Implicit (se configured come implicit=true nel controller)
// Nessuna dichiarazione necessaria nel Jenkinsfile

// Caricamento dinamico (a runtime, durante l'esecuzione pipeline)
library('company-pipeline-lib@main').com.company.jenkins.Docker
```

---

## vars/ — Custom DSL Steps

Ogni file `vars/nomeStep.groovy` espone un metodo `call()` che diventa lo step:

### Step Semplice

```groovy
// vars/notifySlack.groovy
/**
 * Invia notifica Slack con stato della build.
 *
 * @param args Map con:
 *   - channel: String (default '#deployments')
 *   - message: String (required)
 *   - status: String ('SUCCESS'|'FAILURE'|'UNSTABLE') (default: currentBuild.result)
 */
def call(Map args = [:]) {
    def channel  = args.get('channel',  '#deployments')
    def message  = args.get('message',  '')
    def status   = args.get('status',   currentBuild.result ?: 'SUCCESS')

    def colorMap = [
        SUCCESS: '#36a64f',
        FAILURE: '#ff0000',
        UNSTABLE: '#ffa500'
    ]

    def color = colorMap.get(status, '#808080')
    def fullMsg = "${message}\n*Build:* ${env.JOB_NAME} #${env.BUILD_NUMBER} | ${env.BUILD_URL}"

    slackSend(channel: channel, color: color, message: fullMsg)
}
```

```groovy
// Uso nel Jenkinsfile
@Library('company-pipeline-lib@v2.3.1') _

pipeline {
    agent any
    post {
        success {
            notifySlack(message: "✅ Deploy completato", channel: '#ops')
        }
        failure {
            notifySlack(message: "❌ Build fallita", status: 'FAILURE')
        }
    }
}
```

---

### Step Complesso — Docker Build & Push

```groovy
// vars/buildDocker.groovy
def call(Map config) {
    // Validazione parametri obbligatori
    if (!config.image) error("buildDocker: 'image' is required")

    def image        = config.image
    def tag          = config.tag ?: env.GIT_COMMIT?.take(8) ?: 'latest'
    def dockerfile   = config.dockerfile ?: 'Dockerfile'
    def context      = config.context ?: '.'
    def buildArgs    = config.buildArgs ?: [:]
    def registry     = config.registry ?: env.DOCKER_REGISTRY ?: 'registry.company.com'
    def cacheFrom    = config.cacheFrom ?: true
    def platforms    = config.platforms ?: ['linux/amd64']
    def push         = config.push != false    // default true

    def fullImage = "${registry}/${image}:${tag}"
    def latestImage = "${registry}/${image}:latest"

    echo "Building ${fullImage} (platforms: ${platforms.join(',')})"

    // Costruisci lista --build-arg
    def buildArgStr = buildArgs.collect { k, v -> "--build-arg ${k}=${v}" }.join(' ')

    // Cache from previous image
    def cacheStr = cacheFrom ? "--cache-from=${registry}/${image}:cache" : ''

    withCredentials([usernamePassword(
        credentialsId: 'docker-registry-credentials',
        usernameVariable: 'DOCKER_USER',
        passwordVariable: 'DOCKER_PASS'
    )]) {
        sh """
            echo \$DOCKER_PASS | docker login ${registry} -u \$DOCKER_USER --password-stdin

            docker buildx build \
              --platform ${platforms.join(',')} \
              --file ${dockerfile} \
              ${buildArgStr} \
              ${cacheStr} \
              --tag ${fullImage} \
              ${push ? "--tag ${latestImage} --push" : '--load'} \
              ${context}
        """
    }

    // Restituisce il nome dell'immagine per uso successivo
    return fullImage
}
```

---

### Pipeline Template — Il Pattern Più Potente

```groovy
// vars/standardPipeline.groovy
// Pipeline template completa — i team chiamano solo questa funzione

def call(Map config, Closure body = null) {
    // Defaults
    config.agentLabel     = config.agentLabel ?: 'kubernetes'
    config.timeoutMinutes = config.timeoutMinutes ?: 60
    config.slackChannel   = config.slackChannel ?: '#deployments'
    config.sonarEnabled   = config.sonarEnabled != false  // default true
    config.dockerEnabled  = config.dockerEnabled != false
    config.deployEnvs     = config.deployEnvs ?: ['dev', 'staging']

    pipeline {
        agent {
            kubernetes {
                inheritFrom config.agentLabel
                yaml libraryResource('pod-templates/standard.yaml')
            }
        }

        options {
            timeout(time: config.timeoutMinutes, unit: 'MINUTES')
            buildDiscarder(logRotator(numToKeepStr: '30'))
            disableConcurrentBuilds(abortPrevious: true)
            timestamps()
            ansiColor('xterm')
        }

        environment {
            APP_NAME  = config.appName
            IMAGE_TAG = "${env.GIT_COMMIT?.take(8) ?: 'latest'}"
        }

        stages {
            stage('Checkout') {
                steps {
                    checkout scm
                }
            }

            stage('Build & Test') {
                steps {
                    container('build') {
                        sh config.buildCommand ?: 'make build test'
                    }
                }
                post {
                    always {
                        if (config.junitPattern) {
                            junit(testResults: config.junitPattern, allowEmptyResults: true)
                        }
                    }
                }
            }

            stage('Quality Gate') {
                when { expression { config.sonarEnabled } }
                steps {
                    withSonarQubeEnv('company-sonarqube') {
                        sh config.sonarCommand ?: 'mvn sonar:sonar'
                    }
                    timeout(time: 5, unit: 'MINUTES') {
                        waitForQualityGate abortPipeline: true
                    }
                }
            }

            stage('Container Build') {
                when { expression { config.dockerEnabled } }
                steps {
                    script {
                        buildDocker(
                            image: config.appName,
                            tag: env.IMAGE_TAG,
                            registry: config.registry ?: env.DOCKER_REGISTRY
                        )
                    }
                }
            }

            // Hook per step custom del team
            stage('Custom Steps') {
                when { expression { body != null } }
                steps {
                    script {
                        body.call()    // esegue la closure passata dal team
                    }
                }
            }

            stage('Deploy') {
                when { branch 'main' }
                steps {
                    script {
                        config.deployEnvs.each { env_name ->
                            deployHelm(
                                chart: config.helmChart ?: config.appName,
                                namespace: env_name,
                                imageTag: env.IMAGE_TAG,
                                values: "helm/values-${env_name}.yaml"
                            )
                        }
                    }
                }
            }
        }

        post {
            success {
                notifySlack(
                    channel: config.slackChannel,
                    message: "✅ ${config.appName} deployed successfully",
                    status: 'SUCCESS'
                )
            }
            failure {
                notifySlack(
                    channel: config.slackChannel,
                    message: "❌ ${config.appName} pipeline FAILED",
                    status: 'FAILURE'
                )
            }
            always { cleanWs() }
        }
    }
}
```

**Uso del template da parte di un team:**

```groovy
// Jenkinsfile di un microservizio — 8 righe invece di 200+
@Library('company-pipeline-lib@v2.3.1') _

standardPipeline(
    appName: 'payment-service',
    buildCommand: 'gradle build test',
    junitPattern: 'build/test-results/**/*.xml',
    sonarCommand: 'gradle sonarqube',
    helmChart: 'payment-service',
    deployEnvs: ['dev', 'staging'],
    slackChannel: '#team-payments'
) {
    // Step custom del team (hook opzionale)
    sh './scripts/db-migration.sh'
    sh './scripts/cache-warmup.sh'
}
```

---

## src/ — Classi Groovy

```groovy
// src/com/company/jenkins/Docker.groovy
package com.company.jenkins

import groovy.transform.Field

class Docker implements Serializable {
    private final def script        // riferimento all'oggetto pipeline (steps)
    private final String registry
    private final String credentialsId

    Docker(script, String registry, String credentialsId = 'docker-registry-credentials') {
        this.script = script
        this.registry = registry
        this.credentialsId = credentialsId
    }

    String buildAndPush(String imageName, String tag, String dockerfile = 'Dockerfile', String context = '.') {
        def fullName = "${registry}/${imageName}:${tag}"
        script.withCredentials([
            script.usernamePassword(
                credentialsId: this.credentialsId,
                usernameVariable: 'DOCKER_USER',
                passwordVariable: 'DOCKER_PASS'
            )
        ]) {
            script.sh """
                echo \$DOCKER_PASS | docker login ${registry} -u \$DOCKER_USER --password-stdin
                docker build -f ${dockerfile} -t ${fullName} ${context}
                docker push ${fullName}
            """
        }
        return fullName
    }

    void scan(String imageName, String tag, int severityThreshold = 7) {
        def fullName = "${registry}/${imageName}:${tag}"
        script.sh """
            trivy image \
              --severity HIGH,CRITICAL \
              --exit-code ${severityThreshold >= 7 ? 1 : 0} \
              --format json \
              --output trivy-report.json \
              ${fullName}
        """
        script.archiveArtifacts 'trivy-report.json'
    }
}
```

```groovy
// Uso nel Jenkinsfile (dentro script block)
@Library('company-pipeline-lib@v2.3.1') _
import com.company.jenkins.Docker

pipeline {
    agent any
    stages {
        stage('Build & Scan') {
            steps {
                script {
                    def docker = new Docker(
                        this,                                        // riferimento pipeline
                        'registry.company.com',
                        'docker-registry-credentials'
                    )
                    def imageUrl = docker.buildAndPush('myapp', env.GIT_COMMIT.take(8))
                    docker.scan('myapp', env.GIT_COMMIT.take(8))
                }
            }
        }
    }
}
```

---

## resources/ — File Statici

```groovy
// vars/someStep.groovy
def call(String templateName) {
    // Carica file da resources/
    def template = libraryResource("com/company/jenkins/${templateName}")

    // Scriviamo su disco per usarlo
    writeFile(file: 'generated-config.yaml', text: template)
    sh 'kubectl apply -f generated-config.yaml'
}
```

```yaml
# resources/com/company/jenkins/pod-template-standard.yaml
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  containers:
  - name: build
    image: eclipse-temurin:21-jdk
    command: [sleep, infinity]
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "4Gi"
        cpu: "2000m"
```

---

## Versioning della Library

```
Strategy consigliata per una Shared Library enterprise:

  main          → stato corrente (sviluppo attivo)
  v1            → branch di manutenzione versione 1.x
  v2            → branch di manutenzione versione 2.x
  v2.3.1        → tag SemVer per versione precisa (usare in Jenkinsfile produzione)
  feature/XXX   → feature branch (testing in sandbox)
```

```groovy
// Jenkinsfile sviluppo (team può testare la library in evoluzione)
@Library('company-pipeline-lib@feature/new-deploy-step') _

// Jenkinsfile produzione (versione FISSA — mandatory per traceability)
@Library('company-pipeline-lib@v2.3.1') _
```

**Processo di release della library:**
1. Sviluppo su `feature/XXX`
2. PR review da Platform team
3. Merge su `main`
4. Test automatici in sandbox Jenkins
5. Tag SemVer: `git tag v2.4.0 && git push --tags`
6. Comunicazione changelog ai team

---

## Testing con JenkinsPipelineUnit

**JenkinsPipelineUnit** è il framework di unit testing per Groovy pipeline Jenkins:

```groovy
// test/vars/NotifySlackTest.groovy
import com.lesfurets.jenkins.unit.BasePipelineTest
import org.junit.Before
import org.junit.Test
import static org.assertj.core.api.Assertions.*

class NotifySlackTest extends BasePipelineTest {
    def notifySlack

    @Before
    void setUp() {
        super.setUp()
        // Mock step Jenkins
        helper.registerAllowedMethod('slackSend', [Map]) { Map args ->
            // Registra la chiamata per asserzioni
        }
        notifySlack = loadScript('vars/notifySlack.groovy')
    }

    @Test
    void 'should send with default channel on success'() {
        binding.setVariable('env', [JOB_NAME: 'my-job', BUILD_NUMBER: '42', BUILD_URL: 'http://...'])
        binding.setVariable('currentBuild', [result: 'SUCCESS'])

        notifySlack(message: 'Deploy ok')

        assertThat(helper.callStack)
            .filteredOn { it.methodName == 'slackSend' }
            .hasSize(1)
            .extracting { it.args[0] }
            .extracting('channel')
            .containsExactly('#deployments')
    }

    @Test
    void 'should use FAILURE color on failure'() {
        binding.setVariable('currentBuild', [result: 'FAILURE'])

        notifySlack(message: 'Build failed', status: 'FAILURE')

        def slackCall = helper.callStack.find { it.methodName == 'slackSend' }
        assertThat(slackCall.args[0].color).isEqualTo('#ff0000')
    }
}
```

```groovy
// build.gradle (Shared Library project)
dependencies {
    testImplementation 'com.lesfurets:jenkins-pipeline-unit:1.21'
    testImplementation 'org.junit.jupiter:junit-jupiter-api:5.10.0'
    testImplementation 'org.assertj:assertj-core:3.24.2'
}

test {
    useJUnitPlatform()
}
```

---

## Best Practices Shared Libraries

| Pratica | Motivazione |
|---------|------------|
| **Versioning semantico su tag Git** | Jenkinsfile in produzione puntano a versione precisa, non a `main` |
| **Input validation all'inizio del `call()`** | Fail fast con errore chiaro invece di failure oscura a metà pipeline |
| **Documenta ogni step con `.txt` companion** | Appare in Pipeline Syntax helper UI di Jenkins |
| **Test con JenkinsPipelineUnit** | Rileva regressioni prima del deploy in produzione |
| **Non fare `@Library` implicita per default** | Controllo esplicito: i team scelgono quale versione usare |
| **Usare `@Field` per costanti di modulo** | Evita ripetizioni nel codice della library |
| **Non esporre dettagli infrastruttura in `vars/`** | L'astrazione nasconde dove il deploy avviene — i team dichiarano l'intenzione |
| **Platform team review per ogni merge** | La library è infrastruttura condivisa — ogni cambiamento impatta tutti i team |

---

## Riferimenti

- [Jenkins Shared Libraries Documentation](https://www.jenkins.io/doc/book/pipeline/shared-libraries/)
- [JenkinsPipelineUnit](https://github.com/jenkinsci/JenkinsPipelineUnit)
- [Pipeline Library Examples](https://github.com/jenkinsci/pipeline-library-demo)
- [Groovy CPS and Shared Libraries](https://www.jenkins.io/doc/book/pipeline/shared-libraries/#defining-global-variables)
