---
title: "GCP Shared Responsibility Model"
slug: shared-responsibility
category: cloud/gcp
tags: [gcp, shared-responsibility, security, compliance, iaas, paas, saas, google-cloud]
search_keywords: [GCP shared responsibility model, responsabilità condivisa GCP, sicurezza cloud Google, Google security of the cloud, security in the cloud GCP, Google managed vs customer managed, IaaS GCP responsabilità, PaaS GCP responsabilità, SaaS GCP responsabilità, Compute Engine security, Cloud Run security, GCP compliance, ISO 27001 GCP, SOC 2 GCP, PCI DSS GCP, HIPAA GCP, GDPR GCP, FedRAMP GCP, Google Compliance Reports Manager, compliance certifications Google Cloud, patching GCP, encryption at rest GCP, Cloud KMS, customer managed encryption keys, CMEK, GCP security posture, Security Command Center]
parent: cloud/gcp/fondamentali/_index
related: [cloud/gcp/fondamentali/panoramica, cloud/aws/fondamentali/shared-responsibility, cloud/azure/fondamentali/shared-responsibility]
official_docs: https://cloud.google.com/architecture/framework/security/shared-responsibility
status: complete
difficulty: beginner
last_updated: 2026-03-29
---

# GCP Shared Responsibility Model

Il **Modello di Responsabilità Condivisa** (Shared Responsibility Model) è il principio fondamentale della sicurezza in Google Cloud Platform. Definisce in modo preciso cosa è compito di Google e cosa rimane in carico al cliente, in funzione del tipo di servizio usato.

> **Google** è responsabile della sicurezza **del** cloud ("security OF the cloud").
> **Il cliente** è responsabile della sicurezza **nel** cloud ("security IN the cloud").

