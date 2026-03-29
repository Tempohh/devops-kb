---
title: "Azure Virtual Machines"
slug: virtual-machines-azure
category: cloud
tags: [azure, vm, vmss, managed-disks, availability-zones, scale-set, spot, proximity-placement]
search_keywords: [Azure VM, Virtual Machine Azure, VMSS Scale Set, Managed Disks, Availability Zones, Spot VM preemptible, Azure Bastion, Just-In-Time JIT, cloud-init, VM Extensions, Azure Hybrid Benefit, proximity placement group]
parent: cloud/azure/compute/_index
related: [cloud/azure/networking/vnet, cloud/azure/security/key-vault, cloud/azure/monitoring/monitor-log-analytics]
official_docs: https://learn.microsoft.com/azure/virtual-machines/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Azure Virtual Machines

## Panoramica

Le Azure Virtual Machines (VM) sono il servizio IaaS fondamentale di Azure: forniscono istanze di calcolo virtualizzate con pieno controllo su sistema operativo, software installato e configurazione di rete. A differenza dei servizi PaaS, con le VM si gestisce tutto ciò che sta sopra l'hypervisor (OS patch, runtime, middleware). Questo le rende ideali per lift & shift di applicazioni legacy, workload che richiedono OS specifici, ambienti di sviluppo e scenari HPC.

Non usare VM quando: l'applicazione è cloud-native, non richied controllo OS, o la gestione del patching è un overhead non voluto — in quei casi App Service, AKS o Azure Functions sono più appropriati.

## Famiglie di VM

Azure offre decine di famiglie di VM ottimizzate per use case specifici. La scelta corretta evita overprovisioning e riduce i costi.

| Famiglia | Serie | vCPU Range | Caratteristiche | Use Case |
|---|---|---|---|---|
| **General Purpose** | B, D, Dv5, Dsv5, Dads | 2-96 vCPU | Bilanciato CPU/memoria | Web server, dev/test, database piccoli |
| **Burstable** | B-series | 1-20 vCPU | CPU credit-based bursting | Dev/test, CI agents, web app con traffico intermittente |
| **Compute Optimized** | F, Fsv2 | 2-72 vCPU | Alto rapporto CPU/memoria | Web server ad alto traffico, batch, gaming server |
| **Memory Optimized** | E, Esv5, M, Mv2 | 2-416 vCPU | Alto rapporto memoria/CPU, fino a 12 TB RAM | SAP HANA, database in-memory, analytics, cache grandi |
| **Storage Optimized** | L, Lsv3 | 8-80 vCPU | NVMe locale ad alta velocità | Cassandra, MongoDB, Elasticsearch, data warehousing |
| **GPU** | NC, ND, NV, NCv3, NDv4 | 6-96 vCPU + GPU | GPU NVIDIA T4/A100/A10 | Machine learning training, inference, rendering, VDI |
| **HPC** | HB, HBv3, HC | 44-120 vCPU | InfiniBand RDMA, alto bandwidth memoria | CFD, molecular dynamics, weather modeling |
| **Large Memory** | M-series, Mv2 | 128-416 vCPU | Fino a 12 TB RAM | SAP HANA scale-up, database colossali |

### Naming Convention VM

Il nome di uno SKU VM segue uno schema preciso:

```
Standard_D4s_v5
│       │││  │
│       ││└─ v5 = versione generazione
│       │└── s  = supporto Premium Storage (disco SSD)
│       └─── 4  = numero vCPU
└─────────── D  = famiglia (D = General Purpose)
```

Altri suffissi comuni:
- `a` = processore AMD (es. `Standard_D4as_v5`)
- `d` = disco temporaneo NVMe locale (es. `Standard_D4ds_v5`)
- `l` = bassa memoria (less memory)
- `b` = block storage ottimizzato
- `i` = isolated (hardware dedicato single-tenant)

## Creare una VM con Azure CLI

### Esempio Completo: VM Linux con Best Security Practice

