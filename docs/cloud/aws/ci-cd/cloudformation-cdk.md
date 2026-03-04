---
title: "CloudFormation, CDK & SAM"
slug: cloudformation-cdk
category: cloud
tags: [aws, cloudformation, cdk, sam, iac, infrastructure-as-code, stacks, stacksets, change-sets, drift, custom-resources, nested-stacks, cfn-guard]
search_keywords: [AWS CloudFormation, AWS CDK, Cloud Development Kit, SAM, Serverless Application Model, infrastructure as code, IaC, stack, nested stack, StackSets, change set, drift detection, custom resource, CloudFormation macro, intrinsic functions, Ref, Fn::GetAtt, Fn::Sub, DeletionPolicy, UpdateReplacePolicy, CloudFormation hooks, cfn-guard, CDK constructs, L1 L2 L3, CDK pipelines, CDK Nag, CDK aspects, cdk synth, cdk deploy, sam local, sam build]
parent: cloud/aws/ci-cd/_index
related: [cloud/aws/ci-cd/code-services, cloud/aws/compute/lambda, cloud/aws/containers-ecs-eks]
official_docs: https://docs.aws.amazon.com/cloudformation/
status: complete
difficulty: advanced
last_updated: 2026-03-03
---

# CloudFormation, CDK & SAM

## AWS CloudFormation

**CloudFormation** è il servizio IaC (Infrastructure as Code) nativo di AWS — definisci l'infrastruttura in JSON o YAML e AWS crea/aggiorna/elimina le risorse (Stack) in modo dichiarativo.

```
CloudFormation Lifecycle

  Template (YAML/JSON)
       ↓
  Change Set (preview)
       ↓
  Stack → CREATE / UPDATE / DELETE
       ↓
  Resources: EC2, RDS, VPC, Lambda...
  (State stored in CloudFormation, NOT in a state file)
```

