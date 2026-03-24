---
title: "Pulumi — Fondamentali"
slug: fondamentali
category: iac
tags: [pulumi, iac, infrastructure-as-code, python, typescript, go, dotnet, cloud]
search_keywords: [pulumi, infrastructure as code, iac, python iac, typescript iac, go iac, pulumi vs terraform, pulumi stack, pulumi project, sdk iac, programmatic iac, real language iac, pulumi cloud, pulumi state, crosswalk, component resources, automation api]
parent: iac/pulumi/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management, iac/terraform/moduli, iac/ansible/fondamentali]
official_docs: https://www.pulumi.com/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Pulumi — Fondamentali

## Panoramica

Pulumi è un framework IaC (Infrastructure as Code) che permette di definire l'infrastruttura cloud usando **linguaggi di programmazione reali**: Python, TypeScript/JavaScript, Go, C#, Java e YAML. A differenza di Terraform (che usa HCL, un DSL dichiarativo), Pulumi espone le risorse cloud come oggetti in codice ordinario, abilitando loop, condizioni, astrazioni, test unitari e riuso tramite librerie standard.

Pulumi è **complementare**, non sostitutivo, di Terraform: la scelta dipende dalle competenze del team e dall'approccio preferito (DSL dichiarativo vs. linguaggio general-purpose). È particolarmente indicato per platform team con forte background da developer che vogliono trattare l'infrastruttura come software.

**Quando usare Pulumi:**
- Team che preferiscono un linguaggio noto (Python, TS) a HCL
- Infrastruttura con logica condizionale complessa, loop, o dati calcolati
- Necessità di testare l'infrastruttura con unit test standard
- Integrazione diretta con SDK cloud (boto3, SDK Azure) nella stessa codebase
- Creazione di librerie IaC riusabili e pubblicabili su npm/PyPI

**Quando NON usare Pulumi (preferire Terraform):**
- Team con consolidata esperienza HCL e ampio Terraform Registry già utilizzato
- Organizzazioni con governance centralizzata su Terraform Cloud/Enterprise
- Necessità di leggere infrastruttura esistente via `terraform import` senza refactoring

---

## Concetti Chiave

### Project
Un **Project** è la radice di un programma Pulumi, definito dal file `Pulumi.yaml`. Contiene il nome del progetto, il runtime (python, nodejs, go, dotnet) e la descrizione. Un progetto corrisponde tipicamente a un repository o a un sotto-directory.

```yaml
# Pulumi.yaml
name: my-infra
runtime: python
description: Infrastruttura applicazione produzione
```

### Stack
Uno **Stack** è un'istanza isolata del progetto, con il proprio state e configurazione. Il pattern standard è avere uno stack per ambiente:

```
my-infra/
  stack: dev     → state separato, config separata
  stack: staging → state separato, config separata
  stack: prod    → state separato, config separata
```

Un singolo stack corrisponde concettualmente a un Terraform workspace. La configurazione è separata per stack via `pulumi config set`.

### Resources
Le **Resources** sono gli oggetti cloud che Pulumi gestisce. Ogni provider espone risorse come classi nel linguaggio target:

```python
import pulumi_aws as aws

bucket = aws.s3.Bucket("my-bucket",
    acl="private",
    versioning=aws.s3.BucketVersioningArgs(enabled=True),
    tags={"Environment": "prod"}
)
```

### Outputs
Gli **Output** sono valori che dipendono dall'esecuzione (es. ARN, IP, URL). In Pulumi sono oggetti `Output[T]` — wrapped values che si risolvono solo dopo l'`apply`. Non sono stringhe normali: vanno usati con `pulumi.Output.all()` o `.apply()`.

```python
# Corretto: usare .apply() per trasformare un Output
bucket_url = bucket.website_endpoint.apply(
    lambda endpoint: f"https://{endpoint}"
)

# Esportare un output verso altri stack o CLI
pulumi.export("bucket_url", bucket_url)
```