```bash
# Variabili
RG="rg-prod-westeurope"
LOCATION="westeurope"
VM_NAME="vm-app-01"
VNET_NAME="vnet-prod"
SUBNET_NAME="snet-app"
NSG_NAME="nsg-app"

# Creare il resource group
az group create \
  --name $RG \
  --location $LOCATION

# Creare la VM
az vm create \
  --resource-group $RG \
  --name $VM_NAME \
  --image Ubuntu2204 \
  --size Standard_D4s_v5 \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --nsg $NSG_NAME \
  --public-ip-sku Standard \
  --admin-username azureuser \
  --ssh-key-values ~/.ssh/id_rsa.pub \
  --zone 1 \
  --custom-data cloud-init.yaml \
  --security-type TrustedLaunch \
  --enable-secure-boot true \
  --enable-vtpm true \
  --os-disk-size-gb 128 \
  --os-disk-delete-option Delete \
  --data-disk-sizes-gb 256 \
  --storage-sku Premium_LRS \
  --assign-identity \
  --output json
```

!!! note "TrustedLaunch"
    `--security-type TrustedLaunch` abilita Secure Boot e vTPM per proteggere contro bootkit e rootkit. Disponibile per la maggior parte delle immagini di generazione 2 (Gen2). Usa sempre `--enable-secure-boot true --enable-vtpm true` insieme.

!!! tip "No Public IP"
    In produzione, considera di non assegnare Public IP (`--public-ip-address ""`) e di usare Azure Bastion per l'accesso SSH/RDP. Riduce drasticamente la superficie di attacco.

### Cloud-Init: Configurazione Automatica all'Avvio

Il file `cloud-init.yaml` permette di personalizzare la VM al primo boot:

```yaml
#cloud-config
package_update: true
package_upgrade: true

packages:
  - nginx
  - python3-pip
  - git
  - curl
  - jq

users:
  - name: appuser
    groups: sudo
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-rsa AAAA... your-key-here

write_files:
  - path: /etc/nginx/sites-available/default
    content: |
      server {
          listen 80;
          server_name _;
          location / {
              proxy_pass http://localhost:8080;
              proxy_set_header Host $host;
              proxy_set_header X-Real-IP $remote_addr;
          }
      }

runcmd:
  - systemctl enable nginx
  - systemctl start nginx
  - pip3 install gunicorn fastapi
  - echo "VM provisioning completed" >> /var/log/cloud-init-custom.log
```

## VM Extensions

Le VM Extensions permettono di installare software o eseguire script post-deploy senza accesso SSH/RDP diretto.

### Azure Monitor Agent

```bash
# Installa Azure Monitor Agent (AMA) — sostituisce MMA/OMS Agent
az vm extension set \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --name AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor \
  --version 1.0 \
  --enable-auto-upgrade true
```

### Custom Script Extension

```bash
# Esegui uno script da storage account o URL pubblico
az vm extension set \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --name CustomScript \
  --publisher Microsoft.Azure.Extensions \
  --version 2.1 \
  --settings '{
    "fileUris": ["https://mystorageaccount.blob.core.windows.net/scripts/setup.sh"],
    "commandToExecute": "bash setup.sh"
  }' \
  --protected-settings '{
    "storageAccountName": "mystorageaccount",
    "storageAccountKey": "..."
  }'
```

### Altre Extension Utili

```bash
# Disk Encryption (Azure Disk Encryption con Key Vault)
az vm encryption enable \
  --resource-group $RG \
  --name $VM_NAME \
  --disk-encryption-keyvault /subscriptions/.../resourceGroups/.../providers/Microsoft.KeyVault/vaults/mykeyvault

# AAD Login Extension (login con Entra ID invece di local user)
az vm extension set \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --name AADSSHLoginForLinux \
  --publisher Microsoft.Azure.ActiveDirectory
```

## VM Scale Sets (VMSS)

I VM Scale Sets permettono di creare e gestire un gruppo di VM identiche con autoscale automatico. Dal 2021, l'orchestration mode **Flexible** è preferito rispetto a Uniform perché supporta VM eterogenee e integrazioni più avanzate.

### Creare un VMSS

