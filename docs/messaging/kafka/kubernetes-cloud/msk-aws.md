---
title: "Amazon MSK (Managed Streaming for Apache Kafka)"
slug: msk-aws
category: messaging
tags: [kafka, aws, msk, managed, cloud, amazon]
search_keywords: [amazon msk, managed kafka aws, msk provisioned, msk serverless, kafka aws, msk terraform, msk iam auth, msk connect, msk cloudwatch]
parent: messaging/kafka/kubernetes-cloud
related: [messaging/kafka/sicurezza/ssl-tls, messaging/kafka/operazioni/monitoring, messaging/kafka/kubernetes-cloud/strimzi-operator]
official_docs: https://docs.aws.amazon.com/msk/latest/developerguide/
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# Amazon MSK (Managed Streaming for Apache Kafka)

## Panoramica

Amazon MSK (Managed Streaming for Apache Kafka) è il servizio AWS fully managed per Apache Kafka che elimina l'overhead operativo di gestione dei broker, dello storage, dei patch e della disponibilità. AWS si occupa del provisioning dell'infrastruttura, della sostituzione dei broker in fault, degli aggiornamenti di sicurezza e del backup automatico. MSK offre due modalità: **MSK Provisioned** per workload stabili e prevedibili con cluster dedicati, e **MSK Serverless** per workload intermittenti con pricing pay-per-use senza gestione della capacità. MSK è integrato nativamente con l'ecosistema AWS: IAM per autenticazione, VPC per isolamento di rete, CloudWatch per monitoraggio, Secrets Manager per credenziali SCRAM, e MSK Connect per i connector Kafka Connect gestiti. La piena compatibilità con l'API Kafka standard permette di usare qualsiasi client Kafka esistente senza modifiche.

!!! note "Versioni Kafka supportate"
    MSK supporta le versioni LTS di Kafka. Verificare sempre la [compatibility matrix](https://docs.aws.amazon.com/msk/latest/developerguide/supported-kafka-versions.html) prima di pianificare un upgrade. MSK non supporta KRaft in modalità Provisioned (usa ancora ZooKeeper internamente).

---

## Concetti Chiave

### MSK Provisioned vs MSK Serverless

| Caratteristica | MSK Provisioned | MSK Serverless |
|----------------|----------------|----------------|
| **Capacità** | Definita (broker type + count) | Automatica |
| **Pricing** | Orario per broker | Per GB in/out e storage |
| **Kafka Version** | Scelta dall'utente | Gestita da AWS |
| **Configurazione** | Piena flessibilità | Limitata |
| **Performance** | Prevedibile | Variabile |
| **Use case** | Produzione, workload stabili | Dev, workload intermittenti |

### Tipi di Broker (MSK Provisioned)

| Tipo | vCPU | RAM | Network |
|------|------|-----|---------|
| `kafka.t3.small` | 2 | 2 GB | Bassa (dev only) |
| `kafka.m5.large` | 2 | 8 GB | Fino a 10 Gbps |
| `kafka.m5.xlarge` | 4 | 16 GB | Fino a 10 Gbps |
| `kafka.m5.2xlarge` | 8 | 32 GB | Fino a 10 Gbps |
| `kafka.m5.4xlarge` | 16 | 64 GB | Fino a 10 Gbps |

### Autenticazione

MSK supporta tre metodi di autenticazione:
1. **IAM Authentication (sigv4)**: Autenticazione tramite IAM role/user, consigliata per client AWS-native
2. **TLS mutual authentication**: Certificati client firmati da una CA privata (ACM PCA)
3. **SASL/SCRAM**: Username e password gestite tramite AWS Secrets Manager

---

## Architettura / Come Funziona

```
┌─────────────────────────────────────────────────────────────┐
│                          VPC AWS                            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 MSK Cluster (Multi-AZ)               │   │
│  │                                                      │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐         │   │
│  │  │ Broker 1 │   │ Broker 2 │   │ Broker 3 │         │   │
│  │  │  (AZ-a)  │   │  (AZ-b)  │   │  (AZ-c)  │         │   │
│  │  └────┬─────┘   └────┬─────┘   └────┬─────┘         │   │
│  │       │              │              │                │   │
│  │       └──────────────┼──────────────┘                │   │
│  │                      │                               │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │ ZooKeeper (3 nodi, gestiti da AWS, nascosti) │    │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────────────────┐   │
│  │  ECS/EKS         │    │  Lambda / EC2 Producers       │   │
│  │  Consumer Apps   │    │  Consumer Apps                │   │
│  └────────┬─────────┘    └──────────────┬───────────────┘   │
│           │                             │                   │
│           └─────────────────────────────┘                   │
│                         │                                   │
│               Security Group MSK                            │
│               Port 9092 (Plain), 9094 (TLS), 9096 (IAM)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Configurazione & Pratica

### Terraform — Creazione Cluster MSK Completo

```hcl
# variables.tf
variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "kafka_version" {
  type    = string
  default = "3.6.0"
}

# security-groups.tf
resource "aws_security_group" "msk_sg" {
  name        = "msk-production-sg"
  description = "Security group per MSK cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 9092
    to_port         = 9096
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
    description     = "Kafka client access"
  }

  ingress {
    from_port = 2181
    to_port   = 2181
    protocol  = "tcp"
    self      = true
    description = "ZooKeeper internal"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "msk-production-sg"
    Environment = "production"
  }
}

