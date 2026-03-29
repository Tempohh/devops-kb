---
title: "EC2 — Elastic Compute Cloud"
slug: ec2
category: cloud
tags: [aws, ec2, instances, ami, user-data, instance-types, pricing, placement-groups, hibernate, spot, dedicated, ebs, networking, elastic-network-adapter]
search_keywords: [AWS EC2, Elastic Compute Cloud, instance types, t3, m5, c5, r5, p3, g4, instance family, AMI, Amazon Machine Image, user data, metadata service, IMDSv2, placement group, cluster placement, spread placement, partition placement, EC2 hibernate, EC2 nitro, Graviton, ARM, Spot Instances, Reserved Instances, On-Demand, instance profile, EC2 key pair, SSH, Systems Manager Session Manager]
parent: cloud/aws/compute/_index
related: [cloud/aws/compute/ec2-autoscaling, cloud/aws/storage/ebs-efs-fsx, cloud/aws/networking/vpc, cloud/aws/iam/_index]
official_docs: https://docs.aws.amazon.com/ec2/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# EC2 — Elastic Compute Cloud

**EC2** (Elastic Compute Cloud) fornisce macchine virtuali nel cloud con pieno controllo sull'OS, sul networking e sullo storage. È il servizio IaaS (Infrastructure as a Service) fondamentale di AWS: offre la massima flessibilità, ma richiede anche la maggiore responsabilità operativa — il cliente gestisce il sistema operativo, le patch, il middleware e l'applicazione.

**Quando scegliere EC2:**
- Hai bisogno di accesso root all'OS o di configurazioni specifiche di sistema
- L'applicazione ha requisiti di stato persistente in memoria o su disco locale
- Stai eseguendo software che richiede licenze BYOL (Bring Your Own License)
- Il workload gira H24 con carico relativamente costante (EC2 On-Demand o Reserved è più economico di Lambda in questi casi)
- Hai bisogno di tipi di istanza specializzati (GPU, FPGA, alta memoria)

**Quando valutare alternative:**
- Workload event-driven o intermittente → **Lambda** (nessun server da gestire)
- Container senza voler gestire cluster → **Fargate** (serverless containers)
- Applicazione containerizzata con orchestrazione → **EKS** o **ECS**
- Database → servizi gestiti come **RDS** o **Aurora** (AWS gestisce OS e patch del DB)

---

## Instance Types e Famiglie

Le istanze EC2 sono organizzate in **famiglie** in base al workload ottimizzato.

```
Instance Type naming: m6g.2xlarge
                      │ │ │
                      │ │ └── Size (nano/micro/small/medium/large/xlarge/2xlarge...)
                      │ └──── Generation (6 = sesta generazione)
                      └────── Family (m = general purpose)

Additional characters:
  d = NVMe SSD local storage
  n = enhanced networking
  a = AMD EPYC
  g = Graviton (ARM)
  e = extra capacity
  i = Intel
  z = high frequency
```

**Famiglie principali:**

| Famiglia | Tipo | Esempi | Use case |
|----------|------|--------|----------|
| **General Purpose** | Bilanciato CPU/Mem | t3, t4g, m5, m6g, m7g | Web server, dev, app generiche |
| **Compute Optimized** | CPU alta | c5, c6g, c7g | Batch, ML inference, gaming |
| **Memory Optimized** | Molta RAM | r5, r6g, x2gd, z1d | Database in-memory, SAP, Redis |
| **Storage Optimized** | I/O locale alto | i3, i4i, d3, h1 | Database NoSQL, data warehouse |
| **Accelerated** | GPU/FPGA | p3, p4, g4dn, g5, f1 | ML training, rendering, HPC |
| **HPC** (High Performance Computing) | Networking ultra-basso | hpc6a, hpc7g | Simulazioni scientifiche |

**Graviton (ARM):** istanze `g` (m6g, c7g, r7g) — 20-40% prezzo/performance migliore vs x86 equivalente. Raccomandato per nuovi workloads.

**Burstable (T instances):** le istanze t3, t3a e t4g usano un sistema di **CPU Credits**. L'idea è che l'istanza ha una "baseline" di utilizzo CPU garantita (es. 20% per t3.small). Quando la CPU è sotto questa baseline, si accumulano crediti; quando si supera, si consumano. Questo le rende economiche per workload con utilizzo medio basso ma con spike occasionali (es. un server di sviluppo, un sito con traffico variabile). Con la modalità `unlimited`, l'istanza può fare burst illimitato anche a crediti esauriti, ma si paga il surplus — da monitorare per evitare sorprese in fattura.

