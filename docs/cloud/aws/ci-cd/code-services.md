---
title: "CodeBuild, CodeDeploy, CodePipeline e CodeArtifact"
slug: code-services
category: cloud
tags: [aws, codebuild, codedeploy, codepipeline, codeartifact, ci-cd, buildspec, appspec, blue-green, canary, pipeline]
search_keywords: [codebuild, buildspec, codedeploy, appspec, deployment configuration, blue green, canary linear, codepipeline, pipeline stages, manual approval, github actions alternative, codeartifact, npm registry, pip, maven, nuget, swift, upstream repository, codecommit deprecated, github connection, cross account deployment, pipeline v2]
parent: cloud/aws/ci-cd/_index
related: [cloud/aws/ci-cd/cloudformation-cdk, cloud/aws/monitoring/cloudwatch, cloud/aws/security/kms-secrets, cloud/aws/storage/s3]
official_docs: https://docs.aws.amazon.com/codebuild/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# CodeBuild, CodeDeploy, CodePipeline e CodeArtifact

## Panoramica

I servizi AWS Developer Tools formano una suite CI/CD completamente managed: CodeBuild per build e test, CodeDeploy per deployment automatizzato, CodePipeline per orchestrazione della pipeline, e CodeArtifact per gestione degli artefatti software.

!!! note "AWS CodeCommit — Deprecato per nuovi utenti"
    Dal luglio 2024, AWS ha smesso di accettare nuovi utenti su CodeCommit. Gli utenti esistenti possono continuare a usarlo. Per nuovi progetti, AWS raccomanda GitHub, GitLab o Bitbucket integrati con CodeBuild/CodePipeline tramite GitHub App connections.

---

## AWS CodeBuild

### Panoramica

CodeBuild è un servizio di build e test completamente managed. Non richiede server o agenti da gestire. Si paga per minuto di build consumato.

**Caratteristiche principali:**
- Build environment: Ubuntu 22.04, Amazon Linux 2023, Windows Server 2019/2022
- Runtime supportati: Python, Node.js, Java, .NET, Go, PHP, Ruby, Docker
- Integrazione nativa con ECR, S3, Secrets Manager, Parameter Store
- VPC support: accesso a risorse private (RDS, ElastiCache, ECS in VPC privata)
- Concurrency: build parallele illimitate (dipende dal tipo di istanza)
- Cache: S3 (tra build separati) e Local cache (Docker layer, source, custom path)

### buildspec.yml

Il file `buildspec.yml` definisce come CodeBuild esegue il build. Deve trovarsi nella root del repository (o specificare un path alternativo).

```yaml
version: 0.2

env:
  variables:
    ENVIRONMENT: "production"
    AWS_DEFAULT_REGION: "us-east-1"
  parameter-store:
    DATABASE_URL: "/myapp/prod/database-url"
  secrets-manager:
    API_KEY: "prod/myapp/api-key:api-key"
  exported-variables:
    - IMAGE_TAG
    - BUILD_NUMBER

phases:
  install:
    runtime-versions:
      python: 3.12
      nodejs: 20
    commands:
      - echo "Installing dependencies"
      - pip install -r requirements.txt
      - npm ci --prefix frontend
      - pip install pytest coverage bandit safety

  pre_build:
    commands:
      - echo "Running security scans"
      - bandit -r src/ -ll -ii  # SAST scan Python
      - safety check            # Dependency vulnerabilities
      - echo "Logging in to Amazon ECR"
      - aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
      - export IMAGE_TAG=$(git rev-parse --short HEAD)
      - export BUILD_NUMBER=$CODEBUILD_BUILD_NUMBER

  build:
    commands:
      - echo "Running unit tests"
      - python -m pytest tests/unit/ --junitxml=reports/unit-tests.xml --cov=src --cov-report xml:reports/coverage.xml
      - echo "Building Docker image"
      - docker build -t $ECR_REPO_URI:$IMAGE_TAG -t $ECR_REPO_URI:latest .
      - echo "Building frontend"
      - npm run build --prefix frontend

  post_build:
    commands:
      - echo "Pushing Docker image"
      - docker push $ECR_REPO_URI:$IMAGE_TAG
      - docker push $ECR_REPO_URI:latest
      - echo "Writing image definition file for CodeDeploy"
      - printf '[{"name":"app","imageUri":"%s"}]' $ECR_REPO_URI:$IMAGE_TAG > imagedefinitions.json
      - echo "Build completed at $(date)"

reports:
  UnitTestResults:
    files:
      - "reports/unit-tests.xml"
    file-format: JUNITXML
    discard-paths: no
  CoverageReport:
    files:
      - "reports/coverage.xml"
    file-format: COBERTURAXML

artifacts:
  files:
    - imagedefinitions.json
    - appspec.yaml
    - taskdef.json
    - "frontend/build/**/*"
  discard-paths: no
  secondary-artifacts:
    frontend:
      files:
        - "frontend/build/**/*"
      base-directory: "frontend"

cache:
  paths:
    - "/root/.cache/pip/**/*"
    - "/root/.npm/**/*"
    - "/var/lib/docker/**/*"
```