```bash
az vmss create \
  --resource-group $RG \
  --name vmss-web-frontend \
  --image Ubuntu2204 \
  --vm-sku Standard_D2s_v5 \
  --orchestration-mode Flexible \
  --instance-count 2 \
  --admin-username azureuser \
  --ssh-key-values ~/.ssh/id_rsa.pub \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --upgrade-policy-mode Rolling \
  --max-batch-instance-percent 20 \
  --max-unhealthy-instance-percent 20 \
  --max-unhealthy-upgraded-instance-percent 20 \
  --pause-time-between-batches PT5M \
  --zones 1 2 3 \
  --load-balancer vmss-lb \
  --custom-data cloud-init.yaml
```

### Autoscale per VMSS

```bash
# Crea profilo autoscale
az monitor autoscale create \
  --resource-group $RG \
  --resource vmss-web-frontend \
  --resource-type Microsoft.Compute/virtualMachineScaleSets \
  --name autoscale-vmss-web \
  --min-count 2 \
  --max-count 20 \
  --count 2

# Regola scale-out: CPU > 70% per 5 minuti → aggiungi 2 istanze
az monitor autoscale rule create \
  --resource-group $RG \
  --autoscale-name autoscale-vmss-web \
  --condition "Percentage CPU > 70 avg 5m" \
  --scale out 2 \
  --cooldown 5

# Regola scale-in: CPU < 30% per 10 minuti → rimuovi 1 istanza
az monitor autoscale rule create \
  --resource-group $RG \
  --autoscale-name autoscale-vmss-web \
  --condition "Percentage CPU < 30 avg 10m" \
  --scale in 1 \
  --cooldown 10
```

## Alta Disponibilità: Availability Zones vs Availability Sets

| Funzionalità | Availability Zones | Availability Set |
|---|---|---|
| **Protezione da** | Guasto intero datacenter (zona) | Guasto rack / unità di alimentazione |
| **SLA** | 99.99% | 99.95% |
| **Numero** | 2-3 zone per region | Fino a 3 fault domain, 20 update domain |
| **Costo** | Banda dati cross-zone a pagamento | Gratuito (si paga solo VM) |
| **Managed Disks** | Zone-redundant storage (ZRS) consigliato | Standard LRS sufficiente |
| **Use case** | Nuovo deployment, workload critici | Lift & shift da on-premises, compatibilità legacy |
| **Terraform/Bicep** | `zones: ['1', '2', '3']` | `availabilitySet` resource |

!!! tip "Raccomandazione"
    Per nuovi workload, usa sempre **Availability Zones**. Deployment zone-redundant garantisce 99.99% SLA e protegge da guasti datacenter completi.

```bash
# VM in zona specifica
az vm create --zone 1 ...

# VMSS distribuito su 3 zone
az vmss create --zones 1 2 3 ...

# Availability Set (legacy)
az vm availability-set create \
  --resource-group $RG \
  --name avset-web \
  --platform-fault-domain-count 3 \
  --platform-update-domain-count 5

az vm create --availability-set avset-web ...
```

## Managed Disks

### Tipi di Disco

| Tipo | IOPS Max | Throughput Max | Latency | Use Case |
|---|---|---|---|---|
| **Standard HDD** | 2000 | 500 MB/s | 10-100ms | Backup, archivio, dev/test |
| **Standard SSD** | 6000 | 750 MB/s | 1-10ms | Web server, dev/test produzione |
| **Premium SSD v1** | 20000 | 900 MB/s | <1ms | Database, workload I/O intensivi |
| **Premium SSD v2** | 80000 | 1200 MB/s | sub-ms | Database enterprise, SAP |
| **Ultra Disk** | 160000 | 2000 MB/s | sub-ms | Database mission-critical, HPC |

```bash
# Creare un disco managed Premium SSD
az disk create \
  --resource-group $RG \
  --name disk-data-01 \
  --size-gb 512 \
  --sku Premium_LRS \
  --zone 1 \
  --os-type Linux

# Allegare disco a VM esistente
az vm disk attach \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --name disk-data-01 \
  --new \
  --size-gb 512 \
  --sku Premium_LRS

# Snapshot disco
az snapshot create \
  --resource-group $RG \
  --name snapshot-disk-data-01-$(date +%Y%m%d) \
  --source disk-data-01 \
  --incremental true \
  --sku Standard_ZRS
```