---

## AMI — Amazon Machine Image

Un'**AMI** è il template da cui vengono lanciate le istanze EC2 (OS + software + configurazione).

**Tipi:**
- **AWS Managed**: Amazon Linux 2023, Ubuntu, Windows Server — mantenute da AWS
- **AWS Marketplace**: immagini di vendor terzi (Palo Alto, CentOS, Kali...)
- **Community AMI**: condivise dalla community (non supportate)
- **Custom**: create da te (dorate, con software preinstallato)

```bash
# Cercare AMI Amazon Linux 2023
aws ec2 describe-images \
    --owners amazon \
    --filters 'Name=name,Values=al2023-ami-2023.*-x86_64' \
              'Name=state,Values=available' \
    --query 'sort_by(Images, &CreationDate)[-1].{Name:Name,ImageId:ImageId}' \
    --output table

# Creare AMI da istanza esistente
aws ec2 create-image \
    --instance-id i-1234567890abcdef0 \
    --name "MyApp-AMI-$(date +%Y%m%d)" \
    --description "Golden AMI con myapp configurata" \
    --no-reboot    # crea AMI senza spegnere l'istanza (potenzialmente inconsistente)

# Copiare AMI in un'altra Region (per DR o deployment multi-region)
aws ec2 copy-image \
    --source-region eu-central-1 \
    --source-image-id ami-xxxx \
    --name "MyApp-AMI-EU-WEST-1" \
    --region eu-west-1

# Condividere AMI con un altro account
aws ec2 modify-image-attribute \
    --image-id ami-xxxx \
    --launch-permission "Add=[{UserId=999999999999}]"
```

---

## Lanciare un'Istanza EC2

```bash
# Lanciare istanza con configurazione completa
aws ec2 run-instances \
    --image-id ami-0a1b2c3d4e5f67890 \           # AMI ID
    --instance-type t3.medium \
    --key-name my-key-pair \                      # SSH key
    --security-group-ids sg-xxxx \
    --subnet-id subnet-xxxx \                     # subnet (AZ)
    --iam-instance-profile Name=MyEC2Profile \   # IAM Role
    --ebs-optimized \                             # EBS ottimizzato
    --block-device-mappings '[{
        "DeviceName": "/dev/xvda",
        "Ebs": {
            "VolumeSize": 30,
            "VolumeType": "gp3",
            "Iops": 3000,
            "Throughput": 125,
            "Encrypted": true,
            "DeleteOnTermination": true
        }
    }]' \
    --user-data file://userdata.sh \              # script eseguito al boot
    --metadata-options HttpTokens=required \      # IMDSv2 obbligatorio
    --tag-specifications 'ResourceType=instance,Tags=[
        {Key=Name,Value=my-ec2},
        {Key=Environment,Value=prod},
        {Key=Team,Value=platform}
    ]' \
    --count 1
```

---

## User Data

Lo **User Data** è uno script eseguito **una sola volta** al primo avvio dell'istanza, prima che diventi disponibile. È il meccanismo per automatizzare la configurazione iniziale: installare pacchetti, avviare servizi, scaricare il codice applicativo. Lo script gira come root, quindi ha pieno controllo sul sistema.

Un'alternativa moderna e più scalabile allo User Data è **AWS Systems Manager (SSM)**: permette di gestire la configurazione delle istanze in modo centralizzato e di eseguire comandi su flotte di istanze senza SSH. Lo User Data rimane utile per bootstrap semplici; per configurazioni complesse si preferisce SSM oppure strumenti di configuration management come Ansible o Chef.

```bash
#!/bin/bash
# userdata.sh — eseguito come root al primo boot

# Update sistema
dnf update -y

# Installare dependencies
dnf install -y docker

# Avviare e abilitare Docker
systemctl start docker
systemctl enable docker

# Aggiungere ec2-user al gruppo docker
usermod -aG docker ec2-user

# Scaricare e avviare applicazione
docker pull registry.company.com/myapp:latest
docker run -d \
    --name myapp \
    --restart unless-stopped \
    -p 80:8080 \
    -e AWS_REGION=eu-central-1 \
    registry.company.com/myapp:latest

# Log User Data
echo "User Data completato $(date)" >> /var/log/user-data.log
```

```bash
# Verificare output User Data (dal cloud-init log)
cat /var/log/cloud-init-output.log

# Recuperare User Data dall'istanza via IMDS
curl http://169.254.169.254/latest/user-data
```

---

## Instance Metadata Service (IMDS)