### Config e Secrets
La **Config** è separata per stack. I secrets sono cifrati a riposo nel backend (Pulumi Cloud o KMS custom).

```bash
pulumi config set db_host mydb.example.com
pulumi config set --secret db_password supersecret
```

```python
config = pulumi.Config()
db_host = config.require("db_host")
db_password = config.require_secret("db_password")  # Output[str] cifrato
```

### Provider
I **Provider** sono plugin che gestiscono le API cloud. Si installano tramite pip/npm/go get e si configurano con credenziali standard (env vars, profili AWS, etc.) o via costruttore esplicito.

```bash
# Python
pip install pulumi-aws pulumi-kubernetes pulumi-gcp

# TypeScript/Node
npm install @pulumi/aws @pulumi/kubernetes
```

---

## Architettura / Come Funziona

### Pulumi Engine e State

```
Developer
    │
    ▼
pulumi up / preview
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Pulumi CLI                                     │
│  1. Esegue il programma utente (python/ts/go)   │
│  2. Intercetta le chiamate new Resource(...)     │
│  3. Costruisce il "desired state" graph          │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│  Engine — Diff & Reconcile                      │
│  Confronta desired state con state corrente     │
│  Genera piano: create / update / delete / same  │
└──────────────┬──────────────────────────────────┘
               │
     ┌─────────┴──────────┐
     ▼                    ▼
 Provider               State Backend
 (AWS, GCP, K8s...)     (Pulumi Cloud / S3 / Azure Blob / GCS)
 Chiama le API          Persiste lo stato dello stack
```

Il programma utente viene eseguito ogni volta che si fa `pulumi up` o `pulumi preview`. Non è un template: è codice reale che genera il grafo delle risorse. Il risultato viene confrontato con lo stato precedente (nel backend) per calcolare il diff.

### Backend di Stato
Pulumi supporta più backend per lo stato:

| Backend | Comando setup | Adatto per |
|---|---|---|
| Pulumi Cloud (default) | Account gratuito su app.pulumi.com | Team piccoli, collaborazione immediata |
| AWS S3 | `pulumi login s3://bucket-name` | Self-hosted, team con AWS |
| Azure Blob Storage | `pulumi login azblob://container` | Self-hosted, team con Azure |
| GCS | `pulumi login gs://bucket-name` | Self-hosted, team con GCP |
| Filesystem locale | `pulumi login file://~/.pulumi` | Sviluppo locale, test |

```bash
# Login su backend S3
pulumi login s3://my-pulumi-state-bucket

# Login su Pulumi Cloud (default)
pulumi login
```

### Component Resources
Le **Component Resources** sono astrazioni riusabili che raggruppano più risorse primitive. Sono l'equivalente dei moduli Terraform, ma scritte in codice:

```python
from pulumi import ComponentResource, ResourceOptions

class VpcWithSubnets(ComponentResource):
    def __init__(self, name: str, cidr: str, opts=None):
        super().__init__("myorg:network:VpcWithSubnets", name, {}, opts)

        self.vpc = aws.ec2.Vpc(f"{name}-vpc",
            cidr_block=cidr,
            opts=ResourceOptions(parent=self)
        )

        self.public_subnet = aws.ec2.Subnet(f"{name}-public",
            vpc_id=self.vpc.id,
            cidr_block="10.0.1.0/24",
            opts=ResourceOptions(parent=self)
        )

        self.register_outputs({"vpc_id": self.vpc.id})

# Utilizzo
network = VpcWithSubnets("production", cidr="10.0.0.0/16")
```

---

## Configurazione & Pratica

### Installazione e Setup

```bash
# Installare Pulumi CLI
# Windows (winget)
winget install pulumi

# macOS
brew install pulumi/tap/pulumi

# Linux
curl -fsSL https://get.pulumi.com | sh

# Verificare installazione
pulumi version
```