# msk.tf
resource "aws_msk_configuration" "production" {
  kafka_versions = [var.kafka_version]
  name           = "msk-production-config"

  server_properties = <<PROPERTIES
auto.create.topics.enable=false
default.replication.factor=3
min.insync.replicas=2
offsets.topic.replication.factor=3
transaction.state.log.replication.factor=3
transaction.state.log.min.isr=2
log.retention.hours=168
log.segment.bytes=1073741824
compression.type=lz4
message.max.bytes=10485760
replica.fetch.max.bytes=10485760
PROPERTIES
}

resource "aws_msk_cluster" "production" {
  cluster_name           = "msk-production"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = 3

  broker_node_group_info {
    instance_type  = "kafka.m5.xlarge"
    client_subnets = var.private_subnet_ids
    storage_info {
      ebs_storage_info {
        volume_size = 1000  # GB per broker
        provisioned_throughput {
          enabled           = true
          volume_throughput = 250  # MiB/s
        }
      }
    }
    security_groups = [aws_security_group.msk_sg.id]
  }

  configuration_info {
    arn      = aws_msk_configuration.production.arn
    revision = aws_msk_configuration.production.latest_revision
  }

  client_authentication {
    sasl {
      iam   = true   # IAM authentication abilitata
      scram = true   # SASL/SCRAM abilitata
    }
    tls {
      certificate_authority_arns = []  # Aggiungere ACM PCA ARN se serve mTLS
    }
    unauthenticated = false  # Disabilita accesso non autenticato
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"           # Obbliga TLS tra client e broker
      in_cluster    = true            # TLS anche tra broker
    }
    encryption_at_rest {
      data_volume_kms_key_id = aws_kms_key.msk.arn
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk_brokers.name
      }
      s3 {
        enabled = true
        bucket  = aws_s3_bucket.msk_logs.bucket
        prefix  = "msk-broker-logs/"
      }
    }
  }

  tags = {
    Environment = "production"
    Team        = "platform"
  }
}