**IMDS** fornisce informazioni sull'istanza accessibili dall'interno (169.254.169.254 — link-local).

```bash
# IMDSv2 (obbligatorio per sicurezza — previene SSRF)
# Step 1: Ottenere token
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")

# Step 2: Usare token per query
# Ottenere istanza ID
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/instance-id)

# AZ corrente
AZ=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/placement/availability-zone)

# Region
REGION=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/placement/region)

# Credenziali IAM Role (aggiornate automaticamente)
CREDS=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/iam/security-credentials/MyRole)
echo $CREDS | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['AccessKeyId'])"

# Instance Identity Document (per verifica identità)
IDENTITY=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/dynamic/instance-identity/document)
```

---

## Placement Groups

I **Placement Groups** controllano dove vengono fisicamente collocate le istanze all'interno dell'infrastruttura AWS. Di default, AWS distribuisce le istanze per minimizzare il rischio di guasti correlati. Con i Placement Groups puoi sovrascrivere questo comportamento per ottimizzare in base alle esigenze del tuo workload — massima bandwidth (cluster), massima disponibilità (spread), o un compromesso per sistemi distribuiti come Kafka (partition).

| Tipo | Posizionamento | Use case | Note |
|------|-------------|----------|------|
| **Cluster** | Stesso rack fisico | HPC, bassa latency inter-istanza | Alta bandwidth (10-100Gbps), alto rischio fail correlato |
| **Spread** | Rack fisici diversi | Istanze critiche, HA | Max 7 istanze per AZ |
| **Partition** | Gruppi di rack separati | Hadoop, Kafka, Cassandra | Max 7 partizioni/AZ, centinaia di istanze |

```bash
# Creare Cluster Placement Group
aws ec2 create-placement-group \
    --group-name hpc-cluster \
    --strategy cluster \
    --partition-count 0    # non applicabile per cluster

# Creare Partition Placement Group
aws ec2 create-placement-group \
    --group-name kafka-partitions \
    --strategy partition \
    --partition-count 3

# Lanciare istanza in Placement Group
aws ec2 run-instances \
    --placement GroupName=hpc-cluster \
    ...
```

---

## EC2 Nitro System

Il **Nitro System** è l'hypervisor di nuova generazione AWS — dedicato hardware NVMe SSD e SR-IOV (Single Root I/O Virtualization — tecnica che permette a una scheda di rete di presentarsi come più interfacce virtuali indipendenti) networking.

- Quasi-bare-metal performance (overhead hypervisor <1%)
- ENA (Elastic Network Adapter): fino a **100 Gbps** per `u-6tb1.112xlarge`
- EFA (Elastic Fabric Adapter): per HPC/MPI (Message Passing Interface — standard di comunicazione tra processi paralleli in cluster HPC), latency simil-bare-metal
- NVMe SSD locale: I/O diretto senza hypervisor (istanze `i4i`, `c5d`, ecc.)
- **EBS-optimized** nativo: bandwidth dedicata per EBS (no condivisione con rete)

```bash
# Verificare se un'istanza usa Nitro
aws ec2 describe-instance-types \
    --instance-types m6g.xlarge \
    --query 'InstanceTypes[0].Hypervisor'
# Output: "nitro"
```

---

## Key Pairs e Accesso Sicuro

Il metodo tradizionale per accedere alle istanze EC2 è tramite **SSH con key pair**: si genera una coppia di chiavi asimmetriche, la chiave pubblica viene caricata sull'istanza al lancio, e si usa la chiave privata per autenticarsi. È un approccio funzionante ma con limitazioni operative: richiede che la porta 22 sia aperta nei Security Group, che la chiave privata sia distribuita ai collaboratori in modo sicuro, e che le istanze siano raggiungibili via rete.

I due metodi alternativi moderni — **Session Manager** e **EC2 Instance Connect** — eliminano questi problemi: non richiedono porte SSH aperte, funzionano anche su istanze senza IP pubblico, e ogni accesso viene loggato su CloudTrail.

```bash
# Creare key pair
aws ec2 create-key-pair \
    --key-name my-key \
    --key-type ed25519 \             # ED25519 più sicuro di RSA
    --key-format pem \
    --query 'KeyMaterial' \
    --output text > my-key.pem
chmod 400 my-key.pem

# SSH con key pair
ssh -i my-key.pem ec2-user@<PUBLIC_IP>

# Alternative SICURE senza SSH key aperta su Internet:
# 1. Systems Manager Session Manager (no porta 22, no public IP necessario)
aws ssm start-session --target i-1234567890abcdef0

# 2. EC2 Instance Connect (push temporanea di public key via API)
aws ec2-instance-connect send-ssh-public-key \
    --instance-id i-1234567890abcdef0 \
    --instance-os-user ec2-user \
    --ssh-public-key file://~/.ssh/id_ed25519.pub
ssh ec2-user@<PUBLIC_IP>    # Valido per 60 secondi
```

