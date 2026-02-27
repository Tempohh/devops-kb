---
title: "AWS CI/CD"
slug: ci-cd
category: cloud
tags: [aws, ci-cd, codebuild, codedeploy, codepipeline, codeartifact, cloudformation, cdk, sam, devops]
search_keywords: [aws ci-cd, codebuild, codedeploy, codepipeline, codeartifact, cloudformation, cdk, cloud development kit, sam, serverless application model, continuous integration, continuous deployment, devops, blue green deployment, canary, infrastructure as code, iac]
parent: cloud/aws/_index
related: [cloud/aws/ci-cd/code-services, cloud/aws/ci-cd/cloudformation-cdk, cloud/aws/monitoring/cloudwatch, cloud/aws/security/kms-secrets]
official_docs: https://aws.amazon.com/products/developer-tools/
status: complete
difficulty: beginner
last_updated: 2026-02-25
---

# AWS CI/CD — Developer Tools e Infrastructure as Code

AWS offre un portfolio completo di strumenti per CI/CD e Infrastructure as Code, dalle pipeline di build e deploy ai framework IaC di alto livello.

---

## Servizi CI/CD AWS

<div class="grid cards" markdown>

-   **CodeBuild, CodeDeploy, CodePipeline, CodeArtifact**

    ---

    Pipeline CI/CD: build (CodeBuild), deploy (CodeDeploy), orchestrazione (CodePipeline), gestione artefatti (CodeArtifact).

    [:octicons-arrow-right-24: Code Services](code-services.md)

-   **CloudFormation, CDK, SAM**

    ---

    Infrastructure as Code: CloudFormation (dichiarativo), CDK (linguaggi di programmazione), SAM (serverless), StackSets per multi-account.

    [:octicons-arrow-right-24: CloudFormation e CDK](cloudformation-cdk.md)

</div>

---

## Architettura CI/CD Tipica su AWS

### Pipeline Standard (Container/EC2)

```
[Developer Push]
    │ GitHub / CodeCommit
    ▼
[CodePipeline — Source Stage]
    │ trigger automatico su push
    ▼
[CodeBuild — Build Stage]
    │ buildspec.yml
    │ - Unit test
    │ - Build Docker image
    │ - Push ECR
    │ - Security scan (Trivy, Snyk)
    ▼
[CodeBuild — Test Stage]
    │ - Integration test
    │ - DAST scan
    ▼
[Manual Approval] (opzionale per prod)
    │ email SNS al team
    ▼
[CodeDeploy — Deploy Stage]
    │ - Blue/Green (ECS/EC2)
    │ - Canary/Linear (Lambda)
    │ - Rollback automatico su failure
    ▼
[CloudWatch + X-Ray]
    └── Monitoring post-deploy
```

### Pipeline Serverless (SAM/CDK)

```
[Developer Push]
    │ GitHub
    ▼
[CodePipeline]
    │
    ├── Source: GitHub App connection
    ├── Build: CodeBuild → sam build → sam package
    ├── Test: CodeBuild → integration tests
    ├── Approval: Manual per prod
    └── Deploy: CloudFormation change set → execute
```

---

## Quick Reference

| Servizio | Cosa Fa | Quando Usarlo |
|---------|---------|--------------|
| **CodeBuild** | Build, test, Docker push | Sempre (sostituzione Jenkins) |
| **CodeDeploy** | Deploy su EC2/ECS/Lambda | Deploy automatizzati con rollback |
| **CodePipeline** | Orchestrazione pipeline | Collegare Source→Build→Test→Deploy |
| **CodeArtifact** | Repository artefatti | Package Python/npm/Maven interni |
| **CloudFormation** | IaC dichiarativo YAML/JSON | Qualsiasi infrastruttura AWS |
| **CDK** | IaC con TypeScript/Python/Java | Team con preferenza per linguaggi |
| **SAM** | IaC per serverless | Applicazioni Lambda-first |

---

## Integrazione con GitHub

AWS CodePipeline v2 supporta GitHub tramite **GitHub App connection** (raccomandato), più sicuro e stabile di OAuth.

```bash
# Creare una connessione GitHub (richiede autorizzazione manuale nella console)
aws codeconnections create-connection \
  --provider-type GitHub \
  --connection-name "github-myorg" \
  --tags Key=Environment,Value=production
```

---

## Riferimenti

- [AWS Developer Tools](https://aws.amazon.com/products/developer-tools/)
- [CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [CodeDeploy Documentation](https://docs.aws.amazon.com/codedeploy/)
- [CodePipeline Documentation](https://docs.aws.amazon.com/codepipeline/)
- [CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