### Creare un CodeBuild Project

```bash
# Creare un progetto CodeBuild
aws codebuild create-project \
  --name "my-app-build" \
  --source '{
    "type": "GITHUB",
    "location": "https://github.com/myorg/my-app",
    "buildspec": "buildspec.yml",
    "gitCloneDepth": 1,
    "reportBuildStatus": true
  }' \
  --artifacts '{
    "type": "S3",
    "location": "my-artifacts-bucket",
    "path": "builds/",
    "name": "my-app",
    "packaging": "ZIP"
  }' \
  --environment '{
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_MEDIUM",
    "privilegedMode": true,
    "environmentVariables": [
      {"name": "ECR_REPO_URI", "value": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app"},
      {"name": "AWS_ACCOUNT_ID", "value": "123456789012"}
    ]
  }' \
  --service-role arn:aws:iam::123456789012:role/CodeBuildServiceRole \
  --vpc-config '{
    "vpcId": "vpc-1234567890",
    "subnets": ["subnet-1234567890"],
    "securityGroupIds": ["sg-1234567890"]
  }' \
  --cache '{
    "type": "S3",
    "location": "my-cache-bucket/codebuild-cache"
  }' \
  --logs-config '{
    "cloudWatchLogs": {
      "status": "ENABLED",
      "groupName": "/aws/codebuild/my-app-build"
    }
  }'

# Avviare un build manualmente
aws codebuild start-build \
  --project-name "my-app-build" \
  --source-version "main" \
  --environment-variables-override Name=ENVIRONMENT,Value=staging,Type=PLAINTEXT

# Monitorare il build
BUILD_ID=$(aws codebuild list-builds-for-project --project-name "my-app-build" --query 'ids[0]' --output text)
aws codebuild batch-get-builds --ids $BUILD_ID \
  --query 'builds[0].{Status:buildStatus,StartTime:startTime,Phases:phases[*].{Phase:phaseType,Status:phaseStatus}}'
```

### Docker-in-Docker (Privileged Mode)

```yaml
# buildspec.yml per build Docker
phases:
  pre_build:
    commands:
      - aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI

  build:
    commands:
      # Multi-stage build per immagini minimali
      - |
        docker build \
          --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
          --build-arg GIT_COMMIT=$(git rev-parse HEAD) \
          --cache-from $ECR_URI:cache \
          --tag $ECR_URI:$IMAGE_TAG \
          --tag $ECR_URI:latest \
          .
      # Scan dell'immagine con Trivy
      - trivy image --exit-code 1 --severity CRITICAL $ECR_URI:$IMAGE_TAG

  post_build:
    commands:
      - docker push $ECR_URI:$IMAGE_TAG
      - docker push $ECR_URI:latest
      # Salva il cache layer
      - docker push $ECR_URI:cache || true
```

---

## AWS CodeDeploy

### Panoramica

CodeDeploy automatizza il deployment di applicazioni su EC2, ECS, Lambda e server on-premises. Supporta rolling updates, blue/green e canary deployments con rollback automatico.

### AppSpec File

L'AppSpec file (appspec.yml o appspec.json) definisce il comportamento del deployment.