### Creare un Nuovo Progetto

```bash
# Progetto Python da template AWS
pulumi new aws-python

# Progetto TypeScript da template GCP
pulumi new gcp-typescript

# Progetto Go da template Azure
pulumi new azure-go

# Progetto da zero
pulumi new python --name my-infra --stack dev
```

### Workflow Operativo

```bash
# Vedere il piano (dry-run) — equivalente terraform plan
pulumi preview

# Applicare le modifiche — equivalente terraform apply
pulumi up

# Distruggere l'infrastruttura — equivalente terraform destroy
pulumi destroy

# Visualizzare lo stato corrente
pulumi stack --show-urns

# Visualizzare gli output dello stack
pulumi stack output

# Elencare gli stack
pulumi stack ls
```

### Esempio Completo — Python (AWS ECS Fargate)

```python
# __main__.py
import pulumi
import pulumi_aws as aws

# Config
config = pulumi.Config()
app_name = config.get("app_name") or "myapp"
container_port = config.get_int("container_port") or 8080
cpu = config.get_int("cpu") or 256
memory = config.get_int("memory") or 512

# VPC e Subnet (usando VPC default per semplicità)
default_vpc = aws.ec2.get_vpc(default=True)
default_subnets = aws.ec2.get_subnets(filters=[{
    "name": "vpc-id",
    "values": [default_vpc.id]
}])

# Security Group
sg = aws.ec2.SecurityGroup(f"{app_name}-sg",
    vpc_id=default_vpc.id,
    ingress=[{
        "protocol": "tcp",
        "from_port": container_port,
        "to_port": container_port,
        "cidr_blocks": ["0.0.0.0/0"]
    }],
    egress=[{
        "protocol": "-1",
        "from_port": 0,
        "to_port": 0,
        "cidr_blocks": ["0.0.0.0/0"]
    }]
)

# ECS Cluster
cluster = aws.ecs.Cluster(f"{app_name}-cluster")

# Task Definition
task_definition = aws.ecs.TaskDefinition(f"{app_name}-task",
    family=app_name,
    cpu=str(cpu),
    memory=str(memory),
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    container_definitions=pulumi.Output.json_dumps([{
        "name": app_name,
        "image": "nginx:latest",
        "portMappings": [{"containerPort": container_port}]
    }])
)

# ECS Service
service = aws.ecs.Service(f"{app_name}-service",
    cluster=cluster.arn,
    desired_count=2,
    launch_type="FARGATE",
    task_definition=task_definition.arn,
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=default_subnets.ids,
        security_groups=[sg.id],
        assign_public_ip=True
    )
)

pulumi.export("cluster_name", cluster.name)
pulumi.export("service_name", service.name)
```

### Esempio — TypeScript (Kubernetes Deployment)

```typescript
// index.ts
import * as pulumi from "@pulumi/pulumi";
import * as k8s from "@pulumi/kubernetes";

const config = new pulumi.Config();
const replicas = config.getNumber("replicas") ?? 2;
const image = config.get("image") ?? "nginx:1.25";

const appLabels = { app: "webserver" };

const deployment = new k8s.apps.v1.Deployment("webserver", {
    spec: {
        replicas: replicas,
        selector: { matchLabels: appLabels },
        template: {
            metadata: { labels: appLabels },
            spec: {
                containers: [{
                    name: "webserver",
                    image: image,
                    ports: [{ containerPort: 80 }],
                    resources: {
                        requests: { cpu: "100m", memory: "128Mi" },
                        limits: { cpu: "200m", memory: "256Mi" }
                    }
                }]
            }
        }
    }
});

const service = new k8s.core.v1.Service("webserver-svc", {
    spec: {
        selector: appLabels,
        ports: [{ port: 80, targetPort: 80 }],
        type: "ClusterIP"
    }
});

export const deploymentName = deployment.metadata.name;
export const serviceName = service.metadata.name;
```