!!! tip "Incremental Snapshots"
    Gli snapshot incrementali (`--incremental true`) salvano solo i delta dal snapshot precedente. Costano significativamente meno degli snapshot completi per dischi grandi.

### Ultra Disk

```bash
az disk create \
  --resource-group $RG \
  --name disk-ultra-01 \
  --size-gb 1024 \
  --sku UltraSSD_LRS \
  --disk-iops-read-write 50000 \
  --disk-mbps-read-write 1000 \
  --zone 1
```

## Azure Hybrid Benefit

Se si dispone di licenze Windows Server o SQL Server con Software Assurance, si può risparmiare fino al 40% sui costi VM.

```bash
# Windows Server Hybrid Benefit
az vm create \
  --license-type Windows_Server \
  ...

# SQL Server Hybrid Benefit
az vm create \
  --license-type Windows_Server \
  --image MicrosoftSQLServer:sql2019-ws2022:sqldev:latest \
  ...

# Applicare a VM esistente
az vm update \
  --resource-group $RG \
  --name $VM_NAME \
  --license-type Windows_Server
```

## Spot VM

Le Spot VM usano capacità inutilizzata Azure a prezzi ridotti (fino al 90% rispetto a PAYG). Possono essere terminate (evicted) con 30 secondi di preavviso quando Azure necessita della capacità.

```bash
az vm create \
  --resource-group $RG \
  --name vm-spot-01 \
  --image Ubuntu2204 \
  --size Standard_D4s_v5 \
  --priority Spot \
  --eviction-policy Deallocate \
  --max-price -1 \
  --admin-username azureuser \
  --ssh-key-values ~/.ssh/id_rsa.pub
```

- `--eviction-policy Deallocate`: la VM viene deallocata (non eliminata) all'eviction — si può riavviare quando c'è capacità
- `--eviction-policy Delete`: la VM viene eliminata all'eviction — usare solo per workload completamente stateless
- `--max-price -1`: accetta qualsiasi prezzo fino al prezzo PAYG

!!! warning "Workload Adatti a Spot"
    Spot VM sono adatte a: rendering, simulazioni, CI/CD, analisi batch, training ML. Non usare per: database, web server primari, qualsiasi workload che richiede disponibilità continua.

## Sicurezza Accesso: Just-In-Time e Bastion

### Just-In-Time (JIT) VM Access

JIT Access, parte di Microsoft Defender for Cloud, elimina la necessità di tenere le porte SSH/RDP sempre aperte. Le porte vengono aperte solo su richiesta per un periodo definito.

```bash
# Abilitare JIT su una VM (richiede Defender for Servers)
az security jit-policy create \
  --resource-group $RG \
  --location $LOCATION \
  --name "default" \
  --virtual-machines "[
    {
      \"id\": \"/subscriptions/.../resourceGroups/$RG/providers/Microsoft.Compute/virtualMachines/$VM_NAME\",
      \"ports\": [
        {\"number\": 22, \"protocol\": \"TCP\", \"allowedSourceAddressPrefix\": \"*\", \"maxRequestAccessDuration\": \"PT3H\"},
        {\"number\": 3389, \"protocol\": \"TCP\", \"allowedSourceAddressPrefix\": \"*\", \"maxRequestAccessDuration\": \"PT3H\"}
      ]
    }
  ]"

# Richiedere accesso JIT (apre la porta per 3 ore)
az security jit-policy initiate \
  --resource-group $RG \
  --name "default" \
  --virtual-machines "[{\"id\": \"/subscriptions/.../virtualMachines/$VM_NAME\", \"ports\": [{\"number\": 22, \"duration\": \"PT3H\", \"allowedSourceAddressPrefix\": \"YOUR_IP\"}]}]"
```

### Azure Bastion

Azure Bastion fornisce accesso SSH/RDP via browser HTTPS al portale Azure, senza esporre le VM a Internet. Elimina completamente la necessità di IP pubblici sulle VM.