**Vantaggi rispetto a script imperativi:**
- Idempotente: apply dello stesso template = no cambiamenti se già aggiornato
- Rollback automatico su errore
- Dependency graph automatico (CloudFormation capisce l'ordine)
- Drift detection: confronta template vs risorse reali
- Nessun state file locale (a differenza di Terraform)

---

## Struttura Template

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: "Stack di produzione per MyApp"

# Metadati opzionali (es. per AWS Console UI)
Metadata:
  AWS::CloudFormation::Interface:
    ParameterGroups:
      - Label: {default: "Applicazione"}
        Parameters: [AppName, Environment]
    ParameterLabels:
      AppName: {default: "Nome Applicazione"}

# Parametri: valori passati al deploy
Parameters:
  AppName:
    Type: String
    Description: "Nome dell'applicazione"
    Default: myapp
    AllowedPattern: "[a-z][a-z0-9-]*"
    MaxLength: 50

  Environment:
    Type: String
    AllowedValues: [dev, staging, prod]
    Default: dev

  InstanceType:
    Type: String
    Default: t3.medium
    AllowedValues: [t3.small, t3.medium, t3.large, m5.large]

  VpcId:
    Type: AWS::EC2::VPC::Id    # tipo AWS speciale per validazione

  SubnetIds:
    Type: List<AWS::EC2::Subnet::Id>

  DBPassword:
    Type: String
    NoEcho: true               # nasconde il valore in Console/CLI
    MinLength: 8

# Mapping: lookup tables per environment/region
Mappings:
  EnvironmentConfig:
    dev:
      InstanceType: t3.small
      MinCapacity: 1
      MaxCapacity: 2
    prod:
      InstanceType: m5.large
      MinCapacity: 3
      MaxCapacity: 20

  RegionAMI:
    eu-central-1:
      AMI: ami-0a1b2c3d4e5f67890
    eu-west-1:
      AMI: ami-0987654321fedcba0

# Conditions: logica condizionale
Conditions:
  IsProd: !Equals [!Ref Environment, prod]
  IsNotDev: !Not [!Equals [!Ref Environment, dev]]
  HasMultiAZ: !Or [!Condition IsProd, !Condition IsNotDev]

# Risorse: la sezione principale e obbligatoria
Resources:

  # Security Group
  AppSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: !Sub "${AppName}-${Environment}-sg"
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 8080
          ToPort: 8080
          SourceSecurityGroupId: !Ref ALBSecurityGroup
      Tags:
        - Key: Name
          Value: !Sub "${AppName}-${Environment}-sg"
        - Key: Environment
          Value: !Ref Environment

  # RDS Instance con condition
  Database:
    Type: AWS::RDS::DBInstance
    DeletionPolicy: Snapshot          # crea snapshot prima di eliminare
    UpdateReplacePolicy: Snapshot     # crea snapshot prima di replace
    Properties:
      DBInstanceClass: !FindInMap [EnvironmentConfig, !Ref Environment, InstanceType]
      Engine: postgres
      EngineVersion: "16.1"
      MasterUsername: myapp
      MasterUserPassword: !Ref DBPassword
      AllocatedStorage: "20"
      StorageType: gp3
      MultiAZ: !If [IsProd, true, false]   # MultiAZ solo in prod
      DBSubnetGroupName: !Ref DBSubnetGroup
      VPCSecurityGroups: [!Ref DBSecurityGroup]
      StorageEncrypted: true
      BackupRetentionPeriod: !If [IsProd, 7, 1]
      DeletionProtection: !If [IsProd, true, false]
      Tags:
        - Key: Environment
          Value: !Ref Environment

  # Lambda Function
  MyFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${AppName}-${Environment}"
      Runtime: python3.12
      Handler: handler.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        S3Bucket: !Sub "my-deployments-${AWS::AccountId}"
        S3Key: !Sub "${AppName}/lambda.zip"
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment
          DB_HOST: !GetAtt Database.Endpoint.Address
          DB_PORT: !GetAtt Database.Endpoint.Port
      Timeout: 30
      MemorySize: !If [IsProd, 512, 256]
      Architectures: [arm64]

# Output: valori esportati dopo il deploy
Outputs:
  DatabaseEndpoint:
    Description: "RDS Endpoint"
    Value: !GetAtt Database.Endpoint.Address
    Export:
      Name: !Sub "${AWS::StackName}-db-endpoint"   # importabile da altri stack

  FunctionArn:
    Value: !GetAtt MyFunction.Arn
    Export:
      Name: !Sub "${AWS::StackName}-function-arn"
```

---

## Intrinsic Functions

```yaml
# Ref — riferimento a parametro o risorsa (ID/Name)
!Ref Environment             # "prod"
!Ref MyEC2Instance           # "i-1234567890abcdef0"

# Fn::GetAtt — attributo di una risorsa
!GetAtt Database.Endpoint.Address
!GetAtt ALB.DNSName
!GetAtt LambdaRole.Arn

# Fn::Sub — interpolazione stringhe
!Sub "arn:aws:s3:::${AppName}-${Environment}-bucket"
!Sub
  - "jdbc:postgresql://${Host}:5432/${DBName}"
  - Host: !GetAtt Database.Endpoint.Address
    DBName: myapp

# Fn::Join — unire stringhe
!Join [",", [!Ref SubnetA, !Ref SubnetB, !Ref SubnetC]]

# Fn::Select — seleziona da lista
!Select [0, !Ref SubnetIds]   # primo elemento

# Fn::Split — divide stringa in lista
!Split [",", "a,b,c"]

# Fn::If — condizionale
!If [IsProd, "m5.large", "t3.small"]

# Fn::ImportValue — importa output di un altro stack
!ImportValue "network-stack-VpcId"

# Fn::FindInMap — lookup in Mappings
!FindInMap [RegionAMI, !Ref "AWS::Region", AMI]

# Fn::Base64 — codifica base64 (es. UserData)
!Base64 |
  #!/bin/bash
  echo "Hello World" > /tmp/test.txt

# Fn::Cidr — genera lista di CIDR
!Cidr [!GetAtt VPC.CidrBlock, 6, 8]   # 6 subnet da /24 each

# Pseudo Parameters
!Ref "AWS::Region"            # eu-central-1
!Ref "AWS::AccountId"         # 123456789012
!Ref "AWS::StackName"         # my-stack-prod
!Ref "AWS::Partition"         # aws (o aws-cn, aws-us-gov)
!Ref "AWS::NoValue"           # rimuove la proprietà (nelle Conditions)
!Ref "AWS::URLSuffix"         # amazonaws.com
```

---

## Operazioni Stack

```bash
# Creare stack con parametri
aws cloudformation create-stack \
    --stack-name myapp-prod \
    --template-body file://template.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=prod \
        ParameterKey=AppName,ParameterValue=myapp \
        ParameterKey=DBPassword,ParameterValue="$(aws secretsmanager get-secret-value \
            --secret-id myapp/db-password --query SecretString --output text)" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --tags Key=Environment,Value=prod Key=Team,Value=platform \
    --on-failure ROLLBACK     # ROLLBACK | DO_NOTHING | DELETE

# Attendere completamento
aws cloudformation wait stack-create-complete --stack-name myapp-prod

# Creare Change Set (preview delle modifiche)
aws cloudformation create-change-set \
    --stack-name myapp-prod \
    --change-set-name update-instance-type \
    --template-body file://template-v2.yaml \
    --parameters ParameterKey=Environment,UsePreviousValue=true \
    --capabilities CAPABILITY_IAM

# Visualizzare Change Set
aws cloudformation describe-change-set \
    --stack-name myapp-prod \
    --change-set-name update-instance-type \
    --query 'Changes[*].{Action:ResourceChange.Action,Resource:ResourceChange.LogicalResourceId,Type:ResourceChange.ResourceType,Replace:ResourceChange.Replacement}'

# Eseguire Change Set
aws cloudformation execute-change-set \
    --stack-name myapp-prod \
    --change-set-name update-instance-type

# Aggiornare stack direttamente (senza change set)
aws cloudformation update-stack \
    --stack-name myapp-prod \
    --template-body file://template-v2.yaml \
    --parameters ParameterKey=Environment,UsePreviousValue=true \
    --capabilities CAPABILITY_IAM

# Drift Detection
aws cloudformation detect-stack-drift --stack-name myapp-prod
aws cloudformation describe-stack-drift-detection-status \
    --stack-drift-detection-id "DETECTION_ID"
aws cloudformation describe-stack-resource-drifts \
    --stack-name myapp-prod \
    --stack-resource-drift-status-filters MODIFIED DELETED

# Eliminare stack
aws cloudformation delete-stack --stack-name myapp-dev
aws cloudformation wait stack-delete-complete --stack-name myapp-dev
```

---

## Nested Stacks

I **Nested Stacks** riutilizzano template come moduli in altri stack.

```yaml
# parent-stack.yaml
Resources:
  NetworkStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://s3.amazonaws.com/my-templates/network.yaml
      Parameters:
        VpcCidr: "10.0.0.0/16"
        Environment: !Ref Environment
      TimeoutInMinutes: 30

  AppStack:
    Type: AWS::CloudFormation::Stack
    DependsOn: NetworkStack
    Properties:
      TemplateURL: https://s3.amazonaws.com/my-templates/app.yaml
      Parameters:
        VpcId: !GetAtt NetworkStack.Outputs.VpcId
        SubnetIds: !GetAtt NetworkStack.Outputs.PrivateSubnetIds
        Environment: !Ref Environment
```

```bash
# Aggiornare template nested in S3
aws s3 cp network.yaml s3://my-templates/network.yaml
aws s3 cp app.yaml s3://my-templates/app.yaml

# Poi aggiornare il parent stack
aws cloudformation update-stack \
    --stack-name parent-stack \
    --template-body file://parent-stack.yaml \
    --capabilities CAPABILITY_IAM
```

---

## CloudFormation StackSets

**StackSets** deploya uno stesso template in **più account e/o Region** simultaneamente.

```bash
# Creare StackSet con Organizations integration
aws cloudformation create-stack-set \
    --stack-set-name security-baseline \
    --template-body file://security-baseline.yaml \
    --permission-model SERVICE_MANAGED \    # o SELF_MANAGED
    --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false

# Deployare in OU specifica (tutti gli account nell'OU)
aws cloudformation create-stack-instances \
    --stack-set-name security-baseline \
    --deployment-targets OrganizationalUnitIds=ou-xxxx-yyyyyyy \
    --regions eu-central-1 eu-west-1 \
    --operation-preferences \
        RegionConcurrencyType=PARALLEL,\
        MaxConcurrentPercentage=100,\
        FailureTolerancePercentage=10

# Aggiornare tutte le istanze dello StackSet
aws cloudformation update-stack-set \
    --stack-set-name security-baseline \
    --template-body file://security-baseline-v2.yaml \
    --deployment-targets OrganizationalUnitIds=ou-xxxx-yyyyyyy \
    --regions eu-central-1 eu-west-1

# Monitorare operazione
aws cloudformation describe-stack-set-operation \
    --stack-set-name security-baseline \
    --operation-id OPERATION_ID
```

---

## Custom Resources

Le **Custom Resource** permettono di gestire risorse non supportate nativamente da CloudFormation tramite Lambda.

```python
# Lambda handler per custom resource
import json
import urllib.request

def handler(event, context):
    print(f"RequestType: {event['RequestType']}")
    print(f"ResourceProperties: {event['ResourceProperties']}")

    response_data = {}
    physical_id = event.get('PhysicalResourceId', 'custom-resource-1')

    try:
        if event['RequestType'] == 'Create':
            # Esegui creazione
            result = create_resource(event['ResourceProperties'])
            physical_id = result['id']
            response_data = {'Endpoint': result['endpoint']}

        elif event['RequestType'] == 'Update':
            # Esegui update
            update_resource(physical_id, event['ResourceProperties'])

        elif event['RequestType'] == 'Delete':
            # Esegui cleanup
            delete_resource(physical_id)

        send_response(event, context, 'SUCCESS', response_data, physical_id)

    except Exception as e:
        print(f"Error: {e}")
        send_response(event, context, 'FAILED', {'Error': str(e)}, physical_id)

def send_response(event, context, status, data, physical_id):
    body = json.dumps({
        'Status': status,
        'Reason': f'See logs in {context.log_stream_name}',
        'PhysicalResourceId': physical_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': False,
        'Data': data
    })
    url = event['ResponseURL']
    req = urllib.request.Request(url, data=body.encode(), method='PUT')
    req.add_header('Content-Type', '')
    urllib.request.urlopen(req)
```

```yaml
# Template con Custom Resource
Resources:
  CustomResourceLambda:
    Type: AWS::Lambda::Function
    Properties:
      Handler: custom_resource.handler
      Role: !GetAtt LambdaRole.Arn
      Code:
        ZipFile: |
          # inline code (o da S3)
      Runtime: python3.12

  MyCustomResource:
    Type: Custom::MyResourceType
    Properties:
      ServiceToken: !GetAtt CustomResourceLambda.Arn   # ARN Lambda
      # Qualsiasi proprietà custom:
      DatabaseName: myapp
      Region: !Ref AWS::Region

Outputs:
  CustomEndpoint:
    Value: !GetAtt MyCustomResource.Endpoint   # valore restituito dalla Lambda
```

---

## CloudFormation Guard (cfn-guard)

**cfn-guard** è uno strumento di policy-as-code per validare template CloudFormation.

```bash
# Installare cfn-guard
brew install cloudformation-guard   # macOS
# o: cargo install cfn-guard

# Regola: S3 bucket deve avere encryption abilitata
cat > s3-encryption.guard <<'EOF'
rule s3_bucket_encryption_enabled {
    AWS::S3::Bucket {
        Properties {
            BucketEncryption exists
            BucketEncryption.ServerSideEncryptionConfiguration[*].ServerSideEncryptionByDefault.SSEAlgorithm in
                ["aws:kms", "AES256"]
        }
    }
}

rule no_public_s3_buckets {
    AWS::S3::Bucket {
        Properties {
            PublicAccessBlockConfiguration exists
            PublicAccessBlockConfiguration.BlockPublicAcls == true
            PublicAccessBlockConfiguration.BlockPublicPolicy == true
        }
    }
}
EOF

# Validare template contro regole
cfn-guard validate \
    --data template.yaml \
    --rules s3-encryption.guard

# Usare in CodeBuild (CI/CD pre-deployment check)
# buildspec.yml:
# - cfn-guard validate --data $CODEBUILD_SRC_DIR/template.yaml --rules rules/
```

---

## AWS CDK (Cloud Development Kit)

**CDK** permette di definire infrastruttura AWS con linguaggi di programmazione reali — eliminando la verbosità del YAML CloudFormation.

```bash
# Setup progetto CDK TypeScript
npm install -g aws-cdk
mkdir myapp-infra && cd myapp-infra
cdk init app --language typescript

# Struttura progetto
# myapp-infra/
# ├── bin/myapp-infra.ts      ← Entry point, crea Stack
# ├── lib/myapp-infra-stack.ts ← Definizione dello Stack
# ├── test/                   ← Test
# └── cdk.json                ← Configurazione CDK
```

```typescript
// lib/myapp-infra-stack.ts
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

export class MyappInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // L2 Construct: VPC con 3 tier (Public, Private, Isolated)
    const vpc = new ec2.Vpc(this, 'AppVpc', {
      maxAzs: 3,
      natGateways: 1,       // crea NAT GW automaticamente
      subnetConfiguration: [
        { name: 'Public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
        { name: 'App',    subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS, cidrMask: 24 },
        { name: 'DB',     subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 },
      ],
    });

    // Secret per DB password (rotazione automatica)
    const dbSecret = new secretsmanager.Secret(this, 'DbSecret', {
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'myapp' }),
        generateStringKey: 'password',
        excludeCharacters: '"@/\\',
      },
    });

    // RDS Aurora PostgreSQL (L2 Construct)
    const cluster = new rds.DatabaseCluster(this, 'AuroraCluster', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_16_1,
      }),
      credentials: rds.Credentials.fromSecret(dbSecret),
      writer: rds.ClusterInstance.provisioned('writer', {
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.R6G, ec2.InstanceSize.LARGE
        ),
      }),
      readers: [
        rds.ClusterInstance.provisioned('reader1', {
          instanceType: ec2.InstanceType.of(
            ec2.InstanceClass.R6G, ec2.InstanceSize.LARGE
          ),
        }),
      ],
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      defaultDatabaseName: 'myapp',
      backup: { retention: cdk.Duration.days(7) },
      deletionProtection: true,
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
    });

    // ECS Cluster + Fargate Service
    const ecsCluster = new ecs.Cluster(this, 'AppCluster', { vpc });

    const repository = ecr.Repository.fromRepositoryName(
      this, 'AppRepo', 'myapp'
    );

    const taskDefinition = new ecs.FargateTaskDefinition(this, 'AppTask', {
      cpu: 512,
      memoryLimitMiB: 1024,
    });

    const container = taskDefinition.addContainer('app', {
      image: ecs.ContainerImage.fromEcrRepository(repository, 'latest'),
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'myapp' }),
      secrets: {
        DB_PASSWORD: ecs.Secret.fromSecretsManager(dbSecret, 'password'),
      },
      environment: {
        DB_HOST: cluster.clusterEndpoint.hostname,
      },
    });
    container.addPortMappings({ containerPort: 8080 });

    // ALB + Fargate Service (L3 Construct — tutto in uno)
    const loadBalancedService = new ecs_patterns.ApplicationLoadBalancedFargateService(
      this, 'AppService', {
        cluster: ecsCluster,
        taskDefinition,
        desiredCount: 2,
        listenerPort: 443,
        protocol: elbv2.ApplicationProtocol.HTTPS,
        publicLoadBalancer: true,
        circuitBreaker: { rollback: true },
      }
    );

    // Grant access: ECS task può leggere il secret
    dbSecret.grantRead(taskDefinition.taskRole);
    // Grant access: ECS task può connettersi a RDS
    cluster.connections.allowFrom(
      loadBalancedService.service, ec2.Port.tcp(5432)
    );

    // Output
    new cdk.CfnOutput(this, 'LoadBalancerDNS', {
      value: loadBalancedService.loadBalancer.loadBalancerDnsName,
    });
  }
}
```

```typescript
// bin/myapp-infra.ts — entry point multi-environment
import * as cdk from 'aws-cdk-lib';
import { MyappInfraStack } from '../lib/myapp-infra-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