```
SHARED RESPONSIBILITY MODEL — GCP

┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTE                                   │
│  "Security IN the Cloud"                                         │
│                                                                  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────┐  │
│  │   Dati    │ │   IAM /   │ │    App    │ │ OS, VPC, FW    │  │
│  │ + cifratu.│ │  Policy   │ │  (codice) │ │ (Compute Eng.) │  │
│  └───────────┘ └───────────┘ └───────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  "Controlli Condivisi" — entrambi hanno responsabilità          │
│  (cifratura in transit, logging, configurazione sicura)          │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                        GOOGLE                                    │
│  "Security OF the Cloud"                                         │
│                                                                  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────┐  │
│  │  Compute  │ │  Storage  │ │ Database  │ │   Networking   │  │
│  └───────────┘ └───────────┘ └───────────┘ └────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Infrastruttura Fisica                       │   │
│  │  (hardware, datacenter, rete globale, hypervisor)        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Google è Responsabile di: "Security OF the Cloud"

Google garantisce la sicurezza dell'infrastruttura fisica, del software di sistema e dei servizi gestiti:

**Infrastruttura fisica:**
- Sicurezza fisica dei datacenter (accessi biometrici, sorveglianza, distruzione dischi)
- Hardware dei server (host, storage, networking custom-built da Google)
- Rete globale privata di Google (fibra sottomarina, POP, routing interno)
- Isolamento fisico tra regioni e zone

**Hypervisor e virtualizzazione:**
- Hypervisor custom (KVM modificato da Google) che isola le VM tra tenant diversi
- Patching del firmware, hardware e del software di sistema
- Boot sicuro verificato (Shielded VMs offrono ulteriore garanzia al cliente)

**Servizi gestiti (Managed/Serverless):**
- Per servizi come **Cloud Run, GKE Autopilot, App Engine, BigQuery, Cloud Storage, Cloud SQL** → Google gestisce OS, patching, aggiornamenti del runtime e dell'infrastruttura sottostante
- Google garantisce SLA di disponibilità per ciascun servizio
- Cifratura at rest di default per tutti i dati (AES-256) senza costo aggiuntivo

---

## Il Cliente è Responsabile di: "Security IN the Cloud"

Il cliente è responsabile di tutto ciò che crea, configura e gestisce nel cloud:

| Area | Responsabilità Cliente |
|------|------------------------|
| **Dati** | Classificazione, cifratura aggiuntiva (CMEK), backup, gestione retention |
| **IAM** | Policy, ruoli, principio del minimo privilegio, service account, chiavi JSON |
| **OS / Platform** | Patching OS (se Compute Engine), aggiornamento librerie applicative |
| **Rete** | Regole firewall VPC, route, Private Service Connect, VPC peering config |
| **Applicazione** | Sicurezza del codice, dipendenze, secret management (Secret Manager) |
| **Cifratura aggiuntiva** | Abilitare CMEK con Cloud KMS se richiesto da compliance |
| **Monitoring** | Configurare Cloud Audit Logs, Security Command Center, alerting |
| **Configurazione servizi** | Bucket policy, IAM binding, impostazioni di accesso pubblico |

---

## Matrice per Tipo di Servizio

La responsabilità del cliente **cambia significativamente** in base al modello del servizio usato.

=== "IaaS — Compute Engine (VM)"

    | Area di Responsabilità | Google | Cliente |
    |------------------------|--------|---------|
    | Hardware fisico e datacenter | ✓ | |
    | Hypervisor e rete sottostante | ✓ | |
    | Immagine OS (patch, hardening) | | ✓ |
    | Runtime (Java, Python, Node) | | ✓ |
    | Middleware (Nginx, Apache) | | ✓ |
    | Applicazione | | ✓ |
    | Regole firewall VPC | | ✓ |
    | Cifratura disco (Persistent Disk) | ✓ (default) | ✓ (CMEK opzionale) |
    | Dati applicativi | | ✓ |
    | Backup snapshot | | ✓ (configurare) |

    **Massima responsabilità cliente — massima flessibilità.**

    ```bash
    # Abilitare OS Config per patch automatiche su Compute Engine
    gcloud compute instances add-metadata my-vm \
        --zone=europe-west8-b \
        --metadata=enable-osconfig=TRUE

    # Verificare lo stato patch compliance tramite OS Config
    gcloud compute os-config patch-jobs list

    # Creare un Patch Job per applicare patch a tutte le VM con tag specifico
    gcloud compute os-config patch-jobs execute \
        --instance-filter-all \
        --description="Monthly security patching" \
        --reboot-config=DEFAULT
    ```

=== "PaaS — Cloud SQL, GKE Standard, App Engine"

    | Area di Responsabilità | Google | Cliente |
    |------------------------|--------|---------|
    | Hardware fisico e datacenter | ✓ | |
    | OS dei nodi (Cloud SQL, App Engine) | ✓ | |
    | Patching OS e engine (Cloud SQL) | ✓ | |
    | Configurazione database (parametri) | | ✓ |
    | IAM per accesso al servizio | | ✓ |
    | Cifratura at rest (default AES-256) | ✓ | |
    | CMEK (chiavi gestite cliente) | | ✓ (opzionale) |
    | Dati inseriti | | ✓ |
    | Network policy (GKE) | | ✓ |
    | Workload security (container image) | | ✓ |

    **Google gestisce OS e middleware — il cliente gestisce configurazione, rete e dati.**

    ```bash
    # Cloud SQL: verificare versione engine e manutenzione automatica
    gcloud sql instances describe my-instance \
        --format="table(name,databaseVersion,settings.maintenanceWindow,settings.backupConfiguration.enabled)"

    # Abilitare backup automatico con retention 7 giorni
    gcloud sql instances patch my-instance \
        --backup-start-time=02:00 \
        --retained-backups-count=7

    # GKE: verificare la versione del cluster e il canale di aggiornamento automatico
    gcloud container clusters describe my-cluster \
        --region=europe-west8 \
        --format="table(name,currentMasterVersion,releaseChannel.channel)"
    ```

=== "Serverless / SaaS — Cloud Storage, BigQuery, Cloud Run"

    | Area di Responsabilità | Google | Cliente |
    |------------------------|--------|---------|
    | Tutta l'infrastruttura | ✓ | |
    | Durabilità (Cloud Storage: 11 nove) | ✓ | |
    | SLA disponibilità | ✓ | |
    | Cifratura at rest di default | ✓ | |
    | CMEK | | ✓ (se richiesto da compliance) |
    | IAM e accesso ai dati | | ✓ |
    | Bucket policy / dataset ACL | | ✓ |
    | Uniform Bucket-Level Access | | ✓ (abilitare) |
    | Dati e classificazione | | ✓ |

    **Google gestisce tutto il runtime — il cliente configura accesso, cifratura e dati.**

    ```bash
    # Cloud Storage: abilitare Uniform Bucket-Level Access (consigliato)
    gcloud storage buckets update gs://my-bucket \
        --uniform-bucket-level-access

    # Verificare che il bucket non sia accessibile pubblicamente
    gcloud storage buckets get-iam-policy gs://my-bucket

    # BigQuery: verificare chi ha accesso al dataset
    bq show --format=prettyjson my-project:my_dataset | \
        python3 -c "import sys,json; [print(e) for e in json.load(sys.stdin)['access']]"

    # Cloud Run: configurare ingress solo per traffico interno o da Load Balancer
    gcloud run services update my-service \
        --region=europe-west8 \
        --ingress=internal-and-cloud-load-balancing
    ```

---

## Controlli Condivisi

Alcune aree richiedono azioni **sia da parte di Google che del cliente**:

| Controllo | Azione Google | Azione Cliente |
|-----------|---------------|----------------|
| **Cifratura in transit** | TLS su tutti gli endpoint GCP | Configurare TLS applicativo; usare SSL policy per Load Balancer |
| **Logging** | Genera i log delle API GCP | Abilitare Cloud Audit Logs, configurare sink e retention |
| **Identity** | Fornisce Cloud IAM | Configurare policy, MFA, ruoli granulari |
| **Patch infrastruttura** | Patch hypervisor, managed services | Patch OS sulle VM, patch container image |
| **Encryption key management** | Gestisce le chiavi di default | Può portare proprie chiavi con CMEK (Cloud KMS) |
| **DDoS protection** | Google Cloud Armor a livello rete | Configurare Cloud Armor policies per le proprie applicazioni |

---

## Architettura / Come Funziona

### Cifratura di Default vs CMEK

GCP cifra **tutti i dati at rest per default** con AES-256, senza costo aggiuntivo e senza configurazione richiesta dal cliente. Questo è un vantaggio rispetto ad alcuni competitor dove la cifratura va abilitata esplicitamente.

```
Livelli di cifratura in GCP:

