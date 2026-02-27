---
title: "GuardDuty, Inspector, Macie, Security Hub, Config e CloudTrail"
slug: compliance-audit
category: cloud
tags: [aws, guardduty, inspector, macie, security-hub, config, cloudtrail, compliance, audit, threat-detection, vulnerability-assessment, cspm]
search_keywords: [guardduty, threat detection, ml security, inspector, vulnerability assessment, cve, ecr scan, lambda security, macie, pii detection, data classification, security hub, asff, compliance standards, cis benchmark, pci dss, aws config, config rules, conformance pack, remediation, cloudtrail, api audit log, cloudtrail lake, data events, insights events, log integrity, organizations multi-account]
parent: cloud/aws/security/_index
related: [cloud/aws/security/kms-secrets, cloud/aws/security/network-security, cloud/aws/monitoring/cloudwatch, cloud/aws/monitoring/observability]
official_docs: https://docs.aws.amazon.com/guardduty/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# GuardDuty, Inspector, Macie, Security Hub, Config e CloudTrail

## Panoramica

Questo documento copre i servizi AWS per il rilevamento delle minacce, la valutazione delle vulnerabilità, la protezione dei dati, la compliance e l'audit. Insieme, questi servizi formano il layer di detection e governance della sicurezza AWS.

---

## Amazon GuardDuty

### Panoramica

GuardDuty è un servizio di threat detection continuativo basato su machine learning. Analizza automaticamente i log AWS per identificare attività sospette, comportamenti anomali e compromissioni.

**Fonti dati analizzate:**
- AWS CloudTrail (Management Events + Data Events)
- VPC Flow Logs
- DNS Query Logs
- EKS Audit Logs
- RDS/Aurora Login Activity
- Lambda Network Activity Logs
- ECS Runtime Monitoring
- EC2 Runtime Monitoring (via SSM agent)
- S3 Data Events
- EBS Malware Protection (scansione EBS su istanze sospette)

!!! tip "GuardDuty non richiede configurazione dei log"
    GuardDuty accede direttamente ai log AWS tramite integrazione nativa, senza che il cliente debba abilitare CloudTrail o VPC Flow Logs sul proprio account. Tuttavia, se si usano anche per altri scopi, abilitarli è comunque consigliato.

### Categorie di Finding

| Categoria | Esempi |
|-----------|--------|
| **Backdoor** | Istanza EC2 che si comporta da botnet |
| **Behavior** | Pattern di traffico anomalo |
| **CryptoCurrency** | Mining di criptovalute |
| **Discovery** | Ricognizione di risorse AWS (enumeration) |
| **Exfiltration** | Trasferimento insolito di dati verso IP esterni |
| **Impact** | Eliminazione di risorse, defacement |
| **Initial Access** | Login insolito, accesso da IP anomalo |
| **Persistence** | Backdoor IAM, nuovi utenti creati |
| **Policy** | Root account usato, IAM permission escalation |
| **Privilege Escalation** | Cambio policy IAM sospetto |
| **Recon** | Port scanning, chiamate API enumeration |
| **Stealth** | Logging disabilitato, CloudTrail interrotto |
| **Trojan** | Traffico verso C2 noti |
| **UnauthorizedAccess** | Accesso da TOR exit node, IP blacklist |

**Severity:** Low (1-3.9), Medium (4-6.9), High (7-8.9), Critical (9-10)

### Abilitare GuardDuty

```bash
# Abilitare GuardDuty nel proprio account
aws guardduty create-detector \
  --enable \
  --data-sources '{
    "S3Logs": {"Enable": true},
    "Kubernetes": {"AuditLogs": {"Enable": true}},
    "MalwareProtection": {
      "ScanEc2InstanceWithFindings": {
        "EbsVolumes": {"Enable": true}
      }
    },
    "RdsLoginEvents": {"Enable": true},
    "RuntimeMonitoring": {
      "RuntimeMonitoringConfiguration": {"Enable": true},
      "EksAddonManagement": {"Enable": true},
      "EcsFargateAgentManagement": {"Enable": true},
      "Ec2AgentManagement": {"Enable": true}
    },
    "Lambda": {"LambdaNetworkLogs": {"Enable": true}}
  }' \
  --finding-publishing-frequency FIFTEEN_MINUTES

# Ottenere il Detector ID
DETECTOR_ID=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)

# Listare i finding
aws guardduty list-findings \
  --detector-id $DETECTOR_ID \
  --finding-criteria '{
    "Criterion": {
      "severity": {"Gte": 7}
    }
  }'

# Dettagli di un finding
aws guardduty get-findings \
  --detector-id $DETECTOR_ID \
  --finding-ids "finding-id-here"
```