new MyappInfraStack(app, 'MyappDev', {
  env,
  tags: { Environment: 'dev' },
});

new MyappInfraStack(app, 'MyappProd', {
  env: { account: '999999999999', region: 'eu-central-1' },
  tags: { Environment: 'prod' },
  terminationProtection: true,
});
```

```bash
# Comandi CDK
cdk synth                       # genera CloudFormation YAML (senza deploy)
cdk diff                        # mostra differenze vs stack attuale
cdk deploy                      # deploy
cdk deploy --hotswap            # deploy rapido (solo Lambda/ECS, no full CF update)
cdk watch                       # deploy automatico su salvataggio file (dev)
cdk destroy                     # elimina stack
cdk ls                          # lista tutti gli stacks

# Bootstrap (necessario una volta per account/Region)
cdk bootstrap aws://123456789012/eu-central-1

# Deploy con context values
cdk deploy -c environment=prod -c appVersion=1.3.0

# CDK con profilo AWS specifico
cdk deploy --profile prod-account
```

### CDK Constructs — L1 / L2 / L3

```typescript
// L1 Construct: mappatura diretta a CloudFormation (CfnXxx)
const cfnBucket = new s3.CfnBucket(this, 'L1Bucket', {
  bucketEncryption: {
    serverSideEncryptionConfiguration: [{
      serverSideEncryptionByDefault: { sseAlgorithm: 'aws:kms' },
    }],
  },
});