```bash
# Creare subnet dedicata (nome fisso: AzureBastionSubnet, minimo /26)
az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET_NAME \
  --name AzureBastionSubnet \
  --address-prefixes 10.0.255.0/26

# Creare public IP per Bastion
az network public-ip create \
  --resource-group $RG \
  --name pip-bastion \
  --sku Standard \
  --location $LOCATION

# Creare host Bastion
az network bastion create \
  --resource-group $RG \
  --name bastion-prod \
  --public-ip-address pip-bastion \
  --vnet-name $VNET_NAME \
  --location $LOCATION \
  --sku Standard \
  --enable-tunneling true

# Connessione SSH via Bastion da CLI
az network bastion ssh \
  --resource-group $RG \
  --name bastion-prod \
  --target-resource-id /subscriptions/.../virtualMachines/$VM_NAME \
  --auth-type ssh-key \
  --username azureuser \
  --ssh-key ~/.ssh/id_rsa
```

## Operazioni Comuni

```bash
# Start / Stop / Deallocate VM
az vm start --resource-group $RG --name $VM_NAME
az vm stop --resource-group $RG --name $VM_NAME         # OS shutdown, disco e IP preservati
az vm deallocate --resource-group $RG --name $VM_NAME   # Rilascia risorse compute, no billing CPU

# Resize VM
az vm resize \
  --resource-group $RG \
  --name $VM_NAME \
  --size Standard_D8s_v5

# Listare VM nel resource group
az vm list \
  --resource-group $RG \
  --show-details \
  --output table

# Ottenere IP privato/pubblico
az vm list-ip-addresses \
  --resource-group $RG \
  --name $VM_NAME \
  --output table

# Estendere disco OS
az vm update \
  --resource-group $RG \
  --name $VM_NAME \
  --os-disk-size-gb 256
```

## Proximity Placement Groups

I Proximity Placement Groups (PPG) garantiscono che le VM siano fisicamente vicine (stesso rack o edificio) per minimizzare la latency di rete tra di loro.

```bash
# Creare PPG
az ppg create \
  --resource-group $RG \
  --name ppg-sap-hana \
  --location $LOCATION \
  --type Standard

# Creare VM nel PPG
az vm create \
  --resource-group $RG \
  --name vm-sap-app \
  --ppg ppg-sap-hana \
  ...
```

!!! warning "Limitazione PPG"
    I PPG aumentano la latency di rete tra VM ma riducono la resilienza: tutte le VM sono nello stesso dominio fisico. Non combinare PPG con Availability Zones su workload che richiedono alta disponibilità geografica.

## Pricing e Modelli di Acquisto

| Modello | Sconto vs PAYG | Commitment | Flessibilità |
|---|---|---|---|
| **Pay-As-You-Go (PAYG)** | – | Nessuno | Massima |
| **Reserved Instances (RI) 1 anno** | ~40% | 1 anno | Scope: subscription/resource group |
| **Reserved Instances (RI) 3 anni** | ~60% | 3 anni | Instance size flexibility |
| **Azure Savings Plan** | Fino a 65% | 1 o 3 anni | Più flessibile di RI, si applica a qualsiasi compute |
| **Spot VM** | Fino a 90% | Nessuno | Può essere evicted, solo workload tolerant |
| **Dev/Test pricing** | ~30-50% | Subscription EA | Solo per non-produzione |

```bash
# Esempio costo approssimativo Standard_D4s_v5 (West Europe, 2026)
# PAYG:   ~0.19 $/ora = ~140 $/mese
# RI 1yr: ~0.12 $/ora = ~86 $/mese  (40% sconto)
# RI 3yr: ~0.08 $/ora = ~58 $/mese  (60% sconto)
# Spot:   ~0.02-0.04 $/ora (variabile)
```

## Best Practices