Livello 1 — Google Default Encryption (automatica, sempre attiva)
  └── Google genera e gestisce le chiavi
  └── Copre: Persistent Disk, Cloud Storage, BigQuery, Cloud SQL, ecc.

Livello 2 — CMEK: Customer Managed Encryption Keys
  └── Il cliente crea e gestisce le chiavi in Cloud KMS
  └── Google usa le chiavi del cliente per cifrare i dati
  └── Il cliente può revocare le chiavi → Google non può più accedere ai dati
  └── Richiesto da alcune compliance (es. regolamento bancario, sanità)

Livello 3 — CSEK: Customer Supplied Encryption Keys
  └── Il cliente fornisce direttamente le chiavi a ogni operazione
  └── Le chiavi non vengono mai salvate da Google
  └── Disponibile su: Compute Engine (Persistent Disk), Cloud Storage
```

```bash
# Creare una chiave CMEK in Cloud KMS
gcloud kms keyrings create my-keyring \
    --location=europe-west8

gcloud kms keys create my-key \
    --location=europe-west8 \
    --keyring=my-keyring \
    --purpose=encryption

# Usare CMEK per un bucket Cloud Storage
gcloud storage buckets create gs://my-secure-bucket \
    --location=europe-west8 \
    --default-encryption-key=projects/my-project/locations/europe-west8/keyRings/my-keyring/cryptoKeys/my-key