// L2 Construct: abstraction con defaults sensati (la maggior parte CDK)
const bucket = new s3.Bucket(this, 'L2Bucket', {
  encryption: s3.BucketEncryption.KMS_MANAGED,   // default key
  versioned: true,
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});

// L3 Construct (Pattern): infrastruttura complessa pre-configurata
// es. QueueProcessingFargateService, ApplicationLoadBalancedFargateService
```

### CDK Aspects

```typescript
// Aspetti: applicano logica trasversale a TUTTO il costrutto tree
class RequireTagsAspect implements cdk.IAspect {
  visit(node: cdk.IConstruct): void {
    if (node instanceof cdk.CfnResource) {
      cdk.Tags.of(node).add('ManagedBy', 'CDK');
      cdk.Tags.of(node).add('LastUpdated', new Date().toISOString().split('T')[0]);
    }
  }
}

// Applicare l'aspetto a tutto lo stack
cdk.Aspects.of(app).add(new RequireTagsAspect());

// CDK Nag — sicurezza e compliance checks
import { AwsSolutionsChecks } from 'cdk-nag';
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
```

### CDK Pipelines

```typescript
// CDK Pipelines: pipeline CI/CD self-mutating
import * as pipelines from 'aws-cdk-lib/pipelines';

class InfraPipelineStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const pipeline = new pipelines.CodePipeline(this, 'Pipeline', {
      synth: new pipelines.ShellStep('Synth', {
        input: pipelines.CodePipelineSource.gitHub(
          'company/myapp-infra', 'main',
          { authentication: cdk.SecretValue.secretsManager('github-token') }
        ),
        commands: ['npm ci', 'npm run build', 'npx cdk synth'],
      }),
      selfMutation: true,   // la pipeline si aggiorna automaticamente
    });

    // Stage: staging
    pipeline.addStage(new MyappStage(this, 'Staging', {
      env: { account: '111111111111', region: 'eu-central-1' },
    }), {
      post: [
        new pipelines.ShellStep('IntegrationTest', {
          commands: ['npm run test:integration'],
        }),
      ],
    });

    // Stage: produzione con approvazione manuale
    pipeline.addStage(new MyappStage(this, 'Production', {
      env: { account: '999999999999', region: 'eu-central-1' },
    }), {
      pre: [new pipelines.ManualApprovalStep('ApproveProduction')],
    });
  }
}
```

---

## AWS SAM (Serverless Application Model)

**SAM** è un'estensione CloudFormation ottimizzata per applicazioni serverless. Il template SAM viene trasformato in CloudFormation al deploy.

```yaml
# template.yaml (SAM)
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31   # SAM Transform