- Usa **TrustedLaunch** (Secure Boot + vTPM) su tutte le VM Gen2
- Non assegnare Public IP alle VM in produzione — usa Azure Bastion o VPN/ExpressRoute
- Abilita **JIT Access** per VM che necessitano accesso diretto occasionale
- Usa **Managed Identity** invece di credenziali hardcoded per accesso ad altri servizi Azure
- Configura **Azure Monitor Agent** su tutte le VM per telemetria centralizzata
- Per VMSS, usa **Flexible orchestration mode** (più feature, più flessibile di Uniform)
- Imposta `--os-disk-delete-option Delete` per evitare dischi orfani quando si elimina una VM
- Abilita **Accelerated Networking** (`--accelerated-networking true`) su VM D-series e superiori per networking SR-IOV

## Troubleshooting

### Scenario 1 — VM non raggiungibile via SSH/RDP

**Sintomo:** Connessione SSH o RDP rifiutata o in timeout. La VM risulta in stato `Running` nel portale.

**Causa:** NSG blocca le porte, IP pubblico non assegnato, servizio SSH/RDP non attivo dentro la VM, o disco OS pieno/corrotto.

**Soluzione:** Verificare NSG, abilitare boot diagnostics per vedere lo stato della VM, usare la console seriale come accesso di emergenza.

```bash
# 1. Verifica stato VM e IP
az vm show --resource-group $RG --name $VM_NAME --show-details --output table

# 2. Controlla NSG associato alla NIC
NIC_ID=$(az vm show -g $RG -n $VM_NAME --query "networkProfile.networkInterfaces[0].id" -o tsv)
az network nic show --ids $NIC_ID --query "networkSecurityGroup" -o tsv

# 3. Visualizza regole NSG (verifica porta 22/3389 in entrata)
az network nsg rule list --resource-group $RG --nsg-name $NSG_NAME --output table

# 4. Accesso di emergenza via console seriale (non richiede rete)
az serial-console connect --resource-group $RG --name $VM_NAME

# 5. Boot diagnostics — log seriale per vedere errori OS
az vm boot-diagnostics enable \
  --resource-group $RG \
  --name $VM_NAME \
  --storage mystorageaccount

az vm boot-diagnostics get-boot-log --resource-group $RG --name $VM_NAME
```

---

### Scenario 2 — VM Extension bloccata in stato "Updating" o "Failed"

**Sintomo:** Un'extension (es. AzureMonitorLinuxAgent, CustomScript) rimane in stato `Transitioning` per ore, oppure mostra `ProvisioningState: Failed`.

**Causa:** Script di setup fallito dentro la VM, versione extension incompatibile con l'OS, o agente VM guest non responsivo.

**Soluzione:** Rimuovere e reinstallare l'extension. Se persiste, riavviare il VM agent.

```bash
# Visualizza stato di tutte le extension
az vm extension list \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --output table

# Rimuovi l'extension bloccata
az vm extension delete \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --name AzureMonitorLinuxAgent

# Riavvia il VM agent (da dentro la VM via SSH/console)
# Linux:
sudo systemctl restart walinuxagent

# Windows (da PowerShell dentro la VM):
# Restart-Service WindowsAzureGuestAgent

# Reinstalla l'extension dopo riavvio agent
az vm extension set \
  --resource-group $RG \
  --vm-name $VM_NAME \
  --name AzureMonitorLinuxAgent \
  --publisher Microsoft.Azure.Monitor \
  --version 1.0 \
  --enable-auto-upgrade true
```

---

### Scenario 3 — VMSS non scala: nuove istanze non raggiungono stato Healthy

**Sintomo:** L'autoscale scatta e aggiunge istanze, ma queste rimangono in stato `Creating` o passano a `Unhealthy`. Il load balancer non instrada traffico alle nuove istanze.

**Causa:** cloud-init/custom-data fallisce, health probe del load balancer non riceve risposta (porta chiusa, app non ancora pronta), o immagine corrotta.

**Soluzione:** Verificare i log di provisioning delle istanze fallite e i health probe del LB.