---

## Storage EC2

```bash
# EC2 Instance Store (ephemeral)
# - NVMe SSD fisicamente sul server
# - Dati persi se istanza viene stoppata/terminata
# - Solo alcune famiglie: i3, i4i, c5d, m5d...
# - Altissimi IOPS (fino a 3.3M IOPS su i4i.32xlarge)
# - Usare per tmp, cache, buffer — mai per dati persistenti

# EBS (Elastic Block Store) — persistente
# - Si può detachare e riattachare ad altra istanza
# - Snapshot per backup/AMI
# - Tipi: gp3 (default), gp2, io2, st1, sc1
# (vedere dettaglio in storage/ebs-efs-fsx.md)

# EFS (Elastic File System) — condiviso tra istanze
# - File system NFS managed
# - Montabile da multiple istanze contemporaneamente
# (vedere storage/ebs-efs-fsx.md)
```

---

## Hibernate

**EC2 Hibernate** salva il contenuto della RAM su EBS e spegne l'istanza, in modo analogo alla funzione "sleep" di un laptop. Al prossimo avvio, l'istanza ripristina lo stato in memoria e l'applicazione riprende da dove si era fermata — senza dover ripassare per il boot del sistema operativo e l'avvio dell'applicazione.

È utile quando hai processi con stato in memoria che richiedono molto tempo per l'inizializzazione (es. database in-memory, applicazioni ML che caricano modelli grandi), e vuoi poter "mettere in pausa" l'istanza risparmiando sui costi senza perdere lo stato.

```bash
# Abilitare hibernation al lancio
aws ec2 run-instances \
    --hibernation-options Configured=true \
    --block-device-mappings '[{
        "DeviceName": "/dev/xvda",
        "Ebs": {
            "Encrypted": true,       # OBBLIGATORIO per hibernate
            "VolumeSize": 50         # >= RAM size
        }
    }]' \
    ...

# Hibernare istanza
aws ec2 stop-instances \
    --instance-ids i-xxxx \
    --hibernate

# Riprendere (start normale)
aws ec2 start-instances --instance-ids i-xxxx
```

**Limiti:** RAM max 150 GB, max 60 giorni di hibernation, non tutti i tipi supportati.

---

## Monitoring EC2

```bash
# Metriche CloudWatch di default (5 minuti):
# CPUUtilization, NetworkIn, NetworkOut, DiskReadOps, DiskWriteOps

# Abilitare detailed monitoring (1 minuto) — $0.35/istanza/mese
aws ec2 monitor-instances --instance-ids i-xxxx

# Metriche non disponibili di default (richiedono CloudWatch Agent):
# Memoria (MemoryUtilization), Disk usage (%), processi

# CloudWatch Agent per metriche OS
aws ssm send-command \
    --instance-ids i-xxxx \
    --document-name "AWS-ConfigureAWSPackage" \
    --parameters '{"action": ["Install"], "name": ["AmazonCloudWatchAgent"]}' \
    --region eu-central-1
```

---

## Troubleshooting

### Scenario 1 — Istanza non raggiungibile via SSH

**Sintomo:** `ssh: connect to host <IP> port 22: Connection timed out` o `Connection refused`.

**Causa:** Security Group non permette la porta 22 in ingresso, oppure l'istanza non ha IP pubblico/Elastic IP, oppure il servizio SSH è crashato.

**Soluzione:**
```bash
# Verificare Security Group dell'istanza
aws ec2 describe-instances \
    --instance-ids i-xxxx \
    --query 'Reservations[0].Instances[0].SecurityGroups'

# Controllare regole ingress del Security Group
aws ec2 describe-security-groups \
    --group-ids sg-xxxx \
    --query 'SecurityGroups[0].IpPermissions'

# Verificare che l'istanza abbia un IP pubblico
aws ec2 describe-instances \
    --instance-ids i-xxxx \
    --query 'Reservations[0].Instances[0].{PublicIP:PublicIpAddress,State:State.Name}'

# Alternativa senza SSH: usare Session Manager (non richiede porta 22)
aws ssm start-session --target i-xxxx
```

---