Globals:                                # valori default per tutte le funzioni
  Function:
    Runtime: python3.12
    Architectures: [arm64]
    Timeout: 30
    MemorySize: 256
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        TABLE_NAME: !Ref MyTable
    Tracing: Active                     # X-Ray

Parameters:
  Environment:
    Type: String
    Default: dev

Resources:
  # AWS::Serverless::Function → Lambda + trigger + permissions automatiche
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: api.handler
      CodeUri: src/api/
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref MyTable
        - SQSSendMessagePolicy:
            QueueName: !GetAtt MyQueue.QueueName
      Events:
        ApiEvent:
          Type: Api              # → crea API Gateway REST automaticamente
          Properties:
            RestApiId: !Ref MyApi
            Path: /items
            Method: GET
        ApiPostEvent:
          Type: Api
          Properties:
            RestApiId: !Ref MyApi
            Path: /items
            Method: POST

  ProcessorFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: processor.handler
      CodeUri: src/processor/
      Events:
        SQSEvent:
          Type: SQS              # → Event Source Mapping automatico
          Properties:
            Queue: !GetAtt MyQueue.Arn
            BatchSize: 10
            FunctionResponseTypes:
              - ReportBatchItemFailures

  # AWS::Serverless::Api → API Gateway REST
  MyApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: !Ref Environment
      Cors:
        AllowMethods: "'GET,POST,OPTIONS'"
        AllowHeaders: "'Content-Type,Authorization'"
        AllowOrigin: "'*'"
      Auth:
        DefaultAuthorizer: CognitoAuthorizer
        Authorizers:
          CognitoAuthorizer:
            UserPoolArn: !GetAtt UserPool.Arn

  # AWS::Serverless::SimpleTable → DynamoDB
  MyTable:
    Type: AWS::Serverless::SimpleTable
    Properties:
      PrimaryKey:
        Name: id
        Type: String
      ProvisionedThroughput:
        ReadCapacityUnits: 5
        WriteCapacityUnits: 5

  MyQueue:
    Type: AWS::SQS::Queue
    Properties:
      VisibilityTimeout: 90     # >= Lambda timeout × 6