**AppSpec per ECS:**
```yaml
version: 0.0
Resources:
  - TargetService:
      Type: AWS::ECS::Service
      Properties:
        TaskDefinition: <TASK_DEFINITION>
        LoadBalancerInfo:
          ContainerName: "app"
          ContainerPort: 8080
        PlatformVersion: "LATEST"
Hooks:
  - BeforeInstall: "arn:aws:lambda:us-east-1:123456789012:function:pre-deploy-check"
  - AfterInstall: "arn:aws:lambda:us-east-1:123456789012:function:smoke-test"
  - AfterAllowTestTraffic: "arn:aws:lambda:us-east-1:123456789012:function:integration-test"
  - BeforeAllowTraffic: "arn:aws:lambda:us-east-1:123456789012:function:final-check"
  - AfterAllowTraffic: "arn:aws:lambda:us-east-1:123456789012:function:cleanup"
```

**AppSpec per Lambda (canary):**
```yaml
version: 0.0
Resources:
  - MyLambdaFunction:
      Type: AWS::Lambda::Function
      Properties:
        Name: !Ref MyLambdaFunction
        Alias: !Ref LambdaFunctionAlias
        CurrentVersion: !Ref CurrentVersion
        TargetVersion: !Ref NewVersion
Hooks:
  - BeforeAllowTraffic: "arn:aws:lambda:us-east-1:123456789012:function:pre-traffic-hook"
  - AfterAllowTraffic: "arn:aws:lambda:us-east-1:123456789012:function:post-traffic-hook"
```

**AppSpec per EC2:**
```yaml
version: 0.0
os: linux
files:
  - source: /
    destination: /var/www/html
permissions:
  - object: /var/www/html
    owner: www-data
    group: www-data
    mode: "755"
    type:
      - directory
      - file
hooks:
  BeforeInstall:
    - location: scripts/stop-server.sh
      timeout: 60
      runas: root
  AfterInstall:
    - location: scripts/configure.sh
      timeout: 120
  ApplicationStart:
    - location: scripts/start-server.sh
      timeout: 60
  ValidateService:
    - location: scripts/validate.sh
      timeout: 30
```

### Deployment Configurations

**Per EC2:**
- `CodeDeployDefault.AllAtOnce`: aggiorna tutte le istanze contemporaneamente (rischio alto, downtime)
- `CodeDeployDefault.HalfAtATime`: aggiorna metà per volta
- `CodeDeployDefault.OneAtATime`: aggiorna una istanza per volta (più sicuro, più lento)
- Custom: percentuale configurabile

**Per Lambda:**
- `Canary10Percent5Minutes`: 10% traffico per 5 minuti, poi 100%
- `Canary10Percent30Minutes`: 10% per 30 minuti, poi 100%
- `Linear10PercentEvery1Minute`: 10% ogni minuto fino a 100%
- `Linear10PercentEvery10Minutes`: 10% ogni 10 minuti
- `AllAtOnce`: deploy immediato

**Per ECS:**
- `CodeDeployDefault.ECSAllAtOnce`: blue/green immediato
- `ECSCanary10Percent5Minutes`: canary ECS
- `ECSLinear10PercentEvery1Minute`: linear ECS

```bash
# Creare un'applicazione CodeDeploy
aws deploy create-application \
  --application-name "my-ecs-app" \
  --compute-platform ECS

# Creare un deployment group per ECS
aws deploy create-deployment-group \
  --application-name "my-ecs-app" \
  --deployment-group-name "production" \
  --deployment-config-name "CodeDeployDefault.ECSAllAtOnce" \
  --service-role-arn arn:aws:iam::123456789012:role/CodeDeployRole \
  --ecs-services '[{
    "serviceName": "my-ecs-service",
    "clusterName": "production-cluster"
  }]' \
  --load-balancer-info '{
    "targetGroupPairInfoList": [{
      "targetGroups": [
        {"name": "my-tg-blue"},
        {"name": "my-tg-green"}
      ],
      "prodTrafficRoute": {
        "listenerArns": ["arn:aws:elasticloadbalancing:..."]
      },
      "testTrafficRoute": {
        "listenerArns": ["arn:aws:elasticloadbalancing:...test"]
      }
    }]
  }' \
  --blue-green-deployment-configuration '{
    "terminateBlueInstancesOnDeploymentSuccess": {
      "action": "TERMINATE",
      "terminationWaitTimeInMinutes": 5
    },
    "deploymentReadyOption": {
      "actionOnTimeout": "CONTINUE_DEPLOYMENT",
      "waitTimeInMinutes": 0
    }
  }' \
  --auto-rollback-configuration '{
    "enabled": true,
    "events": ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }' \
  --alarm-configuration '{
    "enabled": true,
    "alarms": [{"name": "HighErrorRate"}],
    "ignorePollAlarmFailure": false
  }'

# Creare un deployment
aws deploy create-deployment \
  --application-name "my-ecs-app" \
  --deployment-group-name "production" \
  --revision '{
    "revisionType": "S3",
    "s3Location": {
      "bucket": "my-artifacts-bucket",
      "key": "appspec.yaml",
      "bundleType": "YAML"
    }
  }' \
  --description "Deploy version 1.2.3"

# Rollback manuale
aws deploy stop-deployment \
  --deployment-id d-ABCDEFG12 \
  --auto-rollback-enabled
```