# Usare CMEK per un Persistent Disk su Compute Engine
gcloud compute disks create my-disk \
    --zone=europe-west8-b \
    --kms-key=projects/my-project/locations/europe-west8/keyRings/my-keyring/cryptoKeys/my-key
```

### Security Command Center

**Security Command Center (SCC)** è lo strumento centralizzato di GCP per monitorare il posture di sicurezza e rilevare misconfigurazioni — il cliente è responsabile di abilitarlo e agire sui findings.

```bash
# Listare i security findings attivi nel progetto
gcloud scc findings list \
    --organization=ORGANIZATION_ID \
    --filter="state=ACTIVE AND severity=HIGH"

# Listare le misconfigurazioni rilevate da Security Health Analytics
gcloud scc findings list \
    --organization=ORGANIZATION_ID \
    --filter="category=PUBLIC_BUCKET_ACL OR category=OPEN_FIREWALL"
```

---

## Compliance e Certificazioni GCP

Google mantiene un programma di compliance esteso. Le certificazioni di Google attestano la sicurezza **dell'infrastruttura** — il cliente deve implementare i propri controlli per mantenere la compliance nell'uso dei servizi.

### Certificazioni Principali di Google Cloud

| Certificazione | Scope | Rilevanza |
|---------------|-------|-----------|
| **ISO 27001** | Information Security Management | Standard globale di sicurezza |
| **ISO 27017** | Cloud security controls | Specifico per provider cloud |
| **ISO 27018** | PII in public cloud | Protezione dati personali in cloud |
| **SOC 1 Type II** | Controlli su financial reporting | Rilevante per clienti finanziari |
| **SOC 2 Type II** | Security, availability, confidentiality | Standard di riferimento generale |
| **SOC 3** | Report pubblico SOC 2 | Versione pubblica del SOC 2 |
| **PCI DSS Level 1** | Payment Card Industry | Applicazioni che gestiscono pagamenti |
| **HIPAA** | Sanità USA | Con Business Associate Agreement (BAA) |
| **FedRAMP** | US Government | Google Cloud GovCloud per PA americana |
| **GDPR** | Protezione dati EU | Google come Data Processor; cliente come Data Controller |
| **C5** | Bundesamt für Sicherheit in der Informationstechnik | Mercato tedesco/europeo |
| **ENS** | Esquema Nacional de Seguridad | Pubblica amministrazione spagnola |

### GDPR: Distribuzione delle Responsabilità

```
GDPR in GCP:

Data Controller (Cliente)              Data Processor (Google)
─────────────────────────────          ──────────────────────────
- Definisce le finalità del            - Tratta i dati su istruzione
  trattamento dei dati                   del controller
- Garantisce la base giuridica         - Non usa i dati per propri fini
- Risponde agli interessati            - Notifica breach entro 72h a Google
  (diritti GDPR)                       - Fornisce DPA (Data Processing
- Configura retention e deletion         Agreement) su richiesta
- Sceglie la regione di                - Mantiene Standard Contractual
  residenza dei dati                     Clauses per trasferimenti extra-UE
```

!!! warning "GDPR: il cliente è sempre Data Controller"
    Anche se Google è certificato GDPR-compliant, il **cliente** è il Data Controller e risponde davanti all'autorità di protezione dei dati (es. Garante Privacy in Italia). Google fornisce gli strumenti (DPA, SCCs, regioni UE), ma la corretta configurazione — scelta della regione, retention policy, access logging — è responsabilità del cliente.

### Google Compliance Reports Manager

**Compliance Reports Manager** è l'equivalente GCP di AWS Artifact — una piattaforma centralizzata per scaricare i report di audit di terze parti (SOC, ISO, PCI DSS, ecc.).

```bash
# Accesso via Console: https://cloud.google.com/security/compliance/compliance-reports-manager
# I report sono scaricabili previa accettazione dei termini di utilizzo

# Verificare le certificazioni attive per una regione specifica
# (via browser: Console → Security → Compliance → Reports)

# Alternativa: Google Cloud Compliance posture può essere gestita via API
gcloud org-policies list --organization=ORGANIZATION_ID