### GuardDuty Multi-Account (Organizations)

```bash
# Designare un account come GuardDuty Delegated Admin (dall'account Management)
aws guardduty enable-organization-admin-account \
  --admin-account-id 123456789012

# Dall'account Delegated Admin: abilitare GuardDuty in tutti i member account
aws guardduty update-organization-configuration \
  --detector-id $DETECTOR_ID \
  --auto-enable-organization-members ALL \
  --data-sources '{
    "S3Logs": {"AutoEnable": true},
    "Kubernetes": {"AuditLogs": {"AutoEnable": true}}
  }'
```

### Automazione con EventBridge

```bash
# EventBridge rule per auto-remediation su finding High/Critical
aws events put-rule \
  --name "GuardDutyHighSeverityAlert" \
  --event-pattern '{
    "source": ["aws.guardduty"],
    "detail-type": ["GuardDuty Finding"],
    "detail": {
      "severity": [{"numeric": [">=", 7]}]
    }
  }' \
  --state ENABLED

# Target Lambda per auto-remediation
aws events put-targets \
  --rule "GuardDutyHighSeverityAlert" \
  --targets '[{
    "Id": "AutoRemediationLambda",
    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:guardduty-remediation",
    "InputTransformer": {
      "InputPathsMap": {
        "severity": "$.detail.severity",
        "type": "$.detail.type",
        "accountId": "$.detail.accountId",
        "region": "$.detail.region"
      },
      "InputTemplate": "{\"severity\": <severity>, \"type\": \"<type>\", \"accountId\": \"<accountId>\", \"region\": \"<region>\"}"
    }
  }]'
```