---

## AWS CodePipeline

### Panoramica

CodePipeline è il servizio di orchestrazione CI/CD. Collega automaticamente Source → Build → Test → Deploy in una pipeline multi-stage.

**Versioni:**
- **V1:** trigger limitati (branch push), no variabili avanzate
- **V2:** trigger avanzati (pull request, tag, branch specifici), variabili, execution modes

### Pipeline Completa — ECS Blue/Green

```bash
# Creare una pipeline CodePipeline v2
aws codepipeline create-pipeline \
  --cli-input-json file://pipeline.json
```

```json
{
  "pipeline": {
    "name": "my-ecs-pipeline",
    "roleArn": "arn:aws:iam::123456789012:role/CodePipelineRole",
    "artifactStore": {
      "type": "S3",
      "location": "my-pipeline-artifacts",
      "encryptionKey": {
        "id": "alias/codepipeline-key",
        "type": "KMS"
      }
    },
    "stages": [
      {
        "name": "Source",
        "actions": [{
          "name": "GitHub",
          "actionTypeId": {
            "category": "Source",
            "owner": "AWS",
            "provider": "CodeStarSourceConnection",
            "version": "1"
          },
          "configuration": {
            "ConnectionArn": "arn:aws:codeconnections:us-east-1:123456789012:connection/abc123",
            "FullRepositoryId": "myorg/my-app",
            "BranchName": "main",
            "OutputArtifactFormat": "CODE_ZIP",
            "DetectChanges": "true"
          },
          "outputArtifacts": [{"name": "SourceArtifact"}],
          "runOrder": 1
        }]
      },
      {
        "name": "Build",
        "actions": [{
          "name": "BuildAndTest",
          "actionTypeId": {
            "category": "Build",
            "owner": "AWS",
            "provider": "CodeBuild",
            "version": "1"
          },
          "configuration": {
            "ProjectName": "my-app-build",
            "PrimarySource": "SourceArtifact"
          },
          "inputArtifacts": [{"name": "SourceArtifact"}],
          "outputArtifacts": [{"name": "BuildArtifact"}],
          "runOrder": 1
        }]
      },
      {
        "name": "Staging",
        "actions": [{
          "name": "DeployToStaging",
          "actionTypeId": {
            "category": "Deploy",
            "owner": "AWS",
            "provider": "CodeDeployToECS",
            "version": "1"
          },
          "configuration": {
            "ApplicationName": "my-ecs-app",
            "DeploymentGroupName": "staging",
            "TaskDefinitionTemplateArtifact": "BuildArtifact",
            "AppSpecTemplateArtifact": "BuildArtifact",
            "TaskDefinitionTemplatePath": "taskdef.json",
            "AppSpecTemplatePath": "appspec.yaml",
            "Image1ArtifactName": "BuildArtifact",
            "Image1ContainerName": "IMAGE1_NAME"
          },
          "inputArtifacts": [{"name": "BuildArtifact"}],
          "runOrder": 1
        }]
      },
      {
        "name": "Approval",
        "actions": [{
          "name": "ManualApproval",
          "actionTypeId": {
            "category": "Approval",
            "owner": "AWS",
            "provider": "Manual",
            "version": "1"
          },
          "configuration": {
            "NotificationArn": "arn:aws:sns:us-east-1:123456789012:pipeline-approval",
            "CustomData": "Please review the staging deployment before approving production.",
            "ExternalEntityLink": "https://staging.myapp.com"
          },
          "runOrder": 1
        }]
      },
      {
        "name": "Production",
        "actions": [{
          "name": "DeployToProduction",
          "actionTypeId": {
            "category": "Deploy",
            "owner": "AWS",
            "provider": "CodeDeployToECS",
            "version": "1"
          },
          "configuration": {
            "ApplicationName": "my-ecs-app",
            "DeploymentGroupName": "production",
            "TaskDefinitionTemplateArtifact": "BuildArtifact",
            "AppSpecTemplateArtifact": "BuildArtifact"
          },
          "inputArtifacts": [{"name": "BuildArtifact"}],
          "runOrder": 1
        }]
      }
    ],
    "version": 1,
    "pipelineType": "V2",
    "triggers": [{
      "providerType": "CodeStarSourceConnection",
      "gitConfiguration": {
        "sourceActionName": "GitHub",
        "push": [{
          "branches": {"includes": ["main"]},
          "tags": {"excludes": ["*"]}
        }]
      }
    }]
  }
}
```