# Verificare se ci sono policy di Organization che limitano risorse a regioni UE
gcloud org-policies describe constraints/gcp.resourceLocations \
    --organization=ORGANIZATION_ID
```

!!! tip "Organization Policy per data residency"
    Per garantire la residenza dei dati nell'UE (requisito GDPR per molte organizzazioni), usare **Organization Policy** con il constraint `gcp.resourceLocations` per limitare la creazione di risorse alle regioni europee. Questo è un controllo del cliente, non di Google.

    ```bash
    # Applicare policy per limitare le risorse alle sole regioni EU
    gcloud org-policies set-policy eu-residency-policy.yaml \
        --organization=ORGANIZATION_ID
    # dove eu-residency-policy.yaml specifica in.allowedValues: ["in:europe-locations"]
    ```

---

## Confronto AWS / Azure / GCP

| Aspetto | AWS | Azure | GCP |
|---------|-----|-------|-----|
| **Terminologia** | "Security OF/IN the cloud" | "Microsoft/Customer Responsibility" | "Security OF/IN the cloud" |
| **Cifratura at rest default** | Dipende dal servizio (S3 sì, EBS no per default) | Sì su quasi tutti i servizi | Sì su tutti i servizi |
| **Report compliance** | AWS Artifact | Microsoft Service Trust Portal | Compliance Reports Manager |
| **CMEK** | AWS KMS | Azure Key Vault (CMK) | Cloud KMS |
| **Security posture tool** | AWS Security Hub | Microsoft Defender for Cloud | Security Command Center |
| **Data residency control** | AWS Regions + SCP | Azure Policy + Blueprints | Organization Policy |
| **IaaS OS patching** | Cliente (EC2) | Cliente (VM) | Cliente (Compute Engine) |
| **PaaS OS patching** | Google/AWS (RDS, Lambda) | Microsoft (App Service, Azure SQL) | Google (Cloud SQL, Cloud Run) |
| **DDoS protection base** | AWS Shield Standard (gratis) | Azure DDoS Basic (gratis) | Google Cloud Armor (base gratis) |
| **IAM tool** | AWS IAM | Azure Active Directory + RBAC | Cloud IAM |

---

## Best Practices

!!! tip "Abilitare Cloud Audit Logs su tutti i servizi"
    Cloud Audit Logs registra chi ha fatto cosa e quando. Abilitare **Data Access Logs** (disabilitati di default perché generano volume) per servizi critici come Cloud Storage e BigQuery. Senza i log, il cliente non può dimostrare di aver agito correttamente in caso di audit.

    ```bash
    # Abilitare Data Access Logs a livello di progetto
    gcloud projects get-iam-policy my-project-id > /tmp/policy.yaml
    # Aggiungere auditLogConfigs nel file e poi:
    gcloud projects set-iam-policy my-project-id /tmp/policy.yaml
    ```

!!! tip "Usare CMEK per dati regolamentati"
    Per settori regolamentati (sanità, finanza, pubblica amministrazione), usare **CMEK** con Cloud KMS e abilitare la **Key Access Justifications** (solo con Cloud EKM). Questo permette di revocare l'accesso ai dati anche agli operatori Google in caso di controversia legale.

!!! warning "IAM: evitare ruoli primitivi e service account con chiavi JSON"
    I ruoli `roles/editor` e `roles/owner` danno accesso a tutti i servizi del progetto. Le chiavi JSON dei service account sono credenziali a lungo termine non revocabili senza eliminarle. Preferire **Workload Identity Federation** per CI/CD esterni e **service account impersonation** per accessi temporanei.

!!! warning "Cloud Storage: bloccare l'accesso pubblico per default"
    Contrariamente ad S3 (dove il blocco pubblico è ora di default), in GCP è il cliente a dover configurare IAM correttamente. Abilitare **Uniform Bucket-Level Access** ed evitare `allUsers`/`allAuthenticatedUsers` nei binding IAM, a meno di non gestire contenuto pubblico intenzionalmente.

- **Abilitare Security Command Center** almeno al tier Standard per ricevere findings di misconfiguration automatici
- **Usare VPC Service Controls** per creare perimetri di sicurezza attorno ai servizi managed (previene data exfiltration)
- **Configurare Organization Policy** per limitare regioni, tipi di macchine, e comportamenti non conformi
- **Ruotare regolarmente le chiavi Cloud KMS** — configurare la rotazione automatica ogni 90-365 giorni

---

## Troubleshooting

### Scenario 1 — Cloud Storage bucket esposto pubblicamente

**Sintomo:** Security Command Center segnala finding `PUBLIC_BUCKET_ACL`; dati potenzialmente accessibili da internet.

**Causa:** Il cliente ha assegnato il ruolo `roles/storage.objectViewer` a `allUsers` o `allAuthenticatedUsers` — responsabilità del cliente secondo il modello condiviso.

**Soluzione:** Revocare immediatamente il binding pubblico e abilitare Uniform Bucket-Level Access.

```bash
# Verificare i binding IAM del bucket
gcloud storage buckets get-iam-policy gs://my-bucket