```bash
# Elenca istanze VMSS con stato
az vmss list-instances \
  --resource-group $RG \
  --name vmss-web-frontend \
  --output table

# Visualizza log di provisioning di una specifica istanza
INSTANCE_ID="0"
az vmss get-instance-view \
  --resource-group $RG \
  --name vmss-web-frontend \
  --instance-id $INSTANCE_ID

# Log cloud-init dall'istanza (via SSH o bastion)
# sudo cat /var/log/cloud-init-output.log
# sudo journalctl -u cloud-init

# Verifica health probe LB
az network lb probe list \
  --resource-group $RG \
  --lb-name vmss-lb \
  --output table

# Forza reimaging di un'istanza problematica
az vmss reimage \
  --resource-group $RG \
  --name vmss-web-frontend \
  --instance-id $INSTANCE_ID
```

---

### Scenario 4 — Disco OS pieno: VM non risponde, applicazione crashata

**Sintomo:** La VM è in stato `Running` ma le applicazioni crashano, SSH connette ma i comandi falliscono con "No space left on device". I log mostrano errori di scrittura su filesystem.

**Causa:** Disco OS o dati esaurito. Cause comuni: log non ruotati, dump applicativi, immagini Docker accumulate, /tmp non pulita.

**Soluzione:** Estendere il disco tramite Azure (richiede deallocate se disco OS), poi espandere la partizione dentro la VM.

```bash
# 1. Verifica dimensione disco OS corrente
az vm show \
  --resource-group $RG \
  --name $VM_NAME \
  --query "storageProfile.osDisk.diskSizeGb"

# 2. Deallocate VM (necessario per resize disco OS)
az vm deallocate --resource-group $RG --name $VM_NAME

# 3. Estendi il disco OS (es. da 128 a 256 GB)
az vm update \
  --resource-group $RG \
  --name $VM_NAME \
  --os-disk-size-gb 256

# Per disco dati (può essere fatto a caldo su Premium SSD)
az disk update \
  --resource-group $RG \
  --name disk-data-01 \
  --size-gb 512

# 4. Riavvia la VM
az vm start --resource-group $RG --name $VM_NAME

# 5. Da dentro la VM: espandi la partizione (Linux)
# sudo growpart /dev/sda 1
# sudo resize2fs /dev/sda1      # ext4
# sudo xfs_growfs /             # xfs
```

---

### Strumenti diagnostici generali

```bash
# Repair VM: monta disco OS su VM di supporto per riparazione offline
az vm repair create \
  --resource-group $RG \
  --name $VM_NAME \
  --repair-username repairuser \
  --repair-password "SecurePassword123!" \
  --verbose

# Restore VM da repair
az vm repair restore --resource-group $RG --name $VM_NAME

# Run Command: esegui script dentro la VM senza SSH (richiede VM agent)
az vm run-command invoke \
  --resource-group $RG \
  --name $VM_NAME \
  --command-id RunShellScript \
  --scripts "df -h && free -m && top -bn1 | head -20"
```

## Relazioni

??? info "VNet e Networking — Approfondimento"
    Le VM sono collegate alla rete tramite NIC (Network Interface Card) associate a subnet di una VNet. NSG e UDR controllano il traffico.

    **Approfondimento completo →** [Azure VNet](../networking/vnet.md)

??? info "Managed Identity — Approfondimento"
    Usa Managed Identity (`--assign-identity`) per autorizzare la VM ad accedere a Key Vault, Storage, ecc. senza credenziali.

    **Approfondimento completo →** [RBAC & Managed Identity](../identita/rbac-managed-identity.md)

## Riferimenti

- [Documentazione Azure Virtual Machines](https://learn.microsoft.com/azure/virtual-machines/)
- [Famiglie di dimensioni VM](https://learn.microsoft.com/azure/virtual-machines/sizes)
- [Azure VM Selector](https://azure.microsoft.com/pricing/vm-selector/)
- [Cloud-init su Azure](https://learn.microsoft.com/azure/virtual-machines/linux/using-cloud-init)
- [VM Scale Sets Documentation](https://learn.microsoft.com/azure/virtual-machine-scale-sets/)
- [Azure Bastion Documentation](https://learn.microsoft.com/azure/bastion/)
- [Prezzi VM Azure](https://azure.microsoft.com/pricing/details/virtual-machines/linux/)