### Cross-Account Deployment

```bash
# Per deploy cross-account, configurare il KMS key e il bucket S3 degli artefatti
# per permettere accesso all'account di destinazione.

# Nel bucket S3 artefatti — bucket policy
aws s3api put-bucket-policy \
  --bucket my-pipeline-artifacts \
  --policy '{
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::999888777666:role/CrossAccountDeployRole"},
      "Action": ["s3:Get*", "s3:Put*", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-pipeline-artifacts",
        "arn:aws:s3:::my-pipeline-artifacts/*"
      ]
    }]
  }'

# Nel KMS key — key policy (per cifrare/decifrare artefatti)
# Aggiungere l'account di destinazione come "Allow Key Usage"
```

---

## AWS CodeArtifact

### Panoramica

CodeArtifact è un repository managed per artefatti software: npm, pip, Maven, NuGet, Swift, Gradle, generic.

**Vantaggi rispetto a registri pubblici:**
- Proxy e cache verso registri pubblici (PyPI, npm, Maven Central)
- Scansione di sicurezza opzionale
- Controllo degli accessi tramite IAM
- Integrazione con CodeBuild per pull automatico

### Struttura

```
Domain (my-org)
├── Repository (production)
│   ├── Upstream: PyPI, npm, Maven Central (proxy/cache)
│   └── Packages interni: my-lib-1.0.0.tar.gz
└── Repository (development)
    └── Upstream: production (ereditare pacchetti prod)
```

```bash
# Creare un domain
aws codeartifact create-domain \
  --domain my-org \
  --encryption-key alias/codeartifact-key

# Creare un repository con upstream PyPI
aws codeartifact create-repository \
  --domain my-org \
  --repository production \
  --description "Production packages" \
  --upstreams '[{"repositoryName": "pypi-store"}]'

# Creare il repository upstream per PyPI
aws codeartifact create-repository \
  --domain my-org \
  --repository pypi-store \
  --external-connections public:pypi

# Ottenere il token di autenticazione (scade dopo 12h)
TOKEN=$(aws codeartifact get-authorization-token \
  --domain my-org \
  --domain-owner 123456789012 \
  --query authorizationToken \
  --output text)

# Configurare pip per usare CodeArtifact
aws codeartifact login --tool pip --domain my-org --repository production

# Pubblicare un pacchetto Python
pip install twine
twine upload \
  --repository-url https://my-org-123456789012.d.codeartifact.us-east-1.amazonaws.com/pypi/production/ \
  --username aws \
  --password $TOKEN \
  dist/*

# In buildspec.yml — login automatico
# phases:
#   install:
#     commands:
#       - aws codeartifact login --tool pip --domain my-org --repository production
#       - pip install -r requirements.txt  # usa il registry CodeArtifact automaticamente
```

---

## Esempio Completo: Pipeline SAM/Lambda

```yaml
# Pipeline per applicazione serverless (SAM)
# buildspec.yml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - pip install aws-sam-cli pytest

  pre_build:
    commands:
      - sam validate
      - python -m pytest tests/ --junitxml=reports/test-results.xml

  build:
    commands:
      - sam build --use-container
      - sam package \
          --s3-bucket $SAM_ARTIFACTS_BUCKET \
          --output-template-file packaged-template.yaml \
          --region $AWS_DEFAULT_REGION

  post_build:
    commands:
      - echo Build complete

artifacts:
  files:
    - packaged-template.yaml
    - samconfig.toml

reports:
  TestReport:
    files:
      - reports/test-results.xml
    file-format: JUNITXML
```