# Rimuovere l'accesso pubblico
gcloud storage buckets remove-iam-policy-binding gs://my-bucket \
    --member="allUsers" \
    --role="roles/storage.objectViewer"

# Abilitare Uniform Bucket-Level Access (previene ACL per-oggetto)
gcloud storage buckets update gs://my-bucket \
    --uniform-bucket-level-access

# Verifica: nessun binding pubblico deve essere presente
gcloud storage buckets get-iam-policy gs://my-bucket \
    --format="json" | python3 -c "
import sys, json
policy = json.load(sys.stdin)
for b in policy.get('bindings', []):
    if 'allUsers' in b.get('members', []) or 'allAuthenticatedUsers' in b.get('members', []):
        print('WARN: public access found:', b)
"
```

---

### Scenario 2 — VM Compute Engine con OS non aggiornato

**Sintomo:** Security Command Center segnala vulnerabilità CVE critica su OS di una VM; oppure VM Infrastructure report mostra OS con patch mancanti.

**Causa:** Il patching del sistema operativo su Compute Engine (IaaS) è responsabilità esclusiva del cliente. Google non ha accesso all'OS della VM per eseguire aggiornamenti.

**Soluzione:** Applicare patch tramite OS Config Patch Management o accedere via SSH e aggiornare manualmente.

```bash
# Creare un Patch Job urgente su VM specifica
gcloud compute os-config patch-jobs execute \
    --description="Emergency CVE patching" \
    --instance-filter-names="zones/europe-west8-b/instances/my-vm" \
    --reboot-config=ALWAYS

# Monitorare lo stato del Patch Job
gcloud compute os-config patch-jobs describe PATCH_JOB_ID

# Configurare patch automatiche settimanali con Patch Deployment
gcloud compute os-config patch-deployments create weekly-patch \
    --file=patch-deployment.yaml
# patch-deployment.yaml: schedule: weekly, patchConfig: rebootConfig: DEFAULT
```

---

### Scenario 3 — Service account con chiave JSON esposta

**Sintomo:** Chiave JSON di un service account trovata in un repository Git pubblico; alert da Security Command Center o IAM Recommender su utilizzo anomalo.

**Causa:** La gestione delle credenziali IAM è responsabilità del cliente. Le chiavi JSON dei service account sono credenziali permanenti che Google non può revocare automaticamente.

**Soluzione:** Eliminare immediatamente la chiave compromessa, analizzare i log di accesso, e migrare a Workload Identity Federation.

```bash
# 1. Listare tutte le chiavi del service account compromesso
gcloud iam service-accounts keys list \
    --iam-account=my-sa@my-project.iam.gserviceaccount.com

# 2. Eliminare la chiave compromessa
gcloud iam service-accounts keys delete KEY_ID \
    --iam-account=my-sa@my-project.iam.gserviceaccount.com

# 3. Analizzare i log di accesso con la chiave compromessa (Cloud Audit Logs)
gcloud logging read \
    "protoPayload.authenticationInfo.serviceAccountKeyName:KEY_ID" \
    --limit=100 \
    --format="table(timestamp, protoPayload.methodName, protoPayload.resourceName)"