**Lambda di auto-remediation (esempio: isola un'istanza compromessa):**
```python
import boto3
import json

ec2 = boto3.client('ec2')
sns = boto3.client('sns')

def handler(event, context):
    finding_type = event.get('type', '')
    severity = event.get('severity', 0)

    # Per finding di tipo malware su EC2
    if 'Trojan' in finding_type or 'Backdoor' in finding_type:
        instance_id = extract_instance_id(event)
        if instance_id:
            # Isola l'istanza (rimuovi da SG normali, metti in quarantine SG)
            ec2.modify_instance_attribute(
                InstanceId=instance_id,
                Groups=['sg-quarantine-12345']  # SG senza regole outbound
            )

            # Notifica il team di sicurezza
            sns.publish(
                TopicArn='arn:aws:sns:us-east-1:123456789012:security-alerts',
                Subject=f'[CRITICAL] Malware detected on {instance_id}',
                Message=json.dumps(event, indent=2)
            )
```

---

## Amazon Inspector

### Panoramica

Inspector v2 (2021+) è un servizio di vulnerability assessment continuo e automatico. A differenza di Inspector v1 (che richiedeva configurazione manuale e scan periodici), Inspector v2 è sempre attivo e scansiona automaticamente.

**Scope di scansione:**
- **EC2:** scansione OS e applicazioni installate (richiede SSM Agent)
- **Amazon ECR:** scansione immagini Docker al push e continuamente
- **Lambda:** scansione del codice Lambda e dipendenze

**Finding types:**
- CVE (Common Vulnerabilities and Exposures) dal NVD database
- CIS (Center for Internet Security) benchmarks
- Network reachability (porte aperte esposte a Internet)
- Software composition analysis (SBOM — Software Bill of Materials)

```bash
# Abilitare Inspector v2
aws inspector2 enable \
  --resource-types EC2 ECR LAMBDA

# Con Organizations — abilitare su tutti gli account
aws inspector2 enable-delegated-admin-account \
  --delegated-admin-account-id 123456789012

# Listare i finding
aws inspector2 list-findings \
  --filter-criteria '{
    "severity": [{"comparison": "EQUALS", "value": "CRITICAL"}],
    "findingStatus": [{"comparison": "EQUALS", "value": "ACTIVE"}]
  }' \
  --sort-criteria '{"field": "SEVERITY", "sortOrder": "DESC"}'

# Trovare CVE specifici
aws inspector2 list-findings \
  --filter-criteria '{
    "vulnerabilityId": [{"comparison": "EQUALS", "value": "CVE-2021-44228"}]
  }'

# Esportare SBOM per un'immagine ECR
aws inspector2 create-sbom-export \
  --report-format SPDX_2_3 \
  --s3-destination '{
    "bucketName": "my-sbom-bucket",
    "keyPrefix": "sbom/"
  }'
```

### Inspector ECR Integration

```bash
# Configurare Enhanced Scanning per ECR (al posto del Basic Scanning)
aws ecr put-registry-scanning-configuration \
  --scan-type ENHANCED \
  --rules '[{
    "scanFrequency": "CONTINUOUS_SCAN",
    "repositoryFilters": [{"filter": "*", "filterType": "WILDCARD"}]
  }]'

# Verificare i risultati di una scan
aws ecr describe-image-scan-findings \
  --repository-name my-app \
  --image-id imageTag=latest \
  --query 'imageScanFindings.enhancedFindings[?severity==`CRITICAL`]'
```

---

## Amazon Macie

### Panoramica

Macie usa machine learning per scoprire, classificare e proteggere dati sensibili (PII, PHI, credenziali, IP, dati finanziari) archiviati in Amazon S3.

**Tipi di dati rilevati:**
- PII: SSN, carte di credito, numeri di passaporto, indirizzi, numeri di telefono
- PHI: dati sanitari (HIPAA)
- Credenziali: password, chiavi API, chiavi SSH private
- Dati finanziari: coordinate bancarie, codici IBAN

```bash
# Abilitare Macie
aws macie2 enable-macie

# Creare un job di classificazione
aws macie2 create-classification-job \
  --job-type ONE_TIME \
  --name "Initial S3 Scan" \
  --s3-job-definition '{
    "bucketDefinitions": [
      {
        "accountId": "123456789012",
        "buckets": ["my-data-bucket", "another-bucket"]
      }
    ]
  }' \
  --sampling-percentage 100

# Job schedulato (ogni giorno)
aws macie2 create-classification-job \
  --job-type SCHEDULED \
  --name "Daily Scan" \
  --schedule-frequency DAILY \
  --s3-job-definition '{
    "bucketDefinitions": [{"accountId": "123456789012", "buckets": ["my-data-bucket"]}]
  }'

# Listare i finding
aws macie2 list-findings \
  --filter-criteria '{
    "findingCriteria": {
      "criterion": {
        "severity.score": {"gte": 50}
      }
    }
  }'

# Dettagli di un finding
aws macie2 get-findings \
  --finding-ids "finding-id-here"

# Statistiche per bucket
aws macie2 describe-buckets \
  --criteria '{
    "sharedAccess": {"eq": ["INTERNAL"]},
    "publicAccess.effectivePermission": {"eq": ["NOT_PUBLIC"]}
  }'
```

### Macie con Organizations

```bash
# Delegare Macie a un account admin
aws macie2 enable-organization-admin-account \
  --admin-account-id 123456789012

# Auto-abilitare su nuovi account
aws macie2 update-organization-configuration \
  --auto-enable
```

---

## AWS Security Hub

### Panoramica

Security Hub è il pannello di controllo centrale per la sicurezza AWS. Aggrega, organizza e priorizza i finding di sicurezza da GuardDuty, Inspector, Macie, Config, Firewall Manager, IAM Access Analyzer, e altri.

**Compliance Standards supportati:**
- AWS Foundational Security Best Practices (FSBP)
- CIS AWS Foundations Benchmark (v1.2, v1.4, v3.0)
- PCI DSS v3.2.1
- NIST SP 800-53 Rev. 5
- SOC 2
- AWS Resource Tagging Standard

```bash
# Abilitare Security Hub
aws securityhub enable-security-hub \
  --enable-default-standards \
  --tags "Environment=production"

# Abilitare standard CIS
aws securityhub batch-enable-standards \
  --standards-subscription-requests '[
    {"StandardsArn": "arn:aws:securityhub:us-east-1::standards/cis-aws-foundations-benchmark/v/1.4.0"},
    {"StandardsArn": "arn:aws:securityhub:us-east-1::standards/pci-dss/v/3.2.1"}
  ]'

# Listare i finding
aws securityhub get-findings \
  --filters '{
    "SeverityLabel": [{"Value": "CRITICAL", "Comparison": "EQUALS"}],
    "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
  }' \
  --sort-criteria '[{
    "Field": "SeverityLabel",
    "SortOrder": "desc"
  }]'

# Aggiornare lo stato di workflow di un finding
aws securityhub batch-update-findings \
  --finding-identifiers '[{
    "Id": "arn:aws:securityhub:us-east-1:123456789012:finding/finding-id",
    "ProductArn": "arn:aws:securityhub:us-east-1::product/aws/guardduty"
  }]' \
  --workflow '{"Status": "NOTIFIED"}' \
  --note '{"Text": "Escalato al team SOC", "UpdatedBy": "analyst-alice"}'
```

### ASFF — Amazon Security Findings Format

Tutti i finding in Security Hub usano il formato standardizzato ASFF (JSON). Ogni tool di sicurezza che si integra con Security Hub deve tradurre i propri finding in questo formato.

```json
{
  "SchemaVersion": "2018-10-08",
  "Id": "arn:aws:securityhub:...",
  "ProductArn": "arn:aws:securityhub:us-east-1::product/aws/guardduty",
  "GeneratorId": "arn:aws:guardduty:...",
  "AwsAccountId": "123456789012",
  "Types": ["TTPs/Initial Access/Unusual ConsoleLogin"],
  "CreatedAt": "2024-01-15T10:00:00Z",
  "UpdatedAt": "2024-01-15T10:00:00Z",
  "Severity": {
    "Label": "HIGH",
    "Normalized": 70,
    "Original": "7.5"
  },
  "Title": "Unusual ConsoleLogin from IP in threat intel list",
  "Description": "...",
  "Resources": [{
    "Type": "AwsIamUser",
    "Id": "arn:aws:iam::123456789012:user/alice"
  }],
  "Workflow": {"Status": "NEW"},
  "RecordState": "ACTIVE"
}
```

### Automazione Security Hub → Ticketing

```bash
# EventBridge rule per inviare finding critici a Jira/ServiceNow
aws events put-rule \
  --name "SecurityHubCriticalFindings" \
  --event-pattern '{
    "source": ["aws.securityhub"],
    "detail-type": ["Security Hub Findings - Imported"],
    "detail": {
      "findings": {
        "Severity": {"Label": ["CRITICAL", "HIGH"]},
        "Workflow": {"Status": ["NEW"]},
        "RecordState": ["ACTIVE"]
      }
    }
  }'
```

---

## AWS Config

### Panoramica

AWS Config registra lo **stato** e le **modifiche** delle risorse AWS nel tempo. Permette di:
- Vedere la configurazione di ogni risorsa in un momento passato
- Rilevare modifiche non autorizzate
- Verificare la conformità alle policy aziendali (Config Rules)
- Generare report di compliance per audit

```bash
# Abilitare AWS Config con recorder
aws configservice put-configuration-recorder \
  --configuration-recorder '{
    "name": "default",
    "roleARN": "arn:aws:iam::123456789012:role/ConfigRole",
    "recordingGroup": {
      "allSupported": true,
      "includeGlobalResourceTypes": true
    }
  }'

# Configurare il delivery channel (dove inviare i dati)
aws configservice put-delivery-channel \
  --delivery-channel '{
    "name": "default",
    "s3BucketName": "my-config-bucket",
    "snsTopicARN": "arn:aws:sns:us-east-1:123456789012:config-alerts",
    "configSnapshotDeliveryProperties": {
      "deliveryFrequency": "Six_Hours"
    }
  }'

# Avviare il recorder
aws configservice start-configuration-recorder \
  --configuration-recorder-name default
```

### Config Rules

Le Config Rules verificano automaticamente che le risorse AWS siano conformi alle policy configurate.

```bash
# Regola managed: bucket S3 non deve essere pubblicamente accessibile
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "s3-bucket-public-read-prohibited",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "S3_BUCKET_PUBLIC_READ_PROHIBITED"
    }
  }'

# Regola managed: volume EBS deve essere cifrato
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "encrypted-volumes",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "ENCRYPTED_VOLUMES"
    }
  }'

# Regola managed: MFA abilitato per root account
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "root-account-mfa-enabled",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "ROOT_ACCOUNT_MFA_ENABLED"
    }
  }'

# Regola managed: istanze EC2 non devono avere public IP di default
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "ec2-instance-no-public-ip",
    "Source": {
      "Owner": "AWS",
      "SourceIdentifier": "EC2_INSTANCE_NO_PUBLIC_IP"
    }
  }'

# Regola custom con Lambda
aws configservice put-config-rule \
  --config-rule '{
    "ConfigRuleName": "required-tags",
    "Description": "Verifica che le risorse abbiano i tag obbligatori",
    "Source": {
      "Owner": "CUSTOM_LAMBDA",
      "SourceIdentifier": "arn:aws:lambda:us-east-1:123456789012:function:check-required-tags",
      "SourceDetails": [{
        "EventSource": "aws.config",
        "MessageType": "ConfigurationItemChangeNotification"
      }]
    },
    "InputParameters": "{\"requiredTags\": \"Environment,Project,Owner\"}"
  }'

# Verificare lo stato di conformità
aws configservice describe-compliance-by-config-rule \
  --config-rule-names "encrypted-volumes" "s3-bucket-public-read-prohibited"

# Trovare risorse non conformi
aws configservice get-compliance-details-by-config-rule \
  --config-rule-name "encrypted-volumes" \
  --compliance-types NON_COMPLIANT
```

### Config Remediations

Le Remediations eseguono automaticamente azioni correttive quando una risorsa non è conforme.

```bash
# Aggiungere una remediation action (es. cifrare un volume EBS)
aws configservice put-remediation-configurations \
  --remediation-configurations '[{
    "ConfigRuleName": "encrypted-volumes",
    "TargetType": "SSM_DOCUMENT",
    "TargetId": "AWS-EncryptEBSVolume",
    "Parameters": {
      "VolumeId": {
        "ResourceValue": {"Value": "RESOURCE_ID"}
      },
      "KmsKeyId": {
        "StaticValue": {"Values": ["alias/aws/ebs"]}
      }
    },
    "Automatic": false,
    "RetryAttemptSeconds": 60,
    "MaximumAutomaticAttempts": 3
  }]'

# Eseguire la remediation manualmente su risorse specifiche
aws configservice start-remediation-execution \
  --config-rule-name "encrypted-volumes" \
  --resource-keys '[{
    "resourceType": "AWS::EC2::Volume",
    "resourceId": "vol-1234567890abcdef0"
  }]'
```

### Configuration Timeline

```bash
# Vedere la storia di configurazione di una risorsa
aws configservice get-resource-config-history \
  --resource-type AWS::EC2::SecurityGroup \
  --resource-id sg-1234567890 \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-31T23:59:59Z"

# Snapshot della configurazione corrente
aws configservice deliver-config-snapshot \
  --delivery-channel-name default
```

### Config Aggregator (Multi-Account)

```bash
# Creare un aggregatore per tutti gli account nell'organizzazione
aws configservice put-configuration-aggregator \
  --configuration-aggregator-name "MyOrgAggregator" \
  --organization-aggregation-source '{
    "RoleArn": "arn:aws:iam::123456789012:role/ConfigAggregatorRole",
    "AllAwsRegions": true
  }'
```

### Conformance Pack

I Conformance Pack sono una raccolta di Config Rules + Remediations pre-assemblate per uno standard di compliance specifico.

```bash
# Deploy di un Conformance Pack AWS-managed (es. AWS Operational Best Practices for PCI DSS)
aws configservice put-conformance-pack \
  --conformance-pack-name "PCI-DSS-Pack" \
  --template-s3-uri "s3://aws-config-conformance-packs-us-east-1/Operational-Best-Practices-for-PCI-DSS.yaml" \
  --delivery-s3-bucket "my-config-bucket"

# Listare i Conformance Pack disponibili
aws configservice describe-conformance-packs

# Verificare compliance di un Conformance Pack
aws configservice describe-conformance-pack-compliance \
  --conformance-pack-names "PCI-DSS-Pack"
```

---

## AWS CloudTrail

### Panoramica

CloudTrail registra ogni **API call** effettuata sull'account AWS: chi (principal), cosa (azione), quando (timestamp), da dove (IP sorgente), su cosa (risorsa) e con quale risultato (successo/fallimento).

**Tipi di eventi:**
- **Management Events (default ON):** operazioni di controllo (CreateBucket, RunInstances, DeleteUser)
- **Data Events (opzionale, costo aggiuntivo):** operazioni sui dati (S3 GetObject/PutObject, Lambda Invoke, DynamoDB PutItem)
- **Insights Events:** anomalie nel pattern di API calls (picchi di utilizzo insoliti)

```bash
# Creare un trail multi-Region
aws cloudtrail create-trail \
  --name "my-audit-trail" \
  --s3-bucket-name "my-cloudtrail-bucket" \
  --is-multi-region-trail \
  --include-global-service-events \
  --enable-log-file-validation \
  --kms-key-id alias/cloudtrail-key

# Abilitare il trail
aws cloudtrail start-logging --name "my-audit-trail"

# Aggiungere Data Events (S3)
aws cloudtrail put-event-selectors \
  --trail-name "my-audit-trail" \
  --event-selectors '[{
    "ReadWriteType": "All",
    "IncludeManagementEvents": true,
    "DataResources": [
      {
        "Type": "AWS::S3::Object",
        "Values": ["arn:aws:s3:::my-sensitive-bucket/"]
      },
      {
        "Type": "AWS::Lambda::Function",
        "Values": ["arn:aws:lambda"]
      },
      {
        "Type": "AWS::DynamoDB::Table",
        "Values": ["arn:aws:dynamodb"]
      }
    ]
  }]'

# Abilitare CloudTrail Insights
aws cloudtrail put-insight-selectors \
  --trail-name "my-audit-trail" \
  --insight-selectors '[
    {"InsightType": "ApiCallRateInsight"},
    {"InsightType": "ApiErrorRateInsight"}
  ]'
```

### Cercare Events in CloudTrail

```bash
# Cercare eventi degli ultimi 90 giorni (CloudTrail Event History)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteBucket \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-31T23:59:59Z"

# Cercare tutte le azioni di un utente specifico
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=alice \
  --max-results 50

# Cercare azioni su una risorsa specifica
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=my-bucket
```

### CloudTrail Lake

CloudTrail Lake permette di eseguire query SQL direttamente sui log CloudTrail senza doverli esportare. Retention fino a 7 anni.

```bash
# Creare un Event Data Store
aws cloudtrail create-event-data-store \
  --name "MyAuditLake" \
  --retention-period 2555 \
  --multi-region-enabled \
  --organization-enabled \
  --kms-key-id alias/cloudtrail-key \
  --advanced-event-selectors '[{
    "Name": "All events",
    "FieldSelectors": [
      {"Field": "eventCategory", "Equals": ["Management"]}
    ]
  }]'

# Query SQL su CloudTrail Lake
aws cloudtrail start-query \
  --query-statement "
    SELECT
      eventTime,
      eventName,
      userIdentity.arn,
      sourceIPAddress,
      errorCode
    FROM my-event-data-store-id
    WHERE
      eventName IN ('DeleteBucket', 'DeleteTable', 'TerminateInstances')
      AND eventTime > '2024-01-01 00:00:00'
    ORDER BY eventTime DESC
    LIMIT 100
  "

# Ottenere risultati della query
aws cloudtrail get-query-results \
  --event-data-store arn:aws:cloudtrail:us-east-1:123456789012:eventdatastore/abc123 \
  --query-id query-id-here
```

### Log Validation e Integrità

CloudTrail può validare l'integrità dei log file usando digest files firmati digitalmente con SHA-256. Questo permette di verificare che i log non siano stati alterati.

```bash
# Abilitare log validation (alla creazione o dopo)
aws cloudtrail update-trail \
  --name "my-audit-trail" \
  --enable-log-file-validation

# Validare l'integrità dei log (usando AWS CLI)
aws cloudtrail validate-logs \
  --trail-arn arn:aws:cloudtrail:us-east-1:123456789012:trail/my-audit-trail \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-31T23:59:59Z" \
  --verbose
```

### Integrazione CloudTrail con CloudWatch Logs

```bash
# Inviare i log CloudTrail a CloudWatch Logs per alerting in real-time
aws cloudtrail update-trail \
  --name "my-audit-trail" \
  --cloud-watch-logs-log-group-arn arn:aws:logs:us-east-1:123456789012:log-group:CloudTrailLogs \
  --cloud-watch-logs-role-arn arn:aws:iam::123456789012:role/CloudTrail-CloudWatch-Role

# Creare un metric filter per "root account login"
aws logs put-metric-filter \
  --log-group-name "CloudTrailLogs" \
  --filter-name "RootAccountUsage" \
  --filter-pattern '{ $.userIdentity.type = "Root" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != "AwsServiceEvent" }' \
  --metric-transformations '[{
    "metricName": "RootAccountUsageCount",
    "metricNamespace": "CloudTrailMetrics",
    "metricValue": "1"
  }]'

# Alarm su root login
aws cloudwatch put-metric-alarm \
  --alarm-name "RootAccountLogin" \
  --alarm-description "Root account ha eseguito un API call" \
  --metric-name "RootAccountUsageCount" \
  --namespace "CloudTrailMetrics" \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:security-critical-alerts
```

---

## Best Practices

### Strategia di Sicurezza Multi-Layer

```
Abilita sempre (Day 1):
  ✓ CloudTrail multi-region con log validation
  ✓ GuardDuty in tutti gli account e Region
  ✓ AWS Config con le regole base
  ✓ Security Hub con FSBP standard

Configura nel primo mese:
  ✓ Inspector v2 per EC2 + ECR + Lambda
  ✓ Macie per bucket S3 sensibili
  ✓ Config Remediations per i finding più critici
  ✓ CloudTrail Lake per query avanzate

Automatizza:
  ✓ EventBridge rules per GuardDuty high/critical findings → Lambda remediation
  ✓ Security Hub → ServiceNow/Jira per incident tracking
  ✓ Config non-compliant resources → notifica + remediation automatica
```

### CIS Benchmark AWS — Controlli Essenziali

1. Root account: MFA abilitato, nessun access key
2. IAM: MFA per tutti gli utenti con console access
3. CloudTrail: abilitato in tutte le Region con log validation
4. Config: recorder abilitato
5. Monitoring: alarm su root login, console login senza MFA, unauthorized API calls
6. Networking: VPC Flow Logs abilitati, nessun SG con 0.0.0.0/0 su porta 22/3389
7. S3: Block Public Access a livello account

---

## Troubleshooting

### GuardDuty: Troppi Falsi Positivi

```bash
# Sopprimere finding specifici (supression rules)
aws guardduty create-filter \
  --detector-id $DETECTOR_ID \
  --name "SuppressNATGatewayFindings" \
  --action ARCHIVE \
  --finding-criteria '{
    "Criterion": {
      "type": {
        "Equals": ["Recon:EC2/PortProbeUnprotectedPort"]
      },
      "resource.instanceDetails.tags.key": {
        "Equals": ["Role"]
      },
      "resource.instanceDetails.tags.value": {
        "Equals": ["nat-gateway"]
      }
    }
  }'
```

### Config: Stato "Not Applicable" per Regole Managed

Alcune regole managed Config si applicano solo a specifici tipi di risorsa. "Not Applicable" significa che non esistono risorse di quel tipo nell'account/Region, non che c'è una violazione.

### CloudTrail: Log Non Consegnati in S3

1. Verificare la bucket policy (CloudTrail deve poter scrivere nel bucket)
2. Verificare che il bucket esista e sia nella stessa Region del trail
3. Controllare i CloudTrail service events per errori di delivery

```bash
# Verificare la bucket policy per CloudTrail
aws cloudtrail get-trail-status --name "my-audit-trail" \
  --query '[LatestDeliveryError, LatestDeliveryTime]'
```

---

## Relazioni

??? info "CloudWatch — Log e Metriche"
    CloudTrail può inviare log a CloudWatch Logs per alerting in real-time. GuardDuty pubblica metriche su CloudWatch.

    **Approfondimento completo →** [CloudWatch](../monitoring/cloudwatch.md)

??? info "KMS — Encryption dei Log"
    CloudTrail, Config, Security Hub e altri possono cifrare i propri dati con KMS CMK.

    **Approfondimento completo →** [KMS e Secrets Manager](kms-secrets.md)

??? info "EventBridge — Automazione"
    GuardDuty, Inspector, Macie, Security Hub e Config inviano eventi a EventBridge per automazione e integrazione.

    **Approfondimento completo →** [EventBridge e Kinesis](../messaging/eventbridge-kinesis.md)

---

## Riferimenti

- [GuardDuty Documentation](https://docs.aws.amazon.com/guardduty/)
- [Inspector v2 Documentation](https://docs.aws.amazon.com/inspector/)
- [Macie Documentation](https://docs.aws.amazon.com/macie/)
- [Security Hub Documentation](https://docs.aws.amazon.com/securityhub/)
- [AWS Config Documentation](https://docs.aws.amazon.com/config/)
- [CloudTrail Documentation](https://docs.aws.amazon.com/cloudtrail/)
- [CloudTrail Lake](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html)
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)
- [AWS Security Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/)