```bash
# Pipeline di deployment con CloudFormation (SAM deploy)
# Stage di deploy nella pipeline — usa CloudFormation action
# "ActionTypeId": {"category": "Deploy", "provider": "CloudFormation"}
# "Configuration":
#   "ActionMode": "CREATE_UPDATE"
#   "StackName": "my-serverless-app"
#   "TemplatePath": "BuildArtifact::packaged-template.yaml"
#   "Capabilities": "CAPABILITY_IAM,CAPABILITY_AUTO_EXPAND"
#   "RoleArn": "arn:aws:iam::123456789012:role/CloudFormationRole"
```

---

## Best Practices

### CodeBuild

1. **Usare ECR Public o cache Docker** per velocizzare pull delle immagini base
2. **Local cache** per dipendenze (pip, npm, Maven) — riduce i tempi di build del 50-70%
3. **Scan di sicurezza nel build** (Bandit, Safety, Trivy) — fail the build su CRITICAL
4. **Report** di test JUnit e coverage — feedback immediato nel build
5. **VPC** per accedere a risorse private, ma aggiunge latenza (NAT Gateway necessario per Internet)

### CodeDeploy

1. **Alarm-based rollback** sempre attivo — monitora error rate post-deploy
2. **Hooks di test** nei lifecycle (AfterInstall, AfterAllowTraffic) per validare il deploy
3. **Blue/Green su ECS** per zero-downtime garantito
4. **Canary deployment su Lambda** per ridurre il rischio di nuove versioni

### CodePipeline

1. **Manual Approval per production** — sempre richiedere approvazione umana
2. **Notifiche SNS** per approval e fallimenti della pipeline
3. **Artifact encryption** con KMS CMK
4. **Cross-account con least-privilege** — il ruolo cross-account deve avere solo i permessi di deploy

---

## Troubleshooting

### CodeBuild: Build Fallisce con "Cannot connect to Docker"

Il container CodeBuild deve avere `privilegedMode: true` per usare Docker-in-Docker.

```bash
aws codebuild update-project \
  --name my-app-build \
  --environment privilegedMode=true
```

### CodePipeline: Stage Bloccato

```bash
# Verificare lo stato della pipeline
aws codepipeline get-pipeline-state \
  --name "my-ecs-pipeline" \
  --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}'

# Sbloccare uno stage (skip dell'azione corrente)
aws codepipeline put-action-revision \
  --pipeline-name "my-ecs-pipeline" \
  --stage-name "Approval" \
  --action-name "ManualApproval" \
  --action-revision '{
    "revisionId": "manual-skip",
    "revisionChangeId": "skip-$(date +%s)",
    "created": "2024-01-15T10:00:00Z"
  }'
```

### CodeDeploy: Rollback Non Avviene

1. Verificare che l'alarm configuration sia corretta (alarm name corrisponde esattamente)
2. Verificare che CodeDeploy abbia permesso CloudWatch per leggere gli allarmi
3. Controllare i log del deployment nella console CodeDeploy

---

## Relazioni

??? info "CloudFormation e CDK"
    CodePipeline si integra nativamente con CloudFormation per deploy di infrastruttura IaC.

    **Approfondimento completo →** [CloudFormation e CDK](cloudformation-cdk.md)

??? info "CloudWatch — Monitoring Post-Deploy"
    CloudWatch alarms si integrano con CodeDeploy per rollback automatico.

    **Approfondimento completo →** [CloudWatch](../monitoring/cloudwatch.md)

??? info "ECR — Image Registry"
    CodeBuild pusha le immagini Docker su ECR. CodeDeploy fa pull da ECR per i deploy ECS.

---

## Riferimenti

- [CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [CodeBuild buildspec reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
- [CodeDeploy Documentation](https://docs.aws.amazon.com/codedeploy/)
- [CodePipeline Documentation](https://docs.aws.amazon.com/codepipeline/)
- [CodeArtifact Documentation](https://docs.aws.amazon.com/codeartifact/)
- [CodePipeline V2 Features](https://docs.aws.amazon.com/codepipeline/latest/userguide/pipeline-types.html)
- [CodeDeploy AppSpec Reference](https://docs.aws.amazon.com/codedeploy/latest/userguide/reference-appspec-file.html)
- [CodeBuild Pricing](https://aws.amazon.com/codebuild/pricing/)