# KMS key per encryption at rest
resource "aws_kms_key" "msk" {
  description             = "KMS key per MSK cluster"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

# CloudWatch log group
resource "aws_cloudwatch_log_group" "msk_brokers" {
  name              = "/aws/msk/production/brokers"
  retention_in_days = 30
}

# Output utili
output "bootstrap_brokers_iam" {
  description = "Bootstrap brokers per IAM authentication"
  value       = aws_msk_cluster.production.bootstrap_brokers_sasl_iam
}

output "bootstrap_brokers_scram" {
  description = "Bootstrap brokers per SASL/SCRAM"
  value       = aws_msk_cluster.production.bootstrap_brokers_sasl_scram
}

output "bootstrap_brokers_tls" {
  description = "Bootstrap brokers per TLS"
  value       = aws_msk_cluster.production.bootstrap_brokers_tls
}
```

### IAM Policy per client MSK (IAM Authentication)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:Connect",
        "kafka-cluster:DescribeCluster"
      ],
      "Resource": "arn:aws:kafka:eu-west-1:123456789:cluster/msk-production/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:ReadData",
        "kafka-cluster:DescribeTopic"
      ],
      "Resource": "arn:aws:kafka:eu-west-1:123456789:topic/msk-production/*/ordini-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:WriteData",
        "kafka-cluster:DescribeTopic",
        "kafka-cluster:CreateTopic"
      ],
      "Resource": "arn:aws:kafka:eu-west-1:123456789:topic/msk-production/*/ordini-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kafka-cluster:AlterGroup",
        "kafka-cluster:DescribeGroup"
      ],
      "Resource": "arn:aws:kafka:eu-west-1:123456789:group/msk-production/*/order-service-*"
    }
  ]
}
```

### Configurazione Client con IAM Authentication

```properties
# client.properties per IAM authentication
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
```

```xml
<!-- Dipendenza Maven per IAM auth -->
<dependency>
    <groupId>software.amazon.msk</groupId>
    <artifactId>aws-msk-iam-auth</artifactId>
    <version>2.1.1</version>
</dependency>
```

### MSK Connect — Kafka Connect Gestito

```bash
# Crea un connector S3 Sink tramite AWS CLI
aws kafkaconnect create-connector \
  --connector-name "s3-sink-ordini" \
  --connector-configuration '{
    "connector.class": "io.confluent.connect.s3.S3SinkConnector",
    "tasks.max": "4",
    "topics": "ordini-v1",
    "s3.region": "eu-west-1",
    "s3.bucket.name": "my-kafka-sink-bucket",
    "s3.part.size": "67108864",
    "flush.size": "1000",
    "storage.class": "io.confluent.connect.s3.storage.S3Storage",
    "format.class": "io.confluent.connect.s3.format.avro.AvroFormat",
    "schema.compatibility": "FULL",
    "locale": "en_US"
  }' \
  --kafka-cluster '{
    "apacheKafkaCluster": {
      "bootstrapServers": "b-1.msk-production...:9098,b-2...:9098",
      "vpc": {
        "subnetIds": ["subnet-abc123", "subnet-def456"],
        "securityGroups": ["sg-xyz789"]
      }
    }
  }' \
  --kafka-cluster-client-authentication '{"authenticationType": "IAM"}' \
  --kafka-cluster-encryption-in-transit '{"encryptionType": "TLS"}' \
  --capacity '{
    "provisionedCapacity": {"mcuCount": 2, "workerCount": 2}
  }' \
  --plugins '[{"customPlugin": {"customPluginArn": "arn:aws:kafkaconnect:...", "revision": 1}}]' \
  --service-execution-role-arn "arn:aws:iam::123456789:role/MSKConnectRole"
```

### CloudWatch Dashboard — Metriche Chiave

```python
# Script Python per creare una CloudWatch Dashboard per MSK
import boto3
import json

client = boto3.client('cloudwatch', region_name='eu-west-1')

dashboard_body = {
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "title": "Bytes In Per Broker",
                "metrics": [
                    ["AWS/Kafka", "BytesInPerSec", "Cluster Name", "msk-production",
                     "Broker ID", "1"],
                    ["AWS/Kafka", "BytesInPerSec", "Cluster Name", "msk-production",
                     "Broker ID", "2"],
                    ["AWS/Kafka", "BytesInPerSec", "Cluster Name", "msk-production",
                     "Broker ID", "3"]
                ],
                "period": 60,
                "stat": "Average",
                "view": "timeSeries"
            }
        },
        {
            "type": "metric",
            "properties": {
                "title": "Consumer Lag",
                "metrics": [
                    ["AWS/Kafka", "EstimatedTimeLag",
                     "Cluster Name", "msk-production",
                     "Consumer Group", "order-service-group",
                     "Topic", "ordini-v1"]
                ],
                "period": 60,
                "stat": "Maximum",
                "view": "timeSeries"
            }
        },
        {
            "type": "metric",
            "properties": {
                "title": "Under Replicated Partitions",
                "metrics": [
                    ["AWS/Kafka", "UnderReplicatedPartitions",
                     "Cluster Name", "msk-production", "Broker ID", "1"],
                    ["AWS/Kafka", "UnderReplicatedPartitions",
                     "Cluster Name", "msk-production", "Broker ID", "2"],
                    ["AWS/Kafka", "UnderReplicatedPartitions",
                     "Cluster Name", "msk-production", "Broker ID", "3"]
                ],
                "period": 60,
                "stat": "Sum",
                "view": "timeSeries"
            }
        },
        {
            "type": "metric",
            "properties": {
                "title": "Storage Utilization",
                "metrics": [
                    ["AWS/Kafka", "KafkaDataLogsDiskUsed",
                     "Cluster Name", "msk-production", "Broker ID", "1"]
                ],
                "period": 300,
                "stat": "Average",
                "view": "timeSeries"
            }
        }
    ]
}

client.put_dashboard(
    DashboardName='MSK-Production',
    DashboardBody=json.dumps(dashboard_body)
)
```

---

## Best Practices

- **Multi-AZ obbligatorio**: Distribuire i broker su almeno 3 Availability Zone. MSK lo gestisce automaticamente specificando 3 subnet in AZ diverse.
- **Disabilitare `auto.create.topics`**: Gestire i topic tramite IaC (Terraform provider `aws_msk_topic` non esiste — usare scripts con `kafka-topics.sh` o provider community).
- **IAM Authentication come default**: Preferire IAM auth per applicazioni su AWS. Evita la gestione di credenziali e sfrutta i meccanismi di autorizzazione IAM.
- **Encryption ovunque**: `client_broker = "TLS"` e `in_cluster = true` obbligatori. Non lasciare traffico Kafka in chiaro su AWS.
- **Provisioned Throughput**: Per volumi elevati (>100 MB/s per broker) abilitare Provisioned Throughput per storage EBS con prestazioni garantite.
- **Monitoraggio Consumer Lag**: Configurare allarmi CloudWatch su `EstimatedTimeLag` e `SumOffsetLag` per ogni consumer group critico.
- **Tagging sistematico**: Tag `Environment`, `Team`, `CostCenter` su ogni risorsa MSK per cost allocation e governance.

!!! warning "Limitazioni MSK vs Self-managed Kafka"
    MSK non espone l'accesso diretto ai broker via SSH. Non è possibile modificare configurazioni a livello di JVM, o installare plugin personalizzati sui broker. Le configurazioni broker disponibili sono un sottoinsieme di quelle Kafka. Per workload che richiedono configurazioni avanzate, valutare Kafka self-managed su EC2 o Kubernetes.

### Costi Indicativi (eu-west-1, febbraio 2026)

| Componente | Costo Approssimativo |
|-----------|---------------------|
| `kafka.m5.xlarge` (per broker/ora) | ~$0.23/ora |
| Storage EBS (per GB/mese) | ~$0.10/GB |
| Provisioned Throughput (per MiB/s) | ~$0.015/MiB-s |
| MSK Serverless (per GB in/out) | ~$0.10/GB |
| Data transfer (stesso AZ) | $0.00 |
| Data transfer (cross-AZ) | $0.01/GB |

Un cluster 3x `kafka.m5.xlarge` con 1TB storage per broker costa circa **$600-700/mese** escluso il traffico.

---

## Troubleshooting

### Client non riesce a connettersi al cluster MSK

```bash
# Verifica connettività al bootstrap broker
telnet b-1.msk-production.eu-west-1.amazonaws.com 9098

# Controlla il security group: le porte 9092/9094/9096/9098 devono essere aperte
aws ec2 describe-security-groups --group-ids sg-xyz789 \
  --query "SecurityGroups[0].IpPermissions"

# Verifica che il client sia nella stessa VPC o connesso tramite VPC peering
```

### Errore IAM Authentication

```bash
# Testa i permessi IAM con aws-cli
aws kafka describe-cluster \
  --cluster-arn arn:aws:kafka:eu-west-1:123456789:cluster/msk-production/...

# Verifica che il ruolo IAM abbia i permessi kafka-cluster:Connect
# L'errore più comune è il mancato permesso kafka-cluster:Connect sull'ARN del cluster
```

### Consumer Lag in aumento

```bash
# Controlla il lag dei consumer group
aws kafka list-client-vpcs \
  --cluster-arn arn:aws:kafka:...

# Usa kafka-consumer-groups.sh
kafka-consumer-groups.sh \
  --bootstrap-server b-1...:9098 \
  --command-config client.properties \
  --describe --group order-service-group
```

---

## Riferimenti

- [Amazon MSK Developer Guide](https://docs.aws.amazon.com/msk/latest/developerguide/)
- [MSK IAM Authentication Library](https://github.com/aws/aws-msk-iam-auth)
- [Terraform AWS MSK Resources](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/msk_cluster)
- [MSK Pricing](https://aws.amazon.com/msk/pricing/)
- [MSK Best Practices](https://docs.aws.amazon.com/msk/latest/developerguide/bestpractices.html)
- [MSK Connect Documentation](https://docs.aws.amazon.com/msk/latest/developerguide/msk-connect.html)