# 4. Configurare Workload Identity Federation per GitHub Actions (eliminare chiavi)
gcloud iam workload-identity-pools create "github-pool" \
    --location="global" \
    --description="GitHub Actions WIF Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"
```

---

### Scenario 4 — Audit GDPR: incertezza su dove risiedono i dati

**Sintomo:** Audit interno o DPA (Data Protection Authority) chiede dimostrazione che i dati personali non escono dall'UE. Il team non ha documentazione sulla configurazione.

**Causa:** La configurazione della data residency in GCP è responsabilità del cliente. Google fornisce le regioni EU, ma senza Organization Policy o vincoli espliciti, le risorse possono essere create in qualsiasi regione.

**Soluzione:** Verificare la configurazione attuale, applicare Organization Policy per limitare le regioni, e documentare la configurazione per il DPA.

```bash
# Verificare se esiste una policy di data residency
gcloud org-policies describe constraints/gcp.resourceLocations \
    --organization=ORGANIZATION_ID 2>/dev/null || echo "Nessuna policy di residency configurata"

# Listare tutte le risorse per regione (verificare presenza di risorse fuori EU)
gcloud asset search-all-resources \
    --scope=organizations/ORGANIZATION_ID \
    --query="location:us-*" \
    --format="table(name, assetType, location)"

# Applicare policy per limitare a regioni europee
cat > /tmp/eu-residency.yaml << 'EOF'
name: organizations/ORGANIZATION_ID/policies/gcp.resourceLocations
spec:
  rules:
  - values:
      allowedValues:
      - in:europe-locations
EOF

gcloud org-policies set-policy /tmp/eu-residency.yaml

# Verificare che la policy sia attiva
gcloud org-policies describe constraints/gcp.resourceLocations \
    --organization=ORGANIZATION_ID
```

---

## Relazioni

??? info "AWS Shared Responsibility Model — Confronto"
    Il modello GCP è concettualmente identico all'AWS: "security OF the cloud" (provider) vs "security IN the cloud" (cliente). Le differenze principali: GCP cifra at rest di default su tutti i servizi (AWS lo fa solo su alcuni), e GCP usa Cloud IAM con policy centralizzate (AWS usa IAM per-account).

    **Approfondimento →** [AWS Shared Responsibility Model](../../aws/fondamentali/shared-responsibility.md)

??? info "Azure Shared Responsibility Model — Confronto"
    Azure segue la stessa struttura. Una differenza rilevante: Azure ha una matrice esplicita che include la categoria "Condivisa" per alcune aree (es. account e identità in PaaS). GCP tende a essere più netta nella divisione.

    **Approfondimento →** [Azure Shared Responsibility Model](../../azure/fondamentali/shared-responsibility.md)

??? info "IAM GCP — Gestione identità e accessi"
    Il corretto rispetto del modello condiviso richiede una configurazione IAM precisa: ruoli granulari, principio del minimo privilegio, service account senza chiavi JSON dove possibile. La sezione IAM di Panoramica GCP copre i dettagli operativi.

    **Approfondimento →** [Panoramica GCP — IAM](panoramica.md)

---

## Riferimenti

- [GCP Shared Responsibility Model](https://cloud.google.com/architecture/framework/security/shared-responsibility)
- [Google Cloud Compliance Programs](https://cloud.google.com/security/compliance/compliance-reports-manager)
- [Cloud KMS — Customer Managed Encryption Keys](https://cloud.google.com/kms/docs)
- [Organization Policy — Resource Location Constraint](https://cloud.google.com/resource-manager/docs/organization-policy/restricting-resources)
- [Security Command Center](https://cloud.google.com/security-command-center/docs/concepts-security-command-center-overview)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Cloud Audit Logs](https://cloud.google.com/logging/docs/audit)
- [VPC Service Controls](https://cloud.google.com/vpc-service-controls/docs/overview)
- [Google Cloud GDPR](https://cloud.google.com/privacy/gdpr)