### Stack References (Cross-Stack)

```python
# Stack "networking" esporta VPC id
pulumi.export("vpc_id", vpc.id)

# Stack "app" legge l'output di "networking"
network_stack = pulumi.StackReference("myorg/networking/prod")
vpc_id = network_stack.get_output("vpc_id")

subnet = aws.ec2.Subnet("app-subnet",
    vpc_id=vpc_id,
    cidr_block="10.0.10.0/24"
)
```

### Pulumi Automation API

L'**Automation API** permette di incorporare Pulumi in programmi Python/TypeScript come libreria, senza la CLI interattiva. Utile per pipeline CI, tool interni, o platform engineering:

```python
from pulumi.automation import create_or_select_stack, LocalWorkspace

def deploy(stack_name: str, config: dict):
    stack = create_or_select_stack(
        stack_name=stack_name,
        project_name="my-infra",
        program=pulumi_program,  # funzione Python normale
        opts=LocalWorkspaceOptions(
            env_vars={"AWS_REGION": "eu-west-1"}
        )
    )

    for key, value in config.items():
        stack.set_config(key, ConfigValue(value=value))

    result = stack.up(on_output=print)
    return result.outputs
```

---

## Best Practices

### Struttura Progetto Multi-Stack

```
infra/
├── Pulumi.yaml           # Definizione progetto
├── Pulumi.dev.yaml       # Config stack dev
├── Pulumi.staging.yaml   # Config stack staging
├── Pulumi.prod.yaml      # Config stack prod
├── __main__.py           # Entry point
├── components/           # Component resources riusabili
│   ├── __init__.py
│   ├── vpc.py
│   └── ecs_service.py
├── requirements.txt
└── tests/
    └── test_infrastructure.py
```

### Testing dell'Infrastruttura

Il vantaggio principale di Pulumi rispetto a Terraform è la possibilità di **unit test nativi**:

```python
# tests/test_infrastructure.py
import unittest
import pulumi

class TestInfrastructure(unittest.TestCase):
    @pulumi.runtime.test
    def test_bucket_is_private(self):
        """Il bucket S3 deve essere privato"""
        import __main__

        def check_bucket_acl(args):
            bucket, acl = args
            self.assertEqual(acl, "private",
                "Bucket deve essere privato, non pubblico")

        return pulumi.Output.all(
            __main__.bucket.id,
            __main__.bucket.acl
        ).apply(check_bucket_acl)
```

```bash
# Eseguire i test senza creare risorse reali
PULUMI_TEST_MODE=true python -m pytest tests/
```

### Gestione Secrets

```bash
# Usare Pulumi Cloud (default) per KMS managed
pulumi config set --secret api_key mykey123

# Usare AWS KMS come provider di cifratura
pulumi stack change-secrets-provider "awskms://alias/pulumi-stack-key"

# Usare una passphrase locale (no KMS)
export PULUMI_CONFIG_PASSPHRASE="my-passphrase"
pulumi config set --secret api_key mykey123
```

### Naming e Tagging

```python
# Pattern: usare il nome dello stack come prefix
stack = pulumi.get_stack()
project = pulumi.get_project()

common_tags = {
    "ManagedBy": "pulumi",
    "Stack": stack,
    "Project": project,
}

resource = aws.ec2.Instance("web",
    # ...
    tags={**common_tags, "Name": f"{stack}-web-server"}
)
```

### Import di Risorse Esistenti

```python
# Importare una risorsa esistente (creata fuori da Pulumi)
existing_bucket = aws.s3.Bucket("existing-bucket",
    bucket="my-existing-bucket-name",
    opts=pulumi.ResourceOptions(import_="my-existing-bucket-name")
)
```

```bash
# Equivalente via CLI
pulumi import aws:s3/bucket:Bucket existing-bucket my-existing-bucket-name
```