### Scenario 2 — User Data non viene eseguito / errori al boot

**Sintomo:** L'istanza è avviata ma le configurazioni attese (pacchetti, servizi) non sono presenti. Nessun errore visibile nella console.

**Causa:** Errore nello script User Data (bash error, comando non trovato, variabile non definita). Il processo cloud-init esegue lo script ma fallisce silenziosamente dal punto di vista dell'utente.

**Soluzione:**
```bash
# Controllare il log di cloud-init (dalla console EC2 o via SSH/SSM)
sudo cat /var/log/cloud-init-output.log

# Stato dettagliato di cloud-init
sudo cloud-init status --long

# Verificare se il User Data è stato ricevuto correttamente
curl -H "X-aws-ec2-metadata-token: $(curl -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600')" \
    http://169.254.169.254/latest/user-data

# Se si vuole ri-eseguire User Data su un'istanza esistente (dev/test)
sudo cloud-init clean --logs
sudo cloud-init init
```

---

### Scenario 3 — Istanza in stato `pending` per lungo tempo o `terminated` subito dopo il lancio

**Sintomo:** `aws ec2 describe-instances` mostra `state: pending` per più di 5 minuti, oppure l'istanza passa direttamente da `pending` a `terminated`.

**Causa principale per `terminated` immediato:** capacità insufficiente per il tipo di istanza richiesto nella AZ scelta (comune per istanze Spot o tipi specializzati); volume EBS root troppo piccolo rispetto al minimo dell'AMI; IAM Instance Profile inesistente o con nome sbagliato.

**Soluzione:**
```bash
# Verificare il motivo della terminazione
aws ec2 describe-instances \
    --instance-ids i-xxxx \
    --query 'Reservations[0].Instances[0].StateReason'

# Controllare la dimensione minima richiesta dall'AMI
aws ec2 describe-images \
    --image-ids ami-xxxx \
    --query 'Images[0].BlockDeviceMappings[0].Ebs.VolumeSize'

# Provare una AZ diversa (se problema di capacità)
aws ec2 run-instances \
    --subnet-id subnet-yyyy \   # subnet in AZ diversa
    ...

# Verificare disponibilità del tipo di istanza per AZ
aws ec2 describe-instance-type-offerings \
    --location-type availability-zone \
    --filters Name=instance-type,Values=m6g.xlarge \
    --query 'InstanceTypeOfferings[].Location'
```

---

### Scenario 4 — CPU Credits esauriti su istanze T (burstable)

**Sintomo:** Performance applicativa degrada bruscamente su istanze t3/t4g. CloudWatch mostra `CPUCreditBalance` che scende a 0 e `CPUSurplusChargesApplied` sale.

**Causa:** Il workload ha un utilizzo CPU costantemente superiore alla baseline dell'istanza (es. t3.small ha baseline 20%). I crediti CPU si esauriscono e, se in modalità `unlimited`, iniziano ad accumularsi costi aggiuntivi.

**Soluzione:**
```bash
# Verificare il saldo crediti CPU
aws cloudwatch get-metric-statistics \
    --namespace AWS/EC2 \
    --metric-name CPUCreditBalance \
    --dimensions Name=InstanceId,Value=i-xxxx \
    --start-time $(date -u -d '1 hour ago' +%FT%TZ) \
    --end-time $(date -u +%FT%TZ) \
    --period 300 \
    --statistics Average

# Controllare costi surplus (modalità unlimited)
aws cloudwatch get-metric-statistics \
    --namespace AWS/EC2 \
    --metric-name CPUSurplusChargesApplied \
    --dimensions Name=InstanceId,Value=i-xxxx \
    --start-time $(date -u -d '1 day ago' +%FT%TZ) \
    --end-time $(date -u +%FT%TZ) \
    --period 3600 \
    --statistics Sum

# Disabilitare modalità unlimited per contenere i costi (degrada a standard)
aws ec2 modify-instance-credit-specification \
    --instance-credit-specifications InstanceId=i-xxxx,CpuCredits=standard

# Soluzione definitiva: upgrade a istanza non-burstable della stessa famiglia
# t3.medium → m5.large (baseline 100%, costo maggiore ma prevedibile)
```

---

## Riferimenti

- [EC2 User Guide](https://docs.aws.amazon.com/ec2/latest/userguide/)
- [Instance Types](https://aws.amazon.com/ec2/instance-types/)
- [EC2 Pricing](https://aws.amazon.com/ec2/pricing/)
- [Nitro System](https://aws.amazon.com/ec2/nitro/)
- [Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