Outputs:
  ApiUrl:
    Value: !Sub "https://${MyApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
```

```bash
# SAM CLI
sam build                     # installa dipendenze, impacchetta
sam local invoke ApiFunction  # invoca localmente
sam local start-api           # avvia API Gateway locale (http://localhost:3000)
sam local start-lambda        # endpoint Lambda locale (per test SDK)

# Deploy
sam deploy \
    --stack-name myapp-prod \
    --region eu-central-1 \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment=prod \
    --s3-bucket my-sam-artifacts \
    --confirm-changeset          # richiede conferma Change Set prima del deploy

# Pipeline per SAM (genera CodePipeline con CodeBuild)
sam pipeline init
sam pipeline bootstrap
```

---

## Best Practices CloudFormation/CDK

```
CloudFormation/CDK Best Practices

  Template Design:
  ✓ DeletionPolicy: Snapshot per database (mai Delete in prod)
  ✓ Termination Protection su stack di produzione
  ✓ NoEcho: true per parametri sensibili
  ✓ Usare Secrets Manager per credenziali (non Parametri)
  ✓ Change Set prima di ogni update su produzione
  ✓ Drift Detection periodica

  Stack Architecture:
  ✓ Separare Network / IAM / App in stack distinti
  ✓ Nested Stacks per riuso moduli
  ✓ StackSets per standard cross-account (GuardDuty, Config, CloudTrail)
  ✓ Export/ImportValue per dipendenze tra stack

  CDK Specifico:
  ✓ cdk synth in CI per validazione prima del deploy
  ✓ CDK Nag per security compliance check
  ✓ CDK Aspects per tag e policy trasversali
  ✓ Test con fine-grained assertions (non solo snapshot)
  ✓ CDK Pipelines per self-mutating CI/CD
```

---

## Riferimenti

- [CloudFormation User Guide](https://docs.aws.amazon.com/cloudformation/latest/userguide/)
- [CloudFormation Template Reference](https://docs.aws.amazon.com/cloudformation/latest/userguide/template-reference.html)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/latest/guide/)
- [CDK API Reference](https://docs.aws.amazon.com/cdk/api/v2/)
- [SAM Developer Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/)
- [cfn-guard](https://github.com/aws-cloudformation/cloudformation-guard)
- [CDK Nag](https://github.com/cdklabs/cdk-nag)
- [CDK Patterns](https://cdkpatterns.com/)