### Anti-Pattern da Evitare

| Anti-pattern | Problema | Soluzione |
|---|---|---|
| Credenziali hardcoded nel codice | Leak nei repository | Usare `pulumi.Config().require_secret()` |
| Un unico stack per tutti gli ambienti | Nessun isolamento, rollback impossibile | Stack separato per dev/staging/prod |
| `pulumi up --yes` in CI senza preview | Cambiamenti inattesi applicati senza revisione | `pulumi preview --diff` poi `pulumi up` separati |
| Output tipizzati come stringhe normali | Errori runtime, dipendenze non tracciate | Usare `pulumi.Output.all()` e `.apply()` |
| Logica complessa nel top-level | Difficile da testare e riusare | Estrarre Component Resources |

---

## Troubleshooting

### `pulumi up` fallisce con "resource already exists"
La risorsa esiste nel cloud ma non nello state Pulumi. Soluzione: importarla.
```bash
pulumi import <resource-type> <logical-name> <cloud-id>
```

### State corrotto o inconsistente
```bash
# Visualizzare lo state raw
pulumi stack export > state-backup.json

# Modificare manualmente e reimportare
pulumi stack import < state-fixed.json

# Rimuovere una risorsa dallo state (senza distruggerla nel cloud)
pulumi state delete <urn>
```

### Output non disponibile (`Output<None>`)
Tipicamente causato da un `apply()` che ritorna `None` implicito:
```python
# ERRATO — ritorna None
url = endpoint.apply(lambda e: print(f"https://{e}"))

# CORRETTO — ritorna la stringa
url = endpoint.apply(lambda e: f"https://{e}")
```

### Provider non autenticato
```bash
# AWS — verificare credenziali
aws sts get-caller-identity

# GCP — autenticare application default
gcloud auth application-default login

# Azure — login
az login
```

### `pulumi refresh` — Allineare State con Realtà
Se risorse sono state modificate fuori da Pulumi (manualmente nel cloud):
```bash
# Aggiorna lo state leggendo lo stato attuale dal cloud
pulumi refresh

# Poi applicare per riportare al desired state
pulumi up
```

---

## Relazioni

??? info "Terraform — Alternativa Dichiarativa"
    Terraform usa HCL, un DSL dichiarativo, al posto di linguaggi general-purpose. La scelta è principalmente culturale: HCL è più accessibile a chi non ha background da developer; Pulumi è più potente per chi vuole logica e test. Lo state management è concettualmente identico.

    **Approfondimento →** [Terraform Fondamentali](../terraform/fondamentali.md)

??? info "Terraform State Management — Confronto Backend"
    Pulumi e Terraform hanno lo stesso problema di state: condivisione in team, locking, cifratura. Le soluzioni sono analoghe (S3+DynamoDB per Terraform, S3 per Pulumi). Pulumi Cloud gestisce anche il locking nativo.

    **Approfondimento →** [Terraform State Management](../terraform/state-management.md)

??? info "Ansible — Configuration Management Post-Provisioning"
    Pulumi e Terraform provisionano l'infrastruttura (VM, network, storage). Ansible configura il software su quella infrastruttura. Il pattern classico è: Pulumi/Terraform → VM → Ansible → software configurato.

    **Approfondimento →** [Ansible Fondamentali](../ansible/fondamentali.md)

---

## Riferimenti

- [Documentazione ufficiale Pulumi](https://www.pulumi.com/docs/)
- [Pulumi Registry — Provider e componenti](https://www.pulumi.com/registry/)
- [Pulumi Examples (GitHub)](https://github.com/pulumi/examples)
- [Pulumi AI — Generazione codice IaC con AI](https://www.pulumi.com/ai/)
- [Pulumi Automation API](https://www.pulumi.com/docs/using-pulumi/automation-api/)
- [Testing Pulumi Programs](https://www.pulumi.com/docs/using-pulumi/testing/)
